"""Hub measurement runbook — the three things that need Hub access.

Instrumentation only: this script changes no model behaviour, is on no C1
enumerated surface, and is not part of any milestone's deliverable. It exists
so one Hub session settles three open questions at once.

    python _SUPPORT/src/scripts/hub_measurement.py --workdir ~/hub_meas

⚠️ ON THE HUB, use plain `python` -- `uv` is NOT installed there. The Hub's
JupyterHub environment already has the dependencies, and this script uses
`sys.executable` throughout, so whichever interpreter launches it is the one
the subprocesses inherit. Locally on a dev machine, `uv run python ...`.

WHAT IT MEASURES

1. THE HUB MULTIPLIER H.  Every runtime in the design docs is a fast Mac, and
   no Hub runtime is recorded anywhere in the repo. T0.0 calls timing one
   known case "the cheapest outstanding action in the project", because the
   frozen budget turns on it:

       HUB_FINE_TARGET_S  = 600   # intended operating point
       HUB_FINE_CEILING_S = 900   # hard pass/fail (half the 1800 s wall)

   The corrected-Courant 2 m corridor takes ~316 s on a fast Mac. At an
   illustrative H = 3 that is ~948 s -- already over the ceiling, at which
   point T2 FAILS and takes a declared failure edge (back to T1 for a cheaper
   GridSpec, or to T0 to revise the threshold). It may not pass by
   reclassifying the mandatory fine run as optional.

   Baseline, from the macOS qualification of 2026-08-20:
       min 14.35 s | mean 14.61 s | max 15.00 s   per side

2. THE GATE'S HUB-SIDE QUALIFICATION.  T0.0 Sec 5.1 passed on macOS-arm64 and
   says so explicitly: "it makes NO claim about the Hub, and a Hub-side T1
   gate would need its own qualification." The same `qualify` run supplies
   both this and (1), which is why they are one command.

3. S10's CAPTURE-FINGERPRINT REPEATABILITY ENVELOPE.  `capture_halfwidth_m`
   has a ~24% Mac<->Hub spread against TOL_WIDTH_REL = 5%. S10 therefore
   records it as DESCRIPTIVE-ONLY and refuses every comparison until a
   measured envelope exists. A 24% spread indicates general
   implementation-sensitivity, so platform equality alone proves nothing --
   the envelope must come from REPLICATED RUNS IN FRESH PROCESSES on one
   machine, and must land materially below 5% before the metric can carry
   grid evidence.

OUTPUT: one JSON block on stdout. Paste it back verbatim.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MAC_BASELINE_S = {"min": 14.35, "mean": 14.61, "max": 15.00, "date": "2026-08-20",
                  "platform": "macOS-arm64"}
HUB_FINE_TARGET_S = 600.0
HUB_FINE_CEILING_S = 900.0
FINE_RUN_MAC_S = 316.0          # the corrected-Courant 2 m corridor, fast Mac
TOL_WIDTH_REL = 0.05


def _pin_threads(env: dict) -> dict:
    """T0.0 Sec 5: threads pinned BEFORE Python starts, or reduction order
    becomes a machine property."""
    for var in ("OMP_NUM_THREADS", "GDAL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[var] = "1"
    return env


def _clear_stale_worktrees(out: Path) -> None:
    """Remove a previous run's worktrees so a re-run is not blocked.

    The harness aborts with "worktree path already exists" if an earlier
    attempt died partway -- which is exactly what happens when preflight
    catches a problem AFTER the first worktree was created. `rm -rf` alone is
    not enough: git still has the worktree REGISTERED in the repo metadata, so
    `git worktree prune` has to follow, or the next run fails the same way
    against a directory that no longer exists.
    """
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
        print(f"  cleared stale workdir {out}", file=sys.stderr, flush=True)
    subprocess.run(["git", "worktree", "prune"], cwd=str(REPO),
                   capture_output=True, text=True)


def run_qualification(workdir: Path) -> dict:
    """(1) + (2): the gate against itself, cold, repeated. Per-side wall times
    give H; the pass/fail gives the Hub-side qualification."""
    out = workdir / "qualify"
    _clear_stale_worktrees(out)
    cmd = [sys.executable, str(REPO / "_SUPPORT/src/scripts/t0_gate_harness.py"),
           "qualify", "--workdir", str(out)]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                          env=_pin_threads(dict(os.environ)))
    wall = time.time() - t0
    report = out / "qualification_report.json"
    data = json.loads(report.read_text()) if report.exists() else {}
    return {"returncode": proc.returncode, "total_wall_s": round(wall, 1),
            "report": data, "stderr_tail": proc.stderr[-800:] if proc.returncode else ""}


def run_fingerprint_replication(workdir: Path, n: int) -> dict:
    """(3): `capture_halfwidth_at` in n FRESH PROCESSES. Fresh matters -- a
    warm in-process cache would measure memoisation, not repeatability."""
    snippet = (
        "import sys, json; sys.path.insert(0, r'{src}');"
        "import transport_prt_capture as prt;"
        "r = prt.capture_halfwidth_at(0.0, case_ws=r'{ws}');"
        "print('RESULT ' + json.dumps({{'hw': r.get('halfwidth_m'),"
        "'asym': r.get('asymptotic_halfwidth_m')}}))"
    )
    vals, errs = [], []
    for i in range(n):
        ws = workdir / f"fp_{i}"
        code = snippet.format(src=str(REPO / "_SUPPORT/src"), ws=str(ws))
        t0 = time.time()
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(REPO),
                              capture_output=True, text=True,
                              env=_pin_threads(dict(os.environ)))
        dt = time.time() - t0
        line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")), None)
        if line:
            d = json.loads(line[len("RESULT "):])
            vals.append({"run": i, "halfwidth_m": d["hw"], "wall_s": round(dt, 1)})
            print(f"  fingerprint run {i}: {d['hw']} m  ({dt:.1f}s)", file=sys.stderr, flush=True)
        else:
            errs.append({"run": i, "stderr_tail": proc.stderr[-400:]})
            print(f"  fingerprint run {i}: FAILED", file=sys.stderr, flush=True)

    hw = [v["halfwidth_m"] for v in vals if v["halfwidth_m"] is not None]
    env = {}
    if len(hw) >= 2:
        mean = statistics.fmean(hw)
        spread_rel = (max(hw) - min(hw)) / mean if mean else float("nan")
        env = {
            "n": len(hw), "min": min(hw), "max": max(hw), "mean": round(mean, 4),
            "stdev": round(statistics.pstdev(hw), 4),
            "spread_rel": round(spread_rel, 5),
            "tol_width_rel": TOL_WIDTH_REL,
            "below_tolerance": bool(spread_rel < TOL_WIDTH_REL),
            "verdict": ("ENVELOPE OK -- comparisons may be enabled"
                        if spread_rel < TOL_WIDTH_REL else
                        "ENVELOPE TOO WIDE -- fingerprint stays descriptive-only"),
        }
    return {"runs": vals, "failures": errs, "envelope": env}


def preflight() -> list:
    """Cheap checks that would otherwise fail MINUTES in.

    The first Hub run (2026-08-26) lost its qualification stage to a missing
    `config.py` -- gitignored, so a fresh Hub checkout never has one, while the
    gate harness requires it to propagate the data-source config into both
    worktrees. The fingerprint stage ran fine, which is exactly why this is
    worth checking up front: the failure is silent until the harness aborts.
    """
    problems = []
    if not (REPO / "config.py").exists():
        problems.append(
            "MISSING config.py -- the gate qualification (questions 1 and 2) cannot run.\n"
            "    Fix, from the repo root:   cp config_template.py config.py\n"
            "    (config.py is gitignored, so a fresh checkout never has one. The\n"
            "     template's defaults -- limmat / dropbox -- are what the Hub wants.)"
        )
    mf6 = Path(os.path.expanduser("~/.local/share/flopy/bin"))
    if not mf6.exists():
        problems.append(
            f"flopy bin dir not found at {mf6} -- MF6/Triangle may be unresolvable.\n"
            "    Fix:   uv run python -m flopy.mf6.utils.get_modflow ~/.local/share/flopy/bin"
        )
    return problems


def _side_wall_times(report: dict) -> list:
    """Pull per-side wall clock out of a qualification report.

    🔴 The first version of this guessed at `report["pairs"][*]["side_A"]`,
    which does not exist -- so the Hub run of 2026-08-26 passed the
    qualification and still reported an EMPTY multiplier_H. The real shape,
    written by `t0_gate_harness.py` at `workdir/qualification_report.json`, is
    flat: `summary.side_A.wall_s` and `summary.side_B.wall_s`, mirrored at the
    top level. ONE qualify invocation is ONE PAIR (two cold side-runs); T0.0
    Sec 5.1's "6 pairs" came from running it six times.
    """
    sides = []
    for container in (report.get("summary") or {}, report):
        for key in ("side_A", "side_B", "side_A_reference", "side_B_candidate"):
            side = container.get(key)
            if isinstance(side, dict) and isinstance(side.get("wall_s"), (int, float)):
                sides.append(float(side["wall_s"]))
        if sides:
            break          # prefer summary; do not double-count the mirror
    return sides


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--fingerprint-reps", type=int, default=5,
                    help="replications for the repeatability envelope (default 5)")
    ap.add_argument("--skip-fingerprint", action="store_true")
    ap.add_argument("--ignore-preflight", action="store_true",
                    help="run anyway despite preflight problems")
    args = ap.parse_args()

    workdir = Path(os.path.expanduser(args.workdir)).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    problems = preflight()
    if problems:
        print("== PREFLIGHT FAILED -- fix these first ==", file=sys.stderr)
        for prob in problems:
            print("  * " + prob, file=sys.stderr)
        if not args.ignore_preflight:
            print("\n(re-run with --ignore-preflight to proceed anyway; the stages that "
                  "do not need the missing piece will still run)", file=sys.stderr)
            return 2
        print("  ... proceeding anyway (--ignore-preflight)\n", file=sys.stderr)

    print("== 1+2: gate qualification (cold, threads pinned) ==", file=sys.stderr, flush=True)
    qual = run_qualification(workdir)

    sides = _side_wall_times(qual.get("report", {}))
    h = {}
    if sides:
        mean = statistics.fmean(sides)
        h = {"hub_mean_side_s": round(mean, 2),
             "hub_min_side_s": round(min(sides), 2),
             "hub_max_side_s": round(max(sides), 2),
             "n_sides": len(sides),
             "mac_baseline": MAC_BASELINE_S,
             "H": round(mean / MAC_BASELINE_S["mean"], 3)}
        fine = FINE_RUN_MAC_S * h["H"]
        h["projected_fine_run_s"] = round(fine, 1)
        h["verdict"] = ("PASSES CLEANLY (<= target)" if fine <= HUB_FINE_TARGET_S
                        else "PASSES WITH WARNING (target..ceiling)" if fine <= HUB_FINE_CEILING_S
                        else "T2 FAILS -- above HUB_FINE_CEILING_S, declared failure edge")

    fp = {"skipped": True}
    if not args.skip_fingerprint:
        print("== 3: capture-fingerprint repeatability (fresh processes) ==",
              file=sys.stderr, flush=True)
        fp = run_fingerprint_replication(workdir, args.fingerprint_reps)

    print(json.dumps({
        "hub_measurement_version": "1",
        "platform": {"platform": platform.platform(), "machine": platform.machine(),
                     "python": sys.version.split()[0]},
        "qualification": {"returncode": qual["returncode"],
                          "passed": qual["returncode"] == 0,
                          "total_wall_s": qual["total_wall_s"],
                          "summary": (qual.get("report") or {}).get("summary", {}),
                          "stderr_tail": qual["stderr_tail"]},
        "multiplier_H": h,
        "fingerprint_repeatability": fp,
    }, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
