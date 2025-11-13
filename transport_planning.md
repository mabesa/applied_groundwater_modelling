# Transport Case Study Planning Document

> **📋 IMPORTANT: This is the authoritative planning document for the transport case study**
>
> **For AI Assistants**: Always read this document at the start of any session involving transport materials. All design decisions, structure, and implementation guidance are documented here.
>
> **For Instructors**: This document guides all transport case study development. Update it when design decisions change.
>
> **Last Updated**: 2025-11-09
> **Status**: Planning complete - ready for implementation (analytical verification is optional without bonus credit)

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
- **Rationale**: While professional modelers verify, this is a learning exercise focused on transport modeling workflow. Verification adds significant complexity and time.
- **Implementation**: Templates provided in SUPPORT_REPO for students who choose to verify
- **Grading**: Optional component that demonstrates advanced understanding, but does not affect grading
- **Note**: All groups have equal opportunity for verification regardless of contaminant properties (conservative vs. reactive)

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
│       │   ├── case_config_transport.yaml  ← NEW: Transport scenario config (all groups)
│       │   └── case_study_transport_group_0.ipynb  ← NEW: Complete demo case
│       ├── group_1/
│       │   └── case_config_transport.yaml  ← Same file, different group uses id: 1
│       ├── group_2/
│       │   └── case_config_transport.yaml  ← Same file, different group uses id: 2
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

#### **Section 3: Analytical Solution - Pulse Source for 1D Transport**
   - 3.1 The Pulse Source Solution (theory and equations)
   - 3.2 Implement Pulse Source Function (Python implementation)
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
# Load case_config.yaml (group number, authors, wells from flow case)
# Load case_config_transport.yaml (transport scenarios, select by group number)
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
# Identify source location from case_config_transport.yaml
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
# Answer scenario-specific questions from case_config_transport.yaml
# Maximum extent of plume
# Time to reach monitoring/compliance points
# Concentration exceedances
# Effectiveness of natural attenuation (if decay/sorption)
```

#### 13. (OPTIONAL) Analytical Verification
```python
# OPTIONAL: Students can choose to complete this section
# Extract 1D transect from MT3DMS results
# Implement pulse source analytical solution
# Compare numerical vs. analytical results
# Plot comparison at multiple times
# Breakthrough curve comparison
# Discuss discrepancies and when each method is appropriate
```

**If choosing to do verification** - available to all groups:
- Implementation approach depends on contaminant properties:
  - **Conservative tracers**: Direct 1D analytical comparison possible
  - **Reactive transport**: Can compare conservative scenario OR implement analytical with sorption/decay
- Quantify differences and explain causes (2D effects, grid discretization, reactions, etc.)
- Discuss when analytical vs. numerical methods are appropriate

#### 14. Summary and Conclusions
- Key findings for your scenario
- Parameter sensitivity discussion
- Limitations and uncertainties
- Recommendations

---

## Configuration File Design

### Complementary Configuration Strategy

**Design Decision**: Transport configuration is **complementary** to flow configuration, not duplicative.

- **case_config.yaml** (from flow case study): Contains group number, authors, concession, and well definitions
- **case_config_transport.yaml** (new for transport): Contains transport-specific parameters, all 9 scenarios, and references wells from case_config.yaml

**Benefits of this approach**:
- Eliminates duplication (DRY principle)
- Single source of truth for wells (avoids inconsistencies)
- Students load both configs: `case_config.yaml` for wells/concession, `case_config_transport.yaml` for transport scenario
- Easier maintenance (update wells in one place)

### case_config_transport.yaml Structure

**Note**: This file contains ALL 9 transport scenarios (id 0-8). Each group uses the scenario matching their group number.

```yaml
###############################################################
# Transport Case Study Configuration (All Groups)
###############################################################
# This file contains ALL transport scenarios for groups 0-8.
# Each group uses the scenario matching their group number.
# Wells are REUSED from flow case study (case_config.yaml).
# The group number and authors are already defined in the case_config.yaml file.

# Base parent model (fresh download, independent from student flow results)
model:
  data_name: baseline_model               # Fixed - downloads known-good model
  workspace: "~/applied_groundwater_modelling_data/limmat/transport/baseline_model"
  namefile: "limmat_valley_model_nwt.nam"

# Transport submodel output location
output:
  workspace: "~/applied_groundwater_modelling_data/limmat/transport/case_study_transport_group_"

# Wells from flow case study (REUSED, not reimplemented)
wells:
  source: "case_config"                   # Reuse wells from flow case study
  config_file: "./case_config.yaml"       # Path to flow case configuration

# Transport scenario assignments (FIXED by group number)
transport_scenarios:
  options:
    # ========== GROUP 0: TCE - Industrial Spill (Demo) ==========
    - id: 0
      title: "Industrial solvent spill (TCE)"
      contaminant: "Trichloroethylene (TCE)"
      description: >
        A 30-day TCE spill from an industrial facility. Assess plume migration
        under natural gradient conditions and with well pumping/injection effects.
        Determine if/when contamination reaches the well (monitoring location).

      properties:
        cas_number: "79-01-6"
        molecular_weight_g_mol: 131.39
        solubility_mg_L: 1100
        conservative: true                # No sorption or decay

      transport:
        porosity: 0.25
        bulk_density_kg_m3: 1800.0
        longitudinal_dispersivity_m: 10.0
        transverse_dispersivity_m: 1.0
        vertical_dispersivity_m: 0.1
        molecular_diffusion_m2_s: 1.0e-9
        sorption: false
        distribution_coefficient_mL_g: 0.0
        decay: false
        first_order_decay_constant_1_per_day: 0.0
        half_life_days: null

      source:
        type: "point"
        release_type: "pulse"
        location:
          easting: +60              # m, relative to well locations
          northing: +60             # m, relative to well locations
          layer: 1
        start_time_days: 0
        duration_days: 30               # 30-day spill
        concentration_mg_L: 100.0

      simulation:
        duration_days: 3650             # 10 years
        output_times_days: [30, 90, 180, 365, 730, 1095, 1825, 3650]

      submodel:
        buffer_north_m: 500
        buffer_south_m: 500
        buffer_east_m: 500
        buffer_west_m: 500
        cell_size_m: 5

      monitoring:
        threshold_mg_L: 5.0
        compliance_location: "Property boundary and Limmat River"

    # ========== Additional scenarios for Groups 1-8 follow same structure ==========
    # See case_config_transport.yaml for complete definitions

# Analytical comparison (OPTIONAL)
analytical_verification:
  optional: true                          # OPTIONAL for all groups

  notes: >
    Analytical comparison is OPTIONAL. Templates provided in SUPPORT_REPO.
    Completing this section demonstrates professional verification practice and deepens
    understanding of numerical modeling limitations. Budget 30-60 minutes for this task
    if you choose to complete it.

    All groups can complete analytical verification regardless of contaminant properties.
    Approach depends on scenario: conservative tracers can use direct comparison,
    reactive transport can compare simplified scenarios or use analytical solutions with reactions.

# Analysis tasks (apply to all groups)
analysis_tasks:
  - "Map concentration distribution at 1, 3, 5, and 10 years"
  - "Plot breakthrough curves at all monitoring points"
  - "Calculate plume extent (area where C > threshold) over time"
  - "Estimate time for contamination to reach compliance points"
  - "Assess whether concentration exceeds threshold at any location/time"
  - "Evaluate mass balance (% mass remaining vs. exported vs. captured by wells)"
  - "Analyze well-contaminant interactions (capture zones, spreading from injection)"
  - "OPTIONAL: Analytical comparison for verification"
  - "Sensitivity analysis: vary dispersivity ±50%, compare results"
  - "Create concentration vs. time plots at key locations"

# Quality control checklist (apply to all groups)
quality_checks:
  - "Mass balance error < 1%"
  - "Courant number ≤ 1 (advective stability)"
  - "Peclet number ≤ 2-4 (dispersive stability)"
  - "Plume contained within submodel domain (or justify truncation)"
  - "Concentration values physically reasonable (no negatives, no overshoot)"
  - "Results make sense given flow direction, source location, and well pumping/injection"
  - "MT3DMS convergence achieved for all time steps"
  - "Flow model converged and mass balance closed before running transport"

# Deliverables (apply to all groups)
deliverables:
  technical:
    - "Completed case_config_transport.yaml with justified parameters"
    - "Executed case_study_transport_group_X.ipynb with all results"
    - "MT3DMS model files (input and output)"
    - "Concentration maps (at least 4 time steps)"
    - "Breakthrough curves at all monitoring points"
    - "Mass balance summary table"
    - "OPTIONAL: Analytical comparison section with plots and discussion"
    - "Analysis of well effects on contaminant transport"
    - "Parameter sensitivity plots (dispersivity variation)"

  report:
    format: "PDF"
    length_pages: "3-4"
    sections:
      - "Problem statement and objectives (0.5 page)"
      - "Methodology (0.75 page)"
      - "Results with figures (1.5-2 pages)"
      - "Discussion and conclusions (0.75-1 page)"
    notes: >
      Professional modeling report demonstrating communication skills.
      Template provided. Focus on key findings and well-contaminant interactions.
      Include analytical comparison section only if you completed that optional work.
```
  - "Executed case_study_transport_group_X.ipynb with all results"
  - "Concentration maps (at least 4 time steps)"
  - "Breakthrough curves at monitoring points"
  - "Mass balance summary"
  - "OPTIONAL: Analytical comparison section with plots and discussion"
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

### Scenario Complexity

**Conservative Tracer Scenarios (Groups 0, 1, 2, 5, 6):**
- No sorption or decay (or very slight sorption for PCE)
- Focus on advection, dispersion, and well capture/spreading
- Simpler transport physics, good for learning fundamentals
- **Analytical verification (optional)**: Direct 1D comparison possible

**Reactive Transport Scenarios (Groups 3, 4, 7, 8):**
- Sorption OR decay processes included
- Combined effect of reactions + well pumping/injection
- More complex transport physics, realistic contaminant behavior
- **Analytical verification (optional)**: Multiple approaches possible
  - Compare simplified conservative scenario, OR
  - Use analytical solutions with retardation/decay factors

**Note on Analytical Verification**: All groups have equal opportunity to complete analytical verification. The approach may differ based on contaminant properties, but the learning value is equivalent.

---

## Implementation Steps

### Phase 1: Planning and Design ✅ COMPLETE
- [x] Define overall approach (simpler, independent from flow case)
- [x] Finalize 9 transport scenarios (one per group)
- [x] Design case_config_transport.yaml structure (complementary to case_config.yaml)
- [x] Outline both notebook structures
- [x] Update planning document with implemented structure (2025-11-03)
- [x] Update group_0 template to make analytical verification optional (2025-11-04)
- [x] Implement complementary config design: case_config.yaml + case_config_transport.yaml (2025-11-07)
- [x] Remove tier distinctions from analytical verification (2025-11-07)

### Phase 2: Teaching Notebook (4b_transport_model_implementation.ipynb) ✅ COMPLETE
**Completed (2025-11-03):**
- [x] Section 1: Overview and learning path with complete pedagogical roadmap
- [x] Section 2: Transport fundamentals with comprehensive forcing terms theory
- [x] Section 3: Analytical solution (pulse source) implementation and visualization
- [x] Section 4: 1D numerical verification (MT3D-USGS) with analytical comparison
- [x] Section 5: Load Limmat Valley flow model
- [x] Section 6: 2.5D transport on coarse grid (Pe = 5.0) with diagnostic analysis
- [x] Section 6.10: Comprehensive diagnosis of grid resolution problems
- [x] Section 7: Alternative approaches and method selection
- [x] Section 8: Telescope approach demonstration (create refined submodel, compare with Section 6)
- [x] Test complete notebook end-to-end (Sections 1-8)

**Key Changes from Original Plan:**
- Added Section 1 as comprehensive overview/roadmap (major pedagogical improvement)
- Expanded Section 2.3 to include complete forcing terms theory (eliminates need for separate source term section)
- Section 6 deliberately uses coarse grid (Pe = 5.0) as "controlled failure" for learning
- Section 6.10 provides detailed diagnosis comparing good (Sec 4) vs bad (Sec 6) resolution
- Telescope approach moved to Section 8 (was originally Section 6)

**Status**: Teaching notebook is complete and ready for student use

### Phase 3: Demo Case Study (group_0/) ✅ COMPLETE
**Status**: Demo case study notebook fully implemented and ready for testing

**Completed (2025-11-04):**
- [x] Create case_config_transport.yaml with all 9 transport scenarios
- [x] Create case_study_transport_group_0.ipynb structure with all sections
- [x] Update both files to make analytical verification optional (without bonus credit)

**Completed (2025-11-07):**
- [x] Implement complementary config design (loads from both case_config.yaml and case_config_transport.yaml)
- [x] Update planning document to reflect improved design

**Completed (2025-11-09):**
- [x] Full implementation of all core sections (Sections 1-17)
- [x] Configuration and parent model loading
- [x] Well loading and submodel domain definition
- [x] Telescope submodel creation with refined grid
- [x] MT3D-USGS transport model setup (all packages)
- [x] Source term definition and implementation
- [x] Transport simulation execution
- [x] Post-processing and visualization
- [x] Quality checks and diagnostics
- [x] Well-contaminant interaction analysis
- [x] Optional analytical verification section
- [x] Sensitivity analysis
- [x] Summary and conclusions

**Next Step**: Testing and validation (Phase 3.3)

### Phase 4: Student Configurations (groups 1-8) ✅ COMPLETE
**Status**: All 9 transport scenarios defined in case_config_transport.yaml

**Note**: All group configurations (0-8) are defined in the shared case_config_transport.yaml file. Each group uses their group ID to select their specific scenario.

#### 4.1 Configuration Files
- [ ] **Group 1 (Concession 219): Nitrate - Sports field fertilizer**
  - [ ] Load well data from existing case_config.yaml
  - [ ] Define continuous source (fertilizer application)
  - [ ] Set nitrate parameters: conservative tracer
  - [ ] Position source near sports fields

- [ ] **Group 2 (Concession 201): Chloride - Legacy landfill**
  - [ ] Load well data
  - [ ] Define long-duration continuous source (10-year history)
  - [ ] Set chloride parameters: conservative tracer
  - [ ] Position source at landfill location

- [ ] **Group 3 (Concession 236): Benzene - Gas station leak**
  - [ ] Load well data
  - [ ] Define point source with decay (biodegradation)
  - [ ] Set benzene parameters: λ = 0.002-0.01 /day
  - [ ] Position source at gas station

- [ ] **Group 4 (Concession 190): Atrazine - Garden allotment pesticide**
  - [ ] Load well data
  - [ ] Define diffuse/area source with sorption
  - [ ] Set atrazine parameters: Kd = 0.2-0.5 mL/g
  - [ ] Position source at Schrebergärten

- [ ] **Group 5 (Concession 223): PFOA - Industrial point source**
  - [ ] Load well data
  - [ ] Define point source, continuous
  - [ ] Set PFOA parameters: conservative, very mobile
  - [ ] Position source at industrial facility

- [ ] **Group 6 (Concession 227): PCE - Dry cleaning facility leak**
  - [ ] Load well data
  - [ ] Define point source pulse
  - [ ] Set PCE parameters: slight sorption (Kd = 0.05-0.1 mL/g)
  - [ ] Position source at dry cleaner

- [ ] **Group 7 (Concession 213): Ammonium - Leaking sewer line**
  - [ ] Load well data
  - [ ] Define continuous line source with decay (nitrification)
  - [ ] Set ammonium parameters: λ = 0.01-0.05 /day
  - [ ] Position source along sewer infrastructure

- [ ] **Group 8 (Concession 207): Chromium - Metal plating facility**
  - [ ] Load well data
  - [ ] Define point source with strong sorption
  - [ ] Set chromium parameters: Kd = 1-5 mL/g
  - [ ] Position source at electroplating workshop

#### 4.2 Source Location Strategy
For each group, position sources to create diverse well-contaminant interactions:
- Some upgradient of pumping wells (test capture efficiency)
- Some near injection wells (test spreading effects)
- Some between pumping and injection (complex interactions)
- Vary locations across Limmat Valley for diversity

**Time Estimate for Phase 4**: 1-2 days

### Phase 5: Test Case Studies for Groups 1-8 🚧 IN PROGRESS
**Target**: Verify each group's transport scenario works correctly with the demo notebook

**Note**: The case_study_transport_group_0.ipynb notebook is designed to work for all groups by reading their group-specific configuration from case_config_transport.yaml. Each group needs to:
1. Copy the group_0 notebook to their folder
2. Update the group number in Section 3
3. Test that their specific scenario runs successfully

#### 5.1 Testing Checklist by Group

**Conservative Tracer Groups (Test First - No RCT package):**
- [ ] **Group 1: Nitrate** (Concession 219) - Sports field fertilizer, continuous source
  - [ ] Test notebook runs with group_id=1
  - [ ] Verify continuous source implementation
  - [ ] Check plume migration patterns
  - [ ] Verify computational time < 1 hour
  - [ ] Document any issues

- [ ] **Group 2: Chloride** (Concession 201) - Legacy landfill, long-duration source
  - [ ] Test notebook runs with group_id=2
  - [ ] Verify historical source implementation
  - [ ] Check plume extent
  - [ ] Verify computational time < 1 hour
  - [ ] Document any issues

- [ ] **Group 5: PFOA** (Concession 223) - Industrial point source
  - [ ] Test notebook runs with group_id=5
  - [ ] Verify point source setup
  - [ ] Check long-term migration
  - [ ] Verify computational time < 1 hour
  - [ ] Document any issues

**Slight Complexity Groups:**
- [ ] **Group 6: PCE** (Concession 227) - Dry cleaning, slight sorption
  - [ ] Test notebook runs with group_id=6
  - [ ] Verify RCT package with low Kd
  - [ ] Check retardation effects
  - [ ] Verify computational time < 1 hour
  - [ ] Document any issues

**Reactive Transport Groups (Test Last - Need RCT package):**
- [ ] **Group 3: Benzene** (Concession 236) - Gas station, decay only
  - [ ] Test notebook runs with group_id=3
  - [ ] Verify RCT package with decay
  - [ ] Check natural attenuation
  - [ ] Verify computational time < 1 hour
  - [ ] Document any issues

- [ ] **Group 4: Atrazine** (Concession 190) - Pesticide, sorption only
  - [ ] Test notebook runs with group_id=4
  - [ ] Verify RCT package with Kd
  - [ ] Check retardation effects
  - [ ] Verify computational time < 1 hour
  - [ ] Document any issues

- [ ] **Group 7: Ammonium** (Concession 213) - Sewer line, decay
  - [ ] Test notebook runs with group_id=7
  - [ ] Verify RCT package with decay
  - [ ] Check degradation in capture zone
  - [ ] Verify computational time < 1 hour
  - [ ] Document any issues

- [ ] **Group 8: Chromium** (Concession 207) - Metal plating, strong sorption
  - [ ] Test notebook runs with group_id=8
  - [ ] Verify RCT package with high Kd
  - [ ] Check strong retardation
  - [ ] Verify computational time < 1 hour
  - [ ] Document any issues

#### 5.2 Common Quality Checks (All Groups)
For each tested group, verify:
- [ ] Mass balance error < 1%
- [ ] Courant and Peclet numbers acceptable
- [ ] Plume contained in domain (or documented/justified)
- [ ] Results physically reasonable for contaminant type
- [ ] Computational time < 1 hour
- [ ] Well-contaminant interactions clearly visible
- [ ] All visualizations render correctly
- [ ] No errors or warnings in model output

**Time Estimate for Phase 5**: 1-2 days (testing 8 scenarios, ~2-3 hours per scenario)

### Phase 6: Supporting Materials - NOT STARTED
- [ ] Update README.md in student_work/ with transport instructions
- [ ] **Add analytical solution functions to SUPPORT_REPO** (for students choosing optional verification)
  - [ ] 1D solution in uniform flow field (instantaneous and continuous source)
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

**Time Estimate for Phase 6**: 2-3 days

### Phase 7: Documentation and Testing - NOT STARTED
- [ ] Test group_0 notebook runs without errors on clean environment
- [ ] Verify each group's transport_config.yaml is complete
- [ ] Check that all scenarios are appropriately differentiated
- [ ] **Write instructor notes with expected results for all groups**
  - [ ] Summary table: plume extents, breakthrough times, well capture percentages
  - [ ] Parameter sensitivity insights per group
  - [ ] Known challenges and solutions
  - [ ] Grading rubric with examples
- [ ] **Document common pitfalls and troubleshooting**
  - [ ] Create TRANSPORT_TROUBLESHOOTING.md
  - [ ] Common MT3DMS errors and solutions
  - [ ] Grid resolution issues
  - [ ] Mass balance problems
  - [ ] Convergence failures
- [ ] Estimate and verify completion time for students (target: 8-10 hours)

**Time Estimate for Phase 7**: 1-2 days

### Phase 8: Integration and Deployment - NOT STARTED
- [ ] Link 4b notebook from main course structure
- [ ] Update course introduction to mention transport case study
- [ ] Add transport to progress tracking (if applicable)
- [ ] Prepare assignment handout/instructions
- [ ] Schedule: when transport assignment is due relative to flow assignment
- [ ] Create cross-group comparison gallery (optional but nice)

**Time Estimate for Phase 8**: 0.5-1 day

---

## Overall Implementation Timeline

**Total estimated time**: 12-18 days of focused work

| Phase | Description | Days | Status |
|-------|-------------|------|--------|
| 1 | Planning and design | 0.5 | ✅ **COMPLETE** |
| 2 | Teaching notebook (4b) | 1-2 | ✅ **COMPLETE** |
| 3 | Group 0 demo implementation | 2-3 | ✅ **COMPLETE** |
| 4 | Configs for groups 1-8 | 1-2 | ✅ **COMPLETE** (configs exist) |
| 5 | Instructor solutions (groups 1-8) | 3-5 | 🚧 **READY FOR TESTING** |
| 6 | Supporting materials | 2-3 | ⏳ Not started |
| 7 | Documentation and testing | 1-2 | 🚧 **IN PROGRESS** |
| 8 | Integration and deployment | 0.5-1 | ⏳ Not started |

**Current Priority**: Phase 5 & 7 - Test case studies for groups 1-8

**Recommended schedule**:
- **Week 1**: ✅ Phases 1-2 complete, Phase 3 in progress (demo implementation)
- **Week 2**: Phases 4-5 (configs and instructor solutions)
- **Week 3**: Phases 6-8 (supporting materials, testing, deployment)

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
✓ **Verification (optional)**: If completed, explain value and limitations of analytical comparison
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
   - **DECIDED (2025-11-03, updated 2025-11-09)**: **Optional without bonus credit**
   - **All groups** have equal opportunity to complete analytical verification regardless of contaminant properties
   - **Conservative tracers**: Can use direct 1D analytical comparison
   - **Reactive transport**: Can compare simplified scenarios or use analytical solutions with reactions
   - **Rationale**: While verification is professional practice, this is a learning exercise focused on transport workflow. Making it optional without extra credit keeps it as a learning opportunity for those interested in deeper understanding without creating grade disparities.

3. ~~**Time constraints**: How many weeks for transport case study?~~
   - **DECIDED**: 2-3 weeks, approximately **10 hours total** including report writing
   - **Breakdown estimate**:
     - Read/understand teaching notebook (4b): 1-2 hours
     - Setup and adapt demo for their scenario: 2-3 hours
     - Run simulations and troubleshoot: 2-3 hours
     - (Optional) Analytical comparison: 0.5-1 hour (with templates)
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
   - **DECIDED (Updated 2025-11-09)**: Grading split between technical implementation and professional report

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

   **Optional Analytical Verification**:
   - Not graded, but demonstrates advanced understanding for students interested in deeper learning

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
- **(Optional) Analytical comparison (with templates): 0.5-1 hour**
- **Total: ~8-10 hours per group** (target based on 2-3 week timeline)
- **Total with optional verification: ~10-11 hours**

**Note**: The 8-10 hour target is achievable because:
- Wells are reused from flow case (no new implementation)
- Analytical comparison is optional (not required)
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

**1D Advection-Dispersion (Pulse Source)**:
For instantaneous source in uniform flow:
```
C(x,t) = 1 / (n * np.sqrt(4 * np.pi * D * t)) * np.exp(-((x - xc - v * t) ** 2) / (4 * D * t) - lamb * t)
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
