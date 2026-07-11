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

import os
import signal
import subprocess
import sys
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

# Statuses that make a report "not green" for --require-green purposes.
_BAD_STATUSES = frozenset({"FAIL", "TIMEOUT", "ERROR", "NOT_IMPLEMENTED"})

DEFAULT_STAGE_TIMEOUT_S = 60.0

# stage_id -> (callable, timeout_s)
_REGISTRY: dict[str, tuple[Callable, float]] = {}


# ---------------------------------------------------------------------------
# Registry API
# ---------------------------------------------------------------------------

def register_stage(stage_id: str, fn: Callable, timeout_s: Optional[float] = None) -> None:
    """Register *fn* as the implementation for canonical stage *stage_id*.

    *fn* is called as ``fn(group)`` inside a fresh subprocess, so it must be
    a top-level module function (its ``__qualname__`` must not contain ``.``
    or ``<locals>``) — lambdas, closures, and bound/nested methods are
    rejected up front rather than failing mysteriously at run time.
    """
    if stage_id not in REQUIRED_STAGES:
        raise ValueError(f"unknown stage id {stage_id!r}; must be one of {REQUIRED_STAGES}")

    qualname = getattr(fn, "__qualname__", "")
    if "." in qualname or "<" in qualname:
        raise ValueError(
            f"stage {stage_id!r}: implementation must be a top-level module "
            f"function, got __qualname__={qualname!r}"
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
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT", f"stage exceeded its {timeout_s:g}s timeout", time.monotonic() - t0

    elapsed = time.monotonic() - t0
    rc = result.returncode

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

    stderr_tail = (result.stderr or b"").decode(errors="replace").strip()
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
    """True iff every required stage is present and PASS in every group.

    Any of FAIL / TIMEOUT / ERROR / NOT_IMPLEMENTED, or a required stage
    missing entirely from a group's report, makes the report "not green".
    """
    required = set(REQUIRED_STAGES)
    for g in report.get("groups", []):
        seen_ids = {s["id"] for s in g.get("stages", [])}
        if not required.issubset(seen_ids):
            return False
        for s in g.get("stages", []):
            if s["id"] in required and s["status"] in _BAD_STATUSES:
                return False
    return True
