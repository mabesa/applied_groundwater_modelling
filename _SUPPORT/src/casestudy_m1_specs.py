"""
casestudy_m1_specs -- M1.5 loader + linter for the three M1.5 spec YAMLs.

SPEC-ONLY (no model run). Parses + lints:
  * casestudy_structural_gates.yaml       -- code-hygiene grep gates + a
                                             physics_gates_ref that points at
                                             M1.4 (orphan-id + version/hash gate)
  * casestudy_equalization_dimensions.yaml -- each dimension resolves to EXACTLY
                                             ONE producer (an M1.4 id / an
                                             M2a/M3a emit-obligation / reviewer)
  * casestudy_config_schema.yaml           -- the machine-readable config
                                             contract (cross-checked against the
                                             keys case_utils enforces)

This module does NOT reimplement M1.4's diagnostics or case_utils's linting: it
REFERENCES M1.4 (via casestudy_diagnostics) to verify no orphan/stale physics
references, and it cross-checks the config schema against case_utils's source
without re-running it.

Author: Applied Groundwater Modelling Course (transport track, M1.5).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

import casestudy_diagnostics as cdx  # M1.4 -- referenced, never reimplemented

_MODULE_DIR = Path(__file__).resolve().parent
STRUCTURAL_GATES_PATH = _MODULE_DIR / "casestudy_structural_gates.yaml"
EQUALIZATION_DIMENSIONS_PATH = _MODULE_DIR / "casestudy_equalization_dimensions.yaml"
CONFIG_SCHEMA_PATH = _MODULE_DIR / "casestudy_config_schema.yaml"
CASE_UTILS_PATH = _MODULE_DIR / "case_utils.py"

OWNER_MILESTONES = frozenset({"M2a", "M3a", "M3b"})
DIMENSION_KINDS = frozenset({"numeric", "qualitative"})
EMIT_MILESTONES = frozenset({"M2a", "M3a", "M2a+M3a"})
CONFIG_TYPES = frozenset({"num", "int", "str", "bool", "list"})

# The leaf keys case_utils._lint_* require (mirror of case_utils; a consistency
# test asserts each leaf token still appears in case_utils.py AND that the full
# path is covered by casestudy_config_schema.yaml).
CASE_UTILS_ENFORCED_KEYS = (
    "doublet.injection_easting", "doublet.injection_northing",
    "doublet.extraction_easting", "doublet.extraction_northing",
    "doublet.pumping_rate_m3_d", "doublet.recirculation_fraction",
    "source.type", "source.release_type",
    "source.location.easting", "source.location.northing", "source.location.layer",
    "source.duration_days", "source.concentration_mg_L",
    "simulation.duration_days", "simulation.output_times_days",
    "submodel.cell_size_m",
    "monitoring.threshold_mg_L",
)


class SpecError(ValueError):
    """Raised when an M1.5 spec YAML fails linting."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require_str(where: str, d: Dict[str, Any], key: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v.strip():
        raise SpecError(f"{where}: {key!r} must be a non-empty string.")
    return v


def _m14_schema_ids() -> set:
    return set(cdx.diagnostic_ids())


# ---------------------------------------------------------------------------
# loaders (lint by default)
# ---------------------------------------------------------------------------
def load_structural_gates(path: Optional[Path] = None, *, lint: bool = True) -> Dict[str, Any]:
    doc = _load_yaml(Path(path or STRUCTURAL_GATES_PATH))
    if lint:
        lint_structural_gates(doc)
    return doc


def load_equalization_dimensions(path: Optional[Path] = None, *, lint: bool = True) -> Dict[str, Any]:
    doc = _load_yaml(Path(path or EQUALIZATION_DIMENSIONS_PATH))
    if lint:
        lint_equalization_dimensions(doc)
    return doc


def load_config_schema(path: Optional[Path] = None, *, lint: bool = True) -> Dict[str, Any]:
    doc = _load_yaml(Path(path or CONFIG_SCHEMA_PATH))
    if lint:
        lint_config_schema(doc)
    return doc


# ---------------------------------------------------------------------------
# lint: structural gates + physics_gates_ref integrity
# ---------------------------------------------------------------------------
def lint_structural_gates(doc: Dict[str, Any],
                          m14_schema_path: Optional[Path] = None) -> None:
    if not isinstance(doc, dict):
        raise SpecError("structural gates: root must be a mapping.")
    _require_str("structural gates", doc, "schema_version")
    gates = doc.get("gates")
    if not isinstance(gates, list) or not gates:
        raise SpecError("structural gates: 'gates' must be a non-empty list.")

    seen: set = set()
    for i, g in enumerate(gates):
        where = f"gate {g.get('id')!r}" if isinstance(g, dict) else f"gates[{i}]"
        if not isinstance(g, dict):
            raise SpecError(f"{where}: must be a mapping.")
        gid = _require_str(where, g, "id")
        if gid in seen:
            raise SpecError(f"duplicate gate id {gid!r}.")
        seen.add(gid)
        pattern = _require_str(where, g, "pattern")
        try:
            re.compile(pattern)
        except re.error as e:
            raise SpecError(f"{where}: pattern is not a valid regex ({e}).")
        scope = g.get("scope")
        if not isinstance(scope, list) or not scope or not all(isinstance(s, str) and s for s in scope):
            raise SpecError(f"{where}: 'scope' must be a non-empty list of glob strings.")
        if g.get("expected") != 0:
            raise SpecError(f"{where}: 'expected' must be 0 (got {g.get('expected')!r}).")
        if g.get("owner_milestone") not in OWNER_MILESTONES:
            raise SpecError(f"{where}: owner_milestone {g.get('owner_milestone')!r} not in {sorted(OWNER_MILESTONES)}.")
        _require_str(where, g, "rationale")

    # Two M1.4-reference blocks share the same {schema_path,version,sha256,ids}
    # drift-pin shape: physics_gates_ref (the physics GATES) and
    # diagnostic_producers_ref (the M1.4 ids used as equalization PRODUCERS,
    # e.g. flow_head_delta / capture_fraction_bounds). BOTH are orphan/drift
    # linted, so removing any pinned id from M1.4 fails M1.5's lint here (not
    # only at resolve_producer call time).
    _lint_m14_ref(doc.get("physics_gates_ref"), "physics_gates_ref", m14_schema_path)
    _lint_m14_ref(doc.get("diagnostic_producers_ref"), "diagnostic_producers_ref", m14_schema_path)


def _lint_m14_ref(ref: Any, block: str, m14_schema_path: Optional[Path]) -> set:
    """Lint an M1.4-reference block: required fields, that schema_path resolves
    to the REAL M1.4 schema (fail on a wrong directory), orphan-id gate, and
    version+hash drift gate. Returns the M1.4 id set."""
    if not isinstance(ref, dict):
        raise SpecError(f"structural gates: {block!r} block is required.")
    recorded_path = _require_str(block, ref, "schema_path")
    _require_str(block, ref, "schema_version")
    _require_str(block, ref, "schema_sha256")
    ids = ref.get("ids")
    if not isinstance(ids, list) or not ids:
        raise SpecError(f"{block}: 'ids' must be a non-empty list.")

    # The authoritative M1.4 schema location (tests may override).
    expected = Path(m14_schema_path).resolve() if m14_schema_path else cdx.DEFAULT_SCHEMA_PATH.resolve()

    # Resolve the RECORDED schema_path (repo-relative) to a real path and assert
    # it IS the M1.4 schema -- a wrong directory must fail even if the basename
    # matches / the default exists.
    repo_root = _MODULE_DIR.parent.parent
    resolved = (repo_root / recorded_path).resolve()
    if resolved != expected:
        raise SpecError(
            f"{block}: schema_path {recorded_path!r} resolves to {resolved} != the M1.4 "
            f"schema at {expected} (wrong path).")
    if not resolved.exists():
        raise SpecError(f"{block}: schema_path {recorded_path!r} does not exist ({resolved}).")

    m14 = cdx.load_schema(resolved)          # loads + lints M1.4
    m14_ids = {d["id"] for d in m14["diagnostics"]}

    missing = [x for x in ids if x not in m14_ids]
    if missing:
        raise SpecError(f"{block}: orphan id(s) not in M1.4 schema: {missing}.")

    if str(ref["schema_version"]) != str(m14.get("schema_version")):
        raise SpecError(
            f"{block}: schema_version {ref['schema_version']!r} != M1.4 "
            f"{m14.get('schema_version')!r} (M1.4 schema drifted -- update the reference).")
    actual_sha = _sha256_file(resolved)
    if str(ref["schema_sha256"]) != actual_sha:
        raise SpecError(
            f"{block}: schema_sha256 mismatch -- recorded {ref['schema_sha256']!r} "
            f"!= actual {actual_sha!r} (M1.4 schema changed; update the reference).")
    return m14_ids


# ---------------------------------------------------------------------------
# lint: equalization dimensions + producer resolution
# ---------------------------------------------------------------------------
def resolve_producer(producer: Any, m14_ids: Optional[set] = None) -> Dict[str, str]:
    """Resolve a producer string to EXACTLY ONE allowed form; raise otherwise.
    Returns ``{"form": ..., "ref": ...}``."""
    if not isinstance(producer, str) or not producer.strip():
        raise SpecError(f"producer must be a non-empty string (got {producer!r}).")
    m14_ids = m14_ids if m14_ids is not None else _m14_schema_ids()

    if producer.startswith("M1.4:"):
        did = producer[len("M1.4:"):]
        if did not in m14_ids:
            raise SpecError(f"producer {producer!r}: M1.4 diagnostic id {did!r} does not exist.")
        return {"form": "m1.4", "ref": did}
    if producer.startswith("emit-obligation:"):
        ms = producer[len("emit-obligation:"):]
        if ms not in EMIT_MILESTONES:
            raise SpecError(f"producer {producer!r}: emit-obligation milestone {ms!r} not in {sorted(EMIT_MILESTONES)}.")
        return {"form": "emit-obligation", "ref": ms}
    if producer == "reviewer:M5":
        return {"form": "reviewer", "ref": "M5"}
    raise SpecError(
        f"producer {producer!r} is not a valid form "
        "(expected 'M1.4:<id>', 'emit-obligation:M2a|M3a|M2a+M3a', or 'reviewer:M5').")


def lint_equalization_dimensions(doc: Dict[str, Any]) -> None:
    if not isinstance(doc, dict):
        raise SpecError("equalization dimensions: root must be a mapping.")
    _require_str("equalization dimensions", doc, "schema_version")
    dims = doc.get("dimensions")
    if not isinstance(dims, list) or not dims:
        raise SpecError("equalization dimensions: 'dimensions' must be a non-empty list.")

    m14_ids = _m14_schema_ids()
    seen: set = set()
    for i, d in enumerate(dims):
        where = f"dimension {d.get('id')!r}" if isinstance(d, dict) else f"dimensions[{i}]"
        if not isinstance(d, dict):
            raise SpecError(f"{where}: must be a mapping.")
        did = _require_str(where, d, "id")
        if did in seen:
            raise SpecError(f"duplicate dimension id {did!r}.")
        seen.add(did)
        if d.get("kind") not in DIMENSION_KINDS:
            raise SpecError(f"{where}: kind {d.get('kind')!r} not in {sorted(DIMENSION_KINDS)}.")
        # EXACTLY ONE producer form (raises if ambiguous/invalid)
        resolve_producer(d.get("producer"), m14_ids)
        for f in ("source", "unit", "aggregation", "baseline_convention", "m3c_band", "notes"):
            _require_str(where, d, f)


def emit_obligations(doc: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """Enumerate the emit-obligations the dimensions place on the builders:
    ``{"M2a": [...], "M3a": [...], "M2a+M3a": [...]}`` -> dimension ids each
    milestone still owes."""
    doc = doc or load_equalization_dimensions()
    out: Dict[str, List[str]] = {ms: [] for ms in sorted(EMIT_MILESTONES)}
    for d in doc["dimensions"]:
        r = resolve_producer(d["producer"])
        if r["form"] == "emit-obligation":
            out[r["ref"]].append(d["id"])
    return out


# ---------------------------------------------------------------------------
# lint: config schema + consistency vs case_utils
# ---------------------------------------------------------------------------
def _iter_key_specs(config_block: Dict[str, Any]):
    for k in config_block.get("required_keys", []) or []:
        yield k, k.get("path")
    for lb in config_block.get("list_blocks", []) or []:
        for k in lb.get("item_required_keys", []) or []:
            yield k, k.get("name")


def lint_config_schema(doc: Dict[str, Any]) -> None:
    if not isinstance(doc, dict):
        raise SpecError("config schema: root must be a mapping.")
    _require_str("config schema", doc, "schema_version")
    if not isinstance(doc.get("enforced_by"), list) or not doc["enforced_by"]:
        raise SpecError("config schema: 'enforced_by' must be a non-empty list.")
    configs = doc.get("configs")
    if not isinstance(configs, dict) or not {"flow", "transport"} <= set(configs):
        raise SpecError("config schema: 'configs' must contain 'flow' and 'transport'.")

    for cname, cblock in configs.items():
        where = f"config '{cname}'"
        if not isinstance(cblock, dict):
            raise SpecError(f"{where}: must be a mapping.")
        _require_str(where, cblock, "file")
        if "required_keys" not in cblock and "list_blocks" not in cblock:
            raise SpecError(f"{where}: needs at least one of required_keys/list_blocks.")
        for spec, name in _iter_key_specs(cblock):
            if not isinstance(spec, dict) or not (isinstance(name, str) and name):
                raise SpecError(f"{where}: every key spec needs a non-empty path/name.")
            # a spec must carry a type OR be an explicit 'forbidden' key
            if not spec.get("forbidden") and spec.get("type") not in CONFIG_TYPES:
                raise SpecError(
                    f"{where}: key {name!r} type {spec.get('type')!r} not in {sorted(CONFIG_TYPES)} "
                    "(or mark it forbidden: true).")
            if "enum" in spec and not (isinstance(spec["enum"], list) and spec["enum"]):
                raise SpecError(f"{where}: key {name!r} 'enum' must be a non-empty list.")
        cf = cblock.get("cross_field")
        if cf is not None and not (isinstance(cf, list) and all(isinstance(s, str) for s in cf)):
            raise SpecError(f"{where}: 'cross_field' must be a list of strings.")


def advisory_check_config_schema_vs_case_utils(doc: Optional[Dict[str, Any]] = None) -> None:
    """ADVISORY smoke test (NOT a guarantee of full coverage).

    `case_utils.lint_transport_config` / `get_scenario_for_group` remain the
    ENFORCEMENT source of truth; `casestudy_config_schema.yaml` is a parseable
    REFERENCE. This check only verifies that the hand-maintained mirror
    ``CASE_UTILS_ENFORCED_KEYS`` (a) still appears as an ENFORCEMENT-context
    token (a quoted ``"leaf"`` string, not a mere comment) in case_utils.py and
    (b) is covered by the schema. It does NOT auto-discover a NEW enforced key
    -- so **adding a case_utils-enforced key REQUIRES updating BOTH
    ``CASE_UTILS_ENFORCED_KEYS`` here AND the config schema**. It is a drift
    smoke test, not proof the schema covers every enforced key.
    """
    doc = doc or load_config_schema()
    schema_keys: set = set()
    for cblock in doc["configs"].values():
        for _spec, name in _iter_key_specs(cblock):
            if name:
                schema_keys.add(name)
    src = CASE_UTILS_PATH.read_text()
    for key in CASE_UTILS_ENFORCED_KEYS:
        leaf = key.split(".")[-1]
        # require the leaf as a QUOTED enforcement literal (case_utils uses
        # e.g. `_get_required(source, "type", ...)`), not just any substring --
        # a bare mention in a comment must not satisfy the check.
        if f'"{leaf}"' not in src:
            raise SpecError(
                f"case_utils no longer references enforced key leaf {leaf!r} as a quoted "
                "literal -- CASE_UTILS_ENFORCED_KEYS is stale (update the mirror + schema).")
        if key not in schema_keys:
            raise SpecError(f"config schema does not cover case_utils-enforced key {key!r}.")


# backward-compatible alias (deprecated name)
check_config_schema_covers_case_utils = advisory_check_config_schema_vs_case_utils


# ---------------------------------------------------------------------------
# top-level
# ---------------------------------------------------------------------------
def check_producer_ids_pinned(gates_doc: Dict[str, Any], dims_doc: Dict[str, Any]) -> None:
    """Every M1.4 id used as a `producer: M1.4:<id>` in the equalization
    dimensions MUST be pinned in the gates file's `diagnostic_producers_ref.ids`
    (so it shares the drift pin). Fails if a new M1.4-backed producer is added
    without pinning it."""
    used = set()
    for d in dims_doc["dimensions"]:
        p = d["producer"]
        if isinstance(p, str) and p.startswith("M1.4:"):
            used.add(p[len("M1.4:"):])
    pinned = set(gates_doc.get("diagnostic_producers_ref", {}).get("ids", []))
    missing = used - pinned
    if missing:
        raise SpecError(
            f"equalization producers reference M1.4 id(s) {sorted(missing)} not pinned in "
            "diagnostic_producers_ref.ids (add them so drift is caught).")


def lint_all() -> Dict[str, Any]:
    """Load + lint all three M1.5 specs, the M1.4-reference drift pins, the
    producer-pin cross-check, and the advisory config-schema smoke test.
    Returns the three parsed docs."""
    gates = load_structural_gates()
    dims = load_equalization_dimensions()
    cfg = load_config_schema()
    check_producer_ids_pinned(gates, dims)
    advisory_check_config_schema_vs_case_utils(cfg)
    return {"structural_gates": gates, "equalization_dimensions": dims, "config_schema": cfg}


if __name__ == "__main__":
    docs = lint_all()
    print(f"M1.5 specs OK: {len(docs['structural_gates']['gates'])} gates "
          f"(+ physics_gates_ref & diagnostic_producers_ref pinned to M1.4), "
          f"{len(docs['equalization_dimensions']['dimensions'])} dimensions, "
          f"config-schema advisory smoke-check passed.")
    obs = emit_obligations(docs["equalization_dimensions"])
    for ms, ids in obs.items():
        if ids:
            print(f"  emit-obligation:{ms} -> {ids}")
