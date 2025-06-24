import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, RectangleSelector
import porespy as ps
from IPython.display import display, clear_output
import ipywidgets as widgets
import matplotlib.colors as mcolors

class REVExplorer:
    def __init__(self):
        self.shape = [300, 300]  # Size of the 2D image
        self.current_blobiness = 2
        self.current_porosity = 0.5
        self.selected_data = {}  # Format: {(porosity, blobiness): [(area, porosity), ...]}
        self.colors = plt.cm.tab10.colors  # Color cycle
        self.markers = ['o', 's', '^', 'D', 'v', 'p', '*', 'h', 'X', '+']  # Different marker shapes
        self.blobiness_values = []  # Track which blobiness values have been used
        self.porosity_values = []   # Track which porosity values have been used
        
        # Create custom colormap for porous media (greyish-brown for solid, light blue for pores)
        solid_color = mcolors.to_rgba('#8D7B68')  # Greyish brown for solid material
        pore_color = mcolors.to_rgba('#A0E9FF')   # Light blue for water in pores
        self.porous_cmap = mcolors.ListedColormap([solid_color, pore_color])
        
        # Generate initial image
        np.random.seed(42)  # For reproducibility
        self.image = ps.generators.blobs(
            shape=self.shape, 
            porosity=self.current_porosity, 
            blobiness=self.current_blobiness
        )
        
        # Create figures separately for better layout control
        self.fig_image = plt.figure(figsize=(5, 5))  # Image figure
        self.ax_image = self.fig_image.add_subplot(111)
        self.img_plot = self.ax_image.imshow(self.image, cmap=self.porous_cmap, origin='lower')
        self.ax_image.set_title('Select areas to analyze porosity')
        
        # Set μm scale for axes
        self.ax_image.set_xlabel('Distance (μm)')
        self.ax_image.set_ylabel('Distance (μm)')
        
        self.fig_rev = plt.figure(figsize=(5, 5))  # REV plot
        self.ax_rev = self.fig_rev.add_subplot(111)
        self.ax_rev.set_xlabel('Area (μm²)')
        self.ax_rev.set_ylabel('Porosity')
        self.ax_rev.set_title('REA Analysis')
        self.ax_rev.grid(True)
        self.ax_rev.axhline(y=self.current_porosity, color='black', linestyle='--', alpha=0.5)
        
        # Add widget controls
        self.porosity_slider = widgets.FloatSlider(
            value=self.current_porosity,
            min=0.1,
            max=0.9,
            step=0.05,
            description='Porosity:',
            continuous_update=False,
            layout=widgets.Layout(width='30%')
        )
        
        self.blobiness_slider = widgets.FloatSlider(
            value=self.current_blobiness,
            min=1.0,
            max=5.0,
            step=0.5,
            description='Blobiness:',
            continuous_update=False,
            layout=widgets.Layout(width='30%')
        )
        
        self.randomize_button = widgets.Button(
            description='Randomize',
            button_style='',
            tooltip='Generate new random medium',
            layout=widgets.Layout(width='15%')
        )
        
        self.clear_button = widgets.Button(
            description='Clear Plot',
            button_style='',
            tooltip='Clear REA Plot',
            layout=widgets.Layout(width='15%')
        )
        
        # Connect widget events
        self.porosity_slider.observe(self.update_image, names='value')
        self.blobiness_slider.observe(self.update_image, names='value')
        self.randomize_button.on_click(self.randomize)
        self.clear_button.on_click(self.clear_plot)
        
        # Set up rectangle selector
        self.rect_selector = RectangleSelector(
            self.ax_image, self.on_rect_select,
            useblit=True,
            button=[1],  # Left mouse button
            minspanx=5, minspany=5,
            spancoords='pixels',
            interactive=True
        )
        
        # Create layout for widgets and figures
        self.controls = widgets.HBox([
            self.porosity_slider, 
            self.blobiness_slider, 
            self.randomize_button,
            self.clear_button
        ])
        
        # Info text
        self.info_text = widgets.HTML(
            value="<b>Instructions:</b> Click and drag on the left image to select an area. The area and porosity will be plotted on the right."
        )
        
        self.selection_info = widgets.Output()
        
        # Side-by-side layout for figures (responsive to window width)
        self.figures = widgets.HBox([
            widgets.VBox([self.fig_image.canvas], layout=widgets.Layout(width='48%', height='auto')),
            widgets.VBox([self.fig_rev.canvas], layout=widgets.Layout(width='48%', height='auto'))
        ])
        
        # Combine everything into a vertical layout
        self.app = widgets.VBox([
            self.info_text,
            self.figures,
            self.controls,
            self.selection_info
        ])
        
        # Add legend for the porous media colors
        self.add_color_legend()
        
    def add_color_legend(self):
        """Add a small legend indicating what the colors represent"""
        legend_elements = [
            plt.Rectangle((0, 0), 1, 1, facecolor='#8D7B68', edgecolor='none', label='Solid material'),
            plt.Rectangle((0, 0), 1, 1, facecolor='#A0E9FF', edgecolor='none', label='Pore space (water)')
        ]
        self.ax_image.legend(handles=legend_elements, loc='upper right', fontsize='small')
        
    def update_image(self, change):
        # Update the image with new parameters
        self.current_porosity = self.porosity_slider.value
        self.current_blobiness = self.blobiness_slider.value
        
        # Regenerate the image
        np.random.seed(42)  # Keep the same seed for consistency
        self.image = ps.generators.blobs(
            shape=self.shape, 
            porosity=self.current_porosity, 
            blobiness=self.current_blobiness
        )
        
        # Update the image plot
        self.img_plot.set_data(self.image)
        
        # Update the target porosity line
        for line in self.ax_rev.lines:
            if line.get_linestyle() == '--':
                line.set_ydata([self.current_porosity, self.current_porosity])
        
        self.fig_image.canvas.draw_idle()
        self.fig_rev.canvas.draw_idle()
        
        # Re-add the legend since it gets cleared when the image updates
        self.add_color_legend()
    
    def randomize(self, b):
        # Generate a new random seed
        seed = np.random.randint(0, 1000)
        np.random.seed(seed)
        
        # Regenerate the image
        self.image = ps.generators.blobs(
            shape=self.shape, 
            porosity=self.current_porosity, 
            blobiness=self.current_blobiness
        )
        
        # Update the image plot
        self.img_plot.set_data(self.image)
        self.fig_image.canvas.draw_idle()
        
        # Re-add the legend
        self.add_color_legend()
    
    def clear_plot(self, b):
        # Clear the REV plot data
        self.selected_data = {}
        self.blobiness_values = []
        self.porosity_values = []
        self.update_rev_plot()
        
        # Clear selection rectangle
        for rect in self.ax_image.patches:
            rect.remove()
        self.fig_image.canvas.draw_idle()
        
        with self.selection_info:
            clear_output()
            print("Plot cleared. Make new selections.")
    
    def on_rect_select(self, eclick, erelease):
        # Get the coordinates of the selected rectangle
        x1, y1 = int(eclick.xdata), int(eclick.ydata)
        x2, y2 = int(erelease.xdata), int(erelease.ydata)
        
        # Ensure coordinates are within image bounds
        x1 = max(0, min(x1, self.shape[1]-1))
        y1 = max(0, min(y1, self.shape[0]-1))
        x2 = max(0, min(x2, self.shape[1]-1))
        y2 = max(0, min(y2, self.shape[0]-1))
        
        # Make sure x1 < x2 and y1 < y2
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        # Extract the selected region
        selected_region = self.image[y1:y2, x1:x2]
        
        # Highlight the selected area with a rectangle
        for rect in self.ax_image.patches:
            rect.remove()
        rect = plt.Rectangle((x1, y1), x2-x1, y2-y1, linewidth=2, 
                            edgecolor='red', facecolor='none', alpha=0.7)
        self.ax_image.add_patch(rect)
        self.fig_image.canvas.draw_idle()
        
        # Calculate area in mm²
        area = (x2 - x1) * (y2 - y1)
        porosity = np.mean(selected_region)
        
        # Store the result
        blobiness_rounded = round(self.current_blobiness, 1)
        porosity_rounded = round(self.current_porosity, 2)
        
        # Create a key for this parameter combination
        param_key = (porosity_rounded, blobiness_rounded)
        
        if param_key not in self.selected_data:
            self.selected_data[param_key] = []
            if blobiness_rounded not in self.blobiness_values:
                self.blobiness_values.append(blobiness_rounded)
            if porosity_rounded not in self.porosity_values:
                self.porosity_values.append(porosity_rounded)
        
        self.selected_data[param_key].append((area, porosity))
        
        # Update the REV plot
        self.update_rev_plot()
        
        # Show selection info
        with self.selection_info:
            clear_output()
            print(f"Selection: ({x1},{y1}) to ({x2},{y2})")
            print(f"Area: {area} μm²")
            print(f"Measured porosity: {porosity:.4f}")
            print(f"Target porosity: {porosity_rounded}")
            print(f"Blobiness: {blobiness_rounded}")
    
    def update_rev_plot(self):
        # Clear the REV plot
        self.ax_rev.clear()
        
        # Add reference lines for all used target porosities
        for porosity in self.porosity_values:
            self.ax_rev.axhline(y=porosity, color='gray', linestyle='--', alpha=0.3)
        
        # Highlight current porosity
        self.ax_rev.axhline(y=self.current_porosity, color='black', linestyle='--', alpha=0.5)
        
        # Plot data points
        for param_key, data_points in self.selected_data.items():
            porosity_value, blobiness_value = param_key
            
            # Determine color and marker
            color_idx = self.blobiness_values.index(blobiness_value) % len(self.colors)
            marker_idx = self.porosity_values.index(porosity_value) % len(self.markers)
            
            color = self.colors[color_idx]
            marker = self.markers[marker_idx]
            
            # Sort data points by area
            sorted_data_points = sorted(data_points, key=lambda x: x[0])
        
            areas = [d[0] for d in sorted_data_points]
            porosities = [d[1] for d in sorted_data_points]
            
            # Plot scatter points with both color (blobiness) and marker shape (porosity)
            self.ax_rev.scatter(
                areas, 
                porosities, 
                color=color, 
                marker=marker,
                s=60,  # Slightly larger marker size for better visibility
                label=f'P={porosity_value}, B={blobiness_value}'
            )

            # Add connecting line between sorted points
            self.ax_rev.plot(
                areas,
                porosities,
                color=color,
                linestyle='-',
                alpha=0.7,
                linewidth=1.5
            )
        
        # Set labels and title
        self.ax_rev.set_xlabel('Area (μm²)')
        self.ax_rev.set_ylabel('Porosity')
        self.ax_rev.set_title('REA Analysis')
        self.ax_rev.grid(True)
        
        # Create legend with unique entries
        if self.selected_data:
            handles, labels = self.ax_rev.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            self.ax_rev.legend(by_label.values(), by_label.keys(), 
                              loc='best', fontsize='small')
        
        self.fig_rev.canvas.draw_idle()
    
    def show(self):
        display(self.app)