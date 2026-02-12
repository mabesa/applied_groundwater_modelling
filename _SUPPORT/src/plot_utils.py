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


# =============================================================================
# DISV Grid Support Functions (MODFLOW 6 / Unstructured Grids)
# =============================================================================

def quick_model_plot(
    modelgrid,
    array,
    boundary_gdf=None,
    title="",
    cmap='viridis',
    colorbar_label="",
    vmin=None,
    vmax=None,
    figsize=(10, 10),
    show_grid=True,
    grid_alpha=0.3,
    grid_linewidth=0.5,
    ax=None,
):
    """
    Standard model array visualization with consistent styling.

    Works with both StructuredGrid and VertexGrid (DISV) grids from FloPy.
    Provides a simple, consistent interface for visualizing model arrays.

    Parameters
    ----------
    modelgrid : flopy.discretization.StructuredGrid or VertexGrid
        FloPy model grid object. Supports both structured and DISV grids.
    array : numpy.ndarray
        Array of values to plot. Shape should match the grid:
        - For VertexGrid: 1D array of length ncpl, or 2D (nlay, ncpl)
        - For StructuredGrid: 2D (nrow, ncol) or 3D (nlay, nrow, ncol)
    boundary_gdf : geopandas.GeoDataFrame, optional
        Optional boundary polygon to overlay on the plot.
    title : str, optional
        Plot title. Default: "".
    cmap : str or matplotlib.colors.Colormap, optional
        Colormap for the array values. Default: 'viridis'.
    colorbar_label : str, optional
        Label for the colorbar. Default: "".
    vmin : float, optional
        Minimum value for color scaling. If None, uses array minimum.
    vmax : float, optional
        Maximum value for color scaling. If None, uses array maximum.
    figsize : tuple, optional
        Figure size (width, height) in inches. Default: (10, 10).
    show_grid : bool, optional
        Whether to show grid lines. Default: True.
    grid_alpha : float, optional
        Transparency of grid lines. Default: 0.3.
    grid_linewidth : float, optional
        Width of grid lines. Default: 0.5.
    ax : matplotlib.axes.Axes, optional
        Existing axes to plot on. If None, creates new figure/axes.

    Returns
    -------
    fig : matplotlib.figure.Figure
        The figure object.
    ax : matplotlib.axes.Axes
        The axes object.

    Examples
    --------
    >>> # Plot hydraulic conductivity on DISV grid
    >>> fig, ax = quick_model_plot(
    ...     modelgrid, hk_array,
    ...     title="Hydraulic Conductivity",
    ...     colorbar_label="K (m/day)",
    ...     cmap='YlOrBr'
    ... )

    >>> # Plot heads with custom range
    >>> fig, ax = quick_model_plot(
    ...     modelgrid, heads,
    ...     title="Simulated Heads",
    ...     colorbar_label="Head (m a.s.l.)",
    ...     vmin=380, vmax=420
    ... )
    """
    from flopy.discretization import VertexGrid, StructuredGrid

    # Create figure if needed
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.get_figure()

    # Flatten array if needed
    array = np.asarray(array)
    if array.ndim > 2:
        array = array[0]  # Take first layer for 3D arrays
    if array.ndim == 2 and isinstance(modelgrid, VertexGrid):
        array = array.flatten()

    # Create PlotMapView
    pmv = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax)

    # Plot the array
    plot_kwargs = {'cmap': cmap}
    if vmin is not None:
        plot_kwargs['vmin'] = vmin
    if vmax is not None:
        plot_kwargs['vmax'] = vmax

    # Use plot_array which works for both grid types
    im = pmv.plot_array(array, **plot_kwargs)

    # Plot grid if requested
    if show_grid:
        pmv.plot_grid(alpha=grid_alpha, linewidth=grid_linewidth, color='gray')

    # Plot boundary if provided
    if boundary_gdf is not None:
        boundary_gdf.boundary.plot(ax=ax, color='black', linewidth=1.5)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
    if colorbar_label:
        cbar.set_label(colorbar_label)

    # Set title and labels
    if title:
        ax.set_title(title, fontweight='bold')
    ax.set_xlabel('Easting (m)')
    ax.set_ylabel('Northing (m)')
    ax.set_aspect('equal')

    return fig, ax


def plot_model_results_summary(
    gwf,
    sim,
    boundary_gdf=None,
    figsize=(16, 14),
    head_cmap='Blues',
    save_path=None,
):
    """
    Create 4-panel summary of MODFLOW 6 model results.

    Displays heads, water budget, flow vectors, and a combined view.
    Works with both structured and DISV (unstructured) grids.

    Parameters
    ----------
    gwf : flopy.mf6.ModflowGwf
        MODFLOW 6 groundwater flow model object.
    sim : flopy.mf6.MFSimulation
        MODFLOW 6 simulation object.
    boundary_gdf : geopandas.GeoDataFrame, optional
        Optional boundary polygon to overlay on plots.
    figsize : tuple, optional
        Figure size (width, height) in inches. Default: (16, 14).
    head_cmap : str, optional
        Colormap for head distribution. Default: 'Blues'.
    save_path : str, optional
        Path to save the figure. If None, figure is not saved.

    Returns
    -------
    fig : matplotlib.figure.Figure
        The figure object.
    axes : numpy.ndarray
        Array of axes objects.

    Notes
    -----
    The four panels show:
    1. Head distribution with contours
    2. Water budget summary (bar chart)
    3. Flow vectors (quiver plot)
    4. Combined heads + vectors view

    Requires the model to have been run successfully before calling.

    Examples
    --------
    >>> # Run simulation first
    >>> sim.run_simulation()
    >>>
    >>> # Create summary plot
    >>> fig, axes = plot_model_results_summary(gwf, sim)
    """
    from flopy.discretization import VertexGrid

    # Get model grid
    modelgrid = gwf.modelgrid
    is_disv = isinstance(modelgrid, VertexGrid)

    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=figsize)

    # --- Panel 1: Head distribution ---
    ax1 = axes[0, 0]

    try:
        # Get head data
        head = gwf.output.head().get_data()
        if head.ndim == 3:
            head = head[0]  # First layer

        # Mask inactive cells
        try:
            idomain = gwf.dis.idomain.array if hasattr(gwf.dis, 'idomain') else None
            if idomain is None and hasattr(gwf, 'disv'):
                idomain = gwf.disv.idomain.array
            if idomain is not None:
                if idomain.ndim == 3:
                    idomain = idomain[0]
                head = np.where(idomain <= 0, np.nan, head)
        except Exception:
            pass

        # Plot heads
        pmv1 = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax1)
        im1 = pmv1.plot_array(head, cmap=head_cmap)
        pmv1.plot_grid(alpha=0.2, linewidth=0.3)

        # Add contours
        try:
            levels = np.linspace(np.nanmin(head), np.nanmax(head), 10)
            cont1 = pmv1.contour_array(head, levels=levels, colors='darkblue', linewidths=0.8)
            ax1.clabel(cont1, inline=True, fontsize=8, fmt='%.1f')
        except Exception:
            pass

        cbar1 = plt.colorbar(im1, ax=ax1, shrink=0.6, pad=0.02)
        cbar1.set_label('Head (m a.s.l.)')
        ax1.set_title('(a) Head Distribution', fontweight='bold')
        ax1.set_xlabel('Easting (m)')
        ax1.set_ylabel('Northing (m)')
        ax1.set_aspect('equal')

    except Exception as e:
        ax1.text(0.5, 0.5, f'Could not load heads:\n{e}',
                ha='center', va='center', transform=ax1.transAxes)
        ax1.set_title('(a) Head Distribution', fontweight='bold')

    # --- Panel 2: Water budget ---
    ax2 = axes[0, 1]

    try:
        # Get budget data
        budget = gwf.output.budget()

        # Get unique record names
        records = budget.get_unique_record_names()

        # Extract budget terms
        budget_data = {}
        for rec in records:
            rec_name = rec.decode('utf-8').strip() if isinstance(rec, bytes) else rec.strip()
            data = budget.get_data(text=rec_name)
            if len(data) > 0:
                # Sum all values for this term
                total = np.sum(data[-1]['q'])  # Last time step
                budget_data[rec_name] = total

        # Separate inflows and outflows
        inflows = {k: v for k, v in budget_data.items() if v > 0}
        outflows = {k: -v for k, v in budget_data.items() if v < 0}  # Make positive for plotting

        # Create bar chart
        all_terms = list(inflows.keys()) + list(outflows.keys())
        all_values = list(inflows.values()) + [-v for v in outflows.values()]
        colors = ['green'] * len(inflows) + ['red'] * len(outflows)

        if all_terms:
            y_pos = np.arange(len(all_terms))
            bars = ax2.barh(y_pos, all_values, color=colors, alpha=0.7)
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(all_terms, fontsize=9)
            ax2.axvline(x=0, color='black', linewidth=1)
            ax2.set_xlabel('Flow Rate (m³/day)')

            # Add value labels
            for bar, val in zip(bars, all_values):
                width = bar.get_width()
                ax2.annotate(f'{val:,.0f}',
                           xy=(width, bar.get_y() + bar.get_height()/2),
                           xytext=(3 if width > 0 else -3, 0),
                           textcoords="offset points",
                           ha='left' if width > 0 else 'right',
                           va='center', fontsize=8)
        else:
            ax2.text(0.5, 0.5, 'No budget data available',
                    ha='center', va='center', transform=ax2.transAxes)

        ax2.set_title('(b) Water Budget', fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='x')

    except Exception as e:
        ax2.text(0.5, 0.5, f'Could not load budget:\n{e}',
                ha='center', va='center', transform=ax2.transAxes)
        ax2.set_title('(b) Water Budget', fontweight='bold')

    # --- Panel 3: Flow vectors ---
    ax3 = axes[1, 0]

    try:
        pmv3 = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax3)

        # Plot grid background
        pmv3.plot_grid(alpha=0.3, linewidth=0.3, color='gray')

        # Try to get specific discharge if available
        try:
            spdis = budget.get_data(text='DATA-SPDIS')
            if len(spdis) > 0:
                qx = spdis[-1]['qx']
                qy = spdis[-1]['qy']
                if qx.ndim == 3:
                    qx = qx[0]
                    qy = qy[0]

                # Plot vectors using quiver
                pmv3.plot_vector(qx, qy, normalize=True, color='blue', alpha=0.7)
                ax3.set_title('(c) Flow Vectors (Specific Discharge)', fontweight='bold')
            else:
                ax3.text(0.5, 0.5, 'No specific discharge data\n(enable SAVE_SPECIFIC_DISCHARGE)',
                        ha='center', va='center', transform=ax3.transAxes)
                ax3.set_title('(c) Flow Vectors', fontweight='bold')
        except Exception:
            ax3.text(0.5, 0.5, 'Flow vectors not available',
                    ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('(c) Flow Vectors', fontweight='bold')

        ax3.set_xlabel('Easting (m)')
        ax3.set_ylabel('Northing (m)')
        ax3.set_aspect('equal')

    except Exception as e:
        ax3.text(0.5, 0.5, f'Could not plot vectors:\n{e}',
                ha='center', va='center', transform=ax3.transAxes)
        ax3.set_title('(c) Flow Vectors', fontweight='bold')

    # --- Panel 4: Combined view ---
    ax4 = axes[1, 1]

    try:
        pmv4 = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax4)

        # Plot heads
        im4 = pmv4.plot_array(head, cmap=head_cmap, alpha=0.7)

        # Add contours
        try:
            cont4 = pmv4.contour_array(head, levels=levels, colors='darkblue', linewidths=0.8)
            ax4.clabel(cont4, inline=True, fontsize=8, fmt='%.1f')
        except Exception:
            pass

        # Add boundary if provided
        if boundary_gdf is not None:
            boundary_gdf.boundary.plot(ax=ax4, color='black', linewidth=1.5)

        cbar4 = plt.colorbar(im4, ax=ax4, shrink=0.6, pad=0.02)
        cbar4.set_label('Head (m a.s.l.)')
        ax4.set_title('(d) Heads with Boundary', fontweight='bold')
        ax4.set_xlabel('Easting (m)')
        ax4.set_ylabel('Northing (m)')
        ax4.set_aspect('equal')

    except Exception as e:
        ax4.text(0.5, 0.5, f'Could not create combined plot:\n{e}',
                ha='center', va='center', transform=ax4.transAxes)
        ax4.set_title('(d) Combined View', fontweight='bold')

    plt.tight_layout()

    # Save if requested
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to: {save_path}")

    return fig, axes


def plot_grid_refinement(
    modelgrid,
    refinement_gdf=None,
    boundary_gdf=None,
    highlight_color='red',
    base_color='lightblue',
    figsize=(12, 10),
    title="DISV Grid with Refinement",
    show_cell_count=True,
    ax=None,
):
    """
    Visualize DISV grid with optional refinement zones highlighted.

    Useful for students to verify their local grid refinement in case
    study notebooks. Shows cell structure and highlights refinement areas.

    Parameters
    ----------
    modelgrid : flopy.discretization.VertexGrid
        FloPy VertexGrid object (DISV grid).
    refinement_gdf : geopandas.GeoDataFrame, optional
        GeoDataFrame with polygon(s) defining the refinement area.
        Cells within this area will be highlighted.
    boundary_gdf : geopandas.GeoDataFrame, optional
        Model boundary polygon to overlay.
    highlight_color : str, optional
        Color for cells in refinement area. Default: 'red'.
    base_color : str, optional
        Color for cells outside refinement area. Default: 'lightblue'.
    figsize : tuple, optional
        Figure size (width, height) in inches. Default: (12, 10).
    title : str, optional
        Plot title. Default: "DISV Grid with Refinement".
    show_cell_count : bool, optional
        Whether to show cell count statistics. Default: True.
    ax : matplotlib.axes.Axes, optional
        Existing axes to plot on. If None, creates new figure/axes.

    Returns
    -------
    fig : matplotlib.figure.Figure
        The figure object.
    ax : matplotlib.axes.Axes
        The axes object.

    Examples
    --------
    >>> # Visualize base grid
    >>> fig, ax = plot_grid_refinement(modelgrid)

    >>> # Visualize with refinement area highlighted
    >>> study_area = gpd.read_file("my_study_area.gpkg")
    >>> fig, ax = plot_grid_refinement(
    ...     modelgrid,
    ...     refinement_gdf=study_area,
    ...     title="Grid with Local Refinement"
    ... )
    """
    from flopy.discretization import VertexGrid
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union

    # Validate grid type
    if not isinstance(modelgrid, VertexGrid):
        raise TypeError(
            f"modelgrid must be a VertexGrid (DISV), got {type(modelgrid)}. "
            "For structured grids, use plot_grid() directly."
        )

    # Create figure if needed
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.get_figure()

    # Get cell information
    ncpl = modelgrid.ncpl
    vertices = modelgrid._vertices
    cell2d = modelgrid.cell2d

    # Build vertex dictionary
    vert_dict = {v[0]: (v[1], v[2]) for v in vertices}

    # Determine which cells are in refinement area
    refined_cells = set()
    if refinement_gdf is not None:
        refine_union = unary_union(refinement_gdf.geometry)

        for cell in cell2d:
            cell_id = cell[0]
            xc, yc = cell[1], cell[2]
            if refine_union.contains(Point(xc, yc)):
                refined_cells.add(cell_id)

    # Build cell polygons and plot
    from matplotlib.patches import Polygon as MplPolygon
    from matplotlib.collections import PatchCollection

    base_patches = []
    refined_patches = []

    for cell in cell2d:
        cell_id = cell[0]
        nvert = cell[3]
        vert_ids = cell[4:4+nvert]

        coords = [vert_dict[vid] for vid in vert_ids]

        if cell_id in refined_cells:
            refined_patches.append(MplPolygon(coords, closed=True))
        else:
            base_patches.append(MplPolygon(coords, closed=True))

    # Plot base cells
    if base_patches:
        base_collection = PatchCollection(
            base_patches,
            facecolor=base_color,
            edgecolor='gray',
            linewidth=0.3,
            alpha=0.7
        )
        ax.add_collection(base_collection)

    # Plot refined cells
    if refined_patches:
        refined_collection = PatchCollection(
            refined_patches,
            facecolor=highlight_color,
            edgecolor='darkred',
            linewidth=0.5,
            alpha=0.6
        )
        ax.add_collection(refined_collection)

    # Plot refinement area boundary if provided
    if refinement_gdf is not None:
        refinement_gdf.boundary.plot(
            ax=ax, color='darkred', linewidth=2,
            linestyle='--', label='Refinement Area'
        )

    # Plot model boundary if provided
    if boundary_gdf is not None:
        boundary_gdf.boundary.plot(
            ax=ax, color='black', linewidth=2, label='Model Boundary'
        )

    # Set axis limits
    xc = modelgrid.xcellcenters
    yc = modelgrid.ycellcenters
    if xc.ndim > 1:
        xc = xc.flatten()
        yc = yc.flatten()

    buffer = (xc.max() - xc.min()) * 0.02
    ax.set_xlim(xc.min() - buffer, xc.max() + buffer)
    ax.set_ylim(yc.min() - buffer, yc.max() + buffer)

    # Add cell count statistics
    if show_cell_count:
        n_refined = len(refined_cells)
        n_base = ncpl - n_refined

        stats_text = f"Total cells: {ncpl:,}"
        if n_refined > 0:
            stats_text += f"\nRefined area: {n_refined:,} cells"
            stats_text += f"\nBase area: {n_base:,} cells"

        ax.text(
            0.02, 0.98, stats_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
        )

    # Set labels
    ax.set_title(title, fontweight='bold')
    ax.set_xlabel('Easting (m)')
    ax.set_ylabel('Northing (m)')
    ax.set_aspect('equal')

    # Add legend if we have boundaries
    if refinement_gdf is not None or boundary_gdf is not None:
        ax.legend(loc='upper right')

    plt.tight_layout()

    return fig, ax


def get_idomain_cmap():
    """
    Return standard IDOMAIN discrete colormap and normalizer.

    Creates a colormap suitable for visualizing IDOMAIN arrays with three
    categories: inactive (0), active (1), and vertical pass-through (-1).

    Returns
    -------
    cmap : matplotlib.colors.ListedColormap
        Discrete colormap with 3 colors.
    norm : matplotlib.colors.BoundaryNorm
        Normalizer for discrete boundaries.
    tick_labels : list
        Labels for colorbar ticks.

    Examples
    --------
    >>> cmap, norm, labels = get_idomain_cmap()
    >>> fig, ax = plt.subplots()
    >>> im = ax.imshow(idomain, cmap=cmap, norm=norm)
    >>> cbar = plt.colorbar(im, ax=ax, ticks=[-1, 0, 1])
    >>> cbar.ax.set_yticklabels(labels)
    """
    from matplotlib.colors import ListedColormap, BoundaryNorm

    # Colors for: -1 (pass-through), 0 (inactive), 1 (active)
    colors = ['lightgray', 'white', 'lightblue']
    cmap = ListedColormap(colors)

    # Boundaries: -1.5 to -0.5 (=-1), -0.5 to 0.5 (=0), 0.5 to 1.5 (=1)
    bounds = [-1.5, -0.5, 0.5, 1.5]
    norm = BoundaryNorm(bounds, cmap.N)

    tick_labels = ['Pass-through (-1)', 'Inactive (0)', 'Active (1)']

    return cmap, norm, tick_labels


# =============================================================================
# Legacy Functions (Structured Grids / MODFLOW 2005/NWT)
# =============================================================================

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


def plot_chd_validation(
    chd_spd,
    modelgrid,
    model_top,
    model_bottom,
    idomain=None,
    boundary_gdf=None,
    riv_spd=None,
    buffer_m=100,
    figsize=(14, 6),
    title="CHD Boundary Validation"
):
    """
    Create validation figure for CHD (Constant Head) boundary estimation.

    Shows two panels:
    1. Map view zoomed to the CHD boundary area with continuous head values
    2. Cross-section along northing showing model top, CHD head, river bottom, and model bottom

    Parameters
    ----------
    chd_spd : list of tuple
        CHD stress period data. Each tuple contains:
        - For DISV grids: ((layer, cell_id), head)
        - For structured grids: ((layer, row, col), head)
    modelgrid : flopy.discretization.Grid
        FloPy model grid object (StructuredGrid or VertexGrid).
    model_top : numpy.ndarray
        Model top elevation array. Shape depends on grid type:
        - For DISV: 1D array of shape (ncpl,)
        - For structured: 2D array of shape (nrow, ncol)
    model_bottom : numpy.ndarray
        Model bottom elevation array. Same shape as model_top.
    idomain : numpy.ndarray, optional
        IDOMAIN array for showing active domain. If None, all cells assumed active.
    boundary_gdf : geopandas.GeoDataFrame, optional
        Model boundary polygon for context.
    riv_spd : list of tuple, optional
        RIV stress period data for plotting river bottom. Each tuple contains:
        ((layer, cell_id), stage, conductance, rbot)
    buffer_m : float, optional
        Buffer distance (meters) around CHD cells for zoom extent. Default is 100.
    figsize : tuple, optional
        Figure size (width, height) in inches. Default is (14, 6).
    title : str, optional
        Figure title. Default is "CHD Boundary Validation".

    Returns
    -------
    fig, axes : matplotlib figure and axes tuple (ax_map, ax_xsec)
        The figure and axes objects for further customization.

    Examples
    --------
    >>> # After creating CHD stress period data
    >>> chd_spd = [[(0, i), 390.0] for i in outflow_cell_ids]
    >>> fig, axes = plot_chd_validation(
    ...     chd_spd, modelgrid, model_top, model_bottom,
    ...     idomain=idomain, boundary_gdf=boundary_gdf, riv_spd=riv_spd
    ... )
    >>> plt.show()
    """
    from flopy.discretization import VertexGrid

    if len(chd_spd) == 0:
        print("Warning: No CHD cells to validate")
        return None, None

    # Extract cell IDs and head values from stress period data
    cell_ids = []
    head_values = []

    for entry in chd_spd:
        cellid = entry[0]  # (layer, cell_id) or (layer, row, col)
        head = entry[1]

        if isinstance(modelgrid, VertexGrid):
            # DISV: cellid is (layer, cell_index)
            cell_idx = cellid[1]
        else:
            # Structured: cellid is (layer, row, col)
            layer, row, col = cellid
            cell_idx = row * modelgrid.ncol + col

        cell_ids.append(cell_idx)
        head_values.append(head)

    cell_ids = np.array(cell_ids)
    head_values = np.array(head_values)

    # Get cell coordinates
    xc = modelgrid.xcellcenters
    yc = modelgrid.ycellcenters

    if xc.ndim > 1:
        xc = xc.flatten()
        yc = yc.flatten()

    # Get model top/bottom at CHD cells
    top_flat = model_top.flatten() if model_top.ndim > 1 else model_top
    bottom_flat = model_bottom.flatten() if model_bottom.ndim > 1 else model_bottom
    top_at_chd = top_flat[cell_ids]
    bottom_at_chd = bottom_flat[cell_ids]

    # Calculate zoom extent based on CHD cell locations
    chd_xmin, chd_xmax = xc[cell_ids].min(), xc[cell_ids].max()
    chd_ymin, chd_ymax = yc[cell_ids].min(), yc[cell_ids].max()

    # Add buffer
    xlim = (chd_xmin - buffer_m, chd_xmax + buffer_m)
    ylim = (chd_ymin - buffer_m, chd_ymax + buffer_m)

    # Create figure with two panels
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    ax_map, ax_xsec = axes

    # --- Panel 1: Map view ---
    # Create array for CHD visualization
    if isinstance(modelgrid, VertexGrid):
        ncells = modelgrid.ncpl
    else:
        ncells = modelgrid.nrow * modelgrid.ncol

    chd_array = np.full(ncells, np.nan)
    chd_array[cell_ids] = head_values

    # Plot using PlotMapView for unstructured grid support
    pmv = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax_map)

    # Plot grid
    pmv.plot_grid(linewidth=0.3, color='gray', alpha=0.5)

    # Plot CHD cells with continuous head values
    vmin, vmax = head_values.min(), head_values.max()
    # Add small buffer to color range if all values are the same
    if vmin == vmax:
        vmin -= 1
        vmax += 1

    im = pmv.plot_array(chd_array, cmap='Blues', alpha=0.9, vmin=vmin, vmax=vmax)

    # Add boundary if provided
    if boundary_gdf is not None:
        boundary_gdf.boundary.plot(ax=ax_map, color='black', linewidth=1.5)

    # Colorbar with continuous scale
    cbar = plt.colorbar(im, ax=ax_map, shrink=0.7, pad=0.02)
    cbar.set_label('CHD Head (m a.s.l.)', fontsize=10)

    # Apply zoom to CHD area
    ax_map.set_xlim(xlim)
    ax_map.set_ylim(ylim)

    ax_map.set_xlabel('Easting (m)')
    ax_map.set_ylabel('Northing (m)')
    ax_map.set_title('CHD Cell Locations', fontsize=11)
    ax_map.set_aspect('equal')

    # --- Panel 2: Cross-section along northing ---
    # Sort CHD cells by northing (y coordinate)
    chd_y = yc[cell_ids]
    sort_idx = np.argsort(chd_y)

    y_sorted = chd_y[sort_idx]
    top_sorted = top_at_chd[sort_idx]
    bottom_sorted = bottom_at_chd[sort_idx]
    head_sorted = head_values[sort_idx]
    cell_ids_sorted = cell_ids[sort_idx]

    # Plot model top
    ax_xsec.plot(y_sorted, top_sorted, 'k-', linewidth=2, label='Model top (land surface)')

    # Plot model bottom
    ax_xsec.plot(y_sorted, bottom_sorted, 'brown', linewidth=2, label='Model bottom')

    # Plot CHD head
    ax_xsec.plot(y_sorted, head_sorted, 'b-', linewidth=2, label='CHD head')

    # Fill aquifer zone
    ax_xsec.fill_between(y_sorted, bottom_sorted, top_sorted, alpha=0.2, color='lightblue', label='Aquifer')

    # Plot river bottom if RIV data provided
    if riv_spd is not None and len(riv_spd) > 0:
        # Extract river cell info
        riv_cell_ids = []
        riv_rbot = []
        riv_stage = []

        for entry in riv_spd:
            cellid = entry[0]
            stage = entry[1]
            rbot = entry[3]

            if isinstance(modelgrid, VertexGrid):
                cell_idx = cellid[1]
            else:
                layer, row, col = cellid
                cell_idx = row * modelgrid.ncol + col

            riv_cell_ids.append(cell_idx)
            riv_rbot.append(rbot)
            riv_stage.append(stage)

        riv_cell_ids = np.array(riv_cell_ids)
        riv_rbot = np.array(riv_rbot)
        riv_stage = np.array(riv_stage)

        # Find river cells near the CHD boundary (within x range of CHD cells)
        riv_x = xc[riv_cell_ids]
        riv_y = yc[riv_cell_ids]

        # Filter to cells within the CHD x-range (+ small buffer)
        x_tolerance = 150  # meters
        near_chd_mask = (riv_x >= chd_xmin - x_tolerance) & (riv_x <= chd_xmax + x_tolerance)

        if near_chd_mask.sum() > 0:
            riv_y_near = riv_y[near_chd_mask]
            riv_rbot_near = riv_rbot[near_chd_mask]
            riv_stage_near = riv_stage[near_chd_mask]

            # Sort by y
            riv_sort_idx = np.argsort(riv_y_near)
            ax_xsec.plot(riv_y_near[riv_sort_idx], riv_rbot_near[riv_sort_idx],
                        'g--', linewidth=1.5, label='River bottom', marker='v', markersize=4)
            ax_xsec.plot(riv_y_near[riv_sort_idx], riv_stage_near[riv_sort_idx],
                        'c-', linewidth=1.5, label='River stage', marker='^', markersize=4)

    ax_xsec.set_xlabel('Northing (m)')
    ax_xsec.set_ylabel('Elevation (m a.s.l.)')
    ax_xsec.set_title('Cross-section at Western Boundary', fontsize=11)
    ax_xsec.legend(loc='upper right', fontsize=9)
    ax_xsec.grid(True, alpha=0.3)

    # Add stats text
    depth_below_surface = top_at_chd - head_values
    stats_text = (
        f"CHD cells: {len(cell_ids)}\n"
        f"Head: {head_values.min():.1f} - {head_values.max():.1f} m\n"
        f"Depth below surface: {depth_below_surface.min():.1f} - {depth_below_surface.max():.1f} m"
    )
    ax_xsec.text(0.02, 0.02, stats_text, transform=ax_xsec.transAxes, fontsize=9,
                verticalalignment='bottom', horizontalalignment='left',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))

    fig.suptitle(title, fontsize=12, fontweight='bold')
    plt.tight_layout()

    # Print validation summary
    print(f"CHD Validation Summary:")
    print(f"  Total CHD cells: {len(cell_ids)}")
    print(f"  Head values: {head_values.min():.1f} to {head_values.max():.1f} m a.s.l.")
    print(f"  Land surface at CHD: {top_at_chd.min():.1f} to {top_at_chd.max():.1f} m a.s.l.")
    print(f"  Depth below surface: {depth_below_surface.min():.1f} to {depth_below_surface.max():.1f} m")

    valid_mask = depth_below_surface > 0
    if (~valid_mask).sum() > 0:
        print(f"  WARNING: {(~valid_mask).sum()} cells have head at or above land surface!")
    else:
        print(f"  All CHD heads are below land surface")

    return fig, axes

