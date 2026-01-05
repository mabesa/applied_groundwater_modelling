# Development Guide

This guide is for developers and contributors working on the Applied Groundwater Modelling course materials. It covers environment setup, AI-assisted development tools, and contribution workflows.

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [AI-Assisted Development](#2-ai-assisted-development)
3. [Contributing](#3-contributing)
4. [Code Style and Conventions](#4-code-style-and-conventions)

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

## 2. AI-Assisted Development

This project is configured for AI-assisted development using Claude Code with MCP (Model Context Protocol) servers. Two MCP servers are pre-configured:

- **Context7**: Provides up-to-date documentation for any library
- **Serena**: Semantic code analysis and intelligent editing tools

### 2.1 MCP Server Configuration

The MCP servers are configured in `.vscode-mcp.json`:

```json
{
    "mcp": {
        "servers": {
            "context7": {
                "type": "http",
                "url": "https://mcp.context7.com/mcp"
            },
            "serena": {
                "type": "stdio",
                "command": "uvx",
                "args": [
                    "--from", "git+https://github.com/oraios/serena",
                    "serena", "start-mcp-server",
                    "--project-root", "${workspaceFolder}"
                ]
            }
        }
    }
}
```

### 2.2 Using Context7

Context7 provides up-to-date documentation for any library. It's automatically available when Claude Code starts.

**Example usage in conversation:**
- "Look up the FloPy documentation for creating a MODFLOW model"
- "What's the latest API for geopandas.read_file?"

### 2.3 Using Serena

Serena provides semantic code analysis tools that understand your codebase structure.

#### Getting Started with Serena

When starting a new Claude Code session, Serena needs to be onboarded to understand the project:

```
serena onboarding()
```

This creates memory files with project information that persist across sessions.

#### Serena Capabilities

**Code Navigation:**
- `find_symbol` - Find classes, functions, methods by name
- `get_symbols_overview` - Get overview of symbols in a file
- `find_referencing_symbols` - Find where a symbol is used

**Code Editing:**
- `replace_symbol_body` - Replace a function/method definition
- `insert_after_symbol` / `insert_before_symbol` - Add code near a symbol
- `rename_symbol` - Rename across the codebase

**Search:**
- `search_for_pattern` - Regex search across files
- `find_file` - Find files by name pattern
- `list_dir` - List directory contents

**Memory:**
- `list_memories` - See saved project knowledge
- `read_memory` - Read a memory file
- `write_memory` - Save new knowledge

#### Serena Workflow Tips

1. **Start sessions with**: Check if onboarding was performed
2. **Use symbolic tools**: Prefer `find_symbol` over grep for code
3. **Read before editing**: Always understand code before modifying
4. **Think tools**: Use `think_about_collected_information` and `think_about_task_adherence` to verify your approach

### 2.4 Project Context for AI

The `.claude/context.md` file provides project-specific context for AI assistants, including:
- Key planning documents to reference
- Repository structure
- Development guidelines
- Important design decisions

---

## 3. Contributing

### 3.1 Git Workflow

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

### 3.2 Branch Structure

- `main` - Latest stable version
- `course_2025`, `course_2026` - Active course versions
- Feature branches - For development work

### 3.3 Testing

Run the dependency check script:
```bash
python _SUPPORT/src/scripts/check_notebook_dependencies.py
```

### 3.4 Documentation

- Update `README.md` for user-facing changes
- Update `.claude/context.md` for AI-relevant context
- Check `planning/` for any planning documents to update

---

## 4. Code Style and Conventions

### 4.1 Python Style

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

### 4.2 Notebook Conventions

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

### 4.3 Accessibility

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

### 4.4 File Organization

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
| Serena onboarding | `serena onboarding()` in Claude Code |

---

## Resources

- [FloPy Documentation](https://flopy.readthedocs.io/)
- [MODFLOW 6 Documentation](https://modflow6.readthedocs.io/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [Serena GitHub](https://github.com/oraios/serena)
- [Context7](https://context7.com/)
