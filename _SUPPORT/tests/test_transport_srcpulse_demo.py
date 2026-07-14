"""Tests for transport_srcpulse_demo (SRC finite-pulse spill -> capture demo).

The model build+run is expensive (~15 s), so it runs once via a module-scoped
fixture and every test reads its diagnostics.  Re-calls hit the npz cache and are
solve-free.  Run with:  uv run pytest _SUPPORT/tests/test_transport_srcpulse_demo.py
"""
import dataclasses
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_srcpulse_demo as tsd  # noqa: E402

# Locked demo parameters (kept in sync with the module defaults / smoke anchor).
MASS_G = 3.0e5
PULSE_DAYS = 30.0
TOTAL_DAYS = 120.0
SOLUBILITY_MGL = 1000.0

# ---------------------------------------------------------------------------
# reactive-transport variant parameters (M4 step 1)
# ---------------------------------------------------------------------------
REACTIVE_R = 2.0
REACTIVE_TOTAL_DAYS = 220.0    # conservative arrival ~41 d; R=2 roughly doubles it,
                                # plus dispersive tailing -- give it plenty of headroom
DISPERSIVITY_ALPHA_L = 20.0    # vs. the LOCKED default of 10.0 m
DECAY_HALFLIFE_DAYS = 30.0
DECAY_LAM = math.log(2.0) / DECAY_HALFLIFE_DAYS


@pytest.fixture(scope="module")
def demo():
    """Build (or load-from-cache) the SRC finite-pulse demo once for all tests."""
    return tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, force=False)


def test_model_builds_and_runs(demo):
    """The coupled GWF/GWT SRC-pulse model builds, runs, and returns diagnostics."""
    assert isinstance(demo, tsd.SrcPulseDemo)
    assert demo.times.size > 1
    assert demo.breakthrough.size == demo.times.size
    # SRC introduced the full released mass (grams) with essentially no discrepancy.
    assert demo.mass_balance.get("src_in_g") == pytest.approx(MASS_G, rel=1e-3)
    # Corridor is well-resolved for advection (grid Peclet Pe_L <= 2).
    assert demo.PeL_max <= 2.0


def test_mass_balance_closes(demo):
    """The GWT mass budget closes to well under ~5%."""
    pct = demo.mass_balance.get("pct_imbalance")
    assert pct is not None and np.isfinite(pct)
    assert abs(pct) < 5.0
    # Sanity: released mass is (almost) all accounted for by well capture +
    # boundary loss + aquifer storage.
    src_in = demo.mass_balance["src_in_g"]
    accounted = (demo.mass_balance["well_out_g"]
                 + demo.mass_balance["boundary_out_g"]
                 + demo.mass_balance["storage_g"])
    assert accounted == pytest.approx(src_in, rel=0.05)


def test_breakthrough_resolvable_not_saturated(demo):
    """Peak breakthrough at the extraction well is > 0 and not saturated."""
    assert demo.peak_mgL > 0.0
    # "Not saturated": well below the emergent source concentration (dispersion +
    # dilution attenuate the pulse) and below solubility.
    assert demo.peak_mgL < demo.emergent_C_mgL
    assert demo.peak_mgL < demo.solubility_mgL
    # Arrival is a real time within the simulated window.
    assert 0.0 < demo.arrival_day <= demo.total_days


def test_solubility_guardrail(demo):
    """The solubility guardrail returns a boolean and passes for the chosen mass."""
    assert isinstance(demo.solubility_ok, bool)
    assert demo.solubility_ok is True
    assert demo.emergent_C_mgL < demo.solubility_mgL
    assert demo.solubility_margin > 1.0


# ---------------------------------------------------------------------------
# M4 step 1: REACTIVE-TRANSPORT + DISPERSIVITY parameters
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def reactive_demo():
    """Retarded (R=2), non-decaying variant; solved once for the module."""
    return tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=REACTIVE_TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, R=REACTIVE_R, force=False)


@pytest.fixture(scope="module")
def dispersivity_demo():
    """alpha_L=20 (2x the LOCKED default), conservative (R=1, lam=0) otherwise."""
    return tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, alpha_L=DISPERSIVITY_ALPHA_L, force=False)


@pytest.fixture(scope="module")
def decay_demo():
    """Decay-only variant (R=1, lam = ln(2)/30 d); solved once for the module."""
    return tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, lam=DECAY_LAM, force=False)


@pytest.mark.slow
def test_default_unchanged(demo):
    """Regression lock: the default (conservative) run is unchanged by the new
    optional reactive-transport / dispersivity kwargs (all default to today's
    behavior)."""
    assert demo.peak_mgL == pytest.approx(4.95, rel=0.02)
    assert demo.arrival_day == pytest.approx(41.0, abs=5.0)
    assert demo.alpha_L == pytest.approx(tsd.LOCKED_PARAMS["alh"])
    assert demo.alpha_T == pytest.approx(tsd.LOCKED_PARAMS["ath1"])
    assert demo.R == pytest.approx(1.0)
    assert demo.Kd == pytest.approx(0.0)
    assert demo.lam == pytest.approx(0.0)
    pct = demo.mass_balance.get("pct_imbalance")
    assert pct is not None and np.isfinite(pct) and abs(pct) < 1.0


@pytest.mark.slow
def test_reactive_input_validation():
    """R < 1, lam < 0, and alpha_L <= 0 are rejected before any solve."""
    with pytest.raises(ValueError):
        tsd.build_srcpulse_demo(R=0.5)
    with pytest.raises(ValueError):
        tsd.build_srcpulse_demo(lam=-1.0)
    with pytest.raises(ValueError):
        tsd.build_srcpulse_demo(alpha_L=0.0)
    with pytest.raises(ValueError):
        tsd.build_srcpulse_demo(alpha_L=-5.0)


@pytest.mark.slow
def test_reactive_is_later_and_lower(demo, reactive_demo):
    """Retardation (R=2) delays and attenuates the peak vs. the conservative run."""
    assert reactive_demo.R == pytest.approx(REACTIVE_R)
    assert reactive_demo.Kd > 0.0
    # plume must actually reach the well within the (extended) simulation window
    assert reactive_demo.peak_mgL > 0.0
    assert 0.0 < reactive_demo.arrival_day <= reactive_demo.total_days
    assert reactive_demo.peak_mgL < demo.peak_mgL
    assert reactive_demo.arrival_day > demo.arrival_day
    # regression lock (verified numbers): R=2.0, total_days=220 -> peak 2.987065 mg/L
    # @ day 61.46. Pins the MAGNITUDE, not just the direction, so a regression in the
    # peak/arrival value (not just its sign relative to the conservative run) is caught.
    assert reactive_demo.peak_mgL == pytest.approx(2.987, rel=0.02)
    assert reactive_demo.arrival_day == pytest.approx(61.5, abs=5.0)
    # mass balance still closes for the reactive (sorbing) run
    pct = reactive_demo.mass_balance.get("pct_imbalance")
    assert pct is not None and np.isfinite(pct) and abs(pct) < 1.0


@pytest.mark.slow
def test_dispersivity_sensitivity(demo, dispersivity_demo):
    """alpha_L=20 (and, per the locked 10:1 ratio, ath1=2.0) halves both grid
    Peclet numbers and broadens/advances the breakthrough curve."""
    assert dispersivity_demo.alpha_L == pytest.approx(DISPERSIVITY_ALPHA_L)
    assert dispersivity_demo.alpha_T == pytest.approx(DISPERSIVITY_ALPHA_L / 10.0)
    assert dispersivity_demo.PeL_max == pytest.approx(demo.PeL_max / 2.0, rel=0.02)
    assert dispersivity_demo.PeT_max == pytest.approx(demo.PeT_max / 2.0, rel=0.02)

    # earlier-toe metric: first time C exceeds a small threshold (1% of the
    # conservative peak) is earlier for the more-dispersive run.
    threshold = 0.01 * demo.peak_mgL

    def _first_exceedance(d):
        above = np.where(d.breakthrough > threshold)[0]
        assert above.size > 0, "breakthrough never exceeds the toe threshold"
        return float(d.times[above[0]])

    t_toe_base = _first_exceedance(demo)
    t_toe_disp = _first_exceedance(dispersivity_demo)
    assert t_toe_disp < t_toe_base

    # broader breakthrough curve: width at half max is larger for alpha_L=20.
    def _fwhm(d):
        half = 0.5 * d.breakthrough.max()
        above = np.where(d.breakthrough >= half)[0]
        assert above.size > 0
        return float(d.times[above[-1]] - d.times[above[0]])

    fwhm_base = _fwhm(demo)
    fwhm_disp = _fwhm(dispersivity_demo)
    assert fwhm_disp > fwhm_base

    # spec amendment: alpha_T also doubles, so transverse dilution should also
    # lower the peak relative to the conservative run -- check it, report if not.
    if not (dispersivity_demo.peak_mgL < demo.peak_mgL):
        pytest.fail(
            "spec-amendment check did not hold: expected alpha_L=20 (alpha_T=2.0) "
            f"peak ({dispersivity_demo.peak_mgL:.4g} mg/L) < conservative peak "
            f"({demo.peak_mgL:.4g} mg/L) due to added transverse dilution; "
            "reporting actual numbers instead of dropping the assertion.")


@pytest.mark.slow
def test_cache_is_per_variant_no_cross_contamination(demo, reactive_demo):
    """Re-calling with the FIRST param set after a different variant was solved
    must return the FIRST run's cached numbers -- not the second run's (this is
    the subtle cache-identity bug the per-variant hashed cache file guards
    against).  Solve-free: both variants are already cached by prior fixtures."""
    # sanity: the two variants really are different runs
    assert reactive_demo.R != demo.R
    assert reactive_demo.peak_mgL != pytest.approx(demo.peak_mgL, rel=1e-6)

    # re-call the FIRST (conservative) param set; must hit ITS cache, unchanged
    # by the reactive_demo call that happened in between.
    recalled = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, force=False)
    assert recalled.peak_mgL == pytest.approx(demo.peak_mgL, rel=1e-9)
    assert recalled.arrival_day == pytest.approx(demo.arrival_day, rel=1e-9)
    assert recalled.R == pytest.approx(demo.R)
    assert recalled.mass_balance == demo.mass_balance


@pytest.mark.slow
def test_decay_only(demo, decay_demo):
    """Decay-only (lam=ln(2)/30d, R=1): peak is lower and net mass is removed by
    decay relative to the conservative (non-decaying) run."""
    assert decay_demo.lam == pytest.approx(DECAY_LAM)
    assert decay_demo.R == pytest.approx(1.0)
    assert decay_demo.Kd == pytest.approx(0.0)
    assert decay_demo.peak_mgL < demo.peak_mgL
    decay_g = decay_demo.mass_balance.get("decay_g")
    assert decay_g is not None and np.isfinite(decay_g)
    assert decay_g != 0.0
    # total mass recovered (well + boundary) is lower than the conservative run's
    recovered_decay = (decay_demo.mass_balance["well_out_g"]
                        + decay_demo.mass_balance["boundary_out_g"])
    recovered_base = (demo.mass_balance["well_out_g"]
                       + demo.mass_balance["boundary_out_g"])
    assert recovered_decay < recovered_base


# ---------------------------------------------------------------------------
# FIX 3 (cache identity) + FIX 6 (grouped mass-balance reconciliation) regressions
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def reactive_decay_demo():
    """R=2 AND lam>0 together -- the reactive-transport case with the MOST GWT
    budget terms (STORAGE-AQUEOUS, STORAGE-SORBED, DECAY-AQUEOUS, DECAY-SORBED
    all appear at once), used to pin the FIX 6 grouped mass-balance
    reconciliation self-check."""
    return tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=REACTIVE_TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, R=REACTIVE_R, lam=DECAY_LAM, force=False)


@pytest.mark.slow
def test_grouped_mass_balance_reconciles(reactive_decay_demo):
    """FIX 6 regression: `pct_imbalance` is MF6's own PERCENT_DISCREPANCY, which
    says nothing about whether OUR substring grouping (SRC/WEL/RIV/CHD/RCH,
    "STORAGE" in cu, "DECAY" in cu) missed or double-counted a budget column.
    `grouped_residual_g` reconciles the sum of our grouped terms against MF6's
    own TOTAL_IN/TOTAL_OUT directly, and must be ~0 g -- checked on the
    reactive+decaying run, which has the most budget terms to mis-group."""
    mb = reactive_decay_demo.mass_balance
    residual = mb.get("grouped_residual_g")
    assert residual is not None and np.isfinite(residual)
    # near-zero in grams, against a released mass of order 1e5 g: a missed or
    # double-counted column would show up as a residual many orders larger
    # than listing-file rounding noise.
    assert abs(residual) < 1.0
    # sanity: pct_imbalance (MF6's own number) still closes too, and the two
    # self-checks are not the same computation.
    pct = mb.get("pct_imbalance")
    assert pct is not None and np.isfinite(pct) and abs(pct) < 1.0


def test_save_load_cache_restores_locked_exactly(tmp_path):
    """FIX 3 regression, isolated and FAST (no MF6 solve): exercises
    `_save_cache`/`_load_cache` directly with a synthetic `locked` snapshot
    that deliberately differs from the live `tsd.LOCKED_PARAMS`. If `locked`
    were dropped from the save/load round trip (the exact FIX 3 bug -- it was
    silently resurrected from the CURRENT LOCKED_PARAMS default factory
    instead of the value actually saved), `restored.locked` would come back
    equal to the LIVE global instead of the saved snapshot, and this test
    would fail. Complements `test_cache_round_trip_fidelity` /
    `test_locked_params_change_busts_cache` below, which exercise the same
    bug through the full (slow) build_srcpulse_demo path."""
    fake_locked = dict(tsd.LOCKED_PARAMS)
    fake_locked["porosity"] = 0.123456  # deliberately NOT the live LOCKED_PARAMS value
    assert fake_locked["porosity"] != tsd.LOCKED_PARAMS["porosity"]

    dummy = tsd.SrcPulseDemo(
        times=np.array([0.0, 1.0]), breakthrough=np.array([0.0, 1.0]),
        peak_mgL=1.0, arrival_day=1.0, mass_balance={"a": 1.0}, solubility_ok=True,
        emergent_C_mgL=1.0, solubility_mgL=1.0, solubility_margin=1.0,
        PeL_min=1.0, PeL_max=1.0, PeT_min=1.0, PeT_max=1.0,
        mass_g=1.0, pulse_days=1.0, total_days=2.0, smassrate_gpd=1.0,
        src_cells=[0], ext_cell=1, inj_cell=2, spill_xy=(0.0, 0.0),
        alpha_L=10.0, alpha_T=1.0, R=1.0, rho_b=1800.0, Kd=0.0, lam=0.0,
        meta={"k": "v"}, locked=fake_locked)

    params = {"mass_g": 1.0, "locked": fake_locked}
    cache_path = tmp_path / "unit_cache.npz"
    tsd._save_cache(cache_path, dummy, params)
    restored = tsd._load_cache(cache_path, params)

    assert restored is not None
    assert restored.locked == fake_locked
    # the crux: must NOT have been silently resurrected from the live global
    assert restored.locked["porosity"] != tsd.LOCKED_PARAMS["porosity"]


@pytest.mark.slow
def test_cache_round_trip_fidelity(tmp_path):
    """FIX 3 regression: a fresh (real) solve and a cache-hit re-call with
    IDENTICAL args, in an isolated workspace, must return dataclass objects
    that are equal field-for-field -- including `locked` and `meta` -- not
    just equal on a few spot-checked attributes.  Iterates
    dataclasses.fields() so a newly added SrcPulseDemo field is automatically
    covered, rather than hand-listed here.  This is the test that would have
    caught FIX 3's dropped `locked` field (previously resurrected from the
    CURRENT LOCKED_PARAMS default factory instead of the cached value)."""
    ws = tmp_path / "srcpulse_ws"
    fresh = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, case_ws=ws, force=True)
    cached = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, case_ws=ws, force=False)

    for f in dataclasses.fields(tsd.SrcPulseDemo):
        fv, cv = getattr(fresh, f.name), getattr(cached, f.name)
        if isinstance(fv, np.ndarray):
            np.testing.assert_array_equal(cv, fv, err_msg=f"field {f.name!r} mismatch")
        else:
            assert cv == fv, f"field {f.name!r} mismatch: fresh={fv!r} cached={cv!r}"


@pytest.mark.slow
def test_locked_params_change_busts_cache(tmp_path, monkeypatch):
    """FIX 3 regression: editing LOCKED_PARAMS (e.g. porosity) must NOT be
    silently masked by an existing cache file.  Cache identity now folds in a
    LOCKED_PARAMS snapshot, so changing ONLY a LOCKED_PARAMS value must
    produce a DIFFERENT cache file and force a real rebuild, rather than
    returning the stale entry computed under the old locked params."""
    ws = tmp_path / "srcpulse_ws_locked"
    baseline = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, case_ws=ws, force=True)
    baseline_caches = set(ws.glob("srcpulse_cache_*.npz"))
    assert len(baseline_caches) == 1

    patched_locked = dict(tsd.LOCKED_PARAMS)
    patched_locked["porosity"] = tsd.LOCKED_PARAMS["porosity"] * 1.5
    monkeypatch.setattr(tsd, "LOCKED_PARAMS", patched_locked)

    changed = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, case_ws=ws, force=False)

    changed_caches = set(ws.glob("srcpulse_cache_*.npz"))
    # a NEW cache file must exist -- the old (now params-mismatched) one must
    # not have been reused.
    assert changed_caches != baseline_caches
    assert len(changed_caches) == 2
    # the result must actually reflect the new porosity -- solved fresh under
    # the patched LOCKED_PARAMS, not resurrected from the stale cache.
    assert changed.locked["porosity"] == pytest.approx(patched_locked["porosity"])
    assert changed.locked["porosity"] != pytest.approx(baseline.locked["porosity"])
