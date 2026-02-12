
import ipywidgets as widgets
from IPython.display import display, Markdown, clear_output
from tasks_data import solutions, solutions_exact, solution_unit, questions_markdown, solutions_markdown, task_functions, task_functions_start, multiple_choice_options
from uncertainty_plot import display_disc_area_interactive




# Function to check the user's input and toggle the solution visibility
def check_task_with_solution(task_id):
    """
    Check the user's input for a task and toggle the solution visibility upon request.

    Parameters:
    - task_id (str): The ID of the task (e.g., "task1").
    """
    question_to_print = questions_markdown.get(task_id)
    correct_interval = solutions.get(task_id)
    exact_solution = solutions_exact.get(task_id)
    solution_to_print = solutions_markdown.get(task_id)
    unit_to_print = solution_unit.get(task_id)

    if not correct_interval:
        print(f"Error: No solution found for {task_id}.")
        return

    # Create widgets
    input_box = widgets.FloatText(
        description='Answer:',
        style={'description_width': 'initial'}
    )
    submit_button = widgets.Button(description="Submit")
    solution_button = widgets.Button(description="Show Solution", disabled=True)
    output = widgets.Output()
    solution_output = widgets.Output()

    # Track solution visibility state
    solution_visible = {"state": False}

   # Function to handle submission
    def on_submit(b):
        global user_input
        with output:
            output.clear_output()
            user_input = input_box.value
            display(Markdown(f"**Your answer:** {user_input}"))
            if correct_interval[0] <= user_input <= correct_interval[1]:
                output.clear_output()
                display(Markdown("**Correct!** Your input is within the correct interval."))
                display(Markdown(f"The exact solution is: **{exact_solution}**"))
                solution_button.disabled = False  # Enable the "Show Solution" button
            else:
                output.clear_output()
                display(Markdown("**Incorrect.**"))
                display(Markdown(f"The accepted interval is **{correct_interval}{unit_to_print}**."))
                display(Markdown(f"The exact solution is: **{exact_solution}{unit_to_print}**"))
                solution_button.disabled = False  # Enable the "Show Solution" button
            # Disable the submit button after submission
            submit_button.disabled = True
            input_box.disabled = True  # Disable the input box as well

    
    # Function to toggle the solution visibility
    def on_toggle_solution(b):
        with solution_output:
            if solution_visible["state"]:
                # Hide the solution
                solution_output.clear_output()
                solution_button.description = "Show Solution"
                solution_visible["state"] = False
            else:
                # Show the solution
                solution_output.clear_output()
                display(Markdown(solution_to_print))
                display(Markdown(r"""<br><br>"""))
                solution_button.description = "Hide Solution"
                solution_visible["state"] = True
                # Execute the task-specific function if provided
                if task_functions and task_id in task_functions:
                    task_functions[task_id]()  # Call the function


    # Attach event handlers
    submit_button.on_click(on_submit)
    solution_button.on_click(on_toggle_solution)

    # Display widgets
    display(Markdown(question_to_print))
    if task_functions_start and task_id in task_functions_start:
        task_functions_start[task_id]()  # Call the function
    display(widgets.HBox([input_box, submit_button]), output, solution_button, solution_output)


def check_dict_task_with_solution(task_id, user_values):
    """
    Check user's dict input against per-key tolerance ranges.

    Used for exercises where students fill in multiple related values,
    such as K values for different geological zones.

    Parameters:
    - task_id (str): The ID of the task (e.g., "task04_k_values")
    - user_values (dict): Dictionary of user-provided values to check

    The task must have entries in:
    - solutions: dict mapping keys to (min, max) tolerance tuples
    - solutions_exact: dict mapping keys to exact/reference values
    - questions_markdown: the question text
    - solutions_markdown: the solution explanation
    - solution_unit: dict mapping keys to unit strings (optional)
    """
    question_to_print = questions_markdown.get(task_id)
    tolerances = solutions.get(task_id)
    exact_solutions = solutions_exact.get(task_id)
    solution_to_print = solutions_markdown.get(task_id)
    units = solution_unit.get(task_id, {})

    if not tolerances or not isinstance(tolerances, dict):
        print(f"Error: No dict tolerances found for {task_id}.")
        return

    if not isinstance(user_values, dict):
        print(f"Error: Expected a dictionary of values, got {type(user_values).__name__}.")
        return

    # Create output widgets
    output = widgets.Output()
    solution_button = widgets.Button(description="Show Solution", disabled=True)
    solution_output = widgets.Output()
    solution_visible = {"state": False}

    # Check each key
    all_correct = True
    results = []

    for key, (min_val, max_val) in tolerances.items():
        user_val = user_values.get(key)
        exact_val = exact_solutions.get(key) if isinstance(exact_solutions, dict) else None
        unit = units.get(key, "") if isinstance(units, dict) else ""

        if user_val is None:
            results.append((key, "missing", None, (min_val, max_val), exact_val, unit))
            all_correct = False
        elif min_val <= user_val <= max_val:
            results.append((key, "correct", user_val, (min_val, max_val), exact_val, unit))
        else:
            results.append((key, "incorrect", user_val, (min_val, max_val), exact_val, unit))
            all_correct = False

    # Display results
    with output:
        output.clear_output()

        if all_correct:
            display(Markdown("**All values correct!** Your inputs are within the accepted ranges."))
        else:
            display(Markdown("**Some values need adjustment:**"))

        display(Markdown(""))

        for key, status, user_val, (min_val, max_val), exact_val, unit in results:
            key_display = key.replace("_", " ").title()
            if status == "missing":
                display(Markdown(f"- **{key_display}**: ⚠️ Missing value (expected {min_val}-{max_val} {unit})"))
            elif status == "correct":
                display(Markdown(f"- **{key_display}**: ✓ {user_val} {unit} (accepted range: {min_val}-{max_val} {unit})"))
            else:
                display(Markdown(f"- **{key_display}**: ✗ {user_val} {unit} (expected {min_val}-{max_val} {unit})"))

    # Enable solution button
    solution_button.disabled = False

    def on_toggle_solution(b):
        with solution_output:
            if solution_visible["state"]:
                solution_output.clear_output()
                solution_button.description = "Show Solution"
                solution_visible["state"] = False
            else:
                solution_output.clear_output()
                display(Markdown(solution_to_print))
                display(Markdown(r"""<br><br>"""))
                solution_button.description = "Hide Solution"
                solution_visible["state"] = True
                if task_functions and task_id in task_functions:
                    task_functions[task_id]()

    solution_button.on_click(on_toggle_solution)

    # Display
    display(Markdown(question_to_print))
    display(output, solution_button, solution_output)


def create_multiple_choice(task_id):
    """
    Create a multiple-choice widget for conceptual checkpoints.

    Parameters:
    - task_id (str): The ID of the task (e.g., "task04_checkpoint_5").

    The task must have entries in:
    - multiple_choice_options: list of (value, label) tuples
    - questions_markdown: the question text
    - solutions_exact: the correct answer (matching one of the values)
    - solutions_markdown: the solution explanation
    """
    question_to_print = questions_markdown.get(task_id)
    options = multiple_choice_options.get(task_id)
    correct_answer = solutions_exact.get(task_id)
    solution_to_print = solutions_markdown.get(task_id)

    if not options:
        print(f"Error: No multiple choice options found for {task_id}.")
        return

    if not correct_answer:
        print(f"Error: No correct answer found for {task_id}.")
        return

    # Extract just the labels for display in RadioButtons
    option_labels = [label for (value, label) in options]
    # Create mapping from label back to value for checking
    label_to_value = {label: value for (value, label) in options}

    # Create widgets
    radio = widgets.RadioButtons(
        options=option_labels,
        value=None,
        description='',
        disabled=False,
        layout=widgets.Layout(width='100%')
    )

    submit_button = widgets.Button(description="Check Answer", button_style='primary')
    solution_button = widgets.Button(description="Show Solution", button_style='info', disabled=True)
    output = widgets.Output()
    solution_output = widgets.Output()

    # Track solution visibility state
    solution_visible = {"state": False}

    def on_submit(b):
        with output:
            output.clear_output()
            if radio.value is None:
                display(Markdown("**Please select an answer.**"))
                return

            selected_label = radio.value
            selected_value = label_to_value[selected_label]

            # Check if correct - match the value prefix (e.g., "B) Losing" starts with "B)")
            is_correct = (selected_value == correct_answer or
                         selected_value.startswith(correct_answer.split(")")[0] + ")"))

            if is_correct:
                display(Markdown("**✓ Correct!**"))
            else:
                display(Markdown(f"**✗ Incorrect.** The correct answer is: **{correct_answer}**"))

            # Enable solution button and disable inputs
            solution_button.disabled = False
            submit_button.disabled = True
            radio.disabled = True

    def on_toggle_solution(b):
        with solution_output:
            if solution_visible["state"]:
                # Hide the solution
                solution_output.clear_output()
                solution_button.description = "Show Solution"
                solution_visible["state"] = False
            else:
                # Show the solution
                solution_output.clear_output()
                display(Markdown(solution_to_print))
                display(Markdown(r"""<br><br>"""))
                solution_button.description = "Hide Solution"
                solution_visible["state"] = True
                # Execute the task-specific function if provided
                if task_functions and task_id in task_functions:
                    task_functions[task_id]()

    # Attach event handlers
    submit_button.on_click(on_submit)
    solution_button.on_click(on_toggle_solution)

    # Display widgets
    display(Markdown(question_to_print))
    if task_functions_start and task_id in task_functions_start:
        task_functions_start[task_id]()
    display(radio)
    display(widgets.HBox([submit_button, solution_button]))
    display(output, solution_output)



