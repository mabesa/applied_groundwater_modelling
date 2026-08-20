# T0.1 input — pinned surfaces (result-derived literals in code and tests)

**Generated**, do not hand-edit. Regenerate with the command in §3.
**Status:** an INPUT to T0.1 (C1 v2), specifically to its *enumerated surfaces* and its *approved numeric
rebaseline* parts. It is **not** a claim inventory.

## 1. Why this file exists

Two independent codex raters split almost perfectly on the 34 code/test candidates: rater C read each test
assertion as the claim it encodes, rater D read it as test machinery. **Both are right about different
things**, and the resolution recorded on 2026-08-20 is:

> A test assertion, its message, and an implementation comment are **not claims the course makes to
> students** — so they are `not_a_claim` in the T0.2a taxonomy. But they **are pinned surfaces**: every one
> of them holds a result-derived number that must move, with an approved old→new entry, when the JAG
> rebaselines. Classifying them as `not_a_claim` must therefore never mean *forgetting* them.

This file is the mechanism that stops that. Losing these would mean a JAG rebaseline that silently leaves
stale pins behind — which is the exact failure this repo has shipped before.

⚠️ **These pins are far looser than T0.2b's support tolerances** (`TOL_CONC_REL` 2%, `TOL_TIME_REL` 2%).
They are **regression guards, not support tolerances**, and a JAG rebaseline could pass while a number moved
materially. T0.1 must record the *values*, not rely on the assertions passing.

## 2. The pinned surfaces

| file | id | pinned assertion |
|---|---|---|
| `test_transport_prt_capture.py` | `14d09b80aaed` | `assert base["regional_qb_m2d"] == pytest.approx(9.56, rel=0.10) # Phase-4: 2,160 m³/d (was 6.3 at 1,080)` |
| `test_transport_prt_capture.py` | `3e98d97bc922` | `assert 0.0 < wider.max_captured_offset_m <= wider.asymptotic_halfwidth_m * 1.5` |
| `test_transport_prt_capture.py` | `73806ad825cc` | `assert 0.0 < capture.meta["halfwidth_minus_m"] < capture.asymptotic_halfwidth_m` |
| `test_transport_prt_capture.py` | `765282001389` | `assert capture.meta["halfwidth_s_m"] == 0.0 # AT the spill transect` |
| `test_transport_prt_capture.py` | `76c3816fe0c6` | `assert far["halfwidth_m"] > base["halfwidth_m"] + 10.0, (` |
| `test_transport_prt_capture.py` | `7d8f6f31616c` | `assert alt["halfwidth_m"] == pytest.approx(base["halfwidth_m"], abs=1.0), (` |
| `test_transport_prt_capture.py` | `80d330b200b0` | `assert 0.0 < wide.max_captured_offset_m <= wide.asymptotic_halfwidth_m * 1.1` |
| `test_transport_prt_capture.py` | `93099eb1cdb5` | `assert np.all(tt > 0.0), "a travel time of 0 d means a particle was released " \` |
| `test_transport_prt_capture.py` | `97a32a00cd02` | `assert base["asymptotic_halfwidth_m"] == pytest.approx(71.6, rel=0.10)` |
| `test_transport_prt_capture.py` | `9d1a1be3a4e6` | `assert far["halfwidth_m"] == pytest.approx(base["asymptotic_halfwidth_m"], rel=0.15)` |
| `test_transport_prt_capture.py` | `bc067bb50905` | `assert 0.0 < capture.meta["halfwidth_plus_m"] < capture.asymptotic_halfwidth_m` |
| `test_transport_prt_capture.py` | `d4b6a6ae3cfd` | `assert far["halfwidth_m"] == pytest.approx(67.5, rel=0.10) # Phase-4 (was 112 at 1,080)` |
| `test_transport_prt_capture.py` | `d927be6a82d1` | `assert 0.0 < capture.halfwidth_at_spill_m < capture.asymptotic_halfwidth_m` |
| `test_transport_prt_capture.py` | `eb895cb45a73` | `assert base["halfwidth_m"] == pytest.approx(53.1, rel=0.05) # Phase-4: 2,160 m³/d (was 78.9 at 1,080)` |
| `test_transport_srcpulse_demo.py` | `0568dd562a16` | `assert reactive_demo.peak_mgL == pytest.approx(3.39, rel=0.08)` |
| `test_transport_srcpulse_demo.py` | `0fcb94e2d22e` | `assert demo.arrival_day == pytest.approx(38.8, abs=5.0)` |
| `test_transport_srcpulse_demo.py` | `2e15bbd86c1b` | `assert decay_demo.arrival_day == pytest.approx(36.85, abs=5.0)` |
| `test_transport_srcpulse_demo.py` | `3e9d506fa083` | `assert 0.0 < reactive_demo.arrival_day <= reactive_demo.total_days` |
| `test_transport_srcpulse_demo.py` | `42a942837b0f` | `assert peak == 0.0` |
| `test_transport_srcpulse_demo.py` | `51e7332a5eda` | `assert hit.peak_mgL == pytest.approx(1.0)` |
| `test_transport_srcpulse_demo.py` | `7054b9c51ef4` | `assert reactive_demo.peak_mgL > 0.0` |
| `test_transport_srcpulse_demo.py` | `841f354b1d60` | `assert reactive_demo.arrival_day == pytest.approx(54.5, abs=5.0)` |
| `test_transport_srcpulse_demo.py` | `ac52663cce6a` | `assert demo.peak_mgL == pytest.approx(5.28, rel=0.08)` |
| `test_transport_srcpulse_demo.py` | `c4dcc829a28b` | `assert 0.0 < demo.arrival_day <= demo.total_days` |
| `test_transport_srcpulse_demo.py` | `c59af8b434e4` | `assert demo.peak_mgL > 0.0` |
| `test_transport_srcpulse_demo.py` | `ea17cc64ea64` | `assert decay_demo.peak_mgL == pytest.approx(3.20, rel=0.08)` |
| `test_transport_verify_2d.py` | `0d52985c12c2` | `assert cse.Pe_T >= 5.0 and fine.Pe_T <= 2.0 # sanity on the two grids` |
| `test_transport_verify_2d.py` | `1df5e7fac155` | `assert r.peak_conc_err < 0.10` |
| `test_transport_verify_2d.py` | `2802c929c949` | `assert r.Pe_L <= 2.0 and r.Pe_T <= 2.0 # grid Peclet OK for advection` |
| `test_transport_verify_2d.py` | `391eca719b5d` | `assert r.peak_conc_err < 0.10 # peak concentration < 10%` |
| `test_transport_verify_2d.py` | `5deb03c42e94` | `assert r.peak_pos_err < 0.05` |
| `test_transport_verify_2d.py` | `83999ab705ac` | `assert r.peak_pos_err < 0.05 # peak position < 5%` |

**32 pinned assertions.**

### Also in scope, not matched by the pattern above

- `transport_prt_capture.py` `if __name__ == "__main__":` block — prints **"the ADE's day-39 CONCENTRATION
  peak"** as a prose literal. Developer-facing (the notebooks import only `build_prt_capture`), so it is
  not a student claim — but it is a **result-derived literal in a module** and rots exactly like the ones
  the 2026-08-18 sweep fixed.
- `test_transport_srcpulse_demo.py` `REACTIVE_TOTAL_DAYS = 220.0` — a horizon chosen *because* of a
  result (`conservative arrival ~38.8 d; R=2 pushes arrival to ...`). If the arrival moves, the horizon
  may need to move with it or the run becomes horizon-censored.

## 3. Regenerate

```
python3 - <<'EOF' > DOCUMENTATION/contracts/T0_1_pinned_surfaces.md
# (this file's own generator; see git history)
EOF
```

The authoritative inputs are `DOCUMENTATION/contracts/T0_2a_claim_inventory.json` and
`_SUPPORT/src/scripts/transport_claim_classifications.yaml`. Re-run after any inventory change.
