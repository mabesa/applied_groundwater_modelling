#!/usr/bin/env python
"""
================================================================================
 M2b.1 -- case-study FLOW student viz + metrics-primitives + sandbox module
================================================================================

Support module for the M2b group-0 student flow template (M2b.3). Callers
pass ALREADY-SOLVED "state_result" dicts -- what
``casestudy_flow_builder.build_flow_state`` / ``build_all_flow_states``
return: ``gwf`` (flopy GWF; ``gwf.modelgrid`` is a flopy VertexGrid/DISV),
``heads``, ``spec``, ``headfile``, ``budgetfile``, ``grid_hash``,
``package_hashes``, ``diagnostics``, ``diagnostics_file``, ``workspace``,
``state``, ``group``.

Three groups of functions:

* DISV plotting (flopy ``PlotMapView`` on ``gwf.modelgrid``; NaN-safe;
  aspect-equal; flat-cell overlays) -- ``plot_head_map``,
  ``plot_difference_map``, ``plot_budget_bars``.
* Data-extraction PRIMITIVES the notebook TODO composes into metrics --
  ``heads_of``, ``difference``, ``cell_areas``, ``active_domain_mask``,
  ``free_head_mask``, ``budget_components``, ``read_diagnostics``,
  ``emit_equalization_json``, ``summarize_metrics``, ``write_flow_metrics``,
  ``save_fig``.
* A reusable metric-RECIPE registry (``FLOW_METRIC_RECIPES``) -- the
  instructor/M3c reference surface, NOT auto-applied in the student path.
* A scenario SANDBOX helper (``explore_scenario``) -- the ONLY function in
  this module that may run MF6 (via the public
  ``casestudy_flow_common.assemble_flow_state``), always into an isolated
  ``work_dir/_sandbox/<type>_<paramhash>/`` workspace.

NaN-safety (a recurring bug class in this repo): MF6 dry/inactive sentinel
heads (``hdry``/``hnoflo``, typically +-1e30) are mapped to ``np.nan`` by
``heads_of`` -- never left as a giant-magnitude finite number that could
silently sail through a ``<``/``<=`` gate or a max/sum reduction.

`uv run` for everything (see CLAUDE.md).
================================================================================
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

# sys.path wiring so the module imports the same way notebooks/pytest do.
_SRC_DIR = str(Path(__file__).resolve().parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import flopy  # noqa: E402

import casestudy_flow_builder as cfb  # noqa: E402
import casestudy_flow_common as cfc  # noqa: E402
import casestudy_flow_scenarios as scn  # noqa: E402
import casestudy_refine_riv as crr  # noqa: E402
import casestudy_equalization_metrics as cem  # noqa: E402

StateResult = Dict[str, Any]

# MF6 dry/inactive sentinel heads (hdry/hnoflo) are typically +-1e30; any head
# whose magnitude clears this threshold is treated as a sentinel, never a real
# head value.
_SENTINEL_ABS_THRESHOLD_M = 1e20

# Internal/structured CBC records that carry no boundary "q" flux (the intercell
# face flows + specific-discharge + saturation FMI arrays). These MUST be
# skipped by budget_components -- they have no ``q`` field (a cast would fail)
# and would otherwise pollute the per-component totals.
_INTERNAL_BUDGET_TEXTS = frozenset(
    {"FLOW-JA-FACE", "DATA-SPDIS", "DATA-SAT", "STO-SS", "STO-SY"}
)

# Fallback boundary-flow whitelist used ONLY when the enabled-package set cannot
# be derived from the state's gwf (no ``gwf`` on the result, or an empty derived
# set). A real GWF state derives the exact set from its packages instead.
_BOUNDARY_WHITELIST = frozenset(
    {"RIV", "WEL", "CHD", "RCH", "RCHA", "GHB", "DRN", "EVT", "EVTA"}
)


# =============================================================================
# DISV plotting (flopy PlotMapView; Agg-safe when the caller sets the Agg
# backend; aspect-equal; NaN-safe; flat-cell overlays).
# =============================================================================
def _fig_ax(ax=None):
    """Return ``(fig, ax)`` -- a NEW figure+axes if *ax* is None, else the
    figure that owns *ax*."""
    if ax is None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
    else:
        fig = ax.figure
    return fig, ax


def _flat_cells(cellids: Optional[Iterable[Any]]) -> List[int]:
    """Sorted unique FLAT icell ids from a spec ``(layer, icell)`` cellid
    list (CHD/RIV/WEL representation) -- never row/col."""
    if not cellids:
        return []
    return sorted({int(c[1]) for c in cellids})


def _maybe_contour(pmv, arr: np.ndarray, **kwargs):
    """NaN-safe DISV contour helper. flopy's ``contour_array`` triangulates the
    cell centers, which matplotlib cannot contour when either (a) too few cells
    carry a finite value to form a triangle, or (b) the finite values have zero
    range (a flat field has no contour levels). SKIP only those genuinely
    non-contourable cases (return ``None``); any OTHER error (mismatched array
    length, ...) is a real bug and is allowed to propagate -- never swallowed by
    a broad ``except``."""
    values = np.asarray(arr, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size < 3:
        return None
    if float(np.max(finite)) == float(np.min(finite)):
        return None  # flat field -> no increasing contour levels
    return pmv.contour_array(arr, **kwargs)


def _add_bc_overlays(ax, state_result: StateResult) -> None:
    """Scatter RIV/CHD/WEL cells at their FLAT-cell centers (never row/col)."""
    modelgrid = state_result["gwf"].modelgrid
    spec = state_result["spec"]
    xc = np.asarray(modelgrid.xcellcenters).reshape(-1)
    yc = np.asarray(modelgrid.ycellcenters).reshape(-1)

    riv = _flat_cells(spec.get("riv_cellid"))
    chd = _flat_cells(spec.get("chd_cellid"))
    wel = _flat_cells(spec.get("wel_cellid"))

    if riv:
        ax.scatter(xc[riv], yc[riv], marker="s", color="tab:blue", s=24,
                   label="RIV", zorder=3)
    if chd:
        ax.scatter(xc[chd], yc[chd], marker="D", color="tab:green", s=24,
                   label="CHD", zorder=3)
    if wel:
        ax.scatter(xc[wel], yc[wel], marker="^", color="tab:red", s=36,
                   label="WEL", zorder=3)


def plot_head_map(
    state_result: StateResult, *, ax=None, title: Optional[str] = None,
    contour: bool = True, overlays: bool = True,
):
    """Filled head map (+ optional NaN-safe contours + BC overlays) for one
    solved flow state, on ``state_result['gwf'].modelgrid`` AS-IS (no manual
    rotation -- the modelgrid already carries xoff/yoff/angrot/CRS). Returns
    ``(fig, ax)``."""
    heads = heads_of(state_result)
    modelgrid = state_result["gwf"].modelgrid
    fig, ax = _fig_ax(ax)
    pmv = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax)
    pmv.plot_array(heads, cmap="viridis")
    if contour:
        _maybe_contour(pmv, heads, colors="black", linewidths=0.6)
    if overlays:
        _add_bc_overlays(ax, state_result)
    ax.set_aspect("equal")
    if title:
        ax.set_title(title)
    return fig, ax


def plot_difference_map(state_b: StateResult, state_a: StateResult, *, ax=None,
                         title: Optional[str] = None):
    """(b - a) head-difference map on the SHARED grid, diverging colormap
    centered on 0. Raises ``ValueError`` if the two states' ``grid_hash``
    differ. Returns ``(fig, ax)``."""
    diff = difference(state_b, state_a)  # asserts grid_hash equality
    modelgrid = state_b["gwf"].modelgrid
    fig, ax = _fig_ax(ax)
    pmv = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax)
    finite = diff[np.isfinite(diff)]
    vmax = float(np.max(np.abs(finite))) if finite.size else 1.0
    vmax = vmax if vmax > 0 else 1.0
    pmv.plot_array(diff, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    _maybe_contour(pmv, diff, colors="black", linewidths=0.6)
    ax.set_aspect("equal")
    if title:
        ax.set_title(title)
    return fig, ax


def plot_budget_bars(state_result: StateResult, *, ax=None):
    """Signed inflow/outflow-by-component bar chart (from
    :func:`budget_components`). Returns ``(fig, ax)``."""
    df = budget_components(state_result)
    fig, ax = _fig_ax(ax)
    colors = ["tab:blue" if v >= 0 else "tab:red" for v in df["net_m3d"]]
    ax.bar(df["component"], df["net_m3d"], color=colors)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_ylabel("Net flux (m3/d)")
    return fig, ax


# =============================================================================
# Data-extraction PRIMITIVES.
# =============================================================================
def heads_of(state_result: StateResult) -> np.ndarray:
    """1-D head array (ncpl), NaN-safe: MF6 dry/inactive sentinel heads
    (``hdry``/``hnoflo``, typically +-1e30) AND any non-finite value are
    mapped to ``np.nan`` -- never left as a sentinel a ``<``/``<=`` gate could
    silently misread."""
    heads = np.asarray(state_result["heads"], dtype=float).reshape(-1).copy()
    bad = ~np.isfinite(heads) | (np.abs(heads) >= _SENTINEL_ABS_THRESHOLD_M)
    heads[bad] = np.nan
    return heads


def _assert_same_grid(state_b: StateResult, state_a: StateResult) -> None:
    if state_a["grid_hash"] != state_b["grid_hash"]:
        raise ValueError(
            "casestudy_flow_viz: grid_hash mismatch "
            f"({state_a['grid_hash']!r} != {state_b['grid_hash']!r}) -- the two "
            "states must share the SAME grid to be differenced/plotted together"
        )


def difference(state_b: StateResult, state_a: StateResult) -> np.ndarray:
    """Element-wise head difference ``heads(b) - heads(a)`` on the shared
    grid. Raises ``ValueError`` if ``state_a['grid_hash'] != state_b['grid_hash']``."""
    _assert_same_grid(state_b, state_a)
    return heads_of(state_b) - heads_of(state_a)


def cell_areas(state_result: StateResult) -> np.ndarray:
    """Per-cell area (m^2), one per flat icell, from the VertexGrid polygon
    geometry (reuses ``casestudy_refine_riv.refined_cell_polygons`` -- the
    same primitive ``casestudy_flow_common.refined_cell_sizes`` uses)."""
    polys = crr.refined_cell_polygons(state_result["spec"]["gridprops"])
    return np.array([p.area for p in polys], dtype=float)


def active_domain_mask(state_result: StateResult) -> np.ndarray:
    """Boolean ``idomain != 0`` -- whole-domain area/budget-scope metrics."""
    idomain = np.asarray(state_result["spec"]["idomain"]).reshape(-1)
    return idomain != 0


def free_head_mask(state_result: StateResult) -> np.ndarray:
    """Boolean ACTIVE-and-NOT-CHD mask -- the mask for drawdown/head/gradient
    metrics (CHD heads are pinned by the boundary condition, so they must be
    excluded from a head-RESPONSE statistic)."""
    mask = active_domain_mask(state_result).copy()
    chd = _flat_cells(state_result["spec"].get("chd_cellid"))
    if chd:
        mask[np.array(chd, dtype=int)] = False
    return mask


def _record_name(raw_name: Any) -> str:
    if isinstance(raw_name, (bytes, bytearray)):
        return raw_name.decode(errors="ignore").strip()
    return str(raw_name).strip()


def _boundary_texts(state_result: StateResult) -> Optional[frozenset]:
    """The set of BOUNDARY budget texts this state's CBC should carry, derived
    from the enabled packages of the state's ``gwf`` (via the builder's
    ``_expected_boundary_texts``). Returns ``None`` when it cannot be derived
    (no ``gwf`` on the result, or an empty set) -- the caller then falls back to
    :data:`_BOUNDARY_WHITELIST`."""
    gwf = state_result.get("gwf")
    if gwf is None:
        return None
    try:
        texts = cfb._expected_boundary_texts(gwf)
    except Exception:
        return None
    return frozenset(texts) or None


def budget_components(state_result: StateResult) -> pd.DataFrame:
    """Tidy DataFrame of SIGNED per-component NET fluxes (RIV/WEL/CHD/RCHA/...)
    read from the state's CBC (``flopy.utils.CellBudgetFile``), for the LAST
    timestep. A clean, sign-correct alternative to the noisy
    ``model_io_utils.format_budget_summary`` table (students hand-compute
    discharge-component CHANGES from this). Columns: ``component``,
    ``net_m3d`` (MF6 convention: positive = flow INTO the aquifer).

    A real MF6 CBC also carries INTERNAL/structured records (``FLOW-JA-FACE``,
    ``DATA-SPDIS``, ``DATA-SAT``) that have no boundary ``q`` field -- these are
    SKIPPED (they would fail the cast / pollute the totals). Only boundary-flow
    records are returned: the enabled-package set derived from the state's
    ``gwf`` when available, else the :data:`_BOUNDARY_WHITELIST` fallback; and
    every record must expose a ``q`` field to be counted."""
    cbc = flopy.utils.CellBudgetFile(str(state_result["budgetfile"]))
    names = cbc.get_unique_record_names()
    times = cbc.get_times()
    if not times:
        raise RuntimeError("budget_components: CBC has no recorded time steps")
    last_time = times[-1]

    allowed = _boundary_texts(state_result)

    rows = []
    for raw_name in names:
        name = _record_name(raw_name)
        if name in _INTERNAL_BUDGET_TEXTS:
            continue
        if allowed is not None:
            if name not in allowed:
                continue
        elif name not in _BOUNDARY_WHITELIST:
            continue
        data = cbc.get_data(text=raw_name, totim=last_time)
        if not data:
            continue
        # boundary records expose a structured ``q`` field; anything else
        # (an internal array that slipped the name filters) is skipped, never
        # cast blindly into the totals.
        flows: List[np.ndarray] = []
        has_q = True
        for arr in data:
            if hasattr(arr, "dtype") and arr.dtype.names and "q" in arr.dtype.names:
                flows.append(np.asarray(arr["q"], dtype=float).reshape(-1))
            else:
                has_q = False
                break
        if not has_q:
            continue
        flat = np.concatenate(flows) if flows else np.array([], dtype=float)
        rows.append({"component": name, "net_m3d": float(np.sum(flat)) if flat.size else 0.0})

    df = pd.DataFrame(rows, columns=["component", "net_m3d"])
    return df.sort_values("component").reset_index(drop=True)


def read_diagnostics(state_result: StateResult) -> Dict[str, Any]:
    """Load the builder-emitted ``diagnostics.<state>.json`` for this state."""
    return json.loads(Path(state_result["diagnostics_file"]).read_text())


def emit_equalization_json(
    group: int, state_iii_result: StateResult, *, out_dir,
) -> Dict[str, Any]:
    """Thin wrapper over the EXISTING M2a.4
    ``casestudy_equalization_metrics.{emit_equalization_metrics,
    write_equalization_metrics}``: the builder does NOT itself write the
    equalization JSON (its state-iii return only carries the INPUTS --
    ``response_metrics``/``gradient_inputs``/``runtime_s``). Computes the 3
    obligations from *state_iii_result*, writes
    ``equalization_metrics.<group>.json`` under *out_dir*, and returns the
    metrics dict (the authoritative cross-check for ``river_leakage_change`` +
    ``gradient_change`` ONLY -- not the other student metrics)."""
    metrics = cem.emit_equalization_metrics(int(group), state_iii_result)
    cem.write_equalization_metrics(int(group), metrics, out_dir)
    return metrics


def summarize_metrics(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """Tidy DataFrame from student ``{name, value, unit}`` metric rows."""
    df = pd.DataFrame(list(rows), columns=["name", "value", "unit"])
    return df


def write_flow_metrics(group: int, rows: Iterable[Dict[str, Any]], *, out_dir) -> Dict[str, Path]:
    """Emit ``flow_metrics.group<N>.{csv,json}`` -- the concrete student
    metric artifact (distinct from the equalization JSON). Returns
    ``{"csv": path, "json": path}``."""
    rows = list(rows)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"flow_metrics.group{int(group)}.csv"
    json_path = out_dir / f"flow_metrics.group{int(group)}.json"
    summarize_metrics(rows).to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(rows, indent=2, default=str, sort_keys=True) + "\n")
    return {"csv": csv_path, "json": json_path}


def save_fig(fig, name: str, *, out_dir) -> Path:
    """Save *fig* to ``<out_dir>/figs/<name>.png`` (deterministic, whatever
    backend is active). Returns the path."""
    out_dir = Path(out_dir)
    figs_dir = out_dir / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    stem = name[:-4] if name.lower().endswith(".png") else name
    path = figs_dir / f"{stem}.png"
    fig.savefig(path, dpi=150)
    return path


# =============================================================================
# Reusable metric RECIPES (instructor/M3c reference surface -- NOT
# auto-applied in the student TODO path; students hand-compose from the
# primitives above). Each entry documents: unit, which mask, a one-line doc,
# and a ``compute(state_b, state_a)`` callable used ONLY by tests / M3c / the
# group-0 demo self-check.
# =============================================================================
def recipe_max_drawdown_m(state_b: StateResult, state_a: StateResult) -> float:
    """max |head change| (b - a) over FREE (active, non-CHD) cells."""
    mask = free_head_mask(state_a)
    vals = difference(state_b, state_a)[mask]
    finite = vals[np.isfinite(vals)]
    return float(np.max(np.abs(finite))) if finite.size else float("nan")


def recipe_area_drawdown_gt_0p5m_m2(
    state_b: StateResult, state_a: StateResult, *, threshold_m: float = 0.5,
) -> float:
    """Area-weighted sum of FREE-cell area where |head change| exceeds
    *threshold_m* (area-weighted drawdown -- NOT the broad active-area rule)."""
    mask = free_head_mask(state_a)
    diff = difference(state_b, state_a)
    areas = cell_areas(state_a)
    responding = mask & np.isfinite(diff) & (np.abs(diff) > threshold_m)
    return float(np.sum(areas[responding]))


def recipe_river_leakage_change_m3d(state_b: StateResult, state_a: StateResult) -> float:
    """Change in the whole-model net RIV (river<->aquifer) flux, b - a (no
    cell mask -- a whole-model budget total)."""
    net_a = budget_components(state_a).set_index("component")["net_m3d"]
    net_b = budget_components(state_b).set_index("component")["net_m3d"]
    return float(net_b.get("RIV", 0.0) - net_a.get("RIV", 0.0))


def _gradient_at(state_result: StateResult, *, from_cell: int) -> Optional[float]:
    """(head_at ``from_cell`` - head_at nearest ACTIVE RIV cell) / distance,
    reusing the builder's ``nearest_riv_cell`` primitive. ``None`` (censored)
    if there is no active RIV cell / zero distance / a non-finite head."""
    spec = state_result["spec"]
    modelgrid = state_result["gwf"].modelgrid
    riv_cell, dist = cfb.nearest_riv_cell(int(from_cell), spec, modelgrid)
    if riv_cell is None or not np.isfinite(dist) or dist == 0.0:
        return None
    heads = heads_of(state_result)
    h_from, h_riv = heads[int(from_cell)], heads[int(riv_cell)]
    if not (np.isfinite(h_from) and np.isfinite(h_riv)):
        return None
    return float((h_from - h_riv) / dist)


def _resolved_extraction_cell(state_b: StateResult, state_a: StateResult) -> Optional[int]:
    """The resolved EXTRACTION cell from the doublet metadata carried on a
    wells/scenario state result (``state['doublet']['extraction']['cell']``);
    checks *state_b* then *state_a*. ``None`` if neither carries the doublet."""
    for st in (state_b, state_a):
        doublet = st.get("doublet")
        if isinstance(doublet, dict):
            ext = doublet.get("extraction")
            if isinstance(ext, dict) and ext.get("cell") is not None:
                return int(ext["cell"])
    return None


def recipe_gradient_toward_river_change(
    state_b: StateResult, state_a: StateResult, *, from_cell: Optional[int] = None,
) -> Optional[float]:
    """Change in the (head_at_extraction - head_at_nearest_river)/distance
    gradient, b - a. *from_cell* defaults to the RESOLVED EXTRACTION cell from
    the doublet metadata (the builder's authoritative gradient receptor -- NOT
    ``well_cells[0]``, which is an arbitrary background well). ``from_cell``
    MUST be a free-head cell (active, non-CHD) per this recipe's mask.
    ``None`` (censored) if either state's gradient is censored."""
    if from_cell is None:
        from_cell = _resolved_extraction_cell(state_b, state_a)
        if from_cell is None:
            raise ValueError(
                "recipe_gradient_toward_river_change: no doublet metadata on "
                "either state to resolve the extraction cell -- pass from_cell "
                "explicitly (the authoritative receptor is the extraction cell)"
            )
    from_cell = int(from_cell)
    if not free_head_mask(state_a)[from_cell]:
        raise ValueError(
            f"recipe_gradient_toward_river_change: from_cell {from_cell} is not a "
            "free-head cell (it is inactive or a CHD cell) -- the gradient "
            "receptor must be a free (active, non-CHD) cell"
        )
    g_a = _gradient_at(state_a, from_cell=from_cell)
    g_b = _gradient_at(state_b, from_cell=from_cell)
    if g_a is None or g_b is None:
        return None
    return g_b - g_a


def recipe_discharge_component_change(
    state_b: StateResult, state_a: StateResult,
) -> Dict[str, float]:
    """Per-component signed net-flux CHANGE (b - a), from
    :func:`budget_components` (whole-model fluxes, no cell mask)."""
    net_a = budget_components(state_a).set_index("component")["net_m3d"]
    net_b = budget_components(state_b).set_index("component")["net_m3d"]
    components = sorted(set(net_a.index) | set(net_b.index))
    return {c: float(net_b.get(c, 0.0) - net_a.get(c, 0.0)) for c in components}


FLOW_METRIC_RECIPES: Dict[str, Dict[str, Any]] = {
    "max_drawdown_m": {
        "unit": "m",
        "mask": "free_head_mask",
        "doc": "max |head change| (state_b - state_a) over free (active, non-CHD) cells",
        "compute": recipe_max_drawdown_m,
    },
    "area_drawdown_gt_0p5m_m2": {
        "unit": "m2",
        "mask": "free_head_mask + cell_areas",
        "doc": (
            "area-weighted sum of free-cell area where |head change| > 0.5 m "
            "(NOT the broad active-area rule)"
        ),
        "compute": recipe_area_drawdown_gt_0p5m_m2,
    },
    "river_leakage_change_m3d": {
        "unit": "m3/d",
        "mask": "budget_components (no cell mask; whole-model signed RIV net flux)",
        "doc": "change in the net RIV (river<->aquifer) flux, state_b - state_a",
        "compute": recipe_river_leakage_change_m3d,
    },
    "gradient_toward_river_change": {
        "unit": "dimensionless",
        "mask": (
            "free_head_mask (from_cell = resolved extraction cell, asserted "
            "free-head; receptor = nearest active RIV cell)"
        ),
        "doc": (
            "change in (head_at_extraction - head_at_nearest_river)/distance, "
            "state_b - state_a"
        ),
        "compute": recipe_gradient_toward_river_change,
    },
    "discharge_component_change": {
        "unit": "m3/d",
        "mask": "budget_components (no cell mask; whole-model signed per-component fluxes)",
        "doc": "per-component net-flux change (state_b - state_a) from budget_components",
        "compute": recipe_discharge_component_change,
    },
}


# =============================================================================
# Scenario SANDBOX helper (exploratory; the ONLY function here that may solve
# MF6 -- via the PUBLIC assemble_flow_state, never the private
# _solve_validate_scenario / build_flow_state(state='wells_plus_scenario'),
# so the frozen scenario EXPECTATION gate is bypassed while every physics gate
# (convergence/finite/mass-balance/no-dry/same-grid, via assemble_flow_state
# + the identity assertions below) stays intact).
# =============================================================================
# The RAISE-severity flow diagnostics the sandbox re-checks after a solve (the
# same correctness gates the builder enforces) -- everything EXCEPT the frozen
# scenario expectation, which the sandbox deliberately bypasses.
_SANDBOX_PHYSICS_GATES = ("flow_convergence", "flow_mass_balance", "finite_heads",
                          "flow_no_dry_cells")


def _assert_sandbox_physics(built: Dict[str, Any], scen_spec: Dict[str, Any], *,
                            scenario_type: str) -> None:
    """Keep EVERY physics gate the builder applies (convergence / mass balance /
    finite heads / no-dry-cells), computed by reusing the builder's own
    ``_emit_flow_diagnostics``; RAISE if any RAISE-severity gate fails. Does NOT
    enforce the frozen scenario EXPECTATION (that is the one gate a free sandbox
    bypasses)."""
    if not built["converged"]:
        raise RuntimeError(
            f"explore_scenario({scenario_type!r}): the sandbox solve did NOT "
            f"converge -- see the listing in the _sandbox workspace"
        )
    diagnostics = cfb._emit_flow_diagnostics(
        converged=built["converged"], heads=built["heads"],
        botm=scen_spec["botm"], gwf=built["gwf"], head_delta=None,
    )
    failed = [g for g in _SANDBOX_PHYSICS_GATES if not diagnostics[g]["passed"]]
    if failed:
        raise RuntimeError(
            f"explore_scenario({scenario_type!r}): physics gate(s) {failed} "
            "failed on the sandbox solve -- refusing to return an invalid model "
            "(the sandbox bypasses ONLY the frozen scenario expectation, never "
            "the correctness gates)"
        )


def _assert_grid_identity_unchanged(scen_spec: Dict[str, Any], baseline_spec: Dict[str, Any]) -> None:
    """Cheap PRE-assembly guard: the value-only scenario transforms must never
    touch ncpl or idomain. (Full assembled-grid geometry -- vertices/cell2d/
    top/botm -- is asserted AFTER assembly against the SOLVED model via
    ``casestudy_flow_builder._assert_solved_grid_is_canonical``.)"""
    if int(scen_spec["ncpl"]) != int(baseline_spec["ncpl"]):
        raise RuntimeError(
            "explore_scenario: ncpl changed vs the canonical baseline -- grid "
            "identity violated (apply_scenario must only mutate package VALUES)"
        )
    if not np.array_equal(
        np.asarray(scen_spec["idomain"]).reshape(-1), np.asarray(baseline_spec["idomain"]).reshape(-1),
    ):
        raise RuntimeError(
            "explore_scenario: idomain changed vs the canonical baseline -- grid "
            "identity violated"
        )


def explore_scenario(
    group: int, scenario_type: str, params: Dict[str, Any], *, work_dir,
    base_states: Optional[Dict[str, Any]] = None, run: bool = True,
) -> Dict[str, Any]:
    """Exploratory scenario sandbox: vary a scenario's parameters BEYOND the
    group's fixed graded assignment, on the CANONICAL baseline + the resolved
    doublet, WITHOUT the frozen-expectation gate that
    ``build_flow_state(state='wells_plus_scenario')`` self-enforces.

    Uses PUBLIC APIs only: ``casestudy_flow_scenarios.apply_scenario`` on the
    canonical ``base_states['baseline']['spec']``, the RESOLVED doublet from
    ``base_states['wells_only']`` (added ONCE via the ``extra_wells`` seam --
    never re-resolved, never double-added), and
    ``casestudy_flow_common.assemble_flow_state`` into an ISOLATED
    ``work_dir/_sandbox/<type>_<paramhash>/`` workspace (never overwrites the
    graded ``wells_plus_scenario`` artifacts).

    Keeps EVERY physics gate the builder applies: when ``run`` is True the
    sandbox solve is checked for convergence, mass balance, finite heads, and
    no-dry-cells (via ``casestudy_flow_builder._emit_flow_diagnostics``) and
    RAISES if any fails. Bypasses ONLY the frozen hydro-reasoning expectation
    table (never invoked here) -- an expectation-VIOLATING param does not raise;
    that is the point of a free sandbox. Grid identity is asserted twice: a
    cheap ncpl/idomain PRE-check, then the full assembled-model geometry
    (vertices/cell2d/top/botm) against the canonical baseline via
    ``casestudy_flow_builder._assert_solved_grid_is_canonical`` -- only THEN is
    the baseline ``grid_hash`` stamped on the result.

    The doublet is added ONCE via the ``extra_wells`` seam and the returned
    ``spec`` merges that ASSEMBLED (background + doublet) WEL back in (via the
    builder's ``_spec_with_assembled_wel``), so ``spec['well_cells']`` and the
    WEL overlays reflect the doublet actually installed.

    ``run=False`` assembles (writes the MF6 input files, incl. the merged WEL)
    WITHOUT solving -- the unit-test seam (``heads``/``converged`` are ``None``;
    the physics gates are skipped, the grid-geometry assertion still runs).

    Returns a state_result-shaped dict (``gwf``, ``heads``, ``spec``,
    ``headfile``, ``budgetfile``, ``grid_hash``, ``workspace``, ...) +
    ``exploratory: True`` + the scenario ``params`` -- the same
    plotting/primitives apply to it.
    """
    if base_states is None:
        base_states = cfb.build_all_flow_states(int(group), work_dir=work_dir)

    baseline_spec = base_states["baseline"]["spec"]
    wells = base_states["wells_only"]
    doublet = wells["doublet"]
    Q = float(wells["resolved_Q"])
    inj_cell = int(doublet["injection"]["cell"])
    ext_cell = int(doublet["extraction"]["cell"])

    scen_spec = scn.apply_scenario(baseline_spec, scenario_type, params)
    _assert_grid_identity_unchanged(scen_spec, baseline_spec)

    # geometry-identity hash, computed from the UNMUTATED baseline spec (the
    # scenario mutates package VALUES, not the grid) -- same convention the
    # builder uses for its state-iii ``grid_hash``.
    grid_hash, _ = cfc.spec_canonical_hashes(baseline_spec)
    canonical_grid_hash = base_states.get("grid_hash") or base_states["baseline"]["grid_hash"]
    if grid_hash != canonical_grid_hash:
        raise RuntimeError(
            "explore_scenario: the baseline spec's hash does not match "
            "base_states['grid_hash'] -- base_states looks stale/inconsistent"
        )

    params = dict(params)
    paramhash = hashlib.sha256(
        json.dumps(params, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    sandbox_dir = Path(work_dir) / "_sandbox" / f"{scenario_type}_{paramhash[:12]}"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    sim_name = f"sbx_{scenario_type}_{paramhash[:8]}"
    model_name = ("sbx" + paramhash[:8])[:16]  # MF6 modelname <= 16 chars

    built = cfc.assemble_flow_state(
        scen_spec, workspace=sandbox_dir, sim_name=sim_name, model_name=model_name,
        extra_wells=[((0, inj_cell), +Q), ((0, ext_cell), -Q)],
        run=run, raise_on_failure=False,
    )

    # KEEP all physics gates (convergence/mass-balance/finite/no-dry); bypass
    # ONLY the frozen scenario expectation. Skipped when not solving (run=False).
    if run:
        _assert_sandbox_physics(built, scen_spec, scenario_type=scenario_type)

    # Full assembled-grid geometry MUST equal the canonical baseline (the
    # value-only transforms preserve geometry; the package aggregate hash
    # legitimately changes, so compare GEOMETRY, not the aggregate). Reuses the
    # builder's solved-grid-identity check -- works with or without a solve
    # (the DISV package is written during assembly regardless).
    cfb._assert_solved_grid_is_canonical(
        built, baseline_spec, group=int(group), state="exploratory",
    )

    # Merge the ASSEMBLED (background + doublet) WEL back into the returned spec
    # so well_cells / WEL overlays reflect the doublet added once (HIGH-2).
    returned_spec = cfb._spec_with_assembled_wel(scen_spec, built)

    return {
        "gwf": built["gwf"],
        "sim": built["sim"],
        "gwf_name": built["model_name"],
        "heads": built["heads"],
        "spec": returned_spec,
        "headfile": built["headfile"],
        "budgetfile": built["budgetfile"],
        "grid_hash": grid_hash,
        "workspace": str(Path(sandbox_dir).resolve()),
        "state": "exploratory",
        "group": int(group),
        "converged": built["converged"],
        "doublet": doublet,
        "exploratory": True,
        "scenario_type": scenario_type,
        "params": params,
    }
