# Task Completion Checklist

## Before Committing Code

### 1. Notebook Output Clearing
- [ ] Clear all notebook outputs before committing
- [ ] Option A: `Kernel` → `Restart & Clear Output` in Jupyter
- [ ] Option B: `jupyter nbconvert --clear-output --inplace notebook.ipynb`
- [ ] If nbstripout is installed, this happens automatically

### 2. Sensitive Information Check
- [ ] No API keys, passwords, or credentials in code
- [ ] No private URLs (SWITCHdrive links, etc.)
- [ ] No personal data or student information
- [ ] Review `.serena/memories/` content before committing

### 3. Code Quality
- [ ] Functions have docstrings with Args and Returns
- [ ] No hardcoded file paths (use `data_utils.py` functions)
- [ ] Mathematical content has text explanations

### 4. Accessibility
- [ ] Images have descriptive alt text
- [ ] Widgets have proper labels
- [ ] Color is not the only indicator of information

### 5. Testing
- [ ] Notebooks run without errors (Restart & Run All)
- [ ] Data downloads work correctly
- [ ] Visualizations display properly

### 6. Environment Files
- [ ] If new packages added, update `pyproject.toml`
- [ ] Run `uv sync` to update lock file

## For Pull Requests

### Before Submitting
- [ ] Base branch is correct (usually `develop` or year branch)
- [ ] All notebooks have cleared outputs
- [ ] Run dependency check: `python _SUPPORT/src/scripts/check_notebook_dependencies.py`
- [ ] Commit messages are clear and descriptive

### PR Description Should Include
- Description of changes
- Testing performed
- Any new dependencies added

## Development Workflow

### Setting Up
1. Fork repository (if not collaborator)
2. Create feature branch from current year branch
3. Activate development environment: `conda activate gw_course_development`

### During Development
1. Make changes in feature branch
2. Test notebooks with `Restart & Run All`
3. Clear outputs before committing
4. Commit with clear messages

### After Development
1. Push to remote
2. Create Pull Request
3. Address review feedback
4. Merge when approved

## CI/CD Pipeline
The repository uses GitHub Actions to:
- Check notebook dependencies automatically
- Verify environment configuration
- Run on push to `**.ipynb` or `**.yml` files
