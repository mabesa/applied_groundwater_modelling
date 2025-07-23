
import ipywidgets as widgets
from IPython.display import display, Markdown
import print_images as du
import numpy as np
import matplotlib.pyplot as plt



def dictionnary_matching(dictionnary, plot_func=None):
    equations = list(dictionnary.values())
    descriptions = list(dictionnary.keys())
    
    import random
    shuffled_desc = descriptions.copy()
    random.shuffle(shuffled_desc)
    
    dropdowns = []
    feedback_boxes = []
    options_with_select = ['--- select ---'] + shuffled_desc
    
    for eq in equations:
        dd = widgets.Dropdown(
            options=options_with_select,
            value='--- select ---',
            description='',
            layout=widgets.Layout(width='300px')
        )
        dropdowns.append(dd)
        feedback_boxes.append(widgets.HTML(value=""))
    
    output = widgets.Output()
    submit_btn = widgets.Button(description="Submit")
    
    def on_submit(b):
        output.clear_output()
        with output:
            correct = 0
            for i, eq in enumerate(equations):
                student_ans = dropdowns[i].value
                correct_ans = [desc for desc, v in dictionnary.items() if v == eq][0]
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
        if plot_func:
            plot_func()

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
    # Display the schema associated
    du.display_image(
        image_filename='SchemaBoundaries.png', 
        image_folder='3_exercises', 
        figure_size=(5, 3),  # Adjust the figure size as needed
    )
    dictionnary_matching(possibilities_BC)
    return

def sources_and_sinks_matching():
    possibilities_sources_and_sinks = {
        'Recharge rate' : "$W_{in} = N$",
        'Well input rate (negative if injection)' : '$W_w = -\\frac{Q_{well}}{\\Delta x \\Delta y}$',
        'River leakage rate if riverbed is above the water table' : "$W_r(x,y) = \\frac{K_{river}}{L_{river}}(h_{surf} - z_{riverbed}(x,y))$",
        'River leakage rate if riverbed is below the water table' : "$W_r(x,y) = \\frac{K_{river}}{L_{river}}(h_{surf} - h(x,y))$",
    }
    # Display the schema associated
    du.display_image(
        image_filename='SchemaSources.png', 
        image_folder='3_exercises', 
        figure_size=(5, 3),  # Adjust the figure size as needed
    )
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
        'Steady-state 1D flow, confined aquifer, no source/sink' : "$h(x) = h(x = 0) + \\frac{h(x = L) - h(x = 0)}{L} x$",
        'Steady-state 1D flow, unconfined aquifer, no source/sink (Dupuit solution)' : "$h(x)^2 = h(x=0)^2 - (h(x=0)^2 - h(x=L)^2)\\frac{x}{L} + \\frac{N}{K} \\cdot x (x-L)$ ",
        'Steady-state 1D flow, confined aquifer, with a well' : "$h(r)= h(r=0) - \\frac{Q_w}{2 \\pi T} \\ln (\\frac{r}{R(t)})$",
        'Steady-state 1D flow, unconfined aquifer, with a well' : "$h(r)^2 = h(r=0)^2 - \\frac{Q_w}{K \\pi} \\ln (\\frac{r}{R(t)})$",
    }
    dictionnary_matching(possibilities_solution, solution_transport_matching)
    return

def transport_matching():
    possibilities_solution = {
        'Advection term' : "$\\vec{j_1} = \\phi_e \\vec{u} c = \\vec{q} c$",
        'Molecular diffusion term' : "$\\vec{j_2} = - \\phi_e \\bold{D_{me}} \\vec{\\nabla}c$",
        'Dispersion term' : "$\\vec{j_3} = - \\phi_e \\bold{D} \\vec{\\nabla}c$",
    }
    dictionnary_matching(possibilities_solution)
    return

def transport_observation_matching():
    possibilities_solution = {
        'Advection term' : "Translation of the gaussian mean position with time",
        'Molecular diffusion term' : "Change in the Gaussian integral with time",
        'Dispersion term' : "Change in the Gaussian width with time",
    }
    dictionnary_matching(possibilities_solution)
    return

def solution_transport_matching(): 

    L = 20  
    x = np.linspace(0.01, L, 500) 
    h0 = 10  
    hL = 8  
    K = 0.78*1e-3  
    N = -1e-5*5 
    Qw = 0.1  
    T = 1e-2  
    Rt = 20  
    r = np.linspace(0.01, Rt, 5000)  

    # 1. 
    h1 = h0 + (hL - h0) * x / L
    # 2. 
    h2 = np.sqrt(h0**2 - ((h0**2 - hL**2) * x / L) + (N / K) * x * (x - L))
    # 3.
    h3 = 8 - (Qw / (2 * np.pi * T)) * np.log(r / Rt)
    # 4.
    h4 = np.sqrt(8**2 - (Qw / (K * np.pi)) * np.log(r / Rt))

    fig, axs = plt.subplots(2, 2, figsize=(12, 7))
    axs = axs.flatten()

    # --- Graph 1: ---
    axs[0].plot(x, h1, label='h(x)')
    axs[0].axvline(L, color='gray', linestyle='--', label='x = L')
    axs[0].axhline(hL, color='gray', linestyle='--', label='h = h(L)')
    axs[0].axvline(0, color='gray', linestyle=':', label='x = 0')
    axs[0].axhline(h0, color='gray', linestyle=':', label='h = h(0)')
    axs[0].set_title('Steady-state 1D flow, confined aquifer, no source/sink')
    axs[0].set_xlabel('x (m)')
    axs[0].set_ylabel('h (m)')
    axs[0].legend(loc='upper right')

    # --- Graph 2:---
    axs[1].plot(x, h2, label='h(x)')
    axs[1].axvline(L, color='gray', linestyle='--', label='x = L')
    axs[1].axhline(hL, color='gray', linestyle='--', label='h = h(L)')
    axs[1].axvline(0, color='gray', linestyle=':', label='x = 0')
    axs[1].axhline(h0, color='gray', linestyle=':', label='h = h(0)')
    axs[1].set_title('Steady-state 1D flow, unconfined aquifer, no source/sink (Dupuit solution)')
    axs[1].set_xlabel('x (m)')
    axs[1].set_ylabel('h (m)')
    axs[1].legend(loc='upper right')

    # --- Graph 3:  ---
    axs[2].plot(r, h3, label='h(r)')
    axs[2].axvline(Rt, color='gray', linestyle='--', label='r = R(t)')
    axs[2].axhline(h3[-1], color='gray', linestyle='--', label='h = h(R(t))')
    axs[2].axvline(0, color='gray', linestyle=':', label='x = $r_{well}$')
    axs[2].axhline(20, color='gray', linestyle=':', label='h = $h_{well}$')
    axs[2].set_title('Steady-state 1D flow, confined aquifer, with a well')
    axs[2].set_xlabel('r (m)')
    axs[2].set_ylabel('h (m)')
    axs[2].legend(loc='upper right')

    # --- Graph 4: ---
    axs[3].plot(r, h4, label='h(r)')
    axs[3].axvline(Rt, color='gray', linestyle='--', label='r = R(t)')
    axs[3].axhline(h4[-1], color='gray', linestyle='--', label='h = h(R(t))')
    axs[3].axvline(0, color='gray', linestyle=':', label='x = $r_{well}$')
    axs[3].axhline(20, color='gray', linestyle=':', label='h = $h_{well}$')
    axs[3].set_title('Steady-state 1D flow, unconfined aquifer, with a well')
    axs[3].set_xlabel('r (m)')
    axs[3].set_ylabel('h (m)')
    axs[3].legend(loc='upper right')

    plt.tight_layout()
    plt.show()
    return