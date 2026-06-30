[![Package Dependencies](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/check-dependencies.yml/badge.svg)](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/check-dependencies.yml)

# Applied Groundwater Modeling

<a href="https://ethz.ch/">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="_SUPPORT/static/figures/0_readme/eth-logo-neg.svg">
    <img alt="ETH Zurich" src="_SUPPORT/static/figures/0_readme/eth-logo-pos.svg" width="100">
  </picture>
</a>

> 🚧 **HS26 iteration in active development on the `course_2026` branch.** 

![Groundwater Model Visualization](_SUPPORT/static/figures/0_readme/Groundwater_course.jpg)

> **Tip:** This README is best viewed on [GitHub](https://github.com/mabesa/applied_groundwater_modelling). In VS Code, you can use Markdown preview: right-click the file → *Open Preview*, or press `Ctrl+Shift+V` (`Cmd+Shift+V` on Mac).

## 1 Overview

Course materials for Master-level groundwater modeling (4 ECTS) at ETH Zurich. Combines theoretical exercises with a practical project using MODFLOW and FloPy, applied to the Limmat Valley aquifer case study.

## 2 Quick Start for Students

Choose your preferred way to work with the course materials:

### Option A: Local Setup (Recommended)

Working locally with VS Code gives you the best development experience, version control, and prepares you for
professional workflows.

**Before you start:**
- Read this README on GitHub, in a browser, or in VS Code Markdown Preview (`Cmd/Ctrl+Shift+V` /
`Ctrl+Shift+V`). The raw VS Code view is harder to read.
- Run Step 2 in your system terminal. After the folder is open in VS Code, run Steps 3 onward in the **VS Code
integrated terminal** (*Terminal → New Terminal*), not in a notebook cell.
- Cloning the repository can take a few minutes, about 4 minutes on a typical connection.

**New to Python?** Follow the [Python for Water Modellers](https://mabesa.github.io/python-for-water-modellers/) tutorial first - it covers VS Code installation, uv setup, and Python basics.

**Already comfortable with Python?** Follow these steps in order.

#### Step 1 — Decide: solo or group?

- **Working solo:** clone the course repository directly:
  `https://github.com/mabesa/applied_groundwater_modelling.git`
- **Working in a group:** fork the repository first, then clone your fork:
  `https://github.com/YOUR_USERNAME/applied_groundwater_modelling.git`

<details>
<summary><strong>For group work: Fork the repository</strong></summary>

Forking creates your own copy of the repository on GitHub, where your group can collaborate independently. For
case study collaboration:

1. Go to the [repository page](https://github.com/mabesa/applied_groundwater_modelling) and click the **Fork**
button in the top right. This creates a copy under your GitHub account.
2. Add group members as collaborators on your fork's GitHub page: *Settings → Collaborators → Add people*.
3. Clone your fork locally by replacing `YOUR_USERNAME` in the clone command below.
4. Work together using branches and pull requests.

This mirrors professional workflows and gives your group a shared workspace with full version control.

</details>

#### Step 2 — Clone and open the folder in VS Code

Run this step in your system terminal:

```bash
# Working solo:
git clone -b course_2026 https://github.com/mabesa/applied_groundwater_modelling.git

# For group work, clone your fork instead:
# git clone -b course_2026 https://github.com/YOUR_USERNAME/applied_groundwater_modelling.git

cd applied_groundwater_modelling
code .
```

> 📌 **Current semester branch:** `course_2026` (HS26). Taking the course in a later year? Use that semester's branch instead.

If `code .` is not found, install the command from VS Code via Command Palette → **Shell Command: Install 'code'
command in PATH**, or open the cloned folder with **File → Open Folder**.

#### Step 3 — Install in the VS Code terminal

In the VS Code window that just opened, use *Terminal → New Terminal*, then run:

```bash
uv sync
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

get-modflow :flopy
```

#### Step 4 — Verify the setup

1. Open `0_diagnostics.ipynb`.
2. When VS Code asks for a notebook kernel, select the workspace `.venv`.
3. Run all cells.
4. Confirm `overall_ready = True`.

**Jupyter kernel checklist:**
- Expected kernel: the Python environment pointing to `./.venv/bin/python`.
- Example VS Code label: `applied-groundwater-modelling (3.12.x)  ./.venv/bin/python  Workspace` — your exact
patch version may differ.
- If VS Code does not prompt you: choose **Select Kernel → Python Environments → `.venv`**.
- See [Jupyter Kernel Setup](#jupyter-kernel-setup) if the `.venv` kernel does not appear.

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
| 1 | Model Goal | `flow/01f_model_goal.ipynb` | `transport/01t_model_goal.ipynb` |
| 2 | Perceptual Model | `flow/02f_perceptual_model.ipynb` | `transport/02t_perceptual_model.ipynb` |
| 3 | Conceptual Model | `flow/03f_modflow_fundamentals.ipynb` | `transport/03t_modflow_transport.ipynb` |
| 4 | Model Implementation | `flow/04f_model_implementation.ipynb` | `transport/04t_model_implementation.ipynb` |
| 5 | Calibration | `flow/05f_calibration.ipynb` | `transport/05t_calibration.ipynb` |
| 6 | Validation | `flow/06f_validation.ipynb` | — |
| 7 | Sensitivity & Uncertainty | `flow/07f_sensitivity_uncertainty.ipynb` | — |
| 8 | Model Application | `flow/08f_model_application.ipynb` | — |
| 9 | Documentation | `flow/09f_documentation.ipynb` | — |
| 10 | Communication | `flow/10f_communication.ipynb` | — |

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
│   ├── transport/            # Transport track (steps 1-5)
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
- Implement and analyze numerical solutions using MODFLOW 6 (with GWT/GWE for transport) and FloPy
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
git fetch origin && git reset --hard origin/course_2026
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

**Multiple figures accumulating in VS Code:** Use Command Palette (Cmd/Ctrl+Shift+P) → "Developer: Reload Window"

### Jupyter Kernel Setup

Use the workspace `.venv` kernel for course notebooks.

1. Open a notebook, such as `0_diagnostics.ipynb`.
2. Click **Select Kernel** in the top right.
3. Choose **Python Environments**.
4. Select the `.venv` environment in this repository.

Expected VS Code label:

```text
applied-groundwater-modelling (3.12.x)  ./.venv/bin/python  Workspace
```

Your exact Python patch version may differ.

If the `.venv` kernel does not appear — or if you get numpy version errors or package conflicts when running `uv
run jupyter lab` directly — first run `uv sync` again from the VS Code terminal. As a fallback for Jupyter
environments that still do not find the workspace environment, register it manually:

```bash
uv run python -m ipykernel install --user --name=applied_gw_modelling --display-name="Applied GW Modelling (uv)"
```

Then select `Applied GW Modelling (uv)` as your kernel.

### MODFLOW Model Issues

**Model changes not taking effect:**
If you modify model settings, run the model, but results don't change:
1. Delete the model workspace folder (e.g., `model_ws/`)
2. Re-run the notebook cells that create and run the model

MODFLOW may reuse cached files from previous runs, causing your changes to be ignored.

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

Funded by the ETH Zurich Department of Earth and Planetary Sciences and the Rectors Innovendum Fund ([project link](https://innovedumprojects.ethz.ch/projects/groundwater-in-action-real-world-problem-centered-approach-with-students-collaborative-projects/)).

Computational resources for development provided by [hydrosolutions](https://hydrosolutions.ch).

<a href="https://hydrosolutions.ch"><img alt="hydrosolutions" src="_SUPPORT/static/figures/0_readme/hydrosolutionsLogo_Vec.png" width="80"></a>
