"""Readiness regressions using fake geospatial imports; no MODFLOW or GIS setup."""
from __future__ import annotations

import builtins
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import diagnostics  # noqa: E402


@pytest.fixture
def geospatial_stack(monkeypatch):
    """Exercise the smoke test with controlled core operations and extra imports."""
    state = SimpleNamespace(core_error=None, valid=True, missing=set(), probes=[])
    polygon = SimpleNamespace(
        exterior=SimpleNamespace(coords=SimpleNamespace(xy=([0, 1, 0], [0, 0, 1]))),
        area=1.0,
    )

    class GeoDataFrame:
        def __init__(self, data, crs):
            self.geometry = data["geometry"]
            self.area = SimpleNamespace(sum=lambda: 2.0)

        def to_crs(self, crs):
            if state.core_error:
                raise RuntimeError(state.core_error)
            return self

        def __len__(self):
            return len(self.geometry)

    class GeoSeries:
        def __init__(self, geometries, crs):
            self.iloc = geometries

        def to_crs(self, crs):
            return self

    def unary_union(geometries):
        polygon.is_valid = state.valid
        return polygon

    modules = {
        "geopandas": SimpleNamespace(GeoDataFrame=GeoDataFrame, GeoSeries=GeoSeries),
        "shapely.geometry": SimpleNamespace(box=lambda *args: polygon),
        "shapely.ops": SimpleNamespace(unary_union=unary_union),
        "pyproj": SimpleNamespace(
            Geod=lambda **kwargs: SimpleNamespace(
                polygon_area_perimeter=lambda lon, lat: (1.0, 4.0)
            )
        ),
    }
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in modules:
            return modules[name]
        if name in ("fiona", "rasterio", "contextily"):
            state.probes.append(name)
            if name in state.missing:
                raise ModuleNotFoundError(f"No module named '{name}'")
            return SimpleNamespace()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    return state


def ready_results():
    """Supply passing unrelated inputs and run the actual geospatial smoke test."""
    return {
        "packages": {"missing_essential": []},
        "modflow": {"executable_found": True, "run_success": True},
        "geospatial": diagnostics.geospatial_smoke_test(),
    }


@pytest.mark.parametrize("extra", ["fiona", "rasterio", "contextily"])
def test_healthy_core_missing_optional_extra_is_ready(geospatial_stack, extra):
    geospatial_stack.missing.add(extra)
    results = ready_results()
    summary = diagnostics.build_summary(results)
    assert results["geospatial"]["success"] is True
    assert results["geospatial"][extra].startswith("ERROR:")
    assert geospatial_stack.probes == ["fiona", "rasterio", "contextily"]
    assert summary["geospatial_success"] is True
    assert summary["geospatial_optional_errors"] == [extra]
    assert "geospatial_errors" not in summary
    assert summary["overall_ready"] is True


def test_core_operation_failure_skips_extras(geospatial_stack):
    geospatial_stack.core_error = "projection failed"
    results = ready_results()
    geo = results["geospatial"]
    summary = diagnostics.build_summary(results)
    assert geo["success"] is False
    assert geo["error"] == "projection failed"
    assert geospatial_stack.probes == []
    assert not {"fiona", "rasterio", "contextily"}.intersection(geo)
    assert summary["geospatial_optional_errors"] == []
    assert summary["overall_ready"] is False


def test_invalid_union_fails_core(geospatial_stack):
    geospatial_stack.valid = False
    results = ready_results()
    assert results["geospatial"]["union_valid"] is False
    assert results["geospatial"]["success"] is False
    assert results["geospatial"]["error"] == "Geospatial union is invalid"
    assert geospatial_stack.probes == []
    assert diagnostics.build_summary(results)["overall_ready"] is False


def test_absent_modflow_results_fail_closed(geospatial_stack):
    results = ready_results()
    del results["modflow"]
    assert diagnostics.build_summary(results)["overall_ready"] is False


def test_missing_geospatial_success_fails_closed(geospatial_stack):
    results = ready_results()
    del results["geospatial"]["success"]
    assert diagnostics.build_summary(results)["overall_ready"] is False


@pytest.mark.parametrize("absent", [True, False], ids=["absent", "empty"])
def test_absent_or_empty_geospatial_results_fail_closed(geospatial_stack, absent):
    results = ready_results()
    if absent:
        del results["geospatial"]
    else:
        results["geospatial"] = {}
    assert diagnostics.build_summary(results)["overall_ready"] is False


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("packages", "missing_essential", ["numpy"]),
        ("modflow", "executable_found", False),
        ("modflow", "run_success", False),
    ],
    ids=["missing-essential", "missing-modflow-executable", "failed-modflow-run"],
)
def test_unrelated_readiness_inputs_still_block(geospatial_stack, section, key, value):
    results = ready_results()
    assert diagnostics.build_summary(results)["overall_ready"] is True
    results[section][key] = value
    assert diagnostics.build_summary(results)["overall_ready"] is False
