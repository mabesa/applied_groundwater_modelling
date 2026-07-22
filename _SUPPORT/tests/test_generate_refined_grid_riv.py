"""
FR.1 invariant tests -- ``model_io_utils.generate_refined_grid``'s RIV transfer.

FR.1 (see DESIGN_DOCS/student_casestudy_FR_steps.md) replaces
``generate_refined_grid``'s old centroid-in-polygon + per-cell area-scaling
RIV transfer -- which assigned RIV only where a refined cell CENTER fell
inside the river polygon, dropping conductance on any cell whose center
missed a narrow river footprint (measured on the real corridor: coarse 1458
reaches / Sigma cond ~136,700 -> refined 164 cells / ~88,075, i.e. ratio
~0.64) -- with a delegation to ``casestudy_refine_riv.faithful_riv_from_coarse``
(area-weighted, per-reach, conductance-conserving, overbank-filtered).

These tests exercise ONLY generate_refined_grid's plain-array spec output;
per the locked-test scoping used across this test suite, NO real
Triangle/Voronoi refinement and NO MODFLOW solve may occur here (both are
stubbed/trip-wired), so this file is safe to run on macOS without SIGILL risk
and without a real solve.

Run with:  uv run pytest _SUPPORT/tests/test_generate_refined_grid_riv.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import geopandas as gpd
import pytest
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import model_io_utils as mio  # noqa: E402
import disv_grid_utils as dgu  # noqa: E402


# =============================================================================
# Synthetic geometry: a COARSE 2x2 grid of 10 m cells (like
# test_split_refine_assembly's fixture) refined to a 4x4 grid of 5 m cells,
# both over the same 20x20 m domain. The refined grid is a REAL subdivision
# (not an identity copy) so the RIV conductance split is non-trivial: each
# coarse RIV cell overlaps FOUR refined cells, none of whose CENTERS fall
# inside the narrow river band below -- the exact shape of gap the old
# centroid-in-polygon transfer fell into.
# =============================================================================
def _make_grid(n: int, cell_size: float):
    """A regular n x n grid of ``cell_size`` cells over [0, n*cell_size]^2.

    Returns (vertices, cell2d, ncpl) in flopy DISV gridprops row format, plus
    a name->flat-index map for cell (row, col) with row 0 at the TOP (largest
    y), matching test_split_refine_assembly's existing 2x2 convention (cell 0
    = top-left, ... row-major).
    """
    verts = []
    for r in range(n + 1):
        for c in range(n + 1):
            iv = r * (n + 1) + c
            x = c * cell_size
            y = n * cell_size - r * cell_size
            verts.append([iv, float(x), float(y)])

    def ivert(r, c):
        return r * (n + 1) + c

    cell2d = []
    flat_of = {}
    for r in range(n):
        for c in range(n):
            flat = r * n + c
            xc = c * cell_size + cell_size / 2
            yc = n * cell_size - r * cell_size - cell_size / 2
            cell2d.append([
                flat, float(xc), float(yc), 4,
                ivert(r, c), ivert(r, c + 1), ivert(r + 1, c + 1), ivert(r + 1, c),
            ])
            flat_of[(r, c)] = flat
    return verts, cell2d, n * n, flat_of


_COARSE_N, _COARSE_CELL = 2, 10.0
_REFINED_N, _REFINED_CELL = 4, 5.0

_C_VERTS, _C_CELL2D, _C_NCPL, _C_FLAT = _make_grid(_COARSE_N, _COARSE_CELL)
_R_VERTS, _R_CELL2D, _R_NCPL, _R_FLAT = _make_grid(_REFINED_N, _REFINED_CELL)

# Coarse RIV: bottom-left cell (row1,col0) cond=100, bottom-right (row1,col1)
# cond=60. Both stage=14, rbot=12 (rbot=12 > botm=0 everywhere -- no
# all-overbank raise; per Codex FR.1 review this fixture is safe).
_RIV_BL = _C_FLAT[(1, 0)]
_RIV_BR = _C_FLAT[(1, 1)]
_COARSE_RIV_COND = {_RIV_BL: 100.0, _RIV_BR: 60.0}
_COARSE_SUM_COND = sum(_COARSE_RIV_COND.values())  # 160.0

# Narrow river band y in [4, 6] across the full domain width -- a coarse RIV
# cell's footprint intersects it (area 10x2=20 m^2 per coarse cell), but NO
# refined 5x5 cell's CENTER (at y=2.5, 7.5, 12.5, 17.5) ever lands inside
# [4, 6]. The old centroid-in-polygon transfer would therefore assign this
# river's conductance to ZERO refined cells; the faithful area-weighted
# transfer must still place it (fully, conserved) by footprint overlap.
_RIVER_Y0, _RIVER_Y1 = 4.0, 6.0


def _gridprops(verts, cell2d, ncpl):
    return {"nvert": len(verts), "vertices": [list(v) for v in verts],
            "cell2d": [list(c) for c in cell2d], "ncpl": ncpl}


def _build_coarse_gwf(tmp_path):
    import flopy

    ncpl = _C_NCPL
    sim = flopy.mf6.MFSimulation(
        sim_name="coarse", exe_name="mf6", sim_ws=str(tmp_path / "coarse")
    )
    flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1)])
    flopy.mf6.ModflowIms(sim)
    gwf = flopy.mf6.ModflowGwf(sim, modelname="coarse")
    flopy.mf6.ModflowGwfdisv(
        gwf, nlay=1, ncpl=ncpl, nvert=len(_C_VERTS),
        top=np.full(ncpl, 20.0), botm=[np.zeros(ncpl)],
        vertices=_C_VERTS, cell2d=_C_CELL2D,
        idomain=np.ones((1, ncpl), dtype=int),
    )
    flopy.mf6.ModflowGwfnpf(gwf, k=np.full(ncpl, 10.0), icelltype=1)
    flopy.mf6.ModflowGwfic(gwf, strt=np.full(ncpl, 15.0))
    flopy.mf6.ModflowGwfrcha(gwf, recharge=1e-4)
    flopy.mf6.ModflowGwfchd(
        gwf, stress_period_data=[((0, 0), 15.0), ((0, 1), 15.0)]
    )
    flopy.mf6.ModflowGwfriv(
        gwf, stress_period_data=[
            ((0, _RIV_BL), 14.0, _COARSE_RIV_COND[_RIV_BL], 12.0),
            ((0, _RIV_BR), 14.0, _COARSE_RIV_COND[_RIV_BR], 12.0),
        ],
    )
    return gwf


def _domain_gdf():
    return gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])],
        crs="EPSG:2056",
    )


def _river_gdf():
    return gpd.GeoDataFrame(
        geometry=[Polygon([
            (0, _RIVER_Y0), (20, _RIVER_Y0), (20, _RIVER_Y1), (0, _RIVER_Y1),
        ])],
        crs="EPSG:2056",
    )


class _StubNN:
    """Cheap stand-in for scipy.interpolate.NearestNDInterpolator: returns a
    constant broadcast of the first supplied value (identical pattern to
    test_split_refine_assembly._StubNN)."""

    def __init__(self, points, values, *a, **k):
        vals = np.asarray(values, dtype=float).ravel()
        self._val = float(vals[0]) if vals.size else 0.0

    def __call__(self, x, y=None):
        return np.full(np.shape(x), self._val, dtype=float)


def _stub_refinement(monkeypatch):
    """Patch Triangle/Voronoi generation to return the hand-built REFINED
    4x4 mesh (a real subdivision of the 2x2 coarse mesh, not an identity
    copy), and scipy NearestND to the cheap stub -- no real Triangle/Voronoi
    or MODFLOW ever runs."""
    from flopy.discretization import VertexGrid

    def fake_create(*a, **k):
        return {"disv_gridprops": _gridprops(_R_VERTS, _R_CELL2D, _R_NCPL), "ncpl": _R_NCPL}

    def fake_refine(*a, **k):
        mg = VertexGrid(
            vertices=_R_VERTS, cell2d=_R_CELL2D, ncpl=_R_NCPL, nlay=1,
            top=np.full(_R_NCPL, 20.0), botm=np.zeros((1, _R_NCPL)),
        )
        return {"disv_gridprops": _gridprops(_R_VERTS, _R_CELL2D, _R_NCPL),
                "ncpl": _R_NCPL, "modelgrid": mg}

    monkeypatch.setattr(dgu, "create_disv_from_boundary", fake_create)
    monkeypatch.setattr(dgu, "refine_grid_locally", fake_refine)
    import scipy.interpolate
    monkeypatch.setattr(scipy.interpolate, "NearestNDInterpolator", _StubNN)
    monkeypatch.setattr(mio, "NearestNDInterpolator", _StubNN, raising=False)


def _generate(monkeypatch, tmp_path):
    _stub_refinement(monkeypatch)
    import flopy
    monkeypatch.setattr(
        flopy.mf6.MFSimulation, "run_simulation",
        lambda self, *a, **k: (_ for _ in ()).throw(
            AssertionError("generate_refined_grid must not run MODFLOW")
        ),
    )
    gwf = _build_coarse_gwf(tmp_path)
    spec = mio.generate_refined_grid(
        gwf,
        _domain_gdf(),
        _river_gdf(),
        [(5.0, 5.0)],
        np.full(_C_NCPL, 15.0),
        refine_radius=150.0,
        base_cell_size=50.0,
        refined_cell_size=5.0,
        well_data=None,
    )
    return spec


class TestFaithfulRivTransfer:
    def test_riv_arrays_present_same_length_finite(self, monkeypatch, tmp_path):
        spec = _generate(monkeypatch, tmp_path)
        n = len(spec["riv_cellid"])
        assert n > 0, "faithful RIV transfer produced no records"
        assert len(spec["riv_stage"]) == n
        assert len(spec["riv_cond"]) == n
        assert len(spec["riv_rbot"]) == n
        assert np.all(np.isfinite(spec["riv_stage"]))
        assert np.all(np.isfinite(spec["riv_cond"]))
        assert np.all(np.isfinite(spec["riv_rbot"]))
        assert all(c > 0 for c in spec["riv_cond"])

    def test_riv_cells_are_active(self, monkeypatch, tmp_path):
        spec = _generate(monkeypatch, tmp_path)
        idom = np.asarray(spec["idomain"])
        for (layer, icell) in spec["riv_cellid"]:
            assert idom[icell] != 0, f"RIV placed on inactive cell {icell}"

    def test_conductance_conservation(self, monkeypatch, tmp_path):
        """The core FR.1 fix: refined Sigma cond ~= coarse Sigma cond.

        Historically (centroid-in-polygon transfer) this ratio was ~0.64 on
        the real corridor (measured: coarse Sigma cond ~136,700 -> refined
        ~88,075). In THIS synthetic fixture the old transfer would have
        dropped the river's conductance ENTIRELY (ratio 0.0 -- no refined
        cell CENTER falls in the narrow river band; see module docstring),
        so any ratio detectably far from 1.0 is a regression.
        """
        spec = _generate(monkeypatch, tmp_path)
        refined_sum_cond = float(sum(spec["riv_cond"]))
        ratio = refined_sum_cond / _COARSE_SUM_COND
        assert ratio == pytest.approx(1.0, rel=1e-6), (
            f"refined Sigma cond {refined_sum_cond:.3f} vs coarse "
            f"{_COARSE_SUM_COND:.3f} (ratio {ratio:.4f}); expected ~1.0 "
            "(conductance-conserving), not the historical ~0.64 loss"
        )

    def test_every_coarse_reach_covered(self, monkeypatch, tmp_path):
        """Coverage invariant: every coarse RIV reach must be represented
        somewhere in the refined field (mirrors
        casestudy_flow_common.apply_faithful_riv's coverage gate)."""
        spec = _generate(monkeypatch, tmp_path)
        stats = spec.get("riv_stats")
        assert stats is not None, "generate_refined_grid must surface riv_stats"
        assert stats["n_source_reaches"] == len(_COARSE_RIV_COND)
        assert stats["n_reaches_placed"] == stats["n_source_reaches"]

    def test_old_centroid_gap_would_have_missed_every_cell(self, monkeypatch, tmp_path):
        """Guard that the OLD centroid-in-polygon behavior is gone: in this
        fixture, NO refined cell center lies inside the river band, yet the
        faithful transfer still places (and conserves) every reach's
        conductance -- proving the transfer no longer depends on
        center-containment. If a future change reintroduced a
        centroid-based test, this fixture's coverage/conservation
        assertions above would fail (records would drop to 0 / ratio to 0)."""
        spec = _generate(monkeypatch, tmp_path)
        # Recompute refined cell centers from the returned gridprops and
        # confirm none fall in the river band -- i.e. this fixture really
        # does exercise the "centroid misses, footprint overlaps" gap.
        cell2d = spec["gridprops"]["cell2d"]
        centers_in_band = [
            row for row in cell2d if _RIVER_Y0 <= row[2] <= _RIVER_Y1
        ]
        assert not centers_in_band, (
            "fixture invariant violated: a refined cell center falls inside "
            "the river band, so this fixture no longer demonstrates the "
            "centroid-in-polygon gap"
        )
        # And yet the faithful transfer produced full, conserved coverage.
        assert len(spec["riv_cellid"]) > 0
        refined_sum_cond = float(sum(spec["riv_cond"]))
        assert refined_sum_cond == pytest.approx(_COARSE_SUM_COND, rel=1e-6)
