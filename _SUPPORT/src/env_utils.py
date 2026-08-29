"""
env_utils — runtime dependency self-healing for JupyterHub kernels.

Provides ensure_package(), which checks whether a Python package is importable
and pip-installs it into the running kernel if it is not. The intended use-case
is a small set of packages (currently only pyemu) that may be absent from the
JupyterHub image but that are required by specific notebooks.

Scope: pyemu ONLY — do NOT add auto-installs for geospatial or other packages
whose pip wheel may conflict with the conda-managed ABI on the hub.

Also provides READ-ONLY drift reporting against ``uv.lock`` — see
:func:`check_pinned_versions`. That half installs nothing, deliberately: the
JupyterHub image is not something a student can change, and upgrading a
foundational package in a shared kernel risks an environment inconsistent with
the image. Reporting is the product; repair is a deployment action.
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


# ---------------------------------------------------------------------------
# Lock drift reporting (read-only; installs nothing)
# ---------------------------------------------------------------------------
#: Packages whose VERSION changes model numbers, so a mismatch against the lock
#: is worth reporting. Deliberately short.
#:
#: ⚠️ `shapely` is excluded ON PURPOSE. Its relevance is via the native GEOS
#: runtime, and a lock comparison reports the *Python package* version, which
#: does not describe GEOS — the flow goldens record `geos` separately for
#: exactly that reason. A shapely row here would look like GEOS coverage
#: without being it, which is worse than no row. `pandas`/`geopandas` shape
#: dataframes, not model arrays, and are excluded too.
CRITICAL_PACKAGES = ("numpy", "scipy", "flopy")


def _find_uv_lock(start=None):
    """Walk up from this file (or *start*) looking for ``uv.lock``."""
    from pathlib import Path
    here = Path(start) if start else Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "uv.lock" if parent.is_dir() else parent.parent / "uv.lock"
        if candidate.is_file():
            return candidate
    return None


def locked_versions(lock_path=None) -> dict:
    """``{package: version}`` from ``uv.lock``, or ``{}`` if it cannot be read.

    The lock is READ, never restated in code. A second copy of the pins is the
    very thing that goes stale — which is how a Hub running numpy 2.1.3 against
    a lock pinning 2.3.5 stayed invisible.
    """
    from pathlib import Path
    path = Path(lock_path) if lock_path else _find_uv_lock()
    if path is None or not path.is_file():
        return {}
    try:
        import tomllib                      # stdlib on 3.11+
    except ImportError:                     # pragma: no cover - 3.10 and below
        try:
            import tomli as tomllib         # type: ignore
        except ImportError:
            return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:                       # noqa: BLE001 - malformed lock -> unknown
        return {}
    return {p["name"]: p.get("version") for p in data.get("package", [])
            if isinstance(p, dict) and p.get("name")}


def check_pinned_versions(packages=CRITICAL_PACKAGES, lock_path=None) -> dict:
    """Compare installed versions against ``uv.lock``. Reports; never installs.

    Returns ``{"lock_found": bool, "packages": {name: {installed, locked,
    matches}}, "mismatches": [...], "unknown": [...]}``.

    ``matches`` is ``None`` — *unknown*, never ``True`` — when either side is
    unavailable, so a missing lock or an uninstalled package can never read as
    agreement.
    """
    locked = locked_versions(lock_path)
    out = {"lock_found": bool(locked), "packages": {}, "mismatches": [], "unknown": []}
    for name in packages:
        try:
            installed = getattr(__import__(name), "__version__", None)
        except Exception:                   # noqa: BLE001 - absent or broken import
            installed = None
        want = locked.get(name)
        matches = None if (installed is None or want is None) else (installed == want)
        out["packages"][name] = {"installed": installed, "locked": want,
                                 "matches": matches}
        if matches is False:
            out["mismatches"].append(name)
        elif matches is None:
            out["unknown"].append(name)
    return out
