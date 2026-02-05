# Design Review: Notebook 4 Sections 6-8

**Review Date:** 2026-02-05
**Review Method:** 10 parallel expert agents
**Overall Assessment:** Ready for implementation with critical fixes required

---

## ✅ FIXES APPLIED (2026-02-05)

The following critical issues from this review have been addressed:

| Issue | Status | Fix Applied |
|-------|--------|-------------|
| FloPy API Errors (HeadFile, totim) | ✅ FIXED | Updated `notebook4_sections_6-8.md` to use `gwf.output.head().get_data()` |
| DISV Grid Indexing | ✅ FIXED | Updated to use correct 2D indexing `heads[0, cell_id]` |
| PlotMapView Usage | ✅ FIXED | Changed from non-existent `modelgrid.plot()` to `PlotMapView(model=gwf).plot_array()` |
| Function Signature Mismatch | ✅ FIXED | Standardized across all documents |
| Pickle Filename Inconsistency | ✅ N/A | Already consistent (`notebook4_uncalibrated_sim.pkl`) |
| Checkpoint 3 Range Error | ✅ FIXED | Updated IMPLEMENTATION_CHECKLIST to (4500, 5500) |
| Multiple-Choice Widget | ✅ DOCUMENTED | Added implementation spec to `notebook4_checkpoint_data.md` |
| Cell 7.4 Indexing Bug | ✅ FIXED | Fixed in `notebook4_sections_6-8_code_reference.md` |

**New Documents Created:**
- `PREREQUISITES.md` - Documents all implicit assumptions (data files, FloPy version, Sections 1-5 requirements)

**Remaining Prerequisites (not code fixes):**
- Create `_SUPPORT/processed_data/` directory with 6 required data files
- Implement `create_multiple_choice()` in `shared_functions.py`
- Rewrite Notebook 4 Sections 1-5 for MODFLOW 6 / DISV

---

## Executive Summary

The design documents for Notebook 4 Sections 6-8 are comprehensive and pedagogically sound (4.4/5 course alignment score), but contain several critical code errors that would cause runtime failures. This review consolidates findings from 10 specialized review agents.

---

## Critical Issues (Must Fix Before Implementation)

### 1. FloPy API Errors

**Issue:** HeadFile access pattern is incorrect throughout code reference.

```python
# WRONG (will fail):
heads = flopy.utils.HeadFile(head_file).get_ts(0)
heads[0][0, row, col]

# CORRECT:
heads = gwf.output.head().get_data()
heads[0, cell_id]  # For DISV grids
```

**Files to fix:** `notebook4_sections_6-8_code_reference.md` (Cells 6.6, 7.1, 7.4)

### 2. DISV Grid Indexing

**Issue:** Head array indexing assumes structured grid.

```python
# WRONG for DISV:
simulated_head = heads[0, 0, cell_id]  # 3D indexing

# CORRECT for DISV:
simulated_head = heads[0, cell_id]  # 2D: (nlay, ncpl)
```

**Files to fix:** `notebook4_sections_6-8_code_reference.md`

### 3. Steady-State Time Reference

**Issue:** `totim=0.0` returns initial conditions, not steady-state solution.

```python
# WRONG:
heads = head_obj.get_data(totim=0.0)

# CORRECT:
heads = head_obj.get_data()  # Returns last time step (steady-state result)
# OR explicitly:
heads = head_obj.get_data(totim=head_obj.get_times()[-1])
```

**Files to fix:** `notebook4_sections_6-8_code_reference.md` (multiple cells)

### 4. PlotMapView for Visualization

**Issue:** `modelgrid.plot(array=...)` method doesn't exist.

```python
# WRONG:
pc = modelgrid.plot(ax=ax, array=head_2d, cmap='viridis')

# CORRECT:
from flopy.plot import PlotMapView
pmv = PlotMapView(model=gwf, ax=ax)
pc = pmv.plot_array(head_2d, cmap='viridis')
```

**Files to fix:** `notebook4_sections_6-8_code_reference.md` (Cell 7.1)

### 5. Pickle Filename Inconsistency

**Issue:** Two different filenames used across documents.

| Document | Filename Used |
|----------|---------------|
| notebook4_sections_6-8.md (line 731) | `notebook4_initial_sim.pkl` |
| notebook4_sections_6-8_code_reference.md | `notebook4_uncalibrated_sim.pkl` |
| notebook4_sections_6-8_SUMMARY.md | `notebook4_uncalibrated_sim.pkl` |
| DELIVERABLES.txt | `notebook4_uncalibrated_sim.pkl` |

**Resolution:** Standardize to `notebook4_uncalibrated_sim.pkl`

### 6. Checkpoint 3 Range Error

**Issue:** Acceptable range doesn't match calculated expected value.

- **Documented calculation:** 0.3 mm/day × 17 km² = 5,100 m³/day
- **Acceptable range:** 2,500-4,000 m³/day
- **Problem:** Students with correct understanding will fail checkpoint

**Resolution:** Either update range to (4,500, 5,500) or clarify why total is lower (inactive cells, etc.)

**Files to fix:** `notebook4_checkpoint_data.md`

### 7. Multiple-Choice Widget Not Implemented

**Issue:** `shared_functions.py` only supports `FloatText` widgets, but checkpoint 5 requires multiple-choice.

**Resolution:** Add `create_multiple_choice()` function to `shared_functions.py`

---

## High Priority Issues

### 8. Checkpoint Data Discrepancies with tasks_data.py

| Checkpoint | Checklist Range | tasks_data.py Range | Status |
|------------|-----------------|---------------------|--------|
| checkpoint_1 (cells) | 4,500-5,500 | (4500, 5500) | Match |
| checkpoint_2 (thickness) | 5.0-8.0 m | (13, 22) | **Mismatch** |
| checkpoint_3 (recharge) | 2,500-4,000 | (4500, 5500) | **Mismatch** |
| checkpoint_4 (error) | 0.0-0.15% | (0, 1) | Checklist stricter |
| checkpoint_6 | Not in checklist | Present in code | **Missing** |

**Resolution:** Run actual model to determine correct values, update both files

### 9. Function Signatures in SUMMARY.md

**Issue:** Signatures don't match main design document.

| Function | SUMMARY says | Main doc says |
|----------|--------------|---------------|
| `get_heads_at_observation_wells()` | `(gwf, modelgrid, observation_coords)` | `(gwf, observation_locations)` |
| `format_budget_summary()` | `(gwf, verbose)` | `(gwf, sim, significant_figures=1)` |

**Files to fix:** `notebook4_sections_6-8_SUMMARY.md`

### 10. Missing Equations

**Issue:** Key hydrogeology equations not provided.

**Add to Section 7.2 (Water Balance):**
$$\sum Q_{in} - \sum Q_{out} = 0$$
$$\epsilon_{balance} = \frac{|Q_{in} - Q_{out}|}{Q_{in}} \times 100\%$$

**Add to Section 7.5 (River Exchange):**
$$Q_{riv} = C_{riv} \cdot (h_{riv} - h_{aquifer})$$

**Add to Section 6.1 (Newton-Raphson):**
Boussinesq equation showing nonlinearity: $T = Kh$

### 11. Stress Period Numbering

**Issue:** Document says stress period is "0" for steady-state.

**Correction:** MODFLOW 6 uses 1-based indexing (stress period 1, time step 1). Python/FloPy uses 0-based for array access.

**Files to fix:** `notebook4_sections_6-8.md` (Section 6.4)

---

## Medium Priority Issues

### 12. Missing Learning Objectives

**Add to start of Section 6:**
```markdown
## Learning Objectives

By the end of this section, you will be able to:
1. **Configure** the IMS solver with appropriate convergence tolerances
2. **Execute** a MODFLOW 6 simulation and interpret convergence status
3. **Evaluate** water balance closure as a model quality indicator
4. **Compare** simulated heads to observations and explain mismatch sources
5. **Determine** whether a river reach is gaining or losing from budget analysis
```

### 13. Missing Progress Tracker Integration

**Add at end of Section 6:**
```python
from progress_tracking import create_model_implementation_step_completion_marker
create_model_implementation_step_completion_marker(6)
```

**Add at end of Section 7:**
```python
create_model_implementation_step_completion_marker(7)
```

### 14. Missing Misconception Callouts

Add these callout boxes throughout:

> **Common Misconception:** "Steady state means nothing is happening."
> **Reality:** Steady state means ∂h/∂t = 0, but water is continuously flowing.

> **Common Misconception:** "If my water balance closes, my model is correct."
> **Reality:** Water balance closure only confirms mass conservation numerically, not physical accuracy.

> **Common Misconception:** "I should minimize residuals as much as possible."
> **Reality:** Over-fitting leads to unrealistic parameters. Target residuals ≈ measurement error.

### 15. Anisotropy Caveat for Flow Direction

**Current text (Section 7.1):**
> "Flow directions (perpendicular to head contours, from high to low head)"

**Should be:**
> "Flow directions: In **isotropic** aquifers, flow is perpendicular to head contours. In anisotropic aquifers, flow deflects toward the principal direction of maximum conductivity."

### 16. Variable Shadowing Bug

**Issue in Cell 7.4:**
```python
for idx, row in obs_data.iterrows():
    ...
    if isinstance(cell_info, (tuple, list)):
        row, col = cell_info  # SHADOWS loop variable!
```

**Fix:**
```python
for idx, obs_row in obs_data.iterrows():
    ...
    if isinstance(cell_info, (tuple, list)):
        i, j = cell_info
```

### 17. Missing Lecture References

**Add to Section 6.3 (Prediction Exercise):**
> Reference: Week 2-3 slides on hydraulic head and gradients

### 18. Timing Inconsistencies

| Document | Section 7 Time | Total Time |
|----------|----------------|------------|
| Main design doc | 7 min | ~16 min |
| SUMMARY | 7 min | ~15-16 min |
| DELIVERABLES | 8 min | 16-18 min |

**Resolution:** Standardize to "7-8 min" for Section 7, "16-18 min" total

---

## Pedagogical Recommendations

### From Course Context Review (Score: 4.4/5)

1. **Link checkpoints to rubric criteria** explicitly
2. **Add peer learning opportunity** - discussion prompt for prediction comparison
3. **Add local context paragraph** explaining Limmat Valley importance to Zurich water supply

### From Pedagogy Review

1. **Add hint accordions** before challenging checkpoints
2. **Add internal navigation** (mini TOC) for Section 7
3. **Convert prediction exercise** to widget pattern for consistency
4. **Add diagnostic feedback** explaining common errors in checkpoint solutions

---

## Files Requiring Modification

| File | Priority | Changes |
|------|----------|---------|
| `notebook4_sections_6-8_code_reference.md` | Critical | Fix all FloPy API calls, DISV indexing, totim |
| `notebook4_sections_6-8.md` | High | Add equations, fix stress period, add objectives |
| `notebook4_checkpoint_data.md` | High | Fix checkpoint 3 range, clarify checkpoint 5 |
| `notebook4_sections_6-8_SUMMARY.md` | High | Fix function signatures, filename |
| `IMPLEMENTATION_CHECKLIST.md` | Medium | Add checkpoint_6, fix double checkboxes |
| `shared_functions.py` | High | Add multiple-choice widget support |
| `tasks_data.py` | High | Reconcile checkpoint ranges |

---

## Review Agent Summary

| Agent | Focus | Key Findings |
|-------|-------|--------------|
| 1 | FloPy technical (main doc) | HeadFile API, DISV indexing, pickle issues |
| 2 | FloPy code reference | totim=0.0, PlotMapView, variable shadowing |
| 3 | Hydrogeology theory | Missing equations, misconceptions, anisotropy |
| 4 | Checkpoint data | Checkpoint 3 range error, sign convention |
| 5 | Course alignment | 4.4/5 score, rubric mapping needed |
| 6 | Notebook pedagogy | Learning objectives, progress tracker, hints |
| 7 | Implementation checklist | Discrepancies with tasks_data.py |
| 8 | Cross-document consistency | Pickle filename, timing variations |
| 9 | Summary accuracy | Function signatures wrong |
| 10 | README/deliverables | Multiple-choice widget gap |

---

## Conclusion

The design documents demonstrate strong pedagogical design and comprehensive coverage. The critical issues are primarily technical (FloPy API usage) rather than conceptual. Once the critical fixes are applied, the materials will be ready for implementation.

**Recommended Implementation Order:**
1. Fix FloPy API issues in code reference (Critical)
2. Standardize pickle filename across all docs (Critical)
3. Fix/verify checkpoint ranges against actual model (Critical)
4. Add missing equations to main design doc (High)
5. Add pedagogical enhancements (Medium)
