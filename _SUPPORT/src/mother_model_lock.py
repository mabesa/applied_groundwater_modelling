"""
mother_model_lock — hash-verified lock for a frozen MODFLOW6 model workspace.

Purpose: once a "mother model" workspace (e.g. the base flow model produced by
an earlier notebook) is considered final, pin it as a lock file so that all
downstream work (scenario builds, calibration, transport handoff, ...) can
verify it is building against the exact, unchanged workspace rather than a
silently-drifted copy.

Scope: this module is pure Python plumbing — it walks a directory tree and
hashes file bytes. It does NOT import flopy or pyemu, does NOT run MODFLOW,
and does NOT know anything about MODFLOW6 file formats. It works on an
arbitrary directory of files.

Lock file schema (JSON)
------------------------
{
    "schema_version": "1.0",
    "sim_name": "<sim_name>",
    "files": ["<sorted POSIX relative paths>", ...],
    "file_hashes": {"<relative path>": "<sha256 hex>", ...},
    "aggregate_hash": "<sha256 hex over the sorted (path, hash) pairs>"
}
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA_VERSION = "1.0"

# _SUPPORT/src/mother_model_lock.py -> _SUPPORT/validation/mother_model_lock.json
_MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_LOCK_PATH = _MODULE_DIR.parent / "validation" / "mother_model_lock.json"

_CHUNK_SIZE = 65536


def _iter_files_sorted(workspace: Path) -> list[Path]:
    """Return all regular files under *workspace*, sorted by POSIX relative path."""
    files = [p for p in workspace.rglob("*") if p.is_file()]
    return sorted(files, key=lambda p: p.relative_to(workspace).as_posix())


def _hash_file(path: Path) -> str:
    """Return the sha256 hex digest of a single file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def _compute_manifest(workspace) -> dict:
    """Compute the {files, file_hashes, aggregate_hash} manifest for *workspace*.

    Deterministic: files are sorted by POSIX relative path, and the aggregate
    hash is derived by folding the sorted (relative_path, file_hash) pairs
    through a single sha256, so re-running on an unchanged workspace always
    yields byte-identical output.
    """
    workspace = Path(workspace)
    files = _iter_files_sorted(workspace)
    rel_paths = [p.relative_to(workspace).as_posix() for p in files]
    file_hashes = {rel: _hash_file(p) for rel, p in zip(rel_paths, files)}

    agg = hashlib.sha256()
    for rel in rel_paths:  # already sorted
        agg.update(rel.encode("utf-8"))
        agg.update(b"\x00")
        agg.update(file_hashes[rel].encode("utf-8"))
        agg.update(b"\n")

    return {
        "files": rel_paths,
        "file_hashes": file_hashes,
        "aggregate_hash": agg.hexdigest(),
    }


def write_mother_model_lock(workspace, lock_path=None, sim_name: str = "limmat_valley") -> dict:
    """Write a hash-verified lock for *workspace* to *lock_path*.

    Parameters
    ----------
    workspace:
        Directory whose current contents (recursively, all regular files)
        are hashed and pinned.
    lock_path:
        Where to write the lock JSON. Defaults to ``DEFAULT_LOCK_PATH``. The
        parent directory is created if it does not exist.
    sim_name:
        Free-form label recorded in the lock (e.g. the MODFLOW6 sim name).

    Returns
    -------
    dict — the lock contents that were written (same structure as the JSON
    file).
    """
    workspace = Path(workspace)
    lock_path = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH

    manifest = _compute_manifest(workspace)
    lock = {
        "schema_version": SCHEMA_VERSION,
        "sim_name": sim_name,
        "files": manifest["files"],
        "file_hashes": manifest["file_hashes"],
        "aggregate_hash": manifest["aggregate_hash"],
    }

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as fh:
        json.dump(lock, fh, indent=2, sort_keys=True)
        fh.write("\n")

    return lock


def verify_mother_model_lock(workspace, lock_path=None) -> bool:
    """Verify that *workspace* exactly matches the lock at *lock_path*.

    Returns ``True`` when every locked file is present, unchanged, and no
    extra files exist. Raises ``ValueError`` naming the first (in sorted
    POSIX-path order) missing, extra, or content-mismatched file otherwise.
    """
    workspace = Path(workspace)
    lock_path = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH

    with open(lock_path, "r", encoding="utf-8") as fh:
        lock = json.load(fh)

    locked_files = lock["files"]
    locked_hashes = lock["file_hashes"]
    locked_set = set(locked_files)

    current = _compute_manifest(workspace)
    current_hashes = current["file_hashes"]
    current_set = set(current["files"])

    # Deterministic order: walk the union of locked + current relative paths,
    # sorted, so the FIRST discrepancy encountered is reproducible.
    for rel in sorted(locked_set | current_set):
        if rel not in current_set:
            raise ValueError(f"mother model lock mismatch: missing file {rel!r} (present in lock, absent from workspace)")
        if rel not in locked_set:
            raise ValueError(f"mother model lock mismatch: extra file {rel!r} (present in workspace, not in lock)")
        if current_hashes[rel] != locked_hashes[rel]:
            raise ValueError(f"mother model lock mismatch: content changed for file {rel!r}")

    return True
