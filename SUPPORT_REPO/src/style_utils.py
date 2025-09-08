from IPython.display import HTML, display
import os
from typing import Dict, Any

# --- Figure / caption style defaults (project-wide) ---
FIGURE_CAPTION_STYLE: Dict[str, Any] = {
    "fontsize": 12,
    "fontweight": "bold",
    "fontfamily": "DejaVu Sans",
    # Add other style kwargs here if needed (color, pad, loc, etc.)
}

def apply_caption_style(ax, text: str, pad: int = 20, wrap: int | None = None):
    """Apply the standardized caption/title style to an axes.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes
    text : str
        Title/caption text
    pad : int
        Padding in points between axes and title
    wrap : int | None
        Optional character width to wrap text; if None no manual wrapping.
    """
    import textwrap as _tw
    if wrap:
        text = _tw.fill(text, width=wrap)
    return ax.set_title(text, pad=pad, **FIGURE_CAPTION_STYLE)


def load_project_styles():
    """Load project-wide CSS styles for consistent formatting across notebooks"""
    project_root = os.path.abspath(os.path.join(os.getcwd(), '../../..'))  # Adjust as needed
    css_path = os.path.join(project_root, 'SUPPORT_REPO/static/css/custom_styles.css')
    
    if os.path.exists(css_path):
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Apply styles globally to the notebook
        display(HTML(f"""
        <style>
        {css_content}
        </style>
        """))
        #print("✅ Project styles loaded successfully")
    #else:
    #    print(f"❌ CSS file not found at {css_path}")
