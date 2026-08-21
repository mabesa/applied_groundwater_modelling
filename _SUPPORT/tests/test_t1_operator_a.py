"""Tests for `transport_operator_a` -- T1 S6, operator A (the fixed-support
disc diagnostic labelled `observation_support_robustness`).

Per `DESIGN_DOCS/T1_S6_brief.md` v2 Sec 4/5: operator A is DIAGNOSTIC ONLY,
never causal support, and does not change the taught single-cell metric. Most
tests here run against synthetic geometry (fast, no MF6 solve) because the
diagnostic itself is a pure post-processing computation over already-produced
arrays. The one test that MUST use the real corridor-refined DISV mesh --
`test_operator_a_is_not_algebraically_the_single_cell_value` -- is marked
`@pytest.mark.slow` and pays for exactly one real flow solve (via a
module-scoped fixture), mirroring how the rest of the transport test suite
already prices a real mesh (`test_transport_srcpulse_demo.py`'s `case_ws`
docstring).

Run with:  uv run pytest _SUPPORT/tests/test_t1_operator_a.py -v
"""
import dataclasses
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import flopy  # noqa: E402

import transport_operator_a as opa  # noqa: E402
import transport_srcpulse_demo as tsd  # noqa: E402
import t1_evidence_artifact as tea  # noqa: E402

TOL_CONC_REL = 0.02  # T0_2b_metrics_and_causal_rule.md Sec 2.7


# ---------------------------------------------------------------------------
# synthetic-geometry helpers
# ---------------------------------------------------------------------------
def _regular_grid(cell: float, extent: float = 80.0, origin=(0.0, 0.0)):
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


def _gaussian_field(x, y, *, x0=5.0, y0=3.0, amp=10.0, sigma=30.0):
    return amp * np.exp(-((x - x0) ** 2 + (y - y0) ** 2) / (2.0 * sigma ** 2))


# ---------------------------------------------------------------------------
# 1. mesh-independence
# ---------------------------------------------------------------------------
def test_same_field_two_meshes_same_value_within_tolerance():
    """The SAME imposed physical field, sampled on two different meshes (5 m
    and 2 m regular tilings covering the disc with margin), must give C_A
    within TOL_CONC_REL of each other."""
    center = (0.0, 0.0)

    def _run(cell):
        polys, cx, cy = _regular_grid(cell)
        n = len(polys)
        field = _gaussian_field(cx, cy)
        record = opa.compute_operator_a(
            cell_polygons=polys, heads=np.ones(n), top=np.ones(n), botm=np.zeros(n),
            porosity=1.0, get_concentration=lambda t, f=field: f, times=[0.0],
            cell_size_m=cell, center_xy=center)
        assert record.status == "computed"
        return record.values[0]

    c5 = _run(5.0)
    c2 = _run(2.0)
    rel_diff = abs(c5 - c2) / c2
    assert rel_diff < TOL_CONC_REL, (c5, c2, rel_diff)


# ---------------------------------------------------------------------------
# 2. THE test that matters most: not algebraically the single-cell value,
#    on the REAL default 10 m corridor-refined mesh.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real_default_grid(tmp_path_factory):
    """The real, corridor-refined DISV mesh at the DEFAULT `MeshSpec()` (10 m
    intended cell size) -- one real flow solve, reused by every test in this
    module that needs actual model geometry."""
    ws = tmp_path_factory.mktemp("operator_a_real_grid_ws")
    cgwf, boundary, rivers, exe = tsd.load_limmat_flow()
    grid = tsd.refine_corridor(cgwf, boundary, rivers, mesh_spec=tsd.MeshSpec(),
                               case_ws=ws)
    return grid


@pytest.mark.slow
def test_operator_a_is_not_algebraically_the_single_cell_value(real_default_grid):
    """Exit criterion 2 (brief Sec 4): on the DEFAULT 10 m geometry, impose a
    ONE-HOT field (C_ext = 1, every other cell 0). A synthetic mesh could
    prove `A != C_ext` while the DEFAULT geometry stayed effectively
    single-cell -- this construction, on the real demo mesh, cannot."""
    grid = real_default_grid
    mg = grid["modelgrid"]
    ncpl = grid["ncpl"]
    ext_cell = grid["ext_cell"]
    top = grid["top"]
    botm = grid["botm"][0]
    heads = grid["heads"]
    porosity = tsd.LOCKED_PARAMS["porosity"]
    cell_size_m = opa.cell_size_from_mesh_spec(tsd.MeshSpec())
    assert cell_size_m == pytest.approx(10.0)

    polys = opa.cell_polygons_from_modelgrid(mg, ncpl)

    one_hot = np.zeros(ncpl, dtype=float)
    one_hot[ext_cell] = 1.0

    record = opa.compute_operator_a(
        cell_polygons=polys, heads=heads, top=top, botm=botm, porosity=porosity,
        get_concentration=lambda t: one_hot, times=[0.0], cell_size_m=cell_size_m,
        center_xy=tsd.ABS_XY)
    assert record.status == "computed"
    c_a = record.values[0]

    # independent verification: C_A must equal w_ext / sum(w)
    disc = opa.disc_polygon(tsd.ABS_XY, radius_m=opa.RADIUS_M, quad_segs=opa.QUAD_SEGS)
    areas = opa.cell_intersection_areas(polys, disc)
    b_sat = opa.saturated_thickness(heads, top, botm)
    weights = opa.cell_weights(areas, b_sat, porosity)
    assert weights.sum() > 0.0
    expected = float(weights[ext_cell] / weights.sum())
    assert c_a == pytest.approx(expected, rel=1e-9)

    # THE exit criterion: A is not algebraically the single-cell value.
    assert 1.0 - c_a > 0.02, (
        f"operator A collapsed to (near) the single-cell value on the default "
        f"geometry: C_A={c_a!r}")

    # mutating only a non-extraction contributor must change A.
    others = np.where((weights > 0.0) & (np.arange(ncpl) != ext_cell))[0]
    assert others.size > 0, "no non-extraction cell has positive weight in the disc"
    j = int(others[np.argmax(weights[others])])
    mutated = one_hot.copy()
    mutated[j] = 0.5
    record2 = opa.compute_operator_a(
        cell_polygons=polys, heads=heads, top=top, botm=botm, porosity=porosity,
        get_concentration=lambda t: mutated, times=[0.0], cell_size_m=cell_size_m,
        center_xy=tsd.ABS_XY)
    assert record2.values[0] != pytest.approx(c_a, rel=1e-9), (
        "mutating a non-extraction contributor did not change operator A")


# ---------------------------------------------------------------------------
# 3. label
# ---------------------------------------------------------------------------
def test_artifact_label_is_observation_support_robustness():
    assert opa.LABEL == "observation_support_robustness"
    record = opa.computed_record([0.0], [1.0], center_xy=(0.0, 0.0))
    assert record.label == "observation_support_robustness"
    assert record.label in tea.DIAGNOSTIC_LABELS


# ---------------------------------------------------------------------------
# 4. exact intersection vs. a hand-computed case; centroid-in-disc fails
# ---------------------------------------------------------------------------
def test_exact_intersection_matches_hand_computed_case():
    disc = opa.disc_polygon((0.0, 0.0), radius_m=10.0, quad_segs=64)

    fully_inside = box(-1.0, -1.0, 1.0, 1.0)          # area 4.0, well inside r=10
    fully_disjoint = box(100.0, 100.0, 101.0, 101.0)  # far away
    left_half = box(-50.0, -50.0, 0.0, 50.0)          # covers x in [-50, 0]

    areas = opa.cell_intersection_areas([fully_inside, fully_disjoint, left_half], disc)

    assert areas[0] == pytest.approx(4.0, rel=1e-9)
    assert areas[1] == pytest.approx(0.0, abs=1e-12)
    # by the disc's symmetry about x=0, a half-plane covering the disc's
    # bounding box on one side must intersect it in exactly half its area --
    # an INDEPENDENT hand argument, not a re-derivation via the same code path.
    assert areas[2] == pytest.approx(disc.area / 2.0, rel=1e-9)


def test_centroid_in_disc_implementation_fails():
    """A long, thin rectangle whose CENTROID sits outside the disc but whose
    polygon still overlaps it: a centroid-in-disc implementation would assign
    it zero weight; exact intersection must not."""
    disc = opa.disc_polygon((0.0, 0.0), radius_m=10.0, quad_segs=64)
    rect = box(-5.0, -2.0, 60.0, 2.0)

    centroid_dist = math.hypot(rect.centroid.x, rect.centroid.y)
    assert centroid_dist > 10.0, "test setup: centroid must be OUTSIDE the disc"

    areas = opa.cell_intersection_areas([rect], disc)
    assert areas[0] > 0.0, (
        "exact intersection must be > 0 even though the cell's centroid is "
        "outside the disc -- a centroid-in-disc implementation would fail this")


# ---------------------------------------------------------------------------
# 5. thickness weighting
# ---------------------------------------------------------------------------
def test_thickness_weighting_changes_the_result():
    center = (0.0, 0.0)
    polys, cx, cy = _regular_grid(5.0)
    n = len(polys)
    field = np.linspace(1.0, 2.0, n)  # arbitrary distinct per-cell values
    top = np.full(n, 10.0)
    heads = np.full(n, 10.0)  # saturated to top everywhere -> b_sat = top - botm
    botm_thin = np.full(n, 5.0)   # b_sat = 5 m everywhere
    botm_thick = botm_thin.copy()
    # deepen botm (thicken the saturated zone) at ONE cell nearest the centre
    i0 = int(np.argmin(cx ** 2 + cy ** 2))
    botm_thick[i0] = 0.0  # b_sat there becomes 10 m instead of 5 m

    r_thin = opa.compute_operator_a(
        cell_polygons=polys, heads=heads, top=top, botm=botm_thin, porosity=1.0,
        get_concentration=lambda t: field, times=[0.0], cell_size_m=5.0,
        center_xy=center)
    r_thick = opa.compute_operator_a(
        cell_polygons=polys, heads=heads, top=top, botm=botm_thick, porosity=1.0,
        get_concentration=lambda t: field, times=[0.0], cell_size_m=5.0,
        center_xy=center)
    assert r_thin.values[0] != pytest.approx(r_thick.values[0], rel=1e-9)


# ---------------------------------------------------------------------------
# 6. cells outside the disc have no influence
# ---------------------------------------------------------------------------
def test_cell_outside_the_disc_has_no_influence():
    center = (0.0, 0.0)
    polys, cx, cy = _regular_grid(5.0)
    n = len(polys)
    outside = np.where(cx ** 2 + cy ** 2 > (opa.RADIUS_M + 20.0) ** 2)[0]
    assert outside.size > 0
    field = np.ones(n)
    baseline = opa.compute_operator_a(
        cell_polygons=polys, heads=np.ones(n), top=np.ones(n), botm=np.zeros(n),
        porosity=1.0, get_concentration=lambda t: field, times=[0.0],
        cell_size_m=5.0, center_xy=center)

    mutated = field.copy()
    mutated[outside[0]] = 999.0
    after = opa.compute_operator_a(
        cell_polygons=polys, heads=np.ones(n), top=np.ones(n), botm=np.zeros(n),
        porosity=1.0, get_concentration=lambda t: mutated, times=[0.0],
        cell_size_m=5.0, center_xy=center)
    assert after.values[0] == pytest.approx(baseline.values[0], rel=1e-12)


# ---------------------------------------------------------------------------
# 7. applicability
# ---------------------------------------------------------------------------
def test_not_applicable_when_cell_size_exceeds_radius():
    assert opa.is_applicable(50.0, radius_m=25.0) is False
    record = opa.compute_operator_a(
        cell_polygons=[], heads=[], top=[], botm=[], porosity=0.2,
        get_concentration=lambda t: [], times=[0.0], cell_size_m=50.0,
        center_xy=(0.0, 0.0))
    assert record.status == "not_applicable"
    assert record.times == ()
    assert record.values == ()
    assert record.reason and "50" in record.reason


def test_applicable_at_equality_and_just_below():
    assert opa.is_applicable(25.0, radius_m=25.0) is True     # equality
    assert opa.is_applicable(24.999, radius_m=25.0) is True   # just below
    assert opa.is_applicable(25.001, radius_m=25.0) is False  # just above

    single = tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=20.0),))
    assert opa.cell_size_from_mesh_spec(single) == pytest.approx(20.0)

    multi = tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=20.0),
                                  tsd.MeshLevel(cell_size=5.0, radius_m=30.0)))
    with pytest.raises(NotImplementedError):
        opa.cell_size_from_mesh_spec(multi)


# ---------------------------------------------------------------------------
# 8. payload/meta hygiene
# ---------------------------------------------------------------------------
def test_no_new_payload_or_meta_field():
    field_names = {f.name for f in dataclasses.fields(tsd.SrcPulseDemo)}
    assert "observation_support_robustness" not in field_names
    assert not any("operator_a" in name for name in field_names)

    source = Path(tsd.__file__).read_text()
    assert "observation_support_robustness" not in source
    assert "operator_a_disc_v1" not in source


# ---------------------------------------------------------------------------
# 9. saturated thickness, not layer thickness
# ---------------------------------------------------------------------------
def test_saturated_thickness_not_layer_thickness():
    heads = np.array([12.0, 8.0, -50.0])   # above top / below top / dry (below botm)
    top = np.array([10.0, 10.0, 10.0])
    botm = np.array([0.0, 0.0, 0.0])
    b_sat = opa.saturated_thickness(heads, top, botm)
    # cell 0: head above top -> clipped to top -> b_sat == top - botm == 10.0
    assert b_sat[0] == pytest.approx(10.0)
    # cell 1: head below top -> b_sat == head - botm == 8.0, LESS than top - botm
    assert b_sat[1] == pytest.approx(8.0)
    assert b_sat[1] < (top[1] - botm[1])
    # cell 2: dry -> zero, never negative
    assert b_sat[2] == pytest.approx(0.0)

    naive_layer_thickness = top - botm  # the WRONG formula the brief bars
    assert not np.allclose(b_sat, naive_layer_thickness)


# ---------------------------------------------------------------------------
# 10. heterogeneous porosity
# ---------------------------------------------------------------------------
def test_heterogeneous_porosity_changes_the_result():
    center = (0.0, 0.0)
    polys, cx, cy = _regular_grid(5.0)
    n = len(polys)
    field = np.linspace(1.0, 2.0, n)
    heads = np.ones(n)
    top = np.ones(n)
    botm = np.zeros(n)

    uniform = opa.compute_operator_a(
        cell_polygons=polys, heads=heads, top=top, botm=botm, porosity=0.2,
        get_concentration=lambda t: field, times=[0.0], cell_size_m=5.0,
        center_xy=center)

    hetero = np.full(n, 0.2)
    i0 = int(np.argmin(cx ** 2 + cy ** 2))
    hetero[i0] = 0.35
    varied = opa.compute_operator_a(
        cell_polygons=polys, heads=heads, top=top, botm=botm, porosity=hetero,
        get_concentration=lambda t: field, times=[0.0], cell_size_m=5.0,
        center_xy=center)
    assert varied.values[0] != pytest.approx(uniform.values[0], rel=1e-9)


# ---------------------------------------------------------------------------
# 11. zero denominator raises
# ---------------------------------------------------------------------------
def test_zero_denominator_raises():
    center = (0.0, 0.0)
    polys, cx, cy = _regular_grid(5.0)
    n = len(polys)
    field = np.ones(n)
    # every cell is dry: head == botm everywhere -> b_sat == 0 everywhere
    heads = np.zeros(n)
    top = np.ones(n)
    botm = np.zeros(n)
    with pytest.raises(ValueError):
        opa.compute_operator_a(
            cell_polygons=polys, heads=heads, top=top, botm=botm, porosity=0.2,
            get_concentration=lambda t: field, times=[0.0], cell_size_m=5.0,
            center_xy=center)


# ---------------------------------------------------------------------------
# 12. no solve
# ---------------------------------------------------------------------------
def test_operator_a_invokes_no_solve(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("operator A must never trigger an MF6 solve")

    monkeypatch.setattr(flopy.mf6.MFSimulation, "run_simulation", _boom)

    center = (0.0, 0.0)
    polys, cx, cy = _regular_grid(5.0)
    n = len(polys)
    field = np.ones(n)
    record = opa.compute_operator_a(
        cell_polygons=polys, heads=np.ones(n), top=np.ones(n), botm=np.zeros(n),
        porosity=0.2, get_concentration=lambda t: field, times=[0.0, 1.0],
        cell_size_m=5.0, center_xy=center)
    assert record.status == "computed"


# ---------------------------------------------------------------------------
# 13. exactly one concentration read per output time
# ---------------------------------------------------------------------------
def test_one_concentration_read_per_output_time():
    center = (0.0, 0.0)
    polys, cx, cy = _regular_grid(5.0)
    n = len(polys)
    field = np.ones(n)
    times = [0.0, 1.0, 2.5, 10.0]
    calls = []

    def _get(t):
        calls.append(t)
        return field

    record = opa.compute_operator_a(
        cell_polygons=polys, heads=np.ones(n), top=np.ones(n), botm=np.zeros(n),
        porosity=0.2, get_concentration=_get, times=times, cell_size_m=5.0,
        center_xy=center)
    assert record.status == "computed"
    assert calls == [float(t) for t in times]
    assert len(calls) == len(times)


# ---------------------------------------------------------------------------
# 14. warm-cache path
# ---------------------------------------------------------------------------
def test_warm_cache_path_records_a_status_not_a_crash(tmp_path):
    """`build_srcpulse_demo` returns from its warm cache before any grid or
    concentration field exists (transport_srcpulse_demo.py ~:1198-1201) --
    demonstrated here the same way the existing cache tests do (see
    `test_cache_string_param_round_trips_and_busts`
    in test_transport_srcpulse_demo.py): a synthetic `SrcPulseDemo` round-trips
    through `_save_cache`/`_load_cache` with NO grid, NO modelgrid, NO
    concentration file involved at all."""
    dummy = tsd.SrcPulseDemo(
        times=np.array([0.0, 1.0]), breakthrough=np.array([0.0, 1.0]),
        peak_mgL=1.0, arrival_day=1.0, mass_balance={"a": 1.0}, solubility_ok=True,
        emergent_C_mgL=1.0, solubility_mgL=1.0, solubility_margin=1.0,
        PeL_min=1.0, PeL_max=1.0, PeT_min=1.0, PeT_max=1.0,
        mass_g=1.0, pulse_days=1.0, total_days=2.0, smassrate_gpd=1.0,
        src_cells=[0], ext_cell=1, inj_cell=2, spill_xy=(0.0, 0.0),
        alpha_L=10.0, alpha_T=1.0, R=1.0, rho_b=1800.0, Kd=0.0, lam=0.0,
        meta={"k": "v"}, locked=dict(tsd.LOCKED_PARAMS))
    cache_path = tmp_path / "warm_cache.npz"
    params = {"mass_g": 1.0, "src_sha": "abc123"}
    tsd._save_cache(cache_path, dummy, params)

    cached = tsd._load_cache(cache_path, params)
    assert cached is not None  # this IS the warm-cache hit: no grid was rebuilt

    # the primitive S6 provides for exactly this situation
    record = opa.status_for_missing_run_materials(center_xy=tsd.ABS_XY)
    assert record.status == "not_applicable"
    assert record.times == ()
    assert record.values == ()
    assert record.reason
    assert "cache" in record.reason.lower()
    # distinct from the cell-size-rule reason, so a reader can tell them apart
    assert "cell size" not in record.reason.lower()


# ---------------------------------------------------------------------------
# 15. artifact round trip
# ---------------------------------------------------------------------------
def test_artifact_round_trip_preserves_series_and_status(tmp_path):
    computed = opa.computed_record([1.0, 2.0, 3.0], [0.1, 0.2, 0.15],
                                    center_xy=tsd.ABS_XY)
    record = tea.build_fixture_record(
        run_role="spatial_series",
        diagnostics={"observation_support_robustness": computed})

    path = tmp_path / "evidence_record.json"
    tea.write_record(record, path)
    loaded = tea.load_record(path)

    loaded_diag = loaded.diagnostics["observation_support_robustness"]
    assert loaded_diag.status == "computed"
    assert loaded_diag.times == (1.0, 2.0, 3.0)
    assert loaded_diag.values == (0.1, 0.2, 0.15)
    assert loaded_diag.label == "observation_support_robustness"
    assert loaded_diag.reason is None

    not_applicable = opa.not_applicable_record(
        "cell size 50 m exceeds operator A's 25 m disc radius", center_xy=tsd.ABS_XY)
    record2 = tea.build_fixture_record(
        run_role="spatial_series",
        diagnostics={"observation_support_robustness": not_applicable})
    path2 = tmp_path / "evidence_record_na.json"
    tea.write_record(record2, path2)
    loaded2 = tea.load_record(path2)
    loaded_diag2 = loaded2.diagnostics["observation_support_robustness"]
    assert loaded_diag2.status == "not_applicable"
    assert loaded_diag2.times == ()
    assert loaded_diag2.values == ()
    assert loaded_diag2.reason
