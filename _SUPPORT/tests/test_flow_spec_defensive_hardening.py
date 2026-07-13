"""
Regression tests for the M2a defensive-hardening fixes (adversarial Codex
review) applied on top of the already-shipped flow-spec split/pinned-loader
machinery in ``model_io_utils.py``:

  * FIX A -- ``validate_flow_spec(spec, *, require_crs=True)``: a central
    internal-consistency gate (array lengths, finite values, BC cellid
    bounds, crs presence) wired into ``assemble_gwf_from_spec`` (start),
    ``load_flow_spec`` (end), and ``freeze_flow_spec`` (before writing).
  * FIX B -- the ragged DISV ``cell2d`` CSR decoder
    (``_decode_gridprops_from_npz``) now validates row length invariants
    and the running flat-array offset, so a hash-valid-but-corrupt artifact
    fails loudly at decode instead of building a malformed ``cell2d``.
  * FIX C -- ``crs`` is now a REQUIRED, frozen flow-spec field (added to
    ``_FLOW_SPEC_REQUIRED_KEYS``); freeze/load round-trip it.

LOCKED-TEST SCOPING (same convention as the sibling M2 test files): no test
here runs MODFLOW or real Triangle/Voronoi/NearestND refinement -- every
spec is hand-built, and MF6 solves are intercepted (write-only) where a
solve would otherwise be attempted.

Run with:  uv run pytest _SUPPORT/tests/test_flow_spec_defensive_hardening.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import model_io_utils as mio  # noqa: E402
import case_artifact_lock as cal  # noqa: E402


# =============================================================================
# Synthetic tiny *RAGGED* DISV spec (one triangle nv=3, two quads nv=4) --
# same shape convention as test_pinned_flow_loader.py / test_case_flow_stage.py
# so a naive rectangular reshape of cell2d would corrupt it.
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


def _gridprops():
    return {
        "nvert": _NVERT,
        "vertices": [list(v) for v in _VERTICES],
        "cell2d": [list(c) for c in _CELL2D],
        "ncpl": _NCPL,
    }


def _good_spec():
    return {
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
        "refine_radius_used": 175.0,
        "crs": "EPSG:2056",
    }


# =============================================================================
# FIX A: validate_flow_spec
# =============================================================================
class TestValidateFlowSpecApiExists:
    def test_function_exists(self):
        assert hasattr(mio, "validate_flow_spec")
        assert callable(mio.validate_flow_spec)


class TestValidateFlowSpecHappyPath:
    def test_well_formed_spec_passes_and_is_returned(self):
        spec = _good_spec()
        result = mio.validate_flow_spec(spec)
        assert result is spec

    def test_well_formed_spec_with_2d_botm_passes(self):
        # botm shaped (nlay, ncpl) is also valid per the spec.
        spec = _good_spec()
        spec["botm"] = np.zeros((1, _NCPL))
        mio.validate_flow_spec(spec)

    def test_empty_bc_arrays_are_valid(self):
        spec = _good_spec()
        for key in ("chd_cellid", "chd_head", "riv_cellid", "riv_stage",
                    "riv_cond", "riv_rbot", "wel_cellid", "wel_rate", "well_cells"):
            spec[key] = []
        mio.validate_flow_spec(spec)


class TestValidateFlowSpecBcLengthMismatch:
    def test_riv_cond_length_mismatch_raises(self):
        spec = _good_spec()
        spec["riv_cellid"] = [(0, 0), (0, 1)]
        spec["riv_stage"] = [7.5, 7.6]
        # riv_cond deliberately left at length 1 -> parallel-array mismatch.
        with pytest.raises(ValueError, match="riv"):
            mio.validate_flow_spec(spec)

    def test_chd_head_length_mismatch_raises(self):
        spec = _good_spec()
        spec["chd_head"] = [8.0]  # chd_cellid has 2 entries
        with pytest.raises(ValueError, match="chd"):
            mio.validate_flow_spec(spec)

    def test_wel_rate_length_mismatch_raises(self):
        spec = _good_spec()
        spec["wel_rate"] = [-30.0, -10.0]  # wel_cellid has 1 entry
        with pytest.raises(ValueError, match="wel"):
            mio.validate_flow_spec(spec)


class TestValidateFlowSpecNonFinite:
    @pytest.mark.parametrize("key,bad_value", [("k", np.nan), ("top", np.inf)])
    def test_non_finite_value_raises(self, key, bad_value):
        spec = _good_spec()
        arr = np.asarray(spec[key], dtype=float).copy()
        arr[0] = bad_value
        spec[key] = arr
        with pytest.raises(ValueError, match=key):
            mio.validate_flow_spec(spec)

    def test_idomain_is_not_finite_checked(self):
        # idomain is an integer flag array, not a float property -- it must
        # not be swept into the finite-value check.
        spec = _good_spec()
        spec["idomain"] = np.array([1, 1, 1], dtype=int)
        mio.validate_flow_spec(spec)  # no error


class TestValidateFlowSpecCellidBounds:
    def test_icell_out_of_range_raises(self):
        spec = _good_spec()
        spec["riv_cellid"] = [(0, _NCPL)]  # icell == ncpl -> out of range
        with pytest.raises(ValueError, match="riv_cellid"):
            mio.validate_flow_spec(spec)

    def test_negative_layer_raises(self):
        spec = _good_spec()
        spec["chd_cellid"] = [(-1, 0), (0, 2)]
        with pytest.raises(ValueError):
            mio.validate_flow_spec(spec)

    def test_well_cells_out_of_range_raises(self):
        spec = _good_spec()
        spec["well_cells"] = [_NCPL]  # == ncpl -> out of range
        with pytest.raises(ValueError, match="well_cells"):
            mio.validate_flow_spec(spec)

    def test_non_int_icell_raises(self):
        spec = _good_spec()
        spec["wel_cellid"] = [(0, 1.5)]
        with pytest.raises(ValueError):
            mio.validate_flow_spec(spec)


class TestValidateFlowSpecNcplAndGridprops:
    def test_ncpl_not_positive_raises(self):
        spec = _good_spec()
        spec["ncpl"] = 0
        with pytest.raises(ValueError, match="ncpl"):
            mio.validate_flow_spec(spec)

    def test_gridprops_missing_cell2d_raises(self):
        spec = _good_spec()
        del spec["gridprops"]["cell2d"]
        with pytest.raises(ValueError, match="gridprops"):
            mio.validate_flow_spec(spec)

    def test_wrong_length_array_raises(self):
        spec = _good_spec()
        spec["k"] = np.array([1.0, 2.0])  # length 2 != ncpl (3)
        with pytest.raises(ValueError, match="k"):
            mio.validate_flow_spec(spec)


class TestValidateFlowSpecCrs:
    def test_missing_crs_raises_when_required(self):
        spec = _good_spec()
        del spec["crs"]
        with pytest.raises(ValueError, match="crs"):
            mio.validate_flow_spec(spec, require_crs=True)

    def test_missing_crs_allowed_when_not_required(self):
        spec = _good_spec()
        del spec["crs"]
        mio.validate_flow_spec(spec, require_crs=False)

    def test_none_crs_raises_when_required(self):
        spec = _good_spec()
        spec["crs"] = None
        with pytest.raises(ValueError, match="crs"):
            mio.validate_flow_spec(spec, require_crs=True)


# =============================================================================
# FIX A wiring: assemble_gwf_from_spec / freeze_flow_spec call validate FIRST.
# =============================================================================
class TestAssembleGwfFromSpecValidatesFirst:
    def test_invalid_spec_raises_before_any_mf6_write(self, tmp_path, monkeypatch):
        import flopy

        def boom(self, *a, **k):
            raise AssertionError(
                "assemble_gwf_from_spec must validate BEFORE writing MF6 input"
            )

        monkeypatch.setattr(flopy.mf6.MFSimulation, "write_simulation", boom)
        monkeypatch.setattr(flopy.mf6.MFSimulation, "run_simulation", boom)

        spec = _good_spec()
        spec["riv_cond"] = []  # mismatched BC array length -> invalid
        with pytest.raises(ValueError):
            mio.assemble_gwf_from_spec(spec, str(tmp_path / "asm"))


class TestFreezeFlowSpecValidatesFirst:
    def test_invalid_spec_raises_before_npz_written(self, tmp_path):
        spec = _good_spec()
        spec["top"] = np.array([np.nan, 10.0, 10.0])
        npz = tmp_path / "group0_flow.npz"
        with pytest.raises(ValueError):
            mio.freeze_flow_spec(spec, npz)
        assert not npz.exists(), "freeze_flow_spec must not write the npz on validation failure"

    def test_missing_crs_raises_before_npz_written(self, tmp_path):
        spec = _good_spec()
        del spec["crs"]
        npz = tmp_path / "group0_flow.npz"
        with pytest.raises((KeyError, ValueError)):
            mio.freeze_flow_spec(spec, npz)
        assert not npz.exists()


class TestLoadFlowSpecValidatesDecoded:
    def test_hash_valid_but_out_of_range_cellid_raises(self, tmp_path):
        # Freeze a GOOD spec, then hand-corrupt the npz member so a cellid is
        # out of range, and re-sign the manifest so the corrupted content is
        # still hash-VALID -- proving the failure comes from validate_flow_spec
        # at decode time, not from the (now-consistent) hash check.
        spec = _good_spec()
        npz = tmp_path / "group0_flow.npz"
        mio.freeze_flow_spec(spec, npz)
        manifest = npz.with_suffix("").with_suffix(".manifest.json")

        with np.load(npz, allow_pickle=False) as z:
            members = {name: z[name] for name in z.files}
        # riv_cellid is stored as an (n, 2) int array; push icell out of range.
        members["riv_cellid"] = np.array([[0, _NCPL]], dtype=np.int64)
        np.savez(npz, **members)
        cal.write_artifact_manifest(npz, {}, manifest_path=manifest)

        with pytest.raises(ValueError):
            mio.load_flow_spec(npz, manifest, verify=True)


# =============================================================================
# FIX B: ragged cell2d CSR decode validation.
# =============================================================================
class TestCsrDecodeValidation:
    def test_good_ragged_artifact_round_trips(self, tmp_path):
        spec = _good_spec()
        npz = tmp_path / "group0_flow.npz"
        mio.freeze_flow_spec(spec, npz)
        loaded = mio.load_flow_spec(npz)
        assert [len(r) for r in loaded["gridprops"]["cell2d"]] == [7, 8, 8]
        for loaded_row, orig_row in zip(loaded["gridprops"]["cell2d"], _CELL2D):
            assert [float(x) for x in loaded_row] == [float(x) for x in orig_row]

    def _freeze_good(self, tmp_path):
        spec = _good_spec()
        npz = tmp_path / "group0_flow.npz"
        mio.freeze_flow_spec(spec, npz)
        manifest = npz.with_suffix("").with_suffix(".manifest.json")
        return npz, manifest

    def test_tampered_cell2d_lengths_raises_on_load(self, tmp_path):
        # Hash-VALID-but-corrupt artifact: tamper cell2d_lengths (bump the
        # first row's length so it no longer matches its nverts field / the
        # flat payload), then re-sign the manifest so verify_artifact passes
        # and the failure is purely the CSR structural check at decode time.
        npz, manifest = self._freeze_good(tmp_path)

        with np.load(npz, allow_pickle=False) as z:
            members = {name: z[name] for name in z.files}
        lengths = members["gridprops__cell2d_lengths"].copy()
        lengths[0] = lengths[0] + 1  # 7 -> 8, now inconsistent with the payload
        members["gridprops__cell2d_lengths"] = lengths
        np.savez(npz, **members)
        cal.write_artifact_manifest(npz, {}, manifest_path=manifest)

        assert cal.verify_artifact(npz, manifest) is True  # hash-valid ...
        with pytest.raises(ValueError):
            mio.load_flow_spec(npz, manifest, verify=True)  # ... but corrupt

    def test_short_row_below_four_raises(self, tmp_path):
        npz, manifest = self._freeze_good(tmp_path)

        with np.load(npz, allow_pickle=False) as z:
            members = {name: z[name] for name in z.files}
        lengths = members["gridprops__cell2d_lengths"].copy()
        lengths[0] = 3  # < 4, structurally impossible
        members["gridprops__cell2d_lengths"] = lengths
        np.savez(npz, **members)
        cal.write_artifact_manifest(npz, {}, manifest_path=manifest)

        with pytest.raises(ValueError):
            mio.load_flow_spec(npz, manifest, verify=True)


# =============================================================================
# FIX C: crs is a required, frozen field.
# =============================================================================
class TestCrsRequiredField:
    def test_crs_in_required_keys(self):
        assert "crs" in mio._FLOW_SPEC_REQUIRED_KEYS

    def test_freeze_load_round_trips_crs(self, tmp_path):
        spec = _good_spec()
        npz = tmp_path / "group0_flow.npz"
        mio.freeze_flow_spec(spec, npz)
        loaded = mio.load_flow_spec(npz)
        assert loaded["crs"] == "EPSG:2056"

    def test_freeze_missing_crs_raises(self, tmp_path):
        spec = _good_spec()
        del spec["crs"]
        npz = tmp_path / "group0_flow.npz"
        with pytest.raises((KeyError, ValueError)):
            mio.freeze_flow_spec(spec, npz)

    def test_assemble_applies_crs(self, tmp_path, monkeypatch):
        import flopy

        monkeypatch.setattr(
            flopy.mf6.MFSimulation, "run_simulation",
            lambda self, *a, **k: (True, []),
        )

        class _FakeHead:
            def get_data(self):
                return np.full((1, 1, _NCPL), 8.5)

        class _FakeOutput:
            def head(self, *a, **k):
                return _FakeHead()

        monkeypatch.setattr(
            flopy.mf6.ModflowGwf, "output",
            property(lambda self: _FakeOutput()), raising=False,
        )

        spec = _good_spec()
        result = mio.assemble_gwf_from_spec(spec, str(tmp_path / "asm"))
        crs = result["modelgrid"].crs
        assert crs is not None and "2056" in str(crs)
