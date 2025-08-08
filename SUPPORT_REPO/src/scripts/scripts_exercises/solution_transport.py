import numpy as np
import matplotlib.pyplot as plt
import scipy
import ipywidgets as widgets
from IPython.display import display, Markdown


def plot_tracer_propagation():
    """
    Plots the tracer front propagation in a column using:
    c(x, t) = c0 + (c1 - c0) * 0.5 * erfc((x - u * t / R) / np.sqrt(4 * D * t / R))
    """
    u=10
    D=10
    R=1.0
    x=400.0
    c0=0.0
    c1=1.0
    t_front = np.linspace(0.01, 80, 200)
    arg = (x - u * t_front / R) / np.sqrt(4 * D * t_front / R)
    c_xt_front = c0 + (c1 - c0) * 0.5 * scipy.special.erfc(arg)


    """
    Plots the concentration at an observation well at (x, y=0) for an instantaneous point source in 1D:
    c(x, t) = (M / (phi * m))/ ( 4*pi*t*sqrt(Dl * Dt)  * exp(-(x - u * t)^2 / (4 * Dl * t)), m=1, Dl=Dt=D
    """
    M=10 
    phi=0.2 
    u=10 
    Dl=10 
    Dt=0.1 
    x=400
    t_instant = np.linspace(0.01, 80, 200)
    # 1D solution for instantaneous source at x, y=0
    c_xt_instant = (M / (phi))/ ( 4*3.14*t_instant*np.sqrt(Dl * Dt))  * np.exp(-(x - u * t_instant)**2 / (4 * Dl * t_instant))
    
    """
    Plots the concentration at an observation well at (x, y=0) for an instantaneous point source in 1D BUT TOO SLOW:
    c(x, t) = (M / (phi * m))/ ( 4*pi*t*sqrt(Dl * Dt)  * exp(-(x - u * t)^2 / (4 * Dl * t)), m=1, Dl=Dt=D
    """
    M=10 
    phi=0.2 
    u=20 
    Dl=10 
    Dt=0.1 
    x=400
    t_instant_SLOW = np.linspace(0.01, 80, 200)
    # 1D solution for instantaneous source at x, y=0
    c_xt_instant_SLOW   = (M / (phi))/ ( 4*3.14*t_instant_SLOW*np.sqrt(Dl * Dt))  * np.exp(-(x - u * t_instant)**2 / (4 * Dl * t_instant))
    

    fig, axs = plt.subplots(1, 3, figsize=(12, 5))
    axs = axs.flatten()

    axs[0].plot(t_front, c_xt_front)
    axs[0].set_xlabel("$t$ [days]")
    axs[0].set_ylabel("$c(x, t)$ [kg/m$^3$]")
    axs[0].set_title("(a)")
    axs[0].grid(True)

    axs[1].plot(t_instant, c_xt_instant)
    axs[1].set_xlabel("$t$ [days]")
    axs[1].set_title("(b)")
    axs[1].set_ylim(0, 0.2)
    axs[1].grid(True)

    axs[2].plot(t_instant_SLOW, c_xt_instant_SLOW)
    axs[2].set_xlabel("$t$ [days]")
    axs[2].set_title("(c)")
    axs[2].set_ylim(0, 0.2)
    axs[2].grid(True)

    plt.show()


def question_tracer_propagation_plot():
    
    # Correct answer (for example, let's say "b" is correct)
    correct_answer = "b"
    options = ["a", "b", "c"]
    dropdown = widgets.Dropdown(
        options=options,
        value=None,
        description="Select:",
        layout=widgets.Layout(width='150px')
    )
    submit_btn = widgets.Button(description="Submit")
    feedback = widgets.Output()

    def on_submit(b):
        feedback.clear_output()
        with feedback:
            if dropdown.value is None:
                display(Markdown("Please select an option."))
            elif dropdown.value == correct_answer:
                display(Markdown("**Correct!**"))
                display(Markdown("**Solution:**"))
                display(Markdown("Plot (a) is not for an instantaneous source but for a tracer front propagation. "))
                display(Markdown("Plot (c) is for an instantaneous source but the peak reaches the well too earls ( 20 days) whereas our mean flow velocity is 10 m/day."))
                display(Markdown("Plot (b) is the correct one as it shows the concentration at the well for an instantaneous source with a mean flow velocity of 10 m/day, and has the expected gaussian shape"))
            else:
                display(Markdown(f"**Incorrect.** The correct answer is **{correct_answer}**."))
                display(Markdown("**Solution:**"))
                display(Markdown("Plot (a) is not for an instantaneous source but for a tracer front propagation. "))
                display(Markdown("Plot (c) is for an instantaneous source but the peak reaches the well too earls ( 20 days) whereas our mean flow velocity is 10 m/day."))
                display(Markdown("Plot (b) is the correct one as it shows the concentration at the well for an instantaneous source with a mean flow velocity of 10 m/day, and has the expected gaussian shape"))
            
            
    submit_btn.on_click(on_submit)
    display(widgets.HBox([dropdown, submit_btn]))
    display(feedback)
    plot_tracer_propagation()
    


def plot_curve_and_question_estimation():
    M=10 
    phi=0.2 
    u=10 
    Dl=10 
    Dt=0.1 
    x=400
    t_instant = np.linspace(0.01, 80, 200)
    # 1D solution for instantaneous source at x, y=0
    c_xt_instant = (M / (phi))/ ( 4*3.14*t_instant*np.sqrt(Dl * Dt))  * np.exp(-(x - u * t_instant)**2 / (4 * Dl * t_instant))
   
    fig, ax = plt.subplots(figsize=(5, 6))
    ax.plot(t_instant, c_xt_instant)
    ax.set_xlabel("Time [days]")
    ax.set_ylabel("Concentration [μg/L]")
    ax.grid(True)
    plt.show()

    # Widgets for answers
    conc_box = widgets.FloatText(
        description="Max conc. [μg/L]:",
        layout=widgets.Layout(width='500px')
    )
    span_box = widgets.FloatText(
        description="Δt time span above ref [days]:",
        layout=widgets.Layout(width='500px')
    )
    submit_btn = widgets.Button(description="Submit")
    feedback = widgets.Output()

    # Correct values
    max_index = np.argmax(c_xt_instant)
    correct_conc = c_xt_instant[max_index]
    above_ref = t_instant[c_xt_instant > 0.05]
    correct_span = above_ref[-1] - above_ref[0]

    def on_submit(b):
        feedback.clear_output()
        with feedback:
            score = 0
            # Check max concentration
            if abs(conc_box.value - correct_conc) < 0.01:
                display(Markdown(f"✅ Max concentration in the correct range. Exact analytical solution : ({correct_conc:.3f} μg/L)"))
                score += 1
            else:
                display(Markdown(f"❌ Max concentration incorrect.  Exact analytical solution : **{correct_conc:.3f} μg/L**"))
            # Check time span above reference
            if abs(span_box.value - correct_span) < 3:
                display(Markdown(f"✅ Time span above reference in the correct range. Exact analytical solution : ({correct_span:.1f} days)"))
                score += 1
            else:
                display(Markdown(f"❌ Time span incorrect.  Exact analytical solution : **{correct_span:.1f} days**"))
            display(Markdown(f"**Score: {score}/3**"))

    submit_btn.on_click(on_submit)

    display(Markdown("From the concentration curve (b), determine:"))
    display(conc_box)
    display(span_box)
    display(submit_btn)
    display(feedback)
