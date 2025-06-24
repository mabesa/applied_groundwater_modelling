import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
from ipywidgets import interact, FloatText, VBox, Label

# Darcy's law: q = K * (dh/L)
def darcy_law(K, dh_L):
    return K * dh_L * 100 # in mm/s 

# Plotting function
def plot_darcy(K):
    # Load the Darcy experiment setup image
    img_path = "../SUPPORT_REPO/static/DarcyExperimentSetup.png"
    img = mpimg.imread(img_path)

    # Create a figure with two subplots
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    # Plot the Darcy experiment setup image
    axes[0].imshow(img)
    axes[0].axis('off')
    axes[0].set_title("Darcy Experiment Setup")

    # Generate data for the hydraulic gradient vs discharge graph
    dh_L = np.linspace(0, 1, 100)  # Hydraulic gradient (dh/L)
    q = darcy_law(K, dh_L)         # Discharge (q)

    # Plot the graph
    axes[1].plot(dh_L, q)

    axes[1].set_xlabel(r"$\frac{\Delta h}{L}$", fontsize=12)
    axes[1].set_ylabel(r"$q$ [mm/s]", fontsize=12)
    axes[1].set_title("Hydraulic Gradient vs Discharge")
    axes[1].grid()

    # Add a red point at dh/L = 0.4
    dh_L_point = 0.4
    q_point = darcy_law(K, dh_L_point)
    axes[1].scatter(dh_L_point, q_point, color='red')
    

    # Add a green point at q = 0.025 mm/s
    q_green = 0.025
    dh_L_green = q_green / (K * 100)  # Calculate dh/L for the green point
    axes[1].scatter(dh_L_green, q_green, color='green')
    
    # Hide axis values except at the red and green points
    axes[1].set_xticks([dh_L_point, dh_L_green])
    axes[1].set_xticklabels([rf"{dh_L_point:.2f}", ""])  # Hide green point dh/L value
    axes[1].set_yticks([q_point, q_green])
    axes[1].set_yticklabels(["", rf" {q_green:.3f}"])  # Hide red point q value    

    plt.tight_layout()
    plt.show()


# Fixed permeability value
K_fixed = 0.0003  # Example value in m/s

# Call the plotting function with the fixed K value
plot_darcy(K_fixed)