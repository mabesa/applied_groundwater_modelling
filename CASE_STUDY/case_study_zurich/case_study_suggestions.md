## New municipal well (drawdown & capture)

Problem: Assess the impact of a new municipal well on the surrounding groundwater system.

Change: Add 1 well at (x₁,y₁) with rate Q.

Outputs: drawdown map, heads at 3 obs points, % of inflow from each boundary.

Check: Thiem (confined) or Dupuit (unconfined) radial drawdown at an observation radius.

## Well interference (simple wellfield)

Problem: Assess the impact of two nearby wells on each other's performance.

Change: Two wells at (x₁,y₁) and (x₂,y₂), split total Q.

Outputs: superposition of drawdowns, max drawdown constraint at a “sensitive” point.

Check: Sum of two Thiem solutions vs model.

## Stream depletion at equilibrium (RIV)

Problem: Assess the impact of a new pumping well on river flow.

Change: Add a pumping well near river.

Outputs: Δ in “RIVER LEAKAGE” (CBC) vs baseline; fraction of Q coming from river.

Check: Compare fraction with expectation from distance/leakance; discuss sensitivity to conductance.

## Boundary condition uncertainty (RIV vs GHB)

Problem: TODO

Change: Replace river reach (or a segment) with GHB calibrated to same stage.

Outputs: head and budget differences; which BC better conserves mass locally?

Check: Head along river line vs prescribed stage.

## Managed Aquifer Recharge (MAR) patch

Change: Increase RCH over a polygonal area (basin) by ΔR.

Outputs: mound height at centerline, % MAR captured by the new/nearby well.

Check: Order-of-magnitude with Dupuit mound scaling (broad area recharge).

## Low-K lens or barrier (HFB or zoned LPF)

Change: Insert a low-K strip between river and well (or use HFB).

Outputs: heads upstream/downstream of barrier, river capture fraction vs case 3.

Check: Image-well/barrier intuition (qualitative), compare budgets.

## Quarry/Construction dewatering

Change: Strong pumping from shallow layer near a DRN (wetland/drain).

Outputs: extent of dewatered area (cells near top), drain outflow change.

Check: Drawdown footprint vs simple Thiem; discuss sensitivity to K and drain conductance.

## Protection of a spring/CHD boundary

Change: Add a well; impose max allowed drawdown at a spring (CHD line).

Task: Find maximum Q that keeps Δh at spring ≤ d_max (trial runs or simple search).

Outputs: feasible Q, head map, budgets.

Check: Distance-drawdown estimate for feasibility.

## Anisotropy & well performance

Change: Vary horizontal anisotropy (Kx/Ky) or vertical anisotropy (Kh/Kv).

Outputs: head contours elongation, drawdown at fixed radii.

Check: Compare with elliptical flow expectation; note effect on capture toward river.

## Plume capture (with MODPATH on steady heads)

Change: Add a hypothetical source cell (no mass transport—just particles).

Task: Size and place a pumping well to fully capture the source.

Outputs: pathlines, 50%/100% capture zones, pumping rate needed.

Check: Compare capture width with simple uniform-flow analytic (Reilly capture rule-of-thumb).