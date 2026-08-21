# T1 — definitions the contracts deliberately left open

**Status:** **ADOPTED 2026-08-21.** Proposed by an independent reviewer at the lecturer's delegation,
arithmetic checked before adoption.
**Not contract amendments.** T0.3 and T0.4 each *reference* a quantity without defining it; these fill
those gaps. Neither changes a signed rule, so neither needs a signature — but both are now **operative**,
and changing one later is a decision to record, not a silent edit.

---

## 1. The convergence / stabilisation TREND PREDICATE

**Referenced by:** `T0_3_claim_support_state.md` §4.6. **Used by:** the S12 evaluator.

It runs **only after** the deterministic within-tolerance check has already failed, so the series is known
*not* to be within tolerance. It decides `no_convergence_trend` (→ `not_supported`) versus
`decision_stable_metric_over_tolerance` (→ the middle state).

**Per axis, in the supplied coarse→fine order**, with `rᵢ` the successive relative changes (same
denominator convention the evaluator already uses):

- an axis already **within tolerance is neutral** — it neither passes nor fails;
- fewer than **3 points** → **no trend can be inferred** → `False`;
- **convergence** — `r[-1] < r[0]` **and** a strict majority of successive step comparisons shrink;
- **stabilisation** — the final three points **reverse direction** and their peak-to-peak band is
  **≤ 2 × tolerance**;
- the predicate is `True` only if **every** over-tolerance axis satisfies one of the two.

⚠️ **The 2τ band is not a second tolerance.** It separates a modest limit-cycle from uncontrolled movement;
the claim remains over tolerance either way.

**Why every axis must pass:** a converging spatial series must not be able to conceal an erratic temporal
one.

**Costs when wrong.** A **false positive** hands a threshold claim
`decision_supported_magnitude_sensitive` instead of `not_supported` — more confidence in eventual settling
than the evidence earns; bounded, because it still cannot reach `grid_supported`. A **false negative**
erases the useful distinction between *"the decision survived but the magnitude is sensitive"* and *"the
refinement evidence is directionless"*.

**Evidence it was wrong:** predicate-positive series that subsequently move away, and predicate-negative
series that settle, often enough to change the assigned state.

---

## 2. Operator A's DIAGNOSTIC DISC RADIUS — **25.0 m**

**Referenced by:** T0.4 / `T0_2b…` §6. **Used by:** S6.

$$C_A(t)=\frac{\sum_i C_i(t)\,n_i\,b_i\,|P_i\cap D_{25}|}{\sum_i n_i\,b_i\,|P_i\cap D_{25}|}$$

on **exact cell-polygon ∩ disc** intersections centred on `ABS_XY`. **A centroid-in-disc approximation is
not acceptable.** The artifact label stays exactly `observation_support_robustness`, and the result stays
barred from causal support.

**Why 25 m.** With the locked `α_T = 1 m` over the 90 m spill→extraction path, the transverse screening
scale is `σ_T = √(2·α_T·L) = √180 = 13.4 m`, so a 95% half-width is `1.96σ_T ≈ 26.3 m`. **25 m samples
about the physical transverse plume envelope** without becoming a corridor-scale average. Geometry checks:
65 m clear of the spill, ~175 m from the injection well, covers only 28% of the corridor along-axis, and is
under half the ~53 m PRT capture half-width.

### 2.1 🔴 A is NOT meaningful on the 50 m identity

A 25 m disc has area **1,963 m² = 0.785 of a single nominal 50×50 m cell**, and a diameter of one cell.
Depending on well placement it can sit almost entirely inside the extraction cell and **collapse back into
the single-cell observation it exists to contrast with**.

> **Operator A is compared across 20 / 10 / 5 / 2 m only.** On the 50 m identity it is recorded as
> **support-underresolved / not applicable** — never reported as a robustness result.

Making A valid at 50 m would need a radius near 50 m, comparable to the capture half-width and averaging
nearly half the corridor. **Excluding the coarse point is the more defensible trade.**

⚠️ **Consequence for T2:** operator A's comparison series has **four** points, not five. The A diagnostic
still adds no solves, but it does not span the full spatial series.

**Costs when wrong.** **Too small** → dominated by the extraction cell, disguising the single-cell operator.
**Too large** → the peak is diluted by clean neighbouring pore volume, so an exceedance could vanish because
the *estimand* was averaged, not because the grid effect went away.

**Evidence it was wrong:** on 20/10/5/2 m the exact-intersection value fails the 2% concentration tolerance
for the same imposed physical field, or a 15/20/25/30 m sweep shows 25 m removes the peak or flips the
threshold decision.
