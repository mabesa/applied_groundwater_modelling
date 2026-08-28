# ✅ ROOT CAUSE — a drifted local mother model, served unverified

**Settled 2026-08-28. S3b is UNBLOCKED.**

```
[PASS] group 0..8   (hashes ENFORCED)
9 passed, 0 failed, 0 inconclusive (environment), of 9 groups
mesh-topology hashes enforced on 9/9 groups
```

The goldens were correct. The code was correct. The libraries, once synced, were correct.
**The Hub's local copy of the mother model had drifted from the published artifact.**

## The mechanism

`model_io_utils.ensure_flow_model()` resolves the calibrated mother model like this:

> 1. If the simulation is already present locally → **return it (no download)**
> 2. Otherwise download `flow_model_mf6` and extract

🔴 **Step 1 performs no verification of any kind.** And `05f_calibration.ipynb` regenerates that
same workspace — `<data>/limmat/calibration`, where cell 6 does `rmtree` + `copytree`. So running
the calibration notebook **overwrites the downloaded frozen model with a locally recalibrated
one**, and every later caller silently inherits it, indefinitely.

## The proof

| | `botm` hash | |
|---|---|---|
| Mac (reproduces the goldens) | `145effba3ba79799` | |
| **Hub, local copy** | **`07eb1dc11896f126`** | 🔴 drifted |
| Hub, after rename + re-download | `145effba3ba79799` | ✅ matches |

`top` was byte-identical throughout, `ncpl` (4845) never moved, and `botm`'s min/max were
unchanged (351.920999 / 406.718750) — **only per-cell values drifted.** That is why the signature
was so narrow: refined `botm` is interpolated from the mother model and `strt` follows it through
`strt = max(strt, botm + 0.01)`, so every group failed with exactly

```
topology intact: True | topology: none | cell-properties: ['botm', 'strt'] | packages: none
```

**Recovery:** rename `<data>/limmat/calibration` and let `ensure_flow_model` re-download.

## 🔴 It crashed students, not just tests

```
PROJECT/workspace/template/case_study_flow_group_N.ipynb
  -> cfb.build_all_flow_states -> _refine_solve_baseline_walk
    -> _pin_built_grid_to_frozen_golden  -> RuntimeError
```

Any student whose Hub account had a drifted calibration copy could not build the flow case study
**at all**, on any of the nine groups — with an error message pointing at the *grid*, while the
cause was a *data file*.

## Three hypotheses were refuted first — recorded so they are not re-walked

| # | Hypothesis | How it died |
|---|---|---|
| 1 | `fe0cc4b`, the botm-floor fallback ("output-neutral") | `riv_rbot` appears in **no** group's member-level diff; `casestudy_flow_common:229` leaves `botm` unchanged. *"Output-neutral" was accurate.* |
| 2 | Library drift (numpy 2.1.3 / flopy 3.9.3 vs locked 2.3.5 / 3.9.5) | **Real, but not causal.** `uv sync` fixed the versions; the checker reported `0 inconclusive (environment)`; all nine still failed identically |
| 3 | Cross-platform Triangle mesh | Topology was **intact** on Linux — `topology: none` for every group |

⚠️ Each was well-evidenced. The one that survived did so because it was the only one carrying a
**falsifiable hash comparison**. The lesson is not "hypothesise less" but "make each hypothesis
produce a number that can disagree with you."

## 🔴 The structural hole this exposed — still OPEN

**The goldens pin their outputs to 12 significant digits while their single largest input is
unpinned and unverified.** Manifests record `numpy`, `flopy`, `geos`, `python`, `mf6` and the
kernel — and **no hash of the mother model**.

Three follow-ups, in priority order:

1. **`ensure_flow_model` must verify what it returns.** A hash check with a message like *"your
   local calibration copy has drifted from the published artifact — remove it and re-download"*
   converts this two-day hunt into one line of output. ⚠️ **Needs an authority decision**:
   `model_io_utils.py` is a C1 transitively-reached surface, and **A16 names it only for graded
   mesh construction**, which this is not.
2. **Record the mother-model hash in the golden manifests.** Same hole, one level up: a changed
   input would still be invisible to a golden.
3. **The pin's error message says "the built grid DIVERGED"** — it points at the model when the
   cause was data. It cost two days here and would cost a student their afternoon.

## Also fixed along the way

- `check_nine_mesh_goldens.py` reports **`ENV_MISMATCH`** as its own outcome (never PASS, never
  FAIL) when recorded library versions differ — this is what killed hypothesis 2 in one step.
- The member-level diff must build at **`manifest["radius_used"]`**: five goldens are radius
  **62**, not the default 70, and comparing a 70-build against a 62-golden reports *every* member
  differing — an artefact that briefly looked like a catastrophic regression. Regression tests
  over all five radius-62 goldens now guard it.
- `botm`/`top` are classified as **cell properties**, not topology; an earlier version printed
  "mesh intact: False" for an intact mesh.
