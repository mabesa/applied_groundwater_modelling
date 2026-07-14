"""Tests for transport_srcpulse_demo (SRC finite-pulse spill -> capture demo).

The model build+run is expensive (~15 s), so it runs once via a module-scoped
fixture and every test reads its diagnostics.  Re-calls hit the npz cache and are
solve-free.  Run with:  uv run pytest _SUPPORT/tests/test_transport_srcpulse_demo.py
"""
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
