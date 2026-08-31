> 🔴 **SUPERSEDED IN PART, 2026-08-31** by . The pricing verdicts in §2
> below were for the SERIES; the series is no longer ceiling-bound ( §3 rule 4,
> amended 2026-08-27 — instructor-side precomputation). What S8 still owes is the PROBE price,
> and that is now **measured, not predicted**: 503 s against a 600 s target. §1's 
> requirement is resolved —  is the shipped default.

# T2 · S8 — the pricing model, and a blocker it exposed

**2026-08-26.** The model is fitted on the **five measured points** from S4 and S5 — never on the
withdrawn capped run — per `T2_steps.md` §1.1.

```
wall  =  14.4168 µs · W  +  6.66 s          W = ncpl · nstp
max relative residual over the fit points: 3.94%
```

The intercept is **58% of the cheapest run**: these points are **overhead-dominated**.

**Mesh diagnostic** (a mesh build only — no solve, so not a matrix identity):

| corridor | `ncpl` | build |
|---:|---:|---:|
| 50 m | 4221 | — |
| 20 m | 4233 | — |
| 10 m | 4408 | — |
| **5 m** | **5784** | 2.1 s |
| **2 m** | **15727** | 4.7 s |

🔴 **The regime change S4 predicted is real.** The fit spans `ncpl` 4221–4408 — a 4% range. **2 m is
15727, 3.6× the top of that range**, and its `W` is **21.8× the largest fitted point.**

---

## 1. 🔴 THE BLOCKER: the 2 m identity cannot run under the legacy Courant profile

The legacy sliver floor is `0.4 × LOCKED_PARAMS["refined_cell_size"]` = **4.0 m**, and it is **constant —
it does not follow the `MeshSpec`.**

| corridor | cells vs the 4.0 m floor | Courant sizing |
|---:|---|---|
| 50 · 20 · 10 · 5 m | ≥ 4 m | ✅ included |
| **2 m** | **< 4 m** | 🔴 **EXCLUDED — `nstp` under-counts and the reported `Cr` is a lie** |

> **`spatial_2m_cr0.9` run under `legacy_srcpulse` would be silently under-resolved in time.** That is
> precisely the defect that made the original grid spike unusable — *"graded runs reported `Cr = 0.90`
> while the 1 m cells ran at `Cr ≈ 5.5`"*.

> 🔴 **So the frozen spatial series carries an implicit requirement nobody wrote down: the 2 m identity
> must run under `exp_v1`.** T1 built that profile for exactly this, but no contract text connects it to
> the spatial series — and running the series naively under the default profile would reproduce the
> confound T2 exists to remove.

⚠️ **5 m is safe under either profile** (5 m > 4 m floor), so this bites only at 2 m.

## 2. Pricing verdicts

| identity | `W` | vs fit range | predicted Hub | conservative bound | verdict |
|---|---:|---:|---:|---:|---|
| **5 m** @ `cr 0.9` | 1.16 M | **0.8×** — *inside* | 54 s | **84 s** | ✅ **clean pass** |
| **2 m** @ `cr 0.9`, `exp_v1` | 31.5 M | **21.8×** — far outside | 1058 s | **1650 s** | 🔴 **REFUSE** (ceiling 900 s) |

**5 m is an INTERPOLATION, not an extrapolation** — its `W` sits inside the fitted range. It is safe to run
and it is the next step.

🔴 **The 2 m number must NOT be acted on.** It extrapolates **21.8× beyond the largest fitted point**, from
an overhead-dominated fit into a work-dominated regime, on an `nstp` taken from the corrected-Courant
record that **itself sat on a cap**. `T2_steps.md` §1.2's recalibration gate exists for exactly this:
**2 m is priced only after 5 m has run and the model is refitted.**

⚠️ **But the direction is a warning worth carrying:** every current estimate puts 2 m **above** the ceiling,
and the `exp_v1` requirement of §1 makes it **more** expensive than a legacy-profile estimate, not less.

## 3. What this means for the stated preference for "finer than 5 m"

- **5 m: affordable, and next.**
- **2 m: currently prices above the ceiling** — and `T0_2b…` §3 rule 2 then says the series **stops**,
  which is *"a result, not a failure"*.
- The routes that would still reach 2 m are a **cheaper `GridSpec`** (a T1 failure edge) or a **revised
  threshold** (a T0 one). **Both are signatures, and neither is a preference.**
- **The recalibration gate is the honest place to settle it**, on a refitted model rather than a 21.8×
  extrapolation.
