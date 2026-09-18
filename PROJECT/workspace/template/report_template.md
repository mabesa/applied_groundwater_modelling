> **GUIDANCE — delete this block.**
> **Group report template — Applied Groundwater Modelling.**
> Read `REPORT_BRIEF.md` first: it says what each section is FOR and how it is judged.
> This file is only the skeleton.
>
> **Same skeleton in three formats — pick one, they are equivalent:**
> `report_template.md` (JupyterHub, VS Code, any editor) ·
> `report_template.tex` (LaTeX / Overleaf) ·
> `report_template.docx` (Microsoft Word).
>
> **How to use.** Copy your chosen file into your group folder as `report.md`, `report.tex`
> or `report.docx`. Delete each grey GUIDANCE block as you fill that section in — they are
> instructions, not content. Then export to **`report.pdf`** in your group folder root:
> print to PDF from Word, hit Recompile in Overleaf, or from Markdown run
> `pandoc report.md -o report.pdf` — **this works on the course JupyterHub**, which has
> pandoc and LaTeX installed. On your own laptop it needs a LaTeX engine; if you get
> `pdflatex not found`, run `pandoc report.md -o report.docx` instead and print to PDF
> from Word.
>
> **Limits.** 10 pages max, excluding this title block, references and appendix.
> Appendix capped at 5 pages. The per-section budgets below add to about 8, which leaves
> you room — they are guides, not rules.

# `<Your title — name the concession and the question, not "Groundwater Modelling Report">`

**Group `<N>`** · `<First Last>`, `<First Last>`, `<First Last>`
Applied Groundwater Modelling · `<date>`

---

## 1. Problem and modelling question

> **GUIDANCE — delete this block.**
> ~0.5 page. One paragraph.
>   Your concession, its setting, and the question your scenario actually asks.
>   Be specific. "Does the assigned recharge reduction change river leakage enough to
>   matter for the concession's yield" is a question. "We study the Limmat aquifer" is not.


`<...>`

## 2. Conceptual model and assumptions

> **GUIDANCE — delete this block.**
> ~1.5 pages.
>   The aquifer as YOU are modelling it: boundaries and what they represent, the stresses,
>   your scenario's physical story (the type -> story mapping in flow section 3), and the
>   transport setup — spill, doublet, the locked physics (alpha_L = 10 m, alpha_T = 1 m,
>   n_e = 0.20) and your group's pinned reactions.
>   State the assumptions YOU are making, not the ones the software makes, and name the
>   CONSEQUENCE of each — steady state, one shared regional model, local refinement, a
>   clean-water doublet with a separate zero-water contaminant source.


`<...>`

### 2.1 Assumptions and their consequences

| Assumption | Why it is reasonable here | What it costs us |
|---|---|---|
| `<e.g. steady state>` | `<...>` | `<...>` |
| `<...>` | `<...>` | `<...>` |

## 3. Method

> **GUIDANCE — delete this block.**
> ~1 page.
>   Enough that a competent reader could repeat it: the four flow states and what each
>   isolates, how your scenario forcing is applied, the transport build, and which
>   quantities came from which export. Point to the notebooks; do not reproduce their code.


`<...>`

## 4. Results

> **GUIDANCE — delete this block.**
> ~3 pages. THE STRUCTURE MATTERS: organise by FINDING, not by card.
>   The full record of each card and its extension is already in the scratch notebooks and
>   in tables/ — do not re-narrate it here. What belongs here is the INTEGRATED result:
>   what the flow response, the scenario forcing, the water balance and the transport
>   verdict say TOGETHER about your concession.
>   Every figure and table: caption, units, and the file under figures/ or tables/ it came
>   from. Every computed number must be traceable to the frozen bundle.
>   Two traps to handle explicitly:
>    - head change has two conventions: abs() (counts the injection mound) vs drawdown
>      (base - compare, positive where head falls). Say which you are quoting.
>    - an advective travel time is not a concentration peak. Do not reconcile them by
>      arithmetic.
>   Suggested finding-shaped headings — rename them to YOUR findings:


> **Figure and table pattern — copy the shapes below.** Every caption carries the units
> and the file the figure came from, which is what the brief asks of every one of them.
> (The paths are examples; yours appear only once you have run your cards.)

```text
![Drawdown (base -> wells), m. Source: figures/cardA_drawdown_map.png](figures/cardA_drawdown_map.png)
```

| Metric | Value | Unit | Source |
|---|---|---|---|
| Max drawdown | `<...>` | m | `tables/cardA_drawdown_summary.csv` |

### 4.1 `<What the doublet does to the flow field>`

`<...>`

### 4.2 `<What your scenario forcing adds, and where it dominates>`

`<...>`

### 4.3 `<What the water balance says>`

`<...>`

### 4.4 `<The transport verdict>`

`<...>`

## 5. Uncertainty and the limits of your claims

> **GUIDANCE — delete this block.**
> ~1.5 pages. This section separates reports at this level. Required content:
>    - the mesh envelope on your transport peak (two defensible meshes move it by roughly
>      +/-20 %), and its consequence — WHETHER OR NOT it flips your verdict;
>    - a signal / artefact / instability judgment on your main flow result, with the
>      evidence that discriminates — or a correct finding that your evidence CANNOT
>      discriminate, and what would;
>    - at least one limitation you found and quantified yourselves;
>    - your card extensions' defensibility answers, synthesised rather than listed.
>   A limitation you found and measured is worth more than a paragraph of generic caveats.


`<...>`

### 5.1 What this model cannot tell you

> **GUIDANCE — delete this block.**
> State these explicitly. The model resolves transport ALONG the flow axis but not
>   across it, so:
>     CLAIMABLE     — arrival time, first threshold exceedance, receptor peak concentration
>     NOT CLAIMABLE — contaminated-area maps, lateral threshold-contour width, exact plume
>                     footprint. These are numerical artefacts at any feasible grid.
>   Then check nothing elsewhere in your report quietly breaks this.


`<...>`

## 6. Conclusion and practical recommendation

> **GUIDANCE — delete this block.**
> ~0.5 page.
>   What the result means for the actual problem — the concession, the receptor, the
>   compliance question. ONE recommendation, and the condition under which you would
>   withdraw it.
>   A no-reach or below-threshold result is not a weaker result. "It does not reach the
>   well, and here is the mechanism" is a strong conclusion when the evidence supports it.


`<...>`

## 7. Contribution statement

> **GUIDANCE — delete this block.**
> Must be consistent with `SUBMISSION_README.md` and the `STUDENT_NAME` fields in the
> scratch notebooks. That file lists one row per *card*, this one per *member* — different
> shapes, same people. In a two-member group one member has three cards; mark the short
> one `(short)`.


| Member | Cards | Contribution |
|---|---|---|
| `<name>` | `<X, Y>` | `<one sentence>` |
| `<name>` | `<X, Y>` | `<one sentence>` |
| `<name>` | `<X, Y>` | `<one sentence>` |

**Steward roles:** flow `<name>` · transport `<name>` · export `<name>`

## References

`<...>`

---

# Appendix

> **GUIDANCE — delete this block.**
> Not counted in the 10 pages. Capped at 5 pages.


## A. Figure and table index

| Report item | File |
|---|---|
| Figure 1 | `figures/<...>` |
| Table 1 | `tables/<...>` |

## B. `<Derivations or intermediate numbers you want on record>`

`<...>`
