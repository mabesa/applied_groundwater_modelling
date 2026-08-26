"""Tests for T1 step S10 -- the GWF-grid sensitivity arm
(`DESIGN_DOCS/T1_S10_brief.md` v2).

Authority: A13 (`transport_srcpulse_demo.py`) only.

Scope (brief header): "Gate coverage: BLIND -- S10 adds no default-path
behaviour. The Sec 5 tests are the safety argument." This file IS that
safety argument, not a supplement to the `compare` gate.

Almost every test below is a FAST, pure-Python unit test against synthetic
`MeshFlowDiagnostics` / `CaptureFingerprintRecord` fixtures -- exactly the
composition/validation logic the brief's exit-criteria table exercises
(refusal rules, provenance validation, ordering, serialisation). The one
real MODFLOW 6 solve this module's production code can perform
(`solve_mesh_flow` / `run_gwf_grid_sensitivity_arm`) is expensive (brief:
"~316 s for a fine mesh on a fast Mac; Hub speed unmeasured") and is
exercised by a single `@pytest.mark.slow` integration test at the bottom,
proving the real capability end-to-end without paying that cost on every
run.

Run with:  uv run pytest _SUPPORT/tests/test_t1_gwf_grid_sensitivity.py -v
Use `-m "not slow"` to run only the fast, solve-free tests.
"""
from __future__ import annotations

import ast
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_srcpulse_demo as tsd  # noqa: E402

SRC_FILE = Path(tsd.__file__).resolve()

# Pinned identically to test_t1_src_closure.py::DEMO_EXPECTED -- this file
# does not import that test module (it is a sibling test file, not
# production code), so the set is repeated here rather than imported, per
# the brief's own "the frozen 7-module demo closure test still passes"
# framing (exit criterion 4).
DEMO_EXPECTED = {
    "case_artifact_lock", "casestudy_refine_riv", "data_utils",
    "disv_grid_utils", "grid_utils", "model_io_utils", "transport_srcpulse_demo",
}


# ---------------------------------------------------------------------------
# fixtures -- synthetic MeshFlowDiagnostics / CaptureFingerprintRecord, no
# MF6 solve needed
# ---------------------------------------------------------------------------
def _mesh_id(tag: str) -> str:
    """A stand-in mesh identity string -- any non-empty, distinct string
    works for the composition/validation logic under test; the real
    `mesh_hash()` machinery is exercised elsewhere (test_t1_gridspec.py)."""
    return f"meshid_{tag}"


def _diag(tag: str, *, q_src: float, q_rcpt: float, head_diff: float,
          q_ext: float, support_cells=(11,), platform="darwin-arm64",
          solved=True, solver_status="converged") -> tsd.MeshFlowDiagnostics:
    mid = _mesh_id(tag)
    flow_id = tsd.flow_identity_string(mid, support_cells) if solved else ""
    return tsd.MeshFlowDiagnostics(
        mesh_id=mid, mesh_spec_hash=f"specid_{tag}",
        q_source_darcy_m_d=q_src if solved else float("nan"),
        q_receptor_darcy_m_d=q_rcpt if solved else float("nan"),
        head_diff_corridor_m=head_diff if solved else float("nan"),
        extraction_throughflow_m3d=q_ext if solved else float("nan"),
        flow_identity=flow_id, platform=platform, solved=solved,
        solver_status=solver_status,
    )


def _fp(tag: str, *, mesh_tag: str, support_cells=(11,), value_m=53.0,
        platform="darwin-arm64", producing_run_id=None, method_id="prt_capture_halfwidth@v1",
        compatibility_status="compatible") -> tsd.CaptureFingerprintRecord:
    mid = _mesh_id(mesh_tag)
    return tsd.CaptureFingerprintRecord(
        value_m=value_m, platform=platform,
        producing_run_id=producing_run_id or f"prtrun_{tag}",
        mesh_id=mid,
        flow_identity=tsd.flow_identity_string(mid, support_cells),
        method_id=method_id, compatibility_status=compatibility_status,
    )


REFERENCE = lambda: _diag("ref", q_src=1.0, q_rcpt=2.0, head_diff=3.0, q_ext=4.0)  # noqa: E731
CANDIDATE = lambda: _diag("cand", q_src=1.2, q_rcpt=1.8, head_diff=2.7, q_ext=4.4)  # noqa: E731


# ---------------------------------------------------------------------------
# exit criterion 4 / named tests: PRT is neither imported nor modified
# ---------------------------------------------------------------------------
def test_demo_module_does_not_import_prt():
    """AST-based, not a substring grep: catches `import transport_prt_capture`
    and `from transport_prt_capture import ...` in any form, anywhere in the
    module, at any nesting depth."""
    tree = ast.parse(SRC_FILE.read_text(encoding="utf-8"), filename=str(SRC_FILE))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert "transport_prt_capture" not in names


def test_demo_closure_is_still_exactly_seven_modules():
    closure = tsd._resolve_src_closure(tsd.__file__)
    assert set(closure) == DEMO_EXPECTED, (
        "S10 must not grow the frozen 7-module demo source closure -- a "
        "reverse import edge to transport_prt_capture (or any other new "
        "module) would show up here first")


def test_fingerprint_is_injected_not_computed():
    """S10 has no code path that CALLS PRT to obtain a fingerprint -- proven
    at runtime (a fresh subprocess importing only this module never pulls
    transport_prt_capture into sys.modules), not just by the AST scan above."""
    src_dir = str(SRC_FILE.parent)
    code = (
        f"import sys; sys.path.insert(0, {src_dir!r})\n"
        "import transport_srcpulse_demo as tsd\n"
        "assert 'transport_prt_capture' not in sys.modules\n"
        "print('ok')\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"
    # and the public API never accepts "compute it yourself" -- only an
    # already-built CaptureFingerprintRecord can be attached.
    import inspect
    sig = inspect.signature(tsd.assemble_gwf_grid_sensitivity_arm)
    assert "fingerprints" in sig.parameters


# ---------------------------------------------------------------------------
# exit criteria 2 / 5 / 11 / 12: the injected fingerprint, its refusal rules
# ---------------------------------------------------------------------------
def test_capture_fingerprint_refused_when_sink_support_is_distributed():
    """Today's B-control configuration (brief Sec 2.2): the arm's OWN solved
    flow realizes the extraction sink through MULTIPLE cells (a distributed
    support disc), while the injected fingerprint's flow_identity was
    computed from PRT's hard-coded SINGLE-CELL doublet. The two flow
    identities differ -> refused. The rule tested is flow-IDENTITY equality,
    never a literal `sink_support_m > 0` check (brief Sec 2.2's round-1
    finding) -- see test_fingerprint_from_another_mesh_raises and
    test_injected_record_validated_against_run_mesh_and_flow_identity for
    the same validator exercised on other mismatch axes.
    """
    mid = _mesh_id("distributed")
    distributed_diag = tsd.MeshFlowDiagnostics(
        mesh_id=mid, mesh_spec_hash="spec_distributed",
        q_source_darcy_m_d=1.0, q_receptor_darcy_m_d=1.0,
        head_diff_corridor_m=1.0, extraction_throughflow_m3d=1.0,
        flow_identity=tsd.flow_identity_string(mid, (10, 11, 12)),
        platform="darwin-arm64", solved=True, solver_status="converged")
    prt_single_cell_fp = _fp("x", mesh_tag="distributed", support_cells=(11,))
    with pytest.raises(tsd.FingerprintFlowIncompatibleError):
        tsd._validate_capture_fingerprint(
            prt_single_cell_fp, mesh_id=distributed_diag.mesh_id,
            flow_identity=distributed_diag.flow_identity)

    # and the SAME rule is enforced through the public assemble() entrypoint
    ref = REFERENCE()
    with pytest.raises(tsd.FingerprintFlowIncompatibleError):
        tsd.assemble_gwf_grid_sensitivity_arm(
            [ref, distributed_diag], reference_mesh_id=ref.mesh_id,
            fingerprints={distributed_diag.mesh_id: prt_single_cell_fp})

    # and a future fingerprint LEGITIMATELY computed from the SAME
    # distributed-support flow is NOT wrongly blocked (brief Sec 2.2:
    # "would wrongly block a future fingerprint legitimately computed from
    # the distributed-support flow").
    matching_fp = _fp("y", mesh_tag="distributed", support_cells=(10, 11, 12))
    tsd._validate_capture_fingerprint(  # does not raise
        matching_fp, mesh_id=distributed_diag.mesh_id,
        flow_identity=distributed_diag.flow_identity)


def test_fingerprint_from_another_mesh_raises():
    ref = REFERENCE()
    cand = CANDIDATE()
    fp_for_ref = _fp("a", mesh_tag="ref")
    # supplied keyed under the CANDIDATE's mesh id, but the record itself
    # names the REFERENCE mesh -- a swap.
    with pytest.raises(tsd.FingerprintMeshMismatchError):
        tsd.assemble_gwf_grid_sensitivity_arm(
            [ref, cand], reference_mesh_id=ref.mesh_id,
            fingerprints={cand.mesh_id: fp_for_ref})


def test_injected_record_validated_against_run_mesh_and_flow_identity():
    ref = REFERENCE()
    cand = CANDIDATE()
    fp = _fp("a", mesh_tag="ref", producing_run_id="prt_run_007")
    result = tsd.assemble_gwf_grid_sensitivity_arm(
        [ref, cand], reference_mesh_id=ref.mesh_id,
        fingerprints={ref.mesh_id: fp})
    # the validated record rides along, unmodified, with its own producing
    # run id intact -- proof the arm records provenance rather than
    # discarding it once validated.
    assert result.fingerprints[ref.mesh_id].producing_run_id == "prt_run_007"
    assert result.fingerprints[ref.mesh_id].mesh_id == ref.mesh_id
    assert result.fingerprints[ref.mesh_id].flow_identity == ref.flow_identity

    # mesh mismatch -> raise (exit criterion 12)
    bad_mesh_fp = _fp("b", mesh_tag="cand")
    with pytest.raises(tsd.FingerprintMeshMismatchError):
        tsd.assemble_gwf_grid_sensitivity_arm(
            [ref, cand], reference_mesh_id=ref.mesh_id,
            fingerprints={ref.mesh_id: bad_mesh_fp})

    # flow-identity mismatch -> raise (exit criterion 2/5/11)
    bad_flow_fp = _fp("c", mesh_tag="ref", support_cells=(99,))
    with pytest.raises(tsd.FingerprintFlowIncompatibleError):
        tsd.assemble_gwf_grid_sensitivity_arm(
            [ref, cand], reference_mesh_id=ref.mesh_id,
            fingerprints={ref.mesh_id: bad_flow_fp})


def test_two_meshes_produce_distinct_flow_identities():
    ref = REFERENCE()
    cand = CANDIDATE()
    assert ref.mesh_id != cand.mesh_id
    assert ref.flow_identity != cand.flow_identity  # distinct mesh_id folded in
    # same mesh, different realized support -> different identity too
    same_mesh_a = tsd.flow_identity_string("m1", (11,))
    same_mesh_b = tsd.flow_identity_string("m1", (10, 11, 12))
    assert same_mesh_a != same_mesh_b
    # order-independent (a set of realized cells, not a sequence)
    assert tsd.flow_identity_string("m1", (12, 10, 11)) == same_mesh_b


# ---------------------------------------------------------------------------
# exit criterion 3 / 10: platform recorded, cross-platform / envelope rules
# ---------------------------------------------------------------------------
def test_platform_recorded_with_every_fingerprint():
    fp = _fp("a", mesh_tag="ref")
    assert fp.platform in tsd.SUPPORTED_PLATFORMS
    d = tsd.dataclasses.asdict(fp)
    assert "platform" in d and d["platform"] == fp.platform
    diag = REFERENCE()
    assert diag.platform in tsd.SUPPORTED_PLATFORMS


def test_cross_platform_fingerprint_comparison_raises():
    fp_a = _fp("a", mesh_tag="ref", platform="darwin-arm64", value_m=50.0)
    fp_b = _fp("b", mesh_tag="ref", platform="linux-x86_64", value_m=53.0)
    with pytest.raises(tsd.CrossPlatformFingerprintComparisonError):
        tsd.compare_fingerprints(fp_a, fp_b, envelope=None)
    # even WITH an envelope, cross-platform still raises (checked first)
    env = tsd.RepeatabilityEnvelope(platform="darwin-arm64", n_replicates=3,
                                    spread_rel=0.01,
                                    replicate_run_ids=("r1", "r2", "r3"))
    with pytest.raises(tsd.CrossPlatformFingerprintComparisonError):
        tsd.compare_fingerprints(fp_a, fp_b, envelope=env)


def test_comparison_raises_without_a_repeatability_envelope():
    fp_a = _fp("a", mesh_tag="ref", platform="darwin-arm64", value_m=50.0)
    fp_b = _fp("b", mesh_tag="ref", platform="darwin-arm64", value_m=51.0)
    with pytest.raises(tsd.MissingRepeatabilityEnvelopeError):
        tsd.compare_fingerprints(fp_a, fp_b, envelope=None)


def test_same_platform_comparison_is_permitted():
    fp_a = _fp("a", mesh_tag="ref", platform="darwin-arm64", value_m=50.0)
    fp_b = _fp("b", mesh_tag="ref", platform="darwin-arm64", value_m=51.0)
    env = tsd.RepeatabilityEnvelope(platform="darwin-arm64", n_replicates=4,
                                    spread_rel=0.02,
                                    replicate_run_ids=("r1", "r2", "r3", "r4"))
    result = tsd.compare_fingerprints(fp_a, fp_b, envelope=env)
    assert result.delta_m == pytest.approx(1.0)
    assert result.delta_rel == pytest.approx(1.0 / 50.0)
    assert result.platform == "darwin-arm64"

    # an envelope on the WRONG platform still refuses a same-platform pair
    wrong_platform_env = tsd.RepeatabilityEnvelope(
        platform="linux-x86_64", n_replicates=4, spread_rel=0.02,
        replicate_run_ids=("h1", "h2", "h3", "h4"))
    with pytest.raises(tsd.RepeatabilityEnvelopeMismatchError):
        tsd.compare_fingerprints(fp_a, fp_b, envelope=wrong_platform_env)

    # an envelope whose spread is NOT demonstrably below TOL_WIDTH_REL
    # refuses too, even same-platform (the ~24% observed spread case)
    loose_env = tsd.RepeatabilityEnvelope(
        platform="darwin-arm64", n_replicates=4, spread_rel=0.24,
        replicate_run_ids=("l1", "l2", "l3", "l4"))
    with pytest.raises(tsd.RepeatabilityEnvelopeInsufficientError):
        tsd.compare_fingerprints(fp_a, fp_b, envelope=loose_env)


def test_missing_nan_or_negative_fingerprint_raises():
    kwargs = dict(platform="darwin-arm64", producing_run_id="r1",
                 mesh_id="m1", flow_identity="f1", method_id="algo@v1",
                 compatibility_status="compatible")
    with pytest.raises(tsd.MalformedFingerprintError):
        tsd.CaptureFingerprintRecord(value_m=float("nan"), **kwargs)
    with pytest.raises(tsd.MalformedFingerprintError):
        tsd.CaptureFingerprintRecord(value_m=-1.0, **kwargs)
    with pytest.raises(tsd.MalformedFingerprintError):
        tsd.CaptureFingerprintRecord(value_m=None, **kwargs)
    # missing/empty string fields raise too (structural completeness)
    bad = dict(kwargs)
    bad["producing_run_id"] = ""
    with pytest.raises(tsd.MalformedFingerprintError):
        tsd.CaptureFingerprintRecord(value_m=50.0, **bad)


def test_unsupported_platform_raises():
    kwargs = dict(producing_run_id="r1", mesh_id="m1", flow_identity="f1",
                 method_id="algo@v1", compatibility_status="compatible")
    with pytest.raises(tsd.UnsupportedPlatformError):
        tsd.CaptureFingerprintRecord(value_m=50.0, platform="windows-x86_64", **kwargs)
    with pytest.raises(tsd.UnsupportedPlatformError):
        tsd.RepeatabilityEnvelope(platform="windows-x86_64", n_replicates=2,
                                  spread_rel=0.01, replicate_run_ids=("a", "b"))


# ---------------------------------------------------------------------------
# exit criterion 1 / 17: non-isolation statement in the code + every export
# path
# ---------------------------------------------------------------------------
def test_arm_states_it_does_not_isolate_the_flow_field():
    ref = REFERENCE()
    cand = CANDIDATE()
    result = tsd.assemble_gwf_grid_sensitivity_arm(
        [ref, cand], reference_mesh_id=ref.mesh_id)
    assert result.non_isolation_statement == tsd.NON_ISOLATION_STATEMENT
    assert result.claim_ceiling == "hypothesis"
    assert "cause" not in result.claim_ceiling
    assert "isolat" in result.non_isolation_statement.lower()

    # structurally impossible to construct a result claiming otherwise
    with pytest.raises(ValueError):
        tsd.GwfGridSensitivityArmResult(
            reference_mesh_id=ref.mesh_id, mesh_results=(ref, cand),
            deltas=(), fingerprints={}, non_isolation_statement="all good, isolated")
    with pytest.raises(ValueError):
        tsd.GwfGridSensitivityArmResult(
            reference_mesh_id=ref.mesh_id, mesh_results=(ref, cand),
            deltas=(), fingerprints={}, claim_ceiling="cause")
    with pytest.raises(ValueError):
        tsd.GwfGridSensitivityArmResult(
            reference_mesh_id=ref.mesh_id, mesh_results=(ref, cand),
            deltas=(), fingerprints={}, is_control=True)


def test_every_export_path_preserves_the_non_isolation_statement():
    ref = REFERENCE()
    cand = CANDIDATE()
    result = tsd.assemble_gwf_grid_sensitivity_arm(
        [ref, cand], reference_mesh_id=ref.mesh_id)

    d = result.to_dict()
    assert d["non_isolation_statement"] == tsd.NON_ISOLATION_STATEMENT
    assert d["claim_ceiling"] == "hypothesis"

    j = json.loads(result.to_json())
    assert j["non_isolation_statement"] == tsd.NON_ISOLATION_STATEMENT
    assert j["claim_ceiling"] == "hypothesis"

    text = result.summary_text()
    assert tsd.NON_ISOLATION_STATEMENT in text
    assert "hypothesis" in text

    table = result.deltas_table()
    assert table["non_isolation_statement"] == tsd.NON_ISOLATION_STATEMENT
    assert table["claim_ceiling"] == "hypothesis"
    assert len(table["rows"]) > 0


# ---------------------------------------------------------------------------
# exit criterion 7: no CONTROL label; role group reused
# ---------------------------------------------------------------------------
def test_no_control_label_added():
    assert not hasattr(tsd, "CONTROL_LABELS")
    assert not hasattr(tsd, "ControlRecord")
    ref = REFERENCE()
    cand = CANDIDATE()
    result = tsd.assemble_gwf_grid_sensitivity_arm(
        [ref, cand], reference_mesh_id=ref.mesh_id)
    assert result.is_control is False
    assert "control" not in result.analysis_kind.lower()
    # the frozen Role group IS present
    assert result.run_role in ("spatial_series", "temporal_series", "b_control",
                               "pilot", "feasibility_probe")
    assert result.run_role != "b_control"
    assert result.counterpart_run_id == ref.mesh_id


# ---------------------------------------------------------------------------
# exit criterion 9: quantified flow deltas
# ---------------------------------------------------------------------------
def test_quantified_flow_deltas_are_reported():
    ref = REFERENCE()   # q_src=1.0, q_rcpt=2.0, head_diff=3.0, q_ext=4.0
    cand = CANDIDATE()  # q_src=1.2, q_rcpt=1.8, head_diff=2.7, q_ext=4.4
    result = tsd.assemble_gwf_grid_sensitivity_arm(
        [ref, cand], reference_mesh_id=ref.mesh_id)
    assert len(result.deltas) == 1
    delta = result.deltas[0]
    assert delta.mesh_id == cand.mesh_id
    assert delta.reference_mesh_id == ref.mesh_id
    assert delta.d_q_source_darcy_m_d == pytest.approx(0.2)
    assert delta.d_q_source_darcy_rel == pytest.approx(0.2)
    assert delta.d_q_receptor_darcy_m_d == pytest.approx(-0.2)
    assert delta.d_q_receptor_darcy_rel == pytest.approx(-0.1)
    assert delta.d_head_diff_corridor_m == pytest.approx(-0.3)
    assert delta.d_head_diff_corridor_rel == pytest.approx(-0.1)
    assert delta.d_extraction_throughflow_m3d == pytest.approx(0.4)
    assert delta.d_extraction_throughflow_rel == pytest.approx(0.1)

    # zero-reference edge case does not raise/inf -- relative delta is None
    zero_ref = _diag("zero", q_src=0.0, q_rcpt=1.0, head_diff=1.0, q_ext=1.0)
    other = _diag("other", q_src=0.5, q_rcpt=1.0, head_diff=1.0, q_ext=1.0)
    zresult = tsd.assemble_gwf_grid_sensitivity_arm(
        [zero_ref, other], reference_mesh_id=zero_ref.mesh_id)
    assert zresult.deltas[0].d_q_source_darcy_rel is None
    assert zresult.deltas[0].d_q_source_darcy_m_d == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# exit criteria 13 / 15: duplicates, ordering, misalignment, failed solves
# ---------------------------------------------------------------------------
def test_duplicate_mesh_ids_raise():
    ref = REFERENCE()
    dupe = _diag("ref", q_src=9.0, q_rcpt=9.0, head_diff=9.0, q_ext=9.0)
    assert dupe.mesh_id == ref.mesh_id
    with pytest.raises(tsd.DuplicateMeshIdError):
        tsd.assemble_gwf_grid_sensitivity_arm(
            [ref, dupe], reference_mesh_id=ref.mesh_id)


def test_multi_mesh_ordering_is_deterministic():
    ref = REFERENCE()
    cand = CANDIDATE()
    third = _diag("third", q_src=1.5, q_rcpt=1.5, head_diff=1.5, q_ext=1.5)
    meshes = [ref, cand, third]
    r1 = tsd.assemble_gwf_grid_sensitivity_arm(meshes, reference_mesh_id=ref.mesh_id)
    r2 = tsd.assemble_gwf_grid_sensitivity_arm(meshes, reference_mesh_id=ref.mesh_id)
    assert [d.mesh_id for d in r1.mesh_results] == [d.mesh_id for d in r2.mesh_results]
    assert [d.mesh_id for d in r1.mesh_results] == [ref.mesh_id, cand.mesh_id, third.mesh_id]
    assert [d.mesh_id for d in r1.deltas] == [cand.mesh_id, third.mesh_id]

    # a fingerprint naming a mesh id outside this arm is a detectable
    # misalignment
    stray_fp = _fp("stray", mesh_tag="not_in_this_arm")
    with pytest.raises(ValueError):
        tsd.assemble_gwf_grid_sensitivity_arm(
            meshes, reference_mesh_id=ref.mesh_id,
            fingerprints={"meshid_not_in_this_arm": stray_fp})

    # reference_mesh_id itself not among the supplied meshes
    with pytest.raises(ValueError):
        tsd.assemble_gwf_grid_sensitivity_arm(meshes, reference_mesh_id="meshid_ghost")


def test_failed_solve_is_not_recorded_as_a_successful_arm():
    ref = REFERENCE()
    failed = _diag("failed", q_src=0, q_rcpt=0, head_diff=0, q_ext=0,
                   solved=False, solver_status="mf6 did not converge (ok=False)")
    # constructing the failed record itself does not raise -- it is
    # REPRESENTED explicitly, not silently produced as a false success
    assert failed.solved is False
    assert "did not converge" in failed.solver_status

    with pytest.raises(tsd.MeshSolveFailedError):
        tsd.assemble_gwf_grid_sensitivity_arm(
            [ref, failed], reference_mesh_id=ref.mesh_id)

    # a solved=False record with an empty solver_status is itself malformed
    with pytest.raises(ValueError):
        tsd.MeshFlowDiagnostics(
            mesh_id="m1", mesh_spec_hash="s1", q_source_darcy_m_d=float("nan"),
            q_receptor_darcy_m_d=float("nan"), head_diff_corridor_m=float("nan"),
            extraction_throughflow_m3d=float("nan"), flow_identity="",
            platform="darwin-arm64", solved=False, solver_status="")


# ---------------------------------------------------------------------------
# exit criterion 16: deterministic serialization
# ---------------------------------------------------------------------------
def test_serialization_is_deterministic():
    ref = REFERENCE()
    cand = CANDIDATE()
    fp = _fp("a", mesh_tag="ref")
    result_a = tsd.assemble_gwf_grid_sensitivity_arm(
        [ref, cand], reference_mesh_id=ref.mesh_id, fingerprints={ref.mesh_id: fp})

    # freshly-rebuilt, value-equal (but not object-identical) inputs
    ref2 = REFERENCE()
    cand2 = CANDIDATE()
    fp2 = _fp("a", mesh_tag="ref")
    result_b = tsd.assemble_gwf_grid_sensitivity_arm(
        [ref2, cand2], reference_mesh_id=ref2.mesh_id, fingerprints={ref2.mesh_id: fp2})

    assert result_a.to_json() == result_a.to_json()          # stable across calls
    assert result_a.to_json() == result_b.to_json()          # stable across equal inputs
    assert result_a.to_dict() == result_b.to_dict()
    # sort_keys makes key order irrelevant to the string too
    assert json.loads(result_a.to_json()) == json.loads(result_b.to_json())


# ---------------------------------------------------------------------------
# slow, real end-to-end integration -- proves solve_mesh_flow / run_gwf_
# grid_sensitivity_arm actually work against a genuine MF6 solve. Not part
# of the fast/default safety argument above (deselect with -m "not slow").
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_real_single_mesh_solve_reports_finite_diagnostics(tmp_path):
    diag = tsd.solve_mesh_flow(tsd.MeshSpec(), case_ws=tmp_path / "gwf_grid_sensitivity")
    assert diag.solved is True
    assert diag.platform in tsd.SUPPORTED_PLATFORMS
    for value in (diag.q_source_darcy_m_d, diag.q_receptor_darcy_m_d,
                 diag.head_diff_corridor_m, diag.extraction_throughflow_m3d):
        assert math.isfinite(value)
    assert diag.extraction_throughflow_m3d > 0.0
    assert diag.flow_identity  # non-empty -- see flow_identity_string's docstring

    # the arm's own top-level entrypoint accepts this diagnostic as its own
    # (single-mesh, no fingerprint) arm -- exercises assemble() against a
    # REAL solve, not just the synthetic fixtures used everywhere else.
    result = tsd.assemble_gwf_grid_sensitivity_arm([diag], reference_mesh_id=diag.mesh_id)
    assert result.deltas == ()
    assert result.non_isolation_statement == tsd.NON_ISOLATION_STATEMENT
