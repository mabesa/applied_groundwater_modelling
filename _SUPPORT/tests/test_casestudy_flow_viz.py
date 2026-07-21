"""
Unit tests for milestone M2b.1 -- ``casestudy_flow_viz.py``.

Everything here runs on a TINY, HAND-BUILT synthetic DISV VertexGrid (3 rows x
4 cols = 12 quad cells, SIGILL-free -- no Triangle/Voronoi, no MF6 solve),
mirroring the synthetic-spec pattern in ``test_case_flow_stage.py`` /
``test_pinned_flow_loader.py``. Agg backend is forced before ``pyplot`` is
imported so plotting is headless-safe.

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_viz.py -v
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import numpy as np
import pandas as pd
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import flopy  # noqa: E402

import casestudy_flow_common as cfc  # noqa: E402
import casestudy_flow_viz as cfv  # noqa: E402


# =============================================================================
# Synthetic tiny DISV grid: 3 rows x 4 cols of unit-square quad cells
# (ncpl=12), large enough that a single NaN cell never masks EVERY triangle
# in flopy's tricontour (the degenerate 3-cell case does -- a known
# matplotlib/flopy edge case unrelated to this module's NaN-safety).
# =============================================================================
NROW, NCOL = 3, 4
CHD_CELLS = [0, 4]
RIV_CELLS = [7]
WEL_CELLS = [5]
INACTIVE_CELL = 11


def _make_gridprops(nrow: int, ncol: int):
    nvcols = ncol + 1
    vertices = []
    for r in range(nrow + 1):
        for c in range(nvcols):
            vertices.append([r * nvcols + c, float(c), float(r)])
    cell2d = []
    ncpl = nrow * ncol
    for r in range(nrow):
        for c in range(ncol):
            icell = r * ncol + c
            bl, br = r * nvcols + c, r * nvcols + c + 1
            tr, tl = (r + 1) * nvcols + c + 1, (r + 1) * nvcols + c
            cell2d.append([icell, c + 0.5, r + 0.5, 4, bl, br, tr, tl])
    return {"nvert": len(vertices), "vertices": vertices, "cell2d": cell2d, "ncpl": ncpl}, ncpl


GRIDPROPS, NCPL = _make_gridprops(NROW, NCOL)


def _base_spec():
    idomain = np.ones(NCPL, dtype=int)
    idomain[INACTIVE_CELL] = 0
    return {
        "gridprops": GRIDPROPS,
        "ncpl": NCPL,
        "top": np.full(NCPL, 10.0),
        "botm": np.zeros(NCPL),
        "k": np.full(NCPL, 10.0),
        "rch": np.full(NCPL, 1e-4),
        "strt": np.full(NCPL, 8.0),
        "idomain": idomain,
        "chd_cellid": [(0, c) for c in CHD_CELLS],
        "chd_head": [9.0, 9.5],
        "riv_cellid": [(0, c) for c in RIV_CELLS],
        "riv_stage": [7.5],
        "riv_cond": [50.0],
        "riv_rbot": [6.0],
        "wel_cellid": [(0, c) for c in WEL_CELLS],
        "wel_rate": [-100.0],
        "well_cells": list(WEL_CELLS),
        "refine_radius_used": 70.0,
        "crs": "EPSG:2056",
    }


def _build_gwf(tmp_path, spec, name):
    """A real (never-run) flopy DISV GWF with the boundary packages installed --
    enough for ``gwf.modelgrid`` (VertexGrid) AND for the builder's
    ``_expected_boundary_texts`` to derive {CHD,RIV,WEL,RCHA} -- without
    Triangle/Voronoi or an MF6 solve."""
    sim = flopy.mf6.MFSimulation(sim_name=name, sim_ws=str(tmp_path / name))
    flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1)])
    flopy.mf6.ModflowIms(sim)
    gwf = flopy.mf6.ModflowGwf(sim, modelname=name)
    flopy.mf6.ModflowGwfdisv(
        gwf, nlay=1, ncpl=spec["ncpl"], nvert=spec["gridprops"]["nvert"],
        top=spec["top"], botm=[spec["botm"]], idomain=[spec["idomain"]],
        vertices=spec["gridprops"]["vertices"], cell2d=spec["gridprops"]["cell2d"],
    )
    flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=spec["k"])
    flopy.mf6.ModflowGwfic(gwf, strt=spec["strt"])
    flopy.mf6.ModflowGwfrcha(gwf, recharge=spec["rch"])
    flopy.mf6.ModflowGwfchd(
        gwf, stress_period_data=list(zip(spec["chd_cellid"], spec["chd_head"])),
    )
    flopy.mf6.ModflowGwfriv(
        gwf, stress_period_data=list(zip(
            spec["riv_cellid"], spec["riv_stage"], spec["riv_cond"], spec["riv_rbot"],
        )),
    )
    flopy.mf6.ModflowGwfwel(
        gwf, stress_period_data=list(zip(spec["wel_cellid"], spec["wel_rate"])),
    )
    return gwf


def _make_state(tmp_path, *, name, heads, grid_hash="h1", spec=None, budgetfile=None,
                 diagnostics=None):
    spec = spec if spec is not None else _base_spec()
    gwf = _build_gwf(tmp_path, spec, name)
    ws = tmp_path / name
    ws.mkdir(parents=True, exist_ok=True)
    diagnostics = diagnostics if diagnostics is not None else {
        "flow_convergence": {"passed": True, "value": True},
    }
    diag_file = ws / f"diagnostics.{name}.json"
    diag_file.write_text(json.dumps(diagnostics, sort_keys=True))
    return {
        "gwf": gwf,
        "heads": np.asarray(heads, dtype=float),
        "spec": spec,
        "headfile": str(ws / f"{name}.hds"),
        "budgetfile": budgetfile or str(ws / f"{name}.cbc"),
        "grid_hash": grid_hash,
        "diagnostics": diagnostics,
        "diagnostics_file": str(diag_file),
        "workspace": str(ws),
        "state": name,
        "group": 0,
    }


@pytest.fixture()
def two_states(tmp_path):
    """``state_a`` (baseline-like) + ``state_b`` (wells-like), SAME grid_hash.

    Cell 11 is INACTIVE + carries the MF6 dry/inactive sentinel head (1e30) in
    BOTH states. Free (active, non-CHD) cells 5 and 6 respond by 1.2 m and
    0.6 m respectively (b - a); every other free cell is unchanged.
    """
    heads_a = np.full(NCPL, 9.0)
    heads_a[INACTIVE_CELL] = 1e30
    heads_b = heads_a.copy()
    heads_b[5] = 7.8   # -1.2 m
    heads_b[6] = 8.4   # -0.6 m

    state_a = _make_state(tmp_path, name="state_a", heads=heads_a)
    state_b = _make_state(tmp_path, name="state_b", heads=heads_b)
    return state_a, state_b


@pytest.fixture()
def mismatched_state(tmp_path, two_states):
    state_a, _ = two_states
    other = dict(state_a)
    other["grid_hash"] = "totally-different-hash"
    return other


# =============================================================================
# heads_of -- NaN safety.
# =============================================================================
class TestHeadsOf:
    def test_sentinel_maps_to_nan(self, two_states):
        state_a, _ = two_states
        heads = cfv.heads_of(state_a)
        assert np.isnan(heads[INACTIVE_CELL])
        assert np.all(np.isfinite(np.delete(heads, INACTIVE_CELL)))

    def test_inf_maps_to_nan(self, tmp_path):
        heads = np.full(NCPL, 9.0)
        heads[3] = np.inf
        heads[4] = -np.inf
        state = _make_state(tmp_path, name="inf_state", heads=heads)
        out = cfv.heads_of(state)
        assert np.isnan(out[3]) and np.isnan(out[4])

    def test_both_sentinel_signs_map_to_nan(self, tmp_path):
        # MF6 hdry/hnoflo can surface as EITHER +1e30 or -1e30; both must NaN.
        heads = np.full(NCPL, 9.0)
        heads[2] = 1e30
        heads[3] = -1e30
        state = _make_state(tmp_path, name="sentinel_state", heads=heads)
        out = cfv.heads_of(state)
        assert np.isnan(out[2]) and np.isnan(out[3])
        assert np.all(np.isfinite(np.delete(out, [2, 3])))

    def test_composed_max_ignores_nan(self, two_states):
        state_a, _ = two_states
        heads = cfv.heads_of(state_a)
        # a naive np.max would propagate the NaN; nanmax must not.
        assert np.isfinite(np.nanmax(heads))
        assert np.isnan(np.max(heads))  # sanity: the raw max IS nan (contrast)

    def test_does_not_mutate_input(self, two_states):
        state_a, _ = two_states
        original = np.array(state_a["heads"], copy=True)
        cfv.heads_of(state_a)
        assert np.array_equal(np.asarray(state_a["heads"]), original, equal_nan=True)


# =============================================================================
# difference / grid-hash guard.
# =============================================================================
class TestDifference:
    def test_computes_elementwise_diff(self, two_states):
        state_a, state_b = two_states
        diff = cfv.difference(state_b, state_a)
        assert diff[5] == pytest.approx(-1.2)
        assert diff[6] == pytest.approx(-0.6)
        assert diff[0] == pytest.approx(0.0)

    def test_raises_on_grid_hash_mismatch(self, two_states, mismatched_state):
        state_a, _ = two_states
        with pytest.raises(ValueError, match="grid_hash"):
            cfv.difference(mismatched_state, state_a)


# =============================================================================
# cell_areas / active_domain_mask / free_head_mask.
# =============================================================================
class TestMasksAndAreas:
    def test_cell_areas_are_known_unit_squares(self, two_states):
        state_a, _ = two_states
        areas = cfv.cell_areas(state_a)
        assert areas.shape == (NCPL,)
        assert np.allclose(areas, 1.0)

    def test_active_domain_mask_excludes_only_inactive(self, two_states):
        state_a, _ = two_states
        mask = cfv.active_domain_mask(state_a)
        assert mask.shape == (NCPL,)
        assert not mask[INACTIVE_CELL]
        assert mask.sum() == NCPL - 1

    def test_free_head_mask_also_excludes_chd(self, two_states):
        state_a, _ = two_states
        active = cfv.active_domain_mask(state_a)
        free = cfv.free_head_mask(state_a)
        # free is a STRICT subset of active (CHD cells dropped in addition).
        assert np.all(free <= active)
        assert free.sum() == active.sum() - len(CHD_CELLS)
        for c in CHD_CELLS:
            assert not free[c]
        assert not free[INACTIVE_CELL]


# =============================================================================
# Plotting: Figure returned, non-empty collections, aspect-equal, NaN masked.
# =============================================================================
class TestPlotHeadMap:
    def test_returns_figure_with_nonempty_collections(self, two_states):
        state_a, _ = two_states
        fig, ax = cfv.plot_head_map(state_a)
        assert isinstance(fig, plt.Figure)
        assert len(ax.collections) > 0
        assert ax.get_aspect() == 1.0

    def test_nan_cell_is_masked_not_zero(self, two_states):
        state_a, _ = two_states
        fig, ax = cfv.plot_head_map(state_a, contour=False, overlays=False)
        coll = ax.collections[0]
        arr = coll.get_array()
        assert np.ma.getmaskarray(arr)[INACTIVE_CELL]

    def test_overlays_add_bc_scatter_collections(self, two_states):
        state_a, _ = two_states
        fig_no, ax_no = cfv.plot_head_map(state_a, contour=False, overlays=False)
        fig_yes, ax_yes = cfv.plot_head_map(state_a, contour=False, overlays=True)
        assert len(ax_yes.collections) > len(ax_no.collections)

    def test_contour_does_not_raise_and_can_add_collections(self, two_states):
        state_a, _ = two_states
        fig, ax = cfv.plot_head_map(state_a, contour=True, overlays=False)
        assert len(ax.collections) >= 1

    def test_accepts_external_axes(self, two_states):
        state_a, _ = two_states
        fig, ax = plt.subplots()
        fig2, ax2 = cfv.plot_head_map(state_a, ax=ax)
        assert fig2 is fig
        assert ax2 is ax


class TestMaybeContour:
    """MEDIUM-6: the contour helper skips ONLY the genuinely-degenerate
    too-few-finite-cells case; any OTHER error propagates (never swallowed)."""

    def test_skips_when_too_few_finite_cells(self, two_states):
        state_a, _ = two_states
        fig, ax = plt.subplots()
        pmv = flopy.plot.PlotMapView(modelgrid=state_a["gwf"].modelgrid, ax=ax)
        mostly_nan = np.full(NCPL, np.nan)
        mostly_nan[0] = 9.0  # only 1 finite cell -> cannot triangulate
        assert cfv._maybe_contour(pmv, mostly_nan) is None

    def test_genuine_error_propagates(self, two_states):
        state_a, _ = two_states
        fig, ax = plt.subplots()
        pmv = flopy.plot.PlotMapView(modelgrid=state_a["gwf"].modelgrid, ax=ax)
        # A wrong-length, NON-flat array is a genuine bug -- it must NOT be
        # swallowed (varying values so the flat-field skip doesn't hide it).
        wrong_length = np.arange(NCPL + 5, dtype=float)
        with pytest.raises(Exception):
            cfv._maybe_contour(pmv, wrong_length)


class TestPlotDifferenceMap:
    def test_returns_figure_with_nonempty_collections(self, two_states):
        state_a, state_b = two_states
        fig, ax = cfv.plot_difference_map(state_b, state_a)
        assert isinstance(fig, plt.Figure)
        assert len(ax.collections) > 0
        assert ax.get_aspect() == 1.0

    def test_raises_on_grid_hash_mismatch(self, two_states, mismatched_state):
        state_a, _ = two_states
        with pytest.raises(ValueError, match="grid_hash"):
            cfv.plot_difference_map(mismatched_state, state_a)


class TestPlotBudgetBars:
    def test_returns_figure_with_bars(self, two_states, monkeypatch):
        state_a, _ = two_states
        _patch_fake_cbc(monkeypatch)
        state_a = dict(state_a)
        state_a["budgetfile"] = "/fake/state_a.cbc"
        fig, ax = cfv.plot_budget_bars(state_a)
        assert isinstance(fig, plt.Figure)
        # a bar chart's artifacts live in ax.containers/ax.patches, not
        # ax.collections -- assert on the artifact family bar() actually uses.
        assert len(ax.containers) > 0 or len(ax.patches) > 0


# =============================================================================
# budget_components -- signed net fluxes from a STUBBED CellBudgetFile.
# =============================================================================
# Boundary-flow q-fields per component; PLUS internal/structured records a real
# MF6 CBC also carries (no boundary ``q`` field) -- budget_components MUST skip
# these, not crash or fold them into the totals.
_FAKE_CBC_BOUNDARY = {
    "state_a.cbc": {"RIV": np.array([30.0, -10.0]), "WEL": np.array([-50.0]),
                     "CHD": np.array([50.0, 25.0])},
    "state_b.cbc": {"RIV": np.array([60.0, -10.0]), "WEL": np.array([-50.0]),
                     "CHD": np.array([50.0, 25.0])},
}
# Internal records with NO ``q`` field (imeth=1 face flows / aux arrays).
_FAKE_CBC_INTERNAL = ("FLOW-JA-FACE", "DATA-SPDIS", "DATA-SAT")


class _FakeCellBudgetFile:
    def __init__(self, path):
        self.key = Path(path).name

    def get_unique_record_names(self):
        boundary = [k.encode() for k in _FAKE_CBC_BOUNDARY[self.key]]
        internal = [k.encode() for k in _FAKE_CBC_INTERNAL]
        # interleave so ordering can't accidentally help the filter
        return internal[:1] + boundary + internal[1:]

    def get_times(self):
        return [1.0]

    def get_data(self, text=None, totim=None):
        name = text.decode().strip() if isinstance(text, (bytes, bytearray)) else str(text).strip()
        if name in _FAKE_CBC_INTERNAL:
            # a structured array with NO ``q`` field -- casting arr["q"] would
            # KeyError; budget_components must skip it.
            return [np.zeros((3,), dtype=[("nodes", int), ("flux", float)])]
        data = _FAKE_CBC_BOUNDARY.get(self.key, {})
        if name not in data:
            return []
        q = data[name]
        rec = np.zeros(len(q), dtype=[("q", float)])
        rec["q"] = q
        return [rec]


def _patch_fake_cbc(monkeypatch):
    monkeypatch.setattr(flopy.utils, "CellBudgetFile", _FakeCellBudgetFile)


class TestBudgetComponents:
    def test_signed_net_fluxes_ignoring_internal_records(self, two_states, monkeypatch):
        # The gwf (with CHD/RIV/WEL/RCHA packages) derives the boundary set; the
        # FLOW-JA-FACE / DATA-SPDIS / DATA-SAT internal records must be dropped.
        state_a, _ = two_states
        _patch_fake_cbc(monkeypatch)
        state_a = dict(state_a)
        state_a["budgetfile"] = "/fake/state_a.cbc"
        df = cfv.budget_components(state_a)
        assert isinstance(df, pd.DataFrame)
        assert set(df["component"]) == {"RIV", "WEL", "CHD"}
        by_name = df.set_index("component")["net_m3d"]
        assert by_name["RIV"] == pytest.approx(20.0)
        assert by_name["WEL"] == pytest.approx(-50.0)
        assert by_name["CHD"] == pytest.approx(75.0)

    def test_falls_back_to_whitelist_without_gwf(self, monkeypatch):
        # With no gwf on the state (allowed set cannot be derived), the whitelist
        # + q-field guard must still drop the internal records cleanly.
        _patch_fake_cbc(monkeypatch)
        state = {"budgetfile": "/fake/state_a.cbc"}  # NOTE: no "gwf" key
        df = cfv.budget_components(state)
        assert set(df["component"]) == {"RIV", "WEL", "CHD"}

    def test_no_time_steps_raises(self, two_states, monkeypatch):
        state_a, _ = two_states

        class _EmptyCBC:
            def __init__(self, path):
                pass

            def get_unique_record_names(self):
                return []

            def get_times(self):
                return []

        monkeypatch.setattr(flopy.utils, "CellBudgetFile", _EmptyCBC)
        with pytest.raises(RuntimeError):
            cfv.budget_components(state_a)


# =============================================================================
# read_diagnostics / write_flow_metrics / summarize_metrics round-trip.
# =============================================================================
class TestDiagnosticsAndMetricsIO:
    def test_read_diagnostics_round_trips(self, two_states):
        state_a, _ = two_states
        loaded = cfv.read_diagnostics(state_a)
        assert loaded == state_a["diagnostics"]

    def test_summarize_metrics_tidy_dataframe(self):
        rows = [
            {"name": "max_drawdown_m", "value": 1.2, "unit": "m"},
            {"name": "area_drawdown_gt_0p5m_m2", "value": 2.0, "unit": "m2"},
        ]
        df = cfv.summarize_metrics(rows)
        assert list(df.columns) == ["name", "value", "unit"]
        assert len(df) == 2
        assert df.loc[0, "value"] == pytest.approx(1.2)

    def test_write_flow_metrics_emits_csv_and_json(self, tmp_path):
        rows = [
            {"name": "max_drawdown_m", "value": 1.2, "unit": "m"},
            {"name": "area_drawdown_gt_0p5m_m2", "value": 2.0, "unit": "m2"},
        ]
        paths = cfv.write_flow_metrics(0, rows, out_dir=tmp_path)
        assert paths["csv"].exists()
        assert paths["json"].exists()
        assert paths["csv"].name == "flow_metrics.group0.csv"
        assert paths["json"].name == "flow_metrics.group0.json"

        df = pd.read_csv(paths["csv"])
        assert list(df["name"]) == ["max_drawdown_m", "area_drawdown_gt_0p5m_m2"]

        loaded = json.loads(paths["json"].read_text())
        assert loaded == rows


class TestSaveFig:
    def test_saves_under_figs_subdir(self, two_states, tmp_path):
        state_a, _ = two_states
        fig, _ax = cfv.plot_head_map(state_a)
        path = cfv.save_fig(fig, "heads_baseline", out_dir=tmp_path)
        assert path == tmp_path / "figs" / "heads_baseline.png"
        assert path.exists()

    def test_strips_redundant_png_extension(self, two_states, tmp_path):
        state_a, _ = two_states
        fig, _ax = cfv.plot_head_map(state_a)
        path = cfv.save_fig(fig, "heads_baseline.png", out_dir=tmp_path)
        assert path.name == "heads_baseline.png"


# =============================================================================
# emit_equalization_json -- thin wrapper over the EXISTING M2a.4 emit/write.
# =============================================================================
class TestEmitEqualizationJson:
    def _state_iii_result(self):
        return {
            "response_metrics": {
                "river_to_aquifer_flux": {"ii": 100.0, "iii": 130.0},
            },
            "gradient_inputs": {
                "riv_cell": 7, "dist_m": 10.0,
                "head_ext_ii": 9.0, "head_ext_iii": 8.5,
                "head_riv_ii": 9.0, "head_riv_iii": 9.0,
                "ext_active": True, "riv_active": True,
                "ext_dry_ii": False, "ext_dry_iii": False,
                "riv_dry_ii": False, "riv_dry_iii": False,
            },
            "runtime_s": 12.3,
        }

    def test_writes_and_returns_metrics(self, tmp_path):
        metrics = cfv.emit_equalization_json(0, self._state_iii_result(), out_dir=tmp_path)
        assert set(metrics) == {"river_leakage_change", "gradient_change", "runtime"}
        assert metrics["river_leakage_change"]["value"] == pytest.approx(30.0)
        assert metrics["runtime"]["value"] == pytest.approx(12.3)

        out_file = tmp_path / "equalization_metrics.0.json"
        assert out_file.exists()
        on_disk = json.loads(out_file.read_text())
        assert on_disk == metrics


# =============================================================================
# FLOW_METRIC_RECIPES self-check.
# =============================================================================
class TestFlowMetricRecipes:
    EXPECTED_IDS = {
        "max_drawdown_m", "area_drawdown_gt_0p5m_m2", "river_leakage_change_m3d",
        "gradient_toward_river_change", "discharge_component_change",
    }

    def test_registry_has_the_five_ids_with_metadata(self):
        assert set(cfv.FLOW_METRIC_RECIPES) == self.EXPECTED_IDS
        for name, entry in cfv.FLOW_METRIC_RECIPES.items():
            assert "unit" in entry and entry["unit"]
            assert "mask" in entry and entry["mask"]
            assert "doc" in entry and entry["doc"]
            assert callable(entry["compute"])

    def test_max_drawdown_self_check(self, two_states):
        state_a, state_b = two_states
        val = cfv.FLOW_METRIC_RECIPES["max_drawdown_m"]["compute"](state_b, state_a)
        assert val == pytest.approx(1.2)

    def test_area_drawdown_self_check(self, two_states):
        state_a, state_b = two_states
        val = cfv.FLOW_METRIC_RECIPES["area_drawdown_gt_0p5m_m2"]["compute"](state_b, state_a)
        assert val == pytest.approx(2.0)  # cells 5 + 6, area 1.0 each

    def test_river_leakage_change_self_check(self, two_states, monkeypatch):
        state_a, state_b = two_states
        _patch_fake_cbc(monkeypatch)
        state_a = dict(state_a); state_a["budgetfile"] = "/fake/state_a.cbc"
        state_b = dict(state_b); state_b["budgetfile"] = "/fake/state_b.cbc"
        val = cfv.FLOW_METRIC_RECIPES["river_leakage_change_m3d"]["compute"](state_b, state_a)
        assert val == pytest.approx(30.0)

    def test_discharge_component_change_self_check(self, two_states, monkeypatch):
        state_a, state_b = two_states
        _patch_fake_cbc(monkeypatch)
        state_a = dict(state_a); state_a["budgetfile"] = "/fake/state_a.cbc"
        state_b = dict(state_b); state_b["budgetfile"] = "/fake/state_b.cbc"
        val = cfv.FLOW_METRIC_RECIPES["discharge_component_change"]["compute"](state_b, state_a)
        assert val == {"CHD": pytest.approx(0.0), "RIV": pytest.approx(30.0), "WEL": pytest.approx(0.0)}

    def test_gradient_toward_river_change_uses_extraction_cell(self, tmp_path):
        # Doublet extraction cell = 6 (NOT well_cells[0]=5). The recipe must
        # resolve the receptor to the EXTRACTION cell from the doublet metadata.
        spec = _base_spec()
        heads_a = np.full(NCPL, 9.0); heads_a[INACTIVE_CELL] = 1e30
        heads_b = heads_a.copy()
        heads_b[6] = 8.4   # extraction cell drops
        heads_b[5] = 7.8   # well_cells[0] moves differently (would give -0.6/2)
        doublet = {"injection": {"cell": 1}, "extraction": {"cell": 6}}
        state_a = _make_state(tmp_path, name="grad_a", heads=heads_a, spec=spec)
        state_b = _make_state(tmp_path, name="grad_b", heads=heads_b, spec=spec)
        state_a["doublet"] = doublet
        state_b["doublet"] = doublet
        val = cfv.FLOW_METRIC_RECIPES["gradient_toward_river_change"]["compute"](state_b, state_a)
        # cell 6 (center 2.5,1.5) -> river cell 7 (center 3.5,1.5), dist=1.
        # grad_a=(9-9)/1=0; grad_b=(8.4-9)/1=-0.6; change=-0.6.
        assert val == pytest.approx(-0.6)

    def test_gradient_raises_without_doublet_metadata(self, two_states):
        state_a, state_b = two_states  # neither carries a doublet
        with pytest.raises(ValueError, match="doublet metadata"):
            cfv.recipe_gradient_toward_river_change(state_b, state_a)

    def test_gradient_rejects_chd_from_cell(self, two_states):
        state_a, state_b = two_states
        # CHD cell 0 is a pinned boundary head -> not a valid free-head receptor.
        with pytest.raises(ValueError, match="free-head"):
            cfv.recipe_gradient_toward_river_change(state_b, state_a, from_cell=0)


# =============================================================================
# explore_scenario -- the sandbox seam, run=False (no MF6 solve).
# =============================================================================
@pytest.fixture()
def base_states_stub():
    spec = _base_spec()
    grid_hash, _ = cfc.spec_canonical_hashes(spec)
    return {
        "baseline": {"spec": spec, "grid_hash": grid_hash},
        "wells_only": {
            "doublet": {"injection": {"cell": 2}, "extraction": {"cell": 9}},
            "resolved_Q": 500.0,
        },
        "grid_hash": grid_hash,
    }


class TestExploreScenario:
    def test_run_false_returns_same_grid_result(self, base_states_stub, tmp_path):
        result = cfv.explore_scenario(
            0, "river_conductance", {"conductance_factor": 2.0},
            work_dir=tmp_path, base_states=base_states_stub, run=False,
        )
        assert result["exploratory"] is True
        assert result["grid_hash"] == base_states_stub["grid_hash"]
        assert result["heads"] is None  # run=False -- no solve
        assert result["converged"] is None

    def test_run_false_applies_the_scenario(self, base_states_stub, tmp_path):
        baseline_spec = base_states_stub["baseline"]["spec"]
        result = cfv.explore_scenario(
            0, "river_conductance", {"conductance_factor": 2.0},
            work_dir=tmp_path, base_states=base_states_stub, run=False,
        )
        assert result["spec"]["riv_cond"] != baseline_spec["riv_cond"]
        assert result["spec"]["riv_cond"] == [100.0]

    def test_does_not_raise_on_expectation_violating_param(self, base_states_stub, tmp_path):
        # An extreme, hydrologically-"wrong" parameter must NOT raise here --
        # the frozen expectation table is never consulted by the sandbox.
        result = cfv.explore_scenario(
            0, "river_conductance", {"conductance_factor": 1000.0},
            work_dir=tmp_path, base_states=base_states_stub, run=False,
        )
        assert result["exploratory"] is True

    def test_writes_under_isolated_sandbox_dir(self, base_states_stub, tmp_path):
        result = cfv.explore_scenario(
            0, "river_conductance", {"conductance_factor": 2.0},
            work_dir=tmp_path, base_states=base_states_stub, run=False,
        )
        ws = Path(result["workspace"])
        assert "_sandbox" in ws.parts
        assert ws.is_relative_to(tmp_path)

    def test_grid_identity_unchanged(self, base_states_stub, tmp_path):
        baseline_spec = base_states_stub["baseline"]["spec"]
        result = cfv.explore_scenario(
            0, "river_conductance", {"conductance_factor": 2.0},
            work_dir=tmp_path, base_states=base_states_stub, run=False,
        )
        assert result["spec"]["ncpl"] == baseline_spec["ncpl"]
        assert result["spec"]["gridprops"] == baseline_spec["gridprops"]
        assert np.array_equal(
            np.asarray(result["spec"]["idomain"]), np.asarray(baseline_spec["idomain"]),
        )

    def test_returned_spec_carries_the_doublet(self, base_states_stub, tmp_path):
        # HIGH-2: the returned spec's WEL must reflect the assembled
        # (background + doublet) set -- inj cell 2 and ext cell 9, each once.
        result = cfv.explore_scenario(
            0, "river_conductance", {"conductance_factor": 2.0},
            work_dir=tmp_path, base_states=base_states_stub, run=False,
        )
        well_cells = list(result["spec"]["well_cells"])
        assert 2 in well_cells and 9 in well_cells
        assert well_cells.count(2) == 1 and well_cells.count(9) == 1
        # the background well (cell 5) is still present -> doublet added, not replaced
        assert 5 in well_cells

    def test_assembled_geometry_mismatch_raises(self, base_states_stub, tmp_path, monkeypatch):
        # MEDIUM-4: a scenario that (wrongly) perturbs the grid geometry while
        # keeping ncpl/idomain must be caught by the ASSEMBLED-model geometry
        # check (not just the cheap pre-check).
        import copy as _copy
        import casestudy_flow_scenarios as _scn

        real_apply = _scn.apply_scenario

        def _geometry_breaking_apply(spec, scenario_type, params):
            out = real_apply(spec, scenario_type, params)
            out = dict(out)
            gp = _copy.deepcopy(out["gridprops"])
            gp["vertices"][0][1] = gp["vertices"][0][1] + 500.0  # move a vertex
            out["gridprops"] = gp
            return out

        monkeypatch.setattr(_scn, "apply_scenario", _geometry_breaking_apply)
        with pytest.raises(RuntimeError, match="canonical grid"):
            cfv.explore_scenario(
                0, "river_conductance", {"conductance_factor": 2.0},
                work_dir=tmp_path, base_states=base_states_stub, run=False,
            )

    # --- HIGH-1: run=True KEEPS the physics gates (stubbed assemble; no MF6) ---
    def _stub_built(self, *, converged, heads):
        return {
            "gwf": object(),
            "sim": object(),
            "model_name": "sbx",
            "heads": heads,
            "headfile": "sbx.hds",
            "budgetfile": "sbx.cbc",
            "converged": converged,
            "wel_cellid": [(0, 5)],
            "wel_rate": [-100.0],
            "well_cells": [5],
        }

    def test_run_true_raises_on_nonconvergence(self, base_states_stub, tmp_path, monkeypatch):
        stub = self._stub_built(converged=False, heads=None)
        monkeypatch.setattr(cfc, "assemble_flow_state", lambda *a, **k: stub)
        with pytest.raises(RuntimeError, match="converge"):
            cfv.explore_scenario(
                0, "river_conductance", {"conductance_factor": 2.0},
                work_dir=tmp_path, base_states=base_states_stub, run=True,
            )

    def test_run_true_raises_on_nonfinite_heads(self, base_states_stub, tmp_path, monkeypatch):
        heads = np.full(NCPL, 9.0)
        heads[3] = np.nan
        stub = self._stub_built(converged=True, heads=heads)
        monkeypatch.setattr(cfc, "assemble_flow_state", lambda *a, **k: stub)
        # stub out the budget read so the mass-balance gate passes cleanly and
        # the FINITE-HEADS gate is the one that trips (no real MF6).
        import casestudy_flow_builder as cfb
        monkeypatch.setattr(cfb, "_mass_balance_percent", lambda gwf: 0.0)
        with pytest.raises(RuntimeError, match="gate"):
            cfv.explore_scenario(
                0, "river_conductance", {"conductance_factor": 2.0},
                work_dir=tmp_path, base_states=base_states_stub, run=True,
            )

    def test_run_true_raises_on_mass_imbalance(self, base_states_stub, tmp_path, monkeypatch):
        heads = np.full(NCPL, 9.0)  # finite
        stub = self._stub_built(converged=True, heads=heads)
        monkeypatch.setattr(cfc, "assemble_flow_state", lambda *a, **k: stub)
        import casestudy_flow_builder as cfb
        # a 50% mass-balance error must trip the mass-balance gate.
        monkeypatch.setattr(cfb, "_mass_balance_percent", lambda gwf: 50.0)
        with pytest.raises(RuntimeError, match="gate"):
            cfv.explore_scenario(
                0, "river_conductance", {"conductance_factor": 2.0},
                work_dir=tmp_path, base_states=base_states_stub, run=True,
            )

    def test_builds_all_flow_states_only_when_base_states_omitted(self, tmp_path, monkeypatch):
        called = {}

        def fake_build_all(group, *, work_dir):
            called["group"] = group
            spec = _base_spec()
            grid_hash, _ = cfc.spec_canonical_hashes(spec)
            return {
                "baseline": {"spec": spec, "grid_hash": grid_hash},
                "wells_only": {
                    "doublet": {"injection": {"cell": 2}, "extraction": {"cell": 9}},
                    "resolved_Q": 500.0,
                },
                "grid_hash": grid_hash,
            }

        import casestudy_flow_builder as cfb

        monkeypatch.setattr(cfb, "build_all_flow_states", fake_build_all)
        cfv.explore_scenario(
            0, "river_conductance", {"conductance_factor": 2.0},
            work_dir=tmp_path, base_states=None, run=False,
        )
        assert called["group"] == 0

    def test_never_calls_the_private_scenario_solver_or_expectation_gate(self):
        src = inspect.getsource(cfv.explore_scenario)
        for forbidden in (
            "_solve_validate_scenario", "evaluate_scenario_expectation",
            "assert_config_matches_frozen",
        ):
            assert forbidden not in src, f"explore_scenario must not reference {forbidden!r}"
