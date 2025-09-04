import os
os.environ.setdefault("GDAL_NUM_THREADS", "ALL_CPUS")
os.environ.setdefault("OMP_NUM_THREADS", str(os.cpu_count() or 1))

import sys
import requests
from pathlib import Path
from tqdm.notebook import tqdm
from urllib.parse import urlparse
from typing import Union, Optional, Literal

import numpy as np

from rasterio.windows import from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.transform import rowcol
from scipy.ndimage import map_coordinates


def find_project_root(marker_files=['config.py', 'config_template.py']):
    """Find the project root by searching for a list of marker files."""
    # Start from current working directory. In a locally run Jupyter notebook, 
    # this will be the directory where the notebook is located.
    # In a JupyterHub environment, it will be the user's home directory.
    path = os.getcwd()
    print(f"Starting search for project root from: {path}")
    # Traverse up the directory tree until we find the marker file
    # or reach the filesystem root.
    while os.path.dirname(path) != path: # Stop at filesystem root
        print(f"Checking path: {path}")
        for marker in marker_files:
            if os.path.exists(os.path.join(path, marker)):
                print(f"Found project root: {path} (marker: {marker})")
                return path
        print(f"Marker file not found in {path}. Moving up...")
        path = os.path.dirname(path)
    
    # Fallback 
    # If running as a script, __file__ might be available
    try:
        print(f"Trying to find project root using __file__...")
        path = os.path.dirname(os.path.abspath(__file__))
        while os.path.dirname(path) != path:
            for marker in marker_files:
                if os.path.exists(os.path.join(path, marker)):
                    return path
            path = os.path.dirname(path)
    except NameError:
        pass # __file__ is not defined in interactive environments
    raise FileNotFoundError(f"Project root with one of {marker_files} not found.")

project_root = find_project_root()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from config import CASE_STUDY, DATA_SOURCE, DATA_URLS
    print("Loaded configuration from 'config.py'")
except ImportError:
    print("Warning: 'config.py' not found. Falling back to 'config_template.py'.")
    from config_template import CASE_STUDY, DATA_SOURCE, DATA_URLS


def get_data_urls():
    """Get data URLs based on current case study and data source settings."""
    if CASE_STUDY not in DATA_URLS:
        raise ValueError(f"Unknown case study: {CASE_STUDY}")
    
    if DATA_SOURCE not in DATA_URLS[CASE_STUDY]:
        raise ValueError(f"Data source '{DATA_SOURCE}' not available for case study '{CASE_STUDY}'")
    
    return DATA_URLS[CASE_STUDY][DATA_SOURCE]

def get_default_data_folder():
    """Get the default data folder for the current case study."""
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, "applied_groundwater_modelling_data", CASE_STUDY)

def download_named_file(name, dest_folder=None, data_type=None):
    """
    Download a named file from the configured data source.
    
    Args:
        name: Name of the file/dataset to download
        dest_folder: Destination folder (if None, uses default structure)
        data_type: Type of data (climate, groundwater, rivers, geology) for organization
    
    Returns:
        Path to the downloaded file
    """
    # Get the appropriate URLs for current case study and data source
    url_dict = get_data_urls()
    
    if name not in url_dict:
        raise ValueError(f"No URL configured for '{name}' in {DATA_SOURCE} data for case study '{CASE_STUDY}'.")

    file_info = url_dict[name]
    url = file_info['url']
    filename = file_info['filename']
    
    # Determine destination folder
    if dest_folder is None:
        dest_folder = get_default_data_folder()
        if data_type:
            dest_folder = os.path.join(dest_folder, data_type)
    
    os.makedirs(dest_folder, exist_ok=True)

    # --- Helper function for downloading ---
    def _download(url, filename, description):
        dest_path = os.path.join(dest_folder, filename)
        if os.path.exists(dest_path):
            print(f"{filename} already exists in {dest_folder}.")
            return dest_path
        
        print(f"Downloading {description} ({filename})...")
        try:
            r = requests.get(url, stream=True)
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            with open(dest_path, 'wb') as f, tqdm(
                desc=filename, total=total, unit='iB', unit_scale=True, unit_divisor=1024
            ) as bar:
                for chunk in r.iter_content(chunk_size=1024):
                    size = f.write(chunk)
                    bar.update(size)
            print(f"Download complete: {dest_path}")
            return dest_path
        except Exception as e:
            print(f"Error downloading {filename}: {e}")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise

    # --- Download data file ---
    data_path = _download(file_info['url'], file_info['filename'], "data file")

    # --- Download README if it exists ---
    if 'readme_url' in file_info:
        readme_url = file_info['readme_url']
        
        # Automatically determine the README filename
        original_name, _ = os.path.splitext(file_info['filename'])
        
        # Extract file extension from the URL path
        parsed_url = urlparse(readme_url)
        _, readme_ext = os.path.splitext(parsed_url.path)
        
        if not readme_ext:
            print(f"Warning: Could not determine file extension for README from URL: {readme_url}")
        else:
            readme_filename = f"{original_name}_readme{readme_ext}"
            _download(readme_url, readme_filename, "README")

    return data_path

def get_data_path(data_type=None):
    """
    Get the path to data folder for the current case study.
    
    Args:
        data_type: Optional data type subdirectory (climate, groundwater, etc.)
    
    Returns:
        Path to the data folder
    """
    base_path = get_default_data_folder()
    if data_type:
        return os.path.join(base_path, data_type)
    return base_path

def list_available_datasets():
    """List all available datasets for the current case study and data source."""
    try:
        url_dict = get_data_urls()
        print(f"Available datasets for '{CASE_STUDY}' from '{DATA_SOURCE}':")
        for name in url_dict.keys():
            print(f"  - {name}")
    except Exception as e:
        print(f"Error listing datasets: {e}")


def fast_resample_dem_to_modelgrid(
    dem_path: Union[str, Path],
    modelgrid,
    method: Literal["nearest", "linear"] = "nearest",
    fill_value: Optional[float] = np.nan,
    mask_nonpositive: bool = True,
    dtype: str = "float32",
) -> np.ndarray:
    """
    Fast resample of a DEM to a (possibly rotated) FloPy StructuredGrid by sampling
    the DEM at grid cell centers in a single vectorized call.

    This uses GDAL's C-backed warper (via rasterio.WarpedVRT) for on-the-fly CRS
    reprojection and reads only the model extent. Sampling is performed with
    scipy.ndimage.map_coordinates:
    - method='nearest' → nearest-neighbor
    - method='linear' → bilinear

    Parameters:
    - dem_path (str | Path): Path to the DEM raster (elevation in meters a.s.l.) [m]
    - modelgrid: FloPy StructuredGrid (with .xcellcenters, .ycellcenters, .extent, .crs)
    - method ('nearest' | 'linear'): Resampling kernel ('linear' ≈ bilinear)
    - fill_value (float | None): Value to fill outside-coverage or nodata cells (default: NaN)
    - mask_nonpositive (bool): If True, set elevations <= 0 m to NaN (simple sanity mask)
    - dtype (str): Output dtype (e.g., 'float32')

    Returns:
    - np.ndarray: Array of shape (nrow, ncol) with elevations [m a.s.l.]

    Notes:
    - CRS handling: If DEM CRS differs from modelgrid.crs, a WarpedVRT performs
      on-the-fly reprojection. Ensure modelgrid.crs is properly set (e.g., EPSG:2056 for Swiss LV95).
    - Performance: Avoids Python loops; leverages GDAL threading (GDAL_NUM_THREADS=ALL_CPUS).
      Typical speedup is 5–20× over pure Python resampling in notebooks/JupyterHub.
    - Rotated grids: Works for rotated FloPy grids by sampling exact cell centers.

    Example:
    >>> # model_top_m: elevation at model cell centers [m a.s.l.]
    >>> model_top_m = fast_resample_dem_to_modelgrid("/path/to/dem.tif", modelgrid, method="linear")
    >>> model_top_m = np.round(model_top_m, 0)  # keep 0.1–1 m precision as needed
    """
    import rasterio  # local import to speed startup if rasterio is not used elsewhere

    xmin, xmax, ymin, ymax = modelgrid.extent  # (xmin, xmax, ymin, ymax)

    with rasterio.open(str(dem_path)) as src:
        needs_warp = str(src.crs) != str(modelgrid.crs)
        if needs_warp:
            ds = WarpedVRT(src, crs=modelgrid.crs, resampling=Resampling.bilinear)
        else:
            ds = src

        # Read only the window covering the model domain
        win = from_bounds(xmin, ymin, xmax, ymax, transform=ds.transform)
        arr = ds.read(1, window=win, boundless=True).astype("float32", copy=False)
        nodata = ds.nodata
        tr = ds.window_transform(win)

    # Replace raster nodata with NaN prior to interpolation to avoid contamination
    if nodata is not None:
        arr = np.where(np.isclose(arr, nodata), np.nan, arr)

    # Cell-center coordinates (vectorized)
    xs = modelgrid.xcellcenters.ravel()
    ys = modelgrid.ycellcenters.ravel()

    # Map to fractional row/col indices in the read window
    rows, cols = rowcol(tr, xs, ys, op=float)
    coords = np.vstack([rows, cols])

    # Interpolate
    order = 1 if method == "linear" else 0
    vals = map_coordinates(
        arr, coords, order=order, mode="constant",
        cval=np.nan if fill_value is None or np.isnan(fill_value) else float(fill_value),
        prefilter=False,
    ).reshape(modelgrid.nrow, modelgrid.ncol)

    # Fill any NaNs with nearest-neighbor fallback
    if np.isnan(vals).any():
        vals_nn = map_coordinates(
            arr, coords, order=0, mode="nearest", prefilter=False
        ).reshape(vals.shape)
        nan_mask = ~np.isfinite(vals)
        vals[nan_mask] = vals_nn[nan_mask]

    # Optional masking of non-physical elevations
    if mask_nonpositive:
        vals = np.where(vals <= 0.0, np.nan, vals)

    # Cast and return
    return vals.astype(dtype, copy=False)




