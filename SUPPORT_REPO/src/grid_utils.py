"""
Utilities for working with FloPy StructuredGrid and GeoPandas.

Functions:
- grid_to_gdf(modelgrid, crs=None): Build a GeoDataFrame of cell polygons with row/col.
- compute_active_mask(grid_gdf, boundary_gdf, frac_threshold=0.5): Tag cells by area fraction inside boundary.
- ibound_from_active(grid_gdf, nlay=1, active_field='active', active_value=1, inactive_value=0): Build a 3D IBOUND array.
- build_grid_gdf_and_ibound(modelgrid, boundary_gdf, frac_threshold=0.5, nlay=1): Convenience wrapper.

Notes:
- Assumes modelgrid.xvertices/yvertices represent cell corner coordinates in map space.
- CRS: grid_gdf is created with the boundary CRS by default to ensure spatial ops work.
"""

from __future__ import annotations

from typing import Tuple
import warnings

import numpy as np
import geopandas as gpd

from scipy.interpolate import griddata

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

import rasterio
from rasterio.features import rasterize


def grid_to_gdf(modelgrid, crs=None) -> gpd.GeoDataFrame:
    """Convert a FloPy StructuredGrid to a GeoDataFrame of cell polygons.

    Parameters
    ----------
    modelgrid : flopy.discretization.StructuredGrid
        The FloPy structured grid.
    crs : any, optional
        CRS to assign to the output GeoDataFrame (e.g., from boundary_gdf.crs).

    Returns
    -------
    geopandas.GeoDataFrame
        Columns: row, col, geometry (Polygon)
    """
    xv, yv = modelgrid.xvertices, modelgrid.yvertices  # shape (nrow+1, ncol+1)
    nrow, ncol = modelgrid.nrow, modelgrid.ncol
    polys, rows, cols = [], [], []
    for r in range(nrow):
        for c in range(ncol):
            # Corner order: (r,c) -> (r,c+1) -> (r+1,c+1) -> (r+1,c)
            polys.append(
                Polygon(
                    [
                        (float(xv[r, c]), float(yv[r, c])),
                        (float(xv[r, c + 1]), float(yv[r, c + 1])),
                        (float(xv[r + 1, c + 1]), float(yv[r + 1, c + 1])),
                        (float(xv[r + 1, c]), float(yv[r + 1, c])),
                    ]
                )
            )
            rows.append(r)
            cols.append(c)
    g = gpd.GeoDataFrame({"row": rows, "col": cols, "geometry": polys}, crs=crs)
    return g


def _unary_union(gdf: gpd.GeoDataFrame, repair: bool = False) -> BaseGeometry:
    """Return a single (multi)polygon geometry from a GeoDataFrame.

    Uses Shapely 2.0's union_all when available (faster, non-deprecated).
    Falls back to shapely.ops.unary_union for older Shapely versions.

    Parameters
    ----------
    gdf : GeoDataFrame
        Input geometries.
    repair : bool, optional
        If True, attempt to make invalid geometries valid before union
        (buffer(0) fallback if make_valid unavailable).

    Returns
    -------
    BaseGeometry
        Unified geometry.
    """
    if gdf is None or gdf.empty:
        raise ValueError("boundary_gdf is empty or None")

    geoms = gdf.geometry
    if repair:
        # Attempt validity repair (Shapely 2 has make_valid)
        try:
            from shapely import make_valid  # type: ignore
            geoms = geoms.apply(make_valid)
        except Exception:
            geoms = geoms.apply(lambda g: g if g.is_valid else g.buffer(0))

    # Prefer Shapely 2 union_all
    try:
        from shapely import union_all  # Shapely >= 2.0
        unified = union_all(list(geoms.values))
    except Exception:  # pragma: no cover - fallback path
        from shapely.ops import unary_union
        unified = unary_union(geoms)

    if callable(unified):  # Safety check
        raise TypeError("Unified geometry is callable; incorrect Shapely interaction.")

    return unified


def compute_active_mask(
    grid_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    frac_threshold: float = 0.5,
) -> gpd.GeoDataFrame:
    """Compute area fraction of each cell inside the boundary and tag active cells.

    Parameters
    ----------
    grid_gdf : GeoDataFrame
        GeoDataFrame with cell polygons and row/col columns.
    boundary_gdf : GeoDataFrame
        Boundary polygons (can be multi-part). Will be unioned.
    frac_threshold : float, default 0.5
        Minimum fraction of cell area within boundary to mark as active.

    Returns
    -------
    GeoDataFrame
        Copy of grid_gdf with added columns: 'frac_inside' (float) and 'active' (bool).
    """
    if grid_gdf.crs is None and boundary_gdf.crs is not None:
        grid_gdf = grid_gdf.set_crs(boundary_gdf.crs)
    elif grid_gdf.crs is not None and boundary_gdf.crs is not None and grid_gdf.crs != boundary_gdf.crs:
        warnings.warn(
            "CRS mismatch between grid and boundary; reprojecting grid to boundary CRS.",
            stacklevel=2,
        )
        grid_gdf = grid_gdf.to_crs(boundary_gdf.crs)

    boundary = _unary_union(boundary_gdf)
    areas = grid_gdf.geometry.area
    inter_areas = grid_gdf.geometry.intersection(boundary).area
    with np.errstate(divide="ignore", invalid="ignore"):
        frac_inside = np.where(areas > 0, inter_areas / areas, 0.0)

    out = grid_gdf.copy()
    out["frac_inside"] = frac_inside
    out["active"] = frac_inside >= float(frac_threshold)
    return out


def ibound_from_active(
    grid_gdf: gpd.GeoDataFrame,
    nlay: int = 1,
    active_field: str = "active",
    active_value: int = 1,
    inactive_value: int = 0,
) -> np.ndarray:
    """Build a 3D IBOUND array from a grid GeoDataFrame with an 'active' field.

    Parameters
    ----------
    grid_gdf : GeoDataFrame
        Must contain integer 'row' and 'col' columns and a boolean active field.
    nlay : int
        Number of model layers.
    active_field : str
        Name of the boolean column indicating active cells.
    active_value : int
        Value assigned to active cells in IBOUND.
    inactive_value : int
        Value assigned to inactive cells in IBOUND.

    Returns
    -------
    np.ndarray
        IBOUND array of shape (nlay, nrow, ncol).
    """
    if active_field not in grid_gdf.columns:
        raise KeyError(f"Column '{active_field}' not found in grid_gdf")

    nrow = int(grid_gdf["row"].max()) + 1
    ncol = int(grid_gdf["col"].max()) + 1
    ib2d = np.full((nrow, ncol), inactive_value, dtype=int)

    # Set active cells
    active_rows = grid_gdf.loc[grid_gdf[active_field], "row"].to_numpy()
    active_cols = grid_gdf.loc[grid_gdf[active_field], "col"].to_numpy()
    ib2d[active_rows, active_cols] = active_value

    # Stack across layers
    ibound = np.repeat(ib2d[np.newaxis, :, :], repeats=int(nlay), axis=0)
    return ibound


def build_grid_gdf_and_ibound(
    modelgrid,
    boundary_gdf: gpd.GeoDataFrame,
    frac_threshold: float = 0.5,
    nlay: int = 1,
) -> Tuple[gpd.GeoDataFrame, np.ndarray]:
    """Convenience wrapper: grid polygons + active tagging + IBOUND.

    Parameters
    ----------
    modelgrid : flopy.discretization.StructuredGrid
        The FloPy structured grid.
    boundary_gdf : GeoDataFrame
        Case-study boundary polygons (CRS should match model coordinates).
    frac_threshold : float
        Minimum fraction of cell area within boundary to mark as active.
    nlay : int
        Number of layers for IBOUND.

    Returns
    -------
    (grid_gdf, ibound)
        grid_gdf includes 'row', 'col', 'geometry', 'frac_inside', 'active'.
        ibound is a (nlay, nrow, ncol) integer array.
    """
    grid_gdf = grid_to_gdf(modelgrid, crs=boundary_gdf.crs)
    grid_gdf = compute_active_mask(grid_gdf, boundary_gdf, frac_threshold=frac_threshold)
    ibound = ibound_from_active(grid_gdf, nlay=nlay)
    return grid_gdf, ibound

def interpolate_isohypses_to_grid(gdf_isohypses, modelgrid, buffer_distance=500):
    """
    Interpolate groundwater isohypses to a MODFLOW structured grid.
    
    Parameters:
    -----------
    gdf_isohypses : geopandas.GeoDataFrame
        Geodataframe containing isohypse lines with elevation values
    modelgrid : flopy.discretization.StructuredGrid
        MODFLOW structured grid object
    buffer_distance : float
        Buffer distance (in model units) to extend clipping beyond model grid extent
    
    Returns:
    --------
    numpy.ndarray
        2D array of interpolated groundwater elevations matching the model grid
    """
    
    # Create model grid boundary polygon for clipping
    from shapely.geometry import Polygon
    
    # Get model grid extent
    xmin, xmax, ymin, ymax = modelgrid.extent
    
    # Create buffered boundary polygon
    boundary = Polygon([
        (xmin - buffer_distance, ymin - buffer_distance),
        (xmax + buffer_distance, ymin - buffer_distance),
        (xmax + buffer_distance, ymax + buffer_distance),
        (xmin - buffer_distance, ymax + buffer_distance)
    ])
    
    # Create boundary geodataframe with same CRS as isohypses
    boundary_gdf = gpd.GeoDataFrame([1], geometry=[boundary], crs=gdf_isohypses.crs)
    
    # Clip isohypses to the buffered model grid extent
    print(f"Original isohypses: {len(gdf_isohypses)} features")
    gdf_clipped = gpd.clip(gdf_isohypses, boundary_gdf)
    print(f"Clipped isohypses: {len(gdf_clipped)} features")
    
    if len(gdf_clipped) == 0:
        raise ValueError("No isohypses found within the model grid extent (including buffer). Check CRS alignment.")
    
    # Use clipped data for interpolation
    gdf_isohypses = gdf_clipped
    
    # Get model grid coordinates
    x_centers = modelgrid.xcellcenters
    y_centers = modelgrid.ycellcenters
    
    # Create arrays of point coordinates for interpolation
    x_flat = x_centers.flatten()
    y_flat = y_centers.flatten()
    
    # Extract points and values from isohypse lines
    points_x = []
    points_y = []
    values = []
    
    # Assuming the elevation values are in a column (adjust column name as needed)
    # Common column names: 'ELEVATION', 'VALUE', 'Z', 'GW_ELEV', etc.
    elevation_column = None
    
    # Try to identify the elevation column
    possible_columns = ['ELEVATION', 'ELEV', 'VALUE', 'Z', 'GW_ELEV', 'HEIGHT', 'H']
    for col in possible_columns:
        if col in gdf_isohypses.columns:
            elevation_column = col
            break
    
    if elevation_column is None:
        # If no standard column found, use the first numeric column
        numeric_columns = gdf_isohypses.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            elevation_column = numeric_columns[0]
            print(f"Using column '{elevation_column}' for elevation values")
        else:
            raise ValueError("No elevation column found in the geodataframe")
    
    # Extract points along each isohypse line
    for idx, row in gdf_isohypses.iterrows():
        geom = row.geometry
        elevation = row[elevation_column]
        
        if geom.geom_type == 'LineString':
            # Sample points along the line
            coords = list(geom.coords)
            for coord in coords:
                points_x.append(coord[0])
                points_y.append(coord[1])
                values.append(elevation)
        
        elif geom.geom_type == 'MultiLineString':
            # Handle multipart lines
            for line in geom.geoms:
                coords = list(line.coords)
                for coord in coords:
                    points_x.append(coord[0])
                    points_y.append(coord[1])
                    values.append(elevation)
    
    # Convert to numpy arrays
    points_x = np.array(points_x)
    points_y = np.array(points_y)
    values = np.array(values)
    
    # Create points array for scipy interpolation
    points = np.column_stack((points_x, points_y))
    grid_points = np.column_stack((x_flat, y_flat))
    
    # Interpolate using different methods (you can choose the best one)
    print("Interpolating groundwater elevations...")
    
    # Method 1: Linear interpolation (recommended for most cases)
    try:
        interpolated_values = griddata(points, values, grid_points, method='linear')
        
        # Fill any NaN values with nearest neighbor interpolation
        nan_mask = np.isnan(interpolated_values)
        if np.any(nan_mask):
            print("Filling NaN values with nearest neighbor interpolation...")
            interpolated_nearest = griddata(points, values, grid_points, method='nearest')
            interpolated_values[nan_mask] = interpolated_nearest[nan_mask]
    
    except Exception as e:
        print(f"Linear interpolation failed: {e}")
        print("Using nearest neighbor interpolation...")
        interpolated_values = griddata(points, values, grid_points, method='nearest')
    
    # Reshape back to grid dimensions
    gw_elevations = interpolated_values.reshape(x_centers.shape)
    
    return gw_elevations

def alternative_raster_interpolation(gdf_isohypses, modelgrid, cell_size=10):
    """
    Alternative method using rasterization and resampling.
    Useful if the line-based interpolation doesn't work well.
    
    Parameters:
    -----------
    gdf_isohypses : geopandas.GeoDataFrame
        Geodataframe containing isohypse lines
    modelgrid : flopy.discretization.StructuredGrid
        MODFLOW structured grid object
    cell_size : float
        Resolution for intermediate raster (meters)
    
    Returns:
    --------
    numpy.ndarray
        2D array of interpolated groundwater elevations
    """
    
    # Get model bounds
    xmin, xmax, ymin, ymax = modelgrid.extent
    
    # Create high-resolution grid for rasterization
    width = int((xmax - xmin) / cell_size)
    height = int((ymax - ymin) / cell_size)
    
    # Create transform for the raster
    from rasterio.transform import from_bounds
    transform = from_bounds(xmin, ymin, xmax, ymax, width, height)
    
    # Identify elevation column (same logic as above)
    elevation_column = None
    possible_columns = ['ELEVATION', 'ELEV', 'VALUE', 'Z', 'GW_ELEV', 'HEIGHT', 'H']
    for col in possible_columns:
        if col in gdf_isohypses.columns:
            elevation_column = col
            break
    
    if elevation_column is None:
        numeric_columns = gdf_isohypses.select_dtypes(include=[np.number]).columns
        elevation_column = numeric_columns[0] if len(numeric_columns) > 0 else 'value'
    
    # Create shapes for rasterization
    shapes = [(geom, value) for geom, value in zip(gdf_isohypses.geometry, gdf_isohypses[elevation_column])]
    
    # Rasterize the lines
    raster = rasterize(shapes, out_shape=(height, width), transform=transform, dtype=np.float32)
    
    # Get model grid coordinates
    x_centers = modelgrid.xcellcenters.flatten()
    y_centers = modelgrid.ycellcenters.flatten()
    
    # Sample the raster at model grid points
    from rasterio.transform import rowcol
    interpolated_values = []
    
    for x, y in zip(x_centers, y_centers):
        row, col = rowcol(transform, x, y)
        if 0 <= row < height and 0 <= col < width:
            interpolated_values.append(raster[row, col])
        else:
            interpolated_values.append(np.nan)
    
    # Convert to numpy array and reshape
    interpolated_values = np.array(interpolated_values)
    gw_elevations = interpolated_values.reshape(modelgrid.xcellcenters.shape)
    
    return gw_elevations