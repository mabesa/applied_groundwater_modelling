"""
Tests for the template-local, FloPy-free scratch reader.

Two concerns are covered:

1. **Static contract** — ``PROJECT/workspace/template/scratch_io.py`` must never
   import ``flopy``, ``pyemu`` or the ``_SUPPORT`` repo helpers, so the student
   scratch notebook reruns from the submission ZIP alone. This is enforced by AST
   inspection (no import of the module required, so the check itself stays cheap
   and FloPy-free).

2. **Behaviour** — the reader/analysis helpers work against tiny synthetic
   exports (GPKG / CSV / JSON) built on the fly, with no heavy model workspace.

Run with:  uv run pytest _SUPPORT/tests/test_scratch_io_flopy_free.py -v
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import Polygon

# --------------------------------------------------------------------------
# Locate the template-local module (NOT on the _SUPPORT path on purpose).
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRATCH_IO_PATH = REPO_ROOT / "PROJECT" / "workspace" / "template" / "scratch_io.py"

FORBIDDEN_IMPORTS = ("flopy", "pyemu")
FORBIDDEN_IMPORT_PREFIXES = ("_SUPPORT",)
ALLOWED_THIRD_PARTY = {"numpy", "pandas", "geopandas"}
STDLIB_ALLOWED = {"json", "pathlib", "sys", "__future__"}


# =============================================================================
# 1. Static contract: no flopy / pyemu / _SUPPORT imports
# =============================================================================
def _collect_imported_roots(source: str) -> set:
    """Return the set of top-level module names imported anywhere in `source`."""
    tree = ast.parse(source)
    roots: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # level > 0 would be a relative import; there should be none.
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_scratch_io_exists():
    assert SCRATCH_IO_PATH.is_file(), f"missing template-local module: {SCRATCH_IO_PATH}"


def test_scratch_io_has_no_forbidden_imports():
    source = SCRATCH_IO_PATH.read_text(encoding="utf-8")
    roots = _collect_imported_roots(source)

    for bad in FORBIDDEN_IMPORTS:
        assert bad not in roots, (
            f"scratch_io.py must be FloPy-free but imports {bad!r}. "
            "The scratch notebook has to rerun from the submission ZIP alone."
        )
    for root in roots:
        for prefix in FORBIDDEN_IMPORT_PREFIXES:
            assert not root.startswith(prefix), (
                f"scratch_io.py must not depend on the {prefix} repo helpers "
                f"(found import of {root!r})."
            )


def test_scratch_io_import_allowlist():
    """Every imported root must be stdlib-allowed or an approved third party."""
    source = SCRATCH_IO_PATH.read_text(encoding="utf-8")
    roots = _collect_imported_roots(source)
    allowed = STDLIB_ALLOWED | ALLOWED_THIRD_PARTY
    unexpected = roots - allowed
    assert not unexpected, (
        f"scratch_io.py imports unexpected modules {sorted(unexpected)}. "
        f"Allowed: {sorted(allowed)}."
    )


def test_scratch_io_no_model_workspace_reads():
    """Guard against accidental use of FloPy readers for heavy model artifacts.

    We look for FloPy API symbols in *code* (string literals such as the module
    docstring, which merely names ``.hds``/``.cbc`` to say it avoids them, are
    excluded). Any of these would require a forbidden ``flopy`` import.
    """
    tree = ast.parse(SCRATCH_IO_PATH.read_text(encoding="utf-8"))
    banned_symbols = {"MfListBudget", "HeadFile", "MFSimulation", "CellBudgetFile"}
    used_names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    used_names |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    offending = sorted(banned_symbols & used_names)
    assert not offending, f"scratch_io.py uses FloPy model readers: {offending}"


# =============================================================================
# 2. Behaviour tests against synthetic exports
# =============================================================================
@pytest.fixture(scope="module")
def scratch_io():
    """Import the template-local module directly from its path."""
    spec = importlib.util.spec_from_file_location("scratch_io_under_test", SCRATCH_IO_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _square(x0, y0, size=5.0):
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)])


def _write_heads_gpkg(path: Path, heads):
    """Two 5x5 m cells (25 m² each) in EPSG:2056 with given head values."""
    gdf = gpd.GeoDataFrame(
        {
            "cellid": ["0_0", "0_1"],
            "row": [0, 0],
            "col": [0, 1],
            "head_m": heads,
        },
        geometry=[_square(2683000, 1248000), _square(2683005, 1248000)],
        crs="EPSG:2056",
    )
    gdf.to_file(path, driver="GPKG")


@pytest.fixture()
def exports_dir(tmp_path) -> Path:
    """Build a complete, tiny synthetic exports/ bundle."""
    ex = tmp_path / "group_test" / "exports"
    ex.mkdir(parents=True)

    _write_heads_gpkg(ex / "flow_heads_sub_base.gpkg", [100.0, 100.0])
    _write_heads_gpkg(ex / "flow_heads_sub_wells.gpkg", [99.0, 100.0])
    _write_heads_gpkg(ex / "flow_heads_sub_scenario.gpkg", [98.5, 99.5])

    pd.DataFrame(
        {
            "model": ["sub_base", "sub_base", "sub_wells", "sub_wells"],
            "term": ["RECHARGE", "RIVER_LEAKAGE", "WELLS", "RIVER_LEAKAGE"],
            "flow_in_m3_d": [500.0, 200.0, 0.0, 350.0],
            "flow_out_m3_d": [0.0, 150.0, 1200.0, 100.0],
        }
    ).to_csv(ex / "flow_budget_summary.csv", index=False)

    pd.DataFrame(
        {"time_days": [0.0, 10.0, 20.0], "concentration_mg_L": [0.0, 5.0, 2.0]}
    ).to_csv(ex / "transport_breakthrough.csv", index=False)

    with open(ex / "transport_meta.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "group_number": 0,
                "contaminant": "TCE",
                "threshold_mg_L": 1.0,
                "peak_mg_L": 5.0,
                "t_peak_days": 10.0,
            },
            fh,
        )

    with open(ex / "run_info.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "schema_version": "1.0",
                "group_number": 0,
                "crs": "EPSG:2056",
                "exports": {
                    "flow_heads_sub_base.gpkg": {"present": True},
                    "flow_heads_sub_wells.gpkg": {"present": True},
                },
            },
            fh,
        )
    return ex


# --- find_exports -----------------------------------------------------------
def test_find_exports_from_group_folder(scratch_io, exports_dir):
    group_folder = exports_dir.parent  # notebook opened next to exports/
    assert scratch_io.find_exports(start=group_folder) == exports_dir


def test_find_exports_from_inside_exports(scratch_io, exports_dir):
    assert scratch_io.find_exports(start=exports_dir) == exports_dir


def test_find_exports_shallow_zip_layout(scratch_io, exports_dir, tmp_path):
    # Simulate: notebook extracted one level above the group folder.
    assert scratch_io.find_exports(start=tmp_path) == exports_dir


def test_find_exports_missing_raises(scratch_io, tmp_path):
    empty = tmp_path / "nothing_here"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        scratch_io.find_exports(start=empty)


# --- provenance / schema ----------------------------------------------------
def test_load_run_info_and_schema(scratch_io, exports_dir):
    info = scratch_io.load_run_info(exports_dir)
    assert info["group_number"] == 0
    assert scratch_io.check_schema(info) is True


def test_check_schema_rejects_major_mismatch(scratch_io):
    with pytest.raises(ValueError):
        scratch_io.check_schema({"schema_version": "2.0", "group_number": 0, "crs": "x", "exports": {}})


def test_check_schema_rejects_missing_keys(scratch_io):
    with pytest.raises(ValueError):
        scratch_io.check_schema({"schema_version": "1.0"})


def test_available_exports_flags_presence(scratch_io, exports_dir):
    avail = scratch_io.available_exports(exports_dir)
    assert avail["flow_heads_base"] is not None
    assert avail["transport_breakthrough"] is not None
    assert avail["pathlines"] is None  # not written in the fixture


# --- heads / drawdown -------------------------------------------------------
def test_load_heads_gpkg(scratch_io, exports_dir):
    gdf = scratch_io.load_heads_gpkg("base", exports_dir)
    assert list(gdf["cellid"]) == ["0_0", "0_1"]
    assert gdf.crs.to_epsg() == 2056


def test_load_heads_gpkg_bad_which(scratch_io, exports_dir):
    with pytest.raises(ValueError):
        scratch_io.load_heads_gpkg("nope", exports_dir)


def test_compute_drawdown_and_affected_area(scratch_io, exports_dir):
    base = scratch_io.load_heads_gpkg("base", exports_dir)
    wells = scratch_io.load_heads_gpkg("wells", exports_dir)
    dd = scratch_io.compute_drawdown(base, wells)
    # cell 0_0: 100 - 99 = 1 m ; cell 0_1: 100 - 100 = 0 m
    dd_by_cell = dict(zip(dd["cellid"], dd["drawdown_m"]))
    assert dd_by_cell["0_0"] == pytest.approx(1.0)
    assert dd_by_cell["0_1"] == pytest.approx(0.0)
    # only cell 0_0 exceeds 0.5 m -> one 5x5 m cell = 25 m²
    area = scratch_io.affected_area(dd, threshold=0.5)
    assert area == pytest.approx(25.0)


def test_affected_area_none_above_threshold(scratch_io, exports_dir):
    base = scratch_io.load_heads_gpkg("base", exports_dir)
    dd = scratch_io.compute_drawdown(base, base)  # zero drawdown everywhere
    assert scratch_io.affected_area(dd, threshold=0.5) == 0.0


# --- budget -----------------------------------------------------------------
def test_load_budget_and_river_exchange(scratch_io, exports_dir):
    budget = scratch_io.load_budget_summary(exports_dir)
    assert "net_m3_d" in budget.columns
    riv = scratch_io.river_exchange(budget)
    riv_by_model = dict(zip(riv["model"], riv["net_m3_d"]))
    # sub_base river: in 200 - out 150 = +50 ; sub_wells: 350 - 100 = +250
    assert riv_by_model["sub_base"] == pytest.approx(50.0)
    assert riv_by_model["sub_wells"] == pytest.approx(250.0)


def test_river_exchange_empty_when_no_river(scratch_io):
    df = pd.DataFrame(
        {"model": ["m"], "term": ["WELLS"], "flow_in_m3_d": [0.0], "flow_out_m3_d": [1.0]}
    )
    assert scratch_io.river_exchange(df).empty


# --- transport --------------------------------------------------------------
def test_load_transport(scratch_io, exports_dir):
    bt = scratch_io.load_transport_breakthrough(exports_dir)
    assert list(bt.columns) == ["time_days", "concentration_mg_L"]
    meta = scratch_io.load_transport_meta(exports_dir)
    assert meta["contaminant"] == "TCE"


def test_missing_optional_transport_raises(scratch_io, tmp_path):
    ex = tmp_path / "exports"
    ex.mkdir()
    with pytest.raises(FileNotFoundError):
        scratch_io.load_transport_breakthrough(ex)


def test_missing_pathlines_raises(scratch_io, exports_dir):
    with pytest.raises(FileNotFoundError):
        scratch_io.load_pathlines_summary(exports_dir)


# --- environment guard ------------------------------------------------------
def test_assert_no_flopy_passes_when_absent(scratch_io, monkeypatch):
    monkeypatch.delitem(sys.modules, "flopy", raising=False)
    monkeypatch.delitem(sys.modules, "pyemu", raising=False)
    scratch_io.assert_no_flopy()  # should not raise


def test_assert_no_flopy_raises_when_present(scratch_io, monkeypatch):
    import types

    monkeypatch.setitem(sys.modules, "flopy", types.ModuleType("flopy"))
    with pytest.raises(RuntimeError):
        scratch_io.assert_no_flopy()
