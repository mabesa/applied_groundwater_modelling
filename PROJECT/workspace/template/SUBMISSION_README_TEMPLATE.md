# Submission README — Group &lt;NUMBER&gt;

*Copy this file into your group folder, fill every `<...>` field, and include it in the
submission ZIP.*

## Group members

| Name | Role |
|------|------|
| `<First Last>` | steward |
| `<First Last>` | deputy |
| `<First Last>` | member |

## Card assignment & contribution statements

One row per member. State the card and one sentence on what you produced.

| Member | Card | Contribution |
|--------|------|--------------|
| `<name>` | `<A/B/C/D/E/F>` | `<e.g. computed the drawdown affected area and wrote the interpretation>` |
| `<name>` | `<card>` | `<...>` |
| `<name>` | `<card>` | `<...>` |

## Included files checklist

Tick what is in this ZIP:

- [ ] `case_config.yaml` (filled in)
- [ ] `case_config_transport.yaml` (if transport was done)
- [ ] `case_study_flow_group_<N>.ipynb` — master flow notebook, **with saved output**
- [ ] `case_study_transport_group_<N>.ipynb` — master transport notebook, with saved output *(optional)*
- [ ] `steward_export_lightweight.ipynb` — export notebook, with saved output
- [ ] `scratch_analysis_template.ipynb` (or per-member copies) — with saved figures/tables
- [ ] `scratch_io.py` — the FloPy-free reader (required for rerun)
- [ ] `exports/` — the lightweight bundle (see below)
- [ ] `figures/` and `tables/` — outputs produced by the scratch cards
- [ ] project report (PDF) and presentation

### `exports/` bundle contents

- [ ] `run_info.json` *(required)*
- [ ] `flow_heads_sub_base.gpkg` *(required)*
- [ ] `flow_heads_sub_wells.gpkg` *(required)*
- [ ] `flow_budget_summary.csv` *(required)*
- [ ] `flow_heads_sub_scenario.gpkg` *(optional)*
- [ ] `transport_breakthrough.csv` *(optional)*
- [ ] `transport_meta.json` *(optional)*
- [ ] `pathlines_summary.csv` *(optional)*

## Optional exports we did NOT include

List any optional artifact that is intentionally absent and why (this matches
`run_info.json → missing_optional`):

- `<e.g. pathlines_summary.csv — MODPATH section not run>`
- `<e.g. transport_* — transport scenario not attempted>`

## Reproducibility note

- The **scratch** notebook (`scratch_analysis_template.ipynb`) reruns from this ZIP
  **alone** — it is FloPy-free and reads only the `exports/` bundle via `scratch_io.py`.
- The **master** and **steward export** notebooks are **provenance records** (saved
  output). They are **not** expected to rerun from the ZIP because the heavy model
  workspaces are **excluded** (see below).

## What is excluded

The heavy MODFLOW / transport model workspaces under
`~/applied_groundwater_modelling_data/` are **not** part of this submission (hundreds of
MB, machine-specific). The lightweight `exports/` bundle stands in for them.

## Submission channel

Submit **one single ZIP** — no loose files, no split/multi-part archives.

- **Preferred: Moodle** — upload the single group ZIP. The exact Moodle assignment
  location and file-size limit are **pending confirmation** by the teaching team; check
  the current course announcement before submitting.
- **Fallback: email** (if Moodle is unavailable or the ZIP is over the Moodle limit) —
  **one** email to **both lecturers** with **all group members in CC**. Attach the
  single ZIP if it is small enough; if it is too large to email, send a **SWITCHdrive
  link** to the single ZIP instead. One ZIP only — no loose files, no split archives.
- **Receipt** — a lecturer replies by email to confirm receipt. The **first lecturer
  confirmation** is the official receipt timestamp.

Record how you submitted:

- [ ] Moodle
- [ ] Email attachment (both lecturers, group in CC)
- [ ] Email with SWITCHdrive link (both lecturers, group in CC)
