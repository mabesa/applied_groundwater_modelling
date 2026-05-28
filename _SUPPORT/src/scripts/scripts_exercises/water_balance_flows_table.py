
import ipywidgets as widgets
from IPython.display import display, clear_output

# ==========================================
# 1. CONFIGURATION (EDIT THIS SECTION)
# ==========================================

CASE_TITLE = "Task 1: identify flow components"

CASE_DESCRIPTION = """
Identify flow components who can be set to zero for the water balance.
"""

# List of all possible flows
FLOW_OPTIONS = [
    "Precipitation Infiltration",
    "Evapotranspiration",
    "Lateral Groundwater Inflow",
    "Lateral Groundwater Outflow",
    "Artificial inflow (e.g. injection well)",
    "Artificial outflow (e.g. pumping well)",
    "Surface Water Infiltration to the Aquifer",
    "Surface Water Discharge from the Aquifer",
    "Groundwater Inflow from lower aquifer",
    "Groundwater Outflow to lower aquifer",
]

# THE SOLUTION: List exactly which flows should be set to ZERO.
# Copy strings exactly from FLOW_OPTIONS.
FLOWS_THAT_ARE_ZERO = [
    #"Precipitation Infiltration",
    "Evapotranspiration",
    "Lateral Groundwater Inflow",
    "Lateral Groundwater Outflow",
    "Artificial inflow (e.g. injection well)",
    "Artificial outflow (e.g. pumping well)",
    "Surface Water Infiltration to the Aquifer",
    #"Surface Water Discharge from the Aquifer",
    "Groundwater Inflow from lower aquifer",
    "Groundwater Outflow to lower aquifer",
]

# TEXT TO DISPLAY WHEN "SHOW SOLUTION" IS CLICKED
# You can edit this text freely. Use \n for new lines.
SOLUTION_TEXT = """
Here is the correct conceptual model for this case study:

In this specific catchment, the only active flows are:
1. Precipitation Infiltration (Recharge)
2. Surface Water Discharge (The river gains water from the aquifer)

All other flows (ET, Lateral flows, Artificial flows, Deep leakage) are considered negligible or non-existent due to the geological boundaries and lack of human activity.
"""

# ==========================================
# 2. INTERACTIVE LOGIC
# ==========================================

def run_quiz_water_balance():
    # Create Header
    header = widgets.HTML(f"<h2>{CASE_TITLE}</h2><p>{CASE_DESCRIPTION.replace(chr(10), '<br>')}</p>")
    
    # Create Checkboxes
    checkboxes = {}
    rows = []
    
    # Table Header Row (Visual only)
    header_row = widgets.Box([
        widgets.HTML("<b>Inflow or Outflow flux</b>", layout=widgets.Layout(flex='2')),
        widgets.HTML("<b>Tick if the flux should be considered zero</b>", layout=widgets.Layout(flex='1', textAlign='center'))
    ], layout=widgets.Layout(border_bottom='1px solid black', padding='5px'))
    rows.append(header_row)

    for flow in FLOW_OPTIONS:
        cb = widgets.Checkbox(value=False, indent=False)
        checkboxes[flow] = cb
        row = widgets.Box([
            widgets.HTML(flow, layout=widgets.Layout(flex='2')),
            cb
        ], layout=widgets.Layout(padding='5px', align_items='center'))
        rows.append(row)

    table_box = widgets.VBox(rows, layout=widgets.Layout(border='1px solid #ddd', margin='10px 0'))

    # Buttons
    btn_check = widgets.Button(description="Submit Answer", button_style='primary')
    btn_reset = widgets.Button(description="Reset", button_style='warning')
    btn_solution = widgets.Button(description="Show Solution", button_style='info', layout=widgets.Layout(display='none')) # Hidden initially
    
    output = widgets.Output()
    solution_output = widgets.Output()

    def on_check(b):
        with output:
            clear_output()
        with solution_output:
            clear_output()
            
        student_zeros = {flow for flow, cb in checkboxes.items() if cb.value}
        correct_zeros = set(FLOWS_THAT_ARE_ZERO)

        missed = correct_zeros - student_zeros
        false_pos = student_zeros - correct_zeros

        if not missed and not false_pos:
            print("✅ CORRECT! You perfectly identified the zero-flows.")
        else:
            print("❌ Not quite right. Review the following:")
            if missed:
                print(f"\n• Missed (Should be zero): {', '.join(missed)}")
            if false_pos:
                print(f"\n• Incorrect (Should NOT be zero): {', '.join(false_pos)}")
        
        # Reveal the solution button after submission
        btn_solution.layout.display = 'flex'

    def on_reset(b):
        with output:
            clear_output()
        with solution_output:
            clear_output()
        for cb in checkboxes.values():
            cb.value = False
        # Hide solution button again on reset
        btn_solution.layout.display = 'none'

    def on_show_solution(b):
        with solution_output:
            clear_output()
            # Format the text nicely with line breaks
            formatted_text = SOLUTION_TEXT.replace('\n', '<br>')
            display(widgets.HTML(f"<div style='background-color: #f0f0f0; padding: 15px; border-left: 5px solid #007bff;'><b>Solution:</b><br>{formatted_text}</div>"))

    btn_check.on_click(on_check)
    btn_reset.on_click(on_reset)
    btn_solution.on_click(on_show_solution)

    # Display everything
    display(header, table_box, widgets.HBox([btn_check, btn_reset, btn_solution]), output, solution_output)

# Run the quiz
run_quiz_water_balance()