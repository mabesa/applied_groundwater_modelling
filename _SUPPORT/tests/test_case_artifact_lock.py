"""
Acceptance tests for _SUPPORT/src/case_artifact_lock.py (M2 milestone
"M2-artifact-lock").

The module under test is a flopy-free, per-ARRAY content-hashing lock for the
pinned MF6/DISV model-assembly artifacts stored as .npz bundles. It parallels
`mother_model_lock` (reusing its sorted-(name, hash)-fold idiom) but hashes the
numpy array CONTENTS inside an .npz rather than the .npz file bytes, because
`np.savez` embeds per-member mtimes that would make file-byte hashing
false-mismatch on a re-save of identical arrays.

These tests are LOCKED. They must FAIL against a missing/incorrect module and
pass only against a correct implementation. They cover every acceptance
criterion including negative / error paths.

Run with:  uv run pytest _SUPPORT/tests/test_case_artifact_lock.py -v
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# Add src to path (mirrors the style used by the other tests in this directory)
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

MODULE_PATH = SRC_DIR / "case_artifact_lock.py"

import case_artifact_lock as cal  # noqa: E402
import mother_model_lock as mml  # noqa: E402  (for the shared fold idiom cross-check)


# =============================================================================
# Helpers
# =============================================================================

def _make_arrays() -> dict:
    """A small, mixed-dtype / mixed-shape set of arrays to bundle into an .npz."""
    return {
        "top": np.arange(12, dtype=np.float64).reshape(3, 4),
        "idomain": np.array([[1, 1, 0], [1, 1, 1]], dtype=np.int32),
        "k": np.linspace(1.0, 50.0, 6, dtype=np.float32),
    }


def _save_npz(path: Path, arrays: dict, order=None) -> Path:
    """Save `arrays` to an .npz. `order` optionally re-orders the members
    (which changes the zip byte layout while keeping member names/contents)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(arrays) if order is None else list(order)
    np.savez(path, **{k: arrays[k] for k in keys})
    return path


# =============================================================================
# Criterion 1: flopy/pyemu-free, stdlib + numpy only, no MODFLOW
# =============================================================================

def _imported_roots(source: str) -> set:
    tree = ast.parse(source)
    roots: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


class TestFlopyFree:
    def test_module_exists(self):
        assert MODULE_PATH.is_file(), f"missing module: {MODULE_PATH}"

    def test_static_imports_are_stdlib_or_numpy_only(self):
        roots = _imported_roots(MODULE_PATH.read_text(encoding="utf-8"))
        assert "flopy" not in roots
        assert "pyemu" not in roots
        allowed = set(sys.stdlib_module_names) | {"numpy"}
        unexpected = roots - allowed
        assert not unexpected, (
            f"case_artifact_lock.py may import only the standard library + numpy; "
            f"found disallowed import roots: {sorted(unexpected)}"
        )

    def test_calling_functions_does_not_import_flopy_or_pyemu(self):
        """A clean interpreter: import the module and exercise every public
        function, then assert flopy/pyemu never entered sys.modules."""
        code = f"""
import sys
sys.path.insert(0, {str(SRC_DIR)!r})
import tempfile
from pathlib import Path
import numpy as np
import case_artifact_lock as cal

# hash_array
cal.hash_array(np.arange(6).reshape(2, 3))

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    npz = root / "artifact.npz"
    np.savez(npz, a=np.arange(4), b=np.ones((2, 2), dtype=np.float32))
    m = cal.write_artifact_manifest(npz, {{"case_name": "c"}}, manifest_path=root / "m.json")
    assert cal.verify_artifact(npz, root / "m.json") is True

assert "flopy" not in sys.modules, "flopy leaked into sys.modules"
assert "pyemu" not in sys.modules, "pyemu leaked into sys.modules"
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
        )
        assert result.returncode == 0, (
            f"subprocess failed (rc={result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "OK" in result.stdout


# =============================================================================
# Criterion 2: hash_array — content hash over dtype, shape, C-contiguous bytes
# =============================================================================

class TestHashArray:
    def test_returns_sha256_hex(self):
        h = cal.hash_array(np.arange(5))
        assert isinstance(h, str)
        assert len(h) == 64
        int(h, 16)  # valid hex

    def test_equal_arrays_hash_equal(self):
        a = np.arange(12, dtype=np.float64).reshape(3, 4)
        b = np.arange(12, dtype=np.float64).reshape(3, 4)
        assert cal.hash_array(a) == cal.hash_array(b)

    def test_dtype_difference_changes_hash(self):
        a = np.arange(6, dtype=np.int32)
        b = np.arange(6, dtype=np.int64)
        assert cal.hash_array(a) != cal.hash_array(b)

    def test_shape_difference_changes_hash(self):
        base = np.arange(12, dtype=np.float64)
        a = base.reshape(3, 4)
        b = base.reshape(4, 3)
        # Same raw C-contiguous bytes, different shape -> must differ.
        assert cal.hash_array(a) != cal.hash_array(b)

    def test_single_element_change_changes_hash(self):
        a = np.arange(12, dtype=np.float64).reshape(3, 4)
        b = a.copy()
        b[1, 2] += 1.0
        assert cal.hash_array(a) != cal.hash_array(b)

    def test_noncontiguous_view_and_contiguous_copy_hash_equal(self):
        a = np.arange(12, dtype=np.float64).reshape(3, 4)
        view = a[:, ::2]  # non-contiguous view
        assert not view.flags["C_CONTIGUOUS"]
        copy = np.ascontiguousarray(view)
        assert copy.flags["C_CONTIGUOUS"]
        assert cal.hash_array(view) == cal.hash_array(copy)


# =============================================================================
# Criterion 3: write_artifact_manifest structure + sibling path + parent mkdir
# =============================================================================

class TestWriteManifest:
    def test_manifest_contains_required_structure(self, tmp_path):
        arrays = _make_arrays()
        npz = _save_npz(tmp_path / "artifact.npz", arrays)
        manifest_path = tmp_path / "artifact.manifest.json"

        caller = {"case_name": "limmat_case_A", "step": "F.3"}
        m = cal.write_artifact_manifest(npz, caller, manifest_path=manifest_path)

        # returned dict == on-disk JSON
        on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert on_disk == m

        assert "schema_version" in m and isinstance(m["schema_version"], str)
        # caller's fields carried through
        assert m["case_name"] == "limmat_case_A"
        assert m["step"] == "F.3"

        # array_hashes covers EVERY member; members sorted list matching keys
        assert set(m["array_hashes"].keys()) == set(arrays)
        assert m["members"] == sorted(arrays)
        assert "aggregate_hash" in m and isinstance(m["aggregate_hash"], str)

    def test_array_hashes_are_the_content_hashes(self, tmp_path):
        arrays = _make_arrays()
        npz = _save_npz(tmp_path / "artifact.npz", arrays)
        m = cal.write_artifact_manifest(npz, {}, manifest_path=tmp_path / "m.json")
        for name, arr in arrays.items():
            assert m["array_hashes"][name] == cal.hash_array(arr)

    def test_aggregate_uses_shared_fold_idiom(self, tmp_path):
        """The aggregate must be the sorted-(name, hash) fold shared with
        mother_model_lock, computed over the sorted members + array_hashes."""
        arrays = _make_arrays()
        npz = _save_npz(tmp_path / "artifact.npz", arrays)
        m = cal.write_artifact_manifest(npz, {}, manifest_path=tmp_path / "m.json")
        expected = mml._fold_aggregate(m["members"], m["array_hashes"])
        assert m["aggregate_hash"] == expected

    def test_default_manifest_path_is_a_created_sibling(self, tmp_path):
        arrays = _make_arrays()
        npz = _save_npz(tmp_path / "sub" / "artifact.npz", arrays)

        m = cal.write_artifact_manifest(npz, {"case_name": "c"})

        # A sibling JSON manifest was written next to the .npz ...
        siblings = [p for p in npz.parent.glob("*.json")]
        assert len(siblings) == 1, f"expected one sibling manifest, found {siblings}"
        sib = siblings[0]
        assert json.loads(sib.read_text(encoding="utf-8")) == m
        # ... and it verifies against the artifact.
        assert cal.verify_artifact(npz, sib) is True

    def test_creates_missing_parent_directory(self, tmp_path):
        arrays = _make_arrays()
        npz = _save_npz(tmp_path / "artifact.npz", arrays)
        nested = tmp_path / "does" / "not" / "exist" / "m.json"
        assert not nested.parent.exists()

        cal.write_artifact_manifest(npz, {}, manifest_path=nested)

        assert nested.is_file()


# =============================================================================
# Criterion 4: verify_artifact — True iff exact match, else names FIRST divergence
# =============================================================================

class TestVerifyArtifact:
    def _written(self, tmp_path, arrays=None, order=None):
        arrays = arrays or _make_arrays()
        npz = _save_npz(tmp_path / "artifact.npz", arrays, order=order)
        manifest_path = tmp_path / "m.json"
        cal.write_artifact_manifest(npz, {"case_name": "c"}, manifest_path=manifest_path)
        return npz, manifest_path, arrays

    def test_verify_true_on_unchanged(self, tmp_path):
        npz, manifest_path, _ = self._written(tmp_path)
        assert cal.verify_artifact(npz, manifest_path) is True

    def test_changed_contents_raise_naming_member(self, tmp_path):
        npz, manifest_path, arrays = self._written(tmp_path)
        arrays["k"] = arrays["k"] + 1.0  # change one member's contents
        _save_npz(npz, arrays)
        with pytest.raises(ValueError, match="k"):
            cal.verify_artifact(npz, manifest_path)

    def test_missing_member_raises_naming_it(self, tmp_path):
        npz, manifest_path, arrays = self._written(tmp_path)
        del arrays["idomain"]  # drop a locked member
        _save_npz(npz, arrays)
        with pytest.raises(ValueError, match="idomain"):
            cal.verify_artifact(npz, manifest_path)

    def test_extra_member_raises_naming_it(self, tmp_path):
        npz, manifest_path, arrays = self._written(tmp_path)
        arrays["surprise_extra"] = np.zeros(3)
        _save_npz(npz, arrays)
        with pytest.raises(ValueError, match="surprise_extra"):
            cal.verify_artifact(npz, manifest_path)

    def test_names_first_divergent_member_in_sorted_order(self, tmp_path):
        # Members sorted: idomain, k, top. Introduce TWO divergences:
        #  - change 'top' (last in sort order)
        #  - add extra 'aaa_extra' (sorts FIRST of everything)
        # The first divergence in sorted order is 'aaa_extra'.
        npz, manifest_path, arrays = self._written(tmp_path)
        arrays["top"] = arrays["top"] + 5.0
        arrays["aaa_extra"] = np.ones(2)
        _save_npz(npz, arrays)
        with pytest.raises(ValueError) as exc:
            cal.verify_artifact(npz, manifest_path)
        assert "aaa_extra" in str(exc.value)
        assert "top" not in str(exc.value)


# =============================================================================
# Criterion 5: manifest internal-integrity validation (clean ValueError only)
# =============================================================================

class TestManifestIntegrity:
    def _write(self, tmp_path):
        arrays = _make_arrays()
        npz = _save_npz(tmp_path / "artifact.npz", arrays)
        manifest_path = tmp_path / "m.json"
        cal.write_artifact_manifest(npz, {"case_name": "c"}, manifest_path=manifest_path)
        return npz, manifest_path

    def _tamper(self, manifest_path, mutate):
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        mutate(m)
        manifest_path.write_text(json.dumps(m), encoding="utf-8")

    def test_missing_required_key_raises_value_error(self, tmp_path):
        npz, manifest_path = self._write(tmp_path)
        self._tamper(manifest_path, lambda m: m.pop("aggregate_hash"))
        with pytest.raises(ValueError):
            cal.verify_artifact(npz, manifest_path)

    def test_tampered_aggregate_raises_value_error(self, tmp_path):
        npz, manifest_path = self._write(tmp_path)
        self._tamper(manifest_path, lambda m: m.__setitem__("aggregate_hash", "0" * 64))
        with pytest.raises(ValueError):
            cal.verify_artifact(npz, manifest_path)

    def test_unsorted_members_raises_value_error(self, tmp_path):
        npz, manifest_path = self._write(tmp_path)
        self._tamper(manifest_path, lambda m: m.__setitem__("members", list(reversed(m["members"]))))
        with pytest.raises(ValueError):
            cal.verify_artifact(npz, manifest_path)

    def test_duplicate_member_raises_value_error(self, tmp_path):
        npz, manifest_path = self._write(tmp_path)
        def dup(m):
            m["members"] = sorted(m["members"] + [m["members"][0]])
        self._tamper(manifest_path, dup)
        with pytest.raises(ValueError):
            cal.verify_artifact(npz, manifest_path)

    def test_members_inconsistent_with_array_hashes_raises_value_error(self, tmp_path):
        npz, manifest_path = self._write(tmp_path)
        # Add a member name not present in array_hashes keys.
        self._tamper(manifest_path, lambda m: m["members"].append("zzz_ghost"))
        with pytest.raises(ValueError):
            cal.verify_artifact(npz, manifest_path)

    def test_invalid_json_raises_clean_value_error_not_jsondecodeerror(self, tmp_path):
        npz, manifest_path = self._write(tmp_path)
        manifest_path.write_text("{ this is : not json", encoding="utf-8")
        with pytest.raises(ValueError) as exc:
            cal.verify_artifact(npz, manifest_path)
        # JSONDecodeError subclasses ValueError; the contract demands it be
        # re-raised as a plain ValueError, not leaked raw.
        assert not isinstance(exc.value, json.JSONDecodeError)

    def test_internally_consistent_but_wrong_hash_still_caught_against_npz(self, tmp_path):
        """Defense in depth: a manifest hand-edited so a member's recorded
        hash is wrong AND the aggregate is recomputed to match (internally
        self-consistent) must still fail verification against the real .npz."""
        npz, manifest_path = self._write(tmp_path)
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        target = m["members"][0]
        m["array_hashes"][target] = "a" * 64
        m["aggregate_hash"] = mml._fold_aggregate(m["members"], m["array_hashes"])
        manifest_path.write_text(json.dumps(m), encoding="utf-8")
        with pytest.raises(ValueError, match=target):
            cal.verify_artifact(npz, manifest_path)


# =============================================================================
# Criterion 6: CONTENT-not-byte determinism
# =============================================================================

class TestContentNotByteDeterminism:
    def test_writing_manifest_twice_is_identical(self, tmp_path):
        arrays = _make_arrays()
        npz = _save_npz(tmp_path / "artifact.npz", arrays)
        m1 = cal.write_artifact_manifest(npz, {"case_name": "c"}, manifest_path=tmp_path / "m1.json")
        m2 = cal.write_artifact_manifest(npz, {"case_name": "c"}, manifest_path=tmp_path / "m2.json")
        assert m1["array_hashes"] == m2["array_hashes"]
        assert m1["aggregate_hash"] == m2["aggregate_hash"]

    def test_resave_same_arrays_new_npz_still_verifies(self, tmp_path):
        """Re-saving the SAME arrays to a different .npz changes the zip's
        embedded byte layout (member order / mtimes), but content hashing
        must still verify True against the original manifest."""
        arrays = _make_arrays()
        npz1 = _save_npz(tmp_path / "artifact1.npz", arrays)
        manifest_path = tmp_path / "m.json"
        cal.write_artifact_manifest(npz1, {"case_name": "c"}, manifest_path=manifest_path)

        # Different member ordering => different zip bytes, identical contents.
        reordered = list(reversed(list(arrays)))
        npz2 = _save_npz(tmp_path / "artifact2.npz", arrays, order=reordered)

        assert npz1.read_bytes() != npz2.read_bytes(), (
            "test precondition: the two .npz files must have different bytes"
        )
        assert cal.verify_artifact(npz2, manifest_path) is True
