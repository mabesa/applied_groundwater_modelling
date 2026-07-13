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
import os
from pathlib import Path

SCHEMA_VERSION = "1.0"

# _SUPPORT/src/mother_model_lock.py -> _SUPPORT/validation/mother_model_lock.json
_MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_LOCK_PATH = _MODULE_DIR.parent / "validation" / "mother_model_lock.json"

_CHUNK_SIZE = 65536


def _iter_files_sorted(workspace: Path) -> list[Path]:
    """Return all regular, non-symlink files under *workspace*, sorted by POSIX
    relative path.

    Symlinks are deliberately excluded (``p.is_file() and not p.is_symlink()``)
    so hashing never follows a link outside the tree and behavior is fully
    deterministic. A frozen MF6 workspace is not expected to contain any.
    """
    files = [p for p in workspace.rglob("*") if p.is_file() and not p.is_symlink()]
    return sorted(files, key=lambda p: p.relative_to(workspace).as_posix())


def _hash_file(path: Path) -> str:
    """Return the sha256 hex digest of a single file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def _fold_aggregate(rel_paths, file_hashes) -> str:
    """Fold sorted (relative_path, file_hash) pairs into a single sha256 hex digest.

    Shared by ``_compute_manifest`` (computing the aggregate over a live
    workspace) and ``verify_mother_model_lock`` (recomputing the aggregate over
    a lock file's own recorded ``files``/``file_hashes`` to detect tampering),
    so the two can never drift apart.

    *rel_paths* must already be sorted. Relative paths are encoded with
    ``surrogateescape`` so unusual (non-UTF-8-decodable) POSIX filenames can't
    crash hashing.
    """
    agg = hashlib.sha256()
    for rel in rel_paths:
        agg.update(rel.encode("utf-8", "surrogateescape"))
        agg.update(b"\x00")
        agg.update(file_hashes[rel].encode("utf-8", "surrogateescape"))
        agg.update(b"\n")
    return agg.hexdigest()


def _require_existing_dir(workspace: Path) -> None:
    """Raise FileNotFoundError if *workspace* is not an existing directory."""
    if not workspace.is_dir():
        raise FileNotFoundError(f"mother model workspace not found or not a directory: {workspace}")


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

    return {
        "files": rel_paths,
        "file_hashes": file_hashes,
        "aggregate_hash": _fold_aggregate(rel_paths, file_hashes),
    }


def write_mother_model_lock(workspace, lock_path=None, sim_name: str = "limmat_valley") -> dict:
    """Write a hash-verified lock for *workspace* to *lock_path*.

    Parameters
    ----------
    workspace:
        Directory whose current contents (recursively, all regular,
        non-symlink files) are hashed and pinned. Symlinks are skipped (see
        ``_iter_files_sorted``).
    lock_path:
        Where to write the lock JSON. REQUIRED — there is no default for
        writes (see ``ValueError`` below): ``DEFAULT_LOCK_PATH`` points inside
        the repo tree, and silently writing there is unsafe on a read-only
        JupyterHub checkout or a student clone. ``DEFAULT_LOCK_PATH`` remains
        the default for *reads* via ``verify_mother_model_lock``. The parent
        directory of *lock_path* is created if it does not exist. Must NOT be
        inside *workspace* — a lock written into the hashed tree can never
        verify (it is an extra file on the first write, and a content-changed
        file on every rewrite thereafter).
    sim_name:
        Free-form label recorded in the lock (e.g. the MODFLOW6 sim name).

    Returns
    -------
    dict — the lock contents that were written (same structure as the JSON
    file).

    Raises
    ------
    ValueError
        If *lock_path* is ``None`` (writes must name an explicit destination
        — see above), if *lock_path* resolves to a location inside
        *workspace* (checked case-insensitively, so this also catches a
        differently-cased escape on a case-insensitive filesystem), or if
        *workspace* contains zero regular files to lock.
    FileNotFoundError
        If *workspace* does not exist or is not a directory.
    """
    if lock_path is None:
        raise ValueError("write_mother_model_lock requires an explicit lock_path")

    workspace = Path(workspace)
    lock_path = Path(lock_path)

    _require_existing_dir(workspace)

    resolved_workspace = workspace.resolve()
    resolved_lock_path = lock_path.resolve()
    # Case-normalize before the is_relative_to check so a differently-cased
    # lock path (e.g. on a case-insensitive filesystem such as default macOS
    # HFS+/APFS or Windows) can't slip through the guard. os.path.normcase is
    # a no-op on case-sensitive POSIX filesystems (e.g. Linux), so this is
    # purely additive there. resolve() (above) already handles symlinks and
    # relative paths.
    normcased_workspace = Path(os.path.normcase(str(resolved_workspace)))
    normcased_lock_path = Path(os.path.normcase(str(resolved_lock_path)))
    if normcased_lock_path.is_relative_to(normcased_workspace):
        raise ValueError(
            f"lock_path must not be inside workspace: {lock_path} is inside {workspace}"
        )

    manifest = _compute_manifest(workspace)
    if not manifest["files"]:
        raise ValueError(
            f"workspace contains no regular files to lock: {workspace}"
        )

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


_REQUIRED_LOCK_KEYS = ("schema_version", "sim_name", "files", "file_hashes", "aggregate_hash")


def _load_and_validate_lock(lock_path: Path) -> dict:
    """Load the lock JSON at *lock_path* and validate its internal integrity.

    Checks, in order:
    (a) the JSON parses at all (a corrupt file raises a clean ``ValueError``,
        never a raw ``json.JSONDecodeError``);
    (b) all of ``_REQUIRED_LOCK_KEYS`` are present;
    (c) ``schema_version`` matches the module's ``SCHEMA_VERSION`` exactly;
    (d) ``files`` is a list and ``file_hashes`` is a dict, and every element
        of ``files`` and every value of ``file_hashes`` is a ``str`` (a
        doctored lock with e.g. a non-string entry raises a clean
        ``ValueError`` here rather than a raw ``TypeError`` later);
    (e) ``files`` is a sorted, duplicate-free list and
        ``set(files) == set(file_hashes)``;
    (f) recomputing the aggregate hash from the lock's own ``files`` +
        ``file_hashes`` (using the same folding as ``_compute_manifest``)
        matches the recorded ``aggregate_hash``.

    Raises ``ValueError`` (never ``KeyError``/``JSONDecodeError``/``TypeError``)
    on any malformed or internally-inconsistent lock.
    """
    try:
        with open(lock_path, "r", encoding="utf-8") as fh:
            lock = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read mother model lock at {lock_path}: {exc}") from exc

    if not isinstance(lock, dict):
        raise ValueError(f"mother model lock at {lock_path} is not a JSON object")

    missing = [k for k in _REQUIRED_LOCK_KEYS if k not in lock]
    if missing:
        raise ValueError(
            f"mother model lock at {lock_path} is malformed: missing key(s) {missing!r}"
        )

    schema_version = lock["schema_version"]
    if schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"mother model lock at {lock_path} has incompatible schema_version "
            f"{schema_version!r}; expected {SCHEMA_VERSION!r}"
        )

    files = lock["files"]
    file_hashes = lock["file_hashes"]

    if not isinstance(files, list) or not isinstance(file_hashes, dict):
        raise ValueError(
            f"mother model lock at {lock_path} is malformed: "
            "'files' must be a list and 'file_hashes' must be an object"
        )

    if not all(isinstance(p, str) for p in files):
        raise ValueError(
            f"mother model lock at {lock_path} is malformed: "
            "'files' must be a list of strings"
        )
    if not all(isinstance(v, str) for v in file_hashes.values()):
        raise ValueError(
            f"mother model lock at {lock_path} is malformed: "
            "'file_hashes' values must all be strings"
        )

    if files != sorted(files):
        raise ValueError(f"mother model lock at {lock_path} is malformed: 'files' is not sorted")
    if len(files) != len(set(files)):
        raise ValueError(f"mother model lock at {lock_path} is malformed: 'files' has duplicates")
    if set(files) != set(file_hashes.keys()):
        raise ValueError(
            f"mother model lock at {lock_path} is malformed: "
            "'files' and 'file_hashes' keys do not match"
        )

    try:
        recomputed_aggregate = _fold_aggregate(files, file_hashes)
    except (AttributeError, TypeError) as exc:
        raise ValueError(
            f"mother model lock at {lock_path} is malformed: could not recompute aggregate hash: {exc}"
        ) from exc

    if recomputed_aggregate != lock["aggregate_hash"]:
        raise ValueError(
            "lock file is internally inconsistent (aggregate_hash mismatch / tampered): "
            f"{lock_path}"
        )

    return lock


def verify_mother_model_lock(workspace, lock_path=None) -> bool:
    """Verify that *workspace* exactly matches the lock at *lock_path*.

    Before comparing against the workspace, the lock file itself is validated
    for internal integrity (required keys present, ``files``/``file_hashes``
    consistent, and the recorded ``aggregate_hash`` matches a fresh fold of
    the lock's own contents) — see ``_load_and_validate_lock``. This catches
    malformed and tampered locks with a clean ``ValueError`` rather than
    silently trusting a doctored file or crashing with a raw ``KeyError``.

    Returns ``True`` when every locked file is present, unchanged, and no
    extra files exist. Raises ``ValueError`` naming the first (in sorted
    POSIX-path order) missing, extra, or content-mismatched file otherwise.
    """
    workspace = Path(workspace)
    lock_path = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH

    _require_existing_dir(workspace)

    lock = _load_and_validate_lock(lock_path)

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
