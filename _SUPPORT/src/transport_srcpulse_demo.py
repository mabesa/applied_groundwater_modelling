"""
Finite-pulse SRC (mass-loading) spill -> capture demo for MODFLOW 6 GWT.

Self-contained teaching demo (UNGRADED) for the transport track (charter milestone
M2).  Builds and runs a coupled steady-GWF / transient-GWT simulation on a
corridor-refined DISV grid:

    * A representative geothermal DOUBLET (spare concession ``b010191``) is active
      for FLOW ONLY -- a clean injection well (+Q) and an extraction / monitoring
      well (-Q) shape a forced-gradient flow field.  No solute rides the wells.
    * A finite-duration point SPILL is placed ~90 m UPGRADIENT of the extraction
      well (upgradient computed from the local regional flow direction).  The
      solute is introduced with the MODFLOW 6 **SRC** package (mass loading,
      g/d) rather than a fixed concentration (CNC).  The pulse is ON for the
      first stress period (duration ``pulse_days``) and OFF thereafter, so the
      plume migrates freely toward the pumping well.

Units: the flow model runs in metres / day, so mg/L == g/m^3 and SRC mass rates
are in **grams per day**.  A released mass ``M`` [g] over a pulse ``T`` [d] gives a
per-cell loading ``smassrate = M / (n_src_cells * T)`` [g/d].

Diagnostics returned: breakthrough at the extraction well (mg/L), peak + arrival,
a mass-balance table from the binary GWT budget (SRC in, well out, boundary out,
storage, % imbalance), a solubility guardrail (emergent source-cell concentration
vs a stated solubility), and the grid Peclet numbers Pe_L / Pe_T on the corridor.

OWNERSHIP: this module imports the shared grid utility ``model_io_utils`` only.
It does NOT import ``transport_base_model`` -- the corridor radius-walk retry
and other helpers are re-implemented inline here. The one exception (T1 S4,
``DESIGN_DOCS/T1_S4_brief.md`` v2) is Courant sizing: this module now owns the
CANONICAL ``courant_nstp`` calculator (``_courant_nstp_canonical``, below),
and ``transport_base_model.courant_nstp`` imports and delegates to it (never
the other way -- an import edge in that direction would grow this module's
own frozen source-closure fingerprint, ``test_t1_src_closure.py::DEMO_EXPECTED``).

Author: Applied Groundwater Modelling Course (transport track, M2 SRC demo)
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import math
import os
import platform
import shutil
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
import geopandas as gpd
import flopy
from shapely.geometry import LineString, Point, Polygon

import model_io_utils as mio  # shared grid utility (grid + property interpolation)


# ---------------------------------------------------------------------------
# LOCKED transport parameters (replicated from transport_base_model.LOCKED_PARAMS)
# ---------------------------------------------------------------------------
LOCKED_PARAMS: Dict[str, Any] = {
    "alh": 10.0,            # longitudinal dispersivity [m]
    "ath1": 1.0,            # transverse horizontal dispersivity [m]
    "diffc": 8.64e-5,       # effective molecular diffusion [m^2/d] (= 1e-9 m^2/s)
    "porosity": 0.20,       # effective porosity n_e [-]
    "scheme": "TVD",        # ADV weighting
    "xt3d_off": False,      # XT3D default-on for DSP
    "refined_cell_size": 10.0,
    "base_cell_size": 50.0,
    "time_units": "DAYS",
}


# ---------------------------------------------------------------------------
# T1 S3a (DESIGN_DOCS/T1_S3_brief.md v3): mesh identity + content-addressed
# workspaces. `MeshSpec` parameterises the grid; `CourantSpec` is DECLARED
# ONLY (brief Section 2) -- S4 (below, `_courant_nstp_canonical`) canonicalises
# the two legacy `courant_nstp` bodies behind explicit `legacy_base` /
# `legacy_srcpulse` profiles but does not wire `CourantSpec` in; S8 does, as
# `exp_v1`. `_courant_nstp_canonical` itself reads no `LOCKED_PARAMS` -- each
# caller passes its own floor reference explicitly.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MeshLevel:
    """One refinement level: a target cell size and (for an inner level) the
    radius it applies within. ``radius_m=None`` means "the outermost level,
    scoped by the retry ladder" -- today's single-level default."""
    cell_size: float
    radius_m: Optional[float] = None


@dataclass(frozen=True)
class MeshSpec:
    """What the GRID is (declared). Today is exactly ``MeshSpec()`` -- see
    ``_resolve_mesh_spec`` for how the legacy ``refine_radii=`` argument
    folds into this default, and ``mesh_spec_hash`` / ``mesh_hash`` below for
    the two identities this spec feeds (brief Section 2.1).

    ``levels`` is order-significant (outer -> inner) and a tuple so a graded
    (multi-level) spec is EXPRESSIBLE -- but S3a only BUILDS a single level;
    see ``_require_single_level``. Building more than one level is S3b, which
    needs a signature extending contract A4 to ``model_io_utils.py`` /
    ``disv_grid_utils.py`` (brief Section 7) -- neither is authorised here.
    """
    base_cell_size: float = 50.0
    levels: Tuple[MeshLevel, ...] = (MeshLevel(cell_size=10.0),)
    retry_radii: Tuple[float, ...] = (70.0, 62.0, 78.0, 56.0, 84.0)


@dataclass(frozen=True)
class CourantSpec:
    """What the TIME STEPPING is -- owned by S4/S8. Declared here only, so
    those milestones have somewhere to put the sliver floor; S3a does not
    read or wire this in (no Courant behaviour change in this step, per the
    brief's explicit constraint)."""
    sliver_floor_frac: float = 0.4
    cr_target: float = 0.9
    nstp_cap: int = 2000


# Sentinel: distinguishes "refine_radii not passed" from "refine_radii passed
# its own default value" for the mesh_spec/refine_radii ValueError rule
# (brief Section 3.1) -- a concrete default tuple could not be told apart
# from an explicit call carrying that same tuple.
_UNSET = object()


def _resolve_mesh_spec(*, refine_radii: Any = _UNSET,
                       mesh_spec: Optional["MeshSpec"] = None) -> "MeshSpec":
    """The ONE authoritative ``MeshSpec`` default/resolution factory (brief
    Section 3.1), living beside ``LOCKED_PARAMS``.

    ``refine_radii=`` predates ``MeshSpec`` and remains accepted on both
    public builders (``build_srcpulse_demo``, ``build_prt_capture``) as well
    as ``refine_corridor``; it folds into the default ``MeshSpec`` (only
    ``retry_radii`` is overridden -- ``base_cell_size`` and ``levels`` stay
    at their defaults). Supplying BOTH ``refine_radii`` and ``mesh_spec`` is
    a ``ValueError``, never a silent precedence rule.
    """
    refine_radii_given = refine_radii is not _UNSET
    if refine_radii_given and mesh_spec is not None:
        raise ValueError(
            "pass either refine_radii= or mesh_spec=, not both: refine_radii "
            "predates MeshSpec and folds into its default retry_radii, so "
            "supplying both would leave precedence silently undefined "
            "(DESIGN_DOCS/T1_S3_brief.md Section 3.1)")
    if mesh_spec is not None:
        return mesh_spec
    if refine_radii_given:
        return MeshSpec(retry_radii=tuple(float(r) for r in refine_radii))
    return MeshSpec()


def _require_single_level(spec: "MeshSpec") -> "MeshLevel":
    """S3a validates but does not BUILD more than one level (brief Section
    7: S3a scope). A graded (multi-level) ``MeshSpec`` is expressible -- the
    shape already admits it -- but constructing it needs per-level
    ``targets=`` scoping and changes inside ``model_io_utils.py`` /
    ``disv_grid_utils.py``, neither authorised by contract A4. That is S3b,
    which needs its own signature; this never silently builds one level."""
    if len(spec.levels) != 1:
        raise NotImplementedError(
            f"MeshSpec.levels carries {len(spec.levels)} levels; this build "
            "only supports a single level. Multi-level mesh CONSTRUCTION is "
            "milestone S3b (DESIGN_DOCS/T1_S3_brief.md Section 7) -- it "
            "needs a signature extending contract A4 to model_io_utils.py "
            "and disv_grid_utils.py, which S3a does not have.")
    return spec.levels[0]


# ---------------------------------------------------------------------------
# Canonical, LOSSLESS serialisation for the mesh identities (brief Section
# 2.2). Deliberately NOT T0.0 Section 4's FLOAT_FORMAT: that formatter is a
# 12-significant-digit LOSSY quantisation built to make a COMPARISON
# tolerant of last-bit solver noise -- an IDENTITY needs the opposite (two
# distinct cell sizes must never collide), so this uses ``float.hex()``
# (exact IEEE-754) instead. Sorted keys, order-significant sequences,
# non-finite values REJECTED, digest sha256, first 32 hex chars.
# ---------------------------------------------------------------------------
def _canonical_float(x: float) -> str:
    if not math.isfinite(x):
        raise ValueError(
            f"non-finite value is not allowed in an identity payload: {x!r} "
            "(brief Section 2.2: non-finite values REJECTED)")
    return float(x).hex()


def _canonical_value(v: Any) -> Any:
    """Recursively convert ``v`` into a JSON-safe canonical form: floats
    become ``float.hex()`` strings, dataclasses become
    ``{field: canonical(value)}``, tuples/lists stay ORDER-preserving JSON
    arrays, dict values are canonicalised (key SORTING is
    ``json.dumps(..., sort_keys=True)``'s job at serialisation time, not
    this function's)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        return _canonical_float(v)
    if isinstance(v, (int, str)):
        return v
    if v is None:
        return None
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: _canonical_value(getattr(v, f.name))
                for f in dataclasses.fields(v)}
    if isinstance(v, (tuple, list)):
        return [_canonical_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _canonical_value(x) for k, x in v.items()}
    raise TypeError(f"cannot canonicalise value of type {type(v)!r}: {v!r}")


def _canonical_json(obj: Any) -> str:
    return json.dumps(_canonical_value(obj), sort_keys=True, separators=(",", ":"))


def _identity_digest(obj: Any) -> str:
    """sha256 of the canonical JSON form, first 32 hex chars (brief
    Section 2.2)."""
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()[:32]


def mesh_spec_hash(spec: "MeshSpec") -> str:
    """The DECLARED identity: the ``MeshSpec`` fields as written (brief
    Section 2.1). For provenance / artifact records -- NOT for keying a
    workspace or cache (the retry ladder means a declared spec does not
    determine the resulting mesh; see ``mesh_hash``)."""
    return _identity_digest(spec)


def _file_content_hash(path: Union[str, Path]) -> str:
    """sha256 hex digest of a file's raw bytes -- the GIS content identity
    (brief Section 2.1: ``mesh_hash`` folds in ``model_boundary`` and
    ``rivers``). Content, not path: a byte-identical file at a different
    location hashes the same; an edited file at the SAME path hashes
    differently."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _gis_source_paths() -> Tuple[Path, Path]:
    """Local file paths for the two GIS layers that shape the mesh: the
    model boundary (sets the domain) and the rivers (change refined RIV
    allocation, hence velocity and Courant sizing) -- content-hashed into
    ``mesh_hash`` so an edit to either file changes the effective mesh
    identity even though it changes no source byte. ``download_named_file``
    is a cache hit whenever the files are already local (both layers are
    also fetched by ``_load_calibrated_flow``), so this is a cheap local
    path lookup, not an extra download in the common case."""
    from data_utils import download_named_file
    boundary_path = Path(download_named_file(name="model_boundary", data_type="gis"))
    rivers_path = Path(download_named_file(name="rivers", data_type="gis"))
    return boundary_path, rivers_path


def mesh_hash(spec: "MeshSpec", *, winning_radius: float,
             boundary_path: Union[str, Path],
             rivers_path: Union[str, Path]) -> str:
    """The EFFECTIVE identity (brief Section 2.1): the declared spec PLUS
    the winning retry radius PLUS the GIS content hashes. This -- not
    ``mesh_spec_hash`` -- is what keys every workspace and cache: the retry
    ladder means a declared spec does not by itself determine the resulting
    mesh, and the boundary/river geometry shape it too."""
    if not math.isfinite(winning_radius):
        raise ValueError(f"winning_radius must be finite (got {winning_radius!r})")
    payload = {
        "mesh_spec": spec,
        "winning_radius_m": float(winning_radius),
        "gis": {
            "model_boundary_sha256": _file_content_hash(boundary_path),
            "rivers_sha256": _file_content_hash(rivers_path),
        },
    }
    return _identity_digest(payload)

# Solver policy (replicated from transport_base_model)
_GWF_NEWTON = "NEWTON"
# ⚠️ dvclose stays at 1e-4/1e-5 -- lecturer decision 2026-08-27, made against
# measurement rather than in the abstract.
#
# Relaxing to 1e-3/1e-4 (what `model_io_utils` uses for the REFGRID build, and
# what PR #113 established a refined GWF needs) DOES make a 2 m mesh converge:
# the coupled sim currently fails at SP1/TS1 where the refgrid build succeeds.
# But it moves this model's CONCENTRATIONS by up to 2.3e-04 relative --
# `breakthrough[13]`, which sits at 1.010 mg/L, essentially on the 1 mg/L
# compliance threshold. The gate's concentration tolerance is 1e-5 (T0.0
# Sec 4), so the change is inadmissible, and the tolerance was kept rather
# than widened: precision near the exceedance threshold is where it buys
# something physical rather than numerical.
#
# Consequence, recorded so it is not rediscovered: the 2 m identity is NOT
# reachable by relaxing this solver. Graded refinement is the remaining route.
_GWF_IMS = dict(complexity="COMPLEX", outer_maximum=1000, inner_maximum=100,
                outer_dvclose=1e-4, inner_dvclose=1e-5, linear_acceleration="BICGSTAB")
# 🔴 COMPLEXITY drives the LINEAR PRECONDITIONER, and it is the only knob that makes the
# transport solve converge on finely refined corridors (C1 **A17**, lecturer signature
# 2026-08-27).  Under MODERATE the GWT solution ("Solution 2") fails at sp1/ts1 for
# corridors at or below 1 m while the FLOW solve converges normally -- raising GWT
# outer/inner iteration budgets does not help, so this is preconditioning, not iteration
# count.  Evidence: DOCUMENTATION/contracts/evidence/t2/S10_SUB2M_SOLVER.md.
#
# ⚠️ NOT the solver route rejected by A16.  That route relaxed the dvclose TOLERANCES and
# moved concentrations 2.3e-04.  This changes the preconditioner with tolerances UNCHANGED
# (1e-6 / 1e-7): the converged answer is the same answer, reached by a different path, and
# it is measured -- peak_mgL agrees to 7.3e-10 across the two preconditioners at 10 m.
_GWT_IMS = dict(complexity="COMPLEX", linear_acceleration="BICGSTAB",
                outer_dvclose=1e-6, inner_dvclose=1e-7)

# Representative spare doublet b010191 (LV95) -- FLOW ONLY, not assigned to any group.
INJ_XY: Tuple[float, float] = (2681297.0, 1248917.0)   # injection well  (Rückgabe)
ABS_XY: Tuple[float, float] = (2681487.0, 1248981.0)   # extraction well (Entnahme)
DOUBLET_Q: float = 1370.0                              # doublet rate [m^3/d]
SPILL_UPGRADIENT_M: float = 90.0                       # spill offset upgradient of ABS [m]

_MF6_FALLBACK = os.path.expanduser("~/.local/share/flopy/bin/mf6")


# ---------------------------------------------------------------------------
# result container
# ---------------------------------------------------------------------------
@dataclass
class SrcPulseDemo:
    """Diagnostics from the SRC finite-pulse spill -> capture demo."""
    times: np.ndarray                       # output times [d]
    breakthrough: np.ndarray                # C at extraction well [mg/L]
    peak_mgL: float                         # peak breakthrough [mg/L]
    arrival_day: float                      # time of peak [d]
    mass_balance: Dict[str, float]          # cumulative mass terms [g] + % imbalance
    solubility_ok: bool                     # emergent C < solubility ?
    emergent_C_mgL: float                   # emergent source-cell concentration [mg/L]
    solubility_mgL: float                   # stated solubility [mg/L]
    solubility_margin: float                # solubility / emergent_C
    PeL_min: float
    PeL_max: float
    PeT_min: float
    PeT_max: float
    mass_g: float
    pulse_days: float
    total_days: float
    smassrate_gpd: float                    # per-cell SRC loading [g/d]
    src_cells: List[int]
    ext_cell: int
    inj_cell: int
    spill_xy: Tuple[float, float]
    alpha_L: float                          # effective longitudinal dispersivity [m]
    alpha_T: float                          # effective transverse dispersivity [m] (alpha_L / 10)
    R: float                                # retardation factor [-]
    rho_b: float                            # dry bulk density [kg/m^3]
    Kd: float                               # distribution coefficient [m^3/kg] (0.0 when R==1)
    lam: float                              # first-order decay rate [1/d] (0.0 = no decay)
    # ---- T1 S2 (DESIGN_DOCS/T1_S2_brief.md v2): pre-authorised payload fields,
    # placed AFTER lam (the last non-default field) -- a defaulted, init-enabled
    # field inserted earlier would raise "non-default argument follows default
    # argument" (brief Section 3.2). No behaviour change: both sit at their
    # identity default until a later milestone (S9b/S9c) makes them real.
    sink_support_m: float = 0.0             # [m] extraction-support disc radius;
                                             # 0.0 == today's behaviour exactly (the
                                             # whole rate on one nearest-centroid cell)
    # `t_peak` is the T1/T2 lattice alias of `arrival_day` (contract A7). It is
    # declared `init=False` and derived in `__post_init__` -- NOT assigned at a
    # call site and NOT a `@property` (the T0 gate harness enumerates the payload
    # via `dataclasses.fields()`, which a property is invisible to). Passing
    # `t_peak=` to the constructor therefore raises TypeError rather than being
    # silently accepted/corrected: a silent override would mask a missed JAG
    # transition later, when `t_peak` legitimately diverges from `arrival_day`
    # (brief Section 3.1, codex S2 review #2).
    t_peak: float = field(init=False)
    meta: Dict[str, Any] = field(default_factory=dict)
    locked: Dict[str, Any] = field(default_factory=lambda: dict(LOCKED_PARAMS))

    def __post_init__(self) -> None:
        # The lattice alias: exactly `arrival_day`, cast to `float` (a no-op for
        # an already-float value, and NaN-preserving when arrival_day is NaN --
        # see the "never arrives" guard in build_srcpulse_demo).
        self.t_peak = float(self.arrival_day)


# ---------------------------------------------------------------------------
# inline helpers (re-implemented; NOT imported from transport_base_model)
# ---------------------------------------------------------------------------
def _cellsize(mg, ncpl) -> np.ndarray:
    """Representative cell edge length sqrt(area) per cell."""
    return np.array([np.sqrt(Polygon(mg.get_cell_vertices(i)).area) for i in range(ncpl)])


def _run_failure_tail(ws: Union[str, Path], buf, n: int = 40) -> str:
    """Assemble a readable failure message from the MF6 listing tails."""
    ws = Path(ws)
    chunks = []
    for name in ("mfsim.lst", "gwf.lst", "gwt.lst"):
        p = ws / name
        if p.exists():
            try:
                lines = p.read_text(errors="replace").splitlines()
            except OSError:
                continue
            if lines:
                chunks.append(f"--- {name} (last {n} lines) ---\n" + "\n".join(lines[-n:]))
    buf_tail = "\n".join(buf[-12:]) if buf else ""
    if buf_tail.strip():
        chunks.append("--- run_simulation buffer (tail) ---\n" + buf_tail)
    return "\n\n".join(chunks) if chunks else "(no listing output found)"


def _corridor_points(a_xy, b_xy, step: float = 40.0, pad: float = 40.0):
    """Evenly-spaced refine points along a->b (padded past both ends)."""
    a, b = np.array(a_xy, float), np.array(b_xy, float)
    L = float(np.hypot(*(b - a)))
    u = (b - a) / L
    n = max(int((L + 2 * pad) // step) + 1, 2)
    return [tuple(a + s * u) for s in np.linspace(-pad, L + pad, n)], u, L


def _refine_with_retry(coarse_gwf, boundary_gdf, river_gdf, refine_points, head_array,
                       case_ws: Union[str, Path], *,
                       mesh_spec: "MeshSpec",
                       boundary_path: Union[str, Path],
                       rivers_path: Union[str, Path],
                       sim_name: str = "rg") -> Tuple[Dict[str, Any], float, str]:
    """Corridor refine, walking ``mesh_spec.retry_radii`` to dodge the cs=10
    SIGILL / Triangle-precision abort (macOS arm64 / mf6 6.7.0).

    T1 S3a (brief Section 2.1/3): each candidate radius is tried directly in
    its OWN content-addressed workspace, ``case_ws / f"refgrid_{candidate}"``,
    where ``candidate`` is ``mesh_hash(mesh_spec, winning_radius=<this
    radius>, ...)`` computed FOR THAT radius -- so the winning build lands
    exactly at the path its effective identity names (no rename step), and a
    failed candidate's SIGILL debris is left in its own directory, never
    colliding with anything else.

    Re-implemented inline (charter constraint: do NOT import
    transport_base_model). Returns (build_refined_gwf_model result dict, the
    radius actually used, and its mesh_hash).
    """
    level = _require_single_level(mesh_spec)
    case_ws = Path(case_ws)
    last_exc: Optional[Exception] = None
    for rr in mesh_spec.retry_radii:
        candidate_hash = mesh_hash(mesh_spec, winning_radius=float(rr),
                                   boundary_path=boundary_path, rivers_path=rivers_path)
        ws = case_ws / f"refgrid_{candidate_hash}"
        try:
            res = mio.build_refined_gwf_model(
                coarse_gwf, boundary_gdf=boundary_gdf, river_gdf=river_gdf,
                refine_points=refine_points, head_array=head_array,
                workspace=str(ws), refine_radius=float(rr),
                base_cell_size=mesh_spec.base_cell_size,
                refined_cell_size=level.cell_size,
                sim_name=sim_name)
            return res, float(rr), candidate_hash
        except Exception as e:  # SIGILL / Triangle abort surfaces here
            last_exc = e
            continue
    raise RuntimeError(
        f"corridor refinement failed at all radii {tuple(mesh_spec.retry_radii)}; "
        f"last error: {last_exc!r}")


# ---------------------------------------------------------------------------
# T1 S4 (DESIGN_DOCS/T1_S4_brief.md v2): canonical `courant_nstp` calculator.
#
# Collapses the two pre-S4 duplicates -- this module's own private
# `_courant_nstp` (below) and `transport_base_model.courant_nstp` -- into ONE
# implementation, selected by `profile`. It lives HERE (not in
# `transport_base_model`) because this module already owns `CourantSpec`
# (declared above, for S4/S8) and its exact source is pinned byte-for-byte by
# `test_t1_src_closure.py::DEMO_EXPECTED` -- an import edge FROM here TO
# `transport_base_model` would grow that frozen closure. The reverse edge
# (`transport_base_model` importing this module) does not, since nothing pins
# `transport_base_model`'s own import set.
#
# `profile` admitted ONLY the two legacy IDs in S4. T1 S8
# (`DESIGN_DOCS/T1_S8_brief.md` v2) adds a THIRD profile, `exp_v1` -- the
# corrected policy: floor keyed off the finest *intended* cell size (a
# `MeshSpec`, not `LOCKED_PARAMS["refined_cell_size"]`), source/well cells
# INCLUDED (`exclusions` accepted but ignored), the reported Cr measured as
# the maximum over the ENTIRE original unmasked corridor (not just the
# selection that sized `nstp`), and `nstp_cap` RAISING instead of silently
# absorbing. `exp_v1` inherits NEITHER legacy profile's degenerate-input
# fallback (see `_courant_nstp_corrected`'s own docstring) and is dispatched
# to a SEPARATE function below rather than folded into this one, so this
# function's own source stays the frozen S4 shape (`test_t1_courant_profiles
# .py::test_canonical_has_no_corrected_policy_surface` pins that literally).
# This function itself never warns and never reports a cap flag: both stay
# caller-owned exactly as today (`build_doublet_base` has no cap flag;
# `build_spill_scenario` sets `cr_capped` from `Cr > 1.001` without a
# caution message; this module's own wrapper sets `cr_capped = nstp >=
# nstp_cap` and raises a RuntimeWarning -- all unchanged, at the call
# sites, not here). `exp_v1` is not wired into any default call in S8 --
# it ships the capability; T2 uses it.
# ---------------------------------------------------------------------------
_COURANT_LEGACY_PROFILES = ("legacy_base", "legacy_srcpulse")
# T1 S8: the one corrected-policy id, kept as a module-level constant (not a
# literal inside `_courant_nstp_canonical`'s own body -- see the structural
# pin noted above) and folded into the admitted-profile enum.
_COURANT_CORRECTED_PROFILE = "exp_v1"
_COURANT_PROFILES = _COURANT_LEGACY_PROFILES + (_COURANT_CORRECTED_PROFILE,)


def _courant_nstp_canonical(v_cells: np.ndarray, size_cells: np.ndarray, mask: np.ndarray,
                            total_time: float, *, exclusions: Sequence[int] = (),
                            cr_target: float = 0.9, nstp_cap: int,
                            sliver_floor_frac: float = 0.4, refined_cell_size: float,
                            mesh_spec: Optional["MeshSpec"] = None,
                            profile: str) -> Tuple[int, float, float, Dict[str, float]]:
    """Size fixed time steps from a per-cell Courant number Cr_i = v_i*dt/ds_i.

    Takes the ORIGINAL (unmasked) corridor `mask` plus `exclusions` (cell ids
    to drop -- source and/or well cells, per caller) rather than a pre-masked
    array: a pre-masked array cannot be inverted, and S8 needs to know what was
    excluded so it can stop excluding it. `mask` is copied, never mutated; the
    legacy (excluded) mask is reconstructed as `mask` minus `exclusions`, and
    BOTH the floor-filtered selection and `diag["ds_true_min"]` are computed
    from that reconstructed mask -- reproducing each pre-S4 call site exactly.

    `refined_cell_size` is the CALLER's own floor reference (each module reads
    its own `LOCKED_PARAMS["refined_cell_size"]` and passes it in): this
    function owns no `LOCKED_PARAMS` read, so the two modules' locked-parameter
    copies (a divergence hazard on record, C1 S0.2) stay decoupled even though
    the calculator itself is now shared.

    Profile behaviour (verified byte-for-byte against both pre-S4 bodies):

    * `legacy_base` -- mirrors `transport_base_model.py`'s pre-S4 body. No
      empty-selection fallback (`ratio.max()` on an empty selection raises); no
      zero/negative-critical fallback (`critical == 0` raises at division; a
      negative `critical` can yield a negative `nstp`, or a zero `nstp` that
      raises at `dt = total_time / nstp`); `nstp` is NOT clamped to >= 1.
    * `legacy_srcpulse` -- mirrors this module's pre-S4 private body. An empty
      floor-filtered selection falls back to the whole (reconstructed) mask;
      `critical <= 0` (zero OR negative) returns the cap with
      `Cr = critical * dt` instead of raising; `nstp` is clamped to >= 1.

    A third, corrected profile is admitted too (T1 S8) but its policy is
    implemented in a sibling function, not here -- see the module comment
    just above `_COURANT_LEGACY_PROFILES`. `mesh_spec` is accepted by this
    signature only to be threaded through to that sibling; the two profiles
    above never read it.
    """
    if profile not in _COURANT_PROFILES:
        raise ValueError(
            f"unknown courant_nstp profile {profile!r}; expected one of "
            f"{_COURANT_PROFILES}")
    if profile not in _COURANT_LEGACY_PROFILES:
        return _courant_nstp_corrected(
            v_cells, size_cells, mask, total_time, exclusions=exclusions,
            cr_target=cr_target, nstp_cap=nstp_cap,
            sliver_floor_frac=sliver_floor_frac, mesh_spec=mesh_spec)

    # Copy, never mutate, the caller's mask; reconstruct the legacy
    # (pre-S4 pre-masked) selection as mask-minus-exclusions.
    legacy_mask = np.array(mask, dtype=bool, copy=True)
    for cell in exclusions:
        legacy_mask[int(cell)] = False

    floor = sliver_floor_frac * refined_cell_size
    sel = legacy_mask & (size_cells >= floor)

    if profile == "legacy_srcpulse":
        if not sel.any():                       # degenerate: fall back to whole mask
            sel = legacy_mask
        ratio = v_cells[sel] / size_cells[sel]
        critical = float(ratio.max())
        j = np.where(sel)[0][int(np.argmax(ratio))]
        if critical <= 0.0:
            # degenerate zero/negative-velocity field on the selected cells:
            # cr_target / critical would ZeroDivisionError (or size dt off a
            # backwards signal). Fall back to the step cap -- there is no
            # forward advective signal to size dt against.
            nstp = max(nstp_cap, 1)
            dt = total_time / nstp
            diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                        ds_true_min=float(size_cells[legacy_mask].min()), floor=floor)
            return nstp, dt, critical * dt, diag
        dt_need = cr_target / critical
        nstp = min(int(np.ceil(total_time / dt_need)), nstp_cap)
        nstp = max(nstp, 1)
        dt = total_time / nstp
        diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                    ds_true_min=float(size_cells[legacy_mask].min()), floor=floor)
        return nstp, dt, critical * dt, diag

    # profile == "legacy_base": no empty-selection fallback, no zero/negative
    # fallback, no >= 1 clamp -- preserve the raises exactly.
    ratio = v_cells[sel] / size_cells[sel]
    critical = float(ratio.max())
    dt_need = cr_target / critical
    nstp = min(int(np.ceil(total_time / dt_need)), nstp_cap)
    dt = total_time / nstp
    j = np.where(sel)[0][int(np.argmax(ratio))]
    diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                ds_true_min=float(size_cells[legacy_mask].min()), floor=floor)
    return nstp, dt, critical * dt, diag


# ---------------------------------------------------------------------------
# T1 S8 (DESIGN_DOCS/T1_S8_brief.md v2): the corrected `courant_nstp` policy,
# profile `"exp_v1"`. Kept out of `_courant_nstp_canonical`'s own body
# deliberately -- that function's frozen S4-era structural pin
# (test_t1_courant_profiles.py::test_canonical_has_no_corrected_policy_surface)
# asserts several corrected-policy tokens are ABSENT from its source; this
# sibling function is dispatched to from there but is not itself scanned by
# that pin, so both the S4 shape and the S8 policy can be true at once.
# `_courant_nstp_canonical` still owns no `LOCKED_PARAMS` read, and neither
# does this function (brief Section 2.4): the floor reference comes from
# `mesh_spec`, passed in by the caller.
# ---------------------------------------------------------------------------
def _courant_nstp_corrected(v_cells: np.ndarray, size_cells: np.ndarray, mask: np.ndarray,
                            total_time: float, *, exclusions: Sequence[int] = (),
                            cr_target: float = CourantSpec().cr_target,
                            nstp_cap: int = CourantSpec().nstp_cap,
                            sliver_floor_frac: float = CourantSpec().sliver_floor_frac,
                            mesh_spec: Optional["MeshSpec"] = None
                            ) -> Tuple[int, float, float, Dict[str, float]]:
    """The `"exp_v1"` policy (brief Sections 1-3), four corrections over both
    legacy profiles:

    1. The sliver floor is keyed off the FINEST INTENDED cell size --
       ``min(level.cell_size for level in mesh_spec.levels)`` -- not a single
       achieved ``refined_cell_size``. ``mesh_spec`` is REQUIRED here (unlike
       the legacy profiles, which take a plain ``refined_cell_size`` float);
       an empty/missing ``mesh_spec`` or a non-finite/nonpositive
       ``cell_size`` on any level raises.
    2. ``exclusions`` is accepted (not an error) but IGNORED: source and well
       cells are included in the floor-filtered selection that sizes `nstp`.
    3. The reported Courant number is the MEASURED MAXIMUM over every cell of
       the original (unmasked) ``mask`` -- including cells the sliver floor
       drops from selection -- not just the cells selection kept. Selection
       determines `nstp`; this measures the resulting field over the whole
       corridor.
    4. ``nstp_cap`` RAISES (naming the cap and the `nstp` that would have been
       needed) instead of silently truncating.

    Degenerate inputs inherit NEITHER legacy profile's fallback (brief
    Section 3.2 -- both are preserved defects, not policies): an empty
    floor-filtered selection raises rather than falling back to the whole
    mask (that would defeat correction 1), and a nonpositive/non-finite
    `critical` (e.g. a zero-or-negative-velocity selection) raises rather
    than returning the cap (that would contradict correction 4). Every raise
    here names its condition explicitly and is distinct from every other,
    including the cap error -- unlike `legacy_base`/`legacy_srcpulse`, which
    take a plain `refined_cell_size` float and never validate `mesh_spec`.

    The three scalar defaults above come from `CourantSpec()` (S3a declared
    it for exactly this purpose; S4 did not wire it in) rather than being
    re-hardcoded, so a future edit to `CourantSpec`'s own defaults cannot
    silently diverge from this profile's.
    """
    if mesh_spec is None or not getattr(mesh_spec, "levels", ()):
        raise ValueError(
            "courant_nstp profile 'exp_v1' requires mesh_spec=MeshSpec(...) "
            "with at least one MeshLevel -- unlike legacy_base/legacy_srcpulse, "
            f"which take a single refined_cell_size directly; got mesh_spec={mesh_spec!r}")
    level_sizes = [float(level.cell_size) for level in mesh_spec.levels]
    if any((not math.isfinite(s)) or s <= 0.0 for s in level_sizes):
        raise ValueError(
            "courant_nstp profile 'exp_v1': every mesh_spec.levels[*].cell_size "
            f"must be finite and > 0; got {level_sizes!r}")

    corridor = np.array(mask, dtype=bool, copy=True)   # never mutate the caller's mask
    if not corridor.any():
        raise ValueError("courant_nstp profile 'exp_v1': mask has no active corridor cells")

    corridor_sizes = size_cells[corridor]
    if not np.all(np.isfinite(corridor_sizes)) or np.any(corridor_sizes <= 0.0):
        raise ValueError(
            "courant_nstp profile 'exp_v1': size_cells contains a nonpositive "
            "or non-finite entry within the corridor")
    corridor_v = v_cells[corridor]
    if not np.all(np.isfinite(corridor_v)):
        raise ValueError(
            "courant_nstp profile 'exp_v1': v_cells contains a non-finite "
            "entry within the corridor")

    floor = sliver_floor_frac * min(level_sizes)
    sel = corridor & (size_cells >= floor)          # exclusions ignored by design (correction 2)
    if not sel.any():
        raise ValueError(
            "courant_nstp profile 'exp_v1': the floor-filtered selection is "
            f"empty (every corridor cell is below sliver_floor_frac*min(level."
            f"cell_size)={floor:g}); unlike legacy_srcpulse this does not fall "
            "back to the whole mask (that would defeat the corrected floor policy)")

    ratio = v_cells[sel] / size_cells[sel]
    critical = float(ratio.max())
    if not math.isfinite(critical) or critical <= 0.0:
        raise ValueError(
            "courant_nstp profile 'exp_v1': the selected cells' maximum v/size "
            f"ratio is nonpositive or non-finite (critical={critical!r}); unlike "
            "legacy_srcpulse this does not fall back to nstp_cap (that would "
            "contradict the cap-raises correction)")
    j = np.where(sel)[0][int(np.argmax(ratio))]

    dt_need = cr_target / critical
    nstp_needed = int(np.ceil(total_time / dt_need))
    if nstp_needed > nstp_cap:
        raise ValueError(
            f"courant_nstp profile 'exp_v1': nstp_cap={nstp_cap} is smaller than "
            f"the nstp={nstp_needed} needed to reach cr_target={cr_target:g} "
            f"(binding rate={critical:g}/d); raise nstp_cap or relax cr_target")
    nstp = max(nstp_needed, 1)
    dt = total_time / nstp

    # The measured maximum over EVERY corridor cell (correction 3) -- not just
    # `sel`, the floor-filtered selection that sized `nstp` above.
    cr_reported = float((corridor_v * dt / corridor_sizes).max())

    diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                ds_true_min=float(corridor_sizes.min()), floor=floor)
    return nstp, dt, cr_reported, diag


def _courant_nstp(v_cells: np.ndarray, size_cells: np.ndarray, mask: np.ndarray,
                  total_time: float, cr_target: float = 0.9, nstp_cap: int = 2000,
                  sliver_floor_frac: float = 0.4, *,
                  exclusions: Sequence[int] = ()) -> Tuple[int, float, float, Dict[str, float]]:
    """Thin wrapper (T1 S4): delegates to `_courant_nstp_canonical` with
    `profile='legacy_srcpulse'`. `mask` is the ORIGINAL (unmasked) corridor
    mask; pass excluded cell ids (source + well cells) via `exclusions`.

    Slivers below sliver_floor_frac * refined_cell_size are excluded (they carry
    negligible pore volume but would force an impractically tiny dt).
    """
    return _courant_nstp_canonical(
        v_cells, size_cells, mask, total_time, exclusions=exclusions,
        cr_target=cr_target, nstp_cap=nstp_cap, sliver_floor_frac=sliver_floor_frac,
        refined_cell_size=float(LOCKED_PARAMS["refined_cell_size"]),
        profile="legacy_srcpulse")


def _budget_has_spdis(cgwf) -> bool:
    """True iff the loaded model's saved budget carries the DATA-SPDIS record."""
    try:
        recs = cgwf.output.budget().get_unique_record_names(decode=True)
    except Exception:
        return False  # no/unreadable .cbc -> treat as missing so we regenerate
    return any("DATA-SPDIS" in str(r) for r in recs)


def _ensure_spdis(csim, cgwf, flow_ws, exe):
    """Guarantee the coarse flow model's budget carries ``DATA-SPDIS``.

    The transport track reads the specific-discharge recarray
    (``cgwf.output.budget().get_data(text='DATA-SPDIS')``) to place the spill and
    Courant-size the time steps. A pre-computed / archived flow model whose NPF
    was saved without ``save_specific_discharge`` lacks that record, so loading it
    on a fresh JupyterHub (or any stale ``<data>/calibration`` cache) raises
    "The specified text string is not in the budget file."

    We repair it in place: enable the specific-discharge output flags and re-run
    the (steady-state, single-period) model — a few-second regeneration that
    persists in the workspace, so it is a one-time cost per workspace. Returns a
    freshly reloaded ``(csim, cgwf)`` so downstream output handles read the new
    ``.cbc``.
    """
    if _budget_has_spdis(cgwf):
        return csim, cgwf

    mname = cgwf.name
    cgwf.npf.save_specific_discharge = True
    cgwf.npf.save_flows = True
    try:
        cgwf.npf.save_saturation = True
    except Exception:
        pass  # older grids may not expose the option; SPDIS only needs the two above

    try:
        csim.write_simulation(silent=True)
        ok, buf = csim.run_simulation(silent=True)
    except Exception as exc:
        raise RuntimeError(
            "The calibrated flow model's budget lacks specific discharge "
            "(DATA-SPDIS), which the transport track needs, and it could not be "
            f"regenerated (is the workspace writable and mf6 available?).\n"
            f"  workspace: {flow_ws}\n  mf6: {exe}\n(underlying error: {exc})"
        ) from exc
    if not ok:
        tail = "\n".join(buf[-15:]) if buf else ""
        raise RuntimeError(
            "Re-running the calibrated flow model to add specific discharge "
            f"(DATA-SPDIS) failed.\n  workspace: {flow_ws}\n  mf6: {exe}\n{tail}"
        )

    # reload so cached output handles point at the freshly written .cbc
    csim = flopy.mf6.MFSimulation.load(sim_ws=str(flow_ws), exe_name=exe, verbosity_level=0)
    return csim, csim.get_model(mname)


def _load_calibrated_flow():
    """Load the 05f-calibrated coarse flow model + GIS (boundary, Limmat/Sihl)."""
    from data_utils import download_named_file
    flow_ws = mio.ensure_flow_model()
    # prefer an mf6 already on PATH; fall back to the flopy-bin install location.
    exe = shutil.which("mf6") or _MF6_FALLBACK
    csim = flopy.mf6.MFSimulation.load(sim_ws=str(flow_ws), exe_name=exe, verbosity_level=0)
    cgwf = csim.get_model("limmat_valley")
    # Archived / stale flow models may lack DATA-SPDIS in their budget; the
    # transport track requires it, so regenerate it once if missing.
    csim, cgwf = _ensure_spdis(csim, cgwf, flow_ws, exe)
    boundary = gpd.read_file(download_named_file(name="model_boundary", data_type="gis"))
    rivers = gpd.read_file(download_named_file(name="rivers", data_type="gis"))
    rivers = rivers[rivers["GEWAESSERNAME"].isin(["Limmat", "Sihl"])
                    & rivers.intersects(boundary.geometry.iloc[0])]
    return cgwf, boundary, rivers, exe


def _default_case_ws() -> Path:
    from data_utils import get_default_data_folder
    return Path(get_default_data_folder()) / "transport_srcpulse_demo"


# ---------------------------------------------------------------------------
# Transitive `_SUPPORT/src` source-closure fingerprint (T1 S1;
# DESIGN_DOCS/T1_S1_brief.md). Shared by this module's ``_src_sha()`` and
# ``transport_prt_capture``'s -- ONE implementation so the two cannot drift.
#
# The scan is AST-based over the ENTIRE module, at any nesting depth: local
# dependencies deferred inside a function (e.g. ``model_io_utils`` importing
# ``disv_grid_utils`` only inside ``build_refined_gwf_model``) must still be
# discovered, or a source edit there would leave every warm cache valid while
# the grid moved underneath it -- the exact bug class this repo has already
# shipped once. Static on source TEXT: never import a candidate module to see
# its imports -- importing executes module-level code and drags in FloPy.
# ---------------------------------------------------------------------------
def _closure_import_names(path: Path) -> set[str]:
    """First-dotted-segment import names ``path`` references, at any AST depth.

    ``Import`` -> each ``alias.name``'s first dotted segment. ``ImportFrom`` ->
    ``node.module``'s first segment. Aliases (``as y``) and imported symbols do
    not change the edge.

    Raises ``ValueError`` on a relative import (``node.level > 0``) or a
    dynamic import (``__import__`` / ``importlib``) -- neither occurs in this
    closure today, and guessing at their target would be worse than refusing.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read source-closure member {path}: {exc}") from exc
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise ValueError(f"cannot parse source-closure member {path}: {exc}") from exc

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "__import__":
            raise ValueError(
                f"{path}: dynamic import via '__import__' is not supported by "
                "the source-closure scan (refusing to guess its target)")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top == "importlib":
                    raise ValueError(
                        f"{path}: dynamic import via 'importlib' is not "
                        "supported by the source-closure scan (refusing to "
                        "guess its target)")
                names.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                raise ValueError(
                    f"{path}: relative import (level={node.level}) is not "
                    "supported by the source-closure scan (refusing to guess "
                    "its target)")
            if node.module:
                top = node.module.split(".")[0]
                if top == "importlib":
                    raise ValueError(
                        f"{path}: dynamic import via 'importlib' is not "
                        "supported by the source-closure scan (refusing to "
                        "guess its target)")
                names.add(top)
    return names


def _resolve_src_closure(root_path: Union[str, Path]) -> dict[str, Path]:
    """Transitive ``_SUPPORT/src`` closure of ``root_path``, as ``{name: Path}``.

    A name is IN the closure iff it resolves to ``_SUPPORT/src/<name>.py``;
    stdlib and third-party names are out of scope. Transitive, with a
    ``visited`` set so a cycle among local modules terminates instead of
    recursing forever -- a cycle is not itself an error.
    """
    src_dir = Path(__file__).resolve().parent
    root = Path(root_path).resolve()
    visited: dict[str, Path] = {}
    stack = [root]
    while stack:
        current = stack.pop()
        stem = current.stem
        if stem in visited:
            continue
        visited[stem] = current
        for name in _closure_import_names(current):
            candidate = src_dir / f"{name}.py"
            if candidate.is_file() and candidate.stem not in visited:
                stack.append(candidate)
    return visited


def _framed_closure_digest(members) -> str:
    """SHA1 (first 16 hex chars) of a length-framed, sorted record sequence.

    Each record is ``(repo-relative POSIX path, sha256 of that file's bytes)``,
    sorted by path, with every field length-prefixed. FRAMED, not concatenated:
    plain concatenation of path-bytes + file-bytes has no boundary marker, so a
    byte moved from the end of one member's content to the start of the next's
    would leave the concatenated stream -- and the digest -- unchanged.
    """
    repo_root = Path(__file__).resolve().parents[2]
    records: list[tuple[str, bytes]] = []
    for member in members:
        path = Path(member).resolve()
        try:
            rel = path.relative_to(repo_root).as_posix()
        except ValueError as exc:
            raise ValueError(
                f"source-closure member {path} is outside repo root "
                f"{repo_root}") from exc
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ValueError(
                f"cannot read source-closure member {path}: {exc}") from exc
        records.append((rel, hashlib.sha256(content).digest()))
    records.sort(key=lambda r: r[0])

    h = hashlib.sha1()
    for rel, digest in records:
        rel_b = rel.encode("utf-8")
        h.update(len(rel_b).to_bytes(4, "big"))
        h.update(rel_b)
        h.update(len(digest).to_bytes(4, "big"))
        h.update(digest)
    return h.hexdigest()[:16]


def _src_closure_digest(root_path: Union[str, Path]) -> str:
    """Framed digest (see ``_framed_closure_digest``) of the transitive
    ``_SUPPORT/src`` closure of ``root_path`` (see ``_resolve_src_closure``)."""
    closure = _resolve_src_closure(root_path)
    return _framed_closure_digest(closure.values())


def _src_sha() -> str:
    """SHA of every module SOURCE this model is built from.

    The TRANSITIVE ``_SUPPORT/src`` closure of this module -- not a hand-picked
    file list. Covers THIS module (the doublet, the spill rule, the SRC/MST
    wiring, the Courant sizing) and every local module it imports, directly or
    indirectly, at ANY nesting depth -- including deferred imports inside
    functions, e.g. ``model_io_utils`` deferring ``disv_grid_utils`` (which
    BUILDS the refined grid) inside ``build_refined_gwf_model``. An edit
    anywhere in that closure changes this model just as surely as an edit here
    does, and without covering it that edit would leave every warm cache valid
    while the grid moved underneath it -- the exact bug class this repo has
    already shipped once. See ``_resolve_src_closure`` / ``_framed_closure_digest``.
    """
    return _src_closure_digest(Path(__file__))


# ---------------------------------------------------------------------------
# PUBLIC builders -- the visible, teachable model-construction API.
#
# ``build_srcpulse_demo`` below is exactly these composed in order:
#     load_limmat_flow -> refine_corridor
#       -> (pilot)      new_sim -> add_flow_model -> add_transport_model -> couple_and_run
#       -> (production) new_sim -> add_flow_model -> add_transport_model -> couple_and_run
# The messy corridor-refinement SIGILL retry stays hidden inside
# ``refine_corridor``; every FloPy package call is the verbatim, real construction
# a notebook can render and read.
# ---------------------------------------------------------------------------
def load_limmat_flow():
    """Load the 05f-calibrated coarse **Limmat valley** GWF + GIS.

    Thin public wrapper over ``_load_calibrated_flow``.  Returns
    ``(cgwf, boundary_gdf, rivers_gdf, exe)``: the coarse Limmat GWF model, the
    model-boundary polygon, the Limmat/Sihl river lines, and the resolved mf6
    executable path.
    """
    return _load_calibrated_flow()


# ---------------------------------------------------------------------------
# T1 S5 (DESIGN_DOCS/T1_S5_brief.md v3, C1 A11): fixed physical source
# footprint. Replaces the single nearest-centroid `src_cells` selection with
# an AREA-WEIGHTED DISC apportioned across every active layer-0 cell it
# intersects, so the applied source's support is a fixed PHYSICAL region
# (radius `footprint_radius_m`, centred on the spill point) rather than one
# mesh-dependent cell.
#
# `footprint_radius_m == 0.0` is the frozen SENTINEL and the default
# everywhere in this module: it takes an explicit branch reproducing pre-S5
# behaviour byte-for-byte -- the same `argmin` nearest-cell selection, the
# same single-cell `src_cells`, the same
# `smassrate = mass_g / (1 * pulse_days)`. No disc geometry is built at the
# sentinel; `_disc_footprint_areas` below is never called for it.
#
# The frozen rule (brief Sec 1/2/3.3), for a positive radius:
#   a_i    = area(cell_i INTERSECT disc)
#   rate_i = (M / T) * a_i / sum(a)
#   cells emitted SORTED ASCENDING by cell index
#   sum(rate_i) == M/T, asserted to 1e-9 relative
#   an incomplete disc (not fully covered by eligible cells) RAISES -- never
#   a silent renormalisation
#
# Geometry is computed ONCE, in `refine_corridor` (which has the mesh but
# not mass_g/pulse_days), and stored in the returned grid bundle
# (`footprint_areas_m2`, aligned with `src_cells`). `_footprint_rates`
# (called once mass_g/pulse_days are known, by `add_transport_model` and
# `build_srcpulse_demo`) apportions the mass across that ALREADY-COMPUTED
# geometry -- it never re-solves the disc-cell intersection.
#
# `smassrate_gpd` (the SrcPulseDemo payload field) keeps its pre-S5
# expression VERBATIM: `mass_g / (n_src * pulse_days)`. With unequal
# per-cell rates this is the ARITHMETIC MEAN per-cell rate -- true by
# construction, since `sum(rate_i) == M/T` -- and it is NEVER used to build
# a positive-radius SRC record; only `_footprint_rates`'s per-cell rates
# are. T0_0's Sec 2.5 makes a new payload field or `meta` key a failure
# edge, so the per-cell apportionment itself is recorded nowhere in this
# module -- it belongs in the evidence artifact (S13's
# `t1_evidence_artifact.SourceFootprintRecord`), built by a CALLER from the
# plain data this module returns. This module does not import
# `t1_evidence_artifact`: doing so would grow `_src_sha()`'s transitive
# `_SUPPORT/src` closure (`test_t1_src_closure.py::DEMO_EXPECTED`, frozen).
# ---------------------------------------------------------------------------
_FOOTPRINT_ALGORITHM_ID = "area_weighted_disc_v1"
_FOOTPRINT_QUAD_SEGS = 64
#: Brief Sec 3.3 "Coverage failure": area(disc - union(eligible cells)) >
#: 1e-6 * area(disc) -> raise.
_FOOTPRINT_COVERAGE_TOL_REL = 1e-6
#: Brief Sec 3.3 "Rate-sum assertion": |sum(rate_i) - M/T| <= 1e-9 * M/T.
_FOOTPRINT_RATE_SUM_TOL_REL = 1e-9


def _validate_footprint_radius(radius_m: float) -> None:
    """Brief Sec 3.3 'Radius validation': negative or non-finite -> raise."""
    if not math.isfinite(radius_m):
        raise ValueError(f"footprint_radius_m must be finite (got {radius_m!r})")
    if radius_m < 0.0:
        raise ValueError(f"footprint_radius_m must be >= 0 (got {radius_m!r})")


def _footprint_cell_polygons(mg, ncpl: int,
                             idomain: Optional[np.ndarray]) -> List[Optional[Polygon]]:
    """Layer-0 DISV cell polygons, `None` for an inactive cell (`idomain <=
    0`) -- brief Sec 3.3 'Eligible cells: the active layer-0 DISV cell
    polygons'. Same `Polygon(mg.get_cell_vertices(i))` convention as
    `_cellsize` (`:363`)."""
    polys: List[Optional[Polygon]] = []
    for i in range(int(ncpl)):
        if idomain is not None and int(idomain[i]) <= 0:
            polys.append(None)
            continue
        polys.append(Polygon(mg.get_cell_vertices(i)))
    return polys


def _disc_footprint_areas(mg, ncpl: int, idomain: Optional[np.ndarray],
                          centre_xy: Tuple[float, float], radius_m: float, *,
                          disc_label: str = "source footprint disc",
                          ) -> Tuple[List[int], List[float], float, float]:
    """T1 S5's frozen area-weighted footprint geometry (brief Sec 3.3):
    intersect a disc of `radius_m` centred on `centre_xy` -- Shapely
    `Point(...).buffer(radius_m, quad_segs=64)` -- with every active
    layer-0 DISV cell polygon.

    Returns `(cells, areas_m2, disc_area_m2, covered_area_m2)`. `cells` is
    SORTED ASCENDING by cell index (guaranteed by iterating cells 0..ncpl-1
    in order) with `areas_m2` the matching NONZERO intersection areas -- a
    tangent/zero-area touch contributes nothing and is EXCLUDED from
    `cells` (brief Sec 3.3 'Zero-area touch'). Raises `ValueError` if the
    disc is not, within `_FOOTPRINT_COVERAGE_TOL_REL`, fully covered by the
    eligible cells -- a disc extending outside the domain is an error,
    never a silent renormalisation (brief Sec 3.3 'Coverage failure').

    Callers must validate `radius_m` (`_validate_footprint_radius`) and
    must not call this at the `radius_m == 0.0` sentinel -- see the module
    section banner above.

    `disc_label` (T1 S9a, `DESIGN_DOCS/T1_S9a_brief.md` v2 exit criterion
    14) is the noun phrase the coverage-failure message opens with --
    keyword-only, message-only, defaulting to this function's original S5
    wording so every existing (positional) call site is byte-for-byte
    unchanged. S9a's sink wrapper passes `disc_label="sink footprint disc"`
    so the raised text names a sink, not a source.
    """
    disc = Point(float(centre_xy[0]), float(centre_xy[1])).buffer(
        float(radius_m), quad_segs=_FOOTPRINT_QUAD_SEGS)
    disc_area = float(disc.area)
    bx0, by0, bx1, by1 = disc.bounds
    polys = _footprint_cell_polygons(mg, ncpl, idomain)

    cells: List[int] = []
    areas: List[float] = []
    covered_area = 0.0
    for i, poly in enumerate(polys):
        if poly is None or poly.is_empty:
            continue
        px0, py0, px1, py1 = poly.bounds
        if px1 < bx0 or px0 > bx1 or py1 < by0 or py0 > by1:
            continue  # bounding boxes disjoint -> polygons cannot overlap
        a = float(poly.intersection(disc).area)
        covered_area += a
        if a <= 0.0:
            continue  # tangent / zero-area touch: contributes nothing (Sec 3.3)
        cells.append(i)
        areas.append(a)
    assert cells == sorted(cells)  # ascending by construction (iterated 0..ncpl-1)

    if disc_area - covered_area > _FOOTPRINT_COVERAGE_TOL_REL * disc_area:
        missing = disc_area - covered_area
        raise ValueError(
            f"{disc_label} (radius_m={radius_m!r}, centre_xy={centre_xy!r}) "
            f"is not fully covered by the mesh's active layer-0 cells: "
            f"{missing:.6g} m^2 of {disc_area:.6g} m^2 uncovered "
            f"({(missing / disc_area if disc_area else float('nan')):.3%}) -- a disc "
            "extending outside the domain is an error, never a silent "
            "renormalisation (DESIGN_DOCS/T1_S5_brief.md Sec 3.3)")

    return cells, areas, disc_area, covered_area


def _apportion_rates(areas: Sequence[float], total_rate: float) -> List[float]:
    """T1 S5's frozen apportionment (brief Sec 1/3.3): `rate_i = (M / T) *
    area_i / sum(area)`. Raises `ValueError` if the total intersection area
    is not positive (nothing to apportion across), and `AssertionError` if
    the resulting per-cell rates do not sum back to `total_rate` within
    `_FOOTPRINT_RATE_SUM_TOL_REL` (brief Sec 3.3's rate-sum assertion).
    """
    total_area = float(math.fsum(areas))
    if not (total_area > 0.0):
        raise ValueError(
            f"source footprint has non-positive total intersection area "
            f"(got {total_area!r}); cannot apportion {total_rate!r} across it")
    rates = [total_rate * a / total_area for a in areas]
    rate_sum = float(math.fsum(rates))
    tol = _FOOTPRINT_RATE_SUM_TOL_REL * abs(total_rate)
    if abs(rate_sum - total_rate) > tol:
        raise AssertionError(
            f"area-weighted per-cell rates sum to {rate_sum!r}, expected "
            f"{total_rate!r} within {tol!r} "
            "(DESIGN_DOCS/T1_S5_brief.md Sec 3.3 rate-sum assertion)")
    return rates


def _footprint_rates(grid: Dict[str, Any], mass_g: float, pulse_days: float,
                     ) -> Tuple[List[int], List[float], float]:
    """The per-cell SRC loading for `grid["src_cells"]` -- T1 S5 (brief Sec
    1-3). `grid["footprint_radius_m"] == 0.0` is the frozen SENTINEL: the
    single `src_cells[0]` carries the WHOLE `M/T`, exactly reproducing
    today's `smassrate = mass_g / (1 * pulse_days)`. A positive radius
    apportions `M/T` across `grid["src_cells"]` by `grid["footprint_areas_m2"]`
    via `_apportion_rates`, using geometry `refine_corridor` already
    computed (no re-solve here).

    Also returns `smassrate` -- the FROZEN payload expression `mass_g /
    (n_src * pulse_days)` (brief Sec 3.1). By construction this is exactly
    the arithmetic MEAN of the returned per-cell rates (`sum(rate_i) ==
    M/T`, so `mean(rate_i) == (M/T) / n_src == smassrate`); it must NEVER be
    used by a caller to build a positive-radius SRC record -- use the
    per-cell rates this function returns instead.
    """
    src_cells = list(grid["src_cells"])
    n_src = len(src_cells)
    smassrate = float(mass_g) / (n_src * float(pulse_days))
    radius_m = float(grid.get("footprint_radius_m", 0.0))
    if radius_m == 0.0:
        per_cell_rates = [smassrate for _ in src_cells]
    else:
        total_rate = float(mass_g) / float(pulse_days)
        per_cell_rates = _apportion_rates(grid["footprint_areas_m2"], total_rate)
    return src_cells, per_cell_rates, smassrate


# ---------------------------------------------------------------------------
# T1 S9a (DESIGN_DOCS/T1_S9a_brief.md v2): B-control intersection geometry.
#
# What this IS: an apportionment of the doublet's extraction rate across the
# cells intersecting a FIXED PHYSICAL DISC centred on the extraction well --
# `a_i = area(cell_i INTERSECT disc)`, `q_i = Q * a_i / sum(a)`, cells sorted
# ascending, `sum(q_i) == Q` asserted on SIGNED values. Identical in FORM to
# S5's source rule (the same areal regularisation), reusing S5's
# `_disc_footprint_areas` / `_apportion_rates` VERBATIM -- brief Sec 1 makes
# writing a second intersection routine a known defect, not a design choice
# ("courant_nstp", "_src_sha" and the doublet WEL have each already paid for
# that duplication once).
#
# What this is NOT: a physical model of well inflow. Real screen inflow
# depends on hydraulic conductance, transmissivity / saturated thickness and
# the evolving well-to-cell head difference -- a MAW-style formulation, which
# this is not. Area-weighting only holds the receptor's SUPPORT fixed across
# meshes; it does not reproduce how a well actually draws water. B-control
# licenses "sink support was controlled", never "the well is physically
# modelled" and never causal isolation (brief Sec 2.0).
#
# Single layer only (brief Sec 2.0.1): `_disc_footprint_areas` intersects
# LAYER-0 cell polygons, correct here only because this model is nlay=1
# (`add_flow_model`/`add_transport_model`, both `nlay=1`). A screened
# multilayer well would need layer-specific geometry and vertical
# allocation this geometry cannot express -- it will not fail loudly if the
# model ever gains layers.
#
# Sign convention (the one place the sink differs from the source): callers
# pass `total_rate <= 0` (extraction) -- `Q = -abs(DOUBLET_Q)` at the one
# call site the brief anticipates (S9b). `_apportion_rates` (reused
# unmodified) makes every `q_i` share `total_rate`'s sign by construction:
# `q_i = total_rate * a_i / sum(a)` with `a_i, sum(a) > 0`.
#
# S9a builds NO MODEL and is wired into NO CALL PATH -- it adds no
# `SrcPulseDemo` field and no `meta` key (both already exist at their S2
# identity default; T0_0 Sec 3). S9b does the WEL integration; S9c the
# matched arm. The tests in `test_t1_sink_support_geometry.py` are the whole
# safety argument for this step (gate coverage: BLIND).
# ---------------------------------------------------------------------------
def _validate_sink_centre(centre_xy: Tuple[float, float]) -> Tuple[float, float]:
    """T1 S9a: a finite `(x, y)` pair, or raise `ValueError` -- the disc
    centre is not validated by `_disc_footprint_areas` itself (brief Sec 4
    exit criterion 10, 'non-finite ... centre')."""
    try:
        cx, cy = float(centre_xy[0]), float(centre_xy[1])
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError(
            f"sink_centre_xy must be an (x, y) pair of finite floats "
            f"(got {centre_xy!r})") from exc
    if not (math.isfinite(cx) and math.isfinite(cy)):
        raise ValueError(f"sink_centre_xy must be finite (got {centre_xy!r})")
    return cx, cy


def _validate_finite_footprint_geometry(areas: Sequence[float], disc_area: float,
                                        covered_area: float) -> None:
    """T1 S9a (brief Sec 4 exit criterion 10): NaN/inf anywhere in the
    geometry -- `disc_area`, `covered_area`, or any per-cell area -- raises
    here, before `_apportion_rates` would otherwise propagate a NaN/inf rate
    silently."""
    if not (math.isfinite(disc_area) and math.isfinite(covered_area)):
        raise ValueError(
            f"sink footprint disc geometry produced a non-finite area "
            f"(disc_area_m2={disc_area!r}, covered_area_m2={covered_area!r})")
    if any(not math.isfinite(a) for a in areas):
        raise ValueError(
            f"sink footprint disc geometry produced a non-finite per-cell "
            f"intersection area: {list(areas)!r}")


def _sink_footprint_areas(mg, ncpl: int, idomain: Optional[np.ndarray],
                          centre_xy: Tuple[float, float], radius_m: float,
                          ) -> Tuple[List[int], List[float], float, float]:
    """T1 S9a geometry: REUSES `_disc_footprint_areas` verbatim for the
    disc/cell intersection (brief Sec 1 -- a second intersection routine is
    forbidden) and adds two guards that helper does not provide on its own:

    * over-coverage (brief Sec 4 exit criterion 9): `_disc_footprint_areas`'s
      own coverage check (`disc_area - covered_area > tol * disc_area`) is
      ONE-SIDED -- it catches only UNDER-coverage. Overlapping or invalid
      cell polygons that double-count area would pass it silently, so this
      wrapper additionally asserts `covered_area <= disc_area * (1 + tol)`,
      using the SAME `_FOOTPRINT_COVERAGE_TOL_REL` tolerance, in its own
      check -- `_disc_footprint_areas` itself is not edited beyond its
      exception noun (S5's shipped source path depends on it unchanged).
    * non-finite geometry (exit criterion 10): see
      `_validate_finite_footprint_geometry`.

    Mirrors `_disc_footprint_areas`'s own contract: callers must not call
    this at the `radius_m == 0.0` sentinel (see `_sink_footprint_rates`,
    which owns that branch -- the generic helper does not supply it).
    """
    cx, cy = _validate_sink_centre(centre_xy)
    _validate_footprint_radius(radius_m)
    cells, areas, disc_area, covered_area = _disc_footprint_areas(
        mg, ncpl, idomain, (cx, cy), radius_m, disc_label="sink footprint disc")
    _validate_finite_footprint_geometry(areas, disc_area, covered_area)
    if covered_area - disc_area > _FOOTPRINT_COVERAGE_TOL_REL * disc_area:
        excess = covered_area - disc_area
        raise ValueError(
            f"sink footprint disc (radius_m={radius_m!r}, centre_xy=({cx!r}, {cy!r})) "
            f"is OVER-covered by the mesh's active layer-0 cells: "
            f"{excess:.6g} m^2 of {disc_area:.6g} m^2 double-counted "
            f"({(excess / disc_area if disc_area else float('nan')):.3%}) -- overlapping "
            "or invalid cell polygons must not silently double-count area "
            "(DESIGN_DOCS/T1_S9a_brief.md Sec 4 exit criterion 9)")
    return cells, areas, disc_area, covered_area


def _sink_footprint_rates(mg, ncpl: int, idomain: Optional[np.ndarray],
                          centre_xy: Tuple[float, float], radius_m: float,
                          ext_cell: int, total_rate: float,
                          ) -> Tuple[List[int], List[float]]:
    """T1 S9a (`DESIGN_DOCS/T1_S9a_brief.md` v2): apportion `total_rate`
    (the doublet's extraction rate -- callers pass `Q = -abs(DOUBLET_Q)`,
    negative) across the cells intersecting a disc of `radius_m` centred on
    `centre_xy`, reusing `_sink_footprint_areas` (geometry) and S5's
    `_apportion_rates` (`q_i = total_rate * a_i / sum(a)`, unmodified) for
    the arithmetic.

    This is an **imposed distributed extraction control** -- a
    mesh-independent regularisation of a prescribed areal sink. It is **NOT
    a physical model of well inflow**: real screen inflow depends on
    hydraulic conductance, transmissivity / saturated thickness, and the
    evolving well-to-cell head difference (a MAW-style formulation, which
    this is not). Area-weighting holds the receptor's support fixed across
    meshes; it establishes only that "sink support was controlled", never
    that the well is physically modelled and never causal isolation (brief
    Sec 2.0).

    Assumes a SINGLE-LAYER, horizontally distributed sink (brief Sec 2.0.1)
    -- correct only because this model is `nlay=1`. A screened multilayer
    well needs layer-specific geometry and vertical allocation this cannot
    express; it will not fail loudly if the model ever gains layers.

    `radius_m == 0.0` is the frozen SENTINEL -- returns `([ext_cell],
    [total_rate])`, exactly today's single nearest-centroid extraction cell
    and its whole rate (`T0_0...` Sec 3's identity default,
    `[(ext_cell, -abs(DOUBLET_Q))]`), with NO disc geometry built at all.
    This sentinel is NOT supplied by `_disc_footprint_areas` / the generic
    helper -- it is this function's own contract.

    At a positive radius, `cells` is sorted ascending by cell index
    (inherited from `_disc_footprint_areas`) with `sum(rates) == total_rate`
    to `_FOOTPRINT_RATE_SUM_TOL_REL` relative tolerance on SIGNED values
    (asserted inside `_apportion_rates`), and every rate carries
    `total_rate`'s sign (negative, for extraction) by construction.

    Raises `ValueError` for a non-finite `radius_m`/`centre_xy`/`total_rate`,
    for an incompletely- or over-covered disc, or for non-finite geometry.
    """
    _validate_footprint_radius(radius_m)
    if not math.isfinite(total_rate):
        raise ValueError(f"total_rate must be finite (got {total_rate!r})")
    if radius_m == 0.0:
        return [int(ext_cell)], [float(total_rate)]
    cells, areas, _disc_area, _covered_area = _sink_footprint_areas(
        mg, ncpl, idomain, centre_xy, radius_m)
    rates = _apportion_rates(areas, total_rate)
    return cells, rates


def _binding_cell(cells: Sequence[int], rates: Sequence[float],
                  q_cells: Sequence[float]) -> int:
    """T1 S5's frozen binding-cell rule (brief Sec 3.2): the cell maximising
    `rate_i / q_cell_i` -- the highest emergent concentration, where a
    solubility limit actually binds. Ties break to the LOWEST cell index.
    At a single-cell footprint (the sentinel) the maximum over one cell is
    that cell, so the default is untouched.
    """
    best_ratio = -math.inf
    best_cell: Optional[int] = None
    for c, r, q in zip(cells, rates, q_cells):
        ratio = r / q
        if ratio > best_ratio or (ratio == best_ratio
                                  and (best_cell is None or c < best_cell)):
            best_ratio = ratio
            best_cell = c
    if best_cell is None:
        raise ValueError("_binding_cell: cells must be non-empty")
    return best_cell


def refine_corridor(cgwf, boundary, rivers, spill_xy=None, *,
                    refine_radii: Any = _UNSET,
                    mesh_spec: Optional["MeshSpec"] = None,
                    case_ws: Optional[Union[str, Path]] = None,
                    footprint_radius_m: float = 0.0) -> Dict[str, Any]:
    """Refine the spill->extraction corridor and return a **GridBundle** dict.

    Computes the local regional-flow direction at the extraction well (to place
    the spill ``SPILL_UPGRADIENT_M`` upgradient, unless ``spill_xy`` is given),
    then corridor-refines the DISV grid via ``_refine_with_retry`` (the macOS
    arm64 SIGILL / Triangle-precision radius-walk stays INSIDE this call).

    ``refine_radii=`` (legacy) and ``mesh_spec=`` (T1 S3a) are resolved by
    ``_resolve_mesh_spec`` -- supplying both is a ``ValueError``. A
    ``mesh_spec`` with more than one ``MeshLevel`` raises ``NotImplementedError``
    (S3b, not built here).

    ``footprint_radius_m`` (T1 S5, default ``0.0``) is the fixed physical
    source footprint's radius. At ``0.0`` (the sentinel) ``src_cells`` is the
    single nearest-centroid cell, exactly as before S5. At a positive radius
    it is every active layer-0 cell the disc (centred on the spill point)
    intersects, sorted ascending by cell index; negative or non-finite
    raises ``ValueError``. The returned dict also carries the footprint's
    GEOMETRY (``footprint_areas_m2``, aligned with ``src_cells``,
    ``footprint_disc_area_m2``, ``footprint_covered_area_m2``) -- not rates,
    which need ``mass_g``/``pulse_days`` and are apportioned later by
    ``_footprint_rates``.

    The returned dict carries everything the sim builders need -- modelgrid,
    gridprops, cell arrays, boundary stress data, and the injection / extraction /
    source cell indices -- so nothing downstream reaches back into the coarse or
    refined GWF objects. It also carries the two T1 S3a mesh identities:
    ``mesh_spec_hash`` (declared) and ``mesh_hash`` (effective -- the winning
    retry radius and the GIS content hashes folded in).
    """
    spec = _resolve_mesh_spec(refine_radii=refine_radii, mesh_spec=mesh_spec)
    _require_single_level(spec)   # NotImplementedError for >1 level, before any I/O
    _validate_footprint_radius(footprint_radius_m)   # before any I/O (T1 S5 brief Sec 3.3)

    heads_array = cgwf.output.head().get_data().flatten()

    # ---- regional flow direction at the extraction well -> upgradient spill ----
    mg0 = cgwf.modelgrid
    xc0 = np.array(mg0.xcellcenters); yc0 = np.array(mg0.ycellcenters)
    spd0 = cgwf.output.budget().get_data(text="DATA-SPDIS")[0]
    ia = int(np.argmin((xc0 - ABS_XY[0]) ** 2 + (yc0 - ABS_XY[1]) ** 2))
    u_reg = np.array([spd0["qx"][ia], spd0["qy"][ia]], float)
    u_reg = u_reg / np.hypot(*u_reg)                     # flow (downgradient) unit vector
    if spill_xy is None:
        spill_xy = (ABS_XY[0] - SPILL_UPGRADIENT_M * u_reg[0],
                    ABS_XY[1] - SPILL_UPGRADIENT_M * u_reg[1])

    # ---- corridor refinement (spill->extraction corridor + injection well) ----
    case_ws = Path(case_ws) if case_ws is not None else _default_case_ws()
    corr_pts, u, L = _corridor_points(spill_xy, ABS_XY)
    refine_points = corr_pts + [tuple(INJ_XY)]
    boundary_path, rivers_path = _gis_source_paths()
    res, refine_radius_used, refgrid_hash = _refine_with_retry(
        cgwf, boundary, rivers, refine_points, heads_array, case_ws,
        mesh_spec=spec, boundary_path=boundary_path, rivers_path=rivers_path,
        sim_name="rg")
    rgwf = res["gwf"]; mg = res["modelgrid"]; gp = res["gridprops"]; ncpl = res["ncpl"]
    xc = np.array(mg.xcellcenters); yc = np.array(mg.ycellcenters)
    csz = _cellsize(mg, ncpl)

    k_ref = rgwf.npf.k.array; top_ref = rgwf.disv.top.array; botm_ref = rgwf.disv.botm.array
    heads_ref = rgwf.output.head().get_data().flatten()
    chd = rgwf.get_package("CHD").stress_period_data.get_data(0)
    riv = rgwf.get_package("RIV").stress_period_data.get_data(0)
    rch = rgwf.get_package("RCHA").recharge.get_data()

    injc = int(np.argmin((xc - INJ_XY[0]) ** 2 + (yc - INJ_XY[1]) ** 2))
    extc = int(np.argmin((xc - ABS_XY[0]) ** 2 + (yc - ABS_XY[1]) ** 2))

    # ---- T1 S5 (DESIGN_DOCS/T1_S5_brief.md v3): fixed physical source
    # footprint. footprint_radius_m == 0.0 is the frozen SENTINEL -- the
    # SAME argmin single-cell selection as always, no disc geometry built at
    # all, so this branch is byte-for-byte identical to pre-S5 code. A
    # positive radius apportions the disc across every active layer-0 cell
    # it intersects (Sec 3.3); geometry only -- rates are apportioned later,
    # once mass_g/pulse_days are known (see `_footprint_rates`).
    if footprint_radius_m == 0.0:
        src_cells = [int(np.argmin((xc - spill_xy[0]) ** 2 + (yc - spill_xy[1]) ** 2))]
        footprint_areas = [0.0]
        footprint_disc_area = 0.0
        footprint_covered_area = 0.0
    else:
        idomain = np.asarray(rgwf.disv.idomain.array, dtype=int).reshape(-1)
        src_cells, footprint_areas, footprint_disc_area, footprint_covered_area = \
            _disc_footprint_areas(mg, ncpl, idomain, spill_xy, footprint_radius_m)

    line = LineString([tuple(spill_xy), tuple(ABS_XY)])
    corridor_mask = np.array([line.distance(Point(xc[i], yc[i])) < refine_radius_used
                              for i in range(ncpl)])

    return dict(
        modelgrid=mg, gridprops=gp, ncpl=ncpl, nvert=gp["nvert"],
        top=top_ref, botm=botm_ref, k=k_ref, heads=heads_ref,
        chd=chd, riv=riv, rch=rch, cellsize=csz, xc=xc, yc=yc,
        inj_cell=injc, ext_cell=extc, src_cells=src_cells,
        spill_xy=(float(spill_xy[0]), float(spill_xy[1])),
        corridor_mask=corridor_mask, u_reg=tuple(u_reg),
        refine_radius_used=refine_radius_used, rgwf=rgwf,
        mesh_spec=spec, mesh_spec_hash=mesh_spec_hash(spec), mesh_hash=refgrid_hash,
        boundary_path=boundary_path, rivers_path=rivers_path,
        # T1 S5: the fixed physical source footprint's GEOMETRY (brief Sec
        # 1-3.3) -- not rates yet (those need mass_g/pulse_days; see
        # `_footprint_rates`). `footprint_areas_m2` is aligned entry-for-entry
        # with `src_cells`.
        footprint_radius_m=float(footprint_radius_m),
        footprint_centre_xy=(float(spill_xy[0]), float(spill_xy[1])),
        footprint_areas_m2=footprint_areas,
        footprint_disc_area_m2=footprint_disc_area,
        footprint_covered_area_m2=footprint_covered_area)


def new_sim(case_ws: Union[str, Path], *, pulse_days: float, total_days: float,
            nstp_per_period: int, exe: str):
    """Create the ``MFSimulation`` + TDIS (2 periods: pulse ON / migration) + the
    GWF IMS solver.

    TDIS period 0 is the ON pulse (duration ``pulse_days``), period 1 the
    post-pulse migration (``total_days - pulse_days``); ``nstp_per_period`` is
    split between them in proportion to their durations.  The GWT IMS solver is
    added later (in ``add_transport_model``, after the GWT model exists, to
    preserve the original construction order).
    """
    ws = str(Path(case_ws) / "sim")
    sim = flopy.mf6.MFSimulation(sim_name="srcpulse", exe_name=exe, sim_ws=ws)
    # TDIS: 2 periods -> pulse ON (T), then OFF (migration)
    n_on = max(int(nstp_per_period * float(pulse_days) / float(total_days)), 1)
    n_off = max(nstp_per_period - n_on, 1)
    perioddata = [(float(pulse_days), n_on, 1.0),
                  (float(total_days) - float(pulse_days), n_off, 1.0)]
    nper = len(perioddata)
    flopy.mf6.ModflowTdis(sim, time_units=LOCKED_PARAMS["time_units"],
                          nper=nper, perioddata=perioddata)
    flopy.mf6.ModflowIms(sim, filename="gwf.ims", **_GWF_IMS)
    return sim


def _wel_support_cells(gwf, pname: str = "absw") -> List[Tuple[int, float]]:
    """T1 S9b (`DESIGN_DOCS/T1_S9b_brief.md` v2 Sec 2.2): read the
    ACTUALLY BUILT stress-period data off the named WEL package and
    normalise it into ``[(cell_index, rate), ...]``, sorted ascending by
    cell index.

    `T0_0...` Sec 3 calls an empty/recomputed record a "false record":
    ``meta["sink_support_cells"]`` must be derived from the SAME object
    handed to ``ModflowGwfwel``, read back through FloPy, never
    reconstructed a second time from ``sink_support_m`` alongside it.
    "Byte-identical" is not a meaningful comparison once FloPy has converted
    the input list into an ``MFTransientList`` -- ``get_data(0)`` returns a
    structured record array whose ``cellid`` field is itself a tuple (e.g.
    ``(0, 137)`` for this DISV nlay=1 model) and whose ``q`` is a numpy
    scalar; both are normalised here to plain Python ``int``/``float``.
    """
    spd = gwf.get_package(pname).stress_period_data.get_data(0)
    pairs = [(int(rec["cellid"][-1]), float(rec["q"])) for rec in spd]
    return sorted(pairs, key=lambda pair: pair[0])


def _realized_extraction_flows(gwf, pname: str = "absw") -> Dict[int, float]:
    """T1 S9c (`DESIGN_DOCS/T1_S9c_brief.md` v2 Sec 2.1): read the REALIZED
    per-cell extraction flow [m^3/d] off the SOLVED GWF cell-by-cell budget
    (``gwf.cbc``, already written -- ``budget_filerecord="gwf.cbc"`` in
    ``add_flow_model``) -- NOT the rate handed to ``ModflowGwfwel``.
    Configured rates can silently diverge from what the solver actually
    delivered (a cell dries, deactivates, or has its flow reduced), and
    every test built against the CONFIGURED rate would still pass in that
    case -- exactly the footgun the brief's round-1 review caught.

    ``paknam2=pname`` isolates ONE WEL package's records from the OTHER
    doublet well sharing the same ``gwf.cbc``: ``add_flow_model`` builds two
    separate ``ModflowGwfwel`` packages (``"injw"``, ``"absw"``), and a bare
    ``text="WEL"`` read would otherwise mix the injection well's flow into
    the extraction-support weights.

    🔴 The GWF model is STEADY-STATE (``ModflowGwfsto(gwf, steady_state=...)``,
    ``:1567``) with a transient GWT riding on top of one constant flow
    field, so EVERY saved WEL budget record (``saverecord=[..., ("BUDGET",
    "LAST")]``) carries the SAME per-cell flows regardless of stress
    period -- reading the first one is sufficient; no OC change is made or
    needed. **This reduction is INVALID the moment GWF ever becomes
    transient** -- nothing here fails loudly if that changes, so this
    comment (and the matching one in ``_flux_weighted_breakthrough``) is the
    only warning; the weights would need to become time-resolved.
    """
    bud = gwf.output.budget()
    recs = bud.get_data(text="WEL", paknam2=pname)
    if not recs:
        raise RuntimeError(
            f"no {pname!r} WEL budget records found in the solved GWF "
            "cell-by-cell budget -- cannot read realized extraction flows")
    rec = recs[0]   # steady-state: every saved record is identical (see above)
    out: Dict[int, float] = {}
    for row in rec:
        out[int(row["node"]) - 1] = float(row["q"])
    return out


def _validate_realized_sink_flows(prescribed: Dict[int, float],
                                   realized: Dict[int, float],
                                   rtol: float = 1e-5, atol: float = 1e-8) -> None:
    """T1 S9c (brief Sec 2.1, exit criteria 12-13): raise if the solved GWF
    does not deliver the extraction-support control it claims.

    Two independent, both-fatal failure modes (never a silent readout of a
    wrong number under a right-looking name):
      1. a support cell's REALIZED flow differs from what was PRESCRIBED to
         ``ModflowGwfwel`` beyond tolerance -- a dry, deactivated, or
         flow-reduced cell;
      2. a support cell's realized flow has the WRONG SIGN (positive, i.e.
         inflow) -- an extraction cell that is not extracting means the
         control is not doing what it claims, independent of magnitude.
    """
    missing = sorted(set(prescribed) - set(realized))
    if missing:
        raise RuntimeError(
            f"support cell(s) {missing} are missing from the realized WEL "
            "budget -- the arm is not delivering the sink support it claims")
    for cell in sorted(prescribed):
        req = prescribed[cell]
        got = realized[cell]
        if got > 0.0:
            raise RuntimeError(
                f"support cell {cell}: realized WEL flow {got!r} has the "
                "WRONG SIGN (an extraction cell reporting inflow) -- the "
                "arm is not delivering the sink support it claims")
        if not math.isclose(got, req, rel_tol=rtol, abs_tol=atol):
            raise RuntimeError(
                f"support cell {cell}: realized WEL flow {got!r} != "
                f"prescribed {req!r} beyond tolerance (rtol={rtol!r}, "
                f"atol={atol!r}) -- the arm is not delivering the sink "
                "support it claims (dry, deactivated, or flow-reduced cell)")


def _flux_weighted_breakthrough(cobj, times: np.ndarray, sink_cells: List[int],
                                 weights: Dict[int, float]) -> np.ndarray:
    """T1 S9c (`DESIGN_DOCS/T1_S9c_brief.md` v2 Sec 2): the ONE breakthrough
    series -- every downstream metric (``peak_mgL``, ``arrival_day``,
    ``t_peak``, exceedance) derives from this array, at the sentinel and at
    a positive radius alike, so replacing it here is the ONLY place a
    positive radius changes the readout (exit criteria 3/17: the sentinel
    branch below selects only the SERIES; all downstream processing is
    shared code, so the two paths cannot drift).

    ``C_ext(t) = Sum(|q_i| * C_i(t)) / Sum(|q_i|)`` over ``sink_cells``,
    with the weights ``|q_i|`` held CONSTANT across time -- valid ONLY
    because GWF is steady-state (see ``_realized_extraction_flows``'s
    docstring); if GWF ever becomes transient this function's
    time-invariant-weight assumption breaks and the weights must be read
    per output time instead.

    🔴 SENTINEL BRANCH (frozen): with exactly one support cell the general
    formula reduces to ``C`` EXACTLY in real arithmetic (``|q|*C/|q| ==
    C``), but is NOT guaranteed bit-for-bit in floating point -- so the
    single-cell case takes an EXPLICIT branch reading ``cobj`` exactly as
    pre-S9c, rather than resting the default contract on IEEE rounding.
    The general (multi-cell) formula is used ONLY when the support has more
    than one cell.
    """
    if len(sink_cells) == 1:
        c = sink_cells[0]
        raw = np.array([cobj.get_data(totim=t)[0, 0, c] for t in times])
        return np.maximum(raw, 0.0)

    total_w = sum(abs(weights[c]) for c in sink_cells)
    if total_w == 0.0:
        raise RuntimeError(
            "degenerate sink support: sum(|q_i|) over the support cells is "
            "0.0 -- cannot form a flux-weighted mixture")
    raw = np.zeros(len(times), dtype=float)
    for c in sink_cells:
        w = abs(weights[c])
        conc_c = np.array([cobj.get_data(totim=t)[0, 0, c] for t in times])
        raw = raw + w * conc_c
    raw = raw / total_w
    return np.maximum(raw, 0.0)


def add_flow_model(sim, grid: Dict[str, Any], sink_support_m: float = 0.0):
    """Add the GWF flow model (DISV, NPF, IC, STO, RCHA, CHD, RIV, WEL x2 doublet,
    OC) to ``sim`` and return it.  The doublet wells are FLOW ONLY (no solute).

    T1 S9b (`DESIGN_DOCS/T1_S9b_brief.md` v2): ``sink_support_m`` (default
    ``0.0``, the frozen SENTINEL) apportions the EXTRACTION well's rate
    across the cells intersecting a disc of this radius centred on the
    extraction well (``ABS_XY``), via ``_sink_footprint_rates`` -- the SAME
    area-weighted disc/apportionment machinery S5 uses for the source (S9a's
    geometry, reused verbatim; no second apportionment routine). At the
    sentinel, ``_sink_footprint_rates`` takes its own sentinel branch (no
    disc geometry built at all) and the emitted ``absw`` stress-period data
    is STRUCTURALLY IDENTICAL to the pre-S9b literal
    ``[[(0, extc), -abs(DOUBLET_Q)]]``.

    ⚠️ The INJECTION well (``injw``) is UNCHANGED at every radius --
    `T0_0...` Sec 3 names only the EXTRACTION-support disc; S9b does not
    touch injection (brief Sec 3).

    ⚠️ **PRT divergence** (brief Sec 2.4): MODFLOW 6 PRT builds its OWN
    doublet WEL (`transport_prt_capture.py`, hard-coded single-cell) and
    does NOT call this function. At ``sink_support_m > 0`` the demo's GWF
    built here and PRT's own GWF are therefore DIFFERENT flow fields that
    happen to share a mesh identity. Fixing that needs no new authority:
    B-control arms simply do not claim a capture fingerprint (S10).

    ⚠️ **No SSM change is needed** for a distributed sink (brief Sec 1.1):
    ``add_transport_model`` uses bare ``ModflowGwtssm(gwt)``, so MF6 already
    routes each WEL cell's own outflow at that cell's own concentration --
    the flux-weighted mixture a positive radius implies EMERGES from the
    solver; it is not assembled by hand here.

    ⚠️ **Readout caveat / dry-cell policy** (brief Sec 2.3/2.3.1, lifted by
    T1 S9c -- `DESIGN_DOCS/T1_S9c_brief.md` v2): this function only builds
    the WEL package. ``build_srcpulse_demo`` reads the FLUX-WEIGHTED mixture
    across every support cell (``_flux_weighted_breakthrough``), not the
    single ``ext_cell`` concentration -- a distributed sink's single-cell
    reading is a concentration AT ONE CELL OF THE SUPPORT, not the
    extracted concentration. WEL rates themselves are delivered as
    specified: the GWF model is NEWTON (``icelltype=1`` convertible cells,
    Newton-Raphson smoothing), which does not abruptly zero out a drying
    cell's rate the way a Picard/dry-cell reduction could -- a supported
    cell that cannot sustain its requested rate shows up as a
    non-converged run (``ok=False``), not a silently reduced flow.
    ``build_srcpulse_demo`` does not ASSUME the realized rate matches the
    requested one for that reason either: it reads the REALIZED per-cell
    flow back off the solved GWF budget (``_realized_extraction_flows``)
    and RAISES if it diverges from the prescribed rate beyond tolerance, or
    has the wrong sign (``_validate_realized_sink_flows``; see also
    ``test_realized_wel_flow_matches_requested``, the same check exercised
    directly at this level).
    """
    ncpl = grid["ncpl"]; gp = grid["gridprops"]
    top_ref = grid["top"]; botm_ref = grid["botm"]; k_ref = grid["k"]
    heads_ref = grid["heads"]; rch = grid["rch"]; chd = grid["chd"]; riv = grid["riv"]
    injc = grid["inj_cell"]; extc = grid["ext_cell"]
    nper = int(sim.tdis.nper.get_data())
    _validate_footprint_radius(sink_support_m)   # reuse S9a's validator (brief Sec 3)

    gwf = flopy.mf6.ModflowGwf(sim, modelname="gwf", save_flows=True,
                               newtonoptions=_GWF_NEWTON)
    flopy.mf6.ModflowGwfdisv(gwf, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                             botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
    flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=k_ref, save_flows=True,
                            save_specific_discharge=True)
    flopy.mf6.ModflowGwfic(gwf, strt=np.maximum(heads_ref, botm_ref[0] + 0.01))
    flopy.mf6.ModflowGwfsto(gwf, steady_state={i: True for i in range(nper)})
    flopy.mf6.ModflowGwfrcha(gwf, recharge=rch)
    flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["head"]))
                                                     for r in chd])
    flopy.mf6.ModflowGwfriv(gwf, stress_period_data=[(tuple(r["cellid"]), float(r["stage"]),
                            float(r["cond"]), float(r["rbot"])) for r in riv])
    # ---- doublet wells: FLOW ONLY (clean injection, no concentration) ----
    flopy.mf6.ModflowGwfwel(gwf, pname="injw",
                            stress_period_data={0: [[(0, injc), abs(DOUBLET_Q)]]})
    # T1 S9b: extraction-support disc (S9a geometry, reused verbatim via
    # `_sink_footprint_rates`). The sentinel (sink_support_m == 0.0) takes
    # that function's own sentinel branch -- no disc geometry built -- so
    # `absw_spd` below is structurally identical to the pre-S9b literal.
    idomain = np.asarray(grid["rgwf"].disv.idomain.array, dtype=int).reshape(-1)
    mg = grid["modelgrid"]
    sink_cells, sink_rates = _sink_footprint_rates(
        mg, ncpl, idomain, ABS_XY, float(sink_support_m), extc, -abs(DOUBLET_Q))
    # brief Sec 2.3.1: `extc` is not guaranteed to lie inside its own disc --
    # if it did not, the retained single-cell readout would not even be a
    # support-cell observation. Assert it here, at construction time, so a
    # caller (S9c included) inherits a meaningful anchor rather than a
    # silent miss.
    if extc not in sink_cells:
        raise ValueError(
            f"sink_support_m={sink_support_m!r}: the extraction cell "
            f"(ext_cell={extc}) does not lie inside its own resulting "
            f"support {sink_cells!r} -- the readout anchor requires ext_cell "
            "to be a member of the support disc (DESIGN_DOCS/T1_S9b_brief.md "
            "Sec 2.3.1).")
    absw_spd = [[(0, c), r] for c, r in zip(sink_cells, sink_rates)]
    flopy.mf6.ModflowGwfwel(gwf, pname="absw", stress_period_data={0: absw_spd})
    flopy.mf6.ModflowGwfoc(gwf, head_filerecord="gwf.hds", budget_filerecord="gwf.cbc",
                           saverecord=[("HEAD", "LAST"), ("BUDGET", "LAST")])
    return gwf


def add_transport_model(sim, gwf, grid: Dict[str, Any], *, mass_g: float,
                        pulse_days: float, R: float = 1.0, rho_b: float = 1800.0,
                        lam: float = 0.0, alpha_L: Optional[float] = None):
    """Add the GWT solute-transport model (DISV, IC, MST, ADV/TVD, DSP, SSM, SRC,
    OC) + the GWT IMS solver to ``sim`` and return it.

    The spill enters via the SRC package as a per-cell mass loading, ON in
    period 0 and OFF in period 1.  At the T1 S5 sentinel
    (``grid["footprint_radius_m"] == 0.0``, the default) this is one cell
    carrying ``smassrate = mass_g / (1 * pulse_days)`` [g/d] -- exactly as
    before S5.  At a positive footprint radius each cell in
    ``grid["src_cells"]`` carries its own AREA-WEIGHTED rate (see
    ``_footprint_rates`` / ``_apportion_rates``), not an equal split.
    ``alpha_L`` defaults to the LOCKED longitudinal dispersivity;
    ``alpha_T`` is derived from the LOCKED 10:1 ratio.  MST sorption is gated on
    ``R > 1`` (``Kd = (R-1)*porosity/rho_b``) and first-order decay on ``lam > 0``.
    """
    ncpl = grid["ncpl"]; gp = grid["gridprops"]
    top_ref = grid["top"]; botm_ref = grid["botm"]

    alpha_L_eff = float(LOCKED_PARAMS["alh"]) if alpha_L is None else float(alpha_L)
    alpha_T_eff = alpha_L_eff * (float(LOCKED_PARAMS["ath1"]) / float(LOCKED_PARAMS["alh"]))
    porosity = float(LOCKED_PARAMS["porosity"])
    Kd = (float(R) - 1.0) * porosity / float(rho_b) if R > 1.0 else 0.0
    # T1 S5 (brief Sec 1-3): per-cell SRC loading. `smassrate` is kept ONLY
    # as the frozen payload expression (brief Sec 3.1, arithmetic mean of
    # `per_cell_rates` by construction) -- `src_spd` below is built from
    # `per_cell_rates`, never from `smassrate` broadcast, except at the
    # sentinel where they are (by construction) identical.
    src_cells, per_cell_rates, smassrate = _footprint_rates(grid, mass_g, pulse_days)

    gwt = flopy.mf6.ModflowGwt(sim, modelname="gwt", save_flows=True)
    flopy.mf6.ModflowGwtdisv(gwt, nlay=1, ncpl=ncpl, nvert=gp["nvert"], top=top_ref,
                             botm=botm_ref, vertices=gp["vertices"], cell2d=gp["cell2d"])
    flopy.mf6.ModflowGwtic(gwt, strt=0.0)
    # ---- MST: porosity always; sorption only when R > 1; decay only when lam > 0.
    # decay_sorbed is only MF6-valid when sorption is active (decay_sorbed requires
    # sorption="linear"/"freundlich"/"langmuir"), so it is gated on R > 1 as well.
    mst_kwargs: Dict[str, Any] = dict(porosity=LOCKED_PARAMS["porosity"])
    if R > 1.0:
        mst_kwargs.update(sorption="linear", bulk_density=rho_b, distcoef=Kd)
    if lam > 0.0:
        mst_kwargs.update(first_order_decay=True, decay=lam)
        if R > 1.0:
            mst_kwargs.update(decay_sorbed=lam)
    flopy.mf6.ModflowGwtmst(gwt, **mst_kwargs)
    flopy.mf6.ModflowGwtadv(gwt, scheme=LOCKED_PARAMS["scheme"])
    flopy.mf6.ModflowGwtdsp(gwt, alh=alpha_L_eff, ath1=alpha_T_eff,
                            diffc=LOCKED_PARAMS["diffc"], xt3d_off=LOCKED_PARAMS["xt3d_off"])
    # bare SSM: CHD/RIV/RCHA/WEL flows carry default (0 inflow / cell-conc outflow)
    flopy.mf6.ModflowGwtssm(gwt)
    # SRC finite pulse: PER-CELL mass loading [g/d] in period 0, OFF in period 1
    # (T1 S5: `per_cell_rates` is the area-weighted apportionment, not one
    # scalar broadcast across cells -- an equal split would make the support
    # mesh-dependent again in a subtler way).
    src_spd = {0: [[(0, c), r] for c, r in zip(src_cells, per_cell_rates)], 1: []}
    flopy.mf6.ModflowGwtsrc(gwt, stress_period_data=src_spd)
    flopy.mf6.ModflowGwtoc(gwt, concentration_filerecord="gwt.ucn",
                           budget_filerecord="gwt.cbc",
                           saverecord=[("CONCENTRATION", "ALL"), ("BUDGET", "ALL")])
    flopy.mf6.ModflowIms(sim, filename="gwt.ims", **_GWT_IMS)
    sim.register_ims_package(sim.get_package("gwt.ims"), ["gwt"])
    return gwt


def couple_and_run(sim, gwf, gwt, grid: Dict[str, Any],
                   case_ws: Union[str, Path]) -> Tuple[bool, Any, Any]:
    """Register the GWF6-GWT6 exchange, write, and run the coupled simulation.

    Returns ``(ok, buf, sim)`` -- the ``run_simulation`` success flag, its output
    buffer, and the (run) simulation object.  ``gwf`` / ``gwt`` make the coupled
    pair explicit even though the exchange references them by model name.
    """
    flopy.mf6.ModflowGwfgwt(sim, exgtype="GWF6-GWT6", exgmnamea="gwf", exgmnameb="gwt",
                            filename="srcpulse.gwfgwt")
    sim.write_simulation(silent=True)
    ok, buf = sim.run_simulation(silent=True)
    return ok, buf, sim


# ---------------------------------------------------------------------------
# build + run
# ---------------------------------------------------------------------------
def build_srcpulse_demo(
    mass_g: float = 3.0e5,
    pulse_days: float = 30.0,
    total_days: float = 120.0,
    solubility_mgL: float = 1000.0,
    *,
    alpha_L: Optional[float] = None,
    R: float = 1.0,
    rho_b: float = 1800.0,
    lam: float = 0.0,
    case_ws: Optional[Union[str, Path]] = None,
    cr_target: float = 0.9,
    nstp_cap: int = 2000,
    refine_radii: Any = _UNSET,
    mesh_spec: Optional["MeshSpec"] = None,
    footprint_radius_m: float = 0.0,
    sink_support_m: float = 0.0,
    courant_profile: str = "legacy_srcpulse",
    force: bool = False,
) -> SrcPulseDemo:
    """Build + run the SRC finite-pulse spill -> capture demo; return diagnostics.

    Parameters
    ----------
    mass_g : float
        Total solute mass released over the pulse [g].
    pulse_days : float
        Pulse duration T [d] (SRC active in stress period 0, off afterwards).
    total_days : float
        Total simulated time [d] (period 0 = pulse, period 1 = migration).
    solubility_mgL : float
        Stated aqueous solubility [mg/L] for the guardrail assertion.
    alpha_L : float, optional
        Override longitudinal dispersivity [m].  ``None`` (default) uses the
        LOCKED value (10.0 m).  Scales BOTH dispersivities to preserve the
        course's locked 10:1 anisotropy ratio: ``alh = alpha_L`` and
        ``ath1 = alpha_L / 10.0``.  Feeds the DSP package and the Pe_L / Pe_T
        grid-Peclet diagnostics (``PeL = cellsize / alpha_L``,
        ``PeT = cellsize / (alpha_L / 10)``).
    R : float
        Retardation factor [-] (students reason in R, not Kd).  ``R == 1.0``
        (default) is conservative transport -- no sorption args are passed to
        MST at all.  ``R > 1`` enables MODFLOW 6 MST linear sorption with
        ``Kd = (R - 1) * porosity / rho_b``.
    rho_b : float
        Dry bulk density [kg/m^3], used only for the Kd conversion when
        ``R > 1``.
    lam : float
        First-order decay rate [1/d] (e.g. ``ln(2) / half_life``).  ``lam >
        0`` enables MST first-order decay.  ``decay_sorbed`` is only valid
        when sorption is active (MF6 constraint), so it is set equal to
        ``lam`` only when ``R > 1`` as well; otherwise only the aqueous
        ``decay`` is passed.
    case_ws : path, optional
        Workspace for the refined grid + coupled sim + cache.  Defaults to
        ``<data>/transport_srcpulse_demo``.
    refine_radii : sequence of float, optional
        Legacy corridor-refinement retry ladder.  Predates ``MeshSpec`` (T1
        S3a) and remains accepted, folding into the default ``MeshSpec``'s
        ``retry_radii``.  Passing this AND ``mesh_spec`` is a ``ValueError``.
    mesh_spec : MeshSpec, optional
        T1 S3a grid parameterisation (``base_cell_size``, ``levels``,
        ``retry_radii``).  ``None`` (default) uses ``MeshSpec()`` -- today's
        behaviour exactly -- unless ``refine_radii`` is given, in which case
        it is folded in instead.  A ``levels`` tuple with more than one
        ``MeshLevel`` raises ``NotImplementedError`` (multi-level
        construction is milestone S3b, not built here).
    footprint_radius_m : float
        T1 S5 fixed physical source footprint radius [m].  ``0.0`` (default)
        is the frozen SENTINEL -- byte-for-byte the pre-S5 behaviour: the
        single nearest-centroid ``src_cells`` cell carries the whole
        ``mass_g / pulse_days``.  A positive radius apportions that rate,
        AREA-WEIGHTED, across every active layer-0 cell a disc of this
        radius (centred on the spill point) intersects.  Negative or
        non-finite raises ``ValueError``.  The per-cell apportionment is not
        part of this return value (T0_0 Sec 2.5 makes an added payload/``meta``
        field a failure edge) -- it belongs in the evidence artifact; see
        ``DESIGN_DOCS/T1_S5_brief.md`` Sec 3.  Not wired into any default
        call -- a later milestone (T2) uses a positive value.
    sink_support_m : float
        T1 S9b/S9c (``DESIGN_DOCS/T1_S9c_brief.md`` v2) extraction-support
        disc radius [m], threaded to ``add_flow_model``.  ``0.0`` (default)
        is the frozen SENTINEL -- structurally identical to pre-S9b
        behaviour: the whole doublet extraction rate on the single
        nearest-centroid ``ext_cell``, and the breakthrough curve below
        takes the EXPLICIT single-cell branch (bit-identical to pre-S9c;
        see ``_flux_weighted_breakthrough``).  Negative or non-finite raises
        ``ValueError``.  A POSITIVE value is supported since S9c: the
        breakthrough curve becomes the FLUX-WEIGHTED mixture
        ``Sum(|q_i| C_i) / Sum(|q_i|)`` over the support cells, with the
        weights read from the REALIZED (not configured) GWF budget after
        the solve -- see ``_realized_extraction_flows`` /
        ``_validate_realized_sink_flows``, which RAISE if a support cell's
        realized flow diverges from what was prescribed (dry, deactivated,
        or flow-reduced) or has the wrong sign.  Not wired into any default
        call -- a later milestone (T2) uses a positive value.
        🔴 **Ceiling:** a positive ``sink_support_m`` controls sink support
        ONLY.  It is NEVER causal isolation of a grid effect -- flow was
        not held common across compared runs (that control is descoped,
        `T0_2b...` Sec 4.2) -- so a grid comparison using this control
        remains ``hypothesis``, never a stronger claim.
        ⚠️ MODFLOW 6 PRT builds its own single-cell doublet WEL and does not
        call ``add_flow_model``, so a positive ``sink_support_m`` used with
        this builder makes PRT's GWF diverge from this one -- B-control
        arms do not claim a capture fingerprint (S10).
    courant_profile : {"legacy_srcpulse", "exp_v1"}
        T1 S8 (``DESIGN_DOCS/T1_S8_brief.md`` v2) ``courant_nstp`` policy
        selector.  ``"legacy_srcpulse"`` (default) is byte-for-byte today's
        behaviour.  ``"exp_v1"`` is the corrected policy: the sliver floor is
        keyed off the finest INTENDED cell size in ``mesh_spec`` rather than
        ``LOCKED_PARAMS["refined_cell_size"]``, source/well cells are
        INCLUDED in selection, the reported ``Cr`` is the measured maximum
        over the whole corridor (not just the surviving selection), and
        ``nstp_cap`` RAISES instead of silently truncating.  Folds into the
        cache identity (``params``, below) exactly as ``footprint_radius_m``
        does, so a run under one profile never resolves to a cache file the
        other wrote.  Not wired into any default call -- a later milestone
        (T2) uses ``"exp_v1"``.
    force : bool
        Rebuild even if a matching cache exists.

    Returns
    -------
    SrcPulseDemo
    """
    # NaN/inf defeat every "<" / "<=" guard below (they are False for NaN), so a
    # NaN would sail through validation and then silently take a wrong branch
    # downstream (e.g. `R > 1.0` is False for R=nan -> falls back to a
    # CONSERVATIVE run mislabelled "R=nan").  Reject non-finite values up front.
    for _name, _val in (("mass_g", mass_g), ("pulse_days", pulse_days),
                         ("total_days", total_days), ("solubility_mgL", solubility_mgL),
                         ("R", R), ("rho_b", rho_b), ("lam", lam),
                         ("cr_target", cr_target), ("footprint_radius_m", footprint_radius_m),
                         ("sink_support_m", sink_support_m)):
        if not math.isfinite(_val):
            raise ValueError(f"{_name} must be finite (got {_val!r})")
    if alpha_L is not None and not math.isfinite(alpha_L):
        raise ValueError(f"alpha_L must be finite (got {alpha_L!r})")

    # T1 S5 (brief Sec 3.3 "Radius validation"): negative or non-finite ->
    # raise, checked up front (before any GIS/MF6 work) like every other
    # parameter guard in this block.
    _validate_footprint_radius(footprint_radius_m)
    # T1 S9b: same validator, reused verbatim (brief Sec 3 "Validation:
    # negative / non-finite -> raise (reuse S9a's validators)").
    _validate_footprint_radius(sink_support_m)

    # T1 S9c (`DESIGN_DOCS/T1_S9c_brief.md` v2 Sec 1) LIFTS the raise S9b put
    # here: a positive `sink_support_m` used to be refused before any
    # GIS/MF6 work because the breakthrough readout below read the single
    # `ext_cell`, which for a distributed sink is the concentration at ONE
    # CELL OF THE SUPPORT, not the extracted concentration. That readout is
    # now the flux-weighted mixture (`_flux_weighted_breakthrough`, wired in
    # below), so a positive radius can be built, solved, and read
    # meaningfully. `sink_support_m` was already part of `params` (the
    # cache-identity dict, below) before this milestone -- see the comment
    # there -- so a positive value reaching the cache lookup for the first
    # time is exactly the previously-untested behaviour
    # `test_sink_support_m_changes_the_cache_identity_cold_and_warm_both_directions`
    # closes (S9b could only test this statically, since the raise fired
    # first). The WEL construction itself is unchanged from S9b
    # (`add_flow_model`, `test_t1_sink_support_wel.py`).

    # T1 S8 (brief Section 3): only the id this module's own call site
    # understands -- "legacy_base" belongs to transport_base_model, not here.
    if courant_profile not in ("legacy_srcpulse", "exp_v1"):
        raise ValueError(
            f"courant_profile must be 'legacy_srcpulse' or 'exp_v1' (got "
            f"{courant_profile!r})")

    if R < 1.0:
        raise ValueError(f"R must be >= 1.0 (got {R!r})")
    if lam < 0.0:
        raise ValueError(f"lam must be >= 0.0 (got {lam!r})")
    if alpha_L is not None and alpha_L <= 0.0:
        raise ValueError(f"alpha_L must be > 0 (got {alpha_L!r})")
    if rho_b <= 0.0:
        raise ValueError(f"rho_b must be > 0 (got {rho_b!r})")
    if mass_g <= 0.0:
        raise ValueError(f"mass_g must be > 0 (got {mass_g!r})")
    if solubility_mgL <= 0.0:
        raise ValueError(f"solubility_mgL must be > 0 (got {solubility_mgL!r})")
    if cr_target <= 0.0:
        raise ValueError(f"cr_target must be > 0 (got {cr_target!r})")
    if nstp_cap < 1:
        raise ValueError(f"nstp_cap must be >= 1 (got {nstp_cap!r})")
    if pulse_days <= 0.0:
        raise ValueError(f"pulse_days must be > 0 (got {pulse_days!r})")
    if total_days <= pulse_days:
        raise ValueError(
            f"total_days ({total_days!r}) must be > pulse_days ({pulse_days!r}); "
            "period 1 (post-pulse migration) would otherwise have zero/negative length")

    # T1 S3a: resolve refine_radii=/mesh_spec= to ONE MeshSpec (ValueError if
    # both given) and refuse >1 level up front (NotImplementedError naming
    # S3b), before any GIS / MF6 work.
    spec = _resolve_mesh_spec(refine_radii=refine_radii, mesh_spec=mesh_spec)
    _require_single_level(spec)

    alpha_L_eff = float(LOCKED_PARAMS["alh"]) if alpha_L is None else float(alpha_L)
    # Derive the transverse ratio FROM LOCKED_PARAMS (currently 1.0 / 10.0 = 0.1)
    # rather than hardcoding "/ 10.0" -- that hardcode previously matched the
    # locked ratio only by coincidence, and silently ignored LOCKED_PARAMS["ath1"].
    alpha_T_eff = alpha_L_eff * (float(LOCKED_PARAMS["ath1"]) / float(LOCKED_PARAMS["alh"]))
    porosity = float(LOCKED_PARAMS["porosity"])
    Kd = (float(R) - 1.0) * porosity / float(rho_b) if R > 1.0 else 0.0

    case_ws = Path(case_ws) if case_ws is not None else _default_case_ws()
    case_ws.mkdir(parents=True, exist_ok=True)

    # GIS content hashes are cheap (local file reads; `download_named_file` is
    # a cache hit whenever the files are already local) and known WITHOUT a
    # corridor build, unlike the winning retry radius -- so they fold into the
    # pre-solve cache identity (`params`) directly, while the full effective
    # `mesh_hash` (which needs the winning radius) is only known after
    # `refine_corridor` runs and is folded into `run_hash` below instead.
    boundary_path, rivers_path = _gis_source_paths()

    params = dict(mass_g=float(mass_g), pulse_days=float(pulse_days),
                  total_days=float(total_days), solubility_mgL=float(solubility_mgL),
                  alpha_L=alpha_L_eff, R=float(R), rho_b=float(rho_b), lam=float(lam),
                  # T1 S5 (brief Sec 4 exit criterion 7): the footprint radius
                  # must be part of the cache identity -- the cache digest is
                  # embedded in the filename, so a run at one radius must
                  # never resolve to a cache file a different radius wrote.
                  footprint_radius_m=float(footprint_radius_m),
                  # T1 S9b (brief Sec 3 "Cache identity"): folds in exactly
                  # like footprint_radius_m above -- with S7 dropped,
                  # hash-folding IS the isolation between a sentinel run and
                  # a (currently unreachable past the NotImplementedError
                  # above) supported run.
                  sink_support_m=float(sink_support_m),
                  cr_target=float(cr_target), nstp_cap=int(nstp_cap),
                  # T1 S8 (brief Section 2.3): the selected courant_nstp
                  # policy must be part of the cache identity, exactly as
                  # footprint_radius_m is above -- a run under one profile
                  # must never resolve to a cache file the other wrote. The
                  # digest is in the filename, so a stale cache is bypassed,
                  # never migrated or rejected.
                  courant_profile=str(courant_profile),
                  # T1 S3a: the DECLARED mesh identity (brief Section 2.1) --
                  # every MeshSpec field (base_cell_size, levels, retry_radii)
                  # folds in here, replacing the old raw refine_radii list.
                  mesh_spec_hash=mesh_spec_hash(spec),
                  # ...and the GIS content that shapes the EFFECTIVE mesh, so a
                  # boundary/river edit busts this cache too (exit criterion 4).
                  gis_boundary_sha256=_file_content_hash(boundary_path),
                  gis_rivers_sha256=_file_content_hash(rivers_path),
                  # Fold a snapshot of LOCKED_PARAMS into the cache identity so an
                  # edit to LOCKED_PARAMS (porosity, scheme, xt3d_off, diffc,
                  # base_cell_size, refined_cell_size, time_units, ath1, ...) busts
                  # every existing cache instead of being silently ignored.
                  # json.dumps(..., sort_keys=True) below sorts this nested dict's
                  # keys too, so the hash is deterministic regardless of
                  # LOCKED_PARAMS's declaration order.
                  locked=dict(LOCKED_PARAMS),
                  # Fold a fingerprint of the model SOURCE into the cache identity
                  # too.  LOCKED_PARAMS only covers edits to that one dict --
                  # editing DOUBLET_Q, SPILL_UPGRADIENT_M, INJ_XY/ABS_XY, the Kd
                  # formula, the MST decay wiring, SRC cell placement,
                  # _courant_nstp, or _mass_balance would otherwise leave the
                  # hash (and every warm cache, notebook users included) unchanged
                  # while the model itself changed underneath it.  `model_io_utils`
                  # is in the fingerprint because it BUILDS the refined grid
                  # (mio.build_refined_gwf_model): an edit to grid generation
                  # changes this model just as surely as an edit here does.
                  src_sha=_src_sha(),
                  # A fingerprint of the calibrated flow DATA itself (not its
                  # source): the 1,080->2,160 m³/d recalibration changed the
                  # downloaded flow field without touching src_sha, so this is what
                  # busts the warm cache on that change.
                  flow_fp=mio.calibrated_flow_fingerprint())
    cache_hash = hashlib.sha1(
        json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    cache = case_ws / f"srcpulse_cache_{cache_hash}.npz"
    if cache.exists() and not force:
        cached = _load_cache(cache, params)
        if cached is not None:
            return cached

    # ---- load + refine (the visible builders; SIGILL retry stays inside) ----
    cgwf, boundary, rivers, exe = load_limmat_flow()
    grid = refine_corridor(cgwf, boundary, rivers, mesh_spec=spec, case_ws=case_ws,
                           footprint_radius_m=footprint_radius_m)
    ncpl = grid["ncpl"]
    csz = grid["cellsize"]
    heads_ref = grid["heads"]; botm_ref = grid["botm"]
    injc = grid["inj_cell"]; extc = grid["ext_cell"]
    corridor_mask = grid["corridor_mask"]
    refine_radius_used = grid["refine_radius_used"]
    u_reg = np.array(grid["u_reg"], float)
    spill_xy = grid["spill_xy"]
    # T1 S5 (brief Sec 1-3): area-weighted per-cell rates, not an equal
    # split -- see `_footprint_rates`'s docstring for the sentinel/positive-
    # radius distinction and what `smassrate` means with unequal rates.
    src_cells, per_cell_rates, smassrate = _footprint_rates(grid, mass_g, pulse_days)
    n_src = len(src_cells)

    # T1 S3a (brief Section 3, location "demo coupled sim"): the coupled sim's
    # workspace is content-addressed by `run_hash` -- `params` (the pre-solve
    # identity) with the DECLARED `mesh_spec_hash` swapped for the EFFECTIVE
    # `mesh_hash` now that `refine_corridor` has revealed the winning retry
    # radius, so two runs whose declared spec+GIS resolve to the SAME winning
    # radius (the common, deterministic case) reuse one directory, and two
    # that resolve differently never collide. `new_sim` itself is unchanged
    # (still appends "sim" under whatever it is given -- see
    # test_public_builders_compose_to_build_srcpulse_demo, which calls it
    # directly and depends on that); passing it the hash-keyed parent here is
    # what makes the FINAL sim directory content-addressed.
    run_params = dict(params)
    run_params["mesh_hash"] = grid["mesh_hash"]
    run_hash = hashlib.sha1(
        json.dumps(run_params, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    run_ws = case_ws / f"sim_{run_hash}"

    def _make_sim(nstp_per_period):
        """Compose the public builders into one coupled GWF+GWT solve."""
        sim = new_sim(run_ws, pulse_days=pulse_days, total_days=total_days,
                      nstp_per_period=nstp_per_period, exe=exe)
        gwf = add_flow_model(sim, grid, sink_support_m=sink_support_m)
        gwt = add_transport_model(sim, gwf, grid, mass_g=mass_g, pulse_days=pulse_days,
                                  R=R, rho_b=rho_b, lam=lam, alpha_L=alpha_L_eff)
        ok, buf, sim = couple_and_run(sim, gwf, gwt, grid, run_ws)
        return sim, gwf, gwt, ok, buf

    # ---- pilot: read velocity, size Courant, then production ----
    sim, gwf, gwt, ok, buf = _make_sim(20)
    if not ok:
        raise RuntimeError("pilot run failed; listing tail:\n"
                           + _run_failure_tail(run_ws / "sim", buf))
    spd = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    vmag = np.sqrt(spd["qx"] ** 2 + spd["qy"] ** 2) / LOCKED_PARAMS["porosity"]
    # T1 S4: pass the ORIGINAL corridor mask + excluded cell ids (source +
    # BOTH doublet wells, inj + ext) rather than a pre-masked array -- see
    # `_courant_nstp_canonical`. T1 S8: `courant_profile` selects the policy;
    # the default ("legacy_srcpulse") is the byte-identical pre-S8 call below.
    # `exp_v1` ignores `exclusions` and needs `mesh_spec` instead of
    # `refined_cell_size` -- see `_courant_nstp_corrected`.
    if courant_profile == "legacy_srcpulse":
        nstp, dt, cr_act, cdiag = _courant_nstp(vmag, csz, corridor_mask, float(total_days),
                                                cr_target, nstp_cap,
                                                exclusions=src_cells + [injc, extc])
    else:
        nstp, dt, cr_act, cdiag = _courant_nstp_canonical(
            vmag, csz, corridor_mask, float(total_days), exclusions=src_cells + [injc, extc],
            cr_target=cr_target, nstp_cap=nstp_cap,
            refined_cell_size=float(LOCKED_PARAMS["refined_cell_size"]),
            mesh_spec=spec, profile=courant_profile)

    sim, gwf, gwt, ok, buf = _make_sim(nstp)
    if not ok:
        raise RuntimeError("production run failed; listing tail:\n"
                           + _run_failure_tail(run_ws / "sim", buf))

    # ---- breakthrough at the extraction well/support (T1 S9c) ----
    cobj = gwt.output.concentration(); times = np.array(cobj.get_times())
    # T1 S9b (brief Sec 2.2): the apportionment ACTUALLY applied by the WEL
    # construction in `add_flow_model` -- read back from the BUILT
    # stress-period data on `gwf`'s own "absw" package via
    # `_wel_support_cells`, never recomputed in parallel from
    # `sink_support_m`/`DOUBLET_Q` a second time (T0_0 Sec 3: an independent
    # re-derivation is exactly how a "false record" gets written). At the
    # sentinel (`sink_support_m == 0.0`) this is
    # `[(ext_cell, -abs(DOUBLET_Q))]`, sorted ascending (trivially, with one
    # entry) -- the frozen identity default (`T0_0...` Sec 3). Computed HERE
    # (moved up from after the mass-balance section, pre-S9c) because the
    # flux-weighted readout below needs it before `bt` can be built.
    sink_support_cells = _wel_support_cells(gwf, pname="absw")
    _sink_cells = [c for c, _ in sink_support_cells]
    _prescribed_sink_rates = dict(sink_support_cells)
    # T1 S9c (brief Sec 2.1): weights are the REALIZED per-cell extraction
    # flow off the solved GWF budget, not the rate handed to
    # `ModflowGwfwel` -- see `_realized_extraction_flows`'s docstring for
    # why one budget read is sufficient (GWF is steady-state). Raises if the
    # realized flow diverges from what was prescribed, or has the wrong
    # sign (`_validate_realized_sink_flows`).
    _realized_sink_rates = _realized_extraction_flows(gwf, pname="absw")
    _validate_realized_sink_flows(_prescribed_sink_rates, _realized_sink_rates)
    bt = _flux_weighted_breakthrough(cobj, times, _sink_cells, _realized_sink_rates)
    peak = float(bt.max()) if bt.size else float("nan")
    # `arrival_day = times[argmax(bt)]` with no guard is wrong-but-plausible in
    # two degenerate cases: (1) the plume never arrives (bt is all-zero) ->
    # argmax(bt) is 0 -> arrival is reported as "day <first output time>", not
    # "never"; (2) the breakthrough curve is STILL RISING at the end of a
    # too-short window -> the last sample (not a real peak) is reported as the
    # arrival.  Guard (1) with `peak <= 0.0` -> NaN; flag (2) via
    # `peak_at_last_step` below so callers (the notebook) can warn instead of
    # silently trusting a still-rising curve's last point.
    peak_at_last_step = bool(bt.size and int(np.argmax(bt)) == bt.size - 1)
    arrival = (float(times[int(np.argmax(bt))]) if (bt.size and peak > 0.0)
               else float("nan"))

    # ---- emergent source-cell concentration vs solubility ----
    # T1 S5 (brief Sec 3.2): with unequal per-cell rates, `src_cells[0]` is
    # merely the lowest cell index -- physically arbitrary. The BINDING cell
    # is the one maximising rate_i / q_cell_i (the highest emergent
    # concentration, where a solubility limit actually binds); ties break to
    # the lowest cell index. Each per-candidate formula below is UNCHANGED
    # from pre-S5 -- only generalised from a hardcoded `src_cells[0]` to
    # every candidate -- so at the sentinel (one cell) the max over one cell
    # IS that cell and every quantity below is byte-identical to before.
    q_src_all = [float(np.hypot(spd["qx"][c], spd["qy"][c])) for c in src_cells]  # Darcy [m/d]
    b_src_all = [float(max(heads_ref[c] - botm_ref[0][c], 0.1)) for c in src_cells]
    ds_src_all = [float(csz[c]) for c in src_cells]
    q_cell_all = [max(q * ds * b, 1e-6)                       # throughflow [m^3/d]
                 for q, ds, b in zip(q_src_all, ds_src_all, b_src_all)]
    bcell = _binding_cell(src_cells, per_cell_rates, q_cell_all)
    bidx = src_cells.index(bcell)
    q_src = q_src_all[bidx]; b_src = b_src_all[bidx]; ds_src = ds_src_all[bidx]
    q_cell = q_cell_all[bidx]
    emergent_C = per_cell_rates[bidx] / q_cell                # [g/m^3] == [mg/L]
    solubility_ok = bool(emergent_C < solubility_mgL)
    sol_margin = float(solubility_mgL / emergent_C) if emergent_C > 0 else float("inf")

    # ---- mass balance from the binary GWT budget (gwt.cbc) ----
    mb = _mass_balance(run_ws / "sim" / "gwt.cbc")

    # ---- grid Peclet on the corridor (uses the EFFECTIVE dispersivities) ----
    csz_corr = csz[corridor_mask]
    PeL_min = float(csz_corr.min() / alpha_L_eff)
    PeL_max = float(csz_corr.max() / alpha_L_eff)
    PeT_min = float(csz_corr.min() / alpha_T_eff)
    PeT_max = float(csz_corr.max() / alpha_T_eff)

    # cr_capped must flag BOTH ways the target Courant number can be missed:
    # (a) Cr_actual overshoots cr_target (the old `cr_act > 1.001` check), and
    # (b) nstp hit nstp_cap and truncated the step count before cr_target was
    # reached at all (e.g. nstp==nstp_cap with cr_act=0.96 > cr_target=0.9 --
    # the old check reports "not capped" even though the cap is exactly why
    # the target was missed).  `nstp >= nstp_cap` catches both: case (a) drives
    # nstp up until it saturates at the cap, and case (b) IS the cap binding.
    cr_capped = bool(nstp >= nstp_cap)
    if cr_capped:
        warnings.warn(
            f"srcpulse demo: nstp hit nstp_cap ({nstp_cap}); the target Courant "
            f"number cr_target={cr_target:g} may not have been reached "
            f"(Cr_actual={cr_act:.3f}). Diagnostics/results may be under-resolved "
            "in time -- consider raising nstp_cap.", RuntimeWarning, stacklevel=2)

    meta = dict(ncpl=ncpl, nstp=nstp, dt=dt, Cr=cr_act, n_src=n_src,
                q_src_darcy=q_src, b_src=b_src, ds_src=ds_src, q_cell=q_cell,
                v_bind=cdiag["v_bind"], ds_bind=cdiag["ds_bind"],
                ds_true_min=cdiag["ds_true_min"], courant_floor=cdiag["floor"],
                refine_radius_used=refine_radius_used, u_reg=tuple(u_reg),
                cr_capped=cr_capped, peak_at_last_step=peak_at_last_step,
                sink_support_cells=sink_support_cells)

    result = SrcPulseDemo(
        times=times, breakthrough=bt, peak_mgL=peak, arrival_day=arrival,
        mass_balance=mb, solubility_ok=solubility_ok, emergent_C_mgL=emergent_C,
        solubility_mgL=float(solubility_mgL), solubility_margin=sol_margin,
        PeL_min=PeL_min, PeL_max=PeL_max, PeT_min=PeT_min, PeT_max=PeT_max,
        mass_g=float(mass_g), pulse_days=float(pulse_days), total_days=float(total_days),
        smassrate_gpd=smassrate, src_cells=src_cells, ext_cell=extc, inj_cell=injc,
        spill_xy=(float(spill_xy[0]), float(spill_xy[1])),
        alpha_L=alpha_L_eff, alpha_T=alpha_T_eff, R=float(R), rho_b=float(rho_b),
        Kd=float(Kd), lam=float(lam),
        # T1 S9b/S9c: the REAL parameter, threaded through -- a positive
        # value now reaches this line (S9c lifted the raise above) and
        # `breakthrough` above is the flux-weighted mixture for it.
        # `t_peak` is NOT passed here (init=False; derived in __post_init__
        # from arrival_day above).
        sink_support_m=float(sink_support_m), meta=meta)

    _save_cache(cache, result, params)
    return result


# ---------------------------------------------------------------------------
# mass balance from the GWT listing file
# ---------------------------------------------------------------------------
_MB_NUMERIC_KEYS = (
    "src_in_g", "well_out_g", "boundary_out_g", "storage_g", "decay_g",
    "total_in_g", "total_out_g", "pct_imbalance", "grouped_residual_g",
)
# Budget-record substrings -> mass-balance group. Each GWT budget record name
# (SRC, WEL, RIV, CHD, RCHA, STORAGE-AQUEOUS/-SORBED, DECAY-AQUEOUS/-SORBED) is
# classified by the FIRST substring it contains. FLOW-JA-FACE / DATA-SPDIS are
# internal/GWF and excluded.
_MB_GROUPS = ("SRC", "WEL", "RIV", "CHD", "RCH", "STORAGE", "DECAY")


def _mass_balance(gwt_cbc: Union[str, Path]) -> Dict[str, float]:
    """Cumulative GWT mass budget: SRC in, well out, boundary out, storage, decay, % imbalance.

    Reads the BINARY GWT budget (``gwt.cbc``) and integrates each package's
    per-timestep flow rate [g/d] over the run (rate x dt) to recover cumulative
    mass [g]. Terms are grouped exactly as before: source (SRC), extraction-well
    out (WEL), boundary out (RIV + CHD + RCHA), storage (STORAGE-AQUEOUS always;
    STORAGE-SORBED too when R > 1), decay (DECAY-AQUEOUS when lam > 0; DECAY-SORBED
    too when R > 1). Units are grams (model g/m^3, m/day).

    Why the binary budget, not the text listing (``Mf6ListBudget`` on ``gwt.lst``):
    at high pumping (2,160 m3/d) a cumulative boundary-mass term overflows the
    listing's fixed-width Fortran field ("error casting in cumu for CHD to float"),
    so the listing parse silently returns NaN for that term -> NaN pct_imbalance.
    The binary budget stores float64 rates with no field-width limit, so it is
    robust at any magnitude. Cumulative = sum_i(rate_i * dt_i) reproduces MF6's own
    cumulative (rate is constant over each step).

    ``pct_imbalance`` is the percent discrepancy of the integrated TOTAL_IN vs
    TOTAL_OUT. ``grouped_residual_g`` is a self-check: the sum of the grouped
    terms above reconciled against the all-records total; ~0 g iff the grouping
    captured every budget record without missing or double-counting one.
    """
    from flopy.utils import CellBudgetFile
    try:
        cbc = CellBudgetFile(str(gwt_cbc))
        times = list(cbc.get_times())
        raw_names = cbc.get_unique_record_names(decode=True)
        names = [n.decode() if isinstance(n, bytes) else n for n in raw_names]
        names = [n.strip() for n in names]
    except Exception as e:                       # keep the demo robust
        # Return the expected NUMERIC keys as NaN alongside "error" so the
        # notebook's `f"{v:14.4g}"` over mass_balance.values() does not crash on a
        # str and hide the REAL read error behind a formatting traceback.
        return {"error": repr(e), **{k: float("nan") for k in _MB_NUMERIC_KEYS}}

    acc = {g: [0.0, 0.0] for g in _MB_GROUPS}    # group -> [cum_in_g, cum_out_g]
    other = [0.0, 0.0]                            # records matching NO group (see below)
    total_in_all = total_out_all = 0.0
    t_prev = 0.0
    for t in times:
        dt = t - t_prev
        t_prev = t
        for name in names:
            u = name.upper()
            if "FLOW-JA-FACE" in u or "DATA-SPDIS" in u:
                continue
            try:
                data = cbc.get_data(text=name, totim=t)
            except Exception:
                continue
            if not data:
                continue
            arr = data[0]
            if getattr(arr, "dtype", None) is not None and arr.dtype.names \
                    and "q" in arr.dtype.names:
                q = np.asarray(arr["q"], dtype=float)
            else:
                q = np.asarray(arr, dtype=float).ravel()
            q_in = float(q[q > 0].sum()) * dt
            q_out = float(-q[q < 0].sum()) * dt
            total_in_all += q_in
            total_out_all += q_out
            grp = next((g for g in _MB_GROUPS if g in u), None)
            if grp is not None:
                acc[grp][0] += q_in
                acc[grp][1] += q_out
            else:
                # Ungrouped record. The BINARY GWT budget aggregates the SSM
                # boundary+well solute flux under a single record (e.g. "SSM")
                # rather than per-package (WEL/CHD/RIV/RCHA) as the text listing
                # does, so the dominant sink (the extraction well capturing the
                # plume) matches none of _MB_GROUPS. Fold it into the boundary
                # term so the budget still CLOSES (Σ grouped == Σ all-records).
                other[0] += q_in
                other[1] += q_out

    src_in, src_out = acc["SRC"]
    wel_in, wel_out = acc["WEL"]
    riv_in, riv_out = acc["RIV"]
    chd_in, chd_out = acc["CHD"]
    rch_in, rch_out = acc["RCH"]
    sto_in, sto_out = acc["STORAGE"]
    dcy_in, dcy_out = acc["DECAY"]

    denom = 0.5 * (total_in_all + total_out_all)
    pct = 100.0 * (total_in_all - total_out_all) / denom if denom != 0 else float("nan")

    grouped_in = (src_in + wel_in + riv_in + chd_in + rch_in + sto_in + dcy_in
                  + other[0])
    grouped_out = (src_out + wel_out + riv_out + chd_out + rch_out + sto_out + dcy_out
                   + other[1])
    grouped_residual_g = float(abs(grouped_in - total_in_all)
                               + abs(grouped_out - total_out_all))

    return {
        "src_in_g": src_in,
        "well_out_g": wel_out,
        # includes any SSM-aggregated boundary/well sink (see the `other` bucket)
        "boundary_out_g": riv_out + chd_out + rch_out + other[1],
        "storage_g": sto_out - sto_in,        # net into storage (accumulation) [g]
        "decay_g": dcy_out - dcy_in,          # net mass removed by decay [g] (0 if no decay)
        "total_in_g": total_in_all,
        "total_out_g": total_out_all,
        "pct_imbalance": pct,
        "grouped_residual_g": grouped_residual_g,
    }


# ---------------------------------------------------------------------------
# cache (solve-free re-call)
# ---------------------------------------------------------------------------
def _save_cache(path: Path, r: SrcPulseDemo, params: Dict[str, Any]) -> None:
    np.savez(str(path), times=r.times, breakthrough=r.breakthrough,
             peak_mgL=r.peak_mgL, arrival_day=r.arrival_day,
             mass_balance=r.mass_balance, solubility_ok=r.solubility_ok,
             emergent_C_mgL=r.emergent_C_mgL, solubility_mgL=r.solubility_mgL,
             solubility_margin=r.solubility_margin,
             PeL_min=r.PeL_min, PeL_max=r.PeL_max, PeT_min=r.PeT_min, PeT_max=r.PeT_max,
             mass_g=r.mass_g, pulse_days=r.pulse_days, total_days=r.total_days,
             smassrate_gpd=r.smassrate_gpd, src_cells=np.array(r.src_cells),
             ext_cell=r.ext_cell, inj_cell=r.inj_cell, spill_xy=np.array(r.spill_xy),
             alpha_L=r.alpha_L, alpha_T=r.alpha_T, R=r.R, rho_b=r.rho_b, Kd=r.Kd, lam=r.lam,
             # T1 S2: the two new top-level fields must round-trip too -- an
             # existing test (test_cache_round_trip_fidelity) asserts every
             # CURRENT dataclass field has a matching npz key.
             sink_support_m=r.sink_support_m, t_peak=r.t_peak,
             meta=r.meta, locked=r.locked, params=params, allow_pickle=True)


def _load_cache(path: Path, params: Dict[str, Any]) -> Optional[SrcPulseDemo]:
    # The WHOLE body (params-key check, value comparison, AND the SrcPulseDemo
    # construction/z[...] reads below) lives inside this one try.  Previously
    # only np.load + z["params"].item() were guarded: the 29 z[...] reads below
    # sat OUTSIDE the try, protected only by the params key-set check above.
    # That means a future dataclass field added WITHOUT touching the hashed
    # `params` dict would pass the key-set guard on every existing warm cache
    # and then KeyError on the read -- crashing instead of cleanly rebuilding.
    # Wrapping everything means any bad/incomplete/legacy cache just MISSES.
    try:
        z = np.load(str(path), allow_pickle=True)
        stored = dict(z["params"].item())
        # A missing/extra key must NOT silently count as a match (e.g.
        # stored.get(k, nan) comparing "> 1e-9" as False for a missing key
        # would look like equality).
        if set(stored) != set(params):
            return None                      # key set changed -> rebuild
        for k, v in params.items():
            sv = stored[k]
            if k == "refine_radii":
                # non-scalar entry: compare as arrays, not via a bare "abs(list - list)".
                sv_arr = np.asarray(sv, dtype=float)
                v_arr = np.asarray(v, dtype=float)
                if sv_arr.shape != v_arr.shape or np.any(np.abs(sv_arr - v_arr) > 1e-9):
                    return None
            elif k == "locked":
                # non-scalar (nested dict) entry: mixed str/float/bool values, so
                # compare via a canonical JSON dump rather than a bare "==" (which
                # would work here too, but this stays robust if a future
                # LOCKED_PARAMS value becomes a list/array).
                if json.dumps(sv, sort_keys=True) != json.dumps(v, sort_keys=True):
                    return None
            elif isinstance(v, str) or isinstance(sv, str):
                # e.g. src_sha: a plain string value.  The numeric branch below
                # does `abs(float(sv) - float(v))`, which would crash (or worse,
                # silently coerce) on a non-numeric string -- compare by equality.
                if str(sv) != str(v):
                    return None
            else:
                if abs(float(sv) - float(v)) > 1e-9:
                    return None              # params changed -> rebuild

        # T1 S2 (brief Section 3.1): `t_peak` is `init=False`, so it cannot be
        # passed to the SrcPulseDemo constructor below -- instead the STORED
        # value is read and VALIDATED against the STORED `arrival_day`,
        # NaN-aware (arrival_day is legitimately NaN when the plume never
        # arrives; see the guard in build_srcpulse_demo). A mismatch means the
        # cached alias is corrupt or stale relative to the value it aliases --
        # that is a CACHE MISS, never a silent repair (an override here would
        # mask a genuine JAG-era divergence between t_peak and arrival_day).
        stored_t_peak = float(z["t_peak"])
        stored_arrival = float(z["arrival_day"])
        both_nan = math.isnan(stored_t_peak) and math.isnan(stored_arrival)
        if not both_nan and stored_t_peak != stored_arrival:
            return None                      # stored alias mismatch -> rebuild

        return SrcPulseDemo(
            times=z["times"], breakthrough=z["breakthrough"],
            peak_mgL=float(z["peak_mgL"]), arrival_day=float(z["arrival_day"]),
            mass_balance=dict(z["mass_balance"].item()), solubility_ok=bool(z["solubility_ok"]),
            emergent_C_mgL=float(z["emergent_C_mgL"]), solubility_mgL=float(z["solubility_mgL"]),
            solubility_margin=float(z["solubility_margin"]),
            PeL_min=float(z["PeL_min"]), PeL_max=float(z["PeL_max"]),
            PeT_min=float(z["PeT_min"]), PeT_max=float(z["PeT_max"]),
            mass_g=float(z["mass_g"]), pulse_days=float(z["pulse_days"]),
            total_days=float(z["total_days"]), smassrate_gpd=float(z["smassrate_gpd"]),
            src_cells=[int(c) for c in z["src_cells"]], ext_cell=int(z["ext_cell"]),
            inj_cell=int(z["inj_cell"]),
            # Cast to plain Python float (not np.float64): the build path
            # produces Python floats, and _save_cache round-trips through
            # np.array(r.spill_xy) -- without this cast, a cache HIT returns a
            # tuple of np.float64 that compares equal (np.float64(x) == x) but
            # is a different TYPE, which bites e.g. json.dumps(demo.spill_xy).
            spill_xy=(float(z["spill_xy"][0]), float(z["spill_xy"][1])),
            alpha_L=float(z["alpha_L"]), alpha_T=float(z["alpha_T"]),
            R=float(z["R"]), rho_b=float(z["rho_b"]), Kd=float(z["Kd"]), lam=float(z["lam"]),
            # T1 S2: sink_support_m IS init-enabled (unlike t_peak) -- pass the
            # stored value through so it round-trips like every other field.
            sink_support_m=float(z["sink_support_m"]),
            meta=dict(z["meta"].item()), locked=dict(z["locked"].item()))
    except Exception:
        return None


# =============================================================================
# T1 S10 (DESIGN_DOCS/T1_S10_brief.md v2): the GWF-grid sensitivity arm.
#
# WHAT THIS IS (brief Sec 1): the "common flow" control -- running transport
# for several meshes on ONE shared flow field -- is DESCOPED (MF6 GWT requires
# the GWF discretisation; a non-matching-grid remapper is out of proportion to
# a teaching artifact). The replacement is THIS arm: flow solved and reported
# PER MESH, so the arm DOCUMENTS that the flow field changed rather than
# isolating it. Each mesh carrying its own GWF solve is inherent to the
# design, not a defect to "optimise" away.
#
# 🔴 THE CEILING IS NAMED BY CONSTRUCTION (brief Sec 1, quoting
# `DOCUMENTATION/contracts/T0_2b_metrics_and_causal_rule.md` Sec 4.2): "any
# comparison in which the sink support OR the flow field also changed" is
# insufficient for a `cause` claim. This arm IS such a comparison, by design,
# so it can NEVER license `cause` -- a grid comparison carrying it stays
# `hypothesis`. `NON_ISOLATION_STATEMENT` / `CLAIM_CEILING` below encode that
# in the code (not merely in this comment), `GwfGridSensitivityArmResult.
# __post_init__` makes it structurally impossible to construct a result
# claiming otherwise, and every one of `to_dict` / `to_json` / `summary_text`
# / `deltas_table` (the arm's four reporting/export paths) carries both.
#
# 🔴 QUANTIFIED FLOW DELTAS ARE THE SUBSTANCE (brief Sec 1.1): recording
# *that* flow changed is worth nothing; `GwfMeshFlowDelta` records HOW MUCH,
# per mesh pair (each non-reference mesh vs the reference mesh), in physical
# units AND relative terms, for the four "at minimum" diagnostics the brief
# names: Darcy-flux magnitude at the source and receptor, the head
# difference across the corridor, and the extraction-cell throughflow.
#
# 🔴 NO IMPORT OF `transport_prt_capture` (brief Sec 2.1): that module already
# imports THIS one (`transport_prt_capture.py:173`), so the reverse edge
# would close a cycle; `test_t1_src_closure.py::DEMO_EXPECTED` pins this
# module's transitive `_SUPPORT/src` closure to EXACTLY 7 members, with the
# PRT closure a strict superset -- an import here would break both. Authority
# A13 names only this one module. The capture fingerprint is therefore
# ACCEPTED AS AN ARGUMENT (`CaptureFingerprintRecord`, injected by the
# caller -- T2's runner, which does import PRT), never computed or imported
# here -- and, per the SAME cycle/closure constraint, `t1_evidence_artifact`
# (home of the frozen Role-group vocabulary this section reuses, `run_role` /
# `grid_role` / `counterpart_run_id`) is likewise not imported: that module's
# own docstring freezes its imports as one-way `artifact -> model`, never the
# reverse. The Role-group STRING VALUES are therefore transcribed as local
# constants below (`_RUN_ROLES`, `_ARM_RUN_ROLE`), not imported -- this is a
# repetition of the same closed vocabulary, not a redefinition of policy. No
# `CONTROL_LABELS` vocabulary is touched or reused anywhere in this section:
# S10 is explicitly NOT a control (brief Sec 3) -- `GwfGridSensitivityArmResult
# .is_control` is always `False`, enforced in `__post_init__`, and
# `analysis_kind` is a plainly-named, non-control discoverability marker.
#
# Nothing in this section is wired into any default call path (`build_
# srcpulse_demo`, `__main__`, or any cached/gated payload) -- T1 ships the
# capability, T2 runs it. Gate coverage is BLIND (brief header): `compare`
# never sees any of this, so `test_t1_gwf_grid_sensitivity.py` is the entire
# safety argument for this step, not a supplement to `compare`.
# =============================================================================

#: T0_2b Sec 5.1 -- the frozen Role-group vocabulary, TRANSCRIBED (never
#: imported -- see the module-comment above) purely to validate the one
#: value this arm ever assigns to `run_role`.
_RUN_ROLES: Tuple[str, ...] = (
    "spatial_series", "temporal_series", "b_control", "pilot", "feasibility_probe",
)
#: This arm's own reading (flagged, brief Sec 3 does not name a specific
#: value): a GWF-grid-sensitivity arm varies MESH, i.e. it is a point in the
#: spatial series -- never `b_control` (S9c's vocabulary, not reused here),
#: `pilot`, `feasibility_probe`, or `temporal_series` (that varies timestep,
#: not mesh).
_ARM_RUN_ROLE = "spatial_series"
#: A non-control, plainly-named discoverability marker (brief Sec 3: "a
#: non-control analysis-kind marker is permitted... discoverability does not
#: imply controlling power"). Never read as a control by anything in this
#: module.
_ANALYSIS_KIND = "gwf_grid_sensitivity"

#: This module's own closed platform vocabulary (flagged -- brief Sec 2.3
#: does not fix a wire format for "Mac" / "Hub"): `"<system>-<machine>"`,
#: lower-cased. A value outside this set is UNSUPPORTED and raises (brief
#: exit criterion 14).
SUPPORTED_PLATFORMS: Tuple[str, ...] = ("darwin-arm64", "linux-x86_64")

#: `DOCUMENTATION/contracts/T0_2b_metrics_and_causal_rule.md` Sec 2.6/2.7 --
#: the frozen 5% relative tolerance `capture_halfwidth_m` is judged against.
#: Transcribed here (this module imports no contract file); a ~24%
#: Mac<->Hub spread against this 5% is WHY brief Sec 2.3 requires a measured
#: repeatability envelope, demonstrably below this value, before ANY
#: fingerprint comparison (even same-platform) is permitted.
TOL_WIDTH_REL = 0.05

#: brief Sec 1: the ceiling this arm's evidence can NEVER exceed, "named by
#: construction" per `T0_2b...` Sec 4.2 -- never `cause`.
CLAIM_CEILING = "hypothesis"

#: brief Sec 1 / exit criterion 1 -- must be IN the code (not merely in this
#: comment block) and asserted by a test; every reporting/export path below
#: carries it verbatim (exit criterion 17).
NON_ISOLATION_STATEMENT = (
    "This arm solves MODFLOW 6 GWF flow SEPARATELY for each mesh -- it does "
    "NOT hold the flow field (or the sink support) common across the meshes "
    "it compares. Per DOCUMENTATION/contracts/T0_2b_metrics_and_causal_rule.md "
    "Sec 4.2, any comparison in which the sink support OR the flow field also "
    "changed can NEVER license a 'cause' claim; a grid comparison carrying "
    "this arm's evidence stays 'hypothesis', by construction. The quantified "
    "flow deltas this arm reports let a reader say the observed transport "
    "difference COINCIDED with these mesh-dependent flow differences, so "
    "transport-grid causation is UNRESOLVED for the meshes that differ "
    "materially -- and identify which meshes have negligible flow deltas "
    "and are therefore better candidates for later isolation work. They do "
    "NOT let a reader say the transport grid caused, explained, or even "
    "dominated the observed difference."
)


# ---------------------------------------------------------------------------
# exceptions -- the fail-closed vocabulary for this section
# ---------------------------------------------------------------------------
class GwfGridSensitivityError(RuntimeError):
    """Base class for every error the T1 S10 GWF-grid sensitivity arm raises."""


class DuplicateMeshIdError(GwfGridSensitivityError):
    """Two (or more) entries in one arm share the same `mesh_id` (exit
    criterion 13)."""


class MeshSolveFailedError(GwfGridSensitivityError):
    """A mesh's GWF solve failed or was partial, and either (a) mesh
    construction itself raised, or (b) `assemble_gwf_grid_sensitivity_arm`
    refuses to record a successful arm from a run set containing an
    unsolved mesh (exit criterion 15)."""


class MalformedFingerprintError(GwfGridSensitivityError):
    """An injected `CaptureFingerprintRecord`'s value is missing, NaN, or
    negative, or a required string field is empty (exit criterion 14)."""


class UnsupportedPlatformError(GwfGridSensitivityError):
    """A platform value outside `SUPPORTED_PLATFORMS` (exit criterion 14)."""


class FingerprintMeshMismatchError(GwfGridSensitivityError):
    """An injected fingerprint names a `mesh_id` different from the arm's
    own mesh -- fingerprints cannot be swapped between meshes (exit
    criterion 12)."""


class FingerprintFlowIncompatibleError(GwfGridSensitivityError):
    """An injected fingerprint's `flow_identity` does not match the arm's
    own solved flow identity (brief Sec 2.2, exit criterion 2/5/11)."""


class CrossPlatformFingerprintComparisonError(GwfGridSensitivityError):
    """Two fingerprints recorded on different platforms were compared (exit
    criterion 3)."""


class MissingRepeatabilityEnvelopeError(GwfGridSensitivityError):
    """A fingerprint comparison was attempted with no `RepeatabilityEnvelope`
    at all (brief Sec 2.3, exit criterion 10)."""


class RepeatabilityEnvelopeMismatchError(GwfGridSensitivityError):
    """The supplied envelope was measured on a different platform than the
    fingerprints being compared."""


class RepeatabilityEnvelopeInsufficientError(GwfGridSensitivityError):
    """The supplied envelope's spread is not demonstrably below
    `TOL_WIDTH_REL` (brief Sec 2.3, exit criterion 10)."""


# ---------------------------------------------------------------------------
# small numeric helpers
# ---------------------------------------------------------------------------
def _rel_delta(delta: float, reference: float) -> Optional[float]:
    """Relative delta = `delta / reference`; `None` (never `inf`/`nan`) when
    `reference == 0.0` exactly -- a bare division would either raise or
    produce a non-finite value this section's deterministic JSON export
    cannot represent."""
    if reference == 0.0:
        return None
    return float(delta) / float(reference)


def _fmt_rel(rel: Optional[float]) -> str:
    return "n/a (zero reference)" if rel is None else f"{rel * 100.0:+.2f}%"


def current_platform_tag() -> str:
    """This run's platform tag in `SUPPORTED_PLATFORMS`' own format --
    `"<system>-<machine>"`, lower-cased (e.g. `"darwin-arm64"` on a
    developer Mac, `"linux-x86_64"` on JupyterHub)."""
    return f"{platform.system().lower()}-{platform.machine().lower()}"


def flow_identity_string(mesh_id: str, realized_extraction_cells: Sequence[int]) -> str:
    """Canonical flow-identity descriptor (brief Sec 2.1/2.2; this module's
    own construction, flagged -- neither contract quoted in the brief fixes
    an algorithm for this).

    Two solved flow fields share a "flow identity", for the purpose of
    validating an injected capture fingerprint, exactly when this string
    matches -- true whenever the REALIZED extraction-well support cell set
    matches, regardless of *why* it does or doesn't. MODFLOW 6 PRT always
    builds its own hard-coded, single-cell doublet
    (`transport_prt_capture.py:542-545`), which corresponds to a
    realized-support set of exactly one cell; a demo GWF solved at
    `sink_support_m > 0` realizes through MORE than one cell, so the two
    identities differ TODAY -- without this function ever testing
    `sink_support_m > 0` directly (brief Sec 2.2's round-1 finding: that
    would wrongly block a future fingerprint legitimately computed from a
    distributed-support flow, and would miss any OTHER way the two fields
    could diverge). If PRT ever grows a matching distributed-support well,
    the two identity strings would agree again with no change needed here.

    `realized_extraction_cells` MUST come from the SOLVED GWF budget
    (`_realized_extraction_flows`), never the cells merely PRESCRIBED to the
    WEL package -- the same "realized, not configured" ethos S9c already
    applies to breakthrough weighting.
    """
    cells = tuple(sorted(int(c) for c in realized_extraction_cells))
    return _identity_digest({"mesh_id": str(mesh_id),
                             "realized_extraction_support_cells": list(cells)})


# ---------------------------------------------------------------------------
# the injected capture fingerprint -- a TYPED PROVENANCE RECORD (brief Sec
# 2.1), never a bare float
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CaptureFingerprintRecord:
    """A PRT capture-halfwidth fingerprint, INJECTED by the caller (T2's
    runner, which calls `transport_prt_capture.capture_halfwidth_at()`) --
    never computed or imported by this module (brief Sec 2.1). A bare float
    would relocate the coupling to T2 where it is LESS visible and silently
    permit stale, swapped, or independently generated values; this record
    carries the value together with enough provenance for THIS arm to
    validate it against its own run/mesh/flow identity before ever reading
    `value_m` (see `_validate_capture_fingerprint`,
    `assemble_gwf_grid_sensitivity_arm`).

    Structural validity (non-empty strings, a finite non-negative value, a
    supported platform) is enforced HERE, at construction (exit criteria
    14). `mesh_id` / `flow_identity` compatibility with a SPECIFIC arm run
    can only be checked once that arm's own identities are known, so that
    check lives in `_validate_capture_fingerprint`, called from
    `assemble_gwf_grid_sensitivity_arm` (exit criteria 2, 5, 11, 12).

    `compatibility_status` is the PRODUCER's own self-declared status (e.g.
    what PRT believed it was compatible with) -- it is recorded but is
    explicitly NOT authoritative: this arm always independently re-verifies
    `mesh_id` and `flow_identity` itself rather than trusting the
    self-declared string, exactly the same "recompute, never trust a
    declared value verbatim" posture `t1_evidence_artifact.EvidenceRecord.
    provenance_valid` already uses for `run_health.provenance_valid`.
    """

    value_m: float
    platform: str
    producing_run_id: str
    mesh_id: str
    flow_identity: str
    method_id: str
    compatibility_status: str

    def __post_init__(self) -> None:
        if (self.value_m is None or isinstance(self.value_m, bool)
                or not isinstance(self.value_m, (int, float))
                or not math.isfinite(float(self.value_m))):
            raise MalformedFingerprintError(
                "CaptureFingerprintRecord.value_m must be a finite number; got "
                f"{self.value_m!r}")
        if float(self.value_m) < 0.0:
            raise MalformedFingerprintError(
                "CaptureFingerprintRecord.value_m must be non-negative (a "
                f"capture half-width cannot be negative); got {self.value_m!r}")
        for name in ("platform", "producing_run_id", "mesh_id", "flow_identity",
                     "method_id", "compatibility_status"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v.strip():
                raise MalformedFingerprintError(
                    f"CaptureFingerprintRecord.{name} must be a non-empty "
                    f"string; got {v!r}")
        if self.platform not in SUPPORTED_PLATFORMS:
            raise UnsupportedPlatformError(
                f"CaptureFingerprintRecord.platform={self.platform!r} is not "
                f"one of {SUPPORTED_PLATFORMS!r}")


def _validate_capture_fingerprint(fp: "CaptureFingerprintRecord", *, mesh_id: str,
                                  flow_identity: str) -> None:
    """Re-verify an injected fingerprint against THIS arm's own identities
    (brief Sec 2.1: "validates it against the arm's own run/mesh/flow
    identity ... raises on mismatch") -- `CaptureFingerprintRecord.
    __post_init__` already checked internal structural validity; this
    checks EXTERNAL consistency with the specific mesh it is being attached
    to."""
    if fp.mesh_id != mesh_id:
        raise FingerprintMeshMismatchError(
            f"injected capture fingerprint names mesh_id={fp.mesh_id!r}, but "
            f"this arm's own mesh is {mesh_id!r} -- fingerprints cannot be "
            "swapped between meshes (brief exit criterion 12)")
    if fp.flow_identity != flow_identity:
        raise FingerprintFlowIncompatibleError(
            f"injected capture fingerprint's flow_identity={fp.flow_identity!r} "
            f"does not match this arm's own solved flow_identity="
            f"{flow_identity!r} -- the fingerprint's producing run solved a "
            "DIFFERENT flow field than this arm did (brief Sec 2.2: refuse on "
            "flow-identity incompatibility, not on sink_support_m > 0 "
            "directly)")


# ---------------------------------------------------------------------------
# the repeatability envelope + fingerprint comparison -- descriptive-only
# until measured (brief Sec 2.3)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RepeatabilityEnvelope:
    """Evidence a fingerprint comparison is meaningful (brief Sec 2.3):
    replicated runs in FRESH EXECUTIONS, demonstrably below `TOL_WIDTH_REL`.
    Never inferred or defaulted -- always supplied by the caller, from
    actually-measured replicate runs."""

    platform: str
    n_replicates: int
    spread_rel: float
    replicate_run_ids: Tuple[str, ...]

    def __post_init__(self) -> None:
        if self.platform not in SUPPORTED_PLATFORMS:
            raise UnsupportedPlatformError(
                f"RepeatabilityEnvelope.platform={self.platform!r} is not "
                f"one of {SUPPORTED_PLATFORMS!r}")
        if self.n_replicates < 2:
            raise ValueError(
                "RepeatabilityEnvelope.n_replicates must be >= 2 -- a "
                "repeatability envelope needs replicated runs, not a single "
                f"execution; got {self.n_replicates!r}")
        if len(self.replicate_run_ids) != self.n_replicates:
            raise ValueError(
                f"RepeatabilityEnvelope.replicate_run_ids has "
                f"{len(self.replicate_run_ids)} entries but n_replicates="
                f"{self.n_replicates}")
        if len(set(self.replicate_run_ids)) != len(self.replicate_run_ids):
            raise ValueError(
                "RepeatabilityEnvelope.replicate_run_ids must be distinct -- "
                "replicated FRESH EXECUTIONS, not the same run counted twice")
        if not math.isfinite(self.spread_rel) or self.spread_rel < 0.0:
            raise ValueError(
                "RepeatabilityEnvelope.spread_rel must be finite and >= 0; "
                f"got {self.spread_rel!r}")


@dataclass(frozen=True)
class FingerprintComparisonResult:
    """The result of a PERMITTED fingerprint comparison (brief Sec 2.3) --
    `compare_fingerprints` raises rather than returning this whenever the
    comparison is not permitted."""

    a_mesh_id: str
    b_mesh_id: str
    platform: str
    delta_m: float
    delta_rel: Optional[float]
    envelope: "RepeatabilityEnvelope"


def compare_fingerprints(a: "CaptureFingerprintRecord", b: "CaptureFingerprintRecord", *,
                         envelope: Optional["RepeatabilityEnvelope"]
                         ) -> "FingerprintComparisonResult":
    """Compare two capture fingerprints -- DESCRIPTIVE-ONLY (brief Sec 2.3).

    Raises unless ALL of: (1) both fingerprints share the same `platform`
    (a cross-platform comparison always raises, regardless of any envelope);
    (2) a `RepeatabilityEnvelope` is supplied at all; (3) that envelope was
    itself measured on the SAME platform; (4) its `spread_rel` is
    demonstrably below `TOL_WIDTH_REL`. This arm's OWN substance is the
    deterministic flow deltas of `GwfMeshFlowDelta` -- this function exists
    so a caller CANNOT accidentally treat the fingerprint as a discriminator
    without the evidence Sec 2.3 requires; it does not block S10 itself.
    """
    if a.platform != b.platform:
        raise CrossPlatformFingerprintComparisonError(
            "cannot compare capture fingerprints from different platforms "
            f"({a.platform!r} vs {b.platform!r}) -- a ~24% Mac<->Hub spread "
            "makes a cross-platform comparison meaningless regardless of any "
            "repeatability envelope (brief Sec 2.3)")
    if envelope is None:
        raise MissingRepeatabilityEnvelopeError(
            "fingerprint comparison requires a recorded repeatability "
            "envelope (brief Sec 2.3) -- absent one, ANY comparison, "
            "including same-platform, is refused")
    if envelope.platform != a.platform:
        raise RepeatabilityEnvelopeMismatchError(
            f"the supplied repeatability envelope was measured on "
            f"{envelope.platform!r}, not {a.platform!r} -- it cannot support "
            "this comparison")
    if not (envelope.spread_rel < TOL_WIDTH_REL):
        raise RepeatabilityEnvelopeInsufficientError(
            f"the repeatability envelope's spread ({envelope.spread_rel:.4f}) "
            f"is not demonstrably below TOL_WIDTH_REL ({TOL_WIDTH_REL:.4f}) -- "
            "the fingerprint metric stays descriptive-only until a tighter "
            "envelope is measured (brief Sec 2.3)")
    delta_m = float(b.value_m) - float(a.value_m)
    return FingerprintComparisonResult(
        a_mesh_id=a.mesh_id, b_mesh_id=b.mesh_id, platform=a.platform,
        delta_m=delta_m, delta_rel=_rel_delta(delta_m, float(a.value_m)),
        envelope=envelope)


# ---------------------------------------------------------------------------
# per-mesh flow diagnostics + deltas
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MeshFlowDiagnostics:
    """Comparable quantitative flow diagnostics for ONE mesh's solved GWF
    (brief Sec 1.1) -- the "at minimum" four: Darcy-flux magnitude at the
    source and receptor, head difference across the corridor, and
    extraction-cell throughflow. `flow_identity` is `flow_identity_string`'s
    output for THIS mesh's actually-realized extraction support (empty only
    when `solved` is `False`, i.e. never computed)."""

    mesh_id: str
    mesh_spec_hash: str
    q_source_darcy_m_d: float
    q_receptor_darcy_m_d: float
    head_diff_corridor_m: float
    extraction_throughflow_m3d: float
    flow_identity: str
    platform: str
    solved: bool
    solver_status: str

    def __post_init__(self) -> None:
        if not isinstance(self.mesh_id, str) or not self.mesh_id.strip():
            raise ValueError("MeshFlowDiagnostics.mesh_id must be a non-empty string")
        if not isinstance(self.solver_status, str) or not self.solver_status.strip():
            raise ValueError(
                "MeshFlowDiagnostics.solver_status must be a non-empty string "
                "(brief exit criterion 15: solver failure must be handled "
                "explicitly, never silent)")
        if self.solved:
            for name in ("q_source_darcy_m_d", "q_receptor_darcy_m_d",
                         "head_diff_corridor_m", "extraction_throughflow_m3d"):
                v = getattr(self, name)
                if v is None or not math.isfinite(float(v)):
                    raise ValueError(
                        f"MeshFlowDiagnostics.{name} must be finite for a "
                        f"solved mesh; got {v!r}")
            if not self.flow_identity:
                raise ValueError(
                    "MeshFlowDiagnostics.flow_identity must be non-empty for "
                    "a solved mesh")


@dataclass(frozen=True)
class GwfMeshFlowDelta:
    """One mesh-vs-reference-mesh flow delta (brief Sec 1.1, exit criterion
    9) -- the quantified substance of this arm. Every delta is reported in
    BOTH physical units and as a relative fraction of the reference value
    (`None` only when the reference value is exactly zero; see
    `_rel_delta`)."""

    mesh_id: str
    reference_mesh_id: str
    d_q_source_darcy_m_d: float
    d_q_source_darcy_rel: Optional[float]
    d_q_receptor_darcy_m_d: float
    d_q_receptor_darcy_rel: Optional[float]
    d_head_diff_corridor_m: float
    d_head_diff_corridor_rel: Optional[float]
    d_extraction_throughflow_m3d: float
    d_extraction_throughflow_rel: Optional[float]


def _compute_delta(candidate: "MeshFlowDiagnostics",
                   reference: "MeshFlowDiagnostics") -> "GwfMeshFlowDelta":
    d_src = candidate.q_source_darcy_m_d - reference.q_source_darcy_m_d
    d_rcpt = candidate.q_receptor_darcy_m_d - reference.q_receptor_darcy_m_d
    d_head = candidate.head_diff_corridor_m - reference.head_diff_corridor_m
    d_ext = candidate.extraction_throughflow_m3d - reference.extraction_throughflow_m3d
    return GwfMeshFlowDelta(
        mesh_id=candidate.mesh_id, reference_mesh_id=reference.mesh_id,
        d_q_source_darcy_m_d=d_src,
        d_q_source_darcy_rel=_rel_delta(d_src, reference.q_source_darcy_m_d),
        d_q_receptor_darcy_m_d=d_rcpt,
        d_q_receptor_darcy_rel=_rel_delta(d_rcpt, reference.q_receptor_darcy_m_d),
        d_head_diff_corridor_m=d_head,
        d_head_diff_corridor_rel=_rel_delta(d_head, reference.head_diff_corridor_m),
        d_extraction_throughflow_m3d=d_ext,
        d_extraction_throughflow_rel=_rel_delta(
            d_ext, reference.extraction_throughflow_m3d),
    )


# ---------------------------------------------------------------------------
# the arm result -- role group reused, ceiling enforced structurally
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GwfGridSensitivityArmResult:
    """The T1 S10 arm's result: one reference mesh, one or more compared
    meshes, their flow deltas, any validated injected fingerprints, and the
    non-isolation statement + ceiling every reporting path below carries
    (exit criteria 1, 17).

    `run_role` / `grid_role` / `counterpart_run_id` reuse T0_2b Sec 5.1's
    frozen Role group (transcribed, not imported -- see the section-level
    comment above); `is_control` is always `False` and `analysis_kind` is a
    plain, non-control discoverability label (brief Sec 3: "No CONTROL
    label").
    """

    reference_mesh_id: str
    mesh_results: Tuple["MeshFlowDiagnostics", ...]
    deltas: Tuple["GwfMeshFlowDelta", ...]
    fingerprints: Mapping[str, "CaptureFingerprintRecord"]
    non_isolation_statement: str = NON_ISOLATION_STATEMENT
    claim_ceiling: str = CLAIM_CEILING
    run_role: str = _ARM_RUN_ROLE
    grid_role: Optional[str] = None
    counterpart_run_id: Optional[str] = None
    analysis_kind: str = _ANALYSIS_KIND
    is_control: bool = False

    def __post_init__(self) -> None:
        if self.non_isolation_statement != NON_ISOLATION_STATEMENT:
            raise ValueError(
                "GwfGridSensitivityArmResult.non_isolation_statement must be "
                "exactly the frozen NON_ISOLATION_STATEMENT -- this arm can "
                "never quietly read as isolating the flow field (brief "
                "exit criterion 1)")
        if self.claim_ceiling != CLAIM_CEILING:
            raise ValueError(
                f"GwfGridSensitivityArmResult.claim_ceiling must be "
                f"{CLAIM_CEILING!r} -- a grid comparison carrying this arm "
                "can never license 'cause' (brief Sec 1, T0_2b Sec 4.2)")
        if self.is_control is not False:
            raise ValueError(
                "GwfGridSensitivityArmResult.is_control must be False -- "
                "this arm is explicitly NOT a control (brief Sec 3)")
        if self.run_role not in _RUN_ROLES:
            raise ValueError(
                f"GwfGridSensitivityArmResult.run_role={self.run_role!r} is "
                f"not one of {_RUN_ROLES!r}")

    # -- reporting / export paths -- EVERY one carries the non-isolation
    # statement and the ceiling verbatim (exit criterion 17) --------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference_mesh_id": self.reference_mesh_id,
            "non_isolation_statement": self.non_isolation_statement,
            "claim_ceiling": self.claim_ceiling,
            "role": {
                "run_role": self.run_role,
                "grid_role": self.grid_role,
                "counterpart_run_id": self.counterpart_run_id,
            },
            "analysis_kind": self.analysis_kind,
            "is_control": self.is_control,
            "meshes": [dataclasses.asdict(d) for d in self.mesh_results],
            "deltas": [dataclasses.asdict(d) for d in self.deltas],
            "fingerprints": {mid: dataclasses.asdict(fp)
                             for mid, fp in sorted(self.fingerprints.items())},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=True)

    def summary_text(self) -> str:
        lines = [
            "GWF-grid sensitivity arm (T1 S10) -- flow solved and reported "
            "per mesh.",
            f"  claim ceiling: {self.claim_ceiling!r}",
            f"  reference mesh: {self.reference_mesh_id}",
            "",
            self.non_isolation_statement,
            "",
        ]
        for d in self.deltas:
            lines.append(
                f"  mesh {d.mesh_id} vs reference {d.reference_mesh_id}:")
            lines.append(
                f"    d(q_source)  = {d.d_q_source_darcy_m_d:+.4g} m/d "
                f"({_fmt_rel(d.d_q_source_darcy_rel)})")
            lines.append(
                f"    d(q_receptor)= {d.d_q_receptor_darcy_m_d:+.4g} m/d "
                f"({_fmt_rel(d.d_q_receptor_darcy_rel)})")
            lines.append(
                f"    d(head diff) = {d.d_head_diff_corridor_m:+.4g} m "
                f"({_fmt_rel(d.d_head_diff_corridor_rel)})")
            lines.append(
                f"    d(Q_ext)     = {d.d_extraction_throughflow_m3d:+.4g} "
                f"m3/d ({_fmt_rel(d.d_extraction_throughflow_rel)})")
        return "\n".join(lines)

    def deltas_table(self) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        for d in self.deltas:
            for metric, abs_val, rel_val, units in (
                ("q_source_darcy", d.d_q_source_darcy_m_d,
                 d.d_q_source_darcy_rel, "m/d"),
                ("q_receptor_darcy", d.d_q_receptor_darcy_m_d,
                 d.d_q_receptor_darcy_rel, "m/d"),
                ("head_diff_corridor", d.d_head_diff_corridor_m,
                 d.d_head_diff_corridor_rel, "m"),
                ("extraction_throughflow", d.d_extraction_throughflow_m3d,
                 d.d_extraction_throughflow_rel, "m3/d"),
            ):
                rows.append({
                    "mesh_id": d.mesh_id,
                    "reference_mesh_id": d.reference_mesh_id,
                    "metric": metric,
                    "absolute_delta": abs_val,
                    "relative_delta": rel_val,
                    "units": units,
                })
        return {
            "non_isolation_statement": self.non_isolation_statement,
            "claim_ceiling": self.claim_ceiling,
            "rows": rows,
        }


def assemble_gwf_grid_sensitivity_arm(
        mesh_diagnostics: Sequence["MeshFlowDiagnostics"], *,
        reference_mesh_id: str,
        fingerprints: Optional[Mapping[str, "CaptureFingerprintRecord"]] = None,
) -> "GwfGridSensitivityArmResult":
    """Validate + assemble one `GwfGridSensitivityArmResult` from already
    -solved per-mesh diagnostics (brief Sec 5, the exit-criteria table):

      * duplicate mesh ids raise (`DuplicateMeshIdError`, exit criterion 13);
      * `mesh_diagnostics` order IS the result's order -- deterministic by
        construction (a Python sequence's order is never silently reshuffled
        here), and any fingerprint naming a `mesh_id` outside this set, or
        `reference_mesh_id` itself not among the supplied meshes, raises
        (misalignment, exit criterion 13);
      * ANY unsolved mesh refuses the WHOLE arm (`MeshSolveFailedError`,
        never a partially-successful result -- exit criterion 15);
      * every supplied fingerprint is validated against ITS OWN mesh's
        identity (`_validate_capture_fingerprint`) before being attached.
    """
    mesh_list = list(mesh_diagnostics)
    if not mesh_list:
        raise ValueError("assemble_gwf_grid_sensitivity_arm: mesh_diagnostics is empty")

    ids = [d.mesh_id for d in mesh_list]
    dupes = sorted({m for m in ids if ids.count(m) > 1})
    if dupes:
        raise DuplicateMeshIdError(f"duplicate mesh id(s) in this arm: {dupes!r}")

    if reference_mesh_id not in ids:
        raise ValueError(
            f"reference_mesh_id={reference_mesh_id!r} is not among the "
            f"supplied mesh ids {ids!r}")

    failed = [d for d in mesh_list if not d.solved]
    if failed:
        raise MeshSolveFailedError(
            "refusing to record a GWF-grid-sensitivity arm: mesh(es) "
            f"{[d.mesh_id for d in failed]!r} did not solve successfully "
            f"(solver_status={[d.solver_status for d in failed]!r}) -- a "
            "failed or partial solve is never recorded as a successful arm "
            "(brief exit criterion 15)")

    fingerprints = dict(fingerprints or {})
    unknown = sorted(set(fingerprints) - set(ids))
    if unknown:
        raise ValueError(
            f"fingerprint(s) supplied for mesh id(s) {unknown!r}, which are "
            "not among this arm's meshes -- misalignment")

    by_id = {d.mesh_id: d for d in mesh_list}
    validated: Dict[str, CaptureFingerprintRecord] = {}
    for mesh_id, fp in fingerprints.items():
        diag = by_id[mesh_id]
        _validate_capture_fingerprint(fp, mesh_id=mesh_id, flow_identity=diag.flow_identity)
        validated[mesh_id] = fp

    reference = by_id[reference_mesh_id]
    deltas = tuple(_compute_delta(d, reference) for d in mesh_list
                   if d.mesh_id != reference_mesh_id)

    return GwfGridSensitivityArmResult(
        reference_mesh_id=reference_mesh_id,
        mesh_results=tuple(mesh_list),
        deltas=deltas,
        fingerprints=validated,
        counterpart_run_id=reference.mesh_id,
    )


# ---------------------------------------------------------------------------
# the REAL per-mesh GWF solve (brief Sec 1: "flow solved and reported per
# mesh"). Expensive -- a full corridor refinement + MF6 GWF solve (T2's own
# timing note: ~316 s for a fine mesh on a fast Mac; Hub speed unmeasured) --
# so this is NOT exercised by the fast unit tests in
# test_t1_gwf_grid_sensitivity.py, which test the composition/validation
# logic above against synthetic `MeshFlowDiagnostics` built from the exact
# same fields this function returns. Never wired into any default call path.
# ---------------------------------------------------------------------------
def _mesh_flow_diagnostics_from_solved_gwf(gwf, grid: Dict[str, Any],
                                           platform_tag: str) -> "MeshFlowDiagnostics":
    spd = gwf.output.budget().get_data(text="DATA-SPDIS")[0]
    heads = gwf.output.head().get_data().flatten()
    src_cell = int(grid["src_cells"][0])
    ext_cell = int(grid["ext_cell"])
    q_src = float(np.hypot(spd["qx"][src_cell], spd["qy"][src_cell]))
    q_ext = float(np.hypot(spd["qx"][ext_cell], spd["qy"][ext_cell]))
    head_diff = float(heads[src_cell] - heads[ext_cell])
    realized = _realized_extraction_flows(gwf, "absw")
    extraction_throughflow = float(sum(abs(v) for v in realized.values()))
    flow_id = flow_identity_string(grid["mesh_hash"], tuple(realized.keys()))
    return MeshFlowDiagnostics(
        mesh_id=grid["mesh_hash"], mesh_spec_hash=grid["mesh_spec_hash"],
        q_source_darcy_m_d=q_src, q_receptor_darcy_m_d=q_ext,
        head_diff_corridor_m=head_diff,
        extraction_throughflow_m3d=extraction_throughflow,
        flow_identity=flow_id, platform=platform_tag, solved=True,
        solver_status="converged")


def solve_mesh_flow(mesh_spec: "MeshSpec", *, sink_support_m: float = 0.0,
                    case_ws: Optional[Union[str, Path]] = None) -> "MeshFlowDiagnostics":
    """Build + solve MODFLOW 6 GWF for ONE mesh and return its flow
    diagnostics. A mesh-BUILD failure (corridor refinement exhausting its
    retry ladder) raises `MeshSolveFailedError`; a mesh that BUILDS but
    whose MF6 solve does not converge returns `solved=False` with
    `solver_status` naming the failure (brief exit criterion 15: handled
    explicitly, never silently recorded as success) -- callers pass such a
    record straight to `assemble_gwf_grid_sensitivity_arm`, which refuses to
    build a result from it.
    """
    cgwf, boundary, rivers, exe = _load_calibrated_flow()
    root = Path(case_ws) if case_ws is not None else _default_case_ws() / "gwf_grid_sensitivity"
    try:
        grid = refine_corridor(cgwf, boundary, rivers, mesh_spec=mesh_spec, case_ws=root)
    except Exception as exc:
        raise MeshSolveFailedError(
            f"mesh build (corridor refinement) failed for mesh_spec="
            f"{mesh_spec!r}: {exc!r}") from exc

    platform_tag = current_platform_tag()
    mesh_ws = root / f"mesh_{grid['mesh_hash']}"
    sim = new_sim(mesh_ws, pulse_days=1.0, total_days=1.0, nstp_per_period=1, exe=exe)
    gwf = add_flow_model(sim, grid, sink_support_m=sink_support_m)
    sim.write_simulation(silent=True)
    ok, buf = sim.run_simulation(silent=True)
    if not ok:
        return MeshFlowDiagnostics(
            mesh_id=grid["mesh_hash"], mesh_spec_hash=grid["mesh_spec_hash"],
            q_source_darcy_m_d=float("nan"), q_receptor_darcy_m_d=float("nan"),
            head_diff_corridor_m=float("nan"),
            extraction_throughflow_m3d=float("nan"), flow_identity="",
            platform=platform_tag, solved=False,
            solver_status=_run_failure_tail(mesh_ws / "sim", buf))
    return _mesh_flow_diagnostics_from_solved_gwf(gwf, grid, platform_tag)


def run_gwf_grid_sensitivity_arm(
        mesh_specs: Sequence["MeshSpec"], *, reference_index: int = 0,
        sink_support_m: float = 0.0,
        fingerprints: Optional[Mapping[str, "CaptureFingerprintRecord"]] = None,
        case_ws: Optional[Union[str, Path]] = None) -> "GwfGridSensitivityArmResult":
    """Convenience wrapper: `solve_mesh_flow` for every mesh in
    `mesh_specs` (⚠️ each mesh carrying its OWN GWF solve is inherent to the
    design, brief Sec 1 -- not a defect to "optimise" away by sharing one
    flow field), then `assemble_gwf_grid_sensitivity_arm`. Never wired into
    any default call path.
    """
    diagnostics = [solve_mesh_flow(spec, sink_support_m=sink_support_m, case_ws=case_ws)
                  for spec in mesh_specs]
    reference_mesh_id = diagnostics[reference_index].mesh_id
    return assemble_gwf_grid_sensitivity_arm(
        diagnostics, reference_mesh_id=reference_mesh_id, fingerprints=fingerprints)


# ---------------------------------------------------------------------------
# demo / smoke anchor
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    t0 = time.time()
    r = build_srcpulse_demo(mass_g=3.0e5, pulse_days=30.0, total_days=120.0,
                            solubility_mgL=1000.0, force=("--force" in sys.argv))
    dt = time.time() - t0
    print("SRC FINITE-PULSE SPILL -> CAPTURE DEMO")
    print(f"  released mass M      = {r.mass_g:.4g} g  over T = {r.pulse_days:.0f} d "
          f"(total {r.total_days:.0f} d)")
    print(f"  per-cell SRC loading = {r.smassrate_gpd:.4g} g/d  ({r.meta['n_src']} src cell)")
    print(f"  spill_xy             = ({r.spill_xy[0]:.1f}, {r.spill_xy[1]:.1f})  "
          f"[{SPILL_UPGRADIENT_M:.0f} m upgradient of ABS]")
    print(f"  peak breakthrough    = {r.peak_mgL:.4g} mg/L  at day {r.arrival_day:.1f}")
    print(f"  emergent source C    = {r.emergent_C_mgL:.4g} mg/L  "
          f"(solubility {r.solubility_mgL:.0f} mg/L; margin x{r.solubility_margin:.1f}) -> "
          f"{'PASS' if r.solubility_ok else 'FAIL'}")
    mb = r.mass_balance
    print("  mass balance [g]:")
    print(f"    SRC in       = {mb.get('src_in_g', float('nan')):.4g}")
    print(f"    well out     = {mb.get('well_out_g', float('nan')):.4g}")
    print(f"    boundary out = {mb.get('boundary_out_g', float('nan')):.4g}")
    print(f"    storage      = {mb.get('storage_g', float('nan')):.4g}")
    print(f"    % imbalance  = {mb.get('pct_imbalance', float('nan')):.3f}")
    print(f"  Pe_L corridor = {r.PeL_min:.2f}..{r.PeL_max:.2f}   "
          f"Pe_T = {r.PeT_min:.2f}..{r.PeT_max:.2f}")
    print(f"  Cr peak = {r.meta['Cr']:.2f}  nstp={r.meta['nstp']}  "
          f"refine_radius={r.meta['refine_radius_used']:.0f} m")
    print(f"  wall-clock = {dt:.0f}s")
    ok = (r.solubility_ok and r.peak_mgL > 0
          and abs(mb.get("pct_imbalance", 99)) < 5.0 and r.PeL_max <= 2.0)
    print("  SMOKE:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
