"""T2 -- run one identity of the frozen matrix, through the S3 controls.

Every run in T2 goes through here, so no identity can be run that the
pre-registration does not reference, under a guard the caller invented, or be
treated as evidence before it passes acceptance.

    uv run python _SUPPORT/src/scripts/t2_run_matrix.py spatial_10m_cr0.9 --workdir ~/t2

`T2_steps.md` v4: S4 (cheap spatial) produces the `(ncpl, nstp, wall)` triples
that S8's pricing model fits. That model is what eventually decides whether
2 m is affordable -- so these cheap runs are the basis for the expensive
decision, not a warm-up.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "_SUPPORT/src"))
sys.path.insert(0, str(REPO / "_SUPPORT/src/scripts"))

import t2_controls as ctl          # noqa: E402
import t1_artifact_producer as prod  # noqa: E402
import transport_srcpulse_demo as tsd  # noqa: E402

#: identity -> the corridor cell size it names. "50 m (native)" is the
#: corridor at base resolution, expressed as a single level equal to
#: `base_cell_size` -- `_require_single_level` admits exactly one level, so
#: "no refinement" is spelled as "refine to the size it already is".
SPATIAL_CELL_SIZE = {
    "spatial_50m_cr0.9": 50.0,
    "spatial_20m_cr0.9": 20.0,
    "spatial_10m_cr0.9": 10.0,
    "spatial_5m_cr0.9": 5.0,
    "spatial_2m_cr0.9": 2.0,
    "spatial_1m_cr0.9": 1.0,
}
CR_TARGET = {**{k: 0.9 for k in SPATIAL_CELL_SIZE},
             "bcontrol_coarse": 0.9, "bcontrol_fine": 0.9,
             "temporal_50m_cr0.45": 0.45, "temporal_50m_cr0.225": 0.225,
             "temporal_2m_cr0.45": 0.45, "temporal_2m_cr0.225": 0.225}
TEMPORAL_CELL_SIZE = {"temporal_50m_cr0.45": 50.0, "temporal_50m_cr0.225": 50.0,
                      "temporal_2m_cr0.45": 2.0, "temporal_2m_cr0.225": 2.0}

# --- B-control: the matched sink-support arm -------------------------------
#
# 🔴 `sink_support_m` was never frozen, which is what blocked these two
# identities. It is frozen HERE at operator A's already-frozen radius, under
# operator A's already-frozen applicability rule -- rather than inventing a
# second, inconsistent number for the same geometric question.
#
#   transport_operator_a.RADIUS_M = 25.0, applicable iff
#   `cell_size_m <= radius_m` ("the disc diameter spans at least two nominal
#   cells").
#
# That rule IS the degeneracy that blocked B-control: at 50 m cells `50 <= 25`
# is false, the disc falls inside a single cell, the apportionment
# `q_i = Q * area(cell_i ^ disc)/area(disc)` returns the whole rate to one cell,
# and the "control" controls nothing.
#
# So the matched pair is **10 m + 2 m**, NOT 50 m + 2 m. Both satisfy the rule,
# both are registered spatial identities, and 10 m is the meaningful coarse case
# -- it is the teaching default students actually run. Nothing in the contracts
# pins B's coarse mesh to 50 m; `T0_2b…` §5 says only "matched coarse + fine".
SINK_SUPPORT_M = 25.0
BCONTROL_CELL_SIZE = {"bcontrol_coarse": 10.0, "bcontrol_fine": 2.0}
BCONTROL_GRID_ROLE = {"bcontrol_coarse": "coarse", "bcontrol_fine": "fine"}
#: the OTHER half of the matched pair
BCONTROL_COUNTERPART = {"bcontrol_coarse": "t2_bcontrol_fine",
                        "bcontrol_fine": "t2_bcontrol_coarse"}
#: the same mesh WITHOUT the sink control -- what the arm is a control FOR
BCONTROL_UNCONTROLLED = {"bcontrol_coarse": "t2_spatial_10m_cr0.9",
                         "bcontrol_fine": "t2_spatial_2m_cr0.9"}


def run_role_for(identity: str) -> str:
    """🔴 The role was HARD-CODED to `spatial_series` for every identity.

    `T0_2b…` §5.1 freezes `run_role` as a closed enum and makes it mandatory
    precisely so a run's role cannot be confused -- and the two temporal
    identities were emitted mislabelled as `spatial_series` on 2026-08-31
    before this was caught. Derive it from the identity instead.
    """
    if identity.startswith("temporal"):
        return "temporal_series"
    if identity.startswith("bcontrol"):
        return "b_control"
    return "spatial_series"


# One representative claim per run. The artifact records the RUN; `claim_id`
# is one field of it, and S14 produces the per-(claim, run) records the
# evaluation actually consumes.
REPRESENTATIVE_CLAIM = "85c05b6b5be4"


def run_identity(identity: str, workdir: Path, *,
                 measured_cr09_demand: int | None = None,
                 courant_profile: str = "exp_v1") -> dict:
    """🔴 `exp_v1` is the DEFAULT here, deliberately.

    `legacy_srcpulse` excludes `src_cells + [injc, extc]` from Courant sizing
    -- the source and BOTH doublet wells, which are the highest-velocity
    cells in the domain because flow converges on the extraction well. It
    also pins the sliver floor at a constant 4.0 m regardless of the
    `MeshSpec`, which silently drops every cell of a 2 m corridor.

    Under that policy the reported `Cr` is not the field's Cr, and a
    refinement series measures its own re-quantisation -- the exact confound
    that made the original grid spike unusable. T1 built `exp_v1` to fix it;
    T2's matrix is experimental evidence generation, not the teaching
    default, so it is what the matrix runs under.
    """
    ctl.verify_prereg()
    ctl.require_registered(identity)
    guard = ctl.guard_for(identity, measured_cr09_demand)

    cell = (SPATIAL_CELL_SIZE.get(identity) or TEMPORAL_CELL_SIZE.get(identity)
            or BCONTROL_CELL_SIZE.get(identity))
    if cell is None:
        raise ctl.ControlRefusal(f"no cell size known for identity {identity!r}")
    is_b = identity in BCONTROL_CELL_SIZE
    if is_b and cell > SINK_SUPPORT_M:
        # operator A's applicability rule, applied to the sink disc
        raise ctl.ControlRefusal(
            f"{identity}: cell size {cell} m exceeds sink_support_m "
            f"{SINK_SUPPORT_M} m -- the disc would fall inside a single cell "
            "and the control would be a no-op")
    spec = tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=cell),))

    case_ws = workdir / identity
    t0 = time.time()
    record, omitted = prod.run_and_build_record(
        run_id=f"t2_{identity}", case_id="t2_notebook_matrix",
        claim_id=REPRESENTATIVE_CLAIM, claim_type="numeric",
        metric="capture_halfwidth_m", tolerance=0.05,
        run_role=run_role_for(identity),
        axis="temporal" if identity.startswith("temporal") else "spatial",
        grid_role=BCONTROL_GRID_ROLE.get(identity),
        counterpart_run_id=BCONTROL_COUNTERPART.get(identity),
        uncontrolled_counterpart_run_id=BCONTROL_UNCONTROLLED.get(identity),
        sink_support_m=SINK_SUPPORT_M if is_b else 0.0,
        mesh_spec=spec, cr_target=CR_TARGET[identity], nstp_cap=guard,
        courant_profile=courant_profile, case_ws=case_ws, force=True,
    )
    wall = time.time() - t0

    artifact = case_ws / f"{identity}.json"
    prod.write_record(record, omitted, artifact)
    acc = ctl.accept_run(artifact, identity=identity, requested_guard=guard)
    ctl.write_acceptance(acc, artifact)

    return {"identity": identity, "cell_size_m": cell,
            "courant_profile": courant_profile,
            "cr_target": CR_TARGET[identity], "guard": guard,
            "ncpl": record.ncpl, "nstp": record.nstp,
            "cr_achieved": record.cr_achieved, "wall_s": round(wall, 1),
            "work_W": (record.ncpl or 0) * (record.nstp or 0),
            "accepted": acc.passed, "failures": acc.failures,
            "artifact": str(artifact)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("identities", nargs="+")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--measured-cr09-demand", type=int, default=None)
    ap.add_argument("--courant-profile", default="exp_v1",
                    choices=["exp_v1", "legacy_srcpulse"],
                    help="exp_v1 (default) is the corrected policy; legacy is "
                         "the teaching default and UNDER-RESOLVES in time")
    args = ap.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    out = []
    for ident in args.identities:
        try:
            res = run_identity(ident, workdir,
                               measured_cr09_demand=args.measured_cr09_demand,
                               courant_profile=args.courant_profile)
        except ctl.ControlRefusal as exc:
            print(f"[REFUSED] {ident}: {exc}", file=sys.stderr)
            return 2
        flag = "ok  " if res["accepted"] else "FAIL"
        print(f"[{flag}] {ident:22s} ncpl={res['ncpl']:6d} nstp={res['nstp']:5d} "
              f"Cr={res['cr_achieved']:.3f} wall={res['wall_s']:7.1f}s", flush=True)
        if not res["accepted"]:
            print(f"         acceptance failures: {res['failures']}", file=sys.stderr)
        out.append(res)

    (workdir / "t2_run_summary.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nsummary -> {workdir / 't2_run_summary.json'}")
    return 0 if all(r["accepted"] for r in out) else 1


if __name__ == "__main__":
    raise SystemExit(main())
