#!/usr/bin/env python3
"""
Script to simplify 4b_transport_model_implementation.ipynb by:
1. Removing Section 6 entirely (2.5D transport with Pe=5.0)
2. Removing excessive Peclet number discussions
3. Simplifying Section 7 (Method Selection)
4. Renumbering sections logically
"""

import json
import re

def remove_section_6(nb):
    """Remove Section 6 entirely (cells 32-52)"""
    # Find Section 6 start and Section 7 start
    section_6_start = None
    section_7_start = None

    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            if '## 6. 2.5D Transport' in source:
                section_6_start = i
            elif '## 7. Alternative Approaches' in source:
                section_7_start = i
                break

    if section_6_start is not None and section_7_start is not None:
        print(f"Removing Section 6: cells {section_6_start} to {section_7_start - 1}")
        # Remove all cells from Section 6
        del nb['cells'][section_6_start:section_7_start]
        return section_7_start - section_6_start
    return 0

def add_peclet_mention_to_section_2(nb):
    """Add brief Peclet number mention to Section 2"""
    peclet_text = """
## 2.4 Grid Resolution and the Peclet Number

When using numerical methods like MT3D, grid resolution is critical for accurate transport modeling. The **Peclet number (Pe)** is a dimensionless number that helps us assess whether our grid is fine enough:

$$
Pe = \\frac{\\Delta x}{\\alpha_L}
$$

Where:
- $\\Delta x$ is the grid cell size [L]
- $\\alpha_L$ is the longitudinal dispersivity [L]

**Rule of thumb**: Keep Pe ≤ 2 (ideally ≤ 1) to avoid numerical dispersion artifacts. This means your grid cells should be smaller than or equal to 2 times the dispersivity.

For example:
- If $\\alpha_L = 20$ m, then $\\Delta x \\leq 40$ m (better if $\\Delta x \\leq 20$ m)
- Smaller dispersivity requires finer grids
- Around wells or sources, local grid refinement is often needed

This is why we'll use the **telescope approach** (local grid refinement) for our case study—it gives us fine resolution where we need it without making the entire model too large.

"""

    # Find Section 2.3 (last subsection before 2.4 analytical vs numerical)
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            if '### 2.4 Analytical vs. Numerical Solutions' in source:
                # Insert new Peclet section before this
                new_cell = {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": peclet_text.strip().split('\n')
                }
                nb['cells'].insert(i, new_cell)
                print(f"Added Peclet mention at cell {i}")
                return 1
    return 0

def simplify_section_7(nb):
    """Simplify Section 7 by removing Peclet-heavy content"""
    # Find Section 7
    section_7_start = None
    section_8_start = None

    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            if '## 7. Alternative Approaches' in source:
                section_7_start = i
            elif '## 8. Telescope Approach' in source:
                section_8_start = i
                break

    if section_7_start is None or section_8_start is None:
        return

    # Simplify the section 7 content
    simplified_section_7 = """## 7. Alternative Approaches and Method Selection

### 7.1 Learning Objectives

After completing this section, you will be able to:
- Understand when to use different transport modeling approaches
- Select appropriate methods based on problem requirements
- Recognize the advantages and limitations of each approach

### 7.2 The Modeling Spectrum: From Simple to Complex

Transport modeling offers a range of approaches, from simple analytical solutions to complex numerical simulations. **The key is choosing the right tool for the problem at hand.**

### 7.3 Method Categories and Their Characteristics

#### 7.3.1 Analytical Solutions

**When to use:**
- Homogeneous, simple geology
- Constant flow field
- Simple boundary conditions
- Quick screening or verification

**Limitations:**
- Cannot handle complex heterogeneity
- Limited to idealized conditions
- No irregular boundaries

**Example:** The 1D pulse source solution we verified in Section 4.

#### 7.3.2 Numerical Models (MT3DMS, MODFLOW 6 GWT)

**When to use:**
- Complex heterogeneous geology
- Multiple sources and sinks
- Time-varying conditions
- Need for detailed concentration predictions

**Limitations:**
- Requires careful grid design
- More computationally intensive
- Need verification against simpler cases

**Example:** The telescope submodel approach we'll use for the case study.

#### 7.3.3 Particle Tracking (MODPATH)

**When to use:**
- Advection-dominated transport
- Capture zone delineation
- Travel time analysis
- Preliminary site assessments

**Limitations:**
- Does not model dispersion or reactions
- Qualitative for concentration predictions
- Assumes steady-state flow

**Example:** Wellhead protection zone delineation.

#### 7.3.4 Hybrid Approaches

**Combining methods can leverage the strengths of each:**
- Use particle tracking for preliminary assessment, then MT3D for detailed modeling
- Verify numerical models against analytical solutions where possible
- Use telescope refinement to focus computational effort where needed

### 7.4 Decision Framework for Method Selection

**Key questions to guide method selection:**

1. **What level of detail do you need?**
   - Screening → Analytical or particle tracking
   - Detailed predictions → Numerical (MT3D)

2. **How complex is your site?**
   - Simple/homogeneous → Analytical possible
   - Heterogeneous/complex → Numerical required

3. **What processes are important?**
   - Advection only → Particle tracking
   - Advection + dispersion → Analytical or MT3D
   - Reactions/decay → MT3D with reaction packages

4. **What are your computational constraints?**
   - Limited resources → Start simple, use local refinement
   - More resources → Full 3D transport if justified

### 7.5 Professional Practice: Method Selection in Real Projects

In professional practice, projects typically follow a tiered approach:

**Phase 1 - Screening:** Analytical solutions or particle tracking for preliminary assessment

**Phase 2 - Calibration:** Numerical models with field data integration

**Phase 3 - Prediction:** Refined numerical models for detailed predictions

**Key principle:** Start simple, add complexity only when needed and justified.

### 7.6 Common Pitfalls in Method Selection

1. **Overcomplicating early:** Using complex numerical models when simpler approaches suffice
2. **Underestimating requirements:** Using particle tracking when dispersion is important
3. **Ignoring verification:** Not checking numerical models against analytical solutions
4. **Wrong grid resolution:** Using grid cells that are too coarse for the dispersivity

### 7.7 Key Takeaways for Method Selection

- **Match method to problem complexity** - don't over- or under-engineer
- **Verify numerical models** against analytical solutions when possible
- **Use local grid refinement** (telescope approach) to focus computational effort
- **Start simple** and add complexity incrementally
- **Consider computational efficiency** - fine grids everywhere are rarely needed

### 7.8 Looking Ahead to Section 8

The telescope approach (Section 8) is our solution to the grid resolution challenge. It allows us to:
- Use appropriate grid resolution around wells and sources
- Keep the regional model computationally manageable
- Maintain connection between local and regional scales

This is the approach you'll implement for your transport case studies.
"""

    # Replace Section 7 content
    nb['cells'][section_7_start] = {
        "cell_type": "markdown",
        "metadata": {},
        "source": simplified_section_7.strip().split('\n')
    }

    # Remove any additional cells in Section 7 (keep only the main markdown)
    cells_to_remove = section_8_start - section_7_start - 1
    if cells_to_remove > 0:
        del nb['cells'][section_7_start + 1:section_8_start]
        print(f"Simplified Section 7: removed {cells_to_remove} cells")
        return cells_to_remove

    return 0

def renumber_sections(nb):
    """Renumber sections after removals"""
    # Mapping: old section number -> new section number
    section_map = {
        '1': '1',  # Overview
        '2': '2',  # Introduction
        '3': '3',  # Analytical Solution
        '4': '4',  # 1D Verification
        '5': '5',  # Load Flow Model (will be removed/merged)
        '6': None,  # REMOVED (2.5D Transport)
        '7': '6',  # Method Selection
        '8': '7',  # Telescope Approach
        '9': '8',  # Summary and Case Study
    }

    # Also need to handle Section 5 - it loads the flow model but doesn't add transport
    # We should merge it into Section 7 (telescope) or remove it
    # For now, let's keep it but renumber

    for cell in nb['cells']:
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])

            # Renumber main sections
            for old_num, new_num in section_map.items():
                if new_num is not None:
                    # Match patterns like "## 7." or "## 7 "
                    pattern1 = f'## {old_num}\\.'
                    replacement1 = f'## {new_num}.'
                    pattern2 = f'## {old_num} '
                    replacement2 = f'## {new_num} '

                    if pattern1 in source:
                        source = source.replace(pattern1, replacement1)
                    if pattern2 in source:
                        source = source.replace(pattern2, replacement2)

                    # Also handle subsections like "### 7.1"
                    pattern3 = f'### {old_num}\\.'
                    replacement3 = f'### {new_num}.'
                    if pattern3 in source:
                        source = source.replace(pattern3, replacement3)

                    # References like "Section 7"
                    pattern4 = f'Section {old_num}'
                    replacement4 = f'Section {new_num}'
                    if pattern4 in source:
                        source = source.replace(pattern4, replacement4)

                    # References like "Sections 3-6"
                    # Handle ranges separately

            cell['source'] = source.split('\n')

    print("Renumbered sections")

def update_section_1_structure(nb):
    """Update Section 1.5 (Notebook Structure) to reflect new organization"""

    new_structure = """### 1.5 Notebook Structure

This notebook guides you through transport modeling with increasing complexity:

**Section 1:** Overview and learning path

**Section 2:** Transport theory fundamentals (including grid resolution basics)

**Section 3:** Analytical solution for verification

**Section 4:** 1D MT3D verification (proves MT3D works correctly)

**Section 5:** Load Limmat Valley regional flow model

**Section 6:** Method selection framework (when to use different approaches)

**Section 7:** Telescope submodel implementation (refined grid + transport)

**Section 8:** Your transport case study workflow

**The key insight:** We verify MT3D works (Section 4), then apply telescope refinement with transport (Section 7) because we need fine resolution around wells. This is the approach you'll use for your case studies.
"""

    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            if '### 1.5 Notebook Structure' in source:
                cell['source'] = new_structure.strip().split('\n')
                print(f"Updated Section 1.5 at cell {i}")
                break

def remove_section_5_renumber(nb):
    """
    Actually, let's keep Section 5 but update its title and make it shorter.
    It's needed to show the flow model is ready.
    """
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            if '## 5. Load Limmat Valley Flow Model' in source:
                # Just update the summary
                for j in range(i, min(i+20, len(nb['cells']))):
                    if nb['cells'][j]['cell_type'] == 'markdown':
                        sub_source = ''.join(nb['cells'][j]['source'])
                        if '### 5.4 Summary' in sub_source:
                            new_summary = """### 5.4 Summary: Flow Model Ready for Transport

We now have a calibrated regional flow model of the Limmat Valley that provides:
- Steady-state flow field
- Head distribution
- Specific discharge vectors for transport

**Next steps:**
- Skip directly to Section 7 to learn about the telescope approach
- We'll create a refined submodel with appropriate grid resolution for transport
- This workflow (regional flow → refined transport submodel) is what you'll use for your case studies
"""
                            nb['cells'][j]['source'] = new_summary.strip().split('\n')
                            print(f"Updated Section 5.4 summary at cell {j}")
                            break
                break

def main():
    print("Loading notebook...")
    with open('4b_transport_model_implementation.ipynb', 'r') as f:
        nb = json.load(f)

    print(f"Original notebook has {len(nb['cells'])} cells\n")

    # Step 1: Remove Section 6 entirely
    print("Step 1: Removing Section 6...")
    cells_removed = remove_section_6(nb)
    print(f"  Removed {cells_removed} cells\n")

    # Step 2: Add brief Peclet mention to Section 2
    print("Step 2: Adding Peclet mention to Section 2...")
    cells_added = add_peclet_mention_to_section_2(nb)
    print(f"  Added {cells_added} cells\n")

    # Step 3: Simplify Section 7
    print("Step 3: Simplifying Section 7...")
    cells_removed_7 = simplify_section_7(nb)
    print(f"  Simplified Section 7 (removed {cells_removed_7} cells)\n")

    # Step 4: Update Section 5 summary
    print("Step 4: Updating Section 5 summary...")
    remove_section_5_renumber(nb)
    print()

    # Step 5: Renumber sections
    print("Step 5: Renumbering sections...")
    renumber_sections(nb)
    print()

    # Step 6: Update Section 1 structure
    print("Step 6: Updating Section 1.5 structure...")
    update_section_1_structure(nb)
    print()

    print(f"Final notebook has {len(nb['cells'])} cells")
    print(f"Net change: {len(nb['cells']) - (60 if 'original_count' not in locals() else original_count)} cells\n")

    # Save the modified notebook
    print("Saving modified notebook...")
    with open('4b_transport_model_implementation.ipynb', 'w') as f:
        json.dump(nb, f, indent=1)

    print("Done! Notebook simplified successfully.")

if __name__ == '__main__':
    main()
