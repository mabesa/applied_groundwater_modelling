"""
Calibration utilities for the Limmat Valley groundwater model.

This module provides functions for model calibration including:
- Loading and preparing observation data
- Generating synthetic observations for teaching purposes
- Calculating calibration metrics (ME, MAE, RMSE, NRMSE, R²)
- Visualizing calibration results (scatter plots, residual maps)
- Running calibration trials with parameter multipliers

Note on synthetic observations:
    To demonstrate calibration methods with adequate spatial coverage,
    this module can generate synthetic observation points in addition
    to real AWEL monitoring data. Synthetic points are always clearly
    marked with is_synthetic=True and visually distinguished in plots.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


# =============================================================================
# CALIBRATION METRICS
# =============================================================================

def calculate_calibration_metrics(
    observed: np.ndarray,
    simulated: np.ndarray
) -> Dict[str, float]:
    """
    Calculate standard calibration metrics.

    Parameters
    ----------
    observed : np.ndarray
        Observed head values (m)
    simulated : np.ndarray
        Simulated head values (m)

    Returns
    -------
    dict
        Dictionary containing:
        - ME: Mean Error (bias) - positive means simulated > observed
        - MAE: Mean Absolute Error
        - RMSE: Root Mean Square Error
        - NRMSE: Normalized RMSE as percentage of observed range
        - R2: Coefficient of determination

    Examples
    --------
    >>> obs = np.array([100, 98, 95, 92, 90])
    >>> sim = np.array([99.5, 97.8, 95.2, 92.5, 90.3])
    >>> metrics = calculate_calibration_metrics(obs, sim)
    >>> print(f"RMSE: {metrics['RMSE']:.2f} m")
    """
    observed = np.asarray(observed)
    simulated = np.asarray(simulated)

    if len(observed) != len(simulated):
        raise ValueError("observed and simulated arrays must have same length")

    residuals = simulated - observed

    # Mean Error (bias)
    ME = np.mean(residuals)

    # Mean Absolute Error
    MAE = np.mean(np.abs(residuals))

    # Root Mean Square Error
    RMSE = np.sqrt(np.mean(residuals**2))

    # Normalized RMSE (as percentage of observed range)
    obs_range = observed.max() - observed.min()
    if obs_range > 0:
        NRMSE = (RMSE / obs_range) * 100
    else:
        NRMSE = np.nan

    # Coefficient of determination (R²)
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((observed - observed.mean())**2)
    if ss_tot > 0:
        R2 = 1 - (ss_res / ss_tot)
    else:
        R2 = np.nan

    return {
        "ME": ME,
        "MAE": MAE,
        "RMSE": RMSE,
        "NRMSE": NRMSE,
        "R2": R2
    }


def format_metrics_table(metrics: Dict[str, float]) -> str:
    """
    Format calibration metrics as a readable table string.

    Parameters
    ----------
    metrics : dict
        Dictionary from calculate_calibration_metrics()

    Returns
    -------
    str
        Formatted table string
    """
    lines = [
        "Calibration Metrics",
        "-" * 30,
        f"  Mean Error (ME):     {metrics['ME']:>8.3f} m",
        f"  Mean Abs Error (MAE):{metrics['MAE']:>8.3f} m",
        f"  RMSE:                {metrics['RMSE']:>8.3f} m",
        f"  NRMSE:               {metrics['NRMSE']:>8.1f} %",
        f"  R²:                  {metrics['R2']:>8.3f}",
        "-" * 30,
    ]
    return "\n".join(lines)


def compare_metrics(
    before: Dict[str, float],
    after: Dict[str, float],
    labels: Tuple[str, str] = ("Before", "After"),
) -> str:
    """
    Format a side-by-side comparison of two sets of calibration metrics.

    Parameters
    ----------
    before : dict
        Metrics dictionary from calculate_calibration_metrics() (first set).
    after : dict
        Metrics dictionary from calculate_calibration_metrics() (second set).
    labels : tuple of str
        Labels for the two columns.

    Returns
    -------
    str
        Formatted comparison table string.
    """
    header = f"{'Metric':<22} {labels[0]:>10} {labels[1]:>10} {'Change':>10}"
    sep = "-" * len(header)
    lines = [
        "Calibration Metrics Comparison",
        sep,
        header,
        sep,
    ]
    for key, unit in [("ME", "m"), ("MAE", "m"), ("RMSE", "m"),
                       ("NRMSE", "%"), ("R2", "")]:
        v1 = before[key]
        v2 = after[key]
        diff = v2 - v1
        fmt = ".3f" if key != "NRMSE" else ".1f"
        u = f" {unit}" if unit else "  "
        sign = "+" if diff > 0 else ""
        lines.append(
            f"  {key:<20} {v1:>8{fmt}}{u} {v2:>8{fmt}}{u} {sign}{diff:>7{fmt}}{u}"
        )
    lines.append(sep)
    return "\n".join(lines)


# =============================================================================
# OBSERVATION DATA LOADING
# =============================================================================

def load_awel_observations(
    data_dir: Union[str, Path],
    model_boundary: gpd.GeoDataFrame,
    target_date: Optional[str] = None,
    use_mean: bool = True
) -> gpd.GeoDataFrame:
    """
    Load AWEL groundwater observation data and filter to model domain.

    Parameters
    ----------
    data_dir : str or Path
        Path to the data directory containing time_series/all_wells_long_format.csv
    model_boundary : gpd.GeoDataFrame
        GeoDataFrame with the model boundary polygon
    target_date : str, optional
        Specific date to extract (format: 'YYYY-MM-DD'). If None, uses mean.
    use_mean : bool, default True
        If True and target_date is None, compute mean head per well.
        If False, returns all observations.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with columns:
        - obs_id: well identifier
        - x, y: coordinates (LV95)
        - head_m: observed head (m a.s.l.)
        - error_m: estimated measurement error
        - is_synthetic: False for real AWEL data
        - geometry: Point geometry
    """
    data_dir = Path(data_dir)
    csv_path = data_dir / "time_series" / "all_wells_long_format.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"AWEL data not found at {csv_path}")

    # Load the CSV
    df = pd.read_csv(csv_path)

    # Ensure required columns exist
    required_cols = ['well_id', 'x_coord', 'y_coord', 'value']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in AWEL data: {missing}")

    # Filter out rows with missing well_id or coordinates
    df = df.dropna(subset=['well_id', 'x_coord', 'y_coord', 'value'])

    if target_date is not None:
        # Filter to specific date
        if 'date' in df.columns:
            df = df[df['date'] == target_date]
        else:
            raise ValueError("Cannot filter by date: 'date' column not found")
    elif use_mean:
        # Compute mean head per well
        df = df.groupby('well_id').agg({
            'x_coord': 'first',
            'y_coord': 'first',
            'value': 'mean'
        }).reset_index()

    # Convert LV03 (6-digit) coordinates to LV95 (7-digit) if needed
    lv03_mask = df['x_coord'] < 1_000_000
    if lv03_mask.any():
        df.loc[lv03_mask, 'x_coord'] += 2_000_000
        df.loc[lv03_mask, 'y_coord'] += 1_000_000

    # Create GeoDataFrame
    geometry = [Point(x, y) for x, y in zip(df['x_coord'], df['y_coord'])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:2056")

    # Filter to model boundary
    boundary_geom = model_boundary.union_all() if hasattr(model_boundary, 'union_all') else model_boundary.unary_union
    gdf = gdf[gdf.within(boundary_geom)]

    # Rename and select columns
    gdf = gdf.rename(columns={
        'well_id': 'obs_id',
        'x_coord': 'x',
        'y_coord': 'y',
        'value': 'head_m'
    })

    # Add metadata columns
    gdf['error_m'] = 0.2  # Typical measurement uncertainty for piezometers
    gdf['is_synthetic'] = False
    gdf['source'] = 'AWEL'

    # Select final columns
    cols = ['obs_id', 'x', 'y', 'head_m', 'error_m', 'is_synthetic', 'source', 'geometry']
    gdf = gdf[[c for c in cols if c in gdf.columns]]

    return gdf


# =============================================================================
# SYNTHETIC OBSERVATION GENERATION
# =============================================================================

def generate_reference_k_field(
    modelgrid, idomain, top, bottom,
    n_pilot_points=30, seed=42,
    noise_std=0.15,
    variogram_range=3000.0,
    k_bounds=(10.0, 600.0),
    anisotropy_angle=0.0,
    anisotropy_scaling=1.0,
):
    """
    Generate a stochastic reference K field correlated with aquifer thickness.

    K follows a log-linear relationship with thickness, reflecting the geology
    of alluvial aquifers where deeper sections contain coarser gravels:

        log10(K) = 1.751 + 0.022 × thickness

    This gives K ≈ 94 m/d at 10 m thickness, ≈ 200 m/d at 25 m (matching the
    sensitivity sweep), and ≈ 710 m/d at 50 m (clipped to 600).

    Parameters
    ----------
    modelgrid : flopy grid
        Model grid object with cell centres.
    idomain : np.ndarray
        Active-cell indicator (1=active).
    top : np.ndarray
        Top elevation of the aquifer (1-D or 2-D).
    bottom : np.ndarray
        Bottom elevation of the aquifer (1-D or 2-D).
    n_pilot_points : int
        Number of pilot points for the stochastic field.
    seed : int
        Random seed for reproducibility.
    noise_std : float
        Standard deviation of Gaussian noise in log10(K) space (~±40% at 0.15).
    variogram_range : float
        Kriging variogram range [m] controlling spatial correlation.
    k_bounds : tuple
        (min, max) K bounds [m/d] for clipping.
    anisotropy_angle : float
        Angle of major anisotropy axis, CCW from east [degrees].
    anisotropy_scaling : float
        Ratio of major to minor variogram range.

    Returns
    -------
    k_field : np.ndarray (ncells,)
        Hydraulic conductivity array [m/d].
    """
    from setup_pest_calibration import _distribute_pilot_points, _interpolate_pp_to_grid

    rng = np.random.default_rng(seed)

    # Distribute pilot points across active domain
    pp_xy = _distribute_pilot_points(
        modelgrid, n_target=n_pilot_points, seed=seed, idomain=idomain,
    )

    # Cell centroids
    if hasattr(modelgrid, 'nrow'):
        xc = modelgrid.xcellcenters.ravel()
        yc = modelgrid.ycellcenters.ravel()
    else:
        xc = modelgrid.xcellcenters
        yc = modelgrid.ycellcenters

    # Thickness at all cells
    thickness = (np.asarray(top) - np.asarray(bottom)).flatten()

    # At each pilot point, find the nearest cell and compute log10(K)
    pp_log_k = np.zeros(len(pp_xy))
    for i in range(len(pp_xy)):
        dx = xc - pp_xy[i, 0]
        dy = yc - pp_xy[i, 1]
        nearest = int(np.argmin(dx**2 + dy**2))
        b = thickness[nearest]
        pp_log_k[i] = 1.751 + 0.022 * b

    # Add Gaussian noise in log10 space for spatial variability
    pp_log_k += rng.normal(0, noise_std, len(pp_log_k))

    # Interpolate to full grid via kriging
    k_field = _interpolate_pp_to_grid(
        pp_xy, pp_log_k, modelgrid,
        method="ordinary_kriging", variogram_range=variogram_range,
        anisotropy_angle=anisotropy_angle,
        anisotropy_scaling=anisotropy_scaling,
    )

    # Clip to physical bounds
    k_field = np.clip(np.asarray(k_field).flatten(), k_bounds[0], k_bounds[1])

    return k_field


def generate_conditioned_k_field(
    sim, gwf, modelgrid, idomain, top, bottom,
    obs_gdf,
    *,
    n_pilot_points=15,
    seed=42,
    noise_std=0.25,
    variogram_range=3000.0,
    anisotropy_angle=-30.0,
    anisotropy_scaling=3.0,
    k_bounds=(10.0, 600.0),
    delta_log_k=0.02,
    lambda_reg=1.0,
    max_iterations=3,
    convergence_tol=0.5,
    verbose=True,
):
    """
    Generate a thickness-dependent K field conditioned on real AWEL head
    observations using in-memory Gauss-Newton inversion.

    This function:
    1. Distributes pilot points and assigns thickness-based log10(K)
    2. Iteratively adjusts pilot-point K values so that the model reproduces
       observed heads at real AWEL wells (Jacobian-based least-squares)
    3. Adds spatially correlated stochastic noise for realistic heterogeneity
    4. Returns the final K field for synthetic observation generation

    Parameters
    ----------
    sim : flopy.mf6.MFSimulation
        The loaded MODFLOW 6 simulation.
    gwf : flopy.mf6.MFModel
        The groundwater flow model.
    modelgrid : flopy grid
        Model grid with cell centres.
    idomain : np.ndarray
        Active-cell indicator (1=active).
    top, bottom : np.ndarray
        Top and bottom elevations of the aquifer.
    obs_gdf : gpd.GeoDataFrame
        Observation wells. Must contain ``is_synthetic`` column; only wells
        with ``is_synthetic == False`` are used for conditioning.
    n_pilot_points : int
        Number of pilot points (fewer than PEST calibration since we only
        condition on ~4 real observations).
    seed : int
        Random seed for reproducibility.
    noise_std : float
        Standard deviation of post-conditioning Gaussian noise in log10(K)
        space. Smaller than unconditioned (0.15) because the trend already
        captures the main spatial structure.
    variogram_range : float
        Kriging variogram range [m].
    anisotropy_angle : float
        Angle of major anisotropy axis, CCW from east [degrees].
    anisotropy_scaling : float
        Ratio of major to minor variogram range.
    k_bounds : tuple
        (min, max) K bounds [m/d] for clipping.
    delta_log_k : float
        Finite-difference step for Jacobian computation [log10(m/d)].
    lambda_reg : float
        Tikhonov regularisation weight for the Gauss-Newton update.
    max_iterations : int
        Maximum Gauss-Newton iterations.
    convergence_tol : float
        Stop when max |residual| < this threshold [m].
    verbose : bool
        Print progress messages.

    Returns
    -------
    k_field : np.ndarray (ncells,)
        Final K with stochastic perturbation [m/d].
    k_conditioned : np.ndarray (ncells,)
        K after conditioning but before noise [m/d] (for diagnostics).
    conditioning_info : dict
        Diagnostics: iteration count, residuals, pilot-point values,
        model run count.

    Raises
    ------
    ValueError
        If no real (non-synthetic) observations are found in obs_gdf.
    """
    from setup_pest_calibration import _distribute_pilot_points, _interpolate_pp_to_grid
    from flopy.utils import GridIntersect
    from shapely.geometry import Point

    # --- Filter to real observations only ---
    if 'is_synthetic' not in obs_gdf.columns:
        raise ValueError("obs_gdf must have an 'is_synthetic' column")
    real_obs = obs_gdf[~obs_gdf['is_synthetic']].copy()
    if len(real_obs) == 0:
        raise ValueError("No real (non-synthetic) observations for conditioning")

    n_obs = len(real_obs)
    obs_heads = real_obs['head_m'].values.copy()
    if verbose:
        print(f"Conditioning on {n_obs} real AWEL observations")

    rng = np.random.default_rng(seed)

    # --- Cell centroids and thickness ---
    if hasattr(modelgrid, 'nrow'):
        xc = modelgrid.xcellcenters.ravel()
        yc = modelgrid.ycellcenters.ravel()
    else:
        xc = modelgrid.xcellcenters
        yc = modelgrid.ycellcenters

    thickness = (np.asarray(top) - np.asarray(bottom)).flatten()

    # --- Distribute pilot points ---
    pp_xy = _distribute_pilot_points(
        modelgrid, n_target=n_pilot_points, seed=seed, idomain=idomain,
    )
    n_pp = len(pp_xy)

    # --- Thickness-based initial log10(K) at each pilot point ---
    pp_log_k = np.zeros(n_pp)
    for i in range(n_pp):
        dx = xc - pp_xy[i, 0]
        dy = yc - pp_xy[i, 1]
        nearest = int(np.argmin(dx**2 + dy**2))
        b = thickness[nearest]
        pp_log_k[i] = 1.751 + 0.022 * b

    log_k_lower, log_k_upper = np.log10(k_bounds[0]), np.log10(k_bounds[1])
    pp_log_k_init = pp_log_k.copy()

    # --- Pre-compute observation cell indices ---
    ix = GridIntersect(modelgrid, method='vertex')
    obs_cell_ids = []
    for _, row in real_obs.iterrows():
        result = ix.intersect(Point(row['x'], row['y']))
        if len(result) > 0:
            cid = result.cellids[0]
            obs_cell_ids.append(cid[-1] if isinstance(cid, tuple) else cid)
        else:
            obs_cell_ids.append(None)
    obs_cell_ids = np.array(obs_cell_ids, dtype=object)

    # --- Helper: run model with given pp values and extract heads ---
    model_run_count = 0

    def _run_and_extract(log_k_vals):
        nonlocal model_run_count
        k_full = _interpolate_pp_to_grid(
            pp_xy, log_k_vals, modelgrid,
            method="ordinary_kriging", variogram_range=variogram_range,
            anisotropy_angle=anisotropy_angle,
            anisotropy_scaling=anisotropy_scaling,
        )
        k_full = np.clip(np.asarray(k_full).flatten(), k_bounds[0], k_bounds[1])
        gwf.npf.k.set_data(k_full)
        sim.write_simulation()
        success, _ = sim.run_simulation(silent=True)
        model_run_count += 1
        if not success:
            return None
        head = gwf.output.head().get_data()
        heads_flat = head.flatten() if head.ndim > 1 else head
        h_obs = np.full(n_obs, np.nan)
        for j in range(n_obs):
            if obs_cell_ids[j] is not None:
                h_obs[j] = heads_flat[int(obs_cell_ids[j])]
        return h_obs

    # --- Gauss-Newton iteration ---
    damping = 0.7
    residuals_history = []

    for iteration in range(max_iterations):
        # Base run
        h_sim = _run_and_extract(pp_log_k)
        if h_sim is None:
            if verbose:
                print(f"  Iteration {iteration+1}: base model run FAILED, stopping")
            break

        # Filter to valid observations
        valid = ~np.isnan(h_sim) & ~np.isnan(obs_heads)
        residuals = obs_heads[valid] - h_sim[valid]
        max_res = np.max(np.abs(residuals)) if len(residuals) > 0 else 0.0
        residuals_history.append(residuals.copy())

        if verbose:
            print(f"  Iteration {iteration+1}: max|residual| = {max_res:.3f} m, "
                  f"RMSE = {np.sqrt(np.mean(residuals**2)):.3f} m  "
                  f"({model_run_count} model runs so far)")

        if max_res < convergence_tol:
            if verbose:
                print(f"  Converged (max|residual| < {convergence_tol} m)")
            break

        # Compute Jacobian by finite differences
        n_valid = int(valid.sum())
        J = np.zeros((n_valid, n_pp))
        for p in range(n_pp):
            pp_pert = pp_log_k.copy()
            pp_pert[p] += delta_log_k
            h_pert = _run_and_extract(pp_pert)
            if h_pert is not None:
                h_pert_valid = h_pert[valid]
                valid_pert = ~np.isnan(h_pert_valid)
                if valid_pert.all():
                    J[:, p] = (h_pert_valid - h_sim[valid]) / delta_log_k
                # else: column stays 0 (no sensitivity)

        # Solve regularised least squares: (J^T J + λI) δk = J^T r
        JtJ = J.T @ J
        Jtr = J.T @ residuals
        A = JtJ + lambda_reg * np.eye(n_pp)
        try:
            delta_k = np.linalg.solve(A, Jtr)
        except np.linalg.LinAlgError:
            if verbose:
                print(f"  Singular matrix at iteration {iteration+1}, stopping")
            break

        # Damped update with clipping
        pp_log_k = pp_log_k + damping * delta_k
        pp_log_k = np.clip(pp_log_k, log_k_lower, log_k_upper)

    # --- Build conditioned K field (before noise) ---
    k_conditioned = _interpolate_pp_to_grid(
        pp_xy, pp_log_k, modelgrid,
        method="ordinary_kriging", variogram_range=variogram_range,
        anisotropy_angle=anisotropy_angle,
        anisotropy_scaling=anisotropy_scaling,
    )
    k_conditioned = np.clip(np.asarray(k_conditioned).flatten(), k_bounds[0], k_bounds[1])

    # --- Add spatially correlated noise ---
    pp_log_k_noisy = pp_log_k + rng.normal(0, noise_std, n_pp)
    pp_log_k_noisy = np.clip(pp_log_k_noisy, log_k_lower, log_k_upper)

    k_field = _interpolate_pp_to_grid(
        pp_xy, pp_log_k_noisy, modelgrid,
        method="ordinary_kriging", variogram_range=variogram_range,
        anisotropy_angle=anisotropy_angle,
        anisotropy_scaling=anisotropy_scaling,
    )
    k_field = np.clip(np.asarray(k_field).flatten(), k_bounds[0], k_bounds[1])

    # --- Restore model state with final K ---
    gwf.npf.k.set_data(k_field)

    conditioning_info = {
        'n_iterations': len(residuals_history),
        'residuals_final': residuals_history[-1] if residuals_history else np.array([]),
        'max_residual_final': float(np.max(np.abs(residuals_history[-1]))) if residuals_history else np.nan,
        'pp_xy': pp_xy,
        'pp_log_k_conditioned': pp_log_k.copy(),
        'pp_log_k_final': pp_log_k_noisy.copy(),
        'model_run_count': model_run_count,
    }

    if verbose:
        print(f"  Done: {model_run_count} model runs, "
              f"final max|residual| = {conditioning_info['max_residual_final']:.3f} m")

    return k_field, k_conditioned, conditioning_info


def generate_synthetic_observations(
    model_grid,
    true_heads: np.ndarray,
    idomain: np.ndarray,
    n_points: int = 15,
    noise_std: float = 0.3,
    seed: int = 42,
    min_distance_m: float = 200.0,
    avoid_boundaries_m: float = 100.0,
    exclude_cells: Optional[np.ndarray] = None,
    river_buffer_m: float = 50.0,
    river_gdf: Optional[gpd.GeoDataFrame] = None,
    boundary_polygon=None,
    exclude_north_of_river: bool = False,
) -> gpd.GeoDataFrame:
    """
    Generate synthetic observation points distributed across the model domain.

    These synthetic observations supplement real AWEL data for teaching
    calibration methods. They are generated by:
    1. Sampling cell centroids from active model cells
    2. Excluding river cells, cells near rivers, and cells north of the river
    3. Excluding cells too close to the model boundary
    4. Extracting "true" heads from a reference model run
    5. Adding realistic Gaussian measurement noise

    Parameters
    ----------
    model_grid : flopy.discretization.VertexGrid
        The DISV model grid
    true_heads : np.ndarray
        Head array from a "true" model run (shape: ncpl or nlay x ncpl)
    idomain : np.ndarray
        Active cell indicator (1=active, 0=inactive, -1=pass-through)
    n_points : int, default 15
        Number of synthetic observation points to generate
    noise_std : float, default 0.3
        Standard deviation of measurement noise (m)
    seed : int, default 42
        Random seed for reproducibility
    min_distance_m : float, default 200.0
        Minimum distance between synthetic points (m)
    avoid_boundaries_m : float, default 100.0
        Minimum distance from model boundary (m). When boundary_polygon is
        provided, this uses proper geometry-based distance; otherwise falls
        back to a simple bounding-box approach.
    exclude_cells : np.ndarray, optional
        Array of cell indices to exclude (e.g., river cells from RIV package).
        These cells will not be selected for observations.
    river_buffer_m : float, default 50.0
        Minimum distance from river geometries (if river_gdf provided)
    river_gdf : gpd.GeoDataFrame, optional
        GeoDataFrame with river polygon geometries. Cells within river_buffer_m
        of these polygons will be excluded. Also used for north/south
        classification when exclude_north_of_river is True.
    boundary_polygon : shapely.geometry.Polygon, optional
        Model domain boundary polygon. When provided, used for accurate
        distance-based boundary exclusion instead of the bounding-box fallback.
    exclude_north_of_river : bool, default False
        If True and river_gdf is provided, exclude cells whose centroids lie
        north of the river (i.e. a vertical line drawn south from the cell
        crosses the river geometry). This restricts synthetic observations
        to the main aquifer south of the river system.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with synthetic observations, columns:
        - obs_id: identifier (SYN_001, SYN_002, ...)
        - x, y: coordinates (LV95)
        - head_m: observed head with noise (m a.s.l.)
        - true_head_m: actual head without noise (for validation)
        - error_m: measurement uncertainty (= noise_std)
        - is_synthetic: True
        - geometry: Point geometry

    Notes
    -----
    The true_head_m column is included for instructor validation but
    should be hidden from students during calibration exercises.

    River cells should be excluded because their heads are controlled by
    the RIV boundary condition, not by aquifer parameters. Calibrating
    to river cell heads would give misleading results.
    """
    np.random.seed(seed)

    # Flatten heads if needed
    heads_flat = true_heads.flatten()
    idomain_flat = idomain.flatten()

    # Get active cell indices
    active_mask = idomain_flat > 0
    active_cells = np.where(active_mask)[0]

    if len(active_cells) < n_points:
        raise ValueError(f"Not enough active cells ({len(active_cells)}) for {n_points} observations")

    # Get cell centroids
    xc = model_grid.xcellcenters.flatten()
    yc = model_grid.ycellcenters.flatten()

    # Filter cells away from model boundary
    if boundary_polygon is not None:
        # Proper geometry-based boundary distance
        interior_polygon = boundary_polygon.buffer(-avoid_boundaries_m)
        if interior_polygon.is_empty:
            raise ValueError(
                f"Boundary buffer of {avoid_boundaries_m}m eliminates entire domain. "
                f"Reduce avoid_boundaries_m."
            )
        from shapely import prepare as _prepare
        _prepare(interior_polygon)
        interior_mask = np.array([
            interior_polygon.contains(Point(xc[i], yc[i]))
            for i in range(len(xc))
        ]) & active_mask
        n_boundary = active_mask.sum() - interior_mask.sum()
        print(f"Excluding {n_boundary} cells within {avoid_boundaries_m}m of boundary")
    else:
        # Fallback: simple bounding-box approach
        x_min, x_max = xc[active_mask].min(), xc[active_mask].max()
        y_min, y_max = yc[active_mask].min(), yc[active_mask].max()
        interior_mask = (
            (xc > x_min + avoid_boundaries_m) &
            (xc < x_max - avoid_boundaries_m) &
            (yc > y_min + avoid_boundaries_m) &
            (yc < y_max - avoid_boundaries_m) &
            active_mask
        )

    # Exclude specified cells (e.g., river cells)
    if exclude_cells is not None and len(exclude_cells) > 0:
        exclude_set = set(exclude_cells)
        exclude_mask = np.array([i not in exclude_set for i in range(len(idomain_flat))])
        interior_mask = interior_mask & exclude_mask
        print(f"Excluding {len(exclude_cells)} river cells")

    # Resolve river union once (used for buffer and north-of-river checks)
    river_union = None
    if river_gdf is not None and len(river_gdf) > 0:
        river_union = river_gdf.union_all() if hasattr(river_gdf, 'union_all') else river_gdf.unary_union

    # Exclude cells near river geometries
    if river_union is not None:
        river_buffered = river_union.buffer(river_buffer_m)
        near_river_mask = np.array([
            not river_buffered.contains(Point(xc[i], yc[i]))
            for i in range(len(xc))
        ])
        interior_mask = interior_mask & near_river_mask
        n_near_river = (~near_river_mask).sum()
        print(f"Excluding {n_near_river} cells within {river_buffer_m}m of rivers")

    # Exclude cells north of the river
    if exclude_north_of_river and river_union is not None:
        y_far_south = yc[active_mask].min() - 10000
        north_mask = np.array([
            LineString([(xc[i], yc[i]), (xc[i], y_far_south)]).intersects(river_union)
            for i in range(len(xc))
        ])
        n_north = (north_mask & interior_mask).sum()
        interior_mask = interior_mask & ~north_mask
        print(f"Excluding {n_north} cells north of river")

    candidate_cells = np.where(interior_mask)[0]

    if len(candidate_cells) < n_points:
        print(f"Warning: Only {len(candidate_cells)} candidate cells after filtering. "
              f"Relaxing boundary distance to {avoid_boundaries_m / 2:.0f}m.")
        # Fall back to half the boundary distance, keeping other exclusions
        if boundary_polygon is not None:
            fallback_polygon = boundary_polygon.buffer(-avoid_boundaries_m / 2)
            if not fallback_polygon.is_empty:
                fallback_mask = np.array([
                    fallback_polygon.contains(Point(xc[i], yc[i]))
                    for i in range(len(xc))
                ]) & active_mask
            else:
                fallback_mask = active_mask.copy()
        else:
            x_min, x_max = xc[active_mask].min(), xc[active_mask].max()
            y_min, y_max = yc[active_mask].min(), yc[active_mask].max()
            half_dist = avoid_boundaries_m / 2
            fallback_mask = (
                (xc > x_min + half_dist) &
                (xc < x_max - half_dist) &
                (yc > y_min + half_dist) &
                (yc < y_max - half_dist) &
                active_mask
            )
        # Re-apply cell and river exclusions (but not north-of-river)
        if exclude_cells is not None and len(exclude_cells) > 0:
            fallback_mask = fallback_mask & exclude_mask
        if river_union is not None:
            fallback_mask = fallback_mask & near_river_mask
        candidate_cells = np.where(fallback_mask)[0]

    # Select points with minimum spacing
    selected_cells = []
    selected_coords = []

    # Shuffle candidates
    shuffled_candidates = np.random.permutation(candidate_cells)

    for cell_idx in shuffled_candidates:
        if len(selected_cells) >= n_points:
            break

        cx, cy = xc[cell_idx], yc[cell_idx]

        # Check minimum distance from already selected points
        if len(selected_coords) > 0:
            distances = np.sqrt(
                (np.array([c[0] for c in selected_coords]) - cx)**2 +
                (np.array([c[1] for c in selected_coords]) - cy)**2
            )
            if distances.min() < min_distance_m:
                continue

        # Check for valid head (not dry cell)
        head_val = heads_flat[cell_idx]
        if np.isnan(head_val) or head_val < -1e10:
            continue

        selected_cells.append(cell_idx)
        selected_coords.append((cx, cy))

    if len(selected_cells) < n_points:
        print(f"Warning: Could only place {len(selected_cells)} of {n_points} synthetic observations")

    # Extract heads and add noise
    x_coords = np.array([c[0] for c in selected_coords])
    y_coords = np.array([c[1] for c in selected_coords])
    true_h = heads_flat[selected_cells]
    noisy_h = true_h + np.random.normal(0, noise_std, len(selected_cells))

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame({
        'obs_id': [f'SYN_{i+1:03d}' for i in range(len(selected_cells))],
        'x': x_coords,
        'y': y_coords,
        'head_m': noisy_h,
        'true_head_m': true_h,
        'error_m': noise_std,
        'is_synthetic': True,
        'source': 'synthetic',
        'cell_id': selected_cells,
        'geometry': [Point(x, y) for x, y in zip(x_coords, y_coords)]
    }, crs="EPSG:2056")

    return gdf


def combine_observations(
    real_obs: gpd.GeoDataFrame,
    synthetic_obs: gpd.GeoDataFrame,
    drop_true_heads: bool = True
) -> gpd.GeoDataFrame:
    """
    Combine real and synthetic observations into a single dataset.

    Parameters
    ----------
    real_obs : gpd.GeoDataFrame
        Real AWEL observations
    synthetic_obs : gpd.GeoDataFrame
        Synthetic observations
    drop_true_heads : bool, default True
        If True, removes the true_head_m column from synthetic data
        (to hide "answers" from students)

    Returns
    -------
    gpd.GeoDataFrame
        Combined observation dataset
    """
    if drop_true_heads and 'true_head_m' in synthetic_obs.columns:
        synthetic_obs = synthetic_obs.drop(columns=['true_head_m'])

    # Ensure consistent columns
    common_cols = ['obs_id', 'x', 'y', 'head_m', 'error_m', 'is_synthetic', 'source', 'geometry']

    real_subset = real_obs[[c for c in common_cols if c in real_obs.columns]].copy()
    synth_subset = synthetic_obs[[c for c in common_cols if c in synthetic_obs.columns]].copy()

    combined = pd.concat([real_subset, synth_subset], ignore_index=True)
    combined = gpd.GeoDataFrame(combined, crs="EPSG:2056")

    return combined


# =============================================================================
# HEAD EXTRACTION
# =============================================================================

def extract_heads_at_observations(
    head_array: np.ndarray,
    obs_gdf: gpd.GeoDataFrame,
    model_grid,
    layer: int = 0
) -> np.ndarray:
    """
    Extract simulated heads at observation point locations.

    Parameters
    ----------
    head_array : np.ndarray
        Simulated head array (shape: nlay x ncpl or ncpl)
    obs_gdf : gpd.GeoDataFrame
        Observation points with geometry
    model_grid : flopy.discretization.VertexGrid
        The model grid for spatial lookup
    layer : int, default 0
        Layer index to extract (for multi-layer models)

    Returns
    -------
    np.ndarray
        Simulated heads at observation locations
    """
    from flopy.utils import GridIntersect

    # Handle array shape
    if head_array.ndim == 1:
        heads_flat = head_array
    elif head_array.ndim == 2:
        heads_flat = head_array[layer, :]
    else:
        heads_flat = head_array[layer, :].flatten()

    # Create grid intersect object
    ix = GridIntersect(model_grid, method='vertex')

    simulated_heads = []
    for _, row in obs_gdf.iterrows():
        point = row.geometry
        result = ix.intersect(point)

        if len(result) > 0:
            cell_id = result.cellids[0]
            # Handle tuple cell IDs for DISV
            if isinstance(cell_id, tuple):
                cell_id = cell_id[-1]  # Get the cell number
            simulated_heads.append(heads_flat[cell_id])
        else:
            simulated_heads.append(np.nan)

    return np.array(simulated_heads)


# =============================================================================
# VISUALIZATION
# =============================================================================

def plot_calibration_scatter(
    observed: np.ndarray,
    simulated: np.ndarray,
    obs_gdf: Optional[gpd.GeoDataFrame] = None,
    title: str = "Observed vs Simulated Heads",
    show_metrics: bool = True,
    figsize: Tuple[float, float] = (8, 8)
) -> plt.Figure:
    """
    Create scatter plot of observed vs simulated heads.

    Parameters
    ----------
    observed : np.ndarray
        Observed head values
    simulated : np.ndarray
        Simulated head values
    obs_gdf : gpd.GeoDataFrame, optional
        If provided, uses is_synthetic column to color points
    title : str
        Plot title
    show_metrics : bool, default True
        If True, displays calibration metrics on plot
    figsize : tuple
        Figure size (width, height)

    Returns
    -------
    plt.Figure
        The matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Determine colors based on synthetic flag
    if obs_gdf is not None and 'is_synthetic' in obs_gdf.columns:
        is_synth = obs_gdf['is_synthetic'].values
        colors = ['#E67E22' if s else '#2E86AB' for s in is_synth]

        # Plot real and synthetic separately for legend
        real_mask = ~is_synth
        synth_mask = is_synth

        if real_mask.any():
            ax.scatter(observed[real_mask], simulated[real_mask],
                      c='#2E86AB', s=80, edgecolor='black', linewidth=0.5,
                      label='Real (AWEL)', zorder=3)
        if synth_mask.any():
            ax.scatter(observed[synth_mask], simulated[synth_mask],
                      c='#E67E22', s=80, marker='^', edgecolor='black', linewidth=0.5,
                      label='Synthetic', zorder=3)
        ax.legend(loc='upper left')
    else:
        ax.scatter(observed, simulated, c='#2E86AB', s=80,
                  edgecolor='black', linewidth=0.5, zorder=3)

    # 1:1 line
    all_vals = np.concatenate([observed, simulated])
    min_val, max_val = np.nanmin(all_vals), np.nanmax(all_vals)
    margin = (max_val - min_val) * 0.05
    line_range = [min_val - margin, max_val + margin]
    ax.plot(line_range, line_range, 'k--', linewidth=1, label='1:1 line', zorder=1)

    # Calculate and display metrics
    if show_metrics:
        valid = ~(np.isnan(observed) | np.isnan(simulated))
        if valid.any():
            metrics = calculate_calibration_metrics(observed[valid], simulated[valid])
            metrics_text = (
                f"RMSE = {metrics['RMSE']:.2f} m\n"
                f"ME = {metrics['ME']:.2f} m\n"
                f"R² = {metrics['R2']:.3f}\n"
                f"NRMSE = {metrics['NRMSE']:.1f}%"
            )
            ax.text(0.95, 0.05, metrics_text, transform=ax.transAxes,
                   fontsize=10, verticalalignment='bottom', horizontalalignment='right',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    ax.set_xlabel('Observed Head (m a.s.l.)', fontsize=11)
    ax.set_ylabel('Simulated Head (m a.s.l.)', fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.set_xlim(line_range)
    ax.set_ylim(line_range)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def plot_residual_map(
    obs_gdf: gpd.GeoDataFrame,
    residuals: np.ndarray,
    model_grid=None,
    boundary_gdf: Optional[gpd.GeoDataFrame] = None,
    title: str = "Spatial Distribution of Residuals",
    figsize: Tuple[float, float] = (12, 10),
    vmax: Optional[float] = None
) -> plt.Figure:
    """
    Map residuals spatially with diverging colormap.

    Parameters
    ----------
    obs_gdf : gpd.GeoDataFrame
        Observation points with geometry
    residuals : np.ndarray
        Residual values (simulated - observed)
    model_grid : optional
        Model grid for background (not yet implemented)
    boundary_gdf : gpd.GeoDataFrame, optional
        Model boundary for context
    title : str
        Plot title
    figsize : tuple
        Figure size
    vmax : float, optional
        Maximum absolute value for colormap. If None, uses data range.

    Returns
    -------
    plt.Figure
        The matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Add residuals to geodataframe
    plot_gdf = obs_gdf.copy()
    plot_gdf['residual'] = residuals

    # Determine color scale
    if vmax is None:
        vmax = max(abs(residuals.min()), abs(residuals.max()))
    vmax = max(vmax, 0.5)  # Minimum range of 0.5 m

    # Plot boundary if provided
    if boundary_gdf is not None:
        boundary_gdf.boundary.plot(ax=ax, color='black', linewidth=1.5, zorder=1)

    # Create diverging colormap
    cmap = plt.cm.RdBu_r
    norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    # Plot based on synthetic flag
    if 'is_synthetic' in plot_gdf.columns:
        real_gdf = plot_gdf[~plot_gdf['is_synthetic']]
        synth_gdf = plot_gdf[plot_gdf['is_synthetic']]

        # Real observations (circles)
        if len(real_gdf) > 0:
            sc1 = ax.scatter(real_gdf.geometry.x, real_gdf.geometry.y,
                           c=real_gdf['residual'], cmap=cmap, norm=norm,
                           s=150, edgecolor='black', linewidth=1.5,
                           marker='o', zorder=3, label='Real (AWEL)')

        # Synthetic observations (triangles)
        if len(synth_gdf) > 0:
            sc2 = ax.scatter(synth_gdf.geometry.x, synth_gdf.geometry.y,
                           c=synth_gdf['residual'], cmap=cmap, norm=norm,
                           s=150, edgecolor='black', linewidth=1.5,
                           marker='^', zorder=3, label='Synthetic')

        ax.legend(loc='upper right')
        scatter_for_cbar = sc1 if len(real_gdf) > 0 else sc2
    else:
        scatter_for_cbar = ax.scatter(
            plot_gdf.geometry.x, plot_gdf.geometry.y,
            c=plot_gdf['residual'], cmap=cmap, norm=norm,
            s=150, edgecolor='black', linewidth=1.5, zorder=3
        )

    # Colorbar
    cbar = plt.colorbar(scatter_for_cbar, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label('Residual (Sim - Obs) [m]', fontsize=11)

    # Add residual labels
    for _, row in plot_gdf.iterrows():
        ax.annotate(f"{row['residual']:.1f}",
                   (row.geometry.x, row.geometry.y),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=8, alpha=0.8)

    ax.set_xlabel('Easting (m)', fontsize=11)
    ax.set_ylabel('Northing (m)', fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.set_aspect('equal')

    plt.tight_layout()
    return fig


def plot_observation_network(
    obs_gdf: gpd.GeoDataFrame,
    boundary_gdf: Optional[gpd.GeoDataFrame] = None,
    river_gdf: Optional[gpd.GeoDataFrame] = None,
    title: str = "Observation Network",
    figsize: Tuple[float, float] = (12, 10)
) -> plt.Figure:
    """
    Plot the observation network showing real and synthetic points.

    Parameters
    ----------
    obs_gdf : gpd.GeoDataFrame
        Observation points
    boundary_gdf : gpd.GeoDataFrame, optional
        Model boundary
    river_gdf : gpd.GeoDataFrame, optional
        River geometries
    title : str
        Plot title
    figsize : tuple
        Figure size

    Returns
    -------
    plt.Figure
        The matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Plot boundary
    if boundary_gdf is not None:
        boundary_gdf.plot(ax=ax, facecolor='#f0f0f0', edgecolor='black',
                         linewidth=1.5, zorder=1)

    # Plot rivers
    if river_gdf is not None:
        river_gdf.plot(ax=ax, facecolor='#a6cee3', edgecolor='#1f78b4',
                      linewidth=0.5, alpha=0.7, zorder=2)

    # Plot observations
    if 'is_synthetic' in obs_gdf.columns:
        real_gdf = obs_gdf[~obs_gdf['is_synthetic']]
        synth_gdf = obs_gdf[obs_gdf['is_synthetic']]

        if len(real_gdf) > 0:
            real_gdf.plot(ax=ax, color='#2E86AB', markersize=120,
                         edgecolor='black', linewidth=1.5, marker='o',
                         zorder=4, label='Real (AWEL)')
        if len(synth_gdf) > 0:
            synth_gdf.plot(ax=ax, color='#E67E22', markersize=120,
                          edgecolor='black', linewidth=1.5, marker='^',
                          zorder=4, label='Synthetic')
        ax.legend(loc='upper right', fontsize=10)
    else:
        obs_gdf.plot(ax=ax, color='#2E86AB', markersize=120,
                    edgecolor='black', linewidth=1.5, zorder=4)

    # Add labels
    for _, row in obs_gdf.iterrows():
        ax.annotate(row['obs_id'],
                   (row.geometry.x, row.geometry.y),
                   xytext=(8, 8), textcoords='offset points',
                   fontsize=8, fontweight='bold')

    ax.set_xlabel('Easting (m)', fontsize=11)
    ax.set_ylabel('Northing (m)', fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.set_aspect('equal')

    plt.tight_layout()
    return fig


# =============================================================================
# CALIBRATION TRIALS
# =============================================================================

def run_calibration_trial(
    sim,
    gwf_name: str,
    k_multipliers: Optional[Dict[str, float]] = None,
    k_global_multiplier: float = 1.0,
    rch_multiplier: float = 1.0,
    riv_multiplier: float = 1.0,
    run_model: bool = True,
    return_budget: bool = False,
) -> np.ndarray:
    """
    Run the model with modified parameters and return heads.

    This function applies multipliers relative to the *current* parameter
    values, runs the model, and then **restores all modified parameters**
    to their pre-trial state.  This makes the function safe to call in a
    loop without cumulative drift.

    Parameters
    ----------
    sim : flopy.mf6.MFSimulation
        The MODFLOW 6 simulation object
    gwf_name : str
        Name of the groundwater flow model
    k_multipliers : dict, optional
        Zone-specific K multipliers {zone_name: multiplier}
        Not yet implemented - uses global multiplier instead
    k_global_multiplier : float, default 1.0
        Global multiplier for all K values
    rch_multiplier : float, default 1.0
        Multiplier for recharge rates
    riv_multiplier : float, default 1.0
        Multiplier for river conductance
    run_model : bool, default True
        If True, runs the model after modifying parameters
    return_budget : bool, default False
        If True, also compute the water balance summary and return a
        ``(heads, budget_df)`` tuple instead of just heads.

    Returns
    -------
    np.ndarray or tuple
        Simulated head array, or None if model failed.
        When *return_budget* is True, returns ``(heads, budget_df)``.
    """
    import copy

    gwf = sim.get_model(gwf_name)

    # --- Save current state so we can restore after the trial ---
    saved_k = None
    saved_rch = None
    saved_riv = None

    # Modify hydraulic conductivity
    if k_global_multiplier != 1.0:
        npf = gwf.get_package('NPF')
        if npf is not None:
            saved_k = copy.deepcopy(npf.k.get_data())
            original_k = npf.k.get_data()
            if isinstance(original_k, list):
                new_k = [arr * k_global_multiplier for arr in original_k]
            else:
                new_k = original_k * k_global_multiplier
            npf.k.set_data(new_k)

    # Modify recharge
    if rch_multiplier != 1.0:
        rch = gwf.get_package('RCHA')
        if rch is not None:
            original_rch = rch.recharge.get_data()
            if original_rch is not None:
                saved_rch = copy.deepcopy(original_rch)
                if isinstance(original_rch, dict):
                    new_rch = {k: v * rch_multiplier for k, v in original_rch.items()}
                else:
                    new_rch = original_rch * rch_multiplier
                rch.recharge.set_data(new_rch)

    # Modify river conductance
    if riv_multiplier != 1.0:
        riv = gwf.get_package('RIV')
        if riv is not None:
            stress_period_data = riv.stress_period_data.get_data()
            if stress_period_data is not None:
                saved_riv = copy.deepcopy(stress_period_data)
                for per, spd in stress_period_data.items():
                    if spd is not None:
                        spd['cond'] = spd['cond'] * riv_multiplier
                riv.stress_period_data.set_data(stress_period_data)

    # Write and run model
    heads = None
    budget_df = None
    if run_model:
        sim.write_simulation()
        success, _ = sim.run_simulation(silent=True)

        if not success:
            print("Model run failed!")
        else:
            head_file = gwf.output.head()
            heads = head_file.get_data()

            if return_budget and heads is not None:
                from model_io_utils import format_budget_summary
                budget_df = format_budget_summary(gwf, sim)

    # --- Restore parameters to pre-trial state ---
    if saved_k is not None:
        gwf.get_package('NPF').k.set_data(saved_k)
    if saved_rch is not None:
        gwf.get_package('RCHA').recharge.set_data(saved_rch)
    if saved_riv is not None:
        gwf.get_package('RIV').stress_period_data.set_data(saved_riv)

    if return_budget:
        return (heads, budget_df)
    return heads


def grid_search_calibration(
    sim,
    gwf_name: str,
    obs_gdf: gpd.GeoDataFrame,
    model_grid,
    k_range: Tuple[float, float, int] = (0.5, 2.0, 5),
    rch_range: Tuple[float, float, int] = (0.5, 2.0, 5),
    base_sim_path: Optional[str] = None
) -> pd.DataFrame:
    """
    Perform grid search over K and recharge multipliers.

    Parameters
    ----------
    sim : flopy.mf6.MFSimulation
        The simulation object
    gwf_name : str
        Name of GWF model
    obs_gdf : gpd.GeoDataFrame
        Observation data
    model_grid : VertexGrid
        The model grid
    k_range : tuple
        (min_mult, max_mult, n_steps) for K multiplier
    rch_range : tuple
        (min_mult, max_mult, n_steps) for recharge multiplier
    base_sim_path : str, optional
        Path to reload simulation between runs

    Returns
    -------
    pd.DataFrame
        Results with columns: k_mult, rch_mult, RMSE, ME, R2, NRMSE
    """
    import flopy

    k_mults = np.linspace(k_range[0], k_range[1], k_range[2])
    rch_mults = np.linspace(rch_range[0], rch_range[1], rch_range[2])

    results = []
    observed = obs_gdf['head_m'].values

    for k_mult in k_mults:
        for rch_mult in rch_mults:
            # Reload simulation for fresh parameters
            if base_sim_path is not None:
                sim = flopy.mf6.MFSimulation.load(sim_ws=base_sim_path)

            # Run trial
            heads = run_calibration_trial(
                sim, gwf_name,
                k_global_multiplier=k_mult,
                rch_multiplier=rch_mult
            )

            if heads is not None:
                simulated = extract_heads_at_observations(heads, obs_gdf, model_grid)
                valid = ~np.isnan(simulated)

                if valid.any():
                    metrics = calculate_calibration_metrics(
                        observed[valid], simulated[valid]
                    )
                    results.append({
                        'k_mult': k_mult,
                        'rch_mult': rch_mult,
                        **metrics
                    })

    return pd.DataFrame(results)


# =============================================================================
# TRANSPARENCY UTILITIES
# =============================================================================

def get_observation_summary(obs_gdf: gpd.GeoDataFrame) -> str:
    """
    Generate a summary of the observation dataset.

    Parameters
    ----------
    obs_gdf : gpd.GeoDataFrame
        The observation dataset

    Returns
    -------
    str
        Formatted summary text
    """
    total = len(obs_gdf)

    if 'is_synthetic' in obs_gdf.columns:
        n_real = (~obs_gdf['is_synthetic']).sum()
        n_synth = obs_gdf['is_synthetic'].sum()
    else:
        n_real = total
        n_synth = 0

    head_vals = obs_gdf['head_m'].round(2)

    lines = [
        "=" * 50,
        "OBSERVATION DATA SUMMARY",
        "=" * 50,
        f"Total observation points: {total}",
        f"  - Real (AWEL):   {n_real}",
        f"  - Synthetic:     {n_synth}",
        "",
        f"Head range: {head_vals.min():.2f} - {head_vals.max():.2f} m a.s.l.",
        f"Mean head:  {head_vals.mean():.2f} m a.s.l.",
        "=" * 50,
    ]

    if n_synth > 0:
        lines.insert(-1, "")
        lines.insert(-1, "Note: Synthetic observations are artificial data points")
        lines.insert(-1, "created for teaching purposes. They are clearly marked")
        lines.insert(-1, "with is_synthetic=True and shown as orange triangles.")

    return "\n".join(lines)
