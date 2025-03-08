[![Package Dependencies](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/check-dependencies.yml/badge.svg)](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/check-dependencies.yml) [![Flopy Installation](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/test_flopy_installation.yml/badge.svg)](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/test_flopy_installation.yml)

# Applied Groundwater Modeling - Exercises and Case Study

![Groundwater Model Visualization](static/Groundwater_course.jpg)

## Overview
Project-based course materials for Master-level groundwater modeling (4 ECTS) at ETH Zurich. Focuses on practical modeling skills using MODFLOW and FloPy through a real-world case study of the Limmat valley aquifer.

## Learning Objectives
- Apply groundwater flow and transport principles to practical modeling scenarios
- Construct and adapt models to address real-world hydrogeological challenges
- Implement and analyze numerical solutions using MODFLOW and FloPy
- Critically evaluate modeling results and their implications

## Prerequisites
- Basic understanding of hydrogeology (Darcy's Law, hydraulic conductivity, aquifer properties)
- Groundwater flow concepts and boundary conditions
- Basic Python programming skills

Self-assessment notebooks are available in the `00_prerequisites` directory.

## Repository Structure
(to be refined)
```
├── 00_prerequisites/    # Self-assessment materials
├── 01_introduction/     # Introduction to course & case study
├── 02_groundwater_flow/ # Groundwater flow & analytical solutions
├── 03_modflow/          # MODFLOW fundamentals and FloPy interface
├── 04_transport/        # Transport in groundwater & analytical solutions
├── 05_MT3D/             # MT3D fundamentals and FloPy interface
├── 06_case_studies/     # Templates for student projects
├── ...                  # Additional course materials
├── requirements.txt     # Python dependencies
└── README.md            # Course overview and instructions
```

Currently not covered: Sensitivity & uncertainty analysis, model calibration, model validation


## Getting Started
### JupyterHub (ETH Students)
ETH students can access these materials through the course JupyterHub environment linked in Moodle.

### Local Installation
To run these materials locally, follow these steps:
1. Clone this repository:
   `git clone https://github.com/your-repo/groundwater-modeling.git`
2. Set up your Python environment (e.g., using conda). We recommend Python 3.12 as scientific packages we use here have not yet been updated to Python 3.13 at time of writing.
    - Create a new environment:
     `conda create -n gw_course_312 python=3.12`
    - Activate the environment:
     `conda activate gw_course_312`
3. Install dependencies via conda-forge:
   `conda install -c conda-forge numpy matplotlib scipy pandas jupyterlab ipywidgets`
   `conda install -c conda-forge porespy "scikit-image<0.25.0"`
   `conda install -c conda-forge flopy`
4. Get modflow executables:
   `get-modflow :flopy`
5. Launch Jupyter:
   `jupyter lab` or `jupyter notebook`

## The Limmat Valley Aquifer Case Study
This course uses a numerical groundwater flow and transport model of the Limmat valley aquifer as its central case study. Students will:
- Understand the hydrogeological setting
- Develop and refine the numerical model
- Apply the model to explore various scenarios including climate change impacts and water management challenges

## Course Timeline
(To be refined)
- **Weeks 1-7**: Core concepts, model setup, and calibration
- **Weeks 8-13**: Student-led case studies investigating specific problems using the Limmat valley model

<details>
<summary>Detailed sylabus (under development)</summary>
The course stretches over 13 weeks with 4 lectures per week. For each lecture we expect 25-30 hours of work for the student. You will have a mid-term exam in week 7 and a final exam in week 13. The course is structured as follows:

- Lesson 1: Introduction to the course, group formation, and project assignment
- Lesson 2: Introduction to Groundwater Flow Modeling
- Lesson 2: Numerical Methods for Groundwater Flow Modeling
- Lesson 3: Introduction to Groundwater Transport Modeling
- Lesson 4: Numerical Methods for Groundwater Transport Modeling
- Lesson 5: Calibration and Validation of Groundwater Models
- Mid-term exam
- Lesson 6: Uncertainty Analysis in Groundwater Modeling
- Lesson 7: Groundwater Modeling in Practice
- Project work
- Project work
- Project work
- Project presentation & discussion
- Project work
- Final exam
</details>

## Acknowledgments
Funded by the ETH Zurich Department of Earth and Planetary Sciences and the Rectors Innovendum Fund ([project link](https://ww2.lehrbetrieb.ethz.ch/id-workflows/faces/instances/Innovedum/ProzessInnovedum$1/195511738774A87D/innovedumPublic.Details/Details.xhtml)).