# Instructions for Copilot

## Project Context
This is an educational groundwater modeling course for Master-level students at ETH Zurich. The project focuses on practical modeling skills using MODFLOW, MT3D, and FloPy through real-world case studies, particularly the Limmat valley aquifer.

## Technical Environment
- Use library versions specified in environment_development.yml as context
- Python 3.12 environment
- Jupyter notebook-based content delivery

## Code Style & Standards
- Use lower case with underscores for function and variable names
- Use type hints in function signatures
- Use triple quotes for docstrings with clear parameter descriptions
- Follow groundwater modeling domain conventions (e.g., hydraulic conductivity as `K`, head as `h`)
- Include units in variable names or comments where applicable (e.g., `K_ms` for K in m/s)

## Educational Content Guidelines
- **Pedagogical Approach**: Structure content progressively from basic concepts to complex applications
- **Interactive Elements**: Use ipywidgets for interactive exercises and visualizations
- **Visual Learning**: Prioritize clear, well-labeled plots and diagrams for hydrogeological concepts
- **Real-world Context**: Connect theoretical concepts to practical applications and case studies
- **Error Handling**: Provide clear, educational error messages that guide learning

## Notebook Structure Standards
- Start notebooks with standardized imports from SUPPORT_REPO/src
- Use consistent markdown formatting with > for boxes. Below you find examples of the different boxes we use. 
- Include clear section headers and learning objectives
- Provide context and motivation before technical content

### Example Boxes
```markdown
> ✏️ **Exercise: Limmat Valley Aquifer Analysis**
> 
> What are the major hydrological processes in the Limmat valley aquifer?
> 
> Where would you set the boundaries of the Limmat valley aquifer?
```

```markdown
> 🤔 **Further Thinking: River Flow Analysis**
> 
> Please take some time to familiarize yourself with the yearbook sheets.
> 
> Did you notice the different shapes of the flow duration curves? What does this tell you about the hydrological regime of the rivers?
> 
> Can you find the highest ever measured discharge in both rivers? Which one might be the more difficult to manage?
```

```markdown 
> 📚 **Theory: Groundwater Flow Equation**
> 
> The groundwater flow equation is a partial differential equation that describes the movement of groundwater through porous media. It is based on Darcy's law and the principle of mass conservation.
```

```markdown
> 💡 **Example: Simple Classification**
> 
> A mouse is an example of a mammal.
```


## Domain-Specific Considerations
- **Units**: Always specify units for hydrogeological parameters (m/day, m³/s, etc.)
- **Coordinate Systems**: Use appropriate Swiss coordinate systems when relevant
- **Model Validation**: Emphasize the importance of model calibration and validation
- **Uncertainty**: Address uncertainty quantification in modeling results
- **Best Practices**: Promote good modeling practices and critical evaluation of results

## Function Documentation Template
```python
def calculate_hydraulic_conductivity(q: float, gradient: float, area: float) -> float:
    """
    Calculate hydraulic conductivity using Darcy's Law.
    
    Parameters:
    - q (float): Discharge rate [m³/s]
    - gradient (float): Hydraulic gradient [dimensionless]
    - area (float): Cross-sectional area [m²]
    
    Returns:
    - float: Hydraulic conductivity [m/s]
    
    Example:
    >>> K = calculate_hydraulic_conductivity(0.001, 0.01, 10.0)
    >>> print(f"K = {K:.2e} m/s")
    """
    return q / (gradient * area)
```

## Interactive Exercise Standards
- Use the shared_functions framework for consistent task checking
- Provide meaningful feedback for both correct and incorrect answers
- Include solution toggles with detailed explanations
- Encourage critical thinking through follow-up questions

## Visualization Guidelines
- Use consistent color schemes and styling via load_project_styles()
- Label all axes with appropriate units
- Include legends and titles for all plots
- Create publication-quality figures for key concepts
- Use interactive plots (ipympl) for exploration when beneficial

## Assessment Integration
- Align content with learning objectives
- Distinguish between required knowledge (exam-relevant) and supplementary material
- Provide clear connections between exercises and real-world applications
- Include references to relevant literature and data sources

## Accessibility Guidelines

### Visual Accessibility
- **Color Usage**: Never rely solely on color to convey information; always pair with text, symbols, or patterns
- **Color Contrast**: Ensure sufficient contrast ratios (minimum 4.5:1 for normal text, 3:1 for large text)
- **Colorblind-Friendly Palettes**: Use colorblind-safe color schemes (e.g., viridis, plasma) for plots and visualizations
- **Font Sizes**: Use readable font sizes (minimum 12pt) and scalable text in plots
- **Image Descriptions**: Provide detailed alt-text for all images, diagrams, and plots

### Content Structure & Navigation
- **Hierarchical Headers**: Use proper markdown header hierarchy (H1 → H2 → H3) for screen readers
- **Clear Navigation**: Provide table of contents for longer notebooks
- **Logical Flow**: Structure content in logical, sequential order
- **Section Breaks**: Use clear visual and textual breaks between concepts

### Mathematical Content
- **LaTeX Accessibility**: Use semantic LaTeX commands when possible (e.g., `\frac{}{}` instead of `/`)
- **Variable Definitions**: Always define mathematical symbols and variables in text
- **Unit Clarity**: State units clearly and consistently, both in text and equations
- **Alternative Descriptions**: Provide text descriptions of complex equations and their physical meaning

### Interactive Elements
- **Keyboard Navigation**: Ensure all interactive widgets are keyboard accessible
- **Clear Instructions**: Provide explicit instructions for using interactive elements
- **Multiple Input Methods**: Support both mouse and keyboard interactions
- **Timeout Considerations**: Avoid time-limited interactions unless absolutely necessary

### Code Accessibility
- **Descriptive Variable Names**: Use self-explanatory variable names that convey meaning
- **Extensive Comments**: Include detailed comments explaining code logic and hydrogeological concepts
- **Error Messages**: Provide clear, instructive error messages that guide problem-solving
- **Code Structure**: Use consistent indentation and clear code organization

### Language & Communication
- **Plain Language**: Use clear, concise language appropriate for non-native speakers
- **Technical Jargon**: Define all technical terms when first introduced
- **Active Voice**: Prefer active voice for clarity
- **Cultural Sensitivity**: Use inclusive examples and avoid cultural assumptions
- **Multiple Learning Styles**: Address visual, auditory, and kinesthetic learning preferences




