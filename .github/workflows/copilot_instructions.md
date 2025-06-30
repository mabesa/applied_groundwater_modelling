# Instructions for Copilot

## Project Context
This is an educational groundwater modeling course for Master-level students at ETH Zurich. The project focuses on practical modeling skills using MODFLOW, MT3D, and FloPy through real-world case studies, particularly the Limmat valley aquifer.

## Technical Environment
- Use library versions specified in environment_development.yml as context
- Primary libraries: FloPy 3.9.2, NumPy 1.26.4, Matplotlib 3.10.1, Pandas 2.2.3, GeoPandas 1.0.1
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
- Use consistent markdown formatting with custom CSS boxes:
  - `exercise-box` for required thinking exercises
  - `example-box` for practical examples
  - `furtherthinking-box` for optional advanced topics
- Include clear section headers and learning objectives
- Provide context and motivation before technical content

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

### Data Visualization Accessibility
```python
# Example of accessible plotting
def create_accessible_plot(x_data, y_data, title, xlabel, ylabel):
    """
    Create an accessible plot with proper labels and descriptions.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Use accessible colors and markers
    ax.plot(x_data, y_data, 'o-', color='#1f77b4', linewidth=2, markersize=6)
    
    # Clear, descriptive labels
    ax.set_xlabel(f'{xlabel} [units]', fontsize=12, fontweight='bold')
    ax.set_ylabel(f'{ylabel} [units]', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # Grid for easier reading
    ax.grid(True, alpha=0.3)
    
    # Ensure readable tick labels
    ax.tick_params(labelsize=10)
    
    plt.tight_layout()
    return fig, ax
```

### Documentation Standards for Accessibility
- **Image Alt-Text Template**: "Figure X: [Brief description]. [Detailed description of key elements, trends, and relationships shown]. [Context for why this is important in groundwater modeling]."
- **Table Descriptions**: Provide summary descriptions for data tables
- **Link Descriptions**: Use descriptive link text instead of "click here" or URLs
- **Abbreviation Expansion**: Spell out acronyms on first use (e.g., "Representative Elementary Volume (REV)")

### Testing & Validation
- **Screen Reader Testing**: Test content with screen reader software when possible
- **High Contrast Mode**: Verify content remains usable in high contrast display modes
- **Zoom Testing**: Ensure content remains functional at 200% zoom
- **Keyboard-Only Navigation**: Test all interactive elements using only keyboard input

### Inclusive Design Principles
- **Multiple Representations**: Present information in multiple formats (text, visual, audio when applicable)
- **Flexible Interaction**: Provide alternative ways to complete tasks
- **Progressive Disclosure**: Allow users to access increasing levels of detail as needed
- **Error Prevention**: Design interfaces to prevent common errors rather than just handle them

## Accessibility in Assessment & Feedback

### Exercise Design
- **Multiple Input Formats**: Accept various answer formats (numerical, text descriptions, conceptual explanations)
- **Clear Success Criteria**: Provide explicit criteria for what constitutes a correct or acceptable answer
- **Partial Credit Recognition**: Acknowledge partially correct approaches and provide constructive guidance
- **Time Flexibility**: Avoid strict time limits unless pedagogically essential

### Feedback Mechanisms
- **Multi-Modal Feedback**: Provide feedback through text, visual indicators, and when possible, audio cues
- **Specific Guidance**: Give actionable feedback rather than just "incorrect" or "try again"
- **Positive Reinforcement**: Acknowledge correct reasoning even when final answers are incorrect
- **Learning Path Suggestions**: Direct students to relevant resources for improvement

### Interactive Widget Accessibility
```python
# Example of accessible widget design
def create_accessible_input_widget(question_text, hint_text=""):
    """
    Create an accessible input widget with proper labeling and instructions.
    """
    # Clear question display
    question_display = widgets.HTML(
        value=f"<h3>{question_text}</h3>",
        description=""
    )
    
    # Input with clear description
    answer_input = widgets.FloatText(
        description="Your answer:",
        style={'description_width': '120px'},
        placeholder="Enter numerical value"
    )
    
    # Optional hint
    if hint_text:
        hint_display = widgets.HTML(
            value=f"<em>Hint: {hint_text}</em>",
            description=""
        )
        return widgets.VBox([question_display, answer_input, hint_display])
    
    return widgets.VBox([question_display, answer_input])
```

### Alternative Assessment Methods
- **Conceptual Questions**: Include qualitative questions alongside quantitative problems
- **Diagram Interpretation**: Provide text-based alternatives to visual diagram questions
- **Peer Discussion**: Encourage collaborative problem-solving and explanation
- **Portfolio Approach**: Allow multiple ways to demonstrate understanding

## Implementation Checklist

### For Each Notebook
- [ ] Header hierarchy follows logical structure (H1 → H2 → H3)
- [ ] All images have descriptive alt-text
- [ ] Color-coding is supplemented with text/symbols
- [ ] Mathematical notation is properly formatted and explained
- [ ] Interactive elements have clear instructions
- [ ] Code includes explanatory comments
- [ ] Technical terms are defined on first use

### For Visualizations
- [ ] Colorblind-friendly palette used
- [ ] Sufficient contrast ratios maintained
- [ ] All axes properly labeled with units
- [ ] Legend/key provided when needed
- [ ] Alternative text description included
- [ ] Data patterns described in text

### For Exercises
- [ ] Multiple input methods supported
- [ ] Clear success criteria provided
- [ ] Constructive feedback implemented
- [ ] Keyboard navigation functional
- [ ] Instructions are unambiguous


