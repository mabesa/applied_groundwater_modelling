# Design Document: Interactive K-Averaging Exercise for Notebook 3

**Status:** Plan (ready for implementation)
**Date:** 2026-02-12
**Target notebook:** `PROJECT/flow/3_modflow_fundamentals.ipynb`

---

## 1. Context and Rationale

### 1.1 The Gap

Notebook 3 introduces conductance as $C_{ij} = K \cdot A_{ij} / L_{ij}$ (cell-5, collapsible section) and lists NPF in the packages table (cell-10). But it never addresses the question: **what K do you use when adjacent cells have different hydraulic conductivities?**

This is a fundamental concept that:
- Directly follows from the conductance formula
- Explains why MODFLOW's NPF package has an `alternative_cell_averaging` option
- Has major practical implications (e.g., a clay layer reducing flow by orders of magnitude)
- Is a common source of modeling errors

### 1.2 What Prompted This

An LLM-generated draft covering K-averaging, Newton-Raphson, and anisotropy was reviewed. The content was too long, included topics better suited for Notebook 4, and the exercise was static (pen-and-paper). This design distills the relevant parts and makes the exercise interactive.

---

## 2. What to Include (and What to Cut)

### Include in Notebook 3

| Content | Rationale |
|---------|-----------|
| The challenge: "which K between two cells?" | Direct follow-up to conductance formula |
| Four averaging methods with formulas | Core concept, maps to NPF options |
| Interactive widget to explore K contrast effects | Builds intuition; follows course patterns |
| Multiple-choice: which method for a streambed? | Applies concept to Limmat Valley context |

### Move to Notebook 4 (or drop)

| Content | Reason to exclude |
|---------|-------------------|
| Newton-Raphson formulation | Implementation detail; belongs where NPF is actually coded |
| Anisotropy (K_h/K_v ratios) | Belongs in Notebook 4/5 when K is actually specified |
| Detailed Newton solver settings | Too advanced for a "fundamentals" notebook |
| FloPy code snippet for NPF | Notebook 3 has no code exercises; code starts in Notebook 4 |

---

## 3. Placement in Notebook

### Recommended location: New cell after cell-5, before cell-6

**Why here:**
- Cell-5 is the collapsible "How MODFLOW Discretizes" section that introduces $C_{ij} = K \cdot A_{ij} / L_{ij}$
- The natural question after seeing this formula is "but which K?"
- Cell-6 is the unit consistency warning — the K-averaging section slots cleanly between discretization details and the unit warning

### Alternative: Inside the collapsible section in cell-5

The K-averaging content could be added at the end of the existing `<details>` block in cell-5, after "Why This Works for Any Grid Shape." This keeps it optional for students who want to go deeper, without adding length to the core reading path.

**Recommendation:** Use the collapsible approach. The notebook already states "~10 minutes" for core content, and adding a mandatory section would break that promise. Making it a collapsible subsection within cell-5 keeps it available for interested students.

### Structure

```
Cell-5 (existing collapsible section):
  ├── From Continuous Equation to Discrete Cells (existing)
  ├── Flow Between Two Connected Cells (existing)
  ├── Mass Balance at Each Cell (existing)
  ├── The System of Equations (existing)
  ├── Why This Works for Any Grid Shape (existing)
  └── NEW: What K Between Cells with Different Properties? (new subsection)
       ├── Brief intro paragraph + ASCII diagram
       ├── Averaging methods table (4 rows)
       ├── Interactive widget (code cell)
       └── Multiple-choice checkpoint
```

---

## 4. Content Specification

### 4.1 Markdown Introduction (~100 words)

A brief paragraph explaining the challenge:
- The conductance formula assumes a single K, but neighboring cells often have different K values
- MODFLOW 6's NPF package provides methods to compute an effective K between cells
- The choice matters most when there's **high contrast** (e.g., streambed over aquifer)

Reuse the ASCII diagram from the LLM draft (it's clear and effective):

```
      Cell i                 Cell j
    +---------+           +---------+
    | K_i     |           |     K_j |
    |  = 100 ----→ Q_ij --→  = 10   |  (m/d)
    |   m/d   |           |   m/d   |
    +---------+           +---------+
              |← L_ij  →|
```

### 4.2 Averaging Methods Table

Simplified from the LLM draft. Drop the Pros/Cons columns (too much for this notebook level). Note: the formulas below assume **equal cell sizes** for simplicity — state this explicitly.

| Method | Formula | Physical Analogy |
|--------|---------|------------------|
| **Harmonic mean** (MODFLOW default) | $K_{eff} = \frac{2 K_i K_j}{K_i + K_j}$ | Resistors in **series** — low K dominates |
| **Logarithmic mean** | $K_{eff} = \frac{K_i - K_j}{\ln(K_i / K_j)}$ | Between harmonic and arithmetic |
| **Arithmetic mean** | $K_{eff} = \frac{K_i + K_j}{2}$ | Resistors in **parallel** — high K dominates |
| **Geometric mean** | $K_{eff} = \sqrt{K_i \cdot K_j}$ | Middle ground (for reference) |

**Teaching notes for the implementer:**
- The harmonic mean formula is for **equal-length cells**. The general form is $K_{eff} = (L_i + L_j) / (L_i/K_i + L_j/K_j)$. For this exercise, equal cells are fine.
- The logarithmic mean approaches K_i as K_i → K_j (L'Hôpital). No division-by-zero issue in practice; just note "≈ K when K_i ≈ K_j."
- The geometric mean ($\sqrt{K_i K_j}$) is not a MODFLOW 6 option but is useful pedagogically to show the ordering.
- The ordering is always: **harmonic ≤ geometric ≤ arithmetic** (with equality iff K_i = K_j). The logarithmic mean falls between harmonic and arithmetic (closer to geometric).

**MODFLOW 6 connection** (one sentence): "In FloPy, the averaging method is set via `alternative_cell_averaging` in the NPF package. The default is harmonic mean."

### 4.3 Interactive Widget

#### Design

Two sliders controlling K_i and K_j, with a real-time plot showing where each effective K falls on a log-scale axis between K_min and K_max.

#### Widget Specifications

| Widget | Type | Range | Default | Scale |
|--------|------|-------|---------|-------|
| K_i | `FloatLogSlider` | 0.01 – 1000 m/d | 100 m/d | Logarithmic |
| K_j | `FloatLogSlider` | 0.01 – 1000 m/d | 10 m/d | Logarithmic |

> **Why log sliders:** K varies over orders of magnitude. Linear sliders would make it impossible to explore realistic contrasts like streambed (0.1 m/d) vs. gravel aquifer (1000 m/d).

#### Visualization

A horizontal "number line" style plot (single matplotlib figure, ~3 inches tall):

```
K_eff values on log scale
|----•---------•------•---------•-----------|
   Harm(18)  Log(39) Geom(32)  Arith(55)

K_j=10                                K_i=100
 ▼                                      ▼
```

Concrete specifications:
- **X-axis:** log scale, range from min(K_i, K_j)/2 to max(K_i, K_j)*2
- **Markers:** Colored dots for each averaging method, with value labels
- **Reference lines:** Vertical dashed lines at K_i and K_j positions
- **Color scheme:** Use distinct colors (e.g., blue=harmonic, green=logarithmic, orange=geometric, red=arithmetic)
- **Key insight text** below the plot: dynamically shows the ratio K_max/K_min and a one-line interpretation, e.g.:
  - "K contrast = 10×. Harmonic mean is 5.5× smaller than arithmetic mean."
  - "K contrast = 1×. All methods give the same value (as expected)."

#### Implementation Pattern

Follow the existing pattern from `uncertainty_plot.py` (slider + `widgets.interactive`):

```python
import ipywidgets as widgets
import numpy as np
import matplotlib.pyplot as plt

def plot_k_averaging(K_i, K_j):
    """Plot effective K for all averaging methods."""
    harmonic = 2 * K_i * K_j / (K_i + K_j)
    arithmetic = (K_i + K_j) / 2
    geometric = np.sqrt(K_i * K_j)

    # Logarithmic mean (handle K_i ≈ K_j)
    if abs(K_i - K_j) / max(K_i, K_j) < 1e-6:
        logarithmic = K_i
    else:
        logarithmic = (K_i - K_j) / np.log(K_i / K_j)

    # ... create horizontal log-scale plot with markers ...

K_i_slider = widgets.FloatLogSlider(
    value=100, base=10, min=-2, max=3, step=0.1,
    description='K_i (m/d):', readout_format='.1f'
)
K_j_slider = widgets.FloatLogSlider(
    value=10, base=10, min=-2, max=3, step=0.1,
    description='K_j (m/d):', readout_format='.1f'
)

widgets.interactive(plot_k_averaging, K_i=K_i_slider, K_j=K_j_slider)
```

#### File Location

Create a new module: `_SUPPORT/src/k_averaging_demo.py`

This follows the pattern of `grid_demo.py` — a small, self-contained demo module imported by the notebook. Export a single function `show_k_averaging()` that creates and displays the widget.

### 4.4 Follow-Up: Multiple-Choice Checkpoint

After the widget, add a conceptual question using the existing `create_multiple_choice` pattern from `shared_functions.py`.

**Question:** "You're modeling the Limmat riverbed (K = 0.1 m/d, thickness = 0.5 m) overlying the gravel aquifer (K = 864 m/d). Which K-averaging method best represents flow through this system?"

**Options:**
- A) Arithmetic mean — gives equal weight to both K values
- B) Harmonic mean — low-K layer controls flow (like resistors in series)
- C) Geometric mean — a balanced middle ground
- D) It doesn't matter — all methods give similar results at this contrast

**Correct answer:** B

**Explanation (shown after submission):**
"The harmonic mean is correct because water must flow *through* the low-K riverbed to reach the aquifer — like resistors in series, the highest resistance controls the total flow. At this contrast (K ratio ≈ 8600×), the choice matters enormously: harmonic mean gives ~0.2 m/d while arithmetic mean gives ~432 m/d — a factor of 2000 difference! This is exactly why MODFLOW uses harmonic mean as the default."

**Implementation:** Add this task to `tasks_data.py` with a new task ID (e.g., `task03_k_averaging_1`).

---

## 5. Implementation Checklist

### Files to Create
- [ ] `_SUPPORT/src/k_averaging_demo.py` — Widget module (~80 lines)

### Files to Modify
- [ ] `PROJECT/flow/3_modflow_fundamentals.ipynb` — Add new content (2-3 new cells)
- [ ] `_SUPPORT/src/scripts/scripts_exercises/tasks_data.py` — Add multiple-choice task data

### Steps

1. **Create `k_averaging_demo.py`**
   - Function `show_k_averaging()` that builds sliders + plot
   - Function `plot_k_averaging(K_i, K_j)` for the visualization
   - Handle edge case: K_i ≈ K_j for logarithmic mean
   - Test standalone: `from k_averaging_demo import show_k_averaging; show_k_averaging()`

2. **Add task data to `tasks_data.py`**
   - Add `task03_k_averaging_1` multiple-choice question
   - Add options, correct answer, and explanation markdown

3. **Edit notebook cell-5** (the collapsible `<details>` section)
   - Add new subsection "What K Between Cells with Different Properties?" at the end
   - Include intro paragraph, ASCII diagram, and simplified table
   - Add one-sentence MODFLOW 6 connection

4. **Add new code cell** after cell-5 (before the unit warning in cell-6)
   - Import and call `show_k_averaging()`
   - Brief instruction: "Explore the effect of K contrast using the sliders below"

5. **Add multiple-choice cell** after the widget code cell
   - Import `create_multiple_choice` from shared_functions
   - Call `create_multiple_choice("task03_k_averaging_1")`

6. **Test**
   - Run notebook end-to-end
   - Verify widget renders in JupyterLab
   - Check that sliders work across full range
   - Verify edge cases (K_i = K_j, extreme contrasts)
   - Check that multiple-choice feedback displays correctly

---

## 6. Design Decisions and Alternatives Considered

| Decision | Chosen | Alternative | Why |
|----------|--------|-------------|-----|
| Placement | Inside collapsible section | New standalone section | Keeps core reading time at ~10 min |
| Slider type | FloatLogSlider | FloatSlider | K varies over orders of magnitude |
| Visualization | Horizontal number line | Bar chart | Number line better shows ordering and relative position |
| Geometric mean | Included for reference | Omit (not a MODFLOW option) | Useful for teaching the ordering property |
| AMT-LMK / AMT-HMK | Not detailed | Full MODFLOW 6 options | Too implementation-specific for a fundamentals notebook |
| Newton-Raphson | Excluded | Include per LLM draft | Separate topic; belongs in Notebook 4 |
| Anisotropy | Excluded | Include per LLM draft | Belongs in Notebook 4/5 |

---

## 7. Correctness Notes

### Formula Accuracy

- The **harmonic mean** formula $\frac{2K_iK_j}{K_i+K_j}$ assumes equal cell sizes. This is correct for teaching but the implementer should note this assumption in the text.
- The **logarithmic mean** $\frac{K_i - K_j}{\ln(K_i/K_j)}$ is mathematically correct. It equals $K_i$ when $K_i = K_j$ (by L'Hôpital's rule). Code should handle this with a tolerance check.
- The LLM draft's "arithmetic-mean thickness" formula was actually a **weighted arithmetic mean** (weighted by distance), not a pure arithmetic mean. For equal cells it reduces to the arithmetic mean. The simplified table above avoids this confusion.

### MODFLOW 6 NPF Options (Reference)

For the implementer's reference, the actual MODFLOW 6 `alternative_cell_averaging` options are:
- **(default):** Harmonic mean of transmissivity
- **LOGARITHMIC:** Logarithmic mean
- **AMT-LMK:** Arithmetic-mean thickness, logarithmic-mean K
- **AMT-HMK:** Arithmetic-mean thickness, harmonic-mean K

In FloPy: `flopy.mf6.ModflowGwfnpf(gwf, alternative_cell_averaging="LOGARITHMIC", ...)`

These details are **not** needed in the notebook — just mention "harmonic mean is the MODFLOW default" and that alternatives exist in NPF.

### Ordering Property

For any $K_i \neq K_j > 0$:

$$K_{harmonic} \leq K_{geometric} \leq K_{logarithmic} \leq K_{arithmetic}$$

Wait — this is actually: harmonic ≤ geometric ≤ logarithmic? Let me verify.

For K_i = 100, K_j = 10:
- Harmonic: 2(100)(10)/110 = 18.18
- Geometric: sqrt(1000) = 31.62
- Logarithmic: 90/ln(10) = 39.09
- Arithmetic: 55

So the ordering is: **harmonic ≤ geometric ≤ logarithmic ≤ arithmetic**. Correct.
