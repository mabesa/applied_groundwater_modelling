# Code Style and Conventions

## General Python Style

### Docstrings
Use detailed docstrings with Args, Returns, and examples:

```python
def theis_analysis(time, drawdown, pumping_rate, distance):
    """
    Analyze pumping test data using the Theis method.
    
    Args:
        time (array): Time since pumping started (days)
        drawdown (array): Observed drawdown (meters)
        pumping_rate (float): Constant pumping rate (m³/day)
        distance (float): Distance from pumping well (meters)
    
    Returns:
        dict: Calculated aquifer properties
    """
    # Implementation here...
```

### Type Hints
Not strictly enforced but encouraged for clarity, especially in utility modules.

### Naming Conventions
- Functions: `snake_case` (e.g., `download_named_file`, `plot_model_area_map`)
- Variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

## Jupyter Notebook Conventions

### Cell Organization
- Clear markdown headers with logical hierarchy (H1 → H2 → H3)
- Use numbered sections (e.g., "# 1. Introduction", "## 1.1 Basic Principles")
- Separate code cells for distinct operations

### Output Management
**CRITICAL**: Clear all notebook outputs before committing!
- Manual: `Kernel` → `Restart & Clear Output`
- Automated: Use `nbstripout` (installed via pre-commit)

### Content Boxes (Markdown)
Use blockquote format with emoji indicators:
```markdown
> 💡 **Example: Clear Title**
> 
> Content goes here with clear, descriptive text.

> 📚 **Theory: Groundwater Flow Equation**
> 
> The groundwater flow equation combines...

> ⚠️ **Warning: Important Note**
> 
> Pay attention to...
```

## Accessibility Requirements

### Images
Always include descriptive alt text:
```markdown
![Graph showing groundwater head decline over time from 2010 to 2020, starting at 15m and declining to 8m](path/to/image.png)
```

### Interactive Widgets
Use proper labels and descriptions:
```python
checkbox = widgets.Checkbox(
    value=False,
    description="Step 1: Problem Definition - Mark complete when you understand...",
    style={'description_width': 'initial'},
    layout=widgets.Layout(width='100%')
)
```

### Color Usage
- Ensure sufficient contrast (4.5:1 minimum)
- Never use color alone to convey information
- Provide text/pattern alternatives

## Mathematical Content
Always provide text explanations alongside equations:
```markdown
The Darcy velocity (v) is calculated as:

v = Ki

Where:
- v = Darcy velocity (m/day)
- K = hydraulic conductivity (m/day)  
- i = hydraulic gradient (dimensionless)
```

## File Organization

### Utility Modules Location
Place utility code in `SUPPORT_REPO/src/`:
- `data_utils.py` - Data download and file management
- `map_utils.py` - Map visualization functions
- `grid_utils.py` - Model grid operations
- `plot_utils.py` - Plotting helpers
- `river_utils.py` - River data processing

### Configuration
- Use `config.py` for data source configuration
- Never commit `config.py` (contains private links)
- Provide `config_template.py` for reference
