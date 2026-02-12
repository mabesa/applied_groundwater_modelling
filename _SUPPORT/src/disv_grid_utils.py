"""
DISV Grid Utilities for MODFLOW 6 Unstructured Grids

This module provides helper functions for creating and working with
Voronoi-based unstructured grids (DISV) in MODFLOW 6. It is designed
to complement the existing grid_utils.py (for structured grids) and
uses FloPy utilities wherever possible.

Key capabilities:
- Create Voronoi grids from boundary polygons using FloPy's Triangle and VoronoiGrid
- Create grids with river polygons as internal constraints (cells align with river banks)
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

import tempfile
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import geopandas as gpd
import numpy as np
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union

try:
    import flopy
    from flopy.discretization import VertexGrid, StructuredGrid
    from flopy.utils.triangle import Triangle
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
        This determines the maximum_area parameter for Triangle meshing.
        Actual cell sizes will vary, especially near boundaries.
    rotation_angle : float, optional
        Rotation angle in degrees for aligning the seed point grid with
        the principal flow direction. Positive values rotate counter-clockwise.
        If None, no rotation is applied. Note: rotation is applied by
        rotating the boundary polygon before meshing.
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
    - The function uses FloPy's Triangle class for mesh generation and
      VoronoiGrid for creating the Voronoi tessellation.
    - Cells near the boundary may have irregular shapes due to clipping.
    - For local refinement, use refine_grid_locally() or create_disv_from_boundary()
      with refinement_areas parameter.

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
    boundary_polygon = _get_boundary_polygon(boundary_gdf)

    # Apply rotation if specified
    if rotation_angle is not None and rotation_angle != 0:
        boundary_polygon = _rotate_polygon(boundary_polygon, rotation_angle)

    # Convert cell_size to maximum_area for Triangle
    # Triangle uses area, so for roughly square cells: area ≈ cell_size^2
    maximum_area = cell_size ** 2

    # Create Voronoi grid using FloPy utilities
    vor, modelgrid = _create_voronoi_with_flopy(
        boundary_polygon, maximum_area, output_crs
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
    It uses FloPy's Triangle and VoronoiGrid classes for robust mesh generation.

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
        If True, ensures boundary polygon vertices are respected in the mesh.
        This is handled automatically by FloPy's Triangle class.
    crs : str, optional
        Coordinate reference system. If None, uses CRS from boundary_gdf.

    Returns
    -------
    dict
        Dictionary containing DISV grid components:
        - 'voronoi_grid': VoronoiGrid object from FloPy
        - 'modelgrid': VertexGrid object
        - 'vertices': list of (iv, xv, yv) vertex tuples for DISV package
        - 'cell2d': list of cell connectivity for DISV package
        - 'ncpl': number of cells per layer
        - 'nvert': number of vertices
        - 'disv_gridprops': dict that can be unpacked into ModflowGwfdisv
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
    This function uses FloPy's Triangle class with region-based refinement.
    The Triangle class automatically handles boundary vertices and ensures
    proper mesh quality.

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
    boundary_polygon = _get_boundary_polygon(boundary_gdf)

    # Convert cell_size to maximum_area
    base_max_area = cell_size ** 2

    # Process refinement areas
    refinement_polygons = []
    refinement_max_areas = []

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

            # Handle MultiPolygon
            if isinstance(refine_clipped, MultiPolygon):
                for poly in refine_clipped.geoms:
                    refinement_polygons.append(poly)
                    refinement_max_areas.append(refine_cell_size ** 2)
            elif isinstance(refine_clipped, Polygon):
                refinement_polygons.append(refine_clipped)
                refinement_max_areas.append(refine_cell_size ** 2)

    # Create Voronoi grid with refinement
    vor, modelgrid = _create_voronoi_with_refinement(
        boundary_polygon,
        base_max_area,
        refinement_polygons,
        refinement_max_areas,
        output_crs,
    )

    # Extract DISV properties
    disv_gridprops = vor.get_disv_gridprops()
    ncpl = disv_gridprops['ncpl']
    nvert = disv_gridprops['nvert']
    vertices = disv_gridprops['vertices']
    cell2d = disv_gridprops['cell2d']

    return {
        'voronoi_grid': vor,
        'modelgrid': modelgrid,
        'vertices': vertices,
        'cell2d': cell2d,
        'ncpl': ncpl,
        'nvert': nvert,
        'disv_gridprops': disv_gridprops,
        'crs': output_crs,
        # For backwards compatibility with refine_grid_locally
        'boundary_polygon': boundary_polygon,
        'base_max_area': base_max_area,
    }


def create_grid_with_rivers(
    boundary_gdf: gpd.GeoDataFrame,
    river_gdf: gpd.GeoDataFrame,
    cell_size: float,
    river_cell_size: Optional[float] = None,
    refinement_areas: Optional[List[Tuple[gpd.GeoDataFrame, float]]] = None,
    crs: Optional[str] = None,
    min_river_intersection_fraction: float = 0.0,
) -> Dict[str, Any]:
    """
    Create a Voronoi grid with river polygons as internal constraints.

    This function creates a DISV grid where the river banks become mesh edges,
    ensuring that Voronoi cells align with river boundaries. This improves
    accuracy for river-aquifer exchange calculations in the RIV package.

    The river polygons are added as internal boundaries to FloPy's Triangle
    mesh generator. This forces the triangulation to respect river bank
    geometries, and consequently the Voronoi cells align with the rivers.

    Parameters
    ----------
    boundary_gdf : geopandas.GeoDataFrame
        GeoDataFrame containing the model boundary polygon.
    river_gdf : geopandas.GeoDataFrame
        GeoDataFrame containing river polygons (bank geometries).
        These become internal boundaries in the mesh.
    cell_size : float
        Target cell size for the general domain in CRS units (typically meters).
    river_cell_size : float, optional
        Target cell size within and near rivers. Default is cell_size / 2.
        Smaller values provide better resolution of river-aquifer exchange.
    refinement_areas : list of (GeoDataFrame, float), optional
        Additional refinement areas, same format as create_disv_from_boundary().
        Each tuple contains (polygon_gdf, refined_cell_size).
    crs : str, optional
        Coordinate reference system. If None, uses CRS from boundary_gdf.
    min_river_intersection_fraction : float, default 0.0
        Minimum fraction of cell area that must overlap with river polygon
        for the cell to be classified as a river cell. Values between 0.0
        (any overlap) and 1.0 (complete overlap). A value of 0.3 means at
        least 30% of the cell must be covered by river. This helps reduce
        the number of river cells by excluding cells that only marginally
        touch river boundaries.

    Returns
    -------
    dict
        Dictionary containing DISV grid components:
        - 'voronoi_grid': VoronoiGrid object from FloPy
        - 'modelgrid': VertexGrid object
        - 'vertices': list of (iv, xv, yv) vertex tuples for DISV package
        - 'cell2d': list of cell connectivity for DISV package
        - 'ncpl': number of cells per layer
        - 'nvert': number of vertices
        - 'disv_gridprops': dict that can be unpacked into ModflowGwfdisv
        - 'crs': coordinate reference system
        - 'river_cells': numpy array of cell indices inside river polygons
        - 'river_polygons': list of river Polygon objects (clipped to boundary)
        - 'boundary_polygon': the boundary Polygon
        - 'base_max_area': base maximum cell area (for use with refine_grid_locally)

    Examples
    --------
    Basic usage with rivers:

    >>> boundary = gpd.read_file("model_boundary.gpkg")
    >>> rivers = gpd.read_file("rivers.gpkg")
    >>> grid_data = create_grid_with_rivers(
    ...     boundary, rivers, cell_size=50, river_cell_size=20
    ... )
    >>> print(f"Grid has {grid_data['ncpl']} cells")
    >>> print(f"River cells: {len(grid_data['river_cells'])}")

    With additional refinement areas:

    >>> study_area = gpd.read_file("study_area.gpkg")
    >>> grid_data = create_grid_with_rivers(
    ...     boundary, rivers, cell_size=50,
    ...     refinement_areas=[(study_area, 15)]
    ... )

    Notes
    -----
    - River polygons are clipped to the model boundary automatically.
    - Cells inside rivers are identified and returned in 'river_cells'.
    - For best results with RIV package, use river_cell_size <= cell_size / 2.
    - The river banks become edges in the mesh, so Voronoi cell faces
      will align with the river geometry.

    See Also
    --------
    create_disv_from_boundary : Grid creation without river constraints
    create_voronoi_grid : Simple grid creation
    refine_grid_locally : Add local refinement to existing grid
    """
    # Validate inputs
    if boundary_gdf.empty:
        raise ValueError("boundary_gdf is empty")

    if river_gdf.empty:
        raise ValueError("river_gdf is empty")

    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")

    if river_cell_size is None:
        river_cell_size = cell_size / 2

    if river_cell_size <= 0:
        raise ValueError(f"river_cell_size must be positive, got {river_cell_size}")

    # Determine CRS
    output_crs = crs or boundary_gdf.crs

    # Get boundary polygon
    boundary_polygon = _get_boundary_polygon(boundary_gdf)

    # Get river polygons clipped to boundary
    river_union = unary_union(river_gdf.geometry)
    river_clipped = river_union.intersection(boundary_polygon)

    if river_clipped.is_empty:
        warnings.warn(
            "River polygons do not intersect model boundary. "
            "Creating grid without river constraints."
        )
        return create_disv_from_boundary(
            boundary_gdf, cell_size, refinement_areas, crs=crs
        )

    # Simplify river geometry to reduce vertex count
    # Tolerance based on cell size to preserve detail at mesh resolution
    simplify_tolerance = river_cell_size / 4
    river_clipped = river_clipped.simplify(simplify_tolerance, preserve_topology=True)

    # Erode rivers slightly to ensure they don't touch the boundary
    # Triangle fails with coincident vertices between polygons
    erosion = 2.0  # 2 meter erosion
    river_eroded = river_clipped.buffer(-erosion)
    if river_eroded.is_empty:
        # If erosion removes all rivers, use original clipped geometry
        river_eroded = river_clipped

    # Collect river polygons and fill holes (islands)
    # Triangle mesh generator struggles with interior rings
    river_polygons = _extract_polygons_no_holes(river_eroded)

    if not river_polygons:
        warnings.warn(
            "No valid river polygons found. Creating grid without river constraints."
        )
        return create_disv_from_boundary(
            boundary_gdf, cell_size, refinement_areas, crs=crs
        )

    # Process additional refinement areas
    additional_refinement_polygons = []
    additional_refinement_areas = []

    if refinement_areas:
        for refine_gdf, refine_cell_size in refinement_areas:
            if refine_cell_size <= 0:
                raise ValueError(
                    f"Refinement cell_size must be positive, got {refine_cell_size}"
                )

            refine_union = unary_union(refine_gdf.geometry)
            refine_clipped = refine_union.intersection(boundary_polygon)

            if refine_clipped.is_empty:
                warnings.warn(
                    "Refinement area does not intersect model boundary. Skipping."
                )
                continue

            for poly in _extract_polygons(refine_clipped):
                additional_refinement_polygons.append(poly)
                additional_refinement_areas.append(refine_cell_size ** 2)

    # Convert cell sizes to maximum areas
    base_max_area = cell_size ** 2
    river_max_area = river_cell_size ** 2

    # Create Voronoi grid with river constraints
    vor, modelgrid = _create_voronoi_with_rivers(
        boundary_polygon,
        river_polygons,
        base_max_area,
        river_max_area,
        additional_refinement_polygons,
        additional_refinement_areas,
        output_crs,
    )

    # Extract DISV properties
    disv_gridprops = vor.get_disv_gridprops()
    ncpl = disv_gridprops['ncpl']
    nvert = disv_gridprops['nvert']
    vertices = disv_gridprops['vertices']
    cell2d = disv_gridprops['cell2d']

    # Identify cells inside rivers
    river_cells = _identify_river_cells(
        modelgrid,
        river_polygons,
        min_intersection_fraction=min_river_intersection_fraction,
    )

    return {
        'voronoi_grid': vor,
        'modelgrid': modelgrid,
        'vertices': vertices,
        'cell2d': cell2d,
        'ncpl': ncpl,
        'nvert': nvert,
        'disv_gridprops': disv_gridprops,
        'crs': output_crs,
        'river_cells': river_cells,
        'river_polygons': river_polygons,
        'boundary_polygon': boundary_polygon,
        'base_max_area': base_max_area,
    }


def refine_grid_locally(
    base_grid: Dict[str, Any],
    refinement_gdf: gpd.GeoDataFrame,
    refined_cell_size: float,
    boundary_gdf: Optional[gpd.GeoDataFrame] = None,
) -> Dict[str, Any]:
    """
    Add local refinement to an existing DISV grid.

    This function regenerates the Voronoi tessellation with additional
    refinement in the specified area. It is designed for students to
    refine the base grid around their detail study areas in case study
    notebooks.

    Parameters
    ----------
    base_grid : dict
        Dictionary from create_disv_from_boundary() containing grid information.
    refinement_gdf : geopandas.GeoDataFrame
        GeoDataFrame with polygon(s) defining the area(s) to refine.
        Multiple polygons will be merged.
    refined_cell_size : float
        Target cell size within the refinement area (in CRS units).
        Should be smaller than the base grid cell size.
    boundary_gdf : geopandas.GeoDataFrame, optional
        Model boundary polygon. Required if not stored in base_grid.

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
    ...     base_data, my_study_area, refined_cell_size=10, boundary_gdf=boundary
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
    if not isinstance(base_grid, dict):
        raise TypeError(
            f"base_grid must be a dict from create_disv_from_boundary(), got {type(base_grid)}"
        )

    output_crs = base_grid.get('crs')
    base_ncpl = base_grid.get('ncpl', 0)
    boundary_polygon = base_grid.get('boundary_polygon')
    base_max_area = base_grid.get('base_max_area')

    # Get boundary polygon
    if boundary_polygon is None:
        if boundary_gdf is None:
            raise ValueError("boundary_gdf is required for local refinement")
        boundary_polygon = _get_boundary_polygon(boundary_gdf)

    if output_crs is None and boundary_gdf is not None:
        output_crs = boundary_gdf.crs

    if base_max_area is None:
        raise ValueError(
            "base_grid dictionary must contain 'base_max_area'. "
            "Use create_disv_from_boundary() to create the base grid."
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

    # Prepare refinement polygons
    refinement_polygons = []
    if isinstance(refine_clipped, MultiPolygon):
        refinement_polygons = list(refine_clipped.geoms)
    elif isinstance(refine_clipped, Polygon):
        refinement_polygons = [refine_clipped]

    refinement_max_areas = [refined_cell_size ** 2] * len(refinement_polygons)

    # Create new Voronoi grid with refinement
    vor, modelgrid = _create_voronoi_with_refinement(
        boundary_polygon,
        base_max_area,
        refinement_polygons,
        refinement_max_areas,
        output_crs,
    )

    # Extract DISV properties
    disv_gridprops = vor.get_disv_gridprops()
    ncpl = disv_gridprops['ncpl']
    nvert = disv_gridprops['nvert']
    vertices = disv_gridprops['vertices']
    cell2d = disv_gridprops['cell2d']

    return {
        'voronoi_grid': vor,
        'modelgrid': modelgrid,
        'vertices': vertices,
        'cell2d': cell2d,
        'ncpl': ncpl,
        'nvert': nvert,
        'disv_gridprops': disv_gridprops,
        'crs': output_crs,
        'boundary_polygon': boundary_polygon,
        'base_max_area': base_max_area,
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
        vertices = modelgrid._vertices
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

def _get_boundary_polygon(boundary_gdf: gpd.GeoDataFrame) -> Polygon:
    """
    Extract and validate boundary polygon from GeoDataFrame.

    Parameters
    ----------
    boundary_gdf : geopandas.GeoDataFrame
        GeoDataFrame with boundary polygon(s).

    Returns
    -------
    Polygon
        Single boundary polygon.
    """
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
    return boundary_polygon


def _rotate_polygon(polygon: Polygon, angle_degrees: float) -> Polygon:
    """
    Rotate a polygon around its centroid.

    Parameters
    ----------
    polygon : Polygon
        Shapely polygon to rotate.
    angle_degrees : float
        Rotation angle in degrees (counter-clockwise).

    Returns
    -------
    Polygon
        Rotated polygon.
    """
    from shapely import affinity
    return affinity.rotate(polygon, angle_degrees, origin='centroid')


def _create_voronoi_with_flopy(
    boundary_polygon: Polygon,
    maximum_area: float,
    crs: Optional[str],
) -> Tuple[VoronoiGrid, VertexGrid]:
    """
    Create Voronoi grid using FloPy's Triangle and VoronoiGrid classes.

    Parameters
    ----------
    boundary_polygon : Polygon
        Boundary polygon for the model domain.
    maximum_area : float
        Maximum cell area for Triangle meshing.
    crs : str, optional
        Coordinate reference system.

    Returns
    -------
    vor : VoronoiGrid
        FloPy VoronoiGrid object.
    modelgrid : VertexGrid
        FloPy VertexGrid object.
    """
    # Get boundary coordinates as numpy array
    boundary_coords = np.array(boundary_polygon.exterior.coords[:-1])

    # Create Triangle object with a temporary workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        tri = Triangle(maximum_area=maximum_area, angle=30, model_ws=tmpdir)

        # Add the boundary polygon
        tri.add_polygon(boundary_coords)

        # Build the triangular mesh
        tri.build(verbose=False)

        # Create Voronoi grid from Triangle
        vor = VoronoiGrid(tri)

    # Create VertexGrid from VoronoiGrid
    gridprops = vor.get_gridprops_vertexgrid()

    # Add placeholder top/botm for VertexGrid
    ncpl = gridprops['ncpl']
    top = np.ones(ncpl)
    botm = np.zeros((1, ncpl))

    modelgrid = VertexGrid(
        **gridprops,
        top=top,
        botm=botm,
        nlay=1,
        crs=crs,
    )

    return vor, modelgrid


def _create_voronoi_with_refinement(
    boundary_polygon: Polygon,
    base_max_area: float,
    refinement_polygons: List[Polygon],
    refinement_max_areas: List[float],
    crs: Optional[str],
) -> Tuple[VoronoiGrid, VertexGrid]:
    """
    Create Voronoi grid with local refinement using FloPy's Triangle.

    Parameters
    ----------
    boundary_polygon : Polygon
        Boundary polygon for the model domain.
    base_max_area : float
        Maximum cell area for base (non-refined) regions.
    refinement_polygons : list of Polygon
        List of polygons defining refinement areas.
    refinement_max_areas : list of float
        Maximum cell areas for each refinement polygon.
    crs : str, optional
        Coordinate reference system.

    Returns
    -------
    vor : VoronoiGrid
        FloPy VoronoiGrid object.
    modelgrid : VertexGrid
        FloPy VertexGrid object.
    """
    # Get boundary coordinates as numpy array
    boundary_coords = np.array(boundary_polygon.exterior.coords[:-1])

    # Create Triangle object with a temporary workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        tri = Triangle(angle=30, model_ws=tmpdir)

        # Add the boundary polygon (must be first)
        tri.add_polygon(boundary_coords)

        # Add refinement polygons
        for refine_poly in refinement_polygons:
            refine_coords = np.array(refine_poly.exterior.coords[:-1])
            tri.add_polygon(refine_coords)

        # Add regions with different maximum areas
        # Region for base area (point inside boundary but outside refinement)
        base_centroid = boundary_polygon.centroid

        # Find a point in the base region (not in any refinement area)
        base_point = _find_point_outside_polygons(
            boundary_polygon, refinement_polygons
        )
        tri.add_region(base_point, 0, maximum_area=base_max_area)

        # Regions for refinement areas
        for i, (refine_poly, max_area) in enumerate(
            zip(refinement_polygons, refinement_max_areas)
        ):
            centroid = refine_poly.centroid
            tri.add_region((centroid.x, centroid.y), i + 1, maximum_area=max_area)

        # Build the triangular mesh
        tri.build(verbose=False)

        # Create Voronoi grid from Triangle
        vor = VoronoiGrid(tri)

    # Create VertexGrid from VoronoiGrid
    gridprops = vor.get_gridprops_vertexgrid()

    # Add placeholder top/botm for VertexGrid
    ncpl = gridprops['ncpl']
    top = np.ones(ncpl)
    botm = np.zeros((1, ncpl))

    modelgrid = VertexGrid(
        **gridprops,
        top=top,
        botm=botm,
        nlay=1,
        crs=crs,
    )

    return vor, modelgrid


def _find_point_outside_polygons(
    boundary: Polygon,
    exclusion_polygons: List[Polygon],
) -> Tuple[float, float]:
    """
    Find a point inside the boundary but outside all exclusion polygons.

    Parameters
    ----------
    boundary : Polygon
        Outer boundary polygon.
    exclusion_polygons : list of Polygon
        Polygons to avoid.

    Returns
    -------
    tuple
        (x, y) coordinates of a valid point.
    """
    # Try the boundary centroid first
    centroid = boundary.centroid
    if not any(poly.contains(centroid) for poly in exclusion_polygons):
        return (centroid.x, centroid.y)

    # Sample points along a grid within the boundary
    minx, miny, maxx, maxy = boundary.bounds
    for x in np.linspace(minx, maxx, 20):
        for y in np.linspace(miny, maxy, 20):
            point = Point(x, y)
            if boundary.contains(point):
                if not any(poly.contains(point) for poly in exclusion_polygons):
                    return (x, y)

    # Fallback: use boundary centroid anyway
    warnings.warn(
        "Could not find point outside refinement areas. "
        "Using boundary centroid."
    )
    return (centroid.x, centroid.y)


def _extract_polygons(geometry) -> List[Polygon]:
    """
    Extract a list of Polygon objects from various geometry types.

    Parameters
    ----------
    geometry : shapely geometry
        Can be Polygon, MultiPolygon, or GeometryCollection.

    Returns
    -------
    list of Polygon
        List of valid Polygon objects.
    """
    polygons = []

    if geometry is None or geometry.is_empty:
        return polygons

    if isinstance(geometry, Polygon):
        if geometry.is_valid and geometry.area > 0:
            polygons.append(geometry)
    elif isinstance(geometry, MultiPolygon):
        for poly in geometry.geoms:
            if poly.is_valid and poly.area > 0:
                polygons.append(poly)
    elif hasattr(geometry, 'geoms'):
        # GeometryCollection
        for geom in geometry.geoms:
            polygons.extend(_extract_polygons(geom))

    return polygons


def _extract_polygons_no_holes(geometry, min_area: float = 100.0) -> List[Polygon]:
    """
    Extract polygons from geometry, removing interior holes (islands).

    Triangle mesh generator can struggle with interior rings. This function
    extracts only the exterior boundary of each polygon, effectively filling
    any holes (islands in rivers, etc.).

    Parameters
    ----------
    geometry : shapely geometry
        Can be Polygon, MultiPolygon, or GeometryCollection.
    min_area : float, default 100.0
        Minimum polygon area to include (filters tiny fragments).

    Returns
    -------
    list of Polygon
        List of valid Polygon objects without holes.
    """
    polygons = []

    if geometry is None or geometry.is_empty:
        return polygons

    # Get all polygons
    raw_polygons = _extract_polygons(geometry)

    for poly in raw_polygons:
        if poly.area < min_area:
            continue

        # Create new polygon from exterior only (no holes)
        exterior_only = Polygon(poly.exterior.coords)

        if exterior_only.is_valid and exterior_only.area > min_area:
            polygons.append(exterior_only)
        elif not exterior_only.is_valid:
            # Try to fix invalid geometry
            fixed = exterior_only.buffer(0)
            if fixed.is_valid and fixed.area > min_area:
                if isinstance(fixed, Polygon):
                    polygons.append(fixed)
                elif isinstance(fixed, MultiPolygon):
                    for p in fixed.geoms:
                        if p.area > min_area:
                            polygons.append(p)

    return polygons


def _create_voronoi_with_rivers(
    boundary_polygon: Polygon,
    river_polygons: List[Polygon],
    base_max_area: float,
    river_max_area: float,
    additional_refinement_polygons: List[Polygon],
    additional_refinement_areas: List[float],
    crs: Optional[str],
) -> Tuple[VoronoiGrid, VertexGrid]:
    """
    Create Voronoi grid with river polygons as internal boundaries.

    The river banks become edges in the triangular mesh, which means
    Voronoi cells will align with the river boundaries.

    Parameters
    ----------
    boundary_polygon : Polygon
        Outer boundary of the model domain.
    river_polygons : list of Polygon
        River polygons to use as internal boundaries.
    base_max_area : float
        Maximum cell area for general domain.
    river_max_area : float
        Maximum cell area within rivers.
    additional_refinement_polygons : list of Polygon
        Additional refinement areas (not rivers).
    additional_refinement_areas : list of float
        Maximum areas for additional refinement polygons.
    crs : str, optional
        Coordinate reference system.

    Returns
    -------
    vor : VoronoiGrid
        FloPy VoronoiGrid object.
    modelgrid : VertexGrid
        FloPy VertexGrid object.
    """
    # Get boundary coordinates
    boundary_coords = np.array(boundary_polygon.exterior.coords[:-1])

    # Combine all internal polygons (rivers + refinement areas)
    all_internal_polygons = river_polygons + additional_refinement_polygons
    all_internal_areas = (
        [river_max_area] * len(river_polygons) +
        additional_refinement_areas
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tri = Triangle(angle=30, model_ws=tmpdir)

        # 1. Add outer boundary (MUST be first polygon)
        tri.add_polygon(boundary_coords)

        # 2. Add all internal polygons (rivers and refinement areas)
        for internal_poly in all_internal_polygons:
            if internal_poly.is_valid and internal_poly.area > 0:
                internal_coords = np.array(internal_poly.exterior.coords[:-1])
                tri.add_polygon(internal_coords)

        # 3. Add regions with different maximum areas
        # Region for base aquifer (outside all internal polygons)
        base_point = _find_point_outside_polygons(
            boundary_polygon, all_internal_polygons
        )
        tri.add_region(base_point, attribute=0, maximum_area=base_max_area)

        # Regions for each internal polygon
        for i, (internal_poly, max_area) in enumerate(
            zip(all_internal_polygons, all_internal_areas)
        ):
            # Find a point inside this polygon
            centroid = internal_poly.centroid
            if internal_poly.contains(centroid):
                region_point = (centroid.x, centroid.y)
            else:
                # Use representative point if centroid is outside
                rep_point = internal_poly.representative_point()
                region_point = (rep_point.x, rep_point.y)

            tri.add_region(region_point, attribute=i + 1, maximum_area=max_area)

        # Build triangular mesh
        tri.build(verbose=False)

        # Create Voronoi grid from Triangle
        vor = VoronoiGrid(tri)

    # Create VertexGrid from VoronoiGrid
    gridprops = vor.get_gridprops_vertexgrid()

    ncpl = gridprops['ncpl']
    top = np.ones(ncpl)
    botm = np.zeros((1, ncpl))

    modelgrid = VertexGrid(
        **gridprops,
        top=top,
        botm=botm,
        nlay=1,
        crs=crs,
    )

    return vor, modelgrid


def _identify_river_cells(
    modelgrid: VertexGrid,
    river_polygons: List[Polygon],
    method: str = 'intersects',
    min_intersection_fraction: float = 0.0,
) -> np.ndarray:
    """
    Identify which grid cells intersect with river polygons.

    Parameters
    ----------
    modelgrid : VertexGrid
        FloPy VertexGrid object.
    river_polygons : list of Polygon
        River polygons.
    method : str, default 'intersects'
        Method for identifying river cells:
        - 'intersects': cell polygon intersects river (most inclusive)
        - 'contains': cell center is inside river (strictest)
    min_intersection_fraction : float, default 0.0
        Minimum fraction of cell area that must overlap with river polygon
        for the cell to be included. Only applies when method='intersects'.
        Values between 0.0 (any overlap) and 1.0 (complete overlap).
        A value of 0.3 means at least 30% of the cell must be covered by river.

    Returns
    -------
    numpy.ndarray
        1D array of cell indices that are in/near rivers.

    Notes
    -----
    Using min_intersection_fraction > 0 helps reduce the number of river cells
    by excluding cells that only marginally touch river boundaries. This is
    useful when the default 'intersects' method includes too many cells (e.g.,
    cells that barely clip the edge of a river polygon).
    """
    river_cells = []
    river_union = unary_union(river_polygons)

    # Get vertices for building cell polygons
    vertices = modelgrid._vertices
    vert_dict = {v[0]: (v[1], v[2]) for v in vertices}

    for cell in modelgrid.cell2d:
        cell_id = cell[0]
        xc, yc = cell[1], cell[2]
        nvert = cell[3]
        vert_ids = cell[4:4+nvert]

        if method == 'contains':
            # Check if cell center is inside river
            if river_union.contains(Point(xc, yc)):
                river_cells.append(cell_id)
        else:
            # Build cell polygon and check intersection
            try:
                coords = [vert_dict[vid] for vid in vert_ids]
                coords.append(coords[0])  # Close polygon
                cell_poly = Polygon(coords)

                if not cell_poly.is_valid:
                    continue

                if not river_union.intersects(cell_poly):
                    continue

                # Apply minimum intersection fraction threshold
                if min_intersection_fraction > 0:
                    intersection = cell_poly.intersection(river_union)
                    intersection_fraction = intersection.area / cell_poly.area
                    if intersection_fraction >= min_intersection_fraction:
                        river_cells.append(cell_id)
                else:
                    # Any intersection counts
                    river_cells.append(cell_id)

            except (KeyError, ValueError):
                # Skip cells with invalid geometry
                continue

    return np.array(river_cells, dtype=int)
