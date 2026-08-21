"""
transport_operator_a -- T1 S6: operator A, the fixed-support disc diagnostic.

Scope (``DESIGN_DOCS/T1_S6_brief.md`` v2, codex-reviewed; authorised by
``DOCUMENTATION/contracts/T0_1_C1_v2.md`` entry **A12**: "``transport_srcpulse_demo.py``
+ new"): operator A is a **fixed-support post-processing average**,

    C_A(t) = sum_i( C_i(t) * n_i * b_sat_i(t) * |P_i intersect D_25| )
             / sum_i( n_i * b_sat_i(t) * |P_i intersect D_25| )

over a 25.0 m disc ``D_25`` centred on the extraction well (``ABS_XY``,
``transport_srcpulse_demo.py:291``), integrated against the EXACT cell-polygon
intersection area for every cell that touches the disc.  It is DIAGNOSTIC ONLY
(``T0_2b_metrics_and_causal_rule.md`` Sec 4.2, item 1): a null result under A is
AMBIGUOUS, because A changes the estimand (a spatial average, not a point
sample) and spatially smooths the plume.  It does not change the taught
metric -- students keep reading the single-cell well concentration -- and its
result is barred from ever counting as causal support.  The artifact label,
frozen by ``T0_1_C1_v2.md``/``T1_open_definitions.md`` Sec 2, is
``observation_support_robustness``; ``t1_evidence_artifact.DiagnosticRecord``
carries ``causal_support_eligible=False`` for that label unconditionally.

================================================================================
WHY THIS IS A SEPARATE MODULE, AND WHY ``transport_srcpulse_demo.py`` DOES NOT
IMPORT IT (flagged explicitly, per the project's practice of surfacing
interpretive choices rather than making them silently)
================================================================================

``T0_1_C1_v2.md`` Sec 0.1 / entry A8 froze ``transport_srcpulse_demo._src_sha()``
as the sha256 of the TRANSITIVE ``_SUPPORT/src`` import closure reachable from
``transport_srcpulse_demo.py`` -- including deferred, function-body imports, not
just module-level ones (``test_t1_src_closure.py::
test_closure_includes_deferred_function_level_imports``).  That closure is
PINNED EXACTLY (``test_t1_src_closure.py::DEMO_EXPECTED``, 7 members) and is one
of the test suites this step's own brief requires to stay green.  Adding ANY
import of this module -- top-level or inside a function body -- to
``transport_srcpulse_demo.py`` would grow that pinned set and break the pin.

So this module imports ``t1_evidence_artifact`` (an ``artifact``-side module;
per that module's own docstring, imports are one-way ``artifact -> model``,
NEVER ``model -> artifact`` -- this module sits on the ``model`` side of that
boundary, consuming the artifact schema, which is the direction the boundary
allows) and pure third-party geometry (``numpy``, ``shapely``).  It does NOT
import ``transport_srcpulse_demo`` at all -- every quantity it needs
(``ABS_XY``, a cell size, a ``MeshSpec``-shaped object) is passed in by the
caller as a plain value, so the coupling is by DUCK TYPING
(``cell_size_from_mesh_spec`` reads ``mesh_spec.levels[0].cell_size``
structurally) rather than by import.  A future integration point (S14, the
artifact producer -- not built by this step; see
``t1_evidence_artifact.py``'s own docstring, "S1-S11 land the capabilities
... this schema's fields describe") is expected to import BOTH modules and
wire them together; that integration is exactly the ``model -> artifact``
direction the one-way rule was written for, and belongs to the module that
already legitimately imports ``transport_srcpulse_demo`` (an evidence
producer), not to this one.

================================================================================
THE WARM-CACHE PATH (brief Sec 3.1) -- what this module can and cannot do
================================================================================

``build_srcpulse_demo`` returns from its ``.npz`` cache BEFORE any grid or
concentration field exists (``transport_srcpulse_demo.py:1198-1201``), so
operator A cannot be recomputed on that path -- there is no mesh, no head
field, and no concentration file to read.  This module cannot "reach into"
``build_srcpulse_demo`` to detect that condition itself (doing so would
require the very import this docstring's previous section explains is
forbidden).  What it provides instead is the PRIMITIVE a future caller needs:
``status_for_missing_run_materials`` builds a well-formed, non-crashing
``not_applicable`` ``DiagnosticRecord`` carrying a reason that names the cache
hit explicitly -- distinct from the reason a genuinely coarse mesh gets from
``compute_operator_a`` itself (see ``NOT_APPLICABLE_REASON_CACHE_HIT`` below).
A caller that hits the warm-cache branch is expected to call this function
rather than omit the diagnostic silently or crash; ``test_t1_operator_a.py``
tests exactly that contract.

================================================================================
FROZEN PARAMETERS AND POLICIES (brief Sec 2, Sec 3.2 -- restated, not reinvented)
================================================================================

* Radius: 25.0 m (``RADIUS_M``).  Centre: the caller's ``center_xy`` (the
  extraction well, ``ABS_XY``, in the caller's coordinates -- this module does
  not hard-code it, since hard-coding a model constant into a module that
  deliberately does not import the model would itself be a silent coupling).
* Intersection: EXACT cell-polygon-vs-disc area, via
  ``Point(center).buffer(radius_m, quad_segs=64)``.  quad_segs=64 gives a
  256-sided polygon; measured against the closed-form circle area at r=25 m,
  the polygonal disc's own area is 1963.298 m^2 against the true pi*r^2 =
  1963.495 m^2 -- a RELATIVE AREA ERROR of 1.0e-4 (0.01%), two orders of
  magnitude under ``TOL_CONC_REL`` (2%, ``T0_2b...`` Sec 2.7).  A
  centroid-in-disc approximation is explicitly NOT this module's algorithm
  (``test_centroid_in_disc_implementation_fails``).
* Weight: ``n_i * b_sat_i * |P_i intersect D|`` -- porosity (scalar or
  per-cell array; kept in the formula even though it is uniform today, per
  the brief) times SATURATED thickness (not ``top - botm``: the layer is
  ``icelltype=1``, convertible/unconfined, so a cell whose water table sits
  below its top would otherwise be over-weighted) times the intersection
  area.  ``saturated_thickness`` computes
  ``max(min(head, top) - botm, 0)`` from the PRODUCTION head -- the head
  field of the actual coupled-run GWF, not the pre-solve refined-grid head
  used only as an initial condition.
* Dry / inactive cells: zero weight (``saturated_thickness`` clips to 0 for a
  dry cell; an optional ``active`` mask multiplies inactive cells to 0 too).
* Negative numerical concentrations: clipped at zero before averaging, matching
  today's breakthrough clip (``transport_srcpulse_demo.py:1265``,
  ``np.maximum(..., 0.0)``) -- so operator A and the taught single-cell metric
  treat a negative numerical artifact the same way.
* Zero total weight in the disc: raises ``ValueError``, never returns NaN.
* Applicability: ``cell_size_m <= radius_m`` (the disc diameter spans at least
  two nominal cells).  ``cell_size_from_mesh_spec`` reads exactly
  ``mesh_spec.levels[0].cell_size`` -- never ``LOCKED_PARAMS`` and never a
  measured ``min(cellsize)`` (the realised sliver minimum, not the intended
  resolution) -- and raises ``NotImplementedError`` for more than one level
  (S3a admits exactly one; a graded mesh needs the predicate restated,
  ``T1_open_definitions.md`` Sec 2.1).
* Not applicable: a structured status (``DiagnosticRecord(status="not_applicable")``
  with a non-empty ``reason`` and empty ``times``/``values``), never ``None``
  and never a sentinel number.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Sequence, Tuple, Union

import numpy as np
from shapely.geometry import Point, Polygon

from t1_evidence_artifact import DIAGNOSTIC_LABELS, DiagnosticRecord

# ---------------------------------------------------------------------------
# Frozen constants (T1_open_definitions.md Sec 2 / T0_1_C1_v2.md entry A12)
# ---------------------------------------------------------------------------

#: The one closed-vocabulary label this diagnostic is ever filed under
#: (t1_evidence_artifact.DIAGNOSTIC_LABELS). Asserted against that module's
#: own closed enum at import time so the two modules cannot silently drift.
LABEL: str = "observation_support_robustness"
assert LABEL in DIAGNOSTIC_LABELS, (
    f"transport_operator_a.LABEL {LABEL!r} is not in "
    f"t1_evidence_artifact.DIAGNOSTIC_LABELS {DIAGNOSTIC_LABELS!r}")

#: T1_open_definitions.md Sec 2 -- the frozen disc radius.
RADIUS_M: float = 25.0

#: T1_S6_brief.md Sec 3.2 -- the declared, non-default polygonal resolution.
#: 64 quad segments -> a 256-sided polygon; see the module docstring for the
#: measured area error at RADIUS_M.
QUAD_SEGS: int = 64

#: T1_S6_brief.md Sec 2 -- the algorithm identity recorded on every record.
ALGORITHM_ID: str = "operator_a_disc_v1"

#: The reason text used specifically for the warm-cache path (brief Sec 3.1),
#: kept distinct from the cell-size not_applicable reason `compute_operator_a`
#: builds itself -- a reader must be able to tell "this mesh is too coarse for
#: A" apart from "A was never attempted because no grid/concentration field
#: existed on this call".
NOT_APPLICABLE_REASON_CACHE_HIT: str = (
    "build_srcpulse_demo returned from its warm .npz cache before any grid or "
    "concentration field existed (transport_srcpulse_demo.py ~:1198-1201); "
    "operator A requires the production mesh, head field and concentration "
    "series and cannot be recomputed from a cached SrcPulseDemo result alone "
    "(T1_S6_brief.md Sec 3.1)."
)


# ---------------------------------------------------------------------------
# Disc geometry
# ---------------------------------------------------------------------------
def disc_polygon(center_xy: Tuple[float, float], radius_m: float = RADIUS_M,
                  quad_segs: int = QUAD_SEGS) -> Polygon:
    """The fixed-support disc D, as a declared polygonal approximation of a
    circle of radius ``radius_m`` centred on ``center_xy`` -- see the module
    docstring for the measured area error at the frozen ``RADIUS_M``/``QUAD_SEGS``."""
    if not (radius_m > 0.0):
        raise ValueError(f"radius_m must be > 0 (got {radius_m!r})")
    if quad_segs < 1:
        raise ValueError(f"quad_segs must be >= 1 (got {quad_segs!r})")
    return Point(float(center_xy[0]), float(center_xy[1])).buffer(
        float(radius_m), quad_segs=int(quad_segs))


def cell_intersection_areas(cell_polygons: Sequence[Optional[Polygon]],
                             disc: Polygon) -> np.ndarray:
    """Exact ``|P_i intersect D|`` for every cell polygon in ``cell_polygons``.

    A cell whose polygon is ``None``/empty, or whose bounding box does not
    touch the disc's bounding box, contributes exactly 0.0 -- never
    approximated by a centroid-in-disc test
    (``test_centroid_in_disc_implementation_fails``).
    """
    bx0, by0, bx1, by1 = disc.bounds
    areas = np.zeros(len(cell_polygons), dtype=float)
    for i, poly in enumerate(cell_polygons):
        if poly is None or poly.is_empty:
            continue
        px0, py0, px1, py1 = poly.bounds
        if px1 < bx0 or px0 > bx1 or py1 < by0 or py0 > by1:
            continue  # bounding boxes disjoint -> polygons cannot overlap
        areas[i] = poly.intersection(disc).area
    return areas


def cell_polygons_from_modelgrid(mg: Any, ncpl: int) -> list:
    """Cell polygons for a flopy DISV ``modelgrid``, matching the convention
    ``transport_srcpulse_demo._cellsize`` already uses
    (``Polygon(mg.get_cell_vertices(i))``, ``transport_srcpulse_demo.py:363``).
    Duck-typed against ``mg.get_cell_vertices`` -- does not import flopy types."""
    return [Polygon(mg.get_cell_vertices(i)) for i in range(int(ncpl))]


# ---------------------------------------------------------------------------
# Saturated-thickness weighting (brief Sec 2 red flag: NOT top - botm)
# ---------------------------------------------------------------------------
def saturated_thickness(heads: Any, top: Any, botm: Any) -> np.ndarray:
    """``b_sat = max(min(head, top) - botm, 0)`` -- the layer is
    ``icelltype=1`` (convertible/unconfined,
    ``transport_srcpulse_demo.py:936``), so a cell whose water table sits
    below its top must not be weighted by the full ``top - botm`` layer
    thickness.  A dry cell (``head <= botm``) gets exactly 0.0, never a
    negative thickness."""
    heads = np.asarray(heads, dtype=float)
    top = np.asarray(top, dtype=float)
    botm = np.asarray(botm, dtype=float)
    return np.maximum(np.minimum(heads, top) - botm, 0.0)


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------
def cell_weights(areas: Any, b_sat: Any, porosity: Union[float, Any], *,
                  active: Optional[Any] = None) -> np.ndarray:
    """``n_i * b_sat_i * |P_i intersect D|`` per cell.

    ``porosity`` may be a scalar (today's uniform ``LOCKED_PARAMS["porosity"]``,
    which cancels algebraically but is kept in the formula per the brief) or a
    per-cell array (a spatially variable porosity would change the answer).
    Non-finite ``b_sat``/weight entries and any cell an optional ``active``
    mask marks inactive are forced to exactly 0.0 -- never propagated as NaN.
    """
    areas = np.asarray(areas, dtype=float)
    b_sat = np.asarray(b_sat, dtype=float)
    n = np.broadcast_to(np.asarray(porosity, dtype=float), areas.shape)
    b_sat = np.where(np.isfinite(b_sat), b_sat, 0.0)
    b_sat = np.maximum(b_sat, 0.0)
    w = n * b_sat * areas
    w = np.where(np.isfinite(w), w, 0.0)
    if active is not None:
        w = np.where(np.asarray(active, dtype=bool), w, 0.0)
    return np.maximum(w, 0.0)


# ---------------------------------------------------------------------------
# Applicability (T1_open_definitions.md Sec 2.1)
# ---------------------------------------------------------------------------
def is_applicable(cell_size_m: float, radius_m: float = RADIUS_M) -> bool:
    """Operator A is applicable iff the intended cell size spans at least two
    nominal cells across the disc diameter: ``cell_size_m <= radius_m``."""
    return float(cell_size_m) <= float(radius_m)


def cell_size_from_mesh_spec(mesh_spec: Any) -> float:
    """Read the intended cell size EXACTLY per the brief: ``mesh_spec.levels[0]
    .cell_size`` -- never ``LOCKED_PARAMS``, never a measured ``min(cellsize)``.

    Duck-typed on ``mesh_spec.levels`` (a sequence of objects with a
    ``.cell_size`` attribute) so this module never has to import
    ``transport_srcpulse_demo.MeshSpec`` -- any object with that shape works,
    including the real ``MeshSpec``.

    Raises ``NotImplementedError`` for more than one level: S3a builds a
    single-level mesh only, and a graded (multi-level) mesh needs this
    predicate restated as "the coarsest intended size intersecting the disc"
    before it can be evaluated (``T1_open_definitions.md`` Sec 2.1) -- a
    silent "first level" read would pass a graded mesh on its fine level
    alone.
    """
    levels = mesh_spec.levels
    if len(levels) != 1:
        raise NotImplementedError(
            "operator A's applicability rule (T1_open_definitions.md Sec 2.1) is "
            f"defined for a single-level MeshSpec only; got {len(levels)} levels. "
            "Multi-level evaluation needs the predicate restated as 'the coarsest "
            "intended size intersecting the disc' before it can be answered.")
    return float(levels[0].cell_size)


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------
def not_applicable_record(reason: str, *, center_xy: Tuple[float, float],
                           radius_m: float = RADIUS_M,
                           algorithm_id: str = ALGORITHM_ID) -> DiagnosticRecord:
    """A structured ``not_applicable`` ``DiagnosticRecord`` -- never ``None``,
    never a sentinel number.  ``reason`` must be non-empty
    (``t1_evidence_artifact`` itself enforces this on load; enforced again
    here so a caller gets the error at construction, not at the artifact
    write/read boundary)."""
    if not reason:
        raise ValueError("not_applicable_record requires a non-empty reason")
    return DiagnosticRecord(
        label=LABEL, status="not_applicable", algorithm_id=str(algorithm_id),
        radius_m=float(radius_m),
        centre_xy_m=(float(center_xy[0]), float(center_xy[1])),
        times=(), values=(), reason=str(reason))


def status_for_missing_run_materials(
        reason: str = NOT_APPLICABLE_REASON_CACHE_HIT, *,
        center_xy: Tuple[float, float], radius_m: float = RADIUS_M,
        algorithm_id: str = ALGORITHM_ID) -> DiagnosticRecord:
    """The warm-cache-path primitive (module docstring, "THE WARM-CACHE PATH"):
    a well-formed, non-crashing ``not_applicable`` record for a caller that has
    no grid/concentration field to recompute operator A from -- e.g. because
    ``build_srcpulse_demo`` returned from its ``.npz`` cache.  Defaults to the
    cache-hit reason text; a caller with a different "no materials" reason may
    override it, as long as it is still non-empty."""
    return not_applicable_record(reason, center_xy=center_xy, radius_m=radius_m,
                                  algorithm_id=algorithm_id)


def computed_record(times: Sequence[float], values: Sequence[float], *,
                     center_xy: Tuple[float, float], radius_m: float = RADIUS_M,
                     algorithm_id: str = ALGORITHM_ID) -> DiagnosticRecord:
    times_t = tuple(float(t) for t in times)
    values_t = tuple(float(v) for v in values)
    if not times_t or len(times_t) != len(values_t):
        raise ValueError(
            "computed_record requires equal-length, non-empty times/values "
            f"(got {len(times_t)} times, {len(values_t)} values)")
    return DiagnosticRecord(
        label=LABEL, status="computed", algorithm_id=str(algorithm_id),
        radius_m=float(radius_m),
        centre_xy_m=(float(center_xy[0]), float(center_xy[1])),
        times=times_t, values=values_t, reason=None)


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------
def get_concentration_reader(cobj: Any) -> Callable[[float], np.ndarray]:
    """Adapt a flopy ``gwt.output.concentration()`` binary-file object into the
    ``get_concentration(t) -> ncpl array`` callable ``compute_operator_a``
    expects -- reading the WHOLE field at ``totim=t`` (never a per-cell loop),
    the same read pattern the breakthrough curve already uses for one cell
    (``transport_srcpulse_demo.py:1265``,
    ``cobj.get_data(totim=t)[0, 0, extc]``)."""
    def _read(t: float) -> np.ndarray:
        return np.asarray(cobj.get_data(totim=float(t))[0, 0, :], dtype=float)
    return _read


def _weighted_average_at_time(concentration: Any, weights: np.ndarray) -> float:
    c = np.asarray(concentration, dtype=float)
    c = np.maximum(c, 0.0)  # clip negative numerical concentrations at zero
    # (T1_S6_brief.md Sec 3.2; matches transport_srcpulse_demo.py:1265's
    # np.maximum(..., 0.0) breakthrough clip, so A and the taught metric treat
    # a negative numerical artifact the same way)
    denom = float(np.sum(weights))
    if not (denom > 0.0):
        raise ValueError(
            "operator A: zero (or non-finite) total weight inside the disc -- "
            "refusing to return NaN (T1_S6_brief.md Sec 3.2, 'Zero denominator: "
            "error, never NaN')")
    return float(np.dot(c, weights) / denom)


def compute_series(weights: np.ndarray,
                    get_concentration: Callable[[float], Any],
                    times: Sequence[float]) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    """The C_A(t) series: ``get_concentration(t)`` is called EXACTLY ONCE per
    entry of ``times`` (never more, never per-cell) -- weights are computed
    once by the caller and reused for every time."""
    times_out = []
    values_out = []
    for t in times:
        c = get_concentration(t)
        values_out.append(_weighted_average_at_time(c, weights))
        times_out.append(float(t))
    return tuple(times_out), tuple(values_out)


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------
def compute_operator_a(
        *,
        cell_polygons: Sequence[Optional[Polygon]],
        heads: Any,
        top: Any,
        botm: Any,
        porosity: Union[float, Any],
        get_concentration: Callable[[float], Any],
        times: Sequence[float],
        cell_size_m: float,
        center_xy: Tuple[float, float],
        radius_m: float = RADIUS_M,
        quad_segs: int = QUAD_SEGS,
        algorithm_id: str = ALGORITHM_ID,
        active: Optional[Any] = None) -> DiagnosticRecord:
    """Compute operator A's C_A(t) series for one production run, or return a
    structured ``not_applicable`` record when the intended cell size exceeds
    the disc radius (``T1_open_definitions.md`` Sec 2.1).

    Invokes NO solve: every argument is already-produced data (cell polygons,
    a static head/top/botm geometry, a concentration reader over already
    written output).  Raises ``ValueError`` rather than returning NaN if the
    total in-disc weight is zero (Sec 3.2).
    """
    if not is_applicable(cell_size_m, radius_m):
        return not_applicable_record(
            f"intended cell size {float(cell_size_m):g} m exceeds operator A's "
            f"{float(radius_m):g} m disc radius -- the disc would collapse into "
            "(or nearly into) a single cell, the observation it exists to "
            "contrast with (T1_open_definitions.md Sec 2.1); not reported as a "
            "robustness result.",
            center_xy=center_xy, radius_m=radius_m, algorithm_id=algorithm_id)

    disc = disc_polygon(center_xy, radius_m=radius_m, quad_segs=quad_segs)
    areas = cell_intersection_areas(cell_polygons, disc)
    b_sat = saturated_thickness(heads, top, botm)
    weights = cell_weights(areas, b_sat, porosity, active=active)
    times_out, values_out = compute_series(weights, get_concentration, times)
    return computed_record(times_out, values_out, center_xy=center_xy,
                            radius_m=radius_m, algorithm_id=algorithm_id)
