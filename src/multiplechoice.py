import ipywidgets as widgets
from IPython.display import Math, Markdown, display, HTML

class MultipleChoice:
    def __init__(self, question, options, correct_answer, learning_resource):
        self.question = question
        self.options = options
        self.correct_answer = correct_answer
        self.learning_resource = learning_resource

    def ask(self):
        # Display question and options using Markdown
        display(Markdown(self.question))
        for i, opt in enumerate(self.options):
            display(Markdown(f"{i+1}. {opt}"))

        answer = widgets.RadioButtons(
            options=[(i+1) for i in range(len(self.options))],
            description='Select:',
            disabled=False
        )

        submit = widgets.Button(description='Submit')
        output = widgets.Output()

        def check_answer(b):
            with output:
                output.clear_output()
                if answer.value == self.correct_answer:
                    #display(Markdown("✅ Correct! Well done!"))
                    display(HTML("<p>✅ Correct! Well done!</p>"))
                else:
                    #display(Markdown(f"❌ Incorrect. Read up on the topic [here]({self.learning_resource}) and try again!"))
                    display(HTML(
                        f'<p>❌ Incorrect. Read up on the topic <a href="{self.learning_resource}" target="_blank">here</a> and try again!</p>'
                    ))

        submit.on_click(check_answer)
        return widgets.VBox([answer, submit, output])