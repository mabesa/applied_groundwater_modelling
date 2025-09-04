# ...existing imports...
from ipywidgets import Output, VBox, FloatSlider, Button, RadioButtons
from IPython.display import Markdown, display, clear_output
import matplotlib.pyplot as plt
import numpy as np
from shared_functions import check_task_with_solution

# Task 1.1: Multiple choice question about the expected curve
def darcy_task_1_1():
    options = ["Quadratic", "Linear", "Logarithmic"]
    correct_answer = "Linear"
    question_output = Output()
    answer_output = Output()
    radio_buttons = RadioButtons(
        options=options,
        description="Select:",
        style={'description_width': 'initial'}
    )
    submit_button = Button(description="Submit")

    def on_submit(button):
        with answer_output:
            clear_output(wait=True)
            selected_answer = radio_buttons.value
            if selected_answer == correct_answer:
                display(Markdown(
                    "<br>✅ **Correct!** Darcy's law describes a **linear** relationship: $q = K \\cdot I$, where $K$ is the hydraulic conductivity.<br><br>"
                ))
            else:
                display(Markdown(
                    "<br>❌ **Incorrect.** The correct answer is **linear**: $q = K \\cdot I$, where $K$ is the hydraulic conductivity.<br><br>"
                ))
            submit_button.disabled = True

    submit_button.on_click(on_submit)

    with question_output:
        display(Markdown("What behavior do you expect for the curve of $q$ versus $I$?"))
    display(VBox([question_output, radio_buttons, submit_button, answer_output]))

# Task 1.2: Interactive simulation for adding points and plotting fit
def darcy_task_1_2():
    display(Markdown(
        "Perform the Darcy experiment simulation.<br>"
        "Add (I, q) points for at least 5 different hydraulic head differences.<br>"
        "Once at least 5 points are added, you will be able to plot the linear fit.<br>"
    ))

    delta_h_values = []
    q_values = []
    output = Output()
    feedback_output = Output()
    feedback_texts = []
    point_count = 0
    fit_coefficients = None

    def darcy_law(K, dh_L):
        return K * dh_L

    def update_plot(show_fit=False):
        with output:
            clear_output(wait=True)
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.set_title("Darcy Experiment: Δh vs q")
            ax.set_xlabel("I = Δh/L (-)")
            ax.set_ylabel("q (mm/s)")
            ax.grid(True)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 0.3)
            ax.scatter(delta_h_values, [q * 1000 for q in q_values], color='blue')
            if fit_coefficients is not None and show_fit:
                fit_line = np.poly1d(fit_coefficients)
                x_fit = np.linspace(0, 1, 100)
                y_fit = fit_line(x_fit)
                ax.plot(x_fit, [y * 1000 for y in y_fit], color='red')
            plt.show()

    def on_validate_point(button):
        nonlocal point_count
        with feedback_output:
            delta_h = slider.value
            if delta_h in delta_h_values:
                display(Markdown(f"**Error:** Δh = {delta_h:.2f} has already been added."))
                return
            q = darcy_law(0.0003, delta_h)
            delta_h_values.append(delta_h)
            q_values.append(q)
            point_count += 1
            update_plot()
            if len(delta_h_values) > 4:
                plot_fit_button.disabled = False
            feedback_text = f"**Point {point_count} added:** Δh = {delta_h:.2f}, q = {q * 1000:.6f} mm/s"
            feedback_texts.append(feedback_text)
            clear_output(wait=True)
            for text in feedback_texts:
                display(Markdown(text))

    def on_plot_fit(button):
        nonlocal fit_coefficients
        fit_coefficients = np.polyfit(delta_h_values, q_values, 1)
        update_plot(show_fit=True)
        plot_fit_button.disabled = True
        validate_button.disabled = True

    slider = FloatSlider(value=0.5, min=0.05, max=0.95, step=0.05, description='Δh:')
    validate_button = Button(description="Add measurement")
    validate_button.on_click(on_validate_point)
    plot_fit_button = Button(description="Plot Fit", disabled=True)
    plot_fit_button.on_click(on_plot_fit)

    display(VBox([slider, validate_button, plot_fit_button, feedback_output, output]))
    update_plot()
    with feedback_output:
        for text in feedback_texts:
            display(Markdown(text))

# Task 1.3: Solution check for further analysis
def darcy_task_1_3():
    display(Markdown("Analyze the results and answer the following questions:"))
    check_task_with_solution("task03_3")

