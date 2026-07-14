"""Tests for transport_prt_capture (forward PRT spill-footprint -> capture demo).

Two physics variants are built once each, in a session-scoped ISOLATED tmp
workspace (see the `case_ws` fixture), via module-scoped fixtures:

  * `capture` -- the SPILL FOOTPRINT rung (release_radius_m = 10 m, the realistic
    footprint).  Measured: capture fraction 1.000 -- the entire footprint sits
    inside the capture zone.
  * `wide`    -- the CAPTURE-ZONE rung (release_radius_m = 120 m =
    `WIDE_RELEASE_RADIUS_M`).  Measured: capture fraction 0.719 -- strictly
    between 0 and 1, so it actually resolves where the capture zone ENDS.  A rung
    where everything is captured teaches nothing about a capture zone, which is
    exactly why this second rung exists.

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

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_prt_capture as tpc  # noqa: E402

N_PARTICLES = 200
FOOTPRINT_RADIUS_M = 10.0                      # realistic spill footprint
WIDE_RADIUS_M = tpc.WIDE_RELEASE_RADIUS_M      # 120 m -- straddles the capture zone
TRACK_DAYS = 730.0

# The ADE demo's answer to the OTHER question (transport_srcpulse_demo):
# peak CONCENTRATION 4.95 mg/L at day 41, from a finite 30-day pulse.
ADE_PEAK_DAY = 41.0
ADE_PULSE_DAYS = 30.0


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
    """The capture-zone rung (120 m disc); solved once for the module."""
    return tpc.build_prt_capture(
        n_particles=N_PARTICLES, release_radius_m=WIDE_RADIUS_M,
        track_days=TRACK_DAYS, case_ws=case_ws, force=False)


def _perp_offsets(res, xy):
    """Signed offsets of points `xy` (N,2) perpendicular to the spill->well axis."""
    u = np.asarray(res.axis_u, dtype=float)
    perp = np.array([-u[1], u[0]])
    d = np.asarray(xy, dtype=float) - np.asarray(res.spill_xy, dtype=float)
    return d[:, 0] * perp[0] + d[:, 1] * perp[1]


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


def _dummy(**over):
    """A synthetic PrtCapture for the solve-free cache unit tests."""
    kw = dict(
        capture_fraction=0.5, n_particles=4, n_released=4, n_captured=2, n_escaped=2,
        tt_median_d=10.0, tt_p10_d=5.0, tt_p90_d=15.0, tt_min_d=4.0, tt_max_d=16.0,
        lateral_swath_m=7.0, capture_halfwidth_m=6.0,
        release_points=np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]),
        release_cells=np.array([1, 2, 3, 4], dtype=np.int64),
        endpoints=np.array([[9.0, 9.0, 10.0], [9.0, 9.0, 11.0],
                            [5.0, 5.0, 730.0], [5.0, 5.0, 730.0]]),
        end_cells=np.array([7, 7, 3, 4], dtype=np.int64),
        end_status=np.array([5, 5, 10, 10], dtype=np.int64),
        captured=np.array([True, True, False, False]),
        travel_times=np.array([10.0, 11.0, 730.0, 730.0]),
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
    # the census must close: every released particle is captured XOR escaped
    assert capture.n_captured + capture.n_escaped == capture.n_released
    assert capture.n_captured == int(capture.captured.sum())
    assert capture.n_escaped == int((~capture.captured).sum())
    assert 0.0 < capture.capture_fraction <= 1.0
    assert capture.capture_fraction == pytest.approx(
        capture.n_captured / capture.n_released)

    # array shapes are all per-released-particle and mutually consistent
    n = capture.n_released
    assert capture.release_points.shape == (n, 2)
    assert capture.release_cells.shape == (n,)
    assert capture.endpoints.shape == (n, 3)
    assert capture.end_cells.shape == (n,)
    assert capture.end_status.shape == (n,)
    assert capture.captured.shape == (n,)
    assert capture.travel_times.shape == (n,)
    # pathlines carry every particle, with >= 2 vertices each (release + terminate)
    assert capture.pathlines.ndim == 2 and capture.pathlines.shape[1] == 4
    assert set(capture.pathlines[:, 0].astype(int)) == set(range(n))
    assert capture.pathlines.shape[0] >= 2 * n

    # the release disc really is centred on the ADE demo's spill location
    d = np.hypot(capture.release_points[:, 0] - capture.spill_xy[0],
                 capture.release_points[:, 1] - capture.spill_xy[1])
    assert d.max() <= capture.release_radius_m + 1e-6
    assert capture.meta["spill_to_well_m"] == pytest.approx(
        tpc.SPILL_UPGRADIENT_M, rel=1e-6)


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

    # and the classification is internally consistent with that definition
    assert np.all(capture.end_cells[capture.captured] == capture.ext_cell)
    assert np.all(capture.end_cells[~capture.captured] != capture.ext_cell)
    # every captured particle terminated by the SAME mechanism (istatus 5 = no exit
    # face, i.e. the strong sink), and no particle was captured by the injection well
    assert len(set(capture.end_status[capture.captured].tolist())) == 1
    assert not np.any(capture.end_cells == capture.inj_cell)


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
def test_captured_travel_times_are_finite_positive_and_physical(capture):
    """Captured particles must have finite, strictly POSITIVE travel times, and the
    median advective travel time must be physically sane -- checked against an
    implied seepage velocity, not just pinned to a magic number."""
    tt = capture.travel_times[capture.captured]
    assert tt.size == capture.n_captured > 0
    assert np.all(np.isfinite(tt))
    assert np.all(tt > 0.0), "a travel time of 0 d means a particle was released " \
                             "inside the well cell -- those must be dropped"

    for v in (capture.tt_median_d, capture.tt_p10_d, capture.tt_p90_d,
              capture.tt_min_d, capture.tt_max_d):
        assert math.isfinite(v) and v > 0.0
    # the reported stats really are the stats of the CAPTURED subset
    assert capture.tt_median_d == pytest.approx(float(np.median(tt)))
    assert capture.tt_p10_d == pytest.approx(float(np.percentile(tt, 10)))
    assert capture.tt_p90_d == pytest.approx(float(np.percentile(tt, 90)))
    assert capture.tt_min_d == pytest.approx(float(tt.min()))
    assert capture.tt_max_d == pytest.approx(float(tt.max()))
    assert capture.tt_min_d <= capture.tt_p10_d <= capture.tt_median_d \
        <= capture.tt_p90_d <= capture.tt_max_d

    # PHYSICS: the implied seepage velocity over the 90 m spill->well path must be
    # a plausible forced-gradient gravel-aquifer velocity (m/d, not mm/d or km/d).
    v_implied = capture.meta["spill_to_well_m"] / capture.tt_median_d
    assert 0.5 < v_implied < 20.0, f"implied seepage velocity {v_implied:.3g} m/d"

    # every particle terminates within the tracking window
    assert np.all(capture.travel_times <= capture.track_days + 1e-6)

    # REGRESSION PIN (measured): median 25.8 d, p10 22.7, p90 28.6.
    assert capture.tt_median_d == pytest.approx(25.8, rel=0.05)
    assert capture.tt_p10_d == pytest.approx(22.7, rel=0.05)
    assert capture.tt_p90_d == pytest.approx(28.6, rel=0.05)

    # PRT vs ADE: these are DIFFERENT quantities and MUST NOT be conflated.  The
    # advective median (~26 d) is NOT the ADE's day-41 concentration peak.  They
    # are nevertheless consistent: the ADE releases a finite 30-day pulse, whose
    # centre of mass leaves at t = 15 d, and 15 + 25.8 = 40.8 ~ 41.
    assert capture.tt_median_d < ADE_PEAK_DAY
    assert (ADE_PULSE_DAYS / 2.0 + capture.tt_median_d) == pytest.approx(
        ADE_PEAK_DAY, abs=3.0)


@pytest.mark.slow
def test_spill_footprint_is_entirely_inside_the_capture_zone(capture):
    """The 10 m footprint rung: EVERY particle is captured (fraction exactly 1.0).

    That is the honest answer for this spill -- and it is also why a second,
    wider rung exists: a run where everything is captured says nothing about where
    the capture zone ENDS (see the next test)."""
    assert capture.release_radius_m == pytest.approx(FOOTPRINT_RADIUS_M)
    assert capture.n_escaped == 0
    assert capture.capture_fraction == 1.0
    assert capture.meta["n_dropped_wellcell"] == 0    # 90 m away, 10 m disc
    # the swept swath is about the footprint width -- the pathlines converge on the
    # well, they do not fan out
    assert capture.lateral_swath_m == pytest.approx(10.5, rel=0.15)
    assert capture.capture_halfwidth_m == pytest.approx(FOOTPRINT_RADIUS_M, rel=0.05)


@pytest.mark.slow
def test_capture_zone_boundary_on_axis_captured_off_axis_escapes(wide):
    """THE physics contrast, and the lateral answer the ADE model could not give.

    On the 120 m rung the release disc straddles the capture-zone boundary, so the
    capture fraction is STRICTLY between 0 and 1.  A particle released on the
    spill -> well axis is captured; particles far enough OFF that axis are not."""
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

    # (c) captured particles are systematically closer to the axis than escapees --
    # and the two populations SEPARATE: no captured particle lies further off-axis
    # than the widest captured one (that is the capture half-width), which is
    # strictly inside the release disc.
    assert np.abs(off[wide.captured]).mean() < np.abs(off[~wide.captured]).mean()
    assert wide.capture_halfwidth_m == pytest.approx(
        float(np.abs(off[wide.captured]).max()))
    assert wide.capture_halfwidth_m < wide.release_radius_m, (
        "the capture half-width is not resolved: every captured particle reaches "
        "the edge of the release disc, so this rung does not bracket the boundary")
    # measured: half-width 82.9 m, swath 82.9 m, fraction 0.719
    assert wide.capture_halfwidth_m == pytest.approx(82.9, rel=0.10)
    assert wide.lateral_swath_m == pytest.approx(82.9, rel=0.10)
    assert wide.capture_fraction == pytest.approx(0.72, abs=0.06)

    # (d) the lateral swath is a real, defensible number: it is at least the
    # capture half-width (pathlines start at the release points) and never wider
    # than the disc that produced it.
    assert wide.lateral_swath_m >= wide.capture_halfwidth_m - 1e-6
    assert wide.lateral_swath_m <= wide.release_radius_m + 1e-6

    # release points inside a doublet well cell are dropped (they would report a
    # 0 d travel time); at 120 m the disc reaches the well, so exactly this happens
    assert wide.meta["n_dropped_wellcell"] >= 1
    assert wide.n_released == wide.n_particles - wide.meta["n_dropped_wellcell"]
    assert np.all(wide.travel_times[wide.captured] > 0.0)


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


@pytest.mark.slow
def test_module_source_change_busts_cache(tmp_path, monkeypatch):
    """Editing the module SOURCE (this module or the ADE module it inherits the
    doublet / spill geometry / corridor refinement from) must bust the cache.

    LOCKED_PARAMS only covers one dict: changing DOUBLET_Q, SPILL_UPGRADIENT_M,
    INJ_XY/ABS_XY, the release layout, the FMI wiring or the fate classification
    would otherwise leave the hash -- and every warm cache, notebook users
    included -- unchanged while the model changed underneath it."""
    ws = tmp_path / "prt_ws_src"
    tpc.build_prt_capture(n_particles=32, release_radius_m=FOOTPRINT_RADIUS_M,
                          track_days=TRACK_DAYS, case_ws=ws, force=True)
    before = set(ws.glob("prtcapture_cache_*.npz"))
    assert len(before) == 1

    # stand in for "somebody edited the source" without editing it
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
