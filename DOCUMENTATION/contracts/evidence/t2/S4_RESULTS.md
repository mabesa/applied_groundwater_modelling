# T2 · S4 — the cheap spatial identities

**Run 2026-08-26**, macOS-arm64, through the S3 controls: pre-registration checksum verified, each
identity checked against the registered set, guard taken from S2 (**40000**, the discovery guard), each
artifact through `accept_run` with the verdict written beside it. **All three ACCEPTED.**

| identity | cell | `ncpl` | `nstp` | `Cr` | wall | `W = ncpl·nstp` |
|---|---:|---:|---:|---:|---:|---:|
| `spatial_50m_cr0.9` | 50 m | 4221 | 86 | 0.894 | 11.9 s | 363,006 |
| `spatial_20m_cr0.9` | 20 m | 4233 | 85 | 0.898 | 11.4 s | 359,805 |
| `spatial_10m_cr0.9` | 10 m | 4408 | 122 | 0.898 | 15.0 s | 537,776 |

✅ **The 10 m identity reproduces the reference exactly** — `peak_mgL = 5.27695440327`,
`t_peak = 38.8043478261`. The default is intact and the chain is trustworthy.

---

## 1. 🔴 A ~4% change in CELL COUNT moves the peak ~47%

| | |
|---|---|
| `ncpl` across the whole series | **4221 → 4408, +4.4%** |
| `peak_mgL` across the same | **3.589 → 5.277, +47.0%** |

The domain is dominated by the base 50 m grid; corridor refinement adds only ~190 cells. **Yet the metric
moves enormously.** That is consistent with the receptor-cell-size hypothesis the earlier spikes raised and
could not rule out: `peak_mgL` is read at **one cell**, so its size and placement dominate the readout far
more than the global cell count does.

⚠️ **Consequence for pricing:** `ncpl` is nearly constant, so cost here is driven almost entirely by
**`nstp`**. `W = ncpl·nstp` still tracks wall time acceptably over these three points, but the series has
not yet exercised the regime where `ncpl` grows — **5 m and 2 m are where that changes**, and the S10
recalibration gate exists precisely because extrapolating past that point is unsafe.

## 2. 🔴 Neither metric is MONOTONE, and the two axes disagree

```
peak_mgL : 3.589 -> 5.338 -> 5.277     up, then DOWN
t_peak   : 44.62 -> 34.13 -> 38.80     down, then UP
```

| step | `peak_mgL` | vs 2% | `t_peak` | vs 2% |
|---|---:|---|---:|---|
| 50 m → 20 m | **+48.72%** | OVER | **−23.52%** | OVER |
| 20 m → 10 m | **−1.14%** | ✅ within | **+13.70%** | **OVER** |

> 🔴 **At 20 m → 10 m the concentration axis is inside tolerance while the timing axis is six times outside
> it.** Stopping rule 1 says *"two successive refinements move **the metric** by less than its tolerance"* —
> singular. **These metrics converge at different rates, so convergence is PER-METRIC, not per-series**, and
> a claim's verdict depends on which metric the pre-registration mapped it to.

⚠️ **Non-monotone behaviour also means a two-point comparison can mislead.** 20 m → 10 m looks nearly
converged on the peak, but only because the peak overshot at 20 m and came back — not because it settled.

## 3. What this does NOT establish

- **Nothing about 5 m or 2 m.** Three coarse points, in a regime where `ncpl` barely moves.
- **Nothing about the temporal axis** — that is S5 (50 m) and, if it runs, S11 (2 m).
- **No convergence verdict.** Both surviving steps are over tolerance on at least one metric, so on this
  evidence the series is **not converged at 10 m**.
- ⚠️ **These are macOS numbers.** Hub cost is `× H ≈ 2.30`.
