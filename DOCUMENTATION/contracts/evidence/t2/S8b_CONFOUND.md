# T2 — 🔴 the spatial series is confounded, and its coarse end does not exist

**2026-08-26.** Found while switching the matrix to the corrected Courant profile.

---

## 1. `exp_v1` reports honestly, and what it reports is bad

Same three identities, `cr_target = 0.9` for all three:

| identity | legacy `nstp` / `Cr` | **`exp_v1` `nstp` / `Cr`** | meets its own target? |
|---|---:|---:|---|
| `spatial_50m_cr0.9` | 86 / **0.894** | 25 / **3.076** | 🔴 **fails by 3.4×** |
| `spatial_20m_cr0.9` | 85 / **0.898** | 57 / **1.339** | 🔴 **fails by 1.5×** |
| `spatial_10m_cr0.9` | 122 / 0.898 | 122 / **0.898** | ✅ meets it |

**Legacy reported `Cr ≈ 0.9` for all three. That was false** — it measured `Cr` only over the cells that
survived its own filter. `exp_v1` reports the **global** max over the corridor, and two of the three
identities are **badly under-resolved in time.**

> 🔴 **So the "spatial series at constant `cr_target = 0.9`" is not at constant `Cr` at all.** Differences
> between these identities mix spatial refinement with temporal resolution varying **3.4×**. That is not a
> controlled comparison, and it is the same confound that made the original grid spike unusable.

**The user's instinct was right: no meaningful evaluation is possible while this holds.**

## 2. 🔴 The deeper cause — the coarse identities are not coarse

Measured corridor cell sizes:

| requested corridor | corridor cells | **actual size: min / median / max** | `exp_v1` floor | cells excluded from sizing |
|---|---:|---|---:|---:|
| **50 m** | 116 | **5.48 / 10.53 / 37.23 m** | 20.0 m | 🔴 **76.7%** |
| **10 m** | 255 | 5.48 / **10.88** / 14.34 m | 4.0 m | 0.0% |

> **Requesting a 50 m corridor does not produce 50 m cells. It produces a median of 10.53 m — essentially
> the same as the 10 m request (10.88 m).**

Refinement adds *more* cells without making them *smaller*: `ncpl` 4221 → 4408 (+4%), corridor cells
116 → 255, median size **unchanged**. You cannot coarsen a mesh by asking for larger refinement cells —
the base discretisation already dominates. Coarsening would require changing **`base_cell_size`**, which
the frozen series does not vary.

**Two consequences:**

1. 🔴 **The series has no working coarse end.** 50 m, 20 m and 10 m are nearly the same mesh — which is
   exactly why `ncpl` barely moved, and why S4 saw a 47% peak swing from a 4% cell-count change.
2. 🔴 **`exp_v1`'s floor mis-describes them.** It keys off the *intended* size (`0.4 × 50 = 20 m`) on the
   assumption that the intended size bounds the mesh from below. Here it does not, so the floor discards
   **76.7%** of the corridor and sizes `nstp` from the coarse remainder — hence `Cr = 3.076`.
   ⚠️ `exp_v1` is implementing **A3's frozen wording correctly**; the wording assumes something this mesh
   does not satisfy.

## 3. What is and is not established

✅ **Established by measurement:** legacy's `Cr` reporting is false; `exp_v1`'s is honest; two of three
identities fail their own `cr_target`; the requested corridor size barely changes achieved cell size across
50 → 10 m; the fine end **does** bite (`ncpl` 5784 at 5 m, 15727 at 2 m).

❌ **Not established:** why the base mesh is already ~10 m in the corridor when `base_cell_size = 50`;
whether a working coarse end is achievable by varying `base_cell_size`; whether A3's floor rule should key
off the achieved mesh instead of the intended size.

## 4. Needs a decision — this is a contract question, not a bug

The floor rule is **A3's frozen wording** (*"key the sliver floor off the finest **intended** cell size
from the `GridSpec`"*), and the series composition is **`T0_2b…` §3's frozen 11**. Both are signed.

**The options, none of which is an implementation choice:**
- **Vary `base_cell_size`** to give the series a real coarse end — changes the frozen series composition.
- **Re-key the floor** off the achieved mesh — changes A3's frozen wording.
- **Accept the series as fine-end-only**, treating 50/20/10 m as one point rather than three — an honest
  reading of what was measured, and it shrinks the series to 10 → 5 → 2 m.

⚠️ **Whichever is chosen, the coarse identities as they stand cannot support a spatial-refinement claim** —
they neither differ meaningfully in mesh nor hold `Cr` constant.
