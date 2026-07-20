"""
Acceptance tests for M2a.1 — the reusable case-study flow builder
`casestudy_flow_builder.build_flow_state(group, state='baseline', *, work_dir)`.

Structure:
* REGRESSION GUARD (real group-0 build; skipped when mf6 is unavailable):
  builder output compared DIRECTLY to the COMMITTED golden
  (`_SUPPORT/src/golden/group0_flow.{npz,manifest.json}`) -- PRIMARY canonical
  package hashes + faithful_riv hash == committed; SECONDARY heads within
  1e-3 m (max/RMS reported); PACKAGE INVARIANTS (CHD/RIV/RCHA/NPF/WEL counts +
  Sigma cond/rate + active-cell count) == the committed NPZ.
* Cheap tests (no mf6): the M1.4 diagnostics surface shape (flow_head_delta
  NULL for baseline), the rich return-shape keys, unsupported-state guard, the
  state-(iii) interface declaration, grep gate.

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_builder.py -v
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import model_io_utils as mio  # noqa: E402
import casestudy_flow_common as cfc  # noqa: E402
import casestudy_flow_builder as b  # noqa: E402

GOLDEN_DIR = SRC_DIR / "golden"

_MF6 = cfc.resolve_mf6_exe()
_HAS_MF6 = Path(_MF6).exists() or (os.path.dirname(_MF6) == "" and __import__("shutil").which(_MF6))
requires_mf6 = pytest.mark.skipif(
    not _HAS_MF6, reason="real group-0 build needs the mf6 executable (PATH or flopy bin)"
)


def _coarse_data_present() -> bool:
    """The 05f-calibrated coarse model is present locally (no download)."""
    try:
        from data_utils import get_default_data_folder
        return (Path(get_default_data_folder()) / "calibration" / "mfsim.nam").exists()
    except Exception:
        return False


requires_coarse_data = pytest.mark.skipif(
    not _coarse_data_present(),
    reason="needs the 05f-calibrated coarse model present locally (no mf6 solve)",
)


# =============================================================================
# REGRESSION GUARD — pinned to the COMMITTED oracle (real build).
# =============================================================================
@requires_mf6
class TestRegressionGuardAgainstCommittedGolden:
    @pytest.fixture(scope="class")
    def built(self, tmp_path_factory):
        wd = tmp_path_factory.mktemp("builder_group0")
        return b.build_flow_state(0, "baseline", work_dir=wd)

    @pytest.fixture(scope="class")
    def manifest(self):
        return json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())

    @pytest.fixture(scope="class")
    def committed_spec(self):
        return mio.load_flow_spec(GOLDEN_DIR / "group0_flow.npz")

    def test_primary_canonical_package_hashes_match(self, built, manifest):
        assert built["grid_hash"] == manifest["aggregate_hash"]
        assert built["package_hashes"] == manifest["array_hashes"]

    def test_faithful_riv_hash_matches_committed(self, built, manifest):
        assert built["riv_info"]["hash"] == manifest["faithful_riv"]["hash"]

    def test_secondary_heads_within_1e_3_m(self, built, manifest):
        hb = np.asarray(built["heads"], dtype=float)
        hg = np.asarray(manifest["heads"], dtype=float)
        assert hb.shape == hg.shape
        d = np.abs(hb - hg)
        max_d, rms_d = float(d.max()), float(np.sqrt((d ** 2).mean()))
        assert max_d <= 1e-3, f"heads max delta {max_d:.3e} m exceeds 1e-3 m (RMS {rms_d:.3e})"

    def test_package_invariants_match_committed_npz(self, built, committed_spec):
        sp = built["spec"]
        cs = committed_spec
        # counts
        assert len(sp["chd_cellid"]) == len(cs["chd_cellid"])
        assert len(sp["riv_cellid"]) == len(cs["riv_cellid"])
        assert len(sp["wel_cellid"]) == len(cs["wel_cellid"])
        assert int(sp["ncpl"]) == int(cs["ncpl"])
        assert int(np.count_nonzero(np.asarray(sp["idomain"]))) == \
               int(np.count_nonzero(np.asarray(cs["idomain"])))
        # sums (RIV conductance, WEL rate) + RCHA/NPF totals
        assert sum(sp["riv_cond"]) == pytest.approx(sum(cs["riv_cond"]), abs=1e-6)
        assert sum(sp["wel_rate"]) == pytest.approx(sum(cs["wel_rate"]), abs=1e-6)
        assert float(np.sum(sp["rch"])) == pytest.approx(float(np.sum(cs["rch"])), rel=1e-9)
        assert float(np.sum(sp["k"])) == pytest.approx(float(np.sum(cs["k"])), rel=1e-9)

    def test_diagnostics_baseline_json_written_with_flow_ids(self, built):
        diag_path = Path(built["workspace"]) / "diagnostics.baseline.json"
        assert diag_path.exists()
        diag = json.loads(diag_path.read_text())
        assert set(diag.keys()) == set(b.FLOW_DIAGNOSTIC_IDS)
        # flow_head_delta null for baseline; everything passes on the clean run
        assert diag["flow_head_delta"]["value"] is None
        assert all(e["passed"] for e in diag.values())

    def test_rich_return_shape_keys_present(self, built):
        for key in b.BUILD_RESULT_KEYS:
            assert key in built, f"build_flow_state result missing {key!r}"
        assert built["gwf_name"] == "group0_baseline"
        assert built["headfile"].endswith("group0_baseline.hds")
        assert built["budgetfile"].endswith("group0_baseline.cbc")
        assert built["stress_period"]["nper"] == 1 and built["stress_period"]["steady"] is True
        assert built["units"]["length"] == "meters"


# =============================================================================
# Finding 3: hash-regression coverage that does NOT need mf6 (spec-only, no
# solve) + a hub-required assertion so the real guard cannot silently skip on
# the target. The hub CI MUST exercise TestRegressionGuardAgainstCommittedGolden
# (which does the full mf6 solve).
# =============================================================================
@requires_coarse_data
def test_builder_spec_hashes_match_committed_without_solve():
    """Always-on (no mf6): the builder's baseline SPEC canonical package
    hashes + faithful-RIV hash reproduce the COMMITTED golden manifest -- so a
    `common`-code drift that changes the frozen spec is caught even on a box
    without the mf6 solver."""
    import model_io_utils as _mio
    mother = _mio.ensure_flow_model()
    _sim, cgwf = cfc.load_coarse_model(mother)
    coarse_heads = cgwf.output.head().get_data().flatten()
    boundary_gdf, river_gdf = cfc.load_gis(mother)
    refine_points = cfc.group_refine_points(0)
    spec, riv_info = cfc.build_baseline_spec(
        cgwf, boundary_gdf, river_gdf, refine_points, coarse_heads,
    )
    agg, arr = cfc.spec_canonical_hashes(spec)
    manifest = json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())
    assert agg == manifest["aggregate_hash"]
    assert arr == manifest["array_hashes"]
    assert riv_info["hash"] == manifest["faithful_riv"]["hash"]


def test_regression_guard_is_exercised_on_hub():
    """On the hub/target (AGM_HUB=1) the real mf6 regression guard must NOT be
    skipped -- mf6 has to be available so the full build+solve is checked."""
    if os.environ.get("AGM_HUB") == "1":
        assert _HAS_MF6, (
            "AGM_HUB=1 but mf6 is unavailable: the real group-0 regression "
            "guard (build+solve vs committed golden) would silently skip"
        )


# =============================================================================
# M1.4 diagnostics surface (cheap; format_budget_summary stubbed).
# =============================================================================
class TestDiagnosticsSurface:
    def _stub_budget(self, monkeypatch, pct):
        monkeypatch.setattr(
            b.mio, "format_budget_summary",
            lambda gwf: pd.DataFrame(
                {"Inflow (m3/d)": ["-"], "Outflow (m3/d)": ["-"], "Net (m3/d)": [pct]},
                index=["PERCENT ERROR"],
            ),
        )

    def test_shape_is_m14_id_entry_dict_with_null_head_delta(self, monkeypatch):
        self._stub_budget(monkeypatch, 0.01)
        diag = b._emit_flow_diagnostics(
            converged=True, heads=np.array([8.0, 8.5, 9.0]), botm=np.array([0.0, 0.0, 0.0]),
            gwf=object(),
        )
        assert set(diag.keys()) == set(b.FLOW_DIAGNOSTIC_IDS)
        # each value is an M1.4 entry dict
        for e in diag.values():
            assert {"value", "triggered_severity", "passed"} <= set(e)
        # baseline: flow_head_delta is NULL (not a faked zero), and passes
        assert diag["flow_head_delta"]["value"] is None
        assert diag["flow_head_delta"]["passed"] is True
        assert diag["flow_convergence"]["value"] is True
        assert diag["finite_heads"]["value"] is True
        assert diag["flow_no_dry_cells"]["value"] == 0

    def test_dry_cell_counted(self, monkeypatch):
        self._stub_budget(monkeypatch, 0.01)
        diag = b._emit_flow_diagnostics(
            converged=True, heads=np.array([8.0, -1.0, 9.0]), botm=np.array([0.0, 0.0, 0.0]),
            gwf=object(),
        )
        assert diag["flow_no_dry_cells"]["value"] == 1

    def test_nonfinite_head_flags_finite_heads_false(self, monkeypatch):
        self._stub_budget(monkeypatch, 0.01)
        diag = b._emit_flow_diagnostics(
            converged=True, heads=np.array([8.0, np.nan, 9.0]), botm=np.array([0.0, 0.0, 0.0]),
            gwf=object(),
        )
        assert diag["finite_heads"]["value"] is False
        assert diag["finite_heads"]["passed"] is False

    def test_diagnostics_json_is_strict_serializable(self, monkeypatch, tmp_path):
        self._stub_budget(monkeypatch, 0.01)
        diag = b._emit_flow_diagnostics(
            converged=True, heads=np.array([8.0, 8.5, 9.0]), botm=np.array([0.0, 0.0, 0.0]),
            gwf=object(),
        )
        # must serialize with allow_nan=False (RFC-8259) -- no NaN/Inf leaks
        (tmp_path / "d.json").write_text(json.dumps(diag, allow_nan=False))


class TestBuilderNonFiniteHeadGate:
    """Finding 4: a converged run with a non-finite head must RAISE (the
    dry-cell count / downstream metadata would be silently wrong otherwise)."""

    def test_nan_head_makes_build_flow_state_raise(self, tmp_path, monkeypatch):
        # Stub the whole assemble+solve to a converged run with a NaN head, and
        # the coarse-model/GIS/spec plumbing so no real MODFLOW/Triangle runs.
        monkeypatch.setattr(b.mio, "ensure_flow_model", lambda: tmp_path / "mother")
        monkeypatch.setattr(
            b.cfc, "load_coarse_model",
            lambda m: (None, type("G", (), {"output": type("O", (), {"head": staticmethod(
                lambda: type("H", (), {"get_data": staticmethod(lambda: np.zeros((1, 1, 3)))})())})()})()),
        )
        monkeypatch.setattr(b.cfc, "load_gis", lambda m: (None, None))
        monkeypatch.setattr(b.cfc, "group_refine_points", lambda g: [(0.0, 0.0), (1.0, 1.0)])
        spec = {"botm": np.array([0.0, 0.0, 0.0])}
        monkeypatch.setattr(b.cfc, "build_baseline_spec", lambda *a, **k: (spec, {"hash": "x"}))
        monkeypatch.setattr(
            b.cfc, "assemble_flow_state",
            lambda spec, **k: {
                "heads": np.array([8.0, np.nan, 9.0]), "converged": True,
                "gwf": object(), "sim": object(), "model_name": "g0",
                "headfile": str(tmp_path / "g0.hds"), "budgetfile": str(tmp_path / "g0.cbc"),
            },
        )
        monkeypatch.setattr(
            b.mio, "format_budget_summary",
            lambda gwf: pd.DataFrame(
                {"Inflow (m3/d)": ["-"], "Outflow (m3/d)": ["-"], "Net (m3/d)": [0.01]},
                index=["PERCENT ERROR"],
            ),
        )
        with pytest.raises(RuntimeError, match="(?i)non-finite|nan"):
            b.build_flow_state(0, "baseline", work_dir=tmp_path / "wd")
        # the diagnostics surface was still written (with finite_heads failing)
        diag = json.loads((tmp_path / "wd" / "diagnostics.baseline.json").read_text())
        assert diag["finite_heads"]["value"] is False


# =============================================================================
# Unsupported-state guard + state-(iii) interface + grep gate.
# =============================================================================
class TestContract:
    def test_unsupported_state_raises_not_implemented(self, tmp_path):
        with pytest.raises(NotImplementedError, match="(?i)state"):
            b.build_flow_state(0, "wells_only", work_dir=tmp_path)

    def test_state_iii_interface_declares_required_keys(self):
        fake_result = {
            "grid_hash": "abc123", "headfile": "/x/group0_baseline.hds",
            "budgetfile": "/x/group0_baseline.cbc", "gwf_name": "group0_baseline",
            "stress_period": dict(b.STRESS_PERIOD), "units": dict(b.UNITS),
        }
        iface = b.state_iii_interface(fake_result)
        assert set(iface.keys()) == set(b.STATE_III_INTERFACE_KEYS)
        assert iface["no_regridding"] is True
        assert iface["grid_hash"] == "abc123"
        assert iface["state_id"] == "wells_plus_scenario"

    def test_state_iii_interface_grid_hash_binds_to_manifest(self):
        manifest = json.loads((GOLDEN_DIR / "group0_flow.manifest.json").read_text())
        fake_result = {
            "grid_hash": manifest["aggregate_hash"], "headfile": "/x/h.hds",
            "budgetfile": "/x/b.cbc", "gwf_name": "g0", "stress_period": {}, "units": {},
        }
        iface = b.state_iii_interface(fake_result)
        assert iface["grid_hash"] == manifest["aggregate_hash"]

    def test_builder_does_not_import_the_golden_generator(self):
        src = (SRC_DIR / "casestudy_flow_builder.py").read_text()
        import re
        assert not re.search(r"^\s*import\s+casestudy_flow_golden", src, re.MULTILINE)
        assert not re.search(r"^\s*from\s+casestudy_flow_golden\s+import", src, re.MULTILINE)

    def test_grep_gate_no_legacy_strings(self):
        low = (SRC_DIR / "casestudy_flow_builder.py").read_text().lower()
        assert "nwt" not in low
        assert "modflow-nwt" not in low
        assert "telescop" not in low
