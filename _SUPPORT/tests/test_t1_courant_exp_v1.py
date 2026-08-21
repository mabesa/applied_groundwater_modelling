"""T1 S8 -- the corrected `courant_nstp` policy, profile `exp_v1`
(`DESIGN_DOCS/T1_S8_brief.md` v2, `_SUPPORT/src/transport_srcpulse_demo.py`).

S4 canonicalised the two pre-S4 duplicate `courant_nstp` bodies into one
calculator, `_courant_nstp_canonical`, behind explicit `legacy_base` /
`legacy_srcpulse` profiles -- deliberately taking the UNMASKED corridor mask
plus explicit `exclusions` so a THIRD profile could stop excluding. S8 adds
that profile, `exp_v1`, correcting four things over both legacy profiles:

  1. the sliver floor is keyed off the finest INTENDED cell size
     (`min(level.cell_size for level in mesh_spec.levels)`), not a single
     achieved `refined_cell_size`;
  2. `exclusions` is accepted but IGNORED -- source and well cells are
     included in the selection that sizes `nstp`;
  3. the reported Cr is the MEASURED MAXIMUM over the entire original
     (unmasked) corridor mask -- including cells the sliver floor drops from
     selection -- not just the surviving selection;
  4. `nstp_cap` RAISES (naming the cap and the `nstp` that would have been
     needed) instead of silently truncating.

The T0 gate is BLIND to this step: the sliver floor is numerically inert at
the shipped default (`courant_floor=4.0` vs `ds_true_min=5.478`), so
`compare` passes under either policy. Per brief Section 2.2, no test here
asserts that `exp_v1` and a legacy profile produce DIFFERENT NUMBERS at any
shared input -- only WHICH policy ID was selected, and the corrected
behaviour on synthetic fields constructed so it demonstrably bites.

Most tests below are calculator-level (fast, synthetic, no MF6 solve),
mirroring `test_t1_courant_profiles.py`'s own style. Three tests must
observe the REAL on-disk cache mechanism (courant_profile is part of the
cache identity, brief Section 2.3) and share ONE module-scoped fixture that
pays for two real, cold builds -- mirroring `test_t1_source_footprint.py`'s
`cache_identity_case` fixture for `footprint_radius_m`.

Run with:  uv run pytest _SUPPORT/tests/test_t1_courant_exp_v1.py -v
Use `-m "not slow"` to skip the three real-build cache-identity tests.
"""
from __future__ import annotations

import inspect
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_base_model as tbm  # noqa: E402
import transport_srcpulse_demo as tsd  # noqa: E402

MeshSpec = tsd.MeshSpec
MeshLevel = tsd.MeshLevel

REFINED_CELL_SIZE = 10.0   # both modules' LOCKED_PARAMS["refined_cell_size"]
SLIVER_FLOOR_FRAC = 0.4
FLOOR = SLIVER_FLOOR_FRAC * REFINED_CELL_SIZE


def _fields(n: int = 6):
    """`n` corridor cells, all size == REFINED_CELL_SIZE (well above the 4.0
    floor) and all velocity 1.0 -- override per-cell to probe behaviour."""
    v = np.full(n, 1.0)
    size = np.full(n, REFINED_CELL_SIZE)
    mask = np.ones(n, dtype=bool)
    return v, size, mask


# ---------------------------------------------------------------------------
# 1. exit criterion 1: legacy profiles are unchanged by S8
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("wrapper,default_cap", [
    (tbm.courant_nstp, 1000),
    (tsd._courant_nstp, 2000),
])
def test_legacy_profiles_unchanged_against_the_pinned_cases(wrapper, default_cap):
    """Independent, hand-computed expectation (not derived from the
    production formula) for a representative input -- the numbers each
    legacy wrapper returns must be untouched by S8."""
    v = np.array([1.0, 2.0, 3.0, 0.5, 4.0, 1.5])
    size = np.full(6, 10.0)
    mask = np.ones(6, dtype=bool)
    total_time = 200.0

    floor = 0.4 * 10.0
    sel = mask.copy() & (size >= floor)
    ratio = v[sel] / size[sel]
    critical = float(ratio.max())
    dt_need = 0.9 / critical
    expected_nstp = min(int(np.ceil(total_time / dt_need)), default_cap)
    expected_dt = total_time / expected_nstp
    expected_cr = critical * expected_dt

    nstp, dt, cr, diag = wrapper(v, size, mask.copy(), total_time)
    assert nstp == expected_nstp
    assert dt == pytest.approx(expected_dt)
    assert cr == pytest.approx(expected_cr)
    assert diag["floor"] == floor


# ---------------------------------------------------------------------------
# 2. correction 1: floor keyed off the finest INTENDED cell size
# ---------------------------------------------------------------------------
def test_exp_v1_floor_uses_the_finest_intended_cell_size():
    """A graded MeshSpec (outer level 10 m, inner level 2 m) must floor at
    0.4*2=0.8, not 0.4*10=4.0 -- the finest level, via `min()`, wins."""
    v = np.full(4, 1.0)
    size = np.full(4, 1.0)   # below 0.4*10=4.0, above 0.4*2=0.8
    mask = np.ones(4, dtype=bool)
    coarse_only = MeshSpec(levels=(MeshLevel(cell_size=10.0),))
    graded = MeshSpec(levels=(MeshLevel(cell_size=10.0), MeshLevel(cell_size=2.0, radius_m=20.0)))

    with pytest.raises(ValueError, match="floor-filtered selection is empty"):
        tsd._courant_nstp_canonical(v, size, mask.copy(), 100.0, nstp_cap=2000,
                                    refined_cell_size=REFINED_CELL_SIZE,
                                    mesh_spec=coarse_only, profile="exp_v1")

    nstp, dt, cr, diag = tsd._courant_nstp_canonical(
        v, size, mask.copy(), 100.0, nstp_cap=2000, refined_cell_size=REFINED_CELL_SIZE,
        mesh_spec=graded, profile="exp_v1")
    assert diag["floor"] == pytest.approx(0.4 * 2.0)


# ---------------------------------------------------------------------------
# 3. exit criterion 3: the floor bites on a synthetic graded field
# ---------------------------------------------------------------------------
def test_sub_floor_cells_included_under_exp_v1_excluded_under_legacy():
    v = np.full(6, 1.0)
    size = np.full(6, 10.0)
    size[2] = 3.0     # below the legacy floor (0.4*10=4.0), above the graded exp_v1 floor (0.4*2=0.8)
    v[2] = 5.0         # would dominate the ratio if included
    mask = np.ones(6, dtype=bool)
    graded = MeshSpec(levels=(MeshLevel(cell_size=10.0), MeshLevel(cell_size=2.0, radius_m=20.0)))

    _, _, _, diag_legacy = tsd._courant_nstp_canonical(
        v, size, mask.copy(), 100.0, nstp_cap=2000, refined_cell_size=REFINED_CELL_SIZE,
        profile="legacy_srcpulse")
    assert diag_legacy["v_bind"] != 5.0    # excluded by the legacy floor

    _, _, _, diag_exp = tsd._courant_nstp_canonical(
        v, size, mask.copy(), 100.0, nstp_cap=2000, refined_cell_size=REFINED_CELL_SIZE,
        mesh_spec=graded, profile="exp_v1")
    assert diag_exp["v_bind"] == 5.0       # included by the graded exp_v1 floor


# ---------------------------------------------------------------------------
# 4. correction 2: source and well cells INCLUDED under exp_v1
# ---------------------------------------------------------------------------
def test_source_and_well_cells_included_under_exp_v1():
    v, size, mask = _fields(6)
    v[4] = 50.0   # a "well" cell -- would dominate the ratio if included
    spec = MeshSpec()

    _, _, _, diag_legacy = tsd._courant_nstp_canonical(
        v, size, mask.copy(), 100.0, exclusions=[4], nstp_cap=2000,
        refined_cell_size=REFINED_CELL_SIZE, profile="legacy_srcpulse")
    assert diag_legacy["v_bind"] != 50.0

    # exp_v1: exclusions is PASSED (not an error) but IGNORED
    _, _, _, diag_exp = tsd._courant_nstp_canonical(
        v, size, mask.copy(), 100.0, exclusions=[4], nstp_cap=2000,
        refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec, profile="exp_v1")
    assert diag_exp["v_bind"] == 50.0


# ---------------------------------------------------------------------------
# 5. correction 3: reported Cr is the global max, not the post-exclusion max
# ---------------------------------------------------------------------------
def test_reported_cr_is_the_global_max_not_post_exclusion():
    """exp_v1 ignores `exclusions`: the reported Cr equals the measured
    maximum over the WHOLE corridor mask -- verified against an independent
    formula-based recomputation, and shown to differ from what the
    post-exclusion (legacy-style) domain alone would report."""
    v = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 8.0])
    size = np.full(6, 10.0)
    mask = np.ones(6, dtype=bool)
    spec = MeshSpec()
    total_time = 50.0

    nstp, dt, cr, diag = tsd._courant_nstp_canonical(
        v, size, mask.copy(), total_time, exclusions=[5], nstp_cap=5000,
        refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec, profile="exp_v1")

    independent_cr = float((v * dt / size).max())          # over the WHOLE mask
    assert cr == pytest.approx(independent_cr)
    assert diag["v_bind"] == 8.0                            # the nominally "excluded" cell binds

    post_exclusion_domain = np.ones(6, dtype=bool)
    post_exclusion_domain[5] = False
    post_exclusion_cr = float((v[post_exclusion_domain] * dt / size[post_exclusion_domain]).max())
    assert cr != pytest.approx(post_exclusion_cr)


# ---------------------------------------------------------------------------
# 6. correction 4: nstp_cap RAISES under exp_v1 only
# ---------------------------------------------------------------------------
def test_nstp_cap_raises_under_exp_v1_only():
    v = np.full(6, 1000.0)   # huge velocity -> would need nstp >> any small cap
    size = np.full(6, 10.0)
    mask = np.ones(6, dtype=bool)
    spec = MeshSpec()
    total_time = 365.0
    cap = 5

    for profile in ("legacy_base", "legacy_srcpulse"):
        nstp, dt, cr, diag = tsd._courant_nstp_canonical(
            v, size, mask.copy(), total_time, nstp_cap=cap,
            refined_cell_size=REFINED_CELL_SIZE, profile=profile)
        assert nstp == cap    # saturates, no raise

    with pytest.raises(ValueError, match="nstp_cap"):
        tsd._courant_nstp_canonical(
            v, size, mask.copy(), total_time, nstp_cap=cap,
            refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec, profile="exp_v1")


# ---------------------------------------------------------------------------
# 7. exit criterion 2: each real caller's cap metadata is UNCHANGED by S8
# ---------------------------------------------------------------------------
def test_each_caller_cap_metadata_is_unchanged():
    """Structural check against the frozen line-level facts in
    DESIGN_DOCS/T1_S8_brief.md Section 2.1: `build_doublet_base` sets no cap
    flag at all; `build_spill_scenario` keys off `Cr > 1.001` and does not
    warn; `build_srcpulse_demo` sets `cr_capped = nstp >= nstp_cap` and DOES
    warn. None of the three call sites may change in any respect."""
    demo_src = inspect.getsource(tsd.build_srcpulse_demo)
    assert "cr_capped = bool(nstp >= nstp_cap)" in demo_src
    assert "warnings.warn(" in demo_src

    base_src = inspect.getsource(tbm.build_doublet_base)
    assert "cr_capped" not in base_src

    spill_src = inspect.getsource(tbm.build_spill_scenario)
    assert "cr_capped=bool(cr_act > 1.001)" in spill_src
    assert "warnings.warn(" not in spill_src


# ---------------------------------------------------------------------------
# 8-9, 18. the REAL cache mechanism: profile is part of the identity, and a
# warm cache never serves a different profile, in EITHER direction. ONE
# shared, module-scoped, cold real build (mirrors
# test_t1_source_footprint.py::cache_identity_case for footprint_radius_m).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def courant_cache_identity_case(tmp_path_factory):
    ws = tmp_path_factory.mktemp("t1_s8_cache_identity_ws")
    kwargs = dict(mass_g=1.0e4, pulse_days=5.0, total_days=15.0,
                  solubility_mgL=1000.0, case_ws=ws, force=False)
    r_legacy = tsd.build_srcpulse_demo(courant_profile="legacy_srcpulse", **kwargs)
    r_exp = tsd.build_srcpulse_demo(courant_profile="exp_v1", **kwargs)
    return ws, kwargs, r_legacy, r_exp


@pytest.mark.slow
def test_profile_changes_the_cache_identity(courant_cache_identity_case):
    """Brief Section 2.3 / exit criterion 7: the selected `courant_profile`
    must be part of the `params` dict that keys the cache filename -- two
    runs differing ONLY in profile must produce two DISTINCT cache files."""
    ws, _kwargs, _r_legacy, _r_exp = courant_cache_identity_case
    caches = sorted(p.name for p in ws.glob("srcpulse_cache_*.npz"))
    assert len(caches) == 2


@pytest.mark.slow
def test_legacy_warm_cache_is_not_served_to_an_exp_v1_run(courant_cache_identity_case):
    """With both caches warm on disk, a fresh exp_v1 request must return the
    exp_v1 run's own result, and must not create a THIRD cache file."""
    ws, kwargs, _r_legacy, r_exp = courant_cache_identity_case
    exp_again = tsd.build_srcpulse_demo(courant_profile="exp_v1", **kwargs)
    assert exp_again.meta["nstp"] == r_exp.meta["nstp"]
    assert exp_again.peak_mgL == pytest.approx(r_exp.peak_mgL)
    caches_after = sorted(p.name for p in ws.glob("srcpulse_cache_*.npz"))
    assert len(caches_after) == 2   # cache HIT -- no new file


@pytest.mark.slow
def test_warm_exp_v1_cache_is_not_served_to_a_legacy_run(courant_cache_identity_case):
    """The reverse direction: with both caches warm, a fresh legacy_srcpulse
    request must return the legacy run's own result, unaffected by the warm
    exp_v1 cache sitting alongside it."""
    ws, kwargs, r_legacy, _r_exp = courant_cache_identity_case
    legacy_again = tsd.build_srcpulse_demo(courant_profile="legacy_srcpulse", **kwargs)
    assert legacy_again.meta["nstp"] == r_legacy.meta["nstp"]
    assert legacy_again.peak_mgL == pytest.approx(r_legacy.peak_mgL)
    caches_after = sorted(p.name for p in ws.glob("srcpulse_cache_*.npz"))
    assert len(caches_after) == 2   # cache HIT -- no new file


# ---------------------------------------------------------------------------
# 10. no LOCKED_PARAMS read anywhere in the calculator (brief Section 2.4)
# ---------------------------------------------------------------------------
def test_calculator_reads_no_locked_params():
    assert "LOCKED_PARAMS" not in tsd._courant_nstp_canonical.__code__.co_names
    assert "LOCKED_PARAMS" not in tsd._courant_nstp_corrected.__code__.co_names


# ---------------------------------------------------------------------------
# 11. exp_v1 inherits NEITHER legacy profile's degenerate-input fallback
# ---------------------------------------------------------------------------
def test_exp_v1_degenerate_cases_follow_srcpulse_not_base():
    """exp_v1 raises on both degenerate conditions where `legacy_srcpulse`
    falls back -- but with its OWN typed errors naming the condition, not
    `legacy_base`'s incidental ones (`ratio.max()` on an empty array /
    a raw ZeroDivisionError)."""
    spec = MeshSpec()
    mask = np.ones(5, dtype=bool)
    total_time = 100.0

    # (a) every corridor cell below the floor: legacy_srcpulse rescues via the
    # whole-mask fallback; exp_v1 must not.
    size = np.full(5, 0.1)
    v = np.full(5, 1.0)
    result = tsd._courant_nstp_canonical(
        v, size, mask.copy(), total_time, nstp_cap=2000,
        refined_cell_size=REFINED_CELL_SIZE, profile="legacy_srcpulse")
    assert result is not None
    with pytest.raises(ValueError, match="floor-filtered selection is empty"):
        tsd._courant_nstp_canonical(
            v, size, mask.copy(), total_time, nstp_cap=2000,
            refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec, profile="exp_v1")

    # (b) zero velocity: legacy_srcpulse returns the cap with Cr=0; exp_v1 raises.
    size2 = np.full(5, 10.0)
    v2 = np.zeros(5)
    nstp_s, dt_s, cr_s, _ = tsd._courant_nstp_canonical(
        v2, size2, mask.copy(), total_time, nstp_cap=2000,
        refined_cell_size=REFINED_CELL_SIZE, profile="legacy_srcpulse")
    assert nstp_s == 2000 and cr_s == 0.0
    with pytest.raises(ValueError, match="nonpositive or non-finite"):
        tsd._courant_nstp_canonical(
            v2, size2, mask.copy(), total_time, nstp_cap=2000,
            refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec, profile="exp_v1")


# ---------------------------------------------------------------------------
# 12. brief Section 2.2: assert WHICH policy id was selected, never that the
# numbers differ from a legacy profile at a shared input
# ---------------------------------------------------------------------------
def test_selected_policy_id_is_recorded(monkeypatch):
    calls = []
    real_corrected = tsd._courant_nstp_corrected

    def _spy(*args, **kwargs):
        calls.append("exp_v1")
        return real_corrected(*args, **kwargs)

    monkeypatch.setattr(tsd, "_courant_nstp_corrected", _spy)
    v, size, mask = _fields(4)
    spec = MeshSpec()

    tsd._courant_nstp_canonical(v, size, mask.copy(), 100.0, nstp_cap=2000,
                                refined_cell_size=REFINED_CELL_SIZE, profile="legacy_srcpulse")
    assert calls == []   # a legacy profile never dispatches to the corrected policy

    tsd._courant_nstp_canonical(v, size, mask.copy(), 100.0, nstp_cap=2000,
                                refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec,
                                profile="exp_v1")
    assert calls == ["exp_v1"]   # the selected policy id determined which implementation ran


# ---------------------------------------------------------------------------
# 13. THE gap test (review round 1, Section 4): the unique max Cr sits in a
# cell excluded SOLELY by the sliver floor, not by an explicit `exclusions`
# id -- without this, every other test here could pass while global
# reporting is still wrong for floor-excluded cells.
# ---------------------------------------------------------------------------
def test_global_max_cr_comes_from_a_floor_excluded_cell():
    v = np.full(6, 1.0)
    size = np.full(6, 10.0)
    size[2] = 1.0     # below 0.4*10=4.0 -> excluded from selection by the FLOOR ALONE
    v[2] = 100.0      # the unique dominant ratio (100/1=100) if it were counted
    mask = np.ones(6, dtype=bool)
    spec = MeshSpec()   # single level, cell_size=10.0 -> floor=4.0
    total_time = 50.0

    nstp, dt, cr, diag = tsd._courant_nstp_canonical(
        v, size, mask.copy(), total_time, exclusions=[], nstp_cap=5000,
        refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec, profile="exp_v1")

    # nstp/dt are sized off the SURVIVING (floor-filtered) selection
    assert diag["v_bind"] != 100.0
    assert diag["ds_bind"] >= diag["floor"]

    # but the REPORTED Cr reflects the floor-excluded cell's huge ratio
    expected_cr = float((v * dt / size).max())          # over the WHOLE corridor
    assert cr == pytest.approx(expected_cr)
    assert cr == pytest.approx(100.0 * dt)

    sel_only = np.array([0, 1, 3, 4, 5])
    sel_only_cr = float((v[sel_only] * dt / size[sel_only]).max())
    assert cr != pytest.approx(sel_only_cr)


# ---------------------------------------------------------------------------
# 14-17. exp_v1 degenerate/invalid-input raises, named individually
# ---------------------------------------------------------------------------
def test_exp_v1_raises_on_empty_selection():
    v = np.full(4, 1.0)
    size = np.full(4, 0.1)   # every cell below the floor
    mask = np.ones(4, dtype=bool)
    spec = MeshSpec()
    with pytest.raises(ValueError, match="floor-filtered selection is empty"):
        tsd._courant_nstp_canonical(v, size, mask.copy(), 100.0, nstp_cap=2000,
                                    refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec,
                                    profile="exp_v1")


def test_exp_v1_raises_on_nonpositive_critical():
    size = np.full(4, 10.0)
    mask = np.ones(4, dtype=bool)
    spec = MeshSpec()

    v_zero = np.zeros(4)
    with pytest.raises(ValueError, match="nonpositive or non-finite"):
        tsd._courant_nstp_canonical(v_zero, size, mask.copy(), 100.0, nstp_cap=2000,
                                    refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec,
                                    profile="exp_v1")

    v_neg = np.full(4, -1.0)
    with pytest.raises(ValueError, match="nonpositive or non-finite"):
        tsd._courant_nstp_canonical(v_neg, size, mask.copy(), 100.0, nstp_cap=2000,
                                    refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec,
                                    profile="exp_v1")


def test_exp_v1_raises_on_invalid_mesh_spec():
    v, size, mask = _fields(4)

    with pytest.raises(ValueError, match="mesh_spec"):
        tsd._courant_nstp_canonical(v, size, mask.copy(), 100.0, nstp_cap=2000,
                                    refined_cell_size=REFINED_CELL_SIZE, profile="exp_v1")

    empty_levels = MeshSpec(levels=())
    with pytest.raises(ValueError, match="mesh_spec"):
        tsd._courant_nstp_canonical(v, size, mask.copy(), 100.0, nstp_cap=2000,
                                    refined_cell_size=REFINED_CELL_SIZE, mesh_spec=empty_levels,
                                    profile="exp_v1")

    for bad_cell_size in (0.0, -5.0, float("nan"), float("inf")):
        bad_spec = MeshSpec(levels=(MeshLevel(cell_size=bad_cell_size),))
        with pytest.raises(ValueError, match="finite and > 0"):
            tsd._courant_nstp_canonical(v, size, mask.copy(), 100.0, nstp_cap=2000,
                                        refined_cell_size=REFINED_CELL_SIZE, mesh_spec=bad_spec,
                                        profile="exp_v1")


def test_exp_v1_raises_on_nonfinite_sizes():
    v, size, mask = _fields(4)
    spec = MeshSpec()

    for bad_value in (float("nan"), float("inf"), 0.0, -1.0):
        bad_size = size.copy()
        bad_size[1] = bad_value
        with pytest.raises(ValueError, match="size_cells contains"):
            tsd._courant_nstp_canonical(v, bad_size, mask.copy(), 100.0, nstp_cap=2000,
                                        refined_cell_size=REFINED_CELL_SIZE, mesh_spec=spec,
                                        profile="exp_v1")
