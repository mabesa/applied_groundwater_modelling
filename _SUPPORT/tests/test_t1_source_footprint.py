"""Tests for T1 step S5 -- the fixed physical source footprint
(`DESIGN_DOCS/T1_S5_brief.md` v3, C1 A11, `transport_srcpulse_demo.py`).

Most tests here run against SYNTHETIC geometry (fast, no MF6 solve, no GIS
download) -- the frozen apportionment rule (area-weighted disc, per-cell
rates, the binding-cell rule, the sentinel branch) is a pure geometric/
arithmetic computation over already-available arrays, mirroring the
`test_t1_operator_a.py` philosophy ("most tests here run against synthetic
geometry ... because the diagnostic itself is a pure post-processing
computation"). Only the two tests that must observe the REAL on-disk cache
mechanism (`test_radius_changes_the_cache_identity`,
`test_warm_cache_does_not_serve_a_different_footprint`) pay for a real,
COLD build -- and they share ONE module-scoped fixture so the corridor mesh
(content-addressed independently of the footprint radius) is refined once
and reused, not twice.

Run with:  uv run pytest _SUPPORT/tests/test_t1_source_footprint.py -v
Use `-m "not slow"` to run only the fast, solve-free tests.
"""
import dataclasses
import math
import os
import sys

import numpy as np
import pytest
from shapely.geometry import box

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "scripts"))

import transport_srcpulse_demo as tsd  # noqa: E402
import t1_evidence_artifact as tea  # noqa: E402
import t0_gate_harness as gate  # noqa: E402


# ---------------------------------------------------------------------------
# synthetic-geometry helpers (mirrors test_t1_operator_a.py's `_regular_grid`)
# ---------------------------------------------------------------------------
def _regular_grid(cell: float, extent: float = 100.0, origin=(0.0, 0.0)):
    """A square tiling of `extent` x `extent` centred on `origin`, cell size
    `cell`. Returns (polygons, centroid_x, centroid_y)."""
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
    """Duck-typed stand-in for a flopy DISV ``modelgrid`` -- only
    ``get_cell_vertices`` is used by ``_footprint_cell_polygons`` /
    ``_disc_footprint_areas``."""

    def __init__(self, polys):
        self._polys = polys

    def get_cell_vertices(self, i):
        return list(self._polys[i].exterior.coords)


MASS_G = 3.0e5
PULSE_DAYS = 30.0


# ---------------------------------------------------------------------------
# 1. THE SENTINEL: byte-exact reproduction of pre-S5 SRC stress-period data
# ---------------------------------------------------------------------------
def test_zero_radius_sentinel_emits_identical_src_stress_period_data():
    """Exit criterion 1: `footprint_radius_m == 0.0` (the default) must
    reproduce pre-S5 behaviour byte-for-byte -- the same single nearest-
    centroid cell, the same `smassrate = mass_g / (1 * pulse_days)`, and
    (reconstructing the literal `add_transport_model` list comprehension)
    the same `src_spd` shape and values."""
    _, cx, cy = _regular_grid(10.0)
    spill_xy = (3.3, -2.1)
    nearest_expected = int(np.argmin((cx - spill_xy[0]) ** 2 + (cy - spill_xy[1]) ** 2))

    grid = dict(src_cells=[nearest_expected], footprint_radius_m=0.0)
    src_cells, rates, smassrate = tsd._footprint_rates(grid, MASS_G, PULSE_DAYS)

    expected_rate = MASS_G / (1 * PULSE_DAYS)
    assert src_cells == [nearest_expected]
    assert rates == [expected_rate]
    assert smassrate == expected_rate

    # the literal src_spd construction line from add_transport_model
    src_spd = {0: [[(0, c), r] for c, r in zip(src_cells, rates)], 1: []}
    assert src_spd == {0: [[(0, nearest_expected), expected_rate]], 1: []}


# ---------------------------------------------------------------------------
# 2. per-cell rates are AREA-WEIGHTED, not an equal split
# ---------------------------------------------------------------------------
def test_rates_are_area_weighted_not_equally_split():
    """Exit criterion 2: a cell that barely clips the disc must carry
    proportionally LESS than a cell mostly/fully inside it -- an equal
    split is the exact trap S5 exists to remove."""
    polys, cx, cy = _regular_grid(10.0)
    ncpl = len(polys)
    mg = _FakeModelGrid(polys)
    idomain = np.ones(ncpl, dtype=int)

    cells, areas, disc_area, covered_area = tsd._disc_footprint_areas(
        mg, ncpl, idomain, (0.0, 0.0), 12.0)
    rates = tsd._apportion_rates(areas, total_rate=1000.0)

    assert len(cells) > 1  # the disc spans more than one cell
    assert len(set(round(r, 6) for r in rates)) > 1  # NOT an equal split
    # the apportionment law itself: rate_i / area_i is constant
    ratios = [r / a for r, a in zip(rates, areas)]
    assert max(ratios) == pytest.approx(min(ratios), rel=1e-9)
    # the smallest-area cell carries the smallest rate
    i_min = int(np.argmin(areas))
    assert rates[i_min] == min(rates)


# ---------------------------------------------------------------------------
# 3. mass conservation
# ---------------------------------------------------------------------------
def test_rates_sum_to_total_loading():
    """Exit criterion 3: sum(rate_i) == M/T to tolerance, for every radius."""
    polys, cx, cy = _regular_grid(10.0)
    ncpl = len(polys)
    mg = _FakeModelGrid(polys)
    idomain = np.ones(ncpl, dtype=int)

    for radius in (5.0, 12.0, 27.3, 40.0):
        _, areas, _, _ = tsd._disc_footprint_areas(mg, ncpl, idomain, (0.0, 0.0), radius)
        total_rate = 12345.678
        rates = tsd._apportion_rates(areas, total_rate)
        assert abs(sum(rates) - total_rate) <= 1e-9 * abs(total_rate)


# ---------------------------------------------------------------------------
# 4. mesh independence: same PHYSICAL disc, different meshes
# ---------------------------------------------------------------------------
def test_footprint_geometry_and_total_mass_invariant_across_meshes():
    """T1's exit row (brief Sec 4 exit criterion 4): perturb the mesh and
    assert BOTH the geometry (same physical disc, fully covered) and the
    total mass are invariant. This is explicitly NOT an identical cell set
    -- different meshes necessarily intersect a fixed disc differently."""
    centre = (0.0, 0.0)
    radius = 15.0
    total_rate = 500.0

    polys_a, _, _ = _regular_grid(10.0)
    polys_b, _, _ = _regular_grid(4.0)
    mg_a, mg_b = _FakeModelGrid(polys_a), _FakeModelGrid(polys_b)

    cells_a, areas_a, disc_a, cov_a = tsd._disc_footprint_areas(
        mg_a, len(polys_a), np.ones(len(polys_a), dtype=int), centre, radius)
    cells_b, areas_b, disc_b, cov_b = tsd._disc_footprint_areas(
        mg_b, len(polys_b), np.ones(len(polys_b), dtype=int), centre, radius)

    # same physical disc, fully covered, on BOTH meshes
    assert disc_a == pytest.approx(disc_b, rel=1e-9)
    assert cov_a == pytest.approx(disc_a, rel=1e-6)
    assert cov_b == pytest.approx(disc_b, rel=1e-6)
    # the finer mesh necessarily uses MORE cells to cover the same disc --
    # different meshes intersect it differently, which is the whole point
    assert len(cells_b) > len(cells_a)

    rates_a = tsd._apportion_rates(areas_a, total_rate)
    rates_b = tsd._apportion_rates(areas_b, total_rate)
    assert sum(rates_a) == pytest.approx(total_rate, rel=1e-9)
    assert sum(rates_b) == pytest.approx(total_rate, rel=1e-9)


# ---------------------------------------------------------------------------
# 5. incomplete coverage RAISES -- never a silent renormalisation
# ---------------------------------------------------------------------------
def test_incomplete_disc_coverage_raises():
    """Exit criterion 5 / brief Sec 3.3 'Coverage failure'. Two scenarios:
    (a) the disc extends past the meshed domain's edge, (b) a cell inside
    the disc is INACTIVE (idomain <= 0) -- eligible cells are ACTIVE
    layer-0 cells only, so an inactive cell inside the disc is also a
    coverage failure, not a cell that quietly keeps its area out of the
    apportionment."""
    polys, cx, cy = _regular_grid(10.0, extent=100.0)
    ncpl = len(polys)
    mg = _FakeModelGrid(polys)

    # (a) disc pushed past the meshed domain's edge (extent/2 == 50)
    idomain = np.ones(ncpl, dtype=int)
    with pytest.raises(ValueError, match="not fully covered"):
        tsd._disc_footprint_areas(mg, ncpl, idomain, (48.0, 0.0), 20.0)

    # (b) an inactive cell sits inside an otherwise-fully-meshed disc
    idomain2 = np.ones(ncpl, dtype=int)
    dist2 = (cx - 0.0) ** 2 + (cy - 0.0) ** 2
    inner_cell = int(np.argmin(dist2))
    idomain2[inner_cell] = 0
    with pytest.raises(ValueError, match="not fully covered"):
        tsd._disc_footprint_areas(mg, ncpl, idomain2, (0.0, 0.0), 15.0)


# ---------------------------------------------------------------------------
# 6. no new payload / meta field
# ---------------------------------------------------------------------------
def test_no_new_payload_or_meta_field():
    """Exit criterion 6: S5 must not add a `SrcPulseDemo` dataclass field
    nor a new `meta` key -- T0_0 Sec 2.5 makes either a failure edge. The
    T0 gate's own CANDIDATE enumeration (`t0_gate_harness.py`) is the
    ground truth for what is authorised on the candidate side.

    The `meta` key set below is copied verbatim from the literal
    `meta = dict(...)` construction in `build_srcpulse_demo`
    (`transport_srcpulse_demo.py`), unchanged by S5 (S5 only changed the
    q_src_darcy/b_src/ds_src/q_cell VALUES via the binding-cell rule, never
    the key set). `test_t1_payload_bootstrap.py::
    test_payload_field_set_matches_harness_candidate_schema` independently
    re-checks this same invariant against a REAL run every time the full
    suite executes.
    """
    field_names = {f.name for f in dataclasses.fields(tsd.SrcPulseDemo)
                   if not f.name.startswith("_")}
    assert field_names == set(gate.CANDIDATE_TOP_LEVEL_FIELDS)

    real_meta_keys = {
        "ncpl", "nstp", "dt", "Cr", "n_src", "q_src_darcy", "b_src", "ds_src",
        "q_cell", "v_bind", "ds_bind", "ds_true_min", "courant_floor",
        "refine_radius_used", "u_reg", "cr_capped", "peak_at_last_step",
        "sink_support_cells",
    }
    assert real_meta_keys == set(gate.CANDIDATE_META_KEYS)


# ---------------------------------------------------------------------------
# 7. cells sorted ascending
# ---------------------------------------------------------------------------
def test_src_cells_sorted_by_cell_index():
    polys, cx, cy = _regular_grid(10.0)
    ncpl = len(polys)
    mg = _FakeModelGrid(polys)
    idomain = np.ones(ncpl, dtype=int)

    cells, _, _, _ = tsd._disc_footprint_areas(mg, ncpl, idomain, (3.7, -6.2), 22.0)
    assert cells == sorted(cells)
    assert len(cells) == len(set(cells))  # strictly ascending, no duplicates


# ---------------------------------------------------------------------------
# 8. smassrate_gpd is the arithmetic mean of the per-cell rates
# ---------------------------------------------------------------------------
def test_smassrate_gpd_is_the_arithmetic_mean_of_per_cell_rates():
    """Brief Sec 3.1: `smassrate_gpd` keeps its pre-S5 expression VERBATIM
    (`mass_g / (n_src * pulse_days)`); with unequal per-cell rates this
    equals their arithmetic mean, by construction."""
    polys, cx, cy = _regular_grid(10.0)
    ncpl = len(polys)
    mg = _FakeModelGrid(polys)
    idomain = np.ones(ncpl, dtype=int)

    cells, areas, _, _ = tsd._disc_footprint_areas(mg, ncpl, idomain, (0.0, 0.0), 18.0)
    grid = dict(src_cells=cells, footprint_areas_m2=areas, footprint_radius_m=18.0)
    mass_g, pulse_days = 4.5e5, 25.0
    src_cells, rates, smassrate = tsd._footprint_rates(grid, mass_g, pulse_days)

    assert len(src_cells) > 1  # a trivial n=1 case would not distinguish mean from total
    assert smassrate == pytest.approx(sum(rates) / len(src_cells), rel=1e-12)
    assert smassrate == pytest.approx(mass_g / (len(src_cells) * pulse_days), rel=1e-12)


# ---------------------------------------------------------------------------
# 9-10. the REAL cache mechanism: radius is part of the identity, and a warm
# cache never serves a different footprint. ONE shared, module-scoped, cold
# real build so the corridor mesh (content-addressed independently of the
# footprint radius) is refined ONCE and reused between the two radii.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cache_identity_case(tmp_path_factory):
    ws = tmp_path_factory.mktemp("t1_s5_cache_identity_ws")
    kwargs = dict(mass_g=1.0e4, pulse_days=5.0, total_days=15.0,
                  solubility_mgL=1000.0, case_ws=ws, force=False)
    r0 = tsd.build_srcpulse_demo(footprint_radius_m=0.0, **kwargs)
    r_pos = tsd.build_srcpulse_demo(footprint_radius_m=10.0, **kwargs)
    return ws, kwargs, r0, r_pos


@pytest.mark.slow
def test_radius_changes_the_cache_identity(cache_identity_case):
    """Exit criterion 7: the params dict that keys the cache filename must
    include `footprint_radius_m` -- two runs differing ONLY in radius must
    produce two DISTINCT cache files, never one overwriting the other."""
    ws, _kwargs, _r0, _r_pos = cache_identity_case
    caches = sorted(p.name for p in ws.glob("srcpulse_cache_*.npz"))
    assert len(caches) == 2


@pytest.mark.slow
def test_warm_cache_does_not_serve_a_different_footprint(cache_identity_case):
    """Exit criterion 7's safety property: with BOTH caches warm on disk, a
    fresh request for the sentinel radius must return the SENTINEL's own
    result (not the positive-radius run's), and must not create a THIRD
    cache file."""
    ws, kwargs, r0, r_pos = cache_identity_case
    assert len(r0.src_cells) == 1                     # sentinel: one cell
    assert r_pos.src_cells != r0.src_cells or len(r_pos.src_cells) > 1

    r0_again = tsd.build_srcpulse_demo(footprint_radius_m=0.0, **kwargs)
    assert r0_again.src_cells == r0.src_cells
    assert r0_again.smassrate_gpd == pytest.approx(r0.smassrate_gpd)
    assert r0_again.peak_mgL == pytest.approx(r0.peak_mgL)

    caches_after = sorted(p.name for p in ws.glob("srcpulse_cache_*.npz"))
    assert len(caches_after) == 2  # cache HIT -- no new file


# ---------------------------------------------------------------------------
# 11-12. the binding-cell rule (pure -- synthetic rates/throughflows)
# ---------------------------------------------------------------------------
def test_binding_cell_is_max_rate_over_throughflow():
    """Brief Sec 3.2: the binding cell maximises rate_i / q_cell_i -- the
    highest emergent concentration, where a solubility limit actually
    binds -- NOT simply the highest rate or the lowest throughflow alone."""
    cells = [3, 7, 12]
    # equal throughflow -> ratio order matches rate order
    assert tsd._binding_cell(cells, [10.0, 50.0, 20.0], [100.0, 100.0, 100.0]) == 7
    # a modest rate at very low throughflow beats a larger rate at high
    # throughflow (this is the whole point of the rule)
    rates = [10.0, 50.0, 5.0]
    q_cells = [1.0, 100.0, 0.1]
    # ratios: 10.0/1.0=10.0, 50.0/100.0=0.5, 5.0/0.1=50.0 -> cell 12 binds,
    # even though it has neither the highest rate (cell 7) nor the lowest
    # throughflow alone (cell 3) -- the RATIO is what matters.
    ratios = [r / q for r, q in zip(rates, q_cells)]
    expected = cells[int(np.argmax(ratios))]
    assert expected == 12
    assert tsd._binding_cell(cells, rates, q_cells) == expected


def test_binding_cell_tie_breaks_to_lowest_index():
    """Brief Sec 3.2: ties break to the LOWEST cell index."""
    cells = [9, 2, 5]
    rates = [10.0, 10.0, 1.0]
    q_cells = [1.0, 1.0, 1.0]   # cells 9 and 2 tie at ratio 10.0; cell 5 loses outright
    assert tsd._binding_cell(cells, rates, q_cells) == 2

    # order-independence: the same tie, presented in a different iteration order
    assert tsd._binding_cell([5, 9, 2], [1.0, 10.0, 10.0], [1.0, 1.0, 1.0]) == 2
    assert tsd._binding_cell([2, 9, 5], [10.0, 10.0, 1.0], [1.0, 1.0, 1.0]) == 2


# ---------------------------------------------------------------------------
# 13. a genuinely hand-checkable intersection area
# ---------------------------------------------------------------------------
def test_hand_computed_intersection_area():
    """A disc centred exactly ON the shared edge of two adjacent cells. By
    SYMMETRY each cell must get EXACTLY half the disc's polygonal area --
    no numerical approximation beyond the polygonal disc itself (brief Sec
    3.3: Shapely `Point(...).buffer(r, quad_segs=64)`)."""
    cell_a = box(-10.0, -5.0, 0.0, 5.0)    # x in [-10, 0]
    cell_b = box(0.0, -5.0, 10.0, 5.0)     # x in [0, 10]
    mg = _FakeModelGrid([cell_a, cell_b])
    idomain = np.ones(2, dtype=int)
    radius = 3.0  # well inside the +/-5 y half-extent of both cells

    cells, areas, disc_area, covered_area = tsd._disc_footprint_areas(
        mg, 2, idomain, (0.0, 0.0), radius)

    assert cells == [0, 1]
    assert areas[0] == pytest.approx(areas[1], rel=1e-9)
    assert areas[0] == pytest.approx(disc_area / 2.0, rel=1e-9)
    assert covered_area == pytest.approx(disc_area, rel=1e-9)
    # sanity: the polygonal disc itself is close to the closed-form circle
    # area (quad_segs=64 measures ~1e-4 relative error, per
    # transport_operator_a.py's module docstring for the same construction)
    assert disc_area == pytest.approx(math.pi * radius ** 2, rel=2e-4)


# ---------------------------------------------------------------------------
# 14. a tangent / zero-area touch contributes nothing and is excluded
# ---------------------------------------------------------------------------
def test_tangent_cell_contributes_nothing():
    """Brief Sec 3.3 'Zero-area touch': a cell whose bounding box touches
    the disc's bounding box but whose actual polygon intersection is a
    single POINT (zero area) must contribute nothing and be EXCLUDED from
    `cells` -- not merely skipped by the cheap bounding-box pre-filter."""
    real_cell = box(-3.0, -3.0, 3.0, 3.0)         # disc (r=3) is inscribed in this box
    corner_touch_cell = box(3.0, 3.0, 5.0, 5.0)   # touches the disc's bbox at (3, 3) only
    mg = _FakeModelGrid([real_cell, corner_touch_cell])
    idomain = np.ones(2, dtype=int)

    cells, areas, disc_area, covered_area = tsd._disc_footprint_areas(
        mg, 2, idomain, (0.0, 0.0), 3.0)

    assert cells == [0]              # the corner-touch cell is excluded
    assert len(areas) == 1
    assert covered_area == pytest.approx(disc_area, rel=1e-9)  # full coverage from cell 0 alone


# ---------------------------------------------------------------------------
# 15. radius validation
# ---------------------------------------------------------------------------
def test_negative_or_nonfinite_radius_raises():
    """Brief Sec 3.3 'Radius validation': negative or non-finite -> raise,
    at every layer that accepts a radius, BEFORE any I/O."""
    for bad in (-1.0, -0.001, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            tsd._validate_footprint_radius(bad)

    with pytest.raises(ValueError):
        tsd.build_srcpulse_demo(mass_g=1.0, pulse_days=1.0, total_days=2.0,
                                solubility_mgL=1.0, footprint_radius_m=-5.0)

    # refine_corridor validates before touching cgwf/boundary/rivers -- mirrors
    # test_t1_gridspec.py's object()-sentinel pattern for the mesh_spec guard
    with pytest.raises(ValueError):
        tsd.refine_corridor(object(), object(), object(), footprint_radius_m=float("nan"))


# ---------------------------------------------------------------------------
# 16. the artifact round-trip
# ---------------------------------------------------------------------------
def test_artifact_round_trip_preserves_the_footprint_record():
    """T1 S5 hands its per-cell apportionment to S13's evidence-artifact
    schema (brief Sec 6) as PLAIN DATA -- `transport_srcpulse_demo.py` never
    imports `t1_evidence_artifact` (doing so would grow `_src_sha()`'s
    frozen closure, `test_t1_src_closure.py::DEMO_EXPECTED`). The CALLER
    (here, standing in for S13's producer) builds the
    `SourceFootprintRecord` from this module's plain outputs and round-trips
    it through the artifact's own (de)serialisation."""
    polys, cx, cy = _regular_grid(10.0)
    ncpl = len(polys)
    mg = _FakeModelGrid(polys)
    idomain = np.ones(ncpl, dtype=int)
    centre = (4.0, -7.0)
    radius = 17.0
    mass_g, pulse_days = 2.5e5, 20.0
    total_rate = mass_g / pulse_days

    cells, areas, disc_area, covered_area = tsd._disc_footprint_areas(
        mg, ncpl, idomain, centre, radius)
    rates = tsd._apportion_rates(areas, total_rate)

    entries = tuple(
        tea.FootprintEntry(cell=c, intersection_area_m2=a, rate_g_per_day=r)
        for c, a, r in zip(cells, areas, rates))
    footprint = tea.SourceFootprintRecord(
        algorithm_id=tsd._FOOTPRINT_ALGORITHM_ID, radius_m=float(radius),
        centre_xy_m=(float(centre[0]), float(centre[1])), entries=entries,
        total_rate_g_per_day=float(total_rate),
        coverage=tea.FootprintCoverage(disc_area_m2=disc_area, covered_area_m2=covered_area))

    record = tea.build_fixture_record(run_role="spatial_series", source_footprint=footprint)
    raw = tea.record_to_raw_dict(record)
    reloaded = tea.record_from_raw_dict(raw)

    assert reloaded.source_footprint == footprint
    assert reloaded.source_footprint.entries == entries
    assert reloaded.source_footprint.coverage == footprint.coverage
