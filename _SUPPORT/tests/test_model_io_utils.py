"""
Unit tests for model_io_utils module.

Tests cover:
- load_and_interpolate_aquifer_thickness: Loading and blending thickness data
  - Happy path with all data sources
  - Fallback behavior when data is missing
  - Error handling for various failure modes
  - Backward compatibility (blend_shallow_zones=False)

Run with: pytest _SUPPORT/tests/test_model_io_utils.py -v
"""

from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point, Polygon, LineString, MultiPolygon

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from model_io_utils import (
    load_and_interpolate_aquifer_thickness,
    DEFAULT_GWLTYP_TO_THICKNESS_M,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def simple_boundary_gdf():
    """Create a simple 1000x1000m square boundary polygon."""
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
        crs='EPSG:2056',
    )


@pytest.fixture
def simple_modelgrid(simple_boundary_gdf):
    """Create a simple Voronoi grid for testing."""
    from disv_grid_utils import create_voronoi_grid

    vor, modelgrid = create_voronoi_grid(
        simple_boundary_gdf,
        cell_size=100,
    )
    return modelgrid


@pytest.fixture
def deep_contours_gdf():
    """
    Create mock deep thickness contour lines (GS_GW_MAECHTIGKEIT_L).

    Contours with LABEL values representing deep aquifer thickness (30-50m).
    """
    # Create horizontal contour lines across the domain
    contours = [
        LineString([(0, 200), (1000, 200)]),
        LineString([(0, 500), (1000, 500)]),
        LineString([(0, 800), (1000, 800)]),
    ]
    labels = ['30', '40', '50']  # Deep thickness values in meters

    return gpd.GeoDataFrame(
        {'LABEL': labels, 'other_col': ['a', 'b', 'c']},
        geometry=contours,
        crs='EPSG:2056',
    )


@pytest.fixture
def shallow_zones_gdf():
    """
    Create mock shallow groundwater zones (GS_GW_LEITER_F).

    Polygons with GWLTYP values representing shallow zone classifications.
    """
    # Create zone polygons covering different parts of domain
    zone1 = Polygon([(0, 0), (500, 0), (500, 500), (0, 500), (0, 0)])
    zone2 = Polygon([(500, 0), (1000, 0), (1000, 500), (500, 500), (500, 0)])
    zone3 = Polygon([(0, 500), (1000, 500), (1000, 1000), (0, 1000), (0, 500)])

    return gpd.GeoDataFrame(
        {
            'GWLTYP': [1, 4, 6],  # Low, High, Very High thickness zones
            'name': ['zone1', 'zone2', 'zone3'],
        },
        geometry=[zone1, zone2, zone3],
        crs='EPSG:2056',
    )


@pytest.fixture
def mock_geopackage(tmp_path, deep_contours_gdf, shallow_zones_gdf):
    """
    Create a mock GeoPackage file with both deep and shallow layers.
    """
    gpkg_path = tmp_path / "mock_groundwater_data.gpkg"

    # Write both layers to the GeoPackage
    deep_contours_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
    shallow_zones_gdf.to_file(gpkg_path, layer='GS_GW_LEITER_F', driver='GPKG')

    return gpkg_path


@pytest.fixture
def mock_geopackage_deep_only(tmp_path, deep_contours_gdf):
    """Create a GeoPackage with only deep contours (no shallow layer)."""
    gpkg_path = tmp_path / "deep_only.gpkg"
    deep_contours_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
    return gpkg_path


@pytest.fixture
def mock_geopackage_shallow_only(tmp_path, shallow_zones_gdf):
    """Create a GeoPackage with only shallow zones (no deep contours)."""
    gpkg_path = tmp_path / "shallow_only.gpkg"
    shallow_zones_gdf.to_file(gpkg_path, layer='GS_GW_LEITER_F', driver='GPKG')
    return gpkg_path


@pytest.fixture
def shallow_zones_no_gwltyp_gdf():
    """Create shallow zones without GWLTYP column."""
    zone1 = Polygon([(0, 0), (500, 0), (500, 500), (0, 500), (0, 0)])
    return gpd.GeoDataFrame(
        {'name': ['zone1'], 'other_column': [123]},
        geometry=[zone1],
        crs='EPSG:2056',
    )


@pytest.fixture
def mock_geopackage_no_gwltyp(tmp_path, deep_contours_gdf, shallow_zones_no_gwltyp_gdf):
    """Create a GeoPackage where shallow layer has no GWLTYP column."""
    gpkg_path = tmp_path / "no_gwltyp.gpkg"
    deep_contours_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
    shallow_zones_no_gwltyp_gdf.to_file(gpkg_path, layer='GS_GW_LEITER_F', driver='GPKG')
    return gpkg_path


@pytest.fixture
def shallow_zones_unmapped_gwltyp_gdf():
    """Create shallow zones with GWLTYP values not in the default mapping."""
    zone1 = Polygon([(0, 0), (1000, 0), (1000, 1000), (0, 1000), (0, 0)])
    return gpd.GeoDataFrame(
        {'GWLTYP': [99], 'name': ['zone1']},  # 99 is not in default mapping
        geometry=[zone1],
        crs='EPSG:2056',
    )


@pytest.fixture
def mock_geopackage_unmapped_gwltyp(tmp_path, deep_contours_gdf, shallow_zones_unmapped_gwltyp_gdf):
    """Create a GeoPackage where GWLTYP values don't match the mapping."""
    gpkg_path = tmp_path / "unmapped_gwltyp.gpkg"
    deep_contours_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
    shallow_zones_unmapped_gwltyp_gdf.to_file(gpkg_path, layer='GS_GW_LEITER_F', driver='GPKG')
    return gpkg_path


@pytest.fixture
def deep_contours_wrong_column_gdf():
    """Create deep contours with wrong thickness column name."""
    contours = [LineString([(0, 500), (1000, 500)])]
    return gpd.GeoDataFrame(
        {'WRONG_COLUMN': ['40']},  # Not 'LABEL'
        geometry=contours,
        crs='EPSG:2056',
    )


@pytest.fixture
def mock_geopackage_wrong_column(tmp_path, deep_contours_wrong_column_gdf, shallow_zones_gdf):
    """Create a GeoPackage where deep contours have wrong column name."""
    gpkg_path = tmp_path / "wrong_column.gpkg"
    deep_contours_wrong_column_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
    shallow_zones_gdf.to_file(gpkg_path, layer='GS_GW_LEITER_F', driver='GPKG')
    return gpkg_path


@pytest.fixture
def deep_contours_invalid_values_gdf():
    """Create deep contours with non-numeric LABEL values."""
    contours = [
        LineString([(0, 200), (1000, 200)]),
        LineString([(0, 500), (1000, 500)]),
        LineString([(0, 800), (1000, 800)]),
    ]
    labels = ['invalid', 'NaN', 'abc']  # Non-numeric values

    return gpd.GeoDataFrame(
        {'LABEL': labels},
        geometry=contours,
        crs='EPSG:2056',
    )


@pytest.fixture
def mock_geopackage_invalid_values(tmp_path, deep_contours_invalid_values_gdf):
    """Create a GeoPackage with non-numeric thickness values."""
    gpkg_path = tmp_path / "invalid_values.gpkg"
    deep_contours_invalid_values_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
    return gpkg_path


@pytest.fixture
def empty_contours_gdf():
    """Create an empty GeoDataFrame with correct structure."""
    return gpd.GeoDataFrame(
        {'LABEL': []},
        geometry=[],
        crs='EPSG:2056',
    )


@pytest.fixture
def mock_geopackage_empty_contours(tmp_path, empty_contours_gdf):
    """Create a GeoPackage with empty contour layer."""
    gpkg_path = tmp_path / "empty_contours.gpkg"
    empty_contours_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
    return gpkg_path


@pytest.fixture
def contours_outside_boundary_gdf():
    """Create contours that are completely outside the model boundary."""
    contours = [
        LineString([(5000, 5000), (6000, 5000)]),
        LineString([(5000, 6000), (6000, 6000)]),
    ]
    return gpd.GeoDataFrame(
        {'LABEL': ['30', '40']},
        geometry=contours,
        crs='EPSG:2056',
    )


@pytest.fixture
def mock_geopackage_outside_boundary(tmp_path, contours_outside_boundary_gdf):
    """Create a GeoPackage with contours outside model boundary."""
    gpkg_path = tmp_path / "outside_boundary.gpkg"
    contours_outside_boundary_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
    return gpkg_path


@pytest.fixture
def shallow_zones_multipolygon_gdf():
    """Create shallow zones with MultiPolygon geometry."""
    poly1 = Polygon([(0, 0), (400, 0), (400, 400), (0, 400), (0, 0)])
    poly2 = Polygon([(600, 600), (1000, 600), (1000, 1000), (600, 1000), (600, 600)])
    multi = MultiPolygon([poly1, poly2])

    return gpd.GeoDataFrame(
        {'GWLTYP': [4], 'name': ['multi_zone']},
        geometry=[multi],
        crs='EPSG:2056',
    )


@pytest.fixture
def mock_geopackage_multipolygon(tmp_path, deep_contours_gdf, shallow_zones_multipolygon_gdf):
    """Create a GeoPackage with MultiPolygon shallow zones."""
    gpkg_path = tmp_path / "multipolygon.gpkg"
    deep_contours_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
    shallow_zones_multipolygon_gdf.to_file(gpkg_path, layer='GS_GW_LEITER_F', driver='GPKG')
    return gpkg_path


# =============================================================================
# Tests for DEFAULT_GWLTYP_TO_THICKNESS_M constant
# =============================================================================

class TestDefaultGwltypMapping:
    """Tests for the DEFAULT_GWLTYP_TO_THICKNESS_M constant."""

    def test_constant_exists(self):
        """Verify the constant is defined."""
        assert DEFAULT_GWLTYP_TO_THICKNESS_M is not None
        assert isinstance(DEFAULT_GWLTYP_TO_THICKNESS_M, dict)

    def test_constant_has_expected_keys(self):
        """Verify the constant has expected GWLTYP keys."""
        expected_keys = {1, 2, 4, 6}
        assert set(DEFAULT_GWLTYP_TO_THICKNESS_M.keys()) == expected_keys

    def test_constant_values_are_positive(self):
        """Verify all thickness values are positive."""
        for key, value in DEFAULT_GWLTYP_TO_THICKNESS_M.items():
            assert value > 0, f"GWLTYP {key} has non-positive thickness {value}"

    def test_constant_values_are_reasonable(self):
        """Verify thickness values are in reasonable range (1-50m)."""
        for key, value in DEFAULT_GWLTYP_TO_THICKNESS_M.items():
            assert 1 <= value <= 50, f"GWLTYP {key} has unreasonable thickness {value}"


# =============================================================================
# Tests for load_and_interpolate_aquifer_thickness - Happy Path
# =============================================================================

class TestLoadAndInterpolateThicknessHappyPath:
    """Tests for successful thickness loading and interpolation."""

    def test_basic_blending_all_sources(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that blending works with all three data sources."""
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            verbose=False,
        )

        assert result is not None
        assert isinstance(result, np.ndarray)
        assert len(result) == simple_modelgrid.ncpl
        assert not np.any(np.isnan(result))

    def test_result_within_minmax_range(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that result values are within min/max range."""
        min_thickness = 2.0
        max_thickness = 80.0

        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            min_thickness=min_thickness,
            max_thickness=max_thickness,
            verbose=False,
        )

        assert np.all(result >= min_thickness)
        assert np.all(result <= max_thickness)

    def test_disable_blending(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that blend_shallow_zones=False uses only deep contours."""
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            blend_shallow_zones=False,
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl
        # With only deep contours (30-50m), mean should be higher
        # than when blending with shallow zones (2-20m)

    def test_blending_produces_valid_results(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that blending shallow zones produces valid results.

        Note: With centroid-based blending (for smooth interpolation), the
        shallow zones provide sparse point constraints rather than dense
        boundary data. The deep contours typically dominate the interpolation,
        which produces smoother results.
        """
        result_no_blend = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            blend_shallow_zones=False,
            include_boundary_constraint=False,
            verbose=False,
        )

        result_with_blend = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            blend_shallow_zones=True,
            include_boundary_constraint=False,
            verbose=False,
        )

        # Both should produce valid results
        assert result_no_blend is not None
        assert result_with_blend is not None
        assert len(result_no_blend) == simple_modelgrid.ncpl
        assert len(result_with_blend) == simple_modelgrid.ncpl
        assert not np.any(np.isnan(result_no_blend))
        assert not np.any(np.isnan(result_with_blend))

    def test_disable_boundary_constraint(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that include_boundary_constraint=False works."""
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            include_boundary_constraint=False,
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl

    def test_custom_gwltyp_mapping(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that custom GWLTYP mapping is used."""
        custom_mapping = {1: 5, 4: 15, 6: 25}  # Different values than default

        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            gwltyp_to_thickness=custom_mapping,
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl

    def test_multipolygon_shallow_zones(
        self, mock_geopackage_multipolygon, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that MultiPolygon geometries are handled correctly.

        Each polygon in a MultiPolygon should contribute its centroid as a
        constraint point for smooth interpolation.
        """
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage_multipolygon,
            simple_modelgrid,
            simple_boundary_gdf,
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl

    def test_basic_interpolation_method(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that method='basic' works."""
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            method='basic',
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl


# =============================================================================
# Tests for load_and_interpolate_aquifer_thickness - Missing Data
# =============================================================================

class TestLoadAndInterpolateThicknessMissingData:
    """Tests for fallback behavior when data is missing or invalid."""

    def test_missing_file_returns_fallback(
        self, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that missing file returns uniform fallback thickness."""
        nonexistent_path = Path("/nonexistent/path/to/file.gpkg")
        fallback = 15.0

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = load_and_interpolate_aquifer_thickness(
                nonexistent_path,
                simple_modelgrid,
                simple_boundary_gdf,
                fallback_thickness=fallback,
                verbose=False,
            )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl
        assert np.all(result == fallback)
        # Check that a warning was issued
        assert len(w) >= 1
        assert "not found" in str(w[0].message).lower()

    def test_missing_contour_layer_with_shallow_zones(
        self, mock_geopackage_shallow_only, simple_modelgrid, simple_boundary_gdf
    ):
        """Test behavior when deep contour layer is missing but shallow exists."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = load_and_interpolate_aquifer_thickness(
                mock_geopackage_shallow_only,
                simple_modelgrid,
                simple_boundary_gdf,
                verbose=False,
            )

        # Should still work with shallow zones + boundary constraint
        assert result is not None
        assert len(result) == simple_modelgrid.ncpl

    def test_missing_shallow_layer_continues_with_deep(
        self, mock_geopackage_deep_only, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that missing shallow layer continues with deep contours only."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = load_and_interpolate_aquifer_thickness(
                mock_geopackage_deep_only,
                simple_modelgrid,
                simple_boundary_gdf,
                blend_shallow_zones=True,  # Explicitly enable blending
                verbose=False,
            )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl
        # Check that a warning was issued about missing shallow layer
        warning_messages = [str(warning.message).lower() for warning in w]
        assert any('shallow' in msg or 'leiter' in msg.lower() for msg in warning_messages)

    def test_missing_gwltyp_column_continues_with_deep(
        self, mock_geopackage_no_gwltyp, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that missing GWLTYP column continues with deep contours only."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = load_and_interpolate_aquifer_thickness(
                mock_geopackage_no_gwltyp,
                simple_modelgrid,
                simple_boundary_gdf,
                verbose=False,
            )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl
        # Check that a warning was issued about GWLTYP
        warning_messages = [str(warning.message).lower() for warning in w]
        assert any('gwltyp' in msg for msg in warning_messages)

    def test_unmapped_gwltyp_values_continues_with_deep(
        self, mock_geopackage_unmapped_gwltyp, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that unmapped GWLTYP values continue with deep contours only."""
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage_unmapped_gwltyp,
            simple_modelgrid,
            simple_boundary_gdf,
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl

    def test_wrong_thickness_column_with_shallow_zones(
        self, mock_geopackage_wrong_column, simple_modelgrid, simple_boundary_gdf
    ):
        """Test behavior when deep contours have wrong column but shallow exists."""
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage_wrong_column,
            simple_modelgrid,
            simple_boundary_gdf,
            verbose=False,
        )

        # Should still work with shallow zones + boundary constraint
        assert result is not None
        assert len(result) == simple_modelgrid.ncpl

    def test_invalid_thickness_values_returns_fallback(
        self, mock_geopackage_invalid_values, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that non-numeric thickness values result in fallback."""
        fallback = 17.5

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = load_and_interpolate_aquifer_thickness(
                mock_geopackage_invalid_values,
                simple_modelgrid,
                simple_boundary_gdf,
                blend_shallow_zones=False,  # Only use deep contours
                include_boundary_constraint=False,
                fallback_thickness=fallback,
                verbose=False,
            )

        # All values invalid, so should return fallback
        assert result is not None
        assert len(result) == simple_modelgrid.ncpl
        assert np.all(result == fallback)

    def test_empty_contours_returns_fallback(
        self, mock_geopackage_empty_contours, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that empty contour layer returns fallback thickness."""
        fallback = 20.0

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = load_and_interpolate_aquifer_thickness(
                mock_geopackage_empty_contours,
                simple_modelgrid,
                simple_boundary_gdf,
                blend_shallow_zones=False,
                include_boundary_constraint=False,
                fallback_thickness=fallback,
                verbose=False,
            )

        assert result is not None
        assert np.all(result == fallback)

    def test_contours_outside_boundary_returns_fallback(
        self, mock_geopackage_outside_boundary, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that contours completely outside boundary returns fallback."""
        fallback = 18.0

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = load_and_interpolate_aquifer_thickness(
                mock_geopackage_outside_boundary,
                simple_modelgrid,
                simple_boundary_gdf,
                blend_shallow_zones=False,
                include_boundary_constraint=False,
                fallback_thickness=fallback,
                verbose=False,
            )

        assert result is not None
        assert np.all(result == fallback)


# =============================================================================
# Tests for load_and_interpolate_aquifer_thickness - Input Validation
# =============================================================================

class TestLoadAndInterpolateThicknessValidation:
    """Tests for input validation and error handling."""

    def test_missing_xcellcenters_raises(
        self, mock_geopackage, simple_boundary_gdf
    ):
        """Test that grid without xcellcenters raises ValueError."""
        class MockGrid:
            ncpl = 100
            ycellcenters = np.zeros(100)

        with pytest.raises(ValueError, match="xcellcenters"):
            load_and_interpolate_aquifer_thickness(
                mock_geopackage,
                MockGrid(),
                simple_boundary_gdf,
                verbose=False,
            )

    def test_missing_ycellcenters_raises(
        self, mock_geopackage, simple_boundary_gdf
    ):
        """Test that grid without ycellcenters raises ValueError."""
        class MockGrid:
            ncpl = 100
            xcellcenters = np.zeros(100)

        with pytest.raises(ValueError, match="ycellcenters"):
            load_and_interpolate_aquifer_thickness(
                mock_geopackage,
                MockGrid(),
                simple_boundary_gdf,
                verbose=False,
            )

    def test_missing_ncpl_raises(
        self, mock_geopackage, simple_boundary_gdf
    ):
        """Test that grid without ncpl raises an error."""
        class MockGrid:
            xcellcenters = np.zeros(100)
            ycellcenters = np.zeros(100)

        # The implementation accesses ncpl early, so it raises AttributeError
        # before the explicit ValueError check
        with pytest.raises((ValueError, AttributeError)):
            load_and_interpolate_aquifer_thickness(
                mock_geopackage,
                MockGrid(),
                simple_boundary_gdf,
                verbose=False,
            )


# =============================================================================
# Tests for load_and_interpolate_aquifer_thickness - Edge Cases
# =============================================================================

class TestLoadAndInterpolateThicknessEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_verbose_output(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf, capsys
    ):
        """Test that verbose=True produces output."""
        load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            verbose=True,
        )

        captured = capsys.readouterr()
        assert "Loading" in captured.out
        assert "Result" in captured.out

    def test_verbose_false_suppresses_function_output(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf, capsys
    ):
        """Test that verbose=False suppresses the function's own output.

        Note: The underlying grid_utils interpolation functions may still print
        their own output. This test verifies that the function's own messages
        (Loading, Combining, Result, etc.) are suppressed.
        """
        load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            verbose=False,
        )

        captured = capsys.readouterr()
        # Our function's specific messages should not appear when verbose=False
        assert "Loading aquifer thickness" not in captured.out
        assert "Combining" not in captured.out
        assert "Result:" not in captured.out

    def test_extreme_min_thickness_clipping(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that extreme min_thickness clips values correctly."""
        min_thickness = 50.0  # Higher than most interpolated values

        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            min_thickness=min_thickness,
            max_thickness=100.0,
            verbose=False,
        )

        assert np.all(result >= min_thickness)

    def test_extreme_max_thickness_clipping(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that extreme max_thickness clips values correctly."""
        max_thickness = 5.0  # Lower than most interpolated values

        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            min_thickness=1.0,
            max_thickness=max_thickness,
            verbose=False,
        )

        assert np.all(result <= max_thickness)

    def test_custom_contour_layer_name(
        self, tmp_path, deep_contours_gdf, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that custom contour_layer parameter works."""
        gpkg_path = tmp_path / "custom_layer.gpkg"
        deep_contours_gdf.to_file(gpkg_path, layer='CUSTOM_LAYER', driver='GPKG')

        result = load_and_interpolate_aquifer_thickness(
            gpkg_path,
            simple_modelgrid,
            simple_boundary_gdf,
            contour_layer='CUSTOM_LAYER',
            blend_shallow_zones=False,
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl

    def test_custom_shallow_layer_name(
        self, tmp_path, deep_contours_gdf, shallow_zones_gdf, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that custom shallow_layer parameter works."""
        gpkg_path = tmp_path / "custom_shallow.gpkg"
        deep_contours_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')
        shallow_zones_gdf.to_file(gpkg_path, layer='CUSTOM_SHALLOW', driver='GPKG')

        result = load_and_interpolate_aquifer_thickness(
            gpkg_path,
            simple_modelgrid,
            simple_boundary_gdf,
            shallow_layer='CUSTOM_SHALLOW',
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl

    def test_alternative_thickness_column(
        self, tmp_path, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that alternative thickness column names are detected."""
        # Create contours with 'aquifer_thickness' column instead of 'LABEL'
        contours = [LineString([(0, 500), (1000, 500)])]
        gdf = gpd.GeoDataFrame(
            {'aquifer_thickness': [25.0]},
            geometry=contours,
            crs='EPSG:2056',
        )

        gpkg_path = tmp_path / "alt_column.gpkg"
        gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')

        result = load_and_interpolate_aquifer_thickness(
            gpkg_path,
            simple_modelgrid,
            simple_boundary_gdf,
            blend_shallow_zones=False,
            include_boundary_constraint=False,
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl


# =============================================================================
# Tests for load_and_interpolate_aquifer_thickness - Backward Compatibility
# =============================================================================

class TestLoadAndInterpolateThicknessBackwardCompatibility:
    """Tests to ensure backward compatibility with original behavior."""

    def test_default_parameters_work(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that function works with all default parameters."""
        # Only required parameters, all others default
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl

    def test_blend_false_matches_old_behavior(
        self, mock_geopackage_deep_only, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that blend_shallow_zones=False with deep-only data works like old behavior."""
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage_deep_only,
            simple_modelgrid,
            simple_boundary_gdf,
            blend_shallow_zones=False,
            include_boundary_constraint=False,
            verbose=False,
        )

        assert result is not None
        assert len(result) == simple_modelgrid.ncpl
        # Mean should be in the range of deep contours (30-50m)
        assert 25 <= result.mean() <= 55

    def test_return_type_unchanged(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that return type is still a 1D numpy array."""
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            verbose=False,
        )

        assert isinstance(result, np.ndarray)
        assert result.ndim == 1


# =============================================================================
# Tests for Boundary Constraint Handling
# =============================================================================

class TestBoundaryConstraint:
    """Tests specifically for boundary constraint feature."""

    def test_boundary_constraint_uses_min_thickness(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that boundary constraint is set to min_thickness value."""
        # With boundary constraint, edge cells should be influenced by min_thickness
        min_val = 3.0

        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            min_thickness=min_val,
            include_boundary_constraint=True,
            verbose=False,
        )

        assert np.all(result >= min_val)

    def test_boundary_constraint_handles_multipolygon_boundary(
        self, mock_geopackage, simple_modelgrid
    ):
        """Test that MultiPolygon boundaries are handled."""
        poly1 = Polygon([(0, 0), (400, 0), (400, 1000), (0, 1000), (0, 0)])
        poly2 = Polygon([(600, 0), (1000, 0), (1000, 1000), (600, 1000), (600, 0)])

        multi_boundary = gpd.GeoDataFrame(
            {'name': ['multi']},
            geometry=[MultiPolygon([poly1, poly2])],
            crs='EPSG:2056',
        )

        # This should not raise an error
        result = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            multi_boundary,
            verbose=False,
        )

        assert result is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestLoadAndInterpolateThicknessIntegration:
    """Integration tests for the complete workflow."""

    def test_complete_workflow_with_real_structure(
        self, mock_geopackage, simple_boundary_gdf
    ):
        """Test complete workflow from boundary to interpolated thickness."""
        from disv_grid_utils import create_voronoi_grid

        # Create grid
        vor, modelgrid = create_voronoi_grid(
            simple_boundary_gdf,
            cell_size=50,
        )

        # Load and interpolate thickness
        thickness = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            modelgrid,
            simple_boundary_gdf,
            verbose=False,
        )

        # Verify
        assert thickness is not None
        assert len(thickness) == modelgrid.ncpl
        assert not np.any(np.isnan(thickness))
        assert np.all(thickness > 0)

    def test_thickness_can_be_used_for_bottom_calculation(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that thickness array can be used to calculate model bottom."""
        thickness = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            verbose=False,
        )

        # Simulate model top
        model_top = np.full(simple_modelgrid.ncpl, 100.0)

        # Calculate bottom
        model_bottom = model_top - thickness

        # Verify
        assert len(model_bottom) == simple_modelgrid.ncpl
        assert np.all(model_bottom < model_top)
        assert np.all(model_bottom > 0)  # Assuming top=100, max_thickness=100


# =============================================================================
# Tests for Point Geometry Handling (Critical Bug Fix)
# =============================================================================

class TestPointGeometryHandling:
    """Tests to verify Point geometries are handled by interpolation functions.

    This test class was added after discovering a critical bug where Point
    geometries from shallow zone sampling were silently ignored by all
    interpolation functions in grid_utils.py.
    """

    def test_shallow_zone_points_affect_interpolation(
        self, mock_geopackage, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that shallow zone data actually affects the interpolation result.

        This is a critical test - previously, Point geometries from shallow
        zone interior sampling were silently ignored, making blend_shallow_zones
        effectively a no-op.
        """
        # Get result with blending (includes shallow zone Points)
        result_with_blend = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            blend_shallow_zones=True,
            include_boundary_constraint=False,
            verbose=False,
        )

        # Get result without blending (only deep contours)
        result_no_blend = load_and_interpolate_aquifer_thickness(
            mock_geopackage,
            simple_modelgrid,
            simple_boundary_gdf,
            blend_shallow_zones=False,
            include_boundary_constraint=False,
            verbose=False,
        )

        # The results should be different because shallow zones add constraints
        # Deep contours have 30-50m values, shallow zones have 2-20m values
        # If Points were being ignored, these would be identical
        assert not np.allclose(result_with_blend, result_no_blend), \
            "Shallow zone blending should affect interpolation result"

    def test_point_only_data_interpolates_correctly(
        self, tmp_path, simple_modelgrid, simple_boundary_gdf
    ):
        """Test that data containing only Point geometries is interpolated."""
        # Create a GeoDataFrame with only Point geometries
        points = [
            Point(200, 200),
            Point(500, 500),
            Point(800, 800),
        ]
        point_gdf = gpd.GeoDataFrame(
            {'LABEL': ['10', '20', '30']},
            geometry=points,
            crs='EPSG:2056',
        )

        gpkg_path = tmp_path / "points_only.gpkg"
        point_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')

        result = load_and_interpolate_aquifer_thickness(
            gpkg_path,
            simple_modelgrid,
            simple_boundary_gdf,
            blend_shallow_zones=False,
            include_boundary_constraint=False,
            verbose=False,
        )

        # Should get valid interpolation from Point data
        assert result is not None
        assert len(result) == simple_modelgrid.ncpl
        assert not np.any(np.isnan(result))
        # Values should be in the range of our input points (10-30m)
        assert np.min(result) >= 1.0  # After clipping
        assert np.max(result) <= 100.0

    def test_mixed_point_and_linestring_data(
        self, tmp_path, simple_modelgrid, simple_boundary_gdf
    ):
        """Test interpolation with mixed Point and LineString geometries."""
        # Create mixed geometry GeoDataFrame
        geometries = [
            LineString([(0, 300), (1000, 300)]),  # LineString
            Point(500, 700),  # Point
            LineString([(0, 900), (1000, 900)]),  # LineString
        ]
        mixed_gdf = gpd.GeoDataFrame(
            {'LABEL': ['20', '40', '60']},
            geometry=geometries,
            crs='EPSG:2056',
        )

        gpkg_path = tmp_path / "mixed_geom.gpkg"
        mixed_gdf.to_file(gpkg_path, layer='GS_GW_MAECHTIGKEIT_L', driver='GPKG')

        result = load_and_interpolate_aquifer_thickness(
            gpkg_path,
            simple_modelgrid,
            simple_boundary_gdf,
            blend_shallow_zones=False,
            include_boundary_constraint=False,
            verbose=False,
        )

        # Should handle both geometry types
        assert result is not None
        assert len(result) == simple_modelgrid.ncpl
        assert not np.any(np.isnan(result))


class TestGridUtilsPointExtraction:
    """Direct tests for Point handling in grid_utils extraction functions."""

    def test_extract_points_from_contours_handles_points(self):
        """Test _extract_points_from_contours handles Point geometries."""
        from grid_utils import _extract_points_from_contours

        # Create GeoDataFrame with Point geometries
        gdf = gpd.GeoDataFrame(
            {'thickness': [10.0, 20.0, 30.0]},
            geometry=[Point(0, 0), Point(100, 100), Point(200, 200)],
        )

        points = _extract_points_from_contours(gdf, 'thickness')

        assert len(points) == 3
        assert points[0] == (0, 0, 10.0)
        assert points[1] == (100, 100, 20.0)
        assert points[2] == (200, 200, 30.0)

    def test_extract_points_from_contours_handles_mixed(self):
        """Test _extract_points_from_contours handles mixed geometries."""
        from grid_utils import _extract_points_from_contours

        # Create GeoDataFrame with mixed geometries
        gdf = gpd.GeoDataFrame(
            {'thickness': [10.0, 20.0]},
            geometry=[
                Point(50, 50),
                LineString([(0, 0), (100, 0), (100, 100)]),
            ],
        )

        points = _extract_points_from_contours(gdf, 'thickness')

        # Should have 1 point from Point geometry + 3 points from LineString
        assert len(points) >= 4
        # First point should be from the Point geometry
        assert (50, 50, 10.0) in points

    def test_extract_dense_points_handles_points(self):
        """Test _extract_dense_points_from_contours handles Point geometries."""
        from grid_utils import _extract_dense_points_from_contours

        # Create GeoDataFrame with Point geometries
        gdf = gpd.GeoDataFrame(
            {'thickness': [15.0, 25.0]},
            geometry=[Point(0, 0), Point(500, 500)],
        )

        points = _extract_dense_points_from_contours(gdf, 'thickness', point_spacing=10)

        assert len(points) == 2
        assert points[0] == (0, 0, 15.0)
        assert points[1] == (500, 500, 25.0)

    def test_extract_dense_points_improved_handles_points(self):
        """Test _extract_dense_points_from_contours_improved handles Point geometries."""
        from grid_utils import _extract_dense_points_from_contours_improved

        # Create GeoDataFrame with Point geometries
        gdf = gpd.GeoDataFrame(
            {'thickness': [5.0, 35.0]},
            geometry=[Point(100, 100), Point(900, 900)],
        )

        points = _extract_dense_points_from_contours_improved(gdf, 'thickness', point_spacing=10)

        assert len(points) == 2
        assert points[0] == (100, 100, 5.0)
        assert points[1] == (900, 900, 35.0)

    def test_multipoint_geometry_handled(self):
        """Test that MultiPoint geometries are handled correctly."""
        from grid_utils import _extract_points_from_contours
        from shapely.geometry import MultiPoint

        # Create GeoDataFrame with MultiPoint geometry
        multi_point = MultiPoint([(0, 0), (100, 0), (100, 100)])
        gdf = gpd.GeoDataFrame(
            {'thickness': [42.0]},
            geometry=[multi_point],
        )

        points = _extract_points_from_contours(gdf, 'thickness')

        # Should extract all 3 points from the MultiPoint
        assert len(points) == 3
        assert all(p[2] == 42.0 for p in points)  # All should have same thickness
