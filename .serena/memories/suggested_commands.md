# Suggested Commands for Development

## Environment Setup

### Install uv (Python package manager)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify installation
uv --version
```

### Create and Activate Environment
```bash
# Sync the environment (creates venv and installs dependencies)
uv sync

# Activate the virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### Update Environment (when dependencies change)
```bash
uv sync
```

### Install MODFLOW Executables
```bash
get-modflow :flopy
```

## Git Workflow

### Clone Repository
```bash
git clone https://github.com/mabesa/applied-groundwater-modeling.git
cd applied-groundwater-modeling
```

### Branches
- `main`: Latest stable version
- `course_2025` / `course_2026`: Active course versions
- Feature branches: `year_feature_name`

### Update Local Repository (JupyterHub)
```bash
git fetch origin
git reset --hard origin/course_2025
```

## Development Tools

### Setup Pre-commit Hooks (for contributors)
```bash
uv run pre-commit install
```

### Notebook outputs
Notebook outputs are automatically stripped on commit via pre-commit hook (nbstripout).

### Manual Notebook Output Clearing
```bash
uv run jupyter nbconvert --clear-output --inplace your_notebook.ipynb
```

### Run Dependency Check Script
```bash
uv run python SUPPORT_REPO/src/scripts/check_notebook_dependencies.py
```

## Running Notebooks

### Start JupyterLab
```bash
uv run jupyter lab
```

### Run Diagnostics (first time setup verification)
Open and run `0_diagnostics.ipynb`

### Sync Repository (get latest updates)
Open and run `0_sync_repo.ipynb`

## System Commands (macOS/Darwin)

### File Operations
```bash
ls -la              # List files with details
cd /path/to/dir     # Change directory
pwd                 # Print working directory
```

### Search
```bash
find . -name "*.py" # Find files by name
grep -r "pattern" . # Search in files
```

### Git
```bash
git status          # Check repository status
git diff            # Show changes
git log --oneline   # Show commit history
```
