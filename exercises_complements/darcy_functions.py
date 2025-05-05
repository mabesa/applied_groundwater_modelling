import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.lines as lines
import numpy as np
import ipywidgets as widgets
from IPython.display import display

def launch_darcy_experiment_interactive(qmin=0.000001, qmax=0.00001, kmin=0.00001, kmax=0.0001):
    """
    Launch an interactive Darcy experiment visualization with adjustable sliders for q and K.

    Parameters:
        qmin (float): Minimum value for the flow rate slider.
        qmax (float): Maximum value for the flow rate slider.
        kmin (float): Minimum value for the hydraulic conductivity slider.
        kmax (float): Maximum value for the hydraulic conductivity slider.
    """
    # Function to draw the Darcy experiment setup and the x-h coordinate system
    def draw_darcy_experiment_with_coordinates(K, q):
        # Map q to a color (white for low q, blue for high q)
        pipe_color = ((qmax - q) / (qmax - qmin), (qmax - q) / (qmax - qmin), 1)  # Gradient from white (low q) to blue (high q)

        # Create the figure and axes for two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5, 7), gridspec_kw={'height_ratios': [1, 1]})
        
        # --- First Subfigure: Darcy Experiment ---
        # Map K to a color (white for low K, dark gray for high K)
        color = ((kmax - K) / (kmax - kmin), (kmax - K) / (kmax - kmin), (kmax - K) / (kmax - kmin))  # Gradient for K value
        
        # Draw input pipe (two parallel lines)
        ax1.add_line(lines.Line2D([1.6, 2.93], [5], color=pipe_color, linewidth=10))  # Input pipe
        
        # Draw output pipe (two parallel lines)
        ax1.add_line(lines.Line2D([7.09, 8.4], [5, 5], color=pipe_color, linewidth=10))  # Output pipe
        
        # Draw the soil column (rectangle)
        soil_column = patches.Rectangle((3, 3), 4, 4, edgecolor='black', facecolor=color, label="Soil Column")
        ax1.add_patch(soil_column)
        
        # Add arrow at the entrance of the input pipe
        ax1.arrow(1.1, 5, 0.2, 0, head_width=0.2, head_length=0.2, fc=pipe_color, ec=pipe_color)
        ax1.text(0.9, 5, r'$q_{in}$', fontsize=14, color='blue', ha='center')  # Label q_in

        # Add arrow at the entrance of the output pipe
        ax1.arrow(8.47, 5, 0.2, 0, head_width=0.2, head_length=0.2, fc=pipe_color, ec=pipe_color)
        ax1.text(9.2, 5, r'$q_{out}$', fontsize=14, color='blue', ha='center')  # Label q_out

        # Add coordinate system at the bottom left
        ax1.arrow(1.5, 1.5, 7, 0, head_width=0.2, head_length=0.2, fc='black', ec='black')  # X-axis
        ax1.text(3, 1.2, r'$x_0 = 0$', fontsize=14, color='black', ha='center')  # Label x0
        ax1.text(7, 1.2, r'$x_1 = 400$m', fontsize=14, color='black', ha='center')  # Label x1
        
        # Add vertical lines to mark x0 and x1
        ax1.vlines(3, 1.5, 2, colors='black', linestyles='dashed')  # Vertical line at x0
        ax1.vlines(7, 1.5, 2, colors='black', linestyles='dashed')  # Vertical line at x1

        # Add a title showing the current K and q values
        ax1.set_title(rf'Darcy Experiment Setup ($K = {K:.5f}$, $q = {q:.6f}$)', fontsize=16)
        
        # Set axis limits and remove ticks for the first subplot
        ax1.set_xlim(0, 10)
        ax1.set_ylim(0, 10)
        ax1.axis('off')  # Turn off the axis
        
        # --- Second Subfigure: Plot h(x) ---
        # Parameters for h(x)
        x0 = 0
        x1 = 400
        h0 = 50
        x = np.linspace(x0, x1, 10000)  # 100 points between 0 and 10
        h = -(q / K) * (x - x0) + h0

        x_bef = np.linspace(-300, 0, 10000)  # 100 points between -10 and 0
        h_bef = np.zeros_like(x_bef) + h0  # h(x) = h0 for x < x0
        x_aft = np.linspace(x1, 700, 10000)  # 100 points between 10 and 20
        h_aft = np.zeros_like(x_aft) - (q / K) * (x1 - x0) + h0  

        # Plot h(x) in the second subplot
        ax2.plot(x, h, label=r"$h(x) = -\frac{q}{K}(x - x_0) + h_0$", color="blue")
        ax2.plot(x_bef, h_bef, color="blue")
        ax2.plot(x_aft, h_aft, color="blue")

        # Add a triangle to denote the water table level
        triangle = patches.Polygon([[-100, h0 + 2], [-80, h0 + 2], [-90, h0]], closed=True, color="blue")
        ax2.add_patch(triangle)
        
        # Add labels, legend, and grid
        ax2.set_xlabel("$x$ [m]", fontsize=14)
        ax2.set_ylabel("$h(x)$ [m]", fontsize=14)
        ax2.set_title("Hydraulic Head $h(x)$", fontsize=16)
        ax2.axhline(0, color="black", linewidth=0.5, linestyle="--")  # Add x-axis
        ax2.legend(fontsize=12)
        ax2.grid(True)

        # Set axis limits for the second subplot
        ax2.set_xlim(-300, 700)
        ax2.set_ylim(-10, h0 + 10)

        # Show the plot
        plt.tight_layout()
        plt.show()

    # Create sliders to adjust the K and q values
    K_slider = widgets.FloatSlider(
        value=0.00005,  # Initial value
        min=kmin,       # Minimum value
        max=kmax,       # Maximum value
        step=0.00001,   # Step size
        description='K:',
        continuous_update=True
    )

    q_slider = widgets.FloatSlider(
        value=0.000003,  # Initial value
        min=qmin,        # Minimum value
        max=qmax,        # Maximum value
        step=0.000001,   # Step size
        description='q:',
        continuous_update=True
    )

    # Link the sliders to the function
    interactive_plot = widgets.interactive(draw_darcy_experiment_with_coordinates, K=K_slider, q=q_slider)

    # Display the sliders and the interactive plot
    display(interactive_plot)


