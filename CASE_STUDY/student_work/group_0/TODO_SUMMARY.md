# TODO Analysis Summary - Quick Reference

**Notebook**: `case_study_transport_group_0.ipynb`
**Total TODOs**: 33
**Analysis Date**: 2025-11-13

---

## Quick Decision Matrix

### ✅ KEEP (45 TODOs) - No Action Needed
- Cell #0: Names and date (2 TODOs)
- Cell #85-86: Breakthrough curve template (20 TODOs)
- Cell #107: Discussion prompts (6 TODOs)
- Cell #108: Interpretation prompts (5 TODOs)
- Cell #109: Conclusions (1 TODO)
- Cell #110-111: Recommendations (3 TODOs)
- Cell #113: References (1 TODO)

### ❌ REMOVE (12 TODOs) - Already Implemented or Instructor Notes

**Critical - Instructor Planning Notes Leaked to Students:**
- Cell #84: 5 instructor planning TODOs (lines 95600-95604) ⚠️ **FIX IMMEDIATELY**

**Already Implemented - Misleading:**
- Cell #12: "Load well data" (line 465) - 4373 chars of code already there
- Cell #64: "Check DSP package" (line 5410) - DSP already created
- Cell #70: "Check loading of source location" (line 5529) - already loaded
- Cell #72: "Create map showing..." (line 5584) - map already created
- Cell #89: "Extract mass balance" (line 95852) - 4984 chars of complex code already there

**Minor Instructor Notes:**
- Cell #88: "Keep this simple" (line 95778)
- Cell #103: "Tasks: Affected area..." (line 96585)

### 🔄 UPDATE (4 TODOs) - Needs Clarification

1. **Cell #45 & #46**: Well pumping rate
   - Current: "TODO: Choose a total pumping rate..."
   - Issue: Rate already set to 20000 m³/d
   - Fix: Change to informational NOTE

2. **Cell #66**: RCT package
   - Current: "TODO: Check if RCT package needed" then says "No RCT needed"
   - Issue: Contradictory
   - Fix: Clarify it's group-dependent, Group 0 doesn't need it

3. **Cell #29**: Property fields
   - Current: "TODO: Check the property fields..."
   - Issue: Empty cell, ambiguous intent
   - Fix: Change to verification note (passive check)

### ℹ️ CLARIFY (5 TODOs) - Add "OPTIONAL" Context

These are empty stub cells for advanced exercises:
- Cell #94: Define transect line
- Cell #96: Analytical solution
- Cell #98: Comparison plots
- Cell #100: Quantify differences
- Cell #104: Sensitivity analysis

**Fix**: Add markdown cells stating these sections are OPTIONAL/ADVANCED

---

## Priority Order for Fixes

### 🔥 CRITICAL (Do First)
1. **Cell #84** - Remove 5 instructor planning TODOs
   - Most visible problem
   - Unprofessional and confusing

### ⚠️ HIGH PRIORITY
2. **Cells #12, 64, 70, 72, 89** - Remove "already implemented" TODOs
   - Students will waste time
   - Creates confusion

3. **Cells #45, 46** - Update well rate TODO
   - Currently misleading

### 📋 MEDIUM PRIORITY
4. **Cell #66** - Fix RCT contradiction
5. **Cell #29** - Clarify property check
6. **Cells #94-100, 104** - Add OPTIONAL markers

### 🎨 LOW PRIORITY
7. **Cells #88, 103** - Remove minor instructor notes

---

## Cell-by-Cell Quick Reference

| Cell | Action | What to Do |
|------|--------|------------|
| 0 | ✅ KEEP | Names & date - student tasks |
| 12 | ❌ REMOVE | "Load well data" - already loaded |
| 29 | 🔄 UPDATE | Make it a verification note |
| 45 | 🔄 UPDATE | Change TODO to NOTE about rate |
| 46 | 🔄 UPDATE | Change TODO to NOTE about rate |
| 64 | ❌ REMOVE | "Check DSP" - already created |
| 66 | 🔄 UPDATE | Remove contradiction |
| 70 | ❌ REMOVE | "Check source" - already loaded |
| 72 | ❌ REMOVE | "Create map" - already created |
| 84 | ❌ REMOVE | **5 instructor TODOs - CRITICAL** |
| 85-86 | ✅ KEEP | Breakthrough template - 20 TODOs |
| 88 | ❌ REMOVE | "Keep simple" instructor note |
| 89 | ❌ REMOVE | "Extract mass balance" - already done |
| 94-100 | ℹ️ CLARIFY | Add OPTIONAL context |
| 103 | ❌ REMOVE | "Affected area" instructor note |
| 104 | ℹ️ CLARIFY | Add OPTIONAL context |
| 107 | ✅ KEEP | Discussion - 6 prompts |
| 108 | ✅ KEEP | Interpretation - 5 prompts |
| 109 | ✅ KEEP | Conclusions - 1 prompt |
| 110-111 | ✅ KEEP | Recommendations - 3 prompts |
| 113 | ✅ KEEP | References - 1 prompt |

---

## Key Findings

### Good News ✅
- **Template structure is solid**: Cells 85-86 (breakthrough), 107-111 (discussion/recommendations) are well-designed student exercises
- **Most TODOs are legitimate**: 45 out of 66 total TODO instances should be kept
- **Clear learning scaffolding**: Discussion prompts have good guiding questions

### Problems Found ⚠️
1. **Instructor notes leaked**: Cell #84 has raw planning notes visible to students
2. **Misleading "already done" TODOs**: 6 cells have complete code but TODO headers
3. **Rate contradiction**: Cells 45/46 ask students to "choose" a rate that's already set
4. **Ambiguous "Check" wording**: Unclear if verification or implementation
5. **Optional sections not marked**: Students may think analytical/sensitivity are required

### Root Cause
The notebook appears to be an instructor working copy that wasn't properly cleaned before giving to students. Needs a clear separation between instructor notes and student-facing content.

---

## Recommended Workflow

1. **Make a backup** of the current notebook
2. **Critical fixes first** (Cell #84 instructor notes)
3. **High priority** (Remove misleading "already implemented" TODOs)
4. **Medium priority** (Clarifications and updates)
5. **Test with a student** to verify clarity
6. **Document the changes** in a changelog

---

## For Quick Communication

**One-sentence summary**:
> "12 TODOs need removal (misleading/instructor notes), 4 need updates (clarification), 5 need OPTIONAL markers, and 45 are good student tasks - Cell #84 is the most critical issue (instructor planning notes visible)."

**Elevator pitch**:
> "The notebook has good student templates (breakthrough curves, discussion prompts), but 6 cells have 'already implemented' misleading TODOs, and Cell #84 accidentally shows instructor planning notes. Quick fixes will make this student-ready."

---

See `TODO_ANALYSIS_REPORT.md` for complete details and specific edit instructions.
