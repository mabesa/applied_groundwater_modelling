"""
casestudy_doublet_roster -- M1.1: deterministic doublet-geometry extraction.

Extracts the 9 GWHE (groundwater heat exchanger) doublet geometries -- one per
student group -- from the cantonal well registry
(``Wasserfassungen_-OGD.gpkg``, CRS LV95 / EPSG:2056) and writes a
provenance-stamped ``doublet_table`` (CSV + YAML mirror).

THIS IS A DATA-SPINE STEP (charter M1.1): it produces the fixed geometry +
operating-rate inputs everything downstream (M1.2/M1.3a/M1.3b) is built on.
No model solve is required or performed here -- the optional cell-validity
gate reads the already-calibrated 05f flow model's STATIC grid/idomain, never
runs it.

Rule (fully pinned, see DESIGN_DOCS/student_casestudy_M1_steps.md, M1.1)
-------------------------------------------------------------------------
1. **Role from FASSART substring.** ``"Entnahme"`` -> extraction ("ext"),
   ``"Rückgabe"`` -> injection ("inj"). Any FASSART containing
   ``"Sickergalerie"`` / ``"Anreicherung"`` (or matching neither substring,
   e.g. a plain observation well) is excluded from the doublet pair. The
   registry has no status column, so every row is treated as current.
2. **Geometry = geometric centroid, NOT Q-weighted** (the registry carries no
   per-well Q): the extraction point is the geometric centroid of a
   concession's Entnahme wells; the injection point is the centroid of its
   Rückgabe wells. Wells are sorted by GWR_ID before any averaging so ties
   resolve the same way every run. Coordinates are rounded to 0.1 m.
3. **Spread / cell-validity gate.** If a role's wells span more than
   ``SPREAD_LIMIT_M`` (50 m, max pairwise distance) OR the centroid is
   in-river (``in_river`` -- i.e. within ``RIVER_BUFFER_M`` = 20 m of a
   mapped Limmat/Sihl river polygon; this is a BUFFER proximity test, not a
   strict inside-the-polygon test) or falls in an inactive 05f cell, the row
   is flagged and the geometry falls back to the single REAL well of that
   role nearest the (bad) centroid -- never a synthetic point sitting in a
   bad spot. If only one real well exists for that role (n=1), there is
   nothing to fall back to: the point is kept, but the violation is flagged
   verbatim for human review.
4. **Operating Q = licensed max.** Parsed from the free-text
   ``BESCHREIBUNG`` field's ``Ertrag`` clause (e.g. ``"Ertrag 300 - 3000
   l/min"`` -> take 3000; ``"Ertrag > 3000 l/min"`` -> take 3000 but flag it
   as a lower-bound-only estimate). Parsing is case-insensitive, tolerant of
   whitespace in ``l/min`` and of Swiss thousands separators
   (``3'000`` / ``3’000`` -> 3000). If a concession's rows carry DISAGREEING
   Ertrag clauses, the largest is picked deterministically AND a flag records
   the disagreement. Converted l/min -> m3/d via x1.44. A concession with no
   parseable ``Ertrag`` anywhere gets ``Q_m3d = None`` and a flag for manual
   assignment.

Acceptance / strict mode
------------------------
``build_doublet_table(strict=True)`` (the default, and what the ``__main__``
entry point and the committed deliverable use) RAISES rather than write a
provenance-stamped "acceptance-valid" table if either (a) the active-cell
check did not actually run (05f load degraded/skipped -> validity is
unknown), or (b) any row still has an unresolved bad-validity after the
fallback rule (a gate-tripped point that remains in-river / inactive /
out-of-domain, including an n=1 kept-bad point). The degraded / None-validity
path is available ONLY via ``strict=False``, which is explicitly a
non-acceptance build for inspection/debugging.

Known outcome (grounded against the live registry, 2026-07 snapshot)
----------------------------------------------------------------------
- The roster is a CLEAN set: every concession is a single-Entnahme +
  single-Rückgabe (or tightly-clustered) doublet whose centroids are
  in-domain, in an active 05f cell, and clear of the river buffer -> all 9
  resolve with ``ext_method == inj_method == "centroid"`` and NO flags.
- G4 is **b010120** (a clean doublet ~228 m / ~343 m clear of any river),
  the user-approved swap for the gallery-only **b010190** (which must NOT
  appear). It replaced an earlier candidate, b010005, which was dropped
  because b010005's lone Rückgabe well sat ~14 m inside a river with no
  fallback and its Entnahme wells spanned ~70 m -- i.e. it could not clear
  the gate cleanly. b010005 is no longer in the roster.
- All 9 concessions resolve the ordinary "300 - 3000 l/min" Ertrag range
  (Q = 3000 l/min = 4320 m3/d).

Deliverable
-----------
``build_doublet_table()`` returns a ``pandas.DataFrame`` (9 rows) and writes
it deterministically to ``PROJECT/workspace/template/doublet_table.csv``
(+ a ``.yaml`` mirror). Re-running yields byte-identical coordinates -- no
randomness anywhere in this module.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# ---------------------------------------------------------------------------
# Pinned constants
# ---------------------------------------------------------------------------

# The 9 concessions, ordered to match case_config.yaml's existing group
# numbering (group N -> CONCESSIONS[N]), so "group" == f"G{N}" lines up with
# the acceptance criterion "G4 = b010120". b010120 is the user-approved swap
# for the gallery-only b010190 (which is deliberately ABSENT); it replaced an
# earlier b010005 candidate that could not clear the river/spread gate cleanly.
CONCESSIONS: Tuple[str, ...] = (
    "b010210", "b010219", "b010201", "b010236", "b010120",
    "b010223", "b010227", "b010213", "b010207",
)

SPREAD_LIMIT_M = 50.0     # max pairwise distance within a role before flag+fallback
RIVER_BUFFER_M = 20.0     # distance to a river polygon counted as "in river"
LMIN_TO_M3D = 1.44        # l/min -> m3/d
WELLS_LAYER = "GS_GRUNDWASSERFASSUNGEN_OGD_P"
CRS = "EPSG:2056"

# repo_root/_SUPPORT/src/casestudy_doublet_roster.py -> repo_root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT_CSV = _REPO_ROOT / "PROJECT" / "workspace" / "template" / "doublet_table.csv"
DEFAULT_OUT_YAML = DEFAULT_OUT_CSV.with_suffix(".yaml")

# A number is either thousands-grouped with a Swiss separator (3'000 / 3’000 /
# 1'234'567) OR a plain integer/decimal (3000 / 300.5 / 300,5). Thousands
# separators are stripped and a ',' decimal is normalized to '.' in
# ``_num_to_float`` below. Case-insensitive; whitespace tolerated inside
# ``l / min``.
_NUM = r"\d{1,3}(?:[’']\d{3})+|\d+(?:[.,]\d+)?"
_ERTRAG_RE = re.compile(
    r"Ertrag\s*(?P<op><=|>=|>|<)?\s*(?P<num1>" + _NUM + r")"
    r"\s*(?:-\s*(?P<num2>" + _NUM + r"))?\s*l\s*/\s*min",
    re.IGNORECASE,
)


def _num_to_float(token: str) -> float:
    """Normalize a captured Ertrag number token to a float.

    Strips Swiss thousands separators (``'`` / ``’``) then treats a remaining
    ``,`` as a decimal point (Swiss/European decimal comma).
    """
    cleaned = token.replace("’", "").replace("'", "").replace(",", ".")
    return float(cleaned)

_CHUNK_SIZE = 65536


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _sha256_file(path: Path) -> str:
    """sha256 hex digest of a file's bytes (streamed, no full read into memory)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def _round1(v: float) -> float:
    return round(float(v), 1)


def _max_pairwise_dist(pts: Sequence[Tuple[float, float]]) -> float:
    if len(pts) < 2:
        return 0.0
    return max(math.hypot(ax - bx, ay - by) for (ax, ay), (bx, by) in combinations(pts, 2))


def _role_from_fassart(fassart: Any) -> Optional[str]:
    """Classify a FASSART string into "ext" / "inj" / None (excluded).

    A string containing BOTH "Entnahme" and "Rückgabe" is ambiguous -- it is
    NOT silently classified as extraction. It returns the sentinel
    ``"ambiguous"`` so the caller can flag it (see ``_classify_roles``). This
    does not occur in the current registry but is a latent trap for a future
    roster swap.
    """
    if not isinstance(fassart, str):
        return None
    if "Sickergalerie" in fassart or "Anreicherung" in fassart:
        return None
    has_ext = "Entnahme" in fassart
    has_inj = "Rückgabe" in fassart
    if has_ext and has_inj:
        return "ambiguous"
    if has_ext:
        return "ext"
    if has_inj:
        return "inj"
    return None


def _parse_ertrag(texts: Sequence[Any]) -> Dict[str, Any]:
    """Parse the licensed-yield ``Ertrag`` clause out of a concession's
    BESCHREIBUNG texts (all rows -- Entnahme rows normally carry it,
    Rückgabe rows normally don't).

    Rule: a plain range "X - Y l/min" resolves to Y (exact upper bound). A
    "> Y l/min" / ">= Y l/min" clause resolves to Y but is flagged as a
    lower-bound-only estimate (the true max could be higher). A "<= X
    l/min" or bare "N l/min" resolves to that number, not flagged. If a
    concession's rows carry DISAGREEING Ertrag values, the largest resolved
    value wins (deterministic -- values are compared numerically, not by row
    order) AND ``disagreement`` is set True so the caller can flag it (this is
    NOT observed in the 9 concessions this module currently targets, where
    each has one distinct Ertrag clause across all its rows).

    Returns a dict with ``raw`` (all distinct clause strings), ``q_lmin``
    (chosen value or None), ``lower_bound`` (bool), and ``disagreement``
    (bool).
    """
    resolved: List[Tuple[float, bool, str]] = []
    for t in texts:
        if not isinstance(t, str):
            continue
        m = _ERTRAG_RE.search(t)
        if not m:
            continue
        op = m.group("op")
        num1 = _num_to_float(m.group("num1"))
        num2 = m.group("num2")
        if num2 is not None:
            val = _num_to_float(num2)
            lower_bound = False
        elif op in (">", ">="):
            val = num1
            lower_bound = True
        else:
            val = num1
            lower_bound = False
        resolved.append((val, lower_bound, m.group(0)))
    if not resolved:
        return dict(raw=None, q_lmin=None, lower_bound=False, disagreement=False)
    # Disagreement = more than one DISTINCT resolved value across the rows.
    distinct_values = {round(r[0], 6) for r in resolved}
    disagreement = len(distinct_values) > 1
    # deterministic pick: largest value first; on a tie, prefer the exact
    # (non-lower-bound) reading.
    resolved.sort(key=lambda r: (-r[0], r[1]))
    val, lower_bound, raw = resolved[0]
    all_raw = " | ".join(sorted({r[2] for r in resolved}))
    return dict(raw=all_raw, q_lmin=val, lower_bound=lower_bound,
                disagreement=disagreement)


# ---------------------------------------------------------------------------
# cell-validity context (in_domain / in_active_cell / in_river)
# ---------------------------------------------------------------------------
@dataclass
class _CellValidityContext:
    """Bundles whatever domain/river/grid info could be loaded, plus a clear
    record of what was NOT checked so a failed/skipped load never silently
    reads as "passed"."""
    domain_checked: bool = False
    river_checked: bool = False
    active_cell_checked: bool = False
    boundary_poly: Any = None
    rivers_gdf: Any = None
    modelgrid: Any = None
    idomain: Any = None
    boundary_file: Optional[str] = None
    boundary_sha256: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def check(self, x: float, y: float) -> Dict[str, Optional[bool]]:
        out: Dict[str, Optional[bool]] = dict(in_domain=None, in_active_cell=None, in_river=None)
        pt = Point(x, y)
        if self.domain_checked and self.boundary_poly is not None:
            # covers (not contains) so a point exactly ON the boundary counts
            # as in-domain.
            out["in_domain"] = bool(self.boundary_poly.covers(pt))
        if self.river_checked and self.rivers_gdf is not None:
            if len(self.rivers_gdf):
                out["in_river"] = bool(self.rivers_gdf.distance(pt).min() <= RIVER_BUFFER_M)
            else:
                out["in_river"] = False
        if self.active_cell_checked and self.modelgrid is not None and self.idomain is not None:
            try:
                cellid = self.modelgrid.intersect(x, y)
                out["in_active_cell"] = bool(self.idomain[cellid] > 0)
            except Exception:
                # point falls entirely outside the grid -> not a valid/active cell.
                out["in_active_cell"] = False
        return out

    def is_bad(self, validity: Dict[str, Optional[bool]]) -> bool:
        """True if any CHECKED validity flag actively fails (unknown/None never counts as bad)."""
        if validity.get("in_domain") is False:
            return True
        if validity.get("in_river") is True:
            return True
        if validity.get("in_active_cell") is False:
            return True
        return False


def _build_cell_validity_context(check_active_cell: bool = True) -> _CellValidityContext:
    """Build the cell-validity context against the calibrated 05f model.

    Primary path (per the M1.1 spec): a single
    ``transport_srcpulse_demo.load_limmat_flow()`` call, which returns
    ``(cgwf, boundary_gdf, rivers_gdf, exe)`` for the STATIC, already-solved
    05f-calibrated flow model (its modelgrid pickle restores the 30-degree
    rotation -- this module never re-rotates or re-solves anything).

    If that fails (e.g. mf6 executable missing, no network for the cached
    model download) or ``check_active_cell=False``, this degrades to a
    boundary+river-only context (independent of the flow-model load) so
    in_domain/in_river can still be reported; ``active_cell_checked`` stays
    False and a note records exactly why -- never a silent pass.
    """
    if not check_active_cell:
        ctx = _CellValidityContext()
        ctx.notes.append("cell-validity check disabled by caller (check_active_cell=False); "
                          "in_domain/in_active_cell/in_river NOT RUN")
        return ctx

    try:
        import transport_srcpulse_demo as tsd
        from data_utils import download_named_file

        cgwf, boundary_gdf, rivers_gdf, _exe = tsd.load_limmat_flow()
        boundary_path = Path(download_named_file(name="model_boundary", data_type="gis"))
        idomain = cgwf.dis.idomain.array[0]
        modelgrid = cgwf.modelgrid
        try:
            boundary_poly = boundary_gdf.union_all()
        except AttributeError:  # older geopandas/shapely
            boundary_poly = boundary_gdf.unary_union
        return _CellValidityContext(
            domain_checked=True, river_checked=True, active_cell_checked=True,
            boundary_poly=boundary_poly, rivers_gdf=rivers_gdf,
            modelgrid=modelgrid, idomain=idomain,
            boundary_file=str(boundary_path), boundary_sha256=_sha256_file(boundary_path),
        )
    except Exception as e_flow:
        # Degrade to boundary+river only (does not need the flow model / mf6 exe).
        try:
            from data_utils import download_named_file

            boundary_path = Path(download_named_file(name="model_boundary", data_type="gis"))
            boundary_gdf = gpd.read_file(boundary_path)
            rivers_path = Path(download_named_file(name="rivers", data_type="gis"))
            rivers_gdf_full = gpd.read_file(rivers_path)
            try:
                boundary_poly = boundary_gdf.union_all()
            except AttributeError:
                boundary_poly = boundary_gdf.unary_union
            rivers_gdf = rivers_gdf_full[
                rivers_gdf_full["GEWAESSERNAME"].isin(["Limmat", "Sihl"])
                & rivers_gdf_full.intersects(boundary_gdf.geometry.iloc[0])
            ]
            ctx = _CellValidityContext(
                domain_checked=True, river_checked=True, active_cell_checked=False,
                boundary_poly=boundary_poly, rivers_gdf=rivers_gdf,
                boundary_file=str(boundary_path), boundary_sha256=_sha256_file(boundary_path),
            )
            ctx.notes.append(
                f"05f flow-model load failed ({e_flow!r}); in_active_cell NOT RUN "
                "(in_domain/in_river still checked against the boundary/river GIS artifacts)."
            )
            return ctx
        except Exception as e_gis:
            ctx = _CellValidityContext()
            ctx.notes.append(
                f"cell-validity check NOT RUN at all -- flow-model load failed ({e_flow!r}) "
                f"AND boundary/river GIS fallback also failed ({e_gis!r}); "
                "in_domain/in_active_cell/in_river all None for every row."
            )
            return ctx


# ---------------------------------------------------------------------------
# registry load
# ---------------------------------------------------------------------------
def _load_registry() -> Tuple[gpd.GeoDataFrame, Path]:
    from data_utils import download_named_file

    path = Path(download_named_file(name="wells", data_type="gis"))
    gdf = gpd.read_file(path, layer=WELLS_LAYER)
    return gdf, path


# ---------------------------------------------------------------------------
# per-role geometry (centroid, spread gate, fallback)
# ---------------------------------------------------------------------------
def _centroid_or_fallback(wells: List[Dict[str, Any]], role_label: str,
                          ctx: _CellValidityContext) -> Dict[str, Any]:
    """*wells* must already be sorted by GWR_ID (determinism)."""
    pts = [(float(w["E"]), float(w["N"])) for w in wells]
    gwr_ids = [w["GWR_ID"] for w in wells]
    n = len(wells)

    spread = _max_pairwise_dist(pts)
    cx = _round1(sum(p[0] for p in pts) / n)
    cy = _round1(sum(p[1] for p in pts) / n)

    validity = ctx.check(cx, cy)
    spread_violation = spread > SPREAD_LIMIT_M
    cell_violation = ctx.is_bad(validity)

    method = "centroid"
    chosen_gwr: Optional[str] = gwr_ids[0] if n == 1 else None
    flags: List[str] = []

    if spread_violation or cell_violation:
        reasons = []
        if spread_violation:
            reasons.append(f"spread {spread:.1f} m > {SPREAD_LIMIT_M:.0f} m")
        if validity.get("in_river"):
            reasons.append("centroid within river buffer")
        if validity.get("in_active_cell") is False:
            reasons.append("centroid in an inactive 05f cell")
        if validity.get("in_domain") is False:
            reasons.append("centroid outside model domain")
        reason_str = "; ".join(reasons)

        if n == 1:
            # Nothing to fall back to -- the centroid already IS the one real
            # well. Keep it, but flag it unresolved for human review.
            flags.append(
                f"{role_label}: gate tripped ({reason_str}) but n=1 real well -- "
                f"no fallback alternative exists (well {gwr_ids[0]}); "
                "flagged for human review, geometry kept as-is."
            )
        else:
            # Fall back to the nearest REAL well; ties broken by sorted GWR_ID
            # (stable sort of (distance, gwr_id) -> deterministic).
            dists = sorted(
                ((math.hypot(px - cx, py - cy), gid, (px, py))
                 for (px, py), gid in zip(pts, gwr_ids)),
                key=lambda d: (d[0], d[1]),
            )
            _, chosen_gwr, (fx, fy) = dists[0]
            fx, fy = _round1(fx), _round1(fy)
            fallback_validity = ctx.check(fx, fy)
            flags.append(
                f"{role_label}: gate tripped ({reason_str}) -- fell back to "
                f"nearest real well {chosen_gwr} at ({fx}, {fy})."
            )
            method = "fallback"
            cx, cy = fx, fy
            validity = fallback_validity
            if ctx.is_bad(validity):
                flags.append(
                    f"{role_label}: fallback well {chosen_gwr} ALSO fails cell-validity -- "
                    "unresolved, flagged for human review."
                )

    # unresolved_bad: the FINAL chosen point (after any fallback) still fails a
    # CHECKED validity flag -- i.e. the gate could not be resolved to a good
    # location. Strict-mode acceptance uses this.
    return dict(
        E=cx, N=cy, method=method, spread_m=round(spread, 1), n=n,
        gwr_ids=gwr_ids, chosen_gwr=chosen_gwr, validity=validity, flags=flags,
        unresolved_bad=ctx.is_bad(validity),
    )


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def build_doublet_table(check_active_cell: bool = True,
                        out_csv: Optional[Path] = None,
                        out_yaml: Optional[Path] = None,
                        write: bool = True,
                        strict: bool = True) -> pd.DataFrame:
    """Build the 9-row doublet_table and (by default) write it to disk.

    Parameters
    ----------
    check_active_cell : bool
        If True (default), attempt the full in_domain/in_active_cell/in_river
        gate against the calibrated 05f model + boundary/river GIS. If False,
        skip it entirely (geometry + Q + provenance are still computed) --
        the corresponding columns are ``None`` and a flag records that the
        check was not run. (Setting this False is incompatible with
        ``strict=True`` -- see below.)
    out_csv, out_yaml : Path, optional
        Override the default output locations
        (``PROJECT/workspace/template/doublet_table.{csv,yaml}``).
    write : bool
        If False, compute the table but do not write it to disk (used by
        tests that only want the in-memory result).
    strict : bool
        If True (default -- and what ``__main__`` and the committed deliverable
        use), RAISE ``RuntimeError`` rather than return/write a
        provenance-stamped "acceptance-valid" table when either (a) the
        active-cell check did not actually run (05f load degraded/skipped ->
        validity unknown), or (b) any row still has an unresolved bad-validity
        after the fallback rule (a gate-tripped point that remains in-river /
        inactive / out-of-domain, including an n=1 kept-bad point). Set
        ``strict=False`` for an explicitly NON-acceptance build (e.g. to
        inspect a degraded/None-validity table); the raise conditions become
        recorded flags instead.

    Returns
    -------
    pandas.DataFrame
        9 rows, one per concession, columns as documented in the module
        docstring / DESIGN_DOCS/student_casestudy_M1_steps.md (M1.1).

    Raises
    ------
    RuntimeError
        In ``strict=True`` mode, if the active-cell check did not run or any
        row is unresolved-bad after fallback (message lists the offending
        rows/reasons).
    """
    gdf, source_path = _load_registry()
    source_sha256 = _sha256_file(source_path)

    gdf = gdf.copy()
    gdf["concession"] = gdf["GWR_ID"].str.split("_").str[0]
    gdf["role"] = gdf["FASSART"].map(_role_from_fassart)
    # Determinism: every downstream grouping/averaging operates on wells in
    # sorted-GWR_ID order.
    gdf = gdf.sort_values("GWR_ID", kind="mergesort").reset_index(drop=True)

    ctx = _build_cell_validity_context(check_active_cell=check_active_cell)

    rows: List[Dict[str, Any]] = []
    _acceptance_violations: List[str] = []
    for group_idx, concession in enumerate(CONCESSIONS):
        sub = gdf[gdf["concession"] == concession]
        if sub.empty:
            raise ValueError(f"concession {concession!r} not found in registry {source_path}")

        ext_wells = sub[sub["role"] == "ext"][["GWR_ID", "E", "N"]].to_dict("records")
        inj_wells = sub[sub["role"] == "inj"][["GWR_ID", "E", "N"]].to_dict("records")
        if not ext_wells:
            raise ValueError(f"{concession}: no Entnahme (extraction) wells found in registry")
        if not inj_wells:
            raise ValueError(f"{concession}: no Rückgabe (injection) wells found in registry")

        # Both-role guard: a FASSART string that contains BOTH "Entnahme" and
        # "Rückgabe" is ambiguous and was excluded from both role sets above --
        # flag it (a latent trap for a future roster swap; not in the current
        # registry).
        ambiguous = sub[sub["role"] == "ambiguous"]["GWR_ID"].tolist()

        ext = _centroid_or_fallback(ext_wells, "ext", ctx)
        inj = _centroid_or_fallback(inj_wells, "inj", ctx)

        ertrag = _parse_ertrag(sub["BESCHREIBUNG"].tolist())
        flags: List[str] = list(ext["flags"]) + list(inj["flags"])

        if ambiguous:
            flags.append(
                "role: FASSART strings contain BOTH 'Entnahme' and 'Rückgabe' for "
                f"well(s) {'|'.join(ambiguous)} -- ambiguous role, excluded from the "
                "doublet pair, flagged for human review."
            )

        if ertrag["q_lmin"] is None:
            q_m3d: Optional[float] = None
            flags.append(
                "Q: no 'Ertrag' clause parsed anywhere in this concession's BESCHREIBUNG -- "
                "Q_m3d=None, flagged for manual assignment."
            )
        else:
            q_m3d = round(ertrag["q_lmin"] * LMIN_TO_M3D, 2)
            if ertrag["lower_bound"]:
                flags.append(
                    f"Q: Ertrag clause is a lower-bound only ('{ertrag['raw']}') -- "
                    "Q_m3d taken as the stated floor; the true licensed max may be higher."
                )
            if ertrag["disagreement"]:
                flags.append(
                    f"Q: rows carry DISAGREEING Ertrag clauses ('{ertrag['raw']}') -- "
                    "took the largest deterministically; flagged for human review."
                )

        for note in ctx.notes:
            flags.append(f"cell-validity: {note}")

        def _combine_domain(a, b):
            if a is None or b is None:
                return None
            return bool(a and b)

        def _combine_river(a, b):
            if a is None or b is None:
                return None
            return bool(a or b)

        in_domain_ext = ext["validity"].get("in_domain")
        in_domain_inj = inj["validity"].get("in_domain")
        in_active_cell_ext = ext["validity"].get("in_active_cell")
        in_active_cell_inj = inj["validity"].get("in_active_cell")
        in_river_ext = ext["validity"].get("in_river")
        in_river_inj = inj["validity"].get("in_river")

        in_domain = _combine_domain(in_domain_ext, in_domain_inj)
        in_active_cell = _combine_domain(in_active_cell_ext, in_active_cell_inj)
        in_river = _combine_river(in_river_ext, in_river_inj)

        rows.append(dict(
            group=f"G{group_idx}",
            concession=concession,
            inj_E=inj["E"], inj_N=inj["N"],
            ext_E=ext["E"], ext_N=ext["N"],
            Q_m3d=q_m3d,
            source_file=str(source_path),
            source_sha256=source_sha256,
            boundary_file=ctx.boundary_file,
            boundary_sha256=ctx.boundary_sha256,
            gwr_ids_ext="|".join(ext["gwr_ids"]),
            gwr_ids_inj="|".join(inj["gwr_ids"]),
            n_ext=ext["n"],
            n_inj=inj["n"],
            ext_method=ext["method"],
            inj_method=inj["method"],
            ertrag_raw=ertrag["raw"],
            ertrag_max_lmin=ertrag["q_lmin"],
            crs=CRS,
            spread_ext_m=ext["spread_m"],
            spread_inj_m=inj["spread_m"],
            in_domain=in_domain,
            in_active_cell=in_active_cell,
            in_river=in_river,
            in_domain_ext=in_domain_ext,
            in_domain_inj=in_domain_inj,
            in_active_cell_ext=in_active_cell_ext,
            in_active_cell_inj=in_active_cell_inj,
            in_river_ext=in_river_ext,
            in_river_inj=in_river_inj,
            flags="; ".join(flags) if flags else "",
        ))

        # Collect strict-mode acceptance violations for THIS row.
        for role_label, role in (("ext", ext), ("inj", inj)):
            if role["unresolved_bad"]:
                _acceptance_violations.append(
                    f"{concession} ({role_label}): unresolved bad-validity after fallback "
                    f"-- {role['validity']}"
                )

    columns = [
        "group", "concession", "inj_E", "inj_N", "ext_E", "ext_N", "Q_m3d",
        "source_file", "source_sha256", "boundary_file", "boundary_sha256",
        "gwr_ids_ext", "gwr_ids_inj", "n_ext", "n_inj", "ext_method", "inj_method",
        "ertrag_raw", "ertrag_max_lmin", "crs", "spread_ext_m", "spread_inj_m",
        "in_domain", "in_active_cell", "in_river",
        "in_domain_ext", "in_domain_inj", "in_active_cell_ext", "in_active_cell_inj",
        "in_river_ext", "in_river_inj",
        "flags",
    ]
    df = pd.DataFrame(rows, columns=columns)

    # ---- strict-mode acceptance gate -------------------------------------
    if strict:
        problems: List[str] = []
        if not ctx.active_cell_checked:
            problems.append(
                "active-cell check did NOT run (05f load degraded/skipped) -- "
                "cannot certify in_active_cell; "
                + (ctx.notes[0] if ctx.notes else "no context note recorded")
            )
        problems.extend(_acceptance_violations)
        if problems:
            raise RuntimeError(
                "build_doublet_table(strict=True): refusing to emit an "
                "acceptance-valid table --\n  " + "\n  ".join(problems)
                + "\n(Re-run with strict=False to produce a NON-acceptance table for inspection.)"
            )

    if write:
        _write_outputs(df, out_csv=out_csv or DEFAULT_OUT_CSV, out_yaml=out_yaml or DEFAULT_OUT_YAML)

    return df


def _write_outputs(df: pd.DataFrame, out_csv: Path, out_yaml: Path) -> None:
    out_csv = Path(out_csv)
    out_yaml = Path(out_yaml)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)

    import yaml

    # Deterministic mirror: plain list of dicts in the same column order,
    # native Python types only (no numpy scalars) so YAML output is stable.
    records = []
    for row in df.to_dict("records"):
        clean = {}
        for k, v in row.items():
            if pd.isna(v) if not isinstance(v, str) else False:
                clean[k] = None
            else:
                clean[k] = v
        records.append(clean)
    with open(out_yaml, "w") as fh:
        yaml.safe_dump({"doublet_table": records}, fh, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    # strict=True: this raises rather than emit a provenance-stamped table if
    # the 05f active-cell check did not run or any row is unresolved-bad.
    table = build_doublet_table(strict=True)
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(table[["group", "concession", "inj_E", "inj_N", "ext_E", "ext_N",
                     "Q_m3d", "ext_method", "inj_method", "flags"]])
