import os
import matplotlib.pyplot as plt


def display_image(image_filename):
    """
    Display an image from the 'sources' folder.

    Parameters:
    - image_filename (str): The name of the image file to display.
    """
    # Define the path to the image in the 'sources' folder
    image_path = os.path.join("sources", image_filename)

    # Check if the file exists
    if not os.path.exists(image_path):
        print(f"Error: The file '{image_path}' does not exist.")
        return

    # Load and display the image using matplotlib
    img = plt.imread(image_path)
    plt.imshow(img)
    plt.axis('off')  # Turn off axis for better visualization
    plt.show()

    