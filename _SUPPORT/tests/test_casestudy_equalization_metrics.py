"""
Tests for M2a.4 — the equalization emit-obligations
(`casestudy_equalization_metrics`): the ID set + contract fields asserted
against the LIVE M1.5 functions (anti-drift), the three obligation formulas +
censor branches, the runtime golden-omission, and a real group-0 build.

Cheap/pure tests use synthetic `state_metrics`; the real group-0
`wells_plus_scenario` build is mf6-gated.

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_equalization_metrics.py -v
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import casestudy_m1_specs as m1  # noqa: E402
import casestudy_equalization_metrics as em  # noqa: E402

GOLDEN_DIR = SRC_DIR / "golden"

_MF6 = __import__("casestudy_flow_common").resolve_mf6_exe()
_HAS_MF6 = Path(_MF6).exists() or (os.path.dirname(_MF6) == "" and __import__("shutil").which(_MF6))
requires_mf6 = pytest.mark.skipif(not _HAS_MF6, reason="real group-0 build needs mf6")


def _sm(**over):
    """A fully-valid synthetic state-iii metrics dict."""
    sm = {
        "response_metrics": {"river_to_aquifer_flux": {"ii": -6400.0, "iii": -2062.0}},
        "gradient_inputs": {
            "receptor_type": "river", "riv_cell": 10, "dist_m": 50.0,
            "head_ext_ii": 400.0, "head_ext_iii": 401.0,
            "head_riv_ii": 398.0, "head_riv_iii": 398.2,
            "ext_active": True, "riv_active": True,
            "ext_dry_ii": False, "ext_dry_iii": False,
            "riv_dry_ii": False, "riv_dry_iii": False,
        },
        "runtime_s": 3.8,
    }
    sm.update(over)
    return sm


# =============================================================================
# ANTI-DRIFT: the emitted set + contract fields vs the LIVE M1.5 functions.
# =============================================================================
class TestAntiDrift:
    def test_emitted_id_set_equals_live_obligations_no_extras(self):
        eo = m1.emit_obligations()
        live = set(eo["M2a"]) | set(eo["M2a+M3a"])
        emitted = set(em.emit_equalization_metrics(0, _sm()).keys())
        assert emitted == live, f"missing {live - emitted}, extras {emitted - live}"

    def test_each_obligation_contract_fields_match_live_dimensions(self):
        doc = m1.load_equalization_dimensions()
        by_id = {d["id"]: d for d in doc["dimensions"]}
        metrics = em.emit_equalization_metrics(0, _sm())
        for oid, entry in metrics.items():
            live = by_id[oid]
            assert entry["unit"] == live["unit"]
            assert entry["aggregation"] == live["aggregation"]
            assert entry["baseline_convention"] == live["baseline_convention"]
            assert entry["producer"] == live["producer"]

    def test_state_pairs_and_producers(self):
        m = em.emit_equalization_metrics(0, _sm())
        assert m["river_leakage_change"]["state_pair"] == ["wells_only", "wells_plus_scenario"]
        assert m["gradient_change"]["state_pair"] == ["wells_only", "wells_plus_scenario"]
        assert m["runtime"]["state_pair"] is None
        assert m["runtime"]["producer"] == "emit-obligation:M2a+M3a"


# =============================================================================
# river_leakage_change — SIGNED flux delta (never abs), % secondary field.
# =============================================================================
class TestRiverLeakageChange:
    def test_signed_flux_delta_and_pct(self):
        m = em.emit_equalization_metrics(0, _sm())["river_leakage_change"]
        assert m["value"] == pytest.approx(-2062.0 - (-6400.0))  # +4338 m3/d
        assert m["pct_of_state_ii"] == pytest.approx(100.0 * 4338.0 / 6400.0)

    def test_uses_signed_not_abs_exchange(self):
        # a case where |exchange| is unchanged but SIGNED flux flips sign:
        # abs delta would be ~0, signed delta is large. The metric must use signed.
        sm = _sm()
        sm["response_metrics"] = {
            "river_to_aquifer_flux": {"ii": -100.0, "iii": +100.0},
            "abs_river_exchange": {"ii": 100.0, "iii": 100.0},
        }
        m = em.emit_equalization_metrics(0, sm)["river_leakage_change"]
        assert m["value"] == pytest.approx(200.0)  # signed: +100 - (-100)

    def test_near_zero_state_ii_flux_pct_null(self):
        sm = _sm()
        sm["response_metrics"] = {"river_to_aquifer_flux": {"ii": 0.0, "iii": 5.0}}
        m = em.emit_equalization_metrics(0, sm)["river_leakage_change"]
        assert m["value"] == pytest.approx(5.0)
        assert m["pct_of_state_ii"] is None

    def test_censored_when_flux_missing(self):
        sm = _sm()
        sm["response_metrics"] = {}
        m = em.emit_equalization_metrics(0, sm)["river_leakage_change"]
        assert m["value"] is None and m["censored_reason"]


# =============================================================================
# gradient_change — (head_ext - head_river)/dist delta + censor branches.
# =============================================================================
class TestGradientChange:
    def test_formula(self):
        m = em.emit_equalization_metrics(0, _sm())["gradient_change"]
        # grad_ii=(400-398)/50=0.04; grad_iii=(401-398.2)/50=0.056; Δ=0.016
        assert m["value"] == pytest.approx(0.016)
        assert m["receptor_type"] == "river"

    @pytest.mark.parametrize("mutate,reason_kw", [
        ({"riv_cell": None}, "active riv"),
        ({"dist_m": 0.0}, "distance"),
        ({"ext_active": False}, "inactive"),
        ({"riv_active": False}, "inactive"),
        ({"ext_dry_iii": True}, "dry"),
        ({"riv_dry_ii": True}, "dry"),
        ({"head_ext_iii": float("nan")}, "non-finite"),
    ])
    def test_censor_branches(self, mutate, reason_kw):
        sm = _sm()
        sm["gradient_inputs"].update(mutate)
        m = em.emit_equalization_metrics(0, sm)["gradient_change"]
        assert m["value"] is None
        assert reason_kw.lower() in m["censored_reason"].lower()

    def test_censored_when_gradient_inputs_missing(self):
        sm = _sm()
        del sm["gradient_inputs"]
        m = em.emit_equalization_metrics(0, sm)["gradient_change"]
        assert m["value"] is None and m["censored_reason"]


# =============================================================================
# runtime — positive, non-hashed (never in a golden), censored when absent.
# =============================================================================
class TestRuntime:
    def test_positive_runtime(self):
        m = em.emit_equalization_metrics(0, _sm(runtime_s=2.5))["runtime"]
        assert m["value"] == pytest.approx(2.5) and m["value"] > 0

    def test_censored_when_absent_or_nonpositive(self):
        for rt in (None, 0.0, -1.0):
            sm = _sm()
            sm["runtime_s"] = rt
            m = em.emit_equalization_metrics(0, sm)["runtime"]
            assert m["value"] is None and m["censored_reason"]

    def test_runtime_not_in_any_committed_golden(self):
        # runtime is a metric, NEVER a golden/hashed field.
        for manifest in GOLDEN_DIR.glob("group*_flow.manifest.json"):
            text = manifest.read_text()
            assert "runtime" not in text, f"{manifest.name} must not contain runtime"
        for npz in GOLDEN_DIR.glob("group*_flow.npz"):
            import numpy as np
            with np.load(npz) as z:
                assert not any("runtime" in n for n in z.files), f"{npz.name} has a runtime array"


# =============================================================================
# writer + surface shape.
# =============================================================================
class TestWriter:
    def test_writes_per_group_file_strict_json(self, tmp_path):
        metrics = em.emit_equalization_metrics(3, _sm())
        p = em.write_equalization_metrics(3, metrics, tmp_path)
        assert p.name == "equalization_metrics.3.json"
        loaded = json.loads(p.read_text())  # strict JSON (no NaN)
        assert set(loaded.keys()) == {"river_leakage_change", "gradient_change", "runtime"}
        for entry in loaded.values():
            assert "value" in entry and "unit" in entry and "producer" in entry
            assert "provenance_input_ids" in entry

    def test_censored_entries_serialize_with_null(self, tmp_path):
        sm = _sm()
        del sm["gradient_inputs"]
        p = em.write_equalization_metrics(5, em.emit_equalization_metrics(5, sm), tmp_path)
        loaded = json.loads(p.read_text())
        assert loaded["gradient_change"]["value"] is None
        assert loaded["gradient_change"]["censored_reason"]


# =============================================================================
# real group-0 wells_plus_scenario build -> all 3 obligations finite.
# =============================================================================
@requires_mf6
def test_real_group0_emits_three_finite_obligations(tmp_path):
    import casestudy_flow_builder as b

    result = b.build_flow_state(0, "wells_plus_scenario", work_dir=tmp_path)
    metrics = em.emit_equalization_metrics(0, result)
    assert set(metrics) == {"river_leakage_change", "gradient_change", "runtime"}
    for oid, entry in metrics.items():
        assert entry["value"] is not None, f"{oid} unexpectedly censored: {entry.get('censored_reason')}"
        assert float(entry["value"]) == entry["value"]  # finite
    assert metrics["runtime"]["value"] > 0
    # writer round-trips
    p = em.write_equalization_metrics(0, metrics, tmp_path)
    assert json.loads(p.read_text())["river_leakage_change"]["unit"] == "m3/d or %"


def test_grep_gate_no_legacy_strings():
    low = (SRC_DIR / "casestudy_equalization_metrics.py").read_text().lower()
    assert "nwt" not in low and "telescop" not in low and "modflow-nwt" not in low
