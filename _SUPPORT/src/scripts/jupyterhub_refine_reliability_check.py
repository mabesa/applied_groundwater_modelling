#!/usr/bin/env python
"""
================================================================================
 cs=10 GWT-REFINEMENT RELIABILITY CHECK  (run on the course JupyterHub / Linux)
================================================================================

PURPOSE
    A spike on macOS/arm64 + MODFLOW6 6.7.0 found that locally refining the
    Limmat DISV Voronoi grid to ~10 m cells around a contaminant source and
    running a GWF6-GWT6 transport model crashes with SIGILL (illegal
    instruction, exit code 132) for ~40% of source locations -- deterministic,
    solver-independent, on geometrically healthy grids. Project memory says
    cs=10 "reliably works" (presumably on the Linux JupyterHub mf6 build).

    This script settles the platform question: it sweeps ~10 deep-interior
    source locations, attempts the full refine -> GWF -> GWT pipeline at each,
    classifies the outcome, and prints a clear VERDICT on whether cs=10 GWT
    refinement is reliable ON THIS PLATFORM.

HOW TO RUN
    uv run python jupyterhub_refine_reliability_check.py
    (optionally:  SWEEP_N=6 uv run python jupyterhub_refine_reliability_check.py)

REQUIREMENTS
    - The course repo (so we can import disv_grid_utils / model_io_utils).
    - The flow model workspace (notebook4_model) with a solved GWF run.
    - mf6 + triangle executables resolvable by flopy (they are in the course env).
    EDIT THE TWO CONSTANTS BELOW if your paths differ.
================================================================================
"""
import os, sys, time, subprocess, traceback

# ----------------------------------------------------------------------------
# EDIT THESE TWO PATHS IF NEEDED
# ----------------------------------------------------------------------------
# (env vars REPO_ROOT / MODEL_WS override these, for convenience)
REPO_ROOT  = os.environ.get("REPO_ROOT", os.path.expanduser("~/applied_groundwater_modelling"))          # course repo
MODEL_WS   = os.environ.get("MODEL_WS",  os.path.expanduser("~/applied_groundwater_modelling_data/limmat/notebook4_model"))
# ----------------------------------------------------------------------------

SUPPORT_SRC = os.path.join(REPO_ROOT, "_SUPPORT", "src")
sys.path.append(SUPPORT_SRC)

import numpy as np
import flopy
import geopandas as gpd
from shapely.geometry import Point, Polygon
from scipy.interpolate import NearestNDInterpolator

import disv_grid_utils as dgu          # noqa: E402
import model_io_utils as mio           # noqa: E402

# --- config ---------------------------------------------------------------
SIM_NAME      = "limmat_valley"
REFINED_CS    = 10.0          # the cell size under test
REFINE_RADIUS = 200.0
BASE_CS       = 50.0
MIN_EDGE_DIST = 350.0         # deep-interior threshold (m from boundary)
N_LOCATIONS   = int(os.environ.get("SWEEP_N", "10"))
PORO, ALH, ATH = 0.20, 5.0, 0.5
TOTT, NSTP    = 1825.0, 30    # 5 yr, modest steps -> keeps each GWT run quick
WORK          = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reliability_sweep")
os.makedirs(WORK, exist_ok=True)

def banner(msg):
    print("\n" + "=" * 78 + "\n " + msg + "\n" + "=" * 78, flush=True)

def find_mf6():
    import shutil
    exe = shutil.which("mf6")
    if exe is None:
        # flopy's bundled location
        cand = os.path.expanduser("~/.local/share/flopy/bin/mf6")
        exe = cand if os.path.exists(cand) else "mf6"
    return exe

MF6 = find_mf6()

# --------------------------------------------------------------------------
banner("SETUP: loading flow model and boundary")
print(f"  REPO_ROOT  = {REPO_ROOT}")
print(f"  MODEL_WS   = {MODEL_WS}")
print(f"  mf6 exe    = {MF6}")
print(f"  refined_cs = {REFINED_CS} m   refine_radius = {REFINE_RADIUS} m   N = {N_LOCATIONS}")
try:
    print(f"  mf6 version: " + subprocess.run([MF6, "--version"], capture_output=True, text=True).stdout.strip().splitlines()[0])
except Exception:
    pass

csim = flopy.mf6.MFSimulation.load(sim_ws=MODEL_WS, exe_name=MF6, verbosity_level=0)
cgwf = csim.get_model(SIM_NAME)
mg   = cgwf.modelgrid
xc, yc = np.array(mg.xcellcenters), np.array(mg.ycellcenters)
heads  = cgwf.output.head().get_data().flatten()

# boundary + river GIS (read directly from the data folder next to the model)
GIS = os.path.join(os.path.dirname(MODEL_WS), "gis")
boundary_gdf = gpd.read_file(os.path.join(GIS, "limmat_model_boundary.gpkg"))
river_all    = gpd.read_file(os.path.join(GIS, "AV_Gewasser_-OGD.gpkg"))
river_gdf    = river_all[river_all["GEWAESSERNAME"].isin(["Limmat", "Sihl"])
                         & river_all.intersects(boundary_gdf.geometry.iloc[0])]
bpoly = boundary_gdf.geometry.iloc[0]
ext   = bpoly.boundary
print(f"  flow grid: {mg.ncpl} cells | boundary crs {boundary_gdf.crs} | {len(river_gdf)} river features")

# --------------------------------------------------------------------------
banner("PICKING DEEP-INTERIOR SOURCE LOCATIONS (farthest-point spread)")
rng = np.random.default_rng(12345)
cand = []
for _ in range(8000):
    px = rng.uniform(*mg.extent[:2]); py = rng.uniform(*mg.extent[2:])
    p = Point(px, py)
    if bpoly.contains(p) and p.distance(ext) > MIN_EDGE_DIST:
        cand.append((px, py))
cand = np.array(cand)
sel = [cand[0]]
while len(sel) < N_LOCATIONS:
    d = np.min([np.hypot(cand[:, 0] - s[0], cand[:, 1] - s[1]) for s in sel], axis=0)
    sel.append(cand[int(np.argmax(d))])
print(f"  selected {len(sel)} locations (all > {MIN_EDGE_DIST:.0f} m from boundary)")

# --------------------------------------------------------------------------
def add_gwt_and_run(sim, gwfname, gp, ncpl, src_cell, top, botm):
    gwt = flopy.mf6.ModflowGwt(sim, modelname="trans", save_flows=True)
    flopy.mf6.ModflowGwtdisv(gwt, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top, botm=botm,
                             vertices=gp["vertices"], cell2d=gp["cell2d"])
    flopy.mf6.ModflowGwtic(gwt, strt=0.0)
    flopy.mf6.ModflowGwtmst(gwt, porosity=PORO)
    flopy.mf6.ModflowGwtadv(gwt, scheme="TVD")
    flopy.mf6.ModflowGwtdsp(gwt, alh=ALH, ath1=ATH, diffc=0.0)
    flopy.mf6.ModflowGwtssm(gwt)
    flopy.mf6.ModflowGwtcnc(gwt, stress_period_data={0: [[(0, int(src_cell)), 1.0]]})
    flopy.mf6.ModflowGwtoc(gwt, concentration_filerecord="trans.ucn",
                           saverecord=[("CONCENTRATION", "LAST")])
    ims = flopy.mf6.ModflowIms(sim, filename="trans.ims", complexity="MODERATE",
                               linear_acceleration="BICGSTAB", outer_dvclose=1e-6, inner_dvclose=1e-7)
    sim.register_ims_package(ims, ["trans"])
    flopy.mf6.ModflowGwfgwt(sim, exgtype="GWF6-GWT6", exgmnamea=gwfname,
                            exgmnameb="trans", filename="c.gwfgwt")
    sim.tdis.nper = 1
    sim.tdis.perioddata = [(TOTT, NSTP, 1.2)]
    sim.write_simulation(silent=True)
    ok, _ = sim.run_simulation(silent=True)
    return ok

def mf6_returncode(ws):
    """Re-run mf6 in a workspace to capture the raw OS return code (132 = SIGILL)."""
    try:
        r = subprocess.run([MF6], cwd=ws, capture_output=True, text=True, timeout=300)
        return r.returncode, ("SIGILL" in (r.stdout + r.stderr))
    except Exception:
        return None, False

def classify(i, px, py):
    """Run the full pipeline at one location, return an outcome string."""
    ws = os.path.join(WORK, f"loc_{i:02d}")
    # ---- step 1: refine + build + run GWF (may Triangle-abort or SIGILL) ----
    try:
        res = mio.build_refined_gwf_model(
            cgwf, boundary_gdf=boundary_gdf, river_gdf=river_gdf,
            refine_points=[(px, py)], head_array=heads, workspace=ws,
            refine_radius=REFINE_RADIUS, base_cell_size=BASE_CS,
            refined_cell_size=REFINED_CS, sim_name="limmat_ref")
    except subprocess.CalledProcessError:
        return "TRIANGLE_PRECISION_ABORT", None
    except RuntimeError:
        rc, sig = mf6_returncode(ws)
        if rc in (-4, 132) or sig:
            return "SIGILL_exit132_GWF", None
        return f"GWF_FAIL_rc={rc}", None
    except Exception as e:
        return f"OTHER_gridbuild:{type(e).__name__}", None

    # ---- step 2: attach GWT and run (may SIGILL during transport) ----
    rgwf = res["gwf"]; gp = res["gridprops"]; ncpl = res["ncpl"]; mgr = res["modelgrid"]
    xr, yr = np.array(mgr.xcellcenters), np.array(mgr.ycellcenters)
    scell = int(np.argmin((xr - px) ** 2 + (yr - py) ** 2))
    try:
        ok = add_gwt_and_run(res["sim"], "limmat_ref", gp, ncpl, scell,
                             rgwf.disv.top.array, rgwf.disv.botm.array)
    except Exception as e:
        return f"OTHER_gwt:{type(e).__name__}", ncpl
    if not ok:
        rc, sig = mf6_returncode(ws)
        if rc in (-4, 132) or sig:
            return "SIGILL_exit132_GWT", ncpl
        return f"GWT_FAIL_rc={rc}", ncpl

    # ---- sanity: did concentration actually move? ----
    try:
        conc = res["sim"].get_model("trans").output.concentration().get_data()[0, 0]
        c = conc.copy(); c[c < 0] = 0
        spread = int((c > 0.01).sum())
        return ("CLEAN", ncpl) if spread > 1 else ("CLEAN_NO_PLUME", ncpl)
    except Exception:
        return "CLEAN_NO_OUTPUT", ncpl

# --------------------------------------------------------------------------
banner(f"SWEEP: {len(sel)} locations  x  (refine cs={REFINED_CS} -> GWF -> GWT)")
results = []
t0 = time.time()
for i, (px, py) in enumerate(sel):
    ts = time.time()
    outcome = classify(i, float(px), float(py))
    if isinstance(outcome, tuple):
        outcome, ncpl = outcome
    else:
        ncpl = None
    results.append((i, float(px), float(py), outcome, ncpl))
    print(f"  [{i+1:2d}/{len(sel)}] ({px:9.0f},{py:9.0f})  ncpl={str(ncpl):>5}  "
          f"-> {outcome:<24} ({time.time()-ts:4.0f}s)", flush=True)

# --------------------------------------------------------------------------
banner("SUMMARY")
clean = sum(1 for r in results if r[3].startswith("CLEAN") and "NO_PLUME" not in r[3])
sigill = sum(1 for r in results if r[3].startswith("SIGILL"))
tri = sum(1 for r in results if r[3] == "TRIANGLE_PRECISION_ABORT")
other = len(results) - clean - sigill - tri
n = len(results)
print(f"  {'loc':>3} {'x':>10} {'y':>10} {'ncpl':>6}  outcome")
for i, px, py, oc, ncpl in results:
    print(f"  {i:>3} {px:>10.0f} {py:>10.0f} {str(ncpl):>6}  {oc}")
print(f"\n  clean runs ...................... {clean}/{n}")
print(f"  SIGILL / exit-132 crashes ....... {sigill}/{n}")
print(f"  Triangle precision aborts ....... {tri}/{n}")
print(f"  other failures .................. {other}/{n}")
print(f"  total sweep time ................ {time.time()-t0:.0f} s")

rate = clean / n if n else 0.0
reliable = (clean == n)
banner("VERDICT")
if reliable:
    print(f"  cs={REFINED_CS:.0f} GWT refinement is RELIABLE on THIS platform "
          f"({clean}/{n} locations clean, success rate {rate*100:.0f}%).")
else:
    print(f"  cs={REFINED_CS:.0f} GWT refinement is UNRELIABLE on THIS platform "
          f"({clean}/{n} locations clean, success rate {rate*100:.0f}%; "
          f"{sigill} SIGILL, {tri} Triangle abort, {other} other).")
    print(f"  -> Student free-choice of source location is UNSAFE here; pin a")
    print(f"     validated location or auto-retry with a jittered refine polygon.")
print("=" * 78)
