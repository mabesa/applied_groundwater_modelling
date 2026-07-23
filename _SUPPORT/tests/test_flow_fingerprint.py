"""Tests for the flow-model fingerprint primitive (model_io_utils).

The fingerprint is the shared identity that the shipped-archive manifest,
`ensure_flow_model` freshness, and every flow-derived cache key on — so a changed
calibration (e.g. the 1,080->2,160 m3/d pumping change) cannot be silently masked
by a warm cache or a stale local workspace. These tests pin its two required
properties: it is STABLE for an unchanged model and it CHANGES when a
physics-defining input (NPF/WEL/DISV/RIV/CHD/RCHA/IC) changes — but NOT when a
non-defining file (solver, output control, run outputs) changes.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import model_io_utils as mio  # noqa: E402


def _write(ws, name, data=b"x"):
    (ws / name).write_bytes(data)


def test_fingerprint_stable_and_16_hex(tmp_path):
    ws = tmp_path / "m"; ws.mkdir()
    _write(ws, "limmat_valley.npf", b"k data")
    _write(ws, "limmat_valley.wel", b"wel data")
    _write(ws, "limmat_valley.disv", b"grid data")
    fp = mio.flow_model_fingerprint(ws)
    assert len(fp) == 16 and all(c in "0123456789abcdef" for c in fp)
    assert fp == mio.flow_model_fingerprint(ws)  # stable on re-read


def test_fingerprint_changes_when_pumping_input_changes(tmp_path):
    ws = tmp_path / "m"; ws.mkdir()
    _write(ws, "limmat_valley.npf", b"k data")
    _write(ws, "limmat_valley.wel", b"pump 1080")
    _write(ws, "limmat_valley.disv", b"grid data")
    fp0 = mio.flow_model_fingerprint(ws)
    _write(ws, "limmat_valley.wel", b"pump 2160")  # changed pumping
    assert mio.flow_model_fingerprint(ws) != fp0


def test_fingerprint_ignores_non_defining_files(tmp_path):
    """Solver / output-control / run outputs must not move the fingerprint."""
    ws = tmp_path / "m"; ws.mkdir()
    _write(ws, "limmat_valley.npf", b"k data")
    _write(ws, "limmat_valley.wel", b"wel data")
    _write(ws, "limmat_valley.disv", b"grid data")
    fp0 = mio.flow_model_fingerprint(ws)
    for junk in ("limmat_valley.ims", "limmat_valley.oc", "limmat_valley.hds",
                 "limmat_valley.cbc", "limmat_valley.lst", "mfsim.nam"):
        _write(ws, junk, b"whatever")
    assert mio.flow_model_fingerprint(ws) == fp0


def test_fingerprint_requires_inputs(tmp_path):
    empty = tmp_path / "empty"; empty.mkdir()
    with pytest.raises(FileNotFoundError):
        mio.flow_model_fingerprint(empty)


def test_pumping_helper(tmp_path):
    """flow_model_pumping_m3d sums the negative-Q WEL entries of a real MF6 model."""
    flopy = pytest.importorskip("flopy")
    import numpy as np
    ws = tmp_path / "tiny"
    sim = flopy.mf6.MFSimulation(sim_name="t", sim_ws=str(ws))
    flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1.0)])
    flopy.mf6.ModflowIms(sim)
    gwf = flopy.mf6.ModflowGwf(sim, modelname="limmat_valley")
    # minimal 2-cell DISV
    vertices = [[0, 0.0, 0.0], [1, 1.0, 0.0], [2, 2.0, 0.0], [3, 0.0, 1.0],
                [4, 1.0, 1.0], [5, 2.0, 1.0]]
    cell2d = [[0, 0.5, 0.5, 4, 0, 1, 4, 3], [1, 1.5, 0.5, 4, 1, 2, 5, 4]]
    flopy.mf6.ModflowGwfdisv(gwf, nlay=1, ncpl=2, nvert=6, top=10.0, botm=0.0,
                             vertices=vertices, cell2d=cell2d)
    flopy.mf6.ModflowGwfic(gwf, strt=10.0)
    flopy.mf6.ModflowGwfnpf(gwf, k=10.0)
    # two pumping wells + one injection; helper must return only the negative sum
    flopy.mf6.ModflowGwfwel(gwf, stress_period_data=[
        [(0, 0), -540.0], [(0, 1), -540.0], [(0, 0), 200.0]])
    sim.write_simulation(silent=True)
    assert mio.flow_model_pumping_m3d(ws) == pytest.approx(-1080.0)
