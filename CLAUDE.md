# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

Applied Groundwater Modelling course (ETH Zurich). Teaches MODFLOW 6 using FloPy with a Limmat Valley aquifer case study.

**Structure:**
- `THEORY/` - Foundational exercises and demonstrations
- `PROJECT/` - 10-step modeling workflow on Limmat Valley case study
- `_SUPPORT/` - Python utilities, tests, and static assets
- `DESIGN_DOCS/` - Development planning and implementation tracking

## Quick Reference

Requires **Python >= 3.12**. Uses **uv** for package management.

| Task | Command |
|------|---------|
| Install dependencies | `uv sync` |
| Run Jupyter | `uv run jupyter lab` |
| Run tests | `uv run pytest` |
| Run tests (verbose) | `uv run pytest -v` |
| Run specific test | `uv run pytest _SUPPORT/tests/test_file.py` |
| Run with coverage | `uv run pytest --cov=_SUPPORT/src` |
| Add dependency | `uv add package_name` |
| Add dev dependency | `uv add --dev package_name` |
| Setup pre-commit hooks | `uv run pre-commit install` |
| Register Jupyter kernel | `uv run python -m ipykernel install --user --name=applied_gw_modelling --display-name="Applied GW Modelling (uv)"` |

## Jupyter Kernel Setup

When running notebooks with `uv run jupyter lab`, ensure you select the correct kernel:

1. **Register the uv environment as a kernel** (one-time setup):
   ```bash
   uv run python -m ipykernel install --user --name=applied_gw_modelling --display-name="Applied GW Modelling (uv)"
   ```

2. **Select the kernel** in Jupyter: Kernel menu → Change Kernel → "Applied GW Modelling (uv)"

This ensures notebooks use the uv environment with correct package versions, avoiding conflicts with other Python installations (e.g., anaconda).

**Troubleshooting:**
- If you see multiple figures accumulating in VS Code, use Command Palette → "Developer: Reload Window"
- If you get numpy version errors, you're likely using the wrong kernel

## Module Import Pattern

Notebooks find support modules by adding `_SUPPORT/src` to `sys.path` using the project root. The `data_utils.find_project_root()` function locates the root via marker files (`config.py`, `config_template.py`). This works in both local and JupyterHub environments.

## Key Modules (`_SUPPORT/src/`)

| Module | Purpose |
|--------|---------|
| `data_utils.py` | Data download, project root discovery, path management |
| `disv_grid_utils.py` | DISV (unstructured) grid creation using FloPy VoronoiGrid |
| `grid_utils.py` | Structured grid utilities and operations |
| `boundary_utils.py` | Geometry-based boundary condition assignment |
| `river_utils.py` | River boundary condition utilities |
| `model_io_utils.py` | MODFLOW 6 I/O, loading boundaries, sampling rasters |
| `case_utils.py` | Case study configuration and utilities |
| `climate_utils.py` | Climate data handling |
| `map_utils.py` | Folium interactive maps |
| `plot_utils.py` | Cross-sections, grid visualization, head contours |
| `progress_tracking.py` | Student progress tracking with checkboxes |
| `diagnostics.py` | Environment and capability checking |
| `calibration_common.py` | Shared calibration functions |

Exercise utilities in `scripts/scripts_exercises/`: `shared_functions.py`, `tasks_data.py`

## Testing

Tests in `_SUPPORT/tests/` use pytest. Key fixtures in `conftest.py`:
- `square_boundary`, `rectangular_boundary`, `irregular_boundary` - Test geometries
- `simple_voronoi_grid`, `refined_voronoi_grid` - DISV grid fixtures
- `structured_grid_5x5` - Structured grid fixture
- GeoDataFrame fixtures with/without CRS

## Coding Conventions

| Convention | Example |
|------------|---------|
| Functions | `snake_case` |
| Classes | `PascalCase` |
| Constants | `UPPER_SNAKE_CASE` |
| Units in names | `K_ms`, `head_m`, `conductance_m2_per_day` |
| Docstrings | Google style with Args, Returns, Raises |

**Notebook standards:** Numbered sections (1., 1.1, 1.1.1). Content boxes: `✏️ Exercise`, `📚 Theory`, `💡 Example`, `🤔 Further Thinking`, `⚠️ Warning`

## Domain Conventions

- **Coordinate system:** Swiss LV95 (EPSG:2056)
- **Hydraulic conductivity:** m/s or m/day
- **Transmissivity:** m²/s or m²/day
- **Recharge:** m/day
- **Pumping rates:** m³/s or m³/day
- **Grid types:** Both structured (`StructuredGrid`) and unstructured (`VertexGrid`/DISV)

## Design Principles

1. **Geometry-first boundary conditions:** Store BCs as GeoPackage geometries, not cell IDs. Use `GridIntersect` for flexible cell assignment.
2. **Grid flexibility:** Support both grid types for comparison and teaching.
3. **Educational clarity:** Progressive complexity, interactive widgets, real-world case study.

## Git Workflow

- **Pre-commit hooks:** `nbstripout` strips notebook outputs automatically
- **Branches:** `main` (stable), `course_2025`, `course_2026`, feature branches

## Data Location

Course data downloads to `~/applied_groundwater_modelling_data/`. GeoPackage files contain spatial data (boundaries, rivers, wells, observation points).

**Configuration:**
- `config_template.py` - Public data URLs (committed)
- `config.py` - User config (gitignored) - copy from template for public data
