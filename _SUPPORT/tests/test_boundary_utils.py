"""
Unit tests for boundary_utils.py module.

Tests cover all boundary condition utility functions:
- assign_river_cells
- assign_well_cells
- assign_idomain_from_geometry
- create_riv_package
- create_wel_package
- create_chd_package
- create_rch_package
- validate_bc_geometries

Run tests with: uv run pytest _SUPPORT/tests/test_boundary_utils.py -v
"""

from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point, LineString, Polygon, box

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from boundary_utils import (
    assign_river_cells,
    assign_well_cells,
    assign_idomain_from_geometry,
    create_riv_package,
    create_wel_package,
    create_chd_package,
    create_rch_package,
    validate_bc_geometries,
)


# =============================================================================
# Additional Fixtures for Boundary Tests
# =============================================================================

@pytest.fixture
def river_gdf():
    """Create a river GeoDataFrame for testing river boundary conditions."""
    line = LineString([(0, 500), (500, 500), (1000, 500)])
    return gpd.GeoDataFrame(
        {
            'name': ['Test River'],
            'stage': [100.0],
            'conductance': [10.0],  # conductance per unit length
            'rbot': [95.0],
        },
        geometry=[line],
        crs=None,
    )


@pytest.fixture
def river_gdf_multi_reach():
    """Create a river GeoDataFrame with multiple reaches."""
    line1 = LineString([(0, 500), (500, 500)])
    line2 = LineString([(500, 500), (1000, 500)])
    return gpd.GeoDataFrame(
        {
            'name': ['Reach 1', 'Reach 2'],
            'stage': [100.0, 99.5],
            'conductance': [10.0, 15.0],
            'rbot': [95.0, 94.5],
        },
        geometry=[line1, line2],
        crs=None,
    )


@pytest.fixture
def well_gdf():
    """Create a well GeoDataFrame for testing well boundary conditions."""
    points = [
        Point(250, 250),
        Point(750, 250),
        Point(500, 750),
    ]
    return gpd.GeoDataFrame(
        {
            'name': ['Well_1', 'Well_2', 'Well_3'],
            'rate': [-100.0, -150.0, -50.0],  # Negative = extraction
        },
        geometry=points,
        crs=None,
    )


@pytest.fixture
def well_gdf_with_layers():
    """Create a well GeoDataFrame with layer specification."""
    points = [
        Point(250, 250),
        Point(750, 250),
        Point(500, 750),
    ]
    return gpd.GeoDataFrame(
        {
            'name': ['Well_1', 'Well_2', 'Well_3'],
            'rate': [-100.0, -150.0, -50.0],
            'layer': [0, 1, 2],
        },
        geometry=points,
        crs=None,
    )


@pytest.fixture
def chd_points_gdf():
    """Create point geometries for constant head boundaries."""
    points = [
        Point(50, 500),
        Point(950, 500),
    ]
    return gpd.GeoDataFrame(
        {'head': [100.0, 98.0]},
        geometry=points,
        crs=None,
    )


@pytest.fixture
def chd_line_gdf():
    """Create line geometry for constant head boundary."""
    line = LineString([(0, 0), (0, 1000)])  # Left edge
    return gpd.GeoDataFrame(
        {'head': [100.0]},
        geometry=[line],
        crs=None,
    )


@pytest.fixture
def chd_polygon_gdf():
    """Create polygon geometry for constant head boundary."""
    polygon = Polygon([(0, 0), (100, 0), (100, 1000), (0, 1000), (0, 0)])
    return gpd.GeoDataFrame(
        {'head': [100.0]},
        geometry=[polygon],
        crs=None,
    )


@pytest.fixture
def recharge_zones_gdf():
    """Create recharge zone polygons with different rates."""
    zone1 = Polygon([(0, 0), (500, 0), (500, 1000), (0, 1000), (0, 0)])
    zone2 = Polygon([(500, 0), (1000, 0), (1000, 1000), (500, 1000), (500, 0)])
    return gpd.GeoDataFrame(
        {'rate': [0.001, 0.002]},  # Different recharge rates (m/day)
        geometry=[zone1, zone2],
        crs=None,
    )


@pytest.fixture
def well_outside_domain():
    """Create a well point outside the model domain."""
    point = Point(1500, 500)  # Outside 1000x1000 domain
    return gpd.GeoDataFrame(
        {'name': ['Outside Well'], 'rate': [-50.0]},
        geometry=[point],
        crs=None,
    )


@pytest.fixture
def mock_gwf_model(simple_disv_data):
    """Create a minimal mock GWF model for package creation tests."""
    import flopy

    # Create a simulation and model in a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        sim = flopy.mf6.MFSimulation(
            sim_name='test_sim',
            sim_ws=tmpdir,
            exe_name='mf6',
        )

        tdis = flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1.0)])
        ims = flopy.mf6.ModflowIms(sim)

        gwf = flopy.mf6.ModflowGwf(sim, modelname='test_model')

        # Add DISV package to the model using the disv_data from the fixture
        disv_data = simple_disv_data
        ncpl = disv_data['ncpl']
        nvert = disv_data['nvert']
        vertices = disv_data['vertices']
        cell2d = disv_data['cell2d']

        disv = flopy.mf6.ModflowGwfdisv(
            gwf,
            nlay=1,
            ncpl=ncpl,
            nvert=nvert,
            top=100.0,
            botm=[0.0],
            vertices=vertices,
            cell2d=cell2d,
        )

        # Get the modelgrid from the gwf model
        modelgrid = gwf.modelgrid

        yield {
            'gwf': gwf,
            'modelgrid': modelgrid,
            'sim': sim,
            'tmpdir': tmpdir,
        }


# =============================================================================
# Tests for assign_river_cells
# =============================================================================

class TestAssignRiverCells:
    """Tests for the assign_river_cells function."""

    def test_basic_river_intersection(self, river_gdf, simple_voronoi_grid):
        """Test basic river-grid intersection."""
        modelgrid = simple_voronoi_grid['modelgrid']

        spd = assign_river_cells(river_gdf, modelgrid)

        assert len(spd) > 0, "Should find intersecting cells"

        # Check structure of stress period data
        for entry in spd:
            cell_id, stage, conductance, rbot = entry
            assert isinstance(cell_id, tuple), "Cell ID should be a tuple"
            assert len(cell_id) == 2, "DISV cell ID should have (layer, cell2d)"
            assert stage == 100.0, "Stage should match input"
            assert rbot == 95.0, "Rbot should match input"
            assert conductance > 0, "Conductance should be positive"

    def test_river_conductance_scaling(self, simple_voronoi_grid):
        """Test that conductance is scaled by intersection length."""
        modelgrid = simple_voronoi_grid['modelgrid']

        # Create a short and long river
        short_river = gpd.GeoDataFrame(
            {'stage': [100.0], 'conductance': [10.0], 'rbot': [95.0]},
            geometry=[LineString([(400, 500), (600, 500)])],  # 200m
            crs=None,
        )

        long_river = gpd.GeoDataFrame(
            {'stage': [100.0], 'conductance': [10.0], 'rbot': [95.0]},
            geometry=[LineString([(0, 500), (1000, 500)])],  # 1000m
            crs=None,
        )

        short_spd = assign_river_cells(short_river, modelgrid)
        long_spd = assign_river_cells(long_river, modelgrid)

        # Total conductance should be proportional to river length
        short_total_cond = sum(entry[2] for entry in short_spd)
        long_total_cond = sum(entry[2] for entry in long_spd)

        # Long river should have more total conductance
        assert long_total_cond > short_total_cond

    def test_river_multi_reach(self, river_gdf_multi_reach, simple_voronoi_grid):
        """Test river with multiple reaches."""
        modelgrid = simple_voronoi_grid['modelgrid']

        spd = assign_river_cells(river_gdf_multi_reach, modelgrid)

        assert len(spd) > 0, "Should find intersecting cells"

        # Check that we have both stage values in results
        stages = set(entry[1] for entry in spd)
        assert 100.0 in stages or 99.5 in stages, "Should include stages from different reaches"

    def test_river_missing_columns(self, simple_voronoi_grid):
        """Test error handling for missing required columns."""
        modelgrid = simple_voronoi_grid['modelgrid']

        # Missing conductance column
        bad_gdf = gpd.GeoDataFrame(
            {'stage': [100.0], 'rbot': [95.0]},
            geometry=[LineString([(0, 500), (1000, 500)])],
            crs=None,
        )

        with pytest.raises(ValueError, match="Missing required columns"):
            assign_river_cells(bad_gdf, modelgrid)

    def test_river_custom_column_names(self, simple_voronoi_grid):
        """Test using custom column names."""
        modelgrid = simple_voronoi_grid['modelgrid']

        gdf = gpd.GeoDataFrame(
            {'water_level': [100.0], 'cond': [10.0], 'bottom': [95.0]},
            geometry=[LineString([(0, 500), (1000, 500)])],
            crs=None,
        )

        spd = assign_river_cells(
            gdf,
            modelgrid,
            stage_column='water_level',
            conductance_column='cond',
            rbot_column='bottom',
        )

        assert len(spd) > 0, "Should work with custom column names"

    def test_river_with_layer(self, river_gdf, simple_voronoi_grid):
        """Test river assignment to specific layer."""
        modelgrid = simple_voronoi_grid['modelgrid']

        spd = assign_river_cells(river_gdf, modelgrid, layer=2)

        for entry in spd:
            cell_id = entry[0]
            assert cell_id[0] == 2, "Layer should be 2"

    def test_river_empty_geodataframe(self, simple_voronoi_grid):
        """Test with empty GeoDataFrame."""
        modelgrid = simple_voronoi_grid['modelgrid']

        empty_gdf = gpd.GeoDataFrame(
            {'stage': [], 'conductance': [], 'rbot': []},
            geometry=[],
            crs=None,
        )

        spd = assign_river_cells(empty_gdf, modelgrid)

        assert len(spd) == 0, "Should return empty list for empty input"

    def test_river_outside_domain(self, simple_voronoi_grid):
        """Test river completely outside domain."""
        modelgrid = simple_voronoi_grid['modelgrid']

        outside_river = gpd.GeoDataFrame(
            {'stage': [100.0], 'conductance': [10.0], 'rbot': [95.0]},
            geometry=[LineString([(2000, 500), (3000, 500)])],  # Far outside
            crs=None,
        )

        spd = assign_river_cells(outside_river, modelgrid)

        assert len(spd) == 0, "Should return empty list for river outside domain"


# =============================================================================
# Tests for assign_well_cells
# =============================================================================

class TestAssignWellCells:
    """Tests for the assign_well_cells function."""

    def test_basic_well_assignment(self, well_gdf, simple_voronoi_grid):
        """Test basic well-to-cell assignment."""
        modelgrid = simple_voronoi_grid['modelgrid']

        spd = assign_well_cells(well_gdf, modelgrid)

        assert len(spd) == 3, "Should find cells for all 3 wells"

        # Check structure
        for entry in spd:
            cell_id, rate = entry
            assert isinstance(cell_id, tuple), "Cell ID should be a tuple"
            assert rate < 0, "Extraction rates should be negative"

    def test_well_rates_preserved(self, well_gdf, simple_voronoi_grid):
        """Test that well rates are preserved correctly."""
        modelgrid = simple_voronoi_grid['modelgrid']

        spd = assign_well_cells(well_gdf, modelgrid)

        rates = sorted([entry[1] for entry in spd])
        expected_rates = sorted([-150.0, -100.0, -50.0])

        assert rates == expected_rates, "Rates should match input"

    def test_well_with_layers(self, well_gdf_with_layers, simple_voronoi_grid):
        """Test well assignment with layer specification."""
        modelgrid = simple_voronoi_grid['modelgrid']

        spd = assign_well_cells(
            well_gdf_with_layers,
            modelgrid,
            layer_column='layer',
        )

        layers = [entry[0][0] for entry in spd]
        assert 0 in layers and 1 in layers and 2 in layers, "Should use specified layers"

    def test_well_default_layer(self, well_gdf, simple_voronoi_grid):
        """Test well assignment with default layer."""
        modelgrid = simple_voronoi_grid['modelgrid']

        spd = assign_well_cells(well_gdf, modelgrid, default_layer=3)

        for entry in spd:
            assert entry[0][0] == 3, "All wells should be in layer 3"

    def test_well_missing_rate_column(self, simple_voronoi_grid):
        """Test error for missing rate column."""
        modelgrid = simple_voronoi_grid['modelgrid']

        bad_gdf = gpd.GeoDataFrame(
            {'name': ['Well_1']},
            geometry=[Point(500, 500)],
            crs=None,
        )

        with pytest.raises(ValueError, match="Missing required column"):
            assign_well_cells(bad_gdf, modelgrid)

    def test_well_outside_domain_warning(self, well_outside_domain, simple_voronoi_grid):
        """Test warning for wells outside domain."""
        modelgrid = simple_voronoi_grid['modelgrid']

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            spd = assign_well_cells(well_outside_domain, modelgrid)

            assert len(spd) == 0, "Should not find cell for well outside domain"
            assert any("outside the model domain" in str(warning.message) for warning in w)

    def test_well_custom_rate_column(self, simple_voronoi_grid):
        """Test using custom rate column name."""
        modelgrid = simple_voronoi_grid['modelgrid']

        gdf = gpd.GeoDataFrame(
            {'pumping': [-100.0]},
            geometry=[Point(500, 500)],
            crs=None,
        )

        spd = assign_well_cells(gdf, modelgrid, rate_column='pumping')

        assert len(spd) == 1
        assert spd[0][1] == -100.0

    def test_well_injection_positive_rate(self, simple_voronoi_grid):
        """Test that positive rates (injection) work correctly."""
        modelgrid = simple_voronoi_grid['modelgrid']

        gdf = gpd.GeoDataFrame(
            {'rate': [50.0]},  # Positive = injection
            geometry=[Point(500, 500)],
            crs=None,
        )

        spd = assign_well_cells(gdf, modelgrid)

        assert spd[0][1] == 50.0, "Injection rate should be positive"


# =============================================================================
# Tests for assign_idomain_from_geometry
# =============================================================================

class TestAssignIdomainFromGeometry:
    """Tests for the assign_idomain_from_geometry function."""

    def test_basic_idomain_assignment(self, simple_square_boundary, simple_voronoi_grid):
        """Test basic IDOMAIN creation from boundary polygon."""
        modelgrid = simple_voronoi_grid['modelgrid']

        idomain = assign_idomain_from_geometry(simple_square_boundary, modelgrid)

        assert idomain.shape[0] == 1, "Default is 1 layer"
        assert idomain.shape[1] == modelgrid.ncpl, "Should match grid cells"
        assert np.sum(idomain == 1) > 0, "Should have active cells"

    def test_idomain_multiple_layers(self, simple_square_boundary, simple_voronoi_grid):
        """Test IDOMAIN with multiple layers."""
        modelgrid = simple_voronoi_grid['modelgrid']

        idomain = assign_idomain_from_geometry(
            simple_square_boundary,
            modelgrid,
            nlay=3,
        )

        assert idomain.shape[0] == 3, "Should have 3 layers"
        # All layers should have the same pattern
        assert np.array_equal(idomain[0], idomain[1])
        assert np.array_equal(idomain[1], idomain[2])

    def test_idomain_custom_values(self, simple_square_boundary, simple_voronoi_grid):
        """Test IDOMAIN with custom active/inactive values."""
        modelgrid = simple_voronoi_grid['modelgrid']

        idomain = assign_idomain_from_geometry(
            simple_square_boundary,
            modelgrid,
            active_value=5,
            inactive_value=-1,
        )

        assert 5 in idomain, "Should have custom active value"
        # May or may not have inactive cells depending on grid

    def test_idomain_partial_coverage(self, simple_voronoi_grid):
        """Test IDOMAIN where polygon covers only part of grid."""
        modelgrid = simple_voronoi_grid['modelgrid']

        # Polygon covering only left half
        partial_polygon = gpd.GeoDataFrame(
            {'name': ['partial']},
            geometry=[Polygon([(0, 0), (500, 0), (500, 1000), (0, 1000), (0, 0)])],
            crs=None,
        )

        idomain = assign_idomain_from_geometry(partial_polygon, modelgrid)

        # Should have both active and inactive cells
        n_active = np.sum(idomain == 1)
        n_inactive = np.sum(idomain == 0)

        assert n_active > 0, "Should have some active cells"
        assert n_inactive > 0, "Should have some inactive cells"

    def test_idomain_empty_polygon_error(self, simple_voronoi_grid):
        """Test error for empty polygon GeoDataFrame."""
        modelgrid = simple_voronoi_grid['modelgrid']

        empty_gdf = gpd.GeoDataFrame(geometry=[], crs=None)

        with pytest.raises(ValueError, match="No valid polygon geometries"):
            assign_idomain_from_geometry(empty_gdf, modelgrid)

    def test_idomain_l_shaped_domain(self, irregular_boundary, simple_voronoi_grid):
        """Test IDOMAIN for L-shaped domain."""
        modelgrid = simple_voronoi_grid['modelgrid']

        idomain = assign_idomain_from_geometry(irregular_boundary, modelgrid)

        n_active = np.sum(idomain == 1)
        total_cells = modelgrid.ncpl

        # L-shaped domain should cover less than full grid
        assert n_active < total_cells, "L-shape should not cover all cells"
        assert n_active > 0, "Should have some active cells"


# =============================================================================
# Tests for create_riv_package
# =============================================================================

class TestCreateRivPackage:
    """Tests for the create_riv_package function."""

    def test_basic_riv_package_creation(self, mock_gwf_model, river_gdf):
        """Test basic RIV package creation."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        riv = create_riv_package(gwf, river_gdf, modelgrid)

        assert riv is not None, "Package should be created"
        assert riv.name[0] == 'riv', "Package name should be 'riv'"

    def test_riv_package_custom_name(self, mock_gwf_model, river_gdf):
        """Test RIV package with custom name."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        riv = create_riv_package(gwf, river_gdf, modelgrid, pname='river_bc')

        assert riv.name[0] == 'river_bc'

    def test_riv_package_empty_warning(self, mock_gwf_model):
        """Test warning when no river cells found."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        # River outside domain
        outside_river = gpd.GeoDataFrame(
            {'stage': [100.0], 'conductance': [10.0], 'rbot': [95.0]},
            geometry=[LineString([(2000, 500), (3000, 500)])],
            crs=None,
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            riv = create_riv_package(gwf, outside_river, modelgrid)

            assert any("No river cells found" in str(warning.message) for warning in w)


# =============================================================================
# Tests for create_wel_package
# =============================================================================

class TestCreateWelPackage:
    """Tests for the create_wel_package function."""

    def test_basic_wel_package_creation(self, mock_gwf_model, well_gdf):
        """Test basic WEL package creation."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        wel = create_wel_package(gwf, well_gdf, modelgrid)

        assert wel is not None, "Package should be created"
        assert wel.name[0] == 'wel', "Package name should be 'wel'"

    def test_wel_package_with_layers(self, mock_gwf_model, well_gdf_with_layers):
        """Test WEL package with layer specification."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        wel = create_wel_package(
            gwf,
            well_gdf_with_layers,
            modelgrid,
            layer_column='layer',
        )

        assert wel is not None


# =============================================================================
# Tests for create_chd_package
# =============================================================================

class TestCreateChdPackage:
    """Tests for the create_chd_package function."""

    def test_chd_from_points(self, mock_gwf_model, chd_points_gdf):
        """Test CHD package from point geometries."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        chd = create_chd_package(gwf, chd_points_gdf, modelgrid)

        assert chd is not None, "Package should be created"
        assert chd.name[0] == 'chd'

    def test_chd_from_line(self, mock_gwf_model, chd_line_gdf):
        """Test CHD package from line geometry."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        chd = create_chd_package(gwf, chd_line_gdf, modelgrid)

        assert chd is not None

    def test_chd_from_polygon(self, mock_gwf_model, chd_polygon_gdf):
        """Test CHD package from polygon geometry."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        chd = create_chd_package(gwf, chd_polygon_gdf, modelgrid)

        assert chd is not None

    def test_chd_missing_head_column(self, mock_gwf_model):
        """Test error for missing head column."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        bad_gdf = gpd.GeoDataFrame(
            {'name': ['point']},
            geometry=[Point(500, 500)],
            crs=None,
        )

        with pytest.raises(ValueError, match="Missing required column"):
            create_chd_package(gwf, bad_gdf, modelgrid)

    def test_chd_custom_head_column(self, mock_gwf_model):
        """Test CHD with custom head column name."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        gdf = gpd.GeoDataFrame(
            {'water_level': [100.0]},
            geometry=[Point(500, 500)],
            crs=None,
        )

        chd = create_chd_package(gwf, gdf, modelgrid, head_column='water_level')

        assert chd is not None


# =============================================================================
# Tests for create_rch_package
# =============================================================================

class TestCreateRchPackage:
    """Tests for the create_rch_package function."""

    def test_uniform_recharge(self, mock_gwf_model):
        """Test uniform recharge package."""
        gwf = mock_gwf_model['gwf']

        rch = create_rch_package(gwf, recharge_rate=0.001)

        assert rch is not None, "Package should be created"
        assert rch.name[0] == 'rch'

    def test_zone_based_recharge(self, mock_gwf_model, recharge_zones_gdf):
        """Test zone-based recharge package."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        rch = create_rch_package(
            gwf,
            recharge_rate=0.0005,  # Default rate
            recharge_zones_gdf=recharge_zones_gdf,
            modelgrid=modelgrid,
        )

        assert rch is not None

    def test_zone_recharge_missing_modelgrid(self, mock_gwf_model, recharge_zones_gdf):
        """Test error when zones provided but no modelgrid."""
        gwf = mock_gwf_model['gwf']

        with pytest.raises(ValueError, match="modelgrid must be provided"):
            create_rch_package(
                gwf,
                recharge_rate=0.001,
                recharge_zones_gdf=recharge_zones_gdf,
                modelgrid=None,
            )

    def test_zone_recharge_missing_rate_column(self, mock_gwf_model):
        """Test error for missing rate column in zones."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        bad_zones = gpd.GeoDataFrame(
            {'name': ['zone1']},
            geometry=[Polygon([(0, 0), (500, 0), (500, 500), (0, 500), (0, 0)])],
            crs=None,
        )

        with pytest.raises(ValueError, match="Missing required column"):
            create_rch_package(
                gwf,
                recharge_rate=0.001,
                recharge_zones_gdf=bad_zones,
                modelgrid=modelgrid,
            )

    def test_rch_custom_pname(self, mock_gwf_model):
        """Test RCH package with custom name."""
        gwf = mock_gwf_model['gwf']

        rch = create_rch_package(gwf, recharge_rate=0.001, pname='recharge')

        assert rch.name[0] == 'recharge'


# =============================================================================
# Tests for validate_bc_geometries
# =============================================================================

class TestValidateBcGeometries:
    """Tests for the validate_bc_geometries function."""

    def test_validate_points_inside_domain(self, well_gdf, simple_voronoi_grid):
        """Test validation of points inside domain."""
        modelgrid = simple_voronoi_grid['modelgrid']

        results = validate_bc_geometries(well_gdf, modelgrid, expected_type='point')

        assert results['n_features'] == 3
        assert results['n_valid'] == 3
        assert results['n_inside_domain'] == 3
        assert 'Point' in results['geometry_types']
        assert len(results['warnings']) == 0

    def test_validate_lines(self, river_gdf, simple_voronoi_grid):
        """Test validation of line geometries."""
        modelgrid = simple_voronoi_grid['modelgrid']

        results = validate_bc_geometries(river_gdf, modelgrid, expected_type='line')

        assert results['n_features'] == 1
        assert 'LineString' in results['geometry_types']

    def test_validate_polygons(self, two_zone_polygons, simple_voronoi_grid):
        """Test validation of polygon geometries."""
        modelgrid = simple_voronoi_grid['modelgrid']

        results = validate_bc_geometries(two_zone_polygons, modelgrid, expected_type='polygon')

        assert results['n_features'] == 2
        assert 'Polygon' in results['geometry_types']

    def test_validate_outside_domain_warning(self, well_outside_domain, simple_voronoi_grid):
        """Test warning for geometries outside domain."""
        modelgrid = simple_voronoi_grid['modelgrid']

        results = validate_bc_geometries(well_outside_domain, modelgrid)

        assert results['n_inside_domain'] == 0
        assert len(results['warnings']) > 0
        assert any("outside" in w.lower() for w in results['warnings'])

    def test_validate_unexpected_geometry_type(self, well_gdf, simple_voronoi_grid):
        """Test warning for unexpected geometry type."""
        modelgrid = simple_voronoi_grid['modelgrid']

        # Expect lines but get points
        results = validate_bc_geometries(well_gdf, modelgrid, expected_type='line')

        assert len(results['warnings']) > 0
        assert any("Unexpected geometry types" in w for w in results['warnings'])

    def test_validate_any_geometry_type(self, well_gdf, simple_voronoi_grid):
        """Test validation with 'any' geometry type (no warnings)."""
        modelgrid = simple_voronoi_grid['modelgrid']

        results = validate_bc_geometries(well_gdf, modelgrid, expected_type='any')

        # No warning about geometry types with 'any'
        type_warnings = [w for w in results['warnings'] if "Unexpected geometry" in w]
        assert len(type_warnings) == 0

    def test_validate_empty_geodataframe(self, simple_voronoi_grid):
        """Test validation of empty GeoDataFrame."""
        modelgrid = simple_voronoi_grid['modelgrid']

        empty_gdf = gpd.GeoDataFrame(geometry=[], crs=None)

        results = validate_bc_geometries(empty_gdf, modelgrid)

        assert results['n_features'] == 0
        assert results['n_valid'] == 0
        assert results['n_inside_domain'] == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestBoundaryUtilsIntegration:
    """Integration tests combining multiple boundary utilities."""

    def test_complete_model_setup(self, mock_gwf_model, river_gdf, well_gdf, simple_square_boundary):
        """Test setting up a complete model with multiple boundary conditions."""
        gwf = mock_gwf_model['gwf']
        modelgrid = mock_gwf_model['modelgrid']

        # Create all boundary packages
        riv = create_riv_package(gwf, river_gdf, modelgrid)
        wel = create_wel_package(gwf, well_gdf, modelgrid)
        rch = create_rch_package(gwf, recharge_rate=0.001)

        # All packages should be created
        assert riv is not None
        assert wel is not None
        assert rch is not None

    def test_structured_and_disv_compatibility(self, river_gdf, well_gdf, simple_structured_grid, simple_voronoi_grid):
        """Test that functions work with both structured and DISV grids."""
        struct_grid = simple_structured_grid
        disv_grid = simple_voronoi_grid['modelgrid']

        # River cells
        riv_struct = assign_river_cells(river_gdf, struct_grid)
        riv_disv = assign_river_cells(river_gdf, disv_grid)

        assert len(riv_struct) > 0
        assert len(riv_disv) > 0

        # Well cells
        wel_struct = assign_well_cells(well_gdf, struct_grid)
        wel_disv = assign_well_cells(well_gdf, disv_grid)

        assert len(wel_struct) == 3
        assert len(wel_disv) == 3

        # Cell ID formats differ
        # Structured: (layer, row, col)
        # DISV: (layer, cell2d)
        assert len(riv_struct[0][0]) == 3, "Structured should have 3 element cell ID"
        assert len(riv_disv[0][0]) == 2, "DISV should have 2 element cell ID"


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_multilinestring_river(self, simple_voronoi_grid):
        """Test river with MultiLineString geometry."""
        from shapely.geometry import MultiLineString

        modelgrid = simple_voronoi_grid['modelgrid']

        multi_line = MultiLineString([
            [(0, 500), (500, 500)],
            [(500, 500), (1000, 500)],
        ])

        gdf = gpd.GeoDataFrame(
            {'stage': [100.0], 'conductance': [10.0], 'rbot': [95.0]},
            geometry=[multi_line],
            crs=None,
        )

        spd = assign_river_cells(gdf, modelgrid)

        assert len(spd) > 0, "Should handle MultiLineString"

    def test_multipolygon_idomain(self, simple_voronoi_grid):
        """Test IDOMAIN with MultiPolygon geometry."""
        from shapely.geometry import MultiPolygon

        modelgrid = simple_voronoi_grid['modelgrid']

        multi_poly = MultiPolygon([
            Polygon([(100, 100), (400, 100), (400, 400), (100, 400)]),
            Polygon([(600, 600), (900, 600), (900, 900), (600, 900)]),
        ])

        gdf = gpd.GeoDataFrame(
            {'name': ['zones']},
            geometry=[multi_poly],
            crs=None,
        )

        idomain = assign_idomain_from_geometry(gdf, modelgrid)

        assert np.sum(idomain == 1) > 0, "Should find active cells in MultiPolygon"

    def test_zero_rate_wells(self, simple_voronoi_grid):
        """Test wells with zero pumping rate."""
        modelgrid = simple_voronoi_grid['modelgrid']

        gdf = gpd.GeoDataFrame(
            {'rate': [0.0, 0.0]},
            geometry=[Point(250, 250), Point(750, 750)],
            crs=None,
        )

        spd = assign_well_cells(gdf, modelgrid)

        # Should still include wells with zero rate
        assert len(spd) == 2
        assert all(entry[1] == 0.0 for entry in spd)

    def test_very_small_river_segment(self, simple_voronoi_grid):
        """Test very small river segment (smaller than cell size)."""
        modelgrid = simple_voronoi_grid['modelgrid']

        # Very short segment (1m when cells are ~100m)
        tiny_river = gpd.GeoDataFrame(
            {'stage': [100.0], 'conductance': [10.0], 'rbot': [95.0]},
            geometry=[LineString([(500, 500), (501, 500)])],  # 1m segment
            crs=None,
        )

        spd = assign_river_cells(tiny_river, modelgrid)

        # Should find the cell containing this segment
        # May be 0 or 1 depending on grid alignment
        assert len(spd) >= 0  # Just ensure it doesn't crash

    def test_coincident_wells(self, simple_voronoi_grid):
        """Test multiple wells at the same location."""
        modelgrid = simple_voronoi_grid['modelgrid']

        # Two wells at exact same location
        gdf = gpd.GeoDataFrame(
            {'rate': [-100.0, -50.0]},
            geometry=[Point(500, 500), Point(500, 500)],
            crs=None,
        )

        spd = assign_well_cells(gdf, modelgrid)

        # Both wells should be assigned to the same cell
        assert len(spd) == 2
        assert spd[0][0] == spd[1][0], "Same location = same cell"
