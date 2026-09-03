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
