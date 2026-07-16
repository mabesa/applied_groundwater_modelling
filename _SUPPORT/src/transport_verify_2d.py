"""
Verify the MODFLOW 6 GWT transport scheme against an EXACT 2D analytical solution.

Self-contained teaching helper (UNGRADED) for the contaminant-transport track.
It pairs an exact closed-form solution for an instantaneous point/line mass
release in a 2D uniform flow field (with retardation ``R`` and first-order decay
``lambda``) with a small, idealized MODFLOW 6 GWF (steady) + GWT (transient)
model built from scratch on a rectangular structured DIS grid.  The numerical
plume is then compared to the analytical plume so students can SEE the scheme
work -- and, on a deliberately coarse grid, see where numerical (transverse)
smearing creeps in.

Physical picture
----------------
An instantaneous mass ``M`` [g] is released at ``t = 0`` at the source point
``(x0, y0)`` over the full aquifer thickness ``m`` [m] (a line source in 3D, a
point in map view).  Groundwater flows uniformly in ``+x`` at seepage velocity
``u = K * i / phi_e`` [m/d].  The plume centre-of-mass travels at ``u / R`` and
spreads by longitudinal / transverse dispersion ``DL = alpha_L*u + Dm`` and
``DT = alpha_T*u + Dm``.

Units: everything is metres / days.  Concentration ``mg/L == g/m^3``, so a mass
``M`` in grams yields concentration directly in ``mg/L``.

OWNERSHIP: this module is standalone.  It does NOT import (or reuse) the doublet
infrastructure in ``transport_base_model`` -- it builds its own flopy DIS / GWF /
GWT from scratch.  It has no dependency on the graded ``PROJECT/workspace`` tree.

Author: Applied Groundwater Modelling Course (transport track, 2D verification).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Union

import numpy as np
import flopy


# ---------------------------------------------------------------------------
# resolve the MODFLOW 6 executable (flopy-installed binary or PATH)
# ---------------------------------------------------------------------------
_MF6_FALLBACK = os.path.expanduser("~/.local/share/flopy/bin/mf6")


def _resolve_mf6(exe_name: Optional[str]) -> str:
    """Return a usable mf6 executable path (explicit -> PATH -> flopy bin)."""
    if exe_name and (shutil.which(exe_name) or os.path.exists(exe_name)):
        return exe_name
    on_path = shutil.which("mf6")
    if on_path:
        return on_path
    if os.path.exists(_MF6_FALLBACK):
        return _MF6_FALLBACK
    raise FileNotFoundError(
        "Could not find a MODFLOW 6 executable (looked at explicit arg, PATH, "
        f"and {_MF6_FALLBACK}).")


# ===========================================================================
# 1. EXACT ANALYTICAL SOLUTION
# ===========================================================================
def plume_2d_instantaneous(
    x: Union[float, np.ndarray],
    y: Union[float, np.ndarray],
    t: float,
    M: float,
    phi_e: float,
    m: float,
    R: float,
    DL: float,
    DT: float,
    u: float,
    lam: float = 0.0,
) -> np.ndarray:
    """Exact concentration of an instantaneous 2D point/line source.

    Implements EXACTLY::

        c(x, y, t) = [ M / (phi_e * R * m) ]
                     / ( 2*pi * sqrt(2*DL*t/R) * sqrt(2*DT*t/R) )
                     * exp( -(x - (u/R)*t)^2 / (4*DL*t/R)
                            -  y^2            / (4*DT*t/R) )
                     * exp(-lambda * t)

    The source is at the origin, so ``x`` and ``y`` are measured RELATIVE to the
    source point ``(x0, y0)``.  The plume centre-of-mass sits at
    ``x = (u/R)*t`` (and ``y = 0``); its variances are
    ``sigma_x^2 = 2*DL*t/R`` and ``sigma_y^2 = 2*DT*t/R``.

    Parameters
    ----------
    x, y : float or ndarray
        Coordinates RELATIVE to the source origin [m].  May be scalars or
        numpy arrays (e.g. from ``np.meshgrid``); broadcast together.
    t : float
        Elapsed time since the release [d].  Must be > 0 (``t <= 0`` returns
        an all-zero field, since a delta release is not yet spread).
    M : float
        Released mass [g] (instantaneous, over the aquifer thickness ``m``).
    phi_e : float
        Effective porosity [-].
    m : float
        Aquifer (saturated) thickness [m].
    R : float
        Retardation factor [-] (``R = 1`` for a conservative tracer).
    DL, DT : float
        Longitudinal / transverse dispersion coefficients [m^2/d]
        (``DL = alpha_L*u + Dm``, ``DT = alpha_T*u + Dm``).
    u : float
        Seepage (linear) velocity [m/d].  The plume peak travels at ``u/R``.
    lam : float, optional
        First-order decay constant [1/d] (``lam = ln2 / half_life``; 0 for a
        conservative solute).

    Returns
    -------
    ndarray
        Concentration [mg/L] (== g/m^3), same broadcast shape as ``x``/``y``.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if t <= 0.0:
        return np.zeros(np.broadcast(x, y).shape)

    # variances of the (retarded) 2D Gaussian
    two_DL_t_R = 2.0 * DL * t / R
    two_DT_t_R = 2.0 * DT * t / R

    prefactor = (M / (phi_e * R * m)) / (
        2.0 * np.pi * np.sqrt(two_DL_t_R) * np.sqrt(two_DT_t_R)
    )
    x_centre = (u / R) * t
    exponent = (
        -((x - x_centre) ** 2) / (4.0 * DL * t / R)
        - (y ** 2) / (4.0 * DT * t / R)
    )
    c = prefactor * np.exp(exponent) * np.exp(-lam * t)
    return c


# ===========================================================================
# 2. MOMENT DIAGNOSTICS (shared by analytical + numerical)
# ===========================================================================
def _field_moments(
    conc: np.ndarray, xc: np.ndarray, yc: np.ndarray, delr: float, delc: float, *,
    phi_e: float, R: float, m: float,
) -> Dict[str, float]:
    """Spatial moments of the (piecewise-constant) numerical concentration field.

    The MODFLOW 6 finite-volume solution is a PIECEWISE-CONSTANT function: each
    cell holds a single value over its whole footprint.  Its exact spatial second
    moment is therefore the cell-centre moment PLUS the within-cell contribution
    (``delr^2/12`` in x, ``delc^2/12`` in y -- the variance of a uniform slab).
    Including this term is what makes the diagnostic honest about coarse-grid
    smearing: a coarse transverse grid cannot represent sub-cell structure, so
    the field it produces genuinely has a wider transverse spread.  On a fine
    grid the term is negligible (delc=1 -> 0.083 m^2).

    Parameters
    ----------
    conc : (nrow, ncol) ndarray
        Concentration [mg/L].
    xc, yc : (nrow, ncol) ndarray
        Cell-centre x / y coordinates [m].
    delr, delc : float
        Cell sizes in x / y [m] (uniform grid).
    phi_e, R, m : float
        Convert the field to a total (aqueous + sorbed) solute mass
        ``Sum c * phi_e * R * m * A_cell`` [g].

    Returns
    -------
    dict with x_cm, y_cm, sigma_x, sigma_y (field second moments),
    sigma_x_centres, sigma_y_centres (raw cell-centre moments), peak_c, mass_g.
    """
    c = np.maximum(np.asarray(conc, dtype=float), 0.0)
    tot = c.sum()
    if tot <= 0.0:
        return dict(x_cm=np.nan, y_cm=np.nan, sigma_x=np.nan, sigma_y=np.nan,
                    sigma_x_centres=np.nan, sigma_y_centres=np.nan,
                    peak_c=0.0, mass_g=0.0)
    x_cm = float((c * xc).sum() / tot)
    y_cm = float((c * yc).sum() / tot)
    var_x = float((c * (xc - x_cm) ** 2).sum() / tot)   # cell-centre variance
    var_y = float((c * (yc - y_cm) ** 2).sum() / tot)
    var_x_field = var_x + delr ** 2 / 12.0              # + within-cell slab variance
    var_y_field = var_y + delc ** 2 / 12.0
    return dict(
        x_cm=x_cm, y_cm=y_cm,
        sigma_x=float(np.sqrt(max(var_x_field, 0.0))),
        sigma_y=float(np.sqrt(max(var_y_field, 0.0))),
        sigma_x_centres=float(np.sqrt(max(var_x, 0.0))),
        sigma_y_centres=float(np.sqrt(max(var_y, 0.0))),
        peak_c=float(c.max()),
        mass_g=float(tot * phi_e * R * m * delr * delc),
    )


def _rotated_sigma(
    conc: np.ndarray, xc: np.ndarray, yc: np.ndarray,
    x_cm: float, y_cm: float, cos_t: float, sin_t: float,
    delr: float, delc: float,
):
    """Along-/cross-flow (rotated) second moments of the numerical field.

    Rotates the cell-centre offsets ``(x-x_cm, y-y_cm)`` into flow-aligned
    coordinates::

        xi  =  dx*cos + dy*sin      (along-flow)
        eta = -dx*sin + dy*cos      (cross-flow)

    and returns the piecewise-constant field second moments ``sigma_xi``,
    ``sigma_eta`` (each including the within-cell slab variance projected onto
    the rotated axis: ``(cos^2*delr^2 + sin^2*delc^2)/12`` for xi, and
    ``(sin^2*delr^2 + cos^2*delc^2)/12`` for eta) plus the RAW cell-centre
    cross-flow moment ``sigma_eta_centres`` (no sub-cell term).

    For ``theta = 0`` (cos=1, sin=0) this reduces exactly to the grid-aligned
    sigma_x / sigma_y (eta axis == grid y).

    Returns
    -------
    (sigma_xi, sigma_eta, sigma_eta_centres) : tuple of float
    """
    c = np.maximum(np.asarray(conc, dtype=float), 0.0)
    tot = c.sum()
    if tot <= 0.0:
        return (np.nan, np.nan, np.nan)
    dx = xc - x_cm
    dy = yc - y_cm
    xi = dx * cos_t + dy * sin_t
    eta = -dx * sin_t + dy * cos_t
    var_xi_c = float((c * xi ** 2).sum() / tot)
    var_eta_c = float((c * eta ** 2).sum() / tot)
    sub_xi = (cos_t ** 2 * delr ** 2 + sin_t ** 2 * delc ** 2) / 12.0
    sub_eta = (sin_t ** 2 * delr ** 2 + cos_t ** 2 * delc ** 2) / 12.0
    return (
        float(np.sqrt(max(var_xi_c + sub_xi, 0.0))),
        float(np.sqrt(max(var_eta_c + sub_eta, 0.0))),
        float(np.sqrt(max(var_eta_c, 0.0))),
    )


# ===========================================================================
# 3. RESULT CONTAINER
# ===========================================================================
@dataclass
class Verification2D:
    """Diagnostics from a 2D MODFLOW 6 GWT vs analytical verification run."""

    # --- output times and the comparison time ---
    times: np.ndarray                       # GWT output times [d]
    compare_time: float                     # time diagnostics are reported at [d]

    # --- extracted profiles at the comparison time ---
    centreline_x: np.ndarray                # x centres along the plume centre row [m]
    centreline_c: np.ndarray                # numerical c(x, y=~y0, compare_time) [mg/L]
    transverse_y: np.ndarray                # y centres down the peak column [m]
    transverse_c: np.ndarray                # numerical c(x=x_peak, y, compare_time) [mg/L]
    conc_field: np.ndarray                  # full numerical field at compare_time (nrow, ncol)

    # --- grid metadata ---
    delr: float
    delc: float
    ncol: int
    nrow: int
    Pe_L: float                             # delr / alpha_L
    Pe_T: float                             # delc / alpha_T

    # --- input parameters (echoed) ---
    u: float
    phi_e: float
    alpha_L: float
    alpha_T: float
    Dm: float
    DL: float
    DT: float
    R: float
    lam: float
    M: float
    m: float
    x0: float
    y0: float

    # --- per-output-time series (concentration-weighted moments) ---
    x_cm_t: np.ndarray                      # centre-of-mass x(t) [m]
    y_cm_t: np.ndarray                      # centre-of-mass y(t) [m]
    sigma_x_t: np.ndarray                   # numerical sigma_x(t) [m]
    sigma_y_t: np.ndarray                   # numerical sigma_y(t) [m]
    peak_c_t: np.ndarray                    # numerical peak concentration(t) [mg/L]
    mass_t: np.ndarray                      # numerical in-domain mass(t) [g]

    # --- match diagnostics at compare_time (numerical vs analytical) ---
    x_cm_num: float
    y_cm_num: float
    x_cm_an: float                          # x0 + (u/R)*compare_time*cos(theta)
    sigma_x_num: float
    sigma_x_an: float                       # sqrt(2*DL*t/R)
    sigma_y_num: float
    sigma_y_an: float                       # sqrt(2*DT*t/R)
    peak_c_num: float
    peak_c_an: float
    mass_num: float
    mass_an: float                          # M * exp(-lam*t)

    peak_pos_err: float                     # |centroid - analytical centre| / travel [-]
    peak_conc_err: float                    # |peak_c_num - peak_c_an| / peak_c_an [-]
    sigma_x_err: float                      # |sigma_x_num - sigma_x_an| / sigma_x_an [-]
    sigma_y_err: float                      # |sigma_y_num - sigma_y_an| / sigma_y_an [-]
    mass_err: float                         # |mass_num - mass_an| / M [-]

    # --- flow-aligned (oblique) diagnostics (theta = 0 -> eta axis == grid y) ---
    flow_angle_deg: float = 0.0             # flow angle to +x axis [deg]
    sigma_xi_num: float = float("nan")      # numerical along-flow spread [m]
    sigma_xi_an: float = float("nan")       # sqrt(2*DL*t/R)
    sigma_eta_num: float = float("nan")     # numerical cross-flow spread [m] (field moment)
    sigma_eta_an: float = float("nan")      # sqrt(2*DT*t/R)
    sigma_eta_err: float = float("nan")     # |sigma_eta_num - sigma_eta_an| / sigma_eta_an [-]
    sigma_eta_centres_num: float = float("nan")   # raw cell-centre cross-flow moment [m]
    sigma_eta_t: np.ndarray = field(default_factory=lambda: np.array([]))  # cross-flow sigma(t)
    crossflow_s: np.ndarray = field(default_factory=lambda: np.array([]))  # cross-flow axis [m]
    crossflow_c: np.ndarray = field(default_factory=lambda: np.array([]))  # c along cross-flow axis

    workspace: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


# ===========================================================================
# 4. BUILD + RUN THE NUMERICAL VERIFICATION MODEL
# ===========================================================================
def build_and_run_2d_verification(
    *,
    # domain / grid
    xL: float = 300.0,
    y_half: float = 60.0,
    m: float = 10.0,
    delr: float = 2.0,
    delc: float = 1.0,
    # flow
    K: float = 1.0,
    gradient: float = 0.1,
    phi_e: float = 0.20,
    flow_angle_deg: float = 0.0,
    # dispersion
    alpha_L: float = 10.0,
    alpha_T: float = 1.0,
    Dm: float = 0.0,
    # source
    x0: float = 50.0,
    y0: float = 0.0,
    M: float = 1000.0,
    # reactions
    R: float = 1.0,
    lam: float = 0.0,
    rho_b: float = 1600.0,
    # time
    total_time: float = 120.0,
    dt: float = 2.0,
    compare_time: Optional[float] = None,
    compare_times: Optional[Sequence[float]] = None,
    # scheme
    scheme: str = "TVD",
    xt3d_off: bool = True,
    # run control
    workspace: Optional[Union[str, Path]] = None,
    exe_name: Optional[str] = None,
    silent: bool = True,
) -> Verification2D:
    """Build + run a uniform-flow MF6 GWF/GWT model and compare to the analytic plume.

    A steady GWF flow field (uniform ``+x`` gradient via CHD on the left / right
    boundaries) drives a transient GWT run.  The instantaneous mass release is
    realized as an initial-concentration spike in the single source cell::

        STRT_source = M / (phi_e * R * m * A_cell),   A_cell = delr * delc

    so that the source cell's total (aqueous + sorbed) mass equals ``M``.  All
    other cells start at 0.

    Reactions are optional: ``R > 1`` is realized with linear MST sorption
    (``Kd = (R-1)*phi_e/rho_b``) and ``lam > 0`` with first-order decay on BOTH
    the aqueous and sorbed phases (so the total mass decays as ``exp(-lam*t)``,
    matching the analytical solution).

    Molecular diffusion ``Dm`` defaults to 0 so that ``DL = alpha_L*u`` and
    ``DT = alpha_T*u`` exactly; set it non-zero for a diffusion floor (kept
    consistent with the analytical ``DL``/``DT``).

    Parameters largely follow the module defaults; the returned
    :class:`Verification2D` carries the grid metadata, the echoed parameters,
    per-time moment series, and self-computed match diagnostics vs
    :func:`plume_2d_instantaneous`.
    """
    exe = _resolve_mf6(exe_name)

    # ---- derived flow / transport quantities ----
    q = K * gradient                         # Darcy flux [m/d]
    u = q / phi_e                            # seepage velocity [m/d]
    DL = alpha_L * u + Dm                    # longitudinal dispersion coeff [m^2/d]
    DT = alpha_T * u + Dm                    # transverse dispersion coeff [m^2/d]
    Kd = (R - 1.0) * phi_e / rho_b if R > 1.0 else 0.0   # distribution coeff [m^3/kg]

    # ---- structured grid ----
    ncol = int(round(xL / delr))
    nrow = int(round((2.0 * y_half) / delc))
    top = float(m)
    botm = 0.0
    A_cell = delr * delc

    # cell-centre coordinates (row 0 = +y_half side; MF6 rows march in -y)
    xc_1d = (np.arange(ncol) + 0.5) * delr                       # 0 .. xL
    yc_1d = y_half - (np.arange(nrow) + 0.5) * delc              # +y_half .. -y_half
    XC, YC = np.meshgrid(xc_1d, yc_1d)                           # (nrow, ncol)

    # ---- source cell (nearest cell centre to (x0, y0)) ----
    jsrc = int(np.argmin(np.abs(yc_1d - y0)))
    isrc = int(np.argmin(np.abs(xc_1d - x0)))
    x0_cell = float(xc_1d[isrc])
    y0_cell = float(yc_1d[jsrc])

    strt_c = np.zeros((1, nrow, ncol), dtype=float)
    strt_c[0, jsrc, isrc] = M / (phi_e * R * m * A_cell)

    # ---- flow orientation ----
    theta = np.radians(flow_angle_deg)
    cos_t, sin_t = float(np.cos(theta)), float(np.sin(theta))
    aligned = abs(flow_angle_deg) < 1e-9

    # ---- flow boundary heads (confined, thickness == m regardless of head) ----
    if aligned:
        # ALIGNED (+x) flow: CHD on the left / right columns only (unchanged).
        h_left = top + gradient * xL         # upstream head
        h_right = top                        # downstream head (== top; confined)
        strt_gwf = h_left
        chd_spd = ([[(0, j, 0), h_left] for j in range(nrow)]
                   + [[(0, j, ncol - 1), h_right] for j in range(nrow)])
    else:
        # OBLIQUE flow at angle theta: impose the exact linear head field
        #   h(x,y) = href - gradient*(x*cos + y*sin)
        # on ALL perimeter cells.  This drives a uniform Darcy flux of magnitude
        # K*gradient in direction (cos, sin) across the whole domain.  href is
        # offset so every head stays >= top (kept confined / positive).
        href = top + gradient * (xL * abs(cos_t) + 2.0 * y_half * abs(sin_t))
        Hfield = href - gradient * (XC * cos_t + YC * sin_t)     # (nrow, ncol)
        strt_gwf = Hfield[np.newaxis, :, :]
        chd_spd = []
        for j in range(nrow):
            for i in range(ncol):
                if i == 0 or i == ncol - 1 or j == 0 or j == nrow - 1:
                    chd_spd.append([(0, j, i),
                                    float(href - gradient
                                          * (xc_1d[i] * cos_t + yc_1d[j] * sin_t))])
        h_left = float(Hfield.max())
        h_right = float(Hfield.min())

    # ---- workspace ----
    if workspace is None:
        workspace = Path(tempfile.mkdtemp(prefix="mf6_verify2d_"))
    else:
        workspace = Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
    ws = str(workspace)

    # ---- time discretization ----
    nstp = max(int(round(total_time / dt)), 1)

    # ---- build simulation ----
    sim = flopy.mf6.MFSimulation(sim_name="verify2d", exe_name=exe, sim_ws=ws)
    flopy.mf6.ModflowTdis(sim, time_units="DAYS", nper=1,
                          perioddata=[(float(total_time), nstp, 1.0)])

    # --- GWF (steady, uniform flow) ---
    ims_gwf = flopy.mf6.ModflowIms(
        sim, filename="gwf.ims", complexity="SIMPLE",
        linear_acceleration="CG", outer_dvclose=1e-8, inner_dvclose=1e-9,
        outer_maximum=100, inner_maximum=100)
    gwf = flopy.mf6.ModflowGwf(sim, modelname="gwf", save_flows=True)
    dis = flopy.mf6.ModflowGwfdis(
        gwf, nlay=1, nrow=nrow, ncol=ncol, delr=delr, delc=delc,
        top=top, botm=botm, xorigin=0.0, yorigin=-y_half)
    flopy.mf6.ModflowGwfnpf(gwf, icelltype=0, k=K, save_flows=True,
                            save_specific_discharge=True)
    flopy.mf6.ModflowGwfic(gwf, strt=strt_gwf)
    flopy.mf6.ModflowGwfsto(gwf, steady_state={0: True})
    flopy.mf6.ModflowGwfchd(gwf, stress_period_data=chd_spd)
    flopy.mf6.ModflowGwfoc(
        gwf, head_filerecord="gwf.hds", budget_filerecord="gwf.cbc",
        saverecord=[("HEAD", "LAST"), ("BUDGET", "LAST")])

    # --- GWT (transient transport) ---
    ims_gwt = flopy.mf6.ModflowIms(
        sim, filename="gwt.ims", complexity="MODERATE",
        linear_acceleration="BICGSTAB", outer_dvclose=1e-8, inner_dvclose=1e-9,
        outer_maximum=200, inner_maximum=200)
    gwt = flopy.mf6.ModflowGwt(sim, modelname="gwt", save_flows=True)
    flopy.mf6.ModflowGwtdis(
        gwt, nlay=1, nrow=nrow, ncol=ncol, delr=delr, delc=delc,
        top=top, botm=botm, xorigin=0.0, yorigin=-y_half)
    flopy.mf6.ModflowGwtic(gwt, strt=strt_c)
    flopy.mf6.ModflowGwtadv(gwt, scheme=scheme)
    flopy.mf6.ModflowGwtdsp(gwt, alh=alpha_L, ath1=alpha_T, diffc=Dm,
                            xt3d_off=xt3d_off)

    # MST: porosity, optional linear sorption (R) and first-order decay (lam)
    mst_kw: Dict[str, Any] = dict(porosity=phi_e)
    if R > 1.0:
        mst_kw.update(sorption="linear", bulk_density=rho_b, distcoef=Kd)
    if lam > 0.0:
        mst_kw.update(first_order_decay=True, decay=lam)
        if R > 1.0:
            mst_kw.update(decay_sorbed=lam)     # decay both phases -> total ~ e^{-lam t}
    flopy.mf6.ModflowGwtmst(gwt, **mst_kw)

    flopy.mf6.ModflowGwtssm(gwt)                # CHD in/out handled at bnd/cell conc
    flopy.mf6.ModflowGwtoc(
        gwt, concentration_filerecord="gwt.ucn", budget_filerecord="gwt.cbc",
        saverecord=[("CONCENTRATION", "ALL"), ("BUDGET", "ALL")])

    # --- register each IMS with its own model (GWF first, then GWT) ---
    sim.register_ims_package(ims_gwf, ["gwf"])
    sim.register_ims_package(ims_gwt, ["gwt"])

    # --- flow -> transport coupling ---
    flopy.mf6.ModflowGwfgwt(sim, exgtype="GWF6-GWT6",
                            exgmnamea="gwf", exgmnameb="gwt")

    sim.write_simulation(silent=silent)
    ok, buf = sim.run_simulation(silent=silent)
    if not ok:
        tail = "\n".join(buf[-25:]) if buf else "(no buffer)"
        raise RuntimeError(f"MF6 verification run failed:\n{tail}")

    # ---- read concentrations ----
    cobj = gwt.output.concentration()
    times = np.array(cobj.get_times(), dtype=float)

    # per-time moment series (grid-aligned x/y AND flow-aligned cross-flow eta)
    x_cm_t, y_cm_t, sigma_x_t, sigma_y_t, peak_c_t, mass_t, sigma_eta_t = (
        [], [], [], [], [], [], [])
    for t in times:
        fld = cobj.get_data(totim=float(t))[0]              # (nrow, ncol)
        mom = _field_moments(fld, XC, YC, delr, delc, phi_e=phi_e, R=R, m=m)
        x_cm_t.append(mom["x_cm"]); y_cm_t.append(mom["y_cm"])
        sigma_x_t.append(mom["sigma_x"]); sigma_y_t.append(mom["sigma_y"])
        peak_c_t.append(mom["peak_c"]); mass_t.append(mom["mass_g"])
        _, sig_eta, _ = _rotated_sigma(fld, XC, YC, mom["x_cm"], mom["y_cm"],
                                       cos_t, sin_t, delr, delc)
        sigma_eta_t.append(sig_eta)
    x_cm_t = np.array(x_cm_t); y_cm_t = np.array(y_cm_t)
    sigma_x_t = np.array(sigma_x_t); sigma_y_t = np.array(sigma_y_t)
    peak_c_t = np.array(peak_c_t); mass_t = np.array(mass_t)
    sigma_eta_t = np.array(sigma_eta_t)

    # ---- comparison time (nearest available output time) ----
    if compare_time is None:
        compare_time = float(times[-1])
    it = int(np.argmin(np.abs(times - compare_time)))
    t_cmp = float(times[it])
    field_cmp = cobj.get_data(totim=t_cmp)[0]               # (nrow, ncol)
    mom_cmp = _field_moments(field_cmp, XC, YC, delr, delc, phi_e=phi_e, R=R, m=m)

    # ---- extracted profiles at compare_time ----
    jc = int(np.argmin(np.abs(yc_1d - y0_cell)))            # plume centre row
    centreline_c = field_cmp[jc, :].astype(float)
    ipk = int(np.argmax(centreline_c))                      # peak column
    transverse_c = field_cmp[:, ipk].astype(float)

    # ---- analytical references at compare_time (RELATIVE to source cell) ----
    # plume centre advects along the flow direction (cos, sin) at u/R
    cx_an = x0_cell + (u / R) * t_cmp * cos_t
    cy_an = y0_cell + (u / R) * t_cmp * sin_t
    x_cm_an = cx_an                                         # along-flow-projected x
    sigma_x_an = float(np.sqrt(2.0 * DL * t_cmp / R))       # grid-x (== xi at theta=0)
    sigma_y_an = float(np.sqrt(2.0 * DT * t_cmp / R))       # grid-y (== eta at theta=0)
    sigma_xi_an = float(np.sqrt(2.0 * DL * t_cmp / R))      # along-flow spread
    sigma_eta_an = float(np.sqrt(2.0 * DT * t_cmp / R))     # cross-flow spread
    peak_c_an = float(plume_2d_instantaneous(
        (u / R) * t_cmp, 0.0, t_cmp, M, phi_e, m, R, DL, DT, u, lam))  # at moving peak
    mass_an = float(M * np.exp(-lam * t_cmp))

    # ---- flow-aligned (rotated) numerical moments at compare_time ----
    sigma_xi_num, sigma_eta_num, sigma_eta_centres_num = _rotated_sigma(
        field_cmp, XC, YC, mom_cmp["x_cm"], mom_cmp["y_cm"],
        cos_t, sin_t, delr, delc)

    # ---- cross-flow profile through the centroid (axis perpendicular to flow) ----
    s_axis = np.linspace(-3.0 * sigma_eta_an, 3.0 * sigma_eta_an, 61)
    px = mom_cmp["x_cm"] + s_axis * (-sin_t)               # cross-flow direction (-sin, cos)
    py = mom_cmp["y_cm"] + s_axis * cos_t
    # locate nearest cell (xc_1d ascending, yc_1d descending) by abs-diff
    cf_c = np.array([
        field_cmp[int(np.argmin(np.abs(yc_1d - yy))), int(np.argmin(np.abs(xc_1d - xx)))]
        for xx, yy in zip(px, py)], dtype=float)

    # ---- match diagnostics ----
    travel = (u / R) * t_cmp
    peak_pos_err = (np.hypot(mom_cmp["x_cm"] - cx_an, mom_cmp["y_cm"] - cy_an) / travel
                    if travel > 0 else np.nan)
    peak_conc_err = abs(mom_cmp["peak_c"] - peak_c_an) / peak_c_an if peak_c_an > 0 else np.nan
    sigma_x_err = abs(mom_cmp["sigma_x"] - sigma_x_an) / sigma_x_an
    sigma_y_err = abs(mom_cmp["sigma_y"] - sigma_y_an) / sigma_y_an
    sigma_eta_err = abs(sigma_eta_num - sigma_eta_an) / sigma_eta_an
    mass_err = abs(mom_cmp["mass_g"] - mass_an) / M

    return Verification2D(
        times=times, compare_time=t_cmp,
        centreline_x=xc_1d.copy(), centreline_c=centreline_c,
        transverse_y=yc_1d.copy(), transverse_c=transverse_c,
        conc_field=np.asarray(field_cmp, dtype=float),
        delr=delr, delc=delc, ncol=ncol, nrow=nrow,
        Pe_L=delr / alpha_L, Pe_T=delc / alpha_T,
        u=u, phi_e=phi_e, alpha_L=alpha_L, alpha_T=alpha_T, Dm=Dm,
        DL=DL, DT=DT, R=R, lam=lam, M=M, m=m, x0=x0_cell, y0=y0_cell,
        x_cm_t=x_cm_t, y_cm_t=y_cm_t, sigma_x_t=sigma_x_t, sigma_y_t=sigma_y_t,
        peak_c_t=peak_c_t, mass_t=mass_t,
        x_cm_num=mom_cmp["x_cm"], y_cm_num=mom_cmp["y_cm"], x_cm_an=x_cm_an,
        sigma_x_num=mom_cmp["sigma_x"], sigma_x_an=sigma_x_an,
        sigma_y_num=mom_cmp["sigma_y"], sigma_y_an=sigma_y_an,
        peak_c_num=mom_cmp["peak_c"], peak_c_an=peak_c_an,
        mass_num=mom_cmp["mass_g"], mass_an=mass_an,
        peak_pos_err=peak_pos_err, peak_conc_err=peak_conc_err,
        sigma_x_err=sigma_x_err, sigma_y_err=sigma_y_err, mass_err=mass_err,
        flow_angle_deg=float(flow_angle_deg),
        sigma_xi_num=sigma_xi_num, sigma_xi_an=sigma_xi_an,
        sigma_eta_num=sigma_eta_num, sigma_eta_an=sigma_eta_an,
        sigma_eta_err=sigma_eta_err, sigma_eta_centres_num=sigma_eta_centres_num,
        sigma_eta_t=sigma_eta_t, crossflow_s=s_axis, crossflow_c=cf_c,
        workspace=ws,
        meta=dict(exe=exe, q=q, Kd=Kd, rho_b=rho_b, nstp=nstp, dt=total_time / nstp,
                  Cr=u * (total_time / nstp) / delr, h_left=h_left, h_right=h_right,
                  isrc=isrc, jsrc=jsrc, scheme=scheme, xt3d_off=xt3d_off,
                  cos_t=cos_t, sin_t=sin_t, cx_an=cx_an, cy_an=cy_an,
                  sigma_x_centres_num=mom_cmp["sigma_x_centres"],
                  sigma_y_centres_num=mom_cmp["sigma_y_centres"]),
    )


# ---------------------------------------------------------------------------
# demo / smoke anchor
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import time

    t0 = time.time()
    r = build_and_run_2d_verification()
    dt = time.time() - t0
    print("2D MF6 GWT vs ANALYTICAL VERIFICATION (conservative, fine grid)")
    print(f"  u = {r.u:.3f} m/d   DL = {r.DL:.3g}   DT = {r.DT:.3g} m^2/d")
    print(f"  grid {r.nrow} x {r.ncol}  (delr={r.delr} delc={r.delc})  "
          f"Pe_L={r.Pe_L:.2f} Pe_T={r.Pe_T:.2f}  Cr={r.meta['Cr']:.2f}")
    print(f"  compare @ t = {r.compare_time:.0f} d")
    print(f"  peak position: num {r.x_cm_num:.1f} vs an {r.x_cm_an:.1f} m  "
          f"-> {100*r.peak_pos_err:.2f}% of travel")
    print(f"  peak conc    : num {r.peak_c_num:.4g} vs an {r.peak_c_an:.4g} mg/L "
          f"-> {100*r.peak_conc_err:.2f}%")
    print(f"  sigma_x      : num {r.sigma_x_num:.2f} vs an {r.sigma_x_an:.2f} m "
          f"-> {100*r.sigma_x_err:.2f}%")
    print(f"  sigma_y      : num {r.sigma_y_num:.2f} vs an {r.sigma_y_an:.2f} m "
          f"-> {100*r.sigma_y_err:.2f}%")
    print(f"  mass         : num {r.mass_num:.4g} vs an {r.mass_an:.4g} g "
          f"-> {100*r.mass_err:.2f}% of M")
    print(f"  wall-clock   = {dt:.1f}s")
    ok = (r.peak_pos_err < 0.05 and r.peak_conc_err < 0.10 and r.sigma_y_err < 0.15)
    print("  SMOKE:", "PASS" if ok else "FAIL")

    # ---- oblique (theta=45 deg) cross-wind numerical dispersion + refinement ----
    print("\nOBLIQUE FLOW (theta=45 deg): cross-wind numerical dispersion vs grid")
    obl_kw = dict(xL=160.0, y_half=80.0, x0=45.0, y0=-45.0, total_time=100.0,
                  flow_angle_deg=45.0, xt3d_off=False)
    print("  cell[m]  sigma_eta_num  sigma_eta_an   error%   (refinement removes it)")
    prev = None
    monotone = True
    for cs in (8.0, 4.0, 2.0, 1.0):
        ro = build_and_run_2d_verification(delr=cs, delc=cs, **obl_kw)
        print(f"   {cs:4.1f}     {ro.sigma_eta_num:8.3f}     {ro.sigma_eta_an:8.3f}   "
              f"{100*ro.sigma_eta_err:6.2f}")
        if prev is not None and ro.sigma_eta_err >= prev:
            monotone = False
        prev = ro.sigma_eta_err
    print("  refinement monotonically reduces cross-flow error:",
          "PASS" if monotone else "FAIL")
    sys.exit(0 if ok else 1)
