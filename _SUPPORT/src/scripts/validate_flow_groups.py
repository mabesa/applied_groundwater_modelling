#!/usr/bin/env python
"""Instructor driver: execute the FLOW case-study notebook once per student group.

The counterpart to ``validate_transport_groups.py``, and it exists for the same
reason that one does: builder-level checks are not the gate that matters. The
transport side only became trustworthy once the REAL student notebook was executed
end to end, which caught wiring the builder tests could not see. The flow half had
no such gate -- its builder produced 13 goldens, but nobody had ever run
``case_study_flow_group_0.ipynb`` for all 13 groups.

Runs each group in its own subprocess via nbconvert (so a crash in one group does
not abort the sweep), driving the notebook's ``AGM_GROUP_ID`` override, and writes
a machine-readable JSON report alongside the log.

Deliberately thin: the nbconvert invocation, SIGILL classification, output
extraction and timeouts are IMPORTED from ``validate_transport_groups`` rather than
copied. Two copies of that logic drifting apart is precisely the failure this
workstream spent a week unpicking.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_SRC = _HERE.parents[1]
for _p in (str(_SRC), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import validate_transport_groups as vtg  # noqa: E402  -- shared machinery

_TEMPLATE_DIR = vtg._TEMPLATE_DIR
_NOTEBOOK_NAME = "case_study_flow_group_0.ipynb"

WALL_TIMEOUT_S = vtg.WALL_TIMEOUT_S
CELL_TIMEOUT_S = vtg.CELL_TIMEOUT_S
BUDGET_WARN_S = vtg.BUDGET_WARN_S
_SIGILL_CODES = vtg._SIGILL_CODES

#: Groups come from the TRANSPORT config -- it is the single roster (the flow
#: builder reads the doublet from there too, via group_refine_points).
CANONICAL_GROUPS = tuple(range(13))


def _parse_flow_metrics(text: str) -> dict[str, Any]:
    """Pull the few numbers worth reporting out of the executed notebook's output.

    Best-effort by design: a metric that cannot be found is simply absent, never a
    guess and never a failure -- the PASS/FAIL signal is the notebook's exit code.
    """
    out: dict[str, Any] = {}
    patterns = {
        "group": r"Group\s+(\d+):",
        "ncpl": r"ncpl[\"'\s:=]+(\d+)",
        "refine_radius": r"refine[_ ]radius[\"'\s:=m]+([\d.]+)",
        "states": r"(\d+)\s+states",
        "mass_balance_pct": r"Percent Error:\s*([\d.eE+-]+)%",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, re.I)
        if m:
            try:
                out[key] = float(m.group(1)) if "." in m.group(1) else int(m.group(1))
            except ValueError:
                out[key] = m.group(1)
    if re.search(r"\bTraceback\b", text):
        out["traceback_in_output"] = True
    return out


def _run_group(group_id: int, *, keep_cache: bool) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False) as tmp:
        tmp_nb = Path(tmp.name)

    cmd = [
        sys.executable, "-m", "jupyter", "nbconvert",
        "--to", "notebook", "--execute",
        f"--ExecutePreprocessor.timeout={CELL_TIMEOUT_S}",
        "--output", str(tmp_nb),
        _NOTEBOOK_NAME,
    ]
    env = {**os.environ, "AGM_GROUP_ID": str(group_id)}

    t0 = time.monotonic()
    status, error, stderr_tail = "FAIL", None, None
    metrics: dict[str, Any] = {}
    try:
        result = subprocess.run(cmd, cwd=str(_TEMPLATE_DIR), env=env,
                                capture_output=True, timeout=WALL_TIMEOUT_S)
        runtime_s = time.monotonic() - t0
        rc = result.returncode
        if rc == 0:
            status = "OK"
            try:
                metrics = _parse_flow_metrics(vtg._extract_text_outputs(tmp_nb))
            except Exception as exc:                    # noqa: BLE001
                error = f"output parse failed: {type(exc).__name__}: {exc}"
        elif rc in _SIGILL_CODES:
            status = "SIGILL"
        else:
            status = "FAIL"
        if rc != 0:
            stderr_tail = (result.stderr or b"").decode("utf-8", "replace").strip()[-1500:]
    except subprocess.TimeoutExpired:
        runtime_s = time.monotonic() - t0
        status = "TIMEOUT"
        error = f"exceeded the {WALL_TIMEOUT_S}s wall timeout"
    finally:
        tmp_nb.unlink(missing_ok=True)

    return {"group": group_id, "status": status, "runtime_s": round(runtime_s, 1),
            "metrics": metrics, "error": error, "stderr_tail": stderr_tail,
            "over_budget": bool(status == "OK" and runtime_s > BUDGET_WARN_S)}


def _print_summary(results: list[dict]) -> None:
    print("=" * 96)
    print("FLOW GROUP VALIDATION SUMMARY")
    print("=" * 96)
    print(f"{'id':<4} | {'status':<8} | {'runtime_s':>9} | {'ncpl':>6} | {'radius':>7} | notes")
    print("-" * 96)
    for r in results:
        m = r["metrics"]
        note = r.get("error") or ("SLOW - over budget" if r["over_budget"] else "")
        print(f"{r['group']:<4} | {r['status']:<8} | {r['runtime_s']:>9.0f} | "
              f"{str(m.get('ncpl', '')):>6} | {str(m.get('refine_radius', '')):>7} | {note[:38]}")
    print("-" * 96)

    # 🔴 Print the captured stderr for every failure. `error` is None for an ordinary
    # non-zero exit (the detail lands in `stderr_tail`), so a summary that shows only
    # `error` prints a BLANK notes column -- which is exactly what happened on
    # 2026-09-04: 13 identical FAILs whose real cause ("The program triangle does not
    # exist or is not executable") sat unread in the JSON report and took three Hub
    # sessions to find. The transport validator already does this.
    for r in results:
        if r["status"] == "OK" or not r.get("stderr_tail"):
            continue
        print(f"\n--- group {r['group']} ({r['status']}) ---")
        if r.get("error"):
            print(f"  error: {r['error']}")
        print("  stderr tail:")
        for ln in r["stderr_tail"].splitlines()[-15:]:
            print(f"    {ln}")
    if any(r["status"] != "OK" for r in results):
        print()

    tally = {}
    for r in results:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    print("Tally: " + " / ".join(f"{n} {s}" for s, n in sorted(tally.items())))
    slow = [r["group"] for r in results if r["over_budget"]]
    if slow:
        print(f"⚠ over the {BUDGET_WARN_S}s budget: groups {slow}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--groups", default=",".join(str(g) for g in CANONICAL_GROUPS),
                    help="comma list, e.g. --groups 0,3,5 (default: all 13)")
    ap.add_argument("--keep-cache", action="store_true",
                    help="do not pre-clear the group workspace")
    ap.add_argument("--out", default="flow_group_validation_report.json")
    args = ap.parse_args(argv)

    groups = [int(x) for x in args.groups.split(",") if x.strip() != ""]
    bad = [g for g in groups if g not in CANONICAL_GROUPS]
    if bad:
        print(f"error: groups outside the roster {CANONICAL_GROUPS}: {bad}", file=sys.stderr)
        return 2

    if vtg.preflight():
        return 2

    results = []
    for g in groups:
        print(f"--- group {g} ---", flush=True)
        r = _run_group(g, keep_cache=args.keep_cache)
        print(f"    {r['status']} in {r['runtime_s']:.0f}s", flush=True)
        results.append(r)

    _print_summary(results)
    Path(args.out).write_text(json.dumps(
        {"notebook": _NOTEBOOK_NAME, "results": results}, indent=2) + "\n")
    print(f"\nJSON report written to: {Path(args.out).resolve()}")
    return 0 if all(r["status"] == "OK" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
