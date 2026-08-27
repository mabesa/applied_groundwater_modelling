# T2 · S5 — the cheap temporal identities (50 m)

**Run 2026-08-26**, macOS-arm64, through the S3 controls. **Both ACCEPTED.**

| identity | `nstp` | wall | `peak_mgL` | `t_peak` |
|---|---:|---:|---:|---:|
| `spatial_50m_cr0.9` *(the shared cr 0.9 endpoint)* | 86 | 11.9 s | 3.5893 | 44.624 |
| `temporal_50m_cr0.45` | 171 | 17.0 s | 3.6961 | 44.603 |
| `temporal_50m_cr0.225` | 342 | 27.4 s | 3.7528 | 44.585 |

`nstp` doubles exactly as `cr_target` halves — **86 → 171 → 342** — confirming the `nstp ∝ 1/cr` assumption
the pricing predictions rest on.

---

## 1. ✅ The temporal axis CONVERGES at 50 m — on both metrics

| step | `peak_mgL` | vs 2% | `t_peak` | vs 2% |
|---|---:|---|---:|---|
| `cr 0.9 → 0.45` | +2.975% | OVER | −0.048% | ✅ within |
| `cr 0.45 → 0.225` | **+1.536%** | ✅ **within** | **−0.039%** | ✅ **within** |

Both metrics are inside tolerance at the final step, and both series are **monotone**. On this axis, at this
grid, refinement behaves the way a convergence study is supposed to.

## 2. 🔴 The two axes control DIFFERENT things — and it is almost a clean split

| | `peak_mgL` | `t_peak` |
|---|---|---|
| **Spatial** refinement (20 → 10 m) | −1.14% *(within)* | **+13.70%** *(6× over)* |
| **Temporal** refinement (0.45 → 0.225) | **+1.54%** *(within)* | −0.04% *(essentially zero)* |

> **Spatial refinement moves the TIMING. Temporal refinement moves the MAGNITUDE.** Each axis is nearly
> inert on the other's metric.

That is direct evidence for `T0_3…` §4.4's **both-axes** requirement — not as a formality, but because **a
one-axis study is blind to whichever quantity that axis does not control.** A spatial-only study would have
declared the peak converged while the arrival time was still moving 13.7%.

⚠️ **It also explains S4's non-monotonicity**: the spatial series was moving `t_peak` sharply while the
temporal series holds it to 0.04%. The axes were never measuring the same thing.

## 3. 🔴 Cost is dominated by FIXED overhead at this end of the series

`nstp` rose **4.0×** (86 → 342) while wall rose only **2.3×** (11.9 → 27.4 s), implying

```
wall ≈ 6.7 s fixed  +  ~60 ms per timestep
```

**≈56% of the cheapest run is fixed cost** — grid build, GWF solve, I/O — none of which scales with `nstp`.

> ⚠️ **A third independent reason the S10 recalibration gate is necessary.** These cheap points are
> *overhead-dominated*; the expensive ones will be *work-dominated*. Fitting `wall ≈ k·W + c` here and
> extrapolating to 2 m means fitting in one regime and predicting in another. The intercept must be carried
> explicitly, and the fit re-done once 5 m lands.

## 4. 🔴 The B-control COARSE arm did NOT run — its radius is not frozen

S5 was to include the coarse B-control adjacent to its 50 m endpoint. **It cannot run yet.**

`T0_0…` §3 freezes `sink_support_m`'s **identity default (`0.0`)** and its meaning — *"radius of the fixed
physical extraction-support disc"* — but **no positive value is frozen anywhere** for the B-control arm.
Operator A's disc radius was decided and recorded (**25.0 m**, `T1_open_definitions.md`); the **sink-support
radius never received the same treatment.**

🔴 **And it is not a free parameter.** `T1_open_definitions.md` already records that operator A is **not
applicable at 50 m**, because a 25 m disc covers **0.785 of one cell**. The B-control faces the same
constraint at its coarse endpoint:

> **A support disc must be meaningfully larger than the cell, or it degenerates into the single-cell sink
> it exists to replace.** At 50 m cells, any radius near 25 m is *smaller than one cell* — the "control"
> would be the thing it controls for.

Since the arm is **matched coarse + fine** — the *same physical disc* at both grids — the radius must be
chosen so it is non-degenerate at the **coarse** end. That points well above 50 m, which is a physical
modelling decision (how large a region should the well be treated as drawing from?), **not an
implementation detail to assume.**

**Needed:** a decided, recorded `sink_support_m` for the B-control arm, with the same treatment operator A's
25.0 m got.
