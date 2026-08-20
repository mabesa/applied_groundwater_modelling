# T0.0 — Canonical Default Contract Freeze

**Milestone:** T0.0 of `transport_notebook_milestones.md` (READY v7).
**Status:** **DRAFT v2 — awaiting the named, dated lecturer approval in §7.**
v2 folds all nine findings of codex review round 1 (**BLOCK**, 2026-08-20) —
`DESIGN_DOCS/codex_reviews/T0/t0_round1_out.md`. Every one was verified against the code before acceptance.
**Blocks:** every T1 source edit. No edit to `transport_srcpulse_demo.py`, `transport_prt_capture.py`,
`transport_base_model.py` or `model_io_utils.py` may begin until §7 is signed.
**Governs:** (a) the canonical default-preservation gate in T1 and (b) the Hub feasibility thresholds of
§6, which the parent plan assigns to T0.0 item 4 and whose *ownership and probe identity* belong to T0.5.
Nothing else. It is not a teaching document.
*(codex r1 #9: v1 said "and nothing else" while §6 froze T2 and case-study runtime policy — an internal
contradiction. The scope statement is widened rather than §6 moved, because the parent plan puts the
threshold here.)*

> **Why this exists.** T1 must edit the very modules the live teaching path imports
> (`04t_model_implementation.ipynb:73`, `08t_model_application.ipynb:82`). The only honest way to claim
> "the student-facing default did not move" is to fix — *before* any edit, while the effect is still
> unknown — exactly what is compared and exactly how it is rounded. Choosing either afterwards is
> choosing the answer.

---

## 1. The exact invocation

**The canonical default identity is `build_srcpulse_demo()` at its declared SEMANTIC defaults, plus two
gate-only controls** (`force` and `case_ws`, which exist to defeat caching and are not physics), from
`_SUPPORT/src/transport_srcpulse_demo.py:532`. *(codex r1 #9: "every argument at its declared default" was
false, since the gate overrides exactly those two.)*

| Argument | Frozen value | Note |
|---|---|---|
| `mass_g` | `3.0e5` | |
| `pulse_days` | `30.0` | |
| `total_days` | `120.0` | |
| `solubility_mgL` | `1000.0` | |
| `alpha_L` | `None` | resolves to `LOCKED_PARAMS["alh"] = 10.0`; the payload records the **effective** `10.0`, never `None` |
| `R` | `1.0` | conservative — no MST sorption args passed at all |
| `rho_b` | `1800.0` | inert while `R == 1.0` |
| `lam` | `0.0` | no decay |
| `cr_target` | `0.9` | |
| `nstp_cap` | `2000` | |
| `refine_radii` | `(70.0, 62.0, 78.0, 56.0, 84.0)` | the SIGILL retry ladder, in this order |
| `force` | **`True`** | see §1.2 — belt-and-braces against a warm cache |
| `case_ws` | **a fresh, non-existent directory, one per side** | see §1.2 |

**`sink_support_m` is added at its identity default `0.0` once T1 introduces it — see §3.**

### 1.1 The flow input is part of the identity

`build_srcpulse_demo` loads the 05f-calibrated coarse Limmat GWF (`load_limmat_flow`, `:328`) and folds a
fingerprint of that **downloaded flow data** into the cache identity (`:660`ff). **Both sides of the
comparison must read the same data folder, at the same content fingerprint.** The recalibration of
2026-07-24 (1,080 → 2,160 m³/d) changed the flow field without touching `_src_sha()`; a differential run
across that boundary would be meaningless. Record the flow fingerprint on both sides and assert equality
before comparing anything else.

🔴 **And the flow fingerprint does NOT cover the GIS that shapes the mesh** *(codex r1 #4, verified)*.
`_load_calibrated_flow` separately downloads `model_boundary` and `rivers` (`:290–293`), and both feed
corridor refinement — so a GIS change moves the mesh while the flow fingerprint stays put. **The harness
hashes the boundary and river files too** (§5.0).

### 1.2 Cold-workspace policy — **no warm cache may serve either side**

- Each side runs in its **own freshly created, previously non-existent** `case_ws`. Never the shared
  default `<data>/transport_srcpulse_demo` (`_default_case_ws()`, `:297`), and never the same directory
  twice.
- `force=True` is additionally passed, so `_load_cache` (`:931`) cannot serve a result even if a stale
  artifact were somehow present.
- The two workspaces are **not** deleted after the run — they are the evidence.
- 🔴 **A warm-cache hit on either side voids the gate.** It is a re-run of the gate, not a pass.

### 1.3 Both sides, one environment

One machine, one OS/arch, one MF6 binary, one FloPy, one Python, one data folder — **the only permitted
difference is the repo commit**: `b685f24` (the frozen reference) versus the T1 candidate. A digest
recorded on any other machine is informational and **cannot** discharge the gate (T1, "secondary form").

---

## 2. The canonical payload — defined EXACTLY ONCE, here

**The payload is the ENTIRE public surface of the `SrcPulseDemo` dataclass**
(`transport_srcpulse_demo.py:88–119`). Not a curated selection: a curated list was tried twice and was too
narrow both times (codex r4/r5), missing fields that drive student-visible `08t` behaviour.

**Rule of construction:** the payload is *every field of the dataclass that does not begin with an
underscore*, enumerated by reflection, not by hand. A test asserts the enumerated payload covers every
public field, so a **new** field fails the gate rather than escaping it.

### 2.1 Top-level fields (29)

| Field | Type | Normalisation class (§4) |
|---|---|---|
| `times` | `np.ndarray[float]` | `ARRAY_FLOAT` |
| `breakthrough` | `np.ndarray[float]` | `ARRAY_FLOAT` |
| `peak_mgL` | `float` | `FLOAT` |
| `arrival_day` | `float` | `FLOAT` — ⚠️ this is **time of peak**, not first arrival (`:94`); T0.2 owns the rename-or-alias decision |
| `mass_balance` | `Dict[str, float]` | `MAPPING` → §2.2 |
| `solubility_ok` | `bool` | `BOOL` |
| `emergent_C_mgL` | `float` | `FLOAT` |
| `solubility_mgL` | `float` | `FLOAT` |
| `solubility_margin` | `float` | `FLOAT` |
| `PeL_min` | `float` | `FLOAT` |
| `PeL_max` | `float` | `FLOAT` |
| `PeT_min` | `float` | `FLOAT` |
| `PeT_max` | `float` | `FLOAT` |
| `mass_g` | `float` | `FLOAT` |
| `pulse_days` | `float` | `FLOAT` |
| `total_days` | `float` | `FLOAT` |
| `smassrate_gpd` | `float` | `FLOAT` |
| `src_cells` | `List[int]` | `ARRAY_INT` |
| `ext_cell` | `int` | `INT` |
| `inj_cell` | `int` | `INT` |
| `spill_xy` | `Tuple[float, float]` | `ARRAY_FLOAT` |
| `alpha_L` | `float` | `FLOAT` |
| `alpha_T` | `float` | `FLOAT` — drives `08t` (`:202,209,275`) |
| `R` | `float` | `FLOAT` |
| `rho_b` | `float` | `FLOAT` |
| `Kd` | `float` | `FLOAT` — drives `08t` |
| `lam` | `float` | `FLOAT` — drives `08t` |
| `meta` | `Dict[str, Any]` | `MAPPING` → §2.3 |
| `locked` | `Dict[str, Any]` | `MAPPING` → §2.4 |

### 2.2 `mass_balance` — the nine keys (`:900`), and the tenth that must abort the gate

`src_in_g` · `well_out_g` · `boundary_out_g` · `storage_g` · `decay_g` · `total_in_g` · `total_out_g` ·
`pct_imbalance` · `grouped_residual_g` — all `FLOAT`.
⚠️ `pct_imbalance` is `NaN` when the denominator is zero (`:891`) → the `NaN` sentinel of §4.3, which is a
**legitimate value**, never a skip.

🔴 **There is a TENTH key on the error path, and v1 missed it** *(codex r1 #1, verified)*. When the budget
read raises, `_mass_balance` returns the nine numeric keys as `NaN` **plus a string-valued `"error"`**
(`:835`), and that string is `repr(e)` — which **can contain the workspace path**, directly contradicting
§4.4's claim that no payload field carries one.

**Rule:** a **valid canonical result has EXACTLY the nine numeric keys.** If `"error"` is present, or the
keyset differs in any way, the **gate ABORTS** — it does not compare, does not normalise, and does not
record a result. A failed budget read is a broken run, not a payload difference.

### 2.2b Keyset assertions are nested, not top-level

Top-level dataclass reflection (§2) does not see inside `mass_balance`, `meta` or `locked`. **Each nested
mapping is asserted against its exact frozen keyset** — nine, seventeen and nine keys respectively — so a
key appearing or vanishing inside one of them fails the gate instead of passing through it.

### 2.3 `meta` — the seventeen keys (`:769–774`)

`ncpl`(`INT`) · `nstp`(`INT`) · `dt`(`FLOAT`) · `Cr`(`FLOAT`) · `n_src`(`INT`) · `q_src_darcy`(`FLOAT`) ·
`b_src`(`FLOAT`) · `ds_src`(`FLOAT`) · `q_cell`(`FLOAT`) · `v_bind`(`FLOAT`) · `ds_bind`(`FLOAT`) ·
`ds_true_min`(`FLOAT`) · `courant_floor`(`FLOAT`) · `refine_radius_used`(`FLOAT`) · `u_reg`(`ARRAY_FLOAT`) ·
`cr_capped`(`BOOL`) · **`peak_at_last_step`**(`BOOL`).

`peak_at_last_step` is the **horizon-censoring flag** and is explicitly in scope — it decides whether a
reported peak is a peak at all, and `08t` reads it.

### 2.4 `locked` — the full `LOCKED_PARAMS` snapshot (`:57`)

`alh` · `ath1` · `diffc` · `porosity` · `scheme`(`STR`) · `xt3d_off`(`BOOL`) · `refined_cell_size` ·
`base_cell_size` · `time_units`(`STR`); the rest `FLOAT`.
This is a **snapshot taken at construction** (`:119`), so it travels with the result and a LOCKED_PARAMS
edit is visible in the payload as well as in the cache key.

### 2.5 Amendment rule

**Adding, removing or renaming any public field, `meta` key, `mass_balance` key or `locked` key is a
payload change → failure edge to T0.** Not an in-flight edit. The single pre-authorised exception is §3.

---

## 3. Pre-authorised: the B-control support field

T0.4 (v7) funds **B-as-control**. It needs new public state, and §2.5 would otherwise make adding it a
failure edge back to here. It is therefore **named and frozen now**:

| Name | Type | Identity default | Meaning |
|---|---|---|---|
| `sink_support_m` | `float` | **`0.0`** | Radius [m] of the fixed physical extraction-support disc. `0.0` means **today's behaviour exactly**: the whole pumping rate on the single nearest-centroid cell (`:386`, `:453`). |
| `meta["sink_support_cells"]` | `List[Tuple[int, float]]` | **`[(ext_cell, -abs(DOUBLET_Q))]`** | The apportionment **actually applied**, `(cell_index, q_i)` pairs with `Σqᵢ = Q`. 🔴 **NOT `[]`** *(codex r1 #3, verified)*: today's applied support really is one cell carrying the whole rate (`:386`, `:453`, `DOUBLET_Q = 1370.0`). An empty list would be a **false record**, and because v1 then excluded the field from comparison, an implementation could report `[]` without ever proving which WEL support it used. |

**Normalisation:** `sink_support_m` is `FLOAT`; `meta["sink_support_cells"]` is `ARRAY_PAIR`
(`INT`, `FLOAT`), ordered by ascending `cell_index`.

### 3.1 🔴 Pre-authorised fields are SCHEMA-LIFTED, never excluded *(rewritten — codex r1 #3)*

v1 excluded pre-authorised fields from the comparison. That closed the schema hole and **opened a
behavioural one**: an excluded field is an unchecked field, so an implementation could emit any value for
it — including a wrong one — and still pass.

**The rule is now schema-lifting, and nothing is excluded:**

1. The `b685f24` reference payload is **lifted** into the frozen schema: each pre-authorised field is
   added to it **at the identity-default value in the §3 table**, which is by construction *what the
   reference run actually did* — `sink_support_m = 0.0`, `sink_support_cells = [(ext_cell, -1370.0)]`.
2. The candidate payload **must contain** the field.
3. **Both fields are then compared exactly, like every other field.** There is no exclusion list.
4. **Every other field is compared exactly**, as in §5.

The lift is legitimate only because the identity default is a *statement of existing behaviour* that can be
independently verified from the reference run — see §3.2. A field whose identity default cannot be derived
from the reference run may **not** be pre-authorised.

A field may be added to this table **only before the T1 edit that introduces it**, and only with the
lecturer approval of §7. Discovering mid-T1 that another field is needed is a **failure edge to T0**.

### 3.2 🔴 `sink_support_m = 0.0` is an explicit SENTINEL BRANCH, not a degenerate disc

*(codex r1 #3, verified.)* `0.0` **cannot** be processed through the B-control apportionment formula
`qᵢ = Q·area(cellᵢ ∩ disc)/area(disc)` — the disc area is zero and the expression is undefined. T1 must
implement `sink_support_m == 0.0` as a **named sentinel branch that retains the existing nearest-centroid
single-cell WEL construction verbatim**, not as a limit of the disc formula.

**T1 test obligation:** assert the **emitted WEL stress-period data** at the identity default is
byte-identical to the reference construction, and assert the degenerate flux-weighted readout reduces to
the single-cell concentration. Output equality alone does not prove the right sink was built.

### 3.3 🔴 Pre-authorised: the `arrival_day` → `t_peak` migration *(codex r1 #8, verified)*

`arrival_day` (`:94`) is **time of peak**, and §2.5 makes renaming a payload field a failure edge to T0.
But **M0 already retired the arrival name** in favour of three separately-named quantities —
`t_first_exceedance` (the compliance answer), `t_peak` (magnitude timing), `t_first_detection`
(`M0_contract_freeze_plan.md:75`) — and T0.2 owes a rename-or-alias decision. Signing v1 unchanged would
make the migration T0.2 requires a **violation of T0.0**.

**Pre-authorised now, so it is a planned freeze item rather than a breach:**
- The canonical name becomes **`t_peak`**, matching M0.
- **`arrival_day` is retained as an explicitly deprecated compatibility alias** carrying the identical
  value, so `04t`/`08t` and the test suite do not break inside T1.
- The reference payload is **schema-lifted** exactly as in §3.1: `t_peak` is added to it at the reference
  run's `arrival_day` value, and both names are then compared normally.
- The alias is removed only at or after the JAG, under C1's approved change allow-list — never during T1.

---

## 4. The normalisation, frozen

One formatter, applied everywhere. Named integers, no inline magic numbers.

```
SIGFIG_FLOAT        = 12    # every float, including inside meta / mass_balance / locked / arrays
FLOAT_FORMAT        = "{:.11e}"   # 12 significant digits, one canonical exponent form
```

12 significant digits is **strict on purpose**. It is not a tolerance — the ±8% test pin already exists
elsewhere and is exactly what cannot detect leakage (T1's stated reason for this gate).

⚠️ **But do not call it bitwise** *(codex r1 #2)*. `FLOAT_FORMAT` is lossy 12-significant-digit
quantisation, not float equality; and v1's claim that "deterministic MF6 on one machine reproduces
bitwise" was an **assumption, not a measurement**. §5.1 turns it into a measurement before anything
depends on it.

### 4.1 Per-class rules

| Class | Rule |
|---|---|
| `FLOAT` | `FLOAT_FORMAT` applied to the Python float; result is a **string** |
| `INT` | decimal string, no padding, no separators |
| `BOOL` | literal `"true"` / `"false"` |
| `STR` | verbatim, NFC-normalised |
| `ARRAY_FLOAT` | **list of `FLOAT` strings**, original order preserved, never binary, never base64 |
| `ARRAY_INT` | list of `INT` strings, original order preserved |
| `ARRAY_PAIR` | list of two-element lists, sorted by the leading `INT` |
| `MAPPING` | keys sorted lexicographically (byte order); values by their own class |

### 4.2 Ordering

- Mapping keys: **sorted**, at every nesting depth. `json.dumps(..., sort_keys=True)`.
- Array elements: **fixed original order** — `times` and `breakthrough` are time series and must not be
  sorted. `src_cells` is emitted in its produced order; `meta["sink_support_cells"]` is the sole exception
  and is sorted by cell index (§3).

### 4.3 Special values

| Value | Canonical form |
|---|---|
| `NaN` | the literal string `"NaN"` |
| `+Inf` | the literal string `"Infinity"` |
| `-Inf` | the literal string `"-Infinity"` |
| `-0.0` | normalised to `0.0` **before** formatting |
| `None` | the literal string `"null"` — and its appearance in a numeric field is a **defect**, not a value |

`NaN` is a legitimate payload value (§2.2) and compares **equal to `NaN`** under this normalisation, because
both sides render the same sentinel string. This is deliberate: the alternative — IEEE `NaN != NaN` — would
make a legitimate default result impossible to reproduce.

### 4.4 What is NOT in the payload

Wall-clock timings, workspace paths, temp directories, hostnames, the `case_ws` location, and the
environment fingerprint. They are recorded **alongside** the payload for provenance and are **never
compared**. (Nothing in §2 carries one today — this rule exists so nothing acquires one.)

---

## 5. The gate harness *(rewritten — codex r1 #4: v1 was not executable without inventing policy)*

v1 named two runs and left the operator to invent the checkout layout, process isolation, normaliser and
environment control. Those choices decide the answer, so they are frozen here.

### 5.0 The harness, frozen

- **Two git worktrees**, one at `b685f24`, one at the T1 candidate. Never one working tree mutated in
  place, and never one interpreter session.
- **Two fresh OS processes**, one per side. Same-process runs share FloPy/NumPy module state and a warm
  import cache; a SIGILL in refinement also kills the whole process (`model_io_utils.py:2846` — it is a
  fatal signal and **cannot** be caught by any `try/except`), so process isolation is required for the
  harness to survive one at all.
- **Asserted import roots:** each side asserts `transport_srcpulse_demo.__file__` and
  `model_io_utils.__file__` resolve **inside its own worktree**. Without this the candidate can silently
  import the reference's modules through a stale `sys.path`.
- 🔴 **Controlled cwd and config.** `find_project_root` walks up from the **current working directory**
  looking for `config.py` *or* `config_template.py` (`data_utils.py:21`). This machine has a gitignored
  `config.py`; a fresh worktree has only `config_template.py` — **so the two sides can resolve different
  data folders.** The harness sets cwd explicitly per side and asserts both resolve the **same** data
  folder.
- **Absolute, hashed executables.** MF6 is found via `shutil.which("mf6")` with a fallback (`:283`), and
  the refined solve separately hard-codes `exe_name="mf6"` (`model_io_utils.py:2637`). Resolve both to a
  **realpath + SHA-256** and assert the two sides used the identical binary. Same for the `triangle`
  executable.
  🔴 **`triangle` has NO fallback, unlike `mf6`** *(found during the §5.1 qualification run, 2026-08-20)*.
  `disv_grid_utils.py:1436,1501,1877` construct `Triangle(...)` without `exe_name`, so FloPy resolves the
  bare name `triangle` through `PATH` — while `mf6` carries an explicit
  `~/.local/share/flopy/bin/mf6` fallback in **four** places (`transport_srcpulse_demo.py:83`,
  `transport_base_model.py:611`, `tracer_test_utils.py:250`, `casestudy_flow_common.py:92`). Nothing in
  the repo puts that directory on `PATH`. The harness prepends it identically on both sides so the binary
  is hashable and deterministic. **This asymmetry is recorded as a T1 hardening candidate for C1's
  approved change allow-list — it is NOT fixed here**, because T0.0 §7 is unsigned and no T1 source edit
  may begin. If a student's `PATH` lacks that directory, every DISV refinement fails while MF6 works.
- **Pinned threading, set BEFORE Python starts** — `OMP_NUM_THREADS`, `GDAL_NUM_THREADS` and the rest to
  **1**. `data_utils` otherwise defaults them to all CPUs, which makes reduction order a machine property.
- **Identical process environment** on both sides apart from the worktree path.
- **Hashed inputs:** the calibrated flow model **and** the `model_boundary` / `rivers` GIS (§1.1).

### 5.1 🔴 QUALIFICATION — the gate must first pass against ITSELF

> ✅ **QUALIFICATION PASSED — 6 PAIRS, 12 COLD SIDE-RUNS, 2026-08-20.**
> `b685f24` vs `b685f24`, two worktrees, two cold processes, threads pinned, six independent repetitions.
> **6/6 pairs exact-equal; 0 field diffs anywhere**, across all 29 fields including the 122-point
> `times`/`breakthrough` series and the 9/17/9 nested keysets. `peak_mgL = 5.27695440327` and
> `arrival_day = 38.8043478261` were identical **across all twelve runs**, not merely within each pair.
> **`refine_radius_used = 70.0` on 12/12 — the retry ladder never advanced. `ncpl = 4408` on 12/12.**
> **SIGILL rate 0/12.** This is the first measurement bearing on the repo-memory claim of a historical
> ~40% SIGILL rate on macOS-arm64: 12 samples cannot rule out a small non-zero rate, but they do rule out
> anything close to 40%. Wall clock **min 14.35 s, max 15.00 s, mean 14.61 s** per side.
> ⚠️ **This qualifies the gate on THIS environment only** — macOS-arm64, this MF6/Triangle/FloPy/Python.
> The gate is same-environment by construction (§1.3), so that is exactly what it needs to prove; it makes
> **no** claim about the Hub, and a Hub-side T1 gate would need its own qualification.
>
> *(Superseded detail — the first single pair, 2026-08-20)*
> **FIRST QUALIFICATION PASSED, 2026-08-20** (`scratchpad/t0_qual/qualification_report.json`).
> `b685f24` vs `b685f24`, two worktrees, two cold processes, threads pinned. **Exact normalised equality
> on all 29 fields** — including the 122-point `times`/`breakthrough` series and the 9/17/9 nested
> keysets. `refine_radius_used = 70.0` and `ncpl = 4408` on both sides; no SIGILL.
> **Wall clock ≈ 14.8 s per side** — the first recorded timing of this identity anywhere in the project.
> ⚠️ *(At the time: one pair is not statistical confidence — the retry ladder only advances when an
> attempt fails, so determinism holds exactly as long as radius 70.0 keeps succeeding.)* **Resolved by the
> six-pair distribution above: 12/12 first-attempt successes, no retry, no divergence.**

*(codex r1 #2 / its "single most important remaining fix".)* Before the gate is used to judge anything, and
**before §7 is signed**, run it **`b685f24` versus `b685f24`** — two cold runs of the *same* commit through
the full harness.

**It must produce exact normalised equality on every field.** Until it does, the gate is unproven, and
signing it would freeze a contract nobody knows can be satisfied.

Known threats to that, none yet disproven:
- **`meta["refine_radius_used"]` is the first direct instability indicator** — it records *which* retry
  succeeded (`_refine_with_retry`, `:158`), and a changed radius cascades through most of the payload.
- Triangle/Voronoi geometry is **regenerated on every run**; cell ordering reaches `src_cells`,
  `ext_cell`, `inj_cell`, `meta["ncpl"]`, every mesh-derived diagnostic, and the solve itself.
- Nearest-cell and binding-cell selection break ties by **index order** through `argmin`/`argmax`
  (`:386`, `:201`).

**If qualification fails**, the response is to **strengthen the harness, never to relax the contract**:
freeze the mesh spec by hash, isolate and pin the refinement attempt, assert nearest/binding selections are
**unique** (no tie), and re-qualify. **Loosening `SIGFIG_FLOAT` after seeing a diff is forbidden** — that is
choosing the answer, which is the one thing this document exists to prevent.

### 5.2 The comparison

1. Record the environment fingerprint, the flow-data fingerprint and the GIS hashes. Assert §1.1, §1.3.
2. Run §1's invocation at **`b685f24`** in worktree A, fresh `case_ws`, fresh process → normalise per §4.
3. **Schema-lift** the reference per §3.1 and §3.3.
4. Run §1's invocation at the **T1 candidate** in worktree B, fresh `case_ws`, fresh process → normalise.
5. **Abort** per §2.2 if either side's `mass_balance` carries `"error"` or a non-conforming keyset.
6. Assert the exact nested keysets of §2.2b.
7. Assert **exact string equality**, field by field, **for every field including the pre-authorised ones**.
8. On mismatch: report **every** differing field with both values. A mismatch is a **T1 defect to fix**,
   never a rebaseline to record — rebaselines exist only at the JAG, against T2's audited old→new map.

No stored digest discharges this. The gate is differential and same-environment **by construction**, which
is what makes it incapable of self-baselining.

---

## 6. Hub feasibility threshold and safety margin *(T0.0 item 4; detail in T0.5)*

Frozen limits, applied by T2 to the named feasibility-probe identity and by case-study M3/M6 to every
actual fine identity:

```
HUB_FINE_TARGET_S  =  600    # == BUDGET_WARN_S; the intended operating point
HUB_FINE_CEILING_S =  900    # hard pass/fail: 50% of WALL_TIMEOUT_S = 1800 s
HUB_SAFETY_MARGIN  =  2.0    # ceiling = wall / MARGIN
```

- A probe **at or under `HUB_FINE_TARGET_S`** passes cleanly.
- Between target and `HUB_FINE_CEILING_S`: passes **with a recorded warning** that students on a loaded Hub
  will see it.
- **Above `HUB_FINE_CEILING_S`: T2 fails** and takes its declared failure edge (T1 for a cheaper `GridSpec`,
  T0 for a revised threshold or requirement). It may **not** pass by reclassifying the mandatory fine run
  as optional.

⚠️ **The Hub multiplier `H` is still unmeasured.** Every runtime in the design docs is a fast Mac. At the
illustrative `H = 3`, the 316 s fine identity becomes ≈ 948 s — **over this ceiling.** That is precisely why
the threshold is frozen before the measurement rather than after it. **Timing one known case on the Hub
remains the cheapest outstanding action in the project.**

---

## 7. Approval

T0.0 takes effect only when this section is completed. Until then, **no T1 source edit may begin.**

| | |
|---|---|
| **Document version** | v1 |
| **Prepared** | 2026-08-20 |
| **Approved by** | *(name)* |
| **Approval date** | *(date)* |

**Open items at approval:**

1. ✅ **§5.1 qualification has PASSED** — 6 pairs / 12 cold runs, exact normalised equality every time,
   0/12 SIGILLs, retry ladder never advanced. **This precondition of signature is now met on this
   environment.** It remains a per-environment claim: a Hub-side gate needs its own qualification.
2. **The three constants in §6** are proposed policy, not a measurement. `HUB_FINE_CEILING_S = 900` (half
   the 1800 s wall) is the value to accept or change; changing it *after* T2 measures the Hub is a failure
   edge, not an edit.
3. **The `arrival_day` → `t_peak` migration of §3.3** — pre-authorised here, but it is a naming decision
   T0.2 formally owns and M0 already made. Confirm it rather than reopen it.

*(The regulatory threshold values — PFOA especially — remain open but are **not** a T0 blocker: they are
consumed by T3/T4, not by the canonical contract.)*
