# 🔴 S3b BLOCKER — A16's nine-mesh regression evidence does not exist

**Status:** OPEN. **S3b must not start until this is resolved.**
**Found:** 2026-08-27, while triaging six pre-existing test failures.
**Plan:** `DESIGN_DOCS/casestudy_golden_platform_plan.md` (DRAFT, **local-only —
`DESIGN_DOCS/` is gitignored**). This file is the tracked record of the obligation, so the
blocker survives even if the local plan does not.

## What A16 requires

> ⚠️ **Blast radius: `disv_grid_utils` also builds the NINE FROZEN case-study group meshes** —
> S3b must carry regression evidence for those, not just the transport suite.
> — `T0_1_C1_v2.md`, allow-list **A16**, lecturer signature 2026-08-27

## What exists — measured, not assumed

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

## Not in scope

Regenerating the goldens (they are valid on their own OS) · making Triangle deterministic across
platforms (M2a.5 established it is not feasible; pinning is the adopted answer) · group 1's
documented deferral (`group1_flow.deferral.json`).
