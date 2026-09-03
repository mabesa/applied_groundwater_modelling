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


def ensure_pinned_versions(packages=CRITICAL_PACKAGES, lock_path=None, *,
                           install: bool = True, user: bool = True,
                           quiet: bool = True) -> dict:
    """Bring the CRITICAL packages up to the versions ``uv.lock`` pins.

    ``ensure_package`` only helps when a package is MISSING. These packages are
    always present -- the JupyterHub image ships them -- just sometimes at the wrong
    version, which ``ensure_package``'s importability check cannot see.

    🔴 Why this exists. The Hub's base image carries older numpy/flopy than the
    project pins. The frozen goldens record the versions that produced them, and
    numpy/flopy set the bit pattern of those arrays, so a drifted kernel cannot tell
    a real regression from an environment difference -- the checks report
    ENV_MISMATCH (inconclusive), never a silent pass. On 2026-09-02 the same Hub node
    produced goldens at numpy 2.3.5 / flopy 3.9.5 and then, weeks later, at
    2.1.3 / 3.9.3: the top-up into the user site had been lost (image rebuild or a
    fresh home), and nothing re-applied it. This re-applies it.

    Installs into the USER site (``pip --user``), which is what a multi-user Hub
    allows -- the base image itself cannot be modified.

    ⚠️ numpy and flopy are almost certainly imported already by the time this runs
    (flopy imports numpy), so a successful install does NOT take effect in the
    running kernel. Such a package is reported ``installed_needs_restart``; the
    caller must tell the user to restart and re-run.

    Parameters
    ----------
    install:
        When False, behaves exactly like ``check_pinned_versions`` -- report only.
        Useful for a dry run, and for tests that must never touch the environment.

    Returns
    -------
    dict
        The ``check_pinned_versions`` report, plus ``"actions"``:
        ``{name: {"status": ..., "from": installed, "to": locked, "error": ...}}``
        where status is ``ok`` (already correct), ``installed_needs_restart``,
        ``failed``, ``skipped_no_lock``, or ``reported_only``; and
        ``"needs_restart"``: bool.
    """
    import subprocess
    import sys

    report = check_pinned_versions(packages=packages, lock_path=lock_path)
    report["actions"] = {}
    report["needs_restart"] = False

    for name, row in report["packages"].items():
        if row["matches"] is True:
            report["actions"][name] = {"status": "ok", "from": row["installed"],
                                       "to": row["locked"]}
            continue
        if row["locked"] is None:
            # No pin to aim at -- never guess a version.
            report["actions"][name] = {"status": "skipped_no_lock",
                                       "from": row["installed"], "to": None}
            continue
        if not install:
            report["actions"][name] = {"status": "reported_only",
                                       "from": row["installed"], "to": row["locked"]}
            continue

        cmd = [sys.executable, "-m", "pip", "install", f"{name}=={row['locked']}"]
        if user:
            cmd.append("--user")
        if quiet:
            cmd.append("--quiet")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as exc:                        # noqa: BLE001
            report["actions"][name] = {"status": "failed", "from": row["installed"],
                                       "to": row["locked"],
                                       "error": f"subprocess error: {exc}"}
            continue
        if proc.returncode != 0:
            report["actions"][name] = {
                "status": "failed", "from": row["installed"], "to": row["locked"],
                "error": (proc.stderr or "").strip()[:500]
                          or f"pip exited with code {proc.returncode}"}
            continue
        # Installed, but the OLD module object is already bound in this kernel.
        report["actions"][name] = {"status": "installed_needs_restart",
                                   "from": row["installed"], "to": row["locked"]}
        report["needs_restart"] = True

    return report


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


# ---------------------------------------------------------------------------
# security floors  (>= semantics, NOT ==)
# ---------------------------------------------------------------------------
#: Packages we want at a MINIMUM version for security. The floor is read from
#: ``uv.lock``, so a future CVE bump is ``uv lock --upgrade-package X`` and nothing
#: else -- no Hub-admin ticket per minor version (lecturer, 2026-09-03).
#:
#: 🔴 Why this is separate from :data:`CRITICAL_PACKAGES`. That set is pinned with
#: ``==`` because the frozen goldens record exact versions and a newer numpy can
#: change array bit patterns. A security bump needs the opposite: *at least* this
#: version, never *exactly* it. Pinning ``==`` would DOWNGRADE a Hub whose image
#: runs ahead of our lock -- and that becomes the normal case as the lock ages.
#:
#: 🔴 Split by BLAST RADIUS, not by severity:
#:
#: * KERNEL packages are imported by the student's kernel. A user-site top-up is
#:   picked up on the next kernel restart and cannot stop a session from starting.
#: * SERVER packages are the Jupyter server's OWN stack. These are never installed
#:   automatically. A broken user-site copy can stop a single-user server from
#:   starting, and the student then has no notebook from which to repair it -- so
#:   they are REPORTED and a human decides. (Lecturer's choice, 2026-09-03:
#:   "option B".)
SECURITY_FLOOR_KERNEL: tuple = ()
SECURITY_FLOOR_SERVER: tuple = ("tornado",)
SECURITY_FLOOR_PACKAGES: tuple = SECURITY_FLOOR_KERNEL + SECURITY_FLOOR_SERVER


def installed_version(name: str):
    """Installed version of *name*, or ``None``.

    Uses distribution metadata rather than a ``__version__`` attribute: tornado --
    the first package enrolled here -- exposes ``tornado.version`` and NO
    ``__version__``, so an attribute probe reports it as unknown and the floor
    check would silently never fire.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:                     # pragma: no cover - <3.8
        return None
    try:
        return version(name)
    except PackageNotFoundError:
        return None
    except Exception:                       # noqa: BLE001 - broken metadata
        return None


def _below(installed, floor) -> bool:
    """True when *installed* is strictly older than *floor*. Unknown -> False."""
    if installed is None or floor is None:
        return False
    try:
        from packaging.version import Version
        return Version(installed) < Version(floor)
    except Exception:                       # noqa: BLE001 - unparseable version
        # Never guess: an unparseable version is not evidence of being behind.
        return False


def check_security_floors(packages=SECURITY_FLOOR_PACKAGES, lock_path=None) -> dict:
    """Compare installed versions against the ``uv.lock`` FLOOR. Reports only.

    ``satisfied`` is ``None`` -- unknown, never ``True`` -- when either side is
    unavailable, so a missing lock can never read as agreement.
    """
    locked = locked_versions(lock_path)
    out = {"lock_found": bool(locked), "packages": {}, "below_floor": [],
           "unknown": []}
    for name in packages:
        inst = installed_version(name)
        floor = locked.get(name)
        if inst is None or floor is None:
            satisfied = None
        else:
            satisfied = not _below(inst, floor)
        out["packages"][name] = {"installed": inst, "floor": floor,
                                 "satisfied": satisfied,
                                 "layer": "server" if name in SECURITY_FLOOR_SERVER
                                          else "kernel"}
        if satisfied is False:
            out["below_floor"].append(name)
        elif satisfied is None:
            out["unknown"].append(name)
    return out


def ensure_security_floors(packages=SECURITY_FLOOR_PACKAGES, lock_path=None, *,
                           install: bool = True, user: bool = True,
                           quiet: bool = True) -> dict:
    """Top up KERNEL-layer packages that are below their ``uv.lock`` floor.

    Installs ``{name}>={floor}`` -- never ``==`` -- and only when the installed
    version is strictly older, so a Hub already ahead of our lock is left alone.
    SERVER-layer packages are reported, never installed; see
    :data:`SECURITY_FLOOR_SERVER` for why.

    Status values: ``ok`` (at or above the floor), ``installed_needs_restart``,
    ``server_stack_reported`` (below floor, deliberately not installed),
    ``failed``, ``skipped_no_lock``, ``skipped_unknown_version``,
    ``reported_only`` (``install=False``).
    """
    import subprocess
    import sys

    report = check_security_floors(packages=packages, lock_path=lock_path)
    report["actions"] = {}
    report["needs_restart"] = False
    report["server_stack_below_floor"] = []

    for name, row in report["packages"].items():
        inst, floor, layer = row["installed"], row["floor"], row["layer"]
        act = {"from": inst, "to": floor, "layer": layer}

        if floor is None:
            report["actions"][name] = {**act, "status": "skipped_no_lock"}
            continue
        if inst is None:
            # Not installed at all. Absent from a Hub image is not the case this
            # exists for, and guessing an install here could pull a whole stack.
            report["actions"][name] = {**act, "status": "skipped_unknown_version"}
            continue
        if row["satisfied"] is True:
            report["actions"][name] = {**act, "status": "ok"}
            continue
        if layer == "server":
            # 🔴 Deliberately NOT installed -- see SECURITY_FLOOR_SERVER.
            report["actions"][name] = {**act, "status": "server_stack_reported"}
            report["server_stack_below_floor"].append(name)
            continue
        if not install:
            report["actions"][name] = {**act, "status": "reported_only"}
            continue

        cmd = [sys.executable, "-m", "pip", "install", f"{name}>={floor}"]
        if user:
            cmd.append("--user")
        if quiet:
            cmd.append("--quiet")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as exc:            # noqa: BLE001
            report["actions"][name] = {**act, "status": "failed",
                                       "error": f"subprocess error: {exc}"}
            continue
        if proc.returncode != 0:
            report["actions"][name] = {
                **act, "status": "failed",
                "error": (proc.stderr or "").strip()[:500]
                          or f"pip exited with code {proc.returncode}"}
            continue
        report["actions"][name] = {**act, "status": "installed_needs_restart"}
        report["needs_restart"] = True

    return report
