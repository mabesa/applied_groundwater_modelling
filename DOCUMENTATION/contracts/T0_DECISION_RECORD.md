# T0 — The single decision record

**Milestone:** T0 (Contract closure) of `transport_notebook_milestones.md` (READY v7).
**Status:** ✅ **SIGNED v3, RE-SIGNED v4 — 2026-08-20, Beatrice Marti** (re-signature covers C1 v5,
amendments 1–3; see §8).
All twelve substantive exit items closed (§2). **T0 is CLOSED and T1 source edits are unblocked**, within
the C1 allow-list (**A1–A14**, as amended) and subject to §5's limits.
The codex consolidated review returned **DO-NOT-SIGN** on v2; its findings were folded in and §7 records
what changed.

This is the one record the milestone's T0 exit requires. It does **not** restate the contracts — each is
frozen in its own file, and restating them is exactly how a narrower duplicate got adopted twice during
planning. It **assembles** them, checks completeness item by item, and carries the single signature.

---

## 1. What T0 froze

| Doc | Version | What it freezes |
|---|---|---|
| `T0_0_canonical_contract.md` | **v3** | The canonical default-preservation gate: exact invocation · cold-workspace policy · the payload (the **entire** public `SrcPulseDemo` surface, with the 9 `mass_balance` / 17 `meta` / 9 `locked` keys enumerated) · the normalisation · the two-process harness · the §5.1 qualification · the Hub thresholds |
| `T0_1_C1_v2.md` | **v5** (re-signed; amendments 1–3) | C1 v2: enumerated surfaces (**generated**) · invariant gates with per-milestone scoping · the versioned change allow-list (**A1–A14**, as amended) · the numeric-rebaseline table |
| `T0_1_pinned_surfaces.md` | generated | The **32** result-derived pins in tests and modules — input to C1 §4 |
| `T0_2a_claim_inventory.json` / `.md` | schema **v3** | **427** candidates / **458** typed assignments over **three** detector nets; **gate exits 0** |
| `T0_2b_metrics_and_causal_rule.md` | **v4** | Metric algorithms + interpolation · sequences and stopping rules · the three tolerances · the causal-support rule and the `causal-physics` / `causal-numerical` split · both matrices · the claim-typing rules R0–R4 |
| `T0_3_claim_support_state.md` | **v2** | `claim_support_state`: three states · thirteen reason codes · the ordered gate pipeline · the total compute truth table |
| `T0_5_feasibility_probe.md` | **v2** | The probe **rule** — max `spill_distance × horizon` over the release roster, currently **`b010227`**, confirmed by a T2 pilot · the cold/warm protocol and gating statistic · the T2 / M3–M6 division of labour · the predeclared feasibility risk. *(v1 ranked by well separation and named `b010210` — retracted, §7)* |

---

## 2. Completeness check against the T0 exit

🔴 **v1 of this record claimed "12 of 13 complete". That was not supportable** — the codex consolidated
review audited it and found several rows pointing at something thinner than the exit requires. The table
below is the corrected audit, and it is deliberately unflattering: **three items are still open, and the
record is NOT signable until they close.**

| # | Required by the T0 exit | Where | Status |
|---|---|---|---|
| 1 | T0.0's frozen canonical contract | `T0_0…` §§1–5; approval **delegated** to §6 here | ✅ — typed path→class validation runs **before** normalisation and aborts by named path; the permissive test was **deleted**, not supplemented; **all six qualifications re-run** against the hardened harness (6/6 PASS, 0 mismatches); evidence carries `harness_identity` and no longer leaks machine paths |
| 2 | The C1 v2 text | `T0_1_C1_v2.md` v2, incl. **Appendix A** | ✅ — A1's normative scope is now **inside** C1 rather than delegated to a gitignored file; A5 points at a frozen schema |
| 3 | `claim_support_state` **with precedence** | `T0_3…` §4 + §4.6 | ✅ |
| 4 | The receptor decision | A + B-control; B-default not activated | ✅ |
| 5 | **Both** matrices, named separately | `T0_2b…` §5 — `notebook_evidence_matrix` now **11 identities**, exactly enumerated; `case_study_release_matrix` 50 | ✅ — v1's "5 × 3" read as a full factorial and overstated it |
| 6 | The Hub feasibility threshold | `T0_0…` §6 + `T0_5…` v2 | ✅ — but see §7: the probe rule was **wrong in v1** and is corrected |
| 7 | Claim inventory — **declared coverage**, not "exhaustive" | `T0_2a…` | ✅ — **three** detector nets (`r_and_n` 249 · `r_without_n` 132 · `word_only` 46) = **427 candidates**, gate **exits 0**. The original single net saw **58%** of this. The word "exhaustive" is retired: no net can prove it, so the tool now claims declared coverage with each detector's blind spot named |
| 8 | Exact metric algorithm per metric | `T0_2b…` §2 | ✅ — re-derived against the new nets: across the whole corpus there is **exactly one** unnumbered detection-language candidate (`01t` cell 6), and the three originally cited hits were all already-numbered. The `t_first_detection` scope-out stands, now on evidence that can see the claims |
| 9 | Sequences + stopping rules | `T0_2b…` §3 | ✅ — now with exact cardinality |
| 10 | Predeclared **causal-support rule** | `T0_2b…` §4 | ✅ |
| 11 | Vocabulary crosswalk + precedence | `T0_3…` §1, §4.1b | ✅ |
| 12 | Artifact schema | **`T0_2b…` §5.1** | ✅ — v1 pointed at T0.0 §2, which freezes the *demo result payload*, a different object from the **T2 evidence artifact**. The evidence-artifact schema is now frozen, including the mandatory `run_role` |
| 13 | Named, dated approval | §6 below | ⬜ outstanding |

**12 complete · 1 outstanding (the signature).** No item is asserted complete on a pointer alone.

**Claim inventory, final:** 427 candidates · 458 assignments · **30 compound spans** ·
`not_a_claim` 223 · `causal` **131** · `numeric` 61 · `threshold-decision` 34 · `illustrative` 9.
Every candidate judged by **two independent raters** (84% / 65% / 74% agreement across the three passes),
with the residue resolved by the recorded rules R0–R4 rather than case by case.

⚠️ **The causal set tripled — 42 → 131.** That is the honest measure of the T3 rewrite surface, and it was
invisible while one detector net was doing the work.

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

**Does:** unblocks T1 source edits within the C1 allow-list (**A1–A14**, as amended) — `GridSpec`, the `courant_nstp`
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
| **Record version** | **v4** (re-signed) |
| **Prepared** | 2026-08-20 |
| **Constituent versions** | T0.0 **v3** · C1 **v5** (Appendices A + B, amendments 1–3) · T0.2a schema **v3** · T0.2b **v4** · T0.3 **v2** · T0.5 **v2** |
| **Approved by** | **Beatrice Marti** |
| **Approval date** | **2026-08-20** (original) · **2026-08-20** (re-signature covering C1 v5) |
| **Evidence at signature** | 6/6 qualification pairs PASS, 0 mismatches (`evidence/t0_qualification/`, SHA256SUMS verified) · claim gate exits 0 at **427/427** · **127** tests green |

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

---

## 8. Post-signature amendments

The signature of §6 stands. This section records changes made to the signed set **after** it, so the set is
never silently different from what was signed.

| # | Date | Document | Change | Re-signed? |
|---|---|---|---|---|
| **1** | 2026-08-20 | `T0_1_C1_v2.md` → **v3** | Added allow-list entries **A10–A14** — content-addressed workspaces · fixed source footprint · operator A · GWF-grid sensitivity arm · `claim_support_state` evaluator | **No** — lecturer decision; bounded by C1 §3.1 |
| **2** | 2026-08-20 | `T0_1_C1_v2.md` → **v4** | **A8 extended to `transport_prt_capture.py`**, which carries its own `_src_sha()` with the identical three-file hole; plus **Appendix B**, the tracked and hashed T1 build-list snapshot | **Yes, retrospectively** — see amendment 3 |
| **3** | 2026-08-20 | `T0_1_C1_v2.md` → **v5**, **RE-SIGNED** | **A7's surface widened** to a new `exp`-only metrics module; **amendments 1–3 re-based on the signature** rather than on derivation from Appendix B | **YES** |

**What happened.** The T1 plan review found that C1's A1–A9, though signed, **omitted five changes the T1
build list requires**. Because C1 §3 makes an unlisted change a defect, **no implementation could satisfy
both the frozen contract and T1's required build list** — T1 was unstartable. All five were already in the
READY milestone plan's T1 build list before the signature, so this corrected an **enumeration error**, not
the scope.

**The bound, and the hole in it that round 2 found.** C1 §3.1 limits amendments to entries already required
by pre-existing scope — but v3 pointed that rule at the **gitignored** milestone plan, from which no
signature-time text can ever be recovered, making the bound unverifiable. **C1 §0/Appendix B (amendment 2)
closes it**: the T1 build list is now copied into the contract, tracked and SHA-256'd, and amendments cite
**it**. This is the same defect C1 had already fixed once for the vision document in Appendix A.

⚠️ **Amendment 1 predates Appendix B**, so its authority rests on two independent readings of the milestone
plan — the assistant's and the reviewer's — rather than on a hash. Amendment 2 onward are anchored. The
lecturer declined to re-sign.

⚠️ **Recorded dissent.** The assistant recommended taking the failure edge and re-signing, on the ground
that an allow-list able to grow without a signature weakens what the signature attests. The lecturer chose
to amend without re-signature; §3.1 is the agreed bound.

**Also corrected by the same review, in the plan rather than the contracts:** the per-step gate cannot run
before the pre-authorised payload fields exist (`t0_gate_harness.py` validates the candidate side against
`CANDIDATE_TOP_LEVEL_FIELDS` unconditionally), and the six passing runs recorded in §3 were **`qualify`**,
not `compare` — `compare --candidate b685f24` would fail candidate-schema validation. The T1 plan is being
reworked accordingly.

### 8.1 🔴 Why the re-signature happened — the unsigned path failed its first test

The amendment rule permitted unsigned amendments only for changes already required by Appendix B.
**Amendment 2 exceeded that bound the first time it was used**: Appendix B requires PRT to *consume* the
same `GridSpec`; it says nothing about extending PRT's `_src_sha()`. That derivation was an **inference,
not an entry** *(codex T1 review round 3, §2)*. The same applied to the new metrics module S11 needs, which
A7's single-file surface did not cover.

The bound could not be repaired by widening Appendix B — **changing the authorising source is exactly what
the bound forbids**. So the lecturer re-signed on 2026-08-20, and amendments 1–3 now rest on that signature.
**§3.1 remains in force for future amendments**: cite Appendix B, or be signed.

**What this cost:** one signature. **What it caught:** two allow-list entries that would have been used as
authority for source edits without ever having been authorised — found before any code was written.