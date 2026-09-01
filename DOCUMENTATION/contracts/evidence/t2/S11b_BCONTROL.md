# T2 · S11b — B-control unblocked, and what it shows

**2026-08-31.** The B-control pair was blocked on a **definition**: `sink_support_m` — the radius
of the fixed extraction-support disc — was never frozen. It is frozen here, and both identities
ran. **The `notebook_evidence_matrix` is now complete: 12 of 12.**

---

## 1. How it was unblocked — by reusing a radius that was already frozen

Operator A faces the identical geometric question and had already answered it:

> `transport_operator_a.RADIUS_M = 25.0`, applicable iff `cell_size_m <= radius_m`
> — *"the disc diameter spans at least two nominal cells."*

**That rule IS the degeneracy that blocked B-control.** At 50 m cells `50 <= 25` is false: the disc
falls inside one cell, the apportionment `qᵢ = Q·area(cellᵢ ∩ disc)/area(disc)` hands the whole rate
back to that single cell, and the control controls nothing.

**Frozen, therefore:**

| | |
|---|---|
| `sink_support_m` | **25.0 m** — operator A's radius, under operator A's rule |
| matched pair | **10 m (coarse) + 2 m (fine)**, NOT 50 m + 2 m |

⚠️ **Nothing in the contracts pinned B's coarse mesh to 50 m** — `T0_2b…` §5 says only *"matched
coarse + fine"*. Naming the pair was a definition to make, not a contract to amend. 10 m is the
meaningful coarse case: it is the teaching default students actually run.

### 1.1 🔴 Two honest caveats on this choice *(codex, 2026-08-31)*

**(a) 25 m is CONSISTENCY, not a measured extraction footprint.** Operator A averages a
*concentration* over a disc for observation-support robustness; B apportions a *pumping rate*.
The geometry is the same, the question is not. 25 m is adopted because it keeps the two receptor
operators consistent and because its applicability rule is already frozen — **not** because anyone
has established that the extraction actually draws from a 25 m disc. **If the physical support of
this well is materially different from 25 m, this radius is wrong**, and the arm would need
re-running rather than reinterpreting.

**(b) The 10 m + 2 m pair was chosen AFTER adopting the rule, and that is convenient.** The rule
excludes 50 m; the pair that survives it is the pair I then named. This is legitimate only because
"coarse" was never fixed — but selecting the option that makes your own constraint satisfiable
deserves saying out loud rather than presenting as forced.

The runner now **refuses** a B identity whose cell size exceeds the radius, rather than silently
producing a no-op control.

## 2. 🔴 A `run_role` defect, found and fixed

`t2_run_matrix.py` hard-coded `run_role="spatial_series"` for **every** identity. `T0_2b…` §5.1
freezes `run_role` as a closed enum and makes it mandatory *precisely* so a run's role cannot be
confused.

**`temporal_2m_cr0.45` and `temporal_2m_cr0.225` were emitted mislabelled** and merged that way.
The role is now derived from the identity, and both were **re-run** rather than hand-edited — the
artifacts carry a `content_hash`, so editing evidence in place would have been worse than the error.

✅ **The re-runs reproduce the physics bit-identically** (`peak_mgL` 6.116975 and 6.121254 to every
digit, same `nstp`) — the runs are deterministic and the label does not touch the calculation.

🔴 **And the re-run was NECESSARY, not merely tidier — measured, not assumed** *(codex asked)*:

| identity | old `content_hash` | new |
|---|---|---|
| `temporal_2m_cr0.45` | `8a1bfcfc…` | `c4853159…` |
| `temporal_2m_cr0.225` | `bd26d148…` | `3a886cd6…` |

**`run_role` IS inside `content_hash`.** Hand-editing the field would have left every artifact with
a hash that no longer described it. Bit-identical physics plus a changed hash is exactly the right
signature: the label is part of the record's identity, not part of its arithmetic.

## 3. What B-control shows

| mesh | | `nstp` | `peak_mgL` | `t_peak` |
|---|---|---:|---:|---:|
| 10 m | uncontrolled | 122 | — | — |
| 10 m | **B-controlled** | **86** | 4.9123 | 38.953 |
| 2 m | uncontrolled | 1 979 | 6.1085 | 37.653 |
| 2 m | **B-controlled** | **371** | 5.7771 | 38.245 |

### 3.1 Most of the fine-mesh timestep cost is the SINK, not the plume

At 2 m the control cuts `nstp` from **1 979 to 371 — 5.3×**. At 10 m it is only 1.4× (122 → 86).

**MEASURED:** the control reduces `nstp` by 5.3× at 2 m and 1.4× at 10 m. That is the finding, and
it is solid — four registered runs, all uncapped, all accepted.

⚠️ **HYPOTHESIS, not a finding** *(codex, 2026-08-31)*: that the cause is a velocity singularity at
the single-cell sink which sharpens as the mesh refines, with Courant sizing paying for it. It is
the natural reading — the sink is the only thing the control changed — but **two ratios do not
establish a mechanism**. Solver behaviour, cell geometry near the well, or another binding term in
the timestep calculation could contribute. The `courant_nstp` diagnostic records which cell binds;
reading it would settle this, and has not been done.

> **What may be stated:** spreading the sink over a fixed disc makes fine meshes dramatically
> cheaper in timesteps. **What may not yet be stated:** *why*.

### 3.2 🔴 But the grid sensitivity SURVIVES the control — a negative result

| | 10 m | 2 m | coarse → fine |
|---|---:|---:|---:|
| uncontrolled | 5.2770 | 6.1085 | **+15.76%** |
| **B-controlled** | 4.9123 | 5.7771 | **+17.60%** |

✅ **Both sides are now registered identities.** An earlier draft compared the measured controlled
figure against ≈ +15.7% *derived from `04t`'s published series*, and codex was right that a
half-measured contrast should not be asserted. `spatial_10m_cr0.9` was already a registered
identity and cost **19.6 s** to run through the controlled path, so it was measured rather than
withdrawn. Its **+15.76%** confirms `04t`'s published +15.7%.

Holding the sink support fixed does **not** shrink the mesh sensitivity of the peak; if anything it
is marginally larger. **Sink discretisation is not what drives the grid effect.**

This is consistent with what `T0_2b…` §4.2 predeclared: B-control *"controls the SINK, not the
FLOW"* and does **not** reach `cause`, because GWF and GWT stay tied to each mesh's DISV grid. The
arm establishes *"sink support was held fixed in the matched B arm"* — and that is all it may be
cited for.

⚠️ **`spatial_10m_cr0.9` was promoted from an S4 summary row to a full artifact for this
comparison.** That is a targeted exception to the "do not back-fill S4/S5" decision, taken because a
specific claim needed the metric — not a reversal of it. The other five S4/S5 points remain summary
rows.

### 3.3 The control lowers the peak, as expected

At 2 m the peak falls **6.1085 → 5.7771 (−5.43%)**. Spreading extraction over a 25 m disc draws
from a larger volume and dilutes the receptor concentration. This is the estimand changing — which
is exactly why `T0_2b…` §4.2 lists a changed estimand among the comparisons that may **not** be
cited as isolation.

## 4. Matrix status — 12 of 12

| arm | identities | how recorded |
|---|---|---|
| spatial 50 / 20 / 10 m | 3 | S4 summary (accepted) |
| spatial 5 / 2 / 1 m | 3 | full artifacts |
| temporal 50 m ×2 | 2 | S5 summary (accepted) |
| temporal 2 m ×2 | 2 | full artifacts, **re-emitted** with `run_role=temporal_series` |
| **B-control coarse + fine** | **2** | **full artifacts, `run_role=b_control`** |
