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
## Task 2:
The mean residence time of water $\tau$ was estimated to be 1 year.  
- **Estimate the total volume of the aquifer $V_{aq}$**
""",

"task01_3": r"""
## Task 3:
Based on the previous results :
- **Estimate $M_{aq}$ the mean thickness of the aquifer**" 
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
    "task01_3": (1.8, 2.0),  # Correct solution 1.9
    "task04_1": (37, 39),  # Correct solution 38
    "task04_2": (25, 27),  # Correct solution 26
    # Add more tasks and their correct intervals here
}



#------ Dictionary to store correct exact solution for tasks
solutions_exact = {
    "task01_1": "1.7 ",
    "task01_2": "3153600 ",
    "task01_3": "1.9 ",
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
- $ Q $ is the flow rate in $\text{km}^3$/day, $ Q = 1728 \text{m}^3/\text{day} = 1728 \times 10^{-9} \text{km}^3/\text{day} $
- $ t $ is 1 day

So we have that $ P \times A \times t = Q \times t $

We can solve $ A = \frac{1728 \times 10^{-9}}{1 \times 10^{-6}} \simeq 1.7 \text{km}^2 $

This result is close to the value from the BAFU :

<img src="sources/SwissTopoTsaletArea.png" alt="Spring Catchment Area" style="width:50%;">""",

"task01_2": r"""

The volume of water $V_{out}$ going out from the aquifer in one residence time period $\tau$ is needed to estimate the volume of the aquifer itself $V_{aq}$. We also need to take into account the aquifer porosity. 

Overall we have that $V_{aq} = \frac{V_{out}}{\phi}$ where :
- $V_{out} = Q \times \tau = 1728 \text{m}^3/\text{day} \times 365 \text{ day} = 1728 \times 365 \text{m}^3 $
- ${\phi} = 0.2$

Finally, $V_{acq} = 1728 \times 365 \text{m}^3 / 0.2 = 3153600 \text{m}^3$
""",


"task01_3": r"""

The thickness is : $M_{aq} = \frac{V_{acq}}{A} = \frac{3123600}{1.7} \frac{ \text{m}^3 }{\text{km}^2} = \frac{3123600}{1.7 \times 10^6}\text{m} \simeq 1.9 \text{m}$
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
