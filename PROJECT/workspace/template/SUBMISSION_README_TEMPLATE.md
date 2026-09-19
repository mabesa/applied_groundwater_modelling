# Submission README — Group &lt;NUMBER&gt;

*Copy this file into your group folder, fill every `<...>` field, and include it in the
submission ZIP.*

## Group members and stewardship

Stewardship rotates — see `COLLABORATION.md`. Name the member who **actually ran** each
heavy notebook. In a two-person group one member holds two steward roles; in a
three-person group each member holds exactly one.

| Role | Member | Ran | Deputy |
|------|--------|-----|--------|
| Flow steward | `<First Last>` | `case_study_flow_group_0.ipynb` | `<name>` |
| Transport steward | `<First Last>` | `case_study_transport_group_0.ipynb` | `<name>` |
| Export steward | `<First Last>` | `steward_export_lightweight.ipynb` + bundle QA | `<name>` |

- [ ] Every member ran at least one master or steward-export notebook themselves.

## Card assignment & contribution statements

**Two cards per member, with extensions.** Cards **A, B, C, D and E** are required in
every group; a three-member group covers all six, two each. A two-member group has four
extension slots for five required cards, so one member carries a **third** card as a
**short card** — shipped analysis + interpretation, no extension. Mark it `(short)`.

One row per card — state what you produced **and what your extension added**.

| Member | Card | Contribution | Extension — what you computed and what you concluded |
|--------|------|--------------|------------------------------------------------------|
| `<name>` | `<A/B/C/D/E/F>` | `<e.g. computed the drawdown affected area and wrote the interpretation>` | `<e.g. swept the area threshold 0.1–2.0 m; the 'affected area' halves between 0.4 and 0.6 m, so the 0.5 m figure is a convention, not a boundary>` |
| `<name>` | `<card>` | `<...>` | `<...>` |
| `<name>` | `<card>` | `<...>` | `<...>` |
| `<name>` | `<card>` | `<...>` | `<...>` |
| `<name>` | `<card>` | `<...>` | `<...>` |
| `<name>` | `<card>` | `<...>` | `<...>` |

- [ ] Every member owns **two** cards with extensions. *(Two-member group: one of you
      also carries the short card, so that member has three rows below — mark it
      `(short)`.)*
- [ ] No card is duplicated. A deliberate cross-check is **additional** work, not a
      replacement — if you did one, say what it showed: `<...>`
- [ ] Cards A, B, C, D and E are all covered. Two-member group: which card is the
      short one, and why that one? `<...>`
- [ ] Every **full** card's extension is completed: the computation **and** the written
      defensibility answer. *(The short card is the one exception — shipped analysis +
      interpretation only. Mark it `(short)` above.)*

## Report authorship

| Report section | Drafted by |
|---|---|
| Conceptual model, synthesis, limitations, conclusion | whole group |
| Method — flow | `<flow steward>` |
| Method — transport | `<transport steward>` |
| Results — `<card>` + `<card>` | `<name>` |
| Results — `<card>` + `<card>` | `<name>` |
| Results — `<card>` + `<card>` | `<name>` |

- [ ] Every **computed** number quoted in `report.pdf` appears in a table under
      `tables/` produced from the frozen bundle. (Values you were *given* — α_L,
      porosity, your threshold — are cited from the config instead.)

## Included files checklist

Tick what is in this ZIP. The template notebooks keep their shipped filenames — **do not
rename them to your group number**. Your group is identified by **`group.number` in
`case_config.yaml`**; the `group_<N>/` folder name must match it, and the notebooks now
refuse to run if it does not.

- [ ] `case_config.yaml` (filled in) *(required)*
- [ ] `case_config_transport.yaml` (filled in) *(required)*
- [ ] `case_study_flow_group_0.ipynb` — master flow notebook, **with saved output** *(required)*
- [ ] `case_study_transport_group_0.ipynb` — master transport notebook, with saved output *(required)*
- [ ] `steward_export_lightweight.ipynb` — export notebook, with saved output *(required)*
- [ ] `scratch_<name>.ipynb` (one per member, **two cards each with their extensions run**;
      in a pair, one member also carries the short card) — with saved figures/tables
      *(required)*
- [ ] `scratch_io.py` — the FloPy-free reader (required for rerun) *(required)*
- [ ] `exports/` — the lightweight bundle (see below) *(required)*
- [ ] `figures/` and `tables/` — outputs produced by the scratch cards **and their
      extensions** *(required)*
- [ ] `report.pdf` — the group report, in the group folder root *(required)*
- [ ] `presentation.pdf` — in the group folder root *(required)*
- [ ] Presentation rehearsed and comes in **under 12 minutes** (hard limit; questions extra)

Flow **and** transport are both required for the final submission once the transport
phase has been assigned.

### `exports/` bundle contents

- [ ] `run_info.json` *(required)*
- [ ] `flow_heads_sub_base.gpkg` *(required)*
- [ ] `flow_heads_sub_wells.gpkg` *(required)*
- [ ] `flow_budget_summary.csv` *(required)*
- [ ] `transport_breakthrough.csv` *(required)*
- [ ] `transport_meta.json` *(required)*
- [ ] `flow_heads_sub_scenario.gpkg` *(required — Card C needs it)*
- [ ] `pathlines_summary.csv` *(required — PRT; Card B needs it. Absent means the flow
      master ran with `RUN_PRT = False`: set it `True`, re-run and re-export)*

All eight are required. The `exports/` bundle has **no optional parts** — `scratch_io`
tolerates a missing file so a card skips instead of crashing, but that is defensive
reading, not permission to omit it.

Optional non-export extras:

- [ ] presentation source file such as `presentation.pptx` *(optional — `presentation.pdf`
      in the group folder root is what is required)*
- [ ] report source file such as `report.md`, `report.tex` or `report.docx` *(optional —
      `report.pdf` is what is required)*

## Required exports we could not produce

This should be **empty**. If it is not, your bundle is incomplete and cards downstream
of the missing file cannot deliver. List anything absent, why, and what you did about
it — this must match `run_info.json → missing_required`:

- `<file — why it is missing, and what you tried>`

- [ ] `run_info.json → missing_required` is empty.

## Reproducibility note

- Every member's **scratch** notebook (`scratch_<name>.ipynb`) reruns from this ZIP
  **alone** — they are FloPy-free and read only the `exports/` bundle via `scratch_io.py`.
  This covers the **card extension code** each member wrote, not just the shipped cells.
- The **master** and **steward export** notebooks are **provenance records** (saved
  output). They are **not** expected to rerun from the ZIP because the heavy model
  workspaces are **excluded** (see below).

## What is excluded

The heavy MODFLOW / transport model workspaces under
`~/applied_groundwater_modelling_data/` are **not** part of this submission (hundreds of
MB, machine-specific). The lightweight `exports/` bundle stands in for them.

## Submission channel

Submit **one single ZIP** — no loose files, no split/multi-part archives.

- **Preferred: Moodle** — upload the single group ZIP.
- **Fallback: email** (if Moodle is unavailable or the ZIP is over the Moodle limit) —
  **one** email to **both lecturers** with **all group members in CC**. Attach the
  single ZIP if it is small enough; if it is too large to email, send a **SWITCHdrive
  link** to the single ZIP instead. One ZIP only — no loose files, no split archives.
- **Receipt** — a lecturer replies by email to confirm receipt. The **first lecturer
  confirmation** is the official receipt timestamp.

> **Moodle is the definitive source for the local course run.** The actual fallback
> lecturer email addresses, the Moodle assignment location, and any file-size limit are
> announced in Moodle / in class — they are **not** stored in this public repository.
> Check the current course announcement before submitting.

Record how you submitted:

- [ ] Moodle
- [ ] Email attachment (both lecturers, group in CC)
- [ ] Email with SWITCHdrive link (both lecturers, group in CC)
