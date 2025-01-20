from IPython.display import display, HTML, Markdown
import json
import os

class NotebookNavigation:
    def __init__(self, chapter_config_path='chapter_config.json', notebook_dir=None):
        """
        Initialize navigation with chapter configuration.
        """
        # Convert paths to absolute paths
        if notebook_dir:
            self.base_path = os.path.abspath(notebook_dir)
        else:
            # If no notebook_dir provided, use directory of the config file
            config_dir = os.path.dirname(os.path.abspath(chapter_config_path))
            self.base_path = config_dir

        self.config_path = os.path.join(self.base_path, os.path.basename(chapter_config_path))
        self.load_config()

    def load_config(self):
        """Load chapter configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.chapters = config['chapters'] if isinstance(config, dict) else config
        except Exception as e:
            print(f"Error loading config: {e}")
            print(f"Config path: {self.config_path}")
            print(f"Current working directory: {os.getcwd()}")
            self.chapters = []

    def get_relative_path(self, target_notebook):
        """
        Calculate relative path from current notebook to target notebook.
        """
        try:
            from IPython import get_ipython
            current_notebook = get_ipython().kernel.path
            current_dir = os.path.dirname(os.path.abspath(current_notebook))
        except:
            current_dir = os.getcwd()

        # Construct target path
        target_path = os.path.join(self.base_path, target_notebook)

        # Calculate relative path
        rel_path = os.path.relpath(target_path, current_dir)
        return rel_path

    def get_navigation_links(self, current_chapter):
        """Generate navigation links for current chapter."""
        try:
            current_idx = -1
            for i, chapter in enumerate(self.chapters):
                if chapter.get('id') == current_chapter:
                    current_idx = i
                    break

            if current_idx == -1:
                print(f"Chapter '{current_chapter}' not found in config")
                return ""

            prev_chapter = self.chapters[current_idx - 1] if current_idx > 0 else None
            next_chapter = (self.chapters[current_idx + 1]
                          if current_idx < len(self.chapters) - 1 else None)

            nav_html = ['<div style="display: flex; justify-content: space-between; padding: 20px;">']

            if prev_chapter:
                prev_path = self.get_relative_path(prev_chapter["filename"])
                nav_html.append(
                    f'<a href="{prev_path}" '
                    f'style="text-decoration: none; color: #2196F3;">'
                    f'← Previous: {prev_chapter["title"]}</a>'
                )
            else:
                nav_html.append('<span></span>')

            if next_chapter:
                next_path = self.get_relative_path(next_chapter["filename"])
                nav_html.append(
                    f'<a href="{next_path}" '
                    f'style="text-decoration: none; color: #2196F3;">'
                    f'Next: {next_chapter["title"]} →</a>'
                )

            nav_html.append('</div>')
            return '\n'.join(nav_html)
        except Exception as e:
            print(f"Error generating navigation links: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def display_navigation(self, current_chapter):
        """Display navigation links in the notebook."""
        nav_html = self.get_navigation_links(current_chapter)
        if nav_html:
            display(HTML(nav_html))

    def debug_config(self):
        """Print the current configuration for debugging."""
        print("\nCurrent chapters configuration:")
        print(f"Base path: {self.base_path}")
        print(f"Config path: {self.config_path}")
        try:
            from IPython import get_ipython
            print(f"Current notebook: {get_ipython().kernel.path}")
        except:
            print("Not running in IPython/Jupyter")

        for chapter in self.chapters:
            print(f"\nChapter: {chapter}")
            if 'filename' in chapter:
                full_path = os.path.join(self.base_path, chapter['filename'])
                rel_path = self.get_relative_path(chapter['filename'])
                print(f"Full path: {full_path}")
                print(f"Relative path: {rel_path}")
                print(f"Exists: {os.path.exists(full_path)}")

# Example chapter configuration (save as chapter_config.json):
"""
{
    "chapters": [
        {
            "id": "intro",
            "title": "Introduction to Groundwater Modeling",
            "filename": "01_introduction.ipynb",
            "prerequisites": []
        },
        {
            "id": "groundwater_balance",
            "title": "Groundwater Balance & REV",
            "filename": "02_groundwater_balance.ipynb",
            "prerequisites": ["intro"]
        },
        {
            "id": "darcy",
            "title": "Darcy's Law & Flow Physics",
            "filename": "03_darcy_law.ipynb",
            "prerequisites": ["groundwater_balance"]
        }
    ]
}
"""

# Usage in each notebook:
"""
# At the top of the notebook:
from notebook_navigation import NotebookNavigation
nav = NotebookNavigation()
nav.display_navigation('current_chapter_id')

# At the bottom of the notebook:
nav.display_navigation('current_chapter_id')
"""