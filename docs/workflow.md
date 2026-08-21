# Workflow conventions

How work is planned, reviewed and landed in this repo. `CLAUDE.md` points here for the full conventions.

---

## 1. The loop

**brief → adversarial review → fold → implement → verify independently → commit.**

It is slower than writing the code directly and it keeps paying for itself. On the transport milestones it
caught, among others: a headline finding derived from a checkout 19 commits behind `origin/main`; an
allow-list entry that would have authorised the *wrong fix*; and an implementation whose one moved test
had three missing imports and had never been run.

**Every step is written down before it is built.** Briefs live in `DESIGN_DOCS/` (gitignored, local);
frozen contracts live in `DOCUMENTATION/contracts/` (tracked).

🔴 **Anything in `DESIGN_DOCS/` that something else *depends on* is a bug waiting.** That directory is
gitignored, so a dependency on it breaks on a clean clone. This has been hit **three times** — an
allow-list entry citing a gitignored vision doc, an amendment rule citing a gitignored plan, and a gate
reading a gitignored pattern file. If it is load-bearing, it belongs in a tracked file.

---

## 2. Adversarial review with `codex`

Plans and briefs are reviewed by `codex` before execution — and, increasingly, **decisions are reviewed
after they are made**. Two decisions were reversed on substance that way.

### Invocation

```bash
codex exec --skip-git-repo-check -c model_reasoning_effort="medium" -C <dir> "$(cat prompt.md)"
```

🔴 **Always set `model_reasoning_effort`.** The default is `xhigh`, which blows a 10-minute timeout even on
a small self-contained input. Same review: **timed out at `xhigh`, 64 s at `medium`, 21 s at `low`** — and
the low-effort run still returned a correct verdict that changed the decision. If `medium` times out, drop
to `low` rather than retrying. Latency is variable at every effort level, so a timeout is worth one retry.

🔴 **Run it in the foreground.** Backgrounded (`nohup … &`) runs are killed mid-execution **and still exit
0**, leaving a file of tool-trace with no verdict.

⚠️ A trivial health probe answers in ~5 s at any effort, so `CODEX OK` tells you **nothing** about whether
a real review will finish.

### Getting a useful review

- **Pre-extract the evidence into a scratch pack.** One markdown file with the relevant code excerpts and
  the decision text, in a scratch dir, plus *"read ONLY this file, do not explore"*. Exploration is where
  the time goes; reasoning is what you want.
- **Say what it flagged last round and how the revision responded** — including anything you *rejected*,
  asking it to confirm or refute. It has conceded its own findings that way.
- **Ask for a verdict plus "the single most important remaining fix."** Keeps rounds converging.
- **Cap what it re-reads.** A prompt that says "read these six files" spends the budget reading.

### Reading the result

- **Verify its claims before accepting them.** Right on substance, wrong on detail more than once.
- **A concept it endorses is not the wording you then write.** Show it your actual text before treating
  earlier agreement as approval — a rule it approved in principle was rejected on its wording.
- **When it says an enumeration keeps being incomplete, replace the enumeration with a command.**

---

## 3. Delegating implementation

- **State the authorised surface explicitly, and say that touching anything else means stopping and
  reporting.** An agent once made three unauthorised edits — all plausibly right, none declared.
- **Require foreground test runs.** Agents have stalled repeatedly waiting on backgrounded `pytest`.
- **Ask for what could NOT be satisfied, and for decisions the brief did not determine** — stated as the
  agent's own reading rather than folded in silently. This is where the real findings surface: one agent
  correctly refused a brief instruction that would have moved a frozen number.
- **Verify the claims yourself**: run the suite, run the gate, diff against the authorised surface.

---

## 4. Committing

- 🔴 **`git add -A` is banned.** It once swept a parked workstream's untracked file into a commit. Always
  stage explicit paths.
- **Do not commit while an agent is mid-edit** — the pre-commit hook stashes and restores unstaged files,
  which is not something to run concurrently with another writer.
- **Commit messages say why, not what.** The diff shows what changed; the message explains the trap that
  made the change necessary and what was deliberately *not* changed.
- **Check merge state with `gh pr view`, not by looking at `origin/main`** — and `git fetch` first. Both
  failure directions have happened: reporting a merged PR as open, and an open one as merged.

---

## 5. Contracts and signatures

Frozen contracts live in tracked `DOCUMENTATION/contracts/`, carry a signature, and change only through a
recorded amendment.

- **Changing signed text is a failure edge, never an in-flight edit.**
- **The allow-list is exhaustive**: a change to an enumerated surface that is not on the list is a
  **defect**, not a change. Check authority *before* writing the brief — a step was drafted, reviewed and
  nearly built before anyone noticed it had no surface authority at all.
- **Amendments** may correct an enumeration error without a signature, but only under C1 §3.1's test:
  quote **one Appendix B bullet** in full naming the surface and the obligation, and have it confirmed by
  a **named reviewer who is not the author** before it takes force. Anything else needs a signature.
- ⚠️ **The recurring failure is a derivation presented as a quotation** — "it would not really be X
  without Y". Three amendments died on it. If the authority must be argued for, it is not enumeration.
- **Signatures are the lecturer's**, never assumed.

---

## 6. Verification

- **Run the canonical gate on a committed candidate** after every step that touches model code:
  ```bash
  uv run python _SUPPORT/src/scripts/t0_gate_harness.py compare --workdir <fresh-dir> --candidate <sha>
  ```
- ⚠️ **Know what the gate cannot see.** It reflects one builder's payload — it is blind to most units,
  and to PRT entirely. Named tests are the safety argument; `compare` is the backstop.
- **Where the gate is blind, prove it another way.** One step was verified by 200 randomised comparisons
  against the pre-change implementation.
- **Confirm pre-existing failures are pre-existing** by running them against a stashed tree, and say so
  rather than implying the suite is green.

---

## 7. Package manager

`uv` only — `uv run python`, `uv run pytest`, `uv run ruff check`. Never pip, conda or poetry.
