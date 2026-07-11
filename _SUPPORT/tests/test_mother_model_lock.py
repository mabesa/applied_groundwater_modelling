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
