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

# ============================================================================
# EXERCISES THEORY
# ============================================================================

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
## Task 1.4
Different soils can have different hydraulic conductivity. 
We refill the same Darcy experiment setup's column with mixed deposits of hydraulic conductivity **$K_{T}$=0.0005 $\text{m}\text{s}^{-1}$**,
and effective porosity **$\phi_e$=0.2**. 
We now observe that $\Delta h=0.4$ m.

**What is your estimate of the specific discharge $q$ in mm/s?**
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
## Task 2.2
You are given a 200 m long confined aquifer, composed of two successive layers of different hydraulic conductivities.
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
You ran the model with three different K values (150, 200, 300 m/d).
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
""",

# ============================================================================
# NOTEBOOK 8 - MODEL APPLICATION CHECKPOINTS
# ============================================================================

"task08_checkpoint_1": r"""
## Checkpoint 1 — Scenario Design
Our Limmat Valley model is steady-state, single-layer, with spatially varying K calibrated via PEST++.
- **Can this model predict how quickly a new well reaches its maximum drawdown?**
""",

"task08_checkpoint_2": r"""
## Checkpoint 2 — Maximum Drawdown
After running the pumping well scenario (-500 m³/d):
- **What is the maximum drawdown (m) at the well cell?**
""",

"task08_checkpoint_3": r"""
## Checkpoint 3 — Water Source
Comparing the baseline and pumping-well water balances:
- **Where does the pumped water primarily come from?**
""",

"task08_checkpoint_4": r"""
## Checkpoint 4 — Linearity
You doubled the pumping rate from -500 to -1000 m³/d. The maximum drawdown also approximately doubled.
- **Why does drawdown scale linearly with pumping rate in this model?**
""",

"task08_checkpoint_5": r"""
## Checkpoint 5 — Protection Zone Classification
The 10-day isochrone extends upstream of the well. A dairy farm with manure storage sits inside the 10-day isochrone.
- **Under Swiss regulations, which protection zone does the farm fall in?**
""",

"task08_checkpoint_6": r"""
## Checkpoint 6 — Non-Stationarity
We delineated protection zones from a single steady-state simulation.
- **Why should protection zones not be based on a single steady-state model run?**
""",

"task08_checkpoint_7": r"""
## Checkpoint 7 — Drought Impact
After reducing recharge by 30% (climate drought scenario):
- **What is the mean head decline (m) across the active domain?**
""",

"task08_checkpoint_8": r"""
## Checkpoint 8 — Capture Zone Under Drought
You re-ran PRT (particle tracking) under the reduced-recharge scenario.
- **How does the capture zone of the pumping well change under drought conditions?**
""",

# Transport Track — Notebook 2: Perceptual Model
"task_t02_checkpoint_1": r"""
## Checkpoint 1 — Seepage Velocity
Given:
- Hydraulic conductivity $K = 864$ m/d
- Hydraulic gradient $i = 0.0026$
- Effective porosity $n_e = 0.20$

**Calculate the seepage velocity $v$ in m/day.**
""",

"task_t02_checkpoint_2": r"""
## Checkpoint 2 — Thermal Retardation Factor
Given:
- Effective porosity $n_e = 0.25$
- Solid density $\rho_s = 2650$ kg/m³
- Solid heat capacity $c_s = 880$ J/(kg·K)
- Water density $\rho_w = 1000$ kg/m³
- Water heat capacity $c_w = 4184$ J/(kg·K)

The thermal retardation factor is:

$$R = \frac{n_e \cdot \rho_w \cdot c_w + (1 - n_e) \cdot \rho_s \cdot c_s}{n_e \cdot \rho_w \cdot c_w}$$

**Calculate $R$.**
""",

"task_t02_checkpoint_pe": r"""
## Checkpoint — Grid Peclet Number
Given:
- Seepage velocity $v = 2.5 \times 10^{-5}$ m/s
- Longitudinal dispersivity $\alpha_L = 10$ m
- Grid cell size $\Delta x = 100$ m

The grid Peclet number is defined as:

$$Pe_{grid} = \frac{v \cdot \Delta x}{D_L}$$

where $D_L = \alpha_L \cdot v + D_m^* \approx \alpha_L \cdot v$ (molecular diffusion negligible).

**Calculate $Pe_{grid}$.**
""",

"task_t02_checkpoint_3": r"""
## Checkpoint 3 — Thermal Well Distribution
Based on the concession map you just generated:
- **How are thermal groundwater concessions (WPG/KW) distributed in the model area?**
""",

"task_t02_checkpoint_4": r"""
## Checkpoint 4 — Dominant Thermal Input
Based on the thermal energy budget:
- **Which flux component contributes the most thermal energy (warming) to the Limmat Valley aquifer?**
""",

# Transport Track — Notebook 3: MODFLOW for Heat Transport
"task_t03_checkpoint_1": r"""
## Checkpoint 1 — ADE Comprehension
In the advection-dispersion equation:
- **Which process moves the solute/heat front at the groundwater velocity?**
""",

"task_t03_checkpoint_2": r"""
## Checkpoint 2 — Grid Peclet Number
Given a longitudinal dispersivity $\alpha_L = 15$ m:
- **What is the maximum cell size $\Delta x$ (in metres) to satisfy $Pe_{grid} \leq 2$?**

**Hint:** $\Delta x \leq 2 \alpha_L$ when molecular diffusion is negligible.
""",

"task_t03_checkpoint_3": r"""
## Checkpoint 3 — Package Identification
In a MODFLOW 6 GWE model:
- **Which package computes thermal retardation from porosity, density, and heat capacity?**
""",

# ============================================================================
# TRANSPORT NOTEBOOK 4 - HEAT TRANSPORT MODEL IMPLEMENTATION CHECKPOINTS
# ============================================================================

"task_t04_checkpoint_1": r"""
## Checkpoint 1 — Thermal Retardation Factor
Given:
- Effective porosity $n_e = 0.20$
- Solid density $\rho_s = 2650$ kg/m³
- Solid heat capacity $c_s = 880$ J/(kg·K)
- Water density $\rho_w = 1000$ kg/m³
- Water heat capacity $c_w = 4184$ J/(kg·K)

$$R = \frac{n_e \cdot \rho_w \cdot c_w + (1 - n_e) \cdot \rho_s \cdot c_s}{n_e \cdot \rho_w \cdot c_w}$$

**Calculate the thermal retardation factor $R$.**
""",

"task_t04_checkpoint_2": r"""
## Checkpoint 2 — Courant Number
Given:
- Seepage velocity $v = 11$ m/d
- Time step $\Delta t = 5$ days
- Cell size $\Delta x = 25$ m

$$Cr = \frac{v \cdot \Delta t}{\Delta x}$$

**Calculate the Courant number.**
""",

"task_t04_checkpoint_3": r"""
## Checkpoint 3 — Dominant Thermal Input
Considering the boundary conditions of your heat transport model:
- **Which boundary introduces the most thermal energy anomaly to the aquifer?**
""",

"task_t04_checkpoint_4": r"""
## Checkpoint 4 — Summer Aquifer Temperature
After running the transient heat transport simulation:
- **What is the mean aquifer temperature (°C) in the last summer (July) snapshot?**
""",

"task_t04_checkpoint_5": r"""
## Checkpoint 5 — Energy Budget
From the GWE energy budget:
- **Which component dominates energy input to the aquifer?**
""",

"task_t04_checkpoint_seasonal": r"""
## Checkpoint — Seasonal Signal
Looking at the temperature time series plot at your monitoring points:
- **How does the seasonal temperature amplitude change with distance from the river?**
""",

"task_t04_checkpoint_alpha": r"""
## Checkpoint — Dispersivity Sensitivity
You increased the longitudinal dispersivity $\alpha_L$ from 10 m to 50 m:
- **How does increasing $\alpha_L$ affect the thermal plume?**
""",

# ── Transport Track — Notebook 5 checkpoints ──

"task_t05_checkpoint_1": r"""
## Checkpoint 1 — Monitoring Network
Looking at the synthetic temperature observation network:
- **How many monitoring wells are there?**
""",

"task_t05_checkpoint_2": r"""
## Checkpoint 2 — Initial Temperature RMSE
Using the NB4 default parameters ($\alpha_L = 10$ m, $n_e = 0.20$):
- **What is the overall temperature RMSE (°C) when comparing simulated to observed time series?**
""",

"task_t05_tt_checkpoint_1": r"""
## Checkpoint — Tracer Test Velocity
From the moment analysis of MW-1 (at $x = 50$ m):

$$\bar{t} = \frac{M_1}{M_0}, \quad v = \frac{x}{\bar{t}}$$

- **What is the estimated seepage velocity (m/d)?**
""",

"task_t05_tt_checkpoint_2": r"""
## Checkpoint — Tracer Test Dispersivity
From the moment analysis of MW-1:

$$\sigma_t^2 = \frac{M_2}{M_0} - \bar{t}^2, \quad \sigma_x^2 = v^2 \cdot \sigma_t^2, \quad \alpha_L = \frac{\sigma_x^2}{2x}$$

- **What is the estimated longitudinal dispersivity $\alpha_L$ (m)?**
""",

"task_t05_tt_checkpoint_3": r"""
## Checkpoint — Dispersivity Variation
The moment analysis shows $\alpha_L$ varies slightly from well to well:
- **Why does the estimated $\alpha_L$ differ between observation wells?**
""",

"task_t05_checkpoint_best_alpha": r"""
## Checkpoint — Best Dispersivity
Looking at the calibration sweep results:
- **Which $\alpha_L$ value gave the best (lowest) temperature RMSE?**
""",

"task_t05_checkpoint_3": r"""
## Checkpoint — Calibrated Temperature RMSE
After calibrating with the best $\alpha_L$ from the sweep:
- **What is the calibrated overall temperature RMSE (°C)?**
""",

"task_t05_checkpoint_4": r"""
## Checkpoint — Energy Balance
From the GWE energy budget of the calibrated model:
- **What is the energy balance error (%)?**
""",

"task_t05_checkpoint_nonunique": r"""
## Checkpoint — Non-Uniqueness
You tested trade-off combinations that give similar temperature RMSE:
- **What independent measurement breaks the $\alpha_L$–$n_e$ trade-off?**
""",

"task_t05_checkpoint_transfer": r"""
## Checkpoint — Heat to Solute Transfer
When transferring calibrated parameters from a heat transport model to a solute transport model:
- **Which parameter does NOT transfer directly?**
""",

"task_exercise_flow_net_1": r"""
## Task 1
Compute the hydraulic head at point A (in meter)
""",

"task_exercise_flow_net_2": r"""
## Task 2
Compute the pressure gradient (in kPa/m) of pore water between Points B and C which are at the same elevation.
""",

"task_exercise_flow_net_3": r"""
## Task 3
Compute the groundwater discharge of unit aquifer width (in $cm^3$/s) in the Box D which has a dimension of 10 m by 10 m.
""",

"task_exercise_darcy_further_application_and_use_1": r"""

A highly permeable detritus layer overlies a sandstone aquifer.

Assume $K_{detritus} >> K_{sandstone}$

The sandstone aquifer has:
- horizontal impermeable bottom at z = 0 m
- top elevation z_top = 10 m
- porosity n = 0.22

Groundwater flows from Point C toward a spring at Point A.

Known data:
- $h_C$ = 12.0 m
- $h_A$ = 0.1 m
- $q_A$ = 1.0 10⁻⁴ m/s
- $L_{AC}$ = 1000 m

The aquifer is:
- unconfined between C and B
- confined between B and A

Assume:
- steady-state conditions
- one-dimensional horizontal flow
- unit width
- no recharge between C and A

## Task 3.1
    
Using Darcy's law:
- **Determine the specific discharge $q_B$, at the vertical Profile B**
""",

"task_exercise_darcy_further_application_and_use_2": r"""
## Task 3.2
Given the Dupuit assumption that specific discharge, $q_B$, at vertical Profile B is calculated as,
$q_B=K\left(h_B^2-h_A^2\right)/\left(2L_{AB}h_B\right)$, where $K$ is the hydraulic conductivity of the sandstone aquifer:
- **Determine the distance $L_{AB}$**
""",

"pumping_test_1": r"""
## Task 1
- **Determine the transmissivity of the aquifer using Jacob's approximation to the Theiss solution** (give the result in $m^2/s$ with 4 decimals)
""",

"pumping_test_2": r"""
## Task 2
- **Determine the storativity of the aquifer, again using Jacob's approximation to the Theiss solution** (give the result with 5 decimals)
""",


"K_increase_sandstone_1": r"""
- If $h_A$ and $q_A$ are fixed, where would B shift?
""",

"K_increase_sandstone_2": r"""
- If $q_A$ and B location are maintained, what happens to $h_A$?
""",

"K_increase_sandstone_3": r"""
- If B location and $h_A$ are fixed, how would $q_A$ change?
""",

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
    "task05_pt_checkpoint_1": (0.15, 0.22),   # Cooper-Jacob slope ~0.18 m/log-cycle
    "task05_pt_checkpoint_2": (2600, 3500),    # Transmissivity T ~3000 m²/d
    "task05_pt_checkpoint_3": (260, 350),      # K = T/b ~300 m/d
    "task05_pt_checkpoint_4": (260, 350),      # Mean K from all 4 wells ~300 m/d
    # PT Checkpoint 5 is multiple choice - handled separately
    # Manual trial and non-uniqueness checkpoints are multiple choice - handled separately
    # Notebook 7 checkpoints
    # Checkpoint 1 is multiple choice - handled separately
    "task07_checkpoint_2": (5, 12),         # Number of params with identifiability > 0.5 (~8)
    # Checkpoint 3 is multiple choice - handled separately
    "task07_checkpoint_4": (1.0, 2.5),      # Posterior std dev at well 516 (~1.60 m)
    # Checkpoints 5, 6, 7 are multiple choice - handled separately
    # Notebook 8 checkpoints
    "task08_checkpoint_2": (1.0, 4.0),      # Max drawdown at well cell (~2.3 m)
    "task08_checkpoint_7": (0.05, 0.5),    # Mean head decline under 30% recharge reduction (~0.18 m)
    # Checkpoints 1, 3, 4, 5, 6, 8 are multiple choice - handled separately
    # Transport Track — Notebook 2 checkpoints
    "task_t02_checkpoint_1": (10.0, 12.5),  # Correct solution 11.2 m/d (864 * 0.0026 / 0.20)
    "task_t02_checkpoint_2": (2.5, 2.9),    # Correct solution 2.67
    "task_t02_checkpoint_pe": (9.0, 11.0),  # Correct solution 10.0 (Δx/α_L = 100/10)
    # task_t02_checkpoint_3 is multiple choice - handled separately
    # task_t02_checkpoint_4 is multiple choice - handled separately
    # Transport Track — Notebook 3 checkpoints
    "task_t03_checkpoint_2": (28, 32),      # Correct solution 30 m (2 * 15)
    # task_t03_checkpoint_1 is multiple choice - handled separately
    # task_t03_checkpoint_3 is multiple choice - handled separately
    # Transport Track — Notebook 4 checkpoints
    "task_t04_checkpoint_1": (3.0, 3.5),    # Correct solution 3.23 (n_e=0.20)
    "task_t04_checkpoint_2": (2.0, 2.5),    # Correct solution 2.2 (11*5/25)
    "task_t04_checkpoint_4": (10.5, 13.5),  # Mean aquifer temperature in summer 2023
    # task_t04_checkpoint_3 is multiple choice - handled separately
    # task_t04_checkpoint_5 is multiple choice - handled separately
    # task_t04_checkpoint_alpha is multiple choice - handled separately
    # task_t04_checkpoint_seasonal is multiple choice - handled separately
    # Transport Track — Notebook 5 checkpoints
    "task_t05_checkpoint_1": (4, 6),        # 5 monitoring wells
    "task_t05_checkpoint_2": (0.1, 1.5),    # Initial RMSE with default params
    "task_t05_tt_checkpoint_1": (10.0, 14.0),  # Velocity at MW-1 ~12.3 m/d
    "task_t05_tt_checkpoint_2": (3.0, 7.0),    # alpha_L at MW-1 ~4.6 m
    # task_t05_tt_checkpoint_3 is multiple choice - handled separately
    # task_t05_checkpoint_best_alpha is multiple choice - handled separately
    "task_t05_checkpoint_3": (0.01, 1.0),   # Calibrated RMSE
    "task_t05_checkpoint_4": (0, 1.0),      # Energy balance error < 1%
    # task_t05_checkpoint_nonunique is multiple choice - handled separately
    # task_t05_checkpoint_transfer is multiple choice - handled separately
    "task_exercise_flow_net_1": (20, 22), 
    "task_exercise_flow_net_2": (-2.2, -1.8), 
    "task_exercise_flow_net_3": (90, 110), 
    "task_exercise_darcy_further_application_and_use_1": (9.9,10.1), 
    "task_exercise_darcy_further_application_and_use_2": (710,718), 
    "pumping_test_1": (0.01,0.02), 
    "pumping_test_2": (0.0001, 0.0003), 
    # "K_increase_sandstone_1" mcq- handled separately
    # "K_increase_sandstone_2" mcp- handled separately
    # "K_increase_sandstone_3" mcq- handled separately
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
    "task05_pt_checkpoint_1": "~0.18",
    "task05_pt_checkpoint_2": "~3000",
    "task05_pt_checkpoint_3": "~300",
    "task05_pt_checkpoint_4": "~300",
    "task05_pt_checkpoint_5": "B) Measurement noise and the Cooper-Jacob approximation",
    # Manual trial and non-uniqueness checkpoints
    "task05_checkpoint_manual": "C) K = 300 m/d (multiplier 1.5)",
    "task05_checkpoint_nonunique": "B) River baseflow measurements",
    # Notebook 7 checkpoints
    "task07_checkpoint_1": "A) The pilot point nearest the observation wells",
    "task07_checkpoint_2": "~8",
    "task07_checkpoint_3": "B) The pilot point nearest the observation well cluster",
    "task07_checkpoint_4": "~1.60",
    "task07_checkpoint_5": "B) FOSM σ is smaller — it captures only parameter uncertainty",
    "task07_checkpoint_6": "A) It fills a spatial gap",
    "task07_checkpoint_7": "B) Install an observation well in the western domain",
    # Notebook 8 checkpoints
    "task08_checkpoint_1": "A) No — a steady-state model cannot predict transient drawdown evolution",
    "task08_checkpoint_2": "See output",
    "task08_checkpoint_3": "B) Increased river leakage into the aquifer",
    "task08_checkpoint_4": "A) The steady-state flow equation is linear in head",
    "task08_checkpoint_5": "B) S2 (Engere Schutzzone)",
    "task08_checkpoint_6": "C) Capture zones vary seasonally and with parameter uncertainty",
    "task08_checkpoint_7": "See output",
    "task08_checkpoint_8": "A) The capture zone expands",
    # Transport Track — Notebook 2 checkpoints
    "task_t02_checkpoint_1": "11.2",
    "task_t02_checkpoint_2": "2.67",
    "task_t02_checkpoint_pe": "10.0",
    "task_t02_checkpoint_3": "B) Concentrated in the city centre",
    "task_t02_checkpoint_4": "B) River Limmat / Hardhof recharge",
    # Transport Track — Notebook 3 checkpoints
    "task_t03_checkpoint_1": "B) Advection",
    "task_t03_checkpoint_2": "30",
    "task_t03_checkpoint_3": "B) EST",
    # Transport Track — Notebook 4 checkpoints
    "task_t04_checkpoint_1": "3.23",
    "task_t04_checkpoint_2": "2.2",
    "task_t04_checkpoint_3": "B) River Limmat",
    "task_t04_checkpoint_4": "See output",
    "task_t04_checkpoint_5": "C) SSM-RIV",
    "task_t04_checkpoint_alpha": "B) Wider and more diffuse",
    "task_t04_checkpoint_seasonal": "A) Decreases with distance",
    # Transport Track — Notebook 5 checkpoints
    "task_t05_checkpoint_1": "5",
    "task_t05_checkpoint_2": "See output",
    "task_t05_tt_checkpoint_1": "~12.3",
    "task_t05_tt_checkpoint_2": "~4.6",
    "task_t05_tt_checkpoint_3": "B) Measurement noise and scale dependence",
    "task_t05_checkpoint_best_alpha": "B) alpha_L = 5 m",
    "task_t05_checkpoint_3": "See output",
    "task_t05_checkpoint_4": "~0.001",
    "task_t05_checkpoint_nonunique": "B) The tracer test constrains n_e independently",
    "task_t05_checkpoint_transfer": "C) Thermal retardation factor",
    "task_exercise_flow_net_1": "21",
    "task_exercise_flow_net_2": "-2",
    "task_exercise_flow_net_3": "100",
    "task_exercise_darcy_further_application_and_use_1": "10", 
    "task_exercise_darcy_further_application_and_use_2": "714", 
    "pumping_test_1": "0.0142", 
    "pumping_test_2": "0.000211", 
    "K_increase_sandstone_1": "A) shift of B towards A",
    "K_increase_sandstone_2": "B) $h_A$ increase",
    "K_increase_sandstone_3": "B) $q_A$ increase",
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
    # Notebook 8 checkpoints
    "task08_checkpoint_1": "multiple choice",
    "task08_checkpoint_2": "m",
    "task08_checkpoint_3": "multiple choice",
    "task08_checkpoint_4": "multiple choice",
    "task08_checkpoint_5": "multiple choice",
    "task08_checkpoint_6": "multiple choice",
    "task08_checkpoint_7": "m",
    "task08_checkpoint_8": "multiple choice",
    # Transport Track — Notebook 2 checkpoints
    "task_t02_checkpoint_1": "m/d",
    "task_t02_checkpoint_2": "—",
    "task_t02_checkpoint_pe": "—",
    "task_t02_checkpoint_3": "multiple choice",
    "task_t02_checkpoint_4": "multiple choice",
    # Transport Track — Notebook 3 checkpoints
    "task_t03_checkpoint_1": "multiple choice",
    "task_t03_checkpoint_2": "m",
    "task_t03_checkpoint_3": "multiple choice",
    # Transport Track — Notebook 4 checkpoints
    "task_t04_checkpoint_1": "—",
    "task_t04_checkpoint_2": "—",
    "task_t04_checkpoint_3": "multiple choice",
    "task_t04_checkpoint_4": "°C",
    "task_t04_checkpoint_5": "multiple choice",
    "task_t04_checkpoint_alpha": "multiple choice",
    "task_t04_checkpoint_seasonal": "multiple choice",
    # Transport Track — Notebook 5 checkpoints
    "task_t05_checkpoint_1": "wells",
    "task_t05_checkpoint_2": "°C",
    "task_t05_tt_checkpoint_1": "m/d",
    "task_t05_tt_checkpoint_2": "m",
    "task_t05_tt_checkpoint_3": "multiple choice",
    "task_t05_checkpoint_best_alpha": "multiple choice",
    "task_t05_checkpoint_3": "°C",
    "task_t05_checkpoint_4": "%",
    "task_t05_checkpoint_nonunique": "multiple choice",
    "task_t05_checkpoint_transfer": "multiple choice",
    # Exercises implemented in notebooks from theory
    "task_exercise_flow_net_1": " m",
    "task_exercise_flow_net_2": " kPa/m",
    "task_exercise_flow_net_3": " cm^3/s",
    "task_exercise_darcy_further_application_and_use_1": "m", 
    "task_exercise_darcy_further_application_and_use_2": "m", 
    "pumping_test_1": "m^2/s", 
    "pumping_test_2": "", 
    "K_increase_sandstone_1": "multiple choice",
    "K_increase_sandstone_2": "multiple choice",
    "K_increase_sandstone_3": "multiple choice",
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
        ("A) K = 150 m/d (multiplier 0.75)", "A) K = 150 m/d — lower K raises heads"),
        ("B) K = 200 m/d (multiplier 1.0)", "B) K = 200 m/d — the baseline from Notebook 4"),
        ("C) K = 300 m/d (multiplier 1.5)", "C) K = 300 m/d — higher K lowers heads"),
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
    # Notebook 8 - Model Application checkpoints
    "task08_checkpoint_1": [
        ("A) No — a steady-state model cannot predict transient drawdown evolution", "A) No — steady-state gives only the final equilibrium drawdown, not how quickly it develops"),
        ("B) Yes — if K is well-calibrated", "B) Yes — accurate K values are sufficient for predicting response times"),
        ("C) Only if the well is near an observation point", "C) Only near validated locations"),
        ("D) Yes — MODFLOW 6 handles this automatically", "D) Yes — the solver handles transient effects internally"),
    ],
    "task08_checkpoint_3": [
        ("A) Reduced lateral inflow from the valley margins", "A) Reduced lateral inflow from the valley margins"),
        ("B) Increased river leakage into the aquifer", "B) Increased river leakage into the aquifer — drawdown lowers heads below river stage, inducing more infiltration"),
        ("C) Decreased recharge from the surface", "C) Recharge decreases in response to pumping"),
        ("D) The water comes from storage depletion", "D) Storage depletion — the aquifer releases water from storage"),
    ],
    "task08_checkpoint_4": [
        ("A) The steady-state flow equation is linear in head", "A) The steady-state flow equation is linear in head — doubling the pumping rate doubles the drawdown everywhere"),
        ("B) The aquifer is homogeneous", "B) The aquifer is homogeneous — heterogeneous aquifers would not behave linearly"),
        ("C) The river boundary absorbs the extra pumping", "C) The river boundary absorbs extra stress, preventing nonlinearity"),
        ("D) Linearity only holds near the well", "D) Linearity is a coincidence that only holds near the well cell"),
    ],
    "task08_checkpoint_5": [
        ("A) S1 (Fassungsbereich)", "A) S1 — the immediate well area (typically 10 m radius)"),
        ("B) S2 (Engere Schutzzone)", "B) S2 — inside the 10-day travel time isochrone, where hazardous substance restrictions apply"),
        ("C) S3 (Weitere Schutzzone)", "C) S3 — within the full capture zone but outside the 10-day isochrone"),
        ("D) Outside all protection zones", "D) Outside all protection zones — no restrictions apply"),
    ],
    "task08_checkpoint_6": [
        ("A) The model hasn't been validated in this area", "A) The model hasn't been validated near the well — predictions are unreliable"),
        ("B) Steady-state overestimates drawdown", "B) Steady-state always overestimates drawdown, so zones are too conservative already"),
        ("C) Capture zones vary seasonally and with parameter uncertainty", "C) Capture zones vary seasonally and with parameter uncertainty — a single run may underestimate zone extent during dry periods"),
        ("D) Protection zones are defined by law, not by models", "D) Swiss law defines fixed distances, so models are unnecessary"),
    ],
    "task08_checkpoint_8": [
        ("A) The capture zone expands", "A) It expands — lower hydraulic gradients mean the well draws water from a larger area"),
        ("B) The capture zone shrinks", "B) It shrinks — lower water table means less water is available"),
        ("C) The capture zone stays the same", "C) It stays the same — the pumping rate hasn't changed"),
        ("D) The capture zone shifts laterally", "D) It shifts to one side due to asymmetric recharge reduction"),
    ],
    # Transport Track — Notebook 2 checkpoints
    "task_t02_checkpoint_3": [
        ("A) Uniformly distributed", "A) Uniformly distributed across the model area"),
        ("B) Concentrated in the city centre", "B) Concentrated in the city centre — high heating/cooling demand in urban core"),
        ("C) Along the river banks only", "C) Along the river banks only — close to the recharge source"),
        ("D) In the western outskirts", "D) In the western outskirts — industrial zone"),
    ],
    "task_t02_checkpoint_4": [
        ("A) Areal recharge", "A) Areal recharge — largest area but low temperature anomaly"),
        ("B) River Limmat / Hardhof recharge", "B) River Limmat / Hardhof recharge — large flux at +2 °C above background"),
        ("C) River Sihl infiltration", "C) River Sihl infiltration — alpine water close to background temperature"),
        ("D) Lateral inflow from hills", "D) Lateral inflow from hills — at background temperature"),
    ],
    # Transport Track — Notebook 3 checkpoints
    "task_t03_checkpoint_1": [
        ("A) Dispersion", "A) Dispersion — spreading due to velocity variations and diffusion"),
        ("B) Advection", "B) Advection — bulk movement with the flowing groundwater"),
        ("C) Conduction", "C) Conduction — heat transfer through the solid matrix"),
        ("D) Retardation", "D) Retardation — slowing of the front due to solid-phase storage"),
    ],
    "task_t03_checkpoint_3": [
        ("A) CND", "A) CND — handles conduction and mechanical dispersion"),
        ("B) EST", "B) EST — Energy Storage and Transfer: porosity, density, heat capacity"),
        ("C) ADV", "C) ADV — handles the advection scheme selection"),
        ("D) SSM", "D) SSM — Source-Sink Mixing: assigns temperatures to GWF fluxes"),
    ],
    # Transport Track — Notebook 4 checkpoints
    "task_t04_checkpoint_3": [
        ("A) Areal recharge", "A) Areal recharge — largest area but small temperature anomaly (9.8 °C)"),
        ("B) River Limmat", "B) River Limmat — large flux at 12.5 °C, 2 °C above background"),
        ("C) River Sihl", "C) River Sihl — moderate flux at near-background temperature (11.1 °C)"),
        ("D) Lateral inflow", "D) Lateral inflow — at background temperature (10.5 °C)"),
    ],
    "task_t04_checkpoint_5": [
        ("A) SSM-WEL", "A) SSM-WEL — lateral inflow wells carry heat into the domain"),
        ("B) SSM-RCHA", "B) SSM-RCHA — areal recharge spreads heat across the entire surface"),
        ("C) SSM-RIV", "C) SSM-RIV — river-aquifer exchange is the dominant heat source"),
        ("D) CND", "D) CND — conduction through the solid matrix dominates"),
    ],
    "task_t04_checkpoint_alpha": [
        ("A) Narrower and sharper", "A) Narrower and sharper — higher dispersivity focuses the plume"),
        ("B) Wider and more diffuse", "B) Wider and more diffuse — higher dispersivity spreads heat over a larger area"),
        ("C) No significant change", "C) No significant change — dispersivity has little effect on temperature"),
        ("D) Higher peak temperature", "D) Higher peak temperature — more dispersion concentrates energy"),
    ],
    "task_t04_checkpoint_seasonal": [
        ("A) Decreases with distance", "A) Decreases with distance — thermal retardation and dispersion attenuate the signal"),
        ("B) Increases with distance", "B) Increases with distance — the aquifer amplifies the seasonal signal"),
        ("C) Stays constant", "C) Stays constant — the seasonal signal propagates unchanged"),
        ("D) Inverts with distance", "D) Inverts with distance — summer becomes winter and vice versa"),
    ],
    # Transport Track — Notebook 5 checkpoints
    "task_t05_tt_checkpoint_3": [
        ("A) Aquifer heterogeneity", "A) The aquifer is heterogeneous — each well samples a different dispersivity zone"),
        ("B) Measurement noise and scale dependence", "B) Measurement noise + dispersivity tends to increase with transport distance (scale dependence)"),
        ("C) The tracer decayed", "C) The tracer decayed differently at each well"),
        ("D) All wells should give identical values", "D) All wells should give identical values — any difference is an error"),
    ],
    "task_t05_checkpoint_best_alpha": [
        ("A) alpha_L = 3 m", "A) alpha_L = 3 m — under-dispersive, seasonal amplitude too large"),
        ("B) alpha_L = 5 m", "B) alpha_L = 5 m — matches tracer test estimate, best RMSE"),
        ("C) alpha_L = 10 m", "C) alpha_L = 10 m — the NB4 default, over-damps the signal"),
    ],
    "task_t05_checkpoint_nonunique": [
        ("A) More temperature observations", "A) More temperature observations — better spatial coverage of the same data type"),
        ("B) The tracer test constrains n_e independently", "B) The tracer test constrains n_e independently — moment analysis gives v and n_e from a single BTC"),
        ("C) Longer simulation time", "C) Longer simulation time — let the model reach steady-state"),
        ("D) Higher-resolution grid", "D) Higher-resolution grid — better numerical accuracy"),
    ],
    "task_t05_checkpoint_transfer": [
        ("A) Longitudinal dispersivity", "A) Longitudinal dispersivity alpha_L — mechanical dispersion is identical for heat and solute"),
        ("B) Effective porosity", "B) Effective porosity n_e — same pore space carries heat and solute"),
        ("C) Thermal retardation factor", "C) Thermal retardation factor — replace with sorption retardation for solutes"),
        ("D) Transverse dispersivity", "D) Transverse dispersivity alpha_T — mechanical dispersion is identical"),
    ],

    "K_increase_sandstone_1": [
        ("A) shift of B towards A", "A) shift of B towards A"),
        ("B) shift of B towards C", "B) shift of B towards C"),
    ],
    "K_increase_sandstone_2": [
        ("A) $h_A$ decreases", "A) decreases"),
        ("B) $h_A$ increase", "B) increases"),
    ],
    "K_increase_sandstone_3": [
        ("A) $q_A$ decreases", "A) decreases"),
        ("B) $q_A$ increase", "B) increases"),
    ],

}


#------ Dictionary to store the markdown to display the correction
solutions_markdown = {

"task01_1": r"""
At a steady state, we must have that $ V_{in} = V_{out} $.
We know from the Task 1 that the only inflow is from precipitation and the only outflow is to the river.

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

From the Theis solution with $T$ = 3000 m²/d and $Q$ = 3000 m³/d:

$$\Delta s = \frac{2.3\,Q}{4\pi\,T} = \frac{2.3 \times 3000}{4\pi \times 3000} \approx 0.18 \text{ m}$$

The fitted value may differ slightly due to measurement noise.
<br>
""",

"task05_pt_checkpoint_2": r"""
## Solution — Transmissivity

Rearranging the Cooper-Jacob slope equation:

$$T = \frac{2.3\,Q}{4\pi\,\Delta s} = \frac{2.3 \times 3000}{4\pi \times 0.18} \approx 3050 \text{ m}^2\text{/d}$$

**Common mistakes:**
- Forgetting the 2.3 factor → $T \approx 1330$ (too low by ~2.3×)
- Using $2\pi$ instead of $4\pi$ → $T \approx 6100$ (too high by 2×)
- Omitting $\pi$ entirely → $T \approx 9600$ (too high by ~$\pi$×)
<br>
""",

"task05_pt_checkpoint_3": r"""
## Solution — Hydraulic Conductivity

$$K = \frac{T}{b} = \frac{3000}{10} \approx 300 \text{ m/d}$$

This is higher than the uniform K = 200 m/d used in Notebook 4, suggesting the aquifer at the pumping test site is more permeable than the assumed domain average — consistent with coarse gravels in the central alluvial valley.

**Common mistake:** Reporting $T$ instead of $K$ (off by a factor of $b$ = 25).
<br>
""",

"task05_pt_checkpoint_4": r"""
## Solution — Mean K from All Wells

All four wells should give similar $T$ (and thus $K$) values because the Cooper-Jacob slope depends only on $Q$ and $T$, not on distance $r$. The mean K $\approx$ 300 m/d confirms this consistency.

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

**Correct answer: C) K = 300 m/d (multiplier 1.5)**

**Reasoning:**
- The reference K field (used to generate synthetic observations) has higher K values in many areas than the uniform 200 m/d baseline
- Increasing K lowers simulated heads, which better matches observations in areas where the baseline overpredicts
- The RMSE decreases when moving from 200 → 300 m/d, confirming that the baseline K is too low on average

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
""",

# ============================================================================
# NOTEBOOK 8 - MODEL APPLICATION SOLUTIONS
# ============================================================================

"task08_checkpoint_1": r"""
## Solution — Scenario Design

**Correct answer: A) No — a steady-state model cannot predict transient drawdown evolution**

A steady-state model computes the **equilibrium** (final) head distribution — the state after all transients have died out. It cannot tell you:
- How quickly drawdown develops after pumping starts
- How long recovery takes after pumping stops
- Whether maximum drawdown is reached in days, weeks, or months

To predict **timing**, you need a **transient model** with storage parameters ($S_s$ or $S_y$).

**What our model *can* predict:** The final (long-term) drawdown under sustained pumping — useful for assessing steady-state impacts but not short-term dynamics.

**Key insight:** Always match your model's temporal capabilities to the question being asked. "How much drawdown?" is a steady-state question; "How fast does drawdown develop?" is a transient question.
<br>
""",

"task08_checkpoint_2": r"""
## Solution — Maximum Drawdown

The maximum drawdown occurs at the well cell itself. The exact value depends on:
- The **local K** at the well location (from the calibrated pilot-point field)
- The **aquifer thickness** at that location
- The **proximity to river boundaries** (which limit drawdown by providing induced recharge)
- The **cell size** (DISV cell area controls the effective well radius)

For a pumping rate of -500 m³/d in an alluvial gravel aquifer with T ≈ 200–400 m²/d, typical drawdown at the well cell is on the order of **0.5–2 m**.

**Quick analytical check** (Thiem equation for confined steady-state radial flow):

$$s = \frac{Q}{2\pi T} \ln\left(\frac{R}{r_w}\right)$$

With Q = 500 m³/d, T = 300 m²/d, R = 1000 m, $r_w$ = 50 m (effective cell radius):

$$s \approx \frac{500}{2\pi \times 300} \ln(20) \approx 0.27 \times 3.0 \approx 0.8 \text{ m}$$
<br>
""",

"task08_checkpoint_3": r"""
## Solution — Water Source

**Correct answer: B) Increased river leakage into the aquifer**

In the Limmat Valley, the river is the dominant hydraulic boundary. When a pumping well lowers the water table:
1. The head difference between river stage and aquifer head **increases**
2. This drives more water from the river into the aquifer (induced recharge)
3. The river effectively supplies the pumped water

You can verify this by comparing the RIV inflow between baseline and pumping scenarios — the increase in RIV inflow should approximately equal the pumping rate.

**Why not the other options?**
- A) Lateral inflow is from CHD boundaries — their flux changes somewhat but is not the primary source
- C) Recharge is specified and doesn't change with pumping
- D) There is no storage in a steady-state model ($\partial h / \partial t = 0$)

**Key insight:** In steady state, all pumped water must come from increased inflow or decreased outflow at boundaries. The boundary with the most responsive head-dependent flux (RIV) dominates.
<br>
""",

"task08_checkpoint_4": r"""
## Solution — Linearity

**Correct answer: A) The steady-state flow equation is linear in head**

The steady-state groundwater flow equation for a confined aquifer is:

$$\nabla \cdot (T \nabla h) + W = 0$$

This is a **linear** equation in $h$. If you double the source term $W$ (pumping rate), the head change (drawdown) exactly doubles everywhere. This is the **superposition principle**.

**Important caveats:**
- Linearity holds exactly for **confined** aquifers where $T$ is constant
- For **unconfined** aquifers, $T = K \times h$ depends on head, making the equation nonlinear
- In our single-layer model, if drawdown is small relative to saturated thickness, the system behaves approximately linearly
- Near boundaries where cells might go dry, linearity breaks down

**Practical use:** Linearity means you can compute drawdown for any pumping rate by scaling — no need to rerun the model for each rate.
<br>
""",

"task08_checkpoint_5": r"""
## Solution — Protection Zone Classification

**Correct answer: B) S2 (Engere Schutzzone)**

The Swiss protection zone system (GSchV Art. 29):

| Zone | Definition | Farm at 150 m upstream? |
|------|-----------|------------------------|
| **S1** | ~10 m around well | No (too far) |
| **S2** | 10-day travel time isochrone | **Yes** — inside the 10-day isochrone |
| **S3** | Full capture zone | Also yes, but S2 takes precedence |

Since the farm (150 m) is inside the 10-day isochrone (200 m), it falls within **S2**. This means:
- No storage of liquid hazardous substances (including manure lagoons)
- Restrictions on agricultural practices
- The farm would need to modify or relocate its manure storage

**Key insight:** The 10-day isochrone is the critical boundary for practical land-use decisions. Computing it accurately — including uncertainty — has real regulatory and economic consequences.
<br>
""",

"task08_checkpoint_6": r"""
## Solution — Non-Stationarity

**Correct answer: C) Capture zones vary seasonally and with parameter uncertainty**

A single steady-state model gives **one** snapshot of the capture zone under average conditions. In reality:

1. **Seasonal variation:** During summer low-flow periods, river recharge decreases and regional gradients change, potentially enlarging the capture zone. During winter high-flow, the capture zone may shrink.

2. **Parameter uncertainty:** From NB7 (FOSM), we know that K is uncertain — especially in the western domain. Different plausible K fields produce different capture zones. An ensemble of K realisations (e.g., from PEST++ IES) would give a **probabilistic** capture zone boundary.

3. **Regulatory implication:** Swiss guidelines recommend basing protection zones on the **most conservative** (largest) capture zone, typically the dry-season scenario or the upper bound of a Monte Carlo ensemble.

**Why not the other options?**
- A) Validation status affects confidence but doesn't explain why one run is insufficient
- B) Steady-state doesn't systematically overestimate — it may underestimate during droughts
- D) Swiss law uses model-based delineation for S2 and S3; only S1 is defined by fixed distance
<br>
""",

"task08_checkpoint_7": r"""
## Solution — Drought Impact

Reducing recharge by 30% simulates a sustained drought. The mean head decline depends on:
- The fraction of total inflow from recharge vs river boundaries
- How much the river compensates (increased losing or reduced gaining)
- The spatial distribution of recharge and active cells

The exact value comes from computing the difference between baseline and drought heads across all active cells.

**Physical interpretation:** The head decline is modest because river boundaries are head-dependent — as aquifer heads drop, the river provides more water, partially buffering the recharge loss. This illustrates the self-regulating nature of connected surface water–groundwater systems.
<br>
""",

"task08_checkpoint_8": r"""
## Solution — Capture Zone Under Drought

**Correct answer: A) The capture zone expands**

Under reduced recharge:
1. The regional hydraulic gradient **decreases** (flatter water table)
2. Ambient groundwater velocity **decreases** ($v = Ki/n_e$)
3. The well must therefore draw water from a **larger area** to capture the same volume
4. The capture zone boundary moves **outward** (wider and longer)

This is exactly the non-stationarity effect discussed in Section 3: the drought-scenario capture zone is larger than the average-conditions zone.

**Regulatory implication:** Protection zones based on dry-season conditions are more conservative (larger) than those based on average conditions. Swiss practice typically requires the more conservative delineation.

**Analytical check:** The maximum half-width of the capture zone is $y_{max} = Q / (2Ti)$. If the gradient $i$ decreases under drought, $y_{max}$ increases.
<br>
""",

# Transport Track — Notebook 2: Perceptual Model
"task_t02_checkpoint_1": r"""
## Solution — Seepage Velocity

The seepage velocity is:

$$v = \frac{K \cdot i}{n_e} = \frac{864 \times 0.0026}{0.20} = \frac{2.246}{0.20} = 11.2 \text{ m/d}$$

This is the average linear velocity of groundwater — the speed at which a conservative tracer (or thermal front, before retardation) would move through the aquifer.

Note: the specific discharge $q = Ki = 2.25$ m/d is the flux per unit area. Dividing by porosity converts from flux to velocity because water only moves through the pore space, not through the solid grains.
<br>
""",

"task_t02_checkpoint_2": r"""
## Solution — Thermal Retardation Factor

The bulk volumetric heat capacity is:

$$(\rho c)_{bulk} = n_e \cdot \rho_w \cdot c_w + (1 - n_e) \cdot \rho_s \cdot c_s$$
$$= 0.25 \times 1000 \times 4184 + 0.75 \times 2650 \times 880$$
$$= 1\,046\,000 + 1\,749\,000 = 2\,795\,000 \text{ J/(m}^3 \cdot \text{K)}$$

The thermal retardation factor is:

$$R = \frac{(\rho c)_{bulk}}{n_e \cdot \rho_w \cdot c_w} = \frac{2\,795\,000}{0.25 \times 1000 \times 4184} = \frac{2\,795\,000}{1\,046\,000} = 2.67$$

A thermal front moves 2.67× slower than the groundwater velocity. Higher porosity → lower $R$ because more of the bulk volume is water (which carries the heat) and less is solid (which stores it).
<br>
""",

"task_t02_checkpoint_pe": r"""
## Solution — Grid Peclet Number

Since molecular diffusion is negligible ($D_m^* \ll \alpha_L v$), the hydrodynamic dispersion coefficient simplifies to:

$$D_L \approx \alpha_L \cdot v = 10 \times 2.5 \times 10^{-5} = 2.5 \times 10^{-4} \text{ m}^2/\text{s}$$

The grid Peclet number is:

$$Pe_{grid} = \frac{v \cdot \Delta x}{D_L} = \frac{v \cdot \Delta x}{\alpha_L \cdot v} = \frac{\Delta x}{\alpha_L} = \frac{100}{10} = 10$$

Note that when $D_m^*$ is negligible, the velocity cancels and $Pe_{grid}$ reduces to the simple ratio $\Delta x / \alpha_L$. This is well above the classical stability limit of 2, so a TVD advection scheme is needed.
<br>
""",

"task_t02_checkpoint_3": r"""
## Solution — Thermal Well Distribution

**Correct answer: B) Concentrated in the city centre**

The map shows that thermal groundwater concessions (WPG = heat pumps, KW = cooling water) are clustered in Zurich's city centre (districts 1–5). This reflects:

1. **High heating and cooling demand** in dense urban areas (offices, commercial buildings)
2. **Favourable aquifer conditions** — the Limmat Valley gravel aquifer is productive and accessible
3. **Proximity to the Limmat** — river filtrate provides a large, renewable thermal resource

This concentration creates a cumulative urban heat island effect in the aquifer that is part of the background thermal state we model.
<br>
""",

"task_t02_checkpoint_4": r"""
## Solution — Dominant Thermal Input

**Correct answer: B) River Limmat / Hardhof recharge**

The energy budget analysis shows that the Limmat / Hardhof recharge is the dominant thermal input because it combines:

1. **Large volumetric flux**: ~7.7 × 10⁶ m³/yr (the largest single inflow)
2. **Significant temperature anomaly**: +2.0 °C above background (12.5 vs. 10.5 °C)

The thermal power anomaly $\Phi = \rho_w c_w Q \Delta T$ is proportional to both the flux and the temperature difference. While areal recharge covers a large area, its temperature anomaly is small (−0.7 °C) and its total flux is modest. The Sihl contributes a moderate flux but at near-background temperature (+0.1 °C).

The Limmat's elevated temperature comes from Lake Zurich (thermal buffering) and urban heat inputs.
<br>
""",

# Transport Track — Notebook 3: MODFLOW for Heat Transport
"task_t03_checkpoint_1": r"""
## Solution — ADE Comprehension

**Correct answer: B) Advection**

Advection is the process that transports solute or heat at the groundwater velocity $\mathbf{v}$. In the ADE:

$$\frac{\partial (nC)}{\partial t} = \nabla \cdot (n \mathbf{D} \nabla C) - \nabla \cdot (n \mathbf{v} C) + q_s$$

The advection term $\nabla \cdot (n \mathbf{v} C)$ moves the concentration front bodily with the flow. Dispersion spreads the front around its mean position but does not control the front velocity. Conduction (heat only) and retardation modify the effective front speed but are separate from the advective process itself.
<br>
""",

"task_t03_checkpoint_2": r"""
## Solution — Grid Peclet Number

The grid Peclet criterion requires:

$$Pe_{grid} = \frac{v \cdot \Delta x}{D_L} \leq 2$$

When molecular diffusion is negligible, $D_L \approx \alpha_L \cdot v$, so:

$$\Delta x \leq \frac{2 \cdot D_L}{v} = \frac{2 \cdot \alpha_L \cdot v}{v} = 2 \cdot \alpha_L = 2 \times 15 = 30 \text{ m}$$

This means cells must be no larger than 30 m in the flow direction. Note that this constraint depends only on dispersivity, not on velocity — a useful simplification for grid design.
<br>
""",

"task_t03_checkpoint_3": r"""
## Solution — Package Identification

**Correct answer: B) EST**

The **EST** (Energy Storage and Transfer) package computes thermal retardation from:

$$R = \frac{n_e \cdot \rho_w \cdot c_w + (1-n_e) \cdot \rho_s \cdot c_s}{n_e \cdot \rho_w \cdot c_w}$$

It requires porosity ($n_e$), solid density ($\rho_s$), and solid heat capacity ($c_s$) as inputs. CND handles conduction and dispersion, ADV handles the advection scheme, and SSM assigns temperatures to GWF fluxes — none of these compute retardation.
<br>
""",

# Transport Track — Notebook 4: Heat Transport Model Implementation

"task_t04_checkpoint_1": r"""
## Solution — Thermal Retardation Factor

With $n_e = 0.20$ (the value used throughout the transport track):

$$(\rho c)_{bulk} = n_e \cdot \rho_w \cdot c_w + (1-n_e) \cdot \rho_s \cdot c_s$$
$$= 0.20 \times 1000 \times 4184 + 0.80 \times 2650 \times 880$$
$$= 836\,800 + 1\,865\,600 = 2\,702\,400 \text{ J/(m}^3 \cdot \text{K)}$$

$$R = \frac{(\rho c)_{bulk}}{n_e \cdot \rho_w \cdot c_w} = \frac{2\,702\,400}{836\,800} = 3.23$$

Note: The NB2 checkpoint exercise used $n_e = 0.25$ to test the formula, giving $R = 2.67$. The model consistently uses $n_e = 0.20$, which gives the higher retardation shown here.
<br>
""",

"task_t04_checkpoint_2": r"""
## Solution — Courant Number

$$Cr = \frac{v \cdot \Delta t}{\Delta x} = \frac{11 \times 5}{25} = 2.2$$

This exceeds the classical $Cr \leq 1$ criterion. The TVD (Total Variation Diminishing) advection scheme handles $Cr > 1$ without oscillations, at the cost of some numerical dispersion. For our multi-decade simulation with monthly time steps, this is an acceptable trade-off between accuracy and run time.
<br>
""",

"task_t04_checkpoint_3": r"""
## Solution — Dominant Thermal Input

**Correct answer: B) River Limmat**

The Limmat combines the largest volumetric flux with the greatest temperature anomaly (~+2 °C above background). The thermal power anomaly $\Phi = \rho_w c_w Q \Delta T$ scales with both flux and temperature difference. Areal recharge covers a large area but is only slightly below background; the Sihl carries a moderate flux at near-background temperature; lateral inflow is at background temperature.

This is consistent with the energy budget from NB2.
<br>
""",

"task_t04_checkpoint_4": r"""
## Solution — Summer Aquifer Temperature

In the last summer (July) snapshot, the rivers are near their annual peak (~22–25 °C), and the Sihl drives a strong heat pulse into the aquifer through infiltration. The mean aquifer temperature in summer is elevated above background — cells near the infiltrating Sihl are warmed significantly, while cells far from the rivers remain near background. The domain-wide mean is around 10.8 °C, within the accepted range of 10.5–13.5 °C.
<br>
""",

"task_t04_checkpoint_5": r"""
## Solution — Energy Budget

**Correct answer: C) SSM-RIV**

River-aquifer exchange (SSM-RIV) dominates the energy budget because:
1. The RIV package has the largest volumetric flux in the water balance
2. The Limmat's 12.5 °C temperature carries significant thermal energy above background

This mirrors the flow model where RIV dominates the water budget — the same water flux that dominates the hydraulic balance also dominates the energy balance.
<br>
""",

"task_t04_checkpoint_alpha": r"""
## Solution — Dispersivity Sensitivity

**Correct answer: B) Wider and more diffuse**

Increasing $\alpha_L$ increases mechanical dispersion ($D_L = \alpha_L \cdot v$), which spreads the thermal signal over a larger area. The peak temperature anomaly decreases (more mixing with background), while the spatial extent of the warm plume increases. With transient forcing, higher dispersivity also **damps the seasonal amplitude** — the summer peak and winter trough become less extreme.

This exercise motivates calibration in NB5: the right $\alpha_L$ must reproduce observed temperature patterns — too low gives an overly sharp plume, too high gives an unrealistically diffuse one.
<br>
""",

"task_t04_checkpoint_seasonal": r"""
## Solution — Seasonal Signal Attenuation

**Correct answer: A) Decreases with distance**

The seasonal temperature signal attenuates with distance from the river due to:
1. **Thermal retardation** ($R \approx 3.23$): the thermal front moves ~3× slower than the water, delaying and damping the signal
2. **Dispersion**: mechanical and thermal dispersion smooth out sharp temperature gradients
3. **Conduction**: heat exchange with the solid matrix acts as a low-pass filter

Near the river, the aquifer closely tracks the seasonal river forcing. Far from the river, the signal is heavily damped and approaches the background temperature. The signal also **lags** — the summer peak at 300 m distance arrives later than at the river.
<br>
""",

# ── Transport Track — Notebook 5 solutions ──

"task_t05_checkpoint_1": r"""
## Solution — Monitoring Network

**5 monitoring wells** placed at increasing distances from the mid-Limmat (30, 80, 200, 400, 700 m). The near-river wells capture the strongest seasonal signal, while the distant wells show heavily attenuated temperature variations.
<br>
""",

"task_t05_checkpoint_2": r"""
## Solution — Initial Temperature RMSE

With the NB4 default parameters ($\alpha_L = 10$ m, $n_e = 0.20$), the model over-damps the seasonal amplitude compared to the reference (which used $\alpha_L = 5$ m, $n_e = 0.18$). The initial RMSE quantifies this mismatch. Higher dispersivity smooths the temperature signal too much, reducing the simulated seasonal swing.
<br>
""",

"task_t05_tt_checkpoint_1": r"""
## Solution — Seepage Velocity

From the moment analysis of the MW-1 breakthrough curve at $x = 50$ m:

$$\bar{t} = \frac{M_1}{M_0} \approx 4.1 \text{ d}$$

$$v = \frac{x}{\bar{t}} = \frac{50}{4.1} \approx 12.3 \text{ m/d}$$

This is consistent with the Limmat Valley Darcy flux ($q \approx 2.2$ m/d) and effective porosity ($n_e \approx 0.18$).
<br>
""",

"task_t05_tt_checkpoint_2": r"""
## Solution — Longitudinal Dispersivity

From the temporal variance of the MW-1 BTC:

$$\sigma_t^2 = \frac{M_2}{M_0} - \bar{t}^2$$

$$\sigma_x^2 = v^2 \cdot \sigma_t^2$$

$$\alpha_L = \frac{\sigma_x^2}{2x} = \frac{\sigma_x^2}{100} \approx 4.6 \text{ m}$$

The small deviation from the true 5.0 m is due to measurement noise. Farther wells (MW-2, MW-3) give values closer to 5.0 m because their BTCs have higher signal-to-noise ratios.
<br>
""",

"task_t05_tt_checkpoint_3": r"""
## Solution — Dispersivity Variation

**Correct answer: B) Measurement noise and scale dependence**

Two effects contribute:
1. **Measurement noise** — the noisy BTC tails slightly bias the moment estimates, especially at the nearest well where the BTC is sharpest
2. **Scale dependence** — longitudinal dispersivity tends to increase with transport distance in real aquifers (though this is a known artifact of the 1D moment analysis applied to heterogeneous media)

The mean across wells provides a more robust estimate than any single well.
<br>
""",

"task_t05_checkpoint_best_alpha": r"""
## Solution — Best Dispersivity

**Correct answer: B) alpha_L = 5 m**

The calibration sweep shows a clear RMSE minimum at $\alpha_L = 5$ m, which matches the tracer test estimate. Values lower than 5 m under-damp the signal (too much seasonal amplitude), while values higher than 5 m over-damp it (too little amplitude). This convergence of two independent methods — tracer test and temperature calibration — builds confidence in the result.
<br>
""",

"task_t05_checkpoint_3": r"""
## Solution — Calibrated Temperature RMSE

After calibration with $\alpha_L = 5$ m and $n_e = 0.18$ (from the tracer test), the temperature RMSE decreases significantly compared to the initial model. The improvement is most visible at near-river wells where the seasonal signal is strongest.
<br>
""",

"task_t05_checkpoint_4": r"""
## Solution — Energy Balance

The GWE energy balance error should be very small (< 0.01%), confirming that the numerical solution is mass-conservative. This is the transport equivalent of the water balance check in flow modeling.
<br>
""",

"task_t05_checkpoint_nonunique": r"""
## Solution — Breaking Non-Uniqueness

**Correct answer: B) The tracer test constrains n_e independently**

The temperature time series alone cannot distinguish between (high $\alpha_L$, low $n_e$) and (low $\alpha_L$, high $n_e$) — both combinations can produce similar seasonal amplitudes. The tracer test BTC provides an independent measurement: moment analysis gives velocity $v = x/\bar{t}$, and since $n_e = q/v$, porosity is determined directly. With $n_e$ fixed, only $\alpha_L$ remains to be calibrated.

This is the transport analogue of flow NB5's pumping test: an independent measurement that constrains one parameter, reducing the calibration to a 1D search.
<br>
""",

"task_t05_checkpoint_transfer": r"""
## Solution — Heat to Solute Transfer

**Correct answer: C) Thermal retardation factor**

| Parameter | Transfers? | Notes |
|-----------|------------|-------|
| $\alpha_L$, $\alpha_T$ | YES | Mechanical dispersion is identical for heat and solute |
| $n_e$ | YES | Same pore space carries both heat and solute |
| Thermal conductivity $\lambda$ | NO | Replace with molecular diffusion $D_m^*$ |
| **Thermal retardation $R$** | **NO** | Replace with sorption retardation $R_d = 1 + \rho_b K_d / n_e$ |
| Source terms | NO | Solute sources are chemically specific |

Dispersivity and porosity transfer directly because they describe the physical pore structure. Retardation does not transfer because it has different physical origins: thermal retardation comes from heat exchange with the solid matrix, while sorption retardation comes from chemical partitioning.
<br>
""",

"task_exercise_flow_net_1": r"""
The computation is the following: $h_A = h - \frac{\Delta h}{N_D} = 23 - \frac{20}{10}= 21$ m
""",

"task_exercise_flow_net_2": r"""
The computation is the following: 

The pore pressure at point B is $p_B = \rho g (h_B - z_B)$

The pore pressure at point C is $p_C = \rho g (h_C - z_C)$

The pressure gradient of pore water between Points B and C, given that $z_B = z_C$ is:

$\frac{dp}{dx} = \frac{p_B - p_C}{x_B - x_C} $
$= \frac{\rho g (h_B - z_B) - \rho g (h_C - z_C)}{x_B - x_C}$
$= \frac{\rho g (h_B - h_C)}{x_B - x_C}$
$= \frac{10 [m/s^2] 1000 [kg/m^3] 2[m]} {-10 [m]}$
$= -2 \cdot 10^3$ Pa/m
$= -2$ kPa/m
""",

"task_exercise_flow_net_3": r"""
The hydraulic gradient across the Box D can be calculated as :

$I = \frac{\Delta h}{\Delta s} = 2 [m]/10 [m] = 0.2$

The discharge of unit width (B=1 m) across Box D can be calculated as :

$Q_D = K \cdot I\cdot A = 5 \cdot 10^{-5} [m/s]\cdot  0.2 \cdot 10 [m]\cdot  1[m] = 10^{-4} m^3/s = 100 cm^3/s$

""",

"task_exercise_darcy_further_application_and_use_1": r"""
At Profile B, the water table intersects the top of the sandstone aquifer. 
Therefore the pressure at the aquifer roof is atmospheric ($p$=0), and the hydraulic head equals the elevation of the aquifer top.
Consequently we have: 
$ h_B = z_{top} +  \frac{p_B}{\rho g} = z_{top} +  0 = 10$ m
""",

"task_exercise_darcy_further_application_and_use_2": r"""
According to mass conservation, the discharge through vertical Profile C is the same as the one through vertical Profile B: $Q_B=Q_C$. 

In addition, $m_B$ and $m_C$ are the aquifer thicknesses at B and C and are both equalling $z_{top}$ such that the relation between discharge and specific discharge at B and C vertical profiles becomes:
- $Q_B= q_B\times m_B\times1=q_B \times z_{top}$ 
- $Q_C= q_C\times m_C\times1=q_C \times z_{top}$

Since $Q_B=Q_C$ is then obtained that $q_B=q_C$ as well.


We apply Dupuit'y assumption both from confined B-C and unconfined A-B sides perspectives
- $q_C = K\times\frac{h_C-h_B}{L-L_{AB}}$
- $q_B = K\left(h_B^2-h_A^2\right)/\left(2L_{AB}h_B\right)$ 

Kowing that $q_B=q_C$  we can solve the equation for the unknown $L_{AB}$:
- $L_{AB}=\frac{\left(h_B^2-h_A^2\right)L}{h_B^2-h_A^2+2\left(h_C-h_B\right)h_B}$ 
$= \frac{\left(10\ m\right)^2-\left(0.1\ m\right)^2}{\left(10\ m\right)^2-\left(0.1\ m\right)^2+2\times\left(12\ m-10\ m\right)\times10\ m}\times1000 m=714$ m
""",

"pumping_test_1": r"""
We use Jacob's approximation to the Theiss solution. We assume to have a transient radial flow in a confined aquifer. The drawdown at a single well of pumping rate $Q$=31.6 L/s located at radius r=122m is measured regularly in time from 1 to 240 minutes.

$$s(r,t) \approx -\frac{2.3\, Q}{4\pi T} \log_{10}\left(\frac{2.25\, T\, t}{r^2 S}\right) = -\frac{2.3\, Q}{4\pi T} \log_{10}\left(\frac{2.25\, T}{r^2 S}\right) - \frac{2.3\, Q}{4\pi T} \log_{10}(t)$$

A plot s(t) can be produced on a linear-logarithmic diagram, and a linear fit is done on the late time data (linear portion of the data). $\Delta s$ is measured for late times where the approximation is more accurate, so for us $\Delta s \approx 0.408m$ for the log cycle $t=10$ to $t=100$ min.

In these conditions, we find that:

$$T = - \frac{2.3\cdot Q}{4\pi \cdot\Delta s} =  - \frac{2.3\cdot 0.0316}{4\cdot 3.1416\cdot 0.408} \approx 0.0142\, m^2/s$$


For $Q=0.0316\, m^{-3}s^{-1}$ and $t=0.0142\, m^2/s$
""",

"pumping_test_2": r"""
For the storativity, the late time linear fit can be continued to cross the $s=0$ line such that $t_0$ is read. In this case, it can be estimated to be $t_0 \approx 1.64$ min. Therefore:

$$S = \frac{2.25\, T\, t_o}{r_0^2} = \frac{2.25\cdot 0.0142\cdot 1.64 \cdot 60}{122^2} \simeq 0.000211$$""",

"K_increase_sandstone_1": r"""
Look at $q_C$ equation: if $K$ increases, $L-L_{AB}$ must increase, $L_{AB}$ must decrease.
""",

"K_increase_sandstone_2": r"""
Look at $q_C$ equation: $q_C$ increase because of K increasing so $Q_C$ and then $Q_A$ as well increase. Since $Q=q\cdot A$, if $q_A$ is maintained, $A$, i.e. $q_A$ must increase.
""",

"K_increase_sandstone_3": r"""
Look at $q_C$ equation: $q_C$ increase because of K increasing so $Q_C$ and then $Q_A$ as well increase. Since $Q=q\cdot A$, if $h_A$ is maintained $A$ is maintained so $q_A$ must increase.
""",




}


# Dictionary to map tasks to Python functions to execute with the solution
task_functions = {
    "task01_1": lambda: du.display_image(image_filename='SwissTopoTsaletArea.png', image_folder='3_exercises'),
    "task01_4": lambda: display_disc_area_interactive(),
    "task04_1": lambda: draw_hx_plot(),
    "pumping_test_1": lambda: du.display_image(image_filename='PumpingTestFit.png', image_folder='3_exercises'),
    
}

# Dictionary to map tasks to Python functions to execute before the question
task_functions_start = {
    "task04_1": lambda: draw_schematic_interface()

}