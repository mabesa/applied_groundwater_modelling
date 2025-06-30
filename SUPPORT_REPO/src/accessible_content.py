"""
Accessible content display utilities for educational content.

This module provides functions to create accessible alternatives to CSS-styled boxes
that rely on color alone to convey meaning.
"""

from IPython.display import display, HTML, Markdown
from accessibility_config import is_accessibility_enabled, get_accessibility_setting
from typing import Optional


def display_content_box(content: str, 
                       box_type: str = "info",
                       title: str = "",
                       use_accessible_version: Optional[bool] = None) -> None:
    """
    Display educational content in either accessible or styled format.
    
    Parameters:
    - content (str): The main content to display
    - box_type (str): Type of box ('example', 'exercise', 'theory', 'furtherthinking')
    - title (str): Optional title for the box
    - use_accessible_version (bool, optional): Force accessible version. If None, uses accessibility settings
    """
    
    # Determine which version to use
    if use_accessible_version is None:
        use_accessible = is_accessibility_enabled()
    else:
        use_accessible = use_accessible_version
    
    # Box type configurations
    box_configs = {
        'example': {
            'emoji': '📚',
            'label': 'Example',
            'semantic_role': 'complementary',
            'aria_label': 'Example content'
        },
        'exercise': {
            'emoji': '🤔',
            'label': 'Think about it',
            'semantic_role': 'complementary', 
            'aria_label': 'Exercise for reflection'
        },
        'theory': {
            'emoji': '📖',
            'label': 'Theory',
            'semantic_role': 'complementary',
            'aria_label': 'Theoretical background'
        },
        'furtherthinking': {
            'emoji': '🔍',
            'label': 'Further Thinking',
            'semantic_role': 'complementary',
            'aria_label': 'Optional advanced topic'
        }
    }
    
    config = box_configs.get(box_type, box_configs['example'])
    
    if use_accessible:
        # Accessible version using semantic HTML and clear text indicators
        display_title = title if title else f"{config['emoji']} {config['label']}"
        
        accessible_html = f"""
        <section role="{config['semantic_role']}" aria-label="{config['aria_label']}">
            <h4 style="margin: 0 0 10px 0; padding: 10px; background-color: #f8f9fa; border: 2px solid #dee2e6; border-radius: 4px;">
                <strong>{display_title}</strong>
            </h4>
            <div style="padding: 15px; border: 1px solid #dee2e6; border-radius: 4px; background-color: #ffffff;">
                {content}
            </div>
        </section>
        """
        display(HTML(accessible_html))
        
    else:
        # Original styled version for users who prefer it
        css_class = f"custom-box {box_type}-box"
        if title:
            display_title = f"<strong>{title}</strong>"
        else:
            display_title = f"<strong>{config['emoji']} {config['label']}:</strong>"
        
        styled_html = f"""
        <div class="{css_class}">
            {display_title}<br>
            {content}
        </div>
        """
        display(HTML(styled_html))


def display_example_box(content: str, title: str = "") -> None:
    """Display an example box with appropriate accessibility handling."""
    display_content_box(content, 'example', title)


def display_exercise_box(content: str, title: str = "") -> None:
    """Display an exercise box with appropriate accessibility handling.""" 
    display_content_box(content, 'exercise', title)


def display_theory_box(content: str, title: str = "") -> None:
    """Display a theory box with appropriate accessibility handling."""
    display_content_box(content, 'theory', title)


def display_furtherthinking_box(content: str, title: str = "") -> None:
    """Display a further thinking box with appropriate accessibility handling."""
    display_content_box(content, 'furtherthinking', title)


def convert_html_box_to_accessible(html_content: str, box_type: str = "example") -> str:
    """
    Convert existing HTML box content to accessible format.
    
    This helper function can be used to quickly convert existing div-based boxes
    to the new accessible format.
    """
    # Extract content from HTML (basic extraction - may need refinement)
    import re
    
    # Remove HTML tags but preserve line breaks
    content = re.sub(r'<div[^>]*>', '', html_content)
    content = re.sub(r'</div>', '', content)
    content = re.sub(r'<br\s*/?>', '\n', content)
    content = content.strip()
    
    return content
