# 🔴 S3b BLOCKER — A16's nine-mesh regression evidence does not exist

**Status:** ✅ **CLOSED 2026-08-28 — S3b IS UNBLOCKED.**

The authoritative Hub (Linux) run passed with mesh-topology hashes **enforced on 9/9 groups**:

```
[PASS] group 0..8   (hashes ENFORCED)
9 passed, 0 failed, 0 inconclusive (environment), of 9 groups
mesh-topology hashes enforced on 9/9 groups
```

**The artifact is committed: `nine_mesh_check_linux.json`.** Every check verdict is `PASS` — no
`SKIP_CROSS_PLATFORM` anywhere — on the canonical calibration `6a9e27c455dcbb66`.

Getting there required finding why it first failed all nine — a drifted local mother model served
unverified by `ensure_flow_model`. See **`ROOT_CAUSE_MOTHER_MODEL_DRIFT.md`**, which also records
the three refuted hypotheses.

### ⚠️ One residual gap, visible in the artifact itself

Every record carries `"golden_flow_model_fingerprint": null` and therefore
`"flow_model_matches_golden": null`. The nine goldens were frozen **before** manifests recorded
the calibration they were built from, so **this run cannot prove it used the same calibration as
the goldens** — only that it used the one currently shipped.

That the field reads `null` rather than `true` is the guard behaving correctly: **absence is
reported as unknown, never as agreement.** It closes the next time the goldens are regenerated,
which will stamp `flow_model_fingerprint` into their manifests.
**Found:** 2026-08-27, while triaging six pre-existing test failures.
**Plan:** `DESIGN_DOCS/casestudy_golden_platform_plan.md` (DRAFT, **local-only —
`DESIGN_DOCS/` is gitignored**). This file is the tracked record of the obligation, so the
blocker survives even if the local plan does not.

## What A16 requires

> ⚠️ **Blast radius: `disv_grid_utils` also builds the NINE FROZEN case-study group meshes** —
> S3b must carry regression evidence for those, not just the transport suite.
> — `T0_1_C1_v2.md`, allow-list **A16**, lecturer signature 2026-08-27

## What existed before 2026-08-27 — measured, not assumed

⚠️ **Precision, because the first draft of this file overstated it:** *anchoring* did exist and
passed — `casestudy_flow_builder.assert_all_groups_anchored()` confirms every group is anchored
by a committed golden XOR a deferral, and all nine are **authoritative** (none provisional, none
deferred). But it performs **zero builds**, so it proves the artifacts are *present*, not that the
meshes still *reproduce*. What was missing was regression evidence, not anchoring.

| | |
|---|---|
| committed goldens | `group0` … `group8` — **nine** |
| groups the builder suite actually builds | **group 0 only** (`build_flow_state(0` ×8; no loop over nine) |
| groups **6** and **8** | **zero references in any test file** |
| groups 1–5, 7 | referenced only in *other* files (canonical mapping, refine reliability, pinned loader) — not as builder golden-hash regressions |

**And group 0's own coverage does not currently run.** Six golden-hash assertions in
`_SUPPORT/tests/test_casestudy_flow_builder.py` fail on macOS, because the goldens are **Linux
hub oracles** (`0574b46`) and the Triangle/Voronoi mesh is platform-dependent. The failure is
deterministic — byte-identical across runs — so it is platform drift, not nondeterminism:

```
expected (golden) 95e35bf00e45fd03ff1e2b33147d0b4a97244c5f600e3a46f779bc12c043cb4a
actual   (macOS)  2ba3bd7891b67aeb38c26bc8ad06dab1052cb3014c0c2f5f2d17cd5b3d0bf09e
```

`casestudy_flow_builder._golden_is_cross_platform()` already detects this correctly (golden
gen-OS `Linux`, current `Darwin` → `True`) and `TestRegressionGuardAgainstCommittedGolden`
skips. **Only that one class calls the guard**; the six failing assertions never do.

⚠️ **These six are NOT a regression** — verified identical at `2a5c6a8`, before the 2026-08-27
A17 work, on a detached worktree.

## Why this blocks S3b

S3b changes `disv_grid_utils.py`, which builds all nine meshes. What the measured facts support,
stated precisely:

> **Builder golden-hash regression coverage currently exercises group 0 only, against
> Linux-generated goldens — and on macOS those assertions do not run at all.**

⚠️ **The narrow claim is the defensible one.** It does **not** follow that `disv_grid_utils.py`
is tested *only* through group 0: other test files reference groups 1–5 and 7 and may exercise
invariants that utility affects. Equally, a *reference* to a group is not proof of construction
or of meaningful regression coverage. What the facts establish is the absence of **nine-mesh
golden regression evidence**, which is precisely what A16 names — not a broader claim about all
testing of that module.

So S3b cannot produce the evidence A16 requires. Six permanent reds also mean a genuine failure
would land in an already-red file and go unremarked.

## What has to be decided first

**Is Linux the authoritative enforcement platform, or must macOS enforce too?** That choice
changes the fix, so it comes before any implementation:

- **Linux authoritative** → guard the topology-hash assertions, and the Hub run *is* the
  evidence. Matches how the goldens were made.
- **macOS enforces too** → wait on **M2**'s pinned mesh artifacts (locked decision #5: students
  load, never regenerate), so the hash becomes platform-independent by construction.

Either way, a separate decision is needed on **groups 1–8**: extend builder coverage to all nine,
or record explicitly that A16's evidence is Hub-only and produced by a named command outside
pytest.

## How to produce the evidence

```bash
uv run python _SUPPORT/src/scripts/check_nine_mesh_goldens.py \
    --json DOCUMENTATION/contracts/evidence/s3b/nine_mesh_check_linux.json
```

Rebuilds all nine groups and compares each against its committed golden, in two classes:

| class | checks | enforced |
|---|---|---|
| **platform-independent** | refine radius · flow mass balance · convergence · finite heads · no dry cells | **always, every OS** |
| **platform-dependent** | grid aggregate hash · canonical array/package hashes · faithful-RIV hash | **only on the golden's generation OS** |

So a non-authoritative run is not vacuous — it still catches a radius walk landing somewhere new,
a solver regression, or a broken flow field in any of the nine. But it is **not the pin**:
`is_full_a16_evidence` is `true` only when all nine passed **and** the hashes were enforced on
every one. Skipped hashes are reported as `SKIP_CROSS_PLATFORM`, never folded into the pass count.

🔴 **The mechanism can fail** — negative controls in `_SUPPORT/tests/test_nine_mesh_goldens.py`
corrupt a golden in a temporary copy and assert `FAIL` is reported. A check that cannot fail is
not evidence.

## Status of the runs

| platform | result | is A16 evidence? |
|---|---|---|
| **macOS** (`nine_mesh_check_macos.json`) | **9 passed / 0 failed**, hashes enforced on **0/9** | ❌ **no** — hashes skipped cross-platform |
| **Hub (Linux)** | ⏳ **NOT YET RUN — this is what remains** | — |

## What was fixed in the test suite (2026-08-27)

The six failing assertions no longer enforce a Linux pin on macOS:

- **four pure topology-hash assertions** now carry `@requires_same_platform_golden`, whose skip
  reason names where the pin *is* enforced;
- **two package-hash assertions** were **split** rather than skipped, because their intent is not
  the hash. The platform-independent part (spec self-consistency, doublet-cell membership) runs
  on every OS; only the golden-geometry comparison is guarded.

⚠️ **A false PASS was found and removed while doing this.** Several of those golden comparisons
were `!=` assertions — off the generation OS every hash differs anyway, so they could not fail
and were green for the wrong reason. `test_casestudy_flow_builder.py`: **6 failed → 0 failed,
38 passed, 12 skipped**.

## Not in scope

Regenerating the goldens (they are valid on their own OS) · making Triangle deterministic across
platforms (M2a.5 established it is not feasible; pinning is the adopted answer) · group 1's
documented deferral (`group1_flow.deferral.json`).
