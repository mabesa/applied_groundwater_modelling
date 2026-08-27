# 🔴 The authoritative Linux run FAILED all nine — the goldens are STALE, not drifted

**Run:** JupyterHub (Linux), `main` @ `a6aa8c4`, 2026-08-27.
**Result:** `0 passed, 9 failed`, **mesh-topology hashes enforced on 9/9 groups**.
`is_full_a16_evidence: false`. **S3b remains blocked.**

This is the run that was supposed to close the A16 gap. It did the opposite, and what it
found is more useful than a pass would have been.

## 1. This is NOT cross-platform drift

The goldens were generated **on the Hub** (`0574b46`, *"Linux hub oracles"*). The Hub now
**fails to reproduce its own goldens**. Three distinct hashes exist for group 0:

| source | aggregate hash |
|---|---|
| committed golden (Linux, 2026-07-23) | `95e35bf00e45…` |
| macOS rebuild (2026-08-27) | `2ba3bd7891b6…` |
| **Linux rebuild (2026-08-27)** | **`a4fc7f956f2c…`** |

All nine groups failed the same way. Cell counts are unchanged (group 0 builds **4105
cells** on both platforms), so the mesh has not been resized — the hashed content changed.

## 2. 🔴 The six red macOS tests were masking this

The cross-platform guard skipped the topology assertions on macOS, and **nothing enforced
them on Linux** because no test built groups 1–8 and the group-0 assertions were part of
the six that had been failing for other reasons. The staleness has therefore been
invisible since **2026-07-24**.

⚠️ This is the exact hazard the plan named: *"six permanent reds mean a genuine failure
would land in an already-red file and go unremarked."* It had already happened.

## 3. Prime suspect: `fe0cc4b`, recorded as "output-neutral"

Exactly **one** commit touches the flow-grid import closure after the golden regen:

```
0574b46  2026-07-23  regenerate 8 flow goldens on the 2,160 m3/d field (Linux hub oracles)
fe0cc4b  2026-07-24  casestudy(riv): implement botm-floor fallback for the all-overbank case
```

`fe0cc4b` *"FLOORS each emitted `rbot` up to that cell's `botm`"*. **`riv_rbot` is a hashed
canonical member** (`members` in every manifest), so flooring it necessarily changes
`array_hashes["riv_rbot"]` and therefore `aggregate_hash`.

> **"Output-neutral" was true for heads and mass balance. It was never true for hashes** —
> and the goldens pin hashes.

The Hub log shows the fallback firing on group 1:
`reach (0, 1785) all-overbank -> BOTM-FLOOR fallback: rbot 396.098 raised to cell botm (+0.056 m)`

⚠️ **Not yet proven for all nine.** The fallback visibly fires only on group 1, yet all nine
hashes differ. Either the commit changed `rbot` handling on the non-fallback path too, or a
second cause exists. **Do not close this on the hypothesis alone** — §5 is how to settle it.

## 4. My changes are NOT the cause

The flow builder's import closure is `casestudy_flow_common`, `casestudy_refine_riv`,
`model_io_utils`, `case_utils`, `casestudy_diagnostics`, `casestudy_flow_scenarios`.
**None** of the 2026-08-27 A17 files (`transport_srcpulse_demo.py`, `t0_gate_harness.py`,
`t2_*.py`) appear in it, and `transport_srcpulse_demo` is not imported by the flow path at
all. The staleness predates this work by a month.

## 5. How to settle it — member-level diff

`check_nine_mesh_goldens.py` gained a `--diagnose` mode, because the builder's pin raises
before any comparison can say *which* member moved:

```bash
python _SUPPORT/src/scripts/check_nine_mesh_goldens.py --diagnose \
    --json DOCUMENTATION/contracts/evidence/s3b/nine_mesh_diagnose_linux.json
```

It reports, per group, `mesh members differing` vs `package members differing`. The two
outcomes mean very different things:

| Linux result | reading | action |
|---|---|---|
| `mesh intact: True`, only `riv_*` differ | ✅ confirms §3 — a package array changed, the mesh did not | regenerate goldens, or restore rbot behaviour |
| mesh members (`gridprops__*`) differ too | 🔴 the **mesh itself** moved on its own platform — a second, worse cause | stop; do not regenerate until understood |

For reference, the macOS `--diagnose` on group 0 reports
`mesh intact: False · mesh: [gridprops__cell2d_flat, gridprops__vertices] · package: [riv_cond]`
— `ncpl` is NOT among them, matching the identical 4105 cell count. That is the expected
cross-platform signature, and it is *not* what Linux should show if §3 is right.

## 6. What this does NOT license

**Do not regenerate the goldens to make the check pass.** That would delete the only
evidence that something changed. The goldens are the record of a reviewed, frozen state;
regenerating them is a decision about whether `fe0cc4b`'s rbot change is *wanted* in the
frozen artifact — a lecturer call, taken after §5 identifies the cause, not before.
