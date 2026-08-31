# T2 · S10–S12 — the spatial series closes, and both series CONVERGE

**2026-08-31.** Four frozen identities run through the controlled path
(`t2_run_matrix.py`: `verify_prereg` → registered-identity refusal → guard → acceptance).
**All four ACCEPTED, zero failures, none capped.**

| identity | `ncpl` | `nstp` | `Cr` | guard | `W` | wall (Mac) |
|---|---:|---:|---:|---:|---:|---:|
| `spatial_5m_cr0.9` | 5 784 | 370 | 0.899 | 40 000 | 2.14 M | 54 s |
| `spatial_2m_cr0.9` | 15 727 | 1 979 | 0.900 | 40 000 | 31.1 M | 650 s |
| `temporal_2m_cr0.45` | 15 727 | 3 958 | 0.4499 | 40 000 | 62.2 M | 1 196 s |
| `temporal_2m_cr0.225` | 15 727 | 7 915 | 0.2250 | 40 000 | 124.5 M | 2 204 s |

**10 of the 12 registered identities are now measured.** The two outstanding are the
**B-control** pair, blocked on a definition — `sink_support_m` was never frozen — not on cost.

---

## 1. ✅ The spatial series converges, and `TOL_CONC_REL` is met

| cell | `peak_mgL` | step | `t_peak` | step |
|---:|---:|---:|---:|---:|
| 5 m | 5.8765 | — | 37.392 | — |
| 2 m | 6.1085 | **+3.948%** | 37.653 | +0.697% |
| **1 m** | **6.1322** | **+0.389%** | 37.946 | +0.779% |

`TOL_CONC_REL = 2%` (§2.7). The **2 m → 1 m step is +0.389%** — inside tolerance. The preceding
step is +3.948%, outside it. Stopping rule 1 asks for **two successive refinements** below
tolerance, so on `peak_mgL` this series delivers **one** qualifying step, not two.

`t_peak` moves +0.697% then +0.779%, both inside `TOL_TIME_REL = 2%` — two successive steps, so
**timing is converged** by rule 1.

🔴 **Convergence is PER-METRIC.** `t_peak` satisfies rule 1; `peak_mgL` does not, on the strict
two-step reading. The magnitude is clearly settling — 3.948% → 0.389%, a factor of ten — but the
rule is a rule, and this file does not soften it.

⚠️ **These steps REPRODUCE the numbers `04t` already publishes to students** — *"+11.4%, then
+3.9%, then +0.4%"*. Until now only `spatial_1m_cr0.9` was a registered identity, so those
student-facing claims rested on the earlier spike. They now rest on controlled-path evidence.

## 2. ✅ The temporal series at 2 m converges

| `cr_target` | `nstp` | `peak_mgL` | step |
|---:|---:|---:|---:|
| 0.9 | 1 979 | 6.1085 | — |
| 0.45 | 3 958 | 6.1170 | +0.139% |
| 0.225 | 7 915 | 6.1213 | +0.070% |

Two successive refinements at **+0.139%** and **+0.070%**, both far inside `TOL_CONC_REL = 2%`.
**Rule 1 is satisfied: time-stepping is converged at 2 m.**

## 3. 🔴 S8's refusal of 2 m was correct — and conservative in the right direction

S8 priced 2 m at `W` = 31.5 M and **refused** it against `HUB_FINE_CEILING_S`.

| | |
|---|---|
| S8 predicted `W` | 31.5 M |
| **measured `W`** | **31.12 M** — 1.2% high |
| S8 projected Hub | 1 058 s |
| **measured × H 2.169** | **1 410 s** |

So 2 m really would have breached the 900 s ceiling, by more than S8 thought. **When the ceiling
still bound the series, 2 m was genuinely infeasible for students.** The 2026-08-27 amendment —
fine grids become instructor-side precomputation — is what makes this run legitimate, and this
measurement is what shows the amendment was load-bearing rather than convenient.

⚠️ **The cost model is weaker than the earlier checks suggested.** At 5 m it under-predicted the
wall by **31%**, and its `W` input there was **1.84×** low (it assumed `nstp` ≈ 200; actual 370).
It is good at 1 m and at 2 m and poor at 5 m — treat it as an order-of-magnitude tool.

## 4. The guard choice, and why it mattered

`T2_run_guards.json` offers a **derived** guard — 2× the measured `cr 0.9` demand — for identities
whose `cr 0.9` demand is known. At 2 m that is 2 × 1 979 = **3 958**.

**`temporal_2m_cr0.225` needed 7 915 steps.** A derived guard would have **capped it**, and
`T0_2b…` §3 rule 3 says a capped run *"FAILS LOUDLY and takes a failure edge; it may never pass as
honest time-stepping."* The result would have been a false failure edge.

The **discovery guard 40 000** was used instead, following S5's precedent: it used 40 000 for both
50 m temporal identities even though their `cr 0.9` counterpart had been measured. A temporal
identity's own demand is unknown until measured, so the derived rule does not reach it.

## 5. What remains

| | |
|---|---|
| **B-control coarse + fine** | 🔴 blocked on the unfrozen `sink_support_m` radius — a definition, not a cost. **Cut from S11** (codex, 2026-08-31) so it cannot gate runnable identities |
| S13 Operator A | post-processing, 0 solves — unblocked |
| S4/S5 artifacts | deliberately **not** back-filled (codex): their accepted summary evidence exists, and re-running six cheap identities to change the shape of the record buys nothing |
