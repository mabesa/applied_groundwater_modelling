"""Diagnostics utility functions for the Applied Groundwater Modelling course.

This module centralizes the environment and capability checks that were
previously embedded directly in the `0_diagnostics.ipynb` notebook.

Each function returns plain Python data structures (dict / list) so the
notebook can simply assign them into the shared `diag_results` container.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence, Dict, Any, Set


# Mapping of distribution names to importable module names (and special cases)
SPECIAL_IMPORT_NAMES = {
    "ipython": "IPython",
    "pyyaml": "yaml",
    "scikit-image": "skimage",
    "python-graphviz": "graphviz",
    "opencv-python": "cv2",
    "gdal": "osgeo",  # GDAL imports through the osgeo namespace
}


def parse_environment(
    env_file: str,
    optional_packages: Iterable[str] | None = None,
    exclude_packages: Iterable[str] | None = None,
) -> Dict[str, Any]:
    """Parse a conda/mamba environment YAML file to extract package names.

    Parameters
    ----------
    env_file : str
        Path to the YAML environment file.
    optional_packages : Iterable[str] | None
        Package names considered optional (won't block readiness).
    exclude_packages : Iterable[str] | None
        Names that should never be added to the required list (case-insensitive).

    Returns
    -------
    dict with keys:
        required_list : sorted list of distinct required package names
        source : original env file name
        raw_dependency_strings : raw dependency entries (including pip section)
        optional_packages : sorted list of optional package names
    """
    import yaml  # local import to keep top-level light
    import re

    optional_set: Set[str] = set(optional_packages or [])
    exclude_set: Set[str] = {p.lower() for p in (exclude_packages or [])}

    raw_dep_strings: list[str] = []
    required: set[str] = set()

    def clean_name(dep: str) -> str:
        d = dep.strip()
        if "#" in d:
            d = d.split("#", 1)[0].strip()
        if "[" in d:  # strip bracketed extras or markers (e.g. pkg[version
            d = d.split("[", 1)[0]
        if " @ " in d:  # remove URL / direct refs
            d = d.split(" @ ", 1)[0]
        # Split at first version/comparison token
        d = re.split(r"[ =<>!~]", d, 1)[0]
        return d.strip()

    from os.path import exists

    if exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            deps = data.get("dependencies", [])
            for dep in deps:
                if isinstance(dep, str):
                    raw_dep_strings.append(dep)
                    base = clean_name(dep)
                    if base and base.lower() not in exclude_set:
                        required.add(base)
                elif isinstance(dep, dict) and "pip" in dep:
                    for p in dep["pip"]:
                        raw_dep_strings.append(p)
                        base = clean_name(p)
                        if base and base.lower() not in exclude_set:
                            required.add(base)
        except Exception as e:  # pragma: no cover - defensive
            return {
                "required_list": [],
                "source": env_file,
                "raw_dependency_strings": raw_dep_strings,
                "optional_packages": sorted(optional_set),
                "parse_error": str(e),
            }
    else:
        return {
            "required_list": [],
            "source": env_file,
            "raw_dependency_strings": raw_dep_strings,
            "optional_packages": sorted(optional_set),
            "note": f"Environment file {env_file} not found",
        }

    # Case-insensitive uniqueness while preserving first occurrence casing
    normalized: dict[str, str] = {}
    for pkg in required:
        key = pkg.lower()
        if key not in normalized:
            normalized[key] = pkg

    final_list = sorted(normalized.values())
    return {
        "required_list": final_list,
        "source": env_file,
        "raw_dependency_strings": raw_dep_strings,
        "optional_packages": sorted(optional_set),
    }


def _resolve_version(pkg: str, import_name: str, module) -> str:
    """Try to determine a version string for an imported module."""
    ver = getattr(module, "__version__", None)
    if ver:
        return ver
    # Special handling for GDAL (imported via osgeo)
    if pkg.lower() == "gdal":  # pragma: no cover - environment dependent
        try:
            from osgeo import gdal as _gdal  # type: ignore

            for attr in ["__version__"]:
                if hasattr(_gdal, attr):
                    v = getattr(_gdal, attr)
                    if v:
                        return v
            try:
                vinfo = _gdal.VersionInfo()
                if vinfo:
                    return vinfo
            except Exception:
                pass
        except Exception:
            pass
    return "unknown"


def run_import_checks(
    required_list: Sequence[str],
    optional_packages: Set[str] | None = None,
) -> Dict[str, Any]:
    """Attempt to import each package and classify missing vs optional.

    Parameters
    ----------
    required_list : Sequence[str]
        Packages to attempt importing.
    optional_packages : set[str] | None
        Package names considered optional.

    Returns
    -------
    dict with keys: status, missing_essential, missing_optional
    """
    import importlib

    optional_set = set(optional_packages or [])
    package_status: dict[str, dict[str, Any]] = {}
    missing_essential: list[str] = []
    missing_optional: list[str] = []

    for pkg in required_list:
        tried: list[str] = []
        success = False
        version = "unknown"
        used_name = None

        # Build candidate import names
        candidates: list[str] = []
        base_candidate = pkg.replace("-", "_")
        candidates.append(base_candidate)
        mapped = SPECIAL_IMPORT_NAMES.get(pkg.lower())
        if mapped and mapped not in candidates:
            candidates.append(mapped)
        if pkg not in candidates:
            candidates.append(pkg)

        for cand in candidates:
            try:
                mod = importlib.import_module(cand)
                used_name = cand
                version = _resolve_version(pkg, cand, mod)
                success = True
                break
            except Exception as e:  # pragma: no cover - import error paths
                tried.append(f"{cand}: {e.__class__.__name__}")

        if success:
            package_status[pkg] = {
                "ok": True,
                "version": version,
                "import_name": used_name,
            }
        else:
            is_optional = pkg in optional_set
            package_status[pkg] = {
                "ok": False,
                "error": tried[-1] if tried else "unknown import error",
                "attempts": tried,
                "optional": is_optional,
            }
            if is_optional:
                missing_optional.append(pkg)
            else:
                missing_essential.append(pkg)

    return {
        "status": package_status,
        "missing_essential": missing_essential,
        "missing_optional": missing_optional,
    }


def geospatial_smoke_test() -> Dict[str, Any]:
    """Run quick geospatial capability checks (GeoPandas, Shapely, etc.)."""
    checks: Dict[str, Any] = {}
    try:
        import geopandas as gpd  # type: ignore
        from shapely.geometry import box  # type: ignore
        from shapely.ops import unary_union  # type: ignore
        from pyproj import Geod  # type: ignore

        poly1 = box(8.54, 47.36, 8.56, 47.38)
        poly2 = box(8.55, 47.37, 8.57, 47.39)
        gdf = gpd.GeoDataFrame({"id": [1, 2], "geometry": [poly1, poly2]}, crs="EPSG:4326")
        union_geom = unary_union(gdf.geometry)
        gdf_planar = gdf.to_crs(3857)
        union_planar = gpd.GeoSeries([union_geom], crs="EPSG:4326").to_crs(3857).iloc[0]

        geod = Geod(ellps="WGS84")

        def geodesic_area(poly):  # pragma: no cover - numeric path
            lon, lat = poly.exterior.coords.xy
            area, _ = geod.polygon_area_perimeter(lon, lat)
            return abs(area)

        geodesic_union_area = geodesic_area(union_geom)
        planar_sum_area = float(gdf_planar.area.sum())
        planar_union_area = float(union_planar.area)
        overlap_factor = (
            planar_union_area / planar_sum_area if planar_sum_area else None
        )
        planar_vs_geodesic_ratio = (
            planar_union_area / geodesic_union_area if geodesic_union_area else None
        )

        checks.update(
            {
                "geopandas": True,
                "polygons_count": len(gdf),
                "union_valid": union_geom.is_valid,
                "planar_sum_area_m2": planar_sum_area,
                "planar_union_area_m2": planar_union_area,
                "overlap_factor": overlap_factor,
                "geodesic_union_area_m2": geodesic_union_area,
                "planar_vs_geodesic_ratio": planar_vs_geodesic_ratio,
            }
        )
    except Exception as e:  # pragma: no cover - environment dependent
        checks["error"] = str(e)

    for extra in ["fiona", "rasterio", "contextily"]:
        if "error" in checks:
            break
        try:
            __import__(extra)
            checks[extra] = True
        except Exception as e:  # pragma: no cover
            checks[extra] = f"ERROR: {e}"

    return checks


def viz_smoke_test() -> Dict[str, Any]:
    """Test folium, plotly, and matplotlib basic functionality."""
    status: Dict[str, Any] = {}
    import logging
    import warnings

    warnings.filterwarnings("ignore", category=DeprecationWarning, module="traitlets")
    for noisy in ["traitlets", "comm", "matplotlib"]:
        try:
            logging.getLogger(noisy).setLevel(logging.ERROR)
        except Exception:  # pragma: no cover
            pass

    try:
        import folium  # type: ignore

        fmap = folium.Map(location=[47.37, 8.55], zoom_start=10, control_scale=True)
        folium.Marker([47.37, 8.55], tooltip="Zurich").add_to(fmap)
        status["folium"] = "ok (map object created)"
        status["_folium_map_object"] = fmap  # retained so notebook may display
    except Exception as e:  # pragma: no cover
        status["folium"] = f"ERROR: {e}"

    try:
        import plotly.graph_objects as go  # type: ignore

        fig = go.Figure(data=[go.Scatter(x=[0, 1], y=[0, 1])])
        fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, b=10, t=30))
        status["plotly"] = "ok (scatter figure created)"
    except Exception as e:  # pragma: no cover
        status["plotly"] = f"ERROR: {e}"

    try:
        import matplotlib  # type: ignore

        backend_before = matplotlib.get_backend()
        if backend_before.lower() not in ["agg", "module://matplotlib_inline.backend_inline"]:
            try:
                matplotlib.use("Agg")
            except Exception:  # pragma: no cover
                pass
        import matplotlib.pyplot as plt  # type: ignore

        plt.figure(); plt.plot([0, 1], [0, 1]); plt.close()
        status["matplotlib"] = "ok (simple plot created)"
        status["matplotlib_backend_used"] = matplotlib.get_backend()
    except Exception as e:  # pragma: no cover
        status["matplotlib"] = f"ERROR: {e}"

    status["warnings_suppressed"] = ["traitlets DeprecationWarning", "comm warnings"]
    return status


def modflow_minimal_model(
    auto_download: bool = True,
    persistent_workspace: Path | None = None,
    cleanup_on_success: bool = False,
) -> Dict[str, Any]:
    """Run a minimal 1D steady-state MODFLOW-2005 test model via FloPy.

    Parameters
    ----------
    auto_download : bool
        Attempt automatic retrieval (requires `pymake` get-modflow) if not found.
    persistent_workspace : Path | None
        Directory to use for model files; created if missing.
    cleanup_on_success : bool
        If True, remove model-specific files after a successful run.
    """
    import subprocess
    import sys
    import glob
    import os
    import shutil

    diag: Dict[str, Any] = {}
    try:
        import flopy  # type: ignore
    except Exception as e:  # pragma: no cover
        diag["error"] = f"FloPy not installed: {e}"
        diag["advice"] = "Install flopy (e.g., pip install flopy)"
        return diag

    exe_candidates = ["mf2005", "mf2005.exe", "mf2005dbl", "mfnwt"]

    def find_exe():
        for cand in exe_candidates:
            path = flopy.which(cand)
            if path:
                return path
        extra_dirs = [
            Path(sys.executable).parent,
            Path.home() / ".local" / "bin",
            Path.cwd(),
        ]
        for d in extra_dirs:
            if not d.exists():
                continue
            for cand in exe_candidates:
                p = d / cand
                if p.exists() and p.is_file():
                    return str(p.resolve())
        return None

    found_exe = find_exe()
    diag["executable_found"] = bool(found_exe)
    diag["executable_path"] = found_exe

    if not found_exe and auto_download:
        diag["attempted_download"] = True
        cmd = ["get-modflow", ":flopy"]
        diag["download_command"] = " ".join(cmd)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, check=False, timeout=300
            )
            diag["download_returncode"] = proc.returncode
            if proc.stdout:
                diag["download_stdout_tail"] = proc.stdout[-2000:]
            if proc.stderr:
                diag["download_stderr_tail"] = proc.stderr[-2000:]
            if proc.returncode == 0:
                found_exe = find_exe()
                diag["executable_found_after_attempt"] = bool(found_exe)
                diag["executable_path"] = found_exe
        except FileNotFoundError:  # pragma: no cover
            diag["download_error"] = (
                "get-modflow command not found in PATH (install pymake)\n"
                "Try: pip install pymake   (or mamba/conda install -c conda-forge pymake)"
            )
        except subprocess.TimeoutExpired:  # pragma: no cover
            diag["download_error"] = "get-modflow timed out after 300s"
        except Exception as e_dl:  # pragma: no cover
            diag["download_error"] = f"unexpected download error: {e_dl}"

    if not found_exe:
        diag.setdefault(
            "advice",
            "Install pymake (pip install pymake) then run get-modflow :flopy",
        )
        diag.setdefault(
            "note", "MODFLOW executable unavailable; model run skipped"
        )
        diag["run_success"] = False
        return diag

    # Workspace handling
    ws = persistent_workspace or Path.cwd() / "_modflow_diag"  # fallback path
    ws.mkdir(parents=True, exist_ok=True)
    diag["workspace_path"] = str(ws)

    # Clean previous diagtest.* files only
    try:
        for item in ws.iterdir():
            if item.name.startswith("diagtest"):
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    try:
                        item.unlink()
                    except Exception:  # pragma: no cover
                        pass
    except Exception as e_cleanup:  # pragma: no cover
        diag["pre_run_workspace_cleanup_warning"] = str(e_cleanup)

    # Build model
    m = flopy.modflow.Modflow("diagtest", model_ws=str(ws), exe_name=found_exe)
    nlay, nrow, ncol = 1, 1, 10
    Lx = 100.0
    delr = Lx / ncol
    delc = 1.0
    top = 10.0
    botm = 0.0
    flopy.modflow.ModflowDis(m, nlay, nrow, ncol, delr=delr, delc=delc, top=top, botm=botm)
    ibound = [[[1] * ncol]]
    ibound[0][0][0] = -1
    ibound[0][0][-1] = -1
    strt = [[[top * (1 - (j / (ncol - 1))) for j in range(ncol)]]]
    flopy.modflow.ModflowBas(m, ibound=ibound, strt=strt)
    flopy.modflow.ModflowLpf(m, hk=10.0, vka=10.0, ipakcb=53)
    flopy.modflow.ModflowPcg(m)
    flopy.modflow.ModflowOc(m)

    m.write_input()
    namefile = ws / "diagtest.nam"
    diag["namefile_exists_after_write"] = namefile.exists()
    if not namefile.exists():  # pragma: no cover
        diag["pre_run_namefile_missing"] = True
        diag["run_success"] = False
        return diag

    model_files = sorted(
        [Path(p).name for p in glob.glob(str(ws / "diagtest*"))]
    )
    diag["model_files_written"] = model_files

    success, _buff = m.run_model(silent=True)
    diag["run_success"] = success
    if success:
        from flopy.utils import HeadFile  # type: ignore

        hf = HeadFile(str(ws / "diagtest.hds"))
        h = hf.get_data(kstpkper=(0, 0))[0, 0, :]
        diag["final_heads"] = h.tolist()
        analytical = [10.0 * (1 - j / (ncol - 1)) for j in range(ncol)]
        diag["analytical_heads"] = analytical
        max_abs_err = float(max(abs(hi - ha) for hi, ha in zip(h, analytical)))
        diag["max_abs_error_linear_solution"] = max_abs_err
        diag["analytical_ok"] = max_abs_err < 1e-5
        if cleanup_on_success:
            try:
                for f in model_files:
                    try:
                        (ws / f).unlink()
                    except Exception:  # pragma: no cover
                        pass
                diag["workspace_cleaned"] = True
            except Exception as e_rm:  # pragma: no cover
                diag["workspace_cleanup_error"] = str(e_rm)
    else:
        diag["workspace_retained"] = str(ws)
    return diag


def plotly_3d_test() -> Dict[str, Any]:
    """Create a trivial Plotly 3D surface figure to validate 3D capability."""
    result: Dict[str, Any] = {}
    try:
        import numpy as np  # type: ignore
        import plotly.graph_objects as go  # type: ignore

        X, Y = np.mgrid[-2:2:30j, -2:2:30j]
        Z = np.exp(-(X**2 + Y**2))
        go.Figure(data=[go.Surface(z=Z, x=X, y=Y, colorscale="Viridis")])
        result["success"] = True
    except Exception as e:  # pragma: no cover
        result["success"] = False
        result["error"] = str(e)
    return result


def system_snapshot() -> Dict[str, Any]:
    """Capture basic system memory statistics using psutil if available."""
    snap: Dict[str, Any] = {}
    try:
        import psutil  # type: ignore

        vm = psutil.virtual_memory()
        snap["memory_total_GB"] = round(vm.total / 1024**3, 2)
        snap["memory_available_GB"] = round(vm.available / 1024**3, 2)
        proc = psutil.Process()
        snap["process_memory_MB"] = round(proc.memory_info().rss / 1024**2, 1)
    except Exception as e:  # pragma: no cover
        snap["error"] = str(e)
    return snap


def build_summary(diag_results: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate overall readiness summary from the diag_results structure."""
    packages = diag_results.get("packages", {})
    modflow = diag_results.get("modflow", {})
    geospatial = diag_results.get("geospatial", {})
    viz = diag_results.get("viz", {})

    missing_essential = packages.get("missing_essential", [])
    summary: Dict[str, Any] = {
        "missing_essential": missing_essential,
        "missing_optional": packages.get("missing_optional", []),
        "modflow_executable_found": modflow.get("executable_found"),
        "modflow_run_success": modflow.get("run_success"),
        "modflow_linear_solution_ok": modflow.get("analytical_ok"),
        "geospatial_errors": [
            k
            for k, v in geospatial.items()
            if isinstance(v, str) and v.startswith("ERROR")
        ],
        "plotly_3d_success": viz.get("plotly_3d", {}).get("success"),
    }

    summary["overall_ready"] = (
        (not summary["missing_essential"])  # no essential gaps
        and summary["modflow_executable_found"]
        and summary["modflow_run_success"]
        and summary["geospatial_errors"] == []
    )
    return summary


__all__ = [
    "parse_environment",
    "run_import_checks",
    "geospatial_smoke_test",
    "viz_smoke_test",
    "modflow_minimal_model",
    "plotly_3d_test",
    "system_snapshot",
    "build_summary",
    "SPECIAL_IMPORT_NAMES",
]
