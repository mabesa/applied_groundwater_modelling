"""
Acceptance tests for M2a.1 — the reusable case-study flow builder
`casestudy_flow_builder.build_flow_state(group, state='baseline', *, work_dir)`.

Structure:
* REGRESSION GUARD (real group-0 build; skipped when mf6 is unavailable):
  builder output compared DIRECTLY to the COMMITTED golden
  (`_SUPPORT/src/golden/group0_flow.{npz,manifest.json}`) -- PRIMARY canonical
  package hashes + faithful_riv hash == committed; SECONDARY heads within
  1e-3 m (max/RMS reported); PACKAGE INVARIANTS (CHD/RIV/RCHA/NPF/WEL counts +
  Sigma cond/rate + active-cell count) == the committed NPZ.
* Cheap tests (no mf6): the M1.4 diagnostics surface shape (flow_head_delta
  NULL for baseline), the rich return-shape keys, unsupported-state guard, the
  state-(iii) interface declaration, grep gate.

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_builder.py -v
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import model_io_utils as mio  # noqa: E402
import casestudy_flow_common as cfc  # noqa: E402
import casestudy_flow_builder as b  # noqa: E402

GOLDEN_DIR = SRC_DIR / "golden"

_MF6 = cfc.resolve_mf6_exe()
_HAS_MF6 = Path(_MF6).exists() or (os.path.dirname(_MF6) == "" and __import__("shutil").which(_MF6))
requires_mf6 = pytest.mark.skipif(
    not _HAS_MF6, reason="real group-0 build needs the mf6 executable (PATH or flopy bin)"
)


def _coarse_data_present() -> bool:
    """The 05f-calibrated coarse model is present locally (no download)."""
    try:
        from data_utils import get_default_data_folder
        return (Path(get_default_data_folder()) / "calibration" / "mfsim.nam").exists()
    except Exception:
        return False


requires_coarse_data = pytest.mark.skipif(
    not _coarse_data_present(),
    reason="needs the 05f-calibrated coarse model present locally (no mf6 solve)",
)


# =============================================================================
# REGRESSION GUARD — pinned to the COMMITTED oracle (real build).
# =============================================================================
@requires_mf6
class TestRegressionGuardAgainstCommittedGolden:
    @pytest.fixture(scope="class")
    def built(self, tmp_path_factory):
        wd = tmp_path_factory.mktemp("builder_group0")
        return b.build_flow_state(0, "baseline", work_dir=wd)

    @pytest.fixture(scope="class")
    def manifest(self):
        return json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())

    @pytest.fixture(scope="class")
    def committed_spec(self):
        return mio.load_flow_spec(GOLDEN_DIR / "group0_flow.npz")

    def test_primary_canonical_package_hashes_match(self, built, manifest):
        assert built["grid_hash"] == manifest["aggregate_hash"]
        assert built["package_hashes"] == manifest["array_hashes"]

    def test_faithful_riv_hash_matches_committed(self, built, manifest):
        assert built["riv_info"]["hash"] == manifest["faithful_riv"]["hash"]

    def test_secondary_heads_within_1e_3_m(self, built, manifest):
        hb = np.asarray(built["heads"], dtype=float)
        hg = np.asarray(manifest["heads"], dtype=float)
        assert hb.shape == hg.shape
        d = np.abs(hb - hg)
        max_d, rms_d = float(d.max()), float(np.sqrt((d ** 2).mean()))
        assert max_d <= 1e-3, f"heads max delta {max_d:.3e} m exceeds 1e-3 m (RMS {rms_d:.3e})"

    def test_package_invariants_match_committed_npz(self, built, committed_spec):
        sp = built["spec"]
        cs = committed_spec
        # counts
        assert len(sp["chd_cellid"]) == len(cs["chd_cellid"])
        assert len(sp["riv_cellid"]) == len(cs["riv_cellid"])
        assert len(sp["wel_cellid"]) == len(cs["wel_cellid"])
        assert int(sp["ncpl"]) == int(cs["ncpl"])
        assert int(np.count_nonzero(np.asarray(sp["idomain"]))) == \
               int(np.count_nonzero(np.asarray(cs["idomain"])))
        # sums (RIV conductance, WEL rate) + RCHA/NPF totals
        assert sum(sp["riv_cond"]) == pytest.approx(sum(cs["riv_cond"]), abs=1e-6)
        assert sum(sp["wel_rate"]) == pytest.approx(sum(cs["wel_rate"]), abs=1e-6)
        assert float(np.sum(sp["rch"])) == pytest.approx(float(np.sum(cs["rch"])), rel=1e-9)
        assert float(np.sum(sp["k"])) == pytest.approx(float(np.sum(cs["k"])), rel=1e-9)

    def test_diagnostics_baseline_json_written_with_flow_ids(self, built):
        diag_path = Path(built["workspace"]) / "diagnostics.baseline.json"
        assert diag_path.exists()
        diag = json.loads(diag_path.read_text())
        assert set(diag.keys()) == set(b.FLOW_DIAGNOSTIC_IDS)
        # flow_head_delta null for baseline; everything passes on the clean run
        assert diag["flow_head_delta"]["value"] is None
        assert all(e["passed"] for e in diag.values())

    def test_rich_return_shape_keys_present(self, built):
        for key in b.BUILD_RESULT_KEYS:
            assert key in built, f"build_flow_state result missing {key!r}"
        assert built["gwf_name"] == "group0_baseline"
        assert built["headfile"].endswith("group0_baseline.hds")
        assert built["budgetfile"].endswith("group0_baseline.cbc")
        assert built["stress_period"]["nper"] == 1 and built["stress_period"]["steady"] is True
        assert built["units"]["length"] == "meters"


# =============================================================================
# M2a.2 — state (ii) wells_only + half-rate (real group-0 build; mf6-gated).
# =============================================================================
@requires_mf6
class TestWellsOnlyStateGroup0:
    @pytest.fixture(scope="class")
    def full(self, tmp_path_factory):
        return b.build_flow_state(0, "wells_only", work_dir=tmp_path_factory.mktemp("g0_wells"))

    @pytest.fixture(scope="class")
    def half(self, tmp_path_factory):
        return b.build_flow_state(0, "wells_only", half_rate=True,
                                  work_dir=tmp_path_factory.mktemp("g0_wells_half"))

    def test_doublet_placement_cells(self, full):
        d = full["doublet"]
        # inj/ext resolve into the fine corridor, active, non-CHD/RIV (no raise)
        assert d["injection"]["cell"] == 673 and d["extraction"]["cell"] == 732
        assert d["injection"]["cellsize_m"] < cfc.CORRIDOR_CELLSIZE_THRESHOLD_M
        assert d["extraction"]["cellsize_m"] < cfc.CORRIDOR_CELLSIZE_THRESHOLD_M

    def test_incremental_per_role_flux_is_plus_minus_Q(self, full):
        assert full["resolved_Q"] == pytest.approx(cfc.DOUBLET_Q_M3D)
        assert full["incremental_flux"]["injection"] == pytest.approx(+cfc.DOUBLET_Q_M3D, abs=1e-6)
        assert full["incremental_flux"]["extraction"] == pytest.approx(-cfc.DOUBLET_Q_M3D, abs=1e-6)

    def test_head_direction_sanity(self, full):
        assert full["doublet_head_delta"]["injection"] > +b.HEAD_DIRECTION_TOL_M
        assert full["doublet_head_delta"]["extraction"] < -b.HEAD_DIRECTION_TOL_M

    def test_half_rate_flux_and_response_less_than_full(self, full, half):
        assert half["resolved_Q"] == pytest.approx(0.5 * cfc.DOUBLET_Q_M3D)
        assert half["incremental_flux"]["injection"] == pytest.approx(+0.5 * cfc.DOUBLET_Q_M3D, abs=1e-6)
        assert half["incremental_flux"]["extraction"] == pytest.approx(-0.5 * cfc.DOUBLET_Q_M3D, abs=1e-6)
        # both solved on the IDENTICAL built grid -> half response < full
        assert half["grid_hash"] == full["grid_hash"]
        assert half["head_delta_max_m"] < full["head_delta_max_m"]
        assert abs(half["doublet_head_delta"]["injection"]) < abs(full["doublet_head_delta"]["injection"])

    def test_diagnostics_wells_only_json_has_drawdown(self, full):
        diag_path = Path(full["workspace"]) / "diagnostics.wells_only.json"
        assert diag_path.exists()
        diag = json.loads(diag_path.read_text())
        assert set(diag.keys()) == set(b.FLOW_DIAGNOSTIC_IDS)
        # flow_head_delta is the same-grid drawdown (NOT null), and passes
        assert diag["flow_head_delta"]["value"] == pytest.approx(full["head_delta_max_m"])
        assert diag["flow_head_delta"]["value"] > 0
        assert all(e["passed"] for e in diag.values())

    def test_halfrate_diagnostics_filename_distinct(self, half):
        assert (Path(half["workspace"]) / "diagnostics.wells_only_halfrate.json").exists()

    def test_grid_hash_matches_committed_golden(self, full):
        # the doublet is a STRESS, not a grid change: the built grid is still
        # the committed baseline golden's grid.
        manifest = json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())
        assert full["grid_hash"] == manifest["aggregate_hash"]

    def test_rich_return_shape(self, full):
        for key in b.BUILD_RESULT_KEYS:
            assert key in full
        assert full["state"] == "wells_only"
        assert full["gwf_name"] == "g0_wells"
        assert full["headfile"].endswith("group0_wells_only.hds")


# =============================================================================
# M2a.2 REWORK Finding 5 — full + half built on ONE grid (build_wells_states),
# and Finding 4 — a FROZEN group is builder-pinned to its committed golden.
# =============================================================================
@requires_mf6
class TestBuildWellsStatesSameGrid:
    @pytest.fixture(scope="class")
    def both(self, tmp_path_factory):
        return b.build_wells_states(0, work_dir=tmp_path_factory.mktemp("g0_both"))

    def test_full_half_baseline_share_one_grid(self, both):
        assert both["full"]["grid_hash"] == both["half"]["grid_hash"] == both["grid_hash"]

    def test_half_response_less_than_full_same_grid(self, both):
        assert both["half"]["head_delta_max_m"] < both["full"]["head_delta_max_m"]
        assert both["full"]["resolved_Q"] == pytest.approx(cfc.DOUBLET_Q_M3D)
        assert both["half"]["resolved_Q"] == pytest.approx(0.5 * cfc.DOUBLET_Q_M3D)

    def test_grid_pinned_to_committed_golden(self, both):
        manifest = json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())
        assert both["grid_hash"] == manifest["aggregate_hash"]


# =============================================================================
# M2a.3 — state (iii) wells_plus_scenario (real group-0 build; mf6-gated).
# =============================================================================
@requires_mf6
class TestScenarioStateGroup0:
    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        return b.build_flow_state(0, "wells_plus_scenario",
                                  work_dir=tmp_path_factory.mktemp("g0_scen"))

    def test_scenario_read_from_flow_config(self, result):
        # group 0 flow scenario is chd_head_change (from case_config.yaml)
        assert result["scenario_type"] == "chd_head_change"
        assert result["scenario_params"]["type"] == "chd_head_change"

    def test_same_grid_as_committed_golden(self, result):
        # state iii is on the SAME grid as states i/ii (grid hash == golden)
        manifest = json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())
        assert result["grid_hash"] == manifest["aggregate_hash"]

    def test_diagnostics_wells_plus_scenario_json(self, result):
        p = Path(result["workspace"]) / "diagnostics.wells_plus_scenario.json"
        assert p.exists()
        diag = json.loads(p.read_text())
        assert set(diag.keys()) == set(b.FLOW_DIAGNOSTIC_IDS)
        # flow_head_delta = same-grid max|iii - ii| (NOT null), and passes
        assert diag["flow_head_delta"]["value"] == pytest.approx(result["head_delta_max_m"])
        assert diag["flow_head_delta"]["value"] > 0
        assert all(e["passed"] for e in diag.values())

    def test_response_consistent_with_frozen_expectation(self, result):
        # Finding 2: the builder SELF-ENFORCES this (it would have raised on a
        # contradiction); the result carries the evaluated report.
        assert result["expectation"]["consistent"], result["expectation"]["problems"]
        assert result["expectation"]["assertion_class"] == "feature_local"

    def test_package_hashes_reflect_scenario_not_pre_scenario(self, result):
        # Finding 3: grid_hash == golden (geometry unchanged) BUT package_hashes
        # reflect the SCENARIO-mutated packages (chd_head changed) -> they must
        # match hashes of result['spec'] (scen_spec) and DIFFER from the golden.
        manifest = json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())
        assert result["grid_hash"] == manifest["aggregate_hash"]
        agg_scen, arr_scen = cfc.spec_canonical_hashes(result["spec"])
        assert result["package_hashes"] == arr_scen
        assert result["package_hashes"] != manifest["array_hashes"], (
            "package_hashes must reflect the scenario-mutated packages, not the pre-scenario spec"
        )
        # the mutated field (chd_head) hash differs; geometry hashes match golden
        assert arr_scen["chd_head"] != manifest["array_hashes"]["chd_head"]
        assert arr_scen["gridprops__vertices"] == manifest["array_hashes"]["gridprops__vertices"]

    def test_builder_raises_on_frozen_expectation_contradiction(self, tmp_path, monkeypatch):
        # Finding 2: a state-iii build whose response CONTRADICTS the frozen
        # expectation must FAIL (not return). Force the evaluator to report an
        # inconsistency and assert the real build raises.
        import casestudy_flow_scenarios as scn
        monkeypatch.setattr(
            b.scn, "evaluate_scenario_expectation",
            lambda group, metrics, **k: {
                "consistent": False, "assertion_class": "clear_sign",
                "problems": ["forced contradiction for the test"], "observed": {},
            },
        )
        with pytest.raises(RuntimeError, match="(?i)CONTRADICTS|frozen expectation"):
            b.build_flow_state(0, "wells_plus_scenario", work_dir=tmp_path)

    def test_rich_return_shape(self, result):
        for key in b.BUILD_RESULT_KEYS:
            assert key in result
        assert result["state"] == "wells_plus_scenario"
        assert result["headfile"].endswith("group0_wells_plus_scenario.hds")


# =============================================================================
# M2a.3 Finding 1 — response metrics are ACTIVE-CELL masked (no mf6).
# =============================================================================
class TestScenarioResponseMetricsActiveMasked:
    def _fake_gwf(self, riv_q):
        import numpy as _np
        rec = _np.array([(1, 1, riv_q)], dtype=[("node", int), ("node2", int), ("q", float)])

        class _Bud:
            def get_times(self_inner):
                return [1.0]

            def get_data(self_inner, text, totim):
                return [rec]

        return SimpleNamespace(output=SimpleNamespace(budget=lambda: _Bud()))

    def test_inactive_cell_excluded_from_all_stats(self):
        # 4 cells; cell 3 INACTIVE with a huge (bogus) head change -> must be
        # ignored by max/argmax/mean/n_dry.
        spec = {
            "idomain": np.array([1, 1, 1, 0]),
            "chd_cellid": [(0, 0)], "riv_cellid": [(0, 1)],
        }
        mg = SimpleNamespace(
            xcellcenters=np.array([0.0, 10.0, 20.0, 30.0]),
            ycellcenters=np.array([0.0, 0.0, 0.0, 0.0]),
        )
        heads_ii = np.array([5.0, 5.0, 5.0, 5.0])
        heads_iii = np.array([5.1, 5.2, 5.3, 999.0])  # cell 3 (inactive) is bogus
        botm = np.array([0.0, 0.0, 0.0, 0.0])
        m = b._scenario_response_metrics(
            0, spec, mg, heads_ii, heads_iii,
            self._fake_gwf(-100.0), self._fake_gwf(-90.0), botm,
        )
        # max over ACTIVE cells is 0.3 (cell 2), NOT 993.9 (inactive cell 3)
        assert m["max_abs_head_change"] == pytest.approx(0.3)
        assert m["n_active"] == 3
        # argmax is the active cell 2 (x=20) -> dist to CHD cell 0 (x=0) = 20 m
        assert m["argmax_dist_to_chd_m"] == pytest.approx(20.0)
        # mean over active cells only (0.1+0.2+0.3)/3
        assert m["mean_head_change"] == pytest.approx(0.2)
        assert m["n_dry_iii"] == 0


# =============================================================================
# Finding 3: hash-regression coverage that does NOT need mf6 (spec-only, no
# solve) + a hub-required assertion so the real guard cannot silently skip on
# the target. The hub CI MUST exercise TestRegressionGuardAgainstCommittedGolden
# (which does the full mf6 solve).
# =============================================================================
def test_frozen_goldens_are_valid_provisional_artifacts():
    """Every group<N>_flow.{npz,manifest.json} present in the golden dir must
    load + hash-verify and be a provisional (macOS) artifact tagged for Linux
    re-verify -- guards the M2a.2 per-group baseline goldens (2/7/8) alongside
    the committed group 0."""
    import model_io_utils as _mio
    npzs = sorted(GOLDEN_DIR.glob("group*_flow.npz"))
    assert npzs, "expected at least the committed group0 golden"
    for npz in npzs:
        manifest = json.loads(npz.with_suffix("").with_suffix(".manifest.json").read_text())
        # loads + hash-verifies against its manifest
        spec = _mio.load_flow_spec(npz)
        assert int(spec["ncpl"]) > 0
        agg, arr = cfc.spec_canonical_hashes(spec)
        assert agg == manifest["aggregate_hash"]
        assert manifest["provisional"] is True
        assert manifest["authoritative_platform"] == "linux"
        assert "faithful_riv" in manifest and len(manifest["faithful_riv"]["hash"]) == 64


@requires_coarse_data
def test_builder_spec_hashes_match_committed_without_solve():
    """Always-on (no mf6): the builder's baseline SPEC canonical package
    hashes + faithful-RIV hash reproduce the COMMITTED golden manifest -- so a
    `common`-code drift that changes the frozen spec is caught even on a box
    without the mf6 solver."""
    import model_io_utils as _mio
    mother = _mio.ensure_flow_model()
    _sim, cgwf = cfc.load_coarse_model(mother)
    coarse_heads = cgwf.output.head().get_data().flatten()
    boundary_gdf, river_gdf = cfc.load_gis(mother)
    refine_points = cfc.group_refine_points(0)
    spec, riv_info = cfc.build_baseline_spec(
        cgwf, boundary_gdf, river_gdf, refine_points, coarse_heads,
    )
    agg, arr = cfc.spec_canonical_hashes(spec)
    manifest = json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())
    assert agg == manifest["aggregate_hash"]
    assert arr == manifest["array_hashes"]
    assert riv_info["hash"] == manifest["faithful_riv"]["hash"]


def test_regression_guard_is_exercised_on_hub():
    """On the hub/target (AGM_HUB=1) the real mf6 regression guard must NOT be
    skipped -- mf6 has to be available so the full build+solve is checked."""
    if os.environ.get("AGM_HUB") == "1":
        assert _HAS_MF6, (
            "AGM_HUB=1 but mf6 is unavailable: the real group-0 regression "
            "guard (build+solve vs committed golden) would silently skip"
        )


# =============================================================================
# M1.4 diagnostics surface (cheap; format_budget_summary stubbed).
# =============================================================================
class TestDiagnosticsSurface:
    def _stub_budget(self, monkeypatch, pct):
        monkeypatch.setattr(
            b.mio, "format_budget_summary",
            lambda gwf: pd.DataFrame(
                {"Inflow (m3/d)": ["-"], "Outflow (m3/d)": ["-"], "Net (m3/d)": [pct]},
                index=["PERCENT ERROR"],
            ),
        )

    def test_shape_is_m14_id_entry_dict_with_null_head_delta(self, monkeypatch):
        self._stub_budget(monkeypatch, 0.01)
        diag = b._emit_flow_diagnostics(
            converged=True, heads=np.array([8.0, 8.5, 9.0]), botm=np.array([0.0, 0.0, 0.0]),
            gwf=object(),
        )
        assert set(diag.keys()) == set(b.FLOW_DIAGNOSTIC_IDS)
        # each value is an M1.4 entry dict
        for e in diag.values():
            assert {"value", "triggered_severity", "passed"} <= set(e)
        # baseline: flow_head_delta is NULL (not a faked zero), and passes
        assert diag["flow_head_delta"]["value"] is None
        assert diag["flow_head_delta"]["passed"] is True
        assert diag["flow_convergence"]["value"] is True
        assert diag["finite_heads"]["value"] is True
        assert diag["flow_no_dry_cells"]["value"] == 0

    def test_dry_cell_counted(self, monkeypatch):
        self._stub_budget(monkeypatch, 0.01)
        diag = b._emit_flow_diagnostics(
            converged=True, heads=np.array([8.0, -1.0, 9.0]), botm=np.array([0.0, 0.0, 0.0]),
            gwf=object(),
        )
        assert diag["flow_no_dry_cells"]["value"] == 1

    def test_nonfinite_head_flags_finite_heads_false(self, monkeypatch):
        self._stub_budget(monkeypatch, 0.01)
        diag = b._emit_flow_diagnostics(
            converged=True, heads=np.array([8.0, np.nan, 9.0]), botm=np.array([0.0, 0.0, 0.0]),
            gwf=object(),
        )
        assert diag["finite_heads"]["value"] is False
        assert diag["finite_heads"]["passed"] is False

    def test_diagnostics_json_is_strict_serializable(self, monkeypatch, tmp_path):
        self._stub_budget(monkeypatch, 0.01)
        diag = b._emit_flow_diagnostics(
            converged=True, heads=np.array([8.0, 8.5, 9.0]), botm=np.array([0.0, 0.0, 0.0]),
            gwf=object(),
        )
        # must serialize with allow_nan=False (RFC-8259) -- no NaN/Inf leaks
        (tmp_path / "d.json").write_text(json.dumps(diag, allow_nan=False))


class TestBuilderNonFiniteHeadGate:
    """Finding 4: a converged run with a non-finite head must RAISE (the
    dry-cell count / downstream metadata would be silently wrong otherwise)."""

    def test_persistent_nan_head_never_silently_builds(self, tmp_path, monkeypatch):
        # A solve that always returns a NON-FINITE head must never yield a
        # "built" state: the refine+solve WALK rejects a non-finite solve at
        # EVERY radius and raises a DEFERRAL RuntimeError (the NaN-fragility
        # guard -- build_flow_state cannot proceed on a broken head field).
        monkeypatch.setattr(b.mio, "ensure_flow_model", lambda: tmp_path / "mother")
        monkeypatch.setattr(
            b.cfc, "load_coarse_model",
            lambda m: (None, type("G", (), {"output": type("O", (), {"head": staticmethod(
                lambda: type("H", (), {"get_data": staticmethod(lambda: np.zeros((1, 1, 3)))})())})()})()),
        )
        monkeypatch.setattr(b.cfc, "load_gis", lambda m: (None, None))
        monkeypatch.setattr(b.cfc, "group_refine_points", lambda g: [(0.0, 0.0), (1.0, 1.0)])
        spec = {"botm": np.array([0.0, 0.0, 0.0])}
        monkeypatch.setattr(b.cfc, "build_baseline_spec", lambda *a, **k: (spec, {"hash": "x"}))
        monkeypatch.setattr(
            b.cfc, "assemble_flow_state",
            lambda spec, **k: {
                "heads": np.array([8.0, np.nan, 9.0]), "converged": True,
                "gwf": object(), "sim": object(), "model_name": "g0",
                "headfile": str(tmp_path / "g0.hds"), "budgetfile": str(tmp_path / "g0.cbc"),
            },
        )
        with pytest.raises(RuntimeError, match="(?i)could not refine\\+solve|defer"):
            b.build_flow_state(0, "baseline", work_dir=tmp_path / "wd")

    def test_wells_nan_head_emits_diagnostic_then_raises_no_json_error(self, tmp_path, monkeypatch):
        # Finding 3: a converged wells solve with a NaN head must NOT let the
        # NaN reach np.max (-> NaN head_delta -> strict-JSON write raises).
        # Instead: emit the M1.4 diagnostic (finite_heads=False, flow_head_delta
        # null, valid JSON) THEN raise a clean RuntimeError.
        walk = {
            "spec": {"botm": np.zeros(3), "wel_cellid": [], "wel_rate": []},
            "riv_info": {"hash": "x"}, "refine_points": [(0.0, 0.0), (1.0, 1.0)],
            "refine_radius": 70.0,
            "base_built": {"heads": np.array([8.0, 8.5, 9.0]), "modelgrid": object(), "gwf": object()},
        }
        monkeypatch.setattr(
            b.cfc, "resolve_doublet_cells",
            lambda spec, mg, rp: {"injection": {"cell": 0}, "extraction": {"cell": 1}},
        )
        monkeypatch.setattr(
            b.cfc, "assemble_flow_state",
            lambda spec, **k: {
                "heads": np.array([8.0, np.nan, 9.0]), "converged": True,
                "gwf": object(), "sim": object(), "model_name": "g0w",
                "headfile": str(tmp_path / "h.hds"), "budgetfile": str(tmp_path / "b.cbc"),
                "wel_cellid": [], "wel_rate": [],
            },
        )
        monkeypatch.setattr(
            b.mio, "format_budget_summary",
            lambda gwf: pd.DataFrame(
                {"Inflow (m3/d)": ["-"], "Outflow (m3/d)": ["-"], "Net (m3/d)": [0.01]},
                index=["PERCENT ERROR"],
            ),
        )
        wd = tmp_path / "wd"
        wd.mkdir()
        with pytest.raises(RuntimeError, match="(?i)non-finite"):
            b._solve_validate_wells(0, walk, wd, half_rate=False)
        # the diagnostic surface was written as VALID strict JSON (no NaN)
        diag = json.loads((wd / "diagnostics.wells_only.json").read_text())
        assert diag["finite_heads"]["value"] is False
        assert diag["flow_head_delta"]["value"] is None


class TestBuilderVsGoldenPin:
    """Finding 4: a FROZEN group's built grid must reproduce its committed
    golden -- the pin FAILS loudly on any grid/hash/radius divergence, and is
    a no-op for a non-frozen (walker) group."""

    def test_pin_noop_when_no_golden(self, monkeypatch):
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)
        b._pin_built_grid_to_frozen_golden(99, {"any": "spec"}, {"hash": "z"}, 62.0)  # no raise

    def test_pin_raises_on_aggregate_hash_divergence(self, monkeypatch):
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: {
            "aggregate_hash": "GOLDEN", "array_hashes": {}, "faithful_riv": {"hash": "RIV"},
            "radius_used": 70.0,
        })
        monkeypatch.setattr(b.cfc, "spec_canonical_hashes", lambda spec: ("DIFFERENT", {}))
        with pytest.raises(RuntimeError, match="(?i)diverged|golden"):
            b._pin_built_grid_to_frozen_golden(2, {"s": 1}, {"hash": "RIV"}, 70.0)

    def test_pin_raises_on_faithful_riv_or_radius_divergence(self, monkeypatch):
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: {
            "aggregate_hash": "GOLDEN", "array_hashes": {}, "faithful_riv": {"hash": "RIV"},
            "radius_used": 70.0,
        })
        monkeypatch.setattr(b.cfc, "spec_canonical_hashes", lambda spec: ("GOLDEN", {}))
        # wrong faithful_riv hash
        with pytest.raises(RuntimeError, match="(?i)faithful_riv|diverged"):
            b._pin_built_grid_to_frozen_golden(2, {"s": 1}, {"hash": "OTHER"}, 70.0)
        # wrong radius
        with pytest.raises(RuntimeError, match="(?i)radius|diverged"):
            b._pin_built_grid_to_frozen_golden(2, {"s": 1}, {"hash": "RIV"}, 62.0)

    def test_pin_passes_when_all_match(self, monkeypatch):
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: {
            "aggregate_hash": "GOLDEN", "array_hashes": {"a": "1"},
            "faithful_riv": {"hash": "RIV"}, "radius_used": 70.0,
        })
        monkeypatch.setattr(b.cfc, "spec_canonical_hashes", lambda spec: ("GOLDEN", {"a": "1"}))
        b._pin_built_grid_to_frozen_golden(2, {"s": 1}, {"hash": "RIV"}, 70.0)  # no raise


# =============================================================================
# Unsupported-state guard + state-(iii) interface + grep gate.
# =============================================================================
class TestContract:
    def test_unsupported_state_raises_not_implemented(self, tmp_path):
        # a genuinely unsupported state (baseline/wells_only/wells_plus_scenario
        # are all handled) must raise NotImplementedError.
        with pytest.raises(NotImplementedError, match="(?i)state"):
            b.build_flow_state(0, "transport_coupled_future", work_dir=tmp_path)

    def test_half_rate_on_non_wells_state_raises(self, tmp_path):
        with pytest.raises(ValueError, match="(?i)half_rate"):
            b.build_flow_state(0, "baseline", half_rate=True, work_dir=tmp_path)

    def test_state_iii_interface_declares_required_keys(self):
        fake_result = {
            "grid_hash": "abc123", "headfile": "/x/group0_baseline.hds",
            "budgetfile": "/x/group0_baseline.cbc", "gwf_name": "group0_baseline",
            "stress_period": dict(b.STRESS_PERIOD), "units": dict(b.UNITS),
        }
        iface = b.state_iii_interface(fake_result)
        assert set(iface.keys()) == set(b.STATE_III_INTERFACE_KEYS)
        assert iface["no_regridding"] is True
        assert iface["grid_hash"] == "abc123"
        assert iface["state_id"] == "wells_plus_scenario"

    def test_state_iii_interface_grid_hash_binds_to_manifest(self):
        manifest = json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())
        fake_result = {
            "grid_hash": manifest["aggregate_hash"], "headfile": "/x/h.hds",
            "budgetfile": "/x/b.cbc", "gwf_name": "g0", "stress_period": {}, "units": {},
        }
        iface = b.state_iii_interface(fake_result)
        assert iface["grid_hash"] == manifest["aggregate_hash"]

    def test_builder_does_not_import_the_golden_generator(self):
        src = (SRC_DIR / "casestudy_flow_builder.py").read_text()
        import re
        assert not re.search(r"^\s*import\s+casestudy_flow_golden", src, re.MULTILINE)
        assert not re.search(r"^\s*from\s+casestudy_flow_golden\s+import", src, re.MULTILINE)

    def test_grep_gate_no_legacy_strings(self):
        low = (SRC_DIR / "casestudy_flow_builder.py").read_text().lower()
        assert "nwt" not in low
        assert "modflow-nwt" not in low
        assert "telescop" not in low
