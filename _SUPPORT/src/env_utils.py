"""
env_utils — runtime dependency self-healing for JupyterHub kernels.

Provides ensure_package(), which checks whether a Python package is importable
and pip-installs it into the running kernel if it is not. The intended use-case
is a small set of packages (currently only pyemu) that may be absent from the
JupyterHub image but that are required by specific notebooks.

Scope: pyemu ONLY — do NOT add auto-installs for geospatial or other packages
whose pip wheel may conflict with the conda-managed ABI on the hub.
"""

from __future__ import annotations


def ensure_package(import_name: str, pip_spec: str | None = None,
                   user: bool = True, quiet: bool = True) -> dict:
    """Ensure *import_name* is importable, installing *pip_spec* if needed.

    Parameters
    ----------
    import_name:
        The module name used in ``import <import_name>``.
    pip_spec:
        The pip install spec (e.g. ``'pyemu==1.4.0'``).  Defaults to
        *import_name* when omitted.
    user:
        Pass ``--user`` to pip so the package is installed into the user site
        directory (safe on multi-user JupyterHub instances).
    quiet:
        Pass ``--quiet`` to pip to suppress verbose output.

    Returns
    -------
    dict with keys:
        ``package``  – the *import_name* string.
        ``status``   – one of ``'present'``, ``'installed'``,
                       ``'installed_needs_restart'``, or ``'failed'``.
        ``version``  – package ``__version__`` string (present/installed only).
        ``error``    – diagnostic message (failed/installed_needs_restart only).
    """
    # Keep all imports local so the module itself has no heavy top-level deps.
    import importlib

    pip_spec = pip_spec or import_name

    # --- fast path: already importable ---
    try:
        m = importlib.import_module(import_name)
        return {
            'package': import_name,
            'status': 'present',
            'version': getattr(m, '__version__', 'unknown'),
        }
    except ImportError:
        pass

    # --- attempt pip install ---
    import sys
    import subprocess

    cmd = [sys.executable, '-m', 'pip', 'install', pip_spec]
    if user:
        cmd.append('--user')
    if quiet:
        cmd.append('--quiet')

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
    except Exception as exc:  # subprocess itself failed (very unusual)
        return {
            'package': import_name,
            'status': 'failed',
            'error': f'subprocess error: {exc}',
        }

    if result.returncode != 0:
        stderr_trimmed = (result.stderr or '').strip()[:500]
        return {
            'package': import_name,
            'status': 'failed',
            'error': stderr_trimmed or f'pip exited with code {result.returncode}',
        }

    # --- make the newly installed package importable in THIS kernel ---
    import site

    usp = site.getusersitepackages()
    if usp and usp not in sys.path:
        sys.path.insert(0, usp)
    importlib.invalidate_caches()

    try:
        m = importlib.import_module(import_name)
        return {
            'package': import_name,
            'status': 'installed',
            'version': getattr(m, '__version__', 'unknown'),
        }
    except ImportError:
        return {
            'package': import_name,
            'status': 'installed_needs_restart',
            'error': (
                'installed but not importable in the running kernel'
                ' — restart the kernel and re-run'
            ),
        }
