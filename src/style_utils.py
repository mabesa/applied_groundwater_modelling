from IPython.display import HTML, display
import os


def load_project_styles():
    """Load project-wide CSS styles for consistent formatting across notebooks"""
    project_root = os.path.abspath(os.path.join(os.getcwd(), '../..'))  # Adjust as needed
    css_path = os.path.join(project_root, 'static/css/custom_styles.css')
    
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
        #print(f"❌ CSS file not found at {css_path}")
