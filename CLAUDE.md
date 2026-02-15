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
- Notebooks follow pattern: banner → imports → progress tracker → sections with completion markers
