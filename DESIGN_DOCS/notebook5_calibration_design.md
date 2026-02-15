# Design Document: Notebook 5 - Model Calibration

**Status:** Implemented — PEST++ pilot-point calibration (not manual zone-based)
**Date:** 2026-02-14
**Depends on:** Notebook 4 (MODFLOW 6 model with DISV grid)

---

## 1. Overview

### 1.1 Purpose

Calibrate the MODFLOW 6 model built in notebook 4 using PEST++ with pilot points. The notebook teaches calibration concepts using real AWEL observation data supplemented with synthetic observation points for spatial coverage.

### 1.2 Key Change from Previous Version

The previous notebook 5 used MODFLOW-NWT with manual zone-based calibration. The implemented version uses:
- **MODFLOW 6** simulation framework with **DISV (Voronoi) grids**
- **PEST++ (pestpp-glm)** for automated parameter estimation
- **~25 pilot points** with kriging/IDW interpolation (not K zones)
- **Prior information** from a Cooper-Jacob pumping test analysis

### 1.3 Learning Objectives

By the end of this notebook, students will be able to:
1. **Assess** observation data coverage and identify spatial gaps
2. **Evaluate** a pumping test using the Cooper-Jacob straight-line method
3. **Calculate** calibration metrics (ME, MAE, RMSE, R², NRMSE)
4. **Explain** how PEST++ with pilot points estimates spatially varying parameters
5. **Interpret** a calibrated K field and the role of prior information
6. **Verify** calibration quality through water balance checks and residual analysis

---

## 2. Observation Data Strategy

### 2.1 Real Data: AWEL Monitoring Wells

**Source:** Canton Zurich groundwater monitoring network (AWEL)
**File:** `all_wells_long_format.csv`
**Coverage:** ~5-10 wells within model domain (to be verified)
**Time range:** 1970s-2024

**Limitations:**
- Few stations within the model domain
- Uneven spatial distribution
- Some wells may be outside active model cells

### 2.2 Synthetic Observation Points

> **Transparency Note:** To adequately demonstrate calibration methods, we supplement the real AWEL observations with synthetic (artificial) observation points. These are clearly marked as synthetic in all visualizations and data tables. The synthetic observations are generated from a "reference" model run and perturbed with realistic measurement noise.

**Rationale for synthetic data:**
1. Ensure adequate spatial coverage across the model domain
2. Provide observations in each hydraulic conductivity zone
3. Enable meaningful calibration exercises even with limited real data
4. Allow controlled demonstration of calibration concepts

**Synthetic observation design:**
- **Count:** 15-20 additional points
- **Distribution:** Stratified across K zones and near boundaries
- **Generation method:**
  1. Run model with "true" parameters (kept hidden from students initially)
  2. Extract heads at synthetic observation locations
  3. Add Gaussian noise (σ = 0.3 m, representing measurement uncertainty)
- **Labeling:** All synthetic points marked with `is_synthetic = True`

### 2.3 Combined Observation Dataset

| Field | Type | Description |
|-------|------|-------------|
| `obs_id` | str | Unique identifier (e.g., "AWEL_001" or "SYN_015") |
| `x` | float | Easting (LV95, EPSG:2056) |
| `y` | float | Northing (LV95, EPSG:2056) |
| `head_m` | float | Observed head (m a.s.l.) |
| `error_m` | float | Measurement uncertainty (m) |
| `is_synthetic` | bool | True for artificial observations |
| `zone` | str | K zone name (for analysis) |
| `weight` | float | Observation weight (1/error²) |

---

## 3. Calibration Approach

### 3.1 Parameters to Calibrate

| Parameter | Initial Value | Calibration Range | Method |
|-----------|---------------|-------------------|--------|
| K_zone1 (upstream) | 20 m/d | 10-40 m/d | Zone multiplier |
| K_zone2 (downstream) | 20 m/d | 5-25 m/d | Zone multiplier |
| K_zone3 (Hardhof) | 20 m/d | 20-50 m/d | Zone multiplier |
| Recharge | 0.0003 m/d | 0.0001-0.0005 m/d | Global multiplier |
| River conductance | Varies | 0.5x-2.0x | Global multiplier |

### 3.2 Calibration Strategy

**Phase 1: Manual Calibration (Primary Focus)**
- Trial-and-error parameter adjustment
- Visual interpretation of residual maps
- Systematic exploration using multiplier factors
- Emphasis on physical reasoning

**Phase 2: Guided Optimization (Optional/Advanced)**
- Introduction to `scipy.optimize.minimize`
- Single objective function (RMSE)
- Bounds-constrained optimization
- Comparison with manual results

### 3.3 Calibration Metrics

```python
def calculate_metrics(observed, simulated):
    """Calculate standard calibration metrics."""
    residuals = simulated - observed

    ME = np.mean(residuals)                    # Mean Error (bias)
    MAE = np.mean(np.abs(residuals))           # Mean Absolute Error
    RMSE = np.sqrt(np.mean(residuals**2))      # Root Mean Square Error
    NRMSE = RMSE / (observed.max() - observed.min()) * 100  # Normalized RMSE (%)

    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((observed - observed.mean())**2)
    R2 = 1 - (ss_res / ss_tot)                 # Coefficient of determination

    return {"ME": ME, "MAE": MAE, "RMSE": RMSE, "NRMSE": NRMSE, "R2": R2}
```

**Target criteria:**
- NRMSE < 10%
- R² > 0.9
- ME near zero (no systematic bias)

---

## 4. Notebook Structure

### Chapter 1: Introduction (~5 min)
- What is calibration and why it matters
- Overview of the Limmat Valley model from notebook 4
- Learning objectives

### Chapter 2: Loading Model and Observations (~10 min)
- 2.1 Load the MODFLOW 6 model from notebook 4
- 2.2 Load real AWEL observation data
- 2.3 Load synthetic observation points (with transparency note)
- 2.4 Visualize observation network on model grid
- **Checkpoint:** Verify observation count and spatial coverage

### Chapter 3: Initial Model Assessment (~10 min)
- 3.1 Run uncalibrated model
- 3.2 Extract simulated heads at observation points
- 3.3 Calculate initial calibration metrics
- 3.4 Create observed vs. simulated scatter plot
- 3.5 Map residuals spatially
- **Checkpoint:** Interpret initial RMSE and bias

### Chapter 4: Understanding Residual Patterns (~10 min)
- 4.1 What do residual patterns tell us?
- 4.2 Positive residuals (simulated > observed) → K too low or recharge too high
- 4.3 Negative residuals (simulated < observed) → K too high or recharge too low
- 4.4 Spatial clustering → zone-specific parameter issues
- **Exercise:** Identify which zone needs adjustment based on residual map

### Chapter 5: Manual Calibration (~15 min)
- 5.1 Define parameter multipliers
- 5.2 Calibration trial function
- 5.3 Systematic trials (grid search over K multipliers)
- 5.4 Record and compare results
- 5.5 Select best parameter set
- **Exercise:** Run calibration trials and find optimal multipliers
- **Checkpoint:** Achieve NRMSE < 10%

### Chapter 6: Calibration Results (~10 min)
- 6.1 Final calibrated parameter values
- 6.2 Comparison: initial vs. calibrated metrics
- 6.3 Scatter plot improvement
- 6.4 Residual map improvement
- 6.5 Water balance verification
- **Checkpoint:** Verify water balance closes (<1% error)

### Chapter 7: Non-Uniqueness and Equifinality (~10 min)
- 7.1 Multiple parameter combinations can give similar fit
- 7.2 Demonstration: K-Recharge trade-off
- 7.3 Implications for model predictions
- 7.4 Why physical plausibility matters
- **Exercise:** Find alternative parameter set with similar RMSE

### Chapter 8: Discussion and Best Practices (~5 min)
- 8.1 Limitations of manual calibration
- 8.2 When to use automatic calibration (PEST++)
- 8.3 Importance of validation (preview of notebook 6)
- 8.4 Key takeaways

### Chapter 9: Optional - Automatic Calibration Preview (~10 min, optional)
- 9.1 Introduction to scipy.optimize
- 9.2 Setting up objective function
- 9.3 Running bounded optimization
- 9.4 Comparing results with manual calibration
- 9.5 Pointers to PEST++ and pyEMU for advanced users

---

## 5. Technical Implementation

### 5.1 New Utilities Required

**In `model_io_utils.py`:**
```python
def load_observations_for_calibration(
    data_dir: Path,
    model_grid: flopy.discretization.VertexGrid,
    include_synthetic: bool = True
) -> gpd.GeoDataFrame:
    """Load and prepare observation data for calibration."""

def extract_heads_at_observations(
    head_array: np.ndarray,
    obs_gdf: gpd.GeoDataFrame,
    model_grid: flopy.discretization.VertexGrid
) -> np.ndarray:
    """Extract simulated heads at observation point locations."""
```

**In `calibration_utils.py` (new module):**
```python
def generate_synthetic_observations(
    model_grid: flopy.discretization.VertexGrid,
    true_heads: np.ndarray,
    n_points: int = 20,
    noise_std: float = 0.3,
    seed: int = 42
) -> gpd.GeoDataFrame:
    """Generate synthetic observation points with realistic noise."""

def calculate_calibration_metrics(
    observed: np.ndarray,
    simulated: np.ndarray
) -> dict:
    """Calculate ME, MAE, RMSE, NRMSE, R²."""

def plot_calibration_scatter(
    observed: np.ndarray,
    simulated: np.ndarray,
    title: str = "Observed vs Simulated Heads"
) -> plt.Figure:
    """Create scatter plot with 1:1 line and metrics annotation."""

def plot_residual_map(
    obs_gdf: gpd.GeoDataFrame,
    residuals: np.ndarray,
    model_grid: flopy.discretization.VertexGrid,
    title: str = "Spatial Residuals"
) -> plt.Figure:
    """Map residuals spatially with diverging colormap."""

def run_calibration_trial(
    sim: flopy.mf6.MFSimulation,
    k_multipliers: dict,
    rch_multiplier: float = 1.0,
    riv_multiplier: float = 1.0
) -> np.ndarray:
    """Run model with modified parameters and return heads."""
```

### 5.2 Synthetic Observation Generation

```python
def generate_synthetic_observations(grid, true_heads, n_points=20, noise_std=0.3, seed=42):
    """
    Generate synthetic observations distributed across the model domain.

    Strategy:
    1. Create stratified random points within active cells
    2. Ensure coverage of all K zones
    3. Avoid cells too close to boundaries
    4. Extract "true" heads and add measurement noise
    """
    np.random.seed(seed)

    # Get active cell centroids
    active_cells = np.where(idomain.flatten() > 0)[0]
    cell_centers = np.array([grid.get_cell_vertices(i) for i in active_cells])

    # Stratified sampling by zone
    selected_cells = stratified_sample(active_cells, zones, n_points)

    # Extract coordinates and true heads
    x = cell_centers[selected_cells, 0]
    y = cell_centers[selected_cells, 1]
    true_h = true_heads.flatten()[selected_cells]

    # Add realistic measurement noise
    observed_h = true_h + np.random.normal(0, noise_std, n_points)

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame({
        'obs_id': [f'SYN_{i:03d}' for i in range(n_points)],
        'head_m': observed_h,
        'true_head_m': true_h,  # Hidden during calibration exercise
        'error_m': noise_std,
        'is_synthetic': True,
        'geometry': [Point(xi, yi) for xi, yi in zip(x, y)]
    }, crs="EPSG:2056")

    return gdf
```

### 5.3 Checkpoints and Exercises

**Checkpoint definitions (for `tasks_data.py`):**
```python
TASK05_CHECKPOINTS = {
    "task05_checkpoint_1": {
        "description": "Count total observation points",
        "type": "numeric",
        "tolerance": 0
    },
    "task05_checkpoint_2": {
        "description": "Initial RMSE before calibration",
        "type": "numeric",
        "tolerance": 0.5  # Allow ±0.5 m
    },
    "task05_checkpoint_3": {
        "description": "Calibrated RMSE",
        "type": "numeric",
        "tolerance": 0.3,
        "target": "< 2.0 m"
    },
    "task05_checkpoint_4": {
        "description": "Water balance error",
        "type": "numeric",
        "tolerance": 0.5,
        "target": "< 1%"
    },
    "task05_checkpoint_5": {
        "description": "Identify parameter adjustment direction",
        "type": "multiple_choice",
        "question": "Based on the residual pattern showing positive residuals in Zone 1, what parameter adjustment would improve the fit?",
        "options": [
            "Increase K in Zone 1",
            "Decrease K in Zone 1",
            "Increase recharge everywhere",
            "Decrease river conductance"
        ],
        "correct": 0  # Increase K (positive residuals = heads too high = K too low)
    }
}
```

---

## 6. Data Files

### 6.1 Required Input Files

| File | Source | Description |
|------|--------|-------------|
| `notebook4_model/` | Notebook 4 output | Complete MF6 simulation |
| `all_wells_long_format.csv` | AWEL download | Real observation time series |
| `observation_wells.gpkg` | To be created | Well locations with metadata |

### 6.2 Generated Output Files

| File | Description |
|------|-------------|
| `calibration_observations.gpkg` | Combined real + synthetic observations |
| `calibration_results.csv` | Trial results log |
| `calibrated_model/` | Final calibrated model files |

---

## 7. Transparency About Synthetic Data

### 7.1 In-Notebook Disclosure

The notebook will include a prominent callout box:

```markdown
> **About the Observation Data**
>
> This notebook uses two types of observation data:
>
> 1. **Real observations** (marked `is_synthetic=False`): Groundwater levels from
>    the Canton Zurich monitoring network (AWEL). These are actual measurements
>    from the Limmat Valley.
>
> 2. **Synthetic observations** (marked `is_synthetic=True`): Artificial data points
>    we created to ensure adequate spatial coverage for demonstrating calibration
>    methods. These were generated by:
>    - Running the model with "true" parameter values
>    - Extracting heads at strategically placed locations
>    - Adding realistic measurement noise (±0.3 m)
>
> In professional practice, you would only use real observations. The synthetic
> points here serve an educational purpose: they allow us to demonstrate calibration
> concepts even when real data coverage is limited.
```

### 7.2 Visual Distinction

- Real observations: **blue circles**
- Synthetic observations: **orange triangles**
- All plots will include a legend distinguishing the two types

---

## 8. Timeline and Dependencies

### 8.1 Implementation Order

1. **Create `calibration_utils.py`** with core functions
2. **Process AWEL observation data** - extract wells within model domain
3. **Implement synthetic observation generator**
4. **Add checkpoints to `tasks_data.py`**
5. **Write notebook 5** following chapter structure
6. **Test end-to-end** calibration workflow
7. **Review and refine** based on testing

### 8.2 Dependencies

- Notebook 4 must be complete and produce a working MF6 model
- `disv_grid_utils.py` functions for grid operations
- `model_io_utils.py` for loading model and extracting results

---

## 9. Open Questions

1. **How many real AWEL wells** are actually within the model domain? Need to verify.
2. **K zone boundaries** - Are they defined in notebook 4, or do we need to add them?
3. **Should we include transient calibration** or keep it steady-state only?
4. **scipy.optimize section** - Required or truly optional?

---

## 10. Success Criteria

The notebook is complete when:
- [ ] Students can load and visualize observation data
- [ ] Calibration metrics are correctly calculated
- [ ] Manual calibration achieves NRMSE < 10%
- [ ] Synthetic data is clearly disclosed and visually distinguished
- [ ] All checkpoints pass with reference solutions
- [ ] Water balance verification succeeds
- [ ] Non-uniqueness concept is demonstrated
- [ ] Notebook runs end-to-end without errors
