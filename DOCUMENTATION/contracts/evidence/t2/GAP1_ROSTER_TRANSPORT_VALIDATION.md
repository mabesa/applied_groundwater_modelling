# Gap 1 pre-freeze check — the transport problem run for all 13 student groups

**Date** 2026-09-01 · **Branch** `main` (`4747073`) · **Platform** macOS (hub column = Mac x H, H = 2.169)
**Question asked** (lecturer): before freezing the case-study geometries, are the 13 student
transport problems *solvable* and *meaningful*?

**Answer: 12 of 13 are solvable; group 4 is not, on the geometry currently shipped.** The cause is a
degenerate mesh, not the solver. A verified fix exists. Two further defects are recorded below.

## 1. The roster as shipped

Run through `build_spill_scenario` from `case_config_transport.yaml`, `nstp_cap=40000`,
`Cr` target 0.9. `peak/limit` is receptor peak concentration divided by the group's threshold.

| g | contaminant | peak/limit | t_peak (d) | horizon (d) | Mac s | hub s | status |
|---|---|---|---|---|---|---|---|
| 0 | Trichloroethylene | 148.31 | 16 | 60 | 15.5 | 34 | runs |
| 1 | Nitrate | 0.007 | 18 | 30 | 24.7 | 54 | runs |
| 2 | Benzene | 23.65 | 14 | 60 | 45.6 | 99 | runs |
| 3 | Chloride | 0.53 | 705 | 730 | 238.6 | 518 | runs |
| 4 | Chromium (Cr-VI) | — | — | 730 | — | — | 🔴 **FAILS** |
| 5 | PFOA | 49.76 | 12 | 30 | 8.8 | 19 | runs |
| 6 | Perchloroethylene | 46.54 | 188 | 1095 | 190.0 | 412 | runs |
| 7 | Ammonium | 5.74 | 636 | 730 | 96.5 | 209 | runs |
| 8 | Atrazine | 0.07 | 60 | 60 | 9.4 | 20 | runs, **truncated** |
| 9 | MTBE | 1.89 | 48 | 365 | 103.1 | 224 | runs |
| 10 | Carbamazepine | 1.47 | 113 | 365 | 38.8 | 84 | runs |
| 11 | Boron | 0.44 | 365 | 365 | 177.3 | 385 | runs |
| 12 | Nickel | 1.16 | 519 | 1095 | 130.3 | 283 | runs |

All 13 reach the receptor. No run was Courant-capped. Worst hub time among the 12 that run is
**518 s (group 3)**, inside the 15-minute student budget.

## 2. 🔴 Group 4 fails — degenerate mesh, not the solver

MODFLOW terminates at stress period 2, ~time step 1045 of 2432 ("Solution 2 did not converge").
Mass balance is 0.00 % — nothing is leaking; the concentration field is diverging:

| time (d) | min c | max c | negative cells |
|---|---|---|---|
| 0.33 | -0.007 | 13.0 | 33 |
| 158.7 | -71.9 | 65.9 | 472 |
| 316.9 | -5.2e9 | 5.7e9 | 445 |

Source concentration is 13 mg/L. Growth is ~2.5 %/step, compounding over 1000+ steps.

**Not the solver.** Four GWT solver configurations were run on the full production problem; all
four fail at essentially the same step:

| GWT setting | outcome |
|---|---|
| MODERATE | fails, step 1048 |
| COMPLEX (A18, current default) | fails, step 1043 |
| SIMPLE | fails, step 1015 |
| explicit, `under_relaxation=NONE` | fails, step 1053 |

Switching the advection scheme TVD -> UPSTREAM also fails (step 842).

**Controlled 2x2 — the mesh decides, the solver decides nothing.** Running the *clean* mesh under
the *old* solver setting completes the design:

| mesh | GWT solver | outcome | peak/limit |
|---|---|---|---|
| degenerate r70 | MODERATE / COMPLEX / SIMPLE / no-under-relaxation | all fail | — |
| clean r90 | COMPLEX | passes | 0.9480657 |
| clean r90 | MODERATE | passes | 0.9480657 |
| clean r62 | COMPLEX | passes | 0.8060477 |
| clean r62 | MODERATE | passes | 0.8060479 |

Mesh choice flips pass/fail. Solver choice changes nothing — clean-mesh MODERATE and clean-mesh
COMPLEX agree to seven significant figures. ⚠️ The *mechanism* (ill-conditioning from tiny cells
versus local Courant far above 1 in cells the time-step sizing ignores) is **not** separately
established here; the two are confounded and no condition-number evidence was collected. What is
established is that the geometry determines the outcome and no solver setting rescues it.

⚠️ **This corrects the basis recorded for A18.** A18 was justified on group 4 failing the *pilot*
solve under MODERATE, and was never validated against a *production* run. On the production run
MODERATE and COMPLEX fail alike, and on a clean mesh both succeed with identical answers. So A18
neither causes nor cures this failure, and it does not change the number group 4 reports. That is
the bounded claim; whether A18 is still wanted for the pilot-stage behaviour it was actually
adopted for is a separate question this evidence does not settle.

**The actual cause.** The blow-up is confined to a cluster of cells within ~1 m of each other at
(2682715, 1248420), sizes **0.061–0.576 m**, in a grid whose refined target is 10 m and whose
median cell is 52.5 m. Sub-metre cells make the transport matrix badly conditioned.

## 3. 🔴 The refinement ladder picks the first radius that BUILDS, not the first that is CLEAN

`_refine_with_retry` walks `refine_radii = (70, 62, 78, 56, 84)` and stops at the first radius that
produces a model that runs. For group 4 that is 70 — **the worst of all of them**:

| radius | builds | ncpl | min cell | cells <1 m | cells <2 m |
|---|---|---|---|---|---|
| **70 (shipped)** | yes | 4884 | **0.068 m** | **225** | 403 |
| 62 | yes | 4398 | 2.441 m | 0 | 0 |
| 78 | no | — | — | — | — |
| 56 | yes | 4437 | 2.324 m | 0 | 0 |
| 84 | yes | 4344 | 1.393 m | 0 | 4 |
| 90 | yes | 4371 | 4.062 m | 0 | 0 |

**Verified fix — group 4 completes and is physical on either clean radius:**

| radius | ncpl | min cell | peak/limit | t_peak | field min/max | Mac s | hub s |
|---|---|---|---|---|---|---|---|
| 62 | 4398 | 2.441 m | **0.806** | 121 d | -0.014 / 13.0 | 232.2 | 504 |
| 90 | 4371 | 4.062 m | **0.948** | 136 d | -0.038 / 13.0 | 157.8 | 342 |

Both bounded by the 13 mg/L source, both inside budget, both land just under the legal limit.
The 18 % spread in peak between the two radii is mesh sensitivity; the compliance verdict
(under the limit, but marginally) is the same either way.

## 4. ⚠️ 8 of the 13 shipped meshes contain sub-metre cells

| g | ncpl | min cell | <1 m | <2 m | verdict |
|---|---|---|---|---|---|
| 0 | 4512 | 1.700 | 0 | 16 | watch |
| 1 | 4462 | 0.994 | 1 | 11 | has slivers |
| 2 | 4508 | 4.512 | 0 | 0 | clean |
| 3 | 4755 | 0.631 | 50 | 186 | has slivers |
| 4 | 4884 | 0.061 | 225 | 403 | **failed** |
| 5 | 4120 | 2.538 | 0 | 0 | clean |
| 6 | 4736 | 0.445 | 13 | 27 | has slivers |
| 7 | 4302 | 1.604 | 0 | 16 | watch |
| 8 | 4512 | 0.136 | 41 | 104 | has slivers |
| 9 | 4615 | 2.414 | 0 | 0 | clean |
| 10 | 4641 | 0.248 | 14 | 43 | has slivers |
| 11 | 4444 | 0.155 | 82 | 174 | has slivers |
| 12 | 4359 | 0.812 | 2 | 21 | has slivers |

Only groups 2, 5 and 9 are clean.

🔴 **These are not merely a latent risk — at least one shipped answer is materially wrong.** An
earlier draft of this report claimed the sliver-bearing runs were safe because each stays bounded
by its own source concentration with undershoot ≤0.5 %. That test is too weak, and a direct
remesh falsifies the claim. Group 11 (82 sub-metre cells) re-run across four meshes:

| radius | sub-metre cells | peak/limit | t_peak |
|---|---|---|---|
| **70 (shipped)** | 82 | **0.435** | 365 d |
| 56 | 185 | 0.608 | 271 d |
| 84 | 0 | 0.619 | 365 d |
| 90 | 0 | 0.601 | 365 d |

The shipped geometry is the low outlier: it **understates group 11's receptor peak by about 30 %**
against meshes that contain no sub-metre cells. The two sliver-free meshes (84, 90) agree within
3 % of each other. Note that mesh *cleanliness* alone does not predict agreement — radius 56 has
the most slivers of all and still lands with the clean pair — so "no cells below 1 m" is a
necessary screen, not a sufficient one; agreement between independent meshes is the real test.

Group 4 is the case where the defect escalates from a wrong number to no answer at all, plausibly
because its retardation (R≈19) keeps the plume in the corridor for 1000+ time steps.

**Interaction with `courant_nstp`.** The sliver floor (`sliver_floor_frac=0.4`, i.e. 4 m at a 10 m
refined size) excludes all 554 sub-4 m cells of group 4 from time-step sizing. The run therefore
reports `Cr = 0.9` while its smallest cells run at a local Courant of order 150. This is the
already-known "silently ignores refined cells" defect; this is the first time it has been shown to
produce an outright failure rather than an inaccuracy.

## 5. ⚠️ Group 8's horizon cuts off its own peak

Groups 8 and 11 both reported their peak at the final time step. Re-run longer:

| g | shipped horizon | true t_peak | shipped peak/limit | true peak/limit | verdict |
|---|---|---|---|---|---|
| 8 | 60 d | 125 d | 0.070 | **0.178** | understated 2.5x |
| 11 | 365 d | 523 d (plateau) | 0.435 | 0.435 | unchanged |
| 3 | 730 d | 1269 d | 0.532 | 0.532 | unchanged |

Group 8's 60-day window ends while the curve is still rising; students would read a peak that is
2.5x too low off a plot that visibly has not turned over. The compliance verdict stays "under the
limit" either way. Groups 11 and 3 sit on a plateau — their numbers are robust.

## 6. Meaningfulness: the difficulty spread is very wide

| band | groups | what the student concludes |
|---|---|---|
| >20x over limit | 0 (148x), 5 (50x), 6 (47x), 2 (24x) | obvious exceedance |
| 1–6x over | 7 (5.7x), 9 (1.9x), 10 (1.5x), 12 (1.2x) | genuine judgment call |
| just under | 4 (0.81–0.95x), 3 (0.53x), 11 (0.44x) | genuine judgment call |
| far under | 8 (0.18x), 1 (0.007x) | obvious compliance |

⚠️ These ratios are computed on the shipped meshes, which section 4 shows can be ~30 % off, and
group 4's row comes from a replacement geometry. Treat the banding as indicative, not settled.

Two further cautions on reading this table. A concentration ratio alone does not establish that a
case is a "genuine judgment call" — that depends on the reasoning the task demands, not only on
how close the number sits to the limit. Nor is a large exceedance automatically less instructive:
groups 0, 2, 5 and 6 still have to size and defend a remediation response. What the table does
show is that the *compliance verdict itself* is a foregone conclusion at the two extremes
(group 0 at 148x over, group 1 at 140x under) and genuinely open in the middle.

## 7. What this means for freezing

The original Gap 1 task was to freeze Linux goldens for groups 9–12. **It should not proceed as
scoped.** The rule that *selects* a geometry is defective for all 13 groups, group 4's shipped
geometry cannot run at all, and group 11's shipped geometry returns a peak ~30 % below what
sliver-free meshes give. Freezing now would pin those defects.

The minimum control before any geometry is frozen: the chosen mesh must contain no sub-metre
cells, **and** the receptor peak must agree with an independently chosen clean mesh closely enough
that the threshold decision cannot flip. Group 11's clean pair agrees within 3 % and would pass;
**group 4's two clean meshes differ by 18 % (0.806 vs 0.948) and would fail**, with the higher
value close enough to 1.0 that mesh noise alone could cross the limit. Group 4 therefore needs
more than a radius swap.

Decisions required from the lecturer are carried in the session summary.

## Reproduction

`GAP1_all13.json`, `GAP1_all13_b.json` (roster), `GAP1_g4_ab.json`, `GAP1_g4_ab2.json`,
`GAP1_upstream.json` (solver and scheme A/B), `GAP1_g4_mesh2.json` (radius sweep),
`GAP1_g4_rad.json` (fix), `GAP1_horizon.json` (horizon probe), `GAP1_control_2x2.json`
(mesh-vs-solver control), `GAP1_conv_g11.json` (group 11 remesh), all in this directory.

**Review.** Reviewed adversarially by `codex` on 2026-09-01, which returned BLOCK on the first
draft. Three of its findings are incorporated above: the mechanism claim is now bounded (section
2), the A18 correction is narrowed to what the 2x2 supports (section 2), and the "latent risk"
claim was tested and falsified (section 4). Its headline fix — a geometry acceptance test
requiring the receptor peak to be stable across independent clean meshes before freezing — is
adopted in section 7.

---

# Part 2 — the P1 re-pick survey, and what it found instead

Run 2026-09-01 after the lecturer authorised A19. P1 was meant to choose a clean radius per group.
It did that, and in doing so found something larger: **the 10 m corridor is not a converged
discretisation for this problem, for anyone.**

## 8. P1 results — 3 of 12 groups pass

Candidate radii 56 / 62 / 70 / 78 / 84 / 90; G1 = no cell below 1 m; G2 = the two most widely
separated G1-passers agree within 10 %.

| g | contaminant | G1-passing radii | pair | spread | status |
|---|---|---|---|---|---|
| 0 | Trichloroethylene | 62, 70, 84, 90 | 62 / 90 | 15.3 % | FAIL G2 |
| 1 | Nitrate | *none* | — | — | no clean mesh |
| 2 | Benzene | 62, 78, 84 | 62 / 84 | 21.9 % | FAIL G2 |
| 3 | Chloride | 56, 90 | 56 / 90 | **1.4 %** | ✅ PASS |
| 5 | PFOA | 56, 62, 70 | 56 / 70 | 15.9 % | FAIL G2 |
| 6 | Perchloroethylene | 56 only | — | — | no second clean mesh |
| 7 | Ammonium | 56, 70, 84 | 56 / 84 | — | run failed |
| 8 | Atrazine | 78 only | — | — | no second clean mesh |
| 9 | MTBE | 56, 70, 84 | 56 / 84 | **8.2 %** | ✅ PASS |
| 10 | Carbamazepine | 78 only | — | — | no second clean mesh |
| 11 | Boron | 84, 90 | 84 / 90 | **3.0 %** | ✅ PASS |
| 12 | Nickel | *none* | — | — | no clean mesh |

Typical disagreement between two meshes of the same nominal 10 m corridor is **15–22 %**.

## 9. Refining to 5 m makes it WORSE, and busts the budget

Group 4 at a 5 m corridor (A19):

| corridor | radius | ncpl | nstp | peak/limit | hub s |
|---|---|---|---|---|---|
| 10 m | 62 | 4398 | 3622 | 0.806 | 480 |
| 10 m | 90 | 4371 | 2534 | 0.948 | 333 |
| **5 m** | 62 | 5336 | 11074 | **0.317** | **1679** |
| **5 m** | 84 | 6142 | 11004 | **0.215** | **1903** |

Refinement does not converge the answer: the two 5 m meshes disagree by **47 %** (worse than 10 m's
17.6 %), and both sit ~3x below the 10 m answers. Hub cost rises to **28–32 min**, roughly double
the 15-minute student budget. **Decision 2 ("refine finer until two meshes agree") cannot be
satisfied by refinement** — that is a measured result, not a budget complaint.

## 10. Two candidate explanations, both tested and REJECTED

**Time-step sizing.** `courant_nstp`'s sliver floor excludes cells below 0.4 × corridor size, so a
mesh can run above its nominal Courant target in cells the sizing never sees. Re-running group 4
with the floor removed (A3 authorises this) gives **bit-identical results** — `nstp` 3622 and 2534
unchanged, peaks identical to 10 significant figures. The sub-4 m cells in this corridor are slow
and never bind. **Ruled out.**

**The receptor metric.** The peak is read from the single extraction-well cell, whose size and
boundaries move with every mesh. Re-deriving it as a volume-weighted average over cells within a
support radius, from the same four solved runs:

| receptor definition | spread across the 4 meshes |
|---|---|
| single well cell (current) | 17.6 % |
| average within 10 m | 34.7 % |
| average within 25 m | 28.8 % |
| average within 50 m | 13.7 % |

Averaging does not stabilise it — the small radii are markedly worse. **Ruled out** as the primary
cause.

⚠️ What remains is the mesh itself: independent Voronoi tessellations of the same corridor produce
genuinely different transport solutions at this resolution. This report does **not** establish the
mechanism, and the 5 m results are too few to claim a convergence direction. What it establishes is
the size of the disagreement, and that two plausible fixes do not remove it.

## 11. What actually matters: 11 of 13 verdicts survive it anyway

The quantity students report is a compliance verdict, not a concentration. Applying a **±25 %**
mesh uncertainty — comfortably wider than the 15–22 % observed — to each group's peak/limit ratio:

| verdict robust | groups |
|---|---|
| ✅ yes (11) | 0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11 |
| 🔴 can flip (2) | **4** (0.871 → 0.65–1.09) · **12** (1.155 → 0.87–1.44) |

So the discretisation problem is real but **narrow in consequence**: it threatens two groups'
conclusions, not thirteen. Groups 4 and 12 sit inside the band where mesh noise alone decides
compliance.

## 12. Recommendation

Chasing convergence is the expensive path and the measurements say it does not work at affordable
resolution. The proportionate path is to stop treating the mesh spread as a defect to eliminate and
start treating it as a quantity to report:

1. **Fix group 4's geometry** — it cannot run at all on radius 70. Any G1-passing radius works.
2. **Move groups 4 and 12 out of the knife-edge band** by adjusting their scenario (source
   strength, threshold, or pumping) so the verdict is robust to ±25 %. Config-only.
3. **State the mesh uncertainty to students** and require the verdict to be reported with it.
   This serves the course's stated aim — judging model quality and seeing how modeller decisions
   move outcomes — better than a falsely precise number would.
4. **Do not adopt the 5 m corridor.** It doubles hub cost, and it does not converge the answer.

Superseded by this part: Part 1 §7's plan to re-pick every geometry under a 10 % agreement rule.
That rule is unreachable at 10 m for 9 of 12 groups, and refinement does not deliver it.

---

# Part 3 — the two danger groups, fixed and verified

Lecturer instruction 2026-09-01: act on Part 2 §12 for groups 4 and 12, cross-checked by `codex`
first. `codex` returned **SHIP-WITH-CHANGES**; its changes are adopted and named in §15.

## 13. 🔴 Group 12's shipped geometry FLIPS its verdict

Group 12 had no mesh passing the ≥1 m screen in the original candidate set. A wider radius search
found two: **48** (min cell 1.194 m) and **88** (min cell 1.069 m). Re-run on those:

| mesh | min cell | peak/limit | verdict |
|---|---|---|---|
| radius 70 (shipped) | 0.812 m, 2 sub-metre cells | **1.155** | EXCEEDS |
| radius 48 | 1.194 m, clean | **0.826** | COMPLIANT |
| radius 88 | 1.069 m, clean | **0.930** | COMPLIANT |

**The shipped answer is not merely imprecise — it is on the wrong side of the limit.** This is the
third shipped geometry shown to be materially wrong (group 4 cannot run; group 11 reads ~30 % low).
It also reverses the fix direction planned for group 12: its honest baseline is compliant at ~0.88,
so the scenario is scaled to be *robustly compliant* rather than pushed up into a manufactured
exceedance the trustworthy meshes do not support.

## 14. The acceptance rule, and the fix

Replacing Part 1's ±25 % framing, which implied a statistical claim the evidence does not support:

> **Instructor acceptance rule.** Every validated mesh for a group must give a receptor peak
> **below 0.8** of the threshold (compliant) or **above 1.333** (exceeds). No group's assessed
> verdict may depend on which defensible mesh it happens to get.

Lever: the **source concentration**, a synthetic scenario-design value. The threshold is a legal
limit and is untouched. Transport here is linear in the source concentration (CNC source, linear
sorption, zero decay), so the peak scales proportionally — **verified to 0.06 %** below.

| g | radius pinned | c_src | peak/limit before | after | linearity error | verdict | hub s |
|---|---|---|---|---|---|---|---|
| 4 | **90** (was: ladder picked 70, unusable) | 13.0 → **9.0** | 0.806–0.948 | **0.656** | 0.00 % | COMPLIANT | 349 |
| 12 | **48** (was: ladder picked 70, verdict-flipping) | 8.0 → **5.5** | 0.826–0.930 | **0.568** | 0.06 % | COMPLIANT | 346 |

Projecting the remaining validated meshes through the verified linearity: group 4's four meshes give
0.558 / 0.568 / 0.630 / 0.656 and group 12's second mesh gives 0.639 — **every validated mesh for
both groups is below 0.8.** Both runs are sliver-free (min cell 4.062 m and 1.194 m), both inside
the 15-minute budget, and both bounded by their own source concentration.

**Changes made** (config + notebook only; no solver, no locked physics):
- `case_config_transport.yaml`: per-group `geometry.refine_radius_m` for groups 4 and 12;
  `concentration_mg_L` 13.0→9.0 and 8.0→5.5, each with the measurement recorded in a comment.
- `case_study_transport_group_0.ipynb`: reads the pinned radius and passes it to
  `build_spill_scenario`; group selector corrected from 0–8 to **0–12**; a new section states the
  ~±20 % mesh uncertainty and asks an **ungraded** question about reasoning under a marginal result.

⚠️ **A19 was authorised for more than was used.** It permits `refined_cell_size` to become
per-group; that was **not** done, because §9 measured the 5 m corridor to be both worse-agreeing
and over budget. Only the per-group *radius* is pinned. The student-facing "grid refinement is
locked" wording therefore needs no change, and §0's existing promise that the refinement "has been
tuned and tested for you" becomes true for the first time.

## 15. What `codex` changed in this step

- **Freeze the geometry before tuning concentrations** — otherwise the scale factor is fitted to a
  mesh that is about to be replaced. Adopted: radius pinned first, then scaled, then verified.
- **Drop the ±25 % band** as an uncalibrated statistical-sounding claim; state a plain instructor
  acceptance margin instead. Adopted as §14's rule.
- **Do not manufacture group 12's exceedance.** Adopted — see §13.
- **Label the concentrations as synthetic scenario-design values**, so tuning them cannot read as
  outcome engineering. Adopted in the config comments.
- **One linearity check is enough**, not four verification runs. Adopted.
- **Keep the marginal case as an ungraded discussion** rather than deleting the uncertainty lesson —
  "do not let a mesh lottery determine assessed answers". Adopted as the new notebook section.
- **Cut**: relaxing group 12's cleanliness screen (clean meshes now exist), the 1.155 figure from
  all baselines, and any appeal to preserving the roster's exceeds/complies balance — that count
  has no physical or pedagogical authority. All cut.

## 16. Still open

- The other 11 groups still rebuild their corridor from the generic ladder; 6 of them carry
  sub-metre cells. They are not verdict-threatened (§11), but their peaks carry the same 15–22 %
  and group 11's is ~30 % low. Pinning a validated radius for each is the remaining P2 work.
- Group 8's horizon (60 d, truncates its own peak at day 125) is **not yet changed**.
- Goldens for all 13 groups still need re-freezing on Linux once the radii are pinned.

## 17. Group 11 — radius pinned; the spill was NOT moved

Lecturer asked whether group 11's spill should move closer or carry more mass, and then whether its
runtime could be cut while keeping the problem interesting. Both premises were tested.

**Runtime was not the problem.** Group 11 runs in **385 s on the hub — 6.4 min against a 15-minute
budget**, third in the roster behind group 3 (517 s) and group 6 (412 s). No group exceeds 8.6 min.

**Moving the spill would have made it slower, not faster.** Its plume currently misses the capture
zone by 61 m laterally against a 76.7 m doublet separation. Closing that gap raises the peak sharply
— and costs time, because a plume that actually arrives needs more steps:

| spill position | distance | lateral miss | peak/limit | clean mesh | hub s |
|---|---|---|---|---|---|
| **current** | 70 m | 61.2 m | **0.619** | r84, min 5.088 m | **272** |
| moved | 70 m | 30.0 m | 2.017 | r90, min 2.223 m | 460 |
| moved | 70 m | 0.0 m | 4.117 | r84, min 2.029 m | 387 |
| moved | 50 m | 0.0 m | 3.166 | r90, min 4.616 m | 358 |

⚠️ Note the 50 m case is **lower** than the 70 m case on the same line (3.17 vs 4.12): the lateral
miss, not the distance, controls this scenario. "Move it closer" and "move it into the capture zone"
are different levers and only the second reliably bites.

**Action taken: pin radius 84, change nothing else.** It is simultaneously the cleanest mesh for
this corridor and the fastest, and it corrects a known error:

| | shipped (ladder picks r70) | pinned r84 |
|---|---|---|
| min cell | 0.156 m, 82 sub-metre cells | **5.088 m, none** |
| peak/limit | 0.435 (~30 % low) | **0.619** |
| hub runtime | 385 s | **271 s** (−30 %) |

Verified through the config path: 0.6187, `rule_pass` true, COMPLIANT, bounded by its 15 mg/L
source. **The scenario itself is untouched** — position and concentration unchanged — so group 11
keeps its "is the plume captured at all?" character, which is what makes it worth setting. Increasing
the source to force an exceedance would have needed ~35 mg/L boron, high for demolition-waste
leachate, and moving the spill would have answered the capture question for the students.

---

# Part 4 — every group now has a pinned, validated mesh

Lecturer instruction 2026-09-01: check the remaining groups' radii, confirm they finish and that the
case study is consistent and meaningful. Protocol as Part 2: build every candidate radius, keep those
with no cell below 1 m, solve transport on the two most widely separated survivors, and require the
**verdict** — not the concentration — to be stable.

## 18. Widening the search fixed every group that had too few clean meshes

The default ladder `(70, 62, 78, 56, 84)` is simply too narrow. Adding candidates rescued all four
groups that previously had fewer than two clean meshes:

| g | clean meshes in the ladder | after widening | found at |
|---|---|---|---|
| 1 | **none** | 42, 44, 50 | 42 / 44 / 50 |
| 6 | 56 only | 44, 48, 56 | 44 / 48 |
| 8 | 78 only | 44, 74, 78 | 44 / 74 |
| 10 | 78 only | 74, 78, 96 | 74 / 96 |
| 12 | **none** (Part 3) | 48, 88 | 48 / 88 |

⚠️ **Group 7's radius 56 fails its pilot solve outright** — the P1 "RUN_FAILED" was this, not a
scenario problem. Radii 70 and 84 both run. Another instance of the ladder's first-that-builds rule
selecting a radius that does not work.

## 19. The final roster — all 13 built exactly as the student notebook now does

Radius read from `geometry.refine_radius_m`, everything else from the shipped config:

| g | contaminant | radius | min cell | sub-metre | peak/limit | verdict | hub s | t_peak/T |
|---|---|---|---|---|---|---|---|---|
| 0 | Trichloroethylene | 90 | 5.32 m | 0 | 138.5 | EXCEEDS | 39 | 0.27 |
| 1 | Nitrate | 50 | 1.79 m | 0 | 0.0089 | COMPLIANT | 63 | 0.57 |
| 2 | Benzene | 62 | 4.51 m | 0 | 23.65 | EXCEEDS | 97 | 0.24 |
| 3 | Chloride | 90 | 4.39 m | 0 | 0.522 | COMPLIANT | 537 | 0.93 |
| 4 | Chromium (Cr-VI) | 90 | 4.06 m | 0 | 0.656 | COMPLIANT | 328 | 0.19 |
| 5 | PFOA | 70 | 2.54 m | 0 | 49.76 | EXCEEDS | 19 | 0.40 |
| 6 | Perchloroethylene | 44 | 2.03 m | 0 | 38.22 | EXCEEDS | 359 | 0.17 |
| 7 | Ammonium | 84 | 4.56 m | 0 | 6.58 | EXCEEDS | 209 | 0.95 |
| 8 | Atrazine | 44 | 1.67 m | 0 | 0.096 | COMPLIANT | 73 | 0.41 |
| 9 | MTBE | 56 | 1.92 m | 0 | 1.93 | EXCEEDS | 249 | 0.13 |
| 10 | Carbamazepine | 74 | 1.58 m | 0 | 1.51 | EXCEEDS | 79 | 0.33 |
| 11 | Boron | 84 | 5.09 m | 0 | 0.619 | COMPLIANT | 263 | 1.00 (plateau) |
| 12 | Nickel | 48 | 1.19 m | 0 | 0.568 | COMPLIANT | 329 | 0.58 |

**Every group: builds, finishes, no sub-metre cells, concentrations bounded by its own source, no
Courant cap, verdict robust (<0.8 or >1.333), inside the 15-minute budget.** Slowest is group 3 at
537 s; the whole roster is 2644 s of hub compute.

Selection rule for the pinned radius: among the two solved, take the **cleanest** mesh, tie-broken on
speed. The radius chosen and its measured min cell, runtime and peak are recorded in a comment beside
each `geometry:` block in the config.

## 20. Is the case study consistent and meaningful?

**Consistent — yes.** 7 groups exceed their limit, 6 comply, and no verdict depends on which
defensible mesh a student happens to get. The mesh spread that Part 2 measured (15–22 %, and 38 % for
group 8) is still there and is not removable, but it no longer decides anyone's answer.

**Meaningful — mostly, with a known asymmetry.** Distance from the limit:

| band | groups | what the student concludes |
|---|---|---|
| far over (>20x) | 0 (138x), 5 (50x), 6 (38x), 2 (24x) | exceedance obvious; the work is the remediation argument |
| clearly over (1.5–7x) | 7 (6.6x), 9 (1.9x), 10 (1.5x) | the number carries the argument |
| clearly under (0.5–0.66) | 4 (0.66), 11 (0.62), 12 (0.57), 3 (0.52) | real margin, still needs defending |
| far under (<0.1) | 8 (0.096), 1 (0.0089) | compliance obvious |

Seven of thirteen sit where the number does the work. Six are settled before modelling — four
obvious exceedances and two obvious compliances. ⚠️ This is a **pedagogy** observation, not a defect:
group 0's 138x and group 1's 0.009x are physically honest for a TCE spill and for nitrate that
largely bypasses the well. Levelling them would mean inventing scenarios. Recorded for the lecturer,
not acted on.

⚠️ **Group 10 is the tightest pass**: its two meshes give 1.51 and 1.38, and 1.38 clears the 1.333
rule by only 3.7 %. A third mesh landing lower could push it into review.

## 21. Group 8's horizon extended, 60 -> 365 d

Applied (lecturer decision 3). At 60 days the run ended while the curve was still rising and reported
the last time step as the peak. At 365 days the peak lands at **day 128–149**, `t_peak/T` = 0.41, and
the value rises from 0.070 to 0.096 of the threshold. Verdict unchanged (compliant); students now see
the curve turn over. Output times updated to `[30, 90, 180, 270, 365]`.

## 22. Remaining

- Goldens for all 13 still need re-freezing on Linux against these pinned radii.
- `canonical_mapping.csv` has no column for the pinned radius, so the instructor provenance record
  does not yet capture which mesh a group uses. Schema change, not done.
- The default `refine_radii` ladder is still a trap for any future caller: it is too narrow (it found
  no clean mesh at all for groups 1 and 12) and it stops at the first radius that builds.
