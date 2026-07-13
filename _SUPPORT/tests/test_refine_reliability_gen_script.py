"""
LOCKED acceptance tests for milestone M2b-gen-script.

This milestone builds the INSTRUCTOR generation / freeze / determinism-check
orchestration that runs on the JupyterHub-Linux (M2b-run) to produce the
per-group PINNED flow artifacts. It composes already-shipped pieces
(``model_io_utils.refine_with_retry`` / ``freeze_flow_spec`` /
``validate_flow_spec`` / ``load_flow_spec`` / ``assemble_gwf_from_spec``).

Public API under test (all in the NEW CLI module
``_SUPPORT/src/scripts/jupyterhub_refine_reliability_gen.py``, which MUST be
importable with NO import-time side effects -- the model-loading/sweep body
must live under a ``main()`` / ``if __name__ == '__main__'`` guard).

NOTE: this is a DISTINCT file from the already-shipped
``jupyterhub_refine_reliability_check.py`` (commit a28ed4e), which is an
unrelated real-MF6 SIGILL sweep with module-level side effects. Do NOT
overwrite that script -- the generation/freeze/determinism orchestration
below lives at its own path so the legacy diagnostic survives:

  * ``run_group_determinism_check(group, runner, *, reruns=5) -> dict``
        PURE orchestration. Calls ``runner(group)`` ``reruns`` times; each call
        returns ``(spec_dict, radius_used, retried_bool)``. Reports PASS only if
        every rerun agrees EXACTLY on ncpl, active-cell count, and every cellid
        array (chd/riv/wel cellid + well_cells), the radius is identical, and
        retried is False on every run. Else FAIL naming the first divergence.
        Contains NO MODFLOW and NO subprocess.

  * ``subprocess_refine_runner(group, *, mother_model, work_dir) -> tuple``
        REAL runner. Runs the refinement in a FRESH SUBPROCESS and returns
        ``(spec, radius_used, retried)`` via a freeze->load IPC hop. Honours two
        test hooks in the child (so the IPC path is exercisable WITHOUT
        MODFLOW):
          - ``AGM_FAKE_SPEC_NPZ``  : child returns this pre-frozen synthetic
            spec instead of running MODFLOW.
          - ``AGM_FAKE_CHILD_SIGNAL`` : child kills itself with this signal
            number (simulates an uncatchable SIGILL).
        A child that dies by signal or nonzero exit is surfaced as a FAILED run
        by RAISING a normal Python exception -- the parent process never dies.

  * ``freeze_group_flow_artifact(spec, *, group, meshes_dir, radius_used, ...)``
        On a determinism PASS, freezes the canonical spec via
        ``freeze_flow_spec`` (which calls ``validate_flow_spec``) to
        ``<meshes_dir>/group<N>_flow.npz`` + manifest, recording
        ``platform.node()``, best-effort tool versions, and ``radius_used``.

  * ``assert_flow_specs_equal(spec_a, spec_b) -> None``
        Equivalence helper: raises unless every spec array is exactly equal
        (np.array_equal on flat arrays; identical gridprops vertices/cell2d).

  * ``main(argv=None) -> int``
        CLI: ``--groups`` (0-8 ranges/lists), ``--reruns``, ``--meshes-dir``,
        ``--freeze``, ``--out``, ``--require-green-style``. Emits a
        machine-readable JSON report per group and exits nonzero under
        ``--require-green-style`` if any selected group failed determinism.

LOCKED-TEST SCOPING (do not weaken): no test here runs MODFLOW or real
Triangle/Voronoi refinement. ``run_group_determinism_check`` is driven with
fake runners; ``subprocess_refine_runner`` / the CLI are driven via
``AGM_FAKE_SPEC_NPZ`` (a synthetic frozen spec) and via a fake child that exits
by signal / nonzero. The heavy 'assemble + real MF6 heads/budget equal to a
direct build_refined_gwf_model' equivalence is HUB-ONLY (guarded, skipped
locally).

Run with:  uv run pytest _SUPPORT/tests/test_refine_reliability_gen_script.py -v
"""

from __future__ import annotations

import copy
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# --- import paths -----------------------------------------------------------
SRC_DIR = Path(__file__).parent.parent / "src"
SCRIPTS_DIR = SRC_DIR / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import model_io_utils as mio  # noqa: E402

# The module under test. It does not exist yet, so this import raises at
# collection and every test below errors -- the correct fast "fails now" state.
# Once implemented it MUST NOT run the model-loading sweep on import (that body
# must be guarded under main()). It is a DISTINCT file from the legacy
# jupyterhub_refine_reliability_check.py diagnostic (which must not be clobbered).
import jupyterhub_refine_reliability_gen as rc  # noqa: E402


# =============================================================================
# Synthetic tiny *ragged* DISV spec (triangle + two quads). No Triangle/Voronoi
# is used; the mesh is hand-built and SIGILL-free. Same schema the shipped
# freeze/load codec round-trips.
# =============================================================================
_VERTICES = [
    [0, 0.0, 0.0], [1, 10.0, 0.0], [2, 20.0, 0.0],
    [3, 0.0, 10.0], [4, 10.0, 10.0], [5, 20.0, 10.0],
]
_CELL2D = [
    [0, 3.0, 6.0, 3, 3, 0, 4],       # triangle (nv=3)
    [1, 5.0, 5.0, 4, 0, 1, 4, 3],    # quad     (nv=4)
    [2, 15.0, 5.0, 4, 1, 2, 5, 4],   # quad     (nv=4)
]
_NCPL = 3
_NVERT = 6


def _gridprops():
    return {
        "nvert": _NVERT,
        "vertices": [list(v) for v in _VERTICES],
        "cell2d": [list(c) for c in _CELL2D],
        "ncpl": _NCPL,
    }


def make_spec(**overrides):
    """A fully valid synthetic flow spec; override any field for divergence tests."""
    spec = {
        "gridprops": _gridprops(),
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
        "refine_radius_used": 70.0,
        "crs": "EPSG:2056",
    }
    spec.update(overrides)
    return spec


def freeze_synthetic_spec(dest_dir: Path, name: str = "fake_spec.npz", **overrides) -> Path:
    """Freeze a synthetic spec to dest_dir/name and return the .npz path."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    npz = dest_dir / name
    mio.freeze_flow_spec(make_spec(**overrides), npz)
    return npz


# ---------------------------------------------------------------------------
# Fake runners for the PURE determinism check (no subprocess, no MODFLOW).
# ---------------------------------------------------------------------------
class SeqRunner:
    """Return a preset sequence of (spec, radius, retried) tuples; count calls."""

    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = []

    def __call__(self, group):
        self.calls.append(group)
        return self.sequence[len(self.calls) - 1]


def const_runner(spec=None, radius=70.0, retried=False):
    spec = make_spec() if spec is None else spec

    def _runner(group):
        return (copy.deepcopy(spec), radius, retried)

    return _runner


def status_of(result):
    assert isinstance(result, dict), f"result must be a dict, got {type(result)!r}"
    assert "status" in result, f"result must carry a 'status' field; got keys {sorted(result)!r}"
    st = result["status"]
    assert st in ("PASS", "FAIL"), f"result['status'] must be 'PASS'/'FAIL', got {st!r}"
    return st


# =============================================================================
# Criterion 1 -- run_group_determinism_check: pure orchestration logic.
# =============================================================================
def test_determinism_pass_on_identical_runs():
    runner = const_runner(radius=70.0, retried=False)
    result = rc.run_group_determinism_check(3, runner, reruns=5)
    assert status_of(result) == "PASS"
    assert not result.get("reason"), "PASS must have no divergence reason"
    assert float(result["radius_used"]) == 70.0
    assert int(result["group"]) == 3


def test_determinism_calls_runner_exactly_reruns_times_with_group():
    runner = SeqRunner([(make_spec(), 70.0, False) for _ in range(4)])
    rc.run_group_determinism_check(7, runner, reruns=4)
    assert len(runner.calls) == 4, "runner must be called exactly `reruns` times"
    assert all(g == 7 for g in runner.calls), "runner must be called with the group id"


def test_determinism_default_reruns_is_five():
    runner = SeqRunner([(make_spec(), 70.0, False) for _ in range(5)])
    rc.run_group_determinism_check(0, runner)  # no reruns kwarg -> default 5
    assert len(runner.calls) == 5


def test_determinism_is_pure_no_subprocess(monkeypatch):
    """The pure check must never spawn a subprocess -- trip-wire subprocess."""
    def boom(*a, **k):
        raise AssertionError("run_group_determinism_check must not use subprocess")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    result = rc.run_group_determinism_check(1, const_runner(), reruns=3)
    assert status_of(result) == "PASS"


def test_determinism_fail_on_retry_fallback():
    # Any retried=True on any run means a first-radius fallback -> not freezable.
    runner = SeqRunner([
        (make_spec(), 70.0, False),
        (make_spec(), 70.0, True),   # fallback fired here
        (make_spec(), 70.0, False),
    ])
    result = rc.run_group_determinism_check(2, runner, reruns=3)
    assert status_of(result) == "FAIL"
    reason = (result.get("reason") or "").lower()
    assert reason, "FAIL must name a reason"
    assert ("retr" in reason) or ("fallback" in reason), f"reason should name the fallback: {reason!r}"


def test_determinism_fail_on_differing_radius():
    runner = SeqRunner([
        (make_spec(), 70.0, False),
        (make_spec(), 62.0, False),  # radius walked
    ])
    result = rc.run_group_determinism_check(4, runner, reruns=2)
    assert status_of(result) == "FAIL"
    assert "radius" in (result.get("reason") or "").lower()


def test_determinism_fail_on_differing_ncpl():
    other = make_spec()
    other["ncpl"] = _NCPL + 1
    other["gridprops"] = dict(other["gridprops"], ncpl=_NCPL + 1)
    runner = SeqRunner([(make_spec(), 70.0, False), (other, 70.0, False)])
    result = rc.run_group_determinism_check(5, runner, reruns=2)
    assert status_of(result) == "FAIL"
    assert "ncpl" in (result.get("reason") or "").lower()


def test_determinism_fail_on_differing_cellids_same_ncpl():
    # Same ncpl, but a CHD cellid moved -> nondeterministic BC reassignment.
    other = make_spec(chd_cellid=[(0, 1), (0, 2)])
    runner = SeqRunner([(make_spec(), 70.0, False), (other, 70.0, False)])
    result = rc.run_group_determinism_check(6, runner, reruns=2)
    assert status_of(result) == "FAIL"
    assert "cellid" in (result.get("reason") or "").lower()


def test_determinism_fail_on_differing_well_cells():
    other = make_spec(well_cells=[2])
    runner = SeqRunner([(make_spec(), 70.0, False), (other, 70.0, False)])
    result = rc.run_group_determinism_check(8, runner, reruns=2)
    assert status_of(result) == "FAIL"
    assert result.get("reason"), "FAIL must name a reason"


def test_determinism_fail_on_differing_active_cell_count():
    # Same ncpl but a different active-cell count (idomain sum differs).
    other = make_spec(idomain=np.array([1, 1, 0], dtype=int))
    runner = SeqRunner([(make_spec(), 70.0, False), (other, 70.0, False)])
    result = rc.run_group_determinism_check(0, runner, reruns=2)
    assert status_of(result) == "FAIL"
    reason = (result.get("reason") or "").lower()
    assert reason, "FAIL must name a reason"
    assert any(tok in reason for tok in ("active", "idomain", "cell"))


# =============================================================================
# Criterion 2 -- subprocess_refine_runner: fresh subprocess + IPC, crash-safe.
# =============================================================================
def test_subprocess_runner_returns_spec_via_fake_npz_ipc(tmp_path, monkeypatch):
    """AGM_FAKE_SPEC_NPZ exercises the freeze->subprocess->load IPC path with no MODFLOW."""
    npz = freeze_synthetic_spec(tmp_path / "fake", "fake_spec.npz", refine_radius_used=70.0)
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))

    out = rc.subprocess_refine_runner(
        3, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work"
    )
    assert isinstance(out, tuple) and len(out) == 3, "runner must return (spec, radius, retried)"
    spec, radius_used, retried = out

    assert int(spec["ncpl"]) == _NCPL
    assert [tuple(int(x) for x in c) for c in spec["chd_cellid"]] == [(0, 0), (0, 2)]
    assert float(radius_used) == 70.0
    # `retried` is now DERIVED from refine_radius_used (== RETRY_RADII[0]
    # here), not read back from a manifest 'retried' field -- the child no
    # longer writes one at all.
    assert bool(retried) is False, "fake (no real refinement) path did not retry"


def test_subprocess_runner_derives_retried_true_from_fallback_radius(tmp_path, monkeypatch):
    """`retried` is DERIVED from `refine_radius_used`, not plumbed through a
    manifest field: a frozen spec whose radius is a LATER entry in
    `RETRY_RADII` (i.e. the run fell back past the first radius) must come
    back as retried=True purely from that radius -- even though the child no
    longer writes, and the parent no longer reads, any manifest 'retried'
    key at all."""
    fallback_radius = rc.RETRY_RADII[1]
    assert fallback_radius != rc.RETRY_RADII[0]
    npz = freeze_synthetic_spec(
        tmp_path / "fake", "fake_spec.npz", refine_radius_used=fallback_radius
    )
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))

    spec, radius_used, retried = rc.subprocess_refine_runner(
        9, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work"
    )
    assert float(radius_used) == fallback_radius
    assert retried is True, "a non-first RETRY_RADII radius must derive retried=True"


def test_subprocess_runner_derives_retried_false_at_first_radius(tmp_path, monkeypatch):
    """Positive mirror of the fallback test above: a spec frozen at exactly
    `RETRY_RADII[0]` must derive retried=False."""
    npz = freeze_synthetic_spec(
        tmp_path / "fake", "fake_spec.npz", refine_radius_used=rc.RETRY_RADII[0]
    )
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))

    spec, radius_used, retried = rc.subprocess_refine_runner(
        9, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work"
    )
    assert float(radius_used) == rc.RETRY_RADII[0]
    assert retried is False


def test_determinism_check_fails_on_derived_retried_via_real_runner(tmp_path, monkeypatch):
    """End-to-end through the REAL `subprocess_refine_runner` (driven by the
    AGM_FAKE_SPEC_NPZ hook, so still MODFLOW-free): a frozen spec whose
    `refine_radius_used` is a fallback radius must make
    `run_group_determinism_check` FAIL on the zero-fallback rule -- proving
    `retried` is correctly derived AND enforced end-to-end, with no manifest
    'retried' field involved anywhere in the chain."""
    fallback_radius = rc.RETRY_RADII[2]
    npz = freeze_synthetic_spec(
        tmp_path / "fake", "fake_spec.npz", refine_radius_used=fallback_radius
    )
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))

    def runner(group):
        return rc.subprocess_refine_runner(
            group, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work"
        )

    result = rc.run_group_determinism_check(9, runner, reruns=2)
    assert status_of(result) == "FAIL"
    reason = (result.get("reason") or "").lower()
    assert ("retr" in reason) or ("fallback" in reason), f"reason should name the fallback: {reason!r}"


def test_determinism_check_passes_on_derived_retried_false_via_real_runner(tmp_path, monkeypatch):
    """Positive mirror of the fallback-FAIL test above: a spec frozen at
    `RETRY_RADII[0]` derives retried=False and, being identical across
    reruns (the fake hook always returns the same frozen spec), PASSes."""
    npz = freeze_synthetic_spec(
        tmp_path / "fake", "fake_spec.npz", refine_radius_used=rc.RETRY_RADII[0]
    )
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))

    def runner(group):
        return rc.subprocess_refine_runner(
            group, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work"
        )

    result = rc.run_group_determinism_check(9, runner, reruns=2)
    assert status_of(result) == "PASS"


def test_subprocess_runner_actually_spawns_a_fresh_child(tmp_path, monkeypatch):
    """Trip-wire the crash-isolation contract: the runner MUST fork/exec a real
    child (so a SIGILL kills only the child). An in-process implementation that
    just reads AGM_FAKE_SPEC_NPZ itself -- providing no isolation -- would pass
    the black-box test above but is caught here because no subprocess is spawned.
    Mirror of test_determinism_is_pure_no_subprocess (which forbids the spawn)."""
    npz = freeze_synthetic_spec(tmp_path / "fake", "fake_spec.npz", refine_radius_used=70.0)
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))

    calls = []
    real_run = subprocess.run
    real_popen = subprocess.Popen

    def spy_run(*a, **k):
        calls.append(("run", a, k))
        return real_run(*a, **k)

    class SpyPopen(real_popen):
        def __init__(self, *a, **k):
            calls.append(("Popen", a, k))
            super().__init__(*a, **k)

    monkeypatch.setattr(subprocess, "run", spy_run)
    monkeypatch.setattr(subprocess, "Popen", SpyPopen)

    spec, radius_used, retried = rc.subprocess_refine_runner(
        3, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work"
    )

    # A real child process was launched (not an in-process fake path).
    assert calls, "subprocess_refine_runner must spawn a FRESH child process"
    # The child honoured AGM_FAKE_SPEC_NPZ over the freeze->load IPC hop.
    assert int(spec["ncpl"]) == _NCPL
    assert float(radius_used) == 70.0
    # The fake npz env var reached the child: either forwarded explicitly via
    # env=, or inherited from the parent environment we set above.
    passed_envs = [k.get("env") for _, _a, k in calls]
    assert (
        any(e is not None and "AGM_FAKE_SPEC_NPZ" in e for e in passed_envs)
        or "AGM_FAKE_SPEC_NPZ" in os.environ
    ), "the fake-spec env var must be visible to the spawned child"


def test_subprocess_runner_surfaces_nonzero_exit_as_failure(tmp_path, monkeypatch):
    """A child that cannot produce a spec (missing npz) exits nonzero -> parent
    RAISES a normal exception naming the exit code, and never itself crashes."""
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(tmp_path / "does_not_exist.npz"))
    # Narrow to the failure contract; AttributeError (unimplemented) / NameError
    # (stray bug) must NOT satisfy this -- otherwise the error path is untested.
    with pytest.raises((RuntimeError, subprocess.SubprocessError)) as excinfo:
        rc.subprocess_refine_runner(
            1, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work"
        )
    msg = str(excinfo.value)
    low = msg.lower()
    assert re.search(r"\d", msg) and any(
        w in low for w in ("exit", "return", "code", "status", "nonzero")
    ), f"the surfaced failure must name the nonzero exit code: {msg!r}"


def test_subprocess_runner_surfaces_signal_death_as_failure(tmp_path, monkeypatch):
    """A child killed by SIGNAL (uncatchable SIGILL analogue) -> parent RAISES a
    normal exception naming the signal, and never itself crashes."""
    npz = freeze_synthetic_spec(tmp_path / "fake", "fake_spec.npz")
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))
    signum = int(signal.SIGILL)
    monkeypatch.setenv("AGM_FAKE_CHILD_SIGNAL", str(signum))
    with pytest.raises((RuntimeError, subprocess.SubprocessError)) as excinfo:
        rc.subprocess_refine_runner(
            2, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work"
        )
    msg = str(excinfo.value)
    low = msg.lower()
    assert ("sigill" in low) or ("signal" in low and str(signum) in msg), (
        f"the surfaced failure must name the killing signal: {msg!r}"
    )


# =============================================================================
# Criterion 3 -- freeze on PASS to group<N>_flow.npz + manifest (node/versions/radius).
# =============================================================================
def _flatten_json(obj):
    """Yield every scalar value in a nested JSON-ish structure."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _flatten_json(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _flatten_json(v)
    else:
        yield obj


def _strict_json_loads(text: str):
    """``json.loads`` that REJECTS the non-standard NaN/Infinity constants
    Python's ``json`` module otherwise round-trips silently. Proves a report
    is actually valid (RFC 8259) JSON, not merely Python-parseable."""
    def _reject(const):
        raise ValueError(f"strict JSON forbids the bare constant {const!r}")

    return json.loads(text, parse_constant=_reject)


def test_freeze_group_artifact_writes_npz_manifest_and_metadata(tmp_path):
    import platform

    meshes = tmp_path / "meshes"
    spec = make_spec(refine_radius_used=62.0)
    manifest = rc.freeze_group_flow_artifact(spec, group=3, meshes_dir=meshes, radius_used=62.0)

    npz = meshes / "group3_flow.npz"
    man = meshes / "group3_flow.manifest.json"
    assert npz.exists(), "canonical spec must be frozen to <meshes>/group<N>_flow.npz"
    assert man.exists(), "a sibling manifest must be written"

    # Re-loadable via the shipped loader (verifies the manifest hash-matches).
    reloaded = mio.load_flow_spec(npz)
    assert int(reloaded["ncpl"]) == _NCPL

    written = json.loads(man.read_text())
    scalars = list(_flatten_json(written))
    node = platform.node()
    if node:
        assert node in scalars, "manifest must record platform.node()"
    assert any(isinstance(v, (int, float)) and float(v) == 62.0 for v in scalars), (
        "manifest must record radius_used"
    )
    text = json.dumps(written)
    assert "flopy" in text and "numpy" in text, "manifest must record tool versions (best-effort)"


def test_freeze_group_artifact_rejects_invalid_spec_and_writes_nothing(tmp_path):
    meshes = tmp_path / "meshes"
    bad = make_spec(chd_head=[8.0])  # len(chd_head)=1 != len(chd_cellid)=2 -> validate_flow_spec fails
    with pytest.raises((ValueError, KeyError)):
        rc.freeze_group_flow_artifact(bad, group=4, meshes_dir=meshes, radius_used=70.0)
    assert not (meshes / "group4_flow.npz").exists(), "no artifact may be frozen for an invalid spec"


# =============================================================================
# Criterion 4 -- equivalence helper (freeze->load reproduces every array exactly).
# =============================================================================
def test_equivalence_helper_accepts_exact_roundtrip(tmp_path):
    spec = make_spec()
    npz = tmp_path / "rt" / "group0_flow.npz"
    mio.freeze_flow_spec(spec, npz)
    reloaded = mio.load_flow_spec(npz)
    # No raise == every flat array + ragged gridprops reproduced exactly.
    assert rc.assert_flow_specs_equal(spec, reloaded) in (None, True)


def test_equivalence_helper_rejects_flat_array_difference():
    a = make_spec()
    b = make_spec()
    b["k"] = np.array([7.5, 3.25, 999.0])  # one property cell changed
    with pytest.raises((AssertionError, ValueError)) as excinfo:
        rc.assert_flow_specs_equal(a, b)
    assert str(excinfo.value)


def test_equivalence_helper_rejects_gridprops_difference():
    a = make_spec()
    b = make_spec()
    perturbed = [list(row) for row in _CELL2D]
    perturbed[2][1] = 15.5  # move a cell centre -> gridprops mismatch
    b["gridprops"] = dict(b["gridprops"], cell2d=perturbed)
    with pytest.raises((AssertionError, ValueError)):
        rc.assert_flow_specs_equal(a, b)


@pytest.mark.skipif(
    os.environ.get("AGM_HUB_CHECKS") != "1",
    reason="HUB-ONLY: real MF6 assemble-vs-build equivalence (runs MODFLOW; not in the local suite)",
)
def test_hub_only_mf6_assemble_equals_direct_build():
    """Heavier equivalence: assembling a frozen spec yields MF6 heads/budget equal
    to a direct build_refined_gwf_model. Guarded so the local (macOS) suite never
    runs MODFLOW; only exercised on the JupyterHub via AGM_HUB_CHECKS=1."""
    meshes = os.environ["AGM_HUB_MESHES_DIR"]
    group = int(os.environ.get("AGM_HUB_GROUP", "3"))
    import tempfile

    with tempfile.TemporaryDirectory() as ws:
        result = mio.load_pinned_flow_model(group, meshes_dir=meshes, workspace=ws)
    heads = np.asarray(result["heads"])
    assert heads.size == int(result["ncpl"])
    assert np.all(np.isfinite(heads))


# =============================================================================
# Criterion 5 -- CLI: flags, per-group JSON report, require-green exit code.
# =============================================================================
def _run_cli(argv):
    rv = rc.main(argv)
    assert isinstance(rv, int), "main() must return an int exit code"
    return rv


def test_cli_pass_group_freezes_and_reports(tmp_path, monkeypatch):
    npz = freeze_synthetic_spec(tmp_path / "fake", "fake_spec.npz", refine_radius_used=70.0)
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))
    meshes = tmp_path / "meshes"
    report = tmp_path / "report.json"

    rv = _run_cli([
        "--groups", "3", "--reruns", "2",
        "--meshes-dir", str(meshes), "--freeze",
        "--out", str(report), "--require-green-style",
    ])
    assert rv == 0, "a green group under --require-green-style must exit 0"

    # Frozen artifact for the passing group.
    assert (meshes / "group3_flow.npz").exists()
    assert (meshes / "group3_flow.manifest.json").exists()

    # Machine-readable JSON report with determinism status + freeze + node + radius.
    data = json.loads(report.read_text())
    scalars = [v for v in _flatten_json(data) if isinstance(v, str)]
    assert any("PASS" == v or "PASS" in v for v in scalars), "report must record determinism PASS"
    numbers = [float(v) for v in _flatten_json(data) if isinstance(v, (int, float))]
    assert 70.0 in numbers, "report must record the radius used"
    import platform
    if platform.node():
        assert platform.node() in scalars, "report must record the node"


def test_cli_pass_group_without_freeze_flag_writes_no_artifact(tmp_path, monkeypatch):
    """Positive gating of --freeze: a determinism-PASS group run WITHOUT the
    --freeze flag must NOT write group<N>_flow.npz / manifest. Criterion 3
    conditions freezing on 'when freezing is requested'; an implementation that
    always freezes on PASS (or ignores the flag) must fail here. Mirror of
    test_cli_pass_group_freezes_and_reports (same PASS group, freeze omitted)."""
    npz = freeze_synthetic_spec(tmp_path / "fake", "fake_spec.npz", refine_radius_used=70.0)
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))
    meshes = tmp_path / "meshes"
    report = tmp_path / "report.json"

    rv = _run_cli([
        "--groups", "3", "--reruns", "2",
        "--meshes-dir", str(meshes),  # NOTE: no --freeze
        "--out", str(report),
    ])
    assert rv == 0

    # The group PASSED determinism (same fake-spec PASS path as the freeze test),
    # yet with --freeze omitted NO canonical artifact may be written.
    scalars = [v for v in _flatten_json(json.loads(report.read_text())) if isinstance(v, str)]
    assert any("PASS" == v or "PASS" in v for v in scalars), (
        "sanity: the group must have PASSED determinism (else this asserts nothing)"
    )
    assert not (meshes / "group3_flow.npz").exists(), (
        "no artifact may be frozen when --freeze is omitted, even on a determinism PASS"
    )
    assert not (meshes / "group3_flow.manifest.json").exists(), (
        "no manifest may be written when --freeze is omitted, even on a determinism PASS"
    )


def _report_group_ids(obj):
    """Recover the set of group ids the report has an entry for, tolerant of
    either a list of per-group dicts (each with a 'group' field, matching the
    pure check's result schema) or a mapping keyed by group id."""
    ids = set()
    if isinstance(obj, dict):
        if "group" in obj and str(obj["group"]).lstrip("-").isdigit():
            ids.add(int(obj["group"]))
        for k, v in obj.items():
            if isinstance(v, dict) and str(k).lstrip("-").isdigit():
                ids.add(int(k))
            ids |= _report_group_ids(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            ids |= _report_group_ids(v)
    return ids


def test_cli_groups_comma_list_parsing_emits_entry_per_listed_group(tmp_path, monkeypatch):
    """--groups accepts a comma-separated LIST (not only a range). '0,3,5' must
    produce entries for exactly those groups and skip the in-between 1,2,4."""
    npz = freeze_synthetic_spec(tmp_path / "fake", "fake_spec.npz")
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))
    report = tmp_path / "report.json"

    rv = _run_cli([
        "--groups", "0,3,5", "--reruns", "1",
        "--meshes-dir", str(tmp_path / "meshes"),
        "--out", str(report),
    ])
    assert rv == 0
    got = _report_group_ids(json.loads(report.read_text()))
    assert {0, 3, 5} <= got, f"comma-list must yield entries for each listed group; got {sorted(got)}"
    assert not ({1, 2, 4} & got), (
        f"a comma-list must NOT be treated as a range (1,2,4 must be absent); got {sorted(got)}"
    )


def test_cli_groups_range_parsing_emits_entry_per_group(tmp_path, monkeypatch):
    npz = freeze_synthetic_spec(tmp_path / "fake", "fake_spec.npz")
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))
    report = tmp_path / "report.json"

    rv = _run_cli([
        "--groups", "1-2", "--reruns", "1",
        "--meshes-dir", str(tmp_path / "meshes"),
        "--out", str(report),
    ])
    assert rv == 0
    text = report.read_text()
    assert '"1"' in text or " 1" in text or "group1" in text, "range must include group 1"
    assert '"2"' in text or " 2" in text or "group2" in text, "range must include group 2"


def test_cli_failed_group_no_freeze_and_require_green_exits_nonzero(tmp_path, monkeypatch):
    # Missing fake spec -> child exits nonzero -> subprocess_refine_runner
    # RAISES -> this is exactly the "runner raised" exception path in main().
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(tmp_path / "missing.npz"))
    meshes = tmp_path / "meshes"
    report = tmp_path / "report.json"

    rv = _run_cli([
        "--groups", "5", "--reruns", "2",
        "--meshes-dir", str(meshes), "--freeze",
        "--out", str(report), "--require-green-style",
    ])
    assert rv != 0, "--require-green-style must exit nonzero when a group fails determinism"
    assert not (meshes / "group5_flow.npz").exists(), "no artifact may be frozen on a determinism FAIL"
    assert not (meshes / "group5_flow.manifest.json").exists(), (
        "no manifest may be written on a determinism FAIL"
    )

    raw = report.read_text()
    assert "NaN" not in raw, (
        f"a runner exception must never fabricate a NaN radius into the report: {raw!r}"
    )
    data = _strict_json_loads(raw)  # must be STRICT (RFC 8259) valid JSON, no bare NaN
    scalars = [v for v in _flatten_json(data) if isinstance(v, str)]
    assert any("FAIL" == v or "FAIL" in v for v in scalars), "report must record the determinism FAIL"


def test_cli_failed_group_without_require_green_exits_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(tmp_path / "missing.npz"))
    report = tmp_path / "report.json"

    rv = _run_cli([
        "--groups", "5", "--reruns", "2",
        "--meshes-dir", str(tmp_path / "meshes"),
        "--out", str(report),
    ])
    assert rv == 0, "without --require-green-style a failing group is reported but does not fail the run"
    assert report.exists(), "a report must still be written"


def test_cli_groups_oversized_range_exits_2(tmp_path):
    """--groups '0-999999999' must be rejected (a typo/malicious range span,
    not a legitimate wide selection) with a clear error and exit code 2 --
    caught before any subprocess is ever spawned, so no AGM_FAKE_SPEC_NPZ
    hook is needed here."""
    rv = rc.main([
        "--groups", "0-999999999", "--meshes-dir", str(tmp_path / "meshes"),
        "--out", str(tmp_path / "report.json"),
    ])
    assert rv == 2


def test_cli_groups_out_of_domain_single_id_exits_2(tmp_path):
    """--groups '9' is a syntactically valid single id, but this script's
    frozen artifacts only ever cover the canonical 0-8 group domain -- must
    be rejected with exit code 2."""
    rv = rc.main([
        "--groups", "9", "--meshes-dir", str(tmp_path / "meshes"),
        "--out", str(tmp_path / "report.json"),
    ])
    assert rv == 2


def test_cli_groups_full_canonical_range_is_accepted(tmp_path, monkeypatch):
    """'0-8' is exactly the canonical domain and must be accepted (not
    rejected as 'out of domain' or 'oversized')."""
    npz = freeze_synthetic_spec(tmp_path / "fake", "fake_spec.npz")
    monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))

    rv = rc.main([
        "--groups", "0-8", "--reruns", "1",
        "--meshes-dir", str(tmp_path / "meshes"),
        "--out", str(tmp_path / "report.json"),
    ])
    assert rv == 0


class TestParseGroupsCanonicalDomain:
    """Unit-level coverage of `_parse_groups` itself (Fix 3): it now shares
    case_validation.parse_groups_spec's range-span cap and additionally
    restricts to case_validation.CANONICAL_GROUPS (0-8)."""

    def test_rejects_oversized_range(self):
        with pytest.raises(ValueError):
            rc._parse_groups("0-999999999")

    def test_rejects_out_of_domain_single_id(self):
        with pytest.raises(ValueError):
            rc._parse_groups("9")

    def test_rejects_out_of_domain_within_otherwise_valid_list(self):
        with pytest.raises(ValueError):
            rc._parse_groups("0,3,9")

    def test_accepts_full_canonical_range(self):
        assert rc._parse_groups("0-8") == list(range(9))

    def test_accepts_canonical_comma_list(self):
        assert rc._parse_groups("0,3,5") == [0, 3, 5]


# =============================================================================
# Fix 1: refine_points must be DERIVED from the group's doublet, not a random
# interior point -- group_refine_points is a small MODFLOW-free helper.
# =============================================================================
class TestGroupRefinePoints:
    def test_returns_doublet_coords_for_group_0(self):
        import case_utils as cu

        doublet = cu.lint_transport_config(groups=[0])[0]["doublet"]
        expected = [
            (float(doublet["injection_easting"]), float(doublet["injection_northing"])),
            (float(doublet["extraction_easting"]), float(doublet["extraction_northing"])),
        ]
        assert rc.group_refine_points(0) == expected

    def test_returns_doublet_coords_for_group_3(self):
        import case_utils as cu

        doublet = cu.lint_transport_config(groups=[3])[3]["doublet"]
        expected = [
            (float(doublet["injection_easting"]), float(doublet["injection_northing"])),
            (float(doublet["extraction_easting"]), float(doublet["extraction_northing"])),
        ]
        assert rc.group_refine_points(3) == expected

    def test_returns_exactly_two_points(self):
        points = rc.group_refine_points(1)
        assert isinstance(points, list)
        assert len(points) == 2
        for pt in points:
            assert isinstance(pt, tuple) and len(pt) == 2
            assert all(isinstance(v, float) for v in pt)

    def test_is_deterministic_across_calls(self):
        """No randomness: reruns of the SAME group must return identical
        points (required for run_group_determinism_check to ever PASS)."""
        assert rc.group_refine_points(2) == rc.group_refine_points(2)

    def test_is_modflow_free_no_subprocess_spawned(self, monkeypatch):
        """Trip-wire: group_refine_points must be a pure config lookup --
        no MODFLOW, no subprocess. Mirror of
        test_determinism_is_pure_no_subprocess."""
        def boom(*a, **k):
            raise AssertionError("group_refine_points must not spawn a subprocess")

        monkeypatch.setattr(subprocess, "run", boom)
        monkeypatch.setattr(subprocess, "Popen", boom)
        points = rc.group_refine_points(0)
        assert len(points) == 2


# =============================================================================
# Fix 2: subprocess_refine_runner must not hang forever -- a bounded,
# CLI-configurable --child-timeout kills the child's WHOLE process group and
# surfaces the group as a FAILED run.
# =============================================================================
class TestSubprocessChildTimeout:
    def test_hung_child_is_killed_and_surfaced_as_failure_without_hanging(self, tmp_path, monkeypatch):
        """Replace the real child command with one that sleeps far longer
        than a short --child-timeout, so subprocess_refine_runner must kill
        it (process group SIGKILL) rather than block until it exits on its
        own. Asserts: (a) a RuntimeError naming the timeout is raised, (b)
        the call returns well within a small bound (never hangs), and (c)
        the killed child's pid no longer exists afterwards (no leaked
        process)."""
        import time as time_mod

        real_popen = subprocess.Popen
        captured: dict = {}

        class _SleepyPopen(real_popen):
            """Ignore the real refinement child command; spawn a plain
            Python process that sleeps well past the test's timeout, so we
            can prove it gets killed instead of the parent hanging."""

            def __init__(self, _cmd, *a, **k):
                super().__init__(
                    [sys.executable, "-c", "import time; time.sleep(60)"], *a, **k
                )
                captured["pid"] = self.pid

        monkeypatch.setattr(subprocess, "Popen", _SleepyPopen)

        t0 = time_mod.monotonic()
        with pytest.raises(RuntimeError, match="timeout"):
            rc.subprocess_refine_runner(
                0, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work",
                timeout_s=0.5,
            )
        elapsed = time_mod.monotonic() - t0
        assert elapsed < 30.0, (
            f"subprocess_refine_runner must not hang past its timeout: took {elapsed:.1f}s"
        )

        assert "pid" in captured, "the (fake) child process must actually have been spawned"
        pid = captured["pid"]
        deadline = time_mod.monotonic() + 5.0
        while time_mod.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time_mod.sleep(0.1)
        else:
            pytest.fail(f"child pid {pid} still alive after timeout+kill -- process leaked")

    def test_child_timeout_default_is_a_positive_bound(self):
        assert rc.DEFAULT_CHILD_TIMEOUT_S > 0

    def test_cli_exposes_child_timeout_flag(self):
        parser = rc._build_arg_parser()
        args = parser.parse_args([
            "--groups", "0", "--meshes-dir", "/tmp/x", "--out", "/tmp/y.json",
            "--child-timeout", "42",
        ])
        assert args.child_timeout == 42.0


def test_cli_runner_exception_before_any_spec_reports_fail_no_freeze_no_nan(tmp_path, monkeypatch):
    """Directly exercises the `runner raised` branch in `main()` (as opposed
    to the nonzero-child-exit route above): a runner that raises before ANY
    spec/radius was ever obtained must still produce a per-group FAIL, freeze
    NOTHING, and the emitted JSON report must contain no fabricated NaN
    radius and remain strictly valid JSON."""
    meshes = tmp_path / "meshes"
    report = tmp_path / "report.json"

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated runner crash before any spec was produced")

    monkeypatch.setattr(rc, "subprocess_refine_runner", boom)

    rv = _run_cli([
        "--groups", "7", "--reruns", "2",
        "--meshes-dir", str(meshes), "--freeze",
        "--out", str(report),
    ])
    assert rv == 0, "without --require-green-style the run still exits 0"
    assert not (meshes / "group7_flow.npz").exists(), (
        "no artifact may be frozen for a group whose runner raised"
    )
    assert not (meshes / "group7_flow.manifest.json").exists()

    raw = report.read_text()
    assert "NaN" not in raw, f"the JSON report must never contain a NaN literal: {raw!r}"
    data = _strict_json_loads(raw)
    scalars = [v for v in _flatten_json(data) if isinstance(v, str)]
    assert any("FAIL" == v or "FAIL" in v for v in scalars), "report must record the FAIL"
