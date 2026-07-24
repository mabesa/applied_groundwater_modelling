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
a mass-balance table from the binary GWT budget (SRC in, well out, boundary out,
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


def _budget_has_spdis(cgwf) -> bool:
    """True iff the loaded model's saved budget carries the DATA-SPDIS record."""
    try:
        recs = cgwf.output.budget().get_unique_record_names(decode=True)
    except Exception:
        return False  # no/unreadable .cbc -> treat as missing so we regenerate
    return any("DATA-SPDIS" in str(r) for r in recs)


def _ensure_spdis(csim, cgwf, flow_ws, exe):
    """Guarantee the coarse flow model's budget carries ``DATA-SPDIS``.

    The transport track reads the specific-discharge recarray
    (``cgwf.output.budget().get_data(text='DATA-SPDIS')``) to place the spill and
    Courant-size the time steps. A pre-computed / archived flow model whose NPF
    was saved without ``save_specific_discharge`` lacks that record, so loading it
    on a fresh JupyterHub (or any stale ``<data>/calibration`` cache) raises
    "The specified text string is not in the budget file."

    We repair it in place: enable the specific-discharge output flags and re-run
    the (steady-state, single-period) model — a few-second regeneration that
    persists in the workspace, so it is a one-time cost per workspace. Returns a
    freshly reloaded ``(csim, cgwf)`` so downstream output handles read the new
    ``.cbc``.
    """
    if _budget_has_spdis(cgwf):
        return csim, cgwf

    mname = cgwf.name
    cgwf.npf.save_specific_discharge = True
    cgwf.npf.save_flows = True
    try:
        cgwf.npf.save_saturation = True
    except Exception:
        pass  # older grids may not expose the option; SPDIS only needs the two above

    try:
        csim.write_simulation(silent=True)
        ok, buf = csim.run_simulation(silent=True)
    except Exception as exc:
        raise RuntimeError(
            "The calibrated flow model's budget lacks specific discharge "
            "(DATA-SPDIS), which the transport track needs, and it could not be "
            f"regenerated (is the workspace writable and mf6 available?).\n"
            f"  workspace: {flow_ws}\n  mf6: {exe}\n(underlying error: {exc})"
        ) from exc
    if not ok:
        tail = "\n".join(buf[-15:]) if buf else ""
        raise RuntimeError(
            "Re-running the calibrated flow model to add specific discharge "
            f"(DATA-SPDIS) failed.\n  workspace: {flow_ws}\n  mf6: {exe}\n{tail}"
        )

    # reload so cached output handles point at the freshly written .cbc
    csim = flopy.mf6.MFSimulation.load(sim_ws=str(flow_ws), exe_name=exe, verbosity_level=0)
    return csim, csim.get_model(mname)


def _load_calibrated_flow():
    """Load the 05f-calibrated coarse flow model + GIS (boundary, Limmat/Sihl)."""
    from data_utils import download_named_file
    flow_ws = mio.ensure_flow_model()
    # prefer an mf6 already on PATH; fall back to the flopy-bin install location.
    exe = shutil.which("mf6") or _MF6_FALLBACK
    csim = flopy.mf6.MFSimulation.load(sim_ws=str(flow_ws), exe_name=exe, verbosity_level=0)
    cgwf = csim.get_model("limmat_valley")
    # Archived / stale flow models may lack DATA-SPDIS in their budget; the
    # transport track requires it, so regenerate it once if missing.
    csim, cgwf = _ensure_spdis(csim, cgwf, flow_ws, exe)
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
# PUBLIC builders -- the visible, teachable model-construction API.
#
# ``build_srcpulse_demo`` below is exactly these composed in order:
#     load_limmat_flow -> refine_corridor
#       -> (pilot)      new_sim -> add_flow_model -> add_transport_model -> couple_and_run
#       -> (production) new_sim -> add_flow_model -> add_transport_model -> couple_and_run
# The messy corridor-refinement SIGILL retry stays hidden inside
# ``refine_corridor``; every FloPy package call is the verbatim, real construction
# a notebook can render and read.
# ---------------------------------------------------------------------------
def load_limmat_flow():
    """Load the 05f-calibrated coarse **Limmat valley** GWF + GIS.

    Thin public wrapper over ``_load_calibrated_flow``.  Returns
    ``(cgwf, boundary_gdf, rivers_gdf, exe)``: the coarse Limmat GWF model, the
    model-boundary polygon, the Limmat/Sihl river lines, and the resolved mf6
    executable path.
    """
    return _load_calibrated_flow()


def refine_corridor(cgwf, boundary, rivers, spill_xy=None, *,
                    refine_radii: Sequence[float] = (70.0, 62.0, 78.0, 56.0, 84.0),
                    case_ws: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Refine the spill->extraction corridor and return a **GridBundle** dict.

    Computes the local regional-flow direction at the extraction well (to place
    the spill ``SPILL_UPGRADIENT_M`` upgradient, unless ``spill_xy`` is given),
    then corridor-refines the DISV grid via ``_refine_with_retry`` (the macOS
    arm64 SIGILL / Triangle-precision radius-walk stays INSIDE this call).

    The returned dict carries everything the sim builders need -- modelgrid,
    gridprops, cell arrays, boundary stress data, and the injection / extraction /
    source cell indices -- so nothing downstream reaches back into the coarse or
    refined GWF objects.
    """
    heads_array = cgwf.output.head().get_data().flatten()

    # ---- regional flow direction at the extraction well -> upgradient spill ----
    mg0 = cgwf.modelgrid
    xc0 = np.array(mg0.xcellcenters); yc0 = np.array(mg0.ycellcenters)
    spd0 = cgwf.output.budget().get_data(text="DATA-SPDIS")[0]
    ia = int(np.argmin((xc0 - ABS_XY[0]) ** 2 + (yc0 - ABS_XY[1]) ** 2))
    u_reg = np.array([spd0["qx"][ia], spd0["qy"][ia]], float)
    u_reg = u_reg / np.hypot(*u_reg)                     # flow (downgradient) unit vector
    if spill_xy is None:
        spill_xy = (ABS_XY[0] - SPILL_UPGRADIENT_M * u_reg[0],
                    ABS_XY[1] - SPILL_UPGRADIENT_M * u_reg[1])

    # ---- corridor refinement (spill->extraction corridor + injection well) ----
    case_ws = Path(case_ws) if case_ws is not None else _default_case_ws()
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

    line = LineString([tuple(spill_xy), tuple(ABS_XY)])
    corridor_mask = np.array([line.distance(Point(xc[i], yc[i])) < refine_radius_used
                              for i in range(ncpl)])

    return dict(
        modelgrid=mg, gridprops=gp, ncpl=ncpl, nvert=gp["nvert"],
        top=top_ref, botm=botm_ref, k=k_ref, heads=heads_ref,
        chd=chd, riv=riv, rch=rch, cellsize=csz, xc=xc, yc=yc,
        inj_cell=injc, ext_cell=extc, src_cells=src_cells,
        spill_xy=(float(spill_xy[0]), float(spill_xy[1])),
        corridor_mask=corridor_mask, u_reg=tuple(u_reg),
        refine_radius_used=refine_radius_used, rgwf=rgwf)


def new_sim(case_ws: Union[str, Path], *, pulse_days: float, total_days: float,
            nstp_per_period: int, exe: str):
    """Create the ``MFSimulation`` + TDIS (2 periods: pulse ON / migration) + the
    GWF IMS solver.

    TDIS period 0 is the ON pulse (duration ``pulse_days``), period 1 the
    post-pulse migration (``total_days - pulse_days``); ``nstp_per_period`` is
    split between them in proportion to their durations.  The GWT IMS solver is
    added later (in ``add_transport_model``, after the GWT model exists, to
    preserve the original construction order).
    """
    ws = str(Path(case_ws) / "sim")
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
    return sim


def add_flow_model(sim, grid: Dict[str, Any]):
    """Add the GWF flow model (DISV, NPF, IC, STO, RCHA, CHD, RIV, WEL x2 doublet,
    OC) to ``sim`` and return it.  The doublet wells are FLOW ONLY (no solute)."""
    ncpl = grid["ncpl"]; gp = grid["gridprops"]
    top_ref = grid["top"]; botm_ref = grid["botm"]; k_ref = grid["k"]
    heads_ref = grid["heads"]; rch = grid["rch"]; chd = grid["chd"]; riv = grid["riv"]
    injc = grid["inj_cell"]; extc = grid["ext_cell"]
    nper = int(sim.tdis.nper.get_data())

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
    return gwf


def add_transport_model(sim, gwf, grid: Dict[str, Any], *, mass_g: float,
                        pulse_days: float, R: float = 1.0, rho_b: float = 1800.0,
                        lam: float = 0.0, alpha_L: Optional[float] = None):
    """Add the GWT solute-transport model (DISV, IC, MST, ADV/TVD, DSP, SSM, SRC,
    OC) + the GWT IMS solver to ``sim`` and return it.

    The spill enters via the SRC package as a per-cell mass loading
    ``smassrate = mass_g / (n_src_cells * pulse_days)`` [g/d], ON in period 0 and
    OFF in period 1.  ``alpha_L`` defaults to the LOCKED longitudinal dispersivity;
    ``alpha_T`` is derived from the LOCKED 10:1 ratio.  MST sorption is gated on
    ``R > 1`` (``Kd = (R-1)*porosity/rho_b``) and first-order decay on ``lam > 0``.
    """
    ncpl = grid["ncpl"]; gp = grid["gridprops"]
    top_ref = grid["top"]; botm_ref = grid["botm"]
    src_cells = grid["src_cells"]

    alpha_L_eff = float(LOCKED_PARAMS["alh"]) if alpha_L is None else float(alpha_L)
    alpha_T_eff = alpha_L_eff * (float(LOCKED_PARAMS["ath1"]) / float(LOCKED_PARAMS["alh"]))
    porosity = float(LOCKED_PARAMS["porosity"])
    Kd = (float(R) - 1.0) * porosity / float(rho_b) if R > 1.0 else 0.0
    n_src = len(src_cells)
    smassrate = float(mass_g) / (n_src * float(pulse_days))   # per-cell SRC loading [g/d]

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
    return gwt


def couple_and_run(sim, gwf, gwt, grid: Dict[str, Any],
                   case_ws: Union[str, Path]) -> Tuple[bool, Any, Any]:
    """Register the GWF6-GWT6 exchange, write, and run the coupled simulation.

    Returns ``(ok, buf, sim)`` -- the ``run_simulation`` success flag, its output
    buffer, and the (run) simulation object.  ``gwf`` / ``gwt`` make the coupled
    pair explicit even though the exchange references them by model name.
    """
    flopy.mf6.ModflowGwfgwt(sim, exgtype="GWF6-GWT6", exgmnamea="gwf", exgmnameb="gwt",
                            filename="srcpulse.gwfgwt")
    sim.write_simulation(silent=True)
    ok, buf = sim.run_simulation(silent=True)
    return ok, buf, sim


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
                  src_sha=_src_sha(),
                  # A fingerprint of the calibrated flow DATA itself (not its
                  # source): the 1,080->2,160 m³/d recalibration changed the
                  # downloaded flow field without touching src_sha, so this is what
                  # busts the warm cache on that change.
                  flow_fp=mio.calibrated_flow_fingerprint())
    cache_hash = hashlib.sha1(
        json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    cache = case_ws / f"srcpulse_cache_{cache_hash}.npz"
    if cache.exists() and not force:
        cached = _load_cache(cache, params)
        if cached is not None:
            return cached

    # ---- load + refine (the visible builders; SIGILL retry stays inside) ----
    cgwf, boundary, rivers, exe = load_limmat_flow()
    grid = refine_corridor(cgwf, boundary, rivers, refine_radii=refine_radii,
                           case_ws=case_ws)
    ncpl = grid["ncpl"]
    csz = grid["cellsize"]
    heads_ref = grid["heads"]; botm_ref = grid["botm"]
    injc = grid["inj_cell"]; extc = grid["ext_cell"]; src_cells = grid["src_cells"]
    corridor_mask = grid["corridor_mask"]
    refine_radius_used = grid["refine_radius_used"]
    u_reg = np.array(grid["u_reg"], float)
    spill_xy = grid["spill_xy"]
    n_src = len(src_cells)
    smassrate = float(mass_g) / (n_src * float(pulse_days))   # per-cell SRC loading [g/d]

    def _make_sim(nstp_per_period):
        """Compose the public builders into one coupled GWF+GWT solve."""
        sim = new_sim(case_ws, pulse_days=pulse_days, total_days=total_days,
                      nstp_per_period=nstp_per_period, exe=exe)
        gwf = add_flow_model(sim, grid)
        gwt = add_transport_model(sim, gwf, grid, mass_g=mass_g, pulse_days=pulse_days,
                                  R=R, rho_b=rho_b, lam=lam, alpha_L=alpha_L_eff)
        ok, buf, sim = couple_and_run(sim, gwf, gwt, grid, case_ws)
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

    # ---- mass balance from the binary GWT budget (gwt.cbc) ----
    mb = _mass_balance(case_ws / "sim" / "gwt.cbc")

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
_MB_NUMERIC_KEYS = (
    "src_in_g", "well_out_g", "boundary_out_g", "storage_g", "decay_g",
    "total_in_g", "total_out_g", "pct_imbalance", "grouped_residual_g",
)
# Budget-record substrings -> mass-balance group. Each GWT budget record name
# (SRC, WEL, RIV, CHD, RCHA, STORAGE-AQUEOUS/-SORBED, DECAY-AQUEOUS/-SORBED) is
# classified by the FIRST substring it contains. FLOW-JA-FACE / DATA-SPDIS are
# internal/GWF and excluded.
_MB_GROUPS = ("SRC", "WEL", "RIV", "CHD", "RCH", "STORAGE", "DECAY")


def _mass_balance(gwt_cbc: Union[str, Path]) -> Dict[str, float]:
    """Cumulative GWT mass budget: SRC in, well out, boundary out, storage, decay, % imbalance.

    Reads the BINARY GWT budget (``gwt.cbc``) and integrates each package's
    per-timestep flow rate [g/d] over the run (rate x dt) to recover cumulative
    mass [g]. Terms are grouped exactly as before: source (SRC), extraction-well
    out (WEL), boundary out (RIV + CHD + RCHA), storage (STORAGE-AQUEOUS always;
    STORAGE-SORBED too when R > 1), decay (DECAY-AQUEOUS when lam > 0; DECAY-SORBED
    too when R > 1). Units are grams (model g/m^3, m/day).

    Why the binary budget, not the text listing (``Mf6ListBudget`` on ``gwt.lst``):
    at high pumping (2,160 m3/d) a cumulative boundary-mass term overflows the
    listing's fixed-width Fortran field ("error casting in cumu for CHD to float"),
    so the listing parse silently returns NaN for that term -> NaN pct_imbalance.
    The binary budget stores float64 rates with no field-width limit, so it is
    robust at any magnitude. Cumulative = sum_i(rate_i * dt_i) reproduces MF6's own
    cumulative (rate is constant over each step).

    ``pct_imbalance`` is the percent discrepancy of the integrated TOTAL_IN vs
    TOTAL_OUT. ``grouped_residual_g`` is a self-check: the sum of the grouped
    terms above reconciled against the all-records total; ~0 g iff the grouping
    captured every budget record without missing or double-counting one.
    """
    from flopy.utils import CellBudgetFile
    try:
        cbc = CellBudgetFile(str(gwt_cbc))
        times = list(cbc.get_times())
        raw_names = cbc.get_unique_record_names(decode=True)
        names = [n.decode() if isinstance(n, bytes) else n for n in raw_names]
        names = [n.strip() for n in names]
    except Exception as e:                       # keep the demo robust
        # Return the expected NUMERIC keys as NaN alongside "error" so the
        # notebook's `f"{v:14.4g}"` over mass_balance.values() does not crash on a
        # str and hide the REAL read error behind a formatting traceback.
        return {"error": repr(e), **{k: float("nan") for k in _MB_NUMERIC_KEYS}}

    acc = {g: [0.0, 0.0] for g in _MB_GROUPS}    # group -> [cum_in_g, cum_out_g]
    other = [0.0, 0.0]                            # records matching NO group (see below)
    total_in_all = total_out_all = 0.0
    t_prev = 0.0
    for t in times:
        dt = t - t_prev
        t_prev = t
        for name in names:
            u = name.upper()
            if "FLOW-JA-FACE" in u or "DATA-SPDIS" in u:
                continue
            try:
                data = cbc.get_data(text=name, totim=t)
            except Exception:
                continue
            if not data:
                continue
            arr = data[0]
            if getattr(arr, "dtype", None) is not None and arr.dtype.names \
                    and "q" in arr.dtype.names:
                q = np.asarray(arr["q"], dtype=float)
            else:
                q = np.asarray(arr, dtype=float).ravel()
            q_in = float(q[q > 0].sum()) * dt
            q_out = float(-q[q < 0].sum()) * dt
            total_in_all += q_in
            total_out_all += q_out
            grp = next((g for g in _MB_GROUPS if g in u), None)
            if grp is not None:
                acc[grp][0] += q_in
                acc[grp][1] += q_out
            else:
                # Ungrouped record. The BINARY GWT budget aggregates the SSM
                # boundary+well solute flux under a single record (e.g. "SSM")
                # rather than per-package (WEL/CHD/RIV/RCHA) as the text listing
                # does, so the dominant sink (the extraction well capturing the
                # plume) matches none of _MB_GROUPS. Fold it into the boundary
                # term so the budget still CLOSES (Σ grouped == Σ all-records).
                other[0] += q_in
                other[1] += q_out

    src_in, src_out = acc["SRC"]
    wel_in, wel_out = acc["WEL"]
    riv_in, riv_out = acc["RIV"]
    chd_in, chd_out = acc["CHD"]
    rch_in, rch_out = acc["RCH"]
    sto_in, sto_out = acc["STORAGE"]
    dcy_in, dcy_out = acc["DECAY"]

    denom = 0.5 * (total_in_all + total_out_all)
    pct = 100.0 * (total_in_all - total_out_all) / denom if denom != 0 else float("nan")

    grouped_in = (src_in + wel_in + riv_in + chd_in + rch_in + sto_in + dcy_in
                  + other[0])
    grouped_out = (src_out + wel_out + riv_out + chd_out + rch_out + sto_out + dcy_out
                   + other[1])
    grouped_residual_g = float(abs(grouped_in - total_in_all)
                               + abs(grouped_out - total_out_all))

    return {
        "src_in_g": src_in,
        "well_out_g": wel_out,
        # includes any SSM-aggregated boundary/well sink (see the `other` bucket)
        "boundary_out_g": riv_out + chd_out + rch_out + other[1],
        "storage_g": sto_out - sto_in,        # net into storage (accumulation) [g]
        "decay_g": dcy_out - dcy_in,          # net mass removed by decay [g] (0 if no decay)
        "total_in_g": total_in_all,
        "total_out_g": total_out_all,
        "pct_imbalance": pct,
        "grouped_residual_g": grouped_residual_g,
    }


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
