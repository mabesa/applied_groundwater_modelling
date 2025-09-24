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
    
    def __init__(self, parent_model: flopy.modflow.Modflow, head_file_path: str):
        """
        Initialize the boundary head extractor.
        
        Parameters:
        -----------
        parent_model : flopy.modflow.Modflow
            The parent MODFLOW model object
        head_file_path : str
            Path to the parent model head file (.hds)
        """
        self.parent_model = parent_model
        self.head_file_path = head_file_path
        self.heads = None
        self.grid_info = self._get_grid_info()
        
    def _get_grid_info(self) -> Dict:
        """Extract grid information from parent model."""
        mg = self.parent_model.modelgrid
        
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
    
    def get_submodel_bounds_cells(self, 
                                 xmin: float, 
                                 xmax: float, 
                                 ymin: float, 
                                 ymax: float,
                                 buffer_cells: int = 2) -> Tuple[int, int, int, int]:
        """
        Convert submodel coordinate bounds to parent model cell indices.
        
        Parameters:
        -----------
        xmin, xmax, ymin, ymax : float
            Submodel bounds in model coordinate system
        buffer_cells : int, default 2
            Additional buffer cells around the specified bounds
            
        Returns:
        --------
        Tuple[int, int, int, int]
            (row_min, row_max, col_min, col_max) in parent model indices
        """
        mg = self.parent_model.modelgrid
        
        # Convert coordinates to cell indices
        col_min = max(0, mg.get_col(xmin)[0] - buffer_cells)
        col_max = min(mg.ncol - 1, mg.get_col(xmax)[0] + buffer_cells)
        row_max = max(0, mg.get_row(ymin)[0] - buffer_cells)  # Note: row increases downward
        row_min = min(mg.nrow - 1, mg.get_row(ymax)[0] + buffer_cells)
        
        return row_min, row_max, col_min, col_max
    
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