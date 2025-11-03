# Transport Case Study Planning Document

> **📋 IMPORTANT: This is the authoritative planning document for the transport case study**
>
> **For AI Assistants**: Always read this document at the start of any session involving transport materials. All design decisions, structure, and implementation guidance are documented here.
>
> **For Instructors**: This document guides all transport case study development. Update it when design decisions change.
>
> **Last Updated**: 2025-11-03
> **Status**: Planning complete - ready for implementation (analytical verification changed to optional)

---

## Project Goal

Create a groundwater transport case study that:
1. Is **simpler and independent** from the flow case study (no error carry-over)
2. Uses the **base parent model** (fresh download) as the foundation
3. **Integrates wells** from the flow case (same locations, analyze well-contaminant interactions)
4. Demonstrates the **telescope/submodel approach** for transport
5. Allows students to work on **different contaminant scenarios** per group
6. Provides flexibility in solution methods (numerical/analytical/hybrid)

## Key Design Decisions (2025-11-01)

### Decision 1: Wells are INCLUDED
- Each group uses the same well field from their flow case study
- Wells are loaded from the existing `case_config.yaml`
- Students analyze how pumping wells capture contamination and how injection wells/Sickergalerie spread it
- Contaminant sources are placed strategically relative to the well field
- This adds real-world relevance: understanding well-contaminant interactions is critical for groundwater management

### Decision 2: Analytical Comparison is OPTIONAL
- **Groups can optionally verify their numerical model with analytical solutions**
- **If chosen, two tiers available**:
  - **Tier 1** (Groups 0, 1, 2, 5 - conservative tracers): Full 1D Ogata-Banks comparison
  - **Tier 2** (Groups 3, 4, 6, 7, 8 - reactive transport): Simplified comparison OR justification
- **Rationale**: While professional modelers verify, this is a learning exercise focused on transport modeling workflow. Verification adds significant complexity and time.
- **Implementation**: Templates provided in SUPPORT_REPO for students who choose to verify
- **Grading**: Bonus points available (5-10% extra credit) for students who complete analytical verification

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

**Purpose**: Demonstrate transport concepts and MT3D-USGS setup to students

**Status**: Sections 1-6 implemented (as of 2025-11-03)

**Content Structure (IMPLEMENTED)**:

#### **Section 1: Overview - Learning Path for Contaminant Transport Modeling**
   - 1.1 The Problem: Contaminant Plume Migration
   - 1.2 The Approach: Simple to Complex (roadmap through sections)
   - 1.3 Why This Structure? (pedagogical justification)
   - 1.4 Learning Outcomes
   - 1.5 Notebook Structure (visual roadmap)
   - 1.6 The Key Insight (analytical → verification → application)

**Key Innovation**: Students see the entire learning journey upfront - why we start with analytical, verify numerically, then apply to real cases.

#### **Section 2: Introduction to Contaminant Transport Modeling**
   - 2.1 Fundamental Transport Processes (advection, dispersion, sorption, decay)
   - 2.2 Governing Equation (3D advection-dispersion-reaction)
   - 2.3 **Formulation with Forcing Terms** (NEW - comprehensive source term theory)
     - Complete transport equation with sources/sinks
     - Physical interpretation of forcing terms
     - Mathematical forms for different source types (Dirichlet, Neumann, Cauchy)
     - Units and consistency
     - Boundary and initial conditions
     - Solution strategy in MT3D-USGS
     - Key takeaways for modeling
   - 2.4 Analytical vs. Numerical Solutions
   - 2.5 MT3D-USGS: Modular Transport Simulator (package overview)
   - 2.6 When to Use Which Method? (decision framework)
   - 2.7 References

**Key Innovation**: Section 2.3 provides comprehensive theoretical foundation for source terms, eliminating need for separate section later.

#### **Section 3: Analytical Solution - Ogata-Banks for 1D Transport**
   - 3.1 The Ogata-Banks Solution (theory and equations)
   - 3.2 Implement Ogata-Banks Function (Python implementation)
   - 3.3 Visualize Analytical Solution (parameter exploration)
   - 3.4 Summary: Analytical Solution Established

**Purpose**: Establish "ground truth" before any numerical modeling. Students understand what the correct answer should look like.

#### **Section 4: Numerical Verification - 1D MT3D-USGS Model**
   - 4.1 Why Verify Against Analytical Solution?
   - 4.2 Model Design for Verification (Pe = 0.5 target)
   - 4.3 Set Up 1D MODFLOW Model
   - 4.4 Set Up 1D MT3D Model (all packages: BTN, ADV, DSP, SSM, GCG)
   - 4.5 Run 1D MT3D and Extract Results
   - 4.6 Compare MT3D Results to Analytical Solution
   - 4.8 Summary: Numerical Verification Complete

**Purpose**: Build confidence in MT3D-USGS. Students see <10% error when properly configured (Pe = 0.5). This establishes that the tool works correctly.

#### **Section 5: Load Limmat Valley Flow Model**
   - 5.1 Import Libraries
   - 5.2 Load and Run Parent Flow Model
   - 5.3 Load and Inspect Flow Results
   - 5.4 Summary: Flow Model Ready for Transport

**Purpose**: Transition from idealized 1D to real 2.5D Limmat Valley model.

#### **Section 6: 2.5D Transport - Limmat Valley Implementation**
   - 6.1 Define Contaminant Source Location (includes source term practical implementation)
   - 6.2 Create MT3D Model and Check Grid Resolution (Pe = 5.0 - too coarse!)
   - 6.3 Set Up MT3D Packages (BTN, ADV, DSP, SSM)
   - 6.4 Optional: RCT Package for Reactive Transport
   - 6.5 Write and Run MT3D Model
   - 6.6 Load Concentration Results
   - 6.7 Diagnostic Analysis of Concentrations
   - 6.8 Visualize Concentration Over Time
   - 6.9 Summary: 2.5D Transport Implementation Complete
   - 6.10 **Diagnosis: Grid Resolution is the Problem**
     - Peclet Number Check (Pe = 5.0 vs Pe = 0.5)
     - The Contrast: Good vs Bad Resolution (comparison with Section 4)
     - Why We Implemented It Anyway (learning from controlled failure)
     - When is Coarse Grid Acceptable?
     - Solution: Telescope Approach (preview of Section 7)
     - What We Learned Despite Coarse Grid

**Key Innovation**: Section 6 deliberately implements transport on coarse grid (Pe = 5.0) to create a "controlled failure." Section 6.10 diagnoses why it fails and contrasts with successful Section 4 (Pe = 0.5). This teaches students to recognize and diagnose grid resolution problems.

**Pedagogical Flow**:
- Section 3: Theory → "correct answer"
- Section 4: Proper numerical implementation → success (Pe = 0.5)
- Section 6: Coarse grid implementation → problems (Pe = 5.0)
- Section 6.10: Diagnosis → understanding
- Section 7: Solution → telescope approach

#### **Section 7: Alternative Approaches and Method Selection** (PLANNED - not yet implemented)
   - When analytical solutions are sufficient
   - Hybrid approaches (particle tracking, analytical overlays)
   - Trade-offs between methods
   - Decision framework for method selection

#### **Section 8: Telescope Approach for Transport** (PLANNED - not yet implemented)
   - Why refine around the source area?
   - Creating transport submodel from parent model
   - Extracting flow boundary conditions
   - Running transport on submodel with Pe = 0.5
   - Comparison: coarse (Section 6) vs refined (Section 8)
   - Advantages: resolution, computation time

**Key Teaching Points**:
- Students see complete workflow before their assignment
- **Analytical-first approach builds confidence** (Section 3)
- **Verification is mandatory** (Section 4)
- **Learning from controlled failure** (Section 6.10 diagnosis)
- **Grid resolution is critical** (Pe number as diagnostic)
- Clear explanation of when/why telescope approach helps (Section 8)
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

#### 13. (OPTIONAL) Analytical Verification for Bonus Credit
```python
# OPTIONAL: Students can choose to complete this for bonus points
# Extract 1D transect from MT3DMS results
# Implement Ogata-Banks analytical solution
# Compare numerical vs. analytical results
# Plot comparison at multiple times
# Breakthrough curve comparison
# Discuss discrepancies and when each method is appropriate
```

**For Tier 1 Groups (0, 1, 2, 5)** - if choosing to do verification:
- Full implementation of 1D analytical solution
- Direct comparison with MT3DMS along flow transect
- Quantify differences and explain causes (2D effects, grid discretization, etc.)
- **Bonus**: +5-10% extra credit

**For Tier 2 Groups (3, 4, 6, 7, 8)** - if choosing to do verification:
- Choose Option A, B, or C (see analytical_verification in config)
- If A: Run MT3DMS without reactions, compare to Ogata-Banks
- If B: Implement analytical with R/λ, compare to full MT3DMS
- If C: Justify why analytical comparison is not meaningful for your scenario
- **Bonus**: +5-10% extra credit

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
    title: "Sports field fertilizer contamination"
    contaminant: "Nitrate (NO3-)"
    description: >
      Continuous nitrate loading from over-fertilized sports fields/football pitches.
      Evaluate long-term plume development and potential impact on nearby drinking water wells.

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
    title: "Garden allotment pesticide contamination"
    contaminant: "Atrazine"
    description: >
      Diffuse pesticide source from family garden plots (Schrebergärten) with sorption.
      Evaluate retardation effects and breakthrough timing at monitoring locations.

  - id: 5
    group: 5
    title: "PFAS contamination"
    contaminant: "PFOA (perfluorooctanoic acid)"
    description: >
      Point source PFAS release (conservative, mobile). Assess long-term
      migration and compliance with drinking water standards.

  - id: 6
    group: 6
    title: "Dry cleaning facility solvent leak"
    contaminant: "Perchloroethylene (PCE)"
    description: >
      Point source PCE leak from urban dry cleaning facility with slight sorption.
      Assess plume migration and potential for natural attenuation.

  - id: 7
    group: 7
    title: "Leaking sewer line contamination"
    contaminant: "Ammonium"
    description: >
      Continuous ammonium discharge from aging urban sewer infrastructure with
      nitrification (decay). Model transformation and downgradient concentration profiles.

  - id: 8
    group: 8
    title: "Metal plating facility chromium leak"
    contaminant: "Chromium (Cr-VI)"
    description: >
      Point source chromium from electroplating workshop with sorption. Assess plume
      mobility and evaluate pump-and-treat remediation timing requirements.

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

# Modeling approach
approach:
  primary_method: "numerical_mt3d"        # Primary method is always MT3DMS

  analytical_comparison:
    required: true                         # MANDATORY for all groups
    tier: 1                                # 1 for simple, 2 for moderate (assigned by scenario)

  justification: >
    TODO: Explain why numerical MT3DMS is needed for your scenario.
    Consider: 2D/3D effects, well influences, boundary conditions,
    heterogeneity that analytical solutions cannot capture.

# Analytical comparison requirements (OPTIONAL - bonus credit available)
analytical_verification:
  optional: true  # Set to false if you choose not to do verification
  tier: 1  # or 2, automatically set based on group scenario

  # Tier 1 requirements (Groups 0, 1, 2, 5 - conservative tracers)
  tier_1_tasks:
    - "Extract 1D concentration transect from MT3DMS results along flow direction"
    - "Implement 1D Ogata-Banks analytical solution with same parameters (v, D, source)"
    - "Plot comparison: analytical vs. numerical at multiple times"
    - "Calculate breakthrough curves at monitoring point: analytical vs. numerical"
    - "Discuss discrepancies (2D spreading, grid effects, boundary conditions)"
    - "Conclude when analytical is sufficient vs. when numerical is required"

  # Tier 2 requirements (Groups 3, 4, 6, 7, 8 - reactive transport)
  tier_2_options:
    option_a: "Run simplified MT3DMS without reactions (Kd=0, λ=0), compare to Ogata-Banks"
    option_b: "Implement 1D analytical with retardation/decay, compare to full MT3DMS"
    option_c: "Detailed written justification why analytical comparison is not meaningful"

  tier_2_tasks:
    - "Choose one of the three options above"
    - "If Option A or B: Plot and discuss comparison"
    - "If Option C: Explain specific aspects that make analytical unsuitable"
    - "In all cases: discuss what transport processes require numerical modeling"

  notes: >
    Analytical comparison is OPTIONAL (bonus credit: +5-10%). Templates provided in SUPPORT_REPO
    for students who choose to verify their models. This demonstrates professional verification
    practice and understanding of when simple vs. complex methods are needed.
    Budget 30-60 minutes if you choose to complete this.

# Analysis tasks
analysis_tasks:
  - "Map concentration distribution at 1, 3, 5, and 10 years"
  - "Plot breakthrough curves at monitoring points"
  - "Calculate plume extent (area where C > 1 mg/L) over time"
  - "Estimate time for contamination to reach compliance point"
  - "Assess whether concentration exceeds threshold at any location"
  - "Evaluate mass balance (% mass remaining in domain vs exported)"
  - "Analyze well-contaminant interactions (capture zones, spreading)"
  - "OPTIONAL (bonus): Analytical comparison (tier 1 or tier 2 requirements)"
  - "Sensitivity analysis: vary dispersivity ±50%, compare results"

# Deliverables
deliverables:
  - "Completed transport_config.yaml with justified parameters"
  - "Executed case_study_transport_group_X.ipynb with all results"
  - "Concentration maps (at least 4 time steps)"
  - "Breakthrough curves at monitoring points"
  - "Mass balance summary"
  - "OPTIONAL (bonus): Analytical comparison section with plots and discussion"
  - "Analysis of well effects on contaminant transport"
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
| 0 | 210 | Mixed | TCE | Industrial spill upgradient | No | No | Will pumping wells capture the plume? |
| 1 | 219 | Mixed | Nitrate | Sports field fertilizer | No | No | Effect on downgradient wells |
| 2 | 201 | Mixed | Chloride | Legacy landfill | No | No | Extent of historical plume |
| 3 | 236 | Mixed | Benzene | Gas station leak | No | Yes | Natural attenuation vs. capture |
| 4 | 190 | Mixed | Atrazine | Garden allotment pesticide | Yes | No | Retardation effects |
| 5 | 223 | Mixed | PFOA | Industrial point source | No | No | Long-term migration |
| 6 | 227 | Mixed | PCE | Dry cleaning facility leak | Slight | No | Plume migration and attenuation |
| 7 | 213 | Mixed | Ammonium | Leaking sewer line | No | Yes | Degradation in capture zone |
| 8 | 207 | Mixed | Chromium | Metal plating facility | Yes | No | Sorption + pumping interaction |

**Note**: "Mixed" means well fields contain both pumping wells (extraction) and injection wells/Sickergalerie. Groups will need to:
1. Identify which wells pump and which inject
2. Place contamination source strategically relative to wells
3. Analyze how wells affect contaminant fate and transport

### Scenario Complexity and Analytical Comparison Tiers

**Tier 1 - Simple Scenarios (Groups 0, 1, 2, 5, 6):**
- Conservative tracer (no sorption or decay, or very slight sorption for PCE)
- Focus on advection, dispersion, and well capture/spreading
- **Analytical verification (optional bonus)**: Full 1D Ogata-Banks comparison
  - Extract 1D transect from numerical model
  - Implement analytical solution with same parameters
  - Plot comparison and discuss differences
  - Estimate when analytical is "good enough" vs. when 2D/3D numerical is needed
  - **Bonus credit**: +5-10%

**Tier 2 - Moderate Scenarios (Groups 3, 4, 7, 8):**
- Reactive transport (sorption OR decay)
- Combined effect of reactions + well pumping/injection
- **Analytical verification (optional bonus)**: Choose one option
  - **Option A**: Simplified comparison (set Kd=0 and λ=0, compare conservative transport)
  - **Option B**: Semi-analytical with retardation/decay (1D with R and λ)
  - **Option C**: Detailed justification why analytical comparison is not feasible/meaningful
  - **Bonus credit**: +5-10%
- **Purpose**: Understand what aspects require numerical modeling vs. can be solved analytically

---

## Implementation Steps

### Phase 1: Planning and Design ✅ COMPLETE
- [x] Define overall approach (simpler, independent from flow case)
- [x] Finalize 9 transport scenarios (one per group)
- [x] Design transport_config.yaml structure
- [x] Outline both notebook structures
- [x] Update planning document with implemented structure (2025-11-03)

### Phase 2: Teaching Notebook (4b_transport_model_implementation.ipynb) - PARTIALLY COMPLETE
**Completed (2025-11-03):**
- [x] Section 1: Overview and learning path with complete pedagogical roadmap
- [x] Section 2: Transport fundamentals with comprehensive forcing terms theory
- [x] Section 3: Analytical solution (Ogata-Banks) implementation and visualization
- [x] Section 4: 1D numerical verification (MT3D-USGS) with analytical comparison
- [x] Section 5: Load Limmat Valley flow model
- [x] Section 6: 2.5D transport on coarse grid (Pe = 5.0) with diagnostic analysis
- [x] Section 6.10: Comprehensive diagnosis of grid resolution problems

**Remaining:**
- [ ] Section 7: Alternative approaches and method selection (partially implemented, needs completion)
- [ ] Section 8: Telescope approach demonstration (create refined submodel, compare with Section 6)
- [ ] Test complete notebook end-to-end (Sections 1-8)
- [ ] Add exercises/reflection questions (if needed)

**Key Changes from Original Plan:**
- Added Section 1 as comprehensive overview/roadmap (major pedagogical improvement)
- Expanded Section 2.3 to include complete forcing terms theory (eliminates need for separate source term section)
- Section 6 deliberately uses coarse grid (Pe = 5.0) as "controlled failure" for learning
- Section 6.10 provides detailed diagnosis comparing good (Sec 4) vs bad (Sec 6) resolution
- Telescope approach moved to Section 8 (was originally Section 6)

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
- [ ] **Add analytical solution functions to SUPPORT_REPO** (for students choosing optional verification)
  - [ ] Ogata-Banks 1D solution (instantaneous and continuous source)
  - [ ] 1D solution with retardation factor
  - [ ] 1D solution with first-order decay
  - [ ] Combined retardation + decay
  - [ ] Helper function to extract 1D transect from 2D/3D MT3DMS results
  - [ ] Template plotting functions for analytical vs. numerical comparison
- [ ] Create helper functions for common transport tasks
  - [ ] Source term cell identification
  - [ ] Breakthrough curve plotting (both numerical and analytical)
  - [ ] Mass balance checking
  - [ ] Stability criteria checking (Courant, Peclet)
  - [ ] Velocity calculation from head gradients
- [ ] Add transport-specific plotting utilities
  - [ ] Concentration map plotting with well locations
  - [ ] Side-by-side analytical vs. numerical comparison plots
  - [ ] Breakthrough curve comparison templates
- [ ] **Create professional report template** (CRITICAL for deliverable)
  - [ ] LaTeX or Word template with standard structure
  - [ ] Example filled-in report (from group_0 demo)
  - [ ] Figure quality guidelines
  - [ ] Citation style guidance
  - [ ] Writing style tips for technical reports

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

## Professional Report Structure (3-4 pages)

Students must submit a concise professional modeling report (PDF, 3-4 pages) focusing on key learning goals:

### Report Outline

**1. Problem Statement and Objectives (0.5 page)**
- Brief description of well field and contamination scenario
- Modeling objectives (what questions are we answering?)
- Why numerical modeling is needed (justify over analytical alone)

**2. Methodology (0.75 page)**
- Transport model setup summary (domain, parameters, source term)
- Key assumptions and their justification
- (If completed) Brief mention of analytical verification approach

**3. Results (1.5-2 pages, mostly figures with brief text)**
- **Figure 1**: Concentration map at key time (e.g., 5 or 10 years)
- **Figure 2**: Breakthrough curve at critical location
- **Figure 3** (optional): Analytical vs. numerical comparison (if completed)
- Brief text: Maximum concentrations, breakthrough times, plume extent
- Well-contaminant interaction summary (capture or spreading)

**4. Discussion and Conclusions (0.75-1 page)**
- Interpretation: What do results mean for the scenario?
- (If completed) Analytical comparison: When is simple method sufficient? When is numerical needed?
- Parameter uncertainty: Which parameters matter most?
- Recommendations: Well management, monitoring, or remediation suggestions

### Key Learning Goals Assessed in Report

✓ **Communication**: Distill technical work into client-ready summary
✓ **Critical thinking**: Justify modeling choices and parameter selection
✓ **Analysis**: Interpret results in context of well-contaminant interactions
✓ **Verification (bonus)**: If completed, explain value and limitations of analytical comparison
✓ **Engineering judgment**: Provide actionable recommendations

### Quality Guidelines

- **Figures**: High resolution, clear labels, captions, referenced in text
- **Conciseness**: Every sentence adds value, no filler
- **Professional tone**: Technical but accessible, past tense for methods
- **Citations**: Cite FloPy, MT3DMS, parameter sources

### Template Provided

A Word/LaTeX template with this structure will be provided with:
- Formatting guidelines
- Example figures with proper captions
- Writing tips for each section

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

2. ~~**Analytical comparison**: Required or optional?~~
   - **DECIDED (2025-11-03)**: **Optional with bonus credit**
   - **Tier 1** (Simple scenarios - Groups 0, 1, 2, 5): Full analytical comparison available (1D Ogata-Banks) - bonus +5-10%
   - **Tier 2** (Moderate scenarios - Groups 3, 4, 6, 7, 8): Simplified analytical comparison OR justification - bonus +5-10%
   - **Rationale**: While verification is professional practice, this is a learning exercise focused on transport workflow. Making it optional reduces student workload while still providing incentive for those interested in deeper understanding.

3. ~~**Time constraints**: How many weeks for transport case study?~~
   - **DECIDED**: 2-3 weeks, approximately **10 hours total** including report writing
   - **Breakdown estimate**:
     - Read/understand teaching notebook (4b): 1-2 hours
     - Setup and adapt demo for their scenario: 2-3 hours
     - Run simulations and troubleshoot: 2-3 hours
     - (Optional) Analytical comparison: 0.5-1 hour (with templates) - bonus credit
     - Analysis and interpretation: 1-2 hours
     - Professional report writing (3-4 pages): 2-3 hours
   - **Total: ~8-10 hours** (manageable for 2-3 week timeline, 10-11 hours if including optional verification)

4. ~~**Coupling**: Do any groups eventually combine flow + transport? (e.g., pumping well capture of contamination)~~
   - **DECIDED**: Yes! Wells will be active in the transport model. Groups will analyze how their pumping/injection wells affect contaminant transport (capture zones, plume spreading from injection wells).

5. ~~**Software flexibility**: How much do we encourage alternative methods?~~
   - **DECIDED**: MT3DMS via FloPy is **strongly recommended** but not required
   - Alternative **open-source/free** software is **permitted** if:
     - Software is publicly and freely available
     - Can be run/reviewed by tutors
     - Students provide complete model setup and instructions for reproduction
     - Analytical comparison requirement still applies
   - **Examples of acceptable free alternatives**:
     - MODFLOW 6 with GWT package (via FloPy)
     - OpenGeoSys (OGS)
     - MT3D-USGS
     - PHT3D (if free version available)
   - **Student responsibility**: Using alternative software will require significantly more work (no templates, no direct support)
   - **Recommendation**: Strongly encourage MT3DMS/FloPy for 10-hour time constraint
   - **Grading**: Same rubric applies regardless of software choice

6. ~~**Deliverables format**: Notebook only, or separate report?~~
   - **DECIDED**: Three required deliverables for ALL students

   **Deliverable 1: Technical Implementation**
   - **If using MT3DMS/FloPy (recommended)**:
     - Jupyter notebook (.ipynb) with code, results, and narrative markdown
     - Completed transport_config.yaml
   - **If using alternative software**:
     - All model input files
     - Setup instructions/documentation (reproducible steps)
     - Results visualization and analysis (notebook or script)
     - Completed transport_config.yaml (adapted as needed)

   **Deliverable 2: Professional Report (PDF)** - **MANDATORY for all groups**
   - Concise professional modeling report in PDF format
   - Purpose: Demonstrate ability to communicate key results to clients/stakeholders
   - Structure follows standard groundwater modeling report format (template provided)
   - **Target length: 3-4 pages (including figures)**
   - Focus on: problem statement, key results, analytical verification, conclusions
   - Allocation: 2-3 hours of the 10-hour budget

   **Deliverable 3: Model Files**
   - Completed and executed notebook OR model setup files
   - transport_config.yaml
   - Any supplementary scripts or data

   - **Rationale**:
     - Professional report writing is a critical engineering skill
     - Separates technical implementation (notebook) from communication (report)
     - Mimics real-world consulting: technical work + client deliverable

7. ~~**Grading criteria**: What aspects are weighted?~~
   - **DECIDED (Updated 2025-11-03)**: Grading split between technical implementation and professional report

   **Technical Implementation (50%)**:
   - Model setup and configuration (15%)
   - MT3DMS implementation and execution (20%)
   - Quality checks and mass balance (15%)

   **Professional Report (50%)**:
   - Problem statement and objectives (10%)
   - Methodology description (10%)
   - Results presentation and visualization (15%)
   - Interpretation, analysis, and conclusions (10%)
   - Professional writing quality and format (5%)

   **Bonus Credit (up to +10%)**:
   - Analytical verification (tier 1 or tier 2): +5-10% depending on completeness and quality
   - This allows motivated students to exceed 100% on the assignment

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
- Read/understand teaching notebook (4b): 1-2 hours
- Setup and adapt demo for their scenario: 2-3 hours
- Run simulations and troubleshoot: 2-3 hours
- Analysis and interpretation: 1-2 hours
- Professional report writing (3-4 pages): 2-3 hours
- **(Optional) Analytical comparison (with templates): 0.5-1 hour** - bonus credit
- **Total: ~8-10 hours per group** (target based on 2-3 week timeline)
- **Total with bonus: ~10-11 hours** if including analytical verification

**Note**: The 8-10 hour target is achievable because:
- Wells are reused from flow case (no new implementation)
- No mandatory analytical comparison (reduced from original 10 hours)
- Templates provided for report and optional analytical solutions
- No parameter scenarios (simpler than flow case)
- Demo notebook provides complete working example
- Concise report format (3-4 pages) focuses on key learning goals

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
