import ipywidgets as widgets
from IPython.display import display, Markdown

# ==========================================
# 1. CONFIGURATION (EDIT THIS SECTION)
# ==========================================

CASE_TITLE = ""

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
    "Surface Water Infiltration to the Aquifer (precipitation not included here)",
    "Surface Water Discharge from the Aquifer",
    "Groundwater Inflow from lower aquifer",
    "Groundwater Outflow to lower aquifer",
]

# THE SOLUTION: List exactly which flows should be set to ZERO.
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
SOLUTION_TEXT = """In this specific catchment, the only flows that are to be considered are:
1. Precipitation Infiltration: recharge
2. Surface Water Discharge: the river gains water from the aquifer at the outflow of the system.
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
    
    # Table Header Row
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

    # Placeholder for feedback/solution text inside the table
    feedback_widget = widgets.HTML("")
    feedback_row = widgets.Box([feedback_widget], layout=widgets.Layout(padding='10px', border_top='1px solid #ddd', background_color='#fafafa'))
    rows.append(feedback_row)

    table_box = widgets.VBox(rows, layout=widgets.Layout(border='1px solid #ddd', margin='10px 0'))

    # Buttons (No button_style argument)
    btn_check = widgets.Button(description="Submit Answer")
    btn_reset = widgets.Button(description="Reset")
    
    # Solution button starts hidden
    btn_solution = widgets.Button(description="Show Solution")
    btn_solution.layout.display = 'none' 

    def on_check(b):
        student_zeros = {flow for flow, cb in checkboxes.items() if cb.value}
        correct_zeros = set(FLOWS_THAT_ARE_ZERO)

        missed = correct_zeros - student_zeros
        false_pos = student_zeros - correct_zeros

        html_content = ""
        if not missed and not false_pos:
            html_content = "<span style='color: green; font-weight: bold;'>Correct! You perfectly identified the zero-flows.</span>"
        else:
            html_content = "<span style='color: #d9534f; font-weight: bold;'>Some elements are not correct:</span><ul style='margin-top:5px;'>"
            if missed:
                html_content += f"<li style='color: #d9534f;'><b>Missed (Should be zero):</b> {', '.join(missed)}</li>"
            if false_pos:
                html_content += f"<li style='color: #d9534f;'><b>Incorrect (Should NOT be zero):</b> {', '.join(false_pos)}</li>"
            html_content += "</ul>"
        
        # Update the feedback widget inside the table
        feedback_widget.value = html_content
        
        # Reveal the solution button
        btn_solution.layout.display = 'flex'

    def on_reset(b):
        # Clear feedback
        feedback_widget.value = ""
        # Uncheck all
        for cb in checkboxes.values():
            cb.value = False
        # Hide solution button
        btn_solution.layout.display = 'none'

    def on_show_solution(b):
        formatted_solution = SOLUTION_TEXT.replace('\n', '<br>').replace('**', '<b>').replace('**', '</b>')
        feedback_widget.value = f"<div style='background-color: #e9f5ff; padding: 10px; border-left: 4px solid #007bff; margin-top: 10px;'><b>💡 Solution:</b><br><br>{formatted_solution}</div>"

    btn_check.on_click(on_check)
    btn_reset.on_click(on_reset)
    btn_solution.on_click(on_show_solution)

    # Layout for buttons
    button_box = widgets.HBox([btn_check, btn_reset, btn_solution], layout=widgets.Layout(margin='10px 0'))

    # Display everything
    display(header, table_box, button_box)

