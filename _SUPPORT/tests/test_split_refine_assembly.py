"""
Acceptance tests for milestone M2-split-refine.

The refactor splits ``build_refined_gwf_model`` (model_io_utils.py) into:

* ``generate_refined_grid(...)``  — instructor-only: Triangle/Voronoi grid
  generation (disv_grid_utils) + NearestND property interpolation +
  CHD/RIV/WEL spatial reassignment, returning a plain numpy "assembly spec"
  (no live MF6 objects, no solve).
* ``assemble_gwf_from_spec(...)`` — shared / student path: builds an MF6 GWF
  simulation purely from the frozen spec arrays; contains NO Triangle/Voronoi,
  NO NearestND, NO point-in-polygon reassignment.
* ``build_refined_gwf_model(...)`` — unchanged public signature/return keys,
  now == generate_refined_grid followed by assemble_gwf_from_spec.

LOCKED-TEST SCOPING (see milestone brief): these tests MUST NOT run real
Triangle/Voronoi refinement and MUST NOT run MODFLOW. Real refinement is
stubbed; MODFLOW solves are intercepted; only ``write_simulation`` (write, no
run) is exercised. End-to-end numeric equivalence is validated later on
JupyterHub, not here.

Run with:  uv run pytest _SUPPORT/tests/test_split_refine_assembly.py -v
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import geopandas as gpd
import pytest
from shapely.geometry import Polygon

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import model_io_utils as mio  # noqa: E402
import disv_grid_utils as dgu  # noqa: E402


# =============================================================================
# Synthetic tiny DISV geometry (2x2 grid of 10 m cells over a 20x20 m domain).
# No Triangle/Voronoi involved — hand-built so the locked gate is SIGILL-free.
# =============================================================================
_VERTICES = [
    [0, 0.0, 20.0], [1, 10.0, 20.0], [2, 20.0, 20.0],
    [3, 0.0, 10.0], [4, 10.0, 10.0], [5, 20.0, 10.0],
    [6, 0.0, 0.0], [7, 10.0, 0.0], [8, 20.0, 0.0],
]
_CELL2D = [
    [0, 5.0, 15.0, 4, 0, 1, 4, 3],   # top-left
    [1, 15.0, 15.0, 4, 1, 2, 5, 4],  # top-right
    [2, 5.0, 5.0, 4, 3, 4, 7, 6],    # bottom-left
    [3, 15.0, 5.0, 4, 4, 5, 8, 7],   # bottom-right
]
_NCPL = 4


def _gridprops():
    return {
        "nvert": 9,
        "vertices": [list(v) for v in _VERTICES],
        "cell2d": [list(c) for c in _CELL2D],
        "ncpl": _NCPL,
    }


def _contains(values, expected):
    """True if *expected* was threaded through (identity first, then equality).

    Robust to numpy arrays and to sentinel ``object()`` values whose ``==``
    returns ``NotImplemented``.  Used to assert that build_refined_gwf_model
    forwards a given argument to a delegate without pinning positional vs.
    keyword calling convention.
    """
    for v in values:
        if v is expected:
            return True
    for v in values:
        try:
            if isinstance(v, np.ndarray) or isinstance(expected, np.ndarray):
                if np.array_equal(v, expected):
                    return True
            elif v == expected:
                return True
        except Exception:
            pass
    return False


def _build_coarse_gwf(tmp_path):
    """A real (but never-run) MF6 DISV GWF model to feed generate_refined_grid.

    Building flopy objects in memory is fast and SIGILL-free; only real
    Triangle/Voronoi refinement and MODFLOW solves are dangerous, and neither
    happens here.
    """
    import flopy

    ncpl = _NCPL
    sim = flopy.mf6.MFSimulation(
        sim_name="coarse", exe_name="mf6", sim_ws=str(tmp_path / "coarse")
    )
    flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1)])
    flopy.mf6.ModflowIms(sim)
    gwf = flopy.mf6.ModflowGwf(sim, modelname="coarse")
    flopy.mf6.ModflowGwfdisv(
        gwf, nlay=1, ncpl=ncpl, nvert=9,
        top=np.full(ncpl, 20.0), botm=[np.zeros(ncpl)],
        vertices=_VERTICES, cell2d=_CELL2D,
        idomain=np.ones((1, ncpl), dtype=int),
    )
    flopy.mf6.ModflowGwfnpf(gwf, k=np.full(ncpl, 10.0), icelltype=1)
    flopy.mf6.ModflowGwfic(gwf, strt=np.full(ncpl, 15.0))
    flopy.mf6.ModflowGwfrcha(gwf, recharge=1e-4)
    # CHD on the two top cells; RIV on a bottom cell.
    flopy.mf6.ModflowGwfchd(
        gwf, stress_period_data=[((0, 0), 15.0), ((0, 1), 15.0)]
    )
    flopy.mf6.ModflowGwfriv(
        gwf, stress_period_data=[((0, 2), 14.0, 100.0, 12.0)]
    )
    return gwf


def _domain_gdf():
    return gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])],
        crs="EPSG:2056",
    )


def _river_gdf():
    # Covers the bottom band (y in [0, 10]) -> refined cells 2 & 3 fall inside.
    return gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])],
        crs="EPSG:2056",
    )


class _StubNN:
    """Cheap stand-in for scipy.interpolate.NearestNDInterpolator.

    Accepts (points, values) and, when called with either arrays or scalars,
    returns a constant broadcast of the first value. Enough to exercise the
    property-interpolation code path without scipy.
    """

    def __init__(self, points, values, *a, **k):
        vals = np.asarray(values, dtype=float).ravel()
        self._val = float(vals[0]) if vals.size else 0.0

    def __call__(self, x, y=None):
        return np.full(np.shape(x), self._val, dtype=float)


def _stub_refinement(monkeypatch):
    """Patch Triangle/Voronoi generation + scipy NearestND to cheap stubs.

    The refined grid reuses the same tiny hand-built 2x2 mesh (a real
    VertexGrid so ``xcellcenters`` / ``get_cell_vertices`` behave), but NO
    Triangle/Voronoi code runs.
    """
    from flopy.discretization import VertexGrid

    called = {"create": 0, "refine": 0, "nn": 0}

    def fake_create(*a, **k):
        called["create"] += 1
        return {"disv_gridprops": _gridprops(), "ncpl": _NCPL}

    def fake_refine(*a, **k):
        called["refine"] += 1
        mg = VertexGrid(
            vertices=_VERTICES, cell2d=_CELL2D, ncpl=_NCPL, nlay=1,
            top=np.full(_NCPL, 20.0), botm=np.zeros((1, _NCPL)),
        )
        return {"disv_gridprops": _gridprops(), "ncpl": _NCPL, "modelgrid": mg}

    class _CountingNN(_StubNN):
        def __init__(self, *a, **k):
            called["nn"] += 1
            super().__init__(*a, **k)

    monkeypatch.setattr(dgu, "create_disv_from_boundary", fake_create)
    monkeypatch.setattr(dgu, "refine_grid_locally", fake_refine)
    import scipy.interpolate
    monkeypatch.setattr(
        scipy.interpolate, "NearestNDInterpolator", _CountingNN
    )
    # Belt-and-suspenders if the implementation imports the symbol at module top.
    monkeypatch.setattr(
        mio, "NearestNDInterpolator", _CountingNN, raising=False
    )
    return called


_SPEC_ARRAY_KEYS = ["top", "botm", "k", "rch", "strt", "idomain"]
_REQUIRED_SPEC_KEYS = [
    "gridprops", "ncpl",
    "top", "botm", "k", "rch", "strt", "idomain",
    "chd_cellid", "chd_head",
    "riv_cellid", "riv_stage", "riv_cond", "riv_rbot",
    "wel_cellid", "wel_rate", "well_cells",
    "refine_radius_used",
]


# =============================================================================
# Presence of the new public API
# =============================================================================
class TestNewPublicApiExists:
    def test_generate_refined_grid_exists(self):
        assert hasattr(mio, "generate_refined_grid")
        assert callable(mio.generate_refined_grid)

    def test_assemble_gwf_from_spec_exists(self):
        assert hasattr(mio, "assemble_gwf_from_spec")
        assert callable(mio.assemble_gwf_from_spec)


# =============================================================================
# Criterion 1: generate_refined_grid produces a complete numpy assembly spec.
# =============================================================================
class TestGenerateRefinedGridSpec:

    def _generate(self, monkeypatch, tmp_path, well_data):
        called = _stub_refinement(monkeypatch)
        # NO solve may happen inside generate_refined_grid.
        import flopy
        monkeypatch.setattr(
            flopy.mf6.MFSimulation, "run_simulation",
            lambda self, *a, **k: (_ for _ in ()).throw(
                AssertionError("generate_refined_grid must not run MODFLOW")
            ),
        )
        gwf = _build_coarse_gwf(tmp_path)
        spec = mio.generate_refined_grid(
            gwf,
            _domain_gdf(),
            _river_gdf(),
            [(5.0, 5.0)],
            np.full(_NCPL, 15.0),
            refine_radius=150.0,
            base_cell_size=50.0,
            refined_cell_size=10.0,
            well_data=well_data,
        )
        return spec, called

    def test_returns_all_required_keys(self, monkeypatch, tmp_path):
        spec, _ = self._generate(monkeypatch, tmp_path, [(15.0, 5.0, -50.0)])
        assert isinstance(spec, dict)
        missing = [k for k in _REQUIRED_SPEC_KEYS if k not in spec]
        assert not missing, f"spec missing keys: {missing}"

    def test_no_live_mf6_objects_or_solve(self, monkeypatch, tmp_path):
        # run_simulation is patched to raise; reaching here proves no solve.
        spec, _ = self._generate(monkeypatch, tmp_path, [(15.0, 5.0, -50.0)])
        assert "sim" not in spec, "spec must not carry a live MFSimulation"
        assert "gwf" not in spec, "spec must not carry a live ModflowGwf"

    def test_grid_generation_and_interpolation_are_invoked(
        self, monkeypatch, tmp_path
    ):
        # Proves generate_refined_grid CONTAINS grid-gen + NearestND (not that
        # they were removed to the assemble half).
        _, called = self._generate(monkeypatch, tmp_path, [(15.0, 5.0, -50.0)])
        assert called["create"] >= 1, "did not call create_disv_from_boundary"
        assert called["refine"] >= 1, "did not call refine_grid_locally"
        assert called["nn"] >= 1, "did not use NearestNDInterpolator"

    def test_property_arrays_are_numpy_and_cell_length(
        self, monkeypatch, tmp_path
    ):
        spec, _ = self._generate(monkeypatch, tmp_path, [(15.0, 5.0, -50.0)])
        ncpl = int(spec["ncpl"])
        for key in _SPEC_ARRAY_KEYS:
            arr = np.asarray(spec[key])
            assert arr.shape[-1] == ncpl or arr.size == ncpl, (
                f"spec['{key}'] length {arr.size} != ncpl {ncpl}"
            )

    def test_idomain_is_new_explicit_all_active(self, monkeypatch, tmp_path):
        # Newly surfaced: the old return value had no idomain.
        spec, _ = self._generate(monkeypatch, tmp_path, [(15.0, 5.0, -50.0)])
        idom = np.asarray(spec["idomain"])
        assert idom.size == int(spec["ncpl"])
        assert np.all(idom >= 1), "idomain must be explicit all-active"

    def test_refine_radius_used_is_surfaced(self, monkeypatch, tmp_path):
        # Newly surfaced: not in the pre-refactor return value.
        spec, _ = self._generate(monkeypatch, tmp_path, [(15.0, 5.0, -50.0)])
        assert float(spec["refine_radius_used"]) == pytest.approx(150.0)

    def test_reassignment_records_are_mutually_consistent(
        self, monkeypatch, tmp_path
    ):
        spec, _ = self._generate(monkeypatch, tmp_path, [(15.0, 5.0, -50.0)])
        # CHD: nearest-within-radius reassignment produced records.
        assert len(spec["chd_cellid"]) == len(spec["chd_head"])
        assert len(spec["chd_cellid"]) >= 1, "CHD reassignment produced nothing"
        # RIV: point-in-polygon reassignment produced records.
        assert (
            len(spec["riv_cellid"]) == len(spec["riv_stage"])
            == len(spec["riv_cond"]) == len(spec["riv_rbot"])
        )
        assert len(spec["riv_cellid"]) >= 1, "RIV reassignment produced nothing"
        # WEL: argmin reassignment produced one record per well.
        assert (
            len(spec["wel_cellid"]) == len(spec["wel_rate"])
            == len(spec["well_cells"]) == 1
        )

    def test_no_wells_yields_empty_but_present_wel_arrays(
        self, monkeypatch, tmp_path
    ):
        # Negative path: well_data=None must still surface the WEL spec keys.
        spec, _ = self._generate(monkeypatch, tmp_path, None)
        for key in ("wel_cellid", "wel_rate", "well_cells"):
            assert key in spec
            assert len(spec[key]) == 0


# =============================================================================
# Criterion 2 + 5: assemble_gwf_from_spec builds MF6 from frozen arrays only.
# =============================================================================
class TestAssembleGwfFromSpec:

    def _spec(self):
        ncpl = _NCPL
        return {
            "gridprops": _gridprops(),
            "ncpl": ncpl,
            "top": np.full(ncpl, 20.0),
            "botm": np.zeros(ncpl),
            "k": np.full(ncpl, 7.5),
            "rch": np.full(ncpl, 1e-4),
            "strt": np.full(ncpl, 15.0),
            "idomain": np.ones(ncpl, dtype=int),
            "chd_cellid": [(0, 0), (0, 1)],
            "chd_head": [15.0, 15.0],
            "riv_cellid": [(0, 2)],
            "riv_stage": [14.0],
            "riv_cond": [100.0],
            "riv_rbot": [12.0],
            "wel_cellid": [(0, 3)],
            "wel_rate": [-50.0],
            "well_cells": [3],
            "refine_radius_used": 150.0,
        }

    def _assemble(self, monkeypatch, tmp_path):
        """Call assemble with the MODFLOW solve intercepted (write, no run)."""
        import flopy

        state = {"ran": False, "wrote": False}
        real_write = flopy.mf6.MFSimulation.write_simulation

        def spy_write(self, *a, **k):
            state["wrote"] = True
            return real_write(self, *a, **k)

        def fake_run(self, *a, **k):
            state["ran"] = True
            return True, []

        # Fake solved-head accessor so assemble can populate 'heads' with no run.
        class _FakeHead:
            def get_data(self):
                return np.full((1, 1, _NCPL), 15.0)

        class _FakeOutput:
            def head(self, *a, **k):
                return _FakeHead()

        monkeypatch.setattr(
            flopy.mf6.MFSimulation, "write_simulation", spy_write
        )
        monkeypatch.setattr(flopy.mf6.MFSimulation, "run_simulation", fake_run)
        monkeypatch.setattr(
            flopy.mf6.ModflowGwf, "output",
            property(lambda self: _FakeOutput()), raising=False,
        )
        spec = self._spec()
        result = mio.assemble_gwf_from_spec(spec, str(tmp_path / "asm"))
        return spec, result, state

    def test_returns_expected_keys(self, monkeypatch, tmp_path):
        _, result, _ = self._assemble(monkeypatch, tmp_path)
        for key in ("sim", "gwf", "modelgrid", "gridprops", "ncpl",
                    "heads", "well_cells"):
            assert key in result, f"assemble result missing '{key}'"

    def test_write_simulation_succeeds_write_only(self, monkeypatch, tmp_path):
        _, _, state = self._assemble(monkeypatch, tmp_path)
        assert state["wrote"], "assemble must write the simulation"
        # Input files exist on disk (write happened, no run required).
        asm = tmp_path / "asm"
        written = {p.suffix for p in asm.glob("*")}
        assert ".disv" in written and ".nam" in written

    def test_packages_carry_frozen_spec_arrays(self, monkeypatch, tmp_path):
        spec, result, _ = self._assemble(monkeypatch, tmp_path)
        gwf = result["gwf"]
        assert int(result["ncpl"]) == spec["ncpl"]
        # NPF K comes straight from the frozen array.
        assert np.allclose(gwf.npf.k.array.flatten(), spec["k"])
        # DISV top from the frozen array.
        disv = gwf.get_package("DISV")
        assert np.allclose(disv.top.array.flatten(), spec["top"])

    def test_bcs_built_from_frozen_cellids(self, monkeypatch, tmp_path):
        spec, result, _ = self._assemble(monkeypatch, tmp_path)
        gwf = result["gwf"]
        chd = gwf.get_package("CHD").stress_period_data.get_data(0)
        assert [tuple(c) for c in chd["cellid"]] == spec["chd_cellid"]
        assert list(chd["head"]) == spec["chd_head"]
        riv = gwf.get_package("RIV").stress_period_data.get_data(0)
        assert [tuple(c) for c in riv["cellid"]] == spec["riv_cellid"]
        assert list(riv["stage"]) == spec["riv_stage"]
        wel = gwf.get_package("WEL").stress_period_data.get_data(0)
        assert [tuple(c) for c in wel["cellid"]] == spec["wel_cellid"]
        assert list(result["well_cells"]) == spec["well_cells"]

    def test_source_has_no_refinement_or_interpolation(self):
        # Criterion 2/5: the assemble half must not reference Triangle/Voronoi,
        # scipy NearestND, or any spatial reassignment machinery.
        src = inspect.getsource(mio.assemble_gwf_from_spec)
        for forbidden in (
            "disv_grid_utils",
            "create_disv_from_boundary",
            "refine_grid_locally",
            "NearestNDInterpolator",
        ):
            assert forbidden not in src, (
                f"assemble_gwf_from_spec must not reference {forbidden!r}"
            )


# =============================================================================
# Criterion 3: build_refined_gwf_model preserved + delegates to the split.
# =============================================================================
class TestBuildRefinedGwfModelContract:

    def test_public_signature_unchanged(self):
        sig = inspect.signature(mio.build_refined_gwf_model)
        params = list(sig.parameters.values())
        names = [p.name for p in params]
        assert names == [
            "gwf", "boundary_gdf", "river_gdf", "refine_points", "head_array",
            "workspace", "refine_radius", "base_cell_size", "refined_cell_size",
            "well_data", "sim_name", "baseline_head_array",
        ]
        defaults = {p.name: p.default for p in params}
        assert defaults["refine_radius"] == 200.0
        assert defaults["base_cell_size"] == 50.0
        assert defaults["refined_cell_size"] == 10.0
        assert defaults["well_data"] is None
        assert defaults["sim_name"] == "refined_model"
        assert defaults["baseline_head_array"] is None

    def test_delegates_generate_then_assemble(self, monkeypatch, tmp_path):
        # Implemented as generate_refined_grid followed by assemble_gwf_from_spec:
        # generate's spec must be handed verbatim to assemble, build must return
        # assemble's result, AND build's own arguments must be threaded through
        # to the delegates (not dropped or hardcoded).
        order = []
        sentinel_spec = {"_sentinel_spec": True}
        sentinel_result = {
            "sim": object(), "gwf": object(), "modelgrid": object(),
            "gridprops": _gridprops(), "ncpl": _NCPL,
            "heads": np.zeros(_NCPL), "well_cells": [3],
        }
        gen = {}
        asm = {}

        def fake_generate(*a, **k):
            order.append("generate")
            gen["args"], gen["kwargs"] = a, k
            return sentinel_spec

        def fake_assemble(spec, *a, **k):
            order.append("assemble")
            asm["spec"], asm["args"], asm["kwargs"] = spec, a, k
            return sentinel_result

        monkeypatch.setattr(mio, "generate_refined_grid", fake_generate)
        monkeypatch.setattr(mio, "assemble_gwf_from_spec", fake_assemble)

        # --- distinctive NON-default arguments: proves genuine threading ------
        s_gwf, s_boundary, s_river, s_points, s_well = (object() for _ in range(5))
        s_head = np.array([1.0, 2.0, 3.0, 4.0])
        s_baseline = np.array([9.0, 8.0])
        ws = str(tmp_path / "build_ws")

        result = mio.build_refined_gwf_model(
            gwf=s_gwf,
            boundary_gdf=s_boundary,
            river_gdf=s_river,
            refine_points=s_points,
            head_array=s_head,
            workspace=ws,
            refine_radius=201.5,
            base_cell_size=52.5,
            refined_cell_size=11.5,
            well_data=s_well,
            sim_name="my_refined",
            baseline_head_array=s_baseline,
        )

        assert order == ["generate", "assemble"], (
            "build must call generate_refined_grid then assemble_gwf_from_spec"
        )
        assert asm["spec"] is sentinel_spec, (
            "generate's spec must be forwarded verbatim to assemble"
        )
        for key in ("sim", "gwf", "modelgrid", "gridprops", "ncpl",
                    "heads", "well_cells"):
            assert result[key] is sentinel_result[key] or np.all(
                result[key] == sentinel_result[key]
            ), f"build must surface assemble's '{key}'"

        gen_vals = list(gen["args"]) + list(gen["kwargs"].values())
        asm_vals = [asm["spec"], *asm["args"], *asm["kwargs"].values()]
        all_vals = gen_vals + asm_vals

        # generate_refined_grid must receive the grid-generation inputs verbatim.
        for expected, label in (
            (s_gwf, "gwf"), (s_boundary, "boundary_gdf"), (s_river, "river_gdf"),
            (s_points, "refine_points"), (s_head, "head_array"),
            (s_well, "well_data"), (201.5, "refine_radius"),
            (52.5, "base_cell_size"), (11.5, "refined_cell_size"),
        ):
            assert _contains(gen_vals, expected), (
                f"build must forward {label} to generate_refined_grid"
            )
        # assemble_gwf_from_spec must receive workspace + sim_name verbatim.
        assert _contains(asm_vals, ws), "build must forward workspace to assemble"
        assert _contains(asm_vals, "my_refined"), (
            "build must forward sim_name to assemble"
        )
        # baseline_head_array must not be silently dropped (destination is an
        # implementation choice, so only require it reach one delegate).
        assert _contains(all_vals, s_baseline), (
            "build must forward baseline_head_array to a delegate"
        )

        # --- default call: keyword-only geom params have NO default in
        # generate_refined_grid, so build MUST forward the documented defaults
        # (catches hardcoding to a non-default value). --------------------------
        order.clear(); gen.clear(); asm.clear()
        ws2 = str(tmp_path / "build_ws2")
        mio.build_refined_gwf_model(
            gwf=object(), boundary_gdf=object(), river_gdf=object(),
            refine_points=object(), head_array=np.zeros(_NCPL), workspace=ws2,
        )
        assert order == ["generate", "assemble"]
        gen_vals2 = list(gen["args"]) + list(gen["kwargs"].values())
        asm_vals2 = [asm["spec"], *asm["args"], *asm["kwargs"].values()]
        assert _contains(gen_vals2, 200.0), "refine_radius default must forward"
        assert _contains(gen_vals2, 50.0), "base_cell_size default must forward"
        assert _contains(gen_vals2, 10.0), "refined_cell_size default must forward"
        assert _contains(asm_vals2, ws2), "workspace must forward on default call"
