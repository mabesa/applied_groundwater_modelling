# Spike — does GRADED refinement fix the 2 m instability? **No.**

**2026-08-27.** Tried before writing an S3b brief, on the lecturer's instruction to test the idea rather
than re-plan around it. **No production file was changed.**

---

## 0. It was buildable today

`_create_voronoi_with_refinement` **already accepts per-polygon max areas**
(`disv_grid_utils.py:1466`). `refine_grid_locally` simply passes *one* size for all of them. So a graded
mesh needed only a monkeypatched call in the spike — **A16's authority was not required to find this out.**

Grading as specified: base grid kept · corridor at an intermediate size · **smallest cells only at the
spill and both wells**.

## 1. 🔴 The limit is an ABSOLUTE MINIMUM CELL SIZE, not the grading

| disc request | **actual min cell** | pilot converges? |
|---:|---:|---|
| 5 m | 3.09 m | ✅ |
| **4 m** | **3.09 m** | ✅ |
| 3 m | 2.71 m | ❌ |
| 2 m | 1.47 m | ❌ |

> **The coupled GWF destabilises below ~3 m minimum cell size, however the refinement is graded.**
> Grading changes **where** the fine cells are — not whether the model tolerates them.

That is consistent with the solver finding: at `dvclose` 1e-3/1e-4 a uniform 2 m mesh *does* converge, so
the floor is a **solver-tolerance** property. Grading does not bypass it; it only puts fewer cells beneath
it. **And the solver route is closed** (`T0_0…` §4 — it moves concentrations 2.3e-04).

## 2. Graded buys nothing over uniform 5 m — it costs slightly more

| configuration | `ncpl` | `nstp` | `Cr` | `peak_mgL` | `t_peak` | wall |
|---|---:|---:|---:|---:|---:|---:|
| uniform **5 m** | 5784 | 370 | 0.899 | **5.8765** | 37.39 | **44.0 s** |
| graded **10 m corridor / 4 m discs** | 5243 | **531** | 0.899 | **5.8945** | 37.44 | **53.0 s** |

**Same answer** — 0.31% apart on the peak, 0.13% on the timing, both far inside their 2% tolerances.
**More expensive**, despite *fewer* cells.

🔴 **Why it costs more is the interesting part.** Grading puts the finest cells exactly at the **wells**,
which is where velocity is highest — so `max(v/ds)` rises and `nstp` goes **370 → 531**. **Refining where
the flow is fastest buys timesteps, not accuracy.**

## 3. ✅ What the spike did confirm

- **Uniform 5 m reproduces the original spike's 5 m value**: `5.8765` against the recorded `5.876`. The
  corrected pipeline agrees with the pre-T1 measurement where both are valid.
- **The fine end matters**: 10 m → 5 m moves the peak `5.277 → 5.877`, **+11.4%**. This is a real effect,
  not quantisation.
- **5 m converges and meets `cr_target`** (`Cr = 0.899`).

## 4. Where this leaves the grid question

- **The spatial series is `10 m → 5 m`.** Both converge, both meet `cr_target`, and they differ materially
  in the answer.
- **Finer than ~3 m is unreachable** by any currently authorised route: the solver path was measured and
  rejected on concentration movement, and grading does not lift the floor.
- ⚠️ **The spike's 2 m value (6.042) is 2.8% above 5 m** — so movement below 5 m is real and **remains
  unmeasured**. Ending *"tolerance not reached within the feasible envelope"* is the honest `T0_2b…` §3
  rule-2 outcome.
- **A16 is not wasted**, but it does not solve this. If graded construction ships, its value is
  cost-shaping — not reaching finer cells.
