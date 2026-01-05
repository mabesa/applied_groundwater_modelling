from pykrige.ok import OrdinaryKriging
from pykrige.uk import UniversalKriging
import numpy as np
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import ipywidgets as widgets
from IPython.display import display, Markdown, clear_output, HTML
from math import sqrt


cmap = 'cividis_r' #cividis

# Initial well data
x_river = np.arange(0, 101, 1)
y_river = 0 * x_river
head_river = np.arange(148.99, 150, 0.01)[::-1]

x_wells = np.array([2, 2, 2, 2, 2, 20, 20, 20, 20, 20, 50, 50,50, 50, 50,80, 80, 80, 80, 80, 98, 98, 98, 98, 98])
y_wells = np.array([2, 20, 50, 80, 98,2, 20, 50, 80, 98, 2, 20, 50, 80, 98, 2, 20, 50, 80, 98,  2, 20, 50, 80, 98])
head_wells = np.array([
    149, 146, 145, 144, 143, 
    149, 146, 145, 149, 145, 
    149, 146, 145, 144, 142, 
    149, 144, 140, 141, 143, 
    149, 144, 146, 144, 142
])

x_all = np.concatenate((x_river, x_wells))
y_all = np.concatenate((y_river, y_wells))
head_all = np.concatenate((head_river, head_wells))

# Add 3 new wells (A, B, C) with unknown heads
x_new = np.array([20, 80, 70])
y_new = np.array([70, 70, 80])
labels_new = ['A', 'B', 'C']
global heads_new

def enable_hover_coordinates(ax):
    def format_coord(x, y):
        return f"x = {x:.1f}, y = {y:.1f}"
    ax.format_coord = format_coord

def plot_initial_wells():
    fig, ax = plt.subplots(figsize=(10, 6))
    x_all = np.concatenate((x_river, x_wells))
    y_all = np.concatenate((y_river, y_wells))
    head_all = np.concatenate((head_river, head_wells))
    sc = ax.scatter(
        x_all, y_all, c=head_all, cmap=cmap,
        marker='.', edgecolors='face',  # Use 'face' to match edge to colormap
        s=300, label='Known wells'
    )
    plt.colorbar(sc, label='$h(x,y)$ [m]')
    # Annotate only the observation wells (not the river)
    for x, y, h in zip(x_wells, y_wells, head_wells):
        ax.text(x + 1, y, f"{h:.0f}", fontsize=8, color='black', va='bottom')
    for i, (x, y, label) in enumerate(zip(x_new, y_new, labels_new)):
        ax.scatter(x, y, facecolors='red', edgecolors='red', marker='.', s=200, linewidths=1)
        ax.text(x + 1, y, label, fontsize=14, color='red', va='center')
    ax.set_xlabel('$x$ [m]')
    ax.set_ylabel('$y$ [m]')
    ax.set_xlim(-3, 103)
    ax.set_ylim(-3, 103)
    ax.set_title(f"Field data")
    ax.grid(True)
    enable_hover_coordinates(ax)
    plt.show()


def attribution_observation_well_student(resolution_interpolation):
    # Shuffle values for dropdown choices
    shuffled_heads = heads_new.copy()
    np.random.shuffle(shuffled_heads)
    # Create dropdowns for student selection
    dropdowns = {
        label: widgets.Dropdown(
            options=[str(round(head, 1))+"m" for head in shuffled_heads],
            description=label + ":",
            layout=widgets.Layout(width='180px')
        ) for label in labels_new
    }
    # Output widget
    output = widgets.Output()
    # Submit button and callback
    submit_button = widgets.Button(description="Submit")

    def on_submit_clicked(b):
        output.clear_output()
        submit_button.disabled = True
        with output:
            student_choice = []
            for label in labels_new:
                student_choice.append(dropdowns[label].value)
            for i in range(len(heads_new)):
                correct_value = round(heads_new[i], 1)
                # Compare as floats for robustness
                student_val = float(student_choice[i].replace('m', ''))
                if abs(student_val - correct_value) < 1e-6:
                    display(Markdown(f" - {labels_new[i]}: Correct (Your choice: {student_choice[i]})"))
                else:
                    display(Markdown(f" - {labels_new[i]}: Incorrect (Your choice: {student_choice[i]}, Correct: {correct_value}m)"))
            display(Markdown("Full interpolatied field using the linear interpolation method:"))
            plot_head_full_field_interactive('linear', resolution_interpolation)

    submit_button.on_click(on_submit_clicked)
    
    # Display the interactive matching tool
    display(Markdown(f"- **Match the correct interpolated head values to each observation well:**"))
    display(widgets.HBox([dropdowns['A'], dropdowns['B'], dropdowns['C']]))
    display(submit_button, output)


def estimation_hydraulic_head(method_passed = 'linear', resolution_interpolation_passed = 1000):
    global heads_new
    heads_new = griddata(
    (x_all, y_all), head_all, (x_new, y_new), method=method_passed
    )
    global method 
    method = method_passed
    global resolution_interpolation
    resolution_interpolation = resolution_interpolation_passed
    # Ask the student to guess the heads and then show the interpolatde field
    attribution_observation_well_student(resolution_interpolation)
    plot_initial_wells()



def plot_head_full_field_interactive(method_passed, resolution_interpolation_passed=1000):
    xi = np.linspace(0, 100, resolution_interpolation_passed)
    yi = np.linspace(0, 100, resolution_interpolation_passed)
    xi_grid, yi_grid = np.meshgrid(xi, yi)

    if method_passed in ['linear', 'nearest', 'cubic']:
        zi = griddata((x_all, y_all), head_all, (xi_grid, yi_grid), method=method_passed)
        heads_new = griddata((x_all, y_all), head_all, (x_new, y_new), method=method_passed)
    elif method_passed == 'ordinary_kriging':
        x_all_float = x_all.astype(float)
        y_all_float = y_all.astype(float)
        x_new_float = x_new.astype(float)
        y_new_float = y_new.astype(float)       
        OK = OrdinaryKriging(x_all_float, y_all_float, head_all, variogram_model='linear', verbose=False, enable_plotting=False)
        zi, _ = OK.execute('grid', xi, yi)
        heads_new = np.array([OK.execute('points', [x], [y])[0][0] for x, y in zip(x_new_float, y_new_float)])
    elif method_passed == 'universal_kriging':
        x_all_float = x_all.astype(float)
        y_all_float = y_all.astype(float)
        x_new_float = x_new.astype(float)
        y_new_float = y_new.astype(float)   
        UK = UniversalKriging(x_all_float, y_all_float, head_all, variogram_model='linear', drift_terms=['regional_linear'])
        zi, _ = UK.execute('grid', xi, yi)
        heads_new = np.array([UK.execute('points', [x], [y])[0][0] for x, y in zip(x_new_float, y_new_float)])
    else:
        raise ValueError("Unknown interpolation method.")

    fig, ax = plt.subplots(figsize=(8, 6))
    contour = ax.contour(xi_grid, yi_grid, zi, 15, cmap=cmap)
    fmt = lambda x: f"{x:.1f} m"
    plt.clabel(contour, inline=True, fontsize=8, fmt=fmt)
    ax.scatter(x_new, y_new, c=heads_new, cmap=cmap, edgecolor='red', s=80, marker='.', label='A, B, C')
    for i, label in enumerate(labels_new):
        ax.text(x_new[i] + 1, y_new[i], label, fontsize=14, color='red', va='center')
    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_title(f"Interpolated $h(x,y)$ field ({method_passed})")
    ax.grid(True)
    enable_hover_coordinates(ax)
    plt.show()

# Interactive widget for method selection
def interactive_interpolation():
    methods = [
        ('Nearest', 'nearest'),
        ('Linear', 'linear'),
        ('Cubic', 'cubic'),
        ('Ordinary Kriging', 'ordinary_kriging'),
        ('Universal Kriging', 'universal_kriging')
    ]
    method_buttons = widgets.ToggleButtons(
        options=methods,
        button_style='info',
        value=None  # No button selected at start
    )
    output = widgets.Output()

    def on_method_change(change):
        output.clear_output(wait=True)
        with output:
            display(Markdown("###         Loading the new interpolated field..."))
        # Now update plot
        output.clear_output(wait=True)
        with output:
            plot_head_full_field_interactive(change['new'])

    display(Markdown("<br>**Click on the interpolation method to display the field :** <br>"))
    method_buttons.observe(on_method_change, names='value')
    display(method_buttons)
    display(output)

