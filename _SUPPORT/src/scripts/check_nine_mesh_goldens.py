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

#: The mesh TOPOLOGY -- vertices and connectivity. If these differ, the grid moved.
_TOPOLOGY_MEMBERS = frozenset({
    "gridprops__vertices", "gridprops__cell2d_flat", "gridprops__cell2d_lengths",
    "gridprops__ncpl", "gridprops__nvert", "ncpl", "nvert",
})
#: Per-cell PROPERTIES sampled onto that topology. `botm` and `top` are elevations
#: interpolated from the mother model, NOT mesh geometry -- an earlier version of this
#: script bucketed `botm` as topology and so reported "mesh intact: False" for a run
#: whose mesh was in fact identical. `strt` follows `botm` through the
#: `strt = max(strt, botm + 0.01)` clip, so the two move together from one cause.
_CELL_PROPERTY_MEMBERS = frozenset({
    "botm", "top", "idomain", "k", "strt", "crs", "refine_radius_used", "well_cells",
})

#: Recorded in every manifest's `versions`, and decisive: these libraries determine the
#: bit pattern of interpolated arrays. Kernel/platform strings are deliberately NOT
#: compared -- a kernel bump is not a numerical difference.
_ENV_KEYS = ("numpy", "flopy", "python", "geos")


def current_env() -> dict:
    import platform as _p
    env = {"python": _p.python_version()}
    try:
        import numpy
        env["numpy"] = numpy.__version__
    except Exception:                              # noqa: BLE001
        env["numpy"] = None
    try:
        import flopy
        env["flopy"] = flopy.__version__
    except Exception:                              # noqa: BLE001
        env["flopy"] = None
    try:
        from shapely import geos_version_string
        env["geos"] = str(geos_version_string)
    except Exception:                              # noqa: BLE001
        env["geos"] = None
    return env


def env_mismatch(manifest) -> dict:
    """Which recorded library versions differ from this environment.

    🔴 A golden pins hashes of FLOATING-POINT ARRAYS. Those are reproducible only in the
    environment that produced them -- same OS is necessary but NOT sufficient. The
    manifest has always recorded `versions`; nothing ever compared them, so an
    environment mismatch surfaced as nine spurious FAILs indistinguishable from a real
    regression.
    """
    golden = (manifest.get("versions") or {})
    now = current_env()
    out = {}
    for k in _ENV_KEYS:
        a, b = golden.get(k), now.get(k)
        if a is None or b is None:
            continue
        a, b = str(a), str(b)
        if k == "python":
            # MEASURED, not assumed: a machine on CPython 3.12.10 reproduces `botm` and
            # `strt` bit-for-bit against goldens frozen on 3.12.9, so a PATCH bump is not
            # a numerical difference. Compare major.minor only -- comparing the patch
            # level would flag a conforming environment and make the check unusable.
            a, b = ".".join(a.split(".")[:2]), ".".join(b.split(".")[:2])
        if a != b:
            out[k] = {"golden": str(golden.get(k)), "current": str(now.get(k))}
    return out

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
    out = {"topology_members_differing": [], "cell_property_members_differing": [],
           "package_members_differing": [], "topology_intact": None,
           "aggregate_matches": None,
           "built_at_radius": manifest.get("radius_used")}
    try:
        mother = mio.ensure_flow_model()
        _sim, cgwf = cfc.load_coarse_model(mother)
        coarse_heads = cgwf.output.head().get_data().flatten()
        boundary_gdf, river_gdf = cfc.load_gis(mother)
        refine_points = cfc.group_refine_points(group)
        # 🔴 BUILD AT THE GOLDEN'S OWN RADIUS. The builder walks `retry_radii` =
        # (70, 62, 78, 56, 84) and freezes whichever one first converged, so five of the
        # nine goldens are radius 62, not the default 70. Calling build_baseline_spec
        # without a radius silently builds at 70 and compares it against a 62 golden --
        # which reports EVERY member as differing and looks exactly like a catastrophic
        # regression. That artefact is precisely what this argument prevents.
        golden_radius = manifest.get("radius_used")
        kwargs = {} if golden_radius is None else {"refine_radius": float(golden_radius)}
        spec, riv_info = cfc.build_baseline_spec(
            cgwf, boundary_gdf, river_gdf, refine_points, coarse_heads, **kwargs)
        agg, arr = cfc.spec_canonical_hashes(spec)
    except Exception as exc:                       # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return out

    golden_arr = manifest.get("array_hashes") or {}
    for name, want in sorted(golden_arr.items()):
        if arr.get(name) != want:
            if name in _TOPOLOGY_MEMBERS:
                out["topology_members_differing"].append(name)
            elif name in _CELL_PROPERTY_MEMBERS:
                out["cell_property_members_differing"].append(name)
            else:
                out["package_members_differing"].append(name)
    out["topology_intact"] = not out["topology_members_differing"]
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
    env_diff = env_mismatch(manifest)
    # The calibration a golden was built from. Goldens frozen before 2026-08-28 do not
    # record it, so absence is reported as unknown rather than treated as agreement --
    # a drifted mother model was the 2026-08-28 root cause and must never read as "fine".
    golden_fp = (manifest.get("versions") or {}).get("flow_model_fingerprint")
    try:
        import model_io_utils as _mio
        current_fp = _mio.flow_model_fingerprint(_mio.ensure_flow_model())
    except Exception:                                        # noqa: BLE001
        current_fp = None
    # 🔴 Same OS is necessary but NOT sufficient: a golden pins hashes of floating-point
    # arrays, reproducible only in the environment that produced them. If the recorded
    # libraries differ, the hashes cannot distinguish a regression from an environment
    # change, so they are not enforced and the run is INCONCLUSIVE -- never a silent PASS.
    rec = {
        "group": group,
        "golden_generation_os": b._golden_generation_os(manifest),
        "current_os": platform.system(),
        "env_mismatch": env_diff,
        "flow_model_fingerprint": current_fp,
        "golden_flow_model_fingerprint": golden_fp,
        "flow_model_matches_golden": (None if golden_fp is None else golden_fp == current_fp),
        "hashes_enforced": (not cross) and not env_diff,
        "checks": {},
        "failures": [],
    }

    t0 = time.time()
    try:
        with tempfile.TemporaryDirectory() as wd:
            built = b.build_flow_state(group, state, work_dir=wd)
    except Exception as exc:                       # noqa: BLE001 -- report, never mask
        rec["wall_s"] = round(time.time() - t0, 1)
        rec["failures"].append(f"build raised {type(exc).__name__}: {str(exc)[:400]}")
        # the builder's pin fires before any of our own comparisons, so go get the
        # member-level detail it could not give us
        rec["diff"] = member_level_diff(group, manifest)
        # `_pin_built_grid_to_frozen_golden` guards on OS ALONE, so it raises even when
        # the real cause is a library mismatch. Do not report that as a regression.
        rec["result"] = "ENV_MISMATCH" if env_diff else "FAIL"
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
    # DELIBERATELY nine, not N_GROUPS. This script is A16's regression evidence
    # over the FROZEN golden set, and only groups 0-8 have frozen goldens. Groups
    # 9-12 (added 2026-08-31) carry deferrals until their authoritative Linux
    # goldens are generated; widening this default would silently report a pass
    # over meshes that were never frozen. Pass expected_groups explicitly to widen.
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
            pkg = d["package_members_differing"]
            print(f"         > topology intact: {d['topology_intact']}"
                  f" | topology: {d['topology_members_differing'] or 'none'}"
                  f" | cell-properties: {d['cell_property_members_differing'] or 'none'}"
                  f" | packages: {pkg or 'none'}", flush=True)
        elif d.get("error"):
            print(f"         > member-level diff unavailable: {d['error']}", flush=True)

    n_fail = sum(1 for r in records if r["result"] == "FAIL")
    n_pass = sum(1 for r in records if r["result"] == "PASS")
    n_env = sum(1 for r in records if r["result"] == "ENV_MISMATCH")
    n_hash_enforced = sum(1 for r in records if r.get("hashes_enforced"))

    print(f"\n{n_pass} passed, {n_fail} failed, {n_env} inconclusive (environment), "
          f"of {len(records)} groups")
    unknown_fp = [r["group"] for r in records
                  if r.get("golden_flow_model_fingerprint") is None]
    if unknown_fp and n_fail:
        cur = next((r.get("flow_model_fingerprint") for r in records), None)
        print(f"\n⚠️  {len(unknown_fp)} golden(s) predate flow_model_fingerprint recording, so "
              f"the calibration they\n   were built from CANNOT be checked here. This "
              f"machine's calibration is {cur}.\n   Verify with "
              f"model_io_utils.verify_flow_model() -- a drifted mother model produces "
              f"exactly\n   the signature 'topology none / cell-properties [botm, strt]'.")
    if n_env:
        ex = next(r for r in records if r["result"] == "ENV_MISMATCH")
        print("\n🔴 ENVIRONMENT MISMATCH -- these goldens pin hashes of floating-point "
              "arrays and\n   are reproducible ONLY in the environment that produced them:")
        for k, v in ex["env_mismatch"].items():
            print(f"     {k:8s} golden {v['golden']:12s} != current {v['current']}")
        print("   This is NOT a regression and NOT evidence either way. Install the "
              "project's\n   locked dependencies (uv.lock) and re-run.")
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
    return 1 if (n_fail or n_env) else 0


if __name__ == "__main__":
    raise SystemExit(main())
