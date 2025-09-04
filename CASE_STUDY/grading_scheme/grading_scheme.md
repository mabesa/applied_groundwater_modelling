# Steady-State Case Study — Assignment & Rubric

**Goal.** Apply the baseline MODFLOW-2005 model to a small practical question (e.g., new well near a river) and show that you can set up a scenario, run it, interpret results, and sanity-check with an analytical formula.

## Deliverables (max 4 pages + figures)
1. **Problem statement (≤5 sentences)** — what you changed and why it matters.
2. **Methods** — baseline description (1–2 sentences), scenario definition (YAML excerpt), solver notes if relevant.
3. **Results (required figures)**  
   - Head map (Layer 1) and Drawdown map (Scenario − Baseline)  
   - Observation heads table (3–5 points)  
   - Compact water budget summary (selected terms, e.g., WEL, RIVER LEAKAGE, CHD, RECHARGE)
4. **Analytical check** — Thiem/Dupuit computation at one radius with assumptions stated; compare to model.
5. **Discussion (≤8 sentences)** — interpretation + one sensitivity (e.g., ×0.5/×2 on K or RIV conductance).

---

**Tip:** Keep the scenario small (1–2 changes). If you push the model into convergence trouble, reduce conductances or step back to a milder case and explain the limitation.


## Reproducibility
- Include your `case_student.yaml` and the notebook used to generate results.
- Use meters and days consistently. Note any assumptions you made.

## Report grading scheme (100 points)

The report will be graded based on the following criteria:
Content (60%)
Layout (40%)

### Content
- **Clarity of problem statement** (10) — concise, relevant, measurable objective.  
- **Scenario setup accuracy** (20) — YAML correctness, units, locations, rates reasonable.  
- **Figures & tables quality** (20) — required plots readable with units; obs heads and budget present.  
- **Analytical check** (20) — correct formula/parameters, comparison and reasoning.  
- **Interpretation & sensitivity** (20) — physical insight, linkage to budgets/BCs, sensible sensitivity.  
- **Reproducibility** (10) — code and config run top-to-bottom without edits.

### Layout
Layout is important! It is what you hand out to your customers in written form and which will be dough out even years after project end if a new project is happening in the same location. It should be clear, concise, and easy to read.
Here are some tips:
- No numbers without units (or `-` for dimensionless quantities)
- Consistent font size and type
- Consistent numbering of figures and tables
- Figures and tables have captions (figures below, tables above).
- Each figure and table is referenced in the text.
- Table formatting is consistent (e.g., units in parentheses, right-aligned numbers (or aligned by decimal point), left-aligned text, etc.)
- Consistent numbering of chapters and sections
- Consistent referencing of figures, tables, and chapters, equations, etc.
- Correct referencing of sources
