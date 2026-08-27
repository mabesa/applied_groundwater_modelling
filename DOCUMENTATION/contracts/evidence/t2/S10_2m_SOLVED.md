# T2 — 2 m converges. The limit was an ITERATION CAP, not physics.

**2026-08-27.** After the graded-refinement spike returned "no", the failure was diagnosed properly.

---

## 1. What was actually limiting us

The failed run's own listing gave it away:

```
PERCENT DISCREPANCY = -0.09      WEL ABSW = 1370.0 m3/d
****FAILED TO MEET SOLVER CONVERGENCE CRITERIA IN TIME STEP 1 OF STRESS PERIOD 1****
```

**The budget closes to −0.09% with correct flows.** The solution was physically fine — it simply never
drove the head change below `outer_dvclose = 1e-4 m` (**0.1 mm**) within **200 outer iterations**.

**No dry cells. No oscillation into garbage. An iteration budget.**

| configuration | 2 m converges? | pilot |
|---|---|---:|
| `outer_maximum = 200` (as shipped) | ❌ | 16.4 s |
| **`outer_maximum = 1000`** | ✅ | 28.0 s |
| `outer_maximum = 1000` + DBD under-relaxation | ✅ | 15.2 s |

## 2. 🔴 And raising the cap is EXACTLY output-neutral

This is the crucial difference from relaxing `dvclose`. **The tolerance is unchanged** — a run that already
converges inside 200 iterations never reaches the higher limit.

| change | default `peak_mgL` | |
|---|---|---|
| as shipped | `5.27695440327` | reference |
| **`outer_maximum = 1000`** | **`5.27695440327`** | ✅ **bit-identical** |
| `+ DBD` | `5.27695660395` | moves 4.2e-07 — inside 1e-5, but not identical |

**`compare` PASSES with 0 payload mismatches.** So the cap was raised and **DBD was not**: the cap costs
nothing, while DBD changes the answer for a benefit that turns out to be small (§4).

## 3. ✅ The complete spatial series

All three converge and all three meet `cr_target` under `exp_v1`:

| cell | `ncpl` | `nstp` | `peak_mgL` | `t_peak` | Mac | Hub (×2.30) |
|---:|---:|---:|---:|---:|---:|---:|
| 10 m | 4408 | 122 | 5.2770 | 38.67 | 14.8 s | 34 s |
| 5 m | 5784 | 370 | 5.8765 | 37.39 | 44.0 s | 101 s |
| **2 m** | **15727** | **1979** | **6.1085** | 37.65 | **524.9 s** | **1207 s** |

✅ **Agrees with the original spike where both are valid**: ours `5.277 / 5.877 / 6.109` against the
recorded `5.277 / 5.876 / 6.042`. The 2 m difference is expected — the spike ran under the defective
Courant policy S8 fixed.

## 4. 🔴 The peak has NOT converged, even at 2 m

| step | `peak_mgL` | vs 2% | `t_peak` | vs 2% |
|---|---:|---|---:|---|
| 10 m → 5 m | **+11.36%** | OVER | −3.31% | OVER |
| 5 m → 2 m | **+3.95%** | 🔴 **OVER** | **+0.70%** | ✅ within |

> **Timing has converged. The magnitude has not.** `t_peak` is inside tolerance at the finest step;
> `peak_mgL` is still moving **3.95%** — twice its tolerance — with no sign of settling.

⚠️ **This is the substantive T2 result on the spatial axis**, and it is now *measured* rather than assumed:
**the peak is not grid-converged within the envelope that was reachable.**

## 5. Where the feasibility question now sits

**2 m projects to ~1207 s on the Hub, above `HUB_FINE_CEILING_S = 900 s`.** Per `T0_2b…` §3 rule 2 the
series stops there and reports *"tolerance not reached within the feasible envelope"* — **a result, not a
failure.**

⚠️ **But we now hold the 2 m datum**, which is strictly more informative than stopping blind: we know the
peak is still climbing at 3.95% per refinement step, and we know what it costs to see that.

**DBD does not rescue the cost.** It nearly halves the *pilot* (GWF-dominated) but the full run is
timestep-dominated at `nstp = 1979`: **503.5 s against 524.9 s, 4%.**

🔴 **Whether the 2 m run counts as matrix evidence, given it exceeds the ceiling, is the lecturer's call.**
