# Notebook 4: Sections 6-8 Complete Design
## Model Implementation - Solver, Results, and Next Steps

**Date:** February 2026
**Target:** Sections 6, 7, 8 from Notebook 4 redesign
**Scope:** Complete markdown and code cell content for solver configuration, initial results interpretation, and transition to calibration

---

## Section 6: Solver and Run (Target: 7 min)

## Learning Objectives

By the end of Sections 6-8, you will be able to:
1. **Configure** the IMS solver with appropriate convergence tolerances
2. **Execute** a MODFLOW 6 simulation and interpret convergence status
3. **Evaluate** water balance closure as a model quality indicator
4. **Compare** simulated heads to observations and explain mismatch sources
5. **Determine** whether a river reach is gaining or losing from budget analysis

### 6.1 Solver Configuration (IMS - Iterative Model Solution)

**Markdown:**
```markdown
## 6. Solver and Run

Now that we have built the model structure—grid, parameters, and boundary conditions—we need to solve the groundwater flow equations. MODFLOW 6 uses the **IMS (Iterative Model Solution)** package, which employs Newton-Raphson iteration to solve the nonlinear flow equations. This is a significant advantage over older solvers (PCG, NWT) because it handles unconfined flow and thin/dry cells more robustly.

### 6.1 - Configuring the IMS Solver

The IMS solver controls numerical solution accuracy through two main parameters:

- **Convergence tolerance (HCLOSE)**: Stops when head changes between iterations are smaller than this value (typically 0.01 m for groundwater models)
- **Closure tolerance (RCLOSE)**: Stops when the residual (imbalance in flow equations) is smaller than this value (typically 0.1 m³/day)

For our model:
- We use the default IMS settings with **HCLOSE = 0.01 m** and **RCLOSE = 0.1 m³/day**
- These are conservative (tight) tolerances that ensure solution accuracy without excessive computation
- For production models, you would tune these based on model complexity and available compute time

The IMS solver uses Newton-Raphson iteration, which:
1. Starts with initial heads (from initial conditions or previous solution)
2. Computes flow imbalances at each cell
3. Adjusts heads to reduce imbalances
4. Repeats until both HCLOSE and RCLOSE are satisfied

**UNDERSTAND THIS:** Newton-Raphson converges faster than older methods because it accounts for how conductivity changes with head in unconfined aquifers.

```

### 6.2 Output Control

**Markdown:**
```markdown
### 6.2 - Output Control (OC)

The **OC (Output Control)** package specifies what MODFLOW saves to disk:
- Head arrays (binary .hds file) - used to visualize water table
- Budget data (.cbb file) - used to compute water balance and track flows
- Concentration data (for transport models, not used here)

We configure OC to save heads and budget at the end of the steady-state simulation. For our analysis, we need:
- **Heads** to compare against observations
- **Budget** to calculate water balance error

```

### 6.3 Prediction Exercise

**Markdown:**
```markdown
### 6.3 - Prediction Exercise (Before Running)

Before we run the simulation, let's engage your predictive thinking. We have observation wells at three locations where measured groundwater heads are available. Based on your understanding of:
- The aquifer geometry (model top and bottom)
- The boundary conditions (constant head, rivers, recharge)
- The hydraulic conductivity distribution (zones)

**Make predictions** for the simulated head at three observation wells. Later, after running the model, we'll compare your predictions to the actual results.

The observation well locations and measured heads are:
1. **Well OW-01** (upstream, south): Measured head = 420.5 m a.s.l. → Your prediction: ?
2. **Well OW-02** (mid-valley, center): Measured head = 409.3 m a.s.l. → Your prediction: ?
3. **Well OW-03** (downstream, north): Measured head = 398.8 m a.s.l. → Your prediction: ?

Write your predictions in the cell below, then we'll run the model and see how close you were.

> **Hint:** Think about the hydraulic gradients we identified in the perceptual model (Notebook 2). The groundwater generally flows from high elevations (south) to low elevations (west/north). Your predictions should reflect this trend.

```

**Code:**
```python
# EXERCISE: Make your predictions before running the model
# Fill in your estimated head values (in meters a.s.l.)

prediction_ow01 = ____  # Well OW-01 prediction (m a.s.l.)
prediction_ow02 = ____  # Well OW-02 prediction (m a.s.l.)
prediction_ow03 = ____  # Well OW-03 prediction (m a.s.l.)

print("Your predictions:")
print(f"  OW-01: {prediction_ow01} m a.s.l.")
print(f"  OW-02: {prediction_ow02} m a.s.l.")
print(f"  OW-03: {prediction_ow03} m a.s.l.")
print("\nNote: These are your initial estimates.")
print("After running the model, we'll see how well you predicted!")
```

### 6.4 Run Simulation

**Markdown:**
```markdown
### 6.4 - Run the Simulation

Now we run MODFLOW 6 to solve the groundwater flow equations. This typically takes 2-10 seconds on a standard computer for a ~5000-cell model.

During execution, you'll see messages indicating:
- **Stress period number** and **time step** (for steady-state: stress period 1, time step 1 (Python uses 0-based indexing for array access))
- **Iteration count** and convergence information
- **Solver status** ("Converged" = success, "Failed to converge" = check boundary conditions)

```

**Code:**
```python
# [UNDERSTAND THIS: Running a MODFLOW 6 simulation]

print("=" * 70)
print("Running MODFLOW 6 groundwater flow simulation...")
print("=" * 70)

# Create simulation object (if not already created)
# Assuming gwf and sim objects are defined in previous section

try:
    sim.write_simulation()
    print("\nSimulation files written successfully.")
    print(f"Working directory: {sim.sim_ws}")

    # Run the model
    success, buff = sim.run_simulation(silent=False)

    if success:
        print("\n" + "=" * 70)
        print("SUCCESS: Model converged!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("WARNING: Model did not converge.")
        print("This typically indicates a problem with boundary conditions")
        print("or solver parameters. Check the list file (.lst) for details.")
        print("=" * 70)

except Exception as e:
    print(f"Error running simulation: {e}")
    print("\nCommon issues:")
    print("1. Check that all boundary conditions are properly assigned")
    print("2. Verify active domain (IDOMAIN) is set correctly")
    print("3. Ensure no cells are isolated or have undefined properties")
```

### 6.5 Check Convergence

**Markdown:**
```markdown
### 6.5 - Check Convergence and Simulation Status

MODFLOW 6 outputs convergence information to a **.lst (list) file**. We can examine this file to confirm the solver converged and to see iteration details.

Key indicators of a successful solution:
- Convergence achieved within acceptable iterations (typically < 50 for steady-state)
- No warnings about dry cells or inactive areas
- Final residual is below RCLOSE tolerance

```

**Code:**
```python
# [BLACK BOX: Read convergence information from list file]

def check_model_convergence(sim):
    """
    Extract convergence summary from MODFLOW 6 list file.
    Returns convergence status and iteration count.
    """
    lst_file = sim.sim_ws / f"{sim.name}.lst"

    if not lst_file.exists():
        print("List file not found. Simulation may not have run.")
        return False, 0

    with open(lst_file, 'r') as f:
        content = f.read()

    # Look for convergence message
    converged = "convergence" in content.lower() or "solution converged" in content.lower()

    # Count iterations
    iteration_count = content.count("iter")

    return converged, iteration_count

# Check convergence
converged, iterations = check_model_convergence(sim)

if converged:
    print(f"Model Convergence Status: SUCCESS")
    print(f"Number of iterations: {iterations}")
    print("\nThe solver found a solution that satisfies convergence criteria.")
else:
    print(f"Model Convergence Status: CHECK LIST FILE")
    print(f"Solution status uncertain. Review {sim.sim_ws / f'{sim.name}.lst'}")
```

### 6.6 Compare Predictions to Results

**Markdown:**
```markdown
### 6.6 - Compare Your Predictions to Simulation Results

Now let's see how well your predictions matched the actual simulated heads. This comparison helps build intuition about aquifer behavior and highlights the importance of rigorous modeling.

```

**Code:**
```python
# [BLACK BOX: Extract simulated heads at observation well locations]

import numpy as np

def get_heads_at_observation_wells(gwf, modelgrid, observation_coords):
    """
    Extract simulated heads at specified observation well locations.

    Parameters:
        gwf: flopy.mf6.ModflowGwf object
        modelgrid: flopy.discretization grid object
        observation_coords: dict with well_name -> (x, y) tuples

    Returns:
        dict with well_name -> simulated_head values
    """
    # Load head file using FloPy's output interface
    head_obj = gwf.output.head()

    # Get final time step (steady-state: uses last timestep by default)
    heads = head_obj.get_data()  # Returns array [layer, ncpl] for DISV or [layer, row, col] for structured

    results = {}

    for well_name, (x, y) in observation_coords.items():
        try:
            # Find cell containing coordinate
            # For DISV: returns cell_id directly
            # For structured: returns (row, col)
            cell_info = modelgrid.intersect(x, y)

            # Handle both DISV and structured grids
            if isinstance(cell_info, (tuple, list)):
                # Structured grid: (row, col)
                i, j = cell_info
                simulated_head = heads[0, i, j]  # [layer, row, col]
            else:
                # DISV grid: cell_id (2D indexing: nlay, ncpl)
                cell_id = cell_info
                simulated_head = heads[0, cell_id]  # [layer, cell_id]

            results[well_name] = simulated_head
        except Exception as e:
            print(f"Warning: Could not extract head for {well_name}: {e}")
            results[well_name] = np.nan

    return results


# Define observation well coordinates (from preprocessed data)
observation_wells = {
    'OW-01': (2683400, 1249300),  # (easting, northing in local coordinate system)
    'OW-02': (2682100, 1250500),
    'OW-03': (2680800, 1251200),
}

# Get simulated heads
simulated_heads = get_heads_at_observation_wells(gwf, modelgrid, observation_wells)

# Compare predictions to results
print("=" * 70)
print("PREDICTION VS. SIMULATION RESULTS")
print("=" * 70)
print()

prediction_data = {
    'OW-01': prediction_ow01,
    'OW-02': prediction_ow02,
    'OW-03': prediction_ow03,
}

differences = {}
for well_name in ['OW-01', 'OW-02', 'OW-03']:
    pred = prediction_data[well_name]
    sim = simulated_heads[well_name]
    diff = abs(pred - sim)
    differences[well_name] = diff

    print(f"{well_name}:")
    print(f"  Your prediction:    {pred:7.2f} m a.s.l.")
    print(f"  Simulated head:     {sim:7.2f} m a.s.l.")
    print(f"  Difference:         {diff:7.2f} m")
    print()

mean_error = np.mean(list(differences.values()))
print(f"Mean absolute error: {mean_error:.2f} m")

if mean_error < 0.5:
    print("Excellent! Your intuition about the aquifer flow is strong.")
elif mean_error < 2.0:
    print("Good! You captured the major trends. Note areas where your")
    print("predictions differed - these reveal complexities in the model.")
else:
    print("No worries if your predictions were off. Groundwater systems")
    print("are complex! This is why we use models to quantify behavior.")
```

---

## Section 7: Initial Results (Target: 7 min)

### 7.1 Head Distribution Map

**Markdown:**
```markdown
## 7. Initial Results

We now examine the simulation output to understand the initial groundwater flow pattern. **Important:** Remember that this is an **uncalibrated model** using initial parameter estimates from literature. The results will show mismatch with observations, which motivates the calibration in Notebook 5.

### 7.1 - Head Distribution Map on DISV Grid

The primary output of a steady-state groundwater model is the **head distribution** – the water table elevation across the model domain. This map shows us:
- Flow directions (perpendicular to head contours, from high to low head). Note: This applies to isotropic aquifers. In anisotropic aquifers, flow deflects toward the principal direction of maximum conductivity.
- Areas of high and low groundwater elevation
- Boundary effects (constant-head boundaries create gradients)
- Influence of sources/sinks (rivers, recharge, pumping)

```

**Code:**
```python
# [UNDERSTAND THIS: Visualizing model results on DISV grids]

import matplotlib.pyplot as plt
import numpy as np

def plot_head_distribution(gwf, modelgrid, boundary_gdf=None, title="Simulated Groundwater Heads"):
    """
    Create a map of simulated heads on DISV or structured grid.

    Parameters:
        gwf: flopy.mf6.ModflowGwf object
        modelgrid: flopy.discretization grid object
        boundary_gdf: Optional GeoDataFrame with model boundary polygon
        title: Plot title

    Returns:
        fig, ax: matplotlib figure and axes
    """
    from flopy.plot import PlotMapView

    # Load head file using FloPy's output interface
    head_obj = gwf.output.head()
    head_data = head_obj.get_data()  # Final time step (default is last)

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 10))

    # Extract 2D head array (single layer model)
    # For DISV: head_data shape is [nlay, ncpl]
    head_2d = head_data[0, :]  # [layer, cells]

    # Plot using PlotMapView for proper DISV grid rendering
    pmv = PlotMapView(model=gwf, ax=ax)
    pc = pmv.plot_array(head_2d, cmap='viridis', alpha=0.9)

    # Add colorbar
    cbar = plt.colorbar(pc, ax=ax, label='Head (m a.s.l.)', shrink=0.8)

    # Overlay boundary polygon if provided
    if boundary_gdf is not None:
        try:
            boundary_gdf.boundary.plot(ax=ax, edgecolor='black', linewidth=2.5, label='Model boundary')
            ax.legend(loc='upper right')
        except Exception as e:
            print(f"Warning: Could not plot boundary: {e}")

    # Labels and title
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Easting (m)', fontsize=11)
    ax.set_ylabel('Northing (m)', fontsize=11)
    ax.set_aspect('equal')

    plt.tight_layout()
    return fig, ax


# Create and display head distribution map
fig, ax = plot_head_distribution(gwf, modelgrid, boundary_gdf=boundary_gdf,
                                  title="Simulated Groundwater Heads - Uncalibrated Model")
plt.show()

print("Head Distribution Summary:")
print(f"  Minimum head: {head_data.min():.2f} m a.s.l.")
print(f"  Maximum head: {head_data.max():.2f} m a.s.l.")
print(f"  Head range: {head_data.max() - head_data.min():.2f} m")
print("\nInterpretation:")
print("  The groundwater table is highest in the south-east (upstream)")
print("  and decreases toward the west (downstream), consistent with")
print("  general flow direction identified in the perceptual model.")
```

### 7.2 Water Balance Summary

**Markdown:**
```markdown
### 7.2 - Water Balance Summary (Budget Components)

The water balance is a fundamental check on model correctness. MODFLOW calculates volumetric flow for each boundary condition type (rivers, wells, recharge, etc.) and compares total inflows to total outflows.

The conservation of mass for steady-state groundwater flow:

$$\sum Q_{in} - \sum Q_{out} = 0$$

The budget error percentage is:
$$\epsilon_{balance} = \frac{|Q_{in} - Q_{out}|}{Q_{in}} \times 100\%$$

For steady-state models: **Inflows = Outflows** (no change in storage, $\Delta S = 0$)

> **Common Misconception:** A low water balance error (e.g., < 0.1%) does NOT mean the model is correct or calibrated. It only means that the numerical solution is internally consistent. A model can have perfect mass balance but still produce heads that are completely wrong compared to observations. Water balance closure is a necessary but not sufficient condition for model quality.

The budget shows:
- **Positive values** = water entering the aquifer (source)
- **Negative values** = water leaving the aquifer (sink)
- **Imbalance** = mass balance error (should be < 0.1% for properly configured models)

**UNDERSTAND THIS: Budget Components**
- **CHD (Constant Head)**: Fixed-head boundary – can flow either way
- **RIV (River)**: Exchanges water based on head difference
- **WEL (Well)**: Pumping (negative) and injection (positive)
- **RCH (Recharge)**: Areal recharge from precipitation and infiltration

```

**Code:**
```python
# [BLACK BOX: Extract and format water balance from MODFLOW 6 budget file]

import pandas as pd
import numpy as np

def format_budget_summary(gwf, verbose=True):
    """
    Extract water balance summary from MODFLOW 6 budget file.

    Parameters:
        gwf: flopy.mf6.ModflowGwf object
        verbose: If True, print detailed output

    Returns:
        dict with package flows and summary statistics
    """
    # Load budget file using FloPy's output interface
    bud_obj = gwf.output.budget()

    # Get available record names from the budget file
    available_records = bud_obj.get_unique_record_names()

    flows = {}

    for record_name in available_records:
        try:
            # Extract budget data for this record
            data = bud_obj.get_data(text=record_name)
            if data is not None and len(data) > 0:
                # Get last timestep data
                record_data = data[-1]
                # Sum all flows in this record
                if hasattr(record_data, 'dtype') and 'q' in record_data.dtype.names:
                    total_flow = np.sum(record_data['q'])
                else:
                    total_flow = np.sum(record_data)
                # Clean up record name for display
                clean_name = record_name.decode().strip() if isinstance(record_name, bytes) else record_name.strip()
                flows[clean_name] = total_flow
        except:
            # Record not accessible
            pass

    return flows


# Get budget summary
budget_summary = format_budget_summary(gwf, verbose=False)

# Calculate totals
inflows = sum([v for k, v in budget_summary.items() if v > 0])
outflows = abs(sum([v for k, v in budget_summary.items() if v < 0]))
imbalance = inflows - outflows
error_percent = (imbalance / inflows) * 100 if inflows > 0 else 0

# Display formatted table
print("=" * 80)
print("WATER BALANCE SUMMARY (Steady-State Model)")
print("=" * 80)
print()
print(f"{'Package':<20} {'Flow (m³/day)':<20} {'% of Inflow':<15}")
print("-" * 80)

for pkg, flow in budget_summary.items():
    pct = (abs(flow) / inflows) * 100 if inflows > 0 else 0
    if flow > 0:
        print(f"{pkg:<20} {flow:>15,.0f}  {pct:>10.1f}%  (inflow)")
    else:
        print(f"{pkg:<20} {flow:>15,.0f}  {pct:>10.1f}%  (outflow)")

print("-" * 80)
print(f"{'INFLOWS':<20} {inflows:>15,.0f}")
print(f"{'OUTFLOWS':<20} {outflows:>15,.0f}")
print(f"{'IMBALANCE':<20} {imbalance:>15,.0f}")
print(f"{'Mass Balance Error':<20} {error_percent:>10.2f}%")
print("=" * 80)

if abs(error_percent) < 0.1:
    print("\nExcellent! Mass balance closes to < 0.1%")
elif abs(error_percent) < 1.0:
    print("\nGood! Mass balance error is acceptable (< 1%)")
else:
    print("\nWarning: Mass balance error > 1%. Check boundary conditions.")
```

### 7.3 Checkpoint: Water Balance Error

**Markdown:**
```markdown
### 7.3 - Checkpoint: Water Balance Error

Based on your simulation results, determine the water balance error percentage.

```

**Code:**
```python
# Checkpoint: Calculate mass balance error from your model
check_task_with_solution("task04_checkpoint_4")
```

### 7.4 Simulated vs. Observed Heads

**Markdown:**
```markdown
### 7.4 - Comparing Simulated vs. Observed Heads

To assess model quality, we compare **simulated heads** (from the model) to **observed heads** (measured in the field at observation wells).

For an uncalibrated model with initial parameter estimates, we expect some mismatch. This mismatch motivates **calibration** (Notebook 5), where we adjust parameters to minimize the difference.

```

**Code:**
```python
# [UNDERSTAND THIS: Comparing model to observations]

# Load observed head data (from preprocessed data file)
obs_data = pd.read_csv("_SUPPORT/processed_data/observation_data.csv")

# Extract simulated heads at observation well locations
simulated_at_obs = {}
for idx, row in obs_data.iterrows():
    well_id = row['well_id']
    x, y = row['easting'], row['northing']

    # Find cell and get simulated head
    # [Implementation depends on specific DISV grid setup]
    cell_id = modelgrid.intersect(x, y)
    simulated_head = head_data[cell_id]
    simulated_at_obs[well_id] = simulated_head

# Create comparison DataFrame
comparison = pd.DataFrame({
    'Well ID': obs_data['well_id'],
    'Observed Head (m)': obs_data['head_measured'],
    'Simulated Head (m)': [simulated_at_obs[w] for w in obs_data['well_id']],
})

comparison['Residual (m)'] = comparison['Observed Head (m)'] - comparison['Simulated Head (m)']
comparison['Absolute Error (m)'] = abs(comparison['Residual (m)'])

# > **Common Misconception:** Residuals are NOT the same as model error.
# > A residual is the difference between observed and simulated values at a specific location.
# > Model error includes conceptual uncertainty, parameter uncertainty, and measurement error.
# > Small residuals do not guarantee the model is "correct" - they only indicate
# > the model reproduces observations at those specific points. The model may still
# > be wrong in areas without observations (interpolation vs. extrapolation).

print("=" * 90)
print("SIMULATED vs. OBSERVED HEADS")
print("=" * 90)
print(comparison.to_string(index=False))
print("=" * 90)

mae = comparison['Absolute Error (m)'].mean()
rmse = np.sqrt((comparison['Residual (m)']**2).mean())

print(f"\nMean Absolute Error: {mae:.3f} m")
print(f"RMSE (Root Mean Square Error): {rmse:.3f} m")
print("\nInterpretation:")
print("This uncalibrated model shows significant mismatch with observations.")
print("This is EXPECTED - we used literature values for K and estimated river")
print("conductances. Notebook 5 will adjust these parameters to minimize this")
print("mismatch through automatic calibration.")
```

### 7.5 Conceptual Question: Gaining vs. Losing River

**Markdown:**
```markdown
### 7.5 - Conceptual Question: River Gaining or Losing?

Based on your simulation results, answer this key conceptual question:

> **Is the Limmat River gaining or losing water from the aquifer in the model area? How can you tell from the water balance budget?**

The river-aquifer exchange is governed by:
$$Q_{riv} = C_{riv} \cdot (h_{riv} - h_{aquifer})$$

where:
- $C_{riv}$ = river conductance (m²/day)
- $h_{riv}$ = river stage (m)
- $h_{aquifer}$ = simulated head in the aquifer cell (m)

If $h_{aquifer} > h_{riv}$: water flows FROM aquifer TO river (gaining stream)
If $h_{aquifer} < h_{riv}$: water flows FROM river TO aquifer (losing stream)

To answer this, look at:
1. **Budget output**: Check the RIV (River) package flow. If negative (outflow from aquifer), the river is gaining. If positive (inflow to aquifer), the river is losing.
2. **Head map**: Compare the simulated head at river cells to the specified river stage in the boundary condition data.
3. **Physical interpretation**: Where heads are above the river stage, groundwater flows toward and into the river (gaining stream).

```

**Code:**
```python
# Checkpoint: Conceptual question about river-aquifer interaction
check_task_with_solution("task04_checkpoint_5")
```

### 7.6 Discussion: Uncalibrated Model

**Markdown:**
```markdown
### 7.6 - Why the Mismatch? Understanding Uncalibrated Models

The comparison in Section 7.4 shows that our simulated heads don't match observations well. **This is expected and informative.** Here's why:

**Why mismatch occurs:**
1. **Hydraulic conductivity (K)** - We used literature values (15-40 m/day), which are rough estimates for the Limmat Valley glaciofluvial gravels
2. **River conductance** - We estimated based on clogging layer properties; actual values vary by an order of magnitude (Doppler et al. 2007)
3. **Recharge rate** - We assumed 10% of precipitation; actual recharge varies with land use, infiltration infrastructure
4. **Model geometry** - We simplified aquifer thickness and top elevation; reality is more complex

**What calibration does (Notebook 5):**
- Systematically adjusts K, river conductance, and recharge
- Minimizes the difference between simulated and observed heads
- Constrains previously uncertain parameters (especially Limmat conductance)
- Quantifies remaining uncertainty (equifinality)

This demonstrates a fundamental principle: **Models are hypotheses to be tested against data, not perfect representations of reality.**

```

### 7.7 Optional: Detailed Output File Analysis

**Markdown:**
```markdown
<details>
<summary><strong>Optional Deep Dive: Output File Structure and Analysis</strong></summary>

MODFLOW 6 produces several output files that contain detailed model results. Understanding these files helps when debugging model issues or extracting specific results.

**Main output files:**

1. **Heads (.hds file)** - Binary file containing head values for every active cell at each time step
   - Accessed via `flopy.utils.HeadFile`
   - Can be very large for multi-layer models or transient simulations
   - Stored in scientific notation to save space

2. **Budget (.cbb file)** - Binary file containing flow terms for each package (RIV, WEL, RCH, etc.)
   - Accessed via `flopy.utils.CellBudgetFile`
   - Used to compute water balance summaries
   - Essential for interpretation of model results

3. **List file (.lst file)** - Text file with convergence information, warnings, and execution summary
   - Readable with any text editor
   - First place to look if model fails to converge
   - Contains iteration counts, residuals, and final convergence status

4. **Grid file (.grb file)** - MODFLOW 6 binary grid file (unstructured grids)
   - Stores DISV cell geometry (vertices, cell face areas)
   - Used by post-processors to visualize on correct grid cells

**Accessing output files programmatically:**

```python
# Read entire head array
from flopy.utils import HeadFile
head_file = HeadFile('model/model.hds')
heads_all = head_file.get_alldata()  # Returns 3D array [timestep, layer, cell]
heads_final = head_file.get_data(totim=0.0)  # Returns final time step

# Read specific budget term
from flopy.utils import CellBudgetFile
budget_file = CellBudgetFile('model/model.cbb')
river_flow = budget_file.get_data(text='  RIV', totim=0.0)  # Note the spacing!
```

For detailed information on output file formats, see the [MODFLOW 6 I/O documentation](https://water.usgs.gov/water-resources/software/MODFLOW-6/).

</details>

```

---

## Section 8: Summary and Next Steps (Target: 2 min)

### 8.1 Key Takeaways

**Markdown:**
```markdown
## 8. Summary and Next Steps

Congratulations! You have successfully implemented a complete groundwater flow model for the Limmat Valley aquifer using MODFLOW 6 and FloPy.

### 8.1 - Key Takeaways

You've learned that:

**Model Implementation:**
- MODFLOW 6 with unstructured (DISV) grids can handle complex aquifer geometries flexibly
- Boundary conditions (CHD, RIV, WEL, RCH) translate hydrogeological understanding into numerical form
- The IMS solver robustly handles nonlinear problems (unconfined flow) that caused issues in older software

**Interpretation:**
- Water balance closure (< 0.1% error) indicates correct boundary condition assignment
- Mismatch between simulated and observed heads reveals which parameters need calibration
- River-aquifer interaction dominates the flow budget in valley aquifers

**Limitations of Initial Estimates:**
- Literature values for K carry ±50% to ×10 uncertainty, depending on source
- River leakage coefficients can vary by orders of magnitude along complex reaches
- Recharge varies with land use and infrastructure, not just climate

### 8.2 - Why Calibration Is Essential

This uncalibrated model reveals the key limitation of forward modeling: we can build a physically reasonable model with literature values, but it may not match observations.

The mismatch you see is **not a failure**—it's diagnostic information. It tells us which parameters are most important:
- The difference between simulated and observed heads directly reveals errors in K or river conductance
- Systematic biases (e.g., simulated heads consistently too high in one region) point to missing processes or poorly estimated parameters

**Notebook 5 (Calibration)** will:
1. Define an objective function (minimize sum of squared residuals at observations)
2. Use automatic optimization to adjust K values and river conductances
3. Demonstrate how uncertainty constrains predictions
4. Show trade-offs between parameters (equifinality)

```

### 8.3 Reflection Prompt

**Markdown:**
```markdown
### 8.3 - Reflection Prompt

Before moving to Notebook 5, take a moment to reflect:

> **What was the most challenging part of this notebook for you?**
>
> - Was it understanding DISV grid concepts?
> - Configuring boundary conditions from geometries?
> - Interpreting the budget and water balance?
> - Something else?
>
> Write a brief note (even just a sentence) about what you found difficult and why. This reflection helps you identify knowledge gaps before moving to calibration.

```

### 8.4 Save Simulation

**Markdown:**
```markdown
### 8.4 - Save the Simulation

Before moving to Notebook 5, we save the current simulation structure. Notebook 5 will load this simulation and perform automatic parameter estimation (calibration).

```

**Code:**
```python
# [BLACK BOX: Save simulation for use in Notebook 5]

import pickle

# Define path for saved simulation
sim_save_path = Path("_SUPPORT/model_checkpoints/notebook4_uncalibrated_sim.pkl")
sim_save_path.parent.mkdir(parents=True, exist_ok=True)

try:
    # Save the simulation object
    with open(sim_save_path, 'wb') as f:
        pickle.dump(sim, f)

    print(f"Simulation saved to: {sim_save_path}")
    print("\nNotebook 5 will load this simulation and perform calibration.")

except Exception as e:
    print(f"Error saving simulation: {e}")
    print("You can still proceed to Notebook 5, but manual setup will be required.")
```

### 8.5 Preview: Next Steps with Notebook 5

**Markdown:**
```markdown
### 8.5 - What Comes Next: Notebook 5 (Calibration)

You now have a **working groundwater model** with initial parameter estimates. Notebook 5 takes this model to the next level through calibration.

**In Notebook 5, you will:**

1. **Load this uncalibrated simulation** from the checkpoint
2. **Define observation data** - groundwater head measurements at monitoring wells (you've seen these in the comparison plots above)
3. **Define an objective function** - sum of squared residuals between simulated and observed heads
4. **Run automatic calibration** using gradient-based optimization (PEST_HP or similar)
5. **Examine parameter changes** - how much did K and river conductance shift?
6. **Assess parameter uncertainty** - can different parameter sets fit the observations equally well? (equifinality)
7. **Validate the calibrated model** against a held-out dataset

**Key insights you'll gain:**
- Calibration is an **inverse problem**: given observations, what parameters best explain them?
- There may be multiple parameter sets that fit observations equally well (equifinality problem)
- Calibration typically reveals that some parameters are **insensitive** - the model is weakly constrained by the available observations

---

> **Navigation:** [< Notebook 3: MODFLOW Fundamentals](3_modflow_fundamentals.ipynb) | [Notebook 5: Calibration >](5_calibration.ipynb)

```

---

## Implementation Notes

### Code Labels

Throughout Sections 6-8, use consistent labeling:

- `[BLACK BOX]` - Infrastructure code (I/O, file operations, formatting) students don't need to understand
  - Example: reading budget files, extracting specific data from binary output

- `[UNDERSTAND THIS]` - Conceptual code showing MODFLOW principles
  - Example: how to set up IMS convergence parameters, how to compare predictions to results

### Style Consistency

- Follow Notebook 2 markdown style: clear headings, inline code formatting, conceptual questions in blockquotes
- No emojis in section headers or emphasis markers
- Use `>` blockquotes for emphasis, not bold formatting where not necessary
- Code cells have brief descriptions before major operations

### Exercise Format

The prediction exercise (Section 6.3) uses fill-in-the-blank (`____`) placeholders. Students must provide numeric values before proceeding. This engages higher-order thinking before seeing results.

### Checkpoint Integration

Two checkpoints in this design use the `check_task_with_solution()` framework:
- **task04_checkpoint_4**: Water balance error (%)
- **task04_checkpoint_5**: River gaining/losing (multiple choice)

Add these to `tasks_data.py` with tolerance ranges and solution explanations.

### Optional Content

Detailed output file analysis (Section 7.7) is marked as `<details>` collapsible section. This allows interested students to explore deeper while keeping core content focused.

---

## Timing Estimate

Based on design:
- **Section 6 (Solver and Run)**: 2 min intro + 3-4 min execution + 1-2 min review = 6-7 min
- **Section 7 (Results)**: 1 min head map + 2 min budget + 1 min checkpoint + 2 min comparison + 1 min river question = 7 min
- **Section 8 (Summary)**: 1 min takeaways + 0.5 min calibration preview + 0.5 min save + 0 min reflection (async) = 2 min

**Total: ~16 min** (slightly over target due to practical model run time; can be reduced by pre-running model and loading results)

---

## Prerequisite Knowledge

Students reaching this section should understand from previous notebooks:
- MODFLOW 6 package concepts (NPF, RCH, RIV, WEL, CHD, IMS, OC)
- Grid structure and active domain (IDOMAIN)
- Boundary condition types and when to use them
- Basic water balance concept and units

---
