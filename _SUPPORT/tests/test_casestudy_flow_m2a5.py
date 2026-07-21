"""
Acceptance tests for M2a.5 -- single-walk ALL-STATES orchestration, the
transport (FMI) budget-record assertion, Linux-golden-or-deferral anchoring,
and the hub-gated smoke.

MACOS-DOABLE (this file):
* `build_all_flow_states(0)` -- one canonical grid, states i/ii/half/iii, grid
  hash + refine_radius equal across all four (+ == committed group-0 golden),
  before/after-solve invariance (real group-0 build; skipped without mf6).
* `assert_transport_budget_records` -- real group-0 state-iii CBC carries
  FLOW-JA-FACE + DATA-SPDIS + the enabled-package boundary records, non-empty;
  synthetic stale-file + missing-record cases FAIL.
* `assert_all_groups_anchored()` -- 4 provisional goldens (0/2/7/8) + 5
  deferrals (1/3/4/5/6), golden XOR deferral, provisional-vs-authoritative
  split + hub-pending report; neither/both FAILS; deferral schema.
* The hub smoke is present + correctly SKIPPED on macOS; the hard hub-gate
  FAILS if AGM_HUB=1 but mf6 (hence the smoke) is unavailable.

HUB-TODO (cannot run here): the actual Linux/JupyterHub smoke + the
authoritative Linux goldens -- see DESIGN_DOCS/student_casestudy_M2a5_HUB_TODO.md.

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_m2a5.py -v
"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import numpy as np  # noqa: E402
import casestudy_flow_common as cfc  # noqa: E402
import casestudy_flow_builder as b  # noqa: E402

GOLDEN_DIR = SRC_DIR / "golden"

_MF6 = cfc.resolve_mf6_exe()
_HAS_MF6 = Path(_MF6).exists() or (
    os.path.dirname(_MF6) == "" and __import__("shutil").which(_MF6)
)
requires_mf6 = pytest.mark.skipif(
    not _HAS_MF6, reason="real group-0 build needs the mf6 executable (PATH or flopy bin)"
)

# Hub gate: the smoke is REQUIRED on Linux/JupyterHub (AGM_HUB=1) and SKIPPED
# on macOS/dev. A skipped smoke can NEVER be acceptance evidence (Codex #6).
requires_hub = pytest.mark.skipif(
    os.environ.get("AGM_HUB") != "1",
    reason="hub-only smoke: set AGM_HUB=1 on Linux/JupyterHub (see M2a5_HUB_TODO.md)",
)


# =====================================================================
# 0. gridprops normalisation (format-flexible cell2d) -- no mf6
# =====================================================================
class TestNormCell2d:
    def test_flattened_and_nested_representations_agree(self):
        # FLATTENED: (icell2d, xc, yc, ncvert, iv0, iv1, ...), padded with None
        flat = [
            [0, 0.5, 0.5, 4, 0, 1, 2, 3, None],       # quad, one padding column
            [1, 1.6, 0.8, 5, 1, 4, 5, 6, 2],          # pentagon, full width
        ]
        # NESTED: (icell2d, xc, yc, ncvert, [iv0, iv1, ...]) -- single list field
        nested = [
            (0, 0.5, 0.5, 4, [0, 1, 2, 3]),
            (1, 1.6, 0.8, 5, np.array([1, 4, 5, 6, 2])),
        ]
        norm_flat = b._norm_cell2d(flat)
        norm_nested = b._norm_cell2d(nested)
        assert norm_flat == norm_nested
        # exact connectivity preserved, padding truncated to ncvert
        assert norm_flat[0] == (0, 0.5, 0.5, 4, (0, 1, 2, 3))
        assert norm_flat[1] == (1, 1.6, 0.8, 5, (1, 4, 5, 6, 2))


# =====================================================================
# A. Single-walk ALL-STATES orchestration (one canonical grid)
# =====================================================================
@requires_mf6
class TestBuildAllFlowStatesGroup0:
    @pytest.fixture(scope="class")
    def allstates(self, tmp_path_factory):
        wd = tmp_path_factory.mktemp("g0_all_states")
        return b.build_all_flow_states(0, work_dir=wd)

    def test_emits_all_four_states(self, allstates):
        for key in b.ALL_STATE_KEYS:
            assert key in allstates, f"missing state {key!r}"
            assert allstates[key]["grid_hash"], f"state {key!r} has no grid_hash"

    def test_one_canonical_grid_all_four_hashes_equal(self, allstates):
        hashes = {allstates[k]["grid_hash"] for k in b.ALL_STATE_KEYS}
        assert len(hashes) == 1, f"states did not share one grid hash: {hashes}"
        assert allstates["grid_hash"] in hashes

    def test_grid_hash_equals_committed_group0_golden(self, allstates):
        manifest = b._frozen_golden_manifest(0)
        assert manifest is not None, "group-0 golden should be committed"
        # The Triangle/Voronoi mesh (hence the grid hash) is platform-DEPENDENT:
        # the committed golden is a valid oracle only on its own generation OS.
        # On its OS (macOS) this asserts equality; cross-OS (e.g. the Linux hub)
        # it legitimately differs -> skip until the authoritative regen.
        if b._golden_is_cross_platform(manifest):
            pytest.skip(
                "cross-platform provisional golden; grid_hash differs cross-OS; "
                "re-verify after the Linux authoritative regen"
            )
        assert allstates["grid_hash"] == manifest["aggregate_hash"]

    def test_refine_radius_equal_and_frozen(self, allstates):
        manifest = b._frozen_golden_manifest(0)
        assert allstates["refine_radius"] == float(manifest["radius_used"])
        # every state carries the same walked radius
        for k in b.ALL_STATE_KEYS:
            assert allstates[k].get("refine_radius", allstates["refine_radius"]) == \
                allstates["refine_radius"]

    def test_records_runtime(self, allstates):
        assert isinstance(allstates["runtime_s"], float) and allstates["runtime_s"] > 0
        assert allstates["wells_plus_scenario"]["runtime_s"] == allstates["runtime_s"]

    def test_diagnostics_written_per_state(self, allstates, tmp_path_factory):
        # the sub-builders emit diagnostics.<state>.json into the work dir
        wd = Path(allstates["baseline"]["diagnostics_file"]).parent
        for name in ("baseline", "wells_only", "wells_only_halfrate", "wells_plus_scenario"):
            assert (wd / f"diagnostics.{name}.json").exists(), name

    # ---- FMI budget-record assertion (real CBC) ----
    def test_state_iii_interface_fmi_records(self, allstates):
        iface = b.state_iii_interface(allstates["wells_plus_scenario"], assert_fmi=True)
        rec = iface["fmi_records"]
        assert "FLOW-JA-FACE" in rec["records"]
        assert "DATA-SPDIS" in rec["records"]
        # enabled boundary packages for group 0: WEL, RIV, CHD, RCHA
        for text in ("WEL", "RIV", "CHD", "RCHA"):
            assert text in rec["boundary_records"], text
        assert rec["grid_hash"] == allstates["grid_hash"]
        assert rec["steady_time"] == 1.0

    def test_assert_transport_budget_records_real(self, allstates):
        res = allstates["wells_plus_scenario"]
        report = b.assert_transport_budget_records(
            res["gwf"], res["budgetfile"],
            headfile=res["headfile"], grid_hash=res["grid_hash"],
        )
        for text in ("FLOW-JA-FACE", "DATA-SPDIS", "WEL", "RIV", "CHD", "RCHA"):
            assert text in report["records"], text

    def test_fmi_missing_boundary_record_fails(self, allstates, monkeypatch):
        # if an enabled-package boundary text is EXPECTED but not in the CBC,
        # the assertion FAILS (a synthetic missing-record case on a real file).
        monkeypatch.setattr(b, "_expected_boundary_texts", lambda gwf: {"DRN"})
        res = allstates["wells_plus_scenario"]
        with pytest.raises(AssertionError, match="DRN"):
            b.assert_transport_budget_records(res["gwf"], res["budgetfile"])

    # ---- Finding 2: the SOLVED model grid is verified == canonical ----
    def test_solved_grid_identity_accepts_the_canonical_grid(self, allstates):
        res = allstates["wells_plus_scenario"]
        # the state's own spec carries the canonical geometry -> passes
        b._assert_solved_grid_is_canonical(
            {"gwf": res["gwf"]}, res["spec"], group=0, state="wells_plus_scenario"
        )

    def test_solved_grid_identity_rejects_changed_cardinality(self, allstates):
        # a re-refined grid with a DIFFERENT cell count must be caught.
        res = allstates["wells_plus_scenario"]
        bad = copy.deepcopy(res["spec"])
        bad["ncpl"] = int(bad["ncpl"]) + 1
        with pytest.raises(RuntimeError, match="did NOT solve the one canonical grid"):
            b._assert_solved_grid_is_canonical(
                {"gwf": res["gwf"]}, bad, group=0, state="wells_plus_scenario"
            )

    def test_solved_grid_identity_rejects_moved_vertex_same_cardinality(self, allstates):
        # SAME cardinality (ncpl/nvert/#vertices/#cell2d unchanged) but a vertex
        # COORDINATE moved -> a length-only check would MISS this; the value
        # check must RAISE (Codex REWORK #2 crux).
        res = allstates["wells_plus_scenario"]
        bad = copy.deepcopy(res["spec"])
        v = bad["gridprops"]["vertices"]
        moved = list(v[1])
        moved[1] = float(moved[1]) + 3.0  # shift x, keep ivert + count
        v[1] = moved
        with pytest.raises(RuntimeError, match="COORDINATES|did NOT solve the one canonical grid"):
            b._assert_solved_grid_is_canonical(
                {"gwf": res["gwf"]}, bad, group=0, state="wells_plus_scenario"
            )

    def test_solved_grid_identity_rejects_changed_connectivity_same_cardinality(self, allstates):
        # SAME cardinality but the cell2d vertex-index connectivity changed
        # (swap two vertices of cell 0) -> the value check must RAISE.
        res = allstates["wells_plus_scenario"]
        bad = copy.deepcopy(res["spec"])
        c = bad["gridprops"]["cell2d"]
        row = list(c[0])
        assert len(row) >= 6 and row[4] != row[5]  # >=2 vertices, distinct
        row[4], row[5] = row[5], row[4]  # reorder connectivity, same ncvert
        c[0] = row
        with pytest.raises(RuntimeError, match="CONNECTIVITY|did NOT solve the one canonical grid"):
            b._assert_solved_grid_is_canonical(
                {"gwf": res["gwf"]}, bad, group=0, state="wells_plus_scenario"
            )


# =====================================================================
# B. FMI staleness guard (synthetic, no mf6)
# =====================================================================
def _fake_gwf(*, oc_budget, oc_head, sim_path):
    oc = SimpleNamespace(
        budget_filerecord=SimpleNamespace(array=[(oc_budget,)]),
        head_filerecord=SimpleNamespace(array=[(oc_head,)]),
    )
    return SimpleNamespace(
        get_package=lambda name: oc if name == "OC" else None,
        simulation=SimpleNamespace(
            simulation_data=SimpleNamespace(
                mfpath=SimpleNamespace(get_sim_path=lambda: sim_path)
            )
        ),
    )


class TestFmiStalenessGuard:
    def test_stale_or_foreign_budget_name_fails(self, tmp_path):
        # OC declares run.cbc but the interface points at a DIFFERENT file ->
        # a stale/foreign CBC can NOT satisfy the check.
        gwf = _fake_gwf(oc_budget="run.cbc", oc_head="run.hds", sim_path=str(tmp_path))
        foreign = tmp_path / "someother.cbc"
        foreign.write_bytes(b"")
        with pytest.raises(AssertionError, match="stale/foreign"):
            b.assert_transport_budget_records(gwf, foreign)

    def test_budget_outside_workspace_fails(self, tmp_path):
        # name matches OC but the file lives OUTSIDE the model workspace.
        gwf = _fake_gwf(oc_budget="run.cbc", oc_head="run.hds", sim_path=str(tmp_path / "ws"))
        (tmp_path / "ws").mkdir()
        elsewhere = tmp_path / "run.cbc"
        elsewhere.write_bytes(b"")
        with pytest.raises(AssertionError, match="workspace"):
            b.assert_transport_budget_records(gwf, elsewhere)

    def test_no_oc_package_fails(self, tmp_path):
        gwf = SimpleNamespace(get_package=lambda name: None)
        with pytest.raises(AssertionError, match="no OC package"):
            b.assert_transport_budget_records(gwf, tmp_path / "x.cbc")

    def test_run_start_time_flags_stale_budget(self, tmp_path):
        # Codex REWORK #4: with a run-start timestamp, an OLD CBC (from an
        # earlier solve in the same ws) is flagged STALE before it is opened.
        import os
        import time as _time
        ws = tmp_path / "ws"
        ws.mkdir()
        gwf = _fake_gwf(oc_budget="run.cbc", oc_head="run.hds", sim_path=str(ws))
        cbc = ws / "run.cbc"
        hds = ws / "run.hds"
        cbc.write_bytes(b"")
        hds.write_bytes(b"")
        old = _time.time() - 3600.0  # an hour before the (future) run start
        os.utime(cbc, (old, old))
        with pytest.raises(AssertionError, match="STALE"):
            b.assert_transport_budget_records(
                gwf, cbc, headfile=hds, run_start_time=_time.time(),
            )

    def test_head_file_outside_workspace_fails(self, tmp_path):
        # budget passes (name+parent OK) but the HEAD file is out of the ws:
        # the head-parent guard (Codex REWORK #4) catches it before opening.
        ws = tmp_path / "ws"
        ws.mkdir()
        gwf = _fake_gwf(oc_budget="run.cbc", oc_head="run.hds", sim_path=str(ws))
        (ws / "run.cbc").write_bytes(b"")
        foreign_head = tmp_path / "run.hds"  # correct name, WRONG dir
        foreign_head.write_bytes(b"")
        with pytest.raises(AssertionError, match="head file.*workspace"):
            b.assert_transport_budget_records(gwf, ws / "run.cbc", headfile=foreign_head)


# =====================================================================
# C. Linux-golden-or-deferral anchoring
# =====================================================================
class TestAnchoring:
    def test_all_groups_anchored_passes(self):
        # Graduation-invariant: assert the STRUCTURE -- every group anchored by
        # exactly one of golden XOR deferral, and the three buckets partition
        # ALL_GROUPS -- NOT a snapshot of which groups are provisional today.
        # Survives the Linux-golden graduation (deferrals shrink, goldens grow,
        # provisional -> authoritative) with no test edit.
        report = b.assert_all_groups_anchored()
        assert report["anchored"] is True
        buckets = (
            report["authoritative_goldens"]
            + report["provisional_goldens"]
            + report["deferrals"]
        )
        assert sorted(buckets) == sorted(b.ALL_GROUPS)   # exact partition
        assert len(buckets) == len(set(buckets))          # no group in two buckets

    def test_hub_pending_report(self):
        # Invariant: hub_pending mirrors the report's own deferral/provisional
        # lists, whatever the current graduation state is.
        report = b.assert_all_groups_anchored()
        hp = report["hub_pending"]
        assert hp["deferred_need_linux_golden"] == report["deferrals"]
        assert hp["provisional_need_linux_reverify"] == report["provisional_goldens"]

    def test_deferral_schema(self):
        # Iterate the deferrals ACTUALLY committed (derived from disk), so this
        # tracks graduation instead of a hard-coded [1,3,4,5,6] snapshot.
        deferred = [g for g in b.ALL_GROUPS if b._load_deferral(g) is not None]
        for g in deferred:
            d = b._load_deferral(g)
            assert d is not None, f"group {g} deferral missing"
            for key in b.DEFERRAL_KEYS:
                assert key in d, f"group {g} deferral missing key {key!r}"
            assert d["group"] == g
            rw = d["radius_walked"]
            assert isinstance(rw, (int, float)) and not isinstance(rw, bool) and rw > 0
            assert d["authoritative_platform"] == "linux"
            assert d["status"] == "linux-pending"
            assert isinstance(d["mf6_version"], str) and d["mf6_version"]

    def test_golden_provisional_flag_consistent_with_generation_os(self):
        # Invariant (replaces the old "0/2/7/8 are provisional" snapshot): a
        # committed golden is provisional IFF it was NOT frozen on the
        # authoritative platform (Linux). Holds for the macOS-provisional
        # goldens AND the graduated Linux-authoritative ones.
        for g in b.ALL_GROUPS:
            m = b._frozen_golden_manifest(g)
            if m is None:
                continue
            expected_provisional = b._golden_generation_os(m) != "Linux"
            assert bool(m.get("provisional")) is expected_provisional, (
                f"group {g}: provisional={m.get('provisional')} but generation "
                f"OS is {b._golden_generation_os(m)!r}"
            )
            assert m.get("authoritative_platform") == "linux"

    def test_golden_xor_deferral_no_overlap(self):
        # a group is NEVER both a golden and a deferral
        for g in b.ALL_GROUPS:
            has_golden = b._frozen_golden_manifest(g) is not None
            has_deferral = b._load_deferral(g) is not None
            assert has_golden != has_deferral, f"group {g}: golden XOR deferral violated"

    def test_both_golden_and_deferral_fails(self, monkeypatch):
        # group 0 has a golden; inject a phantom deferral -> BOTH -> FAIL
        monkeypatch.setattr(b, "_load_deferral", lambda g: {"group": g} if g == 0 else None)
        with pytest.raises(AssertionError, match="BOTH"):
            b.assert_all_groups_anchored(groups=[0])

    def test_neither_golden_nor_deferral_fails(self, monkeypatch):
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)
        monkeypatch.setattr(b, "_load_deferral", lambda g: None)
        with pytest.raises(AssertionError, match="NEITHER"):
            b.assert_all_groups_anchored(groups=[0])

    def test_malformed_deferral_fails(self, monkeypatch):
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)
        monkeypatch.setattr(b, "_load_deferral", lambda g: {"group": g})  # missing keys
        with pytest.raises(AssertionError, match="missing keys"):
            b.assert_all_groups_anchored(groups=[3])

    def _valid_deferral(self, group=3):
        # A synthetic, schema-complete deferral (independent of what's on disk),
        # so the negative tests below don't depend on any group still being
        # deferred after the Linux-golden graduation.
        return {
            "group": group,
            "reason": "synthetic deferral for negative testing",
            "platform": "macOS-arm64",
            "mf6_version": "6.7.0",
            "date": "2026-07-21",
            "radius_walked": 62,
            "authoritative_platform": "linux",
            "status": "linux-pending",
        }

    def test_deferral_wrong_group_field_fails(self, monkeypatch):
        # Finding 5: group field must equal the group it anchors
        bad = self._valid_deferral(3); bad["group"] = 99
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)
        monkeypatch.setattr(b, "_load_deferral", lambda g: bad)
        with pytest.raises(AssertionError, match="group field"):
            b.assert_all_groups_anchored(groups=[3])

    def test_deferral_nonpositive_radius_fails(self, monkeypatch):
        bad = self._valid_deferral(3); bad["radius_walked"] = 0
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)
        monkeypatch.setattr(b, "_load_deferral", lambda g: bad)
        with pytest.raises(AssertionError, match="radius_walked"):
            b.assert_all_groups_anchored(groups=[3])

    def test_deferral_boolean_radius_rejected(self, monkeypatch):
        # bool is a subclass of int -- must NOT count as a positive number
        bad = self._valid_deferral(3); bad["radius_walked"] = True
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)
        monkeypatch.setattr(b, "_load_deferral", lambda g: bad)
        with pytest.raises(AssertionError, match="radius_walked"):
            b.assert_all_groups_anchored(groups=[3])


# =====================================================================
# C2. Cross-PLATFORM golden pin (M2a.5 hub) -- the mesh is platform-dependent
#
# A golden is a valid pin/oracle ONLY on its own generation OS (REGARDLESS of
# the provisional flag). Skip cross-OS; enforce same-OS; enforce when the
# generation OS is undeterminable (fail-safe).
# =====================================================================
class TestCrossPlatformGoldenPin:
    def _manifest(self, gen_platform, *, provisional=True):
        return {
            "aggregate_hash": "GOLDEN_AGG", "array_hashes": {"a": "1"},
            "faithful_riv": {"hash": "GOLDEN_RIV"}, "radius_used": 70.0,
            "provisional": provisional, "versions": {"platform": gen_platform},
        }

    # ---- the helper ----
    def test_helper_cross_os_true_regardless_of_provisional(self, monkeypatch):
        monkeypatch.setattr(b.platform, "system", lambda: "Linux")
        assert b._golden_is_cross_platform(self._manifest("macOS-26.5.2-arm64-arm-64bit"))
        assert b._golden_is_cross_platform(
            self._manifest("macOS-26.5.2-arm64-arm-64bit", provisional=False)
        )

    def test_helper_same_os_false(self, monkeypatch):
        monkeypatch.setattr(b.platform, "system", lambda: "Darwin")
        assert not b._golden_is_cross_platform(self._manifest("macOS-26.5.2-arm64-arm-64bit"))
        # a Linux golden viewed from Linux is also same-OS
        monkeypatch.setattr(b.platform, "system", lambda: "Linux")
        assert not b._golden_is_cross_platform(self._manifest("Linux-6.8.0-x86_64"))

    def test_helper_undeterminable_os_enforces(self, monkeypatch):
        monkeypatch.setattr(b.platform, "system", lambda: "Linux")
        assert not b._golden_is_cross_platform({"provisional": True, "versions": {}})
        assert not b._golden_is_cross_platform({"provisional": True})  # no versions at all
        assert not b._golden_is_cross_platform(self._manifest("Plan9-weird"))  # unrecognised

    # ---- Gap 1: malformed manifest/versions must NOT crash -> enforce ----
    def test_helper_non_dict_versions_enforces(self, monkeypatch):
        monkeypatch.setattr(b.platform, "system", lambda: "Linux")
        assert b._golden_generation_os({"versions": "bad"}) == ""
        assert not b._golden_is_cross_platform({"versions": "bad"})  # no crash -> enforce

    def test_helper_non_dict_manifest_enforces(self, monkeypatch):
        monkeypatch.setattr(b.platform, "system", lambda: "Linux")
        for bad in ("not-a-dict", None, ["list"], 42):
            assert b._golden_generation_os(bad) == ""
            assert not b._golden_is_cross_platform(bad)  # no crash -> enforce

    # ---- Gap 2: unknown CURRENT OS must fail-safe ENFORCE, not skip ----
    def test_helper_unknown_current_os_enforces(self, monkeypatch):
        monkeypatch.setattr(b.platform, "system", lambda: "Plan9")
        # golden gen-OS is KNOWN (macOS) but current OS is unknown -> NOT cross
        assert not b._golden_is_cross_platform(self._manifest("macOS-26.5.2-arm64"))

    def test_pin_enforces_on_unknown_current_os(self, monkeypatch):
        monkeypatch.setattr(b.platform, "system", lambda: "Plan9")
        monkeypatch.setattr(
            b, "_frozen_golden_manifest", lambda g: self._manifest("macOS-26.5.2-arm64")
        )
        monkeypatch.setattr(b.cfc, "spec_canonical_hashes", lambda spec: ("DIFFERENT", {"a": "9"}))
        with pytest.raises(RuntimeError, match="DIVERGED"):
            b._pin_built_grid_to_frozen_golden(0, {"s": 1}, {"hash": "GOLDEN_RIV"}, 70.0)

    # ---- the pin (skip vs enforce) ----
    def test_pin_skips_cross_platform(self, monkeypatch):
        # (a) Linux building vs a macOS golden -> SKIP even though hashes mismatch
        monkeypatch.setattr(b.platform, "system", lambda: "Linux")
        monkeypatch.setattr(
            b, "_frozen_golden_manifest", lambda g: self._manifest("macOS-26.5.2-arm64")
        )
        monkeypatch.setattr(b.cfc, "spec_canonical_hashes", lambda spec: ("DIFFERENT", {"a": "9"}))
        b._pin_built_grid_to_frozen_golden(0, {"s": 1}, {"hash": "DIFFERENT_RIV"}, 62.0)  # no raise

    def test_pin_skips_cross_platform_even_if_authoritative(self, monkeypatch):
        # provisional is ORTHOGONAL: a non-provisional Linux golden viewed from
        # macOS still skips (cross-OS) -> no false failure once the hub commits it.
        monkeypatch.setattr(b.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(
            b, "_frozen_golden_manifest",
            lambda g: self._manifest("Linux-6.8.0-x86_64", provisional=False),
        )
        monkeypatch.setattr(b.cfc, "spec_canonical_hashes", lambda spec: ("DIFFERENT", {"a": "9"}))
        b._pin_built_grid_to_frozen_golden(0, {"s": 1}, {"hash": "DIFFERENT_RIV"}, 62.0)  # no raise

    def test_pin_enforces_same_platform(self, monkeypatch):
        # (b) Darwin building vs the macOS golden -> ENFORCE -> mismatch RAISES
        monkeypatch.setattr(b.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(
            b, "_frozen_golden_manifest", lambda g: self._manifest("macOS-26.5.2-arm64")
        )
        monkeypatch.setattr(b.cfc, "spec_canonical_hashes", lambda spec: ("DIFFERENT", {"a": "9"}))
        with pytest.raises(RuntimeError, match="DIVERGED"):
            b._pin_built_grid_to_frozen_golden(0, {"s": 1}, {"hash": "GOLDEN_RIV"}, 70.0)

    def test_pin_enforces_when_gen_os_undeterminable(self, monkeypatch):
        # (c) missing versions.platform -> fail-safe ENFORCE -> mismatch RAISES
        monkeypatch.setattr(b.platform, "system", lambda: "Linux")
        m = self._manifest("macOS-26.5.2-arm64"); m["versions"] = {}
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: m)
        monkeypatch.setattr(b.cfc, "spec_canonical_hashes", lambda spec: ("DIFFERENT", {"a": "9"}))
        with pytest.raises(RuntimeError, match="DIVERGED"):
            b._pin_built_grid_to_frozen_golden(0, {"s": 1}, {"hash": "GOLDEN_RIV"}, 70.0)


# =====================================================================
# D. FENCE + hub smoke + the hard hub gate
# =====================================================================
# =====================================================================
# D. FENCE (RUNTIME-ENFORCED) -- Codex REWORK #1
#
# The fence must actually PREVENT a caller from getting divergent grids via
# independent non-baseline builds on an UNPINNED group, not merely document it.
# =====================================================================
class TestFence:
    def test_independent_nonbaseline_on_unpinned_group_raises(self, monkeypatch, tmp_path):
        # unpinned = no committed golden. The fence must RAISE before the walk.
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)

        def _no_walk(*a, **k):
            raise AssertionError("fence must raise BEFORE the walk/solve")

        monkeypatch.setattr(b, "_refine_solve_baseline_walk", _no_walk)
        for state in ("wells_only", "wells_plus_scenario"):
            with pytest.raises(RuntimeError, match="UNPINNED"):
                b.build_flow_state(3, state, work_dir=tmp_path / state)

    def test_escape_hatch_bypasses_fence(self, monkeypatch, tmp_path):
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)
        seen = {}

        def _stub_walk(*a, **k):
            seen["walked"] = True
            raise RuntimeError("past-fence-sentinel")

        monkeypatch.setattr(b, "_refine_solve_baseline_walk", _stub_walk)
        with pytest.raises(RuntimeError, match="past-fence-sentinel"):
            b.build_flow_state(3, "wells_only", work_dir=tmp_path, allow_independent_grid=True)
        assert seen.get("walked"), "escape hatch must let the build proceed past the fence"

    def test_pinned_group_exempt_from_fence(self, monkeypatch, tmp_path):
        # group 0 is pinned -> non-baseline allowed without the escape hatch.
        def _stub_walk(*a, **k):
            raise RuntimeError("past-fence-sentinel")

        monkeypatch.setattr(b, "_refine_solve_baseline_walk", _stub_walk)
        with pytest.raises(RuntimeError, match="past-fence-sentinel"):
            b.build_flow_state(0, "wells_only", work_dir=tmp_path)

    def test_baseline_state_never_fenced(self, monkeypatch, tmp_path):
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)

        def _stub_walk(*a, **k):
            raise RuntimeError("reached-walk")

        monkeypatch.setattr(b, "_refine_solve_baseline_walk", _stub_walk)
        with pytest.raises(RuntimeError, match="reached-walk"):
            b.build_flow_state(3, "baseline", work_dir=tmp_path)

    def test_build_all_flow_states_not_blocked_by_fence(self, monkeypatch, tmp_path):
        # the sanctioned all-states path reaches the SINGLE walk for an unpinned
        # group with NO fence block -- the asymmetry vs independent calls.
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)

        def _stub_walk(*a, **k):
            raise RuntimeError("reached-single-walk")

        monkeypatch.setattr(b, "_refine_solve_baseline_walk", _stub_walk)
        with pytest.raises(RuntimeError, match="reached-single-walk"):
            b.build_all_flow_states(3, work_dir=tmp_path)

    def test_build_wells_states_not_blocked_by_fence(self, monkeypatch, tmp_path):
        # Codex REWORK #1 regression: build_wells_states reaches its state builds
        # via the SANCTIONED seam (_solve_validate_wells on ONE walk), NOT a
        # fenced independent build_flow_state -- so it works for an UNPINNED
        # group too. Prove it reaches the single walk with no fence block.
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)

        def _stub_walk(*a, **k):
            raise RuntimeError("reached-single-walk")

        monkeypatch.setattr(b, "_refine_solve_baseline_walk", _stub_walk)
        with pytest.raises(RuntimeError, match="reached-single-walk"):
            b.build_wells_states(3, work_dir=tmp_path)

    @requires_mf6
    def test_build_wells_states_succeeds_for_unpinned_group(self, monkeypatch, tmp_path):
        # End-to-end: make group 0 LOOK unpinned (golden -> None), then the
        # sanctioned orchestrator still BUILDS both states on one grid -- the
        # fence never blocks a legitimate walker-group orchestration.
        monkeypatch.setattr(b, "_frozen_golden_manifest", lambda g: None)
        both = b.build_wells_states(0, work_dir=tmp_path)
        assert both["full"]["grid_hash"] == both["half"]["grid_hash"] == both["grid_hash"]
        assert both["half"]["head_delta_max_m"] < both["full"]["head_delta_max_m"]


# =====================================================================
# E. hub smoke + the hard hub gate
# =====================================================================
class TestFenceAndHubGate:
    def test_build_all_flow_states_is_the_documented_fence(self):
        # the single-walk orchestration exists and is the documented SOLE entry
        assert hasattr(b, "build_all_flow_states")
        assert b.ALL_STATE_KEYS == (
            "baseline", "wells_only", "wells_only_half", "wells_plus_scenario"
        )
        assert "sole" in b.build_all_flow_states.__doc__.lower() or \
            "SOLE" in Path(b.__file__).read_text()

    def test_grep_gate_clean(self):
        text = Path(b.__file__).read_text().lower()
        for banned in ("nwt", "telescop", "modflow-nwt"):
            assert banned not in text, f"banned token {banned!r} present in builder module"

    def test_hub_gate_smoke_is_acceptance_evidence(self):
        # On the hub (AGM_HUB=1) mf6 MUST be present so the smoke actually RUNS
        # -- a skipped smoke is never acceptance evidence. On macOS/dev this is
        # the documented non-acceptance state (the hub run is the real gate).
        if os.environ.get("AGM_HUB") == "1":
            assert _HAS_MF6, (
                "AGM_HUB=1 but mf6 unavailable: the smoke would SKIP -> not "
                "acceptance evidence (the hub target MUST provide mf6)"
            )

    @requires_hub
    def test_m2a5_smoke(self, tmp_path):
        # HUB acceptance smoke: build group-0 all-states + diagnostics +
        # interface + FMI records on Linux/JupyterHub. SKIPPED on macOS.
        allstates = b.build_all_flow_states(0, work_dir=tmp_path)
        assert set(b.ALL_STATE_KEYS) <= set(allstates)
        iface = b.state_iii_interface(allstates["wells_plus_scenario"], assert_fmi=True)
        assert "FLOW-JA-FACE" in iface["fmi_records"]["records"]
        assert allstates["runtime_s"] > 0
        b.assert_all_groups_anchored()
