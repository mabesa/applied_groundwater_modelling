"""
Unit tests for disv_grid_utils module.

Tests cover:
- create_voronoi_grid: Basic Voronoi grid creation using FloPy's VoronoiGrid
- create_disv_from_boundary: DISV grid with refinement options
- refine_grid_locally: Local grid refinement
- export_grid_to_geopackage: GeoPackage export
- assign_properties_from_zones: Zone-based property assignment
- assign_points_to_grid: Point-to-cell assignment

Run with: pytest _SUPPORT/tests/test_disv_grid_utils.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point, Polygon

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from disv_grid_utils import (
    create_voronoi_grid,
    create_disv_from_boundary,
    create_grid_with_rivers,
    refine_grid_locally,
    export_grid_to_geopackage,
    assign_properties_from_zones,
    assign_points_to_grid,
)


# =============================================================================
# Test Helper Functions
# =============================================================================

def assert_valid_voronoi_grid(vor, modelgrid, min_cells=10):
    """
    Assert that a Voronoi grid is valid.

    Checks:
    - Grid has minimum expected cells
    - All cells have valid vertices
    - VoronoiGrid object has expected attributes

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


# =============================================================================
# Tests for create_voronoi_grid
# =============================================================================

class TestCreateVoronoiGrid:
    """Tests for the create_voronoi_grid function."""

    def test_basic_grid_creation(self, simple_square_boundary):
        """Test basic Voronoi grid creation with default parameters."""
        vor, modelgrid = create_voronoi_grid(
            simple_square_boundary,
            cell_size=100,
        )

        # Check that grid was created
        assert vor is not None
        assert modelgrid is not None
        assert modelgrid.ncpl > 0

        # Validate grid structure
        assert_valid_voronoi_grid(vor, modelgrid, min_cells=50)

    def test_cell_count_scales_with_size(self, simple_square_boundary):
        """Test that smaller cell sizes produce more cells."""
        _, grid_100m = create_voronoi_grid(simple_square_boundary, cell_size=100)
        _, grid_50m = create_voronoi_grid(simple_square_boundary, cell_size=50)

        # 50m cells should produce ~4x more cells than 100m cells
        ratio = grid_50m.ncpl / grid_100m.ncpl
        assert ratio > 2.0, f"Expected ratio > 2, got {ratio:.2f}"
        assert ratio < 6.0, f"Expected ratio < 6, got {ratio:.2f}"

    def test_with_rotation(self, simple_square_boundary):
        """Test grid creation with rotation angle."""
        vor, modelgrid = create_voronoi_grid(
            simple_square_boundary,
            cell_size=100,
            rotation_angle=45,
        )

        assert modelgrid.ncpl > 0
        assert_valid_voronoi_grid(vor, modelgrid)

    def test_with_crs(self, simple_square_boundary_with_crs):
        """Test grid creation with CRS preservation."""
        vor, modelgrid = create_voronoi_grid(
            simple_square_boundary_with_crs,
            cell_size=100,
        )

        assert modelgrid.crs == 'EPSG:2056'

    def test_rectangular_boundary(self, rectangular_boundary):
        """Test grid creation with non-square boundary."""
        vor, modelgrid = create_voronoi_grid(
            rectangular_boundary,
            cell_size=100,
        )

        # Rectangular domain should have ~2x cells of square
        assert modelgrid.ncpl > 100
        assert_valid_voronoi_grid(vor, modelgrid)

    def test_irregular_boundary(self, irregular_boundary):
        """Test grid creation with L-shaped boundary."""
        vor, modelgrid = create_voronoi_grid(
            irregular_boundary,
            cell_size=50,
        )

        assert modelgrid.ncpl > 0
        assert_valid_voronoi_grid(vor, modelgrid)

    def test_empty_boundary_raises(self):
        """Test that empty boundary raises ValueError."""
        empty_gdf = gpd.GeoDataFrame(geometry=[], crs=None)

        with pytest.raises(ValueError, match="empty"):
            create_voronoi_grid(empty_gdf, cell_size=100)

    def test_invalid_cell_size_raises(self, simple_square_boundary):
        """Test that non-positive cell size raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            create_voronoi_grid(simple_square_boundary, cell_size=0)

        with pytest.raises(ValueError, match="positive"):
            create_voronoi_grid(simple_square_boundary, cell_size=-50)


# =============================================================================
# Tests for create_disv_from_boundary
# =============================================================================

class TestCreateDisvFromBoundary:
    """Tests for the create_disv_from_boundary function."""

    def test_basic_creation(self, simple_square_boundary):
        """Test basic DISV grid creation."""
        disv_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
        )

        # Check all expected keys are present
        expected_keys = [
            'voronoi_grid', 'modelgrid', 'vertices', 'cell2d',
            'ncpl', 'nvert', 'disv_gridprops', 'crs'
        ]
        for key in expected_keys:
            assert key in disv_data, f"Missing key: {key}"

        # Validate consistency
        assert disv_data['ncpl'] == len(disv_data['cell2d'])
        assert disv_data['nvert'] == len(disv_data['vertices'])
        assert disv_data['ncpl'] == disv_data['modelgrid'].ncpl

        # Check disv_gridprops can be used with ModflowGwfdisv
        gridprops = disv_data['disv_gridprops']
        assert 'ncpl' in gridprops
        assert 'nvert' in gridprops
        assert 'vertices' in gridprops
        assert 'cell2d' in gridprops

    def test_with_single_refinement(self, simple_square_boundary, small_refinement_area):
        """Test DISV grid with one refinement area."""
        base_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
        )

        refined_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
            refinement_areas=[(small_refinement_area, 25)],
        )

        # Refined grid should have more cells
        assert refined_data['ncpl'] > base_data['ncpl']

    def test_with_multiple_refinements(self, simple_square_boundary):
        """Test DISV grid with multiple refinement areas."""
        # Create two refinement zones
        zone1 = gpd.GeoDataFrame(
            geometry=[Polygon([(100, 100), (300, 100), (300, 300), (100, 300)])],
            crs=None,
        )
        zone2 = gpd.GeoDataFrame(
            geometry=[Polygon([(700, 700), (900, 700), (900, 900), (700, 900)])],
            crs=None,
        )

        disv_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
            refinement_areas=[(zone1, 25), (zone2, 25)],
        )

        # Should have cells from both refinement areas
        assert disv_data['ncpl'] > 200  # Rough minimum with refinement

    def test_boundary_vertices_included(self, simple_square_boundary):
        """Test that boundary vertices are included when requested."""
        with_boundary = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
            include_boundary_vertices=True,
        )

        without_boundary = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
            include_boundary_vertices=False,
        )

        # Grid with boundary vertices might have slightly different cell count
        # Main check is that both work
        assert with_boundary['ncpl'] > 0
        assert without_boundary['ncpl'] > 0

    def test_refinement_outside_boundary_warning(self, simple_square_boundary):
        """Test that refinement outside boundary issues warning."""
        outside_zone = gpd.GeoDataFrame(
            geometry=[Polygon([(2000, 2000), (3000, 2000), (3000, 3000), (2000, 3000)])],
            crs=None,
        )

        with pytest.warns(UserWarning, match="does not intersect"):
            create_disv_from_boundary(
                simple_square_boundary,
                cell_size=100,
                refinement_areas=[(outside_zone, 25)],
            )

    def test_voronoi_grid_has_disv_methods(self, simple_square_boundary):
        """Test that VoronoiGrid object has required methods."""
        disv_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
        )

        vor = disv_data['voronoi_grid']
        assert hasattr(vor, 'get_disv_gridprops')
        assert hasattr(vor, 'get_gridprops_vertexgrid')

        # Test that methods work
        gridprops = vor.get_disv_gridprops()
        assert 'ncpl' in gridprops


# =============================================================================
# Tests for create_grid_with_rivers
# =============================================================================

class TestCreateGridWithRivers:
    """Tests for the create_grid_with_rivers function."""

    def test_basic_river_grid_creation(self, simple_square_boundary, sample_river_polygon):
        """Test basic grid creation with river constraints."""
        grid_data = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
        )

        # Check standard grid outputs
        assert 'voronoi_grid' in grid_data
        assert 'modelgrid' in grid_data
        assert 'ncpl' in grid_data
        assert 'disv_gridprops' in grid_data

        # Check river-specific outputs
        assert 'river_cells' in grid_data
        assert 'river_polygons' in grid_data

        # Grid should have cells
        assert grid_data['ncpl'] > 0
        assert len(grid_data['modelgrid'].cell2d) == grid_data['ncpl']

    def test_river_cells_identified(self, simple_square_boundary, sample_river_polygon):
        """Test that cells intersecting rivers are correctly identified."""
        grid_data = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=30,
        )

        river_cells = grid_data['river_cells']

        # Should have some river cells
        assert len(river_cells) > 0

        # River cells should be valid indices
        assert all(0 <= cell_id < grid_data['ncpl'] for cell_id in river_cells)

        # Check river cells actually intersect river polygons
        from shapely.geometry import Polygon as ShapelyPolygon
        from shapely.ops import unary_union

        river_union = unary_union(grid_data['river_polygons'])
        modelgrid = grid_data['modelgrid']
        vertices = modelgrid._vertices
        vert_dict = {v[0]: (v[1], v[2]) for v in vertices}

        for cell_id in river_cells[:5]:  # Check first 5
            cell = modelgrid.cell2d[cell_id]
            nvert = cell[3]
            vert_ids = cell[4:4+nvert]
            coords = [vert_dict[vid] for vid in vert_ids]
            coords.append(coords[0])
            cell_poly = ShapelyPolygon(coords)
            assert river_union.intersects(cell_poly), (
                f"River cell {cell_id} does not intersect river polygon"
            )

    def test_default_river_cell_size(self, simple_square_boundary, sample_river_polygon):
        """Test that default river_cell_size is cell_size / 2."""
        grid_data = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            # river_cell_size not specified, should default to 50
        )

        # Grid should be created successfully
        assert grid_data['ncpl'] > 0
        assert len(grid_data['river_cells']) > 0

    def test_with_two_rivers(self, simple_square_boundary, two_river_polygons):
        """Test grid creation with multiple river polygons."""
        grid_data = create_grid_with_rivers(
            simple_square_boundary,
            two_river_polygons,
            cell_size=100,
            river_cell_size=40,
        )

        # Should have cells in rivers
        assert len(grid_data['river_cells']) > 0
        # River polygons may be merged if they touch
        assert len(grid_data['river_polygons']) >= 1

    def test_with_additional_refinement(
        self, simple_square_boundary, sample_river_polygon, small_refinement_area
    ):
        """Test river grid with additional refinement areas."""
        grid_data = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
            refinement_areas=[(small_refinement_area, 25)],
        )

        # Should have more cells due to refinement
        base_grid = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
        )

        assert grid_data['ncpl'] > base_grid['ncpl']

    def test_empty_river_raises(self, simple_square_boundary):
        """Test that empty river GeoDataFrame raises error."""
        import geopandas as gpd

        empty_rivers = gpd.GeoDataFrame(geometry=[], crs=None)

        with pytest.raises(ValueError, match="river_gdf is empty"):
            create_grid_with_rivers(
                simple_square_boundary,
                empty_rivers,
                cell_size=100,
            )

    def test_river_outside_boundary_warning(self, simple_square_boundary):
        """Test that river outside boundary creates grid without rivers."""
        from shapely.geometry import Polygon

        # Create river outside boundary
        river_outside = Polygon([
            (2000, 480), (3000, 480), (3000, 520), (2000, 520), (2000, 480)
        ])
        river_gdf = gpd.GeoDataFrame(
            {'name': ['outside']},
            geometry=[river_outside],
            crs=None,
        )

        # Should warn and fall back to grid without rivers
        with pytest.warns(UserWarning, match="do not intersect"):
            grid_data = create_grid_with_rivers(
                simple_square_boundary,
                river_gdf,
                cell_size=100,
            )

        # Should still create a valid grid
        assert grid_data['ncpl'] > 0

    def test_invalid_cell_size_raises(self, simple_square_boundary, sample_river_polygon):
        """Test that invalid cell sizes raise errors."""
        with pytest.raises(ValueError, match="cell_size must be positive"):
            create_grid_with_rivers(
                simple_square_boundary,
                sample_river_polygon,
                cell_size=-50,
            )

        with pytest.raises(ValueError, match="river_cell_size must be positive"):
            create_grid_with_rivers(
                simple_square_boundary,
                sample_river_polygon,
                cell_size=100,
                river_cell_size=-25,
            )

    def test_disv_gridprops_valid(self, simple_square_boundary, sample_river_polygon):
        """Test that DISV grid properties are valid for MODFLOW."""
        grid_data = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
        )

        gridprops = grid_data['disv_gridprops']

        # Check required DISV properties
        assert 'ncpl' in gridprops
        assert 'nvert' in gridprops
        assert 'vertices' in gridprops
        assert 'cell2d' in gridprops

        # Check consistency
        assert len(gridprops['vertices']) == gridprops['nvert']
        assert len(gridprops['cell2d']) == gridprops['ncpl']

    def test_min_intersection_fraction_reduces_river_cells(
        self, simple_square_boundary, sample_river_polygon
    ):
        """Test that min_intersection_fraction reduces number of river cells."""
        # Grid without threshold
        grid_no_threshold = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
            min_river_intersection_fraction=0.0,
        )

        # Grid with threshold
        grid_with_threshold = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
            min_river_intersection_fraction=0.3,
        )

        # Threshold should reduce number of river cells
        n_cells_no_threshold = len(grid_no_threshold['river_cells'])
        n_cells_with_threshold = len(grid_with_threshold['river_cells'])

        assert n_cells_with_threshold < n_cells_no_threshold, (
            f"Expected fewer river cells with threshold. "
            f"Without: {n_cells_no_threshold}, With: {n_cells_with_threshold}"
        )

    def test_min_intersection_fraction_high_threshold(
        self, simple_square_boundary, sample_river_polygon
    ):
        """Test that high threshold results in fewer cells than low threshold."""
        grid_low = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
            min_river_intersection_fraction=0.1,
        )

        grid_high = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
            min_river_intersection_fraction=0.5,
        )

        # Higher threshold should have fewer or equal cells
        assert len(grid_high['river_cells']) <= len(grid_low['river_cells'])

    def test_min_intersection_fraction_zero_same_as_default(
        self, simple_square_boundary, sample_river_polygon
    ):
        """Test that min_intersection_fraction=0 gives same result as default."""
        grid_default = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
        )

        grid_explicit_zero = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
            min_river_intersection_fraction=0.0,
        )

        # Should have same number of river cells
        assert len(grid_default['river_cells']) == len(grid_explicit_zero['river_cells'])

    def test_min_intersection_fraction_preserves_fully_contained_cells(
        self, simple_square_boundary, sample_river_polygon
    ):
        """Test that cells fully contained in river are always included."""
        # With a very high threshold (0.9), only cells almost entirely in river
        grid_strict = create_grid_with_rivers(
            simple_square_boundary,
            sample_river_polygon,
            cell_size=100,
            river_cell_size=50,
            min_river_intersection_fraction=0.9,
        )

        # Should still have some cells (those fully inside river)
        # The river is 40m wide, cells are ~50m, so some should be mostly inside
        assert len(grid_strict['river_cells']) > 0


# =============================================================================
# Tests for refine_grid_locally
# =============================================================================

class TestRefineGridLocally:
    """Tests for the refine_grid_locally function."""

    def test_basic_refinement(self, simple_disv_data, small_refinement_area, simple_square_boundary):
        """Test basic local grid refinement."""
        refined_data = refine_grid_locally(
            simple_disv_data,
            small_refinement_area,
            refined_cell_size=25,
            boundary_gdf=simple_square_boundary,
        )

        # Check refinement occurred
        assert refined_data['refined_cell_count'] > refined_data['base_cell_count']
        assert refined_data['refinement_area_m2'] > 0

    def test_refinement_increases_cells(self, simple_disv_data, small_refinement_area, simple_square_boundary):
        """Test that refinement increases cell count proportionally."""
        base_count = simple_disv_data['ncpl']

        refined_data = refine_grid_locally(
            simple_disv_data,
            small_refinement_area,
            refined_cell_size=25,
            boundary_gdf=simple_square_boundary,
        )

        # Refinement should increase total cells
        assert refined_data['ncpl'] > base_count

        # Base count should be preserved in output
        assert refined_data['base_cell_count'] == base_count

    def test_refinement_has_voronoi_grid(self, simple_disv_data, small_refinement_area, simple_square_boundary):
        """Test that refinement preserves VoronoiGrid object."""
        refined_data = refine_grid_locally(
            simple_disv_data,
            small_refinement_area,
            refined_cell_size=25,
            boundary_gdf=simple_square_boundary,
        )

        # Refined grid should have voronoi_grid
        assert 'voronoi_grid' in refined_data
        assert refined_data['voronoi_grid'] is not None

    def test_empty_refinement_area_raises(self, simple_disv_data, simple_square_boundary):
        """Test that empty refinement GeoDataFrame raises ValueError."""
        empty_gdf = gpd.GeoDataFrame(geometry=[], crs=None)

        with pytest.raises(ValueError, match="empty"):
            refine_grid_locally(
                simple_disv_data,
                empty_gdf,
                refined_cell_size=25,
                boundary_gdf=simple_square_boundary,
            )

    def test_refinement_outside_boundary_raises(self, simple_disv_data, simple_square_boundary):
        """Test that refinement completely outside boundary raises ValueError."""
        outside_zone = gpd.GeoDataFrame(
            geometry=[Polygon([(2000, 2000), (3000, 2000), (3000, 3000), (2000, 3000)])],
            crs=None,
        )

        with pytest.raises(ValueError, match="does not intersect"):
            refine_grid_locally(
                simple_disv_data,
                outside_zone,
                refined_cell_size=25,
                boundary_gdf=simple_square_boundary,
            )


# =============================================================================
# Tests for export_grid_to_geopackage
# =============================================================================

class TestExportGridToGeopackage:
    """Tests for the export_grid_to_geopackage function."""

    def test_basic_export(self, simple_disv_data, temp_output_dir):
        """Test basic GeoPackage export."""
        modelgrid = simple_disv_data['modelgrid']
        array = np.random.uniform(10, 50, size=modelgrid.ncpl)

        output_path = str(temp_output_dir / "test_export.gpkg")

        result_path = export_grid_to_geopackage(
            modelgrid,
            array,
            output_path,
            layer_name="test_layer",
            array_name="hydraulic_k",
        )

        # Check file was created
        assert Path(result_path).exists()

        # Read back and verify
        gdf = gpd.read_file(result_path, layer="test_layer")
        assert len(gdf) == modelgrid.ncpl
        assert 'hydraulic_k' in gdf.columns
        assert 'cell_id' in gdf.columns

    def test_export_with_crs(self, simple_disv_data, temp_output_dir):
        """Test GeoPackage export with CRS."""
        modelgrid = simple_disv_data['modelgrid']
        array = np.ones(modelgrid.ncpl)

        output_path = str(temp_output_dir / "test_crs.gpkg")

        export_grid_to_geopackage(
            modelgrid,
            array,
            output_path,
            layer_name="test",
            crs='EPSG:2056',
        )

        gdf = gpd.read_file(output_path)
        assert gdf.crs is not None
        assert gdf.crs.to_epsg() == 2056

    def test_export_adds_gpkg_extension(self, simple_disv_data, temp_output_dir):
        """Test that .gpkg extension is added if missing."""
        modelgrid = simple_disv_data['modelgrid']
        array = np.ones(modelgrid.ncpl)

        output_path = str(temp_output_dir / "test_no_ext")

        result_path = export_grid_to_geopackage(
            modelgrid,
            array,
            output_path,
            layer_name="test",
        )

        assert result_path.endswith('.gpkg')
        assert Path(result_path).exists()

    def test_export_2d_array(self, simple_disv_data, temp_output_dir):
        """Test export with 2D array (nlay, ncpl)."""
        modelgrid = simple_disv_data['modelgrid']
        array_2d = np.random.uniform(0, 100, size=(1, modelgrid.ncpl))

        output_path = str(temp_output_dir / "test_2d.gpkg")

        export_grid_to_geopackage(
            modelgrid,
            array_2d,
            output_path,
            layer_name="test",
        )

        gdf = gpd.read_file(output_path)
        assert len(gdf) == modelgrid.ncpl

    def test_export_structured_grid(self, simple_structured_grid, temp_output_dir):
        """Test export with structured grid."""
        modelgrid = simple_structured_grid
        nrow, ncol = 10, 10
        array = np.random.uniform(0, 100, size=(nrow, ncol))

        output_path = str(temp_output_dir / "test_structured.gpkg")

        export_grid_to_geopackage(
            modelgrid,
            array,
            output_path,
            layer_name="test",
        )

        gdf = gpd.read_file(output_path)
        assert len(gdf) == nrow * ncol

    def test_array_size_mismatch_raises(self, simple_disv_data, temp_output_dir):
        """Test that mismatched array size raises ValueError."""
        modelgrid = simple_disv_data['modelgrid']
        wrong_size_array = np.ones(modelgrid.ncpl + 10)

        output_path = str(temp_output_dir / "test_error.gpkg")

        with pytest.raises(ValueError, match="does not match"):
            export_grid_to_geopackage(
                modelgrid,
                wrong_size_array,
                output_path,
                layer_name="test",
            )


# =============================================================================
# Tests for assign_properties_from_zones
# =============================================================================

class TestAssignPropertiesFromZones:
    """Tests for the assign_properties_from_zones function."""

    def test_basic_assignment(self, simple_disv_data, two_zone_polygons):
        """Test basic property assignment from zones."""
        modelgrid = simple_disv_data['modelgrid']
        property_map = {1: 25.0, 2: 15.0}

        properties = assign_properties_from_zones(
            two_zone_polygons,
            modelgrid,
            property_map,
            zone_column='zone',
        )

        # Check output shape
        assert len(properties) == modelgrid.ncpl

        # Check values are from property map
        unique_values = np.unique(properties[~np.isnan(properties)])
        assert set(unique_values).issubset({25.0, 15.0})

    def test_assignment_with_default_value(self, simple_disv_data, two_zone_polygons):
        """Test assignment with default value for unassigned cells."""
        modelgrid = simple_disv_data['modelgrid']
        property_map = {1: 25.0}  # Only map zone 1

        properties = assign_properties_from_zones(
            two_zone_polygons,
            modelgrid,
            property_map,
            zone_column='zone',
            default_value=10.0,
        )

        # Unmapped cells should have default value
        assert 10.0 in properties

    def test_assignment_without_default_leaves_nan(self, simple_disv_data, two_zone_polygons):
        """Test that cells outside zones are NaN without default."""
        modelgrid = simple_disv_data['modelgrid']
        property_map = {1: 25.0}  # Only map zone 1

        properties = assign_properties_from_zones(
            two_zone_polygons,
            modelgrid,
            property_map,
            zone_column='zone',
            default_value=None,
        )

        # Some cells should be NaN (zone 2 cells)
        assert np.any(np.isnan(properties))

    def test_missing_zone_column_raises(self, simple_disv_data, two_zone_polygons):
        """Test that missing zone column raises ValueError."""
        modelgrid = simple_disv_data['modelgrid']
        property_map = {1: 25.0}

        with pytest.raises(ValueError, match="not found"):
            assign_properties_from_zones(
                two_zone_polygons,
                modelgrid,
                property_map,
                zone_column='nonexistent_column',
            )

    def test_empty_zones_raises(self, simple_disv_data):
        """Test that empty zones GeoDataFrame raises ValueError."""
        modelgrid = simple_disv_data['modelgrid']
        empty_gdf = gpd.GeoDataFrame(geometry=[], crs=None)
        empty_gdf['zone'] = []

        with pytest.raises(ValueError, match="empty"):
            assign_properties_from_zones(
                empty_gdf,
                modelgrid,
                {1: 25.0},
                zone_column='zone',
            )

    def test_unmapped_zone_warning(self, simple_disv_data, two_zone_polygons):
        """Test warning when zone not in property_map."""
        modelgrid = simple_disv_data['modelgrid']
        partial_map = {1: 25.0}  # Missing zone 2

        with pytest.warns(UserWarning, match="not found in property_map"):
            assign_properties_from_zones(
                two_zone_polygons,
                modelgrid,
                partial_map,
                zone_column='zone',
            )

    def test_works_with_structured_grid(self, simple_structured_grid, two_zone_polygons):
        """Test property assignment works with structured grid."""
        property_map = {1: 25.0, 2: 15.0}

        properties = assign_properties_from_zones(
            two_zone_polygons,
            simple_structured_grid,
            property_map,
            zone_column='zone',
        )

        assert len(properties) == simple_structured_grid.nrow * simple_structured_grid.ncol

    def test_three_zones(self, simple_disv_data, three_zone_polygons):
        """Test assignment with three zones."""
        modelgrid = simple_disv_data['modelgrid']
        property_map = {'A': 10.0, 'B': 20.0, 'C': 30.0}

        properties = assign_properties_from_zones(
            three_zone_polygons,
            modelgrid,
            property_map,
            zone_column='zone',
        )

        # All three values should be present
        unique_values = np.unique(properties[~np.isnan(properties)])
        assert len(unique_values) == 3


# =============================================================================
# Tests for assign_points_to_grid
# =============================================================================

class TestAssignPointsToGrid:
    """Tests for the assign_points_to_grid function."""

    def test_basic_assignment(self, simple_disv_data, sample_well_points):
        """Test basic point-to-cell assignment."""
        modelgrid = simple_disv_data['modelgrid']

        cell_ids = assign_points_to_grid(
            sample_well_points,
            modelgrid,
        )

        # Should return array of cell IDs
        assert len(cell_ids) == len(sample_well_points)
        assert all(0 <= cid < modelgrid.ncpl for cid in cell_ids)

    def test_assignment_with_values(self, simple_disv_data, sample_well_points):
        """Test assignment returning cell IDs with values."""
        modelgrid = simple_disv_data['modelgrid']

        results = assign_points_to_grid(
            sample_well_points,
            modelgrid,
            value_column='rate',
        )

        # Should return list of (cell_id, value) tuples
        assert len(results) == len(sample_well_points)
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

        # Check values match input
        rates = [r[1] for r in results]
        assert set(rates) == set(sample_well_points['rate'].tolist())

    def test_point_outside_with_fallback(self, simple_disv_data, point_outside_boundary):
        """Test that point outside grid falls back to nearest cell."""
        modelgrid = simple_disv_data['modelgrid']

        with pytest.warns(UserWarning, match="outside grid"):
            cell_ids = assign_points_to_grid(
                point_outside_boundary,
                modelgrid,
                fallback_to_nearest=True,
            )

        # Should still return a valid cell ID
        assert len(cell_ids) == 1
        assert 0 <= cell_ids[0] < modelgrid.ncpl

    def test_point_outside_without_fallback(self, simple_disv_data, point_outside_boundary):
        """Test that point outside grid is skipped without fallback."""
        modelgrid = simple_disv_data['modelgrid']

        with pytest.warns(UserWarning, match="outside grid"):
            cell_ids = assign_points_to_grid(
                point_outside_boundary,
                modelgrid,
                fallback_to_nearest=False,
            )

        # Should return empty array
        assert len(cell_ids) == 0

    def test_empty_points_returns_empty(self, simple_disv_data):
        """Test that empty points GeoDataFrame returns empty result."""
        modelgrid = simple_disv_data['modelgrid']
        empty_gdf = gpd.GeoDataFrame(geometry=[], crs=None)

        with pytest.warns(UserWarning, match="empty"):
            cell_ids = assign_points_to_grid(empty_gdf, modelgrid)

        assert len(cell_ids) == 0

    def test_missing_value_column_raises(self, simple_disv_data, sample_well_points):
        """Test that missing value column raises ValueError."""
        modelgrid = simple_disv_data['modelgrid']

        with pytest.raises(ValueError, match="not found"):
            assign_points_to_grid(
                sample_well_points,
                modelgrid,
                value_column='nonexistent_column',
            )

    def test_works_with_structured_grid(self, simple_structured_grid, sample_well_points):
        """Test point assignment works with structured grid."""
        cell_ids = assign_points_to_grid(
            sample_well_points,
            simple_structured_grid,
        )

        assert len(cell_ids) == len(sample_well_points)
        max_cell = simple_structured_grid.nrow * simple_structured_grid.ncol
        assert all(0 <= cid < max_cell for cid in cell_ids)

    def test_observation_points(self, simple_disv_data, sample_observation_points):
        """Test assignment of observation well points."""
        modelgrid = simple_disv_data['modelgrid']

        results = assign_points_to_grid(
            sample_observation_points,
            modelgrid,
            value_column='observed_head',
        )

        assert len(results) == 3
        # Check observed heads are preserved
        heads = [r[1] for r in results]
        assert 100.5 in heads
        assert 99.8 in heads
        assert 98.2 in heads


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_workflow_grid_to_export(self, simple_square_boundary, temp_output_dir):
        """Test complete workflow: create grid, assign properties, export."""
        # Create grid
        disv_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
        )
        modelgrid = disv_data['modelgrid']

        # Create simple zones
        zones = gpd.GeoDataFrame(
            {'zone': [1, 2]},
            geometry=[
                Polygon([(0, 0), (500, 0), (500, 1000), (0, 1000)]),
                Polygon([(500, 0), (1000, 0), (1000, 1000), (500, 1000)]),
            ],
            crs=None,
        )

        # Assign properties
        hk = assign_properties_from_zones(
            zones,
            modelgrid,
            {1: 25.0, 2: 15.0},
            zone_column='zone',
        )

        # Export to GeoPackage
        output_path = str(temp_output_dir / "workflow_test.gpkg")
        export_grid_to_geopackage(
            modelgrid,
            hk,
            output_path,
            layer_name="hydraulic_k",
            array_name="K_m_day",
        )

        # Verify export
        gdf = gpd.read_file(output_path)
        assert len(gdf) == modelgrid.ncpl
        assert set(gdf['K_m_day'].dropna().unique()).issubset({25.0, 15.0})

    def test_refinement_preserves_properties(
        self, simple_square_boundary, small_refinement_area, temp_output_dir
    ):
        """Test that property assignment works on refined grids."""
        # Create base grid
        base_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
        )

        # Refine grid
        refined_data = refine_grid_locally(
            base_data,
            small_refinement_area,
            refined_cell_size=25,
            boundary_gdf=simple_square_boundary,
        )

        # Create zones
        zones = gpd.GeoDataFrame(
            {'zone': ['left', 'right']},
            geometry=[
                Polygon([(0, 0), (500, 0), (500, 1000), (0, 1000)]),
                Polygon([(500, 0), (1000, 0), (1000, 1000), (500, 1000)]),
            ],
            crs=None,
        )

        # Assign properties to refined grid
        hk = assign_properties_from_zones(
            zones,
            refined_data['modelgrid'],
            {'left': 25.0, 'right': 15.0},
            zone_column='zone',
        )

        # Verify assignment worked on refined grid
        assert len(hk) == refined_data['ncpl']
        assert not np.all(np.isnan(hk))

    def test_wells_assigned_to_refined_grid(
        self, simple_square_boundary, small_refinement_area, sample_well_points
    ):
        """Test well assignment works on refined grids."""
        # Create refined grid (refinement in center where some wells are)
        refined_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
            refinement_areas=[(small_refinement_area, 25)],
        )

        # Assign wells
        results = assign_points_to_grid(
            sample_well_points,
            refined_data['modelgrid'],
            value_column='rate',
        )

        assert len(results) == len(sample_well_points)

        # All cell IDs should be valid
        for cell_id, rate in results:
            assert 0 <= cell_id < refined_data['ncpl']


# =============================================================================
# Performance Tests (optional, marked as slow)
# =============================================================================

@pytest.mark.slow
class TestPerformance:
    """Performance tests for larger grids."""

    def test_large_grid_creation(self, simple_square_boundary):
        """Test creation of grid with many cells (~5000)."""
        disv_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=15,  # ~4400 cells in 1000x1000m domain
        )

        assert disv_data['ncpl'] > 3000
        assert disv_data['ncpl'] < 6000

    def test_fine_refinement(self, simple_square_boundary, small_refinement_area):
        """Test fine refinement in small area."""
        refined_data = create_disv_from_boundary(
            simple_square_boundary,
            cell_size=100,
            refinement_areas=[(small_refinement_area, 10)],  # 10m cells
        )

        # Should have significantly more cells due to fine refinement
        base_data = create_disv_from_boundary(simple_square_boundary, cell_size=100)
        assert refined_data['ncpl'] > base_data['ncpl'] * 2
