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
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry


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


def _unary_union(gdf: gpd.GeoDataFrame) -> BaseGeometry:
    if gdf is None or gdf.empty:
        raise ValueError("boundary_gdf is empty or None")
    return gdf.geometry.unary_union


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


__all__ = [
    "grid_to_gdf",
    "compute_active_mask",
    "ibound_from_active",
    "build_grid_gdf_and_ibound",
]
