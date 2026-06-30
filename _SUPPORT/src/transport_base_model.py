"""
Transport Base Model utilities for MODFLOW 6 GWT (solute) on the Limmat DISV grid.

Builds the M2/M3/M4 "GWT-solute base model": a locally-refined source->receptor
corridor on the inherited steady-state DISV flow model, coupled GWF6(steady,NEWTON)
-GWT6(transient,TVD) in a single simulation, with two source modes:

    - 'well_aux'  : geothermal-doublet recirculation source (injection WEL +Q with
                    SSM AUX CONCENTRATION, paired extraction WEL -Q).  [08t keystone]
    - 'cnc'       : zero-water contaminant source (constant-concentration cells with
                    a pulse on->off or continuous schedule; point/line/area).  [groups]

Locked transport parameters live in LOCKED_PARAMS; do not edit per-call.

NOTE (provenance): prototyped and gate-validated in scratchpad/13_doublet.py.
This module reproduces those numbers via its __main__ regression anchor
(loc2 geothermal doublet -> recirculation fraction ~ 0.566, all gates pass).

A third source mode is the student-project COMBINED scenario:

    - build_spill_scenario : a real geothermal DOUBLET active for FLOW ONLY (clean
                    injection well +Q, extraction/monitoring well -Q) PLUS a SEPARATE
                    zero-water CNC contaminant SPILL (the solute) placed upgradient,
                    with per-group sorption/decay in MST and the source->extraction
                    corridor (plus the injection well) refined.  This is the
                    "will the spill reach the well, and does it exceed the threshold?"
                    setup the Weeks 11-12 student template runs.  [groups]

Functions:
    build_doublet_base   : build + run the validated corridor-refine coupled sim
    build_spill_scenario : doublet-flow + separate CNC contaminant spill (students)
    load_doublet_base    : solve-free loader (re-open cached sim + npz)
    courant_nstp         : size fixed nstp from a pilot seepage-velocity field
    relocate_receptor    : receptor-relocation rule for retarded (sorbing) species

Author: Applied Groundwater Modelling Course (M2 transport base)
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union, Dict, List, Optional, Any, Tuple, Sequence

import numpy as np
import geopandas as gpd
import flopy
from shapely.geometry import Polygon, Point, LineString

import model_io_utils as mio  # build_refined_gwf_model (grid + property interpolation)

# ---------------------------------------------------------------------------
# LOCKED transport parameters (M2/M3/M4 — do not override per call)
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
    "refine_radius": 70.0,  # corridor half-width [m]
    "time_units": "DAYS",
}

# GWF solver policy (NEWTON is a model option, not an IMS keyword)
_GWF_NEWTON = "NEWTON"
_GWF_IMS = dict(complexity="COMPLEX", outer_maximum=200, inner_maximum=100,
                outer_dvclose=1e-4, inner_dvclose=1e-5, linear_acceleration="BICGSTAB")
_GWT_IMS = dict(complexity="MODERATE", linear_acceleration="BICGSTAB",
                outer_dvclose=1e-6, inner_dvclose=1e-7)


@dataclass
class DoubletBase:
    """Loaded, solve-free handle to a pre-built GWT-solute base model."""
    sim: Any
    gwf: Any
    gwt: Any
    modelgrid: Any
    src_cells: List[int]            # source cell(s); for well_aux this is [inj_cell]
    receptor_cell: int              # extraction well / receptor / monitoring cell
    corridor_mask: np.ndarray       # bool[ncpl] refined source->receptor cells
    spdis: Any                      # GWF DATA-SPDIS recarray; seepage V = |q|/n_e
    breakthrough: Tuple[np.ndarray, np.ndarray]   # (times[d], C/c_src at receptor)
    recirc_fraction: float          # plateau C_inf / c_src (well_aux); peak ratio for pulse
    src_xy: Tuple[float, float]
    receptor_xy: Tuple[float, float]
    locked: Dict[str, Any] = field(default_factory=lambda: dict(LOCKED_PARAMS))
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def seepage_velocity(self) -> np.ndarray:
        q = self.spdis
        return np.sqrt(q["qx"] ** 2 + q["qy"] ** 2) / self.locked["porosity"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _cellsize(mg, ncpl) -> np.ndarray:
    return np.array([np.sqrt(Polygon(mg.get_cell_vertices(i)).area) for i in range(ncpl)])


def _run_failure_tail(ws: Union[str, Path], buf, n: int = 40) -> str:
    """Build a useful failure message from the MF6 listing files.

    sim.run_simulation's returned buffer (`buf`) frequently comes back empty on a
    convergence/parameter error, which hid the real MF6 message behind an empty
    tail.  Read the tail of mfsim.lst and the gwf/gwt listings so the actual error
    (e.g. "DECAY_SORBED not provided ...") is surfaced.
    """
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
    """Refine the corridor, retrying over a small set of refine radii.

    cs=10 local refinement SIGILL-crashes on a fraction of source locations
    (macOS arm64 / mf6 6.7.0) and boundary-clipped circles can trip a Triangle
    precision abort.  Both manifest as an exception out of build_refined_gwf_model.
    Walking the radius slightly (70 -> 62 -> 78 -> 56 -> 84 m) reliably dodges the
    crash for the validated student doublets (the corridor stays well-resolved at
    any of these radii: Pe_L <= 2 throughout).

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
        except Exception as e:  # SIGILL / Triangle abort surface here
            last_exc = e
            continue
    raise RuntimeError(
        f"corridor refinement failed at all radii {tuple(refine_radii)}; "
        f"last error: {last_exc!r}")


def courant_nstp(v_cells: np.ndarray, size_cells: np.ndarray, mask: np.ndarray,
                 total_time: float, cr_target: float = 0.9, nstp_cap: int = 1000,
                 sliver_floor_frac: float = 0.4) -> Tuple[int, float, float, Dict[str, float]]:
    """Size fixed time steps from a PER-CELL Courant number Cr_i = v_i*dt/Δs_i.

    Returns (nstp, dt, Cr_actual, diag).  The binding cell is the one with the
    largest v_i/Δs_i among corridor cells whose size is >= sliver_floor_frac *
    refined_cell_size (sub-resolution Voronoi slivers carry negligible pore volume
    and are excluded so they do not force an impractically tiny Δt).  ATS is NOT
    used (convergence-driven, not Courant-driven).
    """
    floor = sliver_floor_frac * LOCKED_PARAMS["refined_cell_size"]
    sel = mask & (size_cells >= floor)
    ratio = v_cells[sel] / size_cells[sel]          # 1/day, per-cell Courant rate
    critical = float(ratio.max())
    dt_need = cr_target / critical
    nstp = min(int(np.ceil(total_time / dt_need)), nstp_cap)
    dt = total_time / nstp
    j = np.where(sel)[0][int(np.argmax(ratio))]
    diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                ds_true_min=float(size_cells[mask].min()), floor=floor)
    return nstp, dt, critical * dt, diag


def relocate_receptor(src_xy, receptor_xy, v_seepage: float, retardation: float,
                      target_time: float, reach_frac: float = 0.7) -> Tuple[Tuple[float, float], bool, float]:
    """Receptor-relocation rule for retarded species.

    The retarded advective travel time to distance x is t_R = R*x/v.  If the
    original receptor cannot be reached within reach_frac*target_time, move the
    receptor inward along the source->receptor line to x_max = v*reach_frac*target_time/R.

    Returns (new_receptor_xy, relocated?, x_used).
    """
    a, b = np.array(src_xy, float), np.array(receptor_xy, float)
    L = float(np.hypot(*(b - a)))
    u = (b - a) / L
    x_max = v_seepage * reach_frac * target_time / max(retardation, 1.0)
    if L <= x_max:
        return tuple(b), False, L
    new = a + u * x_max
    return (float(new[0]), float(new[1])), True, float(x_max)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def build_doublet_base(
    coarse_gwf,
    boundary_gdf: gpd.GeoDataFrame,
    river_gdf: gpd.GeoDataFrame,
    src_xy: Tuple[float, float],
    receptor_xy: Tuple[float, float],
    case_ws: Union[str, Path],
    *,
    source_mode: str = "well_aux",          # 'well_aux' | 'cnc'
    Q: float = 400.0,                        # injection/extraction rate [m3/d] (well_aux)
    c_src: float = 1.0,                      # source concentration
    release: Optional[Dict[str, Any]] = None,  # {'type':'pulse'|'continuous','duration_days':..}
    geometry: str = "point",                # 'point' | 'line' | 'area' (cnc)
    geometry_size: float = 20.0,            # line half-length / area radius [m] (cnc)
    reactions: Optional[Dict[str, Any]] = None,  # {'Kd':mL/g,'rho_b':kg/m3,'lambda':1/d}
    total_time: float = 365.0,
    cr_target: float = 0.9,
    nstp_cap: int = 1000,
    heads_array: Optional[np.ndarray] = None,
) -> DoubletBase:
    """Build + run the validated corridor-refine coupled GWF(steady)-GWT(transient) base.

    Uses build_refined_gwf_model ONLY for grid + property interpolation; all flow/transport
    packages are rebuilt fresh from the returned gwf object so the WEL-AUX source works
    inside one coupled simulation.
    """
    case_ws = Path(case_ws); case_ws.mkdir(parents=True, exist_ok=True)
    exe = coarse_gwf.simulation.exe_name
    if heads_array is None:
        heads_array = coarse_gwf.output.head().get_data().flatten()

    # ---- 1. corridor refinement (grid + interpolated props) ----
    corr_pts, u, L = _corridor_points(src_xy, receptor_xy)
    refgrid_ws = case_ws / "refgrid"
    res = mio.build_refined_gwf_model(
        coarse_gwf, boundary_gdf=boundary_gdf, river_gdf=river_gdf,
        refine_points=corr_pts, head_array=heads_array, workspace=str(refgrid_ws),
        refine_radius=LOCKED_PARAMS["refine_radius"],
        base_cell_size=LOCKED_PARAMS["base_cell_size"],
        refined_cell_size=LOCKED_PARAMS["refined_cell_size"], sim_name="rg")
    rgwf = res["gwf"]; mg = res["modelgrid"]; gp = res["gridprops"]; ncpl = res["ncpl"]
    xc = np.array(mg.xcellcenters); yc = np.array(mg.ycellcenters)
    csz = _cellsize(mg, ncpl)

    k_ref = rgwf.npf.k.array; top_ref = rgwf.disv.top.array; botm_ref = rgwf.disv.botm.array
    heads_ref = rgwf.output.head().get_data().flatten()
    chd = rgwf.get_package("CHD").stress_period_data.get_data(0)
    riv = rgwf.get_package("RIV").stress_period_data.get_data(0)
    rch = rgwf.get_package("RCHA").recharge.get_data()

    rcell = int(np.argmin((xc - receptor_xy[0]) ** 2 + (yc - receptor_xy[1]) ** 2))
    # source cells per geometry
    if geometry == "point" or source_mode == "well_aux":
        src_cells = [int(np.argmin((xc - src_xy[0]) ** 2 + (yc - src_xy[1]) ** 2))]
    elif geometry == "line":
        t = np.array([-u[1], u[0]])  # perpendicular
        pts = [np.array(src_xy) + s * t for s in np.linspace(-geometry_size, geometry_size, 5)]
        src_cells = sorted({int(np.argmin((xc - p[0]) ** 2 + (yc - p[1]) ** 2)) for p in pts})
    else:  # area
        d = np.hypot(xc - src_xy[0], yc - src_xy[1])
        src_cells = [int(i) for i in np.where(d < geometry_size)[0]]
    line = LineString([tuple(src_xy), tuple(receptor_xy)])
    corridor_mask = np.array([line.distance(Point(xc[i], yc[i])) < LOCKED_PARAMS["refine_radius"]
                              for i in range(ncpl)])

    rel = release or {"type": "continuous", "duration_days": total_time}
    is_pulse = rel.get("type") == "pulse"
    dur = float(rel.get("duration_days", total_time))

    def _make_sim(nstp_per_period):
        ws = str(case_ws / "sim")
        sim = flopy.mf6.MFSimulation(sim_name="m2", exe_name=exe, sim_ws=ws)
        # TDIS: 1 period (continuous) or 2 (pulse: on then off)
        if is_pulse and dur < total_time:
            perioddata = [(dur, max(int(nstp_per_period * dur / total_time), 1), 1.0),
                          (total_time - dur, max(nstp_per_period -
                           max(int(nstp_per_period * dur / total_time), 1), 1), 1.0)]
        else:
            perioddata = [(total_time, nstp_per_period, 1.0)]
        nper = len(perioddata)
        flopy.mf6.ModflowTdis(sim, time_units=LOCKED_PARAMS["time_units"], nper=nper, perioddata=perioddata)
        flopy.mf6.ModflowIms(sim, filename="gwf.ims", **_GWF_IMS)
        gwf = flopy.mf6.ModflowGwf(sim, modelname="gwf", save_flows=True, newtonoptions=_GWF_NEWTON)
        flopy.mf6.ModflowGwfdisv(gwf, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                                 botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
        flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=k_ref, save_flows=True, save_specific_discharge=True)
        flopy.mf6.ModflowGwfic(gwf, strt=np.maximum(heads_ref, botm_ref[0] + 0.01))
        flopy.mf6.ModflowGwfsto(gwf, steady_state={i: True for i in range(nper)})
        flopy.mf6.ModflowGwfrcha(gwf, recharge=rch)
        flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["head"])) for r in chd])
        flopy.mf6.ModflowGwfriv(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["stage"]),
                                float(r["cond"]), float(r["rbot"])) for r in riv])
        # ---- source ----
        if source_mode == "well_aux":
            inj = src_cells[0]
            flopy.mf6.ModflowGwfwel(gwf, pname="injw", auxiliary=["CONCENTRATION"],
                                    stress_period_data={0: [[(0, inj), Q, c_src]]})
            flopy.mf6.ModflowGwfwel(gwf, pname="absw",
                                    stress_period_data={0: [[(0, rcell), -abs(Q)]]})
        # cnc source adds NO water; wells (if any) are inherited only
        flopy.mf6.ModflowGwfoc(gwf, head_filerecord="gwf.hds", budget_filerecord="gwf.cbc",
                               saverecord=[("HEAD", "LAST"), ("BUDGET", "LAST")])
        # ---- GWT ----
        gwt = flopy.mf6.ModflowGwt(sim, modelname="gwt", save_flows=True)
        flopy.mf6.ModflowGwtdisv(gwt, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                                 botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
        flopy.mf6.ModflowGwtic(gwt, strt=0.0)
        mst_kw = dict(porosity=LOCKED_PARAMS["porosity"])
        if reactions:
            Kd = reactions.get("Kd", 0.0); lam = reactions.get("lambda", 0.0)
            has_sorption = bool(Kd and Kd > 0)
            has_decay = bool(lam and lam > 0)
            if has_sorption:
                mst_kw.update(sorption="linear", distcoef=Kd * 1e-3,  # mL/g -> m3/kg
                              bulk_density=reactions.get("rho_b", 1800.0))
            if has_decay:
                mst_kw.update(first_order_decay=True, decay=lam)
                # MF6 6.x requires DECAY_SORBED whenever first-order decay AND
                # sorption are both active (else: "DECAY_SORBED not provided in
                # GRIDDATA block but decay and sorption are active"). Use the
                # standard equal-first-order-rate assumption: the sorbed phase
                # decays at the same rate as the dissolved phase. Decay-only
                # (no sorption) does NOT need decay_sorbed, so it is gated here.
                if has_sorption:
                    mst_kw.update(decay_sorbed=lam)
        flopy.mf6.ModflowGwtmst(gwt, **mst_kw)
        flopy.mf6.ModflowGwtadv(gwt, scheme=LOCKED_PARAMS["scheme"])
        flopy.mf6.ModflowGwtdsp(gwt, alh=LOCKED_PARAMS["alh"], ath1=LOCKED_PARAMS["ath1"],
                                diffc=LOCKED_PARAMS["diffc"], xt3d_off=LOCKED_PARAMS["xt3d_off"])
        if source_mode == "well_aux":
            flopy.mf6.ModflowGwtssm(gwt, sources=[["injw", "AUX", "CONCENTRATION"]])
        else:
            # SSM still required because GWF has CHD/RIV/RCHA boundary packages
            # (default c=0 inflow); the CNC package supplies the actual source.
            flopy.mf6.ModflowGwtssm(gwt)
            # cnc zero-water source (pulse -> released in period 2; continuous -> on all periods)
            spd = {0: [[(0, c), c_src] for c in src_cells]}
            if is_pulse and dur < total_time:
                spd[1] = []  # remove CNC -> plume free to migrate/decay
            elif nper > 1:
                for p in range(1, nper):
                    spd[p] = [[(0, c), c_src] for c in src_cells]
            flopy.mf6.ModflowGwtcnc(gwt, stress_period_data=spd)
        flopy.mf6.ModflowGwtoc(gwt, concentration_filerecord="gwt.ucn",
                               saverecord=[("CONCENTRATION", "ALL")])
        flopy.mf6.ModflowIms(sim, filename="gwt.ims", **_GWT_IMS)
        sim.register_ims_package(sim.get_package("gwt.ims"), ["gwt"])
        flopy.mf6.ModflowGwfgwt(sim, exgtype="GWF6-GWT6", exgmnamea="gwf", exgmnameb="gwt",
                                filename="m2.gwfgwt")
        sim.write_simulation(silent=True)
        ok, buf = sim.run_simulation(silent=True)
        return sim, gwf, gwt, ok, buf

    # ---- pilot to read velocity field, size Courant, then production ----
    sim, gwf, gwt, ok, buf = _make_sim(20)
    if not ok:
        raise RuntimeError("pilot run failed; listing tail:\n"
                           + _run_failure_tail(case_ws / "sim", buf))
    spd = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    vmag = np.sqrt(spd["qx"] ** 2 + spd["qy"] ** 2) / LOCKED_PARAMS["porosity"]
    corr_no_wells = corridor_mask.copy()
    for c in src_cells + [rcell]:
        corr_no_wells[c] = False
    nstp, dt, cr_act, cdiag = courant_nstp(vmag, csz, corr_no_wells, total_time, cr_target, nstp_cap)
    v_peak = cdiag["v_bind"]; ds_min = cdiag["ds_bind"]

    sim, gwf, gwt, ok, buf = _make_sim(nstp)
    if not ok:
        raise RuntimeError("production run failed; listing tail:\n"
                           + _run_failure_tail(case_ws / "sim", buf))

    cobj = gwt.output.concentration(); times = np.array(cobj.get_times())
    bt = np.maximum(np.array([cobj.get_data(totim=t)[0, 0, rcell] for t in times]), 0)
    if source_mode == "well_aux":
        recirc = float(np.median(bt[-8:]) / c_src)
    else:
        recirc = float(bt.max() / c_src)  # pulse: peak arrival ratio

    spd_final = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    meta = dict(ncpl=ncpl, nstp=nstp, dt=dt, Cr=cr_act, v_peak=v_peak, ds_min=ds_min,
                PeL_min=float(csz[corridor_mask].min() / LOCKED_PARAMS["alh"]),
                PeL_max=float(csz[corridor_mask].max() / LOCKED_PARAMS["alh"]),
                source_mode=source_mode, geometry=geometry, release=rel,
                reactions=reactions, total_time=total_time,
                ds_true_min=cdiag["ds_true_min"], courant_floor=cdiag["floor"])
    np.savez(str(case_ws / "base_cache.npz"), times=times, bt=bt, src_cells=np.array(src_cells),
             receptor_cell=rcell, corridor_mask=corridor_mask, recirc=recirc,
             src_xy=np.array(src_xy), receptor_xy=np.array(receptor_xy), meta=meta, allow_pickle=True)

    return DoubletBase(sim=sim, gwf=gwf, gwt=gwt, modelgrid=mg, src_cells=src_cells,
                       receptor_cell=rcell, corridor_mask=corridor_mask, spdis=spd_final,
                       breakthrough=(times, bt), recirc_fraction=recirc,
                       src_xy=tuple(src_xy), receptor_xy=tuple(receptor_xy), meta=meta)


def build_spill_scenario(
    coarse_gwf,
    boundary_gdf: gpd.GeoDataFrame,
    river_gdf: gpd.GeoDataFrame,
    inj_xy: Tuple[float, float],
    ext_xy: Tuple[float, float],
    spill_xy: Tuple[float, float],
    case_ws: Union[str, Path],
    *,
    Q: float = 1370.0,                       # doublet rate [m3/d]; inj +Q / ext -Q
    c_src: float = 1.0,                      # spill source concentration [mg/L]
    release: Optional[Dict[str, Any]] = None,  # {'type':'pulse'|'continuous','duration_days':..}
    geometry: str = "point",                # 'point' | 'line' | 'area'
    geometry_size: float = 30.0,            # line half-length / area radius [m]
    reactions: Optional[Dict[str, Any]] = None,  # {'Kd':mL/g,'rho_b':kg/m3,'lambda':1/d}
    total_time: float = 365.0,
    cr_target: float = 0.9,
    nstp_cap: int = 4000,
    refine_radii: Sequence[float] = (70.0, 62.0, 78.0, 56.0, 84.0),
    heads_array: Optional[np.ndarray] = None,
) -> DoubletBase:
    """Build + run the COMBINED student scenario: doublet flow + a separate spill solute.

    The geothermal doublet is active for FLOW ONLY: a clean injection well (+Q, no
    concentration) and an extraction / monitoring well (-Q) shape the forced-gradient
    flow field.  The contaminant is a SEPARATE zero-water CNC source placed at
    ``spill_xy`` (point/line/area, pulse/continuous) carrying per-group sorption/decay
    via MST.  The breakthrough is read at the extraction (monitoring) well, so the
    scenario answers "does the spill reach the well, and does it exceed the threshold?".

    The source->extraction corridor PLUS the injection well are locally refined (cs=10)
    with a SIGILL retry over ``refine_radii``.  nstp is sized from a pilot velocity
    field at ``cr_target``; ``nstp_cap`` defaults high (4000) so high-Q + retarded
    cases (e.g. Atrazine at Q=5760, which needs ~3200 steps) reach Cr<=1 uncapped.

    Returns a DoubletBase with src_cells = spill cell(s), receptor_cell = extraction
    well, src_xy = spill_xy, receptor_xy = ext_xy, recirc_fraction = peak C / c_src.
    Caches to ``case_ws`` in the same format as build_doublet_base (load via
    load_doublet_base).
    """
    case_ws = Path(case_ws); case_ws.mkdir(parents=True, exist_ok=True)
    exe = coarse_gwf.simulation.exe_name
    if heads_array is None:
        heads_array = coarse_gwf.output.head().get_data().flatten()

    rel = release or {"type": "continuous", "duration_days": total_time}
    is_pulse = rel.get("type") == "pulse"
    dur = float(rel.get("duration_days", total_time))
    is_pulse = is_pulse and dur < total_time

    # ---- 1. corridor refinement (spill->extraction corridor + injection well) ----
    corr_pts, u, L = _corridor_points(spill_xy, ext_xy)
    refine_points = corr_pts + [tuple(inj_xy)]
    res, refine_radius_used = _refine_with_retry(
        coarse_gwf, boundary_gdf, river_gdf, refine_points, heads_array,
        case_ws / "refgrid", refine_radii=refine_radii,
        base_cell_size=LOCKED_PARAMS["base_cell_size"],
        refined_cell_size=LOCKED_PARAMS["refined_cell_size"], sim_name="rg")
    rgwf = res["gwf"]; mg = res["modelgrid"]; gp = res["gridprops"]; ncpl = res["ncpl"]
    xc = np.array(mg.xcellcenters); yc = np.array(mg.ycellcenters)
    csz = _cellsize(mg, ncpl)

    k_ref = rgwf.npf.k.array; top_ref = rgwf.disv.top.array; botm_ref = rgwf.disv.botm.array
    heads_ref = rgwf.output.head().get_data().flatten()
    chd = rgwf.get_package("CHD").stress_period_data.get_data(0)
    riv = rgwf.get_package("RIV").stress_period_data.get_data(0)
    rch = rgwf.get_package("RCHA").recharge.get_data()

    injc = int(np.argmin((xc - inj_xy[0]) ** 2 + (yc - inj_xy[1]) ** 2))
    extc = int(np.argmin((xc - ext_xy[0]) ** 2 + (yc - ext_xy[1]) ** 2))
    # spill source cells per geometry
    if geometry == "line":
        t = np.array([-u[1], u[0]])  # perpendicular to the corridor direction
        pts = [np.array(spill_xy) + s * t for s in np.linspace(-geometry_size, geometry_size, 5)]
        src_cells = sorted({int(np.argmin((xc - p[0]) ** 2 + (yc - p[1]) ** 2)) for p in pts})
    elif geometry == "area":
        d = np.hypot(xc - spill_xy[0], yc - spill_xy[1])
        src_cells = [int(i) for i in np.where(d < geometry_size)[0]] or \
                    [int(np.argmin(d))]
    else:  # point
        src_cells = [int(np.argmin((xc - spill_xy[0]) ** 2 + (yc - spill_xy[1]) ** 2))]
    line = LineString([tuple(spill_xy), tuple(ext_xy)])
    corridor_mask = np.array([line.distance(Point(xc[i], yc[i])) < refine_radius_used
                              for i in range(ncpl)])

    def _make_sim(nstp_per_period):
        ws = str(case_ws / "sim")
        sim = flopy.mf6.MFSimulation(sim_name="spill", exe_name=exe, sim_ws=ws)
        if is_pulse:
            n_on = max(int(nstp_per_period * dur / total_time), 1)
            perioddata = [(dur, n_on, 1.0),
                          (total_time - dur, max(nstp_per_period - n_on, 1), 1.0)]
        else:
            perioddata = [(total_time, nstp_per_period, 1.0)]
        nper = len(perioddata)
        flopy.mf6.ModflowTdis(sim, time_units=LOCKED_PARAMS["time_units"], nper=nper, perioddata=perioddata)
        flopy.mf6.ModflowIms(sim, filename="gwf.ims", **_GWF_IMS)
        gwf = flopy.mf6.ModflowGwf(sim, modelname="gwf", save_flows=True, newtonoptions=_GWF_NEWTON)
        flopy.mf6.ModflowGwfdisv(gwf, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                                 botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
        flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=k_ref, save_flows=True, save_specific_discharge=True)
        flopy.mf6.ModflowGwfic(gwf, strt=np.maximum(heads_ref, botm_ref[0] + 0.01))
        flopy.mf6.ModflowGwfsto(gwf, steady_state={i: True for i in range(nper)})
        flopy.mf6.ModflowGwfrcha(gwf, recharge=rch)
        flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["head"])) for r in chd])
        flopy.mf6.ModflowGwfriv(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["stage"]),
                                float(r["cond"]), float(r["rbot"])) for r in riv])
        # ---- doublet wells: FLOW ONLY (clean injection, no concentration) ----
        flopy.mf6.ModflowGwfwel(gwf, pname="injw", stress_period_data={0: [[(0, injc), abs(Q)]]})
        flopy.mf6.ModflowGwfwel(gwf, pname="absw", stress_period_data={0: [[(0, extc), -abs(Q)]]})
        flopy.mf6.ModflowGwfoc(gwf, head_filerecord="gwf.hds", budget_filerecord="gwf.cbc",
                               saverecord=[("HEAD", "LAST"), ("BUDGET", "LAST")])
        # ---- GWT (solute = the spill) ----
        gwt = flopy.mf6.ModflowGwt(sim, modelname="gwt", save_flows=True)
        flopy.mf6.ModflowGwtdisv(gwt, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                                 botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
        flopy.mf6.ModflowGwtic(gwt, strt=0.0)
        mst_kw = dict(porosity=LOCKED_PARAMS["porosity"])
        if reactions:
            Kd = reactions.get("Kd", 0.0); lam = reactions.get("lambda", 0.0)
            has_sorption = bool(Kd and Kd > 0)
            has_decay = bool(lam and lam > 0)
            if has_sorption:
                mst_kw.update(sorption="linear", distcoef=Kd * 1e-3,  # mL/g -> m3/kg
                              bulk_density=reactions.get("rho_b", 1800.0))
            if has_decay:
                mst_kw.update(first_order_decay=True, decay=lam)
                if has_sorption:  # MF6 requires DECAY_SORBED when both are active
                    mst_kw.update(decay_sorbed=lam)
        flopy.mf6.ModflowGwtmst(gwt, **mst_kw)
        flopy.mf6.ModflowGwtadv(gwt, scheme=LOCKED_PARAMS["scheme"])
        flopy.mf6.ModflowGwtdsp(gwt, alh=LOCKED_PARAMS["alh"], ath1=LOCKED_PARAMS["ath1"],
                                diffc=LOCKED_PARAMS["diffc"], xt3d_off=LOCKED_PARAMS["xt3d_off"])
        # SSM still required (CHD/RIV/RCHA default c=0 inflow); CNC supplies the spill
        flopy.mf6.ModflowGwtssm(gwt)
        spd = {0: [[(0, c), c_src] for c in src_cells]}
        if is_pulse:
            spd[1] = []  # spill ends -> plume free to migrate / decay / sorb
        flopy.mf6.ModflowGwtcnc(gwt, stress_period_data=spd)
        flopy.mf6.ModflowGwtoc(gwt, concentration_filerecord="gwt.ucn",
                               saverecord=[("CONCENTRATION", "ALL")])
        flopy.mf6.ModflowIms(sim, filename="gwt.ims", **_GWT_IMS)
        sim.register_ims_package(sim.get_package("gwt.ims"), ["gwt"])
        flopy.mf6.ModflowGwfgwt(sim, exgtype="GWF6-GWT6", exgmnamea="gwf", exgmnameb="gwt",
                                filename="spill.gwfgwt")
        sim.write_simulation(silent=True)
        ok, buf = sim.run_simulation(silent=True)
        return sim, gwf, gwt, ok, buf

    # ---- pilot to read velocity, size Courant, then production ----
    sim, gwf, gwt, ok, buf = _make_sim(20)
    if not ok:
        raise RuntimeError("pilot run failed; listing tail:\n"
                           + _run_failure_tail(case_ws / "sim", buf))
    spd = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    vmag = np.sqrt(spd["qx"] ** 2 + spd["qy"] ** 2) / LOCKED_PARAMS["porosity"]
    corr_no_wells = corridor_mask.copy()
    for c in src_cells + [injc, extc]:
        corr_no_wells[c] = False
    nstp, dt, cr_act, cdiag = courant_nstp(vmag, csz, corr_no_wells, total_time, cr_target, nstp_cap)
    v_peak = cdiag["v_bind"]; ds_min = cdiag["ds_bind"]

    sim, gwf, gwt, ok, buf = _make_sim(nstp)
    if not ok:
        raise RuntimeError("production run failed; listing tail:\n"
                           + _run_failure_tail(case_ws / "sim", buf))

    cobj = gwt.output.concentration(); times = np.array(cobj.get_times())
    bt = np.maximum(np.array([cobj.get_data(totim=t)[0, 0, extc] for t in times]), 0)
    peak = float(bt.max())
    t_arrival = float(times[int(np.argmax(bt))]) if bt.size else float("nan")
    recirc = peak / c_src if c_src else float("nan")

    spd_final = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    meta = dict(ncpl=ncpl, nstp=nstp, dt=dt, Cr=cr_act, v_peak=v_peak, ds_min=ds_min,
                PeL_min=float(csz[corridor_mask].min() / LOCKED_PARAMS["alh"]),
                PeL_max=float(csz[corridor_mask].max() / LOCKED_PARAMS["alh"]),
                source_mode="spill", geometry=geometry, release=rel,
                reactions=reactions, total_time=total_time, Q=Q, c_src=c_src,
                peak=peak, t_arrival=t_arrival, refine_radius_used=refine_radius_used,
                ds_true_min=cdiag["ds_true_min"], courant_floor=cdiag["floor"],
                cr_capped=bool(cr_act > 1.001))
    np.savez(str(case_ws / "base_cache.npz"), times=times, bt=bt, src_cells=np.array(src_cells),
             receptor_cell=extc, corridor_mask=corridor_mask, recirc=recirc,
             src_xy=np.array(spill_xy), receptor_xy=np.array(ext_xy), meta=meta, allow_pickle=True)

    return DoubletBase(sim=sim, gwf=gwf, gwt=gwt, modelgrid=mg, src_cells=src_cells,
                       receptor_cell=extc, corridor_mask=corridor_mask, spdis=spd_final,
                       breakthrough=(times, bt), recirc_fraction=recirc,
                       src_xy=tuple(spill_xy), receptor_xy=tuple(ext_xy), meta=meta)


def load_doublet_base(case_ws: Union[str, Path]) -> DoubletBase:
    """Solve-free loader: re-open the cached coupled sim + npz cache."""
    case_ws = Path(case_ws)
    sim = flopy.mf6.MFSimulation.load(sim_ws=str(case_ws / "sim"), verbosity_level=0)
    gwf = sim.get_model("gwf"); gwt = sim.get_model("gwt")
    z = np.load(str(case_ws / "base_cache.npz"), allow_pickle=True)
    spd = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    return DoubletBase(sim=sim, gwf=gwf, gwt=gwt, modelgrid=gwf.modelgrid,
                       src_cells=[int(c) for c in z["src_cells"]],
                       receptor_cell=int(z["receptor_cell"]),
                       corridor_mask=z["corridor_mask"], spdis=spd,
                       breakthrough=(z["times"], z["bt"]), recirc_fraction=float(z["recirc"]),
                       src_xy=tuple(z["src_xy"]), receptor_xy=tuple(z["receptor_xy"]),
                       meta=dict(z["meta"].item()))


# ---------------------------------------------------------------------------
# regression anchor
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    DATA = os.path.expanduser("~/applied_groundwater_modelling_data/limmat")
    MF6 = os.path.expanduser("~/.local/share/flopy/bin/mf6")
    SCR = os.path.dirname(os.path.abspath(__file__))
    boundary = gpd.read_file(os.path.join(DATA, "gis", "limmat_model_boundary.gpkg"))
    rivers = gpd.read_file(os.path.join(DATA, "gis", "AV_Gewasser_-OGD.gpkg"))
    rivers = rivers[rivers["GEWAESSERNAME"].isin(["Limmat", "Sihl"])
                    & rivers.intersects(boundary.geometry.iloc[0])]
    # Route through the bootstrap so the corridor refine + spill build on the
    # CALIBRATED flow field (05f), not the uncalibrated notebook4_model base.
    flow_ws = mio.ensure_flow_model()
    csim = flopy.mf6.MFSimulation.load(sim_ws=str(flow_ws),
                                       exe_name=MF6, verbosity_level=0)
    cgwf = csim.get_model("limmat_valley")
    inj = (2679712.0, 1249990.0)
    spd = cgwf.output.budget().get_data(text="DATA-SPDIS")[0]
    mg = cgwf.modelgrid; xc = np.array(mg.xcellcenters); yc = np.array(mg.ycellcenters)
    i0 = int(np.argmin((xc - inj[0]) ** 2 + (yc - inj[1]) ** 2))
    u = np.array([spd["qx"][i0], spd["qy"][i0]]); u = u / np.hypot(*u)
    ext = (inj[0] + 160 * u[0], inj[1] + 160 * u[1])
    t0 = time.time()
    db = build_doublet_base(cgwf, boundary, rivers, inj, ext,
                            case_ws=os.path.join(SCR, "m2_regression"),
                            source_mode="well_aux", Q=400.0, c_src=1.0, total_time=365.0)
    dtw = time.time() - t0
    print("REGRESSION ANCHOR (loc2 geothermal doublet)")
    print(f"  recirc_fraction = {db.recirc_fraction:.3f}  (expect ~0.566)")
    print(f"  PeL corridor    = {db.meta['PeL_min']:.2f}..{db.meta['PeL_max']:.2f}  (<=2)")
    print(f"  Cr peak         = {db.meta['Cr']:.2f}  nstp={db.meta['nstp']}  (<=1) "
          f"[binding Δs={db.meta['ds_min']:.1f} m; true-min cell {db.meta['ds_true_min']:.1f} m floored at {db.meta['courant_floor']:.1f} m]")
    print(f"  wall-clock      = {dtw:.0f}s (Mac proxy)")
    # recirc has ~+/-0.05 Voronoi-regeneration sensitivity; partial capture is the invariant
    ok = (0.45 < db.recirc_fraction < 0.65) and db.meta["PeL_max"] <= 2 and db.meta["Cr"] <= 1
    print("  REGRESSION:", "PASS" if ok else "FAIL")

    # --- spill-scenario smoke test (group 2 Benzene: REACHES-above-threshold) ---
    # Doublet b010185, Q=1370; 10-day pulse, decay 0.005/d; spill +50E/-102N of ext well.
    print("\nSPILL SMOKE TEST (group 2 Benzene doublet b010185)")
    g2_inj = (2681487.9, 1249310.9)
    g2_ext = (2681515.9, 1249254.9)
    g2_spill = (g2_ext[0] + 50.0, g2_ext[1] - 102.0)
    t0 = time.time()
    sp = build_spill_scenario(
        cgwf, boundary, rivers, g2_inj, g2_ext, g2_spill,
        case_ws=os.path.join(SCR, "spill_smoke"),
        Q=1370.0, c_src=10.0, geometry="point",
        release={"type": "pulse", "duration_days": 10.0},
        reactions={"Kd": 0.0, "rho_b": 1800.0, "lambda": 0.005},
        total_time=60.0)
    dts = time.time() - t0
    peak = sp.meta["peak"]; thr = 0.005
    print(f"  peak at well    = {peak:.4g} mg/L  (threshold {thr} mg/L -> "
          f"{'ABOVE' if peak >= thr else 'below'})")
    print(f"  PeL corridor    = {sp.meta['PeL_min']:.2f}..{sp.meta['PeL_max']:.2f}  (<=2)")
    print(f"  Cr peak         = {sp.meta['Cr']:.2f}  nstp={sp.meta['nstp']}  "
          f"refine_radius={sp.meta['refine_radius_used']:.0f} m")
    print(f"  wall-clock      = {dts:.0f}s (Mac proxy)")
    ok_sp = (peak >= thr) and sp.meta["PeL_max"] <= 2 and sp.meta["Cr"] <= 1.05
    print("  SPILL SMOKE:", "PASS" if ok_sp else "FAIL")

    sys.exit(0 if (ok and ok_sp) else 1)
