"""
Boundary condition utilities for MODFLOW 6 models.

This module provides functions for assigning boundary conditions to MODFLOW 6
models using geometry-based input (GeoDataFrames). The design principle is
"geometry in, stress_period_data out" - boundary condition data is stored as
geometries (GeoPackage), not cell IDs, enabling grid changes without reprocessing.

All functions support DISV (VertexGrid) grids via FloPy's GridIntersect utility.

Functions:
    assign_river_cells: Intersect river LineString geometries with grid
    assign_well_cells: Intersect well Point geometries with grid
    assign_idomain_from_geometry: Create IDOMAIN array from domain polygon
    create_riv_package: Create MF6 RIV package from river geometries
    create_wel_package: Create MF6 WEL package from well geometries
    create_chd_package: Create MF6 CHD package from boundary geometries
    create_rch_package: Create MF6 RCH package with optional zone-based rates
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiLineString, MultiPolygon

import flopy
from flopy.utils.gridintersect import GridIntersect
from flopy.discretization import VertexGrid, StructuredGrid


def assign_river_cells(
    river_geometry_gdf: gpd.GeoDataFrame,
    modelgrid: Union[VertexGrid, StructuredGrid],
    stage_column: str = 'stage',
    conductance_column: str = 'conductance',
    rbot_column: str = 'rbot',
    layer: int = 0,
) -> List[Tuple]:
    """
    Intersect river LineString geometries with grid to get cell assignments.

    Uses FloPy's GridIntersect utility to find grid cells that intersect with
    river geometries. For each intersection, computes the length-weighted
    conductance and returns stress period data suitable for ModflowGwfriv.

    Parameters
    ----------
    river_geometry_gdf : gpd.GeoDataFrame
        GeoDataFrame with LineString or MultiLineString geometries representing
        river reaches. Must contain columns for stage, conductance, and river
        bottom elevation. Conductance should be specified as conductance per
        unit length (e.g., m2/day per meter of river length).
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object. Can be a DISV VertexGrid or traditional
        StructuredGrid.
    stage_column : str, optional
        Name of the column containing river stage values (m). Default: 'stage'.
    conductance_column : str, optional
        Name of the column containing conductance per unit length (m2/day/m).
        Default: 'conductance'.
    rbot_column : str, optional
        Name of the column containing river bottom elevation (m).
        Default: 'rbot'.
    layer : int, optional
        Layer number (0-indexed) for river cells. Default: 0.

    Returns
    -------
    list of tuple
        Stress period data for ModflowGwfriv. Each tuple contains:
        - For DISV grids: ((layer, cell2d_index), stage, conductance, rbot)
        - For structured grids: ((layer, row, col), stage, conductance, rbot)

    Raises
    ------
    ValueError
        If required columns are missing from river_geometry_gdf.

    Notes
    -----
    The conductance for each grid cell is computed as:
        C_cell = conductance_per_length * intersection_length

    where intersection_length is the length of river geometry within each cell.

    For reaches that span multiple cells, the function distributes the river
    properties across all intersecting cells based on the intersection length.

    Examples
    --------
    >>> river_gdf = gpd.read_file("river_geometry.gpkg")
    >>> spd = assign_river_cells(river_gdf, modelgrid)
    >>> riv = flopy.mf6.ModflowGwfriv(gwf, stress_period_data={0: spd})
    """
    # Validate required columns
    required_columns = [stage_column, conductance_column, rbot_column]
    missing_columns = [col for col in required_columns if col not in river_geometry_gdf.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns in river_geometry_gdf: {missing_columns}. "
            f"Expected columns: {required_columns}"
        )

    # Validate geometry types
    valid_geom_types = {'LineString', 'MultiLineString'}
    geom_types = set(river_geometry_gdf.geometry.geom_type.unique())
    invalid_types = geom_types - valid_geom_types
    if invalid_types:
        warnings.warn(
            f"Found non-line geometry types: {invalid_types}. "
            "Only LineString and MultiLineString geometries will be processed."
        )

    # Create GridIntersect object
    # Use 'vertex' method which works for both structured and unstructured grids
    gix = GridIntersect(modelgrid, method='vertex', rtree=True)

    stress_period_data = []

    for idx, row in river_geometry_gdf.iterrows():
        geom = row.geometry

        # Skip non-line geometries
        if geom.geom_type not in valid_geom_types:
            continue

        # Skip empty or invalid geometries
        if geom is None or geom.is_empty:
            continue

        # Get attribute values
        stage = row[stage_column]
        cond_per_length = row[conductance_column]
        rbot = row[rbot_column]

        # Perform intersection
        try:
            result = gix.intersect(geom, shapetype='line')
        except Exception as e:
            warnings.warn(f"Failed to intersect river geometry at index {idx}: {e}")
            continue

        # Process intersection results
        for intersection in result:
            cellid = intersection.cellids

            # Get the intersection length
            # The intersection geometry is stored in the result
            if hasattr(intersection, 'lengths'):
                length = intersection.lengths
            elif hasattr(intersection, 'length'):
                length = intersection.length
            else:
                # Calculate length from the intersection geometry
                if hasattr(intersection, 'ixshapes'):
                    length = intersection.ixshapes.length
                else:
                    # Fallback: use total geometry length divided by number of cells
                    length = geom.length / len(result) if len(result) > 0 else 0

            # Calculate cell conductance
            cell_conductance = cond_per_length * length

            # Skip cells with zero conductance
            if cell_conductance <= 0:
                continue

            # Build cell identifier based on grid type
            if isinstance(modelgrid, VertexGrid):
                # DISV grid: cellid is a single integer (cell2d index)
                cell_tuple = (layer, cellid)
            else:
                # Structured grid: cellid is (row, col) tuple
                if isinstance(cellid, tuple):
                    cell_tuple = (layer, cellid[0], cellid[1])
                else:
                    # Single index, convert to row/col
                    nrow, ncol = modelgrid.nrow, modelgrid.ncol
                    row_idx = cellid // ncol
                    col_idx = cellid % ncol
                    cell_tuple = (layer, row_idx, col_idx)

            stress_period_data.append((cell_tuple, stage, cell_conductance, rbot))

    return stress_period_data


def assign_well_cells(
    well_geometry_gdf: gpd.GeoDataFrame,
    modelgrid: Union[VertexGrid, StructuredGrid],
    rate_column: str = 'rate',
    layer_column: Optional[str] = None,
    default_layer: int = 0,
) -> List[Tuple]:
    """
    Intersect well Point geometries with grid to get cell assignments.

    Uses FloPy's GridIntersect utility to find the grid cell containing each
    well point. Returns stress period data suitable for ModflowGwfwel.

    Parameters
    ----------
    well_geometry_gdf : gpd.GeoDataFrame
        GeoDataFrame with Point geometries representing well locations.
        Must contain a column for pumping/injection rate.
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object. Can be a DISV VertexGrid or traditional
        StructuredGrid.
    rate_column : str, optional
        Name of the column containing pumping rates (m3/day). Negative values
        indicate extraction, positive values indicate injection.
        Default: 'rate'.
    layer_column : str, optional
        Name of the column containing layer indices (0-indexed). If None,
        all wells are assigned to default_layer. Default: None.
    default_layer : int, optional
        Default layer number (0-indexed) for wells when layer_column is None.
        Default: 0.

    Returns
    -------
    list of tuple
        Stress period data for ModflowGwfwel. Each tuple contains:
        - For DISV grids: ((layer, cell2d_index), rate)
        - For structured grids: ((layer, row, col), rate)

    Raises
    ------
    ValueError
        If required columns are missing from well_geometry_gdf.

    Notes
    -----
    Wells that fall outside the model domain (no intersecting cell) are
    skipped with a warning.

    For MODFLOW convention, extraction (pumping) rates should be negative
    and injection rates should be positive.

    Examples
    --------
    >>> wells_gdf = gpd.read_file("well_geometry.gpkg")
    >>> spd = assign_well_cells(wells_gdf, modelgrid)
    >>> wel = flopy.mf6.ModflowGwfwel(gwf, stress_period_data={0: spd})
    """
    # Validate required columns
    if rate_column not in well_geometry_gdf.columns:
        raise ValueError(
            f"Missing required column '{rate_column}' in well_geometry_gdf."
        )

    if layer_column is not None and layer_column not in well_geometry_gdf.columns:
        raise ValueError(
            f"Specified layer_column '{layer_column}' not found in well_geometry_gdf."
        )

    # Validate geometry types
    valid_geom_types = {'Point'}
    geom_types = set(well_geometry_gdf.geometry.geom_type.unique())
    invalid_types = geom_types - valid_geom_types
    if invalid_types:
        warnings.warn(
            f"Found non-point geometry types: {invalid_types}. "
            "Only Point geometries will be processed."
        )

    # Create GridIntersect object
    gix = GridIntersect(modelgrid, method='vertex', rtree=True)

    stress_period_data = []
    wells_outside_domain = 0

    for idx, row in well_geometry_gdf.iterrows():
        geom = row.geometry

        # Skip non-point geometries
        if geom.geom_type != 'Point':
            continue

        # Skip empty or invalid geometries
        if geom is None or geom.is_empty:
            continue

        # Get attribute values
        rate = row[rate_column]
        layer = row[layer_column] if layer_column is not None else default_layer

        # Perform intersection to find containing cell
        try:
            result = gix.intersect(geom, shapetype='point')
        except Exception as e:
            warnings.warn(f"Failed to intersect well geometry at index {idx}: {e}")
            continue

        # Check if point is within domain
        if len(result) == 0:
            wells_outside_domain += 1
            continue

        # Get the cell ID (should be exactly one for a point)
        cellid = result[0].cellids

        # Build cell identifier based on grid type
        if isinstance(modelgrid, VertexGrid):
            # DISV grid: cellid is a single integer (cell2d index)
            cell_tuple = (int(layer), cellid)
        else:
            # Structured grid: cellid is (row, col) tuple
            if isinstance(cellid, tuple):
                cell_tuple = (int(layer), cellid[0], cellid[1])
            else:
                # Single index, convert to row/col
                nrow, ncol = modelgrid.nrow, modelgrid.ncol
                row_idx = cellid // ncol
                col_idx = cellid % ncol
                cell_tuple = (int(layer), row_idx, col_idx)

        stress_period_data.append((cell_tuple, rate))

    if wells_outside_domain > 0:
        warnings.warn(
            f"{wells_outside_domain} well(s) fell outside the model domain and were skipped."
        )

    return stress_period_data


def assign_idomain_from_geometry(
    domain_polygon_gdf: gpd.GeoDataFrame,
    modelgrid: Union[VertexGrid, StructuredGrid],
    nlay: int = 1,
    active_value: int = 1,
    inactive_value: int = 0,
) -> np.ndarray:
    """
    Create IDOMAIN array by intersecting domain polygon with grid.

    Determines which grid cells fall within the domain polygon and assigns
    active/inactive status accordingly. Cells outside the polygon are set
    to inactive (idomain=0).

    Parameters
    ----------
    domain_polygon_gdf : gpd.GeoDataFrame
        GeoDataFrame with Polygon or MultiPolygon geometry representing
        the active model domain. If multiple polygons are present, they
        are unioned.
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object. Can be a DISV VertexGrid or traditional
        StructuredGrid.
    nlay : int, optional
        Number of model layers. The IDOMAIN array will have shape
        (nlay, ncells) for DISV or (nlay, nrow, ncol) for structured grids.
        Default: 1.
    active_value : int, optional
        Value to assign to active cells. Default: 1.
    inactive_value : int, optional
        Value to assign to inactive cells (outside domain). Default: 0.

    Returns
    -------
    np.ndarray
        IDOMAIN array with shape appropriate for the grid type:
        - For DISV grids: (nlay, ncpl) where ncpl is number of cells per layer
        - For structured grids: (nlay, nrow, ncol)

    Notes
    -----
    A cell is considered active if its centroid falls within the domain
    polygon. This is a simple point-in-polygon test that works well for
    cells that are much smaller than the domain extent.

    For cells that straddle the domain boundary, this approach may include
    or exclude cells depending on centroid location. For more precise
    boundary handling, consider using area-based intersection.

    Examples
    --------
    >>> domain_gdf = gpd.read_file("model_boundary.gpkg")
    >>> idomain = assign_idomain_from_geometry(domain_gdf, modelgrid, nlay=1)
    >>> dis = flopy.mf6.ModflowGwfdisv(gwf, ..., idomain=idomain)
    """
    # Validate geometry types
    valid_geom_types = {'Polygon', 'MultiPolygon'}
    geom_types = set(domain_polygon_gdf.geometry.geom_type.unique())
    invalid_types = geom_types - valid_geom_types
    if invalid_types:
        warnings.warn(
            f"Found non-polygon geometry types: {invalid_types}. "
            "Only Polygon and MultiPolygon geometries will be used."
        )

    # Union all polygons into a single geometry
    from shapely.ops import unary_union
    polygons = [
        geom for geom in domain_polygon_gdf.geometry
        if geom.geom_type in valid_geom_types and not geom.is_empty
    ]

    if not polygons:
        raise ValueError("No valid polygon geometries found in domain_polygon_gdf.")

    domain_polygon = unary_union(polygons)

    # Create GridIntersect object
    gix = GridIntersect(modelgrid, method='vertex', rtree=True)

    # Get cell centroids and check which are inside the domain
    if isinstance(modelgrid, VertexGrid):
        # DISV grid
        ncpl = modelgrid.ncpl
        idomain = np.full((nlay, ncpl), inactive_value, dtype=np.int32)

        # Get cell centers
        xc = modelgrid.xcellcenters
        yc = modelgrid.ycellcenters

        # Flatten if necessary (DISV cell centers are 1D)
        if xc.ndim > 1:
            xc = xc.flatten()
            yc = yc.flatten()

        # Check each cell centroid
        for icell in range(ncpl):
            point = Point(xc[icell], yc[icell])
            if domain_polygon.contains(point):
                for ilay in range(nlay):
                    idomain[ilay, icell] = active_value
    else:
        # Structured grid
        nrow, ncol = modelgrid.nrow, modelgrid.ncol
        idomain = np.full((nlay, nrow, ncol), inactive_value, dtype=np.int32)

        # Get cell centers
        xc = modelgrid.xcellcenters
        yc = modelgrid.ycellcenters

        # Check each cell centroid
        for irow in range(nrow):
            for icol in range(ncol):
                point = Point(xc[irow, icol], yc[irow, icol])
                if domain_polygon.contains(point):
                    for ilay in range(nlay):
                        idomain[ilay, irow, icol] = active_value

    return idomain


def create_riv_package(
    gwf: Any,
    river_geometry_gdf: gpd.GeoDataFrame,
    modelgrid: Union[VertexGrid, StructuredGrid],
    stage_column: str = 'stage',
    conductance_column: str = 'conductance',
    rbot_column: str = 'rbot',
    layer: int = 0,
    boundnames: bool = False,
    name_column: Optional[str] = None,
    print_input: bool = False,
    print_flows: bool = False,
    save_flows: bool = True,
    pname: str = 'riv',
) -> Any:
    """
    Create MF6 RIV package from river geometries.

    Wrapper function that calls assign_river_cells() to compute stress period
    data, then creates and returns a ModflowGwfriv package object.

    Parameters
    ----------
    gwf : ModflowGwf
        FloPy MODFLOW 6 groundwater flow model object.
    river_geometry_gdf : gpd.GeoDataFrame
        GeoDataFrame with LineString geometries and river attributes.
        See assign_river_cells() for required columns.
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object.
    stage_column : str, optional
        Column name for river stage. Default: 'stage'.
    conductance_column : str, optional
        Column name for conductance per unit length. Default: 'conductance'.
    rbot_column : str, optional
        Column name for river bottom elevation. Default: 'rbot'.
    layer : int, optional
        Layer number (0-indexed) for river cells. Default: 0.
    boundnames : bool, optional
        If True, include boundary names in the package. Requires name_column.
        Default: False.
    name_column : str, optional
        Column name for boundary names. Required if boundnames=True.
        Default: None.
    print_input : bool, optional
        Print input to listing file. Default: False.
    print_flows : bool, optional
        Print flows to listing file. Default: False.
    save_flows : bool, optional
        Save flows to budget file. Default: True.
    pname : str, optional
        Package name. Default: 'riv'.

    Returns
    -------
    ModflowGwfriv
        FloPy MODFLOW 6 RIV package object.

    Examples
    --------
    >>> river_gdf = gpd.read_file("river_geometry.gpkg")
    >>> riv = create_riv_package(gwf, river_gdf, modelgrid)
    """
    # Get stress period data
    spd = assign_river_cells(
        river_geometry_gdf,
        modelgrid,
        stage_column=stage_column,
        conductance_column=conductance_column,
        rbot_column=rbot_column,
        layer=layer,
    )

    if len(spd) == 0:
        warnings.warn("No river cells found. RIV package will have no stress period data.")

    # Create the package
    riv = flopy.mf6.ModflowGwfriv(
        gwf,
        stress_period_data={0: spd},
        print_input=print_input,
        print_flows=print_flows,
        save_flows=save_flows,
        pname=pname,
    )

    return riv


def create_wel_package(
    gwf: Any,
    well_geometry_gdf: gpd.GeoDataFrame,
    modelgrid: Union[VertexGrid, StructuredGrid],
    rate_column: str = 'rate',
    layer_column: Optional[str] = None,
    default_layer: int = 0,
    boundnames: bool = False,
    name_column: Optional[str] = None,
    print_input: bool = False,
    print_flows: bool = False,
    save_flows: bool = True,
    pname: str = 'wel',
) -> Any:
    """
    Create MF6 WEL package from well geometries.

    Wrapper function that calls assign_well_cells() to compute stress period
    data, then creates and returns a ModflowGwfwel package object.

    Parameters
    ----------
    gwf : ModflowGwf
        FloPy MODFLOW 6 groundwater flow model object.
    well_geometry_gdf : gpd.GeoDataFrame
        GeoDataFrame with Point geometries and well attributes.
        See assign_well_cells() for required columns.
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object.
    rate_column : str, optional
        Column name for pumping rate. Default: 'rate'.
    layer_column : str, optional
        Column name for layer index. Default: None.
    default_layer : int, optional
        Default layer for wells. Default: 0.
    boundnames : bool, optional
        If True, include boundary names in the package. Default: False.
    name_column : str, optional
        Column name for boundary names. Required if boundnames=True.
        Default: None.
    print_input : bool, optional
        Print input to listing file. Default: False.
    print_flows : bool, optional
        Print flows to listing file. Default: False.
    save_flows : bool, optional
        Save flows to budget file. Default: True.
    pname : str, optional
        Package name. Default: 'wel'.

    Returns
    -------
    ModflowGwfwel
        FloPy MODFLOW 6 WEL package object.

    Examples
    --------
    >>> wells_gdf = gpd.read_file("well_geometry.gpkg")
    >>> wel = create_wel_package(gwf, wells_gdf, modelgrid)
    """
    # Get stress period data
    spd = assign_well_cells(
        well_geometry_gdf,
        modelgrid,
        rate_column=rate_column,
        layer_column=layer_column,
        default_layer=default_layer,
    )

    if len(spd) == 0:
        warnings.warn("No well cells found. WEL package will have no stress period data.")

    # Create the package
    wel = flopy.mf6.ModflowGwfwel(
        gwf,
        stress_period_data={0: spd},
        print_input=print_input,
        print_flows=print_flows,
        save_flows=save_flows,
        pname=pname,
    )

    return wel


def create_chd_package(
    gwf: Any,
    chd_geometry_gdf: gpd.GeoDataFrame,
    modelgrid: Union[VertexGrid, StructuredGrid],
    head_column: str = 'head',
    layer_column: Optional[str] = None,
    default_layer: int = 0,
    print_input: bool = False,
    print_flows: bool = False,
    save_flows: bool = True,
    pname: str = 'chd',
) -> Any:
    """
    Create MF6 CHD package from boundary geometries.

    Supports Point and LineString/Polygon geometries. For points, assigns
    the specified head to the containing cell. For lines/polygons, assigns
    the head to all intersecting cells.

    Parameters
    ----------
    gwf : ModflowGwf
        FloPy MODFLOW 6 groundwater flow model object.
    chd_geometry_gdf : gpd.GeoDataFrame
        GeoDataFrame with geometries (Point, LineString, or Polygon) and
        head values. Each geometry will be intersected with the grid.
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object.
    head_column : str, optional
        Column name for specified head values. Default: 'head'.
    layer_column : str, optional
        Column name for layer index. If None, uses default_layer.
        Default: None.
    default_layer : int, optional
        Default layer for CHD cells. Default: 0.
    print_input : bool, optional
        Print input to listing file. Default: False.
    print_flows : bool, optional
        Print flows to listing file. Default: False.
    save_flows : bool, optional
        Save flows to budget file. Default: True.
    pname : str, optional
        Package name. Default: 'chd'.

    Returns
    -------
    ModflowGwfchd
        FloPy MODFLOW 6 CHD package object.

    Notes
    -----
    For Polygon geometries, all cells whose centroids fall within the
    polygon are assigned the constant head value.

    For LineString geometries, all cells intersecting the line are assigned
    the constant head value.

    Examples
    --------
    >>> chd_gdf = gpd.read_file("constant_head_boundary.gpkg")
    >>> chd = create_chd_package(gwf, chd_gdf, modelgrid, head_column='head')
    """
    # Validate required columns
    if head_column not in chd_geometry_gdf.columns:
        raise ValueError(
            f"Missing required column '{head_column}' in chd_geometry_gdf."
        )

    # Create GridIntersect object
    gix = GridIntersect(modelgrid, method='vertex', rtree=True)

    stress_period_data = []

    for idx, row in chd_geometry_gdf.iterrows():
        geom = row.geometry
        head = row[head_column]
        layer = row[layer_column] if layer_column is not None else default_layer

        # Skip empty or invalid geometries
        if geom is None or geom.is_empty:
            continue

        cellids = []

        if geom.geom_type == 'Point':
            # Point geometry - find containing cell
            try:
                result = gix.intersect(geom, shapetype='point')
                if len(result) > 0:
                    cellids.append(result[0].cellids)
            except Exception as e:
                warnings.warn(f"Failed to intersect CHD point at index {idx}: {e}")

        elif geom.geom_type in ('LineString', 'MultiLineString'):
            # Line geometry - find all intersecting cells
            try:
                result = gix.intersect(geom, shapetype='line')
                for intersection in result:
                    cellids.append(intersection.cellids)
            except Exception as e:
                warnings.warn(f"Failed to intersect CHD line at index {idx}: {e}")

        elif geom.geom_type in ('Polygon', 'MultiPolygon'):
            # Polygon geometry - find all intersecting cells
            try:
                result = gix.intersect(geom, shapetype='polygon')
                for intersection in result:
                    cellids.append(intersection.cellids)
            except Exception as e:
                warnings.warn(f"Failed to intersect CHD polygon at index {idx}: {e}")
        else:
            warnings.warn(f"Unsupported geometry type '{geom.geom_type}' at index {idx}")
            continue

        # Add stress period data for each cell
        for cellid in cellids:
            if isinstance(modelgrid, VertexGrid):
                cell_tuple = (int(layer), cellid)
            else:
                if isinstance(cellid, tuple):
                    cell_tuple = (int(layer), cellid[0], cellid[1])
                else:
                    nrow, ncol = modelgrid.nrow, modelgrid.ncol
                    row_idx = cellid // ncol
                    col_idx = cellid % ncol
                    cell_tuple = (int(layer), row_idx, col_idx)

            stress_period_data.append((cell_tuple, head))

    if len(stress_period_data) == 0:
        warnings.warn("No CHD cells found. CHD package will have no stress period data.")

    # Create the package
    chd = flopy.mf6.ModflowGwfchd(
        gwf,
        stress_period_data={0: stress_period_data},
        print_input=print_input,
        print_flows=print_flows,
        save_flows=save_flows,
        pname=pname,
    )

    return chd


def create_rch_package(
    gwf: Any,
    recharge_rate: float,
    recharge_zones_gdf: Optional[gpd.GeoDataFrame] = None,
    modelgrid: Optional[Union[VertexGrid, StructuredGrid]] = None,
    rate_column: str = 'rate',
    print_input: bool = False,
    print_flows: bool = False,
    save_flows: bool = True,
    pname: str = 'rch',
) -> Any:
    """
    Create MF6 RCH package with optional zone-based rates.

    Creates a recharge package with either a uniform rate or spatially
    variable rates based on zone polygons. Uses the array-based recharge
    approach (READASARRAYS) for efficiency.

    Parameters
    ----------
    gwf : ModflowGwf
        FloPy MODFLOW 6 groundwater flow model object.
    recharge_rate : float
        Default recharge rate (m/day) applied to all cells. This value is
        used for cells not covered by recharge_zones_gdf polygons.
    recharge_zones_gdf : gpd.GeoDataFrame, optional
        GeoDataFrame with Polygon geometries defining recharge zones.
        Each polygon should have an associated rate in rate_column.
        If None, uniform recharge_rate is applied everywhere.
        Default: None.
    modelgrid : VertexGrid or StructuredGrid, optional
        FloPy model grid object. Required if recharge_zones_gdf is provided.
        Default: None.
    rate_column : str, optional
        Column name for zone-specific recharge rates in recharge_zones_gdf.
        Default: 'rate'.
    print_input : bool, optional
        Print input to listing file. Default: False.
    print_flows : bool, optional
        Print flows to listing file. Default: False.
    save_flows : bool, optional
        Save flows to budget file. Default: True.
    pname : str, optional
        Package name. Default: 'rch'.

    Returns
    -------
    ModflowGwfrcha
        FloPy MODFLOW 6 RCH array-based package object.

    Notes
    -----
    Uses READASARRAYS approach (ModflowGwfrcha) which is more efficient
    than list-based recharge for models with recharge applied to many cells.

    For zone-based recharge, cells are assigned to zones based on their
    centroids. If a cell centroid falls within multiple zone polygons,
    the last matching zone's rate is used.

    Examples
    --------
    Uniform recharge:

    >>> rch = create_rch_package(gwf, recharge_rate=0.001)

    Zone-based recharge:

    >>> zones_gdf = gpd.read_file("recharge_zones.gpkg")
    >>> rch = create_rch_package(gwf, 0.0, zones_gdf, modelgrid, rate_column='rch_rate')
    """
    if recharge_zones_gdf is not None:
        if modelgrid is None:
            raise ValueError(
                "modelgrid must be provided when using zone-based recharge."
            )

        if rate_column not in recharge_zones_gdf.columns:
            raise ValueError(
                f"Missing required column '{rate_column}' in recharge_zones_gdf."
            )

        # Create recharge array based on zones
        if isinstance(modelgrid, VertexGrid):
            # DISV grid
            ncpl = modelgrid.ncpl
            recharge_array = np.full(ncpl, recharge_rate, dtype=np.float64)

            # Get cell centers
            xc = modelgrid.xcellcenters
            yc = modelgrid.ycellcenters

            if xc.ndim > 1:
                xc = xc.flatten()
                yc = yc.flatten()

            # Assign zone rates
            for idx, row in recharge_zones_gdf.iterrows():
                geom = row.geometry
                zone_rate = row[rate_column]

                if geom is None or geom.is_empty:
                    continue

                if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                    continue

                for icell in range(ncpl):
                    point = Point(xc[icell], yc[icell])
                    if geom.contains(point):
                        recharge_array[icell] = zone_rate
        else:
            # Structured grid
            nrow, ncol = modelgrid.nrow, modelgrid.ncol
            recharge_array = np.full((nrow, ncol), recharge_rate, dtype=np.float64)

            # Get cell centers
            xc = modelgrid.xcellcenters
            yc = modelgrid.ycellcenters

            # Assign zone rates
            for idx, row in recharge_zones_gdf.iterrows():
                geom = row.geometry
                zone_rate = row[rate_column]

                if geom is None or geom.is_empty:
                    continue

                if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                    continue

                for irow in range(nrow):
                    for icol in range(ncol):
                        point = Point(xc[irow, icol], yc[irow, icol])
                        if geom.contains(point):
                            recharge_array[irow, icol] = zone_rate
    else:
        # Uniform recharge
        recharge_array = recharge_rate

    # Create the package using array-based approach
    rch = flopy.mf6.ModflowGwfrcha(
        gwf,
        recharge={0: recharge_array},
        print_input=print_input,
        print_flows=print_flows,
        save_flows=save_flows,
        pname=pname,
    )

    return rch


# Utility functions for validation and debugging

def validate_bc_geometries(
    gdf: gpd.GeoDataFrame,
    modelgrid: Union[VertexGrid, StructuredGrid],
    expected_type: str = 'any',
) -> Dict[str, Any]:
    """
    Validate boundary condition geometries against a model grid.

    Performs spatial validation to check that geometries fall within the
    model domain and reports statistics about intersection coverage.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        GeoDataFrame with boundary condition geometries.
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object.
    expected_type : str, optional
        Expected geometry type: 'point', 'line', 'polygon', or 'any'.
        Default: 'any'.

    Returns
    -------
    dict
        Dictionary containing validation results:
        - 'n_features': Total number of features
        - 'n_valid': Number of valid features
        - 'n_inside_domain': Number of features intersecting the model domain
        - 'geometry_types': Set of geometry types found
        - 'warnings': List of warning messages
    """
    results = {
        'n_features': len(gdf),
        'n_valid': 0,
        'n_inside_domain': 0,
        'geometry_types': set(),
        'warnings': [],
    }

    # Get model extent
    if hasattr(modelgrid, 'extent'):
        xmin, xmax, ymin, ymax = modelgrid.extent
    else:
        xc = modelgrid.xcellcenters
        yc = modelgrid.ycellcenters
        xmin, xmax = xc.min(), xc.max()
        ymin, ymax = yc.min(), yc.max()

    model_bounds = Polygon([
        (xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)
    ])

    for idx, row in gdf.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        results['geometry_types'].add(geom.geom_type)
        results['n_valid'] += 1

        if geom.intersects(model_bounds):
            results['n_inside_domain'] += 1

    # Check expected geometry type
    expected_map = {
        'point': {'Point'},
        'line': {'LineString', 'MultiLineString'},
        'polygon': {'Polygon', 'MultiPolygon'},
        'any': None,
    }

    if expected_type != 'any':
        expected_types = expected_map.get(expected_type, set())
        unexpected = results['geometry_types'] - expected_types
        if unexpected:
            results['warnings'].append(
                f"Unexpected geometry types found: {unexpected}. "
                f"Expected: {expected_types}"
            )

    if results['n_inside_domain'] < results['n_valid']:
        n_outside = results['n_valid'] - results['n_inside_domain']
        results['warnings'].append(
            f"{n_outside} feature(s) fall outside the model domain."
        )

    return results
