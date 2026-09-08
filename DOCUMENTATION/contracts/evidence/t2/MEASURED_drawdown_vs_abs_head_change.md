# Measured: drawdown area vs |head change| area, all 13 groups

**Date:** 2026-09-08 · **Platform:** macOS-arm64 · **States:** the committed
`_baseline_ref` and `_state_group<N>_wells_only` workspaces for every group.

## Why this exists

`case_study_flow_group_0.ipynb` §8 and the scratch **Card A** both tell students
that the flow master's `abs()`-based area and Card A's drawdown area answer
different questions and can diverge. Those are **empirical claims put in front of
students**, so the numbers behind them are recorded here rather than asserted.

An earlier draft of that prose claimed the two "differ by roughly 2x". That was
reasoned from the geometry of a balanced doublet and **never measured**. The
measurement below shows it is true for **2 of 13 groups**, so the wording was
corrected before it shipped.

## The two quantities

Let `Δh = h_wells − h_baseline`, over FREE (active, non-CHD) cells with finite
head in both states.

| Metric | Definition | Where |
|---|---|---|
| Card A area | area where `h_base − h_wells > 0.5 m` (drawdown only) | `scratch_io.compute_drawdown` + `affected_area` |
| Master area | area where `\|Δh\| > 0.5 m` (drawdown **and** injection mound) | `casestudy_flow_viz.recipe_area_abs_head_change_gt_0p5m_m2` |

So `A_master = A_drawdown + A_mound`. Equal `+Q` / `−Q` guarantees zero net
imposed flux — it does **not** imply the cone and mound clear 0.5 m over
comparable areas.

## Result

| Group | Card A area (m²) | Master area (m²) | Ratio |
|---:|---:|---:|---|
| 0 | 0 | 5 681 | **undefined** (drawdown area is zero) |
| 1 | 3 464 | 3 613 | 1.04 |
| 2 | 37 755 | 44 323 | 1.17 |
| 3 | 118 | 777 | **6.59** |
| 4 | 99 | 240 | 2.44 |
| 5 | 0 | 0 | both zero |
| 6 | 0 | 0 | both zero |
| 7 | 0 | 0 | both zero |
| 8 | 0 | 0 | both zero |
| 9 | 934 | 2 008 | 2.15 |
| 10 | 0 | 0 | both zero |
| 11 | 5 778 | 5 878 | 1.02 |
| 12 | 0 | 0 | both zero |

## What the numbers support

- **6 of 13 groups have no discrepancy at all** — neither area is non-zero,
  because the doublet never moves the head by 0.5 m anywhere. Prose implying a
  contrast would be meaningless for them.
- **Group 0** has zero drawdown area against 5 681 m² of `abs()` area: the
  injection mound clears 0.5 m where the extraction cone never does. The ratio is
  undefined, not "about 2".
- **The six finite ratios span 1.02 to 6.59** — from "indistinguishable" to
  "sixfold". No single multiplier describes the roster.

The shipped wording therefore states the *mechanism* (`abs()` adds the mound),
names the real spread, tells students an area of 0 m² is a finding about their
scenario rather than a failure, and instructs them to **compute both and look**
rather than expect a ratio.

## Reproducing

Load each group's `_baseline_ref` and `_state_group<N>_wells_only` with FloPy,
mask `|head| > 1e29` to NaN, weight by `modelgrid.get_cell_vertices` polygon
areas, and sum where `h_base − h_wells > 0.5` and where `|h_wells − h_base| > 0.5`
respectively. Values above are from the committed pinned meshes and will move if
the meshes are re-frozen.
