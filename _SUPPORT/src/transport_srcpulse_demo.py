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
import shutil
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

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
_GWF_IMS = dict(complexity="COMPLEX", outer_maximum=200, inner_maximum=100,
                outer_dvclose=1e-4, inner_dvclose=1e-5, linear_acceleration="BICGSTAB")
_GWT_IMS = dict(complexity="MODERATE", linear_acceleration="BICGSTAB",
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
# `profile` admits ONLY the two legacy IDs in S4. `exp_v1` -- the corrected
# policy: floor keyed off the finest *intended* cell size, source/wells
# included, global max Courant reported -- does not exist yet; that is S8,
# gated on the T1 JAG. This function never warns and never reports a cap
# flag: both stay caller-owned exactly as today (`build_doublet_base` has no
# cap flag; `build_spill_scenario` sets `cr_capped` from `Cr > 1.001` without
# warning; this module's own wrapper sets `cr_capped = nstp >= nstp_cap` and
# warns -- all unchanged, at the call sites, not here).
# ---------------------------------------------------------------------------
_COURANT_LEGACY_PROFILES = ("legacy_base", "legacy_srcpulse")


def _courant_nstp_canonical(v_cells: np.ndarray, size_cells: np.ndarray, mask: np.ndarray,
                            total_time: float, *, exclusions: Sequence[int] = (),
                            cr_target: float = 0.9, nstp_cap: int,
                            sliver_floor_frac: float = 0.4, refined_cell_size: float,
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
    """
    if profile not in _COURANT_LEGACY_PROFILES:
        raise ValueError(
            f"unknown courant_nstp profile {profile!r}; expected one of "
            f"{_COURANT_LEGACY_PROFILES}")

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


def refine_corridor(cgwf, boundary, rivers, spill_xy=None, *,
                    refine_radii: Any = _UNSET,
                    mesh_spec: Optional["MeshSpec"] = None,
                    case_ws: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Refine the spill->extraction corridor and return a **GridBundle** dict.

    Computes the local regional-flow direction at the extraction well (to place
    the spill ``SPILL_UPGRADIENT_M`` upgradient, unless ``spill_xy`` is given),
    then corridor-refines the DISV grid via ``_refine_with_retry`` (the macOS
    arm64 SIGILL / Triangle-precision radius-walk stays INSIDE this call).

    ``refine_radii=`` (legacy) and ``mesh_spec=`` (T1 S3a) are resolved by
    ``_resolve_mesh_spec`` -- supplying both is a ``ValueError``. A
    ``mesh_spec`` with more than one ``MeshLevel`` raises ``NotImplementedError``
    (S3b, not built here).

    The returned dict carries everything the sim builders need -- modelgrid,
    gridprops, cell arrays, boundary stress data, and the injection / extraction /
    source cell indices -- so nothing downstream reaches back into the coarse or
    refined GWF objects. It also carries the two T1 S3a mesh identities:
    ``mesh_spec_hash`` (declared) and ``mesh_hash`` (effective -- the winning
    retry radius and the GIS content hashes folded in).
    """
    spec = _resolve_mesh_spec(refine_radii=refine_radii, mesh_spec=mesh_spec)
    _require_single_level(spec)   # NotImplementedError for >1 level, before any I/O

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
    src_cells = [int(np.argmin((xc - spill_xy[0]) ** 2 + (yc - spill_xy[1]) ** 2))]

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
        boundary_path=boundary_path, rivers_path=rivers_path)


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


def add_flow_model(sim, grid: Dict[str, Any]):
    """Add the GWF flow model (DISV, NPF, IC, STO, RCHA, CHD, RIV, WEL x2 doublet,
    OC) to ``sim`` and return it.  The doublet wells are FLOW ONLY (no solute)."""
    ncpl = grid["ncpl"]; gp = grid["gridprops"]
    top_ref = grid["top"]; botm_ref = grid["botm"]; k_ref = grid["k"]
    heads_ref = grid["heads"]; rch = grid["rch"]; chd = grid["chd"]; riv = grid["riv"]
    injc = grid["inj_cell"]; extc = grid["ext_cell"]
    nper = int(sim.tdis.nper.get_data())

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
    flopy.mf6.ModflowGwfwel(gwf, pname="absw",
                            stress_period_data={0: [[(0, extc), -abs(DOUBLET_Q)]]})
    flopy.mf6.ModflowGwfoc(gwf, head_filerecord="gwf.hds", budget_filerecord="gwf.cbc",
                           saverecord=[("HEAD", "LAST"), ("BUDGET", "LAST")])
    return gwf


def add_transport_model(sim, gwf, grid: Dict[str, Any], *, mass_g: float,
                        pulse_days: float, R: float = 1.0, rho_b: float = 1800.0,
                        lam: float = 0.0, alpha_L: Optional[float] = None):
    """Add the GWT solute-transport model (DISV, IC, MST, ADV/TVD, DSP, SSM, SRC,
    OC) + the GWT IMS solver to ``sim`` and return it.

    The spill enters via the SRC package as a per-cell mass loading
    ``smassrate = mass_g / (n_src_cells * pulse_days)`` [g/d], ON in period 0 and
    OFF in period 1.  ``alpha_L`` defaults to the LOCKED longitudinal dispersivity;
    ``alpha_T`` is derived from the LOCKED 10:1 ratio.  MST sorption is gated on
    ``R > 1`` (``Kd = (R-1)*porosity/rho_b``) and first-order decay on ``lam > 0``.
    """
    ncpl = grid["ncpl"]; gp = grid["gridprops"]
    top_ref = grid["top"]; botm_ref = grid["botm"]
    src_cells = grid["src_cells"]

    alpha_L_eff = float(LOCKED_PARAMS["alh"]) if alpha_L is None else float(alpha_L)
    alpha_T_eff = alpha_L_eff * (float(LOCKED_PARAMS["ath1"]) / float(LOCKED_PARAMS["alh"]))
    porosity = float(LOCKED_PARAMS["porosity"])
    Kd = (float(R) - 1.0) * porosity / float(rho_b) if R > 1.0 else 0.0
    n_src = len(src_cells)
    smassrate = float(mass_g) / (n_src * float(pulse_days))   # per-cell SRC loading [g/d]

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
    # SRC finite pulse: mass loading [g/d] in period 0, OFF in period 1
    src_spd = {0: [[(0, c), smassrate] for c in src_cells], 1: []}
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
                         ("cr_target", cr_target)):
        if not math.isfinite(_val):
            raise ValueError(f"{_name} must be finite (got {_val!r})")
    if alpha_L is not None and not math.isfinite(alpha_L):
        raise ValueError(f"alpha_L must be finite (got {alpha_L!r})")

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
                  cr_target=float(cr_target), nstp_cap=int(nstp_cap),
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
    grid = refine_corridor(cgwf, boundary, rivers, mesh_spec=spec, case_ws=case_ws)
    ncpl = grid["ncpl"]
    csz = grid["cellsize"]
    heads_ref = grid["heads"]; botm_ref = grid["botm"]
    injc = grid["inj_cell"]; extc = grid["ext_cell"]; src_cells = grid["src_cells"]
    corridor_mask = grid["corridor_mask"]
    refine_radius_used = grid["refine_radius_used"]
    u_reg = np.array(grid["u_reg"], float)
    spill_xy = grid["spill_xy"]
    n_src = len(src_cells)
    smassrate = float(mass_g) / (n_src * float(pulse_days))   # per-cell SRC loading [g/d]

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
        gwf = add_flow_model(sim, grid)
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
    # `_courant_nstp_canonical`.
    nstp, dt, cr_act, cdiag = _courant_nstp(vmag, csz, corridor_mask, float(total_days),
                                            cr_target, nstp_cap,
                                            exclusions=src_cells + [injc, extc])

    sim, gwf, gwt, ok, buf = _make_sim(nstp)
    if not ok:
        raise RuntimeError("production run failed; listing tail:\n"
                           + _run_failure_tail(run_ws / "sim", buf))

    # ---- breakthrough at the extraction well ----
    cobj = gwt.output.concentration(); times = np.array(cobj.get_times())
    bt = np.maximum(np.array([cobj.get_data(totim=t)[0, 0, extc] for t in times]), 0.0)
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
    q_src = float(np.hypot(spd["qx"][src_cells[0]], spd["qy"][src_cells[0]]))  # Darcy [m/d]
    b_src = float(max(heads_ref[src_cells[0]] - botm_ref[0][src_cells[0]], 0.1))
    ds_src = float(csz[src_cells[0]])
    q_cell = max(q_src * ds_src * b_src, 1e-6)                # advective throughflow [m^3/d]
    emergent_C = smassrate / q_cell                          # [g/m^3] == [mg/L]
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

    # T1 S2 (brief Section 3.3): the apportionment ACTUALLY applied by the WEL
    # construction in `add_flow_model` -- the whole doublet rate on the single
    # nearest-centroid extraction cell. `extc`/`DOUBLET_Q` are read off THIS
    # run, never hardcoded a second time. Sorted by cell index (trivial with
    # one entry, but written now so a future multi-cell apportionment -- S9c --
    # inherits an already-sorted invariant).
    sink_support_cells = sorted(
        [(int(extc), -abs(float(DOUBLET_Q)))], key=lambda pair: pair[0])

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
        # T1 S2: identity default (brief Section 3.2). No builder parameter in
        # S2 -- constant until S9b makes it real. `t_peak` is NOT passed here
        # (init=False; derived in __post_init__ from arrival_day above).
        sink_support_m=0.0, meta=meta)

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
