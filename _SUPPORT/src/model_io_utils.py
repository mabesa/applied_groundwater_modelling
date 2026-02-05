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
    load_preprocessed_model_data: Load all pre-computed model inputs as dict
    format_budget_summary: Read MF6 budget and format as DataFrame
    load_base_simulation: Load pre-built MF6 simulation

Author: Applied Groundwater Modelling Course
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Union, Dict, List, Optional, Any

import numpy as np
import pandas as pd
import geopandas as gpd

import flopy
from flopy.utils import Raster
from flopy.mf6 import MFSimulation


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
    raster = Raster.load(str(raster_path), band=band)

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
