"""
casestudy_canonical_mapping -- M1.2: canonical group -> concession -> scenario
-> contaminant mapping (DATA-ONLY, deterministic, no model run).

Resolves the current two-config mismatch into ONE canonical table. The two
source configs disagree on which concession each group gets:

  * the FLOW config (``case_config.yaml``) assigns concessions via scenario
    ``id`` (a pre-swap integer list);
  * the TRANSPORT config (``case_config_transport.yaml``) assigns a DIFFERENT
    concession set per per-group block.

The canonical rule (per the signed-off vision, see
``DESIGN_DOCS/student_casestudy_M1_2_plan.md``) unifies them **by group index**:

    group N -> concession   = M1.1 doublet_table[N]  (the flow list, G4=b010120)
             -> flow scenario = case_config.yaml scenarios.options[id == N]
             -> contaminant / threshold / reactions / source
                              = case_config_transport.yaml options[id == N]

This is a **deliberate pedagogic re-homing** (each group keeps its existing
flow scenario and its existing contaminant, both moved onto its flow-list
doublet) -- NOT physical inheritance. The doublet does NOT "own" the
contaminant. The resulting difficulty drift is expected and is re-measured /
re-equalized downstream (M3c/M4/M5); M1.2 only fixes the mapping.

IMPORTANT ownership boundaries
------------------------------
* The **canonical concession comes from the M1.1 doublet_table**, NOT from the
  flow config's integer ``concession`` field (which is the pre-swap list; it is
  only sanity-checked to match the doublet_table order except G4).
* This module does **NOT edit either config** -- that is M1.3a's job. It only
  reads them and emits the canonical mapping + ledgers that M1.3a/M1.3b
  reconcile the configs to. The canonical mapping **supersedes** the transport
  config's concession/doublet fields.
* The retardation factor **R is derived downstream** (``R = 1 + rho_b*Kd/n_e``);
  this table stores only the raw reaction fields (Kd, bulk density, lambda,
  half-life), NOT R.

Outputs (all deterministic, provenance-stamped; written under
``PROJECT/workspace/template/``)
  1. ``canonical_mapping.{csv,yaml}`` -- the 9-row mapping (identifiers + exact
     reaction fields + difficulty/source metadata + provenance).
  2. ``repairing_ledger.csv`` -- one row per group: original transport
     concession -> canonical flow concession, whether the contaminant moved
     doublets, and a note (group 5 / b010223 overlap explicitly flagged).
  3. ``threshold_sanity.csv`` -- the deterministic threshold sanity check
     against a FIXED per-contaminant reference-bounds table (flag only, never
     fix).

Re-running yields byte-identical outputs -- no randomness anywhere.

Author: Applied Groundwater Modelling Course (transport track, M1.2).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# repo_root/_SUPPORT/src/casestudy_canonical_mapping.py -> repo_root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATE_DIR = _REPO_ROOT / "PROJECT" / "workspace" / "template"

DEFAULT_FLOW_CONFIG = _TEMPLATE_DIR / "case_config.yaml"
DEFAULT_TRANSPORT_CONFIG = _TEMPLATE_DIR / "case_config_transport.yaml"
DEFAULT_DOUBLET_TABLE = _TEMPLATE_DIR / "doublet_table.csv"

DEFAULT_OUT_CSV = _TEMPLATE_DIR / "canonical_mapping.csv"
DEFAULT_OUT_YAML = _TEMPLATE_DIR / "canonical_mapping.yaml"
DEFAULT_LEDGER_CSV = _TEMPLATE_DIR / "repairing_ledger.csv"
DEFAULT_SANITY_CSV = _TEMPLATE_DIR / "threshold_sanity.csv"

N_GROUPS = 9
_LN2 = math.log(2.0)
_DECAY_LAMBDA_RTOL = 0.02   # lambda ~ ln2 / half_life within 2%
_CHUNK_SIZE = 65536


# ---------------------------------------------------------------------------
# FIXED deterministic threshold reference-bounds table.
#
# Keyed by CAS number (robust to contaminant-name spelling). Each entry:
#   (lo_mg_L, hi_mg_L, basis, extra_note)
# A threshold is FLAGGED if it falls strictly outside the inclusive [lo, hi]
# reference band. Bounds are typical drinking-water / regulatory reference
# ranges; they exist to make "looks inconsistent" byte-deterministic, NOT to
# be a definitive regulatory citation. M1.2 only FLAGS -- the fix is a human
# decision (M1.3a or a separate correction).
#
# Grounded expectation (matches the plan): TCE=0.005 is IN-range (not flagged,
# after the 2026-07-19 correction from 5.0); Atrazine=0.1, Nitrate=25, and
# Chloride=100 are flagged/surfaced; all others sit inside their bands.
# ---------------------------------------------------------------------------
REFERENCE_BOUNDS: Dict[str, Tuple[float, float, str, str]] = {
    "79-01-6":    (0.001,   0.02,   "drinking_water_MCL",
                   "TCE drinking-water standard ~0.005 mg/L (5 ug/L)."),
    "14797-55-8": (1.0,     11.3,   "drinking_water_as_N",
                   "Nitrate reference is as-N (US EPA MCL 10 mg/L-N ~= 44 mg/L as NO3-). "
                   "25 mg/L is plausible as NO3- (~5.6 mg/L-N) -- confirm the as-N vs NO3- basis."),
    "71-43-2":    (0.001,   0.01,   "drinking_water_MCL",
                   "Benzene drinking-water MCL ~0.005 mg/L."),
    "16887-00-6": (200.0,   400.0,  "aesthetic_indicator",
                   "Chloride is an aesthetic/taste indicator (~250 mg/L WHO/EU/CH). "
                   "A 100 mg/L compliance threshold is stricter than typical -- confirm intended basis."),
    "18540-29-9": (0.01,    0.1,    "drinking_water_standard",
                   "Cr(VI)/total-Cr drinking-water standard ~0.05-0.1 mg/L."),
    "335-67-1":   (0.00001, 0.001,  "drinking_water_advisory",
                   "PFOA advisory levels are sub-ug/L."),
    "127-18-4":   (0.001,   0.05,   "drinking_water_MCL",
                   "PCE drinking-water MCL ~0.005-0.04 mg/L."),
    "14798-03-9": (0.1,     1.5,    "drinking_water_guideline",
                   "Ammonium aesthetic/health guideline ~0.5 mg/L."),
    "1912-24-9":  (0.0001,  0.003,  "drinking_water_standard_EU",
                   "Atrazine EU single-pesticide limit 0.1 ug/L = 0.0001 mg/L. "
                   "0.1 mg/L is ~1000x above -- likely too high."),
}


# ---------------------------------------------------------------------------
# GOLDEN acceptance table -- CONTENT, not just shape.
#
# `group == contaminant_id` can pass even if the contaminant CONTENT is swapped
# inside the transport options (e.g. Benzene <-> Chloride blocks exchanged). So
# pin, per group, a tuple of STABLE identifiers that must match exactly:
#   (concession, cas_number, threshold_mg_L, sorption, decay)
# CAS + concession + threshold + reaction booleans are robust to contaminant
# name spelling. A build whose content drifts from this fails acceptance.
# ---------------------------------------------------------------------------
GOLDEN_MAPPING: Dict[int, Tuple[str, str, float, bool, bool]] = {
    0: ("b010210", "79-01-6",    0.005,  False, False),   # TCE, conservative
    1: ("b010219", "14797-55-8", 25.0,   False, False),   # Nitrate, conservative
    2: ("b010201", "71-43-2",    0.005,  False, True),    # Benzene, decay
    3: ("b010236", "16887-00-6", 100.0,  False, False),   # Chloride, conservative
    4: ("b010120", "18540-29-9", 0.1,    True,  False),   # Chromium, sorption
    5: ("b010223", "335-67-1",   0.0002, False, False),   # PFOA, conservative
    6: ("b010227", "127-18-4",   0.04,   True,  False),   # PCE, sorption
    7: ("b010213", "14798-03-9", 0.5,    False, True),    # Ammonium, decay
    8: ("b010207", "1912-24-9",  0.1,    True,  False),   # Atrazine, sorption
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _sha256_file(path: Path) -> str:
    """sha256 hex digest of a file's bytes (streamed)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _flow_concession_str(concession_int: Any) -> str:
    """Flow config stores concession as an integer (e.g. 210); render the
    ``b010XXX`` id used everywhere else (e.g. b010210). Used only for a
    sanity-check against the doublet_table order -- NOT as the canonical id."""
    return f"b010{int(concession_int):03d}"


def _to_native(v: Any) -> Any:
    """Coerce pandas/numpy scalars + NaN to plain Python for stable YAML."""
    if isinstance(v, str):
        return v
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        return v.item()
    return v


# ---------------------------------------------------------------------------
# result container
# ---------------------------------------------------------------------------
@dataclass
class CanonicalMappingResult:
    """The three M1.2 deliverables as DataFrames."""
    mapping: pd.DataFrame       # canonical_mapping (9 rows)
    ledger: pd.DataFrame        # repairing_ledger (9 rows)
    sanity: pd.DataFrame        # threshold_sanity (9 rows; `flagged` marks warnings)


# ---------------------------------------------------------------------------
# source-config extraction (deterministic; keyed by id == group)
# ---------------------------------------------------------------------------
def _index_flow_scenarios(flow_cfg: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    opts = flow_cfg["scenarios"]["options"]
    return {int(o["id"]): o for o in opts}


def _index_transport_scenarios(tr_cfg: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    opts = tr_cfg["transport_scenarios"]["options"]
    return {int(o["id"]): o for o in opts}


def _flow_scenario_params(opt: Dict[str, Any]) -> Dict[str, Any]:
    """Everything type-specific about the flow scenario (drop the identifier /
    label / pre-swap concession fields, keep the physics parameters)."""
    drop = {"id", "concession", "label", "type"}
    return {k: _to_native(v) for k, v in opt.items() if k not in drop}


def _threshold_sanity_row(group: int, contaminant: str, cas: str,
                          threshold: float) -> Dict[str, Any]:
    entry = REFERENCE_BOUNDS.get(cas)
    if entry is None:
        return dict(
            group=group, contaminant=contaminant, cas_number=cas,
            threshold_mg_L=threshold, ref_lo_mg_L=None, ref_hi_mg_L=None,
            basis="UNKNOWN", flagged=True,
            note="no reference bounds for this CAS -- cannot sanity-check; flagged for human review.",
        )
    lo, hi, basis, extra = entry
    flagged = bool(threshold < lo or threshold > hi)
    if flagged:
        note = (f"threshold {threshold} mg/L is OUTSIDE reference band "
                f"[{lo}, {hi}] mg/L ({basis}). {extra}")
    else:
        note = f"within reference band [{lo}, {hi}] mg/L ({basis})."
    return dict(
        group=group, contaminant=contaminant, cas_number=cas,
        threshold_mg_L=threshold, ref_lo_mg_L=lo, ref_hi_mg_L=hi,
        basis=basis, flagged=flagged, note=note,
    )


# ---------------------------------------------------------------------------
# reaction-field self-consistency (raise -- these are acceptance invariants)
# ---------------------------------------------------------------------------
def _check_reactions(group: int, contaminant: str, conservative: bool,
                     sorption: bool, kd: float, bulk_density: Optional[float],
                     decay: bool, lam: float, half_life: Optional[float]) -> None:
    tag = f"group {group} ({contaminant})"

    # conservative <=> neither reaction active
    if conservative != (not sorption and not decay):
        raise ValueError(
            f"{tag}: 'conservative'={conservative} inconsistent with "
            f"sorption={sorption}/decay={decay}.")

    if conservative:
        if kd not in (0, 0.0):
            raise ValueError(f"{tag}: conservative but Kd={kd} != 0.")
        if lam not in (0, 0.0):
            raise ValueError(f"{tag}: conservative but decay lambda={lam} != 0.")

    if sorption:
        if not (kd > 0):
            raise ValueError(f"{tag}: sorption=True but Kd={kd} is not > 0.")
        if bulk_density is None or not (bulk_density > 0):
            raise ValueError(f"{tag}: sorption=True but bulk_density={bulk_density} missing/<=0.")
    else:
        # Inactive-field hygiene: an OFF sorption flag must carry Kd == 0, so a
        # stray Kd can't be silently used downstream to derive retardation.
        # (bulk_density is a general aquifer property -- leave it alone.)
        if kd != 0:
            raise ValueError(
                f"{tag}: sorption=False but Kd={kd} != 0 (stray sorption parameter).")

    if decay:
        if not (lam > 0):
            raise ValueError(f"{tag}: decay=True but lambda={lam} is not > 0.")
        if half_life is None:
            raise ValueError(f"{tag}: decay=True but half_life_days is missing.")
        expected = _LN2 / float(half_life)
        if not math.isclose(lam, expected, rel_tol=_DECAY_LAMBDA_RTOL):
            raise ValueError(
                f"{tag}: decay lambda={lam} inconsistent with half_life={half_life} d "
                f"(ln2/t1/2={expected:.6f}, rtol {_DECAY_LAMBDA_RTOL}).")
    else:
        # Inactive-field hygiene: an OFF decay flag must carry lambda == 0 AND
        # no half_life, so a stray decay constant can't be silently applied.
        if lam != 0:
            raise ValueError(
                f"{tag}: decay=False but lambda={lam} != 0 (stray decay constant).")
        if half_life is not None:
            raise ValueError(
                f"{tag}: decay=False but half_life_days={half_life} is present (should be null).")


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def build_canonical_mapping(flow_config: Optional[Path] = None,
                            transport_config: Optional[Path] = None,
                            doublet_table: Optional[Path] = None,
                            out_csv: Optional[Path] = None,
                            out_yaml: Optional[Path] = None,
                            ledger_csv: Optional[Path] = None,
                            sanity_csv: Optional[Path] = None,
                            write: bool = True) -> CanonicalMappingResult:
    """Build the canonical group->concession->scenario->contaminant mapping.

    Deterministic and side-effect-light: reads the two configs + the M1.1
    doublet_table, unifies them by group index, validates the acceptance
    invariants (raising on any violation), and (by default) writes the three
    deliverables. Does NOT edit either config.

    Parameters
    ----------
    flow_config, transport_config, doublet_table : Path, optional
        Override the input locations (default: PROJECT/workspace/template/...).
    out_csv, out_yaml, ledger_csv, sanity_csv : Path, optional
        Override the output locations.
    write : bool
        If False, compute everything but do not write to disk.

    Returns
    -------
    CanonicalMappingResult
        ``.mapping`` (9 rows), ``.ledger`` (9 rows), ``.sanity`` (9 rows).
    """
    flow_path = Path(flow_config or DEFAULT_FLOW_CONFIG)
    tr_path = Path(transport_config or DEFAULT_TRANSPORT_CONFIG)
    dt_path = Path(doublet_table or DEFAULT_DOUBLET_TABLE)

    flow_cfg = _load_yaml(flow_path)
    tr_cfg = _load_yaml(tr_path)
    dt = pd.read_csv(dt_path)

    flow_sha = _sha256_file(flow_path)
    tr_sha = _sha256_file(tr_path)
    dt_sha = _sha256_file(dt_path)

    # Canonical concession list comes from the doublet_table (G0..G8 order).
    # The `group N -> doublet_table[N]` position rule is only valid if the
    # doublet_table's group indices are EXACTLY {0..8}, unique, and each row's
    # group label is the canonical `f"G{gidx}"`. A duplicate/missing group
    # (e.g. two G3 + no G8) would still give 9 rows / 9 concessions but silently
    # break the positional mapping -- so validate it before trusting the order.
    dt = dt.copy()
    if len(dt) != N_GROUPS:
        raise ValueError(f"doublet_table has {len(dt)} rows, expected {N_GROUPS}.")
    dt["_gidx"] = dt["group"].str.replace("G", "", regex=False).astype(int)
    gidx = list(dt["_gidx"])
    if sorted(gidx) != list(range(N_GROUPS)):
        raise ValueError(
            f"doublet_table group indices {sorted(gidx)} are not exactly {{0..{N_GROUPS - 1}}} "
            "(duplicate or missing group).")
    for grp_label, gi in zip(dt["group"], gidx):
        if grp_label != f"G{gi}":
            raise ValueError(
                f"doublet_table group label {grp_label!r} != canonical 'G{gi}'.")
    dt = dt.sort_values("_gidx").reset_index(drop=True)
    canonical_concessions = list(dt["concession"])
    doublet_set = set(canonical_concessions)
    if len(doublet_set) != N_GROUPS:
        raise ValueError("doublet_table has duplicate concessions across groups.")
    if "b010190" in doublet_set:
        raise ValueError("doublet_table still contains the excluded gallery-only b010190.")

    # --- G4 swap: assert the EXACT identity, not just "may differ". The
    #     canonical G4 concession must be b010120, and the flow config's
    #     pre-swap concession for group 4 must be the b010190 we swapped away
    #     from -- so a wrong G4 cannot slip through. ---
    if canonical_concessions[4] != "b010120":
        raise ValueError(
            f"group 4 canonical concession is {canonical_concessions[4]!r}, expected 'b010120' "
            "(the user-approved swap for gallery-only b010190).")

    flow_opts = _index_flow_scenarios(flow_cfg)
    tr_opts = _index_transport_scenarios(tr_cfg)
    if set(flow_opts) != set(range(N_GROUPS)):
        raise ValueError(f"flow scenario ids {sorted(flow_opts)} != {{0..8}}.")
    if set(tr_opts) != set(range(N_GROUPS)):
        raise ValueError(f"transport scenario ids {sorted(tr_opts)} != {{0..8}}.")

    rows: List[Dict[str, Any]] = []
    ledger_rows: List[Dict[str, Any]] = []
    sanity_rows: List[Dict[str, Any]] = []

    for group in range(N_GROUPS):
        concession = canonical_concessions[group]
        flow_opt = flow_opts[group]
        tr_opt = tr_opts[group]

        # --- sanity-check the pre-swap flow concession matches doublet order.
        #     Group 4 is the ONE swap point: the flow config carries EITHER the
        #     pre-swap b010190 (before M1.3a reconciles the configs) OR the
        #     canonical b010120 (after M1.3a). Both are legitimate swap
        #     endpoints; any OTHER value is a wrong G4. After reconcile there is
        #     zero G4-exception mismatch (flow[4] == canonical). ---
        flow_concession_preswap = _flow_concession_str(flow_opt["concession"])
        if group == 4:
            if flow_concession_preswap not in ("b010190", "b010120"):
                raise ValueError(
                    f"group 4: flow-config concession is {flow_concession_preswap!r}, expected "
                    "'b010190' (pre-swap) or 'b010120' (post-M1.3a reconcile).")
        elif flow_concession_preswap != concession:
            raise ValueError(
                f"group {group}: flow-config concession {flow_concession_preswap} "
                f"!= doublet_table concession {concession} (only G4 may differ).")

        props = tr_opt.get("properties", {}) or {}
        transport = tr_opt.get("transport", {}) or {}
        source = tr_opt.get("source", {}) or {}
        monitoring = tr_opt.get("monitoring", {}) or {}
        loc = source.get("location", {}) or {}

        contaminant = tr_opt["contaminant"]
        cas = str(props.get("cas_number"))
        conservative = bool(props.get("conservative", False))
        sorption = bool(transport.get("sorption", False))
        kd = float(transport.get("distribution_coefficient_mL_g", 0.0) or 0.0)
        bulk_density = _to_native(transport.get("bulk_density_kg_m3"))
        decay = bool(transport.get("decay", False))
        lam = float(transport.get("first_order_decay_constant_1_per_day", 0.0) or 0.0)
        half_life = _to_native(transport.get("half_life_days"))
        threshold = float(monitoring["threshold_mg_L"])

        # --- reaction self-consistency (raises on violation) ---
        _check_reactions(group, contaminant, conservative, sorption, kd,
                         bulk_density, decay, lam, half_life)

        # --- threshold sanity (flag only) ---
        sanity_rows.append(_threshold_sanity_row(group, contaminant, cas, threshold))

        # --- flow scenario ---
        flow_type = flow_opt["type"]
        flow_params = _flow_scenario_params(flow_opt)

        # --- source metadata (concentration-or-mass field + unit) ---
        if "concentration_mg_L" in source:
            source_value = _to_native(source["concentration_mg_L"])
            source_value_field = "concentration_mg_L"
            source_value_unit = "mg_L"
        elif "mass_g" in source:
            source_value = _to_native(source["mass_g"])
            source_value_field = "mass_g"
            source_value_unit = "g"
        else:
            source_value = None
            source_value_field = None
            source_value_unit = None

        # --- original transport concession (superseded) + ledger ---
        original_transport_concession = str(tr_opt.get("concession"))
        changed = bool(original_transport_concession != concession)
        note = (f"contaminant '{contaminant}' re-homed from transport concession "
                f"{original_transport_concession} onto canonical flow doublet {concession} "
                "(pedagogic re-homing, not physical inheritance).")
        if group == 5:
            note += (" NOTE: canonical concession b010223 is ALSO the transport config's "
                     "id4 (Chromium) concession -- b010223 appears in both source lists; "
                     "group 5 canonically carries PFOA on this doublet.")
        ledger_rows.append(dict(
            group=group,
            contaminant=contaminant,
            original_transport_concession=original_transport_concession,
            canonical_flow_concession=concession,
            changed=changed,
            note=note,
        ))

        rows.append(dict(
            # --- identifiers ---
            group=group,
            concession=concession,
            flow_scenario_id=group,
            contaminant_id=int(tr_opt["id"]),
            flow_scenario_type=flow_type,
            flow_scenario_params=json.dumps(flow_params, sort_keys=True),
            contaminant=contaminant,
            cas_number=cas,
            threshold_mg_L=threshold,
            threshold_basis=REFERENCE_BOUNDS.get(cas, (None, None, "UNKNOWN", ""))[2],
            # --- exact reaction schema (R derived downstream, NOT here) ---
            conservative=conservative,
            sorption=sorption,
            distribution_coefficient_mL_g=kd,
            bulk_density_kg_m3=bulk_density,
            decay=decay,
            first_order_decay_constant_1_per_day=lam,
            half_life_days=half_life,
            # --- difficulty / source metadata (for M3c/M4/M5) ---
            porosity=_to_native(transport.get("porosity")),
            longitudinal_dispersivity_m=_to_native(transport.get("longitudinal_dispersivity_m")),
            transverse_dispersivity_m=_to_native(transport.get("transverse_dispersivity_m")),
            vertical_dispersivity_m=_to_native(transport.get("vertical_dispersivity_m")),
            molecular_diffusion_m2_s=_to_native(transport.get("molecular_diffusion_m2_s")),
            solubility_mg_L=_to_native(props.get("solubility_mg_L")),
            source_type=_to_native(source.get("type")),
            source_release_type=_to_native(source.get("release_type")),
            source_easting_offset_m=_to_native(loc.get("easting")),
            source_northing_offset_m=_to_native(loc.get("northing")),
            source_layer=_to_native(loc.get("layer")),
            source_start_time_days=_to_native(source.get("start_time_days")),
            source_duration_days=_to_native(source.get("duration_days")),
            source_value=source_value,
            source_value_field=source_value_field,
            source_value_unit=source_value_unit,
            # --- provenance (BOTH configs + doublet_table) ---
            flow_config_file=str(flow_path),
            flow_config_sha256=flow_sha,
            transport_config_file=str(tr_path),
            transport_config_sha256=tr_sha,
            doublet_table_file=str(dt_path),
            doublet_table_sha256=dt_sha,
        ))

    mapping_columns = [
        "group", "concession", "flow_scenario_id", "contaminant_id",
        "flow_scenario_type", "flow_scenario_params",
        "contaminant", "cas_number", "threshold_mg_L", "threshold_basis",
        "conservative", "sorption", "distribution_coefficient_mL_g", "bulk_density_kg_m3",
        "decay", "first_order_decay_constant_1_per_day", "half_life_days",
        "porosity", "longitudinal_dispersivity_m", "transverse_dispersivity_m",
        "vertical_dispersivity_m", "molecular_diffusion_m2_s", "solubility_mg_L",
        "source_type", "source_release_type", "source_easting_offset_m",
        "source_northing_offset_m", "source_layer", "source_start_time_days",
        "source_duration_days", "source_value", "source_value_field", "source_value_unit",
        "flow_config_file", "flow_config_sha256", "transport_config_file",
        "transport_config_sha256", "doublet_table_file", "doublet_table_sha256",
    ]
    ledger_columns = [
        "group", "contaminant", "original_transport_concession",
        "canonical_flow_concession", "changed", "note",
    ]
    sanity_columns = [
        "group", "contaminant", "cas_number", "threshold_mg_L",
        "ref_lo_mg_L", "ref_hi_mg_L", "basis", "flagged", "note",
    ]

    mapping = pd.DataFrame(rows, columns=mapping_columns)
    ledger = pd.DataFrame(ledger_rows, columns=ledger_columns)
    sanity = pd.DataFrame(sanity_rows, columns=sanity_columns)

    # STATE-AWARE reconcile check (not broadly permissive): the config pair is
    # valid in exactly TWO states, and the flow-G4 concession must AGREE with
    # the re-homing ledger. Any third/mixed state fails.
    #   * PRE-reconcile : flow[4] == b010190 AND every group changed (re-homed).
    #   * POST-reconcile: flow[4] == b010120 AND no group changed (already canonical).
    g4_flow = _flow_concession_str(flow_opts[4]["concession"])
    n_changed = int(ledger["changed"].sum())
    pre = (g4_flow == "b010190" and n_changed == N_GROUPS)
    post = (g4_flow == "b010120" and n_changed == 0)
    if not (pre or post):
        raise ValueError(
            f"config pair is in an unexpected reconcile state: flow[4]={g4_flow!r}, "
            f"changed={n_changed}/{N_GROUPS}. Expected either PRE-reconcile "
            "(flow[4]=b010190, all 9 changed) or POST-reconcile (flow[4]=b010120, 0 changed).")

    _assert_acceptance(mapping, ledger, sanity, doublet_set)

    if write:
        _write_outputs(mapping, ledger, sanity,
                       out_csv=out_csv or DEFAULT_OUT_CSV,
                       out_yaml=out_yaml or DEFAULT_OUT_YAML,
                       ledger_csv=ledger_csv or DEFAULT_LEDGER_CSV,
                       sanity_csv=sanity_csv or DEFAULT_SANITY_CSV)

    return CanonicalMappingResult(mapping=mapping, ledger=ledger, sanity=sanity)


# ---------------------------------------------------------------------------
# acceptance invariants (enforced on every build)
# ---------------------------------------------------------------------------
def _assert_acceptance(mapping: pd.DataFrame, ledger: pd.DataFrame,
                       sanity: pd.DataFrame, doublet_set: set) -> None:
    assert len(mapping) == N_GROUPS, f"expected {N_GROUPS} mapping rows, got {len(mapping)}"
    assert len(ledger) == N_GROUPS, f"expected {N_GROUPS} ledger rows, got {len(ledger)}"
    assert len(sanity) == N_GROUPS, f"expected {N_GROUPS} sanity rows, got {len(sanity)}"

    # every concession is a real doublet_table concession; no b010190
    assert set(mapping["concession"]).issubset(doublet_set), "orphaned concession not in doublet_table"
    assert "b010190" not in set(mapping["concession"]), "b010190 leaked into the mapping"
    # no stray pre-swap b0101xx transport concessions leaked in as the canonical id
    assert mapping["concession"].nunique() == N_GROUPS, "duplicate concession across groups"

    # group == flow_scenario_id == contaminant_id, ids exactly {0..8}, no dups
    assert list(mapping["group"]) == list(range(N_GROUPS)), "groups not 0..8 in order"
    assert (mapping["group"] == mapping["flow_scenario_id"]).all(), "group != flow_scenario_id"
    assert (mapping["group"] == mapping["contaminant_id"]).all(), "group != contaminant_id"
    assert set(mapping["flow_scenario_id"]) == set(range(N_GROUPS)), "flow ids != {0..8}"
    assert set(mapping["contaminant_id"]) == set(range(N_GROUPS)), "contaminant ids != {0..8}"
    assert mapping["flow_scenario_id"].nunique() == N_GROUPS, "duplicate flow scenario id"
    assert mapping["contaminant_id"].nunique() == N_GROUPS, "duplicate contaminant id"

    # every row has a flow scenario type + params present, contaminant + threshold
    assert mapping["flow_scenario_type"].notna().all(), "missing flow scenario type"
    assert (mapping["flow_scenario_params"].str.len() > 2).all(), "empty flow scenario params"
    assert mapping["contaminant"].notna().all(), "missing contaminant"
    assert mapping["threshold_mg_L"].notna().all(), "missing threshold"

    # GOLDEN content check: per group, (concession, CAS, threshold, sorption,
    # decay) must match the pinned table exactly. Catches a swapped-contaminant
    # / swapped-threshold that the id-shape checks above would miss.
    by_group = mapping.set_index("group")
    for g, (concession, cas, thr, sorb, dec) in GOLDEN_MAPPING.items():
        row = by_group.loc[g]
        actual = (row["concession"], str(row["cas_number"]), float(row["threshold_mg_L"]),
                  bool(row["sorption"]), bool(row["decay"]))
        expected = (concession, cas, float(thr), sorb, dec)
        assert actual == expected, (
            f"group {g}: golden content mismatch -- got {actual}, expected {expected}")

    # ledger: 9 rows; `changed` == (original != canonical) row-wise (the
    # pre/post reconcile STATE is enforced upstream in build_canonical_mapping).
    # Group-5's b010223 overlap is flagged regardless of state.
    exp_changed = ledger["original_transport_concession"] != ledger["canonical_flow_concession"]
    assert (ledger["changed"] == exp_changed).all(), "`changed` not consistent with orig vs canonical"
    g5 = ledger.loc[ledger["group"] == 5].iloc[0]
    assert g5["canonical_flow_concession"] == "b010223", "group 5 canonical concession != b010223"
    assert "b010223" in g5["note"], "group 5 ledger note must flag the b010223 overlap"

    # threshold sanity ran + recorded for all; the plan's expected flags hold
    assert sanity["flagged"].notna().all(), "sanity check did not run for some row"
    flagged = set(sanity.loc[sanity["flagged"], "contaminant"])
    # TCE must NOT be flagged (post 0.005 correction); Atrazine/Nitrate/Chloride must be.
    assert not any("TCE" in c for c in flagged), "TCE unexpectedly flagged (should be clear at 0.005)"
    assert any("Atrazine" in c for c in flagged), "Atrazine should be flagged (0.1 mg/L too high)"
    assert any("Nitrate" in c for c in flagged), "Nitrate 25 should be surfaced"
    assert any("Chloride" in c for c in flagged), "Chloride 100 should be surfaced"


# ---------------------------------------------------------------------------
# deterministic writers
# ---------------------------------------------------------------------------
def _df_to_native_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    records = []
    for row in df.to_dict("records"):
        records.append({k: _to_native(v) for k, v in row.items()})
    return records


def _write_outputs(mapping: pd.DataFrame, ledger: pd.DataFrame, sanity: pd.DataFrame,
                   out_csv: Path, out_yaml: Path, ledger_csv: Path, sanity_csv: Path) -> None:
    for p in (out_csv, out_yaml, ledger_csv, sanity_csv):
        Path(p).parent.mkdir(parents=True, exist_ok=True)

    # Pin the CSV byte contract for cross-version determinism:
    #   * lineterminator="\n" -> no platform CRLF drift;
    #   * float_format="%.12g" -> 12 significant figures preserves every value
    #     (0.1 m coords, Q, thresholds like 0.0002) with a stable repr that does
    #     not vary across pandas/numpy versions.
    _csv_kw = dict(index=False, lineterminator="\n", float_format="%.12g")
    mapping.to_csv(out_csv, **_csv_kw)
    ledger.to_csv(ledger_csv, **_csv_kw)
    sanity.to_csv(sanity_csv, **_csv_kw)

    # YAML mirror of the canonical mapping (with flow_scenario_params re-expanded
    # to a native dict for readability), plus the ledger + sanity as native lists.
    mapping_records = _df_to_native_records(mapping)
    for rec in mapping_records:
        rec["flow_scenario_params"] = json.loads(rec["flow_scenario_params"])
    payload = {
        "canonical_mapping": mapping_records,
        "repairing_ledger": _df_to_native_records(ledger),
        "threshold_sanity": _df_to_native_records(sanity),
    }
    with open(out_yaml, "w") as fh:
        yaml.safe_dump(payload, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    result = build_canonical_mapping(write=True)
    with pd.option_context("display.max_columns", None, "display.width", 240):
        print("=== canonical_mapping ===")
        print(result.mapping[["group", "concession", "flow_scenario_type",
                              "contaminant", "threshold_mg_L", "conservative",
                              "sorption", "decay"]].to_string(index=False))
        print("\n=== repairing_ledger ===")
        print(result.ledger[["group", "contaminant", "original_transport_concession",
                             "canonical_flow_concession", "changed"]].to_string(index=False))
        print("\n=== threshold_sanity (flagged only) ===")
        fl = result.sanity[result.sanity["flagged"]]
        print(fl[["group", "contaminant", "threshold_mg_L", "ref_lo_mg_L",
                  "ref_hi_mg_L"]].to_string(index=False))
