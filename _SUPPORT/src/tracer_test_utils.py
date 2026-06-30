"""
Tracer test analysis utilities for the transport calibration notebook.

Provides 1D ADE moment analysis functions for evaluating conservative
tracer breakthrough curves (BTCs) from multiple observation wells.

Functions:
    temporal_moment      — Compute the n-th temporal moment of a BTC
    estimate_transport_params — Derive v, n_e, D_L, alpha_L from moments
    analytical_btc       — 1D ADE pulse solution (for fitted curves)
    ogata_banks_btc      — 1D ADE continuous first-type (Ogata-Banks 1961) BTC
    build_and_run_1d_verification — Tiny MF6 GWF+GWT scheme-verification toy
    analyze_all_wells    — Moment analysis on multiple wells
    plot_all_wells_raw   — Raw BTC plot for all wells
    plot_all_wells_fitted — BTCs with fitted analytical curves
    summarize_results    — Print summary table of transport parameters
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.special import erfc, erfcx


# ---------------------------------------------------------------------------
# Moment analysis
# ---------------------------------------------------------------------------

def temporal_moment(time, concentration, order=0):
    """
    Compute the n-th temporal moment of a breakthrough curve.

    Uses trapezoidal integration: M_n = integral t^n * C(t) dt.

    Parameters
    ----------
    time : array-like
        Time values [d].
    concentration : array-like
        Concentration values [mg/L or arbitrary].
    order : int, default 0
        Moment order (0 = zeroth, 1 = first, 2 = second).

    Returns
    -------
    float
        The n-th temporal moment.
    """
    t = np.asarray(time, dtype=float)
    c = np.asarray(concentration, dtype=float)
    _trapz = getattr(np, 'trapezoid', np.trapz)  # numpy ≥ 2.0 compat
    return float(_trapz(t**order * c, t))


def estimate_transport_params(m0, m1, m2, x_m, q_darcy=None):
    """
    Derive transport parameters from temporal moments.

    Given the zeroth, first, and second temporal moments of a BTC
    measured at distance x from the injection point:

        t_bar = M1 / M0               (mean arrival time)
        v     = x / t_bar             (seepage velocity)
        n_e   = q / v                 (if Darcy flux q is given)
        sigma2_t = M2/M0 - t_bar**2   (temporal variance)
        sigma2_x = v**2 * sigma2_t    (spatial variance)
        alpha_L  = sigma2_x / (2 * x) (longitudinal dispersivity)
        D_L      = alpha_L * v        (dispersion coefficient)

    Parameters
    ----------
    m0 : float
        Zeroth moment (integral of C dt).
    m1 : float
        First moment (integral of t*C dt).
    m2 : float
        Second moment (integral of t^2 * C dt).
    x_m : float
        Distance from injection to observation [m].
    q_darcy : float, optional
        Darcy flux [m/d]. If given, effective porosity is estimated.

    Returns
    -------
    dict with keys:
        t_bar_d     : mean arrival time [d]
        v_md        : seepage velocity [m/d]
        n_e         : effective porosity [-]  (None if q_darcy not given)
        sigma2_t_d2 : temporal variance [d²]
        sigma2_x_m2 : spatial variance [m²]
        D_L_m2d     : longitudinal dispersion coefficient [m²/d]
        alpha_L_m   : longitudinal dispersivity [m]
    """
    t_bar = m1 / m0
    v = x_m / t_bar
    sigma2_t = m2 / m0 - t_bar**2
    sigma2_x = v**2 * sigma2_t
    alpha_L = sigma2_x / (2.0 * x_m)
    D_L = alpha_L * v

    n_e = q_darcy / v if q_darcy is not None else None

    return {
        "t_bar_d": t_bar,
        "v_md": v,
        "n_e": n_e,
        "sigma2_t_d2": sigma2_t,
        "sigma2_x_m2": sigma2_x,
        "D_L_m2d": D_L,
        "alpha_L_m": alpha_L,
    }


# ---------------------------------------------------------------------------
# Analytical 1D ADE pulse solution
# ---------------------------------------------------------------------------

def analytical_btc(time, x, v, D_L, M, A, n_e):
    """
    Flux-averaged 1D ADE solution for an instantaneous pulse injection.

    C_f(x,t) = (M / A) * x / (n_e * sqrt(4 * pi * D_L * t^3)) *
               exp(-(x - v*t)^2 / (4 * D_L * t))

    This is the concentration measured at a well screen (flux-averaged).
    Its temporal moments are exact:  t_bar = x/v,  sigma^2 = 2*D_L*x/v^3.

    Parameters
    ----------
    time : array-like
        Time since injection [d].
    x : float
        Distance from injection [m].
    v : float
        Seepage velocity [m/d].
    D_L : float
        Longitudinal dispersion coefficient [m²/d].
    M : float
        Injected mass [g].
    A : float
        Cross-sectional area [m²].
    n_e : float
        Effective porosity [-].

    Returns
    -------
    np.ndarray
        Concentration [g/m³ = mg/L] at each time.
    """
    t = np.asarray(time, dtype=float)
    c = np.zeros_like(t)
    pos = t > 0
    t_pos = t[pos]
    c[pos] = ((M / A) * x / (n_e * np.sqrt(4.0 * np.pi * D_L * t_pos**3))
              * np.exp(-(x - v * t_pos)**2 / (4.0 * D_L * t_pos)))
    return c


# ---------------------------------------------------------------------------
# Analytical 1D ADE continuous first-type (Ogata-Banks 1961) solution
# ---------------------------------------------------------------------------

def ogata_banks_btc(x, t, v, alpha_L, D_m=8.64e-5, c0=1.0):
    """
    Two-term first-type (Dirichlet) Ogata-Banks (1961) solution.

    Continuous constant-concentration source C(0, t) = c0 on a 1D
    semi-infinite column with uniform seepage velocity v:

        C/C0 = 1/2 * erfc[(x - v t) / (2 sqrt(D_L t))]
             + 1/2 * exp(v x / D_L) * erfc[(x + v t) / (2 sqrt(D_L t))]

    with the longitudinal dispersion coefficient

        D_L = alpha_L * v + D_m.

    Numerical stability
    -------------------
    The ``exp(v x / D_L)`` prefactor of the second term overflows at field
    Peclet numbers.  It is evaluated via the scaled complementary error
    function ``erfcx(z) = exp(z^2) erfc(z)`` using the combined-exponent
    identity

        exp(v x / D_L) * erfc[(x + v t) / (2 sqrt(D_L t))]
            = erfcx[(x + v t) / (2 sqrt(D_L t))]
              * exp[-(x - v t)^2 / (4 D_L t)],

    so no positive exponent is ever formed (the companion exponent
    ``-(x - v t)^2 / (4 D_L t)`` is always <= 0 and ``erfcx`` is bounded for
    non-negative arguments).

    Parameters
    ----------
    x : float
        Distance from the inlet [m].
    t : array-like or float
        Time(s) since the source switched on [d].  ``t = 0`` returns 0.
    v : float
        Seepage velocity [m/d].
    alpha_L : float
        Longitudinal dispersivity [m].
    D_m : float, default 8.64e-5
        Effective molecular diffusion coefficient [m²/d]
        (8.64e-5 m²/d ~ 1e-9 m²/s).
    c0 : float, default 1.0
        Source concentration [-] or [mg/L].

    Returns
    -------
    np.ndarray or float
        C/C0 (scaled by ``c0``) at each time.  Scalar in, scalar out.

    Notes
    -----
    Units follow the course convention: model days and metres
    (v in m/d, alpha_L in m, D_m in m²/d).
    """
    D_L = alpha_L * v + D_m
    t_arr = np.asarray(t, dtype=float)
    scalar_in = t_arr.ndim == 0
    t_arr = np.atleast_1d(t_arr)

    c = np.zeros_like(t_arr)
    pos = t_arr > 0.0
    tp = t_arr[pos]

    denom = 2.0 * np.sqrt(D_L * tp)
    arg1 = (x - v * tp) / denom
    arg2 = (x + v * tp) / denom

    # First term: standard erfc, always well behaved.
    term1 = 0.5 * erfc(arg1)
    # Second term: combined-exponent identity, overflow-free.
    term2 = 0.5 * erfcx(arg2) * np.exp(-(x - v * tp) ** 2 / (4.0 * D_L * tp))

    c[pos] = c0 * (term1 + term2)

    if scalar_in:
        return float(c[0])
    return c


# ---------------------------------------------------------------------------
# 1D MF6 GWF+GWT scheme-verification toy (recovers the Ogata-Banks setup)
# ---------------------------------------------------------------------------

def _find_mf6_exe():
    """Locate the MODFLOW 6 executable (flopy bindir, then PATH)."""
    import os
    cand = os.path.expanduser("~/.local/share/flopy/bin/mf6")
    if os.path.exists(cand):
        return cand
    return "mf6"


def build_and_run_1d_verification(
    v=1.5,
    alpha_L=10.0,
    n_e=0.20,
    D_m=8.64e-5,
    x_obs=200.0,
    total_time=300.0,
    workspace=None,
):
    """
    Build, run, and observe a tiny 1D MF6 GWF+GWT model reproducing the
    first-type Ogata-Banks setup, so the ADV/DSP scheme can be verified.

    Design choices (rung 1 of the 08t keystone scheme check)
    --------------------------------------------------------
    * 1D row of confined cells, uniform flow.  K and the head gradient are
      chosen so the simulated seepage velocity q / n_e equals ``v`` (the
      recovered v is asserted to within ~1%).
    * First-type inlet: a ``ModflowGwtcnc`` cell pins C = c0 = 1 at the first
      interior cell, matching the analytic Dirichlet boundary at x = 0.  The
      observation cell sits ``x_obs`` downstream, so the half-cell offset
      between the cell-centred CNC and the analytic x = 0 inlet is negligible.
    * The domain is kept long enough that the front never reaches the
      downstream boundary within ``total_time`` (semi-infinite proxy).
    * Δx <= alpha_L so the grid Peclet number Δx / alpha_L <= ~1 (well
      resolved — this is a scheme check, not a grid-Peclet stress test).
    * ADV scheme = 'TVD'; nstp sized so the Courant number Cr = v dt / Δx <= 1.
    * MST porosity = n_e; DSP alh = alpha_L and diffc = D_m, so the MF6
      dispersion coefficient D = alpha_L * v + D_m matches the analytic D_L.

    Parameters
    ----------
    v : float, default 1.5
        Target seepage velocity [m/d].
    alpha_L : float, default 10.0
        Longitudinal dispersivity [m].
    n_e : float, default 0.20
        Effective porosity [-].
    D_m : float, default 8.64e-5
        Effective molecular diffusion coefficient [m²/d].
    x_obs : float, default 200.0
        Distance from the inlet (CNC cell) to the observation cell [m].
        Rounded to the nearest cell if not a multiple of Δx.
    total_time : float, default 300.0
        Total simulated time [d].
    workspace : str or Path, optional
        Model workspace directory.  Defaults to a ``ob1d_verification``
        folder under the course data directory.

    Returns
    -------
    times : np.ndarray
        Observation times [d].
    c_over_c0 : np.ndarray
        Simulated C/C0 at the observation cell [-].
    """
    import os
    import shutil
    import flopy

    if workspace is None:
        workspace = os.path.expanduser(
            "~/applied_groundwater_modelling_data/limmat/ob1d_verification"
        )
    workspace = str(workspace)
    if os.path.isdir(workspace):
        shutil.rmtree(workspace)
    os.makedirs(workspace, exist_ok=True)

    exe = _find_mf6_exe()
    c0 = 1.0

    # -- Spatial discretisation -------------------------------------------
    # Δx <= alpha_L  -> grid Peclet <= 1 (use half a dispersivity for margin).
    delx = max(min(alpha_L / 2.0, alpha_L), 1.0)
    D_L = alpha_L * v + D_m

    inlet_col = 1                       # first interior cell (CNC)
    n_obs_cells = int(round(x_obs / delx))
    obs_col = inlet_col + n_obs_cells
    x_distance = n_obs_cells * delx     # exact analytic x for ogata_banks_btc

    # Domain long enough that the front stays away from the downstream BC.
    front_reach = v * total_time + 6.0 * np.sqrt(D_L * total_time)
    domain_len = max(x_distance + 5.0 * alpha_L, front_reach) + 10.0 * delx
    ncol = int(np.ceil(domain_len / delx)) + 1
    obs_col = min(obs_col, ncol - 2)

    # -- Flow geometry: confined, single layer/row ------------------------
    K = 10.0                            # m/d (arbitrary; gradient absorbs it)
    top = 10.0
    botm = 0.0
    grad = (v * n_e) / K                # i = q / K, with q = v * n_e
    head_drop = grad * (ncol * delx)
    h_right = top + 5.0                 # keep confined (artesian, h > top)
    h_left = h_right + head_drop

    # -- Time discretisation: Cr = v dt / Δx <= 1 -------------------------
    nstp = int(np.ceil(1.2 * v * total_time / delx))
    nstp = max(nstp, 1)
    dt = total_time / nstp
    cr = v * dt / delx

    # -- Simulation + shared TDIS -----------------------------------------
    sim = flopy.mf6.MFSimulation(
        sim_name="ob1d", sim_ws=workspace, exe_name=exe,
        verbosity_level=0,
    )
    flopy.mf6.ModflowTdis(
        sim, time_units="DAYS", nper=1,
        perioddata=[(total_time, nstp, 1.0)],
    )

    # -- GWF model --------------------------------------------------------
    gwf_name = "gwf"
    gwf = flopy.mf6.ModflowGwf(sim, modelname=gwf_name, save_flows=True)
    flopy.mf6.ModflowIms(
        sim, complexity="SIMPLE", linear_acceleration="BICGSTAB",
        outer_dvclose=1e-8, inner_dvclose=1e-9, filename=f"{gwf_name}.ims",
    )
    sim.register_ims_package(sim.get_package(f"{gwf_name}.ims"), [gwf_name])

    flopy.mf6.ModflowGwfdis(
        gwf, length_units="METERS", nlay=1, nrow=1, ncol=ncol,
        delr=delx, delc=1.0, top=top, botm=botm,
    )
    flopy.mf6.ModflowGwfic(gwf, strt=h_left)
    flopy.mf6.ModflowGwfnpf(
        gwf, icelltype=0, k=K, save_flows=True, save_specific_discharge=True,
    )
    chd_spd = [
        [(0, 0, 0), h_left],
        [(0, 0, ncol - 1), h_right],
    ]
    flopy.mf6.ModflowGwfchd(gwf, stress_period_data=chd_spd)
    flopy.mf6.ModflowGwfoc(
        gwf, head_filerecord=f"{gwf_name}.hds",
        budget_filerecord=f"{gwf_name}.cbc",
        saverecord=[("HEAD", "LAST"), ("BUDGET", "LAST")],
    )

    # -- GWT model --------------------------------------------------------
    gwt_name = "gwt"
    gwt = flopy.mf6.ModflowGwt(sim, modelname=gwt_name, save_flows=True)
    flopy.mf6.ModflowIms(
        sim, complexity="SIMPLE", linear_acceleration="BICGSTAB",
        outer_dvclose=1e-8, inner_dvclose=1e-9, filename=f"{gwt_name}.ims",
    )
    sim.register_ims_package(sim.get_package(f"{gwt_name}.ims"), [gwt_name])

    flopy.mf6.ModflowGwtdis(
        gwt, length_units="METERS", nlay=1, nrow=1, ncol=ncol,
        delr=delx, delc=1.0, top=top, botm=botm,
    )
    flopy.mf6.ModflowGwtic(gwt, strt=0.0)
    flopy.mf6.ModflowGwtmst(gwt, porosity=n_e)
    flopy.mf6.ModflowGwtadv(gwt, scheme="TVD")
    # MF6 dispersion: D = alh * v + diffc  -> matches analytic D_L.
    flopy.mf6.ModflowGwtdsp(gwt, alh=alpha_L, ath1=0.0, diffc=D_m)
    # SSM required because GWF carries flow boundary packages (CHD).  No AUX
    # concentration -> CHD inflow enters at C = 0, outflow leaves at cell C.
    flopy.mf6.ModflowGwtssm(gwt, sources=[[]])
    # First-type inlet: pin C = c0 at the first interior cell.
    flopy.mf6.ModflowGwtcnc(
        gwt, stress_period_data=[[(0, 0, inlet_col), c0]],
    )
    flopy.mf6.ModflowGwtoc(
        gwt, concentration_filerecord=f"{gwt_name}.ucn",
        saverecord=[("CONCENTRATION", "ALL")],
    )

    # -- Couple flow -> transport -----------------------------------------
    flopy.mf6.ModflowGwfgwt(
        sim, exgtype="GWF6-GWT6", exgmnamea=gwf_name, exgmnameb=gwt_name,
    )

    sim.write_simulation(silent=True)
    success, _ = sim.run_simulation(silent=True)
    if not success:
        raise RuntimeError("MF6 1D verification run did not converge.")

    # -- Recover seepage velocity and assert within ~1% -------------------
    spdis = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    qx_obs = float(spdis["qx"][obs_col])
    v_sim = abs(qx_obs) / n_e
    rel_err_v = abs(v_sim - v) / v
    if rel_err_v > 0.01:
        raise AssertionError(
            f"Recovered seepage velocity {v_sim:.4f} m/d deviates "
            f"{100 * rel_err_v:.2f}% from target {v:.4f} m/d (>1%)."
        )

    # -- Extract the observed BTC -----------------------------------------
    cobj = gwt.output.concentration()
    ts = cobj.get_ts((0, 0, obs_col))
    times = ts[:, 0]
    c_over_c0 = ts[:, 1] / c0

    # Stash the resolved discretisation for callers/tests.
    build_and_run_1d_verification.last_meta = {
        "delx": delx,
        "ncol": ncol,
        "obs_col": obs_col,
        "x_distance": x_distance,
        "D_L": D_L,
        "v_sim": v_sim,
        "rel_err_v": rel_err_v,
        "nstp": nstp,
        "dt": dt,
        "Cr": cr,
        "grid_Pe": delx / alpha_L,
        "workspace": workspace,
    }

    return times, c_over_c0


# ---------------------------------------------------------------------------
# Batch analysis
# ---------------------------------------------------------------------------

def analyze_all_wells(df, q_darcy):
    """
    Run moment analysis on all observation wells in a tracer test dataset.

    Parameters
    ----------
    df : pd.DataFrame
        Long-format BTC data with columns:
        ``time_d``, ``well_id``, ``distance_m``, ``concentration_mg_L``.
    q_darcy : float
        Darcy flux [m/d].

    Returns
    -------
    pd.DataFrame
        One row per well with columns: well_id, distance_m, t_bar_d,
        v_md, n_e, alpha_L_m, D_L_m2d.
    dict
        ``{well_id: params_dict}`` — full parameter estimates for each well.
    """
    rows = []
    params = {}
    for well_id, grp in df.groupby("well_id"):
        t = grp["time_d"].values
        c = grp["concentration_mg_L"].values
        x = grp["distance_m"].iloc[0]

        m0 = temporal_moment(t, c, order=0)
        m1 = temporal_moment(t, c, order=1)
        m2 = temporal_moment(t, c, order=2)

        p = estimate_transport_params(m0, m1, m2, x, q_darcy=q_darcy)

        rows.append({
            "well_id": well_id,
            "distance_m": x,
            "t_bar_d": round(p["t_bar_d"], 2),
            "v_md": round(p["v_md"], 2),
            "n_e": round(p["n_e"], 4) if p["n_e"] is not None else None,
            "alpha_L_m": round(p["alpha_L_m"], 2),
            "D_L_m2d": round(p["D_L_m2d"], 1),
        })
        params[well_id] = p

    results = pd.DataFrame(rows)
    return results, params


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

WELL_COLORS = {
    "MW-1": "#1f77b4",
    "MW-2": "#ff7f0e",
    "MW-3": "#2ca02c",
}


def _get_color(well_id):
    return WELL_COLORS.get(well_id, "gray")


def plot_all_wells_raw(df, title="Tracer Test — Breakthrough Curves"):
    """
    Plot concentration vs time for all observation wells.

    Parameters
    ----------
    df : pd.DataFrame
        Long-format data with ``time_d``, ``well_id``, ``distance_m``,
        ``concentration_mg_L``.
    title : str
        Figure title.

    Returns
    -------
    fig, ax
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    for well_id, grp in df.groupby("well_id"):
        x = grp["distance_m"].iloc[0]
        ax.plot(
            grp["time_d"], grp["concentration_mg_L"],
            "o-", markersize=2, linewidth=0.8,
            color=_get_color(well_id),
            label=f"{well_id} (x = {x:.0f} m)",
        )
    ax.set_xlabel("Time [d]")
    ax.set_ylabel("Concentration [mg/L]")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_all_wells_fitted(df, params, results_df, M, A):
    """
    Plot BTCs with fitted analytical curves, one panel per well.

    Parameters
    ----------
    df : pd.DataFrame
        Raw BTC data (long format).
    params : dict
        ``{well_id: params_dict}`` from ``analyze_all_wells``.
    results_df : pd.DataFrame
        Results table from ``analyze_all_wells``.
    M : float
        Injected mass [g].
    A : float
        Cross-sectional area [m²].

    Returns
    -------
    fig, axes
    """
    well_ids = sorted(params.keys())
    n = len(well_ids)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 4))
    if n == 1:
        axes = [axes]

    for i, wid in enumerate(well_ids):
        grp = df[df["well_id"] == wid]
        x = grp["distance_m"].iloc[0]
        p = params[wid]
        row = results_df[results_df["well_id"] == wid].iloc[0]

        # Observed data
        axes[i].plot(
            grp["time_d"], grp["concentration_mg_L"],
            "o", markersize=3, alpha=0.5,
            color=_get_color(wid), label="Observed",
        )

        # Fitted analytical curve
        t_fit = np.linspace(0.01, grp["time_d"].max(), 500)
        c_fit = analytical_btc(t_fit, x, p["v_md"], p["D_L_m2d"], M, A, p["n_e"])
        axes[i].plot(
            t_fit, c_fit, "-", color="black", linewidth=1.5,
            label=f"Fitted (v={row['v_md']:.1f} m/d)",
        )

        # Annotation
        axes[i].text(
            0.95, 0.95,
            f"v = {row['v_md']:.1f} m/d\n"
            f"n_e = {row['n_e']:.3f}\n"
            f"aL = {row['alpha_L_m']:.1f} m",
            transform=axes[i].transAxes, fontsize=9,
            verticalalignment="top", horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.7),
        )

        axes[i].set_xlabel("Time [d]")
        axes[i].set_ylabel("Concentration [mg/L]")
        axes[i].set_title(f"{wid} (x = {x:.0f} m)")
        axes[i].legend(fontsize=8)
        axes[i].grid(True, alpha=0.3)

    fig.tight_layout()
    return fig, axes


def summarize_results(results_df):
    """
    Print a formatted summary table of moment-analysis results.

    Parameters
    ----------
    results_df : pd.DataFrame
        Output of ``analyze_all_wells``.
    """
    print("=" * 72)
    print("TRACER TEST — MOMENT ANALYSIS SUMMARY")
    print("=" * 72)
    print(
        f"{'Well':<8} {'x [m]':>6} {'t_bar [d]':>10} "
        f"{'v [m/d]':>10} {'n_e [-]':>10} {'aL [m]':>8} {'D_L [m2/d]':>10}"
    )
    print("-" * 72)
    for _, row in results_df.iterrows():
        n_e_str = f"{row['n_e']:.4f}" if row['n_e'] is not None else "—"
        print(
            f"{row['well_id']:<8} {row['distance_m']:>6.0f} "
            f"{row['t_bar_d']:>10.2f} "
            f"{row['v_md']:>10.2f} {n_e_str:>10} "
            f"{row['alpha_L_m']:>8.2f} {row['D_L_m2d']:>10.1f}"
        )
    print("-" * 72)
    print(
        f"{'Mean':<8} {'':>6} {'':>10} "
        f"{results_df['v_md'].mean():>10.2f} "
        f"{results_df['n_e'].mean():>10.4f} "
        f"{results_df['alpha_L_m'].mean():>8.2f} "
        f"{results_df['D_L_m2d'].mean():>10.1f}"
    )
    print(
        f"{'Std':<8} {'':>6} {'':>10} "
        f"{results_df['v_md'].std():>10.2f} "
        f"{results_df['n_e'].std():>10.4f} "
        f"{results_df['alpha_L_m'].std():>8.2f} "
        f"{results_df['D_L_m2d'].std():>10.1f}"
    )
    print("=" * 72)
