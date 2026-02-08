# Notebook Refactoring Plan for course_2026

## Overview

This document guides the simplification of CASE_STUDY notebooks by extracting boilerplate code into `SUPPORT_REPO/src/` utilities. The goal is to make notebooks easier to follow while keeping essential learning content visible.

**Principles:**
- Notebooks focus on concepts, decisions, and interpretation
- Utilities handle data loading, plotting, and repetitive setup
- Students should understand *what* the code does, not every implementation detail
- Code students need to modify stays in notebooks

---

## Time Estimates & Content Structure

### Time Tracking
Each notebook should display an estimated completion time at the top:
```markdown
**Estimated time:** 45 minutes (core) + 30 minutes (advanced)
```

Track actual student times to refine estimates over time.

### Content Separation
Notebooks should clearly separate:

1. **Core content** (need to know)
   - Essential concepts for the modeling step
   - Required hands-on exercises
   - Must complete to proceed

2. **Advanced material** (optional)
   - Deeper theoretical background
   - Additional exercises
   - Performance optimizations
   - Marked with collapsible sections or "Advanced" headers

3. **Further reading** (reference)
   - Links to documentation
   - Academic references
   - Related topics not covered

### Target Time Budget (per notebook)
| Content Type | Target Time |
|--------------|-------------|
| Core content | 30-60 min |
| Advanced (optional) | 15-30 min |
| Total maximum | ~90 min |

---

## Model Scope

### Current Implementation: Steady-State Flow
- Primary focus for course_2026
- Full 10-step cycle for steady-state groundwater flow
- All core content supports steady-state

### Future/Optional: Transient Simulation
- **Priority:** Lower - advanced/optional material
- **Status:** Not yet implemented
- **Placement:** Advanced sections in relevant notebooks (4, 5, 6, 7)
- **Prerequisites:** Students complete steady-state first
- **Key additions needed:**
  - Time discretization setup
  - Storage parameters (Ss, Sy)
  - Time-varying boundary conditions
  - Temporal calibration/validation

---

## New Folder Structure

```
CASE_STUDY/
├── 0_introduction.ipynb              # Shared intro to the 10-step framework
│
├── flow/
│   ├── 1_model_goal.ipynb            # Was: 1_introduction.ipynb (split)
│   ├── 2_perceptual_model.ipynb
│   ├── 3_modflow_fundamentals.ipynb
│   ├── 4_model_implementation.ipynb
│   ├── 5_calibration.ipynb
│   ├── 6_validation.ipynb
│   ├── 7_sensitivity_uncertainty.ipynb
│   ├── 8_model_application.ipynb
│   ├── 9_documentation.ipynb
│   └── 10_communication.ipynb
│
├── transport/
│   ├── 1_model_goal.ipynb
│   ├── 2_perceptual_model.ipynb
│   ├── 3_gwt_fundamentals.ipynb
│   ├── 4_model_implementation.ipynb  # Was: 4b_transport_model_implementation.ipynb
│   ├── 5_calibration.ipynb
│   ├── 6_validation.ipynb
│   ├── 7_sensitivity_uncertainty.ipynb
│   ├── 8_model_application.ipynb
│   ├── 9_documentation.ipynb
│   └── 10_communication.ipynb
│
├── student_work/
│   └── ...
│
└── grading_scheme/
    └── ...
```

**Rationale:**
- Both tracks follow the same 10-step modeling methodology
- Students learn the framework once (notebook 0), apply it to flow (1-10), then transport (1-10)
- Clear separation makes navigation easier
- Transport notebooks can reference/build on corresponding flow notebooks

---

## Current State Analysis

### Flow Notebooks (to be moved to flow/)

| Notebook | Code Lines | Markdown Lines | Priority |
|----------|-----------|----------------|----------|
| 1_introduction → split into 0 + 1 | 23 | 462 | Medium |
| 2_perceptual_model | 653 | 298 | Medium |
| 3_modflow_fundamentals | 15 | 88 | Low |
| **4_model_implementation** | **2915** | 585 | **Critical** |
| **5_calibration** | **1563** | 462 | **High** |
| 6_validation | 930 | 265 | Medium |
| 7_sensitivity_uncertainty | 285 | 406 | Low |
| 8_model_application | 0 | 501 | None |
| 9_documentation | 0 | 368 | None |
| 10_communication | 0 | 336 | None |

### Transport Notebooks (to be created/moved to transport/)

| Notebook | Status | Notes |
|----------|--------|-------|
| 1_model_goal | To create | Transport-specific objectives |
| 2_perceptual_model | To create | Transport processes, sources |
| 3_gwt_fundamentals | To create | MODFLOW 6 GWT introduction |
| **4_model_implementation** | **Exists (was 4b)** | 1308 lines - needs refactoring |
| 5_calibration | To create | Concentration calibration |
| 6_validation | To create | Transport validation |
| 7_sensitivity_uncertainty | To create | Transport sensitivity |
| 8_model_application | To create | Scenario analysis |
| 9_documentation | To create | Transport-specific docs |
| 10_communication | To create | Results communication |

### Code Distribution by Category

#### Notebook 4 (Model Implementation) - 2915 lines
- Imports/inline functions: 972 lines
- Plotting: 994 lines
- Data loading: 414 lines
- Model setup: 334 lines
- Other: 201 lines

#### Notebook 5 (Calibration) - 1563 lines
- Imports/inline functions: 757 lines
- Model setup: 342 lines
- Plotting: 298 lines
- Data loading: 84 lines
- Other: 82 lines

#### Notebook 4b (Transport) - 1308 lines
- Model setup: 567 lines
- Plotting: 327 lines
- Imports: 262 lines
- Other: 152 lines

#### Notebook 6 (Validation) - 930 lines
- Plotting: 386 lines
- Imports: 253 lines
- Other: 161 lines
- Model setup: 108 lines
- Data loading: 22 lines

---

## Proposed Utility Modules

### New Modules to Create

#### `model_utils.py`
Purpose: MODFLOW 6 model handling, loading, and inspection

```python
# Proposed functions
def load_simulation(workspace: Path) -> flopy.mf6.MFSimulation
def load_gwf_model(workspace: Path, model_name: str) -> flopy.mf6.ModflowGwf
def get_heads(gwf_model) -> np.ndarray
def find_cell_for_point(modelgrid, x: float, y: float) -> tuple[int, int, int]
def get_water_balance(gwf_model) -> dict
def run_model(sim, silent: bool = True) -> tuple[bool, list]
```

#### `calibration_utils.py`
Purpose: Calibration metrics, observation handling, trial runs

```python
# Proposed functions
def calculate_metrics(observed: np.ndarray, simulated: np.ndarray) -> dict
    # Returns: RMSE, MAE, R², bias
def load_observation_wells(gw_timeseries_path: Path) -> pd.DataFrame
def map_wells_to_grid(wells_df: pd.DataFrame, modelgrid) -> pd.DataFrame
def run_calibration_trial(sim, params: dict) -> dict
def plot_observed_vs_simulated(obs: np.ndarray, sim: np.ndarray, ax=None)
def plot_residual_map(wells_df: pd.DataFrame, modelgrid, ax=None)
```

#### `transport_utils.py`
Purpose: MODFLOW 6 GWT model setup and visualization

```python
# Proposed functions
def create_gwt_model(sim, gwf_model, transport_params: dict) -> flopy.mf6.ModflowGwt
def get_concentrations(gwt_model) -> np.ndarray
def plot_concentration_profile(conc: np.ndarray, distance: np.ndarray, ax=None)
def plot_breakthrough_curve(conc_time: np.ndarray, times: np.ndarray, ax=None)
def analytical_advection_dispersion(x, t, v, D, C0) -> np.ndarray
```

### Existing Modules to Expand

#### `grid_utils.py` (exists)
Add:
```python
def create_rotated_grid(boundary_gdf, dx: float, dy: float, rotation: float)
def resample_dem_to_grid(dem_path: Path, modelgrid) -> np.ndarray
def get_active_cells_from_boundary(modelgrid, boundary_gdf) -> np.ndarray
```

#### `plot_utils.py` (exists)
Add:
```python
def plot_model_grid(modelgrid, ax=None, **kwargs)
def plot_heads_map(heads: np.ndarray, modelgrid, ax=None, **kwargs)
def plot_boundary_conditions(gwf_model, ax=None)
def plot_water_balance_pie(balance_dict: dict, ax=None)
```

#### `data_utils.py` (exists)
Add:
```python
def load_boundary_shapefile(name: str) -> gpd.GeoDataFrame
def load_parameter_zones(name: str) -> gpd.GeoDataFrame
def prepare_river_cells(river_gdf, modelgrid) -> pd.DataFrame
```

---

## Refactoring Plan by Notebook

### Phase 1: Notebook 4 (Model Implementation) - CRITICAL

**Target:** Reduce from ~2900 to ~800 code lines

**Extract to `grid_utils.py`:**
- [ ] Grid rotation and alignment logic
- [ ] DEM resampling to model grid
- [ ] Active cell determination from boundary

**Extract to `model_utils.py`:**
- [ ] MF6 simulation and GWF model creation boilerplate
- [ ] Package setup helpers (DIS, NPF, IC, CHD, RIV, WEL, RCH)

**Extract to `plot_utils.py`:**
- [ ] Grid visualization with boundary overlay
- [ ] Head distribution maps
- [ ] Cross-section plots

**Keep in notebook:**
- Conceptual decisions (grid size, layer structure)
- Boundary condition assignments (students modify these)
- Model execution and basic result inspection

---

### Phase 2: Notebook 5 (Calibration) - HIGH

**Target:** Reduce from ~1500 to ~500 code lines

**Extract to `calibration_utils.py`:**
- [ ] Metric calculation functions (RMSE, MAE, R², bias)
- [ ] Observation well loading and processing
- [ ] Well-to-grid cell mapping
- [ ] Calibration trial runner

**Extract to `plot_utils.py`:**
- [ ] Observed vs simulated scatter plot
- [ ] Residual map
- [ ] Calibration history plot

**Keep in notebook:**
- Calibration strategy discussion
- Parameter selection and bounds
- Results interpretation
- Manual adjustment decisions

---

### Phase 3: Notebook 4b (Transport) - HIGH

**Target:** Reduce from ~1300 to ~400 code lines

**Note:** This notebook will change significantly with MF6 migration (MT3DMS → GWT)

**Extract to `transport_utils.py`:**
- [ ] GWT model creation and package setup
- [ ] Analytical solution functions
- [ ] Concentration profile plotting
- [ ] Breakthrough curve plotting

**Keep in notebook:**
- Transport parameter selection
- Source term definition
- Comparison with analytical solutions
- Results interpretation

---

### Phase 4: Notebook 6 (Validation) - MEDIUM

**Target:** Reduce from ~900 to ~400 code lines

**Benefits from Phase 2 extractions** (shares code with calibration)

**Additional extractions to `calibration_utils.py`:**
- [ ] Validation metrics (same as calibration)
- [ ] Data adequacy assessment

**Extract to `plot_utils.py`:**
- [ ] Validation scatter plots
- [ ] Residual analysis plots

**Keep in notebook:**
- Validation philosophy discussion
- Honest assessment of data limitations
- Model status determination

---

### Phase 5: Notebook 2 (Perceptual Model) - MEDIUM

**Target:** Reduce from ~650 to ~300 code lines

**Most code already uses utilities, but can improve:**
- [ ] Consolidate climate data visualization
- [ ] Streamline river data loading

---

## Implementation Order

1. **Create new utility modules** with function stubs
2. **Refactor Notebook 4** (biggest impact)
3. **Refactor Notebook 5** (calibration utilities reused in 6)
4. **Refactor Notebook 6** (benefits from 5)
5. **Refactor Notebook 4b** (combined with MF6 migration)
6. **Refactor Notebook 2** (lower priority)

---

## Success Criteria

- [ ] No notebook exceeds 800 code lines
- [ ] All utilities have docstrings and type hints
- [ ] Notebooks run successfully after refactoring
- [ ] Student-modifiable code remains visible in notebooks
- [ ] group_0 template updated to use new utilities

---

## Notes

- MF6 migration and notebook refactoring can be done together for notebooks 4, 4b
- Test each refactored notebook with `0_diagnostics.ipynb` patterns
- Update `DEVELOPMENT.md` if new utility patterns emerge
