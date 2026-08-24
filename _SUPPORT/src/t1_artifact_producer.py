"""
t1_artifact_producer -- T1 S14: the evidence-artifact PRODUCER, wiring a real
`build_srcpulse_demo` run into a real `t1_evidence_artifact.EvidenceRecord`.

Scope (`DESIGN_DOCS/T1_S14_brief.md` v2; authorised by
`DOCUMENTATION/contracts/T0_1_C1_v2.md` entry A5, surface "new"): this is a
NEW module. It imports BOTH the model (`transport_srcpulse_demo`,
`model_io_utils`, `data_utils`) and the artifact schema (`t1_evidence_artifact`),
plus the two evaluator-side modules S6/S11/S12 already shipped
(`t1_claim_support_state`, `t1_exp_metrics`). No existing production file is
edited by this module.

================================================================================
DEPENDENCY DIRECTION -- restated, not re-decided
================================================================================
`t1_evidence_artifact.py` stays STDLIB-ONLY; it gains no import from this
module or anywhere else (verified by `test_artifact_module_remains_stdlib_only`
in the companion test file, which re-parses its live imports). The model
(`transport_srcpulse_demo.py`) does not import this module either -- doing so
would grow `test_t1_src_closure.py`'s pinned 7-module demo closure, which this
module's own tests re-assert stays exactly 7 (`test_model_does_not_import_the_producer`).
Only THIS module imports across the boundary, in the one direction the T1
Phase-4 plan authorises: producer -> {model, schema, evaluator}.

================================================================================
🔴 PLACEMENT DECISION -- the experimental marker and `courant_profile` live
INSIDE `run_identity.grid_spec`, NOT in a new top-level field
================================================================================
T0_2b Sec 8.3(a) (via the S14 brief Sec 4) freezes that the record must carry
an explicit, DERIVED experimental-configuration marker (the `exp/vN` label the
S7 drop deferred). But `t1_evidence_artifact.py`'s SCHEMA_VERSION 3.1.0 has NO
field for it, and NO field for `courant_profile` either (T1 S8's third
Courant policy, `run_identity.cr_target` is the ONLY Courant-adjacent field
that schema ships) -- and this module may not add one: `t1_evidence_artifact.py`
is an EXISTING production file, off the authorised surface for S14.

`run_identity.grid_spec` is declared, verbatim, as "an OPAQUE, arbitrary
JSON-safe mapping... does not validate their internal structure beyond 'is a
non-empty mapping of JSON-safe values'" (`t1_evidence_artifact.py` module
docstring, SCHEMA DECISIONS preamble) -- and S14 is explicitly named there as
"responsible for serialising it faithfully". This module therefore nests BOTH
the resolved `MeshSpec` AND the derived experimental marker (which needs the
mesh identity to compare against its own sentinel) inside that one opaque
mapping, under three top-level keys: `mesh_spec`, `courant_profile`,
`experimental`. This is WITHIN the schema's own declared bounds (an opaque,
unvalidated JSON-safe mapping) -- it does not edit, reinterpret, or add a
field to the frozen schema file. It is, however, THIS MODULE'S OWN READING of
an underspecified point (there is no other authorised home for either value),
flagged here exactly as the project's practice requires, and worth a lecturer
confirmation before this shape is treated as settled for T2.

================================================================================
🔴 THE EXPERIMENTAL REGISTRY -- exhaustive by CONSTRUCTION, not by promise
================================================================================
`compute_experimental_marker` compares five `build_srcpulse_demo` parameters
against their documented sentinel defaults: `cr_target` (0.9),
`footprint_radius_m` (0.0), `sink_support_m` (0.0), `courant_profile`
("legacy_srcpulse"), and the RESOLVED `mesh_spec` (`MeshSpec()`). These are
exactly the parameters `build_srcpulse_demo`'s own docstring marks "Not wired
into any default call -- a later milestone (T2) uses ..." -- the T1 S1-S11
capabilities the schema module's own docstring lists (footprint, Courant
policy, sink support, the GWF arm).

`refine_radii` is deliberately NOT a separate registry entry: it folds into
the resolved `mesh_spec` (`_resolve_mesh_spec`), so a caller using the legacy
argument is already caught by the `mesh_spec` comparison.

`mass_g`, `pulse_days`, `total_days`, `solubility_mgL`, `alpha_L`, `R`,
`rho_b`, `lam`, `case_ws`, `nstp_cap`, `force` are treated as CASE-DEFINITION
or plumbing parameters, not experimental-configuration knobs -- changing the
released mass or enabling sorption/decay selects a different physical
SCENARIO, it does not change how the same scenario is solved on the grid/time
axes T0_2b's `exp/vN` matrix explores. *** This split is THIS MODULE'S OWN
JUDGEMENT CALL, not dictated by the brief -- flagged here rather than made
silently; `nstp_cap` in particular is arguable (see the S14 report). ***

Exhaustiveness is enforced, not merely asserted: `test_every_build_srcpulse_demo_parameter_is_classified`
reads `build_srcpulse_demo`'s live signature via `inspect` and asserts every
keyword-only parameter is in EXACTLY ONE of `EXPERIMENTAL_KNOB_PARAMS` /
`CASE_DEFINITION_PARAMS` -- a future parameter landing in neither list fails
the test loudly, forcing a human classification decision instead of silently
defaulting to "not experimental".

================================================================================
🔴 TECHNICAL DEBT, NAMED: environment capture DUPLICATES the gate harness
================================================================================
`_SUPPORT/src/scripts/t0_gate_harness.py:908-936` (`run_worker`'s `env_fp`
dict) already captures OS/arch, Python/FloPy/NumPy versions, MF6/Triangle
SHA-256 and thread pinning -- the same facts `capture_environment` below
needs. That block is INLINE inside a larger function inside a SIGNED T0
artifact (`t0_gate_harness.py` adjudicates the default-preservation contract);
refactoring it to expose a shared helper is not a change to make casually
inside S14, and is explicitly off this step's authorised surface.

`capture_environment` therefore RE-IMPLEMENTS the same capture, ONCE, here.
This is TECHNICAL DEBT, not reuse, exactly as the brief names it. The intended
resolution: a later, explicitly authorised step extracts a shared
`_capture_environment()` helper the harness and this module both call, with
the harness's own behaviour independently pinned by its existing test suite
(`test_t0_gate_harness.py`) so the extraction cannot silently change what the
signed harness reports. Until then, `test_environment_capture_agrees_with_the_gate_harness`
and `test_environment_agreement_invokes_the_harness_not_a_reimplementation`
(in the companion test file) prove the two independent implementations agree
on every shared field, by dynamically extracting and executing the harness's
OWN source statements (never a hand-copied re-statement of its mapping) --
so a future edit to the harness's env capture is caught here as a diff, not
silently drifted past.

================================================================================
🔴 NAMED GAPS -- fields this module cannot source for every real run
================================================================================
1. `run_identity.source_footprint` at a POSITIVE `footprint_radius_m`. At the
   frozen SENTINEL (`footprint_radius_m == 0.0` -- the only value
   `build_srcpulse_demo` is wired to by default, per its own docstring) the
   footprint record is fully and exactly derivable from the run's own
   returned payload (`src_cells`, `smassrate_gpd`, `spill_xy`) -- see
   `footprint_from_result`. At a POSITIVE radius, the per-cell apportionment
   geometry (`_disc_footprint_areas`) needs the REFINED modelgrid object,
   which `build_srcpulse_demo`'s public return value does not expose and
   which this module may not add (T0_0 Sec 2.5, and no existing production
   file may be edited to expose it either). Recomputing it independently, from
   a second call into the model's internal grid-building machinery, risks
   exactly the "independent re-derivation" `T0_0...` Sec 3 warns against for
   a DIFFERENT reason than S9c's WEL readout (there the risk was a solve-time
   surprise; here it would be a second, separate Triangle/GIS build that must
   coincidentally agree byte-for-byte with the one the actual run used).
   **This module does not attempt it.** A record built from a positive-radius
   run is INCOMPLETE (missing `run_identity.source_footprint`) and correctly
   reports `provenance_valid = false` -- reported here as a named T1-exit
   item, per the brief Sec 2.4/7, not silently worked around.
2. `metrics["t_first_exceedance"]` / `["t_last_exceedance"]` /
   `["exceedance_duration"]` / `["capture_halfwidth_m"]`. The first three need
   a `ThresholdRecord` (`t1_exp_metrics.ThresholdRecord`); per that module's
   own docstring, "M0's real threshold-record schema
   (`_SUPPORT/src/casestudy_threshold_records.yaml`)... [is] not yet built".
   `capture_halfwidth_m` needs a PRT capture run (S10's separate pipeline),
   not `build_srcpulse_demo`. `metrics` only ever carries `peak_mgL` and
   `t_peak` here -- legitimate under SCHEMA DECISIONS #11 ("which metrics a
   given record must carry is producer-side policy"), but named so it is not
   mistaken for an oversight.
3. `support.diagnostics` is always `{}`. Wiring operator A
   (`transport_operator_a.compute_operator_a`) needs the solved GWT
   concentration reader, cell polygons, heads/top/botm and porosity off the
   ACTUAL run's GWF/GWT objects -- `transport_operator_a.py`'s own docstring
   names this integration "S14... expected to import BOTH modules and wire
   them together", but `build_srcpulse_demo`'s public return value
   (`SrcPulseDemo`) exposes none of those handles. Legitimate under SCHEMA
   DECISIONS #15 (bare `{}` is a complete, valid record), named here as a
   real gap rather than silently satisfied.

`claim_id` and `roster_hash` (brief Sec 2.4) are, by contrast, SOURCED, not
gapped -- see `validate_claim_id` and `roster_hash` below.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import platform
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

import transport_srcpulse_demo as tsd
import model_io_utils as mio
import data_utils

import t1_evidence_artifact as tea
import t1_claim_support_state as tcs
import t1_exp_metrics as tem


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
PRODUCER_MODULE = "t1_artifact_producer"
PRODUCER_VERSION = "1.0.0"

#: See module docstring, "THE EXPERIMENTAL REGISTRY". Bump this string, never
#: silently change the comparison logic beneath the same version, whenever
#: the registry's own membership or sentinel values change (brief Sec 4:
#: "the derivation version is recorded alongside the marker").
EXPERIMENTAL_DERIVATION_VERSION = "exp_marker_v1"

#: This module's own algorithm-id choices for the two default-path metrics --
#: not frozen by any contract (SCHEMA DECISIONS #8-style naming choice),
#: chosen to match the pre-existing `t1_evidence_artifact.build_fixture_record`
#: examples for continuity.
PEAK_ALGORITHM_ID = "max_breakthrough_v1"
LEGACY_T_PEAK_ALGORITHM_ID = "lattice_argmax_v1"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ArtifactProducerError(RuntimeError):
    """Base class for every error this module raises deliberately (never a
    caught-and-swallowed model exception -- see `run_srcpulse_for_record`)."""


class UnknownClaimIdError(ArtifactProducerError):
    """Raised by `validate_claim_id` when a `claim_id` is not a member of the
    T0.2a claim inventory (brief Sec 2.4: `claim_id` "NEITHER may be
    synthesised" -- validating against the inventory is the enforcement of
    that rule, not a courtesy check)."""


# ---------------------------------------------------------------------------
# Experimental-knob registry (module docstring, "THE EXPERIMENTAL REGISTRY")
# ---------------------------------------------------------------------------
_DEFAULT_MESH_SPEC = tsd.MeshSpec()

#: name -> sentinel value, for the four SCALAR knobs. `mesh_spec` is handled
#: separately (dataclass equality against `_DEFAULT_MESH_SPEC`), not as a
#: scalar sentinel.
EXPERIMENTAL_SCALAR_SENTINELS: Mapping[str, Any] = {
    "cr_target": 0.9,
    "footprint_radius_m": 0.0,
    "sink_support_m": 0.0,
    "courant_profile": "legacy_srcpulse",
}

#: The full registry, scalar knobs + `mesh_spec` -- used by the exhaustiveness
#: test to partition `build_srcpulse_demo`'s live signature.
EXPERIMENTAL_KNOB_PARAMS: Tuple[str, ...] = (
    "cr_target", "footprint_radius_m", "sink_support_m", "courant_profile", "mesh_spec",
)

#: Every OTHER `build_srcpulse_demo` parameter -- case-definition or plumbing,
#: per the module docstring's judgement call, not an experimental-configuration
#: knob in T0_2b's `exp/vN` sense.
CASE_DEFINITION_PARAMS: Tuple[str, ...] = (
    "mass_g", "pulse_days", "total_days", "solubility_mgL",
    "alpha_L", "R", "rho_b", "lam",
    "case_ws", "nstp_cap", "refine_radii", "force",
)


def compute_experimental_marker(
    *,
    cr_target: float,
    footprint_radius_m: float,
    sink_support_m: float,
    courant_profile: str,
    resolved_mesh_spec: "tsd.MeshSpec",
) -> Dict[str, Any]:
    """Derive the `exp/vN` marker from the run's OWN parameters -- never a
    caller-supplied label (brief Sec 4: "A caller-supplied label is an
    assertion; a derived one is a fact about the run.").

    `resolved_mesh_spec` must already be the output of
    `transport_srcpulse_demo._resolve_mesh_spec` (i.e. what the run ACTUALLY
    used), not a raw `mesh_spec=` argument that might be `None`.
    """
    knobs: Dict[str, Any] = {}
    for name, sentinel in EXPERIMENTAL_SCALAR_SENTINELS.items():
        value = {"cr_target": cr_target, "footprint_radius_m": footprint_radius_m,
                 "sink_support_m": sink_support_m, "courant_profile": courant_profile}[name]
        knobs[name] = {"value": value, "sentinel": sentinel, "deviates": bool(value != sentinel)}

    mesh_deviates = bool(resolved_mesh_spec != _DEFAULT_MESH_SPEC)
    knobs["mesh_spec"] = {
        "value": _mesh_spec_to_json(resolved_mesh_spec),
        "sentinel": _mesh_spec_to_json(_DEFAULT_MESH_SPEC),
        "deviates": mesh_deviates,
    }

    is_experimental = any(k["deviates"] for k in knobs.values())
    return {
        "is_experimental": is_experimental,
        "derivation_version": EXPERIMENTAL_DERIVATION_VERSION,
        "knobs": knobs,
    }


def _mesh_spec_to_json(mesh_spec: "tsd.MeshSpec") -> Dict[str, Any]:
    """Faithful, JSON-safe serialisation of a `MeshSpec` -- the model's own
    dataclass shape, per `t1_evidence_artifact.py`'s own docstring naming S14
    "responsible for serialising it faithfully (e.g. `dataclasses.asdict`)"."""
    return dataclasses.asdict(mesh_spec)


def grid_spec_payload(
    *,
    resolved_mesh_spec: "tsd.MeshSpec",
    courant_profile: str,
    marker: Mapping[str, Any],
) -> Dict[str, Any]:
    """Assemble `run_identity.grid_spec`'s opaque payload -- see module
    docstring, "PLACEMENT DECISION"."""
    return {
        "mesh_spec": _mesh_spec_to_json(resolved_mesh_spec),
        "courant_profile": courant_profile,
        "experimental": dict(marker),
    }


# ---------------------------------------------------------------------------
# Environment capture (module docstring, "TECHNICAL DEBT")
# ---------------------------------------------------------------------------
_FLOPY_BINDIR = os.path.dirname(tsd._MF6_FALLBACK)
_TRIANGLE_FALLBACK = os.path.join(_FLOPY_BINDIR, "triangle")


def ensure_flopy_bindir_on_path() -> None:
    """Prepend the flopy-bin install directory to `PATH` if it is not already
    resolvable there -- MF6 has a hardcoded fallback path
    (`transport_srcpulse_demo._MF6_FALLBACK`) but Triangle (invoked by flopy's
    `Triangle` wrapper with the bare name `"triangle"`) does not, and needs it
    on `PATH` to run at all. Mirrors the gate harness's own
    `_child_env`/`flopy_bindir_prepended` policy, applied to THIS process
    rather than a spawned subprocess."""
    if shutil.which("triangle") is not None and shutil.which("mf6") is not None:
        return
    current = os.environ.get("PATH", "")
    if _FLOPY_BINDIR not in current.split(os.pathsep):
        os.environ["PATH"] = _FLOPY_BINDIR + os.pathsep + current


def _sha256_file(path: Union[str, Path]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_binary(name: str, fallback: str) -> Tuple[Optional[str], Optional[str]]:
    """`(realpath, sha256)` for an executable found via `PATH` or *fallback*,
    or `(None, None)` if neither location holds a real file -- never a
    placeholder string."""
    exe = shutil.which(name) or fallback
    if not exe or not os.path.isfile(exe):
        return None, None
    real = os.path.realpath(exe)
    return real, _sha256_file(real)


def capture_environment() -> Dict[str, Any]:
    """Capture the Environment group's nine fields, independently of the
    gate harness's own inline capture (see module docstring). Any field this
    process genuinely cannot determine is OMITTED from the returned dict
    (never a placeholder) -- callers must treat an absent key as "could not
    source this field", not fill it in."""
    ensure_flopy_bindir_on_path()
    import flopy  # local import mirrors the harness's own run_worker pattern
    import numpy as np

    mf6_path, mf6_sha256 = _resolve_binary("mf6", tsd._MF6_FALLBACK)
    triangle_path, triangle_sha256 = _resolve_binary("triangle", _TRIANGLE_FALLBACK)

    env: Dict[str, Any] = {
        "os_arch": f"{platform.system()}-{platform.machine()}",
        "python_version": platform.python_version(),
        "thread_pinning": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "GDAL_NUM_THREADS": os.environ.get("GDAL_NUM_THREADS"),
        },
    }
    if mf6_path is not None:
        env["mf6_path"] = mf6_path
        env["mf6_sha256"] = mf6_sha256
    if triangle_path is not None:
        env["triangle_path"] = triangle_path
        env["triangle_sha256"] = triangle_sha256
    flopy_version = getattr(flopy, "__version__", None)
    if flopy_version:
        env["flopy_version"] = str(flopy_version)
    numpy_version = getattr(np, "__version__", None)
    if numpy_version:
        env["numpy_version"] = str(numpy_version)
    verify_environment_pairing(env)
    return env


def verify_environment_pairing(env: Mapping[str, Any]) -> None:
    """Guard against exit criterion 13 -- "binary hashes are paired with the
    RIGHT paths; a transposed pair passes every count-based check". Nothing
    in the generic schema cross-validates `mf6_sha256` against `mf6_path` (a
    loading machine may not even have the binary), so the guard has to live
    in the PRODUCER that builds the pairing in the first place. Re-hashes
    each binary at its OWN recorded path and compares to the recorded hash;
    raises `ArtifactProducerError` on any mismatch (e.g. the two pairs
    swapped). A no-op for any binary this process could not resolve (already
    omitted, not a pairing defect)."""
    for path_key, sha_key in (("mf6_path", "mf6_sha256"), ("triangle_path", "triangle_sha256")):
        path = env.get(path_key)
        sha = env.get(sha_key)
        if path is None or sha is None:
            continue
        if not os.path.isfile(path):
            continue
        actual = _sha256_file(path)
        if actual != sha:
            raise ArtifactProducerError(
                f"environment pairing defect: recorded {sha_key}={sha!r} does not match "
                f"the hash actually computed from {path_key}={path!r} ({actual!r}) -- "
                "the two path/hash pairs may have been transposed"
            )


# ---------------------------------------------------------------------------
# claim_id / roster_hash sourcing (brief Sec 2.4)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
CLAIM_INVENTORY_PATH = _REPO_ROOT / "DOCUMENTATION" / "contracts" / "T0_2a_claim_inventory.json"
CASE_ROSTER_PATH = _REPO_ROOT / "_SUPPORT" / "casestudy_scenarios" / "doublet_table.csv"

#: Candidate `claim_type` values (T0_2a inventory) that name an evaluable
#: claim -- `not_a_claim` / `illustrative` (retired orphans, T0_2b Sec 4.4)
#: are excluded; `causal` claims ARE evaluable (they reach the T0.3 gate-1
#: `causal_claim_out_of_scope` null, per `t1_claim_support_state.py`), just
#: never `grid_supported`.
_EVALUABLE_CLAIM_TYPES = frozenset({"numeric", "threshold-decision", "causal"})


def _load_claim_inventory() -> Sequence[Mapping[str, Any]]:
    with open(CLAIM_INVENTORY_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)["candidates"]


def validate_claim_id(claim_id: str) -> None:
    """Raise `UnknownClaimIdError` unless *claim_id* names an evaluable entry
    of the T0.2a claim inventory (brief Sec 2.4's named upstream source).
    Never synthesises an id -- a caller must supply one that already exists
    in `T0_2a_claim_inventory.json`."""
    for candidate in _load_claim_inventory():
        if candidate.get("id") == claim_id:
            types = candidate.get("claim_type") or []
            if not _EVALUABLE_CLAIM_TYPES.intersection(types):
                raise UnknownClaimIdError(
                    f"claim_id {claim_id!r} exists in the T0.2a inventory but its "
                    f"claim_type {types!r} is not evaluable ({sorted(_EVALUABLE_CLAIM_TYPES)})"
                )
            return
    raise UnknownClaimIdError(
        f"claim_id {claim_id!r} is not present in {CLAIM_INVENTORY_PATH} -- "
        "claim_id must name an existing inventory entry, never a synthesised string "
        "(brief Sec 2.4)"
    )


def roster_hash() -> Optional[str]:
    """SHA-256 of the shipped case roster (`_SUPPORT/casestudy_scenarios/doublet_table.csv`,
    `casestudy_doublet_roster.build_doublet_table`'s default output -- the
    9-row student-group roster referenced throughout T0/T1 as "the case
    roster"). Returns `None` (never a placeholder) if the roster file is not
    present on disk -- e.g. a fresh checkout that has not yet run
    `casestudy_doublet_roster.build_doublet_table()`.

    *** Naming this specific file as "the case roster" is THIS MODULE'S OWN
    READING of brief Sec 2.4's "the case roster" -- no contract names a file
    path -- flagged here rather than decided silently. ***
    """
    if not CASE_ROSTER_PATH.is_file():
        return None
    return _sha256_file(CASE_ROSTER_PATH)


def gis_hashes() -> Dict[str, str]:
    """`fingerprints.gis_hashes` -- sha256 of the same two GIS files the gate
    harness fingerprints (`model_boundary`, `rivers`), via the same
    `data_utils.download_named_file` entry point."""
    boundary_path = data_utils.download_named_file(name="model_boundary", data_type="gis")
    rivers_path = data_utils.download_named_file(name="rivers", data_type="gis")
    return {
        "model_boundary": _sha256_file(boundary_path),
        "rivers": _sha256_file(rivers_path),
    }


# ---------------------------------------------------------------------------
# source_footprint / controls / metrics from a completed run
# ---------------------------------------------------------------------------
def footprint_from_result(
    result: "tsd.SrcPulseDemo", *, footprint_radius_m: float
) -> Optional[tea.SourceFootprintRecord]:
    """Build `run_identity.source_footprint` from the run's OWN returned
    payload -- ONLY at the frozen sentinel (`footprint_radius_m == 0.0`),
    where it is exactly and fully derivable (SCHEMA DECISIONS #19's sentinel
    branch: one cell, `disc_area_m2 == covered_area_m2 == 0.0`, that cell
    carries the WHOLE rate). Returns `None` (never a fabricated positive-radius
    geometry) for any other radius -- see module docstring, "NAMED GAPS" #1.
    """
    if footprint_radius_m != 0.0:
        return None
    cell = int(result.src_cells[0])
    rate = float(result.smassrate_gpd)
    return tea.SourceFootprintRecord(
        algorithm_id=tsd._FOOTPRINT_ALGORITHM_ID,
        radius_m=0.0,
        centre_xy_m=(float(result.spill_xy[0]), float(result.spill_xy[1])),
        entries=(tea.FootprintEntry(cell=cell, intersection_area_m2=0.0, rate_g_per_day=rate),),
        total_rate_g_per_day=rate,
        coverage=tea.FootprintCoverage(disc_area_m2=0.0, covered_area_m2=0.0),
    )


def controls_from_inputs(
    *,
    sink_support_m: float,
    uncontrolled_counterpart_run_id: Optional[str],
) -> Mapping[str, tea.ControlRecord]:
    """Build `run_identity.controls` from CALL INPUTS only (never the run's
    result) -- `sink_support_m` is known before the run is attempted, so this
    is populated the same way whether or not the solve succeeds. `{}` at the
    sentinel (`sink_support_m == 0.0`), matching SCHEMA DECISIONS #20's "most
    runs carry no control at all"."""
    if sink_support_m == 0.0:
        return {}
    label = "sink_support_controlled"
    return {
        label: tea.ControlRecord(
            label=label,
            sink_support_m=float(sink_support_m),
            uncontrolled_counterpart_run_id=uncontrolled_counterpart_run_id,
            # Frozen True while PRT builds its own unmodified single-cell WEL
            # (model docstring; brief Sec 2.4 / SCHEMA DECISIONS #20).
            prt_capture_diverges=True,
        )
    }


def metrics_from_result(
    result: "tsd.SrcPulseDemo", *, is_experimental: bool
) -> Mapping[str, tea.MetricRecord]:
    """`peak_mgL` + `t_peak` -- the only two metrics this producer sources
    (module docstring, "NAMED GAPS" #2). `peak_mgL`'s algorithm never changes
    (T0_2b Sec 2.1, "unchanged from today"). `t_peak` uses the LEGACY lattice
    algorithm on the DEFAULT path and the T1 S11 interpolated evaluator ONLY
    on an experimental-classified record (T0_2b Sec 2.0's staging table --
    `is_experimental` is exactly the gate that licenses the interpolated
    form)."""
    peak_at_last_step = bool(result.meta.get("peak_at_last_step"))
    peak_record = tea.MetricRecord(
        value=(None if peak_at_last_step else float(result.peak_mgL)),
        units="mg/L",
        algorithm_id=PEAK_ALGORITHM_ID,
        interpolated=False,
        censored=peak_at_last_step,
        tie_broken=False,
    )

    if is_experimental:
        mr = tem.interpolated_t_peak(result.times, result.breakthrough)
        t_peak_record = tea.MetricRecord(
            value=mr.value, units=mr.units, algorithm_id=mr.algorithm_id,
            interpolated=mr.interpolated, censored=mr.censored, tie_broken=mr.tie_broken,
        )
    else:
        never_arrived = math.isnan(result.arrival_day)
        t_peak_record = tea.MetricRecord(
            value=(None if never_arrived else float(result.t_peak)),
            units="d",
            algorithm_id=LEGACY_T_PEAK_ALGORITHM_ID,
            interpolated=False,
            censored=bool(never_arrived or peak_at_last_step),
            tie_broken=False,
        )

    return {"peak_mgL": peak_record, "t_peak": t_peak_record}


# ---------------------------------------------------------------------------
# claim_support_state / envelope, via the REAL S12 evaluator
# ---------------------------------------------------------------------------
def evaluate_claim(
    claim: tcs.Claim,
    series: Sequence[tcs.RunRecord],
    *,
    stopping_rule: str,
) -> Tuple[str, str, tea.SupportEnvelope]:
    """Call the REAL `t1_claim_support_state.claim_support_state` -- never a
    stand-in -- and translate its result into the artifact's own wire values:
    `state=None` (T0.3's machine `null`) becomes the literal STRING `"null"`
    (SCHEMA DECISIONS #7 -- distinct from an absent key), every other state
    passes through unchanged.
    """
    outcome = tcs.claim_support_state(
        claim, series, tcs.canonical_trend_predicate, stopping_rule=stopping_rule
    )
    state = outcome["state"]
    claim_support_state_value = "null" if state is None else state
    reason_code = outcome["reason_code"]
    env_raw = outcome["evidence"]["envelope"]
    envelope = tea.SupportEnvelope(
        grid_series=tuple(env_raw["grid_series"]),
        timestep_series=tuple(env_raw["timestep_series"]),
        stopping_rule=env_raw["stopping_rule"],
        tolerance=env_raw["tolerance"],
        threshold_record_id=env_raw["threshold_record_id"],
    )
    return claim_support_state_value, reason_code, envelope


# ---------------------------------------------------------------------------
# path-leak scan (exit criteria 4/14) -- deliberately EXEMPTS exactly the two
# fields brief Sec 2.3 requires to carry a realpath. Every OTHER field is
# expected to hold no absolute path at all (this module never stores one
# anywhere else); the scan proves that expectation empirically rather than
# leaving it as an unchecked assumption.
# ---------------------------------------------------------------------------
ALLOWED_ABSOLUTE_PATH_FIELDS: frozenset = frozenset({
    ("environment", "mf6_path"),
    ("environment", "triangle_path"),
})

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _looks_like_absolute_path(s: str) -> bool:
    if not isinstance(s, str) or not s:
        return False
    if _WINDOWS_DRIVE_RE.match(s):
        return True
    return s.startswith("/") and len(s) > 1


def find_unexpected_absolute_paths(
    raw: Any, _path: Tuple[str, ...] = ()
) -> List[Tuple[str, str]]:
    """Recursively scan *raw* (a JSON-shaped dict/list/scalar tree) for
    string values that look like an absolute path, EXCEPT at
    `ALLOWED_ABSOLUTE_PATH_FIELDS`. Returns a list of `(dotted_path, value)`
    for every violation -- empty means clean. Covers both exit criterion 4
    (home-directory paths) and 14 (any absolute path, not just `$HOME`)."""
    found: List[Tuple[str, str]] = []
    if isinstance(raw, Mapping):
        for k, v in raw.items():
            found.extend(find_unexpected_absolute_paths(v, _path + (str(k),)))
    elif isinstance(raw, (list, tuple)):
        for v in raw:
            found.extend(find_unexpected_absolute_paths(v, _path))
    elif isinstance(raw, str):
        if _path not in ALLOWED_ABSOLUTE_PATH_FIELDS and _looks_like_absolute_path(raw):
            found.append((".".join(_path), raw))
    return found


# ---------------------------------------------------------------------------
# cross-field invariants (exit criterion 12)
# ---------------------------------------------------------------------------
def check_cross_field_invariants(record: tea.EvidenceRecord) -> None:
    """Raise `ArtifactProducerError` if `solver_status`, `horizon_censored`,
    `cr_capped`, `nstp`, `cr_achieved` or the metrics contradict one another.
    Called defensively at the end of `run_and_build_record`; also exercised
    directly by `test_cross_field_invariants_hold` against a deliberately
    corrupted record."""
    errors: List[str] = []

    if record.solver_status == "failed":
        if record.provenance_valid:
            errors.append("solver_status is 'failed' but provenance_valid is True")
        if record.metrics is not None:
            errors.append("solver_status is 'failed' but metrics is populated")
        for name in ("horizon_censored", "cr_capped", "nstp", "cr_achieved", "ncpl"):
            if getattr(record, name) is not None:
                errors.append(f"solver_status is 'failed' but run_health.{name} is populated")

    if record.cr_capped is not None and record.nstp is not None and record.nstp_cap is not None:
        expected_capped = bool(record.nstp >= record.nstp_cap)
        if bool(record.cr_capped) != expected_capped:
            errors.append(
                f"cr_capped={record.cr_capped!r} disagrees with nstp={record.nstp!r} "
                f">= nstp_cap={record.nstp_cap!r} (expected {expected_capped!r})"
            )

    if record.horizon_censored is not None and record.metrics is not None:
        peak = record.metrics.get("peak_mgL")
        if peak is not None and bool(peak.censored) != bool(record.horizon_censored):
            errors.append(
                f"run_health.horizon_censored={record.horizon_censored!r} disagrees with "
                f"metrics['peak_mgL'].censored={peak.censored!r}"
            )

    if errors:
        raise ArtifactProducerError(
            "evidence record fails cross-field invariant checks: " + "; ".join(errors)
        )


# ---------------------------------------------------------------------------
# raw-dict omission helper -- see module docstring re: SCHEMA DECISIONS #6
# ---------------------------------------------------------------------------
def _delete_path(raw: MutableMapping[str, Any], path: Tuple[str, ...]) -> None:
    """Delete a dotted key from *raw* if present, leaving the parent object
    otherwise untouched. Used to turn a scalar field this producer could NOT
    obtain into a genuinely ABSENT key -- never a JSON `null` standing in for
    "unknown" (brief Sec 2.2: "'unknown' is a placeholder wearing a humble
    face"; `t1_evidence_artifact.py`'s own SCHEMA DECISIONS #6 treats a
    present-null and an absent key as different, and only the latter is
    "missing"). No-ops silently if any intermediate node is absent already.
    """
    node: Any = raw
    for key in path[:-1]:
        if not isinstance(node, MutableMapping) or key not in node:
            return
        node = node[key]
    if isinstance(node, MutableMapping):
        node.pop(path[-1], None)


# ---------------------------------------------------------------------------
# The orchestrator
# ---------------------------------------------------------------------------
def run_and_build_record(
    *,
    run_id: str,
    case_id: str,
    claim_id: str,
    claim_type: str,
    metric: str,
    tolerance: float,
    run_role: str,
    threshold_record_id: Optional[str] = None,
    axis: str = "spatial",
    prior_series: Sequence[tcs.RunRecord] = (),
    stopping_rule: str = "tolerance_reached",
    method_can_answer: bool = True,
    event_occurred: Optional[bool] = None,
    decision: Optional[bool] = None,
    is_feasibility_probe: Optional[bool] = None,
    grid_role: Optional[str] = None,
    counterpart_run_id: Optional[str] = None,
    uncontrolled_counterpart_run_id: Optional[str] = None,
    # -- build_srcpulse_demo passthrough (identical names/defaults) ---------
    mass_g: float = 3.0e5,
    pulse_days: float = 30.0,
    total_days: float = 120.0,
    solubility_mgL: float = 1000.0,
    alpha_L: Optional[float] = None,
    R: float = 1.0,
    rho_b: float = 1800.0,
    lam: float = 0.0,
    case_ws: Optional[Union[str, Path]] = None,
    cr_target: float = 0.9,
    nstp_cap: int = 2000,
    mesh_spec: Optional["tsd.MeshSpec"] = None,
    footprint_radius_m: float = 0.0,
    sink_support_m: float = 0.0,
    courant_profile: str = "legacy_srcpulse",
    force: bool = False,
) -> Tuple[tea.EvidenceRecord, List[Tuple[str, ...]]]:
    """Run `build_srcpulse_demo` for real and assemble a full
    `EvidenceRecord`. Returns `(record, omitted_paths)` -- `omitted_paths` is
    the list of dotted paths this run genuinely could not populate (empty for
    a fully-sourced record); `write_record` (below) deletes exactly those
    paths from the serialised JSON so they are ABSENT, never a placeholder or
    a present null standing in for "unknown".

    `claim_id` is validated against the T0.2a claim inventory
    (`validate_claim_id`) BEFORE any model work -- an unsourceable claim_id is
    a contract error, not something to discover after a multi-minute MF6 run.

    A failed solve is caught here (never propagated as a bare exception) and
    turned into a record with `run_health.solver_status = "failed"`,
    `run_health.provenance_valid = false`, and `metrics` / `run_identity.source_footprint`
    both OMITTED (there is no result to source them from) -- exactly exit
    criterion 9 ("never a silent success").
    """
    validate_claim_id(claim_id)

    resolved_mesh_spec = tsd._resolve_mesh_spec(mesh_spec=mesh_spec)
    marker = compute_experimental_marker(
        cr_target=cr_target, footprint_radius_m=footprint_radius_m,
        sink_support_m=sink_support_m, courant_profile=courant_profile,
        resolved_mesh_spec=resolved_mesh_spec,
    )
    is_experimental = marker["is_experimental"]
    grid_spec = grid_spec_payload(
        resolved_mesh_spec=resolved_mesh_spec, courant_profile=courant_profile, marker=marker
    )

    env = capture_environment()
    src_sha = tsd._src_sha()
    flow_fingerprint = mio.calibrated_flow_fingerprint()
    gis = gis_hashes()
    roster = roster_hash()
    locked_params = dict(tsd.LOCKED_PARAMS)

    omitted: List[Tuple[str, ...]] = []

    ensure_flopy_bindir_on_path()
    try:
        result = tsd.build_srcpulse_demo(
            mass_g=mass_g, pulse_days=pulse_days, total_days=total_days,
            solubility_mgL=solubility_mgL, alpha_L=alpha_L, R=R, rho_b=rho_b, lam=lam,
            case_ws=case_ws, cr_target=cr_target, nstp_cap=nstp_cap,
            mesh_spec=mesh_spec, footprint_radius_m=footprint_radius_m,
            sink_support_m=sink_support_m, courant_profile=courant_profile, force=force,
        )
        solved = True
        solver_status = "solved"
    except Exception:  # noqa: BLE001 -- a failed solve is a RECORDED outcome, not a crash
        result = None
        solved = False
        solver_status = "failed"

    controls = controls_from_inputs(
        sink_support_m=sink_support_m,
        uncontrolled_counterpart_run_id=uncontrolled_counterpart_run_id,
    )

    if solved:
        assert result is not None
        horizon_censored = bool(result.meta.get("peak_at_last_step"))
        cr_capped = bool(result.meta.get("cr_capped"))
        nstp = int(result.meta.get("nstp"))
        cr_achieved = float(result.meta.get("Cr"))
        ncpl = int(result.meta.get("ncpl"))
        metrics = metrics_from_result(result, is_experimental=is_experimental)
        source_footprint = footprint_from_result(result, footprint_radius_m=footprint_radius_m)
        if source_footprint is None:
            omitted.append(("run_identity", "source_footprint"))
            omitted.append(("run_identity", "source_footprint", "algorithm_id"))
            omitted.append(("run_identity", "source_footprint", "radius_m"))
            omitted.append(("run_identity", "source_footprint", "centre_xy_m"))
            omitted.append(("run_identity", "source_footprint", "entries"))
            omitted.append(("run_identity", "source_footprint", "total_rate_g_per_day"))
            omitted.append(("run_identity", "source_footprint", "coverage"))
            omitted.append(("run_identity", "source_footprint", "coverage", "disc_area_m2"))
            omitted.append(("run_identity", "source_footprint", "coverage", "covered_area_m2"))
        metric_value_for_claim: Optional[float] = None
        m = metrics.get(metric)
        if m is not None:
            metric_value_for_claim = m.value
    else:
        horizon_censored = None
        cr_capped = None
        nstp = None
        cr_achieved = None
        ncpl = None
        metrics = None
        source_footprint = None
        metric_value_for_claim = None
        for leaf in ("horizon_censored", "cr_capped", "nstp", "cr_achieved", "ncpl"):
            omitted.append(("run_health", leaf))
        # `metrics` and `run_identity.source_footprint` are OMITTED by simply
        # never being built (record_to_raw_dict only writes those two keys
        # when the record's own attribute is non-None -- see
        # t1_evidence_artifact.record_to_raw_dict) -- no explicit deletion
        # needed for the two nested subtrees themselves.

    run_health = tcs.RunHealth(
        solved=solved, provenance_valid=(solved and source_footprint is not None),
        horizon_censored=bool(horizon_censored) if horizon_censored is not None else False,
    )
    this_run = tcs.RunRecord(
        run_id=run_id, axis=axis, health=run_health, metric_value=metric_value_for_claim,
        event_occurred=event_occurred, decision=decision, method_can_answer=method_can_answer,
        grid_spec=json.dumps(grid_spec, sort_keys=True), cr_target=cr_target,
    )
    series = list(prior_series) + [this_run]
    claim = tcs.Claim(
        claim_type=claim_type, metric=metric, tolerance=tolerance,
        threshold_record_id=threshold_record_id,
    )
    claim_support_state_value, reason_code, envelope = evaluate_claim(
        claim, series, stopping_rule=stopping_rule
    )

    if is_feasibility_probe is None:
        is_feasibility_probe = run_role == "feasibility_probe"

    declared_provenance_valid = solved and source_footprint is not None

    record = tea.EvidenceRecord(
        schema_version=tea.SCHEMA_VERSION,
        producer_module=PRODUCER_MODULE,
        producer_version=PRODUCER_VERSION,
        run_id=run_id,
        grid_spec=grid_spec,
        cr_target=cr_target,
        case_id=case_id,
        nstp_cap=nstp_cap,
        source_footprint=source_footprint,
        controls=controls,
        src_sha=src_sha,
        flow_fingerprint=flow_fingerprint,
        gis_hashes=gis,
        locked_params=locked_params,
        roster_hash=roster,
        os_arch=env.get("os_arch"),
        mf6_path=env.get("mf6_path"),
        mf6_sha256=env.get("mf6_sha256"),
        triangle_path=env.get("triangle_path"),
        triangle_sha256=env.get("triangle_sha256"),
        flopy_version=env.get("flopy_version"),
        numpy_version=env.get("numpy_version"),
        python_version=env.get("python_version"),
        thread_pinning=env.get("thread_pinning"),
        solver_status=solver_status,
        horizon_censored=horizon_censored,
        cr_capped=cr_capped,
        nstp=nstp,
        cr_achieved=cr_achieved,
        ncpl=ncpl,
        metrics=metrics,
        claim_id=claim_id,
        claim_support_state=claim_support_state_value,
        reason_code=reason_code,
        envelope=envelope,
        diagnostics={},  # NAMED GAP #3 -- operator A not wired, see module docstring
        run_role=run_role,
        is_feasibility_probe=is_feasibility_probe,
        grid_role=grid_role,
        counterpart_run_id=counterpart_run_id,
        provenance_valid=declared_provenance_valid,
    )

    if roster is None:
        omitted.append(("fingerprints", "roster_hash"))
    for leaf in ("os_arch", "mf6_path", "mf6_sha256", "triangle_path", "triangle_sha256",
                 "flopy_version", "numpy_version"):
        if env.get(leaf) is None:
            omitted.append(("environment", leaf))

    # 🔴 brief Sec 2.1: `provenance_valid` is COMPUTED FROM THE RECORD'S OWN
    # CONTENTS, never from a hand-written predicate.
    #
    # `declared_provenance_valid` above (`solved and source_footprint is not
    # None`) is a rule ABOUT the run, and a rule can disagree with the record
    # it labels: drop any other required field -- `roster_hash`, an
    # environment leaf -- and that rule still says True while the written
    # record is INCOMPLETE. `T0_2b...` Sec 5.1 defines the predicate the other
    # way round: "a record missing any field above is provenance_valid =
    # false". So derive it from the 36 required paths, evaluated against the
    # record AS IT WILL BE WRITTEN (omissions applied), and AND it with the
    # run-level condition -- a complete record of a failed solve is still not
    # valid evidence.
    _preview = tea.record_to_raw_dict(record)
    for _p in omitted:
        _delete_path(_preview, _p)
    _missing = [p for p in tea.REQUIRED_FIELD_PATHS if not tea._has_path(_preview, p)]
    record = dataclasses.replace(
        record, provenance_valid=(declared_provenance_valid and not _missing)
    )

    check_cross_field_invariants(record)
    return record, omitted


def write_record(
    record: tea.EvidenceRecord, omitted_paths: Sequence[Tuple[str, ...]], path: Union[str, Path]
) -> Dict[str, Any]:
    """Write *record* to *path*, first deleting every path in *omitted_paths*
    from the serialised dict so a field this producer could not source is
    genuinely ABSENT (never a JSON `null` masquerading as "present but
    unknown"). Returns the raw dict actually written (same contract as
    `t1_evidence_artifact.write_record`, which this function deliberately
    does NOT call, precisely because it offers no hook for omission).

    🔴 The artifact is written under *path*'s own directory -- callers MUST
    pass a path inside the run's `case_ws` (brief Sec 2.3: "the producer
    writes ONLY under the run's case_ws"). This function does not enforce
    that itself (it has no notion of "the" case_ws); the companion test file
    asserts it of every path this module's own tests use.
    """
    raw = tea.record_to_raw_dict(record)
    for p in omitted_paths:
        _delete_path(raw, p)
    leaks = find_unexpected_absolute_paths(raw)
    if leaks:
        raise ArtifactProducerError(
            f"refusing to write a record containing unexpected absolute paths: {leaks!r} "
            f"(brief exit criteria 4/14 -- only {sorted(ALLOWED_ABSOLUTE_PATH_FIELDS)} may "
            "carry one)"
        )
    raw["content_hash"] = tea.compute_content_hash(raw)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return raw
