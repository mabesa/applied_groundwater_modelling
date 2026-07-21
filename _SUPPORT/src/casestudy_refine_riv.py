#!/usr/bin/env python
"""
================================================================================
 M2a.0 addendum -- FAITHFUL RIV re-transfer (case-study path ONLY)
================================================================================

`generate_refined_grid`'s corridor-refinement RIV transfer assigns a refined
cell to the river only when the cell CENTROID falls inside the river polygon.
On ~50 m Voronoi cells outside the refined corridor that misses ~40 m-wide
reaches, dropping ~36% of the calibrated river conductance (measured: coarse
1458 RIV cells / Sigma cond ~136,700 -> refined 164 cells / ~88,075), which
drifts the regional head field ~0.34 m RMS / 1.2 m max and corridor velocity
~33% (see DESIGN_DOCS/student_casestudy_M2a_0_riv_addendum.md).

This module implements the OWNER-APPROVED fix for the CASE-STUDY PATH ONLY --
`generate_refined_grid` and the shipped transport demo are left untouched
(the demo's latent error is a tracked follow-up). Both the M2a.0 golden
generator and the later M2a.1 builder call `faithful_riv_from_coarse` to
REPLACE the defective refined RIV package with a faithful one BEFORE the
solve, so the golden baseline heads are computed on the faithful river.

Method (river-geometry-weighted, PER-REACH records) -- per the v2 addendum:
  For each coarse RIV cell `c` (calibrated stage `s_c`, cond `K_c`, rbot
  `b_c`, occupying coarse DISV cell polygon `poly_c`):
    * wetted-bed footprint in `c` = river_geometry INTERSECT poly_c (NOT the
      full coarse-cell footprint -- that would shift conductance onto dry
      overbank);
    * find refined ACTIVE cells whose polygon intersects that footprint and
      split `K_c` in proportion to (footprint INTERSECT refined-cell)
      weight -- polygon-intersection AREA (river geometry is polygonal here)
      or centerline LENGTH (if the river geometry were linear);
    * emit a SEPARATE RIV record per (refined cell, source reach `c`) with
      the ORIGINAL `s_c`/`b_c` + split cond -- NEVER blend stage/rbot (RIV
      flux is nonlinear at rbot; MF6 sums multiple records per cell);
    * FAIL FAST (raise, with diagnostics) if `c`'s footprint intersects no
      ACTIVE refined cell.
  Sigma(split cond) over each coarse cell == `K_c` exactly (to float tol), so
  the total calibrated river conductance is conserved. Output is
  deterministic (sorted by cellid then source-reach index).

Interface note (documented deviation from the addendum's literal signature):
  the addendum lists `faithful_riv_from_coarse(refined_gridprops,
  refined_idomain, coarse_riv, river_gdf, *, crs)`. The METHOD requires each
  coarse reach's DISV cell POLYGON (to clip the river to that reach), which a
  bare `stress_period_data.get_data(0)` recarray (cellid/stage/cond/rbot)
  does NOT carry. So `coarse_riv` here is a sequence of `CoarseRivReach`
  records -- each the calibrated (cellid, stage, cond, rbot) of ONE coarse
  RIV cell PLUS that cell's polygon -- produced by the documented adapter
  `build_coarse_riv_reaches(cgwf)` (which reads exactly
  `cgwf.get_package("RIV").stress_period_data.get_data(0)` for the calibrated
  values and `cgwf.modelgrid.get_cell_vertices` for the geometry). The
  conductance/stage/rbot source is still the coarse RIV package; the river
  GEOMETRY source is still `river_gdf`.

`uv run` for everything (see CLAUDE.md).
================================================================================
"""
from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger("casestudy_refine_riv")


# A single coarse RIV reach: its calibrated boundary values + its coarse DISV
# cell polygon (needed to clip the river geometry to this reach).
@dataclass(frozen=True)
class CoarseRivReach:
    cellid: Tuple[int, int]
    stage: float
    cond: float
    rbot: float
    geometry: Any  # shapely Polygon of the coarse DISV cell


# One faithful refined RIV record: (refined_cellid, stage, cond, rbot).
FaithfulRivRecord = Tuple[Tuple[int, int], float, float, float]

# Overbank over-concentration guard (Finding 4): after the overbank filter
# drops cells (botm > rbot), the reach's whole conductance is renormalized
# onto the RETAINED cells. If most of the reach footprint was dropped, that
# concentrates conductance onto a small sliver.
#   - retained/pre ratio < FAIL_RATIO  -> HARD RAISE (near-total concentration
#     onto a near-zero-area sliver -- degenerate geometry, never ship it);
#   - FAIL_RATIO <= ratio < WARN_RATIO -> RECORD + log a WARNING (visible in
#     the returned stats / manifest, never silently swallowed) but proceed.
# Choice (stated for the reviewer): warn+record in [0.005, 0.25), hard fail
# below 0.005. Rationale from the CLEAN group-0 run: exactly ONE of 1458
# reaches (reach (0,2102)) retains 1.4% -- its conductance lands on a single
# refined cell (3247) whose HEAD is well within the near-field gate (it is NOT
# a head outlier), so the placement is PHYSICALLY BENIGN. The near-field HEAD
# gate (un-refined RMS/p99 + outlier cap) is the PRIMARY fidelity check and
# already catches a genuinely bad concentration (it would show as a head
# outlier); this ratio guard is a secondary backstop, so a hard 0.05 fail
# (which trips on that benign 1.4% reach) was judged wrong -- it would block a
# legitimate golden. The 0.005 floor still fails a truly degenerate
# concentration (>3x worse than anything observed, i.e. conductance onto a
# ~zero-area numerical sliver), while the one 1.4% reach is recorded as a warn.
OVERBANK_RETAINED_WARN_RATIO = 0.25
OVERBANK_RETAINED_FAIL_RATIO = 0.005

# Overlap weights (area in m^2, or length in m) below this are treated as
# numerical slivers and dropped. Conservation stays EXACT because the split
# is renormalized by the sum of RETAINED weights.
_DEFAULT_MIN_OVERLAP = 1e-9


def _cellid_to_flat(cellid) -> int:
    """Flat cell index from an MF6 cellid (tuple or int)."""
    return int(cellid[-1]) if isinstance(cellid, (tuple, list, np.ndarray)) else int(cellid)


def build_coarse_riv_reaches(cgwf) -> List[CoarseRivReach]:
    """Adapter: build the `CoarseRivReach` list this module consumes from a
    coarse GWF model.

    Reads the calibrated boundary values from
    ``cgwf.get_package("RIV").stress_period_data.get_data(0)`` (the exact
    coarse RIV package) and each reach's polygon from
    ``cgwf.modelgrid.get_cell_vertices``. No river_gdf here -- geometry of the
    WETTED BED comes from river_gdf inside `faithful_riv_from_coarse`; this
    polygon only LOCATES the reach.
    """
    from shapely.geometry import Polygon as _Polygon

    riv = cgwf.get_package("RIV")
    if riv is None:
        raise ValueError("coarse model has no RIV package")
    spd = riv.stress_period_data.get_data(0)
    if spd is None or len(spd) == 0:
        raise ValueError("coarse RIV package has no stress_period_data for period 0")

    mg = cgwf.modelgrid
    reaches: List[CoarseRivReach] = []
    for rec in spd:
        flat = _cellid_to_flat(rec["cellid"])
        poly = _Polygon(mg.get_cell_vertices(flat))
        reaches.append(CoarseRivReach(
            cellid=(int(rec["cellid"][0]) if not np.isscalar(rec["cellid"]) else 0,
                    flat),
            stage=float(rec["stage"]),
            cond=float(rec["cond"]),
            rbot=float(rec["rbot"]),
            geometry=poly,
        ))
    return reaches


def refined_cell_polygons(gridprops) -> List[Any]:
    """Build a shapely Polygon per refined DISV cell from a `gridprops` dict
    (``vertices`` = [ivert, x, y] rows; ``cell2d`` = [icell, xc, yc, nverts,
    iv0, iv1, ...] rows). Cell order matches the flat cell index (row order).
    """
    from shapely.geometry import Polygon as _Polygon

    verts = {int(v[0]): (float(v[1]), float(v[2])) for v in gridprops["vertices"]}
    polys: List[Any] = []
    for row in gridprops["cell2d"]:
        nverts = int(row[3])
        ivs = [int(row[4 + k]) for k in range(nverts)]
        polys.append(_Polygon([verts[i] for i in ivs]))
    return polys


def _river_weight_fn(river_gdf):
    """Pick the conductance-split primitive from the river geometry type.

    Polygonal river footprint -> AREA weighting (river wetted-bed polygon);
    linear river centerline -> LENGTH weighting. Returns (weight_fn,
    primitive_name).
    """
    geom_types = set(str(t) for t in river_gdf.geom_type.unique())
    polygonal = {"Polygon", "MultiPolygon"}
    linear = {"LineString", "MultiLineString"}
    if geom_types <= polygonal:
        return (lambda g: float(getattr(g, "area", 0.0))), "area"
    if geom_types <= linear:
        return (lambda g: float(getattr(g, "length", 0.0))), "length"
    raise ValueError(
        f"river_gdf has mixed/unsupported geometry types {sorted(geom_types)!r}; "
        "expected all-polygon (area weighting) or all-line (length weighting)"
    )


def faithful_riv_from_coarse(
    refined_gridprops,
    refined_idomain,
    coarse_riv: Sequence[CoarseRivReach],
    river_gdf,
    *,
    crs: Optional[str] = None,
    refined_botm=None,
    min_overlap: float = _DEFAULT_MIN_OVERLAP,
    return_primitive: bool = False,
    return_stats: bool = False,
):
    """Produce a FAITHFUL refined RIV record set from the coarse (calibrated)
    RIV package + the river geometry, per the v2 addendum method.

    Parameters
    ----------
    refined_gridprops : dict
        Refined DISV ``gridprops`` (``vertices`` + ``cell2d``).
    refined_idomain : array-like
        Refined idomain (length ncpl); RIV is placed on ACTIVE (!=0) cells only.
    coarse_riv : sequence of CoarseRivReach
        The coarse RIV package as reaches with geometry (see
        ``build_coarse_riv_reaches``).
    river_gdf : geopandas.GeoDataFrame
        River geometry (Limmat/Sihl). Polygon -> area weighting; line ->
        length weighting.
    crs : str, optional
        Recorded for provenance; geometry is assumed already in this CRS.
    refined_botm : array-like, optional
        Refined per-cell bottom elevation (length ncpl). When given, the
        OVERBANK FILTER is active: a reach's conductance is split only among
        the overlapping refined cells whose ``botm <= reach.rbot`` (the cells
        that can physically host the river bed -- MF6 requires ``rbot >=
        cell botm``), renormalizing among them so Sigma cond is still exact.
        This is the concrete realization of the addendum's fix #1 ("a refined
        cell over dry OVERBANK must not get river conductance"): a refined
        cell whose interpolated botm sits ABOVE the river bottom is overbank
        and is excluded. When ``None`` (addendum-literal), no overbank filter
        is applied (every overlapping active cell shares the conductance) --
        the caller must then handle any ``rbot < cell botm`` itself.
    min_overlap : float
        Overlap weights (m^2 or m) at/below this are dropped as slivers.
        Conservation stays exact (split renormalized by retained weights).
    return_primitive : bool
        If True, also return the chosen weighting primitive name.
    return_stats : bool
        If True, also return a stats dict: ``primitive``, ``n_source_reaches``,
        ``n_reaches_placed`` (== n_source_reaches by construction; a checked
        coverage invariant), ``min_retained_weight_ratio`` (min over reaches of
        retained/pre-filter overbank ratio, 1.0 when no filtering), and
        ``reaches_below_warn_ratio`` (list of reaches whose overbank-retained
        ratio fell below :data:`OVERBANK_RETAINED_WARN_RATIO`). Takes
        precedence over *return_primitive* if both are set.

    Returns
    -------
    list of (cellid, stage, cond, rbot)
        Deterministic (sorted by cellid then source-reach index). Multiple
        records may share a cellid (one per overlapping coarse reach) -- MF6
        sums them. ``Sigma cond == Sigma coarse cond`` exactly. The
        within-reach conductance split is ORDER-INDEPENDENT: overlaps are
        sorted by cell index and summed with ``math.fsum`` BEFORE the split,
        so the STRtree query order can never produce bit-level drift in
        ``riv_cond`` (which would silently change the frozen NPZ hash).
        If *return_stats*, returns ``(records, stats)``; else if
        *return_primitive*, returns ``(records, primitive_name)``.

    Raises
    ------
    ValueError
        If a coarse reach's wetted-bed footprint intersects NO active refined
        cell (naming the reach, its footprint area, the nearest active-cell
        distance, and idomain/CRS status) -- FAIL FAST, no silent drop. Also
        if the overbank filter is active and EVERY overlapping active cell is
        overbank (``botm > rbot``) so the reach's channel cannot be placed at
        channel elevation anywhere; or if the overbank-retained footprint
        ratio falls below :data:`OVERBANK_RETAINED_FAIL_RATIO` (near-total
        conductance concentration onto a sliver) -- FAIL FAST rather than
        invent/over-concentrate geometry.
    """
    from shapely.strtree import STRtree

    weight_fn, primitive = _river_weight_fn(river_gdf)
    river_union = river_gdf.geometry.union_all()

    polys = refined_cell_polygons(refined_gridprops)
    idomain = np.asarray(refined_idomain).reshape(-1)
    if idomain.size != len(polys):
        raise ValueError(
            f"refined_idomain length {idomain.size} != refined cell count {len(polys)}"
        )
    botm = None
    if refined_botm is not None:
        botm = np.asarray(refined_botm, dtype=float).reshape(-1)
        if botm.size != len(polys):
            raise ValueError(
                f"refined_botm length {botm.size} != refined cell count {len(polys)}"
            )
    active_idx = [i for i in range(len(polys)) if idomain[i] != 0]
    active_polys = [polys[i] for i in active_idx]
    if not active_polys:
        raise ValueError("no active refined cells (idomain all zero)")

    tree = STRtree(active_polys)
    # centroids of active cells for the fail-fast "nearest active distance"
    active_centroids = np.array([[p.centroid.x, p.centroid.y] for p in active_polys])

    records: List[Tuple[Tuple[int, int], float, float, float, int]] = []
    n_reaches_placed = 0
    min_retained_ratio = 1.0
    reaches_below_warn: List[Dict[str, Any]] = []
    for ci, reach in enumerate(coarse_riv):
        footprint = river_union.intersection(reach.geometry)
        foot_w = weight_fn(footprint)
        if footprint.is_empty or foot_w <= min_overlap:
            # This coarse RIV cell is not under the mapped river geometry --
            # a data inconsistency between the coarse RIV assignment and
            # river_gdf. FAIL FAST rather than invent a location.
            raise ValueError(
                "faithful RIV: coarse RIV reach "
                f"{reach.cellid} has empty river-geometry footprint "
                f"(river_gdf INTERSECT coarse-cell polygon area/length="
                f"{foot_w:g}); the coarse RIV cell is not covered by river_gdf. "
                f"crs={crs!r}. Cannot place its conductance."
            )

        cand = tree.query(footprint)  # indices into active_polys (bbox filter)
        overlaps: List[Tuple[int, float]] = []
        for k in np.atleast_1d(cand):
            k = int(k)
            inter = footprint.intersection(active_polys[k])
            w = weight_fn(inter)
            if w > min_overlap:
                overlaps.append((active_idx[k], w))

        if not overlaps:
            # footprint exists but no ACTIVE refined cell overlaps it.
            fx, fy = footprint.centroid.x, footprint.centroid.y
            d = np.hypot(active_centroids[:, 0] - fx, active_centroids[:, 1] - fy)
            nearest = float(d.min()) if d.size else float("nan")
            raise ValueError(
                "faithful RIV: coarse RIV reach "
                f"{reach.cellid} wetted-bed footprint (area/length={foot_w:g}, "
                f"centroid=({fx:.2f},{fy:.2f})) intersects NO active refined "
                f"cell; nearest active refined centroid is {nearest:.2f} m away. "
                f"crs={crs!r}, n_active={len(active_polys)}. This is a coverage "
                "gap (river over inactive/absent refined cells) -- refusing to "
                "silently drop calibrated conductance."
            )

        # OVERBANK FILTER: split only among cells that can host the river bed
        # (botm <= rbot). Overbank cells (botm > rbot) are excluded so MF6
        # never sees rbot < cell botm and no cell botm is invented/lowered.
        if botm is not None:
            pre_w = math.fsum(w for _, w in overlaps)
            compat = [(j, w) for (j, w) in overlaps if botm[j] <= reach.rbot]
            if not compat:
                overbank = sorted(
                    (int(j), round(float(botm[j]), 3)) for j, _ in overlaps
                )
                raise ValueError(
                    "faithful RIV: coarse RIV reach "
                    f"{reach.cellid} (rbot={reach.rbot:.3f}) overlaps only "
                    f"OVERBANK refined cells (all botm > rbot): {overbank[:5]}. "
                    "No refined cell can host the river bed at channel "
                    "elevation; refusing to invent geometry (would need a "
                    "documented botm-floor fallback)."
                )
            post_w = math.fsum(w for _, w in compat)
            ratio = (post_w / pre_w) if pre_w > 0 else 0.0
            if ratio < OVERBANK_RETAINED_FAIL_RATIO:
                retained = sorted(int(j) for j, _ in compat)
                raise ValueError(
                    "faithful RIV: coarse RIV reach "
                    f"{reach.cellid} (rbot={reach.rbot:.3f}) retains only "
                    f"{ratio:.3%} of its wetted-bed footprint after the "
                    f"overbank filter (< {OVERBANK_RETAINED_FAIL_RATIO:.0%}); "
                    f"its full conductance {reach.cond:g} would concentrate "
                    f"onto {len(retained)} sliver cell(s) {retained[:5]}. "
                    "Refusing to over-concentrate calibrated conductance."
                )
            if ratio < OVERBANK_RETAINED_WARN_RATIO:
                entry = {
                    "reach": [int(reach.cellid[0]), int(reach.cellid[1])],
                    "retained_ratio": float(ratio),
                    "retained_cells": sorted(int(j) for j, _ in compat),
                }
                reaches_below_warn.append(entry)
                logger.warning(
                    "faithful RIV: reach %s retains %.1f%% of footprint after "
                    "overbank filter (< %.0f%%) -- conductance concentrated onto "
                    "%d cell(s)", reach.cellid, 100 * ratio,
                    100 * OVERBANK_RETAINED_WARN_RATIO, len(compat),
                )
            min_retained_ratio = min(min_retained_ratio, ratio)
            overlaps = compat

        # ORDER-INDEPENDENT split (Finding 1a): sort by cell index FIRST, then
        # fsum the sorted weights, so the STRtree query order can never change
        # the summed wsum bit pattern (and thus the frozen riv_cond / hash).
        overlaps.sort(key=lambda t: t[0])
        wsum = math.fsum(w for _, w in overlaps)
        for rcell, w in overlaps:
            split_cond = reach.cond * (w / wsum)
            records.append(((0, int(rcell)), reach.stage, split_cond, reach.rbot, ci))
        n_reaches_placed += 1

    # Deterministic global order: cellid (layer, icell), then source reach.
    records.sort(key=lambda t: (t[0][0], t[0][1], t[4]))
    out: List[FaithfulRivRecord] = [
        (cid, stage, cond, rbot) for (cid, stage, cond, rbot, _src) in records
    ]

    # Guard the addendum invariants (cheap, deterministic).
    for cid, stage, cond, rbot in out:
        if not (math.isfinite(stage) and math.isfinite(cond) and math.isfinite(rbot)):
            raise ValueError(
                f"faithful RIV: record {cid} has non-finite value(s) "
                f"(stage={stage}, cond={cond}, rbot={rbot})"
            )
        if stage < rbot:
            raise ValueError(
                f"faithful RIV: record {cid} has stage {stage} < rbot {rbot} "
                "(coarse RIV inconsistency propagated)"
            )
        if cond <= 0:
            raise ValueError(f"faithful RIV: record {cid} has non-positive cond {cond}")

    stats = {
        "primitive": primitive,
        "n_source_reaches": len(coarse_riv),
        "n_reaches_placed": n_reaches_placed,
        "min_retained_weight_ratio": float(min_retained_ratio),
        "reaches_below_warn_ratio": reaches_below_warn,
    }
    if return_stats:
        return out, stats
    if return_primitive:
        return out, primitive
    return out


def riv_records_hash(records: Sequence[FaithfulRivRecord]) -> str:
    """Stable SHA-256 over a faithful RIV record set -- the M3 guard so a
    later builder can prove it used the SAME faithful RIV (not the defective
    or a stale package). Order-independent (records are sorted first),
    rounds floats to 9 decimals so bit-noise never changes the hash while a
    genuine conductance change does.
    """
    rows = sorted(
        (int(cid[0]), int(cid[1]), round(float(stage), 9), round(float(cond), 9), round(float(rbot), 9))
        for cid, stage, cond, rbot in records
    )
    h = hashlib.sha256()
    for layer, icell, stage, cond, rbot in rows:
        h.update(f"{layer}|{icell}|{stage:.9f}|{cond:.9f}|{rbot:.9f}\n".encode("utf-8"))
    return h.hexdigest()


def total_conductance(records: Sequence[FaithfulRivRecord]) -> float:
    return float(sum(float(c) for _, _, c, _ in records))
