# Instructor Guide

This guide is for instructors, teaching assistants, and external adopters. The main [README.md](../README.md) is the student entry point.

## Course Identity

Canonical tagline:

> From Darcy's Law to Model-Based Decisions.

Supporting gloss:

> The course teaches students to reason like applied groundwater modellers, not just solve equations.

The course is designed as a 50-50 integration of groundwater theory and applied modelling workflow. The modelling project reinforces the theory rather than replacing it.

This is not a MODFLOW manual. The notebooks use MODFLOW and FloPy, but the teaching goal is the applied modelling process: defining a modelling question, making assumptions explicit, running scenarios, interpreting budgets and transport behaviour, and communicating limitations.

## Target Audience

The material is aimed at Master's students with basic hydrogeology background. Students typically enter with basic Darcy-law knowledge, but limited experience with full numerical modelling workflows, calibration, transport modelling, uncertainty, and professional communication.

## Learning Outcomes

By the end of the project, students should be able to:

- formulate a groundwater modelling task from a practical question;
- run and interpret flow and transport scenarios;
- interpret head maps, drawdown maps, water budgets, and transport outputs;
- estimate and communicate travel-time or arrival-time implications for a solute scenario;
- distinguish hydrogeological signal from numerical artifacts or model instability;
- communicate modelling choices, limitations, and uncertainty in a report and presentation.

Deeper calibration, advanced debugging, and open-ended scenario development are useful extensions, but should be treated as optional unless additional supervised time is available.

## Theory-To-Project Links

This table is the accessible text version of the planned design figure.

| Theory topic | Project connection | Expected student use |
| --- | --- | --- |
| Darcy law | Hydraulic gradients, flow direction, pumping response | Explain why heads and drawdown change under a scenario |
| Boundary conditions | Model setup and scenario design | Identify which boundaries control model behaviour |
| Water balance | Budget interpretation | Check whether model responses are physically plausible |
| Analytical solutions and pumping tests | Plausibility checks | Compare numerical responses with simpler conceptual expectations |
| Transport equation | Solute travel time and plume behaviour | Interpret arrival time and concentration patterns |
| Sensitivity and uncertainty | Communication of limitations | Explain which conclusions are robust and which depend on assumptions |

## Reuse Layers

The material is reusable as a place-based teaching resource for the Limmat Valley aquifer. It is not packaged as a turnkey template for any aquifer.

| Layer | Scope | Status | Notes |
| --- | --- | --- | --- |
| Layer 1 | Limmat flow scenario | Smallest teachable subset | Use this when an external course needs a compact modelling workflow without the full transport sequence. Do not describe it as a standalone reusable unit until it has been tested independently. |
| Layer 2 | Full Limmat flow + transport course | ETH-style full implementation | Includes flow, transport, report, and presentation. Requires structured student support. |
| Layer 3a | Shipped optional extensions | Available as enrichment | Examples include deeper calibration, sensitivity/uncertainty, and advanced scenario exploration where present in the notebooks. |
| Layer 3b | Adaptation to another aquifer | Possible but not included | Requires replacing the data pipeline, conceptual model, boundary conditions, and validation targets. It is not a tested out-of-the-box workflow. |

## Project Scope

The case study includes both flow and transport because transport is a required part of the course. To keep workload bounded:

- require students to understand the basic calibration concept, but make deeper calibration optional;
- provide a calibrated flow model as a stable starting point or fallback;
- keep required transport tasks focused on process understanding and one controlled solute-transport scenario;
- mark extension tasks clearly as optional;
- avoid assigning optional tasks unless supervised project time is expanded.

Recommended runtime constraint: no individual model run should take more than about 10 minutes.

## Support Model

Do not leave students alone with the notebooks. The project can include self-study, but it is designed as supported independent work, not as a fully unsupervised self-study module. Structured support keeps student effort focused on groundwater modelling judgement rather than avoidable setup, code, or numerical-stability blockers.

Recommended support:

- frame each modelling-heavy notebook sequence before students work independently: identify the take-home modelling idea, required versus optional sections, cells students are expected to modify, and outputs that feed the project report;
- offer supervised project clinics during active project work. As a baseline, plan two clinics in the first half of the project block and two in the second half. If project work is split across the semester, offer two clinics during each active project-work period;
- hold clinics in person, online, or hybrid as staffing allows. All three are valid support formats; choose based on staffing, student location, and course logistics;
- provide a shared question channel, such as a Moodle forum or equivalent course platform;
- publish a monitoring schedule or monitored hours for the question channel, so students know when replies can be expected;
- aim for instructor or TA response within 24 hours during active project periods and monitored times;
- encourage peer support for concepts, setup issues, and debugging symptoms, while keeping group-specific interpretations, report text, figures, and conclusions as each group's own work.

Minimum viable support:

- short in-class framing before modelling-heavy notebook sequences;
- supervised project clinics during active project work;
- a monitored shared question channel;
- clear required/optional labels and explicit deliverable expectations;
- instructor and, where available, TA preparation by running required notebooks in the student environment before assigning them.

The material should not be advertised as a fully unsupported self-study resource. A defensible publication claim is that the notebooks support independent group project work when paired with a lightweight support scaffold: pre-work framing, supervised clinics that may be in person, online, or hybrid, a monitored question channel, and timely instructor/TA responses during monitored periods.

## Student Deliverables

The canonical student deliverables are listed in [PROJECT/workspace/README.md](../PROJECT/workspace/README.md). Keep the deliverables there to avoid drift between student-facing and instructor-facing documentation.

Instructors or TAs should run submitted notebooks to verify that report content is reproducible from the submitted work.

## Graded Versus Practice Material

Exercises are intended for practice and immediate self-correction. Exercise solutions may be public because the graded work is the group-specific project interpretation, report, and presentation.

Project examples and template outputs may also be public. If an instructor wants to grade a local variant using a hidden solution, they should keep that local solution outside the public repository.

## Assessment

The project is assessed through notebooks, report, and presentation. The assessment should reward both correct modelling work and professional communication.

Report and presentation rubrics should emphasize:

- clear problem statement and scenario relevance;
- correct methods and documented assumptions;
- readable figures and tables with units;
- interpretation of budgets, drawdown, transport behaviour, and uncertainty;
- concise conclusions and recommendations.

## Adoption Checklist

Before running the material in another course:

- read the [README.md](../README.md) and verify the local setup with `0_diagnostics.ipynb`;
- check [DATA_AVAILABILITY.md](DATA_AVAILABILITY.md) and confirm that the public data terms fit your intended use;
- review [LICENSE](../LICENSE) and retain required attribution for code, teaching material, figures, and public data providers;
- decide whether to use Layer 1, Layer 2, or optional extensions;
- allocate supervised project clinic time;
- decide which optional notebook sections are in scope;
- run the required notebooks in the intended teaching environment before assigning them;
- adapt grading weights and reporting format to your local course.

## Evidence For Teaching Development

For education research or a teaching-resource publication, avoid relying only on student satisfaction. Stronger evidence can include:

- aggregate grades and rubric distributions;
- quality analysis of final reports and presentations;
- comparison with previous course years where appropriate;
- instructor observations during project clinics;
- short pre/post concept questions.

Any student data intended for publication must be planned before collection. Complete ETH ethics, consent, and data-protection checks before collecting concept-question results, grades, student artifacts, or other student evidence for publication.

Keep student feedback, consent records, grades, and identifiable student artifacts outside the public repository. Store them only in approved private locations and ensure those locations are not tracked by git.

Suggested pre/post concept-question dimensions:

- groundwater theory, including Darcy-law recall;
- modelling judgement;
- numerical-method intuition;
- project workflow confidence.

## Limitations

- The case study is place-based: it uses the Limmat Valley aquifer in Zurich.
- The workflow is not packaged for automatic transfer to another aquifer.
- The project requires active instructor or TA support.
- Workload is sensitive to how many optional sections are assigned.
- The aquifer geometry is simplified for runtime and teaching constraints.

## Licensing

See [LICENSE](../LICENSE) for the repository license structure and [DATA_AVAILABILITY.md](DATA_AVAILABILITY.md) for public data provenance and provider terms.
