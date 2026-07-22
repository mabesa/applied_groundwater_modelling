"""
Pumping test analysis utilities for the calibration notebook.

Provides Cooper-Jacob straight-line analysis functions for evaluating
pumping test data from multiple observation wells.

Functions:
    cooper_jacob_fit     — Fit straight line to semi-log drawdown data
    estimate_T_S         — Calculate T and S from Cooper-Jacob slope/intercept
    analyze_all_wells    — Run Cooper-Jacob analysis on multiple wells
    plot_semilog         — Semi-log plot of drawdown vs time (one well)
    plot_all_wells_raw   — Raw drawdown vs time for all wells
    plot_all_wells_cj    — Semi-log Cooper-Jacob plots for all wells
    summarize_results    — Print summary table of T, S, K from all wells
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import linregress


def cooper_jacob_fit(time_min, drawdown_m, t_start_min=None):
    """
    Fit the Cooper-Jacob straight line to semi-log drawdown data.

    Fits s = a + b * log10(t), where:
        b = Δs per log cycle = 2.3 Q / (4 π T)
        a = intercept → used to find t₀ (zero-drawdown time)

    Parameters
    ----------
    time_min : array-like
        Time since pumping started [minutes].
    drawdown_m : array-like
        Measured drawdown [m].
    t_start_min : float, optional
        Start time for the straight-line fit [minutes].
        If None, uses the first 30 % of data as early-time exclusion.

    Returns
    -------
    dict with keys:
        slope        : Δs per log₁₀ cycle [m]
        intercept    : regression intercept [m]
        t0_min       : zero-drawdown intercept time [minutes]
        r_squared    : R² of the linear fit
        t_start_min  : actual start time used for fitting
        mask         : boolean array — True where data was used in fit
    """
    t = np.asarray(time_min, dtype=float)
    s = np.asarray(drawdown_m, dtype=float)

    if t_start_min is None:
        # Default: use data from the last 70 % (log-time range)
        log_range = np.log10(t.max()) - np.log10(t.min())
        t_start_min = 10 ** (np.log10(t.min()) + 0.3 * log_range)

    mask = t >= t_start_min
    if mask.sum() < 3:
        raise ValueError(
            f"Only {mask.sum()} points after t_start={t_start_min:.1f} min — "
            "need at least 3 for a regression."
        )

    log_t = np.log10(t[mask])
    s_fit = s[mask]

    result = linregress(log_t, s_fit)
    slope = result.slope       # Δs per log10 cycle
    intercept = result.intercept

    # t₀: time at which the fitted line gives s = 0
    # 0 = intercept + slope * log10(t0)  →  log10(t0) = -intercept / slope
    if slope > 0:
        t0_min = 10 ** (-intercept / slope)
    else:
        t0_min = np.nan

    return {
        "slope": slope,
        "intercept": intercept,
        "t0_min": t0_min,
        "r_squared": result.rvalue ** 2,
        "t_start_min": t_start_min,
        "mask": mask,
    }


def estimate_T_S(slope, t0_min, Q_m3d, r_m):
    """
    Calculate transmissivity T and storativity S from Cooper-Jacob parameters.

    T = 2.3 Q / (4 π Δs)
    S = 2.25 T t₀ / r²    (t₀ in days)

    Parameters
    ----------
    slope : float
        Δs per log₁₀ cycle [m] (from ``cooper_jacob_fit``).
    t0_min : float
        Zero-drawdown intercept time [minutes].
    Q_m3d : float
        Pumping rate [m³/d].
    r_m : float
        Distance from pumping well to observation well [m].

    Returns
    -------
    T : float
        Transmissivity [m²/d].
    S : float
        Storativity [-].
    """
    T = 2.3 * Q_m3d / (4.0 * np.pi * slope)
    t0_day = t0_min / (24 * 60)
    S = 2.25 * T * t0_day / r_m ** 2
    return T, S


def analyze_all_wells(df, Q_m3d, b_m, t_start_overrides=None):
    """
    Run Cooper-Jacob analysis on all observation wells in a pumping test dataset.

    Parameters
    ----------
    df : pd.DataFrame
        Long-format pumping test data with columns:
        ``time_min``, ``well_id``, ``distance_m``, ``drawdown_m``.
    Q_m3d : float
        Pumping rate [m³/d].
    b_m : float
        Aquifer thickness at test site [m].
    t_start_overrides : dict, optional
        ``{well_id: t_start_min}`` to override the automatic start-time
        selection for specific wells.

    Returns
    -------
    pd.DataFrame
        One row per well with columns: well_id, distance_m, slope, t0_min,
        T_m2d, S, K_md, r_squared.
    dict
        ``{well_id: fit_dict}`` — full fit results for each well (for plotting).
    """
    if t_start_overrides is None:
        t_start_overrides = {}

    rows = []
    fits = {}
    for well_id, grp in df.groupby("well_id"):
        t = grp["time_min"].values
        s = grp["drawdown_m"].values
        r = grp["distance_m"].iloc[0]
        t_start = t_start_overrides.get(well_id, None)

        fit = cooper_jacob_fit(t, s, t_start_min=t_start)
        T, S = estimate_T_S(fit["slope"], fit["t0_min"], Q_m3d, r)
        K = T / b_m

        rows.append({
            "well_id": well_id,
            "distance_m": r,
            "slope": round(fit["slope"], 4),
            "t0_min": round(fit["t0_min"], 3),
            "T_m2d": round(T, 1),
            "S": round(S, 6),
            "K_md": round(K, 2),
            "r_squared": round(fit["r_squared"], 4),
        })
        fits[well_id] = fit

    results = pd.DataFrame(rows)
    return results, fits


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

WELL_COLORS = {
    "OW-1": "#1f77b4",
    "OW-2": "#ff7f0e",
    "OW-3": "#2ca02c",
    "OW-4": "#d62728",
}


def _get_color(well_id):
    return WELL_COLORS.get(well_id, "gray")


def plot_all_wells_raw(df, title="Pumping Test — Drawdown vs. Time"):
    """
    Plot drawdown vs time for all observation wells on a single figure.

    Parameters
    ----------
    df : pd.DataFrame
        Long-format data with ``time_min``, ``well_id``, ``distance_m``, ``drawdown_m``.
    title : str
        Figure title.

    Returns
    -------
    fig, ax
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    for well_id, grp in df.groupby("well_id"):
        r = grp["distance_m"].iloc[0]
        ax.plot(
            grp["time_min"], grp["drawdown_m"],
            "o-", markersize=2, linewidth=0.8,
            color=_get_color(well_id),
            label=f"{well_id} (r = {r:.0f} m)",
        )
    ax.set_xlabel("Time [min]")
    ax.set_ylabel("Drawdown [m]")
    ax.set_title(title)
    ax.legend()
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_semilog(time_min, drawdown_m, fit, well_id="", r_m=None, ax=None):
    """
    Semi-log plot (s vs log₁₀ t) for one well with Cooper-Jacob fit line.

    Parameters
    ----------
    time_min, drawdown_m : array-like
        Observed data.
    fit : dict
        Output of ``cooper_jacob_fit``.
    well_id : str
        Label for the well.
    r_m : float, optional
        Distance (shown in title).
    ax : matplotlib.axes.Axes, optional
        Axes to plot on.  If None, creates a new figure.

    Returns
    -------
    ax
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))

    t = np.asarray(time_min)
    s = np.asarray(drawdown_m)
    col = _get_color(well_id)
    mask = np.asarray(fit["mask"], dtype=bool)

    # Two point styles, made explicit in the legend so they read as a teaching
    # cue rather than an unexplained change: the Cooper-Jacob straight line is
    # only valid at late time, so early-time points are EXCLUDED from the fit
    # (faint, small) while the points USED for the fit are solid and larger.
    if (~mask).any():
        ax.semilogx(t[~mask], s[~mask], "o", markersize=3, alpha=0.4,
                    color=col, label="excluded (early time)")
    ax.semilogx(t[mask], s[mask], "o", markersize=4, color=col,
                label="used for fit")

    # Fitted line
    t_line = np.logspace(np.log10(t.min()), np.log10(t.max()), 200)
    s_line = fit["intercept"] + fit["slope"] * np.log10(t_line)
    ax.semilogx(t_line, s_line, "--", color="black", linewidth=1.5,
                label=f"CJ fit (R²={fit['r_squared']:.4f})")

    # y-axis: always show 0 (pre-pumping drawdown) with a clear zero reference line
    finite = s[np.isfinite(s)]
    y_lo = min(0.0, float(finite.min())) if finite.size else 0.0
    y_hi = float(finite.max()) if finite.size else 1.0
    pad = 0.06 * (y_hi - y_lo) if y_hi > y_lo else 0.1
    if finite.size:  # guard the all-NaN case: set_ylim(NaN) would raise
        ax.set_ylim(y_lo - pad, y_hi + pad)
        ax.axhline(0.0, color="0.35", linewidth=1.0, zorder=0)

    # Mark t₀ (zero-drawdown intercept). Black label with a legible backing box,
    # anchored just above the x-axis at the t₀ line so it stays visible in every
    # panel (the previous gray label at y=-0.1 was clipped for small-t₀ wells).
    if np.isfinite(fit["t0_min"]):
        ax.axvline(fit["t0_min"], color="0.4", linestyle=":", linewidth=1.2)
        ax.annotate(
            f"t₀ = {fit['t0_min']:.2f} min",
            xy=(fit["t0_min"], y_lo - pad), xycoords="data",
            xytext=(3, 3), textcoords="offset points",
            fontsize=8, color="black", ha="left", va="bottom",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                      edgecolor="0.6", alpha=0.85),
        )

    label = well_id
    if r_m is not None:
        label += f" (r = {r_m:.0f} m)"
    ax.set_xlabel("Time [min]")
    ax.set_ylabel("Drawdown [m]")
    ax.set_title(f"Cooper-Jacob Analysis — {label}")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, which="both", alpha=0.3)
    return ax


def plot_all_wells_cj(df, fits, results_df):
    """
    Create a 2×2 panel of semi-log Cooper-Jacob plots, one per well.

    Parameters
    ----------
    df : pd.DataFrame
        Raw pumping test data (long format).
    fits : dict
        ``{well_id: fit_dict}`` from ``analyze_all_wells``.
    results_df : pd.DataFrame
        Results table from ``analyze_all_wells``.

    Returns
    -------
    fig, axes
    """
    well_ids = sorted(fits.keys())
    n = len(well_ids)
    ncols = min(n, 2)
    nrows = (n + 1) // 2
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4.5 * nrows))
    if n == 1:
        axes = np.array([axes])
    axes = axes.flatten()

    for i, wid in enumerate(well_ids):
        grp = df[df["well_id"] == wid]
        r = grp["distance_m"].iloc[0]
        row = results_df[results_df["well_id"] == wid].iloc[0]
        plot_semilog(
            grp["time_min"].values, grp["drawdown_m"].values,
            fits[wid], well_id=wid, r_m=r, ax=axes[i],
        )
        # T/K/S annotation — placed in the empty UPPER-LEFT corner (early time,
        # high drawdown never occurs) so it never overlaps the data or the
        # lower-right legend.
        axes[i].text(
            0.02, 0.98,
            f"T = {row['T_m2d']:.0f} m²/d\nK = {row['K_md']:.1f} m/d\nS = {row['S']:.2e}",
            transform=axes[i].transAxes, fontsize=9,
            verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.85),
        )

    # Hide unused axes
    for j in range(n, len(axes)):
        axes[j].set_visible(False)

    fig.tight_layout()
    return fig, axes


def summarize_results(results_df):
    """
    Print a formatted summary table of Cooper-Jacob results across wells.

    Parameters
    ----------
    results_df : pd.DataFrame
        Output of ``analyze_all_wells``.
    """
    print("=" * 72)
    print("COOPER-JACOB ANALYSIS — SUMMARY")
    print("=" * 72)
    print(
        f"{'Well':<8} {'r [m]':>6} {'Δs [m]':>8} {'t₀ [min]':>10} "
        f"{'T [m²/d]':>10} {'S [-]':>10} {'K [m/d]':>8} {'R²':>8}"
    )
    print("-" * 72)
    for _, row in results_df.iterrows():
        print(
            f"{row['well_id']:<8} {row['distance_m']:>6.0f} "
            f"{row['slope']:>8.3f} {row['t0_min']:>10.3f} "
            f"{row['T_m2d']:>10.1f} {row['S']:>10.2e} "
            f"{row['K_md']:>8.2f} {row['r_squared']:>8.4f}"
        )
    print("-" * 72)
    print(
        f"{'Mean':<8} {'':>6} {'':>8} {'':>10} "
        f"{results_df['T_m2d'].mean():>10.1f} "
        f"{results_df['S'].mean():>10.2e} "
        f"{results_df['K_md'].mean():>8.2f}"
    )
    print(
        f"{'Std':<8} {'':>6} {'':>8} {'':>10} "
        f"{results_df['T_m2d'].std():>10.1f} "
        f"{results_df['S'].std():>10.2e} "
        f"{results_df['K_md'].std():>8.2f}"
    )
    print("=" * 72)
