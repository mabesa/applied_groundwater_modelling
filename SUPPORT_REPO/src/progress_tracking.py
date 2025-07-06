"""
Progress Tracking System for Applied Groundwater Modeling Course

This module provides a flexible progress tracking system for Jupyter notebooks
with support for multiple progress trackers in the same course.

Basic Usage:

For Introduction/Modeling Process (10 steps):
    from progress_tracking import create_introduction_progress_tracker, create_step_completion_marker
    
    # Display the full tracker
    create_introduction_progress_tracker()
    
    # Mark specific steps complete
    create_step_completion_marker(1)  # Steps 1-10

For Perceptual Model (6 sections):
    from progress_tracking import create_perceptual_model_progress_tracker, create_section_completion_marker
    
    # Display the full tracker
    create_perceptual_model_progress_tracker()
    
    # Mark specific sections complete
    create_section_completion_marker(1)  # Sections 1-6

Reset Functions:
    reset_course_progress()  # Reset both trackers
    reset_introduction_progress()  # Reset only modeling process
    reset_perceptual_model_progress()  # Reset only perceptual model

Backward Compatibility:
    All existing functions continue to work:
    - get_tracker() -> returns IntroductionProgressTracker
    - create_chapter_completion_marker() -> alias for create_step_completion_marker()
"""

import json
import os
from pathlib import Path
import ipywidgets as widgets
from IPython.display import display, HTML
from datetime import datetime

class ProgressTracker:
    """
    Base progress tracker using standard Jupyter checkbox widgets.
    
    This class creates interactive checkboxes that students can tick/untick freely,
    with automatic persistence between sessions.
    """
    
    def __init__(self, tracker_name, progress_filename):
        """
        Initialize the progress tracker.
        
        Args:
            tracker_name (str): Name identifier for this tracker
            progress_filename (str): Filename for storing progress data
        """
        # Set up data directory
        self.tracker_name = tracker_name
        self.data_dir = Path.home() / '.groundwater_course_progress'
        self.data_dir.mkdir(exist_ok=True)
        self.progress_file = self.data_dir / progress_filename
        
        # Initialize steps (to be set by subclasses before calling parent __init__)
        if not hasattr(self, 'steps'):
            self.steps = []
        
        # Load saved progress
        self.progress_data = self._load_progress()
        self.widgets = {}
        self.progress_bar = None
    
    def _load_progress(self):
        """Load progress data from JSON file."""
        try:
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    print(f"📂 Loaded saved progress for {self.tracker_name}")
                    return data
        except Exception as e:
            print(f"⚠️ Could not load progress file for {self.tracker_name}: {e}")
        
        # Return default structure
        return {step_id: False for step_id, _ in self.steps}
    
    def _save_progress(self):
        """Save current progress data to JSON file."""
        try:
            # Get current state from widgets
            current_progress = {}
            for step_id in self.widgets:
                current_progress[step_id] = self.widgets[step_id].value
            
            with open(self.progress_file, 'w') as f:
                json.dump(current_progress, f, indent=2)
            
        except Exception as e:
            print(f"⚠️ Could not save progress for {self.tracker_name}: {e}")
    
    def create_interactive_tracker(self):
        """Create and display the interactive progress tracker."""
        
        # Calculate initial stats
        completed = sum(1 for status in self.progress_data.values() if status)
        total = len(self.steps)
        percentage = (completed / total * 100) if total > 0 else 0
        
        # Create checkbox widgets for each step
        for step_id, step_title in self.steps:
            checkbox = widgets.Checkbox(
                value=self.progress_data.get(step_id, False),
                description=step_title,
                style={'description_width': 'initial'},
                layout=widgets.Layout(width='100%', margin='8px 0px'),
                indent=False
            )
            
            # Store widget reference
            self.widgets[step_id] = checkbox
            
            # Add change handler for auto-save and progress bar update
            def on_change(change):
                self._save_progress()
            
            checkbox.observe(on_change, names='value')
            display(checkbox)
        
        return self.widgets
    
    def mark_step_complete_directly(self, step_number):
        """
        Mark a specific step as complete directly (for internal use).
        
        Args:
            step_number (int): Step number
        """
        step_id = f'step{step_number}'
        
        # Update data
        self.progress_data[step_id] = True
        
        # Update widget if it exists
        if step_id in self.widgets:
            self.widgets[step_id].value = True
            self._save_progress()

    def reset_progress(self):
        """Reset all progress for this tracker."""
        try:
            # Reset data
            self.progress_data = {step_id: False for step_id, _ in self.steps}
            
            # Reset widgets if they exist
            for widget in self.widgets.values():
                widget.value = False
            
            self._save_progress()
            
            print(f"🔄 All progress has been reset for {self.tracker_name}!")
        except Exception as e:
            print(f"⚠️ Could not reset progress for {self.tracker_name}: {e}")


class IntroductionProgressTracker(ProgressTracker):
    """
    Progress tracker for the introduction/modeling process steps.
    
    Tracks the 10-step modeling process outlined in the introduction notebook.
    """
    
    def __init__(self):
        """Initialize the introduction progress tracker."""
        # Define the 10 modeling process steps first
        self.steps = [
            ('step1', 'Step 1: Problem Definition'),
            ('step2', 'Step 2: Perceptual Model Development'),
            ('step3', 'Step 3: Conceptual Model Building'),
            ('step4', 'Step 4: Model Implementation'),
            ('step5', 'Step 5: Calibration'),
            ('step6', 'Step 6: Validation'),
            ('step7', 'Step 7: Sensitivity Analysis'),
            ('step8', 'Step 8: Model Application'),
            ('step9', 'Step 9: Documentation & Maintenance'),
            ('step10', 'Step 10: Result Communication')
        ]
        
        # Initialize base class
        super().__init__("Modeling Process", "modeling_process_progress.json")


class PerceptualModelProgressTracker(ProgressTracker):
    """
    Progress tracker for the perceptual model notebook sections.
    
    Tracks the major sections (H1 headers) in the perceptual model notebook.
    """
    
    def __init__(self):
        """Initialize the perceptual model progress tracker."""
        # Define the major sections from the perceptual model notebook first
        self.steps = [
            ('section1', 'Aquifer Geometry'),
            ('section2', 'Climate'),
            ('section3', 'River Discharge & River Water Levels'),
            ('section4', 'Monitoring the Limmat Valley Aquifer')
        ]
        
        # Initialize base class
        super().__init__("Perceptual Model", "perceptual_model_progress.json")


# Global tracker instances
_global_introduction_tracker = None
_global_perceptual_model_tracker = None

def get_introduction_tracker():
    """Get or create the global introduction tracker instance."""
    global _global_introduction_tracker
    if _global_introduction_tracker is None:
        _global_introduction_tracker = IntroductionProgressTracker()
    return _global_introduction_tracker

def get_perceptual_model_tracker():
    """Get or create the global perceptual model tracker instance."""
    global _global_perceptual_model_tracker
    if _global_perceptual_model_tracker is None:
        _global_perceptual_model_tracker = PerceptualModelProgressTracker()
    return _global_perceptual_model_tracker

def create_perceptual_model_progress_tracker():
    """
    Create and display the perceptual model progress tracker.
    
    This is the main function to call in the perceptual model notebook.
    """
    try:
        tracker = get_perceptual_model_tracker()
        tracker.create_interactive_tracker()
        # Don't return anything to avoid printing widget details
    except Exception as e:
        print(f"⚠️ Interactive tracker failed: {e}")
        return None

def create_section_completion_marker(section_number):
    """
    Create a section completion marker for perceptual model sections.
    
    Args:
        section_number (int): Section number (1-6)
    """
    try:
        tracker = get_perceptual_model_tracker()
        step_id = f'section{section_number}'
        
        # Get section name for display
        step_name = next((title for sid, title in tracker.steps if sid == step_id), f"Section {section_number}")
        
        # Check if already completed
        already_completed = tracker.progress_data.get(step_id, False)
        
        # Create confirmation checkbox
        completion_checkbox = widgets.Checkbox(
            value=already_completed,
            description=f"✅ Yes, I have completed {step_name}",
            style={'description_width': 'initial'},
            layout=widgets.Layout(width='100%', margin='10px 0px'),
            indent=False
        )
        
        # Create feedback area
        feedback_output = widgets.Output()
        
        def on_completion_change(change):
            """Handle when user checks/unchecks the completion box."""
            with feedback_output:
                feedback_output.clear_output()
                
                if change['new']:  # User checked the box
                    # Mark section complete in main tracker
                    tracker.progress_data[step_id] = True
                    if step_id in tracker.widgets:
                        tracker.widgets[step_id].value = True
                        tracker._save_progress()
                    
                else:  # User unchecked the box
                    # Remove completion from main tracker
                    tracker.progress_data[step_id] = False
                    if step_id in tracker.widgets:
                        tracker.widgets[step_id].value = False
                        tracker._save_progress()
        
        completion_checkbox.observe(on_completion_change, names='value')
        
        # Display the checkbox and feedback area
        display(completion_checkbox)
        display(feedback_output)
        
    except Exception as e:
        print(f"⚠️ Could not create section completion marker: {e}")

# Global tracker instance (backward compatibility)
_global_tracker = None

def get_tracker():
    """Get or create the global tracker instance (backward compatibility)."""
    return get_introduction_tracker()

def create_introduction_progress_tracker():
    """
    Create and display the introduction progress tracker.
    
    This is the main function to call in notebooks for modeling process tracking.
    """
    try:
        tracker = get_introduction_tracker()
        tracker.create_interactive_tracker()
        # Don't return anything to avoid printing widget details
    except Exception as e:
        print(f"⚠️ Interactive tracker failed: {e}")
        return None

def create_step_completion_marker(step_number):
    """
    Create a step completion marker that requires user confirmation for modeling process.
    
    Args:
        step_number (int): Step number (1-10)
    """
    try:
        tracker = get_introduction_tracker()
        step_id = f'step{step_number}'
        
        # Get step name for display
        step_name = next((title for sid, title in tracker.steps if sid == step_id), f"Step {step_number}")
        
        # Check if already completed
        already_completed = tracker.progress_data.get(step_id, False)
        
        # Create confirmation checkbox
        completion_checkbox = widgets.Checkbox(
            value=already_completed,
            description=f"✅ Yes, I have completed {step_name}",
            style={'description_width': 'initial'},
            layout=widgets.Layout(width='100%', margin='10px 0px'),
            indent=False
        )
        
        # Create feedback area
        feedback_output = widgets.Output()
        
        def on_completion_change(change):
            """Handle when user checks/unchecks the completion box."""
            with feedback_output:
                feedback_output.clear_output()
                
                if change['new']:  # User checked the box
                    # Mark step complete in main tracker
                    tracker.mark_step_complete_directly(step_number)
                    
                    # Calculate updated stats
                    completed = sum(1 for widget in tracker.widgets.values() if widget.value) if tracker.widgets else sum(tracker.progress_data.values())
                    total = len(tracker.steps)
                    percentage = (completed / total * 100) if total > 0 else 0
                    
                else:  # User unchecked the box
                    # Remove completion from main tracker
                    tracker.progress_data[step_id] = False
                    if step_id in tracker.widgets:
                        tracker.widgets[step_id].value = False
                        tracker._save_progress()
        
        completion_checkbox.observe(on_completion_change, names='value')
        
        # Display the checkbox and feedback area
        display(completion_checkbox)
        display(feedback_output)
        
    except Exception as e:
        print(f"⚠️ Could not create step completion marker: {e}")

def reset_course_progress():
    """Reset all course progress for both trackers."""
    try:
        introduction_tracker = get_introduction_tracker()
        perceptual_model_tracker = get_perceptual_model_tracker()
        
        introduction_tracker.reset_progress()
        perceptual_model_tracker.reset_progress()
        
    except Exception as e:
        print(f"⚠️ Could not reset progress: {e}")

def reset_introduction_progress():
    """Reset only the introduction/modeling process progress."""
    try:
        tracker = get_introduction_tracker()
        tracker.reset_progress()
    except Exception as e:
        print(f"⚠️ Could not reset introduction progress: {e}")

def reset_perceptual_model_progress():
    """Reset only the perceptual model progress."""
    try:
        tracker = get_perceptual_model_tracker()
        tracker.reset_progress()
    except Exception as e:
        print(f"⚠️ Could not reset perceptual model progress: {e}")

# Backward compatibility
create_chapter_completion_marker = create_step_completion_marker