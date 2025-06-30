import os
import matplotlib.pyplot as plt
from IPython.display import display, HTML, Markdown
from typing import Optional, Tuple
import sys

# Add parent directory to path to import accessibility_config
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from accessibility_config import (
    is_accessibility_enabled, 
    get_accessibility_setting, 
    get_figure_size
)


def display_image(image_filename: str, 
                 image_folder: str = "static",
                 alt_text: str = "", 
                 caption: str = "", 
                 figure_size: Optional[Tuple[float, float]] = None,
                 educational_context: str = "") -> None:
    """
    Display an image with optional accessibility features based on user settings.

    This function displays images from the SUPPORT_REPO static folder with 
    accessibility support that can be toggled on/off by the user.
    
    Parameters:
    - image_filename (str): The name of the image file to display
    - image_folder (str): The folder where the image is located [default: 'static']
    - alt_text (str): Alternative text description for screen readers
    - caption (str): Visible caption describing the image content and relevance
    - figure_size (tuple, optional): Figure size as (width, height) in inches. 
                                   If None, uses accessibility-aware default
    - educational_context (str): Learning objective or context for this image
    
    Returns:
    - None
    
    Example:
    >>> display_image("SwissTopoTsaletCatchment.png")  # Basic usage
    >>> 
    >>> # With accessibility features (shown when accessibility mode is on)
    >>> display_image(
    ...     "SwissTopoTsaletCatchment.png",
    ...     alt_text="Topographic map showing the Tsalet catchment boundary",
    ...     caption="Figure 1: Tsalet catchment area from Swiss Federal Office",
    ...     educational_context="Understanding catchment delineation"
    ... )
    """
    # Use accessibility-aware figure size if not specified
    if figure_size is None:
        figure_size = get_figure_size()
    
    # Construct flexible path to image
    base_path = os.path.join("..", "SUPPORT_REPO", image_folder)
    image_path = os.path.join(base_path, image_filename)
    
    # Check if accessibility mode affects error handling
    use_enhanced_errors = (is_accessibility_enabled() and 
                          get_accessibility_setting('enhanced_error_messages'))
    
    # Robust file existence check
    if not os.path.exists(image_path):
        if use_enhanced_errors:
            error_msg = f"""
            📋 **Image Loading Error**
            
            The requested image '{image_filename}' could not be found at:
            `{os.path.abspath(image_path)}`
            
            **Troubleshooting Steps:**
            1. Check that the filename is spelled correctly
            2. Verify the image exists in the SUPPORT_REPO/{image_folder} folder
            3. Ensure you're running this notebook from the correct directory
            
            **Expected location:** `SUPPORT_REPO/{image_folder}/{image_filename}`
            """
            display(Markdown(error_msg))
        else:
            print(f"Error: Image '{image_filename}' not found at {os.path.abspath(image_path)}")
        return
    
    # Display educational context only if accessibility mode is on
    if (educational_context and is_accessibility_enabled() and 
        get_accessibility_setting('show_learning_context')):
        context_html = f"""
        <div style="background-color: #e8f4fd; border-left: 4px solid #1f77b4; padding: 10px; margin: 10px 0;">
            <strong>🎯 Learning Context:</strong> {educational_context}
        </div>
        """
        display(HTML(context_html))
    
    # Create figure
    fig, ax = plt.subplots(figsize=figure_size)
    
    try:
        # Load and display the image
        img = plt.imread(image_path)
        ax.imshow(img)
        ax.axis('off')  # Remove axes for cleaner presentation
        
        # Add caption as figure title if provided and accessibility is on
        if (caption and is_accessibility_enabled() and 
            get_accessibility_setting('show_learning_context')):
            ax.set_title(caption, fontsize=12, fontweight='bold', pad=20)
        
        # Optimize layout
        plt.tight_layout()
        plt.show()
        
        # Display alt-text only if accessibility mode is on
        if (is_accessibility_enabled() and 
            get_accessibility_setting('show_alt_text')):
            if alt_text:
                alt_text_html = f"""
                <div style="font-style: italic; color: #666; margin-top: 5px; font-size: 0.9em;">
                    <strong>Image Description:</strong> {alt_text}
                </div>
                """
                display(HTML(alt_text_html))
            elif get_accessibility_setting('show_accessibility_reminders'):
                # Show reminder only in accessibility mode
                display(HTML("""
                <div style="color: #ff6b35; font-size: 0.8em; margin-top: 5px;">
                    ⚠️ <em>Accessibility Note: Consider adding alt_text for better accessibility</em>
                </div>
                """))
            
    except Exception as e:
        if use_enhanced_errors:
            error_msg = f"""
            📋 **Image Display Error**
            
            An error occurred while displaying '{image_filename}':
            `{str(e)}`
            
            **Common Causes:**
            - Unsupported image format
            - Corrupted image file
            - Insufficient memory for large images
            
            **Suggestion:** Try using a different image format (PNG, JPG) or reducing image size.
            """
            display(Markdown(error_msg))
        else:
            print(f"Error displaying image: {str(e)}")


def display_figure_with_context(image_filename: str,
                               figure_number: int,
                               caption: str,
                               description: str,
                               learning_objective: str = "",
                               source: str = "") -> None:
    """
    Display a figure with comprehensive educational context (accessibility-aware).
    
    This function provides a complete figure display suitable for educational content
    with proper numbering, descriptions, and learning integration. The level of detail
    shown depends on the user's accessibility settings.
    
    Parameters:
    - image_filename (str): Name of the image file
    - figure_number (int): Figure number for reference
    - caption (str): Descriptive caption/title of the figure
    - description (str): Detailed description of figure content and significance
    - learning_objective (str): How this figure relates to learning goals
    - source (str): Citation or source information for the figure
    
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
    
    # Get appropriate figure size based on accessibility settings
    figure_size = get_figure_size()
    
    # Display the image with context based on accessibility settings
    display_image(
        image_filename=image_filename,
        alt_text=alt_text,
        caption=formal_caption,
        educational_context=learning_objective,
        figure_size=figure_size
    )

    