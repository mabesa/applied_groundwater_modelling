"""Tests for transport_verify_2d (MF6 GWT vs exact 2D analytical plume).

Four groups:
  1. Analytical sanity (no MF6): mass conservation, peak position, y-symmetry.
  2. Numerical <-> analytical, CONSERVATIVE (R=1, lam=0), fine grid.
  3. Numerical <-> analytical, REACTIVE (R=2, first-order decay).
  4. Coarse-grid transverse smearing (delc=10 -> Pe_T=10) vs the fine grid.

The MF6 build+run is a few seconds each, so each configuration runs once via a
module-scoped fixture and the tests read its diagnostics.

Run with:  uv run pytest _SUPPORT/tests/test_transport_verify_2d.py
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_verify_2d as v2  # noqa: E402


# ===========================================================================
# 1. ANALYTICAL SANITY (pure closed-form, no MODFLOW)
# ===========================================================================
# Representative parameters (metres / days).
_M = 1000.0        # released mass [g]
_PHI = 0.20        # porosity [-]
_MTHICK = 10.0     # aquifer thickness [m]
_U = 0.5           # seepage velocity [m/d]
_ALPHA_L = 10.0    # longitudinal dispersivity [m]
_ALPHA_T = 1.0     # transverse dispersivity [m]
_DL = _ALPHA_L * _U   # = 5 m^2/d
_DT = _ALPHA_T * _U   # = 0.5 m^2/d


def test_analytical_mass_conservation_conservative():
    """Integral of c over the plane * (phi_e*R*m) == M (R=1, lam=0)."""
    t = 100.0
    # fine integration grid centred on the plume, wide enough for the tails
    xc = _U * t
    x = np.linspace(xc - 250.0, xc + 250.0, 1201)
    y = np.linspace(-120.0, 120.0, 961)
    dx = x[1] - x[0]
    dy = y[1] - y[0]
    X, Y = np.meshgrid(x, y)
    c = v2.plume_2d_instantaneous(X, Y, t, _M, _PHI, _MTHICK, 1.0, _DL, _DT, _U)
    mass = c.sum() * dx * dy * (_PHI * 1.0 * _MTHICK)
    assert mass == pytest.approx(_M, rel=1e-3)


def test_analytical_mass_decay_and_retardation():
    """With R and lam, the integrated mass == M*exp(-lam*t) (decay only)."""
    t = 100.0
    R = 2.0
    lam = np.log(2.0) / 100.0
    xc = (_U / R) * t
    x = np.linspace(xc - 250.0, xc + 250.0, 1201)
    y = np.linspace(-120.0, 120.0, 961)
    dx = x[1] - x[0]
    dy = y[1] - y[0]
    X, Y = np.meshgrid(x, y)
    c = v2.plume_2d_instantaneous(X, Y, t, _M, _PHI, _MTHICK, R, _DL, _DT, _U, lam)
    mass = c.sum() * dx * dy * (_PHI * R * _MTHICK)
    assert mass == pytest.approx(_M * np.exp(-lam * t), rel=1e-3)


def test_analytical_peak_position_and_symmetry():
    """Peak sits at x=(u/R)*t, y=0; field is symmetric in y."""
    t = 80.0
    R = 2.0
    x = np.linspace(0.0, 120.0, 2401)          # fine x line at y=0
    c_line = v2.plume_2d_instantaneous(x, 0.0, t, _M, _PHI, _MTHICK, R, _DL, _DT, _U)
    x_peak = x[int(np.argmax(c_line))]
    assert x_peak == pytest.approx((_U / R) * t, abs=x[1] - x[0])
    # y-symmetry: c(x, +y) == c(x, -y)
    xg = np.array([20.0, 40.0, 60.0])
    yg = np.array([3.0, 7.5, 15.0])
    cp = v2.plume_2d_instantaneous(xg, yg, t, _M, _PHI, _MTHICK, R, _DL, _DT, _U)
    cm = v2.plume_2d_instantaneous(xg, -yg, t, _M, _PHI, _MTHICK, R, _DL, _DT, _U)
    assert np.allclose(cp, cm)
    # transverse decay: on-centre >= off-centre
    assert np.all(cp <= v2.plume_2d_instantaneous(xg, 0.0, t, _M, _PHI, _MTHICK, R,
                                                   _DL, _DT, _U))


def test_analytical_guards_and_shapes():
    """t<=0 returns zeros; scalar and array inputs both work."""
    z = v2.plume_2d_instantaneous(np.zeros((3, 3)), np.zeros((3, 3)), 0.0,
                                  _M, _PHI, _MTHICK, 1.0, _DL, _DT, _U)
    assert np.all(z == 0.0) and z.shape == (3, 3)
    s = v2.plume_2d_instantaneous(30.0, 0.0, 60.0, _M, _PHI, _MTHICK, 1.0,
                                  _DL, _DT, _U)
    assert np.ndim(s) == 0 and s > 0.0


# ===========================================================================
# Fixtures: run each MF6 configuration once (module-scoped).
# ===========================================================================
@pytest.fixture(scope="module")
def conservative():
    """Conservative (R=1, lam=0) fine grid, t=120 d."""
    return v2.build_and_run_2d_verification()


@pytest.fixture(scope="module")
def reactive():
    """Reactive: R=2 (linear sorption) + first-order decay (half-life 100 d)."""
    lam = np.log(2.0) / 100.0
    return v2.build_and_run_2d_verification(R=2.0, lam=lam)


@pytest.fixture(scope="module")
def coarse():
    """Coarse transverse grid delc=10 m (Pe_T=10), otherwise conservative."""
    return v2.build_and_run_2d_verification(delc=10.0)


def _idx_at(times, t):
    return int(np.argmin(np.abs(np.asarray(times) - t)))


# ===========================================================================
# 2. NUMERICAL <-> ANALYTICAL, CONSERVATIVE, FINE GRID
# ===========================================================================
def test_conservative_grid_is_well_resolved(conservative):
    r = conservative
    assert r.Pe_L <= 2.0 and r.Pe_T <= 2.0        # grid Peclet OK for advection
    assert r.meta["Cr"] <= 1.0                    # Courant OK


def test_conservative_matches_analytical(conservative):
    """Fine-grid conservative run matches the exact plume within the gates."""
    r = conservative
    assert r.peak_pos_err < 0.05                  # peak position < 5%
    assert r.peak_conc_err < 0.10                 # peak concentration < 10%
    assert r.sigma_y_err < 0.15                   # transverse sigma < 15%
    # longitudinal spread is also well captured (a bit of TVD numerical disp.)
    assert r.sigma_x_err < 0.15


def test_conservative_mass_is_exactly_M(conservative):
    """The initial spike carries exactly M grams; no decay (lam=0)."""
    r = conservative
    assert r.mass_num == pytest.approx(r.M, rel=0.01)
    assert r.mass_an == pytest.approx(r.M, rel=1e-12)


def test_conservative_peak_velocity(conservative):
    """Numerical centre-of-mass advects at u (R=1)."""
    r = conservative
    sel = r.times > 1e-9
    A = np.vstack([r.times[sel], np.ones(sel.sum())]).T
    v_fit = np.linalg.lstsq(A, r.x_cm_t[sel], rcond=None)[0][0]
    assert v_fit == pytest.approx(r.u / r.R, rel=0.05)


# ===========================================================================
# 3. NUMERICAL <-> ANALYTICAL, REACTIVE (R>1, lam>0)
# ===========================================================================
def test_reactive_matches_analytical(reactive):
    """Reactive run matches the exact retarded/decaying plume within the gates."""
    r = reactive
    assert r.R == 2.0 and r.lam > 0.0
    assert r.peak_pos_err < 0.05
    assert r.peak_conc_err < 0.10
    assert r.sigma_y_err < 0.15
    assert r.sigma_x_err < 0.15


def test_reactive_retarded_velocity(reactive):
    """Numerical peak advects at ~u/R (slower than the conservative u)."""
    r = reactive
    sel = r.times > 1e-9
    A = np.vstack([r.times[sel], np.ones(sel.sum())]).T
    v_fit = np.linalg.lstsq(A, r.x_cm_t[sel], rcond=None)[0][0]
    assert v_fit == pytest.approx(r.u / r.R, rel=0.05)
    assert v_fit < 0.8 * r.u                       # clearly retarded


def test_reactive_mass_decays(reactive):
    """Total in-domain mass follows M*exp(-lam*t) at every output time."""
    r = reactive
    expected = r.M * np.exp(-r.lam * r.times)
    # ratio numerical/expected close to 1 across the run
    valid = r.times > 1e-9
    ratio = r.mass_t[valid] / expected[valid]
    assert np.allclose(ratio, 1.0, atol=0.03)
    # and clearly decayed by the end (half-life 100 d, t=120 d -> ~44% left)
    assert r.mass_num < 0.6 * r.M
    assert r.mass_num == pytest.approx(r.mass_an, rel=0.03)


# ===========================================================================
# 4. COARSE-GRID TRANSVERSE SMEARING (the teaching lesson)
# ===========================================================================
def test_coarse_transverse_sigma_inflated(conservative, coarse):
    """delc=10 (Pe_T=10) inflates the transverse spread vs the fine grid.

    Compared at an early time (t~40 d) where the physical transverse half-width
    (~6 m) is comparable to the 10 m coarse cell, so the coarse grid cannot
    resolve it and the represented plume is meaningfully wider.
    """
    t_cmp = 40.0
    fine, cse = conservative, coarse
    assert cse.Pe_T >= 5.0 and fine.Pe_T <= 2.0     # sanity on the two grids

    i_f = _idx_at(fine.times, t_cmp)
    i_c = _idx_at(cse.times, t_cmp)
    sig_an = np.sqrt(2.0 * fine.DT * fine.times[i_f] / fine.R)

    sig_fine = fine.sigma_y_t[i_f]
    sig_coarse = cse.sigma_y_t[i_c]

    err_fine = abs(sig_fine - sig_an) / sig_an
    err_coarse = abs(sig_coarse - sig_an) / sig_an

    # fine grid: essentially exact; coarse grid: clearly inflated
    assert err_fine < 0.03
    assert err_coarse > 0.06
    assert sig_coarse > 1.05 * sig_fine             # coarse meaningfully wider


def test_coarse_still_conserves_mass(coarse):
    """Coarsening the transverse grid must not lose mass (only smear it)."""
    r = coarse
    assert r.mass_num == pytest.approx(r.M, rel=0.02)


def test_coarse_transported_variance_is_grid_independent(conservative, coarse):
    """The RAW cell-centre transverse moment is (nearly) grid-independent.

    Aligned flow + TVD adds no cross-wind numerical dispersion, so the
    *transported* second moment matches the fine grid; the inflation seen in
    ``sigma_y`` is purely the sub-cell representation limit (delc^2/12).  This
    contrast is the pedagogical point.
    """
    t_cmp = 40.0
    i_f = _idx_at(conservative.times, t_cmp)
    i_c = _idx_at(coarse.times, t_cmp)
    # field second moments differ (representation limit) ...
    assert coarse.sigma_y_t[i_c] > conservative.sigma_y_t[i_f]
    # ... but the raw cell-centre moment at compare time is close between grids
    assert coarse.meta["sigma_y_centres_num"] == pytest.approx(
        conservative.meta["sigma_y_centres_num"], rel=0.05)


# ===========================================================================
# 5. OBLIQUE FLOW -> REAL (grid-orientation) CROSS-WIND NUMERICAL DISPERSION
# ===========================================================================
# Square-ish domain (160 x 160 m) so the plume can travel diagonally without
# reaching a boundary; source in the lower-left, flow at +45 deg carries it to
# the upper-right.  XT3D is ON so the *physical* dispersion tensor is exact at
# any angle -- the residual cross-flow error is then purely the ADVECTIVE
# cross-wind numerical dispersion (cell-size dependent, refinement-removable).
_OBLIQUE = dict(xL=160.0, y_half=80.0, x0=45.0, y0=-45.0,
                total_time=100.0, flow_angle_deg=45.0, xt3d_off=False)
_REFINE_CELLS = [8.0, 4.0, 2.0, 1.0]        # refinement sequence (coarse -> fine)


@pytest.fixture(scope="module")
def oblique_refine():
    """Run the theta=45 deg refinement sequence once (coarse -> fine)."""
    return [v2.build_and_run_2d_verification(delr=cs, delc=cs, **_OBLIQUE)
            for cs in _REFINE_CELLS]


def test_oblique_runs_and_conserves_mass(oblique_refine):
    """Every oblique run advects diagonally and conserves mass (~M, lam=0)."""
    for r in oblique_refine:
        assert r.flow_angle_deg == 45.0
        assert r.mass_num == pytest.approx(r.M, rel=0.02)
        # centroid moved along the +45 deg diagonal (both x and y increased)
        assert r.x_cm_num > r.x0 and r.y_cm_num > r.y0


def test_oblique_crossflow_dispersion_is_real_not_subcell(oblique_refine, coarse):
    """theta=45 coarse grid: cross-flow sigma_eta is inflated by REAL numerical
    dispersion -- far more than the aligned coarse case (sub-cell only)."""
    coarse_obl = oblique_refine[0]                 # cell = 8 m, theta = 45 deg
    # cross-flow spread strongly inflated vs the exact sqrt(2*DT*t/R)
    assert coarse_obl.sigma_eta_err > 0.30
    # and MUCH larger than the aligned coarse transverse inflation (sub-cell)
    assert coarse_obl.sigma_eta_err > 3.0 * coarse.sigma_y_err
    # KEY: the RAW cell-centre cross-flow moment is itself inflated (genuine
    # numerical dispersion) -- unlike the aligned case where it is grid-indep.
    assert coarse_obl.sigma_eta_centres_num > 1.2 * coarse_obl.sigma_eta_an
    assert coarse.meta["sigma_y_centres_num"] == pytest.approx(
        coarse.sigma_y_an, rel=0.05)


def test_oblique_refinement_removes_the_smearing(oblique_refine):
    """Refining the theta=45 grid monotonically shrinks the cross-flow error
    toward the analytical -- proving the smearing is numerical, not physical."""
    errs = [r.sigma_eta_err for r in oblique_refine]     # cells 8,4,2,1
    # strictly decreasing with refinement
    assert all(errs[i] > errs[i + 1] for i in range(len(errs) - 1))
    # trending toward zero: finest grid is small and << the coarsest
    assert errs[-1] < 0.15
    assert errs[-1] < 0.5 * errs[0]
    # raw cross-flow moment also converges down toward the analytical value
    centres = [r.sigma_eta_centres_num for r in oblique_refine]
    assert all(centres[i] > centres[i + 1] for i in range(len(centres) - 1))
    assert centres[-1] == pytest.approx(oblique_refine[-1].sigma_eta_an, rel=0.10)
