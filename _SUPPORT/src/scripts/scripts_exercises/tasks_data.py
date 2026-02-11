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
## Numerical Checkpoint 1 - Model Discretization
Running your groundwater model with a 50m Voronoi grid discretization:
- **How many active cells does the model have?**
""",

"task04_checkpoint_2": r"""
## Numerical Checkpoint 2 - Aquifer Properties
Based on your model setup:
- **What is the average aquifer thickness (m)?**
""",

"task04_checkpoint_3": r"""
## Numerical Checkpoint 3 - Water Balance
From your water balance analysis:
- **What is the total recharge flux (m³/day)?**
""",

"task04_checkpoint_4": r"""
## Numerical Checkpoint 4 - Model Convergence
Examining your simulation results:
- **What is the water balance error (%)?**
""",

"task04_checkpoint_5": r"""
## Conceptual Checkpoint 1 - River-Aquifer Interaction
In the Hardhof area of the Limmat Valley:
- **Is the Limmat River gaining or losing water from the aquifer?**
  - A) Gaining (river receives discharge from aquifer)
  - B) Losing (river loses water to aquifer)
  - C) Varies along reach (both gaining and losing sections)
""",

"task04_checkpoint_6": r"""
## Conceptual Checkpoint 2 - Model Calibration and Validation
Consider how you would assess your model's predictive quality:
- **What observations would you compare to simulated values to assess model quality?**
  - Expected answers may include: head measurements at observation wells, river discharge/baseflow rates, spring discharge data, or other field measurements
""",

# task04_k_values removed - simplified to uniform K in notebook revision

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
After manual calibration:
- **What is your calibrated RMSE (m)?**
""",

"task05_checkpoint_4": r"""
## Checkpoint 4 - Water Balance
Verify your calibrated model's water balance:
- **What is the water balance error (%)?**
""",

"task05_checkpoint_5": r"""
## Conceptual Checkpoint - Residual Interpretation
You observe that residuals in Zone 1 are predominantly positive (simulated > observed).
- **What parameter adjustment would improve the fit?**
  - A) Increase K in Zone 1
  - B) Decrease K in Zone 1
  - C) Increase recharge everywhere
  - D) Decrease river conductance
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
    "task04_checkpoint_1": (3000, 3500),  # Correct solution ~3235 active cells (50m Voronoi grid)
    "task04_checkpoint_2": (15, 20),  # Correct solution ~17.5 m (Limmat Valley default)
    "task04_checkpoint_3": (2700, 3500),  # Correct solution ~3000 m³/day (10.4 km² × 110 mm/yr)
    "task04_checkpoint_4": (0, 0.1),  # Tolerance <0.1% - MF6 should converge to near-zero
    # Checkpoints 5 and 6 are conceptual/multiple choice - handled separately
    # task04_k_values removed - simplified to uniform K
    # Notebook 5 checkpoints
    "task05_checkpoint_1": (17, 22),      # 4 real AWEL + 15 synthetic = 19 obs points
    "task05_checkpoint_2": (1.5, 4.0),    # Initial RMSE before calibration (depends on initial params)
    "task05_checkpoint_3": (0.3, 2.0),    # Target calibrated RMSE < 2.0 m
    "task05_checkpoint_4": (0, 1.0),      # Water balance error < 1%
    # Checkpoint 5 is multiple choice - handled separately
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
    "task04_checkpoint_1": "~3235",
    "task04_checkpoint_2": "17.5",
    "task04_checkpoint_3": "~3000",
    "task04_checkpoint_4": "~0.0002",
    "task04_checkpoint_5": "B) Losing",
    "task04_checkpoint_6": "Head measurements, river discharge, spring discharge",
    # task04_k_values removed - simplified to uniform K
    # Notebook 5 checkpoints
    "task05_checkpoint_1": "19",
    "task05_checkpoint_2": "~2.5",  # Depends on initial parameters
    "task05_checkpoint_3": "~1.0",  # Target after calibration
    "task05_checkpoint_4": "~0.001",
    "task05_checkpoint_5": "A) Increase K in Zone 1",
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
    "task04_checkpoint_1": "cells",
    "task04_checkpoint_2": "m",
    "task04_checkpoint_3": "m³/day",
    "task04_checkpoint_4": "%",
    "task04_checkpoint_5": "multiple choice",
    "task04_checkpoint_6": "open-ended",
    # task04_k_values removed - simplified to uniform K
    # Notebook 5 checkpoints
    "task05_checkpoint_1": "points",
    "task05_checkpoint_2": "m",
    "task05_checkpoint_3": "m",
    "task05_checkpoint_4": "%",
    "task05_checkpoint_5": "multiple choice",
}


#------ Dictionary to store multiple choice options for conceptual checkpoints
# Format: task_id -> list of (value, label) tuples
# The 'value' is what gets compared against solutions_exact[task_id]
multiple_choice_options = {
    "task04_checkpoint_5": [
        ("A) Gaining", "A) Gaining (river receives discharge from aquifer)"),
        ("B) Losing", "B) Losing (river loses water to aquifer)"),
        ("C) Varies", "C) Varies along reach (both gaining and losing sections)"),
    ],
    "task05_checkpoint_5": [
        ("A) Increase K in Zone 1", "A) Increase K in Zone 1 (reduces simulated heads)"),
        ("B) Decrease K in Zone 1", "B) Decrease K in Zone 1 (increases simulated heads)"),
        ("C) Increase recharge everywhere", "C) Increase recharge everywhere (increases all heads)"),
        ("D) Decrease river conductance", "D) Decrease river conductance (affects river-aquifer exchange)"),
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
## Solution - Model Discretization

The number of active cells depends on your model discretization. For a 50m Voronoi grid applied to the Limmat Valley model domain:

- The Voronoi discretization creates a mesh with cell sizes around 50m
- For the typical Limmat Valley study area (~30-35 km²), this results in approximately **5000 active cells**
- The exact number depends on your model domain boundary and any inactive cells you may have defined

To find this value in MODFLOW 6:
- Check the summary output file or check the modulus output
- Look for "Number of active cells" or query the model grid object
- Or count non-zero entries in the IBOUND/IDOMAIN array
<br>
""",

"task04_checkpoint_2": r"""
## Solution - Aquifer Thickness

Based on the geological setup of the Limmat Valley model:

- The Limmat Valley contains primarily Quaternary alluvial and glacial deposits
- Typical aquifer thickness in this region ranges from **15-20 m**
- This represents the active saturated thickness of the main aquifer layer(s)
- Local variations exist, but the area average is approximately **17.5 m**

The average thickness can be calculated by:
- Taking the layer bottom elevation and subtracting the layer top elevation
- Averaging across all active cells in the model
- Or directly from your model layer definitions
<br>
""",

"task04_checkpoint_3": r"""
## Solution - Total Recharge Flux

The total recharge flux depends on your model domain area and recharge rate:

$$Q_{recharge} = A_{active} \times R_{rate}$$

Where:
- $A_{active}$ is the active model area (in m²)
- $R_{rate}$ is the recharge rate (in m/day)

For the Limmat Valley model with ~10 km² active area and 110 mm/year recharge:
- $R_{rate} = 110 \text{ mm/year} \div 365.25 \approx 3.01 \times 10^{-4} \text{ m/day}$
- $Q_{recharge} = 10 \times 10^6 \text{ m}^2 \times 3.01 \times 10^{-4} \text{ m/day} \approx 3000 \text{ m}^3/\text{day}$

To verify from your model:
- Check `total_recharge_m3_day` variable in the recharge calculation cell
- Or check the water balance output for total inflow from RCH package
<br>
""",

"task04_checkpoint_4": r"""
## Solution - Water Balance Error

MODFLOW 6 provides excellent numerical stability. The water balance error should be very small:

- **Target: < 0.1%** (excellent convergence)
- **Acceptable: < 1%** (good convergence)

The water balance error is calculated as:

$$\text{Error (\%)} = \frac{|Q_{in} - Q_{out}|}{|Q_{in}|} \times 100$$

Where $Q_{in}$ is total inflow and $Q_{out}$ is total outflow from all sources/sinks.

For your MF6 model:
- Check the summary output file for "Percent Difference"
- Verify all packages are included (WEL, RCH, RIV, DRN, etc.)
- Ensure stress periods are properly defined
- If error > 1%, check for convergence issues or missing packages
<br>
""",

"task04_checkpoint_5": r"""
## Solution - River-Aquifer Interaction

In the Hardhof area of the Limmat Valley, the Limmat River is **losing water to the aquifer**.

**Answer: B) Losing**

This conclusion is based on:
- The natural gradient in the Limmat Valley generally flows toward the river
- The river elevation is lower than the regional water table in many areas
- Regional groundwater flow patterns indicate convergence toward the river in some reaches and divergence in others
- In the Hardhof area specifically, historical data and typical Alpine valley hydrology show the river typically loses infiltrated water to recharge the aquifer below
- However, during high water stages or in gaining reaches, the relationship may reverse

When setting up river boundary conditions (RIV package in MODFLOW):
- A losing river has river elevation > modeled head (head draws down toward river)
- A gaining river has river elevation < modeled head (river receives groundwater discharge)
<br>
""",

"task04_checkpoint_6": r"""
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

2. **Synthetic observations**: 15 artificial points added for teaching purposes
   - Generated from a reference model run with realistic noise (σ = 0.3 m)
   - Distributed across the model domain for spatial coverage
   - Clearly marked as synthetic in all visualizations

**Total: 4 real + 15 synthetic = 19 observation points**

The synthetic observations allow us to demonstrate calibration methods even with limited real data coverage.
<br>
""",

"task05_checkpoint_2": r"""
## Solution - Initial RMSE

The initial Root Mean Square Error (RMSE) depends on how far the uncalibrated model parameters are from the "true" values.

With the default initial parameters (K = 20 m/day uniform), you should see an RMSE in the range of **1.5-4.0 m**.

The RMSE is calculated as:

$$\text{RMSE} = \sqrt{\frac{1}{n}\sum_{i=1}^{n}(h_{sim,i} - h_{obs,i})^2}$$

A higher initial RMSE indicates more room for improvement through calibration. The spatial pattern of residuals (shown in the residual map) guides which parameters to adjust.
<br>
""",

"task05_checkpoint_3": r"""
## Solution - Calibrated RMSE

After manual calibration, you should achieve an RMSE of **< 2.0 m**, ideally around **1.0 m** or less.

**Calibration quality guidelines:**
- RMSE < 1 m: Excellent
- RMSE 1-2 m: Good
- RMSE 2-3 m: Acceptable
- RMSE > 3 m: Needs improvement

The corresponding NRMSE (Normalized RMSE) should be **< 10%** of the observed head range.

If you cannot achieve RMSE < 2 m:
1. Check for observation points in problematic locations (near boundaries, dry cells)
2. Consider whether the conceptual model is appropriate
3. Review boundary condition assumptions
<br>
""",

"task05_checkpoint_4": r"""
## Solution - Water Balance Error

MODFLOW 6 should achieve excellent water balance closure. The error should be **< 1%**, typically around **0.001%** or less.

The water balance error is:

$$\text{Error (\%)} = \frac{|Q_{in} - Q_{out}|}{(Q_{in} + Q_{out})/2} \times 100$$

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

**Correct answer: A) Increase K in Zone 1**

**Reasoning:**
- Positive residuals mean simulated heads are **higher** than observed
- Higher heads occur when water cannot drain away fast enough
- Increasing K allows water to flow more easily, lowering heads

**Physical interpretation:**
- Simulated head = f(recharge/K) - higher K means lower equilibrium head
- If sim > obs, the aquifer is "mounding" too much → increase K to let water escape

**What the other options would do:**
- B) Decrease K → Would raise heads further (wrong direction)
- C) Increase recharge → Would raise heads everywhere (wrong direction)
- D) Decrease river conductance → Would affect river exchange but not systematically lower heads in Zone 1

This principle is key to manual calibration: use residual patterns to guide parameter adjustments in the correct direction.
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