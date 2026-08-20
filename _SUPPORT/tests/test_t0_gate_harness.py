"""
Tests for the T0.0 gate harness (`_SUPPORT/src/scripts/t0_gate_harness.py`).

These are UNIT tests of the harness's own logic -- schema validation,
schema-lifting, normalisation ordering, environment-fingerprint comparison.
None of them run MODFLOW/Triangle or `build_srcpulse_demo()`; per the T0.0
canonical contract (`DOCUMENTATION/contracts/T0_0_canonical_contract.md`)
that only happens inside a worker subprocess spawned by `qualify`/`compare`
in its own worktree, which is what `qualify`/`compare` (exercised manually,
see the codex-review report) actually validate end to end. Fabricating a
fake MF6 run here and presenting it as a real one would defeat the point of
the gate -- these tests instead prove the harness's OWN control flow: given
synthetic payloads shaped like `SrcPulseDemo`, does it validate, lift, sort
and compare exactly as the contract requires.

Run with:  uv run pytest _SUPPORT/tests/test_t0_gate_harness.py -v
"""
from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))

import t0_gate_harness as gate  # noqa: E402


# ---------------------------------------------------------------------------
# synthetic SrcPulseDemo-shaped dataclasses -- NOT the real dataclass (T1
# hasn't touched it; it can't have sink_support_m/t_peak yet), but shaped
# identically for the purpose of exercising build_payload()'s reflection +
# validation logic in isolation.
# ---------------------------------------------------------------------------
def _make_dataclass(name, field_names):
    return dataclasses.make_dataclass(name, [(n, object) for n in field_names])


_ReferenceStub = _make_dataclass("_ReferenceStub", gate.TOP_LEVEL_FIELDS)
_CandidateStub = _make_dataclass("_CandidateStub", gate.CANDIDATE_TOP_LEVEL_FIELDS)
_CandidateStubWithBogusField = _make_dataclass(
    "_CandidateStubWithBogusField", gate.CANDIDATE_TOP_LEVEL_FIELDS + ("bogus_field",)
)
_ReferenceStubMissingField = _make_dataclass(
    "_ReferenceStubMissingField",
    tuple(f for f in gate.TOP_LEVEL_FIELDS if f != "alpha_T"),
)


def _mass_balance_kwargs(**overrides):
    d = {k: 1.0 for k in gate.MASS_BALANCE_KEYS}
    d.update(overrides)
    return d


def _locked_kwargs(**overrides):
    d = {k: 1.0 for k in gate.LOCKED_KEYS}
    d["scheme"] = "TVD"
    d["xt3d_off"] = True
    d["time_units"] = "days"
    d.update(overrides)
    return d


def _meta_kwargs(extra_keys=(), **overrides):
    d = {k: 1.0 for k in gate.META_KEYS}
    d["ncpl"] = 4408
    d["nstp"] = 200
    d["cr_capped"] = False
    d["peak_at_last_step"] = False
    d["u_reg"] = [1.0, 2.0, 3.0]
    for k in extra_keys:
        d[k] = overrides.pop(k, None)
    d.update(overrides)
    return d


def _reference_payload_kwargs(ext_cell=42, arrival_day=38.8043478261, **field_overrides):
    """Every field of the frozen 29, plausible values, reflection-order
    agnostic (build_payload reflects by field NAME, not position)."""
    kwargs = dict(
        times=[0.0, 1.0, 2.0],
        breakthrough=[0.0, 0.5, 1.0],
        peak_mgL=5.27695440327,
        arrival_day=arrival_day,
        mass_balance=_mass_balance_kwargs(),
        solubility_ok=True,
        emergent_C_mgL=12.3,
        solubility_mgL=1000.0,
        solubility_margin=81.3,
        PeL_min=0.5, PeL_max=2.0, PeT_min=0.1, PeT_max=0.4,
        mass_g=3.0e5, pulse_days=30.0, total_days=120.0,
        smassrate_gpd=10000.0,
        src_cells=[10, 11, 12],
        ext_cell=ext_cell,
        inj_cell=99,
        spill_xy=(2680000.0, 1250000.0),
        alpha_L=10.0, alpha_T=1.0, R=1.0, rho_b=1800.0, Kd=0.0, lam=0.0,
        meta=_meta_kwargs(),
        locked=_locked_kwargs(),
    )
    kwargs.update(field_overrides)
    return kwargs


def _candidate_payload_kwargs(sink_support_m=0.0, sink_support_cells=None,
                               t_peak=None, ext_cell=42,
                               arrival_day=38.8043478261, **field_overrides):
    base = _reference_payload_kwargs(ext_cell=ext_cell, arrival_day=arrival_day)
    if sink_support_cells is None:
        sink_support_cells = [(ext_cell, -1370.0)]
    if t_peak is None:
        t_peak = arrival_day
    base["meta"] = dict(base["meta"])
    base["meta"]["sink_support_cells"] = sink_support_cells
    base["sink_support_m"] = sink_support_m
    base["t_peak"] = t_peak
    base.update(field_overrides)
    return base


# ===========================================================================
# side-aware schema validation (contract Section 3.1 / gap 2)
# ===========================================================================
class TestSideAwareSchema:
    def test_reference_side_accepts_frozen_29(self):
        payload = gate.build_payload(
            _ReferenceStub(**_reference_payload_kwargs()), side="reference"
        )
        assert set(payload.keys()) == set(gate.TOP_LEVEL_FIELDS)

    def test_reference_side_rejects_candidate_shape(self):
        """A dataclass carrying the pre-authorised fields is NOT a valid
        reference-side payload -- b685f24 must match the frozen schema
        exactly (contract Section 2.5)."""
        with pytest.raises(gate.GateAbort, match="top-level payload field set"):
            gate.build_payload(
                _CandidateStub(**_candidate_payload_kwargs()), side="reference"
            )

    def test_reference_side_aborts_on_missing_field(self):
        kwargs = {k: v for k, v in _reference_payload_kwargs().items() if k != "alpha_T"}
        with pytest.raises(gate.GateAbort, match="missing="):
            gate.build_payload(_ReferenceStubMissingField(**kwargs), side="reference")

    def test_candidate_side_accepts_frozen_plus_preauthorised(self):
        """This is the gap the codex review flagged: a candidate carrying
        sink_support_m / meta['sink_support_cells'] / t_peak must NOT abort
        -- it is precisely what Section 3 pre-authorises."""
        payload = gate.build_payload(
            _CandidateStub(**_candidate_payload_kwargs()), side="candidate"
        )
        assert "sink_support_m" in payload
        assert "t_peak" in payload
        assert "sink_support_cells" in payload["meta"]

    def test_candidate_side_rejects_reference_shape(self):
        """Section 3.1 point 2: 'the candidate payload MUST contain the
        field' -- a candidate missing the pre-authorised fields aborts too,
        it is not merely optional."""
        with pytest.raises(gate.GateAbort, match="top-level payload field set"):
            gate.build_payload(
                _ReferenceStub(**_reference_payload_kwargs()), side="candidate"
            )

    def test_candidate_side_rejects_unauthorised_extra_field(self):
        """An unexpected field on EITHER side is still an abort (task spec:
        'Make schema validation SIDE-AWARE ... An unexpected field on either
        side is still an abort.')."""
        kwargs = _candidate_payload_kwargs()
        kwargs["bogus_field"] = 1.0
        with pytest.raises(gate.GateAbort, match="top-level payload field set"):
            gate.build_payload(
                _CandidateStubWithBogusField(**kwargs), side="candidate"
            )

    def test_candidate_side_rejects_missing_pre_authorised_meta_key(self):
        kwargs = _candidate_payload_kwargs()
        kwargs["meta"] = dict(kwargs["meta"])
        del kwargs["meta"]["sink_support_cells"]
        with pytest.raises(gate.GateAbort, match="meta keyset changed"):
            gate.build_payload(_CandidateStub(**kwargs), side="candidate")

    def test_mass_balance_error_key_aborts_regardless_of_side(self):
        kwargs = _reference_payload_kwargs()
        kwargs["mass_balance"] = dict(kwargs["mass_balance"])
        kwargs["mass_balance"]["error"] = "boom: /some/workspace/path"
        with pytest.raises(gate.GateAbort, match="mass_balance abort"):
            gate.build_payload(_ReferenceStub(**kwargs), side="reference")


# ===========================================================================
# the lift table (contract Section 3.1 / gap 3)
# ===========================================================================
class TestLiftTable:
    def test_lift_adds_identity_defaults_derived_from_the_run(self):
        raw = _reference_payload_kwargs(ext_cell=77, arrival_day=38.8043478261)
        lifted = gate.lift_reference(raw, constants={"DOUBLET_Q": 1370.0})
        assert lifted["sink_support_m"] == 0.0
        assert lifted["meta"]["sink_support_cells"] == [(77, -1370.0)]
        assert lifted["t_peak"] == 38.8043478261
        # original untouched (lift returns a new dict)
        assert "sink_support_m" not in raw
        assert "sink_support_cells" not in raw["meta"]

    def test_lift_uses_the_runs_own_ext_cell_not_a_constant(self):
        raw_a = _reference_payload_kwargs(ext_cell=1)
        raw_b = _reference_payload_kwargs(ext_cell=999)
        lifted_a = gate.lift_reference(raw_a, constants={"DOUBLET_Q": 1370.0})
        lifted_b = gate.lift_reference(raw_b, constants={"DOUBLET_Q": 1370.0})
        assert lifted_a["meta"]["sink_support_cells"] == [(1, -1370.0)]
        assert lifted_b["meta"]["sink_support_cells"] == [(999, -1370.0)]

    def test_lift_uses_the_supplied_doublet_q_not_a_hardcoded_one(self):
        """The harness must not hardcode DOUBLET_Q -- it reads it from the
        reference run's own imported module (passed in via `constants`)."""
        raw = _reference_payload_kwargs(ext_cell=5)
        lifted = gate.lift_reference(raw, constants={"DOUBLET_Q": 2222.0})
        assert lifted["meta"]["sink_support_cells"] == [(5, -2222.0)]

    def test_lift_then_normalize_matches_a_correct_candidate(self):
        """End-to-end: lifting the reference and normalising it must equal
        normalising a candidate that reports the identity-default values --
        this is the schema-lift path the review found entirely missing."""
        raw_ref = _reference_payload_kwargs(ext_cell=42, arrival_day=38.8043478261)
        lifted_ref = gate.lift_reference(raw_ref, constants={"DOUBLET_Q": 1370.0})
        normalized_lifted_ref = gate.normalize(lifted_ref)

        candidate_payload = gate.build_payload(
            _CandidateStub(**_candidate_payload_kwargs(ext_cell=42, arrival_day=38.8043478261)),
            side="candidate",
        )
        normalized_candidate = gate.normalize(candidate_payload)

        mismatches = gate._diff_normalized(normalized_lifted_ref, normalized_candidate)
        assert mismatches == []

    def test_adding_a_field_to_the_table_is_the_only_place_candidate_schema_changes(self):
        """CANDIDATE_TOP_LEVEL_FIELDS / CANDIDATE_META_KEYS are DERIVED from
        PRE_AUTHORIZED_FIELDS, not hand-duplicated -- assert the derivation,
        not just the current frozen values, so a future one-line table
        addition automatically flows through."""
        top_from_table = {s["path"][0] for s in gate.PRE_AUTHORIZED_FIELDS if len(s["path"]) == 1}
        meta_from_table = {
            s["path"][1] for s in gate.PRE_AUTHORIZED_FIELDS
            if len(s["path"]) == 2 and s["path"][0] == "meta"
        }
        assert set(gate.CANDIDATE_TOP_LEVEL_FIELDS) == set(gate.TOP_LEVEL_FIELDS) | top_from_table
        assert set(gate.CANDIDATE_META_KEYS) == set(gate.META_KEYS) | meta_from_table


# ===========================================================================
# ARRAY_PAIR ordering (contract Section 4.1/4.2 / gap 4)
# ===========================================================================
class TestArrayPairOrdering:
    def test_sink_support_cells_is_sorted_ascending_by_cell_index(self):
        payload = {"meta": {"sink_support_cells": [(5, -10.0), (1, -20.0), (3, -5.0)]}}
        normalized = gate.normalize(payload)
        cells = normalized["meta"]["sink_support_cells"]
        assert [int(pair[0]) for pair in cells] == [1, 3, 5]

    def test_times_and_breakthrough_are_never_sorted(self):
        """The one field that IS sorted is sink_support_cells alone -- every
        other array, especially a time series, must keep its produced
        order even if that order is not monotonic."""
        payload = {"times": [5.0, 1.0, 3.0], "breakthrough": [0.9, 0.1, 0.5]}
        normalized = gate.normalize(payload)
        assert normalized["times"] == [gate._format_float(x) for x in [5.0, 1.0, 3.0]]
        assert normalized["breakthrough"] == [gate._format_float(x) for x in [0.9, 0.1, 0.5]]

    def test_src_cells_int_array_preserves_order(self):
        payload = {"src_cells": [30, 10, 20]}
        normalized = gate.normalize(payload)
        assert normalized["src_cells"] == ["30", "10", "20"]

    def test_array_pair_only_applies_at_its_own_path(self):
        """A list of pairs living somewhere OTHER than meta.sink_support_cells
        must NOT be sorted -- the rule is path-aware, not type-aware."""
        payload = {"not_meta": {"sink_support_cells": [(9, -1.0), (1, -2.0)]}}
        normalized = gate.normalize(payload)
        cells = normalized["not_meta"]["sink_support_cells"]
        # preserved order: (9, -1.0) then (1, -2.0) -- NOT sorted, and NOT
        # reformatted as an [INT, FLOAT] pair-list either (falls through to
        # the generic tuple/list branch, one normalize() call per element,
        # each element normalised by its own Python type -- int stays INT).
        assert cells[0] == ["9", gate._format_float(-1.0)]
        assert cells[1] == ["1", gate._format_float(-2.0)]


# ===========================================================================
# environment fingerprint comparison (contract Section 5.0/5.2 step 1 / gap 5)
# ===========================================================================
class TestEnvFingerprintComparison:
    def _base_env(self, **overrides):
        env = {
            "os": "macOS-14", "machine": "arm64", "python_version": "3.12.0",
            "python_executable": "/x/.venv/bin/python3",
            "flopy_version": "3.9", "numpy_version": "2.0",
            "mf6_realpath": "/x/mf6", "mf6_sha256": "aaa",
            "triangle_realpath": "/x/triangle", "triangle_sha256": "bbb",
            "data_folder": "/data",
            "flow_fingerprint": "flowfp",
            "model_boundary_path": "/x/boundary.gpkg", "model_boundary_sha256": "ccc",
            "rivers_path": "/x/rivers.gpkg", "rivers_sha256": "ddd",
            "OMP_NUM_THREADS": "1", "GDAL_NUM_THREADS": "1",
            "PATH": "/usr/bin",
            "worktree_root": "/wt/A", "worktree_commit": "sha_a",
            "case_ws": "/wt/A/case_ws",
            "transport_srcpulse_demo_file": "/wt/A/_SUPPORT/src/transport_srcpulse_demo.py",
            "model_io_utils_file": "/wt/A/_SUPPORT/src/model_io_utils.py",
        }
        env.update(overrides)
        return env

    def test_identical_env_passes(self):
        env_a = self._base_env()
        env_b = self._base_env()
        assert gate._env_mismatches(env_a, env_b) == {}

    def test_worktree_path_and_commit_are_permitted_to_differ(self):
        """Section 1.3: 'the only permitted difference is the repo commit'
        -- worktree_root/case_ws/the two resolved __file__s/worktree_commit
        are exactly the fields that are a FUNCTION of which worktree a side
        ran in, so their difference is not a gate failure."""
        env_a = self._base_env()
        env_b = self._base_env(
            worktree_root="/wt/B", worktree_commit="sha_b",
            case_ws="/wt/B/case_ws",
            transport_srcpulse_demo_file="/wt/B/_SUPPORT/src/transport_srcpulse_demo.py",
            model_io_utils_file="/wt/B/_SUPPORT/src/model_io_utils.py",
        )
        assert gate._env_mismatches(env_a, env_b) == {}

    def test_a_real_environment_difference_fails_not_warns(self):
        env_a = self._base_env()
        env_b = self._base_env(mf6_sha256="different_binary")
        mismatches = gate._env_mismatches(env_a, env_b)
        assert "mf6_sha256" in mismatches
        assert mismatches["mf6_sha256"] == {"A": "aaa", "B": "different_binary"}

    def test_full_fingerprint_is_compared_not_a_curated_subset(self):
        """Regression guard for the exact gap the review found: the OLD
        harness only compared 6 keys. Every key outside the expected-diff
        set must be checked -- assert on one of the previously-uncompared
        ones (python_version)."""
        env_a = self._base_env()
        env_b = self._base_env(python_version="3.11.0")
        mismatches = gate._env_mismatches(env_a, env_b)
        assert "python_version" in mismatches

    def test_key_present_on_only_one_side_is_reported(self):
        env_a = self._base_env()
        env_b = self._base_env()
        del env_b["numpy_version"]
        mismatches = gate._env_mismatches(env_a, env_b)
        assert "numpy_version" in mismatches
        assert mismatches["numpy_version"] == {"A": "2.0", "B": None}


# ===========================================================================
# compare_reference_vs_candidate -- the reference-vs-candidate mode (gap 1),
# exercised at unit level with hand-built worker-record dicts (this is
# exactly what run_compare() feeds it after both worker subprocesses exit).
# ===========================================================================
class TestCompareReferenceVsCandidate:
    def _reference_record(self, ext_cell=42, arrival_day=38.8043478261, env=None):
        raw = _reference_payload_kwargs(ext_cell=ext_cell, arrival_day=arrival_day)
        normalized = gate.normalize(raw)
        lifted = gate.lift_reference(raw, constants={"DOUBLET_Q": 1370.0})
        return {
            "status": "OK", "side": "reference", "wall_s": 14.6,
            "env": env or {"data_folder": "/data"},
            "normalized_payload": normalized,
            "lifted_normalized_payload": gate.normalize(lifted),
        }

    def _candidate_record(self, sink_support_m=0.0, sink_support_cells=None,
                           t_peak=None, ext_cell=42, arrival_day=38.8043478261,
                           env=None):
        kwargs = _candidate_payload_kwargs(
            sink_support_m=sink_support_m, sink_support_cells=sink_support_cells,
            t_peak=t_peak, ext_cell=ext_cell, arrival_day=arrival_day,
        )
        payload = gate.build_payload(_CandidateStub(**kwargs), side="candidate")
        return {
            "status": "OK", "side": "candidate", "wall_s": 14.6,
            "env": env or {"data_folder": "/data"},
            "normalized_payload": gate.normalize(payload),
        }

    def test_candidate_at_identity_defaults_compares_equal_to_lifted_reference(self):
        a = self._reference_record()
        b = self._candidate_record()  # sink_support_m=0.0, cells=[(42,-1370)], t_peak=arrival_day
        report = gate.compare_reference_vs_candidate(a, b)
        assert report["summary"]["comparison"] == "PASS"
        assert report["summary"]["payload_mismatch_count"] == 0

    def test_candidate_diverging_on_a_pre_authorised_field_fails_and_names_it(self):
        a = self._reference_record()
        b = self._candidate_record(sink_support_m=5.0)  # NOT the identity default
        report = gate.compare_reference_vs_candidate(a, b)
        assert report["summary"]["comparison"] == "FAIL"
        fields = {m["field"] for m in report["summary"]["payload_mismatches"]}
        assert "sink_support_m" in fields

    def test_candidate_diverging_on_sink_support_cells_fails_and_names_it(self):
        a = self._reference_record(ext_cell=42)
        b = self._candidate_record(sink_support_cells=[(42, -999.0)])
        report = gate.compare_reference_vs_candidate(a, b)
        assert report["summary"]["comparison"] == "FAIL"
        fields = {m["field"] for m in report["summary"]["payload_mismatches"]}
        assert any(f.startswith("meta.sink_support_cells") for f in fields)

    def test_candidate_diverging_on_t_peak_fails_and_names_it(self):
        a = self._reference_record(arrival_day=38.8043478261)
        b = self._candidate_record(t_peak=99.0)
        report = gate.compare_reference_vs_candidate(a, b)
        assert report["summary"]["comparison"] == "FAIL"
        fields = {m["field"] for m in report["summary"]["payload_mismatches"]}
        assert "t_peak" in fields

    def test_candidate_diverging_on_an_ordinary_field_still_fails(self):
        """Sanity: the lift/pre-authorisation machinery must not accidentally
        loosen comparison of an ORDINARY (non-pre-authorised) field."""
        a = self._reference_record()
        b = self._candidate_record()
        b["normalized_payload"]["peak_mgL"] = gate._format_float(999.0)
        report = gate.compare_reference_vs_candidate(a, b)
        assert report["summary"]["comparison"] == "FAIL"
        fields = {m["field"] for m in report["summary"]["payload_mismatches"]}
        assert "peak_mgL" in fields

    def test_env_mismatch_fails_the_comparison_too(self):
        a = self._reference_record(env={"data_folder": "/data/A"})
        b = self._candidate_record(env={"data_folder": "/data/B"})
        report = gate.compare_reference_vs_candidate(a, b)
        assert report["summary"]["comparison"] == "FAIL"
        assert "data_folder" in report["summary"]["env_mismatches"]

    def test_reference_side_missing_lift_is_a_hard_failure(self):
        """If run_compare() were ever called with a mis-sided worker record
        (e.g. --side candidate on the reference commit by mistake), the
        comparison must fail loudly rather than silently compare the wrong
        thing."""
        a = self._reference_record()
        del a["lifted_normalized_payload"]
        b = self._candidate_record()
        report = gate.compare_reference_vs_candidate(a, b)
        assert report["summary"]["comparison"] == "FAIL"
        assert "lifted_normalized_payload" in report["summary"]["reason"]

    def test_non_ok_side_status_fails_without_comparing(self):
        a = {"status": "ABORT", "error": "mass_balance abort"}
        b = self._candidate_record()
        report = gate.compare_reference_vs_candidate(a, b)
        assert report["summary"]["comparison"] == "FAIL"


# ===========================================================================
# None-as-sentinel (explicitly NOT a bug -- regression guard that it stays)
# ===========================================================================
def test_none_renders_as_visible_null_sentinel_not_a_raise():
    assert gate.normalize(None) == "null"
    payload = {"emergent_C_mgL": None}
    normalized = gate.normalize(payload)
    assert normalized["emergent_C_mgL"] == "null"
