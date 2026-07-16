"""Tests for transport_prt_capture (forward PRT spill-footprint -> capture demo).

Three physics variants are built once each, in a session-scoped ISOLATED tmp
workspace (see the `case_ws` fixture), via module-scoped fixtures:

  * `capture` -- the SPILL FOOTPRINT rung (release_radius_m = 10 m, the realistic
    footprint).  Measured: capture fraction 1.000 -- the entire footprint sits
    inside the capture zone.
  * `wide`    -- the CAPTURE-ZONE probe (release_radius_m = 120 m =
    `WIDE_RELEASE_RADIUS_M`).  Measured: capture fraction 0.719.
  * `wider`   -- the SAME flow field probed with a 200 m disc.  It exists for one
    reason: to prove that `max_captured_offset_m` MOVES with the probe (82.9 m ->
    86.9 m) while the real, bisected `halfwidth_at_spill_m` does NOT (78.9 m in
    both).  That contrast is the point of the whole lateral rung.

The isolated workspace is COLD at session start, so these are real MF6 solves
(steady GWF + PRT), not cache hits against a pre-warmed ambient workspace.  Do
NOT drop `case_ws=`: without it `build_prt_capture(..., force=False)` falls
through to the AMBIENT user-home workspace
(`~/applied_groundwater_modelling_data/limmat/transport_prt_capture`), which may
sit pre-warmed with stale `.npz` caches from notebook use -- the suite would then
run ZERO solves and pass green even against a broken model.  (That hole was just
closed in the ADE demo's tests; it must not come back here.)

Run with:  uv run pytest _SUPPORT/tests/test_transport_prt_capture.py
Use `-m "not slow"` for only the fast, solve-free tests.
"""
import dataclasses
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_prt_capture as tpc  # noqa: E402

N_PARTICLES = 200
FOOTPRINT_RADIUS_M = 10.0                      # realistic spill footprint
WIDE_RADIUS_M = tpc.WIDE_RELEASE_RADIUS_M      # 120 m -- straddles the capture zone
WIDER_RADIUS_M = 200.0                         # same flow field, a bigger probe
TRACK_DAYS = 730.0


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def case_ws(tmp_path_factory):
    """Isolated, COLD workspace shared by every physics fixture in this session."""
    return tmp_path_factory.mktemp("prt_capture_ws")


@pytest.fixture(scope="module")
def capture(case_ws):
    """The spill-footprint rung (10 m disc); solved once for the module."""
    return tpc.build_prt_capture(
        n_particles=N_PARTICLES, release_radius_m=FOOTPRINT_RADIUS_M,
        track_days=TRACK_DAYS, case_ws=case_ws, force=False)


@pytest.fixture(scope="module")
def wide(case_ws):
    """The capture-zone probe (120 m disc); solved once for the module."""
    return tpc.build_prt_capture(
        n_particles=N_PARTICLES, release_radius_m=WIDE_RADIUS_M,
        track_days=TRACK_DAYS, case_ws=case_ws, force=False)


@pytest.fixture(scope="module")
def wider(case_ws):
    """The SAME flow field probed with a 200 m disc (the stability control)."""
    return tpc.build_prt_capture(
        n_particles=N_PARTICLES, release_radius_m=WIDER_RADIUS_M,
        track_days=TRACK_DAYS, case_ws=case_ws, force=False)


def _perp_offsets(res, xy):
    """Signed offsets of points `xy` (N,2) perpendicular to the spill->well axis."""
    u = np.asarray(res.axis_u, dtype=float)
    perp = np.array([-u[1], u[0]])
    d = np.asarray(xy, dtype=float) - np.asarray(res.spill_xy, dtype=float)
    return d[:, 0] * perp[0] + d[:, 1] * perp[1]


def _seepage_travel_time_from_gwf_budget(res, n_samples=91):
    """RE-DERIVE the spill->well advective travel time from the GWF BUDGET ALONE.

    Deliberately re-implemented here, from the MF6 files on disk, rather than reading
    `res.tt_flow_integral_d`: the whole point is to check PRT's particle integration
    against an INDEPENDENT computation of the same physics.  Opens the binary grid file
    for the cell centres, reads DATA-SPDIS (specific discharge) out of the cell-by-cell
    budget, forms the seepage velocity v = |q| / n_e with the LOCKED porosity, and
    integrates ds / v along the straight spill -> well axis.

    Returns (travel_time_d, path_averaged_velocity_mpd).
    """
    import flopy

    gwf_ws = Path(res.meta["gwf_ws"])
    grb = flopy.mf6.utils.MfGrdFile(str(gwf_ws / "gwf.disv.grb"))
    mg = grb.modelgrid
    xc = np.array(mg.xcellcenters).ravel()
    yc = np.array(mg.ycellcenters).ravel()

    cbc = flopy.utils.CellBudgetFile(str(gwf_ws / "gwf.cbc"))
    spd = cbc.get_data(text="DATA-SPDIS")[0]
    qx = np.asarray(spd["qx"], dtype=float)
    qy = np.asarray(spd["qy"], dtype=float)

    n_e = float(res.porosity)
    L = float(res.meta["spill_to_well_m"])
    ux, uy = res.axis_u
    s = np.linspace(0.0, L, n_samples)
    v = np.empty_like(s)
    for j, sj in enumerate(s):
        x = res.spill_xy[0] + sj * ux
        y = res.spill_xy[1] + sj * uy
        i = int(np.argmin((xc - x) ** 2 + (yc - y) ** 2))
        v[j] = math.hypot(qx[i], qy[i]) / n_e
    assert np.all(v > 0.0), "zero specific discharge on the spill->well axis"
    tt = float(np.trapezoid(1.0 / v, s))
    return tt, L / tt


# ---------------------------------------------------------------------------
# fast, solve-free tests
# ---------------------------------------------------------------------------
def test_release_disc_is_deterministic_and_geometric():
    """The release layout must be bit-stable: the result is CACHED and asserted on,
    so an unseeded RNG would make the cache identity a lie (same args, different
    particles).  `release_disc` is purely geometric -- prove it by re-calling it
    after perturbing numpy's global RNG state, and by calling it twice."""
    a = tpc.release_disc(100.0, 200.0, 10.0, 64)
    np.random.seed(1234)
    np.random.random(100)
    b = tpc.release_disc(100.0, 200.0, 10.0, 64)
    np.random.seed(999)
    np.random.random(7)
    c = tpc.release_disc(100.0, 200.0, 10.0, 64)
    np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(a, c)

    # every point inside the disc; point 0 EXACTLY on the centre (the on-axis
    # particle the physics-contrast test relies on); the outermost point reaches
    # (essentially) the full radius, so the disc is really sampled to its edge.
    r = np.hypot(a[:, 0] - 100.0, a[:, 1] - 200.0)
    assert r.max() <= 10.0 + 1e-9
    assert r[0] == pytest.approx(0.0, abs=1e-12)
    assert r.max() == pytest.approx(10.0, rel=1e-9)
    # equal-AREA spacing (r ~ sqrt(k)) rather than points piled at the centre:
    # half the points must lie beyond r = R/sqrt(2) (the median radius of a disc).
    assert (r > 10.0 / math.sqrt(2.0)).sum() == pytest.approx(32, abs=2)

    with pytest.raises(ValueError):
        tpc.release_disc(0.0, 0.0, 10.0, 0)


def test_invalid_inputs_rejected():
    """Out-of-range inputs raise ValueError BEFORE any MF6 work (so this is ~0 s
    and is deliberately not marked slow)."""
    with pytest.raises(ValueError):
        tpc.build_prt_capture(n_particles=3)
    with pytest.raises(ValueError):
        tpc.build_prt_capture(release_radius_m=0.0)
    with pytest.raises(ValueError):
        tpc.build_prt_capture(release_radius_m=-5.0)
    with pytest.raises(ValueError):
        tpc.build_prt_capture(track_days=0.0)
    with pytest.raises(ValueError):
        tpc.build_prt_capture(track_days=-1.0)
    # the half-width probe validates its own knobs the same way
    with pytest.raises(ValueError):
        tpc.capture_halfwidth_at(max_offset_m=0.0)
    with pytest.raises(ValueError):
        tpc.capture_halfwidth_at(tol_m=-1.0)
    with pytest.raises(ValueError):
        tpc.capture_halfwidth_at(n_scan=3)
    with pytest.raises(ValueError):
        tpc.capture_halfwidth_at(float("nan"))


def test_nan_inputs_rejected():
    """NaN/inf are TRANSPARENT to `<` / `<=` (every comparison is False for NaN),
    so without explicit math.isfinite guards a NaN would sail through validation,
    reach the model, and get baked into the cache key (json.dumps(nan) does not
    raise either).  All must be rejected up front."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            tpc.build_prt_capture(release_radius_m=bad)
        with pytest.raises(ValueError):
            tpc.build_prt_capture(track_days=bad)
        with pytest.raises(ValueError):
            tpc.build_prt_capture(n_particles=bad)


def test_src_sha_runs_for_real_and_tracks_every_model_source(tmp_path):
    """The module-source fingerprint must actually WORK -- not merely be monkeypatched.

    `test_module_source_change_busts_cache` below stands in for an edit by replacing
    `_src_sha` with a lambda, which means rewriting `_src_sha` as `return "constant"`
    would keep that test green while every warm cache silently served a stale model.
    So run the REAL `_src_sha()` here and require it to move when EITHER of the three
    source files the model is built from is edited on disk:

      * transport_prt_capture   -- the PRT model itself
      * transport_srcpulse_demo -- the doublet, the spill rule, the corridor refinement
      * model_io_utils          -- it BUILDS the refined grid (mio.build_refined_gwf_model);
                                   this one was MISSING, so an edit to grid generation
                                   left every warm cache valid while the grid moved.

    The same fingerprint gap existed in the ADE demo, so its `_src_sha` is checked here
    too.  Solve-free.  Each file is restored in a `finally`, and the digests are
    re-asserted equal to the baseline afterwards, so a failure cannot leave the working
    tree dirty unnoticed.
    """
    import model_io_utils as mio
    import transport_srcpulse_demo as tsd

    base_prt = tpc._src_sha()
    base_ade = tsd._src_sha()
    assert len(base_prt) == 16 and len(base_ade) == 16

    for mod in (tpc, tsd, mio):
        p = Path(mod.__file__)
        original = p.read_bytes()
        (tmp_path / p.name).write_bytes(original)          # belt-and-braces backup
        try:
            p.write_bytes(original + b"\n# a model-changing edit\n")
            assert tpc._src_sha() != base_prt, (
                f"editing {p.name} did NOT change transport_prt_capture's _src_sha(): "
                "an edited model would keep serving stale cached results")
            if mod is not tpc:
                assert tsd._src_sha() != base_ade, (
                    f"editing {p.name} did NOT change transport_srcpulse_demo's "
                    "_src_sha(): same bug, other module")
        finally:
            p.write_bytes(original)

    assert tpc._src_sha() == base_prt
    assert tsd._src_sha() == base_ade


def test_release_z_stays_below_the_water_table():
    """The layer is UNCONFINED (heads ~399 m under a top of 403-407 m), so the cell
    mid-depth 0.5*(top + botm) can sit ABOVE the water table -- i.e. release a particle
    into the unsaturated zone.  `_release_z` must clamp the top to the head.  Pure
    arithmetic, no solve."""
    flow = dict(top_a=np.array([403.0, 407.0, 400.0]),
                botm_a=np.array([380.0, 380.0, 380.0]),
                heads=np.array([399.0, 399.0, 405.0]))
    # UNCONFINED (head below top -- the real case here): z must be the mid-depth of the
    # SATURATED column, NOT of the cell.  The naive 0.5*(top + botm) would put cell 1's
    # release at 393.5 m, i.e. 5.5 m ABOVE the water table.
    assert tpc._release_z(flow, 0) == pytest.approx(0.5 * (399.0 + 380.0))
    assert tpc._release_z(flow, 1) == pytest.approx(0.5 * (399.0 + 380.0))
    assert tpc._release_z(flow, 1) < 0.5 * (407.0 + 380.0)      # the naive value is wrong
    # CONFINED (head above top): the cell mid-depth is already correct, so nothing moves
    assert tpc._release_z(flow, 2) == pytest.approx(0.5 * (400.0 + 380.0))
    # and in every case the release is strictly INSIDE the saturated column
    for c in range(3):
        z = tpc._release_z(flow, c)
        assert flow["botm_a"][c] < z < min(flow["top_a"][c], flow["heads"][c]) + 1e-9


def _dummy(**over):
    """A synthetic PrtCapture for the solve-free cache unit tests."""
    kw = dict(
        capture_fraction=0.5, n_particles=4, n_released=4, n_captured=2, n_escaped=2,
        tt_median_d=10.0, tt_p10_d=5.0, tt_p90_d=15.0, tt_min_d=4.0, tt_max_d=16.0,
        halfwidth_at_spill_m=78.9, asymptotic_halfwidth_m=108.1,
        max_captured_offset_m=6.0,
        v_prt_path_mpd=3.24, v_flow_qn_mpd=3.21, tt_flow_integral_d=28.0,
        arc_len_median_m=83.6,
        release_points=np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]),
        release_cells=np.array([1, 2, 3, 4], dtype=np.int64),
        endpoints=np.array([[9.0, 9.0, 10.0], [9.0, 9.0, 11.0],
                            [5.0, 5.0, 730.0], [5.0, 5.0, 730.0]]),
        end_cells=np.array([7, 7, 3, 4], dtype=np.int64),
        end_status=np.array([5, 5, 10, 10], dtype=np.int64),
        captured=np.array([True, True, False, False]),
        travel_times=np.array([10.0, 11.0, 730.0, 730.0]),
        arc_lengths=np.array([32.0, 35.0, 900.0, 910.0]),
        pathlines=np.array([[0.0, 0.0, 0.0, 0.0], [0.0, 10.0, 9.0, 9.0]]),
        spill_xy=(0.5, 0.5), axis_u=(1.0, 0.0), ext_cell=7, inj_cell=8,
        release_radius_m=10.0, track_days=730.0, stop_at_weak_sink=False,
        porosity=0.2, meta={"k": "v"}, locked=dict(tpc.LOCKED_PARAMS))
    kw.update(over)
    return tpc.PrtCapture(**kw)


def test_cache_string_param_round_trips_and_busts(tmp_path):
    """`src_sha` is a STRING cache-identity key.  `_load_cache`'s comparison loop
    falls back to `abs(float(stored) - float(v))` for keys with no special case --
    which would CRASH on a hex string.  Pin both halves: an identical string must
    HIT, a changed one must MISS (i.e. actually bust the cache).  Solve-free."""
    cache = tmp_path / "c.npz"
    params = {"n_particles": 4.0, "src_sha": "abc123deadbeef01"}
    tpc._save_cache(cache, _dummy(), params)

    hit = tpc._load_cache(cache, params)
    assert hit is not None
    assert hit.capture_fraction == pytest.approx(0.5)

    miss = tpc._load_cache(cache, {"n_particles": 4.0, "src_sha": "0000000000000000"})
    assert miss is None

    # a missing/extra key must not silently count as a match either
    assert tpc._load_cache(cache, {"n_particles": 4.0}) is None


def test_save_load_cache_restores_locked_exactly(tmp_path):
    """`locked` must round-trip from the SAVED snapshot, not be resurrected from
    the live global via the dataclass default_factory (a bug this repo shipped
    once).  Plant a `fake_locked` that differs from the live LOCKED_PARAMS so a
    resurrected default cannot coincidentally compare equal.  Solve-free."""
    fake_locked = dict(tpc.LOCKED_PARAMS)
    fake_locked["porosity"] = 0.123456
    assert fake_locked["porosity"] != tpc.LOCKED_PARAMS["porosity"]

    cache = tmp_path / "c.npz"
    params = {"n_particles": 4.0, "locked": fake_locked}
    tpc._save_cache(cache, _dummy(locked=fake_locked), params)
    restored = tpc._load_cache(cache, params)

    assert restored is not None
    assert restored.locked == fake_locked
    assert restored.locked["porosity"] != tpc.LOCKED_PARAMS["porosity"]


# ---------------------------------------------------------------------------
# physics (real MF6 solves)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_model_builds_and_runs(capture):
    """The steady GWF + PRT pair builds, runs, and returns a coherent fate census."""
    assert isinstance(capture, tpc.PrtCapture)
    assert capture.n_released > 0
    assert 0.0 < capture.capture_fraction <= 1.0

    # array shapes are all per-released-particle and mutually consistent
    n = capture.n_released
    assert capture.release_points.shape == (n, 2)
    assert capture.release_cells.shape == (n,)
    assert capture.endpoints.shape == (n, 3)
    assert capture.end_cells.shape == (n,)
    assert capture.end_status.shape == (n,)
    assert capture.captured.shape == (n,)
    assert capture.travel_times.shape == (n,)
    assert capture.arc_lengths.shape == (n,)
    # pathlines carry every particle, with >= 2 vertices each (release + terminate)
    assert capture.pathlines.ndim == 2 and capture.pathlines.shape[1] == 4
    assert set(capture.pathlines[:, 0].astype(int)) == set(range(n))
    assert capture.pathlines.shape[0] >= 2 * n

    # The RELEASE CELLS really are the cells the release points fall in.  PRT's PRP
    # packagedata is keyed on (cell, x, y), so a mis-paired (point, cell) would release
    # particles in the wrong place while every summary statistic still looked sane.
    # Re-derive the pairing independently, from the binary grid file on disk.
    import flopy
    grb = flopy.mf6.utils.MfGrdFile(
        os.path.join(capture.meta["gwf_ws"], "gwf.disv.grb"))
    xc = np.array(grb.modelgrid.xcellcenters).ravel()
    yc = np.array(grb.modelgrid.ycellcenters).ravel()
    for i in range(n):
        px, py = capture.release_points[i]
        nearest = int(np.argmin((xc - px) ** 2 + (yc - py) ** 2))
        assert capture.release_cells[i] == nearest, (
            f"release point {i} at ({px:.1f}, {py:.1f}) is paired with cell "
            f"{capture.release_cells[i]}, but falls in cell {nearest}")

    # the release disc really is centred on the ADE demo's spill location
    d = np.hypot(capture.release_points[:, 0] - capture.spill_xy[0],
                 capture.release_points[:, 1] - capture.spill_xy[1])
    assert d.max() <= capture.release_radius_m + 1e-6
    assert d.min() == pytest.approx(0.0, abs=1e-9)     # the on-axis centre particle


@pytest.mark.slow
def test_extraction_well_is_a_strong_sink(capture):
    """The load-bearing justification for the whole classification.

    CAPTURED is defined as "terminated in the EXTRACTION-well cell".  That is only
    equivalent to "captured by the well" because the well is a STRONG sink: every
    m^3/d that enters the cell across its faces leaves through the well, so a
    particle that enters the cell CANNOT leave it.  Pin that, rather than trusting
    it: if a future edit (a smaller Q, a coarser cell, a competing sink) made the
    well a WEAK sink, particles would pass straight through and the capture
    fraction would silently become meaningless."""
    assert capture.meta["ext_is_strong_sink"] is True
    # face inflow balances the pumping rate; face OUTflow is zero
    assert capture.meta["ext_inflow_m3d"] == pytest.approx(tpc.DOUBLET_Q, rel=0.01)
    assert capture.meta["ext_outflow_m3d"] == pytest.approx(0.0, abs=1e-6)
    # no particle is captured by the INJECTION well (it is a source, not a sink)
    assert not np.any(capture.end_cells == capture.inj_cell)


@pytest.mark.slow
def test_observed_mf6_istatus_codes(capture, wide):
    """Pin the OBSERVED MF6 6.7.0 istatus codes.

    The classification deliberately keys on the terminating CELL, not on istatus (a
    control run with ISTOPZONE terminates the same particles in the same cell but
    reports a different code).  This test does NOT make the code load-bearing -- it is
    a tripwire: if a future MF6 renumbers them, we want to be told, because the module
    docstring, the notebook prose and `meta["istatus_counts"]` all quote them.

      5  = terminated in a cell with no exit face  -> the strong-sink capture
      10 = the tracking window (stoptime) closed while the particle was still moving
    """
    assert set(capture.end_status[capture.captured].tolist()) == {5}
    assert set(wide.end_status[wide.captured].tolist()) == {5}
    assert set(wide.end_status[~wide.captured].tolist()) == {10}
    assert capture.meta["istatus_counts"] == {"5": capture.n_captured}
    assert wide.meta["istatus_counts"] == {"5": wide.n_captured,
                                           "10": wide.n_escaped}


@pytest.mark.slow
def test_stop_at_weak_sink_does_not_change_capture(capture, wide, case_ws):
    """VERIFY the `stop_at_weak_sink` (MF6 ISTOPWEAKSINK) choice instead of
    asserting it in prose.

    The module leaves it OFF.  If capture depended on that switch, the reported
    capture fraction would be a configuration artifact rather than a physical
    answer.  It does not: the extraction well is a STRONG sink, and MF6 terminates
    particles there either way.  Re-run BOTH rungs with the switch ON and require
    a bit-identical fate vector and identical travel times.

    What the switch DOES change is only where the ESCAPEES stop: with it OFF they
    run to the end of the tracking window (istatus 10); with it ON they terminate
    in the weak-sink RIV cells they were passing through (istatus 3).  Assert that
    contrast too -- it is what makes this test more than a no-op."""
    for base in (capture, wide):
        ws_on = tpc.build_prt_capture(
            n_particles=N_PARTICLES, release_radius_m=base.release_radius_m,
            track_days=TRACK_DAYS, stop_at_weak_sink=True, case_ws=case_ws,
            force=False)
        assert ws_on.stop_at_weak_sink is True
        assert ws_on.n_released == base.n_released
        np.testing.assert_array_equal(ws_on.captured, base.captured)
        assert ws_on.capture_fraction == pytest.approx(base.capture_fraction, rel=1e-12)
        np.testing.assert_allclose(ws_on.travel_times[ws_on.captured],
                                   base.travel_times[base.captured], rtol=1e-9)
        # captures terminate by the same (strong-sink) mechanism in both runs
        assert (set(ws_on.end_status[ws_on.captured].tolist())
                == set(base.end_status[base.captured].tolist()))

    # the escapees DO change mechanism (this is the switch actually doing something)
    ws_on_wide = tpc.build_prt_capture(
        n_particles=N_PARTICLES, release_radius_m=WIDE_RADIUS_M, track_days=TRACK_DAYS,
        stop_at_weak_sink=True, case_ws=case_ws, force=False)
    esc_off = set(wide.end_status[~wide.captured].tolist())
    esc_on = set(ws_on_wide.end_status[~ws_on_wide.captured].tolist())
    assert esc_off and esc_on
    assert esc_off != esc_on, (
        "stop_at_weak_sink=True did not change how the ESCAPED particles terminate; "
        f"off={esc_off} on={esc_on} -- the switch is being ignored, which would make "
        "the 'capture is invariant to it' conclusion above vacuous")


@pytest.mark.slow
def test_advection_engine_matches_the_flow_field_it_was_given(capture):
    """THE verification of the PRT rung -- and it is a real one.

    PRT's Lagrangian particle integration is checked against an INDEPENDENT Eulerian
    computation of the same physics: the seepage velocity v = |q| / n_e, with q read
    straight out of the GWF cell-by-cell budget (DATA-SPDIS) and n_e the locked
    porosity, integrated along the spill -> well axis.  Nothing in that path touches
    the particle tracker.

    Measured: the flow field's path-averaged v = 3.21 m/d and its travel-time integral
    = 28.0 d over the 90 m axis; PRT reports a path-averaged v of 3.24 m/d (median arc
    length 83.6 m / median travel time 25.8 d).  The velocities agree to ~1%.

    (This REPLACES the old `0.5 < v_implied < 20.0` "physics" check, which was a
    40x-wide band already implied by the regression pin below and therefore tested
    nothing, and the old PRT-vs-ADE "cross-validation", which was numerology: PRT's
    advective timescale and the ADE's day-41 CONCENTRATION peak are different
    quantities and no simple identity connects them in a converging 2-D field.)

    NOTE the reach of this check, honestly: PRT and the ADE demo share the SAME flow
    field, grid and porosity, so it verifies the PARTICLE TRACKER against the flow
    solution -- it cannot detect an error in the flow solution itself.  04t Section 5's
    2-D analytical benchmark is the track's end-to-end transport verification.
    """
    tt = capture.travel_times[capture.captured]
    assert tt.size == capture.n_captured > 0
    assert np.all(np.isfinite(tt))
    assert np.all(tt > 0.0), "a travel time of 0 d means a particle was released " \
                             "inside the extraction-well cell -- those must be dropped"
    assert capture.tt_min_d <= capture.tt_p10_d <= capture.tt_median_d \
        <= capture.tt_p90_d <= capture.tt_max_d
    # every particle terminates within the tracking window
    assert np.all(capture.travel_times <= capture.track_days + 1e-6)

    # ---- the INDEPENDENT prediction, re-derived here from the GWF budget files ----
    tt_flow, v_flow = _seepage_travel_time_from_gwf_budget(capture)

    # the module's own helper must agree with this independent re-derivation
    assert capture.tt_flow_integral_d == pytest.approx(tt_flow, rel=0.02)
    assert capture.v_flow_qn_mpd == pytest.approx(v_flow, rel=0.02)

    # (a) PRT's PATH-AVERAGED velocity vs the flow field's q/n.  This is the real
    #     comparison: the particles fly a CURVED path and terminate on entering the
    #     well CELL, so they travel ~83.6 m, not the straight 90 m axis -- dividing
    #     90 m by the travel time (as an earlier version did, giving "3.5 m/d") divides
    #     by a distance no particle travels.
    v_prt = float(np.median(capture.arc_lengths[capture.captured] / tt))
    assert capture.v_prt_path_mpd == pytest.approx(v_prt, rel=1e-9)
    assert capture.arc_len_median_m < capture.meta["spill_to_well_m"], (
        "PRT pathlines are not shorter than the straight spill->well axis; they should "
        "be, because they terminate on entering the well CELL, ~7 m short of the node")
    assert v_prt == pytest.approx(v_flow, rel=0.10), (
        f"PRT's path-averaged seepage velocity ({v_prt:.3f} m/d) disagrees with the "
        f"flow field's q/n ({v_flow:.3f} m/d) by more than 10%: the particle tracker "
        "is not reproducing the flow field it was handed")

    # (b) and the travel TIME itself, against the flow field's integral.  The tolerance
    #     is looser (rel=0.25) and deliberately so: the integral is taken over the full
    #     90 m straight axis while PRT stops at the well-cell face, so the integral is
    #     expected to run ~8% LONG (28.0 d vs 25.8 d).  A 25% band still fails hard on a
    #     wrong porosity (a factor of 2), wrong units, or a broken FMI hand-off.
    assert capture.tt_median_d == pytest.approx(tt_flow, rel=0.25)
    assert capture.tt_median_d < tt_flow, (
        "PRT's median travel time is not SHORTER than the axis integral; it should be, "
        "because PRT terminates at the well-cell face rather than at the well node")

    # REGRESSION PIN (measured): median 25.8 d, p10 22.7, p90 28.6; arc 83.6 m;
    # v_prt 3.24 m/d; v_flow 3.21 m/d; flow integral 28.0 d.
    assert capture.tt_median_d == pytest.approx(25.8, rel=0.05)
    assert capture.tt_p10_d == pytest.approx(22.7, rel=0.05)
    assert capture.tt_p90_d == pytest.approx(28.6, rel=0.05)
    assert capture.arc_len_median_m == pytest.approx(83.6, rel=0.05)
    assert capture.v_prt_path_mpd == pytest.approx(3.24, rel=0.05)
    assert capture.v_flow_qn_mpd == pytest.approx(3.21, rel=0.05)
    assert capture.tt_flow_integral_d == pytest.approx(28.0, rel=0.05)


@pytest.mark.slow
def test_spill_footprint_is_entirely_inside_the_capture_zone(capture):
    """The 10 m footprint rung: EVERY particle is captured (fraction exactly 1.0).

    That is the honest answer for this spill -- and it is also why the wider probes
    exist: a run where everything is captured says nothing about where the capture zone
    ENDS (see the next tests)."""
    assert capture.n_escaped == 0
    assert capture.capture_fraction == 1.0
    assert capture.meta["n_dropped_wellcell"] == 0    # 90 m away, 10 m disc
    # the widest captured release point is just the edge of the disc: at this radius
    # `max_captured_offset_m` is bounded by the PROBE, not by the capture zone -- which
    # is exactly why it is not a half-width.
    assert capture.max_captured_offset_m == pytest.approx(FOOTPRINT_RADIUS_M, rel=0.05)
    assert capture.max_captured_offset_m < capture.halfwidth_at_spill_m


@pytest.mark.slow
def test_capture_zone_boundary_on_axis_captured_off_axis_escapes(wide):
    """THE physics contrast: the 120 m probe straddles the capture-zone boundary, so the
    capture fraction is STRICTLY between 0 and 1.  A particle released on the spill ->
    well axis is captured; particles far enough OFF that axis are not."""
    assert 0.0 < wide.capture_fraction < 1.0
    assert wide.n_captured > 0 and wide.n_escaped > 0

    off = _perp_offsets(wide, wide.release_points)
    dist = np.hypot(wide.release_points[:, 0] - wide.spill_xy[0],
                    wide.release_points[:, 1] - wide.spill_xy[1])

    # (a) the particle AT the spill centre (on-axis) is CAPTURED
    i_centre = int(np.argmin(dist))
    assert dist[i_centre] == pytest.approx(0.0, abs=1e-9)
    assert bool(wide.captured[i_centre]) is True

    # (b) the MOST off-axis particle is NOT captured
    i_far = int(np.argmax(np.abs(off)))
    assert bool(wide.captured[i_far]) is False
    assert abs(off[i_far]) > 100.0

    # (c) captured particles are systematically closer to the axis than escapees
    assert np.abs(off[wide.captured]).mean() < np.abs(off[~wide.captured]).mean()

    # (d) but the two populations do NOT separate cleanly in |offset|: some escapees sit
    #     CLOSER to the axis than the widest captured point, because they are released
    #     DOWNGRADIENT of the well.  This is the evidence that `max_captured_offset_m`
    #     is a sampling statistic and not a boundary -- assert it, so nobody "fixes" the
    #     scatter plot by pretending the disc has a clean dividing line in |offset|.
    esc_min = float(np.abs(off[~wide.captured]).min())
    assert esc_min < wide.max_captured_offset_m, (
        "no escaped release point lies closer to the axis than the widest CAPTURED one; "
        "the disc's |offset| statistic would then look like a real boundary, which it "
        "is not -- re-check the geometry before trusting this test's premise")

    # measured: max captured offset 82.9 m, fraction 0.719 (143/199)
    assert wide.max_captured_offset_m == pytest.approx(82.9, rel=0.10)
    assert wide.capture_fraction == pytest.approx(0.72, abs=0.06)

    # release points inside the EXTRACTION-well cell are dropped (they would report a
    # 0 d travel time); at 120 m the disc reaches the well, so exactly this happens.
    # Points in the INJECTION-well cell would be KEPT (that well is a source, and such a
    # particle advects away normally); none occur at any radius used here.
    assert wide.meta["n_dropped_wellcell"] == 1
    assert wide.meta["n_released_in_injcell"] == 0
    assert wide.n_released == wide.n_particles - wide.meta["n_dropped_wellcell"]
    assert not np.any(wide.release_cells == wide.ext_cell)
    assert np.all(wide.travel_times[wide.captured] > 0.0)


@pytest.mark.slow
def test_halfwidth_is_stable_across_probe_radii_but_max_offset_is_not(capture, wide, wider):
    """FIX B, and the whole reason `halfwidth_at_spill_m` exists.

    `max_captured_offset_m` -- "the most off-axis release point that happened to be
    captured in this disc" -- is a SAMPLING STATISTIC.  It moves with the probe radius
    in an UNCHANGED flow field (measured 82.9 m at r = 120 m, 86.9 m at r = 200 m), and
    the point that sets it can sit tens of metres UPGRADIENT of the spill rather than on
    the spill transect.  It is a lower bound, not a capture-zone half-width.

    `halfwidth_at_spill_m` is the real thing: the captured/escaped boundary BISECTED on
    the transect through the spill.  It is a property of the FLOW FIELD, so it must be
    IDENTICAL across all three probes -- the flow field is the same in all of them.
    That invariance is the convergence check the old number could never pass.
    """
    # the three probes really do share one flow field ...
    assert capture.meta["ncpl"] == wide.meta["ncpl"] == wider.meta["ncpl"]
    assert capture.meta["gwf_ws"] == wide.meta["gwf_ws"] == wider.meta["gwf_ws"]
    assert capture.spill_xy == wide.spill_xy == wider.spill_xy

    # ... so the REAL half-width is bit-identical across them
    assert wide.halfwidth_at_spill_m == pytest.approx(
        capture.halfwidth_at_spill_m, abs=1e-9)
    assert wider.halfwidth_at_spill_m == pytest.approx(
        capture.halfwidth_at_spill_m, abs=1e-9)
    # measured: 78.9 m (+81.4 / -76.4), bisected to 0.5 m
    assert capture.halfwidth_at_spill_m == pytest.approx(78.9, rel=0.05)
    assert capture.meta["halfwidth_s_m"] == 0.0            # AT the spill transect
    assert capture.meta["halfwidth_scan_contiguous"] is True
    assert capture.meta["halfwidth_plus_m"] == pytest.approx(81.4, rel=0.05)
    assert capture.meta["halfwidth_minus_m"] == pytest.approx(76.4, rel=0.05)
    # the two sides differ -- the zone is NOT symmetric about the axis (the injection
    # well sits off to one side), which a single symmetric "half-width" would hide
    assert capture.meta["halfwidth_plus_m"] != pytest.approx(
        capture.meta["halfwidth_minus_m"], rel=1e-3)

    # ... while `max_captured_offset_m` DOES move, in that same unchanged flow field
    assert wider.max_captured_offset_m != pytest.approx(
        wide.max_captured_offset_m, rel=0.02), (
        "max_captured_offset_m did not move between a 120 m and a 200 m probe; the "
        "premise of this whole rename (that it is a probe artifact) needs re-checking")
    assert wider.max_captured_offset_m == pytest.approx(86.9, rel=0.10)

    # and the capture FRACTION is likewise a property of the probe disc, not the doublet
    assert wider.capture_fraction < wide.capture_fraction < capture.capture_fraction


@pytest.mark.slow
def test_halfwidth_probe_converges_and_widens_upgradient(case_ws):
    """The bisected half-width must not move when the PROBE's own settings move (that is
    what "converged" means), and it must reproduce the FLOW FIELD's analytic asymptote
    far upgradient.

    (a) CONVERGENCE: at the spill transect, vary the bisection's max offset, scan
        density and tolerance.  All must return 78.9 m.
    (b) PHYSICS: the capture zone WIDENS upgradient (78.9 m at the spill -> ~112 m at
        300 m upgradient) and converges on the analytic asymptote y_max = Q / (2 q b)
        ~= 108 m read from the GWF budget -- the same screening formula 01t writes as
        Q / (2 T i).  Two completely different computations of the same number.
    """
    base = tpc.capture_halfwidth_at(0.0, case_ws=case_ws)
    assert base["scan_contiguous"] is True
    assert base["halfwidth_m"] == pytest.approx(78.9, rel=0.05)

    for kw in (dict(max_offset_m=200.0, n_scan=41),
               dict(max_offset_m=120.0, n_scan=25),
               dict(tol_m=0.25, n_scan=37, max_offset_m=180.0)):
        alt = tpc.capture_halfwidth_at(0.0, case_ws=case_ws, **kw)
        assert alt["halfwidth_m"] == pytest.approx(base["halfwidth_m"], abs=1.0), (
            f"the bisected half-width moved with the probe settings {kw}: "
            f"{alt['halfwidth_m']:.2f} vs {base['halfwidth_m']:.2f} m -- it is not "
            "converged, and would be no better than the max-offset statistic it replaced")

    far = tpc.capture_halfwidth_at(-300.0, case_ws=case_ws, max_offset_m=200.0, n_scan=41)
    assert far["scan_contiguous"] is True
    assert far["halfwidth_m"] > base["halfwidth_m"] + 20.0, (
        "the capture zone does not widen upgradient of the spill; it must -- the "
        "streamtube that ends at the well is narrowest where the flow is fastest")
    assert far["halfwidth_m"] == pytest.approx(112.0, rel=0.10)

    # the analytic asymptote, from the GWF budget's regional q*b
    assert base["asymptotic_halfwidth_m"] == pytest.approx(108.0, rel=0.10)
    assert base["regional_qb_m2d"] == pytest.approx(6.3, rel=0.10)
    # the numeric half-width AT THE SPILL is NARROWER than the far-field asymptote ...
    assert base["halfwidth_m"] < base["asymptotic_halfwidth_m"]
    # ... and the far-upgradient one has essentially reached it
    assert far["halfwidth_m"] == pytest.approx(base["asymptotic_halfwidth_m"], rel=0.15)


# ---------------------------------------------------------------------------
# cache identity / fidelity (real solves)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_cache_round_trip_fidelity(tmp_path):
    """A fresh solve and a cache-hit re-call with IDENTICAL args must return
    dataclass objects that are equal field-for-field, with identical TYPES.

    Two distinct guards, both needed:
      (a) the npz key-set assertion -- default-factory-proof, because it compares
          the literal set of arrays written to disk against the full set of
          dataclass field names.  A dropped field (silently resurrected from a
          default_factory, a bug this repo shipped once) cannot hide from it,
          whereas the value loop below WOULD miss it: build and cache would both
          fall back to the same default and compare equal.
      (b) the value + type loop -- pins that no field mutates through the round
          trip (tuple -> ndarray, float -> np.float64, int -> np.int64, ...).
    """
    ws = tmp_path / "prt_ws"
    fresh = tpc.build_prt_capture(n_particles=32, release_radius_m=FOOTPRINT_RADIUS_M,
                                  track_days=TRACK_DAYS, case_ws=ws, force=True)
    cached = tpc.build_prt_capture(n_particles=32, release_radius_m=FOOTPRINT_RADIUS_M,
                                   track_days=TRACK_DAYS, case_ws=ws, force=False)

    caches = list(ws.glob("prtcapture_cache_*.npz"))
    assert len(caches) == 1
    z = np.load(str(caches[0]), allow_pickle=True)
    saved = set(z.files) - {"params"}
    expected = {f.name for f in dataclasses.fields(tpc.PrtCapture)}
    assert saved == expected, f"npz fields {saved} != dataclass fields {expected}"

    for f in dataclasses.fields(tpc.PrtCapture):
        fv, cv = getattr(fresh, f.name), getattr(cached, f.name)
        if isinstance(fv, np.ndarray):
            np.testing.assert_array_equal(cv, fv, err_msg=f"field {f.name!r} mismatch")
            assert cv.dtype == fv.dtype, (
                f"field {f.name!r} dtype mismatch: fresh={fv.dtype} cached={cv.dtype}")
        else:
            assert cv == fv, f"field {f.name!r} mismatch: fresh={fv!r} cached={cv!r}"
            assert type(cv) is type(fv), (
                f"field {f.name!r} type mismatch: fresh={type(fv)} cached={type(cv)}")
            if isinstance(fv, (tuple, list)):
                assert [type(x) for x in cv] == [type(x) for x in fv], (
                    f"field {f.name!r} element-type mismatch: "
                    f"fresh={[type(x) for x in fv]} cached={[type(x) for x in cv]}")


@pytest.mark.slow
def test_mf6_workspaces_are_per_variant_and_not_stale(capture, wide, case_ws):
    """FIX F5: every variant must own its MF6 directories.

    The PRT workspace used to be a single shared `case_ws/"prt"`, so each new variant
    OVERWROTE the previous one's files while `meta["prt_ws"]` kept pointing at the (now
    wrong) directory -- a cached r=10 result would hand you a path whose track file on
    disk held some later r=200 run.  Anyone who trusted `meta["prt_ws"]` (to re-plot, to
    debug, to check a residual) read the wrong model.

    The GWF directory, by contrast, is keyed on the FLOW identity alone -- it is
    legitimately SHARED between variants that differ only on the PRT side, because the
    flow solution is bit-identical for them.  Shared-but-identical is not stale.
    """
    assert Path(capture.meta["prt_ws"]).name != Path(wide.meta["prt_ws"]).name
    assert capture.meta["gwf_ws"] == wide.meta["gwf_ws"]      # same flow -> same dir

    # each variant's OWN track file, on disk, holds ITS OWN particles
    import pandas as pd
    for res in (capture, wide):
        trk = pd.read_csv(Path(res.meta["prt_ws"]) / "prt.trk.csv")
        assert trk["irpt"].nunique() == res.n_released, (
            f"the track file at meta['prt_ws'] for r={res.release_radius_m:.0f} m holds "
            f"{trk['irpt'].nunique()} particles, not the {res.n_released} this result "
            "reports -- the workspace is stale (another variant overwrote it)")

    # a variant that differs only in stop_at_weak_sink also gets its own PRT dir
    ws_on = tpc.build_prt_capture(
        n_particles=N_PARTICLES, release_radius_m=FOOTPRINT_RADIUS_M,
        track_days=TRACK_DAYS, stop_at_weak_sink=True, case_ws=case_ws, force=False)
    assert ws_on.meta["prt_ws"] != capture.meta["prt_ws"]
    assert ws_on.meta["gwf_ws"] == capture.meta["gwf_ws"]     # same flow, again


@pytest.mark.slow
def test_locked_params_change_busts_cache(tmp_path, monkeypatch):
    """Editing LOCKED_PARAMS must NOT be masked by a warm cache.  Porosity feeds
    the PRT MIP package directly (v = q / n_e), so a stale cache here would return
    travel times for the WRONG aquifer while reporting the new porosity."""
    ws = tmp_path / "prt_ws_locked"
    baseline = tpc.build_prt_capture(n_particles=32, release_radius_m=FOOTPRINT_RADIUS_M,
                                     track_days=TRACK_DAYS, case_ws=ws, force=True)
    baseline_caches = set(ws.glob("prtcapture_cache_*.npz"))
    assert len(baseline_caches) == 1

    patched = dict(tpc.LOCKED_PARAMS)
    patched["porosity"] = tpc.LOCKED_PARAMS["porosity"] * 2.0
    monkeypatch.setattr(tpc, "LOCKED_PARAMS", patched)

    changed = tpc.build_prt_capture(n_particles=32, release_radius_m=FOOTPRINT_RADIUS_M,
                                    track_days=TRACK_DAYS, case_ws=ws, force=False)

    changed_caches = set(ws.glob("prtcapture_cache_*.npz"))
    assert changed_caches != baseline_caches
    assert len(changed_caches) == 2
    # the rebuild really used the new porosity ...
    assert changed.locked["porosity"] == pytest.approx(patched["porosity"])
    assert changed.porosity == pytest.approx(patched["porosity"])
    # ... and the PHYSICS moved: doubling the porosity halves the seepage velocity,
    # so advective travel times double.  (A stale cache hit would return the old
    # times unchanged -- this is what actually catches the bug.)
    assert changed.tt_median_d == pytest.approx(2.0 * baseline.tt_median_d, rel=0.02)
    # and the flow-field cross-check follows it, because it uses the same n_e
    assert changed.v_prt_path_mpd == pytest.approx(0.5 * baseline.v_prt_path_mpd, rel=0.02)
    assert changed.v_flow_qn_mpd == pytest.approx(0.5 * baseline.v_flow_qn_mpd, rel=1e-6)


@pytest.mark.slow
def test_module_source_change_busts_cache(tmp_path, monkeypatch):
    """Editing the module SOURCE must bust the cache.

    This stands in for an edit by monkeypatching `_src_sha` -- which is exactly why
    `test_src_sha_runs_for_real_and_tracks_every_model_source` (above, solve-free) also
    exists: without it, rewriting `_src_sha` as `return "constant"` would keep THIS test
    green while every warm cache served a stale model."""
    ws = tmp_path / "prt_ws_src"
    tpc.build_prt_capture(n_particles=32, release_radius_m=FOOTPRINT_RADIUS_M,
                          track_days=TRACK_DAYS, case_ws=ws, force=True)
    before = set(ws.glob("prtcapture_cache_*.npz"))
    assert len(before) == 1

    monkeypatch.setattr(tpc, "_src_sha", lambda: "deadbeefdeadbeef")

    tpc.build_prt_capture(n_particles=32, release_radius_m=FOOTPRINT_RADIUS_M,
                          track_days=TRACK_DAYS, case_ws=ws, force=False)
    after = set(ws.glob("prtcapture_cache_*.npz"))
    assert after != before
    assert len(after) == 2, ("the module-source fingerprint did not bust the cache: "
                             "an edited model would keep serving stale results")


@pytest.mark.slow
def test_cache_is_per_variant_no_cross_contamination(capture, wide, case_ws):
    """Re-calling with the FIRST param set after a different variant was solved must
    return the FIRST run's cached numbers, not the second's.  Solve-free: both
    variants are already cached by the fixtures (and this re-uses the SAME isolated
    `case_ws`, so it cannot silently land in a cold directory and solve again)."""
    assert wide.release_radius_m != capture.release_radius_m
    assert wide.capture_fraction != pytest.approx(capture.capture_fraction, rel=1e-6)

    recalled = tpc.build_prt_capture(
        n_particles=N_PARTICLES, release_radius_m=FOOTPRINT_RADIUS_M,
        track_days=TRACK_DAYS, case_ws=case_ws, force=False)
    assert recalled.capture_fraction == pytest.approx(capture.capture_fraction, rel=1e-12)
    assert recalled.tt_median_d == pytest.approx(capture.tt_median_d, rel=1e-12)
    assert recalled.n_captured == capture.n_captured
    np.testing.assert_array_equal(recalled.captured, capture.captured)
