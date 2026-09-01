# T2 · S15 — the default grid stays at 10 m

**Decision: KEEP 10 m.** Lecturer, 2026-09-01. `LOCKED_PARAMS["refined_cell_size"] = 10.0` —
unchanged. **No code changes**; the decision is to leave the default where it is.

S15 is the one T2 step that can change which model students run. It costs nothing to execute:
everything below was measured in S4–S14.

---

## The evidence

| grid | wall (Mac) | `peak_mgL` |
|---:|---:|---:|
| **10 m — the default** | **19.6 s** | **5.2770** |
| 5 m | 54 s | 5.8765 |
| 2 m | 650 s | 6.1085 |
| 1 m | 5 756 s | 6.1322 |

The grid-independent peak is ≈ **6.13**. The default reports **5.277** — **14% low**.

**Why keep it anyway:**

1. **Iteration.** 20 seconds lets a student try something, get it wrong, and try again. At 11
   minutes (2 m) they run once and accept whatever comes out.
2. **The lesson is built on this contrast.** `04t`'s *"What the grid costs you"* teaches the 14%
   deficit and the ~290× speed-up directly. A 5 m default would rewrite that lesson around a
   smaller, less legible gap.
3. **Being 14% low is only a problem if reported as the truth** — and the notebook already teaches
   students not to. That is the point of the section.

**5 m was the real alternative** — about a minute, only 4% low — and is recorded as considered and
rejected: the extra minute costs more than the accuracy buys, given point 3.

## ⚠️ What this decision does NOT claim

**The concentration error still matters.** 14% is not negligible, and nothing here says otherwise.
The judgement is that for *this* exercise the teaching benefit and iteration speed outweigh it —
not that the number is unimportant.

🔴 **The stable-verdict claim is bounded.** S14 returned
`decision_supported_magnitude_sensitive` for the **9 threshold-decision components it could
evaluate**. That is a statement about those nine, over the grids tested. It is **not** a statement
that every outcome in the notebooks is grid-stable: **13 components could not be evaluated at all**
(no threshold-record file exists; the particle-tracking metric was never wired in), and a further
63 were dispositioned `not_evaluated` at S1. Reading "the verdict survives the grid" as covering
those would overstate the evidence considerably.

## When to revisit

This decision is not permanent. Re-open it if any of these change:

- **The compliance threshold** — a lower limit would sit closer to the 14% band, where the verdict
  might stop being stable.
- **The learning goal** — if a student deliverable ever needs the peak *magnitude* rather than the
  compliance verdict, 10 m is the wrong default for it.
- **Runtime** — a faster Hub, or a cheaper mesh, changes the iteration argument that carries most
  of the weight here.
- **The evidence** — in particular if the 13 unevaluated components become evaluable and any of
  them turns out to be grid-sensitive.

## Scope

`T0_5…` §4: *"Deciding the notebook default grid does not discharge the case-study fine-run
requirement. They are different obligations sharing one threshold."* This decision covers the
**notebook** default only.
