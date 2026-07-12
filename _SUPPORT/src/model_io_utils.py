"""
Model I/O Utilities for MODFLOW 6

This module provides utilities for loading model data, sampling rasters,
and reading MODFLOW 6 simulation results. All functions are designed to work
with MODFLOW 6 and the flopy.mf6 API.

Key design principles:
- Use FloPy utilities wherever possible (flopy.utils.Raster, MFSimulation.load)
- Support MODFLOW 6 naming conventions (idomain, not ibound)
- Return data in formats ready for MF6 package creation
- Store boundary conditions as geometries, not cell IDs

Functions:
    load_model_boundary: Load domain polygon GeoPackage for grid generation
    load_bc_geometries: Load river, well, inflow geometries from GeoPackages
    sample_raster_at_cells: Sample DEM/bottom raster at cell centers
    load_and_interpolate_aquifer_thickness: Load and interpolate thickness from GIS contours
    load_preprocessed_model_data: Load all pre-computed model inputs as dict
    format_budget_summary: Read MF6 budget and format as DataFrame
    load_base_simulation: Load pre-built MF6 simulation
    compare_water_balances: Compare two water balance DataFrames
    build_refined_gwf_model: Build locally-refined GWF model from coarse model
    build_prt_model: Build PRT particle-tracking simulation from GWF model
    load_prt_results: Load and classify PRT tracking results
    freeze_flow_spec: Encode a refined-grid spec (incl. ragged DISV gridprops)
        into an NPZ + hash-verified manifest via case_artifact_lock
    load_flow_spec: Reconstruct a frozen flow spec from its NPZ/manifest pair
    load_pinned_flow_model: Load a per-group pinned flow spec and assemble it
        into a runnable GWF model without re-deriving geometry

Author: Applied Groundwater Modelling Course
"""

from __future__ import annotations

import os
import json
import zipfile
from pathlib import Path
from typing import Union, Dict, List, Optional, Any

import numpy as np
import pandas as pd
import geopandas as gpd

import flopy
from flopy.utils import Raster
from flopy.mf6 import MFSimulation
from shapely.geometry import LineString


# Canton Zurich shallow groundwater zone type-to-thickness mapping
# Based on GS_GW_LEITER_F layer GWLTYP classification
DEFAULT_GWLTYP_TO_THICKNESS_M = {
    1: 2,   # Low groundwater thickness area
    2: 2,   # Medium thickness (2-10m) - conservative lower bound
    4: 10,  # High thickness (10-20m)
    6: 20,  # Very high thickness (>20m)
}

# Course steady-state MODFLOW 6 policy used by the refined NB8 model.
GWF_NEWTON_OPTIONS = "NEWTON"
GWF_NEWTON_IMS_OPTIONS = {
    "complexity": "COMPLEX",
    "outer_maximum": 200,
    "inner_maximum": 100,
    "outer_dvclose": 1e-3,
    "inner_dvclose": 1e-4,
    "linear_acceleration": "BICGSTAB",
}


def load_model_boundary(
    data_dir: Union[str, Path],
    filename: str = "model_boundary.gpkg",
    layer: Optional[str] = None
) -> gpd.GeoDataFrame:
    """
    Load the model domain polygon from a GeoPackage file.

    This function loads the model boundary polygon used for grid generation.
    The boundary should be a single polygon (or multipolygon) representing
    the active model domain.

    Parameters
    ----------
    data_dir : str or Path
        Path to the directory containing the boundary GeoPackage file.
    filename : str, optional
        Name of the GeoPackage file. Default is "model_boundary.gpkg".
    layer : str, optional
        Layer name within the GeoPackage. If None, reads the first layer.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame containing the model boundary polygon(s).
        Typically contains a single polygon with the model domain.

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist.
    ValueError
        If the file contains no valid polygon geometries.

    Examples
    --------
    >>> boundary_gdf = load_model_boundary("data/processed")
    >>> print(f"Boundary CRS: {boundary_gdf.crs}")
    >>> print(f"Number of polygons: {len(boundary_gdf)}")

    Notes
    -----
    - The boundary polygon is used by Voronoi grid generation functions
    - CRS should be a projected coordinate system (e.g., EPSG:2056 for Swiss)
    - The polygon exterior vertices are used as constraints in grid generation
    """
    data_dir = Path(data_dir)
    filepath = data_dir / filename

    if not filepath.exists():
        raise FileNotFoundError(
            f"Model boundary file not found: {filepath}\n"
            f"Ensure the file exists in the data directory."
        )

    # Read the GeoPackage
    if layer is not None:
        boundary_gdf = gpd.read_file(filepath, layer=layer)
    else:
        boundary_gdf = gpd.read_file(filepath)

    # Validate that we have polygon geometries
    valid_types = {"Polygon", "MultiPolygon"}
    geom_types = set(boundary_gdf.geometry.geom_type.unique())

    if not geom_types.intersection(valid_types):
        raise ValueError(
            f"Model boundary file must contain Polygon or MultiPolygon geometries. "
            f"Found: {geom_types}"
        )

    print(f"Loaded model boundary from: {filepath}")
    print(f"  CRS: {boundary_gdf.crs}")
    print(f"  Number of features: {len(boundary_gdf)}")
    print(f"  Total bounds: {boundary_gdf.total_bounds}")

    return boundary_gdf


def load_bc_geometries(
    data_dir: Union[str, Path],
    river_file: str = "river_geometry.gpkg",
    well_file: str = "well_geometry.gpkg",
    inflow_file: str = "lateral_inflow_geometry.gpkg",
    load_river: bool = True,
    load_wells: bool = True,
    load_inflow: bool = True
) -> Dict[str, Optional[gpd.GeoDataFrame]]:
    """
    Load boundary condition geometries from GeoPackage files.

    This function loads river, well, and lateral inflow geometries that are
    used to assign boundary conditions to model cells at runtime. The geometries
    are stored with their attributes (stage, conductance, rates, etc.) and
    are intersected with the model grid to determine cell assignments.

    Parameters
    ----------
    data_dir : str or Path
        Path to the directory containing the BC geometry files.
    river_file : str, optional
        Name of the river geometry file. Default is "river_geometry.gpkg".
    well_file : str, optional
        Name of the well geometry file. Default is "well_geometry.gpkg".
    inflow_file : str, optional
        Name of the lateral inflow geometry file.
        Default is "lateral_inflow_geometry.gpkg".
    load_river : bool, optional
        Whether to load river geometries. Default is True.
    load_wells : bool, optional
        Whether to load well geometries. Default is True.
    load_inflow : bool, optional
        Whether to load lateral inflow geometries. Default is True.

    Returns
    -------
    dict
        Dictionary with keys 'river', 'wells', 'inflow', each containing
        a GeoDataFrame or None if not loaded or file not found.

        Expected attributes in each GeoDataFrame:
        - river: stage, conductance, rbot (river bottom), geometry (LineString)
        - wells: rate (negative for extraction), geometry (Point)
        - inflow: head or flux, geometry (LineString or Polygon)

    Examples
    --------
    >>> bc_geoms = load_bc_geometries("data/processed")
    >>> river_gdf = bc_geoms['river']
    >>> print(f"Number of river reaches: {len(river_gdf)}")

    >>> # Load only wells
    >>> bc_geoms = load_bc_geometries(
    ...     "data/processed",
    ...     load_river=False,
    ...     load_inflow=False
    ... )

    Notes
    -----
    - Geometries are stored in Swiss coordinates (EPSG:2056) by default
    - BC cell assignments are computed at runtime via GridIntersect
    - This design allows the same BC files to work with different grids
    - Missing files result in None values rather than errors (with warning)
    """
    data_dir = Path(data_dir)
    result = {"river": None, "wells": None, "inflow": None}

    def _load_file(filename: str, bc_type: str) -> Optional[gpd.GeoDataFrame]:
        """Helper to load a single BC file with error handling."""
        filepath = data_dir / filename
        if not filepath.exists():
            print(f"Warning: {bc_type} geometry file not found: {filepath}")
            return None

        try:
            gdf = gpd.read_file(filepath)
            print(f"Loaded {bc_type} geometries from: {filepath}")
            print(f"  Features: {len(gdf)}, CRS: {gdf.crs}")
            return gdf
        except Exception as e:
            print(f"Error loading {bc_type} geometries: {e}")
            return None

    # Load requested geometry types
    if load_river:
        result["river"] = _load_file(river_file, "river")

    if load_wells:
        result["wells"] = _load_file(well_file, "well")

    if load_inflow:
        result["inflow"] = _load_file(inflow_file, "lateral inflow")

    # Summary
    loaded_count = sum(1 for v in result.values() if v is not None)
    print(f"\nLoaded {loaded_count} of 3 BC geometry files")

    return result


def sample_raster_at_cells(
    raster_path: Union[str, Path],
    modelgrid,
    band: int = 1,
    method: str = "nearest",
    nodata_value: float = np.nan
) -> np.ndarray:
    """
    Sample raster values at model grid cell centers using FloPy's Raster utility.

    This function samples a raster (e.g., DEM for model top, or bottom surface)
    at the cell centers of a FloPy model grid. It uses flopy.utils.Raster for
    efficient sampling and handles both structured and unstructured (DISV) grids.

    Parameters
    ----------
    raster_path : str or Path
        Path to the raster file (GeoTIFF format recommended).
    modelgrid : flopy.discretization.Grid
        FloPy model grid object (StructuredGrid or VertexGrid).
        Must have xcellcenters and ycellcenters attributes.
    band : int, optional
        Raster band to sample. Default is 1.
    method : str, optional
        Interpolation method for sampling. Options:
        - "nearest": Nearest neighbor (fastest, preserves values)
        - "linear": Bilinear interpolation (smoother results)
        Default is "nearest".
    nodata_value : float, optional
        Value to use for cells outside raster extent or at nodata pixels.
        Default is np.nan.

    Returns
    -------
    numpy.ndarray
        Array of sampled values with shape matching the model grid:
        - For StructuredGrid: shape (nrow, ncol)
        - For VertexGrid (DISV): shape (ncpl,) - 1D array of cell values

    Raises
    ------
    FileNotFoundError
        If the raster file does not exist.
    ValueError
        If the raster and grid have no spatial overlap.

    Examples
    --------
    >>> # Sample DEM for model top
    >>> top = sample_raster_at_cells("data/dem.tif", modelgrid)
    >>> print(f"Elevation range: {np.nanmin(top):.1f} to {np.nanmax(top):.1f} m")

    >>> # Sample aquifer bottom with linear interpolation
    >>> botm = sample_raster_at_cells(
    ...     "data/aquifer_bottom.tif",
    ...     modelgrid,
    ...     method="linear"
    ... )

    Notes
    -----
    - Uses flopy.utils.Raster which handles CRS alignment automatically
    - For DISV grids, returns a 1D array indexed by cell number (icpl)
    - Nodata values in the raster are replaced with nodata_value parameter
    - The raster should be in the same CRS as the model grid for best results
    """
    raster_path = Path(raster_path)

    if not raster_path.exists():
        raise FileNotFoundError(f"Raster file not found: {raster_path}")

    # Create FloPy Raster object
    raster = Raster.load(str(raster_path))

    print(f"Sampling raster: {raster_path.name}")
    print(f"  Raster bounds: {raster.bounds}")

    # Get cell centers
    xc = modelgrid.xcellcenters
    yc = modelgrid.ycellcenters

    # Determine grid type and prepare coordinates
    if hasattr(modelgrid, 'nrow') and hasattr(modelgrid, 'ncol'):
        # Structured grid - 2D arrays
        grid_type = "structured"
        output_shape = (modelgrid.nrow, modelgrid.ncol)
        # Flatten for sampling
        xc_flat = xc.flatten()
        yc_flat = yc.flatten()
    else:
        # Unstructured (DISV) grid - 1D arrays
        grid_type = "disv"
        output_shape = xc.shape
        xc_flat = xc.flatten() if xc.ndim > 1 else xc
        yc_flat = yc.flatten() if yc.ndim > 1 else yc

    print(f"  Grid type: {grid_type}")
    print(f"  Number of cells to sample: {len(xc_flat)}")

    # Sample raster at cell centers using FloPy Raster
    # The resample_to_grid method is more robust for grids
    try:
        # Use FloPy's built-in resampling
        sampled = raster.resample_to_grid(
            modelgrid,
            band=band,
            method=method
        )

        # Handle nodata values
        if hasattr(raster, 'nodataval') and raster.nodataval is not None:
            sampled = np.where(
                sampled == raster.nodataval,
                nodata_value,
                sampled
            )

    except Exception as e:
        print(f"  Warning: resample_to_grid failed ({e}), using point sampling...")
        # Fallback to point-by-point sampling
        sampled = np.full(len(xc_flat), nodata_value, dtype=np.float64)

        for i, (x, y) in enumerate(zip(xc_flat, yc_flat)):
            try:
                val = raster.sample_point(x, y, band=band)
                if val is not None:
                    sampled[i] = val
            except Exception:
                pass

        # Reshape if structured grid
        if grid_type == "structured":
            sampled = sampled.reshape(output_shape)

    # Report statistics
    valid_mask = ~np.isnan(sampled) if np.issubdtype(sampled.dtype, np.floating) else np.ones_like(sampled, dtype=bool)
    if valid_mask.any():
        print(f"  Sampled value range: {sampled[valid_mask].min():.2f} to {sampled[valid_mask].max():.2f}")
        print(f"  Valid cells: {valid_mask.sum()} of {sampled.size}")
    else:
        print("  Warning: No valid values sampled from raster!")

    return sampled


def load_preprocessed_model_data(
    data_dir: Union[str, Path],
    load_rasters: bool = True,
    modelgrid = None
) -> Dict[str, Any]:
    """
    Load all pre-computed model inputs from the data directory.

    This function loads pre-processed model data including boundary geometries,
    parameter files, observation data, and optionally samples raster data at
    grid cell centers. The returned dictionary contains data ready for creating
    MODFLOW 6 packages.

    Parameters
    ----------
    data_dir : str or Path
        Path to the directory containing pre-processed model data.
        Expected files:
        - model_boundary.gpkg: Domain polygon
        - river_geometry.gpkg: River reaches with stage, conductance, rbot
        - well_geometry.gpkg: Well locations with rates
        - lateral_inflow_geometry.gpkg: Boundary inflow geometries
        - dem_resampled.tif: DEM for model top
        - aquifer_bottom.tif: Aquifer bottom surface
        - initial_parameters.json: Initial K estimates
        - observation_data.csv: Head observations
    load_rasters : bool, optional
        Whether to sample raster data (requires modelgrid). Default is True.
    modelgrid : flopy.discretization.Grid, optional
        FloPy model grid for raster sampling. Required if load_rasters is True.

    Returns
    -------
    dict
        Dictionary containing all loaded model data with keys:
        - 'boundary': GeoDataFrame with model domain polygon
        - 'river': GeoDataFrame with river geometries and attributes
        - 'wells': GeoDataFrame with well points and rates
        - 'inflow': GeoDataFrame with lateral inflow geometries
        - 'top': numpy array with model top elevations (if load_rasters)
        - 'bottom': numpy array with aquifer bottom (if load_rasters)
        - 'parameters': dict with initial parameter values
        - 'observations': DataFrame with head observations

    Examples
    --------
    >>> # Load all data including rasters
    >>> from flopy.discretization import VertexGrid
    >>> modelgrid = create_disv_grid(...)  # Your grid creation
    >>> data = load_preprocessed_model_data("data/processed", modelgrid=modelgrid)
    >>>
    >>> # Access components
    >>> top = data['top']
    >>> river_gdf = data['river']
    >>> k_values = data['parameters']['hydraulic_conductivity']

    >>> # Load only geometries (no rasters)
    >>> data = load_preprocessed_model_data("data/processed", load_rasters=False)

    Notes
    -----
    - Uses MF6 naming conventions (idomain, not ibound)
    - Missing files result in None values with warnings
    - Raster sampling requires a modelgrid to be provided
    - Parameters file should use JSON format with MF6 package names
    """
    data_dir = Path(data_dir)
    result = {}

    print(f"Loading preprocessed model data from: {data_dir}")
    print("=" * 60)

    # Load model boundary
    try:
        result['boundary'] = load_model_boundary(data_dir)
    except FileNotFoundError:
        result['boundary'] = None
        print("Warning: Model boundary not found")

    # Load BC geometries
    bc_geoms = load_bc_geometries(data_dir)
    result['river'] = bc_geoms['river']
    result['wells'] = bc_geoms['wells']
    result['inflow'] = bc_geoms['inflow']

    # Load raster data if requested
    if load_rasters:
        if modelgrid is None:
            print("\nWarning: modelgrid required for raster sampling, skipping rasters")
            result['top'] = None
            result['bottom'] = None
        else:
            print("\n--- Sampling raster data ---")

            # Sample DEM for model top
            dem_path = data_dir / "dem_resampled.tif"
            if dem_path.exists():
                result['top'] = sample_raster_at_cells(dem_path, modelgrid)
            else:
                print(f"Warning: DEM file not found: {dem_path}")
                result['top'] = None

            # Sample aquifer bottom
            bottom_path = data_dir / "aquifer_bottom.tif"
            if bottom_path.exists():
                result['bottom'] = sample_raster_at_cells(bottom_path, modelgrid)
            else:
                print(f"Warning: Aquifer bottom file not found: {bottom_path}")
                result['bottom'] = None
    else:
        result['top'] = None
        result['bottom'] = None

    # Load initial parameters
    print("\n--- Loading parameters ---")
    params_path = data_dir / "initial_parameters.json"
    if params_path.exists():
        with open(params_path, 'r') as f:
            result['parameters'] = json.load(f)
        print(f"Loaded parameters from: {params_path}")
        if 'hydraulic_conductivity' in result['parameters']:
            print(f"  K values: {result['parameters']['hydraulic_conductivity']}")
    else:
        print(f"Warning: Parameters file not found: {params_path}")
        result['parameters'] = None

    # Load observation data
    print("\n--- Loading observations ---")
    obs_path = data_dir / "observation_data.csv"
    if obs_path.exists():
        result['observations'] = pd.read_csv(obs_path)
        print(f"Loaded {len(result['observations'])} observations from: {obs_path}")
    else:
        print(f"Warning: Observation file not found: {obs_path}")
        result['observations'] = None

    # Summary
    print("\n" + "=" * 60)
    print("Load summary:")
    for key, value in result.items():
        if value is None:
            status = "Not loaded"
        elif isinstance(value, (gpd.GeoDataFrame, pd.DataFrame)):
            status = f"{len(value)} records"
        elif isinstance(value, np.ndarray):
            status = f"Array shape {value.shape}"
        elif isinstance(value, dict):
            status = f"{len(value)} parameters"
        else:
            status = type(value).__name__
        print(f"  {key}: {status}")

    return result


def format_budget_summary(
    gwf,
    sim = None,
    precision: int = 2
) -> pd.DataFrame:
    """
    Read MODFLOW 6 budget and format as a summary DataFrame.

    This function reads the cell-by-cell budget from a completed MODFLOW 6
    simulation and formats it into a readable DataFrame showing inflows,
    outflows, and the overall water balance.

    Parameters
    ----------
    gwf : flopy.mf6.ModflowGwf
        MODFLOW 6 groundwater flow model object. The simulation must have
        been run successfully with budget output enabled.
    sim : flopy.mf6.MFSimulation, optional
        MFSimulation object. If provided, ensures the simulation workspace
        is correctly set. If None, uses gwf.simulation.
    precision : int, optional
        Number of decimal places for budget values. Default is 2.

    Returns
    -------
    pandas.DataFrame
        DataFrame with budget summary containing columns:
        - 'Component': Name of the budget component (e.g., 'RIV', 'WEL', 'RCH')
        - 'Inflow (m3/d)': Flow into the model domain
        - 'Outflow (m3/d)': Flow out of the model domain
        - 'Net (m3/d)': Net flow (inflow - outflow)

        Also includes summary rows:
        - 'TOTAL': Sum of all components
        - 'DISCREPANCY': Mass balance error
        - 'PERCENT ERROR': Error as percentage

    Raises
    ------
    FileNotFoundError
        If the budget file does not exist.
    RuntimeError
        If the model has not been run or budget output was not saved.

    Examples
    --------
    >>> # After running simulation
    >>> sim.run_simulation()
    >>> gwf = sim.get_model("gwf_model")
    >>> budget_df = format_budget_summary(gwf, sim)
    >>> print(budget_df)
    >>>
    >>> # Check water balance error
    >>> error = budget_df.loc['PERCENT ERROR', 'Net (m3/d)']
    >>> print(f"Water balance error: {error:.4f}%")

    Notes
    -----
    - Uses gwf.output.budget() to read the cell-by-cell budget
    - Budget values are for the last stress period by default
    - Positive values indicate flow INTO the model domain
    - MODFLOW 6 reports budget in model length and time units
    """
    # Get the budget object
    try:
        budget = gwf.output.budget()
    except Exception as e:
        raise RuntimeError(
            f"Could not read budget file. Ensure the model has been run "
            f"and OC package includes 'BUDGET SAVE'. Error: {e}"
        )

    # Get list of budget records
    record_names = budget.get_unique_record_names()
    print(f"Budget components found: {len(record_names)}")

    # Initialize storage for budget data
    budget_data = []

    # Get the last time step
    times = budget.get_times()
    if not times:
        raise RuntimeError("No budget data found. Has the model been run?")

    last_time = times[-1]
    print(f"Reading budget for time = {last_time}")

    # Process each budget component
    total_in = 0.0
    total_out = 0.0

    for record_name in record_names:
        # Clean up record name (remove padding)
        clean_name = record_name.strip()

        # Get budget data for this component
        try:
            data = budget.get_data(text=record_name, totim=last_time)
            if data is None or len(data) == 0:
                continue

            # Sum flows - positive is IN, negative is OUT
            # Data structure varies by package type
            if isinstance(data, list):
                flows = []
                for arr in data:
                    if hasattr(arr, 'q'):
                        flows.extend(arr['q'].flatten())
                    elif isinstance(arr, np.ndarray):
                        flows.extend(arr.flatten())
            else:
                if hasattr(data, 'q'):
                    flows = data['q'].flatten()
                else:
                    flows = data.flatten()

            flows = np.array(flows, dtype=float)

            # Separate inflows and outflows
            inflow = float(np.sum(flows[flows > 0]))
            outflow = float(np.abs(np.sum(flows[flows < 0])))
            net = inflow - outflow

            total_in += inflow
            total_out += outflow

            budget_data.append({
                'Component': clean_name,
                'Inflow (m3/d)': round(inflow, precision),
                'Outflow (m3/d)': round(outflow, precision),
                'Net (m3/d)': round(net, precision)
            })

        except Exception as e:
            print(f"Warning: Could not process {clean_name}: {e}")
            continue

    # Create DataFrame
    df = pd.DataFrame(budget_data)

    if len(df) == 0:
        print("Warning: No budget data could be extracted")
        return pd.DataFrame(columns=['Component', 'Inflow (m3/d)', 'Outflow (m3/d)', 'Net (m3/d)'])

    df = df.set_index('Component')

    # Add total row
    df.loc['TOTAL'] = [
        round(total_in, precision),
        round(total_out, precision),
        round(total_in - total_out, precision)
    ]

    # Calculate discrepancy and percent error
    discrepancy = total_in - total_out
    if total_in + total_out > 0:
        percent_error = 200 * abs(discrepancy) / (total_in + total_out)
    else:
        percent_error = 0.0

    df.loc['DISCREPANCY'] = [
        round(discrepancy, precision) if discrepancy > 0 else 0.0,
        round(abs(discrepancy), precision) if discrepancy < 0 else 0.0,
        round(discrepancy, precision)
    ]

    df.loc['PERCENT ERROR'] = [
        '-',
        '-',
        round(percent_error, precision + 2)
    ]

    print(f"\nWater Balance Summary:")
    print(f"  Total Inflow:  {total_in:,.{precision}f} m3/d")
    print(f"  Total Outflow: {total_out:,.{precision}f} m3/d")
    print(f"  Discrepancy:   {discrepancy:,.{precision}f} m3/d")
    print(f"  Percent Error: {percent_error:.{precision+2}f}%")

    return df


def load_base_simulation(
    sim_path: Union[str, Path],
    sim_name: str = "mfsim.nam",
    verbosity_level: int = 0,
    load_only: Optional[List[str]] = None
) -> MFSimulation:
    """
    Load a pre-built MODFLOW 6 simulation using flopy.mf6.MFSimulation.load().

    This function loads an existing MODFLOW 6 simulation from disk, allowing
    students to work with a pre-configured model and modify parameters without
    rebuilding from scratch.

    Parameters
    ----------
    sim_path : str or Path
        Path to the directory containing the simulation files.
        This should be the simulation workspace with mfsim.nam.
    sim_name : str, optional
        Name of the simulation name file. Default is "mfsim.nam".
    verbosity_level : int, optional
        FloPy verbosity level:
        - 0: Errors only
        - 1: Errors and warnings
        - 2: All messages
        Default is 0.
    load_only : list of str, optional
        List of package types to load. If None, loads all packages.
        Example: ['dis', 'npf', 'ic'] to load only discretization,
        node property flow, and initial conditions packages.

    Returns
    -------
    flopy.mf6.MFSimulation
        Loaded MFSimulation object containing all models and packages.
        Access the groundwater flow model with: sim.get_model("model_name")

    Raises
    ------
    FileNotFoundError
        If the simulation directory or name file does not exist.
    RuntimeError
        If the simulation cannot be loaded due to file errors.

    Examples
    --------
    >>> # Load a pre-built calibrated model
    >>> sim = load_base_simulation("models/calibrated_base")
    >>> gwf = sim.get_model("gwf_limmat")
    >>>
    >>> # Modify parameters
    >>> npf = gwf.get_package("npf")
    >>> print(f"Current K: {npf.k.array}")
    >>>
    >>> # Change K and run
    >>> npf.k = new_k_array
    >>> sim.run_simulation()

    >>> # Load only specific packages (faster for large models)
    >>> sim = load_base_simulation(
    ...     "models/base",
    ...     load_only=['dis', 'npf', 'riv']
    ... )

    Notes
    -----
    - The simulation is loaded in place without modifying original files
    - Changes are only saved when sim.write_simulation() is called
    - Use sim.get_model() to access individual model objects
    - Model modifications can be made via package objects
    - Useful for sensitivity analysis and parameter exploration
    """
    sim_path = Path(sim_path)

    # Check simulation path exists
    if not sim_path.exists():
        raise FileNotFoundError(f"Simulation directory not found: {sim_path}")

    # Check for name file
    nam_path = sim_path / sim_name
    if not nam_path.exists():
        raise FileNotFoundError(
            f"Simulation name file not found: {nam_path}\n"
            f"Ensure the directory contains a valid MODFLOW 6 simulation."
        )

    print(f"Loading MODFLOW 6 simulation from: {sim_path}")

    # Load the simulation
    try:
        sim = MFSimulation.load(
            sim_name=sim_name,
            sim_ws=str(sim_path),
            verbosity_level=verbosity_level,
            load_only=load_only
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to load simulation: {e}\n"
            f"Ensure all required simulation files are present and valid."
        )

    # Print summary
    print(f"  Simulation name: {sim.name}")
    print(f"  Models: {list(sim.model_names)}")

    # Print package summary for each model
    for model_name in sim.model_names:
        model = sim.get_model(model_name)
        package_names = [pkg.name[0] for pkg in model.packagelist]
        print(f"  {model_name} packages: {package_names}")

    return sim


def ensure_flow_model(sim_path: Optional[Union[str, Path]] = None) -> Path:
    """Return the CALIBRATED flow-model simulation path, downloading + extracting
    the pre-computed calibration if it is not already present locally.

    The default location is ``<data>/limmat/calibration`` — the steady-state
    MODFLOW 6 / DISV flow model produced by the flow track's
    ``05f_calibration.ipynb``. It has the same DISV grid and wells as the base
    ``notebook4_model`` but with the *calibrated* hydraulic-conductivity field
    (mean K ~ 361 m/d). The model name inside the simulation is ``limmat_valley``.
    The transport track builds on this calibrated field.

    Resolution order:
      1. If ``<sim_path>/mfsim.nam`` already exists (05f output or a prior
         download) -> return ``sim_path``.
      2. Otherwise try ``download_named_file('flow_model_mf6')`` and unzip the
         archive into ``sim_path``.
      3. If the download name is not configured (or the fetch fails) -> raise a
         clear, actionable error pointing the user at 05f / config.py.

    Parameters
    ----------
    sim_path : str or Path, optional
        Simulation workspace to use / populate. Defaults to
        ``<default-data-folder>/calibration``.

    Returns
    -------
    pathlib.Path
        Path to the simulation workspace containing ``mfsim.nam``.

    Raises
    ------
    FileNotFoundError
        If the model is absent locally and cannot be downloaded/extracted.
    """
    # 1. Resolve the default calibrated-model workspace.
    if sim_path is None:
        from data_utils import get_default_data_folder
        sim_path = Path(get_default_data_folder()) / "calibration"
    else:
        sim_path = Path(sim_path)

    nam_path = sim_path / "mfsim.nam"

    # 2. Already present (05f output or a prior download) -> use as-is.
    if nam_path.exists():
        return sim_path

    # 3. Try to download + extract the pre-computed calibrated flow model.
    sim_path.mkdir(parents=True, exist_ok=True)
    try:
        from data_utils import download_named_file
        zip_path = download_named_file("flow_model_mf6", dest_folder=str(sim_path))
    except Exception as exc:
        raise FileNotFoundError(
            "Calibrated flow model not found. Either run the flow track "
            "05f_calibration.ipynb (which downloads the pre-computed "
            "calibration), or configure the 'flow_model_mf6' download in "
            f"config.py.\n(underlying error: {exc})"
        ) from exc

    # 4. Extract the archive (handle a zip wrapping either the workspace
    #    directory or its bare contents). Idempotent on re-run.
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(sim_path)
    except zipfile.BadZipFile as exc:
        raise FileNotFoundError(
            "Calibrated flow model download is not a valid zip archive: "
            f"{zip_path}\n(underlying error: {exc})"
        ) from exc

    if nam_path.exists():
        return sim_path

    # zip wrapped a top-level directory -> locate mfsim.nam and use its parent.
    found = list(sim_path.rglob("mfsim.nam"))
    if found:
        return found[0].parent

    raise FileNotFoundError(
        "Calibrated flow model archive did not contain 'mfsim.nam'. Either run "
        "the flow track 05f_calibration.ipynb, or fix the 'flow_model_mf6' "
        "download in config.py."
    )


# Additional utility functions that may be useful

def get_model_crs(modelgrid) -> Optional[str]:
    """
    Get the coordinate reference system from a FloPy model grid.

    Parameters
    ----------
    modelgrid : flopy.discretization.Grid
        FloPy model grid object.

    Returns
    -------
    str or None
        CRS string (e.g., 'EPSG:2056') or None if not set.
    """
    if hasattr(modelgrid, 'crs') and modelgrid.crs is not None:
        return str(modelgrid.crs)

    # Try to infer from coordinates (Swiss)
    if hasattr(modelgrid, 'xcellcenters') and hasattr(modelgrid, 'ycellcenters'):
        x_range = (modelgrid.xcellcenters.min(), modelgrid.xcellcenters.max())
        y_range = (modelgrid.ycellcenters.min(), modelgrid.ycellcenters.max())

        # Swiss CH1903+ coordinates typically in hundreds of thousands
        if x_range[0] > 100000 and y_range[0] > 100000:
            return 'EPSG:2056'

    return None


def check_simulation_success(sim) -> bool:
    """
    Check if a MODFLOW 6 simulation completed successfully.

    Parameters
    ----------
    sim : flopy.mf6.MFSimulation
        MFSimulation object after running.

    Returns
    -------
    bool
        True if simulation completed successfully, False otherwise.
    """
    # Check for common success indicators
    try:
        # Try to read listing file for success message
        lst_path = Path(sim.sim_path) / f"{sim.name}.lst"
        if lst_path.exists():
            with open(lst_path, 'r') as f:
                content = f.read()
                if "Normal termination" in content:
                    return True
                if "FAILED TO CONVERGE" in content:
                    return False

        # Alternative: check if output files exist
        for model_name in sim.model_names:
            model = sim.get_model(model_name)
            try:
                _ = model.output.head()
                return True
            except Exception:
                pass

        return False

    except Exception:
        return False


def load_and_interpolate_aquifer_thickness(
    gw_map_path: Union[str, Path],
    modelgrid,
    boundary_gdf: gpd.GeoDataFrame,
    thickness_column: str = 'LABEL',
    contour_layer: str = 'GS_GW_MAECHTIGKEIT_L',
    method: str = 'improved',
    fallback_thickness: float = 17.5,
    min_thickness: float = 1.0,
    max_thickness: float = 100.0,
    verbose: bool = True,
    blend_shallow_zones: bool = True,
    shallow_layer: str = 'GS_GW_LEITER_F',
    gwltyp_to_thickness: Optional[Dict[int, float]] = None,
    include_boundary_constraint: bool = True,
) -> np.ndarray:
    """
    Load aquifer thickness data from GIS and interpolate to model grid.

    This function follows the same pattern as sample_raster_at_cells() for model_top:
    data is loaded and processed at runtime, not from a preprocessing step.
    This ensures grid consistency (no coupling between preprocessed files and
    the current model grid).

    The function loads thickness contour lines from the Canton Zurich geological
    survey (GS_GW_MAECHTIGKEIT_L layer), optionally blends with shallow zone data
    (GS_GW_LEITER_F), clips to the model boundary, and interpolates to grid cell
    centers using a two-stage algorithm:
    1. Linear interpolation for smooth interior surfaces
    2. Nearest-neighbor gap filling for areas outside the convex hull

    Data Blending Algorithm
    -----------------------
    When blend_shallow_zones=True (default), the function combines three sources:
    1. **Deep contours** (GS_GW_MAECHTIGKEIT_L): Raw LABEL values (typically 30-60m)
    2. **Shallow zones** (GS_GW_LEITER_F): GWLTYP polygon centroids mapped to
       thickness values (typically 2-20m based on zone classification). Uses
       centroids (not polygon boundaries) to produce smooth interpolation without
       sharp discontinuities at zone edges.
    3. **Boundary constraint**: Model boundary set to min_thickness to prevent
       edge extrapolation artifacts

    The deep contours dominate the interpolation pattern, while shallow zone
    centroids provide additional regional constraints for a smoother result.

    Parameters
    ----------
    gw_map_path : str or Path
        Path to the Grundwasservorkommen GeoPackage file containing thickness
        contours. Can be obtained via: download_named_file('groundwater_map_norm')
    modelgrid : flopy.discretization.VertexGrid
        DISV model grid object (from create_voronoi_grid). Must have
        xcellcenters, ycellcenters, and ncpl attributes.
    boundary_gdf : gpd.GeoDataFrame
        Model boundary polygon used for clipping contours.
    thickness_column : str, optional
        Column name containing thickness values in the contour layer.
        Default is 'LABEL' (standard for Canton Zurich data).
    contour_layer : str, optional
        Layer name for thickness contours in the GeoPackage.
        Default is 'GS_GW_MAECHTIGKEIT_L'.
    method : str, optional
        Interpolation method:
        - 'basic': Simple linear + nearest (fastest)
        - 'robust': Dense point sampling with buffering
        - 'improved': RBF interpolation with boundary constraints (recommended)
        Default is 'improved'. The improved method uses Radial Basis Function
        interpolation which produces smoother surfaces and handles sparse data
        better than linear methods.
    fallback_thickness : float, optional
        Default thickness (m) if interpolation fails completely.
        Default is 17.5 m (approximate mean for Limmat Valley).
    min_thickness : float, optional
        Minimum valid thickness in meters. Values below are clipped.
        Default is 1.0 m.
    max_thickness : float, optional
        Maximum valid thickness in meters. Values above are clipped.
        Default is 100.0 m.
    verbose : bool, optional
        Print status messages during processing. Default is True.
    blend_shallow_zones : bool, optional
        Whether to blend shallow zone data (GS_GW_LEITER_F) with deep contours.
        Default is True. Set to False for backward-compatible behavior using
        only deep contours.
    shallow_layer : str, optional
        Layer name for shallow groundwater zones in the GeoPackage.
        Default is 'GS_GW_LEITER_F'.
    gwltyp_to_thickness : dict, optional
        Mapping from GWLTYP integer codes to thickness values in meters.
        Default is DEFAULT_GWLTYP_TO_THICKNESS_M:
        {1: 2, 2: 2, 4: 10, 6: 20}
    include_boundary_constraint : bool, optional
        Whether to add model boundary as a thickness constraint (set to
        min_thickness). Helps prevent edge extrapolation artifacts.
        Default is True.

    Returns
    -------
    np.ndarray
        1D array of shape (ncpl,) with aquifer thickness at each cell center.
        Values are in meters and are guaranteed to be within [min_thickness, max_thickness].

    Notes
    -----
    This function uses existing interpolation functions from grid_utils.py:
    - interpolate_aquifer_thickness_to_grid() for 'basic' method
    - interpolate_aquifer_thickness_to_grid_robust() for 'robust' method

    The returned array is guaranteed to match modelgrid.ncpl because
    interpolation uses the same modelgrid object (no grid coupling issues).

    Graceful degradation:
    - If data file missing: returns uniform fallback_thickness
    - If layer not found: returns uniform fallback_thickness
    - If no contours in boundary: returns uniform fallback_thickness
    - If interpolation fails: returns uniform fallback_thickness
    - If shallow layer not found: continues with deep contours only (warning)
    - If GWLTYP column missing: continues with deep contours only (warning)
    - If boundary constraint fails: continues without boundary constraint (warning)

    Examples
    --------
    >>> from data_utils import download_named_file
    >>> gw_map_path = download_named_file('groundwater_map_norm', data_type='gis')
    >>> thickness = load_and_interpolate_aquifer_thickness(
    ...     gw_map_path, modelgrid, boundary_gdf
    ... )
    >>> model_bottom = model_top - thickness

    >>> # Disable blending to use only deep contours (old behavior)
    >>> thickness = load_and_interpolate_aquifer_thickness(
    ...     gw_map_path, modelgrid, boundary_gdf,
    ...     blend_shallow_zones=False
    ... )
    """
    import warnings

    gw_map_path = Path(gw_map_path)
    ncpl = modelgrid.ncpl

    # Use default GWLTYP mapping if not provided
    if gwltyp_to_thickness is None:
        gwltyp_to_thickness = DEFAULT_GWLTYP_TO_THICKNESS_M

    # Validate modelgrid has required attributes
    if not hasattr(modelgrid, 'xcellcenters') or not hasattr(modelgrid, 'ycellcenters'):
        raise ValueError("modelgrid must have xcellcenters and ycellcenters attributes")
    if not hasattr(modelgrid, 'ncpl'):
        raise ValueError("modelgrid must have ncpl attribute (DISV grid required)")

    # 1. Check if file exists
    if not gw_map_path.exists():
        warnings.warn(f"Groundwater map file not found: {gw_map_path}. Using fallback thickness.")
        if verbose:
            print(f"Warning: File not found. Using uniform thickness of {fallback_thickness} m")
        return np.full(ncpl, fallback_thickness)

    # Collect all thickness data sources into a list
    thickness_sources = []

    # 2. Load deep thickness contours (primary source)
    if verbose:
        print(f"Loading aquifer thickness data from {contour_layer}...")

    try:
        contour_gdf = gpd.read_file(gw_map_path, layer=contour_layer)
        if verbose:
            print(f"  Loaded {len(contour_gdf)} deep contour features")

        # Clip to model boundary
        try:
            contour_gdf = gpd.clip(contour_gdf, boundary_gdf)
        except Exception as e:
            warnings.warn(f"Clipping deep contours failed: {e}. Proceeding with unclipped contours.")

        if len(contour_gdf) > 0:
            if verbose:
                print(f"  {len(contour_gdf)} deep contours within model boundary")

            # Parse thickness values from column
            if thickness_column in contour_gdf.columns:
                contour_gdf['aquifer_thickness'] = pd.to_numeric(
                    contour_gdf[thickness_column], errors='coerce'
                )
                contour_gdf = contour_gdf.dropna(subset=['aquifer_thickness'])

                if len(contour_gdf) > 0:
                    if verbose:
                        print(f"  Deep contour thickness range: {contour_gdf['aquifer_thickness'].min():.1f} - "
                              f"{contour_gdf['aquifer_thickness'].max():.1f} m")
                    thickness_sources.append(contour_gdf)
                else:
                    if verbose:
                        print(f"  Warning: No valid thickness values in deep contours")
            else:
                if verbose:
                    print(f"  Warning: Column '{thickness_column}' not found in deep contours")
        else:
            if verbose:
                print(f"  Warning: No deep contours within model boundary")

    except Exception as e:
        warnings.warn(f"Could not load deep contour layer '{contour_layer}': {e}")
        if verbose:
            print(f"  Warning: Deep contour layer load failed: {e}")

    # 3. Load shallow zone data (GS_GW_LEITER_F) if blending is enabled
    if blend_shallow_zones:
        if verbose:
            print(f"Loading shallow zone data from {shallow_layer}...")

        try:
            shallow_gdf = gpd.read_file(gw_map_path, layer=shallow_layer)
            if verbose:
                print(f"  Loaded {len(shallow_gdf)} shallow zone features")

            # Clip to model boundary
            try:
                shallow_gdf = gpd.clip(shallow_gdf, boundary_gdf)
            except Exception as e:
                warnings.warn(f"Clipping shallow zones failed: {e}. Proceeding with unclipped zones.")

            if len(shallow_gdf) > 0 and 'GWLTYP' in shallow_gdf.columns:
                if verbose:
                    print(f"  {len(shallow_gdf)} shallow zones within model boundary")

                # Map GWLTYP to thickness
                shallow_gdf['aquifer_thickness'] = shallow_gdf['GWLTYP'].map(gwltyp_to_thickness)
                shallow_gdf = shallow_gdf.dropna(subset=['aquifer_thickness'])

                if len(shallow_gdf) > 0:
                    if verbose:
                        gwltyp_values = shallow_gdf['GWLTYP'].unique()
                        thickness_values = shallow_gdf['aquifer_thickness'].unique()
                        print(f"  GWLTYP values: {sorted(gwltyp_values)} -> thickness: {sorted(thickness_values)} m")

                    # Sample interior points from polygons for smoother interpolation
                    # Using a grid of points rather than just centroids provides better
                    # spatial coverage in areas without deep contour data
                    from shapely.geometry import Point

                    shallow_points = []
                    shallow_point_spacing = 200  # meters between sample points

                    for idx, row in shallow_gdf.iterrows():
                        if row.geometry is None or row.geometry.is_empty:
                            continue

                        thickness_val = row['aquifer_thickness']

                        def sample_polygon_interior(poly, spacing, thickness):
                            """Sample a grid of points within a polygon."""
                            points = []
                            minx, miny, maxx, maxy = poly.bounds

                            # Create grid of candidate points
                            x = minx
                            while x <= maxx:
                                y = miny
                                while y <= maxy:
                                    pt = Point(x, y)
                                    if poly.contains(pt):
                                        points.append({
                                            'geometry': pt,
                                            'aquifer_thickness': thickness
                                        })
                                    y += spacing
                                x += spacing

                            # Always include centroid as fallback for small polygons
                            if len(points) == 0:
                                centroid = poly.centroid
                                if poly.contains(centroid):
                                    points.append({
                                        'geometry': centroid,
                                        'aquifer_thickness': thickness
                                    })
                                else:
                                    # Centroid outside polygon, use representative point
                                    rep_pt = poly.representative_point()
                                    points.append({
                                        'geometry': rep_pt,
                                        'aquifer_thickness': thickness
                                    })
                            return points

                        try:
                            if row.geometry.geom_type == 'Polygon':
                                shallow_points.extend(
                                    sample_polygon_interior(row.geometry, shallow_point_spacing, thickness_val)
                                )
                            elif row.geometry.geom_type == 'MultiPolygon':
                                for poly in row.geometry.geoms:
                                    shallow_points.extend(
                                        sample_polygon_interior(poly, shallow_point_spacing, thickness_val)
                                    )
                        except Exception:
                            continue

                    if shallow_points:
                        shallow_points_gdf = gpd.GeoDataFrame(
                            shallow_points,
                            crs=shallow_gdf.crs
                        )
                        if verbose:
                            print(f"  Sampled {len(shallow_points_gdf)} interior points from shallow zones (spacing: {shallow_point_spacing}m)")
                        thickness_sources.append(shallow_points_gdf)
                    else:
                        if verbose:
                            print(f"  Warning: Could not sample points from shallow zone polygons")
                else:
                    if verbose:
                        print(f"  Warning: No GWLTYP values matched the mapping dictionary")
            elif 'GWLTYP' not in shallow_gdf.columns:
                warnings.warn(f"GWLTYP column not found in {shallow_layer}. Continuing without shallow zones.")
                if verbose:
                    print(f"  Warning: GWLTYP column not found in shallow layer")
            else:
                if verbose:
                    print(f"  Warning: No shallow zones within model boundary")

        except Exception as e:
            warnings.warn(f"Could not load shallow layer '{shallow_layer}': {e}. Continuing without shallow zones.")
            if verbose:
                print(f"  Warning: Shallow layer load failed: {e}")

    # 4. Add model boundary as thickness constraint
    if include_boundary_constraint:
        if verbose:
            print(f"Adding boundary constraint (thickness = {min_thickness} m)...")

        try:
            # Extract model boundary as LineString
            boundary_geom = boundary_gdf.union_all() if hasattr(boundary_gdf, 'union_all') else boundary_gdf.unary_union

            if boundary_geom.geom_type == 'Polygon':
                boundary_line = LineString(boundary_geom.exterior.coords)
                boundary_constraint = gpd.GeoDataFrame(
                    [{'geometry': boundary_line, 'aquifer_thickness': min_thickness}],
                    crs=boundary_gdf.crs
                )
                thickness_sources.append(boundary_constraint)
                if verbose:
                    print(f"  Added boundary constraint line")
            elif boundary_geom.geom_type == 'MultiPolygon':
                boundary_lines = []
                for poly in boundary_geom.geoms:
                    boundary_line = LineString(poly.exterior.coords)
                    boundary_lines.append({
                        'geometry': boundary_line,
                        'aquifer_thickness': min_thickness
                    })
                boundary_constraint = gpd.GeoDataFrame(boundary_lines, crs=boundary_gdf.crs)
                thickness_sources.append(boundary_constraint)
                if verbose:
                    print(f"  Added {len(boundary_lines)} boundary constraint lines")
            else:
                if verbose:
                    print(f"  Warning: Could not extract boundary as LineString (geom_type: {boundary_geom.geom_type})")

        except Exception as e:
            warnings.warn(f"Could not add boundary constraint: {e}. Continuing without boundary constraint.")
            if verbose:
                print(f"  Warning: Boundary constraint failed: {e}")

    # 5. Check if we have any data sources
    if len(thickness_sources) == 0:
        warnings.warn("No thickness data sources available. Using fallback thickness.")
        if verbose:
            print(f"Warning: No data sources. Using uniform thickness of {fallback_thickness} m")
        return np.full(ncpl, fallback_thickness)

    # 6. Concatenate all sources into a single GeoDataFrame
    if verbose:
        print(f"Combining {len(thickness_sources)} data sources...")

    combined_gdf = pd.concat(thickness_sources, ignore_index=True)
    combined_gdf = gpd.GeoDataFrame(combined_gdf, crs=thickness_sources[0].crs)

    if verbose:
        print(f"  Combined: {len(combined_gdf)} features")
        print(f"  Combined thickness range: {combined_gdf['aquifer_thickness'].min():.1f} - "
              f"{combined_gdf['aquifer_thickness'].max():.1f} m")

    # 7. Interpolate to grid using existing grid_utils functions
    if verbose:
        print(f"Interpolating to {ncpl} grid cells (method: {method})...")

    try:
        # Import interpolation functions from grid_utils
        from grid_utils import (
            interpolate_aquifer_thickness_to_grid,
            interpolate_aquifer_thickness_to_grid_robust,
            interpolate_aquifer_thickness_to_grid_improved,
        )

        if method == 'basic':
            thickness_result = interpolate_aquifer_thickness_to_grid(
                combined_gdf, modelgrid, thickness_column='aquifer_thickness'
            )
        elif method == 'improved':
            # RBF interpolation with boundary constraints - best for sparse data
            thickness_result = interpolate_aquifer_thickness_to_grid_improved(
                combined_gdf, modelgrid, thickness_column='aquifer_thickness',
                point_spacing=5, smoothing_factor=0.1
            )
        else:  # 'robust' (default)
            thickness_result = interpolate_aquifer_thickness_to_grid_robust(
                combined_gdf, modelgrid, thickness_column='aquifer_thickness',
                point_spacing=5
            )

    except ImportError:
        # Fallback: implement basic interpolation inline
        if verbose:
            print("  Note: grid_utils not available, using inline interpolation")
        thickness_result = _interpolate_thickness_inline(combined_gdf, modelgrid)
    except Exception as e:
        warnings.warn(f"Interpolation failed: {e}. Using fallback thickness.")
        if verbose:
            print(f"Warning: Interpolation error. Using uniform thickness of {fallback_thickness} m")
        return np.full(ncpl, fallback_thickness)

    # 8. Convert to 1D array for DISV grid
    thickness = thickness_result.ravel() if thickness_result.ndim > 1 else thickness_result

    # 9. Validate shape
    if len(thickness) != ncpl:
        warnings.warn(f"Shape mismatch: got {len(thickness)}, expected {ncpl}. Using fallback.")
        if verbose:
            print(f"Warning: Shape mismatch. Using uniform thickness of {fallback_thickness} m")
        return np.full(ncpl, fallback_thickness)

    # 10. Clip to valid range
    thickness = np.clip(thickness, min_thickness, max_thickness)

    # 11. Handle any remaining NaNs
    nan_count = np.isnan(thickness).sum()
    if nan_count > 0:
        mean_thickness = np.nanmean(thickness)
        if verbose:
            print(f"  Filling {nan_count} NaN cells with mean ({mean_thickness:.1f} m)")
        thickness = np.where(np.isnan(thickness), mean_thickness, thickness)

    if verbose:
        print(f"  Result: {thickness.min():.1f} - {thickness.max():.1f} m, mean {thickness.mean():.1f} m")

    return thickness


def _interpolate_thickness_inline(contour_gdf: gpd.GeoDataFrame, modelgrid) -> np.ndarray:
    """
    Inline fallback interpolation when grid_utils is not available.

    Uses scipy.interpolate.griddata with linear + nearest-neighbor two-stage approach.
    Handles Point, LineString, and MultiLineString geometries.
    """
    from scipy.interpolate import griddata

    # Extract points from geometries (supports Point, LineString, MultiLineString)
    points_for_interp = []
    for idx, row in contour_gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue

        thickness_value = row['aquifer_thickness']

        if row.geometry.geom_type == 'Point':
            x, y = row.geometry.x, row.geometry.y
            points_for_interp.append((x, y, thickness_value))
        elif row.geometry.geom_type == 'MultiPoint':
            for point in row.geometry.geoms:
                points_for_interp.append((point.x, point.y, thickness_value))
        elif row.geometry.geom_type == 'MultiLineString':
            for line in row.geometry.geoms:
                for x, y in line.coords:
                    points_for_interp.append((x, y, thickness_value))
        elif row.geometry.geom_type == 'LineString':
            for x, y in row.geometry.coords:
                points_for_interp.append((x, y, thickness_value))

    if len(points_for_interp) == 0:
        raise ValueError("No valid points extracted from contour geometries")

    points_array = np.array(points_for_interp)

    # Get grid cell centers
    grid_x = modelgrid.xcellcenters
    grid_y = modelgrid.ycellcenters

    # Flatten if needed (for DISV grids these are already 1D)
    if grid_x.ndim > 1:
        grid_x = grid_x.flatten()
        grid_y = grid_y.flatten()

    # Stage 1: Linear interpolation
    interpolated = griddata(
        points_array[:, :2],
        points_array[:, 2],
        (grid_x, grid_y),
        method='linear'
    )

    # Stage 2: Fill NaN values with nearest neighbor
    nan_mask = np.isnan(interpolated)
    if np.any(nan_mask):
        nearest_values = griddata(
            points_array[:, :2],
            points_array[:, 2],
            (grid_x[nan_mask], grid_y[nan_mask]),
            method='nearest'
        )
        interpolated[nan_mask] = nearest_values

    return interpolated


# ---------------------------------------------------------------------------
# Utility helpers for NB8 (model application)
# ---------------------------------------------------------------------------

def _cellid_to_flat(cellid):
    """Extract flat cell index from an MF6 cellid (tuple or int)."""
    return cellid[-1] if isinstance(cellid, tuple) else cellid


def compare_water_balances(
    budget_a: pd.DataFrame,
    budget_b: pd.DataFrame,
    label_a: str = "Baseline",
    label_b: str = "Scenario",
    threshold: float = 1.0,
) -> pd.DataFrame:
    """
    Compare two water balance DataFrames produced by ``format_budget_summary``.

    Iterates over shared budget components, skips TOTAL / DISCREPANCY /
    PERCENT ERROR rows, and prints a formatted table of changes.

    Parameters
    ----------
    budget_a, budget_b : pandas.DataFrame
        Water-balance DataFrames (index = component name, columns include
        'Inflow (m3/d)', 'Outflow (m3/d)', 'Net (m3/d)').
    label_a, label_b : str, optional
        Labels shown in the header.
    threshold : float, optional
        Only show components where |ΔInflow| or |ΔOutflow| exceeds this
        value (m³/d).  Default 1.0.

    Returns
    -------
    pandas.DataFrame
        DataFrame with columns ΔInflow, ΔOutflow, ΔNet for every component
        that exceeds the threshold.
    """
    skip = {'TOTAL', 'DISCREPANCY', 'PERCENT ERROR'}

    print("\n" + "=" * 60)
    print(f"Water Balance Comparison: {label_a} vs {label_b}")
    print("=" * 60)

    rows = []
    for component in budget_a.index:
        comp_str = component.decode() if isinstance(component, bytes) else str(component)
        if comp_str.strip() in skip:
            continue
        if component not in budget_b.index:
            continue

        bl_in = budget_a.loc[component, 'Inflow (m3/d)']
        bl_out = budget_a.loc[component, 'Outflow (m3/d)']
        sc_in = budget_b.loc[component, 'Inflow (m3/d)']
        sc_out = budget_b.loc[component, 'Outflow (m3/d)']

        if not (isinstance(bl_in, (int, float)) and isinstance(sc_in, (int, float))):
            continue

        d_in = sc_in - bl_in
        d_out = sc_out - bl_out
        d_net = (sc_in - sc_out) - (bl_in - bl_out)

        if abs(d_in) > threshold or abs(d_out) > threshold:
            print(f"  {comp_str:20s}  ΔInflow: {d_in:+8.1f}"
                  f"  ΔOutflow: {d_out:+8.1f}  ΔNet: {d_net:+8.1f} m³/d")
            rows.append({
                'Component': comp_str.strip(),
                'ΔInflow (m3/d)': round(d_in, 1),
                'ΔOutflow (m3/d)': round(d_out, 1),
                'ΔNet (m3/d)': round(d_net, 1),
            })

    df = pd.DataFrame(rows)
    if len(df) > 0:
        df = df.set_index('Component')
    return df


def load_prt_results(
    trackcsv_path: Union[str, Path],
    modelgrid,
    well_zone: int = 1,
    river_zone: int = 2,
) -> Dict[str, Any]:
    """
    Load PRT particle-tracking results and classify termination.

    Parameters
    ----------
    trackcsv_path : str or Path
        Absolute path to the ``*.trk.csv`` file written by PRT.
    modelgrid : flopy.discretization.Grid
        Model grid of the PRT model (needed for coordinate transform).
    well_zone : int, optional
        izone value for well cells (default 1).
    river_zone : int, optional
        izone value for river cells (default 2).

    Returns
    -------
    dict
        ``prt_df``       – full DataFrame with ``x_world``, ``y_world``
        ``terminal``     – last record per particle (groupby irpt)
        ``captured_ids`` – set of particle IDs captured by well
        ``captured_df``  – pathlines of captured particles only
        ``travel_times`` – Series of travel times for captured particles
    """
    trackcsv_path = Path(trackcsv_path)
    prt_df = pd.read_csv(trackcsv_path)

    # Transform model-local coordinates to world CRS
    x_world, y_world = modelgrid.get_coords(
        prt_df['x'].values, prt_df['y'].values,
    )
    prt_df['x_world'] = x_world
    prt_df['y_world'] = y_world

    # Terminal records (last per particle)
    terminal = prt_df.groupby('irpt').last()
    captured_ids = set(terminal.loc[terminal['izone'] == well_zone].index)
    captured_df = prt_df[prt_df['irpt'].isin(captured_ids)].copy()

    travel_times = terminal.loc[terminal['izone'] == well_zone, 't']

    n_river = int((terminal['izone'] == river_zone).sum())
    n_other = int((~terminal['izone'].isin([well_zone, river_zone])).sum())

    print(f"PRT completed: {prt_df['irpt'].nunique()} particles tracked")
    print(f"  Captured by well: {len(captured_ids)}")
    print(f"  Reached river:    {n_river}")
    print(f"  Other termination: {n_other}")
    if len(captured_ids) > 0:
        print(f"\nTravel times to well:")
        print(f"  Min:    {travel_times.min():.1f} days")
        print(f"  Median: {travel_times.median():.1f} days")
        print(f"  Max:    {travel_times.max():.1f} days")

    return {
        'prt_df': prt_df,
        'terminal': terminal,
        'captured_ids': captured_ids,
        'captured_df': captured_df,
        'travel_times': travel_times,
    }


def delineate_protection_zones(
    captured_df: pd.DataFrame,
    terminal: pd.DataFrame,
    well_xy: tuple,
    s2_days: float = 10.0,
    s1_radius: float = 10.0,
    s3_ratio: float = 0.2,
    well_zone: int = 1,
) -> Dict[str, Any]:
    """
    Delineate Swiss groundwater protection zones from PRT results.

    Computes S1 (fixed radius), S2 (travel-time isochrone), and S3
    (full capture zone envelope) from forward-tracked particle pathlines.

    Parameters
    ----------
    captured_df : pandas.DataFrame
        Pathline records for particles captured by the well.  Must contain
        ``irpt``, ``x_world``, ``y_world`` columns.
    terminal : pandas.DataFrame
        Terminal (last) record per particle, indexed by ``irpt``.  Must
        contain ``izone`` and ``t`` columns.
    well_xy : tuple of (float, float)
        Well location in world coordinates (x, y).
    s2_days : float, optional
        Travel-time threshold for S2 zone (days).  Default 10.
    s1_radius : float, optional
        Radius for S1 zone (m).  Default 10.
    s3_ratio : float, optional
        Concavity ratio for concave hull of S3 zone.  Default 0.2.
    well_zone : int, optional
        izone value assigned to well cells in MIP.  Default 1.

    Returns
    -------
    dict
        ``s1_geometry``  – shapely Point buffer (circle)
        ``s2_envelope``  – convex hull of S2 pathline points (or None)
        ``s3_envelope``  – concave hull of all captured pathline points
        ``s2_ids``       – set of particle IDs within S2
        ``s2_max_extent``– maximum distance from well for S2 particles (m)
        ``s2_area``      – area of S2 envelope (m²)
        ``s3_area``      – area of S3 envelope (m²)
    """
    from shapely.geometry import Point as _Point
    from shapely.geometry import MultiPoint as _MultiPoint
    from shapely import concave_hull as _concave_hull

    well_x, well_y = well_xy

    # S1: fixed-radius buffer
    s1_geometry = _Point(well_x, well_y).buffer(s1_radius)

    # S2: particles reaching well within s2_days
    travel_to_well = terminal.loc[terminal['izone'] == well_zone, 't']
    s2_ids = set(travel_to_well[travel_to_well <= s2_days].index)

    s2_envelope = None
    s2_max_extent = 0.0
    s2_area = 0.0

    if len(s2_ids) > 0:
        s2_pathlines = captured_df[captured_df['irpt'].isin(s2_ids)]
        s2_pts_x = s2_pathlines['x_world'].values
        s2_pts_y = s2_pathlines['y_world'].values
        s2_dist = np.sqrt((s2_pts_x - well_x)**2 + (s2_pts_y - well_y)**2)
        s2_max_extent = float(s2_dist.max())

        s2_cloud = _MultiPoint(list(zip(s2_pts_x, s2_pts_y)))
        s2_envelope = s2_cloud.convex_hull
        s2_area = float(s2_envelope.area) if s2_envelope and not s2_envelope.is_empty else 0.0

    # S3: concave envelope of full capture zone
    s3_pts_x = captured_df['x_world'].values
    s3_pts_y = captured_df['y_world'].values
    s3_cloud = _MultiPoint(list(zip(s3_pts_x, s3_pts_y)))
    s3_envelope = _concave_hull(s3_cloud, ratio=s3_ratio)
    s3_area = float(s3_envelope.area) if s3_envelope and not s3_envelope.is_empty else 0.0

    print(f"Protection zone delineation:")
    print(f"  S1: {s1_radius:.0f} m radius")
    print(f"  S2: {len(s2_ids)} particles within {s2_days:.0f} days"
          f" (max extent {s2_max_extent:.0f} m, area {s2_area:.0f} m²)")
    print(f"  S3: full capture zone (area {s3_area:.0f} m²)")

    return {
        's1_geometry': s1_geometry,
        's2_envelope': s2_envelope,
        's3_envelope': s3_envelope,
        's2_ids': s2_ids,
        's2_max_extent': s2_max_extent,
        's2_area': s2_area,
        's3_area': s3_area,
    }


def build_prt_model(
    gwf,
    porosity: float = 0.15,
    well_cells: Optional[List[int]] = None,
    tracking_time: float = 365.0,
    workspace: Optional[Union[str, Path]] = None,
    sim_name: str = "prt_model",
) -> Dict[str, Any]:
    """
    Build a MODFLOW 6 PRT simulation linked to a GWF model.

    Creates one particle per active cell using ``representative_point()``
    to guarantee release points lie inside clipped Voronoi cells.  River
    cells get izone = 2; well cells get izone = 1.

    The simulation is written but **not** run — the caller should run it
    so they can handle success / failure.

    Parameters
    ----------
    gwf : flopy.mf6.ModflowGwf
        Completed GWF model (must have been written and run, so that
        ``.hds`` and ``.cbc`` files exist in ``gwf.sim_path``).
    porosity : float, optional
        Effective porosity for particle tracking.  Default 0.15.
    well_cells : list of int, optional
        Flat cell indices to assign izone = 1 (well termination zone).
    tracking_time : float, optional
        Maximum forward tracking time in days.  Default 365.
    workspace : str or Path, optional
        Directory for the PRT files.  If *None*, defaults to
        ``<gwf.sim_path>/prt``.
    sim_name : str, optional
        MF6 simulation / model name.  Default ``"prt_model"``.

    Returns
    -------
    dict
        ``prt_sim``       – MFSimulation
        ``prt``           – ModflowPrt model
        ``trackcsv_path`` – Path to the track CSV (exists after run)
        ``n_particles``   – number of release points
    """
    import shutil
    from shapely.geometry import Polygon as ShapelyPolygon
    import flopy as _flopy

    gwf_ws = Path(gwf.model_ws)
    if workspace is None:
        workspace = gwf_ws / 'prt'
    workspace = Path(workspace)

    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    # --- Grid info from GWF ---
    disv_pkg = gwf.get_package('DISV')
    ncpl = int(disv_pkg.ncpl.data)
    ref_modelgrid = gwf.modelgrid

    # --- izone: well = 1, river = 2 ---
    izone = np.zeros((1, ncpl), dtype=int)
    if well_cells:
        for wc in well_cells:
            izone[0, wc] = 1
    try:
        riv_pkg = gwf.get_package('RIV')
        for rec in riv_pkg.stress_period_data.get_data(0):
            cell_idx = _cellid_to_flat(rec['cellid'])
            izone[0, cell_idx] = 2
    except Exception:
        pass  # no RIV package — skip

    # --- PRP: one particle per cell, using representative_point ---
    release_x = np.zeros(ncpl)
    release_y = np.zeros(ncpl)
    for j in range(ncpl):
        verts = ref_modelgrid.get_cell_vertices(j)
        rp = ShapelyPolygon(verts).representative_point()
        release_x[j] = rp.x
        release_y[j] = rp.y

    prt_data = [
        (i, 0, i, float(release_x[i]), float(release_y[i]), 0.5)
        for i in range(ncpl)
    ]

    trackcsv_file = f'{sim_name}.trk.csv'

    # --- Build simulation ---
    prt_sim = _flopy.mf6.MFSimulation(
        sim_name=sim_name, exe_name='mf6', sim_ws=str(workspace),
    )
    _flopy.mf6.ModflowTdis(
        prt_sim, time_units='DAYS', nper=1,
        perioddata=[(tracking_time, 1, 1)],
    )

    prt = _flopy.mf6.ModflowPrt(prt_sim, modelname=sim_name)

    _flopy.mf6.ModflowPrtdisv(
        prt,
        nlay=disv_pkg.nlay.data,
        ncpl=disv_pkg.ncpl.data,
        nvert=disv_pkg.nvert.data,
        top=disv_pkg.top.array,
        botm=disv_pkg.botm.array,
        vertices=disv_pkg.vertices.array,
        cell2d=disv_pkg.cell2d.array,
    )
    _flopy.mf6.ModflowPrtmip(prt, porosity=porosity, izone=izone)

    _flopy.mf6.ModflowPrtprp(
        prt,
        nreleasepts=len(prt_data),
        packagedata=prt_data,
        local_z=True,
        perioddata={0: ['FIRST']},
        exit_solve_tolerance=1e-5,
        extend_tracking=True,
        stoptraveltime=tracking_time,
    )

    _flopy.mf6.ModflowPrtoc(
        prt,
        budget_filerecord=[f'{sim_name}.cbc'],
        track_filerecord=[f'{sim_name}.trk'],
        trackcsv_filerecord=[trackcsv_file],
        saverecord=[('BUDGET', 'ALL')],
    )

    # FMI — relative paths to GWF head/budget/grid files
    gwf_sim_name = gwf.name
    gwf_hds = gwf_ws / f'{gwf_sim_name}.hds'
    gwf_cbc = gwf_ws / f'{gwf_sim_name}.cbc'
    # Find the binary grid file (.grb) — needed so PRT can read ICELLTYPE
    # when LOCAL_Z release coordinates are used in the PRP package.
    grb_candidates = list(gwf_ws.glob(f'{gwf_sim_name}*.grb'))
    if not grb_candidates:
        grb_candidates = list(gwf_ws.glob('*.grb'))
    fmi_pd = [
        ('GWFHEAD',   os.path.relpath(gwf_hds, workspace)),
        ('GWFBUDGET', os.path.relpath(gwf_cbc, workspace)),
    ]
    if grb_candidates:
        gwf_grb = grb_candidates[0]
        fmi_pd.append(
            ('GWFGRID', os.path.relpath(gwf_grb, workspace))
        )
    _flopy.mf6.ModflowPrtfmi(prt, packagedata=fmi_pd)

    # EMS
    ems = _flopy.mf6.ModflowEms(prt_sim, filename=f'{sim_name}.ems')
    prt_sim.register_solution_package(ems, [prt.name])

    # Write (do NOT run)
    prt_sim.write_simulation()

    print(f"PRT model written to: {workspace}")
    print(f"  Particles: {len(prt_data)} (one per cell)")
    print(f"  Porosity: {porosity}")
    print(f"  Max tracking time: {tracking_time} days")
    print(f"  Zones: well = 1, river = 2")

    return {
        'prt_sim': prt_sim,
        'prt': prt,
        'trackcsv_path': workspace / trackcsv_file,
        'n_particles': len(prt_data),
    }


def generate_refined_grid(
    gwf,
    boundary_gdf: gpd.GeoDataFrame,
    river_gdf: gpd.GeoDataFrame,
    refine_points: Union[List[tuple], gpd.GeoDataFrame],
    head_array: np.ndarray,
    refine_radius: float = 200.0,
    base_cell_size: float = 50.0,
    refined_cell_size: float = 10.0,
    well_data: Optional[List[tuple]] = None,
    baseline_head_array: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Build a locally-refined Voronoi grid and interpolate/reassign all
    model inputs from an existing coarse GWF model onto it.

    This performs every step that depends on geometry — grid generation,
    nearest-neighbour interpolation of arrays, and spatial reassignment of
    CHD / RIV / WEL boundary conditions — and returns a frozen "spec" dict
    of plain arrays/lists with no MF6 objects. :func:`assemble_gwf_from_spec`
    turns that spec into an actual simulation.

    Parameters
    ----------
    gwf : flopy.mf6.ModflowGwf
        Source (coarse) GWF model — must have DISV, NPF, RCHA, CHD, RIV.
    boundary_gdf : geopandas.GeoDataFrame
        Model domain polygon (used for grid generation).
    river_gdf : geopandas.GeoDataFrame
        River polygons used to identify RIV cells in the refined grid.
        Must intersect with ``boundary_gdf``.
    refine_points : list of (x, y) tuples **or** GeoDataFrame with Points
        Locations around which the grid is refined.  Each point gets a
        circular buffer of *refine_radius*.
    head_array : numpy.ndarray
        Head array from the coarse model (used as starting heads on the
        refined grid).  Shape must match the coarse DISV grid.
    refine_radius : float, optional
        Radius of refinement circle around each point (m).  Default 200.
    base_cell_size : float, optional
        Base Voronoi cell size (m).  Default 50.
    refined_cell_size : float, optional
        Cell size inside refinement zones (m).  Default 10.
    well_data : list of (x, y, rate) tuples, optional
        Well locations and rates to add via WEL package.
    baseline_head_array : numpy.ndarray, optional
        Head array from the *coarse* baseline model (before scenario
        changes).  When provided, it is interpolated onto the refined grid
        via nearest-neighbour and returned as ``baseline_heads``.

    Returns
    -------
    dict
        Plain-array spec consumed by :func:`assemble_gwf_from_spec` — no
        live MF6 objects, no VertexGrid: ``gridprops``, ``ncpl``, ``top``,
        ``botm``, ``k``, ``rch``, ``strt``, ``idomain``, ``chd_cellid``,
        ``chd_head``, ``riv_cellid``, ``riv_stage``, ``riv_cond``,
        ``riv_rbot``, ``wel_cellid``, ``wel_rate``, ``well_cells``,
        ``refine_radius_used``, ``crs``, and (optionally)
        ``baseline_heads``.
    """
    from scipy.interpolate import NearestNDInterpolator
    from shapely.geometry import Point as ShapelyPoint
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.prepared import prep as shapely_prep
    import disv_grid_utils as dgu

    # ------------------------------------------------------------------
    # 1. Normalise refine_points → list of (x, y)
    # ------------------------------------------------------------------
    if isinstance(refine_points, gpd.GeoDataFrame):
        pts = [(g.x, g.y) for g in refine_points.geometry]
    else:
        pts = list(refine_points)

    circles = [ShapelyPoint(x, y).buffer(refine_radius) for x, y in pts]
    refine_gdf = gpd.GeoDataFrame(
        geometry=circles, crs=boundary_gdf.crs,
    )

    # ------------------------------------------------------------------
    # 2. Create refined Voronoi grid
    # ------------------------------------------------------------------
    print("Building refined Voronoi grid...")
    base_grid = dgu.create_disv_from_boundary(
        boundary_gdf=boundary_gdf, cell_size=base_cell_size,
        crs=str(boundary_gdf.crs),
    )
    refined = dgu.refine_grid_locally(
        base_grid=base_grid,
        refinement_gdf=refine_gdf,
        refined_cell_size=refined_cell_size,
        boundary_gdf=boundary_gdf,
    )

    gridprops = refined['disv_gridprops']
    ncpl = refined['ncpl']
    mg_ref = refined['modelgrid']
    xc_ref = mg_ref.xcellcenters
    yc_ref = mg_ref.ycellcenters
    print(f"Refined grid: {ncpl} cells")

    # ------------------------------------------------------------------
    # 3. Interpolate properties from coarse grid
    # ------------------------------------------------------------------
    coarse_modelgrid = gwf.modelgrid
    xc_orig = coarse_modelgrid.xcellcenters
    yc_orig = coarse_modelgrid.ycellcenters

    disv_orig = gwf.get_package('DISV')
    idomain_orig = disv_orig.idomain.array.flatten()
    top_orig = disv_orig.top.array.flatten()
    botm_orig = disv_orig.botm.array.flatten()

    active = idomain_orig > 0
    src_pts = list(zip(xc_orig[active], yc_orig[active]))

    k_orig = gwf.npf.k.array.flatten()
    k_ref = NearestNDInterpolator(src_pts, k_orig[active])(xc_ref, yc_ref)
    top_ref = NearestNDInterpolator(src_pts, top_orig[active])(xc_ref, yc_ref)
    botm_ref = NearestNDInterpolator(src_pts, botm_orig[active])(xc_ref, yc_ref)

    head_flat = head_array.flatten() if head_array.ndim > 1 else head_array
    strt_ref = NearestNDInterpolator(src_pts, head_flat[active])(xc_ref, yc_ref)
    strt_ref = np.maximum(strt_ref, botm_ref + 0.01)

    # Optional: interpolate baseline heads onto refined grid
    bl_heads_ref = None
    if baseline_head_array is not None:
        bl_flat = (baseline_head_array.flatten()
                   if baseline_head_array.ndim > 1 else baseline_head_array)
        bl_heads_ref = NearestNDInterpolator(
            src_pts, bl_flat[active],
        )(xc_ref, yc_ref)

    rch_data = gwf.get_package('RCHA').recharge.get_data()
    rch_vals = (list(rch_data.values())[0] if isinstance(rch_data, dict)
                else rch_data)
    rch_ref = NearestNDInterpolator(
        src_pts, rch_vals.flatten()[active],
    )(xc_ref, yc_ref)

    # ------------------------------------------------------------------
    # 4. CHD transfer
    # ------------------------------------------------------------------
    chd_orig = gwf.get_package('CHD')
    chd_data = chd_orig.stress_period_data.get_data(0)
    chd_xy = np.array([
        (xc_orig[_cellid_to_flat(r['cellid'])],
         yc_orig[_cellid_to_flat(r['cellid'])])
        for r in chd_data
    ])
    head_nn = NearestNDInterpolator(
        chd_xy, [r['head'] for r in chd_data],
    )

    chd_spd = []
    for r in chd_data:
        ox, oy = xc_orig[_cellid_to_flat(r['cellid'])], yc_orig[_cellid_to_flat(r['cellid'])]
        dists = np.sqrt((xc_ref - ox)**2 + (yc_ref - oy)**2)
        near = np.where(dists < 30)[0]
        for j in near:
            chd_spd.append(((0, int(j)), float(head_nn(xc_ref[j], yc_ref[j]))))

    seen = set()
    chd_dedup = []
    for rec in chd_spd:
        if rec[0] not in seen:
            seen.add(rec[0])
            chd_dedup.append(rec)
    chd_cellid = [rec[0] for rec in chd_dedup]
    chd_head = [rec[1] for rec in chd_dedup]
    print(f"CHD cells: {len(chd_dedup)}")

    # ------------------------------------------------------------------
    # 5. RIV transfer
    # ------------------------------------------------------------------
    riv_orig = gwf.get_package('RIV').stress_period_data.get_data(0)
    riv_xy = np.array([
        (xc_orig[_cellid_to_flat(r['cellid'])],
         yc_orig[_cellid_to_flat(r['cellid'])])
        for r in riv_orig
    ])
    stage_nn = NearestNDInterpolator(riv_xy, [r['stage'] for r in riv_orig])
    rbot_nn = NearestNDInterpolator(riv_xy, [r['rbot'] for r in riv_orig])
    riv_cond_orig = np.array([r['cond'] for r in riv_orig])

    orig_riv_areas = np.array([
        ShapelyPolygon(coarse_modelgrid.get_cell_vertices(
            _cellid_to_flat(r['cellid'])
        )).area
        for r in riv_orig
    ])

    river_union = river_gdf[
        river_gdf.intersects(boundary_gdf.geometry.iloc[0])
    ].geometry.union_all()
    river_prep = shapely_prep(river_union)

    riv_cellid = []
    riv_stage = []
    riv_cond = []
    riv_rbot = []
    for i in range(ncpl):
        if river_prep.contains(ShapelyPoint(xc_ref[i], yc_ref[i])):
            dists = (riv_xy[:, 0] - xc_ref[i])**2 + (riv_xy[:, 1] - yc_ref[i])**2
            j = np.argmin(dists)
            area_new = ShapelyPolygon(mg_ref.get_cell_vertices(i)).area
            cond_scaled = riv_cond_orig[j] * area_new / orig_riv_areas[j]
            riv_cellid.append((0, i))
            riv_stage.append(float(stage_nn(xc_ref[i], yc_ref[i])))
            riv_cond.append(float(cond_scaled))
            riv_rbot.append(float(rbot_nn(xc_ref[i], yc_ref[i])))
    print(f"RIV cells: {len(riv_cellid)}")

    # ------------------------------------------------------------------
    # 6. WEL
    # ------------------------------------------------------------------
    well_cells_out = []
    wel_cellid = []
    wel_rate = []
    if well_data:
        for wx, wy, rate in well_data:
            wc = int(np.argmin((xc_ref - wx)**2 + (yc_ref - wy)**2))
            wel_cellid.append((0, wc))
            wel_rate.append(rate)
            well_cells_out.append(wc)
        print(f"WEL cells: {len(wel_cellid)}")

    spec: Dict[str, Any] = {
        'gridprops': gridprops,
        'ncpl': ncpl,
        'top': top_ref,
        'botm': botm_ref,
        'k': k_ref,
        'rch': rch_ref,
        'strt': strt_ref,
        'idomain': np.ones(ncpl, dtype=int),
        'chd_cellid': chd_cellid,
        'chd_head': chd_head,
        'riv_cellid': riv_cellid,
        'riv_stage': riv_stage,
        'riv_cond': riv_cond,
        'riv_rbot': riv_rbot,
        'wel_cellid': wel_cellid,
        'wel_rate': wel_rate,
        'well_cells': well_cells_out,
        'refine_radius_used': refine_radius,
        'crs': str(boundary_gdf.crs),
    }
    if bl_heads_ref is not None:
        spec['baseline_heads'] = bl_heads_ref
    return spec


def assemble_gwf_from_spec(
    spec: Dict[str, Any],
    workspace: Union[str, Path],
    sim_name: str = "refined_model",
) -> Dict[str, Any]:
    """
    Build, write, and run an MF6 GWF simulation from a frozen grid spec.

    Pure MF6 construction — no Triangle/Voronoi grid generation, no
    NearestND interpolation, no spatial (point-in-polygon / nearest)
    reassignment happens here.  *spec* is the frozen plain-array dict
    produced by :func:`generate_refined_grid`; every required key is
    accessed directly (no defaulting) so a spec missing a key fails with
    a ``KeyError`` before anything is built.

    Parameters
    ----------
    spec : dict
        Grid/property/boundary-condition spec from
        :func:`generate_refined_grid`.
    workspace : str or Path
        Directory for the refined simulation files (must already exist).
    sim_name : str, optional
        MF6 simulation / model name.

    Returns
    -------
    dict
        ``sim``            – MFSimulation
        ``gwf``            – ModflowGwf (refined)
        ``modelgrid``      – refined VertexGrid
        ``gridprops``      – DISV grid properties dict
        ``ncpl``           – cells per layer
        ``heads``          – 1-D head array from the run
        ``well_cells``     – list of flat cell indices (one per well_data entry)
        ``baseline_heads`` – 1-D head array on refined grid (only when
                             *spec* contains ``baseline_heads``)
    """
    import flopy as _flopy

    workspace = Path(workspace)
    gridprops = spec['gridprops']
    ncpl = spec['ncpl']

    # ------------------------------------------------------------------
    # 1. Build GWF simulation
    # ------------------------------------------------------------------
    ref_sim = _flopy.mf6.MFSimulation(
        sim_name=sim_name, exe_name='mf6', sim_ws=str(workspace),
    )
    _flopy.mf6.ModflowTdis(
        ref_sim, time_units='DAYS', nper=1, perioddata=[(1.0, 1, 1)],
    )
    # Keep the refined solver aligned with the course NEWTON policy.
    _flopy.mf6.ModflowIms(
        ref_sim,
        **GWF_NEWTON_IMS_OPTIONS,
    )

    ref_gwf = _flopy.mf6.ModflowGwf(
        ref_sim, modelname=sim_name, save_flows=True,
        newtonoptions=GWF_NEWTON_OPTIONS,
    )
    _flopy.mf6.ModflowGwfdisv(
        ref_gwf, nlay=1, ncpl=ncpl, nvert=gridprops['nvert'],
        top=spec['top'], botm=[spec['botm']], idomain=[spec['idomain']],
        vertices=gridprops['vertices'], cell2d=gridprops['cell2d'],
    )
    _flopy.mf6.ModflowGwfnpf(
        ref_gwf, icelltype=1, k=spec['k'], save_flows=True,
        save_specific_discharge=True, save_saturation=True,
    )
    _flopy.mf6.ModflowGwfic(ref_gwf, strt=spec['strt'])
    _flopy.mf6.ModflowGwfrcha(ref_gwf, recharge=spec['rch'])

    # ------------------------------------------------------------------
    # 2. CHD / RIV / WEL packages — built from frozen cellid/value arrays
    # ------------------------------------------------------------------
    chd_spd = list(zip(spec['chd_cellid'], spec['chd_head']))
    _flopy.mf6.ModflowGwfchd(ref_gwf, stress_period_data=chd_spd)

    riv_spd = list(zip(
        spec['riv_cellid'], spec['riv_stage'], spec['riv_cond'], spec['riv_rbot'],
    ))
    _flopy.mf6.ModflowGwfriv(ref_gwf, stress_period_data=riv_spd)

    wel_cellid = spec['wel_cellid']
    if wel_cellid:
        wel_spd = list(zip(wel_cellid, spec['wel_rate']))
        _flopy.mf6.ModflowGwfwel(ref_gwf, stress_period_data=wel_spd)

    # ------------------------------------------------------------------
    # 3. OC, write, run
    # ------------------------------------------------------------------
    _flopy.mf6.ModflowGwfoc(
        ref_gwf,
        head_filerecord=[f'{sim_name}.hds'],
        budget_filerecord=[f'{sim_name}.cbc'],
        saverecord=[('HEAD', 'ALL'), ('BUDGET', 'ALL')],
    )

    print("Running refined GWF model...")
    ref_sim.write_simulation()
    success, _ = ref_sim.run_simulation(silent=True)
    if not success:
        raise RuntimeError(
            "Refined GWF model failed — check listing file in "
            f"{workspace}"
        )

    heads = ref_gwf.output.head().get_data().flatten()
    crs = spec.get('crs')
    if crs is not None:
        ref_gwf.modelgrid.set_coord_info(crs=crs)
    print(f"Refined model completed. Head range: "
          f"{heads.min():.2f} – {heads.max():.2f} m")

    result = {
        'sim': ref_sim,
        'gwf': ref_gwf,
        'modelgrid': ref_gwf.modelgrid,
        'gridprops': gridprops,
        'ncpl': ncpl,
        'heads': heads,
        'well_cells': spec['well_cells'],
    }
    if 'baseline_heads' in spec:
        result['baseline_heads'] = spec['baseline_heads']
    return result


def build_refined_gwf_model(
    gwf,
    boundary_gdf: gpd.GeoDataFrame,
    river_gdf: gpd.GeoDataFrame,
    refine_points: Union[List[tuple], gpd.GeoDataFrame],
    head_array: np.ndarray,
    workspace: Union[str, Path],
    refine_radius: float = 200.0,
    base_cell_size: float = 50.0,
    refined_cell_size: float = 10.0,
    well_data: Optional[List[tuple]] = None,
    sim_name: str = "refined_model",
    baseline_head_array: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Build and run a locally-refined GWF model from an existing coarse model.

    Creates a new Voronoi grid with refinement zones around each point in
    *refine_points*, interpolates all properties from the coarse model via
    nearest-neighbour, transfers CHD / RIV / WEL boundary conditions, and
    runs the simulation.

    Thin wrapper around :func:`generate_refined_grid` (spatial/interpolation
    work) followed by :func:`assemble_gwf_from_spec` (pure MF6 construction).

    Parameters
    ----------
    gwf : flopy.mf6.ModflowGwf
        Source (coarse) GWF model — must have DISV, NPF, RCHA, CHD, RIV.
    boundary_gdf : geopandas.GeoDataFrame
        Model domain polygon (used for grid generation).
    river_gdf : geopandas.GeoDataFrame
        River polygons used to identify RIV cells in the refined grid.
        Must intersect with ``boundary_gdf``.
    refine_points : list of (x, y) tuples **or** GeoDataFrame with Points
        Locations around which the grid is refined.  Each point gets a
        circular buffer of *refine_radius*.
    head_array : numpy.ndarray
        Head array from the coarse model (used as starting heads on the
        refined grid).  Shape must match the coarse DISV grid.
    workspace : str or Path
        Directory for the refined simulation files.
    refine_radius : float, optional
        Radius of refinement circle around each point (m).  Default 200.
    base_cell_size : float, optional
        Base Voronoi cell size (m).  Default 50.
    refined_cell_size : float, optional
        Cell size inside refinement zones (m).  Default 10.
    well_data : list of (x, y, rate) tuples, optional
        Well locations and rates to add via WEL package.
    sim_name : str, optional
        MF6 simulation / model name.
    baseline_head_array : numpy.ndarray, optional
        Head array from the *coarse* baseline model (before scenario
        changes).  When provided, it is interpolated onto the refined grid
        via nearest-neighbour and returned as ``baseline_heads``.

    Returns
    -------
    dict
        ``sim``            – MFSimulation
        ``gwf``            – ModflowGwf (refined)
        ``modelgrid``      – refined VertexGrid
        ``gridprops``      – DISV grid properties dict
        ``ncpl``           – cells per layer
        ``heads``          – 1-D head array from the run
        ``well_cells``     – list of flat cell indices (one per well_data entry)
        ``baseline_heads`` – 1-D head array on refined grid (only when
                             *baseline_head_array* is given)
    """
    import shutil

    workspace_path = Path(workspace)
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True)

    spec = generate_refined_grid(
        gwf=gwf,
        boundary_gdf=boundary_gdf,
        river_gdf=river_gdf,
        refine_points=refine_points,
        head_array=head_array,
        refine_radius=refine_radius,
        base_cell_size=base_cell_size,
        refined_cell_size=refined_cell_size,
        well_data=well_data,
        baseline_head_array=baseline_head_array,
    )
    return assemble_gwf_from_spec(spec, workspace=workspace, sim_name=sim_name)


# =============================================================================
# Pinned flow spec codec (freeze_flow_spec / load_flow_spec / load_pinned_flow_model)
#
# These functions let the GRADED path rebuild the refined MF6/DISV model from
# a frozen, hash-verified .npz of plain numpy arrays -- without re-running
# Triangle/Voronoi grid generation (disv_grid_utils) or scipy NearestND
# interpolation. They compose the already-shipped case_artifact_lock (hash
# manifest write/verify) with assemble_gwf_from_spec (pure MF6 construction).
#
# Spec schema (see generate_refined_grid docstring): 'gridprops', 'ncpl',
# 'top', 'botm', 'k', 'rch', 'strt', 'idomain', 'chd_cellid', 'chd_head',
# 'riv_cellid', 'riv_stage', 'riv_cond', 'riv_rbot', 'wel_cellid', 'wel_rate',
# 'well_cells', 'refine_radius_used', 'crs', and (optionally) 'baseline_heads'.
# 'gridprops' (flopy.utils.cvfdutil.get_disv_gridprops output) has keys
# 'ncpl', 'nvert', 'vertices' (rectangular, one (i, x, y) row per vertex), and
# 'cell2d' (RAGGED -- one [icell2d, xc, yc, nverts, *vertex_ids] row per cell,
# row length = 4 + nverts, which varies cell to cell).
# =============================================================================

# Keys whose values are already plain 1-D arrays of length ncpl.
_FLOW_SPEC_FLAT_ARRAY_KEYS = ("top", "botm", "k", "rch", "strt", "idomain")
# Keys holding a list of (layer, cell) cellid tuples -> encoded as (n, 2) int arrays.
_FLOW_SPEC_CELLID_KEYS = ("chd_cellid", "riv_cellid", "wel_cellid")
# Keys holding a 1-D list of floats parallel to a cellid key above.
_FLOW_SPEC_VALUE_FLOAT_KEYS = ("chd_head", "riv_stage", "riv_cond", "riv_rbot", "wel_rate")
# Keys holding a 1-D list of flat cell indices (ints), not cellid tuples.
_FLOW_SPEC_VALUE_INT_KEYS = ("well_cells",)
# Optional keys, round-tripped only when present (and not None) in the spec.
_FLOW_SPEC_OPTIONAL_STR_KEYS = ("crs",)
_FLOW_SPEC_OPTIONAL_FLOAT_ARRAY_KEYS = ("baseline_heads",)

_FLOW_SPEC_REQUIRED_KEYS = (
    ("gridprops", "ncpl", "refine_radius_used")
    + _FLOW_SPEC_FLAT_ARRAY_KEYS
    + _FLOW_SPEC_CELLID_KEYS
    + _FLOW_SPEC_VALUE_FLOAT_KEYS
    + _FLOW_SPEC_VALUE_INT_KEYS
)


def _encode_gridprops_for_npz(gridprops: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """Encode a DISV ``gridprops`` dict (as returned by
    ``flopy.utils.cvfdutil.get_disv_gridprops``) into NPZ-safe plain numpy
    arrays, preserving the RAGGED ``cell2d`` row lengths as a CSR-style
    (flat values + row lengths) pair.
    """
    vertices = np.asarray(
        [[float(v[0]), float(v[1]), float(v[2])] for v in gridprops["vertices"]],
        dtype=np.float64,
    )
    cell2d_rows = [[float(x) for x in row] for row in gridprops["cell2d"]]
    cell2d_lengths = np.array([len(row) for row in cell2d_rows], dtype=np.int64)
    cell2d_flat = (
        np.concatenate([np.asarray(row, dtype=np.float64) for row in cell2d_rows])
        if cell2d_rows
        else np.zeros(0, dtype=np.float64)
    )
    return {
        "gridprops__ncpl": np.array(int(gridprops["ncpl"]), dtype=np.int64),
        "gridprops__nvert": np.array(int(gridprops["nvert"]), dtype=np.int64),
        "gridprops__vertices": vertices,
        "gridprops__cell2d_flat": cell2d_flat,
        "gridprops__cell2d_lengths": cell2d_lengths,
    }


def _decode_gridprops_from_npz(arrays: Dict[str, np.ndarray]) -> Dict[str, Any]:
    """Inverse of :func:`_encode_gridprops_for_npz` -- rebuilds a ``gridprops``
    dict with the exact ragged ``cell2d`` row lengths restored, ready to pass
    straight into ``flopy.mf6.ModflowGwfdisv``.
    """
    vertices_arr = arrays["gridprops__vertices"]
    vertices = [
        (int(round(row[0])), float(row[1]), float(row[2])) for row in vertices_arr
    ]

    lengths = arrays["gridprops__cell2d_lengths"]
    flat = arrays["gridprops__cell2d_flat"]
    cell2d = []
    idx = 0
    for n in lengths:
        n = int(n)
        row = flat[idx : idx + n]
        idx += n
        icell2d = int(round(row[0]))
        xc, yc = float(row[1]), float(row[2])
        nverts = int(round(row[3]))
        ivert_ids = [int(round(v)) for v in row[4 : 4 + nverts]]
        cell2d.append([icell2d, xc, yc, nverts] + ivert_ids)

    return {
        "ncpl": int(arrays["gridprops__ncpl"]),
        "nvert": int(arrays["gridprops__nvert"]),
        "vertices": vertices,
        "cell2d": cell2d,
    }


def _encode_flow_spec_for_npz(spec: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """Encode a ``generate_refined_grid`` spec into a flat dict of NPZ-safe
    (non-object-dtype) numpy arrays.

    Raises
    ------
    KeyError
        If *spec* is missing any of the fields documented in
        ``generate_refined_grid`` / ``assemble_gwf_from_spec``.
    """
    missing = [k for k in _FLOW_SPEC_REQUIRED_KEYS if k not in spec]
    if missing:
        raise KeyError(f"flow spec is missing required key(s): {sorted(missing)!r}")

    arrays: Dict[str, np.ndarray] = {}
    arrays.update(_encode_gridprops_for_npz(spec["gridprops"]))
    arrays["ncpl"] = np.array(int(spec["ncpl"]), dtype=np.int64)
    arrays["refine_radius_used"] = np.array(
        float(spec["refine_radius_used"]), dtype=np.float64
    )

    for key in _FLOW_SPEC_FLAT_ARRAY_KEYS:
        arrays[key] = np.asarray(spec[key])

    for key in _FLOW_SPEC_CELLID_KEYS:
        rows = list(spec[key])
        arrays[key] = (
            np.array([[int(r[0]), int(r[1])] for r in rows], dtype=np.int64)
            if rows
            else np.zeros((0, 2), dtype=np.int64)
        )

    for key in _FLOW_SPEC_VALUE_FLOAT_KEYS:
        arrays[key] = np.asarray(spec[key], dtype=np.float64)

    for key in _FLOW_SPEC_VALUE_INT_KEYS:
        arrays[key] = np.asarray(spec[key], dtype=np.int64)

    for key in _FLOW_SPEC_OPTIONAL_STR_KEYS:
        if spec.get(key) is not None:
            arrays[key] = np.array(str(spec[key]))

    for key in _FLOW_SPEC_OPTIONAL_FLOAT_ARRAY_KEYS:
        if spec.get(key) is not None:
            arrays[key] = np.asarray(spec[key], dtype=np.float64)

    return arrays


def _decode_flow_spec_from_npz(arrays: Dict[str, np.ndarray]) -> Dict[str, Any]:
    """Inverse of :func:`_encode_flow_spec_for_npz`."""
    spec: Dict[str, Any] = {"gridprops": _decode_gridprops_from_npz(arrays)}
    spec["ncpl"] = int(arrays["ncpl"])
    spec["refine_radius_used"] = float(arrays["refine_radius_used"])

    for key in _FLOW_SPEC_FLAT_ARRAY_KEYS:
        spec[key] = arrays[key]

    for key in _FLOW_SPEC_CELLID_KEYS:
        spec[key] = [tuple(int(x) for x in row) for row in arrays[key]]

    for key in _FLOW_SPEC_VALUE_FLOAT_KEYS + _FLOW_SPEC_VALUE_INT_KEYS:
        spec[key] = (
            [int(x) for x in arrays[key]] if key == "well_cells" else arrays[key]
        )

    for key in _FLOW_SPEC_OPTIONAL_STR_KEYS:
        spec[key] = str(arrays[key]) if key in arrays else None

    for key in _FLOW_SPEC_OPTIONAL_FLOAT_ARRAY_KEYS:
        if key in arrays:
            spec[key] = arrays[key]

    return spec


def freeze_flow_spec(
    spec: Dict[str, Any],
    npz_path: Union[str, Path],
    *,
    caller_fields: Optional[Dict[str, Any]] = None,
    manifest_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Encode a ``generate_refined_grid`` spec (incl. ragged DISV ``gridprops``)
    into an NPZ of plain numpy arrays and write a hash-verified manifest for
    it via :mod:`case_artifact_lock`.

    Parameters
    ----------
    spec : dict
        Grid/property/boundary-condition spec, as returned by
        :func:`generate_refined_grid` (or hand-built with the same schema).
    npz_path : str or Path
        Destination ``.npz`` path. Parent directories are created as needed.
    caller_fields : dict, optional
        Free-form fields (e.g. ``{"group": 3, "case": "flow"}``) merged into
        the manifest JSON alongside the array hashes.
    manifest_path : str or Path, optional
        Where to write the manifest. Defaults to a sibling of *npz_path*
        named ``<npz stem>.manifest.json`` (see
        ``case_artifact_lock.write_artifact_manifest``).

    Returns
    -------
    dict
        The manifest contents that were written.

    Raises
    ------
    KeyError
        If *spec* is missing a required field.
    """
    from case_artifact_lock import write_artifact_manifest

    npz_path = Path(npz_path)
    arrays = _encode_flow_spec_for_npz(spec)

    npz_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(npz_path, **arrays)

    return write_artifact_manifest(npz_path, caller_fields or {}, manifest_path=manifest_path)


def load_flow_spec(
    npz_path: Union[str, Path],
    manifest_path: Optional[Union[str, Path]] = None,
    *,
    verify: bool = True,
) -> Dict[str, Any]:
    """
    Reconstruct a ``generate_refined_grid`` spec from a frozen ``.npz`` /
    manifest pair written by :func:`freeze_flow_spec`.

    Reconstruction is pure array decoding -- no Triangle/Voronoi grid
    generation and no NearestND interpolation are used.

    Parameters
    ----------
    npz_path : str or Path
        Path to the frozen ``.npz`` bundle.
    manifest_path : str or Path, optional
        Path to the sibling manifest JSON. Defaults to
        ``<npz stem>.manifest.json``.
    verify : bool, optional
        When True (default), the manifest must exist and every array must
        hash-match it before decoding (via
        ``case_artifact_lock.verify_artifact``). When False, the manifest is
        neither required nor checked.

    Returns
    -------
    dict
        Spec dict with the same schema/shapes as the one passed to
        :func:`freeze_flow_spec` (``gridprops['cell2d']`` restored with its
        original ragged row lengths).

    Raises
    ------
    FileNotFoundError
        If *npz_path* does not exist.
    ValueError
        If ``verify=True`` and the manifest is missing, malformed, or does
        not hash-match the ``.npz`` contents.
    """
    npz_path = Path(npz_path)
    if not npz_path.exists():
        raise FileNotFoundError(f"Frozen flow spec .npz not found: {npz_path}")

    manifest_path = (
        Path(manifest_path)
        if manifest_path is not None
        else npz_path.with_suffix("").with_suffix(".manifest.json")
    )

    if verify:
        from case_artifact_lock import verify_artifact

        if not manifest_path.exists():
            raise ValueError(
                f"Frozen flow spec manifest not found: {manifest_path}\n"
                f"Cannot verify {npz_path} (pass verify=False to skip verification)."
            )
        verify_artifact(npz_path, manifest_path)

    with np.load(npz_path, allow_pickle=False) as npz:
        arrays = {name: npz[name] for name in npz.files}

    return _decode_flow_spec_from_npz(arrays)


def load_pinned_flow_model(
    group: Union[int, str],
    *,
    meshes_dir: Optional[Union[str, Path]] = None,
    workspace: Union[str, Path],
    sim_name: str = "refined_model",
    verify: bool = True,
) -> Dict[str, Any]:
    """
    Load a per-group pinned flow spec and assemble it into a runnable GWF
    model -- the graded/student counterpart to :func:`build_refined_gwf_model`
    that never re-derives grid geometry.

    Resolves ``<meshes_dir>/group<group>_flow.npz`` (+ its sibling manifest),
    reconstructs the frozen spec via :func:`load_flow_spec`, and assembles it
    via :func:`assemble_gwf_from_spec`. No Triangle/Voronoi grid generation
    and no NearestND interpolation are used.

    Parameters
    ----------
    group : int or str
        Student group number/identifier; selects
        ``group<group>_flow.npz`` within *meshes_dir*.
    meshes_dir : str or Path, optional
        Directory containing the instructor-provided ``group<n>_flow.npz`` /
        ``.manifest.json`` pairs. Defaults to
        ``<default-data-folder>/pinned_meshes``.
    workspace : str or Path
        Directory for the assembled simulation files (see
        :func:`assemble_gwf_from_spec`).
    sim_name : str, optional
        MF6 simulation / model name.
    verify : bool, optional
        Passed through to :func:`load_flow_spec`. Default True.

    Returns
    -------
    dict
        Same return shape as :func:`build_refined_gwf_model` /
        :func:`assemble_gwf_from_spec`.

    Raises
    ------
    FileNotFoundError
        If the group's pinned ``.npz`` artifact does not exist.
    ValueError
        If ``verify=True`` and the artifact fails manifest verification.
    """
    if meshes_dir is None:
        from data_utils import get_default_data_folder

        meshes_dir = Path(get_default_data_folder()) / "pinned_meshes"
    else:
        meshes_dir = Path(meshes_dir)

    npz_path = meshes_dir / f"group{group}_flow.npz"
    manifest_path = npz_path.with_suffix("").with_suffix(".manifest.json")

    if not npz_path.exists():
        raise FileNotFoundError(
            f"Pinned flow spec for group{group} not found: {npz_path}\n"
            f"Ensure the instructor-provided mesh archive has been extracted "
            f"into {meshes_dir}."
        )

    spec = load_flow_spec(npz_path, manifest_path, verify=verify)
    return assemble_gwf_from_spec(spec, workspace=workspace, sim_name=sim_name)


def run_scenario_prt(
    ref_gwf,
    ref_sim,
    porosity: float,
    well_cells: List[int],
    rch_multiplier: float = 1.0,
    tracking_time: float = 365.0,
    workspace: Optional[Union[str, Path]] = None,
    sim_name: str = "scenario_prt",
) -> Optional[Dict[str, Any]]:
    """
    Run PRT particle tracking under a modified-recharge scenario.

    Applies a recharge multiplier to the refined GWF model, reruns the
    flow simulation, builds and runs PRT, loads results, and restores
    the original recharge.  This is the workflow used in NB8's drought
    stress-test.

    Parameters
    ----------
    ref_gwf : flopy.mf6.ModflowGwf
        Refined GWF model (already run once).
    ref_sim : flopy.mf6.MFSimulation
        Simulation containing *ref_gwf*.
    porosity : float
        Effective porosity for particle tracking.
    well_cells : list of int
        Flat cell indices for wells (izone = 1).
    rch_multiplier : float, optional
        Multiplier applied to recharge (e.g. 0.7 = −30 %).  Default 1.0.
    tracking_time : float, optional
        Maximum forward tracking time (days).  Default 365.
    workspace : str or Path, optional
        Directory for PRT files.  Defaults to ``<gwf_ws>/prt_scenario``.
    sim_name : str, optional
        PRT simulation name.  Default ``"scenario_prt"``.

    Returns
    -------
    dict or None
        Same structure as ``load_prt_results()`` output, or None on
        failure.  The original recharge is always restored.
    """
    import copy as _copy

    # --- Save and modify recharge ---
    rch_pkg = ref_gwf.get_package('RCHA')
    rch_data = rch_pkg.recharge.get_data()
    original_rch = _copy.deepcopy(rch_data)

    if rch_multiplier != 1.0:
        if isinstance(rch_data, dict):
            new_rch = {k: v * rch_multiplier for k, v in rch_data.items()}
        else:
            new_rch = rch_data * rch_multiplier
        rch_pkg.recharge.set_data(new_rch)

    results = None
    try:
        # --- Run GWF ---
        ref_sim.write_simulation()
        success_gwf, _ = ref_sim.run_simulation(silent=True)
        if not success_gwf:
            print("Scenario GWF run failed.")
            return None

        # --- Build and run PRT ---
        if workspace is None:
            workspace = os.path.join(ref_gwf.model_ws, 'prt_scenario')

        prt_result = build_prt_model(
            ref_gwf,
            porosity=porosity,
            well_cells=well_cells,
            tracking_time=tracking_time,
            workspace=workspace,
            sim_name=sim_name,
        )
        success_prt, _ = prt_result['prt_sim'].run_simulation()
        if not success_prt:
            print("Scenario PRT run failed.")
            return None

        # --- Load results ---
        results = load_prt_results(
            prt_result['trackcsv_path'],
            ref_gwf.modelgrid,
        )
    finally:
        # --- Always restore recharge ---
        rch_pkg.recharge.set_data(original_rch)

    return results
