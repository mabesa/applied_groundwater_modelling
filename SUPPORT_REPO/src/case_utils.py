import os, pprint
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import yaml
import zipfile

from shapely.geometry import Point, Polygon
import geopandas as gpd
from typing import Tuple, List, Dict, Optional

import flopy
from flopy.utils import HeadFile, CellBudgetFile

plt.rcParams['figure.figsize'] = (8, 6)
def ensure_dir(p):
    Path(p).mkdir(parents=True, exist_ok=True)

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def unzip_file(zip_path, extract_to=None):
    print(f"Checking zip file: {zip_path}")
    print(f"File size: {os.path.getsize(zip_path)} bytes")
    if extract_to is None:
        extract_to = os.path.dirname(zip_path)
    print(f"Extracting to: {extract_to}")
    # Check if it's a valid zip file
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            print("✓ Zip file is valid")
            files = zip_ref.namelist()
            print(f"Contains {len(files)} files:")
            for f in files[:5]:  # Show first 5 files
                print(f"  {f}")
            if len(files) > 5:
                print(f"  ... and {len(files)-5} more")
                
            # Try extraction
            extract_path = os.path.dirname(zip_path)
            zip_ref.extractall(extract_path)
            print(f"✓ Extraction successful to {extract_path}")
            
    except zipfile.BadZipFile as e:
        print(f"✗ Bad zip file: {e}")
        
        # Check first few bytes
        with open(zip_path, 'rb') as f:
            header = f.read(10)
            print(f"File header: {header.hex()}")
            print(f"As text: {header}")
            
        raise e   
    
def get_scenario_for_group(config_path, group_number):
    """
    Load the YAML config and return the scenario parameters for the given group number.
    
    Parameters:
    -----------
    config_path : str
        Path to the case_config.yaml file
    group_number : int
        Group number (0-8)
        
    Returns:
    --------
    dict
        Scenario parameters for the group, or None if not found
    """
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Find the scenario with id matching the group number
    scenarios = cfg.get('scenarios', {}).get('options', [])
    
    for scenario in scenarios:
        if scenario.get('id') == group_number:
            return scenario
    
    return None

def filter_wells_by_concession(wells_gdf, concession_id):
    """Filter wells by concession ID."""
    # Work on a copy to avoid SettingWithCopyWarning
    wells_filtered = wells_gdf.copy()
    
    # Normalize / helper columns
    wells_filtered.loc[:, 'GWR_PREFIX'] = (
        wells_filtered['GWR_ID']
        .astype(str)
        .str.split('_', n=1).str[0]
        .str.strip()
        .str.lower()
    )
    
    # Only keep wells where GWR_PREFIX values start with 'b010' (code for Limmat valley aquifer)
    limmat_mask = wells_filtered['GWR_PREFIX'].str.startswith('b010')
    wells_filtered = wells_filtered[limmat_mask].copy()
    
    # Replace 'b010' with '' in GWR_PREFIX
    wells_filtered.loc[:, 'GWR_PREFIX'] = wells_filtered['GWR_PREFIX'].str.replace('b010', '', regex=False)
    
    # Now we get the wells for our concession
    concession_mask = wells_filtered['GWR_PREFIX'] == str(concession_id).lower()
    return wells_filtered[concession_mask].copy()

def plot_wells_on_model(m, wells_gdf, concession_id, modelgrid=None):
    """
    Plot wells on the model grid with proper rotation handling.
    
    Parameters:
    -----------
    m : flopy.modflow.Modflow
        The MODFLOW model object
    wells_gdf : geopandas.GeoDataFrame
        GeoDataFrame containing well locations and attributes
    concession_id : int or str
        The concession ID for labeling
    modelgrid : flopy.discretization.StructuredGrid, optional
        Override modelgrid (if None, uses m.modelgrid)
    """
    fig, ax = plt.subplots(figsize=(14, 12))

    # Use the model's own modelgrid if not provided
    grid_to_use = modelgrid if modelgrid is not None else m.modelgrid
    
    # Create PlotMapView object with the model (this handles rotation automatically)
    pmv = flopy.plot.PlotMapView(model=m, modelgrid=grid_to_use, ax=ax)

    # Plot the model grid
    pmv.plot_grid(alpha=0.4, color='white', linewidth=0.3)

    # Plot ibound - this should work with rotation
    if hasattr(m, 'bas6') and hasattr(m.bas6, 'ibound'):
        ibound_array = m.bas6.ibound.array
    if len(ibound_array.shape) > 2:
        ibound_layer = ibound_array[0]  # Use first layer
    else:
        ibound_layer = ibound_array
    # Plot with RdYlBu colormap and no masking to show all values
    pmv.plot_array(ibound_layer, alpha=0.4, cmap='RdYlBu', vmin=-1, vmax=1)

    # For wells, we need to ensure they're in the right coordinate system
    # Transform wells to model coordinates if needed
    wells_transformed = wells_gdf.copy()
    
    # If the modelgrid has rotation/offset, we might need coordinate transformation
    '''if hasattr(grid_to_use, 'get_local_coords'):
        # Convert real-world coords to local model coords
        local_coords = grid_to_use.get_local_coords(
            wells_gdf.geometry.x.values, 
            wells_gdf.geometry.y.values
        )
        wells_transformed.geometry = gpd.points_from_xy(local_coords[0], local_coords[1])
        wells_transformed.crs = None  # Local coordinates'''
    
    # Plot wells with different colors for different types
    well_types = wells_gdf['FASSART'].unique() if 'FASSART' in wells_gdf.columns else ['Unknown']
    colors = ['red', 'blue', 'green', 'orange']

    for i, well_type in enumerate(well_types):
        if 'FASSART' in wells_gdf.columns:
            wells_subset = wells_transformed[wells_gdf['FASSART'] == well_type]
        else:
            wells_subset = wells_transformed
    
        wells_subset.plot(ax=ax, color=colors[i % len(colors)], 
                         markersize=150, marker='o', 
                         label=f'{well_type}', alpha=0.9, edgecolor='black')

    # Add well ID labels using transformed coordinates
    for idx, (orig_row, trans_row) in enumerate(zip(wells_gdf.itertuples(), wells_transformed.itertuples())):
        ax.annotate(orig_row.GWR_ID.split('_')[-1],
                    xy=(trans_row.geometry.x, trans_row.geometry.y),
                    xytext=(8, 8), textcoords='offset points',
                    fontsize=9, ha='left', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))

    # Formatting
    ax.legend(loc='upper right')
    ax.set_xlabel('X coordinate (m)')
    ax.set_ylabel('Y coordinate (m)')
    ax.set_title(f'Concession {concession_id} Wells on MODFLOW Grid\n'
                 f'Model: {m.name} | Grid: {m.dis.nrow}×{m.dis.ncol} cells')
    ax.set_aspect('equal')

    plt.tight_layout()
    return fig, ax



def recarray_from_wells(wells):
    dtype = [('k', int), ('i', int), ('j', int), ('flux', float)]
    arr = np.zeros((len(wells),), dtype=dtype)
    for idx, w in enumerate(wells):
        arr[idx] = (w['layer'], w['row'], w['col'], w['rate'])
    return arr

def summarize_budget(cbc_path, terms, kstpkper=(0,0)):
    cbc = CellBudgetFile(cbc_path)
    out = {}
    for t in terms:
        try:
            data = cbc.get_data(text=t, kstpkper=kstpkper)
            if data:
                out[t] = float(np.sum(data[0]))
            else:
                out[t] = None
        except Exception:
            out[t] = None
    return out

def sample_heads(hds_path, lrc_list, kstpkper=None):
    hf = HeadFile(hds_path)
    arr = hf.get_data(kstpkper=kstpkper) if kstpkper is not None else hf.get_data()[-1]
    samples = []
    for (k,i,j) in lrc_list:
        samples.append({'k':k, 'i':i, 'j':j, 'head': float(arr[k, i, j])})
    return samples


class BoundaryHeadExtractor:
    """
    Extract boundary heads from a parent MODFLOW model for submodel creation.
    """
    
    def __init__(self, parent_model: flopy.modflow.Modflow, head_file_path: str, modelgrid=None):
        """
        Initialize the boundary head extractor.
        
        Parameters:
        -----------
        parent_model : flopy.modflow.Modflow
            The parent MODFLOW model object
        head_file_path : str
            Path to the parent model head file (.hds)
        modelgrid : flopy.discretization.StructuredGrid, optional
            Rotated/transformed modelgrid object. If None, uses parent_model.modelgrid
        """
        self.parent_model = parent_model
        self.head_file_path = head_file_path
        self.heads = None
        # Use the provided modelgrid if available, otherwise fall back to model's grid
        self.modelgrid = modelgrid if modelgrid is not None else parent_model.modelgrid
        self.grid_info = self._get_grid_info()
        
    def _get_grid_info(self) -> Dict:
        """Extract grid information from modelgrid."""
        mg = self.modelgrid
        
        return {
            'delr': mg.delr,
            'delc': mg.delc,
            'xorigin': mg.xoffset,
            'yorigin': mg.yoffset,
            'rotation': mg.angrot,
            'nrow': mg.nrow,
            'ncol': mg.ncol,
            'nlay': mg.nlay
        }
    
    def get_submodel_bounds_cells(self, 
                                 xmin: float, 
                                 xmax: float, 
                                 ymin: float, 
                                 ymax: float,
                                 buffer_cells: int = 2) -> Tuple[int, int, int, int]:
        """
        Convert submodel coordinate bounds to parent model cell indices.
        Uses the rotated modelgrid for proper coordinate transformation.
        
        Parameters:
        -----------
        xmin, xmax, ymin, ymax : float
            Submodel bounds in real-world coordinate system
        buffer_cells : int, default 2
            Additional buffer cells around the specified bounds
            
        Returns:
        --------
        Tuple[int, int, int, int]
            (row_min, row_max, col_min, col_max) in parent model indices
        """
        mg = self.modelgrid
        
        # Define corner points of the bounding box
        corner_points = [
            (xmin, ymin),  # bottom-left
            (xmax, ymin),  # bottom-right
            (xmin, ymax),  # top-left
            (xmax, ymax)   # top-right
        ]
        
        # Find cell indices for all corner points
        rows = []
        cols = []
        
        for x, y in corner_points:
            try:
                # Try intersect method first (newer FloPy versions)
                if hasattr(mg, 'intersect'):
                    row, col = mg.intersect(x, y)
                    rows.append(row)
                    cols.append(col)
                else:
                    # Fallback: use coordinate arrays
                    # Find closest cell center
                    x_diffs = np.abs(mg.xcellcenters - x)
                    y_diffs = np.abs(mg.ycellcenters - y)
                    
                    # Find minimum distance cell
                    total_diff = x_diffs + y_diffs
                    min_idx = np.unravel_index(np.argmin(total_diff), total_diff.shape)
                    row, col = min_idx
                    rows.append(row)
                    cols.append(col)
                    
            except Exception as e:
                print(f"Warning: Could not intersect point ({x}, {y}): {e}")
                # Use approximate calculation as last resort
                row = int((mg.yoffset - y) / np.mean(mg.delc))
                col = int((x - mg.xoffset) / np.mean(mg.delr))
                rows.append(max(0, min(mg.nrow-1, row)))
                cols.append(max(0, min(mg.ncol-1, col)))
        
        # Get bounding box in cell indices
        row_min = max(0, min(rows) - buffer_cells)
        row_max = min(mg.nrow - 1, max(rows) + buffer_cells)
        col_min = max(0, min(cols) - buffer_cells)
        col_max = min(mg.ncol - 1, max(cols) + buffer_cells)
        
        print(f"Submodel cell bounds: rows {row_min}-{row_max}, cols {col_min}-{col_max}")
        
        return row_min, row_max, col_min, col_max

    
    def load_heads(self, stress_period: int = -1, time_step: int = -1) -> np.ndarray:
        """
        Load heads from the parent model head file.
        
        Parameters:
        -----------
        stress_period : int, default -1
            Stress period to extract (use -1 for last)
        time_step : int, default -1
            Time step to extract (use -1 for last)
            
        Returns:
        --------
        np.ndarray
            3D array of heads [nlay, nrow, ncol]
        """
        try:
            hds = flopy.utils.HeadFile(self.head_file_path)
            
            # Get available time steps and stress periods
            available_kstpkper = hds.get_kstpkper()
            print(f"Available (timestep, stress_period) combinations: {available_kstpkper}")
            
            # If defaults are used, get the last available record
            if stress_period == -1 and time_step == -1:
                if len(available_kstpkper) == 0:
                    raise ValueError("No data found in head file")
                # Use the last available record
                kstpkper_to_use = available_kstpkper[-1]
                print(f"Using last available record: {kstpkper_to_use}")
            else:
                # Check if requested combination exists
                kstpkper_to_use = (time_step, stress_period)
                if kstpkper_to_use not in available_kstpkper:
                    raise ValueError(f"Requested kstpkper {kstpkper_to_use} not found. "
                                   f"Available options: {available_kstpkper}")
            
            self.heads = hds.get_data(kstpkper=kstpkper_to_use)
            hds.close()
            print(f"Successfully loaded heads from kstpkper: {kstpkper_to_use}")
            return self.heads
            
        except Exception as e:
            raise ValueError(f"Error loading head file: {e}")
    
    def extract_boundary_heads(self,
                              submodel_bounds: Tuple[float, float, float, float],
                              layers: Optional[List[int]] = None,
                              buffer_cells: int = 2) -> Dict:
        """
        Extract boundary heads for submodel domain.
        
        Parameters:
        -----------
        submodel_bounds : Tuple[float, float, float, float]
            (xmin, xmax, ymin, ymax) in model coordinates
        layers : List[int], optional
            Layer indices to extract (0-based). If None, extracts all layers
        buffer_cells : int, default 2
            Buffer cells around submodel bounds
            
        Returns:
        --------
        Dict
            Dictionary containing boundary head data and metadata
        """
        if self.heads is None:
            raise ValueError("Heads not loaded. Call load_heads() first.")
        
        xmin, xmax, ymin, ymax = submodel_bounds
        
        # Get cell indices
        row_min, row_max, col_min, col_max = self.get_submodel_bounds_cells(
            xmin, xmax, ymin, ymax, buffer_cells
        )
        
        # Determine layers to extract
        if layers is None:
            layers = list(range(self.grid_info['nlay']))
        
        # Extract boundary cells
        boundary_data = []
        
        for layer in layers:
            # Extract submodel domain from parent heads
            submodel_heads = self.heads[layer, row_min:row_max+1, col_min:col_max+1]
            
            # Find boundary cells (perimeter of the extracted domain)
            nrow_sub, ncol_sub = submodel_heads.shape
            
            # Top and bottom rows
            for col in range(ncol_sub):
                # Top boundary (row 0)
                if not np.isnan(submodel_heads[0, col]):
                    boundary_data.append({
                        'layer': layer + 1,  # MODFLOW uses 1-based indexing
                        'row': 1,  # First row in submodel
                        'col': col + 1,  # MODFLOW uses 1-based indexing
                        'head': submodel_heads[0, col],
                        'boundary_type': 'north'
                    })
                
                # Bottom boundary (last row)
                if not np.isnan(submodel_heads[-1, col]):
                    boundary_data.append({
                        'layer': layer + 1,
                        'row': nrow_sub,  # Last row in submodel
                        'col': col + 1,
                        'head': submodel_heads[-1, col],
                        'boundary_type': 'south'
                    })
            
            # Left and right columns (excluding corners already covered)
            for row in range(1, nrow_sub - 1):
                # Left boundary (col 0)
                if not np.isnan(submodel_heads[row, 0]):
                    boundary_data.append({
                        'layer': layer + 1,
                        'row': row + 1,
                        'col': 1,  # First column in submodel
                        'head': submodel_heads[row, 0],
                        'boundary_type': 'west'
                    })
                
                # Right boundary (last col)
                if not np.isnan(submodel_heads[row, -1]):
                    boundary_data.append({
                        'layer': layer + 1,
                        'row': row + 1,
                        'col': ncol_sub,  # Last column in submodel
                        'head': submodel_heads[row, -1],
                        'boundary_type': 'east'
                    })
        
        # Calculate submodel grid properties
        mg = self.parent_model.modelgrid
        submodel_xmin = mg.xyedges[0][col_min]
        submodel_ymax = mg.xyedges[1][row_min]
        submodel_delr = self.grid_info['delr'][col_min:col_max+1]
        submodel_delc = self.grid_info['delc'][row_min:row_max+1]
        
        return {
            'boundary_data': boundary_data,
            'submodel_grid': {
                'nrow': row_max - row_min + 1,
                'ncol': col_max - col_min + 1,
                'nlay': len(layers),
                'delr': submodel_delr,
                'delc': submodel_delc,
                'xorigin': submodel_xmin,
                'yorigin': submodel_ymax,
                'rotation': self.grid_info['rotation']
            },
            'parent_indices': {
                'row_min': row_min,
                'row_max': row_max,
                'col_min': col_min,
                'col_max': col_max,
                'layers': layers
            }
        }
    
    def create_chd_package_data(self, boundary_data: List[Dict]) -> List[List]:
        """
        Convert boundary data to MODFLOW CHD package format.
        
        Parameters:
        -----------
        boundary_data : List[Dict]
            Boundary head data from extract_boundary_heads()
            
        Returns:
        --------
        List[List]
            CHD package data in format: [layer, row, col, start_head, end_head]
        """
        chd_data = []
        
        for cell in boundary_data:
            chd_data.append([
                cell['layer'] - 1,  # Convert to 0-based for FloPy
                cell['row'] - 1,    # Convert to 0-based for FloPy
                cell['col'] - 1,    # Convert to 0-based for FloPy
                cell['head'],       # Start head
                cell['head']        # End head (same for steady state)
            ])
        
        return chd_data
    
    def visualize_boundary_cells(self, boundary_data: List[Dict], submodel_grid: Dict):
        """
        Create a simple visualization of boundary cells (requires matplotlib).
        
        Parameters:
        -----------
        boundary_data : List[Dict]
            Boundary head data
        submodel_grid : Dict
            Submodel grid information
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("Matplotlib not available for visualization")
            return
        
        # Create a simple plot showing boundary cell locations
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot boundary cells colored by head value
        for cell in boundary_data:
            if cell['layer'] == 1:  # Only plot first layer
                ax.scatter(cell['col'], cell['row'], 
                          c=cell['head'], cmap='viridis', s=50)
        
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')
        ax.set_title('Submodel Boundary Cells (Layer 1)')
        plt.colorbar(ax.collections[0], label='Head (m)')
        plt.show()





def plot_submodel_extent_on_parent_model(m, modelgrid, wells_gdf, concession_id, submodel_bounds, submodel_grid):
    """
    Plot the submodel extent on the parent model grid to verify positioning.
    
    Parameters:
    -----------
    m : flopy.modflow.Modflow
        The parent MODFLOW model object
    modelgrid : flopy.discretization.StructuredGrid
        The rotated/transformed modelgrid object
    wells_gdf : geopandas.GeoDataFrame
        GeoDataFrame containing well locations
    concession_id : int or str
        The concession ID for labeling
    submodel_bounds : tuple
        (xmin, xmax, ymin, ymax) in real-world coordinates
    submodel_grid : dict
        Dictionary containing submodel grid information
    """
    fig, ax = plt.subplots(figsize=(14, 12))

    # Use the provided modelgrid for proper coordinate handling
    pmv = flopy.plot.PlotMapView(model=m, modelgrid=modelgrid, ax=ax)

    # Plot the parent model grid (light)
    pmv.plot_grid(alpha=0.2, color='lightgray', linewidth=0.2)

    # Plot ibound to show active/inactive cells
    if hasattr(m, 'bas6') and hasattr(m.bas6, 'ibound'):
        ibound_array = m.bas6.ibound.array
        if len(ibound_array.shape) > 2:
            ibound_layer = ibound_array[0]  # Use first layer
        else:
            ibound_layer = ibound_array
        pmv.plot_array(ibound_layer, alpha=0.3, cmap='RdYlBu', vmin=-1, vmax=1)

    # Create submodel boundary rectangle
    xmin, xmax, ymin, ymax = submodel_bounds
    
    # Create a rectangle for the submodel bounds
    from matplotlib.patches import Rectangle
    rect = Rectangle((xmin, ymin), xmax - xmin, ymax - ymin,
                     linewidth=3, edgecolor='red', facecolor='red', alpha=0.2,
                     label=f'Submodel Domain\n{submodel_grid["nrow"]}×{submodel_grid["ncol"]} cells')
    ax.add_patch(rect)
    
    # Add corner coordinates as text
    ax.text(xmin, ymax + 20, f'({xmin:.0f}, {ymax:.0f})', 
            ha='left', va='bottom', fontsize=9, 
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    ax.text(xmax, ymin - 20, f'({xmax:.0f}, {ymin:.0f})', 
            ha='right', va='top', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))

    # Plot wells with different colors for different types
    well_types = wells_gdf['FASSART'].unique() if 'FASSART' in wells_gdf.columns else ['Unknown']
    colors = ['darkred', 'darkblue', 'darkgreen', 'orange']

    for i, well_type in enumerate(well_types):
        if 'FASSART' in wells_gdf.columns:
            wells_subset = wells_gdf[wells_gdf['FASSART'] == well_type]
        else:
            wells_subset = wells_gdf
    
        wells_subset.plot(ax=ax, color=colors[i % len(colors)], 
                         markersize=200, marker='o', 
                         label=f'Wells: {well_type}', alpha=1.0, 
                         edgecolor='white', linewidth=2, zorder=10)

    # Add well ID labels
    for idx, row in wells_gdf.iterrows():
        ax.annotate(row.GWR_ID.split('_')[-1],
                    xy=(row.geometry.x, row.geometry.y),
                    xytext=(10, 10), textcoords='offset points',
                    fontsize=10, ha='left', va='bottom', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.8),
                    zorder=11)

    # Add buffer distance annotations
    lateral_dist = (xmax - xmin - (wells_gdf.geometry.x.max() - wells_gdf.geometry.x.min())) / 2
    upstream_dist = wells_gdf.geometry.y.min() - ymin
    downstream_dist = ymax - wells_gdf.geometry.y.max()
    
    # Add dimension annotations
    ax.annotate(f'Lateral buffer: {lateral_dist:.0f}m', 
                xy=(xmin - 50, (ymin + ymax) / 2), rotation=90,
                ha='center', va='bottom', fontsize=9,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='lightblue', alpha=0.7))
    
    ax.annotate(f'Upstream: {upstream_dist:.0f}m', 
                xy=((xmin + xmax) / 2, ymin - 30),
                ha='center', va='top', fontsize=9,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='lightblue', alpha=0.7))
    
    ax.annotate(f'Downstream: {downstream_dist:.0f}m', 
                xy=((xmin + xmax) / 2, ymax + 30),
                ha='center', va='bottom', fontsize=9,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='lightblue', alpha=0.7))

    # Add grid lines for the submodel (if desired)
    # This shows the refined grid resolution
    n_grid_lines = 10  # Show every nth grid line to avoid clutter
    if submodel_grid['ncol'] > n_grid_lines:
        step_col = submodel_grid['ncol'] // n_grid_lines
        cell_width = (xmax - xmin) / submodel_grid['ncol']
        for i in range(0, submodel_grid['ncol'], step_col):
            x_line = xmin + i * cell_width
            ax.axvline(x_line, ymin=(ymin - ax.get_ylim()[0]) / (ax.get_ylim()[1] - ax.get_ylim()[0]),
                      ymax=(ymax - ax.get_ylim()[0]) / (ax.get_ylim()[1] - ax.get_ylim()[0]),
                      color='red', alpha=0.4, linewidth=0.5)
    
    if submodel_grid['nrow'] > n_grid_lines:
        step_row = submodel_grid['nrow'] // n_grid_lines
        cell_height = (ymax - ymin) / submodel_grid['nrow']
        for i in range(0, submodel_grid['nrow'], step_row):
            y_line = ymin + i * cell_height
            ax.axhline(y_line, xmin=(xmin - ax.get_xlim()[0]) / (ax.get_xlim()[1] - ax.get_xlim()[0]),
                      xmax=(xmax - ax.get_xlim()[0]) / (ax.get_xlim()[1] - ax.get_xlim()[0]),
                      color='red', alpha=0.4, linewidth=0.5)

    # Formatting
    ax.legend(loc='upper right', fontsize=10)
    ax.set_xlabel('X coordinate (m)', fontsize=12)
    ax.set_ylabel('Y coordinate (m)', fontsize=12)
    
    # Calculate resolution info
    parent_res = np.mean(modelgrid.delr)  # Assuming uniform parent grid
    sub_res = (xmax - xmin) / submodel_grid['ncol']
    refinement_ratio = parent_res / sub_res
    
    ax.set_title(f'Submodel Domain for Concession {concession_id}\n'
                 f'Parent Grid: {parent_res:.0f}m → Submodel: {sub_res:.0f}m '
                 f'(Refinement: {refinement_ratio:.1f}×)', fontsize=14)
    ax.set_aspect('equal')

    # Set reasonable axis limits (zoom in around the submodel area)
    margin = max((xmax - xmin), (ymax - ymin)) * 0.2
    ax.set_xlim(xmin - margin, xmax + margin)
    ax.set_ylim(ymin - margin, ymax + margin)

    plt.tight_layout()
    plt.show()
    
    # Print summary information
    print(f"\n=== Submodel Grid Summary ===")
    print(f"Submodel bounds: ({xmin:.0f}, {ymin:.0f}) to ({xmax:.0f}, {ymax:.0f})")
    print(f"Submodel size: {xmax-xmin:.0f}m × {ymax-ymin:.0f}m")
    print(f"Grid resolution: {sub_res:.1f}m × {sub_res:.1f}m")
    print(f"Grid dimensions: {submodel_grid['nrow']} rows × {submodel_grid['ncol']} columns")
    print(f"Total cells: {submodel_grid['nrow'] * submodel_grid['ncol']:,}")
    print(f"Refinement ratio: {refinement_ratio:.1f}× finer than parent grid")
    
    return fig, ax