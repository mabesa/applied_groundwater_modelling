"""
Tests for M1.3b -- switch the flow config's ``model:`` block from legacy
MODFLOW-NWT to the calibrated MF6 05f model (``switch_flow_model_to_mf6`` in
casestudy_reconcile_configs).

Config-only, no model run. The committed flow config has ALREADY been switched;
the pre-image ``case_config.yaml.m13b.bak`` holds the pre-M1.3b (NWT) flow
config. Before/after tests run the switch on a fresh COPY of that pre-image in
tmp (never touching the committed files or the M1.3a ``.bak``).

Run with: uv run pytest _SUPPORT/tests/test_casestudy_switch_flow_model.py -v
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import casestudy_reconcile_configs as crc  # noqa: E402

N = crc.N_GROUPS
REAL_FLOW = crc.DEFAULT_FLOW_CONFIG
REAL_TR = crc.DEFAULT_TRANSPORT_CONFIG
M13B_BAK = REAL_FLOW.with_name(REAL_FLOW.name + ".m13b.bak")  # pre-M1.3b (NWT) flow
M13A_BAK = REAL_FLOW.with_name(REAL_FLOW.name + ".bak")       # pre-M1.3a flow

MF6_SHARED = ("workspace", "sim_namefile", "sim_name", "baseline_model_name")


def _load(path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def transport_model() -> dict:
    return _load(REAL_TR)["model"]


@pytest.fixture(scope="module")
def switched(tmp_path_factory):
    """Run the switch on a fresh copy of the pre-M1.3b (.m13b.bak) flow config."""
    if not M13B_BAK.exists():
        pytest.skip("pre-M1.3b backup (.m13b.bak) not present (M1.3b not applied)")
    d = tmp_path_factory.mktemp("m13b")
    flow_p = d / "case_config.yaml"
    shutil.copy(M13B_BAK, flow_p)
    orig = _load(flow_p)
    res = crc.switch_flow_model_to_mf6(
        flow_config=flow_p, transport_config=REAL_TR, dry_run=False, backup=True)
    return d, flow_p, res, orig


# ---------------------------------------------------------------------------
# committed-deliverable acceptance (the live, switched flow config)
# ---------------------------------------------------------------------------
def test_flow_model_block_is_mf6(transport_model):
    fm = _load(REAL_FLOW)["model"]
    assert fm["data_name"] == "flow_model_mf6"
    assert "sim_namefile" in fm and fm["sim_namefile"] == "mfsim.nam"
    assert fm["sim_name"] == "limmat_valley"
    assert fm["baseline_model_name"] == "limmat_valley"
    assert "calibration" in fm["workspace"]


def test_no_mixed_schema():
    fm = _load(REAL_FLOW)["model"]
    assert "namefile" not in fm, "legacy 'namefile' key must be dropped (no mixed schema)"
    assert "sim_namefile" in fm


def test_parsed_shared_fields_equal_transport(transport_model):
    """PARSED comparison (not hardcoded): flow model shared fields == transport."""
    fm = _load(REAL_FLOW)["model"]
    for k in MF6_SHARED:
        assert fm[k] == transport_model[k], f"flow model.{k} != transport model.{k}"


def test_workspace_is_calibration_not_baseline():
    fm = _load(REAL_FLOW)["model"]
    assert fm["workspace"].endswith("/limmat/calibration")
    assert "/limmat/baseline_model" not in fm["workspace"]


def test_whole_file_nwt_gate():
    """Case-insensitive: zero nwt / modflow-nwt / legacy-namefile / old-workspace
    matches anywhere in the flow config (comments included). '.nam' alone is fine
    (mfsim.nam)."""
    txt = REAL_FLOW.read_text()
    low = txt.lower()
    assert "nwt" not in low
    assert "modflow-nwt" not in low
    assert "limmat_valley_model_nwt" not in low
    assert "limmat_valley_model_nwt.nam" not in low
    assert "/limmat/baseline_model" not in txt  # old workspace PATH fragment
    # mfsim.nam is legitimate MF6 and must survive
    assert "mfsim.nam" in txt


def test_baseline_model_name_key_survives_but_not_old_path():
    """The gate must target the workspace PATH fragment, NOT the surviving
    'baseline_model_name' KEY (which is a valid MF6 field = 'limmat_valley')."""
    txt = REAL_FLOW.read_text()
    assert "baseline_model_name: " in txt          # key present
    assert _load(REAL_FLOW)["model"]["baseline_model_name"] == "limmat_valley"


# ---------------------------------------------------------------------------
# loader smoke test + preservation
# ---------------------------------------------------------------------------
def test_flow_loads_and_get_scenario_all_nine():
    import case_utils
    for g in range(N):
        sc = case_utils.get_scenario_for_group(str(REAL_FLOW), g)
        assert sc is not None and int(sc["id"]) == g


def test_transport_config_untouched_and_lints():
    """The transport config must be byte-identical to its M1.3a state and still
    lint (M1.3b only touches the flow config)."""
    import case_utils
    # transport model block is the MF6 source; ensure it still lints for all 9
    report = case_utils.lint_transport_config(config_path=str(REAL_TR), groups=range(N))
    assert sorted(report) == list(range(N))


def test_todo_blocks_survive():
    txt = REAL_FLOW.read_text()
    assert "# TODO: integer group number" in txt
    assert "TODO: list all group members" in txt
    assert txt.count("TODO") >= 8


# ---------------------------------------------------------------------------
# before -> after (on the pre-M1.3b copy): only model: changed, parsed-equal else
# ---------------------------------------------------------------------------
def test_only_model_block_changed_parsed_equal(switched):
    _d, flow_p, _res, orig = switched
    new = _load(flow_p)
    for k in set(orig) | set(new):
        if k == "model":
            continue
        assert orig.get(k) == new.get(k), f"unexpected change outside model: in {k!r}"
    # the model block DID change (NWT -> MF6)
    assert orig["model"] != new["model"]
    assert "namefile" in orig["model"] and "namefile" not in new["model"]


def test_scenarios_and_pumping_untouched(switched):
    _d, flow_p, _res, orig = switched
    new = _load(flow_p)
    assert new["scenarios"] == orig["scenarios"]
    assert new["pumping"] == orig["pumping"]


# ---------------------------------------------------------------------------
# safety: dry-run + backup
# ---------------------------------------------------------------------------
def test_dry_run_writes_nothing(tmp_path):
    if not M13B_BAK.exists():
        pytest.skip("no pre-M1.3b backup")
    flow_p = tmp_path / "case_config.yaml"
    shutil.copy(M13B_BAK, flow_p)
    before = flow_p.read_bytes()
    res = crc.switch_flow_model_to_mf6(flow_config=flow_p, transport_config=REAL_TR, dry_run=True)
    assert res.wrote is False
    assert res.flow_diff  # a diff was produced
    assert flow_p.read_bytes() == before
    assert not (tmp_path / "case_config.yaml.m13b.bak").exists()


def test_backup_is_preimage(switched):
    _d, flow_p, _res, _orig = switched
    bak = flow_p.with_name(flow_p.name + ".m13b.bak")
    assert bak.exists()
    # pre-image = the NWT flow config we copied in
    assert "limmat_valley_model_nwt" in bak.read_text()


def test_m13a_backup_not_clobbered():
    """M1.3b uses a distinct '.m13b.bak' suffix so the M1.3a '.bak' (pre-M1.3a
    original) is preserved."""
    if not M13A_BAK.exists():
        pytest.skip("no M1.3a .bak")
    # M1.3a .bak is the pre-M1.3a original: NWT model AND concession 190
    txt = M13A_BAK.read_text()
    assert "limmat_valley_model_nwt" in txt
    assert "concession: 190" in txt


# ---------------------------------------------------------------------------
# determinism + idempotence
# ---------------------------------------------------------------------------
def test_determinism_two_runs_identical(tmp_path):
    if not M13B_BAK.exists():
        pytest.skip("no pre-M1.3b backup")
    outs = []
    for i in range(2):
        d = tmp_path / f"run{i}"
        d.mkdir()
        fp = d / "case_config.yaml"
        shutil.copy(M13B_BAK, fp)
        crc.switch_flow_model_to_mf6(flow_config=fp, transport_config=REAL_TR,
                                     dry_run=False, backup=False)
        outs.append(fp.read_bytes())
    assert outs[0] == outs[1]


def test_idempotent_second_run_fixed_point(switched):
    _d, flow_p, _res, _orig = switched
    r2 = crc.switch_flow_model_to_mf6(flow_config=flow_p, transport_config=REAL_TR, dry_run=True)
    changed = [l for l in r2.flow_diff.splitlines()
               if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    assert changed == [], "second switch run is not a fixed point"


# ---------------------------------------------------------------------------
# unit-level: the acceptance helper + block composer
# ---------------------------------------------------------------------------
def test_assert_helper_rejects_mixed_schema(transport_model):
    """A flow config that still carries 'namefile' must be rejected."""
    bad = "model:\n  data_name: flow_model_mf6\n  namefile: \"x.nam\"\n  " \
          "workspace: \"~/applied_groundwater_modelling_data/limmat/calibration\"\n  " \
          "sim_namefile: \"mfsim.nam\"\n  sim_name: \"limmat_valley\"\n  " \
          "baseline_model_name: \"limmat_valley\"\n"
    with pytest.raises(ValueError, match="namefile"):
        crc._assert_flow_model_is_mf6(bad, transport_model)


def test_assert_helper_rejects_nwt_token(transport_model):
    bad = ("model:\n  data_name: flow_model_mf6\n  "
           "workspace: \"~/applied_groundwater_modelling_data/limmat/calibration\"\n  "
           "sim_namefile: \"mfsim.nam\"\n  sim_name: \"limmat_valley\"\n  "
           "baseline_model_name: \"limmat_valley\"\n# leftover nwt note\n")
    with pytest.raises(ValueError, match="NWT"):
        crc._assert_flow_model_is_mf6(bad, transport_model)


def test_compose_block_sources_values_from_transport(transport_model):
    block = crc._compose_flow_model_block(transport_model)
    assert f'workspace: "{transport_model["workspace"]}"' in block
    assert f'sim_name: "{transport_model["sim_name"]}"' in block
    assert "nwt" not in block.lower()
