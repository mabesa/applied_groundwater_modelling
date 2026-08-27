# T2 · S6 — the capture fingerprint across MESHES

**Run 2026-08-26**, macOS-arm64, one platform, three meshes — the carried question from
`T1_EXIT_RECORD.md` §5.1.

| cell | `halfwidth_m` | `+` side | `−` side | analytic asymptote | wall |
|---:|---:|---:|---:|---:|---:|
| 50 m | 56.5625 | 57.344 | 55.781 | 71.683 | 5.2 s |
| 20 m | 52.8125 | 58.594 | 47.031 | 71.461 | 4.5 s |
| 10 m | 53.1250 | 63.594 | 42.656 | 71.621 | 4.6 s |

---

## 1. 🔴 The sensitivity is MESH, not platform — and it EXCEEDS tolerance

| axis | spread | vs `TOL_WIDTH_REL = 5%` |
|---|---:|---|
| **Platform** — 2 platforms, 10 fresh runs (2026-08-26) | **0.0000%** | identical to the digit |
| **Mesh** — 50 / 20 / 10 m, one platform | **6.92%** | 🔴 **EXCEEDS** |

> **`T0_2b…` §2.6 recorded a "~24% Mac↔Hub spread" and made a PLATFORM qualification mandatory. The
> measurement says the platform axis is exactly zero and the MESH axis is the one that fails.** The
> caution was real; it was attached to the wrong variable.

⚠️ **This does not contradict the signed narrowing.** §2.6 was narrowed *only* between the two measured
platforms and explicitly *"remains required for any platform, toolchain, or **mesh** not covered by that
measurement."* The mesh half was deliberately left open. **It is now closed, and it fails.**

## 2. What this costs S10

`T1_EXIT_RECORD.md` §5.1 predeclared the consequence, so it is applied rather than negotiated:

> *"If mesh spread exceeds the tolerance, the fingerprint **describes the mesh, not the plume**, and S10's
> arm loses that quantity while keeping its deterministic flow deltas."*

- 🔴 **`capture_halfwidth_m` cannot serve as grid evidence.** A 6.92% mesh spread against a 5% tolerance
  means a cross-mesh difference is not distinguishable from the mesh itself.
- ✅ **S10's arm is NOT lost.** Its substance is the **quantified flow deltas** — deterministic solver
  outputs, unaffected by this.
- ✅ **S10's design already anticipated this**: `compare_fingerprints` refuses without a recorded envelope
  below tolerance. **The envelope now exists and is above tolerance, so the refusal stands** — the control
  works as built, and nothing needs changing.

## 3. 🔴 The MEAN hides a growing asymmetry — and the mean is what gets quoted

| cell | `+` side | `−` side | difference | asymmetry |
|---:|---:|---:|---:|---:|
| 50 m | 57.344 | 55.781 | 1.563 m | 2.8% |
| 20 m | 58.594 | 47.031 | 11.563 m | 21.9% |
| 10 m | 63.594 | 42.656 | **20.938 m** | **39.4%** |

**The two sides diverge as the grid refines** — from 2.8% apart at 50 m to **39.4% apart at 10 m** — while
the reported mean barely moves (56.6 → 52.8 → 53.1).

The notebooks already say the zone *"is not symmetric, because the injection well sits off to one side"*,
and refinement evidently **resolves that asymmetry rather than creating it**. But a single mean is a poor
summary of two numbers moving apart: **the mean looks stable precisely because the sides are diverging in
opposite directions.**

⚠️ **The `≈53 m` quoted to students is the 10 m value** (53.125). It is correct *at the default grid* and
moves 6.92% across meshes — the same class of qualification the platform one was meant to provide,
attached to the right axis this time.

## 4. ✅ The ANALYTIC asymptote is mesh-stable

`y_max = Q/(2qb)`: **71.683 / 71.461 / 71.621** — a spread of **0.31%**, well inside any tolerance.

That is worth noting because it is the screening formula from `01t`: **the hand calculation is stable
where the numerical bisection is not.** The reconciliation argument the notebooks build — *screen and model
agree once compared at the right place* — rests on the stable end.
