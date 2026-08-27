"""Figure of the 1 m corridor-refined DISV mesh (42 071 cells)."""
import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle
from matplotlib.collections import PolyCollection
sys.path.insert(0, '_SUPPORT/src')
import transport_srcpulse_demo as tsd

CASE = sys.argv[1]; OUT = sys.argv[2]
cgwf, boundary, rivers, exe = tsd.load_limmat_flow()
g = tsd.refine_corridor(cgwf, boundary, rivers,
        mesh_spec=tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=1.0),)), case_ws=CASE)

mg   = g["modelgrid"]; csz = np.asarray(g["cellsize"], float)
xc, yc = np.asarray(g["xc"], float), np.asarray(g["yc"], float)
spill = g["spill_xy"]; inj, ext = tsd.INJ_XY, tsd.ABS_XY

# cell polygons straight from gridprops -- independent of flopy plotting helpers
verts = {v[0]: (v[1], v[2]) for v in g["gridprops"]["vertices"]}
polys = [[verts[i] for i in c[4:]] for c in g["gridprops"]["cell2d"]]

def panel(ax, xlim, ylim, lw, title, show_riv=True, ec="0.25"):
    pc = PolyCollection(polys, array=csz, cmap="viridis_r",
                        norm=LogNorm(vmin=max(csz[csz > 0].min(), 0.5), vmax=csz.max()),
                        edgecolors=ec, linewidths=lw)
    ax.add_collection(pc)
    try:
        boundary.boundary.plot(ax=ax, color="k", lw=1.4, zorder=5)
        if show_riv: rivers.plot(ax=ax, color="#1f6feb", lw=1.6, zorder=6)
    except Exception: pass
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect("equal")
    ax.set_title(title, fontsize=11, pad=6)
    ax.tick_params(labelsize=7)
    return pc

fig = plt.figure(figsize=(15.5, 6.4))
gs  = fig.add_gridspec(1, 3, width_ratios=[1.25, 1, 1], wspace=0.18)

# --- (a) whole model domain -------------------------------------------------
axa = fig.add_subplot(gs[0, 0])
vxy  = np.array(list(verts.values()), float)   # ragged on Voronoi -> use vertex table
xl = (vxy[:, 0].min(), vxy[:, 0].max()); yl = (vxy[:, 1].min(), vxy[:, 1].max())
pc = panel(axa, xl, yl, 0.03, "(a) Model domain — 42 071 cells", ec="0.45")
pad2 = 260
axa.add_patch(Rectangle((min(spill[0], ext[0]) - pad2, min(spill[1], ext[1]) - pad2),
                        abs(ext[0] - spill[0]) + 2*pad2, abs(ext[1] - spill[1]) + 2*pad2,
                        fill=False, ec="crimson", lw=1.8, zorder=10))
axa.set_ylabel("LV95 northing [m]", fontsize=9)

# --- (b) corridor -----------------------------------------------------------
axb = fig.add_subplot(gs[0, 1])
cx, cy = (spill[0] + ext[0]) / 2, (spill[1] + ext[1]) / 2
h = 300
panel(axb, (cx - h, cx + h), (cy - h*0.8, cy + h*0.8), 0.05,
      "(b) Refined corridor — graded 50 m \u2192 1 m", ec="0.55")
axb.add_patch(Rectangle((ext[0] - 45, ext[1] - 36), 90, 72,
                        fill=False, ec="crimson", lw=1.8, zorder=10))

# --- (c) extraction well close-up ------------------------------------------
axc = fig.add_subplot(gs[0, 2])
panel(axc, (ext[0] - 45, ext[0] + 45), (ext[1] - 36, ext[1] + 36), 0.32,
      "(c) Extraction well — individual 1 m cells", show_riv=False, ec="0.35")

for ax in (axa, axb, axc):
    ax.plot(*spill, marker="*", ms=15, mfc="#ffd400", mec="k", mew=1.1, zorder=12,
            label="spill source")
    ax.plot(*ext, marker="v", ms=10, mfc="#e5484d", mec="k", mew=1.0, zorder=12,
            label="extraction well")
    ax.plot(*inj, marker="^", ms=10, mfc="#3fb950", mec="k", mew=1.0, zorder=12,
            label="injection well")
    ax.set_xlabel("LV95 easting [m]", fontsize=9)

cb = fig.colorbar(pc, ax=[axa, axb, axc], fraction=0.022, pad=0.015)
cb.set_label("cell size [m]  (log scale)", fontsize=9); cb.ax.tick_params(labelsize=8)
axa.legend(loc="lower left", fontsize=8, framealpha=0.95)
fig.suptitle("Limmat valley transport model \u2014 1 m corridor-refined DISV mesh\n"
             "ncpl = 42 071   |   base 50 m \u2192 corridor 1 m   |   min cell 0.73 m   |   "
             "87.5 % of cells \u2264 1.5 m", fontsize=12, y=1.005)
fig.savefig(OUT, dpi=190, bbox_inches="tight", facecolor="white")
print("WROTE", OUT)
print("cell size: min %.2f m  median %.2f m  max %.1f m" % (csz[csz>0].min(), np.median(csz), csz.max()))
print("cells <=1.5 m: %d  (%.1f%% of mesh)" % ((csz<=1.5).sum(), 100*(csz<=1.5).mean()))
