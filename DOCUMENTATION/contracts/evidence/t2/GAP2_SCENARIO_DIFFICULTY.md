# Making the case studies non-trivial — scenario changes, 2026-09-02

**Instruction (lecturer):** six groups had verdicts that were settled before any modelling —
four exceeded their limit by 24–138x, two were under by 10–100x. Move spill locations and/or
masses so the student has to do the work. All 13 geometries were re-verified afterwards.

## 1. What could be fixed with a number, and what could not

| g | contaminant | was | lever | why |
|---|---|---|---|---|
| 0 | Trichloroethylene | 138.5x | 100 → 5 mg/L | concentration; peak is exactly linear in it |
| 2 | Benzene | 23.7x | 10 → 1.5 mg/L | same |
| 5 | PFOA | 49.8x | 1 → 0.28 mg/L | same |
| 6 | Perchloroethylene | 38.2x | 50 → 2.9 mg/L | same |
| 8 | Atrazine | 0.096x | 1 → 90 d pulse **and** 5 → 15 mg/L | 🔴 concentration alone is IMPOSSIBLE — it would need 104 mg/L against a **35 mg/L solubility** |
| 1 | Nitrate | 0.009x | spill MOVED, 50 → 700 mg/L | 🔴 pure bypass; no concentration fixes a plume that misses |

## 2. Group 8 — duration, measured

Pulse length buys roughly 1.6x per doubling, so it is **not** a substitute for concentration:

| pulse | 1 d | 15 d | 45 d | 90 d | 180 d | 365 d continuous |
|---|---|---|---|---|---|---|
| peak/limit | 0.096 | 0.218 | 0.430 | 0.690 | 1.039 | 1.252 |

⚠️ 180 d and 365 d land at 1.04 and 1.25 — **inside the danger band**, where mesh noise decides
compliance. Neither is usable. The shipped combination is **90 d at 15 mg/L → 2.070 measured**
(predicted 2.070 from linearity), safely clear and still under solubility.

## 3. Group 1 — the capture zone is not where the doublet axis points

The first attempt moved the spill along the doublet axis toward the injection well, copying what
worked for group 11. **It made things 20x worse** (0.009 → 0.0004): the injection well pushes clean
water outward and sweeps the plume away from the extraction well.

A sweep of eight bearings at 120 m found the capture zone lies **north-east**:

| bearing | 0° | 45° | 90° | 135° | 180° | 315° |
|---|---|---|---|---|---|---|
| peak/limit | 0.019 | **0.080** | 0.002 | 0.001 | ~0 | 0.014 |

(225° and 270° were rejected — they put the spill within 80 m of the model boundary.) Closing in
along that bearing cuts dilution further: 120 m → 0.080, 90 m → 0.107, **60 m → 0.131**.

**The story already justified the concentration.** The scenario reads *"the tank holding the nitrate
fertilizer … has leaked"* — a bulk tank of liquid fertilizer, which is ~30 % N by weight. The
shipped 50 mg/L was field-leachate strength and inconsistent with its own narrative. At 60 m / 45°
with 700 mg/L the case lands at **1.832x measured**.

⚠️ Nitrate could never have been made to exceed at 50 mg/L: the limit is 25 mg/L, so even an
undiluted arrival caps at 2.0x, and real dilution is ~8x at the best position.

## 4. A standing chemistry flag, resolved

`casestudy_canonical_mapping.REFERENCE_BOUNDS` carried nitrate as `drinking_water_as_N` with band
[1.0, 11.3], and its own comment said *"confirm the as-N vs NO3- basis."* Our threshold of 25 mg/L
therefore failed the sanity check as out-of-band. **25 mg/L is correct** — it is the Swiss GSchV
Anhang 2 groundwater requirement, expressed **as NO3-**. 25 mg/L *as N* would be 110 mg/L as NO3-,
which is not a standard anywhere. Basis relabelled `drinking_water_as_NO3`, band [10, 50] (Swiss
requirement to the EU/WHO drinking-water value).

## 5. The roster after the changes — all 13 re-verified

| g | contaminant | radius | min cell | peak/limit | verdict | hub s |
|---|---|---|---|---|---|---|
| 0 | Trichloroethylene | 90 | 5.32 m | 6.923 | EXCEEDS | 33 |
| 1 | Nitrate | 50 | 3.27 m | 1.832 | EXCEEDS | 54 |
| 2 | Benzene | 62 | 4.51 m | 3.547 | EXCEEDS | 88 |
| 3 | Chloride | 90 | 4.39 m | 0.522 | COMPLIANT | 553 |
| 4 | Chromium | 90 | 4.06 m | 0.656 | COMPLIANT | 337 |
| 5 | PFOA | 70 | 2.54 m | 13.93 | EXCEEDS | 18 |
| 6 | Perchloroethylene | 44 | 2.03 m | 2.217 | EXCEEDS | 329 |
| 7 | Ammonium | 84 | 4.56 m | 6.578 | EXCEEDS | 216 |
| 8 | Atrazine | 44 | 1.67 m | 2.070 | EXCEEDS | 88 |
| 9 | MTBE | 56 | 1.92 m | 1.930 | EXCEEDS | 254 |
| 10 | Carbamazepine | 74 | 1.58 m | 1.506 | EXCEEDS | 81 |
| 11 | Boron | 84 | 5.09 m | 0.619 | COMPLIANT | 276 |
| 12 | Nickel | 48 | 1.19 m | 0.568 | COMPLIANT | 350 |

Every group: builds, no sub-metre cells, bounded by its own source, no Courant cap, verdict robust
(<0.8 or >1.333), inside the 15-minute budget. Slowest 553 s; roster total 2677 s.

⚠️ **The balance moved from 7 exceeds / 6 complies to 9 / 4** — groups 1 and 8 were both compliant
and both flipped. Magnitudes are well spread (five groups in the demanding 1.5–2.2x band, three at
3.5–7x, one at 14x, four under at 0.52–0.66), but the roster now leans toward exceedance. If
balance is wanted back, group 8 at a 45 d pulse and the original 5 mg/L gives 0.43x.

**Not yet done:** the meshes have NOT been re-frozen against these scenarios. Group 1's move changes
its corridor, so its geometry must be re-frozen with the rest.
