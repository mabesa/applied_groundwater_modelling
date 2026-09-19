# Student Workspace

You are here: `PROJECT/workspace/`. The parent course overview is in the root [README.md](../../README.md).

This is where you work on your flow and transport case study.

> **Reading this on JupyterHub?** A `.md` file opens as *raw* text by default. To see it
> nicely rendered, **right-click the file in the left file browser → Open With → Markdown
> Preview**. The same works for any `.md` here (e.g. `template/COLLABORATION.md`).

## Getting Started

1. Copy the `template/` folder to create your own workspace.
2. Rename the copy to your group folder using the standard naming `group_<N>`, zero-padded
   to two digits — for example `group_03`.
3. **Set `group.number` in `case_config.yaml` to the same number.** Renaming the folder
   does not do this for you: the notebooks read the number from the YAML, which ships as
   `0`. Miss this and every notebook runs the **demo** group's concession, contaminant
   and threshold — and nothing downstream looks wrong. The notebooks now refuse to run
   when the folder and the number disagree, but only if your folder is named exactly
   `group_<N>`.
4. Work only in your group folder.
5. **Do not rename the template notebooks.** The filenames stay exactly as shipped —
   `case_study_flow_group_0.ipynb` and `case_study_transport_group_0.ipynb` — even though
   your folder is `group_<N>`. Your group is identified by `group.number` in
   `case_config.yaml` — the folder name must match it, not the notebook filename.
6. Keep the original `template/` folder unchanged so you can compare against it if needed.

## What Is In The Template

| File | What it is |
|---|---|
| `case_config.yaml`, `case_config_transport.yaml` | your group's flow and transport settings — **you fill these in** |
| `case_study_flow_group_0.ipynb`, `case_study_transport_group_0.ipynb` | **master** notebooks: build and run the heavy models |
| `steward_export_lightweight.ipynb` | **steward** notebook: run once after the masters to write the small `exports/` bundle |
| `scratch_analysis_template.ipynb` | **scratch** notebook: FloPy-free card analysis, reruns from `exports/` alone |
| `scratch_io.py` | the FloPy-free reader for the `exports/` bundle — do not edit it |
| `COLLABORATION.md` | how your group divides the work |
| `REPORT_BRIEF.md` | what the group report must contain, how it is judged, and the 12-minute presentation rule |
| `report_template.md` / `.tex` / `.docx` | the report skeleton — same structure in three formats, pick one |
| `SUBMISSION_README_TEMPLATE.md` | fill in and include in your ZIP |

## How Your Group Works

**Stewardship rotates, so nobody sits out the modelling.** The flow steward runs
`case_study_flow_group_0.ipynb`; the **transport steward** — a different member — runs
`case_study_transport_group_0.ipynb`; the **export steward** runs
`steward_export_lightweight.ipynb` to produce the `exports/` bundle. In a two-person
group one member holds two of these roles; in a three-person group each member holds
exactly one. Deputies are arranged so every role has a named stand-in — in a pair that
means one member deputises for the other's two.

**Every member owns two cards** (A–F) in their own copy of the scratch notebook, and
produces their figures, tables and — the part that is not pre-written — each card's
**extension**. Cards **A, B, C, D and E** are required in every group. That is five
cards against four extension slots in a two-member group, so one of them — your choice,
Card B is the usual one — is carried as a **short card**: shipped analysis +
interpretation, no extension.

The export steward **freezes `exports/` at least 3 days before the deadline** so everyone
finalises against the same numbers.

Full detail — roles, the card table, the extensions, the freeze, and the (optional, off
by default) Git guidance — is in [`template/COLLABORATION.md`](template/COLLABORATION.md).
**Read it before you divide the work.**

## Definition Of Done

Before submission, check that you can answer each item below. The goal is not only to
produce figures.

- what modelling question your scenario addresses;
- which parameters or boundary conditions you changed;
- how the model response appears in heads, drawdown, budgets, and transport outputs;
- whether the result looks like a physical signal, numerical noise, or model instability;
- what the result implies for the practical groundwater problem;
- **which of your claims the model actually supports, and which it does not** — and
  where you say so in the report;
- **what would have to be different for your conclusion to change** — the defensibility
  question each card extension asks, answered for the group's headline result.

Every member should be able to answer all of these for the **group's** work, not only for
their own two cards — expect to be asked about any part of it.

## What You Submit

**One single ZIP** of your group folder — no loose files, no split archives. It contains:

- your filled `case_config.yaml` and `case_config_transport.yaml`;
- the **master** flow and transport notebooks, **with saved output**;
- the **steward export** notebook, with saved output;
- **one scratch notebook per member** (`scratch_<name>.ipynb`), each covering that
  member's **two cards including their extensions** — plus the short card, if they carry
  it — with saved figures/tables, plus `scratch_io.py`;
- the `exports/` bundle, and the `figures/` and `tables/` you produced;
- your filled-in `SUBMISSION_README.md`;
- `report.pdf` and `presentation.pdf` in the **group folder root**.

Start the report from `template/report_template.md`, `.tex` or `.docx` — same skeleton,
three formats. The presentation is **strictly 12 minutes**; see
[`template/REPORT_BRIEF.md`](template/REPORT_BRIEF.md) for what fits.

Flow **and** transport are both required.

### How the pieces are assessed

Four things carry your project grade:

| Component | What it is |
|---|---|
| Written exam | Individual, during the semester. |
| Group report | `report.pdf` — the written record of *how you know*. See [`template/REPORT_BRIEF.md`](template/REPORT_BRIEF.md). |
| Oral presentation | Your presentation delivered and defended. **Strictly 12 minutes**, questions extra. `presentation.pdf` is its artifact. |
| Working notebooks | The **evidence** the report and the oral rest on. Computed work that nothing in the ZIP reproduces cannot be credited. |

> **Moodle is definitive.** The **weighting** of these components, the deadlines, the exam
> arrangements and the grading rubric are published on the Moodle course page — not in this
> repository, so that the repo and the official course description cannot drift apart.
> **Check Moodle before you plan your time.**

The report and the presentation are **not** the same content in two formats — see the
comparison in [`template/REPORT_BRIEF.md`](template/REPORT_BRIEF.md). Write the report
first.

**Only the scratch notebooks have to rerun from the ZIP.** They are FloPy-free and read
only `scratch_io.py` and `exports/`; they are the artifacts your TA can rerun and will
spot-check — your card extension code included. The master and
steward notebooks are saved-output provenance records — the heavy model workspaces under
`~/applied_groundwater_modelling_data/` are excluded from the ZIP, so those notebooks are
not expected to rerun from it.

**Where to submit:** Moodle, preferred. If Moodle is unavailable or the ZIP is over the
limit, email one ZIP (or a SWITCHdrive link to it) to both lecturers with the group in CC;
a lecturer's reply is your official receipt. The exact addresses, assignment location and
size limit are announced in Moodle / in class — **check the current course announcement
before you submit.** The tick-list and the submission-channel detail are in
[`template/SUBMISSION_README_TEMPLATE.md`](template/SUBMISSION_README_TEMPLATE.md).

## Building The ZIP

On the course JupyterHub. Replace `<N>` with your zero-padded group number (e.g. `03`).

1. Copy `template/SUBMISSION_README_TEMPLATE.md` into your group folder as
   `SUBMISSION_README.md` and fill in every `<...>` field.
2. Restart-and-run-all every `scratch_<name>.ipynb`, so figures and tables are saved with
   output. Check that each member's notebook has **every** card they own run, with the
   extensions — the short card excepted, which needs interpretation only.

   > ⚠️ **Do not re-run the steward export notebook here.** It would rebuild `exports/`
   > and break the freeze your group finalised against — the bundle in the ZIP would no
   > longer be the one the figures came from. Its saved output from the freeze run is
   > what you submit. Re-run it only for a deliberate correctness fix, and then tell the
   > group to re-run their cards against the new bundle.
3. Put `report.pdf` and `presentation.pdf` in the group folder root. (Your report source
   — `.md`, `.tex` or `.docx` — may go in too; the PDF is what is required.)
4. Zip **from `PROJECT/workspace/`**, not from inside the group folder, so the archive has
   a single top-level `group_<N>/` folder:

```bash
cd ~/applied_groundwater_modelling.git/PROJECT/workspace
rm -f group_<N>.zip
zip -r group_<N>.zip group_<N> \
  -x "*/.ipynb_checkpoints/*" "*/__pycache__/*" "*.pyc" "*/.DS_Store" "*/__MACOSX/*"
# must print exactly one line: group_<N>/
unzip -Z1 group_<N>.zip | cut -d/ -f1 | sort -u
```

   If that prints anything other than the single line `group_<N>`, you zipped from inside
   the group folder — delete the ZIP and redo this step from `PROJECT/workspace/`.

5. Check it reruns. Extract into a clean folder and restart-and-run one scratch notebook
   from there; it must run top to bottom with no manual fixes:

```bash
rm -rf ~/ziptest/group_<N> && mkdir -p ~/ziptest
unzip -q group_<N>.zip -d ~/ziptest
```

6. Submit that one ZIP.
