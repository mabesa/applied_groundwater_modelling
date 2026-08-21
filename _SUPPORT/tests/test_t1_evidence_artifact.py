"""Tests for `t1_evidence_artifact` (T1 S13 -- the T0_2b Sec 5.1 evidence-
artifact schema, its fail-closed loader, and synthetic fixtures).

Everything here is pure Python against synthetic fixtures -- no MF6, no
FloPy, no model-module import (S13 is schema/loader/fixtures only; wiring
real model output into artifacts is S14, per DESIGN_DOCS/T1_implementation_plan.md
v4 Phase 4). `TestNoModelModuleImports` below asserts that fact by source
inspection, mirroring the equivalent guard planned for S14
(`test_no_model_module_imports_the_producer`) so this schema module carries
its own half of the one-way `artifact -> model` import rule from day one.

Run with:  uv run pytest _SUPPORT/tests/test_t1_evidence_artifact.py -v
"""
from __future__ import annotations

import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import t1_evidence_artifact as t1  # noqa: E402

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _refresh_hash(raw: dict) -> dict:
    """Recompute and overwrite `content_hash` in-place, returning *raw*."""
    raw[t1._HASH_KEY] = t1.compute_content_hash(raw)
    return raw


def _fixture_raw(**overrides) -> dict:
    record = t1.build_fixture_record(run_role="spatial_series", **overrides)
    return t1.dump_record(record)


# ---------------------------------------------------------------------------
# no-model-import guard (this module's half of the Phase-4 one-way rule)
# ---------------------------------------------------------------------------


class TestNoModelModuleImports:
    _FORBIDDEN = {
        "transport_srcpulse_demo",
        "transport_prt_capture",
        "transport_base_model",
        "transport_verify_2d",
        "model_io_utils",
    }

    def test_module_imports_no_model_module(self):
        """AST-based, not substring-based: the module docstring legitimately
        *discusses* these model-module names in prose (explaining why they
        must never be imported), so a raw text search would false-positive
        on its own documentation. Only actual `import` / `from ... import`
        statements count."""
        src_path = os.path.join(os.path.dirname(t1.__file__), "t1_evidence_artifact.py")
        import ast

        with open(src_path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        imported_tops = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_tops.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_tops.add(node.module.split(".")[0])
        forbidden_hit = imported_tops & self._FORBIDDEN
        assert not forbidden_hit, f"t1_evidence_artifact.py must not import {forbidden_hit!r}"

    def test_module_imports_stdlib_only(self):
        allowed_prefixes = {
            "__future__",
            "copy",
            "hashlib",
            "json",
            "math",
            "dataclasses",
            "pathlib",
            "typing",
        }
        src_path = os.path.join(os.path.dirname(t1.__file__), "t1_evidence_artifact.py")
        import ast

        with open(src_path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top in allowed_prefixes, f"unexpected import: {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                assert top in allowed_prefixes, f"unexpected import: {node.module}"


# ---------------------------------------------------------------------------
# well-formed round trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_well_formed_fixture_round_trips_exactly(self, tmp_path):
        original = t1.build_fixture_record(run_role="spatial_series")
        path = tmp_path / "record.json"
        t1.write_record(original, path)
        loaded = t1.load_record(path)
        assert loaded == original
        assert loaded.provenance_valid is True

    @pytest.mark.parametrize("role", t1.RUN_ROLES)
    def test_every_run_role_round_trips(self, tmp_path, role):
        original = t1.build_fixture_record(run_role=role)
        path = tmp_path / f"record_{role}.json"
        t1.write_record(original, path)
        loaded = t1.load_record(path)
        assert loaded.run_role == role
        assert loaded == original
        assert loaded.provenance_valid is True

    def test_two_role_trap_is_representable(self, tmp_path):
        """The finest run of the probe case is simultaneously a
        spatial-series point AND the feasibility probe (T0_2b Sec 5.1's
        stated reason `run_role` is mandatory). Schema must be able to
        record `run_role="spatial_series"` with `is_feasibility_probe=True`
        at once."""
        original = t1.build_fixture_record(
            run_role="spatial_series", is_feasibility_probe=True, grid_role="finest"
        )
        path = tmp_path / "trap.json"
        t1.write_record(original, path)
        loaded = t1.load_record(path)
        assert loaded.run_role == "spatial_series"
        assert loaded.is_feasibility_probe is True

    def test_claim_support_state_null_is_a_string_not_json_null(self, tmp_path):
        original = t1.build_fixture_record(
            run_role="pilot", claim_support_state="null", reason_code="refinement_axis_untested"
        )
        raw = t1.dump_record(original)
        assert raw["support"]["claim_support_state"] == "null"
        assert isinstance(raw["support"]["claim_support_state"], str)
        path = tmp_path / "null_state.json"
        t1.write_record(original, path)
        loaded = t1.load_record(path)
        assert loaded.claim_support_state == "null"
        assert loaded.provenance_valid is True  # "null" state != missing field


# ---------------------------------------------------------------------------
# run_role is mandatory
# ---------------------------------------------------------------------------


class TestRunRoleMandatory:
    def test_run_role_is_mandatory_in_fixture_builder(self):
        with pytest.raises(TypeError):
            t1.build_fixture_record()  # no run_role kwarg

    def test_run_role_absent_yields_provenance_invalid_not_raise(self, tmp_path):
        raw = _fixture_raw()
        del raw["role"]["run_role"]
        _refresh_hash(raw)
        path = tmp_path / "no_role.json"
        path.write_text(json.dumps(raw))
        loaded = t1.load_record(path)  # must NOT raise
        assert loaded.run_role is None
        assert loaded.provenance_valid is False

    def test_run_role_present_but_invalid_value_raises(self, tmp_path):
        raw = _fixture_raw()
        raw["role"]["run_role"] = "not_a_real_role"
        _refresh_hash(raw)
        path = tmp_path / "bad_role.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    def test_build_fixture_record_rejects_invalid_run_role(self):
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.build_fixture_record(run_role="not_a_real_role")


# ---------------------------------------------------------------------------
# fail-closed: schema version
# ---------------------------------------------------------------------------


class TestLoaderFailsClosedOnSchemaVersion:
    def test_loader_fails_closed_on_schema_version_mismatch(self, tmp_path):
        raw = _fixture_raw()
        raw["schema"]["schema_version"] = "0.0.1-not-the-real-version"
        # deliberately do NOT refresh the hash -- schema_version is excluded
        # from hash coverage (SCHEMA DECISIONS #4), so an untouched hash
        # still matches; the version gate alone must catch this.
        path = tmp_path / "bad_version.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.SchemaVersionMismatchError):
            t1.load_record(path)

    def test_loader_fails_closed_on_missing_schema_version(self, tmp_path):
        raw = _fixture_raw()
        del raw["schema"]["schema_version"]
        path = tmp_path / "no_version.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.SchemaVersionMismatchError):
            t1.load_record(path)

    def test_schema_version_gate_precedes_hash_gate(self, tmp_path):
        """A record with BOTH a bad schema_version AND a tampered covered
        field (so the hash would also fail) must raise the version error,
        not the hash error -- version is checked first (module docstring
        SCHEMA DECISIONS #5)."""
        raw = _fixture_raw()
        raw["schema"]["schema_version"] = "9.9.9"
        raw["run_identity"]["run_id"] = "tampered-without-rehash"
        path = tmp_path / "both_bad.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.SchemaVersionMismatchError):
            t1.load_record(path)


# ---------------------------------------------------------------------------
# fail-closed: content hash
# ---------------------------------------------------------------------------


class TestLoaderFailsClosedOnContentHash:
    def test_loader_fails_closed_on_content_hash_mismatch(self, tmp_path):
        raw = _fixture_raw()
        raw["run_identity"]["run_id"] = "tampered-run-id"
        # hash NOT refreshed -> stale, must be caught
        path = tmp_path / "bad_hash.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.ContentHashMismatchError):
            t1.load_record(path)

    def test_loader_fails_closed_on_missing_content_hash(self, tmp_path):
        raw = _fixture_raw()
        del raw["content_hash"]
        path = tmp_path / "no_hash.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.ContentHashMismatchError):
            t1.load_record(path)

    def test_tampering_then_refreshing_hash_passes(self, tmp_path):
        """Sanity check on the mechanism itself: if a covered field is
        changed AND the hash is correctly recomputed, the record loads
        (this is exactly what a legitimate producer does -- it is not a
        loophole, it demonstrates the hash actually covers the field)."""
        raw = _fixture_raw()
        raw["run_identity"]["run_id"] = "a-different-but-consistent-run-id"
        _refresh_hash(raw)
        path = tmp_path / "consistent.json"
        path.write_text(json.dumps(raw))
        loaded = t1.load_record(path)
        assert loaded.run_id == "a-different-but-consistent-run-id"


# ---------------------------------------------------------------------------
# missing required field -> provenance_valid = False (not a raise)
# ---------------------------------------------------------------------------


# One representative path per top-level group, plus the two structured
# subtrees, covering every group in Sec 5.1's table at least once.
_REMOVABLE_PATHS = [
    ("schema", "producer_module"),
    ("run_identity", "run_id"),
    ("run_identity", "grid_spec"),
    ("fingerprints", "src_sha"),
    ("fingerprints", "gis_hashes"),
    ("environment", "mf6_sha256"),
    ("run_health", "solver_status"),
    ("run_health", "nstp"),
    ("metrics",),
    ("support", "claim_id"),
    ("support", "envelope"),
    ("support", "envelope", "tolerance"),
    ("support", "diagnostics"),
    ("role", "run_role"),
    ("role", "grid_role"),
]


class TestMissingRequiredFieldIsProvenanceInvalid:
    @pytest.mark.parametrize("path", _REMOVABLE_PATHS, ids=lambda p: ".".join(p))
    def test_record_missing_any_required_field_is_provenance_invalid(self, tmp_path, path):
        raw = _fixture_raw()
        node = raw
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]
        _refresh_hash(raw)
        out_path = tmp_path / ("missing_" + "_".join(path) + ".json")
        out_path.write_text(json.dumps(raw))

        loaded = t1.load_record(out_path)  # must NOT raise

        assert loaded.provenance_valid is False
        assert ".".join(path) in t1.missing_required_fields(raw)

    def test_well_formed_record_reports_no_missing_fields(self):
        raw = _fixture_raw()
        assert t1.missing_required_fields(raw) == ()

    def test_producer_declaring_true_cannot_override_incompleteness(self, tmp_path):
        """A buggy/dishonest producer that writes `provenance_valid: true`
        on an otherwise-incomplete record must still load as False -- the
        loader recomputes, it never trusts the declared value upward."""
        raw = _fixture_raw()
        raw["run_health"]["provenance_valid"] = True
        del raw["fingerprints"]["roster_hash"]
        _refresh_hash(raw)
        path = tmp_path / "dishonest.json"
        path.write_text(json.dumps(raw))
        loaded = t1.load_record(path)
        assert loaded.provenance_valid is False

    def test_declared_false_on_complete_record_stays_false(self, tmp_path):
        """The AND is not one-directional in a way that fabricates trust:
        a structurally complete record whose producer declared
        provenance_valid=false stays false."""
        record = t1.build_fixture_record(run_role="pilot", provenance_valid=False)
        path = tmp_path / "declared_false.json"
        t1.write_record(record, path)
        loaded = t1.load_record(path)
        assert loaded.provenance_valid is False


# ---------------------------------------------------------------------------
# content hash coverage
# ---------------------------------------------------------------------------


class TestContentHashCoverage:
    def test_hash_changes_when_a_covered_field_changes(self):
        raw = _fixture_raw()
        base_hash = raw["content_hash"]

        mutated = copy.deepcopy(raw)
        mutated["run_identity"]["run_id"] = "a-completely-different-run-id"
        new_hash = t1.compute_content_hash(mutated)

        assert new_hash != base_hash

    @pytest.mark.parametrize(
        "path,new_value",
        [
            (("run_identity", "cr_target"), 0.225),
            (("fingerprints", "src_sha"), "f" * 64),
            (("environment", "mf6_sha256"), "e" * 64),
            (("run_health", "cr_achieved"), 0.123456789),
            (("support", "claim_support_state"), "not_supported"),
            (("role", "is_feasibility_probe"), True),
        ],
    )
    def test_hash_changes_for_each_covered_group(self, path, new_value):
        raw = _fixture_raw()
        base_hash = t1.compute_content_hash(raw)
        mutated = copy.deepcopy(raw)
        node = mutated
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = new_value
        assert t1.compute_content_hash(mutated) != base_hash

    def test_hash_changes_for_a_metric_value(self):
        raw = _fixture_raw()
        base_hash = t1.compute_content_hash(raw)
        mutated = copy.deepcopy(raw)
        mutated["metrics"]["peak_mgL"]["value"] = 9.999
        assert t1.compute_content_hash(mutated) != base_hash

    def test_hash_does_not_change_for_the_uncovered_schema_version_field(self):
        raw = _fixture_raw()
        base_hash = t1.compute_content_hash(raw)
        mutated = copy.deepcopy(raw)
        mutated["schema"]["schema_version"] = "some-other-version-string"
        assert t1.compute_content_hash(mutated) == base_hash

    def test_hash_ignores_the_content_hash_field_itself(self):
        raw = _fixture_raw()
        base_hash = t1.compute_content_hash(raw)
        mutated = copy.deepcopy(raw)
        mutated["content_hash"] = "irrelevant-prior-value"
        assert t1.compute_content_hash(mutated) == base_hash

    def test_hash_is_sensitive_to_float_bit_pattern_not_json_text(self):
        """Convention pinned in the module docstring: floats are hashed via
        float.hex(), so two values that differ only far beyond a naive
        decimal comparison still produce different hashes, and NaN/Infinity
        are rejected outright."""
        raw = _fixture_raw()
        mutated = copy.deepcopy(raw)
        mutated["run_identity"]["cr_target"] = 0.9 + 1e-15
        assert t1.compute_content_hash(mutated) != t1.compute_content_hash(raw)

        bad = copy.deepcopy(raw)
        bad["run_identity"]["cr_target"] = float("nan")
        with pytest.raises(ValueError):
            t1.compute_content_hash(bad)

    def test_hash_is_deterministic_across_key_insertion_order(self):
        raw = _fixture_raw()
        # Force a different top-level key order by rebuilding via a fresh dict
        shuffled = {}
        for k in reversed(list(raw.keys())):
            shuffled[k] = raw[k]
        assert t1.compute_content_hash(shuffled) == t1.compute_content_hash(raw)


# ---------------------------------------------------------------------------
# closed enumerations
# ---------------------------------------------------------------------------


class TestClosedEnumerations:
    def test_claim_support_state_rejects_unknown_value(self, tmp_path):
        raw = _fixture_raw()
        raw["support"]["claim_support_state"] = "definitely_not_a_state"
        _refresh_hash(raw)
        path = tmp_path / "bad_state.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    def test_reason_code_rejects_unknown_value(self, tmp_path):
        raw = _fixture_raw()
        raw["support"]["reason_code"] = "made_up_reason"
        _refresh_hash(raw)
        path = tmp_path / "bad_reason.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    @pytest.mark.parametrize("state", t1.CLAIM_SUPPORT_STATES)
    def test_every_claim_support_state_is_accepted(self, tmp_path, state):
        record = t1.build_fixture_record(run_role="pilot", claim_support_state=state)
        path = tmp_path / f"state_{state}.json"
        t1.write_record(record, path)
        loaded = t1.load_record(path)
        assert loaded.claim_support_state == state

    @pytest.mark.parametrize("code", t1.REASON_CODES)
    def test_every_reason_code_is_accepted(self, tmp_path, code):
        record = t1.build_fixture_record(run_role="pilot", reason_code=code)
        path = tmp_path / f"reason_{code}.json"
        t1.write_record(record, path)
        loaded = t1.load_record(path)
        assert loaded.reason_code == code


# ---------------------------------------------------------------------------
# metrics / envelope / gis_hashes structural rules
# ---------------------------------------------------------------------------


class TestStructuredSubfields:
    def test_metrics_must_be_non_empty(self, tmp_path):
        raw = _fixture_raw()
        raw["metrics"] = {}
        _refresh_hash(raw)
        path = tmp_path / "empty_metrics.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    def test_gis_hashes_missing_rivers_key_raises(self, tmp_path):
        raw = _fixture_raw()
        del raw["fingerprints"]["gis_hashes"]["rivers"]
        _refresh_hash(raw)
        path = tmp_path / "no_rivers.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    def test_censored_metric_may_have_null_value(self, tmp_path):
        metrics = {
            "t_peak": t1.MetricRecord(
                value=None,
                units="d",
                algorithm_id="lattice_argmax_v1",
                interpolated=False,
                censored=True,
                tie_broken=False,
            )
        }
        record = t1.build_fixture_record(run_role="temporal_series", metrics=metrics)
        path = tmp_path / "censored.json"
        t1.write_record(record, path)
        loaded = t1.load_record(path)
        assert loaded.metrics["t_peak"].value is None
        assert loaded.metrics["t_peak"].censored is True
        assert loaded.provenance_valid is True  # legitimate null, key still present

    def test_envelope_nullable_threshold_record_id_round_trips(self, tmp_path):
        envelope = t1.SupportEnvelope(
            grid_series=(50.0, 20.0, 10.0, 5.0, 2.0),
            timestep_series=(0.9,),
            stopping_rule="feasibility_ceiling",
            tolerance=0.02,
            threshold_record_id=None,
        )
        record = t1.build_fixture_record(run_role="feasibility_probe", envelope=envelope)
        path = tmp_path / "no_threshold.json"
        t1.write_record(record, path)
        loaded = t1.load_record(path)
        assert loaded.envelope.threshold_record_id is None
        assert loaded.provenance_valid is True


# ---------------------------------------------------------------------------
# loads_record (string-based loader) parity
# ---------------------------------------------------------------------------


class TestLoadsRecordParity:
    def test_loads_record_matches_load_record(self, tmp_path):
        record = t1.build_fixture_record(run_role="b_control")
        path = tmp_path / "parity.json"
        t1.write_record(record, path)
        from_path = t1.load_record(path)
        from_string = t1.loads_record(path.read_text())
        assert from_path == from_string

    def test_loads_record_fails_closed_on_hash_mismatch(self):
        raw = _fixture_raw()
        raw["run_identity"]["case_id"] = "tampered"
        with pytest.raises(t1.ContentHashMismatchError):
            t1.loads_record(json.dumps(raw))


# ---------------------------------------------------------------------------
# diagnostics (T1 S6 operator A -- SCHEMA_VERSION 2.0.0 addition)
# ---------------------------------------------------------------------------


def _computed_diagnostic(**overrides) -> t1.DiagnosticRecord:
    fields = dict(
        label="observation_support_robustness",
        status="computed",
        algorithm_id="operator_a_disc_v1",
        radius_m=25.0,
        centre_xy_m=(2683450.0, 1248230.0),
        times=(10.0, 20.0, 30.0),
        values=(0.12, 0.34, 0.29),
        reason=None,
    )
    fields.update(overrides)
    return t1.DiagnosticRecord(**fields)


def _not_applicable_diagnostic(**overrides) -> t1.DiagnosticRecord:
    fields = dict(
        label="observation_support_robustness",
        status="not_applicable",
        algorithm_id="operator_a_disc_v1",
        radius_m=25.0,
        centre_xy_m=(2683450.0, 1248230.0),
        times=(),
        values=(),
        reason="disc diameter (50 m) is not smaller than the native cell (50 m)",
    )
    fields.update(overrides)
    return t1.DiagnosticRecord(**fields)


class TestDiagnosticRoundTrip:
    def test_computed_diagnostic_round_trips_exactly_series_intact(self, tmp_path):
        diag = _computed_diagnostic()
        record = t1.build_fixture_record(
            run_role="spatial_series",
            diagnostics={"observation_support_robustness": diag},
        )
        path = tmp_path / "diag.json"
        raw = t1.write_record(record, path)
        assert raw["support"]["diagnostics"]["observation_support_robustness"]["times"] == [
            10.0,
            20.0,
            30.0,
        ]
        assert raw["support"]["diagnostics"]["observation_support_robustness"]["values"] == [
            0.12,
            0.34,
            0.29,
        ]
        loaded = t1.load_record(path)
        assert loaded == record
        assert loaded.diagnostics["observation_support_robustness"] == diag
        assert loaded.diagnostics["observation_support_robustness"].times == (10.0, 20.0, 30.0)
        assert loaded.diagnostics["observation_support_robustness"].values == (0.12, 0.34, 0.29)
        assert loaded.provenance_valid is True

    def test_empty_diagnostics_mapping_round_trips_and_is_complete(self, tmp_path):
        record = t1.build_fixture_record(run_role="temporal_series", diagnostics={})
        path = tmp_path / "no_diag.json"
        t1.write_record(record, path)
        loaded = t1.load_record(path)
        assert loaded.diagnostics == {}
        assert loaded.provenance_valid is True


class TestDiagnosticLabel:
    def test_unknown_label_is_rejected_not_stored(self, tmp_path):
        raw = _fixture_raw()
        raw["support"]["diagnostics"] = {
            "not_a_real_diagnostic": {
                "label": "not_a_real_diagnostic",
                "status": "computed",
                "algorithm_id": "operator_a_disc_v1",
                "radius_m": 25.0,
                "centre_xy_m": [2683450.0, 1248230.0],
                "times": [1.0],
                "values": [0.5],
                "reason": None,
            }
        }
        _refresh_hash(raw)
        path = tmp_path / "bad_label.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    def test_dict_key_disagreeing_with_label_field_is_rejected(self, tmp_path):
        raw = _fixture_raw()
        raw["support"]["diagnostics"] = {
            "observation_support_robustness": {
                "label": "observation_support_robustness",
                "status": "computed",
                "algorithm_id": "operator_a_disc_v1",
                "radius_m": 25.0,
                "centre_xy_m": [2683450.0, 1248230.0],
                "times": [1.0],
                "values": [0.5],
                "reason": None,
            }
        }
        # now desync the dict key from the record's own label
        raw["support"]["diagnostics"]["mismatched_key"] = raw["support"]["diagnostics"].pop(
            "observation_support_robustness"
        )
        _refresh_hash(raw)
        path = tmp_path / "mismatched_key.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    def test_build_fixture_record_accepts_the_one_known_label(self):
        record = t1.build_fixture_record(
            run_role="pilot",
            diagnostics={"observation_support_robustness": _computed_diagnostic()},
        )
        assert "observation_support_robustness" in record.diagnostics


class TestDiagnosticApplicabilityStatus:
    def test_not_applicable_round_trips_with_reason_and_no_values(self, tmp_path):
        diag = _not_applicable_diagnostic()
        record = t1.build_fixture_record(
            run_role="spatial_series",
            grid_role="native",
            diagnostics={"observation_support_robustness": diag},
        )
        path = tmp_path / "not_applicable.json"
        t1.write_record(record, path)
        loaded = t1.load_record(path)
        d = loaded.diagnostics["observation_support_robustness"]
        assert d.status == "not_applicable"
        assert d.times == ()
        assert d.values == ()
        assert d.reason
        assert loaded.provenance_valid is True

    def test_not_applicable_is_distinguishable_from_a_computed_zero(self, tmp_path):
        """A computed diagnostic whose only sample happens to be 0.0 must
        NOT be confusable with 'not applicable' -- status is the
        discriminator, not the presence/absence of a zero value."""
        computed_zero = _computed_diagnostic(times=(10.0,), values=(0.0,))
        not_applicable = _not_applicable_diagnostic()

        rec_computed = t1.build_fixture_record(
            run_role="spatial_series",
            diagnostics={"observation_support_robustness": computed_zero},
        )
        rec_na = t1.build_fixture_record(
            run_role="spatial_series",
            diagnostics={"observation_support_robustness": not_applicable},
        )

        loaded_computed = t1.record_from_raw_dict_fail_closed(t1.dump_record(rec_computed))
        loaded_na = t1.record_from_raw_dict_fail_closed(t1.dump_record(rec_na))

        d_computed = loaded_computed.diagnostics["observation_support_robustness"]
        d_na = loaded_na.diagnostics["observation_support_robustness"]

        assert d_computed.status == "computed"
        assert d_computed.values == (0.0,)
        assert d_computed.reason is None

        assert d_na.status == "not_applicable"
        assert d_na.values == ()
        assert d_na.reason

        assert d_computed != d_na

    def test_not_applicable_with_values_present_is_rejected(self, tmp_path):
        raw = _fixture_raw(
            diagnostics={
                "observation_support_robustness": _not_applicable_diagnostic(
                    times=(1.0,), values=(0.0,)
                )
            }
        )
        # bypass the fixture-builder validation path by writing raw JSON directly
        raw["support"]["diagnostics"]["observation_support_robustness"]["times"] = [1.0]
        raw["support"]["diagnostics"]["observation_support_robustness"]["values"] = [0.0]
        _refresh_hash(raw)
        path = tmp_path / "na_with_values.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    def test_not_applicable_without_reason_is_rejected(self, tmp_path):
        raw = _fixture_raw(
            diagnostics={"observation_support_robustness": _not_applicable_diagnostic()}
        )
        raw["support"]["diagnostics"]["observation_support_robustness"]["reason"] = None
        _refresh_hash(raw)
        path = tmp_path / "na_no_reason.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    def test_computed_with_a_reason_is_rejected(self, tmp_path):
        raw = _fixture_raw(
            diagnostics={"observation_support_robustness": _computed_diagnostic()}
        )
        raw["support"]["diagnostics"]["observation_support_robustness"][
            "reason"
        ] = "should not be here"
        _refresh_hash(raw)
        path = tmp_path / "computed_with_reason.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)

    def test_unknown_status_is_rejected(self, tmp_path):
        raw = _fixture_raw(
            diagnostics={"observation_support_robustness": _computed_diagnostic()}
        )
        raw["support"]["diagnostics"]["observation_support_robustness"][
            "status"
        ] = "definitely_not_a_status"
        _refresh_hash(raw)
        path = tmp_path / "bad_status.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)


class TestDiagnosticSeriesLength:
    def test_mismatched_times_values_lengths_are_rejected(self, tmp_path):
        raw = _fixture_raw(
            diagnostics={"observation_support_robustness": _computed_diagnostic()}
        )
        raw["support"]["diagnostics"]["observation_support_robustness"]["times"] = [
            10.0,
            20.0,
            30.0,
        ]
        raw["support"]["diagnostics"]["observation_support_robustness"]["values"] = [0.12, 0.34]
        _refresh_hash(raw)
        path = tmp_path / "mismatched_lengths.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.MalformedEvidenceRecordError):
            t1.load_record(path)


class TestDiagnosticContentHashCoverage:
    def test_hash_changes_when_diagnostic_values_change(self):
        raw = _fixture_raw(
            diagnostics={"observation_support_robustness": _computed_diagnostic()}
        )
        base_hash = raw["content_hash"]
        mutated = copy.deepcopy(raw)
        mutated["support"]["diagnostics"]["observation_support_robustness"]["values"] = [
            9.9,
            9.9,
            9.9,
        ]
        assert t1.compute_content_hash(mutated) != base_hash

    @pytest.mark.parametrize(
        "field,new_value",
        [
            ("status", "not_applicable"),
            ("radius_m", 30.0),
            ("centre_xy_m", [1.0, 2.0]),
            ("algorithm_id", "operator_a_disc_v2"),
            ("times", [1.0, 2.0, 3.0]),
        ],
    )
    def test_hash_changes_for_each_diagnostic_field(self, field, new_value):
        raw = _fixture_raw(
            diagnostics={"observation_support_robustness": _computed_diagnostic()}
        )
        base_hash = t1.compute_content_hash(raw)
        mutated = copy.deepcopy(raw)
        mutated["support"]["diagnostics"]["observation_support_robustness"][field] = new_value
        assert t1.compute_content_hash(mutated) != base_hash


class TestOldSchemaVersionFailsClosedForDiagnostics:
    def test_pre_diagnostics_schema_version_now_fails_closed(self, tmp_path):
        """A record built under the OLD 1.0.0 schema (no diagnostics
        concept at all) must be refused outright by today's loader -- not
        silently accepted as 'a valid 2.0.0 record with zero diagnostics'.
        """
        raw = _fixture_raw()
        raw["schema"]["schema_version"] = "1.0.0"
        # deliberately do not touch content_hash: schema_version is excluded
        # from hash coverage, so the version gate alone must catch this.
        path = tmp_path / "old_version.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.SchemaVersionMismatchError):
            t1.load_record(path)

    def test_current_schema_version_is_2_0_0(self):
        assert t1.SCHEMA_VERSION == "2.0.0"


# ---------------------------------------------------------------------------
# The causal-support prohibition is stated IN the record, not left to the reader
# ---------------------------------------------------------------------------
class TestDiagnosticCausalSupportEligibility:
    def test_every_known_label_is_barred_from_causal_support(self):
        """T0_2b Section 4.2 names operator A insufficient BY CONSTRUCTION. No
        current diagnostic label may ever be cited as causal support."""
        assert set(t1.DIAGNOSTIC_CAUSAL_SUPPORT_ELIGIBLE) == set(t1.DIAGNOSTIC_LABELS)
        assert all(v is False for v in t1.DIAGNOSTIC_CAUSAL_SUPPORT_ELIGIBLE.values())

    def test_emitted_record_states_the_prohibition(self):
        """These records sit under `support`, next to claim_support_state -- a
        reader could infer the opposite from position alone, so the wire form
        says it outright."""
        wire = t1._diagnostics_to_json(
            {"observation_support_robustness": _computed_diagnostic()}
        )
        diag = wire["observation_support_robustness"]
        assert diag["causal_support_eligible"] is False
