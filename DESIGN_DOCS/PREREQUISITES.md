# Prerequisites for Notebook 4 Sections 6-8 Implementation

**Created:** 2026-02-05
**Purpose:** Document all implicit assumptions that must be satisfied before implementing Sections 6-8

---

## Critical Prerequisites (Must Complete First)

### 1. Notebook 4 Sections 1-5 Must Use MODFLOW 6 / DISV

**Current State:** The existing Notebook 4 uses MODFLOW-2005/NWT with structured DIS grids.

**Required State:** Sections 1-5 must be rewritten to use:
- MODFLOW 6 (`flopy.mf6` API)
- DISV discretization (Voronoi/unstructured grids)
- Newton-Raphson solver (IMS package)
- NPF package (instead of LPF)

**Objects that must exist after Section 5 completes:**

| Object | Type | Description |
|--------|------|-------------|
| `sim` | `flopy.mf6.MFSimulation` | MODFLOW 6 simulation object |
| `gwf` | `flopy.mf6.ModflowGwf` | Groundwater flow model |
| `modelgrid` | `flopy.discretization.VertexGrid` | DISV grid object |
| `boundary_gdf` | `geopandas.GeoDataFrame` | Model boundary polygon |

**Packages that must be configured:**
- TDIS (time discretization)
- DISV (vertex discretization)
- NPF (node property flow)
- IC (initial conditions)
- CHD (constant head boundaries)
- RIV (river package)
- WEL (well package)
- RCH (recharge package)
- IMS (iterative model solution)
- OC (output control)

---

### 2. Data Files Must Be Created

**Directory:** `_SUPPORT/processed_data/` (must be created)

| File | Format | Required Columns/Layers | Status |
|------|--------|------------------------|--------|
| `model_boundary.gpkg` | GeoPackage | Polygon geometry, CRS: EPSG:2056 | **MISSING** |
| `observation_data.csv` | CSV | `well_id, easting, northing, head_measured` | **MISSING** |
| `river_geometry.gpkg` | GeoPackage | LineString, `stage, conductance, rbot` | **MISSING** |
| `well_geometry.gpkg` | GeoPackage | Point, `rate` | **MISSING** |
| `dem_resampled.tif` | GeoTIFF | Elevation (m a.s.l.), CRS: EPSG:2056 | **MISSING** |
| `aquifer_bottom.tif` | GeoTIFF | Bottom elevation (m a.s.l.) | **MISSING** |

**Additional directory to create:** `_SUPPORT/model_checkpoints/`

**Coordinate Reference System:** All spatial data must use Swiss LV95 (EPSG:2056)

---

### 3. FloPy Version Requirement

**Minimum Version:** FloPy >= 3.4.0 (for stable DISV support)

**Verification command:**
```python
import flopy
print(flopy.__version__)  # Must be >= 3.4.0
```

**Note:** No `requirements.txt` currently exists in the repository. Consider adding one.

---

### 4. Multiple-Choice Widget for Checkpoint 5

**Current State:** `shared_functions.py` only supports `FloatText` (numerical) widgets.

**Required Enhancement:** Add support for multiple-choice questions.

**Implementation needed in `_SUPPORT/src/scripts/scripts_exercises/shared_functions.py`:**

```python
def create_multiple_choice(task_id, options):
    """
    Create a multiple-choice widget for conceptual checkpoints.

    Parameters:
        task_id: str - The checkpoint identifier (e.g., "task04_checkpoint_5")
        options: list - List of (value, label) tuples for radio buttons

    Returns:
        ipywidgets.VBox with radio buttons and submit button
    """
    import ipywidgets as widgets
    from IPython.display import display

    # Radio buttons for options
    radio = widgets.RadioButtons(
        options=options,
        description='Answer:',
        disabled=False
    )

    # Submit button
    submit = widgets.Button(description="Check Answer")
    output = widgets.Output()

    def on_submit(b):
        with output:
            output.clear_output()
            selected = radio.value
            correct = solutions_exact.get(task_id, "")
            if selected == correct or selected.startswith(correct):
                print("✓ Correct!")
            else:
                print(f"✗ Try again. Your answer: {selected}")

    submit.on_click(on_submit)

    return widgets.VBox([radio, submit, output])
```

---

## Notebook 3 Prerequisites

Notebook 3 must cover these topics before students reach Notebook 4:

1. **MODFLOW 6 packages** - NPF, CHD, RIV, WEL, RCH, IMS, OC
2. **DISV grid concepts** - Voronoi tessellation, CVFD requirements
3. **Grid generation** - Using `flopy.utils.voronoi.VoronoiGrid`
4. **Cell intersection** - How `modelgrid.intersect(x, y)` works for DISV

**Current gap:** Notebook 3 appears to be primarily conceptual (~14 cells). Students may need hands-on DISV grid construction before Notebook 4.

---

## Python Environment Requirements

### Required Packages

```
flopy>=3.4.0
numpy
pandas
geopandas
matplotlib
ipywidgets
shapely
rasterio
```

### Path Configuration

Notebook 4 must add these paths to `sys.path`:
```python
import sys
sys.path.append('../../_SUPPORT/src')
sys.path.append('../../_SUPPORT/src/scripts/scripts_exercises')
```

---

## Checkpoint Data Requirements

The following checkpoints must be defined in `tasks_data.py`:

| Checkpoint ID | Type | Range/Answer | Status |
|--------------|------|--------------|--------|
| task04_checkpoint_1 | Numerical | (4500, 5500) cells | Optional |
| task04_checkpoint_2 | Numerical | (13, 22) m | Optional |
| task04_checkpoint_3 | Numerical | (4500, 5500) m³/day | Optional |
| task04_checkpoint_4 | Numerical | (0, 1) % | Required |
| task04_checkpoint_5 | Multiple-choice | "B) Losing" | Required (needs MC widget) |
| task04_checkpoint_6 | Open-ended | Text response | Defined |

---

## Pre-Implementation Validation Script

Run this script to verify all prerequisites are met:

```python
#!/usr/bin/env python
"""Validate prerequisites for Notebook 4 Sections 6-8 implementation."""

import sys
from pathlib import Path

def check_prerequisites():
    errors = []
    warnings = []

    # 1. Check FloPy version
    try:
        import flopy
        version = flopy.__version__
        major, minor = map(int, version.split('.')[:2])
        if major < 3 or (major == 3 and minor < 4):
            errors.append(f"FloPy version {version} < 3.4.0 required")
        else:
            print(f"✓ FloPy version: {version}")
    except ImportError:
        errors.append("FloPy not installed")

    # 2. Check data directory
    data_dir = Path("_SUPPORT/processed_data")
    if not data_dir.exists():
        errors.append(f"Data directory missing: {data_dir}")
    else:
        print(f"✓ Data directory exists: {data_dir}")

        # Check required files
        required_files = [
            "model_boundary.gpkg",
            "observation_data.csv",
            "river_geometry.gpkg",
            "well_geometry.gpkg",
            "dem_resampled.tif",
            "aquifer_bottom.tif"
        ]
        for f in required_files:
            if not (data_dir / f).exists():
                errors.append(f"Missing data file: {data_dir / f}")
            else:
                print(f"✓ Data file exists: {f}")

    # 3. Check checkpoint directory
    checkpoint_dir = Path("_SUPPORT/model_checkpoints")
    if not checkpoint_dir.exists():
        warnings.append(f"Checkpoint directory will be created: {checkpoint_dir}")

    # 4. Check shared_functions.py
    shared_func_path = Path("_SUPPORT/src/scripts/scripts_exercises/shared_functions.py")
    if shared_func_path.exists():
        content = shared_func_path.read_text()
        if "create_multiple_choice" not in content:
            warnings.append("shared_functions.py missing create_multiple_choice() for checkpoint 5")
        else:
            print("✓ Multiple-choice widget found in shared_functions.py")
    else:
        errors.append(f"shared_functions.py not found: {shared_func_path}")

    # Report
    print("\n" + "=" * 60)
    if errors:
        print("ERRORS (must fix before implementation):")
        for e in errors:
            print(f"  ✗ {e}")
    if warnings:
        print("\nWARNINGS (should address):")
        for w in warnings:
            print(f"  ⚠ {w}")
    if not errors and not warnings:
        print("✓ All prerequisites satisfied!")

    return len(errors) == 0

if __name__ == "__main__":
    success = check_prerequisites()
    sys.exit(0 if success else 1)
```

---

## Implementation Order

Given these prerequisites, the recommended implementation order is:

1. **Create data files** or run preprocessing notebooks
2. **Update Notebook 3** with hands-on DISV content (if needed)
3. **Rewrite Notebook 4 Sections 1-5** for MODFLOW 6 / DISV
4. **Add MC widget to shared_functions.py**
5. **Implement Sections 6-8** per design documents
6. **Run validation script** to verify all prerequisites
7. **Test end-to-end** on fresh environment

---

## Document History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-05 | Auto-generated | Initial creation based on 10-agent review findings |
