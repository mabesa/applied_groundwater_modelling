"""
Accessibility configuration module for the Applied Groundwater Modeling course.

This module provides global accessibility settings that can be toggled by users
to optimize their learning experience based on their needs.
"""

from typing import Dict, Any
import ipywidgets as widgets
from IPython.display import display, HTML, clear_output

# Global accessibility configuration
_accessibility_config: Dict[str, Any] = {
    'enabled': False,
    'show_alt_text': True,
    'show_learning_context': True,
    'show_accessibility_reminders': True,
    'enhanced_error_messages': True,
    'figure_size_large': False
}


def get_accessibility_setting(key: str) -> Any:
    """
    Get the current value of an accessibility setting.
    
    Parameters:
    - key (str): The setting key to retrieve
    
    Returns:
    - Any: The current value of the setting
    """
    return _accessibility_config.get(key, False)


def set_accessibility_setting(key: str, value: Any) -> None:
    """
    Set an accessibility setting value.
    
    Parameters:
    - key (str): The setting key to update
    - value (Any): The new value for the setting
    """
    _accessibility_config[key] = value


def create_accessibility_switch() -> widgets.VBox:
    """
    Create an interactive accessibility configuration widget.
    
    Returns:
    - widgets.VBox: The complete accessibility control panel
    
    Example:
    >>> accessibility_switch = create_accessibility_switch()
    >>> display(accessibility_switch)
    """
    # Main toggle switch
    main_toggle = widgets.ToggleButton(
        value=_accessibility_config['enabled'],
        description='🔧 Accessibility Mode',
        disabled=False,
        button_style='info',
        tooltip='Enable enhanced accessibility features',
        icon='universal-access'
    )
    
    # Detailed settings (initially hidden)
    detailed_settings = widgets.VBox([
        widgets.HTML("<h4>Accessibility Options:</h4>"),
        widgets.Checkbox(
            value=_accessibility_config['show_alt_text'],
            description='Show image descriptions (alt-text)',
            tooltip='Display detailed descriptions of images and figures'
        ),
        widgets.Checkbox(
            value=_accessibility_config['show_learning_context'],
            description='Show learning context boxes',
            tooltip='Display educational context and learning objectives'
        ),
        widgets.Checkbox(
            value=_accessibility_config['show_accessibility_reminders'],
            description='Show accessibility reminders',
            tooltip='Display tips for better accessibility practices'
        ),
        widgets.Checkbox(
            value=_accessibility_config['enhanced_error_messages'],
            description='Enhanced error messages',
            tooltip='Show detailed, educational error messages'
        ),
        widgets.Checkbox(
            value=_accessibility_config['figure_size_large'],
            description='Use larger figure sizes',
            tooltip='Display images and plots in larger sizes for better visibility'
        )
    ])
    
    # Output area for status messages
    output_area = widgets.Output()
    
    def on_main_toggle_change(change):
        """Handle main accessibility toggle changes."""
        _accessibility_config['enabled'] = change['new']
        
        if change['new']:
            detailed_settings.layout.display = 'block'
            with output_area:
                clear_output()
                print("✅ Accessibility mode enabled")
        else:
            detailed_settings.layout.display = 'none'
            with output_area:
                clear_output()
                print("ℹ️ Accessibility mode disabled")
    
    def on_detailed_setting_change(change, setting_key):
        """Handle detailed setting changes."""
        _accessibility_config[setting_key] = change['new']
        with output_area:
            clear_output()
            status = "enabled" if change['new'] else "disabled"
            print(f"✓ {setting_key.replace('_', ' ').title()}: {status}")
    
    # Connect event handlers
    main_toggle.observe(on_main_toggle_change, names='value')
    
    # Connect detailed settings
    setting_keys = ['show_alt_text', 'show_learning_context', 'show_accessibility_reminders', 
                   'enhanced_error_messages', 'figure_size_large']
    
    for i, key in enumerate(setting_keys):
        detailed_settings.children[i+1].observe(
            lambda change, k=key: on_detailed_setting_change(change, k), 
            names='value'
        )
    
    # Initially hide detailed settings
    detailed_settings.layout.display = 'none' if not _accessibility_config['enabled'] else 'block'
    
    # Create info panel
    info_panel = widgets.HTML("""
    <div style="background-color: #f0f8ff; border: 1px solid #cce7ff; padding: 10px; margin: 10px 0; border-radius: 5px;">
        <strong>ℹ️ About Accessibility Mode:</strong><br>
        When enabled, this mode provides enhanced features for users with different accessibility needs:
        <ul>
            <li><strong>Image descriptions:</strong> Detailed alt-text displayed visually</li>
            <li><strong>Learning context:</strong> Clear connections to educational objectives</li>
            <li><strong>Enhanced feedback:</strong> More detailed error messages and guidance</li>
            <li><strong>Flexible sizing:</strong> Adjustable figure sizes for better visibility</li>
        </ul>
        <em>These features improve the experience for all users, not just those with accessibility needs.</em>
    </div>
    """)
    
    return widgets.VBox([
        widgets.HTML("<h3>🔧 Accessibility Configuration</h3>"),
        info_panel,
        main_toggle,
        detailed_settings,
        output_area
    ])


def is_accessibility_enabled() -> bool:
    """
    Check if accessibility mode is currently enabled.
    
    Returns:
    - bool: True if accessibility mode is enabled
    """
    return _accessibility_config['enabled']


def get_figure_size() -> tuple:
    """
    Get the appropriate figure size based on accessibility settings.
    
    Returns:
    - tuple: (width, height) for figure sizing
    """
    if _accessibility_config['enabled'] and _accessibility_config['figure_size_large']:
        return (12, 8)
    return (10, 6)
