"""
Tests for M1.5 -- the retuning hierarchy + equalization dimensions + structural
gates + config schema (casestudy_m1_specs + the three YAMLs + the retuning MD).

SPEC-ONLY (no model run): all three YAMLs parse + lint; malformed entries are
rejected; the physics_gates_ref ids exist in M1.4's schema and its
version/hash matches (orphan/drift gate); grep patterns match the intended
stale strings and do NOT false-match surviving keys; deterministic.

Run with: uv run pytest _SUPPORT/tests/test_casestudy_m1_specs.py -v
"""
from __future__ import annotations

import copy
import hashlib
import os
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import casestudy_m1_specs as m1  # noqa: E402
import casestudy_diagnostics as cdx  # noqa: E402

_SRC = Path(__file__).resolve().parents[1] / "src"
RETUNING_MD = _SRC / "casestudy_retuning_hierarchy.md"


@pytest.fixture(scope="module")
def gates() -> dict:
    return m1.load_structural_gates()


@pytest.fixture(scope="module")
def dims() -> dict:
    return m1.load_equalization_dimensions()


@pytest.fixture(scope="module")
def config_schema() -> dict:
    return m1.load_config_schema()


# ===========================================================================
# all three YAMLs parse + lint (shipped)
# ===========================================================================
def test_all_specs_lint():
    docs = m1.lint_all()
    assert len(docs["structural_gates"]["gates"]) == 3
    assert len(docs["equalization_dimensions"]["dimensions"]) == 9
    assert {"flow", "transport"} <= set(docs["config_schema"]["configs"])


# ===========================================================================
# structural gates
# ===========================================================================
def test_gate_ids_and_owners(gates):
    by_id = {g["id"]: g for g in gates["gates"]}
    assert set(by_id) == {"legacy_modflow_nwt", "cnc_recirc_live_physics", "submodel_buffer_blocks"}
    assert by_id["legacy_modflow_nwt"]["owner_milestone"] == "M2a"
    assert by_id["cnc_recirc_live_physics"]["owner_milestone"] == "M3a"
    assert by_id["submodel_buffer_blocks"]["owner_milestone"] == "M3b"
    for g in gates["gates"]:
        assert g["expected"] == 0


# --- grep patterns match the intended stale strings + DON'T false-match survivors ---
_POS_NEG = {
    "legacy_modflow_nwt": (
        ['namefile: "limmat_valley_model_nwt.nam"', "MODFLOW-NWT", "telescope_refine", "telescoping"],
        ["mfsim.nam", 'baseline_model_name: "limmat_valley"', "sim_namefile: mfsim.nam"],
    ),
    "cnc_recirc_live_physics": (
        # CNC branch is case-insensitive: FloPy class, standalone token, mixed case
        ["flopy.mf6.ModflowGwtcnc(gwt", "ModflowGWTCNC", "Cnc", "a cnc-package source",
         "recirculation_fraction = 0.3", "recirc_fraction = x"],
        # innocent survivors must NOT match
        ["recirc = derive_from_run()", "circulation_pattern", "# recirc note only",
         "concentration_mg_L", "func_sync", "sink_conc"],
    ),
    "submodel_buffer_blocks": (
        ["    submodel:", "      buffer_north_m: 100", "buffer_west_m: 500"],
        ["submodel_note: x", "buffer_size: 5", "buffer_zone_m: 3"],
    ),
}


@pytest.mark.parametrize("gid", list(_POS_NEG))
def test_gate_pattern_positive_and_negative(gates, gid):
    pat = re.compile(next(g["pattern"] for g in gates["gates"] if g["id"] == gid))
    positives, negatives = _POS_NEG[gid]
    for s in positives:
        assert pat.search(s), f"{gid}: pattern SHOULD match {s!r}"
    for s in negatives:
        assert not pat.search(s), f"{gid}: pattern must NOT match {s!r}"


def test_recirc_gate_excludes_transport_config(gates):
    """The surviving (linted-only) recirculation_fraction config KEY is spared by
    SCOPE: the recirc gate targets code, not the transport config."""
    g = next(x for x in gates["gates"] if x["id"] == "cnc_recirc_live_physics")
    assert not any("case_config_transport.yaml" in s for s in g["scope"])
    assert all(s.endswith(".py") for s in g["scope"])


# --- physics_gates_ref: orphan-id + version/hash integrity vs M1.4 ---
def test_physics_gates_ref_ids_exist_in_m14(gates):
    ref = gates["physics_gates_ref"]
    m14_ids = set(cdx.diagnostic_ids())
    assert set(ref["ids"]) <= m14_ids
    # the exact five the plan pins
    assert set(ref["ids"]) == {"transport_mass_balance", "flow_mass_balance",
                               "capture_stability", "capture_fraction_bounds",
                               "coupled_or_fallback_label"}


def test_physics_gates_ref_version_and_hash_match_m14(gates):
    ref = gates["physics_gates_ref"]
    m14 = cdx.load_schema()
    assert str(ref["schema_version"]) == str(m14["schema_version"])
    actual = hashlib.sha256(cdx.DEFAULT_SCHEMA_PATH.read_bytes()).hexdigest()
    assert ref["schema_sha256"] == actual


def test_no_physics_threshold_restated(gates):
    """M1.5's gates file must not restate M1.4 numeric thresholds (no
    duplication) -- only reference ids."""
    txt = (_SRC / "casestudy_structural_gates.yaml").read_text()
    # M1.4 thresholds that must NOT appear here
    for restated in ("0.05", "2.0", "1.0 %", "-1e-6", "n_captured"):
        assert restated not in txt, f"structural gates must not restate M1.4 threshold {restated!r}"


# ===========================================================================
# structural-gate lint rejections
# ===========================================================================
def _g(gates):
    return copy.deepcopy(gates)


def test_bad_owner_milestone_rejected(gates):
    bad = _g(gates)
    bad["gates"][0]["owner_milestone"] = "M9z"
    with pytest.raises(m1.SpecError, match="owner_milestone"):
        m1.lint_structural_gates(bad)


def test_expected_nonzero_rejected(gates):
    bad = _g(gates)
    bad["gates"][0]["expected"] = 1
    with pytest.raises(m1.SpecError, match="expected"):
        m1.lint_structural_gates(bad)


def test_invalid_regex_rejected(gates):
    bad = _g(gates)
    bad["gates"][0]["pattern"] = "(unclosed["
    with pytest.raises(m1.SpecError, match="regex"):
        m1.lint_structural_gates(bad)


def test_orphan_physics_gate_id_rejected(gates):
    bad = _g(gates)
    bad["physics_gates_ref"]["ids"].append("not_a_real_diagnostic")
    with pytest.raises(m1.SpecError, match="orphan id"):
        m1.lint_structural_gates(bad)


def test_stale_schema_version_rejected(gates):
    bad = _g(gates)
    bad["physics_gates_ref"]["schema_version"] = "0.9"
    with pytest.raises(m1.SpecError, match="schema_version"):
        m1.lint_structural_gates(bad)


def test_stale_schema_hash_rejected(gates):
    bad = _g(gates)
    bad["physics_gates_ref"]["schema_sha256"] = "0" * 64
    with pytest.raises(m1.SpecError, match="sha256"):
        m1.lint_structural_gates(bad)


# --- Codex fix 1: diagnostic_producers_ref pins the M1.4 ids used as producers ---
def test_diagnostic_producers_ref_present_and_pinned(gates):
    ref = gates["diagnostic_producers_ref"]
    assert set(ref["ids"]) == {"flow_head_delta", "capture_fraction_bounds"}
    m14_ids = set(cdx.diagnostic_ids())
    assert set(ref["ids"]) <= m14_ids
    # same drift pin as physics_gates_ref
    assert ref["schema_version"] == gates["physics_gates_ref"]["schema_version"]
    assert ref["schema_sha256"] == gates["physics_gates_ref"]["schema_sha256"]


def test_orphan_diagnostic_producer_id_rejected(gates):
    bad = _g(gates)
    bad["diagnostic_producers_ref"]["ids"].append("not_a_real_diagnostic")
    with pytest.raises(m1.SpecError, match="orphan id"):
        m1.lint_structural_gates(bad)


def test_diagnostic_producers_ref_stale_hash_rejected(gates):
    bad = _g(gates)
    bad["diagnostic_producers_ref"]["schema_sha256"] = "0" * 64
    with pytest.raises(m1.SpecError, match="sha256"):
        m1.lint_structural_gates(bad)


def test_producer_pin_completeness_enforced(gates, dims):
    """Every M1.4:<id> producer in the dimensions must be pinned; dropping one
    from the pin fails the cross-check."""
    m1.check_producer_ids_pinned(gates, dims)   # shipped state passes
    bad = _g(gates)
    bad["diagnostic_producers_ref"]["ids"] = ["capture_fraction_bounds"]  # drop flow_head_delta
    with pytest.raises(m1.SpecError, match="not pinned"):
        m1.check_producer_ids_pinned(bad, dims)


# --- Codex fix 3: schema_path is validated for real (wrong dir fails) ---
def test_wrong_schema_path_rejected(gates):
    bad = _g(gates)
    bad["physics_gates_ref"]["schema_path"] = "_SUPPORT/src/nope/casestudy_diagnostic_schema.yaml"
    with pytest.raises(m1.SpecError, match="wrong path|resolves to"):
        m1.lint_structural_gates(bad)


def test_wrong_schema_path_basename_still_rejected(gates):
    """Even if the basename matches an existing file elsewhere, a wrong
    directory must fail (no basename/default fallback)."""
    bad = _g(gates)
    bad["physics_gates_ref"]["schema_path"] = "_SUPPORT/tests/casestudy_diagnostic_schema.yaml"
    with pytest.raises(m1.SpecError, match="wrong path|resolves to"):
        m1.lint_structural_gates(bad)


# --- Codex fix 5: the NWT gate deliberately matches COMMENTS/docstrings ---
def test_nwt_gate_matches_comments(gates):
    pat = re.compile(next(g["pattern"] for g in gates["gates"] if g["id"] == "legacy_modflow_nwt"))
    assert pat.search("    # this build used the legacy NWT model")      # comment
    assert pat.search('    """telescoping refinement of the grid."""')   # docstring
    # the rationale documents the intent explicitly
    rat = next(g["rationale"] for g in gates["gates"] if g["id"] == "legacy_modflow_nwt")
    assert "comment" in rat.lower()


# ===========================================================================
# equalization dimensions + producers
# ===========================================================================
def test_dimension_ids(dims):
    ids = {d["id"] for d in dims["dimensions"]}
    assert ids == {
        "breakthrough_timing", "advective_travel_time", "capture_prob",
        "exceedance_margin", "drawdown", "river_leakage_change",
        "gradient_change", "runtime", "interpretive_complexity",
    }


def test_breakthrough_distinct_from_travel_time(dims):
    by_id = {d["id"]: d for d in dims["dimensions"]}
    bt, tt = by_id["breakthrough_timing"], by_id["advective_travel_time"]
    assert bt["producer"] == "emit-obligation:M3a"
    assert tt["producer"] == "emit-obligation:M3a"
    assert bt["aggregation"] != tt["aggregation"]  # peak_day vs median -> distinct uses
    assert "peak" in bt["notes"].lower()
    assert "median" in tt["notes"].lower() or tt["aggregation"] == "median"


def test_each_dimension_resolves_exactly_one_producer(dims):
    m14_ids = set(cdx.diagnostic_ids())
    forms = {}
    for d in dims["dimensions"]:
        r = m1.resolve_producer(d["producer"], m14_ids)
        forms[d["id"]] = r["form"]
    # the M1.4-backed ones
    assert forms["capture_prob"] == "m1.4"
    assert forms["drawdown"] == "m1.4"
    # the reviewer one
    assert forms["interpretive_complexity"] == "reviewer"


def test_m14_backed_producers_point_at_real_ids(dims):
    m14_ids = set(cdx.diagnostic_ids())
    by_id = {d["id"]: d for d in dims["dimensions"]}
    assert by_id["capture_prob"]["producer"] == "M1.4:capture_fraction_bounds"
    assert "capture_fraction_bounds" in m14_ids
    assert by_id["drawdown"]["producer"] == "M1.4:flow_head_delta"
    assert "flow_head_delta" in m14_ids


def test_emit_obligations_enumerated(dims):
    obs = m1.emit_obligations(dims)
    assert set(obs["M2a"]) == {"river_leakage_change", "gradient_change"}
    assert set(obs["M3a"]) == {"breakthrough_timing", "advective_travel_time", "exceedance_margin"}
    assert set(obs["M2a+M3a"]) == {"runtime"}


def test_bad_producer_form_rejected():
    with pytest.raises(m1.SpecError, match="valid form"):
        m1.resolve_producer("emit:M2a")   # wrong prefix
    with pytest.raises(m1.SpecError, match="milestone"):
        m1.resolve_producer("emit-obligation:M9")
    with pytest.raises(m1.SpecError, match="does not exist"):
        m1.resolve_producer("M1.4:not_a_diagnostic")


def test_bad_kind_rejected(dims):
    bad = copy.deepcopy(dims)
    bad["dimensions"][0]["kind"] = "fuzzy"
    with pytest.raises(m1.SpecError, match="kind"):
        m1.lint_equalization_dimensions(bad)


def test_missing_dimension_field_rejected(dims):
    bad = copy.deepcopy(dims)
    del bad["dimensions"][0]["baseline_convention"]
    with pytest.raises(m1.SpecError, match="baseline_convention"):
        m1.lint_equalization_dimensions(bad)


# ===========================================================================
# config schema + case_utils consistency (ADVISORY smoke test)
# ===========================================================================
def test_config_schema_advisory_smoke_passes(config_schema):
    m1.advisory_check_config_schema_vs_case_utils(config_schema)  # must not raise


def test_advisory_check_is_documented_as_advisory():
    """Codex fix 2: the check is documented as advisory, not a coverage
    guarantee (case_utils remains the enforcement source of truth)."""
    doc = m1.advisory_check_config_schema_vs_case_utils.__doc__ or ""
    assert "ADVISORY" in doc
    assert "enforcement source of truth" in doc.lower() or "source of truth" in doc.lower()
    assert "requires updating both" in doc.lower() or "update" in doc.lower()


def test_config_schema_flow_is_mf6_no_namefile(config_schema):
    flow_keys = {k.get("path"): k for k in config_schema["configs"]["flow"]["required_keys"]}
    assert flow_keys["model.data_name"]["const"] == "flow_model_mf6"
    assert flow_keys["model.namefile"]["forbidden"] is True


def test_config_schema_transport_covers_reactions_and_threshold(config_schema):
    names = {k for _s, k in m1._iter_key_specs(config_schema["configs"]["transport"])}
    for k in ("transport.sorption", "transport.decay", "transport.distribution_coefficient_mL_g",
              "transport.first_order_decay_constant_1_per_day", "transport.half_life_days",
              "monitoring.threshold_mg_L", "doublet.concession_id", "source.type"):
        assert k in names, f"config schema missing {k}"


def test_config_schema_source_enums(config_schema):
    specs = {k: s for s, k in m1._iter_key_specs(config_schema["configs"]["transport"])}
    assert set(specs["source.type"]["enum"]) == {"point", "line", "area"}
    assert set(specs["source.release_type"]["enum"]) == {"pulse", "continuous"}


def test_config_schema_bad_type_rejected(config_schema):
    bad = copy.deepcopy(config_schema)
    bad["configs"]["flow"]["required_keys"][0]["type"] = "widget"
    with pytest.raises(m1.SpecError, match="type"):
        m1.lint_config_schema(bad)


def test_config_schema_missing_config_rejected(config_schema):
    bad = copy.deepcopy(config_schema)
    del bad["configs"]["transport"]
    with pytest.raises(m1.SpecError, match="flow.*transport|transport"):
        m1.lint_config_schema(bad)


def test_config_schema_advisory_detects_gap(config_schema):
    """Drop a case_utils-enforced key from the schema -> the advisory check
    flags the gap (within the limits of its hard-coded mirror)."""
    bad = copy.deepcopy(config_schema)
    items = bad["configs"]["transport"]["list_blocks"][0]["item_required_keys"]
    bad["configs"]["transport"]["list_blocks"][0]["item_required_keys"] = [
        k for k in items if k.get("name") != "monitoring.threshold_mg_L"
    ]
    with pytest.raises(m1.SpecError, match="threshold_mg_L"):
        m1.advisory_check_config_schema_vs_case_utils(bad)


def test_advisory_leaf_matching_requires_quoted_literal(monkeypatch):
    """Codex fix 2 (tightened): a bare COMMENT mention of an enforced leaf must
    NOT satisfy the advisory check -- it requires the quoted enforcement
    literal `"leaf"`, not any substring."""
    # point CASE_UTILS_PATH at a file that only MENTIONS the leaf in a comment
    fake = Path(__file__).resolve().parent / "_fake_case_utils_comment_only.py"
    fake.write_text("# mentions threshold_mg_L only in a comment, not as a literal\nx = 1\n")
    monkeypatch.setattr(m1, "CASE_UTILS_PATH", fake)
    try:
        with pytest.raises(m1.SpecError, match="quoted literal"):
            m1.advisory_check_config_schema_vs_case_utils()
    finally:
        fake.unlink()


# ===========================================================================
# retuning hierarchy MD -- ordered ladder + numeric envelopes + guardrails
# ===========================================================================
def test_retuning_md_has_ordered_ladder_and_numeric_envelopes():
    txt = RETUNING_MD.read_text()
    # ordered levels 1-4
    for lvl in ("Level 1", "Level 2", "Level 3", "Level 4"):
        assert lvl in txt
    # numeric envelopes
    assert "150 m" in txt          # placement
    assert "5 placement steps" in txt or "5 steps" in txt
    assert "30 %" in txt or "±30%" in txt or "30%" in txt   # magnitude
    assert "1.5 m" in txt          # CHD/river-stage
    assert "50 %" in txt or "50%" in txt   # Kd
    assert "factor of 2" in txt    # lambda
    assert "3 iterations" in txt or "3 iters" in txt


def test_retuning_md_threshold_not_a_lever_and_guardrails():
    txt = RETUNING_MD.read_text().lower()
    assert "threshold_mg_l" in txt and "not a retuning lever" in txt
    assert "anti-masking" in txt or "mask" in txt
    assert "plausib" in txt
    assert "logged roster-change review" in txt  # level 4


# ===========================================================================
# determinism
# ===========================================================================
def test_determinism():
    a = m1.lint_all()
    b = m1.lint_all()
    assert a["structural_gates"] == b["structural_gates"]
    assert a["equalization_dimensions"] == b["equalization_dimensions"]
    assert a["config_schema"] == b["config_schema"]
    assert m1.emit_obligations() == m1.emit_obligations()
