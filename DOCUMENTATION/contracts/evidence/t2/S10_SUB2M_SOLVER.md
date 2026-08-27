# S10 — sub-2 m corridors: the blocker was the TRANSPORT solver, not the flow solver

**Status:** ✅ **RESOLVED AND SHIPPED** (C1 **A17**, lecturer signature 2026-08-27).
The preconditioner is on `main`, the gate gained an absolute floor and returns **PASS /
0 mismatches**, and `spatial_1m_cr0.9` is a **registered identity** whose controlled run
passed all seven acceptance checks. Sections 4, 5 and 9 record how that was reached; they
described an open question when written and are marked where superseded.

## 1. What was asked

> "We will run the refined grid on my mac and on the Hub and provide the run results
> to the students. They will not be required to run the refined grid themselves. So a
> longer runtime is ok. Let's try out a even finer grid. I want to see the t_peak and
> peak_mgL converge if at all possible."

The 900 s Hub ceiling is a *student-experience* constraint. Instructor-side evidence
generation is not bound by it, so runtime stopped being the limiting factor here.

## 2. Both finer meshes BUILD; both pilots failed

| target | `ncpl` | smallest cell | mesh build | pilot |
|---:|---:|---:|---:|:--|
| 1 m   |  42 071 | 0.73 m | 20 s | fail |
| 0.5 m | 214 116 | 0.25 m | 76 s | fail |

Mesh generation was never the problem.

## 3. The misdiagnosis, and what the trace actually said

The 2 m blocker (S10_2m_SOLVED) was a GWF iteration cap, so the obvious hypothesis
was "the same, only worse". It was not. Every one of these changed **nothing** —
identical ~44 s wall time and identical failure:

- GWF `outer_maximum` 1000 → 3000 → 5000
- GWF `inner_maximum` 100 → 500 → 1000
- GWF backtracking (10 / 1.05 / 0.2 / 100.0)
- GWF DBD under-relaxation
- `NO_PTC` (ALL and FIRST), and `COMPLEXITY=MODERATE` on flow

The constant wall time was the tell: nothing being tuned was in the failing path.

`mfsim.lst` says **`Solution 2 did not converge`**, and Solution 2 is **GWT**, not GWF:

```
line 335:  OUTER ITERATION CONVERGENCE CRITERION (DVCLOSE) = 0.100000E-03   <- Solution 1 = GWF
line 389:  OUTER ITERATION CONVERGENCE CRITERION (DVCLOSE) = 0.100000E-05   <- Solution 2 = GWT
line 425:  Solution 2 did not converge for stress period 1 and time step 1
```

The per-outer CSV confirms **flow converged normally** — 130 outers, `dvmax` decaying
monotonically to 9.70e-05, inside its own 1e-4 target:

| outer | 1 | 2 | … | 128 | 129 | 130 |
|---|---|---|---|---|---|---|
| \|dvmax\| | 2.57e-01 | 2.54e-02 | … | 1.52e-04 | 1.48e-04 | **9.70e-05** |

> The flow model was healthy the whole time. The failing solve was transport.

## 4. The fix, and why it did not initially ship

Transport here is linear, so 50 outers failing is a *preconditioner* problem, not an
iteration-count problem — and the isolation matrix says exactly that:

| `_GWT_IMS` variant | 1 m converges? |
|:--|:--|
| `inner_maximum=500` | no |
| `inner_maximum=1000, outer_maximum=200` | no |
| `outer_maximum=200` | no |
| **`complexity="COMPLEX"` (alone)** | **yes** (76 s pilot) |

`COMPLEXITY` selects the linear preconditioner. It is the only knob that matters, and
it needs no companion change. Tolerances stay at 1e-6 / 1e-7 — the converged answer is
the same answer, reached by a different path.

**But it fails the T0 gate at the default**, on three fields:

| field | A (reference) | B (COMPLEX) | rel. diff | tol |
|:--|--:|--:|--:|--:|
| `breakthrough[0]` | 1.52506050267e-04 | 1.52509890547e-04 | 2.518e-05 | 1e-05 |
| `mass_balance.grouped_residual_g` | 5.82e-10 g | 2.33e-10 g | 6.000e-01 | 1e-05 |
| `mass_balance.pct_imbalance` | -1.77e-11 % | 4.40e-11 % | 1.402e+00 | 1e-05 |

🔴 **`peak_mgL` and `t_peak` are not in that list — the headline metrics are bit-identical.**

All three are near-zero quantities, where a *relative* tolerance measures round-off:

- `breakthrough[0]` is the first sample of the curve, 1.5e-4 mg/L against a 5.28 mg/L
  peak. The absolute disagreement is **3.8e-09 mg/L**.
- the two mass-balance fields are residuals of order **1e-10 g on a 3.0e+05 g release**
  (~1e-16 relative). The 1.402 "relative difference" is a sign flip on numerical zero.

The 1e-5 concentration tolerance is right for concentrations of order 1 and wrong for
a 1e-10 g residual. That is a property of the gate, not of this change.

### ✅ RESOLVED 2026-08-27 — the gate gained an absolute floor

The lecturer's call was the near-zero floor, and it shipped as part of **A17**:

> `|a - b|  <=  FLOAT_ABS_TOL + FLOAT_REL_TOL * max(|a|, |b|)`,  `FLOAT_ABS_TOL = 1e-8`

1e-8 sits below every physically meaningful magnitude in the payload and above solver
round-off; for leaves of ordinary magnitude the relative term dominates and 1e-5 still
governs unchanged. `compare` against the shipped candidate now returns **PASS, 0
mismatches**. See `T0_0…` §4 and decision record §8.6.

## 5. How the series was therefore run

`COMPLEX` is applied at runtime inside the spike, and **all** points — including the
already-measured 10 / 5 / 2 m — are re-run under it. Otherwise the 2 m → 1 m step would
mix a refinement change with a solver change, which is the same confound that made the
original grid spike unusable (S8b).

When this was written a sub-2 m identity was **not** in `T2_preregistration.json`, so
`t2_run_matrix.require_registered` refused it by design and the series above was a
diagnostic spike.

### ✅ SUPERSEDED 2026-08-27 — 1 m is a registered identity

`spatial_1m_cr0.9` is registered (34 prereg components; checksum `a3765544…` →
`e88c2ccf…`) under the rule-4 justification recorded at `T0_2b` §3. It was then re-run
through the **controlled path** — `t2_run_matrix.py`, with `verify_prereg`,
`require_registered`, `guard_for` and `accept_run` all in force:

| | |
|---|---|
| `peak_mgL` | **6.132222951825588** — *bit-identical to the spike above* |
| `t_peak` | 37.945764426 d (`t_peak_quadratic_vertex_v1`, interpolated) |
| `ncpl` / `nstp` | 42 071 / 7 986 |
| `cr_achieved` | 0.89996 against a 0.9 target |
| `nstp_cap` | 40 000 — **guard not reached** |
| `provenance_valid` | `true` |
| acceptance | **7 / 7 checks passed** |
| wall | 5 756 s (96 min, Mac) |

⚠️ **Two `t_peak` evaluators, and they differ slightly.** The artifact records the
*interpolated* `t_peak_quadratic_vertex_v1` (37.9458 d); the spike table and the
convergence arithmetic in §8 use the *lattice* alias (37.9482 d). The gap is 0.0025 d
(**0.0065 %**), far inside tolerance, but the two are not the same number and should not
be quoted interchangeably.

Artifacts committed alongside this document: `spatial_1m_cr0.9.json` and
`spatial_1m_cr0.9.acceptance.json`.

## 6. Direct measurement: how much does `COMPLEX` actually move the series?

Because every point was re-run under `COMPLEX`, the three already-measured points give a
back-to-back comparison of the two preconditioners on identical grids:

| cell | `peak_mgL` under `MODERATE` | `peak_mgL` under `COMPLEX` | relative shift |
|---:|---:|---:|---:|
| 10 m | 5.27695440327 | 5.276954407117362 | **7.3e-10** |
| 5 m  | 5.8765        | 5.876457938403268 | ~7e-06 (reference rounded) |
| 2 m  | 6.1085        | 6.108463472394100 | ~6e-06 (reference rounded) |

At 10 m, where the reference is recorded to full precision, the two preconditioners agree
to **7.3e-10 relative** — five orders of magnitude tighter than the 1e-5 concentration
tolerance, and ~4 orders tighter than the smallest refinement step being resolved.

> This is the quantitative statement behind Section 4: the gate's FAIL is round-off in
> near-zero fields, not a change in the answer. `peak_mgL` and `t_peak` are unmoved at
> every measured grid.

It also means the sub-2 m points are **directly comparable** to the frozen 10 / 5 / 2 m
matrix values — the solver swap is far below the effect being measured.

## 7. Caveat on timings from this batch

The 2 m point in this batch reports 647 s against 525 s measured cleanly in S10_2m_SOLVED.
A stale duplicate process was running concurrently for part of the batch (it caught its own
errors and kept building models, discarding the results). **Wall times from this batch are
contaminated and must not be quoted**; `ncpl`, `nstp`, `peak_mgL` and `t_peak` are unaffected,
since those are properties of the simulation, not of how much CPU it had to share.

## 8. ✅ RESULT — the peak converges at 1 m

Full series, all points under `exp_v1`, `cr_target=0.9`, `COMPLEX` transport solver,
none capped (`nstp` guard 40000):

| cell | `ncpl` | `nstp` | `peak_mgL` | `t_peak` | `PeL_max` |
|---:|---:|---:|---:|---:|---:|
| 10 m | 4 408 | 122 | 5.2770 | 38.80 | 1.434 |
| 5 m | 5 784 | 370 | 5.8765 | 37.45 | 0.692 |
| 2 m | 15 727 | 1 979 | 6.1085 | 37.64 | 0.352 |
| **1 m** | **42 071** | **7 986** | **6.1322** | **37.95** | **0.215** |

Step-to-step change against the 2 % criterion:

| step | `peak_mgL` | within 2 %? | `t_peak` | within 2 %? |
|:--|--:|:--|--:|:--|
| 10 → 5 m | +11.361 % | no | −3.500 % | no |
| 5 → 2 m | +3.948 % | no | +0.508 % | yes |
| **2 → 1 m** | **+0.389 %** | **YES** | **+0.829 %** | **YES** |

🟢 **Both metrics are inside tolerance at the 2 → 1 m step. The series has converged.**

The successive differences in `peak_mgL` are **0.5995 → 0.2320 → 0.0238 mg/L**, a reduction
ratio of **0.102** on the last step — converging faster than first order, not drifting.
Richardson-style extrapolation puts the grid-converged peak at **≈ 6.135 mg/L**, leaving
a remaining discretisation error at 1 m of **~0.04 %**.

### This supersedes the S10_2m_SOLVED conclusion

That document closed with "the peak is not grid-converged within the envelope that was
reachable", on the evidence that 5 → 2 m was still moving 3.95 %. That was correct for the
envelope reachable *at the time* — 2 m was the finest grid that would run. With the
transport preconditioner fixed, one further halving settles it. The earlier statement was
a limit of the reachable envelope, not of the physics.

### 0.5 m is not needed

The 0.5 m mesh builds (214 116 cells) and would run, but at roughly **10× the 1 m cost —
on the order of 20 h**. With the extrapolated residual at 1 m already ~0.04 %, a 0.5 m point
would confirm a number that is two orders of magnitude inside tolerance. Not worth the run
unless it is wanted as belt-and-braces confirmation for publication.

### Reproducing this

The spike is deliberately **not** added to `_SUPPORT/src/scripts/` — a new module there is
outside the C1 allow-list, and this is diagnostic, not shipped. It is reproduced by calling
`build_srcpulse_demo` directly with the transport preconditioner patched at runtime:

```python
import sys; sys.path.insert(0, '_SUPPORT/src')
import transport_srcpulse_demo as tsd
tsd._GWT_IMS["complexity"] = "COMPLEX"          # spike-only; main ships MODERATE
for cell in (10.0, 5.0, 2.0, 1.0):
    r = tsd.build_srcpulse_demo(
        mesh_spec=tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=cell),)),
        cr_target=0.9, nstp_cap=40000, courant_profile="exp_v1",
        case_ws=f"<workdir>/c{cell:g}", force=True)
    print(cell, r.meta["ncpl"], r.meta["nstp"], r.peak_mgL, r.t_peak)
```

## 8b. The mesh itself

![Three-panel figure of the 1 m corridor-refined DISV mesh: (a) the full Limmat valley
domain of 42 071 Voronoi cells bounded by the river, with the refined area boxed; (b) the
graded corridor, a 1 m capsule from spill source to extraction well plus a disc at the
injection well, fading outward to the 50 m base grid; (c) individual 1 m cells resolved in
a 90 x 72 m window around the extraction well.](grid_1m_mesh.png)

Refinement is **graded**, not stepped: the 1 m capsule covers the spill-to-extraction
corridor with a second disc at the injection well, and grades outward through intermediate
sizes to the 50 m base grid. **87.5 % of cells are <= 1.5 m** (median 1.13 m, min 0.73 m,
max 74.2 m) -- concentrated in a corridor that is a small fraction of the domain area,
which is why 42 071 cells buys 1 m resolution where it matters.

Regenerate with `plot_grid_1m.py` in this directory (reads the cached mesh; no re-solve).

## 9. ✅ All three decisions taken, 2026-08-27

1. **Gate near-zero handling** → **absolute floor** `FLOAT_ABS_TOL = 1e-8` (§4). `COMPLEX`
   ships on `main`; `compare` returns PASS / 0 mismatches.
2. **1 m as evidence** → **registered** as `spatial_1m_cr0.9`, the sixth spatial point, and
   re-run through the controlled path (§5).
3. **A finer confirmation run** → **declined**, for both 0.5 m and 0.8 m. See §10.

## 10. Why no point finer than 1 m

The ASME grid-convergence procedure (Celik et al., 2008) on the three finest points,
with representative `h` = corridor cell size (a domain-wide `h` would be dominated by the
untouched 50 m background):

| metric | observed order `p` | 1 m value | extrapolated | **GCI band** |
|:--|--:|--:|--:|--:|
| `peak_mgL` | 2.385 | 6.1322 | 6.1378 | **± 0.115 %** |
| `t_peak` | 1.377 | 37.948 | 38.144 | **± 0.643 %** |

`p ≈ 2.4` on the peak is better than second order — the series is in its asymptotic range,
not wandering. Remaining discretisation error at 1 m is **0.0056 mg/L (0.092 %)**.

| next point | expected move in `peak_mgL` | cost vs the 1 m run |
|:--|--:|--:|
| 0.8 m | **0.038 %** | ~2× |
| 0.5 m | 0.074 % | ~8× |

🔴 **A 0.8 m point's expected signal is 3× SMALLER than the ±0.115 % uncertainty band on
the 1 m value itself.** It would be measuring the series' own noise floor, at twice the
cost of the run it is checking.

⚠️ It would also **re-arm `T0_2b` §3 rule 4 in full**, with no envelope change to justify
it: the ceiling was lifted once, for a specific reason, and that is not a standing licence
to keep refining.
