# Student Workspace

You are here: `PROJECT/workspace/`. The parent course overview is in the root [README.md](../../README.md).

This is where you work on your flow and transport case study.

## Getting Started

1. Copy the `template/` folder to create your own workspace.
2. Rename the copy to your group name, for example `group_alice_bob/`.
3. Work only in your group folder.
4. Keep the original `template/` folder unchanged so you can compare against it if needed.

## Template Contents

Configuration:

- `case_config.yaml` - Flow model configuration parameters
- `case_config_transport.yaml` - Transport model configuration

Notebooks:

- `case_study_flow_group_0.ipynb` - **master** flow model notebook (builds/runs the heavy model)
- `case_study_transport_group_0.ipynb` - **master** transport model notebook
- `steward_export_lightweight.ipynb` - **steward** notebook: turns the heavy model
  workspaces into a small, portable `exports/` bundle (run once, after the master
  notebooks)
- `scratch_analysis_template.ipynb` - **scratch** notebook: FloPy-free, card-based
  analysis that reruns from the `exports/` bundle alone

Helper + docs:

- `scratch_io.py` - the FloPy-free reader used **only** by the scratch notebook
- `COLLABORATION.md` - the group workflow (roles, cards, export freeze)
- `SUBMISSION_README_TEMPLATE.md` - fill in and include in your ZIP

## Collaboration Workflow

Read [`template/COLLABORATION.md`](template/COLLABORATION.md) for the full workflow.
In short:

1. **Master notebooks** (FloPy) — the group **steward** (with a **deputy** as backup)
   builds and runs the flow and transport models.
2. **Steward export** (FloPy) — the steward runs `steward_export_lightweight.ipynb`
   once to produce the lightweight `exports/` bundle (heads GeoPackages, budget CSV,
   transport CSV/JSON, `run_info.json`).
3. **Scratch analysis** (FloPy-free) — each member picks a **card**
   (A drawdown · B pathlines · C scenario · D budget/river · E transport · F QA), sets
   their name and card in `scratch_analysis_template.ipynb`, and produces the figures
   and tables for it. Cards self-select, no duplicates unless the steward approves; a
   student only runs the card they own.
4. **Export freeze** — the steward freezes `exports/` at least **3 days** before the
   deadline so everyone finalises against the same numbers.
5. **Git is optional** and off by default (notebook merge conflicts are painful); if
   used, never commit the heavy model workspaces.

## What You Submit

Submit **one single ZIP** of your group folder — no loose files, no split archives.
Fill in and include
[`template/SUBMISSION_README_TEMPLATE.md`](template/SUBMISSION_README_TEMPLATE.md).

**Submission channel:**

- **Preferred — Moodle.** Upload the single group ZIP to Moodle. The exact Moodle
  assignment location and its file-size limit are **still being confirmed** by the
  teaching team; check the current course announcement before you submit.
- **Fallback — email (if Moodle is unavailable or the ZIP exceeds the Moodle limit).**
  Send **one** email to **both lecturers**, with **all group members in CC**:
  - if the ZIP is small enough for email, **attach the single group ZIP**;
  - if the ZIP is too large to email, put it on **SWITCHdrive** and send a **link to
    the single ZIP** instead.
  - Either way: **one ZIP only** — no loose files and no split/multi-part archives.
- **Receipt.** A lecturer replies by email to confirm they received your submission.
  The **first lecturer confirmation** is your official receipt timestamp; keep it.

The ZIP contains:

- your filled `case_config.yaml` (and `case_config_transport.yaml` if used);
- the **master** flow (and transport) notebooks, **with saved output**;
- the **steward export** notebook, with saved output;
- the **scratch** notebook(s) with saved figures/tables, plus `scratch_io.py`;
- the `exports/` bundle, and the `figures/` and `tables/` you produced;
- your project report and presentation covering both flow and transport.

The heavy MODFLOW / transport model workspaces under
`~/applied_groundwater_modelling_data/` are **excluded** from the ZIP — the lightweight
`exports/` bundle stands in for them.

### Reproducibility

- The **scratch** notebook reruns from the submission ZIP **alone**: it is FloPy-free
  and reads only the `exports/` bundle through `scratch_io.py`. This is the artifact
  your TA reruns.
- The **master** and **steward export** notebooks are **provenance / spot-check
  records** (saved output). Because the heavy workspaces are excluded, they are **not**
  expected to rerun from the ZIP.

## Expected Workflow

Work through the required notebook sections first. Optional sections are enrichment and should only be attempted after the required work is complete.

Use the time estimates at the top of each notebook to plan your work. If a task takes much longer than the estimate, ask for help rather than spending many hours debugging alone.

## Definition Of Done

Before submission, check that you can answer each item below. The goal is not only to produce figures.

- what modelling question your scenario addresses;
- which parameters or boundary conditions you changed;
- how the model response appears in heads, drawdown, budgets, and transport outputs;
- whether the result looks like a physical signal, numerical noise, or model instability;
- what the result implies for the practical groundwater problem.

## Before You Submit

- Restart the kernel and run the **scratch** notebook top to bottom against the frozen
  `exports/` bundle — it must run without manual fixes. This is the reproducibility
  check your TA repeats.
- Make sure the **master** and **steward** notebooks are saved **with their output**
  (they are provenance records, not rerun targets).
- Confirm the `exports/` bundle and `scratch_io.py` are inside the ZIP and the heavy
  workspaces are not.

For roles, card assignment, the export freeze, and the (optional) Git guidance, see
[`template/COLLABORATION.md`](template/COLLABORATION.md).

## Pre-course verification (instructors)

Before students start, **run the full workflow once on the actual HS26 JupyterHub
image**: copy one `template/` folder to a group folder, run the master notebooks, the
steward export, and a scratch card end to end, then produce a submission ZIP. This
confirms the environment, the `exports/` bundle, and the FloPy-free scratch rerun all
work on the image students will use.

Rerun the scratch ZIP check after any update that touches the workspace template,
`scratch_io.py`, the steward export notebook, the project dependencies, or the
JupyterHub image. The key check is: extract a submitted-style ZIP in a clean folder and
restart-and-run a scratch notebook using only the local `scratch_io.py` and `exports/`.

Received submissions are saved by the lecturers to the project SWITCHdrive, with access
restricted to lecturers only.
