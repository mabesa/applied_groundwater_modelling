#!/usr/bin/env python
"""
================================================================================
 M2a.3 — the 6 SCENARIO-TYPE transforms (state (ii) -> state (iii))
================================================================================

``apply_scenario(spec, scenario_type, params) -> new_spec`` mutates the
state-(ii) refined DISV spec's PACKAGE ARRAYS to produce the state-(iii)
"wells-plus-scenario" spec, for the 9 case-study groups' 6 scenario types
(see DESIGN_DOCS/student_casestudy_M2a_3_plan.md, config
``PROJECT/workspace/template/case_config.yaml``).

Hard rules (Codex-converged, v4):
  * PARAMETER VALIDITY first -- a non-positive conductance/width/
    transmissivity/recharge factor is rejected (never a degenerate model);
    transformed recharge must stay non-negative.
  * IMMUTABLE RIV -- river scenarios mutate the FAITHFUL per-reach RIV
    records' VALUES (stage/rbot/cond) ONLY. The reach->cell assignment, the
    per-record conductance split, and the overbank filtering are FIXED from
    the M2a.0 faithful-RIV build and are NEVER recomputed/re-split/re-filtered.
  * REJECT-NOT-CLAMP -- after a stage change, every RIV reach must satisfy
    ``stage > rbot + clearance``; any inverted reach FAILS loudly (clamping
    would hide invalid forcing nonlinearly).
  * apply_scenario returns a NEW spec; the input spec is never mutated, and
    every array NOT named by the transform is left byte-identical (shared
    reference) so callers/tests can assert "only <field> changed".

The 6 transforms:
  1. chd_head_change (Δm)          : chd_head += Δm on ALL CHD cells (CHD only)
  2. river_conductance (×f)        : riv_cond *= f (value scale of each split)
  3. recharge_scale (×f)           : rch *= f (uniform; area-weighted Σ ×f)
  4. river_stage (Δm)              : riv_stage += Δm; assert stage>rbot+clr
  5. river_width_and_stage (w, s)  : riv_cond *= w AND
                                     riv_stage += s·(stage − rbot)  [depth
                                     fraction, owner-confirmed]; assert stage>rbot+clr
  6. aquifer_transmissivity (×f)   : k *= f (GLOBAL horizontal Kh multiplier;
                                     preserves calibrated heterogeneity;
                                     K33 untouched -- inert at nlay=1)

`uv run` for everything (see CLAUDE.md).
================================================================================
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

_EXPECTATIONS_PATH = Path(__file__).resolve().parent / "casestudy_scenario_expectations.yaml"

# The 6 scenario transform types (== case_config.yaml scenarios.options[*].type).
SCENARIO_TYPES = (
    "chd_head_change",
    "river_conductance",
    "recharge_scale",
    "river_stage",
    "river_width_and_stage",
    "aquifer_transmissivity",
)

# Small positive river-bed clearance (m): after a stage change a reach must
# keep stage > rbot + this (a zero-depth river with positive conductance is
# unphysical). A violation is REJECTED, never clamped.
STAGE_CLEARANCE_M = 1e-3


def _require_positive(name: str, value: float) -> float:
    if not (value > 0):
        raise ValueError(
            f"scenario parameter {name}={value!r} must be > 0 (a non-positive "
            "multiplier is an invalid/degenerate scenario, not silently applied)"
        )
    return value


def _require_param(params: Dict[str, Any], key: str) -> Any:
    if key not in params:
        raise ValueError(f"scenario params missing required key {key!r}: {sorted(params)!r}")
    return params[key]


def _assert_stage_above_rbot(riv_stage, riv_rbot, *, scenario_type: str) -> None:
    """REJECT (raise) if any RIV reach has stage <= rbot + clearance after a
    stage change -- never clamp."""
    stage = np.asarray(riv_stage, dtype=float)
    rbot = np.asarray(riv_rbot, dtype=float)
    bad = np.where(stage <= (rbot + STAGE_CLEARANCE_M))[0]
    if bad.size:
        i = int(bad[0])
        raise ValueError(
            f"scenario {scenario_type!r}: RIV reach {i} inverts after the stage "
            f"change -- stage {stage[i]:.4f} m <= rbot {rbot[i]:.4f} m + "
            f"clearance {STAGE_CLEARANCE_M} m ({int(bad.size)} reach(es) total). "
            "REJECTING (an invalid river forcing is never clamped)."
        )


def apply_scenario(spec: Dict[str, Any], scenario_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a NEW spec = *spec* with ONLY the scenario's package array(s)
    mutated (state (ii) -> state (iii)). The input *spec* is not modified; any
    array the transform does not touch is left byte-identical (shared ref).

    Raises ``ValueError`` on an unknown type, a missing/invalid parameter, or
    a package-validity violation (e.g. an inverted RIV reach).
    """
    if scenario_type not in SCENARIO_TYPES:
        raise ValueError(
            f"unknown scenario_type {scenario_type!r}; expected one of {SCENARIO_TYPES}"
        )

    new: Dict[str, Any] = dict(spec)  # shallow copy; replace only mutated fields

    if scenario_type == "chd_head_change":
        dm = float(_require_param(params, "chd_head_change_m"))
        # CHD package ONLY: uniform head change on every CHD cell (single
        # regional boundary -- all-CHD scope is intentional).
        new["chd_head"] = [float(h) + dm for h in spec["chd_head"]]

    elif scenario_type == "river_conductance":
        f = _require_positive("conductance_factor", float(_require_param(params, "conductance_factor")))
        # value scale of the already-split faithful per-reach conductances
        # (preserves each record's share + the total scaling; no re-split).
        new["riv_cond"] = [float(c) * f for c in spec["riv_cond"]]

    elif scenario_type == "recharge_scale":
        f = _require_positive("recharge_factor", float(_require_param(params, "recharge_factor")))
        rch = np.asarray(spec["rch"], dtype=float) * f
        if np.any(rch < 0):
            raise ValueError("scenario recharge_scale produced negative recharge (invalid)")
        new["rch"] = rch

    elif scenario_type == "river_stage":
        dm = float(_require_param(params, "stage_change_m"))
        riv_stage = [float(s) + dm for s in spec["riv_stage"]]
        _assert_stage_above_rbot(riv_stage, spec["riv_rbot"], scenario_type=scenario_type)
        new["riv_stage"] = riv_stage

    elif scenario_type == "river_width_and_stage":
        w = _require_positive("width_factor", float(_require_param(params, "width_factor")))
        s = float(_require_param(params, "stage_change_factor"))
        # width feeds conductance linearly (C = K·L·W/M) -> value scale, no re-split.
        new["riv_cond"] = [float(c) * w for c in spec["riv_cond"]]
        # stage change = fraction s of the LOCAL river depth (stage - rbot)
        # (owner-confirmed 2026-07-20: a wider channel is shallower).
        riv_stage = [
            float(st) + s * (float(st) - float(rb))
            for st, rb in zip(spec["riv_stage"], spec["riv_rbot"])
        ]
        _assert_stage_above_rbot(riv_stage, spec["riv_rbot"], scenario_type=scenario_type)
        new["riv_stage"] = riv_stage

    elif scenario_type == "aquifer_transmissivity":
        f = _require_positive("transmissivity_factor", float(_require_param(params, "transmissivity_factor")))
        # GLOBAL horizontal Kh multiplier (preserves relative heterogeneity;
        # NOT a zonal change). K33 is inert at nlay=1 and is NOT in the spec,
        # so nothing else is touched (assert positive-K preserved).
        k = np.asarray(spec["k"], dtype=float) * f
        if np.any(k <= 0):
            raise ValueError("scenario aquifer_transmissivity produced non-positive K (invalid)")
        new["k"] = k

    return new


# =============================================================================
# FROZEN expectation table (READ-ONLY) + the ii->iii consistency evaluator.
# =============================================================================
def load_expectations(path: Optional[Any] = None) -> Dict[str, Any]:
    """Load the frozen ``casestudy_scenario_expectations.yaml`` (authored from
    hydro reasoning BEFORE any solver run -- treated READ-ONLY)."""
    import yaml

    p = Path(path) if path is not None else _EXPECTATIONS_PATH
    with open(p, "r", encoding="utf-8") as fh:
        exp = yaml.safe_load(fh)
    if not exp.get("frozen_before_run"):
        raise ValueError(
            f"expectation table {p} must carry frozen_before_run: true "
            "(a hand-authored expectation is only falsifiable if frozen first)"
        )
    return exp


def assert_config_matches_frozen(group: int, config_scenario: Dict[str, Any],
                                 entry: Dict[str, Any]) -> None:
    """Finding 4: the frozen expectation is ONLY valid for the EXACT scenario
    it was authored against. Assert the live flow-config scenario's TYPE and
    every frozen PARAM value match the frozen table entry, or FAIL loudly (a
    changed ``conductance_factor`` / ``stage_change_m`` etc. must NOT be judged
    against a stale expectation).
    """
    if config_scenario.get("type") != entry["scenario_type"]:
        raise ValueError(
            f"group {group}: flow-config scenario type "
            f"{config_scenario.get('type')!r} != frozen expectation "
            f"{entry['scenario_type']!r}; the frozen table is stale for this config"
        )
    for key, frozen_val in (entry.get("params") or {}).items():
        cfg_val = config_scenario.get(key)
        if cfg_val is None or float(cfg_val) != float(frozen_val):
            raise ValueError(
                f"group {group}: flow-config param {key}={cfg_val!r} != frozen "
                f"expectation {key}={frozen_val!r}; the frozen expectation is only "
                "valid for the exact frozen scenario (re-author the table if the "
                "config scenario genuinely changed)"
            )


def evaluate_scenario_expectation(
    group: int, metrics: Dict[str, Any], expectations: Optional[Dict[str, Any]] = None,
    *, config_scenario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assert the ACTUAL state-ii->iii response *metrics* are CONSISTENT with
    the FROZEN expectation for *group*'s assertion class. Returns a report dict
    (``consistent`` bool + the observed values + the class); NEVER edits the
    frozen table. A ``consistent=False`` is a FINDING for the caller to surface.

    If *config_scenario* (the live flow-config scenario dict) is given, its
    type + frozen params are asserted to MATCH the frozen table FIRST (Finding
    4) -- a stale expectation for a changed config fails loudly.

    *metrics* (computed by the builder from the same-grid ii/iii solves):
      ``max_abs_head_change`` (m), ``mean_head_change`` (m),
      ``abs_river_exchange`` = {ii, iii}, ``river_to_aquifer_flux`` = {ii, iii},
      ``argmax_dist_to_chd_m`` / ``argmax_dist_to_riv_m`` (m),
      ``n_active``, ``n_responding`` (|Δh| > ampl_frac*max), ``n_dry_iii``,
      ``finite_iii`` (bool).
    """
    exp = expectations if expectations is not None else load_expectations()
    cfg = exp["config"]
    entry = exp["groups"][group]
    cls = entry["assertion_class"]

    if config_scenario is not None:
        assert_config_matches_frozen(group, config_scenario, entry)

    presence = float(cfg["presence_tol_m"])
    bound = float(cfg["bound_m"])
    mx = float(metrics["max_abs_head_change"])

    problems = []
    observed = {"max_abs_head_change": mx, "class": cls, "metric": entry.get("metric")}

    # PRESENT + BOUNDED (all classes)
    if not (mx > presence):
        problems.append(f"no response: max|Δh|={mx:.5f} m <= presence_tol {presence} m")
    if not (mx < bound):
        problems.append(f"unbounded response: max|Δh|={mx:.3f} m >= bound {bound} m")

    if cls == "clear_sign":
        direction = entry["direction"]
        metric = entry["metric"]
        min_rel = float(cfg["clear_sign_min_rel"])
        if metric == "mean_head_change":
            val = float(metrics["mean_head_change"])
            observed["mean_head_change"] = val
            rel = abs(val)  # absolute m; use presence-scaled deadband
            ok_dir = (val > presence) if direction == "increase" else (val < -presence)
            if not ok_dir:
                problems.append(f"mean_head_change {val:+.5f} m not {direction} (deadband {presence} m)")
        else:  # abs_river_exchange or river_to_aquifer_flux (ii vs iii)
            pair = metrics[metric]
            ii, iii = float(pair["ii"]), float(pair["iii"])
            observed[metric] = {"ii": ii, "iii": iii, "delta": iii - ii}
            base = max(abs(ii), 1e-9)
            rel = (iii - ii) / base
            ok_dir = (rel > min_rel) if direction == "increase" else (rel < -min_rel)
            if not ok_dir:
                problems.append(
                    f"{metric} {ii:.3f}->{iii:.3f} (rel {rel:+.4%}) not {direction} "
                    f"(deadband {min_rel:.1e})"
                )

    elif cls == "feature_local":
        feature = entry["feature"]  # "chd" or "riv"
        d = float(metrics[f"argmax_dist_to_{feature}_m"])
        loc = float(cfg["locality_dist_m"])
        observed["argmax_dist_to_feature_m"] = d
        observed["feature"] = feature
        if not (d <= loc):
            problems.append(
                f"response NOT localized near '{entry['feature']}': argmax |Δh| is "
                f"{d:.1f} m from the nearest feature cell (> locality_dist {loc} m)"
            )

    elif cls == "global":
        if not metrics.get("finite_iii", True):
            problems.append("state iii has non-finite heads")
        if int(metrics.get("n_dry_iii", 0)) != 0:
            problems.append(f"state iii has {metrics['n_dry_iii']} dry cell(s)")
        n_active = int(metrics["n_active"])
        n_resp = int(metrics["n_responding"])
        frac = n_resp / max(n_active, 1)
        observed["responding_fraction"] = frac
        if not (frac >= float(cfg["global_spread_min_frac"])):
            problems.append(
                f"response NOT spread (localized): only {frac:.1%} of active cells "
                f"respond at > {cfg['global_spread_ampl_frac']:.0%} of max "
                f"(need >= {cfg['global_spread_min_frac']:.0%})"
            )
    else:
        problems.append(f"unknown assertion_class {cls!r}")

    return {
        "group": group,
        "assertion_class": cls,
        "scenario_type": entry["scenario_type"],
        "consistent": len(problems) == 0,
        "problems": problems,
        "observed": observed,
        "expectation": entry.get("expectation", ""),
    }
