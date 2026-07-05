# Group Collaboration Workflow

This file explains how a group of 2–3 students collaborates on the flow + transport
case study, and how the pieces fit together. It complements the top-level
[`../README.md`](../README.md).

## Three kinds of notebook

| Notebook | Who runs it | FloPy? | Purpose |
|----------|-------------|--------|---------|
| **Master** — `case_study_flow_group_0.ipynb`, `case_study_transport_group_0.ipynb` | steward (+ deputy) | yes | Build and run the heavy models. **Saved-output / provenance records** — not expected to rerun from the ZIP. |
| **Steward export** — `steward_export_lightweight.ipynb` | steward | yes | Turns the heavy model workspaces into a small, portable `exports/` bundle. Run **once**, after both master notebooks. Provenance record. |
| **Scratch** — `scratch_analysis_template.ipynb` | every member | **no** | The **rerun target**. FloPy-free; reads only `exports/`; reruns from the submission ZIP alone. Each member does one card here. |

The important asymmetry: **master and steward notebooks are provenance records** (the
TA may spot-check them), but the **scratch notebook is what the TA actually reruns**.
So the scratch notebook must never depend on FloPy, the course repo, or the heavy
model workspaces — only on `scratch_io.py` and the `exports/` bundle.

## Roles: steward and deputy

- **Steward** — owns the master notebooks and the export. They run the flow and
  transport master notebooks to completion, then run
  `steward_export_lightweight.ipynb` to produce `exports/`. They also declare the
  **export freeze**.
- **Deputy** — a second member who can run the master notebooks and re-export if the
  steward is unavailable. Prevents a single point of failure.

Everyone else works in the **scratch** notebook on their assigned card.

## Cards: self-selection, no duplicates

Analysis work is split into **cards** (see the table in
`scratch_analysis_template.ipynb`):

- **A** drawdown affected area · **B** pathlines (optional) · **C** scenario
  comparison · **D** budget / river exchange · **E** transport breakthrough ·
  **F** provenance / submission QA.

Rules:

- Each member **self-selects** one card and sets `STUDENT_NAME` + `CARD` at the top of
  their copy of the scratch notebook.
- **No two members take the same card** unless the steward approves a deliberate
  cross-check.
- Not every card must be done, and **no student has to run every card** — the scratch
  notebook only loads the files its selected card needs. Cards B (pathlines) and C's
  scenario input are optional and degrade or skip cleanly when their export is absent.

## Export freeze

Because every card reads from the same `exports/` bundle, that bundle must stop moving
before people finalise figures. **Default: the steward freezes `exports/` at least
3 days before the submission deadline.** After the freeze, re-export only for a
correctness fix, and tell the group so everyone re-pulls the bundle.

## Git is optional (off by default)

Git is **not required** for this project. Notebook merge conflicts are painful, so the
default is **no Git**: coordinate through your usual channel and hand the frozen
`exports/` bundle around. If your group does choose Git, commit and pull often, avoid
editing the same notebook cells simultaneously, and never commit the heavy model
workspaces under `~/applied_groundwater_modelling_data/`.

## Why the scratch notebook must rerun from the ZIP

The submission ZIP contains the group folder, including `scratch_io.py`, the scratch
notebook, and the `exports/` bundle — but **not** the multi-hundred-MB model
workspaces. A TA on a clean machine can open the scratch notebook and rerun it end to
end using only the bundle. That is the reproducibility guarantee we make; keeping the
scratch notebook FloPy-free is what makes it true. (`scratch_io.assert_no_flopy()` is
called at the start and end of the scratch notebook to enforce it.)
