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

"task04_k_values": r"""
## Exercise - Hydraulic Conductivity Assignment

Based on the geological zones in the Limmat Valley, assign hydraulic conductivity (K) values to each zone.
Use your understanding of the sediment types and typical K ranges for alluvial aquifers.

**Guidelines:**
- Zone 1 (Upstream alluvium): Sandy gravels, moderate conductivity
- Zone 2 (Downstream alluvium): Finer sediments, lower conductivity
- Zone 3 (Hardhof gravels): Coarse well-sorted gravels, high conductivity

Fill in your K values (m/day) in the dictionary below, then run the check.
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
    "task04_checkpoint_3": (6500, 8000),  # Correct solution ~7334 m³/day (depends on model area)
    "task04_checkpoint_4": (0, 0.1),  # Tolerance <0.1% - MF6 should converge to near-zero
    # Checkpoints 5 and 6 are conceptual/multiple choice - handled separately
    # K values task uses dict format for per-key tolerances
    "task04_k_values": {
        "zone_1_upstream": (15, 25),      # Sandy gravels: 15-25 m/day
        "zone_2_downstream": (8, 15),     # Finer sediments: 8-15 m/day
        "zone_3_hardhof": (25, 40),       # Coarse gravels: 25-40 m/day
    },
    # Add more tasks and their correct intervals here
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
    "task04_checkpoint_3": "~7334",
    "task04_checkpoint_4": "~0.0002",
    "task04_checkpoint_5": "B) Losing",
    "task04_checkpoint_6": "Head measurements, river discharge, spring discharge",
    "task04_k_values": {
        "zone_1_upstream": 20,    # Reference value for upstream alluvium
        "zone_2_downstream": 12,  # Reference value for downstream alluvium
        "zone_3_hardhof": 32,     # Reference value for Hardhof gravels
    },
    # Add more tasks and their correct intervals here
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
    "task04_k_values": {
        "zone_1_upstream": "m/day",
        "zone_2_downstream": "m/day",
        "zone_3_hardhof": "m/day",
    },
    # Add more tasks and their correct intervals here

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
    # Add more multiple choice tasks here as needed
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

The total recharge flux depends on your specific model setup and domain area. It is calculated as:

$$Q_{recharge} = A_{recharge} \times R_{rate}$$

Where:
- $A_{recharge}$ is the model area with active recharge (in m²)
- $R_{rate}$ is the recharge rate (in m/day)

For example, if your model area is ~20 km² (20 × 10⁶ m²) with a recharge rate of ~0.25 mm/day (0.00025 m/day):
- $Q_{recharge} = 20 \times 10^6 \text{ m}^2 \times 0.00025 \text{ m/day} = 5000 \text{ m}^3/\text{day}$

To calculate from your model:
- Sum all recharge flows from the RCH package (MODFLOW 6)
- Or integrate recharge rate × cell area across all recharge cells
- Check the water balance output for total inflow from recharge
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

"task04_k_values": r"""
## Solution - Hydraulic Conductivity Values

The hydraulic conductivity (K) values for the Limmat Valley geological zones are based on:
- Field measurements (pumping tests, slug tests)
- Swiss cantonal guidelines (AWA Zurich)
- Literature values for similar Alpine valley deposits

**Recommended values:**

| Zone | Sediment Type | K Range (m/day) | Reference Value |
|------|---------------|-----------------|-----------------|
| Zone 1 (Upstream) | Sandy gravels | 15-25 | 20 m/day |
| Zone 2 (Downstream) | Finer alluvium | 8-15 | 12 m/day |
| Zone 3 (Hardhof) | Coarse gravels | 25-40 | 32 m/day |

**Why these values?**

- **Zone 1 (Upstream alluvium)**: Mixed sandy gravels typical of upper valley deposits. Moderate sorting leads to intermediate K values.

- **Zone 2 (Downstream alluvium)**: Contains more silt and clay from floodplain deposition. Lower K reflects finer grain sizes.

- **Zone 3 (Hardhof gravels)**: Well-sorted coarse gravels from glacial outwash. High K due to large grain size and good sorting. This zone is the primary production aquifer.

These are initial estimates. Calibration against observed heads will refine these values in Notebook 5.
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