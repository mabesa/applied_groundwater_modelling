# T2 · S14 — the matrix-evaluable components through the frozen evaluator

**2026-09-01.** All 34 `evaluated_by_matrix` components were put to
`t1_claim_support_state.claim_support_state` — the single frozen evaluator (C1 **A14**). No
component was judged by hand.

**21 evaluated. 13 could not be, and no amount of running fixes them.**

---

## 1. The verdicts

| state | reason code | n |
|---|---|---:|
| **`grid_supported`** | `converged_both_axes` | **12** |
| **`decision_supported_magnitude_sensitive`** | `decision_stable_metric_over_tolerance` | **9** |

Not one component came back `not_supported`, and none errored.

**The split is exactly the distinction the track teaches.** The 12 numeric components — `peak_mgL`
and `t_peak` — are converged on both axes. The 9 threshold-decision components ask *"does it exceed
1 mg/L at the well?"*, and the evaluator's own words for them are **decision supported, magnitude
sensitive**: the compliance verdict is stable across every grid tested, while the magnitude is not.

> That is `04t`'s line — *"The decision survives the grid. The number does not."* — reproduced
> independently by the frozen evaluator rather than asserted by the notebook.

## 2. 🔴 A correction this evaluation forced

`S10_S12_SERIES_COMPLETE.md` §1 claimed `peak_mgL` **fails** stopping rule 1, on the reading that
*"two successive refinements"* requires two separate steps below tolerance.

**That was wrong.** `_within_tolerance` implements the rule as the relative change between the
**last two runs on each axis** — one comparison, not two qualifying steps. The +3.948% step at
5 m → 2 m does not disqualify the series; the rule never looks at it. `peak_mgL` is inside
tolerance on both axes, which is why all 12 numeric components return `converged_both_axes`.

The stricter reading was mine, not the contract's. That file is corrected in place.

## 3. The 13 that cannot be evaluated

| metric | n | why |
|---|---:|---|
| `t_first_exceedance` | 7 | needs a `ThresholdRecord`; **`casestudy_threshold_records.yaml` does not exist** — the producer names this as an M0 gap in its own docstring |
| `t_last_exceedance` | 2 | same |
| `capture_halfwidth_m` | 4 | comes from the PRT capture pipeline, not `build_srcpulse_demo`; never wired in |

**Neither is T2 work, and neither is a running problem** — the producer emits `peak_mgL` and
`t_peak` and nothing else, by documented policy. Recorded here as owed, not as an oversight.

⚠️ This is separate from the **63** components already dispositioned `not_evaluated` at S1, which
are not re-judged here.

## 4. What the evaluation ran on

All **12** registered identities carry full artifacts, including the four coarse ones re-run after
the `exp_v1` sizing fix (`S14a`). Every run is uncapped, accepted, and now passes
`cr_meets_target` — the check added after four coarse identities were stamped `passed` while
running at up to `Cr` 3.076 against a 0.9 target.

Two mechanical notes for anyone re-running `t2_evaluate_s14.py`:

- `grid_spec` must be passed to the evaluator as an **opaque hashable** identity — it de-duplicates
  the grid series with `dict.fromkeys`, and the artifact's raw `grid_spec` is a dict.
- `RunRecord` is frozen; the threshold decision must be set at construction, not assigned after.
