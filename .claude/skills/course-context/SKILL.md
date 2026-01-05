---
name: course-context
description: Course-specific context for ETH Zurich Groundwater course (651-4023-00). Use when creating exercises, assessments, rubrics, lecture materials, or aligning content with learning objectives. Knows the Limmat Valley case study, grading structure, and teaching philosophy.
---

# Groundwater Course Context (ETH Zurich 651-4023-00)

You are assisting with the development and improvement of the Groundwater course at ETH Zurich. This skill provides the course-specific context needed to create aligned materials.

## Course Overview

| Attribute | Value |
|-----------|-------|
| Course Code | 651-4023-00 |
| Credits | 4 ECTS |
| Level | MSc Earth Sciences / Engineering Geology |
| Department | Geothermal Energy and Geofluids Group (GEG), ETH Zurich |
| Instructors | Dr. Xiangzhao Kong, Dr. Beatrice Marti |
| Teaching Assistant | Louise Noel du Payrat |

### Brief Description

The course provides an introduction to quantitative (analytical and numerical) analysis of groundwater flow, solute transport, and unsaturated flow.

### Four Fundamental Aspects

Groundwater is treated as:

1. **Natural System** - Part of hydrologic cycle; distribution, movement, interaction with geologic framework
2. **Resource** - Exploration, development, production; mapping and simulation tools
3. **Environmental System** - Aquifers as dispersive propagation systems for chemical/pollution stresses
4. **Managed System** - Integrated approach to use, conservation, remediation, quality control

Special emphasis on cross-over between hydrogeology and rock mechanics / engineering geology.

---

## Learning Objectives (Bloom's Taxonomy Aligned)

### LO1: Understanding Flow & Transport Principles
> Students will be able to **describe and explain** (Understand) the basic principles of groundwater flow and solute transport processes, **identify** (Apply) relevant boundary conditions for various practical scenarios, and **evaluate** (Evaluate) their significance in groundwater modeling contexts.

### LO2: Problem Formulation
> Students will be able to **construct** (Apply) simple, practical groundwater flow and solute transport problems, **analyze** (Analyze) their underlying assumptions, and **adapt** (Create) them to address real-world challenges.

### LO3: Analytical & Numerical Methods
> Students will be able to **solve** (Apply) fluid flow and solute transport problems using simple analytical and/or numerical methods, **compare** (Analyze) the results for different scenarios, and **justify** (Evaluate) their choice of method.

### LO4: Critical Evaluation
> Students will be able to **critically evaluate** (Evaluate) a groundwater modeling report by **assessing** (Analyze) its methodology, assumptions, and conclusions, and **recommend** (Create) improvements to enhance its scientific rigor.

### Mapping Bloom's Levels

| Level | Verb | Where Applied |
|-------|------|---------------|
| Remember | Recall, list, define | Prerequisite knowledge |
| Understand | Describe, explain | LO1 |
| Apply | Identify, construct, solve | LO1, LO2, LO3 |
| Analyze | Analyze, compare, assess | LO2, LO3, LO4 |
| Evaluate | Evaluate, justify, critically evaluate | LO1, LO3, LO4 |
| Create | Adapt, recommend | LO2, LO4 |

---

## Course Structure (HS26 Revision)

### New Structure: Theory First, Project Second

| Phase | Weeks | Content | Assessment |
|-------|-------|---------|------------|
| **Theory** | 1-8 | Lectures + Exercises | Formative quiz (flow), Comprehensive exam |
| **Project** | 9-14 | Case Study (numerical modeling) | Report + Presentation |

This addresses student feedback about overlap between exam prep and project work.

### Assessment Timeline

```
Week 1-4: Flow Theory
    ↓
Week 5: Formative Quiz (Flow) - Low stakes, feedback-focused
    ↓
Week 5-8: Transport Theory
    ↓
Week 8: Comprehensive Exam (Flow + Transport) - 50% of grade
    ↓
Week 9-14: Numerical Project
    ↓
Week 14: Presentation + Report Submission - 50% of grade
```

### Weekly Topics (Planned)

| Week | Topic | Key Concepts | Assessment |
|------|-------|--------------|------------|
| 1 | Introduction | Water cycle, porosity, REV, aquifer types, water budget | |
| 2 | Flow Fundamentals | Hydraulic head, Darcy's law, flow equation, storativity | |
| 3 | Flow Problems | Boundary conditions, problem formulation, flow nets | |
| 4 | Analytical Solutions (Flow) | Well hydraulics, Theis, Cooper-Jacob, superposition | |
| 5 | Numerical Methods (Flow) | Finite differences, MODFLOW basics, grid design | **Formative Quiz** |
| 6 | Unsaturated Zone | Vadose zone, capillary pressure, Richards equation | |
| 7 | Water Chemistry & Transport | Meteoric water, ADE, advection, dispersion, retardation | |
| 8 | Transport Solutions | Analytical solutions, numerical transport, MT3D/GWT | **Comprehensive Exam** |
| 9-10 | Project: Flow Model | Case study implementation, calibration concepts | |
| 11-12 | Project: Transport Model | Transport scenarios, sensitivity analysis | |
| 13 | Project: Analysis | Uncertainty, documentation, interpretation | |
| 14 | Presentations | Student presentations, peer feedback | **Report + Presentation** |

---

## Assessment Structure

### Grade Components

| Component | Weight | Timing | Format |
|-----------|--------|--------|--------|
| Formative Quiz | 0% (feedback only) | Week 5 | Short online quiz, immediate feedback |
| Comprehensive Exam | 50% | Week 8 | Closed-book, 2 hours, covers all theory |
| Project Report | 25% | Week 14 | Group (2-3 students), written documentation |
| Project Presentation | 25% | Week 14 | 15 min per group |

### Formative Quiz (Flow) - Week 5

**Purpose:** Early feedback on flow concepts before moving to transport

| Aspect | Details |
|--------|---------|
| Stakes | Ungraded (0%) - purely formative |
| Format | ~10-15 questions, multiple choice + short numeric |
| Duration | 20-30 minutes |
| Topics | Darcy's law, flow equation, boundary conditions, well hydraulics |
| Feedback | Immediate, with explanations for each answer |
| Retakes | Unlimited - students can practice until comfortable |

**Sample Question Types:**
- "Which boundary condition is appropriate for...?" (conceptual)
- "Calculate the drawdown at distance r using Theis" (calculation)
- "What assumption is violated when...?" (critical thinking)

### Comprehensive Exam - Week 8

**Purpose:** Summative assessment of all theoretical content

| Aspect | Details |
|--------|---------|
| Weight | 50% of final grade |
| Format | Closed-book, 2 hours |
| Allowed | One A4 page handwritten notes (both sides), calculator |
| Content | Flow (60%) + Transport (40%) |
| Questions | Short-answer essay + hand calculations |

**Exam Structure:**
- Part A: Flow (Darcy, flow equation, BCs, well hydraulics, numerical concepts)
- Part B: Transport (ADE, advection/dispersion, analytical solutions, numerical concepts)
- Questions similar to homework exercises

### Project Report Rubric

| Criterion | Weight | Excellent (6) | Good (5) | Satisfactory (4) | Needs Work (3-) |
|-----------|--------|---------------|----------|------------------|-----------------|
| **Problem Definition** | 10% | Clear objectives, well-justified scope | Clear objectives, adequate scope | Objectives stated but vague | Unclear or missing objectives |
| **Conceptual Model** | 15% | Comprehensive, well-reasoned assumptions explicitly stated | Good conceptual basis, most assumptions stated | Basic conceptual model, some assumptions missing | Inadequate conceptualization |
| **Model Implementation** | 20% | Correct setup, appropriate discretization, all packages justified | Mostly correct, minor issues | Functional but with notable issues | Major implementation errors |
| **Calibration/Validation** | 15% | Rigorous process, appropriate metrics, uncertainty discussed | Good calibration, metrics reported | Basic calibration attempted | Poor or missing calibration |
| **Results & Interpretation** | 20% | Insightful analysis, physical reasoning, limitations acknowledged | Good analysis, reasonable interpretation | Basic interpretation | Superficial or incorrect interpretation |
| **Documentation** | 10% | Professional quality, reproducible, clear figures | Good documentation, mostly clear | Adequate documentation | Poor or missing documentation |
| **Writing Quality** | 10% | Clear, concise, well-structured, correct terminology | Good writing, minor issues | Understandable but needs improvement | Difficult to follow |

### Project Presentation Rubric

| Criterion | Weight | Excellent (6) | Good (5) | Satisfactory (4) | Needs Work (3-) |
|-----------|--------|---------------|----------|------------------|-----------------|
| **Content** | 40% | Key points clear, appropriate depth, technically accurate | Good coverage, mostly accurate | Basic content, some gaps | Missing key content or errors |
| **Visualization** | 20% | Clear, informative figures, appropriate complexity | Good visuals, mostly clear | Adequate visuals | Poor or confusing visuals |
| **Delivery** | 20% | Confident, clear, good pace, handles questions well | Good delivery, minor issues | Understandable, some awkwardness | Difficult to follow |
| **Time Management** | 10% | Within time, well-paced | Slightly over/under, adequate pacing | Notable time issues | Significantly over/under |
| **Team Coordination** | 10% | Seamless transitions, balanced participation | Good coordination | Some coordination issues | Poor coordination |

---

## Case Study: Limmat Valley Aquifer

### Overview

The course uses a real-world case study based on the Limmat Valley aquifer in Zurich, Switzerland.

### Why Limmat Valley?

- Real-world complexity at manageable scale
- High-quality publicly available data
- Relevant local context for ETH students
- Active groundwater management (drinking water, thermal use)
- River-aquifer interaction
- Urban influences

### Model Specifications (MODFLOW 6)

| Aspect | Specification |
|--------|---------------|
| Software | MODFLOW 6 via FloPy |
| Grid | Flexible (DISV) with local refinement |
| Layers | 1 (simplified) to 3 (detailed) |
| Extent | ~15 km along Limmat valley |
| Resolution | 50-200 m (coarse), 10-25 m (refined areas) |
| Time | Steady-state and transient options |
| Starting Point | Pre-calibrated model provided to students |

### Key Features to Model

| Component | Package | Notes |
|-----------|---------|-------|
| Aquifer properties | NPF | Heterogeneous K field |
| River-aquifer exchange | RIV | Limmat, Sihl rivers |
| Recharge | RCH | Spatially variable |
| Pumping wells | WEL | Major abstractions |
| Lateral boundaries | GHB/CHD | Valley margins |
| Transport | GWT | Conservative tracer scenarios |

### Available Data

| Data Type | Source | Coverage |
|-----------|--------|----------|
| Geology | Cantonal geological maps | Full extent |
| Topography (DEM) | swisstopo | 2m resolution |
| River stages | BAFU gauging stations | Hourly, multi-year |
| Groundwater levels | Cantonal monitoring | ~50 wells, multi-year |
| Pumping rates | Water utilities | Monthly/annual |
| Recharge estimates | Derived from precipitation | Gridded |

### Student Tasks (Typical)

1. **Understand** the hydrogeological setting
2. **Explore** the pre-calibrated numerical model
3. **Run** steady-state and transient simulations
4. **Compare** results to observations
5. **Analyze** sensitivity to key parameters
6. **Interpret** flow patterns and water budget
7. **Apply** scenarios (changed pumping, climate)
8. **Document** methodology and findings

---

## Teaching Philosophy

### Core Principles

1. **Conceptual Understanding First**
   - Equations follow from physical understanding
   - Always ask "why?" before "how?"
   - Fewer equations, deeper understanding

2. **Learning by Doing**
   - Numerical project applies lecture concepts
   - Exercises mirror exam problems
   - Self-assessment with immediate feedback

3. **Real-World Relevance**
   - Case study uses actual Swiss data
   - Connect to professional practice
   - Discuss model limitations honestly

4. **Scaffolded Complexity**
   - Start simple, add complexity gradually
   - Pre-calibrated model as starting point
   - Students modify and analyze, not build from scratch

5. **Transparent Expectations**
   - Clear learning objectives per notebook
   - Published rubrics before assignments
   - Example of "good" work provided

6. **Early Feedback**
   - Formative quiz after flow section
   - Students know where they stand before high-stakes exam
   - Opportunity to adjust study approach

### What Students Should NOT Need to Do

- Write FloPy code from scratch
- Debug complex Python errors
- Understand every line of provided code
- Spend >60 hours on project (target for 4 ECTS)

### What Students SHOULD Be Able to Do

- Modify model parameters and understand effects
- Interpret model outputs physically
- Recognize when assumptions are violated
- Write clear technical documentation
- Present findings to non-specialist audience

---

## Key References

### Primary Textbook
- Domenico, P.A. & Schwartz, F.W. (1990). *Physical and Chemical Hydrogeology*. Wiley.

### Supplementary
- Freeze, R.A. & Cherry, J.A. (1979). *Groundwater*. Prentice Hall. (Free via Groundwater Project)
- Anderson, M.P., Woessner, W.W. & Hunt, R.J. (2015). *Applied Groundwater Modeling*. Academic Press.
- Bear, J. (1979). *Hydraulics of Groundwater*. McGraw-Hill.

### Practical Guides
- Chiang, W.-S. & Kinzelbach, W. (2001). *3-D Groundwater Modeling with PMWIN*. Springer.
- Kruseman, G.P. & de Ridder, N.A. (1991). *Analysis and Evaluation of Pumping Test Data*. ILRI.

---

## Exercise Alignment Matrix

When creating exercises, ensure coverage across learning objectives:

| Topic | LO1 (Understand) | LO2 (Apply/Create) | LO3 (Solve/Analyze) | LO4 (Evaluate) |
|-------|------------------|-------------------|---------------------|----------------|
| Darcy's law | Explain when valid | Formulate problem | Calculate K, q | Assess assumptions |
| Flow equation | Describe terms | Set up BCs | Solve analytically | Compare methods |
| Well hydraulics | Explain Theis assumptions | Adapt to unconfined | Apply Cooper-Jacob | Evaluate test quality |
| Transport | Describe advection/dispersion | Formulate ADE | Solve 1D problems | Assess Peclet regime |
| Numerical modeling | Explain discretization | Build simple model | Run scenarios | Evaluate model quality |

---

## Content Development Guidelines

### For Lecture Slides (PDFs exist)

- Each topic has presentation slides ready
- Exercises should align with slide content
- Self-assessments should test key concepts from slides

### For Exercises

1. **Solvable on paper** - No computer required for core calculation
2. **Exam-aligned** - Same format as exam questions
3. **Progressive difficulty** - Basic → Applied → Critical thinking
4. **Clear solutions** - Step-by-step, with physical interpretation

### For Formative Quiz

1. **Immediate feedback** - Students see correct answer + explanation right away
2. **Unlimited retakes** - Low pressure, encourages practice
3. **Coverage** - All major flow topics from weeks 1-4
4. **Diagnostic** - Identifies specific misconceptions

### For Case Study Notebooks

1. **Learning objectives** at top of each notebook
2. **Connection to lectures** - Reference relevant slide content
3. **Expected outputs** - Students know if results are reasonable
4. **Completion markers** - Track progress through material

---

## Common Student Questions (FAQ)

| Question | Response |
|----------|----------|
| "Do I need to know Python?" | Basic familiarity helps, but you won't write code from scratch. Focus on understanding what the code does. |
| "What's on the exam?" | Short-answer questions and hand calculations covering flow and transport. Exercises are representative. One A4 notes page allowed. |
| "Does the quiz count?" | No, the formative quiz is ungraded. It's for your benefit to check understanding before the exam. |
| "How is the project graded?" | Report (25%) + presentation (25%). Rubric published at project start. Focus on understanding over complexity. |
| "Can I use AI tools?" | For learning, yes. For assessed work, you must understand and explain everything you submit. |
| "How much time should the project take?" | Target ~40-50 hours over the project phase. If it's taking much longer, ask for help. |
