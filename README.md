[![Package Dependencies](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/check-dependencies.yml/badge.svg)](https://github.com/mabesa/applied_groundwater_modelling/actions/workflows/check-dependencies.yml) 

# Applied Groundwater Modeling - Exercises and Case Study

![Groundwater Model Visualization](static/Groundwater_course.jpg)

## Overview
Project-based course materials for Master-level groundwater modeling (4 ECTS) at ETH Zurich. Focuses on practical modeling skills using MODFLOW and FloPy through a real-world case study of the Limmat valley aquifer.

## Learning Objectives
- Deepen your understanding of basic hydrogeological concepts and principles
- Apply numerical methods to solve groundwater flow and transport problems
- Apply groundwater flow and transport principles to practical modeling scenarios
- Construct and adapt models to address real-world hydrogeological challenges
- Implement and analyze numerical solutions using MODFLOW, MT3D and FloPy
- Critically evaluate modeling results and their implications

What is not covered but highly recommended if you want to make your career in modeling:
- Numerical discretization schemes and optimization 

## Prerequisites
- Basic understanding of hydrogeology (Darcy's Law, hydraulic conductivity, aquifer properties)
- Groundwater flow concepts and boundary conditions
- Basic Python programming skills

## Repository Structure
(to be refined)
```
01_introduction : Lesson 1 - Introduction to the course
 |_ assignment : (optionsl) assignment for lesson 1
 |_ content : Content for lesson 1
     |_ 0_introduction.ipynb : Introduction to the course
     |_ 1_case_study.ipynb : Introduction to the Limmat valley aquifer
     |_ 2_modflow_funddamentals.ipynb : Introduction to MODFLOW

exercises
 |_ exercise01 : The long-term groundwater balance
 |_ exercise02 : Porosity and the representative elementary volume
 |_ exercise03 : Darcy's Law and hydraulic conductivity
 |_ exercises_complements : Methods used in the exercises

case_studies : Data and assingment templates for the case studies
 |_ Zurich : The Limmat valley aquifer
     |_ data : Data for the Limmat valley aquifer
         |_ climate : Climate data for the Limmat valley aquifer
     |_ model : Model of the Limmat valley aquifer
 |_ other : Case study to be defined
```

Currently not covered: Sensitivity & uncertainty analysis, model calibration, model validation


## How to Use this Repository as a Student
### JupyterHub (ETH Students)
ETH students can access these materials through the course JupyterHub environment linked in Moodle.

### Local Installation
We recommend Visual Studio Code as an IDE (available for free [here](https://code.visualstudio.com/)) but any other Python IDE will work. We further recomment using the Anaconda distribution of Python (available for free [here](https://www.anaconda.com/products/distribution)) to manage your Python environment.  

To run these materials locally, follow these steps:
1. In your terminal, navigate to the directory where you want to clone the repository. You can do this by using the `cd` command. For example, if you want to clone it into a folder called `gw_modeling_course`, you would run:
   ```bash
   cd path/to/your/folder
   ```
   Replace `path/to/your/folder` with the actual path to your desired folder.
2. Clone this repository:  
   `git clone https://github.com/mabesa/applied-groundwater-modeling.git`
   This will create a new folder called `gw_modeling_course` in your current directory.
3. Navigate into the cloned repository:
   ```bash
   cd gw_modeling_course
   ```
4. Set up your Python environment, e.g. using conda.
    - Update conda (may take a long while):  
      `conda update -n base -c conda-forge conda`
    - Create a new environment with Python 3.12 and the required packages:  
      `conda env create -f environment_students.yml`
    - Activate the environment:  
      `conda activate gw_course_students`
5. Get modflow executables:  
   `get-modflow :flopy`  
6. You might need to install support for visualizing latex in jupyter notebooks. In Visual Studio Code, you can do this by installing the `Markdown+Math` and the `Markdown All in One` extensions or the `LaTeX Workshop` extension.

### Repository structure
Main branches: 
- `main`: Contains the latest stable version of the course materials
- `course_2025`: Contains the latest version of the course materials for the 2025 course which is displayed on the course JupyterHub

## How to Contribute
We welcome contributions to improve the course materials! 

### Setting up Your Environment
Install the project dependencies using the following command:
```bash
conda env create -f environment_development.yml
```
This will create a new conda environment with the necessary packages. Activate the environment using:
```bash
conda activate gw_course_development
```
If, during development, you need to install additional packages, please add them to the `environment_development.yml` files and run the following command to update the environment:
```bash
conda env update --from-history -f environment_development.yml
```
Please also keep the `environmnet_students.yml` file up to date. 

### Git Workflow to Contribute
Here's how you can contribute if you are not yet a collaborator in this repository:  

- Fork the repository: Create your own fork of this repository (skip this step if you are a collaborator in this repository).
- Create a feature branch: Base your work on the develop branch.  
   `git checkout year_feature_name`  
   `git checkout -b your-feature-name`  
- Make your changes: Implement your contribution, focusing on one specific improvement or addition.
- Test your changes: Ensure your notebooks run without errors in the JupyterHub environment.
- Document your work: Add clear comments and documentation to any code or notebooks.
- Submit a Pull Request: Create a pull request to the develop branch with a clear description of what your changes accomplish. We will review your contribution and provide feedback.

### Stripping Notebooks
To ensure that the notebooks are clean and free of unnecessary output, we use the `nbstripout` tool. This tool automatically removes all output cells from Jupyter notebooks when committing changes. We use it as a pre-commit hook to ensure that all notebooks are stripped before they are committed to the repository. To set up `nbstripout`, follow these steps:
1. Activate the pre-commit hook (installed with the `environment_development.yml` file):
   ```bash
   pre-commit install
   ```
2. Install `nbstripout` in your conda environment: 
   ```bash
   conda install nbstripout
   ```
3. Enable `nbstripout` for your repository:
   ```bash
   nbstripout --install
   ```
4. Verify that `nbstripout` is working by checking the `.git/hooks/pre-commit` file. It should contain a line similar to:
   ```bash
   #!/bin/sh
   nbstripout --strip
   ```
5. Now, whenever you commit changes to the repository, `nbstripout` will automatically strip the output from all Jupyter notebooks.
6. If you want to disable `nbstripout` for a specific notebook, you can use the following command:
   ```bash
   nbstripout --skip-notebook your_notebook.ipynb
   ```


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

- Lesson 1: Introduction to the course, group formation
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