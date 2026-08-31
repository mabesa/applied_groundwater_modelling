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
digit, same `nstp`). Only the label changed — which also demonstrates the runs are deterministic.

## 3. What B-control shows

| mesh | | `nstp` | `peak_mgL` | `t_peak` |
|---|---|---:|---:|---:|
| 10 m | uncontrolled | 122 | — | — |
| 10 m | **B-controlled** | **86** | 4.9123 | 38.953 |
| 2 m | uncontrolled | 1 979 | 6.1085 | 37.653 |
| 2 m | **B-controlled** | **371** | 5.7771 | 38.245 |

### 3.1 Most of the fine-mesh timestep cost is the SINK, not the plume

At 2 m the control cuts `nstp` from **1 979 to 371 — 5.3×**. At 10 m it is only 1.4× (122 → 86).

The single-cell sink puts the entire pumping rate on one cell, creating a velocity singularity that
**sharpens as the mesh refines**. Courant sizing then pays for that singularity. Spreading the same
rate over a fixed 25 m disc removes it, and the asymmetry between meshes is the signature.

> **The expensive part of refining this model is not resolving the plume — it is resolving an
> artefact of how the well is discretised.**

### 3.2 🔴 But the grid sensitivity SURVIVES the control — a negative result

| | coarse → fine `peak_mgL` |
|---|---|
| **B-controlled** (10 m → 2 m) | **+17.60%** |
| uncontrolled (10 m → 2 m) | ≈ +15.7% |

Holding the sink support fixed does **not** shrink the mesh sensitivity of the peak; if anything it
is marginally larger. **Sink discretisation is not what drives the grid effect.**

This is consistent with what `T0_2b…` §4.2 predeclared: B-control *"controls the SINK, not the
FLOW"* and does **not** reach `cause`, because GWF and GWT stay tied to each mesh's DISV grid. The
arm establishes *"sink support was held fixed in the matched B arm"* — and that is all it may be
cited for.

⚠️ **The uncontrolled 10 m peak is not a registered metric.** S4 recorded `ncpl`/`nstp`/wall for the
cheap points but not `peak_mgL`, so the ≈ +15.7% above is derived from `04t`'s published series
(+11.4% then +3.9%), not from an artifact. The controlled +17.60% IS from artifacts. Stated as an
approximate comparison, not as a measured contrast.

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
