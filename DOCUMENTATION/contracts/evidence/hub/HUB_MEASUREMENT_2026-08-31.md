# Hub measurement — 2026-08-31 (five pairs)

`hub_measurement.py --workdir ~/hub_meas --qualify-reps 5`, on
`Linux-6.8.0-136-generic-x86_64-with-glibc2.39`, Python 3.12.9.
**Supersedes `HUB_MEASUREMENT_2026-08-26.md`**, which measured one pair.

---

## Result 1 — `H = 2.169`, and the first pair is a COLD OUTLIER

| pair | side A | side B | mean |
|---:|---:|---:|---:|
| **1** | 36.84 | 36.37 | **36.61** |
| 2 | 30.30 | 31.24 | 30.77 |
| 3 | 30.09 | 30.48 | 30.29 |
| 4 | 31.15 | 30.00 | 30.57 |
| 5 | 30.65 | 29.77 | 30.21 |

| basis | n | mean side | spread | `H` |
|---|---:|---:|---:|---:|
| **all 5 pairs (reported)** | 10 | 31.69 s | **22.31%** | **2.169** |
| pairs 2–5 (warm) | 8 | 30.46 s | 4.83% | 2.085 |
| *old, 2026-08-26* | *2* | *33.65 s* | *12.2%* | *2.30* |

🔴 **Pair 1 runs +20.2% slower than pairs 2–5**, and pairs 2–5 agree to within 4.83%.
That is a cold-start effect — first-touch paging and cache warming — not variance.

**This explains the old `H = 2.30`.** It was a single pair whose two sides were 35.69 and
31.60 — a cold side followed by a warmer one, which is the same signature. A one-pair
measurement on a cold worker **cannot avoid** sampling the warm-up, so 2.30 was biased
high by construction, and its own 12.2% internal spread was the visible symptom.

> **Recorded value: `H = 2.169`, pooled over all ten sides.** The warm-only 2.085 is the
> better estimate of steady-state cost, but pooling is retained because it is the
> conservative direction for a ceiling test, and because a student's first run on a fresh
> worker *is* a cold run.

**The 22.31% `side_spread_rel` is therefore structure, not noise** — do not read it as
"H has not converged". Warm-state H is converged to under 5%.

## Result 2 — ✅ the Hub-side gate qualification PASSES

`qualification: PASS` · `payload_mismatch_count: 0` · `env_mismatches: {}` ·
**5 of 5 pairs passed.**

`T0_0…` §5.1 qualified the gate on macOS-arm64 and said plainly that *"it makes **no**
claim about the Hub, and a Hub-side T1 gate would need its own qualification."*
**That gap is now closed by measurement**, over ten side-runs rather than two.
*("Cold" belongs to the first pair only — see Result 1. The later pairs are warm, which is why they are the better guide to steady-state cost.)*

Also a second platform sample against the historical ~40% macOS-arm64 SIGILL claim:
**0 failures in 10 side-runs** (Linux; the historical figure was macOS, so this
corroborates rather than refutes).

## Result 3 — 🔴 the "~24% Mac↔Hub spread" in `capture_halfwidth_m` is REFUTED

`T0_2b…` §2.6 recorded a ~24% Mac↔Hub spread and made a platform qualification mandatory
on the strength of it. Measured directly, with the **identical** call
(`capture_halfwidth_at(0.0)`) in fresh processes on both platforms:

| platform | n | halfwidths | spread |
|---|---:|---|---:|
| Hub (Linux) | 5 | 53.125 × 5 | **0.00%** |
| Mac (arm64) | 3 | 53.125 × 3 | **0.00%** |

**Both platforms return exactly 53.125 m.** Cross-platform spread is **0.00%**, not 24%.
This agrees with S6, which already recorded *"platform was 0.00%"*.

⚠️ **This does NOT lift S6's refusal, and the script's `"ENVELOPE OK -- comparisons may be
enabled"` must not be read as though it does.** That verdict is about the *repeatability*
envelope. What disqualifies `capture_halfwidth_m` as grid evidence is S6's **6.92% spread
across MESHES** (50 m → 56.5625, 20 m → 52.8125, 10 m → 53.125) against a 5% tolerance —
a different axis entirely. Platform repeatability was never the binding constraint.

## Result 4 — ⚠️ the fine-run verdict rests on a WITHDRAWN number

The script reports `projected_fine_run_s: 685.4` → *"PASSES WITH WARNING
(target..ceiling)"*, from `FINE_RUN_MAC_S = 316`.

🔴 **That 316 s figure is the capped run the project withdrew** — it sat on `nstp_cap =
2000`, so `cr_target = 0.9` may never have been reached and the true cost is unknown and
higher. The runbook flags this; the constant does not. **The verdict inherits the defect**:

| basis | projection | band |
|---|---:|---|
| `H` = 2.169 (pooled) | 685.4 s | warning (600–900) |
| `H` = 2.085 (warm) | 658.8 s | warning (600–900) |

Both land in the warning band, but from a base the project does not stand behind. Treat
`projected_fine_run_s` as **not evidence** until it is recomputed from an uncapped run.

⚠️ Separately, the ceiling this is tested against is a **student-experience** constraint.
`S10_SUB2M_SOLVER.md` §1 records the lecturer's instruction that instructor-side evidence
generation is not bound by it — and the 1 m identity was accepted on 2026-08-27 at a
predicted ~81 minutes, roughly 5× the ceiling. So even a clean projection would not, by
itself, stop the run.

---

## What this settles, and what it does not

| | |
|---|---|
| ✅ `H` measured at parity (5 pairs / 10 sides), cold-start structure identified | |
| ✅ Hub-side gate qualification — `T0_0…` §5.1's stated gap, closed | |
| ✅ `capture_halfwidth_m` platform spread — refuted at 0.00%, was recorded as ~24% | |
| ❌ `capture_halfwidth_m` as grid evidence — **still refused**, on S6's 6.92% mesh spread | |
| ❌ the fine-run feasibility verdict — **still unusable**, base number withdrawn | |
