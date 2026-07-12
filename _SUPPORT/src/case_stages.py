"""
case_stages — real stage bodies for the case-study redesign validation
harness (``case_validation.py``).

This module wires the M2 pinned-artifact machinery (``model_io_utils``) into
the M1 instructor validation harness. It defines top-level stage functions
plus an explicit registration entry point; importing this module never
registers anything and never does heavy work (Triangle/Voronoi regeneration,
MODFLOW runs) -- callers must call the ``register_*`` function(s) themselves.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

import case_validation as cv
from model_io_utils import _FLOW_SPEC_REQUIRED_KEYS, load_flow_spec

# Env var pointing at the directory of instructor-provided
# ``group<N>_flow.npz`` / ``.manifest.json`` pinned artifact pairs. When
# unset, defaults to ``<default-data-folder>/pinned_meshes`` (same default
# used by ``model_io_utils.load_pinned_flow_model``).
AGM_MESHES_DIR_ENV_VAR = "AGM_MESHES_DIR"


def _resolve_meshes_dir() -> Path:
    """Resolve the pinned-meshes directory from ``AGM_MESHES_DIR``, falling
    back to a documented default when the env var is unset."""
    env_value = os.environ.get(AGM_MESHES_DIR_ENV_VAR)
    if env_value:
        return Path(env_value)

    from data_utils import get_default_data_folder

    return Path(get_default_data_folder()) / "pinned_meshes"


def flow_refinement_stage(group) -> None:
    """Validate the ``flow_refinement`` stage for *group*.

    Resolves the pinned-meshes directory from ``AGM_MESHES_DIR`` (documented
    default when unset), loads and hash-verifies
    ``<meshes_dir>/group<group>_flow.npz`` (+ sibling manifest) via
    :func:`model_io_utils.load_flow_spec`, and sanity-checks that the decoded
    spec has the expected keys. Runs no MODFLOW and triggers no
    Triangle/Voronoi/NearestND regeneration -- it only loads and verifies the
    pinned artifact.

    Returns
    -------
    None
        On success.

    Raises
    ------
    FileNotFoundError
        If the group's pinned ``.npz`` artifact does not exist.
    ValueError
        If the artifact fails manifest verification, or the decoded spec is
        missing expected keys.
    """
    meshes_dir = _resolve_meshes_dir()
    npz_path = meshes_dir / f"group{group}_flow.npz"
    manifest_path = npz_path.with_suffix("").with_suffix(".manifest.json")

    if not npz_path.exists():
        raise FileNotFoundError(
            f"Pinned flow spec for group{group} not found: {npz_path}\n"
            f"Ensure the instructor-provided mesh archive has been extracted "
            f"into {meshes_dir} (set {AGM_MESHES_DIR_ENV_VAR} to override)."
        )

    spec = load_flow_spec(npz_path, manifest_path, verify=True)

    missing = [k for k in _FLOW_SPEC_REQUIRED_KEYS if k not in spec]
    if missing:
        raise ValueError(
            f"group{group} flow spec decoded from {npz_path} is missing "
            f"expected key(s): {sorted(missing)!r}"
        )

    return None


def register_flow_stages() -> None:
    """Explicitly register the ``flow_refinement`` stage.

    Idempotent: safe to call more than once (re-registering the same
    function under the same stage id is a no-op in effect).
    """
    if "flow_refinement" not in cv.registered_stages():
        cv.register_stage("flow_refinement", flow_refinement_stage)
