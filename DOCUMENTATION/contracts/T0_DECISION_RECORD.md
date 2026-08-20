# T0 — The single decision record

**Milestone:** T0 (Contract closure) of `transport_notebook_milestones.md` (READY v7).
**Status:** **DRAFT v2 (2026-08-20) — NOT YET SIGNABLE.** Three exit items are open (§2).
The codex consolidated review returned **DO-NOT-SIGN**; its findings are folded in and §7 records what
changed.
**Until §6 is signed, no T1 source edit may begin.**

This is the one record the milestone's T0 exit requires. It does **not** restate the contracts — each is
frozen in its own file, and restating them is exactly how a narrower duplicate got adopted twice during
planning. It **assembles** them, checks completeness item by item, and carries the single signature.

---

## 1. What T0 froze

| Doc | Version | What it freezes |
|---|---|---|
| `T0_0_canonical_contract.md` | **v3** | The canonical default-preservation gate: exact invocation · cold-workspace policy · the payload (the **entire** public `SrcPulseDemo` surface, with the 9 `mass_balance` / 17 `meta` / 9 `locked` keys enumerated) · the normalisation · the two-process harness · the §5.1 qualification · the Hub thresholds |
| `T0_1_C1_v2.md` | **v1** | C1 v2: enumerated surfaces (**generated**) · invariant gates with per-milestone scoping · the versioned change allow-list (A1–A9) · the numeric-rebaseline table |
| `T0_1_pinned_surfaces.md` | generated | The **32** result-derived pins in tests and modules — input to C1 §4 |
| `T0_2a_claim_inventory.json` / `.md` | schema v2 | **249** candidates / **267** typed assignments; **gate exits 0** |
| `T0_2b_metrics_and_causal_rule.md` | **v3** | Metric algorithms + interpolation · sequences and stopping rules · the three tolerances · the causal-support rule and the `causal-physics` / `causal-numerical` split · both matrices · the claim-typing rules R0–R4 |
| `T0_3_claim_support_state.md` | **v2** | `claim_support_state`: three states · thirteen reason codes · the ordered gate pipeline · the total compute truth table |
| `T0_5_feasibility_probe.md` | **v1** | The probe **rule** (largest separation in the final roster → currently **G0 / b010210**) · the cold/warm protocol and gating statistic · the T2 / M3–M6 division of labour · the predeclared feasibility risk |

---

## 2. Completeness check against the T0 exit

🔴 **v1 of this record claimed "12 of 13 complete". That was not supportable** — the codex consolidated
review audited it and found several rows pointing at something thinner than the exit requires. The table
below is the corrected audit, and it is deliberately unflattering: **three items are still open, and the
record is NOT signable until they close.**

| # | Required by the T0 exit | Where | Status |
|---|---|---|---|
| 1 | T0.0's frozen canonical contract | `T0_0…` §§1–5; approval now **delegated** to §6 here | ⏳ **pending** — the harness validated keysets but not value **types**, so a type change passed silently. Being hardened; **all six qualifications must be re-run** against the hardened code |
| 2 | The C1 v2 text | `T0_1_C1_v2.md` v2, incl. **Appendix A** | ✅ — A1's normative scope is now **inside** C1 rather than delegated to a gitignored file; A5 points at a frozen schema |
| 3 | `claim_support_state` **with precedence** | `T0_3…` §4 + §4.6 | ✅ |
| 4 | The receptor decision | A + B-control; B-default not activated | ✅ |
| 5 | **Both** matrices, named separately | `T0_2b…` §5 — `notebook_evidence_matrix` now **11 identities**, exactly enumerated; `case_study_release_matrix` 50 | ✅ — v1's "5 × 3" read as a full factorial and overstated it |
| 6 | The Hub feasibility threshold | `T0_0…` §6 + `T0_5…` v2 | ✅ — but see §7: the probe rule was **wrong in v1** and is corrected |
| 7 | Exhaustive claim inventory | `T0_2a…` | ⏳ **pending** — the detector required a result word **AND** a number, so unnumbered claims were invisible. "249/249" was coverage over *detected* candidates. A word-only net is being added; the gate will go **red** and must be re-judged |
| 8 | Exact metric algorithm per metric | `T0_2b…` §2 | ⏳ **pending** — the `t_first_detection` scope-out rested on a search the detector structurally could not perform. **Provisional** until re-derived against the new net |
| 9 | Sequences + stopping rules | `T0_2b…` §3 | ✅ — now with exact cardinality |
| 10 | Predeclared **causal-support rule** | `T0_2b…` §4 | ✅ |
| 11 | Vocabulary crosswalk + precedence | `T0_3…` §1, §4.1b | ✅ |
| 12 | Artifact schema | **`T0_2b…` §5.1** | ✅ — v1 pointed at T0.0 §2, which freezes the *demo result payload*, a different object from the **T2 evidence artifact**. The evidence-artifact schema is now frozen, including the mandatory `run_role` |
| 13 | Named, dated approval | §6 below | ⬜ outstanding |

**8 complete · 3 pending · 1 outstanding.** No item is asserted complete on a pointer alone.

## 3. Evidence, not assertions

| Claim | Evidence |
|---|---|
| The canonical gate can pass | **6 pairs / 12 cold runs**, exact normalised equality every time; `refine_radius_used = 70.0` and `ncpl = 4408` on 12/12; **SIGILL 0/12**; mean **14.61 s** per side. Reports + SHA256SUMS in `evidence/t0_qualification/` |
| The harness implements the gate | `compare` mode, side-aware schema validation, the §3 lift table, path-aware `ARRAY_PAIR` ordering; **31** unit tests; `compare` against the current branch correctly aborts with `missing=['sink_support_m','t_peak']` |
| The inventory is exhaustive and judged | 249/249 typed by **two independent raters per surface**; gate exits 0; **77** tests green across both suites |
| The surfaces are real | generated by import-walk and AST, correcting the plan three times (**12** modules not 4; **5** test suites not 3; **25** keys not 22) |

---

## 4. Open elsewhere — and why none blocks T0

| Item | Owner | Why not a T0 blocker |
|---|---|---|
| **Regulatory threshold values, PFOA especially** | lecturer → T3/T4 | A live legal fact consumed by the *notebooks*, not by the canonical contract. No T0 document depends on the value |
| **The tenth case** | case-study track | T0 freezes the contract and the contract already says **ten**. Supply is ample (21 viable candidates) and none exceeds G0, so the probe rule does not fire |
| **M0's detection floor** | M0 | `t_first_detection` is **scoped out** of the transport notebooks on evidence — no inventoried claim uses one |
| **C1 §4 rebaseline table is empty** | T2 | By design. T0 does not pre-approve rebaselines it has no evidence for |
| **`_src_sha` misses `disv_grid_utils`** | T1 (allow-list **A8**) | A recorded defect with an authorised fix. Fixing it now would itself be a T1 source edit, which §6 blocks |
| **Fine-run feasibility may fail** | T2 | **Predeclared** in `T0_5…` §2 with its failure edges named, before the measurement |

---

## 5. What signing does — and does not — do

**Does:** unblocks T1 source edits within the C1 allow-list (A1–A9) — `GridSpec`, the `courant_nstp`
canonicalisation, the B-control arm, the artifact, the `_src_sha` fix, the pre-authorised payload fields.

**Does not:**
- ❌ **Activate anything.** The **JAG is the sole activation boundary**. Through T1–T4 the teaching default
  is numerically unchanged and the allow-list is **inert**.
- ❌ **License an interpolated default.** `t_peak` is the **lattice alias** of `arrival_day` through T1/T2;
  the interpolated evaluator lives in `exp/vN` and activates at the JAG.
- ❌ **Approve any rebaseline.** C1 §4 is empty and T2 fills it.
- ❌ **Extend beyond this environment.** The §5.1 qualification is same-environment by construction; a
  Hub-side gate needs its own.

**Changing any signed item afterwards is a failure edge to T0, never an in-flight edit.**

---

## 6. Approval

| | |
|---|---|
| **Record version** | v1 |
| **Prepared** | 2026-08-20 |
| **Constituent versions** | T0.0 v3 · C1 v2 v1 · T0.2a schema v2 · T0.2b v3 · T0.3 v2 · T0.5 v1 |
| **Approved by** | *(name)* |
| **Approval date** | *(date)* |

**By signing, the lecturer confirms:** the tolerances (`TOL_CONC_REL` 2% · `TOL_TIME_REL` 2% ·
`TOL_WIDTH_REL` 5%) · the Hub thresholds (`600` / `900` / `2.0`) · the receptor decision (A + B-control,
**not** B-default) · the predeclared verdict **`hypothesis`** · the `arrival_day` → `t_peak` **name**
(not an interpolated value) · and the claim-typing rules R0–R4.

---

## 7. What the consolidated review changed *(2026-08-20)*

The final pre-signature review returned **DO-NOT-SIGN**. Recorded here rather than quietly patched,
because two of the findings were errors of reasoning, not typos.

| # | Finding | Disposition |
|---|---|---|
| 1 | **The probe rule was wrong.** `T0_5…` v1 ranked the roster by **injection↔extraction separation** and named `b010210`. But the corridor is refined **spill→extraction** and the step count scales with the **horizon** — neither is well spacing. On the correct proxy `b010210` is the **second-cheapest** of nine, and `b010227` is **50× larger** | **Accepted, verified, corrected.** `T0_5…` v2 §1 freezes `spill_distance × horizon`, selects `b010227`, and requires a **T2 pilot** to confirm or overturn it. The error is left on the record |
| 2 | **"Exhaustive" was an overclaim.** The detector requires a result word **AND** a number, so unnumbered claims are invisible — including a student-facing causal claim in `01t` cell 6 | **Accepted.** A word-only prose net is being added; exit items 7 and 8 reopened |
| 3 | **The detection scope-out was circular** — its evidence was a search the detector could not perform | **Accepted.** Marked **provisional** in `T0_2b…` §2.5 pending re-derivation |
| 4 | **Signing §6 would not have activated T0.0**, which kept its own signature block and a stale v2 stamp | **Accepted.** T0.0 §7 now delegates to §6 here; there is exactly one signature |
| 5 | **The harness validates keysets, not value types** — a numeric string passed where a float is declared | **Accepted.** Being hardened; **all six qualifications must be re-run**, since the preserved evidence predates the fix |
| 6 | **`nstp_cap` is a resource guard, not the resolution criterion** — v1 wrongly made every cap increase a T0 decision | **Accepted.** `T0_5…` §2.1 separates them: relaxing `cr_target` is a T0 failure edge; raising a resource ceiling to *measure* uncapped demand is engineering |
| 7 | Matrix cardinality, artifact schema, A1's gitignored dependency, the pinned-surfaces generator | **All accepted and fixed** (§2 rows 5, 12, 2) |

⚠️ **One review claim was checked and REJECTED:** it stated the group pathway "already defaults to
`nstp_cap = 4000`", citing `transport_base_model.py:397`. That line is a function definition; the actual
defaults are **1000** (`:147`, `:210`) and 2000 in the demo. The 4000 it saw is a **comment** describing a
past run. The reviewer's *conceptual* point (finding 6) stands regardless.