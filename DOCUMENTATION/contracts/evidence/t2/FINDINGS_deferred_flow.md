# Two findings recorded and deliberately NOT acted on (2026-09-03)

Both are real. Both were left alone to get the case study to students with minimal
change, and are logged here so they are not lost.

## 1. The locality assertion tests ONE cell, so it is close to a coin flip

`feature_local` asks whether the **argmax** |Δh| cell lies within `locality_dist_m`
(500 m) of the feature. For a near-uniform response the argmax is essentially
arbitrary, so the test can pass or fail by accident. Measured, same scenario type,
factors inverted:

| | group 6 | group 11 |
|---|---|---|
| cells within 10 % of max | 4647/4883 = **95 %** | 3991/4194 = **95 %** |
| median distance to river | **582 m** | **581 m** |
| within 500 m of the river | 40 % | 45 % |
| **argmax** distance to river | **0 m** → PASSED | **1034 m** → FAILED |

Statistically identical responses; opposite verdicts. Group 6 passed by luck.

**Suggested fix (not made):** make the assertion distributional -- median distance
of responding cells, or the fraction of the response within X m. That changes
behaviour for every `feature_local` group (0, 6, 11), which is why it was not done
before students.

## 2. River conductance may be high enough that the river controls the whole valley

Total RIV conductance **150,332 m²/d** against a median transmissivity of
**3,818 m²/d**. Empirically, changing the river moves **95 % of the domain** -- both
`river_width_and_stage` groups shift the entire head field rather than a near-river
fringe, which is why both are now classified `global`.

Whether that conductance is *too high* is a calibration question this note does not
answer. ⚠️ It was not touched because changing it moves every head in every group:
all 13 flow goldens, every case-study number, and the transport results computed on
top of them. That is a deliberate investigation, not a pre-semester edit.

⚠️ A crude "leakage length" estimate was attempted and DISCARDED -- it required
assuming a reach area and produced a number (~95 m) that contradicted the measured
domain-wide response. The 95 %-of-cells measurement is the evidence; the analytical
estimate was not sound enough to report.

---

## Orphaned checkpoint questions — DEFERRED to a careful review pass (2026-09-03)

**Lecturer decision, 2026-09-03: delete nothing. A separate careful review pass will
decide each one.**

15 checkpoint keys in `tasks_data.py` are defined but rendered by no notebook. Counting
them requires following the helper indirection: a first pass that scanned notebooks only
reported 16 and was WRONG — `task03_3` is live via `darcy_law_experiment.darcy_task_1_3()`,
which `01f_model_goal.ipynb` calls. Scan notebooks AND `scripts_exercises/*.py`, then check
whether the wrapping helper is itself called.

**10 transport-track** (`task_t04_checkpoint_2` + nine `task_t05_*` except
`task_t05_checkpoint_1`). Orphaned by the 2026-06-29 solute rewrite (`d03b06d`). Genuinely
dead: `task_t05_checkpoint_best_alpha` asks which α_L gave the lowest *temperature* RMSE
against a track that computes no temperature. C1 **A9** authorises retiring these, but
Part 3 is inert until the JAG, so retiring them early needs an explicit lecturer
authorisation line the way A17/A18/A19 got one. This count matches C1 §1.1's own audit.

**5 flow-track** (`task01_2`, `task03_2`, `task03_4`, `task03_conductance`, `task04_2`).
🔴 **NOT junk, and NOT covered by any contract audit.** They are sound exercises —
aquifer volume from residence time, Darcy discharge, K from a graph, conductance
`C = K·A/L`, water-table level. Deleting them would discard usable teaching material;
the conductance one is directly on-topic for a MODFLOW course.

⚠️ **Two look ACCIDENTALLY DROPPED, not retired.** `darcy_task_1_3()` displays
"Analyze the results and answer the following question**s**" — plural — then renders
exactly ONE checkpoint (`task03_3`). `task03_4` is headed "Task 1.3 … your estimate for
the hydraulic conductivity K" and refers to "the experiment's graph", which is what
`darcy_task_1_2()` draws. `task03_2` ("discharge Q in mm/s") plausibly belongs to the same
set. This is inferred from wording, not from a commit that removed a call — the review
pass should confirm against history before acting.
