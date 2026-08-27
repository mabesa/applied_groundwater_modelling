#!/usr/bin/env python3
"""
T0.0 canonical-default gate harness.

Implements DOCUMENTATION/contracts/T0_0_canonical_contract.md (v3):
  - Section 2    -- the frozen per-path TYPE schema (FLOAT/INT/BOOL/STR/
    ARRAY_FLOAT/ARRAY_INT/ARRAY_PAIR/MAPPING per field, derived once from the
    contract's own tables) and Section 4.3's None-in-a-numeric-field defect
    rule. Every payload leaf is validated against its declared class BEFORE
    normalisation; a type mismatch or a None where a numeric/bool class is
    declared aborts the gate with the offending path named -- it is a broken
    or altered run, not a payload difference to diff (mirrors the Section
    2.2 mass_balance abort precedent). This is what stops, e.g., a numeric
    string silently taking the place of a float and passing the gate.
  - Section 3    -- pre-authorised fields, schema-lifted (not excluded) on the
    reference side; side-aware schema validation (reference = frozen legacy
    schema exactly, candidate = frozen schema + pre-authorised fields exactly).
  - Section 4    -- the frozen field normalisation, including the ARRAY_PAIR
    ordering rule (Section 4.1/4.2) applied ONLY to the pre-authorised
    meta["sink_support_cells"] field.
  - Section 5.0  -- the harness (two worktrees, two fresh OS processes,
    asserted import roots, controlled cwd/config, hashed executables,
    pinned threading, hashed flow + GIS inputs).
  - Section 5.2  -- the comparison (exact string equality, field by field,
    every differing field reported with both values; full recorded
    environment fingerprint compared, not a subset).

This file is READ-ONLY with respect to the T1 modules it exercises
(transport_srcpulse_demo.py, model_io_utils.py, etc.) -- it only imports and
calls them, from inside worktrees the harness itself creates.

Three invocation modes:

  qualify  (orchestrator -- what a human runs before signature)
      uv run python _SUPPORT/src/scripts/t0_gate_harness.py qualify \\
          --workdir <scratch-dir> [--ref-commit b685f24] [--keep-worktrees]

      Creates two git worktrees at --ref-commit (default b685f24, the frozen
      reference), runs one side per worktree SEQUENTIALLY as a fresh child
      process, then compares the two canonical payloads per contract Section
      5.2. In qualification mode both worktrees are the SAME commit, so any
      reported difference is pure run-to-run nondeterminism (contract
      Section 5.1) -- not a code change. Both sides run the REFERENCE schema
      (the frozen legacy 29 fields) because b685f24 has none of the Section 3
      pre-authorised fields yet.

  compare  (orchestrator -- the actual T1 gate, Section 5.2)
      uv run python _SUPPORT/src/scripts/t0_gate_harness.py compare \\
          --workdir <scratch-dir> --candidate <commit-or-branch-or-worktree-path> \\
          [--ref-commit b685f24] [--keep-worktrees]

      Worktree A is always created fresh at --ref-commit and run under the
      REFERENCE schema. Worktree B is the candidate: if --candidate resolves
      to an existing directory it is used AS IS (assumed to already be a git
      worktree checked out at the commit/branch under test -- not created or
      removed by the harness); otherwise it is treated as a commit-ish and a
      fresh worktree is created for it, run under the CANDIDATE schema (the
      frozen 29 fields PLUS the Section 3 pre-authorised fields, and nothing
      else). The reference side's raw payload is schema-lifted per Section
      3.1/3.3 before comparison -- nothing is excluded.

  worker  (internal -- one per side, spawned by "qualify"/"compare"; not for
  direct use)
      <python> _SUPPORT/src/scripts/t0_gate_harness.py worker \\
          --worktree-root <path> --case-ws <path> --out <result.json> \\
          --side {reference,candidate}

      Runs entirely inside ONE worktree's import root: builds the canonical
      payload by calling build_srcpulse_demo() at its semantic defaults plus
      the two gate-only controls (force=True, a fresh case_ws), validates and
      normalises it per Sections 2-4 (schema depends on --side), and writes a
      JSON result record. When --side reference, the record additionally
      carries a "lifted_normalized_payload" (Section 3.1's schema-lift, using
      the identity defaults of Section 3, derived from THIS run's own values
      -- e.g. sink_support_cells' identity default is keyed off this run's
      own ext_cell and the imported module's own DOUBLET_Q, never a harness
      constant). A fatal SIGILL in the corridor-refinement retry (macOS
      arm64 / mf6 6.7.0, model_io_utils.py around line 2846) kills this
      process outright before it can write anything -- that is exactly why
      the orchestrator runs each side as its own OS process and detects a
      signal death from the child's return code.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Section 4 -- the frozen normalisation
# ---------------------------------------------------------------------------
SIGFIG_FLOAT = 12
FLOAT_FORMAT = "{:.11e}"  # 12 significant digits, one canonical exponent form

# 🔴 LECTURER DECISION 2026-08-27: the gate compares floats on a RELATIVE
# TOLERANCE, not exact string equality.
#
# FLOAT_FORMAT still normalises for STORAGE and hashing -- the recorded
# payload keeps its 12-digit canonical form. What changed is the COMPARISON:
# 12 significant digits tests solver noise, not the model. The concentrations
# this gate exists to protect carry ~3 significant digits of physical meaning,
# and a bit-level comparison on them was rejecting changes no student and no
# claim could ever see.
#
# 1e-5 was chosen over the physics-matching 1e-3 deliberately: it is 100x
# tighter than the physical resolution, so it still catches anything
# approaching a real change, while admitting the solver-tolerance fix that a
# 2 m mesh needs (which moves the peak 4.5e-06).
#
# ⚠️ Heads would tolerate 1e-3; this constant governs the CONCENTRATION
# payload, which is why it is tighter than the head criterion.
FLOAT_REL_TOL = 1e-5

# ---------------------------------------------------------------------------
# Section 2 -- the frozen REFERENCE payload schema: NAME -> normalisation
# CLASS, transcribed once from the contract's own tables (Section 2.1's
# top-level table, Section 2.2's "all FLOAT" mass_balance keys, Section 2.3's
# meta table, Section 2.4's locked table). This dict pair is the SOLE place
# a field name is mapped to a type -- every keyset tuple used elsewhere in
# this file (TOP_LEVEL_FIELDS, MASS_BALANCE_KEYS, META_KEYS, LOCKED_KEYS) is
# DERIVED from it (`tuple(..._TYPES.keys())`), never hand-duplicated, so a
# keyset and its types cannot drift apart. See path_type_schema() below for
# how this combines with PRE_AUTHORIZED_FIELDS's own "class" entries into one
# path -> class lookup used by validate_types().
# ---------------------------------------------------------------------------
TOP_LEVEL_TYPES = {
    "times": "ARRAY_FLOAT",
    "breakthrough": "ARRAY_FLOAT",
    "peak_mgL": "FLOAT",
    "arrival_day": "FLOAT",
    "mass_balance": "MAPPING",
    "solubility_ok": "BOOL",
    "emergent_C_mgL": "FLOAT",
    "solubility_mgL": "FLOAT",
    "solubility_margin": "FLOAT",
    "PeL_min": "FLOAT",
    "PeL_max": "FLOAT",
    "PeT_min": "FLOAT",
    "PeT_max": "FLOAT",
    "mass_g": "FLOAT",
    "pulse_days": "FLOAT",
    "total_days": "FLOAT",
    "smassrate_gpd": "FLOAT",
    "src_cells": "ARRAY_INT",
    "ext_cell": "INT",
    "inj_cell": "INT",
    "spill_xy": "ARRAY_FLOAT",
    "alpha_L": "FLOAT",
    "alpha_T": "FLOAT",
    "R": "FLOAT",
    "rho_b": "FLOAT",
    "Kd": "FLOAT",
    "lam": "FLOAT",
    "meta": "MAPPING",
    "locked": "MAPPING",
}
MASS_BALANCE_TYPES = {
    "src_in_g": "FLOAT",
    "well_out_g": "FLOAT",
    "boundary_out_g": "FLOAT",
    "storage_g": "FLOAT",
    "decay_g": "FLOAT",
    "total_in_g": "FLOAT",
    "total_out_g": "FLOAT",
    "pct_imbalance": "FLOAT",
    "grouped_residual_g": "FLOAT",
}
META_TYPES = {
    "ncpl": "INT",
    "nstp": "INT",
    "dt": "FLOAT",
    "Cr": "FLOAT",
    "n_src": "INT",
    "q_src_darcy": "FLOAT",
    "b_src": "FLOAT",
    "ds_src": "FLOAT",
    "q_cell": "FLOAT",
    "v_bind": "FLOAT",
    "ds_bind": "FLOAT",
    "ds_true_min": "FLOAT",
    "courant_floor": "FLOAT",
    "refine_radius_used": "FLOAT",
    "u_reg": "ARRAY_FLOAT",
    "cr_capped": "BOOL",
    "peak_at_last_step": "BOOL",
}
LOCKED_TYPES = {
    "alh": "FLOAT",
    "ath1": "FLOAT",
    "diffc": "FLOAT",
    "porosity": "FLOAT",
    "scheme": "STR",
    "xt3d_off": "BOOL",
    "refined_cell_size": "FLOAT",
    "base_cell_size": "FLOAT",
    "time_units": "STR",
}

# Keyset tuples, DERIVED (never hand-duplicated) from the type dicts above --
# every other place in this file that needs "just the names" (build_payload's
# set comparisons, the test module's synthetic dataclasses) uses these.
TOP_LEVEL_FIELDS = tuple(TOP_LEVEL_TYPES.keys())
MASS_BALANCE_KEYS = tuple(MASS_BALANCE_TYPES.keys())
META_KEYS = tuple(META_TYPES.keys())
LOCKED_KEYS = tuple(LOCKED_TYPES.keys())

# ---------------------------------------------------------------------------
# Section 3 -- pre-authorised fields, as a single table.
#
# Adding a future pre-authorised field (Section 3.1's closing sentence, and
# Section 3's own "field may be added to this table only ... with lecturer
# approval") is meant to be a ONE-LINE change here: everything else --
# CANDIDATE_TOP_LEVEL_FIELDS / CANDIDATE_META_KEYS, the ARRAY_PAIR ordering
# path set, and the reference schema-lift -- is derived from this table, not
# hand-duplicated.
#
# "identity_default" is called as identity_default(payload, constants) where
# `payload` is the (possibly partially-lifted) RAW reference payload built so
# far (native Python/numpy types, not yet normalised) and `constants` is a
# dict of values read directly off the reference run's OWN imported module
# (never a harness-side hardcoded physics constant -- Section 3.1's "the
# identity default is ... what the reference run actually did" / "can be
# independently verified from the reference run").
# ---------------------------------------------------------------------------
PRE_AUTHORIZED_FIELDS = (
    {
        # Section 3: sink_support_m -- identity default 0.0 (today's
        # behaviour: the whole pumping rate on the single nearest-centroid
        # cell). A static default, independent of the run.
        "path": ("sink_support_m",),
        "class": "FLOAT",
        "identity_default": lambda payload, constants: 0.0,
    },
    {
        # Section 3: meta["sink_support_cells"] -- identity default
        # [(ext_cell, -abs(DOUBLET_Q))], i.e. the apportionment the
        # single-cell construction ACTUALLY applies today. NOT [] -- an
        # empty list would misrepresent today's behaviour (Section 3, codex
        # r1 #3). ext_cell and DOUBLET_Q are both read off THIS reference
        # run, not hardcoded in the harness.
        "path": ("meta", "sink_support_cells"),
        "class": "ARRAY_PAIR",
        "identity_default": lambda payload, constants: [
            (int(payload["ext_cell"]), -abs(float(constants["DOUBLET_Q"])))
        ],
    },
    {
        # Section 3.3: t_peak -- the arrival_day -> t_peak rename, retained
        # as a compatibility alias. Identity default = this run's own
        # arrival_day value (Section 3.1's schema-lift for the rename).
        "path": ("t_peak",),
        "class": "FLOAT",
        "identity_default": lambda payload, constants: float(payload["arrival_day"]),
    },
)

# Derived, not hand-duplicated (see docstring above).
_PRE_AUTH_TOP_LEVEL_NAMES = tuple(
    spec["path"][0] for spec in PRE_AUTHORIZED_FIELDS if len(spec["path"]) == 1
)
_PRE_AUTH_META_NAMES = tuple(
    spec["path"][1] for spec in PRE_AUTHORIZED_FIELDS
    if len(spec["path"]) == 2 and spec["path"][0] == "meta"
)
if any(len(spec["path"]) not in (1, 2) or
       (len(spec["path"]) == 2 and spec["path"][0] != "meta")
       for spec in PRE_AUTHORIZED_FIELDS):
    raise AssertionError(
        "PRE_AUTHORIZED_FIELDS: every entry must be a top-level field "
        "(path length 1) or nested under 'meta' (path ('meta', ...)) -- "
        "Section 3 defines no other nesting today."
    )

# Section 5.2 step 2 / build_payload(side="candidate"): the candidate schema
# is the frozen legacy schema PLUS exactly the pre-authorised fields, and
# nothing else (contract Section 3.1 point 2: "the candidate payload MUST
# contain the field").
CANDIDATE_TOP_LEVEL_FIELDS = TOP_LEVEL_FIELDS + _PRE_AUTH_TOP_LEVEL_NAMES
CANDIDATE_META_KEYS = META_KEYS + _PRE_AUTH_META_NAMES

# Section 4.1: ARRAY_PAIR is "sorted by the leading INT" -- and Section 4.2
# is explicit that this sort applies to meta["sink_support_cells"] ALONE;
# every other array (times, breakthrough, src_cells, u_reg, ...) keeps its
# produced order. Path-aware: normalize() below only sorts a container whose
# path is in this set.
ARRAY_PAIR_PATHS = frozenset(
    spec["path"] for spec in PRE_AUTHORIZED_FIELDS if spec["class"] == "ARRAY_PAIR"
)

# Fields NOT in the payload (Section 4.4) -- recorded alongside for
# provenance only, never compared: wall-clock timings, workspace paths,
# hostnames. (The environment fingerprint itself IS compared -- Section 5.0 /
# 5.2 step 1 -- just not folded into the payload.)


class GateAbort(RuntimeError):
    """mass_balance carried the 'error' sentinel or a non-conforming keyset
    (contract Section 2.2); the top-level/nested field set did not match the
    schema for this side (Section 2.5 / Section 3.1); or a payload leaf did
    not match its declared normalisation class, including a None where a
    numeric (FLOAT/INT) or BOOL class is declared (Section 2 / Section 4.3
    -- validate_types() below). A broken run, a schema violation or a type
    defect -- never a payload difference -- do not compare, do not
    normalise, do not record a canonical result."""


# ---------------------------------------------------------------------------
# Section 2 / 4.3 -- the per-path TYPE schema and its validator.
#
# The keyset checks in build_payload() (below) only assert that the right
# NAMES are present -- they say nothing about what TYPE lives behind each
# name. That is the hole a codex review found: replacing peak_mgL with a
# numeric string, or arrival_day with an int, or emergent_C_mgL with None,
# produced ZERO differences, because normalize() coerces almost anything to
# a string and nothing upstream of it ever checked the Python type. A type
# change is a broken-or-altered run (a different code path silently produced
# a different kind of value), not a payload difference to diff -- so, like
# Section 2.2's mass_balance "error" key, it is a gate ABORT, not a mismatch
# to report.
#
# path_type_schema() combines TOP_LEVEL_TYPES / MASS_BALANCE_TYPES /
# META_TYPES / LOCKED_TYPES (the single source of truth above) with
# PRE_AUTHORIZED_FIELDS's own "class" entries (Section 3) into ONE
# path-tuple -> class lookup, side-aware exactly like build_payload()'s own
# keyset logic (the pre-authorised paths only exist on the candidate side).
# ---------------------------------------------------------------------------

# Section 4.3: "None ... in a numeric field is a DEFECT, not a value" is
# stated for numeric fields; this harness applies the same hard-abort rule
# to BOOL for the same reason (a None boolean is exactly as meaningless as a
# None float -- there is no third truth value in this schema). No field in
# Section 2/2.2/2.3/2.4/3 is declared to permit an absent value, so in
# practice None aborts for EVERY class here (STR/ARRAY_*/MAPPING included,
# via the generic type-mismatch branch in _check_leaf_or_container) -- this
# set only controls which of the two GateAbort MESSAGES is used, citing
# Section 4.3 by name for the numeric/bool case the contract calls out
# explicitly.
NUMERIC_OR_BOOL_CLASSES = frozenset(("FLOAT", "INT", "BOOL"))

# Section 4.1: the element class inside each array class.
_ARRAY_ELEMENT_CLASS = {"ARRAY_FLOAT": "FLOAT", "ARRAY_INT": "INT"}


def path_type_schema(side: str) -> dict:
    """Section 2's typed schema, keyed by path tuple (matching the `path`
    argument threaded through normalize()): {("peak_mgL",): "FLOAT",
    ("mass_balance", "src_in_g"): "FLOAT", ("meta", "ncpl"): "INT", ...}.
    `side` controls whether the Section 3 pre-authorised paths
    (sink_support_m, meta.sink_support_cells, t_peak) are included --
    candidate only, mirroring build_payload()'s existing side-aware keyset
    logic (Section 3.1: those fields do not exist on the reference side).
    """
    schema = {}
    for name, cls in TOP_LEVEL_TYPES.items():
        schema[(name,)] = cls
    for name, cls in MASS_BALANCE_TYPES.items():
        schema[("mass_balance", name)] = cls
    for name, cls in META_TYPES.items():
        schema[("meta", name)] = cls
    for name, cls in LOCKED_TYPES.items():
        schema[("locked", name)] = cls
    if side == "candidate":
        for spec in PRE_AUTHORIZED_FIELDS:
            schema[spec["path"]] = spec["class"]
    return schema


def _is_scalar_class_match(value, cls: str) -> bool:
    """FLOAT/INT/BOOL/STR leaf check. Deliberately excludes numpy/py bool
    from FLOAT and INT (bool is a Python int subclass, so `isinstance(True,
    int)` is True -- without the exclusion a stray bool would silently pass
    as an INT) and requires the exact declared class, never a coercible
    look-alike (this is the check the numeric-string hole needed: a str is
    never a FLOAT/INT no matter what it parses as)."""
    import numpy as np

    if cls == "FLOAT":
        return isinstance(value, (float, np.floating)) and not isinstance(value, (bool, np.bool_))
    if cls == "INT":
        return isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_))
    if cls == "BOOL":
        return isinstance(value, (bool, np.bool_))
    if cls == "STR":
        return isinstance(value, str)
    raise ValueError(f"_is_scalar_class_match: not a scalar class: {cls!r}")


def _fmt_path(path: tuple) -> str:
    """Human-readable path for a GateAbort message: dict keys joined by
    '.', list indices attached without an extra dot -- "meta.dt" /
    "times[1]" / "meta.sink_support_cells[0][1]", matching _diff_normalized
    ()'s own path style."""
    out = ""
    for p in path:
        s = str(p)
        if s.startswith("["):
            out += s
        elif out:
            out += "." + s
        else:
            out = s
    return out


def _check_leaf_or_container(value, cls: str, path: tuple) -> None:
    """Recursive worker for validate_types(): checks one (value, declared
    class) pair, raising GateAbort by NAMED PATH on any mismatch -- the type
    analogue of build_payload()'s keyset-mismatch abort."""
    import numpy as np

    dotted = _fmt_path(path)

    if cls == "MAPPING":
        if not isinstance(value, dict):
            raise GateAbort(
                f"type defect at {dotted!r}: declared MAPPING, got "
                f"{type(value).__name__} ({value!r})"
            )
        return

    if value is None:
        if cls in NUMERIC_OR_BOOL_CLASSES:
            raise GateAbort(
                f"type defect at {dotted!r}: None in a {cls} field -- Section 4.3: "
                f"'None ... in a numeric field is a DEFECT, not a value'; this harness "
                f"applies the same rule to BOOL. Gate ABORTS, it does not compare or "
                f"normalise this run."
            )
        raise GateAbort(
            f"type defect at {dotted!r}: None where {cls} is declared -- no field in "
            f"this schema is declared to permit an absent value (Section 4.3)."
        )

    if cls in ("FLOAT", "INT", "BOOL", "STR"):
        if not _is_scalar_class_match(value, cls):
            raise GateAbort(
                f"type defect at {dotted!r}: declared {cls}, got "
                f"{type(value).__name__} ({value!r})"
            )
        return

    if cls in ("ARRAY_FLOAT", "ARRAY_INT", "ARRAY_PAIR"):
        if not isinstance(value, (list, tuple, np.ndarray)):
            raise GateAbort(
                f"type defect at {dotted!r}: declared {cls}, got "
                f"{type(value).__name__} ({value!r})"
            )
        items = list(value)
        if cls == "ARRAY_PAIR":
            for i, item in enumerate(items):
                if not isinstance(item, (list, tuple, np.ndarray)) or len(item) != 2:
                    raise GateAbort(
                        f"type defect at {dotted!r}[{i}]: ARRAY_PAIR element must be a "
                        f"two-element (INT, FLOAT) pair, got {item!r}"
                    )
                a, b = item
                _check_leaf_or_container(a, "INT", path + (f"[{i}][0]",))
                _check_leaf_or_container(b, "FLOAT", path + (f"[{i}][1]",))
        else:
            elem_cls = _ARRAY_ELEMENT_CLASS[cls]
            for i, item in enumerate(items):
                _check_leaf_or_container(item, elem_cls, path + (f"[{i}]",))
        return

    raise ValueError(f"validate_types: unknown normalisation class {cls!r} at {dotted!r}")


def validate_types(payload: dict, side: str) -> None:
    """Section 2 / 4.3: every payload leaf must match its declared
    normalisation class BEFORE normalize() ever runs (Section 2.2's
    mass_balance abort is the precedent this generalises: a broken or
    altered run is not a payload difference to diff). Called by
    build_payload() immediately after its keyset checks, so nothing that
    reaches normalize() in the real gate pipeline can carry a type defect --
    a numeric string standing in for a float, an int standing in for a
    bool, or a None anywhere in a numeric/bool field all raise GateAbort
    here, with the offending path named, instead of silently passing
    through as a rendered string.

    Only scalar leaves and array elements are checked directly; the
    mass_balance/meta/locked keysets themselves are already asserted exact
    by build_payload() before this runs, so `MAPPING` here only confirms
    each container really is a dict before validate_types descends into it.
    """
    schema = path_type_schema(side)
    for path, cls in schema.items():
        cur = payload
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                raise GateAbort(
                    f"type validation: path {'.'.join(path)!r} not found while checking "
                    f"declared class {cls} (schema/keyset mismatch should have aborted "
                    f"already -- see build_payload())"
                )
            cur = cur[key]
        _check_leaf_or_container(cur, cls, path)


def _ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Section 4.1 / 4.3 -- per-class formatting
# ---------------------------------------------------------------------------
def _format_float(x: float) -> str:
    x = float(x)
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0.0:
        x = 0.0  # Section 4.3: -0.0 normalised to 0.0 BEFORE formatting
    return FLOAT_FORMAT.format(x)


def normalize(value, path: tuple = ()):
    """Section 4: recursive normaliser, one formatter applied everywhere.

    Every leaf becomes a canonical string (FLOAT_FORMAT for floats, plain
    decimal for ints, "true"/"false" for bools, NFC text for strings).
    Mapping keys are sorted lexicographically at every depth (Section 4.2).

    Array/list/tuple/ndarray element order is PATH-AWARE (Section 4.2):
    preserved for every array (times/breakthrough are time series and must
    never be sorted) EXCEPT a container whose `path` is in ARRAY_PAIR_PATHS
    (today: only meta["sink_support_cells"], Section 3/4.1), which is sorted
    by the leading INT of each [INT, FLOAT] pair and formatted as such.

    `path` is a tuple of the dict keys traversed to reach `value`, e.g.
    normalize(payload) -> normalize(payload["meta"], path=("meta",)) ->
    normalize(payload["meta"]["sink_support_cells"], path=("meta",
    "sink_support_cells")).
    """
    import numpy as np

    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if value is None:
        # Section 4.3's canonical form for a None the SCHEMA permits to be
        # absent -- no field in this payload's Section 2/2.2/2.3/2.4/3
        # schema is such a field, so in the real gate pipeline
        # validate_types() (called from build_payload(), before this
        # function ever runs) has already raised GateAbort on a None in a
        # numeric/bool field, and on a None anywhere else too, per Section
        # 4.3: "None ... in a numeric field is a DEFECT, not a value." This
        # branch is normalize()'s own low-level formatting rule, kept for
        # the day a field IS declared to permit absence, and for the string
        # form itself, "null" -- it is not, on its own, the gate's
        # None-is-a-defect enforcement.
        return "null"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return _format_float(float(value))
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {
            str(k): normalize(value[k], path + (str(k),))
            for k in sorted(value.keys(), key=str)
        }
    if isinstance(value, (list, tuple, np.ndarray)):
        items = list(value)
        if path in ARRAY_PAIR_PATHS:
            # Section 3 / 4.1: ARRAY_PAIR -- list of two-element [INT, FLOAT]
            # lists, sorted by the leading INT. The ONE array field that is
            # sorted; see the docstring above.
            def _leading_int(pair):
                a, _b = pair
                return int(a)

            return [
                [normalize(int(a), path), normalize(float(b), path)]
                for a, b in sorted(items, key=_leading_int)
            ]
        return [normalize(v, path) for v in items]
    raise TypeError(f"normalize(): unhandled type {type(value)!r} for value {value!r}")


# ---------------------------------------------------------------------------
# Section 3.1 -- the reference schema-lift
# ---------------------------------------------------------------------------
def lift_reference(raw_payload: dict, constants: dict) -> dict:
    """Section 3.1: lift the b685f24 reference payload into the frozen
    (legacy + pre-authorised) schema by adding each Section 3 field at its
    identity-default value, computed from THIS reference run's own values
    (never a harness-side hardcoded default). Returns a NEW raw (not yet
    normalised) payload dict; the caller normalises it with normalize(),
    which is what applies the ARRAY_PAIR ordering to the lifted
    sink_support_cells exactly as it would for a real candidate.

    Nothing is excluded afterwards (Section 3.1 point 3/4) -- the caller
    compares the lifted+normalised reference against the candidate's
    normalised payload field-for-field, including the lifted fields.
    """
    lifted = dict(raw_payload)
    lifted["meta"] = dict(raw_payload["meta"])
    for spec in PRE_AUTHORIZED_FIELDS:
        value = spec["identity_default"](lifted, constants)
        cur = lifted
        for key in spec["path"][:-1]:
            cur = cur[key]
        cur[spec["path"][-1]] = value
    return lifted


# ---------------------------------------------------------------------------
# Section 2 / 3 -- payload construction BY REFLECTION over SrcPulseDemo,
# schema validated per SIDE (Section 3.1: reference = frozen legacy schema
# exactly; candidate = frozen schema + pre-authorised fields exactly).
# ---------------------------------------------------------------------------
def build_payload(result, side: str) -> dict:
    """Reflect over every non-underscore field of the SrcPulseDemo dataclass
    instance (Section 2), assert the reflected field set matches the schema
    for `side` (Section 2.5 for the reference side: exactly the frozen 29;
    Section 3.1 for the candidate side: the frozen 29 PLUS exactly the
    pre-authorised fields -- an extra field on EITHER side is still a
    failure edge to T0, it is not merely "allowed to differ"), then assert
    the nested keysets (Section 2.2b): mass_balance (9, unaffected by
    Section 3), meta (17 on the reference side / 17 + len(pre-auth meta
    fields) on the candidate side), locked (9, unaffected). Finally, and
    only once every keyset is confirmed exact, validates every leaf's TYPE
    against the Section 2 schema (validate_types(), above) -- a numeric
    string, an int masquerading as a bool, or a None in a numeric/bool
    field aborts here too, by named path, before this function ever
    returns a payload for normalize() to see.

    Raises GateAbort per Section 2.2 if mass_balance carries the "error"
    sentinel key or any non-conforming keyset, or per Section 2/4.3 if any
    leaf's type does not match its declared class -- these are broken runs
    or type defects, not payload differences, and the gate must not
    compare/normalise/record them.
    """
    if side not in ("reference", "candidate"):
        raise ValueError(f"build_payload: side must be 'reference' or 'candidate', got {side!r}")

    expected_top = set(TOP_LEVEL_FIELDS if side == "reference" else CANDIDATE_TOP_LEVEL_FIELDS)
    expected_meta = set(META_KEYS if side == "reference" else CANDIDATE_META_KEYS)

    names = tuple(f.name for f in dataclasses.fields(result) if not f.name.startswith("_"))
    if set(names) != expected_top:
        missing = sorted(expected_top - set(names))
        extra = sorted(set(names) - expected_top)
        raise GateAbort(
            f"top-level payload field set changed for side={side!r} "
            f"(Section 2.5 / 3.1): missing={missing} extra={extra}"
        )

    payload = {name: getattr(result, name) for name in names}

    mb = payload["mass_balance"]
    if "error" in mb or set(mb.keys()) != set(MASS_BALANCE_KEYS):
        raise GateAbort(
            f"mass_balance abort (Section 2.2): keys={sorted(mb.keys())}"
            + (f" error={mb.get('error')!r}" if "error" in mb else "")
        )

    meta = payload["meta"]
    if set(meta.keys()) != expected_meta:
        raise GateAbort(
            f"meta keyset changed for side={side!r} (Section 2.2b / 3.1): "
            f"keys={sorted(meta.keys())} expected={sorted(expected_meta)}"
        )

    locked = payload["locked"]
    if set(locked.keys()) != set(LOCKED_KEYS):
        raise GateAbort(f"locked keyset changed (Section 2.2b): keys={sorted(locked.keys())}")

    # Section 2 / 4.3: keysets are exact -- now validate every leaf's TYPE.
    # This must run AFTER the keyset checks (a missing/extra key is its own,
    # more specific abort) and BEFORE any caller normalises the payload.
    validate_types(payload, side=side)

    return payload


# ---------------------------------------------------------------------------
# small utilities shared by worker + orchestrator
# ---------------------------------------------------------------------------
def _sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit(worktree_root) -> str:
    r = subprocess.run(
        ["git", "-C", str(worktree_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return r.stdout.strip()


# ---------------------------------------------------------------------------
# Path sanitisation for anything that reaches a COMMITTED report.
#
# This repo ships as public open educational material -- a committed T0.0
# report must never disclose the operator's home-directory layout, installed
# applications or local toolchain. That is provenance noise, not contract
# identity: the identity that matters is a SHA-256 (of a binary or of this
# harness file) or a commit hash, both of which travel unchanged regardless
# of where anything happens to be checked out. Everything below is applied
# at the point each field is CONSTRUCTED (run_worker's env_fp, _run_side's
# log header, _harness_identity) -- never as a later pass over an
# already-written report, so a committed report is authentic tool output,
# not tool output plus redaction.
# ---------------------------------------------------------------------------
def _home_relative(path) -> str:
    """Render an absolute path under the operator's home directory as
    '~/...'. A path NOT under home (e.g. a scratch/worktree dir under
    /private/tmp/... or /tmp/...) is returned unchanged -- it does not
    disclose the home-directory layout in the first place."""
    p = str(path)
    home = str(Path.home())
    if not home or home == os.sep:
        return p
    if p == home:
        return "~"
    if p.startswith(home + os.sep):
        return "~" + p[len(home):]
    return p


def _relative_to(path, base) -> str:
    """Best-effort path relative to `base` (e.g. a file inside a worktree,
    rendered relative to that worktree's root); falls back to
    _home_relative() if `path` is not actually under `base`."""
    try:
        return str(Path(path).resolve().relative_to(Path(base).resolve()))
    except ValueError:
        return _home_relative(path)


_LEAK_PREFIXES = ("/Users/", "/home/", "C:\\")


def _looks_like_path_list(s: str) -> bool:
    """A `PATH`-shaped value: several os.pathsep-joined, path-looking
    segments. Section 5.0's `flopy_bindir_prepended` boolean (below) is the
    one PATH-related fact this harness actually depends on -- the full
    value is never contract-relevant and must never reach a report."""
    if os.pathsep not in s:
        return False
    parts = s.split(os.pathsep)
    return len(parts) >= 4 and sum(1 for p in parts if p.startswith(("/", "~/"))) >= 4


def scan_for_leaked_paths(obj, path: str = "") -> list:
    """Recursively scan a JSON-shaped structure (the kind run_qualification
    / run_compare are about to write to disk) for any string that discloses
    an absolute host path or a raw PATH-like value. Returns a list of
    (json_path, value) violations -- empty means clean. Used both as a
    pytest regression guard (against synthetic old- and new-format data)
    and as a hard gate in the orchestrator itself (see run_qualification /
    run_compare): the harness refuses to WRITE a report a scan flags,
    rather than trusting the sanitisation at each call site to have been
    complete."""
    violations = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            violations.extend(scan_for_leaked_paths(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            violations.extend(scan_for_leaked_paths(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        if any(obj.startswith(pfx) or pfx in obj for pfx in _LEAK_PREFIXES):
            violations.append((path, obj))
        elif _looks_like_path_list(obj):
            violations.append((path, obj))
    return violations


def _assert_no_leaked_paths(report: dict, report_label: str) -> None:
    leaks = scan_for_leaked_paths(report)
    if leaks:
        shown = "\n".join(f"  {p}: {v!r}" for p, v in leaks[:10])
        raise SystemExit(
            f"REFUSING to write {report_label}: {len(leaks)} leaked absolute path(s) / "
            f"PATH-like value(s) found (public-repo evidence must carry none):\n{shown}"
        )


def _tail(path, n=80) -> str:
    """Section 4.4-adjacent: log_tail is captured subprocess output
    (data_utils/FloPy/MF6 console text), not something this harness
    constructs field-by-field -- so it is sanitised as text here, at the
    one place it is read for inclusion in a record, rather than trusting
    every print statement upstream never to mention an absolute path."""
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except Exception as e:
        return f"(could not read log: {e})"
    text = "\n".join(lines[-n:])
    home = str(Path.home())
    if home and home != os.sep:
        text = text.replace(home, "~")
    return text


def _harness_identity(repo_root: Path, this_file: str) -> dict:
    """A report can otherwise be silently mismatched to the code that
    produced it -- e.g. this hardening pass itself, where the preserved
    §5.1 evidence was produced by a PRE-hardening copy of this file and no
    longer matched what the code emits. Every report records the SHA-256 of
    THIS harness script (the single copy that ran both sides -- see
    `this_file` in run_qualification/run_compare, always the orchestrator's
    own `__file__`, never a per-worktree copy, because the harness is the
    test rig and is not itself under T1's freeze) plus the commit of the
    repo it was invoked from, so a stale report is detectable by inspection
    rather than by re-deriving trust from memory.

    The path is recorded REPO-RELATIVE, never absolute: the commit hash
    already identifies the tree this file lives in, so `harness_repo_root`
    (an absolute path) is dropped rather than recorded and redacted."""
    return {
        "t0_gate_harness_py_sha256": _sha256_file(this_file),
        "t0_gate_harness_py_path": _relative_to(this_file, repo_root),
        "harness_repo_commit": _git_commit(repo_root),
    }


# ===========================================================================
# WORKER -- runs entirely inside ONE worktree's import root, one OS process
# ===========================================================================
def run_worker(args) -> None:
    worktree_root = Path(args.worktree_root).resolve()
    case_ws = Path(args.case_ws)
    out_path = Path(args.out)
    side = args.side

    record = {"status": "ERROR", "error": "worker did not complete"}
    try:
        # ---- Section 1.2: cold-workspace policy -- case_ws must be fresh ----
        if case_ws.exists():
            raise RuntimeError(
                f"case_ws already exists (must be a fresh, previously "
                f"non-existent directory per Section 1.2): {case_ws}"
            )

        # ---- Section 5.0: controlled cwd, BEFORE any import that walks it ----
        os.chdir(worktree_root)

        # ---- Section 5.0: asserted import roots -- worktree's own _SUPPORT/src
        # must be found BEFORE anything else on sys.path.
        src_dir = str(worktree_root / "_SUPPORT" / "src")
        sys.path.insert(0, src_dir)

        import numpy as np
        import flopy
        import transport_srcpulse_demo as tsd
        import model_io_utils as mio

        def _resolve(p):
            return str(Path(p).resolve())

        def _in_worktree(p):
            rp = _resolve(p)
            wt = str(worktree_root)
            return rp == wt or rp.startswith(wt + os.sep)

        if not _in_worktree(tsd.__file__):
            raise RuntimeError(
                f"transport_srcpulse_demo imported from OUTSIDE its own worktree "
                f"(stale sys.path?): {tsd.__file__} not under {worktree_root}"
            )
        if not _in_worktree(mio.__file__):
            raise RuntimeError(
                f"model_io_utils imported from OUTSIDE its own worktree "
                f"(stale sys.path?): {mio.__file__} not under {worktree_root}"
            )

        import data_utils

        data_folder = data_utils.get_default_data_folder()

        # ---- Section 5.0: absolute, hashed executables ----
        mf6_exe = shutil.which("mf6") or os.path.expanduser("~/.local/share/flopy/bin/mf6")
        tri_exe = shutil.which("triangle") or os.path.expanduser(
            "~/.local/share/flopy/bin/triangle"
        )
        if not os.path.isfile(mf6_exe):
            raise RuntimeError(f"mf6 executable not found (resolved to {mf6_exe!r})")
        if not os.path.isfile(tri_exe):
            raise RuntimeError(f"triangle executable not found (resolved to {tri_exe!r})")
        mf6_real = os.path.realpath(mf6_exe)
        tri_real = os.path.realpath(tri_exe)
        mf6_sha = _sha256_file(mf6_real)
        tri_sha = _sha256_file(tri_real)

        # ---- Section 1.1 / 5.0: flow + GIS fingerprints ----
        flow_fp = mio.calibrated_flow_fingerprint()
        boundary_path = data_utils.download_named_file(name="model_boundary", data_type="gis")
        rivers_path = data_utils.download_named_file(name="rivers", data_type="gis")
        boundary_sha = _sha256_file(boundary_path)
        rivers_sha = _sha256_file(rivers_path)

        # Section 5.0's ONE contract-relevant PATH fact: triangle has no
        # exe_name fallback (unlike mf6, §5.0), so it resolves via
        # shutil.which("triangle") only because the harness prepended the
        # flopy bin dir. That is the fact worth recording -- the full PATH
        # value is operator machine layout, never contract-relevant, and
        # must never reach a committed report (see scan_for_leaked_paths).
        _path_entries = (os.environ.get("PATH") or "").split(os.pathsep)
        flopy_bindir_prepended = bool(_path_entries) and _path_entries[0] == os.path.expanduser(
            "~/.local/share/flopy/bin"
        )

        env_fp = {
            "os": platform.platform(),
            "machine": platform.machine(),
            "python_version": sys.version,
            "python_executable": _home_relative(os.path.realpath(sys.executable)),
            "flopy_version": getattr(flopy, "__version__", "unknown"),
            "numpy_version": getattr(np, "__version__", "unknown"),
            # Binaries: the SHA-256 is the identity the contract compares
            # (Section 5.0); the absolute location is noise and is dropped,
            # not merely redacted -- only the basename is kept.
            "mf6_basename": os.path.basename(mf6_real),
            "mf6_sha256": mf6_sha,
            "triangle_basename": os.path.basename(tri_real),
            "triangle_sha256": tri_sha,
            "data_folder": _home_relative(data_folder),
            "flow_fingerprint": flow_fp,
            "model_boundary_path": _home_relative(boundary_path),
            "model_boundary_sha256": boundary_sha,
            "rivers_path": _home_relative(rivers_path),
            "rivers_sha256": rivers_sha,
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "GDAL_NUM_THREADS": os.environ.get("GDAL_NUM_THREADS"),
            "flopy_bindir_prepended": flopy_bindir_prepended,
            "worktree_root": _home_relative(str(worktree_root)),
            "worktree_commit": _git_commit(worktree_root),
            "case_ws": _home_relative(str(case_ws)),
            "transport_srcpulse_demo_file": _relative_to(tsd.__file__, worktree_root),
            "model_io_utils_file": _relative_to(mio.__file__, worktree_root),
        }

        # ---- Section 1: the exact invocation -- semantic defaults + the two
        # gate-only controls (force, fresh case_ws). Every other argument is
        # left at build_srcpulse_demo's declared default.
        t0 = time.time()
        result = tsd.build_srcpulse_demo(case_ws=case_ws, force=True)
        wall_s = time.time() - t0

        payload = build_payload(result, side=side)  # raises GateAbort per Section 2.2/2.5/3.1
        normalized = normalize(payload)  # Section 4

        record = {
            "status": "OK",
            "side": side,
            "wall_s": wall_s,
            "env": env_fp,
            "normalized_payload": normalized,
            "raw_top_fields": sorted(payload.keys()),
        }

        if side == "reference":
            # Section 3.1: lift the reference into the frozen schema so it can
            # be compared against a candidate with no exclusions. Constants
            # are read off THIS run's own imported module -- never hardcoded
            # in the harness (Section 3.1: "can be independently verified
            # from the reference run").
            lifted_raw = lift_reference(payload, constants={"DOUBLET_Q": tsd.DOUBLET_Q})
            record["lifted_normalized_payload"] = normalize(lifted_raw)

    except GateAbort as e:
        record = {"status": "ABORT", "side": side, "error": str(e)}
    except Exception as e:  # noqa: BLE001 -- deliberately broad: report, don't crash silently
        record = {"status": "ERROR", "side": side, "error": str(e), "traceback": traceback.format_exc()}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2))
    sys.exit(0 if record["status"] == "OK" else 1)


# ===========================================================================
# ORCHESTRATOR shared plumbing
# ===========================================================================
def _child_env(flopy_bindir: str) -> dict:
    """Section 5.0: pinned threading BEFORE Python starts; identical process
    environment on both sides (the only permitted difference between sides
    is the worktree path / case_ws / --out / --side passed on argv, not
    anything in this env dict)."""
    env = dict(os.environ)
    for k in (
        "OMP_NUM_THREADS", "GDAL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
        "OMP_THREAD_LIMIT", "NUMBA_NUM_THREADS",
    ):
        env[k] = "1"
    env["PATH"] = flopy_bindir + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONPATH", None)  # no stray import roots leaking in
    return env


def _run_side(python_exe, this_file, worktree_root, case_ws, out_path, log_path, env, side):
    cmd = [
        python_exe, this_file, "worker",
        "--worktree-root", str(worktree_root),
        "--case-ws", str(case_ws),
        "--out", str(out_path),
        "--side", side,
    ]
    # The RAW on-disk log file (never committed -- lives under the caller's
    # --workdir) keeps full absolute paths, useful for local debugging. What
    # gets embedded into a committed report is `log_tail` (via _tail(),
    # above), which redacts the home directory out of whatever text is
    # captured here -- so the header line intentionally never writes the
    # full PATH at all (Section 5.0's own "drop PATH, keep the one boolean
    # fact" rule applies here too, not just in run_worker's env_fp).
    path_entries = (env.get("PATH") or "").split(os.pathsep)
    flopy_bindir_prepended = bool(path_entries) and path_entries[0] == os.path.expanduser(
        "~/.local/share/flopy/bin"
    )
    with open(log_path, "w") as lf:
        lf.write(
            f"cmd: {cmd}\ncwd: {worktree_root}\n"
            f"flopy_bindir_prepended: {flopy_bindir_prepended}\n\n"
        )
        lf.flush()
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=str(worktree_root), env=env,
                               stdout=lf, stderr=subprocess.STDOUT)
        wall = time.time() - t0
    return proc.returncode, wall


def _side_outcome(rc: int, result_path: Path, log_path: Path) -> dict:
    if rc is not None and rc < 0:
        sig = -rc
        return {
            "status": "SIGNAL", "signal": sig, "returncode": rc,
            "note": "fatal signal -- cannot be caught by any try/except in the worker "
                    "(model_io_utils.py ~2846); this is the SIGILL hazard Section 5.0 "
                    "mandates process isolation for.",
            "log_tail": _tail(log_path),
        }
    if result_path.exists():
        try:
            data = json.loads(result_path.read_text())
        except Exception as e:
            return {"status": "UNREADABLE_RESULT", "error": str(e), "log_tail": _tail(log_path)}
        data["log_tail"] = _tail(log_path)
        data.setdefault("returncode", rc)
        return data
    return {"status": "NO_RESULT_FILE", "returncode": rc, "log_tail": _tail(log_path)}


def _diff_normalized(a, b, path=""):
    """Section 5.2 step 8: on mismatch, report EVERY differing field with
    both values -- never stop at the first."""
    mismatches = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else k
            if k not in a:
                mismatches.append({"field": p, "A": "<MISSING>", "B": b[k]})
            elif k not in b:
                mismatches.append({"field": p, "A": a[k], "B": "<MISSING>"})
            else:
                mismatches.extend(_diff_normalized(a[k], b[k], p))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            mismatches.append({"field": path, "A": f"<list len {len(a)}>", "B": f"<list len {len(b)}>"})
        else:
            for i, (av, bv) in enumerate(zip(a, b)):
                mismatches.extend(_diff_normalized(av, bv, f"{path}[{i}]"))
    else:
        equal, rel = _leaf_equal(a, b)
        if not equal:
            m = {"field": path, "A": a, "B": b}
            if rel is not None:
                m["relative_difference"] = f"{rel:.3e}"
                m["tolerance"] = f"{FLOAT_REL_TOL:.0e}"
            mismatches.append(m)
    return mismatches


def _leaf_equal(a, b):
    """Compare one normalised leaf. Returns `(equal, relative_difference)`.

    Both sides are canonical STRINGS (`_normalize` ran first). When both parse
    as finite floats they are compared on `FLOAT_REL_TOL`; everything else --
    hashes, versions, enum values, ints that do not parse as float -- keeps
    EXACT equality, because for those a single character is a real difference.

    🔴 Non-finite values are never compared BY TOLERANCE -- only exactly. So
    `nan` against a number, or `inf` against a large float, is a mismatch and
    cannot be waved through by closeness.

    ⚠️ But identical normalised strings ARE equal, `"nan"` included. That is
    deliberate: `peak_mgL`/`t_peak` are legitimately NaN when the plume never
    arrives, and a rule making NaN != NaN would fail the gate against ITSELF
    on a valid run. The gate detects DIFFERENCE between two sides; judging
    whether NaN is a valid outcome is `provenance_valid`'s job, not this one.
    """
    if a == b:
        return True, None
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return False, None
    if not (math.isfinite(fa) and math.isfinite(fb)):
        return False, None          # NaN/inf: exact only
    denom = max(abs(fa), abs(fb))
    if denom == 0.0:
        return True, 0.0            # both zero, differing only in sign/format
    rel = abs(fa - fb) / denom
    return rel <= FLOAT_REL_TOL, rel


# ---------------------------------------------------------------------------
# Section 5.0 / 5.2 step 1 -- the environment fingerprint is compared IN
# FULL, not a curated subset, and a difference FAILS (never a warning). The
# only keys excluded are the ones Section 1.3 explicitly says are PERMITTED
# to differ: everything that is a function of which worktree/commit a side
# is running (its path, its own commit, its own case_ws, the two resolved
# module __file__s). Compared as a set union of whatever either side
# recorded, so a key present on only one side is still reported.
# ---------------------------------------------------------------------------
ENV_EXPECTED_DIFF_KEYS = frozenset((
    "worktree_root", "worktree_commit", "case_ws",
    "transport_srcpulse_demo_file", "model_io_utils_file",
))


def _env_mismatches(env_a: dict, env_b: dict) -> dict:
    mismatches = {}
    for key in sorted((set(env_a) | set(env_b)) - ENV_EXPECTED_DIFF_KEYS):
        va, vb = env_a.get(key), env_b.get(key)
        if va != vb:
            mismatches[key] = {"A": va, "B": vb}
    return mismatches


def _compare_normalized(a_norm: dict, b_norm: dict, env_a: dict, env_b: dict) -> dict:
    """Shared Section 5.2 comparison core: full env-fingerprint equality
    (step 1) plus exact string equality field by field on the already
    normalised (and, for a lifted reference, already schema-lifted) payload
    dicts (steps 6-8)."""
    env_mismatches = _env_mismatches(env_a, env_b)
    payload_mismatches = _diff_normalized(a_norm, b_norm)
    passed = not env_mismatches and not payload_mismatches
    return {
        "result": "PASS" if passed else "FAIL",
        "env_mismatches": env_mismatches,
        "payload_mismatch_count": len(payload_mismatches),
        "payload_mismatches": payload_mismatches,
    }


def compare_sides(a: dict, b: dict) -> dict:
    """Section 5.1 qualification comparison: both sides are the SAME schema
    (side="reference" on both), so their normalized_payload dicts are
    compared directly -- no lift, nothing pre-authorised is in play because
    b685f24 doesn't have those fields yet."""
    summary = {
        "side_A": {"status": a.get("status"), "wall_s": a.get("wall_s")},
        "side_B": {"status": b.get("status"), "wall_s": b.get("wall_s")},
    }

    if a.get("status") != "OK" or b.get("status") != "OK":
        summary["qualification"] = "FAIL"
        summary["reason"] = "one or both sides did not produce a valid canonical payload"
        return {"summary": summary, "side_A": a, "side_B": b}

    core = _compare_normalized(a["normalized_payload"], b["normalized_payload"], a["env"], b["env"])
    summary["qualification"] = core["result"]
    summary["env_mismatches"] = core["env_mismatches"]
    summary["payload_mismatch_count"] = core["payload_mismatch_count"]
    summary["payload_mismatches"] = core["payload_mismatches"]
    return {"summary": summary, "side_A": a, "side_B": b}


def compare_reference_vs_candidate(a: dict, b: dict) -> dict:
    """Section 5.2, the actual T1 gate: side A is the b685f24 REFERENCE
    (its raw payload already schema-lifted per Section 3.1/3.3 by the
    worker -- "lifted_normalized_payload"), side B is the T1 CANDIDATE (its
    "normalized_payload" already validated against the candidate schema by
    the worker). Nothing is excluded (Section 3.1 point 3)."""
    summary = {
        "side_A_reference": {"status": a.get("status"), "wall_s": a.get("wall_s")},
        "side_B_candidate": {"status": b.get("status"), "wall_s": b.get("wall_s")},
    }

    if a.get("status") != "OK" or b.get("status") != "OK":
        summary["comparison"] = "FAIL"
        summary["reason"] = "one or both sides did not produce a valid canonical payload"
        return {"summary": summary, "side_A_reference": a, "side_B_candidate": b}

    if "lifted_normalized_payload" not in a:
        summary["comparison"] = "FAIL"
        summary["reason"] = (
            "reference side did not carry a lifted_normalized_payload -- was it run "
            "with --side reference?"
        )
        return {"summary": summary, "side_A_reference": a, "side_B_candidate": b}

    core = _compare_normalized(
        a["lifted_normalized_payload"], b["normalized_payload"], a["env"], b["env"]
    )
    summary["comparison"] = core["result"]
    summary["env_mismatches"] = core["env_mismatches"]
    summary["payload_mismatch_count"] = core["payload_mismatch_count"]
    summary["payload_mismatches"] = core["payload_mismatches"]
    return {"summary": summary, "side_A_reference": a, "side_B_candidate": b}


def _ensure_config(repo_root: Path, worktree: Path, copy_if_missing_only: bool) -> None:
    """Section 5.0: a fresh worktree has only config_template.py; this
    machine's gitignored config.py must be propagated so both sides resolve
    the SAME data folder (Section 1.1). For a harness-CREATED worktree we
    always overwrite (it is guaranteed empty of a prior config.py from a
    real dev session). For a pre-existing candidate worktree path the
    caller passes copy_if_missing_only=True so a real developer worktree's
    own config.py is never clobbered; if it diverges from the repo's, that
    surfaces later as a data_folder env mismatch (Section 5.2 step 1) rather
    than being silently patched over."""
    cfg = repo_root / "config.py"
    if not cfg.exists():
        raise SystemExit(
            "repo config.py not found -- cannot propagate the data-source config "
            "to the worktrees (both sides would silently diverge onto config_template.py)"
        )
    dest = worktree / "config.py"
    if copy_if_missing_only and dest.exists():
        _log(f"NOTE: {dest} already exists -- leaving it as is (candidate worktree not "
             f"created by this harness run); a data_folder mismatch will surface in the "
             f"environment-fingerprint comparison if it diverges from {cfg}")
        return
    shutil.copy2(cfg, dest)
    _log(f"copied {cfg} into {worktree}")


def _project_venv_python(repo_root: Path) -> str:
    # NOT os.path.realpath(sys.executable): uv creates .venv/bin/python3 as a
    # SYMLINK to a shared uv-managed base interpreter. Resolving the symlink
    # and invoking that target directly loses the venv (no pyvenv.cfg next to
    # the base interpreter -> it falls back to the base site-packages, which
    # has none of flopy/numpy/geopandas installed). Invoke the venv launcher
    # itself so both worker processes get the SAME project virtualenv
    # (Section 1.3: "one FloPy, one Python") -- the only thing that must
    # differ between the two sides is the worktree, never the interpreter.
    python_exe = str(repo_root / ".venv" / "bin" / "python3")
    if not os.path.isfile(python_exe):
        raise SystemExit(f"project venv python not found: {python_exe}")
    return python_exe


def _resolve_commit(repo_root: Path, ref: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", ref],
        capture_output=True, text=True, check=True,
    )
    return r.stdout.strip()


# ===========================================================================
# ORCHESTRATOR -- "qualify": two worktrees, two sequential fresh processes,
# same commit on both sides.
# ===========================================================================
def run_qualification(args) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    ref_commit = args.ref_commit
    worktree_a = workdir / "worktree_A"
    worktree_b = workdir / "worktree_B"
    case_ws_a = workdir / "case_ws_A"
    case_ws_b = workdir / "case_ws_B"
    log_a = workdir / "side_A.log"
    log_b = workdir / "side_B.log"
    result_a = workdir / "side_A_result.json"
    result_b = workdir / "side_B_result.json"
    report_path = workdir / "qualification_report.json"

    for p in (case_ws_a, case_ws_b):
        if p.exists():
            raise SystemExit(f"case_ws already exists -- must be fresh (Section 1.2): {p}")
    for wt in (worktree_a, worktree_b):
        if wt.exists():
            raise SystemExit(f"worktree path already exists: {wt}")

    _log(f"qualification: {ref_commit} vs {ref_commit} (same commit -- pure run-to-run "
         f"nondeterminism measurement, Section 5.1)")
    _log(f"workdir: {workdir}")

    _log(f"creating worktree A at {worktree_a} @ {ref_commit}")
    subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                    str(worktree_a), ref_commit], check=True)
    _log(f"creating worktree B at {worktree_b} @ {ref_commit}")
    subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                    str(worktree_b), ref_commit], check=True)

    _ensure_config(repo_root, worktree_a, copy_if_missing_only=False)
    _ensure_config(repo_root, worktree_b, copy_if_missing_only=False)

    python_exe = _project_venv_python(repo_root)
    this_file = str(Path(__file__).resolve())
    flopy_bindir = os.path.expanduser("~/.local/share/flopy/bin")
    env = _child_env(flopy_bindir)
    _log(f"python: {python_exe}")
    _log(f"PATH (child): {env['PATH']}")
    _log(f"thread pins: OMP_NUM_THREADS={env['OMP_NUM_THREADS']} "
         f"GDAL_NUM_THREADS={env['GDAL_NUM_THREADS']}")

    # Both sides are the frozen reference schema -- b685f24 has none of the
    # Section 3 pre-authorised fields yet.
    _log("launching side A (worktree_A / case_ws_A) -- cold corridor refine + "
         "pilot + production coupled GWF+GWT solve ...")
    rc_a, wall_a = _run_side(python_exe, this_file, worktree_a, case_ws_a,
                              result_a, log_a, env, side="reference")
    _log(f"side A finished: returncode={rc_a} outer_wall={wall_a:.1f}s")

    _log("launching side B (worktree_B / case_ws_B) -- cold corridor refine + "
         "pilot + production coupled GWF+GWT solve ...")
    rc_b, wall_b = _run_side(python_exe, this_file, worktree_b, case_ws_b,
                              result_b, log_b, env, side="reference")
    _log(f"side B finished: returncode={rc_b} outer_wall={wall_b:.1f}s")

    a = _side_outcome(rc_a, result_a, log_a)
    a.setdefault("wall_s", wall_a)
    a["outer_wall_s"] = wall_a
    b = _side_outcome(rc_b, result_b, log_b)
    b.setdefault("wall_s", wall_b)
    b["outer_wall_s"] = wall_b

    report = compare_sides(a, b)
    report["harness_identity"] = _harness_identity(repo_root, this_file)
    _assert_no_leaked_paths(report, f"qualification report {report_path}")
    report_path.write_text(json.dumps(report, indent=2))
    _log(f"report written: {report_path}")
    _log("SUMMARY:\n" + json.dumps(report["summary"], indent=2))

    if not args.keep_worktrees:
        _log("removing worktrees (case_ws directories are kept -- they are the evidence)")
        subprocess.run(["git", "-C", str(repo_root), "worktree", "remove", "--force",
                        str(worktree_a)], check=False)
        subprocess.run(["git", "-C", str(repo_root), "worktree", "remove", "--force",
                        str(worktree_b)], check=False)

    return 0 if report["summary"]["qualification"] == "PASS" else 1


# ===========================================================================
# ORCHESTRATOR -- "compare": Section 5.2, the actual T1 gate. Reference at
# --ref-commit (always a fresh harness-created worktree) versus --candidate
# (a commit-ish -> fresh harness-created worktree, OR an existing directory
# -> used as is, never created or removed by the harness).
# ===========================================================================
def run_compare(args) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    ref_commit = args.ref_commit
    candidate_arg = args.candidate
    candidate_path = Path(candidate_arg).expanduser()
    candidate_is_existing_worktree = candidate_path.is_dir()

    worktree_a = workdir / "worktree_A_reference"
    case_ws_a = workdir / "case_ws_A_reference"
    log_a = workdir / "side_A_reference.log"
    result_a = workdir / "side_A_reference_result.json"

    if candidate_is_existing_worktree:
        worktree_b = candidate_path.resolve()
        _log(f"--candidate {candidate_arg!r} resolves to an existing directory -- using it "
             f"AS IS (not created or removed by this harness run)")
        r = subprocess.run(["git", "-C", str(worktree_b), "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(
                f"--candidate path {worktree_b} does not look like a git worktree "
                f"(git rev-parse failed): {r.stderr.strip()}"
            )
    else:
        worktree_b = workdir / "worktree_B_candidate"
        if worktree_b.exists():
            raise SystemExit(f"worktree path already exists: {worktree_b}")
    case_ws_b = workdir / "case_ws_B_candidate"
    log_b = workdir / "side_B_candidate.log"
    result_b = workdir / "side_B_candidate_result.json"
    report_path = workdir / "compare_report.json"

    if case_ws_a.exists():
        raise SystemExit(f"case_ws already exists -- must be fresh (Section 1.2): {case_ws_a}")
    if case_ws_b.exists():
        raise SystemExit(f"case_ws already exists -- must be fresh (Section 1.2): {case_ws_b}")
    if worktree_a.exists():
        raise SystemExit(f"worktree path already exists: {worktree_a}")

    _log(f"compare: reference {ref_commit!r} vs candidate {candidate_arg!r} (Section 5.2)")
    _log(f"workdir: {workdir}")

    _log(f"creating reference worktree at {worktree_a} @ {ref_commit}")
    subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                    str(worktree_a), ref_commit], check=True)

    candidate_created = False
    if not candidate_is_existing_worktree:
        _log(f"creating candidate worktree at {worktree_b} @ {candidate_arg}")
        subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                        str(worktree_b), candidate_arg], check=True)
        candidate_created = True

    _ensure_config(repo_root, worktree_a, copy_if_missing_only=False)
    _ensure_config(repo_root, worktree_b, copy_if_missing_only=candidate_is_existing_worktree)

    python_exe = _project_venv_python(repo_root)
    this_file = str(Path(__file__).resolve())
    flopy_bindir = os.path.expanduser("~/.local/share/flopy/bin")
    env = _child_env(flopy_bindir)
    _log(f"python: {python_exe}")
    _log(f"PATH (child): {env['PATH']}")
    _log(f"thread pins: OMP_NUM_THREADS={env['OMP_NUM_THREADS']} "
         f"GDAL_NUM_THREADS={env['GDAL_NUM_THREADS']}")

    try:
        _log("launching side A / reference (worktree_A_reference / case_ws_A_reference) ...")
        rc_a, wall_a = _run_side(python_exe, this_file, worktree_a, case_ws_a,
                                  result_a, log_a, env, side="reference")
        _log(f"side A / reference finished: returncode={rc_a} outer_wall={wall_a:.1f}s")

        _log("launching side B / candidate (worktree_B_candidate / case_ws_B_candidate) ...")
        rc_b, wall_b = _run_side(python_exe, this_file, worktree_b, case_ws_b,
                                  result_b, log_b, env, side="candidate")
        _log(f"side B / candidate finished: returncode={rc_b} outer_wall={wall_b:.1f}s")

        a = _side_outcome(rc_a, result_a, log_a)
        a.setdefault("wall_s", wall_a)
        a["outer_wall_s"] = wall_a
        b = _side_outcome(rc_b, result_b, log_b)
        b.setdefault("wall_s", wall_b)
        b["outer_wall_s"] = wall_b

        # Sanity check (Section 5.0's asserted import roots, extended to the
        # orchestrator level): each side actually ran at the commit it was
        # supposed to.
        if a.get("status") == "OK":
            expected_a = _resolve_commit(repo_root, ref_commit)
            got_a = a["env"].get("worktree_commit")
            if got_a != expected_a:
                raise SystemExit(
                    f"reference side ran at commit {got_a!r}, expected {expected_a!r} "
                    f"(resolved from {ref_commit!r})"
                )

        report = compare_reference_vs_candidate(a, b)
        report["harness_identity"] = _harness_identity(repo_root, this_file)
        _assert_no_leaked_paths(report, f"compare report {report_path}")
        report_path.write_text(json.dumps(report, indent=2))
        _log(f"report written: {report_path}")
        _log("SUMMARY:\n" + json.dumps(report["summary"], indent=2))

        return 0 if report["summary"]["comparison"] == "PASS" else 1
    finally:
        if not args.keep_worktrees:
            _log("removing worktrees this run created (case_ws directories are kept -- "
                 "they are the evidence)")
            subprocess.run(["git", "-C", str(repo_root), "worktree", "remove", "--force",
                            str(worktree_a)], check=False)
            if candidate_created:
                subprocess.run(["git", "-C", str(repo_root), "worktree", "remove", "--force",
                                str(worktree_b)], check=False)


# ===========================================================================
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)

    pw = sub.add_parser("worker", help="internal: run one side (spawned by 'qualify'/'compare')")
    pw.add_argument("--worktree-root", required=True)
    pw.add_argument("--case-ws", required=True)
    pw.add_argument("--out", required=True)
    pw.add_argument("--side", required=True, choices=("reference", "candidate"))

    pq = sub.add_parser("qualify", help="run b685f24-vs-b685f24 qualification (Section 5.1)")
    pq.add_argument("--workdir", required=True)
    pq.add_argument("--ref-commit", default="b685f24")
    pq.add_argument("--keep-worktrees", action="store_true")

    pc = sub.add_parser("compare", help="run reference-vs-candidate comparison (Section 5.2)")
    pc.add_argument("--workdir", required=True)
    pc.add_argument("--ref-commit", default="b685f24")
    pc.add_argument("--candidate", required=True,
                     help="T1 candidate: a commit-ish/branch, OR an existing worktree directory path")
    pc.add_argument("--keep-worktrees", action="store_true")

    args = p.parse_args()
    if args.mode == "worker":
        run_worker(args)
    elif args.mode == "qualify":
        sys.exit(run_qualification(args))
    elif args.mode == "compare":
        sys.exit(run_compare(args))


if __name__ == "__main__":
    main()
