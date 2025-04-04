import matplotlib.pyplot as plt
import numpy as np
import ipywidgets as widgets
from IPython.display import display

def display_disc_area_interactive(Q_min=15, Q_max=25, P_min=0.9, P_max=1.1):
    """
    Interactive function to display a disc whose area is equal to A = Q / P,
    where Q and P can be adjusted using sliders. Reference circles for specific
    values of P and Q are always displayed.

    Parameters:
        Q_min (float): Minimum value for Q slider.
        Q_max (float): Maximum value for Q slider.
        P_min (float): Minimum value for P slider.
        P_max (float): Maximum value for P slider.
    """

    # Label to display the current value of A
    A_label = widgets.Label(value="Current A: ")

    def plot_disc(Q, P):
        # Calculate the area A
        A = (1728 * Q * 1e-9 / 20) / (P * 1e-6)
        r = np.sqrt(A / np.pi)  # Radius for the current area

        # Reference circles
        A_ref = (1728 * 20 * 1e-9 / 20) / (1 * 1e-6)  # Reference area for P=1, Q=20
        r_ref = np.sqrt(A_ref / np.pi)

        A_min = (1728 * 15 * 1e-9 / 20) / (1.1 * 1e-6)  # Minimum area for P=1.1, Q=15
        r_min = np.sqrt(A_min / np.pi)

        A_max = (1728 * 25 * 1e-9 / 20) / (0.9 * 1e-6)  # Maximum area for P=0.9, Q=25
        r_max = np.sqrt(A_max / np.pi)

        A_bafu = 1.58  # BAFU estimation
        r_bafu = np.sqrt(A_bafu / np.pi)

        # Update the label with the current value of A
        A_label.value = f"Current A: {A:.4f} km²"

        # Create a 2D disc
        theta = np.linspace(0, 2 * np.pi, 100)
        x = r * np.cos(theta)
        y = r * np.sin(theta)

        # Reference circles
        x_ref = r_ref * np.cos(theta)
        y_ref = r_ref * np.sin(theta)

        x_min = r_min * np.cos(theta)
        y_min = r_min * np.sin(theta)

        x_max = r_max * np.cos(theta)
        y_max = r_max * np.sin(theta)

        x_bafu = r_bafu * np.cos(theta)
        y_bafu = r_bafu * np.sin(theta)

        # Plot the discs
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.fill(x, y, color='b', alpha=0.6, label=r"Result for currently selected $P$ and $Q$")
        ax.plot(x_ref, y_ref, 'r-', label=r"Our initial Area estimation")
        ax.plot(x_min, y_min, 'g--', label=r"$A_{min}$ and $A_{max}$, uncertainty interval.")
        ax.plot(x_max, y_max, 'g--')
        ax.plot(x_bafu, y_bafu, color='gray', linestyle='-', label=r"BAFU estimation ($A = 1.58$)")

        # Configure plot
        ax.set_title(r"Uncertainty on the area estimation", fontsize=14)
        ax.axis('off')  # Hide x and y axes
        ax.set_aspect('equal')  # Ensure the disc is circular
        ax.legend(loc='upper left', bbox_to_anchor=(1.05, 1), fontsize=10, frameon=True)
        plt.show()

    # Create sliders for Q and P
    Q_slider = widgets.FloatSlider(
        value=(Q_min + Q_max) / 2,  # Initial value
        min=Q_min,
        max=Q_max,
        step=0.1,
        description='Q:',
        continuous_update=True
    )

    P_slider = widgets.FloatSlider(
        value=(P_min + P_max) / 2,  # Initial value
        min=P_min,
        max=P_max,
        step=0.01,
        description='P:',
        continuous_update=True
    )

    # Link the sliders to the plot function
    interactive_plot = widgets.interactive(plot_disc, Q=Q_slider, P=P_slider)

    # Display the sliders, label, and the interactive plot
    display(A_label, interactive_plot)