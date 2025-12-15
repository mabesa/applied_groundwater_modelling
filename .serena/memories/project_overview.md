# Applied Groundwater Modelling - Project Overview

## Purpose
Project-based course materials for Master-level groundwater modeling (4 ECTS) at ETH Zurich. Focuses on practical modeling skills using MODFLOW and FloPy through a real-world case study of the Limmat valley aquifer in Switzerland.

## Learning Objectives
- Deepen understanding of basic hydrogeological concepts and principles
- Apply numerical methods to solve groundwater flow and transport problems
- Construct and adapt models to address real-world hydrogeological challenges
- Implement and analyze numerical solutions using MODFLOW, MT3D and FloPy
- Critically evaluate modeling results and their implications

## Tech Stack
- **Python**: 3.12
- **Groundwater Modeling**: FloPy 3.9.2, MODFLOW, MT3D
- **Data Science**: NumPy 1.26.4, Pandas 2.2.3, SciPy 1.15.2, statsmodels 0.14.4
- **Geospatial**: GeoPandas 1.0.1, Rasterio 1.4.3, GDAL 3.10.2, Shapely 2.1.0, PyProj 3.7.1
- **Visualization**: Matplotlib 3.10.1, Seaborn 0.13.2, Plotly 6.2.0, Folium 0.19.5
- **Notebooks**: JupyterLab 4.4.2, ipywidgets 8.1.5, ipympl 0.9.7
- **Other**: PyKrige 1.7.2, pyemu (pip), contextily 1.6.2

## Repository Structure
```
applied_groundwater_modelling/
├── CASE_STUDY/              # Main case study notebooks (10 notebooks)
│   ├── student_work/        # Student workspace with templates
│   └── grading_scheme/      # Grading materials
├── DEMOS/                   # Demonstration notebooks for lectures
│   ├── 05a_calibration_concept.ipynb
│   ├── 05b_calibration_overfitting.ipynb
│   ├── 05c_calibration_equifinality.ipynb
│   ├── 07a_sensitivity_tornado.ipynb
│   ├── 07b_uncertainty_envelope.ipynb
│   ├── calibration_common.py    # Shared utilities for calibration demos
│   └── _animations/             # GIF animations (gitignored)
├── EXERCISES/               # 6 exercises + theory reminder
├── SUPPORT_REPO/
│   ├── src/                 # Utility modules
│   │   ├── data_utils.py    # Data download and management
│   │   ├── map_utils.py     # Map visualization
│   │   ├── grid_utils.py    # Model grid utilities
│   │   ├── river_utils.py   # River processing
│   │   ├── plot_utils.py    # Plotting helpers
│   │   └── ...
│   └── static/              # Static files (images, figures)
├── PLANNING/                # Internal planning documents (gitignored)
├── config.py                # Data source configuration (gitignored)
├── config_template.py       # Template for config.py
├── pyproject.toml           # Project dependencies (uv)
├── DEVELOPMENT.md           # Development guide with AI tools setup
└── .vscode-mcp.json         # MCP server configuration for Claude Code
```

## Data Management
- External data downloaded automatically to `~/applied_groundwater_modelling_data/`
- Configured via `config.py` (copy from `config_template.py`)
- Supports multiple case studies: currently "limmat" (publicly available)
- Data sources: Dropbox links (public), SWITCHdrive (private)

## Case Study: Limmat Valley Aquifer
Based on the real-world Limmat valley aquifer in Zurich, Switzerland. The case study follows 10 numbered notebooks:
1. Introduction
2. Perceptual Model
3. MODFLOW Fundamentals
4. Model Implementation
4b. Transport Model Implementation
5. Calibration
6. Validation
7. Sensitivity & Uncertainty
8. Model Application
9. Documentation
10. Communication
