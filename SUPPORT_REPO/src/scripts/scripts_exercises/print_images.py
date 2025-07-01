import os
import textwrap
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from IPython.display import display, HTML
from typing import Optional, Tuple


def display_image(image_filename: str, 
                 image_folder: str = "static",
                 alt_text: str = "", 
                 caption: str = "", 
                 figure_size: Optional[Tuple[float, float]] = (10, 6)) -> None:
    """
    Display an image with alt text and optional caption.

    This function displays images from the SUPPORT_REPO static folder with 
    alt text support for accessibility.
    
    Parameters:
    - image_filename (str): The name of the image file to display
    - image_folder (str): The folder where the image is located [default: 'static']
    - alt_text (str): Alternative text description for screen readers
    - caption (str): Visible caption describing the image content
    - figure_size (tuple): Figure size as (width, height) in inches [default: (10, 6)]
    
    Returns:
    - None
    
    Example:
    >>> display_image("SwissTopoTsaletCatchment.png", 
    ...               alt_text="Topographic map showing the Tsalet catchment boundary",
    ...               caption="Figure 1: Tsalet catchment area from Swiss Federal Office")
    """
    # Construct path to image
    base_path = os.path.join("..", "SUPPORT_REPO", image_folder)
    image_path = os.path.join(base_path, image_filename)
    
    # Check if file exists
    if not os.path.exists(image_path):
        print(f"Error: Image '{image_filename}' not found at {os.path.abspath(image_path)}")
        return
    
    # Create and display figure
    fig, ax = plt.subplots(figsize=figure_size)
    
    try:
        # Load and display the image
        img = plt.imread(image_path)
        ax.imshow(img)
        ax.axis('off')  # Remove axes for cleaner presentation
        
        # Add caption as figure title if provided
        if caption:
            # Calculate approximate character width based on figure width
            # Assuming ~10-12 characters per inch for 12pt font
            chars_per_inch = 10
            max_width = int(figure_size[0] * chars_per_inch)
            
            # Wrap the caption text to fit the image width
            wrapped_caption = textwrap.fill(caption, width=max_width)
            ax.set_title(wrapped_caption, fontsize=12, fontweight='bold', pad=20)
        
        # Optimize layout and show
        plt.tight_layout()
        plt.show()
        
        # Display alt text if provided
        if alt_text:
            alt_text_html = f"""
            <div style="font-style: italic; color: #666; margin-top: 5px; font-size: 0.9em;">
                <strong>Image Description:</strong> {alt_text}
            </div>
            """
            display(HTML(alt_text_html))
            
    except Exception as e:
        print(f"Error displaying image: {str(e)}")


def display_figure_with_context(image_filename: str,
                               figure_number: int,
                               caption: str,
                               description: str,
                               learning_objective: str = "",
                               source: str = "",
                               figure_size: Optional[Tuple[float, float]] = (12, 8)) -> None:
    """
    Display a figure with comprehensive educational context.
    
    This function provides a complete figure display suitable for educational content
    with proper numbering, descriptions, and learning integration.
    
    Parameters:
    - image_filename (str): Name of the image file
    - figure_number (int): Figure number for reference
    - caption (str): Descriptive caption/title of the figure
    - description (str): Detailed description of figure content and significance
    - learning_objective (str): How this figure relates to learning goals
    - source (str): Citation or source information for the figure
    - figure_size (tuple): Figure size as (width, height) in inches [default: (12, 8)]
    
    Returns:
    - None
    
    Example:
    >>> display_figure_with_context(
    ...     "SwissTopoTsaletCatchment.png",
    ...     figure_number=1,
    ...     caption="Tsalet Catchment Topographic Overview",
    ...     description="Topographic map showing catchment boundaries and key features",
    ...     learning_objective="Practice catchment delineation for groundwater modeling",
    ...     source="Swiss Federal Office for the Environment (BAFU)"
    ... )
    """
    # Create comprehensive alt-text for accessibility
    alt_text = f"Figure {figure_number}: {caption}. {description}"
    
    # Create formal caption with source if provided
    if source:
        formal_caption = f"Figure {figure_number}: {caption} (Source: {source})"
    else:
        formal_caption = f"Figure {figure_number}: {caption}"
    
    # Display learning objective if provided
    if learning_objective:
        context_html = f"""
        <div style="background-color: #e8f4fd; border-left: 4px solid #1f77b4; padding: 10px; margin: 10px 0;">
            <strong>🎯 Learning Context:</strong> {learning_objective}
        </div>
        """
        display(HTML(context_html))
    
    # Display the image with context
    display_image(
        image_filename=image_filename,
        alt_text=alt_text,
        caption=formal_caption,
        figure_size=figure_size
    )
    
    # Display additional description if provided
    if description:
        description_html = f"""
        <div style="margin-top: 10px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
            <strong>Figure Description:</strong> {description}
        </div>
        """
        display(HTML(description_html))

    