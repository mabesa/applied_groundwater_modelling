# Case-study retuning hierarchy (M1.5)

The **ordered ladder** for retuning a group that misses an M3c/M4/M5
equalization band. Retune in order, escalating to the next level **only when
the current level is numerically exhausted**. The numeric envelopes below are
**M5-tunable defaults** — M5 may adjust the envelopes, but the *ordering* and
the *guardrails* are fixed.

Companion machine artifacts:
[`casestudy_equalization_dimensions.yaml`](./casestudy_equalization_dimensions.yaml)
(what is being equalized) and
[`casestudy_structural_gates.yaml`](./casestudy_structural_gates.yaml)
(hygiene gates). Physics gates are M1.4's
[`casestudy_diagnostic_schema.yaml`](./casestudy_diagnostic_schema.yaml).

## The ladder

### Level 1 — Spill placement *(cheapest; try first)*
- **Lever:** the `source.location` E/N offset (relative to the extraction well).
- **Numeric envelope:** `|offset| ≤ 150 m` upgradient of the extraction well;
  the resulting absolute spill must stay **in-domain, in an active cell, and
  non-river** per M1.1's checks. *(default, tunable in M5)*
- **Exhausted → escalate:** the missed band is still not met after **≤ 5
  placement steps**.
- **Objective priority:** move the source, not the physics — a placement change
  never alters the contaminant or the flow forcing.

### Level 2 — Scenario magnitude
- **Lever:** the flow forcing factor (per scenario `type`) **or** the spill
  mass/duration.
- **Numeric envelope (hydrogeologic plausibility):**
  - recharge / transmissivity factor within **±30 %** of the assigned value;
  - CHD / river-stage change within **±1.5 m**;
  - released mass within **one order of magnitude**. *(defaults, tunable in M5)*
- **Exhausted → escalate:** the band is not met after **≤ 3 iterations**.
- **Guardrail (plausibility):** forcing changes may **NOT** be pushed past the
  plausibility bounds to force a band — an implausible forcing is not a valid
  equalization.

### Level 3 — Contaminant parameters
- **Lever:** the reactive-transport parameters.
- **Numeric envelope:**
  - `Kd` (`distribution_coefficient_mL_g`) within **±50 %** of its literature
    value;
  - `λ` (`first_order_decay_constant_1_per_day`) within a **factor of 2** (or
    the half-life within a defensible range). *(defaults, tunable in M5)*
- **Exhausted → escalate:** the band is not met after **≤ 3 iterations**.
- **`threshold_mg_L` is NOT a retuning lever.** It is the **regulatory
  compliance value**; it is corrected only if it is *wrong* (as with the TCE
  0.005 mg/L fix), **never adjusted to hit a difficulty band**.
- **Guardrail (anti-masking):** contaminant parameters may **NOT mask** a bad
  capture/transport setup. A placement or geometry problem is fixed at
  **Level 1–2**, never papered over with reactions (e.g. do not crank up
  sorption/decay to hide a source that is mis-placed relative to the capture
  zone).

### Level 4 — Doublet swap *(last resort)*
- **Lever:** replace the group's doublet concession.
- **Only via a logged roster-change review** — a swap re-runs
  **M1.1 → M1.3a + M4** for that group (new geometry, config rewrite, and flow
  re-validation). Never an ad-hoc edit.

## Escalation summary

| level | lever | numeric envelope | exhausted after | guardrail |
|---|---|---|---|---|
| 1 | spill placement | \|offset\| ≤ 150 m, in-domain/active/non-river | ≤ 5 steps | move source only |
| 2 | scenario magnitude | factor ±30 %, CHD/stage ±1.5 m, mass ×/÷10 | ≤ 3 iters | stay plausible |
| 3 | contaminant params | Kd ±50 %, λ ×2 | ≤ 3 iters | no masking; threshold is fixed |
| 4 | doublet swap | logged roster-change review | — | re-runs M1.1→M1.3a + M4 |

## Guardrails (global)

1. **Plausibility.** Every retune must stay within hydrogeologic /
   chemical-literature plausibility. Hitting a band is never a licence to use an
   implausible value.
2. **Anti-masking.** Difficulty must come from the *right* lever: a geometry /
   placement problem is a Level 1–2 fix, not a reactions fix. Reactions must not
   be used to hide a broken capture or transport setup.
3. **`threshold_mg_L` is off-limits.** The compliance threshold is regulatory
   input, not a difficulty knob — corrected only if demonstrably wrong.
4. **Physics gates are not retuning targets.** The M1.4 correctness gates
   (mass balance, finite fields, capture validity, coupling label) must pass on
   their own merits; you retune to hit *equalization* bands, never to slip past
   a correctness `raise`.
