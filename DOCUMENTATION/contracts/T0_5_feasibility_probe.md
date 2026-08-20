# T0.5 — The feasibility probe: identity, protocol, ownership

**Milestone:** T0.5 of `transport_notebook_milestones.md` (READY v7).
**Status:** **DRAFT v2 (2026-08-20)** — §1 probe rule CORRECTED after the codex consolidated review — signs as part of the single T0 decision record.
**Thresholds live in `T0_0_canonical_contract.md` §6** (`HUB_FINE_TARGET_S` 600 · `HUB_FINE_CEILING_S` 900 ·
`HUB_SAFETY_MARGIN` 2.0). This document does **not** restate them; it says **what gets timed, how, and by
whom**. Codex flagged that §6 referred to a *"named feasibility-probe identity"* that was never named.

---

## 1. 🔴 The probe rule — CORRECTED v2: separation was the wrong variable

**v1 of this document ranked the roster by injection↔extraction separation and named G0 / `b010210`.
That was wrong**, and the codex consolidated review caught it. The refined corridor is built
**spill → extraction** (`transport_srcpulse_demo.py:149`, `_corridor_points`), and the timestep count is
driven by `total_time × max(v/ds)` (`_courant_nstp`, `:188`). **Neither is the well spacing.**

Recomputed from the shipped per-group scenarios (`PROJECT/workspace/template/case_config_transport.yaml`,
where the spill is an offset **from the extraction well** and each case carries its own horizon):

| concession | spill→ext | inj↔ext | horizon (d) | Q (m³/d) | spill × horizon |
|---|---|---|---|---|---|
| **b010227** | **250.3 m** | 124.3 | **1095** | 4320 | **274,126** |
| b010213 | 136.5 m | 49.5 | 730 | 4320 | 99,615 |
| b010236 | 130.0 m | 114.0 | 730 | 4320 | 94,869 |
| b010120 | 92.7 m | 127.5 | 730 | 4320 | 67,638 |
| b010201 | 113.6 m | 235.2 | 60 | 4320 | 6,816 |
| b010207 | 97.6 m | 141.6 | 60 | 4320 | 5,858 |
| **b010210** *(v1's probe)* | 92.4 m | **240.3** | 60 | 4320 | **5,541** |
| b010219 | 179.3 m | 119.1 | 30 | 4320 | 5,380 |
| b010223 | 73.3 m | 34.2 | 30 | 4320 | 2,200 |

🔴 **`b010210` is the second-CHEAPEST identity, not the most expensive** — it topped v1's table only because
it has the widest well spacing, which sets neither corridor length nor step count. v1 would have bounded
the most expensive case with nearly the cheapest one: **the same failure as the demo-as-proxy trap it was
written to avoid, in a worse form.** Recorded rather than quietly rewritten, because the reasoning error
matters more than the wrong name.

### 1.1 The rule, frozen

> **The feasibility probe is the identity that maximises the static cost proxy
> `spill_to_extraction_distance × simulation_horizon_days` over the final release roster.**
> As of 2026-08-20 that is **`b010227` — 250.3 m × 1095 d = 274,126, 2.75× the runner-up.**

**Why a static proxy is legitimate here** *(lecturer decision, 2026-08-20)*: both factors enter the cost
directly — corridor length sets the refined cell count, and the horizon multiplies the step count at a
given Courant target — and the margin over the runner-up is wide enough that no plausible weighting
reorders the top. Pumping rate `Q` is uniform at 4320 m³/d across all nine, so it cannot discriminate.

### 1.2 The pilot confirms it — and may overturn it

🔴 **The proxy selects; it does not measure.** **T2's first act is a same-code pilot** over the roster,
ranking by **measured `ncpl × required_uncapped_nstp`** — the two quantities that actually determine cost,
with the step demand computed **uncapped** so a cap cannot mask it.

- If the pilot confirms `b010227`, the timing run proceeds against it.
- **If the pilot ranks a different identity first, that identity becomes the probe** and this section takes
  a **failure edge to T0.5**. It is not a silent substitution.
- The pilot's ranking is recorded with the roster hash, so adding the tenth case re-opens the question
  explicitly rather than leaving a stale bound.

⚠️ **Adding or replacing a case requires re-evaluating both the proxy and the pilot.** The roster is going
from nine to ten (§5).

## 2. 🔴 Predeclared feasibility risk

Recorded **before** T2 measures anything, so the outcome cannot be renegotiated afterwards.

**Measured facts:**
- The corrected-Courant 2 m corridor needs **`nstp = 2000` and ~316 s** for the **notebook demo** identity
  on a fast Mac (`transport_notebook_regrid_vision.md:97–101`), and the demo's `nstp_cap` **is** 2000
  (`transport_srcpulse_demo.py:544`) — so that run sat **on the cap**, meaning `cr_target = 0.9` may not
  have been reached.
- The demo runs a **60-day-equivalent** exposure at `DOUBLET_Q = 1370` m³/d. The probe case `b010227` runs
  **1095 days at 4320 m³/d over a 250 m corridor** (§1).

**The risk, stated without a false-precision multiplier:** the probe's horizon is **18× the demo's**, its
corridor **~2.8× longer**, and its pumping rate **3.15× higher** — each of which pushes step count or cell
count the same way. **A fine-grid run of `b010227` is therefore very likely to exceed both the step cap and
`HUB_FINE_CEILING_S = 900 s`.**
⚠️ *v1 of this document multiplied a single 3.15× factor onto the demo runtime. That was too crude — step
demand follows `max(v/ds)` over the mesh, not the pumping rate alone — and it also used the wrong case.
**The pilot of §1.2 replaces this reasoning with a measurement**; the risk is recorded, the number is not.*

### 2.1 Resolution criterion vs resource guard — do not conflate them

*(codex consolidated review #6.)* v1 said raising `nstp_cap` is a T0 decision. **That was wrong**:

- **`cr_target` is the RESOLUTION criterion.** Relaxing it changes what "resolved in time" means for every
  claim in the track → **a genuine T0 failure edge.**
- **`nstp_cap` is a RESOURCE GUARD** (`transport_srcpulse_demo.py:544` = 2000;
  `transport_base_model.py:147,210` = 1000). Raising it to *measure* uncapped demand is **engineering, not
  a contract change** — and §1.2's pilot needs exactly that freedom.

**What does NOT change:** a run that hits the cap **fails loudly** and may never pass as "honest
time-stepping" (T1 exit). A capped run is not a feasible run, whatever the cap is set to.

### 2.2 Consequences if the probe exceeds the ceiling

1. **T2 fails and takes its declared failure edge** — to T1 for a cheaper `GridSpec`, or to T0 for a revised
   threshold or requirement.
2. It may **not** be reclassified as a "feasibility stop" (`T0_2b…` §3 rule 2 governs the *spatial series*,
   never the probe).
3. Reducing a case's **horizon** to fit is a **case-study scenario change**, not a T2 convenience — the
   horizons in `case_config_transport.yaml` were chosen to capture rise-peak-decline.

## 3. The timing protocol

| Item | Frozen |
|---|---|
| **Identity** | **the §1 rule's current selection — `b010227`** — at the finest `GridSpec` in the T0.2b §3 spatial series that the case study requires. Named by rule, confirmed by the §1.2 pilot, recorded with the roster hash |
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
| **T2** | Runs the **§1.2 pilot** over the roster, confirms or corrects the probe, then runs the probe on the Hub and applies T0.0 §6's threshold as a **pass/fail** — meeting it or taking the failure edge. Also derives the Hub multiplier `H`. **T2 does not run the full fine matrix.** |
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

### 5.1 Supply is ample — but the tenth case's COST is a design choice, not a roster property

A scan of `Wasserfassungen_-OGD.gpkg` (layer `GS_GRUNDWASSERFASSUNGEN_OGD_P`, LV95) finds **36 in-domain
geothermal (`WPG`) concessions carrying both an *Entnahme* and a *Rückgabe* well**. Nine are in use, and
**21 of the remainder also satisfy the 50 m per-role spread limit** — `b010202`, `b010228`, `b010204`,
`b010224`, `b010212`, `b010230`, `b010214`, `b010200`, `b010220`, `b010232`, `b010211`, `b010231`,
`b010226`, `b010222`, `b010229`, `b010215`, `b010233`, `b010205`, `b010216`, `b010194`, `b010237`.

🔴 **A note v1 of this document got wrong.** v1 concluded "no candidate exceeds G0's 240.3 m, so the probe
is unaffected" — reasoning from **well separation**, the variable §1 has since retired. The correct
statement is sharper and less comfortable:

> **The cost of case ten is not a property of the concession.** It is set by the **spill offset** and the
> **simulation horizon** assigned to that case when its scenario is designed — both of which are authored
> in `case_config_transport.yaml`, not read from the registry. A tenth case given a long corridor and a
> multi-year horizon **would become the probe**.

**Therefore, a constraint on building case ten:** when its scenario is authored, compute
`spill_to_extraction_distance × horizon_days` and compare against **`b010227`'s 274,126**. If it exceeds
that, §1's rule fires, the probe changes, and this document takes a **failure edge to T0.5**. Designing the
tenth case to sit *below* the current maximum keeps the frozen probe valid and is the cheaper path — but
that is a **scenario-design decision for the lecturer**, not something T0 may impose on pedagogy.

⚠️ **The concession list above is a SHORTLIST, not a selection.** The scan applies the boundary polygon,
`NUTZART == WPG`, the `Entnahme`/`Rückgabe` role split and the spread limit. It does **not** apply the
active-cell (`idomain`) test, the 20 m river buffer, the both-role ambiguity guards, or the `Ertrag`
parsing that sets `Q_m3d`. **Only `casestudy_doublet_roster.py` selects a case**, and running it
regenerates all five instructor artifacts together.

## 6. Open items

1. ✅ **Case count RESOLVED** (§5): **ten required**, nine built. Selecting and building the tenth is
   case-study work, tracked there, and does not block T0.
2. **The extrapolation in §2 is not a measurement.** T2's probe replaces it. If the probe lands under the
   ceiling, §2's risk simply did not materialise — the record stays as evidence that it was predeclared.
