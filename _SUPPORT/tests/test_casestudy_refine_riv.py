"""
Unit tests for `casestudy_refine_riv` -- the faithful RIV re-transfer
(case-study path only; see DESIGN_DOCS/student_casestudy_M2a_0_riv_addendum.md).

All synthetic-grid, no MODFLOW: a hand-built regular quad grid, hand-built
coarse RIV reaches (calibrated stage/cond/rbot + a coarse cell polygon), and
a hand-built river polygon. Covers the addendum invariants: exact Sigma-cond
conservation, full coverage, per-reach records (multiple records per cell,
NO stage/rbot blending), fail-fast on zero-overlap, active-only, determinism,
a coarse cell whose footprint spans two reaches on one refined cell, a coarse
RIV cell with no active refined overlap (raises), and the OVERBANK filter.

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_refine_riv.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import geopandas as gpd  # noqa: E402
from shapely.geometry import Polygon, box  # noqa: E402

import casestudy_refine_riv as crr  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic regular quad grid gridprops builder.
# ---------------------------------------------------------------------------
def quad_gridprops(nx, ny, dx=10.0, x0=0.0, y0=0.0):
    """Regular nx*ny grid of dx-square cells; cell index = j*nx + i (row-major,
    bottom-up). Returns a DISV-style gridprops dict."""
    vid = {}
    vertices = []
    k = 0
    for j in range(ny + 1):
        for i in range(nx + 1):
            vid[(i, j)] = k
            vertices.append([k, x0 + i * dx, y0 + j * dx])
            k += 1
    cell2d = []
    ic = 0
    for j in range(ny):
        for i in range(nx):
            bl, br = vid[(i, j)], vid[(i + 1, j)]
            tr, tl = vid[(i + 1, j + 1)], vid[(i, j + 1)]
            xc = x0 + (i + 0.5) * dx
            yc = y0 + (j + 0.5) * dx
            cell2d.append([ic, xc, yc, 4, bl, br, tr, tl])
            ic += 1
    return {"nvert": len(vertices), "ncpl": nx * ny, "vertices": vertices, "cell2d": cell2d}


def cell_index(nx, i, j):
    return j * nx + i


def river_polygon_gdf(geom):
    return gpd.GeoDataFrame(geometry=[geom], crs="EPSG:2056")


def reach(cellid, stage, cond, rbot, poly):
    return crr.CoarseRivReach(cellid=cellid, stage=stage, cond=cond, rbot=rbot, geometry=poly)


# ---------------------------------------------------------------------------
# refined_cell_polygons
# ---------------------------------------------------------------------------
def test_refined_cell_polygons_reconstructs_squares():
    gp = quad_gridprops(2, 2, dx=10.0)
    polys = crr.refined_cell_polygons(gp)
    assert len(polys) == 4
    # cell 0 is the bottom-left [0,10]x[0,10]
    assert polys[0].equals(box(0, 0, 10, 10))
    # cell 3 is top-right [10,20]x[10,20]
    assert polys[3].equals(box(10, 10, 20, 20))


# ---------------------------------------------------------------------------
# Conservation + coverage + per-reach records
# ---------------------------------------------------------------------------
class TestConservationAndCoverage:
    def _grid(self):
        # 4x2 grid of 10 m cells over [0,40]x[0,20]
        return quad_gridprops(4, 2, dx=10.0)

    def test_single_reach_exact_conservation_and_records(self):
        gp = self._grid()
        idomain = np.ones(gp["ncpl"], dtype=int)
        # coarse cell covers the whole bottom row band; river is a horizontal
        # strip y in [4,16] over x in [0,40] -> overlaps all 8 cells partly.
        coarse_poly = box(0, 0, 40, 20)
        river = box(0, 4, 40, 16)
        reaches = [reach((0, 0), stage=8.0, cond=1000.0, rbot=3.0, poly=coarse_poly)]
        recs = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
        # exact conservation
        assert crr.total_conductance(recs) == pytest.approx(1000.0, abs=1e-9)
        # coverage: every cell whose polygon intersects the strip gets a record
        assert len(recs) == 8  # 4 cols x 2 rows all straddle y in [4,16]
        # each record carries the ORIGINAL stage/rbot (no blend)
        for cid, stage, cond, rbot in recs:
            assert stage == 8.0 and rbot == 3.0 and cond > 0

    def test_conductance_split_proportional_to_river_overlap_area(self):
        gp = quad_gridprops(2, 1, dx=10.0)  # 2 cells: [0,10] and [10,20], y[0,10]
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 20, 10)
        # river strip x in [5,20]: cell0 overlaps [5,10] (area 50), cell1 [10,20] (area 100)
        river = box(5, 0, 20, 10)
        reaches = [reach((0, 0), 8.0, 300.0, 3.0, coarse_poly)]
        recs = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
        by_cell = {cid[1]: cond for cid, _, cond, _ in recs}
        # 50:100 -> 100:200
        assert by_cell[0] == pytest.approx(100.0, abs=1e-9)
        assert by_cell[1] == pytest.approx(200.0, abs=1e-9)
        assert sum(by_cell.values()) == pytest.approx(300.0, abs=1e-9)

    def test_two_reaches_on_one_cell_kept_separate_no_blend(self):
        gp = quad_gridprops(1, 1, dx=10.0)  # single cell [0,10]^2
        idomain = np.ones(1, dtype=int)
        cpoly = box(0, 0, 10, 10)
        river = box(0, 0, 10, 10)
        reaches = [
            reach((0, 0), stage=8.0, cond=100.0, rbot=3.0, poly=cpoly),
            reach((0, 1), stage=6.0, cond=40.0, rbot=1.0, poly=cpoly),
        ]
        recs = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
        # the single refined cell carries TWO records (one per reach), NOT one
        # blended record -- MF6 sums them; stage/rbot are each reach's own.
        assert len(recs) == 2
        stages = sorted(s for _, s, _, _ in recs)
        rbots = sorted(b for _, _, _, b in recs)
        assert stages == [6.0, 8.0]
        assert rbots == [1.0, 3.0]
        assert crr.total_conductance(recs) == pytest.approx(140.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Active-only
# ---------------------------------------------------------------------------
class TestActiveOnly:
    def test_conductance_only_on_active_cells_still_conserved(self):
        gp = quad_gridprops(2, 1, dx=10.0)
        idomain = np.array([1, 0], dtype=int)  # cell 1 inactive
        coarse_poly = box(0, 0, 20, 10)
        river = box(0, 0, 20, 10)  # covers both cells
        reaches = [reach((0, 0), 8.0, 300.0, 3.0, coarse_poly)]
        recs = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
        cells = {cid[1] for cid, _, _, _ in recs}
        assert cells == {0}, "RIV must only land on the active cell"
        # all conductance goes to the active cell (renormalized) -> exact
        assert crr.total_conductance(recs) == pytest.approx(300.0, abs=1e-9)

    def test_reach_over_only_inactive_cells_raises(self):
        gp = quad_gridprops(2, 1, dx=10.0)
        idomain = np.array([1, 0], dtype=int)
        # coarse cell + river only over cell 1 (inactive)
        coarse_poly = box(10, 0, 20, 10)
        river = box(10, 0, 20, 10)
        reaches = [reach((0, 1), 8.0, 300.0, 3.0, coarse_poly)]
        with pytest.raises(ValueError, match="(?i)no active refined cell|coverage gap"):
            crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")


# ---------------------------------------------------------------------------
# Fail-fast on zero river overlap
# ---------------------------------------------------------------------------
class TestFailFast:
    def test_reach_not_under_river_raises_empty_footprint(self):
        gp = quad_gridprops(2, 1, dx=10.0)
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 10, 10)
        river = box(100, 100, 110, 110)  # nowhere near the coarse cell
        reaches = [reach((0, 0), 8.0, 100.0, 3.0, coarse_poly)]
        with pytest.raises(ValueError, match="(?i)empty river-geometry footprint|not covered"):
            crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")

    def test_reach_river_outside_grid_raises_no_overlap(self):
        # river footprint is non-empty (over the coarse cell) but the coarse
        # cell sits entirely outside the refined grid -> no refined overlap.
        gp = quad_gridprops(2, 1, dx=10.0)  # grid over [0,20]x[0,10]
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(100, 0, 120, 10)
        river = box(100, 0, 120, 10)  # over the coarse cell, but far from grid
        reaches = [reach((0, 5), 8.0, 100.0, 3.0, coarse_poly)]
        with pytest.raises(ValueError, match="(?i)no active refined cell|coverage gap"):
            crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def test_determinism_identical_across_calls():
    gp = quad_gridprops(4, 3, dx=10.0)
    idomain = np.ones(gp["ncpl"], dtype=int)
    coarse_poly = box(0, 0, 40, 30)
    river = box(5, 5, 35, 25)
    reaches = [
        reach((0, 0), 8.0, 500.0, 3.0, coarse_poly),
        reach((0, 1), 7.0, 250.0, 2.0, box(0, 0, 40, 15)),
    ]
    a = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
    b = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
    # BYTE-identical records (exact float equality via ==), not just "close".
    assert a == b
    assert [repr(x) for x in a] == [repr(x) for x in b]  # bit-pattern identical
    assert crr.riv_records_hash(a) == crr.riv_records_hash(b)


def test_split_is_order_independent_and_exactly_conserving():
    """Finding 1a: the within-reach split sorts cells + uses math.fsum before
    dividing, so the STRtree query order can never perturb the result. A reach
    spread over many cells must (a) sum EXACTLY to the coarse cond (fsum) and
    (b) reproduce byte-identically across calls."""
    import math

    gp = quad_gridprops(6, 6, dx=10.0)  # 36 cells
    idomain = np.ones(gp["ncpl"], dtype=int)
    coarse_poly = box(0, 0, 60, 60)
    river = box(3, 3, 57, 57)  # overlaps many cells with unequal areas
    reaches = [reach((0, 0), 8.0, 1234.5678, 3.0, coarse_poly)]
    recs = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
    # exact conservation via fsum (no float drift)
    assert math.fsum(c for _, _, c, _ in recs) == pytest.approx(1234.5678, abs=1e-9)
    # reproducible byte-for-byte
    recs2 = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
    assert [repr(x) for x in recs] == [repr(x) for x in recs2]


def test_return_stats_reports_full_reach_coverage():
    """Finding 3: n_reaches_placed == n_source_reaches (every reach placed)."""
    gp = quad_gridprops(4, 2, dx=10.0)
    idomain = np.ones(gp["ncpl"], dtype=int)
    reaches = [
        reach((0, 0), 8.0, 100.0, 3.0, box(0, 0, 40, 20)),
        reach((0, 1), 7.0, 50.0, 2.0, box(0, 0, 40, 10)),
    ]
    river = box(0, 0, 40, 20)
    recs, stats = crr.faithful_riv_from_coarse(
        gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056", return_stats=True,
    )
    assert stats["n_source_reaches"] == 2
    assert stats["n_reaches_placed"] == 2
    assert stats["primitive"] == "area"
    assert stats["min_retained_weight_ratio"] == pytest.approx(1.0)  # no overbank filter
    assert stats["reaches_below_warn_ratio"] == []


def test_output_is_sorted_by_cellid():
    gp = quad_gridprops(3, 1, dx=10.0)
    idomain = np.ones(3, dtype=int)
    coarse_poly = box(0, 0, 30, 10)
    river = box(0, 0, 30, 10)
    reaches = [reach((0, 0), 8.0, 300.0, 3.0, coarse_poly)]
    recs = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
    icells = [cid[1] for cid, _, _, _ in recs]
    assert icells == sorted(icells)


# ---------------------------------------------------------------------------
# Overbank filter (refined_botm)
# ---------------------------------------------------------------------------
class TestOverbankFilter:
    def test_overbank_cell_excluded_conductance_renormalized(self):
        gp = quad_gridprops(2, 1, dx=10.0)  # cells 0:[0,10], 1:[10,20]
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 20, 10)
        river = box(0, 0, 20, 10)  # equal overlap on both cells (area 100 each)
        reaches = [reach((0, 0), stage=8.0, cond=200.0, rbot=5.0, poly=coarse_poly)]
        # cell 1 botm=6 > rbot=5 -> overbank, excluded; cell 0 botm=1 <= 5 kept
        botm = np.array([1.0, 6.0])
        recs = crr.faithful_riv_from_coarse(
            gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056", refined_botm=botm,
        )
        cells = {cid[1] for cid, _, _, _ in recs}
        assert cells == {0}, "overbank cell 1 (botm>rbot) must be excluded"
        # ALL conductance renormalized onto the compatible cell -> still exact
        assert crr.total_conductance(recs) == pytest.approx(200.0, abs=1e-9)
        # and rbot >= botm for every emitted record
        for cid, _, _, rbot in recs:
            assert rbot >= botm[cid[1]]

    def test_all_overbank_above_stage_raises_even_with_fallback(self):
        # botm 9 > rbot 5 (overbank) AND > stage 8: a riverbed cannot sit below the
        # water surface anywhere, so even the (default-on) botm-floor fallback drops
        # it. This is the fallback's LIMIT case.
        gp = quad_gridprops(2, 1, dx=10.0)
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 20, 10)
        river = box(0, 0, 20, 10)
        reaches = [reach((0, 0), 8.0, 200.0, 5.0, coarse_poly)]
        botm = np.array([9.0, 9.0])
        with pytest.raises(ValueError, match="(?i)overbank.*stage|stage"):
            crr.faithful_riv_from_coarse(
                gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056", refined_botm=botm,
            )

    def test_botm_floor_fallback_places_and_floors_rbot(self):
        # all cells overbank (botm > rbot 5) but below stage 8 -> fallback keeps
        # both, floors each rbot UP to the cell botm, preserves Sigma cond.
        gp = quad_gridprops(2, 1, dx=10.0)
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 20, 10)
        river = box(0, 0, 20, 10)  # equal overlap on both cells
        reaches = [reach((0, 0), stage=8.0, cond=200.0, rbot=5.0, poly=coarse_poly)]
        botm = np.array([6.0, 7.0])
        recs, stats = crr.faithful_riv_from_coarse(
            gp, idomain, reaches, river_polygon_gdf(river),
            crs="EPSG:2056", refined_botm=botm, return_stats=True,
        )
        assert {cid[1] for cid, _, _, _ in recs} == {0, 1}      # both kept, not dropped
        assert crr.total_conductance(recs) == pytest.approx(200.0, abs=1e-9)  # Sigma cond exact
        by_cell = {cid[1]: (stage, cond, rbot) for cid, stage, cond, rbot in recs}
        assert by_cell[0][2] == pytest.approx(6.0)             # rbot floored to cell botm
        assert by_cell[1][2] == pytest.approx(7.0)
        for _, stage, _, rbot in recs:
            assert rbot >= 5.0 and stage >= rbot               # raised UP; invariant holds
        # provenance recorded
        floored = stats["reaches_botm_floored"]
        assert len(floored) == 1
        assert floored[0]["reach"] == [0, 0]
        assert floored[0]["rbot_coarse_m"] == pytest.approx(5.0)
        assert floored[0]["rbot_floored_min_m"] == pytest.approx(6.0)   # min botm of floored cells
        assert floored[0]["rise_m"] == pytest.approx(1.0)
        assert floored[0]["n_cells"] == 2

    def test_botm_floor_fallback_disabled_raises(self):
        gp = quad_gridprops(2, 1, dx=10.0)
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 20, 10)
        river = box(0, 0, 20, 10)
        reaches = [reach((0, 0), 8.0, 200.0, 5.0, coarse_poly)]
        botm = np.array([6.0, 7.0])  # floorable, but fallback disabled
        with pytest.raises(ValueError, match="(?i)overbank"):
            crr.faithful_riv_from_coarse(
                gp, idomain, reaches, river_polygon_gdf(river),
                crs="EPSG:2056", refined_botm=botm, botm_floor_fallback=False,
            )

    def test_no_floored_reaches_reports_empty_list(self):
        # a clean (no-overbank) build reports an empty reaches_botm_floored
        gp = quad_gridprops(2, 1, dx=10.0)
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 20, 10)
        river = box(0, 0, 20, 10)
        reaches = [reach((0, 0), 8.0, 200.0, 5.0, coarse_poly)]
        botm = np.array([1.0, 1.0])  # both compatible (botm <= rbot)
        recs, stats = crr.faithful_riv_from_coarse(
            gp, idomain, reaches, river_polygon_gdf(river),
            crs="EPSG:2056", refined_botm=botm, return_stats=True,
        )
        assert stats["reaches_botm_floored"] == []

    def test_botm_floor_fallback_over_concentration_fails(self):
        # all cells overbank; only a 0.4% sliver is FLOORABLE (rest above stage) ->
        # the fallback obeys the same FAIL floor as the main path.
        gp = quad_gridprops(2, 1, dx=100.0)      # cells 0:[0,100], 1:[100,200]
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 200, 100)
        river = box(99.6, 0, 200, 100)           # cell0 sliver (40) + all cell1 (10000)
        reaches = [reach((0, 0), 8.0, 1000.0, 5.0, coarse_poly)]
        botm = np.array([6.0, 9.0])              # cell0 floorable (6<=8); cell1 above stage (9>8)
        with pytest.raises(ValueError, match="(?i)concentrat|retains only"):
            crr.faithful_riv_from_coarse(
                gp, idomain, reaches, river_polygon_gdf(river),
                crs="EPSG:2056", refined_botm=botm,
            )

    def test_botm_floor_fallback_warn_band_records_and_proceeds(self):
        gp = quad_gridprops(2, 1, dx=100.0)
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 200, 100)
        river = box(80, 0, 200, 100)             # cell0 2000 + cell1 10000 -> 16.7%
        reaches = [reach((0, 0), 8.0, 1000.0, 5.0, coarse_poly)]
        botm = np.array([6.0, 9.0])
        recs, stats = crr.faithful_riv_from_coarse(
            gp, idomain, reaches, river_polygon_gdf(river),
            crs="EPSG:2056", refined_botm=botm, return_stats=True,
        )
        # proceeds onto cell0, conductance conserved, rbot floored to cell0 botm
        assert {cid[1] for cid, _, _, _ in recs} == {0}
        assert crr.total_conductance(recs) == pytest.approx(1000.0, abs=1e-9)
        assert recs[0][3] == pytest.approx(6.0)
        # both the over-concentration WARN and the botm-floor provenance are recorded
        assert len(stats["reaches_below_warn_ratio"]) == 1
        assert stats["reaches_below_warn_ratio"][0]["retained_ratio"] == pytest.approx(2000.0 / 12000.0, rel=1e-6)
        assert len(stats["reaches_botm_floored"]) == 1
        assert stats["min_retained_weight_ratio"] == pytest.approx(2000.0 / 12000.0, rel=1e-6)

    def test_no_botm_means_no_overbank_filter(self):
        gp = quad_gridprops(2, 1, dx=10.0)
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 20, 10)
        river = box(0, 0, 20, 10)
        reaches = [reach((0, 0), 8.0, 200.0, 5.0, coarse_poly)]
        # without refined_botm, both cells kept regardless of any elevation
        recs = crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")
        assert {cid[1] for cid, _, _, _ in recs} == {0, 1}


class TestOverbankOverConcentration:
    """Finding 4: after the overbank filter, if a reach retains only a tiny
    sliver of its footprint, its whole conductance concentrates there.
      - retained ratio < 0.05 -> HARD RAISE;
      - 0.05 <= ratio < 0.25 -> RECORD a warning + proceed."""

    def _grid_two_100m_cells(self):
        # cells 0:[0,100]x[0,100], 1:[100,200]x[0,100]
        return quad_gridprops(2, 1, dx=100.0)

    def test_ratio_below_fail_floor_raises(self):
        gp = self._grid_two_100m_cells()
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 200, 100)
        # river covers a 0.4 m sliver of cell0 (area 40) + all of cell1 (10000);
        # cell1 is overbank -> retained 40/10040 = 0.40% < FAIL floor 0.5% -> FAIL.
        river = box(99.6, 0, 200, 100)
        botm = np.array([1.0, 9.0])  # cell0 compat (rbot 5), cell1 overbank
        reaches = [reach((0, 0), 8.0, 1000.0, 5.0, coarse_poly)]
        with pytest.raises(ValueError, match="(?i)concentrat|retains only"):
            crr.faithful_riv_from_coarse(
                gp, idomain, reaches, river_polygon_gdf(river),
                crs="EPSG:2056", refined_botm=botm,
            )

    def test_ratio_in_warn_band_records_and_proceeds(self):
        gp = self._grid_two_100m_cells()
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 200, 100)
        # cell0 sliver area 2000 + cell1 (overbank) 10000 -> retained 2000/12000
        # = 16.7%, in [5%, 25%) -> WARN + proceed.
        river = box(80, 0, 200, 100)
        botm = np.array([1.0, 9.0])
        reaches = [reach((0, 0), 8.0, 1000.0, 5.0, coarse_poly)]
        recs, stats = crr.faithful_riv_from_coarse(
            gp, idomain, reaches, river_polygon_gdf(river),
            crs="EPSG:2056", refined_botm=botm, return_stats=True,
        )
        # proceeds: conductance conserved onto the retained (cell 0) only
        assert {cid[1] for cid, _, _, _ in recs} == {0}
        assert crr.total_conductance(recs) == pytest.approx(1000.0, abs=1e-9)
        # recorded, not swallowed
        assert len(stats["reaches_below_warn_ratio"]) == 1
        entry = stats["reaches_below_warn_ratio"][0]
        assert entry["retained_ratio"] == pytest.approx(2000.0 / 12000.0, rel=1e-6)
        assert entry["retained_cells"] == [0]
        assert stats["min_retained_weight_ratio"] == pytest.approx(2000.0 / 12000.0, rel=1e-6)

    def test_no_overbank_drop_keeps_ratio_one(self):
        gp = self._grid_two_100m_cells()
        idomain = np.ones(2, dtype=int)
        coarse_poly = box(0, 0, 200, 100)
        river = box(0, 0, 200, 100)
        botm = np.array([1.0, 1.0])  # both compatible -> nothing dropped
        reaches = [reach((0, 0), 8.0, 1000.0, 5.0, coarse_poly)]
        recs, stats = crr.faithful_riv_from_coarse(
            gp, idomain, reaches, river_polygon_gdf(river),
            crs="EPSG:2056", refined_botm=botm, return_stats=True,
        )
        assert stats["min_retained_weight_ratio"] == pytest.approx(1.0)
        assert stats["reaches_below_warn_ratio"] == []


# ---------------------------------------------------------------------------
# Invariant guards + hash helpers
# ---------------------------------------------------------------------------
def test_stage_below_rbot_raises():
    gp = quad_gridprops(1, 1, dx=10.0)
    idomain = np.ones(1, dtype=int)
    cpoly = box(0, 0, 10, 10)
    river = box(0, 0, 10, 10)
    reaches = [reach((0, 0), stage=2.0, cond=100.0, rbot=5.0, poly=cpoly)]  # stage < rbot
    with pytest.raises(ValueError, match="(?i)stage.*rbot|rbot"):
        crr.faithful_riv_from_coarse(gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056")


def test_hash_changes_with_conductance():
    a = [((0, 1), 8.0, 100.0, 3.0)]
    b = [((0, 1), 8.0, 200.0, 3.0)]
    assert crr.riv_records_hash(a) != crr.riv_records_hash(b)


def test_hash_order_independent():
    a = [((0, 1), 8.0, 100.0, 3.0), ((0, 2), 7.0, 50.0, 2.0)]
    b = list(reversed(a))
    assert crr.riv_records_hash(a) == crr.riv_records_hash(b)


def test_return_primitive_is_area_for_polygon_river():
    gp = quad_gridprops(1, 1, dx=10.0)
    idomain = np.ones(1, dtype=int)
    river = box(0, 0, 10, 10)
    reaches = [reach((0, 0), 8.0, 100.0, 3.0, box(0, 0, 10, 10))]
    recs, prim = crr.faithful_riv_from_coarse(
        gp, idomain, reaches, river_polygon_gdf(river), crs="EPSG:2056", return_primitive=True,
    )
    assert prim == "area"
