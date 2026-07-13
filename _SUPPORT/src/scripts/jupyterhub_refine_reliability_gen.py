#!/usr/bin/env python
"""
================================================================================
 PINNED FLOW GENERATION / DETERMINISM CHECK / FREEZE  (milestone M2b-gen-script)
================================================================================

Instructor-side orchestration that will run on the JupyterHub-Linux box to
produce the per-group PINNED flow artifacts (``group<N>_flow.npz`` +
manifest) consumed by ``model_io_utils.load_pinned_flow_model``.

This is a DISTINCT module from ``jupyterhub_refine_reliability_check.py``
(the pre-existing real-MF6 SIGILL sweep with module-level side effects) --
that legacy diagnostic is left untouched.

Scope (M2b-1): the PURE determinism-check core.
    - ``run_group_determinism_check`` -- reruns a caller-supplied runner and
      verifies exact agreement on the grid/BC structure (ncpl, active-cell
      count, chd/riv/wel cellids, well_cells) and on the refine radius, and
      enforces that no run silently fell back to a wider retry radius.
    - ``assert_flow_specs_equal`` -- exact freeze/load (or rerun) equivalence
      helper for a flow spec, via ``np.array_equal``.

Neither of the above imports MODFLOW/flopy or spawns a subprocess -- both are
plain-data checks over the dicts/tuples a real runner produces.

Scope (M2b-2): subprocess-isolated runner + freeze-on-PASS orchestration.
    - ``subprocess_refine_runner`` -- runs one refinement attempt in a FRESH
      Python subprocess (this same file, re-invoked with a private child
      flag) and returns ``(spec, radius_used, retried)`` via a
      freeze -> subprocess -> load IPC hop. A child that exits nonzero or
      dies by signal (the uncatchable-SIGILL case ``refine_with_retry``
      cannot itself survive) is surfaced as a normal Python exception --
      the parent process never crashes. Honours two child-side test hooks
      so the IPC path is exercisable with NO MODFLOW:
        * ``AGM_FAKE_SPEC_NPZ``    -- child freezes this pre-frozen spec
          instead of running a real refinement.
        * ``AGM_FAKE_CHILD_SIGNAL`` -- child kills itself with this signal
          number (simulates an uncatchable SIGILL) before doing anything
          else.
    - ``freeze_group_flow_artifact`` -- on a determinism PASS, freezes the
      canonical spec (via ``model_io_utils.freeze_flow_spec``, which itself
      calls ``validate_flow_spec`` and never writes on an invalid spec) to
      ``<meshes_dir>/group<N>_flow.npz`` + manifest, recording ``group``,
      ``platform.node()``, best-effort tool versions, and ``radius_used``.

Scope (M2b-3): the CLI entry point.
    - ``main(argv=None) -> int`` -- argparse CLI wiring ``--groups`` (comma
      list and/or ``lo-hi`` ranges, e.g. ``"0-8"`` or ``"0,3,5"``, restricted
      to the canonical 0-8 group domain via
      ``case_validation.parse_groups_spec`` / ``CANONICAL_GROUPS`` -- exits 2
      on a malformed or out-of-domain spec), ``--reruns``, ``--meshes-dir``,
      ``--freeze``, ``--out``, ``--require-green-style`` and
      ``--child-timeout`` (bounds how long a single subprocess child may run
      before its process group is killed and the group recorded FAILED;
      default 1800s). For each selected group it runs
      ``run_group_determinism_check`` against ``subprocess_refine_runner``
      (subprocess-isolated -- a child SIGILL never kills the orchestrator),
      optionally freezes the PASSing spec via
      ``freeze_group_flow_artifact`` when ``--freeze`` is given, and writes
      one machine-readable JSON report entry per group to ``--out``
      (determinism status/reason, freeze status, node, tool versions, and
      radius). Exits nonzero ONLY when ``--require-green-style`` is set and
      at least one selected group failed determinism; without that flag a
      failing group is reported but the run still exits 0. The model-loading
      / subprocess body only ever executes inside ``main()`` -- importing
      this module has no side effects.

      The heavier real-MF6 "assemble a frozen spec == a direct
      ``build_refined_gwf_model``" equivalence check is HUB-ONLY (guarded
      behind ``AGM_HUB_CHECKS=1`` in the test suite) and is NOT part of this
      CLI's local execution path.
================================================================================
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import numpy as np

# Make ``model_io_utils`` (one directory up, in _SUPPORT/src) importable both
# when this module is imported normally (pytest already puts _SUPPORT/src on
# sys.path) and when it is re-invoked as a standalone child subprocess (see
# ``subprocess_refine_runner``), which starts with a fresh sys.path.
_SRC_DIR = str(Path(__file__).resolve().parent.parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import model_io_utils as mio  # noqa: E402
import case_validation as cv  # noqa: E402

# Private CLI flag that re-invokes this file as the subprocess_refine_runner
# child. Not part of the public API.
_CHILD_FLAG = "--_agm-child-refine"

Group = Any
# (spec_dict, radius_used, retried_bool)
RunnerResult = Tuple[Dict[str, Any], float, bool]
Runner = Callable[[Group], RunnerResult]

_CELLID_KEYS = ("chd_cellid", "riv_cellid", "wel_cellid")

# Retry radii ``_real_refine_group`` walks through on a fallback (mirrors
# ``model_io_utils.refine_with_retry``'s default sequence). ``retried`` is
# DERIVED from ``refine_radius_used`` -- a run "retried" iff the radius that
# succeeded is not the FIRST radius here -- rather than plumbed separately
# through the freeze/subprocess IPC hop. This keeps a single source of truth
# instead of a manifest field that can silently drift out of sync with the
# spec (see ``_was_retried``).
RETRY_RADII = (70.0, 62.0, 78.0, 56.0, 84.0)


def _was_retried(radius_used: float) -> bool:
    """True iff *radius_used* differs from ``RETRY_RADII[0]`` -- i.e. the
    refinement fell back to a wider retry radius and is therefore NOT safe
    to freeze as a pinned artifact."""
    return not math.isclose(float(radius_used), RETRY_RADII[0])


def _canon_cellids(cellids) -> list:
    """Normalize a cellid sequence to a plain list of ``(int, int)`` tuples
    so equality is dtype-independent (``int`` vs ``np.integer``)."""
    return [tuple(int(x) for x in c) for c in cellids]


def _active_cell_count(spec: Dict[str, Any]) -> int:
    return int(np.count_nonzero(np.asarray(spec["idomain"])))


def _fail(group: Group, radius_used: Any = None, reason: str = "") -> Dict[str, Any]:
    """Build a FAIL result dict. ``radius_used`` is OPTIONAL: pass ``None``
    (never ``float('nan')``) when no real radius is available -- e.g. a
    runner-exception path that never got as far as reading a spec -- so
    that a NaN can never leak into a JSON report or a freeze call. When
    ``None`` the ``radius_used`` key is simply omitted."""
    result: Dict[str, Any] = {
        "status": "FAIL",
        "group": int(group),
        "reason": reason,
    }
    if radius_used is not None:
        result["radius_used"] = float(radius_used)
    return result


def run_group_determinism_check(
    group: Group, runner: Runner, *, reruns: int = 5
) -> Dict[str, Any]:
    """
    Rerun ``runner(group)`` ``reruns`` times and report whether the
    refinement is deterministic (safe to freeze as a pinned artifact).

    ``runner`` must return ``(spec_dict, radius_used, retried_bool)`` on
    each call. This function contains NO MODFLOW and NO subprocess -- it is
    a pure comparison over whatever the runner returns.

    A run is only reported PASS if, across every rerun:
      - ``retried`` is False (no run silently fell back to a wider radius);
      - ``radius_used`` is identical;
      - ``ncpl`` is identical;
      - the active-cell count (``sum(idomain != 0)``) is identical;
      - ``chd_cellid`` / ``riv_cellid`` / ``wel_cellid`` are identical
        (element-wise, order-sensitive);
      - ``well_cells`` is identical.

    Otherwise FAIL, naming the first divergence found.

    Parameters
    ----------
    group : Any
        Group identifier, passed through to ``runner`` and echoed back in
        the result.
    runner : callable
        ``runner(group) -> (spec_dict, radius_used, retried_bool)``.
    reruns : int, optional
        Number of times to call ``runner``. Default 5. Must be >= 1.

    Returns
    -------
    dict
        ``status`` ("PASS"/"FAIL"), ``group``, ``reason`` (empty on PASS),
        ``radius_used`` (from the first run), and ``reruns``.
    """
    if reruns < 1:
        raise ValueError(f"reruns must be >= 1, got {reruns!r}")

    runs = [runner(group) for _ in range(reruns)]
    for i, run in enumerate(runs):
        if not (isinstance(run, tuple) and len(run) == 3):
            raise ValueError(
                "runner(group) must return a 3-tuple "
                f"(spec, radius_used, retried); run {i} returned {run!r}"
            )

    spec0, radius0, _ = runs[0]
    radius0 = float(radius0)

    for i, (_spec, _radius, retried) in enumerate(runs):
        if retried:
            return _fail(
                group,
                radius0,
                f"run {i} reported a retried/fallback refinement "
                "(retried=True); a first-radius fallback is not safe to freeze",
            )

    for i, (_spec, radius, _retried) in enumerate(runs[1:], start=1):
        if float(radius) != radius0:
            return _fail(
                group,
                radius0,
                f"radius_used differs between run 0 ({radius0!r}) and "
                f"run {i} ({float(radius)!r})",
            )

    ncpl0 = int(spec0["ncpl"])
    active0 = _active_cell_count(spec0)
    for i, (spec, _radius, _retried) in enumerate(runs[1:], start=1):
        ncpl_i = int(spec["ncpl"])
        if ncpl_i != ncpl0:
            return _fail(
                group,
                radius0,
                f"ncpl differs between run 0 ({ncpl0}) and run {i} ({ncpl_i})",
            )

        active_i = _active_cell_count(spec)
        if active_i != active0:
            return _fail(
                group,
                radius0,
                "active cell count (idomain) differs between run 0 "
                f"({active0}) and run {i} ({active_i})",
            )

        for key in _CELLID_KEYS:
            if _canon_cellids(spec0[key]) != _canon_cellids(spec[key]):
                return _fail(
                    group,
                    radius0,
                    f"{key} differs between run 0 and run {i}",
                )

        wc0 = [int(c) for c in spec0["well_cells"]]
        wc_i = [int(c) for c in spec["well_cells"]]
        if wc0 != wc_i:
            return _fail(
                group,
                radius0,
                f"well_cells differs between run 0 and run {i}",
            )

    return {
        "status": "PASS",
        "group": int(group),
        "reason": "",
        "radius_used": radius0,
        "reruns": reruns,
    }


def _assert_gridprops_equal(a: Dict[str, Any], b: Dict[str, Any]) -> None:
    for key in ("ncpl", "nvert"):
        if int(a[key]) != int(b[key]):
            raise AssertionError(
                f"flow spec gridprops[{key!r}] differs: {a[key]!r} != {b[key]!r}"
            )

    va = np.asarray(a["vertices"], dtype=float)
    vb = np.asarray(b["vertices"], dtype=float)
    if va.shape != vb.shape or not np.array_equal(va, vb):
        raise AssertionError("flow spec gridprops 'vertices' differ")

    ca, cb = a["cell2d"], b["cell2d"]
    if len(ca) != len(cb):
        raise AssertionError(
            f"flow spec gridprops 'cell2d' row count differs: {len(ca)} != {len(cb)}"
        )
    for i, (ra, rb) in enumerate(zip(ca, cb)):
        ra_arr = np.asarray(ra, dtype=float)
        rb_arr = np.asarray(rb, dtype=float)
        if ra_arr.shape != rb_arr.shape or not np.array_equal(ra_arr, rb_arr):
            raise AssertionError(f"flow spec gridprops 'cell2d' row {i} differs")


def assert_flow_specs_equal(spec_a: Dict[str, Any], spec_b: Dict[str, Any]) -> None:
    """
    Raise unless *spec_a* and *spec_b* are exactly equal: every flat/BC
    array agrees element-wise (via ``np.array_equal``) and the ragged DISV
    ``gridprops`` (vertices + per-row ``cell2d``) agree exactly.

    Used to prove a freeze->load round trip (or two runner calls) reproduce
    a flow spec byte-for-byte, with no silent precision loss or reordering.
    No MODFLOW and no subprocess.

    Raises
    ------
    AssertionError
        Naming the first differing field, on any mismatch.
    """
    keys_a, keys_b = set(spec_a), set(spec_b)
    if keys_a != keys_b:
        raise AssertionError(
            "flow spec keys differ: only in a="
            f"{sorted(keys_a - keys_b)!r}, only in b={sorted(keys_b - keys_a)!r}"
        )

    _assert_gridprops_equal(spec_a["gridprops"], spec_b["gridprops"])

    for key in sorted(keys_a - {"gridprops"}):
        va, vb = spec_a[key], spec_b[key]

        if va is None or vb is None:
            if va != vb:
                raise AssertionError(f"flow spec field {key!r} differs: {va!r} != {vb!r}")
            continue

        if isinstance(va, str) or isinstance(vb, str):
            if va != vb:
                raise AssertionError(f"flow spec field {key!r} differs: {va!r} != {vb!r}")
            continue

        if key in _CELLID_KEYS:
            aa, ab = _canon_cellids(va), _canon_cellids(vb)
            if aa != ab:
                raise AssertionError(f"flow spec field {key!r} differs: {aa!r} != {ab!r}")
            continue

        aa, ab = np.asarray(va), np.asarray(vb)
        if aa.shape != ab.shape or not np.array_equal(aa, ab):
            raise AssertionError(
                f"flow spec field {key!r} differs (shape {aa.shape} vs {ab.shape})"
            )


# =============================================================================
# M2b-2: subprocess-isolated runner (parent/child IPC).
# =============================================================================

def _best_effort_versions() -> Dict[str, str]:
    """Best-effort tool versions for the freeze manifest. Never raises --
    an unimportable/odd package just gets recorded as ``'unavailable'``.

    Includes ``geos`` (the Triangle/shapely backend) and ``mf6`` alongside
    ``flopy``/``numpy`` -- these are the provenance fields the SIGILL study
    actually needs, since geos/mf6 versions are platform-dependent and
    implicated in the refinement crashes this manifest exists to diagnose.
    """
    versions: Dict[str, str] = {"python": sys.version.split()[0]}
    for name in ("flopy", "numpy"):
        try:
            mod = __import__(name)
            versions[name] = str(getattr(mod, "__version__", "unknown"))
        except Exception:
            versions[name] = "unavailable"

    try:
        import shapely

        versions["geos"] = ".".join(str(part) for part in shapely.geos_version)
    except Exception:
        versions["geos"] = "unavailable"

    try:
        import shutil

        exe = shutil.which("mf6") or os.path.expanduser(
            "~/.local/share/flopy/bin/mf6"
        )
        out = subprocess.run(
            [exe, "--version"], capture_output=True, text=True, timeout=10
        )
        versions["mf6"] = out.stdout.strip().splitlines()[0] if out.stdout else "unavailable"
    except Exception:
        versions["mf6"] = "unavailable"

    return versions


def group_refine_points(group: Group, *, config_path: Any = None) -> List[Tuple[float, float]]:
    """Derive the refine-mesh anchor points for *group* from its configured
    injection/extraction doublet.

    The frozen mesh must be finely resolved AROUND THE GROUP'S ACTUAL WELLS
    (needed for drawdown / capture-zone analysis downstream), not at an
    arbitrary interior point unrelated to the doublet. Reads
    ``case_config_transport.yaml`` via ``case_utils.lint_transport_config``
    and returns the doublet's two well coordinates.

    Reruns of the SAME group are reproducible for
    ``run_group_determinism_check`` because the doublet coordinates in the
    config are fixed -- no randomness is involved.

    Pure data lookup: no MODFLOW, no geopandas/Triangle, no subprocess --
    safe to unit test without loading the mother model.

    Parameters
    ----------
    group : Any
        Group id (int-like), passed straight through to
        ``case_utils.lint_transport_config(groups=[group])``.
    config_path : str or Path, optional
        Override for the transport case config path (see
        ``case_utils.lint_transport_config``); mainly for tests.

    Returns
    -------
    list of (easting, northing) float tuples
        Exactly two points: the injection well, then the extraction well.
    """
    import case_utils as cu

    doublet = cu.lint_transport_config(config_path=config_path, groups=[group])[group]["doublet"]
    return [
        (float(doublet["injection_easting"]), float(doublet["injection_northing"])),
        (float(doublet["extraction_easting"]), float(doublet["extraction_northing"])),
    ]


def _real_refine_group(
    group: Group, *, mother_model: Path, work_dir: Path
) -> RunnerResult:
    """Real (non-fake) refinement for *group*.

    Loads the mother GWF simulation, derives the refine-mesh anchor points
    for *group* from its configured injection/extraction doublet (see
    ``group_refine_points`` -- reruns of the SAME group are reproducible
    because the doublet coordinates are fixed in config, not randomly
    sampled), and retries ``generate_refined_grid`` +
    ``assemble_gwf_from_spec`` over a small set of refine radii (mirrors
    ``model_io_utils.refine_with_retry``, but keeps the plain-array spec --
    rather than discarding it after assembly -- so it can be frozen).

    HUB-ONLY in practice (loads MF6 + geopandas + Triangle); the local test
    suite never reaches this function -- it drives the ``AGM_FAKE_SPEC_NPZ``
    / ``AGM_FAKE_CHILD_SIGNAL`` child hooks instead.
    """
    import flopy
    import geopandas as gpd

    import case_utils as cu

    work_dir.mkdir(parents=True, exist_ok=True)

    # The group's configured injection/extraction doublet (transport case
    # config) -- passed through to ``generate_refined_grid`` so the frozen
    # mesh reflects this group's actual wells, not an arbitrary no-well model.
    doublet = cu.lint_transport_config(groups=[group])[group]["doublet"]
    pumping_rate = doublet["pumping_rate_m3_d"]
    well_data = [
        (doublet["injection_easting"], doublet["injection_northing"], pumping_rate),
        (doublet["extraction_easting"], doublet["extraction_northing"], -pumping_rate),
    ]

    sim = flopy.mf6.MFSimulation.load(sim_ws=str(mother_model), verbosity_level=0)
    gwf = sim.get_model()
    heads = gwf.output.head().get_data().flatten()

    gis_dir = Path(mother_model).parent / "gis"
    boundary_gdf = gpd.read_file(gis_dir / "limmat_model_boundary.gpkg")
    river_all = gpd.read_file(gis_dir / "AV_Gewasser_-OGD.gpkg")
    river_gdf = river_all[
        river_all["GEWAESSERNAME"].isin(["Limmat", "Sihl"])
        & river_all.intersects(boundary_gdf.geometry.iloc[0])
    ]

    # Refine AROUND THE DOUBLET, not an arbitrary interior point -- the
    # capture-zone/drawdown analysis downstream needs the mesh finely
    # resolved at the group's actual wells.
    refine_points = group_refine_points(group)

    last_exc: Any = None
    for k, radius in enumerate(RETRY_RADII):
        try:
            spec = mio.generate_refined_grid(
                gwf, boundary_gdf=boundary_gdf, river_gdf=river_gdf,
                refine_points=refine_points, head_array=heads, refine_radius=radius,
                well_data=well_data,
            )
            mio.assemble_gwf_from_spec(
                spec, workspace=work_dir / f"rg{k}", sim_name=f"g{group}",
            )
            return spec, float(radius), (k > 0)
        except Exception as e:  # Triangle abort / MF6 nonconvergence, etc.
            last_exc = e
            continue
    raise RuntimeError(
        f"group {group}: refinement failed at all radii; last error: {last_exc!r}"
    )


def _child_refine_main(argv) -> int:
    """Child-process entry point (invoked via the private ``_CHILD_FLAG``).

    Produces a flow spec -- either the ``AGM_FAKE_SPEC_NPZ`` fixture (test
    hook, no MODFLOW) or a real refinement -- and freezes it to
    ``--out-npz`` so the parent can load it back via
    ``model_io_utils.load_flow_spec``. Honours ``AGM_FAKE_CHILD_SIGNAL``
    (test hook: self-kill by signal, simulating an uncatchable SIGILL)
    before anything else runs.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", required=True, type=int)
    parser.add_argument("--mother-model", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--out-npz", required=True)
    args = parser.parse_args(argv)

    fake_signal = os.environ.get("AGM_FAKE_CHILD_SIGNAL")
    if fake_signal:
        os.kill(os.getpid(), int(fake_signal))
        return 1  # unreachable when the signal is fatal; kept for clarity

    fake_npz = os.environ.get("AGM_FAKE_SPEC_NPZ")
    if fake_npz:
        spec = mio.load_flow_spec(fake_npz, verify=True)
    else:
        # The child no longer computes/stores `retried` -- it just produces
        # the spec (the spec already carries `refine_radius_used`, which is
        # the single source of truth the parent derives `retried` from; see
        # `_was_retried`). The retry bookkeeping `_real_refine_group` returns
        # is ignored here.
        spec, _radius_used, _retried = _real_refine_group(
            int(args.group),
            mother_model=Path(args.mother_model),
            work_dir=Path(args.work_dir),
        )

    mio.freeze_flow_spec(
        spec, Path(args.out_npz),
        caller_fields={"group": int(args.group)},
    )
    return 0


# Default bound on how long a single subprocess_refine_runner child (real
# MF6/Triangle refinement) may run before it is killed and the group is
# recorded as a FAILED run -- a hang in Triangle/MF6 must never hang the
# whole orchestration. CLI-configurable via --child-timeout.
DEFAULT_CHILD_TIMEOUT_S = 1800.0


def subprocess_refine_runner(
    group: Group, *, mother_model: Any, work_dir: Any,
    timeout_s: float = DEFAULT_CHILD_TIMEOUT_S,
) -> RunnerResult:
    """Run the refinement for *group* in a FRESH Python subprocess and
    return ``(spec, radius_used, retried)`` via a freeze -> load IPC hop.

    Isolating each attempt in its own process means a SIGILL (an
    uncatchable fatal signal out of Triangle/MF6 -- see
    ``model_io_utils.refine_with_retry``) kills only the child; this
    function surfaces that -- or any nonzero exit -- as a normal Python
    exception instead of taking the parent process down.

    The child is launched as the leader of a fresh process group
    (``start_new_session=True``, mirroring
    ``case_validation._run_stage_subprocess``). If it does not finish within
    *timeout_s*, the WHOLE process group is killed (``os.killpg`` +
    ``SIGKILL``) -- not just the direct child -- so a grandchild (e.g. a
    hung ``mf6``/Triangle binary spawned by the child) can never be leaked
    past the timeout, and a ``RuntimeError`` is raised so the caller records
    this group as FAILED instead of hanging forever.

    Honours two child-side test hooks so the IPC path is exercisable with
    NO MODFLOW (see module docstring): ``AGM_FAKE_SPEC_NPZ`` and
    ``AGM_FAKE_CHILD_SIGNAL``. These are read from the current process
    environment and inherited by the child (``env=None`` default inherits
    the parent's environment).

    Parameters
    ----------
    group : Any
        Group identifier passed through to the child.
    mother_model : str or Path
        Coarse/calibrated MF6 simulation workspace the child refines from.
    work_dir : str or Path
        Scratch directory for the child (created if missing); also holds
        the temporary IPC ``.npz`` + manifest.
    timeout_s : float, optional
        Seconds to wait for the child before killing its process group.
        Default ``DEFAULT_CHILD_TIMEOUT_S`` (1800s).

    Returns
    -------
    (spec, radius_used, retried)

    Raises
    ------
    RuntimeError
        If the child exits nonzero, dies by signal, or exceeds *timeout_s*
        (naming the exit code / signal / timeout respectively).
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_npz = work_dir / f"_child_group{group}_spec.npz"

    cmd = [
        sys.executable, str(Path(__file__).resolve()), _CHILD_FLAG,
        "--group", str(group),
        "--mother-model", str(mother_model),
        "--work-dir", str(work_dir),
        "--out-npz", str(out_npz),
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    )

    try:
        _stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass  # process (group) already gone
        proc.communicate()  # reap, avoid a zombie
        raise RuntimeError(
            f"subprocess_refine_runner: child for group {group} exceeded its "
            f"{timeout_s:g}s --child-timeout and was killed (process group "
            "SIGKILL); this group is recorded as FAILED"
        ) from None

    if proc.returncode < 0:
        signum = -proc.returncode
        try:
            signame = signal.Signals(signum).name
        except ValueError:
            signame = str(signum)
        raise RuntimeError(
            f"subprocess_refine_runner: child for group {group} died by "
            f"signal {signum} ({signame}); stderr:\n{stderr}"
        )
    if proc.returncode != 0:
        raise RuntimeError(
            f"subprocess_refine_runner: child for group {group} exited with "
            f"nonzero return code {proc.returncode}; stderr:\n{stderr}"
        )

    spec = mio.load_flow_spec(out_npz, verify=True)
    radius_used = float(spec["refine_radius_used"])
    # DERIVED, not read back from the manifest: a run "retried/fell back"
    # iff the succeeding radius differs from the FIRST radius in
    # RETRY_RADII. This is a single source of truth over the manifest field
    # the child used to freeze (which could silently default away an
    # unsafe retried=True on a load, or simply drift out of sync).
    retried = _was_retried(radius_used)
    return spec, radius_used, retried


# =============================================================================
# M2b-2: freeze-on-PASS to <meshes_dir>/group<N>_flow.npz + manifest.
# =============================================================================

def freeze_group_flow_artifact(
    spec: Dict[str, Any], *, group: Group, meshes_dir: Any, radius_used: float
) -> Dict[str, Any]:
    """Freeze *spec* to ``<meshes_dir>/group<N>_flow.npz`` (+ manifest) --
    the canonical PINNED artifact ``model_io_utils.load_pinned_flow_model``
    reads back.

    Callers MUST only invoke this after a determinism PASS
    (``run_group_determinism_check``); this function does not itself gate
    on that -- it just refuses to write anything for an invalid spec
    (``model_io_utils.freeze_flow_spec`` calls ``validate_flow_spec`` before
    writing).

    Parameters
    ----------
    spec : dict
        Flow spec to freeze (validated internally; see
        ``model_io_utils.validate_flow_spec``).
    group : Any
        Group identifier; selects the ``group<N>_flow.npz`` filename.
    meshes_dir : str or Path
        Destination directory (created if missing).
    radius_used : float
        The refine radius that produced *spec*; recorded in the manifest.

    Returns
    -------
    dict
        The manifest that was written (includes ``group``,
        ``platform.node()``, best-effort tool ``versions``, and
        ``radius_used`` alongside the array hashes).

    Raises
    ------
    KeyError, ValueError
        If *spec* is missing a required field or is internally
        inconsistent (propagated from ``model_io_utils.freeze_flow_spec`` /
        ``validate_flow_spec``) -- nothing is written in that case.
    """
    meshes_dir = Path(meshes_dir)
    npz_path = meshes_dir / f"group{int(group)}_flow.npz"
    caller_fields = {
        "group": int(group),
        "node": platform.node(),
        "radius_used": float(radius_used),
        "versions": _best_effort_versions(),
    }
    return mio.freeze_flow_spec(spec, npz_path, caller_fields=caller_fields)


# =============================================================================
# M2b-3: CLI -- run selected groups through the orchestration above and emit
# a machine-readable per-group JSON report.
# =============================================================================

def _parse_groups(spec: str) -> List[int]:
    """Parse ``--groups`` into a sorted, de-duplicated list of group ids,
    restricted to the canonical group domain.

    Delegates the comma-list / ``lo-hi`` INCLUSIVE range syntax -- and the
    huge-range-span sanity cap (e.g. rejecting a typo like ``"0-999999999"``)
    -- to ``case_validation.parse_groups_spec``, the same parser the
    instructor validation harness CLI uses, so the two tools can never drift
    on what a valid ``--groups`` spec means. On top of that shared parser,
    every resulting id is additionally checked against
    ``case_validation.CANONICAL_GROUPS`` (0-8) -- this script's frozen
    artifacts only ever cover that closed set of case-study groups, so an
    out-of-domain id (e.g. ``"9"``) is rejected here too, not just an
    oversized range.

    Raises
    ------
    ValueError
        If *spec* is empty/malformed (from ``parse_groups_spec``) or selects
        any id outside the canonical 0-8 domain.
    """
    if not spec or not spec.strip():
        raise ValueError("--groups must not be empty")

    groups = cv.parse_groups_spec(spec)
    if not groups:
        raise ValueError(f"--groups produced no group ids from {spec!r}")

    out_of_domain = sorted(g for g in groups if g not in cv.CANONICAL_GROUPS)
    if out_of_domain:
        raise ValueError(
            f"--groups {spec!r} selected group id(s) outside the canonical "
            f"domain {cv.CANONICAL_GROUPS}: {out_of_domain}"
        )
    return groups


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Instructor-side determinism-check / freeze orchestration for "
            "per-group PINNED flow artifacts. Runs each selected group's "
            "refinement in a subprocess-isolated runner, reruns it to check "
            "for exact reproducibility, and (optionally) freezes a PASSing "
            "group to <meshes-dir>/group<N>_flow.npz."
        ),
    )
    parser.add_argument(
        "--groups", required=True,
        help="Group ids to check, as a comma list and/or 'lo-hi' ranges, "
             "e.g. '0-8' or '0,3,5'.",
    )
    parser.add_argument(
        "--reruns", type=int, default=5,
        help="Number of reruns per group for the determinism check (default 5).",
    )
    parser.add_argument(
        "--meshes-dir", required=True,
        help="Destination directory for frozen group<N>_flow.npz artifacts "
             "(and the default location for subprocess scratch work).",
    )
    parser.add_argument(
        "--freeze", action="store_true",
        help="Freeze the canonical spec to --meshes-dir for every group that "
             "PASSES determinism. Without this flag nothing is written.",
    )
    parser.add_argument(
        "--out", required=True,
        help="Path to write the machine-readable per-group JSON report.",
    )
    parser.add_argument(
        "--require-green-style", action="store_true",
        help="Exit nonzero if any selected group fails the determinism check "
             "(otherwise a failing group is reported but the run exits 0).",
    )
    parser.add_argument(
        "--mother-model",
        default=os.environ.get(
            "MODEL_WS",
            os.path.expanduser("~/applied_groundwater_modelling_data/limmat/calibration"),
        ),
        help="Calibrated MF6 workspace each group refines from -- the "
             "05f_calibration.ipynb output (see model_io_utils.ensure_flow_model()); "
             "HUB-only real runs, ignored under the AGM_FAKE_SPEC_NPZ test hook. "
             "Must NOT default to the uncalibrated notebook4_model, or pinned "
             "artifacts would lock in an uncalibrated K/head field.",
    )
    parser.add_argument(
        "--work-dir", default=None,
        help="Scratch directory for subprocess runner children "
             "(default: <meshes-dir>/_work).",
    )
    parser.add_argument(
        "--child-timeout", type=float, default=DEFAULT_CHILD_TIMEOUT_S,
        help="Seconds to wait for a single subprocess_refine_runner child "
             "(one refinement attempt) before killing its process group and "
             f"recording that group as FAILED (default {DEFAULT_CHILD_TIMEOUT_S:g}s). "
             "Prevents a hung MF6/Triangle child from hanging the whole run.",
    )
    return parser


def main(argv=None) -> int:
    """CLI entry point: check determinism (and optionally freeze) each
    ``--groups`` group, writing a per-group JSON report to ``--out``.

    Returns
    -------
    int
        2 if ``--groups`` is malformed or selects an id outside the
        canonical 0-8 domain; otherwise 0 unless ``--require-green-style``
        is set and at least one selected group failed its determinism
        check, in which case 1.
    """
    args = _build_arg_parser().parse_args(argv)
    try:
        groups = _parse_groups(args.groups)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    meshes_dir = Path(args.meshes_dir)
    work_dir = Path(args.work_dir) if args.work_dir else meshes_dir / "_work"

    report: List[Dict[str, Any]] = []
    any_fail = False

    for group in groups:
        calls: List[RunnerResult] = []

        def runner(g: Group, _calls=calls) -> RunnerResult:
            result = subprocess_refine_runner(
                g, mother_model=args.mother_model, work_dir=work_dir,
                timeout_s=args.child_timeout,
            )
            _calls.append(result)
            return result

        try:
            entry = run_group_determinism_check(group, runner, reruns=args.reruns)
        except Exception as e:
            # The runner raised before any spec/radius was ever obtained --
            # record the failure WITHOUT a fabricated radius (never NaN: it
            # would corrupt the JSON report and must never reach `freeze`).
            entry = _fail(group, None, f"runner raised {type(e).__name__}: {e}")
        else:
            entry = dict(entry)

        entry["node"] = platform.node()
        entry["versions"] = _best_effort_versions()

        frozen = False
        if entry["status"] == "PASS" and args.freeze:
            spec = calls[0][0]
            manifest = freeze_group_flow_artifact(
                spec, group=group, meshes_dir=meshes_dir, radius_used=entry["radius_used"],
            )
            entry["manifest"] = manifest
            frozen = True
        entry["frozen"] = frozen

        if entry["status"] != "PASS":
            any_fail = True
        report.append(entry)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str))

    return 1 if (args.require_green_style and any_fail) else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == _CHILD_FLAG:
        sys.exit(_child_refine_main(sys.argv[2:]))
    else:
        sys.exit(main())
