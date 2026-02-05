"""
DISV Grid Utilities for MODFLOW 6 Unstructured Grids

This module provides helper functions for creating and working with
Voronoi-based unstructured grids (DISV) in MODFLOW 6. It is designed
to complement the existing grid_utils.py (for structured grids) and
uses FloPy utilities wherever possible.

Key capabilities:
- Create Voronoi grids from boundary polygons
- Add local refinement to existing grids
- Export model arrays to GeoPackage format
- Assign properties and points to grid cells via spatial intersection

Requirements:
- FloPy >= 3.4.0 (for stable DISV support)
- geopandas
- shapely
- numpy

References:
- FloPy VoronoiGrid: https://flopy.readthedocs.io/en/latest/source/flopy.utils.voronoi.html
- MODFLOW 6 DISV: https://modflow6.readthedocs.io/en/latest/mf6io_gwf_disv.html
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import geopandas as gpd
import numpy as np
from shapely.geometry import Point, Polygon, MultiPolygon, box
from shapely.ops import unary_union

try:
    import flopy
    from flopy.discretization import VertexGrid, StructuredGrid
    from flopy.utils.voronoi import VoronoiGrid
    from flopy.utils.gridintersect import GridIntersect

    # Check FloPy version
    flopy_version = tuple(int(x) for x in flopy.__version__.split('.')[:2])
    if flopy_version < (3, 4):
        warnings.warn(
            f"FloPy version {flopy.__version__} detected. "
            "This module requires FloPy >= 3.4.0 for stable DISV support. "
            "Some features may not work correctly."
        )
except ImportError as e:
    raise ImportError(
        "FloPy is required for disv_grid_utils. "
        "Install with: pip install flopy>=3.4.0"
    ) from e


def create_voronoi_grid(
    boundary_gdf: gpd.GeoDataFrame,
    cell_size: float,
    rotation_angle: Optional[float] = None,
    crs: Optional[str] = None,
) -> Tuple[VoronoiGrid, VertexGrid]:
    """
    Create a Voronoi-based unstructured grid for MODFLOW 6 DISV.

    This function wraps flopy.utils.voronoi.VoronoiGrid to generate a Voronoi
    tessellation within the provided boundary polygon. The resulting grid
    satisfies the control volume finite difference (CVFD) requirements of
    MODFLOW 6, where flow directions are perpendicular to cell faces.

    Parameters
    ----------
    boundary_gdf : geopandas.GeoDataFrame
        GeoDataFrame containing the model boundary polygon. Should contain
        a single polygon or multipolygon geometry. If multiple features
        exist, they will be dissolved into a single boundary.
    cell_size : float
        Target cell size in the units of the CRS (typically meters).
        This determines the spacing of seed points for Voronoi generation.
        Actual cell sizes will vary, especially near boundaries.
    rotation_angle : float, optional
        Rotation angle in degrees for aligning the seed point grid with
        the principal flow direction. Positive values rotate counter-clockwise.
        If None, no rotation is applied.
    crs : str, optional
        Coordinate reference system for the output grid. If None, uses
        the CRS from boundary_gdf. Example: 'EPSG:2056' for Swiss LV95.

    Returns
    -------
    vor : flopy.utils.voronoi.VoronoiGrid
        The VoronoiGrid object containing vertices and cell connectivity.
    modelgrid : flopy.discretization.VertexGrid
        A FloPy VertexGrid object that can be used for model construction
        and visualization.

    Examples
    --------
    >>> import geopandas as gpd
    >>> from disv_grid_utils import create_voronoi_grid
    >>> boundary = gpd.read_file("model_boundary.gpkg")
    >>> vor, modelgrid = create_voronoi_grid(boundary, cell_size=50)
    >>> print(f"Created grid with {modelgrid.ncpl} cells")

    Notes
    -----
    - The function generates a regular grid of seed points within the boundary,
      then uses Voronoi tessellation to create cells.
    - Cells near the boundary may have irregular shapes due to clipping.
    - For local refinement, use refine_grid_locally() instead.

    See Also
    --------
    create_disv_from_boundary : More advanced grid creation with boundary vertices
    refine_grid_locally : Add local refinement to an existing grid
    """
    # Validate input
    if boundary_gdf.empty:
        raise ValueError("boundary_gdf is empty")

    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")

    # Determine CRS
    output_crs = crs or boundary_gdf.crs
    if output_crs is None:
        warnings.warn(
            "No CRS specified and boundary_gdf has no CRS. "
            "Grid coordinates will be in unknown units."
        )

    # Dissolve to single boundary polygon
    boundary_union = unary_union(boundary_gdf.geometry)
    if isinstance(boundary_union, MultiPolygon):
        # Use the largest polygon if multipolygon
        boundary_polygon = max(boundary_union.geoms, key=lambda p: p.area)
        warnings.warn(
            "boundary_gdf contains multiple polygons. "
            "Using the largest polygon as the boundary."
        )
    elif isinstance(boundary_union, Polygon):
        boundary_polygon = boundary_union
    else:
        raise ValueError(
            f"Expected Polygon or MultiPolygon, got {type(boundary_union)}"
        )

    # Get boundary extent
    minx, miny, maxx, maxy = boundary_polygon.bounds

    # Generate seed points within the boundary
    seed_points = _generate_seed_points(
        boundary_polygon, cell_size, rotation_angle
    )

    if len(seed_points) == 0:
        raise ValueError(
            f"No seed points generated. Check that cell_size ({cell_size}) "
            f"is appropriate for the boundary extent."
        )

    # Create Voronoi grid using FloPy
    # Extract boundary as list of vertices
    boundary_vertices = list(boundary_polygon.exterior.coords)

    vor = VoronoiGrid(
        boundary=boundary_vertices,
        point_data=seed_points,
    )

    # Create VertexGrid from VoronoiGrid
    vertices = vor.vertices
    cell2d = vor.cell2d
    ncpl = len(cell2d)

    # Get cell centers for top/bottom arrays
    xcyc = vor.get_cell_xy()

    # Create placeholder top/bottom (will be set by user)
    top = np.ones(ncpl)
    botm = np.zeros((1, ncpl))

    modelgrid = VertexGrid(
        vertices=vertices,
        cell2d=cell2d,
        top=top,
        botm=botm,
        nlay=1,
        ncpl=ncpl,
        crs=output_crs,
    )

    return vor, modelgrid


def create_disv_from_boundary(
    boundary_gdf: gpd.GeoDataFrame,
    cell_size: float,
    refinement_areas: Optional[List[Tuple[gpd.GeoDataFrame, float]]] = None,
    include_boundary_vertices: bool = True,
    crs: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create DISV grid data with proper boundary vertex handling.

    This function creates a complete DISV (Discretization by Vertices) grid
    with options for local refinement and proper handling of boundary vertices.
    It ensures that boundary vertices are incorporated to avoid cells extending
    outside the model domain.

    Parameters
    ----------
    boundary_gdf : geopandas.GeoDataFrame
        GeoDataFrame containing the model boundary polygon.
    cell_size : float
        Base target cell size in CRS units (typically meters).
    refinement_areas : list of (GeoDataFrame, float), optional
        List of tuples specifying refinement areas. Each tuple contains:
        - GeoDataFrame with polygon(s) defining the refinement area
        - float specifying the refined cell size for that area
        Areas are processed in order, so later entries override earlier ones.
    include_boundary_vertices : bool, default True
        If True, ensures boundary polygon vertices are included as seed points
        to maintain domain boundary alignment.
    crs : str, optional
        Coordinate reference system. If None, uses CRS from boundary_gdf.

    Returns
    -------
    dict
        Dictionary containing DISV grid components:
        - 'vor': VoronoiGrid object
        - 'modelgrid': VertexGrid object
        - 'vertices': list of (iv, xv, yv) vertex tuples for DISV package
        - 'cell2d': list of cell connectivity for DISV package
        - 'ncpl': number of cells per layer
        - 'nvert': number of vertices
        - 'seed_points': array of seed point coordinates used
        - 'crs': coordinate reference system

    Examples
    --------
    Basic usage:

    >>> boundary = gpd.read_file("model_boundary.gpkg")
    >>> disv_data = create_disv_from_boundary(boundary, cell_size=50)
    >>> print(f"Grid has {disv_data['ncpl']} cells")

    With local refinement:

    >>> study_area = gpd.read_file("study_area.gpkg")
    >>> refinement_areas = [(study_area, 10)]  # 10m cells in study area
    >>> disv_data = create_disv_from_boundary(
    ...     boundary, cell_size=50, refinement_areas=refinement_areas
    ... )

    Notes
    -----
    This function regenerates the entire Voronoi tessellation with all
    seed points (base + refinement). For iterative refinement of an
    existing grid, use refine_grid_locally() instead.

    See Also
    --------
    create_voronoi_grid : Simpler grid creation without refinement
    refine_grid_locally : Add refinement to existing grid
    """
    # Validate input
    if boundary_gdf.empty:
        raise ValueError("boundary_gdf is empty")

    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")

    # Determine CRS
    output_crs = crs or boundary_gdf.crs

    # Dissolve to single boundary polygon
    boundary_union = unary_union(boundary_gdf.geometry)
    if isinstance(boundary_union, MultiPolygon):
        boundary_polygon = max(boundary_union.geoms, key=lambda p: p.area)
        warnings.warn(
            "boundary_gdf contains multiple polygons. Using largest polygon."
        )
    elif isinstance(boundary_union, Polygon):
        boundary_polygon = boundary_union
    else:
        raise ValueError(
            f"Expected Polygon or MultiPolygon, got {type(boundary_union)}"
        )

    # Collect all seed points
    all_seed_points = []

    # Generate base seed points
    base_seeds = _generate_seed_points(boundary_polygon, cell_size, None)
    all_seed_points.extend(base_seeds)

    # Add boundary vertices if requested
    if include_boundary_vertices:
        boundary_coords = list(boundary_polygon.exterior.coords)[:-1]  # Exclude closing point
        # Densify boundary with additional points
        densified_boundary = _densify_boundary(boundary_coords, cell_size / 2)
        all_seed_points.extend(densified_boundary)

    # Add refinement area seed points
    if refinement_areas:
        for refine_gdf, refine_cell_size in refinement_areas:
            if refine_cell_size <= 0:
                raise ValueError(
                    f"Refinement cell_size must be positive, got {refine_cell_size}"
                )

            # Dissolve refinement area
            refine_union = unary_union(refine_gdf.geometry)

            # Clip to boundary
            refine_clipped = refine_union.intersection(boundary_polygon)

            if refine_clipped.is_empty:
                warnings.warn(
                    "Refinement area does not intersect model boundary. Skipping."
                )
                continue

            # Generate refined seed points
            refined_seeds = _generate_seed_points(
                refine_clipped, refine_cell_size, None
            )

            # Remove base seeds that fall within refinement area
            # to avoid overlapping seeds
            all_seed_points = [
                p for p in all_seed_points
                if not Point(p).within(refine_clipped)
            ]

            all_seed_points.extend(refined_seeds)

    # Convert to numpy array and remove duplicates
    seed_array = np.array(all_seed_points)
    seed_array = _remove_duplicate_points(seed_array, tolerance=cell_size / 10)

    if len(seed_array) == 0:
        raise ValueError("No seed points generated after processing")

    # Create Voronoi grid
    boundary_vertices = list(boundary_polygon.exterior.coords)

    vor = VoronoiGrid(
        boundary=boundary_vertices,
        point_data=seed_array.tolist(),
    )

    # Extract DISV components
    vertices = vor.vertices
    cell2d = vor.cell2d
    ncpl = len(cell2d)
    nvert = len(vertices)

    # Create placeholder arrays
    top = np.ones(ncpl)
    botm = np.zeros((1, ncpl))

    # Create VertexGrid
    modelgrid = VertexGrid(
        vertices=vertices,
        cell2d=cell2d,
        top=top,
        botm=botm,
        nlay=1,
        ncpl=ncpl,
        crs=output_crs,
    )

    return {
        'vor': vor,
        'modelgrid': modelgrid,
        'vertices': vertices,
        'cell2d': cell2d,
        'ncpl': ncpl,
        'nvert': nvert,
        'seed_points': seed_array,
        'crs': output_crs,
    }


def refine_grid_locally(
    base_grid: Union[VoronoiGrid, Dict[str, Any]],
    refinement_gdf: gpd.GeoDataFrame,
    refined_cell_size: float,
    boundary_gdf: Optional[gpd.GeoDataFrame] = None,
) -> Dict[str, Any]:
    """
    Add local refinement to an existing DISV grid.

    This function regenerates the Voronoi tessellation with additional
    seed points in the specified refinement area. It is designed for
    students to refine the base grid around their detail study areas
    in case study notebooks.

    Parameters
    ----------
    base_grid : VoronoiGrid or dict
        Either a VoronoiGrid object from create_voronoi_grid(), or
        a dictionary from create_disv_from_boundary() containing
        'seed_points' and boundary information.
    refinement_gdf : geopandas.GeoDataFrame
        GeoDataFrame with polygon(s) defining the area(s) to refine.
        Multiple polygons will be merged.
    refined_cell_size : float
        Target cell size within the refinement area (in CRS units).
        Should be smaller than the base grid cell size.
    boundary_gdf : geopandas.GeoDataFrame, optional
        Model boundary polygon. Required if base_grid is a VoronoiGrid
        object (to get boundary coordinates). Not needed if base_grid
        is a dictionary containing boundary information.

    Returns
    -------
    dict
        Dictionary with updated DISV grid components (same format as
        create_disv_from_boundary output), plus:
        - 'base_cell_count': number of cells before refinement
        - 'refined_cell_count': number of cells after refinement
        - 'refinement_area_m2': area of the refinement zone

    Examples
    --------
    >>> # Load base grid (created in Notebook 4)
    >>> base_data = create_disv_from_boundary(boundary, cell_size=50)
    >>>
    >>> # Define study area for local refinement
    >>> my_study_area = gpd.read_file("my_study_polygon.gpkg")
    >>>
    >>> # Refine locally
    >>> refined_data = refine_grid_locally(
    ...     base_data, my_study_area, refined_cell_size=10
    ... )
    >>>
    >>> print(f"Cells: {refined_data['base_cell_count']} -> {refined_data['refined_cell_count']}")

    Notes
    -----
    - The entire grid is regenerated, not just the refinement area.
    - Boundary condition data stored as geometries will automatically
      work with the refined grid via spatial intersection.
    - For best results, refinement_cell_size should be significantly
      smaller than the base cell size (e.g., 1/3 to 1/5).

    See Also
    --------
    create_disv_from_boundary : Initial grid creation with refinement
    assign_properties_from_zones : Reassign properties after refinement
    """
    # Extract base grid information
    if isinstance(base_grid, dict):
        seed_points = base_grid.get('seed_points')
        boundary_vertices = base_grid['vor'].boundary if 'vor' in base_grid else None
        output_crs = base_grid.get('crs')
        base_ncpl = base_grid.get('ncpl', 0)

        if seed_points is None:
            raise ValueError(
                "base_grid dictionary must contain 'seed_points'. "
                "Use create_disv_from_boundary() to create the base grid."
            )
    elif isinstance(base_grid, VoronoiGrid):
        # Get seed points from VoronoiGrid cell centers
        seed_points = np.array(base_grid.get_cell_xy())
        boundary_vertices = base_grid.boundary
        output_crs = None
        base_ncpl = len(base_grid.cell2d)
    else:
        raise TypeError(
            f"base_grid must be VoronoiGrid or dict, got {type(base_grid)}"
        )

    # Get boundary polygon
    if boundary_gdf is not None:
        boundary_union = unary_union(boundary_gdf.geometry)
        if isinstance(boundary_union, MultiPolygon):
            boundary_polygon = max(boundary_union.geoms, key=lambda p: p.area)
        else:
            boundary_polygon = boundary_union
        boundary_vertices = list(boundary_polygon.exterior.coords)
        if output_crs is None:
            output_crs = boundary_gdf.crs
    elif boundary_vertices is not None:
        boundary_polygon = Polygon(boundary_vertices)
    else:
        raise ValueError(
            "boundary_gdf is required when base_grid is a VoronoiGrid object"
        )

    # Validate refinement input
    if refinement_gdf.empty:
        raise ValueError("refinement_gdf is empty")

    if refined_cell_size <= 0:
        raise ValueError(
            f"refined_cell_size must be positive, got {refined_cell_size}"
        )

    # Process refinement area
    refine_union = unary_union(refinement_gdf.geometry)
    refine_clipped = refine_union.intersection(boundary_polygon)

    if refine_clipped.is_empty:
        raise ValueError(
            "Refinement area does not intersect model boundary"
        )

    refinement_area = refine_clipped.area

    # Generate refined seed points
    refined_seeds = _generate_seed_points(refine_clipped, refined_cell_size, None)

    # Remove base seeds within refinement area
    new_seeds = []
    for p in seed_points:
        point = Point(p[0], p[1]) if len(p) >= 2 else Point(p)
        if not point.within(refine_clipped):
            new_seeds.append(p)

    # Combine seed points
    all_seeds = new_seeds + refined_seeds
    seed_array = np.array(all_seeds)
    seed_array = _remove_duplicate_points(seed_array, tolerance=refined_cell_size / 10)

    # Create new Voronoi grid
    vor = VoronoiGrid(
        boundary=boundary_vertices,
        point_data=seed_array.tolist(),
    )

    # Extract DISV components
    vertices = vor.vertices
    cell2d = vor.cell2d
    ncpl = len(cell2d)
    nvert = len(vertices)

    # Create placeholder arrays
    top = np.ones(ncpl)
    botm = np.zeros((1, ncpl))

    # Create VertexGrid
    modelgrid = VertexGrid(
        vertices=vertices,
        cell2d=cell2d,
        top=top,
        botm=botm,
        nlay=1,
        ncpl=ncpl,
        crs=output_crs,
    )

    return {
        'vor': vor,
        'modelgrid': modelgrid,
        'vertices': vertices,
        'cell2d': cell2d,
        'ncpl': ncpl,
        'nvert': nvert,
        'seed_points': seed_array,
        'crs': output_crs,
        'base_cell_count': base_ncpl,
        'refined_cell_count': ncpl,
        'refinement_area_m2': refinement_area,
    }


def export_grid_to_geopackage(
    modelgrid: Union[VertexGrid, StructuredGrid],
    array: np.ndarray,
    output_path: str,
    layer_name: str,
    array_name: str = "value",
    crs: Optional[str] = None,
) -> str:
    """
    Export a model array to GeoPackage for QGIS visualization.

    This function creates a GeoPackage file with cell polygons and
    associated array values. It works with both StructuredGrid and
    VertexGrid (DISV) grids from FloPy.

    Parameters
    ----------
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object. For DISV grids, use VertexGrid.
        For structured grids, use StructuredGrid.
    array : numpy.ndarray
        Array of values to export. Shape should match the grid:
        - For VertexGrid: 1D array of length ncpl, or 2D (nlay, ncpl)
        - For StructuredGrid: 2D (nrow, ncol) or 3D (nlay, nrow, ncol)
    output_path : str
        Path for the output GeoPackage file. Will be created or
        overwritten. Should end with '.gpkg'.
    layer_name : str
        Name of the layer within the GeoPackage. Allows multiple
        arrays to be stored in the same file.
    array_name : str, default "value"
        Column name for the array values in the output GeoDataFrame.
    crs : str, optional
        Coordinate reference system (e.g., 'EPSG:2056'). If None,
        attempts to use modelgrid.crs.

    Returns
    -------
    str
        Path to the created GeoPackage file.

    Examples
    --------
    Export hydraulic conductivity:

    >>> hk = np.random.uniform(10, 50, size=modelgrid.ncpl)
    >>> export_grid_to_geopackage(
    ...     modelgrid, hk, "output/hk.gpkg", "hydraulic_k", "K_m_day"
    ... )

    Export heads from simulation:

    >>> heads = gwf.output.head().get_data()
    >>> export_grid_to_geopackage(
    ...     modelgrid, heads[0], "output/heads.gpkg", "heads_layer1", "head_m"
    ... )

    Notes
    -----
    - For multi-layer models, export one layer at a time or use
      different layer_names.
    - GeoPackage files can be opened directly in QGIS, ArcGIS,
      or other GIS software.
    - Large grids may take a few seconds to export.

    See Also
    --------
    assign_properties_from_zones : Import zone values to grid
    """
    # Validate output path
    if not output_path.endswith('.gpkg'):
        output_path = output_path + '.gpkg'

    # Determine CRS
    output_crs = crs
    if output_crs is None:
        if hasattr(modelgrid, 'crs') and modelgrid.crs is not None:
            output_crs = modelgrid.crs
        else:
            warnings.warn(
                "No CRS specified. Output GeoPackage will have unknown CRS."
            )

    # Flatten array if needed and validate shape
    array = np.asarray(array)
    if array.ndim > 2:
        # Take first layer for 3D arrays
        array = array[0]
        warnings.warn(
            "Array has more than 2 dimensions. Using first layer only."
        )
    if array.ndim == 2:
        array = array.flatten()

    # Create cell polygons
    polygons = []
    values = []
    cell_ids = []

    if isinstance(modelgrid, VertexGrid):
        # DISV grid - use cell2d connectivity
        ncpl = modelgrid.ncpl

        if len(array) != ncpl:
            raise ValueError(
                f"Array length ({len(array)}) does not match grid cells ({ncpl})"
            )

        # Get vertices
        vertices = modelgrid.vertices
        vert_dict = {v[0]: (v[1], v[2]) for v in vertices}

        # Build cell polygons from cell2d
        for cell in modelgrid.cell2d:
            cell_id = cell[0]
            # cell[1], cell[2] are xc, yc
            # cell[3] is nvert
            # cell[4:] are vertex indices
            nvert = cell[3]
            vert_ids = cell[4:4+nvert]

            coords = [vert_dict[vid] for vid in vert_ids]
            # Close the polygon
            coords.append(coords[0])

            try:
                poly = Polygon(coords)
                if poly.is_valid:
                    polygons.append(poly)
                    values.append(array[cell_id])
                    cell_ids.append(cell_id)
                else:
                    # Try to fix invalid polygon
                    poly = poly.buffer(0)
                    polygons.append(poly)
                    values.append(array[cell_id])
                    cell_ids.append(cell_id)
            except Exception as e:
                warnings.warn(f"Could not create polygon for cell {cell_id}: {e}")
                continue

    elif isinstance(modelgrid, StructuredGrid):
        # Structured grid
        nrow = modelgrid.nrow
        ncol = modelgrid.ncol

        expected_size = nrow * ncol
        if len(array) != expected_size:
            raise ValueError(
                f"Array length ({len(array)}) does not match grid cells ({expected_size})"
            )

        # Reshape if needed
        if array.ndim == 1:
            array = array.reshape((nrow, ncol))

        for i in range(nrow):
            for j in range(ncol):
                try:
                    # Get cell vertices
                    xv = modelgrid.xvertices
                    yv = modelgrid.yvertices

                    # Cell corners (counterclockwise)
                    coords = [
                        (xv[i, j], yv[i, j]),
                        (xv[i, j+1], yv[i, j+1]),
                        (xv[i+1, j+1], yv[i+1, j+1]),
                        (xv[i+1, j], yv[i+1, j]),
                        (xv[i, j], yv[i, j]),  # Close polygon
                    ]

                    poly = Polygon(coords)
                    polygons.append(poly)
                    values.append(array[i, j])
                    cell_ids.append(i * ncol + j)
                except Exception as e:
                    warnings.warn(f"Could not create polygon for cell ({i},{j}): {e}")
                    continue
    else:
        raise TypeError(
            f"modelgrid must be VertexGrid or StructuredGrid, got {type(modelgrid)}"
        )

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(
        {
            'cell_id': cell_ids,
            array_name: values,
        },
        geometry=polygons,
        crs=output_crs,
    )

    # Export to GeoPackage
    gdf.to_file(output_path, layer=layer_name, driver='GPKG')

    return output_path


def assign_properties_from_zones(
    zones_gdf: gpd.GeoDataFrame,
    modelgrid: Union[VertexGrid, StructuredGrid],
    property_map: Dict[Any, float],
    zone_column: str = 'zone',
    default_value: Optional[float] = None,
) -> np.ndarray:
    """
    Assign property values to grid cells based on zone polygons.

    This function uses FloPy's GridIntersect to determine which cells
    fall within each zone polygon, then assigns the corresponding
    property value from the property_map.

    Parameters
    ----------
    zones_gdf : geopandas.GeoDataFrame
        GeoDataFrame with zone polygons. Must contain a column
        identifying each zone (specified by zone_column).
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object.
    property_map : dict
        Dictionary mapping zone identifiers to property values.
        Keys should match values in the zone_column.
        Example: {1: 25.0, 2: 15.0, 3: 40.0} for K values by zone.
    zone_column : str, default 'zone'
        Name of the column in zones_gdf that contains zone identifiers.
    default_value : float, optional
        Value to assign to cells that don't fall within any zone.
        If None, cells outside all zones will have NaN.

    Returns
    -------
    numpy.ndarray
        1D array of property values, one per grid cell.
        For MODFLOW 6, this can be used directly in packages like NPF.

    Examples
    --------
    >>> # Define K values by geological zone
    >>> zones = gpd.read_file("geological_zones.gpkg")
    >>> k_values = {
    ...     'alluvium_upstream': 25.0,
    ...     'alluvium_downstream': 15.0,
    ...     'hardhof_gravels': 40.0,
    ... }
    >>> hk = assign_properties_from_zones(zones, modelgrid, k_values, zone_column='geology')

    Notes
    -----
    - Uses flopy.utils.gridintersect.GridIntersect internally.
    - For cells that overlap multiple zones, the zone with the
      largest intersection area is used.
    - Works with both StructuredGrid and VertexGrid (DISV).

    See Also
    --------
    assign_points_to_grid : Assign point data to cells
    export_grid_to_geopackage : Export results to GeoPackage
    """
    # Validate inputs
    if zones_gdf.empty:
        raise ValueError("zones_gdf is empty")

    if zone_column not in zones_gdf.columns:
        raise ValueError(
            f"Column '{zone_column}' not found in zones_gdf. "
            f"Available columns: {list(zones_gdf.columns)}"
        )

    # Determine number of cells
    if isinstance(modelgrid, VertexGrid):
        ncells = modelgrid.ncpl
    elif isinstance(modelgrid, StructuredGrid):
        ncells = modelgrid.nrow * modelgrid.ncol
    else:
        raise TypeError(
            f"modelgrid must be VertexGrid or StructuredGrid, got {type(modelgrid)}"
        )

    # Initialize output array
    if default_value is not None:
        properties = np.full(ncells, default_value, dtype=float)
    else:
        properties = np.full(ncells, np.nan, dtype=float)

    # Track which cells have been assigned
    cell_areas = np.zeros(ncells, dtype=float)  # Track max intersection area

    # Create GridIntersect object
    try:
        gix = GridIntersect(modelgrid, method='vertex', rtree=True)
    except Exception:
        # Fallback without rtree
        gix = GridIntersect(modelgrid, method='vertex', rtree=False)

    # Process each zone
    for idx, row in zones_gdf.iterrows():
        zone_id = row[zone_column]
        geom = row.geometry

        if zone_id not in property_map:
            warnings.warn(
                f"Zone '{zone_id}' not found in property_map. Skipping."
            )
            continue

        prop_value = property_map[zone_id]

        # Intersect zone polygon with grid
        try:
            result = gix.intersect(geom, shapetype='polygon')
        except Exception as e:
            warnings.warn(f"Intersection failed for zone '{zone_id}': {e}")
            continue

        # Assign property to intersected cells
        for rec in result:
            # Get cell ID
            cellid = rec.cellids

            # Handle different cellid formats
            if isinstance(cellid, tuple):
                if len(cellid) == 2:  # (row, col) for structured
                    cell_idx = cellid[0] * modelgrid.ncol + cellid[1]
                elif len(cellid) == 1:  # (node,) for unstructured
                    cell_idx = cellid[0]
                else:
                    cell_idx = cellid[-1]  # Last element is usually cell index
            else:
                cell_idx = int(cellid)

            # Get intersection area
            try:
                area = rec.areas
            except AttributeError:
                # Fallback if areas not available
                area = 1.0

            # Assign if this intersection has larger area than previous
            if area > cell_areas[cell_idx]:
                properties[cell_idx] = prop_value
                cell_areas[cell_idx] = area

    # Report coverage
    assigned_count = np.sum(~np.isnan(properties)) if default_value is None else np.sum(properties != default_value)
    coverage_pct = 100 * assigned_count / ncells

    if coverage_pct < 100 and default_value is None:
        warnings.warn(
            f"Only {coverage_pct:.1f}% of cells assigned from zones. "
            f"{ncells - assigned_count} cells have NaN values."
        )

    return properties


def assign_points_to_grid(
    points_gdf: gpd.GeoDataFrame,
    modelgrid: Union[VertexGrid, StructuredGrid],
    value_column: Optional[str] = None,
    fallback_to_nearest: bool = True,
) -> Union[List[Tuple[int, Any]], np.ndarray]:
    """
    Assign point features (e.g., wells) to DISV grid cells.

    This function determines which grid cell each point falls within,
    using FloPy's GridIntersect. Useful for assigning well locations,
    observation points, or other point-based data to model cells.

    Parameters
    ----------
    points_gdf : geopandas.GeoDataFrame
        GeoDataFrame with Point geometries. May include attribute columns
        with values to aggregate (e.g., pumping rates).
    modelgrid : VertexGrid or StructuredGrid
        FloPy model grid object.
    value_column : str, optional
        Column name containing values to return with cell assignments.
        If None, only cell IDs are returned.
    fallback_to_nearest : bool, default True
        If True, points that fall outside the grid are assigned to the
        nearest cell. If False, such points are excluded with a warning.

    Returns
    -------
    list of tuples or numpy.ndarray
        If value_column is specified:
            List of (cell_id, value) tuples for each point.
        If value_column is None:
            1D numpy array of cell IDs for each point.

    Examples
    --------
    Assign wells to cells:

    >>> wells = gpd.read_file("well_locations.gpkg")
    >>> well_cells = assign_points_to_grid(wells, modelgrid, value_column='rate')
    >>> # Returns: [(cell_id, rate), (cell_id, rate), ...]

    Get cell IDs for observation points:

    >>> obs_points = gpd.read_file("observation_wells.gpkg")
    >>> obs_cells = assign_points_to_grid(obs_points, modelgrid)
    >>> # Returns: array([cell_id1, cell_id2, ...])

    Notes
    -----
    - Uses flopy.utils.gridintersect.GridIntersect internally with
      spatial indexing for efficient lookup.
    - Points exactly on cell boundaries may be assigned to either
      adjacent cell.
    - For wells that span multiple cells, consider using line
      geometries instead.

    See Also
    --------
    assign_properties_from_zones : Assign zone-based properties
    export_grid_to_geopackage : Export assignments for visualization
    """
    # Validate inputs
    if points_gdf.empty:
        warnings.warn("points_gdf is empty")
        if value_column:
            return []
        else:
            return np.array([], dtype=int)

    # Check geometry types
    geom_types = points_gdf.geometry.geom_type.unique()
    if not all(gt == 'Point' for gt in geom_types):
        warnings.warn(
            f"points_gdf contains non-Point geometries: {geom_types}. "
            "Only Point geometries will be processed."
        )
        points_gdf = points_gdf[points_gdf.geometry.geom_type == 'Point'].copy()

    if value_column is not None and value_column not in points_gdf.columns:
        raise ValueError(
            f"Column '{value_column}' not found in points_gdf. "
            f"Available columns: {list(points_gdf.columns)}"
        )

    # Get grid extents for fallback nearest-cell calculation
    if isinstance(modelgrid, VertexGrid):
        xcyc = np.array([(c[1], c[2]) for c in modelgrid.cell2d])
        ncells = modelgrid.ncpl
    elif isinstance(modelgrid, StructuredGrid):
        xcyc = np.column_stack([
            modelgrid.xcellcenters.flatten(),
            modelgrid.ycellcenters.flatten()
        ])
        ncells = modelgrid.nrow * modelgrid.ncol
    else:
        raise TypeError(
            f"modelgrid must be VertexGrid or StructuredGrid, got {type(modelgrid)}"
        )

    # Create GridIntersect object
    try:
        gix = GridIntersect(modelgrid, method='vertex', rtree=True)
    except Exception:
        gix = GridIntersect(modelgrid, method='vertex', rtree=False)

    # Process each point
    cell_ids = []
    values = []

    for idx, row in points_gdf.iterrows():
        point = row.geometry
        x, y = point.x, point.y

        # Try to intersect point with grid
        try:
            result = gix.intersect(point, shapetype='point')

            if len(result) > 0:
                # Point falls within a cell
                cellid = result[0].cellids

                # Handle different cellid formats
                if isinstance(cellid, tuple):
                    if len(cellid) == 2:  # (row, col) for structured
                        cell_idx = cellid[0] * modelgrid.ncol + cellid[1]
                    elif len(cellid) == 1:
                        cell_idx = cellid[0]
                    else:
                        cell_idx = cellid[-1]
                else:
                    cell_idx = int(cellid)

                cell_ids.append(cell_idx)
                if value_column:
                    values.append(row[value_column])

            elif fallback_to_nearest:
                # Point outside grid - find nearest cell
                distances = np.sqrt((xcyc[:, 0] - x)**2 + (xcyc[:, 1] - y)**2)
                nearest_cell = np.argmin(distances)
                cell_ids.append(nearest_cell)
                if value_column:
                    values.append(row[value_column])
                warnings.warn(
                    f"Point at ({x:.1f}, {y:.1f}) outside grid. "
                    f"Assigned to nearest cell {nearest_cell}."
                )
            else:
                warnings.warn(
                    f"Point at ({x:.1f}, {y:.1f}) outside grid. Skipping."
                )

        except Exception as e:
            if fallback_to_nearest:
                # Fallback to nearest cell
                distances = np.sqrt((xcyc[:, 0] - x)**2 + (xcyc[:, 1] - y)**2)
                nearest_cell = np.argmin(distances)
                cell_ids.append(nearest_cell)
                if value_column:
                    values.append(row[value_column])
            else:
                warnings.warn(f"Failed to process point at ({x}, {y}): {e}")

    # Return results
    if value_column:
        return list(zip(cell_ids, values))
    else:
        return np.array(cell_ids, dtype=int)


# =============================================================================
# Private helper functions
# =============================================================================

def _generate_seed_points(
    polygon: Union[Polygon, MultiPolygon],
    cell_size: float,
    rotation_angle: Optional[float],
) -> List[Tuple[float, float]]:
    """
    Generate a regular grid of seed points within a polygon.

    Parameters
    ----------
    polygon : Polygon or MultiPolygon
        Boundary polygon to fill with seed points.
    cell_size : float
        Spacing between seed points.
    rotation_angle : float, optional
        Rotation angle in degrees (counter-clockwise).

    Returns
    -------
    list of (x, y) tuples
        Seed point coordinates within the polygon.
    """
    # Get polygon bounds
    minx, miny, maxx, maxy = polygon.bounds

    # Expand bounds slightly to ensure coverage
    buffer = cell_size
    minx -= buffer
    miny -= buffer
    maxx += buffer
    maxy += buffer

    # Generate regular grid
    x_coords = np.arange(minx, maxx + cell_size, cell_size)
    y_coords = np.arange(miny, maxy + cell_size, cell_size)

    xx, yy = np.meshgrid(x_coords, y_coords)
    points = np.column_stack([xx.ravel(), yy.ravel()])

    # Apply rotation if specified
    if rotation_angle is not None and rotation_angle != 0:
        # Rotate around polygon centroid
        centroid = polygon.centroid
        cx, cy = centroid.x, centroid.y

        theta = np.radians(rotation_angle)
        cos_t, sin_t = np.cos(theta), np.sin(theta)

        # Translate to origin, rotate, translate back
        x_rot = (points[:, 0] - cx) * cos_t - (points[:, 1] - cy) * sin_t + cx
        y_rot = (points[:, 0] - cx) * sin_t + (points[:, 1] - cy) * cos_t + cy

        points = np.column_stack([x_rot, y_rot])

    # Filter points to those within polygon
    seed_points = []
    for x, y in points:
        if polygon.contains(Point(x, y)):
            seed_points.append((x, y))

    return seed_points


def _densify_boundary(
    coords: List[Tuple[float, float]],
    max_segment_length: float,
) -> List[Tuple[float, float]]:
    """
    Add intermediate points along boundary segments.

    Parameters
    ----------
    coords : list of (x, y) tuples
        Boundary vertex coordinates.
    max_segment_length : float
        Maximum distance between consecutive points.

    Returns
    -------
    list of (x, y) tuples
        Densified boundary coordinates.
    """
    densified = []

    for i in range(len(coords)):
        p1 = coords[i]
        p2 = coords[(i + 1) % len(coords)]

        densified.append(p1)

        # Calculate segment length
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = np.sqrt(dx**2 + dy**2)

        # Add intermediate points if segment is too long
        if length > max_segment_length:
            n_segments = int(np.ceil(length / max_segment_length))
            for j in range(1, n_segments):
                t = j / n_segments
                x = p1[0] + t * dx
                y = p1[1] + t * dy
                densified.append((x, y))

    return densified


def _remove_duplicate_points(
    points: np.ndarray,
    tolerance: float,
) -> np.ndarray:
    """
    Remove duplicate points within a tolerance.

    Parameters
    ----------
    points : numpy.ndarray
        Array of shape (n, 2) with point coordinates.
    tolerance : float
        Minimum distance between distinct points.

    Returns
    -------
    numpy.ndarray
        Array with duplicates removed.
    """
    if len(points) == 0:
        return points

    # Use a simple approach: keep points that are far enough from all previous
    unique = [points[0]]

    for p in points[1:]:
        is_duplicate = False
        for u in unique:
            dist = np.sqrt((p[0] - u[0])**2 + (p[1] - u[1])**2)
            if dist < tolerance:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(p)

    return np.array(unique)
