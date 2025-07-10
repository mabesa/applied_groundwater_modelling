
import ipywidgets as widgets
from IPython.display import display, Markdown




def dictionnary_matching(dictionnary):
    equations = list(dictionnary.values())
    descriptions = list(dictionnary.keys())
    
    import random
    shuffled_desc = descriptions.copy()
    random.shuffle(shuffled_desc)
    
    dropdowns = []
    feedback_boxes = []
    # Add "--- select ---" as the first option
    options_with_select = ['--- select ---'] + shuffled_desc
    for eq in equations:
        dd = widgets.Dropdown(
            options=options_with_select,
            value='--- select ---',
            description='',
            layout=widgets.Layout(width='300px')
        )
        dropdowns.append(dd)
        feedback_boxes.append(widgets.HTML(value=""))  # For feedback below each dropdown
    
    output = widgets.Output()
    submit_btn = widgets.Button(description="Submit")
    
    def on_submit(b):
        output.clear_output()
        with output:
            correct = 0
            for i, eq in enumerate(equations):
                student_ans = dropdowns[i].value
                correct_ans = [desc for desc, v in dictionnary.items() if v == eq][0]
                # Reset style
                dropdowns[i].style = {}
                if student_ans == correct_ans:
                    dropdowns[i].style = {'description_width': 'initial', 'background': 'lightgreen'}
                    feedback_boxes[i].value = f"<span style='color:green; font-weight:bold;'>Correct!</span>"
                    correct += 1
                elif student_ans == '--- select ---':
                    dropdowns[i].style = {'description_width': 'initial', 'background': 'lightyellow'}
                    feedback_boxes[i].value = f"<span style='color:orange; font-weight:bold;'>Please select an answer.</span>"
                else:
                    dropdowns[i].style = {'description_width': 'initial', 'background': 'salmon'}
                    feedback_boxes[i].value = (
                        f"<span style='color:red; font-weight:bold;'>Incorrect.</span> "
                        f"<span style='color:black;'>Correct answer: <b>{correct_ans}</b></span>"
                    )
    
    submit_btn.on_click(on_submit)
    
    for i, dd in enumerate(dropdowns):
        display(Markdown(f"{equations[i]}"))
        display(dd)
        display(feedback_boxes[i])
    display(submit_btn, output)

# Usage:
def boundary_condition_matching():
    possibilities_BC = {
        'Prescribed head profile along a boudary' : "$h(x,y,t)=h_0(x,y,t)$",
        'Specified discharge perpendicular to a boundary' : "$Q_n = - T \\frac{\\partial h}{\\partial n} = f(x,y,t)$",
        'Specified vertical recharge flux for 3D models' : "$Q_z = N_z \\Delta x \\Delta y$",
        'Impervious boudary' : "$Q_n = - T \\frac{\\partial h}{\\partial n} = 0$",
        'Constant head along a boundary, eg river' : "$h(x,y,t)=z_{r}$",
    }
    dictionnary_matching(possibilities_BC)
    return

def sources_and_sinks_matching():
    possibilities_sources_and_sinks = {
        'Recharge rate' : "$W_{in} = N$",
        'Lateral inflow rate' : '$W_l = q_l$',
        'Well input rate (negative if injection)' : '$W_w = -\\frac{Q_{well}}{\\Delta x \\Delta y}$',
        'River leakage rate if riverbed is above the water table' : "$W_r(x,y) = \\frac{K_{river}}{L_{river}}(h_{surf} - z_{riverbed}(x,y))$",
        'River leakage rate if riverbed is below the water table' : "$W_r(x,y) = \\frac{K_{river}}{L_{river}}(h_{surf} - h(x,y))$",
    }

    dictionnary_matching(possibilities_sources_and_sinks)
    return

def flow_equation_matching():
    possibilities_equation = {
        'Steady-state 1D flow, no source/sink' : "$\\frac{\\partial ^2 h(x)}{\\partial x ^2} = 0$",
        'Steady-state 1D flow, with a well' : "$r \\frac{\\partial h(r)}{\\partial r} = - \\frac{Q_{well}}{2 \\pi T}$",
    }
    dictionnary_matching(possibilities_equation)
    return

def flow_analytical_solutions_matching():
    possibilities_solution = {
        'Steady-state 1D flow, confined aquifer, no source/sink' : "$h(x) = h_0 + \\frac{h_2 - h_1}{L} x$",
        'Steady-state 1D flow, unconfined aquifer, no source/sink (Dupuit solution)' : "$h(x)^2 = h(x=0)^2 - (h(x=0)^2 - h(x=L)^2)\\frac{x}{L} + \\frac{N}{K} \\cdot x (x-L)$ ",
        'Steady-state 1D flow, confined aquifer, with a well' : "$h(r)= h(r=0) - \\frac{Q_w}{2 \\pi T} \\ln (\\frac{r}{R(t)})$",
        'Steady-state 1D flow, unconfined aquifer, with a well' : "$h(r)^2 = h(r=0)^2 - \\frac{Q_w}{K \\pi} \\ln (\\frac{r}{R(t)})$",
    }
    dictionnary_matching(possibilities_solution)
    return

