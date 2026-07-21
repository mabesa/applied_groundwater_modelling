"""
Tests for M2a.3 — the 6 scenario transforms (`casestudy_flow_scenarios`), the
FROZEN expectation table, and the state-(iii) builder path.

Cheap/pure tests (no mf6): each transform's EXACT mutation + sign + validity
(reject-not-clamp stage>rbot+clearance, area-weighted recharge, K33-untouched,
CHD-only-changed, non-positive-factor rejected, immutable-RIV topology); the
expectation-consistency evaluator per assertion class; the frozen-table sanity.
The real state-(iii) build (same-grid, diagnostics, expectation) is mf6-gated.

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_scenarios.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import casestudy_flow_scenarios as scn  # noqa: E402


# --- a small synthetic spec with 4 cells, 2 CHD, 2 RIV -----------------------
def make_spec(**overrides):
    spec = {
        "chd_cellid": [(0, 0), (0, 2)], "chd_head": [8.0, 9.0],
        "riv_cellid": [(0, 1), (0, 3)], "riv_stage": [7.5, 6.0],
        "riv_cond": [50.0, 20.0], "riv_rbot": [6.0, 5.0],
        "rch": np.array([1e-4, 1.5e-4, 1e-4, 2e-4]),
        "k": np.array([7.5, 3.25, 12.0, 5.0]),
        "top": np.array([10.0] * 4), "botm": np.array([0.0] * 4),
        "idomain": np.ones(4, dtype=int),
    }
    spec.update(overrides)
    return spec


# The fields a transform may legitimately touch (for the "only-X-changed" checks).
_ARRAY_FIELDS = ("chd_head", "riv_stage", "riv_cond", "riv_rbot", "rch", "k")


def _changed_fields(before, after):
    changed = []
    for f in _ARRAY_FIELDS:
        a, b = np.asarray(before[f], dtype=float), np.asarray(after[f], dtype=float)
        if a.shape != b.shape or not np.array_equal(a, b):
            changed.append(f)
    return changed


# =============================================================================
# Exact mutation + sign per transform.
# =============================================================================
class TestTransforms:
    def test_chd_head_change_only_chd(self):
        spec = make_spec()
        new = scn.apply_scenario(spec, "chd_head_change", {"chd_head_change_m": -1})
        assert new["chd_head"] == [7.0, 8.0]
        assert _changed_fields(spec, new) == ["chd_head"]
        # input spec untouched, RIV topology (cellids) immutable
        assert spec["chd_head"] == [8.0, 9.0]
        assert new["riv_cellid"] is spec["riv_cellid"]

    def test_river_conductance_scales_values_only(self):
        spec = make_spec()
        new = scn.apply_scenario(spec, "river_conductance", {"conductance_factor": 0.8})
        assert new["riv_cond"] == [40.0, 16.0]
        assert _changed_fields(spec, new) == ["riv_cond"]
        # IMMUTABLE RIV: cellids/stage/rbot unchanged
        assert new["riv_cellid"] is spec["riv_cellid"]
        assert new["riv_stage"] is spec["riv_stage"]
        assert new["riv_rbot"] is spec["riv_rbot"]

    def test_recharge_scale_uniform_and_area_weighted_sum(self):
        spec = make_spec()
        f = 1.2
        new = scn.apply_scenario(spec, "recharge_scale", {"recharge_factor": f})
        assert np.allclose(new["rch"], np.asarray(spec["rch"]) * f)
        assert _changed_fields(spec, new) == ["rch"]
        # area-weighted Sigma recharge scales to f (uniform areas or not)
        areas = np.array([100.0, 250.0, 80.0, 300.0])
        s_before = float(np.sum(np.asarray(spec["rch"]) * areas))
        s_after = float(np.sum(np.asarray(new["rch"]) * areas))
        assert s_after == pytest.approx(f * s_before)

    def test_river_stage_shift_and_reject_not_clamp(self):
        spec = make_spec()
        new = scn.apply_scenario(spec, "river_stage", {"stage_change_m": 1.5})
        assert new["riv_stage"] == [9.0, 7.5]
        assert _changed_fields(spec, new) == ["riv_stage"]
        # a stage drop that inverts a reach (stage <= rbot + clearance) REJECTS
        bad = make_spec(riv_stage=[6.0005, 6.5], riv_rbot=[6.0, 5.0])
        with pytest.raises(ValueError, match="(?i)invert|reject"):
            scn.apply_scenario(bad, "river_stage", {"stage_change_m": -0.001})

    def test_river_width_and_stage_cond_and_depth_fraction(self):
        spec = make_spec()
        new = scn.apply_scenario(
            spec, "river_width_and_stage", {"width_factor": 1.5, "stage_change_factor": -0.5},
        )
        # width feeds conductance linearly
        assert new["riv_cond"] == [75.0, 30.0]
        # stage += s*(stage - rbot): reach0 7.5 - 0.5*1.5 = 6.75; reach1 6.0 - 0.5*1.0 = 5.5
        assert new["riv_stage"] == [6.75, 5.5]
        assert sorted(_changed_fields(spec, new)) == ["riv_cond", "riv_stage"]
        # reject-not-clamp: a huge negative depth fraction inverts -> raise
        with pytest.raises(ValueError, match="(?i)invert|reject"):
            scn.apply_scenario(spec, "river_width_and_stage",
                               {"width_factor": 1.5, "stage_change_factor": -1.5})

    def test_aquifer_transmissivity_global_kh_no_k33(self):
        spec = make_spec()
        new = scn.apply_scenario(spec, "aquifer_transmissivity", {"transmissivity_factor": 1.2})
        assert np.allclose(new["k"], np.asarray(spec["k"]) * 1.2)
        assert _changed_fields(spec, new) == ["k"]
        assert np.all(np.asarray(new["k"]) > 0)
        assert "k33" not in new  # K33 untouched / not introduced (inert at nlay=1)

    @pytest.mark.parametrize("stype,params", [
        ("river_conductance", {"conductance_factor": 0.0}),
        ("river_conductance", {"conductance_factor": -1.0}),
        ("recharge_scale", {"recharge_factor": 0.0}),
        ("recharge_scale", {"recharge_factor": -0.5}),
        ("aquifer_transmissivity", {"transmissivity_factor": 0.0}),
        ("river_width_and_stage", {"width_factor": -1.0, "stage_change_factor": 0.0}),
    ])
    def test_non_positive_factor_rejected(self, stype, params):
        with pytest.raises(ValueError, match="(?i)must be > 0|invalid"):
            scn.apply_scenario(make_spec(), stype, params)

    def test_unknown_scenario_type_rejected(self):
        with pytest.raises(ValueError, match="(?i)unknown scenario_type"):
            scn.apply_scenario(make_spec(), "not_a_scenario", {})

    def test_missing_param_rejected(self):
        with pytest.raises(ValueError, match="(?i)missing required key"):
            scn.apply_scenario(make_spec(), "chd_head_change", {})


# =============================================================================
# FROZEN expectation table + evaluator.
# =============================================================================
class TestFrozenExpectations:
    def test_table_is_frozen_and_matches_config_types(self):
        exp = scn.load_expectations()
        assert exp["frozen_before_run"] is True
        assert set(exp["groups"].keys()) == set(range(9))
        import case_utils as cu
        from casestudy_flow_builder import DEFAULT_FLOW_CONFIG
        for g in range(9):
            cfg = cu.get_scenario_for_group(str(DEFAULT_FLOW_CONFIG), g)
            assert exp["groups"][g]["scenario_type"] == cfg["type"], f"group {g} type mismatch"

    def _base_metrics(self, **over):
        m = {
            "max_abs_head_change": 1.0, "mean_head_change": 0.0,
            "argmax_dist_to_chd_m": 0.0, "argmax_dist_to_riv_m": 0.0,
            "river_to_aquifer_flux": {"ii": -6400.0, "iii": -6400.0},
            "abs_river_exchange": {"ii": 6400.0, "iii": 6400.0},
            "n_active": 4000, "n_responding": 2000, "n_dry_iii": 0, "finite_iii": True,
        }
        m.update(over)
        return m

    def test_clear_sign_increase_consistent_and_violation(self):
        # G1: abs_river_exchange must INCREASE
        ok = scn.evaluate_scenario_expectation(1, self._base_metrics(
            abs_river_exchange={"ii": 6400.0, "iii": 6900.0}))
        assert ok["consistent"] and ok["assertion_class"] == "clear_sign"
        bad = scn.evaluate_scenario_expectation(1, self._base_metrics(
            abs_river_exchange={"ii": 6400.0, "iii": 6100.0}))
        assert not bad["consistent"] and bad["problems"]

    def test_clear_sign_mean_head_rise_drop(self):
        assert scn.evaluate_scenario_expectation(3, self._base_metrics(mean_head_change=0.02))["consistent"]
        assert not scn.evaluate_scenario_expectation(3, self._base_metrics(mean_head_change=-0.02))["consistent"]
        assert scn.evaluate_scenario_expectation(4, self._base_metrics(mean_head_change=-0.02))["consistent"]

    def test_river_to_aquifer_flux_increase_g5(self):
        ok = scn.evaluate_scenario_expectation(5, self._base_metrics(
            river_to_aquifer_flux={"ii": -6400.0, "iii": 1500.0}))
        assert ok["consistent"]

    def test_feature_local_localized_vs_far(self):
        # G0 (chd): argmax must be near a CHD cell
        near = scn.evaluate_scenario_expectation(0, self._base_metrics(argmax_dist_to_chd_m=10.0))
        assert near["consistent"] and near["assertion_class"] == "feature_local"
        far = scn.evaluate_scenario_expectation(0, self._base_metrics(argmax_dist_to_chd_m=5000.0))
        assert not far["consistent"]

    def test_global_spread_vs_localized_and_dry(self):
        # G7 (global): needs spread + no-dry
        ok = scn.evaluate_scenario_expectation(7, self._base_metrics(n_responding=2000))
        assert ok["consistent"] and ok["assertion_class"] == "global"
        localized = scn.evaluate_scenario_expectation(7, self._base_metrics(n_responding=10))
        assert not localized["consistent"]
        dry = scn.evaluate_scenario_expectation(7, self._base_metrics(n_dry_iii=5))
        assert not dry["consistent"]

    def test_no_response_flags_inconsistent(self):
        # zero response fails PRESENT for every class
        for g in range(9):
            r = scn.evaluate_scenario_expectation(g, self._base_metrics(max_abs_head_change=0.0))
            assert not r["consistent"]

    def test_config_param_match_required(self):
        # Finding 4: the frozen expectation is only valid for the EXACT frozen
        # scenario -- a config with the right TYPE but a changed PARAM must fail.
        exp = scn.load_expectations()
        # group 1: river_conductance, conductance_factor 1.2
        good = {"type": "river_conductance", "conductance_factor": 1.2}
        scn.assert_config_matches_frozen(1, good, exp["groups"][1])  # no raise
        # evaluate with a matching config also fine
        r = scn.evaluate_scenario_expectation(
            1, self._base_metrics(abs_river_exchange={"ii": 6400.0, "iii": 6900.0}),
            config_scenario=good)
        assert r["consistent"]
        # a CHANGED param (0.9 != frozen 1.2) fails loudly
        with pytest.raises(ValueError, match="(?i)frozen|param"):
            scn.evaluate_scenario_expectation(
                1, self._base_metrics(), config_scenario={"type": "river_conductance", "conductance_factor": 0.9})
        # a CHANGED type also fails
        with pytest.raises(ValueError, match="(?i)type|frozen"):
            scn.assert_config_matches_frozen(1, {"type": "recharge_scale", "recharge_factor": 1.2}, exp["groups"][1])


# =============================================================================
# Grep gate: no legacy strings.
# =============================================================================
def test_grep_gate_no_legacy_strings():
    low = (SRC_DIR / "casestudy_flow_scenarios.py").read_text().lower()
    assert "nwt" not in low and "telescop" not in low and "modflow-nwt" not in low
