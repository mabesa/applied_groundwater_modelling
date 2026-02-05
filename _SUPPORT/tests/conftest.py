"""
Pytest fixtures for Applied Groundwater Modelling tests.

This module provides shared fixtures for testing grid utilities,
boundary condition utilities, and other course support modules.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point, Polygon, LineString, box


# =============================================================================
# Basic Geometry Fixtures
# =============================================================================

@pytest.fixture
def simple_square_boundary() -> gpd.GeoDataFrame:
    """
    Create a simple 1000x1000m square boundary polygon.

    Origin at (0, 0), extends to (1000, 1000).
    Uses a local CRS (no projection) for simplicity.
    """
    polygon = Polygon([
        (0, 0),
        (1000, 0),
        (1000, 1000),
        (0, 1000),
        (0, 0),
    ])
    return gpd.GeoDataFrame(
        {'name': ['test_boundary']},
        geometry=[polygon],
        crs=None,
    )


@pytest.fixture
def simple_square_boundary_with_crs() -> gpd.GeoDataFrame:
    """
    Create a simple 1000x1000m square boundary with Swiss CRS (EPSG:2056).

    Located in the Limmat Valley area for realistic coordinates.
    """
    # Approximate Limmat Valley coordinates
    xmin, ymin = 2683000, 1248000
    polygon = Polygon([
        (xmin, ymin),
        (xmin + 1000, ymin),
        (xmin + 1000, ymin + 1000),
        (xmin, ymin + 1000),
        (xmin, ymin),
    ])
    return gpd.GeoDataFrame(
        {'name': ['test_boundary']},
        geometry=[polygon],
        crs='EPSG:2056',
    )


@pytest.fixture
def rectangular_boundary() -> gpd.GeoDataFrame:
    """
    Create a rectangular 2000x1000m boundary polygon.

    Useful for testing non-square domains.
    """
    polygon = Polygon([
        (0, 0),
        (2000, 0),
        (2000, 1000),
        (0, 1000),
        (0, 0),
    ])
    return gpd.GeoDataFrame(
        {'name': ['test_boundary']},
        geometry=[polygon],
        crs=None,
    )


@pytest.fixture
def irregular_boundary() -> gpd.GeoDataFrame:
    """
    Create an L-shaped irregular boundary polygon.

    Useful for testing non-convex domains.
    """
    polygon = Polygon([
        (0, 0),
        (1000, 0),
        (1000, 500),
        (500, 500),
        (500, 1000),
        (0, 1000),
        (0, 0),
    ])
    return gpd.GeoDataFrame(
        {'name': ['test_boundary']},
        geometry=[polygon],
        crs=None,
    )


@pytest.fixture
def small_refinement_area() -> gpd.GeoDataFrame:
    """
    Create a small 200x200m polygon for grid refinement testing.

    Centered at (500, 500) within the standard test boundary.
    """
    polygon = Polygon([
        (400, 400),
        (600, 400),
        (600, 600),
        (400, 600),
        (400, 400),
    ])
    return gpd.GeoDataFrame(
        {'name': ['refinement_zone']},
        geometry=[polygon],
        crs=None,
    )


# =============================================================================
# Zone Fixtures
# =============================================================================

@pytest.fixture
def two_zone_polygons() -> gpd.GeoDataFrame:
    """
    Create two adjacent zone polygons covering a 1000x1000m domain.

    Zone 1: Left half (x < 500)
    Zone 2: Right half (x >= 500)
    """
    zone1 = Polygon([
        (0, 0),
        (500, 0),
        (500, 1000),
        (0, 1000),
        (0, 0),
    ])
    zone2 = Polygon([
        (500, 0),
        (1000, 0),
        (1000, 1000),
        (500, 1000),
        (500, 0),
    ])
    return gpd.GeoDataFrame(
        {'zone': [1, 2], 'geology': ['alluvium', 'gravel']},
        geometry=[zone1, zone2],
        crs=None,
    )


@pytest.fixture
def three_zone_polygons() -> gpd.GeoDataFrame:
    """
    Create three zone polygons for property assignment testing.

    Zone A: Bottom third
    Zone B: Middle third
    Zone C: Top third
    """
    zone_a = Polygon([
        (0, 0), (1000, 0), (1000, 333), (0, 333), (0, 0)
    ])
    zone_b = Polygon([
        (0, 333), (1000, 333), (1000, 667), (0, 667), (0, 333)
    ])
    zone_c = Polygon([
        (0, 667), (1000, 667), (1000, 1000), (0, 1000), (0, 667)
    ])
    return gpd.GeoDataFrame(
        {'zone': ['A', 'B', 'C']},
        geometry=[zone_a, zone_b, zone_c],
        crs=None,
    )


# =============================================================================
# Point Fixtures
# =============================================================================

@pytest.fixture
def sample_well_points() -> gpd.GeoDataFrame:
    """
    Create sample well points with pumping rates.

    5 wells distributed across a 1000x1000m domain.
    """
    points = [
        Point(200, 200),
        Point(800, 200),
        Point(500, 500),
        Point(200, 800),
        Point(800, 800),
    ]
    rates = [-100.0, -150.0, -200.0, -50.0, -75.0]  # Negative = extraction
    names = ['Well_1', 'Well_2', 'Well_3', 'Well_4', 'Well_5']

    return gpd.GeoDataFrame(
        {'name': names, 'rate': rates},
        geometry=points,
        crs=None,
    )


@pytest.fixture
def sample_observation_points() -> gpd.GeoDataFrame:
    """
    Create sample observation well points.

    3 observation wells for head monitoring.
    """
    points = [
        Point(250, 500),
        Point(500, 500),
        Point(750, 500),
    ]
    names = ['Obs_1', 'Obs_2', 'Obs_3']
    observed_heads = [100.5, 99.8, 98.2]

    return gpd.GeoDataFrame(
        {'name': names, 'observed_head': observed_heads},
        geometry=points,
        crs=None,
    )


@pytest.fixture
def point_outside_boundary() -> gpd.GeoDataFrame:
    """
    Create a point outside the standard test boundary.

    For testing fallback_to_nearest behavior.
    """
    point = Point(1500, 500)  # Outside 1000x1000 boundary
    return gpd.GeoDataFrame(
        {'name': ['outside_well'], 'rate': [-50.0]},
        geometry=[point],
        crs=None,
    )


# =============================================================================
# Line Fixtures (for river/stream testing)
# =============================================================================

@pytest.fixture
def sample_river_line() -> gpd.GeoDataFrame:
    """
    Create a sample river line crossing the domain.

    River flows from west to east across the middle of the domain.
    """
    line = LineString([
        (0, 500),
        (250, 480),
        (500, 500),
        (750, 520),
        (1000, 500),
    ])
    return gpd.GeoDataFrame(
        {
            'name': ['Limmat'],
            'stage': [100.0],
            'conductance': [500.0],
            'rbot': [95.0],
        },
        geometry=[line],
        crs=None,
    )


@pytest.fixture
def branching_river_lines() -> gpd.GeoDataFrame:
    """
    Create river lines with a branch/tributary.

    Main river with one tributary joining from the north.
    """
    main_river = LineString([
        (0, 500), (500, 500), (1000, 500)
    ])
    tributary = LineString([
        (500, 1000), (500, 500)
    ])
    return gpd.GeoDataFrame(
        {
            'name': ['Main', 'Tributary'],
            'stage': [100.0, 101.0],
            'conductance': [500.0, 200.0],
            'rbot': [95.0, 96.0],
        },
        geometry=[main_river, tributary],
        crs=None,
    )


# =============================================================================
# Temporary Directory Fixture
# =============================================================================

@pytest.fixture
def temp_output_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory for test outputs.

    Automatically cleaned up after test completion.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# Grid Fixtures (require FloPy)
# =============================================================================

@pytest.fixture
def simple_voronoi_grid(simple_square_boundary):
    """
    Create a simple Voronoi grid for testing.

    Uses the simple_square_boundary with 100m cell size.
    Returns dict with 'voronoi_grid' (FloPy VoronoiGrid) and 'modelgrid' (VertexGrid).
    """
    # Import here to avoid import errors if FloPy not available
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
    from disv_grid_utils import create_voronoi_grid

    vor, modelgrid = create_voronoi_grid(
        simple_square_boundary,
        cell_size=100,
    )
    return {'voronoi_grid': vor, 'modelgrid': modelgrid, 'boundary': simple_square_boundary}


@pytest.fixture
def simple_disv_data(simple_square_boundary):
    """
    Create DISV grid data dictionary for testing.

    Uses create_disv_from_boundary with 100m cells.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
    from disv_grid_utils import create_disv_from_boundary

    disv_data = create_disv_from_boundary(
        simple_square_boundary,
        cell_size=100,
    )
    return disv_data


@pytest.fixture
def refined_disv_data(simple_square_boundary, small_refinement_area):
    """
    Create a refined DISV grid for testing local refinement.

    Base grid: 100m cells
    Refinement area: 25m cells
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
    from disv_grid_utils import create_disv_from_boundary

    disv_data = create_disv_from_boundary(
        simple_square_boundary,
        cell_size=100,
        refinement_areas=[(small_refinement_area, 25)],
    )
    return disv_data


# =============================================================================
# Structured Grid Fixture (for comparison testing)
# =============================================================================

@pytest.fixture
def simple_structured_grid():
    """
    Create a simple structured grid for comparison testing.

    10x10 grid with 100m cells covering 1000x1000m domain.
    """
    import flopy

    nrow, ncol = 10, 10
    delr = delc = 100.0

    modelgrid = flopy.discretization.StructuredGrid(
        delc=np.ones(nrow) * delc,
        delr=np.ones(ncol) * delr,
        top=np.ones((nrow, ncol)) * 100.0,
        botm=np.zeros((1, nrow, ncol)),
        nlay=1,
        xoff=0.0,
        yoff=0.0,
    )
    return modelgrid


# =============================================================================
# Helper Functions for Tests
# =============================================================================

def assert_valid_voronoi_grid(vor, modelgrid, min_cells=10):
    """
    Assert that a Voronoi grid is valid.

    Checks:
    - Grid has minimum expected cells
    - All cells have valid vertices
    - VoronoiGrid object has expected methods

    Parameters
    ----------
    vor : flopy.utils.voronoi.VoronoiGrid
        FloPy VoronoiGrid object.
    modelgrid : VertexGrid
        FloPy VertexGrid object.
    min_cells : int
        Minimum expected number of cells.
    """
    assert modelgrid.ncpl >= min_cells, (
        f"Grid has {modelgrid.ncpl} cells, expected at least {min_cells}"
    )

    # Check cell2d structure
    assert len(modelgrid.cell2d) == modelgrid.ncpl

    for cell in modelgrid.cell2d:
        cell_id = cell[0]
        xc, yc = cell[1], cell[2]
        nvert = cell[3]

        assert nvert >= 3, f"Cell {cell_id} has only {nvert} vertices"
        assert len(cell) == 4 + nvert, f"Cell {cell_id} has incorrect vertex count"

    # Check VoronoiGrid object (FloPy VoronoiGrid has get_disv_gridprops method)
    if vor is not None:
        assert hasattr(vor, 'get_disv_gridprops'), "VoronoiGrid missing get_disv_gridprops method"
        assert hasattr(vor, 'get_gridprops_vertexgrid'), "VoronoiGrid missing get_gridprops_vertexgrid method"


def assert_array_values_in_range(array, min_val, max_val, name="array"):
    """
    Assert all non-NaN array values are within expected range.
    """
    valid_values = array[~np.isnan(array)]
    assert np.all(valid_values >= min_val), (
        f"{name} has values below {min_val}: min={valid_values.min()}"
    )
    assert np.all(valid_values <= max_val), (
        f"{name} has values above {max_val}: max={valid_values.max()}"
    )
