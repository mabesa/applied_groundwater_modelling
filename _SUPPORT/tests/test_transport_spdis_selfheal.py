"""Regression test for the DATA-SPDIS self-heal in transport_srcpulse_demo.

A pre-computed / archived calibrated flow model whose NPF was saved WITHOUT
``save_specific_discharge`` produces a budget (.cbc) that carries the usual flow
records but no ``DATA-SPDIS`` -- which is exactly what breaks 04t on a fresh
JupyterHub ("The specified text string is not in the budget file"), because the
transport track reads ``get_data(text='DATA-SPDIS')`` to place the spill and
Courant-size the time steps.  ``_ensure_spdis`` must detect the gap and
regenerate the budget in place.

The archived condition is reproduced with a tiny self-contained steady GWF model
(a real, ~instant MF6 solve) rather than the full Limmat download.
"""
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import flopy  # noqa: E402
import transport_srcpulse_demo as tsd  # noqa: E402

_MF6 = shutil.which("mf6") or (
    tsd._MF6_FALLBACK if os.path.exists(tsd._MF6_FALLBACK) else None
)
pytestmark = pytest.mark.skipif(_MF6 is None, reason="mf6 executable not available")


def _build_tiny_steady_gwf(ws, *, save_spdis):
    """1-layer 10x10 confined steady GWF with a CHD head gradient (=> nonzero qx).

    Budget output is always saved; ``save_specific_discharge`` is toggled so we
    can produce a .cbc that lacks DATA-SPDIS on demand.
    """
    sim = flopy.mf6.MFSimulation(sim_name="tiny", exe_name=_MF6, sim_ws=str(ws))
    flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1.0)])
    flopy.mf6.ModflowIms(sim, complexity="SIMPLE")
    gwf = flopy.mf6.ModflowGwf(sim, modelname="tiny", save_flows=True)
    flopy.mf6.ModflowGwfdis(gwf, nlay=1, nrow=10, ncol=10, delr=10.0, delc=10.0,
                            top=10.0, botm=0.0)
    flopy.mf6.ModflowGwfic(gwf, strt=10.0)
    flopy.mf6.ModflowGwfnpf(gwf, icelltype=0, k=10.0, save_flows=True,
                            save_specific_discharge=save_spdis)
    chd = ([[(0, r, 0), 10.0] for r in range(10)]
           + [[(0, r, 9), 8.0] for r in range(10)])
    flopy.mf6.ModflowGwfchd(gwf, stress_period_data=chd)
    flopy.mf6.ModflowGwfoc(gwf, budget_filerecord="tiny.cbc",
                           head_filerecord="tiny.hds",
                           saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")])
    sim.write_simulation(silent=True)
    ok, buf = sim.run_simulation(silent=True)
    assert ok, "tiny model solve failed:\n" + "\n".join(buf[-10:])


def _spdis_present(gwf):
    try:
        recs = gwf.output.budget().get_unique_record_names(decode=True)
    except Exception:
        return False
    return any("DATA-SPDIS" in str(r) for r in recs)


def test_ensure_spdis_repairs_missing_record(tmp_path):
    """A budget without DATA-SPDIS is regenerated so the notebook call works."""
    ws = tmp_path / "cal"
    _build_tiny_steady_gwf(ws, save_spdis=False)          # archived / hub condition

    sim = flopy.mf6.MFSimulation.load(sim_ws=str(ws), exe_name=_MF6, verbosity_level=0)
    gwf = sim.get_model("tiny")
    assert not _spdis_present(gwf), "precondition: SPDIS should be absent"

    sim, gwf = tsd._ensure_spdis(sim, gwf, ws, _MF6)       # self-heal

    assert _spdis_present(gwf)
    # the exact call 04t cell 5 / refine_corridor make must now succeed
    spd = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    assert spd["qx"].shape[0] == 100                       # 10x10 cells


def test_ensure_spdis_is_noop_when_present(tmp_path):
    """When DATA-SPDIS is already there, no re-run happens (.cbc untouched)."""
    ws = tmp_path / "cal"
    _build_tiny_steady_gwf(ws, save_spdis=True)

    sim = flopy.mf6.MFSimulation.load(sim_ws=str(ws), exe_name=_MF6, verbosity_level=0)
    gwf = sim.get_model("tiny")
    assert _spdis_present(gwf)

    cbc = ws / "tiny.cbc"
    mtime_before = cbc.stat().st_mtime
    sim2, gwf2 = tsd._ensure_spdis(sim, gwf, ws, _MF6)

    assert sim2 is sim and gwf2 is gwf                     # same objects, no reload
    assert cbc.stat().st_mtime == mtime_before             # not re-run
    assert _spdis_present(gwf2)
