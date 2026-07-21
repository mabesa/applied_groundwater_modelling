"""
Unit tests for the provisional-vs-authoritative provenance helpers in
``_SUPPORT/src/casestudy_flow_golden.py`` -- ``_os_family`` and
``_provisional_provenance``.

Rule under test: a golden is AUTHORITATIVE (provisional False) only when
frozen on Linux (the authoritative platform for the Triangle/Voronoi refine
mesh); any other generation OS -- macOS, Windows, or an unrecognised/blank OS
string -- is PROVISIONAL (fail-safe: unknown OS => provisional).

PURE tests only: no MF6 solve, no ``generate_group0_golden`` call (that would
require a real Triangle/Voronoi refine + MF6 solve, which SIGILLs on macOS and
is slow regardless).

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_golden_provenance.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import casestudy_flow_golden as g  # noqa: E402


# =====================================================================
# _provisional_provenance
# =====================================================================
class TestProvisionalProvenance:
    def test_linux_is_authoritative(self):
        result = g._provisional_provenance("Linux")
        assert result["provisional"] is False
        assert result["provisional_reason"] is None
        assert result["generation_os"] == "Linux"
        assert result["authoritative_platform"] == "linux"

    def test_darwin_is_provisional(self):
        result = g._provisional_provenance("Darwin")
        assert result["provisional"] is True
        assert isinstance(result["provisional_reason"], str)
        assert len(result["provisional_reason"]) > 0
        assert "PROVISIONAL" in result["provisional_reason"]
        assert result["generation_os"] == "Darwin"

    def test_windows_is_provisional(self):
        result = g._provisional_provenance("Windows")
        assert result["provisional"] is True

    def test_unknown_os_is_provisional_failsafe(self):
        result = g._provisional_provenance("")
        assert result["provisional"] is True
        assert result["generation_os"] == "unknown"


# =====================================================================
# _os_family
# =====================================================================
class TestOsFamily:
    def test_linux_variant(self):
        assert g._os_family("Linux-6.1.0-x86_64") == "Linux"

    def test_macos_variant(self):
        assert g._os_family("macOS-14.5-arm64") == "Darwin"

    def test_windows_variant(self):
        assert g._os_family("Windows-10") == "Windows"

    def test_blank(self):
        assert g._os_family("") == ""

    def test_unrecognised(self):
        assert g._os_family("Plan9") == ""
