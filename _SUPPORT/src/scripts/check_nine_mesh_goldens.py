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
import casestudy_flow_common as cfc  # noqa: E402
import model_io_utils as mio  # noqa: E402

#: Canonical members describing the MESH ITSELF. If these differ the grid moved;
#: if only the others differ, the grid is intact and a package array changed.
_MESH_MEMBERS = frozenset({
    "gridprops__vertices", "gridprops__cell2d_flat", "gridprops__cell2d_lengths",
    "gridprops__ncpl", "gridprops__nvert", "ncpl", "botm", "top", "idomain",
    "crs", "refine_radius_used",
})

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


def member_level_diff(group: int, manifest: dict) -> dict:
    """Which canonical members differ, WITHOUT the builder's pin raising first.

    `build_flow_state` refuses to continue when the pin fails, so it can say *that*
    the grid diverged but never *which part*. This rebuilds the spec directly -- the
    same path `test_builder_spec_hashes_match_committed_without_solve` uses -- and
    diffs member by member, which is the difference between "the mesh moved" and "a
    package array changed".
    """
    out = {"mesh_members_differing": [], "package_members_differing": [],
           "mesh_intact": None, "aggregate_matches": None}
    try:
        mother = mio.ensure_flow_model()
        _sim, cgwf = cfc.load_coarse_model(mother)
        coarse_heads = cgwf.output.head().get_data().flatten()
        boundary_gdf, river_gdf = cfc.load_gis(mother)
        refine_points = cfc.group_refine_points(group)
        spec, riv_info = cfc.build_baseline_spec(
            cgwf, boundary_gdf, river_gdf, refine_points, coarse_heads)
        agg, arr = cfc.spec_canonical_hashes(spec)
    except Exception as exc:                       # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return out

    golden_arr = manifest.get("array_hashes") or {}
    for name, want in sorted(golden_arr.items()):
        if arr.get(name) != want:
            key = "mesh_members_differing" if name in _MESH_MEMBERS else "package_members_differing"
            out[key].append(name)
    out["mesh_intact"] = not out["mesh_members_differing"]
    out["aggregate_matches"] = (agg == manifest.get("aggregate_hash"))
    out["faithful_riv_matches"] = (
        riv_info.get("hash") == (manifest.get("faithful_riv") or {}).get("hash"))
    return out


def check_group(group: int, *, state: str = "baseline", diagnose: bool = False) -> dict:
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
        # the builder's pin fires before any of our own comparisons, so go get the
        # member-level detail it could not give us
        rec["diff"] = member_level_diff(group, manifest)
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

    if diagnose and "diff" not in rec:
        rec["diff"] = member_level_diff(group, manifest)
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
    ap.add_argument("--diagnose", action="store_true",
                    help="always compute the member-level diff (costs one extra spec "
                         "build per group), not only when the pin fires")
    ap.add_argument("--json", type=Path, default=None,
                    help="write the full per-group record here (the A16 evidence file)")
    args = ap.parse_args()

    host_os = platform.system()
    print(f"A16 nine-mesh regression check -- host {host_os}, "
          f"groups {args.groups}, state {args.state!r}\n", flush=True)

    records = []
    for g in args.groups:
        rec = check_group(g, state=args.state, diagnose=args.diagnose)
        records.append(rec)
        enforced = "hashes ENFORCED" if rec.get("hashes_enforced") else "hashes SKIPPED (cross-platform)"
        print(f"[{rec['result']:4s}] group {g}  ({enforced}, {rec.get('wall_s', '?')}s)", flush=True)
        for f in rec["failures"]:
            print(f"         ! {f}", flush=True)
        d = rec.get("diff") or {}
        if d and not d.get("error"):  # printed for FAIL, and for --diagnose on PASS
            mesh = d["mesh_members_differing"]
            pkg = d["package_members_differing"]
            print(f"         > mesh intact: {d['mesh_intact']}"
                  f"   mesh members differing: {mesh or 'none'}"
                  f"   package members differing: {pkg or 'none'}", flush=True)
        elif d.get("error"):
            print(f"         > member-level diff unavailable: {d['error']}", flush=True)

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
