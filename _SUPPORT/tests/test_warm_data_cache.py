"""
Unit tests for warm_data_cache and format_cache_report in data_utils.py.

Tests cover:
- Successful download (new file → DOWNLOADED)
- Already-present file (CACHED)
- Unknown name isolation (FAILED, does not propagate)
- Mixed scenario: one raise, others succeed
- Report structure and counts
- format_cache_report output

Run with: uv run pytest _SUPPORT/tests/test_warm_data_cache.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path (mirrors the style in test_setup_pest_calibration.py)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import data_utils
from data_utils import (
    PREFETCH_GIS_FILES,
    format_cache_report,
    warm_data_cache,
)


# =============================================================================
# Helpers
# =============================================================================

def _make_fake_download(tmp_dir: Path, fake_size_bytes: int = 1024):
    """
    Return a monkeypatch replacement for data_utils.download_named_file.

    Creates an actual file (so os.path.getsize works) and records calls.
    """
    calls: list[tuple] = []

    def fake_download(name, dest_folder=None, data_type=None):
        calls.append((name, dest_folder, data_type))
        gis_subdir = tmp_dir / (data_type or "gis")
        gis_subdir.mkdir(parents=True, exist_ok=True)
        dest = gis_subdir / f"{name}.tif"
        dest.write_bytes(b"x" * fake_size_bytes)
        return str(dest)

    return fake_download, calls


def _make_fake_get_data_urls(names):
    """Return a fake get_data_urls that includes entries for the given names."""
    def fake_get_data_urls():
        return {n: {"filename": f"{n}.tif", "url": f"http://fake/{n}.tif"} for n in names}
    return fake_get_data_urls


# =============================================================================
# Tests: warm_data_cache report structure
# =============================================================================

class TestWarmDataCacheStructure:
    """Report dict has the expected keys and types."""

    def test_report_keys(self, monkeypatch, tmp_path):
        names = ["layer_a", "layer_b"]
        fake_dl, _ = _make_fake_download(tmp_path)
        monkeypatch.setattr(data_utils, "download_named_file", fake_dl)
        monkeypatch.setattr(data_utils, "get_data_urls", _make_fake_get_data_urls(names))

        report = warm_data_cache(gis_names=names, data_dir=str(tmp_path), verbose=False)

        assert "items" in report
        assert "counts" in report
        assert "total_mb" in report
        assert "ok" in report

    def test_counts_keys(self, monkeypatch, tmp_path):
        names = ["layer_a"]
        fake_dl, _ = _make_fake_download(tmp_path)
        monkeypatch.setattr(data_utils, "download_named_file", fake_dl)
        monkeypatch.setattr(data_utils, "get_data_urls", _make_fake_get_data_urls(names))

        report = warm_data_cache(gis_names=names, data_dir=str(tmp_path), verbose=False)

        for key in ("CACHED", "DOWNLOADED", "FAILED"):
            assert key in report["counts"], f"missing key: {key}"


# =============================================================================
# Tests: DOWNLOADED vs CACHED classification
# =============================================================================

class TestDownloadedVsCached:
    """First call → DOWNLOADED; second call (file already present) → CACHED."""

    def test_new_file_is_downloaded(self, monkeypatch, tmp_path):
        names = ["layer_a"]
        fake_dl, calls = _make_fake_download(tmp_path)
        monkeypatch.setattr(data_utils, "download_named_file", fake_dl)
        monkeypatch.setattr(data_utils, "get_data_urls", _make_fake_get_data_urls(names))

        report = warm_data_cache(gis_names=names, data_dir=str(tmp_path), verbose=False)

        assert report["counts"]["DOWNLOADED"] == 1
        assert report["counts"]["CACHED"] == 0
        assert report["counts"]["FAILED"] == 0
        assert report["ok"] is True

    def test_existing_file_is_cached(self, monkeypatch, tmp_path):
        names = ["layer_a"]
        # Pre-create the file so existed_before=True
        gis_dir = tmp_path / "gis"
        gis_dir.mkdir(parents=True)
        pre_file = gis_dir / "layer_a.tif"
        pre_file.write_bytes(b"x" * 2048)

        fake_dl, _ = _make_fake_download(tmp_path)
        monkeypatch.setattr(data_utils, "download_named_file", fake_dl)
        monkeypatch.setattr(data_utils, "get_data_urls", _make_fake_get_data_urls(names))

        report = warm_data_cache(gis_names=names, data_dir=str(tmp_path), verbose=False)

        assert report["counts"]["CACHED"] == 1
        assert report["counts"]["DOWNLOADED"] == 0
        assert report["ok"] is True


# =============================================================================
# Tests: failure isolation
# =============================================================================

class TestFailureIsolation:
    """One failing item must not abort the loop; ok=False; others proceed."""

    def test_unknown_name_is_failed(self, monkeypatch, tmp_path):
        """Name not in DATA_URLS → FAILED; does not raise."""
        good_names = ["layer_a", "layer_b"]
        all_names = ["not_a_real_layer"] + good_names

        fake_dl, _ = _make_fake_download(tmp_path)
        monkeypatch.setattr(data_utils, "download_named_file", fake_dl)
        # Only good names are in the URL catalog
        monkeypatch.setattr(data_utils, "get_data_urls", _make_fake_get_data_urls(good_names))

        report = warm_data_cache(gis_names=all_names, data_dir=str(tmp_path), verbose=False)

        assert report["counts"]["FAILED"] == 1
        assert report["counts"]["DOWNLOADED"] == 2
        assert report["ok"] is False

        failed_items = [i for i in report["items"] if i["status"] == "FAILED"]
        assert len(failed_items) == 1
        assert failed_items[0]["key"] == "not_a_real_layer"
        assert "not in DATA_URLS" in failed_items[0]["error"]

    def test_raising_download_is_isolated(self, monkeypatch, tmp_path):
        """download_named_file raising for one name must not stop others."""
        names = ["good_layer", "bad_layer", "another_good"]

        calls: list[str] = []

        def fake_dl_with_raise(name, dest_folder=None, data_type=None):
            calls.append(name)
            if name == "bad_layer":
                raise RuntimeError("simulated network failure")
            gis_subdir = tmp_path / (data_type or "gis")
            gis_subdir.mkdir(parents=True, exist_ok=True)
            dest = gis_subdir / f"{name}.tif"
            dest.write_bytes(b"y" * 512)
            return str(dest)

        monkeypatch.setattr(data_utils, "download_named_file", fake_dl_with_raise)
        monkeypatch.setattr(data_utils, "get_data_urls", _make_fake_get_data_urls(names))

        # Must not raise
        report = warm_data_cache(gis_names=names, data_dir=str(tmp_path), verbose=False)

        assert report["counts"]["FAILED"] == 1
        assert report["counts"]["DOWNLOADED"] == 2
        assert report["ok"] is False
        assert set(calls) == set(names), "loop must have called download for all names"

        failed = [i for i in report["items"] if i["status"] == "FAILED"]
        assert failed[0]["key"] == "bad_layer"
        assert "simulated network failure" in failed[0]["error"]

    def test_all_failed_is_not_ok(self, monkeypatch, tmp_path):
        """When every item fails, ok must be False."""
        names = ["x", "y"]
        monkeypatch.setattr(data_utils, "get_data_urls", lambda: {})  # empty catalog

        fake_dl, _ = _make_fake_download(tmp_path)
        monkeypatch.setattr(data_utils, "download_named_file", fake_dl)

        report = warm_data_cache(gis_names=names, data_dir=str(tmp_path), verbose=False)

        assert report["ok"] is False
        assert report["counts"]["FAILED"] == 2


# =============================================================================
# Tests: total_mb accounting
# =============================================================================

class TestTotalMb:
    """total_mb is the sum of sizes for CACHED + DOWNLOADED items only."""

    def test_total_mb_excludes_failed(self, monkeypatch, tmp_path):
        good_names = ["layer_a"]
        all_names = ["not_a_real_layer"] + good_names

        # 1 MB files
        fake_dl, _ = _make_fake_download(tmp_path, fake_size_bytes=1024 * 1024)
        monkeypatch.setattr(data_utils, "download_named_file", fake_dl)
        monkeypatch.setattr(data_utils, "get_data_urls", _make_fake_get_data_urls(good_names))

        report = warm_data_cache(gis_names=all_names, data_dir=str(tmp_path), verbose=False)

        # Failed item has no size; total_mb should only count the good one
        assert report["total_mb"] > 0
        # Verify the failed item has None size
        failed = [i for i in report["items"] if i["status"] == "FAILED"]
        assert failed[0]["size_mb"] is None


# =============================================================================
# Tests: format_cache_report
# =============================================================================

class TestFormatCacheReport:
    """format_cache_report produces a non-empty, human-readable string."""

    def _make_report(self, items):
        counts = {
            "CACHED":     sum(1 for i in items if i["status"] == "CACHED"),
            "DOWNLOADED": sum(1 for i in items if i["status"] == "DOWNLOADED"),
            "FAILED":     sum(1 for i in items if i["status"] == "FAILED"),
        }
        total_mb = sum(
            i["size_mb"] for i in items
            if i["size_mb"] is not None and i["status"] in ("CACHED", "DOWNLOADED")
        )
        return {
            "items": items,
            "counts": counts,
            "total_mb": round(total_mb, 1),
            "ok": counts["FAILED"] == 0,
        }

    def test_returns_string(self):
        report = self._make_report([
            {"key": "layer_a", "group": "gis", "status": "CACHED",
             "path": "/tmp/layer_a.tif", "size_mb": 5.0, "error": None},
        ])
        text = format_cache_report(report)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_contains_all_names(self):
        items = [
            {"key": "layer_a", "group": "gis", "status": "DOWNLOADED",
             "path": "/tmp/layer_a.tif", "size_mb": 10.0, "error": None},
            {"key": "bad_layer", "group": "gis", "status": "FAILED",
             "path": None, "size_mb": None, "error": "simulated"},
        ]
        text = format_cache_report(self._make_report(items))
        assert "layer_a" in text
        assert "bad_layer" in text

    def test_summary_line_present(self):
        items = [
            {"key": "layer_a", "group": "gis", "status": "CACHED",
             "path": "/tmp/layer_a.tif", "size_mb": 3.5, "error": None},
            {"key": "layer_b", "group": "gis", "status": "DOWNLOADED",
             "path": "/tmp/layer_b.tif", "size_mb": 7.2, "error": None},
        ]
        text = format_cache_report(self._make_report(items))
        # Summary line should mention cached / downloaded / failed
        assert "cached" in text.lower()
        assert "downloaded" in text.lower()
        assert "failed" in text.lower()

    def test_checkmarks_and_crosses(self):
        items = [
            {"key": "ok_layer", "group": "gis", "status": "CACHED",
             "path": "/tmp/ok.tif", "size_mb": 1.0, "error": None},
            {"key": "bad_layer", "group": "gis", "status": "FAILED",
             "path": None, "size_mb": None, "error": "oops"},
        ]
        text = format_cache_report(self._make_report(items))
        assert "✓" in text
        assert "✗" in text


# =============================================================================
# Tests: PREFETCH_GIS_FILES constant
# =============================================================================

class TestPrefetchGisFilesConstant:
    """PREFETCH_GIS_FILES contains the six required names."""

    def test_required_names_present(self):
        required = {
            "model_boundary",
            "model_boundary_segments",
            "wells",
            "rivers",
            "groundwater_map_norm",
            "dem_hres",
        }
        assert required.issubset(set(PREFETCH_GIS_FILES)), (
            f"Missing from PREFETCH_GIS_FILES: {required - set(PREFETCH_GIS_FILES)}"
        )

    def test_is_list(self):
        assert isinstance(PREFETCH_GIS_FILES, list)
        assert len(PREFETCH_GIS_FILES) >= 6
