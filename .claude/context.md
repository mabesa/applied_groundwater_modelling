# Project Context for AI Assistants

## About This Project

This is a Master-level groundwater modeling course (4 ECTS) at ETH Zurich focusing on MODFLOW and transport modeling using FloPy. The course uses a real-world case study of the Limmat Valley aquifer in Switzerland.

## Current Status (course_2026 branch)

The course implementation is complete with 10 case study notebooks covering the full modeling workflow:
1. Introduction
2. Perceptual Model
3. MODFLOW Fundamentals
4. Model Implementation (flow)
4b. Transport Model Implementation
5. Calibration
6. Validation
7. Sensitivity & Uncertainty
8. Model Application
9. Documentation
10. Communication

## Repository Structure

Key directories:
- `CASE_STUDY/` - Case study notebooks (1-10)
- `CASE_STUDY/student_work/` - Student working area
  - `group_0/` - Demo/template (tracked in git)
  - `group_1/` through `group_8/` - Student work (gitignored)
- `EXERCISES/` - 6 exercises + theory reminder
- `SUPPORT_REPO/src/` - Helper functions and utilities
- `SUPPORT_REPO/static/` - Static files (images, figures)

## Development Setup

See **[DEVELOPMENT.md](../DEVELOPMENT.md)** for complete instructions including:
- Environment setup with uv
- AI-assisted development (Serena, Context7)
- Contributing guidelines
- Code style conventions

Quick start:
```bash
uv sync
source .venv/bin/activate
get-modflow :flopy
```

## Development Guidelines

1. **Follow established patterns** from existing notebooks
2. **Maintain accessibility** (see README.md section 4)
3. **Test thoroughly** with group_0 demo before deploying to students
4. **Notebook outputs** are stripped automatically via pre-commit hook

## Important Notes

- Students use JupyterHub environment (ETH)
- All data downloaded from configured sources (not in git)
- FloPy is a primary tool
- Course includes both flow and transport modeling components
- Environment management uses uv (not conda) starting course_2026
