"""
Finite-pulse SRC (mass-loading) spill -> capture demo for MODFLOW 6 GWT.

Self-contained teaching demo (UNGRADED) for the transport track (charter milestone
M2).  Builds and runs a coupled steady-GWF / transient-GWT simulation on a
corridor-refined DISV grid:

    * A representative geothermal DOUBLET (spare concession ``b010191``) is active
      for FLOW ONLY -- a clean injection well (+Q) and an extraction / monitoring
      well (-Q) shape a forced-gradient flow field.  No solute rides the wells.
    * A finite-duration point SPILL is placed ~90 m UPGRADIENT of the extraction
      well (upgradient computed from the local regional flow direction).  The
      solute is introduced with the MODFLOW 6 **SRC** package (mass loading,
      g/d) rather than a fixed concentration (CNC).  The pulse is ON for the
      first stress period (duration ``pulse_days``) and OFF thereafter, so the
      plume migrates freely toward the pumping well.

Units: the flow model runs in metres / day, so mg/L == g/m^3 and SRC mass rates
are in **grams per day**.  A released mass ``M`` [g] over a pulse ``T`` [d] gives a
per-cell loading ``smassrate = M / (n_src_cells * T)`` [g/d].

Diagnostics returned: breakthrough at the extraction well (mg/L), peak + arrival,
a mass-balance table from the GWT listing budget (SRC in, well out, boundary out,
storage, % imbalance), a solubility guardrail (emergent source-cell concentration
vs a stated solubility), and the grid Peclet numbers Pe_L / Pe_T on the corridor.

OWNERSHIP: this module imports the shared grid utility ``model_io_utils`` only.
It does NOT import ``transport_base_model`` -- the corridor radius-walk retry,
Courant sizing and helpers are re-implemented inline here.

Author: Applied Groundwater Modelling Course (transport track, M2 SRC demo)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import geopandas as gpd
import flopy
from shapely.geometry import LineString, Point, Polygon

import model_io_utils as mio  # shared grid utility (grid + property interpolation)


# ---------------------------------------------------------------------------
# LOCKED transport parameters (replicated from transport_base_model.LOCKED_PARAMS)
# ---------------------------------------------------------------------------
LOCKED_PARAMS: Dict[str, Any] = {
    "alh": 10.0,            # longitudinal dispersivity [m]
    "ath1": 1.0,            # transverse horizontal dispersivity [m]
    "diffc": 8.64e-5,       # effective molecular diffusion [m^2/d] (= 1e-9 m^2/s)
    "porosity": 0.20,       # effective porosity n_e [-]
    "scheme": "TVD",        # ADV weighting
    "xt3d_off": False,      # XT3D default-on for DSP
    "refined_cell_size": 10.0,
    "base_cell_size": 50.0,
    "time_units": "DAYS",
}

# Solver policy (replicated from transport_base_model)
_GWF_NEWTON = "NEWTON"
_GWF_IMS = dict(complexity="COMPLEX", outer_maximum=200, inner_maximum=100,
                outer_dvclose=1e-4, inner_dvclose=1e-5, linear_acceleration="BICGSTAB")
_GWT_IMS = dict(complexity="MODERATE", linear_acceleration="BICGSTAB",
                outer_dvclose=1e-6, inner_dvclose=1e-7)

# Representative spare doublet b010191 (LV95) -- FLOW ONLY, not assigned to any group.
INJ_XY: Tuple[float, float] = (2681297.0, 1248917.0)   # injection well  (Rückgabe)
ABS_XY: Tuple[float, float] = (2681487.0, 1248981.0)   # extraction well (Entnahme)
DOUBLET_Q: float = 1370.0                              # doublet rate [m^3/d]
SPILL_UPGRADIENT_M: float = 90.0                       # spill offset upgradient of ABS [m]

_MF6_FALLBACK = os.path.expanduser("~/.local/share/flopy/bin/mf6")


# ---------------------------------------------------------------------------
# result container
# ---------------------------------------------------------------------------
@dataclass
class SrcPulseDemo:
    """Diagnostics from the SRC finite-pulse spill -> capture demo."""
    times: np.ndarray                       # output times [d]
    breakthrough: np.ndarray                # C at extraction well [mg/L]
    peak_mgL: float                         # peak breakthrough [mg/L]
    arrival_day: float                      # time of peak [d]
    mass_balance: Dict[str, float]          # cumulative mass terms [g] + % imbalance
    solubility_ok: bool                     # emergent C < solubility ?
    emergent_C_mgL: float                   # emergent source-cell concentration [mg/L]
    solubility_mgL: float                   # stated solubility [mg/L]
    solubility_margin: float                # solubility / emergent_C
    PeL_min: float
    PeL_max: float
    PeT_min: float
    PeT_max: float
    mass_g: float
    pulse_days: float
    total_days: float
    smassrate_gpd: float                    # per-cell SRC loading [g/d]
    src_cells: List[int]
    ext_cell: int
    inj_cell: int
    spill_xy: Tuple[float, float]
    alpha_L: float                          # effective longitudinal dispersivity [m]
    alpha_T: float                          # effective transverse dispersivity [m] (alpha_L / 10)
    R: float                                # retardation factor [-]
    rho_b: float                            # dry bulk density [kg/m^3]
    Kd: float                               # distribution coefficient [m^3/kg] (0.0 when R==1)
    lam: float                              # first-order decay rate [1/d] (0.0 = no decay)
    meta: Dict[str, Any] = field(default_factory=dict)
    locked: Dict[str, Any] = field(default_factory=lambda: dict(LOCKED_PARAMS))


# ---------------------------------------------------------------------------
# inline helpers (re-implemented; NOT imported from transport_base_model)
# ---------------------------------------------------------------------------
def _cellsize(mg, ncpl) -> np.ndarray:
    """Representative cell edge length sqrt(area) per cell."""
    return np.array([np.sqrt(Polygon(mg.get_cell_vertices(i)).area) for i in range(ncpl)])


def _run_failure_tail(ws: Union[str, Path], buf, n: int = 40) -> str:
    """Assemble a readable failure message from the MF6 listing tails."""
    ws = Path(ws)
    chunks = []
    for name in ("mfsim.lst", "gwf.lst", "gwt.lst"):
        p = ws / name
        if p.exists():
            try:
                lines = p.read_text(errors="replace").splitlines()
            except OSError:
                continue
            if lines:
                chunks.append(f"--- {name} (last {n} lines) ---\n" + "\n".join(lines[-n:]))
    buf_tail = "\n".join(buf[-12:]) if buf else ""
    if buf_tail.strip():
        chunks.append("--- run_simulation buffer (tail) ---\n" + buf_tail)
    return "\n\n".join(chunks) if chunks else "(no listing output found)"


def _corridor_points(a_xy, b_xy, step: float = 40.0, pad: float = 40.0):
    """Evenly-spaced refine points along a->b (padded past both ends)."""
    a, b = np.array(a_xy, float), np.array(b_xy, float)
    L = float(np.hypot(*(b - a)))
    u = (b - a) / L
    n = max(int((L + 2 * pad) // step) + 1, 2)
    return [tuple(a + s * u) for s in np.linspace(-pad, L + pad, n)], u, L


def _refine_with_retry(coarse_gwf, boundary_gdf, river_gdf, refine_points, head_array,
                       workspace: Union[str, Path], *,
                       refine_radii: Sequence[float] = (70.0, 62.0, 78.0, 56.0, 84.0),
                       base_cell_size: float = 50.0, refined_cell_size: float = 10.0,
                       sim_name: str = "rg") -> Tuple[Dict[str, Any], float]:
    """Corridor refine, walking the refine radius to dodge the cs=10 SIGILL /
    Triangle-precision abort (macOS arm64 / mf6 6.7.0).

    Re-implemented inline (charter constraint: do NOT import transport_base_model).
    Returns (build_refined_gwf_model result dict, radius actually used).
    """
    workspace = Path(workspace)
    last_exc: Optional[Exception] = None
    for k, rr in enumerate(refine_radii):
        try:
            res = mio.build_refined_gwf_model(
                coarse_gwf, boundary_gdf=boundary_gdf, river_gdf=river_gdf,
                refine_points=refine_points, head_array=head_array,
                workspace=str(workspace / f"rg{k}"), refine_radius=float(rr),
                base_cell_size=base_cell_size, refined_cell_size=refined_cell_size,
                sim_name=sim_name)
            return res, float(rr)
        except Exception as e:  # SIGILL / Triangle abort surfaces here
            last_exc = e
            continue
    raise RuntimeError(
        f"corridor refinement failed at all radii {tuple(refine_radii)}; "
        f"last error: {last_exc!r}")


def _courant_nstp(v_cells: np.ndarray, size_cells: np.ndarray, mask: np.ndarray,
                  total_time: float, cr_target: float = 0.9, nstp_cap: int = 2000,
                  sliver_floor_frac: float = 0.4) -> Tuple[int, float, float, Dict[str, float]]:
    """Size fixed time steps from a per-cell Courant number Cr_i = v_i*dt/ds_i.

    Slivers below sliver_floor_frac * refined_cell_size are excluded (they carry
    negligible pore volume but would force an impractically tiny dt).
    """
    floor = sliver_floor_frac * LOCKED_PARAMS["refined_cell_size"]
    sel = mask & (size_cells >= floor)
    if not sel.any():                       # degenerate: fall back to whole mask
        sel = mask
    ratio = v_cells[sel] / size_cells[sel]
    critical = float(ratio.max())
    j = np.where(sel)[0][int(np.argmax(ratio))]
    if critical <= 0.0:
        # degenerate zero-velocity field on the selected cells: cr_target /
        # critical would ZeroDivisionError.  Fall back to the step cap -- there
        # is no advective signal to size dt against.
        nstp = max(nstp_cap, 1)
        dt = total_time / nstp
        diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                    ds_true_min=float(size_cells[mask].min()), floor=floor)
        return nstp, dt, critical * dt, diag
    dt_need = cr_target / critical
    nstp = min(int(np.ceil(total_time / dt_need)), nstp_cap)
    nstp = max(nstp, 1)
    dt = total_time / nstp
    diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                ds_true_min=float(size_cells[mask].min()), floor=floor)
    return nstp, dt, critical * dt, diag


def _load_calibrated_flow():
    """Load the 05f-calibrated coarse flow model + GIS (boundary, Limmat/Sihl)."""
    from data_utils import download_named_file
    flow_ws = mio.ensure_flow_model()
    # prefer an mf6 already on PATH; fall back to the flopy-bin install location.
    exe = shutil.which("mf6") or _MF6_FALLBACK
    csim = flopy.mf6.MFSimulation.load(sim_ws=str(flow_ws), exe_name=exe, verbosity_level=0)
    cgwf = csim.get_model("limmat_valley")
    boundary = gpd.read_file(download_named_file(name="model_boundary", data_type="gis"))
    rivers = gpd.read_file(download_named_file(name="rivers", data_type="gis"))
    rivers = rivers[rivers["GEWAESSERNAME"].isin(["Limmat", "Sihl"])
                    & rivers.intersects(boundary.geometry.iloc[0])]
    return cgwf, boundary, rivers, exe


def _default_case_ws() -> Path:
    from data_utils import get_default_data_folder
    return Path(get_default_data_folder()) / "transport_srcpulse_demo"


def _src_sha() -> str:
    """SHA of every module SOURCE this model is built from.

    THIS module (the doublet, the spill rule, the SRC/MST wiring, the Courant sizing)
    AND ``model_io_utils``, which BUILDS the refined grid (``mio.build_refined_gwf_model``).
    An edit to grid generation changes this model just as surely as an edit here does,
    and without it that edit would leave every warm cache valid while the grid moved
    underneath it -- the exact bug class this repo has already shipped once.
    """
    h = hashlib.sha1()
    for p in (Path(__file__), Path(mio.__file__)):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# build + run
# ---------------------------------------------------------------------------
def build_srcpulse_demo(
    mass_g: float = 3.0e5,
    pulse_days: float = 30.0,
    total_days: float = 120.0,
    solubility_mgL: float = 1000.0,
    *,
    alpha_L: Optional[float] = None,
    R: float = 1.0,
    rho_b: float = 1800.0,
    lam: float = 0.0,
    case_ws: Optional[Union[str, Path]] = None,
    cr_target: float = 0.9,
    nstp_cap: int = 2000,
    refine_radii: Sequence[float] = (70.0, 62.0, 78.0, 56.0, 84.0),
    force: bool = False,
) -> SrcPulseDemo:
    """Build + run the SRC finite-pulse spill -> capture demo; return diagnostics.

    Parameters
    ----------
    mass_g : float
        Total solute mass released over the pulse [g].
    pulse_days : float
        Pulse duration T [d] (SRC active in stress period 0, off afterwards).
    total_days : float
        Total simulated time [d] (period 0 = pulse, period 1 = migration).
    solubility_mgL : float
        Stated aqueous solubility [mg/L] for the guardrail assertion.
    alpha_L : float, optional
        Override longitudinal dispersivity [m].  ``None`` (default) uses the
        LOCKED value (10.0 m).  Scales BOTH dispersivities to preserve the
        course's locked 10:1 anisotropy ratio: ``alh = alpha_L`` and
        ``ath1 = alpha_L / 10.0``.  Feeds the DSP package and the Pe_L / Pe_T
        grid-Peclet diagnostics (``PeL = cellsize / alpha_L``,
        ``PeT = cellsize / (alpha_L / 10)``).
    R : float
        Retardation factor [-] (students reason in R, not Kd).  ``R == 1.0``
        (default) is conservative transport -- no sorption args are passed to
        MST at all.  ``R > 1`` enables MODFLOW 6 MST linear sorption with
        ``Kd = (R - 1) * porosity / rho_b``.
    rho_b : float
        Dry bulk density [kg/m^3], used only for the Kd conversion when
        ``R > 1``.
    lam : float
        First-order decay rate [1/d] (e.g. ``ln(2) / half_life``).  ``lam >
        0`` enables MST first-order decay.  ``decay_sorbed`` is only valid
        when sorption is active (MF6 constraint), so it is set equal to
        ``lam`` only when ``R > 1`` as well; otherwise only the aqueous
        ``decay`` is passed.
    case_ws : path, optional
        Workspace for the refined grid + coupled sim + cache.  Defaults to
        ``<data>/transport_srcpulse_demo``.
    force : bool
        Rebuild even if a matching cache exists.

    Returns
    -------
    SrcPulseDemo
    """
    # NaN/inf defeat every "<" / "<=" guard below (they are False for NaN), so a
    # NaN would sail through validation and then silently take a wrong branch
    # downstream (e.g. `R > 1.0` is False for R=nan -> falls back to a
    # CONSERVATIVE run mislabelled "R=nan").  Reject non-finite values up front.
    for _name, _val in (("mass_g", mass_g), ("pulse_days", pulse_days),
                         ("total_days", total_days), ("solubility_mgL", solubility_mgL),
                         ("R", R), ("rho_b", rho_b), ("lam", lam),
                         ("cr_target", cr_target)):
        if not math.isfinite(_val):
            raise ValueError(f"{_name} must be finite (got {_val!r})")
    if alpha_L is not None and not math.isfinite(alpha_L):
        raise ValueError(f"alpha_L must be finite (got {alpha_L!r})")

    if R < 1.0:
        raise ValueError(f"R must be >= 1.0 (got {R!r})")
    if lam < 0.0:
        raise ValueError(f"lam must be >= 0.0 (got {lam!r})")
    if alpha_L is not None and alpha_L <= 0.0:
        raise ValueError(f"alpha_L must be > 0 (got {alpha_L!r})")
    if rho_b <= 0.0:
        raise ValueError(f"rho_b must be > 0 (got {rho_b!r})")
    if mass_g <= 0.0:
        raise ValueError(f"mass_g must be > 0 (got {mass_g!r})")
    if solubility_mgL <= 0.0:
        raise ValueError(f"solubility_mgL must be > 0 (got {solubility_mgL!r})")
    if cr_target <= 0.0:
        raise ValueError(f"cr_target must be > 0 (got {cr_target!r})")
    if nstp_cap < 1:
        raise ValueError(f"nstp_cap must be >= 1 (got {nstp_cap!r})")
    if pulse_days <= 0.0:
        raise ValueError(f"pulse_days must be > 0 (got {pulse_days!r})")
    if total_days <= pulse_days:
        raise ValueError(
            f"total_days ({total_days!r}) must be > pulse_days ({pulse_days!r}); "
            "period 1 (post-pulse migration) would otherwise have zero/negative length")

    alpha_L_eff = float(LOCKED_PARAMS["alh"]) if alpha_L is None else float(alpha_L)
    # Derive the transverse ratio FROM LOCKED_PARAMS (currently 1.0 / 10.0 = 0.1)
    # rather than hardcoding "/ 10.0" -- that hardcode previously matched the
    # locked ratio only by coincidence, and silently ignored LOCKED_PARAMS["ath1"].
    alpha_T_eff = alpha_L_eff * (float(LOCKED_PARAMS["ath1"]) / float(LOCKED_PARAMS["alh"]))
    porosity = float(LOCKED_PARAMS["porosity"])
    Kd = (float(R) - 1.0) * porosity / float(rho_b) if R > 1.0 else 0.0

    case_ws = Path(case_ws) if case_ws is not None else _default_case_ws()
    case_ws.mkdir(parents=True, exist_ok=True)

    params = dict(mass_g=float(mass_g), pulse_days=float(pulse_days),
                  total_days=float(total_days), solubility_mgL=float(solubility_mgL),
                  alpha_L=alpha_L_eff, R=float(R), rho_b=float(rho_b), lam=float(lam),
                  cr_target=float(cr_target), nstp_cap=int(nstp_cap),
                  refine_radii=list(map(float, refine_radii)),
                  # Fold a snapshot of LOCKED_PARAMS into the cache identity so an
                  # edit to LOCKED_PARAMS (porosity, scheme, xt3d_off, diffc,
                  # base_cell_size, refined_cell_size, time_units, ath1, ...) busts
                  # every existing cache instead of being silently ignored.
                  # json.dumps(..., sort_keys=True) below sorts this nested dict's
                  # keys too, so the hash is deterministic regardless of
                  # LOCKED_PARAMS's declaration order.
                  locked=dict(LOCKED_PARAMS),
                  # Fold a fingerprint of the model SOURCE into the cache identity
                  # too.  LOCKED_PARAMS only covers edits to that one dict --
                  # editing DOUBLET_Q, SPILL_UPGRADIENT_M, INJ_XY/ABS_XY, the Kd
                  # formula, the MST decay wiring, SRC cell placement,
                  # _courant_nstp, or _mass_balance would otherwise leave the
                  # hash (and every warm cache, notebook users included) unchanged
                  # while the model itself changed underneath it.  `model_io_utils`
                  # is in the fingerprint because it BUILDS the refined grid
                  # (mio.build_refined_gwf_model): an edit to grid generation
                  # changes this model just as surely as an edit here does.
                  src_sha=_src_sha())
    cache_hash = hashlib.sha1(
        json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    cache = case_ws / f"srcpulse_cache_{cache_hash}.npz"
    if cache.exists() and not force:
        cached = _load_cache(cache, params)
        if cached is not None:
            return cached

    cgwf, boundary, rivers, exe = _load_calibrated_flow()
    heads_array = cgwf.output.head().get_data().flatten()

    # ---- regional flow direction at the extraction well -> upgradient spill ----
    mg0 = cgwf.modelgrid
    xc0 = np.array(mg0.xcellcenters); yc0 = np.array(mg0.ycellcenters)
    spd0 = cgwf.output.budget().get_data(text="DATA-SPDIS")[0]
    ia = int(np.argmin((xc0 - ABS_XY[0]) ** 2 + (yc0 - ABS_XY[1]) ** 2))
    u_reg = np.array([spd0["qx"][ia], spd0["qy"][ia]], float)
    u_reg = u_reg / np.hypot(*u_reg)                     # flow (downgradient) unit vector
    spill_xy = (ABS_XY[0] - SPILL_UPGRADIENT_M * u_reg[0],
                ABS_XY[1] - SPILL_UPGRADIENT_M * u_reg[1])

    # ---- corridor refinement (spill->extraction corridor + injection well) ----
    corr_pts, u, L = _corridor_points(spill_xy, ABS_XY)
    refine_points = corr_pts + [tuple(INJ_XY)]
    res, refine_radius_used = _refine_with_retry(
        cgwf, boundary, rivers, refine_points, heads_array, case_ws / "refgrid",
        refine_radii=refine_radii, base_cell_size=LOCKED_PARAMS["base_cell_size"],
        refined_cell_size=LOCKED_PARAMS["refined_cell_size"], sim_name="rg")
    rgwf = res["gwf"]; mg = res["modelgrid"]; gp = res["gridprops"]; ncpl = res["ncpl"]
    xc = np.array(mg.xcellcenters); yc = np.array(mg.ycellcenters)
    csz = _cellsize(mg, ncpl)

    k_ref = rgwf.npf.k.array; top_ref = rgwf.disv.top.array; botm_ref = rgwf.disv.botm.array
    heads_ref = rgwf.output.head().get_data().flatten()
    chd = rgwf.get_package("CHD").stress_period_data.get_data(0)
    riv = rgwf.get_package("RIV").stress_period_data.get_data(0)
    rch = rgwf.get_package("RCHA").recharge.get_data()

    injc = int(np.argmin((xc - INJ_XY[0]) ** 2 + (yc - INJ_XY[1]) ** 2))
    extc = int(np.argmin((xc - ABS_XY[0]) ** 2 + (yc - ABS_XY[1]) ** 2))
    src_cells = [int(np.argmin((xc - spill_xy[0]) ** 2 + (yc - spill_xy[1]) ** 2))]
    n_src = len(src_cells)
    smassrate = float(mass_g) / (n_src * float(pulse_days))   # per-cell SRC loading [g/d]

    line = LineString([tuple(spill_xy), tuple(ABS_XY)])
    corridor_mask = np.array([line.distance(Point(xc[i], yc[i])) < refine_radius_used
                              for i in range(ncpl)])

    def _make_sim(nstp_per_period):
        ws = str(case_ws / "sim")
        sim = flopy.mf6.MFSimulation(sim_name="srcpulse", exe_name=exe, sim_ws=ws)
        # TDIS: 2 periods -> pulse ON (T), then OFF (migration)
        n_on = max(int(nstp_per_period * float(pulse_days) / float(total_days)), 1)
        n_off = max(nstp_per_period - n_on, 1)
        perioddata = [(float(pulse_days), n_on, 1.0),
                      (float(total_days) - float(pulse_days), n_off, 1.0)]
        nper = len(perioddata)
        flopy.mf6.ModflowTdis(sim, time_units=LOCKED_PARAMS["time_units"],
                              nper=nper, perioddata=perioddata)
        flopy.mf6.ModflowIms(sim, filename="gwf.ims", **_GWF_IMS)
        gwf = flopy.mf6.ModflowGwf(sim, modelname="gwf", save_flows=True,
                                   newtonoptions=_GWF_NEWTON)
        flopy.mf6.ModflowGwfdisv(gwf, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                                 botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
        flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=k_ref, save_flows=True,
                                save_specific_discharge=True)
        flopy.mf6.ModflowGwfic(gwf, strt=np.maximum(heads_ref, botm_ref[0] + 0.01))
        flopy.mf6.ModflowGwfsto(gwf, steady_state={i: True for i in range(nper)})
        flopy.mf6.ModflowGwfrcha(gwf, recharge=rch)
        flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["head"]))
                                                         for r in chd])
        flopy.mf6.ModflowGwfriv(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["stage"]),
                                float(r["cond"]), float(r["rbot"])) for r in riv])
        # ---- doublet wells: FLOW ONLY (clean injection, no concentration) ----
        flopy.mf6.ModflowGwfwel(gwf, pname="injw",
                                stress_period_data={0: [[(0, injc), abs(DOUBLET_Q)]]})
        flopy.mf6.ModflowGwfwel(gwf, pname="absw",
                                stress_period_data={0: [[(0, extc), -abs(DOUBLET_Q)]]})
        flopy.mf6.ModflowGwfoc(gwf, head_filerecord="gwf.hds", budget_filerecord="gwf.cbc",
                               saverecord=[("HEAD", "LAST"), ("BUDGET", "LAST")])
        # ---- GWT (solute = the spill, introduced via SRC mass loading) ----
        gwt = flopy.mf6.ModflowGwt(sim, modelname="gwt", save_flows=True)
        flopy.mf6.ModflowGwtdisv(gwt, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                                 botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
        flopy.mf6.ModflowGwtic(gwt, strt=0.0)
        # ---- MST: porosity always; sorption only when R > 1; decay only when lam > 0.
        # decay_sorbed is only MF6-valid when sorption is active (decay_sorbed requires
        # sorption="linear"/"freundlich"/"langmuir"), so it is gated on R > 1 as well.
        mst_kwargs: Dict[str, Any] = dict(porosity=LOCKED_PARAMS["porosity"])
        if R > 1.0:
            mst_kwargs.update(sorption="linear", bulk_density=rho_b, distcoef=Kd)
        if lam > 0.0:
            mst_kwargs.update(first_order_decay=True, decay=lam)
            if R > 1.0:
                mst_kwargs.update(decay_sorbed=lam)
        flopy.mf6.ModflowGwtmst(gwt, **mst_kwargs)
        flopy.mf6.ModflowGwtadv(gwt, scheme=LOCKED_PARAMS["scheme"])
        flopy.mf6.ModflowGwtdsp(gwt, alh=alpha_L_eff, ath1=alpha_T_eff,
                                diffc=LOCKED_PARAMS["diffc"], xt3d_off=LOCKED_PARAMS["xt3d_off"])
        # bare SSM: CHD/RIV/RCHA/WEL flows carry default (0 inflow / cell-conc outflow)
        flopy.mf6.ModflowGwtssm(gwt)
        # SRC finite pulse: mass loading [g/d] in period 0, OFF in period 1
        src_spd = {0: [[(0, c), smassrate] for c in src_cells], 1: []}
        flopy.mf6.ModflowGwtsrc(gwt, stress_period_data=src_spd)
        flopy.mf6.ModflowGwtoc(gwt, concentration_filerecord="gwt.ucn",
                               budget_filerecord="gwt.cbc",
                               saverecord=[("CONCENTRATION", "ALL"), ("BUDGET", "ALL")])
        flopy.mf6.ModflowIms(sim, filename="gwt.ims", **_GWT_IMS)
        sim.register_ims_package(sim.get_package("gwt.ims"), ["gwt"])
        flopy.mf6.ModflowGwfgwt(sim, exgtype="GWF6-GWT6", exgmnamea="gwf", exgmnameb="gwt",
                                filename="srcpulse.gwfgwt")
        sim.write_simulation(silent=True)
        ok, buf = sim.run_simulation(silent=True)
        return sim, gwf, gwt, ok, buf

    # ---- pilot: read velocity, size Courant, then production ----
    sim, gwf, gwt, ok, buf = _make_sim(20)
    if not ok:
        raise RuntimeError("pilot run failed; listing tail:\n"
                           + _run_failure_tail(case_ws / "sim", buf))
    spd = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    vmag = np.sqrt(spd["qx"] ** 2 + spd["qy"] ** 2) / LOCKED_PARAMS["porosity"]
    # exclude BOTH doublet wells (inj + ext) AND the source cells from Courant binding
    corr_no_wells = corridor_mask.copy()
    for c in src_cells + [injc, extc]:
        corr_no_wells[c] = False
    nstp, dt, cr_act, cdiag = _courant_nstp(vmag, csz, corr_no_wells, float(total_days),
                                            cr_target, nstp_cap)

    sim, gwf, gwt, ok, buf = _make_sim(nstp)
    if not ok:
        raise RuntimeError("production run failed; listing tail:\n"
                           + _run_failure_tail(case_ws / "sim", buf))

    # ---- breakthrough at the extraction well ----
    cobj = gwt.output.concentration(); times = np.array(cobj.get_times())
    bt = np.maximum(np.array([cobj.get_data(totim=t)[0, 0, extc] for t in times]), 0.0)
    peak = float(bt.max()) if bt.size else float("nan")
    # `arrival_day = times[argmax(bt)]` with no guard is wrong-but-plausible in
    # two degenerate cases: (1) the plume never arrives (bt is all-zero) ->
    # argmax(bt) is 0 -> arrival is reported as "day <first output time>", not
    # "never"; (2) the breakthrough curve is STILL RISING at the end of a
    # too-short window -> the last sample (not a real peak) is reported as the
    # arrival.  Guard (1) with `peak <= 0.0` -> NaN; flag (2) via
    # `peak_at_last_step` below so callers (the notebook) can warn instead of
    # silently trusting a still-rising curve's last point.
    peak_at_last_step = bool(bt.size and int(np.argmax(bt)) == bt.size - 1)
    arrival = (float(times[int(np.argmax(bt))]) if (bt.size and peak > 0.0)
               else float("nan"))

    # ---- emergent source-cell concentration vs solubility ----
    q_src = float(np.hypot(spd["qx"][src_cells[0]], spd["qy"][src_cells[0]]))  # Darcy [m/d]
    b_src = float(max(heads_ref[src_cells[0]] - botm_ref[0][src_cells[0]], 0.1))
    ds_src = float(csz[src_cells[0]])
    q_cell = max(q_src * ds_src * b_src, 1e-6)                # advective throughflow [m^3/d]
    emergent_C = smassrate / q_cell                          # [g/m^3] == [mg/L]
    solubility_ok = bool(emergent_C < solubility_mgL)
    sol_margin = float(solubility_mgL / emergent_C) if emergent_C > 0 else float("inf")

    # ---- mass balance from the GWT listing budget ----
    mb = _mass_balance(case_ws / "sim" / "gwt.lst")

    # ---- grid Peclet on the corridor (uses the EFFECTIVE dispersivities) ----
    csz_corr = csz[corridor_mask]
    PeL_min = float(csz_corr.min() / alpha_L_eff)
    PeL_max = float(csz_corr.max() / alpha_L_eff)
    PeT_min = float(csz_corr.min() / alpha_T_eff)
    PeT_max = float(csz_corr.max() / alpha_T_eff)

    # cr_capped must flag BOTH ways the target Courant number can be missed:
    # (a) Cr_actual overshoots cr_target (the old `cr_act > 1.001` check), and
    # (b) nstp hit nstp_cap and truncated the step count before cr_target was
    # reached at all (e.g. nstp==nstp_cap with cr_act=0.96 > cr_target=0.9 --
    # the old check reports "not capped" even though the cap is exactly why
    # the target was missed).  `nstp >= nstp_cap` catches both: case (a) drives
    # nstp up until it saturates at the cap, and case (b) IS the cap binding.
    cr_capped = bool(nstp >= nstp_cap)
    if cr_capped:
        warnings.warn(
            f"srcpulse demo: nstp hit nstp_cap ({nstp_cap}); the target Courant "
            f"number cr_target={cr_target:g} may not have been reached "
            f"(Cr_actual={cr_act:.3f}). Diagnostics/results may be under-resolved "
            "in time -- consider raising nstp_cap.", RuntimeWarning, stacklevel=2)

    meta = dict(ncpl=ncpl, nstp=nstp, dt=dt, Cr=cr_act, n_src=n_src,
                q_src_darcy=q_src, b_src=b_src, ds_src=ds_src, q_cell=q_cell,
                v_bind=cdiag["v_bind"], ds_bind=cdiag["ds_bind"],
                ds_true_min=cdiag["ds_true_min"], courant_floor=cdiag["floor"],
                refine_radius_used=refine_radius_used, u_reg=tuple(u_reg),
                cr_capped=cr_capped, peak_at_last_step=peak_at_last_step)

    result = SrcPulseDemo(
        times=times, breakthrough=bt, peak_mgL=peak, arrival_day=arrival,
        mass_balance=mb, solubility_ok=solubility_ok, emergent_C_mgL=emergent_C,
        solubility_mgL=float(solubility_mgL), solubility_margin=sol_margin,
        PeL_min=PeL_min, PeL_max=PeL_max, PeT_min=PeT_min, PeT_max=PeT_max,
        mass_g=float(mass_g), pulse_days=float(pulse_days), total_days=float(total_days),
        smassrate_gpd=smassrate, src_cells=src_cells, ext_cell=extc, inj_cell=injc,
        spill_xy=(float(spill_xy[0]), float(spill_xy[1])),
        alpha_L=alpha_L_eff, alpha_T=alpha_T_eff, R=float(R), rho_b=float(rho_b),
        Kd=float(Kd), lam=float(lam), meta=meta)

    _save_cache(cache, result, params)
    return result


# ---------------------------------------------------------------------------
# mass balance from the GWT listing file
# ---------------------------------------------------------------------------
def _mass_balance(gwt_lst: Union[str, Path]) -> Dict[str, float]:
    """Cumulative GWT mass budget: SRC in, well out, boundary out, storage, decay, % imbalance.

    Reads the final cumulative budget from the GWT listing via Mf6ListBudget.
    Terms are grouped: source (SRC), extraction-well out (WEL), boundary out
    (RIV + CHD + RCHA / GHB), storage (STORAGE-AQUEOUS always; STORAGE-SORBED
    too when R > 1), decay (DECAY-AQUEOUS when lam > 0; DECAY-SORBED too when
    R > 1 as well), and the reported percent discrepancy.  Column names were
    verified against a real reactive (R>1) and a real decaying (lam>0) GWT
    listing -- MF6 emits "STORAGE-SORBED" (not "STORAGE-SORBATE").  Units are
    grams (model mg/L -> g/m^3, m/day).

    ``pct_imbalance`` is MF6's own PERCENT_DISCREPANCY -- it reflects only
    MF6's internal solve, not whether OUR substring grouping above actually
    captured every budget column without missing or double-counting one.
    ``grouped_residual_g`` is a separate self-check: it reconciles the sum of
    our grouped _IN / _OUT terms against MF6's own TOTAL_IN / TOTAL_OUT and
    should be ~0 g when the grouping is complete and non-overlapping.
    """
    from flopy.utils import Mf6ListBudget
    out: Dict[str, float] = {}
    try:
        # GWT listings use the MASS (not VOLUME) budget key.
        lst = Mf6ListBudget(str(gwt_lst), budgetkey="MASS BUDGET FOR ENTIRE MODEL")
        inc, cum = lst.get_dataframes()
        row = cum.iloc[-1]
    except Exception as e:                       # keep the demo robust
        # Return the expected NUMERIC keys as NaN alongside "error".  The
        # notebook does `for k, v in res.mass_balance.items(): print(f"{v:14.4g}")`
        # -- returning only {"error": ...} means that format spec crashes with
        # "ValueError: Unknown format code 'g' for object of type 'str'",
        # which hides the REAL MF6 parse error (this except's `e`) behind an
        # unrelated formatting traceback.
        return {
            "error": repr(e),
            "src_in_g": float("nan"), "well_out_g": float("nan"),
            "boundary_out_g": float("nan"), "storage_g": float("nan"),
            "decay_g": float("nan"), "total_in_g": float("nan"),
            "total_out_g": float("nan"), "pct_imbalance": float("nan"),
            "grouped_residual_g": float("nan"),
        }

    def _grab(substr_in, substr_out=None):
        _in = sum(float(row[c]) for c in row.index if substr_in in c.upper() and c.upper().endswith("_IN"))
        key_out = substr_out if substr_out is not None else substr_in
        _out = sum(float(row[c]) for c in row.index if key_out in c.upper() and c.upper().endswith("_OUT"))
        return _in, _out

    src_in, src_out = _grab("SRC")
    wel_in, wel_out = _grab("WEL")
    riv_in, riv_out = _grab("RIV")
    chd_in, chd_out = _grab("CHD")
    rch_in, rch_out = _grab("RCH")
    sto_in, sto_out = 0.0, 0.0
    dcy_in, dcy_out = 0.0, 0.0
    for c in row.index:
        cu = c.upper()
        # both storage flavours a reactive (sorbing) run emits -- STORAGE-AQUEOUS and
        # STORAGE-SORBED -- share the "STORAGE" substring with the conservative-run
        # "STORAGE" term, so this single branch already catches all of them (verified
        # against a real R>1 gwt.lst).  (MF6 emits STORAGE-AQUEOUS/STORAGE-SORBED,
        # never an "MST"-prefixed budget column, so that alternative is dead code.)
        if "STORAGE" in cu:
            if cu.endswith("_IN"):
                sto_in += float(row[c])
            elif cu.endswith("_OUT"):
                sto_out += float(row[c])
        # decay terms (DECAY / DECAY-AQUEOUS / DECAY-SORBED) only appear when
        # first_order_decay=True on MST; net mass loss usually lands in _OUT.
        if "DECAY" in cu:
            if cu.endswith("_IN"):
                dcy_in += float(row[c])
            elif cu.endswith("_OUT"):
                dcy_out += float(row[c])

    total_in = float(row["TOTAL_IN"]) if "TOTAL_IN" in row.index else None
    total_out = float(row["TOTAL_OUT"]) if "TOTAL_OUT" in row.index else None
    if "PERCENT_DISCREPANCY" in row.index:
        pct = float(row["PERCENT_DISCREPANCY"])
    elif total_in is not None and total_out is not None and (total_in + total_out) != 0:
        pct = 100.0 * (total_in - total_out) / (0.5 * (total_in + total_out))
    else:
        pct = float("nan")

    # ---- self-check: reconcile OUR substring-grouped terms against MF6's own
    # TOTAL_IN / TOTAL_OUT. pct_imbalance above is MF6's own PERCENT_DISCREPANCY --
    # it says nothing about whether the grouping just above (SRC/WEL/RIV/CHD/RCH,
    # "STORAGE" in cu, "DECAY" in cu) missed or double-counted a budget column.
    # If it did, the sum of our grouped _IN terms will drift from MF6's TOTAL_IN
    # (and likewise for _OUT), even while pct_imbalance stays ~0%.
    grouped_total_in = src_in + wel_in + riv_in + chd_in + rch_in + sto_in + dcy_in
    grouped_total_out = src_out + wel_out + riv_out + chd_out + rch_out + sto_out + dcy_out
    if total_in is not None and total_out is not None:
        grouped_residual_g = float(abs(grouped_total_in - total_in)
                                    + abs(grouped_total_out - total_out))
    else:
        grouped_residual_g = float("nan")

    out.update(
        src_in_g=src_in,
        well_out_g=wel_out,
        boundary_out_g=riv_out + chd_out + rch_out,
        storage_g=sto_out - sto_in,           # net into storage (accumulation) [g]
        decay_g=dcy_out - dcy_in,             # net mass removed by decay [g] (0 if no decay)
        total_in_g=total_in if total_in is not None else float("nan"),
        total_out_g=total_out if total_out is not None else float("nan"),
        pct_imbalance=pct,
        grouped_residual_g=grouped_residual_g,
    )
    return out


# ---------------------------------------------------------------------------
# cache (solve-free re-call)
# ---------------------------------------------------------------------------
def _save_cache(path: Path, r: SrcPulseDemo, params: Dict[str, Any]) -> None:
    np.savez(str(path), times=r.times, breakthrough=r.breakthrough,
             peak_mgL=r.peak_mgL, arrival_day=r.arrival_day,
             mass_balance=r.mass_balance, solubility_ok=r.solubility_ok,
             emergent_C_mgL=r.emergent_C_mgL, solubility_mgL=r.solubility_mgL,
             solubility_margin=r.solubility_margin,
             PeL_min=r.PeL_min, PeL_max=r.PeL_max, PeT_min=r.PeT_min, PeT_max=r.PeT_max,
             mass_g=r.mass_g, pulse_days=r.pulse_days, total_days=r.total_days,
             smassrate_gpd=r.smassrate_gpd, src_cells=np.array(r.src_cells),
             ext_cell=r.ext_cell, inj_cell=r.inj_cell, spill_xy=np.array(r.spill_xy),
             alpha_L=r.alpha_L, alpha_T=r.alpha_T, R=r.R, rho_b=r.rho_b, Kd=r.Kd, lam=r.lam,
             meta=r.meta, locked=r.locked, params=params, allow_pickle=True)


def _load_cache(path: Path, params: Dict[str, Any]) -> Optional[SrcPulseDemo]:
    # The WHOLE body (params-key check, value comparison, AND the SrcPulseDemo
    # construction/z[...] reads below) lives inside this one try.  Previously
    # only np.load + z["params"].item() were guarded: the 29 z[...] reads below
    # sat OUTSIDE the try, protected only by the params key-set check above.
    # That means a future dataclass field added WITHOUT touching the hashed
    # `params` dict would pass the key-set guard on every existing warm cache
    # and then KeyError on the read -- crashing instead of cleanly rebuilding.
    # Wrapping everything means any bad/incomplete/legacy cache just MISSES.
    try:
        z = np.load(str(path), allow_pickle=True)
        stored = dict(z["params"].item())
        # A missing/extra key must NOT silently count as a match (e.g.
        # stored.get(k, nan) comparing "> 1e-9" as False for a missing key
        # would look like equality).
        if set(stored) != set(params):
            return None                      # key set changed -> rebuild
        for k, v in params.items():
            sv = stored[k]
            if k == "refine_radii":
                # non-scalar entry: compare as arrays, not via a bare "abs(list - list)".
                sv_arr = np.asarray(sv, dtype=float)
                v_arr = np.asarray(v, dtype=float)
                if sv_arr.shape != v_arr.shape or np.any(np.abs(sv_arr - v_arr) > 1e-9):
                    return None
            elif k == "locked":
                # non-scalar (nested dict) entry: mixed str/float/bool values, so
                # compare via a canonical JSON dump rather than a bare "==" (which
                # would work here too, but this stays robust if a future
                # LOCKED_PARAMS value becomes a list/array).
                if json.dumps(sv, sort_keys=True) != json.dumps(v, sort_keys=True):
                    return None
            elif isinstance(v, str) or isinstance(sv, str):
                # e.g. src_sha: a plain string value.  The numeric branch below
                # does `abs(float(sv) - float(v))`, which would crash (or worse,
                # silently coerce) on a non-numeric string -- compare by equality.
                if str(sv) != str(v):
                    return None
            else:
                if abs(float(sv) - float(v)) > 1e-9:
                    return None              # params changed -> rebuild
        return SrcPulseDemo(
            times=z["times"], breakthrough=z["breakthrough"],
            peak_mgL=float(z["peak_mgL"]), arrival_day=float(z["arrival_day"]),
            mass_balance=dict(z["mass_balance"].item()), solubility_ok=bool(z["solubility_ok"]),
            emergent_C_mgL=float(z["emergent_C_mgL"]), solubility_mgL=float(z["solubility_mgL"]),
            solubility_margin=float(z["solubility_margin"]),
            PeL_min=float(z["PeL_min"]), PeL_max=float(z["PeL_max"]),
            PeT_min=float(z["PeT_min"]), PeT_max=float(z["PeT_max"]),
            mass_g=float(z["mass_g"]), pulse_days=float(z["pulse_days"]),
            total_days=float(z["total_days"]), smassrate_gpd=float(z["smassrate_gpd"]),
            src_cells=[int(c) for c in z["src_cells"]], ext_cell=int(z["ext_cell"]),
            inj_cell=int(z["inj_cell"]),
            # Cast to plain Python float (not np.float64): the build path
            # produces Python floats, and _save_cache round-trips through
            # np.array(r.spill_xy) -- without this cast, a cache HIT returns a
            # tuple of np.float64 that compares equal (np.float64(x) == x) but
            # is a different TYPE, which bites e.g. json.dumps(demo.spill_xy).
            spill_xy=(float(z["spill_xy"][0]), float(z["spill_xy"][1])),
            alpha_L=float(z["alpha_L"]), alpha_T=float(z["alpha_T"]),
            R=float(z["R"]), rho_b=float(z["rho_b"]), Kd=float(z["Kd"]), lam=float(z["lam"]),
            meta=dict(z["meta"].item()), locked=dict(z["locked"].item()))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# demo / smoke anchor
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    t0 = time.time()
    r = build_srcpulse_demo(mass_g=3.0e5, pulse_days=30.0, total_days=120.0,
                            solubility_mgL=1000.0, force=("--force" in sys.argv))
    dt = time.time() - t0
    print("SRC FINITE-PULSE SPILL -> CAPTURE DEMO")
    print(f"  released mass M      = {r.mass_g:.4g} g  over T = {r.pulse_days:.0f} d "
          f"(total {r.total_days:.0f} d)")
    print(f"  per-cell SRC loading = {r.smassrate_gpd:.4g} g/d  ({r.meta['n_src']} src cell)")
    print(f"  spill_xy             = ({r.spill_xy[0]:.1f}, {r.spill_xy[1]:.1f})  "
          f"[{SPILL_UPGRADIENT_M:.0f} m upgradient of ABS]")
    print(f"  peak breakthrough    = {r.peak_mgL:.4g} mg/L  at day {r.arrival_day:.1f}")
    print(f"  emergent source C    = {r.emergent_C_mgL:.4g} mg/L  "
          f"(solubility {r.solubility_mgL:.0f} mg/L; margin x{r.solubility_margin:.1f}) -> "
          f"{'PASS' if r.solubility_ok else 'FAIL'}")
    mb = r.mass_balance
    print("  mass balance [g]:")
    print(f"    SRC in       = {mb.get('src_in_g', float('nan')):.4g}")
    print(f"    well out     = {mb.get('well_out_g', float('nan')):.4g}")
    print(f"    boundary out = {mb.get('boundary_out_g', float('nan')):.4g}")
    print(f"    storage      = {mb.get('storage_g', float('nan')):.4g}")
    print(f"    % imbalance  = {mb.get('pct_imbalance', float('nan')):.3f}")
    print(f"  Pe_L corridor = {r.PeL_min:.2f}..{r.PeL_max:.2f}   "
          f"Pe_T = {r.PeT_min:.2f}..{r.PeT_max:.2f}")
    print(f"  Cr peak = {r.meta['Cr']:.2f}  nstp={r.meta['nstp']}  "
          f"refine_radius={r.meta['refine_radius_used']:.0f} m")
    print(f"  wall-clock = {dt:.0f}s")
    ok = (r.solubility_ok and r.peak_mgL > 0
          and abs(mb.get("pct_imbalance", 99)) < 5.0 and r.PeL_max <= 2.0)
    print("  SMOKE:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
