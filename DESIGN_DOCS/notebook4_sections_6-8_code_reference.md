# Notebook 4: Sections 6-8 Code Reference
## Complete, Copy-Paste Ready Code Cells

---

## Section 6: Solver and Run

### Cell 6.1: Solver Configuration (Markdown Only)

See design document - covers IMS convergence criteria.

---

### Cell 6.2: Output Control (Markdown Only)

See design document - covers OC package settings.

---

### Cell 6.3: Prediction Exercise (Code)

```python
# EXERCISE: Make your predictions before running the model
# Fill in your estimated head values (in meters a.s.l.)
# Hint: Think about gradients from Notebook 2 - flow goes from high (south) to low (west)

prediction_ow01 = ____  # Well OW-01 upstream (m a.s.l.)
prediction_ow02 = ____  # Well OW-02 mid-valley (m a.s.l.)
prediction_ow03 = ____  # Well OW-03 downstream (m a.s.l.)

print("Your predictions before model run:")
print(f"  OW-01 (upstream):     {prediction_ow01} m a.s.l.")
print(f"  OW-02 (mid-valley):   {prediction_ow02} m a.s.l.")
print(f"  OW-03 (downstream):   {prediction_ow03} m a.s.l.")
print("\nAfter running the model, we'll compare to actual results!")
```

---

### Cell 6.4: Run Simulation (Code)

```python
# [UNDERSTAND THIS: Running a MODFLOW 6 simulation]

print("=" * 70)
print("Running MODFLOW 6 groundwater flow simulation...")
print("=" * 70)

# Assuming gwf and sim objects are already defined from previous sections

try:
    # Write all simulation files to disk
    sim.write_simulation()
    print("\nSimulation files written successfully.")
    print(f"Working directory: {sim.sim_ws}")

    # Run the actual simulation
    print("\nExecuting MODFLOW 6...")
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

---

### Cell 6.5: Check Convergence (Code)

```python
# [BLACK BOX: Extract convergence information from MODFLOW 6 list file]

def check_model_convergence(sim):
    """
    Extract convergence status from MODFLOW 6 .lst file.

    Returns:
        converged (bool): True if 'converged' appears in list file
        iterations (int): Count of iteration-related lines
    """
    from pathlib import Path

    lst_file = Path(sim.sim_ws) / f"{sim.name}.lst"

    if not lst_file.exists():
        print(f"List file not found: {lst_file}")
        return False, 0

    with open(lst_file, 'r') as f:
        content = f.read()

    # Look for convergence success message
    converged = "converged" in content.lower() or "solution converged" in content.lower()

    # Count iteration lines (rough estimate)
    iteration_count = content.count("iter")

    return converged, iteration_count


# Check convergence
converged, iterations = check_model_convergence(sim)

if converged:
    print(f"Model Convergence Status: SUCCESS")
    print(f"Approximate iteration count: {iterations}")
    print("\nThe Newton-Raphson solver found a solution.")
else:
    print(f"Model Convergence Status: NEEDS REVIEW")
    lst_path = Path(sim.sim_ws) / f"{sim.name}.lst"
    print(f"Review the list file: {lst_path}")
    print("\nCommon issues:")
    print("  - Boundary conditions not properly set")
    print("  - IDOMAIN issues (isolated cells)")
    print("  - Negative head values (aquifer too thin)")
```

---

### Cell 6.6: Compare Predictions to Results (Code)

```python
# [BLACK BOX: Extract simulated heads at observation well locations]

import numpy as np
import flopy.utils

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


# Define observation well locations (coordinates in model projection)
# Replace with actual coordinates from your data files
observation_wells = {
    'OW-01': (2683400, 1249300),  # (easting, northing)
    'OW-02': (2682100, 1250500),
    'OW-03': (2680800, 1251200),
}

# Extract simulated heads at observation locations
simulated_heads = get_heads_at_observation_wells(gwf, modelgrid, observation_wells)

# Compare predictions to actual results
print("=" * 70)
print("PREDICTION VS. SIMULATION RESULTS")
print("=" * 70)
print()

# Your predictions (from earlier in notebook)
prediction_data = {
    'OW-01': prediction_ow01,
    'OW-02': prediction_ow02,
    'OW-03': prediction_ow03,
}

differences = {}
for well_name in ['OW-01', 'OW-02', 'OW-03']:
    if well_name not in prediction_data or pd.isna(prediction_data[well_name]):
        print(f"{well_name}: Prediction not entered")
        continue

    pred = prediction_data[well_name]
    sim_head = simulated_heads.get(well_name, np.nan)

    if np.isnan(sim_head):
        print(f"{well_name}: Could not extract simulated head")
        continue

    diff = abs(pred - sim_head)
    differences[well_name] = diff

    print(f"{well_name}:")
    print(f"  Your prediction:    {pred:8.2f} m a.s.l.")
    print(f"  Simulated head:     {sim_head:8.2f} m a.s.l.")
    print(f"  Absolute error:     {diff:8.2f} m")
    print()

if differences:
    mean_error = np.mean(list(differences.values()))
    print(f"Mean absolute error: {mean_error:.2f} m")
    print()

    if mean_error < 0.5:
        print("Excellent! Your intuition about the aquifer flow is strong.")
    elif mean_error < 2.0:
        print("Good! You captured the major trends. Note areas where your")
        print("predictions differed - these reveal model complexities.")
    else:
        print("Groundwater systems are complex! This is why we use models")
        print("to rigorously quantify behavior. In Notebook 5, we'll calibrate")
        print("this model to match observations.")
else:
    print("Could not compare predictions - check that observation well")
    print("coordinates are properly defined.")
```

---

## Section 7: Initial Results

### Cell 7.1: Head Distribution Map (Code)

```python
# [UNDERSTAND THIS: Visualizing model results on DISV grids]

import matplotlib.pyplot as plt
import numpy as np
import flopy.utils

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

# Print summary statistics
head_obj = gwf.output.head()
head_data = head_obj.get_data()[0, :]  # Extract 2D array (layer 0)
print("\nHead Distribution Summary:")
print(f"  Minimum head: {np.nanmin(head_data):.2f} m a.s.l.")
print(f"  Maximum head: {np.nanmax(head_data):.2f} m a.s.l.")
print(f"  Mean head:    {np.nanmean(head_data):.2f} m a.s.l.")
print(f"  Head range:   {np.nanmax(head_data) - np.nanmin(head_data):.2f} m")

print("\nInterpretation:")
print("  - Highest heads in the south-east (upstream)")
print("  - Gradual decrease toward west/north (downstream)")
print("  - Consistent with general flow direction identified in Notebook 2")
print("  - River boundaries and boundary conditions shape the contours")
```

---

### Cell 7.2: Water Balance Summary (Code)

```python
# [BLACK BOX: Extract and format water balance from MODFLOW 6 budget file]

import pandas as pd
import numpy as np
from pathlib import Path
import flopy.utils

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
try:
    budget_flows = format_budget_summary(gwf, verbose=False)
except Exception as e:
    print(f"Error reading budget file: {e}")
    budget_flows = {}

# Calculate totals
inflows = sum([v for v in budget_flows.values() if v > 0])
outflows = abs(sum([v for v in budget_flows.values() if v < 0]))
imbalance = inflows - outflows
error_percent = (abs(imbalance) / inflows) * 100 if inflows > 0 else 0

# Display formatted table
print("=" * 90)
print("WATER BALANCE SUMMARY (Steady-State Model)")
print("=" * 90)
print()
print(f"{'Package':<15} {'Flow (m³/day)':<20} {'% of Total In':<15} {'Type':<10}")
print("-" * 90)

for pkg, flow in sorted(budget_flows.items()):
    pct = (abs(flow) / inflows) * 100 if inflows > 0 else 0
    flow_type = "Inflow " if flow > 0 else "Outflow"
    print(f"{pkg:<15} {flow:>18,.0f}  {pct:>13.1f}%  {flow_type:<10}")

print("-" * 90)
print(f"{'TOTAL INFLOWS':<15} {inflows:>18,.0f}")
print(f"{'TOTAL OUTFLOWS':<15} {outflows:>18,.0f}")
print(f"{'IMBALANCE':<15} {imbalance:>18,.0f}")
print(f"{'Mass Bal. Error':<15} {error_percent:>13.2f}%")
print("=" * 90)

# Interpretation
print()
if abs(error_percent) < 0.01:
    status = "Excellent!"
    msg = "Numerical precision near machine limits."
elif abs(error_percent) < 0.1:
    status = "Excellent!"
    msg = "Mass balance closes to < 0.1%"
elif abs(error_percent) < 1.0:
    status = "Good"
    msg = "Mass balance error < 1% (acceptable)"
else:
    status = "Warning"
    msg = "Mass balance error > 1%. Check boundary conditions."

print(f"{status}: {msg}")
```

---

### Cell 7.3: Water Balance Checkpoint (Code)

```python
# Checkpoint: Water balance error
# Students use check_task_with_solution to verify their calculation

from shared_functions import check_task_with_solution

print("CHECKPOINT: Water Balance Error")
print("-" * 50)
print()
check_task_with_solution("task04_checkpoint_4")
```

---

### Cell 7.4: Simulated vs. Observed Heads (Code)

```python
# [UNDERSTAND THIS: Comparing model results to field observations]

import pandas as pd
import numpy as np
import flopy.utils
from pathlib import Path

# Load observed head data (from preprocessing)
# Format: CSV with columns [well_id, easting, northing, head_measured, well_type]
obs_data_path = Path("_SUPPORT/processed_data/observation_data.csv")

try:
    obs_data = pd.read_csv(obs_data_path)
    print(f"Loaded {len(obs_data)} observation wells from {obs_data_path}")
except Exception as e:
    print(f"Error loading observation data: {e}")
    print("Using example data for demonstration.")
    obs_data = pd.DataFrame({
        'well_id': ['OW-01', 'OW-02', 'OW-03'],
        'easting': [2683400, 2682100, 2680800],
        'northing': [1249300, 1250500, 1251200],
        'head_measured': [420.5, 409.3, 398.8]
    })

# Extract simulated heads at observation locations
simulated_at_obs = {}

# Load heads once using FloPy's output interface
head_obj = gwf.output.head()
# Keep full array for proper indexing: [nlay, ncpl] for DISV or [nlay, nrow, ncol] for structured
heads = head_obj.get_data()

for idx, obs_row in obs_data.iterrows():
    well_id = obs_row['well_id']
    x, y = obs_row['easting'], obs_row['northing']

    try:
        # Find cell at this location
        cell_info = modelgrid.intersect(x, y)

        # Get simulated head at this cell (layer 0)
        if isinstance(cell_info, (tuple, list)):
            # Structured grid: intersect returns (row, col)
            i, j = cell_info
            simulated_head = heads[0, i, j]  # [layer, row, col]
        else:
            # DISV grid: intersect returns cell_id directly
            cell_id = cell_info
            simulated_head = heads[0, cell_id]  # [layer, cell_id]

        simulated_at_obs[well_id] = simulated_head
    except Exception as e:
        print(f"Warning: Could not extract head for {well_id}: {e}")
        simulated_at_obs[well_id] = np.nan

# Create comparison DataFrame
comparison = pd.DataFrame({
    'Well ID': obs_data['well_id'],
    'Observed (m)': obs_data['head_measured'],
    'Simulated (m)': [simulated_at_obs.get(w, np.nan) for w in obs_data['well_id']],
})

comparison['Residual (m)'] = comparison['Observed (m)'] - comparison['Simulated (m)']
comparison['Abs Error (m)'] = abs(comparison['Residual (m)'])

print()
print("=" * 100)
print("SIMULATED VS. OBSERVED GROUNDWATER HEADS (Uncalibrated Model)")
print("=" * 100)
print()
print(comparison.to_string(index=False))
print()

# Summary statistics
mae = comparison['Abs Error (m)'].mean()
rmse = np.sqrt((comparison['Residual (m)']**2).mean())
max_error = comparison['Abs Error (m)'].max()

print("-" * 100)
print(f"Mean Absolute Error (MAE):             {mae:6.3f} m")
print(f"Root Mean Square Error (RMSE):         {rmse:6.3f} m")
print(f"Maximum absolute error:                {max_error:6.3f} m")
print()

print("INTERPRETATION:")
print("-" * 100)
print(f"This uncalibrated model shows {mae:.2f}m average error against observations.")
print()
print("This is EXPECTED because:")
print("  1. We used literature values for hydraulic conductivity (±50% uncertainty)")
print("  2. River conductances estimated from limited field data (×10 uncertainty)")
print("  3. Recharge simplified as uniform percentage of precipitation")
print("  4. Model geometry is simplified (real aquifer is more heterogeneous)")
print()
print("NEXT STEPS (Notebook 5 - Calibration):")
print("  - Automatically adjust K and river conductance to minimize these errors")
print("  - Test if other parameter sets also fit the observations (equifinality)")
print("  - Constrain previously uncertain parameters using field data")
```

---

### Cell 7.5: Conceptual Question - River Gaining/Losing (Code)

```python
# Checkpoint: Conceptual question about river-aquifer interaction
from shared_functions import check_task_with_solution

print("CHECKPOINT: Conceptual Understanding")
print("=" * 70)
print()
check_task_with_solution("task04_checkpoint_5")
```

---

### Cell 7.6: Discussion of Uncalibrated Model (Markdown Only)

See design document - provides context for mismatch and previews calibration.

---

### Cell 7.7: Optional - Output Files (Markdown Only)

See design document - collapsible section with technical details about MODFLOW output files.

---

## Section 8: Summary and Next Steps

### Cell 8.1: Key Takeaways (Markdown Only)

See design document - bullet summary of learning outcomes.

---

### Cell 8.2: Why Calibration Is Essential (Markdown Only)

See design document - explains diagnostic value of mismatches.

---

### Cell 8.3: Reflection Prompt (Markdown Only)

See design document - asks student to reflect on learning.

---

### Cell 8.4: Save Simulation (Code)

```python
# [BLACK BOX: Save simulation for use in Notebook 5]

import pickle
from pathlib import Path

# Define checkpoint directory
checkpoint_dir = Path("_SUPPORT/model_checkpoints")
checkpoint_dir.mkdir(parents=True, exist_ok=True)

sim_save_path = checkpoint_dir / "notebook4_uncalibrated_sim.pkl"

try:
    # Save entire simulation object for Notebook 5
    with open(sim_save_path, 'wb') as f:
        pickle.dump(sim, f)

    print("=" * 70)
    print("SIMULATION SAVED")
    print("=" * 70)
    print(f"Saved to: {sim_save_path}")
    print(f"File size: {sim_save_path.stat().st_size / (1024*1024):.2f} MB")
    print()
    print("Notebook 5 will load this simulation and perform calibration.")
    print("You can delete other checkpoint files to save disk space.")
    print()

except Exception as e:
    print(f"Error saving simulation: {e}")
    print("Note: You can still proceed to Notebook 5,")
    print("but the simulation will need to be rebuilt.")
```

---

### Cell 8.5: Preview Next Steps (Markdown Only)

See design document - navigation and preview of Notebook 5.

---

## Notes for Implementation

### Imports Needed at Top of Notebook

```python
# Standard libraries
import sys
import os
from pathlib import Path
import pickle

# Data and scientific
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# FloPy and MODFLOW utilities
import flopy
import flopy.utils
import flopy.mf6

# Custom utilities (from _SUPPORT/src)
sys.path.append('../../_SUPPORT/src')
sys.path.append('../../_SUPPORT/src/scripts/scripts_exercises')

from shared_functions import check_task_with_solution
from data_utils import download_named_file
import plot_utils as pu
```

### Data Files Expected

The code assumes these pre-processed data files exist:
- `_SUPPORT/processed_data/observation_data.csv` - Well locations and measured heads
- Model boundary GeoDataFrame (`boundary_gdf`) from earlier in notebook
- Model grid object (`modelgrid`) from earlier in notebook
- Ground water flow model object (`gwf`) and simulation (`sim`) from earlier sections

### FloPy Version Requirement

Code assumes **FloPy >= 3.4.0** with stable DISV support:
```
flopy>=3.4.0
```

Pin in requirements.txt to ensure consistency.

---

## Timing Notes

**Actual execution time for code cells:**
- **Cell 6.4** (Run simulation): 2-10 seconds (depends on grid size and solver iterations)
- **Cell 6.6** (Prediction comparison): < 1 second
- **Cell 7.1** (Head plot): 2-5 seconds (matplotlib rendering)
- **Cell 7.2** (Budget summary): < 1 second
- **Cell 7.4** (Observed vs simulated): < 1 second
- **Cell 8.4** (Save simulation): 1-5 seconds

Total execution: ~10-30 seconds

**Interpretation and discussion time:** ~14 minutes

**Total section time:** ~16 minutes (within 7+7+2=16 min target)

