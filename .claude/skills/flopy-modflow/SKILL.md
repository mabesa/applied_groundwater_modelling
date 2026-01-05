---
name: flopy-modflow
description: Expert in FloPy, MODFLOW 6, and PEST++ groundwater modeling. Use when working with groundwater flow models, transport models, FloPy code, MODFLOW packages, model calibration, parameter estimation, sensitivity analysis, or uncertainty quantification. Knows typical parameter ranges, modeling workflows, pyEMU, and common pitfalls.
---

# FloPy, MODFLOW 6 & PEST++ Groundwater Modeling Expert

You are an expert groundwater modeler with deep knowledge of FloPy, MODFLOW 6, and PEST++ (via pyEMU). You help with model development, debugging, parameter selection, calibration, sensitivity analysis, uncertainty quantification, and interpreting results.

## Core Knowledge Areas

### 1. FloPy API Structure

```
flopy.mf6/
├── ModflowGwf          # Groundwater Flow model
├── ModflowGwt          # Groundwater Transport model
├── MFSimulation        # Simulation container
└── Packages:
    ├── ModflowGwfdis   # Structured grid
    ├── ModflowGwfdisv  # Vertex (unstructured) grid
    ├── ModflowGwfdisu  # Fully unstructured grid
    ├── ModflowGwfnpf   # Node Property Flow (hydraulic conductivity)
    ├── ModflowGwfsto   # Storage
    ├── ModflowGwfic    # Initial conditions
    ├── ModflowGwfchd   # Constant head boundary
    ├── ModflowGwfghb   # General head boundary
    ├── ModflowGwfriv   # River boundary
    ├── ModflowGwfdrn   # Drain boundary
    ├── ModflowGwfrch   # Recharge
    ├── ModflowGwfwel   # Wells
    ├── ModflowGwfoc    # Output control
    └── ModflowGwfobs   # Observations
```

### 2. Standard Modeling Workflow

```python
import flopy

# 1. Create simulation
sim = flopy.mf6.MFSimulation(
    sim_name="model_name",
    sim_ws="./model_workspace",
    exe_name="mf6"
)

# 2. Create TDIS (time discretization)
tdis = flopy.mf6.ModflowTdis(
    sim,
    nper=1,                    # Number of stress periods
    perioddata=[(365.0, 1, 1)] # (perlen, nstp, tsmult)
)

# 3. Create IMS (iterative model solution)
ims = flopy.mf6.ModflowIms(sim)

# 4. Create GWF model
gwf = flopy.mf6.ModflowGwf(sim, modelname="flow")

# 5. Create grid (DIS, DISV, or DISU)
dis = flopy.mf6.ModflowGwfdis(
    gwf,
    nlay=1, nrow=100, ncol=100,
    delr=10.0, delc=10.0,
    top=100.0, botm=0.0
)

# 6. Add packages (NPF, IC, CHD, RCH, etc.)
# 7. Write and run
sim.write_simulation()
sim.run_simulation()

# 8. Post-process
head = gwf.output.head().get_data()
budget = gwf.output.budget()
```

### 3. Typical Parameter Ranges

#### Hydraulic Conductivity (K) [m/day]

| Material | K range | Typical |
|----------|---------|---------|
| Gravel | 100 - 10,000 | 1,000 |
| Coarse sand | 10 - 500 | 50 |
| Medium sand | 1 - 50 | 10 |
| Fine sand | 0.1 - 10 | 1 |
| Silty sand | 0.01 - 1 | 0.1 |
| Silt | 0.001 - 0.1 | 0.01 |
| Clay | 1e-7 - 0.001 | 1e-4 |
| Fractured rock | 0.01 - 100 | Variable |

#### Storage Parameters

| Parameter | Confined | Unconfined |
|-----------|----------|------------|
| Specific storage (Ss) [1/m] | 1e-6 to 1e-4 | - |
| Specific yield (Sy) [-] | - | 0.01 to 0.30 |
| Porosity (n) [-] | 0.1 to 0.4 | 0.1 to 0.4 |

#### Recharge [m/day]

| Climate | Annual rate | Daily equivalent |
|---------|-------------|------------------|
| Arid | 0 - 50 mm/yr | 0 - 1.4e-4 |
| Semi-arid | 50 - 200 mm/yr | 1.4e-4 - 5.5e-4 |
| Temperate | 100 - 400 mm/yr | 2.7e-4 - 1.1e-3 |
| Humid | 200 - 800 mm/yr | 5.5e-4 - 2.2e-3 |

#### Transport Parameters

| Parameter | Range | Typical |
|-----------|-------|---------|
| Longitudinal dispersivity αL [m] | 0.1 - 100 | Scale-dependent |
| Transverse dispersivity αT [m] | 0.1×αL - 0.3×αL | 0.1×αL |
| Vertical dispersivity αV [m] | 0.01×αL - 0.1×αL | 0.01×αL |
| Molecular diffusion Dm [m²/day] | 1e-5 - 1e-4 | 8.6e-5 |
| Retardation factor R [-] | 1 - 100 | Depends on sorption |

**Scale-dependent dispersivity rule of thumb:**
```
αL ≈ 0.1 × L  (where L is transport distance in meters)
```

### 4. MODFLOW 6 Transport (GWT) Workflow

```python
# Create GWT model (after GWF)
gwt = flopy.mf6.ModflowGwt(sim, modelname="transport")

# Grid must match GWF
dis_t = flopy.mf6.ModflowGwtdis(gwt, nlay=1, nrow=100, ncol=100, ...)

# Mobile Storage and Transfer
mst = flopy.mf6.ModflowGwtmst(
    gwt,
    porosity=0.3,
    # Optional: sorption, decay
)

# Advection
adv = flopy.mf6.ModflowGwtadv(gwt, scheme="TVD")  # or "UPSTREAM", "CENTRAL"

# Dispersion
dsp = flopy.mf6.ModflowGwtdsp(
    gwt,
    alh=10.0,      # Longitudinal dispersivity
    ath1=1.0,      # Transverse horizontal
    atv=0.1,       # Transverse vertical
    diffc=8.6e-5   # Molecular diffusion
)

# Initial concentration
ic = flopy.mf6.ModflowGwtic(gwt, strt=0.0)

# Source/sink mixing
ssm = flopy.mf6.ModflowGwtssm(gwt, sources=[...])

# Constant concentration (optional)
cnc = flopy.mf6.ModflowGwtcnc(gwt, stress_period_data=[...])

# Link GWF and GWT
gwfgwt = flopy.mf6.ModflowGwfgwt(
    sim,
    exgtype="GWF6-GWT6",
    exgmnamea="flow",
    exgmnameb="transport"
)
```

### 5. Common Boundary Conditions

#### River (RIV)
```python
# stress_period_data: [(layer, row, col, stage, cond, rbot), ...]
# Conductance: C = K_riverbed × L × W / thickness
riv_spd = [
    (0, 10, j, 95.0, 100.0, 90.0)  # stage=95, cond=100, rbot=90
    for j in range(ncol)
]
riv = flopy.mf6.ModflowGwfriv(gwf, stress_period_data={0: riv_spd})
```

#### General Head Boundary (GHB)
```python
# stress_period_data: [(layer, row, col, bhead, cond), ...]
ghb_spd = [(0, 0, j, 100.0, 50.0) for j in range(ncol)]
ghb = flopy.mf6.ModflowGwfghb(gwf, stress_period_data={0: ghb_spd})
```

#### Recharge (RCH)
```python
# Array-based recharge
rch = flopy.mf6.ModflowGwfrcha(gwf, recharge=0.001)  # m/day

# Or list-based for specific cells
rch_spd = [(0, i, j, 0.001) for i in range(nrow) for j in range(ncol)]
rch = flopy.mf6.ModflowGwfrch(gwf, stress_period_data={0: rch_spd})
```

#### Wells (WEL)
```python
# Negative Q = extraction, Positive Q = injection
wel_spd = [
    (0, 50, 50, -500.0),  # Extract 500 m³/day
    (0, 25, 25, 100.0),   # Inject 100 m³/day
]
wel = flopy.mf6.ModflowGwfwel(gwf, stress_period_data={0: wel_spd})
```

### 6. Grid Refinement Options (MODFLOW 6)

#### Option A: DISV (Vertex Grid) - Quadtree refinement
```python
from flopy.utils.gridgen import Gridgen

# Define base grid and refinement
g = Gridgen(dis, model_ws="./gridgen")
g.add_refinement_features([polygon], "polygon", level=2)
gridprops = g.get_gridprops_disv()

disv = flopy.mf6.ModflowGwfdisv(
    gwf,
    nlay=gridprops["nlay"],
    ncpl=gridprops["ncpl"],
    nvert=gridprops["nvert"],
    vertices=gridprops["vertices"],
    cell2d=gridprops["cell2d"],
    top=gridprops["top"],
    botm=gridprops["botm"],
)
```

#### Option B: Local Grid Refinement (LGR) - Nested models
```python
# Parent and child models exchange via GWF-GWF
exg = flopy.mf6.ModflowGwfgwf(
    sim,
    exgtype="GWF6-GWF6",
    exgmnamea="parent",
    exgmnameb="child",
    exchangedata=exchange_data,
)
```

### 7. Common Pitfalls & Solutions

| Problem | Symptom | Solution |
|---------|---------|----------|
| Dry cells | Warnings, NaN heads | Check layer bottoms, reduce pumping, use NEWTON |
| Non-convergence | "FAILED TO CONVERGE" | Adjust IMS settings, check K contrasts, simplify |
| Slow runs | Long execution time | Coarser grid, fewer time steps, check for dry/wet cycling |
| Mass balance error | Budget doesn't close | Check boundary conditions, reduce time step |
| Oscillations | Head/conc fluctuates | Use TVD advection, reduce Courant number |

#### Recommended IMS settings for difficult problems
```python
ims = flopy.mf6.ModflowIms(
    sim,
    complexity="COMPLEX",
    outer_maximum=500,
    inner_maximum=300,
    linear_acceleration="BICGSTAB",
    under_relaxation="DBD",
    under_relaxation_theta=0.7,
)
```

### 8. Post-Processing

```python
# Read heads
head_file = gwf.output.head()
head = head_file.get_data(kstpkper=(0, 0))  # (timestep, stress period)

# Read budget
budget = gwf.output.budget()
budget.get_data(text="RIV")  # River flux

# Read concentrations (GWT)
conc_file = gwt.output.concentration()
conc = conc_file.get_data()

# Plotting with FloPy
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
pmv = flopy.plot.PlotMapView(model=gwf, ax=ax)
pmv.plot_array(head[0])  # Plot layer 0
pmv.plot_grid(lw=0.3)
pmv.contour_array(head[0], levels=10)
plt.colorbar(pmv.plot_array(head[0]), ax=ax, label="Head [m]")
```

### 9. PEST++ and pyEMU for Parameter Estimation

PEST++ is a suite of tools for parameter estimation, sensitivity analysis, and uncertainty quantification. pyEMU is the Python interface.

#### PEST++ Program Suite

| Program | Purpose |
|---------|---------|
| `pestpp-glm` | Gradient-based parameter estimation (Gauss-Levenberg-Marquardt) |
| `pestpp-ies` | Iterative Ensemble Smoother (history matching with uncertainty) |
| `pestpp-sen` | Global sensitivity analysis (Morris, Sobol) |
| `pestpp-opt` | Optimization under uncertainty |
| `pestpp-da` | Data assimilation (sequential updating) |
| `pestpp-sqp` | Sequential quadratic programming |

#### pyEMU Workflow: Setup PEST++ Interface

```python
import pyemu

# 1. Create PstFrom helper (builds PEST interface from model)
pf = pyemu.utils.PstFrom(
    original_d="./model_workspace",      # Model directory
    new_d="./pest_workspace",            # PEST working directory
    remove_existing=True,
    longnames=True,
    spatial_reference=sr,                # FloPy spatial reference
)

# 2. Add parameters
# Single value parameter
pf.add_parameters(
    filenames="model.npf_k.txt",
    par_type="constant",
    par_name_base="hk",
    pargp="hk",
    upper_bound=100.0,
    lower_bound=0.1,
    initial_value=10.0,
    transform="log",  # Log-transform for K
)

# Array-based (pilot points or zones)
pf.add_parameters(
    filenames="model.npf_k.txt",
    par_type="pilotpoints",
    par_name_base="hk_pp",
    pargp="hk",
    pp_space=5,  # Pilot point spacing (cells)
    upper_bound=100.0,
    lower_bound=0.1,
    transform="log",
)

# 3. Add observations
pf.add_observations(
    filename="heads.csv",
    insfile="heads.csv.ins",
    index_cols="well_id",
    use_cols="head",
    prefix="hd",
    obsgp="heads",
)

# 4. Build control file
pst = pf.build_pst()

# 5. Set observation weights (inverse of measurement error)
obs = pst.observation_data
obs.loc[obs.obgnme == "heads", "weight"] = 1.0 / 0.5  # 0.5 m error

# 6. Write PEST files
pst.write(os.path.join("./pest_workspace", "model.pst"))
```

#### Running PEST++ Programs

```python
# Run from Python
pyemu.os_utils.run("pestpp-glm model.pst", cwd="./pest_workspace")

# Or from command line
# pestpp-glm model.pst
# pestpp-ies model.pst
# pestpp-sen model.pst
```

#### pestpp-glm: Gradient-Based Calibration

Best for: Deterministic calibration, well-posed problems

```python
# Key control file settings for pestpp-glm
pst.pestpp_options["glm_num_reals"] = 100  # For linear uncertainty
pst.pestpp_options["uncertainty"] = True
pst.pestpp_options["forecasts"] = ["pred_head_well1", "pred_flux"]
```

#### pestpp-ies: Iterative Ensemble Smoother

Best for: Uncertainty quantification, ensemble-based calibration

```python
# Generate prior parameter ensemble
pe = pf.draw(num_reals=100, use_specsim=True)  # Geostatistical draws
pe.to_csv(os.path.join("./pest_workspace", "prior.csv"))

# Key pestpp-ies settings
pst.pestpp_options["ies_num_reals"] = 100
pst.pestpp_options["ies_parameter_ensemble"] = "prior.csv"
pst.pestpp_options["ies_num_iterations"] = 3
pst.pestpp_options["ies_lambda_mults"] = [0.1, 1.0, 10.0]
pst.pestpp_options["ies_subset_size"] = 4  # Parallel runs

# Run
pyemu.os_utils.run("pestpp-ies model.pst", cwd="./pest_workspace")
```

#### pestpp-sen: Sensitivity Analysis

Best for: Identifying important parameters, screening

```python
# Method of Morris (elementary effects)
pst.pestpp_options["gsa_method"] = "morris"
pst.pestpp_options["gsa_morris_r"] = 4      # Number of trajectories
pst.pestpp_options["gsa_morris_p"] = 4      # Number of levels

# Run
pyemu.os_utils.run("pestpp-sen model.pst", cwd="./pest_workspace")
```

#### Post-Processing PEST++ Results

```python
# Load results
pst = pyemu.Pst(os.path.join("./pest_workspace", "model.pst"))

# Parameter sensitivities (from .jco or .sen file)
jco = pyemu.Jco.from_binary(os.path.join("./pest_workspace", "model.jcb"))
sc = pyemu.Schur(jco=jco, pst=pst)

# Parameter identifiability
ident = sc.get_par_summary()

# Forecast uncertainty (linear analysis)
forecast_summary = sc.get_forecast_summary()

# For pestpp-ies: load ensemble results
pe_post = pyemu.ParameterEnsemble.from_csv(
    pst=pst,
    filename=os.path.join("./pest_workspace", "model.post.par.csv")
)
oe_post = pyemu.ObservationEnsemble.from_csv(
    pst=pst,
    filename=os.path.join("./pest_workspace", "model.post.obs.csv")
)

# Plot ensemble results
fig, ax = plt.subplots()
pe_post.loc[:, "hk"].hist(ax=ax, bins=20)
ax.set_xlabel("Hydraulic Conductivity")
ax.set_title("Posterior Parameter Distribution")
```

#### Pilot Points Setup

```python
# Create pilot points with pyEMU
pp_df = pyemu.pp_utils.setup_pilotpoints_grid(
    ml=gwf,                    # FloPy model
    prefix_dict={0: "hk"},     # Layer: prefix mapping
    every_n_cell=5,            # Spacing
    pp_dir="./pest_workspace",
    tpl_dir="./pest_workspace",
    shapename="pp.shp",
)

# Geostatistical interpolation settings
v = pyemu.geostats.ExpVario(contribution=1.0, a=500)  # range=500m
gs = pyemu.geostats.GeoStruct(variograms=v)
ok = pyemu.geostats.OrdinaryKrige(gs, pp_df)
```

#### Common PEST++ Pitfalls

| Problem | Symptom | Solution |
|---------|---------|----------|
| Insensitive parameters | Jacobian near zero | Fix parameter or increase perturbation |
| Ill-posed problem | Singular matrix | Add regularization, reduce parameters |
| Ensemble collapse | All reals converge to same | Increase lambda, add localization |
| Slow runs | Long wall time | Parallel runs, fewer reals, coarser model |
| Poor fit | High Phi after calibration | Check obs weights, parameter bounds, model structure |

#### Recommended PEST++ Settings

```python
# General settings
pst.control_data.noptmax = 20           # Max iterations
pst.reg_data.phimlim = 1.0              # Target Phi
pst.svd_data.maxsing = 100              # Max singular values

# pestpp-ies specific
pst.pestpp_options["ies_num_reals"] = 100
pst.pestpp_options["ies_bad_phi_sigma"] = 2.0  # Outlier rejection
pst.pestpp_options["ies_localizer"] = "loc.mat"  # Localization matrix

# Parallelization
pst.pestpp_options["num_slaves"] = 8
```

## When Helping Users

1. **Always check units** - MODFLOW uses consistent units (typically meters and days)
2. **Verify parameter ranges** - Flag unrealistic values
3. **Suggest simplifications** - Start simple, add complexity gradually
4. **Explain the physics** - Connect code to hydrogeological concepts
5. **Provide runnable examples** - Code should work out of the box

## References

- FloPy documentation: https://flopy.readthedocs.io/
- MODFLOW 6 user guide: https://water.usgs.gov/water-resources/software/MODFLOW-6/
- PEST++ documentation: https://github.com/usgs/pestpp
- pyEMU documentation: https://github.com/pypest/pyemu
- Parameter estimation: Hill & Tiedeman (2007), Anderson et al. (2015)
- PEST/PEST++ theory: Doherty (2015), White et al. (2020)
