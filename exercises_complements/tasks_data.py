from uncertainty_plot import display_disc_area_interactive
from print_images import display_image

### File to define the questions and solutions of tasks / all necessary data

# question to ask (Markdown)
# accepted answers
# exact solution
# unit of the result, if there is one
# correction, steps to explain solution (Markdown)

#------ Dictionary to store the markdown to diplay the question asked
questions_markdown = {
"task01_1":  r"""
## Task 1:
We can assume the system to be at a steady state.
 - **Estimate $A$ the area of the Tsalet catchment in $\text{km}^2$**
""",

"task01_2":  r"""
## Task additionnal 1:
The mean residence time of water $\tau$ was estimated to be 1 year.  
- **Estimate the total volume of the aquifer $V_{aq}$**
""",

"task01_3": r"""
## Task 2:
Based on the previous results :
- **Estimate $M_{aq}$ the mean thickness of the aquifer**" 
""",

"task01_4": r"""
## Task 4:
Given the uncertainety intervals for $P$ and $Q$ :
- **Estimate the lower bound of *A* uncertainety interval**
""",

"task03_1": r"""
## Task 1:
Based on given data, estimate the specific discharge $q$ : 
""",

"task03_2": r"""
## Task 2:
Based on given data, estimate the  discharge $Q$ in the soil column :
""",

"task03_3": r"""
## Task 3:
Based on given data, estimate the mean velocity of water $u$ in the soil column :
""",

"task04_1": r"""
## Task 1:
Based on given data, estimate the water table level at $x$ = 200m :
""",

"task04_2": r"""
## Task 2:
Based on given data, estimate the water table level at $x$ = 400m :
"""
}



#------ Dictionary to store the accepted solutions / range of sample
solutions = {
    "task01_1": (1.6, 1.8),  # Correct solution 1.7
    "task01_2": (3100000, 3200000),  # Correct solution 3153600
    "task01_3": (0.18, 0.20),  # Correct solution 1.9
    "task01_4": (1.1, 1.3),
    "task03_1": (1.1, 1.3), 
    "task03_2": (0.60, 0.62), 
    "task03_3": (4.7, 4.9), 
    "task04_1": (37, 39),  # Correct solution 38
    "task04_2": (25, 27),  # Correct solution 26
    # Add more tasks and their correct intervals here
}



#------ Dictionary to store correct exact solution for tasks
solutions_exact = {
    "task01_1": "1.7 ",
    "task01_2": "3153600 ",
    "task01_3": "0.19 ",
    "task01_4": "1.2 ",
    "task03_1": "1.2",
    "task03_2": "0.61",
    "task03_3": "4.8",
    "task04_1": "38.0",  
    "task04_2": "26.0"
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
    "task03_2": "cm^3/s",
    "task03_3": "mm/s",
    "task04_1": "m",  
    "task04_2": "m"
    # Add more tasks and their correct intervals here

}



#------ Dictionary to store the markdown to display the correction
solutions_markdown = {

"task01_1": r"""
We must have that $ V_{in} = V_{out} $.

Water input volume over 1 day is $ V_{in} = P \times A \times t $ where:
- $ P $ is the precipitation recharge rate in km/day, $ P = 1 \text{mm/day} = 1 \times 10^{-6} \text{km/day} $
- $ A $ is the area of the catchment in $\text{km}^2$
- $ t $ is 1 day

Water output volume over 1 day is $ V_{out} = Q \times t $ where:
- $ Q $ is the flow rate in $\text{km}^3$/day, $ Q = 20 \text{L}/\text{s} = 1728 \text{m}^3/\text{day} = 1728 \times 10^{-9} \text{km}^3/\text{day} $
- $ t $ is 1 day

So we have that $ P \times A \times t = Q \times t $

We can solve $ A = \frac{1728 \times 10^{-9}}{1 \times 10^{-6}} \simeq 1.7 \text{km}^2 $

""",

"task01_2": r"""

The volume of water $V_{out}$ going out from the aquifer in one residence time period $\tau$ is needed to estimate the volume of the aquifer itself $V_{aq}$. We also need to take into account the aquifer porosity. 

Overall we have that $V_{aq} = \frac{V_{out}}{\phi}$ where :
- $V_{out} = Q \times \tau = 1728 \text{m}^3/\text{day} \times 365 \text{ day} = 1728 \times 365 \text{m}^3 $
- ${\phi} = 0.2$

Finally, $V_{aq} = 1728 \times 365 \text{m}^3 / 0.2 = 3153600 \text{m}^3$
""",


"task01_3": r"""

The thickness is : $M_{aq} = \frac{V_{aq}}{A}$. $A$ being known, we still need to compute the aquifer volume $V_{aq}$.

The volume of water $V_{out}$ going out from the aquifer in one residence time period $\tau$ is needed to estimate the volume of the aquifer itself $V_{aq}$. We also need to take into account the aquifer porosity. 

Overall we have that $V_{aq} = \frac{V_{out}}{\phi}$ where :
- $V_{out} = Q \times \tau = 1728 \text{m}^3/\text{day} \times 365 \text{ day} = 1728 \times 365 \text{m}^3 $
- ${\phi} = 0.2$

Finally, $V_{aq} = 1728 \times 365 \text{m}^3 / 0.2 = 3153600 \text{m}^3$

Back to the mean aquifer thickness : $M_{aq} = \frac{V_{aq}}{A} = \frac{3123600}{1.7} \frac{ \text{m}^3 }{\text{km}^2} = \frac{3123600}{1.7 \times 10^6}\text{m} \simeq 1.9 \text{m}$
""",

"task01_4": r"""

The lower bound $A_{min}$ of the area is given by the lower bound of the precipitation recharge rate $P_{min}$ and the upper bound of the flow rate $Q_{max}$.

We have that $A_{min} = \frac{Q_{min}}{P_{max}}$.
- $P_{max} = 1.1 \text{mm/day} = 1.1 \times 10^{-6} \text{km/day}$
- $Q_{min} = 15 \text{L}/\text{s} = 1296 \text{m}^3/\text{day} = 1296 \times 10^{-9} \text{km}^3/\text{day}$
It results that $A_{min} = \frac{1296 \times 10^{-9}}{1.1 \times 10^{-6}} \simeq 1.2 \text{km}^2$.

You might want to have a look at the following interactive plot which shows all possible values of $A$ reachable given the uncertainety intervals for $P$ and $Q$.


""",

"task03_1":
r"""
According to Darcy 's law, we have that :

$q = KI = K \cdot \frac{\Delta h}{L} = 0.0003 \cdot \frac{0.4}{1} = 1.2 \cdot 10^{-4} \cdot\text{m}/\text{s}^{-1} = 0.12 \cdot \text{cm}/\text{s}^{-1}$.
""",

"task03_2":
r"""
The discharge is derived from the specific discharge, accounting for the soil column cross section area : 

$Q = q \cdot A = 
1.2 \cdot 10^{-4} \cdot \pi \cdot \frac{d}{2}^2 = 6.1 \cdot 10^{-8} \cdot\text{mm}^3/\text{s}^{-1} = 6.1 \cdot \text{cm}^3/\text{s}^{-1}$.
""",

"task03_3":
r"""
The mean velocity is derived from the specific discharge, accounting for the soil column effective porosity : 

$u = \frac{q}{\phi_e} = 
 \frac{1.2 \cdot 10^{-4}}{0.25} = 4.8 \cdot 10^{-4} \cdot\text{m}/\text{s}^{-1} = 0.48 \cdot \text{cm}/\text{s}^{-1}$.
""",

"task04_1": r"""

The Darcy law is : $h(x) = -\frac{q}{K}(x - x_0) + h_0$ where:
- $q = 0.000003 \text{m}^2$ /s
- $K = 0.00005 \text{m/day}$
- $x_0 = 0 \text{m}$
- $h_0 = 50 \text{m}$
- $x = 200 \text{m}$

As a result, $h(200) = -\frac{0.000003}{0.00005}(200 - 0) + 50 = 38.0 \text{m}$
""",

"task04_2": r"""

The solution is the same as for the previous question, but plugging $x$ = 400m instead.

As a result, $h(400) = -\frac{0.000003}{0.00005}(400 - 0) + 50 = 26.0 \text{m}$
 """,
}


# Dictionary to map tasks to Python functions to execute
task_functions = {
    "task01_1": display_image("TestImage.png"),
    "task01_4": display_disc_area_interactive

}