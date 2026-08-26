# Hub measurement — 2026-08-26 (first Hub data recorded in this project)

**Platform:** `Linux-6.8.0-136-generic-x86_64`, glibc 2.39, Python 3.12.9.
**Compared against:** macOS-arm64, same script, same workload, 2026-08-26.

---

## Result 1 — ✅ `H = 2.30` measured. The fine run projects **BELOW the ceiling**

**Measured by the gate qualification itself** — the transport solve, i.e. the workload that matters —
after the setup problems of §4 were cleared.

| | macOS-arm64 | Linux Hub |
|---|---:|---:|
| per side | mean **14.61 s** (min 14.35 · max 15.00) | **35.69 s** · **31.60 s** |
| mean | **14.61 s** | **33.65 s** |

> **`H = 2.30`** (range **2.24 – 2.35** against the macOS max/min).

| | |
|---|---:|
| fine run, fast Mac | 316 s |
| **projected on Hub** | **728 s** (709 – 741) |
| `HUB_FINE_TARGET_S` | 600 s → **above target** |
| `HUB_FINE_CEILING_S` | 900 s → ✅ **below the ceiling** |
| headroom | **172 s (19%)** |

> ✅ **Verdict: PASSES WITH A RECORDED WARNING.** Per `T0_0…` §6, between target and ceiling the fine run
> passes but students on a **loaded** Hub will feel it. **T2 does not take its failure edge.**

### 🔴 This CORRECTS the earlier proxy figure — which would have triggered a false failure edge

An earlier entry in this file reported `H ≈ 2.9–3.0`, derived from the **fingerprint stage as a proxy**
(macOS 6.20 s vs Hub 18.54 s). **The proxy overestimated by 28%**, and on that figure the fine run
projected to 921–945 s — **above** the ceiling, which would have sent T2 to its pre-declared failure edge
for no reason.

**Why it was wrong:** PRT particle tracking and a GWT transport solve are different workload mixes, and
they do not scale together across architectures. The proxy was honestly labelled a proxy, but the lesson
is sharper than that — **a same-script, same-workload comparison across platforms is still not a
substitute for measuring the workload you actually care about.**

### ⚠️ What this figure does and does not support

- **`n = 2` side-runs**, and they differ by **12.2%** (35.69 vs 31.60). `H = 2.30` is a two-sample mean,
  not a converged one. Five more `qualify` invocations would give parity with the macOS six-pair record.
- 🔴 **316 s is a FLOOR, not the cost.** That run sat on `nstp_cap = 2000`, so `cr_target = 0.9` may never
  have been reached. If the uncapped demand is higher, the 19% headroom shrinks — and it is the only thing
  standing between this result and the failure edge.
- **Hub load is not controlled.** This was one session on an otherwise-quiet machine.

## Result 2 — ✅ The capture fingerprint is IDENTICAL across platforms

| | macOS-arm64 | Linux Hub |
|---|---:|---:|
| `capture_halfwidth_m`, 5 fresh runs each | **53.125 m** ×5 | **53.125 m** ×5 |
| `stdev` · `spread_rel` | 0.0 · 0.0 | 0.0 · 0.0 |

**Not "within 24%" — identical to the digit, on both platforms, ten runs in total.**

### 🔴 This contradicts `T0_2b…` §2.6, and there is a likely explanation

§2.6 states: *"Platform-sensitive: ~24% Mac↔Hub spread on the bisected half-width
(`test_transport_prt_capture.py:664`)"*, and on that basis `≈53 m` "may never be quoted as a grid-supported
value without a platform qualification".

Reading the cited line, the 24% is attributed there to a **different quantity**:

> *"`max_captured_offset_m` is a SAMPLING statistic on a highly mesh/platform-dependent geometric quantity
> (~24% macOS↔hub spread observed for the related half-width)"*

and the **very next test** — `test_halfwidth_is_stable_across_probe_radii_but_max_offset_is_not` — draws
exactly this distinction: `max_captured_offset_m` "is a lower bound, not a capture-zone half-width", while
`halfwidth_at_spill_m` "is the real thing: the captured/escaped boundary BISECTED".

**So the ~24% appears to have been observed on the explicitly-unstable sampling statistic and then attached
in the contract to the stable bisected quantity.** The measurement above is direct evidence for the
bisected one.

> 🔴 **NOT changed unilaterally.** §2.6 is signed text and this is the lecturer's call. Two consequences if
> the figure is re-attributed:
> - **S10's `capture_halfwidth_m` comparisons could be enabled** — it is currently *descriptive-only*, and
>   every comparison raises for want of exactly this envelope.
> - **The mandatory "platform qualification" on `≈53 m` may be unnecessary**, at least between these two
>   platforms.
>
> ⚠️ Ten runs across two platforms and one toolchain each. It does **not** license "platform-independent"
> in general — a third platform, or a different MF6/Triangle build, remains unmeasured.

---

## Result 3 — ✅ The gate is qualified Hub-side, on ONE pair

`qualify` returned **PASS** on Linux x86_64: both cold side-runs OK, payloads exactly equal, no environment
mismatches. **`T0_0…` §5.1's "a Hub-side T1 gate would need its own qualification" is now met** — the gate
works on the platform students actually use.

⚠️ **On one pair, not six.** One `qualify` invocation is **one pair / two cold side-runs**; §5.1's
"6 pairs, 12 cold side-runs" came from six separate invocations. So the Hub evidence is **1/6 the
sampling** of the macOS record, and in particular the **SIGILL rate is 0/2 here against 0/12 there** —
much weaker evidence about a hazard repo memory once put at ~40% on macOS-arm64. Five more invocations
would give parity and cost ~10 minutes.

---

## 4. Why the qualification stage aborted — and the fix

```
repo config.py not found -- cannot propagate the data-source config to the worktrees
(both sides would silently diverge onto config_template.py)
```

`config.py` is **gitignored**, so a fresh Hub checkout never has one, while the gate harness requires it to
propagate the data-source config into both worktrees. The fingerprint stage was unaffected, which is why
the failure was invisible until the harness aborted.

**Fix, from the repo root on the Hub:**

```bash
cp config_template.py config.py          # defaults (limmat / dropbox) are what the Hub wants
python _SUPPORT/src/scripts/hub_measurement.py --workdir ~/hub_meas --skip-fingerprint
```

🔴 **Plain `python`, not `uv run` — `uv` is NOT installed on the Hub.** The runbook originally said
`uv run python`, which is a dev-machine habit; the JupyterHub environment already carries the
dependencies, and the script uses `sys.executable` so every subprocess inherits the launching
interpreter.

🔴 **The second attempt then failed on a leftover worktree** — `worktree path already exists:
~/hub_meas/qualify/worktree_A`, created before the first run aborted. `rm -rf` alone would not have been
enough: git keeps the worktree REGISTERED in repo metadata, so a prune is required too. **The script now
clears both automatically** before each qualification run.

`--skip-fingerprint` because result 2 is already settled — this second run only needs questions 1 and 2,
and will take ~15 min rather than ~25.

**The script now preflights this** (added the same day), so a missing `config.py` or flopy bin directory
fails in one second with the fix printed, instead of minutes in.
