# T0.5 — The feasibility probe: identity, protocol, ownership

**Milestone:** T0.5 of `transport_notebook_milestones.md` (READY v7).
**Status:** **DRAFT v1 (2026-08-20)** — signs as part of the single T0 decision record.
**Thresholds live in `T0_0_canonical_contract.md` §6** (`HUB_FINE_TARGET_S` 600 · `HUB_FINE_CEILING_S` 900 ·
`HUB_SAFETY_MARGIN` 2.0). This document does **not** restate them; it says **what gets timed, how, and by
whom**. Codex flagged that §6 referred to a *"named feasibility-probe identity"* that was never named.

---

## 1. 🔴 The named probe: **G0 / concession `b010210`** — not the notebook demo

The refined corridor spans **spill → extraction**, plus the injection well
(`transport_srcpulse_demo.py:369–371`), so its extent — and therefore the cell count and the runtime —
is driven mainly by the **doublet separation**. Computed from the shipped roster
(`_SUPPORT/casestudy_scenarios/doublet_table.csv`, 9 rows):

| group | concession | inj↔ext separation | Q (m³/d) |
|---|---|---|---|
| **G0** | **b010210** | **240.3 m** ← largest | 4320 |
| G2 | b010201 | 235.2 m | 4320 |
| G8 | b010207 | 141.6 m | 4320 |
| G4 | b010120 | 127.5 m | 4320 |
| G6 | b010227 | 124.3 m | 4320 |
| G1 | b010219 | 119.1 m | 4320 |
| G3 | b010236 | 114.0 m | 4320 |
| G7 | b010213 | 49.5 m | 4320 |
| G5 | b010223 | 34.2 m | 4320 |
| *(demo)* | *b010191* | *200.5 m* | **1370** |

🔴 **The probe is defined by a RULE, not by a fixed name** — because the roster is going to grow (§5):

> **The feasibility probe is the identity with the LARGEST doublet separation in the final release
> roster.** As of 2026-08-20 that is **G0 / `b010210` (240.3 m)**.

**Why the rule and not just the name.** The lecturer requires **at least ten cases** and the roster holds
nine, so a tenth is still to be built. **If that tenth case has a separation above 240.3 m, G0 stops
bounding the set and the probe changes with it.** Naming G0 alone would have quietly created a stale bound
the moment case ten landed — the same failure mode as the demo-as-proxy trap below, one step later.

**Adding or replacing a case therefore requires re-evaluating this table**, and a new maximum is a
**failure edge to T0.5**, not a silent substitution. It is not a proxy either way: the probe is always one
of the identities the case study must actually run.

### 1.1 🔴 Why the notebook demo identity is DISQUALIFIED as a proxy

It would have been the convenient choice, and it under-prices the real work on **two independent axes**:

1. **Separation** — the demo is 200.5 m; **G0 (240.3 m) and G2 (235.2 m) are larger**, so the demo's
   refined corridor is smaller than two real cases.
2. **Pumping rate** — the demo runs `DOUBLET_Q = 1370` m³/d (`transport_srcpulse_demo.py:79`), while
   **every group runs 4320 m³/d — 3.15×**. Higher Q means higher cell velocities, a tighter Courant limit,
   and therefore **more timesteps for the same grid**.

A proxy that is smaller on both axes cannot bound anything. Had T2 timed the demo and reported "fine run
feasible", the first real group run would have refuted it.

---

## 2. 🔴 Predeclared feasibility risk — the mandatory fine run may already be infeasible

Recorded **before** T2 measures anything, so the outcome cannot be renegotiated afterwards.

**What is measured, not extrapolated:**
- The corrected-Courant 2 m corridor for the **demo** identity needs **`nstp = 2000` and ~316 s** on a fast
  Mac (`transport_notebook_regrid_vision.md:97–101`).
- `nstp_cap = 2000` (`transport_srcpulse_demo.py:544`). **So that run sat exactly ON the cap** — meaning
  `cr_target = 0.9` may not have been reached and `cr_capped` would be true.
- Every group runs **3.15× the demo's pumping rate**.

**What follows (EXTRAPOLATION — flagged as such, to be replaced by T2's measurement):** timestep demand
scales roughly with velocity, so a group fine identity would want **~6,300 steps** against a cap of 2,000,
and its runtime on the same fast Mac would be of order **~1,200 s** — **already past
`HUB_FINE_CEILING_S = 900 s` before any Hub multiplier is applied.**

**The predeclared consequences, in force order:**
1. T1's step-cap rule already says hitting `nstp_cap` **fails loudly**; it may never pass as "honest
   time-stepping". A capped fine run is **not** a feasible fine run.
2. If the G0 probe exceeds the ceiling, **T2 fails and takes its declared failure edge** — to T1 for a
   cheaper `GridSpec`, or to T0 for a revised threshold or a revised requirement. It may **not** be
   reclassified as a "feasibility stop" (`T0_2b…` §3, stopping rule 2 — that applies to the spatial series,
   never to the probe).
3. Raising `nstp_cap` is itself a **T0 decision**, not a T1 convenience: it changes what "resolved in time"
   means for every claim in the track.

⚠️ **This is the single most likely way the mandatory per-group fine run turns out to be unaffordable**, and
it is now on the record before the measurement rather than after it.

---

## 3. The timing protocol

| Item | Frozen |
|---|---|
| **Identity** | G0 / `b010210`, the finest `GridSpec` in the T0.2b §3 spatial series that the case study requires |
| **Executions** | **two COLD runs** (fresh workspace, no warm cache, one process each) **plus one WARM run** |
| **Gating statistic** | 🔴 **the MAXIMUM of the two cold runs** — not the mean, not the best. A student meets the wall on a bad run, not on an average one |
| **Warm run** | **recorded, never gating.** It measures cache benefit, and a student's first run is always cold |
| **Environment** | the course JupyterHub, under the image students actually get; record OS/arch, MF6, FloPy, Python, and the Hub node type if available |
| **Recorded alongside** | `ncpl`, `nstp`, `meta["Cr"]`, `cr_capped`, and whether `nstp_cap` bound — a run that hit the cap is reported as capped, never as a clean timing |

**Cold/warm convention matches the release protocol** so T5's verification compares like with like.

---

## 4. Division of labour — stated so the requirement cannot float

| Who | Does what |
|---|---|
| **T2** | Runs the **G0 probe** on the Hub, applies T0.0 §6's threshold as a **pass/fail**, and either meets it or takes the failure edge. Also derives the Hub multiplier `H` from it. **T2 does not run the other eight.** |
| **Case-study M3/M6** | Applies the **same frozen threshold** to **every actual fine identity**. This is where a per-case infeasibility surfaces. |
| **T5** | Verifies the decided default on a clean Hub. Does not re-decide it. |

Deciding the *notebook* default grid does **not** discharge the case-study fine-run requirement. They are
different obligations sharing one threshold.

---

## 5. 🔴 RESOLVED: ten cases are REQUIRED; the roster has nine — a build gap

**Lecturer decision, 2026-08-20:** *"We ultimately need at least 10 cases. We currently only have 9 cases.
That needs an update."*

So the plans were right and the **roster is short by one**. The discrepancy was surfaced by this document
and resolved in the direction opposite to my own initial reading — which is exactly why it was flagged for
the lecturer rather than "corrected" in the contracts.

**Current state, verified:** nine groups, G0–G8, everywhere —
`casestudy_doublet_roster.py:128` (`CONCESSIONS`, 9 entries) · `doublet_table.csv` (9 rows) ·
`canonical_mapping.csv` (9) · `coherence_ledger.csv` (9) · `threshold_sanity.csv` (9).

**Consequences, recorded here so nothing silently assumes nine:**

1. **`case_study_release_matrix` stays at 40 rough + 10 fine = 50 identities** (`T0_2b…` §5). It is a
   requirement, not an observation, and the roster must rise to meet it.
2. **The probe is defined by the rule in §1**, so the tenth case cannot silently invalidate the bound. If
   its separation exceeds **240.3 m**, the probe becomes that case.
3. **Building case ten is CASE-STUDY work, not T0.** It belongs with the parked plan (roster generation →
   `doublet_table` → `canonical_mapping` → ledgers → validation), and it is **not** a T0 blocker: T0 freezes
   the contract, and the contract already says ten.
4. ⚠️ **Every instructor artifact must be regenerated together**, not patched. The five files above are
   produced by one pipeline and carry cross-referencing shas; hand-adding a row to one of them would
   desynchronise the set.
5. ⚠️ **`CONCESSIONS` is a hand-picked tuple** (`casestudy_doublet_roster.py:128`), so adding a case means
   **choosing a tenth concession** that satisfies the existing roster criteria — in domain, in an active
   cell, not in a river, within the `SPREAD_LIMIT_M = 50 m` pairwise limit for each role — and then
   re-running the pipeline and the group validation.

### 5.1 There is ample supply — and it does NOT move the probe

A scan of `Wasserfassungen_-OGD.gpkg` (layer `GS_GRUNDWASSERFASSUNGEN_OGD_P`, LV95) finds **36 in-domain
geothermal (`WPG`) concessions carrying both an *Entnahme* and a *Rückgabe* well**. Nine are in use, and
**21 of the remainder also satisfy the 50 m per-role spread limit**. The largest by doublet separation:

| concession | sep (m) | n_ext | n_inj | max spread (m) |
|---|---|---|---|---|
| `b010202` | 131.1 | 1 | 1 | 0.0 |
| `b010228` | 127.8 | 2 | 1 | 8.9 |
| `b010204` | 117.8 | 2 | 2 | 23.8 |
| `b010224` | 115.8 | 4 | 6 | 32.1 |
| `b010212` | 114.8 | 2 | 2 | 24.8 |
| `b010230` | 114.2 | 1 | 2 | 36.9 |
| `b010214` | 101.5 | 2 | 2 | 22.0 |
| `b010200` | 99.8 | 2 | 1 | 10.0 |

🔴 **The largest candidate is 131.1 m, far below G0's 240.3 m — so whichever tenth case is chosen from this
pool, the §1 rule does not fire and the probe REMAINS G0.** The feasibility work in §2 is therefore not
blocked on case ten and can proceed now.

⚠️ **This is a SHORTLIST, not a selection.** The scan applies the boundary polygon, `NUTZART == WPG`, the
`Entnahme`/`Rückgabe` role split and the spread limit. It does **not** apply the active-cell (`idomain`)
test, the 20 m river buffer, the both-role ambiguity guards, or the `Ertrag` parsing that sets `Q_m3d`.
**Only the real pipeline selects a case** — `casestudy_doublet_roster.py` must be re-run, which regenerates
all five instructor artifacts together (consequence 4 above).

---

## 6. Open items

1. ✅ **Case count RESOLVED** (§5): **ten required**, nine built. Selecting and building the tenth is
   case-study work, tracked there, and does not block T0.
2. **The extrapolation in §2 is not a measurement.** T2's probe replaces it. If the probe lands under the
   ceiling, §2's risk simply did not materialise — the record stays as evidence that it was predeclared.
