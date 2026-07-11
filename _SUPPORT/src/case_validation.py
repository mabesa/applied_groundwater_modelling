"""
case_validation — instructor validation harness for the case-study redesign.

This module is a SKELETON: it defines the canonical stage order, a registry
that later milestones use to plug in real stage implementations, and the
execution machinery (one subprocess per executed stage, with a hard timeout
and crash-proof result classification). No stage bodies are implemented here
— until a milestone calls ``register_stage(...)``, every stage reports
``NOT_IMPLEMENTED``.

Scope: pure Python plumbing. This module does NOT import flopy or pyemu and
does NOT run MODFLOW; stage bodies registered by later milestones may do so,
but they always run in an isolated subprocess (never in this process).

Design notes
------------
- Each executed stage runs ``fn(group)`` in a *fresh* Python subprocess. The
  registered callable must therefore be a plain, top-level (module-level)
  function — not a lambda, closure, or bound method — because the subprocess
  re-imports it by ``(module, qualname)`` rather than pickling it directly.
- The subprocess inherits the parent's full ``sys.path`` (via the
  ``PYTHONPATH`` environment variable) so the stage's module resolves the
  same way it does in the parent process, regardless of how that module was
  originally imported (plain script, package, or pytest-collected test
  module).
- A stage crashing via a signal (e.g. ``SIGILL``), exiting non-zero, or
  exceeding its timeout is recorded as a single ``FAIL``/``TIMEOUT`` result
  for that stage — the harness itself never crashes, and later
  stages/groups still run.
"""

from __future__ import annotations

import importlib
import inspect
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from typing import Callable, Optional

SCHEMA_VERSION = "1.0"

# Canonical stage order — do not reorder without also updating any downstream
# report consumers (this is treated as a stable public contract).
REQUIRED_STAGES: tuple[str, ...] = (
    "config",
    "mother_model_load",
    "flow_refinement",
    "base_wells",
    "scenario",
    "prt",
    "transport_handoff",
    "export_v2",
    "scratch_zip_rerun",
    "cards",
)

VALID_STATUSES = frozenset({"PASS", "FAIL", "SKIP", "TIMEOUT", "ERROR", "NOT_IMPLEMENTED"})

DEFAULT_STAGE_TIMEOUT_S = 60.0

# The canonical, closed set of case-study group ids (0-8). Used by the CLI to
# reject out-of-domain --groups selections and to define what "all groups"
# means for the --require-green release gate.
CANONICAL_GROUPS: tuple[int, ...] = tuple(range(9))

# Maximum number of ids a single "lo-hi" range in a --groups spec may expand
# to. Guards against a typo (or malicious input) like "0-999999999" silently
# building a huge in-memory list.
_MAX_GROUPS_RANGE_SPAN = 1000

# Bound on how much of a failed stage's stderr is kept for the FAIL reason.
_STDERR_TAIL_BYTES = 4096

# stage_id -> (callable, timeout_s)
_REGISTRY: dict[str, tuple[Callable, float]] = {}


# ---------------------------------------------------------------------------
# Registry API
# ---------------------------------------------------------------------------

def register_stage(stage_id: str, fn: Callable, timeout_s: Optional[float] = None) -> None:
    """Register *fn* as the implementation for canonical stage *stage_id*.

    *fn* is called as ``fn(group)`` inside a fresh subprocess, which re-imports
    it by ``(module, qualname)`` rather than pickling it directly. This
    requires *fn* to be a plain, top-level (module-level) function that a
    fresh interpreter can resolve back to the same object:

    - ``inspect.isfunction(fn)`` must be true — rejects lambdas (caught
      separately below for a clearer message), ``functools.partial`` objects,
      and callable class instances, none of which re-import the same way.
    - its ``__qualname__`` must not contain ``.`` or ``<locals>`` — rejects
      lambdas, closures, and bound/nested methods.
    - ``fn.__module__`` must not be ``"__main__"`` — a function defined in a
      script run directly re-imports as a *different* module in the
      subprocess, so it would silently fail to resolve.
    - ``importlib.import_module(fn.__module__)`` must actually expose an
      attribute named ``fn.__name__`` that *is* ``fn`` — catches the case
      where the module resolves but the top-level name doesn't point back at
      the same function (e.g. it was reassigned or deleted after def).

    All of the above are checked at registration time, so a bad registration
    fails immediately with a clear ``ValueError`` instead of mysteriously
    failing inside a subprocess later.
    """
    if stage_id not in REQUIRED_STAGES:
        raise ValueError(f"unknown stage id {stage_id!r}; must be one of {REQUIRED_STAGES}")

    qualname = getattr(fn, "__qualname__", "")
    if "." in qualname or "<" in qualname:
        raise ValueError(
            f"stage {stage_id!r}: implementation must be a top-level module "
            f"function, got __qualname__={qualname!r}"
        )

    if not inspect.isfunction(fn):
        raise ValueError(
            f"stage {stage_id!r}: implementation must be a plain top-level "
            f"function, got {type(fn)!r} (functools.partial and callable "
            "class instances are not importable by (module, qualname))"
        )

    module_name = getattr(fn, "__module__", None)
    if module_name == "__main__":
        raise ValueError(
            f"stage {stage_id!r}: implementation must not be defined in "
            "'__main__' — it must live in an importable top-level module so "
            "a subprocess can re-import it by (module, qualname)"
        )

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise ValueError(
            f"stage {stage_id!r}: could not import module {module_name!r} to "
            f"verify {fn.__name__!r} is resolvable: {exc}"
        ) from exc

    resolved = getattr(module, fn.__name__, None)
    if resolved is not fn:
        raise ValueError(
            f"stage {stage_id!r}: {module_name}.{fn.__name__} does not resolve "
            "back to the registered function (it may be nested, reassigned, "
            "or shadowed) — a subprocess re-import would not find it"
        )

    _REGISTRY[stage_id] = (fn, DEFAULT_STAGE_TIMEOUT_S if timeout_s is None else float(timeout_s))


def clear_registry() -> None:
    """Remove all registered stage implementations (used to isolate tests)."""
    _REGISTRY.clear()


def registered_stages() -> list[str]:
    """Return the sorted list of currently-registered stage ids."""
    return sorted(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# --groups parsing (shared by the CLI)
# ---------------------------------------------------------------------------

def parse_groups_spec(spec: str) -> list[int]:
    """Parse a ``--groups`` spec such as ``'0-8'`` or ``'0,3,5'`` or ``'0-2,5'``.

    Returns a sorted, de-duplicated list of integer group ids.

    Raises ``ValueError`` for an inverted range (end before start) or a range
    spanning more than ``_MAX_GROUPS_RANGE_SPAN`` ids (guards against a typo
    like ``'0-999999999'`` silently building a huge in-memory list). This is
    purely a sanity cap on the *spec syntax*; it does not know about
    ``CANONICAL_GROUPS`` — the CLI is responsible for rejecting ids outside
    the canonical 0-8 domain.
    """
    groups: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            if hi < lo:
                raise ValueError(f"invalid range {part!r}: end before start")
            if hi - lo + 1 > _MAX_GROUPS_RANGE_SPAN:
                raise ValueError(
                    f"invalid range {part!r}: spans {hi - lo + 1} ids, "
                    f"exceeds the {_MAX_GROUPS_RANGE_SPAN}-id cap"
                )
            groups.update(range(lo, hi + 1))
        else:
            groups.add(int(part))
    return sorted(groups)


# ---------------------------------------------------------------------------
# Subprocess execution of one registered stage
# ---------------------------------------------------------------------------

def _run_stage_subprocess(fn: Callable, group, timeout_s: float) -> tuple[str, str, float]:
    """Run ``fn(group)`` in an isolated subprocess; classify the outcome.

    Returns (status, reason, elapsed_s) where status is one of
    'PASS' / 'FAIL' / 'TIMEOUT'.

    Process-group hygiene: the child is launched in its own session
    (``start_new_session=True``, POSIX), so it is the leader of a fresh
    process group. If it exceeds *timeout_s*, we kill the WHOLE process
    group (``os.killpg``), not just the direct child -- otherwise a stage
    that spawns MODFLOW (or any other grandchild process) would leak that
    grandchild past the timeout. The graded platform is JupyterHub-Linux;
    macOS (also POSIX) is supported the same way.

    Output hygiene: the child's stdout is discarded (``DEVNULL``) and its
    stderr goes to an unnamed temp file (auto-cleaned on close) rather than
    being buffered in parent memory. Only a bounded tail of stderr
    (``_STDERR_TAIL_BYTES``) is ever read back, for the FAIL reason string.
    """
    module_name = fn.__module__
    qualname = fn.__qualname__

    code = textwrap.dedent(f"""
        import importlib
        m = importlib.import_module({module_name!r})
        fn = getattr(m, {qualname!r})
        fn({group!r})
        """)

    env = dict(os.environ)
    # Give the subprocess the same import environment as the parent, so a
    # stage function defined in a pytest-collected test module (or anywhere
    # else on the parent's sys.path) resolves identically.
    env["PYTHONPATH"] = os.pathsep.join(sys.path)

    t0 = time.monotonic()

    with tempfile.TemporaryFile(mode="w+b") as stderr_fh:
        proc = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=stderr_fh,
            env=env,
            start_new_session=True,
        )

        try:
            proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass  # process (group) already gone
            proc.communicate()  # reap, avoid a zombie
            return "TIMEOUT", f"stage exceeded its {timeout_s:g}s timeout", time.monotonic() - t0

        elapsed = time.monotonic() - t0
        rc = proc.returncode

        if rc == 0:
            return "PASS", "", elapsed

        if rc < 0:
            # Popen reports termination by signal N as returncode -N.
            try:
                sig_name = signal.Signals(-rc).name
            except ValueError:
                sig_name = str(-rc)
            return "FAIL", f"terminated by signal {sig_name} (exit code {rc})", elapsed

        if rc == 132:
            # 128 + SIGILL(4), as sometimes reported as a positive exit code.
            return "FAIL", f"exit code {rc} (SIGILL)", elapsed

        stderr_fh.seek(0, os.SEEK_END)
        size = stderr_fh.tell()
        stderr_fh.seek(max(0, size - _STDERR_TAIL_BYTES))
        stderr_tail = stderr_fh.read().decode(errors="replace").strip()
        reason = f"exit code {rc}"
        if stderr_tail:
            reason += f": {stderr_tail[-500:]}"
        return "FAIL", reason, elapsed


def _run_stage(stage_id: str, group, plan_only: bool) -> dict:
    """Produce the report entry for one stage id within one group."""
    entry = _REGISTRY.get(stage_id)
    if entry is None:
        return {
            "id": stage_id,
            "status": "NOT_IMPLEMENTED",
            "reason": "no implementation registered for this stage",
            "elapsed_s": 0.0,
        }

    if plan_only:
        return {
            "id": stage_id,
            "status": "SKIP",
            "reason": "plan_only: stage not executed",
            "elapsed_s": 0.0,
        }

    fn, timeout_s = entry
    try:
        status, reason, elapsed = _run_stage_subprocess(fn, group, timeout_s)
    except Exception as exc:  # harness-level failure must never propagate
        return {"id": stage_id, "status": "ERROR", "reason": f"harness error: {exc}", "elapsed_s": 0.0}

    return {"id": stage_id, "status": status, "reason": reason, "elapsed_s": round(elapsed, 3)}


# ---------------------------------------------------------------------------
# Top-level driver
# ---------------------------------------------------------------------------

def run_validation(groups: list[int], stage: Optional[str] = None, plan_only: bool = False) -> dict:
    """Run the canonical validation stage sequence for each id in *groups*.

    Parameters
    ----------
    groups:
        Group ids (e.g. case-study group numbers) to validate. Every group
        is processed independently; a crash or failure in one group's stage
        never prevents other groups (or later stages of the same group)
        from running.
    stage:
        If given, restrict *execution* to this single canonical stage id;
        all other stages are reported with status ``SKIP``. Must be one of
        ``REQUIRED_STAGES``.
    plan_only:
        Enumerate every canonical stage id per group without executing any
        stage body. Registered stages report ``SKIP``; stages with no
        registered implementation still report ``NOT_IMPLEMENTED`` (a stage
        is never silently omitted, even in plan mode).

    Returns
    -------
    dict matching:
        {schema_version, groups: [{group, stages: [{id, status, reason,
        elapsed_s}, ...]}, ...]}
    """
    if stage is not None and stage not in REQUIRED_STAGES:
        raise ValueError(f"unknown stage id {stage!r}; must be one of {REQUIRED_STAGES}")

    report_groups = []
    for group in groups:
        stages_out = []
        for stage_id in REQUIRED_STAGES:
            if stage is not None and stage_id != stage:
                stages_out.append({
                    "id": stage_id,
                    "status": "SKIP",
                    "reason": f"not selected (--stage {stage})",
                    "elapsed_s": 0.0,
                })
                continue
            stages_out.append(_run_stage(stage_id, group, plan_only))
        report_groups.append({"group": group, "stages": stages_out})

    return {"schema_version": SCHEMA_VERSION, "groups": report_groups}


def is_green(report: dict) -> bool:
    """True iff *report* has at least one group, and every required stage is
    present with status EXACTLY ``"PASS"``, in every group.

    Implemented as a strict PASS-whitelist rather than a "bad status"
    blacklist, which closes several ways a blacklist could be fooled:

    - an empty report -- ``report.get("groups")`` is ``None`` or ``[]`` --
      is NEVER green, even though a for-loop over zero groups would
      trivially satisfy a blacklist check (there would be nothing to find
      "bad");
    - a bogus/unknown status string (anything that is not literally
      ``"PASS"``, including values outside ``VALID_STATUSES``) is rejected,
      since the whitelist only accepts the one known-good value;
    - SKIP is rejected the same way: a stage that was merely skipped (e.g.
      via ``--stage`` restricting execution to a different stage, or
      ``plan_only``) has not been verified to pass;
    - a duplicate entry for the same required stage id, where at least one
      of the duplicates is not PASS, is rejected -- a report is only green
      if EVERY entry whose id is a required stage has status PASS, not just
      "some" entry;
    - a required stage id missing entirely from a group's stage list makes
      that group (and therefore the whole report) not green.
    """
    groups = report.get("groups")
    if not groups:
        return False

    required = set(REQUIRED_STAGES)
    for g in groups:
        stages = g.get("stages", [])
        seen_ids = {s["id"] for s in stages}
        if not required.issubset(seen_ids):
            return False
        for s in stages:
            if s["id"] in required and s["status"] != "PASS":
                return False
    return True
