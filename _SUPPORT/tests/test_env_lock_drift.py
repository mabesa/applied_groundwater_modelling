"""`0_diagnostics` must report when the running environment drifts from `uv.lock`.

Written after a JupyterHub ran numpy 2.1.3 / flopy 3.9.3 against a lock pinning
2.3.5 / 3.9.5 with nothing anywhere saying so. That drift was not what broke the
case-study goldens (a drifted mother-model data file was) -- but ruling it out cost a
diagnostic cycle, which is exactly the cost this reporting removes.

The design constraint these tests protect: the check READS `uv.lock` rather than
restating the versions in code, so there is no second copy of the pins to go stale.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_SUPPORT" / "src"))

import env_utils as eu  # noqa: E402


def test_lock_is_found_and_parsed():
    assert eu._find_uv_lock() is not None
    locked = eu.locked_versions()
    assert locked.get("numpy") and locked.get("flopy")


def test_critical_set_is_small_and_deliberate():
    assert eu.CRITICAL_PACKAGES == ("numpy", "scipy", "flopy")
    # 🔴 shapely is excluded on purpose: a lock comparison reports the PYTHON package
    # version, which does not describe the native GEOS runtime that decides geometry.
    # A shapely row would look like GEOS coverage without being it.
    assert "shapely" not in eu.CRITICAL_PACKAGES
    assert "pandas" not in eu.CRITICAL_PACKAGES


def test_this_environment_matches_the_lock():
    """If this fails, THIS machine has the drift the Hub had."""
    report = eu.check_pinned_versions()
    assert report["lock_found"]
    assert not report["mismatches"], report["packages"]


# --- the negative controls: drift and unknowns must not read as agreement ----
def test_drift_is_reported(tmp_path):
    lock = tmp_path / "uv.lock"
    lock.write_text('[[package]]\nname = "numpy"\nversion = "0.0.1"\n')
    report = eu.check_pinned_versions(packages=("numpy",), lock_path=lock)
    assert report["mismatches"] == ["numpy"]
    assert report["packages"]["numpy"]["matches"] is False


def test_missing_lock_is_unknown_never_ok(tmp_path):
    """🔴 A missing lock must never read as 'versions agree'."""
    report = eu.check_pinned_versions(packages=("numpy",), lock_path=tmp_path / "absent.lock")
    assert report["lock_found"] is False
    assert report["packages"]["numpy"]["matches"] is None
    assert report["mismatches"] == []          # unknown is not a mismatch...
    assert report["unknown"] == ["numpy"]      # ...but it IS surfaced


def test_absent_package_is_unknown_never_ok(tmp_path):
    lock = tmp_path / "uv.lock"
    lock.write_text('[[package]]\nname = "definitely_not_installed_xyz"\nversion = "1.0"\n')
    report = eu.check_pinned_versions(packages=("definitely_not_installed_xyz",), lock_path=lock)
    assert report["packages"]["definitely_not_installed_xyz"]["matches"] is None


def test_malformed_lock_is_unknown_never_ok(tmp_path):
    lock = tmp_path / "uv.lock"
    lock.write_text("this is not toml {{{")
    assert eu.locked_versions(lock) == {}


def test_reporting_never_installs():
    """The REPORTING half must never shell out.

    🔴 2026-09-02 -- this note used to read "auto-install is pyemu ONLY", and that
    policy has changed on the lecturer's instruction: the Hub's base image ships older
    numpy/flopy than the project pins and CANNOT be modified, so `0_diagnostics` now
    tops them up via `ensure_pinned_versions`.

    The original warning still stands and is why repair lives in its own function
    rather than inside these: a pip upgrade of numpy under a conda base can break
    packages compiled against the older one. Mitigations: the bump stays inside
    numpy 2.x (stable ABI); it installs `--user`, so `rm -rf
    ~/.local/lib/python3.*/site-packages/numpy*` reverts it; and it reports
    `installed_needs_restart` instead of pretending the running kernel picked it up.

    So: reporting stays pure, repair is opt-in and explicitly named. This test pins
    that separation.
    """
    import ast
    import inspect
    # Assert on the MECHANISM, not the word: the docstrings legitimately say
    # "installs nothing", so a substring check would fail on its own documentation.
    forbidden = {"subprocess", "check_call", "check_output", "run", "Popen", "system"}
    for fn in (eu.locked_versions, eu.check_pinned_versions, eu._find_uv_lock):
        tree = ast.parse(inspect.getsource(fn).lstrip())
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        imported = {a.name.split(".")[0] for n in ast.walk(tree)
                    if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module.split(".")[0] for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom) and n.module}
        offending = (names | imported) & forbidden
        assert not offending, f"{fn.__name__} may not shell out: {offending}"
        assert "pip" not in imported


# =============================================================================
# ensure_pinned_versions -- repair, not just report (2026-09-02)
#
# The Hub's base image ships older numpy/flopy than the project pins, and the base
# image cannot be modified. `ensure_package` cannot help: it only installs a MISSING
# package, and these are present at the wrong version. Every test here forbids a real
# install -- pip is monkeypatched -- so the suite can never mutate the environment
# it is running in.
# =============================================================================
class TestEnsurePinnedVersions:
    def test_dry_run_never_installs(self, monkeypatch):
        import subprocess as _sp

        def boom(*a, **k):
            raise AssertionError("install=False must not shell out to pip")

        monkeypatch.setattr(_sp, "run", boom)
        rep = eu.ensure_pinned_versions(install=False)
        assert all(a["status"] in ("ok", "reported_only", "skipped_no_lock")
                   for a in rep["actions"].values())
        assert rep["needs_restart"] is False

    def test_a_matching_env_installs_nothing(self, monkeypatch):
        import subprocess as _sp
        calls = []
        monkeypatch.setattr(_sp, "run", lambda *a, **k: calls.append(a))
        monkeypatch.setattr(eu, "check_pinned_versions",
                            lambda **k: {"lock_found": True, "mismatches": [], "unknown": [],
                                         "packages": {"numpy": {"installed": "2.3.5",
                                                                "locked": "2.3.5",
                                                                "matches": True}}})
        rep = eu.ensure_pinned_versions()
        assert calls == [], "nothing to do, so pip must not be called"
        assert rep["actions"]["numpy"]["status"] == "ok"

    def test_drift_triggers_a_pinned_user_install_and_demands_a_restart(self, monkeypatch):
        """The package is already imported, so a successful install cannot take effect
        in the running kernel -- the caller MUST be told to restart."""
        import subprocess as _sp

        seen = {}

        class _OK:
            returncode = 0
            stdout = stderr = ""

        def fake_run(cmd, **k):
            seen["cmd"] = cmd
            return _OK()

        monkeypatch.setattr(_sp, "run", fake_run)
        monkeypatch.setattr(eu, "check_pinned_versions",
                            lambda **k: {"lock_found": True, "mismatches": ["numpy"],
                                         "unknown": [],
                                         "packages": {"numpy": {"installed": "2.1.3",
                                                                "locked": "2.3.5",
                                                                "matches": False}}})
        rep = eu.ensure_pinned_versions()
        assert "numpy==2.3.5" in seen["cmd"], "must pin the EXACT locked version"
        assert "--user" in seen["cmd"], "the Hub base image cannot be modified"
        assert rep["actions"]["numpy"]["status"] == "installed_needs_restart"
        assert rep["needs_restart"] is True

    def test_a_failed_install_is_reported_never_swallowed(self, monkeypatch):
        import subprocess as _sp

        class _Bad:
            returncode = 1
            stdout = ""
            stderr = "no matching distribution"

        monkeypatch.setattr(_sp, "run", lambda *a, **k: _Bad())
        monkeypatch.setattr(eu, "check_pinned_versions",
                            lambda **k: {"lock_found": True, "mismatches": ["flopy"],
                                         "unknown": [],
                                         "packages": {"flopy": {"installed": "3.9.3",
                                                                "locked": "3.9.5",
                                                                "matches": False}}})
        rep = eu.ensure_pinned_versions()
        assert rep["actions"]["flopy"]["status"] == "failed"
        assert "no matching distribution" in rep["actions"]["flopy"]["error"]
        assert rep["needs_restart"] is False, "a failed install is not a pending restart"

    def test_no_lock_entry_is_never_guessed(self, monkeypatch):
        import subprocess as _sp
        monkeypatch.setattr(_sp, "run",
                            lambda *a, **k: pytest.fail("must not install without a pin"))
        monkeypatch.setattr(eu, "check_pinned_versions",
                            lambda **k: {"lock_found": False, "mismatches": [],
                                         "unknown": ["numpy"],
                                         "packages": {"numpy": {"installed": "2.1.3",
                                                                "locked": None,
                                                                "matches": None}}})
        rep = eu.ensure_pinned_versions()
        assert rep["actions"]["numpy"]["status"] == "skipped_no_lock"
