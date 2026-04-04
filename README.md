[![Package Dependencies](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/check-dependencies.yml/badge.svg)](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/check-dependencies.yml)

# Applied Groundwater Modeling

![Groundwater Model Visualization](_SUPPORT/static/figures/0_readme/Groundwater_course.jpg)

> **Tip:** This README is best viewed on [GitHub](https://github.com/mabesa/applied_groundwater_modelling). In VS Code, you can use Markdown preview: right-click the file → *Open Preview*, or press `Ctrl+Shift+V` (`Cmd+Shift+V` on Mac).

## 1 Overview

Course materials for Master-level groundwater modeling (4 ECTS) at ETH Zurich. Combines theoretical exercises with a practical project using MODFLOW and FloPy, applied to the Limmat Valley aquifer case study.

## 2 Quick Start for Students

Choose your preferred way to work with the course materials:

### Option A: Local Setup (Recommended)

Working locally with VS Code gives you the best development experience, version control, and prepares you for professional workflows.

**New to Python?** Follow the [Python for Water Modellers](https://mabesa.github.io/python-for-water-modellers/) tutorial first - it covers VS Code installation, uv setup, and Python basics.

**Already comfortable with Python?** Quick setup — run these commands in the **VS Code integrated terminal** (open it via *Terminal → New Terminal*):

```bash
# 1. Clone the repository
git clone https://github.com/mabesa/applied_groundwater_modelling.git
cd applied_groundwater_modelling

# 2. Install dependencies
uv sync
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 3. Install MODFLOW
get-modflow :flopy

# 4. Verify setup (optional)
# Open 0_diagnostics.ipynb and run all cells
# Confirm: overall_ready = True

# 5. Start working
code .  # Open in VS Code
```

**Selecting the right Python environment:** When you open a notebook for the first time, VS Code will ask you to select a kernel. Choose the one pointing to `./.venv/bin/python` in this project folder. See [Jupyter Kernel Setup](#jupyter-kernel-setup) if you run into issues.

<details>
<summary><strong>For group work: Fork the repository</strong></summary>

Forking creates your own copy of the repository on GitHub, where your group can collaborate independently. For case study collaboration:

1. **Fork:** Go to the [repository page](https://github.com/mabesa/applied_groundwater_modelling) and click the **Fork** button (top right). This creates a copy under your GitHub account.
2. **Clone your fork** locally (replace `YOUR_USERNAME`):
   ```bash
   git clone https://github.com/YOUR_USERNAME/applied_groundwater_modelling.git
   ```
3. **Add group members** as collaborators: on your fork's GitHub page, go to *Settings → Collaborators → Add people*.
4. Work together using branches and pull requests.

This mirrors professional workflows and gives your group a shared workspace with full version control.

</details>

### Option B: JupyterHub (ETH Students)

Access the pre-configured environment via the link on Moodle. No installation required.

<details>
<summary>JupyterHub details</summary>

**First time:**
1. Access JupyterHub via Moodle (don't bookmark - URL may change)
2. Run `0_diagnostics.ipynb` to verify your environment
3. Confirm `overall_ready = True`

**Getting updates:**
- Run `0_sync_repo.ipynb` when instructors announce updates

**Scrolling fix:**
If notebooks scroll erratically: `Settings → Settings Editor → Notebook → Windowing mode → none`

</details>

### Tips for Working with Notebooks

**Navigation in long notebooks:**
- **VS Code:** Use the Outline panel (View → Open View → Outline) to jump between sections
- **JupyterHub:** Use the Table of Contents panel in the left sidebar

**Recommended workflow:**
1. Clear all outputs: `Kernel → Restart Kernel and Clear Outputs`
2. Run cells sequentially from the top, or run the entire notebook
3. This ensures variables are properly initialized and avoids stale state

## 3 Course Structure

The course is organized into two main phases:

### Phase 1: Theory (Weeks 1-8)

Lectures and exercises covering flow and transport fundamentals.

**Materials in `THEORY/`:**
- `exercises/` - 6 exercises reinforcing key concepts
- `_demos/` - Lecture demonstrations (e.g., porosity and REV)

### Phase 2: Project (Weeks 9-14)

Apply concepts to the Limmat Valley aquifer case study.

**Materials in `PROJECT/`:**
- `flow/` and `transport/` - Step-by-step modeling notebooks
- `workspace/` - Your working area
- `_demos/` - Calibration, sensitivity, and uncertainty demonstrations (for lectures)

The project follows a 10-step modeling methodology:

| Step | Topic | Flow Track | Transport Track |
|------|-------|------------|-----------------|
| 0 | Introduction | `0_start_here.ipynb` | `0_start_here.ipynb` |
| 1 | Model Goal | `flow/1_model_goal.ipynb` | `transport/1_model_goal.ipynb` |
| 2 | Perceptual Model | `flow/2_perceptual_model.ipynb` | `transport/2_perceptual_model.ipynb` |
| 3 | Conceptual Model | `flow/3_modflow_fundamentals.ipynb` | — |
| 4 | Model Implementation | `flow/4_model_implementation.ipynb` | `transport/4_model_implementation.ipynb` |
| 5 | Calibration | `flow/5_calibration.ipynb` | — |
| 6 | Validation | `flow/6_validation.ipynb` | — |
| 7 | Sensitivity & Uncertainty | `flow/7_sensitivity_uncertainty.ipynb` | — |
| 8 | Model Application | `flow/8_model_application.ipynb` | — |
| 9 | Documentation | `flow/9_documentation.ipynb` | — |
| 10 | Communication | `flow/10_communication.ipynb` | — |

The transport track builds on the calibrated flow model. Steps marked with "—" use the flow model results.

### Repository Structure

```
applied_groundwater_modelling/
├── THEORY/                   # Phase 1: Theory materials (Weeks 1-8)
│   ├── exercises/            # Exercises aligned with lectures
│   └── _demos/               # Lecture demonstrations
├── PROJECT/                  # Phase 2: Case study (Weeks 9-14)
│   ├── 0_start_here.ipynb    # Course intro & 10-step framework
│   ├── flow/                 # Flow modeling track (steps 1-10)
│   ├── transport/            # Transport track (steps 1, 2, 4)
│   ├── workspace/            # Your working area
│   └── _demos/               # Calibration & uncertainty demos
├── _SUPPORT/                 # Helper code and static files
├── 0_diagnostics.ipynb       # Environment check
└── 0_sync_repo.ipynb         # Update from upstream
```

> **Note:** Folders starting with `_` contain internal/instructor materials - you can ignore them.

## 4 Learning Objectives

- Apply numerical methods to solve groundwater flow and transport problems
- Construct and adapt models to address real-world hydrogeological challenges
- Implement and analyze numerical solutions using MODFLOW, MT3D and FloPy
- Critically evaluate modeling results and their implications

## 5 Prerequisites

- Basic understanding of hydrogeology (Darcy's Law, hydraulic conductivity, aquifer properties)
- Groundwater flow concepts and boundary conditions
- Basic Python programming skills (see [Python for Water Modellers](https://mabesa.github.io/python-for-water-modellers/) if needed)

## 6 Data Management

Course data is downloaded automatically and stored in `~/applied_groundwater_modelling_data/`.

<details>
<summary>Data configuration details</summary>

The data system uses `config.py` for data source configuration. For public data (default), copy `config_template.py` to `config.py`:

```bash
cp config_template.py config.py
```

Workshop participants receive a `config.py` with additional private datasets - don't commit this file.

Data downloads automatically when needed:
```python
from data_utils import download_named_file
file_path = download_named_file(name='groundwater_map_norm', data_type='gis')
```

</details>

## 7 Troubleshooting

<details>
<summary>Common issues and solutions</summary>

### JupyterHub Issues

**Repository out of date:**
Run `0_sync_repo.ipynb` or in terminal:
```bash
git fetch origin && git reset --hard origin/main
```

**405: Method Not Allowed:**
Don't bookmark JupyterHub URLs - always access via Moodle.

### Data Download Issues

**"No URL configured":** Ensure `config.py` exists (copy from `config_template.py`)

**Download failures:** Check internet connection and that Dropbox links are accessible

**"Path does not exist":** The system creates directories automatically - check write permissions in home directory

### Environment Issues

**Package not found:** Run `uv sync` to reinstall dependencies

**MODFLOW not found:** Run `get-modflow :flopy`

**Wrong Python environment in Jupyter:** If you get numpy version errors or package conflicts when running `uv run jupyter lab`, register the uv environment as a kernel:
```bash
uv run python -m ipykernel install --user --name=applied_gw_modelling --display-name="Applied GW Modelling (uv)"
```
Then select "Applied GW Modelling (uv)" as your kernel in Jupyter.

**Multiple figures accumulating in VS Code:** Use Command Palette (Cmd/Ctrl+Shift+P) → "Developer: Reload Window"

### MODFLOW or MT3D Model Issues

**Model changes not taking effect:**
If you modify model settings, run the model, but results don't change:
1. Delete the model workspace folder (e.g., `model_ws/`)
2. Re-run the notebook cells that create and run the model

MODFLOW and MT3D may reuse cached files from previous runs, causing your changes to be ignored.

</details>

## 8 Accessibility

This course is designed with accessibility in mind - screen reader compatibility, keyboard navigation, and clear structure.

<details>
<summary>Accessibility details</summary>

**Features:**
- Standard Markdown for screen reader compatibility
- Keyboard-accessible interactive elements
- Alt text for images
- Consistent heading hierarchy

**Limitations we're working on:**
- Some complex diagrams lack comprehensive text alternatives
- Color-dependent information being improved

**Report issues:** Open a GitHub issue with the `accessibility` label.

</details>

## 9 For Developers

See [DEVELOPMENT.md](DEVELOPMENT.md) for:
- Environment setup with uv
- Pre-commit hooks (auto-strips notebook outputs)
- Code style and contribution guidelines

## 10 Acknowledgments

Funded by the ETH Zurich Department of Earth and Planetary Sciences and the Rectors Innovendum Fund ([project link](https://ww2.lehrbetrieb.ethz.ch/id-workflows/faces/instances/Innovedum/ProzessInnovedum$1/197A35DA732E83F5/innovedumPublic.Details/Details.xhtml)).
