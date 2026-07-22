"""
Unit tests for milestone M2b.2 -- ``casestudy_flow_particles.py`` (MF6 PRT
advective capture-zone / pathline module).

MACOS-DOABLE (this file, always-on, NO MF6/PRT solve):
* Post-processing on hand-authored SYNTHETIC track results matching the
  ``build_capture`` return contract (``pathlines_world``/``end_cells``/
  ``meta``): ``_terminal_records``/``_pathlines_and_end_cells`` (ireason==3
  vs no-terminate-record fallback), ``connection_summary`` (forward,
  end_cells==extc + n_dropped caveat), ``capture_zone_summary`` (backward,
  a DISTINCT contract that never touches ``end_cells``).
* Porosity: ``0 < porosity < 1`` validation + provenance recording, both for
  an explicit argument and for the transport-config default (group 0 ->
  0.20).
* NaN/finite guards on ``build_capture``'s own arguments (mode/n_particles/
  track_days/release_radius_m) -- these raise BEFORE any GWF/mf6 access, so
  they are exercised here without a real state_result.
* A DATA-SAT preflight test: a stub ``flopy.utils.CellBudgetFile`` missing
  ``DATA-SAT`` makes ``assert_data_sat_available`` RAISE (monkeypatched --
  no real budget file is read).
* A STATIC source-inspection test that the module text never mentions
  ``build_prt_capture``, ``_run_prt``, or ``capture_halfwidth_at`` (the
  demo-coupled, RIV-defect-carrying PRT path this module must NOT reuse).

HUB-TODO (cannot run here -- AGM_HUB=1, SKIPPED on macOS): both
``mode='forward'`` and ``mode='backward'`` PRT runs on the REAL group-0
``wells_only`` field (the reverse-file wiring is the riskiest new behavior).

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_particles.py -v
"""
from __future__ import annotations

import inspect
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import flopy  # noqa: E402

import casestudy_flow_particles as cfp  # noqa: E402

MODULE_PATH = SRC_DIR / "casestudy_flow_particles.py"

# Hub gate: the forward+backward PRT smoke is REQUIRED on Linux/JupyterHub
# (AGM_HUB=1) and SKIPPED on macOS/dev (M2a5 precedent -- a skipped smoke is
# NEVER acceptance evidence).
requires_hub = pytest.mark.skipif(
    os.environ.get("AGM_HUB") != "1",
    reason="hub-only PRT smoke: set AGM_HUB=1 on Linux/JupyterHub",
)


# =============================================================================
# Synthetic track-DataFrame builders (hand-authored, no MF6/PRT solve).
# =============================================================================
def _track_row(irpt, t, x_world, y_world, icell1based, ireason, istatus=1):
    return {
        "irpt": irpt, "t": t, "x_world": x_world, "y_world": y_world,
        "icell": icell1based, "ireason": ireason, "istatus": istatus,
    }


def _synthetic_forward_track_df():
    """Three particles released around an injection well:
    * irpt=1: reaches the extraction cell (icell=6, 0-based 5) at t=40, with a
      proper TERMINATE (ireason==3) record.
    * irpt=2: reaches a DIFFERENT cell (icell=9, 0-based 8), TERMINATE record.
    * irpt=3: never gets an ireason==3 record (still active when
      stoptraveltime closes the window) -- exercises the "no terminate
      record" fallback-to-last-row path.
    """
    rows = [
        _track_row(1, 0.0, 100.0, 200.0, 3, ireason=0),
        _track_row(1, 20.0, 110.0, 205.0, 4, ireason=1),
        _track_row(1, 40.0, 120.0, 210.0, 6, ireason=3),

        _track_row(2, 0.0, 100.0, 202.0, 3, ireason=0),
        _track_row(2, 55.0, 130.0, 215.0, 9, ireason=3),

        _track_row(3, 0.0, 100.0, 198.0, 3, ireason=0),
        _track_row(3, 10.0, 105.0, 199.0, 4, ireason=1),
        _track_row(3, 730.0, 140.0, 220.0, 12, ireason=2),  # time-step end, no term.
    ]
    return pd.DataFrame(rows)


def _synthetic_forward_capture(extc=5):
    df = _synthetic_forward_track_df()
    pathlines_world, end_cells, n_no_term = cfp._pathlines_and_end_cells(df)
    return {
        "mode": "forward",
        "pathlines_world": pathlines_world,
        "end_cells": end_cells,
        "meta": {
            "n_released": 3, "n_dropped": 1, "n_no_terminate_record": n_no_term,
        },
        "porosity_provenance": {"value": 0.2, "source": "argument"},
    }, extc


def _synthetic_backward_capture():
    rows = [
        _track_row(1, 0.0, 300.0, 400.0, 10, ireason=0),
        _track_row(1, 15.0, 310.0, 410.0, 11, ireason=3),

        _track_row(2, 0.0, 300.0, 402.0, 10, ireason=0),
        _track_row(2, 30.0, 320.0, 420.0, 14, ireason=3),

        _track_row(3, 0.0, 300.0, 398.0, 10, ireason=0),
        _track_row(3, 60.0, 330.0, 430.0, 20, ireason=3),
    ]
    df = pd.DataFrame(rows)
    pathlines_world, end_cells, n_no_term = cfp._pathlines_and_end_cells(df)
    return {
        "mode": "backward",
        "pathlines_world": pathlines_world,
        # deliberately NO "end_cells" key -- capture_zone_summary must not
        # need it (a distinct contract from connection_summary).
        "meta": {"n_released": 3, "n_dropped": 0, "n_no_terminate_record": n_no_term},
        "porosity_provenance": {"value": 0.2, "source": "argument"},
    }


# =============================================================================
# Terminal-record extraction / pathlines_world post-processing.
# =============================================================================
class TestTerminalRecordsAndPathlines:
    def test_pathlines_world_columns_and_values(self):
        df = _synthetic_forward_track_df()
        pathlines_world, end_cells, n_no_term = cfp._pathlines_and_end_cells(df)
        assert list(pathlines_world.columns) == ["irpt", "x_world", "y_world", "time"]
        assert len(pathlines_world) == len(df)
        # irpt=1's last row (t=40, x=120) must appear with column renamed to "time".
        last_row = pathlines_world[pathlines_world["irpt"] == 1].iloc[-1]
        assert last_row["time"] == pytest.approx(40.0)
        assert last_row["x_world"] == pytest.approx(120.0)

    def test_end_cells_use_ireason3_terminate_when_present(self):
        df = _synthetic_forward_track_df()
        _, end_cells, n_no_term = cfp._pathlines_and_end_cells(df)
        # irpt=1 terminates at icell=6 (1-based) -> 0-based cell 5.
        assert end_cells[1] == 5
        # irpt=2 terminates at icell=9 (1-based) -> 0-based cell 8.
        assert end_cells[2] == 8

    def test_end_cells_fallback_to_last_row_when_no_terminate_record(self):
        df = _synthetic_forward_track_df()
        _, end_cells, n_no_term = cfp._pathlines_and_end_cells(df)
        # irpt=3 has no ireason==3 row -> falls back to its LAST row
        # (icell=12, 1-based) -> 0-based cell 11.
        assert end_cells[3] == 11
        assert n_no_term == 1

    def test_terminal_records_indexed_by_irpt(self):
        df = _synthetic_forward_track_df()
        terminal = cfp._terminal_records(df)
        assert set(terminal.index) == {1, 2, 3}


# =============================================================================
# _release_z -- saturated release elevation (the HIGH fix: never release in
# the dry zone above the water table).
# =============================================================================
class TestReleaseZ:
    def test_confined_cell_uses_top(self):
        # head ABOVE top (confined) -> saturated top is `top` -> 0.5*(10+0)=5.0
        assert cfp._release_z(top=10.0, head=15.0, botm=0.0) == pytest.approx(5.0)

    def test_unconfined_cell_uses_head(self):
        # botm < head < top (unconfined) -> saturated top is `head` -> 0.5*(6+0)=3.0
        assert cfp._release_z(top=10.0, head=6.0, botm=0.0) == pytest.approx(3.0)

    def test_dry_cell_raises(self):
        # head <= botm -> the cell is dry; releasing there is a hard error.
        with pytest.raises(ValueError, match="DRY"):
            cfp._release_z(top=10.0, head=-1.0, botm=0.0)

    def test_head_equal_botm_raises(self):
        with pytest.raises(ValueError, match="DRY"):
            cfp._release_z(top=10.0, head=0.0, botm=0.0)

    @pytest.mark.parametrize("top,head,botm", [
        (float("nan"), 6.0, 0.0),
        (10.0, float("nan"), 0.0),
        (10.0, 6.0, float("nan")),
        (float("inf"), 6.0, 0.0),
    ])
    def test_nonfinite_input_raises(self, top, head, botm):
        with pytest.raises(ValueError, match="finite"):
            cfp._release_z(top=top, head=head, botm=botm)


# =============================================================================
# NaN in the loaded track frame must RAISE (the finite guard fires before any
# post-processing / comparison -- a recurring bug class in this repo).
# =============================================================================
class TestTrackFiniteGuard:
    def test_nan_x_world_raises(self):
        df = _synthetic_forward_track_df()
        df.loc[2, "x_world"] = float("nan")
        with pytest.raises(ValueError, match="non-finite"):
            cfp._pathlines_and_end_cells(df)

    def test_nan_time_raises(self):
        df = _synthetic_forward_track_df()
        df.loc[1, "t"] = float("nan")
        with pytest.raises(ValueError, match="non-finite"):
            cfp._pathlines_and_end_cells(df)

    def test_invalid_icell_raises(self):
        df = _synthetic_forward_track_df()
        df.loc[0, "icell"] = 0  # 0 is not a valid 1-based cell index
        with pytest.raises(ValueError, match="icell"):
            cfp._pathlines_and_end_cells(df)


# =============================================================================
# connection_summary (forward) -- end_cells==extc + n_dropped caveat.
# =============================================================================
class TestConnectionSummary:
    def test_fraction_counts_and_mean_travel_time(self):
        capture, extc = _synthetic_forward_capture(extc=5)
        summary = cfp.connection_summary(capture, extc)
        # Only irpt=1 terminates at extc==5; released=3 (from meta).
        assert summary["n_released"] == 3
        assert summary["n_reached_extraction"] == 1
        assert summary["advective_connection_fraction"] == pytest.approx(1.0 / 3.0)
        assert summary["mean_travel_time_d_to_extraction"] == pytest.approx(40.0)
        # n_dropped is carried through from meta (the release-disc caveat),
        # NOT folded into advective_connection_fraction's denominator.
        assert summary["n_dropped"] == 1

    def test_no_particles_reach_extraction_gives_zero_fraction_and_nan_time(self):
        capture, _ = _synthetic_forward_capture(extc=999)  # a cell nobody reaches
        summary = cfp.connection_summary(capture, 999)
        assert summary["n_reached_extraction"] == 0
        assert summary["advective_connection_fraction"] == pytest.approx(0.0)
        assert math.isnan(summary["mean_travel_time_d_to_extraction"])

    def test_wrong_mode_raises(self):
        backward_capture = _synthetic_backward_capture()
        with pytest.raises(ValueError):
            cfp.connection_summary(backward_capture, 5)


# =============================================================================
# capture_zone_summary (backward) -- a SEPARATE contract, no end_cells==extc.
# =============================================================================
class TestCaptureZoneSummary:
    def test_pathline_count_and_max_backtrack_time(self):
        backward_capture = _synthetic_backward_capture()
        summary = cfp.capture_zone_summary(backward_capture)
        assert summary["capture_zone_pathline_count"] == 3
        assert summary["max_backtrack_time_d"] == pytest.approx(60.0)
        assert isinstance(summary["envelope_note"], str) and summary["envelope_note"]

    def test_does_not_require_end_cells_key(self):
        # The fixture deliberately omits "end_cells" -- capture_zone_summary
        # must not KeyError reaching for it (distinct contract from
        # connection_summary's end_cells==extc).
        backward_capture = _synthetic_backward_capture()
        assert "end_cells" not in backward_capture
        cfp.capture_zone_summary(backward_capture)  # must not raise

    def test_wrong_mode_raises(self):
        capture, _ = _synthetic_forward_capture()
        with pytest.raises(ValueError):
            cfp.capture_zone_summary(capture)


# =============================================================================
# Porosity: 0<phi<1 validation + provenance.
# =============================================================================
class TestPorosity:
    def test_argument_source_provenance(self):
        value, prov = cfp.resolve_porosity({"group": 0}, 0.33)
        assert value == pytest.approx(0.33)
        assert prov["source"] == "argument"
        assert prov["file"] is None and prov["key"] is None and prov["config_hash"] is None
        assert prov["group"] == 0

    @pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.5, float("nan"), float("inf")])
    def test_argument_out_of_range_or_nonfinite_raises(self, bad):
        with pytest.raises(ValueError):
            cfp.resolve_porosity({"group": 0}, bad)

    def test_config_default_group0_is_0p20_with_provenance(self):
        value, prov = cfp.resolve_porosity({"group": 0}, None)
        assert value == pytest.approx(0.20)
        assert prov["source"] == "config"
        assert prov["group"] == 0
        assert prov["file"] and Path(prov["file"]).exists()
        assert "porosity" in prov["key"]
        assert isinstance(prov["config_hash"], str) and len(prov["config_hash"]) == 64

    def test_config_default_unknown_group_raises(self):
        with pytest.raises(KeyError):
            cfp.resolve_porosity({"group": 999}, None)


# =============================================================================
# NaN/finite guards on build_capture's own arguments (raise before touching
# any GWF/mf6 state -- exercised here with a throwaway state_result).
# =============================================================================
class TestBuildCaptureArgGuards:
    def test_bad_mode_raises(self, tmp_path):
        with pytest.raises(ValueError):
            cfp.build_capture({}, mode="sideways", work_dir=tmp_path)

    @pytest.mark.parametrize("bad_n", [0, -5])
    def test_bad_n_particles_raises(self, tmp_path, bad_n):
        with pytest.raises(ValueError):
            cfp.build_capture({}, mode="forward", n_particles=bad_n, work_dir=tmp_path)

    @pytest.mark.parametrize("bad_days", [0.0, -1.0, float("nan"), float("inf")])
    def test_bad_track_days_raises(self, tmp_path, bad_days):
        with pytest.raises(ValueError):
            cfp.build_capture(
                {}, mode="forward", track_days=bad_days, work_dir=tmp_path,
            )

    @pytest.mark.parametrize("bad_radius", [0.0, -3.0, float("nan"), float("inf")])
    def test_bad_release_radius_raises(self, tmp_path, bad_radius):
        with pytest.raises(ValueError):
            cfp.build_capture(
                {}, mode="forward", release_radius_m=bad_radius, work_dir=tmp_path,
            )


# =============================================================================
# DATA-SAT / FMI preflight (monkeypatched CellBudgetFile -- no real file).
# =============================================================================
class _StubCellBudgetFileMissingDataSat:
    def __init__(self, *args, **kwargs):
        pass

    def get_unique_record_names(self):
        return [b"FLOW-JA-FACE    ", b"DATA-SPDIS      ", b"WEL             "]

    def get_data(self, text=None):
        return [np.ones(3)]


class _StubCellBudgetFileComplete:
    def __init__(self, *args, **kwargs):
        pass

    def get_unique_record_names(self):
        return [b"FLOW-JA-FACE    ", b"DATA-SPDIS      ", b"DATA-SAT        "]

    def get_data(self, text=None):
        # all required records present AND non-empty.
        return [np.ones(3)]


class _StubCellBudgetFileEmptyDataSat:
    """All three record NAMES present, but DATA-SAT's payload is EMPTY at the
    steady time -- the presence-only preflight would pass; the non-empty
    preflight must RAISE."""
    def __init__(self, *args, **kwargs):
        pass

    def get_unique_record_names(self):
        return [b"FLOW-JA-FACE    ", b"DATA-SPDIS      ", b"DATA-SAT        "]

    def get_data(self, text=None):
        name = text.strip() if isinstance(text, str) else text
        if name == "DATA-SAT":
            return [np.array([])]
        return [np.ones(3)]


class TestDataSatPreflight:
    def test_missing_data_sat_raises(self, monkeypatch):
        monkeypatch.setattr(flopy.utils, "CellBudgetFile", _StubCellBudgetFileMissingDataSat)
        with pytest.raises(ValueError, match="DATA-SAT"):
            cfp.assert_data_sat_available("does-not-exist.cbc")

    def test_present_but_empty_data_sat_raises(self, monkeypatch):
        monkeypatch.setattr(flopy.utils, "CellBudgetFile", _StubCellBudgetFileEmptyDataSat)
        with pytest.raises(ValueError, match="EMPTY"):
            cfp.assert_data_sat_available("does-not-exist.cbc")

    def test_complete_records_pass(self, monkeypatch):
        monkeypatch.setattr(flopy.utils, "CellBudgetFile", _StubCellBudgetFileComplete)
        cfp.assert_data_sat_available("does-not-exist.cbc")  # must not raise


# =============================================================================
# Static source-inspection: never reuse the demo-coupled PRT path.
# =============================================================================
class TestNoDemoCoupledReuse:
    def test_module_never_mentions_forbidden_symbols(self):
        text = MODULE_PATH.read_text()
        for forbidden in ("build_prt_capture", "_run_prt", "capture_halfwidth_at"):
            assert forbidden not in text, (
                f"casestudy_flow_particles.py must not import/call {forbidden!r} "
                "(demo-coupled, RIV-transfer-defect-carrying path)"
            )


# =============================================================================
# HUB-GATED integration: BOTH modes on the real group-0 field. SKIPPED on
# macOS. A skipped smoke here is NEVER acceptance evidence (M2a5 precedent).
# =============================================================================
@requires_hub
class TestHubPRTIntegration:
    def test_forward_and_backward_on_real_group0_field(self, tmp_path):
        import casestudy_flow_builder as cfb

        state = cfb.build_flow_state(0, "wells_only", work_dir=tmp_path / "flow")
        doublet = state["doublet"]
        extc = doublet["extraction"]["cell"]

        forward = cfp.build_capture(
            state, mode="forward", n_particles=100, track_days=730.0,
            work_dir=tmp_path,
        )
        assert forward["mode"] == "forward"
        assert len(forward["pathlines_world"]) > 0
        conn = cfp.connection_summary(forward, extc)
        assert conn["n_reached_extraction"] >= 1

        backward = cfp.build_capture(
            state, mode="backward", n_particles=100, track_days=730.0,
            work_dir=tmp_path,
        )
        assert backward["mode"] == "backward"
        assert len(backward["pathlines_world"]) > 0
        capzone = cfp.capture_zone_summary(backward)
        assert capzone["capture_zone_pathline_count"] >= 1
