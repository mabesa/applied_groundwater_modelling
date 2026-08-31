# T2 · S8b — the probe ranking, re-opened for the thirteen-case roster

**2026-08-31.** `T0_5…` §1.2 requires the pilot ranking to be re-opened when a case is added:

> The pilot's ranking is recorded with the roster hash, so adding the tenth case re-opens the
> question explicitly rather than leaving a stale bound.
> ⚠️ **Adding or replacing a case requires re-evaluating both the proxy and the pilot.**

The roster went from nine to thirteen on 2026-08-31. This is that re-evaluation.

| | |
|---|---|
| roster (`doublet_table.csv`) | `da80e86d01f9d2d48881f068b593ccbd2ed0463dd36a0bb0131e201683f48b7f` |
| supersedes | the nine-case ranking in `S8_PILOT_AND_PROBE.md` |

---

## 1. The probe HOLDS — and the margin collapsed

| rank | case | contaminant | `W = ncpl × nstp` | wall (Mac) |
|---:|---|---|---:|---:|
| **1** | **`b010236`** (g3) | Chloride | **14,502,750** | 231.8 s |
| **2** | `b010226` (g11) — **new** | Boron | **13,838,616** | 177.8 s |
| 3 | `b010120` (g4) | Chromium | 11,892,540 | 153.3 s |
| 4 | `b010227` (g6) | PCE | 11,158,016 | 183.3 s |
| 5 | `b010222` (g12) — new | Nickel | 9,236,721 | 132.7 s |
| 6 | `b010204` (g9) — new | MTBE | 7,051,720 | 102.6 s |
| 7 | `b010213` (g7) | Ammonium | 6,685,308 | 103.0 s |
| 8 | `b010220` (g10) — new | Carbamazepine | 2,608,242 | 37.7 s |
| 9–13 | the remaining five | | 0.25–2.3 M | 8–46 s |

**`b010236` remains the probe.** No re-naming is required, so §1.2's failure edge does **not** fire
a second time.

🔴 **But the margin fell from 1.22× to 1.05×.** A single new case landed within **4.6%** of taking
the probe. The nine-case margin made the incumbent look settled; it is not.

> **Do not assume the incumbent on the next roster change — re-run the pilot.** At a 4.6% margin,
> one more case of `b010226`'s character flips it.

⚠️ **`W` and wall-clock disagree in magnitude but agree on order here**: `b010226` is 4.6% below on
work yet 23% below on wall. §1.2's statistic is `ncpl × uncapped nstp`, so `W` governs; the
wall-clock agreement is corroboration, not the test.

## 2. Comparability

The nine original cases were measured at transport-config sha `c99b6037…` and the four new ones at
the current sha. A case's own build does not depend on the existence of other cases — same mother
model, same locked parameters, independent corridor — so the two sets are directly comparable. Every
run was uncapped (`cr` ≈ 0.90, `cr_capped: false`).

## 3. Feasibility is unchanged and still comfortable

Worst identity is still **`b010236` at 503 s on the Hub** (231.8 s × H 2.169) against
`HUB_FINE_TARGET_S` = 600 and `HUB_FINE_CEILING_S` = 900. The four new cases land at 386 s, 288 s,
223 s and 82 s. **13 of 13 build, all uncapped.** `T0_5…` §2's predeclared risk — that the mandatory
per-group fine run may be unaffordable — still does not materialise.
