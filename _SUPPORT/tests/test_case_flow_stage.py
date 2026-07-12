"""
LOCKED acceptance tests for milestone M2-flow-stage.

This milestone wires the M2 pinned-artifact machinery into the M1 instructor
validation harness by adding the real ``flow_refinement`` stage:

  * NEW module ``_SUPPORT/src/case_stages.py`` defining a TOP-LEVEL function
    ``flow_refinement_stage(group)`` that resolves the meshes dir from the
    ``AGM_MESHES_DIR`` env var (documented default when unset), builds the
    group's ``group<N>_flow.npz`` + ``.manifest.json`` paths, and calls
    ``model_io_utils.load_flow_spec(npz, manifest, verify=True)`` to
    hash-verify + decode the pinned artifact. It returns None on success,
    raises a clear exception (naming group + path) when the artifact is
    missing, and propagates ``load_flow_spec``'s ValueError on
    tamper/malformed. It runs NO MODFLOW (no assemble/run) and triggers NO
    Triangle/Voronoi regeneration.
  * ``register_flow_stages()`` — EXPLICIT (not import-time) registration of
    ``flow_refinement_stage`` under stage id ``'flow_refinement'`` via
    ``case_validation.register_stage``; idempotent.
  * The CLI ``validate_case_study_redesign.py`` calls ``register_flow_stages()``
    before running validation.

LOCKED-TEST SCOPING (see milestone brief): NO test runs MODFLOW or real
Triangle/Voronoi/NearestND refinement. ``flow_refinement_stage`` is driven off
a SYNTHETIC pinned artifact created with ``freeze_flow_spec`` on a hand-built
tiny ragged DISV spec, placed under a tmp dir pointed to by ``AGM_MESHES_DIR``.

Run with:  uv run pytest _SUPPORT/tests/test_case_flow_stage.py -v
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import case_validation as cv  # noqa: E402
import model_io_utils as mio  # noqa: E402

_CLI_SCRIPT = SRC_DIR / "scripts" / "validate_case_study_redesign.py"


# =============================================================================
# Synthetic tiny *RAGGED* DISV spec (one triangle nv=3, two quads nv=4).
# Hand-built => no Triangle/Voronoi, SIGILL-free. Same schema freeze_flow_spec
# consumes, exercised by test_pinned_flow_loader.py.
# =============================================================================
_NCPL = 3
_NVERT = 6
_VERTICES = [
    [0, 0.0, 0.0], [1, 10.0, 0.0], [2, 20.0, 0.0],
    [3, 0.0, 10.0], [4, 10.0, 10.0], [5, 20.0, 10.0],
]
_CELL2D = [
    [0, 3.0, 6.0, 3, 3, 0, 4],
    [1, 5.0, 5.0, 4, 0, 1, 4, 3],
    [2, 15.0, 5.0, 4, 1, 2, 5, 4],
]


def _synthetic_spec():
    return {
        "gridprops": {
            "nvert": _NVERT,
            "vertices": [list(v) for v in _VERTICES],
            "cell2d": [list(c) for c in _CELL2D],
            "ncpl": _NCPL,
        },
        "ncpl": _NCPL,
        "top": np.array([10.0, 10.0, 10.0]),
        "botm": np.array([0.0, 0.0, 0.0]),
        "k": np.array([7.5, 3.25, 12.0]),
        "rch": np.array([1e-4, 1e-4, 1e-4]),
        "strt": np.array([8.0, 8.5, 9.0]),
        "idomain": np.ones(_NCPL, dtype=int),
        "chd_cellid": [(0, 0), (0, 2)],
        "chd_head": [8.0, 9.0],
        "riv_cellid": [(0, 1)],
        "riv_stage": [7.5],
        "riv_cond": [50.0],
        "riv_rbot": [6.0],
        "wel_cellid": [(0, 1)],
        "wel_rate": [-30.0],
        "well_cells": [1],
        "refine_radius_used": 175.0,
        "crs": "EPSG:2056",
    }


def _freeze_group(meshes_dir: Path, group) -> Path:
    """Freeze the synthetic spec as ``<meshes_dir>/group<group>_flow.npz``
    (+ sibling manifest) — a SYNTHETIC pinned artifact."""
    meshes_dir.mkdir(parents=True, exist_ok=True)
    npz = meshes_dir / f"group{group}_flow.npz"
    mio.freeze_flow_spec(_synthetic_spec(), npz, caller_fields={"group": group})
    return npz


def _tamper_npz_content(npz_path: Path):
    """Change one member's CONTENT (names + stale manifest intact) -> hash
    mismatch that verify_artifact must reject with ValueError."""
    with np.load(npz_path, allow_pickle=False) as z:
        members = {name: z[name] for name in z.files}
    key = next(k for k in members if members[k].size > 0)
    perturbed = np.array(members[key])
    perturbed.reshape(-1)[0] = perturbed.reshape(-1)[0] + 1
    members[key] = perturbed
    np.savez(npz_path, **members)


def _drop_npz_member(npz_path: Path):
    """Rewrite the .npz missing one member the manifest still records."""
    with np.load(npz_path, allow_pickle=False) as z:
        names = list(z.files)
        members = {name: z[name] for name in names[:-1]}
    np.savez(npz_path, **members)


def _tripwire_regeneration_and_solve(monkeypatch):
    """Trip-wire every geometry-regeneration entry point AND the MF6 solve.

    If the stage touches Triangle/Voronoi/NearestND or runs MODFLOW, it
    explodes -- proving flow_refinement_stage only LOADS + hash-verifies the
    pinned artifact.
    """
    import disv_grid_utils as dgu
    import scipy.interpolate as si
    import flopy

    def boom(*a, **k):
        raise AssertionError(
            "flow_refinement_stage must NOT regenerate geometry or run MODFLOW"
        )

    monkeypatch.setattr(dgu, "create_disv_from_boundary", boom)
    monkeypatch.setattr(dgu, "refine_grid_locally", boom)
    monkeypatch.setattr(si, "NearestNDInterpolator", boom)
    monkeypatch.setattr(mio, "NearestNDInterpolator", boom, raising=False)
    monkeypatch.setattr(flopy.mf6.MFSimulation, "run_simulation", boom)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Keep the shared case_validation registry isolated per test."""
    cv.clear_registry()
    yield
    cv.clear_registry()


# =============================================================================
# Import-time behavior (Criterion 3): importing case_stages must NOT error and
# must register nothing (registration is explicit, not an import side effect).
# Checked in a FRESH interpreter so it is a true import-time observation.
# =============================================================================

class TestImportTime:
    def test_import_does_not_register_anything(self):
        code = (
            "import sys;"
            f"sys.path.insert(0, {str(SRC_DIR)!r});"
            "import case_validation as cv;"
            "import case_stages;"
            "assert cv.registered_stages() == [], cv.registered_stages()"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
        )
        assert result.returncode == 0, (
            f"importing case_stages errored or registered a stage.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# =============================================================================
# flow_refinement_stage is a TOP-LEVEL function (Criterion 1) that
# register_stage accepts.
# =============================================================================

class TestStageIsTopLevel:
    def test_stage_is_plain_top_level_function(self):
        import case_stages

        fn = case_stages.flow_refinement_stage
        assert inspect.isfunction(fn)
        assert "." not in fn.__qualname__, fn.__qualname__
        assert "<" not in fn.__qualname__, fn.__qualname__
        assert fn.__module__ != "__main__"

    def test_register_stage_accepts_it_directly(self):
        import case_stages

        # register_stage's top-level-function guard must accept the stage.
        cv.register_stage("flow_refinement", case_stages.flow_refinement_stage)
        assert "flow_refinement" in cv.registered_stages()


# =============================================================================
# register_flow_stages() (Criterion 2): explicit + idempotent.
# =============================================================================

class TestRegisterFlowStages:
    def test_registers_flow_refinement(self):
        import case_stages

        assert "flow_refinement" not in cv.registered_stages()
        case_stages.register_flow_stages()
        assert "flow_refinement" in cv.registered_stages()

    def test_registered_under_correct_id_and_fn(self):
        import case_stages

        case_stages.register_flow_stages()
        fn, _timeout = cv._REGISTRY["flow_refinement"]
        assert fn is case_stages.flow_refinement_stage

    def test_idempotent(self):
        import case_stages

        case_stages.register_flow_stages()
        # A second call must not raise and must leave it registered once.
        case_stages.register_flow_stages()
        assert cv.registered_stages().count("flow_refinement") == 1


# =============================================================================
# flow_refinement_stage happy path (Criterion 1 + LOCKED scoping): load +
# hash-verify a SYNTHETIC pinned artifact, MODFLOW-free, no regeneration.
# =============================================================================

class TestStageHappyPath:
    GROUP = 3

    def test_returns_none_on_valid_artifact(self, tmp_path, monkeypatch):
        meshes = tmp_path / "meshes"
        _freeze_group(meshes, self.GROUP)
        monkeypatch.setenv("AGM_MESHES_DIR", str(meshes))
        _tripwire_regeneration_and_solve(monkeypatch)

        import case_stages

        assert case_stages.flow_refinement_stage(self.GROUP) is None

    def test_reads_meshes_dir_from_env_var(self, tmp_path, monkeypatch):
        # Artifact lives in dir A; AGM_MESHES_DIR points at empty dir B.
        # The stage must consult the env var (=> miss), not a hardcoded path.
        real = tmp_path / "real_meshes"
        _freeze_group(real, self.GROUP)
        empty = tmp_path / "empty_meshes"
        empty.mkdir()
        monkeypatch.setenv("AGM_MESHES_DIR", str(empty))

        import case_stages

        with pytest.raises(Exception):
            case_stages.flow_refinement_stage(self.GROUP)

    def test_stage_source_does_not_assemble_or_run(self):
        # The design point: flow_refinement_stage LOADS (load_flow_spec), it
        # does not assemble+run MODFLOW (load_pinned_flow_model /
        # assemble_gwf_from_spec / run_simulation).
        import case_stages

        src = inspect.getsource(case_stages.flow_refinement_stage)
        for forbidden in (
            "load_pinned_flow_model",
            "assemble_gwf_from_spec",
            "run_simulation",
            "build_refined_gwf_model",
        ):
            assert forbidden not in src, (
                f"flow_refinement_stage must not reference {forbidden!r}"
            )


# =============================================================================
# flow_refinement_stage error paths (Criterion 1, negative).
# =============================================================================

class TestStageErrorPaths:
    GROUP = 3

    def test_missing_artifact_raises_naming_group_and_path(self, tmp_path, monkeypatch):
        empty = tmp_path / "meshes"
        empty.mkdir()
        monkeypatch.setenv("AGM_MESHES_DIR", str(empty))

        import case_stages

        with pytest.raises(Exception) as exc:
            case_stages.flow_refinement_stage(self.GROUP)
        msg = str(exc.value)
        assert f"group{self.GROUP}" in msg, f"error must name the group: {msg!r}"
        assert (".npz" in msg or str(empty) in msg), (
            f"error must name the artifact path: {msg!r}"
        )

    def test_unset_env_var_has_default_and_still_looks_for_artifact(self, monkeypatch):
        # No AGM_MESHES_DIR => a documented DEFAULT dir is used (not a crash on
        # a missing env var). For an almost-certainly-absent artifact the stage
        # must raise a missing-artifact error naming the group -- NOT a bare
        # KeyError about the unset env var.
        monkeypatch.delenv("AGM_MESHES_DIR", raising=False)

        import case_stages

        group = 987654  # no such pinned artifact anywhere
        with pytest.raises(Exception) as exc:
            case_stages.flow_refinement_stage(group)
        msg = str(exc.value)
        assert f"group{group}" in msg or ".npz" in msg, (
            f"unset env var must fall back to a default meshes dir and raise a "
            f"missing-artifact error, got: {msg!r}"
        )

    def test_tampered_content_propagates_valueerror(self, tmp_path, monkeypatch):
        meshes = tmp_path / "meshes"
        npz = _freeze_group(meshes, self.GROUP)
        _tamper_npz_content(npz)
        monkeypatch.setenv("AGM_MESHES_DIR", str(meshes))

        import case_stages

        with pytest.raises(ValueError):
            case_stages.flow_refinement_stage(self.GROUP)

    def test_missing_member_propagates_valueerror(self, tmp_path, monkeypatch):
        meshes = tmp_path / "meshes"
        npz = _freeze_group(meshes, self.GROUP)
        _drop_npz_member(npz)
        monkeypatch.setenv("AGM_MESHES_DIR", str(meshes))

        import case_stages

        with pytest.raises(ValueError):
            case_stages.flow_refinement_stage(self.GROUP)

    def test_sanity_check_rejects_spec_missing_expected_keys(self, tmp_path, monkeypatch):
        # Criterion 1: the stage sanity-checks the decoded spec's keys. With a
        # valid, hash-verifying artifact present but load_flow_spec returning a
        # spec that is MISSING the expected keys, the stage must raise (i.e. the
        # sanity check is real, not a rubber stamp). Patched on both possible
        # import styles so the test is agnostic to how case_stages references it.
        meshes = tmp_path / "meshes"
        _freeze_group(meshes, self.GROUP)
        monkeypatch.setenv("AGM_MESHES_DIR", str(meshes))

        import case_stages

        def _incomplete(*a, **k):
            return {}  # decoded spec missing every expected key

        monkeypatch.setattr(mio, "load_flow_spec", _incomplete, raising=False)
        monkeypatch.setattr(case_stages, "load_flow_spec", _incomplete, raising=False)

        with pytest.raises(Exception):
            case_stages.flow_refinement_stage(self.GROUP)


# =============================================================================
# CLI wiring (Criterion 4): the harness registers flow_refinement and runs it
# end-to-end MODFLOW-free through its subprocess machinery.
# =============================================================================

def _run_cli(args, env_extra=None):
    import os

    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), *args],
        capture_output=True, text=True, timeout=120, env=env,
    )


def _stage_entry(report, group, stage_id):
    for g in report["groups"]:
        if g["group"] == group:
            for s in g["stages"]:
                if s["id"] == stage_id:
                    return s
    raise AssertionError(f"{stage_id} entry for group {group} not found in report")


class TestCliWiring:
    def test_cli_flow_refinement_passes_on_valid_pinned_artifact(self, tmp_path):
        # End-to-end: CLI registers flow_refinement, dispatches it into a fresh
        # subprocess that re-imports case_stages, loads+verifies the SYNTHETIC
        # group0 artifact from AGM_MESHES_DIR, and reports PASS. No MODFLOW.
        meshes = tmp_path / "meshes"
        _freeze_group(meshes, 0)
        result = _run_cli(
            ["--groups", "0", "--stage", "flow_refinement"],
            env_extra={"AGM_MESHES_DIR": str(meshes)},
        )
        assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        report = json.loads(result.stdout)
        entry = _stage_entry(report, 0, "flow_refinement")
        assert entry["status"] == "PASS", entry

    def test_cli_flow_refinement_is_registered_not_unimplemented(self, tmp_path):
        # With no artifact present the stage FAILS (subprocess raises) -- but
        # crucially it is NOT reported NOT_IMPLEMENTED, proving the CLI called
        # register_flow_stages() before validating.
        empty = tmp_path / "meshes"
        empty.mkdir()
        result = _run_cli(
            ["--groups", "0", "--stage", "flow_refinement"],
            env_extra={"AGM_MESHES_DIR": str(empty)},
        )
        report = json.loads(result.stdout)
        entry = _stage_entry(report, 0, "flow_refinement")
        assert entry["status"] != "NOT_IMPLEMENTED", entry
        assert entry["status"] == "FAIL", entry


# =============================================================================
# Criterion 4: existing M1 harness guarantees must still hold after wiring.
# =============================================================================

class TestM1GuaranteesStillHold:
    def test_plan_only_lists_all_ten_stages_and_exits_zero(self):
        result = _run_cli(["--groups", "0-8", "--plan-only"])
        assert result.returncode == 0, f"stderr:\n{result.stderr}"
        report = json.loads(result.stdout)
        assert len(report["groups"]) == 9
        for g in report["groups"]:
            assert [s["id"] for s in g["stages"]] == list(cv.REQUIRED_STAGES)

    def test_require_green_still_nonzero_on_skeleton(self, tmp_path):
        # flow_refinement now PASSES (valid artifacts for all 9 groups), but the
        # other 9 stages are still unimplemented -> the release gate must NOT be
        # green. Guards against wiring flow_refinement accidentally flipping the
        # skeleton green.
        meshes = tmp_path / "meshes"
        for g in range(9):
            _freeze_group(meshes, g)
        result = _run_cli(
            ["--groups", "0-8", "--require-green"],
            env_extra={"AGM_MESHES_DIR": str(meshes)},
        )
        assert result.returncode != 0
