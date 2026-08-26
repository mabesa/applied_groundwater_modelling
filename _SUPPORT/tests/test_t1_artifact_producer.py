"""Tests for `t1_artifact_producer` (T1 S14 -- the artifact producer).

S13 (`test_t1_evidence_artifact.py`) proved the SCHEMA works against
synthetic fixtures; this file proves the PRODUCER makes a REAL
`build_srcpulse_demo` run produce a REAL, loadable, honest record -- see
`DESIGN_DOCS/T1_S14_brief.md` v2.

Only two tests here touch MODFLOW 6/Triangle for real (`@pytest.mark.slow`,
via the module-scoped `real_record` fixture, run ONCE and shared): everything
else exercises the producer's pure logic (the experimental registry, the
environment-pairing guard, the path-leak scan, the cross-field-invariant
checker, the failure path) against synthetic inputs, exactly mirroring the
speed discipline `test_t1_evidence_artifact.py` and `test_t0_gate_harness.py`
already establish for this package.

Run with:  uv run pytest _SUPPORT/tests/test_t1_artifact_producer.py -v
Run including the two slow (real-MF6) tests:
           uv run pytest _SUPPORT/tests/test_t1_artifact_producer.py -v -m slow
"""
from __future__ import annotations

import ast
import json
import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "scripts"))

import transport_srcpulse_demo as tsd  # noqa: E402
import t1_evidence_artifact as tea  # noqa: E402
import t1_artifact_producer as prod  # noqa: E402
import t0_gate_harness as gate  # noqa: E402

REPO_ROOT = Path(prod.__file__).resolve().parents[2]

#: A real, evaluable ("numeric"/"threshold-decision") entry from the T0.2a
#: claim inventory -- about the compliance peak/arrival, per its matched_text.
REAL_CLAIM_ID = "15bbf92b2904"


# ---------------------------------------------------------------------------
# synthetic SrcPulseDemo-shaped stand-in -- duck-typed, no model import beyond
# the attributes `metrics_from_result` / `footprint_from_result` actually read
# ---------------------------------------------------------------------------
def _fake_result(**overrides):
    defaults = dict(
        times=np.array([0.0, 10.0, 20.0, 30.0, 40.0]),
        breakthrough=np.array([0.0, 1.0, 3.0, 5.0, 2.0]),
        peak_mgL=5.0,
        arrival_day=30.0,
        t_peak=30.0,
        smassrate_gpd=10000.0,
        src_cells=[42],
        spill_xy=(2680000.0, 1250000.0),
        meta=dict(ncpl=1000, nstp=100, dt=1.0, Cr=0.5, cr_capped=False,
                  peak_at_last_step=False),
    )
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def _refresh_hash(raw: dict) -> dict:
    raw["content_hash"] = tea.compute_content_hash(raw)
    return raw


# ---------------------------------------------------------------------------
# module-scoped fixture: ONE real run, shared by both slow tests
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real_case_ws(tmp_path_factory):
    return tmp_path_factory.mktemp("t1_s14_case_ws")


@pytest.fixture(scope="module")
def real_record(real_case_ws):
    record, omitted = prod.run_and_build_record(
        run_id="t1-s14-test-run-0001",
        case_id="case_pfoa_reference",
        claim_id=REAL_CLAIM_ID,
        claim_type="numeric",
        metric="peak_mgL",
        tolerance=0.02,
        run_role="pilot",
        case_ws=real_case_ws / "srcpulse",
    )
    return record, omitted


@pytest.fixture(scope="module")
def real_record_path(real_case_ws, real_record):
    record, omitted = real_record
    out_path = real_case_ws / "evidence" / "record.json"
    prod.write_record(record, omitted, out_path)
    return out_path


@pytest.fixture(scope="module")
def real_record_raw(real_record_path):
    with open(real_record_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ===========================================================================
# 1 / exit criterion 1: a real run produces a loadable record
# ===========================================================================
@pytest.mark.slow
def test_real_run_produces_a_loadable_record(real_record_path):
    loaded = tea.load_record(real_record_path)
    assert loaded.schema_version == tea.SCHEMA_VERSION
    assert loaded.run_id == "t1-s14-test-run-0001"
    assert loaded.provenance_valid is True


# ===========================================================================
# provenance_valid is COMPUTED, never asserted (exit criterion 2)
# ===========================================================================
class TestProvenanceValidIsComputed:
    def test_provenance_valid_is_computed_not_asserted(self, tmp_path, real_record):
        """Declare provenance_valid=True on the record but tell `write_record`
        a real, present field is 'omitted' -- the loader must still compute
        False, proving it recomputes from REQUIRED_FIELD_PATHS rather than
        trusting the producer's own declaration."""
        record, _omitted = real_record
        assert record.provenance_valid is True  # sanity: producer declared True
        out_path = tmp_path / "declared_true_but_incomplete.json"
        prod.write_record(record, [("fingerprints", "roster_hash")], out_path)
        loaded = tea.load_record(out_path)
        assert loaded.provenance_valid is False

    def test_incomplete_record_is_provenance_invalid(self, tmp_path, real_record):
        record, _omitted = real_record
        out_path = tmp_path / "incomplete.json"
        raw = prod.write_record(record, [("run_identity", "cr_target")], out_path)
        assert "cr_target" not in raw["run_identity"]
        loaded = tea.load_record(out_path)
        assert loaded.provenance_valid is False
        assert "run_identity.cr_target" in tea.missing_required_fields(raw)


# ===========================================================================
# No placeholder values (exit criterion 3)
# ===========================================================================
def test_no_placeholder_values_are_written(real_record_raw):
    text = json.dumps(real_record_raw).lower()
    assert '"unknown"' not in text
    # every environment leaf this producer captures is either a real value or
    # genuinely absent -- never an empty-string stand-in.
    env = real_record_raw["environment"]
    for key in ("os_arch", "mf6_path", "mf6_sha256", "triangle_path",
                "triangle_sha256", "flopy_version", "numpy_version", "python_version"):
        if key in env:
            assert env[key] != "", f"{key} is a present-but-empty placeholder"


# ===========================================================================
# No absolute developer path leaks (exit criteria 4 / 14)
# ===========================================================================
class TestNoLeakedPaths:
    def test_no_absolute_home_path_in_the_serialized_record(self, real_record_raw):
        home = str(Path.home())
        leaks = prod.find_unexpected_absolute_paths(real_record_raw)
        home_leaks = [(p, v) for p, v in leaks if home in v]
        assert home_leaks == [], f"unexpected $HOME leak(s): {home_leaks!r}"

    def test_allowed_fields_may_carry_a_home_path(self, real_record_raw):
        """The two fields brief Sec 2.3 requires to carry a realpath DO
        contain the home directory -- proving the scan's exemption is real,
        not merely a scan that happens to find nothing."""
        home = str(Path.home())
        env = real_record_raw["environment"]
        assert home in env["mf6_path"]
        assert home in env["triangle_path"]

    def test_no_absolute_path_outside_case_ws(self):
        """The scan is not $HOME-only: a NON-home absolute path in an
        unlisted field must also be flagged."""
        raw = {"environment": {"mf6_path": "/some/other/path/mf6"},
               "run_identity": {"case_id": "/private/tmp/leaked/not_home"}}
        leaks = prod.find_unexpected_absolute_paths(raw)
        leaked_fields = {p for p, _v in leaks}
        assert "environment.mf6_path" not in leaked_fields  # allowlisted
        assert "run_identity.case_id" in leaked_fields

    def test_write_record_refuses_a_leaky_record(self, real_record, tmp_path):
        record, omitted = real_record
        import dataclasses as dc
        leaky = dc.replace(record, case_id="/private/tmp/should/not/be/here")
        with pytest.raises(prod.ArtifactProducerError, match="unexpected absolute paths"):
            prod.write_record(leaky, omitted, tmp_path / "leaky.json")


# ===========================================================================
# `run_identity.controls` must equal case-workspace scoping (exit 16)
# ===========================================================================
def test_artifact_is_written_under_case_ws(real_case_ws, real_record_path):
    resolved = real_record_path.resolve()
    assert str(resolved).startswith(str(real_case_ws.resolve()))
    assert not str(resolved).startswith(str(REPO_ROOT))


# ===========================================================================
# Environment capture agrees with the gate harness (exit criterion 5)
# ===========================================================================
class TestEnvironmentAgreesWithHarness:
    @staticmethod
    def _run_worker_try_body(tree: ast.AST):
        run_worker = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "run_worker"
        )
        try_node = next(n for n in ast.walk(run_worker) if isinstance(n, ast.Try))
        return try_node.body

    @classmethod
    def _exec_binary_resolution(cls, source: str, namespace: dict) -> dict:
        """Execute the harness's OWN `mf6_exe`/`mf6_real`/`mf6_sha` (and the
        triangle equivalents) assignment statements, extracted live from
        *source* -- never a hand-copied re-statement of that logic."""
        tree = ast.parse(source)
        wanted = {"mf6_exe", "mf6_real", "mf6_sha", "tri_exe", "tri_real", "tri_sha"}
        stmts = [
            s for s in cls._run_worker_try_body(tree)
            if isinstance(s, ast.Assign) and len(s.targets) == 1
            and isinstance(s.targets[0], ast.Name) and s.targets[0].id in wanted
        ]
        mod = ast.Module(body=stmts, type_ignores=[])
        ast.fix_missing_locations(mod)
        exec(compile(mod, "<t0_gate_harness.run_worker binary-resolution extract>", "exec"),
             namespace)
        return namespace

    @classmethod
    def _eval_env_fp_key(cls, source: str, key: str, namespace: dict):
        tree = ast.parse(source)
        assign = next(
            s for s in cls._run_worker_try_body(tree)
            if isinstance(s, ast.Assign) and len(s.targets) == 1
            and isinstance(s.targets[0], ast.Name) and s.targets[0].id == "env_fp"
        )
        dict_node = assign.value
        for k_node, v_node in zip(dict_node.keys, dict_node.values):
            if isinstance(k_node, ast.Constant) and k_node.value == key:
                expr = ast.Expression(body=v_node)
                ast.fix_missing_locations(expr)
                return eval(  # noqa: S307 -- evaluating the harness's OWN source, not user input
                    compile(expr, f"<t0_gate_harness.env_fp[{key!r}]>", "eval"), namespace
                )
        raise KeyError(key)

    def test_environment_capture_agrees_with_the_gate_harness(self):
        import flopy
        harness_src = Path(gate.__file__).read_text(encoding="utf-8")
        ns = {"os": gate.os, "shutil": gate.shutil, "_sha256_file": gate._sha256_file}
        self._exec_binary_resolution(harness_src, ns)

        eval_ns = dict(ns)
        eval_ns.update({"platform": gate.platform, "sys": gate.sys, "flopy": flopy, "np": np})

        producer_env = prod.capture_environment()

        assert producer_env["mf6_sha256"] == ns["mf6_sha"]
        assert producer_env["mf6_path"] == ns["mf6_real"]
        assert producer_env["triangle_sha256"] == ns["tri_sha"]
        assert producer_env["triangle_path"] == ns["tri_real"]

        harness_flopy_version = self._eval_env_fp_key(harness_src, "flopy_version", eval_ns)
        harness_numpy_version = self._eval_env_fp_key(harness_src, "numpy_version", eval_ns)
        harness_python_version = self._eval_env_fp_key(harness_src, "python_version", eval_ns)
        harness_machine = self._eval_env_fp_key(harness_src, "machine", eval_ns)
        harness_omp = self._eval_env_fp_key(harness_src, "OMP_NUM_THREADS", eval_ns)
        harness_gdal = self._eval_env_fp_key(harness_src, "GDAL_NUM_THREADS", eval_ns)

        assert producer_env["flopy_version"] == harness_flopy_version
        assert producer_env["numpy_version"] == harness_numpy_version
        # harness records the FULL `sys.version` string; the producer records
        # the clean `platform.python_version()` form -- same underlying fact,
        # different (both legitimate, neither frozen) formats.
        assert harness_python_version.startswith(producer_env["python_version"])
        assert producer_env["os_arch"].endswith(harness_machine)
        assert producer_env["thread_pinning"]["OMP_NUM_THREADS"] == harness_omp
        assert producer_env["thread_pinning"]["GDAL_NUM_THREADS"] == harness_gdal

    def test_environment_agreement_invokes_the_harness_not_a_reimplementation(self, tmp_path):
        """Prove the extraction genuinely reads LIVE source rather than a
        hardcoded expectation: mutate a copy of the harness's `env_fp`
        expression for `mf6_sha256` and confirm the extractor's output
        changes accordingly."""
        original = Path(gate.__file__).read_text(encoding="utf-8")
        needle = '"mf6_sha256": mf6_sha,'
        assert needle in original, "harness source shape changed -- update this test's needle"
        mutated = original.replace(needle, '"mf6_sha256": "MUTATED_SENTINEL_VALUE",')
        assert mutated != original

        ns = {"os": gate.os, "shutil": gate.shutil, "_sha256_file": gate._sha256_file}
        self._exec_binary_resolution(mutated, ns)
        value = self._eval_env_fp_key(mutated, "mf6_sha256", ns)
        assert value == "MUTATED_SENTINEL_VALUE"

        # and the SAME extractor, against the REAL unmutated source, does NOT
        # return the sentinel -- a tautological/hardcoded test would not be
        # able to tell these two apart.
        ns2 = {"os": gate.os, "shutil": gate.shutil, "_sha256_file": gate._sha256_file}
        self._exec_binary_resolution(original, ns2)
        real_value = self._eval_env_fp_key(original, "mf6_sha256", ns2)
        assert real_value != "MUTATED_SENTINEL_VALUE"


# ===========================================================================
# transposed binary hashes are detected (exit criterion 13)
# ===========================================================================
def test_transposed_binary_hashes_are_detected():
    env = prod.capture_environment()
    transposed = dict(env)
    transposed["mf6_sha256"], transposed["triangle_sha256"] = (
        env["triangle_sha256"], env["mf6_sha256"],
    )
    with pytest.raises(prod.ArtifactProducerError, match="transposed"):
        prod.verify_environment_pairing(transposed)


def test_correctly_paired_environment_passes(real_record_raw):
    env = real_record_raw["environment"]
    prod.verify_environment_pairing(env)  # must not raise


# ===========================================================================
# The experimental marker (exit criteria 6 / 15)
# ===========================================================================
class TestExperimentalMarker:
    def test_sentinel_run_is_recorded_as_not_experimental(self, real_record):
        record, _omitted = real_record
        assert record.experimental["is_experimental"] is False

    def test_experimental_derivation_version_is_recorded(self, real_record):
        record, _omitted = real_record
        assert (
            record.experimental["derivation_version"]
            == prod.EXPERIMENTAL_DERIVATION_VERSION
        )

    def test_experimental_marker_is_derived_from_run_parameters(self):
        default = prod.compute_experimental_marker(
            cr_target=0.9, footprint_radius_m=0.0, sink_support_m=0.0,
            courant_profile="legacy_srcpulse", resolved_mesh_spec=tsd.MeshSpec(),
        )
        assert default["is_experimental"] is False

        deviated = prod.compute_experimental_marker(
            cr_target=0.45, footprint_radius_m=0.0, sink_support_m=0.0,
            courant_profile="legacy_srcpulse", resolved_mesh_spec=tsd.MeshSpec(),
        )
        assert deviated["is_experimental"] is True
        assert deviated["knobs"]["cr_target"]["deviates"] is True
        assert deviated["knobs"]["footprint_radius_m"]["deviates"] is False

    @pytest.mark.parametrize("knob", list(prod.EXPERIMENTAL_KNOB_PARAMS))
    def test_every_registered_experimental_knob_changes_classification(self, knob):
        base = dict(
            cr_target=0.9, footprint_radius_m=0.0, sink_support_m=0.0,
            courant_profile="legacy_srcpulse", resolved_mesh_spec=tsd.MeshSpec(),
        )
        if knob == "mesh_spec":
            base["resolved_mesh_spec"] = tsd.MeshSpec(base_cell_size=25.0)
        elif knob == "courant_profile":
            base["courant_profile"] = "exp_v1"
        else:
            base[knob] = {"cr_target": 0.225, "footprint_radius_m": 5.0,
                          "sink_support_m": 5.0}[knob]

        marker = prod.compute_experimental_marker(**base)
        assert marker["is_experimental"] is True
        assert marker["knobs"][knob]["deviates"] is True
        for other in prod.EXPERIMENTAL_KNOB_PARAMS:
            if other != knob:
                assert marker["knobs"][other]["deviates"] is False, (
                    f"moving {knob!r} off its sentinel unexpectedly also flipped {other!r}"
                )

    def test_every_build_srcpulse_demo_parameter_is_classified(self):
        """Exhaustiveness, enforced: every keyword `build_srcpulse_demo`
        parameter must land in EXACTLY ONE of the registry's two partitions.
        A future parameter in neither fails this test loudly, rather than
        silently defaulting to 'not experimental' (brief Sec 4)."""
        import inspect

        sig = inspect.signature(tsd.build_srcpulse_demo)
        live_params = set(sig.parameters.keys())
        registered = set(prod.EXPERIMENTAL_KNOB_PARAMS) | set(prod.CASE_DEFINITION_PARAMS)
        assert live_params == registered, (
            f"build_srcpulse_demo gained/lost parameters not reflected in the "
            f"registry: live-only={live_params - registered!r}, "
            f"registry-only={registered - live_params!r}"
        )
        overlap = set(prod.EXPERIMENTAL_KNOB_PARAMS) & set(prod.CASE_DEFINITION_PARAMS)
        assert overlap == set()


# ===========================================================================
# stdlib-only / one-way import direction (exit criterion 7)
# ===========================================================================
class TestImportDirection:
    def test_artifact_module_remains_stdlib_only(self):
        """Regression guard: S14 must not have added an import to
        `t1_evidence_artifact.py` -- re-parse its LIVE source, mirroring
        `test_t1_evidence_artifact.py::TestNoModelModuleImports`."""
        allowed_prefixes = {
            "__future__", "copy", "hashlib", "json", "math",
            "dataclasses", "pathlib", "typing",
        }
        src_path = Path(tea.__file__)
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top in allowed_prefixes, f"unexpected import: {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                assert top in allowed_prefixes, f"unexpected import: {node.module}"

    def test_model_does_not_import_the_producer(self):
        src_path = Path(tsd.__file__)
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        imported_tops = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_tops.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_tops.add(node.module.split(".")[0])
        assert "t1_artifact_producer" not in imported_tops

    def test_demo_closure_stays_exactly_seven_modules(self):
        """The producer must not have grown into the model's own transitive
        `_SUPPORT/src` closure (`test_t1_src_closure.py::DEMO_EXPECTED`)."""
        closure = tsd._resolve_src_closure(tsd.__file__)
        assert "t1_artifact_producer" not in closure
        assert len(closure) == 7


# ===========================================================================
# content hash reproducibility / exactness (exit criteria 8 / 10)
# ===========================================================================
class TestContentHash:
    def test_content_hash_is_reproducible(self, real_case_ws):
        record_a, omitted_a = prod.run_and_build_record(
            run_id="t1-s14-repro-run", case_id="case_pfoa_reference",
            claim_id=REAL_CLAIM_ID, claim_type="numeric", metric="peak_mgL",
            tolerance=0.02, run_role="pilot", case_ws=real_case_ws / "srcpulse",
        )
        record_b, omitted_b = prod.run_and_build_record(
            run_id="t1-s14-repro-run", case_id="case_pfoa_reference",
            claim_id=REAL_CLAIM_ID, claim_type="numeric", metric="peak_mgL",
            tolerance=0.02, run_role="pilot", case_ws=real_case_ws / "srcpulse",
        )
        raw_a = prod.write_record(record_a, omitted_a, real_case_ws / "a.json")
        raw_b = prod.write_record(record_b, omitted_b, real_case_ws / "b.json")
        assert raw_a["content_hash"] == raw_b["content_hash"]

    def test_content_hash_covers_the_exact_written_bytes(self, tmp_path, real_record):
        """Omitted paths are deleted BEFORE the hash is computed -- the
        stored hash must match a hash recomputed from the file exactly as
        written, and the omitted keys must be genuinely absent from it."""
        record, _omitted = real_record
        out_path = tmp_path / "with_omission.json"
        raw = prod.write_record(record, [("fingerprints", "roster_hash")], out_path)
        assert "roster_hash" not in raw["fingerprints"]

        with open(out_path, "r", encoding="utf-8") as fh:
            reloaded_raw = json.load(fh)
        assert "roster_hash" not in reloaded_raw["fingerprints"]
        assert reloaded_raw["content_hash"] == tea.compute_content_hash(reloaded_raw)

    def test_corrupted_field_fails_to_load(self, real_case_ws, real_record):
        record, omitted = real_record
        out_path = real_case_ws / "corrupt_me.json"
        prod.write_record(record, omitted, out_path)
        text = out_path.read_text(encoding="utf-8")
        # flip one digit of a numeric field's serialised value, WITHOUT
        # recomputing content_hash -- the loader must refuse it.
        raw = json.loads(text)
        raw["run_identity"]["cr_target"] = raw["run_identity"]["cr_target"] + 0.001
        out_path.write_text(json.dumps(raw, indent=2, sort_keys=True))
        with pytest.raises(tea.ContentHashMismatchError):
            tea.load_record(out_path)

    def test_corrupted_field_fails_to_load_is_not_vacuous(self, real_record_path):
        """The un-mutated file, by contrast, loads fine -- proving the raise
        above is caused by the mutation, not some unrelated defect."""
        tea.load_record(real_record_path)  # must not raise


# ===========================================================================
# a failed solve (exit criterion 9)
# ===========================================================================
def test_failed_solve_is_recorded_as_failed(monkeypatch, tmp_path):
    def _boom(*args, **kwargs):
        raise RuntimeError("synthetic solver failure for test_failed_solve_is_recorded_as_failed")

    monkeypatch.setattr(tsd, "build_srcpulse_demo", _boom)
    record, omitted = prod.run_and_build_record(
        run_id="t1-s14-failed-run", case_id="case_pfoa_reference",
        claim_id=REAL_CLAIM_ID, claim_type="numeric", metric="peak_mgL",
        tolerance=0.02, run_role="pilot", case_ws=tmp_path / "never_used",
    )
    assert record.solver_status == "failed"
    assert record.provenance_valid is False
    assert record.metrics is None

    out_path = tmp_path / "failed_record.json"
    raw = prod.write_record(record, omitted, out_path)
    assert "metrics" not in raw
    assert "source_footprint" not in raw["run_identity"]
    for leaf in ("horizon_censored", "cr_capped", "nstp", "cr_achieved", "ncpl"):
        assert leaf not in raw["run_health"], f"run_health.{leaf} should be omitted, not null"

    loaded = tea.load_record(out_path)  # must LOAD (not raise) -- just be invalid
    assert loaded.provenance_valid is False
    assert loaded.solver_status == "failed"
    # T0.3's real evaluator still ran and correctly named the reason.
    assert loaded.reason_code == "run_not_solved"


# ===========================================================================
# cross-field invariants (exit criterion 12)
# ===========================================================================
class TestCrossFieldInvariants:
    def test_a_well_formed_record_passes(self, real_record):
        record, _omitted = real_record
        prod.check_cross_field_invariants(record)  # must not raise

    def test_failed_but_provenance_valid_true_is_caught(self, real_record):
        import dataclasses as dc

        record, _omitted = real_record
        corrupted = dc.replace(record, solver_status="failed", provenance_valid=True)
        with pytest.raises(prod.ArtifactProducerError, match="provenance_valid"):
            prod.check_cross_field_invariants(corrupted)

    def test_cr_capped_disagreeing_with_nstp_is_caught(self, real_record):
        import dataclasses as dc

        record, _omitted = real_record
        corrupted = dc.replace(record, cr_capped=True, nstp=1, nstp_cap=999999)
        with pytest.raises(prod.ArtifactProducerError, match="cr_capped"):
            prod.check_cross_field_invariants(corrupted)

    def test_horizon_censored_disagreeing_with_metric_censoring_is_caught(self, real_record):
        import dataclasses as dc

        record, _omitted = real_record
        flipped_metrics = dict(record.metrics)
        peak = flipped_metrics["peak_mgL"]
        flipped_metrics["peak_mgL"] = dc.replace(peak, censored=not peak.censored)
        corrupted = dc.replace(record, metrics=flipped_metrics)
        with pytest.raises(prod.ArtifactProducerError, match="horizon_censored"):
            prod.check_cross_field_invariants(corrupted)


# ===========================================================================
# recorded metrics match the actual run outputs (exit criterion 11)
# ===========================================================================
@pytest.mark.slow
def test_recorded_metrics_match_the_actual_run_outputs(real_case_ws, real_record):
    """Reproducibility alone (the hash test above) only proves the same
    record comes out twice -- it does not prove the record agrees with the
    real run. This re-fetches the SAME content-addressed cache entry via a
    SEPARATE call into the model (bypassing the producer entirely) and
    compares field-by-field."""
    record, _omitted = real_record
    independent_result = tsd.build_srcpulse_demo(
        case_ws=real_case_ws / "srcpulse", force=False,  # warm-cache hit, same identity
    )
    assert record.metrics["peak_mgL"].value == pytest.approx(independent_result.peak_mgL)
    assert record.metrics["t_peak"].value == pytest.approx(independent_result.t_peak)
    assert record.cr_achieved == pytest.approx(independent_result.meta["Cr"])
    assert record.nstp == independent_result.meta["nstp"]
    assert record.ncpl == independent_result.meta["ncpl"]
    assert record.cr_capped == bool(independent_result.meta["cr_capped"])
    assert record.horizon_censored == bool(independent_result.meta["peak_at_last_step"])
    assert record.source_footprint.entries[0].cell == independent_result.src_cells[0]
    assert record.source_footprint.total_rate_g_per_day == pytest.approx(
        independent_result.smassrate_gpd
    )


# ===========================================================================
# footprint_from_result / controls_from_inputs / metrics_from_result --
# pure-logic unit tests against the synthetic `_fake_result`, no MF6.
# ===========================================================================
class TestFootprintFromResult:
    def test_sentinel_footprint_is_derived_from_the_payload(self):
        result = _fake_result()
        fp = prod.footprint_from_result(result, footprint_radius_m=0.0)
        assert fp is not None
        assert fp.radius_m == 0.0
        assert fp.entries[0].cell == 42
        assert fp.entries[0].rate_g_per_day == pytest.approx(10000.0)
        assert fp.total_rate_g_per_day == pytest.approx(10000.0)
        assert fp.coverage.disc_area_m2 == 0.0
        assert fp.coverage.covered_area_m2 == 0.0
        assert fp.algorithm_id == tsd._FOOTPRINT_ALGORITHM_ID

    def test_positive_radius_footprint_is_not_fabricated(self):
        """Named gap (module docstring): a positive radius cannot be
        derived from the public payload -- the producer must say so by
        returning None, never inventing plausible-looking geometry."""
        result = _fake_result()
        fp = prod.footprint_from_result(result, footprint_radius_m=10.0)
        assert fp is None


class TestControlsFromInputs:
    def test_sentinel_sink_support_yields_no_controls(self):
        assert prod.controls_from_inputs(
            sink_support_m=0.0, uncontrolled_counterpart_run_id=None
        ) == {}

    def test_positive_sink_support_yields_a_control_record(self):
        controls = prod.controls_from_inputs(
            sink_support_m=15.0, uncontrolled_counterpart_run_id="uncontrolled-run-1"
        )
        assert set(controls.keys()) == {"sink_support_controlled"}
        c = controls["sink_support_controlled"]
        assert c.sink_support_m == 15.0
        assert c.uncontrolled_counterpart_run_id == "uncontrolled-run-1"
        assert c.prt_capture_diverges is True


class TestMetricsFromResult:
    def test_default_path_uses_the_legacy_lattice_algorithm(self):
        result = _fake_result()
        metrics = prod.metrics_from_result(result, is_experimental=False)
        assert metrics["t_peak"].algorithm_id == prod.LEGACY_T_PEAK_ALGORITHM_ID
        assert metrics["t_peak"].interpolated is False
        assert metrics["t_peak"].value == pytest.approx(30.0)
        assert metrics["peak_mgL"].algorithm_id == prod.PEAK_ALGORITHM_ID

    def test_experimental_path_uses_the_interpolated_evaluator(self):
        result = _fake_result()
        metrics = prod.metrics_from_result(result, is_experimental=True)
        assert metrics["t_peak"].interpolated is True
        assert metrics["t_peak"].algorithm_id != prod.LEGACY_T_PEAK_ALGORITHM_ID
        # peak_mgL's algorithm NEVER changes with exp/vN (T0_2b Sec 2.1).
        assert metrics["peak_mgL"].algorithm_id == prod.PEAK_ALGORITHM_ID

    def test_never_arrived_is_censored_not_a_fabricated_number(self):
        result = _fake_result(arrival_day=float("nan"), t_peak=float("nan"))
        metrics = prod.metrics_from_result(result, is_experimental=False)
        assert metrics["t_peak"].value is None
        assert metrics["t_peak"].censored is True

    def test_peak_at_last_step_censors_the_peak(self):
        result = _fake_result(meta=dict(ncpl=1, nstp=1, dt=1.0, Cr=0.5,
                                         cr_capped=False, peak_at_last_step=True))
        metrics = prod.metrics_from_result(result, is_experimental=False)
        assert metrics["peak_mgL"].censored is True
        assert metrics["peak_mgL"].value is None


# ===========================================================================
# claim_id / roster_hash sourcing (brief Sec 2.4)
# ===========================================================================
class TestClaimIdAndRosterHash:
    def test_real_claim_id_validates(self):
        prod.validate_claim_id(REAL_CLAIM_ID)  # must not raise

    def test_synthesised_claim_id_is_rejected(self):
        with pytest.raises(prod.UnknownClaimIdError):
            prod.validate_claim_id("not_a_real_inventory_id")

    def test_run_and_build_record_rejects_an_unsourced_claim_id_before_any_model_work(
        self, tmp_path, monkeypatch
    ):
        """The rejection must happen BEFORE `build_srcpulse_demo` is ever
        called -- monkeypatch it to explode if reached, proving the claim_id
        gate runs first."""

        def _must_not_be_called(*args, **kwargs):
            raise AssertionError("build_srcpulse_demo must not run for an invalid claim_id")

        monkeypatch.setattr(tsd, "build_srcpulse_demo", _must_not_be_called)
        with pytest.raises(prod.UnknownClaimIdError):
            prod.run_and_build_record(
                run_id="should-never-run", case_id="case_pfoa_reference",
                claim_id="not_a_real_inventory_id", claim_type="numeric",
                metric="peak_mgL", tolerance=0.02, run_role="pilot",
                case_ws=tmp_path / "unused",
            )

    def test_roster_hash_sources_from_the_shipped_case_roster(self):
        assert prod.CASE_ROSTER_PATH.is_file(), (
            "the shipped case roster is expected on disk in this repo checkout"
        )
        h = prod.roster_hash()
        assert h is not None
        assert h == prod._sha256_file(prod.CASE_ROSTER_PATH)

    def test_roster_hash_is_none_not_a_placeholder_when_absent(self, monkeypatch):
        monkeypatch.setattr(prod, "CASE_ROSTER_PATH", Path("/nonexistent/doublet_table.csv"))
        assert prod.roster_hash() is None


# ---------------------------------------------------------------------------
# provenance_valid is DERIVED, not declared -- the regression that slipped
# through the first implementation
# ---------------------------------------------------------------------------
def test_provenance_valid_is_derived_from_required_field_paths_not_a_rule():
    """Brief Sec 2.1, and a real defect caught in review of the first S14
    implementation.

    That version set `provenance_valid` from a hand-written rule about the
    RUN (`solved and source_footprint is not None`). A rule can disagree with
    the record it labels: drop any OTHER required field -- `roster_hash`, an
    environment leaf -- and the rule still says True while the written record
    is incomplete. `T0_2b` Sec 5.1 defines the predicate the other way round:
    "a record missing any field above is provenance_valid = false."

    This test pins the derivation by asserting the producer consults the
    frozen required-path set, and that dropping one required field really
    does flip the verdict.
    """
    import inspect

    import t1_evidence_artifact as tea

    # the module must actually reference the frozen set -- a rule that merely
    # happens to agree today is what this test exists to reject
    src = inspect.getsource(prod)
    assert "REQUIRED_FIELD_PATHS" in src, (
        "provenance_valid must be derived from the frozen required-path set, "
        "not from a hand-written predicate about the run"
    )

    # and the derivation must be sensitive to EVERY required path, not just
    # the two the old rule looked at
    complete = tea.build_fixture_record(run_role=tea.RUN_ROLES[0])
    raw = tea.record_to_raw_dict(complete)
    assert not [p for p in tea.REQUIRED_FIELD_PATHS if not tea._has_path(raw, p)]

    for victim in (("fingerprints", "roster_hash"),
                   ("environment", "mf6_sha256"),
                   ("run_identity", "case_id")):
        wounded = tea.record_to_raw_dict(complete)
        prod._delete_path(wounded, victim)
        missing = [p for p in tea.REQUIRED_FIELD_PATHS if not tea._has_path(wounded, p)]
        assert missing == [victim], (
            f"dropping {victim} must register as exactly one missing required path"
        )


def test_grid_spec_holds_only_the_grid():
    """The promotion, pinned (lecturer, 2026-08-26).

    `courant_profile` and `experimental` used to live inside `grid_spec`'s
    opaque mapping. That was structurally legal -- the schema declares
    `grid_spec` opaque and `T0_2b` Sec 5.1 calls it "the full
    parameterisation" -- but semantically wrong: `courant_profile` is a
    TIME-STEPPING policy and `experimental` classifies the RUN, so `grid_spec`
    became a grab-bag a T2 consumer would read expecting mesh geometry.

    This asserts the shape T2 will depend on, since changing it after T2
    consumes records is a failure edge rather than an edit.
    """
    import t1_evidence_artifact as tea

    payload = prod.grid_spec_payload(resolved_mesh_spec=tsd.MeshSpec())
    assert set(payload) == {"mesh_spec"}, (
        f"grid_spec must hold only the grid, got {sorted(payload)}"
    )

    # and the two promoted fields are first-class REQUIRED siblings
    for path in (("run_identity", "courant_profile"),
                 ("run_identity", "experimental")):
        assert path in tea.REQUIRED_FIELD_PATHS, f"{path} must be required"

    rec = tea.build_fixture_record(run_role=tea.RUN_ROLES[0])
    raw = tea.record_to_raw_dict(rec)
    assert "experimental" not in raw["run_identity"]["grid_spec"]
    assert "courant_profile" not in raw["run_identity"]["grid_spec"]
    assert raw["run_identity"]["courant_profile"]
    assert "is_experimental" in raw["run_identity"]["experimental"]
