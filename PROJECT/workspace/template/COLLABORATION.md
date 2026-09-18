# Group Collaboration Workflow

This file explains how a group of 2–3 students collaborates on the flow + transport
case study, and how the pieces fit together. It complements the top-level
[`../README.md`](../README.md) and the report specification in
[`REPORT_BRIEF.md`](REPORT_BRIEF.md).

**Read this before you divide the work.** Two rules below are not negotiable and are
checked at submission: **every member runs one of the heavy notebooks themselves** — a
master or the steward export (§ *Rotating stewardship*) — and **every member owns two
cards** (§ *Cards*).

## Three kinds of notebook

| Notebook | Who runs it | FloPy? | Purpose |
|----------|-------------|--------|---------|
| **Master** — `case_study_flow_group_0.ipynb`, `case_study_transport_group_0.ipynb` | flow steward / transport steward | yes | Build and run the heavy models. **Saved-output / provenance records** — not expected to rerun from the ZIP. |
| **Steward export** — `steward_export_lightweight.ipynb` | export steward | yes | Turns the heavy model workspaces into a small, portable `exports/` bundle. Run **once**, after both master notebooks. Provenance record. |
| **Scratch** — `scratch_analysis_template.ipynb` | every member, own copy | **no** | The **rerun target**. FloPy-free; reads only `exports/`; reruns from the submission ZIP alone. Each member does **two** cards here. |

The important asymmetry: **master and steward notebooks are provenance records** (the
TA may spot-check them), but the **scratch notebook is what the TA actually reruns**.
So the scratch notebook must never depend on FloPy, the course repo, or the heavy
model workspaces — only on `scratch_io.py` and the `exports/` bundle.

## Rotating stewardship — nobody sits out the modelling

The heavy notebooks are where the modelling judgment lives: the four-state build, the
hand-composed metrics in flow §8, the transport flip test. A group that lets one person
run all of it leaves the others unable to defend the work in the oral — where you are
questioned individually about any part of the group's work, not just your own cards.

So the steward role **rotates by phase**. There are three roles and they are never all
held by one person: in a trio each member holds exactly one, in a pair one member holds
two.

**Two-member group**

| Role | Runs | Deputy for |
|---|---|---|
| Member 1 — **flow steward** | `case_study_flow_group_0.ipynb` | transport **and export** |
| Member 2 — **transport steward + export steward** | `case_study_transport_group_0.ipynb` + `steward_export_lightweight.ipynb` | flow |

**Three-member group**

| Role | Runs | Deputy for |
|---|---|---|
| Member 1 — **flow steward** | `case_study_flow_group_0.ipynb` | export |
| Member 2 — **transport steward** | `case_study_transport_group_0.ipynb` | flow |
| Member 3 — **export steward** | `steward_export_lightweight.ipynb` + the bundle QA below | transport |

Deputies are cyclic so no role has a single point of failure: if the transport steward
drops out the week before the deadline, a named person already knows how to rerun it.

The **export steward** (member 2 in a pair, member 3 in a trio) additionally owns:
declaring the **export freeze**, keeping `exports/` and `SUBMISSION_README.md`
consistent, and building the submission ZIP.

**Record who did what** in `SUBMISSION_README.md`. If one name appears against every
heavy notebook, expect that to come up in the oral.

## Cards: two per member, self-selected, no duplicates

Analysis work is split into **cards** (see the table in
`scratch_analysis_template.ipynb`):

- **A** drawdown affected area · **B** pathlines / advective capture · **C** scenario
  comparison · **D** budget / river exchange · **E** transport breakthrough ·
  **F** provenance / submission QA.

> **Why PRT is required.** Where water goes, how long it takes and which wells capture
> it is the everyday question of applied groundwater modelling, and particle tracking
> answers it directly. Keep its boundary in view: PRT runs on a **static** flow field
> and tracks **advection only**, so it tells you about connection and travel time — not
> about concentration, dispersion, sorption or decay. Card B's extension is built around
> exactly that distinction.

**Every member owns two cards with extensions.** One card is roughly an afternoon of
pre-written cells; two cards with their extensions is the individual technical workload
this project expects of you.

**In a two-member group the arithmetic does not come out even** — five required cards,
four extension slots. So one member carries a **third** card as the short card (shipped
analysis + interpretation, no extension). Decide between you who takes it and record it
in `SUBMISSION_README.md`; it is the lighter load of the two, not a punishment.

| Group size | Cards the group must cover | Suggested split |
|---|---|---|
| 2 members | **A, B, C, D, E** | M1: A + C · M2: D + E **+ B (short)** |
| 3 members | **A, B, C, D, E, F** | M1: A + C · M2: D + E · M3: B + F |

**A, B, C, D and E are required in every group**: together they cover the flow result,
advective capture and travel time, the assigned scenario forcing, the water balance and
the transport verdict.

The short card still counts as covered. Card B has the lightest shipped analysis so it
is the natural choice, but your group may pick a different one — say which in
`SUBMISSION_README.md`. In a pair, F is folded into the export steward's bundle QA
rather than being a card.

Rules:

- Each member sets `STUDENT_NAME` and lists their two cards in `CARDS` in **their own**
  copy of the scratch notebook, saved as `scratch_<name>.ipynb`.
- **No two members take the same card.** A deliberate cross-check is allowed but it is
  **additional** work — it does not replace either of that member's own two cards — and
  the report must say what the cross-check showed.
- Cards B and C depend on exports that are **normally present** — PRT and the scenario
  state both run by default — but can be absent if a step was skipped. Neither is a
  reason to drop the card:
  - **Card C** degrades to a base→wells comparison, which only repeats Card A. That is
    not an acceptable submission for a required card: tell the export steward and get
    the scenario state re-exported.
  - **Card B** has no degraded mode — it simply has no input. PRT is **required**, so if
    `pathlines_summary.csv` is missing the fix is not a workaround: re-run the flow
    master with `RUN_PRT = True` and re-export. It costs seconds on the steady field.
  - Either way, never present a degraded comparison as the intended one. If you fixed it
    before the freeze, it needs no mention in the report.

## Card extensions: the part that is not pre-written

Every card ships with working code that produces its figure and table. That code is
**scaffolding, not your deliverable.** Each card therefore carries an **Extension**
section with two things you must supply yourself:

1. **A computation the notebook does not do for you.** You write the code. It always
   uses data already in the `exports/` bundle — you never need FloPy, the repo or the
   heavy workspaces — but the notebook does not hand you the answer.
2. **A defensibility question.** In writing, in your own words: *what would have to be
   different for my conclusion to change, and how would I know?*

The extensions are what separates a card from a button press, and they are the raw
material for the report and for the oral. A card submitted with the shipped cells run
and the extension left blank is an incomplete card — **except** the one **short card**
a two-member group is allowed (see above), which is complete with the shipped analysis
and a written interpretation. Name its owner in `SUBMISSION_README.md`; it is submitted
in that member's own `scratch_<name>.ipynb`, like any other card.

Both extension outputs live in your scratch notebook (figure/table under `figures/` and
`tables/`, the written answer in the card's markdown cell) and both must survive the
rerun-from-ZIP check like everything else.

## The report

The group writes **one report** — see [`REPORT_BRIEF.md`](REPORT_BRIEF.md) for its
structure, length and what it must defend. How it maps onto this workflow:

- **Each member contributes the findings from their own two cards** to the results
  section — which is organised **by finding, not by card**. Do not draft a section per
  card and then dismantle it: the full card record already lives in your scratch
  notebook and in `tables/`. The contribution statement records whose work is whose.
- **The flow and transport stewards** each draft the methods text for the phase they ran
  — the four flow states and the scenario forcing; the spill, the doublet and the locked
  transport physics.
- **The whole group** owns the conceptual model, the synthesis, the limitations section
  and the conclusion. These are the sections where the grade is won, and they cannot be
  assembled by concatenating card write-ups.
- **The export steward** checks that every **computed result** quoted in the report —
  every number your analysis produced — appears in a table under `tables/` built from
  the frozen bundle. (Configuration values you were *given*, such as α_L, porosity or
  your threshold, are cited from the config instead; they need a source, not a table.)
  A computed number that nothing in the ZIP reproduces is the single easiest defect for
  a TA to find.

The report and the presentation are **not** the same document in two formats. The report
is the written record of *how you know* — assumptions, method, uncertainty, what you may
and may not claim. The presentation is the decision-facing case: the verdict and the
evidence a client would need, in **strictly 12 minutes**. Write the report first; the
presentation is a selection from it, not a summary of it — and at 12 minutes it has to be.

Start the report from one of the shipped skeletons — `report_template.md`, `.tex` or
`.docx`, same structure in three formats.

## Export freeze

Because every card reads from the same `exports/` bundle, that bundle must stop moving
before people finalise figures. **Default: the export steward freezes `exports/` at
least 3 days before the submission deadline.** After the freeze, re-export only for a
correctness fix, and tell the group so everyone re-pulls the bundle.

Plan backwards from the freeze, not from the deadline: the report is written *against*
frozen numbers, so a bundle that moves on the last day invalidates text, not just
figures.

## Git is optional (off by default)

Git is **not required** for this project. Notebook merge conflicts are painful, so the
default is **no Git**: coordinate through your usual channel and hand the frozen
`exports/` bundle around. If your group does choose Git, commit and pull often, avoid
editing the same notebook cells simultaneously, and never commit the heavy model
workspaces under `~/applied_groundwater_modelling_data/`.

## Why the scratch notebook must rerun from the ZIP

The submission ZIP contains the group folder, including `scratch_io.py`, the scratch
notebooks, and the `exports/` bundle — but **not** the multi-hundred-MB model
workspaces. A TA on a clean machine can open any member's scratch notebook and rerun it
end to end using only the bundle. That is the reproducibility guarantee we make; keeping
the scratch notebook FloPy-free is what makes it true. (`scratch_io.assert_no_flopy()` is
called at the start and end of the scratch notebook to enforce it.)

This applies to your extension code too. If your extension needs something that is not
in the bundle, that is a finding worth a sentence in the report — *the exported bundle
does not carry what would be needed to answer X* — not a reason to import FloPy.
