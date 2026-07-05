# Student Workspace

You are here: `PROJECT/workspace/`. The parent course overview is in the root [README.md](../../README.md).

This is where you work on your flow and transport case study.

## Getting Started

1. Copy the `template/` folder to create your own workspace.
2. Rename the copy to your group folder using the standard naming `group_<N>`, zero-padded
   to two digits — for example `group_03`.
3. Work only in your group folder.
4. **Do not rename the template notebooks.** The filenames stay exactly as shipped —
   `case_study_flow_group_0.ipynb` and `case_study_transport_group_0.ipynb` — even though
   your folder is `group_<N>`. Your group is identified by the folder name, not the
   notebook filename.
5. Keep the original `template/` folder unchanged so you can compare against it if needed.

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

- **Preferred — Moodle.** Upload the single group ZIP to Moodle.
- **Fallback — email (if Moodle is unavailable or the ZIP exceeds the Moodle limit).**
  Send **one** email to **both lecturers**, with **all group members in CC**:
  - if the ZIP is small enough for email, **attach the single group ZIP**;
  - if the ZIP is too large to email, put it on **SWITCHdrive** and send a **link to
    the single ZIP** instead.
  - Either way: **one ZIP only** — no loose files and no split/multi-part archives.
- **Receipt.** A lecturer replies by email to confirm they received your submission.
  The **first lecturer confirmation** is your official receipt timestamp; keep it.

> **Moodle is the definitive source for the local course run.** The actual fallback
> lecturer email addresses, the Moodle assignment location, and any file-size limit are
> announced in Moodle / in class — they are **not** stored in this public repository.
> Always check the current course announcement before you submit.

The ZIP contains:

- your filled `case_config.yaml` and `case_config_transport.yaml`;
- the **master** flow and transport notebooks, **with saved output**
  (`case_study_flow_group_0.ipynb`, `case_study_transport_group_0.ipynb`);
- the **steward export** notebook, with saved output;
- the **scratch** notebook(s) (`scratch_<name>.ipynb`) with saved figures/tables, plus
  `scratch_io.py`;
- the `exports/` bundle, and the `figures/` and `tables/` you produced;
- `report.pdf` and `presentation.pdf` in the **group folder root**.

Flow **and** transport are **both required** for the final project submission once the
transport phase has been assigned.

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

## How To Prepare And Submit The ZIP

These steps run on the course JupyterHub. Replace `<N>` with your zero-padded group
number (for example `03`). All commands avoid `/tmp` and use `~/ziptest` for the extract
check.

**1. Finalise your work inside the group folder.** Do everything inside
`PROJECT/workspace/group_<N>/`. Nothing you submit lives outside that folder.

**2. Fill in the submission README.** Copy `template/SUBMISSION_README_TEMPLATE.md` into
your group folder as `SUBMISSION_README.md` and fill in every `<...>` field.

**3. Run the steward export.** The steward opens `steward_export_lightweight.ipynb`,
restarts the kernel, and runs all cells to (re)build the `exports/` bundle.

**4. Run each scratch notebook.** For every `scratch_<name>.ipynb` in the group folder,
restart the kernel and run all cells so figures and tables are saved with output.

**5. Add the report and presentation.** Put `report.pdf` and `presentation.pdf` in the
**group folder root** (`PROJECT/workspace/group_<N>/`), alongside the notebooks.

**6. Create the ZIP from `PROJECT/workspace/`** — *not* from inside the group folder, so
the archive has a single top-level `group_<N>/` folder. Exclude checkpoint/cache junk:

```bash
cd ~/applied_groundwater_modelling.git/PROJECT/workspace
rm -f group_<N>.zip
zip -r group_<N>.zip group_<N> \
  -x "*/.ipynb_checkpoints/*" "*/__pycache__/*" "*.pyc" "*/.DS_Store" "*/__MACOSX/*"
```

**7. Verify the ZIP has a single top-level `group_<N>/` folder:**

```bash
unzip -l group_<N>.zip | head
```

Everything listed should sit under `group_<N>/`. If you see files at the top level, you
zipped from inside the group folder — redo step 6 from `PROJECT/workspace/`.

**8. Extract into a clean folder and rerun one scratch notebook.** Extract under
`~/ziptest` (never `/tmp`) and confirm a scratch notebook reruns from the extracted copy
alone:

```bash
rm -rf ~/ziptest/group_<N>
mkdir -p ~/ziptest
unzip -q group_<N>.zip -d ~/ziptest
cd ~/ziptest/group_<N>
```

Then open one `scratch_<name>.ipynb` from `~/ziptest/group_<N>/`, **restart the kernel,
and run all cells**. It must run top to bottom without manual fixes, using only the local
`scratch_io.py` and `exports/` bundle.

**9. Submit one ZIP only** via the channel above (Moodle preferred). No loose files, no
split archives.

### What reruns, and what does not

- The **scratch** notebooks (`scratch_<name>.ipynb`) are the **rerun target**: they are
  FloPy-free and rerun from the submission ZIP alone on the course JupyterHub
  environment, reading only `scratch_io.py` and the `exports/` bundle.
- The **master** notebooks (`case_study_flow_group_0.ipynb`,
  `case_study_transport_group_0.ipynb`) and the **steward export** notebook are
  **saved-output / provenance records**, not ZIP-rerun targets.
- The heavy model workspaces under `~/applied_groundwater_modelling_data/` are
  **excluded** from the ZIP; the lightweight `exports/` bundle stands in for them.

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
