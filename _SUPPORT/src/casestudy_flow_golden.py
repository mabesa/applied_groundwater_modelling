#!/usr/bin/env python
"""
================================================================================
 M2a.0 -- PIN THE INDEPENDENT 05f GOLDEN REFERENCE (regression anchor)
================================================================================

Produces the FROZEN, builder-independent "golden" baseline for student
GROUP 0: the steady-state heads of the calibrated MF6 "05f" flow model
(``model_io_utils.ensure_flow_model()``), corridor-refined (DISV, single
layer) around group 0's geothermal doublet location, with NO doublet wells
but WITH the 238 calibrated background abstraction wells re-mapped onto the
refined grid.

This module is standalone and DOES NOT import (or share module code with)
the M2a.1 baseline builder, ``casestudy_flow_builder`` -- the generator must
remain independent of the builder so it can serve as builder-independent
provenance tooling; the COMMITTED golden files are the regression oracle the
builder is pinned to. Both build the SAME baseline via the shared
``casestudy_flow_common`` primitives. It COMPOSES:

  * ``model_io_utils.ensure_flow_model`` / ``generate_refined_grid`` /
    ``freeze_flow_spec`` / ``load_flow_spec`` (shipped, unmodified) +
    ``casestudy_flow_common.assemble_flow_state`` (the single case-study
    flow-package factory; M2a.1 migrated the generator off
    ``model_io_utils.assemble_gwf_from_spec``);
  * ``scripts.jupyterhub_refine_reliability_gen`` primitives:
    ``group_refine_points`` (per-group doublet-anchored refine points),
    ``run_group_determinism_check`` (pure rerun-agreement gate),
    ``RETRY_RADII`` / ``_was_retried`` (single source of truth for the
    "did this run silently fall back to a wider radius" question);

and adds, NEW to this module:

  * ``baseline_well_data(cgwf)`` -- extracts the coarse model's calibrated
    WEL package (238 background abstraction wells) as ``(x, y, rate)``
    coordinate tuples (sign preserved), the well_data ``generate_refined_grid``
    expects for the no-doublet baseline;
  * ``canonicalize_wel_entries`` -- deterministically aggregates (sums) any
    WEL entries that ``generate_refined_grid`` mapped to the SAME refined
    cell (multiple background wells landing on one refined cell after
    corridor refinement), sorted by cellid. This is done BEFORE the model
    is assembled/solved, so the frozen WEL is never anything other than
    what MF6 actually solves;
  * the four pin-time validators (mass balance, no-dry-cells, near-field
    coarse-vs-refined head agreement with two named tolerances, and
    package-construction / geometry-intersection checks) that gate whether
    a candidate golden is safe to freeze;
  * a subprocess-isolated runner mirroring
    ``jupyterhub_refine_reliability_gen.subprocess_refine_runner`` (fresh
    child process per refinement attempt -- SIGILL out of Triangle/MF6
    kills only the child) driving a NEW no-doublet baseline refine function
    (``_real_refine_baseline_group``), because the existing
    ``_real_refine_group`` is hard-wired to the DOUBLET and is explicitly
    left untouched (see "RAISED FOLLOW-UP" in the M2a.0 plan).

Oracle structure (Codex-converged, see DESIGN_DOCS/student_casestudy_M2a_0_plan.md):
  * PRIMARY oracle: the canonical PACKAGE hashes written by
    ``freeze_flow_spec`` (== ``case_artifact_lock.write_artifact_manifest``
    over the encoded spec arrays) -- grid identity + package input arrays
    ONLY. This explicitly EXCLUDES solved MF6 outputs (heads/budget),
    workspace paths, and solver timestamps -- none of those ever become an
    ``.npz`` member, so they can never enter the hash.
  * SECONDARY oracle: the solved heads, stored as a plain JSON list inside
    the manifest ``caller_fields`` (NOT as an ``.npz`` array member, so they
    are outside the primary hash by construction) and compared, by
    downstream consumers, within a tolerance -- with max/RMS deltas
    reported alongside.

Platform reality: macOS-arm64 can SIGILL-crash the Triangle/MF6 refinement
for a fraction of locations (see ``model_io_utils.refine_with_retry``); the
determinism gate here REJECTS any run that fell back off the first retry
radius as non-freezable. The artifact this module ultimately commits is
therefore expected to be generated on the Linux/JupyterHub target (see the
plan's decision 2) -- this module runs identically there; nothing here is
platform-specific beyond the underlying Triangle/MF6 binaries.

Run with:
    uv run python -m casestudy_flow_golden --group 0 --reruns 5 --out-dir _SUPPORT/src/golden
    uv run pytest _SUPPORT/tests/test_casestudy_flow_golden.py -v
================================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# sys.path wiring: importable both as a normal module (pytest / notebooks,
# which already put _SUPPORT/src on sys.path) and as a re-invoked standalone
# child subprocess (see `subprocess_refine_baseline_runner`), which starts
# with a fresh sys.path.
# ---------------------------------------------------------------------------
_SRC_DIR = str(Path(__file__).resolve().parent)
_SCRIPTS_DIR = str(Path(__file__).resolve().parent / "scripts")
for _p in (_SRC_DIR, _SCRIPTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import model_io_utils as mio  # noqa: E402
import jupyterhub_refine_reliability_gen as rg  # noqa: E402
import casestudy_flow_common as cfc  # noqa: E402

# Shared baseline-build primitives now live in casestudy_flow_common (M2a.1
# refactor). Re-exported here under the SAME names the generator + its tests
# already use, so the golden's behaviour and public surface are unchanged.
from casestudy_flow_common import (  # noqa: E402
    baseline_well_data,
    canonicalize_wel_entries,
    apply_faithful_riv,
    load_coarse_model as _load_coarse_model,
    load_gis as _load_gis,
)

Group = Any
# (spec_dict, radius_used, retried_bool) -- same shape rg.Runner expects.
RunnerResult = Tuple[Dict[str, Any], float, bool]

# =============================================================================
# Named tolerances (single source of truth -- generator, manifest, and tests
# all reference these constants; changing a bound here is a deliberate,
# reviewable diff, never a silent drift).
# =============================================================================
GOLDEN_GROUP = 0
MASS_BALANCE_PCT_TOL = 1.0  # |PERCENT ERROR| must be < this, percent.

# Whole-domain refined-vs-coarse head agreement -- ROBUST gates set from the
# CLEAN faithful-RIV group-0 run (owner-approved, 2026-07-20) + margin.
#
# SINGLE SOURCE OF TRUTH for all near-field tolerances: the generator, the
# manifest, and the test all reference this dict; the test additionally pins
# the exact values, so changing a bound here without updating the test FAILS
# fast (the addendum's fail-fast-on-change).
#
# Design (owner decision): accept the ~0.056 m un-refined RMS floor (genuine
# NN-remeshing of K/top/botm) with ROBUST gates, NOT a raw-max gate:
#   - un-refined region: RMS <= 0.08 m AND p99(|delta|) <= 0.25 m -- robust
#     to the handful of pre-existing K/top/botm remeshing outliers;
#   - the un-refined RAW MAX is REPORTED, never gated;
#   - documented remeshing OUTLIERS: every un-refined cell with |delta| above
#     `unrefined_outlier_report_threshold_m` is listed (cellid/coords/delta/
#     distance-to-RIV) in the report+manifest so it is VISIBLE, never silently
#     swallowed; their COUNT must be <= `unrefined_outlier_cap` so a NEW gross
#     error still trips the gate even though the known ~19 remeshing cells (max
#     1.26 m at a cell 1.2 km from any river) are tolerated;
#   - refined corridor: RMS <= 0.06 m AND max <= 0.55 m.
# Observed clean group-0 run: un-refined RMS 0.056, p99 0.170, max 1.259,
# 19 cells > 0.30 m; corridor RMS 0.039, max 0.385. Cap 25 = 19 observed +
# documented ~30% margin.
NEAR_FIELD_TOL: Dict[str, float] = {
    "unrefined_rms_m": 0.08,
    "unrefined_p99_m": 0.25,
    "corridor_rms_m": 0.06,
    "corridor_max_m": 0.55,
    "unrefined_outlier_report_threshold_m": 0.30,
    "unrefined_outlier_cap": 25,
}

# Refined cellsize (m) separating the "corridor" (refined_cell_size ~ 10 m)
# from the "un-refined region" (base_cell_size ~ 50 m) of
# `generate_refined_grid`'s Voronoi mesh. Chosen at the midpoint so a
# reasonable meshing tolerance on either side can never misclassify a cell.
UNREFINED_CELLSIZE_THRESHOLD_M = 30.0

# CHD cells are re-assigned within 30 m of the coarse CHD cell centre by
# `generate_refined_grid` (see its CHD-transfer step); this is the paired
# tolerance for the geometry-intersection check (refined CHD cells must
# stay close to the model boundary).
CHD_BOUNDARY_MAX_DIST_M = 60.0

RCHA_CONSERVATION_REL_TOL = 0.05  # areal recharge: Σ refined vs Σ coarse
WEL_RATE_CONSERVATION_TOL = 1e-6  # m3/d; Σ refined WEL == Σ coarse WEL

# Faithful RIV (case-study addendum): Σ refined cond must equal Σ coarse cond
# to within this RELATIVE tolerance (the area-weighted split is exact, so
# this is a tight guard against a coding regression, not a physical slop).
RIV_COND_CONSERVATION_REL_TOL = 1e-6
# Refined river NET flux vs coarse river net flux: sanity band only (RECORDED
# in the manifest for the owner to judge; not a physics oracle). A gross
# violation (wrong sign / >this factor off) fails; the final flux tolerance
# is set with the owner from the diagnosed run.
RIV_FLUX_SANITY_FACTOR = 3.0

DEFAULT_CHILD_TIMEOUT_S = rg.DEFAULT_CHILD_TIMEOUT_S

_DEFAULT_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

# Private CLI flag that re-invokes this file as the subprocess child (mirrors
# jupyterhub_refine_reliability_gen._CHILD_FLAG, but distinct -- this module
# spawns ITS OWN child entry point, not the doublet one).
_CHILD_FLAG = "--_agm-golden-child-refine"


def _assert_json_finite(obj: Any, _path: str = "") -> None:
    """Recursively raise ``ValueError`` if any numeric leaf in *obj* is
    non-finite (NaN/Inf) -- the manifest guard (Finding 2) so a NaN can never
    be silently serialized into the golden manifest JSON (which would be
    invalid RFC-8259 JSON that some parsers accept and others reject).
    """
    import math as _math

    if isinstance(obj, bool):
        return
    if isinstance(obj, float):
        if not _math.isfinite(obj):
            raise ValueError(
                f"manifest field {_path or '<root>'} is non-finite ({obj!r}); "
                "refusing to serialize a NaN/Inf into the golden manifest"
            )
        return
    if isinstance(obj, (int, str, type(None))):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_json_finite(v, f"{_path}.{k}" if _path else str(k))
        return
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_json_finite(v, f"{_path}[{i}]")
        return
    # numpy scalars / arrays
    arr = np.asarray(obj)
    if arr.dtype.kind in "fc" and not np.all(np.isfinite(arr)):
        raise ValueError(
            f"manifest field {_path or '<root>'} contains non-finite value(s)"
        )


# =============================================================================
# Baseline well extraction + WEL canonicalization now live in
# casestudy_flow_common (re-exported at the top of this module).
# =============================================================================
def assert_wel_rate_conserved(
    coarse_well_data: List[Tuple[float, float, float]],
    wel_rate: List[float],
    *,
    tol: float = WEL_RATE_CONSERVATION_TOL,
) -> None:
    """Raise unless Σ *wel_rate* equals Σ the coarse background-well rates
    (within *tol*) -- flux conservation across the coarse->refined WEL
    remap, invariant to any cellid aggregation (summation never changes a
    total)."""
    rates = np.asarray([float(r) for r in wel_rate], dtype=float)
    if rates.size and not np.all(np.isfinite(rates)):
        raise ValueError("WEL rate array contains non-finite value(s) (NaN/Inf)")
    coarse_sum = float(sum(rate for _, _, rate in coarse_well_data))
    refined_sum = float(rates.sum())
    if abs(coarse_sum - refined_sum) > tol:
        raise ValueError(
            f"WEL flux conservation failed: coarse background-well "
            f"Sigma(rate)={coarse_sum!r} m3/d vs refined baseline "
            f"Sigma(rate)={refined_sum!r} m3/d (tol={tol!r})"
        )


def check_background_wells_present_canonical(
    wel_cellid: List[Tuple[int, int]], *, expected_input_count: int
) -> None:
    """Raise unless the (canonicalized) refined WEL has between 1 and
    *expected_input_count* cells -- present, and never MORE than the
    number of coarse background wells (aggregation can only ever reduce
    the count, never inflate it)."""
    n = len(wel_cellid)
    if n == 0:
        raise ValueError(
            "baseline golden has zero WEL cells; expected the calibrated "
            "background wells to be present (no-doublet baseline still "
            "includes background abstraction)"
        )
    if n > expected_input_count:
        raise ValueError(
            f"baseline golden has more WEL cells ({n}) than coarse "
            f"background wells ({expected_input_count}); duplicate-cellid "
            "aggregation must only ever reduce (or preserve) the count"
        )


# =============================================================================
# Pin-time validator 1: flow mass balance.
# =============================================================================
def validate_mass_balance(gwf, *, tol_pct: float = MASS_BALANCE_PCT_TOL) -> float:
    """Raise unless the solved refined baseline's |PERCENT ERROR| (from
    ``model_io_utils.format_budget_summary``) is below *tol_pct* percent.

    Returns the signed percent-error value on success.
    """
    df = mio.format_budget_summary(gwf)
    pct = float(df.loc["PERCENT ERROR", "Net (m3/d)"])
    if abs(pct) >= tol_pct:
        raise ValueError(
            f"flow mass balance |PERCENT ERROR|={pct!r}% >= tol {tol_pct!r}%"
        )
    return pct


# =============================================================================
# Pin-time validator 2: no dry cells.
# =============================================================================
def validate_no_dry_cells(heads, botm, *, dry_tol: float = 1e-6) -> int:
    """Raise unless zero active cells are dry (``head < botm - dry_tol``).

    Returns 0 on success (kept as a return value so callers can log it).
    """
    heads_arr = np.asarray(heads, dtype=float).reshape(-1)
    botm_arr = np.asarray(botm, dtype=float).reshape(-1)
    if heads_arr.shape != botm_arr.shape:
        raise ValueError(
            f"validate_no_dry_cells: heads shape {heads_arr.shape} != "
            f"botm shape {botm_arr.shape}"
        )
    # NaN-fragility guard (Finding 2): `NaN < botm` is False, so a NaN head
    # would silently PASS the dry check. Reject any non-finite head FIRST.
    if not np.all(np.isfinite(heads_arr)):
        n_bad = int(np.count_nonzero(~np.isfinite(heads_arr)))
        raise ValueError(
            f"{n_bad} non-finite (NaN/Inf) head value(s) in the baseline "
            "golden -- refusing to treat a NaN head as a valid (non-dry) cell"
        )
    dry = heads_arr < (botm_arr - dry_tol)
    n_dry = int(np.count_nonzero(dry))
    if n_dry:
        raise ValueError(
            f"{n_dry} dry active cell(s) found in the baseline golden "
            "(head < botm)"
        )
    return n_dry


# =============================================================================
# Pin-time validator 3: near-field + coarse-head agreement (whole domain,
# TWO NAMED tolerances) + targeted river/CHD/WEL-zone checks.
# =============================================================================
def near_field_head_deltas(
    coarse_xy: np.ndarray, coarse_heads: np.ndarray,
    refined_xy: np.ndarray, refined_heads: np.ndarray,
) -> np.ndarray:
    """Sample every refined-grid head back to its nearest coarse-grid cell
    (NearestND on coarse ACTIVE cell centres) and return
    ``refined_heads - coarse_heads_sampled_onto_refined``.

    Pure numeric function -- no MF6/flopy objects -- so it is directly unit
    testable with synthetic arrays.
    """
    from scipy.interpolate import NearestNDInterpolator

    coarse_xy = np.asarray(coarse_xy, dtype=float)
    coarse_heads = np.asarray(coarse_heads, dtype=float).reshape(-1)
    refined_xy = np.asarray(refined_xy, dtype=float)
    refined_heads = np.asarray(refined_heads, dtype=float).reshape(-1)

    nn = NearestNDInterpolator(coarse_xy, coarse_heads)
    coarse_on_refined = nn(refined_xy[:, 0], refined_xy[:, 1])
    return refined_heads - np.asarray(coarse_on_refined, dtype=float)


def validate_near_field_agreement(
    delta: np.ndarray,
    refined_cellsize: np.ndarray,
    *,
    refined_xy: np.ndarray,
    riv_dist: np.ndarray,
    tol: Optional[Dict[str, float]] = None,
    unrefined_cellsize_threshold: float = UNREFINED_CELLSIZE_THRESHOLD_M,
) -> Dict[str, Any]:
    """Raise unless whole-domain refined-vs-coarse head deltas satisfy the
    ROBUST near-field gates in *tol* (defaults to :data:`NEAR_FIELD_TOL`).
    Always returns a report of observed stats (even on PASS, for the
    manifest), including the documented un-refined outlier list.

    Region split: ``refined_cellsize < unrefined_cellsize_threshold`` is the
    "corridor" (refined, ~10 m cells); the complement is the "un-refined"
    region (~50 m base cells).

    Gates (owner-approved robust set, see :data:`NEAR_FIELD_TOL`):
      - un-refined: ``RMS <= unrefined_rms_m`` AND ``p99(|delta|) <=
        unrefined_p99_m``; the un-refined RAW MAX is REPORTED, not gated;
      - un-refined outliers (``|delta| > unrefined_outlier_report_threshold_m``)
        are listed (cell/coords/delta/distance-to-RIV) and their COUNT must
        be ``<= unrefined_outlier_cap``;
      - corridor: ``RMS <= corridor_rms_m`` AND ``max <= corridor_max_m``.

    Parameters
    ----------
    refined_xy : (ncpl, 2) array
        Refined cell-centre coordinates (for the outlier list).
    riv_dist : (ncpl,) array
        Distance from each refined cell to the nearest refined RIV cell (for
        the outlier list; ``inf`` where there are no RIV cells).
    """
    tol = NEAR_FIELD_TOL if tol is None else tol
    delta = np.asarray(delta, dtype=float)
    cellsize = np.asarray(refined_cellsize, dtype=float)
    if delta.shape != cellsize.shape:
        raise ValueError(
            f"validate_near_field_agreement: delta shape {delta.shape} != "
            f"refined_cellsize shape {cellsize.shape}"
        )
    # NaN-fragility guard (Finding 2): a NaN delta would make every `>`
    # comparison False and silently PASS every gate. Reject it up front.
    if delta.size and not np.all(np.isfinite(delta)):
        raise ValueError(
            "near-field delta contains non-finite (NaN/Inf) value(s) -- "
            "refusing to evaluate the head-agreement gates on a NaN field"
        )
    refined_xy = np.asarray(refined_xy, dtype=float)
    riv_dist = np.asarray(riv_dist, dtype=float).reshape(-1)

    corridor_mask = cellsize < unrefined_cellsize_threshold
    unrefined_mask = ~corridor_mask

    report: Dict[str, Any] = {}

    # ---- un-refined region: robust gates + documented outliers ----------
    du = delta[unrefined_mask]
    adu = np.abs(du)
    u_rms = float(np.sqrt(np.mean(du ** 2))) if du.size else 0.0
    u_p99 = float(np.percentile(adu, 99)) if du.size else 0.0
    u_max = float(adu.max()) if du.size else 0.0
    report["unrefined_rms_m"] = u_rms
    report["unrefined_p99_m"] = u_p99
    report["unrefined_max_m"] = u_max  # REPORTED, not gated

    thr = float(tol["unrefined_outlier_report_threshold_m"])
    cap = int(tol["unrefined_outlier_cap"])
    unref_idx = np.where(unrefined_mask)[0]
    out_local = unref_idx[np.abs(delta[unref_idx]) > thr]
    out_local = out_local[np.argsort(np.abs(delta[out_local]))[::-1]]
    outliers = [
        {
            "cell": int(i),
            "x": float(refined_xy[i, 0]),
            "y": float(refined_xy[i, 1]),
            "delta_m": float(delta[i]),
            "dist_to_riv_m": (float(riv_dist[i]) if np.isfinite(riv_dist[i]) else None),
        }
        for i in out_local
    ]
    report["unrefined_outlier_threshold_m"] = thr
    report["n_unrefined_outliers"] = len(outliers)
    report["unrefined_outliers"] = outliers

    # ---- corridor region -------------------------------------------------
    dc = delta[corridor_mask]
    adc = np.abs(dc)
    c_rms = float(np.sqrt(np.mean(dc ** 2))) if dc.size else 0.0
    c_max = float(adc.max()) if dc.size else 0.0
    report["corridor_rms_m"] = c_rms
    report["corridor_max_m"] = c_max

    # ---- GATES (raise naming the first violation) ------------------------
    if u_rms > tol["unrefined_rms_m"]:
        raise ValueError(
            f"near-field un-refined RMS={u_rms:.4f} m exceeds tol "
            f"{tol['unrefined_rms_m']} m"
        )
    if u_p99 > tol["unrefined_p99_m"]:
        raise ValueError(
            f"near-field un-refined p99(|delta|)={u_p99:.4f} m exceeds tol "
            f"{tol['unrefined_p99_m']} m"
        )
    if len(outliers) > cap:
        top = [(o["cell"], round(o["delta_m"], 3)) for o in outliers[:8]]
        raise ValueError(
            f"near-field un-refined has {len(outliers)} documented outlier(s) "
            f"(|delta| > {thr} m), exceeding the cap of {cap}; a NEW gross "
            f"remeshing error is likely. Top: {top}"
        )
    if c_rms > tol["corridor_rms_m"]:
        raise ValueError(
            f"near-field corridor RMS={c_rms:.4f} m exceeds tol "
            f"{tol['corridor_rms_m']} m"
        )
    if c_max > tol["corridor_max_m"]:
        raise ValueError(
            f"near-field corridor max |delta|={c_max:.4f} m exceeds tol "
            f"{tol['corridor_max_m']} m"
        )
    return report


def _refined_cellsizes(modelgrid) -> np.ndarray:
    """Per-cell 'linear size' proxy (sqrt(area)) for every cell of a refined
    DISV VertexGrid -- used to split the whole domain into the "corridor"
    (small cells) vs "un-refined" (base-size cells) regions."""
    from shapely.geometry import Polygon as ShapelyPolygon

    ncpl = int(modelgrid.ncpl)
    areas = np.array([
        ShapelyPolygon(modelgrid.get_cell_vertices(i)).area for i in range(ncpl)
    ])
    return np.sqrt(areas)


def near_field_and_zone_validation(
    cgwf, coarse_heads: np.ndarray, refined_modelgrid, refined_heads: np.ndarray,
    spec: Dict[str, Any],
) -> Dict[str, Any]:
    """Full near-field validator: whole-domain coarse-vs-refined head
    agreement (ROBUST un-refined RMS/p99 + outlier-count gates; corridor
    RMS/max gates -- see :func:`validate_near_field_agreement`) PLUS
    REPORT-ONLY river/CHD/WEL zone stats.

    The zone stats are recorded (max/RMS per zone) but NOT gated: with the
    faithful RIV, river cells legitimately sit in the un-refined region and a
    few reach ~0.74 m (documented remeshing outliers) -- a raw-max zone gate
    would wrongly trip on them. The robust un-refined RMS/p99/outlier-cap
    gates already cover every un-refined cell (river cells included).

    Returns the combined report dict (region stats + outlier list + per-zone
    stats) on success; raises ValueError naming the first violated gate.
    """
    coarse_mg = cgwf.modelgrid
    idomain = cgwf.get_package("DISV").idomain.array.flatten()
    active = idomain > 0
    coarse_xy = np.column_stack([
        coarse_mg.xcellcenters[active], coarse_mg.ycellcenters[active],
    ])
    coarse_h = np.asarray(coarse_heads, dtype=float).reshape(-1)[active]

    refined_xy = np.column_stack([
        refined_modelgrid.xcellcenters, refined_modelgrid.ycellcenters,
    ])
    delta = near_field_head_deltas(coarse_xy, coarse_h, refined_xy, refined_heads)
    cellsize = _refined_cellsizes(refined_modelgrid)

    # distance from every refined cell to the nearest refined RIV cell (for
    # the documented-outlier list).
    riv_flats = sorted({int(c[1]) for c in spec["riv_cellid"]})
    if riv_flats:
        from scipy.spatial import cKDTree
        riv_dist = cKDTree(refined_xy[riv_flats]).query(refined_xy, k=1)[0]
    else:
        riv_dist = np.full(refined_xy.shape[0], np.inf)

    report = validate_near_field_agreement(
        delta, cellsize, refined_xy=refined_xy, riv_dist=riv_dist,
    )

    # REPORT-ONLY zone stats (no gate).
    for zone_name, cellid_key in (("chd", "chd_cellid"), ("riv", "riv_cellid"), ("wel", "wel_cellid")):
        flats = [int(c[1]) for c in spec[cellid_key]]
        if flats:
            d = delta[np.asarray(flats, dtype=int)]
            report[f"{zone_name}_zone_max_m"] = float(np.max(np.abs(d)))
            report[f"{zone_name}_zone_rms_m"] = float(np.sqrt(np.mean(d ** 2)))
        else:
            report[f"{zone_name}_zone_max_m"] = 0.0
            report[f"{zone_name}_zone_rms_m"] = 0.0
    return report


# =============================================================================
# Pin-time validator 4: package-construction (not heads-only).
# =============================================================================
def check_active_mask(idomain) -> None:
    idomain = np.asarray(idomain)
    if not np.all(idomain != 0):
        raise ValueError(
            "refined baseline has inactive (idomain==0) cell(s); "
            "generate_refined_grid always builds an all-active mask"
        )


def check_npf_k(k) -> None:
    k_arr = np.asarray(k, dtype=float)
    if not np.all(np.isfinite(k_arr)) or not np.all(k_arr > 0):
        raise ValueError(
            "refined baseline NPF K field contains non-finite or "
            "non-positive value(s)"
        )


def check_rcha_conservation(
    coarse_rch, coarse_areas, refined_rch, refined_areas,
    *, tol_frac: float = RCHA_CONSERVATION_REL_TOL,
) -> Tuple[float, float]:
    """Raise unless the areal recharge total is (approximately) conserved
    between the coarse and refined grids: Sigma(rch_i * area_i) agrees
    within *tol_frac* relative difference. Returns (coarse_total, refined_total)."""
    coarse_total = float(np.sum(np.asarray(coarse_rch, dtype=float) * np.asarray(coarse_areas, dtype=float)))
    refined_total = float(np.sum(np.asarray(refined_rch, dtype=float) * np.asarray(refined_areas, dtype=float)))
    if coarse_total == 0.0:
        if abs(refined_total) > tol_frac:
            raise ValueError(
                f"areal recharge not conserved: coarse total is exactly 0 "
                f"but refined total is {refined_total!r}"
            )
        return coarse_total, refined_total
    rel = abs(refined_total - coarse_total) / abs(coarse_total)
    if rel > tol_frac:
        raise ValueError(
            f"areal recharge not conserved: coarse total {coarse_total:.4f} "
            f"vs refined total {refined_total:.4f} (relative diff "
            f"{rel:.3%} > tol {tol_frac:.0%})"
        )
    return coarse_total, refined_total


def check_riv_present(riv_cellid, riv_cond) -> None:
    if len(riv_cellid) == 0:
        raise ValueError("refined baseline has zero RIV cells")
    if not np.all(np.asarray(riv_cond, dtype=float) > 0):
        raise ValueError("refined baseline RIV conductance has non-positive value(s)")


# =============================================================================
# apply_faithful_riv now lives in casestudy_flow_common (re-exported at the top
# of this module); the generator calls it after its determinism gate.
# =============================================================================


def validate_riv_conductance_conserved(
    refined_cond, coarse_cond, *, rel_tol: float = RIV_COND_CONSERVATION_REL_TOL,
) -> float:
    """Raise unless Σ refined RIV cond == *coarse_cond* within *rel_tol*
    (relative). Returns the refined total. THE faithful-RIV invariant."""
    cond = np.asarray(refined_cond, dtype=float)
    if cond.size and not np.all(np.isfinite(cond)):
        raise ValueError("refined RIV conductance contains non-finite value(s) (NaN/Inf)")
    r = float(np.sum(cond))
    c = float(coarse_cond)
    if not np.isfinite(c):
        raise ValueError(f"coarse RIV conductance total is non-finite: {c!r}")
    denom = max(abs(c), 1.0)
    if abs(r - c) > rel_tol * denom:
        raise ValueError(
            f"faithful RIV conductance not conserved: coarse Sigma cond={c:.6f} "
            f"vs refined Sigma cond={r:.6f} (rel diff {abs(r-c)/denom:.3e} > "
            f"tol {rel_tol:.1e})"
        )
    return r


def riv_net_flux(gwf) -> float:
    """Net RIV package flux (m3/d) from a solved GWF model's budget."""
    bud = gwf.output.budget()
    rec = bud.get_data(text="RIV", totim=bud.get_times()[-1])
    if not rec:
        return float("nan")
    return float(np.sum(rec[0]["q"]))


def validate_riv_flux_sanity(
    refined_flux: float, coarse_flux: float, *, factor: float = RIV_FLUX_SANITY_FACTOR,
) -> None:
    """Loose sanity band on refined vs coarse river net flux -- catches a
    gross regression (wrong sign / order-of-magnitude off). The final flux
    tolerance is set with the owner from the diagnosed run; this only guards
    against catastrophe."""
    if not np.isfinite(refined_flux) or not np.isfinite(coarse_flux):
        raise ValueError(
            f"RIV flux not finite: refined={refined_flux!r} coarse={coarse_flux!r}"
        )
    if coarse_flux != 0 and (refined_flux / coarse_flux) < 0:
        raise ValueError(
            f"RIV net flux sign flipped: coarse={coarse_flux:.2f} refined="
            f"{refined_flux:.2f} m3/d"
        )
    if abs(coarse_flux) > 1.0:
        ratio = abs(refined_flux) / abs(coarse_flux)
        if ratio > factor or ratio < 1.0 / factor:
            raise ValueError(
                f"RIV net flux grossly off: coarse={coarse_flux:.2f} refined="
                f"{refined_flux:.2f} m3/d (ratio {ratio:.2f} outside "
                f"[1/{factor:g}, {factor:g}])"
            )


def check_chd_present(chd_cellid) -> None:
    if len(chd_cellid) == 0:
        raise ValueError("refined baseline has zero CHD cells")


def check_riv_intersects_river_geometry(riv_cellid, modelgrid, river_union) -> None:
    """GEOMETRY-level check: every refined RIV cell POLYGON must spatially
    intersect the river geometry -- catches a shifted-but-same-total RIV
    mapping that a count/conductance-only check would miss.

    Uses cell-polygon intersection (not centroid-in-polygon): the faithful
    RIV transfer places conductance on any cell whose polygon overlaps the
    river, and such a cell's CENTROID can legitimately sit just outside the
    river polygon (river clipped at the cell edge)."""
    from shapely.geometry import Polygon as ShapelyPolygon

    bad = []
    for cellid in {int(c[1]) for c in riv_cellid}:
        poly = ShapelyPolygon(modelgrid.get_cell_vertices(cellid))
        if not river_union.intersects(poly):
            bad.append(cellid)
    if bad:
        raise ValueError(
            f"{len(bad)} RIV cell(s) do not spatially intersect the river "
            f"geometry (first few flat indices: {bad[:5]})"
        )


def check_chd_near_boundary(
    chd_cellid, modelgrid, boundary_gdf, *, max_dist_m: float = CHD_BOUNDARY_MAX_DIST_M,
) -> None:
    """GEOMETRY-level check: every refined CHD cell centre must lie within
    *max_dist_m* of the model boundary line (``generate_refined_grid``
    reassigns CHD within 30 m of the coarse CHD cell, itself on the
    boundary) -- catches a shifted-but-same-total CHD mapping."""
    from shapely.geometry import Point as ShapelyPoint

    boundary_line = boundary_gdf.geometry.iloc[0].boundary
    xc, yc = modelgrid.xcellcenters, modelgrid.ycellcenters
    bad = []
    for cellid in chd_cellid:
        i = int(cellid[1])
        d = boundary_line.distance(ShapelyPoint(xc[i], yc[i]))
        if d > max_dist_m:
            bad.append((i, round(float(d), 2)))
    if bad:
        raise ValueError(
            f"{len(bad)} CHD cell(s) are farther than {max_dist_m} m from "
            f"the model boundary (first few [flat_index, dist_m]: {bad[:5]})"
        )


# =============================================================================
# Coarse-model / GIS loaders (`_load_coarse_model`/`_load_gis`) now live in
# casestudy_flow_common (re-exported at the top of this module).
# =============================================================================


# =============================================================================
# NEW no-doublet baseline refine function (mirrors
# jupyterhub_refine_reliability_gen._real_refine_group's structure, but
# builds the background-well baseline spec via the shared
# `casestudy_flow_common.refine_baseline_grid` -- generate_refined_grid +
# canonicalize WEL -- inside the SIGILL radius walk).
# =============================================================================
def _real_refine_baseline_group(
    group: Group, *, mother_model: Path, work_dir: Path,
) -> RunnerResult:
    """Real (non-fake) no-doublet baseline refinement for *group*.

    HUB-ONLY in practice (loads MF6 + geopandas + Triangle); the local test
    suite never reaches this function -- it drives the
    ``AGM_FAKE_SPEC_NPZ`` / ``AGM_FAKE_CHILD_SIGNAL`` child hooks instead
    (see ``_child_refine_main``).
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    sim, gwf = _load_coarse_model(Path(mother_model))
    heads = gwf.output.head().get_data().flatten()
    boundary_gdf, river_gdf = _load_gis(Path(mother_model))
    wells = baseline_well_data(gwf)
    refine_points = rg.group_refine_points(group)

    last_exc: Any = None
    for k, radius in enumerate(rg.RETRY_RADII):
        try:
            spec = cfc.refine_baseline_grid(
                gwf, boundary_gdf, river_gdf, refine_points, heads,
                refine_radius=radius, wells=wells,
            )
            cfc.assemble_flow_state(
                spec, workspace=work_dir / f"rg{k}", sim_name=f"golden_g{group}",
            )
            return spec, float(radius), (k > 0)
        except Exception as e:  # Triangle abort / MF6 nonconvergence, etc.
            last_exc = e
            continue
    raise RuntimeError(
        f"group {group}: no-doublet baseline refinement failed at all "
        f"radii; last error: {last_exc!r}"
    )


def _child_refine_main(argv) -> int:
    """Child-process entry point for the golden-baseline subprocess runner.

    Mirrors ``jupyterhub_refine_reliability_gen._child_refine_main`` but
    calls ``_real_refine_baseline_group`` instead of the doublet-hardwired
    ``_real_refine_group``. Honours the SAME two test hooks
    (``AGM_FAKE_SPEC_NPZ`` / ``AGM_FAKE_CHILD_SIGNAL``) so the whole IPC
    path is exercisable with NO MODFLOW.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", required=True, type=int)
    parser.add_argument("--mother-model", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--out-npz", required=True)
    args = parser.parse_args(argv)

    fake_signal = os.environ.get("AGM_FAKE_CHILD_SIGNAL")
    if fake_signal:
        os.kill(os.getpid(), int(fake_signal))
        return 1  # unreachable when the signal is fatal; kept for clarity

    fake_npz = os.environ.get("AGM_FAKE_SPEC_NPZ")
    if fake_npz:
        spec = mio.load_flow_spec(fake_npz, verify=True)
    else:
        spec, _radius_used, _retried = _real_refine_baseline_group(
            int(args.group),
            mother_model=Path(args.mother_model),
            work_dir=Path(args.work_dir),
        )

    mio.freeze_flow_spec(
        spec, Path(args.out_npz),
        caller_fields={"group": int(args.group)},
    )
    return 0


def subprocess_refine_baseline_runner(
    group: Group, *, mother_model: Any, work_dir: Any,
    timeout_s: float = DEFAULT_CHILD_TIMEOUT_S,
) -> RunnerResult:
    """Run the no-doublet baseline refinement for *group* in a FRESH Python
    subprocess and return ``(spec, radius_used, retried)`` via a
    freeze -> load IPC hop.

    Mirrors ``jupyterhub_refine_reliability_gen.subprocess_refine_runner``
    exactly (isolation / timeout / signal-death semantics), re-invoking
    THIS file (with its own private ``_CHILD_FLAG``) rather than that
    module's, since the child body calls the no-doublet
    ``_real_refine_baseline_group`` instead of the doublet-hardwired
    ``_real_refine_group``.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_npz = work_dir / f"_child_group{group}_baseline_spec.npz"

    cmd = [
        sys.executable, str(Path(__file__).resolve()), _CHILD_FLAG,
        "--group", str(group),
        "--mother-model", str(mother_model),
        "--work-dir", str(work_dir),
        "--out-npz", str(out_npz),
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    )

    try:
        _stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass  # process (group) already gone
        proc.communicate()  # reap, avoid a zombie
        raise RuntimeError(
            f"subprocess_refine_baseline_runner: child for group {group} "
            f"exceeded its {timeout_s:g}s timeout and was killed (process "
            "group SIGKILL); this group is recorded as FAILED"
        ) from None

    if proc.returncode < 0:
        signum = -proc.returncode
        try:
            signame = signal.Signals(signum).name
        except ValueError:
            signame = str(signum)
        raise RuntimeError(
            f"subprocess_refine_baseline_runner: child for group {group} "
            f"died by signal {signum} ({signame}); stderr:\n{stderr}"
        )
    if proc.returncode != 0:
        raise RuntimeError(
            f"subprocess_refine_baseline_runner: child for group {group} "
            f"exited with nonzero return code {proc.returncode}; "
            f"stderr:\n{stderr}"
        )

    spec = mio.load_flow_spec(out_npz, verify=True)
    radius_used = float(spec["refine_radius_used"])
    retried = rg._was_retried(radius_used)
    return spec, radius_used, retried


# =============================================================================
# Best-effort environment/tool-version manifest fields (Codex iter-2: "the
# manifest records the FULL environment" -- OS/arch, Python, MF6 exe+version,
# FloPy/NumPy/Shapely-GEOS, and the IMS solver settings).
# =============================================================================
def _golden_versions() -> Dict[str, Any]:
    versions = rg._best_effort_versions()
    versions["platform"] = platform.platform()
    versions["machine"] = platform.machine()
    versions["ims_options"] = {
        k: (list(v) if isinstance(v, (list, tuple)) else v)
        for k, v in dict(mio.GWF_NEWTON_IMS_OPTIONS).items()
    }
    return versions


# =============================================================================
# Top-level orchestration: determinism check -> real assemble/solve ->
# pin-time validation -> freeze.
# =============================================================================
def generate_group0_golden(
    *,
    mother_model: Optional[Any] = None,
    work_dir: Optional[Any] = None,
    out_dir: Optional[Any] = None,
    reruns: int = 5,
    group: Group = GOLDEN_GROUP,
    child_timeout_s: float = DEFAULT_CHILD_TIMEOUT_S,
) -> Dict[str, Any]:
    """Generate, validate, and freeze the no-doublet golden baseline for
    *group* (default group 0 -- the M2a.0 pilot).

    Raises (naming the failure) on ANY determinism or pin-time-validation
    failure; freezes NOTHING in that case -- there is no partial/unsafe
    artifact left behind for a caller to accidentally pick up.

    Returns
    -------
    dict
        The manifest written by ``model_io_utils.freeze_flow_spec`` on
        success (canonical package hashes + caller fields, incl. the
        solved heads as a SECONDARY oracle and the tolerances/deltas used).
    """
    mother_model = Path(mother_model) if mother_model else mio.ensure_flow_model()
    out_dir = Path(out_dir) if out_dir else _DEFAULT_GOLDEN_DIR
    work_dir = Path(work_dir) if work_dir else out_dir / "_work"

    calls: List[RunnerResult] = []

    def runner(g: Group, _calls=calls) -> RunnerResult:
        result = subprocess_refine_baseline_runner(
            g, mother_model=mother_model, work_dir=work_dir, timeout_s=child_timeout_s,
        )
        _calls.append(result)
        return result

    det = rg.run_group_determinism_check(group, runner, reruns=reruns)
    if det["status"] != "PASS":
        raise RuntimeError(
            f"group {group} golden baseline: determinism check FAILED "
            f"({det.get('reason')!r}); refusing to freeze a "
            "non-deterministic / non-freezable artifact"
        )

    spec = calls[0][0]
    radius_used = float(det["radius_used"])

    # Load the coarse (calibrated) model + GIS up front -- needed BEFORE the
    # solve to apply the faithful RIV re-transfer (case-study addendum).
    _csim, cgwf = _load_coarse_model(mother_model)
    coarse_heads = cgwf.output.head().get_data().flatten()
    boundary_gdf, river_gdf = _load_gis(mother_model)

    # ---- FAITHFUL RIV re-transfer (replace the defective centroid-in-polygon
    # RIV with the conservation-exact area-weighted per-reach transfer) BEFORE
    # the solve, so the golden baseline heads are on the faithful river. The
    # subprocess determinism gate above proved the GRID is reproducible; the
    # faithful RIV is applied HERE in the parent, so its determinism is NOT
    # covered by that gate. GATE it explicitly (Finding 1b): apply the faithful
    # RIV to EVERY rerun's spec and require a byte-identical record hash across
    # all reruns before proceeding -- otherwise a hash drift in the frozen RIV
    # (and thus the primary NPZ hash) could slip through unnoticed.
    faithful_by_rerun = [
        apply_faithful_riv(rerun_spec, cgwf, river_gdf)
        for (rerun_spec, _r, _t) in calls
    ]
    riv_hashes = {fi["hash"] for _fs, fi in faithful_by_rerun}
    if len(riv_hashes) != 1:
        raise RuntimeError(
            f"faithful RIV hash differs across {len(calls)} determinism reruns "
            f"({sorted(riv_hashes)}); the frozen RIV is not reproducible -- "
            "refusing to freeze a non-deterministic golden"
        )
    spec, riv_info = faithful_by_rerun[0]

    # Real assemble+solve (once) to obtain the actual solved heads/gwf for
    # the physics validators and the SECONDARY (heads) oracle.
    assemble_ws = out_dir / "_assemble" / f"group{group}"
    if assemble_ws.exists():
        shutil.rmtree(assemble_ws)
    assemble_ws.mkdir(parents=True)
    built = cfc.assemble_flow_state(
        spec, workspace=assemble_ws, sim_name=f"group{group}_golden",
    )
    gwf = built["gwf"]
    heads = built["heads"]

    # ---- pin-time validation (APPROVE-or-abort) -------------------------
    mass_balance_pct = validate_mass_balance(gwf)
    validate_no_dry_cells(heads, spec["botm"])

    near_field_report = near_field_and_zone_validation(
        cgwf, coarse_heads, built["modelgrid"], heads, spec,
    )

    check_active_mask(spec["idomain"])
    check_npf_k(spec["k"])
    check_riv_present(spec["riv_cellid"], spec["riv_cond"])
    check_chd_present(spec["chd_cellid"])

    river_union = river_gdf[
        river_gdf.intersects(boundary_gdf.geometry.iloc[0])
    ].geometry.union_all()
    check_riv_intersects_river_geometry(spec["riv_cellid"], built["modelgrid"], river_union)
    check_chd_near_boundary(spec["chd_cellid"], built["modelgrid"], boundary_gdf)

    # ---- faithful-RIV invariants + calibrated-equivalence FLUX checks ----
    # Spatial-fidelity gates for the RIV placement are: (1) the near-field HEAD
    # gate above (un-refined RMS/p99) -- heads directly constrain WHERE the
    # river conductance sits, so a conserved-but-misplaced RIV would move heads
    # and trip it; (2) the coarse-reach COVERAGE invariant in apply_faithful_riv
    # (every reach represented); (3) check_riv_intersects_river_geometry (every
    # RIV cell polygon overlaps the river). Net flux alone is weak (a misplaced
    # but conserved RIV can pass net-flux+-factor); a full binned/spatial flux
    # compare is NOT added -- it would be redundant given the head gate already
    # constrains placement (proportionate, per the addendum's Finding 3).
    validate_riv_conductance_conserved(spec["riv_cond"], riv_info["coarse_cond"])
    refined_riv_flux = riv_net_flux(gwf)
    coarse_riv_flux = riv_net_flux(cgwf)
    validate_riv_flux_sanity(refined_riv_flux, coarse_riv_flux)

    coarse_wells = baseline_well_data(cgwf)
    assert_wel_rate_conserved(coarse_wells, spec["wel_rate"])
    check_background_wells_present_canonical(
        spec["wel_cellid"], expected_input_count=len(coarse_wells),
    )

    # ---- freeze ----------------------------------------------------------
    npz_path = out_dir / f"group{group}_flow.npz"
    caller_fields: Dict[str, Any] = {
        "group": int(group),
        "doublet": False,
        "background_wells": len(coarse_wells),
        "steady": True,
        "nlay": 1,
        "radius_used": radius_used,
        "node": platform.node(),
        "versions": _golden_versions(),
        # Provisional-freeze provenance: this artifact may be frozen on the dev
        # box where group 0 happens to be SIGILL-free + deterministic; the
        # AUTHORITATIVE re-verify/re-freeze is on the Linux/JupyterHub target
        # (M2a.5). The PRIMARY oracle (canonical package hashes) is
        # platform-independent; heads are the SECONDARY oracle at 1e-3 m.
        "provisional": True,
        "authoritative_platform": "linux",
        "provisional_reason": (
            "Frozen on macOS-arm64 (group 0 is SIGILL-free + deterministic "
            "here) as a PROVISIONAL golden; MUST be re-verified and re-frozen "
            "on the Linux/JupyterHub target at M2a.5. The primary oracle "
            "(canonical package hashes) is platform-independent; solved heads "
            "are the secondary oracle compared within 1e-3 m."
        ),
        "mass_balance_pct_error": mass_balance_pct,
        "near_field_tol": dict(NEAR_FIELD_TOL),
        "near_field_report": near_field_report,
        # Faithful-RIV provenance + M3 guard (builder must reproduce this hash).
        "faithful_riv": {
            "primitive": riv_info["primitive"],
            "hash": riv_info["hash"],
            "coarse_cond": riv_info["coarse_cond"],
            "refined_cond": riv_info["refined_cond"],
            "n_records": riv_info["n_records"],
            "n_cells": riv_info["n_cells"],
            "coverage_reaches_placed": riv_info["coverage_reaches_placed"],
            "coverage_source_reaches": riv_info["coverage_source_reaches"],
            "min_retained_weight_ratio": riv_info["min_retained_weight_ratio"],
            "n_reaches_below_warn_ratio": len(riv_info["reaches_below_warn_ratio"]),
            "reaches_below_warn_ratio": riv_info["reaches_below_warn_ratio"],
            "coarse_riv_net_flux_m3d": coarse_riv_flux,
            "refined_riv_net_flux_m3d": refined_riv_flux,
            "riv_net_flux_ratio": (
                float(refined_riv_flux / coarse_riv_flux)
                if coarse_riv_flux not in (0, None) else None
            ),
        },
        "heads": [float(h) for h in np.asarray(heads).reshape(-1)],
    }
    # NaN-safe manifest (Finding 2): a NaN/Inf anywhere in the caller fields
    # (a non-finite head, flux, or near-field stat) is invalid JSON and must
    # never be silently serialized -- reject it here BEFORE the write.
    _assert_json_finite(caller_fields)
    manifest = mio.freeze_flow_spec(spec, npz_path, caller_fields=caller_fields)
    return manifest


# =============================================================================
# Thin CLI.
# =============================================================================
def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate, validate, and freeze the M2a.0 no-doublet golden "
            "baseline flow artifact for a student group (default group 0)."
        ),
    )
    parser.add_argument("--group", type=int, default=GOLDEN_GROUP)
    parser.add_argument("--reruns", type=int, default=5)
    parser.add_argument(
        "--mother-model", default=None,
        help="Calibrated MF6 workspace (default: model_io_utils.ensure_flow_model()).",
    )
    parser.add_argument("--out-dir", default=str(_DEFAULT_GOLDEN_DIR))
    parser.add_argument("--work-dir", default=None)
    parser.add_argument("--child-timeout", type=float, default=DEFAULT_CHILD_TIMEOUT_S)
    return parser


def main(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        manifest = generate_group0_golden(
            mother_model=args.mother_model,
            work_dir=args.work_dir,
            out_dir=args.out_dir,
            reruns=args.reruns,
            group=args.group,
            child_timeout_s=args.child_timeout,
        )
    except Exception as e:  # noqa: BLE001 -- CLI boundary: report, don't crash
        print(f"error: {e}", file=sys.stderr)
        return 1

    npz_path = Path(args.out_dir) / f"group{args.group}_flow.npz"
    print(json.dumps({
        "status": "OK", "npz": str(npz_path), "aggregate_hash": manifest.get("aggregate_hash"),
    }))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == _CHILD_FLAG:
        sys.exit(_child_refine_main(sys.argv[2:]))
    else:
        sys.exit(main())
