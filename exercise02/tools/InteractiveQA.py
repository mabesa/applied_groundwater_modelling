import ipywidgets as widgets
from IPython.display import display, HTML, clear_output

class InteractiveQA:
    def __init__(self, questions_and_answers):
        self.qa_pairs = questions_and_answers
        self.current_index = 0
        self.total_questions = len(self.qa_pairs)
        
        # Create widgets
        self.question_text = widgets.HTML(
            value=f"<h3>Question {self.current_index + 1}/{self.total_questions}</h3><p>{self.qa_pairs[self.current_index]['question']}</p>",
            layout=widgets.Layout(width='100%')
        )
        
        self.show_answer_button = widgets.Button(
            description='Show Answer',
            button_style='info',
            layout=widgets.Layout(width='150px')
        )
        
        self.next_button = widgets.Button(
            description='Next Question',
            button_style='success',
            layout=widgets.Layout(width='150px')
        )
        
        self.prev_button = widgets.Button(
            description='Previous Question',
            button_style='warning',
            layout=widgets.Layout(width='150px')
        )
        
        self.reset_button = widgets.Button(
            description='Reset',
            button_style='danger',
            layout=widgets.Layout(width='100px')
        )
        
        self.progress_bar = widgets.IntProgress(
            value=1,
            min=1,
            max=self.total_questions,
            description='Progress:',
            bar_style='info',
            orientation='horizontal'
        )
        
        self.answer_area = widgets.Output()
        
        # Set up layout
        self.button_row = widgets.HBox([self.prev_button, self.show_answer_button, self.next_button, self.reset_button])
        self.qa_container = widgets.VBox([
            self.question_text, 
            self.answer_area, 
            self.button_row,
            self.progress_bar
        ])
        
        # Connect button callbacks
        self.show_answer_button.on_click(self.toggle_answer)
        self.next_button.on_click(self.next_question)
        self.prev_button.on_click(self.prev_question)
        self.reset_button.on_click(self.reset)
        
        # Disable prev button initially
        self.prev_button.disabled = True
        
    def toggle_answer(self, b):
        with self.answer_area:
            clear_output()
            if self.show_answer_button.description == 'Show Answer':
                answer_html = f"""<div style="background-color: #f0f9ff; padding: 15px; border-left: 5px solid #2196F3; margin-top: 10px;">
                <h4>Answer:</h4>
                <p>{self.qa_pairs[self.current_index]['answer']}</p>
                </div>"""
                display(HTML(answer_html))
                self.show_answer_button.description = 'Hide Answer'
            else:
                self.show_answer_button.description = 'Show Answer'
    
    def update_question(self):
        self.question_text.value = f"<h3>Question {self.current_index + 1}/{self.total_questions}</h3><p>{self.qa_pairs[self.current_index]['question']}</p>"
        
        # Update progress bar
        self.progress_bar.value = self.current_index + 1
        
        # Clear answer area
        with self.answer_area:
            clear_output()
        self.show_answer_button.description = 'Show Answer'
        
        # Update button states
        self.prev_button.disabled = (self.current_index == 0)
        self.next_button.disabled = (self.current_index == self.total_questions - 1)
    
    def next_question(self, b):
        if self.current_index < self.total_questions - 1:
            self.current_index += 1
            self.update_question()
    
    def prev_question(self, b):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_question()
    
    def reset(self, b):
        self.current_index = 0
        self.update_question()
    
    def display(self):
        display(self.qa_container)

# Define questions and answers
rev_questions = [
    {
        "question": """<strong>Observation:</strong> As you increased the size of your selected rectangle, what happened to the measured porosity value? Did it converge to a specific value? Why is this significant?""",
        "answer": """As the rectangle size increases, the measured porosity initially fluctuates significantly but eventually stabilizes around the target porosity value. This stabilization demonstrates the existence of a Representative Elementary Volume/Area (REV/REA) - the minimum volume at which a measured property becomes independent of sample size. This is significant because it indicates the scale at which we can meaningfully assign a single porosity value to represent a heterogeneous medium, which is the foundation of continuum-based groundwater modeling."""
    },
    {
        "question": """<strong>Observation:</strong> For the same porosity value (e.g., 0.5), how did changing the blobiness parameter affect the size of rectangle needed to obtain a stable porosity measurement?""",
        "answer": """Higher blobiness values generally require larger rectangle sizes to achieve stable porosity measurements. This is because higher blobiness creates larger, more connected structures (pores and grains), increasing the characteristic length of heterogeneity in the medium. With more spatial correlation (higher blobiness), you need to sample a larger area to capture the full range of the repeating pattern and obtain a representative measurement."""
    },
    {
        "question": """<strong>Observation:</strong> At what approximate sample area did your porosity measurements stabilize for:<br>
        a) Low blobiness (1-2)?<br>
        b) Medium blobiness (2.5-3.5)?<br>
        c) High blobiness (4-5)?""",
        "answer": """Typical stabilization areas are approximately:<br>
        a) Low blobiness (1-2): ~2,500-5,000 μm²<br>
        b) Medium blobiness (2.5-3.5): ~5,000-10,000 μm²<br>
        c) High blobiness (4-5): ~10,000-20,000 μm² or larger<br><br>
        These values demonstrate how the REV size increases with increased spatial correlation (blobiness). In real-world terms, this means that more heterogeneous aquifers require larger sample volumes for representative characterization."""
    },
    {
        "question": """<strong>Concept:</strong> Why is the concept of REV important when setting up a numerical groundwater model? How does it relate to grid cell size selection?""",
        "answer": """The REV concept is crucial for numerical groundwater modeling because it determines the minimum scale at which continuum approaches (like Darcy's Law) are valid. In numerical modeling, grid cells should be at least as large as the REV to ensure that assigned parameter values (hydraulic conductivity, porosity, etc.) are physically meaningful and representative.<br><br>
        If grid cells are smaller than the REV, the assigned property values may not be representative, and the continuum assumption breaks down. This can lead to numerical instabilities and physically unrealistic results. The REV thus provides a theoretical lower bound for grid cell size in physics-based models."""
    },
    {
        "question": """<strong>Concept:</strong> What happens if you choose a grid size smaller than the REV for your numerical model? What about significantly larger?""",
        "answer": """<strong>Grid size smaller than REV:</strong> This can lead to several problems:<br>
        - Violation of the continuum assumption underlying Darcy's Law<br>
        - Physically meaningless property values that capture random variations rather than representative behavior<br>
        - Potential numerical instability and increased computational costs<br>
        - Difficulty in parameterization, as measurements at this scale are highly variable<br><br>
        <strong>Grid size much larger than REV:</strong><br>
        - May oversimplify the system by averaging out important heterogeneity<br>
        - Could miss preferential flow paths or barriers that affect overall system behavior<br>
        - Reduces computational burden but at the cost of resolution and accuracy<br>
        - May require effective parameters that aren't directly measurable"""
    },
    {
        "question": """<strong>Critical Thinking:</strong> Based on your observations, which parameter has a greater effect on the size of the REV: porosity or blobiness? Explain your reasoning.""",
        "answer": """Blobiness typically has a greater effect on REV size than porosity. As blobiness increases, the characteristic length of heterogeneity increases, requiring larger samples to obtain representative measurements.<br><br>
        This occurs because blobiness directly controls the spatial correlation structure of the medium - higher blobiness creates larger, more connected pore/grain structures with longer correlation lengths. While porosity affects the REV size to some extent (with intermediate porosities often requiring larger REVs), the spatial distribution of the pores (controlled by blobiness) generally has a more pronounced effect on how quickly measurements stabilize with increasing sample size."""
    },
    {
        "question": """<strong>Critical Thinking:</strong> From your simulations, at what porosity value did you observe the largest REV size? Can you explain why this happens from a physical perspective?""",
        "answer": """The largest REV typically occurs at intermediate porosity values (around 0.5). This happens because:<br><br>
        At extreme porosities (very high or very low), the medium becomes more homogeneous - either mostly pores (high porosity) or mostly solids (low porosity). With this increased homogeneity, smaller samples can adequately represent the system.<br><br>
        At intermediate porosities (~0.5), there's maximum phase interface complexity and tortuosity. The solid and void phases are both continuous and intertwined, creating complex geometries that require larger samples to capture representative behavior. This is related to percolation theory - near the percolation threshold, correlation lengths are maximized, requiring larger REVs."""
    },
    {
        "question": """<strong>Application:</strong> If your model domain represents an aquifer with dimensions of 10 km × 10 km, and your REV analysis suggests a minimum representative area of 10,000 μm², what is the maximum number of grid cells you should use in your model to ensure valid application of Darcy's Law?""",
        "answer": """Assuming each pixel represents 1 μm, a REV of 10,000 μm² corresponds to dimensions of approximately 100 μm × 100 μm (square root of area).<br><br>
        For a 10 km × 10 km domain:<br>
        - In each direction: 10 km = 10,000,000 μm<br>
        - Maximum number of cells in each direction: 10,000,000 μm ÷ 100 μm = 100,000 cells<br>
        - Maximum total cells: 100,000 × 100,000 = 10,000,000,000 cells<br><br>
        This represents a theoretical maximum. In practice, computational limitations would likely necessitate using far fewer cells, and you would probably use much larger cells to balance computational efficiency with physical accuracy."""
    },
    {
        "question": """<strong>Application:</strong> How might the REV concept change when dealing with:<br>
        a) Fractured rock aquifers<br>
        b) Layered sedimentary aquifers<br>
        c) Karst systems""",
        "answer": """<strong>a) Fractured rock aquifers:</strong> REV may be much larger due to the importance of discrete features (fractures). In some cases, an REV might not exist if fracture spacing is highly variable or if a few dominant fractures control flow. This might necessitate discrete fracture modeling approaches rather than continuum methods.<br><br>
        <strong>b) Layered sedimentary aquifers:</strong> REV likely varies by layer and might be anisotropic (different in horizontal vs. vertical directions). Horizontally, the REV might be smaller within a single layer, but vertically it needs to include multiple layers to be representative. This often leads to using anisotropic grid cells that are wider than they are tall.<br><br>
        <strong>c) Karst systems:</strong> Similar to fractured rock, an REV might not exist due to highly developed preferential flow paths (conduits, caves). The extreme heterogeneity with features spanning many orders of magnitude makes traditional REV-based approaches problematic. Alternative modeling approaches like dual-porosity, dual-permeability, or discrete conduit models are often needed."""
    },
    {
        "question": """<strong>Application:</strong> A colleague is modeling an aquifer with regions of varying heterogeneity. Should they use a uniform grid cell size throughout their domain? Why or why not?""",
        "answer": """Variable grid cell sizes are often more appropriate when heterogeneity varies spatially across an aquifer. This approach is beneficial because:<br><br>
        - Regions with higher heterogeneity (larger characteristic lengths) require larger cells to satisfy REV requirements<br>
        - More homogeneous regions can use smaller cells for higher resolution where it matters<br>
        - Adaptive mesh refinement approaches balance computational efficiency with physical accuracy<br>
        - Areas of particular interest (e.g., near pumping wells or contaminant sources) can be assigned finer resolution<br><br>
        The key principle is that grid resolution should be fine enough to capture important variations in aquifer properties and hydraulic gradients, but not so fine that it violates REV assumptions or creates unnecessary computational burden."""
    }
]