# T2 — why the 2 m identity fails, and what it would cost to fix

**2026-08-26.** Full diagnosis, after the 2 m pilot failed at SP1/TS1.

---

## 1. It is the SOLVER TOLERANCE, not the geometry

Things ruled out by measurement:

| hypothesis | test | result |
|---|---|---|
| The mesh cannot be built | built at 2 m | ✅ builds — `ncpl = 15727`, 4.7 s |
| The retry radius is wrong | corridor at r = **30** and **45** | ❌ both still fail SP1/TS1 |
| Compact zones vs thin strips | focus discs (spill + ext + inj) at r = 30 / 45 | ✅ **meshes build**, `ncpl` 6031 / 8437 |

**What actually differs:** there are **two** GWF solves, and they use different criteria.

| | refgrid build (`model_io_utils`) | **coupled sim** (`_GWF_IMS`) |
|---|---:|---:|
| `outer_dvclose` | **1e-3** | 1e-4 |
| `inner_dvclose` | **1e-4** | 1e-5 |

The refgrid GWF **converges at 2 m**. The coupled sim demands **10× tighter** and fails. PR #113 established
`1e-3 / 1e-4` as *what a refined GWF needs*; the coupled sim asks for more than that.

**Confirmed directly** — 2 m pilot, convergence only:

| tolerance | converges? |
|---|---|
| shipped `1e-4 / 1e-5` | ❌ **no** |
| refgrid's proven `1e-3 / 1e-4` | ✅ **yes** |
| looser `1e-2 / 1e-3` | ✅ yes |

> 🔴 **The 2 m identity is reachable.** It is blocked by a solver setting that is stricter than the
> configuration the project already established as sufficient.

## 2. 🔴 But relaxing is NOT output-neutral — it is a default-path change

Same test at the **default** (10 m, legacy profile), against the qualified reference
`peak_mgL = 5.27695440327`:

| tolerance | default `peak_mgL` | |
|---|---|---|
| shipped `1e-4 / 1e-5` | `5.27695440327` | ✅ identical |
| relaxed `1e-3 / 1e-4` | `5.27697838128` | 🔴 **moves at the 6th significant digit** |

The gate normalises to **11 significant digits**, so **`compare` would fail.** Relaxing `_GWF_IMS` globally
is a **default-path change** — a failure edge, not an edit.

## 3. The shape of the fix, and what it needs

The precedent is exact: **S8 solved the same problem for the Courant policy** by putting the corrected
behaviour behind an `exp_v1` profile while the default kept the legacy one. A **solver profile** would do
the same here.

🔴 **But nothing on the allow-list covers IMS settings.** A3 covers `courant_nstp`; A6 the sink support;
A11 the source footprint; A13 the sensitivity arm. **A solver-tolerance profile has no entry**, so it needs
one — and on the C1 §3.1 test as re-gated, no Appendix B bullet names solver tolerances, which means **a
signature, not an amendment.**

## 4. A cheaper option the spike also surfaced

The lecturer's suggestion — refine **around the wells and source** rather than the whole corridor — is
**independently valuable on cost**, even though it does not fix convergence:

| refinement zone | `ncpl` at 2 m |
|---|---:|
| corridor, r = 70 (the frozen default) | **15 727** |
| focus discs (spill + ext + inj), r = 30 | **6 031** |

**2.6× fewer cells**, which at `W = ncpl · nstp` is a 2.6× cost reduction on the most expensive identity in
the matrix.

⚠️ **Its convergence under relaxed tolerances is untested**, and reaching it needs custom `refine_points`,
which `refine_corridor` does not expose — **that is S3b territory** (`model_io_utils` / `disv_grid_utils`),
deferred out of T1 and itself awaiting a signature.

## 5. Honest summary

- **2 m is not impossible.** It converges at the tolerances the project already proved sufficient.
- **It cannot be had for free.** Relaxing moves the default payload, so it needs a profile, and a profile
  needs authority nobody has granted.
- **The series today is `10 m → 5 m`**, both converging and both meeting `cr_target` under `exp_v1`.
- **Focus-area refinement would make 2 m 2.6× cheaper** — but it is behind the same deferred S3b signature.
