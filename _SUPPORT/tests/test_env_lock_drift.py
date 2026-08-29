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
    """env_utils' own scope note: auto-install is pyemu ONLY. The drift half must not
    acquire an install path -- a pip upgrade of numpy in a shared conda kernel is
    exactly what the module warns against."""
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
