"""Tests for the A16 / S3b nine-mesh regression check.

The check itself is the evidence mechanism C1 **A16** requires for milestone S3b
("regression evidence for the NINE FROZEN case-study group meshes"). These tests exist
to answer the only question that matters about such a mechanism:

    🔴 **can it fail?**

A check that always passes is not evidence. The negative controls below corrupt a golden
in a temporary copy and assert the checker reports FAIL -- so a green nine-mesh run means
something.

They also pin the platform contract: mesh-topology hashes are enforced only on the
golden's generation OS, and when they are skipped that is reported as SKIP, never
silently folded into the pass count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_SUPPORT" / "src"))
sys.path.insert(0, str(REPO / "_SUPPORT" / "src" / "scripts"))

import casestudy_flow_builder as b  # noqa: E402
import check_nine_mesh_goldens as nine  # noqa: E402

GOLDEN_DIR = REPO / "_SUPPORT" / "src" / "golden"


# --- 1. the mechanism covers all nine, not just group 0 ---------------------
def test_default_group_set_is_all_nine():
    assert tuple(b.ALL_GROUPS) == tuple(range(9))
    assert len(b.ALL_GROUPS) == 9


def test_every_group_has_a_committed_golden():
    """A16 names NINE frozen meshes; the checker must have something to check."""
    missing = [g for g in b.ALL_GROUPS if b._frozen_golden_manifest(g) is None]
    assert not missing, f"groups without a committed golden manifest: {missing}"


# --- 2. NEGATIVE CONTROLS -- the check must be able to fail ------------------
@pytest.fixture
def corrupt_golden(monkeypatch, tmp_path):
    """Serve a mutated copy of a group's manifest without touching the real file."""
    def _apply(group, mutate):
        real = json.loads((GOLDEN_DIR / f"group{group}_flow.manifest.json").read_text())
        mutate(real)
        monkeypatch.setattr(nine.b, "_frozen_golden_manifest",
                            lambda g, _m=real, _g=group: _m if g == _g else None)
        return real
    return _apply


def test_radius_divergence_is_reported_as_failure(corrupt_golden):
    """The radius check is platform-INDEPENDENT, so this control runs on every OS."""
    def bump(m):
        m["radius_used"] = float(m["radius_used"]) + 37.0
    corrupt_golden(0, bump)
    rec = nine.check_group(0)
    assert rec["result"] == "FAIL"
    assert rec["checks"]["refine_radius"] == "FAIL"
    assert any("refine_radius" in f for f in rec["failures"])


def test_a_clean_group_passes(corrupt_golden):
    """Same path, unmutated -- guards against the FAIL above being trivially true."""
    corrupt_golden(0, lambda m: None)
    rec = nine.check_group(0)
    assert rec["result"] == "PASS", rec["failures"]


# --- 3. the platform contract is explicit, never a silent pass --------------
def test_hashes_are_skipped_not_passed_off_the_generation_os(corrupt_golden):
    corrupt_golden(0, lambda m: None)
    rec = nine.check_group(0)
    hash_checks = {k: v for k, v in rec["checks"].items()
                   if k in ("aggregate_hash", "array_hashes", "faithful_riv_hash")}
    assert hash_checks, "the checker must report on the mesh-topology hashes"
    if rec["hashes_enforced"]:
        assert all(v in ("PASS", "FAIL") for v in hash_checks.values())
    else:
        # 🔴 the whole point: off the generation OS these are SKIP, and SKIP is not PASS
        assert all(v == "SKIP_CROSS_PLATFORM" for v in hash_checks.values())


def _rec(group, result="PASS", enforced=True):
    return {"group": group, "result": result, "hashes_enforced": enforced}


def test_full_a16_evidence_needs_all_nine_passing_with_hashes_enforced():
    nine_ok = [_rec(g) for g in range(9)]
    assert nine.is_full_a16_evidence(nine_ok) is True


@pytest.mark.parametrize("records, why", [
    ([_rec(g) for g in range(8)], "only eight groups -- A16 names nine"),
    ([_rec(g) for g in range(9)][:-1] + [_rec(8, result="FAIL")], "a group failed"),
    ([_rec(g) for g in range(9)][:-1] + [_rec(8, enforced=False)],
     "one group's hashes were SKIPPED, so the pin was not enforced there"),
    ([_rec(g, enforced=False) for g in range(9)],
     "a full cross-platform run: useful, but not the pin"),
])
def test_these_runs_are_not_a16_evidence(records, why):
    """🔴 The rule must REFUSE each of these, or a green non-authoritative run would be
    mistaken for the evidence A16 requires."""
    assert nine.is_full_a16_evidence(records) is False, why


def test_this_machines_run_is_evidence_only_if_it_is_the_generation_os():
    """Ties the rule to reality on whatever platform the suite is running on."""
    cross = b._golden_is_cross_platform(b._frozen_golden_manifest(0))
    rec = nine.check_group(0)
    assert rec["hashes_enforced"] is (not cross)
    assert nine.is_full_a16_evidence([rec], expected_groups=[0]) is (
        (not cross) and rec["result"] == "PASS")


# --- 4. environment mismatch is its own outcome, never a pass or a regression ---
def test_env_mismatch_is_detected_from_the_manifest():
    manifest = b._frozen_golden_manifest(0)
    assert manifest["versions"]["numpy"], "the manifest must record numpy to compare it"
    assert nine.env_mismatch(manifest) == {}, (
        "this environment should match the golden's recorded versions; if it does not, "
        "install the project's locked dependencies (uv.lock) before trusting any pin")


def test_env_mismatch_reports_each_differing_library(monkeypatch):
    monkeypatch.setattr(nine, "current_env", lambda: {
        "numpy": "2.1.3", "flopy": "3.9.3", "python": "3.12.9", "geos": "3.13.1"})
    diff = nine.env_mismatch(b._frozen_golden_manifest(0))
    assert set(diff) == {"numpy", "flopy"}
    assert diff["numpy"] == {"golden": "2.3.5", "current": "2.1.3"}


def test_kernel_bump_alone_is_not_an_env_mismatch(monkeypatch):
    """The Hub kernel moved 6.8.0-124 -> 6.8.0-136 between freeze and re-run. A kernel
    bump is not a numerical difference and must not be reported as one."""
    golden = b._frozen_golden_manifest(0)["versions"]
    monkeypatch.setattr(nine, "current_env", lambda: {
        k: golden[k] for k in ("numpy", "flopy", "python", "geos")})
    assert nine.env_mismatch(b._frozen_golden_manifest(0)) == {}


def test_env_mismatch_run_is_never_a16_evidence():
    """🔴 The failure mode this guards: nine ENV_MISMATCH results must not be mistaken
    for either a clean run or a real regression."""
    recs = [{"group": g, "result": "ENV_MISMATCH", "hashes_enforced": False}
            for g in range(9)]
    assert nine.is_full_a16_evidence(recs) is False


def test_topology_and_cell_properties_are_classified_apart():
    """`botm` is an elevation sampled onto the mesh, not mesh topology. Bucketing it as
    topology made an earlier run report 'mesh intact: False' for an intact mesh."""
    assert "botm" in nine._CELL_PROPERTY_MEMBERS
    assert "strt" in nine._CELL_PROPERTY_MEMBERS
    assert "botm" not in nine._TOPOLOGY_MEMBERS
    assert "gridprops__vertices" in nine._TOPOLOGY_MEMBERS
    assert not (nine._TOPOLOGY_MEMBERS & nine._CELL_PROPERTY_MEMBERS)


# --- 5. regression: the diff must build at the GOLDEN's radius ---------------
@pytest.mark.parametrize("group", [1, 3, 4, 5, 6])   # the radius-62 goldens
def test_diff_builds_at_the_goldens_own_radius_not_the_default(group):
    """🔴 Regression guard for a bug in this very script.

    The builder walks `retry_radii` = (70, 62, 78, 56, 84) and freezes whichever first
    converged, so FIVE of the nine goldens are radius 62 -- not the default 70. The first
    version of `member_level_diff` called `build_baseline_spec` without a radius, silently
    built at 70, and compared it against a 62 golden. It then reported EVERY member as
    differing, which read as a catastrophic regression and sent the investigation after a
    cause that did not exist.
    """
    manifest = b._frozen_golden_manifest(group)
    assert manifest["radius_used"] == 62.0, "fixture assumption: these goldens are r=62"
    d = nine.member_level_diff(group, manifest)
    assert d.get("error") is None, d
    assert d["built_at_radius"] == 62.0
    # the tell-tale of the bug: essentially every member differing at once
    total = (len(d["topology_members_differing"])
             + len(d["cell_property_members_differing"])
             + len(d["package_members_differing"]))
    assert total < 10, (
        f"group {group} reports {total} differing members -- the signature of comparing "
        f"a radius-70 build against a radius-62 golden")


def test_radius_70_and_radius_62_goldens_give_the_same_signature():
    """Whatever differs must differ for the same reason on both radii; a split by radius
    means the comparison, not the model, is at fault."""
    sigs = {}
    for group in (0, 3):                      # r=70 and r=62
        m = b._frozen_golden_manifest(group)
        d = nine.member_level_diff(group, m)
        sigs[group] = set(d["cell_property_members_differing"])
    assert sigs[0] == sigs[3], (
        f"radius-70 group differs in {sigs[0]}, radius-62 group in {sigs[3]} -- "
        "a radius-dependent signature indicates a comparison bug")
