"""One grid per group: the flow and transport halves must agree.

Each group's case study has a flow half and a transport half. They used to build
DIFFERENT grids -- flow refined around the doublet's 2 points, transport refines the
whole spill->extraction corridor plus the injection well. Two geometries per group, and
only the transport one was ever validated for the sub-metre cells that made group 4's
transport run diverge.

These are STATIC checks (no MODFLOW, no solve) so they run in milliseconds and catch a
divergence before anyone spends an hour of JupyterHub time regenerating artifacts that
cannot match. They exist because the mismatch was found the expensive way: a hub freeze
produced flow meshes at ladder radii for 12 of 13 groups while the validated transport
pins said otherwise.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(SRC), str(SRC / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import case_utils as cu                     # noqa: E402
import casestudy_flow_common as cfc         # noqa: E402

GROUPS = tuple(range(13))


@pytest.mark.parametrize("group", GROUPS)
def test_flow_anchors_equal_transport_anchors(group):
    """The flow half must refine exactly what the transport half refines.

    Compared against ``transport_base_model._corridor_points`` -- the transport side's
    OWN implementation -- so the mirrored copy in casestudy_flow_common cannot drift.
    """
    import transport_base_model as tbm

    scn = cu.lint_transport_config(groups=[group])[group]
    d, s = scn["doublet"], scn["source"]
    inj = (float(d["injection_easting"]), float(d["injection_northing"]))
    ext = (float(d["extraction_easting"]), float(d["extraction_northing"]))
    spill = (ext[0] + float(s["location"]["easting"]),
             ext[1] + float(s["location"]["northing"]))
    corridor, _u, _L = tbm._corridor_points(spill, ext)
    expected = [tuple(pt) for pt in corridor] + [inj]
    assert cfc.group_refine_points(group) == expected


@pytest.mark.parametrize("group", GROUPS)
def test_every_group_has_a_pinned_radius(group):
    r = cfc.group_refine_radius(group)
    assert r is not None, (
        f"group {group} has no geometry.refine_radius_m -- it would fall back to the "
        f"ladder, which picks the first radius that BUILDS, not one that is usable")
    assert isinstance(r, float) and r > 0


@pytest.mark.parametrize("group", GROUPS)
def test_all_flow_consumers_resolve_the_same_radius(group):
    """🔴 The regression this file exists for.

    THREE separate places walked the ladder ``(70, 62, 78, 56, 84)`` taking the first
    radius that built: the mesh freeze, the golden generator, and the builder students
    and tests run. Fixing only one of them produces artifacts that cannot match -- the
    goldens would be built at a ladder radius while the freeze used the pin.
    """
    import casestudy_flow_golden as cfg          # noqa: F401  (import must not explode)
    import casestudy_flow_builder as cfb         # noqa: F401
    import jupyterhub_refine_reliability_gen as rg

    pinned = cfc.group_refine_radius(group)
    assert rg.group_refine_radius(group) == pinned
    assert rg.group_refine_points(group) == cfc.group_refine_points(group)


def test_no_flow_consumer_silently_walks_the_ladder():
    """Each of the three call sites must consult the pin before the ladder.

    A source-level check on purpose: the alternative is running three MODFLOW builds.
    """
    import inspect

    import casestudy_flow_builder as cfb
    import casestudy_flow_golden as cfg
    import jupyterhub_refine_reliability_gen as rg

    for mod, func in ((rg, "_real_refine_group"),
                      (cfg, "_real_refine_baseline_group"),
                      (cfb, "_refine_solve_baseline_walk")):
        src = inspect.getsource(getattr(mod, func))
        assert "group_refine_radius" in src, (
            f"{mod.__name__}.{func} does not consult the pinned radius -- it will build "
            f"at a ladder radius and its artifact will not match the others")


@pytest.mark.parametrize("group", GROUPS)
def test_both_wells_sit_inside_the_refined_region(group):
    """Near-well resolution is what the drawdown / capture-zone analysis needs."""
    import math

    d = cu.lint_transport_config(groups=[group])[group]["doublet"]
    inj = (float(d["injection_easting"]), float(d["injection_northing"]))
    ext = (float(d["extraction_easting"]), float(d["extraction_northing"]))
    pts = cfc.group_refine_points(group)
    radius = cfc.group_refine_radius(group)
    assert inj in pts
    nearest = min(math.hypot(x - ext[0], y - ext[1]) for x, y in pts)
    assert nearest < 0.25 * radius, (
        f"group {group}: extraction well {nearest:.1f} m from the nearest anchor, "
        f"not comfortably inside the {radius:g} m radius")
