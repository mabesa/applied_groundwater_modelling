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
    extraction well, how long do they take to get there, and how wide is the
    well's capture zone?*

PRT says **NOTHING** about concentration, dilution, dispersion, sorption, decay or
any regulatory threshold.  "Is the concentration above the limit, and when" is the
ADE question, and it is answered -- separately -- by ``transport_srcpulse_demo``
(peak 4.95 mg/L at day 41).

**Do not connect the two numbers with arithmetic.**  PRT's median ADVECTIVE travel
time (~25.8 d) and the ADE's CONCENTRATION peak (day 41) are different quantities,
and in a converging 2-D flow field NO simple identity links them.  (The textbook
identity ``source centroid + mean advective travel time`` predicts a breakthrough
curve's CENTRE OF MASS -- its first temporal moment -- not its PEAK, because a
dispersive BTC is right-skewed and peaks before its centroid.  Even the centroid
version fails here: it predicts 40.7 d against the ADE breakthrough curve's actual
centroid of 48.2 d.  An earlier version of this module taught
``15 d + 25.8 d = 40.8 d ~= the day-41 peak`` as a cross-validation; it was
numerology -- two errors cancelling at one pulse length -- and it has been removed.)

HOW THE ADVECTION ENGINE IS ACTUALLY VERIFIED
---------------------------------------------
PRT can be checked directly against the FLOW FIELD it was handed, without invoking
the ADE at all.  Integrate the seepage velocity ``v = q / n_e`` (specific discharge
straight from the GWF budget's ``DATA-SPDIS``, locked porosity ``n_e = 0.20``)
along the spill -> well axis, and compare with what PRT reports:

    * flow field:  path-averaged ``v = L / integral(ds / v(s))`` = **3.21 m/d**;
      the travel-time integral over the 90 m axis is **28.0 d**
      (``v_flow_qn_mpd`` / ``tt_flow_integral_d``)
    * PRT:         median (pathline arc length / travel time) over the captured
      particles = **3.24 m/d** (``v_prt_path_mpd``), median arc length 83.6 m,
      median travel time 25.8 d

The two velocities agree to ~1%.  The ~8% gap between the 28.0 d integral and PRT's
25.8 d median is expected and diagnostic: PRT's paths curve as they converge, and
they TERMINATE on entering the extraction-well CELL (~7 m of the 90 m axis short of
the well node), so a PRT particle travels 83.6 m, not 90 m.

This is an *independent* computation -- specific discharge from the flow budget vs a
Lagrangian particle integration -- so it genuinely verifies the particle-tracking
engine.  Be honest about its reach, though: PRT and the ADE demo share the SAME flow
field, the SAME grid and the SAME porosity (only the transport engines differ), so
this check CANNOT detect an error in the flow solution itself.  The track's real
end-to-end transport verification is 04t Section 5's 2-D analytical benchmark.

THE LATERAL ANSWER: A REAL CAPTURE-ZONE HALF-WIDTH
--------------------------------------------------
``halfwidth_at_spill_m`` is measured by BISECTION on a TRANSECT: single particles are
released at increasing |offset| perpendicular to the spill -> well axis, at a stated
along-axis position ``s``, and the dividing streamline is bracketed to ``tol_m``.
It is a property of the FLOW FIELD, not of any probe: measured **78.9 m at the spill
transect (s = 0)**, unchanged when the bisection's own probe settings are varied
(max offset 120-200 m, scan density 25-41 points, tolerance 0.25-1.0 m).  See
:func:`capture_halfwidth_at`, which measures it at any transect.

The zone WIDENS upgradient -- 78.9 m at the spill, 104.7 m at 200 m upgradient,
~112 m at 300-500 m upgradient -- converging on the flow field's analytic asymptote

    y_max = Q / (2 q b) ~= 1370 / (2 * 6.34) ~= 108 m   (``asymptotic_halfwidth_m``)

with the regional unit-width discharge ``q * b`` read from the GWF budget upgradient
of the doublet.  That asymptote is the same screening formula 01t uses as
``y_max = Q / (2 T i)``; the numeric transect value AT THE SPILL is narrower than the
far-field asymptote, which is exactly what the geometry of a capture zone requires.
(``q * b`` varies 5.9-7.2 m^2/d along the corridor -- heterogeneous K, RIV and RCHA --
so the asymptote is only sharp to ~95-117 m.  It is a screen, not a measurement.)

``max_captured_offset_m`` is the OTHER, weaker number: the most off-axis release point
that happened to be captured in THIS disc.  It is a lower bound that GROWS with the
probe radius (82.9 m at r = 120 m, 90.3 m at r = 160 m, 86.9 m at r = 200 m in an
UNCHANGED flow field), and the point that sets it can sit upgradient of the spill
rather than on the spill transect.  It is NOT a capture-zone half-width; it is kept
only to show a student why a sampling statistic is not a physical property.

A capture zone is also a purely ADVECTIVE envelope.  A real, dispersive plume
straddles it: a source just outside the dividing streamline can still register at the
well, at low concentration.  "Outside 79 m => safe" is false.

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
_IREASON_TERMINATE = 3

# A release disc of this radius is wide enough to STRADDLE the capture-zone
# boundary (measured: capture fraction 0.72 at 120 m vs 1.00 at the default 10 m).
# The default 10 m release radius is a realistic spill footprint and lies ENTIRELY
# inside the capture zone -- which is the honest answer for this spill, but it
# teaches nothing about where the capture zone ENDS.  Use this radius for the
# capture-zone rung.
WIDE_RELEASE_RADIUS_M: float = 120.0

# --- transect-bisection settings for the REAL capture-zone half-width ---------
# The measured half-width is INSENSITIVE to all three (verified: 78.9 m at the spill
# for max offset 120-200 m, 25-41 scan points, tolerance 0.25-1.0 m).  That
# insensitivity is the whole point: unlike `max_captured_offset_m`, this number is a
# property of the flow field and not of the probe that measured it.
HALFWIDTH_MAX_OFFSET_M: float = 150.0     # widest |offset| the bisection will probe
HALFWIDTH_TOL_M: float = 0.5              # bracket the dividing streamline to this
HALFWIDTH_N_SCAN: int = 31                # coarse scan (also checks monotonicity)

# Window (along-axis, metres, NEGATIVE = upgradient of the spill) over which the
# REGIONAL unit-width discharge q*b is averaged for the analytic asymptote
# y_max = Q / (2 q b).  Far enough upgradient that the doublet barely perturbs it,
# but still inside the calibrated corridor.
_ASYMPTOTE_WINDOW_M: Tuple[float, float] = (-500.0, -200.0)
_ASYMPTOTE_STEP_M: float = 25.0


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

    # --- the LATERAL answer -----------------------------------------------------
    halfwidth_at_spill_m: float             # REAL capture-zone half-width, bisected on
                                            # the transect through the spill (s = 0).
                                            # A property of the FLOW FIELD: it does not
                                            # move with the probe.  [m]
    asymptotic_halfwidth_m: float           # Q / (2 q b) from the GWF budget: the flow
                                            # field's far-field analytic asymptote [m]
    max_captured_offset_m: float            # the most off-axis release point CAPTURED in
                                            # THIS disc.  A sampling statistic and a LOWER
                                            # BOUND that grows with the probe radius --
                                            # NOT a capture-zone half-width.  [m]

    # --- the advection engine, checked against the FLOW FIELD it was given -------
    v_prt_path_mpd: float                   # median (arc length / travel time), captured [m/d]
    v_flow_qn_mpd: float                    # L / integral(ds / (q/n)) on the spill->well
                                            # axis, straight from DATA-SPDIS  [m/d]
    tt_flow_integral_d: float               # integral(ds / (q/n)) over the 90 m axis [d]
    arc_len_median_m: float                 # median captured pathline arc length [m]

    release_points: np.ndarray              # (n_released, 2) x, y [m]
    release_cells: np.ndarray               # (n_released,) int, 0-based DISV cell
    endpoints: np.ndarray                   # (n_released, 3) x, y, t_end [m, m, d]
    end_cells: np.ndarray                   # (n_released,) int, 0-based terminating cell
    end_status: np.ndarray                  # (n_released,) int, MF6 PRT istatus
    captured: np.ndarray                    # (n_released,) bool
    travel_times: np.ndarray                # (n_released,) float [d] (all particles)
    arc_lengths: np.ndarray                 # (n_released,) float [m] pathline arc length
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

    KNOWN, ACCEPTED BIAS: pinning ``r_0 = 0`` and ``r_{n-1} = R`` (rather than the
    unbiased ``r_k = R * sqrt((k + 0.5) / n)``) puts one point exactly at the centre
    and one exactly on the rim, which over-weights the disc centre by O(1/n) -- about
    0.5% at n = 200.  It is kept deliberately: the on-axis centre particle is the
    anchor of the capture/escape contrast (it is the one particle guaranteed to be
    on the spill -> well streamline), and the resulting bias in a capture fraction is
    far smaller than the fraction's other, much larger caveats (see the module
    docstring: a capture fraction over a disc is a property of the DISC).
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


def _src_sha() -> str:
    """SHA of every module SOURCE this model is built from.

    * THIS module -- the doublet GWF, the FMI wiring, the release layout, the fate
      classification.
    * ``transport_srcpulse_demo`` -- the doublet coordinates, the pumping rate, the
      spill-offset rule and the corridor-refinement retry guard all live there.
    * ``model_io_utils`` -- it BUILDS the refined grid (``mio.build_refined_gwf_model``).
      Editing grid generation changes the model, and without this the edit would leave
      every warm cache valid while the grid moved underneath it.  This repo has already
      shipped that exact bug class once.

    NOTE: this function is deliberately NOT monkeypatched in the test that proves it
    works (`test_src_sha_tracks_every_model_source`) -- that test rewrites a byte of
    each real file on disk and requires the digest to move.
    """
    import model_io_utils as _mio
    import transport_srcpulse_demo as _tsd
    h = hashlib.sha1()
    for p in (Path(__file__), Path(_tsd.__file__), Path(_mio.__file__)):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# the flow field (steady GWF + doublet), built once per distinct FLOW identity
# ---------------------------------------------------------------------------
def _flow_params(track_days: float, refine_radii: Sequence[float]) -> Dict[str, Any]:
    """The identity of the FLOW model alone.

    Deliberately does NOT include n_particles / release_radius_m / stop_at_weak_sink:
    those are PRT-side knobs and do not change a single number in the GWF solution.
    The flow workspace is named from this hash, so two runs that differ only on the
    PRT side share (and correctly re-use) one flow directory, while two runs with
    DIFFERENT flow get DIFFERENT directories -- no overwriting, no stale
    ``meta["gwf_ws"]``.
    """
    return dict(track_days=float(track_days),
                refine_radii=list(map(float, refine_radii)),
                locked=dict(LOCKED_PARAMS),
                src_sha=_src_sha())


def _build_flow(case_ws: Path, track_days: float,
                refine_radii: Sequence[float]) -> Dict[str, Any]:
    """Calibrated regional flow -> corridor-refined grid -> steady GWF with the doublet.

    Returns everything the PRT side needs, plus the flow-field diagnostics the
    verification rests on (specific discharge, saturated thickness, the strong-sink
    check).  ``build_prt_capture`` and :func:`capture_halfwidth_at` share this.
    """
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
    flow_hash = hashlib.sha1(
        json.dumps(_flow_params(track_days, refine_radii),
                   sort_keys=True).encode("utf-8")).hexdigest()[:16]
    gwf_ws = case_ws / f"gwf_{flow_hash}"
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

    heads_gwf = gwf.output.head().get_data().flatten()
    spd = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    qx = np.asarray(spd["qx"], dtype=float)
    qy = np.asarray(spd["qy"], dtype=float)

    top_a = np.ravel(np.asarray(top_ref, dtype=float))
    botm_a = np.ravel(np.asarray(botm_ref[0], dtype=float))

    axis = np.array([ABS_XY[0] - spill_xy[0], ABS_XY[1] - spill_xy[1]], float)
    axis_len = float(np.hypot(*axis))
    axis_u = axis / axis_len

    return dict(
        exe=exe, gwf=gwf, gwf_ws=gwf_ws, flow_hash=flow_hash,
        gp=gp, ncpl=ncpl, xc=xc, yc=yc, csz=csz,
        top=top_ref, botm=botm_ref, top_a=top_a, botm_a=botm_a,
        heads=heads_gwf, qx=qx, qy=qy,
        extc=extc, injc=injc, spill_xy=spill_xy, u_reg=u_reg,
        axis_u=axis_u, axis_len=axis_len,
        perp=np.array([-axis_u[1], axis_u[0]]),
        ext_in=ext_in, ext_out=ext_out, ext_is_strong=ext_is_strong,
        refine_radius_used=float(refine_radius_used),
        porosity=float(LOCKED_PARAMS["porosity"]),
        track_days=float(track_days),
    )


def _cell_at(flow: Dict[str, Any], x: float, y: float) -> int:
    return int(np.argmin((flow["xc"] - x) ** 2 + (flow["yc"] - y) ** 2))


def _release_z(flow: Dict[str, Any], cell: int) -> float:
    """Mid-depth of the SATURATED column, not of the cell.

    The layer is UNCONFINED (heads ~399 m against a top of 403-407 m), so
    ``0.5 * (top + botm)`` can sit ABOVE the water table -- i.e. release a particle
    in the unsaturated zone.  It happens not to today (0/199 releases are dry), but a
    lower water table would break it silently.  Clamp the top to the head.
    """
    top = float(flow["top_a"][cell])
    botm = float(flow["botm_a"][cell])
    head = float(flow["heads"][cell])
    return 0.5 * (min(top, head) + botm)


# ---------------------------------------------------------------------------
# the PRT side: track an arbitrary set of release points through the flow field
# ---------------------------------------------------------------------------
def _run_prt(flow: Dict[str, Any], pts: np.ndarray, prt_ws: Path, *,
             track_days: float, stop_at_weak_sink: bool) -> Dict[str, np.ndarray]:
    """Run ONE PRT simulation for ``pts`` (N, 2) and return the per-particle fates.

    Returns ``release_cells``, ``end_cells``, ``end_status``, ``endpoints`` (x, y, t),
    ``travel_times``, ``arc_lengths`` (pathline length) and ``pathlines``
    ((M, 4): 0-based particle index, t, x, y).
    """
    import pandas as pd

    pts = np.asarray(pts, dtype=float).reshape(-1, 2)
    n_rel = int(pts.shape[0])
    if n_rel < 1:
        raise ValueError("no release points")
    cells = np.array([_cell_at(flow, px, py) for px, py in pts], dtype=int)

    psim = flopy.mf6.MFSimulation(sim_name="prt", exe_name=flow["exe"],
                                  sim_ws=str(prt_ws))
    # TDIS matches the GWF's exactly (1 period, 1 step, same length) so FMI's
    # budget records line up one-for-one with PRT's time steps.
    flopy.mf6.ModflowTdis(psim, time_units=LOCKED_PARAMS["time_units"], nper=1,
                          perioddata=[(float(track_days), 1, 1.0)])
    prt = flopy.mf6.ModflowPrt(psim, modelname="prt")
    flopy.mf6.ModflowPrtdisv(prt, nlay=1, ncpl=flow["ncpl"], nvert=flow["gp"]["nvert"],
                             top=flow["top"], botm=flow["botm"],
                             vertices=flow["gp"]["vertices"], cell2d=flow["gp"]["cell2d"])
    # MIP: the advective velocity is v = q / porosity, so PRT needs the SAME locked
    # porosity the ADE demo's MST uses -- otherwise the two demos would be tracking
    # different aquifers.
    flopy.mf6.ModflowPrtmip(prt, porosity=flow["porosity"])
    pkgdata = [(i, (0, int(cells[i])), float(pts[i, 0]), float(pts[i, 1]),
                _release_z(flow, int(cells[i]))) for i in range(n_rel)]
    prp_kwargs: Dict[str, Any] = dict(
        nreleasepts=n_rel, packagedata=pkgdata,
        perioddata={0: ["FIRST"]},           # release every particle at t = 0
        exit_solve_tolerance=1e-5,
        stoptime=float(track_days),          # close the tracking window here
    )
    if stop_at_weak_sink:
        prp_kwargs["stop_at_weak_sink"] = True
    flopy.mf6.ModflowPrtprp(prt, pname="prp", **prp_kwargs)
    flopy.mf6.ModflowPrtoc(prt, pname="oc", track_filerecord=["prt.trk"],
                           trackcsv_filerecord=["prt.trk.csv"],
                           track_release=True, track_exit=True, track_terminate=True,
                           budget_filerecord="prt.cbc", saverecord=[("BUDGET", "ALL")])
    flopy.mf6.ModflowPrtfmi(prt, packagedata=[
        ("GWFHEAD", str(flow["gwf_ws"] / "gwf.hds")),
        ("GWFBUDGET", str(flow["gwf_ws"] / "gwf.cbc")),
    ])
    ems = flopy.mf6.ModflowEms(psim, pname="ems", filename="prt.ems")
    psim.register_solution_package(ems, [prt.name])
    psim.write_simulation(silent=True)
    ok, buf = psim.run_simulation(silent=True)
    if not ok:
        raise RuntimeError("PRT tracking run failed; listing tail:\n"
                           + _prt_failure_tail(prt_ws, buf))

    trk = pd.read_csv(prt_ws / "prt.trk.csv")
    irpt = trk["irpt"].to_numpy(dtype=int)
    if set(np.unique(irpt)) != set(range(1, n_rel + 1)):
        raise RuntimeError(
            f"PRT track output does not carry exactly the {n_rel} released particles "
            f"as irpt 1..{n_rel} (got {np.unique(irpt)[:5]}...); refusing to guess the "
            "particle indexing")
    trk = trk.assign(_i=irpt - 1)                    # -> 0-based, aligned with `pts`

    term = trk[trk["ireason"] == _IREASON_TERMINATE]
    if len(term) != n_rel or term["_i"].nunique() != n_rel:
        raise RuntimeError(
            f"expected exactly one PRT termination record per particle ({n_rel}), "
            f"got {len(term)} records for {term['_i'].nunique()} particles")
    term = term.sort_values("_i")

    order = np.lexsort((trk["t"].to_numpy(dtype=float), trk["_i"].to_numpy(dtype=int)))
    pathlines = np.column_stack([
        trk["_i"].to_numpy(dtype=float)[order],
        trk["t"].to_numpy(dtype=float)[order],
        trk["x"].to_numpy(dtype=float)[order],
        trk["y"].to_numpy(dtype=float)[order],
    ])

    # arc length actually flown, per particle (NOT the straight-line spill->well
    # distance: PRT paths curve as they converge, and they stop at the well CELL).
    arc = np.zeros(n_rel, dtype=float)
    pl_i = pathlines[:, 0].astype(int)
    for i in range(n_rel):
        sel = pathlines[pl_i == i]
        arc[i] = float(np.hypot(np.diff(sel[:, 2]), np.diff(sel[:, 3])).sum())

    end_t = term["t"].to_numpy(dtype=float)
    t_rel = term["trelease"].to_numpy(dtype=float)
    return dict(
        release_cells=cells,
        end_cells=term["icell"].to_numpy(dtype=int) - 1,   # MF6 writes 1-based cell ids
        end_status=term["istatus"].to_numpy(dtype=int),
        endpoints=np.column_stack([term["x"].to_numpy(dtype=float),
                                   term["y"].to_numpy(dtype=float), end_t]),
        travel_times=end_t - t_rel,
        arc_lengths=arc,
        pathlines=pathlines,
    )


# ---------------------------------------------------------------------------
# the REAL capture-zone half-width: bisect the dividing streamline on a transect
# ---------------------------------------------------------------------------
def _bisect_halfwidth(flow: Dict[str, Any], s_along_axis_m: float, probe_ws: Path, *,
                      track_days: float, stop_at_weak_sink: bool = False,
                      max_offset_m: float = HALFWIDTH_MAX_OFFSET_M,
                      tol_m: float = HALFWIDTH_TOL_M,
                      n_scan: int = HALFWIDTH_N_SCAN) -> Dict[str, Any]:
    """Capture-zone half-width on the TRANSECT at along-axis position ``s``.

    ``s`` is measured from the SPILL along the spill -> well axis (positive =
    downgradient, toward the well; negative = upgradient).  Particles are released on
    the line through that point PERPENDICULAR to the axis, and the captured/escaped
    boundary is bracketed to ``tol_m`` by bisection, independently on each side (the
    zone is not symmetric -- the injection well sits off to one side).

    A coarse scan runs first, both to bracket the boundary and to CHECK that capture
    is monotone in |offset| on this transect (the captured points must form ONE
    contiguous run containing the axis).  If they do not, a single half-width is not a
    meaningful description of the boundary here and we say so rather than return a
    number: ``meta["scan_contiguous"]`` is False and the caller must not trust it.
    """
    origin = np.asarray(flow["spill_xy"], float) + s_along_axis_m * flow["axis_u"]
    perp = flow["perp"]

    def _fates(offsets: Sequence[float], tag: str) -> np.ndarray:
        off = np.asarray(offsets, dtype=float)
        pts = np.column_stack([origin[0] + off * perp[0], origin[1] + off * perp[1]])
        out = _run_prt(flow, pts, probe_ws / tag, track_days=track_days,
                       stop_at_weak_sink=stop_at_weak_sink)
        return np.asarray(out["end_cells"] == flow["extc"], dtype=bool)

    scan = np.linspace(-float(max_offset_m), float(max_offset_m), int(n_scan))
    cap = _fates(scan, "scan")
    idx = np.where(cap)[0]
    # the axis point itself (offset 0) must be captured, else lo=0 is a false floor.
    # Evaluate offset 0 EXPLICITLY -- np.linspace with an even n_scan never samples the
    # midpoint, so cap[argmin(|scan|)] would silently test the nearest off-axis point.
    axis_captured = bool(_fates([0.0], "axis")[0])
    contiguous = bool(idx.size > 0 and np.all(np.diff(idx) == 1) and axis_captured)

    n_runs = 1
    sides: Dict[str, float] = {}
    bracketed: Dict[str, bool] = {}
    converged: Dict[str, bool] = {}
    for sign, name in ((+1.0, "plus"), (-1.0, "minus")):
        lo, hi = 0.0, float(max_offset_m)          # lo = captured, hi = escaped
        fate = {round(float(scan[i]), 9): bool(cap[i]) for i in range(scan.size)}
        found_escape = False
        for a in sorted(abs(float(v)) for v in scan if v * sign > 0):
            if fate[round(sign * a, 9)]:
                lo = a
            else:
                hi = a
                found_escape = True   # an escaped sample beyond the captured axis, within max_offset
                break
        it = 0
        while hi - lo > tol_m and it < 30:
            mid = 0.5 * (lo + hi)
            if bool(_fates([sign * mid], f"{name}{it}")[0]):
                lo = mid
            else:
                hi = mid
            it += 1
            n_runs += 1
        sides[name] = 0.5 * (lo + hi)
        # a side is only meaningful if the axis is captured AND we actually bracketed
        # an escape within max_offset (else the zone runs past the probe on this side).
        bracketed[name] = bool(axis_captured and found_escape)
        converged[name] = bool(hi - lo <= tol_m)

    half = 0.5 * (sides["plus"] + sides["minus"])
    is_bracketed = bool(bracketed["plus"] and bracketed["minus"])
    is_converged = bool(converged["plus"] and converged["minus"])
    # a single half-width only describes the boundary when the scan is monotone AND
    # both sides bracketed an escape AND bisection converged; otherwise refuse to
    # return a number the caller would over-trust (NaN, with the flags to explain why).
    valid = bool(contiguous and is_bracketed and is_converged)
    return dict(
        halfwidth_m=float(half) if valid else float("nan"),
        halfwidth_plus_m=float(sides["plus"]),
        halfwidth_minus_m=float(sides["minus"]),
        s_along_axis_m=float(s_along_axis_m),
        tol_m=float(tol_m),
        max_offset_m=float(max_offset_m),
        n_scan=int(n_scan),
        scan_contiguous=contiguous,
        bracketed=is_bracketed,
        converged=is_converged,
        valid=valid,
        n_prt_runs=int(n_runs),
    )


def capture_halfwidth_at(
    s_along_axis_m: float = 0.0,
    *,
    track_days: float = 730.0,
    case_ws: Optional[Union[str, Path]] = None,
    refine_radii: Sequence[float] = (70.0, 62.0, 78.0, 56.0, 84.0),
    max_offset_m: float = HALFWIDTH_MAX_OFFSET_M,
    tol_m: float = HALFWIDTH_TOL_M,
    n_scan: int = HALFWIDTH_N_SCAN,
) -> Dict[str, Any]:
    """The REAL capture-zone half-width on the transect at along-axis position ``s``.

    ``s_along_axis_m`` is measured FROM THE SPILL along the spill -> extraction-well
    axis: ``0.0`` is the spill transect, negative is upgradient of the spill, positive
    is downgradient (toward the well).

    Unlike ``PrtCapture.max_captured_offset_m``, this number is a property of the FLOW
    FIELD, not of a probe: it does not move when the probe's radius, scan density or
    tolerance change (verified -- see the module docstring, and
    ``test_halfwidth_is_stable_across_probe_radii``).  Returns a dict with
    ``halfwidth_m`` (the mean of the two sides), ``halfwidth_plus_m`` /
    ``halfwidth_minus_m`` (the capture zone is NOT symmetric about the axis: the
    injection well sits off to one side), ``asymptotic_halfwidth_m`` and
    ``scan_contiguous`` (False => capture is not monotone in |offset| on this transect
    and a single half-width does not describe it).

    Measured at the spill (s = 0): **78.9 m** (+81.4 / -76.4).  It WIDENS upgradient
    -- 104.7 m at s = -200 m, ~112 m at s = -300..-500 m -- converging on the flow
    field's analytic asymptote ``Q / (2 q b) ~= 108 m``.

    Each call builds the steady GWF flow field once (~2 s) and then runs a handful of
    small PRT simulations (~0.2 s each), so it is cheap.
    """
    if not math.isfinite(s_along_axis_m):
        raise ValueError(f"s_along_axis_m must be finite (got {s_along_axis_m!r})")
    if not (math.isfinite(max_offset_m) and max_offset_m > 0.0):
        raise ValueError(f"max_offset_m must be > 0 (got {max_offset_m!r})")
    if not (math.isfinite(tol_m) and tol_m > 0.0):
        raise ValueError(f"tol_m must be > 0 (got {tol_m!r})")
    if int(n_scan) < 5:
        raise ValueError(f"n_scan must be >= 5 (got {n_scan!r})")

    case_ws = Path(case_ws) if case_ws is not None else _default_case_ws()
    case_ws.mkdir(parents=True, exist_ok=True)
    flow = _build_flow(case_ws, float(track_days), refine_radii)

    out = _bisect_halfwidth(
        flow, float(s_along_axis_m),
        case_ws / f"hwprobe_{flow['flow_hash']}",
        track_days=float(track_days), max_offset_m=float(max_offset_m),
        tol_m=float(tol_m), n_scan=int(n_scan))
    qb = _regional_qb(flow)
    out["asymptotic_halfwidth_m"] = float(DOUBLET_Q / (2.0 * qb["qb_m2d"]))
    out["regional_qb_m2d"] = qb["qb_m2d"]
    out["spill_xy"] = (float(flow["spill_xy"][0]), float(flow["spill_xy"][1]))
    out["axis_u"] = (float(flow["axis_u"][0]), float(flow["axis_u"][1]))
    return out


# ---------------------------------------------------------------------------
# flow-field diagnostics: the seepage-velocity integral and the analytic asymptote
# ---------------------------------------------------------------------------
def _axis_seepage(flow: Dict[str, Any], n_samples: int = 91) -> Dict[str, float]:
    """Seepage velocity v = q / n_e sampled from DATA-SPDIS along the spill -> well axis.

    This is the INDEPENDENT check on PRT's advection engine: ``q`` comes straight out of
    the GWF budget and ``n_e`` is the locked porosity, so nothing here touches the
    particle tracker.  Returns the travel-time integral ``T = integral(ds / v)`` over the
    90 m axis and the equivalent path-averaged velocity ``L / T``.

    ``v`` is the local seepage SPEED ``|q| / n_e`` (magnitude), deliberately -- it is
    compared against PRT's path-averaged speed ``v_prt_path = arc_len / travel_time``,
    which is itself the average of ``|q| / n_e`` along the (curved) particle path, so the
    two are like-for-like SPEEDS.  Along the spill->well axis the flow is near-axis-aligned
    (the axis projection ``q.u_hat / n_e`` differs from ``|q| / n_e`` by <1% here), so the
    choice does not move the number.
    """
    L = float(flow["axis_len"])
    n_e = float(flow["porosity"])
    if int(n_samples) < 2:
        raise ValueError(f"n_samples must be >= 2 (got {n_samples!r})")
    s = np.linspace(0.0, L, int(n_samples))
    v = np.empty_like(s)
    for j, sj in enumerate(s):
        i = _cell_at(flow, flow["spill_xy"][0] + sj * flow["axis_u"][0],
                     flow["spill_xy"][1] + sj * flow["axis_u"][1])
        v[j] = float(np.hypot(flow["qx"][i], flow["qy"][i])) / n_e
    if not np.all(v > 0.0):
        raise RuntimeError("zero specific discharge on the spill->well axis; the flow "
                           "field cannot advect anything and the verification is void")
    tt = float(np.trapezoid(1.0 / v, s))
    return dict(tt_flow_integral_d=tt, v_flow_qn_mpd=L / tt,
                v_axis_mean_mpd=float(v.mean()), axis_len_m=L)


def _regional_qb(flow: Dict[str, Any]) -> Dict[str, float]:
    """Regional unit-width discharge q * b [m^2/d], averaged UPGRADIENT of the doublet.

    Feeds the analytic asymptotic half-width ``y_max = Q / (2 q b)`` -- the same
    screening formula 01t writes as ``Q / (2 T i)``, since ``T i = K b i = q b``.
    Sampled far enough upgradient (500 -> 200 m) that the doublet barely perturbs it.
    ``q * b`` varies 5.9-7.2 m^2/d along the corridor (heterogeneous K, RIV, RCHA), so
    the asymptote is only sharp to about +-10%: it is a SCREEN, not a measurement.
    """
    lo, hi = _ASYMPTOTE_WINDOW_M
    s = np.arange(lo, hi + 1e-9, _ASYMPTOTE_STEP_M)
    vals = []
    for sj in s:
        i = _cell_at(flow, flow["spill_xy"][0] + sj * flow["axis_u"][0],
                     flow["spill_xy"][1] + sj * flow["axis_u"][1])
        b = float(min(flow["top_a"][i], flow["heads"][i]) - flow["botm_a"][i])
        q = float(np.hypot(flow["qx"][i], flow["qy"][i]))
        vals.append(q * b)
    v = np.asarray(vals, dtype=float)
    if not np.all(v > 0.0):
        raise RuntimeError("non-positive regional q*b upgradient of the doublet")
    return dict(qb_m2d=float(v.mean()), qb_min_m2d=float(v.min()),
                qb_max_m2d=float(v.max()))


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
        points that would land inside the EXTRACTION-well cell are dropped (you
        cannot spill inside the well, and such a particle reports a travel time of
        exactly 0 d, which would poison the travel-time statistics), so
        ``n_released`` can be slightly smaller than ``n_particles``;
        ``meta["n_dropped_wellcell"]`` records how many.

        BIAS, STATED PLAINLY: a dropped point would have been CAPTURED (it is inside
        the well), so dropping it DEFLATES the capture fraction -- at r = 120 m the
        one dropped point turns 144/200 = 0.7200 into 143/199 = 0.7186.  Points in
        the INJECTION-well cell are NOT dropped: the injection well is a SOURCE, a
        particle released there advects away normally, and its travel time is not 0.
        (In practice no release point lands there at any radius used here;
        ``meta["n_released_in_injcell"]`` records it if one ever does.)
    release_radius_m : float
        Radius of the spill footprint [m].  The default (10 m) is a realistic
        footprint and lies ENTIRELY inside the capture zone (capture fraction
        1.0).  Use ``WIDE_RELEASE_RADIUS_M`` (120 m) to straddle the capture-zone
        boundary and get a fraction strictly between 0 and 1.

        NOTE that the resulting ``capture_fraction`` is a property of the DISC, not of
        the doublet: it is "the fraction of THIS probe disc that happens to lie inside
        the capture zone".  The 120 m disc even reaches ~30 m DOWNGRADIENT of the well,
        and those points can never be captured, yet they count as escaped.  Read the
        captured/escaped scatter, not the scalar -- and read
        ``halfwidth_at_spill_m`` for the number that IS a property of the flow field.
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
        # A fingerprint of the model SOURCE -- this module, the ADE module it imports
        # the doublet / spill geometry / corridor refinement from, AND model_io_utils,
        # which BUILDS the refined grid.  LOCKED_PARAMS only covers that one dict:
        # editing DOUBLET_Q, SPILL_UPGRADIENT_M, INJ_XY/ABS_XY, the release layout, the
        # FMI wiring, the fate classification or the grid generator would otherwise
        # leave the hash (and every warm cache, notebook users included) unchanged
        # while the model changed underneath it.  This repo has already shipped that
        # bug once.
        src_sha=_src_sha(),
    )
    cache_hash = hashlib.sha1(
        json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    cache = case_ws / f"prtcapture_cache_{cache_hash}.npz"
    if cache.exists() and not force:
        cached = _load_cache(cache, params)
        if cached is not None:
            return cached

    # ---- the flow field (steady GWF + doublet), and the checks that rest on it ----
    flow = _build_flow(case_ws, float(track_days), refine_radii)
    extc, injc = flow["extc"], flow["injc"]
    spill_xy = flow["spill_xy"]

    # ---- release disc on the spill footprint ----
    pts = release_disc(spill_xy[0], spill_xy[1], float(release_radius_m), n_particles)
    cells_all = np.array([_cell_at(flow, px, py) for px, py in pts])
    # Drop points that land in the EXTRACTION-well cell only: you cannot spill inside
    # the abstraction well, and such a particle terminates instantly (travel time
    # exactly 0 d), which would poison the travel-time statistics with a meaningless
    # zero.  It also DEFLATES the capture fraction, because a point inside the well is
    # a point that would have been captured -- see the docstring.  A point in the
    # INJECTION-well cell is a different animal (that well is a SOURCE: the particle
    # advects away normally, with a perfectly ordinary travel time), so it is KEPT.
    keep = cells_all != extc
    n_dropped = int((~keep).sum())
    n_in_inj = int((cells_all[keep] == injc).sum())
    rel_pts = pts[keep]
    n_rel = int(rel_pts.shape[0])
    if n_rel < 1:
        raise RuntimeError("every release point landed in the extraction-well cell; "
                           "release_radius_m / n_particles are degenerate")

    prt_ws = case_ws / f"prt_{cache_hash}"
    out = _run_prt(flow, rel_pts, prt_ws, track_days=float(track_days),
                   stop_at_weak_sink=bool(stop_at_weak_sink))
    rel_cells = out["release_cells"]
    end_cells = out["end_cells"]
    end_status = out["end_status"]
    travel_times = out["travel_times"]
    arc_lengths = out["arc_lengths"]
    pathlines = out["pathlines"]

    # CAPTURED == terminated in the EXTRACTION-well cell.  Keyed on the CELL, not
    # on istatus: a control run with ISTOPZONE on the well cell terminates the very
    # same particles in the very same cell but reports a different istatus code.
    captured = np.asarray(end_cells == extc, dtype=bool)
    n_cap = int(captured.sum())
    n_esc = int(n_rel - n_cap)
    capture_fraction = float(n_cap) / float(n_rel)

    if n_cap and not flow["ext_is_strong"]:
        # FATAL, deliberately: the docstring's justification for the entire
        # classification ("terminated in the well cell == captured by the well") is
        # strong-sink termination.  If the well is not a strong sink, that justification
        # is gone and the capture fraction is not a number anyone should read.
        raise RuntimeError(
            "the extraction well is NOT a strong sink in this flow field "
            f"(face outflow {flow['ext_out']:.4g} m^3/d vs inflow "
            f"{flow['ext_in']:.4g} m^3/d); 'terminated in the well cell == captured' "
            "can no longer be justified by strong-sink termination -- re-derive the "
            "classification before trusting the capture fraction")

    tt_cap = travel_times[captured]
    if tt_cap.size:
        tt_median = float(np.median(tt_cap))
        tt_p10 = float(np.percentile(tt_cap, 10))
        tt_p90 = float(np.percentile(tt_cap, 90))
        tt_min = float(tt_cap.min())
        tt_max = float(tt_cap.max())
        arc_median = float(np.median(arc_lengths[captured]))
        # PATH-averaged velocity: arc length actually flown / time actually taken.
        # NOT spill_to_well_m / tt_median -- the particles never travel the straight
        # 90 m axis (they curve, and they stop at the well CELL, ~7 m short of the
        # node), so that quotient divides by a distance nothing travelled.
        v_prt_path = float(np.median(arc_lengths[captured] / tt_cap))
    else:
        tt_median = tt_p10 = tt_p90 = tt_min = tt_max = float("nan")
        arc_median = v_prt_path = float("nan")

    # ---- VERIFY the advection engine against the flow field it was given ----
    seep = _axis_seepage(flow)
    qb = _regional_qb(flow)
    asymptotic_halfwidth = float(DOUBLET_Q / (2.0 * qb["qb_m2d"]))

    # ---- the REAL lateral answer: bisect the dividing streamline at the spill ----
    hw = _bisect_halfwidth(flow, 0.0, case_ws / f"hwprobe_{flow['flow_hash']}",
                           track_days=float(track_days),
                           stop_at_weak_sink=bool(stop_at_weak_sink))

    # ---- and the WEAK lateral number, kept only to be contrasted with it ----
    perp = flow["perp"]

    def _perp_offset(x, y):
        return (x - spill_xy[0]) * perp[0] + (y - spill_xy[1]) * perp[1]

    max_captured_offset = (
        float(np.abs(_perp_offset(rel_pts[captured, 0], rel_pts[captured, 1])).max())
        if n_cap else float("nan"))

    istatus_counts = {str(int(k)): int(v)
                      for k, v in zip(*np.unique(end_status, return_counts=True))}

    meta = dict(
        ncpl=int(flow["ncpl"]),
        refine_radius_used=float(flow["refine_radius_used"]),
        u_reg=(float(flow["u_reg"][0]), float(flow["u_reg"][1])),
        spill_to_well_m=float(flow["axis_len"]),
        ext_inflow_m3d=float(flow["ext_in"]),
        ext_outflow_m3d=float(flow["ext_out"]),
        ext_is_strong_sink=bool(flow["ext_is_strong"]),
        istatus_counts=istatus_counts,
        n_dropped_wellcell=int(n_dropped),
        n_released_in_injcell=int(n_in_inj),
        # the half-width probe (a property of the flow field, not of the disc)
        halfwidth_plus_m=float(hw["halfwidth_plus_m"]),
        halfwidth_minus_m=float(hw["halfwidth_minus_m"]),
        halfwidth_s_m=float(hw["s_along_axis_m"]),
        halfwidth_tol_m=float(hw["tol_m"]),
        halfwidth_max_offset_m=float(hw["max_offset_m"]),
        halfwidth_n_scan=int(hw["n_scan"]),
        halfwidth_scan_contiguous=bool(hw["scan_contiguous"]),
        # the analytic asymptote and the flow-field velocity check
        regional_qb_m2d=float(qb["qb_m2d"]),
        regional_qb_min_m2d=float(qb["qb_min_m2d"]),
        regional_qb_max_m2d=float(qb["qb_max_m2d"]),
        v_axis_mean_mpd=float(seep["v_axis_mean_mpd"]),
        ds_spill=float(flow["csz"][_cell_at(flow, spill_xy[0], spill_xy[1])]),
        ds_ext=float(flow["csz"][extc]),
        gwf_ws=str(flow["gwf_ws"]),
        prt_ws=str(prt_ws),
        exe=str(flow["exe"]),
    )

    result = PrtCapture(
        capture_fraction=capture_fraction,
        n_particles=int(n_particles), n_released=n_rel,
        n_captured=n_cap, n_escaped=n_esc,
        tt_median_d=tt_median, tt_p10_d=tt_p10, tt_p90_d=tt_p90,
        tt_min_d=tt_min, tt_max_d=tt_max,
        halfwidth_at_spill_m=float(hw["halfwidth_m"]),
        asymptotic_halfwidth_m=asymptotic_halfwidth,
        max_captured_offset_m=max_captured_offset,
        v_prt_path_mpd=v_prt_path,
        v_flow_qn_mpd=float(seep["v_flow_qn_mpd"]),
        tt_flow_integral_d=float(seep["tt_flow_integral_d"]),
        arc_len_median_m=arc_median,
        release_points=np.asarray(rel_pts, dtype=float),
        release_cells=np.asarray(rel_cells, dtype=np.int64),
        endpoints=np.asarray(out["endpoints"], dtype=float),
        end_cells=np.asarray(end_cells, dtype=np.int64),
        end_status=np.asarray(end_status, dtype=np.int64),
        captured=captured,
        travel_times=np.asarray(travel_times, dtype=float),
        arc_lengths=np.asarray(arc_lengths, dtype=float),
        pathlines=pathlines,
        spill_xy=(float(spill_xy[0]), float(spill_xy[1])),
        axis_u=(float(flow["axis_u"][0]), float(flow["axis_u"][1])),
        ext_cell=int(extc), inj_cell=int(injc),
        release_radius_m=float(release_radius_m),
        track_days=float(track_days),
        stop_at_weak_sink=bool(stop_at_weak_sink),
        porosity=porosity,
        meta=meta,
    )

    _save_cache(cache, result, params)
    return result


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
        halfwidth_at_spill_m=r.halfwidth_at_spill_m,
        asymptotic_halfwidth_m=r.asymptotic_halfwidth_m,
        max_captured_offset_m=r.max_captured_offset_m,
        v_prt_path_mpd=r.v_prt_path_mpd, v_flow_qn_mpd=r.v_flow_qn_mpd,
        tt_flow_integral_d=r.tt_flow_integral_d, arc_len_median_m=r.arc_len_median_m,
        release_points=r.release_points, release_cells=r.release_cells,
        endpoints=r.endpoints, end_cells=r.end_cells, end_status=r.end_status,
        captured=r.captured, travel_times=r.travel_times, arc_lengths=r.arc_lengths,
        pathlines=r.pathlines,
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
            halfwidth_at_spill_m=float(z["halfwidth_at_spill_m"]),
            asymptotic_halfwidth_m=float(z["asymptotic_halfwidth_m"]),
            max_captured_offset_m=float(z["max_captured_offset_m"]),
            v_prt_path_mpd=float(z["v_prt_path_mpd"]),
            v_flow_qn_mpd=float(z["v_flow_qn_mpd"]),
            tt_flow_integral_d=float(z["tt_flow_integral_d"]),
            arc_len_median_m=float(z["arc_len_median_m"]),
            release_points=z["release_points"], release_cells=z["release_cells"],
            endpoints=z["endpoints"], end_cells=z["end_cells"],
            end_status=z["end_status"], captured=z["captured"],
            travel_times=z["travel_times"], arc_lengths=z["arc_lengths"],
            pathlines=z["pathlines"],
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
              f"{d.n_released} particles ({d.meta['n_dropped_wellcell']} dropped: "
              f"in the extraction-well cell) ---")
        print(f"    captured / escaped = {d.n_captured} / {d.n_escaped}   "
              f"capture fraction = {d.capture_fraction:.3f}  "
              f"(a property of THIS disc, not of the doublet)")
        print(f"    travel time [d]    = median {d.tt_median_d:.1f}  "
              f"(p10 {d.tt_p10_d:.1f}, p90 {d.tt_p90_d:.1f}, "
              f"min {d.tt_min_d:.1f}, max {d.tt_max_d:.1f})")
        print(f"    max captured offset= {d.max_captured_offset_m:.1f} m   "
              f"(a LOWER BOUND that grows with the probe radius -- not a half-width)")
        print(f"    istatus counts     = {d.meta['istatus_counts']}")
    print("  --- THE LATERAL ANSWER (a property of the flow field) ---")
    print(f"    capture-zone half-width at the SPILL transect (s = 0) = "
          f"{r.halfwidth_at_spill_m:.1f} m "
          f"(+{r.meta['halfwidth_plus_m']:.1f} / -{r.meta['halfwidth_minus_m']:.1f}, "
          f"bisected to {r.meta['halfwidth_tol_m']:.1f} m)")
    print(f"    analytic far-field asymptote Q/(2 q b)               = "
          f"{r.asymptotic_halfwidth_m:.1f} m  "
          f"(q*b = {r.meta['regional_qb_m2d']:.2f} m^2/d)")
    print("  --- VERIFICATION: PRT's advection engine vs the FLOW FIELD it was given ---")
    print(f"    PRT   path-averaged velocity (arc / time) = {r.v_prt_path_mpd:.2f} m/d "
          f"(median arc {r.arc_len_median_m:.1f} m, median t {r.tt_median_d:.1f} d)")
    print(f"    FLOW  q/n integrated along the axis       = {r.v_flow_qn_mpd:.2f} m/d "
          f"(travel-time integral {r.tt_flow_integral_d:.1f} d over "
          f"{r.meta['spill_to_well_m']:.0f} m)")
    print("    NOTE: PRT's advective timescale and the ADE's day-41 CONCENTRATION peak "
          "are different\n          quantities; no simple identity connects them in a "
          "converging 2-D field.")
    print(f"  wall-clock = {dt:.0f}s")

    ok = (0.0 < r.capture_fraction <= 1.0
          and math.isfinite(r.tt_median_d) and r.tt_median_d > 0.0
          and r.meta["ext_is_strong_sink"]
          and 0.0 < w.capture_fraction < 1.0
          and r.meta["halfwidth_scan_contiguous"]
          and abs(r.v_prt_path_mpd - r.v_flow_qn_mpd) < 0.25 * r.v_flow_qn_mpd)
    print("  SMOKE:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
