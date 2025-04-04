
import ipywidgets as widgets
from IPython.display import display, Markdown, clear_output
from tasks_data import solutions, solutions_exact, solution_unit, questions_markdown, solutions_markdown, task_functions
from uncertainty_plot import display_disc_area_interactive
from print_images import display_image




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
        with output:
            output.clear_output()
            user_input = input_box.value
            print(f"Your answer: {user_input}")
            if correct_interval[0] <= user_input <= correct_interval[1]:
                output.clear_output()
                print("Correct!")
                print(f"Your input is within the correct interval.")
                print(f"The exact solution is: {exact_solution}")
                solution_button.disabled = False  # Enable the "Show Solution" button
            else:
                output.clear_output()
                print(f"Incorrect")
                print(f"The accepted interval is {correct_interval}{unit_to_print}.")
                print(f"The exact solution is: {exact_solution}{unit_to_print}")
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
    display(input_box, submit_button, output, solution_button, solution_output)


