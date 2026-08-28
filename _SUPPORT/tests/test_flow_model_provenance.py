"""The calibrated mother model must be verified, not merely present.

Regression tests for the 2026-08-28 root cause: `ensure_flow_model()` returned an
already-present local workspace after checking only `MANIFEST_flow.json`'s
`archive_version`. Because `stamp_flow_manifest()` deliberately lets a legitimate local
05f output stamp itself current, a workspace regenerated in place passed that gate with
DIFFERENT CONTENT and was then served to every caller silently.

On the JupyterHub that drifted `botm`, which propagated into the refined `botm` and through
`strt = max(strt, botm + 0.01)` into `strt`, failing all NINE case-study golden pins and
CRASHING the student flow case study -- with an error that named the grid.

See DOCUMENTATION/contracts/evidence/s3b/ROOT_CAUSE_MOTHER_MODEL_DRIFT.md.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_SUPPORT" / "src"))

import model_io_utils as mio  # noqa: E402


@pytest.fixture
def ws():
    try:
        return mio.ensure_flow_model()
    except Exception as exc:                       # noqa: BLE001
        pytest.skip(f"calibrated flow model unavailable: {exc}")


def test_canonical_fingerprint_is_pinned():
    assert isinstance(mio.CANONICAL_FLOW_FINGERPRINT, str)
    assert len(mio.CANONICAL_FLOW_FINGERPRINT) == 16


def test_local_workspace_is_the_shipped_one(ws):
    """If this fails, THIS machine has a drifted calibration -- exactly the Hub's state."""
    r = mio.verify_flow_model(ws)
    assert r["is_canonical"], mio._flow_model_drift_message(Path(ws), r)
    assert r["manifest_consistent"]


def test_verify_reports_rather_than_raises(tmp_path):
    """An empty directory is reported, not exploded on."""
    r = mio.verify_flow_model(tmp_path)
    assert r["fingerprint"] is None
    assert r["is_canonical"] is False


# --- the negative controls: drift MUST be caught -----------------------------
@pytest.fixture
def drifted(monkeypatch):
    monkeypatch.setattr(mio, "CANONICAL_FLOW_FINGERPRINT", "deadbeefdeadbeef")


def test_drift_warns_by_default(ws, drifted):
    """Default is a WARNING: a deliberate local calibration stays usable."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        mio.ensure_flow_model()
    assert len(w) == 1
    assert "NOT the shipped one" in str(w[0].message)


def test_drift_is_refused_when_canonical_is_required(ws, drifted):
    """🔴 The control that protects golden-pinned builds."""
    with pytest.raises(FileNotFoundError, match="NOT the shipped one"):
        mio.ensure_flow_model(require_canonical=True)


def test_drift_warning_names_the_cause_and_the_remedy(ws, drifted):
    r = mio.verify_flow_model(ws)
    msg = mio._flow_model_drift_message(Path(ws), r)
    assert "05f_calibration" in msg                      # the cause
    assert "local-backup" in msg                         # the remedy
    assert "DIVERGED" in msg                             # ties to the symptom seen
    assert mio._SKIP_FINGERPRINT_ENV in msg              # the deliberate opt-out


def test_opt_out_silences_the_warning_but_not_the_refusal(ws, drifted, monkeypatch):
    monkeypatch.setenv(mio._SKIP_FINGERPRINT_ENV, "1")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        mio.ensure_flow_model()
    assert not w, "opt-out should silence the warning"
    with pytest.raises(FileNotFoundError):
        mio.ensure_flow_model(require_canonical=True)


def test_golden_pinned_walk_requires_the_canonical_model():
    """The case-study builder must ask for the shipped calibration, not merely any."""
    src = (REPO / "_SUPPORT" / "src" / "casestudy_flow_builder.py").read_text()
    assert "ensure_flow_model(require_canonical=True)" in src, (
        "the golden-pinned walk must require the canonical calibration -- otherwise a "
        "local 05f variant fails downstream as 'the built grid DIVERGED'")
