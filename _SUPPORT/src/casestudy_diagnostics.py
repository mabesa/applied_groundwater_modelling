"""
casestudy_diagnostics -- M1.4: loader + linter + evaluator for the per-run
MODEL diagnostics contract.

SPEC-ONLY (no model run). This module does NOT compute the diagnostics (that is
M2a/M3a/M3b); it (1) loads + LINTS ``casestudy_diagnostic_schema.yaml``, (2)
exposes the parsed schema, and (3) defines the ``diagnostics.json`` emission
contract + an ``evaluate(id, value)`` helper so every builder emits the same
shape and computes ``triggered_severity``/``passed`` identically from the schema
bands.

Layering: this is the per-run MODEL-diagnostics layer. It is DISTINCT from
``diagnostics.py`` (environment/import/smoke checks). The human catalog is
``casestudy_diagnostic_spec.md``.

``diagnostics.json`` per-run entry shape (one per diagnostic id):
    { "<id>": {
        "value": <num|bool|null>,   # null only for a `nullable` diagnostic that did not run
        "aggregation": <str>,
        "unit": <str>,
        "warn_threshold": <num|null>,
        "raise_threshold": <num|null>,   # the EFFECTIVE band (scaled for relative diagnostics)
        "reference": <num|null>,         # run-time reference used for a relative raise band
        "triggered_severity": "pass"|"warn"|"raise",
        "passed": <bool>          # == (triggered_severity != "raise")
    } }

Boolean diagnostics (``finite`` / ``eq ==True`` checks) are evaluated
boolean-aware BEFORE any float coercion: ``True -> pass``, ``False -> raise``
(so a ``finite=False`` broken-solve flag can never silently pass). A diagnostic
with ``raise_threshold_relative`` (raise band = a fraction of a run-time
reference, e.g. peak concentration) REQUIRES a positive ``reference`` -- calling
``evaluate`` without one is an error, never a silent fallback to the raw
fraction.

Author: Applied Groundwater Modelling Course (transport track, M1.4).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# ---------------------------------------------------------------------------
# paths + enums
# ---------------------------------------------------------------------------
_MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA_PATH = _MODULE_DIR / "casestudy_diagnostic_schema.yaml"

AGGREGATIONS = frozenset({"max", "p95", "cumulative", "per_step", "scalar"})
COMPARATORS = frozenset({"le", "ge", "eq", "in", "finite"})
SEVERITIES = frozenset({"raise", "warn"})
OWNERS = frozenset({"M2a", "M3a", "M3b"})
ENFORCED = frozenset({"now", "M3c", "M4", "M5", "M8"})
OUTPUT_TYPES = frozenset({"bool", "int", "float"})

# structural comparators carry no numeric bands (the comparator IS the gate)
_STRUCTURAL = frozenset({"finite", "in"})

_REQUIRED_FIELDS = (
    "id", "metric", "input_artifact", "aggregation", "comparator",
    "warn_threshold", "raise_threshold", "numeric_tol", "abs_tol",
    "severity", "owner", "enforced", "output",
)
_REQUIRED_ARTIFACT = ("file", "field", "shape", "unit")
_REQUIRED_OUTPUT = ("path", "json_key", "type", "nullable")

# emission-contract keys (diagnostics.json per-entry)
JSON_ENTRY_KEYS = (
    "value", "aggregation", "unit", "warn_threshold", "raise_threshold",
    "reference", "triggered_severity", "passed",
)
TRIGGERED_SEVERITIES = ("pass", "warn", "raise")


class SchemaError(ValueError):
    """Raised when the diagnostic schema fails linting."""


# ---------------------------------------------------------------------------
# load + lint
# ---------------------------------------------------------------------------
def load_schema(path: Optional[Path] = None, *, lint: bool = True) -> Dict[str, Any]:
    """Load (and by default LINT) the diagnostic schema YAML. Returns the parsed
    mapping ``{"schema_version", "reporting_surface", "diagnostics": [...]}``."""
    path = Path(path or DEFAULT_SCHEMA_PATH)
    with open(path, "r") as fh:
        schema = yaml.safe_load(fh)
    if lint:
        lint_schema(schema)
    return schema


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_num_or_null(v: Any) -> bool:
    return v is None or _is_num(v)


def lint_schema(schema: Dict[str, Any]) -> None:
    """Validate the schema against the M1.4 contract; raise ``SchemaError`` on
    the first violation (missing field, bad enum, duplicate id, malformed
    warn/raise band)."""
    if not isinstance(schema, dict):
        raise SchemaError("schema must be a mapping.")
    diags = schema.get("diagnostics")
    if not isinstance(diags, list) or not diags:
        raise SchemaError("schema.diagnostics must be a non-empty list.")

    seen_ids: set = set()
    for i, entry in enumerate(diags):
        if not isinstance(entry, dict):
            raise SchemaError(f"diagnostics[{i}] must be a mapping.")
        did = entry.get("id")
        where = f"diagnostic {did!r}" if did else f"diagnostics[{i}]"

        # required fields present
        for f in _REQUIRED_FIELDS:
            if f not in entry:
                raise SchemaError(f"{where}: missing required field {f!r}.")
        if not isinstance(did, str) or not did:
            raise SchemaError(f"{where}: 'id' must be a non-empty string.")
        if did in seen_ids:
            raise SchemaError(f"duplicate diagnostic id {did!r}.")
        seen_ids.add(did)

        # justification is required (the header declares it) + must be a non-empty string.
        if not isinstance(entry.get("justification"), str) or not entry["justification"].strip():
            raise SchemaError(f"{where}: 'justification' must be a non-empty string.")
        if not isinstance(entry.get("metric"), str) or not entry["metric"].strip():
            raise SchemaError(f"{where}: 'metric' must be a non-empty string.")

        # nested required blocks + sub-field VALUE types (not just presence)
        art = entry["input_artifact"]
        if not isinstance(art, dict) or any(k not in art for k in _REQUIRED_ARTIFACT):
            raise SchemaError(f"{where}: input_artifact must have {list(_REQUIRED_ARTIFACT)}.")
        for k in _REQUIRED_ARTIFACT:
            if not isinstance(art[k], str) or not art[k].strip():
                raise SchemaError(f"{where}: input_artifact.{k} must be a non-empty string.")
        out = entry["output"]
        if not isinstance(out, dict) or any(k not in out for k in _REQUIRED_OUTPUT):
            raise SchemaError(f"{where}: output must have {list(_REQUIRED_OUTPUT)}.")
        if not isinstance(out["path"], str) or not out["path"].strip():
            raise SchemaError(f"{where}: output.path must be a non-empty string.")
        if not isinstance(out["json_key"], str) or not out["json_key"].strip():
            raise SchemaError(f"{where}: output.json_key must be a non-empty string.")

        # enums
        if entry["aggregation"] not in AGGREGATIONS:
            raise SchemaError(f"{where}: aggregation {entry['aggregation']!r} not in {sorted(AGGREGATIONS)}.")
        comparator = entry["comparator"]
        if comparator not in COMPARATORS:
            raise SchemaError(f"{where}: comparator {comparator!r} not in {sorted(COMPARATORS)}.")
        severity = entry["severity"]
        if severity not in SEVERITIES:
            raise SchemaError(f"{where}: severity {severity!r} not in {sorted(SEVERITIES)}.")
        if entry["owner"] not in OWNERS:
            raise SchemaError(f"{where}: owner {entry['owner']!r} not in {sorted(OWNERS)}.")
        if entry["enforced"] not in ENFORCED:
            raise SchemaError(f"{where}: enforced {entry['enforced']!r} not in {sorted(ENFORCED)}.")
        if out["type"] not in OUTPUT_TYPES:
            raise SchemaError(f"{where}: output.type {out['type']!r} not in {sorted(OUTPUT_TYPES)}.")
        if not isinstance(out["nullable"], bool):
            raise SchemaError(f"{where}: output.nullable must be a bool.")

        # emission consistency: json_key == id (so evaluate/emit line up)
        if out["json_key"] != did:
            raise SchemaError(f"{where}: output.json_key {out['json_key']!r} must equal id {did!r}.")

        # tolerances
        if not _is_num(entry["numeric_tol"]) or entry["numeric_tol"] < 0:
            raise SchemaError(f"{where}: numeric_tol must be a non-negative number.")
        if not _is_num_or_null(entry["abs_tol"]):
            raise SchemaError(f"{where}: abs_tol must be a number or null.")
        warn_t, raise_t = entry["warn_threshold"], entry["raise_threshold"]
        if not _is_num_or_null(warn_t) or not _is_num_or_null(raise_t):
            raise SchemaError(f"{where}: warn_threshold/raise_threshold must be number or null.")

        _lint_bands(where, comparator, severity, warn_t, raise_t)

        # finite <-> bool-output consistency: a `finite` diagnostic emits an
        # all-finite FLAG handled by the boolean path, so its output.type must
        # be bool (a float 'value' for a finite check would be mis-evaluated).
        if comparator == "finite" and out["type"] != "bool":
            raise SchemaError(
                f"{where}: comparator 'finite' requires output.type 'bool' (got {out['type']!r}).")

        # relative raise band: raise_threshold_relative must be a bool; when
        # True it may only sit on a multi-band numeric le/ge severity-raise
        # check, and the metric must document the run-time reference (peak).
        rtr = entry.get("raise_threshold_relative")
        if rtr is not None:
            if not isinstance(rtr, bool):
                raise SchemaError(f"{where}: raise_threshold_relative must be a bool.")
            if rtr:
                if comparator not in ("le", "ge") or severity != "raise":
                    raise SchemaError(
                        f"{where}: raise_threshold_relative=true requires a le/ge severity-raise check.")
                if not (_is_num(warn_t) and _is_num(raise_t)):
                    raise SchemaError(
                        f"{where}: raise_threshold_relative=true requires a numeric multi-band "
                        "(both warn_threshold and raise_threshold set).")
                doc = (entry["metric"] + " " + entry["justification"]).lower()
                if "peak" not in doc and "reference" not in doc:
                    raise SchemaError(
                        f"{where}: raise_threshold_relative=true must document its run-time "
                        "reference (mention 'peak' or 'reference' in metric/justification).")


def _lint_bands(where: str, comparator: str, severity: str,
                warn_t: Any, raise_t: Any) -> None:
    """Band well-formedness: multi-band has both thresholds ordered; a
    single-severity check has the matching threshold; structural comparators
    carry no numeric bands."""
    if comparator in _STRUCTURAL:
        if warn_t is not None or raise_t is not None:
            raise SchemaError(f"{where}: comparator {comparator!r} is structural -- thresholds must be null.")
        if severity != "raise":
            raise SchemaError(f"{where}: structural comparator {comparator!r} must be severity 'raise'.")
        return

    if comparator == "eq":
        if raise_t is None:
            raise SchemaError(f"{where}: comparator 'eq' needs a raise_threshold (the target value).")
        if warn_t is not None:
            raise SchemaError(f"{where}: comparator 'eq' must not set a warn_threshold.")
        return

    # comparator in {le, ge}
    if severity == "warn":
        # single warn band: warn_threshold present; raise band absent.
        if warn_t is None:
            raise SchemaError(f"{where}: severity 'warn' requires a warn_threshold.")
        if raise_t is not None:
            raise SchemaError(f"{where}: severity 'warn' must not set a raise_threshold (no hard band).")
        return

    # severity == "raise": the raise band must exist.
    if raise_t is None:
        raise SchemaError(f"{where}: severity 'raise' with comparator {comparator!r} requires a raise_threshold.")
    if warn_t is not None:
        # multi-band: ordering must be sane for the direction.
        if comparator == "le" and not (warn_t <= raise_t):
            raise SchemaError(f"{where}: le multi-band requires warn_threshold <= raise_threshold.")
        if comparator == "ge" and not (warn_t >= raise_t):
            raise SchemaError(f"{where}: ge multi-band requires warn_threshold >= raise_threshold.")


# ---------------------------------------------------------------------------
# parsed-schema accessors
# ---------------------------------------------------------------------------
def diagnostics_by_id(schema: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    schema = schema or load_schema()
    return {d["id"]: d for d in schema["diagnostics"]}


def diagnostic_ids(schema: Optional[Dict[str, Any]] = None) -> List[str]:
    schema = schema or load_schema()
    return [d["id"] for d in schema["diagnostics"]]


# module-level convenience (linted on import)
DIAGNOSTICS: Dict[str, Dict[str, Any]] = diagnostics_by_id(load_schema())


# ---------------------------------------------------------------------------
# evaluator / emission contract
# ---------------------------------------------------------------------------
def _tol(entry: Dict[str, Any]) -> float:
    at = entry.get("abs_tol")
    return float(at) if at is not None else float(entry.get("numeric_tol", 0) or 0)


def _effective_raise_threshold(entry: Dict[str, Any], reference: Optional[float]) -> Any:
    """The raise threshold actually applied. For a relative diagnostic
    (``raise_threshold_relative``) this is ``raise_threshold * reference`` and a
    positive ``reference`` is MANDATORY -- there is no silent fallback to the
    raw fraction."""
    raise_t = entry["raise_threshold"]
    if entry.get("raise_threshold_relative"):
        if reference is None or not _is_num(reference) or float(reference) <= 0:
            raise ValueError(
                f"diagnostic {entry['id']!r} has a relative raise band "
                "(raise_threshold_relative=true) -- a positive `reference` (e.g. peak "
                f"concentration) is REQUIRED; got reference={reference!r}.")
        return float(raise_t) * float(reference)
    return raise_t


def evaluate(diagnostic_id: str, value: Any, *, reference: Optional[float] = None,
             schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compute the ``diagnostics.json`` entry for one diagnostic from its value.

    Returns the emission shape (``value``/``aggregation``/``unit``/
    ``warn_threshold``/``raise_threshold``/``reference``/``triggered_severity``/
    ``passed``). The emitted ``raise_threshold`` is the EFFECTIVE band (scaled by
    ``reference`` for a relative diagnostic), and ``reference`` records the value
    used -- so the reported band matches what was applied.

    ``reference`` is REQUIRED (positive) for a diagnostic whose raise band is
    relative (``raise_threshold_relative: true``, e.g. concentration_nonnegative
    -> a fraction of the peak concentration); calling without it raises.

    ``value`` may be ``None`` ONLY for a ``nullable`` diagnostic that did not run
    (no baseline / non-PRT); it emits ``triggered_severity="pass"``,
    ``passed=True``. ``None`` on a non-nullable diagnostic is an error.
    """
    entry = (schema and diagnostics_by_id(schema).get(diagnostic_id)) or DIAGNOSTICS.get(diagnostic_id)
    if entry is None:
        raise KeyError(f"unknown diagnostic id {diagnostic_id!r}.")

    base = {
        "value": value,
        "aggregation": entry["aggregation"],
        "unit": entry["input_artifact"]["unit"],
        "warn_threshold": entry["warn_threshold"],
    }

    # null semantics: a nullable diagnostic that did not run reports value=null
    # and PASSES (it did not fail a gate); a non-nullable null is an error.
    if value is None:
        if not entry["output"]["nullable"]:
            raise ValueError(
                f"diagnostic {diagnostic_id!r} is not nullable but value is None.")
        return {**base, "raise_threshold": entry["raise_threshold"],
                "reference": None, "triggered_severity": "pass", "passed": True}

    eff_raise = _effective_raise_threshold(entry, reference)   # validates reference for relative
    is_relative = bool(entry.get("raise_threshold_relative"))
    triggered = _triggered_severity(entry, value, eff_raise)
    return {
        **base,
        "raise_threshold": eff_raise,
        "reference": (float(reference) if is_relative else None),
        "triggered_severity": triggered,
        "passed": triggered != "raise",
    }


def _triggered_severity(entry: Dict[str, Any], value: Any, raise_t: Any) -> str:
    """*raise_t* is the EFFECTIVE raise threshold (already scaled for relative
    diagnostics by the caller)."""
    comparator = entry["comparator"]
    severity = entry["severity"]           # the MAX band this diagnostic can hit
    warn_t = entry["warn_threshold"]

    # --- boolean-aware BEFORE any float coercion (float(False)==0.0 is finite!) ---
    if isinstance(value, bool):
        if comparator == "finite":
            return "pass" if value else "raise"        # False -> raise (broken solve)
        if comparator == "eq":
            return "pass" if value == bool(raise_t) else severity
        raise SchemaError(
            f"diagnostic {entry['id']!r}: comparator {comparator!r} received a bool value.")

    if comparator == "finite":
        try:
            ok = math.isfinite(float(value))
        except (TypeError, ValueError):
            ok = False
        return "pass" if ok else "raise"

    if comparator == "in":
        tol = float(entry.get("numeric_tol", 0) or 0)
        ok = (0.0 - tol) <= float(value) <= (1.0 + tol)
        return "pass" if ok else "raise"

    if comparator == "eq":
        ok = abs(float(value) - float(raise_t)) <= _tol(entry)
        return "pass" if ok else severity  # eq is single-band (usually raise)

    v = float(value)
    if comparator == "le":
        if raise_t is not None and warn_t is not None:      # multi-band
            if v <= warn_t:
                return "pass"
            return "warn" if v <= raise_t else "raise"
        if raise_t is not None:                             # single raise
            return "pass" if v <= raise_t else "raise"
        return "pass" if v <= warn_t else "warn"            # single warn

    if comparator == "ge":
        if raise_t is not None and warn_t is not None:      # multi-band
            if v >= warn_t:
                return "pass"
            return "warn" if v >= raise_t else "raise"
        if raise_t is not None:                             # single raise
            return "pass" if v >= raise_t else "raise"
        return "pass" if v >= warn_t else "warn"            # single warn

    raise SchemaError(f"unhandled comparator {comparator!r} for diagnostic {entry['id']!r}.")


if __name__ == "__main__":
    sch = load_schema()
    print(f"schema OK: {len(sch['diagnostics'])} diagnostics, reporting -> {sch['reporting_surface']}")
    for d in sch["diagnostics"]:
        print(f"  {d['id']:28s} owner={d['owner']:4s} sev={d['severity']:5s} "
              f"warn={d['warn_threshold']} raise={d['raise_threshold']} enforced={d['enforced']}")
