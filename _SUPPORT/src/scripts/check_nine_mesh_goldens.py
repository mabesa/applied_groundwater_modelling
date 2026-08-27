"""A16 / S3b — regression evidence for the NINE FROZEN case-study group meshes.

C1 **A16** authorises graded mesh construction (milestone S3b) on `disv_grid_utils.py`,
and records the blast radius explicitly:

    "disv_grid_utils also builds the NINE FROZEN case-study group meshes -- S3b must
     carry regression evidence for those, not just the transport suite."

That evidence did not exist. What existed:

  * `casestudy_flow_builder.assert_all_groups_anchored()` -- ANCHORING: every group has a
    committed golden XOR a deferral. It performs **zero builds**, so it proves the
    artifacts are present, not that the meshes still reproduce.
  * `test_casestudy_flow_builder.py` -- builds **group 0 only**, and its golden-hash
    assertions do not run on macOS (see below).

This script closes that: it REBUILDS each group and compares against its committed golden.

Two classes of check, because they behave differently across platforms
--------------------------------------------------------------------
The Triangle/Voronoi mesh is platform-DEPENDENT (M2a.5 proved a golden frozen on one OS
does not reproduce on another), so hashes are a valid pin only on the golden's own
generation OS. Everything else is not mesh-topology and does hold across platforms.

  PLATFORM-DEPENDENT (enforced only on the golden's generation OS):
      grid aggregate hash · canonical array/package hashes · faithful-RIV hash
  PLATFORM-INDEPENDENT (enforced ALWAYS, on every OS):
      refine radius · flow mass balance · convergence · finite heads · no dry cells

So a run on a non-authoritative OS is NOT vacuous: it still catches a radius walk landing
somewhere new, a solver regression, or a broken flow field in any of the nine groups.

Usage
-----
    uv run python _SUPPORT/src/scripts/check_nine_mesh_goldens.py
    uv run python _SUPPORT/src/scripts/check_nine_mesh_goldens.py --groups 0 3 --json out.json

Exit status is 0 only when every ENFORCED check passed. Checks skipped as
cross-platform are reported as SKIP and never silently counted as passes.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "_SUPPORT" / "src"))

import casestudy_flow_builder as b  # noqa: E402

#: Diagnostic gates the builder already computes; all are platform-independent.
_HEALTH_GATES = ("flow_mass_balance", "flow_convergence", "finite_heads",
                 "flow_no_dry_cells")


def _gate_ok(value) -> bool:
    """Diagnostics entries are either a bool or a dict carrying a pass flag."""
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        for key in ("passed", "ok", "pass", "within_tolerance"):
            if key in value:
                return bool(value[key])
    return value is not None


def check_group(group: int, *, state: str = "baseline") -> dict:
    """Rebuild one group and compare it against its committed golden."""
    manifest = b._frozen_golden_manifest(group)
    if manifest is None:
        return {"group": group, "result": "NO_GOLDEN",
                "detail": "no committed golden manifest -- not a frozen group"}

    cross = b._golden_is_cross_platform(manifest)
    rec = {
        "group": group,
        "golden_generation_os": b._golden_generation_os(manifest),
        "current_os": platform.system(),
        "hashes_enforced": not cross,
        "checks": {},
        "failures": [],
    }

    t0 = time.time()
    try:
        with tempfile.TemporaryDirectory() as wd:
            built = b.build_flow_state(group, state, work_dir=wd)
    except Exception as exc:                       # noqa: BLE001 -- report, never mask
        rec["result"] = "FAIL"
        rec["wall_s"] = round(time.time() - t0, 1)
        rec["failures"].append(f"build raised {type(exc).__name__}: {str(exc)[:400]}")
        return rec
    rec["wall_s"] = round(time.time() - t0, 1)

    # --- platform-independent: enforced on every OS -------------------------
    golden_radius = manifest.get("radius_used")
    built_radius = built.get("refine_radius")
    if golden_radius is not None and built_radius is not None:
        ok = abs(float(built_radius) - float(golden_radius)) <= 1e-9
        rec["checks"]["refine_radius"] = "PASS" if ok else "FAIL"
        if not ok:
            rec["failures"].append(
                f"refine_radius {built_radius} != golden radius_used {golden_radius}")

    diagnostics = built.get("diagnostics") or {}
    for gate in _HEALTH_GATES:
        if gate not in diagnostics:
            continue
        ok = _gate_ok(diagnostics[gate])
        rec["checks"][gate] = "PASS" if ok else "FAIL"
        if not ok:
            rec["failures"].append(f"diagnostic gate {gate} did not pass")

    # --- platform-dependent: only a valid pin on the generation OS ----------
    hash_pairs = (
        ("aggregate_hash", built.get("grid_hash"), manifest.get("aggregate_hash")),
        ("array_hashes", built.get("package_hashes"), manifest.get("array_hashes")),
        ("faithful_riv_hash", (built.get("riv_info") or {}).get("hash"),
         (manifest.get("faithful_riv") or {}).get("hash")),
    )
    for name, got, want in hash_pairs:
        if want is None:
            continue
        if cross:
            rec["checks"][name] = "SKIP_CROSS_PLATFORM"
            continue
        ok = got == want
        rec["checks"][name] = "PASS" if ok else "FAIL"
        if not ok:
            g = json.dumps(got)[:24] if not isinstance(got, str) else got[:24]
            w = json.dumps(want)[:24] if not isinstance(want, str) else want[:24]
            rec["failures"].append(f"{name}: built {g}.. != golden {w}..")

    rec["result"] = "FAIL" if rec["failures"] else "PASS"
    return rec


def is_full_a16_evidence(records, expected_groups=None) -> bool:
    """True only when this run IS the evidence A16 requires.

    Three conditions, all necessary:
      * every group A16 names was checked (nine, unless deliberately subset);
      * no group failed;
      * mesh-topology hashes were ENFORCED on every group -- a run whose hashes were
        skipped as cross-platform is useful (it still checks radius and solver health)
        but it is NOT the pin, so it can never be the evidence.
    """
    expected = tuple(range(9)) if expected_groups is None else tuple(expected_groups)
    seen = tuple(r["group"] for r in records)
    if sorted(seen) != sorted(expected):
        return False
    if any(r.get("result") != "PASS" for r in records):
        return False
    return all(r.get("hashes_enforced") for r in records)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--groups", type=int, nargs="+", default=list(b.ALL_GROUPS))
    ap.add_argument("--state", default="baseline")
    ap.add_argument("--json", type=Path, default=None,
                    help="write the full per-group record here (the A16 evidence file)")
    args = ap.parse_args()

    host_os = platform.system()
    print(f"A16 nine-mesh regression check -- host {host_os}, "
          f"groups {args.groups}, state {args.state!r}\n", flush=True)

    records = []
    for g in args.groups:
        rec = check_group(g, state=args.state)
        records.append(rec)
        enforced = "hashes ENFORCED" if rec.get("hashes_enforced") else "hashes SKIPPED (cross-platform)"
        print(f"[{rec['result']:4s}] group {g}  ({enforced}, {rec.get('wall_s', '?')}s)", flush=True)
        for f in rec["failures"]:
            print(f"         ! {f}", flush=True)

    n_fail = sum(1 for r in records if r["result"] == "FAIL")
    n_pass = sum(1 for r in records if r["result"] == "PASS")
    n_hash_enforced = sum(1 for r in records if r.get("hashes_enforced"))

    print(f"\n{n_pass} passed, {n_fail} failed, of {len(records)} groups")
    print(f"mesh-topology hashes enforced on {n_hash_enforced}/{len(records)} groups")
    if n_hash_enforced < len(records):
        print(f"⚠️  {host_os} is NOT the generation OS for "
              f"{len(records) - n_hash_enforced} golden(s): their topology hashes were "
              f"SKIPPED, not passed. Full A16 evidence requires a run on the "
              f"authoritative platform.")

    summary = {
        "host_os": host_os,
        "state": args.state,
        "groups": args.groups,
        "passed": n_pass,
        "failed": n_fail,
        "hashes_enforced_on": n_hash_enforced,
        "is_full_a16_evidence": is_full_a16_evidence(records),
        "records": records,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(summary, indent=2) + "\n")
        print(f"\nwrote {args.json}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
