"""
Build a PEST++ calibration interface for the Limmat Valley MODFLOW model.

This script creates a ready-to-run pestpp-glm setup using pyEMU's PstFrom.
It is called from the calibration notebook (Notebook 5) and produces a
``pest_setup/`` directory containing the PEST control file and all
supporting template/instruction files.

Key components
--------------
* **Pilot points** (~20) distributed across the active model domain,
  log-transformed K with course calibration bounds (10-600 m/d in NB5/NB6).
* **Observations** — 4 AWEL mean-head measurements plus synthetic observations.
* **Prior information** — K at the pilot point nearest the pumping-test
  location, weighted by the PT-derived uncertainty.
* **Regularisation** — preferred-value (Tikhonov) regularisation on every
  pilot point, pulling K toward the initial estimate where data is sparse.

Usage from the notebook::

    from scripts.setup_pest_calibration import build_pest_setup
    pst = build_pest_setup(
        model_ws="path/to/model",
        obs_df=obs_wells_df,          # DataFrame with observed heads
        pt_K=12.0, pt_location=(x, y),
        pest_ws="path/to/pest_setup",
    )
"""

import os
import json
import shutil
import subprocess
import sys
import warnings
import zipfile

import numpy as np
import pandas as pd


CALIBRATION_BUNDLE_MIN_VERSION = 3

COURSE_PEST_SETTINGS = {
    "n_pilot_points": 20,
    "k_initial": 200.0,
    "k_lower": 10.0,
    "k_upper": 600.0,
    "pt_weight": 1.5,
    "reg_weight": 0.5,
    "variogram_range": 600.0,
    "anisotropy_angle": -30.0,
    "anisotropy_scaling": 3.0,
}

CALIBRATION_BUNDLE_ESSENTIAL_FILES = (
    "calibration.pst",
    "calibration.par",
    "calibration.jcb",
    "calibration.par.usum.csv",
    "calibration.post.cov",
    "pilot_points.csv",
    "hk_pps.dat",
    "pp_xy.npy",
    "sihl_mult.dat",
    "sihl_cell_ids.npy",
    "heads_out.ins",
    "heads_sim.dat",
    "forward_run.py",
    "run_model.sh",
    "hk_pps.tpl",
    "sihl_mult.tpl",
    "calibration.rec",
    "calibration.iobj",
    "calibration.rei",
)


def ensure_pestpp_installed() -> bool:
    """Ensure pestpp-glm is available on PATH, installing via pyEMU if needed."""
    if shutil.which("pestpp-glm") is not None:
        print(f"pestpp-glm found: {shutil.which('pestpp-glm')}")
        return True

    print("pestpp-glm not found on PATH. Installing via get-pestpp...")
    venv_bin = os.path.dirname(sys.executable)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pyemu.utils.get_pestpp",
            "--subset",
            "pestpp-glm",
            venv_bin,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["get-pestpp", "--subset", "pestpp-glm", venv_bin],
            capture_output=True,
            text=True,
        )
    print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    if shutil.which("pestpp-glm"):
        print("pestpp-glm installed successfully.")
        return True
    print("Warning: pestpp-glm could not be installed automatically.")
    print("Install manually: get-pestpp /path/to/bin")
    return False


def _read_calibration_manifest(pest_ws):
    manifest_path = os.path.join(pest_ws, "MANIFEST.json")
    if not os.path.exists(manifest_path):
        return None
    with open(manifest_path) as f:
        return json.load(f)


def _download_calibration_bundle(data_dir):
    from data_utils import download_named_file

    calibration_dir = os.path.join(data_dir, "calibration")
    os.makedirs(calibration_dir, exist_ok=True)
    print("Downloading pre-computed calibration (~0.5 MB)…")
    zip_path = download_named_file(
        name="calibrated_model",
        dest_folder=calibration_dir,
        data_type=None,
    )
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(calibration_dir)


def _validate_calibration_bundle(pest_ws):
    for name in CALIBRATION_BUNDLE_ESSENTIAL_FILES:
        if not os.path.exists(os.path.join(pest_ws, name)):
            raise FileNotFoundError(
                f"Bundle is missing essential file '{name}'; the zip may be corrupted."
            )


def ensure_calibration_workspace(data_dir: str) -> str:
    """Ensure the downloaded calibration pest_setup workspace is present."""
    pest_ws = os.path.join(data_dir, "calibration", "pest_setup")
    pst_path = os.path.join(pest_ws, "calibration.pst")
    did_download = False

    if not os.path.exists(pst_path):
        _download_calibration_bundle(data_dir)
        did_download = True
    else:
        manifest = _read_calibration_manifest(pest_ws)
        if manifest is not None:
            bundle_version = int(manifest.get("bundle_version", 0))
            if bundle_version < CALIBRATION_BUNDLE_MIN_VERSION:
                print(
                    "Local calibration is schema-stale "
                    f"(bundle_version={bundle_version} < min={CALIBRATION_BUNDLE_MIN_VERSION}); refreshing."
                )
                stale_ws = os.path.join(data_dir, "calibration", "pest_setup.stale")
                if os.path.exists(stale_ws):
                    shutil.rmtree(stale_ws)
                shutil.move(pest_ws, stale_ws)
                _download_calibration_bundle(data_dir)
                did_download = True

    _validate_calibration_bundle(pest_ws)
    manifest = _read_calibration_manifest(pest_ws)
    if manifest is None:
        raise FileNotFoundError(
            "`MANIFEST.json` missing from bundle. The bundle was likely produced "
            "before v3 or by an out-of-date `package_calibration.py`. Re-run "
            "packaging from a clean NB5 workspace, or contact the instructor."
        )

    bundle_version = int(manifest.get("bundle_version", 0))
    if bundle_version >= CALIBRATION_BUNDLE_MIN_VERSION:
        print(f"Calibration found (bundle_version={bundle_version}).")
        return pest_ws

    # bundle_version < min. Fail hard rather than silently calibrate against a
    # stale interface: after the 1,080->2,160 m³/d recalibration a below-min
    # bundle carries the OLD flow field / obs weighting, so its outputs would be
    # inconsistent with 04f. A warning here would be ignored; enforcement is the
    # only mechanism that guarantees students get the current model.
    if did_download:
        raise RuntimeError(
            f"Downloaded calibration bundle is stale: bundle_version="
            f"{bundle_version} < required {CALIBRATION_BUNDLE_MIN_VERSION}. The "
            "Dropbox bundle has not yet been refreshed after a schema bump — "
            "contact the instructor; do not proceed with the older bundle."
        )
    raise RuntimeError(
        f"Local calibration bundle is stale: bundle_version={bundle_version} < "
        f"required {CALIBRATION_BUNDLE_MIN_VERSION}, and a fresh copy could not be "
        f"obtained. Delete '{pest_ws}' and re-run to force a re-download, or "
        "contact the instructor."
    )


def ensure_notebook4_model_exists(data_dir: str) -> str:
    """Ensure Notebook 4's MODFLOW 6 workspace exists and loads."""
    nb4_workspace = os.path.join(data_dir, "notebook4_model")
    try:
        import flopy

        sim = flopy.mf6.MFSimulation.load(
            sim_ws=nb4_workspace,
            load_only=["disv"],
            verbosity_level=0,
        )
        for model in sim.model_names:
            modelgrid = sim.get_model(model).modelgrid
            if getattr(modelgrid, "ncpl", None) is None:
                raise ValueError("DISV grid did not load ncpl")
            _ = modelgrid.verts
    except Exception as exc:
        raise FileNotFoundError(
            f"Notebook 4 output not found or incomplete at `{nb4_workspace}`. "
            "Please run [04f_model_implementation.ipynb] first to build the "
            "MODFLOW 6 model — it is a hard prerequisite. "
            f"(Underlying error: `{exc}`)"
        ) from exc

    # Freshness guard: notebook4_model is the STUDENT's 04f output, not a shipped
    # download, so the manifest-version enforcement used for the calibration
    # workspace does not apply here. After the 1,080->2,160 m³/d recalibration a
    # workspace left over from an OLD 04f run would silently feed the wrong
    # pumping into 05f-08f. We cannot rebuild it (it is their notebook output),
    # but we can flag the mismatch loudly and point them back to 04f.
    _warn_if_stale_pumping(nb4_workspace)
    return nb4_workspace


# Total municipal pumping [m³/d] the current course 04f produces (1,500 L/min,
# 50% utilisation). A notebook4_model whose WEL sum is far from this was built by
# an out-of-date 04f and must be rebuilt before it feeds 05f-08f.
EXPECTED_NB4_PUMPING_M3D = 2160.0


def _warn_if_stale_pumping(nb4_workspace: str) -> None:
    try:
        sys.path.insert(
            0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        )
        import model_io_utils as _mio

        pumping = abs(_mio.flow_model_pumping_m3d(nb4_workspace))
    except Exception:
        return  # no WEL / unreadable -> nothing to compare against
    if pumping <= 1.0:
        return
    if abs(pumping - EXPECTED_NB4_PUMPING_M3D) / EXPECTED_NB4_PUMPING_M3D > 0.05:
        warnings.warn(
            f"`notebook4_model` total pumping is {pumping:.0f} m³/d, but the current "
            f"course model expects ~{EXPECTED_NB4_PUMPING_M3D:.0f} m³/d (1,500 L/min, "
            "50% utilisation). This workspace was most likely built by an older "
            "04f_model_implementation.ipynb — re-run 04f to rebuild it before "
            "continuing, or downstream heads and particle paths will not match the "
            "calibrated model.",
            UserWarning,
        )


def _write_k_tpl(tpl_path, n_pilot_points, k_array_file="hk_layer1.dat"):
    """
    Write a simple template file that maps pilot-point parameters to a
    K array file.  Each pilot-point parameter is named ``hk_pp_NN``.
    """
    lines = ["ptf ~\n"]
    for i in range(n_pilot_points):
        lines.append(f"~  hk_pp_{i:02d}  ~\n")
    with open(tpl_path, "w") as f:
        f.writelines(lines)


def _write_k_array(path, values):
    """Write a simple whitespace-delimited array file."""
    np.savetxt(path, values.reshape(1, -1), fmt="%.6e")


def _distribute_pilot_points(modelgrid, n_target=25, seed=123, idomain=None):
    """
    Place pilot points quasi-regularly across the active domain.

    Parameters
    ----------
    modelgrid : flopy grid
    n_target : int
    seed : int
    idomain : np.ndarray, optional
        Active-cell mask (1=active).  If provided, only active cells are
        used as candidates.

    Returns an (N, 2) array of (x, y) coordinates.
    """
    rng = np.random.default_rng(seed)

    # Get cell centres of active cells
    if hasattr(modelgrid, "nrow"):
        # Structured grid
        xc = modelgrid.xcellcenters.ravel()
        yc = modelgrid.ycellcenters.ravel()
    else:
        # DISV / unstructured
        xc = modelgrid.xcellcenters
        yc = modelgrid.ycellcenters

    # Determine active mask
    if idomain is not None:
        active = idomain.ravel() > 0
    elif hasattr(modelgrid, "_idomain") and modelgrid._idomain is not None:
        active = modelgrid._idomain.ravel() > 0
    else:
        active = np.ones(len(xc), dtype=bool)

    xc_act = xc[active]
    yc_act = yc[active]

    # Sub-sample using farthest-point strategy for even coverage
    n = min(n_target, len(xc_act))
    indices = [rng.integers(0, len(xc_act))]
    dists = np.full(len(xc_act), np.inf)
    for _ in range(n - 1):
        last = indices[-1]
        d = (xc_act - xc_act[last]) ** 2 + (yc_act - yc_act[last]) ** 2
        dists = np.minimum(dists, d)
        indices.append(int(np.argmax(dists)))

    pp_x = xc_act[indices]
    pp_y = yc_act[indices]
    return np.column_stack([pp_x, pp_y])


def _nearest_pilot_point(pp_xy, target_xy):
    """Return index of the nearest pilot point to *target_xy*."""
    dx = pp_xy[:, 0] - target_xy[0]
    dy = pp_xy[:, 1] - target_xy[1]
    return int(np.argmin(dx ** 2 + dy ** 2))


def _interpolate_pp_to_grid(pp_xy, pp_values, modelgrid, method="ordinary_kriging",
                            variogram_range=1500.0,
                            anisotropy_angle=0.0, anisotropy_scaling=1.0):
    """
    Interpolate pilot-point values to every active grid cell using
    simple inverse-distance weighting (IDW) or kriging when pykrige
    is available.

    Parameters
    ----------
    pp_xy : (N, 2) array
    pp_values : (N,) array   — values in *log10* space
    modelgrid : flopy grid
    method : str
        'idw' or 'ordinary_kriging'
    variogram_range : float
        Range parameter for the exponential variogram [m].
    anisotropy_angle : float
        Angle of the major axis of anisotropy, measured CCW from east [degrees].
        For the Limmat Valley (~30°), this aligns the long correlation axis
        along the valley.
    anisotropy_scaling : float
        Ratio of major to minor variogram range (e.g. 3.0 means the range
        along the minor axis is 1/3 of the major axis).

    Returns
    -------
    field : 1-D array (ncells) or 2-D array (nrow, ncol) — K in *real* space
    """
    if hasattr(modelgrid, "nrow"):
        xc = modelgrid.xcellcenters.ravel()
        yc = modelgrid.ycellcenters.ravel()
        shape = (modelgrid.nrow, modelgrid.ncol)
    else:
        xc = modelgrid.xcellcenters
        yc = modelgrid.ycellcenters
        shape = None

    if method == "ordinary_kriging":
        try:
            from pykrige.ok import OrdinaryKriging

            ok = OrdinaryKriging(
                pp_xy[:, 0], pp_xy[:, 1], pp_values,
                variogram_model="exponential",
                variogram_parameters={"sill": 0.5, "range": variogram_range, "nugget": 0.01},
                anisotropy_angle=anisotropy_angle,
                anisotropy_scaling=anisotropy_scaling,
                verbose=False, enable_plotting=False,
            )
            z, _ = ok.execute("points", xc, yc)
            field = 10.0 ** z  # back-transform from log10
            return field.reshape(shape) if shape else field
        except ImportError:
            pass

    # Fallback: IDW (power=2) with anisotropic distance
    theta = np.radians(anisotropy_angle)
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    field = np.zeros(len(xc))
    for i in range(len(xc)):
        dx = xc[i] - pp_xy[:, 0]
        dy = yc[i] - pp_xy[:, 1]
        # Rotate into anisotropy frame, stretch minor axis
        dx_rot = dx * cos_t + dy * sin_t
        dy_rot = (-dx * sin_t + dy * cos_t) * anisotropy_scaling
        d2 = dx_rot ** 2 + dy_rot ** 2
        d2[d2 == 0] = 1e-10
        w = 1.0 / d2
        field[i] = np.sum(w * pp_values) / np.sum(w)
    field = 10.0 ** field
    return field.reshape(shape) if shape else field


def build_pest_setup(
    model_ws,
    modelgrid,
    obs_df,
    pt_K,
    pt_location,
    pest_ws=None,
    n_pilot_points=25,
    k_initial=200.0,
    k_lower=10.0,
    k_upper=600.0,
    pt_weight=1.0,
    reg_weight=0.5,
    obs_head_col="head_m",
    obs_x_col="x",
    obs_y_col="y",
    obs_id_col="obs_id",
    variogram_range=3000.0,
    idomain=None,
    sihl_cell_ids=None,
    anisotropy_angle=0.0,
    anisotropy_scaling=1.0,
):
    """
    Build a PEST++ (pestpp-glm) calibration directory.

    This creates a simplified but functional PEST setup that students can
    run from the notebook.  It writes:

    * A PEST control file (``calibration.pst``)
    * Template file for the K parameter array
    * Instruction file for reading simulated heads
    * A forward-run Python script that:
        1. Reads pilot-point K values from the parameter file
        2. Interpolates to the full grid (kriging / IDW)
        3. Writes the K array for MODFLOW
        4. Runs MODFLOW
        5. Extracts simulated heads and writes the observation output

    Parameters
    ----------
    model_ws : str
        Path to the working MODFLOW model directory.
    modelgrid : flopy grid
        Model grid object (with cell centres and CRS).
    obs_df : pd.DataFrame
        Observation wells with columns for ID, x, y, observed head, cell.
    pt_K : float
        Pumping-test derived K [m/d] — used as prior information.
    pt_location : tuple (x, y)
        Coordinates of the pumping-test site.
    pest_ws : str, optional
        Output directory for PEST files.  Defaults to ``<model_ws>/pest_setup``.
    n_pilot_points : int
        Number of pilot points.
    k_initial : float
        Initial K value at all pilot points [m/d].
    k_lower, k_upper : float
        Parameter bounds [m/d].
    pt_weight : float
        Weight for the pumping-test prior-information equation.
    reg_weight : float
        Weight for preferred-value regularisation on every pilot point.
        Controls how strongly each PP is pulled toward ``k_initial``.
    obs_head_col, obs_x_col, obs_y_col, obs_id_col : str
        Column names in obs_df.
    variogram_range : float
        Kriging variogram range [m].
    idomain : np.ndarray, optional
        Active-cell indicator (1=active).  Passed to pilot-point distribution
        so that points are only placed in active cells.

    Returns
    -------
    pest_ws : str
        Path to the pest setup directory.
    pp_xy : ndarray
        Pilot point locations (N, 2).
    """
    if pest_ws is None:
        pest_ws = os.path.join(model_ws, "pest_setup")
    os.makedirs(pest_ws, exist_ok=True)

    # --- 1. Pilot points ------------------------------------------------
    pp_xy = _distribute_pilot_points(modelgrid, n_target=n_pilot_points, idomain=idomain)
    n_pp = len(pp_xy)

    # Save pilot point locations for later visualisation
    pp_df = pd.DataFrame(pp_xy, columns=["x", "y"])
    pp_df.index.name = "pp_id"
    pp_df["par_name"] = [f"hk_pp_{i:02d}" for i in range(n_pp)]
    pp_df.to_csv(os.path.join(pest_ws, "pilot_points.csv"))

    # Nearest PP to pumping test site (for prior information)
    pp_pt_idx = _nearest_pilot_point(pp_xy, pt_location)

    # --- 1b. Sihl leakance multiplier (optional) -------------------------
    if sihl_cell_ids is not None:
        np.save(os.path.join(pest_ws, "sihl_cell_ids.npy"), sihl_cell_ids)
        # Template file for the Sihl multiplier
        with open(os.path.join(pest_ws, "sihl_mult.tpl"), "w") as f:
            f.write("ptf ~\n")
            f.write("~ sihl_leakance_mult ~\n")
        # Initial data file (log10(1.0) = 0.0, i.e. no change)
        np.savetxt(os.path.join(pest_ws, "sihl_mult.dat"),
                   np.array([0.0]), fmt="%.6e")

    # --- 2. Write template file -----------------------------------------
    tpl_path = os.path.join(pest_ws, "hk_pps.tpl")
    _write_k_tpl(tpl_path, n_pp)

    # --- 3. Observation info --------------------------------------------
    obs_records = []
    for _, row in obs_df.iterrows():
        obs_records.append({
            "obs_name": str(row[obs_id_col]).lower().replace("-", "_"),
            "obs_value": row[obs_head_col],
            "weight": 1.0,
            "obs_group": "heads",
        })
    obs_info = pd.DataFrame(obs_records)

    # --- 4. Write instruction file for model output ---------------------
    ins_path = os.path.join(pest_ws, "heads_out.ins")
    with open(ins_path, "w") as f:
        f.write("pif @\n")
        for rec in obs_records:
            f.write(f"l1 !{rec['obs_name']}!\n")

    # --- 5. Write the PEST control file ---------------------------------
    pst_path = os.path.join(pest_ws, "calibration.pst")
    _write_pst_file(
        pst_path,
        n_pp=n_pp,
        k_initial=k_initial,
        k_lower=k_lower,
        k_upper=k_upper,
        obs_info=obs_info,
        pp_pt_idx=pp_pt_idx,
        pt_K=pt_K,
        pt_weight=pt_weight,
        reg_weight=reg_weight,
        tpl_name="hk_pps.tpl",
        ins_name="heads_out.ins",
        par_file="hk_pps.dat",
        obs_file="heads_sim.dat",
        python_exe=sys.executable,
        sihl_cell_ids=sihl_cell_ids,
    )

    # --- 6. Write forward-run script ------------------------------------
    _write_forward_run_script(
        pest_ws, model_ws, modelgrid, obs_df, pp_xy,
        variogram_range=variogram_range,
        obs_x_col=obs_x_col, obs_y_col=obs_y_col,
        obs_id_col=obs_id_col, obs_head_col=obs_head_col,
        sihl_cell_ids=sihl_cell_ids,
        anisotropy_angle=anisotropy_angle,
        anisotropy_scaling=anisotropy_scaling,
    )

    # Write a shell wrapper so PEST++ doesn't mangle the Python path
    wrapper_path = os.path.join(pest_ws, "run_model.sh")
    with open(wrapper_path, "w") as f:
        f.write(f"#!/bin/bash\n{sys.executable} forward_run.py\n")
    os.chmod(wrapper_path, 0o755)

    # --- 7. Write initial parameter file --------------------------------
    par_path = os.path.join(pest_ws, "hk_pps.dat")
    init_vals = np.full(n_pp, np.log10(k_initial))
    np.savetxt(par_path, init_vals, fmt="%.6e")

    n_par_total = n_pp + (1 if sihl_cell_ids is not None else 0)
    print(f"PEST++ setup written to: {pest_ws}")
    print(f"  Parameters         : {n_par_total} ({n_pp} K pilot points"
          + (f" + 1 Sihl leakance mult)" if sihl_cell_ids is not None else ")"))
    print(f"  Observations       : {len(obs_records)}")
    print(f"  Prior info (PT)    : hk_pp_{pp_pt_idx:02d} ≈ log10({pt_K:.1f}) = {np.log10(pt_K):.4f}")
    print(f"  K bounds           : [{k_lower}, {k_upper}] m/d")
    print(f"  Regularisation     : preferred-value weight = {reg_weight}")
    print(f"  Variogram range    : {variogram_range} m")
    if anisotropy_scaling != 1.0:
        print(f"  Anisotropy         : angle={anisotropy_angle}°, scaling={anisotropy_scaling}")
    if sihl_cell_ids is not None:
        print(f"  Sihl RIV cells     : {len(sihl_cell_ids)} (leakance multiplier enabled)")

    return pest_ws, pp_xy


def _write_pst_file(path, n_pp, k_initial, k_lower, k_upper,
                    obs_info, pp_pt_idx, pt_K, pt_weight,
                    reg_weight, tpl_name, ins_name, par_file, obs_file,
                    python_exe="python", sihl_cell_ids=None):
    """Write a minimal PEST control file."""
    n_obs = len(obs_info)
    n_prior = n_pp + 1  # preferred-value regularisation on each PP + PT prior
    has_sihl = sihl_cell_ids is not None
    n_par = n_pp + (1 if has_sihl else 0)

    lines = []
    lines.append("pcf\n")

    # --- Control data (pyemu-compatible format) ---
    lines.append("* control data\n")
    lines.append("restart estimation\n")
    n_pargp = 1 + (1 if has_sihl else 0)   # hk_grp + optional riv_grp
    n_obsgp = 2   # observation groups: heads, prior_info
    n_tplfle = 1 + (1 if has_sihl else 0)  # hk_pps.tpl + optional sihl_mult.tpl
    lines.append(f" {n_par}  {n_obs}  {n_pargp}  {n_prior}  {n_obsgp}\n")
    lines.append(f"  {n_tplfle}  1  single  point  1\n")  # NTPLFLE NINSFLE PRECIS DPOINT NUMCOM
    lines.append("5.0  2.0  0.3  0.01  -3\n")         # RLAMBDA1 RLAMFAC PHIRATSUF PHIREDLAM NUMLAM
    lines.append("3.0  3.0  0.001\n")                  # RELPARMAX FACPARMAX FACORIG
    lines.append("0.01\n")                              # PHIREDSWH
    lines.append("10  0.01  3  3  0.01  3\n")          # NOPTMAX PHIREDSTP NPHISTP NPHINORED RELPARSTP NRELPAR
    lines.append("0  0  0\n")                           # ICOV ICOR IEIG

    # --- Parameter groups ---
    lines.append("* parameter groups\n")
    lines.append("hk_grp  relative  0.01  0.0  switch  2.0  parabolic\n")
    if has_sihl:
        lines.append("riv_grp  relative  0.01  0.01  switch  2.0  parabolic\n")

    # --- Parameter data ---
    lines.append("* parameter data\n")
    for i in range(n_pp):
        name = f"hk_pp_{i:02d}"
        # Values are in log10(K) space; use 'none' transform to avoid double-log
        init = np.log10(k_initial)
        lo = np.log10(k_lower)
        hi = np.log10(k_upper)
        lines.append(f"{name}  none  factor  {init:.6f}  {lo:.6f}  {hi:.6f}  hk_grp  1.0  0.0  1\n")
    if has_sihl:
        # Sihl leakance multiplier: value IS log10, bounds 0.1× to 100×
        # Use 'relative' (not 'factor') because bounds cross zero
        lines.append("sihl_leakance_mult  none  relative  0.000000  -1.000000  2.000000  riv_grp  1.0  0.0  1\n")

    # --- Observation groups ---
    lines.append("* observation groups\n")
    lines.append("heads\n")
    lines.append("prior_info\n")

    # --- Observation data ---
    lines.append("* observation data\n")
    for _, row in obs_info.iterrows():
        lines.append(f"{row['obs_name']}  {row['obs_value']:.4f}  {row['weight']:.4f}  heads\n")

    # --- Model command ---
    # Use a shell wrapper because PEST++ strips the leading '/' from absolute paths
    lines.append("* model command line\n")
    lines.append("./run_model.sh\n")

    # --- Model I/O ---
    lines.append("* model input/output\n")
    lines.append(f"{tpl_name}  {par_file}\n")
    if has_sihl:
        lines.append("sihl_mult.tpl  sihl_mult.dat\n")
    lines.append(f"{ins_name}  {obs_file}\n")

    # --- Prior information ---
    lines.append("* prior information\n")
    # Preferred-value regularisation: pull every PP toward k_initial
    reg_target = np.log10(k_initial)
    for i in range(n_pp):
        name = f"hk_pp_{i:02d}"
        lines.append(f"pi_reg_{i:02d}  1.0 * {name} = {reg_target:.6f}  {reg_weight:.4f}  prior_info\n")
    # PT-specific prior: pull nearest PP toward pumping-test K
    pi_name = f"hk_pp_{pp_pt_idx:02d}"
    pi_val = np.log10(pt_K)
    lines.append(f"pi_pt_k  1.0 * {pi_name} = {pi_val:.6f}  {pt_weight:.4f}  prior_info\n")

    # --- PEST++ section ---
    lines.append("++# pestpp options\n")
    lines.append("++svd_pack(redsvd)\n")
    lines.append("++max_n_super(10)\n")
    lines.append("++n_iter_base(1)\n")
    lines.append("++n_iter_super(4)\n")

    with open(path, "w") as f:
        f.writelines(lines)


def _write_forward_run_script(pest_ws, model_ws, modelgrid, obs_df, pp_xy,
                              variogram_range, obs_x_col, obs_y_col,
                              obs_id_col, obs_head_col, sihl_cell_ids=None,
                              anisotropy_angle=0.0, anisotropy_scaling=1.0):
    """
    Write ``forward_run.py`` inside *pest_ws*.

    This script is executed by PEST++ for each model run.  It:
    1. Reads pilot-point K values from the template-generated file
    2. Interpolates to the model grid
    3. Overwrites the K array in the MODFLOW 6 model (NPF package)
    4. Runs MODFLOW 6
    5. Extracts heads at observation locations → writes output file
    """
    # Serialise observation well (x, y) for the forward-run script
    obs_xy = []
    for _, row in obs_df.iterrows():
        obs_xy.append({
            "obs_id": str(row[obs_id_col]),
            "x": float(row[obs_x_col]),
            "y": float(row[obs_y_col]),
        })

    # Write pp locations
    np.save(os.path.join(pest_ws, "pp_xy.npy"), pp_xy)

    # Compute the absolute path to _SUPPORT/src for the forward-run script
    support_src_abs = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )

    script = f'''#!/usr/bin/env python
"""Forward-run script called by PEST++ for each parameter evaluation."""
import os, sys
import numpy as np

# --- Configuration (written by setup_pest_calibration.py) ---
MODEL_WS = r"{os.path.abspath(model_ws)}"
PEST_WS  = r"{os.path.abspath(pest_ws)}"
SUPPORT_SRC = r"{support_src_abs}"
PP_XY_FILE = os.path.join(PEST_WS, "pp_xy.npy")
VARIOGRAM_RANGE = {variogram_range}
ANISOTROPY_ANGLE = {anisotropy_angle}
ANISOTROPY_SCALING = {anisotropy_scaling}
SIM_NAME = "limmat_valley"
OBS_XY = {obs_xy!r}


def _idw_interpolate(pp_xy, pp_values, xc, yc):
    """Inverse-distance weighting fallback for pilot-point interpolation."""
    theta = np.radians(ANISOTROPY_ANGLE)
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    field = np.zeros(len(xc))
    for i in range(len(xc)):
        dx = xc[i] - pp_xy[:, 0]
        dy = yc[i] - pp_xy[:, 1]
        dx_rot = dx * cos_t + dy * sin_t
        dy_rot = (-dx * sin_t + dy * cos_t) * ANISOTROPY_SCALING
        d2 = dx_rot ** 2 + dy_rot ** 2
        d2[d2 == 0] = 1e-10
        w = 1.0 / d2
        field[i] = np.sum(w * pp_values) / np.sum(w)
    field = 10.0 ** field
    return field


def run():
    # 1. Read pilot-point values (log10 K) from PEST-generated file
    pp_vals = np.loadtxt(os.path.join(PEST_WS, "hk_pps.dat"))
    pp_xy = np.load(PP_XY_FILE)

    # 2. Import interpolation function
    sys.path.insert(0, SUPPORT_SRC)
    try:
        from scripts.setup_pest_calibration import _interpolate_pp_to_grid
    except ImportError:
        _interpolate_pp_to_grid = None

    # 3. Load MODFLOW 6 simulation
    import flopy
    sim = flopy.mf6.MFSimulation.load(
        sim_ws=MODEL_WS, verbosity_level=0,
    )
    gwf = sim.get_model(SIM_NAME)
    modelgrid = gwf.modelgrid

    # Interpolate K field
    if _interpolate_pp_to_grid is not None:
        k_field = _interpolate_pp_to_grid(
            pp_xy, pp_vals, modelgrid,
            method="ordinary_kriging", variogram_range=VARIOGRAM_RANGE,
            anisotropy_angle=ANISOTROPY_ANGLE,
            anisotropy_scaling=ANISOTROPY_SCALING,
        )
    else:
        # IDW fallback
        xc = modelgrid.xcellcenters
        yc = modelgrid.ycellcenters
        k_field = _idw_interpolate(pp_xy, pp_vals, xc, yc)

    # Update K in NPF package
    gwf.npf.k.set_data(k_field)

    # 3b. Apply Sihl leakance multiplier (if present)
    sihl_mult_path = os.path.join(PEST_WS, "sihl_mult.dat")
    sihl_ids_path = os.path.join(PEST_WS, "sihl_cell_ids.npy")
    if os.path.exists(sihl_mult_path) and os.path.exists(sihl_ids_path):
        sihl_mult_log = float(np.loadtxt(sihl_mult_path))
        sihl_mult = 10.0 ** sihl_mult_log
        sihl_ids = np.load(sihl_ids_path)
        sihl_set = set(sihl_ids.tolist())

        riv = gwf.get_package('RIV')
        spd = riv.stress_period_data.get_data(0)
        for i in range(len(spd)):
            cid = spd[i]['cellid']
            cell_idx = cid[-1] if isinstance(cid, tuple) else cid
            if cell_idx in sihl_set:
                spd[i]['cond'] *= sihl_mult
        riv.stress_period_data.set_data(spd, key=0)

    # 4. Write and run
    sim.write_simulation()
    success, _ = sim.run_simulation(silent=True)
    if not success:
        # Write dummy output so PEST knows it failed
        with open(os.path.join(PEST_WS, "heads_sim.dat"), "w") as f:
            for w in OBS_XY:
                f.write("-9999.0\\n")
        return

    # 5. Extract heads at observation locations using GridIntersect
    head = gwf.output.head().get_data()
    heads_flat = head.flatten() if head.ndim > 1 else head

    from flopy.utils import GridIntersect
    from shapely.geometry import Point
    ix = GridIntersect(modelgrid, method="vertex")

    with open(os.path.join(PEST_WS, "heads_sim.dat"), "w") as f:
        for w in OBS_XY:
            try:
                result = ix.intersect(Point(w["x"], w["y"]))
                if len(result) > 0:
                    cell_id = result.cellids[0]
                    if isinstance(cell_id, tuple):
                        cell_id = cell_id[-1]
                    h = float(heads_flat[cell_id])
                else:
                    h = -9999.0
            except Exception:
                h = -9999.0
            f.write(f"{{h:.4f}}\\n")

if __name__ == "__main__":
    run()
'''
    fwd_path = os.path.join(pest_ws, "forward_run.py")
    with open(fwd_path, "w") as f:
        f.write(script)


def run_pestpp_glm(pest_ws, pst_file="calibration.pst", num_workers=1):
    """
    Run pestpp-glm.

    Parameters
    ----------
    pest_ws : str
        Directory containing the PST file.
    pst_file : str
        Name of the PEST control file.
    num_workers : int
        Number of parallel workers (1 = serial).

    Returns
    -------
    success : bool
    """
    import subprocess
    exe = shutil.which("pestpp-glm")
    if exe is None:
        # Try pyemu metadata file (created by get-pestpp)
        try:
            import json as _json
            meta_path = os.path.expanduser("~/.local/share/pyemu/get_pestpp.json")
            if os.path.exists(meta_path):
                with open(meta_path) as _f:
                    meta = _json.load(_f)
                # get_pestpp.json is a list of install records
                if isinstance(meta, list) and len(meta) > 0:
                    meta = meta[0]
                bindir = meta.get("bindir", "") if isinstance(meta, dict) else ""
                candidate = os.path.join(bindir, "pestpp-glm")
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    exe = candidate
        except Exception:
            pass
    if exe is None:
        raise FileNotFoundError(
            "pestpp-glm not found on PATH.\n"
            "Install it with:  get-pestpp /path/to/bin\n"
            "  (get-pestpp is bundled with pyemu)"
        )

    cmd = [exe, pst_file]
    print(f"Running: {' '.join(cmd)}  in  {pest_ws}")
    result = subprocess.run(cmd, cwd=pest_ws, capture_output=True, text=True)
    success = result.returncode == 0
    if not success:
        print("pestpp-glm FAILED")
        print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
        print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
    else:
        print("pestpp-glm completed successfully.")
    return success


def load_pest_results(pest_ws, pst_file="calibration.pst"):
    """
    Load optimised parameters and residuals from a completed PEST++ run.

    Returns
    -------
    par_df : pd.DataFrame  (parameter name, initial, optimised)
    res_df : pd.DataFrame  (observation name, measured, modelled, residual, weight)
    """
    import pyemu
    pst = pyemu.Pst(os.path.join(pest_ws, pst_file))

    # Parameters
    par = pst.parameter_data[["parval1", "parlbnd", "parubnd", "pargp"]].copy()
    par.rename(columns={"parval1": "initial"}, inplace=True)

    # Try to read optimised values
    rei_file = os.path.join(pest_ws, pst_file.replace(".pst", ".rei"))
    if os.path.exists(rei_file):
        res_df = pyemu.pst_utils.read_resfile(rei_file)
    else:
        res_df = pst.observation_data[["obsval", "weight", "obgnme"]].copy()
        res_df["modelled"] = np.nan
        res_df["residual"] = np.nan

    # Optimised parameter values from .par file
    par_file = os.path.join(pest_ws, pst_file.replace(".pst", ".par"))
    if os.path.exists(par_file):
        opt_par = pyemu.pst_utils.read_parfile(par_file)
        par["optimised"] = opt_par["parval1"]
    else:
        par["optimised"] = np.nan

    return par, res_df


def read_pest_phi_progress(pest_ws, pst_file="calibration.pst"):
    """
    Read the PEST++ objective-function history from the ``.iobj`` file.

    Parameters
    ----------
    pest_ws : str
        PEST++ working directory.
    pst_file : str
        Name of the PST file (used to derive the .iobj filename).

    Returns
    -------
    pd.DataFrame with columns: iteration, total_phi, meas_phi, reg_phi
        Returns ``None`` if the file does not exist or cannot be parsed.
    """
    iobj_path = os.path.join(pest_ws, pst_file.replace(".pst", ".iobj"))
    if not os.path.exists(iobj_path):
        return None
    try:
        df = pd.read_csv(iobj_path, skipinitialspace=True)
        # pestpp-glm .iobj has columns like:
        #   iteration, total_phi, model_runs_completed, ...
        # Rename for convenience
        col_map = {}
        for c in df.columns:
            cl = c.strip().lower()
            if cl == "iteration":
                col_map[c] = "iteration"
            elif cl == "total_phi":
                col_map[c] = "total_phi"
            elif cl in ("measurement_phi", "meas_phi"):
                col_map[c] = "meas_phi"
            elif cl in ("regularization_phi", "reg_phi", "regul_phi"):
                col_map[c] = "reg_phi"
        df.rename(columns=col_map, inplace=True)
        return df
    except Exception:
        return None


def get_calibrated_k_field(pest_ws, modelgrid, variogram_range=600.0,
                           anisotropy_angle=-30.0, anisotropy_scaling=3.0):
    """
    Read optimised pilot-point values and interpolate to the model grid.

    Parameters
    ----------
    pest_ws : str
    modelgrid : flopy grid
    variogram_range : float
    anisotropy_angle : float
        Angle of major anisotropy axis, CCW from east [degrees].
    anisotropy_scaling : float
        Ratio of major to minor variogram range.

    Returns
    -------
    k_field : ndarray (nrow, ncol) or (ncells,) — K in m/d
    pp_df : pd.DataFrame with pilot point locations and K values
    """
    pp_df = pd.read_csv(os.path.join(pest_ws, "pilot_points.csv"))
    pp_xy = pp_df[["x", "y"]].values

    # Try reading optimised .par file
    par_file = os.path.join(pest_ws, "calibration.par")
    if os.path.exists(par_file):
        import pyemu
        par = pyemu.pst_utils.read_parfile(par_file)
        pp_log_vals = np.array([par.loc[f"hk_pp_{i:02d}", "parval1"]
                                for i in range(len(pp_df))])
    else:
        # Fall back to initial values
        pp_log_vals = np.loadtxt(os.path.join(pest_ws, "hk_pps.dat"))

    pp_df["log10_K"] = pp_log_vals
    pp_df["K_md"] = 10.0 ** pp_log_vals

    k_field = _interpolate_pp_to_grid(
        pp_xy, pp_log_vals, modelgrid,
        method="ordinary_kriging", variogram_range=variogram_range,
        anisotropy_angle=anisotropy_angle,
        anisotropy_scaling=anisotropy_scaling,
    )
    return k_field, pp_df


def apply_calibrated_parameters(
    gwf, pest_ws, modelgrid, river_gdf, boundary_gdf,
    variogram_range=600.0, anisotropy_angle=-30.0, anisotropy_scaling=3.0,
    set_npf_flags=True,
):
    """
    Apply calibrated K field and Sihl leakance multiplier to a GWF model.

    This encapsulates the boilerplate shared across NB5, NB6, and NB8:
    kriging the pilot-point K field, loading the optimised Sihl multiplier,
    and optionally enabling NPF output flags for particle tracking.

    Parameters
    ----------
    gwf : flopy.mf6.ModflowGwf
        Groundwater flow model to modify in-place.
    pest_ws : str
        Path to the PEST++ working directory.
    modelgrid : flopy grid
        Model grid object.
    river_gdf : geopandas.GeoDataFrame
        River polygons (must include Limmat and Sihl).
    boundary_gdf : geopandas.GeoDataFrame
        Model domain polygon.
    variogram_range : float, optional
        Kriging variogram range [m]. Default 600.
    anisotropy_angle : float, optional
        Variogram anisotropy angle [degrees]. Default -30.
    anisotropy_scaling : float, optional
        Variogram anisotropy scaling. Default 3.
    set_npf_flags : bool, optional
        If True, enable ``save_specific_discharge``, ``save_flows``, and
        ``save_saturation`` on the NPF package. Default True.

    Returns
    -------
    dict
        ``k_field``       – interpolated K array (same shape as grid)
        ``par_df``        – optimised parameter DataFrame
        ``sihl_mult``     – applied Sihl leakance multiplier (1.0 if not present)
        ``sihl_cell_ids`` – array of cell indices belonging to the Sihl
    """
    from shapely.geometry import Point as _Point

    # --- 1. Calibrated K field ---
    k_field, pp_df = get_calibrated_k_field(
        pest_ws, modelgrid,
        variogram_range=variogram_range,
        anisotropy_angle=anisotropy_angle,
        anisotropy_scaling=anisotropy_scaling,
    )
    gwf.npf.k.set_data(k_field)

    # --- 2. Load PEST results and identify Sihl cells ---
    par_df, _ = load_pest_results(pest_ws)

    xc = modelgrid.xcellcenters
    yc = modelgrid.ycellcenters

    sihl_poly = river_gdf[river_gdf['GEWAESSERNAME'] == 'Sihl'].union_all()
    riv = gwf.get_package('RIV')
    riv_data = riv.stress_period_data.get_data(0)
    sihl_cell_ids = []
    for rec in riv_data:
        cid = rec['cellid']
        cell_idx = cid[-1] if isinstance(cid, tuple) else cid
        if sihl_poly.contains(_Point(xc[cell_idx], yc[cell_idx])):
            sihl_cell_ids.append(cell_idx)

    # --- 3. Apply Sihl leakance multiplier ---
    sihl_mult = 1.0
    if 'sihl_leakance_mult' in par_df.index:
        mult_log = par_df.loc['sihl_leakance_mult', 'optimised']
        if not np.isnan(mult_log):
            sihl_mult = 10.0 ** mult_log
            spd = riv.stress_period_data.get_data(0)
            sihl_set = set(sihl_cell_ids)
            for i in range(len(spd)):
                cid = spd[i]['cellid']
                cell_idx = cid[-1] if isinstance(cid, tuple) else cid
                if cell_idx in sihl_set:
                    spd[i]['cond'] *= sihl_mult
            riv.stress_period_data.set_data(spd, key=0)
            print(f"Sihl leakance multiplier applied: {sihl_mult:.1f}×")

    # --- 4. NPF flags ---
    if set_npf_flags:
        gwf.npf.save_specific_discharge = True
        gwf.npf.save_flows = True
        gwf.npf.save_saturation = True

    return {
        'k_field': k_field,
        'par_df': par_df,
        'sihl_mult': sihl_mult,
        'sihl_cell_ids': np.array(sihl_cell_ids),
    }


def run_loo_cross_validation(
    nb4_workspace,
    val_workspace,
    sim_name,
    modelgrid,
    obs_gdf,
    real_well_ids,
    K_pumping_test,
    pt_location,
    idomain,
    sihl_cell_ids=None,
    n_pilot_points=20,
    k_initial=200.0,
    k_lower=10.0,
    k_upper=600.0,
    pt_weight=1.5,
    reg_weight=0.5,
    variogram_range=600.0,
    anisotropy_angle=-30.0,
    anisotropy_scaling=3.0,
    verbose=True,
):
    """
    Run leave-one-out cross-validation on the real observation wells.

    For each of the N real wells, this function:
    1. Creates a fresh copy of the NB4 model
    2. Drops one real well from the observation set (keeps all synthetic)
    3. Builds and runs a PEST++ calibration
    4. Predicts the head at the held-out well
    5. Records the prediction error

    Parameters
    ----------
    nb4_workspace : str
        Path to the base NB4 model directory (copied fresh per fold).
    val_workspace : str
        Parent directory for fold workspaces (fold_0/, fold_1/, ...).
    sim_name : str
        MF6 simulation name (e.g. 'limmat_valley').
    modelgrid : flopy grid
        Model grid object.
    obs_gdf : gpd.GeoDataFrame
        Full observation set (real + synthetic) with columns:
        obs_id, x, y, head_m, is_synthetic, geometry.
    real_well_ids : list of str
        obs_id values of the real wells to hold out one at a time.
    K_pumping_test : float
        Pumping-test K for prior information [m/d].
    pt_location : tuple (x, y)
        Pumping-test location coordinates.
    idomain : np.ndarray
        Active-cell indicator (1=active).
    sihl_cell_ids : np.ndarray, optional
        Cell IDs belonging to the Sihl river (for leakance multiplier).
    n_pilot_points : int
        Number of pilot points (default 20).
    k_initial, k_lower, k_upper : float
        Initial K and bounds [m/d].
    pt_weight, reg_weight : float
        PEST prior-information and regularisation weights.
    variogram_range : float
        Kriging variogram range [m].
    anisotropy_angle, anisotropy_scaling : float
        Variogram anisotropy parameters.
    verbose : bool
        Print progress messages.

    Returns
    -------
    list of dict
        One dict per fold containing:
        - fold : int
        - held_out_well : str (obs_id)
        - obs_head : float (observed head at held-out well)
        - predicted_head : float (predicted head, or NaN on failure)
        - prediction_error : float (predicted - observed, or NaN)
        - k_field : np.ndarray (calibrated K for this fold)
        - calib_rmse : float (training RMSE at calibration wells)
        - pest_success : bool
    """
    import flopy
    from flopy.utils import GridIntersect
    from shapely.geometry import Point
    import numpy.lib.recfunctions as rfn

    # Lazy import for calibration utilities
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import calibration_utils as cu

    os.makedirs(val_workspace, exist_ok=True)
    results = []

    for fold_idx, held_out_id in enumerate(real_well_ids):
        fold_ws = os.path.join(val_workspace, f"fold_{fold_idx}")

        if verbose:
            print(f"\n{'='*60}")
            print(f"LOO Fold {fold_idx + 1}/{len(real_well_ids)}: "
                  f"holding out well {held_out_id}")
            print(f"{'='*60}")

        # --- 1. Fresh copy of NB4 model ---
        if os.path.exists(fold_ws):
            shutil.rmtree(fold_ws)
        shutil.copytree(nb4_workspace, fold_ws)

        # --- 2. Load fresh simulation ---
        try:
            sim = flopy.mf6.MFSimulation.load(sim_ws=fold_ws, verbosity_level=0)
            gwf = sim.get_model(sim_name)
        except Exception as e:
            if verbose:
                print(f"  Failed to load simulation: {e}")
            results.append(_loo_failure_result(fold_idx, held_out_id, obs_gdf))
            continue

        # --- 3. Clean WEL entries in inactive cells ---
        wel = gwf.get_package('WEL')
        if wel is not None:
            wd = wel.stress_period_data.get_data(0)
            if wd is not None and len(wd) > 0:
                id_flat = idomain.flatten()
                keep = [r for r in wd if id_flat[r['cellid'][-1]] > 0]
                if len(keep) < len(wd):
                    wel.stress_period_data.set_data(keep, key=0)

        # --- 4. Drop the held-out well ---
        obs_fold = obs_gdf[obs_gdf['obs_id'] != held_out_id].copy()
        held_out_row = obs_gdf[obs_gdf['obs_id'] == held_out_id].iloc[0]
        obs_head = float(held_out_row['head_m'])

        if verbose:
            n_real = (~obs_fold['is_synthetic']).sum()
            n_synth = obs_fold['is_synthetic'].sum()
            print(f"  Training obs: {len(obs_fold)} ({n_real} real + {n_synth} synthetic)")

        # --- 5. Build PEST setup ---
        try:
            pest_ws, pp_xy = build_pest_setup(
                model_ws=fold_ws,
                modelgrid=modelgrid,
                obs_df=obs_fold,
                pt_K=K_pumping_test,
                pt_location=pt_location,
                n_pilot_points=n_pilot_points,
                k_initial=k_initial,
                k_lower=k_lower,
                k_upper=k_upper,
                pt_weight=pt_weight,
                reg_weight=reg_weight,
                variogram_range=variogram_range,
                idomain=idomain,
                sihl_cell_ids=sihl_cell_ids,
                anisotropy_angle=anisotropy_angle,
                anisotropy_scaling=anisotropy_scaling,
            )
        except Exception as e:
            if verbose:
                print(f"  PEST setup failed: {e}")
            results.append(_loo_failure_result(fold_idx, held_out_id, obs_gdf))
            continue

        # --- 6. Run PEST++ calibration ---
        pest_success = run_pestpp_glm(pest_ws)
        if not pest_success:
            if verbose:
                print(f"  PEST++ failed for fold {fold_idx}")
            results.append(_loo_failure_result(
                fold_idx, held_out_id, obs_gdf, pest_success=False,
            ))
            continue

        # --- 7. Load calibrated K field ---
        try:
            k_field, pp_df = get_calibrated_k_field(
                pest_ws, modelgrid,
                variogram_range=variogram_range,
                anisotropy_angle=anisotropy_angle,
                anisotropy_scaling=anisotropy_scaling,
            )
        except Exception as e:
            if verbose:
                print(f"  Could not load calibrated K: {e}")
            results.append(_loo_failure_result(
                fold_idx, held_out_id, obs_gdf, pest_success=True,
            ))
            continue

        # --- 8. Apply Sihl leakance multiplier if present ---
        try:
            par_df, _ = load_pest_results(pest_ws)
            if 'sihl_leakance_mult' in par_df.index:
                sihl_mult_log = par_df.loc['sihl_leakance_mult', 'optimised']
                if not np.isnan(sihl_mult_log):
                    sihl_mult = 10.0 ** sihl_mult_log
                    riv = gwf.get_package('RIV')
                    if riv is not None and sihl_cell_ids is not None:
                        spd = riv.stress_period_data.get_data(0)
                        sihl_set = set(sihl_cell_ids.tolist())
                        for i in range(len(spd)):
                            cid = spd[i]['cellid']
                            cell_idx = cid[-1] if isinstance(cid, tuple) else cid
                            if cell_idx in sihl_set:
                                spd[i]['cond'] *= sihl_mult
                        riv.stress_period_data.set_data(spd, key=0)
        except Exception:
            pass  # Non-critical: proceed without Sihl adjustment

        # --- 9. Set K, write, run ---
        gwf.npf.k.set_data(k_field)
        sim.write_simulation()
        run_success, _ = sim.run_simulation(silent=True)

        if not run_success:
            if verbose:
                print(f"  Model run failed for fold {fold_idx}")
            results.append(_loo_failure_result(
                fold_idx, held_out_id, obs_gdf,
                pest_success=True, k_field=k_field,
            ))
            continue

        # --- 10. Predict at held-out well ---
        head = gwf.output.head().get_data()
        held_out_gdf = obs_gdf[obs_gdf['obs_id'] == held_out_id].copy()
        pred_heads = cu.extract_heads_at_observations(head, held_out_gdf, modelgrid)
        predicted_head = float(pred_heads[0]) if len(pred_heads) > 0 else np.nan

        prediction_error = predicted_head - obs_head

        # --- 11. Training RMSE at calibration wells ---
        train_sim_heads = cu.extract_heads_at_observations(head, obs_fold, modelgrid)
        valid = ~np.isnan(train_sim_heads)
        if valid.any():
            train_metrics = cu.calculate_calibration_metrics(
                obs_fold.loc[valid, 'head_m'].values,
                train_sim_heads[valid],
            )
            calib_rmse = train_metrics['RMSE']
        else:
            calib_rmse = np.nan

        if verbose:
            print(f"  Observed: {obs_head:.2f} m, "
                  f"Predicted: {predicted_head:.2f} m, "
                  f"Error: {prediction_error:+.2f} m, "
                  f"Training RMSE: {calib_rmse:.2f} m")

        results.append({
            'fold': fold_idx,
            'held_out_well': held_out_id,
            'obs_head': obs_head,
            'predicted_head': predicted_head,
            'prediction_error': prediction_error,
            'k_field': k_field,
            'calib_rmse': calib_rmse,
            'pest_success': True,
        })

    return results


def _loo_failure_result(fold_idx, held_out_id, obs_gdf,
                        pest_success=False, k_field=None):
    """Return a NaN-filled result dict for a failed LOO fold."""
    held_out_row = obs_gdf[obs_gdf['obs_id'] == held_out_id].iloc[0]
    return {
        'fold': fold_idx,
        'held_out_well': held_out_id,
        'obs_head': float(held_out_row['head_m']),
        'predicted_head': np.nan,
        'prediction_error': np.nan,
        'k_field': k_field,
        'calib_rmse': np.nan,
        'pest_success': pest_success,
    }
