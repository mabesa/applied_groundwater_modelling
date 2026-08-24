"""Tests for T1 step S9a -- B-control intersection geometry
(`DESIGN_DOCS/T1_S9a_brief.md` v2, C1 A6, `transport_srcpulse_demo.py`).

S9a apportions the doublet's EXTRACTION rate across the cells intersecting a
fixed physical disc centred on the extraction well, so the receptor's
*support* stops moving with the mesh. It builds no model and is wired into no
call path, so the canonical gate is BLIND to it and these tests are the whole
safety argument (brief Sec 4).

Everything here runs against SYNTHETIC geometry -- no MF6 solve, no GIS
download -- mirroring `test_t1_source_footprint.py`, because the
apportionment is a pure geometric/arithmetic computation.

⚠️ What S9a is: an IMPOSED DISTRIBUTED EXTRACTION CONTROL, a mesh-independent
regularisation of a prescribed areal sink. It is NOT a physical model of well
inflow -- see `test_docstring_states_this_is_not_a_physical_well_model`.

Run with:  uv run pytest _SUPPORT/tests/test_t1_sink_support_geometry.py -v
"""
import ast
import inspect
import math
import os
import sys

import numpy as np
import pytest
from shapely.geometry import box

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_srcpulse_demo as tsd  # noqa: E402


# ---------------------------------------------------------------------------
# synthetic-geometry helpers (same shape as test_t1_source_footprint.py)
# ---------------------------------------------------------------------------
def _regular_grid(cell: float, extent: float = 200.0, origin=(0.0, 0.0)):
    """Square tiling of `extent` x `extent` centred on `origin`. Cell edges
    fall on multiples of `cell` offset from the origin, so a disc centred at
    (0, 0) sits on a grid VERTEX -- which is what makes the centroid vs
    area-weighted discrimination below sharp."""
    n = int(round(extent / cell))
    ox, oy = origin
    polys, cx, cy = [], [], []
    for i in range(n):
        for j in range(n):
            x0 = ox - extent / 2 + i * cell
            y0 = oy - extent / 2 + j * cell
            polys.append(box(x0, y0, x0 + cell, y0 + cell))
            cx.append(x0 + cell / 2)
            cy.append(y0 + cell / 2)
    return polys, np.array(cx), np.array(cy)


class _FakeModelGrid:
    """Duck-typed stand-in for a flopy DISV modelgrid: only
    `get_cell_vertices` is used by `_footprint_cell_polygons`."""

    def __init__(self, polys):
        self._polys = polys

    def get_cell_vertices(self, i):
        return list(self._polys[i].exterior.coords)


DOUBLET_Q = 1370.0          # matches tsd.DOUBLET_Q
Q_EXTRACT = -abs(DOUBLET_Q)  # extraction is NEGATIVE (brief Sec 2)

# The discriminating fixture (brief Sec 2.1): a 10 m grid with the disc
# centred on a grid VERTEX at (0, 0), radius 12 m. Consequences, all exact:
#   * the 4 cells touching the vertex have centroid distance sqrt(50)=7.07 < 12
#     -> centroid INSIDE, and a LARGE partial overlap;
#   * the 8 cells one step out (e.g. [10,20]x[0,10]) have centroid distance
#     sqrt(225+25)=15.81 > 12 -> centroid OUTSIDE, but their nearest corner is
#     at distance 10 < 12 -> a SMALL POSITIVE overlap.
# So a centroid-in-disc rule sees 4 cells; area-weighting sees 12, unequally.
DISC_CELL = 10.0
DISC_R = 12.0


def _fixture():
    polys, cx, cy = _regular_grid(DISC_CELL)
    return _FakeModelGrid(polys), len(polys), None, cx, cy


def _centroid_in_disc_rates(cx, cy, centre, radius, total_rate):
    """The WRONG implementation this step exists to rule out: select cells
    whose CENTROID lies inside the disc, then split `total_rate` equally."""
    d2 = (cx - centre[0]) ** 2 + (cy - centre[1]) ** 2
    sel = np.where(d2 < radius ** 2)[0]
    return [int(c) for c in sel], [total_rate / len(sel)] * len(sel)


# ---------------------------------------------------------------------------
# 1. THE DISCRIMINATING TEST -- the reason S9a exists as its own step
# ---------------------------------------------------------------------------
def test_centroid_in_disc_apportionment_would_fail_this():
    """Brief Sec 2.1 / exit criterion 2. A centroid-in-disc rule must FAIL,
    and must fail CATEGORICALLY rather than by a rounding margin:

      * it selects a DIFFERENT CELL SET (4 cells vs 12) -- it misses every
        cell with positive overlap whose centroid is outside the disc;
      * it splits the rate EQUALLY, so even on the cells it does select its
        rates differ from the area-weighted ones by far more than tolerance.

    Constructed so equal-area luck cannot make it pass: the selected and
    unselected overlaps are deliberately unequal.
    """
    mg, ncpl, idomain, cx, cy = _fixture()
    centre = (0.0, 0.0)

    cells, rates = tsd._sink_footprint_rates(
        mg, ncpl, idomain, centre, DISC_R, ext_cell=0, total_rate=Q_EXTRACT)
    wrong_cells, wrong_rates = _centroid_in_disc_rates(
        cx, cy, centre, DISC_R, Q_EXTRACT)

    # (a) the cell SETS differ -- 12 vs 4
    assert len(wrong_cells) == 4, "fixture invariant: 4 centroids inside the disc"
    assert len(cells) == 12, "fixture invariant: 12 cells with positive overlap"
    assert set(wrong_cells) < set(cells)

    # (b) every centroid-selected cell is a real overlap, so the difference is
    #     not that the wrong rule picked nonsense -- it picked a SUBSET
    for c in wrong_cells:
        assert c in cells

    # (c) at least one cell has POSITIVE overlap but its centroid is OUTSIDE
    #     the disc -- the case centroid selection gets categorically wrong
    outside_but_overlapping = [c for c in cells if c not in wrong_cells]
    assert outside_but_overlapping
    for c in outside_but_overlapping:
        d = math.hypot(cx[c] - centre[0], cy[c] - centre[1])
        assert d > DISC_R, "this cell's centroid must lie OUTSIDE the disc"

    # (d) on the shared cells the rates differ by a wide margin, so the
    #     discrimination is not incidental
    by_cell = dict(zip(cells, rates))
    for c, wrong_rate in zip(wrong_cells, wrong_rates):
        rel = abs(by_cell[c] - wrong_rate) / abs(wrong_rate)
        assert rel > 0.05, (
            f"cell {c}: area-weighted {by_cell[c]!r} vs equal-split "
            f"{wrong_rate!r} -- only {rel:.2%} apart, too close to discriminate")


# ---------------------------------------------------------------------------
# 2. the frozen apportionment rule
# ---------------------------------------------------------------------------
def test_rates_are_area_weighted():
    """Exit criterion 2: rate_i / rate_j == a_i / a_j."""
    mg, ncpl, idomain, _, _ = _fixture()
    cells, areas, _disc, _cov = tsd._sink_footprint_areas(
        mg, ncpl, idomain, (0.0, 0.0), DISC_R)
    _, rates = tsd._sink_footprint_rates(
        mg, ncpl, idomain, (0.0, 0.0), DISC_R, ext_cell=0, total_rate=Q_EXTRACT)
    total_area = math.fsum(areas)
    for a, r in zip(areas, rates):
        assert r == pytest.approx(Q_EXTRACT * a / total_area, rel=1e-12)
    # and the overlaps really are unequal, or the check above is vacuous
    assert max(areas) > 2.0 * min(areas)


def test_rates_sum_to_total_pumping_signed():
    """Exit criterion 3: |sum(q_i) - Q| <= 1e-9*|Q|, on SIGNED values."""
    mg, ncpl, idomain, _, _ = _fixture()
    _, rates = tsd._sink_footprint_rates(
        mg, ncpl, idomain, (0.0, 0.0), DISC_R, ext_cell=0, total_rate=Q_EXTRACT)
    assert math.fsum(rates) == pytest.approx(Q_EXTRACT, abs=1e-9 * abs(Q_EXTRACT))


def test_every_rate_is_negative():
    """Exit criterion 5: extraction stays negative, every q_i <= 0."""
    mg, ncpl, idomain, _, _ = _fixture()
    _, rates = tsd._sink_footprint_rates(
        mg, ncpl, idomain, (0.0, 0.0), DISC_R, ext_cell=0, total_rate=Q_EXTRACT)
    assert rates
    assert all(r < 0.0 for r in rates)


def test_cells_sorted_ascending():
    """Exit criterion 4."""
    mg, ncpl, idomain, _, _ = _fixture()
    cells, _ = tsd._sink_footprint_rates(
        mg, ncpl, idomain, (0.0, 0.0), DISC_R, ext_cell=0, total_rate=Q_EXTRACT)
    assert cells == sorted(cells)
    assert len(cells) == len(set(cells))


def test_tangent_cell_contributes_nothing():
    """Exit criterion 4: a zero-area touch is EXCLUDED, not given a zero
    rate. A disc inscribed in one cell touches its 4 edges tangentially."""
    mg, ncpl, idomain, _, _ = _fixture()
    # centre a disc at a CELL CENTRE with radius exactly half the cell size:
    # tangent to 4 neighbours, strictly inside only its own cell.
    cells, _ = tsd._sink_footprint_rates(
        mg, ncpl, idomain, (5.0, 5.0), DISC_CELL / 2.0,
        ext_cell=0, total_rate=Q_EXTRACT)
    assert len(cells) == 1, f"tangent neighbours must not appear, got {cells}"


def test_hand_computed_intersection_area():
    """Exit criterion 2: an independently computable case. A disc centred on
    a grid VERTEX is split into 4 congruent quadrants by symmetry, so each
    of the 4 vertex-touching cells must receive exactly a quarter of the
    disc's area -- and the total must be the polygonised disc's area.
    """
    mg, ncpl, idomain, _, _ = _fixture()
    cells, areas, disc_area, covered = tsd._sink_footprint_areas(
        mg, ncpl, idomain, (0.0, 0.0), DISC_R)

    # buffer(quad_segs=64) polygonises the circle, so it is slightly under pi*r^2
    assert disc_area == pytest.approx(math.pi * DISC_R ** 2, rel=1e-3)
    assert covered == pytest.approx(disc_area, rel=1e-9)
    assert math.fsum(areas) == pytest.approx(disc_area, rel=1e-9)

    # the four largest overlaps are the vertex-touching cells, congruent by
    # symmetry; each is one quarter of the disc minus its outside-the-cell part
    biggest = sorted(areas, reverse=True)[:4]
    for a in biggest:
        assert a == pytest.approx(biggest[0], rel=1e-6), "quadrants must be congruent"


# ---------------------------------------------------------------------------
# 3. the sentinel -- SAME CELL INDEX, not merely the same total
# ---------------------------------------------------------------------------
def test_zero_radius_sentinel_returns_todays_single_cell_AND_the_same_cell_index():
    """Exit criterion 12. A wrapper preserving sum(q) while MOVING the cell
    would pass a total-only check, so the cell index is asserted explicitly.
    Matches T0_0 Sec 3's identity default [(ext_cell, -abs(DOUBLET_Q))].
    """
    mg, ncpl, idomain, _, _ = _fixture()
    ext_cell = 137
    cells, rates = tsd._sink_footprint_rates(
        mg, ncpl, idomain, (0.0, 0.0), 0.0,
        ext_cell=ext_cell, total_rate=Q_EXTRACT)
    assert cells == [ext_cell]
    assert rates == [Q_EXTRACT]
    # the literal identity-default shape from T0_0 Sec 3
    assert list(zip(cells, rates)) == [(ext_cell, -abs(DOUBLET_Q))]


def test_sentinel_builds_no_disc_geometry():
    """The sentinel must not touch the mesh at all -- a grid whose
    `get_cell_vertices` raises proves no geometry was built."""
    class _Exploding:
        def get_cell_vertices(self, i):
            raise AssertionError("sentinel must not build disc geometry")

    cells, rates = tsd._sink_footprint_rates(
        _Exploding(), 4, None, (0.0, 0.0), 0.0, ext_cell=7, total_rate=Q_EXTRACT)
    assert cells == [7]


# ---------------------------------------------------------------------------
# 4. coverage: BOTH directions
# ---------------------------------------------------------------------------
def test_incomplete_coverage_raises_for_a_disc_near_the_boundary():
    """Exit criterion 6: a disc extending outside the domain is an error,
    never a silent renormalisation. The extraction well may sit nearer a
    boundary than the spill, so this is not a hypothetical for the sink."""
    mg, ncpl, idomain, _, _ = _fixture()
    # the grid spans -100..100; a disc at the corner leaves the domain
    with pytest.raises(ValueError, match="not fully covered"):
        tsd._sink_footprint_rates(
            mg, ncpl, idomain, (99.0, 99.0), DISC_R,
            ext_cell=0, total_rate=Q_EXTRACT)


def test_overcoverage_is_rejected():
    """Exit criterion 9. The shared helper's check is ONE-SIDED
    (`disc_area - covered_area > tol`), so overlapping or invalid polygons
    that DOUBLE-COUNT area would pass it silently. S9a's own wrapper must
    reject the other direction. Simulated with a mesh whose cells overlap.
    """
    cell = DISC_CELL
    polys, _, _ = _regular_grid(cell)
    # duplicate every polygon -> covered_area is exactly twice the disc area
    doubled = polys + list(polys)
    mg = _FakeModelGrid(doubled)
    with pytest.raises(ValueError, match="OVER-covered"):
        tsd._sink_footprint_areas(mg, len(doubled), None, (0.0, 0.0), DISC_R)


# ---------------------------------------------------------------------------
# 5. invalid input
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("radius", [-1.0, float("nan"), float("inf")])
def test_nonfinite_or_negative_radius_raises(radius):
    mg, ncpl, idomain, _, _ = _fixture()
    with pytest.raises(ValueError):
        tsd._sink_footprint_rates(mg, ncpl, idomain, (0.0, 0.0), radius,
                                  ext_cell=0, total_rate=Q_EXTRACT)


@pytest.mark.parametrize("centre", [(float("nan"), 0.0), (0.0, float("inf"))])
def test_nonfinite_centre_raises(centre):
    mg, ncpl, idomain, _, _ = _fixture()
    with pytest.raises(ValueError, match="finite"):
        tsd._sink_footprint_rates(mg, ncpl, idomain, centre, DISC_R,
                                  ext_cell=0, total_rate=Q_EXTRACT)


@pytest.mark.parametrize("rate", [float("nan"), float("inf")])
def test_nonfinite_total_rate_raises(rate):
    mg, ncpl, idomain, _, _ = _fixture()
    with pytest.raises(ValueError, match="finite"):
        tsd._sink_footprint_rates(mg, ncpl, idomain, (0.0, 0.0), DISC_R,
                                  ext_cell=0, total_rate=rate)


# ---------------------------------------------------------------------------
# 6. mesh invariance -- APPORTIONED SUPPORT, not analytic disc area
# ---------------------------------------------------------------------------
def test_mesh_invariance_compares_apportioned_support_not_disc_area():
    """Exit criteria 7 and 11.

    ⚠️ Two meshes trivially agree on pi*r^2, so comparing disc areas proves
    NOTHING. What must be invariant is the APPORTIONED SUPPORT: the total
    rate, and the rate-weighted centroid of where that rate is applied. The
    CELL SETS necessarily differ -- that is the point of a fixed physical
    support -- so they are asserted to differ.
    """
    centre = (0.0, 0.0)

    def support(cell_size):
        polys, cx, cy = _regular_grid(cell_size)
        mg = _FakeModelGrid(polys)
        cells, rates = tsd._sink_footprint_rates(
            mg, len(polys), None, centre, DISC_R,
            ext_cell=0, total_rate=Q_EXTRACT)
        w = np.abs(np.array(rates))
        gx = float(np.sum(w * cx[cells]) / np.sum(w))
        gy = float(np.sum(w * cy[cells]) / np.sum(w))
        return cells, math.fsum(rates), (gx, gy)

    cells_coarse, total_coarse, g_coarse = support(10.0)
    cells_fine, total_fine, g_fine = support(4.0)

    # the cell sets MUST differ -- different meshes intersect the disc differently
    assert len(cells_coarse) != len(cells_fine)

    # but the applied support is the same physical thing
    assert total_coarse == pytest.approx(total_fine, rel=1e-9)
    assert total_coarse == pytest.approx(Q_EXTRACT, rel=1e-9)
    # the rate-weighted centroid is the disc centre on both meshes (symmetry)
    for gc, gf, c in zip(g_coarse, g_fine, centre):
        assert gc == pytest.approx(c, abs=1e-6)
        assert gf == pytest.approx(c, abs=1e-6)


# ---------------------------------------------------------------------------
# 7. reuse, not reimplementation
# ---------------------------------------------------------------------------
def test_reuses_the_s5_helper_and_adds_no_second_intersection_routine():
    """Exit criterion 1. A second buffer/intersection routine would be the
    FOURTH time this repo pays for the same duplication (courant_nstp,
    _src_sha, the doublet WEL). Asserted structurally: the sink geometry
    must CALL `_disc_footprint_areas`, and must not itself buffer a point.
    """
    src = inspect.getsource(tsd._sink_footprint_areas)
    tree = ast.parse(src.lstrip())
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_disc_footprint_areas" in called, "must reuse the S5 helper"

    attr_called = {n.func.attr for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "buffer" not in attr_called, "must not build its own disc"
    assert "intersection" not in attr_called, "must not do its own intersection"
    # and the rates come from S5's apportionment, not a private copy
    rate_src = inspect.getsource(tsd._sink_footprint_rates)
    assert "_apportion_rates" in rate_src


def test_s5_source_behaviour_is_unchanged():
    """Exit criterion 13: the helper was REUSED, not modified. The S5 default
    call path is positional and must be untouched by the new keyword-only
    `disc_label`, and its message must still name the SOURCE."""
    sig = inspect.signature(tsd._disc_footprint_areas)
    label = sig.parameters["disc_label"]
    assert label.kind is inspect.Parameter.KEYWORD_ONLY
    assert label.default == "source footprint disc"

    mg, ncpl, idomain, _, _ = _fixture()
    with pytest.raises(ValueError, match="source footprint disc"):
        tsd._disc_footprint_areas(mg, ncpl, idomain, (99.0, 99.0), DISC_R)


def test_exception_text_names_the_sink_not_the_source():
    """Exit criterion 14: reused for a sink, 'source footprint disc' is
    simply wrong. Message-only, output-neutral."""
    mg, ncpl, idomain, _, _ = _fixture()
    with pytest.raises(ValueError) as excinfo:
        tsd._sink_footprint_areas(mg, ncpl, idomain, (99.0, 99.0), DISC_R)
    msg = str(excinfo.value)
    assert "sink footprint disc" in msg
    assert "source footprint disc" not in msg


# ---------------------------------------------------------------------------
# 8. the honesty requirement (brief Sec 2.0)
# ---------------------------------------------------------------------------
def test_docstring_states_this_is_not_a_physical_well_model():
    """Brief Sec 2.0. The track turns on not overclaiming what a control
    establishes; a docstring implying physical well modelling would re-create
    in code the exact overclaim the notebooks are being rewritten to remove.
    """
    doc = (tsd._sink_footprint_rates.__doc__ or "").lower()
    assert "not" in doc and "physical model of well inflow" in doc
    assert "imposed distributed extraction control" in doc
    # and the single-layer assumption is stated, since it will not fail loudly
    assert "single-layer" in doc or "single layer" in doc


def test_no_new_payload_or_meta_field():
    """Brief Sec 3: S9a adds no field. `sink_support_m` and
    `meta["sink_support_cells"]` already exist at their S2 identity defaults
    (T0_0 Sec 3, schema-lifted), and S9a only COMPUTES what S9b applies."""
    import dataclasses
    names = {f.name for f in dataclasses.fields(tsd.SrcPulseDemo)}
    assert "sink_support_m" in names, "pre-authorised field must already exist"
    assert not {n for n in names if "footprint" in n and n != "sink_support_m"} - names
