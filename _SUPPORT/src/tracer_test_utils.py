"""
Tracer test analysis utilities for the transport calibration notebook.

Provides 1D ADE moment analysis functions for evaluating conservative
tracer breakthrough curves (BTCs) from multiple observation wells.

Functions:
    temporal_moment      — Compute the n-th temporal moment of a BTC
    estimate_transport_params — Derive v, n_e, D_L, alpha_L from moments
    analytical_btc       — 1D ADE pulse solution (for fitted curves)
    analyze_all_wells    — Moment analysis on multiple wells
    plot_all_wells_raw   — Raw BTC plot for all wells
    plot_all_wells_fitted — BTCs with fitted analytical curves
    summarize_results    — Print summary table of transport parameters
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


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
