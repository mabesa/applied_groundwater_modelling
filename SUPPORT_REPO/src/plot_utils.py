import matplotlib.pyplot as plt
import numpy as np
import flopy
import flopy.plot


def plot_cross_section(modelgrid, row=None, col=None, mf=None, ibound=None, river_data=None, figsize=(16, 12), show_top_view=True):
    """
    Create cross-section plots along a specified row or column.
    
    Parameters:
    -----------
    modelgrid : flopy.discretization.StructuredGrid
        The model grid object
    row : int, optional
        Row number for east-west cross-section (0-indexed)
    col : int, optional
        Column number for north-south cross-section (0-indexed)
    mf : flopy.modflow.Modflow, optional
        MODFLOW model object for FloPy cross-section plotting
    ibound : numpy.ndarray, optional
        IBOUND array for showing active/inactive cells
    river_data : numpy.ndarray, optional
        River data array for plotting river cells
    figsize : tuple
        Figure size (width, height)
    show_top_view : bool, default True
        Whether to include a top view showing the cross-section location
    
    Returns:
    --------
    fig, axes : matplotlib figure and axes
        If show_top_view=True: fig, (ax_top, ax1, ax2)
        If show_top_view=False: fig, (ax1, ax2)
    """
    import matplotlib.pyplot as plt
    import numpy as np
    import flopy.plot # Import flopy.plot for PlotMapView and PlotCrossSection

    # Validate inputs
    if row is not None and col is not None:
        raise ValueError("Specify either row OR col, not both")
    if row is None and col is None:
        raise ValueError("Must specify either row or col")
    
    # Determine cross-section type and validate bounds
    if row is not None:
        if not (0 <= row < modelgrid.nrow):
            raise ValueError(f"Row must be between 0 and {modelgrid.nrow-1}")
        section_type = "row"
        section_num = row
        section_total = modelgrid.nrow
        print(f"Creating cross-section along row {row} (east-west, middle of {modelgrid.nrow} rows)")
    else:
        if not (0 <= col < modelgrid.ncol):
            raise ValueError(f"Column must be between 0 and {modelgrid.ncol-1}")
        section_type = "col"
        section_num = col
        section_total = modelgrid.ncol
        print(f"Creating cross-section along column {col} (north-south, middle of {modelgrid.ncol} columns)")
    
    # Create figure with subplots
    if show_top_view:
        fig = plt.figure(figsize=figsize)
        # Create a 2x2 grid, with top view spanning the top row
        ax_top = plt.subplot2grid((3, 2), (0, 0), colspan=2)
        ax1 = plt.subplot2grid((3, 2), (1, 0), colspan=2)
        ax2 = plt.subplot2grid((3, 2), (2, 0), colspan=2)
        axes = (ax_top, ax1, ax2)
    else:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize)
        axes = (ax1, ax2)
    
    # --- Determine the full extent of the modelgrid along the cross-section ---
    if section_type == "row":
        # For a row cross-section, the x-axis corresponds to modelgrid.xcellcenters
        # The full extent is from the first column's x-center to the last column's x-center
        full_x_coords = modelgrid.xcellcenters[row, :]
        xlabel_cs = 'Distance along cross-section (m)' # This label will be used for ax1 and ax2
    else: # col
        # For a column cross-section, the x-axis corresponds to modelgrid.ycellcenters
        # The full extent is from the first row's y-center to the last row's y-center
        full_x_coords = modelgrid.ycellcenters[:, col]
        xlabel_cs = 'Distance along cross-section (m)' # This label will be used for ax1 and ax2

    # Calculate min/max for setting xlim
    x_cs_min_full = full_x_coords.min()
    x_cs_max_full = full_x_coords.max()
    
    # Plot top view if requested
    if show_top_view:
        # Plot model domain
        x_edges = modelgrid.xvertices[0, :]
        y_edges = modelgrid.yvertices[:, 0]
        
        # Create meshgrid for plotting
        X, Y = np.meshgrid(x_edges / 1000, y_edges / 1000)  # Convert to km
        
        # Plot model top elevation as background
        im = ax_top.pcolormesh(X, Y, modelgrid.top, cmap='terrain', alpha=0.7, shading='auto')
        
        # Add colorbar for elevation
        cbar = plt.colorbar(im, ax=ax_top, shrink=0.6, pad=0.01)
        cbar.set_label('Elevation (m a.s.l.)', rotation=270, labelpad=15)
        
        # Highlight the cross-section line
        if section_type == "row":
            # East-west line (constant row, varying column)
            y_line = modelgrid.ycellcenters[row, 0] / 1000  # Convert to km
            x_start = modelgrid.xcellcenters[row, 0] / 1000
            x_end = modelgrid.xcellcenters[row, -1] / 1000
            ax_top.axhline(y=y_line, color='red', linewidth=3, label=f'Cross-section (Row {row})')
            ax_top.plot([x_start, x_end], [y_line, y_line], 'ro-', markersize=6, linewidth=3)
            
            # Set x-axis limits to match the cross-section extent
            ax_top.set_xlim(x_start, x_end)
        else:
            # North-south line (constant column, varying row)
            x_line = modelgrid.xcellcenters[0, col] / 1000  # Convert to km
            y_start = modelgrid.ycellcenters[0, col] / 1000
            y_end = modelgrid.ycellcenters[-1, col] / 1000
            ax_top.axvline(x=x_line, color='red', linewidth=3, label=f'Cross-section (Col {col})')
            ax_top.plot([x_line, x_line], [y_start, y_end], 'ro-', markersize=6, linewidth=3)
            
            # Set y-axis limits to match the cross-section extent
            ax_top.set_ylim(y_start, y_end)
        
        # Plot river cells if available
        if river_data is not None and len(river_data) > 0:
            river_rows = river_data[:, 1].astype(int)
            river_cols = river_data[:, 2].astype(int)
            river_x = modelgrid.xcellcenters[river_rows, river_cols] / 1000
            river_y = modelgrid.ycellcenters[river_rows, river_cols] / 1000
            ax_top.scatter(river_x, river_y, c='blue', s=20, alpha=0.8, label='River Cells', marker='s')
        
        # Plot inactive cells if available
        if ibound is not None:
            inactive_mask = ibound[0] != 1
            if np.any(inactive_mask):
                inactive_rows, inactive_cols = np.where(inactive_mask)
                if len(inactive_rows) > 0:
                    inactive_x = modelgrid.xcellcenters[inactive_rows, inactive_cols] / 1000
                    inactive_y = modelgrid.ycellcenters[inactive_rows, inactive_cols] / 1000
                    ax_top.plot(inactive_x, inactive_y, c='red', s=10, alpha=0.5, 
                                 label='Inactive Cells', marker='x')
        
        ax_top.set_xlabel('Easting (km)')
        ax_top.set_ylabel('Northing (km)')
        ax_top.set_title('Model Domain - Top View')
        ax_top.legend(loc='upper right')
        ax_top.grid(True, alpha=0.3)
        ax_top.set_aspect('equal')
    
    # Plot 1: Model grid and layers using FloPy
    if mf is not None:
        if section_type == "row":
            xs = flopy.plot.PlotCrossSection(model=mf, line={'row': row}, ax=ax1)
        else:
            xs = flopy.plot.PlotCrossSection(model=mf, line={'column': col}, ax=ax1)
        
        # Plot the grid
        patches = xs.plot_grid(alpha=0.5, linewidth=0.5, color='black')
        
        # Plot the model layers (top and bottom)
        patches = xs.plot_surface(modelgrid.top, color='brown', alpha=0.8, linewidth=2, label='Model Top (DEM)')
        patches = xs.plot_surface(modelgrid.botm[0], color='gray', alpha=0.8, linewidth=2, label='Model Bottom')
        
        # Fill the aquifer - use fallback approach to avoid color conflicts
        try:
            # FloPy's plot_fill_between should work here, but fallback remains
            xs.plot_fill_between(modelgrid.top, modelgrid.botm[0], color='lightblue', alpha=0.3, label='Aquifer')
        except (ValueError, TypeError) as e:
            print(f"FloPy fill method failed ({e}), using matplotlib fallback...")
            
            # Get coordinates and elevations for fallback. Use full_x_coords.
            ax1.fill_between(full_x_coords, modelgrid.botm[0, row, :] if section_type=="row" else modelgrid.botm[0, :, col],
                           modelgrid.top[row, :] if section_type=="row" else modelgrid.top[:, col],
                           color='lightblue', alpha=0.3, label='Aquifer')
        
        # Plot river cells if they exist along this section
        if river_data is not None and len(river_data) > 0:
            if section_type == "row":
                river_cells_in_section = river_data[river_data[:, 1].astype(int) == row]
                coord_idx_in_data = 2  # column index in river_data for x-coord on cross-section
            else:
                river_cells_in_section = river_data[river_data[:, 2].astype(int) == col]
                coord_idx_in_data = 1  # row index in river_data for x-coord on cross-section
            
            if len(river_cells_in_section) > 0:
                for i, river_cell in enumerate(river_cells_in_section):
                    cell_idx_on_cs_array = int(river_cell[coord_idx_in_data])
                    river_stage = river_cell[3]
                    river_bottom = river_cell[5]
                    
                    # Get x-coordinate of the cell using full_x_coords
                    x_coord_for_plot = full_x_coords[cell_idx_on_cs_array]
                    
                    # Plot river stage and bottom
                    ax1.scatter(x_coord_for_plot, river_stage, color='blue', s=50, marker='o', zorder=10)
                    ax1.scatter(x_coord_for_plot, river_bottom, color='darkblue', s=50, marker='s', zorder=10)
        
        ax1.set_title(f'Cross-Section: Model Grid and Layers ({section_type.title()} {section_num})')
        ax1.set_xlabel(xlabel_cs) # Use consistent label
        ax1.set_ylabel('Elevation (m a.s.l.)')
        ax1.grid(True, alpha=0.3)
        # ax1.set_xlim() is usually set automatically by FloPy's PlotCrossSection,
        # but we'll make sure ax2 matches it.
        
    # Plot 2: Detailed elevation profile
    # Use full_x_coords for the x-axis of this plot
    top_elevs_for_ax2 = modelgrid.top[row, :] if section_type == "row" else modelgrid.top[:, col]
    bottom_elevs_for_ax2 = modelgrid.botm[0, row, :] if section_type == "row" else modelgrid.botm[0, :, col]
    
    thickness = top_elevs_for_ax2 - bottom_elevs_for_ax2
    
    # Plot elevation profile
    ax2.fill_between(full_x_coords, bottom_elevs_for_ax2, top_elevs_for_ax2, color='lightblue', alpha=0.3, label='Aquifer')
    ax2.plot(full_x_coords, top_elevs_for_ax2, 'brown', linewidth=2, label='Model Top (DEM)')
    ax2.plot(full_x_coords, bottom_elevs_for_ax2, 'gray', linewidth=2, label='Model Bottom')
    
    # Plot river information if present
    if river_data is not None and len(river_data) > 0:
        if section_type == "row":
            river_cells_in_section = river_data[river_data[:, 1].astype(int) == row]
            coord_idx_in_data = 2
        else:
            river_cells_in_section = river_data[river_data[:, 2].astype(int) == col]
            coord_idx_in_data = 1
            
        if len(river_cells_in_section) > 0:
            # Sort river cells by their coordinate along the cross-section for proper plotting
            if section_type == "row":
                sort_indices = np.argsort(river_cells_in_section[:, 2].astype(int))
            else: # column
                sort_indices = np.argsort(river_cells_in_section[:, 1].astype(int))
            river_cells_in_section_sorted = river_cells_in_section[sort_indices]

            for i, river_cell in enumerate(river_cells_in_section_sorted):
                cell_idx_on_cs_array = int(river_cell[coord_idx_in_data])
                river_stage = river_cell[3]
                river_bottom = river_cell[5]
                
                # Get x-coordinate for plotting from full_x_coords
                x_coord_plot = full_x_coords[cell_idx_on_cs_array]
                
                # Determine cell width (in meters)
                if section_type == "row":
                    cell_width = modelgrid.delc[cell_idx_on_cs_array]
                else: # column
                    cell_width = modelgrid.delr[cell_idx_on_cs_array]
                
                half_width = cell_width / 2.0
                
                # Plot water column
                ax2.fill_between([x_coord_plot - half_width, x_coord_plot + half_width],
                                 [river_bottom, river_bottom],
                                 [river_stage, river_stage], color='blue', alpha=0.7)
                
                if i == 0: # Only plot labels once
                    ax2.plot([], [], 'blue', linewidth=3, label='River Stage')
                    ax2.plot([], [], 'darkblue', linewidth=3, label='River Bottom')
    
    # Add active/inactive cell information
    if ibound is not None:
        if section_type == "row":
            active_mask = ibound[0, row, :] == 1
        else:
            active_mask = ibound[0, :, col] == 1
            
        inactive_x = full_x_coords[~active_mask]
        inactive_top = top_elevs_for_ax2[~active_mask]
        if len(inactive_x) > 0:
            ax2.scatter(inactive_x, inactive_top, color='red', s=20, alpha=0.5, 
                       label='Inactive Cells', marker='x')
    else:
        active_mask = np.ones(len(full_x_coords), dtype=bool)  # All active if ibound not defined
    
    ax2.set_title(f'Elevation Profile Along {section_type.title()} {section_num}')
    ax2.set_xlabel(xlabel_cs) # Use consistent label
    ax2.set_ylabel('Elevation (m a.s.l.)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(x_cs_min_full, x_cs_max_full) # Set limits to full modelgrid extent
    
    # Add statistics as text
    stats_text = f"Cross-section Statistics:\n"
    stats_text += f"Length: {(x_cs_max_full - x_cs_min_full):.1f} m\n" # Use meters as per updated x-axis
    stats_text += f"Elevation range: {top_elevs_for_ax2.min():.1f} - {top_elevs_for_ax2.max():.1f} m\n"
    stats_text += f"Aquifer thickness: {thickness.min():.1f} - {thickness.max():.1f} m\n"
    stats_text += f"Active cells: {np.sum(active_mask)}/{len(active_mask)}"
    
    ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes, 
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
             verticalalignment='top', fontsize=10)
    
    plt.tight_layout()
    
    # Print information about the cross-section
    print(f"\nCross-section information:")
    if section_type == "row":
        print(f"Row: {row} (out of {modelgrid.nrow})")
        print(f"Number of columns: {modelgrid.ncol}")
    else:
        print(f"Column: {col} (out of {modelgrid.ncol})")
        print(f"Number of rows: {modelgrid.nrow}")
    print(f"Cross-section length: {(x_cs_max_full - x_cs_min_full):.1f} m") # Use meters
    print(f"Elevation range: {top_elevs_for_ax2.min():.1f} to {top_elevs_for_ax2.max():.1f} m a.s.l.")
    print(f"Aquifer thickness range: {thickness.min():.1f} to {thickness.max():.1f} m")
    print(f"Active cells in this section: {np.sum(active_mask)} out of {len(active_mask)}")
    
    return fig, axes