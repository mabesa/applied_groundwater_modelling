from uncertainty_plot import display_disc_area_interactive
from darcy_several_layers_keq import draw_schematic_interface, draw_hx_plot
import print_images as du

### File to define the questions and solutions of tasks / all necessary data

# question to ask (Markdown)
# accepted answers
# exact solution
# unit of the result, if there is one
# correction, steps to explain solution (Markdown)

#------ Dictionary to store the markdown to diplay the question asked
questions_markdown = {
"task01_1":  r"""
We can assume the system to be at a steady state.
 - **Estimate $A$ the area of the Tsalet catchment in $\text{km}^2$**
""",

"task01_2":  r"""
The mean residence time of water $\tau$ was estimated to be 1 year.  
- **Estimate the total volume of the aquifer $V_{aq}$**
""",

"task01_3": r"""
Based on the previous results :
- **Estimate $M_{aq}$ the mean thickness of the aquifer**" 
""",

"task01_4": r"""
Given the uncertainty intervals for $P$ and $Q$ :
- **Estimate the lower bound of *A* uncertainty interval**
""",

"task03_1": r"""
With Tsalet's mixed deposits in the setup column, you now observe that $\Delta h=0.4$ m.
- **What is your estimate of the specific discharge $q$ in mm/s?**
""",

"task03_2": r"""
- **What is the discharge $Q$ in the soil column in mm/s?**
""",

"task03_3": r"""
- **What is the mean velocity of water $u$ in the soil column in mm/s?**
""",

"task03_4": r"""
## Task 1.3
Based on the experiment's graph:
- **What is your estimate for the hydraulic conductivity $K$ in mm/s?**
""",

"task04_1": r"""
- **Estimate the water table level $h(x)$ (in meter) at the interface $x$ = 100m** :
""",

"task04_2": r"""
Based on given data, **estimate the water table level at $x$ = 400m** :
""",

"task04_checkpoint_1": r"""
## Checkpoint 1 - Aquifer Volume
Using the model domain area (~10.4 km²) and the average aquifer thickness from your model:
- **Calculate the total aquifer volume in million m³**

**Hint:** $V = A \times \bar{b}$. Convert your answer to million m³.
""",

"task04_checkpoint_2": r"""
## Checkpoint 2 - Areal Recharge Flux
Using the daily recharge rate and the active model domain area, calculate the total areal recharge flux.

**Given:**
- Daily recharge rate: 3.0 × 10⁻⁴ m/day (from 110 mm/year)
- Active model domain area: ~10.4 km²

**Calculate** the total recharge flux in m³/day:
""",

"task04_checkpoint_3": r"""
## Checkpoint 3 - Model Convergence
Examining your simulation results:
- **What is the water balance error (%)?**
""",

"task04_checkpoint_4": r"""
## Checkpoint 4 - River-Aquifer Interaction
In the Hardhof area of the Limmat Valley:
- **Is the Limmat River gaining or losing water from the aquifer?**
  - A) Gaining (river receives discharge from aquifer)
  - B) Losing (river loses water to aquifer)
  - C) Varies along reach (both gaining and losing sections)
""",

"task04_checkpoint_5": r"""
## Checkpoint 5 - Model Calibration and Validation
Consider how you would assess your model's predictive quality:
- **What observations would you compare to simulated values to assess model quality?**
  - Expected answers may include: head measurements at observation wells, river discharge/baseflow rates, spring discharge data, or other field measurements
""",

# task04_k_values removed - simplified to uniform K in notebook revision

"task03_unit_conversion": r"""
## Unit Conversion Exercise
A laboratory measurement reports hydraulic conductivity as $K = 2.5 \times 10^{-3}$ m/s.
- **Convert this value to m/day for use in your MODFLOW model.**
""",

"task03_steady_state": r"""
## Steady-State Comprehension
What does **steady state** mean for the groundwater flow equation?
""",

"task03_k_averaging_1": r"""
## K Averaging Checkpoint
Consider flow through two layers in series: a low-K layer (K = 0.1 m/d) overlying a high-K layer (K = 30 m/d). Which K-averaging method best represents the effective conductivity for flow perpendicular to the layers?
""",

"task03_conductance": r"""
## Conductance Calculation
Given K = 500 m/day, a shared face area A = 100 m², and distance between cell centers L = 50 m, calculate the conductance C = K × A / L.
""",

"task03_riv_vs_chd": r"""
## River vs. Constant Head
Why do we use a RIV package for the Limmat and Sihl, rather than a CHD boundary?
""",

"task03_grid_choice": r"""
## Grid Type Selection
Which grid type allows local refinement near wells and rivers while keeping the rest of the domain coarser?
""",

"task04_checkpoint_k_sensitivity": r"""
## Sensitivity Exercise - K and the Water Balance
For the Limmat Valley base model (uniform K, steady state):
- **Which K range produces a physically reasonable simulation (no widespread dry cells, heads within the domain)?**
  - A) K = 0.1-1 m/day
  - B) K = 5-50 m/day
  - C) K = 100-500 m/day
  - D) Any K value works equally well
""",

# ============================================================================
# NOTEBOOK 5 - CALIBRATION CHECKPOINTS
# ============================================================================

"task05_checkpoint_1": r"""
## Checkpoint 1 - Observation Count
After loading and combining observation data:
- **How many total observation points do you have?**
""",

"task05_checkpoint_2": r"""
## Checkpoint 2 - Initial Model Fit
Before calibration, compare your simulated heads to observations:
- **What is the initial RMSE (m)?**
""",

"task05_checkpoint_3": r"""
## Checkpoint 3 - Calibrated Model Fit
After PEST++ calibration:
- **What is your calibrated RMSE (m)?**
""",

"task05_checkpoint_4": r"""
## Checkpoint 4 - Water Balance
Verify your calibrated model's water balance:
- **What is the water balance error (%)?**
""",

"task05_checkpoint_5": r"""
## Conceptual Checkpoint - Residual Interpretation
You observe that residuals in the upstream area are predominantly positive (simulated > observed).
- **What parameter adjustment would improve the fit?**
  - A) Increase K in that area
  - B) Decrease K in that area
  - C) Increase recharge everywhere
  - D) Decrease river conductance
""",

# Notebook 5 - Pumping Test checkpoints
"task05_pt_checkpoint_1": r"""
## Pumping Test — Checkpoint 1: Cooper-Jacob Slope
From your semi-log fit for OW-2:
- **What is the slope $\Delta s$ (drawdown per log cycle) in metres?**
""",

"task05_pt_checkpoint_2": r"""
## Pumping Test — Checkpoint 2: Transmissivity
Using the Cooper-Jacob formula $T = \frac{2.3\,Q}{4\pi\,\Delta s}$:
- **What is the transmissivity $T$ (m²/d) for OW-2?**
""",

"task05_pt_checkpoint_3": r"""
## Pumping Test — Checkpoint 3: Hydraulic Conductivity
Using $K = T / b$:
- **What is the hydraulic conductivity $K$ (m/d) for OW-2?**
""",

"task05_pt_checkpoint_4": r"""
## Pumping Test — Checkpoint 4: Mean K from All Wells
After running the Cooper-Jacob analysis on all 4 observation wells:
- **What is the mean $K$ (m/d) across all wells?**
""",

"task05_pt_checkpoint_5": r"""
## Pumping Test — Checkpoint 5: Consistency Check
The transmissivity estimates from the 4 wells are similar but not identical.
- **What is the most likely reason for the small differences in $T$?**
""",

# Notebook 5 - Manual trial checkpoint
"task05_checkpoint_manual": r"""
## Manual Trial — Which K Direction Improves the Fit?
You ran the model with three different K values (15, 20, 30 m/d).
- **Which K multiplier gave the lowest RMSE?**
""",

# Notebook 5 - Non-uniqueness checkpoint
"task05_checkpoint_nonunique": r"""
## Non-Uniqueness — Reducing the K–Recharge Trade-off
You saw that different K and recharge combinations can produce similar head fits.
- **What additional data type would most reduce this K–recharge non-uniqueness?**
""",

# ============================================================================
# NOTEBOOK 6 - VALIDATION CHECKPOINTS
# ============================================================================

"task06_checkpoint_1": r"""
## Checkpoint 1 — Temporal Split
We calibrated our model to time-averaged (steady-state) head observations.
- **Why can't we do a temporal train/test split for validation?**
""",

"task06_checkpoint_2": r"""
## Checkpoint 2 — Calibration RMSE at Real Wells
After loading the calibrated model and computing metrics at real AWEL wells only:
- **What is the full-calibration RMSE (m) at the 4 real wells?**
""",

"task06_checkpoint_3": r"""
## Checkpoint 3 — Water Balance Error
From the water balance summary of your calibrated model:
- **What is the water balance error (%)?**
""",

"task06_checkpoint_4": r"""
## Checkpoint 4 — Verification vs Validation
Your model passes verification (mass balance OK) and plausibility checks (K and gradients in reasonable ranges).
- **Does this mean its predictions are reliable?**
""",

"task06_checkpoint_5": r"""
## Checkpoint 5 — Synthetic Observations in LOO
In leave-one-out cross-validation, we hold out one real well per fold.
- **Should the synthetic observations also be held out?**
""",

"task06_checkpoint_6": r"""
## Checkpoint 6 — LOO-RMSE
After running 4 LOO folds and computing the prediction error at each held-out real well:
- **What is the LOO-RMSE (m)?**
""",

"task06_checkpoint_7": r"""
## Checkpoint 7 — Interpreting LOO Results
Consider a model where the LOO-RMSE is much larger than the calibration RMSE.
- **What does this suggest about the model?**
""",

# ============================================================================
# NOTEBOOK 7 - SENSITIVITY & UNCERTAINTY CHECKPOINTS
# ============================================================================

"task07_checkpoint_1": r"""
## Checkpoint 1 — Parameter Sensitivity
Looking at the CSS bar chart and map:
- **Which pilot point has the highest Composite Scaled Sensitivity?**
""",

"task07_checkpoint_2": r"""
## Checkpoint 2 — Identifiable Parameters
From the identifiability analysis:
- **How many parameters have identifiability > 0.5?**
""",

"task07_checkpoint_3": r"""
## Checkpoint 3 — Uncertainty Reduction
From the prior vs posterior uncertainty comparison:
- **Which parameter has the largest uncertainty reduction from calibration?**
""",

"task07_checkpoint_4": r"""
## Checkpoint 4 — Prediction Uncertainty
From the FOSM prediction uncertainty at the 4 real wells:
- **What is the posterior standard deviation (m) of the head prediction at well 516?**
""",

"task07_checkpoint_5": r"""
## Checkpoint 5 — FOSM vs LOO-RMSE
Compare the FOSM prediction uncertainty (mean posterior σ across real wells) with the LOO-RMSE from Notebook 6.
- **How do they compare?**
""",

"task07_checkpoint_6": r"""
## Checkpoint 6 — Data Worth
From the removed-observation importance analysis, the synthetic observations have different data worth.
- **Why is syn_005 the most valuable synthetic observation?**
""",

"task07_checkpoint_7": r"""
## Checkpoint 7 — Monitoring Recommendation
The western domain has low identifiability, low uncertainty reduction, and no observation wells.
- **What single action would most improve predictions in the data-sparse western domain?**
"""

}



#------ Dictionary to store the accepted solutions / range of sample
solutions = {
    "task01_1": (1.6, 1.8),  # Correct solution 1.7
    "task01_2": (3100000, 3200000),  # Correct solution 3153600
    "task01_3": (0.18, 0.20),  # Correct solution 1.9
    "task01_4": (1.1, 1.3),
    "task03_1": (0.15, 0.25),  # Correct solution 0.2
    "task03_2": (0.005, 0.015),  # Correct solution 0.01
    "task03_3": (0.5, 1.5), 
    "task03_4": (0.25, 0.35),  # Correct solution 0.3
    "task04_1": (43, 44),  # Correct solution 38
    "task04_2": (25, 27),  # Correct solution 26
    "task04_checkpoint_1": (100, 160),  # Correct solution ~126 million m³ (10.4 km² × ~12 m avg thickness)
    "task04_checkpoint_2": (2700, 3500),  # Correct solution ~3000 m³/day (10.4 km² × 110 mm/yr)
    "task04_checkpoint_3": (0, 0.1),  # Tolerance <0.1% - MF6 should converge to near-zero
    "task03_unit_conversion": (210, 222),  # Correct solution 216 m/d (2.5e-3 * 86400)
    "task03_conductance": (950, 1050),  # Correct solution 1000 m²/d (500 * 100 / 50)
    # task03_steady_state is multiple choice - handled separately
    # task03_riv_vs_chd is multiple choice - handled separately
    # task03_grid_choice is multiple choice - handled separately
    # Checkpoints 4, 5, and k_sensitivity are conceptual/multiple choice - handled separately
    # task04_k_values removed - simplified to uniform K
    # Notebook 5 checkpoints
    "task05_checkpoint_1": (8, 10),       # 4 real AWEL + 5 synthetic = 9 obs points
    "task05_checkpoint_2": (0.5, 6.0),    # Initial RMSE before calibration
    "task05_checkpoint_3": (0.2, 5.0),    # Calibrated RMSE after PEST++
    "task05_checkpoint_4": (0, 1.0),      # Water balance error < 1%
    # Checkpoint 5 is multiple choice - handled separately
    # Notebook 6 checkpoints
    # Checkpoint 1 is multiple choice - handled separately
    "task06_checkpoint_2": (0.2, 5.0),        # Full-calibration RMSE at real wells only
    "task06_checkpoint_3": (0, 1.0),          # Water balance error < 1%
    # Checkpoint 4 is multiple choice - handled separately
    # Checkpoint 5 is multiple choice - handled separately
    "task06_checkpoint_6": (0.3, 8.0),        # LOO-RMSE (wide range, depends on PEST++ convergence)
    # Checkpoint 7 is multiple choice - handled separately
    # Notebook 5 - Pumping Test checkpoints
    "task05_pt_checkpoint_1": (0.50, 0.62),   # Cooper-Jacob slope ~0.56 m/log-cycle
    "task05_pt_checkpoint_2": (580, 740),      # Transmissivity T ~650 m²/d
    "task05_pt_checkpoint_3": (23.0, 30.0),    # K = T/b ~26 m/d
    "task05_pt_checkpoint_4": (23.0, 30.0),    # Mean K from all 4 wells ~26 m/d
    # PT Checkpoint 5 is multiple choice - handled separately
    # Manual trial and non-uniqueness checkpoints are multiple choice - handled separately
    # Notebook 7 checkpoints
    # Checkpoint 1 is multiple choice - handled separately
    "task07_checkpoint_2": (5, 12),         # Number of params with identifiability > 0.5 (~8)
    # Checkpoint 3 is multiple choice - handled separately
    "task07_checkpoint_4": (1.0, 2.5),      # Posterior std dev at well 516 (~1.60 m)
    # Checkpoints 5, 6, 7 are multiple choice - handled separately
}



#------ Dictionary to store correct exact solution for tasks
solutions_exact = {
    "task01_1": "1.7 ",
    "task01_2": "3153600 ",
    "task01_3": "0.19 ",
    "task01_4": "1.2 ",
    "task03_1": "0.2",
    "task03_2": "0.01",
    "task03_3": "1",
    "task03_4": "0.30",
    "task04_1": "43.3",
    "task04_2": "26.0",
    "task04_checkpoint_1": "~125",
    "task04_checkpoint_2": "~3000",
    "task04_checkpoint_3": "~0.0002",
    "task04_checkpoint_4": "B) Losing",
    "task04_checkpoint_5": "Head measurements, river discharge, spring discharge",
    "task03_unit_conversion": "216",
    "task03_conductance": "1000",
    "task03_steady_state": "B) dh/dt = 0 but water still flows",
    "task03_k_averaging_1": "B) Harmonic mean",
    "task03_riv_vs_chd": "A) RIV allows head-dependent two-way exchange",
    "task03_grid_choice": "B) Voronoi (DISV)",
    "task04_checkpoint_k_sensitivity": "B) K = 5-50 m/day",
    # task04_k_values removed - simplified to uniform K
    # Notebook 5 checkpoints
    "task05_checkpoint_1": "9",
    "task05_checkpoint_2": "See output",  # Initial RMSE depends on reference K field
    "task05_checkpoint_3": "See output",  # Calibrated RMSE after PEST++
    "task05_checkpoint_4": "~0.001",
    "task05_checkpoint_5": "A) Increase K in that area",
    # Notebook 6 checkpoints
    "task06_checkpoint_1": "B) We calibrated to time-averaged heads",
    "task06_checkpoint_2": "See output",
    "task06_checkpoint_3": "~0.001",
    "task06_checkpoint_4": "C) No — plausibility confirms physics, not predictive power",
    "task06_checkpoint_5": "B) No — synthetic obs stay in all folds",
    "task06_checkpoint_6": "See output",
    "task06_checkpoint_7": "A) The model may be overfitting",
    # Notebook 5 - Pumping Test checkpoints
    "task05_pt_checkpoint_1": "~0.56",
    "task05_pt_checkpoint_2": "~650",
    "task05_pt_checkpoint_3": "~26",
    "task05_pt_checkpoint_4": "~26",
    "task05_pt_checkpoint_5": "B) Measurement noise and the Cooper-Jacob approximation",
    # Manual trial and non-uniqueness checkpoints
    "task05_checkpoint_manual": "C) K = 30 m/d (multiplier 1.5)",
    "task05_checkpoint_nonunique": "B) River baseflow measurements",
    # Notebook 7 checkpoints
    "task07_checkpoint_1": "A) The pilot point nearest the observation wells",
    "task07_checkpoint_2": "~8",
    "task07_checkpoint_3": "B) The pilot point nearest the observation well cluster",
    "task07_checkpoint_4": "~1.60",
    "task07_checkpoint_5": "B) FOSM σ is smaller — it captures only parameter uncertainty",
    "task07_checkpoint_6": "A) It fills a spatial gap",
    "task07_checkpoint_7": "B) Install an observation well in the western domain",
}



    # Dictionary to store untis for solution



#------ Dictionary to store solution unit (string) 
solution_unit = {
    "task01_1": "km^2",
    "task01_2": "m^3",
    "task01_3": "m",
    "task01_4": "km^2",
    "task03_1": "mm/s",
    "task03_2": "mm^3/s",
    "task03_3": "mm/s",
    "task03_4": "mm/s",
    "task04_1": "m",
    "task04_2": "m",
    "task04_checkpoint_1": "million m³",
    "task04_checkpoint_2": "m³/day",
    "task04_checkpoint_3": "%",
    "task04_checkpoint_4": "multiple choice",
    "task04_checkpoint_5": "open-ended",
    "task03_unit_conversion": "m/day",
    "task03_conductance": "m²/d",
    "task03_steady_state": "multiple choice",
    "task03_k_averaging_1": "multiple choice",
    "task03_riv_vs_chd": "multiple choice",
    "task03_grid_choice": "multiple choice",
    "task04_checkpoint_k_sensitivity": "multiple choice",
    # task04_k_values removed - simplified to uniform K
    # Notebook 5 checkpoints
    "task05_checkpoint_1": "points",
    "task05_checkpoint_2": "m",
    "task05_checkpoint_3": "m",
    "task05_checkpoint_4": "%",
    "task05_checkpoint_5": "multiple choice",
    # Notebook 6 checkpoints
    "task06_checkpoint_1": "multiple choice",
    "task06_checkpoint_2": "m",
    "task06_checkpoint_3": "%",
    "task06_checkpoint_4": "multiple choice",
    "task06_checkpoint_5": "multiple choice",
    "task06_checkpoint_6": "m",
    "task06_checkpoint_7": "multiple choice",
    # Notebook 5 - Pumping Test checkpoints
    "task05_pt_checkpoint_1": "m",
    "task05_pt_checkpoint_2": "m\u00b2/d",
    "task05_pt_checkpoint_3": "m/d",
    "task05_pt_checkpoint_4": "m/d",
    "task05_pt_checkpoint_5": "multiple choice",
    # Manual trial and non-uniqueness checkpoints
    "task05_checkpoint_manual": "multiple choice",
    "task05_checkpoint_nonunique": "multiple choice",
    # Notebook 7 checkpoints
    "task07_checkpoint_1": "multiple choice",
    "task07_checkpoint_2": "parameters",
    "task07_checkpoint_3": "multiple choice",
    "task07_checkpoint_4": "m",
    "task07_checkpoint_5": "multiple choice",
    "task07_checkpoint_6": "multiple choice",
    "task07_checkpoint_7": "multiple choice",
}


#------ Dictionary to store multiple choice options for conceptual checkpoints
# Format: task_id -> list of (value, label) tuples
# The 'value' is what gets compared against solutions_exact[task_id]
multiple_choice_options = {
    "task03_steady_state": [
        ("A) No water flows", "A) No water flows through the aquifer"),
        ("B) dh/dt = 0 but water still flows", "B) dh/dt = 0 but water still flows (heads constant, flow continues)"),
        ("C) K is constant", "C) Hydraulic conductivity is constant everywhere"),
        ("D) No sources or sinks", "D) There are no sources or sinks in the system"),
    ],
    "task03_k_averaging_1": [
        ("A) Arithmetic mean", "A) Arithmetic mean — gives equal weight to both K values"),
        ("B) Harmonic mean", "B) Harmonic mean — low-K layer controls flow (resistors in series)"),
        ("C) Geometric mean", "C) Geometric mean — a balanced middle ground"),
        ("D) Doesn't matter", "D) It doesn't matter — all methods give similar results at this contrast"),
    ],
    "task03_riv_vs_chd": [
        ("A) RIV allows head-dependent two-way exchange", "A) RIV allows head-dependent two-way exchange based on conductance and head difference"),
        ("B) CHD is more physically realistic", "B) CHD is more physically realistic for river boundaries"),
        ("C) RIV is computationally faster", "C) RIV is computationally faster than CHD"),
        ("D) No practical difference", "D) No practical difference between the two approaches"),
    ],
    "task03_grid_choice": [
        ("A) Structured (DIS)", "A) Structured (DIS) — uniform rows and columns"),
        ("B) Voronoi (DISV)", "B) Voronoi (DISV) — add generating points where detail is needed"),
        ("C) Both equally", "C) Both equally — both support local refinement"),
        ("D) Neither", "D) Neither — use uniform spacing everywhere"),
    ],
    "task04_checkpoint_4": [
        ("A) Gaining", "A) Gaining (river receives discharge from aquifer)"),
        ("B) Losing", "B) Losing (river loses water to aquifer)"),
        ("C) Varies", "C) Varies along reach (both gaining and losing sections)"),
    ],
    "task04_checkpoint_k_sensitivity": [
        ("A) K = 0.1-1 m/day", "A) K = 0.1-1 m/day (very low, typical of silts/clays)"),
        ("B) K = 5-50 m/day", "B) K = 5-50 m/day (matches pumping test data for alluvial gravels)"),
        ("C) K = 100-500 m/day", "C) K = 100-500 m/day (very high, clean gravel literature values)"),
        ("D) Any K works", "D) Any K value works equally well"),
    ],
    "task05_checkpoint_5": [
        ("A) Increase K in that area", "A) Increase K in that area (reduces simulated heads)"),
        ("B) Decrease K in that area", "B) Decrease K in that area (increases simulated heads)"),
        ("C) Increase recharge everywhere", "C) Increase recharge everywhere (increases all heads)"),
        ("D) Decrease river conductance", "D) Decrease river conductance (affects river-aquifer exchange)"),
    ],
    "task05_pt_checkpoint_5": [
        ("A) Aquifer heterogeneity", "A) The aquifer is heterogeneous — each well samples a different K zone"),
        ("B) Measurement noise and the Cooper-Jacob approximation", "B) Measurement noise + the Cooper-Jacob late-time approximation introduce small variability"),
        ("C) Leaky aquifer", "C) The aquifer is leaky, violating the confined-aquifer assumption"),
        ("D) Well skin effects", "D) Each well has a different skin factor that biases the slope"),
    ],
    "task05_checkpoint_manual": [
        ("A) K = 15 m/d (multiplier 0.75)", "A) K = 15 m/d — lower K raises heads"),
        ("B) K = 20 m/d (multiplier 1.0)", "B) K = 20 m/d — the baseline from Notebook 4"),
        ("C) K = 30 m/d (multiplier 1.5)", "C) K = 30 m/d — higher K lowers heads"),
    ],
    "task05_checkpoint_nonunique": [
        ("A) More head observations", "A) More head observations — better spatial coverage of the same data type"),
        ("B) River baseflow measurements", "B) River baseflow measurements — constrain the water balance independently of heads"),
        ("C) Soil type mapping", "C) Soil type mapping — better knowledge of surface geology"),
        ("D) Longer pumping tests", "D) Longer pumping tests — more accurate T estimates"),
    ],
    # Notebook 6 - Validation checkpoints
    "task06_checkpoint_1": [
        ("A) We only have 4 wells", "A) We only have 4 wells — not enough data for a split"),
        ("B) We calibrated to time-averaged heads", "B) We calibrated to time-averaged (steady-state) heads — there is no temporal dimension to split"),
        ("C) PEST++ doesn't support it", "C) PEST++ doesn't support temporal splitting"),
        ("D) Transient data is unreliable", "D) Transient head measurements are too noisy to use"),
    ],
    "task06_checkpoint_4": [
        ("A) Yes — verification proves correctness", "A) Yes — if verification and plausibility pass, the model is validated"),
        ("B) Only if RMSE < 1 m", "B) Only if the calibration RMSE is below 1 m"),
        ("C) No — plausibility confirms physics, not predictive power", "C) No — plausibility confirms physics are reasonable, but validation requires testing against independent data"),
        ("D) It depends on the model purpose", "D) It depends entirely on the intended application"),
    ],
    "task06_checkpoint_5": [
        ("A) Yes — hold out all observations", "A) Yes — hold out both real and synthetic observations for a fair test"),
        ("B) No — synthetic obs stay in all folds", "B) No — with only 3 real wells per fold, removing synthetic obs would leave the calibration wildly underdetermined"),
        ("C) Only in some folds", "C) Only in some folds — alternate between holding out real and synthetic"),
    ],
    "task06_checkpoint_7": [
        ("A) The model may be overfitting", "A) The model may be overfitting — it fits calibration data well but predicts poorly at unseen locations"),
        ("B) The observations have errors", "B) The observation data contains large measurement errors"),
        ("C) The model is underfitting", "C) The model is too simple and underfitting the data"),
        ("D) More pilot points are needed", "D) More pilot points would fix the problem"),
    ],
    # Notebook 7 - Sensitivity & Uncertainty checkpoints
    "task07_checkpoint_1": [
        ("A) The pilot point nearest the observation wells", "A) The pilot point nearest the observation wells — observations constrain nearby parameters most"),
        ("B) The pilot point farthest from boundaries", "B) The pilot point farthest from model boundaries"),
        ("C) The Sihl leakance multiplier", "C) The Sihl leakance multiplier — river parameters dominate"),
        ("D) All pilot points have equal CSS", "D) All pilot points have equal CSS — they're evenly distributed"),
    ],
    "task07_checkpoint_3": [
        ("A) The pilot point farthest from any well", "A) The pilot point farthest from any observation well"),
        ("B) The pilot point nearest the observation well cluster", "B) The pilot point nearest the observation well cluster — calibration reduces uncertainty where it has data"),
        ("C) The Sihl leakance multiplier", "C) The Sihl leakance multiplier — river parameters are most constrained"),
        ("D) All parameters reduce equally", "D) All parameters show similar uncertainty reduction"),
    ],
    "task07_checkpoint_5": [
        ("A) They are approximately equal", "A) They are approximately equal — FOSM captures the same error sources as LOO"),
        ("B) FOSM σ is smaller — it captures only parameter uncertainty", "B) FOSM σ is smaller — it captures only parameter uncertainty, while LOO-RMSE also includes structural error"),
        ("C) FOSM σ is larger — it overestimates uncertainty", "C) FOSM σ is larger — the linear assumption overestimates uncertainty"),
        ("D) They cannot be compared", "D) They cannot be compared — they measure different things entirely"),
    ],
    "task07_checkpoint_6": [
        ("A) It fills a spatial gap", "A) It fills a spatial gap — it provides unique information that no other observation covers"),
        ("B) It has the smallest residual", "B) It has the smallest calibration residual — better-fit observations are more informative"),
        ("C) It is closest to the model boundary", "C) It is closest to the model boundary — boundary conditions need the most constraint"),
        ("D) All synthetic obs are equally valuable", "D) All synthetic observations contribute equally to prediction uncertainty"),
    ],
    "task07_checkpoint_7": [
        ("A) Increase regularisation strength", "A) Increase regularisation strength — constrain parameters more tightly"),
        ("B) Install an observation well in the western domain", "B) Install an observation well in the western domain — provide data where identifiability is lowest"),
        ("C) Add more pilot points everywhere", "C) Add more pilot points — increase parameter flexibility"),
        ("D) Re-run calibration with a different algorithm", "D) Re-run calibration with a different algorithm"),
    ],
}


#------ Dictionary to store the markdown to display the correction
solutions_markdown = {

"task01_1": r"""
We must have that $ V_{in} = V_{out} $.

Water input volume over 1 day is $ V_{in} = P \times A \times t $ where:
- $ P $ is the net recharge rate in km/day, $ P = 1 \text{mm/day} = 1 \times 10^{-6} \text{km/day} $
- $ A $ is the area of the catchment in $\text{km}^2$
- $ t $ is 1 day

Water output volume over 1 day is $ V_{out} = Q \times t $ where:
- $ Q $ is the flow rate in $\text{km}^3$/day, $ Q = 20 \text{L}/\text{s} = 1728 \text{m}^3/\text{day} = 1728 \times 10^{-9} \text{km}^3/\text{day} $
- $ t $ is 1 day

So we have that $ P \times A \times t = Q \times t $

We can solve $ A = \frac{1728 \times 10^{-9}}{1 \times 10^{-6}} \simeq 1.7 \text{km}^2 $.

This is not far from the BAFU estimation of 1.58 km², as you can see on the following snapshot.
<br>
""",

"task01_2": r"""

We assume steady state conditions and an average year. The volume of water $V_{out}$ going out from the aquifer in one year $\tau$ is needed to estimate the volume of the aquifer itself $V_{aq}$. We also need to take into account the aquifer porosity. 

Overall we have that $V_{aq} = \frac{V_{out}}{\phi}$ where :
- $V_{out} = Q \times \tau = 1728 \text{m}^3/\text{day} \times 365 \text{ day} = 1728 \times 365 \text{m}^3 $
- ${\phi} = 0.2$

Finally, $V_{aq} = 1728 \times 365 \text{m}^3 / 0.2 = 3153600 \text{m}^3$
<br>
""",


"task01_3": r"""

The thickness is : $M_{aq} = \frac{V_{aq}}{A}$. $A$ being known, we still need to compute the aquifer volume $V_{aq}$.

We assume steady state conditions and an average year. The volume of water $V_{out}$ going out from the aquifer in one year $\tau$ is needed to estimate the volume of the aquifer itself $V_{aq}$. We also need to take into account the aquifer porosity. 

Overall we have that $V_{aq} = \frac{V_{out}}{\phi}$ where :
- $V_{out} = Q \times \tau = 1728 \text{m}^3/\text{day} \times 365 \text{ day} = 1728 \times 365 \text{m}^3 $
- ${\phi} = 0.2$

Finally, $V_{aq} = 1728 \times 365 \text{m}^3 / 0.2 = 3153600 \text{m}^3$

Back to the mean aquifer thickness : $M_{aq} = \frac{V_{aq}}{A} = \frac{3123600}{1.7} \frac{ \text{m}^3 }{\text{km}^2} = \frac{3123600}{1.7 \times 10^6}\text{m} \simeq 1.9 \text{m}$
<br>
""",

"task01_4": r"""

The lower bound $A_{min}$ of the area is given by the lower bound of the net recharge rate $P_{min}$ and the upper bound of the flow rate $Q_{max}$.

We have that $A_{min} = \frac{Q_{min}}{P_{max}}$.
- $P_{max} = 1.1 \text{mm/day} = 1.1 \times 10^{-6} \text{km/day}$
- $Q_{min} = 15 \text{L}/\text{s} = 1296 \text{m}^3/\text{day} = 1296 \times 10^{-9} \text{km}^3/\text{day}$
It results that $A_{min} = \frac{1296 \times 10^{-9}}{1.1 \times 10^{-6}} \simeq 1.2 \text{km}^2$.

You might want to have a look at the following interactive plot which shows all possible values of $A$ reachable given the uncertainety intervals for $P$ and $Q$.
<br>
""",

"task03_1":
r"""
According to Darcy 's law, we have that :

$q = KI = K \cdot \frac{\Delta h}{L} = 0.0005 \cdot \frac{0.4}{1} = 20 \cdot 10^{-5} \cdot\text{m}\text{s}^{-1} = 0.2 \cdot \text{mm}\text{s}^{-1}$.
<br>
""",

"task03_2":
r"""
The discharge is derived from the specific discharge, accounting for the soil column cross section area : 

$Q = q \cdot A = 
0.2 \cdot \pi \cdot r^2 \simeq 0.2 \cdot 0.051 \cdot \text{mm}^3\text{s}^{-1} = 0.01 \cdot \text{mm}^3\text{s}^{-1}$.
<br>
""",

"task03_3":
r"""
The mean velocity is derived from the specific discharge, accounting for the soil column effective porosity : 

$u = \frac{q}{\phi_e} = 
 \frac{0.2}{0.2} = 1 \cdot \text{mm}.\text{s}^{-1}$.
<br>
""",

"task03_4":
r"""
$K$ can be derived from the slope of the linear fit ( Darcy's law : $q$ = $K \cdot I$).<br>From the graph, its value is $0.30$  $\text{mm}.\text{s}^{-1}$.<br> Be careful about the units : on the graph, $q$ is given in $\text{mm}.\text{s}^{-1}$.
<br>
""",

"task04_1": r"""

The Darcy law is : q = $K \cdot I$. Let's apply it separately to each layer of the aquifer. <br> <br>
To the left, $q$ = $K_A \cdot \frac{h(100)-h(0)}{100}$. To the right, $q$ = $K_B \cdot \frac{h(200)-h(100)}{100}$ <br><br>
Both sides being equal to $q$, we can isolate $h(100)$ and reexpress it as a function of known parameters : 
$h(100) = \frac{K_A \cdot h(0) + K_B \cdot h(200)}{K_A + K_B} = 43.3$ m.
<br>
""",

"task04_2": r"""

The solution is the same as for the previous question, but plugging $x$ = 400m instead.
<br>
As a result, $h(400)$ = $-\frac{0.000003}{0.00005}(400 - 0)$ + 50 = 26.0 $\text{m}$
<br>
""",

"task04_checkpoint_1": r"""
## Solution - Aquifer Volume

The aquifer volume is calculated as:

$$V = A \times \bar{b}$$

Where:
- $A$ = model domain area ≈ 10.4 km² = 10.4 × 10⁶ m²
- $\bar{b}$ = average aquifer thickness ≈ 12 m (from the model geometry summary printed above)

$$V = 10.4 \times 10^6 \times 12 = 124.8 \times 10^6 \text{ m}^3 \approx 125 \text{ million m}^3$$

This volume represents the total aquifer material (pore space + solid matrix). The actual **groundwater storage volume** would be $V \times S_y$ where $S_y$ is the specific yield (~0.15-0.25 for gravels), giving ~19-31 million m³ of extractable water.
<br>
""",

"task04_checkpoint_2": r"""
## Solution - Total Recharge Flux

**Step-by-step calculation:**

1. Convert area: 10.4 km² = 10.4 × 10⁶ m²
2. Multiply rate × area:

$$Q_{recharge} = R_{rate} \times A_{active} = 3.01 \times 10^{-4} \text{ m/day} \times 10.4 \times 10^6 \text{ m}^2 \approx 3{,}130 \text{ m}^3\text{/day}$$

This is consistent with the perceptual model estimate from Notebook 2 (~3,000 m³/day).

**Common mistakes:**
- Forgetting to convert km² to m² (multiply by 10⁶)
- Using annual recharge without converting to daily (divide by 365.25)

**Verification:** After running the model, check the RCH package inflow in the water balance output.
<br>
""",

"task04_checkpoint_3": r"""
## Solution - Water Balance Error

MODFLOW 6 provides excellent numerical stability. The water balance error should be very small:

- **Target: < 0.1%** (excellent convergence)
- **Acceptable: < 1%** (good convergence)

The water balance error is calculated as:

$$\text{Error (\%)} = 200 \times \frac{|Q_{in} - Q_{out}|}{Q_{in} + Q_{out}}$$

This is the symmetric MODFLOW 6 standard formula ("Percent Difference" in the listing file), where $Q_{in}$ is total inflow and $Q_{out}$ is total outflow from all sources/sinks.

For your MF6 model:
- Check the summary output file for "Percent Difference"
- Verify all packages are included (WEL, RCH, RIV, etc.)
- Ensure stress periods are properly defined
- If error > 1%, check for convergence issues or missing packages
<br>
""",

"task04_checkpoint_4": r"""
## Solution - River-Aquifer Interaction

In the Hardhof area of the Limmat Valley, the Limmat River is **losing water to the aquifer**.

**Answer: B) Losing**

**In your model:** The RIV package acts as a net water source (inflow to aquifer), meaning simulated aquifer heads are generally below river stage. The river loses water to the aquifer even in the base model — you can verify this in the water balance summary (Section 7.1).

**In reality:** The losing regime is reinforced by the Hardhof pumping well field, which creates a cone of depression that draws the water table further below river level. Artificial recharge operations at Hardhof are specifically designed to infiltrate river water into the aquifer, confirming this losing condition.

When interpreting RIV package results:
- A **losing** river has river stage > aquifer head → water flows from river to aquifer
- A **gaining** river has river stage < aquifer head → groundwater discharges into the river
<br>
""",

"task04_checkpoint_5": r"""
## Solution - Model Calibration and Validation

To assess your model's predictive quality, compare simulated values to observed field data:

**Primary observations to use:**
- **Head measurements** from observation wells or boreholes at various locations and depths
- **River discharge** (baseflow) measurements at gauging stations
- **Spring discharge** data from mapped springs in the study area

**Secondary observations:**
- **Age dating** (tritium, ¹⁴C) to verify residence times
- **Water quality** parameters (temperature, major ions, isotopes) to validate flow paths
- **Seasonal variations** in water table elevation
- **Lake/pond levels** if present in the domain

**Calibration workflow:**
1. Compare simulated vs. observed heads at observation points
2. Adjust model parameters (K, recharge, boundary conditions) to minimize differences
3. Validate using independent observations not used in calibration
4. Perform sensitivity analysis to understand parameter importance
5. Assess model uncertainty through scenario analysis

The quality of your model depends heavily on the availability and accuracy of field observations.
<br>
""",

# task04_k_values solution removed - simplified to uniform K

"task03_conductance": r"""
## Solution — Conductance Calculation

$$C = K \cdot \frac{A}{L} = 500 \, \text{m/d} \cdot \frac{100 \, \text{m}^2}{50 \, \text{m}} = 500 \times 2 = 1000 \, \text{m}^2/\text{d}$$

**Interpretation:** This conductance value means that for every **1 m of head difference** between the two cells, **1000 m³/day** of water will flow across their shared face. Conductance combines the material property (K) with the geometry (face area and distance) into a single coefficient.

This same conductance concept appears in the RIV, GHB, and DRN packages — everywhere MODFLOW computes head-dependent flow.
<br>
""",

"task03_riv_vs_chd": r"""
## Solution — RIV vs. CHD

**Correct answer: A) RIV allows head-dependent two-way exchange**

The RIV package computes river-aquifer exchange based on:

$$Q_{riv} = C_{riv} \cdot (h_{riv} - h_{aquifer})$$

where $C_{riv}$ is the riverbed conductance (from the leakage coefficients estimated in Notebook 2). Water can flow **from river to aquifer** (losing stream, when $h_{riv} > h_{aquifer}$) or **from aquifer to river** (gaining stream, when $h_{aquifer} > h_{riv}$), depending on conditions.

A **CHD boundary** would force a specific head at those cells regardless of aquifer conditions — it cannot represent the physical reality where exchange depends on riverbed properties and the head gradient.

**Key insight:** The leakage coefficients from Notebook 2 translate directly to RIV conductance values, preserving the physics of the river-aquifer interaction.
<br>
""",

"task03_grid_choice": r"""
## Solution — Grid Type Selection

**Correct answer: B) Voronoi (DISV)**

Voronoi grids achieve local refinement simply by adding more **generating points** where detail is needed (near wells, rivers, or geological contacts) while keeping the rest of the domain coarser. Each cell is defined by proximity to its generating point.

**Structured grids (DIS)** cannot refine locally — making one cell smaller in a row forces the entire row to be smaller, leading to unnecessary cells and wasted computation. Note that quadtree grids, despite using quadrilateral cells, are also classified as DISV (not DIS) because their cells do not follow a regular row/column structure.

This is why we use DISV for the Limmat Valley model: we need fine resolution along the Limmat and Sihl rivers and near the Hardhof wells, but coarser cells suffice in the rest of the domain.
<br>
""",

"task03_unit_conversion": r"""
## Solution — Unit Conversion

$$K = 2.5 \times 10^{-3} \text{ m/s} \times 86{,}400 \text{ s/day} = 216 \text{ m/day}$$

The conversion factor from m/s to m/day is **86,400** (the number of seconds in a day: 60 × 60 × 24).

**Common pitfall:** Forgetting this conversion when entering literature values (often in m/s) into a MODFLOW model using m/day units. Always check the units of your input data!
<br>
""",

"task03_steady_state": r"""
## Solution — Steady State

**Correct answer: B) dh/dt = 0 but water still flows**

Steady state means the **time derivative of head is zero** — heads are not changing over time. However, water still flows through the system! Recharge enters, wells pump, rivers exchange water — all these fluxes are in balance so that no net change in storage occurs.

Think of it like a bathtub with the tap on and the drain open: if the water level is constant, the system is at steady state even though water is continuously flowing through.

The governing equation simplifies from:
$$\nabla \cdot (K \nabla h) + W = S_s \frac{\partial h}{\partial t}$$
to:
$$\nabla \cdot (K \nabla h) + W = 0$$
<br>
""",

"task03_k_averaging_1": r"""
## Solution — K Averaging for Layered Flow

**Correct answer: B) Harmonic mean**

The harmonic mean is correct because water must flow **through** both layers in sequence — like resistors in series, the lowest-K layer controls the overall flow rate.

At this contrast (K ratio = 30 / 0.1 = 300×), the choice matters enormously:

| Method | $K_{eff}$ (m/d) |
|--------|-----------------|
| Harmonic | 0.2 |
| Geometric | 1.7 |
| Logarithmic | 5.2 |
| Arithmetic | 15.1 |

Using the arithmetic mean instead of harmonic would overestimate flow by a factor of ~75×. This is why MODFLOW 6 uses the harmonic mean as the default in the NPF package for inter-cell conductance.

**Physical insight:** For flow perpendicular to layering (series flow), the least permeable layer acts as the bottleneck — just like the narrowest pipe segment limits total flow. This principle applies whenever water must pass through a low-K barrier, such as a streambed overlying an aquifer.
<br>
""",

"task04_checkpoint_k_sensitivity": r"""
## Solution - K Sensitivity

**Correct answer: B) K = 5-50 m/day**

This range matches pumping test data for the Limmat Valley alluvial gravels and produces physically reasonable simulations.

**What happens at the extremes:**
- **K too low (< 1 m/day):** The aquifer cannot transmit enough water to the CHD outflow. Heads build up excessively — water "backs up" behind the low-K material, potentially exceeding the land surface or creating unrealistic mounding.
- **K too high (> 100 m/day):** The aquifer drains too efficiently. Heads drop to near the river/CHD levels, the aquifer may partially dewater (dry cells), and lateral gradients become unrealistically flat.
- **K = 5-50 m/day:** Heads remain below the land surface, above the aquifer bottom, and show a realistic west-to-east gradient consistent with the valley topography and boundary conditions.

**Key insight:** The "right" K is not just a material property — it must be consistent with the boundary conditions and recharge rates to produce a balanced water budget with realistic heads. This is why calibration against observed heads (Notebook 5) is essential.
<br>
""",

# ============================================================================
# NOTEBOOK 5 - CALIBRATION SOLUTIONS
# ============================================================================

"task05_checkpoint_1": r"""
## Solution - Observation Count

The observation dataset combines two sources:

1. **Real AWEL observations**: 4 monitoring wells within the model domain
   - Well 516 (Wiedikon/Letzigraben)
   - Well 3601 (Aussersihl/Zweierplatz)
   - Well 83-1
   - Well 3625 (Lagerstrasse)

2. **Synthetic observations**: 5 artificial points added for teaching purposes
   - Generated from a reference model with thickness-dependent K and realistic noise (σ = 1.3 m)
   - Restricted to the aquifer south of the river, away from model boundaries
   - Clearly marked as synthetic in all visualizations

**Total: 4 real + 5 synthetic = 9 observation points**

The synthetic observations come from a reference K field that varies with aquifer thickness (deeper zones = coarser gravels = higher K). This produces head patterns more realistic than a uniform-K model.
<br>
""",

"task05_checkpoint_2": r"""
## Solution - Initial RMSE

The initial Root Mean Square Error (RMSE) measures how well the uncalibrated model (uniform K = 20 m/d) matches the observations.

$$\text{RMSE} = \sqrt{\frac{1}{n}\sum_{i=1}^{n}(h_{sim,i} - h_{obs,i})^2}$$

The misfit occurs because:
- The synthetic observations come from a reference model with spatially varying K (12–90 m/d depending on aquifer thickness)
- The uniform K = 20 model produces different head patterns wherever the true K deviates significantly

This initial misfit motivates the calibration — the model needs spatially varying K to match the observations.
<br>
""",

"task05_checkpoint_3": r"""
## Solution - Calibrated RMSE

After PEST++ calibration with pilot points, the RMSE should improve over the uncalibrated value.

**Why is the improvement modest?** With only 9 observations (4 real + 5 noisy synthetic) and 20 pilot points, the inverse problem is severely underdetermined. The regularization and prior information help constrain the solution, but there simply isn't enough observation data to fully recover the spatially varying K field. This is typical for real-world calibration problems and illustrates why observation network design matters.

**Key takeaway:** Calibration quality is limited by observation data coverage. More wells distributed across the domain would dramatically improve the result.
<br>
""",

"task05_checkpoint_4": r"""
## Solution - Water Balance Error

MODFLOW 6 should achieve excellent water balance closure. The error should be **< 1%**, typically around **0.001%** or less.

The water balance error is:

$$\text{Error (\%)} = 200 \times \frac{|Q_{in} - Q_{out}|}{Q_{in} + Q_{out}}$$

**If your error is > 1%:**
1. Check solver convergence (IMS settings)
2. Verify all boundary conditions are correctly specified
3. Ensure the model is running to completion
4. Check for excessively dry cells

A well-converged steady-state model should have near-zero balance error.
<br>
""",

"task05_checkpoint_5": r"""
## Solution - Residual Interpretation

**Correct answer: A) Increase K in that area**

**Reasoning:**
- Positive residuals mean simulated heads are **higher** than observed
- Higher heads occur when water cannot drain away fast enough
- Increasing K allows water to flow more easily, lowering heads

**Physical interpretation:**
- Simulated head = f(recharge/K) — higher K means lower equilibrium head
- If sim > obs, the aquifer is "mounding" too much → increase K to let water escape

**What the other options would do:**
- B) Decrease K → Would raise heads further (wrong direction)
- C) Increase recharge → Would raise heads everywhere (wrong direction)
- D) Decrease river conductance → Would affect river exchange but not systematically lower heads in the upstream area

This principle is key to calibration: use residual patterns to guide parameter adjustments in the correct direction. With pilot points, PEST++ does this automatically by adjusting K at each point.
<br>
""",

# ============================================================================
# NOTEBOOK 5 - PUMPING TEST SOLUTIONS
# ============================================================================

"task05_pt_checkpoint_1": r"""
## Solution — Cooper-Jacob Slope

The slope $\Delta s$ is the drawdown change per log$_{10}$ cycle on the semi-log plot. The `cooper_jacob_fit` function performs this regression automatically on the late-time data.

From the Theis solution with $T$ = 650 m²/d and $Q$ = 2000 m³/d:

$$\Delta s = \frac{2.3\,Q}{4\pi\,T} = \frac{2.3 \times 2000}{4\pi \times 650} \approx 0.56 \text{ m}$$

The fitted value may differ slightly due to measurement noise.
<br>
""",

"task05_pt_checkpoint_2": r"""
## Solution — Transmissivity

Rearranging the Cooper-Jacob slope equation:

$$T = \frac{2.3\,Q}{4\pi\,\Delta s} = \frac{2.3 \times 2000}{4\pi \times 0.56} \approx 654 \text{ m}^2\text{/d}$$

**Common mistakes:**
- Forgetting the 2.3 factor → $T \approx 284$ (too low by ~2.3×)
- Using $2\pi$ instead of $4\pi$ → $T \approx 1310$ (too high by 2×)
- Omitting $\pi$ entirely → $T \approx 2050$ (too high by ~$\pi$×)
<br>
""",

"task05_pt_checkpoint_3": r"""
## Solution — Hydraulic Conductivity

$$K = \frac{T}{b} = \frac{654}{25} \approx 26 \text{ m/d}$$

This is somewhat higher than the uniform K = 20 m/d used in Notebook 4, suggesting the aquifer at the pumping test site is more permeable than the domain average.

**Common mistake:** Reporting $T$ instead of $K$ (off by a factor of $b$ = 25).
<br>
""",

"task05_pt_checkpoint_4": r"""
## Solution — Mean K from All Wells

All four wells should give similar $T$ (and thus $K$) values because the Cooper-Jacob slope depends only on $Q$ and $T$, not on distance $r$. The mean K $\approx$ 26 m/d confirms this consistency.

Small differences arise from measurement noise and the fact that the Cooper-Jacob approximation is not exact at early times (which affects the fit window selection differently for each well).
<br>
""",

"task05_pt_checkpoint_5": r"""
## Solution — Why T Varies Across Wells

**Correct answer: B) Measurement noise and the Cooper-Jacob approximation**

The pumping test data is generated from a **homogeneous** Theis solution with added noise. The small $T$ differences come from:

1. **Measurement noise** — pressure transducers have finite precision ($\sigma \approx$ 0.02–0.03 m)
2. **Fit-window selection** — each well's late-time regime starts at a different time, affecting which data points are included in the regression
3. **Cooper-Jacob approximation** — the straight-line assumption ($u < 0.01$) is better satisfied at larger times and closer distances

**Why not A (heterogeneity)?** In a real aquifer, heterogeneity would cause $T$ variations, but here the spread is small (~5%) and consistent with noise alone.

**Why not C (leaky)?** Leakage would cause the semi-log plot to curve and flatten at late times — not simply shift the slope.

**Why not D (skin)?** Well skin affects early-time data but not the late-time slope that Cooper-Jacob uses.
<br>
""",

# ============================================================================
# NOTEBOOK 5 - MANUAL TRIAL & NON-UNIQUENESS SOLUTIONS
# ============================================================================

"task05_checkpoint_manual": r"""
## Solution — Which K Direction Improves the Fit?

**Correct answer: C) K = 30 m/d (multiplier 1.5)**

**Reasoning:**
- The reference K field (used to generate synthetic observations) has higher K values in many areas than the uniform 20 m/d baseline
- Increasing K lowers simulated heads, which better matches observations in areas where the baseline overpredicts
- The RMSE decreases when moving from 20 → 30 m/d, confirming that the baseline K is too low on average

This is exactly the intuition that automated calibration (PEST++) formalises: it adjusts parameters in the direction that reduces the objective function.
<br>
""",

"task05_checkpoint_nonunique": r"""
## Solution — Reducing K–Recharge Non-Uniqueness

**Correct answer: B) River baseflow measurements**

**Reasoning:**
- Head observations alone cannot distinguish between K and recharge because both affect the water table height (higher recharge ≈ lower K → similar heads)
- **River baseflow** constrains the **water balance** independently: it tells you how much water leaves the aquifer via the river, which depends differently on K and recharge
- With both head and flux observations, the K–recharge trade-off is broken because each parameter combination produces a different flux even if heads are similar

**Why not the other options?**
- A) More head observations improve spatial coverage but don't break the K–recharge trade-off
- C) Soil mapping gives qualitative constraints but doesn't quantitatively constrain the water balance
- D) Longer pumping tests improve local T estimates but don't constrain recharge
<br>
""",

# ============================================================================
# NOTEBOOK 6 - VALIDATION SOLUTIONS
# ============================================================================

"task06_checkpoint_1": r"""
## Solution — Temporal Split

**Correct answer: B) We calibrated to time-averaged heads**

Our steady-state model was calibrated to **long-term mean** head values — there is no time series to split into calibration and validation periods. A temporal train/test split requires transient data (e.g., calibrate on 2010–2015, validate on 2016–2020).

**Why not the other options?**
- A) While 4 wells is few, temporal splitting is about time periods, not well count
- C) PEST++ fully supports temporal splitting for transient models
- D) Transient data quality is not the issue — the issue is that we don't use transient data at all

**Key insight:** For steady-state models, validation must rely on **spatial** approaches (hold-out wells, cross-validation) or **independent data types** (flux measurements, tracer tests).
<br>
""",

"task06_checkpoint_2": r"""
## Solution — Calibration RMSE at Real Wells

This RMSE measures how well the **full calibration** (using all 9 observations) reproduces heads at the 4 real AWEL wells. It provides the baseline "best-case" fit — the LOO-RMSE will typically be larger because each fold uses fewer constraints.

The exact value depends on the PEST++ calibration outcome.
<br>
""",

"task06_checkpoint_3": r"""
## Solution — Water Balance Error

MODFLOW 6 should achieve near-perfect water balance closure for a well-converged steady-state model. The error should be **< 1%**, typically around **0.001%** or less.

$$\text{Error (\%)} = 200 \times \frac{|Q_{in} - Q_{out}|}{Q_{in} + Q_{out}}$$

This is a **verification** check (mathematical correctness), not a validation check (predictive capability).
<br>
""",

"task06_checkpoint_4": r"""
## Solution — Verification vs Validation

**Correct answer: C) No — plausibility confirms physics are reasonable, but validation requires testing against independent data**

Verification (mass balance) confirms the **equations are solved correctly**. Plausibility checks confirm the **physics are reasonable**. But neither tells us whether the model can **predict at locations it hasn't seen**.

A model can pass both checks and still be:
- Overfitting to calibration data
- Missing important geological features
- Unreliable outside the calibrated area

**Only validation against independent data** (data not used in calibration) can test predictive capability.
<br>
""",

"task06_checkpoint_5": r"""
## Solution — Synthetic Observations in LOO

**Correct answer: B) No — synthetic obs stay in all folds**

With only 3 real wells remaining per fold (one is held out), the pilot-point calibration would be **wildly underdetermined** without the 5 synthetic observations providing spatial coverage.

The synthetic observations serve as spatial constraints that prevent the calibration from producing physically unreasonable K fields. The LOO test is **exclusively on real data** — we only compute prediction errors at held-out real wells.

This is a pragmatic compromise: we test predictive skill at real locations while maintaining calibration stability.
<br>
""",

"task06_checkpoint_6": r"""
## Solution — LOO-RMSE

$$\text{LOO-RMSE} = \sqrt{\frac{1}{N}\sum_{i=1}^{N} e_i^2}$$

where $e_i = h_{predicted}(\text{calibrated without } i) - h_{observed,i}$ and $N = 4$ (one per real well).

The LOO-RMSE is typically **larger** than the calibration RMSE because each fold predicts at a location that was not used for parameter estimation. The exact value depends on PEST++ convergence in each fold.

**Interpretation:**
- LOO-RMSE ≈ calibration RMSE → model generalises well
- LOO-RMSE >> calibration RMSE → possible overfitting
<br>
""",

"task06_checkpoint_7": r"""
## Solution — Interpreting LOO Results

**Correct answer: A) The model may be overfitting**

When LOO-RMSE >> calibration RMSE, it means the model fits the calibration data much better than it predicts at unseen locations. This is the classic signature of **overfitting**: the calibration found parameter values that work well for the specific observations used, but those values don't generalise.

**Why not the other options?**
- B) Observation errors would affect both calibration and LOO equally
- C) Underfitting would show poor calibration RMSE too, not just poor LOO-RMSE
- D) More pilot points could actually make overfitting worse by increasing model flexibility

**Remedies for overfitting:** Stronger regularisation, fewer pilot points, more observations, independent data constraints.
<br>
""",

# ============================================================================
# NOTEBOOK 7 - SENSITIVITY & UNCERTAINTY SOLUTIONS
# ============================================================================

"task07_checkpoint_1": r"""
## Solution — Parameter Sensitivity

**Correct answer: A) The pilot point nearest the observation wells**

Composite Scaled Sensitivity (CSS) measures how much each parameter affects the observations, weighted by observation weights and parameter scale. Pilot points near the 4 real AWEL wells and 5 synthetic observations naturally have the highest CSS because:

1. The Jacobian elements $\partial h_i / \partial p_j$ are largest when observation $i$ and parameter $j$ are close
2. Hydraulic conductivity changes have a local effect — they primarily affect heads in the surrounding area
3. Distant pilot points produce negligible head changes at the observation locations

**Key insight:** High CSS does not mean the parameter is "important" in general — it means the *current observation network* can detect changes in that parameter. A parameter in the data-sparse west might be physically critical but have low CSS because no observations can see it.
<br>
""",

"task07_checkpoint_2": r"""
## Solution — Identifiable Parameters

The number of parameters with identifiability > 0.5 depends on the Jacobian structure. With 9 observations and 21 parameters, at most 9 singular values can carry information — most parameters will be in or near the null space.

Identifiability analysis uses SVD to decompose the parameter space:
- **Solution space** (identifiability → 1): combinations that observations can resolve
- **Null space** (identifiability → 0): combinations invisible to observations

The severely underdetermined nature of our problem (21 parameters, 9 observations) means most parameters cannot be uniquely determined — this is why regularisation and prior information are essential in calibration.
<br>
""",

"task07_checkpoint_3": r"""
## Solution — Uncertainty Reduction

**Correct answer: B) The pilot point nearest the observation well cluster**

Calibration can only reduce uncertainty where it has data. The pilot points clustered near the 4 AWEL wells (eastern domain) show the largest decrease in posterior standard deviation because:

1. Multiple observations constrain the K values in that area
2. The Jacobian entries are large for nearby parameter–observation pairs
3. The Schur complement subtracts the information matrix from the prior covariance

Pilot points in the western domain show minimal uncertainty reduction — calibration barely "touches" them because no observations provide constraining information.

**Practical implication:** Our model's predictions in the western domain carry essentially the same uncertainty as before calibration.
<br>
""",

"task07_checkpoint_4": r"""
## Solution — Prediction Uncertainty

The posterior standard deviation at well 516 comes from the FOSM (Schur complement) analysis, which propagates parameter uncertainty through the Jacobian to give prediction uncertainty.

The exact value depends on the PEST++ calibration outcome. The posterior σ is typically smaller than the prior σ because calibration reduced parameter uncertainty — but it's not zero because:
1. Parameters are not perfectly determined (underdetermined problem)
2. Multiple parameter combinations can produce similar heads (non-uniqueness)
3. The observation network has limited spatial coverage

**Important caveat:** FOSM captures only *parameter uncertainty* under a *linear approximation*. The actual prediction error (LOO-RMSE) is typically larger because it also includes model structural error and nonlinear effects.
<br>
""",

"task07_checkpoint_5": r"""
## Solution — FOSM vs LOO-RMSE

**Correct answer: B) FOSM σ is smaller — it captures only parameter uncertainty**

FOSM and LOO-RMSE both estimate prediction error, but from different perspectives:

| Method | Captures | Assumes |
|--------|----------|---------|
| **FOSM** | Parameter uncertainty only | Linear model, correct structure |
| **LOO-RMSE** | Parameter + structural + nonlinear error | Nothing (empirical) |

FOSM is typically an *underestimate* of total prediction error because it ignores:
- Model structural error (wrong K zonation, missing processes)
- Nonlinear effects (the Jacobian is a local linear approximation)
- Observation noise effects on calibration

When LOO-RMSE >> FOSM σ, the gap is dominated by **structural error** — improving the model structure (more layers, transient, better boundaries) would help more than collecting more head observations.
<br>
""",

"task07_checkpoint_6": r"""
## Solution — Data Worth

**Correct answer: A) It fills a spatial gap**

syn_005 is the most valuable synthetic observation because removing it causes the largest increase in prediction variance across all 4 real-well forecasts. This happens because syn_005 occupies a unique spatial position — it provides information about parameter values in an area that no other observation covers.

When an observation fills a spatial gap:
1. Its Jacobian row constrains parameter combinations that no other observation can
2. Removing it leaves those parameters entirely in the null space
3. The resulting uncertainty increase propagates to all predictions

Observations clustered near other data points have lower data worth because neighbouring observations provide redundant (overlapping) information.

**Practical use:** Data worth analysis helps plan monitoring networks. Observations that fill spatial gaps provide the most new information per well drilled.
<br>
""",

"task07_checkpoint_7": r"""
## Solution — Monitoring Recommendation

**Correct answer: B) Install an observation well in the western domain**

The western domain has:
- **Low CSS** — no observations can detect parameter changes there
- **Low identifiability** — parameters are in the null space
- **Low uncertainty reduction** — calibration didn't help there
- **No observations at all** — it's a data void

Installing a well there would:
1. Move western pilot points out of the null space into the solution space
2. Provide direct constraint on K values in the data-sparse area
3. Dramatically reduce prediction uncertainty for that part of the domain

**Why not the other options?**
- A) More regularisation constrains parameters but doesn't add information
- C) More pilot points would make the problem even more underdetermined
- D) A different algorithm cannot extract information that isn't in the data
<br>
"""

}


# Dictionary to map tasks to Python functions to execute with the solution
task_functions = {
    "task01_1": lambda: du.display_image(image_filename='SwissTopoTsaletArea.png', image_folder='3_exercises'),
    "task01_4": lambda: display_disc_area_interactive(),
    "task04_1": lambda: draw_hx_plot(),

}

# Dictionary to map tasks to Python functions to execute before the question
task_functions_start = {
    "task04_1": lambda: draw_schematic_interface()

}