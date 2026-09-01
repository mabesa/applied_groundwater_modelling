"""Why do the coarse identities under-resolve? Measure the floor's effect."""
import sys, glob, numpy as np
sys.path.insert(0, "_SUPPORT/src")
import flopy, transport_srcpulse_demo as tsd

WS = {50.0: "/Users/bea/agm_t2_s14/spatial_50m_cr0.9",
      20.0: "/Users/bea/agm_t2_s14/spatial_20m_cr0.9",
      10.0: "/Users/bea/agm_t2_10m/spatial_10m_cr0.9",
       2.0: "/Users/bea/agm_t2_s11/spatial_2m_cr0.9"}

def field(ws):
    sim_ws = sorted(glob.glob(f"{ws}/sim_*/sim"))[-1]
    sim = flopy.mf6.MFSimulation.load(sim_ws=sim_ws, verbosity_level=0)
    gwf = sim.get_model([m for m in sim.model_names if "gwt" not in m.lower()][0])
    spd = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    v = np.sqrt(spd["qx"]**2 + spd["qy"]**2) / tsd.LOCKED_PARAMS["porosity"]
    mg = gwf.modelgrid
    ncpl = int(np.ravel(mg.ncpl)[0]) if not np.isscalar(mg.ncpl) else int(mg.ncpl)
    # nominal cell size = sqrt(area)
    from shapely.geometry import Polygon
    ds = np.array([np.sqrt(Polygon(mg.get_cell_vertices(i)).area) for i in range(ncpl)])
    return v[:ncpl], ds

print(f"  {'mesh':>6} {'cells':>6} {'ds min':>8} {'ds med':>8} {'exp_v1 floor':>13} "
      f"{'cells kept':>11} {'cells dropped':>14}")
for cell, ws in WS.items():
    v, ds = field(ws)
    floor = 0.4 * cell
    kept = ds >= floor
    print(f"  {cell:>6} {len(ds):>6} {ds.min():>8.2f} {np.median(ds):>8.2f} {floor:>13.1f} "
          f"{kept.sum():>11} {(~kept).sum():>14}")
    # what the max Courant ratio is over kept vs all
    r_all = np.nanmax(v/ds); r_kept = np.nanmax((v/ds)[kept]) if kept.any() else float('nan')
    print(f"         max v/ds  all cells {r_all:9.4f}   floor-kept only {r_kept:9.4f}"
          f"   ratio {r_all/r_kept:5.2f}x")
