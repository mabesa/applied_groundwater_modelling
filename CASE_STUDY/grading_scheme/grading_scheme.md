# Steady-State Case Study — Assignment & Rubric

**Goal.** Apply the baseline MODFLOW-2005 model to a small practical question (e.g., new well near a river) and show that you can set up a scenario, run it, interpret results, and sanity-check with an analytical formula.

## Deliverables (max 4 pages + figures)
1. **Problem statement (≤5 sentences)** — what you changed and why it matters.
2. **Methods** — baseline description (1–2 sentences), scenario definition (YAML excerpt), solver notes if relevant.
3. **Results (required figures)**  
   - Head map and Drawdown map (Scenario − Baseline)  
   - Observation heads table (3–5 points)  
   - Compact water budget summary (selected terms, e.g., WEL, RIVER LEAKAGE, CHD, RECHARGE)
4. **Analytical check** — Thiem/Dupuit computation at one radius with assumptions stated; compare to model.
5. **Discussion (≤8 sentences)** — interpretation + one sensitivity (e.g., ×0.5/×2 on K or RIV conductance).

---

**Tip:** Keep the scenario small (1–2 changes). If you push the model into convergence trouble, reduce conductances or step back to a milder case and explain the limitation.


## Reproducibility
- Save and test-run your notebook under CASE_STUDY/student_work/ after updating your repository with the diagnostics script and from a fresh kernel before submission as instructors will run it from the same location to check reproducibility.
- The notebook must run from top to bottom without any errors.
- You will be notified 1 day after the submission deadline if your notebook is not reproducible. You will have 24 hours to fix it. This will cost you 20 points.
- If not reproducible, you will receive a 0 for the assignment.
- Use relative paths for data files.
- Use meters and days consistently. Note any assumptions you made.

## Report grading scheme (100 points)

The report will be graded based on the following criteria:
Content (60%)
Layout (40%)

### Content
The content of your report is the most important part. It should be clear, concise, and well-organized. 
- **Problem statement** — what you changed and why it matters.
Here is a breakdown of the content criteria:
- **Clarity of problem statement** (10 points) — concise, relevant, measurable objective.  
- **Scenario setup accuracy** (20 points) — units, locations, rates reasonable.  
- **Figures & tables quality** (20 points) — required plots readable with units; obs heads and budget present.  
- **Analytical check** (20 points) — correct formula/parameters, comparison and reasoning.  
- **Interpretation & sensitivity** (20 points) — physical insight, linkage to budgets/BCs, sensible sensitivity.  

### Layout
Layout is important! It is what you hand out to your customers in written form and which will be dough out even years after project end if a new project is happening in the same location. It should be clear, concise, and easy to read. Jupyter Notebooks are better suited for reproducability of workflows than for professional report writing (there is only limited support for cross-referencing) but we'll find a way to make it work.   
Here is a list of layout items that will be checked (not all apply to every report, e.g., if no tables are used, table formatting is not relevant):
- No numbers without units in tables and figures (or `-` for dimensionless quantities)
- Consistent font size and type in the text (we will be lenient with font types and sizes in figures as they are more difficult to control)
- Consistent numbering of figures and tables
- Figures and tables have captions (figures below, tables above).
- Each figure and table is referenced in the text.
- Table formatting is consistent (e.g., units in parentheses, right-aligned numbers (or aligned by decimal point), left-aligned text, etc. (no mixed alignment styles in one table)).
- Consistent numbering of chapters and sections
- Consistent referencing of figures, tables, and chapters, equations, etc.
- Correct and consistent referencing of sources
