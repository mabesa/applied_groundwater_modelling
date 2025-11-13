# TODO Analysis Report: case_study_transport_group_0.ipynb

**Analysis Date**: 2025-11-13
**Notebook**: `/Users/bea/Documents/GitHub/applied_groundwater_modelling/CASE_STUDY/student_work/group_0/case_study_transport_group_0.ipynb`
**Total TODOs Found**: 33

---

## Section A: TODOs to KEEP (Meaningful Student Tasks)

### A1. Header Information (Cell #0 - Markdown)
**Location**: Cell #0, Lines 13, 15
**TODOs**:
- `TODO: Add your names`
- `**Date**: TODO`

**Status**: Empty template fields
**Recommendation**: **KEEP** - Essential student identification fields

---

### A2. Breakthrough Curve Analysis Template (Cells #85-86)

#### Cell #85 (Markdown) - Learning Objective
**TODO**: `**TODO for Students**: Complete the code blocks below to:`

**Status**: Structured template with clear learning objectives
**Recommendation**: **KEEP** - This is the header for the entire breakthrough curve exercise

#### Cell #86 (Code) - Implementation Tasks
**TODOs** (19 instances):
1. `# TODO 1: Extract concentration time series at well locations` (header)
2. `# TODO: Store the full 4D concentration array`
3. `conc_data = None  # TODO: Replace with ucn.get_alldata()`
4. `# TODO: Create a dictionary of well names and their (layer, row, col) indices`
5. `# TODO: Fill in the dictionary above with at least 3-4 well locations`
6. `# TODO: Create a dictionary storing concentration arrays for each well`
7. `    # TODO: Extract concentration at this location for all time steps`
8. `# TODO 2: Create breakthrough curve plots` (header)
9. `# TODO: Create a figure with subplots (one per well, or all wells on one plot)`
10. `# TODO: Implement the plotting code above`
11. `# TODO 3: Calculate breakthrough times and create summary table` (header)
12. `# TODO: For each well, find the time when concentration first exceeds 5.0 mg/L`
13. `    # TODO: Find index where concentration first exceeds threshold`
14. `    # TODO: Convert index to time in days`
15. `    # TODO: Get maximum concentration reached`
16. `# TODO: Convert summary to DataFrame and display`
17-19. Three checkpoint TODOs at the end

**Status**: Well-structured student coding exercise with skeleton code
**Recommendation**: **KEEP ALL** - This is a complete template exercise with clear scaffolding

---

### A3. Discussion Section Templates (Cell #107 - Markdown)

**TODOs** (6 instances):
1. `**TODO**: Describe the observed TCE plume behavior over the 60-day simulation:`
2. `**TODO**: Analyze the relative importance of advection vs. dispersion:`
3. `**TODO**: Evaluate how pumping/injection wells affected the plume:`
4. `**TODO**: Assess regulatory compliance and contamination risk:`
5. `**TODO**: Interpret the mass balance results:`
6. `**TODO**: Assess how sensitive your results are to advective transport processes:`

**Status**: Structured writing prompts with guiding questions
**Recommendation**: **KEEP ALL** - Clear template for student discussion/analysis

---

### A4. Interpretation Section Templates (Cell #108 - Markdown)

**TODOs** (5 instances):
1. `**TODO**: Evaluate the stability of YOUR simulation results:`
2. `**TODO**: Evaluate mass balance quality:`
3. `**TODO**: Verify that your results make physical sense:`
4. `**TODO**: Summarize the 3-5 most important findings from your transport simulation:`
5. `**TODO**: Critically assess model limitations:`

**Status**: Structured interpretation prompts
**Recommendation**: **KEEP ALL** - Essential for student critical thinking

---

### A5. Conclusions Section (Cell #109 - Markdown)

**TODO**: `**TODO: Write 2-3 paragraphs addressing:**`

**Status**: Writing prompt with 4 specific subtopics
**Recommendation**: **KEEP** - Clear conclusion template

---

### A6. Recommendations Sections (Cells #110-111 - Markdown)

**TODOs** (3 instances):
1. Cell #110: `**TODO**: Provide recommendations for improving future modeling efforts:`
2. Cell #110: `**TODO**: Provide practical recommendations for managing the contamination:`
3. Cell #111: `**TODO: Recommend (bullet points):**`

**Status**: Structured recommendation templates
**Recommendation**: **KEEP ALL** - Important for student application of results

---

### A7. References Section (Cell #113 - Markdown)

**TODO**: `**TODO: Add references for:**`

**Status**: Template for citing sources
**Recommendation**: **KEEP** - Standard academic requirement

---

## Section B: TODOs to REMOVE (Misleading/Already Implemented)

### B1. Well Data Loading (Cell #12 - Code) ⚠️ PROBLEMATIC
**Location**: Cell #12, Line 465
**TODO**: `# TODO: Load well data from case_config.yaml`

**Context**:
```python
# TODO: Load well data from case_config.yaml
# Parse well information
# Separate pumping vs injection wells
# Map to grid coordinates

# Load the rotated model grid for visualization
[...4373 chars of implementation code follows...]
well_data_path = download_named_file(name='wells', data_type='gis')
wells_gdf = gpd.read_file(well_data_path, layer='GS_GRUNDWASSERFASSUNGEN_OGD_P')
```

**Status**: **ALREADY FULLY IMPLEMENTED** - The cell contains 4373 characters of complete code that:
- Loads model grid from pickle file
- Loads well data from GIS file
- Filters wells by concession
- Identifies source location from transport config
- Prints comprehensive verification output

**Recommendation**: **REMOVE** - Misleading instructor note. The TODO suggests students need to implement this, but it's already done.

---

### B2. DSP Package Setup (Cell #64 - Code) ⚠️ PROBLEMATIC
**Location**: Cell #64, Line 5410
**TODO**: `# TODO: Check DSP package`

**Context**:
```python
# TODO: Check DSP package
# Load dispersivity values from config
# al = longitudinal dispersivity
# trpt = ratio of transverse to longitudinal (αT/αL)
# trpv = ratio of vertical to longitudinal (αV/αL)
aL = transport_params['longitudinal_dispersivity_m']
aT = transport_params['transverse_dispersivity_m']
aV = transport_params['vertical_dispersivity_m']
trpt = aT / aL
trpv = aV / aL
dsp = flopy.mt3d.Mt3dDsp(mt, al=aL, trpt=trpt, trpv=trpv)
```

**Status**: **ALREADY FULLY IMPLEMENTED** - Creates DSP package with all parameters
**Recommendation**: **REMOVE** - The word "Check" is ambiguous, and the code is complete. If you want students to verify it, change to "VERIFY: DSP package configuration below:"

---

### B3. Source Location Loading (Cell #70 - Code) ⚠️ PROBLEMATIC
**Location**: Cell #70, Line 5529
**TODO**: `# TODO: Check loading of source location from config`

**Context**:
```python
# TODO: Check loading of source location from config
# source_easting, source_northing from case_config_transport.yaml
# Convert to grid indices (layer, row, col)
# Verify source is within active model domain

# Location relative to pumping well (first in list if cluster)
source_easting = source_config['location']['easting']
source_northing = source_config['location']['northing']
[...1248 chars of complete implementation...]
```

**Status**: **ALREADY FULLY IMPLEMENTED** - Loads source from config, converts to grid indices, prints verification
**Recommendation**: **REMOVE** - Misleading. The code is complete.

---

### B4. Source/Well Visualization (Cell #72 - Code) ⚠️ PROBLEMATIC
**Location**: Cell #72, Line 5584
**TODO**: `# TODO: Create map showing to verify source and well locations`

**Context**:
```python
# TODO: Create map showing to verify source and well locations

# Visualize active cells with wells and source location
fig, ax = plt.subplots(figsize=(10, 8))
pmv = flopy.plot.PlotMapView(modelgrid=submodel_grid, ax=ax)
[...842 chars of plotting code...]
plt.show()
```

**Status**: **ALREADY FULLY IMPLEMENTED** - Complete map with CHD boundaries, wells, and source
**Recommendation**: **REMOVE** - The map is already created.

---

### B5. Mass Balance Extraction (Cell #89 - Code) ⚠️ PROBLEMATIC
**Location**: Cell #89, Line 95852
**TODO**: `# TODO: Extract mass balance from MT3D output`

**Context**:
```python
# TODO: Extract mass balance from MT3D output
# Check cumulative mass balance error
# Flag if error > 1%

# Extract mass balance from MT3D output and verify accuracy
import os
import re
[...4984 chars of complex parsing and analysis code...]
```

**Status**: **ALREADY FULLY IMPLEMENTED** - Sophisticated mass balance parsing from .MAS file with error checking and formatted output
**Recommendation**: **REMOVE** - Completely misleading. This is complex implementation code.

---

### B6. Well Pumping Rate Note (Cell #46 - Code) - PARTIALLY PROBLEMATIC
**Location**: Cell #46, Line 2643
**TODO**: `# TODO: Chose a total pumping/injection rate that is reasonable for your scenario.`

**Context**:
```python
# TODO: Chose a total pumping/injection rate that is reasonable for your
# scenario. It does not need to reflect the concessioned rates but should be
# significant enough to influence plume migration.
well_rates_m3d = 20000
round(well_rates_m3d)
[...rest of well mapping implementation...]
```

**Status**: **RATE ALREADY SET to 20000 m³/d** - But cell has 4765 chars of implementation code
**Issue**: The TODO implies students should choose the rate, but it's already set to 20000. However, students COULD modify this value.

**Recommendation**: **UPDATE** (see Section C) - Change to "NOTE: The rate is set to 20000 m³/d. You may adjust this if needed for your scenario."

---

### B7. Instructor Planning TODOs (Cell #84 - Markdown) ⚠️ HIGHLY PROBLEMATIC
**Location**: Cell #84, Lines 95600-95604
**TODOs** (5 instances - all instructor notes):
1. `TODO: Break through curve at monitoring location - mabye introduce monitoring location further above but students can find this in notebook 4b`
2. `TODO: Ask students to implement that monitoring location to extract the breakthrough curve`
3. `TODO: Estimate the affected area (contour lines, including area within contour lines)`
4. `TODO: Sensitivity analysis should change the flow rate (advective component of transport)`
5. `TODO: Development of mean concentration in aquifer over time`

**Status**: **INSTRUCTOR PLANNING NOTES** - These are meta-notes about what to ask students to do
**Context**: These appear right before "### Mass Balance Analysis" section heading

**Recommendation**: **REMOVE ALL** - These are internal instructor notes that leaked into the student notebook. Confusing and unprofessional.

---

### B8. Quality Checks Simplification Note (Cell #88 - Markdown)
**Location**: Cell #88, Line 95778
**TODO**: `TODO: Keep this simple`

**Status**: **INSTRUCTOR NOTE**
**Context**: Appears in section "## 12. Quality Checks" right before "### Mass Balance Verification"

**Recommendation**: **REMOVE** - Instructor reminder, not a student task

---

### B9. Affected Area Planning Note (Cell #103 - Markdown)
**Location**: Cell #103, Line 96585
**TODO**: `TODO: Tasks: Affected area, contour lines for certain concentration thresholds`

**Status**: **INSTRUCTOR PLANNING NOTE**
**Context**: Appears at top of "## 15. Sensitivity Analysis" section as a standalone line

**Recommendation**: **REMOVE** - This is an instructor reminder of tasks to assign. Not structured as a student task.

---

## Section C: TODOs to UPDATE/CLARIFY

### C1. Well Pumping Rate (Cell #45-46)

#### Cell #45 (Markdown) - Line 2604
**Current**: `TODO: Chose a total pumping/injection rate that is reasonable for your scenario. It does not need to reflect the concessioned rates but should be significant enough to influence plume migration.`

#### Cell #46 (Code) - Line 2643
**Current**:
```python
# TODO: Chose a total pumping/injection rate that is reasonable for your
# scenario. It does not need to reflect the concessioned rates but should be
# significant enough to influence plume migration.
well_rates_m3d = 20000
```

**Issue**: Rate is already set to 20000 m³/d, making the TODO misleading

**Recommendation**: **UPDATE BOTH**

**Suggested fix for Cell #45**:
```markdown
#### WEL package
Here, we reuse the well locations and rates loaded from the flow case study.

**NOTE**: The well pumping/injection rate is set to 20000 m³/d. This is a reasonable default for the Zürich aquifer scenarios. You may adjust this value if your scenario requires different pumping rates, but ensure the rate is significant enough to influence plume migration.
```

**Suggested fix for Cell #46**:
```python
# Well pumping/injection rate for transport scenario
# Default: 20000 m³/d (reasonable for Zürich aquifer)
# Adjust if needed for your specific scenario
well_rates_m3d = 20000
round(well_rates_m3d)
```

---

### C2. Property Field Checking (Cell #29 - Code)

**Location**: Cell #29, Line 1411
**Current**:
```python
# TODO: Check the property fields interpolated from parent to submodel below:
# - Hydraulic conductivity (K)
# - Layer top and bottom elevations
# - Specific storage (if transient)
# Visualize interpolated K field
```

**Status**: **EMPTY CELL** - Only TODO comments, no implementation

**Issue**: Ambiguous intent. Is this:
- A student task to implement visualization?
- An instructor note to add content?
- A verification step students should perform mentally?

**Context**: This appears after submodel creation but before transport setup

**Recommendation**: **UPDATE** - Clarify intent

**Option 1 - If students should verify (passive check)**:
```python
# Verification checkpoint: Property fields interpolated from parent to submodel
# The following fields were interpolated during submodel creation:
# - Hydraulic conductivity (K) - used for velocity calculations
# - Layer top and bottom elevations - defines model geometry
# - Specific storage (if transient) - not used in steady-state transport
#
# These fields are accessible via the submodel_grid object and were
# validated during submodel creation in previous cells.
```

**Option 2 - If students should implement visualization (active task)**:
```markdown
[Create new markdown cell before Cell #29]

### Property Field Verification

**TODO for Students**: Create a visualization to verify the hydraulic conductivity field was properly interpolated from the parent model.

**Guidance**:
- Use `pmv.plot_array()` to visualize K values
- Compare extent with parent model domain
- Verify values are reasonable for the Zürich aquifer (K ~ 1e-3 to 1e-4 m/s)

[Then update Cell #29 code to provide skeleton code for plotting]
```

**Recommendation**: Choose Option 1 (passive verification) since the previous cells already validated the submodel creation, and this would add unnecessary work.

---

### C3. RCT Package TODO (Cell #66 - Code)

**Location**: Cell #66, Lines 5446-5447
**Current**:
```python
# TODO: Check if RCT package is needed & set up accordingly
# TODO: Read reaction parameters from config if needed
# For Group 0: No RCT package needed (conservative tracer)

# For groups with reactions (example):
# rct = flopy.mt3d.Mt3dRct(mt, isothm=1, sp1=Kd, rc1=lambda_decay)
```

**Issue**: Contradictory - Says "TODO: Check if RCT package is needed" then immediately says "No RCT needed"

**Recommendation**: **UPDATE** - Clarify this is conditional based on group

**Suggested fix**:
```python
# RCT Package: Reactions (sorption, decay)
# Group 0: No RCT package needed (conservative tracer - no reactions)
#
# Other groups: If your scenario includes sorption or decay, uncomment and configure:
# rct = flopy.mt3d.Mt3dRct(
#     mt,
#     isothm=1,  # 1=linear, 2=Freundlich, 3=Langmuir
#     sp1=Kd,     # Distribution coefficient (sorption)
#     rc1=lambda_decay  # First-order decay rate
# )
#
# Reaction parameters should be loaded from case_config_transport.yaml
```

---

## Section D: OPTIONAL/ADVANCED TASK STUBS (Empty Implementation Cells)

These cells contain only TODO comments with no implementation. They appear to be advanced/optional exercises.

### D1. Analytical Comparison Section (Cells #94, 96, 98, 100)

**Cell #94**: `# TODO: Define transect line` (207 chars, empty stub)
**Cell #96**: `# TODO: Implement analytical solution function` (346 chars, empty stub)
**Cell #98**: `# TODO: Create comparison plots` (220 chars, empty stub)
**Cell #100**: `# TODO: Quantify differences` (226 chars, empty stub)

**Status**: All are empty cells with only TODO comments
**Context**: Section "## 13. Analytical Comparison (Advanced/Optional)"

**Recommendation**: **KEEP BUT CLARIFY** - These are clearly optional advanced exercises

**Suggested change**: Add a markdown cell before Cell #94:
```markdown
## 13. Analytical Comparison (Advanced/Optional)

**NOTE**: This section is optional and intended for advanced students or groups with extra time.

The following cells provide guidance for comparing your numerical MT3D results with an analytical solution (Ogata-Banks equation). This helps verify the numerical model is working correctly.

**If you choose to skip this section**, proceed directly to Section 14 (Well Breakthrough Curve Analysis).
```

---

### D2. Sensitivity Analysis (Cell #104)

**Cell #104**: `# TODO: Run MT3DMS with:` (299 chars, empty stub)

**Status**: Empty cell with only TODO comments
**Context**: Section "## 15. Sensitivity Analysis"

**Recommendation**: **KEEP BUT CLARIFY** - This is an advanced optional task

**Suggested change**: The preceding markdown (Cell #103) should add:
```markdown
## 15. Sensitivity Analysis

### Parameter Sensitivity

**OPTIONAL**: Test how results change with ±50% variation in dispersivity.

**Rationale**: Dispersivity is scale-dependent and uncertain. Understanding sensitivity helps assess prediction reliability.

The cell below provides guidance if you choose to implement this analysis. Otherwise, proceed to Section 16 (Discussion).
```

---

## SECTION E: SUMMARY AND ACTION PLAN

### E1. Summary Counts

| Category | Count | Action |
|----------|-------|--------|
| **KEEP** - Meaningful student tasks | 45 | No change needed |
| **REMOVE** - Already implemented | 6 | Remove misleading TODOs |
| **REMOVE** - Instructor notes | 6 | Remove internal notes |
| **UPDATE** - Needs clarification | 4 | Rewrite for clarity |
| **Optional/Advanced** - Empty stubs | 5 | Add "OPTIONAL" context |
| **Total TODOs** | **33** | |

### E2. Priority Actions

#### High Priority (Misleading/Confusing) ⚠️

1. **REMOVE Cell #84 instructor planning TODOs** (Lines 95600-95604)
   - Most problematic - internal planning notes visible to students
   - Appears in the middle of the notebook content

2. **REMOVE "already implemented" TODOs** in Cells #12, #64, #70, #72, #89
   - Students will waste time looking for work that's already done
   - Creates confusion about what they need to do

3. **UPDATE Cell #46 well rate TODO** (Line 2643)
   - Currently misleading since rate is already set
   - Change to informational note

#### Medium Priority (Clarity Improvements)

4. **UPDATE Cell #66 RCT package** (Lines 5446-5447)
   - Remove contradiction
   - Clarify it's group-dependent

5. **CLARIFY Cell #29** property fields check
   - Currently ambiguous
   - Convert to verification note

6. **ADD OPTIONAL context** to Cells #94-100, #104
   - Students may think these are required
   - Add markdown explaining these are advanced/optional

#### Low Priority (Style/Consistency)

7. **REMOVE Cell #88 "Keep this simple"** (Line 95778)
   - Minor instructor note
   - Low impact but unprofessional

8. **REMOVE Cell #103 "Tasks: Affected area"** (Line 96585)
   - Instructor planning note
   - Not structured as student task

### E3. Summary by Cell

| Cell | Type | Current TODO | Action | Priority |
|------|------|--------------|--------|----------|
| 0 | md | Names, Date | KEEP | - |
| 12 | code | Load well data | REMOVE | HIGH |
| 29 | code | Check property fields | UPDATE | MEDIUM |
| 45 | md | Choose pumping rate | UPDATE | HIGH |
| 46 | code | Choose pumping rate | UPDATE | HIGH |
| 64 | code | Check DSP package | REMOVE | HIGH |
| 66 | code | Check if RCT needed | UPDATE | MEDIUM |
| 70 | code | Check source location | REMOVE | HIGH |
| 72 | code | Create map | REMOVE | HIGH |
| 84 | md | 5x instructor planning | REMOVE ALL | **CRITICAL** |
| 85 | md | Breakthrough curve header | KEEP | - |
| 86 | code | 19x breakthrough TODOs | KEEP ALL | - |
| 88 | md | Keep this simple | REMOVE | LOW |
| 89 | code | Extract mass balance | REMOVE | HIGH |
| 94 | code | Define transect | CLARIFY OPTIONAL | MEDIUM |
| 96 | code | Analytical solution | CLARIFY OPTIONAL | MEDIUM |
| 98 | code | Comparison plots | CLARIFY OPTIONAL | MEDIUM |
| 100 | code | Quantify differences | CLARIFY OPTIONAL | MEDIUM |
| 103 | md | Affected area tasks | REMOVE | LOW |
| 104 | code | Sensitivity runs | CLARIFY OPTIONAL | MEDIUM |
| 107 | md | 6x discussion prompts | KEEP ALL | - |
| 108 | md | 5x interpretation prompts | KEEP ALL | - |
| 109 | md | Conclusions prompt | KEEP | - |
| 110 | md | 2x recommendations | KEEP ALL | - |
| 111 | md | Recommend bullets | KEEP | - |
| 113 | md | Add references | KEEP | - |

### E4. Detailed Edit List

#### Critical Edits (Do First)

1. **Cell #84 (markdown)** - REMOVE lines with 5 instructor TODOs, keep only:
   ```markdown
   ### Mass Balance Analysis

   Track the fate of contaminant mass:
   - Mass remaining in aquifer
   - Mass exported through boundaries
   - Mass captured by pumping wells
   - Mass lost to decay (if applicable)
   ```

#### High Priority Edits

2. **Cell #12 (code)** - REMOVE TODO comment, change to:
   ```python
   # Load well data from GIS and filter by concession
   # Parse well information and map to submodel grid coordinates
   ```

3. **Cell #64 (code)** - REMOVE TODO, change to:
   ```python
   # DSP Package: Dispersion parameters
   # Load dispersivity values from config and create DSP package
   ```

4. **Cell #70 (code)** - REMOVE TODO, change to:
   ```python
   # Load source location from case_config_transport.yaml
   # Convert coordinates to grid indices and verify placement
   ```

5. **Cell #72 (code)** - REMOVE TODO, change to:
   ```python
   # Visualize source and well locations on submodel grid
   ```

6. **Cell #89 (code)** - REMOVE TODO, change to:
   ```python
   # Extract mass balance from MT3D output files
   # Parse .MAS file and calculate cumulative mass balance error
   ```

7. **Cell #45 (markdown)** - REPLACE TODO with:
   ```markdown
   #### WEL package
   Here, we reuse the well locations and rates loaded from the flow case study.

   **NOTE**: The well pumping/injection rate is set to 20000 m³/d, which is reasonable for Zürich aquifer scenarios. You may adjust this value if needed.
   ```

8. **Cell #46 (code)** - REMOVE TODO comment (lines 2643-2645), replace with:
   ```python
   # Well pumping/injection rate (m³/d)
   # Default: 20000 m³/d (reasonable for Zürich aquifer scenarios)
   # Adjust if needed for your specific scenario
   ```

#### Medium Priority Edits

9. **Cell #66 (code)** - REPLACE both TODOs with:
   ```python
   # RCT Package: Chemical reactions (sorption, decay)
   #
   # Group 0: No RCT package needed (conservative tracer)
   #
   # Other groups with reactive transport: Uncomment and configure below
   # rct = flopy.mt3d.Mt3dRct(
   #     mt,
   #     isothm=1,  # 1=linear, 2=Freundlich, 3=Langmuir
   #     sp1=Kd,     # Distribution coefficient
   #     rc1=lambda_decay  # First-order decay rate
   # )
   ```

10. **Cell #29 (code)** - REPLACE TODO with:
    ```python
    # Verification: The following property fields were interpolated from parent model:
    # - Hydraulic conductivity (K) - used for velocity calculations in transport
    # - Layer top and bottom elevations - defines model geometry
    # - Specific storage - not used in steady-state transport
    #
    # These fields were validated during submodel creation in previous cells.
    ```

11. **Add new markdown cell before Cell #94**:
    ```markdown
    ## 13. Analytical Comparison (Advanced/Optional)

    **NOTE**: This section is OPTIONAL and intended for advanced students.

    If you choose to skip this section, proceed directly to Section 14 (Well Breakthrough Curve Analysis).

    The cells below provide guidance for comparing numerical MT3D results with the Ogata-Banks analytical solution.
    ```

12. **Update Cell #103 markdown** - REMOVE TODO line, add OPTIONAL note:
    ```markdown
    ## 15. Sensitivity Analysis

    **OPTIONAL**: This section provides guidance for sensitivity analysis with varied dispersivity.

    If you choose to skip this section, proceed to Section 16 (Discussion).

    ### Parameter Sensitivity

    Test how results change with ±50% variation in dispersivity.

    **Rationale**: Dispersivity is scale-dependent and uncertain. Understanding sensitivity helps assess prediction reliability.
    ```

#### Low Priority Edits

13. **Cell #88 (markdown)** - REMOVE "TODO: Keep this simple" line:
    ```markdown
    ---
    ## 12. Quality Checks

    ### Mass Balance Verification
    ```

---

## SECTION F: VALIDATION CHECKLIST

Before implementing changes, verify:

- [ ] All 45 "KEEP" TODOs are genuinely student tasks (not instructor notes)
- [ ] All 6 "already implemented" cells truly have complete code
- [ ] Cell #86 (breakthrough curve) template is complete and functional
- [ ] Discussion/Interpretation/Recommendations templates (Cells 107-111) are clear
- [ ] Optional sections (analytical, sensitivity) are clearly marked
- [ ] No student-facing instructor notes remain

---

## SECTION G: NOTES FOR FUTURE NOTEBOOK DEVELOPMENT

### Issues Found

1. **Instructor notes leaked into student version** - Cell #84 has raw planning notes
2. **Inconsistent TODO style** - Mix of instructor notes vs. student tasks
3. **Ambiguous "Check" TODOs** - Unclear if verification or implementation
4. **Pre-implemented code with TODO headers** - Confusing for students
5. **Optional sections not labeled** - Students may think analytical/sensitivity are required

### Recommendations for Future Templates

1. **Use clear TODO categories**:
   - `[STUDENT TODO]:` for student implementation tasks
   - `[VERIFY]:` for verification/checking existing code
   - `[OPTIONAL]:` for advanced exercises
   - NEVER include `[INSTRUCTOR NOTE]:` in student notebooks

2. **Template cell pattern**:
   ```markdown
   ## Section Title

   **Learning Objective**: [Clear statement]

   **TODO for Students**: [Specific task list]

   **Guidance**: [Hints and resources]
   ```

3. **Separate instructor from student versions** properly
   - Use a build process to strip instructor notes
   - Never rely on manual removal

4. **Mark optional sections explicitly**:
   ```markdown
   ## X. Advanced Topic (OPTIONAL)

   **NOTE**: This section is optional...
   ```

5. **Completed code should not have TODO headers**
   - Use descriptive comments instead
   - Save TODOs for skeleton/template cells only

---

**END OF REPORT**
