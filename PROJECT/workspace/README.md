# Student Workspace

You are here: `PROJECT/workspace/`. The parent course overview is in the root [README.md](../../README.md).

This is where you work on your flow and transport case study.

## Getting Started

1. Copy the `template/` folder to create your own workspace.
2. Rename the copy to your group name, for example `group_alice_bob/`.
3. Work only in your group folder.
4. Keep the original `template/` folder unchanged so you can compare against it if needed.

## Template Contents

- `case_config.yaml` - Model configuration parameters
- `case_config_transport.yaml` - Transport model configuration
- `case_study_flow_group_0.ipynb` - Flow model notebook template
- `case_study_transport_group_0.ipynb` - Transport model notebook template

## What You Submit

Submit the complete project material through the channel announced by the teaching team, for example Moodle:

- your completed flow notebook;
- your completed transport notebook;
- your flow and transport configuration files;
- your project report covering both flow and transport;
- your project presentation covering both flow and transport.

Your TA or instructor may run your submitted notebooks to verify that the report results are reproducible.

## Expected Workflow

Work through the required notebook sections first. Optional sections are enrichment and should only be attempted after the required work is complete.

Use the time estimates at the top of each notebook to plan your work. If a task takes much longer than the estimate, ask for help rather than spending many hours debugging alone.

## When To Ask For Help

Use the shared question channel announced by the teaching team when you are blocked. Include the notebook name, section, relevant error message or screenshot, and what you already tried.

Ask for help when:

- JupyterHub, kernels, or file access are unstable;
- code errors appear that you do not understand after reading the surrounding notebook text;
- a required model run fails or takes much longer than expected;
- model edits lead to numerical instability or non-convergence;
- you cannot tell whether a result is a hydrogeological signal, numerical noise, or a code/setup issue;
- you are unsure whether a notebook section is required or optional;
- you cannot connect a notebook output to the report or presentation deliverable.

If numerical instability appears after you edited model parameters or scenario settings, step back to the original `template/` version or your last known working version. Then reintroduce your changes one at a time.

## Definition Of Done

Before submission, check that you can answer each item below. The goal is not only to produce figures.

- what modelling question your scenario addresses;
- which parameters or boundary conditions you changed;
- how the model response appears in heads, drawdown, budgets, and transport outputs;
- whether the result looks like a physical signal, numerical noise, or model instability;
- what the result implies for the practical groundwater problem.

## Collaboration

Work together in your assigned group. Keep track of who changed which files and coordinate before editing the same notebook.

If your group uses Git for collaboration, commit and pull frequently and avoid working on the same notebook cells at the same time. Notebook merge conflicts can be difficult to resolve.

For report writing, use the collaboration workflow recommended by the teaching team.

## Submission

Before submitting, restart the kernel and run each notebook from top to bottom. The submitted notebooks should run without manual fixes in the course environment.
