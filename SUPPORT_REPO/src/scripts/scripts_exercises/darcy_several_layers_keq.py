import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import ipywidgets as widgets
from IPython.display import display, Markdown, clear_output, HTML

def draw_schematic(ax, label, configuration):

    """
    Draws the schematic of the confined aquifer on the given axis based on the configuration.
    """
    L = 50  # Total length of the aquifer (m)
    h0 = 50  # Hydraulic head at x = 0 (m)
    h2L = 45  # Hydraulic head at x = 2L (m)
    type_formula = "vertical"  # Default type_formula
    ax.set_anchor('C')

    # Draw the layers based on the configuration
    if configuration == 1:  # Single layer of K1
        type_formula = "horizontal"
        ax.add_patch(patches.Rectangle((0, 0), 2*L, 2, edgecolor="black", facecolor="blue", alpha=0.3, label="Layer K1"))
        ax.add_patch(patches.Rectangle((0, 2), 2*L, 2, edgecolor="black", facecolor="green", alpha=0.3, label="Layer K2"))
        ax.add_patch(patches.Rectangle((0, 4), 2*L, 2, edgecolor="black", facecolor="orange", alpha=0.3, label="Layer K3"))
        ax.text(L, 1, "K1", color="black", fontsize=14, ha="center", va="center")
        ax.text(L, 3, "K2", color="black", fontsize=14, ha="center", va="center")
        ax.text(L, 5, "K3", color="black", fontsize=14, ha="center", va="center")

    elif configuration == 2:  # Vertically 2 layers: 2/3 K1, 1/3 K2
        type_formula = "horizontal"
        ax.add_patch(patches.Rectangle((0, 0), 2*L, 4, edgecolor="black", facecolor="blue", alpha=0.3, label="Layer K1"))
        ax.add_patch(patches.Rectangle((0, 4), 2*L, 2, edgecolor="black", facecolor="green", alpha=0.3, label="Layer K2"))
        ax.text(L, 1, "K1", color="black", fontsize=14, ha="center", va="center")
        ax.text(L, 5, "K2", color="black", fontsize=14, ha="center", va="center")

    elif configuration == 3:  # Vertically 2 layers: 1/3 K1, 2/3 K2
        type_formula = "horizontal"
        ax.add_patch(patches.Rectangle((0, 0), 2*L, 2, edgecolor="black", facecolor="blue", alpha=0.3, label="Layer K1"))
        ax.add_patch(patches.Rectangle((0, 2), 2*L, 4, edgecolor="black", facecolor="green", alpha=0.3, label="Layer K2"))
        ax.text(L, 1, "K1", color="black", fontsize=14, ha="center", va="center")
        ax.text(L, 5, "K2", color="black", fontsize=14, ha="center", va="center")

    elif configuration == 4:  # Vertically 3 layers: 1/3 K1, 1/3 K2, 1/3 K3
        type_formula = "vertical"
        ax.add_patch(patches.Rectangle((0, 0), 2*L, 6, edgecolor="black", facecolor="blue", alpha=0.3, label="Layer K1"))
        ax.text(L, 3, "K1", color="black", fontsize=14, ha="center", va="center")
        
    elif configuration == 5:  # Horizontally 1/2 K1 and 1/2 K2
        type_formula = "vertical"
        ax.add_patch(patches.Rectangle((0, 0), 2*L / 2, 6, edgecolor="black", facecolor="blue", alpha=0.3, label="Layer K1"))
        ax.add_patch(patches.Rectangle((2*L / 2, 0), 2*L / 2, 6, edgecolor="black", facecolor="green", alpha=0.3, label="Layer K2"))
        ax.text(L/2, 3, "K1", color="black", fontsize=14, ha="center", va="center")
        ax.text(3*L/2, 3, "K2", color="black", fontsize=14, ha="center", va="center")

    elif configuration == 6:  # Horizontally 1/2 K1 and 1/2 K4
        type_formula = "vertical"
        ax.add_patch(patches.Rectangle((0, 0), 2*L / 2, 6, edgecolor="black", facecolor="blue", alpha=0.3, label="Layer K1"))
        ax.add_patch(patches.Rectangle((2*L / 2, 0), 2*L / 2, 6, edgecolor="black", facecolor="purple", alpha=0.3, label="Layer K4"))
        ax.text(L/2, 3, "K1", color="black", fontsize=14, ha="center", va="center")
        ax.text(3*L/2, 3, "K0", color="black", fontsize=14, ha="center", va="center")

    # Draw the wells as piezometers (tubes)
    # Well at x=0
    ax.add_patch(patches.Rectangle((0,0), 5, 8, edgecolor="black", facecolor="white", label="Well at x=0"))
    ax.hlines(7.9, 0, 5, colors="blue", linewidth=2)  # Water table level inside the well

    # Well at x=2L
    ax.add_patch(patches.Rectangle((2 * L - 5, 0), 5, 8, edgecolor="black", facecolor="white", label="Well at x=2L"))
    ax.hlines(6.5, 2 * L - 5, 2 * L, colors="blue", linewidth=2)  # Water table level inside the well

    # Add labels for the wells
    #ax.text(0, 7.5, f"h(0) = {h0} m", fontsize=12, ha="center")
    #ax.text(2 * L, 7.5, f"h(2L) = {h2L} m", fontsize=12, ha="center")

    # Add the x-axis at the bottom
    ax.hlines(0, 0, 2 * L, colors="black", linewidth=5)  # Horizontal line for the x-axis
    # ax.text(0, 3.2, "$x$ = 0", fontsize=12, ha="center")  # Label for x=0
    # ax.text(2 * L, 3.2, "$x$ = 2L", fontsize=12, ha="center")  # Label for x=2L

    # Add ticks on the x-axis
    #ax.vlines(0, 3.4, 3.6, colors="black", linewidth=1)  # Tick at x=0
    #ax.vlines(L, 3.4, 3.6, colors="black", linewidth=1)  # Tick at x=L
    #ax.vlines(2 * L, 3.4, 3.6, colors="black", linewidth=1)  # Tick at x=2L

    # Add subplot label
    ax.text(-10, 9, f"({label})", fontsize=14, fontweight="bold", ha="left")

    ax.set_xlim(-5, 2 * L + 5)
    ax.set_ylim(0, 10)
    ax.axis("off")

def K_eq(type_layers, K1, K2, K3, L1, L2, L3,L=None):
    if type_layers == "vertical":
        # Vertical layers
        L = L1 + L2
        K_eq = L / ((L1 / K1) + (L2 / K2))
    elif type_layers == "horizontal":
        # Horizontal layers
        K_eq = (K1 * L1 + K2 * L2 + K3 * L3) / (L1 + L2 + L3)
    else:
        raise ValueError("Invalid type of layers. Use 'vertical' or 'horizontal'.")
    return K_eq


def h_function_plot(type_layers, K1, K2, K3, L1, L2, L3, L=None, h0=50, q=3e-7, add_correction=True):
    """
    Generates the hydraulic head h(x) based on the type of layering (vertical or horizontal).
    """
      # x values for the entire domain
    A= 1  # Cross-sectional area (m^2)

    if type_layers == "horizontal":
        if K3 is None:
            raise ValueError("K3 must be provided for vertical layers.")

        x_bef = np.linspace(-50, 0, 100)
        x_aft = np.linspace(L, L+50, 100)
        x = np.linspace(0, L, 500)
        
        h = h0 - (q/(K_eq(type_layers, K1, K2, K3, L1, L2, L3)*A)*x)
        h_bef = h0*np.ones_like(x_bef)
        h_aft = h[-1]*np.ones_like(x_aft)

        h = np.concatenate([h_bef, h, h_aft])
        x = np.concatenate([x_bef, x, x_aft])

        if add_correction:
            correction_K_equiv.append(K_eq(type_layers, K1, K2, K3, L1, L2, L3)*1e6)  # Convert to um/s

        return x, h

    elif type_layers == "vertical":
        L=L1+L2+L3

        x_bef = np.linspace(-50, 0, 100)
        x_aft = np.linspace(L, L+50, 100)
        x = np.linspace(0, L, 500)
        x1 = x[x <= L1]
        x2 = x[x > L1]

        h1 = h0 - (q / (K1*A)) * (x1)
        h2 = h1[-1] - (q / (K2*A)) * (x2 - L1)
        h_bef = h0*np.ones_like(x_bef)
        h_aft = h2[-1]*np.ones_like(x_aft)

        h = np.concatenate([h_bef, h1, h2, h_aft])
        x = np.concatenate([x_bef, x1, x2, x_aft])

        if add_correction:
            correction_K_equiv.append( (K_eq(type_layers, K1, K2, K3, L1, L2, L3))*1e6) # Convert to um/s

        return x, h

    else:
        raise ValueError("Invalid type_layers. Use 'vertical' or 'horizontal'.")




def exercise_aquifers_layered_keq_attribution():

    # Gestion of the correction of submission for the results table
    def on_submit(b):
        global correction_K_equiv
        nb_correct_cells=0
        with output:
            #clear_output(wait=True)
            

            # Get user inputs
            user_K_eq = [float(widget.value) if widget.value else None for widget in k_eq_inputs]
            user_profiles = [int(widget.value) if widget.value else None for widget in profile_inputs]

            # Create styled K_eq values
            styled_K_eq = []
            for i, (user_val, correct_val) in enumerate(zip(user_K_eq, correction_K_equiv)):
                if user_val is not None and np.isclose(user_val, correct_val, rtol=0.5):  # Adjust rtol as needed
                    nb_correct_cells += 1
                    styled_K_eq.append(f"<td style='background-color: green;'>{round(correct_val)}</td>")
                else:
                    styled_K_eq.append(f"<td style='background-color: red;'>{round(correct_val)}</td>")

    

            # Create styled profile values
            styled_profiles = []
            for i, (user_val, correct_val) in enumerate(zip(user_profiles, correction_profile_to_schematic)):
                if user_val is not None and user_val == correct_val:
                    nb_correct_cells += 1
                    styled_profiles.append(f"<td style='background-color: green;'>{round(correct_val)}</td>")
                else:
                    styled_profiles.append(f"<td style='background-color: red;'>{round(correct_val)}</td>")
            display(Markdown(fr""" 
## <br>Solution : <br>

**<br>Number of correct cells: {nb_correct_cells}/12**

Equivalent hydraulic conductivities are obtained from formulas (see lecture).<br>
Profiles can be qualitatively attributed given that K0<K1<K2<K3.<br>
Correct submissions are in green and incorrect ones in red :<br><br>
            """))

            # Create the corrected table with styled values
            corrected_table = "<table>\n"
            corrected_table += "  <tr><th>Schematic</th><th>(a)</th><th>(b)</th><th>(c)</th><th>(d)</th><th>(e)</th><th>(f)</th></tr>\n"
            corrected_table += "  <tr><th>Keq</th>" + "".join(styled_K_eq) + "</tr>\n"
            corrected_table += "  <tr><th>Profile</th>" + "".join(styled_profiles) + "</tr>\n"
            corrected_table += "</table>"

            display(Markdown(corrected_table))
            submit_button.disabled = True


            ## Generate and plot the h(x) profiles for the exercise -------------------------------
            fig, axes = plt.subplots(2, 3, figsize=(11/n, 7/n),layout="constrained")

            correction_K_equiv = []
            profiles = [
                h_function_plot("horizontal", 5e-5, 2e-5, 1e-5, 10, 10, 10, 200),
                h_function_plot("horizontal", 2e-5, 1e-5, 1e-5, 10, 10, 10, 200),
                h_function_plot("horizontal", 2e-5, 2e-5, 1e-5, 10, 10, 10, 200),
                h_function_plot("vertical", 1e-5, 1e-5, 0, 100, 100, 0),
                h_function_plot("vertical", 1e-5, 2e-5, 0, 100, 100, 0),
                h_function_plot("vertical", 1e-5, 5e-6, 0, 100, 100, 0),
            ]

            labels_corr = [i + " - " + j for i, j in zip([str(k) for k in [str(i) for i in range(1, 7)]], correction_schematic_to_profile)]


            # Plot the shuffled h(x) profiles
            for ax, idx, label in zip(axes.flat, shuffled_indices, labels_corr):
                x, h = profiles[idx]
                ax.plot(x, h)
                ax.set_title(f"({label})", fontsize=14)
                ax.set_ylim(40, 51)
                ax.set_xlabel("$x$ [m]")
                ax.set_ylabel("$h(x)$ [m]")
                ax.set_yticks(np.arange(40, 54, 2)) 
                ax.grid()
                # Adjust ylim 
                h_min, h_max = h.min(), h.max()

            display(Markdown(r""" 
<br><br>$h(x)$ profiles for the 6 configurations are shown again.<br>
The y-axis scale is now the same for all profiles to help you in comparing different $K_{eq}$ situations.)

"""))      
            plt.show()
          

    """
    Displays the exercise for K_eq attribution.
    """
    display(Markdown(r"""
## <br> Task 1: <br>

This exercise helps you to familiarize with Darcy law, for 1D and steady state conditions.

Horizontal saturated groundwater flow are established in soil layers with following properties :
- length $L$ : 100 $\text{m}$
- specific discharge at in- and out- flow per unit area ($A = 1\text{m}^2$): $q = 3 \cdot 10^{-7}\text{m}^2\text{s}^{-1}$
- negligible groundwater recharge

Each soil is a combination of vertical or horizontal layers, each layer having a given hydraulic conductivities $K$. 
Possible values in $\mu\text{m}\cdot\text{s}^{-1}$ are : **$K_0=5$, $K_1=10$, $K_2=20$, $K_3=50$**.


**Your task is to fill the table below**, where you should enter for each of the 6 soils (schematic (a) to (f)): 
- Line 1 : its equivalent hydraulic conductivity $K_{eq}$
- Line 2 : the number of its $h(x)$ profile plot.
    """))


    # Table of submission and submit button  -------------------------------
    k_eq_inputs = [widgets.Text(layout=widgets.Layout(width='100px')) for _ in range(6)]
    profile_inputs = [widgets.Text(layout=widgets.Layout(width='100px')) for _ in range(6)]
    display(Markdown(r"""**Submission Table :**<br> """))
    
    # Create the interactive table
    table = widgets.GridBox(
        children=[
            widgets.Label(value="Schematic:", layout=widgets.Layout(width='100px', height='30px', border='solid 1px black', align_items='center', justify_content='center')),
            widgets.Label(value="(a)", layout=widgets.Layout(width='100px', height='30px', border='solid 1px black', align_items='center', justify_content='center')),
            widgets.Label(value="(b)", layout=widgets.Layout(width='100px', height='30px', border='solid 1px black', align_items='center', justify_content='center')),
            widgets.Label(value="(c)", layout=widgets.Layout(width='100px', height='30px', border='solid 1px black', align_items='center', justify_content='center')),
            widgets.Label(value="(d)", layout=widgets.Layout(width='100px', height='30px', border='solid 1px black', align_items='center', justify_content='center')),
            widgets.Label(value="(e)", layout=widgets.Layout(width='100px', height='30px', border='solid 1px black', align_items='center', justify_content='center')),
            widgets.Label(value="(f)", layout=widgets.Layout(width='100px', height='30px', border='solid 1px black', align_items='center', justify_content='center')),
            widgets.Label("Keq", layout=widgets.Layout(width='100px', height='30px', border='solid 1px black', align_items='center', justify_content='center')),
            *k_eq_inputs,
            widgets.Label(value="Profile (1-6):", layout=widgets.Layout(width='100px', height='30px', border='solid 1px black', align_items='center', justify_content='center')),
            *profile_inputs,
        ],
        layout=widgets.Layout(grid_template_columns="150px repeat(6, 100px)")
    )
    # Submit button
    submit_button = widgets.Button(description="Submit", layout=widgets.Layout(width='100px', height='30px'), color="lightblue")
    output = widgets.Output()
    submit_button.on_click(on_submit)

    # Display both
    display(table, submit_button, output)

    ## Generate and plot the schematics -------------------------------
    n=1.5 # figure size scaling parameter 
    fig, axes = plt.subplots(2, 3, figsize=(11.2/n, 7/n),layout="constrained")  # Reduced overall figure height
    labels_sch = ["a", "b", "c", "d", "e", "f"]
    configurations = [1, 2, 3, 4, 5, 6]
    # Draw the schematic in each subplot
    for ax, label, config in zip(axes.flat, labels_sch, configurations):    
        draw_schematic(ax, label, config)


    plt.show()


    ## Generate and plot the h(x) profiles for the exercise -------------------------------
    fig, axes = plt.subplots(2, 3, figsize=(11/n, 7/n),layout="constrained")
    labels_prof = ["1", "2", "3", "4", "5", "6"]
    global correction_K_equiv
    correction_K_equiv = []
    profiles = [
        h_function_plot("horizontal", 5e-5, 2e-5, 1e-5, 10, 10, 10, 200),
        h_function_plot("horizontal", 2e-5, 1e-5, 1e-5, 10, 10, 10, 200),
        h_function_plot("horizontal", 2e-5, 2e-5, 1e-5, 10, 10, 10, 200),
        h_function_plot("vertical", 1e-5, 1e-5, 0, 100, 100, 0),
        h_function_plot("vertical", 1e-5, 2e-5, 0, 100, 100, 0),
        h_function_plot("vertical", 1e-5, 5e-6, 0, 100, 100, 0),
    ]
    global shuffled_indices
    global correction_profile_to_schematic
    global correction_schematic_to_profile


    shuffled_indices = np.random.permutation(6)  # Shuffle the profiles
    # Create an array to store the schematic-to-profile mapping
    correction_profile_to_schematic = [shuffled_indices.tolist().index(i) + 1 for i in range(6)]
    correction_schematic_to_profile = [labels_sch[i] for i in shuffled_indices]
    # Plot the shuffled h(x) profiles
    for ax, idx, label in zip(axes.flat, shuffled_indices, labels_prof):
        x, h = profiles[idx]
        ax.plot(x, h)
        ax.set_title(f"({label})", fontsize=14)
        #ax.set_ylim(40, 51)
        ax.set_xlabel("$x$ [m]")
        ax.set_ylabel("$h(x)$ [m]")
        # Adjust ylim 
        h_min, h_max = h.min(), h.max()
        padding = (h_max - h_min) * 0.3  # Calculate padding as 10% of the range
        ax.set_ylim(h_min - padding, h_max + padding)  # Add padding below h_min and above h_max
        ax.set_yticks(np.round(ax.get_yticks(), 0))  # Round to the nearest unit
        ax.grid()

    plt.show()


    

    return


#K3 = 5e-5
#K2 = 2e-5
#K1 = 1e-5
#K0 = 5e-6


## for the exercise asking the hydraulic head at the interface between the two layers



# Parameters
L = 7  # Length of each layer for the plot proportions (m)
K1 = 5e-5  # Hydraulic conductivity of the first layer (m/s)
K2 = 1e-5  # Hydraulic conductivity of the second layer (m/s)
q = 3.35e-5  # Specific discharge (m^2/s)
h0 = 50  # Hydraulic head at x = 0 (m)
hMID = 43.3  # Hydraulic head at the interface between the two layers (m)
h2L = 40  # Hydraulic head at x = 2L (m)



# Function to draw the schematic
def draw_schematic_interface():
    fig, ax = plt.subplots(figsize=(6.5, 4), layout="constrained")

    # Draw the two layers
    ax.add_patch(plt.Rectangle((0, 4), L, 2, edgecolor="black", facecolor="blue", alpha=0.3))
    ax.text(L/2,5 , r"K1=50 $\mu$m/s", color="black", fontsize=10, ha="center", va="center")
    ax.add_patch(plt.Rectangle((L, 4), L, 2, edgecolor="black", facecolor="green", alpha=0.3))

    # Draw the wells as piezometers (tubes)
    # Well at x=0
    ax.add_patch(plt.Rectangle((-0.5, 4), 0.5, 3, edgecolor="black", facecolor="white"))
    ax.text(2*L-L/2, 5 , r"K2=10 $\mu$m/s", color="black", fontsize=10, ha="center", va="center")
    ax.hlines(6.8, -0.5, 0, colors="blue", linewidth=2)  # Water table level inside the well
    
    # Add the blue arrows (square + triangle)
    x_start, y_start = -3, 5
    # Square part
    ax.add_patch(plt.Rectangle((x_start, y_start-0.25), 1, 0.5, edgecolor="blue", facecolor="blue", alpha=1.0))
    # Triangle part (arrowhead)
    triangle = plt.Polygon(
        [[x_start + 1, y_start- 1/2], [x_start + 1, y_start + 1/2], [x_start + 2, y_start]],
        edgecolor="blue",
        facecolor="blue",
        alpha=1.0,
    )
    ax.add_patch(triangle)
    x_start, y_start = 2*L+1, 5
    # Square part
    ax.add_patch(plt.Rectangle((x_start, y_start-0.25), 1, 0.5, edgecolor="blue", facecolor="blue", alpha=1.0))
    # Triangle part (arrowhead)
    triangle = plt.Polygon(
        [[x_start + 1, y_start- 1/2], [x_start + 1, y_start + 1/2], [x_start + 2, y_start]],
        edgecolor="blue",
        facecolor="blue",
        alpha=1.0,
    )
    ax.add_patch(triangle)

    # Well at x=2L
    ax.add_patch(plt.Rectangle((2 * L, 4), 0.5, 3, edgecolor="black", facecolor="white"))
    ax.hlines(6.3, 2 * L , 2 * L + 0.5, colors="blue", linewidth=2)  # Water table level inside the well

    # Well at x=L (Boundary)
    ax.vlines(L, 4, 6, colors="red", linewidth=2)

    # Add labels for the wells
    ax.text(0, 7.5, f"h(0) = {h0} m", fontsize=10, ha="center")
    ax.text(L, 6.5, "h(100) = ?", fontsize=10, ha="center", color="red")
    ax.text(2 * L, 7.5, f"h(200) = {h2L} m", fontsize=10, ha="center")

    # Add the x-axis at the bottom
    ax.hlines(3.5, 0, 2 * L, colors="black", linewidth=1)  # Horizontal line for the x-axis
    ax.text(0, 3, "$x$ = 0", fontsize=10, ha="center")  # Label for x=0
    ax.text(L, 3, "$x$ = 100 m", fontsize=10, ha="center")  # Label for x=L
    ax.text(2 * L, 3, "$x$ = 200 m", fontsize=10, ha="center")  # Label for x=2L

    # Add ticks on the x-axis
    ax.vlines(0, 3.4, 3.6, colors="black", linewidth=1)  # Tick at x=0
    ax.vlines(L, 3.4, 3.6, colors="black", linewidth=1)  # Tick at x=L
    ax.vlines(2 * L, 3.4, 3.6, colors="black", linewidth=1)  # Tick at x=2L

    ax.set_xlim(-5, 2 * L + 5)
    ax.set_ylim(0, 10)
    ax.set_xlabel("$x$ [m]", fontsize=12)
    ax.axis("off")

    plt.show()

# Function to draw the h(x) plot
def draw_hx_plot():
    fig, ax = plt.subplots(figsize=(5, 3),layout="constrained")


    # Plot h(x)
    x, h = h_function_plot("vertical", 5e-5, 1e-4, 0, 100, 100, 0, h0 = 50, q=3.35e-06, add_correction=False)
    ax.plot(x, h)
    ax.axvline(100, color="red")
    ax.axhline(43.3, color="green", linestyle="--")

    ax.set_title("Hydraulic head profile", fontsize=10)
    ax.set_xlabel("$x$ [m]", fontsize=10)
    ax.set_ylabel("$h(x)$ [m]", fontsize=10)
    ax.set_ylim(39, 51)
    ax.set_xlim(-20, 220)
    ax.set_yticks(np.arange(39, 52, 2))
    ax.grid(True)

    plt.show()




