# Case-study model-diagnostic spec (M1.4)

The **human catalog** of the per-run **model** diagnostics for the student
case study. The machine/enforcement contract is
[`casestudy_diagnostic_schema.yaml`](./casestudy_diagnostic_schema.yaml); the
loader + linter + evaluator is
[`casestudy_diagnostics.py`](./casestudy_diagnostics.py). This spec and the
schema are kept in lock-step: the diagnostic ids here are exactly the ids in
the schema (a test asserts it).

Defined **up front (M1.4)** so the builders implement diagnostics rather than
bolt them on: **M2a/M3a/M3b emit**, **M3c/M4/M5/M8 enforce as gates**, and
**M6 surfaces** to students.

## Environment-vs-model boundary

There are two distinct diagnostic layers, and this spec is only about the
second:

- **Environment / import / smoke** diagnostics live in
  [`diagnostics.py`](./diagnostics.py) (the `0_diagnostics.ipynb` checks:
  package imports, capability probes, workspace write-tests). They answer *"is
  the toolchain usable?"* and are **not** reclassified here.
- **Per-run model** diagnostics (this spec) answer *"is THIS flow/transport/PRT
  run correct and accurate?"* They are computed by the model builders and
  written to a per-run **`diagnostics.json`** in the case workspace.

## Common reporting surface — `diagnostics.json`

Every model run writes a `diagnostics.json` into its case workspace with
top-level shape (one object per diagnostic id):

```json
{
  "<diagnostic_id>": {
    "value": <num|bool|null>,
    "aggregation": "<max|p95|cumulative|per_step|scalar>",
    "unit": "<str>",
    "warn_threshold": <num|null>,
    "raise_threshold": <num|null>,
    "reference": <num|null>,
    "triggered_severity": "pass|warn|raise",
    "passed": <bool>
  }
}
```

`triggered_severity` is the band actually hit at run time (`pass` = within
bounds); `passed = (triggered_severity != "raise")`. This mirrors the schema
exactly — there is **no ambiguous singular `threshold`/`severity`**. Builders
must emit via `casestudy_diagnostics.evaluate(id, value)` so `triggered_severity`
and `passed` are computed identically from the schema bands. M3c/M4/M5/M8 read
this file to gate; M6 surfaces it to students.

**Emitted `raise_threshold` is the EFFECTIVE band.** For a relative-threshold
diagnostic (`raise_threshold_relative: true`, e.g. `concentration_nonnegative`),
`raise_threshold` is emitted already scaled by the run-time `reference` (e.g.
`−0.01 × peak`) and `reference` records the value used, so the reported band is
exactly what was applied. `evaluate()` **requires a positive `reference`** for
such a diagnostic (no silent fallback to the raw fraction). `reference` is
`null` for non-relative diagnostics.

**Boolean & null semantics.** Boolean diagnostics (`finite`, `eq ==True`) are
evaluated boolean-aware **before** any float coercion — `True → pass`,
`False → raise` — so a `finite=False` broken-solve flag can never silently pass
(`float(False) == 0.0` is finite). A `nullable` diagnostic that did not run for
this run (no baseline / non-PRT) emits `value: null`, `triggered_severity:
"pass"`, `passed: true`; a `null` value on a non-nullable diagnostic is an
error.

## Schema entry shape

Each `diagnostic_schema.yaml` entry carries **all** of:
`id` · `metric` · `input_artifact:{file,field,shape,unit}` ·
`aggregation` (max|p95|cumulative|per_step|scalar) ·
`comparator` (le|ge|eq|in|finite) ·
`warn_threshold`/`raise_threshold` (num|null — the pass/warn/raise bands) ·
`numeric_tol` + `abs_tol` (num|null — near-zero floor) ·
`severity` (raise|warn — the **max** configured band) ·
`owner` (M2a|M3a|M3b) · `enforced` (now|M3c|M4|M5|M8) ·
`output:{path,json_key,type,nullable}` · `justification`.

**Severity split (enforced by the schema-lint and the acceptance):** every
**correctness** check is `raise`; every **accuracy/quality** check is `warn`.
Band convention: `le` lower-is-better, `ge` higher-is-better,
`eq`/`finite`/`in` are structural (the comparator is the gate). A raise band
tagged `raise_threshold_relative: true` is a fraction of a run-time reference
(e.g. peak concentration).

---

## Catalog

### FLOW — owner M2a

- **`flow_convergence`** *(raise, now)* — the GWF solver reported normal
  termination (all outer iterations met `dvclose`/`hclose`). Input: MF6
  `mfsim.lst`/`gwf.lst` success flag (scalar bool). `== True`. An unconverged
  flow solution invalidates every downstream number.
- **`flow_mass_balance`** *(raise, now)* — `|percent discrepancy|` of the GWF
  budget, **cumulative**; denominator = total flux through the model, with an
  **absolute tol** (`abs_tol = 1e-6`) when total flux ≈ 0 so the ratio does not
  degenerate. Input: `gwf.lst` `PERCENT_DISCREPANCY`. `< 1%`. A larger
  discrepancy means the flow solution is not mass-conservative.
- **`finite_heads`** *(raise, now)* — no NaN/Inf anywhere in the head array
  `(nlay, ncpl)` [m]. A non-finite head is a broken solve.
- **`flow_no_dry_cells`** *(raise, now)* — count of **dry active** cells (head ≤
  cell bottom / HDRY where `idomain > 0`). `== 0`. A dry active cell is a locally
  invalid flow field for a saturated-aquifer model.
- **`flow_head_delta`** *(warn, M4)* — max active-cell `|head − baseline_head|`
  vs the 05f baseline field [m]. `≤ 5 m` (coarse physical-plausibility band for
  these local scenarios; tunable). A large local delta warrants review, not an
  auto-fail — enforced at M4 when the scenario is re-validated. `nullable` (no
  band when the baseline is unavailable).

### TRANSPORT — owner M3a

- **`transport_convergence`** *(raise, now)* — the GWT solver met `dvclose`
  (MF6 listing). `== True`. An unconverged transport solve invalidates the
  plume/breakthrough.
- **`transport_mass_balance`** *(raise, now)* — `|percent discrepancy|` of the
  GWT mass budget, **cumulative**: SRC in vs well/boundary out vs
  storage/decay; denominator = released mass; `abs_tol` near-zero. Input:
  `gwt.lst` (`src_in_g`, `well_out_g`, `boundary_out_g`, `storage_g`,
  `PERCENT_DISCREPANCY`). `< 1%`. A larger discrepancy means solute mass is
  created/lost.
- **`finite_conc`** *(raise, now)* — no NaN/Inf in the concentration, velocity
  (SPDIS `qx,qy`), or mass-budget arrays.
- **`concentration_nonnegative`** *(raise, now)* — min concentration over the
  run [mg/L], comparator `ge` (multi-band): **pass** if `min ≥ −1e-6` (solver
  noise); **warn** if `−1e-6 > min ≥ −1% of peak`; **raise** if
  `min < −1% of peak`. The raise band is relative
  (`raise_threshold_relative: true`, fraction of peak). Small negatives are
  tolerated noise; a large negative is an oscillation/mass error.
- **`src_units`** *(raise, now)* — relative error of
  `|smassrate − mass_g / (n_src · pulse_days)| / smassrate` (mg/L = g/m³ ⇒ SRC
  loading in g/d). `== 0` within tol. A g/d-vs-mg/L unit error is a ~1000×
  mass error, so it must match the SRC formula exactly. Emitter:
  `smassrate_gpd` (`transport_srcpulse_demo.py`).
- **`source_in_domain`** *(raise, now)* — all SRC cells are active + inside the
  transport domain, set in the correct stress period, with the expected count
  (single all-true flag). A source in an inactive cell or wrong period injects
  no/incorrect mass.
- **`grid_peclet`** *(warn, M3c)* — `Pe_L = Δs / α_L` over the corridor cells
  (dimensionless), aggregated as **p95** (and max). `≤ 2`. **Quality, not
  correctness**: MF6 GWT TVD advection tolerates `Pe_L > 2` with added
  numerical dispersion — an accuracy flag. Emitter: `PeL_min`/`PeL_max`.
- **`courant`** *(warn, M3c)* — `Cr = v · Δt / Δs` over the corridor cells,
  **p95** (and max). `≤ 1`. **Quality**: MF6 GWT is an **implicit** solver, so
  `Cr > 1` is not stability-fatal — an accuracy flag. Emitter:
  `_courant_nstp`.
- **`capture_stability`** *(warn, M3c)* — `|Δ capture_fraction|` under a
  probe-radius perturbation of **± one refined-cell step** (tied to
  `refined_cell_size`, **not** an arbitrary 40 m). `< 0.05` (5 pp). This is
  **diagnostic-stability** — whether the capture *measurement* is stable —
  **distinct from** whether the capture *result* is good. The M1.5
  artifact-stability structural gate. Emitter: `capture_fraction` /
  `max_captured_offset_m` (`transport_prt_capture.py`). `nullable` (PRT-only).
- **`capture_fraction_bounds`** *(raise, now)* — the emitted `capture_fraction`
  is a valid fraction `∈ [0, 1]` (comparator `in`). A value outside `[0,1]` is a
  computation bug (`n_captured / n_released`). `nullable` (PRT-only).

### COUPLING — owner M3b

- **`coupled_or_fallback_label`** *(raise, now)* — the run records a coupling
  label `∈ {coupled-student-flow, known-good-wells-only}`, correctly set to the
  flow field actually consumed (single valid-and-present flag). A silent
  fallback to canned wells-only flow would mislead.
- **`coupling_artifact_identity`** *(raise, now)* — the run records the **exact
  flow-artifact hash / run-id** it consumed (non-null), not just the label. An
  absent hash makes the run unauditable.
- **`well_sink_mapping`** *(raise, now)* — the extraction/PRT wells the
  transport/PRT run uses **match the flow wells** by id/location/layer/rate/
  stress-period (exact, single all-match flag). If transport pumps different
  wells than flow, the capture field is inconsistent with the flow field.

### CROSS-CUTTING

- **`time_unit_consistency`** *(raise, now; owner M3a)* — flow, transport,
  source pulse, velocities, and budgets all use consistent time/mass/length
  units (**days / g / m**) (single all-consistent flag). A units mismatch
  silently corrupts every rate, velocity, and mass number.

---

## Owner / severity / enforced map

| diagnostic | owner | severity | warn | raise | enforced |
|---|---|---|---|---|---|
| flow_convergence | M2a | raise | — | ==True | now |
| flow_mass_balance | M2a | raise | — | 1.0 % | now |
| finite_heads | M2a | raise | — | finite | now |
| flow_no_dry_cells | M2a | raise | — | 0 | now |
| flow_head_delta | M2a | warn | 5.0 m | — | M4 |
| transport_convergence | M3a | raise | — | ==True | now |
| transport_mass_balance | M3a | raise | — | 1.0 % | now |
| finite_conc | M3a | raise | — | finite | now |
| concentration_nonnegative | M3a | raise | −1e-6 | −1 % peak | now |
| src_units | M3a | raise | — | 0 (±tol) | now |
| source_in_domain | M3a | raise | — | all-true | now |
| grid_peclet | M3a | warn | 2.0 | — | M3c |
| courant | M3a | warn | 1.0 | — | M3c |
| capture_stability | M3a | warn | 0.05 | — | M3c |
| capture_fraction_bounds | M3a | raise | — | ∈[0,1] | now |
| coupled_or_fallback_label | M3b | raise | — | valid label | now |
| coupling_artifact_identity | M3b | raise | — | present | now |
| well_sink_mapping | M3b | raise | — | exact match | now |
| time_unit_consistency | M3a | raise | — | consistent | now |

**Structural gates M1 must define — all present above:** mass balance
(`flow_mass_balance`, `transport_mass_balance`), the capture/artifact-stability
test (`capture_stability`, `capture_fraction_bounds`), and the
coupled-vs-fallback label (`coupled_or_fallback_label`,
`coupling_artifact_identity`, `well_sink_mapping`). Existing emitters are
referenced by name (`PeL_*`, `Cr` via `_courant_nstp`, the SRC formula
`smassrate`, `capture_fraction`).
