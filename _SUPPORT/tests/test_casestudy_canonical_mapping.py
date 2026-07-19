"""
Tests for casestudy_canonical_mapping (M1.2 -- canonical group -> concession ->
scenario -> contaminant mapping).

Data-only, deterministic, no model run. Reads the two committed configs
(``case_config.yaml`` / ``case_config_transport.yaml``) and the M1.1
``doublet_table.csv``, all under ``PROJECT/workspace/template/``. Fast.

Run with: uv run pytest _SUPPORT/tests/test_casestudy_canonical_mapping.py -v
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import casestudy_canonical_mapping as ccm  # noqa: E402

N = ccm.N_GROUPS

# Grounded expectation (from the plan's canonical table).
EXPECTED_CONCESSIONS = [
    "b010210", "b010219", "b010201", "b010236", "b010120",
    "b010223", "b010227", "b010213", "b010207",
]
EXPECTED_FLOW_TYPES = [
    "chd_head_change", "river_conductance", "river_conductance", "recharge_scale",
    "recharge_scale", "river_stage", "river_width_and_stage",
    "aquifer_transmissivity", "aquifer_transmissivity",
]


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def result() -> ccm.CanonicalMappingResult:
    """Build once (in-memory, no disk write) and reuse."""
    return ccm.build_canonical_mapping(write=False)


@pytest.fixture(scope="module")
def mapping(result) -> pd.DataFrame:
    return result.mapping


@pytest.fixture(scope="module")
def ledger(result) -> pd.DataFrame:
    return result.ledger


@pytest.fixture(scope="module")
def sanity(result) -> pd.DataFrame:
    return result.sanity


# ---------------------------------------------------------------------------
# shape / identity / by-group-index rule
# ---------------------------------------------------------------------------
def test_nine_rows(mapping, ledger, sanity):
    assert len(mapping) == N
    assert len(ledger) == N
    assert len(sanity) == N


def test_canonical_concessions_from_doublet_table(mapping):
    assert list(mapping["concession"]) == EXPECTED_CONCESSIONS


def test_g4_is_b010120_and_no_b010190(mapping):
    assert mapping.loc[mapping["group"] == 4, "concession"].iloc[0] == "b010120"
    assert "b010190" not in set(mapping["concession"])


def test_flow_scenario_types_by_group(mapping):
    assert list(mapping["flow_scenario_type"]) == EXPECTED_FLOW_TYPES


def test_group_equals_flow_id_equals_contaminant_id(mapping):
    assert list(mapping["group"]) == list(range(N))
    assert (mapping["group"] == mapping["flow_scenario_id"]).all()
    assert (mapping["group"] == mapping["contaminant_id"]).all()


def test_ids_are_exactly_0_to_8_no_duplicates(mapping):
    assert set(mapping["flow_scenario_id"]) == set(range(N))
    assert set(mapping["contaminant_id"]) == set(range(N))
    assert mapping["flow_scenario_id"].nunique() == N
    assert mapping["contaminant_id"].nunique() == N
    assert mapping["concession"].nunique() == N


def test_each_concession_in_doublet_table(mapping):
    dt = pd.read_csv(ccm.DEFAULT_DOUBLET_TABLE)
    doublet_set = set(dt["concession"])
    assert set(mapping["concession"]).issubset(doublet_set)


def test_no_orphaned_transport_concessions(mapping):
    """The pre-swap transport concessions (b010205, b010196, ... b010199) must
    NOT appear as canonical concessions -- only the flow-list doublets do."""
    transport_only = {"b010205", "b010196", "b010185", "b010211", "b010200",
                      "b010224", "b010230", "b010199"}
    assert transport_only.isdisjoint(set(mapping["concession"]))


# ---------------------------------------------------------------------------
# flow scenario params present per type
# ---------------------------------------------------------------------------
def test_flow_scenario_params_present_and_typed(mapping):
    for _, row in mapping.iterrows():
        params = json.loads(row["flow_scenario_params"])
        assert isinstance(params, dict) and params, f"group {row['group']}: empty params"
        t = row["flow_scenario_type"]
        if t == "chd_head_change":
            assert "chd_head_change_m" in params
        elif t == "river_conductance":
            assert "conductance_factor" in params
        elif t == "recharge_scale":
            assert "recharge_factor" in params
        elif t == "river_stage":
            assert "stage_change_m" in params
        elif t == "river_width_and_stage":
            assert "width_factor" in params and "stage_change_factor" in params
        elif t == "aquifer_transmissivity":
            assert "transmissivity_factor" in params


# ---------------------------------------------------------------------------
# reaction-field self-consistency (the exact config schema)
# ---------------------------------------------------------------------------
def test_reaction_fields_self_consistent(mapping):
    for _, row in mapping.iterrows():
        conservative = bool(row["conservative"])
        sorption = bool(row["sorption"])
        decay = bool(row["decay"])
        kd = float(row["distribution_coefficient_mL_g"])
        lam = float(row["first_order_decay_constant_1_per_day"])
        half_life = row["half_life_days"]

        assert conservative == (not sorption and not decay)
        if conservative:
            assert kd == 0.0
            assert lam == 0.0
        if sorption:
            assert kd > 0.0
            assert pd.notna(row["bulk_density_kg_m3"]) and row["bulk_density_kg_m3"] > 0
        if decay:
            assert lam > 0.0
            assert pd.notna(half_life)
            assert math.isclose(lam, math.log(2) / float(half_life),
                                rel_tol=ccm._DECAY_LAMBDA_RTOL)


def test_r_factor_not_stored(mapping):
    """R is derived downstream -- it must NOT be a column here."""
    for banned in ("R", "retardation", "retardation_factor"):
        assert banned not in mapping.columns


def test_decay_and_sorption_groups(mapping):
    decay_groups = set(mapping.loc[mapping["decay"], "group"])
    sorb_groups = set(mapping.loc[mapping["sorption"], "group"])
    assert decay_groups == {2, 7}          # Benzene, Ammonium
    assert sorb_groups == {4, 6, 8}        # Chromium, PCE, Atrazine


# ---------------------------------------------------------------------------
# difficulty / source metadata carried forward
# ---------------------------------------------------------------------------
def test_source_and_difficulty_metadata_present(mapping):
    for col in ("porosity", "longitudinal_dispersivity_m", "transverse_dispersivity_m",
                "vertical_dispersivity_m", "molecular_diffusion_m2_s", "solubility_mg_L",
                "source_type", "source_release_type", "source_easting_offset_m",
                "source_northing_offset_m", "source_layer", "source_duration_days",
                "source_value", "source_value_field", "source_value_unit"):
        assert col in mapping.columns
    # every group has a source type + release type + a value
    assert mapping["source_type"].notna().all()
    assert mapping["source_release_type"].notna().all()
    assert mapping["source_value"].notna().all()
    assert (mapping["source_value_unit"] == "mg_L").all()


def test_source_offsets_match_transport_config(mapping):
    """Spot-check a couple of source offsets came through from the transport
    config verbatim (group 0 TCE: +51 / -77; group 8 Atrazine: -53 / -82)."""
    g0 = mapping.loc[mapping["group"] == 0].iloc[0]
    assert g0["source_easting_offset_m"] == 51.0 and g0["source_northing_offset_m"] == -77.0
    g8 = mapping.loc[mapping["group"] == 8].iloc[0]
    assert g8["source_easting_offset_m"] == -53.0 and g8["source_northing_offset_m"] == -82.0


# ---------------------------------------------------------------------------
# provenance (both configs + doublet_table)
# ---------------------------------------------------------------------------
def test_provenance_stamped(mapping):
    for col in ("flow_config_sha256", "transport_config_sha256", "doublet_table_sha256"):
        assert (mapping[col].str.len() == 64).all()
    assert mapping["flow_config_file"].str.endswith("case_config.yaml").all()
    assert mapping["transport_config_file"].str.endswith("case_config_transport.yaml").all()
    assert mapping["doublet_table_file"].str.endswith("doublet_table.csv").all()


def test_provenance_hashes_match_actual_files(mapping):
    row = mapping.iloc[0]
    assert ccm._sha256_file(Path(row["flow_config_file"])) == row["flow_config_sha256"]
    assert ccm._sha256_file(Path(row["transport_config_file"])) == row["transport_config_sha256"]
    assert ccm._sha256_file(Path(row["doublet_table_file"])) == row["doublet_table_sha256"]


# ---------------------------------------------------------------------------
# repairing_ledger
#
# The repairing_ledger records the ONE-TIME pre->post re-homing. The COMMITTED
# repairing_ledger.csv is the frozen record built pre-reconcile (all
# changed=True, originals = the old transport concessions). The in-memory
# `ledger` fixture, by contrast, tracks the LIVE config state: once M1.3a has
# rewritten the transport concessions to canonical, its `original` == canonical
# and `changed` == False. So the re-homing facts are asserted against the
# committed frozen CSV; state-independent facts use the live fixture.
# ---------------------------------------------------------------------------
def _committed_repairing_ledger() -> pd.DataFrame:
    p = ccm.DEFAULT_OUT_CSV.with_name("repairing_ledger.csv")
    return pd.read_csv(p)


def test_committed_ledger_nine_rows_all_changed():
    led = _committed_repairing_ledger()
    assert len(led) == N
    assert bool(led["changed"].all()), "the frozen pre-reconcile ledger records every re-homing"


def test_committed_ledger_original_transport_concessions():
    led = _committed_repairing_ledger()
    expected = {
        0: "b010205", 1: "b010196", 2: "b010185", 3: "b010211", 4: "b010223",
        5: "b010200", 6: "b010224", 7: "b010230", 8: "b010199",
    }
    for g, orig in expected.items():
        assert led.loc[led["group"] == g, "original_transport_concession"].iloc[0] == orig


def test_ledger_changed_consistent_with_orig_vs_canonical(ledger):
    """State-independent: `changed` must equal (original != canonical) row-wise,
    whether the live config is pre- or post-reconcile."""
    exp = ledger["original_transport_concession"] != ledger["canonical_flow_concession"]
    assert (ledger["changed"] == exp).all()


def test_ledger_group5_b010223_overlap_flagged(ledger):
    g5 = ledger.loc[ledger["group"] == 5].iloc[0]
    assert g5["canonical_flow_concession"] == "b010223"
    assert g5["contaminant"].startswith("PFOA")
    assert "b010223" in g5["note"]
    assert "Chromium" in g5["note"] or "id4" in g5["note"]


# ---------------------------------------------------------------------------
# threshold sanity (fixed deterministic bounds table)
# ---------------------------------------------------------------------------
def test_threshold_sanity_ran_for_every_group(sanity):
    assert len(sanity) == N
    assert sanity["flagged"].notna().all()


def test_tce_not_flagged_after_correction(sanity):
    tce = sanity.loc[sanity["contaminant"].str.contains("TCE")].iloc[0]
    assert tce["threshold_mg_L"] == 0.005
    assert bool(tce["flagged"]) is False


def test_atrazine_flagged(sanity):
    atr = sanity.loc[sanity["contaminant"].str.contains("Atrazine")].iloc[0]
    assert atr["threshold_mg_L"] == 0.1
    assert bool(atr["flagged"]) is True


def test_nitrate_and_chloride_surfaced(sanity):
    nit = sanity.loc[sanity["contaminant"].str.contains("Nitrate")].iloc[0]
    chl = sanity.loc[sanity["contaminant"].str.contains("Chloride")].iloc[0]
    assert bool(nit["flagged"]) is True
    assert bool(chl["flagged"]) is True


def test_exact_flagged_set(sanity):
    """Only Nitrate, Chloride, and Atrazine should flag (all others in-band)."""
    flagged = set(sanity.loc[sanity["flagged"], "group"])
    assert flagged == {1, 3, 8}


def test_reference_bounds_documented_for_every_cas(mapping):
    for cas in mapping["cas_number"]:
        assert cas in ccm.REFERENCE_BOUNDS, f"no reference bounds for CAS {cas}"


def test_threshold_sanity_row_helper_flags_outside_band():
    # TCE CAS, 5.0 mg/L (the pre-correction value) -> must flag high.
    row = ccm._threshold_sanity_row(0, "Trichloroethylene (TCE)", "79-01-6", 5.0)
    assert row["flagged"] is True
    # 0.005 -> not flagged
    row2 = ccm._threshold_sanity_row(0, "Trichloroethylene (TCE)", "79-01-6", 0.005)
    assert row2["flagged"] is False


# ---------------------------------------------------------------------------
# reaction-consistency guard raises on a corrupted config
# ---------------------------------------------------------------------------
def test_inconsistent_decay_raises(monkeypatch, tmp_path):
    """A decay=True group whose lambda disagrees with half_life must raise."""
    orig_load = ccm._load_yaml

    def _corrupt(path):
        cfg = orig_load(path)
        if Path(path).name == "case_config_transport.yaml":
            for opt in cfg["transport_scenarios"]["options"]:
                if opt["id"] == 2:  # Benzene, decay
                    opt["transport"]["half_life_days"] = 5.0  # inconsistent with lambda 0.005
        return cfg

    monkeypatch.setattr(ccm, "_load_yaml", _corrupt)
    with pytest.raises(ValueError, match="inconsistent with half_life"):
        ccm.build_canonical_mapping(write=False)


def test_sorption_without_kd_raises(monkeypatch):
    orig_load = ccm._load_yaml

    def _corrupt(path):
        cfg = orig_load(path)
        if Path(path).name == "case_config_transport.yaml":
            for opt in cfg["transport_scenarios"]["options"]:
                if opt["id"] == 4:  # Chromium, sorption
                    opt["transport"]["distribution_coefficient_mL_g"] = 0.0
        return cfg

    monkeypatch.setattr(ccm, "_load_yaml", _corrupt)
    with pytest.raises(ValueError, match="Kd"):
        ccm.build_canonical_mapping(write=False)


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------
def test_determinism_in_memory():
    r1 = ccm.build_canonical_mapping(write=False)
    r2 = ccm.build_canonical_mapping(write=False)
    pd.testing.assert_frame_equal(r1.mapping, r2.mapping)
    pd.testing.assert_frame_equal(r1.ledger, r2.ledger)
    pd.testing.assert_frame_equal(r1.sanity, r2.sanity)


def test_determinism_on_disk_byte_identical(tmp_path):
    kw = dict(
        out_csv=tmp_path / "canonical_mapping.csv",
        out_yaml=tmp_path / "canonical_mapping.yaml",
        ledger_csv=tmp_path / "repairing_ledger.csv",
        sanity_csv=tmp_path / "threshold_sanity.csv",
        write=True,
    )
    ccm.build_canonical_mapping(**kw)
    first = {p: (tmp_path / p).read_bytes() for p in
             ("canonical_mapping.csv", "canonical_mapping.yaml",
              "repairing_ledger.csv", "threshold_sanity.csv")}
    ccm.build_canonical_mapping(**kw)
    for name, data in first.items():
        assert (tmp_path / name).read_bytes() == data, f"{name} not byte-identical on rebuild"


def test_committed_deliverables_exist_and_parse():
    assert ccm.DEFAULT_OUT_CSV.exists(), "canonical_mapping.csv missing -- regenerate it"
    assert ccm.DEFAULT_LEDGER_CSV.exists(), "repairing_ledger.csv missing"
    assert ccm.DEFAULT_SANITY_CSV.exists(), "threshold_sanity.csv missing"
    m = pd.read_csv(ccm.DEFAULT_OUT_CSV)
    assert len(m) == N
    assert list(m["concession"]) == EXPECTED_CONCESSIONS
    if ccm.DEFAULT_OUT_YAML.exists():
        import yaml
        with open(ccm.DEFAULT_OUT_YAML) as fh:
            data = yaml.safe_load(fh)
        assert len(data["canonical_mapping"]) == N
        assert len(data["repairing_ledger"]) == N
        assert len(data["threshold_sanity"]) == N
        # flow_scenario_params re-expanded to a native dict in the YAML mirror
        assert isinstance(data["canonical_mapping"][0]["flow_scenario_params"], dict)


# ===========================================================================
# Codex fix 1: doublet_table group validation (exact {0..8}, unique, G{i} labels)
# ===========================================================================
def _write_doublet_variant(tmp_path, mutate) -> Path:
    """Copy the real doublet_table, apply *mutate(df)*, write to tmp, return path."""
    df = pd.read_csv(ccm.DEFAULT_DOUBLET_TABLE).copy()
    df = mutate(df)
    p = tmp_path / "doublet_table.csv"
    df.to_csv(p, index=False)
    return p


def test_doublet_duplicate_group_raises(tmp_path):
    def _dup(df):
        df.loc[df["group"] == "G8", "group"] = "G3"  # now two G3, no G8
        return df
    p = _write_doublet_variant(tmp_path, _dup)
    with pytest.raises(ValueError, match=r"not exactly \{0\.\.8\}"):
        ccm.build_canonical_mapping(doublet_table=p, write=False)


def test_doublet_missing_group_via_short_table_raises(tmp_path):
    def _drop(df):
        return df[df["group"] != "G8"]  # only 8 rows
    p = _write_doublet_variant(tmp_path, _drop)
    with pytest.raises(ValueError, match="expected 9"):
        ccm.build_canonical_mapping(doublet_table=p, write=False)


def test_doublet_wrong_group_label_raises(tmp_path):
    def _relabel(df):
        # Zero-pad one label: "G03" still parses to index 3 (so indices remain
        # {0..8}), but "G03" != canonical "G3" -> the explicit label guard fires.
        df["group"] = df["group"].replace({"G3": "G03"})
        return df
    p = _write_doublet_variant(tmp_path, _relabel)
    with pytest.raises(ValueError, match="!= canonical 'G3'"):
        ccm.build_canonical_mapping(doublet_table=p, write=False)


# ===========================================================================
# Codex fix 2: explicit G4 swap assertions
# ===========================================================================
def test_g4_wrong_concession_raises(tmp_path):
    def _swap_g4(df):
        df.loc[df["group"] == "G4", "concession"] = "b010999"  # not b010120
        return df
    p = _write_doublet_variant(tmp_path, _swap_g4)
    with pytest.raises(ValueError, match="expected 'b010120'"):
        ccm.build_canonical_mapping(doublet_table=p, write=False)


def test_g4_flow_preswap_must_be_190(monkeypatch):
    """If the flow config's group-4 concession is NOT the pre-swap 190, raise --
    the swap provenance must be verifiable, not assumed."""
    orig_load = ccm._load_yaml

    def _corrupt(path):
        cfg = orig_load(path)
        if Path(path).name == "case_config.yaml":
            for opt in cfg["scenarios"]["options"]:
                if opt["id"] == 4:
                    opt["concession"] = 236  # not 190
        return cfg

    monkeypatch.setattr(ccm, "_load_yaml", _corrupt)
    with pytest.raises(ValueError, match="expected 'b010190'"):
        ccm.build_canonical_mapping(write=False)


# ===========================================================================
# STATE-AWARE reconcile acceptance (pre/post reconcile; fail any third state)
# ===========================================================================
_TEMPLATE = ccm.DEFAULT_OUT_CSV.parent
_BAK_FLOW = _TEMPLATE / "case_config.yaml.bak"
_BAK_TR = _TEMPLATE / "case_config_transport.yaml.bak"


def test_live_config_is_post_reconcile_state(mapping, ledger):
    """The committed (live) config is POST-reconcile: build succeeds AND every
    group's ledger `changed` is False (transport concession == canonical)."""
    assert bool((~ledger["changed"]).all()), "live config should be fully reconciled (0 changed)"


@pytest.mark.skipif(not (_BAK_FLOW.exists() and _BAK_TR.exists()),
                    reason="pre-image .bak backups not present")
def test_pre_reconcile_state_accepted_from_bak():
    """Building against the pre-image (.bak) originals is the PRE-reconcile
    state: flow[4]=b010190, all 9 changed -- must be accepted, and yield the
    same canonical CONTENT."""
    res = ccm.build_canonical_mapping(flow_config=_BAK_FLOW, transport_config=_BAK_TR, write=False)
    assert bool(res.ledger["changed"].all()), "pre-reconcile: every group re-homed"
    assert list(res.mapping["concession"]) == EXPECTED_CONCESSIONS  # content identical


def test_mixed_state_rejected(monkeypatch):
    """A THIRD/mixed state must FAIL: flow[4]=b010120 (post) but a transport
    concession still non-canonical (so changed != 0)."""
    orig_load = ccm._load_yaml

    def _corrupt(path):
        cfg = orig_load(path)
        if Path(path).name == "case_config_transport.yaml":
            for opt in cfg["transport_scenarios"]["options"]:
                if opt["id"] == 0:
                    opt["concession"] = "b010999"  # non-canonical -> changed=True for g0
        return cfg

    monkeypatch.setattr(ccm, "_load_yaml", _corrupt)
    with pytest.raises(ValueError, match="unexpected reconcile state"):
        ccm.build_canonical_mapping(write=False)


# ===========================================================================
# Codex fix 3: GOLDEN content acceptance table
# ===========================================================================
def test_golden_table_matches_build(mapping):
    by_group = mapping.set_index("group")
    for g, (conc, cas, thr, sorb, dec) in ccm.GOLDEN_MAPPING.items():
        row = by_group.loc[g]
        assert row["concession"] == conc
        assert str(row["cas_number"]) == cas
        assert float(row["threshold_mg_L"]) == thr
        assert bool(row["sorption"]) is sorb
        assert bool(row["decay"]) is dec


def test_golden_covers_all_nine_groups():
    assert set(ccm.GOLDEN_MAPPING) == set(range(N))


def test_swapped_threshold_fails_golden(monkeypatch):
    """Swap two groups' thresholds inside the transport config -- shape/id
    checks still pass, but the golden CONTENT check must catch it."""
    orig_load = ccm._load_yaml

    def _swap(path):
        cfg = orig_load(path)
        if Path(path).name == "case_config_transport.yaml":
            opts = {o["id"]: o for o in cfg["transport_scenarios"]["options"]}
            # swap TCE (id0, 0.005) <-> Nitrate (id1, 25.0) thresholds
            opts[0]["monitoring"]["threshold_mg_L"], opts[1]["monitoring"]["threshold_mg_L"] = (
                opts[1]["monitoring"]["threshold_mg_L"], opts[0]["monitoring"]["threshold_mg_L"])
        return cfg

    monkeypatch.setattr(ccm, "_load_yaml", _swap)
    with pytest.raises(AssertionError, match="golden content mismatch"):
        ccm.build_canonical_mapping(write=False)


def test_swapped_contaminant_cas_fails_golden(monkeypatch):
    """A swapped contaminant (CAS) inside the transport options fails golden."""
    orig_load = ccm._load_yaml

    def _swap(path):
        cfg = orig_load(path)
        if Path(path).name == "case_config_transport.yaml":
            for opt in cfg["transport_scenarios"]["options"]:
                if opt["id"] == 0:
                    opt["properties"]["cas_number"] = "999-99-9"  # not TCE
        return cfg

    monkeypatch.setattr(ccm, "_load_yaml", _swap)
    with pytest.raises(AssertionError, match="golden content mismatch"):
        ccm.build_canonical_mapping(write=False)


# ===========================================================================
# Codex fix 4: inactive reaction-field hygiene
# ===========================================================================
def test_sorption_false_with_stray_kd_raises(monkeypatch):
    """sorption=False but Kd>0 (on a non-conservative group) must raise."""
    orig_load = ccm._load_yaml

    def _corrupt(path):
        cfg = orig_load(path)
        if Path(path).name == "case_config_transport.yaml":
            for opt in cfg["transport_scenarios"]["options"]:
                if opt["id"] == 2:  # Benzene: sorption False, decay True (not conservative)
                    opt["transport"]["distribution_coefficient_mL_g"] = 0.5
        return cfg

    monkeypatch.setattr(ccm, "_load_yaml", _corrupt)
    with pytest.raises(ValueError, match="stray sorption parameter"):
        ccm.build_canonical_mapping(write=False)


def test_decay_false_with_stray_lambda_raises(monkeypatch):
    """decay=False but lambda>0 (on a non-conservative group) must raise."""
    orig_load = ccm._load_yaml

    def _corrupt(path):
        cfg = orig_load(path)
        if Path(path).name == "case_config_transport.yaml":
            for opt in cfg["transport_scenarios"]["options"]:
                if opt["id"] == 4:  # Chromium: sorption True, decay False (not conservative)
                    opt["transport"]["first_order_decay_constant_1_per_day"] = 0.01
        return cfg

    monkeypatch.setattr(ccm, "_load_yaml", _corrupt)
    with pytest.raises(ValueError, match="stray decay constant"):
        ccm.build_canonical_mapping(write=False)


def test_decay_false_with_stray_halflife_raises(monkeypatch):
    """decay=False but half_life present must raise."""
    orig_load = ccm._load_yaml

    def _corrupt(path):
        cfg = orig_load(path)
        if Path(path).name == "case_config_transport.yaml":
            for opt in cfg["transport_scenarios"]["options"]:
                if opt["id"] == 4:  # Chromium: decay False
                    opt["transport"]["half_life_days"] = 100.0
        return cfg

    monkeypatch.setattr(ccm, "_load_yaml", _corrupt)
    with pytest.raises(ValueError, match="half_life_days=.*present"):
        ccm.build_canonical_mapping(write=False)


def test_real_config_reaction_hygiene_clean(mapping):
    """The real (unmodified) config must satisfy inactive-field hygiene:
    every non-sorbing row has Kd==0; every non-decaying row has lambda==0 and
    a null half_life."""
    for _, row in mapping.iterrows():
        if not bool(row["sorption"]):
            assert float(row["distribution_coefficient_mL_g"]) == 0.0
        if not bool(row["decay"]):
            assert float(row["first_order_decay_constant_1_per_day"]) == 0.0
            assert pd.isna(row["half_life_days"])


# ===========================================================================
# Codex fix 5: pinned CSV byte format (LF newlines + %.12g float format)
# ===========================================================================
def test_csv_uses_lf_newlines_and_float_format(tmp_path):
    kw = dict(
        out_csv=tmp_path / "canonical_mapping.csv",
        out_yaml=tmp_path / "canonical_mapping.yaml",
        ledger_csv=tmp_path / "repairing_ledger.csv",
        sanity_csv=tmp_path / "threshold_sanity.csv",
        write=True,
    )
    ccm.build_canonical_mapping(**kw)
    raw = (tmp_path / "canonical_mapping.csv").read_bytes()
    assert b"\r\n" not in raw, "CSV must use LF-only line endings"
    assert raw.endswith(b"\n")
    text = raw.decode("utf-8")
    # %.12g preserves small/scientific values without precision loss or padding
    assert "0.0002" in text            # PFOA threshold, not 0.000200000...
    assert "8e-10" in text             # molecular diffusion 0.8e-9 preserved
    # no fixed-width zero padding like 0.0050 (would be 0.005 under %.12g)
    assert ",0.0050," not in text


def test_committed_csv_is_lf_only():
    raw = ccm.DEFAULT_OUT_CSV.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
