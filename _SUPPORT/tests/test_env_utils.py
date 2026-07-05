"""
Unit tests for env_utils.ensure_package.

Tests cover:
- present path: module already importable → status 'present', no install attempted
- missing → install success: subprocess rc=0, re-import succeeds → status 'installed'
- missing → install fail: subprocess rc!=0 → status 'failed', no exception propagates
- missing → subprocess raises → status 'failed', no exception propagates
- installed_needs_restart: install succeeds but re-import still raises → status 'installed_needs_restart'

Run with: uv run pytest _SUPPORT/tests/test_env_utils.py -q
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Add src to path (mirrors the style in other tests in this directory)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import env_utils
from env_utils import ensure_package


# =============================================================================
# Helpers
# =============================================================================

def _make_fake_run(returncode=0, stderr=""):
    """Return a fake subprocess.run that records calls."""
    calls: list[list] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        result = MagicMock()
        result.returncode = returncode
        result.stderr = stderr
        return result

    return fake_run, calls


def _make_import_sequence(*outcomes):
    """
    Return a fake importlib.import_module that steps through *outcomes* on
    successive calls for a given module name.

    Each outcome is either:
    - a SimpleNamespace (returned as the module), or
    - an exception class / instance (raised).

    Other module names (e.g. 'site') are delegated to the real import_module.
    """
    import importlib as _importlib

    target_calls: list[int] = [0]

    def fake_import(name, *args, **kwargs):
        if name == "_test_fake_module_":
            idx = target_calls[0]
            target_calls[0] += 1
            outcome = outcomes[min(idx, len(outcomes) - 1)]
            if isinstance(outcome, type) and issubclass(outcome, BaseException):
                raise outcome(f"fake ImportError #{idx}")
            elif isinstance(outcome, BaseException):
                raise outcome
            return outcome
        # Delegate everything else to real import
        return _importlib.import_module(name)

    return fake_import


# =============================================================================
# Tests: present path
# =============================================================================

class TestPresent:
    """Module already importable → status 'present', subprocess never called."""

    def test_stdlib_module_present(self):
        result = ensure_package('os')
        assert result['package'] == 'os'
        assert result['status'] == 'present'
        assert 'version' in result

    def test_no_subprocess_when_present(self, monkeypatch):
        run_called: list[bool] = []

        def spy_run(cmd, **kwargs):
            run_called.append(True)
            raise AssertionError("subprocess.run must not be called when module is present")

        monkeypatch.setattr(subprocess, 'run', spy_run)
        result = ensure_package('os')
        assert result['status'] == 'present'
        assert not run_called

    def test_version_is_string(self):
        result = ensure_package('os')
        assert isinstance(result.get('version'), str)


# =============================================================================
# Tests: missing → install success
# =============================================================================

class TestInstallSuccess:
    """Module missing; pip succeeds; re-import succeeds → status 'installed'."""

    def test_installed_status(self, monkeypatch):
        fake_module = SimpleNamespace(__version__='9.9.9')

        # import_module: first call raises ImportError, second returns the module
        fake_import = _make_import_sequence(ImportError, fake_module)
        monkeypatch.setattr(importlib, 'import_module', fake_import)

        fake_run, run_calls = _make_fake_run(returncode=0)
        monkeypatch.setattr(subprocess, 'run', fake_run)

        result = ensure_package('_test_fake_module_', '_test_fake_pkg_==9.9.9')

        assert result['status'] == 'installed'
        assert result['version'] == '9.9.9'
        assert result['package'] == '_test_fake_module_'
        assert len(run_calls) == 1

    def test_pip_spec_used(self, monkeypatch):
        """Verify the exact pip_spec ends up in the subprocess command."""
        fake_module = SimpleNamespace(__version__='1.0')
        fake_import = _make_import_sequence(ImportError, fake_module)
        monkeypatch.setattr(importlib, 'import_module', fake_import)

        fake_run, run_calls = _make_fake_run(returncode=0)
        monkeypatch.setattr(subprocess, 'run', fake_run)

        ensure_package('_test_fake_module_', 'mypkg==2.3.4')

        assert any('mypkg==2.3.4' in ' '.join(cmd) for cmd in run_calls)

    def test_default_pip_spec_is_import_name(self, monkeypatch):
        """When pip_spec is omitted, import_name is used as the pip spec."""
        fake_module = SimpleNamespace(__version__='1.0')
        fake_import = _make_import_sequence(ImportError, fake_module)
        monkeypatch.setattr(importlib, 'import_module', fake_import)

        fake_run, run_calls = _make_fake_run(returncode=0)
        monkeypatch.setattr(subprocess, 'run', fake_run)

        ensure_package('_test_fake_module_')

        assert any('_test_fake_module_' in ' '.join(cmd) for cmd in run_calls)


# =============================================================================
# Tests: missing → install fail
# =============================================================================

class TestInstallFail:
    """pip returns non-zero → status 'failed'; no exception propagates."""

    def test_nonzero_returncode(self, monkeypatch):
        fake_import = _make_import_sequence(ImportError)
        monkeypatch.setattr(importlib, 'import_module', fake_import)

        fake_run, _ = _make_fake_run(returncode=1, stderr='ERROR: could not find a version')
        monkeypatch.setattr(subprocess, 'run', fake_run)

        result = ensure_package('_test_fake_module_', 'nosuchpkg==0.0.0')

        assert result['status'] == 'failed'
        assert 'error' in result
        assert result['package'] == '_test_fake_module_'

    def test_subprocess_raises(self, monkeypatch):
        """Even if subprocess.run itself raises, ensure_package must not propagate."""
        fake_import = _make_import_sequence(ImportError)
        monkeypatch.setattr(importlib, 'import_module', fake_import)

        def exploding_run(cmd, **kwargs):
            raise OSError("no such executable")

        monkeypatch.setattr(subprocess, 'run', exploding_run)

        # Must not raise
        result = ensure_package('_test_fake_module_', 'nosuchpkg==0.0.0')
        assert result['status'] == 'failed'
        assert 'error' in result

    def test_no_exception_propagates(self, monkeypatch):
        fake_import = _make_import_sequence(ImportError)
        monkeypatch.setattr(importlib, 'import_module', fake_import)

        fake_run, _ = _make_fake_run(returncode=42, stderr='fatal error')
        monkeypatch.setattr(subprocess, 'run', fake_run)

        # Should return a dict, never raise
        try:
            result = ensure_package('_test_fake_module_')
        except Exception as exc:
            pytest.fail(f"ensure_package raised unexpectedly: {exc}")
        assert isinstance(result, dict)


# =============================================================================
# Tests: installed_needs_restart
# =============================================================================

class TestInstalledNeedsRestart:
    """pip succeeds but re-import still raises → status 'installed_needs_restart'."""

    def test_needs_restart_status(self, monkeypatch):
        # import_module always raises ImportError (even after install)
        fake_import = _make_import_sequence(ImportError, ImportError)
        monkeypatch.setattr(importlib, 'import_module', fake_import)

        fake_run, _ = _make_fake_run(returncode=0)
        monkeypatch.setattr(subprocess, 'run', fake_run)

        result = ensure_package('_test_fake_module_', '_test_fake_pkg_')

        assert result['status'] == 'installed_needs_restart'
        assert 'error' in result
        assert 'restart' in result['error'].lower()

    def test_no_version_key_on_needs_restart(self, monkeypatch):
        fake_import = _make_import_sequence(ImportError, ImportError)
        monkeypatch.setattr(importlib, 'import_module', fake_import)

        fake_run, _ = _make_fake_run(returncode=0)
        monkeypatch.setattr(subprocess, 'run', fake_run)

        result = ensure_package('_test_fake_module_', '_test_fake_pkg_')
        # 'version' should not be present (or be None/absent) when needs_restart
        assert result.get('version') is None or 'version' not in result


# =============================================================================
# Tests: return dict structure
# =============================================================================

class TestReturnStructure:
    """ensure_package always returns a dict with 'package' and 'status' keys."""

    def test_present_has_required_keys(self):
        result = ensure_package('os')
        assert 'package' in result
        assert 'status' in result

    def test_failed_has_error_key(self, monkeypatch):
        fake_import = _make_import_sequence(ImportError)
        monkeypatch.setattr(importlib, 'import_module', fake_import)

        fake_run, _ = _make_fake_run(returncode=1, stderr='oops')
        monkeypatch.setattr(subprocess, 'run', fake_run)

        result = ensure_package('_test_fake_module_')
        assert 'error' in result
