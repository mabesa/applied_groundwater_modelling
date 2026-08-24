"""T1 S11 -- the interpolated metric evaluator, ``exp``-only.

Implements ``DESIGN_DOCS/T1_S11_brief.md`` (v2) / ``DOCUMENTATION/contracts/
T0_2b_metrics_and_causal_rule.md`` Sec 2.2-2.4: parabolic-vertex ``t_peak``
and linear-crossing ``t_first_exceedance`` / ``t_last_exceedance`` /
``exceedance_duration``.

EXPERIMENTAL-ONLY (T0_2b Sec 2.0). This module is NOT wired into the default
call path anywhere:

- ``transport_srcpulse_demo.py``'s ``arrival_day``/``t_peak`` stay the
  un-interpolated lattice ``argmax`` (T0.0 Sec 3.3 pre-authorised alias).
- ``04t_model_implementation.ipynb`` cell 23's ``t_first`` stays the legacy
  ``t[argmax(c > THRESHOLD_mgL)]`` form.
- Nothing in the ``transport_srcpulse_demo`` source closure imports this
  module (``test_t1_src_closure.py`` pins that closure to exactly 7
  members; adding an edge here would break the pin AND put an experimental
  evaluator into the default model's source identity).

Both defaults change only at the JAG, in one atomic commit, per T0_2b Sec
2.0's staging table. Until then this module is a standalone function
library: it takes arrays and a threshold record and returns values. It does
not import, build, or read from any model.

Why interpolation exists at all (T0_2b Sec 1): the qualified reference run's
output-time lattice is PIECEWISE, not uniform -- 30 steps of exactly 1.0 d,
then 92 of 0.97826 d. The concentrations either side of the reference peak
differ by only 0.2%, so a change far smaller than any physical effect can
flip which sample is the argmax and move the reported ``t_peak`` by a full
lattice step (~1 day). Left un-interpolated, a temporal-refinement series
would measure its own re-quantisation and report it as grid sensitivity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Frozen tolerances (T0_2b Sec 2.7)
# ---------------------------------------------------------------------------

#: Relative tolerance for every time-valued metric here. RELATIVE, never an
#: absolute day count -- an absolute ~1 day would exceed the output-lattice
#: step and absorb the very quantisation effect this module exists to
#: remove (T0_2b Sec 2.2).
TOL_TIME_REL = 0.02

#: The tie threshold from T0_2b Sec 2.2: "two samples share the maximum to
#: within 1e-12 relative". This is a FLOATING-POINT EQUALITY rule, not a
#: "flat peak" rule -- it exists to catch two samples that are numerically
#: identical (an exact plateau, or two computations of the same value).
#:
#: It will essentially NEVER fire for the reference peak: its neighbouring
#: samples differ by ~0.2%, eight orders of magnitude above 1e-12. Nothing
#: about this constant protects a caller against a genuinely flat maximum
#: -- that protection, such as it is, comes from the vertex-validity checks
#: (curvature, bracket) applied to whichever single index wins the tie.
TIE_REL_EQ = 1e-12

#: Fallback ABSOLUTE tolerance used only when the relative-closeness
#: reference magnitude is itself ~0, where ``|a-b|/|b|`` is undefined
#: (T0_2b Sec 2.2, "relative comparison near zero must be defined
#: explicitly"). Deliberately the same magnitude as ``TIE_REL_EQ`` -- both
#: exist to catch numerically-identical floats, one relative and one
#: absolute for when relative is undefined.
_ZERO_ABS_TOL = 1e-12

#: Comparison operators a threshold record may carry (T0_2b Sec 2.3: "the
#: comparison operator comes from the threshold record, never hard-coded").
VALID_COMPARISONS = (">", ">=")


# ---------------------------------------------------------------------------
# Public data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThresholdRecord:
    """The minimal threshold record this evaluator needs: an id, the
    concentration value, and the comparison OPERATOR -- read from here,
    never hard-coded (T0_2b Sec 2.3).

    M0's real threshold-record schema
    (``_SUPPORT/src/casestudy_threshold_records.yaml``, referenced by
    ``DESIGN_DOCS/M0_contract_freeze_plan.md`` but not yet built) will
    carry more fields; only these three are needed by
    ``interpolated_exceedance_metrics`` below, so this evaluator does not
    depend on that file existing.
    """

    threshold_record_id: str
    value_mgL: float
    comparison: str  # ">" or ">="

    def __post_init__(self) -> None:
        if self.comparison not in VALID_COMPARISONS:
            raise ValueError(
                f"ThresholdRecord.comparison must be one of {VALID_COMPARISONS!r}, "
                f"got {self.comparison!r}"
            )

    def exceeds(self, c: np.ndarray) -> np.ndarray:
        """Boolean exceedance mask, using THIS record's own operator."""
        if self.comparison == ">":
            return c > self.value_mgL
        return c >= self.value_mgL


@dataclass(frozen=True)
class MetricResult:
    """One metric's interpolated measurement.

    ``value`` is ``None`` exactly when the metric is legitimately
    unavailable (``censored=True``, or a genuine non-exceedance with no
    crossing to report). ``reason`` is a short machine-readable code
    explaining a ``None``/``censored`` result; it is ``None`` when a value
    was produced.
    """

    value: Optional[float]
    units: str
    algorithm_id: str
    interpolated: bool
    censored: bool
    tie_broken: bool
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Shared numeric helpers
# ---------------------------------------------------------------------------


def _rel_close(a: float, b: float, rel_tol: float) -> bool:
    """Relative closeness with an EXPLICIT zero-denominator fallback.

    ``|a-b|/|b|`` is undefined at ``b == 0``. When ``|b|`` (the reference
    magnitude) is below ``_ZERO_ABS_TOL``, fall back to an ABSOLUTE
    comparison against that same tolerance, so a zero-valued (or
    numerically-zero) reference never divides by zero or silently reports
    "not close" via a NaN comparison (T0_2b Sec 2.2).
    """
    if abs(b) < _ZERO_ABS_TOL:
        return abs(a - b) <= _ZERO_ABS_TOL
    return abs(a - b) / abs(b) <= rel_tol


def _validate_series(times: Sequence[float], values: Sequence[float]) -> Tuple[np.ndarray, np.ndarray]:
    """Shared degenerate-input handling for every function in this module.

    Explicit, documented raises -- never a silent NaN/Inf propagating
    through ``argmax`` or a linear-algebra solve, which is "handling" only
    in the sense of not crashing loudly at the point that matters.
    """
    t = np.asarray(times, dtype=float)
    y = np.asarray(values, dtype=float)

    if t.shape != y.shape:
        raise ValueError(
            f"times and values must have the same length/shape, got "
            f"{t.shape} and {y.shape} (mismatched lengths)"
        )
    if t.size == 0:
        raise ValueError("empty series: times/values must contain at least one sample")
    if np.all(np.isnan(y)):
        raise ValueError("all-NaN series: values contains no finite sample at all")
    if np.any(np.isnan(t)) or np.any(np.isinf(t)):
        raise ValueError("non-finite time coordinate(s) in times")
    if np.any(np.isnan(y)) or np.any(np.isinf(y)):
        raise ValueError(
            "partial NaN/Inf in values: rejected explicitly rather than letting a "
            "NaN/Inf sample silently propagate through argmax/interpolation and "
            "produce a nonsense downstream metric"
        )

    dt = np.diff(t)
    if np.any(dt == 0.0):
        raise ValueError("duplicate time coordinate(s) in times: times must be strictly increasing")
    if np.any(dt < 0.0):
        raise ValueError("times are not monotonically increasing (non-monotonic)")

    return t, y


# ---------------------------------------------------------------------------
# t_peak -- parabolic vertex (T0_2b Sec 2.2 / brief Sec 3.1)
# ---------------------------------------------------------------------------

T_PEAK_ALGORITHM_ID = "t_peak_quadratic_vertex_v1"


def _general_quadratic_vertex(
    t0: float, y0: float, t1: float, y1: float, t2: float, y2: float
) -> Optional[Tuple[float, float, float]]:
    """Fit the UNIQUE quadratic ``y = a*t^2 + b*t + c`` through three
    (possibly UNEQUALLY spaced) points on their ACTUAL time coordinates,
    and return ``(a, b, c)``, or ``None`` if the fit is numerically
    degenerate (non-finite coefficients).

    NEVER the equal-spacing shortcut ``t_i + (dt/2)*(y[i-1]-y[i+1]) /
    (y[i-1]-2y[i]+y[i+1])`` -- that formula is valid only when
    ``t1-t0 == t2-t1``. The reference lattice is NOT equally spaced (30
    steps of 1.0 d, then 92 of 0.97826 d), so a triple straddling that
    transition would bias the shortcut (brief Sec 3.1.1). Solving the exact
    3x3 Vandermonde system on the real ``t`` values has no such
    restriction.
    """
    a_mat = np.array(
        [[t0 * t0, t0, 1.0], [t1 * t1, t1, 1.0], [t2 * t2, t2, 1.0]],
        dtype=float,
    )
    y_vec = np.array([y0, y1, y2], dtype=float)
    try:
        a, b, c = np.linalg.solve(a_mat, y_vec)
    except np.linalg.LinAlgError:
        return None
    if not (math.isfinite(a) and math.isfinite(b) and math.isfinite(c)):
        return None
    return float(a), float(b), float(c)


def _bracket_vertex_with_reason(
    t: np.ndarray, y: np.ndarray, idx: int
) -> Tuple[Optional[float], Optional[str]]:
    """The vertex of the quadratic bracketing sample ``idx``, or ``(None,
    reason)`` if any validity check fails (brief Sec 3.1.1, all required):

    - ``idx`` at the first/last sample: no bracketing triple exists at all
      -- CENSORED, never extrapolated.
    - non-finite fit coefficients -- CENSORED.
    - non-negative curvature (``a >= 0``): a convex (or flat/collinear) fit
      is not a maximum -- CENSORED.
    - vertex outside the OPEN neighbour interval ``(t[idx-1], t[idx+1])``:
      extrapolation wearing a fit's clothing -- CENSORED.

    A triple straddling the lattice step-size change is NOT, by itself,
    grounds for censoring -- it is exercised explicitly in the test suite.
    """
    n = t.size
    if idx <= 0 or idx >= n - 1:
        return None, "argmax_at_boundary_no_bracketing_triple"

    t0, t1, t2 = float(t[idx - 1]), float(t[idx]), float(t[idx + 1])
    y0, y1, y2 = float(y[idx - 1]), float(y[idx]), float(y[idx + 1])

    fit = _general_quadratic_vertex(t0, y0, t1, y1, t2, y2)
    if fit is None:
        return None, "nonfinite_quadratic_coefficients"
    a, b, _c = fit
    if not (a < 0.0):
        return None, "convex_or_flat_fit_not_a_peak"

    vertex = -b / (2.0 * a)
    if not (t0 < vertex < t2):
        return None, "vertex_outside_neighbour_interval"

    return float(vertex), None


def interpolated_t_peak(times: Sequence[float], values: Sequence[float]) -> MetricResult:
    """``t_peak`` (T0_2b Sec 2.2): parabolic vertex through the argmax
    sample and its two neighbours, fit on the ACTUAL time coordinates.

    Tie handling (brief Sec 3.1.2): among samples tied to within
    ``TIE_REL_EQ`` relative, the EARLIEST index wins (``tie_broken=True``
    recorded). If the tie set spans more than one index, the vertex
    computed from the earliest-index triple is compared against the vertex
    from the latest-index triple (only when both brackets are interior and
    both fits are valid -- a boundary tie index has no vertex to compare in
    the first place); disagreement beyond ``TOL_TIME_REL`` relative raises,
    per the frozen failure edge.
    """
    t, y = _validate_series(times, values)
    n = t.size

    y_max = float(np.max(y))
    tied = [i for i in range(n) if _rel_close(float(y[i]), y_max, TIE_REL_EQ)]
    tie_broken = len(tied) > 1
    argmax_idx = min(tied)

    if tie_broken:
        earliest_v, _ = _bracket_vertex_with_reason(t, y, min(tied))
        latest_v, _ = _bracket_vertex_with_reason(t, y, max(tied))
        if earliest_v is not None and latest_v is not None:
            if not _rel_close(earliest_v, latest_v, TOL_TIME_REL):
                raise ValueError(
                    "t_peak tie beyond tolerance: the vertex from the "
                    f"earliest-index triple ({earliest_v}) and the vertex from "
                    f"the latest-index triple ({latest_v}) disagree by more than "
                    f"TOL_TIME_REL={TOL_TIME_REL}"
                )

    vertex, reason = _bracket_vertex_with_reason(t, y, argmax_idx)
    if vertex is None:
        return MetricResult(
            value=None, units="d", algorithm_id=T_PEAK_ALGORITHM_ID,
            interpolated=False, censored=True, tie_broken=tie_broken, reason=reason,
        )
    return MetricResult(
        value=vertex, units="d", algorithm_id=T_PEAK_ALGORITHM_ID,
        interpolated=True, censored=False, tie_broken=tie_broken, reason=None,
    )


# ---------------------------------------------------------------------------
# t_first_exceedance / t_last_exceedance / exceedance_duration -- linear
# crossing (T0_2b Sec 2.3-2.4 / brief Sec 3.2-3.3)
# ---------------------------------------------------------------------------

T_FIRST_ALGORITHM_ID = "t_first_exceedance_linear_v1"
T_LAST_ALGORITHM_ID = "t_last_exceedance_linear_v1"
DURATION_ALGORITHM_ID = "exceedance_duration_v1"


def _crossing_time(t0: float, y0: float, t1: float, y1: float, threshold: float) -> float:
    """Linear interpolation of the crossing time between two consecutive
    samples that bracket ``threshold``.

    FIRST-ORDER ONLY (brief Sec 3.2.1): on a realistically curved limb this
    is an approximation, not exact. It is directionally correct (earlier
    than the lattice's un-interpolated answer on a rising limb) and, per
    the refinement check shipped alongside this function
    (``test_curved_limb_crossing_accuracy_and_refinement``), converges
    toward the exact crossing at roughly first order as sample spacing is
    halved. For the reference-lattice spacing (~1 d) against a smooth
    exponential-approach rising limb, the resulting relative error was
    measured to be well within ``TOL_TIME_REL`` (2%); this has NOT been
    verified for every possible curvature, and a caller relying on this for
    a much more sharply curved limb than the reference case should re-run
    that refinement check against their own curve before trusting the 2%
    figure.
    """
    if y1 == y0:
        # A flat bracket has no slope to interpolate along. The lattice-safe
        # fallback is the later sample -- never a division by zero.
        return t1
    frac = (threshold - y0) / (y1 - y0)
    frac = min(max(frac, 0.0), 1.0)
    return t0 + frac * (t1 - t0)


def interpolated_exceedance_metrics(
    times: Sequence[float], values: Sequence[float], threshold: ThresholdRecord
) -> Dict[str, MetricResult]:
    """``t_first_exceedance``, ``t_last_exceedance`` and
    ``exceedance_duration`` (T0_2b Sec 2.3-2.4), all keyed by
    ``threshold.threshold_record_id`` on the caller's side (this function
    returns one triple per call, for the ONE threshold record passed in).

    The exceedance mask uses ``threshold``'s own comparison operator
    (``>`` or ``>=``) -- never hard-coded.

    Non-crossing limbs are distinguished (brief Sec 3.2, the point of the
    rule): never crosses and STILL RISING at the horizon ->
    ``null / horizon_censored``; never crosses and FALLING (or flat) -> a
    REAL not-exceeded result (``censored=False``, ``value=None``).
    "Rising at the horizon" is read off the sign of the last sample-to-
    sample difference (``values[-1] > values[-2]``) -- the last observed
    slope, not a fitted trend.

    Multi-crossing series (brief Sec 3.2.1): ``t_first`` is always the
    FIRST False->True transition; ``t_last`` is always the LAST True->False
    transition. Both are found by scanning for the transition itself, so
    intermediate crossings never displace either endpoint.

    Still above threshold at the horizon (last sample exceeds): both
    ``t_last_exceedance`` and ``exceedance_duration`` are
    ``null / horizon_censored`` -- a duration truncated by the window is
    not a duration (brief Sec 3.3).
    """
    t, y = _validate_series(times, values)
    n = t.size
    exceed = threshold.exceeds(y)

    # --- t_first_exceedance -------------------------------------------------
    first_idx: Optional[int] = None
    for i in range(n):
        if exceed[i] and (i == 0 or not exceed[i - 1]):
            first_idx = i
            break

    if first_idx is None:
        rising = bool(n >= 2 and y[-1] > y[-2])
        if rising:
            first = MetricResult(
                None, "d", T_FIRST_ALGORITHM_ID, False, True, False,
                reason="horizon_censored_still_rising",
            )
        else:
            first = MetricResult(
                None, "d", T_FIRST_ALGORITHM_ID, False, False, False,
                reason="not_exceeded_falling_or_flat",
            )
    elif first_idx == 0:
        # Already exceeding at the very first sample: no "last sample below"
        # exists to interpolate from, so the earliest honest answer is the
        # first sample itself -- not an interpolated value, and not an
        # extrapolation either.
        first = MetricResult(
            float(t[0]), "d", T_FIRST_ALGORITHM_ID, False, False, False,
            reason="already_exceeding_at_first_sample",
        )
    else:
        t_cross = _crossing_time(
            float(t[first_idx - 1]), float(y[first_idx - 1]),
            float(t[first_idx]), float(y[first_idx]), threshold.value_mgL,
        )
        first = MetricResult(t_cross, "d", T_FIRST_ALGORITHM_ID, True, False, False, reason=None)

    # --- t_last_exceedance ---------------------------------------------------
    if bool(exceed[-1]):
        last = MetricResult(
            None, "d", T_LAST_ALGORITHM_ID, False, True, False,
            reason="still_above_at_horizon",
        )
    else:
        last_idx: Optional[int] = None
        for i in range(n - 1, -1, -1):
            if exceed[i] and (i == n - 1 or not exceed[i + 1]):
                last_idx = i
                break
        if last_idx is None:
            # Mirrors t_first: the series never exceeded at all.
            last = MetricResult(
                None, "d", T_LAST_ALGORITHM_ID, False, first.censored, False,
                reason=first.reason,
            )
        else:
            t_cross = _crossing_time(
                float(t[last_idx]), float(y[last_idx]),
                float(t[last_idx + 1]), float(y[last_idx + 1]), threshold.value_mgL,
            )
            last = MetricResult(t_cross, "d", T_LAST_ALGORITHM_ID, True, False, False, reason=None)

    # --- exceedance_duration --------------------------------------------------
    if first.value is not None and last.value is not None:
        duration = MetricResult(
            last.value - first.value, "d", DURATION_ALGORITHM_ID, True, False, False, reason=None,
        )
    else:
        dur_censored = bool(first.censored or last.censored)
        dur_reason = first.reason if first.value is None else last.reason
        duration = MetricResult(
            None, "d", DURATION_ALGORITHM_ID, False, dur_censored, False, reason=dur_reason,
        )

    return {
        "t_first_exceedance": first,
        "t_last_exceedance": last,
        "exceedance_duration": duration,
    }


# ---------------------------------------------------------------------------
# t_first_detection -- deliberately NOT implemented
# ---------------------------------------------------------------------------
#
# T0_2b Sec 2.5: `t_first_detection` is OUT OF SCOPE for the transport
# notebooks. Its scope-out is recorded as PROVISIONAL, with acknowledged
# circular original evidence, pending re-derivation against a word-only
# detector net. Implementing it here would quietly resolve an open contract
# question that is explicitly not this step's to resolve (brief Sec 3.4).
# There is intentionally no `t_first_detection` function, constant, or
# partial stub in this module.
