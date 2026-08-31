# T2 · S8 — the roster pilot, and the probe it overturns

**2026-08-31.** `T0_5…` §1.2 requires that T2's first act be a **same-code pilot** over the
release roster, ranked by **measured `ncpl × required_uncapped_nstp`**, because *"the proxy
selects; it does not measure."* This is that pilot.

**Provenance, as §1.2 requires:**

| | |
|---|---|
| roster (`doublet_table.csv`) | `d5296ece7554f6cf635a8204b29ef487ff93270e036083385fbb3db922ceba7b` |
| transport config | `c99b603784a911e9fb1eefe9bf33895410ff94f60a07dd4903f28bfc9611f4aa` |
| `H` (Mac → Hub) | **2.169**, five pairs / ten sides, `HUB_MEASUREMENT_2026-08-31.md` |
| thresholds | `HUB_FINE_TARGET_S` 600 · `HUB_FINE_CEILING_S` 900 (`T0_0…` §6) |

⚠️ **This roster is the NINE-case one.** `T0_5…` §1.2 states the roster is going from nine to
ten, and that adding a case **re-opens both the proxy and the pilot**. This ranking is bound to
the hash above and expires when the tenth case lands.

---

## 1. 🔴 The pilot OVERTURNS the proxy — `b010236`, not `b010227`

All nine ran **uncapped** (`cr` ≈ 0.90, `cr_capped: false`), so these are measurements, not
floors.

| rank | grp | concession | horizon | `ncpl` | `nstp` | **W** | radius | Mac | Hub (×2.169) | verdict |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| **1** | **3** | **`b010236`** | 730 | 4755 | **3050** | **14,502,750** | 70 | 231.8 s | **503 s** | ✅ clean |
| 2 | 4 | `b010120` | 730 | 4884 | 2435 | 11,892,540 | 70 | 153.3 s | 333 s | ✅ clean |
| 3 | 6 | `b010227` | 1095 | 4736 | 2356 | 11,158,016 | 70 | 183.3 s | 398 s | ✅ clean |
| 4 | 7 | `b010213` | 730 | 4302 | 1554 | 6,685,308 | 70 | 103.0 s | 223 s | ✅ clean |
| 5 | 2 | `b010201` | 60 | 4508 | 507 | 2,285,556 | 62 | 46.2 s | 100 s | ✅ clean |
| 6 | 1 | `b010219` | 30 | 4462 | 223 | 995,026 | 70 | 25.1 s | 54 s | ✅ clean |
| 7 | 0 | `b010210` | 60 | 4512 | 90 | 406,080 | 70 | 15.3 s | 33 s | ✅ clean |
| 8 | 5 | `b010223` | 30 | 4120 | 65 | 267,800 | 70 | 8.7 s | 19 s | ✅ clean |
| 9 | 8 | `b010207` | 60 | 4512 | 56 | 252,672 | 70 | 10.0 s | 22 s | ✅ clean |

**`b010236` leads by 1.22×.** The proxy put it **third**.

### 1.1 Why the proxy was wrong, and it is the same error twice

`T0_5…` §1.1 ranks by `spill_to_extraction_distance × simulation_horizon_days`, giving
`b010227` **274,126 — 2.75× the runner-up**. Measured, `b010227` is third.

The proxy over-weights the **horizon**. `b010236` has the *shorter* horizon (730 d against
1095 d) but needs **3050 steps against 2356**, because step demand is set by
`total_time × max(v/ds)` — and its velocity field is faster. Corridor length and horizon are
both real cost factors, but they are not the only ones, and the margin the proxy reported
(2.75×) was **not** wide enough to survive the one it omitted.

🔴 **This is the second time a static proxy has mis-ranked this roster.** v1 of `T0_5…` ranked
by well separation and named `b010210` — which is the **eighth** cheapest of nine here. §1.1
already recorded that lesson: *"the same failure as the demo-as-proxy trap it was written to
avoid."* The corrected proxy is better — third instead of eighth — but still wrong, which is
exactly why §1.2 mandates the pilot rather than trusting the ranking.

### 1.2 🔴 This is a declared failure edge to T0.5, and it needs a SIGNATURE

§1.2, verbatim:

> **If the pilot ranks a different identity first, that identity becomes the probe** and this
> section takes a **failure edge to T0.5**. It is not a silent substitution.

**Proposed, pending lecturer signature:**

> The feasibility probe becomes **`b010236` (group 3)**, ranked first by measured
> `ncpl × uncapped nstp` = 14,502,750 over the nine-case roster
> `d5296ece7554f6cf635a8204b29ef487ff93270e036083385fbb3db922ceba7b`.

`T0_5…` §1.1's frozen rule is **not** edited by this file. The rule selected `b010227`
correctly *by its own terms*; what the pilot establishes is that the rule's output is not the
most expensive identity. Both readings — re-name the probe, or amend the selection rule so it
accounts for step demand — are the lecturer's, not mine.

---

## 2. ✅ The predeclared feasibility risk does NOT materialise

`T0_5…` §2 records *"a predeclared risk that the mandatory per-group fine run may be
unaffordable."*

| | |
|---|---|
| worst measured identity | **503 s** (`b010236`) |
| `HUB_FINE_TARGET_S` | 600 s — **cleared** |
| `HUB_FINE_CEILING_S` | 900 s — cleared by 44% |
| groups that build | **9 of 9**, all uncapped |

**Every group passes cleanly, and the verdict does not depend on which identity is named the
probe** — second and third place are 333 s and 398 s. T2 does not take the §2 failure edge.

⚠️ **This supersedes the withdrawn `316 × 2.30 = 728 s` projection** (`T0_0…` §6). That figure
was a *lower bound* from a capped run; these are uncapped measurements of the actual
case-study identities, which is what §2 asked for.

---

## 3. What the pilot found on the way — two groups could not build at all

Neither was visible before, because nothing had run all nine since the transport track
changed.

| grp | failure | cause | fixed by |
|---|---|---|---|
| **4** | transport solution will not converge, 3 s, deterministic | the student track never received **A17**'s `MODERATE`→`COMPLEX` preconditioner; `transport_srcpulse_demo` got it, `transport_base_model` did not | **C1 A18**, PR #167 |
| **1** | corridor refinement fails at **all five** radii | the spill sat **10.5 m** from the model boundary; refinement circles are 56–84 m, so none fits, and the 40 m pad put one centre 29.5 m **outside** the domain | spill moved to a bearing that clears (wells unchanged), PR #168 |

🔴 **Both were student-facing and total** — those two groups could not produce any result.
They are the reason `T0_5…` §1.2 mandates running the roster rather than reasoning about it.

---

## 4. The cost model, validated twice more

`T2_steps.md` §1.1's model, `wall = 14.4168 µs · W + 6.66 s`, fitted on `W` up to ~1.44 M:

| point | `W` | extrapolation | predicted | measured | error |
|---|---:|---:|---:|---:|---:|
| 1 m series | 3.36e8 | 233× | 4 850 s | 5 756 s | **−16%** (bound 7 563 s **held**) |
| group 6 | 1.12e7 | 7.7× | 167.5 s | 161.4 s | **+3.8%** |

The point estimate is good to a few percent at ~8× and low by 16% at 233×, with the declared
conservative bound holding in both. **That is the validation `T2_steps.md` §1.2's
recalibration gate existed to obtain** — at a far larger stretch than the 5 m point it
proposed.

---

## 5. Status

| | |
|---|---|
| S8 pricing (probe) | ✅ **done — measured, not predicted.** 503 s, clean pass |
| S9 the probe run | ⚠️ **arguably already satisfied** — the probe identity ran uncapped here; what remains is the cold/warm Hub protocol of `T0_5…` §3 |
| probe identity | 🔴 **awaiting lecturer signature** (§1.2 above) |
| roster | ⚠️ ranking expires when the tenth case lands |
