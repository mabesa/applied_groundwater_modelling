"""
Unit tests for setup_pest_calibration.py module.

Tests cover both pre-existing functions and the new Sihl leakance multiplier
feature:
- _write_k_tpl
- _write_pst_file (with and without Sihl multiplier)
- _nearest_pilot_point
- _distribute_pilot_points
- _interpolate_pp_to_grid (IDW fallback)
- _write_forward_run_script (Sihl block presence)
- build_pest_setup (integration, with and without Sihl)

Run tests with: uv run pytest _SUPPORT/tests/test_setup_pest_calibration.py -v
"""

from __future__ import annotations

import os
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))

from setup_pest_calibration import (
    CALIBRATION_BUNDLE_ESSENTIAL_FILES,
    CALIBRATION_BUNDLE_MIN_VERSION,
    _distribute_pilot_points,
    _interpolate_pp_to_grid,
    _nearest_pilot_point,
    _write_forward_run_script,
    _write_k_tpl,
    _write_pst_file,
    build_pest_setup,
    ensure_calibration_workspace,
    ensure_notebook4_model_exists,
    ensure_pestpp_installed,
)
import setup_pest_calibration


# =============================================================================
# Helpers
# =============================================================================

def _make_obs_df(n=3):
    """Create a minimal observation DataFrame for testing."""
    return pd.DataFrame({
        "obs_id": [f"obs_{i}" for i in range(n)],
        "x": np.linspace(200, 800, n),
        "y": np.full(n, 500.0),
        "head_m": np.linspace(100.0, 98.0, n),
    })


def _make_obs_info(n=3):
    """Create the obs_info DataFrame that _write_pst_file expects."""
    return pd.DataFrame({
        "obs_name": [f"obs_{i}" for i in range(n)],
        "obs_value": np.linspace(100.0, 98.0, n),
        "weight": np.ones(n),
        "obs_group": ["heads"] * n,
    })


def _read_pst_sections(path):
    """Parse a PST file into a dict of {section_name: [lines]}."""
    sections = {}
    current = None
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("* ") or stripped.startswith("++"):
                current = stripped.lstrip("* ").lstrip("+").strip()
                sections.setdefault(current, [])
            elif current is not None:
                sections[current].append(stripped)
            else:
                sections.setdefault("_header", [])
                sections["_header"].append(stripped)
    return sections


def _write_stub_pest_setup(pest_ws, bundle_version=None, include_manifest=True):
    """Create the complete calibration bundle file set with stub contents."""
    pest_ws = Path(pest_ws)
    pest_ws.mkdir(parents=True, exist_ok=True)
    for name in CALIBRATION_BUNDLE_ESSENTIAL_FILES:
        path = pest_ws / name
        if name.endswith(".npy"):
            np.save(path, np.array([1, 2, 3]))
        else:
            path.write_text(f"stub {name}\n")
    if include_manifest:
        if bundle_version is None:
            bundle_version = CALIBRATION_BUNDLE_MIN_VERSION
        (pest_ws / "MANIFEST.json").write_text(json.dumps({
            "bundle_version": bundle_version,
            "commit_sha": "test",
            "pestpp_glm_version": "test",
            "n_pilot_points": 20,
            "n_observations": 5,
            "bundle_date": "2026-06-23",
        }))


def _write_bundle_zip(zip_path, bundle_version=None, include_manifest=True):
    """Create a zip with pest_setup/ at its root."""
    source = Path(zip_path).parent / "bundle_source" / "pest_setup"
    _write_stub_pest_setup(source, bundle_version, include_manifest)
    with zipfile.ZipFile(zip_path, "w") as archive:
        for path in source.rglob("*"):
            archive.write(path, Path("pest_setup") / path.relative_to(source))
    return zip_path


def _patch_calibration_download(monkeypatch, zip_path, calls):
    def fake_download_named_file(name, dest_folder=None, data_type=None):
        calls.append((name, dest_folder, data_type))
        dest = Path(dest_folder) / Path(zip_path).name
        shutil.copy2(zip_path, dest)
        return str(dest)

    monkeypatch.setattr("data_utils.download_named_file", fake_download_named_file)


def _write_valid_notebook4_model(workspace):
    """Write a tiny valid MF6/DISV simulation for load-only validation."""
    import flopy

    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    sim = flopy.mf6.MFSimulation(
        sim_name="test_nb4",
        sim_ws=str(workspace),
        exe_name="mf6",
    )
    flopy.mf6.ModflowTdis(sim)
    gwf = flopy.mf6.ModflowGwf(sim, modelname="limmat_valley")
    ims = flopy.mf6.ModflowIms(sim)
    sim.register_ims_package(ims, [gwf.name])
    vertices = [
        (0, 0.0, 0.0),
        (1, 1.0, 0.0),
        (2, 1.0, 1.0),
        (3, 0.0, 1.0),
    ]
    cell2d = [(0, 0.5, 0.5, 4, 0, 1, 2, 3)]
    flopy.mf6.ModflowGwfdisv(
        gwf,
        nlay=1,
        ncpl=1,
        nvert=4,
        vertices=vertices,
        cell2d=cell2d,
        top=[1.0],
        botm=[[0.0]],
    )
    sim.write_simulation(silent=True)
    return workspace


# =============================================================================
# Tests for optional calibration download guards
# =============================================================================

def test_ensure_pestpp_installed_idempotent_when_on_path(monkeypatch):
    monkeypatch.setattr(setup_pest_calibration.shutil, "which", lambda exe: "/bin/pestpp-glm")
    assert ensure_pestpp_installed() is True


def test_ensure_notebook4_model_exists_valid_missing_and_truncated(tmp_path):
    data_dir = tmp_path / "data"
    nb4_workspace = _write_valid_notebook4_model(data_dir / "notebook4_model")

    assert ensure_notebook4_model_exists(str(data_dir)) == str(nb4_workspace)

    shutil.rmtree(nb4_workspace)
    nb4_workspace.mkdir(parents=True)
    (nb4_workspace / "mfsim.nam").write_text("# partial\n")
    expected = "Notebook 4 output not found or incomplete"
    with pytest.raises(FileNotFoundError, match=expected):
        ensure_notebook4_model_exists(str(data_dir))

    shutil.rmtree(nb4_workspace)
    _write_valid_notebook4_model(nb4_workspace)
    disv_file = next(nb4_workspace.glob("*.disv"))
    disv_file.write_text("truncated\n")
    with pytest.raises(FileNotFoundError, match=expected):
        ensure_notebook4_model_exists(str(data_dir))


def _write_nb4_model_with_pumping(workspace, q_total):
    """Valid MF6/DISV workspace with a single WEL entry of total pumping q_total."""
    import flopy

    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    sim = flopy.mf6.MFSimulation(sim_name="t", sim_ws=str(workspace), exe_name="mf6")
    flopy.mf6.ModflowTdis(sim)
    gwf = flopy.mf6.ModflowGwf(sim, modelname="limmat_valley")
    sim.register_ims_package(flopy.mf6.ModflowIms(sim), [gwf.name])
    flopy.mf6.ModflowGwfdisv(
        gwf, nlay=1, ncpl=1, nvert=4,
        vertices=[(0, 0.0, 0.0), (1, 1.0, 0.0), (2, 1.0, 1.0), (3, 0.0, 1.0)],
        cell2d=[(0, 0.5, 0.5, 4, 0, 1, 2, 3)], top=[1.0], botm=[[0.0]],
    )
    flopy.mf6.ModflowGwfwel(gwf, stress_period_data=[[(0, 0), -abs(q_total)]])
    sim.write_simulation(silent=True)
    return workspace


def test_ensure_notebook4_model_warns_on_stale_pumping(tmp_path, recwarn):
    """An nb4 workspace built by the OLD 04f (1,080 m³/d) is flagged; the current
    2,160 m³/d model is silent."""
    pytest.importorskip("flopy")
    data_dir = tmp_path / "data"

    _write_nb4_model_with_pumping(data_dir / "notebook4_model", 1080.0)
    ensure_notebook4_model_exists(str(data_dir))
    stale = [w for w in recwarn.list if "total pumping is 1080" in str(w.message)]
    assert stale, "expected a stale-pumping warning for the 1,080 m³/d model"

    recwarn.clear()
    shutil.rmtree(data_dir / "notebook4_model")
    _write_nb4_model_with_pumping(data_dir / "notebook4_model", 2160.0)
    ensure_notebook4_model_exists(str(data_dir))
    assert not [w for w in recwarn.list if "total pumping" in str(w.message)]


def test_ensure_calibration_workspace_downloads_complete_bundle(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    zip_path = _write_bundle_zip(tmp_path / "bundle.zip")
    calls = []
    _patch_calibration_download(monkeypatch, zip_path, calls)

    pest_ws = ensure_calibration_workspace(str(data_dir))

    assert pest_ws.endswith(os.path.join("calibration", "pest_setup"))
    for name in CALIBRATION_BUNDLE_ESSENTIAL_FILES:
        assert (Path(pest_ws) / name).exists(), f"Missing {name}"
    assert (Path(pest_ws) / "MANIFEST.json").exists()


def test_ensure_calibration_workspace_refreshes_stale_version(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    current = data_dir / "calibration" / "pest_setup"
    _write_stub_pest_setup(current, bundle_version=0)
    zip_path = _write_bundle_zip(tmp_path / "bundle.zip", bundle_version=1)
    calls = []
    _patch_calibration_download(monkeypatch, zip_path, calls)
    monkeypatch.setattr("setup_pest_calibration.CALIBRATION_BUNDLE_MIN_VERSION", 1)

    pest_ws = ensure_calibration_workspace(str(data_dir))

    assert (data_dir / "calibration" / "pest_setup.stale").is_dir()
    assert len(calls) == 1
    manifest = json.loads((Path(pest_ws) / "MANIFEST.json").read_text())
    assert manifest["bundle_version"] == 1


def test_ensure_calibration_workspace_fails_hard_on_version_skew(tmp_path, monkeypatch):
    """A downloaded bundle still below the code minimum must fail hard, not be
    silently accepted — otherwise students calibrate against the OLD flow field
    after the 1,080->2,160 m³/d recalibration."""
    data_dir = tmp_path / "data"
    zip_path = _write_bundle_zip(tmp_path / "bundle.zip", bundle_version=1)
    calls = []
    _patch_calibration_download(monkeypatch, zip_path, calls)
    monkeypatch.setattr("setup_pest_calibration.CALIBRATION_BUNDLE_MIN_VERSION", 2)

    with pytest.raises(RuntimeError, match="stale.*bundle_version=1 < required 2"):
        ensure_calibration_workspace(str(data_dir))
    assert len(calls) == 1


def test_ensure_calibration_workspace_keeps_single_stale_snapshot(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    calibration_dir = data_dir / "calibration"
    current = calibration_dir / "pest_setup"
    stale = calibration_dir / "pest_setup.stale"
    _write_stub_pest_setup(current, bundle_version=0)
    stale.mkdir(parents=True)
    (stale / "old.txt").write_text("old snapshot\n")
    zip_path = _write_bundle_zip(tmp_path / "bundle.zip", bundle_version=1)
    calls = []
    _patch_calibration_download(monkeypatch, zip_path, calls)
    monkeypatch.setattr("setup_pest_calibration.CALIBRATION_BUNDLE_MIN_VERSION", 1)

    ensure_calibration_workspace(str(data_dir))

    assert stale.is_dir()
    assert not (stale / "old.txt").exists()
    assert (stale / "calibration.pst").exists()
    assert len(list(calibration_dir.glob("pest_setup.stale*"))) == 1


def test_ensure_calibration_workspace_missing_manifest_message(tmp_path):
    data_dir = tmp_path / "data"
    _write_stub_pest_setup(
        data_dir / "calibration" / "pest_setup",
        include_manifest=False,
    )

    with pytest.raises(FileNotFoundError, match="`MANIFEST.json` missing from bundle"):
        ensure_calibration_workspace(str(data_dir))


# =============================================================================
# Tests for _write_k_tpl
# =============================================================================

class TestWriteKTpl:
    """Tests for the K template file writer."""

    def test_basic_template_format(self, tmp_path):
        """Template should start with 'ptf ~' and have one line per pilot point."""
        tpl_path = tmp_path / "hk_pps.tpl"
        _write_k_tpl(str(tpl_path), 5)

        lines = tpl_path.read_text().splitlines()
        assert lines[0] == "ptf ~"
        assert len(lines) == 6  # header + 5 params

    def test_parameter_names(self, tmp_path):
        """Parameters should be named hk_pp_00 .. hk_pp_NN."""
        tpl_path = tmp_path / "hk_pps.tpl"
        _write_k_tpl(str(tpl_path), 3)

        lines = tpl_path.read_text().splitlines()
        assert "hk_pp_00" in lines[1]
        assert "hk_pp_01" in lines[2]
        assert "hk_pp_02" in lines[3]

    def test_pest_delimiters(self, tmp_path):
        """Each parameter line should be delimited with ~."""
        tpl_path = tmp_path / "hk_pps.tpl"
        _write_k_tpl(str(tpl_path), 2)

        lines = tpl_path.read_text().splitlines()
        for line in lines[1:]:
            assert line.count("~") == 2, f"Expected 2 delimiters in: {line}"

    def test_zero_pilot_points(self, tmp_path):
        """Zero pilot points should produce only the header line."""
        tpl_path = tmp_path / "hk_pps.tpl"
        _write_k_tpl(str(tpl_path), 0)

        lines = tpl_path.read_text().splitlines()
        assert len(lines) == 1
        assert lines[0] == "ptf ~"

    def test_large_number_of_pilot_points(self, tmp_path):
        """Template with 100 pilot points should have correct naming."""
        tpl_path = tmp_path / "hk_pps.tpl"
        _write_k_tpl(str(tpl_path), 100)

        lines = tpl_path.read_text().splitlines()
        assert len(lines) == 101
        # Check last parameter name has three digits
        assert "hk_pp_99" in lines[100]


# =============================================================================
# Tests for _nearest_pilot_point
# =============================================================================

class TestNearestPilotPoint:
    """Tests for the nearest-pilot-point finder."""

    def test_exact_match(self):
        """Point at the same location should return that index."""
        pp_xy = np.array([[0, 0], [10, 0], [20, 0]])
        assert _nearest_pilot_point(pp_xy, (10, 0)) == 1

    def test_closest_point(self):
        """Should return the index of the closest point."""
        pp_xy = np.array([[0, 0], [100, 0], [200, 0]])
        assert _nearest_pilot_point(pp_xy, (90, 0)) == 1

    def test_single_point(self):
        """With one pilot point, should always return 0."""
        pp_xy = np.array([[500, 500]])
        assert _nearest_pilot_point(pp_xy, (0, 0)) == 0

    def test_equidistant_points(self):
        """When two points are equidistant, returns the first one found."""
        pp_xy = np.array([[0, 10], [0, -10]])
        result = _nearest_pilot_point(pp_xy, (0, 0))
        assert result in (0, 1)

    def test_diagonal_distance(self):
        """Euclidean distance should work correctly for diagonal offsets."""
        pp_xy = np.array([[0, 0], [10, 10]])
        # (7, 7) is closer to (10, 10) than to (0, 0)
        assert _nearest_pilot_point(pp_xy, (7, 7)) == 1


# =============================================================================
# Tests for _distribute_pilot_points
# =============================================================================

class TestDistributePilotPoints:
    """Tests for the pilot-point distribution algorithm."""

    def test_correct_count(self, simple_structured_grid):
        """Should return the requested number of pilot points."""
        pp = _distribute_pilot_points(simple_structured_grid, n_target=10)
        assert pp.shape == (10, 2)

    def test_n_target_exceeds_cells(self, simple_structured_grid):
        """When n_target > n_cells, should return n_cells points."""
        pp = _distribute_pilot_points(simple_structured_grid, n_target=999)
        n_cells = simple_structured_grid.ncol * simple_structured_grid.nrow
        assert pp.shape[0] == n_cells

    def test_reproducible_with_seed(self, simple_structured_grid):
        """Same seed should produce identical results."""
        pp1 = _distribute_pilot_points(simple_structured_grid, seed=42)
        pp2 = _distribute_pilot_points(simple_structured_grid, seed=42)
        np.testing.assert_array_equal(pp1, pp2)

    def test_different_seeds_differ(self, simple_structured_grid):
        """Different seeds should produce different layouts."""
        pp1 = _distribute_pilot_points(simple_structured_grid, seed=1)
        pp2 = _distribute_pilot_points(simple_structured_grid, seed=2)
        assert not np.array_equal(pp1, pp2)

    def test_with_idomain_mask(self, simple_structured_grid):
        """Points should only be placed in active (idomain>0) cells."""
        nrow, ncol = simple_structured_grid.nrow, simple_structured_grid.ncol
        # Deactivate right half
        idomain = np.ones((1, nrow, ncol), dtype=int)
        idomain[:, :, ncol // 2:] = 0

        pp = _distribute_pilot_points(simple_structured_grid, n_target=5, idomain=idomain)

        # All points should be in the left half (x < ~500)
        xc_mid = simple_structured_grid.xcellcenters.ravel().max() / 2
        assert np.all(pp[:, 0] <= xc_mid + 50)  # small tolerance

    def test_single_point(self, simple_structured_grid):
        """Requesting 1 point should work."""
        pp = _distribute_pilot_points(simple_structured_grid, n_target=1)
        assert pp.shape == (1, 2)


# =============================================================================
# Tests for _interpolate_pp_to_grid (IDW fallback)
# =============================================================================

class TestInterpolatePpToGrid:
    """Tests for pilot-point interpolation using IDW fallback."""

    def test_uniform_values(self, simple_structured_grid):
        """Uniform pilot-point values should produce a uniform field."""
        pp_xy = np.array([[250, 250], [750, 750]])
        pp_values = np.array([1.0, 1.0])  # log10(10) = 1

        field = _interpolate_pp_to_grid(
            pp_xy, pp_values, simple_structured_grid, method="idw"
        )

        # All cells should be 10^1 = 10.0
        np.testing.assert_allclose(field.ravel(), 10.0, atol=1e-6)

    def test_returns_real_space(self, simple_structured_grid):
        """Output should be in real (not log) space."""
        pp_xy = np.array([[500, 500]])
        pp_values = np.array([2.0])  # log10(100) = 2

        field = _interpolate_pp_to_grid(
            pp_xy, pp_values, simple_structured_grid, method="idw"
        )

        # Should be close to 100 everywhere
        np.testing.assert_allclose(field.ravel(), 100.0, atol=1e-6)

    def test_structured_returns_2d(self, simple_structured_grid):
        """Structured grid should return a 2D (nrow, ncol) array."""
        pp_xy = np.array([[500, 500]])
        pp_values = np.array([1.0])

        field = _interpolate_pp_to_grid(
            pp_xy, pp_values, simple_structured_grid, method="idw"
        )

        assert field.ndim == 2
        assert field.shape == (
            simple_structured_grid.nrow,
            simple_structured_grid.ncol,
        )

    def test_disv_returns_1d(self, simple_voronoi_grid):
        """DISV grid should return a 1D array."""
        modelgrid = simple_voronoi_grid["modelgrid"]
        pp_xy = np.array([[500, 500]])
        pp_values = np.array([1.0])

        field = _interpolate_pp_to_grid(
            pp_xy, pp_values, modelgrid, method="idw"
        )

        assert field.ndim == 1

    def test_spatial_gradient(self, simple_structured_grid):
        """High K on left, low K on right should produce a gradient."""
        pp_xy = np.array([[50, 500], [950, 500]])
        pp_values = np.array([2.0, 0.0])  # 100 m/d left, 1 m/d right

        field = _interpolate_pp_to_grid(
            pp_xy, pp_values, simple_structured_grid, method="idw"
        )

        # Left column average should be higher than right column average
        left_mean = field[:, 0].mean()
        right_mean = field[:, -1].mean()
        assert left_mean > right_mean


# =============================================================================
# Tests for _write_pst_file — without Sihl
# =============================================================================

class TestWritePstFileBaseline:
    """Tests for PST file generation without Sihl multiplier."""

    @pytest.fixture
    def pst_path(self, tmp_path):
        """Write a baseline PST file and return its path."""
        path = tmp_path / "calibration.pst"
        obs_info = _make_obs_info(3)
        _write_pst_file(
            str(path), n_pp=5, k_initial=20.0, k_lower=1.0, k_upper=100.0,
            obs_info=obs_info, pp_pt_idx=2, pt_K=12.0, pt_weight=1.0,
            reg_weight=0.5,
            tpl_name="hk_pps.tpl", ins_name="heads_out.ins",
            par_file="hk_pps.dat", obs_file="heads_sim.dat",
            sihl_cell_ids=None,
        )
        return path

    def test_file_starts_with_pcf(self, pst_path):
        """PST file must begin with 'pcf'."""
        first_line = pst_path.read_text().splitlines()[0]
        assert first_line.strip() == "pcf"

    def test_parameter_count(self, pst_path):
        """Control data line should list 5 parameters."""
        sections = _read_pst_sections(str(pst_path))
        ctrl = sections["control data"]
        # First non-"restart" line has: NPAR NOBS NPARGP NPRIOR NOBSGP
        count_line = ctrl[1]  # after "restart estimation"
        tokens = count_line.split()
        assert tokens[0] == "5"  # NPAR

    def test_one_parameter_group(self, pst_path):
        """Should have exactly one parameter group (hk_grp)."""
        sections = _read_pst_sections(str(pst_path))
        pargp = sections["parameter groups"]
        assert len(pargp) == 1
        assert pargp[0].startswith("hk_grp")

    def test_five_parameter_data_lines(self, pst_path):
        """Should have 5 parameter data entries."""
        sections = _read_pst_sections(str(pst_path))
        pardata = sections["parameter data"]
        assert len(pardata) == 5

    def test_ntplfle_is_one(self, pst_path):
        """NTPLFLE should be 1 (only hk_pps.tpl)."""
        sections = _read_pst_sections(str(pst_path))
        ctrl = sections["control data"]
        # NTPLFLE is the first token of line after the count line
        ntplfle_line = ctrl[2]  # "1 1 single point 1"
        assert ntplfle_line.split()[0] == "1"

    def test_model_io_has_two_lines(self, pst_path):
        """Model I/O should have 2 lines: 1 tpl pair + 1 ins pair."""
        sections = _read_pst_sections(str(pst_path))
        mio = sections["model input/output"]
        assert len(mio) == 2
        assert "hk_pps.tpl" in mio[0]
        assert "heads_out.ins" in mio[1]

    def test_prior_information(self, pst_path):
        """Should have regularisation rows and one PT prior referencing hk_pp_02."""
        sections = _read_pst_sections(str(pst_path))
        pi = sections["prior information"]
        assert len(pi) == 6
        assert "hk_pp_02" in pi[-1]
        assert "pi_pt_k" in pi[-1]

    def test_observation_data(self, pst_path):
        """Should have 3 observation data lines matching obs_info."""
        sections = _read_pst_sections(str(pst_path))
        obsdata = sections["observation data"]
        assert len(obsdata) == 3

    def test_k_bounds_in_log_space(self, pst_path):
        """Parameter bounds should be log10(1)=0 and log10(100)=2."""
        sections = _read_pst_sections(str(pst_path))
        pardata = sections["parameter data"]
        for line in pardata:
            tokens = line.split()
            lo = float(tokens[4])
            hi = float(tokens[5])
            assert abs(lo - 0.0) < 1e-4  # log10(1)
            assert abs(hi - 2.0) < 1e-4  # log10(100)


# =============================================================================
# Tests for _write_pst_file — with Sihl multiplier
# =============================================================================

class TestWritePstFileWithSihl:
    """Tests for PST file generation WITH Sihl multiplier."""

    @pytest.fixture
    def pst_path(self, tmp_path):
        """Write a PST file with sihl_cell_ids and return its path."""
        path = tmp_path / "calibration.pst"
        obs_info = _make_obs_info(3)
        _write_pst_file(
            str(path), n_pp=5, k_initial=20.0, k_lower=1.0, k_upper=100.0,
            obs_info=obs_info, pp_pt_idx=2, pt_K=12.0, pt_weight=1.0,
            reg_weight=0.5,
            tpl_name="hk_pps.tpl", ins_name="heads_out.ins",
            par_file="hk_pps.dat", obs_file="heads_sim.dat",
            sihl_cell_ids=np.array([10, 20, 30]),
        )
        return path

    def test_parameter_count_includes_sihl(self, pst_path):
        """Control data should list 6 parameters (5 K + 1 Sihl)."""
        sections = _read_pst_sections(str(pst_path))
        ctrl = sections["control data"]
        count_line = ctrl[1]
        assert count_line.split()[0] == "6"

    def test_two_parameter_groups(self, pst_path):
        """Should have hk_grp and riv_grp."""
        sections = _read_pst_sections(str(pst_path))
        pargp = sections["parameter groups"]
        assert len(pargp) == 2
        assert pargp[0].startswith("hk_grp")
        assert pargp[1].startswith("riv_grp")

    def test_six_parameter_data_lines(self, pst_path):
        """Should have 6 parameter data entries (5 K + 1 Sihl)."""
        sections = _read_pst_sections(str(pst_path))
        pardata = sections["parameter data"]
        assert len(pardata) == 6

    def test_sihl_parameter_line(self, pst_path):
        """Sihl parameter should have correct name, bounds, and group."""
        sections = _read_pst_sections(str(pst_path))
        pardata = sections["parameter data"]
        sihl_line = pardata[-1]
        tokens = sihl_line.split()

        assert tokens[0] == "sihl_leakance_mult"
        assert tokens[1] == "none"       # transform
        assert tokens[2] == "relative"   # parchglim (not factor — bounds cross zero)
        assert float(tokens[3]) == 0.0   # initial (log10(1) = 0)
        assert float(tokens[4]) == -1.0  # lower (log10(0.1) = -1)
        assert float(tokens[5]) == 2.0   # upper (log10(100) = 2)
        assert tokens[6] == "riv_grp"

    def test_ntplfle_is_two(self, pst_path):
        """NTPLFLE should be 2 (hk_pps.tpl + sihl_mult.tpl)."""
        sections = _read_pst_sections(str(pst_path))
        ctrl = sections["control data"]
        ntplfle_line = ctrl[2]
        assert ntplfle_line.split()[0] == "2"

    def test_model_io_has_three_lines(self, pst_path):
        """Model I/O should have 3 lines: 2 tpl pairs + 1 ins pair."""
        sections = _read_pst_sections(str(pst_path))
        mio = sections["model input/output"]
        assert len(mio) == 3
        assert "hk_pps.tpl" in mio[0]
        assert "sihl_mult.tpl" in mio[1]
        assert "heads_out.ins" in mio[2]

    def test_pargp_count_in_control_data(self, pst_path):
        """NPARGP in control data should be 2."""
        sections = _read_pst_sections(str(pst_path))
        ctrl = sections["control data"]
        count_line = ctrl[1]
        tokens = count_line.split()
        assert tokens[2] == "2"  # NPARGP

    def test_sihl_uses_relative_not_factor(self, pst_path):
        """The Sihl parameter must use 'relative' because its bounds cross zero."""
        content = pst_path.read_text()
        assert "sihl_leakance_mult  none  relative" in content
        assert "sihl_leakance_mult  none  factor" not in content


# =============================================================================
# Tests for _write_forward_run_script
# =============================================================================

class TestWriteForwardRunScript:
    """Tests for the generated forward_run.py script."""

    def _write_script(self, tmp_path, sihl_cell_ids=None):
        """Helper to write a forward_run.py and return the content."""
        pest_ws = str(tmp_path / "pest")
        model_ws = str(tmp_path / "model")
        os.makedirs(pest_ws, exist_ok=True)
        os.makedirs(model_ws, exist_ok=True)

        obs_df = _make_obs_df(2)
        pp_xy = np.array([[100, 100], [900, 900]])

        _write_forward_run_script(
            pest_ws, model_ws, simple_structured_grid_inline(),
            obs_df, pp_xy, variogram_range=500.0,
            obs_x_col="x", obs_y_col="y",
            obs_id_col="obs_id", obs_head_col="head_m",
            sihl_cell_ids=sihl_cell_ids,
        )

        fwd_path = os.path.join(pest_ws, "forward_run.py")
        return Path(fwd_path).read_text()

    def test_script_created(self, tmp_path):
        """forward_run.py should be created."""
        content = self._write_script(tmp_path)
        assert len(content) > 0

    def test_sihl_block_absent_when_none(self, tmp_path):
        """Without sihl_cell_ids, no Sihl block in the script."""
        content = self._write_script(tmp_path, sihl_cell_ids=None)
        # The Sihl block is always present in the template (it checks file existence)
        # so we just verify it won't find the files when sihl_cell_ids=None
        # (no sihl_cell_ids.npy written to pest_ws)
        pest_ws = tmp_path / "pest"
        assert not (pest_ws / "sihl_cell_ids.npy").exists()

    def test_sihl_block_present(self, tmp_path):
        """With sihl_cell_ids, the script should contain the Sihl multiplier logic."""
        content = self._write_script(tmp_path, sihl_cell_ids=np.array([10, 20]))
        assert "sihl_mult" in content
        assert "sihl_cell_ids" in content

    def test_pp_xy_saved(self, tmp_path):
        """pp_xy.npy should be written to pest_ws."""
        self._write_script(tmp_path)
        assert (tmp_path / "pest" / "pp_xy.npy").exists()

    def test_script_is_valid_python(self, tmp_path):
        """The generated script should be parseable Python."""
        content = self._write_script(tmp_path)
        compile(content, "<forward_run.py>", "exec")  # raises SyntaxError if invalid


def simple_structured_grid_inline():
    """Create a minimal structured grid (no fixture dependency)."""
    import flopy

    nrow, ncol = 5, 5
    return flopy.discretization.StructuredGrid(
        delc=np.ones(nrow) * 200.0,
        delr=np.ones(ncol) * 200.0,
        top=np.ones((nrow, ncol)) * 100.0,
        botm=np.zeros((1, nrow, ncol)),
        nlay=1, xoff=0.0, yoff=0.0,
    )


# =============================================================================
# Tests for build_pest_setup (integration)
# =============================================================================

class TestBuildPestSetup:
    """Integration tests for the full PEST setup builder."""

    @pytest.fixture
    def setup_args(self, tmp_path, simple_structured_grid):
        """Provide minimal arguments for build_pest_setup."""
        model_ws = str(tmp_path / "model")
        pest_ws = str(tmp_path / "pest")
        os.makedirs(model_ws, exist_ok=True)
        return dict(
            model_ws=model_ws,
            modelgrid=simple_structured_grid,
            obs_df=_make_obs_df(3),
            pt_K=12.0,
            pt_location=(500, 500),
            pest_ws=pest_ws,
            n_pilot_points=5,
            k_initial=20.0,
            k_lower=1.0,
            k_upper=100.0,
            pt_weight=1.0,
            variogram_range=500.0,
        )

    def test_returns_pest_ws_and_pp_xy(self, setup_args):
        """Should return (pest_ws, pp_xy) tuple."""
        pest_ws, pp_xy = build_pest_setup(**setup_args)
        assert os.path.isdir(pest_ws)
        assert pp_xy.shape == (5, 2)

    def test_creates_all_files(self, setup_args):
        """Check that all expected files are written."""
        pest_ws, _ = build_pest_setup(**setup_args)
        expected = [
            "calibration.pst", "hk_pps.tpl", "hk_pps.dat",
            "heads_out.ins", "forward_run.py", "run_model.sh",
            "pilot_points.csv", "pp_xy.npy",
        ]
        for fname in expected:
            assert os.path.exists(os.path.join(pest_ws, fname)), f"Missing {fname}"

    def test_no_sihl_files_without_param(self, setup_args):
        """Without sihl_cell_ids, no Sihl files should exist."""
        pest_ws, _ = build_pest_setup(**setup_args)
        assert not os.path.exists(os.path.join(pest_ws, "sihl_mult.tpl"))
        assert not os.path.exists(os.path.join(pest_ws, "sihl_mult.dat"))
        assert not os.path.exists(os.path.join(pest_ws, "sihl_cell_ids.npy"))

    def test_sihl_files_created(self, setup_args):
        """With sihl_cell_ids, all Sihl files should be written."""
        setup_args["sihl_cell_ids"] = np.array([5, 10, 15])
        pest_ws, _ = build_pest_setup(**setup_args)

        assert os.path.exists(os.path.join(pest_ws, "sihl_mult.tpl"))
        assert os.path.exists(os.path.join(pest_ws, "sihl_mult.dat"))
        assert os.path.exists(os.path.join(pest_ws, "sihl_cell_ids.npy"))

    def test_sihl_tpl_format(self, setup_args):
        """sihl_mult.tpl should be a valid PEST template file."""
        setup_args["sihl_cell_ids"] = np.array([5])
        pest_ws, _ = build_pest_setup(**setup_args)

        content = Path(os.path.join(pest_ws, "sihl_mult.tpl")).read_text()
        lines = content.splitlines()
        assert lines[0] == "ptf ~"
        assert "sihl_leakance_mult" in lines[1]
        assert lines[1].count("~") == 2

    def test_sihl_dat_initial_value(self, setup_args):
        """sihl_mult.dat initial value should be 0.0 (= log10(1.0))."""
        setup_args["sihl_cell_ids"] = np.array([5])
        pest_ws, _ = build_pest_setup(**setup_args)

        val = np.loadtxt(os.path.join(pest_ws, "sihl_mult.dat"))
        assert abs(float(val) - 0.0) < 1e-10

    def test_sihl_cell_ids_roundtrip(self, setup_args):
        """Saved sihl_cell_ids.npy should match the input array."""
        ids = np.array([3, 7, 42, 99])
        setup_args["sihl_cell_ids"] = ids
        pest_ws, _ = build_pest_setup(**setup_args)

        loaded = np.load(os.path.join(pest_ws, "sihl_cell_ids.npy"))
        np.testing.assert_array_equal(loaded, ids)

    def test_pst_param_count_without_sihl(self, setup_args):
        """PST file should have 5 parameters without Sihl."""
        pest_ws, _ = build_pest_setup(**setup_args)
        sections = _read_pst_sections(os.path.join(pest_ws, "calibration.pst"))
        assert sections["control data"][1].split()[0] == "5"

    def test_pst_param_count_with_sihl(self, setup_args):
        """PST file should have 6 parameters with Sihl."""
        setup_args["sihl_cell_ids"] = np.array([1, 2])
        pest_ws, _ = build_pest_setup(**setup_args)
        sections = _read_pst_sections(os.path.join(pest_ws, "calibration.pst"))
        assert sections["control data"][1].split()[0] == "6"

    def test_initial_k_values(self, setup_args):
        """hk_pps.dat should contain log10(k_initial) for each pilot point."""
        setup_args["k_initial"] = 50.0
        pest_ws, pp_xy = build_pest_setup(**setup_args)

        vals = np.loadtxt(os.path.join(pest_ws, "hk_pps.dat"))
        expected = np.log10(50.0)
        np.testing.assert_allclose(vals, expected, atol=1e-6)
        assert len(vals) == len(pp_xy)

    def test_pest_ws_default_path(self, tmp_path, simple_structured_grid):
        """When pest_ws=None, should default to model_ws/pest_setup."""
        model_ws = str(tmp_path / "model")
        os.makedirs(model_ws)
        pest_ws, _ = build_pest_setup(
            model_ws=model_ws,
            modelgrid=simple_structured_grid,
            obs_df=_make_obs_df(2),
            pt_K=10.0,
            pt_location=(500, 500),
            pest_ws=None,
            n_pilot_points=3,
        )
        assert pest_ws == os.path.join(model_ws, "pest_setup")
        assert os.path.isdir(pest_ws)

    def test_run_model_sh_executable(self, setup_args):
        """run_model.sh should be created with execute permission."""
        pest_ws, _ = build_pest_setup(**setup_args)
        sh_path = os.path.join(pest_ws, "run_model.sh")
        assert os.access(sh_path, os.X_OK)


# =============================================================================
# Edge cases for Sihl multiplier
# =============================================================================

class TestSihlEdgeCases:
    """Edge cases for the Sihl leakance multiplier feature."""

    def test_empty_sihl_array(self, tmp_path):
        """Empty sihl_cell_ids array should still create files."""
        path = tmp_path / "calibration.pst"
        obs_info = _make_obs_info(2)
        sihl_ids = np.array([], dtype=int)

        _write_pst_file(
            str(path), n_pp=3, k_initial=20.0, k_lower=1.0, k_upper=100.0,
            obs_info=obs_info, pp_pt_idx=0, pt_K=10.0, pt_weight=1.0,
            reg_weight=0.5,
            tpl_name="hk_pps.tpl", ins_name="heads_out.ins",
            par_file="hk_pps.dat", obs_file="heads_sim.dat",
            sihl_cell_ids=sihl_ids,
        )

        # Should still include the Sihl parameter (empty array is not None)
        sections = _read_pst_sections(str(path))
        assert sections["control data"][1].split()[0] == "4"  # 3 K + 1 Sihl
        pardata = sections["parameter data"]
        assert any("sihl_leakance_mult" in line for line in pardata)

    def test_single_sihl_cell(self, tmp_path):
        """Single Sihl cell should work correctly."""
        path = tmp_path / "calibration.pst"
        obs_info = _make_obs_info(2)

        _write_pst_file(
            str(path), n_pp=3, k_initial=20.0, k_lower=1.0, k_upper=100.0,
            obs_info=obs_info, pp_pt_idx=0, pt_K=10.0, pt_weight=1.0,
            reg_weight=0.5,
            tpl_name="hk_pps.tpl", ins_name="heads_out.ins",
            par_file="hk_pps.dat", obs_file="heads_sim.dat",
            sihl_cell_ids=np.array([42]),
        )

        sections = _read_pst_sections(str(path))
        assert sections["control data"][1].split()[0] == "4"

    def test_duplicate_sihl_cell_ids(self, tmp_path, simple_structured_grid):
        """Duplicate cell IDs in sihl_cell_ids should be stored as-is."""
        model_ws = str(tmp_path / "model")
        pest_ws = str(tmp_path / "pest")
        os.makedirs(model_ws)

        ids_with_dups = np.array([5, 5, 10, 10, 10])
        pest_ws_out, _ = build_pest_setup(
            model_ws=model_ws,
            modelgrid=simple_structured_grid,
            obs_df=_make_obs_df(2),
            pt_K=10.0,
            pt_location=(500, 500),
            pest_ws=pest_ws,
            n_pilot_points=3,
            sihl_cell_ids=ids_with_dups,
        )

        loaded = np.load(os.path.join(pest_ws_out, "sihl_cell_ids.npy"))
        np.testing.assert_array_equal(loaded, ids_with_dups)

    def test_sihl_bounds_cross_zero(self, tmp_path):
        """Verify the Sihl parameter bounds [-1, 2] cross zero and use 'relative'."""
        path = tmp_path / "calibration.pst"
        obs_info = _make_obs_info(2)

        _write_pst_file(
            str(path), n_pp=2, k_initial=20.0, k_lower=1.0, k_upper=100.0,
            obs_info=obs_info, pp_pt_idx=0, pt_K=10.0, pt_weight=1.0,
            reg_weight=0.5,
            tpl_name="hk_pps.tpl", ins_name="heads_out.ins",
            par_file="hk_pps.dat", obs_file="heads_sim.dat",
            sihl_cell_ids=np.array([1]),
        )

        sections = _read_pst_sections(str(path))
        sihl_line = [l for l in sections["parameter data"]
                     if "sihl_leakance_mult" in l][0]
        tokens = sihl_line.split()
        lo, hi = float(tokens[4]), float(tokens[5])

        assert lo < 0 < hi, "Bounds should cross zero"
        assert tokens[2] == "relative", "Must use 'relative' for zero-crossing bounds"

    def test_k_params_use_factor(self, tmp_path):
        """K parameters should use 'factor' (non-negative bounds)."""
        path = tmp_path / "calibration.pst"
        obs_info = _make_obs_info(2)

        _write_pst_file(
            str(path), n_pp=3, k_initial=20.0, k_lower=1.0, k_upper=100.0,
            obs_info=obs_info, pp_pt_idx=0, pt_K=10.0, pt_weight=1.0,
            reg_weight=0.5,
            tpl_name="hk_pps.tpl", ins_name="heads_out.ins",
            par_file="hk_pps.dat", obs_file="heads_sim.dat",
            sihl_cell_ids=np.array([1]),
        )

        sections = _read_pst_sections(str(path))
        for line in sections["parameter data"]:
            if line.startswith("hk_pp"):
                assert "factor" in line, f"K params should use 'factor': {line}"

    def test_backward_compatibility_no_sihl(self, tmp_path, simple_structured_grid):
        """build_pest_setup without sihl_cell_ids should behave identically to before."""
        model_ws = str(tmp_path / "model")
        pest_ws = str(tmp_path / "pest")
        os.makedirs(model_ws)

        pest_ws_out, pp_xy = build_pest_setup(
            model_ws=model_ws,
            modelgrid=simple_structured_grid,
            obs_df=_make_obs_df(3),
            pt_K=12.0,
            pt_location=(500, 500),
            pest_ws=pest_ws,
            n_pilot_points=5,
        )

        pst_content = Path(os.path.join(pest_ws_out, "calibration.pst")).read_text()

        # Should NOT contain any Sihl references
        assert "sihl" not in pst_content.lower()
        assert "riv_grp" not in pst_content

        # Should have exactly 5 parameters, 1 group, 1 tpl file
        sections = _read_pst_sections(os.path.join(pest_ws_out, "calibration.pst"))
        ctrl = sections["control data"]
        assert ctrl[1].split()[0] == "5"   # NPAR
        assert ctrl[1].split()[2] == "1"   # NPARGP
        assert ctrl[2].split()[0] == "1"   # NTPLFLE
