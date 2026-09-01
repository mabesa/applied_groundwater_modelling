"""T2 S13 -- operator A (observation-support robustness). Post-processing, 0 solves."""
import sys, os, json, glob
sys.path.insert(0, "_SUPPORT/src")
import numpy as np, flopy
import transport_operator_a as opa
import transport_srcpulse_demo as tsd

CENTER = tsd.ABS_XY          # the receptor: the extraction well
RUNS = [
    ("spatial_10m_cr0.9", 10.0, "/Users/bea/agm_t2_10m/spatial_10m_cr0.9"),
    ("spatial_5m_cr0.9",   5.0, "/Users/bea/agm_t2_s10/spatial_5m_cr0.9"),
    ("spatial_2m_cr0.9",   2.0, "/Users/bea/agm_t2_s11/spatial_2m_cr0.9"),
    ("bcontrol_coarse",   10.0, "/Users/bea/agm_t2_bc/bcontrol_coarse"),
    ("bcontrol_fine",      2.0, "/Users/bea/agm_t2_fix/bcontrol_fine"),
]

def one(identity, cell_size, ws):
    simdirs = sorted(glob.glob(os.path.join(ws, "sim_*", "sim")))
    if not simdirs:
        return {"identity": identity, "status": "no_sim_dir"}
    sim = flopy.mf6.MFSimulation.load(sim_ws=simdirs[-1], verbosity_level=0)
    gwf = sim.get_model([m for m in sim.model_names if "gwt" not in m.lower()][0])
    gwt = sim.get_model([m for m in sim.model_names if "gwt" in m.lower()][0])
    mg = gwf.modelgrid
    ncpl = mg.ncpl if np.isscalar(mg.ncpl) else int(np.ravel(mg.ncpl)[0])
    polys = opa.cell_polygons_from_modelgrid(mg, ncpl)
    heads = gwf.output.head().get_data().ravel()[:ncpl]
    top = np.ravel(gwf.dis.top.array if hasattr(gwf, "dis") else gwf.disv.top.array)[:ncpl]
    botm = np.ravel(gwf.disv.botm.array)[:ncpl]
    cobj = gwt.output.concentration()
    times = list(cobj.get_times())
    getc = opa.get_concentration_reader(cobj)
    rec = opa.compute_operator_a(
        cell_polygons=polys, heads=heads, top=top, botm=botm,
        porosity=tsd.LOCKED_PARAMS["porosity"],
        get_concentration=getc, times=times,
        cell_size_m=cell_size, center_xy=CENTER)
    out = {"identity": identity, "cell_size_m": cell_size, "status": rec.status}
    if rec.status == "computed":
        vals = np.asarray(rec.values, float)
        out["A_peak_mgL"] = float(vals.max())
        out["A_t_peak_d"] = float(np.asarray(rec.times, float)[int(vals.argmax())])
    else:
        out["reason"] = rec.reason
    return out

if __name__ == "__main__":
    res = []
    for ident, cs, ws in RUNS:
        try:
            r = one(ident, cs, ws)
        except Exception as e:
            r = {"identity": ident, "status": "error", "error": f"{type(e).__name__}: {str(e)[:200]}"}
        res.append(r); print("RESULT " + json.dumps(r), flush=True)
        json.dump(res, open(sys.argv[1], "w"), indent=1)
