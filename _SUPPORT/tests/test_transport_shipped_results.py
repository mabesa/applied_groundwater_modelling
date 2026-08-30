"""The shipped fine-grid result must be verified before use, and absent gracefully.

Both behaviours matter for the teaching design: the notebooks quote 1 m numbers in their
text, so serving an unverified or wrong archive would print numbers that do not match the
curve beside them -- and failing hard when the download is simply unavailable would stop a
student working for a reason that has nothing to do with them.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_SUPPORT" / "src"))

import transport_shipped_results as tsr  # noqa: E402


def _write(d: Path, times, conc, metrics):
    np.savez_compressed(d / "srcpulse_fine_1m.npz",
                        times=np.asarray(times, float),
                        breakthrough=np.asarray(conc, float))
    (d / "srcpulse_fine_1m.json").write_text(json.dumps(metrics) + "\n")


def test_incomplete_folder_has_no_fingerprint(tmp_path):
    assert tsr.fingerprint(tmp_path) is None


def test_fingerprint_changes_with_content(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    _write(a, [1.0, 2.0], [0.0, 1.0], {"peak_mgL": 1.0})
    _write(b, [1.0, 2.0], [0.0, 2.0], {"peak_mgL": 2.0})
    fa, fb = tsr.fingerprint(a), tsr.fingerprint(b)
    assert fa and fb and fa != fb


def test_a_wrong_archive_is_refused(tmp_path, monkeypatch):
    """🔴 The control: content that is present but NOT the shipped result must not load."""
    d = tmp_path / "fine"; d.mkdir()
    _write(d, [1.0, 2.0], [0.0, 1.0], {"peak_mgL": 1.0})
    assert tsr.fingerprint(d) != tsr.CANONICAL_FINE_FINGERPRINT
    # ensure_fine_result would try to re-download; make that impossible and assert refusal
    monkeypatch.setattr(tsr, "_subdir", lambda: d)
    monkeypatch.setitem(sys.modules, "data_utils", None)
    assert tsr.ensure_fine_result(d) is None
    assert tsr.load_fine_result(d) is None


def test_missing_download_returns_none_not_raise(tmp_path, monkeypatch):
    """Offline is a normal state for a student; it must not raise."""
    monkeypatch.setitem(sys.modules, "data_utils", None)
    assert tsr.load_fine_result(tmp_path / "absent") is None


def test_verify_reports_without_raising(tmp_path):
    r = tsr.verify(tmp_path)
    assert r["present"] is False and r["is_canonical"] is False
    assert r["canonical"] == tsr.CANONICAL_FINE_FINGERPRINT


def test_canonical_fingerprint_is_pinned():
    assert isinstance(tsr.CANONICAL_FINE_FINGERPRINT, str)
    assert len(tsr.CANONICAL_FINE_FINGERPRINT) == 16


# --- the config-entry fallback -----------------------------------------------
def test_heal_is_a_noop_when_the_entry_exists(monkeypatch):
    import data_utils as du
    urls = du.get_data_urls()
    if tsr.DOWNLOAD_NAME not in urls:
        pytest.skip("this checkout's config has no transport_fine_1m entry")
    before = dict(urls[tsr.DOWNLOAD_NAME])
    tsr._heal_download_entry()
    assert urls[tsr.DOWNLOAD_NAME] == before, "an existing entry must never be overwritten"


def test_heal_restores_an_entry_missing_from_an_old_config():
    """config.py is a one-time copy, so an existing one never receives new entries."""
    import data_utils as du
    urls = du.get_data_urls()
    if tsr.DOWNLOAD_NAME not in urls:
        pytest.skip("this checkout's config has no transport_fine_1m entry")
    saved = urls.pop(tsr.DOWNLOAD_NAME)            # simulate a config.py that predates it
    try:
        tsr._heal_download_entry()
        assert tsr.DOWNLOAD_NAME in urls
        assert urls[tsr.DOWNLOAD_NAME]["url"] == saved["url"]
    finally:
        urls[tsr.DOWNLOAD_NAME] = saved


def test_a_deliberate_none_url_is_left_alone():
    """Omission is not a supported way to disable the download; url=None is, and the
    heal must not 'repair' it back to the template's URL."""
    import data_utils as du
    urls = du.get_data_urls()
    if tsr.DOWNLOAD_NAME not in urls:
        pytest.skip("this checkout's config has no transport_fine_1m entry")
    saved = urls[tsr.DOWNLOAD_NAME]
    urls[tsr.DOWNLOAD_NAME] = {**saved, "url": None}
    try:
        tsr._heal_download_entry()
        assert urls[tsr.DOWNLOAD_NAME]["url"] is None
    finally:
        urls[tsr.DOWNLOAD_NAME] = saved
