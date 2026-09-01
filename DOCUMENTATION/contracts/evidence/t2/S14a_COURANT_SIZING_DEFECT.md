# T2 · S14a — `exp_v1` under-sizes the coarse identities, and the gate could not see it

**2026-09-01.** Found while running the four cheap identities S14 needs.

## 1. What was measured

All four coarse identities ran far above the Courant target they are named for. Every fine
identity was on target.

| identity | cell | target `Cr` | achieved | over by |
|---|---:|---:|---:|---:|
| `spatial_50m_cr0.9` | 50 m | 0.9 | **3.076** | 242% |
| `temporal_50m_cr0.45` | 50 m | 0.45 | **1.570** | 249% |
| `spatial_20m_cr0.9` | 20 m | 0.9 | **1.339** | 49% |
| `temporal_50m_cr0.225` | 50 m | 0.225 | **0.785** | 249% |
| *10 m · 5 m · 2 m · both B-control · both 2 m temporal* | 2–10 m | — | **on target** | — |

**All four were stamped `passed`.**

## 2. 🔴 The gate checked seven things and none of them was the Courant number

`accept_run` verified: artifact loads · provenance valid · cross-field invariants · `nstp_cap`
recorded · cap matches the guard · guard not reached · versions captured.

**Not one compares achieved `Cr` to the target.** An identity is *named* for its Courant target
(`spatial_50m_cr0.9`), and the gate could not see that the run missed it by 242%.

`cr_meets_target` is added, with a 5% relative tolerance that absorbs rounding `nstp` to a whole
number and nothing more — the observed failures were 49%–249% over. Verified both ways: it fails
the 50 m run and passes the 2 m run.

## 3. 🔴 CORRECTED — the sliver floor IS the cause

⚠️ **This section originally concluded the floor was "ruled out by measurement". That was wrong.**
The probe took `max(v/ds)` over **all 4 221 cells**, where the global maximum sits outside the
corridor and the floor cannot touch it. The sizing works on the **corridor mask** — 116 cells at
50 m. Measured on the right set, the floor is decisive:

| mesh | floor | corridor cells | dropped | max `v/ds` corridor | floor-kept | understated |
|---:|---:|---:|---:|---:|---:|---:|
| **50 m** | 20.0 | 116 | **89** | 0.6409 | 0.1832 | **3.50×** |
| **20 m** | 8.0 | 128 | **32** | 0.6360 | 0.4212 | **1.51×** |
| 10 m | 4.0 | 255 | 0 | 0.9133 | 0.9133 | 1.00× |

The 3.50× understatement matches the 3.42× Courant overshoot. `ds_bind = 20.54` sits just above
the 20 m floor while the smallest real corridor cell is **5.478 m**.

**The root cause:** the floor was keyed to the **requested** cell size, but the realised corridor
minimum comes from the base grid and is ~5.48 m at *every* mesh. So whenever
`0.4 × requested > 5.48` — 20 m and coarser — it discarded genuine corridor cells.

**Fixed 2026-09-01** (correction 5, lecturer authorised): `exp_v1` applies no floor. Re-running the
four identities reproduces S4/S5 exactly — `nstp` 86 / 85 / 171 / 342 and `Cr` 0.894 / 0.898 /
0.450 / 0.225 — and all four now pass `cr_meets_target`.

### Superseded — the original (wrong) section 3

The obvious suspect was `exp_v1`'s sliver floor, which is keyed off the mesh's own cell size
(`refined_cell_size=level.cell_size`) — 20 m at a 50 m mesh against legacy's constant 4 m — so it
drops far more cells from the sizing selection at the coarse end.

**Measured, and it is NOT the cause:**

| mesh | cells | floor | dropped | max `v/ds` all cells | floor-kept only | ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 50 m | 4 221 | 20.0 | 719 | 9.1795 | 9.1795 | **1.00×** |
| 20 m | 4 233 | 8.0 | 179 | 9.1795 | 9.1795 | **1.00×** |
| 10 m | 4 408 | 4.0 | 0 | 9.1795 | 9.1795 | 1.00× |
| 2 m | 15 727 | 0.8 | 0 | 14.8340 | 14.8340 | 1.00× |

The floor drops hundreds of cells at 50 m and **does not change the binding velocity at all**.

## 4. What the sizing SHOULD have produced — and S4/S5 already did

Working back from each run's own honestly-reported `Cr`:

| identity | `nstp` now | `Cr` now | steps needed for target | **S4/S5 recorded** |
|---|---:|---:|---:|---:|
| `spatial_50m_cr0.9` | 25 | 3.076 | **85** | **86** |
| `spatial_20m_cr0.9` | 57 | 1.339 | **85** | **85** |
| `temporal_50m_cr0.45` | 49 | 1.570 | **171** | **171** |
| `temporal_50m_cr0.225` | 98 | 0.785 | **342** | **342** |

**Exact agreement on three of four, off by one on the fourth.** The velocity field is the same;
S4/S5 sized correctly for it and `exp_v1` does not. The old numbers were right — they were not,
as first suspected, a flattering measurement.

⚠️ **What is NOT established:** *why* `exp_v1` sizes low. The floor is ruled out by measurement;
the remaining candidates are in its selection or its `dt` derivation, and were not investigated.

## 5. Consequences

- **The four coarse artifacts are NOT committed.** They are under-resolved and now correctly fail
  the gate.
- **S14's 21 evaluable components span the coarse identities**, so they cannot be evaluated at the
  stated Courant targets until the sizing is fixed or the coarse runs are produced another way.
- 🔴 **`exp_v1` is `transport_srcpulse_demo`'s surface** — C1 **A3** covers `profile` /
  `CourantSpec`. Whether fixing the sizing falls inside A3 or needs its own authorisation is the
  lecturer's call, not mine.

The probe that produced §3 is committed as `t2_courant_probe.py` so the measurement reproduces.
