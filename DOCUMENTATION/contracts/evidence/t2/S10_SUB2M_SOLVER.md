# S10 — sub-2 m corridors: the blocker was the TRANSPORT solver, not the flow solver

**Status:** diagnosed and reproduced. **The shipped default is unchanged** — the fix
fails the T0 gate on three near-zero fields (Section 4) and that call is the lecturer's.

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

## 4. The fix, and why it is not shipped

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
a 1e-10 g residual. That is a property of the gate, not of this change — **but the gate
is a signed T0 artifact and its tolerance was a lecturer decision, so nothing here
touches either.** `_GWT_IMS` stays `MODERATE` on `main`.

**Decision needed:** does the gate get a near-zero absolute floor (compare on absolute
magnitude when both sides are below some epsilon), or does `COMPLEX` stay spike-only?

## 5. How the series was therefore run

`COMPLEX` is applied at runtime inside the spike, and **all** points — including the
already-measured 10 / 5 / 2 m — are re-run under it. Otherwise the 2 m → 1 m step would
mix a refinement change with a solver change, which is the same confound that made the
original grid spike unusable (S8b).

A sub-2 m identity is **not** in `T2_preregistration.json`, and `T0_2b` §3 rule 4 makes
adding a series point a failure edge, so `t2_run_matrix.require_registered` refuses it
by design. This is a diagnostic spike; it is **not matrix evidence** and is not
recorded as such.

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

## 9. What still needs the lecturer

1. 🔴 **The gate's near-zero handling.** `COMPLEX` fails `compare` only on fields that are
   numerically zero (Section 4), while `peak_mgL` agrees to 7.3e-10. Either the gate gains an
   absolute floor for near-zero leaves, or `COMPLEX` stays spike-only and sub-2 m results are
   always produced off the shipped default. Until that is decided, `main` keeps `MODERATE`.
2. **Whether the 1 m result is publishable evidence.** It is a spike by construction — a
   sub-2 m identity is not pre-registered, and registering one is a `T0_2b` §3 rule 4 failure
   edge. Showing students a converged peak means either accepting spike-grade evidence for a
   teaching figure, or amending the pre-registration.
3. **Whether to spend the 0.5 m run** (~20 h) as confirmation.
