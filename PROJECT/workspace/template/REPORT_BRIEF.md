# Group Report — Brief

*Copy nothing from this file into your report. It tells you what the report is for, what
it must contain, and how it is judged.*

Your group writes **one report**, submitted as `report.pdf` in the group folder root.
See [`COLLABORATION.md`](COLLABORATION.md) for who drafts which section, and
[`../README.md`](../README.md) for the full deliverable list.

**Start from the template — you do not have to build the skeleton.** The same structure
ships in three interchangeable formats; pick one, copy it into your group folder, and
delete the guidance blocks as you fill them in:

| File | For |
|---|---|
| [`report_template.md`](report_template.md) | JupyterHub, VS Code, any text editor. The maintained source. |
| [`report_template.tex`](report_template.tex) | LaTeX / Overleaf. Plain `article` class — compiles anywhere. |
| `report_template.docx` | Microsoft Word, with real heading styles. |

Each section below tells you what that section is **for**. The template tells you where
to type.

## What the report is for

The report is the written record of **how you know what you claim**. Not what you did in
chronological order — what you concluded, on what evidence, and how far that evidence
actually reaches.

That makes it a different document from your presentation, and you should not write it
twice:

| | Report | Presentation |
|---|---|---|
| Question it answers | *How do you know?* | *What should be done?* |
| Audience | A reviewer who will check your reasoning | A client or authority who must decide |
| Carries | Assumptions, method, uncertainty, the limits of your claims | The verdict, the two or three figures that establish it |
| Failure mode | Results with no defence | A defence with no decision in it |

Write the report first. The presentation is a **selection** from it, not a summary of it.

## Length and format

- **10 pages maximum**, including figures and tables, excluding title page, references
  and appendix. A shorter report that defends its claims beats a longer one that does not.
- The **appendix is capped at 5 pages** — otherwise the page limit means nothing.
- PDF, as `report.pdf`, in the group folder root, next to `presentation.pdf`.
- Every figure and table: caption, units, and the filename under `figures/` or `tables/`
  it came from. A reader must be able to find the artifact behind any number your
  analysis **computed**. Values you were *given* — α_L, porosity, your threshold, the
  pumping rate — are cited from the config instead; they need a source, not a table.
- Appendix (not counted in the 10 pages, max 5): the figure/table index, and any
  derivation or intermediate numbers you want on record.

## Required structure

### 1. Problem and modelling question
Your concession, its setting, and the question your scenario actually asks. One
paragraph. Be specific: *"does the assigned recharge reduction change river leakage
enough to matter for the concession's yield"* is a question; *"we study the Limmat
aquifer"* is not.

### 2. Conceptual model and assumptions
The aquifer as you are modelling it: boundaries and what they represent, the stresses,
the assigned scenario's physical story (the `type` → story mapping in flow §3), and the
transport setup — spill, doublet, and the locked physics (α_L = 10 m, α_T = 1 m,
n_e = 0.20) with your group's pinned reactions.

State the assumptions you are **making**, not the ones the software makes. Steady state,
the regional grid with local refinement, one model shared by all groups, a clean-water
doublet with a separate zero-water contaminant source — each of these is a choice with
consequences. Name the consequence, not just the choice.

### 3. Method
Enough that a competent reader could repeat it: the four flow states and what each
isolates, how the scenario forcing is applied, the transport build, and which quantities
you computed from which export. Point to the notebooks; do not reproduce their code.

### 4. Results
**Organise this by finding, not by card.** The full record of each card and its
extension already lives in the scratch notebooks and in `tables/`; do not re-narrate it
here. What belongs in the report is the *integrated* result — what the flow response,
the scenario forcing, the budget and the transport verdict say **together** about your
concession, with each claim pointing to the table or figure behind it.

Every member's work must be visible in this section, and the contribution statement
(§7) says whose text is whose — but a results section assembled by concatenating six
card write-ups is the failure mode this structure exists to prevent.

Report numbers with units and with the comparison they belong to. Two specific traps the
material sets for you, both of which a careful report handles explicitly:

- **Head change has two conventions in this project.** The flow master's metrics take
  `abs()`, so they count the injection mound as well as the extraction cone; Card A's
  drawdown is `base − compare`, positive only where the head falls. They can agree
  closely, differ several-fold, or one can be zero while the other is not. Say which one
  you are quoting and why it suits the question you asked.
- **An advective travel time is not a concentration peak.** If you quote both the PRT
  mean travel time and the breakthrough peak time, do not present the difference as an
  error or reconcile them by arithmetic. They are different quantities, and in a
  converging flow field no simple identity connects them.

### 5. Uncertainty and the limits of your claims
The section that most separates reports at this level. Required content:

- **The mesh uncertainty on your transport peak.** Two equally defensible meshes of the
  same corridor move the peak by roughly ±20 %. Quote your peak with that band, and state
  why it does not flip your verdict (or, if your case is marginal, what that costs you).
- **The defensible-threshold judgment.** Your model resolves transport along the flow
  axis but not across it. So arrival time, first exceedance and the receptor peak are
  yours to claim; the contaminated-**area** map, the lateral threshold-contour width and
  any exact plume footprint are **not** — they are numerical artefacts at any feasible
  grid resolution. State this, and make sure nothing elsewhere in your report quietly
  violates it.
- **Signal, artefact or instability.** For your main flow result: which is it, and what
  evidence rules out the other two? Mass-balance closure, convergence and the
  same-grid construction of the four states are the evidence available to you.
- **Your card extensions' defensibility answers**, synthesised rather than listed.

A limitation you found yourself and quantified is worth more than a paragraph of generic
caveats about model uncertainty.

### 6. Conclusion and practical recommendation
What the result means for the actual problem — the concession, the receptor, the
compliance question. One recommendation, and the condition under which you would
withdraw it.

Below-threshold and no-reach outcomes are graded on the quality of the judgment and the
mechanism evidence (capture-zone half-width, retardation delay, dilution), not on having
a high peak. A confident, well-defended "it does not reach the well, and here is why"
is a strong result.

### 7. Contribution statement
One row per member: name, the cards they owned, and one sentence on what they produced.
Must be **consistent with** `SUBMISSION_README.md` and the `STUDENT_NAME` fields in the
scratch notebooks — that file lists one row per *card* and this one lists one row per
*member*, so they are not the same shape, but no one should appear in one and not the
other. In a two-member group, one member has three cards; mark the short one.

## How it is judged

In rough order of weight:

1. **Defensibility** — are the claims supported by the evidence presented, and are the
   limits of that evidence stated rather than implied?
2. **Conceptual reasoning** — assumptions named with their consequences; the physical
   story tied to the parameter change.
3. **Correct and complete results** — the required quantities, with units, from the
   frozen bundle, reproducible from the ZIP.
4. **Communication** — readable figures, honest captions, a conclusion that answers the
   question in §1.

The fastest ways to lose marks, in practice: a **computed** number that nothing in the ZIP
reproduces; a claim the §5 rules say your model cannot support; a peak quoted without its
uncertainty; and a results section that describes figures instead of interpreting them.

## The presentation — 12 minutes, strictly

**Your presentation is limited to 12 minutes. This is a hard limit and it is enforced:**
you will be stopped at 12 minutes, and anything you had not reached does not count.
Questions come afterwards and are **not** part of the 12.

Twelve minutes is deliberately short. It is not enough time to walk through everything you
did, which is the point — selecting what a decision-maker needs is the skill being tested.

**What realistically fits:**

| | Budget |
|---|---|
| The problem and your question | ~1.5 min |
| Conceptual model and the assumptions that matter | ~2 min |
| Results — the integrated finding, not a tour | ~4 min |
| Uncertainty and what you cannot claim | ~2.5 min |
| Verdict and recommendation | ~2 min |

That is roughly **8–10 slides and 2–3 figures**. Every member of the group speaks, so in a
three-person group each person has about four minutes.

**Rehearse against a clock.** A run that comes in at 14 minutes is not a 12-minute talk
with a bit of overrun — it is a talk that will be cut off before its conclusion, which is
the part that carries the most credit.

What to cut first: the method walkthrough (it is in the report), per-card narration (also
in the report), and any figure you would have to apologise for. What to keep whatever
happens: your verdict, the evidence that establishes it, and the limits on it.

## Relationship to the other components

The report is one of three assessed components, alongside the oral presentation and the
written exam; your notebooks are the evidence base all of it rests on. The **weighting**
of the components and the grading rubric are published on **Moodle**, not in this
repository — check there before you plan your time.
