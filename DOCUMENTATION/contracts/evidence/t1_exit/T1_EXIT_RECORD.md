# T1 — exit record

**Milestone:** T1, *Experimental infrastructure*.
**Candidate commit:** `c13e4a1657197bd7fd2f7b2b2dcbaf9755b7f36d`
**Reference:** `b685f24` (the T0-qualified reference run).
**Date:** 2026-08-26. **Platform:** macOS / arm64 (⚠️ Hub unverified — see §4).

---

## 1. The two exit gates

### S15 — the C1 default suite, green *(C1 §2, six gates)*

| # | Gate | Result |
|---|---|---|
| 1 | Default-path execution is clean — the six notebooks run end to end | ✅ **all six OK** — 01t 0.9 s · 02t 2.0 s · 03t 1.0 s · **04t 16.2 s** · 05t 1.5 s · 08t 1.9 s |
| 2 | Every checkpoint resolves **and its revealed solution is correct** | ✅ **15 invoked, 15 defined, 0 undefined.** Values cross-checked against executed output — see §2 |
| 3 | Internal links resolve | ✅ **Scanned 54 files; checked 108 internal links; 0 failures** |
| 4 | Notebook outputs are cleared | ✅ all six: 0 cells with outputs, 0 with `execution_count` set |
| 5 | The five test suites are green | ✅ **187 passed** across the five C1 suites + `test_t0_gate_harness.py` |
| 6 | The canonical default-preservation gate passes | ✅ **S16, below** |

Notebooks were executed in **copies**, so the tracked files remain outputs-cleared — gate 4 cannot be
invalidated by testing gate 1.

### S16 — the canonical gate, on a COMMITTED candidate with a FRESH workdir

```
compare --workdir <fresh> --ref-commit b685f24 --candidate c13e4a1657197bd7fd2f7b2b2dcbaf9755b7f36d
```

| | |
|---|---|
| comparison | ✅ **PASS** |
| `payload_mismatch_count` | **0** |
| `env_mismatches` | **{}** |
| side A / reference | OK, 15.47 s |
| side B / candidate | OK, 15.56 s |

Full report: `s16_compare_report.json`.

---

## 2. The default is intact where a STUDENT can see it

The payload gate proves the dataclass is unchanged. The stronger evidence is that the executed
student-facing notebook still prints:

> **`Peak 5.28 mg/L at day 39.`**   `First exceedance of 1 mg/L at ~day 14.`
> `Pe_L 0.5-1.4 (<= 2 OK)   Pe_T 5-14 (>> 2)`

matching the reference peak **5.2770** and `arrival_day` **38.8043478261**, and matching
`task_t04_checkpoint_1`'s range **(0.5, 1.5)**. This is the same surface that produced the 2026-08-18
rot — `tasks_data.py` promising 5.1 mg/L while the cell printed 5.28 — so it is checked directly rather
than inferred.

---

## 3. 🔴 Two findings recorded, neither blocking T1

### 3.1 A9 enumerates FOUR orphaned checkpoints; there are TEN

A9 names `task_t04_checkpoint_2` and `task_t05_tt_checkpoint_1/2/3`. A complete extraction — every
`task_t*` literal in the six notebooks against every `tasks_data` dict — finds **ten** defined-but-never-
invoked keys. The six A9 does not name:

`task_t05_checkpoint_2` · `task_t05_checkpoint_3` · `task_t05_checkpoint_4` ·
`task_t05_checkpoint_best_alpha` · `task_t05_checkpoint_nonunique` · `task_t05_checkpoint_transfer`

All are `task_t05_*`, consistent with the 2026-06 solute rewrite of `05t` leaving its old calibration
checkpoints behind. Verified complete: no notebook builds a checkpoint key dynamically, so a literal scan
sees every invocation.

**Not a T1 failure** — orphans resolve fine, and retirement is **T3/A9** work. But **A9 as written would
retire four and leave six**, so it is an enumeration error in signed text and needs the C1 §3.1 treatment.

### 3.2 `task_t05_checkpoint_1` carries a stale numeric solution

It is invoked as `create_multiple_choice(...)`, its question is multiple-choice, and its multiple-choice
answer is correct — but `solutions` still holds a numeric range **`(4, 6)`** from before the rewrite.
It is **never revealed** (the MC path reads `multiple_choice_options` / `solutions_exact`), so gate 2
passes. It is dead data of exactly the kind this track is removing, and belongs with §3.1's retirement.

---

## 4. ⚠️ What this record does NOT establish

- **Hub behaviour.** Every timing and result here is macOS/arm64. **No Hub runtime is recorded anywhere in
  the repo**, and the outstanding Hub measurement now carries a second passenger: S10's capture-fingerprint
  **repeatability envelope**, which needs the same access.
- **That the interpolated metrics are right in production** — S11 is `exp`-only and unwired by design.
- **Anything about T2's matrix.** T1 ships capability; T2 runs it.
- **The six pre-existing failures in `test_casestudy_flow_builder.py`** are flow-track
  platform-dependent Triangle goldens, outside C1's five suites, and unrelated to this milestone.

---

## 5. Carried into T2 *(added 2026-08-26, after the first Hub session)*

🔴 **Recorded here, in TRACKED text, because `transport_notebook_milestones.md` is gitignored.** T2's own
statement of these items lives in that file and **two of them are now stale** (§5.3). Anything T2 depends
on has to survive a clean clone.

### 5.1 🔴 The open question is now the MESH, not the platform

`T0_2b…` §2.6 warned about *"a highly **mesh**/platform-dependent geometric quantity"*. The 2026-08-26
measurement addressed only the **platform** half — ten runs across two platforms, but **one mesh, one
transect position, default probe settings** — and the signed narrowing says so explicitly.

**T2 varies the mesh deliberately.** That makes mesh-dependence the exposure that actually bears on its
verdict, and it is **entirely unmeasured**.

> **What T2 should do before trusting `capture_halfwidth_m` as a discriminator:** replicate the fingerprint
> across the spatial series' meshes on **one** platform, and compare that spread against
> `TOL_WIDTH_REL = 5%` — the same test the platform question just passed. `hub_measurement.py`'s
> `run_fingerprint_replication` does the replication; only the mesh needs varying.

⚠️ If mesh spread exceeds the tolerance, the fingerprint is a **descriptor of the mesh**, not evidence
about the plume — and S10's arm loses its second reported quantity while keeping its first (the flow
deltas, which are deterministic solver outputs and unaffected).

### 5.2 ⚠️ `H = 2.30` is a two-sample mean — get parity before committing to a matrix

| | |
|---|---|
| samples | **2** side-runs, differing by **12.2%** (35.69 / 31.60 s) |
| macOS record it is compared against | **6 pairs / 12 cold side-runs** |
| SIGILL evidence | **0/2** on Hub vs **0/12** on macOS |
| headroom to `HUB_FINE_CEILING_S` | **19%** (728 s of 900 s) |
| 🔴 `316 s` | a **FLOOR** — that run sat on `nstp_cap = 2000`, so `cr_target = 0.9` may never have been reached |

**Five more `qualify` invocations (~10 minutes) would give parity with the macOS record.** Worth doing
**before** T2 commits to a mesh matrix, because the verdict that the fine run clears the ceiling rests on
19% headroom against a floor — and T2 prices *every* fine identity against that same threshold.

```bash
python _SUPPORT/src/scripts/hub_measurement.py --workdir ~/hub_meas --skip-fingerprint   # x5
```

### 5.3 🔴 Two items in the milestone plan are now STALE

| Plan item | Status |
|---|---|
| **T2 §6** — *"PRT grid/platform gate — ~24% Mac↔Hub spread … so `≈53 m` cannot be a grid-supported value unqualified"* | **SUPERSEDED.** `T0_2b…` §2.6 was narrowed and **signed 2026-08-26** (decision record §8.4): no platform qualification between macOS-arm64 and this Hub. The **mesh** half stands — see §5.1 |
| **T2 §7** — *"T2 measures the Hub slowdown factor, prices the fine run against `BUDGET_WARN_S` / `WALL_TIMEOUT_S`"* | **PARTLY DISCHARGED.** `H = 2.30` measured; fine run priced at **728 s**, below `HUB_FINE_CEILING_S = 900`. ⚠️ **The default-grid DECISION in the same item is untouched and remains T2's**, as does applying T0.5's threshold as pass/fail to the **case-study** fine identity, which is a different and larger run than the notebook demo measured here |

⚠️ **Do not read §7 as discharged.** What was measured is the **notebook demo** identity. T0.5's probe case
`b010227` runs **1095 days at 4320 m³/d over a 250 m corridor** — an 18× horizon, ~2.8× corridor and 3.15×
pumping against the demo — and its feasibility is still predeclared as *"very likely to exceed both the
step cap and `HUB_FINE_CEILING_S`"*. **`H` prices that run; it does not exempt it.**
