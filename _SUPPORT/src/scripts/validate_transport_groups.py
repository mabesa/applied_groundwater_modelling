"""Instructor validation driver for all 9 student transport-group scenarios.

Run from the repo root (or anywhere) to validate every group scenario on
JupyterHub (Linux), where the cs=10 grid refinement that occasionally SIGILLs
on macOS-arm64 (exit 132 / signal -4) should run cleanly.

Each group is executed in its own subprocess so that a SIGILL or crash does not
abort the sweep.  A machine-readable JSON report is written alongside the run
log so results survive the terminal.

Usage
-----
    python _SUPPORT/src/scripts/validate_transport_groups.py
    python _SUPPORT/src/scripts/validate_transport_groups.py --groups 0,3,5
    python _SUPPORT/src/scripts/validate_transport_groups.py --groups 0 --keep-cache
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths resolved relative to THIS script's location so it can be run from
# anywhere in the repo tree.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[2]          # _SUPPORT/src/scripts/ → repo root
_TEMPLATE_DIR = _REPO_ROOT / "PROJECT" / "workspace" / "template"
_CONFIG_FILE = _TEMPLATE_DIR / "case_config_transport.yaml"
_NOTEBOOK_NAME = "case_study_transport_group_0.ipynb"

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
WALL_TIMEOUT_S = 1800    # 30 min hard wall per group subprocess
CELL_TIMEOUT_S = 1800    # per-cell nbconvert timeout (generous)
BUDGET_WARN_S  = 600     # flag any OK group slower than this

# ---------------------------------------------------------------------------
# SIGILL exit codes
# ---------------------------------------------------------------------------
_SIGILL_CODES = {132, -4}   # 128+4 on Linux; Python reports -4 for signal SIGILL


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load and return the parsed case_config_transport.yaml."""
    import yaml  # lazy: available in the project venv
    with open(_CONFIG_FILE) as fh:
        return yaml.safe_load(fh)


def _discover_groups(cfg: dict) -> list[dict]:
    """Return the list of scenario dicts from the config."""
    return cfg["transport_scenarios"]["options"]


def _workspace_prefix(cfg: dict) -> str:
    """Absolute path prefix for per-group workspaces (without trailing group id)."""
    return str(os.path.expanduser(cfg["output"]["workspace"]))


# ---------------------------------------------------------------------------
# Regex-based metric extraction from executed notebook output
# ---------------------------------------------------------------------------

def _extract_text_outputs(nb_path: Path) -> str:
    """Return all text/stream output lines from the executed notebook as one string."""
    import json as _json
    nb = _json.loads(nb_path.read_text())
    parts: list[str] = []
    for cell in nb.get("cells", []):
        for out in cell.get("outputs", []):
            otype = out.get("output_type", "")
            if otype in ("stream", "execute_result", "display_data"):
                text = out.get("text", out.get("data", {}).get("text/plain", ""))
                if isinstance(text, list):
                    parts.extend(text)
                elif isinstance(text, str):
                    parts.append(text)
    return "".join(parts)


def _parse_metrics(output_text: str) -> dict[str, Any]:
    """Parse build metrics and verdict from notebook stdout using robust regexes."""
    m: dict[str, Any] = {
        "ncpl": None,
        "refine_radius": None,
        "PeL_min": None,
        "PeL_max": None,
        "Cr": None,
        "nstp": None,
        "cr_capped": None,
        "receptor_cell": None,
        "spill_cells": None,
        "verdict": None,
        "peak_mg_L": None,
        "threshold_mg_L": None,
        "t_first_exceed_d": None,
    }

    # "  cells (ncpl)    = 5230   refine radius = 70 m"
    mo = re.search(r"cells\s*\(ncpl\)\s*=\s*(\d+)", output_text)
    if mo:
        m["ncpl"] = int(mo.group(1))

    mo = re.search(r"refine radius\s*=\s*([\d.]+)\s*m", output_text)
    if mo:
        m["refine_radius"] = float(mo.group(1))

    # "  corridor Pe_L   = 0.83 .. 1.94   (<= 2: ..."
    mo = re.search(r"corridor Pe_L\s*=\s*([\d.]+)\s*\.\.\s*([\d.]+)", output_text)
    if mo:
        m["PeL_min"] = float(mo.group(1))
        m["PeL_max"] = float(mo.group(2))

    # "  Courant Cr peak = 0.90   (nstp = 1200, CAPPED)"  or  "(nstp = 1200)"
    mo = re.search(r"Courant Cr peak\s*=\s*([\d.]+)\s*\(\s*nstp\s*=\s*(\d+)(,\s*CAPPED)?", output_text)
    if mo:
        m["Cr"] = float(mo.group(1))
        m["nstp"] = int(mo.group(2))
        m["cr_capped"] = mo.group(3) is not None

    # "  spill cell(s)   = [123]   monitoring (extraction) cell = 456"
    mo = re.search(r"spill cell\(s\)\s*=\s*(\[[^\]]+\]|\d+)", output_text)
    if mo:
        m["spill_cells"] = mo.group(1).strip()

    mo = re.search(r"monitoring \(extraction\) cell\s*=\s*(\d+)", output_text)
    if mo:
        m["receptor_cell"] = int(mo.group(1))

    # "  peak concentration at well = 2.345 mg/L   (threshold 5 mg/L)"
    mo = re.search(r"peak concentration at well\s*=\s*([\d.eE+\-]+)\s*mg/L", output_text)
    if mo:
        m["peak_mg_L"] = float(mo.group(1))

    mo = re.search(r"\(threshold\s*([\d.eE+\-]+)\s*mg/L\)", output_text)
    if mo:
        m["threshold_mg_L"] = float(mo.group(1))

    # "  -> REACHES the well ABOVE the threshold (first exceedance at t = 23 d)"
    # "  -> REACHES the well but stays BELOW the threshold (marginal)"
    # "  -> DOES NOT REACH the well (negligible concentration)"
    mo = re.search(r"->\s*(REACHES.*?|DOES NOT REACH.*?)(?:\n|$)", output_text)
    if mo:
        m["verdict"] = mo.group(1).strip()

    # first exceedance time from verdict string
    mo = re.search(r"first exceedance at t\s*=\s*([\d.]+)\s*d", output_text)
    if mo:
        m["t_first_exceed_d"] = float(mo.group(1))

    return m


def _short_verdict(verdict: str | None) -> str:
    if verdict is None:
        return "(no verdict parsed)"
    if "DOES NOT REACH" in verdict:
        return "DOES NOT REACH"
    if "ABOVE" in verdict:
        return "REACHES ABOVE"
    if "marginal" in verdict.lower():
        return "REACHES MARGINAL"
    if "BELOW" in verdict:
        return "REACHES BELOW"
    return verdict[:40]


# ---------------------------------------------------------------------------
# Per-group runner
# ---------------------------------------------------------------------------

def _run_group(group_id: int, workspace_prefix: str, keep_cache: bool) -> dict:
    """
    Build and run one group scenario in a subprocess.

    Returns a result dict with keys:
        group_id, status, runtime_s, metrics, stderr_tail, error
    """
    case_ws = Path(os.path.expanduser(f"{workspace_prefix}{group_id}"))

    # --- Force fresh build unless --keep-cache ---
    if not keep_cache and case_ws.exists():
        print(f"  [group {group_id}] Deleting cache at {case_ws} ...")
        shutil.rmtree(case_ws, ignore_errors=True)

    # --- Build nbconvert command ---
    # Use a temp output path so we can parse the executed notebook.
    with tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False) as tmp:
        tmp_nb = Path(tmp.name)

    cmd = [
        sys.executable, "-m", "jupyter", "nbconvert",
        "--to", "notebook",
        "--execute",
        f"--ExecutePreprocessor.timeout={CELL_TIMEOUT_S}",
        "--output", str(tmp_nb),
        _NOTEBOOK_NAME,
    ]

    env = {**os.environ, "AGM_GROUP_ID": str(group_id)}

    t0 = time.monotonic()
    status = "FAIL"
    metrics: dict[str, Any] = {}
    stderr_tail: str | None = None
    error: str | None = None

    try:
        result = subprocess.run(
            cmd,
            cwd=str(_TEMPLATE_DIR),
            env=env,
            capture_output=True,
            timeout=WALL_TIMEOUT_S,
        )
        runtime_s = time.monotonic() - t0
        rc = result.returncode

        if rc == 0:
            status = "OK"
            # Parse the executed notebook
            try:
                output_text = _extract_text_outputs(tmp_nb)
                metrics = _parse_metrics(output_text)
            except Exception as exc:
                metrics = {}
                error = f"Parse error: {exc}"
        elif rc in _SIGILL_CODES or (rc < 0 and signal.Signals(-rc) == signal.SIGILL):
            status = "SIGILL"
            stderr_tail = result.stderr.decode(errors="replace")[-2000:]
        else:
            status = "FAIL"
            stderr_lines = result.stderr.decode(errors="replace").splitlines()
            stderr_tail = "\n".join(stderr_lines[-25:])
            error = f"returncode={rc}"

    except subprocess.TimeoutExpired:
        runtime_s = time.monotonic() - t0
        status = "TIMEOUT"
        error = f"Exceeded wall timeout of {WALL_TIMEOUT_S} s"
    except Exception as exc:
        runtime_s = time.monotonic() - t0
        status = "FAIL"
        error = str(exc)
    finally:
        # Clean up temp notebook
        try:
            tmp_nb.unlink(missing_ok=True)
        except Exception:
            pass

    return {
        "group_id": group_id,
        "status": status,
        "runtime_s": round(runtime_s, 1),
        "metrics": metrics,
        "stderr_tail": stderr_tail,
        "error": error,
    }


# ---------------------------------------------------------------------------
# SIGILL classifier self-test helper (not used during normal runs)
# ---------------------------------------------------------------------------

_SIGILL_HELPER_CODE = """\
import os, signal
os.kill(os.getpid(), signal.SIGILL)
"""


def _test_sigill_classifier() -> bool:
    """Run a tiny subprocess that SIGILLs itself; verify we classify it correctly."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tf:
        tf.write(_SIGILL_HELPER_CODE)
        tf_path = Path(tf.name)
    try:
        r = subprocess.run([sys.executable, str(tf_path)], capture_output=True, timeout=10)
        rc = r.returncode
        classified = rc in _SIGILL_CODES
        # On macOS Python may report returncode as -signal.SIGILL.value == -4
        if not classified and rc < 0:
            try:
                classified = signal.Signals(-rc) == signal.SIGILL
            except ValueError:
                pass
        return classified
    finally:
        tf_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Summary table + tally
# ---------------------------------------------------------------------------

def _print_summary(results: list[dict], groups_meta: dict[int, dict]) -> None:
    col_w = [4, 12, 12, 8, 10, 6, 9, 6, 45]
    headers = ["id", "contaminant", "concession", "status", "runtime_s", "ncpl",
               "refine_r", "Cr", "verdict-short"]

    def _fmt_row(vals):
        return " | ".join(str(v)[:col_w[i]].ljust(col_w[i]) for i, v in enumerate(vals))

    sep = "-+-".join("-" * w for w in col_w)
    print("\n" + "=" * (sum(col_w) + 3 * (len(col_w) - 1)))
    print("TRANSPORT GROUP VALIDATION SUMMARY")
    print("=" * (sum(col_w) + 3 * (len(col_w) - 1)))
    print(_fmt_row(headers))
    print(sep)

    budget_warnings: list[int] = []

    for r in results:
        gid = r["group_id"]
        meta = groups_meta.get(gid, {})
        contaminant = (meta.get("contaminant") or "")[:12]
        concession = (meta.get("concession") or "")[:12]
        status = r["status"]
        runtime = f"{r['runtime_s']:.0f}"
        mx = r.get("metrics", {})
        ncpl = str(mx.get("ncpl") or "")
        refine_r = str(mx.get("refine_radius") or "")
        cr = f"{mx['Cr']:.2f}" if mx.get("Cr") is not None else ""
        vshort = _short_verdict(mx.get("verdict")) if status == "OK" else f"({status})"

        row = [gid, contaminant, concession, status, runtime, ncpl, refine_r, cr, vshort]
        line = _fmt_row(row)

        if status == "OK" and r["runtime_s"] > BUDGET_WARN_S:
            line += "  *** BUDGET WARNING"
            budget_warnings.append(gid)
        print(line)

    print(sep)

    n_ok = sum(1 for r in results if r["status"] == "OK")
    n_sigill = sum(1 for r in results if r["status"] == "SIGILL")
    n_timeout = sum(1 for r in results if r["status"] == "TIMEOUT")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")

    print(f"\nTally: {n_ok} OK / {n_sigill} SIGILL / {n_timeout} TIMEOUT / {n_fail} FAIL")
    if budget_warnings:
        print(f"Budget warnings (> {BUDGET_WARN_S} s): groups {budget_warnings}")

    # Print errors for non-OK groups
    for r in results:
        if r["status"] not in ("OK",):
            gid = r["group_id"]
            print(f"\n--- Group {gid} ({r['status']}) ---")
            if r.get("error"):
                print(f"  error: {r['error']}")
            if r.get("stderr_tail"):
                print("  stderr tail:")
                for ln in r["stderr_tail"].splitlines()[-15:]:
                    print(f"    {ln}")


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def _write_json_report(results: list[dict], groups_meta: dict[int, dict],
                       outpath: Path) -> None:
    report = []
    for r in results:
        gid = r["group_id"]
        meta = groups_meta.get(gid, {})
        report.append({
            "group_id": gid,
            "title": meta.get("title"),
            "contaminant": meta.get("contaminant"),
            "concession": meta.get("concession"),
            "status": r["status"],
            "runtime_s": r["runtime_s"],
            "metrics": r.get("metrics", {}),
            "error": r.get("error"),
            "stderr_tail": r.get("stderr_tail"),
        })
    outpath.write_text(json.dumps(report, indent=2))
    print(f"\nJSON report written to: {outpath}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate all (or a subset of) student transport-group scenarios.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--groups",
        default=None,
        help="Comma-separated group ids to run, e.g. --groups 0,3,5 (default: all)",
    )
    parser.add_argument(
        "--keep-cache",
        action="store_true",
        default=False,
        help="Skip pre-deletion of group workspace (load cache if present).",
    )
    parser.add_argument(
        "--test-sigill",
        action="store_true",
        default=False,
        help="Run the SIGILL classifier self-test and exit.",
    )
    args = parser.parse_args()

    # SIGILL self-test mode
    if args.test_sigill:
        print("Running SIGILL classifier self-test...")
        ok = _test_sigill_classifier()
        if ok:
            print("PASS: subprocess that sent SIGILL to itself was correctly classified.")
        else:
            print("FAIL: SIGILL not detected in subprocess exit code.")
            sys.exit(1)
        return

    # Load config
    try:
        import yaml  # noqa: F401 — just check it's importable
    except ImportError:
        print("ERROR: PyYAML not available. Run inside the project venv (uv run python ...).")
        sys.exit(1)

    if not _CONFIG_FILE.exists():
        print(f"ERROR: config not found at {_CONFIG_FILE}")
        sys.exit(1)

    cfg = _load_config()
    scenario_list = _discover_groups(cfg)
    workspace_prefix = _workspace_prefix(cfg)

    all_ids = [s["id"] for s in scenario_list]
    groups_meta: dict[int, dict] = {s["id"]: s for s in scenario_list}

    # Filter by --groups
    if args.groups:
        try:
            requested = [int(x.strip()) for x in args.groups.split(",")]
        except ValueError:
            print(f"ERROR: invalid --groups value '{args.groups}'. Use comma-separated integers.")
            sys.exit(1)
        unknown = [i for i in requested if i not in all_ids]
        if unknown:
            print(f"ERROR: group ids {unknown} not in config (available: {all_ids})")
            sys.exit(1)
        run_ids = requested
    else:
        run_ids = all_ids

    keep_cache = args.keep_cache

    print(f"Transport group validation driver")
    print(f"  Template dir : {_TEMPLATE_DIR}")
    print(f"  Config       : {_CONFIG_FILE}")
    print(f"  Groups to run: {run_ids}")
    print(f"  Keep cache   : {keep_cache}")
    print(f"  Wall timeout : {WALL_TIMEOUT_S} s / group")
    print()

    results: list[dict] = []

    for gid in run_ids:
        meta = groups_meta[gid]
        print(f"[group {gid}] {meta.get('title','?')} ({meta.get('contaminant','?')}) ...")
        r = _run_group(gid, workspace_prefix, keep_cache)
        results.append(r)

        # One-line progress
        if r["status"] == "OK":
            mx = r["metrics"]
            cr_str = f"Cr={mx['Cr']:.2f}" if mx.get("Cr") is not None else ""
            verdict_short = _short_verdict(mx.get("verdict"))
            print(
                f"[group {gid}] OK  {r['runtime_s']:.0f}s  "
                f"ncpl={mx.get('ncpl','?')}  {cr_str}  -> {verdict_short}"
            )
        else:
            print(f"[group {gid}] {r['status']}  {r['runtime_s']:.0f}s  {r.get('error','')}")

    # Summary table
    _print_summary(results, groups_meta)

    # JSON report
    report_path = Path.cwd() / "transport_group_validation_report.json"
    _write_json_report(results, groups_meta, report_path)


if __name__ == "__main__":
    main()
