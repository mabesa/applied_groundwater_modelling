"""
Acceptance tests for milestone M2a.0 -- the FROZEN, builder-independent 05f
golden reference (regression anchor) for student group 0.

Module under test: ``_SUPPORT/src/casestudy_flow_golden.py``. It composes
already-shipped infra (``model_io_utils.generate_refined_grid`` /
``assemble_gwf_from_spec`` / ``freeze_flow_spec`` / ``load_flow_spec``, and
``scripts.jupyterhub_refine_reliability_gen``'s ``group_refine_points`` /
``run_group_determinism_check`` / ``RETRY_RADII`` / ``_was_retried``) plus
NEW pieces: ``baseline_well_data`` (238 background wells, no doublet, sign
preserved), ``canonicalize_wel_entries`` (deterministic duplicate-cellid
aggregation BEFORE the model is solved), the four pin-time validators (mass
balance, no-dry-cells, near-field coarse-vs-refined head agreement with two
NAMED tolerances, package-construction incl. geometry intersection), and a
subprocess-isolated runner mirroring
``jupyterhub_refine_reliability_gen.subprocess_refine_runner`` but driving a
NEW no-doublet baseline refine function (this module owns its own
``_CHILD_FLAG`` / child entry point -- the doublet-hardwired
``_real_refine_group`` in the sibling script is left untouched).

LOCKED-TEST SCOPING (mirrors the rest of this repo's test suite): no test
here runs real Triangle/Voronoi refinement or a real MF6 solve. The
subprocess/IPC path is driven via the ``AGM_FAKE_SPEC_NPZ`` /
``AGM_FAKE_CHILD_SIGNAL`` child hooks (same names the sibling
``jupyterhub_refine_reliability_gen`` script uses); the one full
orchestration test stubs ``flopy.mf6.MFSimulation.run_simulation`` /
``flopy.mf6.ModflowGwf.output`` (as ``test_pinned_flow_loader.py`` does) so
``assemble_gwf_from_spec`` only WRITES, never solves.

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_golden.py -v
"""

from __future__ import annotations

import copy
import inspect
import json
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
SCRIPTS_DIR = SRC_DIR / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import model_io_utils as mio  # noqa: E402
import case_artifact_lock as cal  # noqa: E402
import jupyterhub_refine_reliability_gen as rg  # noqa: E402
import casestudy_flow_golden as cfg  # noqa: E402


# =============================================================================
# Synthetic tiny *ragged* DISV spec -- same shape the rest of the suite uses
# (triangle + two quads). No Triangle/Voronoi involved.
#
#   verts:   3---4---5      (y=10)
#            |   |   |
#            0---1---2      (y=0)
#
#   cell2d:  0 = triangle, centroid (3, 6)
#            1 = quad,     centroid (5, 5)
#            2 = quad,     centroid (15, 5)
# =============================================================================
_VERTICES = [
    [0, 0.0, 0.0], [1, 10.0, 0.0], [2, 20.0, 0.0],
    [3, 0.0, 10.0], [4, 10.0, 10.0], [5, 20.0, 10.0],
]
_CELL2D = [
    [0, 3.0, 6.0, 3, 3, 0, 4],       # triangle (nv=3)
    [1, 5.0, 5.0, 4, 0, 1, 4, 3],    # quad     (nv=4)
    [2, 15.0, 5.0, 4, 1, 2, 5, 4],   # quad     (nv=4)
]
_NCPL = 3
_NVERT = 6


def _gridprops():
    return {
        "nvert": _NVERT,
        "vertices": [list(v) for v in _VERTICES],
        "cell2d": [list(c) for c in _CELL2D],
        "ncpl": _NCPL,
    }


def make_spec(**overrides):
    """A fully valid synthetic (canonical, no-doublet-shaped) flow spec."""
    spec = {
        "gridprops": _gridprops(),
        "ncpl": _NCPL,
        "top": np.array([10.0, 10.0, 10.0]),
        "botm": np.array([0.0, 0.0, 0.0]),
        "k": np.array([7.5, 3.25, 12.0]),
        "rch": np.array([1e-4, 1e-4, 1e-4]),
        "strt": np.array([8.0, 8.5, 9.0]),
        "idomain": np.ones(_NCPL, dtype=int),
        "chd_cellid": [(0, 0), (0, 2)],
        "chd_head": [8.0, 9.0],
        "riv_cellid": [(0, 1)],
        "riv_stage": [7.5],
        "riv_cond": [50.0],
        "riv_rbot": [6.0],
        "wel_cellid": [(0, 1), (0, 2)],
        "wel_rate": [-30.0, 25.0],
        "well_cells": [1, 2],
        "refine_radius_used": 70.0,
        "crs": "EPSG:2056",
    }
    spec.update(overrides)
    return spec


def make_heads(**overrides):
    heads = np.array([8.2, 8.6, 9.1])
    return heads


# =============================================================================
# Criterion 0 -- module hygiene: no import of / shared assembly with the
# (nonexistent) M2a.1 builder.
# =============================================================================
class TestNoBuilderImportGuard:
    def test_source_never_imports_builder_module(self):
        """The docstring is free to NAME casestudy_flow_builder (to explain
        that this generator is deliberately independent of it); what must
        never appear is an actual import statement pulling it in."""
        src = inspect.getsource(cfg)
        import re

        assert not re.search(r"^\s*(import|from)\s+casestudy_flow_builder\b", src, re.MULTILINE), (
            "casestudy_flow_golden.py must not import the M2a.1 builder "
            "module -- it must remain an INDEPENDENT regression oracle"
        )

    def test_module_file_has_no_import_statement_for_builder(self):
        module_path = Path(cfg.__file__)
        for lineno, line in enumerate(module_path.read_text().splitlines(), start=1):
            stripped = line.strip()
            assert not (
                stripped.startswith("import casestudy_flow_builder")
                or stripped.startswith("from casestudy_flow_builder")
            ), f"line {lineno} imports the M2a.1 builder module: {line!r}"

    def test_module_has_no_import_time_subprocess_side_effects(self, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("importing casestudy_flow_golden must not spawn a subprocess")

        monkeypatch.setattr(subprocess, "run", boom)
        monkeypatch.setattr(subprocess, "Popen", boom)
        import importlib

        importlib.reload(cfg)  # must not raise


# =============================================================================
# Criterion 1 -- baseline_well_data: 238-background-well extraction, no
# doublet, sign preserved.
# =============================================================================
class _FakeListPackage:
    """Stand-in for a flopy list package (WEL/RIV): records via
    ``stress_period_data.get_data(0)``."""

    def __init__(self, records):
        self._records = records

    class _SPD:
        def __init__(self, records):
            self._records = records

        def get_data(self, per):
            return self._records if per == 0 else None

    @property
    def stress_period_data(self):
        return self._SPD(self._records)


# backward-compatible alias (older tests referenced _FakeWel)
_FakeWel = _FakeListPackage


class _FakeModelgrid:
    def __init__(self, xc, yc, cell_vertices=None):
        self.xcellcenters = np.asarray(xc) if xc is not None else None
        self.ycellcenters = np.asarray(yc) if yc is not None else None
        self._cell_vertices = cell_vertices or {}

    def get_cell_vertices(self, flat):
        return self._cell_vertices[int(flat)]


class _FakeGwf:
    """Minimal stand-in for a flopy ModflowGwf, just enough surface for
    baseline_well_data / near_field_and_zone_validation / apply_faithful_riv
    to work against."""

    def __init__(self, *, wel_records=None, riv_records=None, xc=None, yc=None,
                 idomain=None, packages=None, cell_vertices=None):
        self._wel_records = wel_records
        self._riv_records = riv_records
        self.modelgrid = _FakeModelgrid(xc, yc, cell_vertices)
        self._packages = packages or {}
        if idomain is not None:
            self._packages["DISV"] = SimpleNamespace(
                idomain=SimpleNamespace(array=np.asarray(idomain))
            )

    def get_package(self, name):
        if name == "WEL":
            if self._wel_records is None:
                return None
            return _FakeListPackage(self._wel_records)
        if name == "RIV":
            if self._riv_records is None:
                return None
            return _FakeListPackage(self._riv_records)
        return self._packages.get(name)


class TestBaselineWellData:
    def test_extracts_xy_rate_sign_preserved(self):
        xc = np.array([0.0, 10.0, 20.0])
        yc = np.array([0.0, 10.0, 20.0])
        records = [
            {"cellid": (0, 0), "q": 26.0},
            {"cellid": (0, 1), "q": -540.0},
            {"cellid": (0, 2), "q": 3.5},
        ]
        gwf = _FakeGwf(wel_records=records, xc=xc, yc=yc)
        wells = cfg.baseline_well_data(gwf)
        assert wells == [(0.0, 0.0, 26.0), (10.0, 10.0, -540.0), (20.0, 20.0, 3.5)]

    def test_no_wel_package_raises(self):
        gwf = _FakeGwf(wel_records=None, xc=[0.0], yc=[0.0])
        with pytest.raises(ValueError, match="WEL"):
            cfg.baseline_well_data(gwf)

    def test_empty_stress_period_data_raises(self):
        gwf = _FakeGwf(wel_records=[], xc=[0.0], yc=[0.0])
        with pytest.raises(ValueError):
            cfg.baseline_well_data(gwf)


# =============================================================================
# Criterion 2 -- canonicalize_wel_entries: deterministic duplicate-cellid
# aggregation.
# =============================================================================
class TestCanonicalizeWelEntries:
    def test_no_duplicates_sorted_unchanged_totals(self):
        cellid, rate = cfg.canonicalize_wel_entries([(0, 2), (0, 0)], [5.0, 7.0])
        assert cellid == [(0, 0), (0, 2)]
        assert rate == [7.0, 5.0]

    def test_duplicate_cellid_sums_rates(self):
        cellid, rate = cfg.canonicalize_wel_entries(
            [(0, 1), (0, 2), (0, 1)], [10.0, 5.0, -3.0]
        )
        assert cellid == [(0, 1), (0, 2)]
        assert rate == [7.0, 5.0]

    def test_empty_input_returns_empty(self):
        cellid, rate = cfg.canonicalize_wel_entries([], [])
        assert cellid == []
        assert rate == []

    def test_is_deterministic_regardless_of_input_order(self):
        a = cfg.canonicalize_wel_entries([(0, 1), (0, 0)], [1.0, 2.0])
        b = cfg.canonicalize_wel_entries([(0, 0), (0, 1)], [2.0, 1.0])
        assert a == b

    def test_sum_of_rates_conserved_across_aggregation(self):
        raw_cellid = [(0, 1), (0, 2), (0, 1), (0, 0)]
        raw_rate = [10.0, 5.0, -3.0, 2.0]
        cellid, rate = cfg.canonicalize_wel_entries(raw_cellid, raw_rate)
        assert sum(rate) == pytest.approx(sum(raw_rate))
        assert len(cellid) <= len(raw_cellid)


# =============================================================================
# Criterion 3 -- WEL flux conservation + presence checks.
# =============================================================================
class TestWelConservationChecks:
    def test_assert_wel_rate_conserved_passes_within_tol(self):
        coarse = [(0.0, 0.0, 10.0), (1.0, 1.0, -4.0), (2.0, 2.0, 1.0)]
        cfg.assert_wel_rate_conserved(coarse, [7.0])  # 10 - 4 + 1 = 7

    def test_assert_wel_rate_conserved_raises_on_mismatch(self):
        coarse = [(0.0, 0.0, 10.0), (1.0, 1.0, -4.0)]
        with pytest.raises(ValueError, match="conservation"):
            cfg.assert_wel_rate_conserved(coarse, [999.0])

    def test_check_background_wells_present_passes(self):
        cfg.check_background_wells_present_canonical([(0, 1), (0, 2)], expected_input_count=238)

    def test_check_background_wells_present_raises_on_empty(self):
        with pytest.raises(ValueError, match="zero"):
            cfg.check_background_wells_present_canonical([], expected_input_count=238)

    def test_check_background_wells_present_raises_when_more_than_expected(self):
        with pytest.raises(ValueError, match="more"):
            cfg.check_background_wells_present_canonical(
                [(0, i) for i in range(5)], expected_input_count=3,
            )


# =============================================================================
# Criterion 4 -- validate_no_dry_cells.
# =============================================================================
class TestValidateNoDryCells:
    def test_passes_when_all_heads_above_botm(self):
        assert cfg.validate_no_dry_cells([1.0, 2.0, 3.0], [0.0, 0.0, 0.0]) == 0

    def test_raises_naming_count_when_cells_dry(self):
        with pytest.raises(ValueError, match="2 dry"):
            cfg.validate_no_dry_cells([1.0, -1.0, -5.0], [0.0, 0.0, 0.0])

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            cfg.validate_no_dry_cells([1.0, 2.0], [0.0, 0.0, 0.0])


# =============================================================================
# Criterion 5 -- near-field + coarse-head agreement (pure numeric functions).
# =============================================================================
class TestNearFieldHeadDeltas:
    def test_nearest_neighbour_sampling(self):
        coarse_xy = np.array([[0.0, 0.0], [100.0, 0.0]])
        coarse_heads = np.array([10.0, 20.0])
        refined_xy = np.array([[1.0, 0.0], [99.0, 0.0]])
        refined_heads = np.array([10.5, 19.0])
        delta = cfg.near_field_head_deltas(coarse_xy, coarse_heads, refined_xy, refined_heads)
        assert delta == pytest.approx([0.5, -1.0])


class TestValidateNearFieldAgreement:
    """Robust gates: un-refined RMS + p99 + documented-outlier cap (NOT raw
    max); corridor RMS + max. Requires refined_xy + riv_dist for the
    outlier list."""

    @staticmethod
    def _xy(n):
        return np.column_stack([np.arange(n, dtype=float), np.zeros(n)])

    @staticmethod
    def _rivd(n):
        return np.full(n, np.inf)

    def _validate(self, delta, cellsize, **kw):
        n = len(delta)
        return cfg.validate_near_field_agreement(
            np.asarray(delta, float), np.asarray(cellsize, float),
            refined_xy=self._xy(n), riv_dist=self._rivd(n), **kw,
        )

    def test_passes_and_reports_observed_stats(self):
        delta = np.array([0.01, 0.02, 0.05])  # cell0/1 un-refined, cell2 corridor
        cellsize = np.array([50.0, 50.0, 10.0])
        report = self._validate(delta, cellsize)
        assert report["unrefined_max_m"] == pytest.approx(0.02)
        assert report["unrefined_rms_m"] == pytest.approx(np.sqrt((0.01**2 + 0.02**2) / 2))
        assert "unrefined_p99_m" in report
        assert report["corridor_max_m"] == pytest.approx(0.05)
        assert report["n_unrefined_outliers"] == 0
        assert report["unrefined_outliers"] == []

    def test_raw_unrefined_max_is_reported_not_gated(self):
        # A single large un-refined outlier: RMS/p99 stay tiny and the count
        # is within the cap -> PASS, with the raw max REPORTED (not gated).
        delta = np.concatenate([np.full(400, 0.01), [1.26]])
        cellsize = np.full(401, 50.0)
        report = self._validate(delta, cellsize)
        assert report["unrefined_max_m"] == pytest.approx(1.26)
        assert report["n_unrefined_outliers"] == 1  # the 1.26 cell, documented

    def test_raises_on_unrefined_rms_violation(self):
        delta = np.full(50, 0.09)  # RMS 0.09 > 0.08
        cellsize = np.full(50, 50.0)
        with pytest.raises(ValueError, match="(?i)un-refined RMS"):
            self._validate(delta, cellsize)

    def test_raises_on_unrefined_p99_violation(self):
        # RMS kept under 0.08 but the 99th percentile exceeds 0.25.
        delta = np.concatenate([np.zeros(90), np.full(10, 0.30)])
        cellsize = np.full(100, 50.0)
        # RMS = sqrt(10*0.09/100)=0.0949 -> would trip RMS first; shrink bulk
        delta = np.concatenate([np.zeros(980), np.full(20, 0.28)])
        cellsize = np.full(1000, 50.0)
        with pytest.raises(ValueError, match="(?i)p99"):
            self._validate(delta, cellsize)

    def test_raises_on_outlier_count_over_cap(self):
        # Many cells just above the 0.30 report threshold but each small
        # enough to keep RMS/p99 under their gates -> the CAP trips.
        n_out = int(cfg.NEAR_FIELD_TOL["unrefined_outlier_cap"]) + 5
        bulk = np.zeros(20000)
        outs = np.full(n_out, 0.31)
        delta = np.concatenate([bulk, outs])
        cellsize = np.full(len(delta), 50.0)
        with pytest.raises(ValueError, match="(?i)outlier"):
            self._validate(delta, cellsize)

    def test_raises_on_corridor_rms_violation(self):
        delta = np.full(10, 0.07)  # corridor RMS 0.07 > 0.06
        cellsize = np.full(10, 10.0)
        with pytest.raises(ValueError, match="(?i)corridor RMS"):
            self._validate(delta, cellsize)

    def test_raises_on_corridor_max_violation(self):
        # corridor: 200 cells at 0 + one at 0.60 -> RMS ~0.042 <= 0.06 (so the
        # corridor-RMS gate passes) but max 0.60 > 0.55 -> corridor-max trips.
        delta = np.concatenate([np.zeros(200), [0.60]])
        cellsize = np.full(201, 10.0)
        with pytest.raises(ValueError, match="(?i)corridor max"):
            self._validate(delta, cellsize)

    def test_outlier_entries_carry_cell_coords_delta_and_riv_dist(self):
        # one un-refined outlier at 0.5 among 200 zeros -> RMS/p99 tiny (pass),
        # the outlier is documented with full metadata.
        delta = np.concatenate([[0.5], np.zeros(200)])
        cellsize = np.full(201, 50.0)
        xy = np.zeros((201, 2))
        xy[0] = (30.0, 40.0)
        rivd = np.full(201, np.inf)
        rivd[0] = 111.0
        report = cfg.validate_near_field_agreement(
            delta, cellsize, refined_xy=xy, riv_dist=rivd,
        )
        assert report["n_unrefined_outliers"] == 1
        o = report["unrefined_outliers"][0]
        assert o["cell"] == 0 and o["delta_m"] == pytest.approx(0.5)
        assert o["x"] == 30.0 and o["y"] == 40.0 and o["dist_to_riv_m"] == pytest.approx(111.0)

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            cfg.validate_near_field_agreement(
                np.array([0.0, 0.0]), np.array([50.0]),
                refined_xy=self._xy(2), riv_dist=self._rivd(2),
            )


class TestNearFieldTolIsSingleSourceOfTruth:
    """Fail-fast-on-change: the exact tolerance set is pinned here so a bound
    changed in the module without updating this test FAILS."""

    def test_exact_tolerance_values(self):
        assert cfg.NEAR_FIELD_TOL == {
            "unrefined_rms_m": 0.08,
            "unrefined_p99_m": 0.25,
            "corridor_rms_m": 0.06,
            "corridor_max_m": 0.55,
            "unrefined_outlier_report_threshold_m": 0.30,
            "unrefined_outlier_cap": 25,
        }

    def test_clean_group0_observed_values_are_within_gates(self):
        # The observed clean faithful group-0 run (documented in the module)
        # must sit inside every gate -- a guard that the bar was set from the
        # real run, not arbitrarily.
        observed = {"unrefined_rms": 0.0557, "unrefined_p99": 0.1698,
                    "corridor_rms": 0.0392, "corridor_max": 0.3850, "n_outliers": 19}
        t = cfg.NEAR_FIELD_TOL
        assert observed["unrefined_rms"] <= t["unrefined_rms_m"]
        assert observed["unrefined_p99"] <= t["unrefined_p99_m"]
        assert observed["corridor_rms"] <= t["corridor_rms_m"]
        assert observed["corridor_max"] <= t["corridor_max_m"]
        assert observed["n_outliers"] <= t["unrefined_outlier_cap"]


# =============================================================================
# Finding 2 -- NaN-fragility guards (a NaN must RAISE, never silently pass).
# =============================================================================
class TestNaNGuards:
    def _xy(self, n):
        return np.column_stack([np.arange(n, dtype=float), np.zeros(n)])

    def test_nan_head_raises_in_no_dry_cells(self):
        heads = np.array([5.0, np.nan, 7.0])
        botm = np.array([0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="(?i)non-finite|nan"):
            cfg.validate_no_dry_cells(heads, botm)

    def test_inf_head_raises_in_no_dry_cells(self):
        with pytest.raises(ValueError, match="(?i)non-finite"):
            cfg.validate_no_dry_cells(np.array([1.0, np.inf]), np.array([0.0, 0.0]))

    def test_nan_delta_raises_in_near_field(self):
        delta = np.array([0.01, np.nan])
        cellsize = np.array([50.0, 50.0])
        with pytest.raises(ValueError, match="(?i)non-finite|nan"):
            cfg.validate_near_field_agreement(
                delta, cellsize, refined_xy=self._xy(2), riv_dist=np.full(2, np.inf),
            )

    def test_nan_cond_raises_in_conductance_conserved(self):
        with pytest.raises(ValueError, match="(?i)non-finite|nan"):
            cfg.validate_riv_conductance_conserved([10.0, np.nan], 50.0)

    def test_nan_coarse_cond_raises(self):
        with pytest.raises(ValueError, match="(?i)non-finite|nan"):
            cfg.validate_riv_conductance_conserved([10.0, 20.0], float("nan"))

    def test_nan_wel_rate_raises(self):
        coarse = [(0.0, 0.0, 10.0)]
        with pytest.raises(ValueError, match="(?i)non-finite|nan"):
            cfg.assert_wel_rate_conserved(coarse, [np.nan])

    def test_assert_json_finite_raises_on_nested_nan(self):
        with pytest.raises(ValueError, match="(?i)non-finite"):
            cfg._assert_json_finite({"a": [1, 2, {"b": float("nan")}]})

    def test_assert_json_finite_raises_on_inf(self):
        with pytest.raises(ValueError, match="(?i)non-finite"):
            cfg._assert_json_finite({"flux": float("inf")})

    def test_assert_json_finite_passes_clean(self):
        cfg._assert_json_finite({"a": 1, "b": 2.5, "c": [0.0, 1.0], "d": "s", "e": None, "f": True})


# =============================================================================
# Criterion 6 -- package-construction validators (incl. geometry intersection).
# =============================================================================
class TestPackageConstructionChecks:
    def test_check_active_mask_passes(self):
        cfg.check_active_mask(np.ones(5, dtype=int))

    def test_check_active_mask_raises_on_inactive_cell(self):
        with pytest.raises(ValueError, match="inactive"):
            cfg.check_active_mask(np.array([1, 1, 0]))

    def test_check_npf_k_passes(self):
        cfg.check_npf_k(np.array([1.0, 10.0, 100.0]))

    @pytest.mark.parametrize("bad", [
        np.array([1.0, np.nan, 5.0]),
        np.array([1.0, -1.0, 5.0]),
        np.array([1.0, 0.0, 5.0]),
    ])
    def test_check_npf_k_raises_on_bad_values(self, bad):
        with pytest.raises(ValueError):
            cfg.check_npf_k(bad)

    def test_check_rcha_conservation_passes_within_tol(self):
        # coarse: 2 x 2500 m^2 @ 1e-4 -> total area 5000 m^2, total flux 0.5
        # refined: 8 x 625 m^2 @ 1e-4 -> total area 5000 m^2, total flux 0.5
        c_total, r_total = cfg.check_rcha_conservation(
            coarse_rch=[1e-4, 1e-4], coarse_areas=[2500.0, 2500.0],
            refined_rch=[1e-4] * 8, refined_areas=[625.0] * 8,
        )
        assert c_total == pytest.approx(r_total)

    def test_check_rcha_conservation_raises_on_violation(self):
        with pytest.raises(ValueError, match="not conserved"):
            cfg.check_rcha_conservation(
                coarse_rch=[1e-4], coarse_areas=[2500.0],
                refined_rch=[1e-4], refined_areas=[10.0],  # way under
            )

    def test_check_rcha_conservation_zero_coarse_total_edge_case(self):
        cfg.check_rcha_conservation(
            coarse_rch=[0.0], coarse_areas=[2500.0],
            refined_rch=[0.0], refined_areas=[625.0],
        )
        with pytest.raises(ValueError):
            cfg.check_rcha_conservation(
                coarse_rch=[0.0], coarse_areas=[2500.0],
                refined_rch=[1.0], refined_areas=[625.0],
            )

    def test_check_riv_present_raises_on_empty(self):
        with pytest.raises(ValueError, match="RIV"):
            cfg.check_riv_present([], [])

    def test_check_riv_present_raises_on_nonpositive_conductance(self):
        with pytest.raises(ValueError, match="conductance"):
            cfg.check_riv_present([(0, 1)], [0.0])

    def test_check_chd_present_raises_on_empty(self):
        with pytest.raises(ValueError, match="CHD"):
            cfg.check_chd_present([])

    def test_check_riv_intersects_river_geometry(self):
        from shapely.geometry import box

        # cell polygons: 0 = [0,10]x[0,10], 1 = [10,20]x[0,10], 2 = [30,40]x[0,10]
        cell_polys = {
            0: [(0, 0), (10, 0), (10, 10), (0, 10)],
            1: [(10, 0), (20, 0), (20, 10), (10, 10)],
            2: [(30, 0), (40, 0), (40, 10), (30, 10)],
        }
        modelgrid = SimpleNamespace(get_cell_vertices=lambda i: cell_polys[int(i)])
        river = box(0, 0, 15, 10)  # overlaps cells 0 and 1, not cell 2
        cfg.check_riv_intersects_river_geometry([(0, 0), (0, 1)], modelgrid, river)
        with pytest.raises(ValueError, match="RIV"):
            cfg.check_riv_intersects_river_geometry([(0, 2)], modelgrid, river)

    def test_check_chd_near_boundary(self):
        import geopandas as gpd
        from shapely.geometry import Polygon

        boundary = gpd.GeoDataFrame(
            geometry=[Polygon([(0, 0), (200, 0), (200, 100), (0, 100)])], crs=None,
        )
        modelgrid = SimpleNamespace(
            xcellcenters=np.array([0.5, 100.0]),
            ycellcenters=np.array([0.5, 50.0]),
        )
        # cell 0 is right on the boundary corner; cell 1 is deep in the interior.
        cfg.check_chd_near_boundary([(0, 0)], modelgrid, boundary, max_dist_m=5.0)
        with pytest.raises(ValueError, match="CHD"):
            cfg.check_chd_near_boundary([(0, 1)], modelgrid, boundary, max_dist_m=5.0)


# =============================================================================
# Criterion 7 -- mass balance validator (format_budget_summary is patched;
# this module never runs a real MF6 budget read in the local suite).
# =============================================================================
class TestValidateMassBalance:
    def _fake_gwf(self):
        return object()  # opaque; format_budget_summary is monkeypatched below

    def _df_with_pct(self, pct):
        df = pd.DataFrame(
            {"Inflow (m3/d)": ["-"], "Outflow (m3/d)": ["-"], "Net (m3/d)": [pct]},
            index=["PERCENT ERROR"],
        )
        return df

    def test_passes_below_tol(self, monkeypatch):
        monkeypatch.setattr(cfg.mio, "format_budget_summary", lambda gwf: self._df_with_pct(0.05))
        pct = cfg.validate_mass_balance(self._fake_gwf())
        assert pct == pytest.approx(0.05)

    def test_raises_at_or_above_tol(self, monkeypatch):
        monkeypatch.setattr(cfg.mio, "format_budget_summary", lambda gwf: self._df_with_pct(1.5))
        with pytest.raises(ValueError, match="mass balance"):
            cfg.validate_mass_balance(self._fake_gwf())

    def test_negative_percent_error_uses_absolute_value(self, monkeypatch):
        monkeypatch.setattr(cfg.mio, "format_budget_summary", lambda gwf: self._df_with_pct(-2.0))
        with pytest.raises(ValueError):
            cfg.validate_mass_balance(self._fake_gwf())


# =============================================================================
# Criterion 8 -- manifest schema / canonical-hash stability / tol-recorded /
# load_flow_spec round-trip / tamper->mismatch / head-stat sanity / WEL
# Sigma-conservation / no-doublet / steady-nlay1-no-STO.
#
# These freeze a hand-built (canonical) spec + caller_fields SHAPED exactly
# like ``generate_group0_golden`` produces, without requiring a real MF6
# solve or Triangle refinement -- the generator's OWN orchestration wiring
# is covered separately (TestGenerateGroup0GoldenEndToEnd, below).
# =============================================================================
def _golden_caller_fields(heads, **overrides):
    fields = {
        "group": 0,
        "doublet": False,
        "background_wells": 2,
        "steady": True,
        "nlay": 1,
        "radius_used": 70.0,
        "node": "test-node",
        "versions": {"python": "3.12.0", "flopy": "3.9.2", "numpy": "2.0", "geos": "3.12", "mf6": "6.7.0"},
        "mass_balance_pct_error": 0.01,
        "provisional": True,
        "authoritative_platform": "linux",
        "provisional_reason": "macOS-provisional; re-verify on Linux at M2a.5",
        "near_field_tol": dict(cfg.NEAR_FIELD_TOL),
        "near_field_report": {
            "unrefined_rms_m": 0.0557, "unrefined_p99_m": 0.1698, "unrefined_max_m": 1.2586,
            "corridor_rms_m": 0.0392, "corridor_max_m": 0.3850,
            "n_unrefined_outliers": 19, "unrefined_outliers": [],
        },
        "heads": [float(h) for h in np.asarray(heads).reshape(-1)],
    }
    fields.update(overrides)
    return fields


class TestFreezeManifestSchema:
    def test_manifest_records_named_tolerances(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        manifest = mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        assert manifest["near_field_tol"] == {
            "unrefined_rms_m": 0.08, "unrefined_p99_m": 0.25,
            "corridor_rms_m": 0.06, "corridor_max_m": 0.55,
            "unrefined_outlier_report_threshold_m": 0.30, "unrefined_outlier_cap": 25,
        }

    def test_manifest_records_observed_near_field_stats(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        manifest = mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        rep = manifest["near_field_report"]
        for key in ("unrefined_rms_m", "unrefined_p99_m", "unrefined_max_m",
                    "corridor_rms_m", "corridor_max_m", "n_unrefined_outliers"):
            assert key in rep, f"manifest near_field_report must record {key!r}"

    def test_manifest_records_provisional_macos_flags(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        manifest = mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        assert manifest["provisional"] is True
        assert manifest["authoritative_platform"] == "linux"
        assert isinstance(manifest["provisional_reason"], str) and manifest["provisional_reason"]

    def test_manifest_records_group_doublet_background_wells_steady_nlay(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        manifest = mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        assert manifest["group"] == 0
        assert manifest["doublet"] is False
        assert manifest["background_wells"] == 2
        assert manifest["steady"] is True
        assert manifest["nlay"] == 1

    def test_manifest_is_strict_json(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        man_path = npz.with_suffix("").with_suffix(".manifest.json")
        # must be strictly valid JSON (no bare NaN/Infinity) and round-trip.
        data = json.loads(man_path.read_text())
        assert data["group"] == 0

    def test_canonical_hash_stable_across_repeated_freezes_of_identical_spec(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz_a = tmp_path / "a" / "group0_flow.npz"
        npz_b = tmp_path / "b" / "group0_flow.npz"
        man_a = mio.freeze_flow_spec(spec, npz_a, caller_fields=_golden_caller_fields(heads))
        man_b = mio.freeze_flow_spec(copy.deepcopy(spec), npz_b, caller_fields=_golden_caller_fields(heads))
        assert man_a["aggregate_hash"] == man_b["aggregate_hash"]

    def test_canonical_hash_excludes_solved_heads(self, tmp_path):
        """The PRIMARY oracle (package/spec hashes) must be identical whether
        the (SECONDARY) heads caller field differs -- heads never enter the
        .npz array members that are hashed."""
        spec = make_spec()
        npz_a = tmp_path / "a" / "group0_flow.npz"
        npz_b = tmp_path / "b" / "group0_flow.npz"
        man_a = mio.freeze_flow_spec(
            spec, npz_a, caller_fields=_golden_caller_fields([1.0, 2.0, 3.0]),
        )
        man_b = mio.freeze_flow_spec(
            copy.deepcopy(spec), npz_b, caller_fields=_golden_caller_fields([99.0, 88.0, 77.0]),
        )
        assert man_a["aggregate_hash"] == man_b["aggregate_hash"], (
            "changing ONLY the solved-heads caller field must not change the "
            "canonical package-hash (PRIMARY oracle)"
        )

    def test_canonical_hash_changes_when_a_package_array_changes(self, tmp_path):
        spec_a = make_spec()
        spec_b = make_spec(k=np.array([7.5, 3.25, 999.0]))
        heads = make_heads()
        npz_a = tmp_path / "a" / "group0_flow.npz"
        npz_b = tmp_path / "b" / "group0_flow.npz"
        man_a = mio.freeze_flow_spec(spec_a, npz_a, caller_fields=_golden_caller_fields(heads))
        man_b = mio.freeze_flow_spec(spec_b, npz_b, caller_fields=_golden_caller_fields(heads))
        assert man_a["aggregate_hash"] != man_b["aggregate_hash"]

    def test_load_flow_spec_round_trip_arrays(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        reloaded = mio.load_flow_spec(npz)
        assert np.array_equal(np.asarray(reloaded["k"]), np.asarray(spec["k"]))
        assert np.array_equal(np.asarray(reloaded["strt"]), np.asarray(spec["strt"]))

    def test_heads_round_trip_via_manifest_caller_field(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        manifest = mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        reloaded_heads = np.asarray(manifest["heads"], dtype=float)
        assert np.array_equal(reloaded_heads, np.asarray(heads, dtype=float))

    def test_tampered_npz_content_raises_on_load(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        # Tamper: rewrite one member's content, leaving the (now stale) manifest.
        with np.load(npz, allow_pickle=False) as z:
            members = {name: z[name] for name in z.files}
        key = next(k for k in members if members[k].size > 0)
        perturbed = np.array(members[key])
        perturbed.reshape(-1)[0] = perturbed.reshape(-1)[0] + 1
        members[key] = perturbed
        np.savez(npz, **members)
        with pytest.raises(ValueError):
            mio.load_flow_spec(npz)

    def test_head_stat_sanity_finite_within_botm_and_plausible_max(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        manifest = mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        h = np.asarray(manifest["heads"], dtype=float)
        assert np.all(np.isfinite(h))
        assert np.all(h >= np.asarray(spec["botm"], dtype=float))
        assert np.all(h <= np.asarray(spec["top"], dtype=float) + 50.0)  # generous plausibility band

    def test_wel_sigma_conservation_on_frozen_spec(self, tmp_path):
        spec = make_spec()  # wel_rate = [-30.0, 25.0] -> Sigma = -5.0
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        reloaded = mio.load_flow_spec(npz)
        assert sum(reloaded["wel_rate"]) == pytest.approx(-5.0)

    def test_baseline_has_background_wel_but_no_doublet(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        manifest = mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        reloaded = mio.load_flow_spec(npz)
        assert len(reloaded["wel_cellid"]) > 0, "baseline must retain background WEL cells"
        assert manifest["doublet"] is False

    def test_steady_nlay1_no_sto_asserted(self, tmp_path):
        spec = make_spec()
        heads = make_heads()
        npz = tmp_path / "group0_flow.npz"
        manifest = mio.freeze_flow_spec(spec, npz, caller_fields=_golden_caller_fields(heads))
        assert manifest["steady"] is True
        assert manifest["nlay"] == 1
        # botm is 1-D (ncpl,) -- a single layer, never (nlay>1, ncpl).
        reloaded = mio.load_flow_spec(npz)
        assert np.asarray(reloaded["botm"]).ndim == 1
        # the shared assembler this generator uses never builds an STO package.
        assert "ModflowGwfsto" not in inspect.getsource(mio.assemble_gwf_from_spec)
        assert "sto" not in {k.lower() for k in spec}


# =============================================================================
# Criterion 9 -- subprocess-isolated runner (NEW child entry point, mirrors
# jupyterhub_refine_reliability_gen.subprocess_refine_runner's contract).
# =============================================================================
def freeze_synthetic_spec(dest_dir: Path, name: str = "fake_spec.npz", **overrides) -> Path:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    npz = dest_dir / name
    mio.freeze_flow_spec(make_spec(**overrides), npz)
    return npz


class TestSubprocessRefineBaselineRunner:
    def test_child_flag_is_distinct_from_doublet_scripts_flag(self):
        assert cfg._CHILD_FLAG != rg._CHILD_FLAG

    def test_returns_spec_via_fake_npz_ipc(self, tmp_path, monkeypatch):
        npz = freeze_synthetic_spec(tmp_path / "fake", refine_radius_used=70.0)
        monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))
        spec, radius_used, retried = cfg.subprocess_refine_baseline_runner(
            0, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work",
        )
        assert int(spec["ncpl"]) == _NCPL
        assert float(radius_used) == 70.0
        assert retried is False

    def test_derives_retried_true_from_fallback_radius(self, tmp_path, monkeypatch):
        fallback_radius = rg.RETRY_RADII[1]
        npz = freeze_synthetic_spec(tmp_path / "fake", refine_radius_used=fallback_radius)
        monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))
        spec, radius_used, retried = cfg.subprocess_refine_baseline_runner(
            0, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work",
        )
        assert retried is True

    def test_surfaces_nonzero_exit_as_failure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(tmp_path / "does_not_exist.npz"))
        with pytest.raises((RuntimeError, subprocess.SubprocessError)):
            cfg.subprocess_refine_baseline_runner(
                0, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work",
            )

    def test_surfaces_signal_death_as_failure(self, tmp_path, monkeypatch):
        npz = freeze_synthetic_spec(tmp_path / "fake")
        monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))
        monkeypatch.setenv("AGM_FAKE_CHILD_SIGNAL", str(int(signal.SIGILL)))
        with pytest.raises((RuntimeError, subprocess.SubprocessError), match="(?i)sig"):
            cfg.subprocess_refine_baseline_runner(
                0, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work",
            )

    def test_actually_spawns_a_fresh_child(self, tmp_path, monkeypatch):
        npz = freeze_synthetic_spec(tmp_path / "fake", refine_radius_used=70.0)
        monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))
        calls = []
        real_popen = subprocess.Popen

        class SpyPopen(real_popen):
            def __init__(self, *a, **k):
                calls.append((a, k))
                super().__init__(*a, **k)

        monkeypatch.setattr(subprocess, "Popen", SpyPopen)
        cfg.subprocess_refine_baseline_runner(
            0, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work",
        )
        assert calls, "must spawn a real child process, not run in-process"

    def test_determinism_check_composes_with_our_runner(self, tmp_path, monkeypatch):
        """End-to-end through the shared (imported, not duplicated)
        run_group_determinism_check, driving OUR runner via the fake hook."""
        npz = freeze_synthetic_spec(tmp_path / "fake", refine_radius_used=rg.RETRY_RADII[0])
        monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))

        def runner(g):
            return cfg.subprocess_refine_baseline_runner(
                g, mother_model=tmp_path / "no_such_mother", work_dir=tmp_path / "work",
            )

        result = rg.run_group_determinism_check(0, runner, reruns=2)
        assert result["status"] == "PASS"


# =============================================================================
# Criterion 10 -- full generator orchestration, driven end-to-end via fakes
# (subprocess IPC hook for the refine step; stubbed flopy solve/output for
# assemble_gwf_from_spec; monkeypatched coarse-model/GIS loaders and
# format_budget_summary) -- proves the WIRING (determinism -> assemble ->
# validate -> freeze) is correct without any real MODFLOW/Triangle.
# =============================================================================
class TestGenerateGroup0GoldenEndToEnd:
    def _stub_solve(self, monkeypatch, heads):
        import flopy

        def fake_run(self, *a, **k):
            return True, []

        class _FakeHead:
            def get_data(self):
                return np.asarray(heads).reshape(1, 1, -1)

        class _FakeOutput:
            def head(self, *a, **k):
                return _FakeHead()

        monkeypatch.setattr(flopy.mf6.MFSimulation, "run_simulation", fake_run)
        monkeypatch.setattr(
            flopy.mf6.ModflowGwf, "output",
            property(lambda self: _FakeOutput()), raising=False,
        )

    def _stub_coarse_model_and_gis(self, monkeypatch, *, coarse_heads, wel_records):
        import geopandas as gpd
        from shapely.geometry import Polygon, box

        xc = np.array([3.0, 5.0, 15.0])
        yc = np.array([6.0, 5.0, 5.0])
        # ONE coarse RIV reach: its coarse cell polygon covers the whole
        # synthetic domain [0,20]x[0,10]; the river polygon (box(0,0,10,10))
        # clips it to the left half -> the faithful transfer places records on
        # the refined cells overlapping the river (the triangle cell 0 + quad
        # cell 1), with rbot=2 (>= refined botm 0, no overbank exclusion).
        riv_records = [{"cellid": (0, 0), "stage": 8.0, "cond": 50.0, "rbot": 2.0}]
        cell_vertices = {0: [(0, 0), (20, 0), (20, 10), (0, 10)]}
        cgwf = _FakeGwf(
            wel_records=wel_records, riv_records=riv_records,
            xc=xc, yc=yc, idomain=np.ones(_NCPL, dtype=int),
            cell_vertices=cell_vertices,
        )
        cgwf._packages["output_heads"] = coarse_heads

        class _FakeCoarseHead:
            def get_data(self_inner):
                return coarse_heads.reshape(1, 1, -1)

        class _FakeCoarseOutput:
            def head(self_inner):
                return _FakeCoarseHead()

        cgwf.output = _FakeCoarseOutput()

        boundary = gpd.GeoDataFrame(
            geometry=[Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])], crs=None,
        )
        river = gpd.GeoDataFrame(
            geometry=[box(0, 0, 10, 10)],
            data={"GEWAESSERNAME": ["Limmat"]},
            crs=None,
        )

        monkeypatch.setattr(cfg, "_load_coarse_model", lambda mother_model: (None, cgwf))
        monkeypatch.setattr(cfg, "_load_gis", lambda mother_model: (boundary, river))
        # RIV net flux comes from a real MF6 budget, which the stubbed solve
        # does not produce -- return a fixed (coarse==refined) value so the
        # flux-sanity check is exercised without a budget stub.
        monkeypatch.setattr(cfg, "riv_net_flux", lambda gwf: -10.0)
        return cgwf

    def test_happy_path_freezes_expected_manifest(self, tmp_path, monkeypatch):
        heads = make_heads()  # [8.2, 8.6, 9.1]; matches coarse -> zero near-field delta
        wel_records = [
            {"cellid": (0, 1), "q": -30.0},
            {"cellid": (0, 2), "q": 25.0},
        ]
        self._stub_coarse_model_and_gis(monkeypatch, coarse_heads=heads.copy(), wel_records=wel_records)
        self._stub_solve(monkeypatch, heads)
        monkeypatch.setattr(
            cfg.mio, "format_budget_summary",
            lambda gwf: pd.DataFrame(
                {"Inflow (m3/d)": ["-"], "Outflow (m3/d)": ["-"], "Net (m3/d)": [0.01]},
                index=["PERCENT ERROR"],
            ),
        )

        npz = freeze_synthetic_spec(tmp_path / "fake", refine_radius_used=rg.RETRY_RADII[0])
        monkeypatch.setenv("AGM_FAKE_SPEC_NPZ", str(npz))

        out_dir = tmp_path / "golden"
        manifest = cfg.generate_group0_golden(
            mother_model=tmp_path / "no_such_mother",
            work_dir=tmp_path / "work",
            out_dir=out_dir,
            reruns=2,
            group=0,
        )

        assert (out_dir / "group0_flow.npz").exists()
        assert (out_dir / "group0_flow.manifest.json").exists()
        assert manifest["group"] == 0
        assert manifest["doublet"] is False
        assert manifest["background_wells"] == 2
        assert manifest["steady"] is True
        assert manifest["nlay"] == 1
        assert manifest["near_field_tol"] == cfg.NEAR_FIELD_TOL
        assert np.array_equal(np.asarray(manifest["heads"]), heads)
        # provisional (macOS) freeze provenance
        assert manifest["provisional"] is True
        assert manifest["authoritative_platform"] == "linux"
        assert "linux" in manifest["provisional_reason"].lower()

        # faithful RIV provenance recorded + conservation held.
        fr = manifest["faithful_riv"]
        assert fr["primitive"] == "area"
        assert fr["coarse_cond"] == pytest.approx(50.0)
        assert fr["refined_cond"] == pytest.approx(50.0)
        assert isinstance(fr["hash"], str) and len(fr["hash"]) == 64
        assert fr["n_records"] >= 1
        assert "riv_net_flux_ratio" in fr
        # the frozen spec's RIV is the FAITHFUL set (Sigma cond conserved), not
        # the synthetic single-cell defective one.
        reloaded = mio.load_flow_spec(out_dir / "group0_flow.npz")
        assert sum(reloaded["riv_cond"]) == pytest.approx(50.0)

        # observed near-field stats are recorded (heads==coarse -> ~0 drift,
        # zero outliers) so the golden is self-describing.
        rep = manifest["near_field_report"]
        assert rep["unrefined_rms_m"] == pytest.approx(0.0, abs=1e-9)
        assert rep["unrefined_p99_m"] == pytest.approx(0.0, abs=1e-9)
        assert rep["n_unrefined_outliers"] == 0
        assert rep["unrefined_outliers"] == []
        for key in ("unrefined_max_m", "corridor_rms_m", "corridor_max_m"):
            assert key in rep

        # coverage invariant + overbank diagnostics recorded (Findings 3 & 4)
        assert fr["coverage_reaches_placed"] == fr["coverage_source_reaches"] == 1
        assert fr["min_retained_weight_ratio"] == pytest.approx(1.0)
        assert fr["n_reaches_below_warn_ratio"] == 0

    def test_determinism_failure_freezes_nothing(self, tmp_path, monkeypatch):
        """A runner that returns a DIFFERENT radius on rerun 2 must FAIL
        determinism and freeze nothing."""
        heads = make_heads()
        wel_records = [{"cellid": (0, 1), "q": -30.0}, {"cellid": (0, 2), "q": 25.0}]
        self._stub_coarse_model_and_gis(monkeypatch, coarse_heads=heads.copy(), wel_records=wel_records)
        self._stub_solve(monkeypatch, heads)

        npz_a = freeze_synthetic_spec(tmp_path / "fake_a", "a.npz", refine_radius_used=rg.RETRY_RADII[0])
        npz_b = freeze_synthetic_spec(tmp_path / "fake_b", "b.npz", refine_radius_used=rg.RETRY_RADII[1])

        calls = {"n": 0}

        def fake_runner(group, *, mother_model, work_dir, timeout_s=None):
            calls["n"] += 1
            npz = npz_a if calls["n"] == 1 else npz_b
            spec = mio.load_flow_spec(npz)
            radius = float(spec["refine_radius_used"])
            return spec, radius, rg._was_retried(radius)

        monkeypatch.setattr(cfg, "subprocess_refine_baseline_runner", fake_runner)

        out_dir = tmp_path / "golden"
        with pytest.raises(RuntimeError, match="determinism"):
            cfg.generate_group0_golden(
                mother_model=tmp_path / "no_such_mother",
                work_dir=tmp_path / "work",
                out_dir=out_dir,
                reruns=2,
                group=0,
            )
        assert not (out_dir / "group0_flow.npz").exists()


# =============================================================================
# Criterion 10b -- faithful RIV wiring (apply_faithful_riv + RIV validators).
# =============================================================================
def _fake_coarse_with_riv():
    """A fake coarse GWF exposing ONE RIV reach whose coarse cell polygon
    covers the synthetic domain; the river polygon clips it to the left half."""
    from shapely.geometry import box
    import geopandas as gpd

    riv_records = [{"cellid": (0, 0), "stage": 8.0, "cond": 50.0, "rbot": 2.0}]
    cell_vertices = {0: [(0, 0), (20, 0), (20, 10), (0, 10)]}
    cgwf = _FakeGwf(
        wel_records=[{"cellid": (0, 1), "q": -30.0}],
        riv_records=riv_records, xc=np.array([3.0, 5.0, 15.0]),
        yc=np.array([6.0, 5.0, 5.0]), idomain=np.ones(_NCPL, dtype=int),
        cell_vertices=cell_vertices,
    )
    river = gpd.GeoDataFrame(
        geometry=[box(0, 0, 10, 10)], data={"GEWAESSERNAME": ["Limmat"]}, crs="EPSG:2056",
    )
    return cgwf, river


class TestApplyFaithfulRiv:
    def test_replaces_riv_conserving_conductance(self):
        spec = make_spec()  # defective RIV: 1 cell, cond 50
        cgwf, river = _fake_coarse_with_riv()
        new, info = cfg.apply_faithful_riv(spec, cgwf, river)
        # RIV replaced with the faithful set; Sigma cond conserved exactly.
        assert info["coarse_cond"] == pytest.approx(50.0)
        assert info["refined_cond"] == pytest.approx(50.0)
        assert sum(new["riv_cond"]) == pytest.approx(50.0)
        assert info["primitive"] == "area"
        assert len(info["hash"]) == 64
        # every faithful record satisfies rbot >= refined cell botm (overbank
        # filter guarantee) -- botm left UNCHANGED (no floor hack).
        botm = np.asarray(new["botm"], dtype=float)
        for (_l, j), _s, _c, rbot in info["records"]:
            assert rbot >= botm[int(j)]
        assert np.array_equal(np.asarray(new["botm"]), np.asarray(spec["botm"]))

    def test_original_spec_not_mutated(self):
        spec = make_spec()
        orig_riv = list(spec["riv_cellid"])
        cgwf, river = _fake_coarse_with_riv()
        cfg.apply_faithful_riv(spec, cgwf, river)
        assert spec["riv_cellid"] == orig_riv, "apply_faithful_riv must not mutate its input spec"

    def test_deterministic(self):
        spec = make_spec()
        cgwf, river = _fake_coarse_with_riv()
        a, ia = cfg.apply_faithful_riv(spec, cgwf, river)
        b, ib = cfg.apply_faithful_riv(spec, cgwf, river)
        assert ia["hash"] == ib["hash"]
        assert a["riv_cellid"] == b["riv_cellid"]

    def test_records_coverage_and_overbank_diagnostics(self):
        # Finding 3 + 4: info carries the coverage invariant (all coarse
        # reaches placed) and the overbank-concentration diagnostics.
        spec = make_spec()
        cgwf, river = _fake_coarse_with_riv()
        _new, info = cfg.apply_faithful_riv(spec, cgwf, river)
        assert info["coverage_reaches_placed"] == info["coverage_source_reaches"] == 1
        assert info["min_retained_weight_ratio"] == pytest.approx(1.0)
        assert info["reaches_below_warn_ratio"] == []


class TestRivValidators:
    def test_conductance_conserved_passes(self):
        cfg.validate_riv_conductance_conserved([10.0, 20.0, 20.0], 50.0)

    def test_conductance_not_conserved_raises(self):
        with pytest.raises(ValueError, match="(?i)conserv"):
            cfg.validate_riv_conductance_conserved([10.0, 20.0], 50.0)

    def test_flux_sanity_passes_close(self):
        cfg.validate_riv_flux_sanity(-6400.0, -6419.0)

    def test_flux_sanity_sign_flip_raises(self):
        with pytest.raises(ValueError, match="(?i)sign"):
            cfg.validate_riv_flux_sanity(+6400.0, -6419.0)

    def test_flux_sanity_gross_magnitude_raises(self):
        with pytest.raises(ValueError, match="(?i)grossly"):
            cfg.validate_riv_flux_sanity(-100.0, -6419.0)

    def test_flux_sanity_nonfinite_raises(self):
        with pytest.raises(ValueError, match="(?i)finite"):
            cfg.validate_riv_flux_sanity(float("nan"), -6419.0)


class TestRivGeometryIntersectPolygon:
    def test_cell_polygon_overlap_passes_even_if_centroid_outside(self):
        """The faithful RIV places conductance on any cell whose POLYGON
        overlaps the river; such a cell's centroid may sit just outside the
        river polygon. The check must use polygon overlap, not centroid-in."""
        from shapely.geometry import box
        from types import SimpleNamespace as NS

        # cell [0,10]x[0,10], centroid (5,5). River strip [0,2]x[0,10] overlaps
        # the cell polygon but does NOT contain the centroid (5,5).
        mg = NS(get_cell_vertices=lambda i: [(0, 0), (10, 0), (10, 10), (0, 10)])
        river = box(0, 0, 2, 10)
        assert not river.contains(__import__("shapely").geometry.Point(5, 5))
        cfg.check_riv_intersects_river_geometry([(0, 0)], mg, river)  # must NOT raise

    def test_non_overlapping_cell_raises(self):
        from shapely.geometry import box
        from types import SimpleNamespace as NS

        mg = NS(get_cell_vertices=lambda i: [(0, 0), (10, 0), (10, 10), (0, 10)])
        river = box(100, 100, 110, 110)
        with pytest.raises(ValueError, match="(?i)RIV"):
            cfg.check_riv_intersects_river_geometry([(0, 0)], mg, river)


# =============================================================================
# Criterion 11 -- CLI smoke test.
# =============================================================================
class TestCli:
    def test_cli_reports_error_and_exits_nonzero_on_failure(self, tmp_path, monkeypatch):
        def boom(**kwargs):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(cfg, "generate_group0_golden", boom)
        rv = cfg.main([
            "--group", "0", "--out-dir", str(tmp_path / "golden"),
            "--mother-model", str(tmp_path / "no_such_mother"),
        ])
        assert rv == 1

    def test_cli_exposes_group_and_reruns_flags(self):
        parser = cfg._build_arg_parser()
        args = parser.parse_args(["--group", "3", "--reruns", "7"])
        assert args.group == 3
        assert args.reruns == 7
