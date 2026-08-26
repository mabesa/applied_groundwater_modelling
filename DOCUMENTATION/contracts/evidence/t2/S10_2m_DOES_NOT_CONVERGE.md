# T2 — 🔴 the 2 m identity does not converge. It is not a cost question.

**2026-08-26.** Found while trying to replace a *scaled* `nstp` estimate with a *measured* one.

---

## 1. What happened

A cheap pilot (20 timesteps) at the 2 m corridor, purely to measure `nstp` demand:

```
PILOT ok=False (15.4 s)

mfsim.lst:  ERROR REPORT:
              1.  Simulation convergence failure occurred 1 time(s).
            Premature termination of simulation.

gwf.lst:    ****FAILED TO MEET SOLVER CONVERGENCE CRITERIA
            IN TIME STEP 1 OF STRESS PERIOD 1****
```

**The FLOW solve fails at time step 1.** Not transport, not timing, not the step cap.

> 🔴 **So `spatial_2m_cr0.9` cannot be priced, because it cannot run.** Everything above about ceilings,
> conservative bounds, `H`, and signatures was pricing something that does not execute.

## 2. This is a KNOWN failure mode, already on record

`transport_notebook_regrid_vision.md`, from the original spikes:

> *"**Compact refinement zones work; thin strips do not.** A 2 m corridor at **half-width 15 m fails to
> converge** (SP1/TS1); at **half-width 30 m it converges.** … The working window between 'too thin to
> converge' and 'too wide to afford' is **not yet mapped**."*

**SP1/TS1 is exactly what just failed.** The spike also *did* obtain a 2 m result (peak 6.042), so 2 m is
**not categorically impossible** — it converged under a different corridor geometry.

⚠️ The mesh itself builds fine (4.7 s, `ncpl = 15727`, `refine_radius_used = 70.0`). **It is the GWF solve
on that mesh that fails**, and the GWF is already `NEWTON` + `COMPLEX` + `BICGSTAB` — the settings PR #113
established as the load-bearing fix for drying-cell oscillation. **The known solver hardening is already
in place and is not enough here.**

## 3. What this changes

| Previously believed | Actually |
|---|---|
| 2 m is a **cost** question — 972 s conservative bound vs a 900 s ceiling | 2 m is a **convergence** question. Cost is irrelevant until it runs |
| The decision needs a **signature** (cheaper `GridSpec` at T1, or a revised threshold at T0) | Neither would help. A threshold revision cannot make a non-converging solve converge |
| The recalibration gate would settle it | The gate settles *price*. This is upstream of price |

🔴 **The frozen spatial series names an identity that does not execute under the frozen `MeshSpec`.**
That is a contract-level fact, not a tuning problem.

## 4. What is NOT established

- **That 2 m is unreachable.** The spike reached it. The corridor **half-width** is the known lever
  (15 m fails, 30 m converges), and `MeshSpec.retry_radii` exists precisely to search that space — this run
  used the default ladder and reported `refine_radius_used = 70.0`.
- **Whether a converging 2 m configuration is affordable.** Unknown, and unknowable until one converges.
- **Whether 5 m is enough.** 5 m ran cleanly at `Cr = 0.899`, meeting its target — the series *does* have a
  working fine end at 5 m.

## 5. The honest position

**The spatial series is currently `10 m → 5 m`.** Both converge, both meet `cr_target` under `exp_v1`, and
`ncpl` genuinely differs between them (4408 → 5784) — unlike the 50/20/10 m cluster, which is one mesh
wearing three names.

Going finer than 5 m requires **finding a converging 2 m geometry first** — a search over corridor
half-width, not a budget decision. Until then, *"tolerance not reached within the feasible envelope"* is the
`T0_2b…` §3 rule-2 outcome, and it is **a result, not a failure**.
