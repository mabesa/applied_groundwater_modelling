import os
import matplotlib.pyplot as plt
import pandas as pd
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

def plot_model_results(model, workspace, model_name, show_heads=True, show_vectors=True, 
                      show_grid=True, show_ibound=True, show_wells=True, contour_levels=None, 
                      vector_scale=1e5, figsize=(12, 10), title=None, save_path=None):
    """
    Plot model results showing heads and/or flow vectors.
    
    Parameters:
    -----------
    model : flopy.modflow object
        The MODFLOW model object
    workspace : str
        Path to model workspace
    model_name : str
        Name of the model (used for file names)
    show_heads : bool, default True
        Whether to show head contours
    show_vectors : bool, default True
        Whether to show flow vectors
    show_grid : bool, default True
        Whether to show model grid
    show_ibound : bool, default True
        Whether to show IBOUND boundaries
    show_wells : bool, default True
        Whether to show well locations from WEL package
    contour_levels : array-like, optional
        Specific contour levels for heads
    vector_scale : float, default 1e5
        Scale factor for flow vectors
    figsize : tuple, default (12, 10)
        Figure size
    title : str, optional
        Custom title for the plot
    save_path : str, optional
        Path to save the figure
        
    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    import os
    import numpy as np
    import matplotlib.pyplot as plt
    import flopy.utils
    
    # Initialize data containers
    head_data = None
    frf_data = None
    fff_data = None
    times = None
    
    # Load budget data if showing vectors
    if show_vectors:
        try:
            budgobj = flopy.utils.CellBudgetFile(os.path.join(workspace, f"{model_name}.cbc"))
            times = budgobj.get_times()
            kstpkper = budgobj.get_kstpkper()
            
            if len(kstpkper) > 0:
                # Extract flow right face and flow front face
                frf_data = budgobj.get_data(text="FLOW RIGHT FACE", totim=times[-1])[0]
                fff_data = budgobj.get_data(text="FLOW FRONT FACE", totim=times[-1])[0]
                print(f"Flow data loaded successfully for time {times[-1]}")
            else:
                print("No budget data found for flow vectors")
                show_vectors = False
        except Exception as e:
            print(f"Error loading flow data: {e}")
            show_vectors = False
    
    # Load head data if showing heads
    if show_heads:
        try:
            headobj = flopy.utils.HeadFile(os.path.join(workspace, f"{model_name}.hds"))
            if times is None:
                times = headobj.get_times()
            
            head_data = headobj.get_data(totim=times[-1])
            if head_data.ndim == 3:
                head_data = head_data[0]  # Get first layer
            
            # Mask head array where ibound == 0 (inactive cells)
            if hasattr(model, 'bas6') and model.bas6.ibound is not None:
                ibound = model.bas6.ibound.array[0]  # First layer
                head_data = np.where(ibound == 0, np.nan, head_data)
            
            print(f"Head data loaded successfully for time {times[-1]}")
        except Exception as e:
            print(f"Error loading head data: {e}")
            show_heads = False
    
    # Check if we have any data to plot
    if not show_heads and not show_vectors:
        print("No data available to plot")
        return None, None
    
    # Create the plot
    fig, ax = plt.subplots(figsize=figsize)
    pmv = flopy.plot.PlotMapView(modelgrid=model.modelgrid, ax=ax)
    
    # Track what was actually plotted for legend
    legend_elements = []
    
    # Plot IBOUND boundaries
    if show_ibound:
        pmv.plot_ibound()
    
    # Plot model grid
    if show_grid:
        pmv.plot_grid(alpha=0.2, linewidth=0.4)
    
    # Plot head contours
    if show_heads and head_data is not None:
        if contour_levels is not None:
            cont = pmv.contour_array(head_data, levels=contour_levels)
        else:
            cont = pmv.contour_array(head_data)
        plt.clabel(cont, inline=1, fontsize=8, fmt="%1.1f")
    
    # Plot flow vectors
    if show_vectors and frf_data is not None and fff_data is not None:
        quiver = pmv.plot_vector(frf_data, fff_data, scale=vector_scale, 
                                headwidth=3, headlength=5, headaxislength=4.5, 
                                color='blue', alpha=0.7)
        legend_elements.append('vectors')
    
    # Plot wells if requested
    if show_wells:
        try:
            if hasattr(model, 'wel') and model.wel is not None:
                # Use FloPy's built-in plot_bc method - much simpler!
                pmv.plot_bc(package=model.wel, kper=0, alpha=0.8)
                print(f"Wells plotted using FloPy's plot_bc method")
                legend_elements.append('wells')
            else:
                print("No WEL package found in model")
        except Exception as e:
            print(f"Error plotting wells: {e}")
    
    # Set title
    if title is None:
        title_parts = []
        if show_heads:
            title_parts.append("Head contours")
        if show_vectors:
            title_parts.append("flow vectors")
        if show_wells:
            title_parts.append("wells")
        title = f"{' and '.join(title_parts)} at time {times[-1] if times else 'final'}"
    
    ax.set_title(title)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_aspect('equal')
    
    # Add legend only if there are actually legend entries
    if len(legend_elements) > 0:
        try:
            ax.legend(loc='best', bbox_to_anchor=(1.05, 1), borderaxespad=0)
            plt.tight_layout()
        except UserWarning:
            # If no legend entries exist, just continue without legend
            plt.tight_layout()
    else:
        plt.tight_layout()
    
    # Save figure if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to: {save_path}")
    
    plt.show()
    return fig, ax

def visualize_budget(workspace, model_name, threshold=100.0):
    """
    Visualize MODFLOW budget terms with improved formatting and conditional rounding.
    
    Parameters:
    -----------
    workspace : str
        Path to the model workspace
    model_name : str
        Name of the model
    threshold : float
        Threshold above which values are rounded to integers (default: 100.0)
    """
    try:
        # Read budget from list file
        list_budget = flopy.utils.MfListBudget(
            os.path.join(workspace, f'{model_name}.list'))
        budget = list_budget.get_budget()[-1]  # Last time step
        
        df = pd.DataFrame(budget).T

        # Identify _IN, _OUT, and summary rows
        in_rows = df.index[df.index.str.endswith('_IN')]
        out_rows = df.index[df.index.str.endswith('_OUT')]
        summary_rows = df.index[~(df.index.str.endswith('_IN') | df.index.str.endswith('_OUT'))]

        # Filter summary rows to IN-OUT and PERCENT_DISCREPANCY
        summary_rows = summary_rows[summary_rows.str.contains('IN-OUT|PERCENT_DISCREPANCY')]

        # Concatenate in desired order
        df_reordered = pd.concat([df.loc[in_rows], df.loc[out_rows], df.loc[summary_rows]])
        
        # Check if most values are above threshold for conditional rounding
        numeric_values = df_reordered.select_dtypes(include=[np.number]).values.flatten()
        numeric_values = numeric_values[~np.isnan(numeric_values)]  # Remove NaN values
        
        if len(numeric_values) > 0:
            above_threshold_count = np.sum(np.abs(numeric_values) >= threshold)
            total_count = len(numeric_values)
            
            if above_threshold_count > total_count / 2:  # More than half are above threshold
                # Round to integers for large values
                df_reordered = df_reordered.round(0).astype(int, errors='ignore')
                unit_label = "m³/day (rounded to integers)"
            else:
                # Keep decimal places for smaller values
                df_reordered = df_reordered.round(2)
                unit_label = "m³/day"
        else:
            df_reordered = df_reordered.round(2)
            unit_label = "m³/day"

        # Remove columns that are all zeros (if any exist)
        df_clean = df_reordered.loc[:, (df_reordered != 0).any(axis=0)]
        
        print(f"Budget terms ({unit_label}) at end of first stress period:")
        print("=" * 60)
        
        if len(in_rows) > 0:
            print("\n📈 INFLOWS:")
            print("-" * 30)
            inflow_df = df_clean.loc[in_rows]
            print(inflow_df.to_string())
            
        if len(out_rows) > 0:
            print("\n📉 OUTFLOWS:")
            print("-" * 30)
            outflow_df = df_clean.loc[out_rows]
            print(outflow_df.to_string())
            
        if len(summary_rows) > 0:
            print("\n📊 SUMMARY:")
            print("-" * 30)
            summary_df = df_clean.loc[summary_rows]
            print(summary_df.to_string())
            
        # Calculate and display totals
        if len(in_rows) > 0 and len(out_rows) > 0:
            total_in = df_clean.loc[in_rows].sum(axis=0, numeric_only=True)
            total_out = df_clean.loc[out_rows].sum(axis=0, numeric_only=True)
            
            print("\n💰 TOTALS:")
            print("-" * 30)
            print(f"Total Inflow:  {total_in.iloc[0]:>10,.0f} m³/day")
            print(f"Total Outflow: {total_out.iloc[0]:>10,.0f} m³/day")
            print(f"Net Flow:      {(total_in.iloc[0] + total_out.iloc[0]):>10,.0f} m³/day")
            
        return df_clean
        
    except Exception as e:
        print(f"Error reading budget: {e}")
        return None
    

def plot_head_difference(model_base, model_scenario, ws_base, ws_scenario, model_name, 
                        save_path=None, show_depth_plots=True, show_wells=True, 
                        well_marker_size=100, scenario_name="Scenario", 
                        min_contour_diff=0.01):
    """
    Plot the difference in groundwater heads between base model and scenario model.
    
    Parameters:
    -----------
    model_base : flopy.modflow.Modflow
        Base model 
    model_scenario : flopy.modflow.Modflow  
        Scenario model to compare against base
    ws_base : str
        Workspace path for base model
    ws_scenario : str
        Workspace path for scenario model
    model_name : str
        Model name for file naming
    save_path : str, optional
        Path to save the figure
    show_depth_plots : bool, optional
        Whether to show the second row of plots (depth to water table analysis).
        Default is True. If False, only shows head analysis plots.
    show_wells : bool, optional
        Whether to show well locations on the plots. Default is True.
    well_marker_size : int, optional
        Size of well markers. Use smaller values (e.g., 50-80) for regional models,
        larger values (e.g., 100-150) for local models. Default is 100.
    scenario_name : str, optional
        Name for the scenario model in plot titles. Default is "Scenario".
    min_contour_diff : float, optional
        Minimum head difference (in meters) required to show contours. 
        Differences smaller than this threshold will not display contours 
        to avoid noisy patterns from numerical precision issues. Default is 0.01 m.
    
    Returns:
    --------
    fig, ax : matplotlib figure and axis objects
    head_diff : numpy.ndarray
        Array of head differences (base - scenario). Positive values indicate 
        drawdown in scenario relative to base model.
    """
    
    # Load head files
    hds_base_path = os.path.join(ws_base, f"{model_name}.hds")
    hds_scenario_path = os.path.join(ws_scenario, f"{model_name}.hds")
    
    if not os.path.exists(hds_base_path):
        raise FileNotFoundError(f"Base model heads file not found: {hds_base_path}")
    if not os.path.exists(hds_scenario_path):
        raise FileNotFoundError(f"Scenario model heads file not found: {hds_scenario_path}")
    
    # Load heads
    headobj_base = flopy.utils.HeadFile(hds_base_path)
    headobj_scenario = flopy.utils.HeadFile(hds_scenario_path)
    
    heads_base = headobj_base.get_data()[0]  # Layer 0, stress period 0
    heads_scenario = headobj_scenario.get_data()[0]  # Layer 0, stress period 0
    
    # Calculate head difference (base - scenario, so drawdown is positive)
    head_diff = heads_base - heads_scenario
    
    # Mask inactive cells
    ibound = model_base.bas6.ibound.array[0]
    head_diff_masked = np.ma.masked_where(ibound <= 0, head_diff)
    heads_base_masked = np.ma.masked_where(ibound <= 0, heads_base)
    heads_scenario_masked = np.ma.masked_where(ibound <= 0, heads_scenario)
    
    # Extract well locations from both models if show_wells is True
    wel_base = []
    wel_scenario = []
    wel_base_pumping = []
    wel_base_injection = []
    wel_scenario_pumping = []
    wel_scenario_injection = []
    
    if show_wells:
        # Extract wells from base model
        if hasattr(model_base, 'wel') and model_base.wel is not None:
            wel_data_base = model_base.wel.stress_period_data[0]  # First stress period
            for wel_cell in wel_data_base:
                layer, row, col, rate = wel_cell
                x = model_base.modelgrid.xcellcenters[row, col]
                y = model_base.modelgrid.ycellcenters[row, col]
                
                if rate < 0:  # Pumping (negative rate)
                    wel_base_pumping.append((x, y, rate))
                else:  # Injection (positive rate)
                    wel_base_injection.append((x, y, rate))
                
                wel_base.append((x, y, rate, row, col))
        
        # Extract wells from scenario model
        if hasattr(model_scenario, 'wel') and model_scenario.wel is not None:
            wel_data_scenario = model_scenario.wel.stress_period_data[0]  # First stress period
            for wel_cell in wel_data_scenario:
                layer, row, col, rate = wel_cell
                x = model_scenario.modelgrid.xcellcenters[row, col]
                y = model_scenario.modelgrid.ycellcenters[row, col]
                
                if rate < 0:  # Pumping (negative rate)
                    wel_scenario_pumping.append((x, y, rate))
                else:  # Injection (positive rate)
                    wel_scenario_injection.append((x, y, rate))
                
                wel_scenario.append((x, y, rate, row, col))
    
    # Create figure based on show_depth_plots parameter
    if show_depth_plots:
        # Create figure with 6 subplots (2 rows, 3 columns)
        fig, axes = plt.subplots(2, 3, figsize=(21, 12))
        row_title_prefix = ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']
    else:
        # Create figure with 3 subplots (1 row, 3 columns)
        fig, axes = plt.subplots(1, 3, figsize=(21, 6))
        # Ensure axes is 2D for consistent indexing
        axes = axes.reshape(1, -1)
        row_title_prefix = ['(a)', '(b)', '(c)']
    
    # Plot 1: Base model heads
    ax1 = axes[0, 0]
    pmv1 = flopy.plot.PlotMapView(model=model_base, ax=ax1)
    im1 = pmv1.plot_array(heads_base_masked, alpha=0.7, cmap='Blues')
    pmv1.plot_grid(color='gray', alpha=0.3, linewidth=0.5)
    
    # Add contours for base heads
    contour_levels_base = np.linspace(np.nanmin(heads_base_masked), 
                                     np.nanmax(heads_base_masked), 8)
    cont1 = pmv1.contour_array(heads_base_masked, levels=contour_levels_base, 
                              colors='darkblue', linewidths=1, linestyles='-')
    ax1.clabel(cont1, inline=True, fontsize=8, fmt='%.1f')
    
    # Plot wells from base model if requested
    if show_wells and wel_base_pumping:
        pump_x, pump_y, pump_rates = zip(*wel_base_pumping)
        ax1.scatter(pump_x, pump_y, c='red', s=well_marker_size, marker='o', 
                   edgecolors='white', linewidth=2, label=f'Pumping ({len(wel_base_pumping)})', 
                   zorder=5)
    
    if show_wells and wel_base_injection:
        inj_x, inj_y, inj_rates = zip(*wel_base_injection)
        ax1.scatter(inj_x, inj_y, c='green', s=well_marker_size, marker='s',
                   edgecolors='white', linewidth=2, label=f'Injection ({len(wel_base_injection)})', 
                   zorder=5)
    
    if show_wells and wel_base:
        ax1.legend(loc='upper right', fontsize=9)
    
    cbar1 = plt.colorbar(im1, ax=ax1, shrink=0.3)
    cbar1.set_label('Head (m a.s.l.)', fontsize=10)
    ax1.set_title(f'{row_title_prefix[0]} Base Model Heads', fontweight='bold')
    ax1.set_aspect('equal')
    
    # Plot 2: Scenario model heads
    ax2 = axes[0, 1]
    pmv2 = flopy.plot.PlotMapView(model=model_scenario, ax=ax2)
    im2 = pmv2.plot_array(heads_scenario_masked, alpha=0.7, cmap='Blues')
    pmv2.plot_grid(color='gray', alpha=0.3, linewidth=0.5)
    
    # Add contours for scenario heads
    contour_levels_scenario = np.linspace(np.nanmin(heads_scenario_masked), 
                                         np.nanmax(heads_scenario_masked), 8)
    cont2 = pmv2.contour_array(heads_scenario_masked, levels=contour_levels_scenario, 
                              colors='darkblue', linewidths=1, linestyles='-')
    ax2.clabel(cont2, inline=True, fontsize=8, fmt='%.2f')
    
    # Plot wells from scenario model if requested
    if show_wells and wel_scenario_pumping:
        pump_x, pump_y, pump_rates = zip(*wel_scenario_pumping)
        ax2.scatter(pump_x, pump_y, c='red', s=well_marker_size, marker='o', 
                   edgecolors='white', linewidth=2, label=f'Pumping ({len(wel_scenario_pumping)})', 
                   zorder=5)
    
    if show_wells and wel_scenario_injection:
        inj_x, inj_y, inj_rates = zip(*wel_scenario_injection)
        ax2.scatter(inj_x, inj_y, c='green', s=well_marker_size, marker='s',
                   edgecolors='white', linewidth=2, label=f'Injection ({len(wel_scenario_injection)})', 
                   zorder=5)
    
    if show_wells and wel_scenario:
        ax2.legend(loc='upper right', fontsize=9)
    
    cbar2 = plt.colorbar(im2, ax=ax2, shrink=0.3)
    cbar2.set_label('Head (m a.s.l.)', fontsize=10)
    ax2.set_title(f'{row_title_prefix[1]} {scenario_name} Model Heads', fontweight='bold')
    ax2.set_aspect('equal')
    
    # Plot 3: Head difference (base - scenario)
    ax3 = axes[0, 2]
    pmv3 = flopy.plot.PlotMapView(model=model_base, ax=ax3)
    
    # Use diverging colormap for differences
    max_diff = np.nanmax(np.abs(head_diff_masked))
    im3 = pmv3.plot_array(head_diff_masked, alpha=0.8, cmap='RdBu_r', 
                         vmin=-max_diff, vmax=max_diff)
    pmv3.plot_grid(color='gray', alpha=0.3, linewidth=0.5)
    
    # Add contours for head differences only if meaningful differences exist
    if max_diff > min_contour_diff:
        diff_levels = np.linspace(-max_diff, max_diff, 9)
        cont3 = pmv3.contour_array(head_diff_masked, levels=diff_levels, 
                                  colors='black', linewidths=1, linestyles='-')
        ax3.clabel(cont3, inline=True, fontsize=8, fmt='%.2f')
    else:
        # Add text annotation when differences are too small for meaningful contours
        ax3.text(0.5, 0.95, f'Max difference: {max_diff:.3f} m\n(Below {min_contour_diff} m threshold)', 
                transform=ax3.transAxes, ha='center', va='top', 
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                fontsize=9)
    
    # Plot wells from scenario model if requested
    if show_wells and wel_scenario_pumping:
        pump_x, pump_y, pump_rates = zip(*wel_scenario_pumping)
        ax3.scatter(pump_x, pump_y, c='red', s=well_marker_size, marker='o',
                   edgecolors='white', linewidth=2, zorder=5)
    
    if show_wells and wel_scenario_injection:
        inj_x, inj_y, inj_rates = zip(*wel_scenario_injection)
        ax3.scatter(inj_x, inj_y, c='green', s=well_marker_size, marker='s',
                   edgecolors='white', linewidth=2, zorder=5)
    
    cbar3 = plt.colorbar(im3, ax=ax3, shrink=0.3)
    cbar3.set_label('Head difference (m)', fontsize=10)
    ax3.set_title(f'{row_title_prefix[2]} Head Difference\n(Base - {scenario_name})', fontweight='bold')
    ax3.set_aspect('equal')
    
    # Only create depth plots if requested
    if show_depth_plots:
        # Get model top for depth calculations
        model_top = model_base.dis.top.array
        
        # Calculate depth to water table for both models
        depth_base = model_top - heads_base
        depth_scenario = model_top - heads_scenario
        
        # Calculate difference in depth to water table (depth_base - depth_scenario)
        # Positive values mean shallower depth in scenario model (water table rise)
        # Negative values mean greater depth in scenario model (drawdown effect)
        # This is consistent with head_diff = heads_base - heads_scenario
        depth_diff = depth_base - depth_scenario
        
        # Mask inactive cells for depth arrays
        depth_base_masked = np.ma.masked_where(ibound <= 0, depth_base)
        depth_scenario_masked = np.ma.masked_where(ibound <= 0, depth_scenario)
        depth_diff_masked = np.ma.masked_where(ibound <= 0, depth_diff)
        
        # Plot 4: Depth to water table - Base model
        ax4 = axes[1, 0]
        pmv4 = flopy.plot.PlotMapView(model=model_base, ax=ax4)
        im4 = pmv4.plot_array(depth_base_masked, alpha=0.7, cmap='YlOrRd')
        pmv4.plot_grid(color='gray', alpha=0.3, linewidth=0.5)
        
        # Add contours for depth to water table
        contour_levels_depth_base = np.linspace(np.nanmin(depth_base_masked), 
                                               np.nanmax(depth_base_masked), 8)
        cont4 = pmv4.contour_array(depth_base_masked, levels=contour_levels_depth_base, 
                                  colors='darkred', linewidths=1, linestyles='-')
        ax4.clabel(cont4, inline=True, fontsize=8, fmt='%.1f')
        
        cbar4 = plt.colorbar(im4, ax=ax4, shrink=0.3)
        cbar4.set_label('Depth to WT (m)', fontsize=10)
        ax4.set_title(f'{row_title_prefix[3]} Base Model\nDepth to Water Table', fontweight='bold')
        ax4.set_aspect('equal')
        
        # Plot 5: Depth to water table - Scenario model
        ax5 = axes[1, 1]
        pmv5 = flopy.plot.PlotMapView(model=model_scenario, ax=ax5)
        im5 = pmv5.plot_array(depth_scenario_masked, alpha=0.7, cmap='YlOrRd')
        pmv5.plot_grid(color='gray', alpha=0.3, linewidth=0.5)
        
        # Add contours for depth to water table
        contour_levels_depth_scenario = np.linspace(np.nanmin(depth_scenario_masked), 
                                                   np.nanmax(depth_scenario_masked), 8)
        cont5 = pmv5.contour_array(depth_scenario_masked, levels=contour_levels_depth_scenario, 
                                  colors='darkred', linewidths=1, linestyles='-')
        ax5.clabel(cont5, inline=True, fontsize=8, fmt='%.2f')
        
        # Plot wells from scenario model if requested
        if show_wells and wel_scenario_pumping:
            pump_x, pump_y, pump_rates = zip(*wel_scenario_pumping)
            ax5.scatter(pump_x, pump_y, c='red', s=well_marker_size, marker='o', 
                       edgecolors='white', linewidth=2, label=f'Pumping ({len(wel_scenario_pumping)})', 
                       zorder=5)
        
        if show_wells and wel_scenario_injection:
            inj_x, inj_y, inj_rates = zip(*wel_scenario_injection)
            ax5.scatter(inj_x, inj_y, c='green', s=well_marker_size, marker='s',
                       edgecolors='white', linewidth=2, label=f'Injection ({len(wel_scenario_injection)})', 
                       zorder=5)
        
        if show_wells and wel_scenario:
            ax5.legend(loc='upper right', fontsize=9)

        cbar5 = plt.colorbar(im5, ax=ax5, shrink=0.3)
        cbar5.set_label('Depth to WT (m)', fontsize=10)
        ax5.set_title(f'{row_title_prefix[4]} {scenario_name} Model\nDepth to Water Table', fontweight='bold')
        ax5.set_aspect('equal')
        
        # Plot 6: Difference in depth to water table
        ax6 = axes[1, 2]
        pmv6 = flopy.plot.PlotMapView(model=model_base, ax=ax6)
        
        # Use diverging colormap for depth differences
        max_depth_diff = np.nanmax(np.abs(depth_diff_masked))
        im6 = pmv6.plot_array(depth_diff_masked, alpha=0.8, cmap='RdBu', 
                             vmin=-max_depth_diff, vmax=max_depth_diff)
        pmv6.plot_grid(color='gray', alpha=0.3, linewidth=0.5)
        
        # Add contours for depth differences only if meaningful differences exist
        if max_depth_diff > min_contour_diff:
            depth_diff_levels = np.linspace(-max_depth_diff, max_depth_diff, 9)
            cont6 = pmv6.contour_array(depth_diff_masked, levels=depth_diff_levels, 
                                      colors='black', linewidths=1, linestyles='-')
            ax6.clabel(cont6, inline=True, fontsize=8, fmt='%.2f')
        else:
            # Add text annotation when differences are too small for meaningful contours
            ax6.text(0.5, 0.95, f'Max difference: {max_depth_diff:.3f} m\n(Below {min_contour_diff} m threshold)', 
                    transform=ax6.transAxes, ha='center', va='top', 
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                    fontsize=9)
        
        # Plot wells from scenario model if requested
        if show_wells and wel_scenario_pumping:
            pump_x, pump_y, pump_rates = zip(*wel_scenario_pumping)
            ax6.scatter(pump_x, pump_y, c='red', s=well_marker_size, marker='o',
                       edgecolors='white', linewidth=2, zorder=5)
        
        if show_wells and wel_scenario_injection:
            inj_x, inj_y, inj_rates = zip(*wel_scenario_injection)
            ax6.scatter(inj_x, inj_y, c='green', s=well_marker_size, marker='s',
                       edgecolors='white', linewidth=2, zorder=5)
        
        cbar6 = plt.colorbar(im6, ax=ax6, shrink=0.3)
        cbar6.set_label('Change in Depth to WT (m)', fontsize=10)
        ax6.set_title(f'{row_title_prefix[5]} Change in Depth to WT\n(Base - {scenario_name})', fontweight='bold')
        ax6.set_aspect('equal')
    
    # Overall title
    plot_type = "Head and Depth to Water Table Analysis" if show_depth_plots else "Head Analysis"
    fig.suptitle(f'Groundwater {plot_type}\nModel: {model_name} (Base vs {scenario_name})', 
                 fontsize=16, fontweight='bold')
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Head difference plot saved to: {save_path}")
    
    plt.show()

    return fig, axes, head_diff_masked


def compare_budget(ws_base, ws_scenario, model_name, threshold=100.0, save_path=None, 
                  scenario_name="Scenario", figsize=(16, 10)):
    """
    Compare groundwater budgets between base model and scenario model.
    
    Parameters:
    -----------
    ws_base : str
        Workspace path for base model
    ws_scenario : str
        Workspace path for scenario model
    model_name : str
        Model name for file naming
    threshold : float, optional
        Threshold above which values are rounded to integers (default: 100.0)
    save_path : str, optional
        Path to save the figure
    scenario_name : str, optional
        Name for the scenario model in plot titles. Default is "Scenario".
    figsize : tuple, optional
        Figure size (width, height). Default is (16, 10).
        
    Returns:
    --------
    fig, axes : matplotlib figure and axes objects
    budget_comparison_df : pandas.DataFrame
        DataFrame containing budget comparison data
    """
    import os
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import flopy.utils
    
    # Load budget data for both models
    try:
        # Base model budget
        list_budget_base = flopy.utils.MfListBudget(
            os.path.join(ws_base, f'{model_name}.list'))
        budget_base = list_budget_base.get_budget()[-1]  # Last time step
        df_base = pd.DataFrame(budget_base).T
        
        # Scenario model budget
        list_budget_scenario = flopy.utils.MfListBudget(
            os.path.join(ws_scenario, f'{model_name}.list'))
        budget_scenario = list_budget_scenario.get_budget()[-1]  # Last time step
        df_scenario = pd.DataFrame(budget_scenario).T
        
        print(f"Budget data loaded successfully for both models")
        
    except Exception as e:
        print(f"Error loading budget data: {e}")
        return None, None, None
    
    # Process both dataframes using the same logic as visualize_budget
    def process_budget_df(df, name):
        # Identify _IN, _OUT, and summary rows
        in_rows = df.index[df.index.str.endswith('_IN')]
        out_rows = df.index[df.index.str.endswith('_OUT')]
        summary_rows = df.index[~(df.index.str.endswith('_IN') | df.index.str.endswith('_OUT'))]
        
        # Filter summary rows to IN-OUT and PERCENT_DISCREPANCY
        summary_rows = summary_rows[summary_rows.str.contains('IN-OUT|PERCENT_DISCREPANCY')]
        
        # Concatenate in desired order
        df_reordered = pd.concat([df.loc[in_rows], df.loc[out_rows], df.loc[summary_rows]])
        
        # Check if most values are above threshold for conditional rounding
        numeric_values = df_reordered.select_dtypes(include=[np.number]).values.flatten()
        numeric_values = numeric_values[~np.isnan(numeric_values)]  # Remove NaN values
        
        if len(numeric_values) > 0:
            above_threshold_count = np.sum(np.abs(numeric_values) >= threshold)
            total_count = len(numeric_values)
            
            if above_threshold_count > total_count / 2:  # More than half are above threshold
                # Round to integers for large values
                df_reordered = df_reordered.round(0).astype(int, errors='ignore')
                unit_label = "m³/day (rounded to integers)"
            else:
                # Keep decimal places for smaller values
                df_reordered = df_reordered.round(2)
                unit_label = "m³/day"
        else:
            df_reordered = df_reordered.round(2)
            unit_label = "m³/day"
        
        # Remove columns that are all zeros (if any exist)
        df_clean = df_reordered.loc[:, (df_reordered != 0).any(axis=0)]
        
        return df_clean, in_rows, out_rows, summary_rows, unit_label
    
    # Process both models
    df_base_clean, in_rows_base, out_rows_base, summary_rows_base, unit_label_base = process_budget_df(df_base, "Base")
    df_scenario_clean, in_rows_scenario, out_rows_scenario, summary_rows_scenario, unit_label_scenario = process_budget_df(df_scenario, scenario_name)
    
    # Create comparison dataframe
    # Get all unique budget terms from both models
    all_terms = sorted(set(df_base_clean.index.tolist() + df_scenario_clean.index.tolist()))
    
    comparison_data = []
    for term in all_terms:
        base_value = df_base_clean.loc[term].iloc[0] if term in df_base_clean.index else 0
        scenario_value = df_scenario_clean.loc[term].iloc[0] if term in df_scenario_clean.index else 0
        difference = scenario_value - base_value
        
        # Calculate percentage change (avoid division by zero)
        if base_value != 0:
            percent_change = (difference / abs(base_value)) * 100
        else:
            percent_change = np.inf if difference != 0 else 0
            
        comparison_data.append({
            'Budget_Term': term,
            'Base_Model': base_value,
            f'{scenario_name}_Model': scenario_value,
            'Difference': difference,
            'Percent_Change': percent_change
        })
    
    budget_comparison_df = pd.DataFrame(comparison_data)
    
    # Create visualization
    fig, axes = plt.subplots(2, 2, figsize=figsize)
    
    # Separate inflows, outflows, and summary terms for plotting
    inflow_terms = [term for term in all_terms if term.endswith('_IN')]
    outflow_terms = [term for term in all_terms if term.endswith('_OUT')]
    summary_terms = [term for term in all_terms if not (term.endswith('_IN') or term.endswith('_OUT'))]
    
    # Plot 1: Inflow comparison
    ax1 = axes[0, 0]
    if inflow_terms:
        inflow_data = budget_comparison_df[budget_comparison_df['Budget_Term'].isin(inflow_terms)]
        
        x_pos = np.arange(len(inflow_terms))
        width = 0.35
        
        bars1 = ax1.bar(x_pos - width/2, inflow_data['Base_Model'], width, 
                       label='Base Model', alpha=0.8, color='skyblue')
        bars2 = ax1.bar(x_pos + width/2, inflow_data[f'{scenario_name}_Model'], width,
                       label=f'{scenario_name} Model', alpha=0.8, color='lightcoral')
        
        ax1.set_xlabel('Budget Terms')
        ax1.set_ylabel('Flow Rate (m³/day)')
        ax1.set_title('(a) Inflow Comparison', fontweight='bold')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels([term.replace('_IN', '') for term in inflow_terms], rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            if abs(height) >= threshold:
                ax1.annotate(f'{height:,.0f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
            else:
                ax1.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
        
        for bar in bars2:
            height = bar.get_height()
            if abs(height) >= threshold:
                ax1.annotate(f'{height:,.0f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
            else:
                ax1.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
    else:
        ax1.text(0.5, 0.5, 'No inflow terms found', ha='center', va='center', transform=ax1.transAxes)
        ax1.set_title('(a) Inflow Comparison', fontweight='bold')
    
    # Plot 2: Outflow comparison
    ax2 = axes[0, 1]
    if outflow_terms:
        outflow_data = budget_comparison_df[budget_comparison_df['Budget_Term'].isin(outflow_terms)]
        
        x_pos = np.arange(len(outflow_terms))
        
        bars1 = ax2.bar(x_pos - width/2, abs(outflow_data['Base_Model']), width,
                       label='Base Model', alpha=0.8, color='lightgreen')
        bars2 = ax2.bar(x_pos + width/2, abs(outflow_data[f'{scenario_name}_Model']), width,
                       label=f'{scenario_name} Model', alpha=0.8, color='orange')
        
        ax2.set_xlabel('Budget Terms')
        ax2.set_ylabel('Flow Rate (m³/day)')
        ax2.set_title('(b) Outflow Comparison (Absolute Values)', fontweight='bold')
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels([term.replace('_OUT', '') for term in outflow_terms], rotation=45, ha='right')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for i, bar in enumerate(bars1):
            height = bar.get_height()
            if abs(height) >= threshold:
                ax2.annotate(f'{height:,.0f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
            else:
                ax2.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
        
        for i, bar in enumerate(bars2):
            height = bar.get_height()
            if abs(height) >= threshold:
                ax2.annotate(f'{height:,.0f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
            else:
                ax2.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
    else:
        ax2.text(0.5, 0.5, 'No outflow terms found', ha='center', va='center', transform=ax2.transAxes)
        ax2.set_title('(b) Outflow Comparison (Absolute Values)', fontweight='bold')
    
    # Plot 3: Budget differences
    ax3 = axes[1, 0]
    
    # Filter out summary terms for the difference plot and focus on flow terms
    flow_terms = inflow_terms + outflow_terms
    if flow_terms:
        diff_data = budget_comparison_df[budget_comparison_df['Budget_Term'].isin(flow_terms)]
        
        # Create horizontal bar chart for differences
        y_pos = np.arange(len(flow_terms))
        differences = diff_data['Difference'].values
        
        # Color bars based on positive/negative difference
        colors = ['green' if diff > 0 else 'red' for diff in differences]
        
        bars = ax3.barh(y_pos, differences, color=colors, alpha=0.7)
        
        ax3.set_xlabel('Difference (m³/day)')
        ax3.set_ylabel('Budget Terms')
        ax3.set_title(f'(c) Budget Differences\n({scenario_name} - Base)', fontweight='bold')
        ax3.set_yticks(y_pos)
        ax3.set_yticklabels([term.replace('_IN', '').replace('_OUT', '') for term in flow_terms])
        ax3.grid(True, alpha=0.3, axis='x')
        ax3.axvline(x=0, color='black', linewidth=1)
        
        # Add value labels on bars
        for i, bar in enumerate(bars):
            width = bar.get_width()
            if abs(width) >= threshold:
                ax3.annotate(f'{width:,.0f}', xy=(width, bar.get_y() + bar.get_height()/2),
                           xytext=(5 if width > 0 else -5, 0), textcoords="offset points", 
                           ha='left' if width > 0 else 'right', va='center', fontsize=8)
            else:
                ax3.annotate(f'{width:.1f}', xy=(width, bar.get_y() + bar.get_height()/2),
                           xytext=(5 if width > 0 else -5, 0), textcoords="offset points", 
                           ha='left' if width > 0 else 'right', va='center', fontsize=8)
    else:
        ax3.text(0.5, 0.5, 'No flow terms found', ha='center', va='center', transform=ax3.transAxes)
        ax3.set_title(f'(c) Budget Differences\n({scenario_name} - Base)', fontweight='bold')
    
    # Plot 4: Summary table
    ax4 = axes[1, 1]
    ax4.axis('off')
    
    # Create summary statistics
    if flow_terms:
        total_inflow_base = budget_comparison_df[budget_comparison_df['Budget_Term'].isin(inflow_terms)]['Base_Model'].sum()
        total_outflow_base = abs(budget_comparison_df[budget_comparison_df['Budget_Term'].isin(outflow_terms)]['Base_Model'].sum())
        total_inflow_scenario = budget_comparison_df[budget_comparison_df['Budget_Term'].isin(inflow_terms)][f'{scenario_name}_Model'].sum()
        total_outflow_scenario = abs(budget_comparison_df[budget_comparison_df['Budget_Term'].isin(outflow_terms)][f'{scenario_name}_Model'].sum())
        
        net_flow_base = total_inflow_base - total_outflow_base
        net_flow_scenario = total_inflow_scenario - total_outflow_scenario
        net_flow_change = net_flow_scenario - net_flow_base
        
        summary_text = f"""Budget Summary Comparison

Base Model:
  Total Inflow:   {total_inflow_base:>10,.0f} m³/day
  Total Outflow:  {total_outflow_base:>10,.0f} m³/day
  Net Flow:       {net_flow_base:>10,.0f} m³/day

{scenario_name} Model:
  Total Inflow:   {total_inflow_scenario:>10,.0f} m³/day
  Total Outflow:  {total_outflow_scenario:>10,.0f} m³/day
  Net Flow:       {net_flow_scenario:>10,.0f} m³/day

Changes:
  Inflow Change:  {total_inflow_scenario - total_inflow_base:>10,.0f} m³/day
  Outflow Change: {total_outflow_scenario - total_outflow_base:>10,.0f} m³/day
  Net Flow Change: {net_flow_change:>10,.0f} m³/day
        """
        
        ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes, fontsize=10,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        ax4.set_title('(d) Summary Statistics', fontweight='bold')
    else:
        ax4.text(0.5, 0.5, 'No flow terms available for summary', ha='center', va='center', 
                transform=ax4.transAxes)
        ax4.set_title('(d) Summary Statistics', fontweight='bold')
    
    # Overall title
    fig.suptitle(f'Groundwater Budget Comparison\n{model_name}: Base vs {scenario_name}', 
                 fontsize=16, fontweight='bold')
    
    plt.tight_layout()
    
    # Print comparison table
    print(f"\nBudget Comparison Table ({unit_label_base}):")
    print("=" * 80)
    
    # Filter and display in organized manner
    if inflow_terms:
        print("\n📈 INFLOWS:")
        print("-" * 50)
        inflow_comparison = budget_comparison_df[budget_comparison_df['Budget_Term'].isin(inflow_terms)]
        for _, row in inflow_comparison.iterrows():
            term_clean = row['Budget_Term'].replace('_IN', '')
            print(f"{term_clean:20s} | Base: {row['Base_Model']:>10,.0f} | {scenario_name}: {row[f'{scenario_name}_Model']:>10,.0f} | Diff: {row['Difference']:>10,.0f}")
    
    if outflow_terms:
        print("\n📉 OUTFLOWS:")
        print("-" * 50)
        outflow_comparison = budget_comparison_df[budget_comparison_df['Budget_Term'].isin(outflow_terms)]
        for _, row in outflow_comparison.iterrows():
            term_clean = row['Budget_Term'].replace('_OUT', '')
            print(f"{term_clean:20s} | Base: {row['Base_Model']:>10,.0f} | {scenario_name}: {row[f'{scenario_name}_Model']:>10,.0f} | Diff: {row['Difference']:>10,.0f}")
    
    if summary_terms:
        print("\n📊 SUMMARY TERMS:")
        print("-" * 50)
        summary_comparison = budget_comparison_df[budget_comparison_df['Budget_Term'].isin(summary_terms)]
        for _, row in summary_comparison.iterrows():
            print(f"{row['Budget_Term']:20s} | Base: {row['Base_Model']:>10,.2f} | {scenario_name}: {row[f'{scenario_name}_Model']:>10,.2f} | Diff: {row['Difference']:>10,.2f}")
    
    # Save figure if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\nBudget comparison plot saved to: {save_path}")
    
    plt.show()
    
    return fig, axes, budget_comparison_df


def plot_chd_comparison(model_base, model_scenario, figsize=(15, 6), buffer_cells=5):
    """
    Plot CHD boundary values for base and scenario models side by side.
    
    Parameters:
    -----------
    model_base : flopy.modflow.Modflow
        Base model with original CHD conditions
    model_scenario : flopy.modflow.Modflow  
        Scenario model with modified CHD conditions
    figsize : tuple, optional
        Figure size (width, height) in inches
    buffer_cells : int, optional
        Number of cells to add as buffer around CHD extent for zooming
        
    Returns:
    --------
    fig, axes : matplotlib figure and axes objects
    """
    import matplotlib.pyplot as plt
    import numpy as np
    import flopy
    
    # Check if both models have CHD packages
    if model_base.chd is None:
        print("Warning: Base model has no CHD package")
        return None, None
    if model_scenario.chd is None:
        print("Warning: Scenario model has no CHD package")  
        return None, None
        
    # Extract CHD data from both models
    chd_base = model_base.chd.stress_period_data[0]
    chd_scenario = model_scenario.chd.stress_period_data[0]
    
    print(f"Base model CHD cells: {len(chd_base)}")
    print(f"Scenario model CHD cells: {len(chd_scenario)}")
    
    # Get ibound arrays for inactive cells
    ibound_base = model_base.bas6.ibound.array[0]  # Top layer
    ibound_scenario = model_scenario.bas6.ibound.array[0]  # Top layer
    
    # Create arrays to hold CHD head values
    chd_array_base = np.full((model_base.nrow, model_base.ncol), np.nan)
    chd_array_scenario = np.full((model_scenario.nrow, model_scenario.ncol), np.nan)
    
    # Fill arrays with head values (using end head values)
    chd_rows, chd_cols = [], []
    for chd_cell in chd_base:
        layer, row, col, head_start, head_end = chd_cell
        chd_array_base[row, col] = head_end
        chd_rows.append(row)
        chd_cols.append(col)
        
    for chd_cell in chd_scenario:
        layer, row, col, head_start, head_end = chd_cell
        chd_array_scenario[row, col] = head_end
        
    # Determine zoom extent based on CHD cell locations
    min_row = max(0, min(chd_rows) - buffer_cells)
    max_row = min(model_base.nrow, max(chd_rows) + buffer_cells + 1)
    min_col = max(0, min(chd_cols) - buffer_cells)  
    max_col = min(model_base.ncol, max(chd_cols) + buffer_cells + 1)
    
    # Extract zoomed arrays
    chd_zoom_base = chd_array_base[min_row:max_row, min_col:max_col]
    chd_zoom_scenario = chd_array_scenario[min_row:max_row, min_col:max_col]
    ibound_zoom_base = ibound_base[min_row:max_row, min_col:max_col]
    ibound_zoom_scenario = ibound_scenario[min_row:max_row, min_col:max_col]
    
    # Determine common color scale
    all_values = np.concatenate([
        chd_zoom_base[~np.isnan(chd_zoom_base)],
        chd_zoom_scenario[~np.isnan(chd_zoom_scenario)]
    ])
    vmin, vmax = np.min(all_values), np.max(all_values)
    
    # Create figure with subplots - adjust width ratios to make room for colorbar
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    
    # Plot base model CHD
    ax1 = axes[0]
    im1 = ax1.imshow(chd_zoom_base, cmap='viridis', vmin=vmin, vmax=vmax, 
                     aspect='equal', origin='upper')
    
    # Add inactive cells as grey semi-transparent overlay
    inactive_mask_base = np.where(ibound_zoom_base == 0, 1, np.nan)
    ax1.imshow(inactive_mask_base, cmap='gray', alpha=0.5, aspect='equal', origin='upper')
    
    ax1.set_title('Base Model CHD Head Values [m]', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Column Index')
    ax1.set_ylabel('Row Index')
    
    # Add grid lines
    ax1.set_xticks(np.arange(-0.5, chd_zoom_base.shape[1], 1), minor=True)
    ax1.set_yticks(np.arange(-0.5, chd_zoom_base.shape[0], 1), minor=True)
    ax1.grid(which='minor', color='white', linestyle='-', linewidth=0.5, alpha=0.3)
    
    # Adjust tick labels to show actual grid indices
    tick_step_x = max(1, chd_zoom_base.shape[1]//10)
    tick_step_y = max(1, chd_zoom_base.shape[0]//10)
    ax1.set_xticks(range(0, chd_zoom_base.shape[1], tick_step_x))
    ax1.set_xticklabels([str(min_col + i) for i in range(0, chd_zoom_base.shape[1], tick_step_x)])
    ax1.set_yticks(range(0, chd_zoom_base.shape[0], tick_step_y))
    ax1.set_yticklabels([str(min_row + i) for i in range(0, chd_zoom_base.shape[0], tick_step_y)])
    
    # Plot scenario model CHD  
    ax2 = axes[1]
    im2 = ax2.imshow(chd_zoom_scenario, cmap='viridis', vmin=vmin, vmax=vmax,
                     aspect='equal', origin='upper')
    
    # Add inactive cells as grey semi-transparent overlay
    inactive_mask_scenario = np.where(ibound_zoom_scenario <= 0, 1, np.nan)
    ax2.imshow(inactive_mask_scenario, cmap='gray', alpha=0.5, aspect='equal', origin='upper')
    
    ax2.set_title('Scenario Model CHD Head Values [m]', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Column Index')
    ax2.set_ylabel('Row Index')
    
    # Add grid lines
    ax2.set_xticks(np.arange(-0.5, chd_zoom_scenario.shape[1], 1), minor=True)
    ax2.set_yticks(np.arange(-0.5, chd_zoom_scenario.shape[0], 1), minor=True)
    ax2.grid(which='minor', color='white', linestyle='-', linewidth=0.5, alpha=0.3)
    
    # Adjust tick labels to show actual grid indices
    ax2.set_xticks(range(0, chd_zoom_scenario.shape[1], tick_step_x))
    ax2.set_xticklabels([str(min_col + i) for i in range(0, chd_zoom_scenario.shape[1], tick_step_x)])
    ax2.set_yticks(range(0, chd_zoom_scenario.shape[0], tick_step_y))
    ax2.set_yticklabels([str(min_row + i) for i in range(0, chd_zoom_scenario.shape[0], tick_step_y)])
    
    # Add colorbar to the right of the right subplot
    cbar = plt.colorbar(im2, ax=ax2, orientation='vertical', shrink=0.8, pad=0.05)
    cbar.set_label('Head Value [m]', fontsize=12)
    
    fig.suptitle('CHD Boundary Conditions Comparison', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    return fig, axes


