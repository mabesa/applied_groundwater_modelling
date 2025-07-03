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
    fig, ax = plt.subplots(figsize=(8, 6))
    x_all = np.concatenate((x_river, x_wells))
    y_all = np.concatenate((y_river, y_wells))
    head_all = np.concatenate((head_river, head_wells))
    sc = ax.scatter(
        x_all, y_all, c=head_all, cmap=cmap,
        marker='.', edgecolors='face',  # Use 'face' to match edge to colormap
        s=300, label='Known wells'
    )
    plt.colorbar(sc, label='$h(x,y)$ [m]')
    for i, (x, y, label) in enumerate(zip(x_new, y_new, labels_new)):
        ax.scatter(x, y, facecolors='red', edgecolors='red', marker='.', s=200, linewidths=1)
        ax.text(x + 1, y, label, fontsize=14, color='red', va='center')
    ax.set_xlabel('$x$ [m]')
    ax.set_ylabel('$y$ [m]')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_title(f"Field data : only known hydraulic heads are shown (observation wells and river).")
    ax.grid(True)
    enable_hover_coordinates(ax)
    plt.show()


def plot_head_full_field(method_passed = 'linear', resolution_interpolation_passed = 1000):
    heads_new = griddata(
        (x_all, y_all), head_all, (x_new, y_new), method=method_passed
    )
    # Grid for interpolation
    xi = np.linspace(0, 100, resolution_interpolation_passed)
    yi = np.linspace(0, 100, resolution_interpolation_passed)
    xi, yi = np.meshgrid(xi, yi)
    zi = griddata((x_all, y_all), head_all, (xi, yi), method=method_passed)
    fig, ax = plt.subplots(figsize=(8, 6))
    # Plot only line contours (no filled colormap)
    contour = ax.contour(xi, yi, zi, 15, cmap=cmap)
    # Add "m" unit to contour labels
    fmt = lambda x: f"{x:.1f} m"
    plt.clabel(contour, inline=True, fontsize=8, fmt=fmt)
    # Plot all wells
    ax.scatter(x_new, y_new, c=heads_new, cmap=cmap, edgecolor='red', s=80, marker='.', label='A, B, C (your answer)')
    for i, label in enumerate(labels_new):
        ax.text(x_new[i] + 1, y_new[i], label, fontsize=14, color='red', va='center')
    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_title(f"Interpolated $h(x,y)$ field ({method_passed} mode)")
    ax.grid(True)
    enable_hover_coordinates(ax)
    plt.show()


def attribution_observation_well_student(method, resolution_interpolation):
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
            # print the correction
            student_choice = []
            for label in labels_new:
                student_choice.append(dropdowns[label].value)
            for i in range (len(heads_new)):
                correct_value = round(heads_new[i], 1)
                if student_choice[i] == correct_value:
                    display(Markdown(f" - {labels_new[i]}: Correct (Your choice: {student_choice[i]})"))
                else:
                    display(Markdown(f" - {labels_new[i]}: Incorrect (Your choice: {student_choice[i]}, Correct: {correct_value})"))
            plot_head_full_field(method, resolution_interpolation)

    submit_button.on_click(on_submit_clicked)
    
    # Display the interactive matching tool
    display(Markdown(f"Match the correct interpolated head values to each observation well:<br>"))
    display(widgets.HBox([dropdowns['A'], dropdowns['B'], dropdowns['C']]))
    display(submit_button, output)




def task_05_01(method_passed = 'linear', resolution_interpolation_passed = 1000):
    global heads_new
    heads_new = griddata(
    (x_all, y_all), head_all, (x_new, y_new), method=method_passed
    )
    global method 
    method = method_passed
    global resolution_interpolation
    resolution_interpolation = resolution_interpolation_passed
    # 1. Show initial plot
    plot_initial_wells()
    # 2. Ask the student to guess the heads and then show the interpolatde field
    attribution_observation_well_student(method, resolution_interpolation)


def linear_interpolation_task():
    # Select 5 known points randomly from x_all, y_all, head_all
    indices = np.random.choice(len(x_all), 5, replace=False)
    x_5 = x_all[indices]
    y_5 = y_all[indices]
    h_5 = head_all[indices]
    
    # Pick 2 points from the 5 for linear interpolation
    idx1, idx2 = np.random.choice(5, 2, replace=False)
    
    x1, y1, h1 = x_5[idx1], y_5[idx1], h_5[idx1]
    x2, y2, h2 = x_5[idx2], y_5[idx2], h_5[idx2]
    
    # Midpoint
    x_mid = (x1 + x2) / 2
    y_mid = (y1 + y2) / 2
    h_mid_actual = (h1 + h2) / 2  # Linear interpolation

    # Distance
    dist = sqrt((x2 - x1)**2 + (y2 - y1)**2)

    # Plot the points
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(x_5, y_5, c=h_5, cmap=cmap, s=150, edgecolor='black')
    for i in range(5):
        ax.text(x_5[i] + 1, y_5[i], f"{h_5[i]:.1f} m", fontsize=12, color='black')
    
    # Highlight selected points
    ax.plot([x1, x2], [y1, y2], 'r--', label="Interpolation segment")
    ax.scatter(x1, y1, color='red', s=120)
    ax.scatter(x2, y2, color='red', s=120)
    
    # Midpoint
    ax.scatter(x_mid, y_mid, color='blue', s=120, label='Midpoint')
    ax.text(x_mid + 1, y_mid, "(Your answer here)", fontsize=12, color='blue')

    ax.set_title(f"Linear Interpolation Task: Distance = {dist:.2f} m")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.grid(True)
    ax.legend()
    plt.colorbar(scatter, label="Head [m]")
    plt.show()

    # Input box for user guess
    guess_input = widgets.FloatText(
        description='Your guess:',
        value=0.0,
        step=0.1,
        layout=widgets.Layout(width='250px')
    )

    check_output = widgets.Output()
    submit_btn = widgets.Button(description="Check Answer")

    def check_guess(b):
        check_output.clear_output()
        with check_output:
            selected = guess_input.value
            if abs(selected - h_mid_actual) < 0.05:
                display(Markdown(f"**Correct!** The interpolated head is **{h_mid_actual:.2f} m**"))
            else:
                display(Markdown(f"**Incorrect.** Your guess: {selected:.2f} m, Correct value: **{h_mid_actual:.2f} m**"))

    submit_btn.on_click(check_guess)

    display(Markdown("## Interpolation Question"))
    display(Markdown(
        f"Estimate the hydraulic head at the midpoint **assuming linear variation** between the two red points."
        f"<br>**Distance between them**: {dist:.2f} m"
    ))
    display(widgets.HBox([guess_input, submit_btn]))
    display(check_output)
