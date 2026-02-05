# Notebook 4 Sections 6-8 Design Package

**Complete design documentation for Sections 6, 7, and 8 of the redesigned Notebook 4 (Model Implementation)**

**Created:** February 5, 2026
**Status:** COMPLETE - Ready for Implementation (Review Completed 2026-02-05)
**Total Documentation:** ~2,470 lines | ~83 KB

---

## What's Included

This package contains **4 comprehensive design documents** that together provide:
- Complete markdown and code content (copy-paste ready)
- Pedagogical framework with learning objectives
- Assessment strategy with checkpoints
- Implementation workflow and timing
- Quality assurance checklist

### Document Overview

| Document | Size | Purpose | Primary Audience |
|----------|------|---------|-----------------|
| **notebook4_sections_6-8.md** | 30 KB | Full design with pedagogy | Instructors, designers |
| **notebook4_sections_6-8_code_reference.md** | 22 KB | Ready-to-use code cells | Developers, implementers |
| **notebook4_checkpoint_data.md** | 16 KB | Assessment framework | TAs, graders |
| **notebook4_sections_6-8_SUMMARY.md** | 16 KB | Executive summary | Project managers |
| **IMPLEMENTATION_CHECKLIST.md** | 15 KB | Phase-by-phase guide | Project leads |
| **PREREQUISITES.md** | 8 KB | Required setup before implementation | **READ FIRST** |
| **REVIEW_NOTEBOOK4_SECTIONS_6-8.md** | Review findings | Consolidated review from 10 expert agents with prioritized fixes |
| **README_NOTEBOOK4_SECTIONS_6-8.md** | This file | Navigation and overview | Everyone |

---

## Review Status

This design package was reviewed on 2026-02-05 using 10 specialized review agents.
See **REVIEW_NOTEBOOK4_SECTIONS_6-8.md** for the original review findings.

**Critical Fixes Applied (2026-02-05):**
- ✅ Function signatures standardized across all documents
- ✅ FloPy API errors fixed (HeadFile, PlotMapView, DISV indexing)
- ✅ Checkpoint ranges reconciled with tasks_data.py
- ✅ Cell 7.4 indexing bug fixed in code reference
- ✅ PREREQUISITES.md created documenting all implicit assumptions
- ✅ Multiple-choice widget specification added for checkpoint 5

**Overall Assessment:** Ready for implementation after completing prerequisites.
**Important:** Read **PREREQUISITES.md** first - data files and Sections 1-5 must be prepared.

---

## Quick Start

### For Project Leads
1. Read: **notebook4_sections_6-8_SUMMARY.md** (10 min)
   - Understand overall structure and timing
   - Review implementation workflow
   - Check dependencies and data files
2. Assign: **IMPLEMENTATION_CHECKLIST.md** (ongoing)
   - Provides phase-by-phase tracking
   - Includes testing protocols
3. Reference: **notebook4_improvement_plan.md** (existing)
   - Context on why these changes

### For Content Developers
1. Read: **notebook4_sections_6-8.md** (30 min)
   - Understand full narrative flow
   - See pedagogical choices and rationale
   - Review learning objectives
2. Use: **notebook4_sections_6-8_code_reference.md** (ongoing)
   - Copy-paste code into notebook cells
   - Adapt to your data paths
   - Test each section

### For Assessment/TAs
1. Read: **notebook4_checkpoint_data.md** (20 min)
   - Understand checkpoint questions
   - Learn acceptable answer ranges
   - See solution explanations
2. Implement: Add to `tasks_data.py`
   - 2 required checkpoints
   - 3 optional checkpoints

### For Quality Assurance
1. Use: **IMPLEMENTATION_CHECKLIST.md** (ongoing)
   - Phase-by-phase validation
   - Testing protocols
   - Sign-off tracking

---

## File Locations

All design documents are located in:
```
/Users/bea/Documents/GitHub/applied_groundwater_modelling/DESIGN_DOCS/
```

Implementation will modify:
```
/Users/bea/Documents/GitHub/applied_groundwater_modelling/PROJECT/flow/4_model_implementation.ipynb
```

Support files to update:
```
_SUPPORT/src/scripts/scripts_exercises/tasks_data.py
requirements.txt (if needed)
README.md (project root)
```

---

## Document Descriptions

### 1. notebook4_sections_6-8.md

**Complete markdown and code specifications**

Contains:
- Full markdown text for all 8 subsections
- Code cell specifications with explanations
- Code comments explaining [BLACK BOX] vs [UNDERSTAND THIS]
- Pedagogical rationale for each choice
- Learning objectives and timing targets
- Implementation notes

**Use when:**
- Understanding pedagogical design choices
- Getting context on why code is structured a certain way
- Adapting content for your institution
- Training other instructors

**Sample sections:**
- Section 6: Solver and Run (7 min target)
  - 6.1: IMS Solver Configuration
  - 6.2: Output Control Settings
  - 6.3: Prediction Exercise (before running model)
  - 6.4: Run Simulation
  - 6.5: Check Convergence
  - 6.6: Compare Predictions to Results

- Section 7: Initial Results (7 min target)
  - 7.1: Head Distribution Map
  - 7.2: Water Balance Summary
  - 7.3: Checkpoint - Water Balance Error
  - 7.4: Simulated vs. Observed Heads
  - 7.5: Checkpoint - River Gaining/Losing
  - 7.6: Discussion of Uncalibrated Model
  - 7.7: Optional Deep Dive - Output Files

- Section 8: Summary and Next Steps (2 min target)
  - 8.1: Key Takeaways
  - 8.2: Why Calibration Is Essential
  - 8.3: Reflection Prompt
  - 8.4: Save Simulation for Notebook 5
  - 8.5: Preview of Notebook 5

---

### 2. notebook4_sections_6-8_code_reference.md

**Copy-paste ready code cells**

Contains:
- All code blocks extracted and organized by section
- Minimal narrative (focus on implementation)
- Import statements and dependencies clearly noted
- Error handling and edge cases
- Inline comments for complex logic
- No external dependencies beyond FloPy

**Use when:**
- Directly implementing code into notebook
- Testing and debugging
- Adapting to your specific data paths
- Quick reference for function signatures

**Code includes:**
- `check_model_convergence(sim)` - Extract convergence info
- `get_heads_at_observation_wells(gwf, modelgrid, coords)` - Extract heads at points
- `plot_head_distribution(gwf, modelgrid, boundary_gdf)` - Visualize heads
- `format_budget_summary(gwf, verbose)` - Calculate water balance
- Complete prediction comparison logic
- Simulated vs. observed analysis

---

### 3. notebook4_checkpoint_data.md

**Assessment framework and checkpoint definitions**

Contains:
- 2 required checkpoints (task04_checkpoint_4, task04_checkpoint_5)
- 3 optional checkpoints (task04_checkpoint_1,2,3)
- Acceptable answer ranges with tolerance justification
- Solution explanations (learning-focused)
- Integration instructions for tasks_data.py
- Grading guidance
- Expected student answers and common misconceptions

**Key checkpoints:**

| ID | Section | Type | Content |
|----|---------|------|---------|
| task04_checkpoint_4 | 7.3 | Numerical | Water balance error (%) |
| task04_checkpoint_5 | 7.5 | Conceptual | River gaining/losing |
| task04_checkpoint_1* | 6.1 | Numerical | Active cell count |
| task04_checkpoint_2* | 6.2 | Numerical | Average aquifer thickness |
| task04_checkpoint_3* | 6.3 | Numerical | Total recharge flux |

*Optional - can be added if desired

**Use when:**
- Adding checkpoints to tasks_data.py
- Setting up assessment infrastructure
- Grading student responses
- Adjusting tolerance ranges

---

### 4. notebook4_sections_6-8_SUMMARY.md

**Executive summary and implementation guide**

Contains:
- Overview of pedagogical approach
- Structural highlights of each section
- Implementation workflow (5 phases)
- Data dependencies and files
- Assessment strategy
- Timing breakdown
- Potential adaptations for different needs
- Integration points with other notebooks
- Troubleshooting guide
- Quality checklist
- Files to modify

**Use when:**
- Getting bird's-eye view of design
- Understanding pedagogical choices
- Planning implementation timeline
- Checking what data files are needed
- Troubleshooting common issues

**Key sections:**
- Pedagogical approach table
- 5-phase implementation workflow
- Data dependency matrix
- Timing breakdown (core vs. execution time)
- Quality assurance checklist
- Integration points with Notebooks 3 and 5

---

### 5. IMPLEMENTATION_CHECKLIST.md

**Detailed phase-by-phase implementation checklist**

Contains:
- Pre-implementation setup (environment, data, docs)
- Phase 1: Checkpoint integration (30 min)
- Phase 2: Section 6 implementation (1 hour)
- Phase 3: Section 7 implementation (1.5 hours)
- Phase 4: Section 8 implementation (30 min)
- Phase 5: Integration & testing (2 hours)
- Phase 6: Documentation (1 hour)
- Phase 7: Final QA/testing (1 hour)
- Phase 8: Version control & deployment
- Sign-off tracking
- Issue tracking table

**Use when:**
- Actively implementing sections
- Tracking progress (mark checkboxes)
- Assigning tasks to team members
- Testing implementation
- Ensuring quality standards

**Template format:**
- ✓ Checkbox format for easy tracking
- Specific, actionable items
- Success criteria listed
- Testing instructions included
- Time estimates for each phase

---

## Key Design Features

### Pedagogical Approach
- **Prediction Exercise**: Students predict heads before running model → compare to results
- **Code Labeling**: [BLACK BOX] for infrastructure, [UNDERSTAND THIS] for concepts
- **Active Checkpoints**: 2 required, 3 optional with auto-grading framework
- **Motivation for Next Steps**: Results show mismatch → leads to calibration

### Content Balance
- **Core (mandatory):** ~15 min reading + analysis
- **Execution:** ~10 min model run (depends on grid size)
- **Interpretation:** ~5 min checkpoint and discussion
- **Total:** ~30 min (within target)

### No External Dependencies
- All code uses FloPy >= 3.4.0 standard utilities
- No custom grid_utils or complex helper modules needed
- Minimal imports (numpy, pandas, matplotlib, geopandas, flopy)

### MODFLOW 6 / DISV Alignment
- Uses flopy.mf6 API (modern, well-maintained)
- Demonstrates unstructured grid visualization
- Shows water balance interpretation on DISV grids
- Bridges to Notebook 5 (calibration)

---

## Implementation Timeline

**Estimated Total:** 8-10 hours (phased implementation)

| Phase | Task | Duration | Prerequisite |
|-------|------|----------|--------------|
| 0 | Setup & review | 1 hour | None |
| 1 | Checkpoints → tasks_data.py | 0.5 hour | Phase 0 |
| 2 | Section 6 code | 1 hour | Phase 1 |
| 3 | Section 7 code | 1.5 hours | Phase 2 |
| 4 | Section 8 code | 0.5 hour | Phase 3 |
| 5 | Integration & testing | 2 hours | Phase 4 |
| 6 | Documentation | 1 hour | Phase 5 |
| 7 | QA & testing | 1 hour | Phase 6 |
| 8 | Version control | 0.5 hour | Phase 7 |
| **Total** | | **~8-10 hours** | |

---

## Data Requirements

### Input Files (Pre-processed)
```
_SUPPORT/processed_data/
├── model_boundary.gpkg          # Domain polygon for grid
├── observation_data.csv         # Well locations & measured heads
├── river_geometry.gpkg          # River reaches (for Section 5 BCs)
├── well_geometry.gpkg           # Well locations (for Section 5 BCs)
├── dem_resampled.tif            # Model top surface
└── aquifer_bottom.tif           # Model bottom surface
```

### Output Files (Created)
```
_SUPPORT/model_checkpoints/
└── notebook4_uncalibrated_sim.pkl    # Simulation checkpoint for Notebook 5

notebook4_model/
└── [MODFLOW output files]            # Auto-generated during model run
```

---

## Testing Protocol

### Minimal Testing
- [ ] Code executes without syntax errors
- [ ] Model converges successfully
- [ ] Plots display correctly
- [ ] Checkpoints work with sample answers

### Standard Testing (Recommended)
- All of minimal, plus:
- [ ] Fresh JupyterHub test run
- [ ] Timing validation (core < 16 min)
- [ ] 3+ students/TAs review content
- [ ] Checkpoint ranges validated

### Comprehensive Testing
- All of standard, plus:
- [ ] Local Jupyter installation test
- [ ] Multiple data scenarios tested
- [ ] Edge case handling verified
- [ ] Accessibility review (alt text, clarity)

---

## Expected Learning Outcomes

After completing Sections 6-8, students should be able to:

**Section 6 (Solver and Run):**
- Explain what the IMS solver does (Newton-Raphson iteration)
- Predict groundwater heads based on boundary conditions and aquifer properties
- Interpret convergence messages and troubleshoot non-convergence
- Appreciate that model predictions differ from observations

**Section 7 (Initial Results):**
- Visualize simulated heads on unstructured grids
- Interpret water balance budget (inflows, outflows, closure)
- Identify parameter uncertainty from observation mismatch
- Determine whether rivers are gaining or losing

**Section 8 (Summary):**
- Articulate why calibration is necessary (observations < 50cm mismatch)
- Understand trade-offs in model complexity and accuracy
- Recognize that models are hypotheses to be tested
- Appreciate role of inverse modeling (Notebook 5)

---

## Common Issues & Solutions

### During Implementation

| Issue | Solution |
|-------|----------|
| "HeadFile not found" | Model didn't run - check convergence error in .lst file |
| Coordinate mismatch | Verify observation well CRS matches model grid |
| Water balance error > 1% | Missing/incorrect BC package - verify all 5 active |
| Slow model execution | Grid too fine - expect 2-10 sec for ~5000 cells |
| Checkpoint answers out of range | Run your model, record actual value, adjust tolerance |

### During Testing

| Issue | Solution |
|-------|----------|
| Plots don't render | Check matplotlib backend; verify data exists |
| Import errors | Verify FloPy >= 3.4.0; check sys.path additions |
| Checkpoint widget fails | Verify task_id matches tasks_data.py exactly |
| Low first-attempt success | Ranges may be too strict - check ±10% tolerance |

---

## How to Navigate the Documents

### Reading Sequence

**If you have 1 hour:**
1. Read SUMMARY (15 min) - Overview
2. Skim CHECKLIST (15 min) - Timeline
3. Scan DESIGN document sections headings (15 min) - Spot check
4. Start implementation

**If you have 2 hours:**
1. Read SUMMARY (15 min)
2. Read CHECKPOINT DATA (20 min)
3. Read DESIGN document (45 min)
4. Review CODE REFERENCE (20 min)
5. Start implementation

**If you have 4+ hours:**
1. Read all documents in order
2. Study CODE REFERENCE in detail
3. Run code cells locally before integration
4. Plan implementation phases
5. Begin Phase 1 with full understanding

---

## Coordination with Other Components

### Upstream Dependencies (Section 5)
- Requires: gwf, sim, modelgrid objects
- Requires: Boundary conditions fully defined (CHD, RIV, WEL, RCH)
- Requires: MODFLOW 6 simulation structure created

### Downstream Handoff (Section 8 → Notebook 5)
- Provides: Pickled sim object (`notebook4_uncalibrated_sim.pkl`)
- Provides: Observation well locations and measured heads
- Provides: Initial parameter estimates (K, river conductance)
- Provides: Head distribution visualization for comparison

### Related Notebooks
- **Notebook 3:** Introduces MODFLOW 6 concepts, DISV grids, CVFD
- **Notebook 5:** Loads sim from Notebook 4, performs calibration
- **Case Studies:** Use grid refinement with same BC geometries

---

## File Manifest

```
DESIGN_DOCS/
├── notebook4_sections_6-8.md              (30 KB) Full design
├── notebook4_sections_6-8_code_reference.md (22 KB) Code cells
├── notebook4_checkpoint_data.md           (16 KB) Assessments
├── notebook4_sections_6-8_SUMMARY.md      (16 KB) Executive summary
├── IMPLEMENTATION_CHECKLIST.md            (15 KB) Phase-by-phase guide
└── README_NOTEBOOK4_SECTIONS_6-8.md       This file
```

**Total:** ~99 KB, 2,470 lines of documentation

---

## Author & Attribution

**Design:** Applied Groundwater Modelling Course Team (February 2026)
**Framework:** Based on notebook4_improvement_plan.md comprehensive redesign
**Implementation Guide:** Ready for any course maintainer to execute

**For questions or updates:**
1. Refer to original improvement_plan.md for context
2. Check shared_functions.py for checkpoint infrastructure
3. Review existing Notebooks 2-3 for style consistency

---

## Version Control

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 5, 2026 | Complete design package |

All design documents are ready for use and versioning in git.

---

**Next Steps:** Begin with Phase 1 of IMPLEMENTATION_CHECKLIST.md
