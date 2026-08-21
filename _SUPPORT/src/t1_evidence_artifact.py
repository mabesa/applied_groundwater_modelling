"""
t1_evidence_artifact -- T1 S13: the frozen T0.2b Section 5.1 evidence-artifact
schema, its fail-closed loader, and synthetic fixtures for testing.

Scope (DESIGN_DOCS/T1_implementation_plan.md v4, Phase 4, step S13; authorised
by DOCUMENTATION/contracts/T0_1_C1_v2.md entry A5): this module is the
SCHEMA + LOADER + FIXTURES only. It does not produce evidence from a real
model run -- that is S14 ("Artifact producer integration"), which runs after
S1-S11 land the capabilities (footprint, operator A, Courant policy, sink
support, the GWF arm, metrics) this schema's fields describe.

PARALLEL-SAFETY (T1_implementation_plan.md Phase 4, non-negotiable): imports
are one-way, `artifact -> model`, never `model -> artifact`. This module
imports nothing from `transport_srcpulse_demo`, `transport_prt_capture`,
`transport_base_model`, `transport_verify_2d`, `model_io_utils`, or any other
model module -- stdlib only. A model module importing this one would pull it
into `_src_sha`'s transitive closure and bust every cache keyed on it.

WHY THIS MATTERS: `grid_spec`, `locked_params` and `thread_pinning` are
therefore stored as OPAQUE, arbitrary JSON-safe mappings. This module does
not know the model's `MeshSpec`/`GridSpec` dataclass shape and does not
validate their internal structure beyond "is a non-empty mapping of
JSON-safe values" -- S14, which does know that shape, is responsible for
serialising it faithfully (e.g. `dataclasses.asdict(mesh_spec)`) before
handing a value to this module.

================================================================================
SCHEMA DECISIONS -- frozen here, stated explicitly per the task brief
================================================================================

T0_2b_metrics_and_causal_rule.md Section 5.1 lists the evidence-artifact
fields "at minimum", grouped into eight groups (Schema, Run identity,
Fingerprints, Environment, Run health, Metrics, Support, Role). Section 5.1
is a table of field NAMES; it does not fix wire-format keys, container
shapes, a serialisation format, a schema-version string, or a content-hash
algorithm. Those choices are frozen HERE, as follows.

1. SERIALISATION FORMAT: on-disk records are UTF-8 JSON objects (matching
   the existing `case_artifact_lock.py` convention in this package), written
   with `json.dump(..., indent=2, sort_keys=True)` for human-diffability and
   read back with `json.load`. The in-memory type is a single frozen
   `EvidenceRecord` dataclass with FLAT Python attributes (`record.run_id`,
   `record.src_sha`, ...); the JSON on disk nests those attributes under
   Section 5.1's eight group names (`schema`, `run_identity`,
   `fingerprints`, `environment`, `run_health`, `metrics`, `support`,
   `role`), plus one sibling top-level key `content_hash` (see #4). The
   flat-Python / nested-JSON split is deliberate: callers get simple
   attribute access; the on-disk shape mirrors the contract table so a
   human reviewer can match a JSON file to Section 5.1 by eye. The exact
   attribute <-> JSON-path mapping is `_FIELD_MAP` below, plus the two
   nested collections (`metrics`, `support.envelope`) handled explicitly.

2. SCHEMA VERSION: `SCHEMA_VERSION = "1.0.0"`, a plain string, stored at
   `schema.schema_version`. The loader's schema-version check is an EXACT
   string match against the currently-imported module's `SCHEMA_VERSION`
   (no semver range matching) -- any drift, including a patch bump, must be
   handled by a new module version or an explicit migration, never by the
   loader silently accepting a close-enough version.

3. `producer`: split into two on-disk leaves, `schema.producer_module`
   (str) and `schema.producer_version` (str), rather than one combined
   string -- "module + version" (Section 5.1's own wording) reads as two
   pieces of information, and keeping them separate lets a test change one
   without the other.

4. CONTENT-HASH ALGORITHM AND SCOPE (the loader's second fail-closed gate):
   - Algorithm: SHA-256 over a CANONICAL JSON serialisation of the record.
   - Canonicalisation: the full nested dict (as it will be / was written to
     disk) is walked recursively; dict keys are sorted; every `float` is
     replaced by the 2-element list `["__float_hex__", x.hex()]` before
     hashing (never by JSON's native float formatting) so the hash is
     sensitive to the exact IEEE-754 bit pattern rather than to whatever
     decimal string `repr()`/`json` happens to choose -- the same
     bit-exact convention already used for float identity elsewhere in
     this package's T1 work (`test_t1_gridspec.py`, "float.hex() round-trips;
     non-finite rejected"). NaN/Infinity are REJECTED (`ValueError`) rather
     than silently hashed -- a non-finite metric or tolerance is a defect,
     not a value to fingerprint.
   - The resulting JSON text uses `sort_keys=True, separators=(",", ":"),
     ensure_ascii=True` and is encoded as UTF-8 before hashing, matching
     `case_artifact_lock._fold_aggregate`'s determinism goals.
   - SCOPE -- what the hash covers: EVERY field in the record, i.e. all
     eight groups in full, EXCEPT:
       (a) the top-level `content_hash` key itself (self-referential -- a
           hash cannot cover its own value), and
       (b) `schema.schema_version` (covered by its OWN, separate,
           EARLIER gate -- see #5). Excluding it here means a
           schema-version mismatch and a content-hash mismatch are two
           independently observable, independently testable failures
           rather than one check masking the other.
     Every other field -- including every metric value, every fingerprint,
     every environment string, `run_role`, the whole support envelope --
     is covered: changing any of them changes the hash.

5. TWO DISTINCT FAIL-CLOSED GATES, in this order, both raising (never
   falling back):
     (1) `schema.schema_version != SCHEMA_VERSION` (or the key is absent)
         -> raises `SchemaVersionMismatchError`, BEFORE the hash is even
         computed -- an incompatible schema cannot be safely canonicalised
         by this module's rules in the first place.
     (2) recomputed content hash != stored `content_hash` (or the key is
         absent) -> raises `ContentHashMismatchError`.
   Neither exception is caught internally; `load_record` never returns a
   partially-trusted object when either gate fails, and never substitutes
   a default or a stale cached value.

6. THE "MISSING REQUIRED FIELD" RULE IS A THIRD, DIFFERENT CASE -- and is
   deliberately NOT a fail-closed raise. Section 5.1: "A record missing any
   field above is `provenance_valid = false` and cannot support a claim."
   This is a CONTENT-COMPLETENESS rule, not an INTEGRITY-VERIFICATION rule:
   a record that is internally self-consistent (schema version matches,
   content hash matches what was actually written) but was produced by a
   buggy or partial producer should still be LOADABLE -- e.g. so a report
   can say *which* fields are missing -- just never usable to support a
   claim. Concretely:
     - `run_health.provenance_valid` IS one of the on-disk fields (Section
       5.1 lists it explicitly under Run health), and a producer may write
       `true` there. That value is ADVISORY ONLY. On load, the AUTHORITATIVE
       `EvidenceRecord.provenance_valid` is always recomputed as
       `raw_declared_value AND structurally_complete` -- loading can only
       downgrade a declared `true` to `false`, never upgrade a declared
       `false` to `true`.
     - "Missing" means the JSON key is absent from its parent object.
       Fields that are LEGITIMATELY nullable in a well-formed record
       (`grid_role`, `counterpart_run_id`, `support.envelope.
       threshold_record_id`, and a censored metric's `value`) must still
       have their KEY present with an explicit JSON `null` -- an absent
       key is "missing"; a present key holding `null` is "complete, and
       the value happens to be null".
     - A field that IS present but fails validation (wrong JSON type, or
       violates one of the three CLOSED enumerations this schema freezes
       -- `run_role`, `claim_support_state`, `reason_code`, all
       exhaustively listed by the T0.2b/T0.3 contracts) is treated as a
       DIFFERENT, more severe defect than "missing": `load_record` RAISES
       `MalformedEvidenceRecordError` rather than silently marking the
       record incomplete. Rationale: a record holding a value outside a
       frozen enum is not "incomplete", it is WRONG, and letting it through
       as "loadable but invalid" risks leaking a bogus enum value into
       downstream code that only checks `provenance_valid` before reading
       `.run_role` / `.claim_support_state` / `.reason_code` directly.
       *** This split (missing -> loadable+invalid vs. malformed -> raise)
       is NOT stated in Section 5.1; it is this module's own choice about
       how to turn "missing" into an exact, testable rule, flagged here
       per the task brief rather than decided silently. ***
     - Similarly, "a field present with the wrong JSON type" is treated
       the same as "malformed" (raises), not the same as "missing" -- also
       not explicit in Section 5.1, also flagged here rather than buried.

7. `run_role` enumeration (CLOSED, frozen by Section 5.1 itself):
   `spatial_series`, `temporal_series`, `b_control`, `pilot`,
   `feasibility_probe` -- `RUN_ROLES` below. `claim_support_state`
   (`grid_supported`, `decision_supported_magnitude_sensitive`,
   `not_supported`, and the literal STRING `"null"`) and `reason_code`
   (the thirteen T0_3_claim_support_state.md Section 3 codes) are likewise
   closed enumerations, frozen from those contracts, not invented here.
   NOTE on `claim_support_state`'s fourth value: T0.3 Section 2 names it
   "`null` (no state; the reason code says why)". This module represents
   that as the JSON STRING `"null"`, never JSON's native `null` literal --
   using the native `null` would be indistinguishable from "this key is
   entirely absent" (a completeness failure), which is a different, more
   severe condition. `CLAIM_SUPPORT_STATES` below therefore includes the
   four-element closed set with `"null"` as an ordinary string member.

8. `solver_status` is DELIBERATELY left as a free-form non-empty string,
   not a closed enum. Unlike `run_role` / `claim_support_state` /
   `reason_code`, neither T0.2b nor T0.3 enumerates a closed set of solver
   status values -- T0.3 Section 4 only ever tests it against the single
   predicate "is not solved". Inventing a closed enum here would be adding
   policy the contracts do not state; flagged rather than done silently.

9. `run_health.cr_achieved` -- Section 5.1 writes this field as "`Cr`"
   (run_health: "... `nstp`, `Cr`, `ncpl`"). This module uses the on-disk
   JSON key `cr_achieved` (snake_case, matching the rest of the schema, and
   distinct from `run_identity.cr_target`) rather than the literal `"Cr"` --
   the contract does not fix a wire-format key name, so this is an explicit
   naming choice, not a restatement of frozen text.

10. `support.claim_id`: ADDED, and NOT in Section 5.1's field table. Flagged
    prominently because it is new policy, not a silent extension:
    Section 5.1 bundles `claim_support_state` / `reason_code` / the
    Section 4.7 envelope into the SAME record as a specific run's identity,
    fingerprints, environment and health. But `claim_support_state` is a
    property of (one claim, evaluated against one refinement series) per
    the T0_3 Section 5 evaluator contract ("Input: one claim record ... +
    the refinement series it was evaluated over"), NOT a property of a run
    in isolation -- a single run can be evidence for several different
    claims, each with its own state. Without an explicit identifier for
    *which claim* a record's `claim_support_state` describes, the field is
    ambiguous whenever more than one claim is evaluated against the same
    run (the ordinary case: one run typically feeds several claims' peak,
    timing, and threshold checks at once). This module therefore reads a
    "record" as one (claim, run) evaluation pair and adds `claim_id: str`
    to the Support group so that reading is well-defined and testable.
    *** This is this module's own resolution of an underspecified point in
    Section 5.1, not an authorised schema field -- surfaced here per the
    task brief rather than decided in silence; it should be confirmed (or
    overridden) before S14 wires a real producer against it. ***

11. `metrics` cardinality: Section 5.1 says "each Section 2 metric" carries
    the six sub-fields, but does not say every record must carry every
    metric Section 2 defines (`peak_mgL`, `t_peak`, `t_first_exceedance`,
    `t_last_exceedance`, `exceedance_duration`, `capture_halfwidth_m` --
    several of which are mutually inapplicable, e.g. `capture_halfwidth_m`
    is PRT-only). This module requires `metrics` to be a NON-EMPTY mapping
    of metric-name -> the six sub-fields, without fixing which names must
    appear -- "which metrics a given record must carry" is a producer-side
    (S14) policy question this schema does not settle. Flagged rather than
    guessed.

Fail-closed contract, restated precisely: `load_record()` raises
`SchemaVersionMismatchError` or `ContentHashMismatchError` and returns
NOTHING on those two failures -- it never falls back to a stale or default
value, and never returns a partially-populated object for them. A missing
*required field* is a third, different, non-raising case (#6 above): the
record loads, and `provenance_valid` is forced `False`.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

# ---------------------------------------------------------------------------
# Frozen constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"

#: T0_2b_metrics_and_causal_rule.md Sec 5.1 "Role" row -- closed, exhaustive.
RUN_ROLES: Tuple[str, ...] = (
    "spatial_series",
    "temporal_series",
    "b_control",
    "pilot",
    "feasibility_probe",
)

#: T0_3_claim_support_state.md Sec 2 -- closed, exhaustive. The fourth value
#: is the literal string "null" (see SCHEMA DECISIONS #7 above), never JSON
#: native null.
CLAIM_SUPPORT_STATES: Tuple[str, ...] = (
    "grid_supported",
    "decision_supported_magnitude_sensitive",
    "not_supported",
    "null",
)

#: T0_3_claim_support_state.md Sec 3 -- closed, exhaustive, all thirteen codes.
REASON_CODES: Tuple[str, ...] = (
    "converged_both_axes",
    "decision_stable_metric_over_tolerance",
    "decision_changed_under_refinement",
    "no_convergence_trend",
    "metric_over_tolerance_no_decision",
    "method_cannot_answer",
    "run_not_solved",
    "provenance_invalid",
    "horizon_censored",
    "metric_not_applicable",
    "refinement_axis_untested",
    "causal_claim_out_of_scope",
    "illustrative_by_design",
)

#: Required keys of `fingerprints.gis_hashes` -- Sec 5.1: "gis_hashes
#: (boundary + rivers)".
_GIS_HASH_KEYS: Tuple[str, ...] = ("model_boundary", "rivers")

#: Required sub-fields of every metrics-dict entry -- Sec 5.1 "Metrics" row.
_METRIC_SUBFIELDS: Tuple[str, ...] = (
    "value",
    "units",
    "algorithm_id",
    "interpolated",
    "censored",
    "tie_broken",
)

#: Required sub-fields of `support.envelope` -- T0.3 Sec 4.7's envelope,
#: named verbatim in Sec 5.1's Support row.
_ENVELOPE_SUBFIELDS: Tuple[str, ...] = (
    "grid_series",
    "timestep_series",
    "stopping_rule",
    "tolerance",
    "threshold_record_id",
)

_HASH_KEY = "content_hash"


# ---------------------------------------------------------------------------
# Exceptions -- the fail-closed vocabulary
# ---------------------------------------------------------------------------


class EvidenceArtifactError(ValueError):
    """Base class for every error this module raises."""


class SchemaVersionMismatchError(EvidenceArtifactError):
    """Raised by `load_record` when the on-disk schema_version does not
    exactly match this module's `SCHEMA_VERSION`, or is absent."""


class ContentHashMismatchError(EvidenceArtifactError):
    """Raised by `load_record` when the recomputed content hash does not
    match the on-disk `content_hash`, or it is absent."""


class MalformedEvidenceRecordError(EvidenceArtifactError):
    """Raised when a present field violates a closed enumeration or its
    required JSON type -- see SCHEMA DECISIONS #6 above. Distinct from a
    field being simply absent (which yields `provenance_valid = False`,
    not a raise)."""


# ---------------------------------------------------------------------------
# Nested value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricRecord:
    """One named metric's measurement, per T0_2b Sec 5.1 "Metrics" row.

    `value` is `None` exactly when the metric is legitimately unavailable
    (e.g. `censored=True`, or the metric could not be computed) -- the key
    must still be present.
    """

    value: Optional[float]
    units: str
    algorithm_id: str
    interpolated: bool
    censored: bool
    tie_broken: bool


@dataclass(frozen=True)
class SupportEnvelope:
    """T0_3_claim_support_state.md Sec 4.7's envelope: "the grid and
    timestep series, the stopping rule, the tolerance, and the
    threshold_record_id"."""

    grid_series: Tuple[Union[float, int, str, bool, None], ...]
    timestep_series: Tuple[Union[float, int, str, bool, None], ...]
    stopping_rule: str
    tolerance: Optional[float]
    threshold_record_id: Optional[str]


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceRecord:
    """The T0_2b Sec 5.1 evidence-artifact record, one (claim, run)
    evaluation pair (see SCHEMA DECISIONS #10 for why `claim_id` is here).

    All fields are declared `Optional`-compatible at the type level because
    an INCOMPLETE record (missing required fields) must still be
    representable -- see SCHEMA DECISIONS #6. Whether a given attribute is
    actually required is governed by `_FIELD_MAP` / `REQUIRED_FIELD_PATHS`,
    not by the Python type annotation.
    """

    # -- schema / producer --------------------------------------------------
    schema_version: Optional[str]
    producer_module: Optional[str]
    producer_version: Optional[str]

    # -- run identity ---------------------------------------------------------
    run_id: Optional[str]
    grid_spec: Optional[Mapping[str, Any]]
    cr_target: Optional[float]
    case_id: Optional[str]
    nstp_cap: Optional[int]

    # -- fingerprints ---------------------------------------------------------
    src_sha: Optional[str]
    flow_fingerprint: Optional[str]
    gis_hashes: Optional[Mapping[str, str]]
    locked_params: Optional[Mapping[str, Any]]
    roster_hash: Optional[str]

    # -- environment ------------------------------------------------------
    os_arch: Optional[str]
    mf6_path: Optional[str]
    mf6_sha256: Optional[str]
    triangle_path: Optional[str]
    triangle_sha256: Optional[str]
    flopy_version: Optional[str]
    numpy_version: Optional[str]
    python_version: Optional[str]
    thread_pinning: Optional[Mapping[str, Any]]

    # -- run health -------------------------------------------------------
    solver_status: Optional[str]
    horizon_censored: Optional[bool]
    cr_capped: Optional[bool]
    nstp: Optional[int]
    cr_achieved: Optional[float]
    ncpl: Optional[int]

    # -- metrics ------------------------------------------------------------
    metrics: Optional[Mapping[str, MetricRecord]]

    # -- support --------------------------------------------------------------
    claim_id: Optional[str]
    claim_support_state: Optional[str]
    reason_code: Optional[str]
    envelope: Optional[SupportEnvelope]

    # -- role -----------------------------------------------------------------
    run_role: Optional[str]
    is_feasibility_probe: Optional[bool]
    grid_role: Optional[str]
    counterpart_run_id: Optional[str]

    # -- authoritative, loader/builder-computed, never trusted verbatim ----
    provenance_valid: bool = field(default=False)


# ---------------------------------------------------------------------------
# Flat-attribute <-> nested-JSON-path mapping (SCHEMA DECISIONS #1)
# ---------------------------------------------------------------------------

# (json_path, attribute_name) for every scalar-or-opaque-mapping field.
# `metrics` and the `support.envelope.*` subtree are handled separately
# because they are structured, not scalar.
_FIELD_MAP: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("schema", "schema_version"), "schema_version"),
    (("schema", "producer_module"), "producer_module"),
    (("schema", "producer_version"), "producer_version"),
    (("run_identity", "run_id"), "run_id"),
    (("run_identity", "grid_spec"), "grid_spec"),
    (("run_identity", "cr_target"), "cr_target"),
    (("run_identity", "case_id"), "case_id"),
    (("run_identity", "nstp_cap"), "nstp_cap"),
    (("fingerprints", "src_sha"), "src_sha"),
    (("fingerprints", "flow_fingerprint"), "flow_fingerprint"),
    (("fingerprints", "gis_hashes"), "gis_hashes"),
    (("fingerprints", "locked_params"), "locked_params"),
    (("fingerprints", "roster_hash"), "roster_hash"),
    (("environment", "os_arch"), "os_arch"),
    (("environment", "mf6_path"), "mf6_path"),
    (("environment", "mf6_sha256"), "mf6_sha256"),
    (("environment", "triangle_path"), "triangle_path"),
    (("environment", "triangle_sha256"), "triangle_sha256"),
    (("environment", "flopy_version"), "flopy_version"),
    (("environment", "numpy_version"), "numpy_version"),
    (("environment", "python_version"), "python_version"),
    (("environment", "thread_pinning"), "thread_pinning"),
    (("run_health", "solver_status"), "solver_status"),
    (("run_health", "provenance_valid"), "provenance_valid"),
    (("run_health", "horizon_censored"), "horizon_censored"),
    (("run_health", "cr_capped"), "cr_capped"),
    (("run_health", "nstp"), "nstp"),
    (("run_health", "cr_achieved"), "cr_achieved"),
    (("run_health", "ncpl"), "ncpl"),
    (("support", "claim_id"), "claim_id"),
    (("support", "claim_support_state"), "claim_support_state"),
    (("support", "reason_code"), "reason_code"),
    (("role", "run_role"), "run_role"),
    (("role", "is_feasibility_probe"), "is_feasibility_probe"),
    (("role", "grid_role"), "grid_role"),
    (("role", "counterpart_run_id"), "counterpart_run_id"),
)

#: Every dotted JSON path a COMPLETE record must have present (key exists),
#: used to compute structural completeness (SCHEMA DECISIONS #6). Includes
#: the two structured subtrees (`metrics`, `support.envelope.*`) explicitly.
REQUIRED_FIELD_PATHS: Tuple[Tuple[str, ...], ...] = tuple(
    p for p, _ in _FIELD_MAP
) + (
    ("metrics",),
    ("support", "envelope"),
    ("support", "envelope", "grid_series"),
    ("support", "envelope", "timestep_series"),
    ("support", "envelope", "stopping_rule"),
    ("support", "envelope", "tolerance"),
    ("support", "envelope", "threshold_record_id"),
)

#: The one field this module deliberately excludes from content-hash
#: coverage, other than the hash field itself (SCHEMA DECISIONS #4).
_HASH_EXCLUDED_PATH: Tuple[str, ...] = ("schema", "schema_version")


# ---------------------------------------------------------------------------
# dict <-> path helpers
# ---------------------------------------------------------------------------


def _get_path(d: Mapping[str, Any], path: Sequence[str]) -> Any:
    node: Any = d
    for key in path:
        if not isinstance(node, Mapping) or key not in node:
            raise KeyError(path)
        node = node[key]
    return node


def _has_path(d: Mapping[str, Any], path: Sequence[str]) -> bool:
    node: Any = d
    for key in path:
        if not isinstance(node, Mapping) or key not in node:
            return False
        node = node[key]
    return True


def _set_path(d: MutableMapping[str, Any], path: Sequence[str], value: Any) -> None:
    node = d
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value


# ---------------------------------------------------------------------------
# Canonicalisation + content hash (SCHEMA DECISIONS #4)
# ---------------------------------------------------------------------------


def _canonicalize(obj: Any) -> Any:
    """Recursively convert *obj* into a JSON-safe, hash-canonical shape.

    Floats become `["__float_hex__", x.hex()]`; NaN/Infinity raise. Tuples
    are treated as lists. Dict key order does not matter here because
    `json.dumps(..., sort_keys=True)` sorts at serialisation time; this
    function only needs to normalise VALUES.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"non-finite float cannot be hashed: {obj!r}")
        return ["__float_hex__", obj.hex()]
    if isinstance(obj, int):
        return obj
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, Mapping):
        return {str(k): _canonicalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(v) for v in obj]
    raise TypeError(f"value of type {type(obj)!r} is not hashable by this schema: {obj!r}")


def compute_content_hash(raw: Mapping[str, Any]) -> str:
    """Return the sha256 hex digest covering every field of *raw* EXCEPT
    the top-level `content_hash` key and `schema.schema_version`
    (SCHEMA DECISIONS #4).

    *raw* is the full nested JSON-shaped dict (as produced by
    `EvidenceRecord`-to-JSON conversion or as loaded from disk) -- NOT an
    `EvidenceRecord`.
    """
    view = copy.deepcopy(dict(raw))
    view.pop(_HASH_KEY, None)
    if "schema" in view and isinstance(view["schema"], dict):
        view["schema"].pop("schema_version", None)
    canonical = _canonicalize(view)
    text = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# EvidenceRecord -> raw JSON dict
# ---------------------------------------------------------------------------


def _metrics_to_json(metrics: Optional[Mapping[str, MetricRecord]]) -> Optional[dict]:
    if metrics is None:
        return None
    out: dict = {}
    for name, m in metrics.items():
        out[name] = {
            "value": m.value,
            "units": m.units,
            "algorithm_id": m.algorithm_id,
            "interpolated": m.interpolated,
            "censored": m.censored,
            "tie_broken": m.tie_broken,
        }
    return out


def _envelope_to_json(env: Optional[SupportEnvelope]) -> Optional[dict]:
    if env is None:
        return None
    return {
        "grid_series": list(env.grid_series),
        "timestep_series": list(env.timestep_series),
        "stopping_rule": env.stopping_rule,
        "tolerance": env.tolerance,
        "threshold_record_id": env.threshold_record_id,
    }


def record_to_raw_dict(record: EvidenceRecord) -> dict:
    """Convert an `EvidenceRecord` into the nested, JSON-ready dict shape
    (without `content_hash` -- callers that want the hash-stamped version
    should use `dump_record`)."""
    raw: dict = {}
    for path, attr in _FIELD_MAP:
        _set_path(raw, path, getattr(record, attr))
    metrics_json = _metrics_to_json(record.metrics)
    if metrics_json is not None:
        raw["metrics"] = metrics_json
    envelope_json = _envelope_to_json(record.envelope)
    if envelope_json is not None:
        _set_path(raw, ("support", "envelope"), envelope_json)
    return raw


def dump_record(record: EvidenceRecord) -> dict:
    """`record_to_raw_dict` plus a freshly-computed `content_hash` sibling
    key. This is the exact shape `write_record` writes to disk."""
    raw = record_to_raw_dict(record)
    raw[_HASH_KEY] = compute_content_hash(raw)
    return raw


def write_record(record: EvidenceRecord, path: Union[str, Path]) -> dict:
    """Write *record* to *path* as canonical JSON. Returns the raw dict
    that was written (same shape `dump_record` returns)."""
    raw = dump_record(record)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return raw


# ---------------------------------------------------------------------------
# raw JSON dict -> EvidenceRecord (structural completeness + type/enum checks)
# ---------------------------------------------------------------------------


def _check_type(path: Tuple[str, ...], value: Any, expected: type, allow_none: bool) -> Optional[str]:
    if value is None:
        if allow_none:
            return None
        return f"{'.'.join(path)}: expected {expected.__name__}, got null"
    if expected is float and isinstance(value, bool):
        return f"{'.'.join(path)}: expected float, got bool"
    if expected is float and isinstance(value, int):
        return None  # JSON has no int/float distinction for whole numbers
    if not isinstance(value, expected):
        return f"{'.'.join(path)}: expected {expected.__name__}, got {type(value).__name__}"
    return None


def _structural_completeness(raw: Mapping[str, Any]) -> Tuple[bool, Tuple[Tuple[str, ...], ...]]:
    """Return (is_complete, missing_paths) per REQUIRED_FIELD_PATHS."""
    missing = tuple(p for p in REQUIRED_FIELD_PATHS if not _has_path(raw, p))
    return (len(missing) == 0, missing)


def _validate_enums_and_types(raw: Mapping[str, Any]) -> None:
    """Raise `MalformedEvidenceRecordError` for any PRESENT field that
    violates a closed enumeration or its required JSON type. Fields that
    are simply ABSENT are not this function's concern -- that is
    `_structural_completeness`'s job and yields `provenance_valid=False`,
    not a raise (SCHEMA DECISIONS #6)."""
    errors = []

    if _has_path(raw, ("role", "run_role")):
        val = _get_path(raw, ("role", "run_role"))
        if val is not None and val not in RUN_ROLES:
            errors.append(f"role.run_role: {val!r} is not one of {RUN_ROLES!r}")

    if _has_path(raw, ("support", "claim_support_state")):
        val = _get_path(raw, ("support", "claim_support_state"))
        if val is not None and val not in CLAIM_SUPPORT_STATES:
            errors.append(
                f"support.claim_support_state: {val!r} is not one of {CLAIM_SUPPORT_STATES!r}"
            )

    if _has_path(raw, ("support", "reason_code")):
        val = _get_path(raw, ("support", "reason_code"))
        if val is not None and val not in REASON_CODES:
            errors.append(f"support.reason_code: {val!r} is not one of {REASON_CODES!r}")

    if _has_path(raw, ("role", "is_feasibility_probe")):
        val = _get_path(raw, ("role", "is_feasibility_probe"))
        err = _check_type(("role", "is_feasibility_probe"), val, bool, allow_none=False)
        if err:
            errors.append(err)

    if _has_path(raw, ("run_health", "provenance_valid")):
        val = _get_path(raw, ("run_health", "provenance_valid"))
        err = _check_type(("run_health", "provenance_valid"), val, bool, allow_none=False)
        if err:
            errors.append(err)

    if _has_path(raw, ("fingerprints", "gis_hashes")):
        gh = _get_path(raw, ("fingerprints", "gis_hashes"))
        if not isinstance(gh, Mapping):
            errors.append("fingerprints.gis_hashes: expected object, got " f"{type(gh).__name__}")
        else:
            for k in _GIS_HASH_KEYS:
                if k not in gh:
                    errors.append(f"fingerprints.gis_hashes: missing required key {k!r}")
                elif not isinstance(gh[k], str):
                    errors.append(f"fingerprints.gis_hashes.{k}: expected str")

    if _has_path(raw, ("metrics",)):
        metrics = _get_path(raw, ("metrics",))
        if not isinstance(metrics, Mapping):
            errors.append("metrics: expected object")
        elif len(metrics) == 0:
            errors.append("metrics: must be non-empty (SCHEMA DECISIONS #11)")
        else:
            for name, m in metrics.items():
                if not isinstance(m, Mapping):
                    errors.append(f"metrics.{name}: expected object")
                    continue
                for sub in _METRIC_SUBFIELDS:
                    if sub not in m:
                        errors.append(f"metrics.{name}.{sub}: missing")
                for bool_field in ("interpolated", "censored", "tie_broken"):
                    if bool_field in m:
                        err = _check_type(
                            ("metrics", name, bool_field), m[bool_field], bool, allow_none=False
                        )
                        if err:
                            errors.append(err)

    if _has_path(raw, ("support", "envelope")):
        env = _get_path(raw, ("support", "envelope"))
        if not isinstance(env, Mapping):
            errors.append("support.envelope: expected object")
        else:
            for sub in ("grid_series", "timestep_series"):
                if sub in env and not isinstance(env[sub], (list, tuple)):
                    errors.append(f"support.envelope.{sub}: expected array")

    if errors:
        raise MalformedEvidenceRecordError(
            "evidence record fails schema validation: " + "; ".join(errors)
        )


def _metrics_from_json(raw_metrics: Any) -> Optional[Mapping[str, MetricRecord]]:
    if raw_metrics is None:
        return None
    out = {}
    for name, m in raw_metrics.items():
        out[name] = MetricRecord(
            value=m.get("value"),
            units=m.get("units"),
            algorithm_id=m.get("algorithm_id"),
            interpolated=m.get("interpolated"),
            censored=m.get("censored"),
            tie_broken=m.get("tie_broken"),
        )
    return out


def _envelope_from_json(raw_env: Any) -> Optional[SupportEnvelope]:
    if raw_env is None:
        return None
    return SupportEnvelope(
        grid_series=tuple(raw_env.get("grid_series") or ()),
        timestep_series=tuple(raw_env.get("timestep_series") or ()),
        stopping_rule=raw_env.get("stopping_rule"),
        tolerance=raw_env.get("tolerance"),
        threshold_record_id=raw_env.get("threshold_record_id"),
    )


def record_from_raw_dict(raw: Mapping[str, Any]) -> EvidenceRecord:
    """Build an `EvidenceRecord` from a nested raw dict (already past the
    schema-version / content-hash gates, or being built fresh by a
    fixture). Validates closed enums and key sub-field types, raising
    `MalformedEvidenceRecordError` on violation (SCHEMA DECISIONS #6);
    never raises merely for an absent field -- absence only affects the
    computed `provenance_valid`.
    """
    _validate_enums_and_types(raw)

    kwargs: dict = {}
    for path, attr in _FIELD_MAP:
        kwargs[attr] = _get_path(raw, path) if _has_path(raw, path) else None
    kwargs["metrics"] = _metrics_from_json(raw.get("metrics"))
    kwargs["envelope"] = _envelope_from_json(
        raw.get("support", {}).get("envelope") if isinstance(raw.get("support"), Mapping) else None
    )

    is_complete, _missing = _structural_completeness(raw)
    declared_valid = bool(kwargs.get("provenance_valid"))
    kwargs["provenance_valid"] = bool(declared_valid and is_complete)

    return EvidenceRecord(**kwargs)


def missing_required_fields(raw: Mapping[str, Any]) -> Tuple[str, ...]:
    """Return the dotted paths of every required field absent from *raw*,
    for diagnostics (e.g. reporting why `provenance_valid` is False)."""
    _complete, missing = _structural_completeness(raw)
    return tuple(".".join(p) for p in missing)


# ---------------------------------------------------------------------------
# The fail-closed loader
# ---------------------------------------------------------------------------


def load_record(path: Union[str, Path]) -> EvidenceRecord:
    """Load one evidence record from *path*, failing closed.

    Raises
    ------
    SchemaVersionMismatchError
        if `schema.schema_version` is absent or != `SCHEMA_VERSION`.
    ContentHashMismatchError
        if `content_hash` is absent or does not match the recomputed hash.
    MalformedEvidenceRecordError
        if a present field violates a closed enum or required type.

    Never falls back to a default or stale value on the first two
    failures; never returns an object for them.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return record_from_raw_dict_fail_closed(raw, source=str(path))


def loads_record(text: str, source: str = "<string>") -> EvidenceRecord:
    """`load_record`, but from an in-memory JSON string (used by tests that
    want to avoid the filesystem)."""
    raw = json.loads(text)
    return record_from_raw_dict_fail_closed(raw, source=source)


def record_from_raw_dict_fail_closed(raw: Mapping[str, Any], source: str = "<dict>") -> EvidenceRecord:
    """The shared fail-closed core of `load_record` / `loads_record`:
    schema-version gate, then content-hash gate, then delegate to
    `record_from_raw_dict` for enum/type validation and construction.
    """
    if not isinstance(raw, Mapping):
        raise MalformedEvidenceRecordError(f"{source}: evidence record is not a JSON object")

    schema_version = raw.get("schema", {}).get("schema_version") if isinstance(raw.get("schema"), Mapping) else None
    if schema_version != SCHEMA_VERSION:
        raise SchemaVersionMismatchError(
            f"{source}: schema_version {schema_version!r} does not match "
            f"the loader's {SCHEMA_VERSION!r} -- refusing to load"
        )

    if _HASH_KEY not in raw:
        raise ContentHashMismatchError(f"{source}: no {_HASH_KEY!r} field present -- cannot verify")
    stored_hash = raw[_HASH_KEY]
    recomputed_hash = compute_content_hash(raw)
    if stored_hash != recomputed_hash:
        raise ContentHashMismatchError(
            f"{source}: content_hash mismatch (stored {stored_hash!r} != "
            f"recomputed {recomputed_hash!r}) -- record may be corrupt or tampered"
        )

    return record_from_raw_dict(raw)


# ---------------------------------------------------------------------------
# Fixtures -- synthetic, well-formed records for tests (no model imports)
# ---------------------------------------------------------------------------


def build_fixture_record(
    *,
    run_role: str,
    run_id: str = "fixture-run-0001",
    claim_id: str = "claim_peak_mgL_pfoa",
    case_id: str = "case_pfoa_reference",
    is_feasibility_probe: Optional[bool] = None,
    grid_role: Optional[str] = "fine",
    counterpart_run_id: Optional[str] = None,
    claim_support_state: str = "grid_supported",
    reason_code: str = "converged_both_axes",
    provenance_valid: bool = True,
    metrics: Optional[Mapping[str, MetricRecord]] = None,
    envelope: Optional[SupportEnvelope] = None,
    **overrides: Any,
) -> EvidenceRecord:
    """Build a synthetic, well-formed `EvidenceRecord` for tests/dev use.

    `run_role` has NO default -- it must always be supplied explicitly,
    mirroring Section 5.1's "run_role is MANDATORY" (this is the strict,
    fixture-construction side of that rule; `test_run_role_is_mandatory`
    also exercises the loader's loadable-but-invalid side, see #6 above).

    This function never touches a model module, MF6, FloPy, or the
    filesystem beyond what the caller does with the returned record --
    every value is a plain, hand-authored stand-in.
    """
    if run_role not in RUN_ROLES:
        raise MalformedEvidenceRecordError(f"run_role must be one of {RUN_ROLES!r}, got {run_role!r}")

    if is_feasibility_probe is None:
        is_feasibility_probe = run_role == "feasibility_probe"

    if metrics is None:
        metrics = {
            "peak_mgL": MetricRecord(
                value=5.277,
                units="mg/L",
                algorithm_id="max_breakthrough_v1",
                interpolated=False,
                censored=False,
                tie_broken=False,
            ),
            "t_peak": MetricRecord(
                value=38.8043478261,
                units="d",
                algorithm_id="lattice_argmax_v1",
                interpolated=False,
                censored=False,
                tie_broken=False,
            ),
        }

    if envelope is None:
        envelope = SupportEnvelope(
            grid_series=(50.0, 20.0, 10.0, 5.0, 2.0),
            timestep_series=(0.9, 0.45, 0.225),
            stopping_rule="tolerance_reached",
            tolerance=0.02,
            threshold_record_id="thr_pfoa_1ugL",
        )

    fields: dict = dict(
        schema_version=SCHEMA_VERSION,
        producer_module="t1_evidence_artifact",
        producer_version="0.1.0",
        run_id=run_id,
        grid_spec={"corridor_cell_size_m": 10.0, "levels": [{"cell_size": 10.0}]},
        cr_target=0.9,
        case_id=case_id,
        nstp_cap=5000,
        src_sha="0" * 64,
        flow_fingerprint="1" * 64,
        gis_hashes={"model_boundary": "2" * 64, "rivers": "3" * 64},
        locked_params={"porosity": 0.3, "alpha_L_m": 10.0},
        roster_hash="4" * 64,
        os_arch="darwin-arm64",
        mf6_path="/usr/local/bin/mf6",
        mf6_sha256="5" * 64,
        triangle_path="/usr/local/bin/triangle",
        triangle_sha256="6" * 64,
        flopy_version="3.9.2",
        numpy_version="2.1.0",
        python_version="3.12.7",
        thread_pinning={"OMP_NUM_THREADS": "1"},
        solver_status="solved",
        provenance_valid=provenance_valid,
        horizon_censored=False,
        cr_capped=False,
        nstp=122,
        cr_achieved=0.87,
        ncpl=5230,
        metrics=metrics,
        claim_id=claim_id,
        claim_support_state=claim_support_state,
        reason_code=reason_code,
        envelope=envelope,
        run_role=run_role,
        is_feasibility_probe=is_feasibility_probe,
        grid_role=grid_role,
        counterpart_run_id=counterpart_run_id,
    )
    fields.update(overrides)
    return EvidenceRecord(**fields)
