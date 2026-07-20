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

Scope (M2a.1): state (i) baseline ONLY. States (ii)/(iii), the doublet,
scenarios, groups 1-8 are M2a.2/M2a.3; the neutral factory's ``extra_wells``
seam is where M2a.2 adds the doublet.

`uv run` for everything (see CLAUDE.md).
================================================================================
"""
from __future__ import annotations

import json
import sys
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

Group = Any

# The only state this milestone builds (M2a.1). States (ii)/(iii) are M2a.2/3.
SUPPORTED_STATES = ("baseline",)

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
    *, converged: bool, heads, botm, gwf,
) -> Dict[str, Dict[str, Any]]:
    """Compute the M1.4 ``{id: entry}`` flow-diagnostics surface for a solved
    baseline state. ``flow_head_delta`` is NULL for baseline (the baseline IS
    the reference states (ii)/(iii) compare against -- NOT a faked zero
    self-reference).
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
        # NULL for baseline: no reference state (nullable diagnostic passes).
        "flow_head_delta": cd.evaluate("flow_head_delta", None),
    }


def build_flow_state(
    group: Group, state: str = "baseline", *, work_dir,
) -> Dict[str, Any]:
    """Build + solve the corridor-refined steady baseline flow state for
    *group* and return the rich metadata dict (see :data:`BUILD_RESULT_KEYS`).

    Parameters
    ----------
    group : int
        Student group id (0-8). M2a.1 exercises group 0.
    state : str
        Only ``"baseline"`` is supported in M2a.1 (states (ii)/(iii) are
        M2a.2/3); any other value raises ``NotImplementedError``.
    work_dir : str or Path
        Directory for the assembled MF6 files + the ``diagnostics.<state>.json``.

    Returns
    -------
    dict
        ``{gwf, heads, spec, diagnostics, workspace, sim, gwf_name, headfile,
        budgetfile, grid_hash, stress_period, units, package_hashes}`` (all
        keys asserted present), plus ``state``/``group``/``riv_info``/
        ``diagnostics_file`` extras.

    Raises
    ------
    NotImplementedError
        For any *state* other than ``"baseline"``.
    RuntimeError
        If the flow model fails to converge (after writing the diagnostics
        surface recording ``flow_convergence`` False).
    """
    if state not in SUPPORTED_STATES:
        raise NotImplementedError(
            f"build_flow_state: state {state!r} is not supported in M2a.1 "
            f"(supported: {SUPPORTED_STATES}); states (ii)/(iii) are M2a.2/M2a.3"
        )

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load 05f + GIS; build the shared baseline spec (faithful RIV).
    mother = mio.ensure_flow_model()
    _sim, cgwf = cfc.load_coarse_model(mother)
    coarse_heads = cgwf.output.head().get_data().flatten()
    boundary_gdf, river_gdf = cfc.load_gis(mother)
    refine_points = cfc.group_refine_points(group)
    spec, riv_info = cfc.build_baseline_spec(
        cgwf, boundary_gdf, river_gdf, refine_points, coarse_heads,
    )

    # 2. Assemble + solve via the NEUTRAL flow-package factory (baseline =
    #    background wells only; no doublet, no extra_wells). raise_on_failure
    #    False so we can EMIT the diagnostics surface on a bad solve before
    #    raising (the generator uses the default raise_on_failure=True).
    sim_name = f"group{group}_{state}"
    built = cfc.assemble_flow_state(
        spec, workspace=work_dir, sim_name=sim_name, raise_on_failure=False,
    )
    heads = built["heads"]
    converged = built["converged"]

    # 3. Emit the M1.4 diagnostics surface -> diagnostics.<state>.json
    #    (CONTENT is the unchanged {id: entry} dict; STATE is in the filename).
    diagnostics = _emit_flow_diagnostics(
        converged=converged, heads=heads, botm=spec["botm"], gwf=built["gwf"],
    )
    diag_file = work_dir / f"diagnostics.{state}.json"
    diag_file.write_text(json.dumps(diagnostics, indent=2, allow_nan=False, sort_keys=True) + "\n")

    if not converged:
        raise RuntimeError(
            f"build_flow_state(group={group}, state={state!r}): flow model did "
            f"not converge -- see {built['headfile']} listing; diagnostics "
            f"written to {diag_file}"
        )
    # NaN-fragility gate (Finding 4): a converged run with any non-finite head
    # must NOT proceed (the dry-cell count / downstream metadata would be
    # silently wrong). finite_heads emits value=False -> raise-severity; abort.
    if not diagnostics["finite_heads"]["passed"]:
        raise RuntimeError(
            f"build_flow_state(group={group}, state={state!r}): solved heads "
            f"contain non-finite (NaN/Inf) value(s) -- refusing to build a "
            f"baseline on a broken head field; diagnostics written to {diag_file}"
        )

    # 4. Rich metadata dict (path/metadata M3 + state-(iii) bind to).
    grid_hash, package_hashes = cfc.spec_canonical_hashes(spec)
    result: Dict[str, Any] = {
        "gwf": built["gwf"],
        "heads": heads,
        "spec": spec,
        "diagnostics": diagnostics,
        "workspace": str(work_dir.resolve()),
        "sim": built["sim"],
        "gwf_name": built["model_name"],
        "headfile": built["headfile"],
        "budgetfile": built["budgetfile"],
        "grid_hash": grid_hash,
        "stress_period": dict(STRESS_PERIOD),
        "units": dict(UNITS),
        "package_hashes": package_hashes,
        # extras (not part of the asserted contract but useful downstream)
        "state": state,
        "group": int(group),
        "riv_info": riv_info,
        "diagnostics_file": str(diag_file.resolve()),
    }
    missing = [k for k in BUILD_RESULT_KEYS if k not in result]
    if missing:
        raise AssertionError(f"build_flow_state result missing required keys: {missing}")
    return result


def state_iii_interface(result: Dict[str, Any], *, state_id: str = "wells_plus_scenario") -> Dict[str, Any]:
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
    return interface
