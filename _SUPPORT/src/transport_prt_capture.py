"""
Forward PRT particle tracking: is the SPILL FOOTPRINT captured by the doublet?

Self-contained teaching demo (UNGRADED) for the transport track (charter milestone
M5).  Builds a STEADY GWF flow model on the SAME corridor-refined DISV grid, with
the SAME geothermal doublet / CHD / RIV / RCHA as ``transport_srcpulse_demo``, and
then runs a MODFLOW 6 **PRT** (particle-tracking) model on top of it via the Flow
Model Interface (FMI).

    * The doublet (spare concession ``b010191``) is FLOW ONLY: a clean injection
      well (+Q) and an extraction well (-Q).  The EXTRACTION well is the
      COMPLIANCE well.
    * A disc of particles is released FORWARD from the SPILL FOOTPRINT, centred on
      the same spill location the ADE demo uses (~90 m upgradient of the extraction
      well, upgradient computed from the local regional flow direction).  A real
      spill has lateral extent, and a lateral question cannot be answered by a
      point release.
    * Each particle's fate is classified from the PRT termination record.

WHAT THIS ANSWERS -- AND WHAT IT DOES NOT
-----------------------------------------
PRT answers a **geometry / wellfield-protection** question:

    *Are advective particles released in the spill footprint CAPTURED by the
    extraction well, how long do they take to get there, and how wide a swath of
    the aquifer feeds the well?*

PRT says **NOTHING** about concentration, dilution, dispersion, sorption, decay or
any regulatory threshold.  "Is the concentration above the limit, and when" is the
ADE question, and it is answered -- separately -- by ``transport_srcpulse_demo``
(peak 4.95 mg/L at day 41).  The two questions are deliberately kept apart; do not
read a capture fraction as a concentration, and do not read an advective travel
time as a breakthrough time.  (They are, however, consistent: the advective median
travel time here is ~26 d, and the ADE's day-41 concentration peak is ~26 d after
the CENTRE OF MASS of the 30-day finite pulse, which is released at t = 15 d.
15 + 26 = 41.  See the module ``__main__`` smoke output.)

HOW A PARTICLE IS CLASSIFIED (verified, not guessed)
----------------------------------------------------
Classification is by **terminating CELL**, taken from the PRT track CSV's
termination record (``ireason == 3``), NOT by the ``istatus`` code:

    CAPTURED = the particle's termination record is in the EXTRACTION-well cell.
    ESCAPED  = anything else (terminated elsewhere, or still moving when the
               tracking window closed).

This is robust because the extraction well is a verified **STRONG sink**: at
Q = 1370 m^3/d the GWF FLOW-JA-FACE balance for the well cell is
inflow ~= 1370 m^3/d, outflow = 0.00 m^3/d -- every drop of water that enters the
cell leaves through the well, so every particle that enters the cell must
terminate there.  ``meta["ext_inflow_m3d"] / meta["ext_outflow_m3d"] /
meta["ext_is_strong_sink"]`` record this check on every build.

``stop_at_weak_sink`` (MF6's ``ISTOPWEAKSINK``) is therefore left **OFF** by
default:

    * It is not needed for capture.  The extraction well is a STRONG sink, and MF6
      terminates particles in a strong sink regardless of this option.  Verified
      empirically: an identical release run with and without the option gives the
      same 200/200 capture and identical travel times.
    * Turning it ON would additionally terminate particles in *partially* draining
      RIV cells that they merely pass through, which corrupts escapee pathlines
      (and could, in principle, terminate a particle that would still have reached
      the well) without improving the capture answer.

It is nonetheless exposed as an argument (and folded into the cache identity) so
the notebook can show the contrast.

Observed MF6 6.7.0 ``istatus`` codes in this scenario (recorded in
``meta["istatus_counts"]``): **5** = terminated in a cell with no exit face (the
strong-sink capture at the well); **10** = terminated because the tracking window
(``stoptime``) closed while the particle was still moving.  A control run with
``ISTOPZONE`` set on the well cell terminates the very same particles in the very
same cell but reports ``istatus = 6`` -- which is exactly why this module keys on
the CELL and not on the code.

OWNERSHIP: this module imports ``model_io_utils`` (shared grid utility) and
``transport_srcpulse_demo`` (ours: LOCKED_PARAMS, the doublet/spill geometry, the
corridor-refinement SIGILL retry guard, and the failure-tail helper).  It does NOT
import ``transport_base_model``.

Author: Applied Groundwater Modelling Course (transport track, M5 PRT demo)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple, Union

import numpy as np
import flopy

# Reused from the ADE demo -- the SAME locked parameters, the SAME doublet, the
# SAME spill-location rule, the SAME corridor refinement (with its SIGILL /
# Triangle-precision radius-walk retry guard) and the SAME failure-tail helper.
# Do NOT re-implement any of these here: the PRT release point must coincide with
# the ADE source, and the grid must be the same grid.
from transport_srcpulse_demo import (  # noqa: F401  (re-exported on purpose)
    LOCKED_PARAMS,
    INJ_XY,
    ABS_XY,
    DOUBLET_Q,
    SPILL_UPGRADIENT_M,
    _MF6_FALLBACK,
    _cellsize,
    _corridor_points,
    _load_calibrated_flow,
    _refine_with_retry,
    _run_failure_tail,
)

# Solver policy for the steady flow model (same as the ADE demo's GWF).
_GWF_NEWTON = "NEWTON"
_GWF_IMS = dict(complexity="COMPLEX", outer_maximum=200, inner_maximum=100,
                outer_dvclose=1e-4, inner_dvclose=1e-5, linear_acceleration="BICGSTAB")

# PRT track-CSV `ireason` codes (MF6 6.7.0): 0 = release, 1 = cell exit,
# 2 = time-step end, 3 = TERMINATION, 4 = weak sink, 5 = user-specified time.
_IREASON_RELEASE = 0
_IREASON_TERMINATE = 3

# A release disc of this radius is wide enough to STRADDLE the capture-zone
# boundary (measured: capture fraction 0.72 at 120 m vs 1.00 at the default 10 m).
# The default 10 m release radius is a realistic spill footprint and lies ENTIRELY
# inside the capture zone -- which is the honest answer for this spill, but it
# teaches nothing about where the capture zone ENDS.  Use this radius for the
# capture-zone rung.
WIDE_RELEASE_RADIUS_M: float = 120.0


# ---------------------------------------------------------------------------
# result container
# ---------------------------------------------------------------------------
@dataclass
class PrtCapture:
    """Diagnostics from the forward PRT spill-footprint -> capture demo."""
    capture_fraction: float                 # n_captured / n_released  [0..1]
    n_particles: int                        # particles REQUESTED
    n_released: int                         # particles actually released
    n_captured: int                         # terminated in the extraction-well cell
    n_escaped: int                          # everything else
    tt_median_d: float                      # travel-time stats, CAPTURED only [d]
    tt_p10_d: float
    tt_p90_d: float
    tt_min_d: float
    tt_max_d: float
    lateral_swath_m: float                  # max |perp. offset| over CAPTURED pathlines [m]
    capture_halfwidth_m: float              # max |perp. offset| of CAPTURED release points [m]
    release_points: np.ndarray              # (n_released, 2) x, y [m]
    release_cells: np.ndarray               # (n_released,) int, 0-based DISV cell
    endpoints: np.ndarray                   # (n_released, 3) x, y, t_end [m, m, d]
    end_cells: np.ndarray                   # (n_released,) int, 0-based terminating cell
    end_status: np.ndarray                  # (n_released,) int, MF6 PRT istatus
    captured: np.ndarray                    # (n_released,) bool
    travel_times: np.ndarray                # (n_released,) float [d] (all particles)
    pathlines: np.ndarray                   # (M, 4): particle index (0-based), t, x, y
    spill_xy: Tuple[float, float]           # release-disc centre (== the ADE source)
    axis_u: Tuple[float, float]             # unit vector spill -> extraction well
    ext_cell: int                           # extraction (compliance) well cell, 0-based
    inj_cell: int                           # injection well cell, 0-based
    release_radius_m: float
    track_days: float
    stop_at_weak_sink: bool
    porosity: float
    meta: Dict[str, Any] = field(default_factory=dict)
    locked: Dict[str, Any] = field(default_factory=lambda: dict(LOCKED_PARAMS))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def release_disc(cx: float, cy: float, radius: float, n: int) -> np.ndarray:
    """DETERMINISTIC, evenly-spread disc of ``n`` points of radius ``radius``.

    Vogel / sunflower (golden-angle) layout: ``r_k = R * sqrt(k / (n-1))``,
    ``theta_k = k * golden_angle``.  The ``sqrt`` makes the points equal-AREA
    (not equal-radius) spaced, so the disc is sampled uniformly rather than
    piling points near the centre; the golden angle keeps rings from aligning.

    Purely geometric -- NO random number generator, seeded or otherwise.  The
    result is cached and asserted on in tests, so the layout must be bit-stable
    across runs and machines.  ``k == 0`` gives ``r == 0``, i.e. point 0 sits
    EXACTLY on the spill centre (on the spill -> well axis).
    """
    if n < 1:
        raise ValueError(f"n must be >= 1 (got {n!r})")
    ga = math.pi * (3.0 - math.sqrt(5.0))          # golden angle ~ 2.39996 rad
    out = np.empty((n, 2), dtype=float)
    for k in range(n):
        r = float(radius) * math.sqrt(k / (n - 1)) if n > 1 else 0.0
        th = k * ga
        out[k, 0] = float(cx) + r * math.cos(th)
        out[k, 1] = float(cy) + r * math.sin(th)
    return out


def _prt_failure_tail(prt_ws: Union[str, Path], buf, n: int = 40) -> str:
    """``_run_failure_tail`` (reused from the ADE demo) + the PRT listing tail.

    ``_run_failure_tail`` only knows about mfsim.lst / gwf.lst / gwt.lst; a PRT
    run's real error message lives in prt.lst, so append it here rather than
    editing the ADE module.
    """
    prt_ws = Path(prt_ws)
    chunks = [_run_failure_tail(prt_ws, buf, n=n)]
    p = prt_ws / "prt.lst"
    if p.exists():
        try:
            lines = p.read_text(errors="replace").splitlines()
            if lines:
                chunks.append(f"--- prt.lst (last {n} lines) ---\n" + "\n".join(lines[-n:]))
        except OSError:
            pass
    return "\n\n".join(chunks)


def _default_case_ws() -> Path:
    from data_utils import get_default_data_folder
    return Path(get_default_data_folder()) / "transport_prt_capture"


def _strong_sink_check(gwf, cell: int) -> Tuple[float, float]:
    """Face inflow / outflow [m^3/d] for ``cell`` from GWF FLOW-JA-FACE.

    A cell whose face OUTflow is ~0 while a well pumps from it is a STRONG sink:
    all the water entering the cell leaves via the well, so a particle entering
    the cell cannot leave it and MUST terminate there.  That is what makes
    "terminated in the extraction-well cell" == "captured by the well" a sound
    classification, independent of any istatus code.
    """
    ws = gwf.simulation.simulation_data.mfpath.get_sim_path()
    grb = flopy.mf6.utils.MfGrdFile(os.path.join(ws, "gwf.disv.grb"))
    ia = grb.ia          # CSR row pointers: ia[n]..ia[n+1] are cell n's connections
    flowja = np.array(gwf.output.budget().get_data(text="FLOW-JA-FACE")[0]).ravel()
    q_in = 0.0
    q_out = 0.0
    for ip in range(ia[cell] + 1, ia[cell + 1]):   # skip the diagonal
        q = float(flowja[ip])
        if q > 0.0:
            q_in += q
        else:
            q_out += q
    return q_in, abs(q_out)


# ---------------------------------------------------------------------------
# build + run
# ---------------------------------------------------------------------------
def build_prt_capture(
    n_particles: int = 200,
    release_radius_m: float = 10.0,
    track_days: float = 730.0,
    *,
    stop_at_weak_sink: bool = False,
    case_ws: Optional[Union[str, Path]] = None,
    refine_radii: Sequence[float] = (70.0, 62.0, 78.0, 56.0, 84.0),
    force: bool = False,
) -> PrtCapture:
    """Build + run the forward PRT spill-footprint -> capture demo.

    Parameters
    ----------
    n_particles : int
        Number of particles REQUESTED in the release disc.  The layout is a
        deterministic golden-angle disc (see :func:`release_disc`).  Release
        points that would land INSIDE a doublet well cell are dropped (you cannot
        spill inside the well, and such a particle would report a travel time of
        0 d), so ``n_released`` can be slightly smaller than ``n_particles``;
        ``meta["n_dropped_wellcell"]`` records how many.
    release_radius_m : float
        Radius of the spill footprint [m].  The default (10 m) is a realistic
        footprint and lies ENTIRELY inside the capture zone (capture fraction
        1.0).  Use ``WIDE_RELEASE_RADIUS_M`` (120 m) to straddle the capture-zone
        boundary and get a fraction strictly between 0 and 1.
    track_days : float
        Length of the forward tracking window [d].  Particles still moving when it
        closes are terminated by MF6 (``istatus = 10``) and classified ESCAPED.
    stop_at_weak_sink : bool
        MF6 PRP ``STOP_AT_WEAK_SINK`` (internally ``ISTOPWEAKSINK``).  Default
        ``False`` -- see the module docstring: the extraction well is a STRONG
        sink, so this option does not affect capture, and enabling it would
        terminate particles in RIV cells they merely pass through.
    case_ws : path, optional
        Workspace for the refined grid + GWF sim + PRT sim + cache.  Defaults to
        ``<data>/transport_prt_capture``.
    force : bool
        Rebuild even if a matching cache exists.

    Returns
    -------
    PrtCapture
    """
    # NaN/inf are TRANSPARENT to every "<" / "<=" guard below (all comparisons are
    # False for NaN), so a non-finite value would sail straight through validation
    # and then land in the model / the cache key.  Reject them explicitly, up front.
    for _name, _val in (("release_radius_m", release_radius_m),
                        ("track_days", track_days)):
        if not math.isfinite(_val):
            raise ValueError(f"{_name} must be finite (got {_val!r})")
    if isinstance(n_particles, float) and not math.isfinite(n_particles):
        raise ValueError(f"n_particles must be finite (got {n_particles!r})")

    n_particles = int(n_particles)
    if n_particles < 4:
        raise ValueError(f"n_particles must be >= 4 (got {n_particles!r}); a disc "
                         "release needs enough points for a fraction to mean anything")
    if release_radius_m <= 0.0:
        raise ValueError(f"release_radius_m must be > 0 (got {release_radius_m!r})")
    if track_days <= 0.0:
        raise ValueError(f"track_days must be > 0 (got {track_days!r})")

    porosity = float(LOCKED_PARAMS["porosity"])

    case_ws = Path(case_ws) if case_ws is not None else _default_case_ws()
    case_ws.mkdir(parents=True, exist_ok=True)

    params = dict(
        n_particles=int(n_particles),
        release_radius_m=float(release_radius_m),
        track_days=float(track_days),
        stop_at_weak_sink=bool(stop_at_weak_sink),
        refine_radii=list(map(float, refine_radii)),
        # A snapshot of LOCKED_PARAMS: an edit to porosity / base_cell_size /
        # refined_cell_size / time_units must bust every existing cache instead of
        # being silently ignored.  json.dumps(..., sort_keys=True) below sorts this
        # nested dict too, so the hash does not depend on declaration order.
        locked=dict(LOCKED_PARAMS),
        # A fingerprint of the model SOURCE -- this module AND the ADE module it
        # imports the doublet / spill geometry / corridor refinement from.
        # LOCKED_PARAMS only covers that one dict: editing DOUBLET_Q,
        # SPILL_UPGRADIENT_M, INJ_XY/ABS_XY, the release layout, the FMI wiring or
        # the fate classification would otherwise leave the hash (and every warm
        # cache, notebook users included) unchanged while the model changed
        # underneath it.  This repo has already shipped that bug once.
        src_sha=_src_sha(),
    )
    cache_hash = hashlib.sha1(
        json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    cache = case_ws / f"prtcapture_cache_{cache_hash}.npz"
    if cache.exists() and not force:
        cached = _load_cache(cache, params)
        if cached is not None:
            return cached

    # ---- calibrated regional flow + the SAME spill location as the ADE demo ----
    cgwf, boundary, rivers, exe = _load_calibrated_flow()
    heads_array = cgwf.output.head().get_data().flatten()

    mg0 = cgwf.modelgrid
    xc0 = np.array(mg0.xcellcenters)
    yc0 = np.array(mg0.ycellcenters)
    spd0 = cgwf.output.budget().get_data(text="DATA-SPDIS")[0]
    ia0 = int(np.argmin((xc0 - ABS_XY[0]) ** 2 + (yc0 - ABS_XY[1]) ** 2))
    u_reg = np.array([spd0["qx"][ia0], spd0["qy"][ia0]], float)
    u_reg = u_reg / np.hypot(*u_reg)                 # regional (downgradient) direction
    spill_xy = (ABS_XY[0] - SPILL_UPGRADIENT_M * u_reg[0],
                ABS_XY[1] - SPILL_UPGRADIENT_M * u_reg[1])

    # ---- corridor refinement (SIGILL / Triangle-precision radius walk) ----
    corr_pts, _u, _L = _corridor_points(spill_xy, ABS_XY)
    refine_points = corr_pts + [tuple(INJ_XY)]
    res, refine_radius_used = _refine_with_retry(
        cgwf, boundary, rivers, refine_points, heads_array, case_ws / "refgrid",
        refine_radii=refine_radii, base_cell_size=LOCKED_PARAMS["base_cell_size"],
        refined_cell_size=LOCKED_PARAMS["refined_cell_size"], sim_name="rg")
    rgwf = res["gwf"]
    mg = res["modelgrid"]
    gp = res["gridprops"]
    ncpl = res["ncpl"]
    xc = np.array(mg.xcellcenters)
    yc = np.array(mg.ycellcenters)
    csz = _cellsize(mg, ncpl)

    k_ref = rgwf.npf.k.array
    top_ref = rgwf.disv.top.array
    botm_ref = rgwf.disv.botm.array
    heads_ref = rgwf.output.head().get_data().flatten()
    chd = rgwf.get_package("CHD").stress_period_data.get_data(0)
    riv = rgwf.get_package("RIV").stress_period_data.get_data(0)
    rch = rgwf.get_package("RCHA").recharge.get_data()

    injc = int(np.argmin((xc - INJ_XY[0]) ** 2 + (yc - INJ_XY[1]) ** 2))
    extc = int(np.argmin((xc - ABS_XY[0]) ** 2 + (yc - ABS_XY[1]) ** 2))

    # ---- STEADY GWF (same doublet / CHD / RIV / RCHA as the ADE demo) ----
    gwf_ws = case_ws / "gwf"
    sim = flopy.mf6.MFSimulation(sim_name="prtgwf", exe_name=exe, sim_ws=str(gwf_ws))
    # One steady period, ONE time step: the flow field is steady, so a single step
    # is all PRT's FMI needs (and FMI insists the GWF budget records it reads line
    # up with the PRT time discretisation -- see the PRT TDIS below, which matches).
    flopy.mf6.ModflowTdis(sim, time_units=LOCKED_PARAMS["time_units"], nper=1,
                          perioddata=[(float(track_days), 1, 1.0)])
    flopy.mf6.ModflowIms(sim, filename="gwf.ims", **_GWF_IMS)
    gwf = flopy.mf6.ModflowGwf(sim, modelname="gwf", save_flows=True,
                               newtonoptions=_GWF_NEWTON)
    flopy.mf6.ModflowGwfdisv(gwf, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                             botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
    # PRT's FMI needs BOTH specific discharge AND saturation in the GWF budget:
    # without save_saturation MF6 aborts with "SATURATION NOT FOUND IN BUDGET FILE.
    # SAVE_SATURATION AND SAVE_FLOWS MUST BE ACTIVATED IN THE NPF PACKAGE."
    flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=k_ref, save_flows=True,
                            save_specific_discharge=True, save_saturation=True)
    flopy.mf6.ModflowGwfic(gwf, strt=np.maximum(heads_ref, botm_ref[0] + 0.01))
    flopy.mf6.ModflowGwfsto(gwf, steady_state={0: True})
    flopy.mf6.ModflowGwfrcha(gwf, recharge=rch)
    flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["head"]))
                                                     for r in chd])
    flopy.mf6.ModflowGwfriv(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["stage"]),
                            float(r["cond"]), float(r["rbot"])) for r in riv])
    # doublet: FLOW ONLY (clean injection; the extraction well is the compliance well)
    flopy.mf6.ModflowGwfwel(gwf, pname="injw",
                            stress_period_data={0: [[(0, injc), abs(DOUBLET_Q)]]})
    flopy.mf6.ModflowGwfwel(gwf, pname="absw",
                            stress_period_data={0: [[(0, extc), -abs(DOUBLET_Q)]]})
    flopy.mf6.ModflowGwfoc(gwf, head_filerecord="gwf.hds", budget_filerecord="gwf.cbc",
                           saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")])
    sim.write_simulation(silent=True)
    ok, buf = sim.run_simulation(silent=True)
    if not ok:
        raise RuntimeError("PRT-capture GWF flow run failed; listing tail:\n"
                           + _run_failure_tail(gwf_ws, buf))

    # ---- is the extraction well a STRONG sink?  (this validates the whole
    # "terminated in the well cell == captured" classification -- see docstring) ----
    ext_in, ext_out = _strong_sink_check(gwf, extc)
    ext_is_strong = bool(ext_out <= 1e-6 * max(ext_in, 1.0))

    # ---- release disc on the spill footprint ----
    pts = release_disc(spill_xy[0], spill_xy[1], float(release_radius_m), n_particles)
    cells_all = np.array([int(np.argmin((xc - px) ** 2 + (yc - py) ** 2))
                          for px, py in pts])
    # Drop points that land in a doublet well cell: you cannot spill inside the
    # well, and such a particle terminates instantly (travel time exactly 0 d),
    # which would poison the travel-time statistics with a meaningless zero.
    keep = ~np.isin(cells_all, [extc, injc])
    n_dropped = int((~keep).sum())
    rel_pts = pts[keep]
    rel_cells = cells_all[keep]
    n_rel = int(rel_pts.shape[0])
    if n_rel < 1:
        raise RuntimeError("every release point landed in a doublet well cell; "
                           "release_radius_m / n_particles are degenerate")

    zmid = 0.5 * (np.asarray(top_ref, float) + np.asarray(botm_ref[0], float))

    # ---- PRT model (own simulation; reads the GWF flow field through FMI) ----
    prt_ws = case_ws / "prt"
    psim = flopy.mf6.MFSimulation(sim_name="prt", exe_name=exe, sim_ws=str(prt_ws))
    # TDIS matches the GWF's exactly (1 period, 1 step, same length) so FMI's
    # budget records line up one-for-one with PRT's time steps.
    flopy.mf6.ModflowTdis(psim, time_units=LOCKED_PARAMS["time_units"], nper=1,
                          perioddata=[(float(track_days), 1, 1.0)])
    prt = flopy.mf6.ModflowPrt(psim, modelname="prt")
    flopy.mf6.ModflowPrtdisv(prt, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                             botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
    # MIP: the advective velocity is v = q / porosity, so PRT needs the SAME locked
    # porosity the ADE demo's MST uses -- otherwise the two demos would be tracking
    # different aquifers.
    flopy.mf6.ModflowPrtmip(prt, porosity=porosity)
    pkgdata = [(i, (0, int(rel_cells[i])), float(rel_pts[i, 0]), float(rel_pts[i, 1]),
                float(zmid[int(rel_cells[i])])) for i in range(n_rel)]
    prp_kwargs: Dict[str, Any] = dict(
        nreleasepts=n_rel, packagedata=pkgdata,
        perioddata={0: ["FIRST"]},           # release every particle at t = 0
        exit_solve_tolerance=1e-5,
        extend_tracking=True,                # keep tracking past the (steady) sim end...
        stoptime=float(track_days),          # ...but no further than the tracking window
    )
    if stop_at_weak_sink:
        prp_kwargs["stop_at_weak_sink"] = True
    flopy.mf6.ModflowPrtprp(prt, pname="prp", **prp_kwargs)
    flopy.mf6.ModflowPrtoc(prt, pname="oc", track_filerecord=["prt.trk"],
                           trackcsv_filerecord=["prt.trk.csv"],
                           track_release=True, track_exit=True, track_terminate=True,
                           budget_filerecord="prt.cbc", saverecord=[("BUDGET", "ALL")])
    flopy.mf6.ModflowPrtfmi(prt, packagedata=[
        ("GWFHEAD", str(gwf_ws / "gwf.hds")),
        ("GWFBUDGET", str(gwf_ws / "gwf.cbc")),
    ])
    ems = flopy.mf6.ModflowEms(psim, pname="ems", filename="prt.ems")
    psim.register_solution_package(ems, [prt.name])
    psim.write_simulation(silent=True)
    ok, buf = psim.run_simulation(silent=True)
    if not ok:
        raise RuntimeError("PRT tracking run failed; listing tail:\n"
                           + _prt_failure_tail(prt_ws, buf))

    # ---- classify fates from the PRT track CSV ----
    import pandas as pd
    trk = pd.read_csv(prt_ws / "prt.trk.csv")
    irpt = trk["irpt"].to_numpy(dtype=int)
    if set(np.unique(irpt)) != set(range(1, n_rel + 1)):
        raise RuntimeError(
            f"PRT track output does not carry exactly the {n_rel} released particles "
            f"as irpt 1..{n_rel} (got {np.unique(irpt)[:5]}...); refusing to guess the "
            "particle indexing")
    idx = irpt - 1                                   # -> 0-based, aligned with rel_pts

    trk = trk.assign(_i=idx)
    term = trk[trk["ireason"] == _IREASON_TERMINATE]
    if len(term) != n_rel or term["_i"].nunique() != n_rel:
        raise RuntimeError(
            f"expected exactly one PRT termination record per particle ({n_rel}), "
            f"got {len(term)} records for {term['_i'].nunique()} particles")
    term = term.sort_values("_i")

    end_cells = term["icell"].to_numpy(dtype=int) - 1     # MF6 writes 1-based cell ids
    end_status = term["istatus"].to_numpy(dtype=int)
    end_x = term["x"].to_numpy(dtype=float)
    end_y = term["y"].to_numpy(dtype=float)
    end_t = term["t"].to_numpy(dtype=float)
    t_rel = term["trelease"].to_numpy(dtype=float)
    travel_times = end_t - t_rel

    # CAPTURED == terminated in the EXTRACTION-well cell.  Keyed on the CELL, not
    # on istatus: a control run with ISTOPZONE on the well cell terminates the very
    # same particles in the very same cell but reports a different istatus code.
    captured = np.asarray(end_cells == extc, dtype=bool)
    n_cap = int(captured.sum())
    n_esc = int(n_rel - n_cap)
    capture_fraction = float(n_cap) / float(n_rel)

    if n_cap and not ext_is_strong:
        # Not fatal (the classification would still be defensible via istatus), but
        # the docstring's justification would no longer hold -- say so loudly.
        raise RuntimeError(
            "the extraction well is NOT a strong sink in this flow field "
            f"(face outflow {ext_out:.4g} m^3/d vs inflow {ext_in:.4g} m^3/d); "
            "'terminated in the well cell == captured' can no longer be justified "
            "by strong-sink termination -- re-derive the classification before "
            "trusting the capture fraction")

    tt_cap = travel_times[captured]
    if tt_cap.size:
        tt_median = float(np.median(tt_cap))
        tt_p10 = float(np.percentile(tt_cap, 10))
        tt_p90 = float(np.percentile(tt_cap, 90))
        tt_min = float(tt_cap.min())
        tt_max = float(tt_cap.max())
    else:
        tt_median = tt_p10 = tt_p90 = tt_min = tt_max = float("nan")

    # ---- pathlines (M, 4): 0-based particle index, t, x, y ----
    order = np.lexsort((trk["t"].to_numpy(dtype=float), trk["_i"].to_numpy(dtype=int)))
    pathlines = np.column_stack([
        trk["_i"].to_numpy(dtype=float)[order],
        trk["t"].to_numpy(dtype=float)[order],
        trk["x"].to_numpy(dtype=float)[order],
        trk["y"].to_numpy(dtype=float)[order],
    ])

    # ---- the LATERAL answer the ADE could not give ----
    axis = np.array([ABS_XY[0] - spill_xy[0], ABS_XY[1] - spill_xy[1]], float)
    axis_len = float(np.hypot(*axis))
    axis_u = axis / axis_len
    perp = np.array([-axis_u[1], axis_u[0]])          # unit normal to the spill->well axis

    def _perp_offset(x, y):
        return (x - spill_xy[0]) * perp[0] + (y - spill_xy[1]) * perp[1]

    if n_cap:
        cap_idx = set(np.where(captured)[0].tolist())
        pl_i = pathlines[:, 0].astype(int)
        sel = np.array([i in cap_idx for i in pl_i])
        lateral_swath = float(np.abs(_perp_offset(pathlines[sel, 2],
                                                  pathlines[sel, 3])).max())
        capture_halfwidth = float(np.abs(_perp_offset(rel_pts[captured, 0],
                                                      rel_pts[captured, 1])).max())
    else:
        lateral_swath = float("nan")
        capture_halfwidth = float("nan")

    istatus_counts = {str(int(k)): int(v)
                      for k, v in zip(*np.unique(end_status, return_counts=True))}

    meta = dict(
        ncpl=int(ncpl),
        refine_radius_used=float(refine_radius_used),
        u_reg=(float(u_reg[0]), float(u_reg[1])),
        spill_to_well_m=axis_len,
        ext_inflow_m3d=float(ext_in),
        ext_outflow_m3d=float(ext_out),
        ext_is_strong_sink=bool(ext_is_strong),
        istatus_counts=istatus_counts,
        n_dropped_wellcell=int(n_dropped),
        ds_spill=float(csz[int(np.argmin((xc - spill_xy[0]) ** 2
                                         + (yc - spill_xy[1]) ** 2))]),
        ds_ext=float(csz[extc]),
        gwf_ws=str(gwf_ws),
        prt_ws=str(prt_ws),
        exe=str(exe),
    )

    result = PrtCapture(
        capture_fraction=capture_fraction,
        n_particles=int(n_particles), n_released=n_rel,
        n_captured=n_cap, n_escaped=n_esc,
        tt_median_d=tt_median, tt_p10_d=tt_p10, tt_p90_d=tt_p90,
        tt_min_d=tt_min, tt_max_d=tt_max,
        lateral_swath_m=lateral_swath, capture_halfwidth_m=capture_halfwidth,
        release_points=np.asarray(rel_pts, dtype=float),
        release_cells=np.asarray(rel_cells, dtype=np.int64),
        endpoints=np.column_stack([end_x, end_y, end_t]).astype(float),
        end_cells=np.asarray(end_cells, dtype=np.int64),
        end_status=np.asarray(end_status, dtype=np.int64),
        captured=captured,
        travel_times=np.asarray(travel_times, dtype=float),
        pathlines=pathlines,
        spill_xy=(float(spill_xy[0]), float(spill_xy[1])),
        axis_u=(float(axis_u[0]), float(axis_u[1])),
        ext_cell=int(extc), inj_cell=int(injc),
        release_radius_m=float(release_radius_m),
        track_days=float(track_days),
        stop_at_weak_sink=bool(stop_at_weak_sink),
        porosity=porosity,
        meta=meta,
    )

    _save_cache(cache, result, params)
    return result


def _src_sha() -> str:
    """SHA of THIS module's source AND the ADE module it inherits the model from.

    The doublet coordinates, the pumping rate, the spill-offset rule and the
    corridor refinement all live in ``transport_srcpulse_demo``; an edit there
    changes THIS model too, so it must bust THIS cache.
    """
    import transport_srcpulse_demo as _tsd
    h = hashlib.sha1()
    for p in (Path(__file__), Path(_tsd.__file__)):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# cache (solve-free re-call)
# ---------------------------------------------------------------------------
def _save_cache(path: Path, r: PrtCapture, params: Dict[str, Any]) -> None:
    np.savez(
        str(path),
        capture_fraction=r.capture_fraction,
        n_particles=r.n_particles, n_released=r.n_released,
        n_captured=r.n_captured, n_escaped=r.n_escaped,
        tt_median_d=r.tt_median_d, tt_p10_d=r.tt_p10_d, tt_p90_d=r.tt_p90_d,
        tt_min_d=r.tt_min_d, tt_max_d=r.tt_max_d,
        lateral_swath_m=r.lateral_swath_m, capture_halfwidth_m=r.capture_halfwidth_m,
        release_points=r.release_points, release_cells=r.release_cells,
        endpoints=r.endpoints, end_cells=r.end_cells, end_status=r.end_status,
        captured=r.captured, travel_times=r.travel_times, pathlines=r.pathlines,
        spill_xy=np.array(r.spill_xy), axis_u=np.array(r.axis_u),
        ext_cell=r.ext_cell, inj_cell=r.inj_cell,
        release_radius_m=r.release_radius_m, track_days=r.track_days,
        stop_at_weak_sink=r.stop_at_weak_sink, porosity=r.porosity,
        meta=r.meta, locked=r.locked, params=params, allow_pickle=True)


def _load_cache(path: Path, params: Dict[str, Any]) -> Optional[PrtCapture]:
    # The WHOLE body -- the params check AND every z[...] read AND the PrtCapture
    # construction -- lives inside this one try, so that a bad / incomplete /
    # legacy cache file cleanly MISSES (and rebuilds) instead of raising.  In
    # particular a dataclass field added later without touching the hashed
    # `params` dict would pass the key-set guard and then KeyError on the read.
    try:
        z = np.load(str(path), allow_pickle=True)
        stored = dict(z["params"].item())
        # A missing/extra key must NOT silently count as a match.
        if set(stored) != set(params):
            return None
        for k, v in params.items():
            sv = stored[k]
            if k == "refine_radii":
                sv_arr = np.asarray(sv, dtype=float)
                v_arr = np.asarray(v, dtype=float)
                if sv_arr.shape != v_arr.shape or np.any(np.abs(sv_arr - v_arr) > 1e-9):
                    return None
            elif k == "locked":
                if json.dumps(sv, sort_keys=True) != json.dumps(v, sort_keys=True):
                    return None
            elif isinstance(v, str) or isinstance(sv, str):
                # e.g. src_sha: the numeric branch below would crash on float("ab..")
                if str(sv) != str(v):
                    return None
            else:
                if abs(float(sv) - float(v)) > 1e-9:
                    return None
        # EVERY dataclass field is restored here.  A silently dropped field that
        # falls back to its default_factory is a bug this repo has already shipped
        # once; `test_cache_round_trip_fidelity` pins the npz key set against
        # dataclasses.fields(PrtCapture) so it cannot come back.  Scalars are cast
        # back to PLAIN Python types (not np.float64 / np.int64 / np.bool_), because
        # that is what the build path produces and the types must round-trip too.
        return PrtCapture(
            capture_fraction=float(z["capture_fraction"]),
            n_particles=int(z["n_particles"]), n_released=int(z["n_released"]),
            n_captured=int(z["n_captured"]), n_escaped=int(z["n_escaped"]),
            tt_median_d=float(z["tt_median_d"]), tt_p10_d=float(z["tt_p10_d"]),
            tt_p90_d=float(z["tt_p90_d"]), tt_min_d=float(z["tt_min_d"]),
            tt_max_d=float(z["tt_max_d"]),
            lateral_swath_m=float(z["lateral_swath_m"]),
            capture_halfwidth_m=float(z["capture_halfwidth_m"]),
            release_points=z["release_points"], release_cells=z["release_cells"],
            endpoints=z["endpoints"], end_cells=z["end_cells"],
            end_status=z["end_status"], captured=z["captured"],
            travel_times=z["travel_times"], pathlines=z["pathlines"],
            spill_xy=(float(z["spill_xy"][0]), float(z["spill_xy"][1])),
            axis_u=(float(z["axis_u"][0]), float(z["axis_u"][1])),
            ext_cell=int(z["ext_cell"]), inj_cell=int(z["inj_cell"]),
            release_radius_m=float(z["release_radius_m"]),
            track_days=float(z["track_days"]),
            stop_at_weak_sink=bool(z["stop_at_weak_sink"]),
            porosity=float(z["porosity"]),
            meta=dict(z["meta"].item()), locked=dict(z["locked"].item()))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# demo / smoke anchor
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    ADE_PEAK_DAY = 41.0          # transport_srcpulse_demo: peak 4.95 mg/L @ day 41
    ADE_PULSE_DAYS = 30.0

    t0 = time.time()
    r = build_prt_capture(force=("--force" in sys.argv))
    w = build_prt_capture(release_radius_m=WIDE_RELEASE_RADIUS_M,
                          force=("--force" in sys.argv))
    dt = time.time() - t0

    print("FORWARD PRT: IS THE SPILL FOOTPRINT CAPTURED BY THE DOUBLET?")
    print(f"  spill_xy         = ({r.spill_xy[0]:.1f}, {r.spill_xy[1]:.1f})  "
          f"[{SPILL_UPGRADIENT_M:.0f} m upgradient of the extraction well]")
    print(f"  extraction well  = cell {r.ext_cell}   injection well = cell {r.inj_cell}")
    print(f"  strong sink?     = {r.meta['ext_is_strong_sink']}  "
          f"(face inflow {r.meta['ext_inflow_m3d']:.1f}, "
          f"outflow {r.meta['ext_outflow_m3d']:.3g} m^3/d; well Q = -{DOUBLET_Q:.0f})")
    for tag, d in (("spill footprint", r), ("capture-zone probe", w)):
        print(f"  --- {tag}: radius {d.release_radius_m:.0f} m, "
              f"{d.n_released} particles ---")
        print(f"    captured / escaped = {d.n_captured} / {d.n_escaped}   "
              f"capture fraction = {d.capture_fraction:.3f}")
        print(f"    travel time [d]    = median {d.tt_median_d:.1f}  "
              f"(p10 {d.tt_p10_d:.1f}, p90 {d.tt_p90_d:.1f}, "
              f"min {d.tt_min_d:.1f}, max {d.tt_max_d:.1f})")
        print(f"    lateral swath      = {d.lateral_swath_m:.1f} m   "
              f"(captured-release half-width {d.capture_halfwidth_m:.1f} m)")
        print(f"    istatus counts     = {d.meta['istatus_counts']}")
    print("  --- PRT vs ADE (two DIFFERENT questions; both true) ---")
    print(f"    PRT: median ADVECTIVE travel time  = {r.tt_median_d:.1f} d")
    print(f"    ADE: CONCENTRATION peak            = {ADE_PEAK_DAY:.0f} d "
          f"(4.95 mg/L, dispersive, finite {ADE_PULSE_DAYS:.0f}-d pulse)")
    print(f"    consistency: pulse centre of mass at t = {ADE_PULSE_DAYS/2:.0f} d, "
          f"+ {r.tt_median_d:.1f} d advection = {ADE_PULSE_DAYS/2 + r.tt_median_d:.1f} d")
    print(f"  wall-clock = {dt:.0f}s")

    ok = (0.0 < r.capture_fraction <= 1.0
          and r.n_captured + r.n_escaped == r.n_released
          and math.isfinite(r.tt_median_d) and r.tt_median_d > 0.0
          and r.meta["ext_is_strong_sink"]
          and 0.0 < w.capture_fraction < 1.0)
    print("  SMOKE:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
