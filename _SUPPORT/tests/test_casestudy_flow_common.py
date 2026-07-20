"""
Tests for `casestudy_flow_common` — the shared M2a flow-build primitives +
the NEUTRAL flow-package factory (M2a.1 refactor of casestudy_flow_golden).

Cheap/pure tests (no mf6 solve): the canonical-hash helper reproduces the
COMMITTED golden's hashes; the neutral factory builds the exact steady
single-layer DISV package set with EXPLICIT controls and NO transport
defaults (same packages whether called for flow or a later transport-coupled
doublet call); WEL primitives; grep gate for legacy strings.

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_common.py -v
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import model_io_utils as mio  # noqa: E402
import casestudy_flow_common as cfc  # noqa: E402

GOLDEN_DIR = SRC_DIR / "golden"


# --- synthetic ragged DISV spec (triangle + two quads) ----------------------
_VERTICES = [
    [0, 0.0, 0.0], [1, 10.0, 0.0], [2, 20.0, 0.0],
    [3, 0.0, 10.0], [4, 10.0, 10.0], [5, 20.0, 10.0],
]
_CELL2D = [
    [0, 3.0, 6.0, 3, 3, 0, 4],
    [1, 5.0, 5.0, 4, 0, 1, 4, 3],
    [2, 15.0, 5.0, 4, 1, 2, 5, 4],
]
_NCPL = 3


def make_spec(**overrides):
    spec = {
        "gridprops": {"nvert": 6, "vertices": [list(v) for v in _VERTICES],
                      "cell2d": [list(c) for c in _CELL2D], "ncpl": _NCPL},
        "ncpl": _NCPL,
        "top": np.array([10.0, 10.0, 10.0]),
        "botm": np.array([0.0, 0.0, 0.0]),
        "k": np.array([7.5, 3.25, 12.0]),
        "rch": np.array([1e-4, 1e-4, 1e-4]),
        "strt": np.array([8.0, 8.5, 9.0]),
        "idomain": np.ones(_NCPL, dtype=int),
        "chd_cellid": [(0, 0), (0, 2)], "chd_head": [8.0, 9.0],
        "riv_cellid": [(0, 1)], "riv_stage": [7.5], "riv_cond": [50.0], "riv_rbot": [6.0],
        "wel_cellid": [(0, 1)], "wel_rate": [-30.0], "well_cells": [1],
        "refine_radius_used": 70.0, "crs": "EPSG:2056",
    }
    spec.update(overrides)
    return spec


# =============================================================================
# Canonical-hash helper reproduces the COMMITTED golden's hashes.
# =============================================================================
class TestSpecCanonicalHashes:
    def test_reproduces_committed_aggregate_and_array_hashes(self):
        spec = mio.load_flow_spec(GOLDEN_DIR / "group0_flow.npz")
        agg, arr = cfc.spec_canonical_hashes(spec)
        manifest = json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())
        assert agg == manifest["aggregate_hash"]
        assert arr == manifest["array_hashes"]

    def test_hash_changes_when_a_package_array_changes(self):
        a, _ = cfc.spec_canonical_hashes(make_spec())
        b, _ = cfc.spec_canonical_hashes(make_spec(k=np.array([7.5, 3.25, 999.0])))
        assert a != b

    def test_deterministic(self):
        assert cfc.spec_canonical_hashes(make_spec())[0] == cfc.spec_canonical_hashes(make_spec())[0]


# =============================================================================
# WEL primitives.
# =============================================================================
class TestWelPrimitives:
    def test_canonicalize_sums_duplicates_and_sorts(self):
        cid, rate = cfc.canonicalize_wel_entries([(0, 1), (0, 2), (0, 1)], [10.0, 5.0, -3.0])
        assert cid == [(0, 1), (0, 2)]
        assert rate == [7.0, 5.0]

    def test_canonicalize_is_order_independent_bitwise(self):
        """Finding 5: summing with math.fsum over sorted keys makes the result
        order-independent to the last bit (not just approximately)."""
        cellid = [(0, 1), (0, 2), (0, 1), (0, 0), (0, 1)]
        rate = [0.1, 0.2, 0.3, 0.4, 0.5]
        import random
        base = cfc.canonicalize_wel_entries(cellid, rate)
        for _ in range(5):
            order = list(range(len(cellid)))
            random.shuffle(order)
            c2, r2 = cfc.canonicalize_wel_entries(
                [cellid[i] for i in order], [rate[i] for i in order],
            )
            assert c2 == base[0]
            # bitwise-identical rates regardless of input order
            assert [r.hex() for r in r2] == [r.hex() for r in base[1]]

    def test_baseline_well_data_sign_preserved(self):
        class _SPD:
            def get_data(self, per):
                return [{"cellid": (0, 0), "q": 26.0}, {"cellid": (0, 1), "q": -540.0}]
        gwf = SimpleNamespace(
            get_package=lambda n: SimpleNamespace(stress_period_data=_SPD()) if n == "WEL" else None,
            modelgrid=SimpleNamespace(xcellcenters=np.array([0.0, 10.0]),
                                      ycellcenters=np.array([0.0, 10.0])),
        )
        assert cfc.baseline_well_data(gwf) == [(0.0, 0.0, 26.0), (10.0, 10.0, -540.0)]


# =============================================================================
# NEUTRAL flow-package factory contract.
# =============================================================================
class TestAssembleFlowStateNeutralFactory:
    def _package_types(self, gwf):
        # normalize flopy package names to their type (drop the _N suffix)
        return sorted({p.package_type.upper() for p in gwf.packagelist})

    def test_builds_steady_single_layer_disv_packages(self, tmp_path):
        built = cfc.assemble_flow_state(
            make_spec(), workspace=tmp_path / "ws", sim_name="flow_x", run=False,
        )
        gwf = built["gwf"]
        types = self._package_types(gwf)
        assert "DISV" in types and "NPF" in types and "IC" in types
        assert "RCHA" in types and "CHD" in types and "RIV" in types and "WEL" in types and "OC" in types
        assert "STO" not in types, "steady flow must have NO STO package"
        # steady single period
        tdis = built["sim"].get_package("tdis")
        assert int(tdis.nper.get_data()) == 1
        # single layer
        assert int(gwf.get_package("DISV").nlay.get_data()) == 1

    def test_same_packages_flow_vs_transport_coupled_doublet_call(self, tmp_path):
        """The factory yields the SAME package TYPES whether called for the
        baseline flow (no extra wells) or a later transport-coupled call that
        injects the doublet via extra_wells -- the doublet only ADDS WEL
        entries, never new/transport packages."""
        flow = cfc.assemble_flow_state(
            make_spec(), workspace=tmp_path / "flow", sim_name="flow", run=False,
        )
        coupled = cfc.assemble_flow_state(
            make_spec(), workspace=tmp_path / "coupled", sim_name="coupled", run=False,
            extra_wells=[((0, 2), +4320.0), ((0, 1), -4320.0)],  # inj +Q / ext -Q
        )
        assert self._package_types(flow["gwf"]) == self._package_types(coupled["gwf"])

    def test_extra_wells_are_appended_to_background_wel(self, tmp_path):
        built = cfc.assemble_flow_state(
            make_spec(), workspace=tmp_path / "ws", sim_name="f", run=False,
            extra_wells=[((0, 2), +4320.0)],  # distinct cell from background (0,1)
        )
        wel = built["gwf"].get_package("WEL")
        spd = wel.stress_period_data.get_data(0)
        # background (1) + doublet (1) = 2 WEL entries; well_cells reflects both
        assert len(spd) == 2
        rates = sorted(float(r["q"]) for r in spd)
        assert rates == [-30.0, 4320.0]
        assert sorted(built["well_cells"]) == [1, 2]

    def test_extra_wells_coincident_cell_is_canonicalized_summed(self, tmp_path):
        """Finding 2: an extra (doublet) well that lands on a BACKGROUND cell
        is SUMMED into a single WEL entry (what MF6 does anyway), and the
        returned well_cells / wel_rate reflect the combined WEL -- not a
        silent duplicate the metadata/hash misses."""
        # background WEL is on cell (0,1) rate -30; add an injection +100 on the
        # SAME cell -> one entry rate 70.
        built = cfc.assemble_flow_state(
            make_spec(), workspace=tmp_path / "ws", sim_name="f", run=False,
            extra_wells=[((0, 1), +100.0)],
        )
        wel = built["gwf"].get_package("WEL")
        spd = wel.stress_period_data.get_data(0)
        assert len(spd) == 1, "coincident doublet+background cell must be one summed entry"
        assert float(spd[0]["q"]) == pytest.approx(70.0)
        assert built["well_cells"] == [1]
        assert built["wel_rate"] == [pytest.approx(70.0)]

    def test_baseline_extra_wells_none_leaves_spec_wel_untouched(self, tmp_path):
        spec = make_spec()
        built = cfc.assemble_flow_state(
            spec, workspace=tmp_path / "ws", sim_name="f", run=False,
        )
        assert built["wel_cellid"] == list(spec["wel_cellid"])
        assert built["wel_rate"] == list(spec["wel_rate"])
        assert built["well_cells"] == spec["well_cells"]

    def test_raise_on_failure_default_raises_when_solve_fails(self, tmp_path, monkeypatch):
        """Finding 1: assemble_flow_state raises on non-convergence by default
        (matching the former assemble_gwf_from_spec fail-loud behaviour that
        the golden generator relies on)."""
        import flopy
        monkeypatch.setattr(flopy.mf6.MFSimulation, "run_simulation", lambda self, *a, **k: (False, []))
        with pytest.raises(RuntimeError, match="(?i)converge"):
            cfc.assemble_flow_state(make_spec(), workspace=tmp_path / "ws", sim_name="f")

    def test_raise_on_failure_false_returns_converged_false(self, tmp_path, monkeypatch):
        import flopy
        monkeypatch.setattr(flopy.mf6.MFSimulation, "run_simulation", lambda self, *a, **k: (False, []))
        built = cfc.assemble_flow_state(
            make_spec(), workspace=tmp_path / "ws", sim_name="f", raise_on_failure=False,
        )
        assert built["converged"] is False
        assert built["heads"] is None

    def test_explicit_oc_filenames_and_model_name(self, tmp_path):
        built = cfc.assemble_flow_state(
            make_spec(), workspace=tmp_path / "ws", sim_name="sim_a",
            model_name="mymodel", head_filename="h.hds", budget_filename="b.cbc", run=False,
        )
        assert built["model_name"] == "mymodel"
        assert built["headfile"].endswith("h.hds")
        assert built["budgetfile"].endswith("b.cbc")
        # model files written under the model name
        written = {p.name for p in (tmp_path / "ws").glob("*")}
        assert "mymodel.disv" in written

    def test_source_has_no_sto_and_no_transport_packages(self):
        src = inspect.getsource(cfc.assemble_flow_state)
        for forbidden in ("ModflowGwfsto", "ModflowGwt", "ModflowGwtgwt", "adv", "dsp", "mst"):
            assert f"{forbidden}(" not in src, f"neutral flow factory must not build {forbidden}"


# =============================================================================
# M2a.2 — well-placement + WEL-budget primitives (synthetic grids, no mf6).
# =============================================================================
def _quad_spec(nx, ny, dx=10.0, x0=0.0, y0=0.0, idomain=None, chd=None, riv=None):
    """A regular nx*ny grid of dx-square cells as a minimal flow spec + a fake
    modelgrid (xcellcenters/ycellcenters). Cell index = j*nx + i."""
    vid, vertices, k = {}, [], 0
    for j in range(ny + 1):
        for i in range(nx + 1):
            vid[(i, j)] = k
            vertices.append([k, x0 + i * dx, y0 + j * dx])
            k += 1
    cell2d, xc, yc = [], [], []
    ic = 0
    for j in range(ny):
        for i in range(nx):
            bl, br, tr, tl = vid[(i, j)], vid[(i + 1, j)], vid[(i + 1, j + 1)], vid[(i, j + 1)]
            cx, cy = x0 + (i + 0.5) * dx, y0 + (j + 0.5) * dx
            cell2d.append([ic, cx, cy, 4, bl, br, tr, tl])
            xc.append(cx); yc.append(cy); ic += 1
    ncpl = nx * ny
    spec = {
        "gridprops": {"nvert": len(vertices), "vertices": vertices, "cell2d": cell2d, "ncpl": ncpl},
        "ncpl": ncpl,
        "idomain": np.ones(ncpl, dtype=int) if idomain is None else np.asarray(idomain),
        "chd_cellid": chd or [], "riv_cellid": riv or [],
    }
    mg = SimpleNamespace(xcellcenters=np.array(xc), ycellcenters=np.array(yc))
    return spec, mg


class TestResolveWellCell:
    def test_nearest_cell(self):
        spec, mg = _quad_spec(3, 1, dx=10.0)  # centroids x=5,15,25
        assert cfc.resolve_well_cell(16.0, 5.0, mg, spec["idomain"]) == 1
        assert cfc.resolve_well_cell(4.0, 5.0, mg, spec["idomain"]) == 0

    def test_requires_all_active_idomain(self):
        # Finding 2: the mapper equals generate_refined_grid's UNMASKED
        # nearest-centroid ONLY on an all-active grid -> require it (a checked
        # precondition, not a happens-to-hold claim).
        spec, mg = _quad_spec(3, 1, dx=10.0, idomain=[1, 0, 1])
        with pytest.raises(ValueError, match="(?i)all-active|inactive"):
            cfc.resolve_well_cell(15.0, 5.0, mg, spec["idomain"])


class TestResolveDoubletCells:
    def _points(self, spec, mg, a, b):
        return [(mg.xcellcenters[a], mg.ycellcenters[a]), (mg.xcellcenters[b], mg.ycellcenters[b])]

    def test_happy_path_fine_corridor(self):
        spec, mg = _quad_spec(4, 4, dx=10.0)  # cellsize 10 < 30 (fine)
        pts = self._points(spec, mg, 5, 10)
        out = cfc.resolve_doublet_cells(spec, mg, pts)
        assert out["injection"]["cell"] == 5
        assert out["extraction"]["cell"] == 10
        assert out["injection"]["cellsize_m"] == pytest.approx(10.0)

    def test_rejects_non_all_active_idomain(self):
        # Finding 2: any inactive cell in the refined grid breaks the "same
        # mapper as background wells" precondition -> reject up front.
        spec, mg = _quad_spec(4, 4, dx=10.0, idomain=None)
        spec["idomain"][7] = 0
        pts = self._points(spec, mg, 5, 10)
        with pytest.raises(ValueError, match="(?i)all-active|inactive"):
            cfc.resolve_doublet_cells(spec, mg, pts)

    def test_rejects_on_edge_ambiguous_containing(self):
        # Finding 1: a point exactly on a shared cell edge is COVERED by two
        # cells (containing has 2) -> a placement ambiguity that must FAIL, not
        # silently resolve to one side.
        spec, mg = _quad_spec(3, 1, dx=10.0)  # cells 0:[0,10], 1:[10,20], 2:[20,30]
        # (10, 5) sits on the vertical edge shared by cell 0 and cell 1
        pts = [(10.0, 5.0), (mg.xcellcenters[2], mg.ycellcenters[2])]
        with pytest.raises(ValueError, match="(?i)ambigu|containing"):
            cfc.resolve_doublet_cells(spec, mg, pts)

    def test_rejects_chd_cell(self):
        spec, mg = _quad_spec(4, 4, dx=10.0, chd=[(0, 5)])
        pts = self._points(spec, mg, 5, 10)
        with pytest.raises(ValueError, match="(?i)CHD"):
            cfc.resolve_doublet_cells(spec, mg, pts)

    def test_rejects_riv_cell(self):
        spec, mg = _quad_spec(4, 4, dx=10.0, riv=[(0, 10)])
        pts = self._points(spec, mg, 5, 10)
        with pytest.raises(ValueError, match="(?i)RIV"):
            cfc.resolve_doublet_cells(spec, mg, pts)

    def test_rejects_coarse_cell_not_in_fine_corridor(self):
        spec, mg = _quad_spec(4, 4, dx=50.0)  # cellsize 50 >= 30
        pts = self._points(spec, mg, 5, 10)
        with pytest.raises(ValueError, match="(?i)corridor|fine"):
            cfc.resolve_doublet_cells(spec, mg, pts)

    def test_rejects_placement_ambiguity_point_outside_grid(self):
        spec, mg = _quad_spec(4, 4, dx=10.0)
        # a point far outside the grid: nearest-active exists but no cell CONTAINS it
        pts = [(1000.0, 1000.0), (mg.xcellcenters[10], mg.ycellcenters[10])]
        with pytest.raises(ValueError, match="(?i)ambigu|contain"):
            cfc.resolve_doublet_cells(spec, mg, pts)


class TestWelFluxByCell:
    def test_sums_q_per_cell_from_1based_node(self):
        rec = np.array([(1, 1, 10.0), (11, 2, -540.0), (11, 3, 5.0)],
                       dtype=[("node", int), ("node2", int), ("q", float)])

        class _Bud:
            def get_times(self): return [1.0]
            def get_data(self, text, totim): return [rec]

        gwf = SimpleNamespace(output=SimpleNamespace(budget=lambda: _Bud()))
        flux = cfc.wel_flux_by_cell(gwf)
        assert flux[0] == pytest.approx(10.0)   # node 1 -> icell 0
        assert flux[10] == pytest.approx(-535.0)  # node 11 -> icell 10, summed


# =============================================================================
# Finding 1: the case-study path uses ONE assembler (assemble_flow_state);
# the generator no longer calls model_io_utils.assemble_gwf_from_spec.
# =============================================================================
def test_case_study_path_uses_single_assembler():
    for mod in ("casestudy_flow_golden.py", "casestudy_flow_builder.py"):
        src = (SRC_DIR / mod).read_text()
        # no CALL to the old assembler (a docstring MENTION with no '(' is fine)
        assert "assemble_gwf_from_spec(" not in src, (
            f"{mod} must use cfc.assemble_flow_state, not "
            "model_io_utils.assemble_gwf_from_spec (single case-study assembler)"
        )
        assert "assemble_flow_state" in src


# =============================================================================
# Grep gate: no legacy-MODFLOW/NWT/telescope strings (M1.5 legacy_modflow_nwt).
# =============================================================================
def test_grep_gate_no_legacy_strings():
    low = (SRC_DIR / "casestudy_flow_common.py").read_text().lower()
    assert "nwt" not in low
    assert "modflow-nwt" not in low
    assert "telescop" not in low
