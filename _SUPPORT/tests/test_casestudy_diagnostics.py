"""
Tests for M1.4 -- the model-diagnostic spec + machine schema
(casestudy_diagnostics + casestudy_diagnostic_schema.yaml +
casestudy_diagnostic_spec.md).

SPEC-ONLY (no model run): the shipped schema lints; malformed entries are
rejected; the spec and schema describe the SAME diagnostic id set; the
evaluate() band logic is correct; deterministic.

Run with: uv run pytest _SUPPORT/tests/test_casestudy_diagnostics.py -v
"""
from __future__ import annotations

import copy
import os
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import casestudy_diagnostics as cd  # noqa: E402

_SRC = Path(__file__).resolve().parents[1] / "src"
SCHEMA_PATH = _SRC / "casestudy_diagnostic_schema.yaml"
SPEC_PATH = _SRC / "casestudy_diagnostic_spec.md"

# The full catalog (per the M1.4 plan) -- exactly these ids, no more/less.
EXPECTED_IDS = {
    # flow (M2a)
    "flow_convergence", "flow_mass_balance", "finite_heads", "flow_no_dry_cells", "flow_head_delta",
    # transport (M3a)
    "transport_convergence", "transport_mass_balance", "finite_conc", "concentration_nonnegative",
    "src_units", "source_in_domain", "grid_peclet", "courant", "capture_stability",
    "capture_fraction_bounds",
    # coupling (M3b)
    "coupled_or_fallback_label", "coupling_artifact_identity", "well_sink_mapping",
    # cross-cutting
    "time_unit_consistency",
}


@pytest.fixture(scope="module")
def schema() -> dict:
    return cd.load_schema(SCHEMA_PATH)


# ---------------------------------------------------------------------------
# schema loads + lints, and covers the full catalog
# ---------------------------------------------------------------------------
def test_schema_lints_clean(schema):
    assert schema["reporting_surface"] == "diagnostics.json"
    assert len(schema["diagnostics"]) == len(EXPECTED_IDS)


def test_schema_ids_are_exactly_the_catalog(schema):
    assert {d["id"] for d in schema["diagnostics"]} == EXPECTED_IDS


def test_every_entry_has_all_contract_fields(schema):
    for d in schema["diagnostics"]:
        for f in cd._REQUIRED_FIELDS:
            assert f in d, f"{d.get('id')}: missing {f}"
        for f in cd._REQUIRED_ARTIFACT:
            assert f in d["input_artifact"], f"{d['id']}: input_artifact missing {f}"
        for f in cd._REQUIRED_OUTPUT:
            assert f in d["output"], f"{d['id']}: output missing {f}"
        assert d["output"]["json_key"] == d["id"]
        assert d["output"]["path"] == "diagnostics.json"
        assert "justification" in d and d["justification"]


def test_enums_valid(schema):
    for d in schema["diagnostics"]:
        assert d["aggregation"] in cd.AGGREGATIONS
        assert d["comparator"] in cd.COMPARATORS
        assert d["severity"] in cd.SEVERITIES
        assert d["owner"] in cd.OWNERS
        assert d["enforced"] in cd.ENFORCED
        assert d["output"]["type"] in cd.OUTPUT_TYPES


def test_owners_assigned_no_orphan(schema):
    by_owner = {}
    for d in schema["diagnostics"]:
        by_owner.setdefault(d["owner"], []).append(d["id"])
    assert set(by_owner) == {"M2a", "M3a", "M3b"}  # every owner used, none else
    # flow -> M2a, coupling -> M3b (grounding)
    assert {"flow_convergence", "flow_mass_balance", "finite_heads",
            "flow_no_dry_cells", "flow_head_delta"} <= set(by_owner["M2a"])
    assert {"coupled_or_fallback_label", "coupling_artifact_identity",
            "well_sink_mapping"} <= set(by_owner["M3b"])


def test_structural_gates_present(schema):
    ids = {d["id"] for d in schema["diagnostics"]}
    assert {"flow_mass_balance", "transport_mass_balance"} <= ids       # mass balance
    assert {"capture_stability", "capture_fraction_bounds"} <= ids       # capture/artifact
    assert {"coupled_or_fallback_label", "coupling_artifact_identity",
            "well_sink_mapping"} <= ids                                  # coupled-vs-fallback


def test_severity_split_correctness_raise_quality_warn(schema):
    """Every correctness check is raise; every accuracy/quality check is warn.
    The quality set is exactly the known accuracy flags."""
    by_id = {d["id"]: d for d in schema["diagnostics"]}
    quality = {"flow_head_delta", "grid_peclet", "courant", "capture_stability"}
    for did, d in by_id.items():
        if did in quality:
            assert d["severity"] == "warn", f"{did} should be a quality warn"
        else:
            assert d["severity"] == "raise", f"{did} should be a correctness raise"


def test_thresholds_match_plan(schema):
    by_id = {d["id"]: d for d in schema["diagnostics"]}
    assert by_id["flow_mass_balance"]["raise_threshold"] == 1.0
    assert by_id["flow_mass_balance"]["abs_tol"] == pytest.approx(1e-6)
    assert by_id["transport_mass_balance"]["raise_threshold"] == 1.0
    assert by_id["grid_peclet"]["warn_threshold"] == 2.0
    assert by_id["grid_peclet"]["aggregation"] == "p95"
    assert by_id["courant"]["warn_threshold"] == 1.0
    assert by_id["capture_stability"]["warn_threshold"] == 0.05
    assert by_id["flow_head_delta"]["warn_threshold"] == 5.0
    assert by_id["concentration_nonnegative"]["warn_threshold"] == pytest.approx(-1e-6)
    assert by_id["capture_fraction_bounds"]["comparator"] == "in"


def test_emitter_names_referenced_in_spec():
    txt = SPEC_PATH.read_text()
    for name in ("PeL_", "_courant_nstp", "smassrate", "capture_fraction"):
        assert name in txt, f"spec should reference existing emitter {name!r}"


# ---------------------------------------------------------------------------
# malformed schemas are REJECTED
# ---------------------------------------------------------------------------
def _base(schema) -> dict:
    return copy.deepcopy(schema)


def test_missing_field_rejected(schema):
    bad = _base(schema)
    del bad["diagnostics"][0]["comparator"]
    with pytest.raises(cd.SchemaError, match="missing required field"):
        cd.lint_schema(bad)


def test_bad_enum_rejected(schema):
    bad = _base(schema)
    bad["diagnostics"][0]["owner"] = "M9z"
    with pytest.raises(cd.SchemaError, match="owner"):
        cd.lint_schema(bad)


def test_duplicate_id_rejected(schema):
    bad = _base(schema)
    bad["diagnostics"].append(_base(schema)["diagnostics"][0])
    with pytest.raises(cd.SchemaError, match="duplicate diagnostic id"):
        cd.lint_schema(bad)


def test_band_encoding_error_rejected(schema):
    # a 'warn' severity le check must NOT carry a raise_threshold
    bad = _base(schema)
    peclet = next(d for d in bad["diagnostics"] if d["id"] == "grid_peclet")
    peclet["raise_threshold"] = 3.0
    with pytest.raises(cd.SchemaError, match="warn.*must not set a raise_threshold"):
        cd.lint_schema(bad)


def test_multiband_ordering_enforced(schema):
    bad = _base(schema)
    cn = next(d for d in bad["diagnostics"] if d["id"] == "concentration_nonnegative")
    # ge multi-band requires warn >= raise; break it
    cn["warn_threshold"] = -0.5   # now warn (-0.5) < raise (-0.01) -> invalid for ge
    with pytest.raises(cd.SchemaError, match="ge multi-band"):
        cd.lint_schema(bad)


def test_structural_with_threshold_rejected(schema):
    bad = _base(schema)
    fh = next(d for d in bad["diagnostics"] if d["id"] == "finite_heads")
    fh["raise_threshold"] = 1.0   # finite comparator must have null thresholds
    with pytest.raises(cd.SchemaError, match="structural"):
        cd.lint_schema(bad)


def test_json_key_mismatch_rejected(schema):
    bad = _base(schema)
    bad["diagnostics"][0]["output"]["json_key"] = "something_else"
    with pytest.raises(cd.SchemaError, match="json_key"):
        cd.lint_schema(bad)


# --- Codex fix 4: hardened lint -- new required checks ---
def test_missing_justification_rejected(schema):
    bad = _base(schema)
    del bad["diagnostics"][0]["justification"]
    with pytest.raises(cd.SchemaError, match="justification"):
        cd.lint_schema(bad)


def test_empty_justification_rejected(schema):
    bad = _base(schema)
    bad["diagnostics"][0]["justification"] = "   "
    with pytest.raises(cd.SchemaError, match="justification"):
        cd.lint_schema(bad)


def test_non_string_input_artifact_subfield_rejected(schema):
    bad = _base(schema)
    bad["diagnostics"][0]["input_artifact"]["unit"] = 123
    with pytest.raises(cd.SchemaError, match="input_artifact.unit"):
        cd.lint_schema(bad)


def test_non_string_output_path_rejected(schema):
    bad = _base(schema)
    bad["diagnostics"][0]["output"]["path"] = None
    with pytest.raises(cd.SchemaError, match="output.path"):
        cd.lint_schema(bad)


def test_finite_output_type_must_be_bool(schema):
    bad = _base(schema)
    fh = next(d for d in bad["diagnostics"] if d["id"] == "finite_heads")
    fh["output"]["type"] = "float"
    with pytest.raises(cd.SchemaError, match="finite.*output.type 'bool'"):
        cd.lint_schema(bad)


def test_raise_threshold_relative_must_be_bool(schema):
    bad = _base(schema)
    cn = next(d for d in bad["diagnostics"] if d["id"] == "concentration_nonnegative")
    cn["raise_threshold_relative"] = -0.01   # numeric, not bool
    with pytest.raises(cd.SchemaError, match="raise_threshold_relative must be a bool"):
        cd.lint_schema(bad)


def test_raise_threshold_relative_needs_multiband(schema):
    bad = _base(schema)
    # slap a relative flag onto a single-band warn check (grid_peclet)
    peclet = next(d for d in bad["diagnostics"] if d["id"] == "grid_peclet")
    peclet["raise_threshold_relative"] = True
    with pytest.raises(cd.SchemaError, match="raise_threshold_relative"):
        cd.lint_schema(bad)


def test_raise_threshold_relative_requires_documented_reference(schema):
    bad = _base(schema)
    cn = next(d for d in bad["diagnostics"] if d["id"] == "concentration_nonnegative")
    cn["metric"] = "min concentration over the run"   # drops the 'peak' mention
    cn["justification"] = "correctness at the raise band."
    with pytest.raises(cd.SchemaError, match="reference"):
        cd.lint_schema(bad)


def test_shipped_schema_relative_entry_is_wellformed():
    """Sanity: the one relative diagnostic in the shipped schema is valid."""
    cn = cd.DIAGNOSTICS["concentration_nonnegative"]
    assert cn["raise_threshold_relative"] is True
    assert cn["comparator"] == "ge" and cn["severity"] == "raise"
    assert cn["warn_threshold"] is not None and cn["raise_threshold"] is not None


# ---------------------------------------------------------------------------
# spec <-> schema id consistency
# ---------------------------------------------------------------------------
def _spec_table_ids() -> set:
    """Extract diagnostic ids from the owner/severity table in the spec.md
    (rows `| <id> | M2a|M3a|M3b | ...`)."""
    ids = set()
    for line in SPEC_PATH.read_text().splitlines():
        m = re.match(r"\|\s*([a-z0-9_]+)\s*\|\s*(M2a|M3a|M3b)\s*\|", line)
        if m:
            ids.add(m.group(1))
    return ids


def test_spec_and_schema_ids_match(schema):
    schema_ids = {d["id"] for d in schema["diagnostics"]}
    assert _spec_table_ids() == schema_ids == EXPECTED_IDS


# ---------------------------------------------------------------------------
# evaluate() band logic + emission shape
# ---------------------------------------------------------------------------
def test_evaluate_emission_shape():
    e = cd.evaluate("grid_peclet", 1.0)
    assert set(e.keys()) == set(cd.JSON_ENTRY_KEYS)
    assert e["aggregation"] == "p95"
    assert e["warn_threshold"] == 2.0
    assert e["triggered_severity"] in cd.TRIGGERED_SEVERITIES
    assert e["passed"] == (e["triggered_severity"] != "raise")


@pytest.mark.parametrize("value,expected", [
    (0.5, "pass"), (1.0, "pass"), (1.0000001, "raise"), (2.0, "raise")
])
def test_evaluate_le_single_raise_boundary(value, expected):
    # flow_mass_balance: le, raise 1.0
    assert cd.evaluate("flow_mass_balance", value)["triggered_severity"] == expected


@pytest.mark.parametrize("value,expected", [
    (1.9, "pass"), (2.0, "pass"), (2.01, "warn")
])
def test_evaluate_le_single_warn_boundary(value, expected):
    # grid_peclet: le, warn 2.0 (never raises)
    e = cd.evaluate("grid_peclet", value)
    assert e["triggered_severity"] == expected
    assert e["passed"] is True  # a warn still "passes" (only raise fails)


@pytest.mark.parametrize("value,ref,expected", [
    (0.0, 100.0, "pass"),            # min 0 >= -1e-6 -> pass
    (-1e-7, 100.0, "pass"),          # within solver-noise band
    (-1e-5, 100.0, "warn"),          # below noise, above -1% of peak -> warn
    (-0.5, 100.0, "warn"),           # -0.5 > -1.0 (= -1% of 100) -> warn
    (-2.0, 100.0, "raise"),          # -2.0 < -1.0 -> raise
])
def test_evaluate_ge_multiband_relative(value, ref, expected):
    # concentration_nonnegative: ge multi-band, raise RELATIVE to peak (reference)
    assert cd.evaluate("concentration_nonnegative", value, reference=ref)["triggered_severity"] == expected


# --- Codex fix 2: relative raise band REQUIRES a positive reference ---
def test_relative_threshold_missing_reference_errors():
    with pytest.raises(ValueError, match="reference"):
        cd.evaluate("concentration_nonnegative", -0.5)  # no reference


@pytest.mark.parametrize("bad_ref", [0, 0.0, -5.0])
def test_relative_threshold_nonpositive_reference_errors(bad_ref):
    with pytest.raises(ValueError, match="reference"):
        cd.evaluate("concentration_nonnegative", -0.5, reference=bad_ref)


# --- Codex fix 3: emitted entry reports the SCALED band + the reference used ---
def test_relative_threshold_emits_scaled_band_and_reference():
    e = cd.evaluate("concentration_nonnegative", -0.5, reference=100.0)
    assert e["raise_threshold"] == pytest.approx(-1.0)   # -0.01 * 100, not the raw -0.01
    assert e["reference"] == pytest.approx(100.0)
    assert e["triggered_severity"] == "warn"
    # a non-relative diagnostic reports reference=None and the static raise band
    e2 = cd.evaluate("flow_mass_balance", 0.5)
    assert e2["reference"] is None
    assert e2["raise_threshold"] == 1.0


@pytest.mark.parametrize("value,expected", [(True, "pass"), (1, "pass"), (0, "raise"), (False, "raise")])
def test_evaluate_eq_boolean(value, expected):
    assert cd.evaluate("flow_convergence", value)["triggered_severity"] == expected


def test_all_eq_bool_diagnostics_map_false_to_raise():
    """Every ==True structural check must RAISE on False (not silently pass)."""
    for did in ("flow_convergence", "transport_convergence", "source_in_domain",
                "coupled_or_fallback_label", "well_sink_mapping", "coupling_artifact_identity",
                "time_unit_consistency"):
        assert cd.evaluate(did, False)["triggered_severity"] == "raise", did
        assert cd.evaluate(did, True)["triggered_severity"] == "pass", did


@pytest.mark.parametrize("value,expected", [(0.0, "pass"), (0.5, "pass"), (1.0, "pass"),
                                            (1.2, "raise"), (-0.01, "raise")])
def test_evaluate_in_bounds(value, expected):
    assert cd.evaluate("capture_fraction_bounds", value)["triggered_severity"] == expected


# --- Codex fix 1: finite comparator is boolean-aware (False must NOT pass) ---
def test_evaluate_finite_numeric():
    assert cd.evaluate("finite_heads", 3.4)["triggered_severity"] == "pass"
    assert cd.evaluate("finite_heads", float("nan"))["triggered_severity"] == "raise"
    assert cd.evaluate("finite_heads", float("inf"))["triggered_severity"] == "raise"


@pytest.mark.parametrize("did", ["finite_heads", "finite_conc"])
def test_finite_bool_false_raises_not_passes(did):
    """CRITICAL: a finite=False all-finite flag must RAISE, not silently pass
    (float(False)==0.0 is finite)."""
    assert cd.evaluate(did, False)["triggered_severity"] == "raise"
    assert cd.evaluate(did, True)["triggered_severity"] == "pass"


# --- Codex fix 4/5: null semantics for nullable diagnostics ---
def test_nullable_none_passes():
    e = cd.evaluate("flow_head_delta", None)   # nullable (no baseline) -> pass
    assert e["value"] is None
    assert e["triggered_severity"] == "pass" and e["passed"] is True


def test_non_nullable_none_errors():
    with pytest.raises(ValueError, match="not nullable"):
        cd.evaluate("flow_mass_balance", None)


def test_evaluate_unknown_id_raises():
    with pytest.raises(KeyError):
        cd.evaluate("not_a_diagnostic", 1.0)


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------
def test_determinism_load_and_evaluate():
    s1 = cd.load_schema(SCHEMA_PATH)
    s2 = cd.load_schema(SCHEMA_PATH)
    assert [d["id"] for d in s1["diagnostics"]] == [d["id"] for d in s2["diagnostics"]]
    for did in EXPECTED_IDS:
        d = cd.DIAGNOSTICS[did]
        # pick a value that is comparator-appropriate
        val = True if d["comparator"] == "eq" else (0.5 if d["comparator"] == "in" else 0.0)
        # relative diagnostics require a positive reference
        ref = 100.0 if d.get("raise_threshold_relative") else None
        assert cd.evaluate(did, val, reference=ref) == cd.evaluate(did, val, reference=ref)


def test_module_diagnostics_matches_file(schema):
    assert set(cd.DIAGNOSTICS) == {d["id"] for d in schema["diagnostics"]}
