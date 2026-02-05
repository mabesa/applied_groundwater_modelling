# Notebook 4: Sections 6-8 Design - Executive Summary

**Created:** February 2026
**Status:** Complete Design (Ready for Implementation)
**Target:** Sections 6, 7, 8 redesign per notebook4_improvement_plan.md

---

## Overview

This design package contains **complete, implementable specifications** for Sections 6-8 of Notebook 4 (Model Implementation), following the improvement plan for restructuring toward MODFLOW 6, DISV grids, and active learning checkpoints.

The three sections work together to:
- **Section 6:** Run the model and verify convergence with prediction exercise
- **Section 7:** Interpret results, compute water balance, benchmark against observations
- **Section 8:** Synthesize learning and transition to calibration (Notebook 5)

---

## Documents Included

### 1. **notebook4_sections_6-8.md** (Main Design Document)
Complete markdown and code cell specifications with:
- Full narrative and conceptual content
- Pedagogical scaffolding (UNDERSTAND THIS vs BLACK BOX labels)
- Code comments and context
- Timing targets and learning objectives
- **Size:** ~4,500 lines | **Read time:** 30-45 min

**Use this for:**
- Understanding the full structure and flow
- Context on pedagogical choices
- Markdown content copy-paste
- Code architecture decisions

### 2. **notebook4_sections_6-8_code_reference.md** (Ready-to-Use Code)
Implementation-ready code cells with:
- Copy-paste ready code blocks
- Minimal extraneous explanation (for coding)
- Import statements and dependencies
- Error handling and edge cases
- **Size:** ~2,500 lines | **Read time:** 20-30 min

**Use this for:**
- Direct implementation into notebook
- Testing and debugging
- Adapting to specific data paths
- Quick reference during coding

### 3. **notebook4_checkpoint_data.md** (Assessment Framework)
Checkpoint definitions for `tasks_data.py`:
- 2 required checkpoints (Sections 7.3, 7.5)
- 3 optional checkpoints (early sections)
- Answer ranges with tolerance justification
- Solution explanations and learning context
- **Size:** ~1,200 lines | **Read time:** 15-20 min

**Use this for:**
- Adding to `tasks_data.py` and `shared_functions.py`
- Grading and feedback framework
- Understanding assessment strategy
- Adapting tolerance ranges to your model

### 4. **notebook4_sections_6-8_SUMMARY.md** (This File)
Executive summary and implementation guide.

### 5. **REVIEW_NOTEBOOK4_SECTIONS_6-8.md** (Review Document)
Consolidated review findings and action items.

---

## Key Design Features

### Pedagogical Approach

| Feature | Implementation | Purpose |
|---------|----------------|---------|
| **Prediction Exercise** | Section 6.3: Students predict 3 well heads before running model | Engage predictive thinking; builds model intuition |
| **Code Labeling** | [BLACK BOX] vs [UNDERSTAND THIS] | Clear transparency about what to internalize |
| **Checkpoints** | 2 required numerical + conceptual; 3 optional | Active verification of learning, not just completion |
| **Water Balance** | Full computational pipeline with interpretation | Demonstrates model correctness and budget thinking |
| **Uncalibrated Results** | Explicitly discuss mismatch with observations | Motivates calibration; reveals parameter uncertainty |
| **Reflection Prompt** | End-of-section self-assessment | Metacognition and knowledge gap identification |

### Structural Highlights

**Section 6 (Solver and Run):**
- IMS solver configuration and convergence criteria
- Prediction exercise (fill-in-the-blank) before running
- Model execution and convergence checking
- Comparison of predictions to results
- **Duration:** 6-7 minutes

**Section 7 (Initial Results):**
- Head distribution map on DISV grid
- Water balance budget with inflow/outflow summary
- Numerical checkpoint: mass balance error
- Simulated vs. observed head comparison (motivates calibration)
- Conceptual checkpoint: river gaining/losing determination
- Optional deep dive on output file structures
- **Duration:** 7-8 minutes

**Section 8 (Summary and Next Steps):**
- Key takeaways (model works, but uncalibrated)
- Discussion of why calibration is essential
- Save simulation checkpoint for Notebook 5
- Preview of calibration workflow
- Reflection prompt
- Navigation to Notebook 5
- **Duration:** 2 minutes

**Total Duration:** ~16-18 minutes (within 6-7+7-8+2=15-17 min target)

---

## Implementation Workflow

### Phase 1: Preparation (1 hour)

1. Review all three documents for familiarity
2. Check FloPy version (>=3.4.0)
3. Verify pre-processed data files exist:
   - `_SUPPORT/processed_data/observation_data.csv`
   - Boundary polygon GeoPackage
   - DEM and aquifer bottom rasters
4. Set up `_SUPPORT/model_checkpoints/` directory

### Phase 2: Add Checkpoints to tasks_data.py (30 min)

1. Copy checkpoint data from **notebook4_checkpoint_data.md**
2. Add 4 dictionaries to `tasks_data.py`:
   - `questions_markdown["task04_checkpoint_*"]`
   - `solutions["task04_checkpoint_*"]`
   - `solutions_exact["task04_checkpoint_*"]`
   - `solutions_markdown["task04_checkpoint_*"]`
3. Test `check_task_with_solution()` with sample data
4. Verify acceptable answer ranges work with your model

### Phase 3: Build Notebook Sections (2-3 hours)

1. Create cells in Jupyter notebook
2. Add markdown from **notebook4_sections_6-8.md**
3. Add code from **notebook4_sections_6-8_code_reference.md**
4. Adapt data paths to your environment
5. Test each code cell:
   - Section 6.3: Prediction entry (no execution needed)
   - Section 6.4: Model run (execute; time execution)
   - Section 6.6: Head extraction (execute; verify output)
   - Section 7.1-7.2: Results visualization (execute; check plots)
   - Section 7.3-7.5: Checkpoints (execute; verify widget behavior)
   - Section 8.4: Checkpoint saving (execute; verify file created)

### Phase 4: Integration & Testing (1-2 hours)

1. Link from Section 5 (BCs) to Section 6 (Solver)
2. Verify navigation between sections
3. Test on fresh JupyterHub environment
4. Confirm model runs in < 30 seconds
5. Check that all plots render correctly
6. Validate that checkpoints work with tolerance ranges
7. Time complete notebook (should be ~16 min + execution)

### Phase 5: Documentation (30 min)

1. Update README with Notebook 4 description
2. Add any data preprocessing notes
3. Document expected outputs for each section
4. Create troubleshooting guide (move from current Notebook 4)

---

## Data Dependencies

### Input Files Needed

| File | Location | Format | Usage |
|------|----------|--------|-------|
| Boundary polygon | `_SUPPORT/processed_data/model_boundary.gpkg` | GeoPackage | Grid generation |
| Observation wells | `_SUPPORT/processed_data/observation_data.csv` | CSV | Head comparison (7.4) |
| River geometries | `_SUPPORT/processed_data/river_geometry.gpkg` | GeoPackage | RIV package (from Section 5) |
| Well locations | `_SUPPORT/processed_data/well_geometry.gpkg` | GeoPackage | WEL package (from Section 5) |
| DEM | `_SUPPORT/processed_data/dem_resampled.tif` | GeoTIFF | Model top (from Section 5) |
| Aquifer bottom | `_SUPPORT/processed_data/aquifer_bottom.tif` | GeoTIFF | Model bottom (from Section 5) |

### Output Files Created

| File | Location | Format | Purpose |
|------|----------|--------|---------|
| Simulation checkpoint | `_SUPPORT/model_checkpoints/notebook4_uncalibrated_sim.pkl` | Pickle | Load in Notebook 5 |
| MODFLOW files | `notebook4_model/` | Various | Intermediate simulation files |

---

## Code Features

### Key Functions Provided

**From notebook4_sections_6-8_code_reference.md:**

1. **`check_model_convergence(sim)`**
   - Extract convergence status from .lst file
   - Returns boolean and iteration count

2. **`get_heads_at_observation_wells(gwf, modelgrid, observation_coords)`**
   - Extract simulated heads at specified (x, y) locations
   - Handles both DISV and structured grids
   - Handles both DISV and structured grids
   - Returns dict of well_name -> head_value

3. **`plot_head_distribution(gwf, modelgrid, boundary_gdf, title)`**
   - Create head map on DISV grid
   - Includes colorbar and boundary overlay
   - Uses FloPy's built-in plotting

4. **`format_budget_summary(gwf, verbose=True)`**
   - Extract water balance from MODFLOW 6 budget file
   - Uses gwf.output.budget() for modern FloPy API
   - Extract package-specific flows
   - Returns dict with flows and statistics

### No Custom External Dependencies

All code uses standard FloPy utilities and built-in functions:
- `flopy.utils.HeadFile` - read head output
- `flopy.utils.CellBudgetFile` - read budget output
- `flopy.plot.PlotMapView` - visualize results
- `flopy.discretization.VertexGrid.intersect()` - find cells at coordinates

No custom `grid_utils.py` or external helper modules required for these sections.

---

## Assessment Framework

### Checkpoint Strategy

**2 Required Checkpoints:**
1. **task04_checkpoint_4** (Section 7.3): Water balance error %
   - Numerical answer: 0.0–0.15% acceptable range
   - Tests understanding of mass balance closure

2. **task04_checkpoint_5** (Section 7.5): River gaining/losing
   - Conceptual question with evidence from budget/heads
   - Tests interpretation of simulation results

**3 Optional Checkpoints (if desired):**
- task04_checkpoint_1: Active cell count
- task04_checkpoint_2: Average aquifer thickness
- task04_checkpoint_3: Total recharge flux

### Grading Guidance

**Numerical checkpoints:**
- Correct answer in range: 100%
- Outside range but reasonable: 50% (with feedback)
- Missing/blank: 0%

**Conceptual checkpoints:**
- Answer + correct reasoning: 100%
- Answer only, no reasoning: 75%
- Reasoning shown but answer wrong: 50%
- Missing/incomplete: 0%

---

## Timing Breakdown

### Student Engagement Time

| Activity | Time (min) | Notes |
|----------|-----------|-------|
| Read Section 6 intro | 2 | Solver configuration and OC settings |
| Prediction exercise | 3 | Fill in 3 head values; think about gradients |
| Run model | 5 | Model execution (3-10 sec) + review |
| Section 6 total | ~10 | Slightly over target to allow thinking |
| Read Section 7 intro + head map | 2 | Interpret head distribution |
| Water balance calculation | 3 | Read budget, calculate error |
| Observations checkpoint | 3 | Checkpoint widget + review |
| Simulated vs observed | 2 | Compare and discuss mismatch |
| River question | 1 | Answer checkpoint |
| Section 7 total | ~11 | Slightly over for detailed interpretation |
| Section 8 total | 2 | Summary + transition |
| **Total** | **~23 min** | Includes ~10 min model execution |
| **Total core time (no execution)** | **~15 min** | Meets 16 min target |

### Computational Time

- Model execution: 2–10 seconds (depends on grid size, solver iterations)
- Plotting: 2–5 seconds (matplotlib rendering)
- Budget calculation: < 1 second
- Checkpoint widgets: instantaneous
- **Total non-execution:** < 10 seconds

---

## Potential Adaptations

### For Faster Convergence (if model runs slowly)

1. **Pre-run the model** and save heads/budget
2. **Load checkpoint instead** of running in notebook
3. **Show timing:** "Model took X seconds to converge (Y iterations)"

### For More Challenge

1. **Add task04_checkpoint_1,2,3** (additional numerical checkpoints)
2. **Require students to calculate checkpoint_4 from raw budget data** (not provided formula)
3. **Add follow-up:** "Which parameter uncertainty most affects this error?"

### For Less Challenge

1. **Remove prediction exercise** (Section 6.3) or provide ranges
2. **Show checkpoint answers upfront** instead of hidden
3. **Skip optional deep dive** (Section 7.7)

---

## Integration Points

### Upstream Dependencies (from Section 5)

Assumes these objects exist:
- `gwf` - FloPy ModflowGwf object (model grid, packages)
- `sim` - FloPy MFSimulation object
- `modelgrid` - Grid object (VertexGrid for DISV)
- `boundary_gdf` - GeoDataFrame with boundary polygon
- All boundary condition packages created (CHD, RIV, WEL, RCH, IMS, OC)

### Downstream Dependencies (for Section 8/Notebook 5)

Saves:
- `sim_save_path` - Pickled simulation object
- Model files in working directory (auto-created by MODFLOW)

Notebook 5 loads and uses the saved simulation for calibration.

---

## Troubleshooting Guide

### Common Issues During Implementation

**Issue:** "HeadFile not found" error
- **Cause:** Model didn't run successfully (see convergence check first)
- **Fix:** Review list file for convergence/error messages

**Issue:** "Observation wells coordinates don't match grid"
- **Cause:** Coordinate system mismatch (UTM vs local, wrong zone)
- **Fix:** Verify CRS in GeoDataFrame and model grid

**Issue:** "Water balance error > 1%"
- **Cause:** Missing or incorrectly defined boundary condition
- **Fix:** Check that all 5 BC packages are active (CHD, RIV, WEL, RCH)

**Issue:** Prediction error > 5 m
- **Cause:** Students made rough estimates (expected!)
- **Fix:** Explain why: real aquifers are complex; models have parameter uncertainty

**Issue:** Checkpoint answer range too narrow/wide
- **Cause:** Model discretization or parameters different from expected
- **Fix:** Run your model, record actual answer, adjust tolerance range

---

## Quality Checklist

Before finalizing implementation:

- [ ] All markdown sections copy-pasted without errors
- [ ] All code cells execute without syntax errors
- [ ] Data files (.csv, .gpkg, .tif) verified to exist
- [ ] Model runs in < 30 seconds (time and note actual time)
- [ ] Plots render correctly with expected content
- [ ] Water balance closes to < 0.1% (confirms boundary conditions)
- [ ] Checkpoints have reasonable answer ranges (±10% of expected)
- [ ] Navigation links between sections work
- [ ] Notebook timing is ~15-16 min (core content only)
- [ ] Code comments explain [BLACK BOX] vs [UNDERSTAND THIS]
- [ ] No emojis in section headers
- [ ] Reflection prompt is open-ended (not yes/no)

---

## Files for Modification

### Primary Implementation File

- **Target:** `/Users/bea/Documents/GitHub/applied_groundwater_modelling/PROJECT/flow/4_model_implementation.ipynb`
- **Sections:** 6, 7, 8 (sections 1-5 from earlier improvements)

### Support Files to Update

1. **`_SUPPORT/src/scripts/scripts_exercises/tasks_data.py`**
   - Add checkpoint data (4 dictionaries)
   - Insert from **notebook4_checkpoint_data.md**

2. **`requirements.txt`** (if needed)
   - Ensure `flopy>=3.4.0` (for stable DISV support)
   - Pin exact version: `flopy==3.4.2` or similar

3. **`README.md`**
   - Update Notebook 4 description
   - Note new MODFLOW 6 / DISV approach

4. **`_SUPPORT/docs/troubleshooting.md`** (create if not exists)
   - Include common issues from this design
   - Add debugging tips

---

## Success Metrics

After implementation, verify:

1. **Timing:** Notebook runs in ~16 min (core) or ~26 min (with model execution)
2. **Checkpoints:** > 80% first-attempt success on numerical answers
3. **Convergence:** Model converges without warnings
4. **Water Balance:** < 0.1% error (indicates correct setup)
5. **Visualization:** All plots appear correctly
6. **Predictions:** Students make meaningful predictions (not random guesses)
7. **Mismatch:** Simulated vs observed shows clear difference (< 5m difference would suggest parameters were too good, > 10m suggests major issues)
8. **Engagement:** Student feedback indicates sections are clear and engaging

---

## Contact & Support

For questions during implementation:
- Refer back to `notebook4_improvement_plan.md` for overall strategy
- Check design documents for code context
- Consult shared_functions.py for checkpoint infrastructure
- Test on sample data before full deployment

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 2026 | Complete design package with 4 documents |

---

## Document Cross-References

- **notebook4_sections_6-8.md**: Full design with pedagogical context
- **notebook4_sections_6-8_code_reference.md**: Copy-paste ready code
- **notebook4_checkpoint_data.md**: Assessment framework
- **notebook4_improvement_plan.md**: Overall project context
- **shared_functions.py**: Checkpoint widget framework
- **tasks_data.py**: Checkpoint answer storage
