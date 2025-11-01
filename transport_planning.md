# Transport Case Study Planning Document

## Project Goal

Create a groundwater transport case study that:
1. Is **simpler and independent** from the flow case study (no error carry-over)
2. Uses the **base parent model** (fresh download) as the foundation
3. **Integrates wells** from the flow case (same locations, analyze well-contaminant interactions)
4. Demonstrates the **telescope/submodel approach** for transport
5. Allows students to work on **different contaminant scenarios** per group
6. Provides flexibility in solution methods (numerical/analytical/hybrid)

## Key Design Decision (2025-11-01)

**Wells are INCLUDED in the transport case study!**
- Each group uses the same well field from their flow case study
- Wells are loaded from the existing `case_config.yaml`
- Students analyze how pumping wells capture contamination and how injection wells/Sickergalerie spread it
- Contaminant sources are placed strategically relative to the well field
- This adds real-world relevance: understanding well-contaminant interactions is critical for groundwater management

---

## Core Principles

### Simplification Compared to Flow Case Study
- **Wells reused, not reimplemented** (students load wells from existing config, no new setup)
- **No scenario modifications** (no recharge/river/K changes like in flow case)
- **Independent from student flow results** (uses fresh base_parent model, not their flow model)
- **Single-stage workflow** (not 3-stage like flow case: just base + wells + transport)
- **Focus on transport processes**: advection, dispersion, sorption, decay, and well interactions
- **Telescope model for resolution** around wells and source area

### Why Simpler than Flow Case?
1. Transport is conceptually more challenging than flow - keep workflow simpler
2. Avoid compounding errors from flow case study (independent base model)
3. No parameter scenarios to implement (no RCH/K/RIV variations)
4. Wells are already defined in `case_config.yaml` - just reuse them
5. Single comparison (with wells vs. without wells, or effect of well placement) instead of 3-stage

### But Still Realistic
- Wells are included because contamination + pumping/injection is a real-world problem
- Students learn about capture zones and contaminant spreading
- More interesting than pure transport without wells
- Builds on their flow case knowledge (same well fields)

---

## Architecture

### File Structure

```
applied_groundwater_modelling/
├── transport_planning.md (this file)
├── CASE_STUDY/
│   ├── 1_introduction.ipynb
│   ├── 2_perceptual_model.ipynb
│   ├── 3_modflow_fundamentals.ipynb
│   ├── 4_model_implementation.ipynb
│   ├── 4b_transport_model_implementation.ipynb  ← NEW: Demo/teaching notebook
│   └── student_work/
│       ├── README.md (update with transport instructions)
│       ├── group_0/
│       │   ├── case_config.yaml (flow - existing)
│       │   ├── case_study_flow_group_0.ipynb (existing)
│       │   ├── transport_config.yaml  ← NEW: Transport scenario config
│       │   └── case_study_transport_group_0.ipynb  ← NEW: Complete demo case
│       ├── group_1/
│       │   └── transport_config.yaml  ← NEW: Pre-configured scenario
│       ├── group_2/
│       │   └── transport_config.yaml
│       └── ... (groups 3-8)
```

---

## Notebook Design

### 4b_transport_model_implementation.ipynb (Teaching Notebook)

**Purpose**: Demonstrate transport concepts and MT3DMS setup to students

**Content Structure**:
1. **Introduction to Transport Modeling**
   - Recap of advection, dispersion, sorption, decay
   - When to use analytical vs numerical approaches
   - Overview of MT3DMS coupling with MODFLOW

2. **Transport Model Setup Fundamentals**
   - Loading a MODFLOW model and flow results
   - Creating an MT3DMS model with FloPy
   - Setting transport parameters (porosity, dispersivity)
   - Understanding Courant and Peclet numbers

3. **Source Term Definition**
   - Point sources vs area sources
   - Continuous vs pulse releases
   - Mapping coordinates to grid cells
   - SSM (Source-Sink Mixing) package

4. **Simple Example: 1D Analytical Verification**
   - Ogata-Banks solution implementation
   - MT3DMS verification against analytical
   - Building confidence in numerical setup

5. **2D/3D Example on Base Model**
   - Point source in Limmat Valley base model
   - Running MT3DMS coupled transport
   - Post-processing: concentration maps, breakthrough curves
   - Mass balance checking

6. **Telescope Approach for Transport**
   - Why refine around the source area?
   - Creating transport submodel from parent model
   - Extracting flow boundary conditions
   - Running transport on submodel
   - Advantages: resolution, computation time

7. **Alternative Approaches Discussion**
   - When analytical solutions are sufficient
   - Hybrid approaches (particle tracking, analytical overlays)
   - Trade-offs between methods

**Key Teaching Points**:
- Students see complete workflow before their assignment
- Emphasis on verification and quality checks
- Clear explanation of when/why telescope approach helps
- Balanced view of analytical vs numerical methods

**MT3DMS Package Overview for Students**:
MT3DMS is modular and uses different "packages" for different transport processes:
- **BTN (Basic Transport)**: Core package - defines grid, porosity, time stepping, initial concentrations
- **ADV (Advection)**: Handles contaminant movement with groundwater flow (several numerical methods available)
- **DSP (Dispersion)**: Models spreading/mixing due to mechanical dispersion and diffusion
- **SSM (Source-Sink Mixing)**: Defines where and how contaminants enter the system (the "source term")
- **RCT (Reaction)**: Handles sorption (retardation) and decay (degradation)
- **GCG (Generalized Conjugate Gradient)**: Solves the transport equations

Think of it like MODFLOW packages (DIS, BAS, LPF, WEL, RCH, etc.) but for transport instead of flow.

---

### case_study_transport_group_0.ipynb (Demo Case Study)

**Purpose**: Complete working example that students copy and adapt

**Content Structure**:

#### 1. Overview and Learning Objectives
- Explain the transport case study task
- Learning goals: apply transport modeling to real scenario
- Deliverables overview

#### 2. Workflow Summary
Transport case study workflow (simpler than 3-stage flow case):
- **Load base parent model** (fresh download, steady-state flow field)
- **Load well locations from flow case study** (same concession data from case_config.yaml)
- **Create transport telescope submodel** around well field (reuse/adapt flow submodel domain)
- **Set up MODFLOW submodel with wells** (steady-state flow with pumping/injection)
- **Set up MT3DMS for transient transport** (concentrations evolve over time with steady flow)
- **Define contaminant source** (located near well field)
- **Run transport simulation** (~10 years, transient concentrations on steady-state flow)
- **Analyze well-contaminant interactions** (capture zones, spreading from injection)
- **Post-process and interpret** results
- **(Optional) Compare with analytical solution** (if applicable)

**Key Concept**: Steady-state flow (heads don't change) + transient transport (concentrations evolve over time). This is the most common approach for long-term contamination problems.

#### 3. Configuration and Setup
```python
# Load transport_config.yaml
# Defines: source location, contaminant type, parameters
# Set group number, load parent model
```

#### 4. Load Parent Flow Model
```python
# Download fresh base_parent_model
# Load with FloPy
# Verify it's the baseline model (no modifications)
# Extract flow results (heads, flows for transport)
```

#### 5. Define Transport Submodel Domain
```python
# Identify source location from transport_config.yaml
# Define buffer around source (consider 10-year travel time)
# Create submodel boundary polygon
# Check that domain is adequate (plume won't exit during simulation)
```

#### 6. Load Well Data and Define Submodel Domain
```python
# Load well locations from case_config.yaml (same as flow case study)
# Identify pumping wells and injection wells/Sickergalerie
# Define submodel domain around well field (can reuse flow case methodology)
# Ensure domain is large enough for both wells AND contaminant plume migration
```

#### 7. Create Telescope Submodel for Flow
```python
# Generate refined grid (e.g., 5m cells around wells and source)
# Extract boundary conditions from parent model heads
# Interpolate aquifer properties to refined grid
# Add wells to submodel (pumping/injection rates)
# Run MODFLOW submodel for steady-state flow with wells
# Verify mass balance, flow patterns, and well behavior
```

#### 7. Set Up MT3DMS Transport Model
```python
# Create MT3DMS model object linked to submodel MODFLOW
# Basic Transport (BTN) package: porosity, initial concentration
# Advection (ADV) package: method selection (MOC, HMOC, TVD, etc.)
# Dispersion (DSP) package: dispersivity values
# Source-Sink Mixing (SSM) package: define source term cells
# Reaction (RCT) package: sorption/decay if applicable
# GCG solver package
```

**Understanding the SSM (Source-Sink Mixing) Package:**
The SSM package is how we tell MT3DMS where contaminants enter the groundwater system and at what concentration. It can handle:
- **Point sources** (like injection wells or spills) - added as WEL package with concentration
- **Boundary sources** (like contaminated water entering through CHD, GHB, or RIV boundaries)
- **Areal sources** (like recharge carrying contaminants from the surface)
- **Constant concentration zones** (like a continuous source area)

In our case studies, we'll primarily use SSM to define:
1. **Pure source terms** (contamination entering at specified cells) using `itype = -1` or `itype = 15` (MAS - mass loading)
2. OR contamination through existing boundaries (e.g., recharge carrying nitrate, river with contaminated water)

The SSM package connects transport to the flow model's stress packages (WEL, RCH, RIV, etc.) and assigns concentrations to water entering the system.

#### 8. Define Source Term
```python
# Map source coordinates to submodel grid cells
# Set concentration and timing (pulse vs continuous)
# Visualize source location on grid
# Set up SSM package with source cells
```

**Two Approaches for Defining Sources in SSM:**

**Approach 1: Pure Source (Constant Concentration Cell)**
Use `itype = -1` (constant concentration) to define a cell that always maintains a specified concentration. Good for:
- Continuous source zones (e.g., landfill leachate pool)
- Boundary conditions with known concentration

Example:
```python
# Cell (layer, row, col) = (0, 50, 50) with concentration 100 mg/L
ssm_data = {0: [(0, 50, 50, 100.0, -1, 0, 0)]}  # stress period 0
```

**Approach 2: Mass Loading (Point Source)**
Use `itype = 15` (MAS - mass loading) or couple with WEL package to inject contaminated water. Good for:
- Spills or injection events
- Sources with known mass flux rather than concentration

Example:
```python
# Add a well with negative flux (injection) and assign concentration via SSM
wel_data = {0: [[(0, 50, 50, -10.0)]]}  # inject 10 m³/day
ssm_data = {0: [(0, 50, 50, 100.0, 2, 0, 0)]}  # itype=2 for WEL package, 100 mg/L
```

For most case studies, **Approach 1** (constant concentration cell) is simpler and appropriate for modeling contamination sources.

#### 9. Run Transport Simulation
```python
# Run MT3DMS
# Monitor progress
# Check for warnings/errors
```

#### 10. Post-Processing and Visualization
```python
# Load concentration results (UCN file)
# Create concentration maps at multiple times (1 yr, 3 yr, 5 yr, 10 yr)
# Breakthrough curves at monitoring points
# Plume extent over time (area above threshold)
# Mass balance summary
```

#### 11. Quality Checks
```python
# Mass balance error < 1%
# Courant number (advective stability)
# Peclet number (dispersive stability)
# Plume contained in domain (or justify truncation)
```

#### 12. Analysis and Interpretation
```python
# Answer scenario-specific questions from transport_config.yaml
# Maximum extent of plume
# Time to reach monitoring/compliance points
# Concentration exceedances
# Effectiveness of natural attenuation (if decay/sorption)
```

#### 13. (Optional) Alternative Method Comparison
```python
# Compare with analytical solution (if applicable)
# Or demonstrate why analytical is insufficient
# Justify chosen method
```

#### 14. Summary and Conclusions
- Key findings for your scenario
- Parameter sensitivity discussion
- Limitations and uncertainties
- Recommendations

---

## Configuration File Design

### transport_config.yaml Structure

```yaml
###############################################################
# Transport Case Study Configuration
# Independent transport problem using base parent model
###############################################################

group:
  number: 0                               # TODO: Set to your group number (0-8)
  authors:                                # TODO: List group members
    - "First Last"
    - "Second Last"

# Base parent model (fresh download, not student flow results)
parent_model:
  data_name: baseline_model               # Fixed - downloads known-good model
  workspace: "~/applied_groundwater_modelling_data/limmat/baseline_model"
  namefile: "limmat_valley_model_nwt.nam"

# Transport submodel output location
output:
  workspace: "~/applied_groundwater_modelling_data/limmat/transport_case_study_group_"

# Transport scenario assignment (FIXED by group number)
scenarios:
  - id: 0
    group: 0
    title: "Demo - Industrial solvent spill"
    contaminant: "Trichloroethylene (TCE)"
    description: >
      A 30-day TCE spill from an industrial facility. Assess plume migration
      under natural gradient conditions and determine if/when contamination
      reaches the Limmat River.

  - id: 1
    group: 1
    title: "Agricultural nitrate contamination"
    contaminant: "Nitrate (NO3-)"
    description: >
      Continuous nitrate loading from agricultural field. Evaluate long-term
      plume development and potential impact on nearby drinking water wells.

  - id: 2
    group: 2
    title: "Legacy landfill plume"
    contaminant: "Chloride (conservative tracer)"
    description: >
      Historical contamination from old landfill (10-year continuous source).
      Characterize current plume extent and predict future migration.

  - id: 3
    group: 3
    title: "Gasoline station leak (BTEX)"
    contaminant: "Benzene"
    description: >
      Point source benzene leak with biodegradation. Assess natural attenuation
      capacity and monitored natural attenuation feasibility.

  - id: 4
    group: 4
    title: "Pesticide contamination"
    contaminant: "Atrazine"
    description: >
      Diffuse pesticide source with sorption. Evaluate retardation effects and
      breakthrough timing at monitoring locations.

  - id: 5
    group: 5
    title: "PFAS contamination"
    contaminant: "PFOA (perfluorooctanoic acid)"
    description: >
      Point source PFAS release (conservative, mobile). Assess long-term
      migration and compliance with drinking water standards.

  - id: 6
    group: 6
    title: "Deicing salt from roadway"
    contaminant: "Chloride"
    description: >
      Seasonal chloride loading from road de-icing. Evaluate cumulative
      impact and seasonal concentration variations.

  - id: 7
    group: 7
    title: "Wastewater treatment plant effluent"
    contaminant: "Ammonium"
    description: >
      Continuous ammonium discharge with nitrification (decay). Model
      transformation and downgradient concentration profiles.

  - id: 8
    group: 8
    title: "Industrial chromium plume"
    contaminant: "Chromium (Cr-VI)"
    description: >
      Point source chromium with sorption. Assess plume mobility and
      evaluate pump-and-treat remediation timing requirements.

# Source term definition for THIS group (group 0 example)
source:
  type: "point"                           # "point" or "area"
  release_type: "pulse"                   # "pulse" or "continuous"

  # Location (Swiss coordinates) - relative to well field
  location:
    easting: 2684500                      # TODO: Set relative to well locations
    northing: 1249500                     # TODO: Set relative to well locations
    layer: 1                               # Top active layer
    placement_strategy: >
      Position source strategically relative to wells. Options:
      - Upgradient of pumping wells (test capture efficiency)
      - Near injection wells/Sickergalerie (test spreading)
      - Between pumping and injection wells (test complex interactions)
      - Downgradient of all wells (test if wells provide protection)

  # Timing
  start_time_days: 0
  duration_days: 30                       # For pulse; large number for continuous

  # Concentration
  concentration_mg_L: 100.0               # TODO: Set realistic value for contaminant

  notes: >
    TODO: Describe source location context relative to well field.
    Example: "Industrial TCE spill 150m upgradient of pumping well cluster,
    testing whether current pumping rates can capture the plume before it
    reaches the Limmat River."

# Transport parameters (students adjust within reasonable ranges)
transport:
  simulation_time_days: 3650              # 10 years

  # Basic transport properties
  porosity: 0.25                          # Effective porosity

  # Dispersivity (students should justify these choices)
  longitudinal_dispersivity_m: 10.0      # TODO: Justify based on scale
  transverse_dispersivity_m: 1.0         # Typically 0.1 * alpha_L
  vertical_dispersivity_m: 0.1           # Typically 0.01 * alpha_L

  # Sorption (if applicable)
  sorption: false                         # true if contaminant sorbs
  bulk_density_kg_m3: 1800.0             # Aquifer bulk density
  distribution_coefficient_mL_g: 0.0     # Kd; 0 for conservative tracer

  # Decay/degradation (if applicable)
  decay: false                            # true if contaminant degrades
  first_order_decay_constant_1_per_day: 0.0  # 0 for conservative
  half_life_days: null                    # Alternative: specify half-life

  notes: >
    TODO: Justify parameter choices. Cite literature values or
    explain assumptions. Discuss uncertainty ranges.

# Telescope submodel configuration
submodel:
  # Buffer distances from source (ensure plume is contained)
  buffer_north_m: 500                     # TODO: Adjust based on travel time
  buffer_south_m: 500
  buffer_east_m: 500
  buffer_west_m: 500

  # Grid refinement
  cell_size_m: 5                          # Fine resolution near source

  notes: >
    TODO: Justify buffer distances. Consider 10-year travel time under
    maximum hydraulic gradient. Verify plume doesn't reach boundaries.

# Monitoring/observation points
monitoring:
  points:
    - name: "MW-1"
      easting: 2684600
      northing: 1249600
      purpose: "Downgradient monitoring well"

    - name: "River boundary"
      easting: 2684800
      northing: 1249700
      purpose: "Assess river impact"

  compliance:
    threshold_mg_L: 10.0                  # Regulatory threshold
    location: "Property boundary / River"

# Modeling approach (student documents their choice)
approach:
  method: "numerical_mt3d"                # "analytical", "numerical_mt3d", "hybrid"

  justification: >
    TODO: Explain why this method is appropriate for your scenario.
    Consider: geometry complexity, boundary conditions, parameter
    heterogeneity, source term characteristics.

  analytical_alternative:
    feasible: false                        # Could analytical work?
    reason: >
      TODO: Explain why analytical solution is/isn't suitable for
      comparison or primary analysis.

# Analysis tasks
analysis_tasks:
  - "Map concentration distribution at 1, 3, 5, and 10 years"
  - "Plot breakthrough curves at monitoring points"
  - "Calculate plume extent (area where C > 1 mg/L) over time"
  - "Estimate time for contamination to reach compliance point"
  - "Assess whether concentration exceeds threshold at any location"
  - "Evaluate mass balance (% mass remaining in domain vs exported)"
  - "Sensitivity analysis: vary dispersivity ±50%, compare results"

# Deliverables
deliverables:
  - "Completed transport_config.yaml with justified parameters"
  - "Executed case_study_transport_group_X.ipynb with all results"
  - "Concentration maps (at least 4 time steps)"
  - "Breakthrough curves at monitoring points"
  - "Mass balance summary"
  - "Written interpretation (2-3 paragraphs in notebook)"
  - "Parameter sensitivity discussion"

# Quality control checklist
quality_checks:
  - "Mass balance error < 1%"
  - "Courant number ≤ 1 (advective stability)"
  - "Peclet number ≤ 2 (dispersive stability)"
  - "Plume contained within submodel domain"
  - "Concentration values physically reasonable (no negatives, no overshoot)"
  - "Results make sense given flow direction and source location"
```

---

## Transport Scenario Differentiation

### Group Assignments

Each group analyzes contamination in relation to their well field from the flow case study:

| Group | Concession | Wells | Contaminant | Source Scenario | Sorption | Decay | Key Question |
|-------|------------|-------|-------------|-----------------|----------|-------|--------------|
| 0 | 210 | Mixed | TCE | Spill upgradient | No | No | Will pumping wells capture the plume? |
| 1 | 219 | Mixed | Nitrate | Agricultural area | No | No | Effect on downgradient wells |
| 2 | 201 | Mixed | Chloride | Legacy contamination | No | No | Extent of historical plume |
| 3 | 236 | Mixed | Benzene | Gas station leak | No | Yes | Natural attenuation vs. capture |
| 4 | 190 | Mixed | Atrazine | Agricultural diffuse | Yes | No | Retardation effects |
| 5 | 223 | Mixed | PFOA | Industrial point | No | No | Long-term migration |
| 6 | 227 | Mixed | Chloride | Road deicing | No | No | Multiple source timing |
| 7 | 213 | Mixed | Ammonium | Wastewater | No | Yes | Degradation in capture zone |
| 8 | 207 | Mixed | Chromium | Industrial spill | Yes | No | Sorption + pumping interaction |

**Note**: "Mixed" means well fields contain both pumping wells (extraction) and injection wells/Sickergalerie. Groups will need to:
1. Identify which wells pump and which inject
2. Place contamination source strategically relative to wells
3. Analyze how wells affect contaminant fate and transport

### Scenario Complexity Levels

**Simple (Groups 0, 1, 2, 5):**
- Conservative tracer (no sorption or decay)
- Focus on advection, dispersion, and well capture/spreading
- Good candidates for analytical comparison (without wells)

**Moderate (Groups 3, 4, 6, 7, 8):**
- Reactive transport (sorption OR decay)
- Combined effect of reactions + well pumping/injection
- Requires careful parameter selection and interpretation

---

## Implementation Steps

### Phase 1: Planning and Design (Current)
- [x] Define overall approach (simpler, independent from flow case)
- [ ] Finalize 9 transport scenarios (one per group)
- [ ] Design transport_config.yaml structure
- [ ] Outline both notebook structures

### Phase 2: Teaching Notebook (4b_transport_model_implementation.ipynb)
- [ ] Section 1-2: Transport fundamentals recap
- [ ] Section 3: MT3DMS basics and FloPy interface
- [ ] Section 4: Simple 1D analytical verification example
- [ ] Section 5: 2D/3D example on base model (no submodel)
- [ ] Section 6: Telescope approach demonstration
- [ ] Section 7: Alternative methods discussion
- [ ] Test notebook end-to-end
- [ ] Add exercises/reflection questions

### Phase 3: Demo Case Study (group_0/)
- [ ] Create transport_config.yaml for group 0 (demo scenario)
- [ ] Build case_study_transport_group_0.ipynb following structure above
  - [ ] Sections 1-4: Setup and parent model
  - [ ] Sections 5-6: Telescope submodel creation
  - [ ] Sections 7-8: MT3DMS setup and source term
  - [ ] Sections 9-10: Run and visualize
  - [ ] Sections 11-12: QC and analysis
  - [ ] Section 13: Optional analytical comparison
  - [ ] Section 14: Summary
- [ ] Test complete workflow end-to-end
- [ ] Verify computational time is reasonable
- [ ] Add helpful comments and TODO markers for students

### Phase 4: Student Configurations (groups 1-8)
- [ ] Create transport_config.yaml for each group
  - [ ] Group 1: Nitrate scenario
  - [ ] Group 2: Legacy landfill
  - [ ] Group 3: Benzene
  - [ ] Group 4: Atrazine
  - [ ] Group 5: PFOA
  - [ ] Group 6: Deicing salt
  - [ ] Group 7: Ammonium
  - [ ] Group 8: Chromium
- [ ] Define source locations (varied across valley)
- [ ] Set appropriate parameters for each contaminant
- [ ] Write scenario-specific descriptions and questions

### Phase 5: Supporting Materials
- [ ] Update README.md in student_work/ with transport instructions
- [ ] Add analytical solution functions to SUPPORT_REPO (Ogata-Banks, etc.)
- [ ] Create helper functions for common transport tasks
  - [ ] Source term cell identification
  - [ ] Breakthrough curve plotting
  - [ ] Mass balance checking
  - [ ] Stability criteria checking (Courant, Peclet)
- [ ] Add transport-specific plotting utilities

### Phase 6: Documentation and Testing
- [ ] Test group_0 notebook runs without errors
- [ ] Verify each group's transport_config.yaml is complete
- [ ] Check that all scenarios are appropriately differentiated
- [ ] Write instructor notes (solution key, expected results)
- [ ] Document common pitfalls and troubleshooting
- [ ] Estimate completion time for students

### Phase 7: Integration and Deployment
- [ ] Link 4b notebook from main course structure
- [ ] Update course introduction to mention transport case study
- [ ] Add transport to progress tracking (if applicable)
- [ ] Prepare assignment handout/instructions
- [ ] Schedule: when transport assignment is due relative to flow assignment

---

## Design Decisions and Rationale

### Why Independent from Flow Case Study?
1. **Error isolation**: Flow modeling mistakes don't propagate
2. **Known-good baseline**: Fresh download ensures working starting point
3. **Simpler workflow**: Fewer moving parts, focus on transport concepts
4. **Parallel completion**: Students can work on both simultaneously if needed

### Why Still Use Telescope Approach?
1. **Resolution**: 5m cells around source vs 25m+ in parent model
2. **Computational efficiency**: Refined domain only where needed
3. **Pedagogical continuity**: Reinforces submodeling concept from flow case
4. **Real-world practice**: Industry-standard technique

### Why Include Wells but No Additional Scenarios?
1. **Real-world relevance**: Wells and contamination often coexist; students learn about capture zones and spreading
2. **Reuse flow case work**: Same well locations, similar submodel domain setup
3. **Manageable complexity**: Wells are already implemented (copy from flow case), only transport is new
4. **Automatic well identification**: Code will identify pumping vs. injection wells from rates
5. **No scenarios**: Keeping it simpler than flow case (no recharge/K variations), just transport + wells

### Well-Transport Interaction Scenarios

Different groups will explore different relationships between wells and contamination:

**Pumping Wells (Extraction)**:
- Create capture zones that can intercept contamination
- Beneficial: Can prevent plume from reaching sensitive receptors
- Students analyze: capture efficiency, breakthrough timing at well

**Injection Wells / Sickergalerie**:
- Spread water (and potentially contaminants) outward from injection point
- Concern: If injecting into or near contaminated zone, could spread contamination
- Students analyze: zone of influence, potential spreading if contaminated water is injected

**Mixed Well Fields** (most realistic):
- Some wells pump, others inject
- Complex flow patterns affect contaminant migration
- Students analyze: net effect on plume, protection vs. spreading

This provides valuable real-world engineering insight: **well placement matters for contaminant management!**

### Parameter Choices
- **10-year simulation**: Long enough to see plume development, short enough to run quickly
- **5m grid cells**: Balance between resolution and computation time
- **Dispersivity ranges**: Scale-appropriate (10m longitudinal for local scale)
- **Buffer distances**: ~500m ensures most plumes contained over 10 years

---

## Key Differences from Flow Case Study

| Aspect | Flow Case Study | Transport Case Study |
|--------|-----------------|---------------------|
| Base model | Fresh parent model | Same fresh parent model |
| Complexity | 3 stages (base, wells, scenario) | 1 stage (wells + transport) |
| Wells | Student implements from concession | Reuse same wells from case_config.yaml |
| Scenarios | Parameter variations (RCH, K, RIV) | No parameter scenarios, focus on transport |
| Configuration | case_config.yaml | transport_config.yaml (extends case_config) |
| Workflow | Load → Wells → Scenario → Compare | Load → Wells → Transport → Analyze |
| Focus | Flow system response to stresses | Contaminant transport with well interactions |
| Time dimension | Steady-state (or multiple stress periods) | Steady flow + transient transport (10 years) |
| New concepts | Telescope modeling, well implementation | MT3DMS packages, transport parameters, stability |
| Analysis | Drawdown, river leakage, budgets | Plume migration, capture zones, breakthrough curves |

---

## Student Learning Objectives

By completing this transport case study, students will:

1. **Understand transport processes**: Advection, dispersion, sorption, decay
2. **Apply MT3DMS**: Set up and run coupled flow-transport simulations
3. **Use telescope approach**: Create refined submodels for local-scale problems
4. **Interpret results**: Concentration maps, breakthrough curves, mass balance
5. **Evaluate methods**: Understand when analytical vs numerical is appropriate
6. **Assess uncertainty**: Parameter sensitivity and its impact on predictions
7. **Communicate findings**: Document assumptions, methods, and conclusions

---

## Open Questions / Decisions Needed

1. ~~**Source locations**: Should all groups have sources in different parts of the valley, or clustered in one area?~~
   - **DECIDED**: Use the same well field locations as flow case study. Each group's submodel domain will be centered on their assigned well group (concession area).

2. **Analytical comparison**: Required or optional? (Suggest optional for moderate complexity scenarios)

3. **Time constraints**: How many weeks for transport case study? (Suggest 2-3 weeks)

4. ~~**Coupling**: Do any groups eventually combine flow + transport? (e.g., pumping well capture of contamination)~~
   - **DECIDED**: Yes! Wells will be active in the transport model. Groups will analyze how their pumping/injection wells affect contaminant transport (capture zones, plume spreading from injection wells).

5. **Software flexibility**: How much do we encourage alternative methods? (Suggest "encouraged to compare, but MT3D must be primary")

6. **Deliverables format**: Notebook only, or separate report? (Suggest notebook with narrative markdown cells)

7. **Grading criteria**: What aspects are weighted? (Suggest: setup 30%, results 30%, interpretation 20%, quality checks 20%)

---

## Timeline Estimate

**For instructor (implementation):**
- Phase 2 (Teaching notebook): 10-15 hours
- Phase 3 (Demo case): 8-12 hours
- Phase 4 (Group configs): 4-6 hours
- Phase 5 (Support materials): 4-6 hours
- Phase 6 (Testing/docs): 4-6 hours
- **Total: ~30-45 hours**

**For students (completion):**
- Read/understand teaching notebook: 2-3 hours
- Adapt demo case for their scenario: 3-4 hours
- Run simulations and troubleshoot: 2-3 hours
- Analysis and interpretation: 2-3 hours
- Documentation and quality checks: 1-2 hours
- **Total: ~10-15 hours per group**

---

## Success Criteria

The transport case study will be successful if:

✅ All groups can complete their scenario in ~10-15 hours
✅ Students understand when/why to use different transport modeling approaches
✅ Results are physically meaningful and properly interpreted
✅ Quality checks (mass balance, stability) are passed
✅ Students can explain parameter choices and their uncertainties
✅ No major technical blockers or software issues
✅ Students see the value of the telescope approach for resolution/efficiency

---

## Next Steps

**Immediate (this planning session):**
1. Review and refine this planning document
2. Finalize 9 transport scenarios
3. Decide on source location distribution strategy

**Next work session:**
1. Create template transport_config.yaml
2. Start building 4b_transport_model_implementation.ipynb (teaching notebook)
3. Set up group_0 folder structure

**Following sessions:**
1. Complete demo case_study_transport_group_0.ipynb
2. Create all group transport_config.yaml files
3. Build supporting utilities and test end-to-end

---

## Notes and Ideas

- Consider adding a "quick start" section in demo notebook for impatient students
- Could provide pre-computed flow results as backup if parent model doesn't converge
- Might want visualization templates (standard plots) to ensure consistency
- Consider creating a transport results comparison gallery showing all 9 group scenarios
- Could have bonus challenge: "What pumping rate would prevent plume from reaching river?"
- For analytical comparison: provide Jupyter widgets for interactive parameter exploration?

---

## Glossary and Quick Reference

### MT3DMS Packages Summary

| Package | Acronym | Purpose | Key Parameters |
|---------|---------|---------|----------------|
| Basic Transport | BTN | Core setup: grid, time, porosity, initial conditions | `prsity`, `icbund`, `sconc`, `nprs` |
| Advection | ADV | Solute movement with groundwater flow | `mixelm` (method: MOC, HMOC, MMOC, etc.) |
| Dispersion | DSP | Mechanical dispersion and diffusion | `al`, `trpt`, `trpv`, `dmcoef` |
| Source-Sink Mixing | SSM | Define contamination sources and concentrations | `stress_period_data`, `itype` |
| Reaction | RCT | Sorption and decay processes | `isothm`, `sp1` (Kd), `rc1` (decay) |
| GCG Solver | GCG | Solves transport equations | `mxiter`, `iter1`, `cclose` |

### SSM Package itype Codes

| itype | Source/Sink Type | Description |
|-------|------------------|-------------|
| -1 | Constant Concentration | Cell maintains fixed concentration (boundary condition) |
| 1 | CHD | Constant head boundary (MODFLOW CHD package) |
| 2 | WEL | Well (injection or extraction) |
| 3 | DRN | Drain |
| 4 | RIV | River |
| 5 | GHB | General head boundary |
| 15 | MAS | Mass loading (direct mass input) |
| Others | RCH, EVT, etc. | Recharge, evapotranspiration, and other packages |

### Typical Transport Parameter Ranges

| Parameter | Symbol | Typical Range | Units | Notes |
|-----------|--------|---------------|-------|-------|
| Effective porosity | n | 0.15 - 0.35 | - | For sand/gravel aquifers |
| Longitudinal dispersivity | αL | 0.1 - 100 m | m | Scale-dependent; ~10% of travel distance |
| Transverse dispersivity | αT | αL / 10 | m | Often 10% of αL |
| Vertical dispersivity | αV | αL / 100 | m | Often 1% of αL |
| Molecular diffusion | Dm | 1×10⁻⁹ - 2×10⁻⁹ | m²/s | Often negligible compared to dispersion |
| Distribution coefficient | Kd | 0 - 10+ | mL/g | 0 = conservative; contaminant-specific |
| Bulk density | ρb | 1600 - 2000 | kg/m³ | For sand/gravel |
| Decay constant | λ | varies | 1/day | Calculate from half-life: λ = ln(2)/t½ |

### Stability Criteria for MT3DMS

**Courant Number** (advective stability):
```
Cr = v·Δt / Δx ≤ 1
```
where v = velocity, Δt = time step, Δx = cell size

**Peclet Number** (dispersive stability):
```
Pe = v·Δx / D ≤ 2-4
```
where D = dispersion coefficient (αL·v)

If stability criteria are violated, reduce time step size or refine grid.

### Useful Analytical Solutions

**1D Advection-Dispersion (Ogata-Banks)**:
For instantaneous source in uniform flow:
```
C(x,t) = (C₀/2) · [erfc((x-vt)/(2√(Dₓt))) + exp(vx/Dₓ)·erfc((x+vt)/(2√(Dₓt)))]
```

**1D with Retardation**:
Replace v with v/R and t with Rt, where R = 1 + (ρb·Kd)/n

**1D with Decay**:
Multiply solution by exp(-λt)

Good for verification and simple scenarios!

### FloPy Code Snippets

**Load MODFLOW model and results**:
```python
import flopy
mf = flopy.modflow.Modflow.load('model.nam', model_ws='path/to/model')
hds = flopy.utils.HeadFile('model.hds')
heads = hds.get_data()
```

**Create MT3DMS model**:
```python
mt = flopy.mt3d.Mt3dms(modelname='transport', modflowmodel=mf)
```

**Basic Transport Package (BTN)**:
```python
btn = flopy.mt3d.Mt3dBtn(mt, prsity=0.25, icbund=1, sconc=0)
```

**Advection Package (ADV)** - using TVD scheme:
```python
adv = flopy.mt3d.Mt3dAdv(mt, mixelm=6)  # mixelm=6 is TVD
```

**Dispersion Package (DSP)**:
```python
dsp = flopy.mt3d.Mt3dDsp(mt, al=10.0, trpt=0.1, trpv=0.01)
```

**Source-Sink Mixing (SSM)** - constant concentration:
```python
itype = flopy.mt3d.Mt3dSsm.itype_dict()
ssm_data = {0: [(0, 10, 10, 100.0, itype['CC'], 0, 0)]}  # layer, row, col, conc
ssm = flopy.mt3d.Mt3dSsm(mt, stress_period_data=ssm_data)
```

**Reaction Package (RCT)** - with sorption and decay:
```python
rct = flopy.mt3d.Mt3dRct(mt, isothm=1, sp1=0.5, rc1=0.001)  # Kd=0.5, lambda=0.001
```

**Run MT3DMS**:
```python
mt.write_input()
success, buff = mt.run_model(silent=False)
```

**Read concentration results**:
```python
ucn = flopy.utils.UcnFile('MT3D001.UCN')
conc = ucn.get_data(totim=365)  # concentration at day 365
```

### Common Pitfalls and Troubleshooting

| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| Negative concentrations | Numerical instability (Courant/Peclet too high) | Reduce time step or refine grid |
| Mass balance error > 1% | Solver tolerance too loose | Tighten GCG solver settings (`cclose`) |
| Plume not moving | Wrong velocity field, porosity too high | Check MODFLOW results, verify porosity |
| Oscillations near source | Grid too coarse for sharp gradients | Refine grid or use TVD advection scheme |
| Model runs very slowly | Grid too fine or time steps too small | Coarsen away from source, use adaptive time stepping |
| Source concentration = 0 | Wrong SSM itype or stress period | Verify SSM setup and stress period data |

---

*Document created: 2025-11-01*
*Last updated: 2025-11-01*
*Status: Initial planning - awaiting review and finalization*
