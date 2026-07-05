# Development Guide

This guide is for developers and contributors working on the Applied Groundwater Modelling course materials. It covers environment setup, AI-assisted development tools, and contribution workflows.

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Contributing](#2-contributing)
3. [Code Style and Conventions](#3-code-style-and-conventions)

---

## 1. Environment Setup

### 1.1 Installing uv

[uv](https://docs.astral.sh/uv/) is a fast Python package and project manager. We use it for environment management and running tools.

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Via pip (alternative):**
```bash
pip install uv
```

Verify the installation:
```bash
uv --version
```

### 1.2 Python Environment (uv)

Create and activate the development environment:

```bash
# Sync the environment (creates venv and installs dependencies)
uv sync

# Activate the virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows
```

To update dependencies:
```bash
uv sync
```

### 1.3 MODFLOW Executables

After activating your environment, install MODFLOW:

```bash
get-modflow :flopy
```

### 1.4 Pre-commit Hooks

Set up pre-commit hooks to automatically strip notebook outputs on commit:

```bash
uv run pre-commit install
```

This installs a git hook that runs `nbstripout` automatically when you commit `.ipynb` files. No manual output clearing needed!

---

## 2. Contributing

### 2.1 Git Workflow

1. **Fork the repository** (if not a collaborator)

2. **Create a feature branch**:
   ```bash
   git checkout course_2026
   git checkout -b your-feature-name
   ```

3. **Make changes** following the code style guidelines

4. **Test your changes**: Ensure notebooks run without errors
   ```bash
   # Run all cells in your notebook
   jupyter nbconvert --execute --inplace your_notebook.ipynb
   ```

5. **Clear notebook outputs** (if not using nbstripout):
   ```bash
   jupyter nbconvert --clear-output --inplace your_notebook.ipynb
   ```

6. **Submit a Pull Request** to the appropriate branch

### 2.2 Branch Structure

- `main` - Latest stable version
- `course_2025`, `course_2026` - Active course versions
- Feature branches - For development work

### 2.3 Testing

Run the dependency check script:
```bash
python _SUPPORT/src/scripts/check_notebook_dependencies.py
```

### 2.4 Documentation

- Update `README.md` for user-facing changes
- Check `planning/` for any planning documents to update

---

## 3. Code Style and Conventions

### 3.1 Python Style

**Docstrings** - Use detailed docstrings with Args and Returns:
```python
def calculate_transmissivity(K, thickness):
    """
    Calculate aquifer transmissivity.

    Args:
        K (float): Hydraulic conductivity (m/day)
        thickness (float): Aquifer thickness (m)

    Returns:
        float: Transmissivity (m²/day)
    """
    return K * thickness
```

**Naming:**
- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

### 3.2 Notebook Conventions

**Structure:**
- Use numbered headings (1., 1.1, 1.1.1)
- Clear markdown explanations between code cells
- One logical operation per cell

**Content boxes** - Use blockquotes with emoji indicators:
```markdown
> 💡 **Example: Calculating Drawdown**
>
> This example shows how to calculate drawdown...

> 📚 **Theory: Darcy's Law**
>
> Darcy's Law describes...

> ⚠️ **Warning: Units**
>
> Ensure all units are consistent...
```

### 3.3 Accessibility

**Images** - Always include descriptive alt text:
```markdown
![Cross-section showing three aquifer layers with flow arrows indicating groundwater movement from east to west](path/to/image.png)
```

**Widgets** - Include clear descriptions:
```python
checkbox = widgets.Checkbox(
    value=False,
    description="Step 1: Complete the boundary conditions setup",
    style={'description_width': 'initial'}
)
```

**Color** - Never use color alone to convey information.

### 3.4 File Organization

**Utility modules** go in `_SUPPORT/src/`:
- `data_utils.py` - Data download and management
- `map_utils.py` - Map visualization
- `grid_utils.py` - Model grid operations
- `plot_utils.py` - Plotting helpers

**Static files** go in `_SUPPORT/static/`.

---

## Quick Reference

| Task | Command |
|------|---------|
| Sync environment | `uv sync` |
| Activate environment | `source .venv/bin/activate` |
| Install MODFLOW | `get-modflow :flopy` |
| Setup pre-commit | `uv run pre-commit install` |
| Clear notebook outputs (manual) | `uv run jupyter nbconvert --clear-output --inplace notebook.ipynb` |
| Check dependencies | `uv run python _SUPPORT/src/scripts/check_notebook_dependencies.py` |
| Run Jupyter | `uv run jupyter lab` |

---

## Resources

- [FloPy Documentation](https://flopy.readthedocs.io/)
- [MODFLOW 6 Documentation](https://modflow6.readthedocs.io/)
- [uv Documentation](https://docs.astral.sh/uv/)
