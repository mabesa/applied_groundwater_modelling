# Suggested grading scheme for the case study

> 🔴 **This is a suggestion for lecturers reusing this course, not a course rule.**
>
> **For students, whatever the course's own page publishes is what counts.** At ETH that
> is the Moodle course page: weighting, deadlines, the presentation slot, exam
> arrangements and the binding rubric live there, and they override everything below.
> This document does not establish any course's assessment rules.

Derived from the ETH HS26 run. Adapt freely; the parts most worth keeping are §3
(notebooks as evidence rather than a gate), §5 (one rule for evidential defects) and the
outcome-neutrality note in §2 — those three are where an assessment scheme for modelling
work usually goes wrong.

---

## 1. Components

| Component | Weight | Individual or group | Artifact |
|---|---|---|---|
| Written exam | **50 %** | individual | — |
| Group report | **20 %** | group, with named contributions | `report.pdf` |
| Oral presentation | **30 %** | shared mark + **individual defence mark** | `presentation.pdf` + the defence |
| Working notebooks | **no separate weight** | — | the submission ZIP |

🔴 **This scheme chooses not to make the notebooks a gate.** They are the evidence
report and oral claims are scored *against* — see §5.

That is a choice, not a consequence of the weights: a course may publish a gate instead.
If you do, define what passing it means before announcing it.

**One rule for evidential defects (§5).** Unsupported, unreproducible, incomplete or
overreaching work is scored **once**, inside the criteria. No deduction table, no cap,
no per-claim scoring — a deduction table layered on criteria double-charges the same
defect, which is easy to do accidentally and hard to defend.

**Suggested percentage → grade.** Linear, rounded to the nearest quarter step:

> **grade = 1 + 5 × (weighted percentage / 100)**, i.e. `1 + pct/20`

| % | 40 | 50 | **60** | 70 | 80 | 90 | 100 |
|---|---|---|---|---|---|---|---|
| Grade | 3.0 | 3.5 | **4.0 (pass)** | 4.5 | 5.0 | 5.5 | 6.0 |

Every 10 percentage points is half a grade, which makes it easy to explain.

⚠️ **Fix the pass boundary explicitly.** With rounding to the nearest quarter, 58 %
becomes 3.9 and rounds to **4.0** — so "60 % = pass" and "grade 4.0 = pass" are not the
same rule. Say which one binds.

**Suggested pass requirement: the weighted total only.** No component passed separately,
so a strong exam can carry a weak project and the reverse. **Say this explicitly to
students** — they will ask, and the answer changes how they allocate effort.

---

## 2. Report — 20 %

Marked out of 100, scaled to 20. Suggested length: 10 pages excluding title page,
references and appendix; appendix capped at 5 pages.

Mark each criterion holistically against its description. The descriptions carry the
standard; there is deliberately no separate band table.

| Criterion | Weight | What earns the top of the range |
|---|---|---|
| **Defensibility** | **30** | Each **computed** claim is traceable to a figure or table from the frozen bundle; conceptual and configuration claims cite their source. The limits of the evidence are stated before the reader has to ask. An unsupported claim costs in proportion to how much the report leans on it. |
| **Conceptual reasoning** | **20** | Assumptions named *with their consequences*. The assigned scenario's physical story is tied to the parameter that actually changed. |
| **Uncertainty and limits** | **20** | The mesh envelope carried on the transport peak and its consequence stated — **whether or not it flips the verdict**. A signal / artefact / instability judgment on the main flow result with the evidence that discriminates — **or a correct finding that the evidence cannot discriminate, and what would**. At least one limitation the group found and quantified themselves. |
| **Results: correct and integrated** | **20** | Required quantities present and correct, with units and the comparison they belong to. Organised **by finding, not by task**. Work that is simply absent is not credited here, whether or not the report claims anything from it. |
| **Communication** | **10** | Readable figures with honest captions; a conclusion that answers the question the report posed; a recommendation with the condition that would withdraw it. Over-length is scored here. |

> 🔴 **Outcome-neutrality.** No criterion requires a particular *result*. A
> verdict-flipping uncertainty envelope, a zero affected area, a no-reach plume and "the
> evidence does not settle this" are all top-of-range outcomes **when correctly
> established and honestly reported**.
>
> This does not make numbers unassessable: correctness, units and the required quantities
> are scored under *Results* as usual. A correct zero and an incorrect zero are not the
> same answer, and demonstrating that the evidence cannot discriminate is not the same as
> failing to look.

### How evidential defects are scored

Each defect is evidence that a **criterion** was not met. The table below names the
criterion a defect is *most obviously* evidence against — **not an exclusive
assignment**. One omission can leave several criteria's standards unmet at once (§1); what
must not happen is the same defect being charged twice for the same reason.

| Defect | Most obviously evidence against |
|---|---|
| A computed number nothing in the submission reproduces or supports | Defensibility |
| A claim the model cannot support | Defensibility |
| Required work absent or incomplete | Results |
| A transport peak quoted with no mesh envelope | Uncertainty and limits |
| A head-change number quoted without its convention | Results |
| Over the page limit | Communication |

---

## 3. Notebooks — the evidence base

Not marked separately. Used to (a) verify what the report and oral claim, and (b) see
each member's own contribution. **Spot-check; do not audit every notebook** — with 13
groups and 2–3 members each that is 26–39 notebooks, and reading them all establishes
neither authorship nor understanding. The oral does that.

Group-level, for navigation when marking:

- the required analysis cards are covered, with any short card's owner named in the
  submission README;
- the export bundle reports no missing required files;
- the contribution table is filled in — it tells you whose work to ask whom about.

---

## 4. Oral presentation — 30 %

Marked out of 100, scaled to 30. Split into a shared mark and an individual mark, so a
disputed mark can be pointed at a criterion.

**Shared, one mark for the group (60 points).**

| Criterion | Points | What earns the top of the range |
|---|---|---|
| **The decision** | 25 | A verdict a client could act on, with the condition that would change it. A justified *"do not act yet, and here is what would settle it"* is an actionable verdict; a tour of the modelling is not. |
| **Evidence selection** | 20 | Two or three figures that actually establish the verdict, chosen rather than pasted. |
| **Delivery** | 15 | Within the published slot, legible slides, units on everything, all members speak. |

**Individual, one mark per student (40 points): defence under questioning.**

| Band | Points | Descriptor |
|---|---|---|
| Excellent | 34–40 | Answers on any part of the group's work, not only their own. Separates what they measured from what they assumed. Concedes a limit cleanly when pressed rather than defending an overclaim. |
| Good | 28–33 | Sound on their own work, reasonable on the rest. |
| Satisfactory | 22–27 | Secure on their own work; vague beyond it. |
| Weak | 16–21 | Cannot account for work they owned or presented. |
| Fail | <16 | Cannot speak to the group's headline result at all. |

Ask each student at least two questions: one on work they owned, one outside it. A
rotating-stewardship rule in the group work exists so that no student has a structural
excuse for the second kind.

> 🔴 **Budget the time before you publish the slot.** Questions are where the individual
> mark — 40 % of the oral — is earned, and it cannot be recovered if the day overruns.
> With ~5 minutes of questions per student, a trio runs presentation + ~15 min and a pair
> presentation + ~10. Across 13 groups that is most of a day. **Check that against the
> sessions you actually have before announcing a slot length**; it is easy to publish a
> per-group slot that the question budget does not fit into.

> A missing or broken **file** is never charged to an individual here; it is scored in the
> report. What is scored here is the understanding the student demonstrates — separate
> evidence, which may be weak even where the file is fine, or sound even where it is not.

---

## 5. One rule for evidential defects

1. **A claim with no reproducible support is weak evidence, not misconduct.** Score it
   under *Defensibility*; the more the report leans on it, the more it costs.
2. **Absent required work is not credited**, under *Results*, whether or not the report
   claims anything from it. Omitting it honestly is not a defect of integrity — it is
   simply work that earned no marks.
3. **A rerun failure is not by itself an academic defect.** If saved outputs are
   present and consistent, mark the science and note the failure. Where outputs are absent
   or mutually inconsistent, do not credit a claim unless the available evidence
   establishes it — outputs that disagree about the transport peak may still establish a
   separate flow result, and their disagreement is not grounds to discard that. Confirm
   the marking environment before concluding a student's code is broken.
4. **Heavy notebooks need not rerun.** They are saved-output provenance records and the
   large workspaces are excluded from the submission by design. Never penalise this.
5. **A no-reach or below-threshold result is not a weaker result.** Grade the mechanism
   evidence the group can actually support — and credit a correct statement that a
   mechanism *cannot* be distinguished from what they have.

---

## 6. Policies worth settling before the course runs

- **Presentation slot.** Publish it on the course page and keep it. 🔴 The repository
  deliberately states no enforced limit: `REPORT_BRIEF.md` gives students a per-section
  time budget written for a 12-minute talk, labelled as guidance to scale. **If you
  announce a limit, hold a clock** — announcing one and not keeping it penalises exactly
  the groups that rehearsed to it.
- **Report length and appendix cap**, with over-length scored under *Communication*.
- **Report template.** Students get the same skeleton in Markdown, LaTeX and Word, so
  section structure is not a differentiator and *Communication* marks presentation quality
  rather than whether they guessed the right headings.
- **Rerun environment.** Name it, so everyone is arguing about the same environment. The
  lightweight per-student notebooks are designed to rerun from the submission alone.
- **The non-claims.** State what the model cannot support, so it is not marked as if it
  could. Here: the model resolves transport along the flow axis but not across it, so
  contaminated-area maps, lateral threshold-contour widths and exact plume footprints are
  not claimable at any feasible grid. Arrival, first exceedance and receptor peak are.

---

## 7. Question bank

Each has a defensible answer in the material; each also accepts a well-argued alternative.

1. Your affected area is *X* m². What is it at a different threshold, and which number
   would you give a regulator?
2. Your particle-tracking mean travel time is *A* days, your concentration peak arrives at
   *B*. Which is "arrival" — and is either of them?
3. Your doublet's net abstraction is zero. Did any budget term change, and why is that
   consistent?
4. Your scenario's effect and the doublet's effect — which dominates, and where?
5. How big would the release have to be to flip your verdict, and how confident is that
   number?
6. Name something your model cannot tell you that a client would probably ask for.
7. What would you check first with one more week?
8. *(to a non-steward)* Which heavy notebook did you run yourself, and what did it do?

---

*Provenance: adapted from the ETH HS26 internal rubric.*
