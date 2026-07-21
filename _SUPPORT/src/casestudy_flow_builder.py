#!/usr/bin/env python
"""
================================================================================
 M2a.1 — reusable case-study FLOW BUILDER (baseline state (i)) + diagnostics
================================================================================

`build_flow_state(group, state='baseline', *, work_dir)` — the reusable
case-study flow builder. On the corridor-refined steady single-layer DISV
grid it builds + solves the baseline flow state (background wells, faithful
river, NO doublet) via the NEUTRAL flow-package factory
(`casestudy_flow_common.assemble_flow_state`), emits the M1.4 diagnostics
surface (`diagnostics.baseline.json`), and returns a RICH metadata dict the
transport coupling (M3) and the state-(iii) interface (M2a.5) bind to.

This is the module the M2a.0 golden generator deliberately does NOT import
(independence): both build the SAME baseline via the shared
`casestudy_flow_common` primitives, and the COMMITTED golden
(`_SUPPORT/src/golden/group0_flow.{npz,manifest.json}`) is the regression
oracle the builder is pinned to (see `test_casestudy_flow_builder.py`).

Scope (M2a.2): state (i) baseline + state (ii) wells_only (the group's
flow-only geothermal doublet) + its 50% half-rate sensitivity, for all 9
groups. The doublet is added via the neutral factory's ``extra_wells`` seam;
the drawdown reference is the SAME-grid state-(i) solve. State (iii)
scenarios are M2a.3.

`uv run` for everything (see CLAUDE.md).
================================================================================
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

# sys.path wiring so the module imports the same way notebooks/pytest do.
_SRC_DIR = str(Path(__file__).resolve().parent)
_SCRIPTS_DIR = str(Path(__file__).resolve().parent / "scripts")
for _p in (_SRC_DIR, _SCRIPTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import model_io_utils as mio  # noqa: E402
import casestudy_flow_common as cfc  # noqa: E402
import casestudy_diagnostics as cd  # noqa: E402
import casestudy_flow_scenarios as scn  # noqa: E402
import case_utils as cu  # noqa: E402

Group = Any

# States this builder can build: (i) baseline (M2a.1) + (ii) wells_only + its
# 50% half-rate sensitivity (M2a.2) + (iii) wells_plus_scenario (M2a.3).
SUPPORTED_STATES = ("baseline", "wells_only", "wells_plus_scenario")

# Default flow config (scenarios.options[id=N]); the state-iii scenario params
# are read from it, never hard-coded.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_FLOW_CONFIG = _REPO_ROOT / "PROJECT" / "workspace" / "template" / "case_config.yaml"

# Doublet magnitude PER WELL (m3/d) + the half-rate sensitivity factor.
DOUBLET_Q_M3D = cfc.DOUBLET_Q_M3D  # 4320 (inj +Q, ext -Q); half = 0.5*Q
# Signed head-direction sanity tolerance at the doublet cells (m): << the
# expected ~metre drawdown, so a real response clears it but numerical noise
# never spuriously satisfies the wrong sign.
HEAD_DIRECTION_TOL_M = 1e-3
# Per-role incremental WEL-flux match tolerance (m3/d): WEL is a specified-flux
# BC, so (state-ii - state-i) at the doublet cell equals Q' to solver round-off.
WEL_FLUX_TOL_M3D = 1e-6

# The 5 FLOW diagnostics (M1.4 ids) this builder emits for a flow state.
FLOW_DIAGNOSTIC_IDS = (
    "flow_convergence",
    "flow_mass_balance",
    "finite_heads",
    "flow_no_dry_cells",
    "flow_head_delta",
)

# The rich metadata dict `build_flow_state` returns (the explicit contract).
BUILD_RESULT_KEYS = (
    "gwf", "heads", "spec", "diagnostics", "workspace", "sim", "gwf_name",
    "headfile", "budgetfile", "grid_hash", "stress_period", "units",
    "package_hashes",
)

# The transport-facing state-(iii) interface (declared here, asserted @ M2a.5).
STATE_III_INTERFACE_KEYS = (
    "state_id", "grid_hash", "headfile", "budgetfile", "gwf_name",
    "stress_period", "units", "no_regridding",
)

# Steady single-period metadata (matches the 05f/refined TDIS).
STRESS_PERIOD = {
    "nper": 1,
    "steady": True,
    "perioddata": [[1.0, 1, 1]],
    "time_units": cfc.FLOW_TIME_UNITS,
}
UNITS = {"length": cfc.FLOW_LENGTH_UNITS, "time": "days", "crs": "EPSG:2056"}

_DRY_TOL_M = 1e-6


def _mass_balance_percent(gwf) -> float:
    """|PERCENT ERROR| of the flow budget (via ``format_budget_summary``)."""
    df = mio.format_budget_summary(gwf)
    return abs(float(df.loc["PERCENT ERROR", "Net (m3/d)"]))


def _emit_flow_diagnostics(
    *, converged: bool, heads, botm, gwf, head_delta=None,
) -> Dict[str, Dict[str, Any]]:
    """Compute the M1.4 ``{id: entry}`` flow-diagnostics surface for a solved
    flow state. ``flow_head_delta`` is NULL for baseline (the baseline IS the
    reference states (ii)/(iii) compare against -- NOT a faked zero
    self-reference); for a wells state it is the drawdown ``max |state(ii) -
    state(i) baseline head|`` on the SAME grid (passed via *head_delta*).
    """
    heads_arr = np.asarray(heads, dtype=float).reshape(-1) if heads is not None else None
    # NaN-fragility gate (Finding 4): `NaN < botm` is False, so a non-finite
    # head would silently count as NOT dry. Only count dry cells on a finite
    # field; a non-finite field trips finite_heads (raise-severity) and the
    # builder aborts.
    finite = bool(heads_arr is not None and np.all(np.isfinite(heads_arr)))
    if heads_arr is not None and finite:
        botm_arr = np.asarray(botm, dtype=float).reshape(-1)
        n_dry = int(np.count_nonzero(heads_arr < (botm_arr - _DRY_TOL_M)))
    else:
        n_dry = 0
    # Mass balance is read from the BUDGET (independent of head finiteness), so
    # compute it whenever the run converged. Clamp any non-finite / unreadable
    # result to a large FINITE sentinel that clearly fails the <=1% gate and
    # keeps the diagnostics JSON strict (allow_nan=False) -- never inf/nan.
    raw_pct = _mass_balance_percent(gwf) if converged else float("inf")
    mass_pct = float(raw_pct) if np.isfinite(raw_pct) else 1e30

    return {
        "flow_convergence": cd.evaluate("flow_convergence", bool(converged)),
        "flow_mass_balance": cd.evaluate("flow_mass_balance", mass_pct),
        "finite_heads": cd.evaluate("finite_heads", finite),
        "flow_no_dry_cells": cd.evaluate("flow_no_dry_cells", n_dry),
        # NULL for baseline (no reference state -> nullable passes); the
        # same-grid drawdown max|Δhead| for a wells state.
        "flow_head_delta": cd.evaluate("flow_head_delta", head_delta),
    }


# The committed/frozen per-group baseline goldens live alongside the modules.
_GOLDEN_DIR = Path(cfc.__file__).resolve().parent / "golden"


def _frozen_golden_manifest(group) -> Any:
    """Return the frozen ``group<N>_flow`` golden manifest dict if one exists
    in the golden dir, else ``None`` (a walker group with no committed pin)."""
    p = _GOLDEN_DIR / f"group{group}_flow.manifest.json"
    return json.loads(p.read_text()) if p.exists() else None


# --- M2a.5: Linux-golden-or-deferral anchoring (review #3, Codex #5) --------
ALL_GROUPS = tuple(range(9))
DEFERRAL_KEYS = (
    "group", "reason", "platform", "mf6_version", "date",
    "radius_walked", "authoritative_platform", "status",
)


def _deferral_path(group) -> Path:
    return _GOLDEN_DIR / f"group{group}_flow.deferral.json"


def _load_deferral(group) -> Any:
    """Return the committed ``group<N>_flow.deferral.json`` dict if present,
    else ``None``. A deferral marks a group whose AUTHORITATIVE (Linux) golden
    is pending -- it builds+validates locally at a walked radius but SIGILLs /
    cannot be frozen on macOS-arm64."""
    p = _deferral_path(group)
    return json.loads(p.read_text()) if p.exists() else None


def assert_all_groups_anchored(groups=ALL_GROUPS) -> Dict[str, Any]:
    """Every group MUST be anchored by EXACTLY ONE of a committed golden XOR a
    committed deferral artifact (review #3, Codex #5). FAIL if a group has
    NEITHER or BOTH. Distinguishes provisional-macOS goldens (which still need
    a Linux re-verify) from authoritative ones, and reports the groups still
    pending the hub: the deferred groups (need a Linux golden) + the
    provisional goldens (need a Linux re-verify).
    """
    authoritative, provisional, deferrals, problems = [], [], [], []
    for g in groups:
        manifest = _frozen_golden_manifest(g)
        deferral = _load_deferral(g)
        has_golden, has_deferral = manifest is not None, deferral is not None
        if has_golden == has_deferral:  # neither, or both
            problems.append(
                f"group {g}: has "
                f"{'BOTH a golden AND a deferral' if has_golden else 'NEITHER a golden nor a deferral'}"
                f" -- exactly one (golden XOR deferral) is required"
            )
            continue
        if has_golden:
            if manifest.get("provisional"):
                provisional.append(g)
            else:
                authoritative.append(g)
        else:
            missing = [k for k in DEFERRAL_KEYS if k not in deferral]
            if missing:
                problems.append(f"group {g}: deferral missing keys {missing}")
            # Codex REWORK #5: validate the VALUES, not just key presence.
            if not missing and int(deferral.get("group")) != int(g):
                problems.append(
                    f"group {g}: deferral group field {deferral.get('group')!r} != {g}"
                )
            rw = deferral.get("radius_walked")
            if not (isinstance(rw, (int, float)) and not isinstance(rw, bool) and rw > 0):
                problems.append(
                    f"group {g}: deferral radius_walked {rw!r} is not a positive number"
                )
            if deferral.get("authoritative_platform") != "linux":
                problems.append(
                    f"group {g}: deferral authoritative_platform "
                    f"{deferral.get('authoritative_platform')!r} != 'linux'"
                )
            if deferral.get("status") != "linux-pending":
                problems.append(
                    f"group {g}: deferral status {deferral.get('status')!r} != 'linux-pending'"
                )
            deferrals.append(g)
    if problems:
        raise AssertionError("group anchoring failed: " + "; ".join(problems))
    return {
        "anchored": True,
        "authoritative_goldens": authoritative,
        "provisional_goldens": provisional,
        "deferrals": deferrals,
        "hub_pending": {
            "deferred_need_linux_golden": deferrals,
            "provisional_need_linux_reverify": provisional,
        },
    }


def _pin_built_grid_to_frozen_golden(group, spec, riv_info, refine_radius) -> None:
    """Finding 4: if a FROZEN golden exists for *group*, the builder's built
    grid MUST reproduce it -- the canonical package (grid) hashes, the
    faithful-RIV hash, and the refine radius must all MATCH the committed
    manifest, or FAIL loudly. This pins EVERY frozen group (not just group 0)
    to its golden, so a builder walk that lands on a different grid than the
    committed artifact can never slip through unnoticed.
    """
    manifest = _frozen_golden_manifest(group)
    if manifest is None:
        return  # walker / not-frozen group -> nothing to pin against
    agg, arr = cfc.spec_canonical_hashes(spec)
    problems: List[str] = []
    if agg != manifest["aggregate_hash"]:
        problems.append(f"aggregate_hash {agg[:12]}.. != golden {manifest['aggregate_hash'][:12]}..")
    if arr != manifest["array_hashes"]:
        problems.append("canonical package (array) hashes differ from the golden")
    if riv_info["hash"] != manifest["faithful_riv"]["hash"]:
        problems.append(
            f"faithful_riv hash {riv_info['hash'][:12]}.. != golden "
            f"{manifest['faithful_riv']['hash'][:12]}.."
        )
    golden_radius = float(manifest.get("radius_used", refine_radius))
    if abs(float(refine_radius) - golden_radius) > 1e-9:
        problems.append(f"refine radius {refine_radius} != golden {golden_radius}")
    if problems:
        raise RuntimeError(
            f"group {group}: the built grid DIVERGED from the committed/frozen "
            f"golden (_SUPPORT/src/golden/group{group}_flow.*): "
            + "; ".join(problems)
            + ". Refusing to build state ii on a grid that does not match the "
            "frozen artifact this group is pinned to."
        )


def _spec_with_assembled_wel(base_spec: Dict[str, Any], assembled: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow copy of *base_spec* whose WEL (``wel_cellid``/``wel_rate``/
    ``well_cells``) is REPLACED by the COMBINED (background + doublet)
    canonicalized WEL that ``assemble_flow_state`` actually built. Used so the
    state-ii/iii ``package_hashes`` describe the packages the model REALLY
    solved (with the doublet), not the pre-assemble background-only WEL."""
    s = dict(base_spec)
    s["wel_cellid"] = assembled["wel_cellid"]
    s["wel_rate"] = assembled["wel_rate"]
    s["well_cells"] = assembled["well_cells"]
    return s


def _refine_solve_baseline_walk(group, workspace, *, sim_name, model_name=None) -> Dict[str, Any]:
    """Load 05f + GIS, then WALK the corridor refine radii; at each radius
    build the baseline spec (faithful RIV) AND solve the baseline flow model,
    returning the FIRST radius whose refine + solve BOTH succeed (converged +
    finite heads).

    The walk dodges both a Triangle abort / all-overbank RIV reach (a PYTHON
    exception in the refine) AND the macOS mf6-6.7.0 SOLVE SIGILL (which
    surfaces as a non-converged run for the specific grid). A walked group is
    valid for state ii even though it is NON-FREEZABLE (the golden determinism
    gate rejects a walk). Group 0 succeeds at the FIRST radius (70) -> its
    baseline is byte-identical to M2a.1. A fatal IN-PROCESS refine SIGILL is
    still uncatchable -- the CALLER must subprocess-isolate for such a group.

    Returns ``{spec, riv_info, refine_radius, refine_points, base_built}``.
    Raises ``RuntimeError`` (a DEFERRAL, naming the per-radius reasons) if no
    radius refines+solves on this platform.
    """
    mother = mio.ensure_flow_model()
    _sim, cgwf = cfc.load_coarse_model(mother)
    coarse_heads = cgwf.output.head().get_data().flatten()
    boundary_gdf, river_gdf = cfc.load_gis(mother)
    refine_points = cfc.group_refine_points(group)

    attempts: List[str] = []
    for radius in cfc.REFINE_RADII:
        try:
            spec, riv_info = cfc.build_baseline_spec(
                cgwf, boundary_gdf, river_gdf, refine_points, coarse_heads,
                refine_radius=radius,
            )
        except Exception as e:  # Triangle abort / all-overbank RIV reach / etc.
            attempts.append(f"r={radius:g} refine:{type(e).__name__}")
            continue
        built = cfc.assemble_flow_state(
            spec, workspace=workspace, sim_name=sim_name, model_name=model_name,
            raise_on_failure=False,
        )
        heads = built["heads"]
        if built["converged"] and heads is not None and np.all(np.isfinite(heads)):
            # Finding 4: a FROZEN group's built grid must match its golden.
            _pin_built_grid_to_frozen_golden(group, spec, riv_info, float(radius))
            return {
                "spec": spec, "riv_info": riv_info, "refine_radius": float(radius),
                "refine_points": refine_points, "base_built": built,
            }
        attempts.append(f"r={radius:g} solve:non-converged/SIGILL")
    raise RuntimeError(
        f"group {group}: baseline could not refine+solve at ANY radius "
        f"{cfc.REFINE_RADII} (attempts: {attempts}) -- DEFERRED (needs Linux/hub)"
    )


def _rich_result(*, built, spec, riv_info, grid_hash, package_hashes, diagnostics,
                 diag_file, work_dir, state, group, extra) -> Dict[str, Any]:
    """Assemble the rich metadata dict (BUILD_RESULT_KEYS + extras) from a
    solved state; assert the required contract keys are present."""
    result: Dict[str, Any] = {
        "gwf": built["gwf"],
        "heads": built["heads"],
        "spec": spec,
        "diagnostics": diagnostics,
        "workspace": str(Path(work_dir).resolve()),
        "sim": built["sim"],
        "gwf_name": built["model_name"],
        "headfile": built["headfile"],
        "budgetfile": built["budgetfile"],
        "grid_hash": grid_hash,
        "stress_period": dict(STRESS_PERIOD),
        "units": dict(UNITS),
        "package_hashes": package_hashes,
        "state": state,
        "group": int(group),
        "riv_info": riv_info,
        "diagnostics_file": str(Path(diag_file).resolve()),
    }
    result.update(extra)
    missing = [k for k in BUILD_RESULT_KEYS if k not in result]
    if missing:
        raise AssertionError(f"build_flow_state result missing required keys: {missing}")
    return result


def build_flow_state(
    group: Group, state: str = "baseline", *, half_rate: bool = False, work_dir,
    allow_independent_grid: bool = False, _canonical_walk=None,
) -> Dict[str, Any]:
    """Build + solve the corridor-refined steady flow state for *group* and
    return the rich metadata dict (see :data:`BUILD_RESULT_KEYS`).

    Parameters
    ----------
    group : int
        Student group id (0-8).
    state : str
        ``"baseline"`` (state i, background wells only), ``"wells_only"``
        (state ii, background + the group's flow-only geothermal doublet), or
        ``"wells_plus_scenario"`` (state iii, state ii + the group's scenario
        transform from the flow config, on the SAME grid). Any other value
        raises ``NotImplementedError``.
    half_rate : bool
        Only valid for ``state='wells_only'``: solve the 50% pumping-
        sensitivity variant (doublet at +-0.5*Q). ``diagnostics.<state>.json``
        gets the ``_halfrate`` suffix.
    work_dir : str or Path
        Directory for the assembled MF6 files + the ``diagnostics.<state>.json``.

    Returns
    -------
    dict
        BUILD_RESULT_KEYS + extras. For ``wells_only``: ``doublet`` (resolved
        inj/ext cells), ``resolved_Q``, ``half_rate``, ``head_delta_max_m``
        (same-grid drawdown), ``doublet_head_delta`` (per-role Δhead),
        ``incremental_flux`` (per-role wells-baseline WEL flux), ``baseline_heads``.

    Raises
    ------
    NotImplementedError
        For any unsupported *state*.
    ValueError
        ``half_rate=True`` on a non-wells state, or a doublet placement failure.
    RuntimeError
        Non-convergence / non-finite heads / a failed state-ii invariant.
    """
    if state not in SUPPORTED_STATES:
        raise NotImplementedError(
            f"build_flow_state: state {state!r} is not supported "
            f"(supported: {SUPPORTED_STATES}); state (iii)/scenarios are M2a.3"
        )
    if half_rate and state != "wells_only":
        raise ValueError("half_rate is only valid for state='wells_only'")

    # ---- RUNTIME FENCE (Codex REWORK #1) --------------------------------
    # A NON-baseline state on an UNPINNED group (no committed golden) walks its
    # own grid; two such independent calls can land on DIFFERENT grids, making
    # cross-state comparisons invalid. Block it unless reached via the
    # sanctioned single-walk path OR explicitly opted into a standalone grid.
    if state != "baseline" and _canonical_walk is not _CANONICAL_WALK and not allow_independent_grid:
        if _frozen_golden_manifest(group) is None:  # unpinned
            raise RuntimeError(
                f"build_flow_state(group={group}, state={state!r}): group {group} is "
                "UNPINNED (no committed golden), so independent non-baseline builds can "
                "land on DIFFERENT walked grids across calls -- cross-state comparisons "
                "would be invalid. Use build_all_flow_states(group) for ONE canonical "
                "grid, or pass allow_independent_grid=True to accept a standalone grid."
            )

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    if state == "baseline":
        walk = _refine_solve_baseline_walk(group, work_dir, sim_name=f"group{group}_baseline")
        return _finalize_baseline_state(group, walk, work_dir)
    # states ii + iii both build on ONE grid (the walk's own baseline solve).
    # runtime (M2a.4) = the flow build+solve wall-clock for the group's M2a
    # states -- a METRIC on the RETURN only, NEVER hashed/frozen.
    _t0 = time.perf_counter()
    walk = _refine_solve_baseline_walk(
        group, work_dir / "_baseline_ref",
        sim_name=f"group{group}_baseline_ref", model_name=f"g{group}_base_ref",
    )
    if state == "wells_only":
        return _solve_validate_wells(group, walk, work_dir, half_rate=half_rate)
    # wells_plus_scenario (state iii): needs state ii (wells) as the drawdown
    # reference, solved on the SAME grid.
    wells = _solve_validate_wells(group, walk, work_dir, half_rate=False)
    result = _solve_validate_scenario(group, walk, wells, work_dir)
    result["runtime_s"] = float(time.perf_counter() - _t0)
    return result


def build_wells_states(group: Group, *, work_dir) -> Dict[str, Any]:
    """Build state (ii) at FULL and HALF rate on ONE grid (Finding 5).

    A single refine+solve WALK builds the grid + the shared baseline reference
    ONCE; the full-rate and half-rate doublet states are then BOTH solved on
    that identical grid, so the drawdown (vs the same baseline) and the
    ``half |Δh| < full |Δh|`` comparison are rigorously same-grid for EVERY
    group (not just group 0). Asserts full/half/baseline share one grid hash.

    Returns ``{"full": <rich result>, "half": <rich result>, "grid_hash",
    "refine_radius"}``.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    walk = _refine_solve_baseline_walk(
        group, work_dir / "_baseline_ref",
        sim_name=f"group{group}_baseline_ref", model_name=f"g{group}_base_ref",
    )
    full = _solve_validate_wells(group, walk, work_dir, half_rate=False)
    half = _solve_validate_wells(group, walk, work_dir, half_rate=True)
    # same-grid guarantee (one walk) -> identical grid hashes; assert it.
    base_hash, _ = cfc.spec_canonical_hashes(walk["spec"])
    if not (full["grid_hash"] == half["grid_hash"] == base_hash):
        raise RuntimeError(
            f"group {group}: full/half/baseline grid hashes differ "
            f"({full['grid_hash'][:12]} / {half['grid_hash'][:12]} / "
            f"{base_hash[:12]}) -- the half<full comparison would be invalid"
        )
    if not (half["head_delta_max_m"] < full["head_delta_max_m"]):
        raise RuntimeError(
            f"group {group}: half-rate drawdown {half['head_delta_max_m']:.4f} m "
            f"is not < full-rate {full['head_delta_max_m']:.4f} m on the same grid"
        )
    return {
        "full": full, "half": half, "grid_hash": base_hash,
        "refine_radius": walk["refine_radius"],
    }


# ---------------------------------------------------------------------------
# M2a.5 -- single-walk ALL-STATES orchestration (review #2, Codex #1/#2).
#
# FENCE (RUNTIME-ENFORCED, not just documented -- Codex REWORK #1):
# ``build_all_flow_states`` is the SOLE all-states orchestration. It builds ONE
# canonical discretization (a single refine+solve walk) and solves EVERY state
# -- (i) baseline, (ii) wells_only, (ii-half) half-rate, (iii)
# wells_plus_scenario -- on that IDENTICAL grid, asserting the grid identity
# (refine_radius + grid_hash, + the frozen golden hash for a pinned group) is
# invariant across all four states, checked BEFORE and AFTER each solve.
#
# For an UNPINNED (walker) group -- one with no committed golden -- issuing
# separate ``build_flow_state`` calls runs an INDEPENDENT walk per call, which
# can land on a DIFFERENT radius/grid, so cross-state comparisons (drawdown,
# scenario response) would silently compare across grids. ``build_flow_state``
# therefore RAISES on a NON-baseline state for an unpinned group UNLESS it is
# reached through the sanctioned single-walk path (the ``_canonical_walk``
# token) or the caller passes ``allow_independent_grid=True`` to accept a
# standalone grid. Pinned groups are exempt (the golden-pin forces one grid).
# The ``TestFence*`` tests in ``test_casestudy_flow_m2a5.py`` guard this.
# ---------------------------------------------------------------------------
ALL_STATE_KEYS = ("baseline", "wells_only", "wells_only_half", "wells_plus_scenario")

# Private sentinel: the token the single-walk orchestration passes to prove a
# non-baseline ``build_flow_state`` call is reached through the sanctioned
# canonical grid (never constructible by an external caller).
_CANONICAL_WALK = object()


def build_all_flow_states(group: Group, *, work_dir) -> Dict[str, Any]:
    """Single-walk ALL-STATES orchestration (M2a.5, review #2 + Codex #1/#2).

    ONE refine+solve walk builds the grid ONCE; its gridprops/idomain/
    refine_radius are FROZEN and the EXACT same discretization (``walk['spec']``)
    is passed into each state's own workspace+solve -- NO state re-runs
    refinement / snapping / active-domain generation. Emits:

    * ``baseline``            -- state (i), the walk's baseline solve
    * ``wells_only``          -- state (ii), full-rate doublet
    * ``wells_only_half``     -- state (ii), half-rate doublet
    * ``wells_plus_scenario`` -- state (iii), scenario transform

    ASSERTS ``refine_radius`` + ``grid_hash`` are EQUAL across all four states
    (and == the committed golden's aggregate hash for a frozen group), checked
    BEFORE and AFTER each solve (grid-input invariance). Returns
    ``{baseline, wells_only, wells_only_half, wells_plus_scenario, grid_hash,
    refine_radius, runtime_s}``.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    _t0 = time.perf_counter()

    # ONE canonical walk -> the single discretization for ALL states.
    walk = _refine_solve_baseline_walk(
        group, work_dir / "_baseline_ref",
        sim_name=f"group{group}_baseline_ref", model_name=f"g{group}_base_ref",
    )
    # FREEZE the canonical grid identity BEFORE any state solve. The aggregate
    # canonical hash over the baseline spec covers gridprops + idomain + the
    # baseline package arrays -- any grid-input mutation changes it, so it is
    # our before/after invariance witness.
    canonical_hash, _ = cfc.spec_canonical_hashes(walk["spec"])
    canonical_radius = float(walk["refine_radius"])
    golden = _frozen_golden_manifest(group)
    if golden is not None and canonical_hash != golden["aggregate_hash"]:
        raise RuntimeError(
            f"group {group}: walked grid hash {canonical_hash[:12]} != committed "
            f"golden {golden['aggregate_hash'][:12]} -- single-walk grid is not the frozen grid"
        )

    def _assert_grid(state_name: str, res: Dict[str, Any]) -> None:
        if res["grid_hash"] != canonical_hash:
            raise RuntimeError(
                f"group {group}: state {state_name!r} grid hash {res['grid_hash'][:12]} "
                f"!= canonical {canonical_hash[:12]} -- states did NOT solve one grid"
            )
        if float(res.get("refine_radius", canonical_radius)) != canonical_radius:
            raise RuntimeError(
                f"group {group}: state {state_name!r} refine_radius "
                f"{res.get('refine_radius')} != canonical {canonical_radius}"
            )
        # AFTER-solve grid-input invariance: the shared spec must be untouched.
        post_hash, _ = cfc.spec_canonical_hashes(walk["spec"])
        if post_hash != canonical_hash:
            raise RuntimeError(
                f"group {group}: canonical grid spec MUTATED during state "
                f"{state_name!r} solve ({post_hash[:12]} != {canonical_hash[:12]})"
            )

    baseline = _finalize_baseline_state(group, walk, work_dir)
    _assert_grid("baseline", baseline)
    wells = _solve_validate_wells(group, walk, work_dir, half_rate=False)
    _assert_grid("wells_only", wells)
    half = _solve_validate_wells(group, walk, work_dir, half_rate=True)
    _assert_grid("wells_only_half", half)
    scenario = _solve_validate_scenario(group, walk, wells, work_dir)
    _assert_grid("wells_plus_scenario", scenario)

    states = {
        "baseline": baseline, "wells_only": wells,
        "wells_only_half": half, "wells_plus_scenario": scenario,
    }
    hashes = {s["grid_hash"] for s in states.values()}
    if len(hashes) != 1:
        raise RuntimeError(
            f"group {group}: the four states did not share ONE grid hash: "
            f"{sorted(h[:12] for h in hashes)}"
        )
    runtime_s = float(time.perf_counter() - _t0)
    # Attach the per-group runtime to the state-(iii) result (M1.5 `runtime`
    # metric consumer); the band is M3c's.
    scenario["runtime_s"] = runtime_s
    return {
        **states,
        "grid_hash": canonical_hash,
        "refine_radius": canonical_radius,
        "runtime_s": runtime_s,
    }


def _finalize_baseline_state(group, walk, work_dir) -> Dict[str, Any]:
    """State (i): the walk's baseline solve. Emits ``diagnostics.baseline.json``
    (``flow_head_delta`` NULL). Byte-compatible with the M2a.1 baseline path
    (group 0 -> first radius 70)."""
    spec, riv_info, built = walk["spec"], walk["riv_info"], walk["base_built"]
    diagnostics = _emit_flow_diagnostics(
        converged=built["converged"], heads=built["heads"],
        botm=spec["botm"], gwf=built["gwf"], head_delta=None,
    )
    diag_file = work_dir / "diagnostics.baseline.json"
    diag_file.write_text(json.dumps(diagnostics, indent=2, allow_nan=False, sort_keys=True) + "\n")
    # the walk already guaranteed converged + finite; re-assert defensively.
    if not diagnostics["finite_heads"]["passed"]:
        raise RuntimeError(
            f"build_flow_state(group={group}, state='baseline'): non-finite "
            f"head(s); diagnostics {diag_file}"
        )
    grid_hash, package_hashes = cfc.spec_canonical_hashes(spec)
    return _rich_result(
        built=built, spec=spec, riv_info=riv_info, grid_hash=grid_hash,
        package_hashes=package_hashes, diagnostics=diagnostics, diag_file=diag_file,
        work_dir=work_dir, state="baseline", group=group,
        extra={"refine_radius": walk["refine_radius"]},
    )


_GRID_COORD_TOL_M = 1e-6  # near-exact: same grid round-trips to <<1 um


def _row_values(row):
    """Normalise a gridprops row (python list/tuple) OR a solved-model DISV
    recarray record to a plain python list of its field values."""
    return list(row.tolist()) if hasattr(row, "tolist") else list(row)


def _norm_vertices(vlist):
    """[(ivert:int, xv:float, yv:float), ...] from a vertices list or the
    solved model's ``disv.vertices.array`` recarray."""
    out = []
    for r in vlist:
        v = _row_values(r)
        out.append((int(v[0]), float(v[1]), float(v[2])))
    return out


def _norm_cell2d(clist):
    """[(icell2d:int, xc:float, yc:float, ncvert:int, iverts:tuple[int]), ...].

    FORMAT-FLEXIBLE (fail-safe against a flopy recarray-shape change): handles
    BOTH representations of the vertex-index columns --
    * FLATTENED ``(icell2d, xc, yc, ncvert, iv0, iv1, ...)`` -- the current
      solved-model recarray (short cells padded with None in the extra
      ``icvert_*`` columns; take exactly the first ``ncvert``), and
    * NESTED ``(icell2d, xc, yc, ncvert, [iv0, iv1, ...])`` -- a single
      list/array field of indices.
    """
    out = []
    for r in clist:
        c = _row_values(r)
        icell2d, xc, yc, ncvert = int(c[0]), float(c[1]), float(c[2]), int(c[3])
        if len(c) == 5 and isinstance(c[4], (list, tuple, np.ndarray)):
            verts = list(c[4])[:ncvert]  # nested single-field representation
        else:
            verts = c[4:4 + ncvert]      # flattened columns (padding truncated)
        iverts = tuple(int(v) for v in verts)
        out.append((icell2d, xc, yc, ncvert, iverts))
    return out


def _assert_solved_grid_is_canonical(built, canonical_spec, *, group, state) -> None:
    """Codex REWORK #2 (the crux): prove the state SOLVED the canonical grid,
    not a grid it re-refined internally while returning the canonical HASH.
    Reads the DISV arrays back from the SOLVED model and asserts they equal the
    canonical ``spec``'s gridprops -- not merely the CARDINALITY (ncpl, nvert,
    #vertices, #cell2d) + the per-cell arrays (idomain, top, botm), but the
    ACTUAL vertex COORDINATES and the cell2d CONNECTIVITY VALUES. A
    same-cardinality re-refinement (identical counts but different vertex
    coordinates or cell->vertex connectivity) is therefore caught too."""
    gwf = built["gwf"]
    disv = gwf.get_package("DISV")
    if disv is None:
        raise RuntimeError(f"group {group} state {state!r}: solved model has no DISV package")
    gp = canonical_spec["gridprops"]
    problems = []
    if int(np.asarray(disv.ncpl.array)) != int(canonical_spec["ncpl"]):
        problems.append(f"ncpl {int(np.asarray(disv.ncpl.array))} != {int(canonical_spec['ncpl'])}")
    if int(np.asarray(disv.nvert.array)) != int(gp["nvert"]):
        problems.append(f"nvert {int(np.asarray(disv.nvert.array))} != {int(gp['nvert'])}")
    if not np.array_equal(
        np.asarray(disv.idomain.array).reshape(-1), np.asarray(canonical_spec["idomain"]).reshape(-1)
    ):
        problems.append("idomain arrays differ")
    if not np.allclose(
        np.asarray(disv.top.array).reshape(-1), np.asarray(canonical_spec["top"]).reshape(-1),
        rtol=0, atol=1e-9,
    ):
        problems.append("top arrays differ")
    if not np.allclose(
        np.asarray(disv.botm.array).reshape(-1), np.asarray(canonical_spec["botm"]).reshape(-1),
        rtol=0, atol=1e-9,
    ):
        problems.append("botm arrays differ")

    # --- vertex COORDINATES (not just count) ---
    solved_v = _norm_vertices(disv.vertices.array)
    canon_v = _norm_vertices(gp["vertices"])
    if len(solved_v) != len(canon_v):
        problems.append(f"#vertices {len(solved_v)} != {len(canon_v)}")
    else:
        if [v[0] for v in solved_v] != [v[0] for v in canon_v]:
            problems.append("vertex ivert ordering differs")
        s_xy = np.array([[v[1], v[2]] for v in solved_v], dtype=float)
        c_xy = np.array([[v[1], v[2]] for v in canon_v], dtype=float)
        if s_xy.shape != c_xy.shape or not np.allclose(s_xy, c_xy, rtol=0, atol=_GRID_COORD_TOL_M):
            problems.append("vertex COORDINATES differ")

    # --- cell2d CONNECTIVITY + centroids (not just count) ---
    solved_c = _norm_cell2d(disv.cell2d.array)
    canon_c = _norm_cell2d(gp["cell2d"])
    if len(solved_c) != len(canon_c):
        problems.append(f"#cell2d {len(solved_c)} != {len(canon_c)}")
    else:
        # icell2d, ncvert and the vertex-index tuple must match EXACTLY.
        s_conn = [(c[0], c[3], c[4]) for c in solved_c]
        c_conn = [(c[0], c[3], c[4]) for c in canon_c]
        if s_conn != c_conn:
            problems.append("cell2d CONNECTIVITY (vertex indices) differ")
        s_xy = np.array([[c[1], c[2]] for c in solved_c], dtype=float)
        c_xy = np.array([[c[1], c[2]] for c in canon_c], dtype=float)
        if s_xy.shape != c_xy.shape or not np.allclose(s_xy, c_xy, rtol=0, atol=_GRID_COORD_TOL_M):
            problems.append("cell2d centroid coordinates differ")

    if problems:
        raise RuntimeError(
            f"group {group} state {state!r}: SOLVED model grid != canonical grid "
            f"({'; '.join(problems)}) -- the state did NOT solve the one canonical grid"
        )


def _assemble_state_solve(
    spec, *, work_dir, sim_name, model_name, extra_wells, group, state_label, canonical_spec=None,
) -> Dict[str, Any]:
    """Assemble+solve one non-baseline state under the M2a.5 coherence guards
    (Codex REWORK #2/#3/#4):

    * #3 -- DEEP-COPY the spec so the state can NEVER mutate the shared canonical
      grid (not even transiently);
    * #4 -- solve in a FRESH per-state workspace and DELETE any pre-existing
      CBC/HDS first, so a stale binary from an earlier solve cannot be mistaken
      for this run's output; then assert the CBC/HDS were (re)written AFTER the
      run start (mtime freshness);
    * #2 -- verify the SOLVED model grid == the canonical grid.

    Returns the ``assemble_flow_state`` ``built`` dict (from the fresh ws)."""
    canonical_spec = spec if canonical_spec is None else canonical_spec
    ws = Path(work_dir) / f"_state_{sim_name}"
    ws.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.cbc", "*.hds"):
        for stale in ws.glob(pattern):
            stale.unlink()
    spec_copy = copy.deepcopy(spec)  # #3: shared grid is untouchable
    run_start = time.time()
    built = cfc.assemble_flow_state(
        spec_copy, workspace=ws, sim_name=sim_name, model_name=model_name,
        extra_wells=extra_wells, raise_on_failure=False,
    )
    # #4: freshness -- the declared CBC/HDS must exist and be NEWER than the run
    # start (allowing a small slack for coarse filesystem mtime granularity).
    if built["converged"]:
        for kind, path in (("budget", built["budgetfile"]), ("head", built["headfile"])):
            p = Path(path)
            if not p.exists():
                raise RuntimeError(
                    f"group {group} {state_label}: converged but {kind} file missing: {p}"
                )
            if p.stat().st_mtime < run_start - 2.0:
                raise RuntimeError(
                    f"group {group} {state_label}: {kind} file {p} is STALE "
                    f"(mtime {p.stat().st_mtime:.3f} < run start {run_start:.3f}) -- "
                    "not this run's output"
                )
    # #2: the solved model must be the canonical grid (guards a helper that
    # re-refined internally but returned the canonical hash).
    _assert_solved_grid_is_canonical(built, canonical_spec, group=group, state=state_label)
    return built


def _solve_validate_wells(group, walk, work_dir, *, half_rate) -> Dict[str, Any]:
    """State (ii): background + the flow-only doublet, solved on the SAME
    built grid as the walk's baseline solve; enforces the strengthened
    state-ii invariants and emits ``diagnostics.wells_only[_halfrate].json``.

    Reused for BOTH the full-rate and half-rate variants against ONE walk, so
    they share the identical grid + baseline reference (see
    ``build_wells_states``)."""
    spec, riv_info, refine_points = walk["spec"], walk["riv_info"], walk["refine_points"]
    base_built = walk["base_built"]  # SAME-grid baseline reference (already solved)
    wells_state = "wells_only_halfrate" if half_rate else "wells_only"
    heads_i = np.asarray(base_built["heads"], dtype=float)

    # (b) Resolve + validate the doublet cells against the BUILT grid.
    doublet = cfc.resolve_doublet_cells(spec, base_built["modelgrid"], refine_points)
    inj_cell = doublet["injection"]["cell"]
    ext_cell = doublet["extraction"]["cell"]
    Q = float(cfc.DOUBLET_Q_M3D) * (0.5 if half_rate else 1.0)

    # (c) State (ii) solve on the SAME grid: doublet inj +Q / ext -Q. Short
    # MODELNAME (<=16 chars); descriptive OC file names via sim_name. Solved in
    # a FRESH per-state workspace on a DEEP-COPY of the canonical spec, with the
    # solved-grid-identity + CBC/HDS freshness guards (Codex REWORK #2/#3/#4).
    wells_model = f"g{group}_wells" + ("_half" if half_rate else "")
    wells_built = _assemble_state_solve(
        spec, work_dir=work_dir, sim_name=f"group{group}_{wells_state}",
        model_name=wells_model,
        extra_wells=[((0, inj_cell), +Q), ((0, ext_cell), -Q)],
        group=group, state_label=wells_state,
    )
    converged = wells_built["converged"]
    heads_ii = np.asarray(wells_built["heads"], dtype=float) if wells_built["heads"] is not None else None

    # Finding 3 (recurring NaN class): finite-check heads_ii BEFORE computing
    # head_delta -- np.max on a NaN field yields a NaN head_delta that would
    # RAISE on the strict-JSON (allow_nan=False) write, instead of cleanly
    # emitting the M1.4 diagnostic. Only compute the drawdown on a finite
    # field; else head_delta stays None (null in the diagnostic) and
    # finite_heads=False trips the abort below.
    finite_ii = bool(converged and heads_ii is not None and np.all(np.isfinite(heads_ii)))
    head_delta = float(np.max(np.abs(heads_ii - heads_i))) if finite_ii else None
    diagnostics = _emit_flow_diagnostics(
        converged=converged, heads=heads_ii, botm=spec["botm"],
        gwf=wells_built["gwf"], head_delta=head_delta,
    )
    diag_file = work_dir / f"diagnostics.{wells_state}.json"
    diag_file.write_text(json.dumps(diagnostics, indent=2, allow_nan=False, sort_keys=True) + "\n")

    if not converged:
        raise RuntimeError(
            f"build_flow_state(group={group}, state={wells_state!r}): did not "
            f"converge -- see {wells_built['headfile']} listing; diagnostics {diag_file}"
        )
    if not diagnostics["finite_heads"]["passed"]:
        raise RuntimeError(
            f"build_flow_state(group={group}, state={wells_state!r}): non-finite "
            f"head(s); diagnostics {diag_file}"
        )

    # ---- STRENGTHENED state-ii invariants -------------------------------
    # (1) per-role INCREMENTAL WEL flux (wells - same-grid baseline) == +-Q.
    flux_i = cfc.wel_flux_by_cell(base_built["gwf"])
    flux_ii = cfc.wel_flux_by_cell(wells_built["gwf"])
    inj_incr = flux_ii.get(inj_cell, 0.0) - flux_i.get(inj_cell, 0.0)
    ext_incr = flux_ii.get(ext_cell, 0.0) - flux_i.get(ext_cell, 0.0)
    if abs(inj_incr - Q) > WEL_FLUX_TOL_M3D:
        raise RuntimeError(
            f"group {group} {wells_state}: injection-cell incremental WEL flux "
            f"{inj_incr:.6f} != +Q ({Q}) m3/d"
        )
    if abs(ext_incr + Q) > WEL_FLUX_TOL_M3D:
        raise RuntimeError(
            f"group {group} {wells_state}: extraction-cell incremental WEL flux "
            f"{ext_incr:.6f} != -Q ({-Q}) m3/d"
        )

    # (2) WEL package-entry assertions (combined-canonicalized cellids/rates):
    # the doublet cell rate == baseline background rate at that cell + doublet.
    base_wel = {int(c[1]): float(r) for c, r in zip(spec["wel_cellid"], spec["wel_rate"])}
    wells_wel = {int(c[1]): float(r) for c, r in zip(wells_built["wel_cellid"], wells_built["wel_rate"])}
    for role, cell, signed_q in (("injection", inj_cell, +Q), ("extraction", ext_cell, -Q)):
        expected = base_wel.get(cell, 0.0) + signed_q
        if cell not in wells_wel or abs(wells_wel[cell] - expected) > WEL_FLUX_TOL_M3D:
            raise RuntimeError(
                f"group {group} {wells_state}: {role} cell {cell} WEL entry "
                f"{wells_wel.get(cell)!r} != baseline+doublet {expected!r} "
                "(combined-canonicalization mismatch)"
            )

    # (3) head-direction sanity (signed tol) at the doublet cells.
    dh_inj = float(heads_ii[inj_cell] - heads_i[inj_cell])
    dh_ext = float(heads_ii[ext_cell] - heads_i[ext_cell])
    if not (dh_inj > +HEAD_DIRECTION_TOL_M):
        raise RuntimeError(
            f"group {group} {wells_state}: injection head Δ={dh_inj:.4f} m not "
            f"> +{HEAD_DIRECTION_TOL_M} m (injection should RAISE head)"
        )
    if not (dh_ext < -HEAD_DIRECTION_TOL_M):
        raise RuntimeError(
            f"group {group} {wells_state}: extraction head Δ={dh_ext:.4f} m not "
            f"< -{HEAD_DIRECTION_TOL_M} m (extraction should DROP head)"
        )

    # (4) mass balance < 1% + no dry cells (the diagnostics gate them).
    if not diagnostics["flow_mass_balance"]["passed"]:
        raise RuntimeError(f"group {group} {wells_state}: flow mass balance gate failed")
    if not diagnostics["flow_no_dry_cells"]["passed"]:
        raise RuntimeError(f"group {group} {wells_state}: dry cells present")

    # grid_hash = geometry identity (plain baseline spec, still == golden).
    # The ASSEMBLED spec has the COMBINED (background + doublet) canonicalized
    # WEL that MF6 actually solved -- so both result['spec'] and package_hashes
    # describe the real forcing (not the pre-assemble background-only WEL).
    assembled_spec = _spec_with_assembled_wel(spec, wells_built)
    grid_hash, _ = cfc.spec_canonical_hashes(spec)
    _, package_hashes = cfc.spec_canonical_hashes(assembled_spec)
    return _rich_result(
        built=wells_built, spec=assembled_spec, riv_info=riv_info, grid_hash=grid_hash,
        package_hashes=package_hashes, diagnostics=diagnostics, diag_file=diag_file,
        work_dir=work_dir, state=wells_state, group=group,
        extra={
            "half_rate": bool(half_rate),
            "refine_radius": walk["refine_radius"],
            "resolved_Q": Q,
            "doublet": doublet,
            "baseline_heads": heads_i,
            "head_delta_max_m": head_delta,
            "doublet_head_delta": {"injection": dh_inj, "extraction": dh_ext},
            "incremental_flux": {"injection": inj_incr, "extraction": ext_incr},
        },
    )


def _riv_net_flux(gwf) -> float:
    """SIGNED total RIV package budget flux (river-to-aquifer POSITIVE, the
    MF6 convention: q > 0 = flow into the aquifer cell)."""
    bud = gwf.output.budget()
    recs = bud.get_data(text="RIV", totim=bud.get_times()[-1])
    if not recs:
        return float("nan")
    return float(np.sum(recs[0]["q"]))


def nearest_riv_cell(ext_cell: int, spec: Dict[str, Any], modelgrid):
    """Resolve the ACTIVE refined RIV cell NEAREST to the doublet *ext_cell*
    and its separation (m) -- the aquifer->river gradient receptor (M2a.4).

    Only ACTIVE (``idomain != 0``) RIV cells are eligible: an inactive RIV cell
    that happens to be closest would give a meaningless gradient (and the
    metric would censor a valid nearest-ACTIVE river gradient). Same
    active-cell fix class as M2a.2's placement mapper. Returns
    ``(riv_cell, dist_m)``; ``(None, inf)`` if there is no ACTIVE RIV cell."""
    idom = np.asarray(spec["idomain"]).reshape(-1)
    riv_flats = sorted({int(c[1]) for c in spec["riv_cellid"]} if spec.get("riv_cellid") else set())
    riv_flats = [i for i in riv_flats if idom[i] != 0]
    if not riv_flats:
        return None, float("inf")
    xc = np.asarray(modelgrid.xcellcenters).reshape(-1)
    yc = np.asarray(modelgrid.ycellcenters).reshape(-1)
    d = np.hypot(xc[riv_flats] - xc[int(ext_cell)], yc[riv_flats] - yc[int(ext_cell)])
    j = int(np.argmin(d))
    return int(riv_flats[j]), float(d[j])


def _gradient_inputs(ext_cell, spec, modelgrid, heads_ii, heads_iii, botm):
    """The aquifer->river gradient RAW inputs (states ii + iii, SAME grid) that
    M2a.4's ``gradient_change`` obligation aggregates -- head at the extraction
    cell + head at the nearest refined RIV cell + their separation, plus the
    active/dry flags the metric censors on."""
    hii = np.asarray(heads_ii, dtype=float).reshape(-1)
    hiii = np.asarray(heads_iii, dtype=float).reshape(-1)
    botm_a = np.asarray(botm, dtype=float).reshape(-1)
    idom = np.asarray(spec["idomain"]).reshape(-1)
    riv_cell, dist = nearest_riv_cell(ext_cell, spec, modelgrid)

    def _dry(h, cell):
        return None if cell is None else bool(h[int(cell)] < (botm_a[int(cell)] - _DRY_TOL_M))

    return {
        "receptor_type": "river",
        "ext_cell": int(ext_cell),
        "riv_cell": riv_cell,
        "dist_m": dist,
        "head_ext_ii": float(hii[int(ext_cell)]),
        "head_ext_iii": float(hiii[int(ext_cell)]),
        "head_riv_ii": (None if riv_cell is None else float(hii[int(riv_cell)])),
        "head_riv_iii": (None if riv_cell is None else float(hiii[int(riv_cell)])),
        "ext_active": bool(idom[int(ext_cell)] != 0),
        "riv_active": (None if riv_cell is None else bool(idom[int(riv_cell)] != 0)),
        "ext_dry_ii": _dry(hii, ext_cell), "ext_dry_iii": _dry(hiii, ext_cell),
        "riv_dry_ii": _dry(hii, riv_cell), "riv_dry_iii": _dry(hiii, riv_cell),
    }


def _scenario_response_metrics(
    group, spec, modelgrid, heads_ii, heads_iii, gwf_ii, gwf_iii, botm,
) -> Dict[str, Any]:
    """Compute the same-grid ii->iii response metrics the frozen expectation
    table is checked against (see casestudy_flow_scenarios.evaluate_...).

    Finding 1: ALL head-response statistics (max/argmax/mean/n_responding/
    n_dry) are computed over ACTIVE cells ONLY -- the frozen table defines
    mean/spread over active cells. (The refined idomain is currently all-ones,
    so this is presently a no-op, but the masking is made EXPLICIT so an
    inactive cell can never contaminate a statistic.)"""
    idomain = np.asarray(spec["idomain"]).reshape(-1)
    active = idomain != 0
    active_idx = np.where(active)[0]  # map masked positions -> global flat index

    hii = np.asarray(heads_ii, dtype=float).reshape(-1)[active]
    hiii = np.asarray(heads_iii, dtype=float).reshape(-1)[active]
    botm_a = np.asarray(botm, dtype=float).reshape(-1)[active]
    dh = hiii - hii
    adh = np.abs(dh)
    max_abs = float(adh.max())
    imax_global = int(active_idx[int(np.argmax(adh))])  # global flat index of the argmax

    # distance from the argmax |Δh| cell (global index) to the nearest CHD/RIV cell.
    xc = np.asarray(modelgrid.xcellcenters).reshape(-1)
    yc = np.asarray(modelgrid.ycellcenters).reshape(-1)

    def _dist_to(cellids):
        flats = sorted({int(c[1]) for c in cellids})
        if not flats:
            return float("inf")
        d = np.hypot(xc[flats] - xc[imax_global], yc[flats] - yc[imax_global])
        return float(d.min())

    ampl = 0.10  # global_spread_ampl_frac (mirrors the frozen config)
    n_active = int(active_idx.size)
    n_responding = int(np.count_nonzero(adh > ampl * max_abs)) if max_abs > 0 else 0
    n_dry = int(np.count_nonzero(hiii < (botm_a - _DRY_TOL_M)))

    riv_ii = _riv_net_flux(gwf_ii)
    riv_iii = _riv_net_flux(gwf_iii)
    return {
        "max_abs_head_change": max_abs,
        "mean_head_change": float(dh.mean()),  # active-cell mean
        "argmax_dist_to_chd_m": _dist_to(spec["chd_cellid"]),
        "argmax_dist_to_riv_m": _dist_to(spec["riv_cellid"]),
        "river_to_aquifer_flux": {"ii": riv_ii, "iii": riv_iii},
        "abs_river_exchange": {"ii": abs(riv_ii), "iii": abs(riv_iii)},
        "n_active": n_active,
        "n_responding": n_responding,  # over active cells
        "n_dry_iii": n_dry,            # over active cells
        "finite_iii": bool(np.all(np.isfinite(hiii))),
    }


def _solve_validate_scenario(group, walk, wells, work_dir, *, config_path=None) -> Dict[str, Any]:
    """State (iii) wells_plus_scenario: apply the group's scenario transform to
    the state-ii spec (values-only, faithful RIV immutable) + the doublet, solve
    on the SAME grid as states i/ii, emit ``diagnostics.wells_plus_scenario.json``
    (flow_head_delta = max|state(iii) - state(ii)|), and compute the ii->iii
    response metrics for the FROZEN-expectation consistency check."""
    spec, riv_info = walk["spec"], walk["riv_info"]
    heads_ii = np.asarray(wells["heads"], dtype=float)
    doublet = wells["doublet"]
    inj_cell = doublet["injection"]["cell"]
    ext_cell = doublet["extraction"]["cell"]
    Q = float(wells["resolved_Q"])

    # scenario params from the FLOW config (never hard-coded).
    cfg_path = str(config_path) if config_path is not None else str(DEFAULT_FLOW_CONFIG)
    scenario = cu.get_scenario_for_group(cfg_path, int(group))
    if scenario is None:
        raise RuntimeError(f"group {group}: no flow scenario found in {cfg_path}")
    scenario_type = scenario["type"]

    # apply_scenario mutates the state-ii spec's package VALUES only.
    scen_spec = scn.apply_scenario(spec, scenario_type, scenario)

    # Fresh per-state workspace + deep-copy + solved-grid-identity/freshness
    # guards. The scenario mutates package VALUES only, so the SOLVED grid must
    # still equal the CANONICAL (walk) grid -- checked against ``spec``.
    scen_model = f"g{group}_scen"
    scen_built = _assemble_state_solve(
        scen_spec, work_dir=work_dir, sim_name=f"group{group}_wells_plus_scenario",
        model_name=scen_model,
        extra_wells=[((0, inj_cell), +Q), ((0, ext_cell), -Q)],
        group=group, state_label="wells_plus_scenario", canonical_spec=spec,
    )
    converged = scen_built["converged"]
    heads_iii = np.asarray(scen_built["heads"], dtype=float) if scen_built["heads"] is not None else None

    # Finite BEFORE head_delta (recurring NaN class): a NaN head must not reach
    # np.max -> NaN into strict JSON. Emit the diagnostic, then raise cleanly.
    finite_iii = bool(converged and heads_iii is not None and np.all(np.isfinite(heads_iii)))
    head_delta = float(np.max(np.abs(heads_iii - heads_ii))) if finite_iii else None
    diagnostics = _emit_flow_diagnostics(
        converged=converged, heads=heads_iii, botm=scen_spec["botm"],
        gwf=scen_built["gwf"], head_delta=head_delta,
    )
    diag_file = work_dir / "diagnostics.wells_plus_scenario.json"
    diag_file.write_text(json.dumps(diagnostics, indent=2, allow_nan=False, sort_keys=True) + "\n")

    if not converged:
        raise RuntimeError(
            f"build_flow_state(group={group}, state='wells_plus_scenario'): did "
            f"not converge -- see {scen_built['headfile']} listing; diagnostics {diag_file}"
        )
    if not diagnostics["finite_heads"]["passed"]:
        raise RuntimeError(
            f"build_flow_state(group={group}, state='wells_plus_scenario'): "
            f"non-finite head(s); diagnostics {diag_file}"
        )

    metrics = _scenario_response_metrics(
        group, scen_spec, scen_built["modelgrid"], heads_ii, heads_iii,
        wells["gwf"], scen_built["gwf"], scen_spec["botm"],
    )
    # aquifer->river gradient RAW inputs (states ii + iii) for M2a.4's
    # gradient_change obligation. RIV topology is immutable across the
    # scenario, so the ext/nearest-river cells are the same for ii and iii.
    gradient_inputs = _gradient_inputs(
        ext_cell, spec, scen_built["modelgrid"], heads_ii, heads_iii, scen_spec["botm"],
    )

    # Finding 2: the BUILDER self-enforces the FROZEN expectation. The
    # evaluator first checks the flow-config scenario type+params MATCH the
    # frozen table (the expectation is only valid for the exact frozen
    # scenario), then the actual ii->iii response. A build that CONTRADICTS
    # its frozen expectation FAILS -- it must not return successfully.
    expectation = scn.evaluate_scenario_expectation(
        int(group), metrics, config_scenario=scenario,
    )
    if not expectation["consistent"]:
        raise RuntimeError(
            f"build_flow_state(group={group}, state='wells_plus_scenario'): the "
            f"state-iii response CONTRADICTS its FROZEN expectation "
            f"({expectation['assertion_class']}): {expectation['problems']}. "
            "Refusing to return a build that violates the frozen table."
        )

    # Finding 3: grid_hash = the GEOMETRY identity (state-ii grid, still ==
    # the committed golden -- the scenario mutates package VALUES, not the
    # grid). package_hashes MUST reflect the ACTUALLY-assembled state-iii
    # packages: the SCENARIO-mutated arrays (CHD/RIV/RCHA/NPF) AND the COMBINED
    # (background + doublet) canonicalized WEL, not the pre-assemble spec.
    assembled_spec = _spec_with_assembled_wel(scen_spec, scen_built)
    grid_hash, _ = cfc.spec_canonical_hashes(spec)              # geometry == golden
    _, package_hashes = cfc.spec_canonical_hashes(assembled_spec)  # real state-iii packages
    return _rich_result(
        built=scen_built, spec=assembled_spec, riv_info=riv_info, grid_hash=grid_hash,
        package_hashes=package_hashes, diagnostics=diagnostics, diag_file=diag_file,
        work_dir=work_dir, state="wells_plus_scenario", group=group,
        extra={
            "refine_radius": walk["refine_radius"],
            "scenario_type": scenario_type,
            "scenario_params": scenario,
            "resolved_Q": Q,
            "doublet": doublet,
            "state_ii_heads": heads_ii,
            "head_delta_max_m": head_delta,
            "response_metrics": metrics,
            "gradient_inputs": gradient_inputs,
            "expectation": expectation,
        },
    )


# --- M2a.5: transport (FMI) budget-record assertion (Codex #3/#4) -----------
# Budget text emitted per boundary GWF package type. Presence is derived from
# the ENABLED packages that actually contribute in the steady period -- NEVER
# hard-coded -- to avoid both false-fail (requiring a package that isn't built)
# and false-pass (not requiring one that is).
_BOUNDARY_BUDGET_TEXT_BY_TYPE = {
    "wel": "WEL", "riv": "RIV", "chd": "CHD", "rcha": "RCHA",
    "rch": "RCH", "drn": "DRN", "ghb": "GHB", "evt": "EVT", "eva": "EVTA",
}


def _expected_boundary_texts(gwf) -> set:
    """Derive the boundary budget texts the CBC MUST contain from the model's
    ENABLED packages that HAVE data in the steady stress period. A list-based
    package (WEL/RIV/CHD/...) with zero period-0 entries is NOT required; an
    array-based package (e.g. RCHA recharge) always contributes when built."""
    expected = set()
    for pkg in gwf.packagelist:
        text = _BOUNDARY_BUDGET_TEXT_BY_TYPE.get(pkg.package_type.lower())
        if text is None:
            continue
        try:
            spd = pkg.stress_period_data.get_data(0)
            has_data = spd is not None and len(spd) > 0
        except AttributeError:
            # No stress_period_data -> array-based package (RCHA recharge etc.):
            # it always contributes a budget term while enabled.
            has_data = True
        if has_data:
            expected.add(text)
    return expected


def assert_transport_budget_records(
    gwf, budgetfile, *, headfile=None, grid_hash=None, run_start_time=None,
) -> Dict[str, Any]:
    """Assert the flow CBC carries the records the M3 transport (FMI) coupling
    needs, and that it is THIS solved model's OUTPUT (not a stale/foreign file).
    Presence is NECESSARY but not SUFFICIENT (Codex #3/#4):

    1. File/model consistency -- the budget (and, if given, head) FILENAME
       equals ``gwf``'s OC record and resides in ``gwf``'s workspace, so a
       stale CBC from another run/grid can't satisfy the check.
    2. A SINGLE steady time index.
    3. ``FLOW-JA-FACE`` + ``DATA-SPDIS`` present AND non-empty (the specific
       discharge + intercell flows FMI reads).
    4. The boundary budget texts of the ENABLED packages that have data in the
       steady period (derived, never hard-coded), each present AND non-empty.

    FRESHNESS (Codex REWORK #4). The authoritative "written by THIS solve"
    freshness guarantee lives in :func:`_assemble_state_solve` (fresh per-state
    workspace + delete-then-solve + mtime-after-run-start) -- that is the
    sanctioned path every M2a state build takes. THIS function's default
    (``run_start_time=None``) checks IDENTITY only (filename == OC record, file
    in the model workspace): a caller that already holds a run-start timestamp
    (e.g. a future external FMI consumer) MAY pass ``run_start_time`` to also
    assert the CBC/HDS were (re)written after that instant; absent it, freshness
    is the caller's responsibility via the sanctioned build path.

    Returns a provenance report. Raises ``AssertionError`` / ``FileNotFoundError``
    on any failure.
    """
    import flopy  # local import: only needed when a real budget is checked

    budgetfile = Path(budgetfile)
    oc = gwf.get_package("OC")
    if oc is None:
        raise AssertionError("model has no OC package -- no budget output declared")

    # (1) file/model consistency ------------------------------------------------
    oc_budget = str(oc.budget_filerecord.array[0][0])
    if budgetfile.name != oc_budget:
        raise AssertionError(
            f"budget file {budgetfile.name!r} != OC budget record {oc_budget!r} "
            f"-- stale/foreign CBC, not this model's output"
        )
    ws = Path(gwf.simulation.simulation_data.mfpath.get_sim_path()).resolve()
    if budgetfile.resolve().parent != ws:
        raise AssertionError(
            f"budget file {budgetfile} is not in the model workspace {ws} -- stale/foreign"
        )
    if not budgetfile.exists():
        raise FileNotFoundError(f"declared budget file does not exist: {budgetfile}")
    if headfile is not None:
        oc_head = str(oc.head_filerecord.array[0][0])
        if Path(headfile).name != oc_head:
            raise AssertionError(
                f"head file {Path(headfile).name!r} != OC head record {oc_head!r} -- stale/foreign"
            )
        if Path(headfile).resolve().parent != ws:  # Codex REWORK #4
            raise AssertionError(
                f"head file {headfile} is not in the model workspace {ws} -- stale/foreign"
            )

    # (1b) OPTIONAL freshness (Codex REWORK #4): when the caller supplies the
    # solve's start timestamp, assert the CBC/HDS were (re)written after it --
    # a stale file from an earlier solve in the same workspace would be older.
    if run_start_time is not None:
        for kind, path in (("budget", budgetfile), ("head", headfile)):
            if path is None:
                continue
            p = Path(path)
            if p.exists() and p.stat().st_mtime < float(run_start_time) - 2.0:
                raise AssertionError(
                    f"{kind} file {p} is STALE (mtime {p.stat().st_mtime:.3f} < run "
                    f"start {float(run_start_time):.3f}) -- not this run's output"
                )

    # (2) single steady time ----------------------------------------------------
    cbc = flopy.utils.CellBudgetFile(str(budgetfile))
    times = cbc.get_times()
    if len(times) != 1:
        raise AssertionError(f"expected a SINGLE steady time index, got {list(times)}")
    totim = times[-1]
    names = {str(n).strip() for n in cbc.get_unique_record_names(decode=True)}

    def _nonempty(text: str) -> bool:
        data = cbc.get_data(text=text, totim=totim)
        if not data:
            return False
        first = data[0]
        return int(getattr(first, "size", len(first))) > 0

    # (3) FMI-required intercell + specific-discharge records -------------------
    for req in ("FLOW-JA-FACE", "DATA-SPDIS"):
        if req not in names:
            raise AssertionError(f"FMI-required budget record {req!r} MISSING from CBC {sorted(names)}")
        if not _nonempty(req):
            raise AssertionError(f"FMI-required budget record {req!r} is EMPTY at the steady time")

    # (4) enabled-package boundary records --------------------------------------
    expected = _expected_boundary_texts(gwf)
    for text in sorted(expected):
        if text not in names:
            raise AssertionError(
                f"enabled-package budget record {text!r} MISSING from CBC {sorted(names)}"
            )
        if not _nonempty(text):
            raise AssertionError(f"boundary budget record {text!r} is EMPTY at the steady time")

    return {
        "records": sorted(names),
        "steady_time": float(totim),
        "boundary_records": sorted(expected),
        "budgetfile": str(budgetfile),
        "workspace": str(ws),
        "grid_hash": grid_hash,
    }


def state_iii_interface(
    result: Dict[str, Any], *, state_id: str = "wells_plus_scenario", assert_fmi: bool = False
) -> Dict[str, Any]:
    """DECLARE the transport-facing state-(iii) binding interface from a
    ``build_flow_state`` result (asserted at M2a.5). It carries exactly what
    the M3 transport coupling needs to reuse the flow field WITHOUT regridding:
    the grid hash (== the golden manifest's), the stable head/budget FILE
    PATHS, the GWF model name, the (steady) stress-period + units, and
    ``no_regridding=True`` (transport reuses the SAME DISV grid).
    """
    interface = {
        "state_id": state_id,
        "grid_hash": result["grid_hash"],
        "headfile": result["headfile"],
        "budgetfile": result["budgetfile"],
        "gwf_name": result["gwf_name"],
        "stress_period": result["stress_period"],
        "units": result["units"],
        "no_regridding": True,
    }
    missing = [k for k in STATE_III_INTERFACE_KEYS if k not in interface]
    if missing:
        raise AssertionError(f"state_iii_interface missing keys: {missing}")
    if assert_fmi:
        # Presence NECESSARY but not SUFFICIENT: assert the CBC carries the FMI
        # records, is THIS solved model's output, and the interface grid hash
        # matches the built model (Codex #3/#4). Requires a real gwf + budget.
        gwf = result.get("gwf")
        if gwf is None:
            raise AssertionError("assert_fmi=True requires result['gwf'] (a solved GWF model)")
        gh = interface["grid_hash"]
        if not (isinstance(gh, str) and len(gh) == 64):
            raise AssertionError(f"interface grid_hash is not a 64-hex digest: {gh!r}")
        report = assert_transport_budget_records(
            gwf, result["budgetfile"],
            headfile=result.get("headfile"), grid_hash=gh,
        )
        # The CBC/HDS staleness guard (file == OC record, in the model
        # workspace) lives in assert_transport_budget_records; the grid_hash is
        # carried into the report as the transport-facing grid identity.
        interface["fmi_records"] = report
    return interface
