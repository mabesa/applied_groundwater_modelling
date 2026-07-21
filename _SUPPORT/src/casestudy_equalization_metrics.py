#!/usr/bin/env python
"""
================================================================================
 M2a.4 — close the M1.5 equalization emit-obligations
================================================================================

``emit_equalization_metrics(group, state_metrics) -> dict`` computes the three
emit-obligations M2a owes the M1.5 equalization contract
(``casestudy_equalization_dimensions.yaml`` /
``casestudy_m1_specs.emit_obligations()``) from the ALREADY-built flow states
(no new model physics), and ``write_equalization_metrics`` writes the per-group
metrics surface ``equalization_metrics.<group>.json`` that M3c/M5 consume.

The three obligations (LIVE set = ``emit_obligations()['M2a'] U ['M2a+M3a']``):
  * river_leakage_change = ``river_to_aquifer_flux[iii] - river_to_aquifer_flux[ii]``
    (m3/d, SIGNED river->aquifer-positive; from M2a.3 response_metrics -- NEVER
    ``abs_river_exchange``, whose magnitude delta would silently invert meaning).
    Secondary FIELD ``pct_of_state_ii`` = 100*change/|flux_ii| only when
    |flux_ii| exceeds a near-zero floor (else null).
  * gradient_change (receptor = RIVER) = ``grad_iii - grad_ii`` (dimensionless),
    ``grad = (head_ext - head_nearest_river) / dist`` near the doublet; positive
    grad = aquifer higher than river (aquifer->river discharge gradient).
    CENSORED (value null + reason) on no RIV cell / zero distance / inactive or
    dry ext-or-river cell.
  * runtime = the flow build+solve wall-clock (s) -- a METRIC on the return
    ONLY, NEVER a golden/hashed/frozen path.

ANTI-DRIFT: every obligation's ``unit`` / ``aggregation`` /
``baseline_convention`` / ``producer`` is copied from the LIVE dimensions doc
(so it tracks the contract), and ``emit_equalization_metrics`` asserts the
emitted ID set EQUALS the live M2a obligation set (no missing, no extras).

`uv run` for everything (see CLAUDE.md).
================================================================================
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Optional

# state_pair for the ii->iii obligations (baseline_convention "wells-only vs
# wells-plus-scenario"); runtime is not_applicable (state_pair null).
STATE_PAIR = ["wells_only", "wells_plus_scenario"]

# |flux_ii| below this (m3/d) makes the % secondary field meaningless -> null.
NEAR_ZERO_FLUX_M3D = 1e-6


def _load_dims(dims_doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if dims_doc is not None:
        return dims_doc
    import casestudy_m1_specs as m1

    return m1.load_equalization_dimensions()


def _live_m2a_obligations(dims_doc: Dict[str, Any]) -> set:
    """The LIVE obligation IDs M2a owes = ``emit_obligations()['M2a'] U
    ['M2a+M3a']`` (river_leakage_change, gradient_change, runtime)."""
    import casestudy_m1_specs as m1

    eo = m1.emit_obligations(dims_doc)
    return set(eo["M2a"]) | set(eo["M2a+M3a"])


def _contract_fields(dims_doc: Dict[str, Any], obligation_id: str) -> Dict[str, Any]:
    """The M1.5 contract fields for *obligation_id* copied from the LIVE
    dimensions doc (so the emitted metadata cannot drift from the contract)."""
    for d in dims_doc["dimensions"]:
        if d["id"] == obligation_id:
            return {
                "unit": d["unit"],
                "aggregation": d["aggregation"],
                "baseline_convention": d["baseline_convention"],
                "producer": d["producer"],
            }
    raise KeyError(f"obligation {obligation_id!r} not found in the dimensions doc")


def _finite(x) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


# --- the three obligation computers -----------------------------------------
def _river_leakage_change(state_metrics: Dict[str, Any], dims_doc) -> Dict[str, Any]:
    entry = {
        **_contract_fields(dims_doc, "river_leakage_change"),
        "state_pair": list(STATE_PAIR),
        "provenance_input_ids": ["river_to_aquifer_flux"],
    }
    rm = (state_metrics or {}).get("response_metrics") or {}
    flux = rm.get("river_to_aquifer_flux")
    # SIGNED river->aquifer flux ONLY (never abs_river_exchange).
    if not flux or not _finite(flux.get("ii")) or not _finite(flux.get("iii")):
        entry["value"] = None
        entry["censored_reason"] = "no signed river-to-aquifer flux for states ii/iii"
        return entry
    ii, iii = float(flux["ii"]), float(flux["iii"])
    change = iii - ii
    entry["value"] = change
    # SECONDARY field (not a second obligation), null under a near-zero flux_ii.
    entry["pct_of_state_ii"] = (100.0 * change / abs(ii)) if abs(ii) > NEAR_ZERO_FLUX_M3D else None
    return entry


def _gradient_change(state_metrics: Dict[str, Any], dims_doc) -> Dict[str, Any]:
    entry = {
        **_contract_fields(dims_doc, "gradient_change"),
        "state_pair": list(STATE_PAIR),
        "provenance_input_ids": ["gradient_inputs"],
        "receptor_type": "river",
    }
    gi = (state_metrics or {}).get("gradient_inputs")

    def censor(reason):
        entry["value"] = None
        entry["censored_reason"] = reason
        return entry

    if not gi:
        return censor("no gradient inputs (no state-iii build recorded)")
    if gi.get("riv_cell") is None:
        return censor("no ACTIVE RIV cell in the domain (no aquifer->river receptor)")
    dist = gi.get("dist_m")
    if not _finite(dist) or float(dist) == 0.0:
        return censor(f"zero/invalid extraction-to-river distance ({dist!r})")
    if (gi.get("ext_active") is False) or (gi.get("riv_active") is False):
        return censor("inactive extraction or river cell")
    if any(bool(gi.get(k)) for k in ("ext_dry_ii", "ext_dry_iii", "riv_dry_ii", "riv_dry_iii")):
        return censor("dry extraction or river cell in state ii or iii")
    for k in ("head_ext_ii", "head_ext_iii", "head_riv_ii", "head_riv_iii"):
        if not _finite(gi.get(k)):
            return censor(f"non-finite {k}")

    dist = float(dist)
    grad_ii = (float(gi["head_ext_ii"]) - float(gi["head_riv_ii"])) / dist
    grad_iii = (float(gi["head_ext_iii"]) - float(gi["head_riv_iii"])) / dist
    entry["value"] = grad_iii - grad_ii
    entry["grad_ii"] = grad_ii
    entry["grad_iii"] = grad_iii
    entry["dist_m"] = dist
    return entry


def _runtime(state_metrics: Dict[str, Any], dims_doc) -> Dict[str, Any]:
    entry = {
        **_contract_fields(dims_doc, "runtime"),
        "state_pair": None,  # baseline_convention not_applicable
        "provenance_input_ids": ["runtime_s"],
    }
    rt = (state_metrics or {}).get("runtime_s")
    if not _finite(rt) or float(rt) <= 0:
        entry["value"] = None
        entry["censored_reason"] = "no positive flow build+solve runtime recorded"
        return entry
    entry["value"] = float(rt)
    return entry


def emit_equalization_metrics(
    group: int, state_metrics: Dict[str, Any], *, dims_doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Compute the 3 M2a emit-obligations for *group* from *state_metrics* (a
    ``build_flow_state('wells_plus_scenario')`` result -- carrying
    ``response_metrics``, ``gradient_inputs``, ``runtime_s``). Returns a dict
    keyed by obligation ID; each entry carries the LIVE M1.5 contract fields +
    ``value|null`` (+ ``censored_reason`` when null) + provenance.

    Asserts the emitted ID set EQUALS the live M2a obligation set (no missing,
    no extras) -- the anti-drift guarantee.
    """
    doc = _load_dims(dims_doc)
    out = {
        "river_leakage_change": _river_leakage_change(state_metrics, doc),
        "gradient_change": _gradient_change(state_metrics, doc),
        "runtime": _runtime(state_metrics, doc),
    }
    live = _live_m2a_obligations(doc)
    emitted = set(out)
    if emitted != live:
        raise ValueError(
            f"emitted equalization-metric IDs {sorted(emitted)} != live M2a "
            f"emit-obligations {sorted(live)} (missing "
            f"{sorted(live - emitted)}, extras {sorted(emitted - live)})"
        )
    return out


def write_equalization_metrics(group: int, metrics: Dict[str, Any], out_dir) -> Path:
    """Write the per-group metrics surface ``equalization_metrics.<group>.json``
    (strict JSON, ``allow_nan=False`` -- runtime/values are finite or explicit
    null). Returns the path. This surface is NOT a golden/hashed artifact."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"equalization_metrics.{int(group)}.json"
    p.write_text(json.dumps(metrics, indent=2, allow_nan=False, sort_keys=True) + "\n")
    return p
