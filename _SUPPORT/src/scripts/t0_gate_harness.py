#!/usr/bin/env python3
"""
T0.0 canonical-default gate harness.

Implements DESIGN_DOCS/T0_0_canonical_contract.md (v2):
  - Section 3    -- pre-authorised fields, schema-lifted (not excluded) on the
    reference side; side-aware schema validation (reference = frozen legacy
    schema exactly, candidate = frozen schema + pre-authorised fields exactly).
  - Section 4    -- the frozen field normalisation, including the ARRAY_PAIR
    ordering rule (Section 4.1/4.2) applied ONLY to the pre-authorised
    meta["sink_support_cells"] field.
  - Section 5.0  -- the harness (two worktrees, two fresh OS processes,
    asserted import roots, controlled cwd/config, hashed executables,
    pinned threading, hashed flow + GIS inputs).
  - Section 5.2  -- the comparison (exact string equality, field by field,
    every differing field reported with both values; full recorded
    environment fingerprint compared, not a subset).

This file is READ-ONLY with respect to the T1 modules it exercises
(transport_srcpulse_demo.py, model_io_utils.py, etc.) -- it only imports and
calls them, from inside worktrees the harness itself creates.

Three invocation modes:

  qualify  (orchestrator -- what a human runs before signature)
      uv run python _SUPPORT/src/scripts/t0_gate_harness.py qualify \\
          --workdir <scratch-dir> [--ref-commit b685f24] [--keep-worktrees]

      Creates two git worktrees at --ref-commit (default b685f24, the frozen
      reference), runs one side per worktree SEQUENTIALLY as a fresh child
      process, then compares the two canonical payloads per contract Section
      5.2. In qualification mode both worktrees are the SAME commit, so any
      reported difference is pure run-to-run nondeterminism (contract
      Section 5.1) -- not a code change. Both sides run the REFERENCE schema
      (the frozen legacy 29 fields) because b685f24 has none of the Section 3
      pre-authorised fields yet.

  compare  (orchestrator -- the actual T1 gate, Section 5.2)
      uv run python _SUPPORT/src/scripts/t0_gate_harness.py compare \\
          --workdir <scratch-dir> --candidate <commit-or-branch-or-worktree-path> \\
          [--ref-commit b685f24] [--keep-worktrees]

      Worktree A is always created fresh at --ref-commit and run under the
      REFERENCE schema. Worktree B is the candidate: if --candidate resolves
      to an existing directory it is used AS IS (assumed to already be a git
      worktree checked out at the commit/branch under test -- not created or
      removed by the harness); otherwise it is treated as a commit-ish and a
      fresh worktree is created for it, run under the CANDIDATE schema (the
      frozen 29 fields PLUS the Section 3 pre-authorised fields, and nothing
      else). The reference side's raw payload is schema-lifted per Section
      3.1/3.3 before comparison -- nothing is excluded.

  worker  (internal -- one per side, spawned by "qualify"/"compare"; not for
  direct use)
      <python> _SUPPORT/src/scripts/t0_gate_harness.py worker \\
          --worktree-root <path> --case-ws <path> --out <result.json> \\
          --side {reference,candidate}

      Runs entirely inside ONE worktree's import root: builds the canonical
      payload by calling build_srcpulse_demo() at its semantic defaults plus
      the two gate-only controls (force=True, a fresh case_ws), validates and
      normalises it per Sections 2-4 (schema depends on --side), and writes a
      JSON result record. When --side reference, the record additionally
      carries a "lifted_normalized_payload" (Section 3.1's schema-lift, using
      the identity defaults of Section 3, derived from THIS run's own values
      -- e.g. sink_support_cells' identity default is keyed off this run's
      own ext_cell and the imported module's own DOUBLET_Q, never a harness
      constant). A fatal SIGILL in the corridor-refinement retry (macOS
      arm64 / mf6 6.7.0, model_io_utils.py around line 2846) kills this
      process outright before it can write anything -- that is exactly why
      the orchestrator runs each side as its own OS process and detects a
      signal death from the child's return code.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Section 4 -- the frozen normalisation
# ---------------------------------------------------------------------------
SIGFIG_FLOAT = 12
FLOAT_FORMAT = "{:.11e}"  # 12 significant digits, one canonical exponent form

# ---------------------------------------------------------------------------
# Section 2 -- the frozen REFERENCE payload schema (used only to ASSERT the
# reflected field set matches; the enumeration itself is by reflection, per
# Section 2). This is the legacy 29/9/17/9 field set -- it never changes.
# ---------------------------------------------------------------------------
TOP_LEVEL_FIELDS = (
    "times", "breakthrough", "peak_mgL", "arrival_day", "mass_balance",
    "solubility_ok", "emergent_C_mgL", "solubility_mgL", "solubility_margin",
    "PeL_min", "PeL_max", "PeT_min", "PeT_max", "mass_g", "pulse_days",
    "total_days", "smassrate_gpd", "src_cells", "ext_cell", "inj_cell",
    "spill_xy", "alpha_L", "alpha_T", "R", "rho_b", "Kd", "lam", "meta",
    "locked",
)
MASS_BALANCE_KEYS = (
    "src_in_g", "well_out_g", "boundary_out_g", "storage_g", "decay_g",
    "total_in_g", "total_out_g", "pct_imbalance", "grouped_residual_g",
)
META_KEYS = (
    "ncpl", "nstp", "dt", "Cr", "n_src", "q_src_darcy", "b_src", "ds_src",
    "q_cell", "v_bind", "ds_bind", "ds_true_min", "courant_floor",
    "refine_radius_used", "u_reg", "cr_capped", "peak_at_last_step",
)
LOCKED_KEYS = (
    "alh", "ath1", "diffc", "porosity", "scheme", "xt3d_off",
    "refined_cell_size", "base_cell_size", "time_units",
)

# ---------------------------------------------------------------------------
# Section 3 -- pre-authorised fields, as a single table.
#
# Adding a future pre-authorised field (Section 3.1's closing sentence, and
# Section 3's own "field may be added to this table only ... with lecturer
# approval") is meant to be a ONE-LINE change here: everything else --
# CANDIDATE_TOP_LEVEL_FIELDS / CANDIDATE_META_KEYS, the ARRAY_PAIR ordering
# path set, and the reference schema-lift -- is derived from this table, not
# hand-duplicated.
#
# "identity_default" is called as identity_default(payload, constants) where
# `payload` is the (possibly partially-lifted) RAW reference payload built so
# far (native Python/numpy types, not yet normalised) and `constants` is a
# dict of values read directly off the reference run's OWN imported module
# (never a harness-side hardcoded physics constant -- Section 3.1's "the
# identity default is ... what the reference run actually did" / "can be
# independently verified from the reference run").
# ---------------------------------------------------------------------------
PRE_AUTHORIZED_FIELDS = (
    {
        # Section 3: sink_support_m -- identity default 0.0 (today's
        # behaviour: the whole pumping rate on the single nearest-centroid
        # cell). A static default, independent of the run.
        "path": ("sink_support_m",),
        "class": "FLOAT",
        "identity_default": lambda payload, constants: 0.0,
    },
    {
        # Section 3: meta["sink_support_cells"] -- identity default
        # [(ext_cell, -abs(DOUBLET_Q))], i.e. the apportionment the
        # single-cell construction ACTUALLY applies today. NOT [] -- an
        # empty list would misrepresent today's behaviour (Section 3, codex
        # r1 #3). ext_cell and DOUBLET_Q are both read off THIS reference
        # run, not hardcoded in the harness.
        "path": ("meta", "sink_support_cells"),
        "class": "ARRAY_PAIR",
        "identity_default": lambda payload, constants: [
            (int(payload["ext_cell"]), -abs(float(constants["DOUBLET_Q"])))
        ],
    },
    {
        # Section 3.3: t_peak -- the arrival_day -> t_peak rename, retained
        # as a compatibility alias. Identity default = this run's own
        # arrival_day value (Section 3.1's schema-lift for the rename).
        "path": ("t_peak",),
        "class": "FLOAT",
        "identity_default": lambda payload, constants: float(payload["arrival_day"]),
    },
)

# Derived, not hand-duplicated (see docstring above).
_PRE_AUTH_TOP_LEVEL_NAMES = tuple(
    spec["path"][0] for spec in PRE_AUTHORIZED_FIELDS if len(spec["path"]) == 1
)
_PRE_AUTH_META_NAMES = tuple(
    spec["path"][1] for spec in PRE_AUTHORIZED_FIELDS
    if len(spec["path"]) == 2 and spec["path"][0] == "meta"
)
if any(len(spec["path"]) not in (1, 2) or
       (len(spec["path"]) == 2 and spec["path"][0] != "meta")
       for spec in PRE_AUTHORIZED_FIELDS):
    raise AssertionError(
        "PRE_AUTHORIZED_FIELDS: every entry must be a top-level field "
        "(path length 1) or nested under 'meta' (path ('meta', ...)) -- "
        "Section 3 defines no other nesting today."
    )

# Section 5.2 step 2 / build_payload(side="candidate"): the candidate schema
# is the frozen legacy schema PLUS exactly the pre-authorised fields, and
# nothing else (contract Section 3.1 point 2: "the candidate payload MUST
# contain the field").
CANDIDATE_TOP_LEVEL_FIELDS = TOP_LEVEL_FIELDS + _PRE_AUTH_TOP_LEVEL_NAMES
CANDIDATE_META_KEYS = META_KEYS + _PRE_AUTH_META_NAMES

# Section 4.1: ARRAY_PAIR is "sorted by the leading INT" -- and Section 4.2
# is explicit that this sort applies to meta["sink_support_cells"] ALONE;
# every other array (times, breakthrough, src_cells, u_reg, ...) keeps its
# produced order. Path-aware: normalize() below only sorts a container whose
# path is in this set.
ARRAY_PAIR_PATHS = frozenset(
    spec["path"] for spec in PRE_AUTHORIZED_FIELDS if spec["class"] == "ARRAY_PAIR"
)

# Fields NOT in the payload (Section 4.4) -- recorded alongside for
# provenance only, never compared: wall-clock timings, workspace paths,
# hostnames. (The environment fingerprint itself IS compared -- Section 5.0 /
# 5.2 step 1 -- just not folded into the payload.)


class GateAbort(RuntimeError):
    """mass_balance carried the 'error' sentinel or a non-conforming keyset
    (contract Section 2.2), or the top-level/nested field set did not match
    the schema for this side (Section 2.5 / Section 3.1). A broken run or a
    schema violation, not a payload difference -- do not compare, do not
    normalise, do not record a canonical result."""


def _ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Section 4.1 / 4.3 -- per-class formatting
# ---------------------------------------------------------------------------
def _format_float(x: float) -> str:
    x = float(x)
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0.0:
        x = 0.0  # Section 4.3: -0.0 normalised to 0.0 BEFORE formatting
    return FLOAT_FORMAT.format(x)


def normalize(value, path: tuple = ()):
    """Section 4: recursive normaliser, one formatter applied everywhere.

    Every leaf becomes a canonical string (FLOAT_FORMAT for floats, plain
    decimal for ints, "true"/"false" for bools, NFC text for strings).
    Mapping keys are sorted lexicographically at every depth (Section 4.2).

    Array/list/tuple/ndarray element order is PATH-AWARE (Section 4.2):
    preserved for every array (times/breakthrough are time series and must
    never be sorted) EXCEPT a container whose `path` is in ARRAY_PAIR_PATHS
    (today: only meta["sink_support_cells"], Section 3/4.1), which is sorted
    by the leading INT of each [INT, FLOAT] pair and formatted as such.

    `path` is a tuple of the dict keys traversed to reach `value`, e.g.
    normalize(payload) -> normalize(payload["meta"], path=("meta",)) ->
    normalize(payload["meta"]["sink_support_cells"], path=("meta",
    "sink_support_cells")).
    """
    import numpy as np

    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if value is None:
        # Section 4.3: None in a numeric field is a DEFECT, not a value --
        # it is still rendered so the mismatch is visible in the diff rather
        # than raising and hiding which field it was.
        return "null"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return _format_float(float(value))
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {
            str(k): normalize(value[k], path + (str(k),))
            for k in sorted(value.keys(), key=str)
        }
    if isinstance(value, (list, tuple, np.ndarray)):
        items = list(value)
        if path in ARRAY_PAIR_PATHS:
            # Section 3 / 4.1: ARRAY_PAIR -- list of two-element [INT, FLOAT]
            # lists, sorted by the leading INT. The ONE array field that is
            # sorted; see the docstring above.
            def _leading_int(pair):
                a, _b = pair
                return int(a)

            return [
                [normalize(int(a), path), normalize(float(b), path)]
                for a, b in sorted(items, key=_leading_int)
            ]
        return [normalize(v, path) for v in items]
    raise TypeError(f"normalize(): unhandled type {type(value)!r} for value {value!r}")


# ---------------------------------------------------------------------------
# Section 3.1 -- the reference schema-lift
# ---------------------------------------------------------------------------
def lift_reference(raw_payload: dict, constants: dict) -> dict:
    """Section 3.1: lift the b685f24 reference payload into the frozen
    (legacy + pre-authorised) schema by adding each Section 3 field at its
    identity-default value, computed from THIS reference run's own values
    (never a harness-side hardcoded default). Returns a NEW raw (not yet
    normalised) payload dict; the caller normalises it with normalize(),
    which is what applies the ARRAY_PAIR ordering to the lifted
    sink_support_cells exactly as it would for a real candidate.

    Nothing is excluded afterwards (Section 3.1 point 3/4) -- the caller
    compares the lifted+normalised reference against the candidate's
    normalised payload field-for-field, including the lifted fields.
    """
    lifted = dict(raw_payload)
    lifted["meta"] = dict(raw_payload["meta"])
    for spec in PRE_AUTHORIZED_FIELDS:
        value = spec["identity_default"](lifted, constants)
        cur = lifted
        for key in spec["path"][:-1]:
            cur = cur[key]
        cur[spec["path"][-1]] = value
    return lifted


# ---------------------------------------------------------------------------
# Section 2 / 3 -- payload construction BY REFLECTION over SrcPulseDemo,
# schema validated per SIDE (Section 3.1: reference = frozen legacy schema
# exactly; candidate = frozen schema + pre-authorised fields exactly).
# ---------------------------------------------------------------------------
def build_payload(result, side: str) -> dict:
    """Reflect over every non-underscore field of the SrcPulseDemo dataclass
    instance (Section 2), assert the reflected field set matches the schema
    for `side` (Section 2.5 for the reference side: exactly the frozen 29;
    Section 3.1 for the candidate side: the frozen 29 PLUS exactly the
    pre-authorised fields -- an extra field on EITHER side is still a
    failure edge to T0, it is not merely "allowed to differ"), then assert
    the nested keysets (Section 2.2b): mass_balance (9, unaffected by
    Section 3), meta (17 on the reference side / 17 + len(pre-auth meta
    fields) on the candidate side), locked (9, unaffected).

    Raises GateAbort per Section 2.2 if mass_balance carries the "error"
    sentinel key or any non-conforming keyset -- that is a broken run, not a
    payload difference, and the gate must not compare/normalise/record it.
    """
    if side not in ("reference", "candidate"):
        raise ValueError(f"build_payload: side must be 'reference' or 'candidate', got {side!r}")

    expected_top = set(TOP_LEVEL_FIELDS if side == "reference" else CANDIDATE_TOP_LEVEL_FIELDS)
    expected_meta = set(META_KEYS if side == "reference" else CANDIDATE_META_KEYS)

    names = tuple(f.name for f in dataclasses.fields(result) if not f.name.startswith("_"))
    if set(names) != expected_top:
        missing = sorted(expected_top - set(names))
        extra = sorted(set(names) - expected_top)
        raise GateAbort(
            f"top-level payload field set changed for side={side!r} "
            f"(Section 2.5 / 3.1): missing={missing} extra={extra}"
        )

    payload = {name: getattr(result, name) for name in names}

    mb = payload["mass_balance"]
    if "error" in mb or set(mb.keys()) != set(MASS_BALANCE_KEYS):
        raise GateAbort(
            f"mass_balance abort (Section 2.2): keys={sorted(mb.keys())}"
            + (f" error={mb.get('error')!r}" if "error" in mb else "")
        )

    meta = payload["meta"]
    if set(meta.keys()) != expected_meta:
        raise GateAbort(
            f"meta keyset changed for side={side!r} (Section 2.2b / 3.1): "
            f"keys={sorted(meta.keys())} expected={sorted(expected_meta)}"
        )

    locked = payload["locked"]
    if set(locked.keys()) != set(LOCKED_KEYS):
        raise GateAbort(f"locked keyset changed (Section 2.2b): keys={sorted(locked.keys())}")

    return payload


# ---------------------------------------------------------------------------
# small utilities shared by worker + orchestrator
# ---------------------------------------------------------------------------
def _sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit(worktree_root) -> str:
    r = subprocess.run(
        ["git", "-C", str(worktree_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return r.stdout.strip()


def _tail(path, n=80) -> str:
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except Exception as e:
        return f"(could not read log: {e})"
    return "\n".join(lines[-n:])


# ===========================================================================
# WORKER -- runs entirely inside ONE worktree's import root, one OS process
# ===========================================================================
def run_worker(args) -> None:
    worktree_root = Path(args.worktree_root).resolve()
    case_ws = Path(args.case_ws)
    out_path = Path(args.out)
    side = args.side

    record = {"status": "ERROR", "error": "worker did not complete"}
    try:
        # ---- Section 1.2: cold-workspace policy -- case_ws must be fresh ----
        if case_ws.exists():
            raise RuntimeError(
                f"case_ws already exists (must be a fresh, previously "
                f"non-existent directory per Section 1.2): {case_ws}"
            )

        # ---- Section 5.0: controlled cwd, BEFORE any import that walks it ----
        os.chdir(worktree_root)

        # ---- Section 5.0: asserted import roots -- worktree's own _SUPPORT/src
        # must be found BEFORE anything else on sys.path.
        src_dir = str(worktree_root / "_SUPPORT" / "src")
        sys.path.insert(0, src_dir)

        import numpy as np
        import flopy
        import transport_srcpulse_demo as tsd
        import model_io_utils as mio

        def _resolve(p):
            return str(Path(p).resolve())

        def _in_worktree(p):
            rp = _resolve(p)
            wt = str(worktree_root)
            return rp == wt or rp.startswith(wt + os.sep)

        if not _in_worktree(tsd.__file__):
            raise RuntimeError(
                f"transport_srcpulse_demo imported from OUTSIDE its own worktree "
                f"(stale sys.path?): {tsd.__file__} not under {worktree_root}"
            )
        if not _in_worktree(mio.__file__):
            raise RuntimeError(
                f"model_io_utils imported from OUTSIDE its own worktree "
                f"(stale sys.path?): {mio.__file__} not under {worktree_root}"
            )

        import data_utils

        data_folder = data_utils.get_default_data_folder()

        # ---- Section 5.0: absolute, hashed executables ----
        mf6_exe = shutil.which("mf6") or os.path.expanduser("~/.local/share/flopy/bin/mf6")
        tri_exe = shutil.which("triangle") or os.path.expanduser(
            "~/.local/share/flopy/bin/triangle"
        )
        if not os.path.isfile(mf6_exe):
            raise RuntimeError(f"mf6 executable not found (resolved to {mf6_exe!r})")
        if not os.path.isfile(tri_exe):
            raise RuntimeError(f"triangle executable not found (resolved to {tri_exe!r})")
        mf6_real = os.path.realpath(mf6_exe)
        tri_real = os.path.realpath(tri_exe)
        mf6_sha = _sha256_file(mf6_real)
        tri_sha = _sha256_file(tri_real)

        # ---- Section 1.1 / 5.0: flow + GIS fingerprints ----
        flow_fp = mio.calibrated_flow_fingerprint()
        boundary_path = data_utils.download_named_file(name="model_boundary", data_type="gis")
        rivers_path = data_utils.download_named_file(name="rivers", data_type="gis")
        boundary_sha = _sha256_file(boundary_path)
        rivers_sha = _sha256_file(rivers_path)

        env_fp = {
            "os": platform.platform(),
            "machine": platform.machine(),
            "python_version": sys.version,
            "python_executable": os.path.realpath(sys.executable),
            "flopy_version": getattr(flopy, "__version__", "unknown"),
            "numpy_version": getattr(np, "__version__", "unknown"),
            "mf6_realpath": mf6_real,
            "mf6_sha256": mf6_sha,
            "triangle_realpath": tri_real,
            "triangle_sha256": tri_sha,
            "data_folder": data_folder,
            "flow_fingerprint": flow_fp,
            "model_boundary_path": str(boundary_path),
            "model_boundary_sha256": boundary_sha,
            "rivers_path": str(rivers_path),
            "rivers_sha256": rivers_sha,
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "GDAL_NUM_THREADS": os.environ.get("GDAL_NUM_THREADS"),
            "PATH": os.environ.get("PATH"),
            "worktree_root": str(worktree_root),
            "worktree_commit": _git_commit(worktree_root),
            "case_ws": str(case_ws),
            "transport_srcpulse_demo_file": _resolve(tsd.__file__),
            "model_io_utils_file": _resolve(mio.__file__),
        }

        # ---- Section 1: the exact invocation -- semantic defaults + the two
        # gate-only controls (force, fresh case_ws). Every other argument is
        # left at build_srcpulse_demo's declared default.
        t0 = time.time()
        result = tsd.build_srcpulse_demo(case_ws=case_ws, force=True)
        wall_s = time.time() - t0

        payload = build_payload(result, side=side)  # raises GateAbort per Section 2.2/2.5/3.1
        normalized = normalize(payload)  # Section 4

        record = {
            "status": "OK",
            "side": side,
            "wall_s": wall_s,
            "env": env_fp,
            "normalized_payload": normalized,
            "raw_top_fields": sorted(payload.keys()),
        }

        if side == "reference":
            # Section 3.1: lift the reference into the frozen schema so it can
            # be compared against a candidate with no exclusions. Constants
            # are read off THIS run's own imported module -- never hardcoded
            # in the harness (Section 3.1: "can be independently verified
            # from the reference run").
            lifted_raw = lift_reference(payload, constants={"DOUBLET_Q": tsd.DOUBLET_Q})
            record["lifted_normalized_payload"] = normalize(lifted_raw)

    except GateAbort as e:
        record = {"status": "ABORT", "side": side, "error": str(e)}
    except Exception as e:  # noqa: BLE001 -- deliberately broad: report, don't crash silently
        record = {"status": "ERROR", "side": side, "error": str(e), "traceback": traceback.format_exc()}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2))
    sys.exit(0 if record["status"] == "OK" else 1)


# ===========================================================================
# ORCHESTRATOR shared plumbing
# ===========================================================================
def _child_env(flopy_bindir: str) -> dict:
    """Section 5.0: pinned threading BEFORE Python starts; identical process
    environment on both sides (the only permitted difference between sides
    is the worktree path / case_ws / --out / --side passed on argv, not
    anything in this env dict)."""
    env = dict(os.environ)
    for k in (
        "OMP_NUM_THREADS", "GDAL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
        "OMP_THREAD_LIMIT", "NUMBA_NUM_THREADS",
    ):
        env[k] = "1"
    env["PATH"] = flopy_bindir + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONPATH", None)  # no stray import roots leaking in
    return env


def _run_side(python_exe, this_file, worktree_root, case_ws, out_path, log_path, env, side):
    cmd = [
        python_exe, this_file, "worker",
        "--worktree-root", str(worktree_root),
        "--case-ws", str(case_ws),
        "--out", str(out_path),
        "--side", side,
    ]
    with open(log_path, "w") as lf:
        lf.write(f"cmd: {cmd}\ncwd: {worktree_root}\nPATH: {env['PATH']}\n\n")
        lf.flush()
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=str(worktree_root), env=env,
                               stdout=lf, stderr=subprocess.STDOUT)
        wall = time.time() - t0
    return proc.returncode, wall


def _side_outcome(rc: int, result_path: Path, log_path: Path) -> dict:
    if rc is not None and rc < 0:
        sig = -rc
        return {
            "status": "SIGNAL", "signal": sig, "returncode": rc,
            "note": "fatal signal -- cannot be caught by any try/except in the worker "
                    "(model_io_utils.py ~2846); this is the SIGILL hazard Section 5.0 "
                    "mandates process isolation for.",
            "log_tail": _tail(log_path),
        }
    if result_path.exists():
        try:
            data = json.loads(result_path.read_text())
        except Exception as e:
            return {"status": "UNREADABLE_RESULT", "error": str(e), "log_tail": _tail(log_path)}
        data["log_tail"] = _tail(log_path)
        data.setdefault("returncode", rc)
        return data
    return {"status": "NO_RESULT_FILE", "returncode": rc, "log_tail": _tail(log_path)}


def _diff_normalized(a, b, path=""):
    """Section 5.2 step 8: on mismatch, report EVERY differing field with
    both values -- never stop at the first."""
    mismatches = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else k
            if k not in a:
                mismatches.append({"field": p, "A": "<MISSING>", "B": b[k]})
            elif k not in b:
                mismatches.append({"field": p, "A": a[k], "B": "<MISSING>"})
            else:
                mismatches.extend(_diff_normalized(a[k], b[k], p))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            mismatches.append({"field": path, "A": f"<list len {len(a)}>", "B": f"<list len {len(b)}>"})
        else:
            for i, (av, bv) in enumerate(zip(a, b)):
                mismatches.extend(_diff_normalized(av, bv, f"{path}[{i}]"))
    else:
        if a != b:
            mismatches.append({"field": path, "A": a, "B": b})
    return mismatches


# ---------------------------------------------------------------------------
# Section 5.0 / 5.2 step 1 -- the environment fingerprint is compared IN
# FULL, not a curated subset, and a difference FAILS (never a warning). The
# only keys excluded are the ones Section 1.3 explicitly says are PERMITTED
# to differ: everything that is a function of which worktree/commit a side
# is running (its path, its own commit, its own case_ws, the two resolved
# module __file__s). Compared as a set union of whatever either side
# recorded, so a key present on only one side is still reported.
# ---------------------------------------------------------------------------
ENV_EXPECTED_DIFF_KEYS = frozenset((
    "worktree_root", "worktree_commit", "case_ws",
    "transport_srcpulse_demo_file", "model_io_utils_file",
))


def _env_mismatches(env_a: dict, env_b: dict) -> dict:
    mismatches = {}
    for key in sorted((set(env_a) | set(env_b)) - ENV_EXPECTED_DIFF_KEYS):
        va, vb = env_a.get(key), env_b.get(key)
        if va != vb:
            mismatches[key] = {"A": va, "B": vb}
    return mismatches


def _compare_normalized(a_norm: dict, b_norm: dict, env_a: dict, env_b: dict) -> dict:
    """Shared Section 5.2 comparison core: full env-fingerprint equality
    (step 1) plus exact string equality field by field on the already
    normalised (and, for a lifted reference, already schema-lifted) payload
    dicts (steps 6-8)."""
    env_mismatches = _env_mismatches(env_a, env_b)
    payload_mismatches = _diff_normalized(a_norm, b_norm)
    passed = not env_mismatches and not payload_mismatches
    return {
        "result": "PASS" if passed else "FAIL",
        "env_mismatches": env_mismatches,
        "payload_mismatch_count": len(payload_mismatches),
        "payload_mismatches": payload_mismatches,
    }


def compare_sides(a: dict, b: dict) -> dict:
    """Section 5.1 qualification comparison: both sides are the SAME schema
    (side="reference" on both), so their normalized_payload dicts are
    compared directly -- no lift, nothing pre-authorised is in play because
    b685f24 doesn't have those fields yet."""
    summary = {
        "side_A": {"status": a.get("status"), "wall_s": a.get("wall_s")},
        "side_B": {"status": b.get("status"), "wall_s": b.get("wall_s")},
    }

    if a.get("status") != "OK" or b.get("status") != "OK":
        summary["qualification"] = "FAIL"
        summary["reason"] = "one or both sides did not produce a valid canonical payload"
        return {"summary": summary, "side_A": a, "side_B": b}

    core = _compare_normalized(a["normalized_payload"], b["normalized_payload"], a["env"], b["env"])
    summary["qualification"] = core["result"]
    summary["env_mismatches"] = core["env_mismatches"]
    summary["payload_mismatch_count"] = core["payload_mismatch_count"]
    summary["payload_mismatches"] = core["payload_mismatches"]
    return {"summary": summary, "side_A": a, "side_B": b}


def compare_reference_vs_candidate(a: dict, b: dict) -> dict:
    """Section 5.2, the actual T1 gate: side A is the b685f24 REFERENCE
    (its raw payload already schema-lifted per Section 3.1/3.3 by the
    worker -- "lifted_normalized_payload"), side B is the T1 CANDIDATE (its
    "normalized_payload" already validated against the candidate schema by
    the worker). Nothing is excluded (Section 3.1 point 3)."""
    summary = {
        "side_A_reference": {"status": a.get("status"), "wall_s": a.get("wall_s")},
        "side_B_candidate": {"status": b.get("status"), "wall_s": b.get("wall_s")},
    }

    if a.get("status") != "OK" or b.get("status") != "OK":
        summary["comparison"] = "FAIL"
        summary["reason"] = "one or both sides did not produce a valid canonical payload"
        return {"summary": summary, "side_A_reference": a, "side_B_candidate": b}

    if "lifted_normalized_payload" not in a:
        summary["comparison"] = "FAIL"
        summary["reason"] = (
            "reference side did not carry a lifted_normalized_payload -- was it run "
            "with --side reference?"
        )
        return {"summary": summary, "side_A_reference": a, "side_B_candidate": b}

    core = _compare_normalized(
        a["lifted_normalized_payload"], b["normalized_payload"], a["env"], b["env"]
    )
    summary["comparison"] = core["result"]
    summary["env_mismatches"] = core["env_mismatches"]
    summary["payload_mismatch_count"] = core["payload_mismatch_count"]
    summary["payload_mismatches"] = core["payload_mismatches"]
    return {"summary": summary, "side_A_reference": a, "side_B_candidate": b}


def _ensure_config(repo_root: Path, worktree: Path, copy_if_missing_only: bool) -> None:
    """Section 5.0: a fresh worktree has only config_template.py; this
    machine's gitignored config.py must be propagated so both sides resolve
    the SAME data folder (Section 1.1). For a harness-CREATED worktree we
    always overwrite (it is guaranteed empty of a prior config.py from a
    real dev session). For a pre-existing candidate worktree path the
    caller passes copy_if_missing_only=True so a real developer worktree's
    own config.py is never clobbered; if it diverges from the repo's, that
    surfaces later as a data_folder env mismatch (Section 5.2 step 1) rather
    than being silently patched over."""
    cfg = repo_root / "config.py"
    if not cfg.exists():
        raise SystemExit(
            "repo config.py not found -- cannot propagate the data-source config "
            "to the worktrees (both sides would silently diverge onto config_template.py)"
        )
    dest = worktree / "config.py"
    if copy_if_missing_only and dest.exists():
        _log(f"NOTE: {dest} already exists -- leaving it as is (candidate worktree not "
             f"created by this harness run); a data_folder mismatch will surface in the "
             f"environment-fingerprint comparison if it diverges from {cfg}")
        return
    shutil.copy2(cfg, dest)
    _log(f"copied {cfg} into {worktree}")


def _project_venv_python(repo_root: Path) -> str:
    # NOT os.path.realpath(sys.executable): uv creates .venv/bin/python3 as a
    # SYMLINK to a shared uv-managed base interpreter. Resolving the symlink
    # and invoking that target directly loses the venv (no pyvenv.cfg next to
    # the base interpreter -> it falls back to the base site-packages, which
    # has none of flopy/numpy/geopandas installed). Invoke the venv launcher
    # itself so both worker processes get the SAME project virtualenv
    # (Section 1.3: "one FloPy, one Python") -- the only thing that must
    # differ between the two sides is the worktree, never the interpreter.
    python_exe = str(repo_root / ".venv" / "bin" / "python3")
    if not os.path.isfile(python_exe):
        raise SystemExit(f"project venv python not found: {python_exe}")
    return python_exe


def _resolve_commit(repo_root: Path, ref: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", ref],
        capture_output=True, text=True, check=True,
    )
    return r.stdout.strip()


# ===========================================================================
# ORCHESTRATOR -- "qualify": two worktrees, two sequential fresh processes,
# same commit on both sides.
# ===========================================================================
def run_qualification(args) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    ref_commit = args.ref_commit
    worktree_a = workdir / "worktree_A"
    worktree_b = workdir / "worktree_B"
    case_ws_a = workdir / "case_ws_A"
    case_ws_b = workdir / "case_ws_B"
    log_a = workdir / "side_A.log"
    log_b = workdir / "side_B.log"
    result_a = workdir / "side_A_result.json"
    result_b = workdir / "side_B_result.json"
    report_path = workdir / "qualification_report.json"

    for p in (case_ws_a, case_ws_b):
        if p.exists():
            raise SystemExit(f"case_ws already exists -- must be fresh (Section 1.2): {p}")
    for wt in (worktree_a, worktree_b):
        if wt.exists():
            raise SystemExit(f"worktree path already exists: {wt}")

    _log(f"qualification: {ref_commit} vs {ref_commit} (same commit -- pure run-to-run "
         f"nondeterminism measurement, Section 5.1)")
    _log(f"workdir: {workdir}")

    _log(f"creating worktree A at {worktree_a} @ {ref_commit}")
    subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                    str(worktree_a), ref_commit], check=True)
    _log(f"creating worktree B at {worktree_b} @ {ref_commit}")
    subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                    str(worktree_b), ref_commit], check=True)

    _ensure_config(repo_root, worktree_a, copy_if_missing_only=False)
    _ensure_config(repo_root, worktree_b, copy_if_missing_only=False)

    python_exe = _project_venv_python(repo_root)
    this_file = str(Path(__file__).resolve())
    flopy_bindir = os.path.expanduser("~/.local/share/flopy/bin")
    env = _child_env(flopy_bindir)
    _log(f"python: {python_exe}")
    _log(f"PATH (child): {env['PATH']}")
    _log(f"thread pins: OMP_NUM_THREADS={env['OMP_NUM_THREADS']} "
         f"GDAL_NUM_THREADS={env['GDAL_NUM_THREADS']}")

    # Both sides are the frozen reference schema -- b685f24 has none of the
    # Section 3 pre-authorised fields yet.
    _log("launching side A (worktree_A / case_ws_A) -- cold corridor refine + "
         "pilot + production coupled GWF+GWT solve ...")
    rc_a, wall_a = _run_side(python_exe, this_file, worktree_a, case_ws_a,
                              result_a, log_a, env, side="reference")
    _log(f"side A finished: returncode={rc_a} outer_wall={wall_a:.1f}s")

    _log("launching side B (worktree_B / case_ws_B) -- cold corridor refine + "
         "pilot + production coupled GWF+GWT solve ...")
    rc_b, wall_b = _run_side(python_exe, this_file, worktree_b, case_ws_b,
                              result_b, log_b, env, side="reference")
    _log(f"side B finished: returncode={rc_b} outer_wall={wall_b:.1f}s")

    a = _side_outcome(rc_a, result_a, log_a)
    a.setdefault("wall_s", wall_a)
    a["outer_wall_s"] = wall_a
    b = _side_outcome(rc_b, result_b, log_b)
    b.setdefault("wall_s", wall_b)
    b["outer_wall_s"] = wall_b

    report = compare_sides(a, b)
    report_path.write_text(json.dumps(report, indent=2))
    _log(f"report written: {report_path}")
    _log("SUMMARY:\n" + json.dumps(report["summary"], indent=2))

    if not args.keep_worktrees:
        _log("removing worktrees (case_ws directories are kept -- they are the evidence)")
        subprocess.run(["git", "-C", str(repo_root), "worktree", "remove", "--force",
                        str(worktree_a)], check=False)
        subprocess.run(["git", "-C", str(repo_root), "worktree", "remove", "--force",
                        str(worktree_b)], check=False)

    return 0 if report["summary"]["qualification"] == "PASS" else 1


# ===========================================================================
# ORCHESTRATOR -- "compare": Section 5.2, the actual T1 gate. Reference at
# --ref-commit (always a fresh harness-created worktree) versus --candidate
# (a commit-ish -> fresh harness-created worktree, OR an existing directory
# -> used as is, never created or removed by the harness).
# ===========================================================================
def run_compare(args) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    ref_commit = args.ref_commit
    candidate_arg = args.candidate
    candidate_path = Path(candidate_arg).expanduser()
    candidate_is_existing_worktree = candidate_path.is_dir()

    worktree_a = workdir / "worktree_A_reference"
    case_ws_a = workdir / "case_ws_A_reference"
    log_a = workdir / "side_A_reference.log"
    result_a = workdir / "side_A_reference_result.json"

    if candidate_is_existing_worktree:
        worktree_b = candidate_path.resolve()
        _log(f"--candidate {candidate_arg!r} resolves to an existing directory -- using it "
             f"AS IS (not created or removed by this harness run)")
        r = subprocess.run(["git", "-C", str(worktree_b), "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(
                f"--candidate path {worktree_b} does not look like a git worktree "
                f"(git rev-parse failed): {r.stderr.strip()}"
            )
    else:
        worktree_b = workdir / "worktree_B_candidate"
        if worktree_b.exists():
            raise SystemExit(f"worktree path already exists: {worktree_b}")
    case_ws_b = workdir / "case_ws_B_candidate"
    log_b = workdir / "side_B_candidate.log"
    result_b = workdir / "side_B_candidate_result.json"
    report_path = workdir / "compare_report.json"

    if case_ws_a.exists():
        raise SystemExit(f"case_ws already exists -- must be fresh (Section 1.2): {case_ws_a}")
    if case_ws_b.exists():
        raise SystemExit(f"case_ws already exists -- must be fresh (Section 1.2): {case_ws_b}")
    if worktree_a.exists():
        raise SystemExit(f"worktree path already exists: {worktree_a}")

    _log(f"compare: reference {ref_commit!r} vs candidate {candidate_arg!r} (Section 5.2)")
    _log(f"workdir: {workdir}")

    _log(f"creating reference worktree at {worktree_a} @ {ref_commit}")
    subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                    str(worktree_a), ref_commit], check=True)

    candidate_created = False
    if not candidate_is_existing_worktree:
        _log(f"creating candidate worktree at {worktree_b} @ {candidate_arg}")
        subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                        str(worktree_b), candidate_arg], check=True)
        candidate_created = True

    _ensure_config(repo_root, worktree_a, copy_if_missing_only=False)
    _ensure_config(repo_root, worktree_b, copy_if_missing_only=candidate_is_existing_worktree)

    python_exe = _project_venv_python(repo_root)
    this_file = str(Path(__file__).resolve())
    flopy_bindir = os.path.expanduser("~/.local/share/flopy/bin")
    env = _child_env(flopy_bindir)
    _log(f"python: {python_exe}")
    _log(f"PATH (child): {env['PATH']}")
    _log(f"thread pins: OMP_NUM_THREADS={env['OMP_NUM_THREADS']} "
         f"GDAL_NUM_THREADS={env['GDAL_NUM_THREADS']}")

    try:
        _log("launching side A / reference (worktree_A_reference / case_ws_A_reference) ...")
        rc_a, wall_a = _run_side(python_exe, this_file, worktree_a, case_ws_a,
                                  result_a, log_a, env, side="reference")
        _log(f"side A / reference finished: returncode={rc_a} outer_wall={wall_a:.1f}s")

        _log("launching side B / candidate (worktree_B_candidate / case_ws_B_candidate) ...")
        rc_b, wall_b = _run_side(python_exe, this_file, worktree_b, case_ws_b,
                                  result_b, log_b, env, side="candidate")
        _log(f"side B / candidate finished: returncode={rc_b} outer_wall={wall_b:.1f}s")

        a = _side_outcome(rc_a, result_a, log_a)
        a.setdefault("wall_s", wall_a)
        a["outer_wall_s"] = wall_a
        b = _side_outcome(rc_b, result_b, log_b)
        b.setdefault("wall_s", wall_b)
        b["outer_wall_s"] = wall_b

        # Sanity check (Section 5.0's asserted import roots, extended to the
        # orchestrator level): each side actually ran at the commit it was
        # supposed to.
        if a.get("status") == "OK":
            expected_a = _resolve_commit(repo_root, ref_commit)
            got_a = a["env"].get("worktree_commit")
            if got_a != expected_a:
                raise SystemExit(
                    f"reference side ran at commit {got_a!r}, expected {expected_a!r} "
                    f"(resolved from {ref_commit!r})"
                )

        report = compare_reference_vs_candidate(a, b)
        report_path.write_text(json.dumps(report, indent=2))
        _log(f"report written: {report_path}")
        _log("SUMMARY:\n" + json.dumps(report["summary"], indent=2))

        return 0 if report["summary"]["comparison"] == "PASS" else 1
    finally:
        if not args.keep_worktrees:
            _log("removing worktrees this run created (case_ws directories are kept -- "
                 "they are the evidence)")
            subprocess.run(["git", "-C", str(repo_root), "worktree", "remove", "--force",
                            str(worktree_a)], check=False)
            if candidate_created:
                subprocess.run(["git", "-C", str(repo_root), "worktree", "remove", "--force",
                                str(worktree_b)], check=False)


# ===========================================================================
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)

    pw = sub.add_parser("worker", help="internal: run one side (spawned by 'qualify'/'compare')")
    pw.add_argument("--worktree-root", required=True)
    pw.add_argument("--case-ws", required=True)
    pw.add_argument("--out", required=True)
    pw.add_argument("--side", required=True, choices=("reference", "candidate"))

    pq = sub.add_parser("qualify", help="run b685f24-vs-b685f24 qualification (Section 5.1)")
    pq.add_argument("--workdir", required=True)
    pq.add_argument("--ref-commit", default="b685f24")
    pq.add_argument("--keep-worktrees", action="store_true")

    pc = sub.add_parser("compare", help="run reference-vs-candidate comparison (Section 5.2)")
    pc.add_argument("--workdir", required=True)
    pc.add_argument("--ref-commit", default="b685f24")
    pc.add_argument("--candidate", required=True,
                     help="T1 candidate: a commit-ish/branch, OR an existing worktree directory path")
    pc.add_argument("--keep-worktrees", action="store_true")

    args = p.parse_args()
    if args.mode == "worker":
        run_worker(args)
    elif args.mode == "qualify":
        sys.exit(run_qualification(args))
    elif args.mode == "compare":
        sys.exit(run_compare(args))


if __name__ == "__main__":
    main()
