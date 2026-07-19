"""
Tests for casestudy_reconcile_configs (M1.3a -- reconcile the two config YAMLs
to the canonical mapping).

M1.3a is the FIRST step that EDITS the student configs, so these tests are
rigorous about (A) direct source-of-truth field validation, (B) preservation /
no-collateral-damage (comments/TODOs/source.location/lint), and (C) the
coherence ledger + determinism/idempotence.

The committed configs under PROJECT/workspace/template/ have ALREADY been
rewritten by M1.3a; the pre-image ``*.bak`` backups hold the originals. Tests
that need a before->after run reconcile on a fresh COPY of the ``.bak``
pre-images in a tmp dir (never touching the committed files or their real
backups).

Run with: uv run pytest _SUPPORT/tests/test_casestudy_reconcile_configs.py -v
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import casestudy_reconcile_configs as crc  # noqa: E402

N = crc.N_GROUPS

REAL_FLOW = crc.DEFAULT_FLOW_CONFIG
REAL_TR = crc.DEFAULT_TRANSPORT_CONFIG
BAK_FLOW = REAL_FLOW.with_name(REAL_FLOW.name + ".bak")
BAK_TR = REAL_TR.with_name(REAL_TR.name + ".bak")
DOUBLET_TABLE = crc.DEFAULT_DOUBLET_TABLE
CANONICAL = crc.DEFAULT_CANONICAL_MAPPING

EXPECTED_CONCESSIONS = [
    "b010210", "b010219", "b010201", "b010236", "b010120",
    "b010223", "b010227", "b010213", "b010207",
]


# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------
def _load(path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def _flow_by_id(cfg) -> dict:
    return {int(o["id"]): o for o in cfg["scenarios"]["options"]}


def _tr_by_id(cfg) -> dict:
    return {int(o["id"]): o for o in cfg["transport_scenarios"]["options"]}


@pytest.fixture(scope="module")
def canonical() -> dict:
    cm = pd.read_csv(CANONICAL)
    return {int(r.group): str(r.concession) for r in cm.itertuples()}


@pytest.fixture(scope="module")
def doublet() -> dict:
    dt = pd.read_csv(DOUBLET_TABLE)
    return {str(r.concession): r for r in dt.itertuples()}


@pytest.fixture(scope="module")
def originals_available() -> bool:
    return BAK_FLOW.exists() and BAK_TR.exists()


@pytest.fixture(scope="module")
def reconciled(tmp_path_factory, originals_available):
    """Run reconcile on a fresh copy of the pre-image (.bak) originals in tmp.

    Returns (tmp_dir, ReconcileResult, original_flow_cfg, original_tr_cfg).
    """
    if not originals_available:
        pytest.skip("pre-image .bak backups not present (M1.3a not yet applied)")
    d = tmp_path_factory.mktemp("m13a")
    flow_p = d / "case_config.yaml"
    tr_p = d / "case_config_transport.yaml"
    shutil.copy(BAK_FLOW, flow_p)
    shutil.copy(BAK_TR, tr_p)
    orig_flow = _load(flow_p)
    orig_tr = _load(tr_p)
    result = crc.reconcile_configs(
        flow_config=flow_p, transport_config=tr_p, ledger_csv=d / "coherence_ledger.csv",
        dry_run=False, backup=True)
    return d, result, orig_flow, orig_tr


# ===========================================================================
# A. Direct source-of-truth validation (on the committed, rewritten configs)
# ===========================================================================
def test_flow_transport_concessions_agree_with_canonical(canonical):
    flow = _flow_by_id(_load(REAL_FLOW))
    tr = _tr_by_id(_load(REAL_TR))
    for gid in range(N):
        canon = canonical[gid]
        flow_conc = f"b010{int(flow[gid]['concession']):03d}"
        assert flow_conc == canon, f"group {gid}: flow {flow_conc} != canonical {canon}"
        assert tr[gid]["concession"] == canon, f"group {gid}: transport concession != canonical"
        assert tr[gid]["doublet"]["concession_id"] == canon, f"group {gid}: doublet.concession_id != canonical"


def test_g4_is_b010120_and_no_b010190_or_190():
    flow = _flow_by_id(_load(REAL_FLOW))
    tr = _tr_by_id(_load(REAL_TR))
    assert flow[4]["concession"] == 120
    assert tr[4]["concession"] == "b010120"
    assert tr[4]["doublet"]["concession_id"] == "b010120"
    # no b010190 / 190 in any concession FIELD (comments may still mention history)
    for gid in range(N):
        assert flow[gid]["concession"] != 190
        assert tr[gid]["concession"] != "b010190"
        assert tr[gid]["doublet"]["concession_id"] != "b010190"


def test_doublet_coords_equal_table_and_not_swapped(doublet, canonical):
    tr = _tr_by_id(_load(REAL_TR))
    for gid in range(N):
        row = doublet[canonical[gid]]
        dbl = tr[gid]["doublet"]
        # injection <- inj_* (Rueckgabe centroid); extraction <- ext_* (Entnahme centroid)
        assert dbl["injection_easting"] == pytest.approx(row.inj_E, abs=1e-9)
        assert dbl["injection_northing"] == pytest.approx(row.inj_N, abs=1e-9)
        assert dbl["extraction_easting"] == pytest.approx(row.ext_E, abs=1e-9)
        assert dbl["extraction_northing"] == pytest.approx(row.ext_N, abs=1e-9)
        # NOT swapped: injection must not equal the extraction centroid
        assert not (dbl["injection_easting"] == row.ext_E and dbl["injection_northing"] == row.ext_N), (
            f"group {gid}: inj/ext appear swapped")


def test_pumping_rate_equals_table_Q(doublet, canonical):
    tr = _tr_by_id(_load(REAL_TR))
    for gid in range(N):
        row = doublet[canonical[gid]]
        assert float(tr[gid]["doublet"]["pumping_rate_m3_d"]) == float(row.Q_m3d)


def test_flow_one_option_per_id_all_nine_no_dupes():
    opts = _load(REAL_FLOW)["scenarios"]["options"]
    ids = [o["id"] for o in opts]
    assert sorted(ids) == list(range(N))
    assert len(ids) == len(set(ids)) == N


def test_written_coords_are_lv95(doublet, canonical):
    tr = _tr_by_id(_load(REAL_TR))
    for gid in range(N):
        dbl = tr[gid]["doublet"]
        crc._assert_lv95(dbl["injection_easting"], dbl["injection_northing"], f"g{gid} inj")
        crc._assert_lv95(dbl["extraction_easting"], dbl["extraction_northing"], f"g{gid} ext")


# ===========================================================================
# B. Preservation / no-collateral-damage
# ===========================================================================
INTENDED_TR_KEYS = {"concession"}
INTENDED_DOUBLET_KEYS = {"concession_id", "injection_easting", "injection_northing",
                         "extraction_easting", "extraction_northing", "pumping_rate_m3_d"}


def test_source_location_byte_unchanged(reconciled):
    _d, _r, _orig_flow, orig_tr = reconciled  # orig from .bak
    new_tr = _load(_d / "case_config_transport.yaml")
    o_by, n_by = _tr_by_id(orig_tr), _tr_by_id(new_tr)
    for gid in range(N):
        assert n_by[gid]["source"] == o_by[gid]["source"], f"group {gid}: source block changed"


def test_recirc_untouched_and_no_new_key(reconciled):
    _d, _r, _orig_flow, orig_tr = reconciled
    new_tr = _load(_d / "case_config_transport.yaml")
    o_by, n_by = _tr_by_id(orig_tr), _tr_by_id(new_tr)
    for gid in range(N):
        o_dbl, n_dbl = o_by[gid]["doublet"], n_by[gid]["doublet"]
        assert n_dbl["recirculation_fraction"] == o_dbl["recirculation_fraction"]
        # no new sibling key added to the doublet block
        assert set(n_dbl.keys()) == set(o_dbl.keys())


def test_only_intended_paths_changed(reconciled):
    """Semantic diff: parse old (.bak) vs new and assert the ONLY differing
    leaf paths are the intended concession/doublet scalars (robust to any
    cosmetic ruamel reflow, which does not change parsed values)."""
    _d, _r, orig_flow, orig_tr = reconciled
    new_tr = _load(_d / "case_config_transport.yaml")
    new_flow = _load(_d / "case_config.yaml")

    # --- flow: only scenarios.options[i].concession may differ ---
    o_flow, n_flow = _flow_by_id(orig_flow), _flow_by_id(new_flow)
    for gid in range(N):
        for k in set(o_flow[gid]) | set(n_flow[gid]):
            if k == "concession":
                continue
            assert o_flow[gid].get(k) == n_flow[gid].get(k), f"flow group {gid}: unexpected change in {k!r}"

    # --- transport: only concession + the 6 doublet scalars may differ ---
    o_tr, n_tr = _tr_by_id(orig_tr), _tr_by_id(new_tr)
    for gid in range(N):
        o_opt, n_opt = o_tr[gid], n_tr[gid]
        for k in set(o_opt) | set(n_opt):
            if k == "concession":
                continue
            if k == "doublet":
                for dk in set(o_opt["doublet"]) | set(n_opt["doublet"]):
                    if dk in INTENDED_DOUBLET_KEYS:
                        continue
                    assert o_opt["doublet"].get(dk) == n_opt["doublet"].get(dk), (
                        f"transport group {gid}: unexpected doublet change in {dk!r}")
                continue
            assert o_opt.get(k) == n_opt.get(k), f"transport group {gid}: unexpected change in {k!r}"


def test_todo_blocks_survive():
    """Student TODO scaffolding must survive the rewrite (known markers)."""
    flow_txt = REAL_FLOW.read_text()
    tr_txt = REAL_TR.read_text()
    assert "# TODO: integer group number" in flow_txt
    assert "TODO: list all group members" in flow_txt
    assert flow_txt.count("TODO") >= 8
    assert "TODO: Tailor with your contaminant" in tr_txt
    assert "TODO: Provide 2" in tr_txt
    assert tr_txt.count("TODO") >= 15


def test_rewritten_transport_lints_clean():
    """Config-loader smoke test: the rewritten transport config passes the
    ACTUAL consumer linter for all 9 groups."""
    import case_utils
    report = case_utils.lint_transport_config(config_path=str(REAL_TR), groups=range(N))
    assert sorted(report) == list(range(N))
    for gid in range(N):
        assert float(report[gid]["doublet"]["pumping_rate_m3_d"]) == 4320.0


def test_rewritten_flow_loads_through_consumer():
    """Flow consumer path: get_scenario_for_group resolves all 9 groups."""
    import case_utils
    for gid in range(N):
        sc = case_utils.get_scenario_for_group(str(REAL_FLOW), gid)
        assert sc is not None and int(sc["id"]) == gid


def test_recirc_has_no_physics_consumer():
    """Grep gate: recirculation_fraction is linted-only -- no physics consumer
    in _SUPPORT/src reads it (only case_utils validates it)."""
    src = Path(__file__).resolve().parents[1] / "src"
    # Allowed to mention recirc: case_utils (the linter that validates it) and
    # casestudy_reconcile_configs (reads the OLD value only to record staleness
    # in the coherence ledger -- NOT physics). Any OTHER module that references
    # it would be a physics consumer and must fail this gate.
    allowed = {"case_utils.py", "casestudy_reconcile_configs.py"}
    offenders = []
    for p in src.glob("*.py"):
        if p.name in allowed:
            continue
        if "recirculation_fraction" in p.read_text():
            offenders.append(p.name)
    assert offenders == [], f"unexpected recirculation_fraction consumer(s): {offenders}"


# ===========================================================================
# C. Coherence ledger + determinism/idempotence
# ===========================================================================
def test_ledger_nine_rows_and_columns(reconciled):
    _d, r, _o, _f = reconciled
    L = r.ledger
    assert len(L) == N
    for col in ("group", "old_concession", "new_concession", "old_inj_E", "old_inj_N",
                "old_ext_E", "old_ext_N", "new_inj_E", "new_inj_N", "new_ext_E", "new_ext_N",
                "inj_move_m", "ext_move_m", "old_Q", "new_Q", "recirc_old", "recirc_stale",
                "source_offset_unchanged", "old_source_abs_E", "old_source_abs_N",
                "new_source_abs_E", "new_source_abs_N", "source_abs_move_m", "upgradient_unverified"):
        assert col in L.columns, f"missing ledger column {col}"


def test_ledger_flags(reconciled):
    _d, r, _o, _f = reconciled
    L = r.ledger
    assert L["recirc_stale"].all()
    assert L["source_offset_unchanged"].all()
    assert L["upgradient_unverified"].all()


def test_ledger_deltas_match_actual_before_after(reconciled, doublet, canonical):
    """The recorded old/new coords + moves must match the actual .bak-before
    and doublet_table-after values."""
    _d, r, _orig_flow, orig_tr = reconciled
    o_by = _tr_by_id(orig_tr)
    L = r.ledger.set_index("group")
    for gid in range(N):
        o_dbl = o_by[gid]["doublet"]
        row = L.loc[gid]
        # old coords match the pre-image
        assert row["old_inj_E"] == pytest.approx(float(o_dbl["injection_easting"]))
        assert row["old_ext_N"] == pytest.approx(float(o_dbl["extraction_northing"]))
        assert row["old_Q"] == pytest.approx(float(o_dbl["pumping_rate_m3_d"]))
        # new coords match the doublet_table
        dt_row = doublet[canonical[gid]]
        assert row["new_inj_E"] == pytest.approx(round(float(dt_row.inj_E), 1))
        assert row["new_ext_N"] == pytest.approx(round(float(dt_row.ext_N), 1))
        assert row["new_Q"] == pytest.approx(float(dt_row.Q_m3d))
        # move distances recomputed
        import math
        exp_ext = math.hypot(row["new_ext_E"] - row["old_ext_E"], row["new_ext_N"] - row["old_ext_N"])
        assert row["ext_move_m"] == pytest.approx(exp_ext, abs=1e-2)


def test_source_abs_move_equals_ext_move(reconciled):
    _d, r, _o, _f = reconciled
    L = r.ledger
    assert (L["source_abs_move_m"].round(3) == L["ext_move_m"].round(3)).all()


def test_absolute_spill_is_ext_plus_offset(reconciled):
    _d, r, _orig_flow, orig_tr = reconciled
    o_by = _tr_by_id(orig_tr)
    L = r.ledger.set_index("group")
    for gid in range(N):
        loc = o_by[gid]["source"]["location"]
        row = L.loc[gid]
        assert row["old_source_abs_E"] == pytest.approx(row["old_ext_E"] + float(loc["easting"]), abs=0.05)
        assert row["new_source_abs_N"] == pytest.approx(row["new_ext_N"] + float(loc["northing"]), abs=0.05)


# --- safety: dry-run + backup ---
def test_dry_run_writes_nothing(tmp_path, originals_available):
    if not originals_available:
        pytest.skip("no pre-image backups")
    flow_p = tmp_path / "case_config.yaml"
    tr_p = tmp_path / "case_config_transport.yaml"
    shutil.copy(BAK_FLOW, flow_p)
    shutil.copy(BAK_TR, tr_p)
    before_flow, before_tr = flow_p.read_bytes(), tr_p.read_bytes()
    r = crc.reconcile_configs(flow_config=flow_p, transport_config=tr_p,
                              ledger_csv=tmp_path / "led.csv", dry_run=True)
    assert r.wrote is False
    assert r.flow_diff and r.transport_diff  # a diff WAS produced
    assert flow_p.read_bytes() == before_flow  # but files untouched
    assert tr_p.read_bytes() == before_tr
    assert not (tmp_path / "led.csv").exists()
    assert not (tmp_path / "case_config.yaml.bak").exists()


def test_backup_is_preimage(reconciled):
    _d, _r, _o, _f = reconciled
    # the tmp run wrote its own .bak; it must equal the pre-image we copied in
    tmp_bak = _d / "case_config_transport.yaml.bak"
    assert tmp_bak.exists()
    assert tmp_bak.read_bytes() == BAK_TR.read_bytes()


# --- determinism + idempotence ---
def test_determinism_two_runs_identical(tmp_path, originals_available):
    if not originals_available:
        pytest.skip("no pre-image backups")
    outs = []
    for i in range(2):
        d = tmp_path / f"run{i}"
        d.mkdir()
        shutil.copy(BAK_FLOW, d / "case_config.yaml")
        shutil.copy(BAK_TR, d / "case_config_transport.yaml")
        crc.reconcile_configs(flow_config=d / "case_config.yaml",
                              transport_config=d / "case_config_transport.yaml",
                              ledger_csv=d / "coherence_ledger.csv", dry_run=False, backup=False)
        outs.append((
            (d / "case_config.yaml").read_bytes(),
            (d / "case_config_transport.yaml").read_bytes(),
            (d / "coherence_ledger.csv").read_bytes(),
        ))
    assert outs[0] == outs[1], "reconcile is not deterministic"


def test_idempotent_second_run_is_fixed_point(reconciled):
    _d, _r, _o, _f = reconciled
    # reconciled already ran once (real write to _d). Run again -> no change.
    r2 = crc.reconcile_configs(flow_config=_d / "case_config.yaml",
                               transport_config=_d / "case_config_transport.yaml",
                               ledger_csv=_d / "coherence_ledger2.csv", dry_run=True)
    changed = [l for l in (r2.flow_diff + r2.transport_diff).splitlines()
               if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    assert changed == [], "second reconcile run is not a fixed point"
    assert (r2.ledger["inj_move_m"].abs().max() == 0.0)
    assert (r2.ledger["ext_move_m"].abs().max() == 0.0)


def test_post_reconcile_flow_matches_canonical_zero_exceptions(reconciled, canonical):
    """After reconcile, flow concession == canonical for ALL 9 (no G4 exception)."""
    _d, _r, _o, _f = reconciled
    new_flow = _flow_by_id(_load(_d / "case_config.yaml"))
    mismatches = [gid for gid in range(N)
                  if f"b010{int(new_flow[gid]['concession']):03d}" != canonical[gid]]
    assert mismatches == []


def test_canonical_content_reproducible_from_rewritten(reconciled, canonical):
    """M1.2's canonical CONTENT (concession + contaminant identity) is
    reproducible from the rewritten configs -- the substantive idempotence
    claim (the configs are now self-consistent with canonical_mapping)."""
    _d, _r, _o, _f = reconciled
    new_tr = _tr_by_id(_load(_d / "case_config_transport.yaml"))
    cm = pd.read_csv(CANONICAL).set_index("group")
    for gid in range(N):
        assert new_tr[gid]["concession"] == canonical[gid]
        assert str(new_tr[gid]["properties"]["cas_number"]) == str(cm.loc[gid, "cas_number"])
        assert float(new_tr[gid]["monitoring"]["threshold_mg_L"]) == float(cm.loc[gid, "threshold_mg_L"])


# ===========================================================================
# unit-level helpers
# ===========================================================================
def test_concession_to_int():
    assert crc._concession_to_int("b010120") == 120
    assert crc._concession_to_int("b010210") == 210
    with pytest.raises(ValueError):
        crc._concession_to_int("x999")


def test_lv95_guard_rejects_out_of_range():
    crc._assert_lv95(2_681_000.0, 1_248_000.0, "ok")  # in-range, no raise
    with pytest.raises(ValueError, match="LV95"):
        crc._assert_lv95(8.54, 47.37, "wgs84")  # WGS84 lon/lat
    with pytest.raises(ValueError, match="LV95"):
        crc._assert_lv95(681_000.0, 248_000.0, "lv03")  # LV03 6-digit


def test_committed_ledger_exists_and_parses():
    led = crc.DEFAULT_LEDGER_CSV
    assert led.exists(), "coherence_ledger.csv missing -- run reconcile_configs"
    df = pd.read_csv(led)
    assert len(df) == N
    assert (df["source_abs_move_m"].round(3) == df["ext_move_m"].round(3)).all()
    assert list(df["new_concession"]) == EXPECTED_CONCESSIONS


# ===========================================================================
# Codex fix 1: stale machine-authored docs are REFRESHED (not blindly preserved)
# ===========================================================================
def test_transport_header_regenerated_current():
    """The header assignment table must state the CURRENT canonical assignment:
    new concessions, Q=4320 for all, recirc stale/M3b, coords pending-M4 -- and
    must NOT carry the old per-doublet Q=1370/5760 or old concessions."""
    txt = REAL_TR.read_text()
    header = txt.split("title:")[0]  # everything above the first `title:` key
    assert "CANONICAL assignment (M1.3a)" in header
    assert "Q = licensed max (4320 m3/d) for ALL groups" in header
    # every group's header line names its canonical concession + Q=4320
    for gid, conc in enumerate(EXPECTED_CONCESSIONS):
        assert f"# Group {gid}: concession {conc} -" in header
    assert "Q=4320 m3/d" in header
    # stale content gone from the header
    assert "Q=1370" not in header and "Q=5760" not in header
    assert "recirc 0.221" not in header  # old per-doublet recirc list dropped
    assert "higher-rate (>3000 L/min) class" not in header
    for old in ("b010205", "b010196", "b010224", "b010199"):
        assert old not in header
    # staleness / pending pointers present
    assert "recirc_stale=True" in header
    assert "pending M4" in header and "upgradient_unverified=True" in header


def test_inline_spill_comments_neutralised():
    """The OLD-doublet / OLD-Q spill-outcome claims must be replaced with
    neutral, pending-M4 wording -- across all 9 source.location blocks."""
    txt = REAL_TR.read_text()
    # stale outcome claims gone
    assert "just inside capture" not in txt
    assert "well outside capture" not in txt
    assert "y_max=Q/(2Ti)" not in txt
    assert "Q=1370 m3/d, T~3000" not in txt
    assert "Tested outcome:" not in txt
    assert "stays BELOW threshold" not in txt
    assert "VALIDATED spill placement" not in txt
    assert "offset from extraction well (upgradient)" not in txt  # "(upgradient)" dropped
    # neutral wording present, once per group (9 source.location blocks)
    assert txt.count("Source position is an easting/northing OFFSET relative to the") == N
    assert txt.count("NOT yet\n") >= N or txt.count("NOT yet") >= N


def test_flow_header_g4_comment_updated():
    txt = REAL_FLOW.read_text()
    assert "# Group 4: concession 120, scenario SC4" in txt
    assert "# Group 4: concession 190" not in txt


def test_comment_rewrite_preserves_parsed_values(reconciled):
    """Honest-scope guarantee: the comment surgery + ruamel round-trip change
    NO parsed value outside the intended concession/doublet scalars -- including
    the reflowed nitrate description (byte-reflowed, value-identical)."""
    _d, _r, orig_flow, orig_tr = reconciled
    new_tr = _load(_d / "case_config_transport.yaml")
    o_by, n_by = _tr_by_id(orig_tr), _tr_by_id(new_tr)
    # nitrate (group 1) description: reflowed onto one line but value unchanged
    assert n_by[1]["description"] == o_by[1]["description"]
    # every non-target node parsed-equal (covered broadly in
    # test_only_intended_paths_changed; re-assert the description class here)
    for gid in range(N):
        assert n_by[gid]["title"] == o_by[gid]["title"]
        assert n_by[gid]["properties"] == o_by[gid]["properties"]
        assert n_by[gid]["monitoring"] == o_by[gid]["monitoring"]


# ===========================================================================
# Codex fix 3: duplicate-key validation
# ===========================================================================
def test_duplicate_canonical_group_raises(tmp_path, originals_available):
    if not originals_available:
        pytest.skip("no pre-image backups")
    cm = pd.read_csv(CANONICAL)
    cm2 = pd.concat([cm, cm.iloc[[3]]], ignore_index=True)  # duplicate group 3
    cm_p = tmp_path / "canonical_mapping.csv"
    cm2.to_csv(cm_p, index=False)
    shutil.copy(BAK_FLOW, tmp_path / "f.yaml")
    shutil.copy(BAK_TR, tmp_path / "t.yaml")
    with pytest.raises(ValueError, match="duplicate group"):
        crc.reconcile_configs(flow_config=tmp_path / "f.yaml", transport_config=tmp_path / "t.yaml",
                              canonical_mapping=cm_p, ledger_csv=tmp_path / "l.csv", dry_run=True)


def test_duplicate_doublet_concession_raises(tmp_path, originals_available):
    if not originals_available:
        pytest.skip("no pre-image backups")
    dt = pd.read_csv(DOUBLET_TABLE)
    dt2 = pd.concat([dt, dt.iloc[[2]]], ignore_index=True)  # duplicate concession
    dt_p = tmp_path / "doublet_table.csv"
    dt2.to_csv(dt_p, index=False)
    shutil.copy(BAK_FLOW, tmp_path / "f.yaml")
    shutil.copy(BAK_TR, tmp_path / "t.yaml")
    with pytest.raises(ValueError, match="duplicate (concession|group)"):
        crc.reconcile_configs(flow_config=tmp_path / "f.yaml", transport_config=tmp_path / "t.yaml",
                              doublet_table=dt_p, ledger_csv=tmp_path / "l.csv", dry_run=True)


# ===========================================================================
# Codex fix 4: post-rewrite ON-DISK all-groups invariant
# ===========================================================================
def test_written_matches_sources_helper_passes():
    """The helper accepts the committed (correct) rewritten configs."""
    cm = pd.read_csv(CANONICAL)
    dt = pd.read_csv(DOUBLET_TABLE)
    canonical = {int(r.group): str(r.concession) for r in cm.itertuples()}
    dt_by_conc = {str(r.concession): r for r in dt.itertuples()}
    crc._assert_written_matches_sources(
        REAL_FLOW.read_text(), REAL_TR.read_text(), canonical, dt_by_conc)


def test_written_matches_sources_helper_catches_corruption():
    """If a written coord is wrong, the on-disk invariant must raise."""
    cm = pd.read_csv(CANONICAL)
    dt = pd.read_csv(DOUBLET_TABLE)
    canonical = {int(r.group): str(r.concession) for r in cm.itertuples()}
    dt_by_conc = {str(r.concession): r for r in dt.itertuples()}
    tampered = REAL_TR.read_text().replace("pumping_rate_m3_d: 4320", "pumping_rate_m3_d: 9999", 1)
    with pytest.raises(ValueError, match="pumping_rate_m3_d"):
        crc._assert_written_matches_sources(
            REAL_FLOW.read_text(), tampered, canonical, dt_by_conc)
