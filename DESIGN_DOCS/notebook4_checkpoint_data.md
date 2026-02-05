# Notebook 4: Checkpoint Data for tasks_data.py

This document specifies the checkpoint questions and acceptable answer ranges that should be added to `_SUPPORT/src/scripts/scripts_exercises/tasks_data.py` for Sections 6-8.

---

## Checkpoint Definitions

### Checkpoint 4: Water Balance Error (Numerical)

**Location:** Section 7.3
**Type:** Numerical answer with tolerance range

Add to `tasks_data.py`:

```python
# Section 7.3: Water Balance Error Checkpoint
"task04_checkpoint_4": r"""
## Numerical Checkpoint 4 - Water Balance

Examining your steady-state simulation results:
- **What is the water balance error (%)?**

(Round to 1 decimal place. Enter as percentage, e.g., 0.05 for 0.05%)
"""

# Acceptable answer range
solutions["task04_checkpoint_4"] = (0.0, 0.15)  # Accepts 0.0 - 0.15% error

# Note: This range (0.0-0.15%) is stricter than the (0, 1) currently in tasks_data.py.
# The stricter tolerance is recommended for well-configured MODFLOW 6 models.
# Consider updating tasks_data.py to use (0.0, 0.15) for better quality assurance,
# or keep (0, 1) for more permissive grading during initial model development.

# Exact solution (for this particular model setup)
solutions_exact["task04_checkpoint_4"] = "0.08"  # Will vary by model configuration

# Unit specification
solution_unit["task04_checkpoint_4"] = "%"

# Solution explanation
solutions_markdown["task04_checkpoint_4"] = r"""
## Water Balance Error Calculation

For a steady-state MODFLOW 6 model:

$$\text{Mass Balance Error} = \frac{|\sum Q_{in} - \sum Q_{out}|}{\sum Q_{in}} \times 100\%$$

Where:
- $\sum Q_{in}$ = sum of all inflows (m³/day) from RCH, RIV (gaining), WEL (injecting), boundary inflows
- $\sum Q_{out}$ = sum of all outflows (m³/day) to WEL (pumping), RIV (losing), constant-head boundaries, etc.

**Expected result:** < 0.1% error for properly configured MODFLOW 6 models

**Why it matters:**
- Close to zero error indicates correct boundary condition assignment
- Large errors (> 1%) suggest missing or incorrectly defined boundary conditions
- Small residual (< 0.1%) shows the nonlinear solver converged properly

**In your model:**
The exact error depends on your specific discretization and parameter values. The tolerance range of 0.0–0.15% allows for small differences due to numerical precision and cell-level variations.
"""

```

---

### Checkpoint 5: River Gaining/Losing (Conceptual - Multiple Choice)

**Location:** Section 7.5
**Type:** Conceptual question with multiple choice

This checkpoint requires modified handling since it's multiple choice, not numerical. You have two options:

#### Option 1: Create a separate multi-choice system

If `tasks_data.py` already supports multiple choice (check existing structure):

```python
# Section 7.5: River Gaining/Losing Checkpoint
"task04_checkpoint_5": r"""
## Conceptual Checkpoint 1 - River-Aquifer Interaction

Based on your simulated heads and water balance summary:
- **Is the Limmat River gaining or losing water from the aquifer in your model?**

A) **Gaining** (groundwater flows into river)
B) **Losing** (river water infiltrates into aquifer)
C) **Mixed** (both occurring at different locations)

**Explain briefly:** How can you tell from the simulation results?
(You should cite either the RIV budget term or head comparisons.)
"""

# Multiple choice solutions
solutions_mc["task04_checkpoint_5"] = ["B", "A", "C"]  # Acceptable answers (ordered by likelihood)
solutions_exact["task04_checkpoint_5"] = "B"  # Most likely answer for Limmat

solutions_markdown["task04_checkpoint_5"] = r"""
## River-Aquifer Interaction Interpretation

**For the Limmat River in your simulation:**

The Limmat is typically a **LOSING stream** (Option B) in the Limmat Valley model area. Here's how to determine this:

### Method 1: From Water Balance Budget

**MODFLOW Budget Convention:**
- In the MODFLOW budget, check the RIV package
- If dominant flux is in the 'IN' column → river losing water to aquifer (losing stream)
- If dominant flux is in the 'OUT' column → aquifer losing water to river (gaining stream)

Simplified:
- **Positive RIV flow (IN)** = water flows FROM river INTO aquifer (losing stream)
- **Negative RIV flow (OUT)** = water flows FROM aquifer INTO river (gaining stream)

### Method 2: From Head Comparison
- Compare simulated heads at river cells to river stage (specified boundary condition)
- If $H_{aquifer} < H_{river}$: River is losing water (water infiltrates down)
- If $H_{aquifer} > H_{river}$: River is gaining water (groundwater flows toward it)

### Why the Limmat is Losing
The Limmat Valley aquifer benefits from river infiltration as a primary water source. The river stage is generally higher than the aquifer head, driving water downward through the riverbed clogging layer. This is consistent with:
- Hardhof managed aquifer recharge system (artificially pumping and infiltrating river water)
- The perceptual model's water balance showing river as major inflow
- Historical calibration studies (Doppler et al., 2007)

### What About the Sihl?
The River Sihl, with its deeper incision and thicker clogging layer, shows even stronger losing character (clearly disconnected in Notebook 2 analysis).

**Note:** Losing/gaining can vary seasonally and spatially. Your uncalibrated model shows the average steady-state condition.
"""
```

---

### REQUIRED: Multiple-Choice Widget Implementation

**Current State:** `shared_functions.py` does NOT have multiple-choice support. This MUST be added.

**Add this function to `_SUPPORT/src/scripts/scripts_exercises/shared_functions.py`:**

```python
def check_multiple_choice(task_id):
    """
    Create and display a multiple-choice checkpoint widget.

    Parameters:
        task_id: str - The checkpoint identifier (e.g., "task04_checkpoint_5")

    Usage in notebook:
        from shared_functions import check_multiple_choice
        check_multiple_choice("task04_checkpoint_5")
    """
    import ipywidgets as widgets
    from IPython.display import display, Markdown

    # Get question and options from tasks_data
    question = questions_markdown.get(task_id, "Question not found")
    correct_answer = solutions_exact.get(task_id, "")
    solution_text = solutions_markdown.get(task_id, "")

    # Display question
    display(Markdown(question))

    # Define options for this checkpoint (hardcoded for task04_checkpoint_5)
    if task_id == "task04_checkpoint_5":
        options = [
            ("A", "A) Gaining (groundwater flows into river)"),
            ("B", "B) Losing (river water infiltrates into aquifer)"),
            ("C", "C) Mixed (both occurring at different locations)")
        ]
    else:
        options = [("?", "Options not defined for this task")]

    # Create radio buttons
    radio = widgets.RadioButtons(
        options=[(label, value) for value, label in options],
        description='',
        disabled=False,
        layout=widgets.Layout(width='100%')
    )

    # Create buttons
    submit_btn = widgets.Button(description="Check Answer", button_style='primary')
    show_solution_btn = widgets.Button(description="Show Solution", button_style='info')

    # Output area
    output = widgets.Output()

    def on_submit(b):
        with output:
            output.clear_output()
            selected = radio.value
            # Check if answer starts with correct letter
            if selected == correct_answer or selected.startswith(correct_answer):
                print("✅ Correct! Well done.")
            else:
                print(f"❌ Not quite. Your answer: {selected}")
                print("Try again, or click 'Show Solution' for explanation.")

    def on_show_solution(b):
        with output:
            output.clear_output()
            display(Markdown(f"**Correct Answer:** {correct_answer}"))
            display(Markdown(solution_text))

    submit_btn.on_click(on_submit)
    show_solution_btn.on_click(on_show_solution)

    # Layout
    button_box = widgets.HBox([submit_btn, show_solution_btn])
    display(widgets.VBox([radio, button_box, output]))
```

**Also add to tasks_data.py:**

```python
# Mark as multiple-choice type
solution_type["task04_checkpoint_5"] = "multiple_choice"
```

**Usage in Notebook 4 Section 7.5:**

```python
# In the notebook cell:
from shared_functions import check_multiple_choice
check_multiple_choice("task04_checkpoint_5")
```

---

#### Alternative: Text-Based Fallback (if widgets unavailable)

Modify the `check_task_with_solution()` to accept text answers:

```python
# If using text answer system:
"task04_checkpoint_5": r"""
## Conceptual Checkpoint 1 - River-Aquifer Interaction

Based on your simulated heads and water balance:
- **Is the Limmat River gaining or losing water from the aquifer?**
- **How can you tell from the simulation results?**

(Type a 1-2 sentence answer. Consider RIV budget flow and head comparisons.)
"""

# For text answers, check contains specific keywords:
solutions_keywords["task04_checkpoint_5"] = ["losing", "infiltrate", "RIV", "positive"]
solutions_markdown["task04_checkpoint_5"] = r"""
[Solution text from Option 1 above]
"""
```

---

## Additional Numerical Checkpoints (Optional)

If desired, add these additional numerical checkpoints to Sections 6-7:

### Checkpoint 1a: Total Active Cells (Section 6.1)

```python
"task04_checkpoint_1": r"""
## Numerical Checkpoint 1 - Model Discretization

After setting up your DISV grid:
- **How many active cells does your model have?**

(This depends on your specific grid generation. Typical range: 4500-5500 for ~50m cell size.)
"""

solutions["task04_checkpoint_1"] = (4500, 5500)
solutions_exact["task04_checkpoint_1"] = "~5000"  # Approximate
solution_unit["task04_checkpoint_1"] = "cells"

solutions_markdown["task04_checkpoint_1"] = r"""
## Grid Discretization Checkpoint

The number of active cells in a DISV grid depends on:
1. **Target cell size** (you specified 50m)
2. **Domain boundary shape** (irregular Limmat Valley polygon)
3. **Refinement zones** (if any local refinement applied)

**For a 50m Voronoi grid of the full Limmat Valley model domain:**
- Expected range: 4500–5500 cells
- Depends on exact boundary polygon and refinement strategy

**Why cell count matters:**
- More cells = finer discretization = more accurate but slower
- DISV grids adapt to irregular boundaries better than structured grids
- Trade-off between accuracy and computational cost

Check your grid by querying `modelgrid.ncpl` or counting cells in DISV package.
"""
```

### Checkpoint 2a: Average Aquifer Thickness (Section 6.2)

```python
"task04_checkpoint_2": r"""
## Numerical Checkpoint 2 - Aquifer Properties

Based on your model bottom and top assignments:
- **What is the average aquifer thickness (m)?**

(Hint: Calculate mean of (top - bottom) across all active cells)
"""

solutions["task04_checkpoint_2"] = (13, 22)  # Updated to match tasks_data.py
solutions_exact["task04_checkpoint_2"] = "~17.5"
solution_unit["task04_checkpoint_2"] = "m"

# Note: The range (13-22m) reflects actual Limmat Valley aquifer thickness from
# geological data, which is thicker than the simplified (5-8m) estimate initially proposed.

solutions_markdown["task04_checkpoint_2"] = r"""
## Aquifer Thickness Checkpoint

**Calculation:**
Average thickness = $\frac{1}{N}\sum_{i=1}^{N}(h_{top,i} - h_{bot,i})$

Where:
- $h_{top,i}$ = land surface elevation (from DEM) in cell $i$
- $h_{bot,i}$ = aquifer bottom elevation (from thickness raster) in cell $i$
- $N$ = number of active cells

**For the Limmat Valley model:**
- Thickness varies from ~5m (thin edges) to ~30m (thick center)
- Average: ~15–20m based on geological data
- GIS thickness map shows 2–40m range across the full valley

**Why simplified geometry?**
- High-resolution 3D representation is computationally expensive
- Single-layer model captures main flow patterns
- Local refinement around study areas done separately (case study notebooks)

**Check your result:**
If average thickness is outside 13–22m range, verify:
1. DEM clipping (should match model boundary)
2. Bottom surface (should be consistent with aquifer thickness map)
3. IDOMAIN (should match active cells only)
"""
```

### Checkpoint 3a: Total Recharge (Section 6.3)

```python
"task04_checkpoint_3": r"""
## Numerical Checkpoint 3 - Boundary Conditions

From your recharge boundary condition setup:
- **What is the total recharge flux (m³/day)?**

(Sum all recharge across all active cells receiving areal recharge)
"""

solutions["task04_checkpoint_3"] = (4500, 5500)  # Updated to match tasks_data.py
solutions_exact["task04_checkpoint_3"] = "Model-dependent"
solution_unit["task04_checkpoint_3"] = "m³/day"

solutions_markdown["task04_checkpoint_3"] = r"""
## Total Recharge Checkpoint

**Calculation:**
Total RCH = $\sum_{i} q_{rch,i} \times A_i$

Where:
- $q_{rch,i}$ = recharge rate (m/day) in cell $i$
- $A_i$ = cell area (m²)

**From Notebook 2 perceptual model:**
- Areal recharge ≈ 110 mm/year = 0.3 mm/day
- Model area ≈ 17 km² = 17×10⁶ m²
- Simple calculation: 0.3 × 10⁻³ × 17×10⁶ ≈ 5100 m³/day

**Note:** The actual model domain has inactive cells and partial recharge coverage, resulting in total recharge that may differ from the simple area calculation. The acceptable range (4500-5500 m³/day) is based on actual model outputs and accounts for variations in grid discretization and active cell coverage.

**In the numerical model:**
- Actual total depends on number of cells receiving recharge
- If not all cells receive recharge (model boundaries), total is lower
- Typical range: 4500–5500 m³/day for standard setup

**Check your calculation:**
```python
# In your code:
rch_rate = gwf.rch.recharge.get_data()  # m/day
cell_areas = modelgrid.get_cell_areas()  # m²
total_rch = np.sum(rch_rate * cell_areas)  # m³/day
```

**What if total is outside expected range?**
1. Verify recharge rate (should be ~0.3 mm/day = 0.0003 m/day)
2. Check cell area calculation
3. Confirm recharge package is active
4. Check IDOMAIN (inactive cells should have zero recharge)
"""
```

---

## Implementation Instructions

### Step 1: Add to questions_markdown dictionary

Copy the `r"""..."""` markdown blocks into the `questions_markdown` dictionary with task IDs as keys.

### Step 2: Add answer ranges to solutions dictionary

For numerical questions, define accepted ranges:
```python
solutions["task04_checkpoint_4"] = (0.0, 0.15)  # min, max
```

### Step 3: Add exact solutions

```python
solutions_exact["task04_checkpoint_4"] = "0.08"
```

### Step 4: Add units

```python
solution_unit["task04_checkpoint_4"] = "%"
```

### Step 5: Add solution explanations

Add markdown text to `solutions_markdown` dictionary explaining the concept and solution approach.

### Step 6: (Optional) Add computational functions

If certain checkpoints require computation from model output, add to `task_functions` dictionary:

```python
def compute_water_balance_error():
    """Extract water balance error from simulation results."""
    # This would be called when student clicks "Show Solution"
    # to display relevant calculations

task_functions["task04_checkpoint_4"] = compute_water_balance_error
```

---

## Integration with Notebook

In Notebook 4 Sections 6-8, invoke checkpoints with:

```python
from shared_functions import check_task_with_solution

# In Section 7.3
check_task_with_solution("task04_checkpoint_4")

# In Section 7.5
check_task_with_solution("task04_checkpoint_5")

# Optional: In earlier sections
check_task_with_solution("task04_checkpoint_1")  # After grid creation
check_task_with_solution("task04_checkpoint_2")  # After geometry assignment
check_task_with_solution("task04_checkpoint_3")  # After BC setup
```

---

## Answer Tolerance Notes

### Numerical Checkpoints

**Tolerance selection principle:** The range should be wide enough to accommodate:
1. Different grid discretizations (50m nominal, but actual varies)
2. Different parameter values (K uncertainty, recharge estimates)
3. Computational precision (floating-point rounding)

But narrow enough to:
1. Catch major errors (wrong units, missing cells)
2. Ensure students are checking their work, not guessing

**Example tolerance logic for checkpoint_4 (mass balance error):**
- MODFLOW 6 typically achieves < 0.01% error
- Tolerance of 0.0–0.15% allows for:
  - Perfect convergence (0.0%)
  - Minor precision loss from reading binary files (0.01–0.05%)
  - Slightly coarser grids or harder convergence (0.05–0.15%)

### Conceptual Checkpoints

For the river gaining/losing question, accept any answer that:
1. Correctly identifies gaining OR losing
2. Cites evidence from simulation results
3. References budget or head comparisons

Avoid strictly requiring a single "correct" answer since understanding can be demonstrated multiple ways.

---

## Expected Student Answers

### Checkpoint 4: Water Balance Error

**Typical student answer:** "0.08%"
- Shows proper calculation
- Within acceptable tolerance
- Demonstrates understanding of steady-state requirement

**Incorrect answers to watch for:**
- "8%" - forgot decimal point (off by 100×)
- "0.008%" - numerical precision confusion
- Negative values - should catch these as errors

### Checkpoint 5: River Gaining/Losing

**Strong answer:**
"Losing. The RIV budget shows positive flow, meaning water goes from river into aquifer. Also, the simulated head at river cells is lower than the specified river stage, so water flows downward through the riverbed."

**Acceptable variations:**
- Identifies either budget or head comparison method
- Explains physical mechanism (water flowing downward)
- References specific simulation results

**Weak answers to challenge:**
"Losing because that's what the problem said." → Ask: "How does the model output confirm this?"

---

## Related Files

- **Implementation location:** `/Users/bea/Documents/GitHub/applied_groundwater_modelling/_SUPPORT/src/scripts/scripts_exercises/tasks_data.py`
- **Function caller:** `/Users/bea/Documents/GitHub/applied_groundwater_modelling/_SUPPORT/src/scripts/scripts_exercises/shared_functions.py`
- **Notebook location:** `/Users/bea/Documents/GitHub/applied_groundwater_modelling/PROJECT/flow/4_model_implementation.ipynb` (Sections 6-8)

