"""
case_artifact_lock — hash-verified lock for pinned MF6/DISV model-assembly
artifacts stored as .npz bundles.

Purpose: parallels `mother_model_lock` (reusing its sorted-(name, hash)-fold
idiom) but hashes numpy array CONTENTS rather than file bytes, because
``np.savez`` embeds per-member mtimes in the zip container that would make
raw file-byte hashing false-mismatch on a re-save of identical arrays.

Scope: this module is flopy/pyemu-free — stdlib + numpy only. It does not
know anything about MODFLOW6 file formats; it works on an arbitrary .npz of
named numpy arrays.

Manifest schema (JSON)
-----------------------
{
    "schema_version": "1.0",
    ... caller-supplied fields (e.g. "case_name", "step") ...,
    "members": ["<sorted array names>", ...],
    "array_hashes": {"<array name>": "<sha256 hex>", ...},
    "aggregate_hash": "<sha256 hex over the sorted (name, hash) pairs>"
}
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

SCHEMA_VERSION = "1.0"

_REQUIRED_MANIFEST_KEYS = ("schema_version", "members", "array_hashes", "aggregate_hash")


def _fold_aggregate(names, hashes) -> str:
    """Fold sorted (name, hash) pairs into a single sha256 hex digest.

    Byte-for-byte the same folding idiom as ``mother_model_lock._fold_aggregate``
    (duplicated rather than imported so this module stays stdlib+numpy-only
    and flopy/pyemu-free), so aggregate hashes computed here are directly
    comparable to that module's.

    *names* must already be sorted.
    """
    agg = hashlib.sha256()
    for name in names:
        agg.update(name.encode("utf-8", "surrogateescape"))
        agg.update(b"\x00")
        agg.update(hashes[name].encode("utf-8", "surrogateescape"))
        agg.update(b"\n")
    return agg.hexdigest()


def hash_array(array: np.ndarray) -> str:
    """Return the sha256 hex digest of an array's dtype, shape, and
    C-contiguous bytes.

    Hashing a C-contiguous byte view (rather than the array's raw buffer)
    means a non-contiguous view (e.g. a strided slice) and a contiguous copy
    with the same logical contents hash equal, while a shape change alone
    (same raw bytes, different shape) changes the hash.
    """
    array = np.ascontiguousarray(array)
    h = hashlib.sha256()
    h.update(str(array.dtype).encode("utf-8"))
    h.update(b"\x00")
    h.update(str(array.shape).encode("utf-8"))
    h.update(b"\x00")
    h.update(array.tobytes())
    return h.hexdigest()


def _load_npz_hashes(npz_path: Path) -> dict:
    """Return {member_name: hash_array(...)} for every array in *npz_path*."""
    with np.load(npz_path) as npz:
        return {name: hash_array(npz[name]) for name in npz.files}


def write_artifact_manifest(npz_path, caller_fields: dict, manifest_path=None) -> dict:
    """Compute a content-hash manifest for the arrays in *npz_path* and write
    it as JSON to *manifest_path*.

    Parameters
    ----------
    npz_path:
        Path to an ``.npz`` bundle of named numpy arrays.
    caller_fields:
        Free-form dict of caller-supplied fields (e.g. ``case_name``,
        ``step``) merged into the manifest. Must not define any of the
        reserved keys in ``_REQUIRED_MANIFEST_KEYS``.
    manifest_path:
        Where to write the manifest JSON. Defaults to a sibling of
        *npz_path* named ``<npz stem>.manifest.json``. The parent directory
        is created if it does not exist.

    Returns
    -------
    dict — the manifest contents that were written (same structure as the
    JSON file).

    Raises
    ------
    ValueError
        If *caller_fields* defines any reserved manifest key.
    """
    npz_path = Path(npz_path)
    reserved_clash = set(caller_fields) & set(_REQUIRED_MANIFEST_KEYS)
    if reserved_clash:
        raise ValueError(
            f"caller_fields must not define reserved manifest key(s): {sorted(reserved_clash)!r}"
        )

    manifest_path = (
        Path(manifest_path)
        if manifest_path is not None
        else npz_path.with_suffix("").with_suffix(".manifest.json")
    )

    array_hashes = _load_npz_hashes(npz_path)
    members = sorted(array_hashes)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        **caller_fields,
        "members": members,
        "array_hashes": array_hashes,
        "aggregate_hash": _fold_aggregate(members, array_hashes),
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")

    return manifest


def _load_and_validate_manifest(manifest_path: Path) -> dict:
    """Load the manifest JSON at *manifest_path* and validate its internal
    integrity.

    Raises ``ValueError`` (never ``JSONDecodeError``/``KeyError``/``TypeError``)
    on any malformed or internally-inconsistent manifest.
    """
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read artifact manifest at {manifest_path}: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ValueError(f"artifact manifest at {manifest_path} is not a JSON object")

    missing = [k for k in _REQUIRED_MANIFEST_KEYS if k not in manifest]
    if missing:
        raise ValueError(
            f"artifact manifest at {manifest_path} is malformed: missing key(s) {missing!r}"
        )

    schema_version = manifest["schema_version"]
    if schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"artifact manifest at {manifest_path} has incompatible schema_version "
            f"{schema_version!r}; expected {SCHEMA_VERSION!r}"
        )

    members = manifest["members"]
    array_hashes = manifest["array_hashes"]

    if not isinstance(members, list) or not isinstance(array_hashes, dict):
        raise ValueError(
            f"artifact manifest at {manifest_path} is malformed: "
            "'members' must be a list and 'array_hashes' must be an object"
        )
    if not all(isinstance(p, str) for p in members):
        raise ValueError(
            f"artifact manifest at {manifest_path} is malformed: "
            "'members' must be a list of strings"
        )
    if not all(isinstance(v, str) for v in array_hashes.values()):
        raise ValueError(
            f"artifact manifest at {manifest_path} is malformed: "
            "'array_hashes' values must all be strings"
        )

    if members != sorted(members):
        raise ValueError(f"artifact manifest at {manifest_path} is malformed: 'members' is not sorted")
    if len(members) != len(set(members)):
        raise ValueError(f"artifact manifest at {manifest_path} is malformed: 'members' has duplicates")
    if set(members) != set(array_hashes.keys()):
        raise ValueError(
            f"artifact manifest at {manifest_path} is malformed: "
            "'members' and 'array_hashes' keys do not match"
        )

    try:
        recomputed_aggregate = _fold_aggregate(members, array_hashes)
    except (AttributeError, TypeError) as exc:
        raise ValueError(
            f"artifact manifest at {manifest_path} is malformed: could not recompute aggregate hash: {exc}"
        ) from exc

    if recomputed_aggregate != manifest["aggregate_hash"]:
        raise ValueError(
            "artifact manifest is internally inconsistent (aggregate_hash mismatch / tampered): "
            f"{manifest_path}"
        )

    return manifest


def verify_artifact(npz_path, manifest_path) -> bool:
    """Verify that the arrays in *npz_path* exactly match the manifest at
    *manifest_path*.

    Before comparing against the .npz, the manifest itself is validated for
    internal integrity (required keys present, ``members``/``array_hashes``
    consistent, and the recorded ``aggregate_hash`` matches a fresh fold of
    the manifest's own contents) — see ``_load_and_validate_manifest``.

    Returns ``True`` when every locked member is present, content-unchanged,
    and no extra members exist. Raises ``ValueError`` naming the first (in
    sorted order) missing, extra, or content-mismatched member otherwise.
    """
    npz_path = Path(npz_path)
    manifest_path = Path(manifest_path)

    manifest = _load_and_validate_manifest(manifest_path)

    locked_members = manifest["members"]
    locked_hashes = manifest["array_hashes"]
    locked_set = set(locked_members)

    current_hashes = _load_npz_hashes(npz_path)
    current_set = set(current_hashes)

    # Deterministic order: walk the union of locked + current member names,
    # sorted, so the FIRST discrepancy encountered is reproducible.
    for name in sorted(locked_set | current_set):
        if name not in current_set:
            raise ValueError(
                f"artifact lock mismatch: missing member {name!r} (present in manifest, absent from .npz)"
            )
        if name not in locked_set:
            raise ValueError(
                f"artifact lock mismatch: extra member {name!r} (present in .npz, not in manifest)"
            )
        if current_hashes[name] != locked_hashes[name]:
            raise ValueError(f"artifact lock mismatch: content changed for member {name!r}")

    return True
