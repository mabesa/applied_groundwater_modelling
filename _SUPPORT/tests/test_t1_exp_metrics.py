"""Tests for `t1_exp_metrics` (T1 S11 -- the interpolated metric evaluator,
`exp`-only).

Implements the exit criteria and named tests of `DESIGN_DOCS/T1_S11_brief.md`
(v2). Two concerns run through this file:

1. The evaluator itself (parabolic `t_peak`, linear-crossing exceedance
   metrics) is EXPERIMENTAL-ONLY -- it must produce correct, well-defined
   values on synthetic series, independent of any model.
2. The evaluator must NOT be reachable from the default path at all. Three
   separate guards cover that: the frozen 7-module `transport_srcpulse_demo`
   source closure (defence in depth alongside `test_t1_src_closure.py`,
   which this file does not edit or duplicate), and a notebook-parsing guard
   over `04t_model_implementation.ipynb` that traces the actual DEPENDENCY
   of the reported `t_first_exceedance` -- not mere textual presence of the
   legacy `>`/`argmax` expression -- and confirms the notebook does not
   import this module.

Run with:  uv run pytest _SUPPORT/tests/test_t1_exp_metrics.py -v
Mark `@pytest.mark.slow` covers the one test that runs a real MF6 solve
(the default-path cold/warm confirmation); everything else is solve-free.
"""
from __future__ import annotations

import ast
import json
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import t1_exp_metrics as tem  # noqa: E402
import transport_srcpulse_demo as tsd  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NOTEBOOK_04T = os.path.join(REPO_ROOT, "PROJECT", "transport", "04t_model_implementation.ipynb")


# ---------------------------------------------------------------------------
# 1. Default path -- confirms this module changed nothing that already
#    exists (T1_S11_brief.md exit criterion 1).
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_default_t_peak_equals_arrival_day_cold_and_warm(tmp_path_factory):
    """The DEFAULT `transport_srcpulse_demo` path is untouched by this
    module's existence: `t_peak` is still exactly `arrival_day` (T0_2b Sec
    2.0's lattice alias), COLD (fresh build) AND WARM (cache hit) -- the
    warm-cache path is where a quietly-wired alias would most likely
    diverge unnoticed, per the brief. Uses the module's own default
    parameters, which are exactly the reference-run parameters (mass_g=3e5,
    pulse_days=30, total_days=120, solubility_mgL=1000 -- the same values
    `04t_model_implementation.ipynb` cell 22 passes)."""
    case_ws = tmp_path_factory.mktemp("t1_exp_metrics_default_path_ws")

    cold = tsd.build_srcpulse_demo(case_ws=case_ws, force=True)
    assert cold.t_peak == cold.arrival_day
    warm = tsd.build_srcpulse_demo(case_ws=case_ws, force=False)
    assert warm.t_peak == warm.arrival_day
    # the warm run is the SAME cached result as the cold one, not a
    # coincidentally-equal fresh solve
    assert warm.arrival_day == cold.arrival_day


# ---------------------------------------------------------------------------
# 2. `t_peak` -- parabolic vertex
# ---------------------------------------------------------------------------


def test_parabolic_vertex_matches_a_hand_computed_parabola():
    """Hand-computed case: y = -(t-5)^2 + 10 sampled at NON-uniform times
    2, 5, 9 -> y = 1, 10, -6. The exact quadratic through these three
    points IS that parabola (a quadratic is uniquely determined by 3
    points), so its vertex is exactly (5.0, 10.0) by construction --
    verifiable by hand without solving anything."""
    times = [2.0, 5.0, 9.0]
    values = [1.0, 10.0, -6.0]
    result = tem.interpolated_t_peak(times, values)
    assert result.censored is False
    assert result.interpolated is True
    assert result.value == pytest.approx(5.0, abs=1e-9)


def test_straddling_triple_across_the_lattice_step_change_is_correct():
    """A triple spanning the reference lattice's 1.0 d -> 0.97826 d step
    change (T0_2b Sec 1): t = 29.0 (dt_left=1.0), 30.0 (argmax),
    30.97826 (dt_right=0.97826), using the actual reference-run
    concentrations either side of the peak (T0_2b Sec 1: "5.2263, 5.2661,
    [5.2770], 5.2578, 5.2092"). The general fit's vertex is verified
    against an INDEPENDENT numerical path (`numpy.polyfit`, a different
    algorithm from the module's direct 3x3 solve) and must land strictly
    inside the neighbour interval."""
    t0, t1, t2 = 29.0, 30.0, 30.0 + 0.97826
    y0, y1, y2 = 5.2661, 5.2770, 5.2578

    result = tem.interpolated_t_peak([t0, t1, t2], [y0, y1, y2])
    assert result.censored is False
    assert result.interpolated is True

    a, b, _c = np.polyfit([t0, t1, t2], [y0, y1, y2], 2)
    independent_vertex = -b / (2.0 * a)
    assert result.value == pytest.approx(independent_vertex, abs=1e-6)
    assert t0 < result.value < t2


def test_equal_spacing_shortcut_would_disagree_on_a_straddling_triple():
    """Pins WHY the general fit is required (brief Sec 3.1.1): the textbook
    equal-spacing three-point formula, applied with the "reach for" choice
    of dt = t[i]-t[i-1] (the left spacing), disagrees with the general fit
    on the same straddling triple used above -- by far more than floating-
    point noise. This function is intentionally NOT part of the production
    module: it exists here only to demonstrate the bias the frozen
    algorithm avoids, and must never be called from `t1_exp_metrics.py`."""
    t0, t1, t2 = 29.0, 30.0, 30.0 + 0.97826
    y0, y1, y2 = 5.2661, 5.2770, 5.2578

    general = tem.interpolated_t_peak([t0, t1, t2], [y0, y1, y2])
    assert general.value is not None

    dt = t1 - t0
    denom = y0 - 2.0 * y1 + y2
    naive_shortcut_vertex = t1 + (dt / 2.0) * (y0 - y2) / denom

    disagreement = abs(general.value - naive_shortcut_vertex)
    assert disagreement > 1e-4, (
        "the equal-spacing shortcut should visibly disagree with the general "
        f"fit on a straddling triple, got only {disagreement} days apart"
    )


def test_argmax_at_first_sample_is_censored():
    times = [0.0, 1.0, 2.0]
    values = [5.0, 3.0, 1.0]  # argmax is index 0
    result = tem.interpolated_t_peak(times, values)
    assert result.censored is True
    assert result.value is None
    assert result.interpolated is False
    assert result.reason == "argmax_at_boundary_no_bracketing_triple"


def test_argmax_at_last_sample_is_censored():
    times = [0.0, 1.0, 2.0]
    values = [1.0, 3.0, 5.0]  # argmax is the last index
    result = tem.interpolated_t_peak(times, values)
    assert result.censored is True
    assert result.value is None
    assert result.reason == "argmax_at_boundary_no_bracketing_triple"


def test_convex_fit_is_censored():
    """Direct unit test of the curvature validity check: a monotonically
    decreasing triple fits a CONVEX (upward-opening) parabola -- `a > 0` --
    which by construction is not a maximum. (A quadratic through a genuine
    two-sided strict local max is always concave, algebraically -- this
    exercises the guard directly, independent of any argmax-selection
    path, including the flat/collinear `a == 0` edge via the module's
    lower-level helper.)"""
    t = np.array([0.0, 1.0, 2.0])
    y_convex = np.array([2.0, 1.0, 0.9])
    vertex, reason = tem._bracket_vertex_with_reason(t, y_convex, 1)
    assert vertex is None
    assert reason == "convex_or_flat_fit_not_a_peak"

    y_collinear = np.array([1.0, 2.0, 3.0])  # a == 0, flat, not negative
    vertex2, reason2 = tem._bracket_vertex_with_reason(t, y_collinear, 1)
    assert vertex2 is None
    assert reason2 == "convex_or_flat_fit_not_a_peak"


def test_vertex_outside_the_bracket_is_censored():
    """A concave (`a < 0`, valid curvature) fit whose vertex nonetheless
    falls OUTSIDE the open neighbour interval `(t0, t2)` -- extrapolation
    wearing a fit's clothing. This arises when the "peak" sample is not a
    genuine two-sided strict local maximum (here: monotonically increasing,
    concave, so the true extremum of the fitted curve lies beyond the last
    sample)."""
    t = np.array([0.0, 1.0, 2.0])
    y = np.array([1.0, 1.2, 1.3])
    a, b, _c = tem._general_quadratic_vertex(t[0], y[0], t[1], y[1], t[2], y[2])
    assert a < 0.0  # curvature check would pass on its own
    vertex, reason = tem._bracket_vertex_with_reason(t, y, 1)
    assert vertex is None
    assert reason == "vertex_outside_neighbour_interval"


def test_nonfinite_coefficients_are_censored():
    """A singular (duplicate-time) triple makes the 3x3 Vandermonde system
    unsolvable -- caught explicitly, censored, never propagated as NaN/Inf
    coefficients."""
    fit = tem._general_quadratic_vertex(1.0, 5.0, 1.0, 5.0, 2.0, 3.0)
    assert fit is None

    t = np.array([0.0, 1.0, 1.0])
    y = np.array([1.0, 5.0, 5.0])
    vertex, reason = tem._bracket_vertex_with_reason(t, y, 1)
    assert vertex is None
    assert reason == "nonfinite_quadratic_coefficients"


def test_tie_takes_the_earlier_index_and_records_tie_broken():
    """A symmetric plateau (y = [1, 5, 5, 1]): both interior samples tie the
    max exactly. The earlier index (1) wins, `tie_broken=True`, and -- by
    the plateau's symmetry -- the earliest- and latest-index vertices agree
    well within tolerance, so this must NOT raise."""
    times = [0.0, 1.0, 2.0, 3.0]
    values = [1.0, 5.0, 5.0, 1.0]
    result = tem.interpolated_t_peak(times, values)
    assert result.tie_broken is True
    assert result.censored is False
    # earlier-index bracket (0,1,2) -- by symmetry, vertex = 1.5
    assert result.value == pytest.approx(1.5, abs=1e-9)


def test_tie_beyond_tolerance_raises():
    """An ASYMMETRIC tie: indices 1 and 3 both hit the exact max (5.0), but
    their respective bracketing triples fit very different local curves
    (bracket around idx1: (0,1),(1,5),(2,2); bracket around idx3:
    (2,2),(3,5),(4,1)), so the earliest-index vertex (~1.07 d) and the
    latest-index vertex (~2.93 d) disagree by far more than
    `TOL_TIME_REL` (2%) -- the frozen failure edge (brief Sec 3.1.2)."""
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    values = [1.0, 5.0, 2.0, 5.0, 1.0]
    with pytest.raises(ValueError, match="tie beyond tolerance"):
        tem.interpolated_t_peak(times, values)


# ---------------------------------------------------------------------------
# 3. `t_first_exceedance` / `t_last_exceedance` / `exceedance_duration`
# ---------------------------------------------------------------------------


def test_linear_crossing_matches_hand_computed_and_is_earlier_than_the_lattice():
    """Hand-computed case: times=[0,1,2,3], values=[0,0.5,1.5,2.5],
    threshold=1.0. First exceedance is between t=1 (0.5) and t=2 (1.5):
    frac = (1.0-0.5)/(1.5-0.5) = 0.5 -> t_cross = 1.5, hand-verifiable.
    Today's un-interpolated lattice answer would be `t[argmax(c>1.0)]` =
    t[2] = 2.0 -- the interpolated answer must be strictly EARLIER."""
    times = [0.0, 1.0, 2.0, 3.0]
    values = [0.0, 0.5, 1.5, 2.5]
    record = tem.ThresholdRecord("thr_hand", 1.0, ">")
    result = tem.interpolated_exceedance_metrics(times, values, record)["t_first_exceedance"]
    assert result.value == pytest.approx(1.5, abs=1e-9)

    legacy_lattice_answer = float(np.asarray(times)[np.argmax(np.asarray(values) > 1.0)])
    assert legacy_lattice_answer == 2.0
    assert result.value < legacy_lattice_answer


def test_comparison_operator_comes_from_the_record_gt_and_ge_differ_at_the_boundary():
    """A sample sits EXACTLY at the threshold (idx 1 and 2 both = 1.0,
    threshold = 1.0). Under strict `>` neither counts as exceeding, and the
    series never exceeds at all (falling by the horizon) -> a real
    not-exceeded result. Under `>=` the very first sample at the threshold
    counts immediately -> `t_first_exceedance = 1.0`, no interpolation
    needed (already at/over on first qualifying sample). The two operators
    must resolve differently, and the operator must come from the record,
    never be hard-coded."""
    times = [0.0, 1.0, 2.0, 3.0]
    values = [0.0, 1.0, 1.0, 0.5]

    gt_record = tem.ThresholdRecord("thr_gt", 1.0, ">")
    gt_result = tem.interpolated_exceedance_metrics(times, values, gt_record)["t_first_exceedance"]
    assert gt_result.value is None
    assert gt_result.censored is False
    assert gt_result.reason == "not_exceeded_falling_or_flat"

    ge_record = tem.ThresholdRecord("thr_ge", 1.0, ">=")
    ge_result = tem.interpolated_exceedance_metrics(times, values, ge_record)["t_first_exceedance"]
    assert ge_result.value == pytest.approx(1.0, abs=1e-9)

    assert gt_result.value != ge_result.value


def test_never_crosses_still_rising_is_horizon_censored():
    times = [0.0, 1.0, 2.0]
    values = [0.1, 0.3, 0.6]  # below threshold=1.0 throughout, still rising
    record = tem.ThresholdRecord("thr_rising", 1.0, ">")
    metrics = tem.interpolated_exceedance_metrics(times, values, record)
    assert metrics["t_first_exceedance"].value is None
    assert metrics["t_first_exceedance"].censored is True
    assert metrics["t_first_exceedance"].reason == "horizon_censored_still_rising"


def test_never_crosses_falling_is_a_real_not_exceeded():
    times = [0.0, 1.0, 2.0]
    values = [0.6, 0.4, 0.1]  # below threshold=1.0 throughout, falling
    record = tem.ThresholdRecord("thr_falling", 1.0, ">")
    metrics = tem.interpolated_exceedance_metrics(times, values, record)
    result = metrics["t_first_exceedance"]
    assert result.value is None
    # the defining distinction (brief Sec 3.2): NOT censored -- a real result
    assert result.censored is False
    assert result.reason == "not_exceeded_falling_or_flat"


def test_still_above_at_horizon_nulls_last_and_duration():
    times = [0.0, 1.0, 2.0]
    values = [0.5, 1.5, 2.5]  # crosses once, still above at the horizon
    record = tem.ThresholdRecord("thr_horizon", 1.0, ">")
    metrics = tem.interpolated_exceedance_metrics(times, values, record)

    assert metrics["t_first_exceedance"].value == pytest.approx(0.5, abs=1e-9)
    assert metrics["t_last_exceedance"].value is None
    assert metrics["t_last_exceedance"].censored is True
    assert metrics["t_last_exceedance"].reason == "still_above_at_horizon"
    assert metrics["exceedance_duration"].value is None
    assert metrics["exceedance_duration"].censored is True


def test_multi_crossing_returns_first_and_last_correctly():
    """A curve that crosses, falls back, crosses again, and falls back a
    final time within the window. `t_first` must be the FIRST up-crossing
    and `t_last` the LAST down-crossing -- invisible in a single-crossing
    test (brief Sec 3.2.1)."""
    times = [0, 1, 2, 3, 4, 5, 6, 7]
    values = [0.0, 0.5, 1.5, 0.8, 0.3, 1.6, 2.0, 0.2]
    record = tem.ThresholdRecord("thr_multi", 1.0, ">")
    metrics = tem.interpolated_exceedance_metrics(times, values, record)

    # first up-crossing: between t=1 (0.5) and t=2 (1.5)
    assert metrics["t_first_exceedance"].value == pytest.approx(1.5, abs=1e-9)
    # last down-crossing: between t=6 (2.0) and t=7 (0.2), NOT the earlier
    # down-crossing between t=2 (1.5) and t=3 (0.8)
    expected_last = 6.0 + (1.0 - 2.0) / (0.2 - 2.0) * (7.0 - 6.0)
    assert metrics["t_last_exceedance"].value == pytest.approx(expected_last, abs=1e-9)
    assert metrics["t_last_exceedance"].value > 6.0


def test_curved_limb_crossing_accuracy_and_refinement():
    """Linear crossing is FIRST-ORDER (brief Sec 3.2.1) -- ship an analytic
    curved case with a KNOWN exact crossing and a refinement check.

    c(t) = Cmax * (1 - exp(-t/tau)), an exponential-approach rise. The
    exact crossing time for c(t*) = threshold is
    t* = -tau * ln(1 - threshold/Cmax), solvable in closed form.

    At the two coarser spacings (h=2.0 d, h=1.0 d -- comparable to the
    reference lattice's ~1 d step), halving the spacing must move the
    linear-crossing estimate CLOSER to the exact value, roughly by a
    factor of ~2 (first order), and the h=1.0 d relative error must sit
    well within `TOL_TIME_REL` (2%) -- both empirically confirmed here for
    this representative curvature, per the brief's requirement to show
    adequacy rather than assert it."""
    cmax, tau, threshold = 5.0, 15.0, 3.0
    t_exact = -tau * math.log(1.0 - threshold / cmax)
    record = tem.ThresholdRecord("thr_curved", threshold, ">")

    def _estimate(h: float) -> float:
        times = np.arange(0.0, 60.0 + h, h)
        values = cmax * (1.0 - np.exp(-times / tau))
        result = tem.interpolated_exceedance_metrics(times, values, record)["t_first_exceedance"]
        assert result.value is not None
        return result.value

    err_h2 = abs(_estimate(2.0) - t_exact)
    err_h1 = abs(_estimate(1.0) - t_exact)
    err_h_half = abs(_estimate(0.5) - t_exact)

    # error must decrease as spacing is halved (both refinement steps)
    assert err_h1 < err_h2
    assert err_h_half < err_h1

    # roughly first order: halving spacing should roughly halve the error,
    # loosely bounded (not exactly 2x, but nowhere near flat or divergent)
    ratio_1 = err_h2 / err_h1
    ratio_2 = err_h1 / err_h_half
    assert 1.3 < ratio_1 < 6.0
    assert 1.3 < ratio_2 < 6.0

    # at the reference-lattice-comparable spacing (h=1.0 d), the relative
    # error is well within TOL_TIME_REL for THIS curvature -- stated as a
    # measured fact for this case, not asserted as a general guarantee (see
    # `_crossing_time`'s docstring for the caveat on sharper curvature)
    assert (err_h1 / t_exact) < tem.TOL_TIME_REL


# ---------------------------------------------------------------------------
# 4. `t_first_detection` -- scope-out
# ---------------------------------------------------------------------------


def test_t_first_detection_is_not_implemented():
    """T0_2b Sec 2.5 / brief Sec 3.4: OUT OF SCOPE, PROVISIONAL scope-out.
    There must be no callable, constant, or partial stub for it in this
    module."""
    assert not hasattr(tem, "t_first_detection")
    assert not hasattr(tem, "interpolated_t_first_detection")
    module_names = {name.lower() for name in dir(tem)}
    assert not any("detection" in name for name in module_names)


# ---------------------------------------------------------------------------
# 5. Degenerate inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("times,values", [
    ([], []),                                    # empty
    ([0.0, 1.0, 2.0], [float("nan")] * 3),       # all-NaN
    ([2.0, 1.0, 0.0], [1.0, 2.0, 3.0]),          # non-monotonic (decreasing)
    ([0.0, 1.0], [1.0, 2.0, 3.0]),               # mismatched lengths
])
def test_degenerate_inputs_raise(times, values):
    with pytest.raises(ValueError):
        tem.interpolated_t_peak(times, values)
    record = tem.ThresholdRecord("thr_degenerate", 1.0, ">")
    with pytest.raises(ValueError):
        tem.interpolated_exceedance_metrics(times, values, record)


def test_duplicate_times_raise():
    times = [0.0, 1.0, 1.0, 2.0]
    values = [1.0, 2.0, 2.5, 3.0]
    with pytest.raises(ValueError, match="duplicate"):
        tem.interpolated_t_peak(times, values)
    record = tem.ThresholdRecord("thr_dup", 1.0, ">")
    with pytest.raises(ValueError, match="duplicate"):
        tem.interpolated_exceedance_metrics(times, values, record)


def test_partial_nan_handled_explicitly():
    """A single NaN (or Inf) among otherwise-finite values is rejected with
    a clear, explicit error -- never silently propagated through
    `argmax`/interpolation, where NaN comparisons behave unpredictably."""
    times = [0.0, 1.0, 2.0, 3.0]
    values = [1.0, float("nan"), 3.0, 2.0]
    with pytest.raises(ValueError, match="NaN/Inf"):
        tem.interpolated_t_peak(times, values)

    values_inf = [1.0, float("inf"), 3.0, 2.0]
    with pytest.raises(ValueError, match="NaN/Inf"):
        tem.interpolated_t_peak(times, values_inf)


def test_zero_valued_tie_is_defined():
    """The relative-tie comparison must be explicitly defined at/near zero,
    where `|a-b|/|b|` is undefined (division by zero) -- T0_2b Sec 2.2.
    `_rel_close` falls back to an absolute comparison rather than raising
    or returning a NaN-derived answer."""
    assert tem._rel_close(0.0, 0.0, tem.TIE_REL_EQ) is True
    assert tem._rel_close(1e-15, 0.0, tem.TIE_REL_EQ) is True
    assert tem._rel_close(0.5, 0.0, tem.TIE_REL_EQ) is False
    # and the full pipeline doesn't choke on an all-zero series either
    result = tem.interpolated_t_peak([0.0, 1.0, 2.0], [0.0, 0.0, 0.0])
    assert result.tie_broken is True
    assert result.censored is True  # earliest tied index (0) is a boundary


# ---------------------------------------------------------------------------
# 6. Not on the default path
# ---------------------------------------------------------------------------


def test_no_default_path_module_imports_the_evaluator():
    """`transport_srcpulse_demo`'s own transitive source closure (the same
    closure `test_t1_src_closure.py` pins to exactly 7 members) must not
    contain this module, and the module's source text must not reference
    it either -- defence in depth alongside the closure test, which this
    file does not edit."""
    closure = tsd._resolve_src_closure(tsd.__file__)
    assert "t1_exp_metrics" not in closure
    assert len(closure) == 7

    demo_src_path = tsd.__file__
    with open(demo_src_path, "r", encoding="utf-8") as f:
        demo_source = f.read()
    assert "t1_exp_metrics" not in demo_source


# ---------------------------------------------------------------------------
# 7. The `04t` notebook guard -- Sec 2.1 / exit criteria 2, 18
# ---------------------------------------------------------------------------
#
# The guard PARSES the notebook and traces the actual DEPENDENCY of the
# assignment reporting `t_first_exceedance` (`t_first` in cell 23), rather
# than checking mere textual presence of the legacy `>`/`argmax` snippet
# somewhere in the file -- a hash of the whole cell would fire on unrelated
# edits, and presence alone could pass while the legacy expression sat dead
# beside a differently-sourced reported value (brief Sec 2.1).


def _load_notebook_code_cell_sources(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    sources = []
    for cell in nb["cells"]:
        if cell.get("cell_type") != "code":
            continue
        sources.append("".join(cell.get("source", [])))
    return sources


def _strip_jupyter_magics(src: str) -> str:
    """Blank out Jupyter line-magics/shell-escapes (`%...`, `!...`) that
    `ast.parse` cannot handle, so the surrounding real Python still parses."""
    lines = src.splitlines()
    cleaned = ["" if line.lstrip().startswith(("%", "!")) else line for line in lines]
    return "\n".join(cleaned)


def _find_last_assignment_across_cells(sources, name: str):
    """The LAST assignment to `name` anywhere across all code cells, in
    notebook order -- a later cell/assignment shadows an earlier one, so
    "some assignment somewhere" is not enough; it must be the one that
    actually determines the reported value."""
    found = None
    for src in sources:
        try:
            tree = ast.parse(_strip_jupyter_magics(src))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == name:
                        found = node
    return found


def _uses_strict_gt(node) -> bool:
    """True iff `node`'s value expression contains a `Compare` with a
    strict `Gt` operator and NOT a `GtE` -- an explicit `>=` anywhere means
    the operator has been changed."""
    saw_gt = False
    for sub in ast.walk(node.value):
        if isinstance(sub, ast.Compare):
            if any(isinstance(op, ast.GtE) for op in sub.ops):
                return False
            if any(isinstance(op, ast.Gt) for op in sub.ops):
                saw_gt = True
    return saw_gt


def _references_name(node, name: str) -> bool:
    return any(isinstance(sub, ast.Name) and sub.id == name for sub in ast.walk(node.value))


def _calls_argmax(node) -> bool:
    for sub in ast.walk(node.value):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Attribute) and f.attr == "argmax":
                return True
            if isinstance(f, ast.Name) and f.id == "argmax":
                return True
    return False


def _t_first_exceedance_is_legacy_and_dependent(sources) -> bool:
    """The DEPENDENCY check: `t_first` must be built FROM the `exceed` mask
    (referenced by name, inside an `np.argmax` call), and `exceed` itself
    must be built from a strict `>` comparison -- not merely have both
    substrings present somewhere in the cell."""
    exceed_node = _find_last_assignment_across_cells(sources, "exceed")
    t_first_node = _find_last_assignment_across_cells(sources, "t_first")
    if exceed_node is None or t_first_node is None:
        return False
    if not _uses_strict_gt(exceed_node):
        return False
    if not _references_name(t_first_node, "exceed"):
        return False
    if not _calls_argmax(t_first_node):
        return False
    return True


def test_04t_notebook_still_uses_the_legacy_uninterpolated_threshold():
    sources = _load_notebook_code_cell_sources(NOTEBOOK_04T)
    assert _t_first_exceedance_is_legacy_and_dependent(sources), (
        "04t_model_implementation.ipynb no longer reports t_first_exceedance "
        "via the legacy strict-> / lattice-argmax dependency chain -- this is "
        "required until the JAG (T0_2b Sec 2.0/2.1)"
    )


def test_04t_guard_checks_the_dependency_not_just_presence():
    """Proves the guard traces dependency, not presence: leaving the legacy
    `exceed = c > THRESHOLD_mgL` line in place as DEAD code while `t_first`
    is actually computed from something else must FAIL the guard -- a
    presence-only check (both substrings appear somewhere) would wrongly
    pass this."""
    dead_code_source = (
        "exceed = c > THRESHOLD_mgL\n"                      # present, but unused below
        "t_first = interpolated_crossing(t, c, THRESHOLD_mgL)\n"  # NOT from exceed/argmax
    )
    assert not _t_first_exceedance_is_legacy_and_dependent([dead_code_source])

    # sanity: the real cell-23 form (reproduced verbatim) passes
    real_source = (
        "exceed = c > THRESHOLD_mgL\n"
        "t_first = float(t[np.argmax(exceed)]) if exceed.any() else None\n"
    )
    assert _t_first_exceedance_is_legacy_and_dependent([real_source])

    # an operator swap (>= for >) must also be caught, even though the
    # dependency chain itself is otherwise intact
    ge_source = (
        "exceed = c >= THRESHOLD_mgL\n"
        "t_first = float(t[np.argmax(exceed)]) if exceed.any() else None\n"
    )
    assert not _t_first_exceedance_is_legacy_and_dependent([ge_source])


def test_04t_notebook_does_not_import_the_exp_evaluator():
    with open(NOTEBOOK_04T, "r", encoding="utf-8") as f:
        raw_text = f.read()
    assert "t1_exp_metrics" not in raw_text

    for src in _load_notebook_code_cell_sources(NOTEBOOK_04T):
        try:
            tree = ast.parse(_strip_jupyter_magics(src))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] == "t1_exp_metrics" for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module != "t1_exp_metrics"
