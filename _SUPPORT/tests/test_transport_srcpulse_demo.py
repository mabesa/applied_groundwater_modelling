"""Tests for transport_srcpulse_demo (SRC finite-pulse spill -> capture demo).

The model build+run is expensive (~15 s), so it runs once via a module-scoped
fixture and every test reads its diagnostics.  Re-calls hit the npz cache and are
solve-free.  Run with:  uv run pytest _SUPPORT/tests/test_transport_srcpulse_demo.py
"""
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
