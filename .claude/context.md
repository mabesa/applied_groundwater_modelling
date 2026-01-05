# Project Context for AI Assistants

## About This Project

This is a Master-level groundwater modeling course (4 ECTS) at ETH Zurich focusing on MODFLOW and transport modeling using FloPy. The course uses a real-world case study of the Limmat Valley aquifer in Switzerland.

## Current Status (course_2026 branch)

The course implementation is complete with 10 case study notebooks covering the full modeling workflow:
1. Introduction
2. Perceptual Model
3. MODFLOW Fundamentals
4. Model Implementation (flow)
4b. Transport Model Implementation
5. Calibration
6. Validation
7. Sensitivity & Uncertainty
8. Model Application
9. Documentation
10. Communication

## Planned Changes for course_2026

### Migration from MODFLOW-NWT to MODFLOW 6
- **Current**: Notebooks use MODFLOW-NWT
- **Target**: Migrate to MODFLOW 6 (MF6)
- **Scope**: Affects notebooks 3, 4, 4b, 5, 6, 7, 8 and student_work templates
- **Key differences**:
  - MF6 uses a modular package structure (GWF, GWT models)
  - Different input file format (structured text → name files + packages)
  - FloPy API changes: `flopy.mf6` module instead of `flopy.modflow`
  - Transport: GWT model replaces MT3DMS

### Notebook Refactoring - Keep Content Concise

**Planning Document:** [planning/notebook_refactoring.md](../planning/notebook_refactoring.md)

**Priority Order:**
1. Notebook 4 (Model Implementation) - 2915 lines → target ~800
2. Notebook 5 (Calibration) - 1563 lines → target ~500
3. Notebook 4b (Transport) - 1308 lines → target ~400 (combine with MF6 migration)
4. Notebook 6 (Validation) - 930 lines → target ~400

**New Utility Modules to Create:**
- `model_utils.py` - MF6 model loading, inspection, water balance
- `calibration_utils.py` - metrics, observation handling, trial runs
- `transport_utils.py` - GWT setup, concentration plotting, analytical solutions

**Existing Modules to Expand:**
- `grid_utils.py` - rotation, DEM resampling, active cells
- `plot_utils.py` - heads maps, boundary conditions, calibration plots
- `data_utils.py` - boundary loading, parameter zones, river cells

## Repository Structure

```
CASE_STUDY/
├── 0_introduction.ipynb      # Shared intro to 10-step framework
├── flow/                     # Flow modeling track (steps 1-10)
│   ├── 1_model_goal.ipynb
│   ├── 2_perceptual_model.ipynb
│   ├── ...
│   └── 10_communication.ipynb
├── transport/                # Transport extension track (steps 1-10)
│   ├── 1_model_goal.ipynb
│   ├── ...
│   └── 10_communication.ipynb
├── student_work/             # Group working areas
└── grading_scheme/
```

Other directories:
- `EXERCISES/` - 6 exercises + theory reminder
- `DEMOS/` - Optional demo materials (REV, porosity)
- `_SUPPORT/src/` - Helper functions and utilities
- `_SUPPORT/static/` - Static files (images, figures)

## Development Setup

See **[DEVELOPMENT.md](../DEVELOPMENT.md)** for complete instructions including:
- Environment setup with uv
- AI-assisted development (Serena, Context7)
- Contributing guidelines
- Code style conventions

Quick start:
```bash
uv sync
source .venv/bin/activate
get-modflow :flopy
```

## Development Guidelines

1. **Follow established patterns** from existing notebooks
2. **Maintain accessibility** (see README.md section 4)
3. **Test thoroughly** with group_0 demo before deploying to students
4. **Notebook outputs** are stripped automatically via pre-commit hook

### MODFLOW/FloPy Coding Patterns

**Always remove packages before replacing:**
When modifying model packages (boundary conditions, properties, etc.), always remove the existing package before adding new content. This prevents cached files from causing unexpected behavior.

```python
# Remove existing package before replacing
gwf.remove_package('CHD')  # or 'RIV', 'WEL', etc.
# Then add new package
flopy.mf6.ModflowGwfchd(gwf, stress_period_data=new_spd)
```

**Use FloPy utilities:**
Prefer FloPy's built-in utilities over custom implementations:
- `flopy.utils.gridintersect` for spatial operations
- `flopy.utils.postprocessing` for results analysis
- `modelgrid` methods for coordinate transformations

## Important Notes

- Students use JupyterHub environment (ETH)
- All data downloaded from configured sources (not in git)
- FloPy is a primary tool
- Course includes both flow and transport modeling components
- Environment management uses uv (not conda) starting course_2026
