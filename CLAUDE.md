# CLAUDE.md — Project Instructions for Claude Code

## Package Manager

This project uses **uv** (not pip, conda, or poetry). Always run Python scripts and commands through `uv run`:

```bash
uv run python script.py
uv run pytest
uv run jupyter lab
```

Dependencies are managed in `pyproject.toml` with `uv.lock` for reproducibility.

## Project Structure

- `PROJECT/flow/` — Main course notebooks (1–10)
- `_SUPPORT/src/` — Utility modules imported by notebooks
- `_SUPPORT/src/scripts/` — Data generation and setup scripts
- `config_template.py` / `config.py` — Data source configuration
- `DESIGN_DOCS/` — Active design documents

## Conventions

- Notebooks add `sys.path.append('../../_SUPPORT/src')` to import utilities
- Data downloads via `data_utils.download_named_file()`
- Default data folder: `~/applied_groundwater_modelling_data/limmat/`
- Model workspace: `~/applied_groundwater_modelling_data/limmat/limmat_valley_model/`
- CRS: Swiss LV95 (EPSG:2056)
- Observation well data has mixed CRS (LV03 6-digit and LV95 7-digit coordinates)
- Current model: MODFLOW-NWT with structured grid (model_name = `limmat_valley_model_nwt`)
- Grid is rotated 30 degrees; modelgrid pickle must be loaded to restore transformation
- Notebooks follow pattern: banner → imports → sections with completion markers
- All `RUN_X` toggles in flow notebooks default to `False` (opt-in). Long-running optional work
  (PEST calibration, LOO cross-validation, etc.) only runs when the student explicitly flips the
  toggle to `True`.

## Workflow

See `docs/workflow.md` for the full conventions. Key points:

- **Orchestrator (Opus) never writes code** — delegates to Sonnet 4.6 subagents
- **Plans are phase-based** with JSON dependency graphs for parallel/sequential execution
- **Every code change updates affected docs** — no exceptions
- **No subagent runs from a DRAFT plan** — user must confirm first

### Avoid Task Jags

Stay focused on the current task until completion. Do not change direction mid-stream
(e.g. switching from implementing A to implementing B, or from implementing to testing).

### Plan Readiness

Plans start as `status: DRAFT`. Opus self-reviews before presenting to user.
User confirms, then Opus sets `status: READY`. Do not begin implementation from
a DRAFT plan.

## Ask Questions

Ask clarifying questions often to fill gaps. Better to clarify upfront than to implement the wrong solution.