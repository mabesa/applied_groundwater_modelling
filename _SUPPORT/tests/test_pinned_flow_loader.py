"""
Acceptance tests for milestone M2-pinned-loader.

This milestone adds the PINNED (graded/student) flow loader — the payoff of the
already-shipped ``generate_refined_grid`` / ``assemble_gwf_from_spec`` split. It
composes:

  * ``case_artifact_lock`` (write_artifact_manifest / verify_artifact — shipped),
  * ``assemble_gwf_from_spec`` (shipped in model_io_utils.py),

into three NEW public functions in ``model_io_utils``:

  * ``freeze_flow_spec(spec, npz_path, *, caller_fields=None, manifest_path=None)``
  * ``load_flow_spec(npz_path, manifest_path=None, *, verify=True)``
  * ``load_pinned_flow_model(group, *, meshes_dir=None, workspace,
                             sim_name='refined_model', verify=True)``

so the graded path can rebuild the refined MF6/DISV model from FROZEN numpy
arrays WITHOUT re-running Triangle/Voronoi (disv_grid_utils) or scipy
NearestND interpolation.

LOCKED-TEST SCOPING (see milestone brief): these tests MUST NOT run MODFLOW
(no real ``sim.run_simulation``) and MUST NOT call real Triangle/Voronoi
refinement or NearestND interpolation. Everything runs off a hand-built tiny
*ragged* DISV spec; the MF6 solve inside ``assemble_gwf_from_spec`` is stubbed
so only file writing (never a solve) happens.

Run with:  uv run pytest _SUPPORT/tests/test_pinned_flow_loader.py -v
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

# Add src to path for imports
SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import model_io_utils as mio  # noqa: E402
import case_artifact_lock as cal  # noqa: E402


# =============================================================================
# Synthetic tiny *RAGGED* DISV spec.
#
# Two cell shapes on purpose (one triangle nv=3, two quads nv=4) so the cell2d
# encoding genuinely has to survive a ragged round-trip (CSR-style offsets) —
# a naive rectangular reshape would corrupt it. No Triangle/Voronoi is used:
# the mesh is hand-built and SIGILL-free.
#
#   verts:   3---4---5      (y=10)
#            |   |   |
#            0---1---2      (y=0)
# =============================================================================
_VERTICES = [
    [0, 0.0, 0.0], [1, 10.0, 0.0], [2, 20.0, 0.0],
    [3, 0.0, 10.0], [4, 10.0, 10.0], [5, 20.0, 10.0],
]
_CELL2D = [
    [0, 3.0, 6.0, 3, 3, 0, 4],       # triangle  (nv=3) -> row length 7
    [1, 5.0, 5.0, 4, 0, 1, 4, 3],    # quad       (nv=4) -> row length 8
    [2, 15.0, 5.0, 4, 1, 2, 5, 4],   # quad       (nv=4) -> row length 8
]
_NCPL = 3
_NVERT = 6

FLAT_KEYS = [
    "top", "botm", "k", "rch", "strt", "idomain",
    "chd_cellid", "chd_head",
    "riv_cellid", "riv_stage", "riv_cond", "riv_rbot",
    "wel_cellid", "wel_rate", "well_cells",
]

RESULT_KEYS = ("sim", "gwf", "modelgrid", "gridprops", "ncpl", "heads", "well_cells")


def _gridprops():
    return {
        "nvert": _NVERT,
        "vertices": [list(v) for v in _VERTICES],
        "cell2d": [list(c) for c in _CELL2D],
        "ncpl": _NCPL,
    }


def _synthetic_spec(with_wells=True):
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
        "refine_radius_used": 175.0,
        "crs": "EPSG:2056",
    }
    if with_wells:
        spec["wel_cellid"] = [(0, 1)]
        spec["wel_rate"] = [-30.0]
        spec["well_cells"] = [1]
    else:
        spec["wel_cellid"] = []
        spec["wel_rate"] = []
        spec["well_cells"] = []
    return spec


# =============================================================================
# Solve stub: intercept MODFLOW so assemble writes (no run) and returns heads.
# =============================================================================
def _stub_solve(monkeypatch):
    import flopy

    state = {"ran": False}

    def fake_run(self, *a, **k):
        state["ran"] = True
        return True, []

    class _FakeHead:
        def get_data(self):
            return np.full((1, 1, _NCPL), 8.5)

    class _FakeOutput:
        def head(self, *a, **k):
            return _FakeHead()

    monkeypatch.setattr(flopy.mf6.MFSimulation, "run_simulation", fake_run)
    monkeypatch.setattr(
        flopy.mf6.ModflowGwf, "output",
        property(lambda self: _FakeOutput()), raising=False,
    )
    return state


def _patch_regeneration_to_raise(monkeypatch):
    """Trip-wire every geometry-regeneration entry point.

    If the graded path touches Triangle/Voronoi or NearestND, it explodes —
    proving the pinned loader rebuilds purely from frozen arrays.
    """
    import disv_grid_utils as dgu
    import scipy.interpolate as si

    def boom(*a, **k):
        raise AssertionError(
            "graded/pinned path must NOT regenerate geometry "
            "(Triangle/Voronoi/NearestND called)"
        )

    monkeypatch.setattr(dgu, "create_disv_from_boundary", boom)
    monkeypatch.setattr(dgu, "refine_grid_locally", boom)
    monkeypatch.setattr(si, "NearestNDInterpolator", boom)
    # Belt-and-suspenders if the symbol was imported into mio's namespace.
    monkeypatch.setattr(mio, "NearestNDInterpolator", boom, raising=False)


def _tamper_npz_content(npz_path):
    """Rewrite the .npz so one member's CONTENT changes while member names and
    the (now stale) manifest are left intact -> hash mismatch."""
    with np.load(npz_path, allow_pickle=False) as z:
        members = {name: z[name] for name in z.files}
    key = next(k for k in members if members[k].size > 0)
    perturbed = np.array(members[key])
    perturbed.reshape(-1)[0] = perturbed.reshape(-1)[0] + 1
    members[key] = perturbed
    np.savez(npz_path, **members)


def _drop_npz_member(npz_path):
    """Rewrite the .npz missing one member the manifest still records."""
    with np.load(npz_path, allow_pickle=False) as z:
        names = list(z.files)
        members = {name: z[name] for name in names[:-1]}
    np.savez(npz_path, **members)


# =============================================================================
# Round-trip equivalence helpers
# =============================================================================
def _assert_flat_arrays_equal(loaded, original):
    for k in FLAT_KEYS:
        a = np.asarray(loaded[k])
        b = np.asarray(original[k])
        assert a.shape == b.shape, f"spec['{k}'] shape {a.shape} != {b.shape}"
        assert np.array_equal(a, b), f"spec['{k}'] content changed on round-trip"


def _rows_as_floats(rows):
    return [[float(x) for x in row] for row in rows]


def _assert_gridprops_equivalent(loaded_gp, orig_gp):
    assert int(loaded_gp["nvert"]) == int(orig_gp["nvert"])
    assert int(loaded_gp["ncpl"]) == int(orig_gp["ncpl"])
    # vertices: rectangular (nvert, 3)
    assert _rows_as_floats(loaded_gp["vertices"]) == _rows_as_floats(orig_gp["vertices"])
    # cell2d: RAGGED — row lengths differ (7 for the triangle, 8 for the quads);
    # comparing row-by-row proves the offsets survived, not just the payload.
    lc = _rows_as_floats(loaded_gp["cell2d"])
    oc = _rows_as_floats(orig_gp["cell2d"])
    assert [len(r) for r in lc] == [len(r) for r in oc], "cell2d raggedness lost"
    assert lc == oc, "cell2d contents changed on round-trip"
    # structural sanity: sizes line up with the counts
    assert len(loaded_gp["cell2d"]) == int(loaded_gp["ncpl"])
    assert len(loaded_gp["vertices"]) == int(loaded_gp["nvert"])


def _build_disv_from_gridprops(tmp_path, gp, spec):
    """Rebuild a real (never-run) flopy DISV from the reconstructed gridprops
    to prove it is a consumable, equivalent grid. No MODFLOW solve."""
    import flopy

    sim = flopy.mf6.MFSimulation(sim_name="rt", sim_ws=str(tmp_path / "rt"))
    flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1)])
    flopy.mf6.ModflowIms(sim)
    gwf = flopy.mf6.ModflowGwf(sim, modelname="rt")
    disv = flopy.mf6.ModflowGwfdisv(
        gwf, nlay=1, ncpl=int(gp["ncpl"]), nvert=int(gp["nvert"]),
        top=np.asarray(spec["top"], dtype=float),
        botm=[np.asarray(spec["botm"], dtype=float)],
        vertices=gp["vertices"], cell2d=gp["cell2d"],
        idomain=[np.ones(int(gp["ncpl"]), dtype=int)],
    )
    return disv


# =============================================================================
# API presence
# =============================================================================
class TestPinnedLoaderApiExists:
    @pytest.mark.parametrize("name", ["freeze_flow_spec", "load_flow_spec",
                                      "load_pinned_flow_model"])
    def test_function_exists(self, name):
        assert hasattr(mio, name) and callable(getattr(mio, name)), (
            f"model_io_utils.{name} must exist"
        )


# =============================================================================
# Criterion 1: freeze_flow_spec
# =============================================================================
class TestFreezeFlowSpec:

    def test_writes_npz_and_manifest_creating_parent_dirs(self, tmp_path):
        npz = tmp_path / "nested" / "deep" / "group3_flow.npz"
        mio.freeze_flow_spec(_synthetic_spec(), npz)
        manifest = npz.with_suffix("").with_suffix(".manifest.json")
        assert npz.exists(), "freeze must create the .npz (incl. parent dirs)"
        assert manifest.exists(), "freeze must write the sibling manifest"

    def test_manifest_verifies_against_npz(self, tmp_path):
        # Proves freeze went through case_artifact_lock.write_artifact_manifest:
        # verify_artifact must accept the pair it produced.
        npz = tmp_path / "group3_flow.npz"
        mio.freeze_flow_spec(_synthetic_spec(), npz)
        manifest = npz.with_suffix("").with_suffix(".manifest.json")
        assert cal.verify_artifact(npz, manifest) is True

    def test_npz_members_are_plain_numpy_no_pickle(self, tmp_path):
        # "an .npz of numpy arrays" — ragged gridprops must be encoded to FLAT
        # numeric arrays, NOT stashed as pickled python objects. Loading with
        # the numpy default (allow_pickle=False) must succeed for every member.
        npz = tmp_path / "group3_flow.npz"
        mio.freeze_flow_spec(_synthetic_spec(), npz)
        with np.load(npz, allow_pickle=False) as z:
            assert len(z.files) >= 1
            for name in z.files:
                arr = z[name]  # raises if this member was pickled
                assert isinstance(arr, np.ndarray)
                assert arr.dtype != object, f"member {name!r} is an object array"

    def test_caller_fields_flow_into_manifest(self, tmp_path):
        npz = tmp_path / "group3_flow.npz"
        mio.freeze_flow_spec(
            _synthetic_spec(), npz, caller_fields={"group": 3, "case": "flow"}
        )
        manifest = json.loads(
            npz.with_suffix("").with_suffix(".manifest.json").read_text()
        )
        assert manifest.get("group") == 3
        assert manifest.get("case") == "flow"

    def test_explicit_manifest_path_is_honored(self, tmp_path):
        npz = tmp_path / "group3_flow.npz"
        manifest = tmp_path / "elsewhere" / "custom.manifest.json"
        mio.freeze_flow_spec(_synthetic_spec(), npz, manifest_path=manifest)
        assert manifest.exists()
        assert cal.verify_artifact(npz, manifest) is True


# =============================================================================
# Criterion 2 + 4: load_flow_spec round-trips the spec and rebuilds the DISV.
# =============================================================================
class TestLoadFlowSpecRoundTrip:

    def _freeze(self, tmp_path, spec=None):
        spec = spec if spec is not None else _synthetic_spec()
        npz = tmp_path / "group3_flow.npz"
        mio.freeze_flow_spec(spec, npz)
        return spec, npz

    def test_flat_arrays_round_trip_exactly(self, tmp_path):
        orig, npz = self._freeze(tmp_path)
        loaded = mio.load_flow_spec(npz)
        _assert_flat_arrays_equal(loaded, orig)

    def test_refine_radius_used_round_trips(self, tmp_path):
        orig, npz = self._freeze(tmp_path)
        loaded = mio.load_flow_spec(npz)
        assert float(np.asarray(loaded["refine_radius_used"])) == pytest.approx(
            float(orig["refine_radius_used"])
        )

    def test_gridprops_round_trip_ragged(self, tmp_path):
        orig, npz = self._freeze(tmp_path)
        loaded = mio.load_flow_spec(npz)
        _assert_gridprops_equivalent(loaded["gridprops"], orig["gridprops"])

    def test_reconstructed_gridprops_rebuild_equivalent_disv(self, tmp_path):
        # Criterion 4: reconstructed gridprops must rebuild an equivalent flopy
        # DISV (same nlay/ncpl/nvert + identical vertices/cell2d). No solve.
        orig, npz = self._freeze(tmp_path)
        loaded = mio.load_flow_spec(npz)
        disv = _build_disv_from_gridprops(tmp_path, loaded["gridprops"], loaded)
        assert int(np.asarray(disv.ncpl.get_data())) == _NCPL
        assert int(np.asarray(disv.nvert.get_data())) == _NVERT

    def test_empty_wells_round_trip_present_but_empty(self, tmp_path):
        # Negative/edge path: a well-free spec must round-trip the WEL keys as
        # present-but-empty (not dropped, not defaulted to a bogus record).
        orig, npz = self._freeze(tmp_path, _synthetic_spec(with_wells=False))
        loaded = mio.load_flow_spec(npz)
        for key in ("wel_cellid", "wel_rate", "well_cells"):
            assert key in loaded
            assert len(np.asarray(loaded[key]).reshape(-1)) == 0

    def test_load_does_not_regenerate_geometry(self, tmp_path, monkeypatch):
        # load_flow_spec must reconstruct without Triangle/Voronoi/NearestND.
        orig, npz = self._freeze(tmp_path)
        _patch_regeneration_to_raise(monkeypatch)
        loaded = mio.load_flow_spec(npz)
        _assert_gridprops_equivalent(loaded["gridprops"], orig["gridprops"])

    def test_source_has_no_refinement_or_interpolation(self):
        src = inspect.getsource(mio.load_flow_spec)
        for forbidden in ("disv_grid_utils", "create_disv_from_boundary",
                          "refine_grid_locally", "NearestNDInterpolator"):
            assert forbidden not in src, (
                f"load_flow_spec must not reference {forbidden!r}"
            )


# =============================================================================
# Criterion 2 (error paths): verification is FIRST and gated by verify=.
# =============================================================================
class TestLoadFlowSpecVerification:

    def _freeze(self, tmp_path):
        npz = tmp_path / "group3_flow.npz"
        mio.freeze_flow_spec(_synthetic_spec(), npz)
        return npz

    def test_tampered_content_raises_valueerror(self, tmp_path):
        npz = self._freeze(tmp_path)
        _tamper_npz_content(npz)
        with pytest.raises(ValueError):
            mio.load_flow_spec(npz)  # verify=True default

    def test_missing_member_raises_valueerror(self, tmp_path):
        npz = self._freeze(tmp_path)
        _drop_npz_member(npz)
        with pytest.raises(ValueError):
            mio.load_flow_spec(npz)

    def test_missing_manifest_raises_when_verify_true(self, tmp_path):
        npz = self._freeze(tmp_path)
        npz.with_suffix("").with_suffix(".manifest.json").unlink()
        with pytest.raises(ValueError):
            mio.load_flow_spec(npz, verify=True)

    def test_verify_false_skips_verification(self, tmp_path):
        # verify=False must reconstruct WITHOUT requiring/validating the
        # manifest — proving verification is genuinely gated by the flag and
        # verify=True is not a no-op that always passes.
        orig = _synthetic_spec()
        npz = tmp_path / "group3_flow.npz"
        mio.freeze_flow_spec(orig, npz)
        npz.with_suffix("").with_suffix(".manifest.json").unlink()
        loaded = mio.load_flow_spec(npz, verify=False)
        _assert_flat_arrays_equal(loaded, orig)


# =============================================================================
# Criterion 3 + 5: load_pinned_flow_model
# =============================================================================
class TestLoadPinnedFlowModel:

    GROUP = 3

    def _freeze_group(self, meshes_dir, group=None, spec=None):
        group = self.GROUP if group is None else group
        spec = spec if spec is not None else _synthetic_spec()
        meshes_dir.mkdir(parents=True, exist_ok=True)
        npz = meshes_dir / f"group{group}_flow.npz"
        mio.freeze_flow_spec(spec, npz)
        return npz

    def test_returns_build_refined_result_keys(self, tmp_path, monkeypatch):
        meshes = tmp_path / "meshes"
        self._freeze_group(meshes)
        _stub_solve(monkeypatch)
        result = mio.load_pinned_flow_model(
            self.GROUP, meshes_dir=meshes, workspace=str(tmp_path / "ws"),
        )
        for key in RESULT_KEYS:
            assert key in result, f"load_pinned_flow_model result missing {key!r}"
        assert int(result["ncpl"]) == _NCPL
        assert list(result["well_cells"]) == [1]

    def test_no_regeneration_contract(self, tmp_path, monkeypatch):
        # Criterion 5: with all geometry regeneration trip-wired to RAISE and
        # the solve stubbed, the pinned loader still returns a runnable model —
        # proving the graded path never re-derives geometry.
        meshes = tmp_path / "meshes"
        self._freeze_group(meshes)
        _stub_solve(monkeypatch)
        _patch_regeneration_to_raise(monkeypatch)
        result = mio.load_pinned_flow_model(
            self.GROUP, meshes_dir=meshes, workspace=str(tmp_path / "ws"),
        )
        for key in RESULT_KEYS:
            assert key in result

    def test_resolves_group_artifact_by_name(self, tmp_path, monkeypatch):
        # Only group7's artifact exists; requesting group7 must resolve
        # <meshes_dir>/group7_flow.npz (+ sibling manifest).
        meshes = tmp_path / "meshes"
        self._freeze_group(meshes, group=7)
        _stub_solve(monkeypatch)
        result = mio.load_pinned_flow_model(
            7, meshes_dir=meshes, workspace=str(tmp_path / "ws7"),
        )
        assert int(result["ncpl"]) == _NCPL

    def test_missing_artifact_raises_actionable_error(self, tmp_path, monkeypatch):
        meshes = tmp_path / "meshes"
        meshes.mkdir(parents=True, exist_ok=True)  # exists but empty
        _stub_solve(monkeypatch)
        with pytest.raises((FileNotFoundError, ValueError)) as exc:
            mio.load_pinned_flow_model(
                self.GROUP, meshes_dir=meshes, workspace=str(tmp_path / "ws"),
            )
        msg = str(exc.value).lower()
        assert (f"group{self.GROUP}" in msg or ".npz" in msg
                or "manifest" in msg or "not found" in msg or "missing" in msg), (
            f"error message not actionable: {exc.value!r}"
        )

    def test_hash_mismatch_propagates_valueerror(self, tmp_path, monkeypatch):
        meshes = tmp_path / "meshes"
        npz = self._freeze_group(meshes)
        _tamper_npz_content(npz)
        _stub_solve(monkeypatch)
        with pytest.raises(ValueError):
            mio.load_pinned_flow_model(
                self.GROUP, meshes_dir=meshes, workspace=str(tmp_path / "ws"),
                verify=True,
            )

    def test_sim_name_is_used(self, tmp_path, monkeypatch):
        meshes = tmp_path / "meshes"
        self._freeze_group(meshes)
        _stub_solve(monkeypatch)
        ws = tmp_path / "ws"
        mio.load_pinned_flow_model(
            self.GROUP, meshes_dir=meshes, workspace=str(ws),
            sim_name="my_pinned",
        )
        # assemble writes <sim_name>.nam / <sim_name>.disv into the workspace.
        written = {p.name for p in ws.glob("*")}
        assert "my_pinned.nam" in written and "my_pinned.disv" in written

    def test_source_has_no_refinement_or_interpolation(self):
        src = inspect.getsource(mio.load_pinned_flow_model)
        for forbidden in ("disv_grid_utils", "create_disv_from_boundary",
                          "refine_grid_locally", "NearestNDInterpolator"):
            assert forbidden not in src, (
                f"load_pinned_flow_model must not reference {forbidden!r}"
            )
