
# Import widgets and Markdown for interactive functionality
from ipywidgets import Output, VBox, FloatSlider, Button, RadioButtons
from IPython.display import Markdown, display, clear_output
import sys
import os
import matplotlib.pyplot as plt
import numpy as np
from shared_functions import check_task_with_solution

def darcy_experiment_simulation():
    """
    Simulates a Darcy experiment:
    - Starts with the point (0.4, 0.00012) already plotted in green.
    - Allows the user to select Δh values using a slider.
    - Plots the corresponding q values on a graph (q in mm/s).
    - Updates the plot dynamically as points are validated.
    - Adds a "Plot Fit" button to plot the fit line after more than 5 points are added.
    - Adds an "End Experiment" button to finalize the experiment.
    """

    display(Markdown("<br><h2> Task 2:"))
    display(Markdown("<br>You can now perform the Darcy experiment simulation. <br><br> Start by adding (I, q) points for at least 5 different hydraulic head differences. <br>Once at least 5 points are added, you will be able to plot the linear fit. <br><br><br>"))

    # Initialize variables
    delta_h_values = []  # Start with the point (0.4, 0.00012)
    q_values = []  # Corresponding q value
    output = Output()
    feedback_output = Output()  # For feedback messages
    feedback_texts = []  # To keep track of all feedback messages
    point_count = 0  # Start with 1 point already added
    fit_coefficients = None  # Store the fit coefficients

    # Darcy's law function
    def darcy_law(K, dh_L):
        return K * dh_L

    # Function to update the plot
    def update_plot(show_fit=False, highlight_first_point=False):
        with output:
            clear_output(wait=True)  # Clear the output to refresh the plot
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.set_title("Darcy Experiment: Δh vs q")
            ax.set_xlabel("I = Δh/L (-)")
            ax.set_ylabel("q (mm/s)")
            ax.grid(True)

            # Set fixed axis limits
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 0.3)  # Convert 0.0003 m/s to mm/s

            # Plot the points
            ax.scatter(delta_h_values, [q * 1000 for q in q_values], color='blue')  # Other points in blue

        
            # Plot the fit line if it has been calculated
            if fit_coefficients is not None:
                fit_line = np.poly1d(fit_coefficients)
                x_fit = np.linspace(0, 1, 100)
                y_fit = fit_line(x_fit)
                ax.plot(x_fit, [y * 1000 for y in y_fit], color='red')  # Convert q to mm/s

            plt.show()

    # Function to handle point validation
    def on_validate_point(button):
        nonlocal point_count
        with feedback_output:
            delta_h = slider.value
            if delta_h in delta_h_values:
                display(Markdown(f"**Error:** Δh = {delta_h:.2f} has already been added."))
                return

            # Calculate q using Darcy's law (assuming K = 0.0003 m/s)
            q = darcy_law(0.0003, delta_h)
            delta_h_values.append(delta_h)
            q_values.append(q)
            point_count += 1

            # Update the plot dynamically
            update_plot()

            # Enable the "Plot Fit" button if more than 5 points are added
            if len(delta_h_values) > 4:
                plot_fit_button.disabled = False

            # Add feedback message
            feedback_text = f"**Point {point_count} added:** Δh = {delta_h:.2f}, q = {q * 1000:.6f} mm/s"
            feedback_texts.append(feedback_text)
            clear_output(wait=True)
            for text in feedback_texts:
                display(Markdown(text))

    # Function to handle the "Plot Fit" button
    def on_plot_fit(button):
        nonlocal fit_coefficients
        # Fit a line to the points
        fit_coefficients = np.polyfit(delta_h_values, q_values, 1)
        update_plot(show_fit=True)
        # update_plot(highlight_first_point=True)  # Highlight the first point again
        plot_fit_button.disabled = True
        validate_button.disabled = True
        check_task_with_solution("task03_4")  # Call the function to launch a new task


        

    # Create the slider and buttons
    slider = FloatSlider(value=0.5, min=0.05, max=0.95, step=0.05, description='Δh:')
    validate_button = Button(description="Add measurement")
    validate_button.on_click(on_validate_point)

    plot_fit_button = Button(description="Plot Fit", disabled=True)  # Initially disabled
    plot_fit_button.on_click(on_plot_fit)


    # Display the widgets and output
    display(VBox([slider, validate_button, plot_fit_button, feedback_output, output]))

    # Initial plot with the pre-added point
    update_plot()
    with feedback_output:
        #feedback_texts.append(feedback_text)
        for text in feedback_texts:
            display(Markdown(text))




def darcy_experiment_simulation_global():
    """
    Creates a multiple-choice question with three options:
    - Linear
    - Quadratic
    - Logarithmic

    The correct answer is "Linear". The solution is displayed when the submit button is clicked.
    """
    # Define the options and the correct answer
    options = ["Quadratic", "Linear", "Logarithmic"]
    correct_answer = "Linear"

    # Create widgets
    question_output = Output()
    answer_output = Output()
    radio_buttons = RadioButtons(
        options=options,
        description="Select:",
        style={'description_width': 'initial'}
    )
    submit_button = Button(description="Submit")

    # Function to handle the submit button click
    def on_submit(button):
        with answer_output:
            clear_output(wait=True)
            selected_answer = radio_buttons.value
            if selected_answer == correct_answer:
                display(Markdown(r"""<br>**Correct!** Darcy's law describes a **linear** relationship : $q$ = $K \cdot I$, where $K$ is the hydraulic conductivity (property of the soil).<br><br><br>"""))
            else:
                display(Markdown(r"""<br>**Incorrect.** The correct answer is **linear** : $q$ = $K \cdot I$, where $K$ is the hydraulic conductivity (property of the soil).<br><br><br>"""))
            submit_button.disabled = True
            darcy_experiment_simulation()  # Call the simulation function

    # Attach the event handler to the submit button
    submit_button.on_click(on_submit)

    # Display the question and widgets
    with question_output:
        display(Markdown("<br><h2> Task 1:"))
        display(Markdown(f"What behavior do you expect for the curve of $q$ versus $I$?<br>"))
    display(VBox([question_output, radio_buttons, submit_button, answer_output]))


    