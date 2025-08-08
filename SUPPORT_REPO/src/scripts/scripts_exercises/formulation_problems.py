
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
    dictionnary_matching(possibilities_solution, solution_flow_matching)
    return


def solution_flow_matching(): 

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
    axs[0].axvline(L, color='blue', linestyle='--', label='x = L')
    axs[0].axhline(hL, color='green', linestyle='--', label='h = h(L)')
    axs[0].axvline(0, color='red', linestyle=':', label='x = 0')
    axs[0].axhline(h0, color='orange', linestyle=':', label='h = h(0)')
    axs[0].set_title('Steady-state 1D flow, confined aquifer, no source/sink')
    axs[0].set_xlabel('x (m)')
    axs[0].set_ylabel('h (m)')
    axs[0].legend(loc='upper right')
    axs[0].grid(True)

    # --- Graph 2:---
    axs[1].plot(x, h2, label='h(x)')
    axs[1].axvline(L, color='blue', linestyle='--', label='x = L')
    axs[1].axhline(hL, color='green', linestyle='--', label='h = h(L)')
    axs[1].axvline(0, color='red', linestyle=':', label='x = 0')
    axs[1].axhline(h0, color='orange', linestyle=':', label='h = h(0)')
    axs[1].set_title('Steady-state 1D flow, unconfined aquifer, no source/sink (Dupuit solution)')
    axs[1].set_xlabel('x (m)')
    axs[1].set_ylabel('h (m)')
    axs[1].legend(loc='upper right')
    axs[1]. grid(True)

    # --- Graph 3:  ---
    axs[2].plot(r, h3, label='h(r)')
    axs[2].axvline(Rt, color='blue', linestyle='--', label='r = R(t)')
    axs[2].axhline(h3[-1], color='green', linestyle='--', label='h = h(R(t))')
    axs[2].axvline(0, color='red', linestyle=':', label='x = $r_{well}$')
    axs[2].axhline(20, color='orange', linestyle=':', label='h = $h_{well}$')
    axs[2].set_title('Steady-state 1D flow, confined aquifer, with a well')
    axs[2].set_xlabel('r (m)')
    axs[2].set_ylabel('h (m)')
    axs[2].legend(loc='upper right')
    axs[2].grid(True)

    # --- Graph 4: ---
    axs[3].plot(r, h4, label='h(r)')
    axs[3].axvline(Rt, color='blue', linestyle='--', label='r = R(t)')
    axs[3].axhline(h4[-1], color='green', linestyle='--', label='h = h(R(t))')
    axs[3].axvline(0, color='red', linestyle=':', label='x = $r_{well}$')
    axs[3].axhline(20, color='orange', linestyle=':', label='h = $h_{well}$')
    axs[3].set_title('Steady-state 1D flow, unconfined aquifer, with a well')
    axs[3].set_xlabel('r (m)')
    axs[3].set_ylabel('h (m)')
    axs[3].legend(loc='upper right')
    axs[3].grid(True)

    plt.tight_layout()
    plt.show()
    return

def transport_matching():
    possibilities_solution = {
        'Advection term' : "$\\vec{j_1} = \\phi_e \\vec{u} c = \\vec{q} c$",
        'Molecular diffusion term' : "$\\vec{j_2} = - \\phi_e \\bold{D_{me}} \\vec{\\nabla}c$, where $\\bold{D_{me}}$ is about $10^{-9} m^2/s^{-1}$",
        'Dispersion term' : "$\\vec{j_3} = - \\phi_e \\bold{D} \\vec{\\nabla}c$, where $\\bold{D}$ is a tensor : $D_{ij}=\\frac{1}{\\mid u \\mid} u_i u_j (\\alpha_l-\\alpha_t)$",
    }
    dictionnary_matching(possibilities_solution)
    return

def transport_observation_matching():
    possibilities_solution = {
        'Advection term' : "Translation of the peak location in time",
        'Diffusion and dispersion term' : "Change in the peak width with time",
        }
    dictionnary_matching(possibilities_solution)
    return

def transport_gaussian_plot():


    def c_x_t_curve(v=1.0, D=0.05, alpha=1.0, t=1.0, M=1.0, phi_0=0.3, R=1.0, x_range=(0, 100), n_points=200):
        """
        Returns x, c(x,t) arrays for given parameters for an instantaneous source solution.
        """
        x = np.linspace(*x_range, n_points)
        D_L = D + alpha * v  # Effective dispersion

        if t == 0:
            c = np.zeros_like(x)
            idx = np.argmin(np.abs(x))  # Approximate delta function at x=0
            c[idx] = M / (R * phi_0)  
            return x, c

        factor1 = M / (R * phi_0 * np.sqrt(4 * np.pi * D_L * t / R))
        exponent = -((x - v * t / R) ** 2) / (4 * D_L * t / R)
        c = factor1 * np.exp(exponent)
        return x, c

    # Fixed y max value using t=0.01 to avoid delta peak
    x_fixed, c_fixed = c_x_t_curve(t=0.5)
    c_fixed_max = np.max(c_fixed)


    def plot_cx_t_interactive(v, D, alpha, t):
        x, c = c_x_t_curve(v, D, alpha, t)

        # Normalize c(x,t) to use as PDF
        dx = x[1] - x[0]
        c_pdf = c / (np.sum(c) * dx)

        # Compute cumulative distribution
        c_cdf = np.cumsum(c_pdf) * dx

        # Interpolate to get mean and quantiles
        mean_x = np.sum(x * c_pdf * dx)
        q1_x = np.interp(0.25, c_cdf, x)
        q3_x = np.interp(0.75, c_cdf, x)


        c_mean = np.interp(mean_x, x, c)
        c_q1 = np.interp(q1_x, x, c)
        c_q3 = np.interp(q3_x, x, c)

        # Observation wells
        obs_x = [5, 10, 15, 20]
        obs_c = np.interp(obs_x, x, c)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(x, c, label=r'$c(x, t)$', color='blue')
        ax.scatter(obs_x, obs_c, color='red', zorder=5, label='Observation wells')

        # Vertical lines to curve (not full height)
        ax.vlines(mean_x, 0, c_mean, color='green', linestyle='--', linewidth=2, label='Mean')
        ax.vlines(q1_x, 0, c_q1, color='green', linestyle=':', linewidth=2, label='1st Quartile')
        ax.vlines(q3_x, 0, c_q3, color='green', linestyle=':', linewidth=2, label='3rd Quartile')

        # Mean line from x-axis up to curve
        c_mean = np.interp(mean_x, x, c)
        ax.vlines(mean_x, 0, c_mean, color='green', linestyle='--', linewidth=2)

        ax.set_xlabel('$x$ [m]')
        ax.set_ylabel('$c(x,t)$ [mass / volume]')
        ax.set_title('Instantaneous Source Transport: $c(x,t)$')
        ax.set_xlim(0, 30)
        ax.set_ylim(0, 1 * c_fixed_max)
        ax.legend(loc='upper right')
        ax.grid(True)
        plt.show()

    def interactive_cx_t():
        v_slider = widgets.FloatSlider(value=1.0, min=0.1, max=3, step=0.2,
                                    description='Seepage velocity u [m/d]', layout=widgets.Layout(width='400px'), style={'description_width': '200px'})
        D_slider = widgets.FloatSlider(value=0.1, min=0.001, max=1.0, step=0.1,
                                    description='Diffusion coefficient D [m²/d]', layout=widgets.Layout(width='400px'), style={'description_width': '200px'})
        alpha_slider = widgets.FloatSlider(value=0.5, min=0.1, max=3, step=0.2,
                                        description='Dispersivity α [m]', layout=widgets.Layout(width='400px'), style={'description_width': '200px'})
        t_slider = widgets.FloatSlider(value=0.1, min=0, max=50.0, step=0.2,
                                    description='Time t [d]', layout=widgets.Layout(width='400px'))
        ui = widgets.VBox([v_slider, D_slider, alpha_slider, t_slider])
        out = widgets.interactive_output(plot_cx_t_interactive, {
            'v': v_slider, 'D': D_slider, 'alpha': alpha_slider, 't': t_slider
        })
        display(ui, out)

    interactive_cx_t()
    return
