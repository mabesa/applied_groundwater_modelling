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

## ✅ The structural hole — CLOSED 2026-08-28 (lecturer: *"fix it, it's in scope"*)

**The goldens pin their outputs to 12 significant digits while their single largest input is
unpinned and unverified.** Manifests record `numpy`, `flopy`, `geos`, `python`, `mf6` and the
kernel — and **no hash of the mother model**.

All three follow-ups are implemented.

### 1 · `ensure_flow_model` now verifies what it returns

The infrastructure already existed and was simply never wired: `flow_model_fingerprint()`'s own
docstring says it is *"used to … **(b) detect a stale/mismatched local workspace in
`ensure_flow_model`**"* — and `ensure_flow_model` never called it. It checked only
`archive_version`, which `stamp_flow_manifest()` deliberately lets a local 05f output satisfy.

- **`CANONICAL_FLOW_FINGERPRINT = "6a9e27c455dcbb66"`** pins the shipped archive.
- **`verify_flow_model(ws)`** reports two independent things — `manifest_consistent` (files vs
  their own manifest: catches partial extraction) and `is_canonical` (files vs the shipped
  archive: catches a local variant). It **reports**; it never raises.
- **Default is a WARNING**, not a failure, so a deliberate local calibration
  (`RUN_PEST_LOCALLY=True`) stays usable — that workflow is legitimate and must not break.
- **`require_canonical=True` REFUSES**, and the golden-pinned walk in
  `casestudy_flow_builder._refine_solve_baseline_walk` now passes it. A local variant is rejected
  *at the point the calibration is loaded*, naming the calibration — instead of surfacing later
  as "the built grid DIVERGED".
- **`AGM_ALLOW_LOCAL_FLOW_MODEL=1`** silences the warning; it does **not** relax the refusal.
- A **freshly downloaded** archive that is non-canonical **raises unconditionally** — that means
  the shipped artifact and the constant disagree, and every golden is suspect.

### 2 · Golden manifests now record the calibration they were built from

`_golden_versions()` records `flow_model_fingerprint`. ⚠️ **Goldens frozen before 2026-08-28 do
not carry it**, so `check_nine_mesh_goldens.py` reports that as *unknown* rather than agreement,
and prints the current calibration fingerprint plus the tell-tale signature when a run fails.
Absence must never read as "fine".

### 3 · The pin's error message no longer blames the grid

`_pin_built_grid_to_frozen_golden` now appends, when the calibration is not canonical:

> 🔴 **LIKELY CAUSE:** the calibrated flow model this was built from is NOT the shipped one
> (fingerprint … != …). The goldens were frozen on the shipped calibration, so no grid built on a
> different one can match.

### Tests

`_SUPPORT/tests/test_flow_model_provenance.py` — 8 tests, including the negative controls that
matter: drift **warns** by default, drift is **refused** under `require_canonical`, the opt-out
silences the warning but **not** the refusal, the message names cause *and* remedy, and the
golden-pinned walk is asserted to require the canonical model.

## Also fixed along the way

- `check_nine_mesh_goldens.py` reports **`ENV_MISMATCH`** as its own outcome (never PASS, never
  FAIL) when recorded library versions differ — this is what killed hypothesis 2 in one step.
- The member-level diff must build at **`manifest["radius_used"]`**: five goldens are radius
  **62**, not the default 70, and comparing a 70-build against a 62-golden reports *every* member
  differing — an artefact that briefly looked like a catastrophic regression. Regression tests
  over all five radius-62 goldens now guard it.
- `botm`/`top` are classified as **cell properties**, not topology; an earlier version printed
  "mesh intact: False" for an intact mesh.
