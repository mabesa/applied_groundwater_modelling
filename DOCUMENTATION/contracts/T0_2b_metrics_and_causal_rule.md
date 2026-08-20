# T0.2b — Metric algorithms, sequences, tolerances and the causal-support rule

**Milestone:** T0.2 of `transport_notebook_milestones.md` (READY v7).
**Status:** **DRAFT v2 (2026-08-20)** — §2.7 tolerances accepted by the lecturer — signs as part of the single T0 decision record.
**Companion:** `T0_3_claim_support_state.md` owns the vocabulary and the gate order; **this document owns
the numbers**. Neither restates the other.
**Depends on:** `T0_2a_claim_inventory.json` (the enumerated claim set).

> **Why every rule here is frozen BEFORE T2 runs.** A tolerance chosen after seeing a result is not a
> tolerance, it is a conclusion. Changing anything in this document after T2 has run is a **failure edge to
> T0**, never an in-flight edit.

---

## 1. 🔴 The quantisation defect — read this before any metric definition

**Measured on the qualified reference run** (`b685f24`, T0.0 §5.1 evidence):

- The output-time lattice is **piecewise, not uniform**: **30 steps of exactly 1.0 d** (the pulse period)
  followed by **92 steps of 0.97826 d** (the migration period). `meta["dt"] = 0.9836` is an average and
  **does not describe the lattice**.
- `t_peak` is computed as `times[argmax(bt)]` (`transport_srcpulse_demo.py:732`) — **no interpolation**.
- `t_first_exceedance` is computed as `t[argmax(c > THRESHOLD)]` (`04t_model_implementation.ipynb` cell 23)
  — **no interpolation**, and strict `>`.

**Therefore both timing metrics can only ever take values on the output lattice**, and the lattice itself
changes with `nstp` — which is precisely the axis T2's temporal-convergence series varies.

**The concentrations either side of the reference peak are `5.2263, 5.2661, [5.2770], 5.2578, 5.2092`.** The
top is nearly flat: neighbouring samples differ by **0.2%**. A change far smaller than any physical effect
can therefore flip which sample is the argmax and move the *reported* `t_peak` by a **full lattice step
(~1 day)** while the true peak moved by a fraction of that.

🔴 **Consequence: without an interpolation rule, T2's temporal series would measure its own re-quantisation
and report it as grid sensitivity.** Every arrival/timing claim would be evaluated against an artefact.
This is why §2 freezes interpolation for every time-valued metric.

---

## 2. Metric algorithms — frozen

Each metric is defined by: **quantity · units · algorithm · tie-break · censoring · tolerance.**
Where the frozen algorithm differs from what the code does today, the change is listed as a **T1
implementation obligation** — it is a metric definition, not a licence to edit T1 sources before T0.0 §7 is
signed.

### 2.1 `peak_mgL` — peak receptor concentration
- **Units** mg/L. **Algorithm** `max(breakthrough)` over the simulated window. Unchanged from today.
- **Censoring** if `meta["peak_at_last_step"]` is true, the value is a **censored maximum, not a peak**;
  the claim is `null / horizon_censored` (T0.3 §4.2).
- **Tolerance** `TOL_CONC_REL = 2%` relative.

### 2.2 `t_peak` — time of peak *(renamed from `arrival_day`)*
- **Units** days. **Naming** `t_peak`, per M0 (`M0_contract_freeze_plan.md:75`); `arrival_day` survives as a
  deprecated alias until the JAG, pre-authorised in `T0_0_canonical_contract.md` §3.3.
- 🔴 **Algorithm — FROZEN WITH INTERPOLATION.** Fit a **parabola through the argmax sample and its two
  neighbours** and report the vertex. This removes the lattice quantisation of §1. Where the argmax is the
  first or last sample there is no bracketing triple → the value is **censored**, not extrapolated.
- **Tie-break** if two samples share the maximum to within `1e-12` relative, take the **earlier** index and
  record `tie_broken = true` in the evidence. A tie that changes the reported value by more than
  `TOL_TIME_REL` is a **failure edge**, not a silent choice.
- **T1 obligation** today's `times[argmax(bt)]` (`:732`) is the un-interpolated form and must be replaced.
- **Tolerance** `TOL_TIME_REL = 2%` relative. ⚠️ **Not an absolute day count** — an absolute tolerance of
  ~1 day would be larger than the lattice step and would absorb the very effect being measured.

### 2.3 `t_first_exceedance` — first threshold crossing
- **Units** days. **Per `threshold_record_id`** (M0 cardinality; T0.3 §1).
- 🔴 **Algorithm — FROZEN WITH INTERPOLATION.** **Linear interpolation between the last sample below and
  the first sample at-or-above** the threshold value. Today's `t[argmax(c > THRESHOLD)]` reports the first
  lattice point after the crossing and is systematically **late by up to one step**.
- **Comparison operator** taken from the **threshold record**, never hard-coded — M0's record carries it
  explicitly. Today's strict `>` silently decides the boundary case; the record decides it.
- **Censoring** if the series never crosses within the window **and is still rising at the horizon**, the
  claim is `null / horizon_censored`. If it never crosses and is **falling**, that is a real
  *not-exceeded* result, evaluable per T0.3 §4.3b.
- **Tolerance** `TOL_TIME_REL = 2%`.

### 2.4 `t_last_exceedance` and `exceedance_duration`
- **Units** days. **Algorithm** symmetric to §2.3 — linear interpolation on the falling limb;
  `exceedance_duration = t_last_exceedance − t_first_exceedance`.
- **Censoring** if the series is **still above threshold at the horizon**, `t_last_exceedance` and the
  duration are `null / horizon_censored`. A duration truncated by the window is not a duration.
- **Tolerance** `TOL_TIME_REL = 2%` on each endpoint; the duration inherits both.

### 2.5 `t_first_detection`
- **Units** days. **Algorithm** as §2.3 with the **detection floor** in place of the regulatory threshold.
- 🔴 **The detection floor is NOT frozen here.** M0 has it under active design
  (`M0_contract_freeze_plan.md:90–97`, `detection_floor = max(source_normalised_floor,
  observed_radius_spread)`). **T0.2b adopts M0's floor by reference and does not invent a second one.**
  Until M0 freezes it, every `t_first_detection` claim is `null / refinement_axis_untested`.

### 2.6 `capture_halfwidth_m` — upstream plume / capture half-width (PRT)
- **Units** m. **Algorithm** bisection of the dividing streamline on a transect
  (`transport_prt_capture.py:666`), bisection tolerance 0.25–1.0 m, max offset 150 m.
- ⚠️ **Platform-sensitive: ~24% Mac↔Hub spread** on the bisected half-width
  (`test_transport_prt_capture.py:664`). **`≈53 m` may never be quoted as a grid-supported value without a
  platform qualification**, and the qualification never substitutes for generation.
- **Tolerance** `TOL_WIDTH_REL = 5%` relative — deliberately looser than the concentration tolerance
  because the bisection's own probe settings move it by ~1 m, and **still far tighter than the 24%
  platform spread**, which is why the platform qualification is mandatory rather than optional.

### 2.7 Frozen tolerance table

| Name | Value | Applies to |
|---|---|---|
| `TOL_CONC_REL` | **2%** | `peak_mgL`, `emergent_C_mgL`, any concentration |
| `TOL_TIME_REL` | **2%** | `t_peak`, `t_first_exceedance`, `t_last_exceedance`, `exceedance_duration`, `t_first_detection` |
| `TOL_WIDTH_REL` | **5%** | `capture_halfwidth_m` and any distance metric |

⚠️ **These supersede nothing and hide nothing.** The existing `±8%` test pin
(`test_transport_srcpulse_demo.py:169`) is a **regression guard**, not a support tolerance — it would
absorb over half of the 14.5% effect and is exactly why T1 needs the canonical digest gate instead.

---

## 3. Sequences and stopping rules — predeclared

**Spatial series** — corridor cell size, coarse → fine, each a separate identity:
`50 m (native) → 20 m → 10 m (current default) → 5 m → 2 m`.
**Temporal series** — `cr_target` tightened at **fixed grid**: `0.9 → 0.45 → 0.225`.

**Stopping rules, in force order:**
1. **Tolerance reached** — two successive refinements move the metric by less than its §2.7 tolerance.
   Stop; the claim is a candidate for `grid_supported`.
2. **Feasibility ceiling** — the next refinement is priced above `HUB_FINE_CEILING_S`
   (`T0_0_canonical_contract.md` §6). Stop and report *"tolerance not reached within the feasible
   envelope"* — which is a **result**, not a failure.
3. **Step-cap** — hitting `nstp_cap` **fails loudly** and takes a failure edge (T1 exit). It may never pass
   as "honest time-stepping".
4. 🔴 **No open-ended refinement.** The series is these five spatial and three temporal points. Adding a
   point after seeing the results is a **failure edge to T0**.

**Both axes are required for `grid_supported`** (T0.3 §4.4). A claim evaluated on only one axis is
`null / refinement_axis_untested` — which is the current state of every arrival and exceedance-window
claim, because only the peak has ever been measured.

---

## 4. 🔴 The causal-support rule

### 4.1 `causal` splits in two — and only one half is in scope

*(Lecturer decision 2026-08-20, from the two-rater classification: of 42 agreed causal claims, roughly
three-quarters are not about this model at all.)*

| Sub-type | What it asserts | Example from the inventory | In T2 scope? |
|---|---|---|---|
| **`causal-physics`** | A statement of transport theory, true independently of any discretisation | *"the sorbing front advances at u/R, so arrival is delayed by R"* · *"∂C/∂t = −λC"* · *"divide q by porosity because water moves only through pore space"* | **No.** No grid could falsify it. `claim_support_state` does not apply; T3 does not rewrite it |
| **`causal-numerical`** | A statement about **this model's numerical behaviour** — what the grid smears, resolves, or cannot represent | *"transverse spreading is under-resolved on any feasible grid"* · *"TVD adds essentially no transverse numerical dispersion"* · *"the physical plume is sub-cell, so even a perfect scheme cannot represent it"* | **YES.** This is what T2 licenses or refuses, and what T3 must put in hypothesis voice |

**The rule applies only to `causal-numerical`.** Filing a physics claim as unsupported would be a category
error; filing a numerical claim as physics would smuggle the overclaim back in.

### 4.2 What would license `cause` — and what cannot

A metric plus a tolerance **cannot** license a causal claim. `cause` requires that every competing
explanation for the observed difference has been **held fixed**, not merely discussed.

🔴 **Named insufficient BY CONSTRUCTION** *(none of these may be cited as isolation)*:
1. **Operator A**, the fixed-support post-processing diagnostic — observation-support robustness only. A
   *null* under A is **ambiguous**, because A changed the estimand and spatially smoothed the plume.
2. **Any comparison in which the sink support OR the flow field also changed.**
3. **A null result under a changed estimand**, in general.
4. 🔴 **The B-control arm — it controls the SINK, not the FLOW.** B-control (funded 2026-08-20) legitimately
   establishes *"sink support was held fixed in the matched B arm"*. It does **not** reach `cause`, because
   GWF and GWT remain tied to each mesh's DISV grid (`transport_srcpulse_demo.py:437,483`) and the
   common-flow control is descoped.

### 4.3 The predeclared verdict

**`hypothesis`.** Under the funded matrix `cause` is **unreachable by construction** — flow is never held
common. This is the expected outcome, recorded before T2 runs so that it cannot be read as a
disappointment or renegotiated afterwards. **T3 and T4 are written in hypothesis voice from the first
draft**, not retrofitted.

What T2 **may** state: the measured difference, its direction and size, for this case and this platform;
whether a threshold decision survived the tested envelope; that sink support was controlled in the matched
B arm; and that reduced transverse numerical smearing is a **plausible leading explanation**.

---

## 5. The two matrices — named separately

| Matrix | Cardinality | Executed by |
|---|---|---|
| **`notebook_evidence_matrix`** | the §3 series: **5 spatial × 3 temporal**, plus the A diagnostic and the matched **B-control** arm at coarse and fine | **T2** |
| **`case_study_release_matrix`** | **40 rough + 10 fine = 50 identities** (≥100 cold/warm executions), with `grid_role` and `counterpart_run_id` | **case-study M3/M6 — NOT T2** |

Recorded here so T2 is never read as owing 50 identities for cases that do not yet exist. Not reopened.

---

## 6. Recorded decisions (not reopened here)

- **Receptor operator:** **A** (diagnostic-only) **and B-control** (matched evidence arm, `exp/vN` only).
  B-default is **not** activated. See `transport_notebook_milestones.md` T0.4.
- **Vocabulary:** `T0_3_claim_support_state.md` — three states, thirteen reason codes, ordered gate
  pipeline, compute truth table.
- **`arrival_day` → `t_peak`:** pre-authorised in `T0_0_canonical_contract.md` §3.3.

---

## 7. Open items

1. ✅ **The three tolerances in §2.7 are ACCEPTED** — lecturer, 2026-08-20: *"let's use your decisions for
   the three tolerances and see how this goes."* `TOL_CONC_REL = 2%` · `TOL_TIME_REL = 2%` ·
   `TOL_WIDTH_REL = 5%` are **frozen for T2**.

   ⚠️ **What "see how this goes" means procedurally, stated so it cannot drift.** The tolerances are now
   predeclared. If T2's results suggest a tolerance was wrong, the documented path is a **failure edge back
   to T0** — re-freeze, then re-run the affected series — **not** an in-flight adjustment once the numbers
   are visible. That is the whole reason they are frozen before T2 rather than chosen after it. A tolerance
   revised in light of the result it is meant to judge is not a tolerance.

   These are the first numbers in this workstream chosen by me rather than by the lecturer, so the
   reasoning is on the record: **2% on concentrations** is roughly 4× tighter than the existing ±8%
   regression pin, which would absorb over half of the 14.5% effect; **2% on times** is relative rather
   than absolute because an absolute ~1 day would exceed the output-lattice step and swallow the very
   effect §1 exists to expose; **5% on widths** is looser because the bisection's own probe settings move
   the half-width by ~1 m, while still being far tighter than the 24% Mac↔Hub platform spread — which is
   why the platform qualification stays mandatory.
2. **The detection floor (§2.5) is owned by M0 and is not yet frozen there.** Until it is, every
   `t_first_detection` claim is `null`.
3. **Regulatory threshold values, PFOA especially** — still open, still a live legal fact, still needed by
   T3/T4 rather than by T0.
4. **The claim inventory's judgment pass is incomplete** — 123 of 249 candidates classified (114 by
   two-rater agreement, 9 as compound spans); 12 student-facing disputes and 114 code/test candidates
   remain. T0.2 does not exit until the inventory gate exits 0.
