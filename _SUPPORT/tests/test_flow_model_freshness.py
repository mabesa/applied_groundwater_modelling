"""Tests for the ensure_flow_model freshness enforcement (model_io_utils).

The shipped flow_model_mf6 archive can be replaced IN PLACE at the same Dropbox url
(as in the 1,080->2,160 pumping recalibration), so a cached zip / existing local
workspace would otherwise silently keep the OLD flow field. These tests pin the fix:
a stamped (current) workspace is used as-is, an unstamped/old one forces a re-download
(defeating the cache), and a legitimate local 05f output is NOT clobbered once stamped.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import model_io_utils as mio  # noqa: E402


def _tiny_model(ws):
    """Write a minimal loadable MF6/DISV workspace (2 cells, 2 pumping wells)."""
    flopy = pytest.importorskip("flopy")
    sim = flopy.mf6.MFSimulation(sim_name="t", sim_ws=str(ws))
    flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1.0)])
    flopy.mf6.ModflowIms(sim)
    gwf = flopy.mf6.ModflowGwf(sim, modelname="limmat_valley")
    vertices = [[0, 0.0, 0.0], [1, 1.0, 0.0], [2, 2.0, 0.0], [3, 0.0, 1.0],
                [4, 1.0, 1.0], [5, 2.0, 1.0]]
    cell2d = [[0, 0.5, 0.5, 4, 0, 1, 4, 3], [1, 1.5, 0.5, 4, 1, 2, 5, 4]]
    flopy.mf6.ModflowGwfdisv(gwf, nlay=1, ncpl=2, nvert=6, top=10.0, botm=0.0,
                             vertices=vertices, cell2d=cell2d)
    flopy.mf6.ModflowGwfic(gwf, strt=10.0)
    flopy.mf6.ModflowGwfnpf(gwf, k=10.0)
    flopy.mf6.ModflowGwfwel(gwf, stress_period_data=[[(0, 0), -540.0], [(0, 1), -540.0]])
    sim.write_simulation(silent=True)


def test_stamp_writes_current_manifest(tmp_path):
    ws = tmp_path / "cal"; ws.mkdir()
    _tiny_model(ws)
    assert mio._flow_manifest_version(ws) == 0            # unstamped
    m = mio.stamp_flow_manifest(ws)
    assert m["archive_version"] == mio.FLOW_MODEL_MIN_VERSION
    assert m["pumping_m3d"] == pytest.approx(-1080.0)
    assert mio._flow_manifest_version(ws) == mio.FLOW_MODEL_MIN_VERSION


def test_fresh_workspace_used_without_download(tmp_path, monkeypatch):
    ws = tmp_path / "cal"; ws.mkdir()
    _tiny_model(ws)
    mio.stamp_flow_manifest(ws)                            # mark current

    import data_utils
    monkeypatch.setattr(data_utils, "download_named_file",
                        lambda *a, **k: pytest.fail("must not download a fresh workspace"))
    assert mio.ensure_flow_model(ws) == ws                 # returned as-is


def test_stale_workspace_forces_refetch(tmp_path, monkeypatch):
    ws = tmp_path / "cal"; ws.mkdir()
    _tiny_model(ws)                                        # unstamped => stale (v0)

    calls = {}
    import data_utils

    def fake_dl(name, dest_folder=None, force=False, **kw):
        calls.update(name=name, force=force)
        raise RuntimeError("network blocked in test")     # only the call is asserted

    monkeypatch.setattr(data_utils, "download_named_file", fake_dl)
    with pytest.warns(UserWarning, match="stale"):
        with pytest.raises(Exception):
            mio.ensure_flow_model(ws)
    assert calls == {"name": "flow_model_mf6", "force": True}
