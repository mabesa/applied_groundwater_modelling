"""
scratch_io.py — lightweight, FloPy-free reader for the case-study "exports/" bundle.

This module is the ONLY dependency of the student *scratch* analysis notebook
(``scratch_analysis_template.ipynb``). It reads the small, portable artifacts that
the *steward* produced with ``steward_export_lightweight.ipynb`` and exports into an
``exports/`` folder that travels inside the submission ZIP.

Design contract
---------------
* This file is **template-local** (it lives next to the scratch notebook) and is
  copied into the submission ZIP. It must therefore stay import-light.
* It is **FloPy-free**. It never imports ``flopy`` or ``pyemu``, never reads a model
  workspace (``.hds``, ``.cbc``, ``.nam``, ``.list`` ...) and never depends on the
  ``_SUPPORT`` repo helpers. Everything it needs is in ``exports/``.
* Allowed third-party imports: ``numpy``, ``pandas``, ``geopandas`` (plus stdlib).

Because of this contract the scratch notebook re-runs from the extracted ZIP alone,
on any machine with a scientific-Python + geopandas environment — no MODFLOW, no
FloPy, no course repository, no heavy model workspaces.

Export bundle (schema 1.0)
--------------------------
``exports/``
    run_info.json                  provenance + manifest (always present)
    flow_heads_sub_base.gpkg       heads, no wells        (required)
    flow_heads_sub_wells.gpkg      heads, with wells      (required)
    flow_heads_sub_scenario.gpkg   heads, forcing scenario (optional)
    flow_budget_summary.csv        list-file budget terms (required)
    transport_breakthrough.csv     C(t) at monitoring well (optional)
    transport_meta.json            transport scenario metadata (optional)
    pathlines_summary.csv          MODPATH summary (optional)

Head GeoPackages carry polygon cell geometry in Swiss LV95 (EPSG:2056) with columns
``cellid`` (``"row_col"``), ``row``, ``col`` and ``head_m`` (NaN where the cell was
dry / no-flow). Because area is intrinsic to the polygons, drawdown areas are computed
directly from the geometry — no cell-size assumption is baked in here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd

# ---------------------------------------------------------------------------
# Schema / constants
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "1.0"

#: Target coordinate reference system for every spatial export (Swiss LV95).
EXPORT_EPSG = 2056

#: Logical export name -> file on disk, relative to the exports/ folder.
EXPORT_FILES = {
    "run_info": "run_info.json",
    "flow_heads_base": "flow_heads_sub_base.gpkg",
    "flow_heads_wells": "flow_heads_sub_wells.gpkg",
    "flow_heads_scenario": "flow_heads_sub_scenario.gpkg",
    "flow_budget": "flow_budget_summary.csv",
    "transport_breakthrough": "transport_breakthrough.csv",
    "transport_meta": "transport_meta.json",
    "pathlines": "pathlines_summary.csv",
}

#: which -> head GeoPackage file name.
_HEADS_FILES = {
    "base": "flow_heads_sub_base.gpkg",
    "wells": "flow_heads_sub_wells.gpkg",
    "scenario": "flow_heads_sub_scenario.gpkg",
}

#: Columns every head GeoPackage must carry (besides geometry).
_HEADS_REQUIRED_COLS = ("cellid", "row", "col", "head_m")


# ---------------------------------------------------------------------------
# Environment guard
# ---------------------------------------------------------------------------
def assert_no_flopy() -> None:
    """Fail loudly if a heavy modelling package leaked into the scratch kernel.

    The scratch analysis notebook must run from the submission ZIP alone, so it
    must never import ``flopy`` or ``pyemu``. Call this at the very start and the
    very end of the notebook: if either module is present in ``sys.modules`` the
    notebook is no longer a faithful "rerun from ZIP" artifact.
    """
    leaked = [pkg for pkg in ("flopy", "pyemu") if pkg in sys.modules]
    if leaked:
        raise RuntimeError(
            "scratch_io must stay FloPy-free but these heavy packages are "
            f"imported in this kernel: {leaked}. Restart the kernel and do NOT "
            "import flopy/pyemu (or _SUPPORT helpers that import them) in the "
            "scratch notebook — it must rerun from the submission ZIP alone."
        )


# ---------------------------------------------------------------------------
# Locating the exports/ folder
# ---------------------------------------------------------------------------
def find_exports(start=None) -> Path:
    """Locate the ``exports/`` folder from wherever the notebook was opened.

    Works both when the scratch notebook sits inside the group folder (next to
    ``exports/``) and when a student extracts the submission ZIP into a shallow
    folder (notebook + ``exports/`` side by side, possibly one level down).

    Parameters
    ----------
    start : str or Path, optional
        Directory to start searching from. Defaults to the current working
        directory.

    Returns
    -------
    Path
        The directory that contains ``run_info.json``.

    Raises
    ------
    FileNotFoundError
        If no ``exports/`` folder with a ``run_info.json`` can be found nearby.
    """
    start = Path(start).expanduser().resolve() if start is not None else Path.cwd().resolve()

    def _has_manifest(d: Path) -> bool:
        return (d / EXPORT_FILES["run_info"]).is_file()

    # 1) Direct candidates: the start dir itself, its exports/ child, and the
    #    same two one level up (covers "notebook is one folder deep in the ZIP").
    candidates = [
        start / "exports",
        start,
        start.parent / "exports",
        start.parent,
    ]
    for cand in candidates:
        if cand.is_dir() and _has_manifest(cand):
            return cand

    # 2) Shallow recursive fallback: any exports/run_info.json within a couple of
    #    levels of `start` (bounded so we never walk a whole home directory).
    seen: set = set()
    for base in (start, start.parent):
        if base in seen or not base.is_dir():
            continue
        seen.add(base)
        for manifest in sorted(base.glob("*/run_info.json")) + sorted(
            base.glob("*/*/run_info.json")
        ):
            if manifest.parent.name == "exports" or _has_manifest(manifest.parent):
                return manifest.parent

    raise FileNotFoundError(
        "Could not find an 'exports/' folder containing run_info.json near "
        f"{start}. Open this notebook inside your group folder (next to exports/) "
        "or extract the submission ZIP so the notebook and exports/ sit together."
    )


def _resolve_exports(exports) -> Path:
    """Return a validated exports directory (accepts None, str, or Path)."""
    if exports is None:
        return find_exports()
    exports = Path(exports).expanduser()
    if exports.name != "exports" and (exports / "exports").is_dir():
        exports = exports / "exports"
    if not exports.is_dir():
        raise FileNotFoundError(f"exports folder does not exist: {exports}")
    return exports


def available_exports(exports=None) -> dict:
    """Return a ``{logical_name: path_or_None}`` map of which artifacts are present.

    Missing optional artifacts (scenario heads, transport, pathlines) map to
    ``None`` so cards can degrade gracefully instead of crashing.
    """
    ex = _resolve_exports(exports)
    out: dict = {}
    for name, fname in EXPORT_FILES.items():
        path = ex / fname
        out[name] = path if path.is_file() else None
    return out


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
def load_run_info(exports=None) -> dict:
    """Load and return ``run_info.json`` (the provenance + manifest record)."""
    ex = _resolve_exports(exports)
    path = ex / EXPORT_FILES["run_info"]
    if not path.is_file():
        raise FileNotFoundError(f"run_info.json not found in {ex}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def check_schema(run_info: dict) -> bool:
    """Validate a ``run_info`` dict against the schema this reader understands.

    Checks the presence of a ``schema_version`` with a matching *major* version
    and the required top-level keys. Returns ``True`` on success, otherwise
    raises ``ValueError`` describing the mismatch.
    """
    version = run_info.get("schema_version")
    if version is None:
        raise ValueError("run_info.json has no 'schema_version' field.")
    major_have = str(version).split(".")[0]
    major_want = SCHEMA_VERSION.split(".")[0]
    if major_have != major_want:
        raise ValueError(
            f"run_info schema_version {version!r} is incompatible with this "
            f"scratch_io (expects {SCHEMA_VERSION}). Ask the steward to re-export "
            "or update scratch_io.py to match."
        )
    required = ("schema_version", "group_number", "crs", "exports")
    missing = [k for k in required if k not in run_info]
    if missing:
        raise ValueError(f"run_info.json is missing required keys: {missing}")
    return True


# ---------------------------------------------------------------------------
# Flow heads
# ---------------------------------------------------------------------------
def load_heads_gpkg(which, exports=None) -> gpd.GeoDataFrame:
    """Load a head GeoPackage as a GeoDataFrame.

    Parameters
    ----------
    which : {"base", "wells", "scenario"}
        Which head field to load.
    exports : str or Path, optional
        Exports folder; auto-located if omitted.

    Returns
    -------
    geopandas.GeoDataFrame
        Polygon cells with ``cellid``, ``row``, ``col``, ``head_m`` columns in
        EPSG:2056. ``head_m`` is NaN where the cell was dry / no-flow.
    """
    if which not in _HEADS_FILES:
        raise ValueError(f"which must be one of {sorted(_HEADS_FILES)}, got {which!r}")
    ex = _resolve_exports(exports)
    path = ex / _HEADS_FILES[which]
    if not path.is_file():
        raise FileNotFoundError(
            f"{path.name} not present in {ex}. "
            + (
                "Scenario heads are optional — check available_exports() first."
                if which == "scenario"
                else "This is a required export; ask the steward to re-run."
            )
        )
    gdf = gpd.read_file(path)
    _assert_heads_schema(gdf, path.name)
    return gdf


def _assert_heads_schema(gdf: gpd.GeoDataFrame, name: str) -> None:
    missing = [c for c in _HEADS_REQUIRED_COLS if c not in gdf.columns]
    if missing:
        raise ValueError(f"{name} is missing expected columns {missing}; got {list(gdf.columns)}")
    if gdf.geometry.isna().all():
        raise ValueError(f"{name} has no geometry.")
    epsg = gdf.crs.to_epsg() if gdf.crs is not None else None
    if epsg != EXPORT_EPSG:
        raise ValueError(f"{name} CRS is {epsg}, expected EPSG:{EXPORT_EPSG} (Swiss LV95).")


def compute_drawdown(base_gdf: gpd.GeoDataFrame, compare_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Compute drawdown = base head − compare head, cell by cell.

    A positive ``drawdown_m`` means the head *dropped* relative to the base case
    (e.g. base = no wells, compare = with wells → drawdown near the wells).

    Returns a GeoDataFrame (geometry from ``base_gdf``) with ``cellid``,
    ``head_base_m``, ``head_compare_m`` and ``drawdown_m``.
    """
    left = base_gdf[["cellid", "head_m", "geometry"]].rename(columns={"head_m": "head_base_m"})
    right = pd.DataFrame(compare_gdf[["cellid", "head_m"]]).rename(columns={"head_m": "head_compare_m"})
    merged = left.merge(right, on="cellid", how="inner")
    merged["drawdown_m"] = merged["head_base_m"] - merged["head_compare_m"]
    out = gpd.GeoDataFrame(merged, geometry="geometry", crs=base_gdf.crs)
    return out


def affected_area(gdf: gpd.GeoDataFrame, value_col: str = "drawdown_m", threshold: float = 0.5) -> float:
    """Total area (m²) of cells whose ``value_col`` exceeds ``threshold``.

    Area is taken from the polygon geometry (EPSG:2056 is metric), so no cell-size
    assumption is required. NaN values never count toward the area.
    """
    if value_col not in gdf.columns:
        raise ValueError(f"'{value_col}' not in GeoDataFrame columns {list(gdf.columns)}")
    mask = gdf[value_col].to_numpy(dtype=float) > threshold
    mask &= ~gdf[value_col].isna().to_numpy()
    if not mask.any():
        return 0.0
    selected = gdf.loc[mask]
    if selected.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        return float(selected.geometry.area.sum())
    # Fallback for point exports that carry an explicit per-cell area column.
    if "cell_area_m2" in selected.columns:
        return float(selected["cell_area_m2"].sum())
    raise ValueError(
        "affected_area needs polygon geometry (to measure area) or a "
        "'cell_area_m2' column; got non-polygon geometry without it."
    )


# ---------------------------------------------------------------------------
# Flow budget
# ---------------------------------------------------------------------------
def load_budget_summary(exports=None) -> pd.DataFrame:
    """Load ``flow_budget_summary.csv`` as a tidy DataFrame.

    Columns: ``model`` (sub_base / sub_wells / sub_scenario), ``term`` (budget
    component, e.g. ``WELLS``, ``RIVER_LEAKAGE``), ``flow_in_m3_d``,
    ``flow_out_m3_d`` and ``net_m3_d`` (in − out).
    """
    ex = _resolve_exports(exports)
    path = ex / EXPORT_FILES["flow_budget"]
    if not path.is_file():
        raise FileNotFoundError(f"{path.name} not present in {ex}")
    df = pd.read_csv(path)
    expected = {"model", "term", "flow_in_m3_d", "flow_out_m3_d"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns {sorted(missing)}; got {list(df.columns)}")
    if "net_m3_d" not in df.columns:
        df["net_m3_d"] = df["flow_in_m3_d"] - df["flow_out_m3_d"]
    return df


def river_exchange(budget_df: pd.DataFrame) -> pd.DataFrame:
    """Extract river leakage terms per model from a budget summary DataFrame.

    Returns one row per model with ``river_in_m3_d`` (river → aquifer),
    ``river_out_m3_d`` (aquifer → river) and ``net_m3_d`` (positive = net gain to
    the aquifer). Returns an empty frame if the model has no river term.
    """
    term_upper = budget_df["term"].astype(str).str.upper()
    riv = budget_df[term_upper.str.contains("RIV")].copy()
    if riv.empty:
        return pd.DataFrame(columns=["model", "river_in_m3_d", "river_out_m3_d", "net_m3_d"])
    grouped = (
        riv.groupby("model")[["flow_in_m3_d", "flow_out_m3_d"]]
        .sum()
        .rename(columns={"flow_in_m3_d": "river_in_m3_d", "flow_out_m3_d": "river_out_m3_d"})
        .reset_index()
    )
    grouped["net_m3_d"] = grouped["river_in_m3_d"] - grouped["river_out_m3_d"]
    return grouped


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
def load_transport_breakthrough(exports=None) -> pd.DataFrame:
    """Load ``transport_breakthrough.csv`` (time series C(t) at the monitoring well).

    Columns: ``time_days`` and ``concentration_mg_L``.
    """
    ex = _resolve_exports(exports)
    path = ex / EXPORT_FILES["transport_breakthrough"]
    if not path.is_file():
        raise FileNotFoundError(
            f"{path.name} not present in {ex}. Transport is optional — the group "
            "may not have run the transport scenario. Check available_exports()."
        )
    df = pd.read_csv(path)
    expected = {"time_days", "concentration_mg_L"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns {sorted(missing)}; got {list(df.columns)}")
    return df


def load_transport_meta(exports=None) -> dict:
    """Load ``transport_meta.json`` (contaminant, threshold, peak, arrival, ...)."""
    ex = _resolve_exports(exports)
    path = ex / EXPORT_FILES["transport_meta"]
    if not path.is_file():
        raise FileNotFoundError(
            f"{path.name} not present in {ex}. Transport is optional; check available_exports()."
        )
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_pathlines_summary(exports=None) -> pd.DataFrame:
    """Load ``pathlines_summary.csv`` (MODPATH particle-track summary).

    Pathlines are optional (Card B). Raises ``FileNotFoundError`` when absent so
    the card can skip cleanly.
    """
    ex = _resolve_exports(exports)
    path = ex / EXPORT_FILES["pathlines"]
    if not path.is_file():
        raise FileNotFoundError(
            f"{path.name} not present in {ex}. Pathlines are optional (MODPATH was "
            "not run or not exported)."
        )
    return pd.read_csv(path)
