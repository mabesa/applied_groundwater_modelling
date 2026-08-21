"""T1 S12 -- the single `claim_support_state` evaluator.

Implements `DOCUMENTATION/contracts/T0_3_claim_support_state.md` (DRAFT v2) Section 5,
authorised by `DOCUMENTATION/contracts/T0_1_C1_v2.md` entry **A14** and
`DESIGN_DOCS/T1_implementation_plan.md` v4 Phase 4 (S12).

STANDALONE MODULE -- pure Python, no MF6, no FloPy, no model imports. Per the plan's
parallel-safety rule, imports across this boundary are one-way (`artifact -> model`,
never `model -> artifact`): this module must never be imported by, and must never
import, `transport_srcpulse_demo.py`, `transport_prt_capture.py`,
`transport_base_model.py`, `transport_verify_2d.py`, `model_io_utils.py`, the harness,
any notebook, or `tasks_data.py`. A model module importing this one would pull it into
`_src_sha`'s transitive closure and bust every cache keyed on it.

WHAT THIS ANSWERS (T0.3 Section 1): for one claim, evaluated over the refinement series
it was tested on, "is this claim supported by the discretisation actually tested?" --
never a statement about parameter, conceptual-model or observational support, and never
a statement about a whole model or a whole run.

--------------------------------------------------------------------------------------
PENDING LECTURER DEFINITION -- read before touching `trend_predicate`
--------------------------------------------------------------------------------------
T0.3 Section 4.6 branches on whether a refinement series "shows a convergence or
stabilisation trend" (reason codes `no_convergence_trend` vs.
`decision_stable_metric_over_tolerance` / `metric_over_tolerance_no_decision`). No
deterministic predicate for that judgement exists yet -- it is with the lecturer. This
module does NOT invent one. Instead, `claim_support_state()` takes `trend_predicate` as
a REQUIRED, INJECTED callable argument: `trend_predicate(claim, series) -> bool`. It is
called only where Section 4.6 requires it (i.e. only once "within tolerance" has already
been ruled out by the module's own, tolerance-comparison logic, which IS deterministic
and does not depend on the missing definition). Tests supply fakes for both outcomes.
Do not add a default implementation here until the lecturer freezes one.

--------------------------------------------------------------------------------------
Everything else this module decides that T0.3 leaves to "the evaluator" (documented
here, not in T0.3, per T0.3 Section 5: "T1 writes the code")
--------------------------------------------------------------------------------------
- `series` is a list of `RunRecord`, each tagged with its refinement `axis`
  ("spatial" | "temporal") and assumed to already be in refinement order
  (coarse -> fine) within each axis -- this module does not re-sort by grid size,
  because grid identities are opaque values to it (no model-module import means no
  shared ordering key beyond list position).
- "Within tolerance" (the deterministic half of Section 4.6, as opposed to the
  lecturer-pending trend judgement) compares the LAST TWO points of each axis's
  metric-value sequence: `|last - prev| / max(|last|, |prev| if last == 0) <= tolerance`.
  This mirrors T0.2 Section 3 stopping rule 1 ("two successive refinements move the
  metric by less than its tolerance"). T0.2 owns the tolerance *numbers*; this module
  only owns the comparison mechanics.
- `method_can_answer` (row 1 of both Section 4.6 tables, "on ANY grid in the tested
  envelope") is read as: the method fails on the WHOLE tested envelope, i.e. every run
  in the series reports `method_can_answer=False`. A single incapable run inside an
  otherwise-answerable envelope is not this row -- Section 4.6's own scope note says
  the code is "first and narrow", not a synonym for "did not converge".
- Malformed input, per Section 5 ("Input: one claim record (type, metric, tolerance
  reference, threshold_record_id)"): `metric`, `tolerance` and a non-empty `series` are
  required on every claim record regardless of type; `threshold_record_id` is required
  only when `claim_type == "threshold-decision"` (T0.3 Section 5, explicit). All of
  these raise `ClaimSupportContractError`, never `null`.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Claim types (T0.2's inventory: numeric / threshold-decision / causal / illustrative)
# ---------------------------------------------------------------------------

CLAIM_TYPE_NUMERIC = "numeric"
CLAIM_TYPE_THRESHOLD_DECISION = "threshold-decision"
CLAIM_TYPE_CAUSAL = "causal"
CLAIM_TYPE_ILLUSTRATIVE = "illustrative"

CLAIM_TYPES: FrozenSet[str] = frozenset(
    {
        CLAIM_TYPE_NUMERIC,
        CLAIM_TYPE_THRESHOLD_DECISION,
        CLAIM_TYPE_CAUSAL,
        CLAIM_TYPE_ILLUSTRATIVE,
    }
)

# ---------------------------------------------------------------------------
# States -- T0.3 Section 2. Machine values are the contract.
# `not_yet_evaluated` is a DISPLAY-ONLY status and is deliberately NOT a member of
# STATES: it must be unrepresentable as a value of this enum (T0.3 Section 2, "There
# is no fourth state").
# ---------------------------------------------------------------------------

STATE_GRID_SUPPORTED = "grid_supported"
STATE_DECISION_SUPPORTED_MAGNITUDE_SENSITIVE = "decision_supported_magnitude_sensitive"
STATE_NOT_SUPPORTED = "not_supported"
STATE_NULL = None  # `null` -- the machine value is literally None, per T0.3 Section 2.

STATES: FrozenSet[Optional[str]] = frozenset(
    {
        STATE_GRID_SUPPORTED,
        STATE_DECISION_SUPPORTED_MAGNITUDE_SENSITIVE,
        STATE_NOT_SUPPORTED,
        STATE_NULL,
    }
)

# Explicitly and permanently excluded -- see module docstring / T0.3 Section 2.
DISPLAY_ONLY_NOT_YET_EVALUATED = "not_yet_evaluated"

# ---------------------------------------------------------------------------
# Reason codes -- T0.3 Section 3, exhaustive, every one reachable.
# ---------------------------------------------------------------------------

REASON_CONVERGED_BOTH_AXES = "converged_both_axes"
REASON_DECISION_STABLE_METRIC_OVER_TOLERANCE = "decision_stable_metric_over_tolerance"
REASON_DECISION_CHANGED_UNDER_REFINEMENT = "decision_changed_under_refinement"
REASON_NO_CONVERGENCE_TREND = "no_convergence_trend"
REASON_METRIC_OVER_TOLERANCE_NO_DECISION = "metric_over_tolerance_no_decision"
REASON_METHOD_CANNOT_ANSWER = "method_cannot_answer"
REASON_RUN_NOT_SOLVED = "run_not_solved"
REASON_PROVENANCE_INVALID = "provenance_invalid"
REASON_HORIZON_CENSORED = "horizon_censored"
REASON_METRIC_NOT_APPLICABLE = "metric_not_applicable"
REASON_REFINEMENT_AXIS_UNTESTED = "refinement_axis_untested"
REASON_CAUSAL_CLAIM_OUT_OF_SCOPE = "causal_claim_out_of_scope"
REASON_ILLUSTRATIVE_BY_DESIGN = "illustrative_by_design"

REASON_CODES: FrozenSet[str] = frozenset(
    {
        REASON_CONVERGED_BOTH_AXES,
        REASON_DECISION_STABLE_METRIC_OVER_TOLERANCE,
        REASON_DECISION_CHANGED_UNDER_REFINEMENT,
        REASON_NO_CONVERGENCE_TREND,
        REASON_METRIC_OVER_TOLERANCE_NO_DECISION,
        REASON_METHOD_CANNOT_ANSWER,
        REASON_RUN_NOT_SOLVED,
        REASON_PROVENANCE_INVALID,
        REASON_HORIZON_CENSORED,
        REASON_METRIC_NOT_APPLICABLE,
        REASON_REFINEMENT_AXIS_UNTESTED,
        REASON_CAUSAL_CLAIM_OUT_OF_SCOPE,
        REASON_ILLUSTRATIVE_BY_DESIGN,
    }
)

# ---------------------------------------------------------------------------
# Metric classification -- T0.3 Section 3 / Section 4.2 / Section 4.3b.
# ---------------------------------------------------------------------------

# "event-time metrics only" -- T0.3 Section 3's `metric_not_applicable` row, and the
# only metrics ever nulled by a validated bypass / non-arrival (Section 4.3b).
EVENT_TIME_METRICS: FrozenSet[str] = frozenset(
    {"t_first_exceedance", "t_first_detection", "t_peak"}
)

# Metrics whose value depends on the simulated tail -- T0.3 Section 4.2: "t_peak, peak
# magnitude, exceedance duration / window".
TAIL_DEPENDENT_METRICS: FrozenSet[str] = frozenset(
    {"t_peak", "peak_mgL", "exceedance_duration", "t_last_exceedance"}
)

# Metrics already resolved before the horizon in the frozen T0.2 inventory -- T0.3
# Section 4.2: "typically t_first_exceedance and t_first_detection". Deliberately
# disjoint from TAIL_DEPENDENT_METRICS: t_peak is tail-dependent, not early-resolved,
# even though it is also an event-time metric for Section 4.3b purposes.
EARLY_RESOLVED_METRICS: FrozenSet[str] = frozenset(
    {"t_first_exceedance", "t_first_detection"}
)

AXIS_SPATIAL = "spatial"
AXIS_TEMPORAL = "temporal"
REQUIRED_AXES: FrozenSet[str] = frozenset({AXIS_SPATIAL, AXIS_TEMPORAL})


# ---------------------------------------------------------------------------
# Typed contract error -- T0.3 Section 4.6 / Section 5: malformed input raises this,
# and MUST NEVER fall back to `null`, which is a reasoned outcome, not an error
# channel.
# ---------------------------------------------------------------------------


class ClaimSupportContractError(Exception):
    """Raised when the input to `claim_support_state` cannot be evaluated at all.

    This is distinct from every `null` outcome: `null` is a reasoned result (a state
    of the world the evaluator can honestly describe), this is a defect in the call --
    a claim record or series that does not meet the Section 5 input contract.
    """


# ---------------------------------------------------------------------------
# Input data model -- T0.3 Section 5's "one claim record ... + the refinement series
# ... + the run-health statuses of every run in that series", made concrete.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Claim:
    """One claim record, per T0.3 Section 5.

    `metric` and `tolerance` are required for every claim type (Section 5 lists them
    as part of every claim record). `threshold_record_id` is mandatory ONLY for
    `threshold-decision` claims (Section 5, explicit) -- its absence there is a typed
    contract error, never a `null` state.
    """

    claim_type: str
    metric: str
    tolerance: float
    threshold_record_id: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class RunHealth:
    """M0's three independent run-health statuses (T0.3 Section 1 table)."""

    solved: bool
    provenance_valid: bool
    horizon_censored: bool


@dataclasses.dataclass(frozen=True)
class RunRecord:
    """One run in the refinement series a claim is evaluated over.

    `axis` names which of the two required T0.2 series this run belongs to
    (`"spatial"` or `"temporal"`) -- T0.3 Section 4.4 requires both to be present.
    `grid_spec` / `cr_target` are opaque identity values (this module does not import
    the model's `GridSpec`) used only to build the Section 4.7 envelope.
    `event_occurred` is only meaningful for event-time metrics: `True` if the timed
    event happened before the horizon in this run, `False` for a validated
    non-occurrence (bypass), `None` when the claim's metric is not an event-time
    metric.
    `decision` is only meaningful for `threshold-decision` claims: `True` if the
    threshold was exceeded in this run, `False` if not, `None` otherwise.
    `method_can_answer` defaults to `True`; set `False` on a run where the method
    cannot address the claim at all (T0.3 Section 4.6's `method_cannot_answer` row).
    """

    run_id: str
    axis: str
    health: RunHealth
    metric_value: Optional[float] = None
    event_occurred: Optional[bool] = None
    decision: Optional[bool] = None
    method_can_answer: bool = True
    grid_spec: Any = None
    cr_target: Any = None


TrendPredicate = Callable[[Claim, Sequence[RunRecord]], bool]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_envelope(
    series: Sequence[RunRecord],
    stopping_rule: str,
    tolerance: float,
    threshold_record_id: Optional[str],
) -> Dict[str, Any]:
    """T0.3 Section 4.7: every emitted record carries the exact envelope it was
    computed over -- the grid and timestep series, the stopping rule, the tolerance,
    and the `threshold_record_id` where applicable."""
    grid_series = tuple(
        dict.fromkeys(r.grid_spec for r in series if r.axis == AXIS_SPATIAL)
    )
    timestep_series = tuple(
        dict.fromkeys(r.cr_target for r in series if r.axis == AXIS_TEMPORAL)
    )
    return {
        "grid_series": grid_series,
        "timestep_series": timestep_series,
        "stopping_rule": stopping_rule,
        "tolerance": tolerance,
        "threshold_record_id": threshold_record_id,
    }


def _build_evidence(
    claim: Claim,
    series: Sequence[RunRecord],
    envelope: Dict[str, Any],
    **extra: Any,
) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {
        "claim_type": claim.claim_type,
        "metric": claim.metric,
        "run_ids": [r.run_id for r in series],
        # Every independent run-health status is preserved here regardless of which
        # one drove the reason code (T0.3 Section 4.1b).
        "run_health": {
            r.run_id: {
                "solved": r.health.solved,
                "provenance_valid": r.health.provenance_valid,
                "horizon_censored": r.health.horizon_censored,
            }
            for r in series
        },
        "envelope": envelope,
    }
    evidence.update(extra)
    return evidence


def _record(
    state: Optional[str], reason_code: str, evidence: Dict[str, Any]
) -> Dict[str, Any]:
    assert state in STATES  # defensive: `not_yet_evaluated` can never leave here.
    assert reason_code in REASON_CODES
    return {"state": state, "reason_code": reason_code, "evidence": evidence}


def _axis_metric_sequence(
    series: Sequence[RunRecord], axis: str
) -> List[Optional[float]]:
    return [r.metric_value for r in series if r.axis == axis]


def _rel_change_within(v_prev: float, v_last: float, tolerance: float) -> bool:
    denom = abs(v_last) if v_last != 0 else abs(v_prev)
    if denom == 0:
        return True  # both exactly zero -- no movement at all.
    return abs(v_last - v_prev) / denom <= tolerance


def _within_tolerance(claim: Claim, series: Sequence[RunRecord]) -> bool:
    """The deterministic half of Section 4.6: "two successive refinements move the
    metric by less than tolerance" (T0.2 Section 3), checked on BOTH required axes.
    Does not consult `trend_predicate` -- that is only for the row that fires once
    this has already returned False."""
    for axis in (AXIS_SPATIAL, AXIS_TEMPORAL):
        values = _axis_metric_sequence(series, axis)
        if len(values) < 2:
            # A single point on an axis cannot demonstrate convergence -- the axis is
            # tested (Section 4.4's gate already passed), but stability is unproven.
            return False
        v_prev, v_last = values[-2], values[-1]
        if v_prev is None or v_last is None:
            raise ClaimSupportContractError(
                f"run reaching compute stage with metric '{claim.metric}' is missing "
                "metric_value -- malformed input, not a null-worthy outcome"
            )
        if not _rel_change_within(v_prev, v_last, claim.tolerance):
            return False
    return True


def _method_cannot_answer_whole_envelope(series: Sequence[RunRecord]) -> bool:
    """Row 1 of both Section 4.6 tables: the method fails on EVERY grid in the tested
    envelope, not merely one run inside it (Section 4.6's own "first and narrow" scope
    note)."""
    return all(not r.method_can_answer for r in series)


def _validate_inputs(claim: Claim, series: Sequence[RunRecord]) -> None:
    if claim is None:
        raise ClaimSupportContractError("claim record is required")
    if claim.claim_type not in CLAIM_TYPES:
        raise ClaimSupportContractError(
            f"unknown claim type '{claim.claim_type}' -- must be one of {sorted(CLAIM_TYPES)}"
        )
    # `causal` and `illustrative` are ALWAYS null (T0.3 Section 2.1) and the
    # claim-type gate short-circuits them BEFORE anything reads a metric or a
    # tolerance (Section 4, gate 1).  Demanding those fields from them would
    # reject well-formed records -- and the claim inventory holds 131 causal
    # claims, so the practical effect would be fabricated metrics and tolerances
    # invented purely to satisfy a validator.  Fields that exist only to pass a
    # check carry no meaning and invite made-up values.
    _needs_metric = claim.claim_type in (CLAIM_TYPE_NUMERIC, CLAIM_TYPE_THRESHOLD_DECISION)
    if _needs_metric:
        if not claim.metric:
            raise ClaimSupportContractError("claim.metric is required (T0.3 Section 5)")
        if claim.tolerance is None:
            raise ClaimSupportContractError(
                "claim.tolerance is required (T0.3 Section 5) -- tolerance values live "
                "in T0.2, but a reference to one is a mandatory field on every "
                "evaluable claim record"
            )
    if claim.tolerance is not None and claim.tolerance < 0:
        raise ClaimSupportContractError("claim.tolerance must be non-negative")
    if claim.claim_type == CLAIM_TYPE_THRESHOLD_DECISION and not claim.threshold_record_id:
        raise ClaimSupportContractError(
            "threshold_record_id is mandatory for every threshold-decision claim "
            "(T0.3 Section 5) -- its absence is a typed contract error, never a null state"
        )
    if not series:
        raise ClaimSupportContractError(
            "series is required -- claim_support_state cannot evaluate a claim "
            "without the refinement series it was tested over"
        )


# ---------------------------------------------------------------------------
# The evaluator -- T0.3 Section 5's single implementation.
# ---------------------------------------------------------------------------


def claim_support_state(
    claim: Claim,
    series: Sequence[RunRecord],
    trend_predicate: TrendPredicate,
    *,
    stopping_rule: str,
) -> Dict[str, Any]:
    """Evaluate ONE claim against the refinement series it was tested over.

    Deterministic: same inputs -> same output. No clock, no environment read.

    Applies T0.3 Section 4's ordered gate pipeline; the first gate that matches fixes
    both the state and the reason code:

      1. CLAIM-TYPE GATE           (Section 4, causal / illustrative)
      2. RUN HEALTH                (solver -> provenance -> horizon, Section 4.1/4.1b/4.2)
      3. METRIC APPLICABILITY      (Section 4.3b, event-time metrics on a bypass)
      4. EVIDENCE COMPLETENESS     (Section 4.4, both axes required)
      5. COMPUTE                   (Section 4.6's total, ordered truth table)

    Raises `ClaimSupportContractError` on malformed input (Section 4.6 / Section 5)
    -- never returns `null` for that; `null` is reserved for the reasoned outcomes
    the gate pipeline above produces.

    `trend_predicate(claim, series) -> bool` is a REQUIRED, INJECTED dependency for
    the "shows a convergence or stabilisation trend" judgement in Section 4.6, which
    has no frozen deterministic definition yet (module docstring). It is called only
    when the deterministic tolerance check has already found the series NOT within
    tolerance.
    """
    _validate_inputs(claim, series)

    envelope = _build_envelope(
        series, stopping_rule, claim.tolerance, claim.threshold_record_id
    )

    def null(reason_code: str, **extra: Any) -> Dict[str, Any]:
        return _record(STATE_NULL, reason_code, _build_evidence(claim, series, envelope, **extra))

    # --- 1. CLAIM-TYPE GATE ------------------------------------------------
    if claim.claim_type == CLAIM_TYPE_CAUSAL:
        return null(REASON_CAUSAL_CLAIM_OUT_OF_SCOPE)
    if claim.claim_type == CLAIM_TYPE_ILLUSTRATIVE:
        return null(REASON_ILLUSTRATIVE_BY_DESIGN)

    # --- 2. RUN HEALTH: solver -> provenance -> horizon (Section 4.1b) -----
    unsolved = [r.run_id for r in series if not r.health.solved]
    if unsolved:
        return null(REASON_RUN_NOT_SOLVED, unsolved_run_ids=unsolved)

    provenance_invalid = [r.run_id for r in series if not r.health.provenance_valid]
    if provenance_invalid:
        return null(REASON_PROVENANCE_INVALID, provenance_invalid_run_ids=provenance_invalid)

    censored = [r.run_id for r in series if r.health.horizon_censored]
    if censored:
        if claim.metric in TAIL_DEPENDENT_METRICS:
            return null(REASON_HORIZON_CENSORED, horizon_censored_run_ids=censored)
        if claim.metric in EARLY_RESOLVED_METRICS:
            # Section 4.2's exact condition: the event must have occurred before the
            # horizon in EVERY run of the series, not merely the uncensored ones.
            if not all(r.event_occurred is True for r in series):
                return null(REASON_HORIZON_CENSORED, horizon_censored_run_ids=censored)
        # else: metric does not depend on the tail -- horizon censoring does not gate it.

    # --- 3. METRIC APPLICABILITY (Section 4.3b) -----------------------------
    # A validated bypass / non-arrival nulls the event-time METRIC, never the
    # threshold DECISION. This gate therefore only ever fires for `numeric` claims:
    # a `threshold-decision` claim's own decision is evaluated in gate 5 regardless.
    if claim.claim_type == CLAIM_TYPE_NUMERIC and claim.metric in EVENT_TIME_METRICS:
        if any(r.event_occurred is False for r in series):
            return null(REASON_METRIC_NOT_APPLICABLE)

    # --- 4. EVIDENCE COMPLETENESS (Section 4.4) -----------------------------
    axes_present = {r.axis for r in series}
    if not REQUIRED_AXES.issubset(axes_present):
        missing = sorted(REQUIRED_AXES - axes_present)
        return null(REASON_REFINEMENT_AXIS_UNTESTED, untested_axes=missing)

    # --- 5. COMPUTE -- Section 4.6's total, ordered, mutually-exclusive table.
    if claim.claim_type == CLAIM_TYPE_THRESHOLD_DECISION:
        return _compute_threshold_decision(claim, series, envelope, trend_predicate)
    return _compute_numeric(claim, series, envelope, trend_predicate)


def _compute_threshold_decision(
    claim: Claim,
    series: Sequence[RunRecord],
    envelope: Dict[str, Any],
    trend_predicate: TrendPredicate,
) -> Dict[str, Any]:
    def state(s: Optional[str], reason_code: str, **extra: Any) -> Dict[str, Any]:
        return _record(s, reason_code, _build_evidence(claim, series, envelope, **extra))

    # Row 1 -- narrow, whole-envelope method failure.
    if _method_cannot_answer_whole_envelope(series):
        return state(STATE_NOT_SUPPORTED, REASON_METHOD_CANNOT_ANSWER)

    decisions = {r.decision for r in series}
    if None in decisions:
        raise ClaimSupportContractError(
            "every run must carry a decision for a threshold-decision claim reaching "
            "compute -- missing RunRecord.decision is malformed input"
        )

    # Row 2 -- decision flip precedes the tolerance check, deliberately (Section 4.6):
    # a flip inside tolerance is `not_supported`, never `grid_supported`.
    if len(decisions) > 1:
        return state(STATE_NOT_SUPPORTED, REASON_DECISION_CHANGED_UNDER_REFINEMENT)

    # Row 3.
    if _within_tolerance(claim, series):
        return state(STATE_GRID_SUPPORTED, REASON_CONVERGED_BOTH_AXES)

    # Rows 4/5 -- trend judgement only reached once "within tolerance" is ruled out.
    if not trend_predicate(claim, series):
        return state(STATE_NOT_SUPPORTED, REASON_NO_CONVERGENCE_TREND)
    return state(
        STATE_DECISION_SUPPORTED_MAGNITUDE_SENSITIVE,
        REASON_DECISION_STABLE_METRIC_OVER_TOLERANCE,
    )


def _compute_numeric(
    claim: Claim,
    series: Sequence[RunRecord],
    envelope: Dict[str, Any],
    trend_predicate: TrendPredicate,
) -> Dict[str, Any]:
    def state(s: Optional[str], reason_code: str, **extra: Any) -> Dict[str, Any]:
        return _record(s, reason_code, _build_evidence(claim, series, envelope, **extra))

    # Row 1.
    if _method_cannot_answer_whole_envelope(series):
        return state(STATE_NOT_SUPPORTED, REASON_METHOD_CANNOT_ANSWER)

    # Row 2. No decision exists for a numeric claim -- the middle state
    # (`decision_supported_magnitude_sensitive`) is structurally unreachable from
    # this function: it is never referenced below.
    if _within_tolerance(claim, series):
        return state(STATE_GRID_SUPPORTED, REASON_CONVERGED_BOTH_AXES)

    # Rows 3/4.
    if not trend_predicate(claim, series):
        return state(STATE_NOT_SUPPORTED, REASON_NO_CONVERGENCE_TREND)
    return state(STATE_NOT_SUPPORTED, REASON_METRIC_OVER_TOLERANCE_NO_DECISION)
