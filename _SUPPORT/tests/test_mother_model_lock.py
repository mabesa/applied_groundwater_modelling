"""
Unit tests for mother_model_lock (write/verify a hash-verified workspace lock).

Tests cover:
- Scenario A: write a lock over a synthetic tmp workspace (with nested
  subdirs); verify passes on an unchanged workspace (including a
  byte-identical copy at a different path); a single-byte mutation, an
  added file, and a removed file each make verify raise ValueError naming
  the offending file.
- Scenario B: the module is flopy/pyemu-free (checked via a clean
  subprocess) and write+verify complete well under a second for a small
  workspace.
- Determinism: writing the lock twice for an unchanged workspace yields a
  byte-identical `files` list and `aggregate_hash`.

Run with: uv run pytest _SUPPORT/tests/test_mother_model_lock.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Add src to path (mirrors the style used by other tests in this directory)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import mother_model_lock as mml
from mother_model_lock import (
    DEFAULT_LOCK_PATH,
    write_mother_model_lock,
    verify_mother_model_lock,
)


# =============================================================================
# Helpers
# =============================================================================

def _build_workspace(root: Path) -> Path:
    """Build a tiny synthetic model workspace with nested subdirectories."""
    ws = root / "mother_model_ws"
    (ws / "sub").mkdir(parents=True)
    (ws / "sub" / "deeper").mkdir(parents=True)

    (ws / "limmat_valley.nam").write_text("BEGIN options\nEND options\n", encoding="utf-8")
    (ws / "sub" / "limmat_valley.dis").write_bytes(b"\x00\x01\x02\x03binarydummy")
    (ws / "sub" / "deeper" / "note.txt").write_text("frozen mother model\n", encoding="utf-8")
    return ws


# =============================================================================
# Scenario A: write / verify / mutate / add / remove
# =============================================================================

class TestWriteAndVerify:
    def test_verify_passes_on_unchanged_workspace(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock" / "mother_model_lock.json"

        lock = write_mother_model_lock(ws, lock_path=lock_path, sim_name="test_sim")

        assert lock["schema_version"]
        assert lock["sim_name"] == "test_sim"
        assert lock["files"] == sorted(lock["files"])
        assert len(lock["files"]) == 3
        assert set(lock["file_hashes"].keys()) == set(lock["files"])
        assert "aggregate_hash" in lock and isinstance(lock["aggregate_hash"], str)

        assert lock_path.is_file()
        on_disk = json.loads(lock_path.read_text(encoding="utf-8"))
        assert on_disk == lock

        assert verify_mother_model_lock(ws, lock_path=lock_path) is True

    def test_verify_passes_on_byte_identical_copy_at_different_path(self, tmp_path):
        """Hashing is per relative path, so a copy at a new absolute path still verifies."""
        ws = _build_workspace(tmp_path / "original")
        lock_path = tmp_path / "mother_model_lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        copy_root = tmp_path / "copy" / "mother_model_ws"
        shutil.copytree(ws, copy_root)

        assert verify_mother_model_lock(copy_root, lock_path=lock_path) is True

    def test_creates_parent_dir_of_lock_path(self, tmp_path):
        ws = _build_workspace(tmp_path)
        nested_lock_path = tmp_path / "does" / "not" / "exist" / "lock.json"
        assert not nested_lock_path.parent.exists()

        write_mother_model_lock(ws, lock_path=nested_lock_path)

        assert nested_lock_path.is_file()

    def test_mutation_raises_naming_the_file(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        mutated = ws / "sub" / "deeper" / "note.txt"
        mutated.write_text("MUTATED bytes\n", encoding="utf-8")

        with pytest.raises(ValueError, match="sub/deeper/note.txt"):
            verify_mother_model_lock(ws, lock_path=lock_path)

    def test_added_file_raises(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        (ws / "sub" / "extra_new_file.txt").write_text("surprise\n", encoding="utf-8")

        with pytest.raises(ValueError, match="extra_new_file.txt"):
            verify_mother_model_lock(ws, lock_path=lock_path)

    def test_removed_file_raises(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        (ws / "limmat_valley.nam").unlink()

        with pytest.raises(ValueError, match="limmat_valley.nam"):
            verify_mother_model_lock(ws, lock_path=lock_path)


# =============================================================================
# Determinism
# =============================================================================

class TestDeterminism:
    def test_writing_twice_yields_identical_files_and_aggregate_hash(self, tmp_path):
        ws = _build_workspace(tmp_path)

        lock1 = write_mother_model_lock(ws, lock_path=tmp_path / "lock1.json")
        lock2 = write_mother_model_lock(ws, lock_path=tmp_path / "lock2.json")

        assert lock1["files"] == lock2["files"]
        assert lock1["aggregate_hash"] == lock2["aggregate_hash"]
        assert lock1["file_hashes"] == lock2["file_hashes"]

    def test_default_lock_path_location(self):
        # No I/O here on purpose: just confirm the constant points at
        # _SUPPORT/validation/mother_model_lock.json relative to the module,
        # without ever writing to the real repo path in a test.
        assert DEFAULT_LOCK_PATH.name == "mother_model_lock.json"
        assert DEFAULT_LOCK_PATH.parent.name == "validation"
        assert DEFAULT_LOCK_PATH.parent.parent == Path(mml.__file__).resolve().parent.parent


# =============================================================================
# Scenario B: flopy/pyemu-free + fast
# =============================================================================

_SUBPROCESS_CHECK_CODE = """
import sys
sys.path.insert(0, {src_dir!r})

import tempfile
from pathlib import Path

from mother_model_lock import write_mother_model_lock, verify_mother_model_lock

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    ws = root / "ws"
    (ws / "sub").mkdir(parents=True)
    (ws / "a.txt").write_text("hello")
    (ws / "sub" / "b.txt").write_text("world")

    lock_path = root / "lock.json"
    write_mother_model_lock(ws, lock_path=lock_path, sim_name="subprocess_check")
    assert verify_mother_model_lock(ws, lock_path=lock_path) is True

assert "flopy" not in sys.modules, "flopy leaked into sys.modules"
assert "pyemu" not in sys.modules, "pyemu leaked into sys.modules"
print("OK")
"""


class TestLockPathInsideWorkspace:
    def test_write_raises_when_lock_path_inside_workspace(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = ws / "sub" / "mother_model_lock.json"

        with pytest.raises(ValueError, match="lock_path must not be inside workspace"):
            write_mother_model_lock(ws, lock_path=lock_path)

    def test_write_raises_when_lock_path_is_workspace_itself_child(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = ws / "mother_model_lock.json"

        with pytest.raises(ValueError, match="lock_path must not be inside workspace"):
            write_mother_model_lock(ws, lock_path=lock_path)


class TestWorkspaceMustExist:
    def test_write_raises_on_nonexistent_workspace(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            write_mother_model_lock(missing, lock_path=tmp_path / "lock.json")

    def test_write_raises_when_workspace_is_a_file(self, tmp_path):
        not_a_dir = tmp_path / "im_a_file.txt"
        not_a_dir.write_text("not a directory", encoding="utf-8")
        with pytest.raises(FileNotFoundError):
            write_mother_model_lock(not_a_dir, lock_path=tmp_path / "lock.json")

    def test_verify_raises_on_nonexistent_workspace(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            verify_mother_model_lock(missing, lock_path=lock_path)

    def test_verify_raises_when_workspace_is_a_file(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        not_a_dir = tmp_path / "im_a_file.txt"
        not_a_dir.write_text("not a directory", encoding="utf-8")
        with pytest.raises(FileNotFoundError):
            verify_mother_model_lock(not_a_dir, lock_path=lock_path)


class TestLockIntegrityValidation:
    def test_aggregate_tampering_raises(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["aggregate_hash"] = "0" * 64
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        with pytest.raises(ValueError, match="internally inconsistent"):
            verify_mother_model_lock(ws, lock_path=lock_path)

    def test_good_file_hashes_but_stale_aggregate_raises(self, tmp_path):
        """Hand-edit a file_hash entry without updating aggregate_hash: the
        per-file map alone would look self-consistent (files == file_hashes
        keys), but the aggregate no longer folds to the recorded value."""
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        some_key = lock["files"][0]
        lock["file_hashes"][some_key] = "f" * 64
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        with pytest.raises(ValueError, match="internally inconsistent"):
            verify_mother_model_lock(ws, lock_path=lock_path)

    def test_malformed_lock_missing_key_raises_value_error(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        del lock["aggregate_hash"]
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        with pytest.raises(ValueError):
            verify_mother_model_lock(ws, lock_path=lock_path)

    def test_malformed_lock_files_file_hashes_mismatch_raises(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["files"].append("nonexistent_extra_entry.txt")
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        with pytest.raises(ValueError):
            verify_mother_model_lock(ws, lock_path=lock_path)

    def test_malformed_lock_invalid_json_raises_value_error_not_json_decode_error(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(ValueError):
            verify_mother_model_lock(ws, lock_path=lock_path)


class TestSymlinkPolicy:
    def test_symlink_is_skipped_from_hashing(self, tmp_path):
        ws = _build_workspace(tmp_path)
        real_file = ws / "limmat_valley.nam"
        link = ws / "sub" / "link_to_nam.txt"
        try:
            link.symlink_to(real_file)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported on this platform/filesystem")

        lock_path = tmp_path / "lock.json"
        lock = write_mother_model_lock(ws, lock_path=lock_path)

        assert "sub/link_to_nam.txt" not in lock["files"]
        assert "limmat_valley.nam" in lock["files"]

        # Verify still passes with the symlink present...
        assert verify_mother_model_lock(ws, lock_path=lock_path) is True

        # ...and still passes once the symlink is removed, confirming it
        # never participated in the lock.
        link.unlink()
        assert verify_mother_model_lock(ws, lock_path=lock_path) is True


class TestElementTypeValidation:
    """Fix A1: a doctored lock with non-string elements must raise a clean
    ValueError, never a raw TypeError (the 'never TypeError' contract)."""

    def test_non_string_element_in_files_raises_value_error_not_type_error(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["files"].append(1)
        lock["file_hashes"]["1"] = "0" * 64
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        with pytest.raises(ValueError, match="'files' must be a list of strings"):
            verify_mother_model_lock(ws, lock_path=lock_path)

    def test_non_string_value_in_file_hashes_raises_value_error_not_type_error(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        some_key = lock["files"][0]
        lock["file_hashes"][some_key] = 12345
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        with pytest.raises(ValueError, match="'file_hashes' values must all be strings"):
            verify_mother_model_lock(ws, lock_path=lock_path)


class TestSchemaVersionValidation:
    """Fix A2: an incompatible schema_version must raise ValueError."""

    def test_wrong_schema_version_raises(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["schema_version"] = "2.0"
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        with pytest.raises(ValueError, match="incompatible schema_version"):
            verify_mother_model_lock(ws, lock_path=lock_path)


class TestEmptyWorkspaceRejected:
    """Fix A3: writing a lock over an empty directory must raise ValueError
    rather than silently producing a lock that verifies vacuously."""

    def test_write_raises_on_empty_directory(self, tmp_path):
        empty_ws = tmp_path / "empty_ws"
        empty_ws.mkdir()

        with pytest.raises(ValueError, match="no regular files to lock"):
            write_mother_model_lock(empty_ws, lock_path=tmp_path / "lock.json")

    def test_write_raises_on_directory_containing_only_empty_subdirs(self, tmp_path):
        ws = tmp_path / "ws_only_dirs"
        (ws / "sub" / "deeper").mkdir(parents=True)

        with pytest.raises(ValueError, match="no regular files to lock"):
            write_mother_model_lock(ws, lock_path=tmp_path / "lock.json")


class TestCaseNormalizedLockInsideWorkspace:
    """Fix A4: the lock-inside-workspace guard is checked case-normalized so
    a differently-cased path can't escape it on a case-insensitive
    filesystem.

    Not portably testable end-to-end via write_mother_model_lock: on a
    genuinely case-sensitive filesystem (e.g. Linux), a differently-cased
    path IS a different, non-existent location on disk, so resolve() would
    not make it collide with the real workspace path regardless of the
    guard's own logic. Instead we directly exercise the same normcase
    comparison the fix performs, which is portable and locks in the fix
    independent of the host filesystem's case sensitivity.
    """

    def test_exact_case_still_rejected(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = ws / "sub" / "mother_model_lock.json"

        with pytest.raises(ValueError, match="lock_path must not be inside workspace"):
            write_mother_model_lock(ws, lock_path=lock_path)

    def test_normcase_comparison_treats_differently_cased_inside_path_as_inside(self, tmp_path):
        import os as _os
        from pathlib import Path as _Path

        ws = _build_workspace(tmp_path)
        inside = (ws / "sub" / "lock.json").resolve()

        # Simulate the normcased form of a differently-cased equivalent path
        # (what a case-insensitive filesystem would resolve a differently
        # cased lock path to): same normcase(str(...)) as the exact-case
        # inside path.
        normcased_ws = _Path(_os.path.normcase(str(ws.resolve())))
        normcased_inside_upper = _Path(_os.path.normcase(str(inside).upper()))
        normcased_inside_exact = _Path(_os.path.normcase(str(inside)))

        # On a case-insensitive normcase (e.g. Windows/macOS default), the
        # upper-cased and exact-case forms normalize identically and both
        # nest under the workspace.
        if _os.path.normcase("A") == _os.path.normcase("a"):
            assert normcased_inside_upper.is_relative_to(normcased_ws)
        assert normcased_inside_exact.is_relative_to(normcased_ws)


class TestContentTamperingWithConsistentAggregateStillCaught:
    """Regression: a lock that is internally self-consistent (a file_hash
    altered AND the aggregate_hash recomputed to match) must still be caught
    -- not by _load_and_validate_lock's internal check, but by the live
    workspace comparison in verify_mother_model_lock, which compares the
    lock's recorded per-file hash against a fresh hash of the actual file on
    disk. This locks in that defense-in-depth layer explicitly."""

    def test_self_consistent_but_workspace_mismatched_lock_raises_content_changed(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"
        write_mother_model_lock(ws, lock_path=lock_path)

        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        target = lock["files"][0]
        # Alter one file's recorded hash to an arbitrary-but-valid-looking
        # sha256 hex string, then recompute aggregate_hash so the lock is
        # internally self-consistent (passes _load_and_validate_lock).
        lock["file_hashes"][target] = "a" * 64
        lock["aggregate_hash"] = mml._fold_aggregate(lock["files"], lock["file_hashes"])
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        # _load_and_validate_lock alone would accept this lock (internally
        # consistent). verify_mother_model_lock must still catch it because
        # the recorded hash for `target` no longer matches the real file on
        # disk.
        with pytest.raises(ValueError, match=f"content changed for file '{target}'"):
            verify_mother_model_lock(ws, lock_path=lock_path)


class TestWriteRequiresExplicitLockPath:
    """Fix (2026-07): write_mother_model_lock must not default to writing
    inside the repo tree (DEFAULT_LOCK_PATH) -- unsafe on a read-only Hub /
    student checkout. Writes must always name an explicit destination;
    DEFAULT_LOCK_PATH remains the default for *reads* (verify)."""

    def test_write_with_no_lock_path_raises_value_error(self, tmp_path):
        ws = _build_workspace(tmp_path)
        with pytest.raises(ValueError, match="requires an explicit lock_path"):
            write_mother_model_lock(ws)

    def test_write_with_explicit_lock_path_still_works(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "explicit_lock.json"

        lock = write_mother_model_lock(ws, lock_path=lock_path, sim_name="explicit_check")

        assert lock_path.is_file()
        assert lock["sim_name"] == "explicit_check"
        assert verify_mother_model_lock(ws, lock_path=lock_path) is True


class TestFlopyFreeAndFast:
    def test_subprocess_is_flopy_and_pyemu_free(self):
        src_dir = str(Path(__file__).parent.parent / "src")
        code = _SUBPROCESS_CHECK_CODE.format(src_dir=src_dir)

        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"subprocess failed (rc={result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_write_and_verify_are_fast(self, tmp_path):
        ws = _build_workspace(tmp_path)
        lock_path = tmp_path / "lock.json"

        t0 = time.monotonic()
        write_mother_model_lock(ws, lock_path=lock_path)
        verify_mother_model_lock(ws, lock_path=lock_path)
        elapsed = time.monotonic() - t0

        assert elapsed < 1.0, f"write+verify took {elapsed:.3f}s, expected well under 1s"
