# ✅ Root cause: the Hub is not running the project's locked dependencies

**Settled 2026-08-28.** The nine Linux FAILs are **an environment mismatch, not a regression.**
The goldens are correct. The code is correct. **The Hub environment is wrong.**

| | golden (frozen) | Hub now | |
|---|---|---|---|
| **numpy** | **2.3.5** | **2.1.3** | 🔴 older |
| **flopy** | **3.9.5** | **3.9.3** | 🔴 older |
| python | 3.12.9 | 3.12.9 | ✅ |
| geos | 3.13.1 | 3.13.1 | ✅ |
| kernel | 6.8.0-124 | 6.8.0-136 | (not numerical) |

`uv.lock` pins **numpy 2.3.5** and **flopy 3.9.5** — exactly the versions the goldens were
frozen with. `pyproject.toml` only bounds them loosely (`numpy>=2.0`, `flopy>=3.9.2`), so the
Hub image satisfied the bounds with **older** releases and never matched the lock.

**The corroborating measurement:** a machine running the locked versions reproduces `botm` and
`strt` **bit-for-bit** against the goldens. On that machine the only differing members are
`gridprops__vertices` / `gridprops__cell2d_flat` (genuine Triangle cross-platform geometry) and
`riv_cond` downstream of them — `botm` and `strt` do **not** appear. The Hub, on older
libraries, differs in exactly `botm` + `strt` with **topology intact**.

## ❌ Two hypotheses this refutes — including a confident one of mine

1. 🔴 **`fe0cc4b` (the botm-floor fallback) is EXONERATED.** I built a detailed case from commit
   archaeology: it was the only commit touching the flow-grid import closure after the golden
   regen, it floors `rbot`, and `riv_rbot` is a hashed member. The member-level diff refutes it —
   **`riv_rbot` does not appear in any group's differing set.** `casestudy_flow_common:229`
   independently confirms it (`new["botm"] = ... # unchanged (no floor)`). *"Output-neutral" was
   accurate.* The hypothesis was plausible, well-evidenced, and wrong; this is why the diagnostic
   was built instead of acting on it.
2. **"The goldens are stale."** They are not. They are valid artifacts of a pinned environment
   that the Hub stopped providing.

## 🔴 The defect this exposed in the checking, not the model

`casestudy_flow_builder._golden_is_cross_platform()` guards on **OS alone**. But a golden pins
hashes of **floating-point arrays**, which are reproducible only in the environment that produced
them — *same OS is necessary, not sufficient*. Every manifest has always recorded `versions`;
**nothing ever compared them.** So a library mismatch surfaced as nine FAILs indistinguishable
from a real regression, and cost a full diagnostic cycle to tell apart.

### Fixed

`check_nine_mesh_goldens.py` now compares the recorded `versions` and reports **`ENV_MISMATCH`**
as an outcome of its own — *not* PASS, *not* FAIL:

- hashes are **not enforced** when the environment differs (they cannot distinguish cause);
- `is_full_a16_evidence` is **false** for such a run;
- the exit status is non-zero, so it can never pass silently in CI;
- the summary prints the offending libraries and says to install `uv.lock`.

⚠️ **Python is compared at `major.minor` only** — measured, not assumed: a machine on CPython
**3.12.10** reproduces `botm`/`strt` against goldens frozen on **3.12.9**. Comparing the patch
level would flag a conforming environment and make the check unusable. Kernel/platform strings
are not compared at all; a kernel bump is not a numerical difference.

### Also fixed: a misleading label in my own diagnostic

The first version bucketed `botm` as a *mesh* member, so it printed **"mesh intact: False"** for a
run whose mesh was in fact identical. `botm`/`top` are elevations **sampled onto** the topology,
not topology; `strt` follows `botm` through the `strt = max(strt, botm + 0.01)` clip, so the two
move together from one cause. Members are now reported in three buckets — **topology**,
**cell-properties**, **packages** — and only the first answers "did the mesh move".

## What to do

1. **Install the locked dependencies on the Hub** (`numpy 2.3.5`, `flopy 3.9.5`), then re-run.
   Under the locked environment the check should enforce hashes on 9/9.
2. **Consider tightening `pyproject.toml`.** `numpy>=2.0` / `flopy>=3.9.2` permits exactly the
   drift that happened. The goldens pin bit patterns; the dependency bounds should not be looser
   than what those bit patterns require.
3. **Manifests record library versions but no hash of the mother model.** A changed *input* would
   still be invisible. Worth closing separately — it is a different hole in the same wall.

## Status

**S3b remains blocked.** The A16 evidence still requires a run with hashes enforced on all nine,
and no such run exists yet. What has changed is that we now know the blocker is an environment
fix, not a model investigation.
