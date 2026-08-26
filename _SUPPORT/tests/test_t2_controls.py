"""Tests for T2 S3 -- the controls that make S1 and S2 executable.

`T2_steps.md` v4 Sec 5: documents are not controls. Every refusal in
`t2_controls.py` has a test here that FIRES it -- a control nobody has seen
refuse is a control nobody knows works.

Run:  uv run pytest _SUPPORT/tests/test_t2_controls.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import t2_controls as ctl  # noqa: E402


# --- 1. the pre-registration is what the evaluation was designed on ---------
def test_prereg_matches_its_recorded_checksum():
    assert ctl.verify_prereg() == ctl.PREREG_SHA256


def test_a_tampered_prereg_is_refused():
    """The point of the checksum: a mapping that moved after the evaluation
    was designed against it must stop the run, not warn."""
    with pytest.raises(ctl.ControlRefusal, match="checksum mismatch"):
        ctl.verify_prereg(expected="0" * 64)


def test_registered_identities_come_from_the_prereg_not_the_frozen_list():
    """⚠️ An identity can be frozen and referenced by NO component -- running
    it would produce evidence no claim consumes."""
    reg = ctl.registered_identities()
    assert reg, "no identities registered"
    doc = json.loads(ctl.PREREG.read_text())
    referenced = {i for c in doc["components"] for i in (c.get("identities") or [])}
    assert reg == referenced


# --- 2. an unregistered identity cannot be run ------------------------------
def test_a_registered_identity_is_accepted():
    one = sorted(ctl.registered_identities())[0]
    assert ctl.require_registered(one) == one


def test_an_unregistered_identity_is_refused():
    with pytest.raises(ctl.ControlRefusal, match="not referenced by the pre-registration"):
        ctl.require_registered("spatial_1m_cr0.9")


# --- 3. the guard comes from S2, never from the caller ----------------------
def test_discovery_guard_is_s2s_recorded_value():
    recorded = json.loads(ctl.GUARDS.read_text())["guards"]["discovery_guard"]["value"]
    assert ctl.guard_for("anything") == recorded == 40000


def test_derived_guard_is_twice_the_measured_demand():
    assert ctl.guard_for("x", measured_cr09_demand=3000) == 6000


@pytest.mark.parametrize("bad", [0, -1])
def test_a_nonpositive_measured_demand_is_refused(bad):
    """A guard derived from a non-measurement is how a guard ends up fitting
    the result it was meant to bound."""
    with pytest.raises(ctl.ControlRefusal, match="not a measurement"):
        ctl.guard_for("x", measured_cr09_demand=bad)


# --- 4. a run is not evidence until it passes acceptance --------------------
def test_a_missing_artifact_fails_acceptance(tmp_path):
    acc = ctl.accept_run(tmp_path / "absent.json",
                         identity="spatial_10m_cr0.9", requested_guard=40000)
    assert acc.passed is False
    assert acc.checks["artifact_loads"] is False


def test_a_corrupted_artifact_fails_acceptance(tmp_path):
    """The deliberately-corrupted case the step exists to catch."""
    bad = tmp_path / "corrupt.json"
    bad.write_text('{"schema": {"schema_version": "not-a-version"}}\n')
    acc = ctl.accept_run(bad, identity="spatial_10m_cr0.9", requested_guard=40000)
    assert acc.passed is False


def test_acceptance_verdict_is_written_beside_the_artifact(tmp_path):
    """'Was this run accepted' must be a FILE, not a memory."""
    art = tmp_path / "run.json"
    art.write_text("{}\n")
    acc = ctl.accept_run(art, identity="spatial_10m_cr0.9", requested_guard=40000)
    out = ctl.write_acceptance(acc, art)
    assert out.exists()
    written = json.loads(out.read_text())
    assert written["identity"] == "spatial_10m_cr0.9"
    assert written["passed"] is False
    assert written["failures"]


# --- 5. reruns are bounded and declared -------------------------------------
def test_a_rerun_without_a_reason_is_refused():
    led = ctl.RerunLedger()
    led.record_attempt("i")
    with pytest.raises(ctl.ControlRefusal, match="record its reason BEFORE it runs"):
        led.may_rerun("i", "   ")


def test_one_automatic_repeat_is_allowed():
    led = ctl.RerunLedger()
    led.record_attempt("i")
    assert led.may_rerun("i", "artifact did not load") is True
    assert led.reasons("i") == ["artifact did not load"]


def test_a_second_automatic_repeat_stops_and_escalates():
    """Uncontrolled reruns are how an inconvenient result gets replaced by a
    convenient one."""
    led = ctl.RerunLedger()
    led.record_attempt("i")
    led.may_rerun("i", "artifact did not load")
    led.record_attempt("i")
    with pytest.raises(ctl.ControlRefusal, match="already used its one automatic repeat"):
        led.may_rerun("i", "still failing")
