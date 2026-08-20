# T0.3 — `claim_support_state`

**Milestone:** T0.3 of `transport_notebook_milestones.md` (READY v7).
**Status:** **DRAFT v2 (2026-08-20)** — folded into the single T0 decision record; signed once, at T0 exit.
v2 answers codex review round 1 (**BLOCK**) — `DESIGN_DOCS/codex_reviews/T0/t0_round1_out.md`, findings
5, 6, 7 and 9. All were verified before acceptance.
**Implemented by:** T1's **single** `claim_support_state` evaluator. Prose alone does not discharge this
spec — T4 cannot "transfer the vocabulary" if only prose defines it *(codex r2 #4)*.
**Inherited by:** the case-study **Defensibility** rubric criterion, which **must call this evaluator, not
a parallel one**.

---

## 1. What this vocabulary is, and what it is not

`claim_support_state` answers exactly one question, **about one claim**:

> Given the refinement actually tested, is this claim supported by the discretisation?

- **Per CLAIM, never per model or per run.** The demonstrated case is the reason: the **1 mg/L exceedance
  is stable across every grid tested** while the **peak value is not**. One run, two claims, two states.
- **Discretisation support only.** Refinement establishes **nothing** about parameter, conceptual-model or
  observational support. *"Value supported"* was rejected as too broad and must not reappear.
- **Where a claim is tied to a threshold record, the state is keyed by `threshold_record_id`** — inherited
  from M0 (`M0_contract_freeze_plan.md:63`), because a run can be above one record and below another.
- **Engine verification, mass balance and solubility are DIAGNOSTICS, not states.** They gate run health
  (§4); they never appear in this enum.

🔴 **It is orthogonal to M0's four axes** — but "those describe a run" was **imprecise, and v1 repeated it**
*(codex r1 #7, verified)*. M0's actual cardinalities, which this document inherits and does not re-decide
(`M0_contract_freeze_plan.md:62–72`):

| M0 axis | Cardinality | Consequence here |
|---|---|---|
| **run health** | **independent statuses** — solver · provenance · horizon — per run | §4.1/§4.2; **every status is preserved in evidence**, never collapsed to one word |
| **plume outcome** | **per `threshold_record_id`** | a run can be above one record and below another; the state is evaluated per record |
| **regulatory assessability** | **per `threshold_record_id`** | §4.3 — and never consulted by this evaluator |
| **attribution** | **per metric**, across the four runs | §4.5 — a different quantity that merely shares two English words |

They are never merged, and §4 fixes exactly how they interact.

---

## 2. The three states — frozen

Machine values are the contract; display labels are the lecturer-approved student-facing wording
(`transport_notebook_vision.md:74–90`) and may not drift from them.

| Machine value | Display label | Means |
|---|---|---|
| `grid_supported` | **Grid-supported value** | **spatial *and* temporal** refinement move the metric less than the predeclared tolerance |
| `decision_supported_magnitude_sensitive` | **Decision grid-supported; magnitude grid-sensitive** | the decision holds across the tested refinement envelope; the metric exceeds tolerance |
| `not_supported` | **Not supported by the tested grid/method** | the decision changes, convergence is absent, or the method cannot answer the claim |
| `null` | *(no state; the reason code says why)* | no support statement can honestly be made — see §4 |

**There is no fourth state.** `not_yet_evaluated` is a **display status only** and is
**unrepresentable as a value of this enum** — asserted by test in T1.

### 2.1 State applicability by claim type

Claim types are T0.2's (`numeric` · `threshold-decision` · `causal` · `illustrative`).

| Claim type | `grid_supported` | `decision_supported_magnitude_sensitive` | `not_supported` | `null` |
|---|---|---|---|---|
| `numeric` | ✅ | ❌ — **no decision attached, so the middle state is unreachable** | ✅ | ✅ |
| `threshold-decision` | ✅ | ✅ | ✅ | ✅ |
| `causal` | ❌ | ❌ | ❌ | ✅ **always** — governed by T0.2's causal-support rule, not by this vocabulary |
| `illustrative` | ❌ | ❌ | ❌ | ✅ **always** |

🔴 **A `causal` claim never carries a `claim_support_state`.** Grid support is not the axis a causal claim
lives on; reporting `grid_supported` for one would smuggle in exactly the mechanism attribution this
workstream exists to retire.

---

## 3. Reason codes — frozen, exhaustive

Every state carries a reason code. **Every code below must be reachable**, asserted by test in T1.

| Reason code | Resulting state | Condition |
|---|---|---|
| `converged_both_axes` | `grid_supported` | spatial **and** temporal series both within the T0.2 tolerance |
| `decision_stable_metric_over_tolerance` | `decision_supported_magnitude_sensitive` | the threshold decision is identical across the tested envelope; the metric is not within tolerance |
| `decision_changed_under_refinement` | `not_supported` | the threshold decision flips anywhere in the tested envelope |
| `no_convergence_trend` | `not_supported` | the series neither converges nor stabilises across the tested envelope |
| `metric_over_tolerance_no_decision` | `not_supported` | a `numeric` claim whose metric exceeds tolerance and has no decision to fall back on |
| `method_cannot_answer` | `not_supported` | the method cannot address the claim on any tested grid — e.g. a sub-grid transverse feature never approached in the tested envelope |
| `run_not_solved` | `null` | solver status is not solved |
| `provenance_invalid` | `null` | provenance is invalid |
| `horizon_censored` | `null` | the metric depends on the simulated tail and the run is horizon-censored — see §4.2 |
| `metric_not_applicable` | `null` | the **metric** does not exist for this outcome — **event-time metrics only** (`t_first_exceedance`, `t_first_detection`, `t_peak`) on a validated bypass / non-arrival. 🔴 **Not the decision itself** — see §4.3b |
| `refinement_axis_untested` | `null` | one of the two required axes was never run — see §4.4 |
| `causal_claim_out_of_scope` | `null` | claim type is `causal` |
| `illustrative_by_design` | `null` | claim type is `illustrative` |

**Display-only status, never a value:** `not_yet_evaluated`.

---

## 4. Precedence and nullability against M0's four axes

The evaluator applies these gates **in order; the first match wins** and fixes both state and reason code.

```
1. CLAIM-TYPE GATE
     causal        -> null / causal_claim_out_of_scope
     illustrative  -> null / illustrative_by_design
2. RUN HEALTH  (M0's split statuses; the ORDER below is a T0.3 decision -- see 4.1b)
     solver not solved      -> null / run_not_solved
     provenance invalid     -> null / provenance_invalid
     horizon-censored       -> see 4.2
3. METRIC APPLICABILITY  (plume outcome, keyed by threshold_record_id where applicable)
     metric undefined for this outcome -> null / metric_not_applicable
4. EVIDENCE COMPLETENESS
     either refinement axis untested   -> null / refinement_axis_untested
5. COMPUTE against the T0.2 tolerance -> §4.6's TOTAL TRUTH TABLE (ordered)
```

🔴 **Gate 5 must itself be ordered, and in v1 it was not** *(codex r1 #5, verified)*. v1 handed off to
§§2–3 as an unordered reference, so reachable inputs matched two reason codes at once — a decision that
flips *while* the metric stays within tolerance satisfied both `converged_both_axes` and
`decision_changed_under_refinement`. §4.6 replaces that with a total, mutually exclusive table.

### 4.1 Run health precedes discretisation support

A claim on a run that is not **solved + provenance-valid** is `null`, **never `not_supported`**. A failed
run has produced no evidence about grid support; calling that "not supported" would report an absence of
evidence as evidence of absence.

### 4.1b 🔴 The order `solver → provenance → horizon` is a T0.3 DECISION, not an inheritance

*(codex r1 #7, verified.)* M0 requires *an* explicit run-health precedence; it does **not** freeze this
order. v1 called it inherited, which would have let a future reader treat it as already-approved elsewhere.
**It is decided here**, on the grounds that a run that never solved cannot have valid provenance or a
meaningful horizon, and an invalid-provenance run's horizon is not trustworthy either.

Two obligations follow:
- **Every independent status is preserved in the evidence record**, so a run that is *both* provenance-
  invalid *and* horizon-censored reports both facts; only the *reason code* is singular.
- **Cross-amend M0** when the case-study plan is unparked, so one order governs both — or, if M0 chooses a
  different order, this section changes and the change is a failure edge, not an edit.

### 4.2 Horizon censoring is metric-dependent

`meta["peak_at_last_step"]` (T0.0 §2.3) means the peak sits at the last output step, so the tail is
censored.

- Claims whose metric depends on the tail — **`t_peak`, peak magnitude, exceedance duration / window** —
  are `null` / `horizon_censored`.
- Claims already resolved **before** the horizon — typically **`t_first_exceedance`** and
  **`t_first_detection`** — **remain evaluable**, and the evaluator proceeds to gate 3, **but only under
  the condition below**.

🔴 **The condition, made exact** *(codex r1 #6)*: the event must have occurred before the horizon in
**every run of the refinement series the claim is evaluated over** — not merely in one. An event that has
**not yet been observed on a rising, censored tail** is `null` / `horizon_censored`: it may simply be
about to happen after the horizon, and treating "not seen yet" as "did not happen" would manufacture a
false negative.

Blanket-nulling every claim on a censored run would discard evidence that is genuinely there; blanket-
evaluating them would report a censored maximum as a peak.

### 4.3b 🔴 Bypass nulls the event-time METRIC, never the threshold DECISION

*(codex r1 #6, accepted.)* v1's example risked reading "bypass → `metric_not_applicable`" as nulling
everything about that claim. It does not. **A validated bypass / non-arrival is a real, positive result:
it supports the decision "the threshold was not exceeded"** — and that decision can be perfectly stable
across the tested refinement envelope, which is exactly `grid_supported`.

Only the **event-time metrics** are inapplicable, because there is no event to time. Split the claim:
the *decision* claim is evaluated normally; the *timing* claim is `null` / `metric_not_applicable`.

### 4.3 🔴 Regulatory assessability NEVER maps to grid non-support

The regulatory axis is **never consulted** by this evaluator. It appears nowhere in §4's gate order, by
design.

**Worked case — PFOA.** The EU record regulates a **sum parameter**, so aggregate compliance is
**not assessable** from a single-species model (`casestudy_milestones.md:140`). That is a statement on the
**regulatory** axis. The **modelled-component** claim — *the modelled PFOA contribution and its threshold
comparison* — still gets its `claim_support_state` **computed independently and displayed**. A renderer
that collapses the two produces *"not supported by the tested grid"* for what is really a legal-scope
limitation, and — worse in the other direction — invites *"below threshold, therefore compliant"*, which
M0 explicitly forbids.

### 4.4 Untested is not unsupported

`grid_supported` requires **both** the spatial and the temporal series. If either was never run, the state
is `null` / `refinement_axis_untested` — **never** `not_supported`.

⚠️ Live instance: **arrival-time and exceedance-window stability have not been measured** — only the peak
has. Under this rule they are `null` / `refinement_axis_untested` until T2 measures them, and they display
as `not yet evaluated`. They may **not** be shown as unsupported.

### 4.6 The compute truth table — total and mutually exclusive

Evaluated **top to bottom; the first row that matches wins.** Every reachable input matches exactly one row.

**For a `threshold-decision` claim** *(`threshold_record_id` is mandatory — §5)*:

| # | Condition | State | Reason code |
|---|---|---|---|
| 1 | the method cannot address the claim on **any** grid in the tested envelope | `not_supported` | `method_cannot_answer` |
| 2 | the decision **flips** anywhere in the tested envelope | `not_supported` | `decision_changed_under_refinement` |
| 3 | decision stable **and** both axes within tolerance | `grid_supported` | `converged_both_axes` |
| 4 | decision stable, tolerance exceeded, **and** the series shows no convergence or stabilisation trend | `not_supported` | `no_convergence_trend` |
| 5 | decision stable, tolerance exceeded, trend present | `decision_supported_magnitude_sensitive` | `decision_stable_metric_over_tolerance` |

🔴 Row 2 **precedes** row 3 deliberately: *a decision that flips is not supported, however small the metric
movement was.* A flip inside tolerance means the claim sits on the threshold, which is precisely when a
grid choice changes the answer — the central lesson of this track.

**For a `numeric` claim** (no decision exists, so rows 2 and 5 are unreachable — §2.1):

| # | Condition | State | Reason code |
|---|---|---|---|
| 1 | the method cannot address the claim on **any** grid in the tested envelope | `not_supported` | `method_cannot_answer` |
| 2 | both axes within tolerance | `grid_supported` | `converged_both_axes` |
| 3 | tolerance exceeded, no convergence or stabilisation trend | `not_supported` | `no_convergence_trend` |
| 4 | tolerance exceeded, trend present | `not_supported` | `metric_over_tolerance_no_decision` |

**Scope restrictions that make the codes exclusive** *(codex r1 #5)*:
- `method_cannot_answer` is **first and narrow**: the method cannot answer *on any tested grid* — e.g. a
  sub-grid feature never approached in the envelope. It is **not** a synonym for "did not converge".
- `no_convergence_trend` applies **only** when tolerance is already exceeded; a within-tolerance series is
  `converged_both_axes` regardless of its trend shape.

**Malformed input** — missing series, missing tolerance, missing `threshold_record_id` on a
threshold-decision claim, an unknown claim type — **raises a typed contract error**. The evaluator must
**never invent a state** for input it cannot evaluate, and must never fall back to `null`, which is a
reasoned outcome rather than an error channel.

### 4.7 🔴 "Supported" always means *within the declared tested envelope*

*(codex r1 #6.)* A decision that is stable across the tested envelope may flip **outside** it. The state is
therefore defensible **only** as *supported within the declared tested envelope* — and that is not a
disclaimer in prose, it is a requirement on the output:

**Every emitted record carries the exact envelope it was computed over** — the grid and timestep series,
the **stopping rule**, the **tolerance**, and the **`threshold_record_id`** where applicable. A record
without them is incomplete and does not discharge any exit. **Known in-scope evidence may not be omitted
from the envelope** to make a claim look better supported than it is.

### 4.5 Attribution

M0's `attribution` axis (`supported` · `not_supported` · `mixed` · `not_applicable`) shares two English
words with this enum and is **a different quantity**. Never copy a value across; never render them in one
column without naming both axes.

---

## 5. Evaluator contract *(specifies T1's build; T1 writes the code)*

- **Exactly one implementation.** A second implementation — including in the case-study path — is a defect.
- **Input:** one claim record (type, metric, tolerance reference, `threshold_record_id`) + the refinement
  series it was evaluated over + the run-health statuses of every run in that series.
  🔴 **`threshold_record_id` is MANDATORY for every `threshold-decision` claim** *(codex r1 #6)* — v1 made
  it optional, which would have allowed a compliance decision with no record of *which threshold* it was
  decided against. Its absence is a typed contract error (§4.6), not a `null` state.
- **Output:** `{state, reason_code, evidence}` where `evidence` names the artifact paths and the run ids
  the decision was computed from. **A hand-written state does not discharge any exit** — T2's content-
  handoff table requires the evaluator-emitted value *(codex r2 #4)*.
- **Deterministic**: same inputs → same output, no clock, no environment read.
- **Tolerance values live in T0.2**, not here. T0.3 owns the vocabulary and the gate order; T0.2 owns the
  numbers. Neither restates the other.

### 5.1 T1 test obligations carried over from the milestone exit table

Every state and every reason code reachable · `null` when run health is not solved + provenance-valid ·
**regulatory non-assessability never maps to grid non-support** · `not_yet_evaluated` unrepresentable as a
value · the middle state unreachable for a `numeric` claim · `causal` and `illustrative` always `null` ·
untested axis yields `refinement_axis_untested`, never `not_supported`.

---

## 6. Open items

v1 claimed "none". That was wrong on two counts *(codex r1 #9)*:

1. 🔴 **T0.3 cannot be signed before T0.2.** The compute stage (§4.6) is defined *against* T0.2's
   tolerances, metric algorithms, stopping rules and claim inventory. Until those exist, this document
   specifies a machine with no numbers in it.
2. **§4.1b is a decision, not an inheritance** — the run-health precedence `solver → provenance → horizon`
   is made here and needs the same signature as the rest, plus a cross-amendment to M0 when the case-study
   plan is unparked.

No **new lecturer** decision is introduced: the three states and their wording are already
lecturer-approved, and §4.6 orders them rather than changing them. Signed as part of the single T0 decision
record at T0 exit, **after** T0.2.
