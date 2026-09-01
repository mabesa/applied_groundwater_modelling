# T2 · S13 — operator A (observation-support robustness)

**2026-09-01.** Post-processing only — **0 solves**. Operator A re-reads each existing run's
concentration as a **saturated-thickness-weighted average over a fixed 25 m disc** centred on the
receptor, instead of the single receptor cell.

`RADIUS_M = 25.0`, `algorithm_id` as frozen in `transport_operator_a`. Applicability is
`cell_size_m <= radius_m`, satisfied by all five runs below. **All five returned `status:
"computed"`** — no `not_applicable`, no error.

| run | cell | single-cell `peak_mgL` | operator A | A ÷ 1-cell |
|---|---:|---:|---:|---:|
| `spatial_10m_cr0.9` | 10 m | 5.2770 | 3.9871 | 0.756 |
| `spatial_5m_cr0.9` | 5 m | 5.8765 | 4.0198 | 0.684 |
| `spatial_2m_cr0.9` | 2 m | 6.1085 | 4.0009 | 0.655 |
| `bcontrol_coarse` | 10 m | 4.9123 | 4.6965 | 0.956 |
| `bcontrol_fine` | 2 m | 5.7771 | 5.5232 | 0.956 |

---

## 1. The measurement

| arm, 10 m → 2 m | single-cell | operator A |
|---|---:|---:|
| **uncontrolled** | **+15.76%** | **+0.35%** |
| **B-controlled** | +17.60% | **+17.60%** |

Across the three uncontrolled meshes (10 / 5 / 2 m) operator A spans **0.82%** total —
3.9871, 4.0198, 4.0009 — while the single-cell metric moves +15.76% over the same refinement.

**In the B-control arm operator A tracks the single-cell metric exactly** (+17.60% against
+17.60%), and the A ÷ 1-cell ratio is constant at 0.956 on both meshes.

## 2. 🔴 What this may and may NOT be read as

It is tempting to conclude *"the grid sensitivity of the peak is an observation-support
artifact"*. **`T0_2b…` §4.2 predeclared that this exact reading is not available:**

> **Named insufficient BY CONSTRUCTION** *(none of these may be cited as isolation)*:
> **Operator A**, the fixed-support post-processing diagnostic — observation-support robustness
> only. **A *null* under A is ambiguous**, because A changed the estimand and spatially smoothed
> the plume.

A near-null under A is precisely the predeclared-ambiguous case. **This file therefore records
the measurement and its ambiguity, and offers no explanation of it.**

⚠️ An earlier draft listed two candidate readings side by side. That was itself a thumb on the
scale *(codex, 2026-09-01)*: naming the appealing explanation first gives it weight the data do
not support. **No preferred explanation is stated here, and none may be inferred downstream.**

What the measurement does support, exactly: **the smoothed measure is near-invariant across the
three uncontrolled meshes tested.** It says nothing decisive about the single-cell metric's
sensitivity — which is what the contract's word *ambiguous* means.

## 3. A described contrast between the arms — description only

In the B-control arm A is **not** near-null: it moves +17.60% over the same refinement, and the
single-cell metric moves +17.60% too. The A ÷ 1-cell ratios were **equal to three decimals (0.956)
at the two meshes tested**.

⚠️ **This is a description, not an explanation, and it cannot isolate a cause** *(codex,
2026-09-01)*. The contract bars citing A as isolation; contrasting A's behaviour *between* two
arms does not evade that bar. Both arms give **one step on two meshes**, no mechanism was tested,
and two rounded values are not a demonstrated constant.

Recorded so the difference between the arms is on the record. Nothing follows from it here.

## 4. Scope

- **Five runs, not twelve.** Operator A needs the run's grid, heads and concentration output.
  The 50 m and 20 m workspaces (S4) and the 1 m workspace no longer exist, and 50 m would be
  `not_applicable` anyway (`50 <= 25` is false). Re-running 1 m to extend this costs ~96 min and
  was not done.
- **`t_peak` under A** is recorded in `S13_operator_a.json` but not analysed here; the frozen
  tolerance work in this file concerns `peak_mgL`.
- **0 solves**, as the step requires. Every number above is post-processing of an existing,
  accepted, registered run.
