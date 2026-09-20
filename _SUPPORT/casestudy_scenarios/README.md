# Case-study scenario pipeline (instructor-only)

These files are the **instructor** scenario-assignment / QA artifacts for the flow +
transport student case studies. They are **deliberately NOT** in
`PROJECT/workspace/template/` — students copy that template into their group folder,
and these files hold **all 13 groups'** scenario assignments (concession, contaminant,
thresholds, doublet coordinates), so shipping them in the student copy would leak the
full assignment set across groups. They are generated, not hand-edited.

## Contents

| File | Produced by | What it is |
|---|---|---|
| `doublet_table.{csv,yaml}` | `casestudy_doublet_roster.py` (M1.1) | the 13 GWHE doublet geometries + licensed-max Q, from the well registry |
| `canonical_mapping.{csv,yaml}` | `casestudy_canonical_mapping.py` (M1.2) | canonical group → concession → flow-scenario → contaminant mapping |
| `repairing_ledger.csv` | `casestudy_canonical_mapping.py` | per-group re-homing record (transport → canonical flow concession). Its "original" column comes from the frozen `pre_reconcile_concessions.csv`, **not** from the live transport config — see below |
| `pre_reconcile_concessions.csv` | hand-frozen from `d4e30e0^` | the pre-reconcile transport concession per group (**groups 0-8 only** — it is frozen at the M1.3a roster; see below); the INPUT that makes the ledger reproducible |
| `threshold_sanity.csv` | `casestudy_canonical_mapping.py` | deterministic threshold-vs-reference-band sanity flags |
| `coherence_ledger.csv` | `casestudy_reconcile_configs.py` (M1.3) | config-reconciliation QA (recirc/upgradient re-derivation flags) |

The two **inputs** these read/rewrite — `case_config.yaml` and
`case_config_transport.yaml` — stay in `PROJECT/workspace/template/` (they are the
student-facing configs).

## Regenerating

Run from the repo root. `_SUPPORT/src` is **not** importable by default — nothing in
`pyproject.toml` puts it on `sys.path`; the test modules each insert it themselves — so
`PYTHONPATH` is required or `python -m` fails with `No module named ...` before the
generator runs. The `PYTHONPATH` below is relative, which is why the repo root is still the
place to run from; the *outputs* are anchored to the module file and land here either way:

```bash
PYTHONPATH=_SUPPORT/src uv run python -m casestudy_doublet_roster      # -> doublet_table.{csv,yaml}
PYTHONPATH=_SUPPORT/src uv run python -m casestudy_canonical_mapping   # -> canonical_mapping.{csv,yaml}, repairing_ledger.csv, threshold_sanity.csv
PYTHONPATH=_SUPPORT/src uv run python -m casestudy_reconcile_configs   # -> coherence_ledger.csv (+ rewrites the two configs in place)
```

⚠️ These rewrite tracked files. `uv run pytest` deliberately does **not** regenerate them;
regeneration is manual. `test_COMMITTED_mapping_is_not_stale_against_the_live_configs`
catches the consequence of forgetting — a committed mapping whose recorded input hashes no
longer match the live configs — but nothing detects a `write=True` reintroduced into the suite.

Only the first two take no arguments — they start work immediately on import of `__main__`,
so there is no `--help` to inspect first.

Tests (`_SUPPORT/tests/test_casestudy_{doublet_roster,canonical_mapping,reconcile_configs}.py`)
assert these committed files exist and are internally consistent.

> **Note:** the currently committed copies were generated from an earlier checkout and
> embed absolute developer paths in their `*_file` provenance columns. Regenerating here
> refreshes them; a follow-up to relativize those provenance columns in the generators is
> tracked separately.

## ⚠️ Why `pre_reconcile_concessions.csv` exists

The repairing ledger records a **one-time** re-homing: each contaminant scenario was moved
off its original transport concession onto the canonical flow doublet. The generator used to
read that "original" concession from the **live** transport config — which is now the
*reconciled* one. So running the regenerate command above, exactly as documented, produced
nine `changed=False` rows and **overwrote the original concession ids**.

This README said the file was generated; the tests said it was a frozen pre-reconcile
snapshot. Both were true, and following the README destroyed history.

The pre-image is now frozen in `pre_reconcile_concessions.csv` (recovered from `d4e30e0^`,
verified 2026-08-31 against the nine `original_transport_concession` values the ledger
held then), the generator reads it, and regeneration
reproduces the ledger **byte-for-byte and idempotently**. A group absent from that file was
never re-homed — a case added after the reconcile — and is recorded as unchanged with a note
saying so. That is not a hypothetical: the roster has since grown from nine to 13, and groups
9-12 appear in the ledger as `changed=False` carrying exactly that note, with no hand-editing.
