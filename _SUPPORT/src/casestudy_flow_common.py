#!/usr/bin/env python
"""
================================================================================
 M2a case-study FLOW — shared build primitives + NEUTRAL flow-package factory
================================================================================

Shared, builder/generator-agnostic primitives for the case-study flow track
(M2a). Extracted from ``casestudy_flow_golden.py`` (M2a.0) so BOTH the golden
generator (provenance tooling) AND the reusable builder
(``casestudy_flow_builder.py``, M2a.1) build the SAME corridor-refined steady
baseline from ONE code path -- the committed golden then pins that path.

Neither the generator nor the builder imports the other; both import this.

Contents
--------
* ``baseline_well_data(cgwf)`` -- coarse WEL -> (x, y, rate) tuples (238
  background wells, sign preserved), the no-doublet well_data.
* ``canonicalize_wel_entries(cellid, rate)`` -- deterministic duplicate-cellid
  aggregation (sum) + sort, so the frozen WEL is semantically identical to
  what MF6 solves and order-independent.
* ``group_refine_points(group)`` -- the corridor refine anchors (the group's
  injection/extraction doublet coords) from ``case_config_transport.yaml``.
* ``load_coarse_model`` / ``load_gis`` -- load the 05f-calibrated GWF + the
  Limmat/Sihl river + boundary geometry.
* ``refine_baseline_grid(...)`` -- generate_refined_grid(well_data=background)
  + canonicalize WEL (the DEFECTIVE-RIV refined spec; grid identity).
* ``apply_faithful_riv(spec, cgwf, river_gdf)`` -- REPLACE the defective RIV
  with the conservation-exact faithful transfer (case-study addendum); the
  golden generator applies it AFTER its determinism gate, the builder applies
  it inline via ``build_baseline_spec``.
* ``build_baseline_spec(...)`` -- refine_baseline_grid + apply_faithful_riv:
  the single-shot "baseline spec" the builder uses (minus the generator's
  freeze/validate/determinism machinery).
* ``assemble_flow_state(spec, *, ...)`` -- the NEUTRAL flow-package factory:
  EXPLICIT controls (model/package names, OC output filenames, IMS
  tolerances, WEL sign convention, save flags, deterministic package order),
  no transport defaults leak. Baseline reproduces
  ``model_io_utils.assemble_gwf_from_spec`` exactly (same packages/settings ->
  identical heads); ``extra_wells`` is the seam M2a.2 uses to add the doublet.
* ``spec_canonical_hashes(spec)`` -- the primary-oracle canonical package
  hashes (aggregate + per-member), computed WITHOUT writing a file, so the
  builder can compare its spec to the committed golden's ``array_hashes`` /
  ``aggregate_hash``.

`uv run` for everything (see CLAUDE.md).
================================================================================
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import model_io_utils as mio
import casestudy_refine_riv as crr

Group = Any

# The pinned corridor refine radius for the baseline (RETRY_RADII[0]); group 0
# is SIGILL-free + deterministic at this radius (see M2a.0). The golden froze
# radius 70; the builder uses the same so its spec is byte-identical.
BASELINE_REFINE_RADIUS = 70.0

# Corridor refine-radius walk (mirrors model_io_utils.refine_with_retry /
# jupyterhub_refine_reliability_gen.RETRY_RADII) -- the builder walks these to
# dodge a Triangle abort (a PYTHON exception; a fatal SIGILL still needs
# subprocess isolation by the caller). Group 0 succeeds at the first radius.
REFINE_RADII = (70.0, 62.0, 78.0, 56.0, 84.0)

# The geothermal doublet magnitude PER WELL (m3/d): 3000 l/min x 1.44 =
# licensed-max extraction, balanced reinjection (net-zero doublet). MF6 sign
# convention: injection +Q, extraction -Q; the 50% sensitivity uses 0.5*Q.
DOUBLET_Q_M3D = 4320.0

# Fine-corridor cell-size threshold (m): the doublet must sit in the
# well-resolved (~10 m) corridor the grid was refined for, NOT the ~50 m base
# region. Mirrors casestudy_flow_golden.UNREFINED_CELLSIZE_THRESHOLD_M (kept
# here so the builder need not import the golden generator -- independence).
CORRIDOR_CELLSIZE_THRESHOLD_M = 30.0

# mf6 executable resolution (PATH, else the flopy-managed bin location) --
# mirrors transport_srcpulse_demo's pattern so a real solve works whether or
# not mf6 is on PATH.
_MF6_FALLBACK = str(Path("~/.local/share/flopy/bin/mf6").expanduser())


def resolve_mf6_exe() -> str:
    """Return the mf6 executable path: ``shutil.which('mf6')`` if on PATH,
    else the flopy-managed bin fallback."""
    return shutil.which("mf6") or _MF6_FALLBACK


# =============================================================================
# Coarse model + GIS loaders.
# =============================================================================
def load_coarse_model(mother_model):
    """Load the 05f-calibrated MF6 simulation; return ``(sim, gwf)`` for the
    ``limmat_valley`` model."""
    import flopy

    sim = flopy.mf6.MFSimulation.load(sim_ws=str(mother_model), verbosity_level=0)
    gwf = sim.get_model("limmat_valley")
    return sim, gwf


def load_gis(mother_model):
    """Load the model boundary polygon + the Limmat/Sihl river geometry
    (clipped to the boundary) from ``<mother_model>/../gis``."""
    import geopandas as gpd

    gis_dir = Path(mother_model).parent / "gis"
    boundary_gdf = gpd.read_file(gis_dir / "limmat_model_boundary.gpkg")
    river_all = gpd.read_file(gis_dir / "AV_Gewasser_-OGD.gpkg")
    river_gdf = river_all[
        river_all["GEWAESSERNAME"].isin(["Limmat", "Sihl"])
        & river_all.intersects(boundary_gdf.geometry.iloc[0])
    ]
    return boundary_gdf, river_gdf


def group_refine_points(group: Group, *, config_path: Any = None) -> List[Tuple[float, float]]:
    """Corridor refine anchors for *group* = its configured injection/
    extraction doublet coords (from ``case_config_transport.yaml``). Pure
    config lookup -- no MODFLOW, no subprocess -- so reruns are reproducible.
    """
    import case_utils as cu

    doublet = cu.lint_transport_config(config_path=config_path, groups=[group])[group]["doublet"]
    return [
        (float(doublet["injection_easting"]), float(doublet["injection_northing"])),
        (float(doublet["extraction_easting"]), float(doublet["extraction_northing"])),
    ]


# =============================================================================
# WEL primitives.
# =============================================================================
def baseline_well_data(cgwf) -> List[Tuple[float, float, float]]:
    """Extract the coarse (05f-calibrated) model's WEL package as
    ``(centroid_x, centroid_y, rate)`` coordinate tuples, sign preserved --
    the "no doublet, background wells only" well_data.

    Raises ``ValueError`` if *cgwf* has no WEL package or an empty period 0.
    """
    wel = cgwf.get_package("WEL")
    if wel is None:
        raise ValueError(
            "coarse (05f-calibrated) model has no WEL package -- cannot "
            "build baseline_well_data for the no-doublet baseline"
        )
    spd = wel.stress_period_data.get_data(0)
    if spd is None or len(spd) == 0:
        raise ValueError("coarse WEL package has no stress_period_data for period 0")

    modelgrid = cgwf.modelgrid
    xc = modelgrid.xcellcenters
    yc = modelgrid.ycellcenters
    wells: List[Tuple[float, float, float]] = []
    for rec in spd:
        flat = mio._cellid_to_flat(rec["cellid"])
        wells.append((float(xc[flat]), float(yc[flat]), float(rec["q"])))
    return wells


def canonicalize_wel_entries(
    wel_cellid: List[Tuple[int, int]], wel_rate: List[float]
) -> Tuple[List[Tuple[int, int]], List[float]]:
    """Deterministically canonicalize a refined WEL spec's ``(cellid, rate)``
    entries: aggregate (sum) any entries mapped to the SAME refined cell, then
    sort by cellid. Makes the frozen WEL semantically identical to what MF6
    solves (MF6 sums duplicate list entries) AND order-independent (stable
    hash across reruns). ``len(result) <= len(wel_cellid)``.
    """
    # Bucket every rate per cell, then sum with math.fsum over a DETERMINISTIC
    # (sorted) order so the result is order-independent to the last bit (the
    # dict insertion / caller order can never perturb the summed rate or the
    # frozen hash -- same fix pattern as casestudy_refine_riv's split).
    buckets: Dict[Tuple[int, int], List[float]] = {}
    for cid, rate in zip(wel_cellid, wel_rate):
        buckets.setdefault((int(cid[0]), int(cid[1])), []).append(float(rate))
    ordered = sorted(buckets)
    return ordered, [math.fsum(buckets[k]) for k in ordered]


# =============================================================================
# Faithful RIV re-transfer (case-study addendum).
# =============================================================================
def apply_faithful_riv(
    spec: Dict[str, Any], cgwf, river_gdf,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return ``(new_spec, info)`` -- a copy of *spec* with its RIV package
    REPLACED by the faithful (area-weighted, per-reach, conductance-conserving)
    transfer from the coarse calibrated RIV.

    The refined ``botm`` is passed to the transfer so its OVERBANK FILTER is
    active (a reach's conductance is split only among refined cells that can
    host the river bed, ``botm <= rbot``); ``botm`` is left unchanged (no
    floor hack). ``info`` carries the faithful-RIV hash + coverage/overbank
    diagnostics (the M3 guard).
    """
    coarse_reaches = crr.build_coarse_riv_reaches(cgwf)
    coarse_cond = float(sum(r.cond for r in coarse_reaches))
    records, stats = crr.faithful_riv_from_coarse(
        spec["gridprops"], spec["idomain"], coarse_reaches, river_gdf,
        crs=spec.get("crs"), refined_botm=spec["botm"], return_stats=True,
    )

    # COVERAGE INVARIANT: every coarse RIV reach must be represented.
    if not (stats["n_reaches_placed"] == stats["n_source_reaches"] == len(coarse_reaches)):
        raise ValueError(
            f"faithful RIV coverage: {stats['n_reaches_placed']} placed vs "
            f"{stats['n_source_reaches']} source vs {len(coarse_reaches)} "
            "coarse reaches -- not every coarse RIV reach was represented"
        )

    new = dict(spec)
    new["riv_cellid"] = [r[0] for r in records]
    new["riv_stage"] = [float(r[1]) for r in records]
    new["riv_cond"] = [float(r[2]) for r in records]
    new["riv_rbot"] = [float(r[3]) for r in records]
    new["botm"] = np.array(spec["botm"], dtype=float)  # unchanged (no floor)

    botm = new["botm"]
    n_bad = sum(1 for (_l, j), _s, _c, rbot in records if rbot < botm[int(j)])
    if n_bad:
        raise ValueError(
            f"faithful RIV: {n_bad} record(s) have rbot < refined cell botm "
            "despite the overbank filter (internal invariant violated)"
        )

    info = {
        "primitive": stats["primitive"],
        "records": records,
        "hash": crr.riv_records_hash(records),
        "coarse_cond": coarse_cond,
        "refined_cond": crr.total_conductance(records),
        "n_records": len(records),
        "n_cells": len({int(c[1]) for c, _, _, _ in records}),
        "coverage_reaches_placed": stats["n_reaches_placed"],
        "coverage_source_reaches": stats["n_source_reaches"],
        "min_retained_weight_ratio": stats["min_retained_weight_ratio"],
        "reaches_below_warn_ratio": stats["reaches_below_warn_ratio"],
    }
    return new, info


# =============================================================================
# Baseline spec builders.
# =============================================================================
def refine_baseline_grid(
    cgwf, boundary_gdf, river_gdf, refine_points, coarse_heads,
    *, refine_radius: float, wells: Optional[List[Tuple[float, float, float]]] = None,
) -> Dict[str, Any]:
    """Build the corridor-refined DISV spec with the background wells
    installed + canonicalized -- i.e. ``generate_refined_grid`` (with the 238
    background wells as ``well_data``) followed by ``canonicalize_wel_entries``.

    This is the GRID-IDENTITY spec (still the DEFECTIVE centroid-in-polygon
    RIV; ``apply_faithful_riv`` replaces that). *wells* defaults to
    ``baseline_well_data(cgwf)``.
    """
    if wells is None:
        wells = baseline_well_data(cgwf)
    spec = mio.generate_refined_grid(
        cgwf, boundary_gdf=boundary_gdf, river_gdf=river_gdf,
        refine_points=refine_points, head_array=coarse_heads,
        refine_radius=refine_radius, well_data=wells,
    )
    cellids, rates = canonicalize_wel_entries(spec["wel_cellid"], spec["wel_rate"])
    spec["wel_cellid"] = cellids
    spec["wel_rate"] = rates
    spec["well_cells"] = sorted({int(c[1]) for c in cellids})
    return spec


def build_baseline_spec(
    cgwf, boundary_gdf, river_gdf, refine_points, coarse_heads,
    *, refine_radius: float = BASELINE_REFINE_RADIUS,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Single-shot baseline spec: ``refine_baseline_grid`` (background wells +
    canonicalized WEL) then ``apply_faithful_riv`` (faithful river). Returns
    ``(spec, riv_info)``. This is the builder's path; it produces the SAME
    spec the golden froze (both use these shared primitives).
    """
    spec = refine_baseline_grid(
        cgwf, boundary_gdf, river_gdf, refine_points, coarse_heads,
        refine_radius=refine_radius,
    )
    spec, riv_info = apply_faithful_riv(spec, cgwf, river_gdf)
    return spec, riv_info


# =============================================================================
# Well placement + WEL budget (state (ii) doublet, M2a.2).
# =============================================================================
def refined_cell_sizes(spec: Dict[str, Any]) -> np.ndarray:
    """Per-cell 'linear size' proxy (sqrt(polygon area)) for the refined DISV
    grid -- corridor (~10 m) vs base (~50 m) region discriminator."""
    polys = crr.refined_cell_polygons(spec["gridprops"])
    return np.sqrt(np.array([p.area for p in polys], dtype=float))


def resolve_well_cell(E: float, N: float, modelgrid, idomain) -> int:
    """Map coordinate ``(E, N)`` to the flat icell of the NEAREST ACTIVE
    refined cell.

    PRECONDITION (asserted): *idomain* is ALL-ACTIVE. ``generate_refined_grid``
    places the background wells by the nearest UNMASKED cell centroid
    (``np.argmin`` over every cell, no active filter -- model_io_utils.py) and
    emits an all-ones idomain. Requiring all-active here makes
    nearest-active == nearest-unmasked, so the doublet is placed by the SAME
    mapping as the background wells -- a checked precondition, not a claim that
    happens to hold. (A future partially-masked refined grid must revisit this,
    because then the two mappings would genuinely differ.)
    """
    xc = np.asarray(modelgrid.xcellcenters).reshape(-1)
    yc = np.asarray(modelgrid.ycellcenters).reshape(-1)
    idom = np.asarray(idomain).reshape(-1)
    if not np.all(idom != 0):
        raise ValueError(
            "resolve_well_cell requires an ALL-ACTIVE idomain (so nearest-active "
            "== nearest-unmasked == generate_refined_grid's background-well "
            f"mapping); {int(np.count_nonzero(idom == 0))} inactive cell(s) found"
        )
    d2 = (xc - E) ** 2 + (yc - N) ** 2
    return int(np.argmin(d2))


def _containing_cells(E: float, N: float, polys) -> List[int]:
    """Flat indices of every refined cell polygon that COVERS ``(E, N)``
    (contains it, boundary included). One cell for a strictly-interior point;
    2+ only if the point sits exactly on a shared edge."""
    from shapely.geometry import Point as _Point

    pt = _Point(E, N)
    return [i for i, p in enumerate(polys) if p.covers(pt)]


def resolve_doublet_cells(
    spec: Dict[str, Any], modelgrid, refine_points,
    *, corridor_threshold: float = CORRIDOR_CELLSIZE_THRESHOLD_M,
) -> Dict[str, Dict[str, Any]]:
    """Resolve + VALIDATE the group's doublet (injection, extraction) cells
    against the ACTUAL built grid (single canonical mapper, cross-checked
    against the containing cell). *refine_points* is ``[(inj_E, inj_N),
    (ext_E, ext_N)]`` (from ``group_refine_points``).

    For each role:
      * resolve via ``resolve_well_cell`` (nearest ACTIVE) AND independently
        via containing-cell (shapely covers over ``refined_cell_polygons``);
        require **UNIQUE** agreement -- ``len(containing) == 1`` AND that one
        cell == the nearest cell. An ambiguous containment (a point exactly on
        a shared edge/vertex -> ``containing`` has 2+) OR a disagreement is a
        real placement ambiguity (the doublet could land on the wrong side of
        the edge) and FAILS, naming role/cell/coords -- never silently resolved;
      * validate: cell ACTIVE, NOT a CHD/RIV cell of THIS model, and in the
        FINE corridor (``cellsize < corridor_threshold``).

    Returns ``{"injection": {...}, "extraction": {...}}`` with ``cell``,
    ``E``, ``N``, ``cellsize_m`` per role. Raises ``ValueError`` on any
    placement/validation failure. Requires an all-active idomain (see
    ``resolve_well_cell``).
    """
    idomain = np.asarray(spec["idomain"]).reshape(-1)
    if not np.all(idomain != 0):
        raise ValueError(
            "resolve_doublet_cells requires an ALL-ACTIVE idomain (so the "
            "doublet uses the SAME mapping as the background wells); "
            f"{int(np.count_nonzero(idomain == 0))} inactive cell(s) found"
        )
    polys = crr.refined_cell_polygons(spec["gridprops"])
    cellsize = refined_cell_sizes(spec)
    chd = {int(c[1]) for c in spec["chd_cellid"]}
    rivc = {int(c[1]) for c in spec["riv_cellid"]}

    if len(refine_points) != 2:
        raise ValueError(f"resolve_doublet_cells expects 2 refine points, got {len(refine_points)}")

    out: Dict[str, Dict[str, Any]] = {}
    for role, (E, N) in zip(("injection", "extraction"), refine_points):
        nn = resolve_well_cell(E, N, modelgrid, idomain)
        containing = _containing_cells(E, N, polys)
        # UNIQUE agreement: exactly one containing cell, and it is the nearest.
        if len(containing) != 1 or containing[0] != nn:
            raise ValueError(
                f"doublet placement ambiguity ({role}) at ({E:.2f}, {N:.2f}): "
                f"nearest cell {nn}, containing cells {containing}. Require a "
                "UNIQUE containing cell equal to the nearest cell; an on-edge / "
                "on-vertex or disagreeing placement is refused (the doublet "
                "could land on the wrong side of the edge)."
            )
        if idomain[nn] == 0:
            raise ValueError(f"doublet {role} cell {nn} is INACTIVE (idomain=0) at ({E:.2f},{N:.2f})")
        if nn in chd:
            raise ValueError(f"doublet {role} cell {nn} is a CHD cell of this model -- cannot place a well there")
        if nn in rivc:
            raise ValueError(f"doublet {role} cell {nn} is a RIV cell of this model -- cannot place a well there")
        if cellsize[nn] >= corridor_threshold:
            raise ValueError(
                f"doublet {role} cell {nn} cellsize {cellsize[nn]:.1f} m is not "
                f"in the FINE corridor (< {corridor_threshold} m) -- the doublet "
                "must sit in the well-resolved refined zone"
            )
        out[role] = {"cell": int(nn), "E": float(E), "N": float(N), "cellsize_m": float(cellsize[nn])}
    return out


def wel_flux_by_cell(gwf) -> Dict[int, float]:
    """Sum the solved WEL package flux (m3/d) per flat icell from a solved
    GWF model's budget. DISV WEL budget records carry a 1-based ``node``
    (or a ``cellid``); this returns ``{icell: total_q}``.
    """
    from collections import defaultdict

    bud = gwf.output.budget()
    recs = bud.get_data(text="WEL", totim=bud.get_times()[-1])
    out: Dict[int, float] = defaultdict(float)
    if recs:
        rec = recs[0]
        names = rec.dtype.names
        for r in rec:
            if "node" in names:
                icell = int(r["node"]) - 1
            elif "cellid" in names:
                cid = r["cellid"]
                icell = int(cid[-1]) if hasattr(cid, "__len__") else int(cid)
            else:
                raise ValueError(f"WEL budget record has no node/cellid field: {names}")
            out[icell] += float(r["q"])
    return dict(out)


# =============================================================================
# NEUTRAL flow-package factory.
# =============================================================================
# Deterministic package build order (no transport defaults; explicit).
FLOW_PACKAGE_ORDER = ("TDIS", "IMS", "GWF", "DISV", "NPF", "IC", "RCHA", "CHD", "RIV", "WEL", "OC")
FLOW_TIME_UNITS = "DAYS"
FLOW_LENGTH_UNITS = "meters"


def assemble_flow_state(
    spec: Dict[str, Any],
    *,
    workspace,
    sim_name: str = "flow_state",
    model_name: Optional[str] = None,
    head_filename: Optional[str] = None,
    budget_filename: Optional[str] = None,
    ims_options: Optional[Dict[str, Any]] = None,
    newtonoptions: str = mio.GWF_NEWTON_OPTIONS,
    npf_icelltype: int = 1,
    save_specific_discharge: bool = True,
    save_saturation: bool = True,
    save_flows: bool = True,
    extra_wells: Optional[List[Tuple[Any, float]]] = None,
    exe_name: Optional[str] = None,
    run: bool = True,
    raise_on_failure: bool = True,
) -> Dict[str, Any]:
    """NEUTRAL flow-package factory: assemble (and optionally solve) a steady
    single-layer DISV GWF model from *spec* with EXPLICIT controls and NO
    transport defaults leaking in.

    Steady flow is fixed here (TDIS nper=1, perioddata ``[(1.0, 1, 1)]``,
    time_units DAYS). Everything else is an explicit parameter:

    * ``sim_name`` / ``model_name`` (model name defaults to ``sim_name``);
    * ``head_filename`` / ``budget_filename`` (default ``<sim_name>.hds`` /
      ``.cbc``) -- the OC output file names M3 binds to;
    * ``ims_options`` (default the course NEWTON policy
      ``model_io_utils.GWF_NEWTON_IMS_OPTIONS``) + ``newtonoptions``;
    * NPF ``icelltype`` + the three save flags
      (heads/budget via OC + specific-discharge + saturation);
    * ``extra_wells`` -- additional WEL entries appended to the spec's
      background WEL (the seam M2a.2 uses to add the doublet). SIGN
      CONVENTION (MF6): a POSITIVE rate is INJECTION into the aquifer, a
      NEGATIVE rate is EXTRACTION -- so the geothermal doublet is
      ``injection +Q`` / ``extraction -Q``. Each entry is
      ``((layer, icell), rate)``.
    * aux-field / boundname policy: NONE (no aux vars, no boundnames) --
      explicit, so no transport aux leaks into the flow WEL/RIV/CHD.
    * ``raise_on_failure`` (default True): raise ``RuntimeError`` if the MF6
      run does not converge -- matching the fail-loud behaviour of the
      former ``model_io_utils.assemble_gwf_from_spec`` so the golden
      generator (which now uses THIS assembler) still aborts on a bad solve.
      Set False (as the builder does) to inspect ``converged`` and emit a
      diagnostic instead.

    Packages are always built in :data:`FLOW_PACKAGE_ORDER`. Baseline
    (``extra_wells=None`` + default knobs) reproduces
    ``model_io_utils.assemble_gwf_from_spec`` exactly, so the solved heads are
    identical.

    When ``extra_wells`` are supplied, the COMBINED WEL (spec background +
    extras) is re-canonicalized via :func:`canonicalize_wel_entries` (a
    doublet cell that coincides with a background cell is summed into a single
    entry -- what MF6 does anyway), and the returned ``well_cells`` reflects
    the combined set. Baseline (``extra_wells=None``) leaves the spec's WEL
    untouched, so it stays byte-identical.

    Returns a dict with ``sim``, ``gwf``, ``modelgrid``, ``gridprops``,
    ``ncpl``, ``heads`` (None if the run did not converge), ``well_cells``
    (combined when ``extra_wells``), ``wel_cellid`` / ``wel_rate`` (the WEL
    actually installed), ``converged`` (bool), ``headfile``, ``budgetfile``
    (absolute paths), ``model_name``, ``sim_name``.
    """
    import flopy

    mio.validate_flow_spec(spec)

    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    model_name = model_name or sim_name
    head_filename = head_filename or f"{sim_name}.hds"
    budget_filename = budget_filename or f"{sim_name}.cbc"
    ims_options = dict(mio.GWF_NEWTON_IMS_OPTIONS if ims_options is None else ims_options)
    exe_name = exe_name or resolve_mf6_exe()
    gridprops = spec["gridprops"]
    ncpl = spec["ncpl"]

    # --- TDIS / IMS / GWF -------------------------------------------------
    sim = flopy.mf6.MFSimulation(sim_name=sim_name, exe_name=exe_name, sim_ws=str(workspace))
    flopy.mf6.ModflowTdis(sim, time_units=FLOW_TIME_UNITS, nper=1, perioddata=[(1.0, 1, 1)])
    flopy.mf6.ModflowIms(sim, **ims_options)
    gwf = flopy.mf6.ModflowGwf(
        sim, modelname=model_name, save_flows=save_flows, newtonoptions=newtonoptions,
    )

    # --- DISV / NPF / IC / RCHA ------------------------------------------
    flopy.mf6.ModflowGwfdisv(
        gwf, nlay=1, ncpl=ncpl, nvert=gridprops["nvert"],
        top=spec["top"], botm=[spec["botm"]], idomain=[spec["idomain"]],
        vertices=gridprops["vertices"], cell2d=gridprops["cell2d"],
    )
    flopy.mf6.ModflowGwfnpf(
        gwf, icelltype=npf_icelltype, k=spec["k"], save_flows=save_flows,
        save_specific_discharge=save_specific_discharge, save_saturation=save_saturation,
    )
    flopy.mf6.ModflowGwfic(gwf, strt=spec["strt"])
    flopy.mf6.ModflowGwfrcha(gwf, recharge=spec["rch"])

    # --- CHD / RIV / WEL (from frozen arrays; no aux, no boundnames) ------
    flopy.mf6.ModflowGwfchd(gwf, stress_period_data=list(zip(spec["chd_cellid"], spec["chd_head"])))
    flopy.mf6.ModflowGwfriv(
        gwf, stress_period_data=list(zip(
            spec["riv_cellid"], spec["riv_stage"], spec["riv_cond"], spec["riv_rbot"],
        )),
    )
    # WEL: baseline uses the spec's (already canonical) background WEL as-is
    # (byte-identical). When extra_wells (e.g. the M2a.2 doublet) are added,
    # re-canonicalize the COMBINED set so a doublet cell that coincides with a
    # background cell is summed into one entry and well_cells/metadata reflect
    # the combined WEL (not just the background).
    if extra_wells:
        combined_cellid = list(spec["wel_cellid"]) + [
            tuple(int(x) for x in cellid) for cellid, _rate in extra_wells
        ]
        combined_rate = list(spec["wel_rate"]) + [float(rate) for _cellid, rate in extra_wells]
        wel_cellid, wel_rate = canonicalize_wel_entries(combined_cellid, combined_rate)
        well_cells = sorted({int(c[1]) for c in wel_cellid})
    else:
        wel_cellid = list(spec["wel_cellid"])
        wel_rate = list(spec["wel_rate"])
        well_cells = spec["well_cells"]
    if wel_cellid:
        flopy.mf6.ModflowGwfwel(gwf, stress_period_data=list(zip(wel_cellid, wel_rate)))

    # --- OC ---------------------------------------------------------------
    flopy.mf6.ModflowGwfoc(
        gwf,
        head_filerecord=[head_filename],
        budget_filerecord=[budget_filename],
        saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")],
    )

    result: Dict[str, Any] = {
        "sim": sim,
        "gwf": gwf,
        "modelgrid": gwf.modelgrid,
        "gridprops": gridprops,
        "ncpl": ncpl,
        "well_cells": well_cells,
        "wel_cellid": wel_cellid,
        "wel_rate": wel_rate,
        "model_name": model_name,
        "sim_name": sim_name,
        "headfile": str((workspace / head_filename).resolve()),
        "budgetfile": str((workspace / budget_filename).resolve()),
        "converged": None,
        "heads": None,
    }

    if not run:
        sim.write_simulation()
        return result

    sim.write_simulation()
    success, _ = sim.run_simulation(silent=True)
    result["converged"] = bool(success)
    if not success:
        if raise_on_failure:
            raise RuntimeError(
                f"assemble_flow_state: MF6 model {model_name!r} failed to "
                f"converge -- check the listing file in {workspace}"
            )
        return result
    heads = gwf.output.head().get_data().flatten()
    crs = spec.get("crs")
    if crs is not None:
        gwf.modelgrid.set_coord_info(crs=crs)
    result["heads"] = heads
    return result


# =============================================================================
# Canonical package hashes (primary oracle) -- without writing a file.
# =============================================================================
def spec_canonical_hashes(spec: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    """Return ``(aggregate_hash, array_hashes)`` for *spec*, computed over the
    SAME encoded npz members ``freeze_flow_spec`` would write -- so the result
    equals a frozen manifest's ``aggregate_hash`` / ``array_hashes`` WITHOUT
    touching the filesystem. The primary (platform-independent) oracle.
    """
    import case_artifact_lock as cal

    arrays = mio._encode_flow_spec_for_npz(spec)
    array_hashes = {name: cal.hash_array(arr) for name, arr in arrays.items()}
    members = sorted(array_hashes)
    aggregate = cal._fold_aggregate(members, array_hashes)
    return aggregate, array_hashes
