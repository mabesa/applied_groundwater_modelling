#!/usr/bin/env python3
"""
T0.0 canonical-default gate harness.

Implements DESIGN_DOCS/T0_0_canonical_contract.md (v2):
  - Section 4  -- the frozen field normalisation.
  - Section 5.0 -- the harness (two worktrees, two fresh OS processes,
    asserted import roots, controlled cwd/config, hashed executables,
    pinned threading, hashed flow + GIS inputs).
  - Section 5.2 -- the comparison (exact string equality, field by field,
    every differing field reported with both values).

This file is READ-ONLY with respect to the T1 modules it exercises
(transport_srcpulse_demo.py, model_io_utils.py, etc.) -- it only imports and
calls them, from inside worktrees the harness itself creates.

Two invocation modes:

  qualify  (orchestrator -- what a human runs)
      uv run python _SUPPORT/src/scripts/t0_gate_harness.py qualify \\
          --workdir <scratch-dir> [--ref-commit b685f24] [--keep-worktrees]

      Creates two git worktrees at --ref-commit (default b685f24, the frozen
      reference), runs one side per worktree SEQUENTIALLY as a fresh child
      process, then compares the two canonical payloads per contract Section
      5.2. In qualification mode both worktrees are the SAME commit, so any
      reported difference is pure run-to-run nondeterminism (contract
      Section 5.1) -- not a code change.

  worker  (internal -- one per side, spawned by "qualify"; not for direct use)
      <python> _SUPPORT/src/scripts/t0_gate_harness.py worker \\
          --worktree-root <path> --case-ws <path> --out <result.json>

      Runs entirely inside ONE worktree's import root: builds the canonical
      payload by calling build_srcpulse_demo() at its semantic defaults plus
      the two gate-only controls (force=True, a fresh case_ws), normalises it
      per Section 4, and writes a JSON result record. A fatal SIGILL in the
      corridor-refinement retry (macOS arm64 / mf6 6.7.0, model_io_utils.py
      around line 2846) kills this process outright before it can write
      anything -- that is exactly why "qualify" runs each side as its own OS
      process and detects a signal death from the child's return code.
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
# Section 2 -- the frozen payload schema (used only to ASSERT the reflected
# field set matches; the enumeration itself is by reflection, per Section 2).
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

# Fields NOT in the payload (Section 4.4) -- recorded alongside for
# provenance only, never compared: wall-clock timings, workspace paths,
# hostnames, environment fingerprint.


class GateAbort(RuntimeError):
    """mass_balance carried the 'error' sentinel or a non-conforming keyset
    (contract Section 2.2). A broken run, not a payload difference -- do not
    compare, do not normalise, do not record a canonical result."""


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


def normalize(value):
    """Section 4: recursive normaliser, one formatter applied everywhere.

    Every leaf becomes a canonical string (FLOAT_FORMAT for floats, plain
    decimal for ints, "true"/"false" for bools, NFC text for strings).
    Mapping keys are sorted lexicographically at every depth (Section 4.2);
    array/list/tuple/ndarray element order is always preserved (Section 4.2
    -- times/breakthrough are time series and must never be sorted).
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
        return {str(k): normalize(value[k]) for k in sorted(value.keys(), key=str)}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [normalize(v) for v in list(value)]
    raise TypeError(f"normalize(): unhandled type {type(value)!r} for value {value!r}")


# ---------------------------------------------------------------------------
# Section 2 -- payload construction BY REFLECTION over SrcPulseDemo
# ---------------------------------------------------------------------------
def build_payload(result) -> dict:
    """Reflect over every non-underscore field of the SrcPulseDemo dataclass
    instance (Section 2), assert the reflected field set is EXACTLY the
    frozen 29 (Section 2.5: a new/removed/renamed field is a failure edge),
    then assert the three nested keysets (Section 2.2b): mass_balance (9),
    meta (17), locked (9).

    Raises GateAbort per Section 2.2 if mass_balance carries the "error"
    sentinel key or any non-conforming keyset -- that is a broken run, not a
    payload difference, and the gate must not compare/normalise/record it.
    """
    names = tuple(f.name for f in dataclasses.fields(result) if not f.name.startswith("_"))
    if set(names) != set(TOP_LEVEL_FIELDS):
        missing = sorted(set(TOP_LEVEL_FIELDS) - set(names))
        extra = sorted(set(names) - set(TOP_LEVEL_FIELDS))
        raise GateAbort(
            f"top-level payload field set changed (Section 2.5): missing={missing} extra={extra}"
        )

    payload = {name: getattr(result, name) for name in names}

    mb = payload["mass_balance"]
    if "error" in mb or set(mb.keys()) != set(MASS_BALANCE_KEYS):
        raise GateAbort(
            f"mass_balance abort (Section 2.2): keys={sorted(mb.keys())}"
            + (f" error={mb.get('error')!r}" if "error" in mb else "")
        )

    meta = payload["meta"]
    if set(meta.keys()) != set(META_KEYS):
        raise GateAbort(f"meta keyset changed (Section 2.2b): keys={sorted(meta.keys())}")

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

        payload = build_payload(result)  # raises GateAbort per Section 2.2
        normalized = normalize(payload)  # Section 4

        record = {
            "status": "OK",
            "wall_s": wall_s,
            "env": env_fp,
            "normalized_payload": normalized,
            "raw_top_fields": sorted(payload.keys()),
        }

    except GateAbort as e:
        record = {"status": "ABORT", "error": str(e)}
    except Exception as e:  # noqa: BLE001 -- deliberately broad: report, don't crash silently
        record = {"status": "ERROR", "error": str(e), "traceback": traceback.format_exc()}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2))
    sys.exit(0 if record["status"] == "OK" else 1)


# ===========================================================================
# ORCHESTRATOR -- "qualify": two worktrees, two sequential fresh processes
# ===========================================================================
def _child_env(flopy_bindir: str) -> dict:
    """Section 5.0: pinned threading BEFORE Python starts; identical process
    environment on both sides (the only permitted difference between sides
    is the worktree path / case_ws / --out passed on argv, not anything in
    this env dict)."""
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


def _run_side(python_exe, this_file, worktree_root, case_ws, out_path, log_path, env):
    cmd = [
        python_exe, this_file, "worker",
        "--worktree-root", str(worktree_root),
        "--case-ws", str(case_ws),
        "--out", str(out_path),
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
    """Section 5.2.8: on mismatch, report EVERY differing field with both
    values -- never stop at the first."""
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


def compare_sides(a: dict, b: dict) -> dict:
    summary = {
        "side_A": {"status": a.get("status"), "wall_s": a.get("wall_s")},
        "side_B": {"status": b.get("status"), "wall_s": b.get("wall_s")},
    }

    if a.get("status") != "OK" or b.get("status") != "OK":
        summary["qualification"] = "FAIL"
        summary["reason"] = "one or both sides did not produce a valid canonical payload"
        return {"summary": summary, "side_A": a, "side_B": b}

    # Section 5.2 step 1: assert Section 1.1 (flow + GIS) and Section 1.3
    # (one MF6 binary, one triangle binary, one data folder).
    env_a, env_b = a["env"], b["env"]
    env_mismatches = {}
    for key in (
        "flow_fingerprint", "model_boundary_sha256", "rivers_sha256",
        "mf6_sha256", "triangle_sha256", "data_folder",
    ):
        if env_a.get(key) != env_b.get(key):
            env_mismatches[key] = {"A": env_a.get(key), "B": env_b.get(key)}

    # Section 5.2 step 7: exact string equality, field by field, EVERY field.
    payload_mismatches = _diff_normalized(a["normalized_payload"], b["normalized_payload"])

    passed = not env_mismatches and not payload_mismatches
    summary["qualification"] = "PASS" if passed else "FAIL"
    summary["env_mismatches"] = env_mismatches
    summary["payload_mismatch_count"] = len(payload_mismatches)
    summary["payload_mismatches"] = payload_mismatches
    return {"summary": summary, "side_A": a, "side_B": b}


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

    # Section 5.0: this machine has a gitignored config.py a fresh worktree
    # lacks -- copy it in so both sides resolve the SAME data folder, rather
    # than falling back to config_template.py.
    cfg = repo_root / "config.py"
    if not cfg.exists():
        raise SystemExit(
            "repo config.py not found -- cannot propagate the data-source config "
            "to the worktrees (both sides would silently diverge onto config_template.py)"
        )
    shutil.copy2(cfg, worktree_a / "config.py")
    shutil.copy2(cfg, worktree_b / "config.py")
    _log(f"copied {cfg} into both worktrees")

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
    this_file = str(Path(__file__).resolve())
    flopy_bindir = os.path.expanduser("~/.local/share/flopy/bin")
    env = _child_env(flopy_bindir)
    _log(f"python: {python_exe}")
    _log(f"PATH (child): {env['PATH']}")
    _log(f"thread pins: OMP_NUM_THREADS={env['OMP_NUM_THREADS']} "
         f"GDAL_NUM_THREADS={env['GDAL_NUM_THREADS']}")

    _log("launching side A (worktree_A / case_ws_A) -- cold corridor refine + "
         "pilot + production coupled GWF+GWT solve ...")
    rc_a, wall_a = _run_side(python_exe, this_file, worktree_a, case_ws_a,
                             result_a, log_a, env)
    _log(f"side A finished: returncode={rc_a} outer_wall={wall_a:.1f}s")

    _log("launching side B (worktree_B / case_ws_B) -- cold corridor refine + "
         "pilot + production coupled GWF+GWT solve ...")
    rc_b, wall_b = _run_side(python_exe, this_file, worktree_b, case_ws_b,
                             result_b, log_b, env)
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
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)

    pw = sub.add_parser("worker", help="internal: run one side (spawned by 'qualify')")
    pw.add_argument("--worktree-root", required=True)
    pw.add_argument("--case-ws", required=True)
    pw.add_argument("--out", required=True)

    pq = sub.add_parser("qualify", help="run b685f24-vs-b685f24 qualification (Section 5.1)")
    pq.add_argument("--workdir", required=True)
    pq.add_argument("--ref-commit", default="b685f24")
    pq.add_argument("--keep-worktrees", action="store_true")

    args = p.parse_args()
    if args.mode == "worker":
        run_worker(args)
    elif args.mode == "qualify":
        sys.exit(run_qualification(args))


if __name__ == "__main__":
    main()
