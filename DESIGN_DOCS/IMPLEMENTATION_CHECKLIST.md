# Notebook 4 Sections 6-8: Implementation Checklist

**Start Date:** ___________
**Target Completion:** February 2026
**Status:** [ ] Planning [ ] In Progress [ ] Complete

---

## Related Documents

- **REVIEW_NOTEBOOK4_SECTIONS_6-8.md**: Review findings and prioritized fixes

---

## Pre-Implementation Setup

### Repository & Environment
- [ ] Clone/pull latest version of repository
- [ ] Create new branch: `feature/notebook4-sections-6-8`
- [ ] Verify FloPy version: `import flopy; print(flopy.__version__)` (requires >= 3.4.0)
- [ ] Set up Jupyter notebook for editing

### Data Files
- [ ] Verify `_SUPPORT/processed_data/model_boundary.gpkg` exists
- [ ] Verify `_SUPPORT/processed_data/observation_data.csv` exists
- [ ] Verify `_SUPPORT/processed_data/river_geometry.gpkg` exists
- [ ] Verify `_SUPPORT/processed_data/well_geometry.gpkg` exists
- [ ] Verify `_SUPPORT/processed_data/dem_resampled.tif` exists
- [ ] Verify `_SUPPORT/processed_data/aquifer_bottom.tif` exists
- [ ] Create directory: `_SUPPORT/model_checkpoints/`

### Documentation Review
- [ ] Read `notebook4_improvement_plan.md` (full context)
- [ ] Read `notebook4_sections_6-8_SUMMARY.md` (overview)
- [ ] Skim `notebook4_sections_6-8.md` (design details)
- [ ] Review `notebook4_sections_6-8_code_reference.md` (code)
- [ ] Review `notebook4_checkpoint_data.md` (assessment)

---

## Phase 1: Checkpoint Integration (30 min)

### Add to tasks_data.py

Located: `_SUPPORT/src/scripts/scripts_exercises/tasks_data.py`

- [ ] **task04_checkpoint_4** (Water balance error)
  - [ ] Add to `questions_markdown`
  - [ ] Add to `solutions` (range: 0.0–0.15)
  - [ ] Add to `solutions_exact` ("0.08" or actual value)
  - [ ] Add to `solution_unit` ("%")
  - [ ] Add to `solutions_markdown` (explanation)

- [ ] **task04_checkpoint_5** (River gaining/losing)
  - [ ] Add to `questions_markdown`
  - [ ] Add to `solutions_markdown` (explanation with methods)
  - [ ] Consider text-based or multi-choice approach
  - [ ] Define acceptable keywords/answers

- [ ] (Optional) **task04_checkpoint_1** (Active cells)
  - [ ] Add all four dictionaries as above
  - [ ] Range: 4500–5500 cells

- [ ] (Optional) **task04_checkpoint_2** (Aquifer thickness)
  - [ ] Add all four dictionaries
  - [ ] Range: 13–22 m (based on actual Limmat Valley geological data)

- [ ] (Optional) **task04_checkpoint_3** (Total recharge)
  - [ ] Add all four dictionaries
  - [ ] Range: 4500–5500 m³/day (accounts for active cell coverage)

- [ ] **task04_checkpoint_6** (Model calibration and validation)
  - [ ] Already defined in `tasks_data.py`
  - [ ] Verify questions_markdown entry exists
  - [ ] Verify solutions_markdown entry exists
  - [ ] Solution type: open-ended (observations for model assessment)

> **Note:** Ranges above have been reconciled with tasks_data.py as of 2026-02-05.
> Run actual model to verify values fall within expected ranges before deployment.

### Test Checkpoints
- [ ] Test `check_task_with_solution()` with sample data
- [ ] Verify answer range accepts your model results
- [ ] Check that widgets display correctly
- [ ] Ensure solution explanations are clear

---

## Phase 2: Section 6 Implementation (1 hour)

### Cell 6.1 & 6.2 (Markdown - IMS Solver & Output Control)
- [ ] Create markdown cell with solver configuration discussion
- [ ] Include coverage of:
  - [ ] Convergence tolerance (HCLOSE)
  - [ ] Closure tolerance (RCLOSE)
  - [ ] Newton-Raphson iteration concept
  - [ ] Output Control settings
- [ ] No code required for this cell

### Cell 6.3 (Prediction Exercise)
- [ ] Create markdown cell explaining prediction exercise
- [ ] Create code cell with fill-in-the-blank template
  - [ ] Three well IDs (OW-01, OW-02, OW-03)
  - [ ] Placeholder lines with `____`
  - [ ] Print statement showing predictions
  - [ ] Hint about hydraulic gradients
- [ ] Test that cell executes without errors

### Cell 6.4 (Run Simulation)
- [ ] Add markdown explaining simulation execution
- [ ] Create code cell:
  - [ ] `sim.write_simulation()`
  - [ ] `sim.run_simulation(silent=False)`
  - [ ] Error handling with try/except
  - [ ] Success/failure messages
- [ ] **TEST: Execute and time the model run**
  - [ ] Record actual execution time: __________ seconds
  - [ ] Verify success message appears

### Cell 6.5 (Check Convergence)
- [ ] Add markdown explaining convergence checking
- [ ] Create code cell with `check_model_convergence()` function
- [ ] Call function and display results
- [ ] **TEST: Execute and verify convergence status**
  - [ ] Confirm "Converged" message appears
  - [ ] Note iteration count

### Cell 6.6 (Compare Predictions to Results)
- [ ] Add markdown explaining comparison
- [ ] Create code cell with `get_heads_at_observation_wells()` function
- [ ] Extract simulated heads at 3 observation wells
- [ ] Compare to predictions from 6.3
- [ ] Display table with prediction/simulated/difference
- [ ] Interpretation text based on mean error
- [ ] **TEST: Execute and verify output**
  - [ ] Check that 3 wells show in comparison
  - [ ] Verify differences are reasonable (±5m range)

---

## Phase 3: Section 7 Implementation (1.5 hours)

### Cell 7.1 (Head Distribution Map)
- [ ] Add markdown with head distribution explanation
- [ ] Create `plot_head_distribution()` function
- [ ] Create code cell:
  - [ ] Load head file
  - [ ] Call plotting function
  - [ ] Add colorbar and boundary
  - [ ] Display statistics (min, max, mean, range)
- [ ] **TEST: Execute and verify plot**
  - [ ] Check that colormap displays correctly
  - [ ] Verify statistics are reasonable (headmax > headmin)
  - [ ] Confirm boundary polygon overlays correctly

### Cell 7.2 (Water Balance Summary)
- [ ] Add markdown explaining budget components
- [ ] Add section on understanding CHD, RIV, WEL, RCH flows
- [ ] Create `format_budget_summary()` function
- [ ] Create code cell:
  - [ ] Load budget file
  - [ ] Extract flows for each package
  - [ ] Calculate inflows, outflows, imbalance
  - [ ] Calculate mass balance error %
  - [ ] Display formatted table
  - [ ] Interpretation based on error magnitude
- [ ] **TEST: Execute and verify budget**
  - [ ] Check that major packages appear (RIV, WEL, RCH)
  - [ ] Verify total inflows ≈ total outflows
  - [ ] Confirm error < 0.1%

### Cell 7.3 (Checkpoint: Water Balance Error)
- [ ] Add markdown explaining checkpoint
- [ ] Create code cell:
  ```python
  from shared_functions import check_task_with_solution
  check_task_with_solution("task04_checkpoint_4")
  ```
- [ ] **TEST: Execute checkpoint widget**
  - [ ] Verify question displays
  - [ ] Test with your model's error value
  - [ ] Confirm "Correct!" feedback appears
  - [ ] Check "Show Solution" button works

### Cell 7.4 (Simulated vs. Observed Heads)
- [ ] Add markdown about uncalibrated models
- [ ] Create `get_heads_at_observation_wells()` function (reuse from 6.6)
- [ ] Create code cell:
  - [ ] Load observation data from CSV
  - [ ] Extract simulated heads at observations
  - [ ] Create comparison DataFrame
  - [ ] Calculate MAE, RMSE
  - [ ] Display table with residuals
  - [ ] Interpretation text about uncalibrated mismatch
- [ ] **TEST: Execute and verify comparison**
  - [ ] Check observation count (typically 5-15 wells)
  - [ ] Verify all wells have both observed and simulated values
  - [ ] Confirm MAE/RMSE values are reasonable
  - [ ] Ensure residuals show ~10-50cm typical mismatch

### Cell 7.5 (Checkpoint: River Gaining/Losing)
- [ ] Add markdown with conceptual question
- [ ] Create code cell:
  ```python
  from shared_functions import check_task_with_solution
  check_task_with_solution("task04_checkpoint_5")
  ```
- [ ] **TEST: Execute checkpoint widget**
  - [ ] Verify question displays correctly
  - [ ] Test with "gaining" or "losing" answer
  - [ ] Confirm solution explanation appears

### Cell 7.6 (Discussion: Uncalibrated Model)
- [ ] Add markdown explaining mismatch sources:
  - [ ] K uncertainty (±50%)
  - [ ] River conductance (×10)
  - [ ] Recharge estimation
  - [ ] Geometry simplification
- [ ] Explain what calibration does
- [ ] State "models are hypotheses to be tested"
- [ ] No code required

### Cell 7.7 (Optional: Output Files Deep Dive)
- [ ] Create collapsible `<details>` section
- [ ] Add markdown:
  - [ ] Description of .hds file (binary heads)
  - [ ] Description of .cbb file (budget)
  - [ ] Description of .lst file (convergence)
  - [ ] Example code for accessing files
  - [ ] Link to MODFLOW documentation
- [ ] No code execution required

---

## Phase 4: Section 8 Implementation (30 min)

### Cell 8.1 (Key Takeaways)
- [ ] Add markdown bullet list:
  - [ ] Model implementation successful
  - [ ] Water balance closes (confirms BC assignment)
  - [ ] Mismatch with observations reveals uncertain parameters
  - [ ] MODFLOW 6 handles nonlinear problems well
- [ ] No code required

### Cell 8.2 (Why Calibration Is Essential)
- [ ] Add markdown explaining:
  - [ ] Forward vs inverse modeling
  - [ ] Mismatch as diagnostic information
  - [ ] Parameters controlling flow budget
  - [ ] Objective function concept
  - [ ] Equifinality problem
- [ ] No code required

### Cell 8.3 (Reflection Prompt)
- [ ] Add markdown with open-ended reflection question
- [ ] Ask what students found challenging
- [ ] Encourage written response (can be in discussion, not graded)
- [ ] No code required

### Cell 8.4 (Save Simulation)
- [ ] Add markdown explaining checkpoint save
- [ ] Create code cell with `pickle.dump(sim, file)`
  - [ ] Save to `notebook4_uncalibrated_sim.pkl`
- [ ] Include try/except error handling
- [ ] Print save path and file size
- [ ] Note that Notebook 5 will load this file
- [ ] **TEST: Execute and verify save**
  - [ ] Check that `notebook4_uncalibrated_sim.pkl` file exists
  - [ ] Note file size
  - [ ] Verify file can be loaded with `pickle.load()`

### Cell 8.5 (Preview: Notebook 5)
- [ ] Add markdown:
  - [ ] Brief description of calibration (4-5 points)
  - [ ] What students will learn
  - [ ] Next steps: objective function, optimization, validation
  - [ ] Navigation links to Notebook 5
- [ ] Include navigation banner (< Notebook 3 | Notebook 5 >)
- [ ] No code required

---

## Phase 5: Integration & Testing (2 hours)

### Integration
- [ ] Link from Section 5 (BCs) to Section 6 via navigation
- [ ] Check that all code cells reference correct objects (gwf, sim, modelgrid)
- [ ] Verify imports at top of notebook include:
  - [ ] `flopy.utils`, `flopy.mf6`
  - [ ] `shared_functions.check_task_with_solution`
  - [ ] `pickle`, `pathlib.Path`
- [ ] Ensure data paths are correct throughout

### Execution Testing
- [ ] Run Section 6 end-to-end
  - [ ] 6.3: Prediction entry works
  - [ ] 6.4: Model runs successfully
  - [ ] 6.5: Convergence check completes
  - [ ] 6.6: Prediction comparison displays

- [ ] Run Section 7 end-to-end
  - [ ] 7.1: Head map displays correctly
  - [ ] 7.2: Budget table shows major flows
  - [ ] 7.3: Checkpoint widget works
  - [ ] 7.4: Comparison shows observations
  - [ ] 7.5: Conceptual checkpoint works

- [ ] Run Section 8 end-to-end
  - [ ] 8.4: Simulation saves to pickle file
  - [ ] 8.5: Navigation links work

### Content Verification
- [ ] No emojis in section headers
- [ ] [BLACK BOX] vs [UNDERSTAND THIS] labels consistent
- [ ] Code comments explain infrastructure vs concepts
- [ ] Markdown uses `>` for emphasis, not bold where inappropriate
- [ ] All references to figures/tables are accurate
- [ ] Learning objectives in Section 7 intro are met

### Timing Validation
- [ ] **Full notebook execution time: __________ minutes**
  - [ ] Core content (no model run): ~15 minutes
  - [ ] With model execution: ~25 minutes
  - [ ] Target: < 30 minutes total
- [ ] Note slow sections for optimization if needed

---

## Phase 6: Documentation (1 hour)

### Code Documentation
- [ ] Add docstrings to all custom functions
- [ ] Include parameter descriptions and return types
- [ ] Add example usage in docstrings

### Notebook README/Overview
- [ ] Update notebook title and description
- [ ] Add learning objectives section
- [ ] Add time estimate
- [ ] Add prerequisites
- [ ] Add data requirements
- [ ] Add navigation (< Section 5 | Section 6+ >)

### Supporting Documentation
- [ ] Update main README with Notebook 4 changes
- [ ] Document data preprocessing (if not already done)
- [ ] Add troubleshooting guide section
- [ ] Note FloPy version requirement (>=3.4.0)

---

## Phase 7: Final QA/Testing (1 hour)

### Execution Quality
- [ ] Run fresh notebook on clean JupyterHub instance
- [ ] Run fresh notebook on local Jupyter installation
- [ ] Verify all plots render correctly
- [ ] Confirm all calculations are correct

### Content Quality
- [ ] Proofread all markdown (spelling, grammar)
- [ ] Verify all math equations render correctly
- [ ] Check that all code is syntactically correct
- [ ] Confirm all imports work

### User Experience
- [ ] Test all checkpoints with multiple answer values
  - [ ] Correct answers in range
  - [ ] Incorrect answers outside range
  - [ ] Edge cases (0, very large numbers)
- [ ] Verify error messages are helpful
- [ ] Check that "Show Solution" buttons work

### Assessment
- [ ] At least 3 students/TAs test sections
- [ ] Collect feedback on clarity and pacing
- [ ] Verify checkpoint answer ranges are appropriate
- [ ] Adjust ranges if needed (document changes)

---

## Phase 8: Version Control & Deployment

### Git Workflow
- [ ] Commit content in logical chunks:
  - [ ] Section 6 complete
  - [ ] Section 7 complete
  - [ ] Section 8 complete
  - [ ] Checkpoints integrated
- [ ] Write clear commit messages:
  ```
  Add Section 6-8 content to Notebook 4

  - Solver configuration and model execution
  - Prediction exercise before running
  - Water balance summary and checkpoint
  - Head comparison analysis
  - Conceptual checkpoints for calibration motivation
  - Saves uncalibrated model for Notebook 5

  Implementation per notebook4_improvement_plan.md
  ```
- [ ] Create pull request for review

### Code Review Checklist
- [ ] Someone else reviews sections 6-8
  - [ ] Content is correct and complete
  - [ ] Code runs without errors
  - [ ] Timing targets are met
  - [ ] Learning objectives are clear
- [ ] Reviewer approves PR
- [ ] Merge to main branch

### Deployment
- [ ] Update on JupyterHub
- [ ] Test on JupyterHub with student accounts
- [ ] Create release notes (if applicable)
- [ ] Communicate updates to students

---

## Documentation Deliverables

By end of implementation, should have:

- [ ] Completed notebook with Sections 6-8
- [ ] Updated `tasks_data.py` with checkpoint data
- [ ] Updated `requirements.txt` (if FloPy version changed)
- [ ] Updated main README
- [ ] Troubleshooting guide (in _SUPPORT/docs/)
- [ ] Data requirements documentation
- [ ] Design documents (already completed)

---

## Sign-Off

**Implementer:** ________________________ **Date:** __________

**Reviewer:** ________________________ **Date:** __________

**QA Tester:** ________________________ **Date:** __________

---

## Notes & Issues

### Issues Encountered

| Issue | Resolution | Status |
|-------|-----------|--------|
| | | |
| | | |

### Deviations from Design

| Original Spec | Actual Implementation | Reason |
|---------------|----------------------|--------|
| | | |
| | | |

### Performance Notes

- **Model execution time:** __________ seconds
- **Slowest cell:** __________ (Section __)
- **Total notebook time:** __________ minutes

### Lessons Learned

(For next iteration or similar notebooks)

1.
2.
3.

---

**Last Updated:** __________ **By:** __________
