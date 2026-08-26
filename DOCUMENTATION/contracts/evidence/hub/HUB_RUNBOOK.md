# Hub measurement runbook

**One session settles three open questions.** They share the same access, so they are one command plus a
paste-back — not three errands.

**The Hub deploys `main`**, so this must be merged before it can be run there.

---

## Run it

```bash
uv run python _SUPPORT/src/scripts/hub_measurement.py --workdir ~/hub_meas
```

Roughly **15–25 minutes**, most of it the gate qualification. It prints progress to stderr and **one JSON
block to stdout — paste that back verbatim.** Nothing is written into the repo.

If the fingerprint stage is slow or noisy, `--skip-fingerprint` still delivers questions 1 and 2, and
`--fingerprint-reps N` changes the replication count (default 5).

---

## What it settles

### 1. The Hub multiplier `H` — the cheapest outstanding action in the project

Every runtime in the design docs is a fast Mac; **no Hub runtime is recorded anywhere in the repo.** The
frozen budget turns on this number:

| Constant | Value | Meaning |
|---|---:|---|
| `HUB_FINE_TARGET_S` | 600 s | intended operating point — passes cleanly |
| `HUB_FINE_CEILING_S` | 900 s | **hard pass/fail** (half the 1800 s wall) |

The corrected-Courant 2 m corridor takes **~316 s on a fast Mac**. At an illustrative `H = 3` that is
**≈948 s — already over the ceiling**, at which point **T2 fails** and takes a declared failure edge: back
to T1 for a cheaper `GridSpec`, or to T0 to revise the threshold. It explicitly **may not** pass by
reclassifying the mandatory fine run as optional.

⚠️ That 316 s run also **sat on the `nstp_cap` of 2000**, so `cr_target = 0.9` may not even have been
reached — the true cost could be higher than 316 s × H.

**Baseline it compares against** — the macOS qualification of 2026-08-20:
**min 14.35 s · mean 14.61 s · max 15.00 s per side.** The script reports `H = hub_mean / 14.61`.

### 2. The gate's Hub-side qualification

`T0_0…` §5.1 passed on macOS-arm64 and says so plainly: *"it makes **no** claim about the Hub, and a
Hub-side T1 gate would need its own qualification."* The same `qualify` run supplies this **and** the
timings for (1) — which is why they are one command and not two.

It also re-measures the **SIGILL rate**, which is 0/12 on macOS against a repo-memory claim of a historical
~40% on macOS-arm64. A Hub figure is a second independent sample.

### 3. S10's capture-fingerprint repeatability envelope

`capture_halfwidth_m` carries a **~24% Mac↔Hub spread** against `TOL_WIDTH_REL = 5%`. S10 therefore records
it as **descriptive-only** and **refuses every comparison** until a measured envelope exists below tolerance.

> 🔴 **macOS baseline, measured 2026-08-26 (this runbook's own script, n = 5, fresh processes):**
> **`53.125 m` on all five runs — `stdev = 0.0`, `spread_rel = 0.0`.**

**That is a useful finding and it narrows the question.** The metric is *bit-deterministic across fresh
processes on one machine*, so the ~24% is **cross-platform**, not run-to-run noise — which is a weaker
problem than "the metric is unstable in general".

⚠️ **It does not settle it.** Five runs on one lightly-loaded machine say nothing about a **loaded** Hub,
different core counts, or a different MF6/Triangle/FloPy build. The Hub number is what decides whether S10's
comparisons can be enabled.

---

## Reading the output

| Field | What it means |
|---|---|
| `qualification.passed` | question 2 — the gate is qualified Hub-side |
| `multiplier_H.H` | question 1 |
| `multiplier_H.projected_fine_run_s` | `316 × H` |
| `multiplier_H.verdict` | clean pass · pass-with-warning · **T2 fails** |
| `fingerprint_repeatability.envelope.spread_rel` | question 3, against the 5% tolerance |
| `fingerprint_repeatability.envelope.verdict` | whether S10 comparisons may be enabled |

**Hand the JSON back and I fold the numbers into the contracts** — T0.0 §6's open item 2, T0.5's
feasibility risk, and S10's descriptive-only status.

⚠️ **Do not edit the constants to fit the measurement.** `HUB_FINE_CEILING_S` was frozen *before* measuring
precisely so the outcome could not be renegotiated afterwards; changing it after the fact is a **failure
edge to T0**, not an edit.
