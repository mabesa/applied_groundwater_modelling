"""Tests for T1 S12 -- the `claim_support_state` evaluator
(DESIGN_DOCS/T1_implementation_plan.md v4 Phase 4; DOCUMENTATION/contracts/
T0_3_claim_support_state.md; test-ledger node names from the plan's Section 4).

Run with:  uv run pytest _SUPPORT/tests/test_t1_claim_support_state.py -v
"""
from __future__ import annotations

import itertools
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import t1_claim_support_state as css  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------

def health(solved=True, provenance_valid=True, horizon_censored=False):
    return css.RunHealth(
        solved=solved, provenance_valid=provenance_valid, horizon_censored=horizon_censored
    )


def run(
    run_id,
    axis,
    metric_value=None,
    decision=None,
    event_occurred=None,
    method_can_answer=True,
    grid_spec=None,
    cr_target=None,
    h=None,
):
    return css.RunRecord(
        run_id=run_id,
        axis=axis,
        health=h if h is not None else health(),
        metric_value=metric_value,
        event_occurred=event_occurred,
        decision=decision,
        method_can_answer=method_can_answer,
        grid_spec=grid_spec,
        cr_target=cr_target,
    )


def two_axis_series(spatial_values, temporal_values, **kwargs):
    """Build a minimal both-axes-tested series from two metric-value sequences."""
    series = []
    for i, v in enumerate(spatial_values):
        series.append(run(f"sp{i}", css.AXIS_SPATIAL, metric_value=v, grid_spec=50 - 10 * i, **kwargs))
    for i, v in enumerate(temporal_values):
        series.append(run(f"tm{i}", css.AXIS_TEMPORAL, metric_value=v, cr_target=0.9 / (i + 1), **kwargs))
    return series


def TREND_TRUE(claim, series):
    return True


def TREND_FALSE(claim, series):
    return False


def numeric_claim(metric="peak_mgL", tolerance=0.02):
    return css.Claim(claim_type=css.CLAIM_TYPE_NUMERIC, metric=metric, tolerance=tolerance)


def decision_claim(metric="peak_mgL", tolerance=0.02, threshold_record_id="thr-1"):
    return css.Claim(
        claim_type=css.CLAIM_TYPE_THRESHOLD_DECISION,
        metric=metric,
        tolerance=tolerance,
        threshold_record_id=threshold_record_id,
    )


CALL_KW = {"stopping_rule": "tolerance_reached"}


# ---------------------------------------------------------------------------
# test_every_state_and_reason_code_reachable
# ---------------------------------------------------------------------------

def test_every_state_and_reason_code_reachable():
    reached_states = set()
    reached_reasons = set()

    def record(result):
        reached_states.add(result["state"])
        reached_reasons.add(result["reason_code"])

    # causal_claim_out_of_scope -> null
    claim = css.Claim(claim_type=css.CLAIM_TYPE_CAUSAL, metric="peak_mgL", tolerance=0.02)
    record(css.claim_support_state(claim, [run("r0", css.AXIS_SPATIAL)], TREND_TRUE, **CALL_KW))

    # illustrative_by_design -> null
    claim = css.Claim(claim_type=css.CLAIM_TYPE_ILLUSTRATIVE, metric="peak_mgL", tolerance=0.02)
    record(css.claim_support_state(claim, [run("r0", css.AXIS_SPATIAL)], TREND_TRUE, **CALL_KW))

    # run_not_solved -> null
    claim = numeric_claim()
    series = two_axis_series([1.0, 1.0], [1.0, 1.0], h=health(solved=False))
    record(css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW))

    # provenance_invalid -> null
    series = two_axis_series([1.0, 1.0], [1.0, 1.0], h=health(provenance_valid=False))
    record(css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW))

    # horizon_censored -> null (tail-dependent metric, e.g. peak_mgL / default)
    series = two_axis_series([1.0, 1.0], [1.0, 1.0], h=health(horizon_censored=True))
    record(css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW))

    # metric_not_applicable -> null (event-time metric, validated bypass)
    bypass_claim = numeric_claim(metric="t_first_exceedance")
    series = two_axis_series(
        [10.0, 10.0], [10.0, 10.0], event_occurred=False
    )
    record(css.claim_support_state(bypass_claim, series, TREND_TRUE, **CALL_KW))

    # refinement_axis_untested -> null (only spatial ever run)
    only_spatial = [
        run("s0", css.AXIS_SPATIAL, metric_value=1.0, grid_spec=50),
        run("s1", css.AXIS_SPATIAL, metric_value=1.0, grid_spec=20),
    ]
    record(css.claim_support_state(numeric_claim(), only_spatial, TREND_TRUE, **CALL_KW))

    # converged_both_axes -> grid_supported (numeric)
    series = two_axis_series([1.0, 1.0005], [1.0, 1.0005])
    record(css.claim_support_state(numeric_claim(), series, TREND_TRUE, **CALL_KW))

    # no_convergence_trend -> not_supported (numeric, tolerance exceeded, no trend)
    series = two_axis_series([1.0, 2.0], [1.0, 2.0])
    record(css.claim_support_state(numeric_claim(), series, TREND_FALSE, **CALL_KW))

    # metric_over_tolerance_no_decision -> not_supported (numeric, tolerance exceeded, trend present)
    series = two_axis_series([1.0, 2.0], [1.0, 2.0])
    record(css.claim_support_state(numeric_claim(), series, TREND_TRUE, **CALL_KW))

    # method_cannot_answer -> not_supported (whole envelope incapable)
    series = two_axis_series([1.0, 1.0], [1.0, 1.0], method_can_answer=False)
    record(css.claim_support_state(numeric_claim(), series, TREND_TRUE, **CALL_KW))

    # decision_changed_under_refinement -> not_supported (decision claim, flip)
    series = [
        run("s0", css.AXIS_SPATIAL, metric_value=1.0, decision=True, grid_spec=50),
        run("s1", css.AXIS_SPATIAL, metric_value=1.0, decision=False, grid_spec=20),
        run("t0", css.AXIS_TEMPORAL, metric_value=1.0, decision=True, cr_target=0.9),
        run("t1", css.AXIS_TEMPORAL, metric_value=1.0, decision=True, cr_target=0.45),
    ]
    record(css.claim_support_state(decision_claim(), series, TREND_TRUE, **CALL_KW))

    # decision_stable_metric_over_tolerance -> decision_supported_magnitude_sensitive
    series = [
        run("s0", css.AXIS_SPATIAL, metric_value=1.0, decision=True, grid_spec=50),
        run("s1", css.AXIS_SPATIAL, metric_value=2.0, decision=True, grid_spec=20),
        run("t0", css.AXIS_TEMPORAL, metric_value=1.0, decision=True, cr_target=0.9),
        run("t1", css.AXIS_TEMPORAL, metric_value=2.0, decision=True, cr_target=0.45),
    ]
    record(css.claim_support_state(decision_claim(), series, TREND_TRUE, **CALL_KW))

    assert reached_states == css.STATES
    assert reached_reasons == css.REASON_CODES


# ---------------------------------------------------------------------------
# test_null_when_run_health_not_solved_and_provenance_valid
# ---------------------------------------------------------------------------

def test_null_when_run_health_not_solved_and_provenance_valid():
    claim = numeric_claim()

    unsolved_series = two_axis_series([1.0, 1.0], [1.0, 1.0], h=health(solved=False))
    result = css.claim_support_state(claim, unsolved_series, TREND_TRUE, **CALL_KW)
    assert result["state"] is None
    assert result["reason_code"] == css.REASON_RUN_NOT_SOLVED

    invalid_series = two_axis_series([1.0, 1.0], [1.0, 1.0], h=health(provenance_valid=False))
    result = css.claim_support_state(claim, invalid_series, TREND_TRUE, **CALL_KW)
    assert result["state"] is None
    assert result["reason_code"] == css.REASON_PROVENANCE_INVALID

    # Run health precedes discretisation support -- never `not_supported`.
    healthy_but_diverging_decision = [
        run("s0", css.AXIS_SPATIAL, metric_value=1.0, decision=True, grid_spec=50, h=health(solved=False)),
        run("s1", css.AXIS_SPATIAL, metric_value=1.0, decision=False, grid_spec=20),
        run("t0", css.AXIS_TEMPORAL, metric_value=1.0, decision=True, cr_target=0.9),
        run("t1", css.AXIS_TEMPORAL, metric_value=1.0, decision=True, cr_target=0.45),
    ]
    result = css.claim_support_state(decision_claim(), healthy_but_diverging_decision, TREND_TRUE, **CALL_KW)
    assert result["state"] is None
    assert result["reason_code"] == css.REASON_RUN_NOT_SOLVED
    assert result["state"] != css.STATE_NOT_SUPPORTED

    # Both provenance-invalid AND horizon-censored: reason code is singular
    # (provenance, per the 4.1b order) but BOTH facts survive in evidence.
    both_bad = two_axis_series(
        [1.0, 1.0], [1.0, 1.0], h=health(provenance_valid=False, horizon_censored=True)
    )
    result = css.claim_support_state(claim, both_bad, TREND_TRUE, **CALL_KW)
    assert result["reason_code"] == css.REASON_PROVENANCE_INVALID
    for run_id, statuses in result["evidence"]["run_health"].items():
        assert statuses["provenance_valid"] is False
        assert statuses["horizon_censored"] is True


# ---------------------------------------------------------------------------
# test_regulatory_non_assessability_never_maps_to_grid_non_support
# ---------------------------------------------------------------------------

def test_regulatory_non_assessability_never_maps_to_grid_non_support():
    """The regulatory-assessability axis is never consulted by this evaluator
    (T0.3 Section 4.3): there is no field on Claim/RunRecord for it, so a claim whose
    *modelled component* is fully discretisation-supported reaches `grid_supported`
    regardless of any regulatory-scope fact (e.g. a sum-parameter record like PFOA)
    that would live entirely outside this evaluator's input."""
    claim = decision_claim(threshold_record_id="pfoa-sum-record")
    series = [
        run("s0", css.AXIS_SPATIAL, metric_value=1.0, decision=False, grid_spec=50),
        run("s1", css.AXIS_SPATIAL, metric_value=1.0005, decision=False, grid_spec=20),
        run("t0", css.AXIS_TEMPORAL, metric_value=1.0, decision=False, cr_target=0.9),
        run("t1", css.AXIS_TEMPORAL, metric_value=1.0005, decision=False, cr_target=0.45),
    ]
    result = css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW)
    assert result["state"] == css.STATE_GRID_SUPPORTED
    assert result["reason_code"] == css.REASON_CONVERGED_BOTH_AXES
    # No mechanism to have collapsed this into not_supported for a legal-scope reason.
    assert "regulatory" not in css.RunRecord.__dataclass_fields__
    assert "regulatory" not in css.Claim.__dataclass_fields__


# ---------------------------------------------------------------------------
# test_not_yet_evaluated_is_unrepresentable
# ---------------------------------------------------------------------------

def test_not_yet_evaluated_is_unrepresentable():
    assert css.DISPLAY_ONLY_NOT_YET_EVALUATED not in css.STATES
    assert len(css.STATES) == 4  # grid_supported, decision_..., not_supported, null


# ---------------------------------------------------------------------------
# test_middle_state_unreachable_for_numeric_claim
# ---------------------------------------------------------------------------

def test_middle_state_unreachable_for_numeric_claim():
    claim = numeric_claim()
    # Sweep every gate-5-relevant combination a numeric claim can reach and confirm
    # the middle state never appears.
    for spatial, temporal, trend in itertools.product(
        [[1.0, 1.0005], [1.0, 2.0]], [[1.0, 1.0005], [1.0, 2.0]], [TREND_TRUE, TREND_FALSE]
    ):
        series = two_axis_series(spatial, temporal)
        result = css.claim_support_state(claim, series, trend, **CALL_KW)
        assert result["state"] != css.STATE_DECISION_SUPPORTED_MAGNITUDE_SENSITIVE


# ---------------------------------------------------------------------------
# test_malformed_input_raises_typed_contract_error
# ---------------------------------------------------------------------------

def test_malformed_input_raises_typed_contract_error():
    good_series = two_axis_series([1.0, 1.0], [1.0, 1.0])

    with pytest.raises(css.ClaimSupportContractError):
        css.claim_support_state(numeric_claim(), [], TREND_TRUE, **CALL_KW)

    with pytest.raises(css.ClaimSupportContractError):
        css.claim_support_state(
            css.Claim(claim_type=css.CLAIM_TYPE_NUMERIC, metric="peak_mgL", tolerance=None),
            good_series,
            TREND_TRUE,
            **CALL_KW,
        )

    with pytest.raises(css.ClaimSupportContractError):
        css.claim_support_state(
            css.Claim(
                claim_type=css.CLAIM_TYPE_THRESHOLD_DECISION,
                metric="peak_mgL",
                tolerance=0.02,
                threshold_record_id=None,
            ),
            good_series,
            TREND_TRUE,
            **CALL_KW,
        )

    with pytest.raises(css.ClaimSupportContractError):
        css.claim_support_state(
            css.Claim(claim_type="not-a-real-type", metric="peak_mgL", tolerance=0.02),
            good_series,
            TREND_TRUE,
            **CALL_KW,
        )

    # never falls back to null for malformed input
    try:
        css.claim_support_state(numeric_claim(), [], TREND_TRUE, **CALL_KW)
        assert False, "expected ClaimSupportContractError"
    except css.ClaimSupportContractError:
        pass


# ---------------------------------------------------------------------------
# causal / illustrative always null
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "claim_type,expected_reason",
    [
        (css.CLAIM_TYPE_CAUSAL, css.REASON_CAUSAL_CLAIM_OUT_OF_SCOPE),
        (css.CLAIM_TYPE_ILLUSTRATIVE, css.REASON_ILLUSTRATIVE_BY_DESIGN),
    ],
)
def test_causal_and_illustrative_always_null(claim_type, expected_reason):
    claim = css.Claim(claim_type=claim_type, metric="peak_mgL", tolerance=0.02)
    # Even a healthy, fully-converged, both-axes series must still null.
    series = two_axis_series([1.0, 1.0], [1.0, 1.0])
    result = css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW)
    assert result["state"] is None
    assert result["reason_code"] == expected_reason


# ---------------------------------------------------------------------------
# horizon censoring is metric-dependent
# ---------------------------------------------------------------------------

def test_horizon_censoring_metric_dependent_tail_metric_always_nulls():
    claim = numeric_claim(metric="t_peak")
    series = two_axis_series([1.0, 1.0], [1.0, 1.0], h=health(horizon_censored=True))
    result = css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW)
    assert result["state"] is None
    assert result["reason_code"] == css.REASON_HORIZON_CENSORED


def test_horizon_censoring_early_resolved_metric_proceeds_if_event_in_every_run():
    claim = numeric_claim(metric="t_first_exceedance")
    series = two_axis_series(
        [10.0, 10.0], [10.0, 10.0], h=health(horizon_censored=True), event_occurred=True
    )
    result = css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW)
    # Proceeds past the horizon gate to compute -- both axes within tolerance here.
    assert result["state"] == css.STATE_GRID_SUPPORTED
    assert result["reason_code"] == css.REASON_CONVERGED_BOTH_AXES


def test_horizon_censoring_early_resolved_metric_nulls_if_not_seen_in_every_run():
    claim = numeric_claim(metric="t_first_exceedance")
    series = [
        run("s0", css.AXIS_SPATIAL, metric_value=10.0, event_occurred=True, grid_spec=50,
            h=health(horizon_censored=True)),
        run("s1", css.AXIS_SPATIAL, metric_value=10.0, event_occurred=False, grid_spec=20,
            h=health(horizon_censored=True)),
        run("t0", css.AXIS_TEMPORAL, metric_value=10.0, event_occurred=True, cr_target=0.9),
        run("t1", css.AXIS_TEMPORAL, metric_value=10.0, event_occurred=True, cr_target=0.45),
    ]
    result = css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW)
    assert result["state"] is None
    assert result["reason_code"] == css.REASON_HORIZON_CENSORED


# ---------------------------------------------------------------------------
# bypass nulls the metric, never the decision (T0.3 Section 4.3b)
# ---------------------------------------------------------------------------

def test_bypass_nulls_event_time_metric_not_the_decision():
    bypass_series = two_axis_series(
        [0.0, 0.0], [0.0, 0.0], event_occurred=False, decision=False
    )

    timing_claim = numeric_claim(metric="t_first_exceedance")
    timing_result = css.claim_support_state(timing_claim, bypass_series, TREND_TRUE, **CALL_KW)
    assert timing_result["state"] is None
    assert timing_result["reason_code"] == css.REASON_METRIC_NOT_APPLICABLE

    decision_result_claim = decision_claim(metric="peak_mgL")
    decision_result = css.claim_support_state(
        decision_result_claim, bypass_series, TREND_TRUE, **CALL_KW
    )
    # The decision ("not exceeded") is a real, positive, independently-computed result.
    assert decision_result["state"] == css.STATE_GRID_SUPPORTED
    assert decision_result["reason_code"] == css.REASON_CONVERGED_BOTH_AXES


# ---------------------------------------------------------------------------
# decision flip inside tolerance -> not_supported (row order, Section 4.6)
# ---------------------------------------------------------------------------

def test_decision_flip_inside_tolerance_yields_not_supported_row_order():
    series = [
        run("s0", css.AXIS_SPATIAL, metric_value=1.0, decision=True, grid_spec=50),
        # Metric barely moves (well within a 2% tolerance) but the decision flips.
        run("s1", css.AXIS_SPATIAL, metric_value=1.0001, decision=False, grid_spec=20),
        run("t0", css.AXIS_TEMPORAL, metric_value=1.0, decision=True, cr_target=0.9),
        run("t1", css.AXIS_TEMPORAL, metric_value=1.0001, decision=True, cr_target=0.45),
    ]
    result = css.claim_support_state(decision_claim(), series, TREND_TRUE, **CALL_KW)
    assert result["state"] == css.STATE_NOT_SUPPORTED
    assert result["reason_code"] == css.REASON_DECISION_CHANGED_UNDER_REFINEMENT


# ---------------------------------------------------------------------------
# envelope present on every record
# ---------------------------------------------------------------------------

def test_envelope_present_on_every_record():
    cases = []

    claim = css.Claim(claim_type=css.CLAIM_TYPE_CAUSAL, metric="peak_mgL", tolerance=0.02)
    cases.append(css.claim_support_state(claim, [run("r0", css.AXIS_SPATIAL)], TREND_TRUE, **CALL_KW))

    claim = numeric_claim()
    cases.append(
        css.claim_support_state(
            claim, two_axis_series([1.0, 1.0], [1.0, 1.0], h=health(solved=False)), TREND_TRUE, **CALL_KW
        )
    )
    cases.append(
        css.claim_support_state(claim, two_axis_series([1.0, 1.0005], [1.0, 1.0005]), TREND_TRUE, **CALL_KW)
    )

    thr_claim = decision_claim(threshold_record_id="thr-9")
    series = two_axis_series([1.0, 1.0005], [1.0, 1.0005], decision=True)
    cases.append(css.claim_support_state(thr_claim, series, TREND_TRUE, **CALL_KW))

    for result in cases:
        envelope = result["evidence"]["envelope"]
        for key in ("grid_series", "timestep_series", "stopping_rule", "tolerance", "threshold_record_id"):
            assert key in envelope

    # threshold_record_id echoed exactly for the threshold-decision case.
    assert cases[-1]["evidence"]["envelope"]["threshold_record_id"] == "thr-9"


# ---------------------------------------------------------------------------
# untested axis yields refinement_axis_untested, never not_supported
# ---------------------------------------------------------------------------

def test_untested_axis_yields_refinement_axis_untested_never_not_supported():
    claim = numeric_claim()
    only_spatial = [
        run("s0", css.AXIS_SPATIAL, metric_value=1.0, grid_spec=50),
        run("s1", css.AXIS_SPATIAL, metric_value=5.0, grid_spec=20),  # would fail tolerance if reached
    ]
    result = css.claim_support_state(claim, only_spatial, TREND_FALSE, **CALL_KW)
    assert result["state"] is None
    assert result["reason_code"] == css.REASON_REFINEMENT_AXIS_UNTESTED
    assert result["state"] != css.STATE_NOT_SUPPORTED

    only_temporal = [
        run("t0", css.AXIS_TEMPORAL, metric_value=1.0, cr_target=0.9),
        run("t1", css.AXIS_TEMPORAL, metric_value=5.0, cr_target=0.45),
    ]
    result = css.claim_support_state(claim, only_temporal, TREND_FALSE, **CALL_KW)
    assert result["state"] is None
    assert result["reason_code"] == css.REASON_REFINEMENT_AXIS_UNTESTED


# ---------------------------------------------------------------------------
# method_cannot_answer: narrow -- whole envelope, not one bad run
# ---------------------------------------------------------------------------

def test_method_cannot_answer_requires_whole_envelope_incapable():
    claim = numeric_claim()
    # Only ONE run incapable -- not the "any grid in the envelope" (whole-envelope)
    # failure; the claim should proceed to ordinary tolerance/trend evaluation rather
    # than reporting method_cannot_answer.
    series = [
        run("s0", css.AXIS_SPATIAL, metric_value=1.0, grid_spec=50, method_can_answer=False),
        run("s1", css.AXIS_SPATIAL, metric_value=1.0005, grid_spec=20),
        run("t0", css.AXIS_TEMPORAL, metric_value=1.0, cr_target=0.9),
        run("t1", css.AXIS_TEMPORAL, metric_value=1.0005, cr_target=0.45),
    ]
    result = css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW)
    assert result["reason_code"] != css.REASON_METHOD_CANNOT_ANSWER

    all_incapable = two_axis_series([1.0, 1.0005], [1.0, 1.0005], method_can_answer=False)
    result = css.claim_support_state(claim, all_incapable, TREND_TRUE, **CALL_KW)
    assert result["state"] == css.STATE_NOT_SUPPORTED
    assert result["reason_code"] == css.REASON_METHOD_CANNOT_ANSWER


# ---------------------------------------------------------------------------
# no_convergence_trend only fires once tolerance is already exceeded
# ---------------------------------------------------------------------------

def test_no_convergence_trend_only_applies_when_tolerance_already_exceeded():
    claim = numeric_claim()
    # Within tolerance: converged_both_axes regardless of what the trend predicate
    # would have said (predicate is never even consulted).
    series = two_axis_series([1.0, 1.0005], [1.0, 1.0005])

    def boom(_claim, _series):
        raise AssertionError("trend_predicate must not be called when within tolerance")

    result = css.claim_support_state(claim, series, boom, **CALL_KW)
    assert result["state"] == css.STATE_GRID_SUPPORTED
    assert result["reason_code"] == css.REASON_CONVERGED_BOTH_AXES


def test_deterministic_same_inputs_same_output():
    claim = decision_claim()
    series = two_axis_series([1.0, 2.0], [1.0, 2.0], decision=True)
    r1 = css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW)
    r2 = css.claim_support_state(claim, series, TREND_TRUE, **CALL_KW)
    assert r1 == r2


def test_causal_and_illustrative_need_no_metric_or_tolerance():
    """Gate 1 short-circuits them (T0.3 Section 2.1 / Section 4), so demanding a
    metric and tolerance would reject well-formed records -- and the claim
    inventory holds 131 causal claims that legitimately carry neither."""
    for ct, expected_reason in (
        (css.CLAIM_TYPE_CAUSAL, "causal_claim_out_of_scope"),
        (css.CLAIM_TYPE_ILLUSTRATIVE, "illustrative_by_design"),
    ):
        claim = css.Claim(claim_type=ct, metric=None, tolerance=None)
        out = css.claim_support_state(
            claim, [run("r0", css.AXIS_SPATIAL)], TREND_TRUE, **CALL_KW
        )
        assert out["state"] is None, f"{ct} must be null"
        assert out["reason_code"] == expected_reason
