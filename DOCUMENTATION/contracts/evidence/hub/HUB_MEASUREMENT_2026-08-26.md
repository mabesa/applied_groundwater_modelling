# Hub measurement — 2026-08-26 (first Hub data recorded in this project)

**Platform:** `Linux-6.8.0-136-generic-x86_64`, glibc 2.39, Python 3.12.9.
**Compared against:** macOS-arm64, same script, same workload, 2026-08-26.

---

## Result 1 — 🔴 `H ≈ 2.9–3.0`, and the fine run projects **ABOVE the ceiling**

The qualification stage did not run (§4), so this comes from the **fingerprint stage as a proxy**: the same
workload, the same script, both platforms, five fresh processes each.

| | macOS-arm64 | Linux Hub |
|---|---:|---:|
| per run | 6.2 s ×5 | 20.4 · 18.1 · 17.9 · 18.6 · 17.7 s |
| mean | **6.20 s** | **18.54 s** |

**`H = 2.99`** on all runs, **`2.92`** excluding the first (warm-up) run.

⚠️ **That is almost exactly the `H = 3` that `T0_0…` §6 used as its illustration of the failure case.**

| | |
|---|---:|
| fine run, fast Mac | 316 s |
| projected on Hub (`H = 2.92 … 2.99`) | **921 – 945 s** |
| `HUB_FINE_TARGET_S` | 600 s |
| `HUB_FINE_CEILING_S` | **900 s** |

> 🔴 **The projection lands ABOVE the ceiling.** On these numbers T2's mandatory fine run **fails** and
> takes its pre-declared failure edge — back to **T1** for a cheaper `GridSpec`, or to **T0** for a revised
> threshold. It may **not** pass by reclassifying the fine run as optional.

⚠️ **And 316 s is likely an UNDER-estimate**: that run sat on `nstp_cap = 2000`, so `cr_target = 0.9` may
never have been reached.

⚠️ **Proxy caveat, stated plainly.** PRT particle tracking is not a GWT transport solve and need not scale
identically. This is a strong signal, **not** the measurement `T0_0…` §6 asks for — that still needs the
qualification stage (§4).

---

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

## 3. Result 3 — the Hub-side gate qualification did NOT run

Blocked by §4. **`T0_0…` §5.1's "a Hub-side T1 gate would need its own qualification" remains open.**

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
uv run python _SUPPORT/src/scripts/hub_measurement.py --workdir ~/hub_meas --skip-fingerprint
```

`--skip-fingerprint` because result 2 is already settled — this second run only needs questions 1 and 2,
and will take ~15 min rather than ~25.

**The script now preflights this** (added the same day), so a missing `config.py` or flopy bin directory
fails in one second with the fix printed, instead of minutes in.
