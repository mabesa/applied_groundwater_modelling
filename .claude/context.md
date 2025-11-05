# Project Context for AI Assistants

## About This Project
This is a Master-level groundwater modeling course at ETH Zurich focusing on MODFLOW and transport modeling using FloPy.

## Key Planning Documents

### Transport Case Study
**Primary Reference**: [transport_planning.md](../transport_planning.md)

**ALWAYS read transport_planning.md when working on transport-related tasks.**

This document contains:
- All design decisions (wells, analytical comparison, deliverables)
- Complete implementation roadmap
- Grading rubrics
- Timeline estimates
- Report structure (3-4 pages)
- All 9 group scenarios

### Quick Reference for Transport Work

**Key Decisions**:
- Wells ARE included (from flow case study)
- Analytical comparison is MANDATORY (tiered: Tier 1 full, Tier 2 simplified)
- 3 deliverables: notebook + 3-4 page PDF report + config
- 10-hour student time budget
- MT3DMS via FloPy recommended, free alternatives permitted
- 50/50 grading split (technical implementation / report)

**When starting transport work**: Read transport_planning.md first, then proceed with implementation following the documented structure.

## Repository Structure

Key directories:
- `CASE_STUDY/` - Case study notebooks and materials
- `CASE_STUDY/student_work/` - Student working area
  - `group_0/` - Demo/template (tracked in git)
  - `group_1/` through `group_8/` - Student work (gitignored)
- `SUPPORT_REPO/` - Helper functions and utilities

## Development Guidelines

1. **Check for planning documents** before starting new features
2. **Update planning documents** when making design changes
3. **Follow established patterns** from existing notebooks
4. **Maintain accessibility** (see README.md section 4)
5. **Test thoroughly** with group_0 demo before deploying to students

## Important Notes

- Students use JupyterHub environment (ETH)
- All data downloaded from configured sources (not in git)
- FloPy and MODFLOW are primary tools
- Course includes both flow and transport modeling components
