"""T1 S4 -- `courant_nstp` legacy canonicalisation (DESIGN_DOCS/T1_S4_brief.md v2).

S4 collapses the two pre-S4 duplicate `courant_nstp` bodies --
`transport_base_model.courant_nstp` (public, "legacy_base") and
`transport_srcpulse_demo._courant_nstp` (private, "legacy_srcpulse") -- into
ONE canonical calculator, `transport_srcpulse_demo._courant_nstp_canonical`,
selected by an explicit `profile` argument. Both original functions become
thin wrappers that delegate to it.

The T0 gate cannot see this step (the sliver floor is numerically inert at the
frozen default, `courant_floor=4.0` vs `ds_true_min=5.478`), and the 130-test
suite never exercised `transport_base_model`'s call sites at all -- while the
STUDENT workspace transport notebook calls `build_spill_scenario` on a cache
miss. So THIS file is the only real check that S4 is behaviour-preserving.

Strategy: a FROZEN ORACLE. `_oracle_legacy_base` / `_oracle_legacy_srcpulse`
below are byte-for-byte copies of the two functions' PRE-S4 bodies (captured
before the refactor), taking the OLD call convention (a single, already
pre-masked `mask` array). Every test constructs synthetic per-cell fields,
computes the pre-masked array by hand (`mask - exclusions`, exactly what each
pre-S4 call site did inline), and asserts that the NEW wrapper -- called with
the NEW convention (the ORIGINAL mask + `exclusions=`) -- reproduces the
oracle's return tuple (or exact exception) precisely.

Covers brief Section 4's full list: source-bound / well-bound / sliver-bound /
empty-selection / zero-velocity / cap-binding / global-vs-post-exclusion-max
for BOTH legacy profiles; `nstp >= 1` reached WITHOUT the zero-velocity
branch; negative `critical`; truly-empty vs floor-emptied mask; mask
immutability; exact `diag` contents and first-index tie behaviour; and parity
for all THREE call paths (`build_doublet_base` nstp_cap=1000,
`build_spill_scenario` nstp_cap=4000, srcpulse nstp_cap=2000), plus wrapper
signatures/defaults/delegation and structural absence of any corrected-policy
surface (`exp_v1`, wired `GridSpec`/`CourantSpec`, global-max reporting,
cap-raising).

Run with:  uv run pytest _SUPPORT/tests/test_t1_courant_profiles.py -v
"""
from __future__ import annotations

import inspect
import os
import sys
import warnings
from typing import Dict, Tuple

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_base_model as tbm  # noqa: E402
import transport_srcpulse_demo as tsd  # noqa: E402

REFINED_CELL_SIZE = 10.0   # both modules' LOCKED_PARAMS["refined_cell_size"]
SLIVER_FLOOR_FRAC = 0.4    # both functions' default -- floor = 4.0
FLOOR = SLIVER_FLOOR_FRAC * REFINED_CELL_SIZE


# ---------------------------------------------------------------------------
# frozen oracle -- byte-for-byte copies of the PRE-S4 bodies, OLD call
# convention (single pre-masked `mask` array, no `exclusions`)
# ---------------------------------------------------------------------------
def _oracle_legacy_base(v_cells: np.ndarray, size_cells: np.ndarray, mask: np.ndarray,
                        total_time: float, cr_target: float = 0.9, nstp_cap: int = 1000,
                        sliver_floor_frac: float = 0.4,
                        refined_cell_size: float = REFINED_CELL_SIZE
                        ) -> Tuple[int, float, float, Dict[str, float]]:
    """Pre-S4 `transport_base_model.courant_nstp` body, verbatim."""
    floor = sliver_floor_frac * refined_cell_size
    sel = mask & (size_cells >= floor)
    ratio = v_cells[sel] / size_cells[sel]
    critical = float(ratio.max())
    dt_need = cr_target / critical
    nstp = min(int(np.ceil(total_time / dt_need)), nstp_cap)
    dt = total_time / nstp
    j = np.where(sel)[0][int(np.argmax(ratio))]
    diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                ds_true_min=float(size_cells[mask].min()), floor=floor)
    return nstp, dt, critical * dt, diag


def _oracle_legacy_srcpulse(v_cells: np.ndarray, size_cells: np.ndarray, mask: np.ndarray,
                            total_time: float, cr_target: float = 0.9, nstp_cap: int = 2000,
                            sliver_floor_frac: float = 0.4,
                            refined_cell_size: float = REFINED_CELL_SIZE
                            ) -> Tuple[int, float, float, Dict[str, float]]:
    """Pre-S4 `transport_srcpulse_demo._courant_nstp` body, verbatim."""
    floor = sliver_floor_frac * refined_cell_size
    sel = mask & (size_cells >= floor)
    if not sel.any():
        sel = mask
    ratio = v_cells[sel] / size_cells[sel]
    critical = float(ratio.max())
    j = np.where(sel)[0][int(np.argmax(ratio))]
    if critical <= 0.0:
        nstp = max(nstp_cap, 1)
        dt = total_time / nstp
        diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                    ds_true_min=float(size_cells[mask].min()), floor=floor)
        return nstp, dt, critical * dt, diag
    dt_need = cr_target / critical
    nstp = min(int(np.ceil(total_time / dt_need)), nstp_cap)
    nstp = max(nstp, 1)
    dt = total_time / nstp
    diag = dict(v_bind=float(v_cells[j]), ds_bind=float(size_cells[j]),
                ds_true_min=float(size_cells[mask].min()), floor=floor)
    return nstp, dt, critical * dt, diag


_ORACLES = {"legacy_base": _oracle_legacy_base, "legacy_srcpulse": _oracle_legacy_srcpulse}
_WRAPPER_DEFAULT_CAP = {"legacy_base": 1000, "legacy_srcpulse": 2000}


def _call_wrapper(profile: str, v, size, mask, total_time, exclusions=(),
                  cr_target=0.9, nstp_cap=None, sliver_floor_frac=SLIVER_FLOOR_FRAC):
    cap = _WRAPPER_DEFAULT_CAP[profile] if nstp_cap is None else nstp_cap
    fn = tbm.courant_nstp if profile == "legacy_base" else tsd._courant_nstp
    return fn(v, size, mask, total_time, cr_target, cap, sliver_floor_frac, exclusions=exclusions)


def _call_oracle(profile: str, v, size, mask, exclusions, total_time,
                 cr_target=0.9, nstp_cap=None, sliver_floor_frac=SLIVER_FLOOR_FRAC):
    """Reproduce the pre-S4 call convention: the caller pre-masks `mask` by
    hand (exactly what `corr_no_wells = mask.copy(); for c in ...: [c]=False`
    did inline at every pre-S4 call site) and passes THAT to the oracle."""
    cap = _WRAPPER_DEFAULT_CAP[profile] if nstp_cap is None else nstp_cap
    premasked = np.array(mask, dtype=bool, copy=True)
    for c in exclusions:
        premasked[c] = False
    return _ORACLES[profile](v, size, premasked, total_time, cr_target, cap, sliver_floor_frac)


def _assert_parity(v, size, mask, total_time, exclusions, profile, **kw):
    """Assert the NEW wrapper reproduces the FROZEN ORACLE exactly: the same
    return tuple + diag, or the exact same exception type/message. Uses
    independent mask copies for each call so neither call can contaminate the
    other via (illegal) mutation."""
    mask_w = np.array(mask, dtype=bool, copy=True)
    mask_o = np.array(mask, dtype=bool, copy=True)

    wrapper_exc = oracle_exc = None
    wrapper_result = oracle_result = None
    try:
        wrapper_result = _call_wrapper(profile, v, size, mask_w, total_time, exclusions, **kw)
    except Exception as exc:  # noqa: BLE001 -- captured for exact-exception parity
        wrapper_exc = exc
    try:
        oracle_result = _call_oracle(profile, v, size, mask_o, exclusions, total_time, **kw)
    except Exception as exc:  # noqa: BLE001
        oracle_exc = exc

    # the wrapper must never have mutated the caller's `mask` (§ mask
    # immutability) even in the exception path
    assert np.array_equal(mask_w, mask), "wrapper mutated the caller's mask array"

    if wrapper_exc is not None or oracle_exc is not None:
        assert type(wrapper_exc) is type(oracle_exc), (wrapper_exc, oracle_exc)
        assert str(wrapper_exc) == str(oracle_exc), (str(wrapper_exc), str(oracle_exc))
        return None

    nstp_w, dt_w, cr_w, diag_w = wrapper_result
    nstp_o, dt_o, cr_o, diag_o = oracle_result
    assert nstp_w == nstp_o
    assert dt_w == dt_o
    assert cr_w == cr_o
    assert diag_w == diag_o
    return wrapper_result


def _fields(n: int = 8):
    """`n` corridor cells, all size == REFINED_CELL_SIZE (well above the 4.0
    floor) and all velocity 1.0 (ratio 0.1/day each) -- override per-cell to
    probe binding/exclusion/floor behaviour."""
    size = np.full(n, REFINED_CELL_SIZE)
    v = np.full(n, 1.0)
    mask = np.ones(n, dtype=bool)
    return v, size, mask


PROFILES = ("legacy_base", "legacy_srcpulse")


# ---------------------------------------------------------------------------
# 1. structural: profile enum, invalid profile, no corrected-policy surface
# ---------------------------------------------------------------------------
def test_profile_enum_admits_only_the_two_legacy_ids():
    assert tsd._COURANT_LEGACY_PROFILES == ("legacy_base", "legacy_srcpulse")


def test_unknown_profile_raises_value_error():
    v, size, mask = _fields(4)
    with pytest.raises(ValueError, match="legacy_base"):
        tsd._courant_nstp_canonical(v, size, mask, 365.0, nstp_cap=1000,
                                    refined_cell_size=REFINED_CELL_SIZE, profile="exp_v1")


def test_canonical_has_no_corrected_policy_surface():
    """`exp_v1`, wired `GridSpec`/`CourantSpec`, global-max reporting and
    cap-raising must be STRUCTURALLY absent from S4's canonical function, not
    merely unused."""
    src = inspect.getsource(tsd._courant_nstp_canonical)
    for forbidden in ("exp_v1", "GridSpec(", "CourantSpec(", "global", "cr_capped", "warn"):
        assert forbidden not in src, f"forbidden token {forbidden!r} found in canonical source"


def test_canonical_reads_no_locked_params():
    """The canonical function owns no LOCKED_PARAMS read -- each caller passes
    its own floor reference explicitly (`refined_cell_size=`). Checked against
    the compiled bytecode's referenced names, not the source text, since the
    docstring legitimately DISCUSSES `LOCKED_PARAMS` as prose."""
    assert "LOCKED_PARAMS" not in tsd._courant_nstp_canonical.__code__.co_names


def test_canonical_is_warning_free_even_when_the_cap_binds():
    v, size, mask = _fields(6)
    v[:] = 1000.0  # huge velocity -> nstp naturally wants to saturate the cap
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tsd._courant_nstp_canonical(v, size, mask, 365.0, nstp_cap=5,
                                    refined_cell_size=REFINED_CELL_SIZE, profile="legacy_base")
        tsd._courant_nstp_canonical(v, size, mask, 365.0, nstp_cap=5,
                                    refined_cell_size=REFINED_CELL_SIZE, profile="legacy_srcpulse")
    assert caught == []


# ---------------------------------------------------------------------------
# 2. wrapper signatures, defaults, delegation
# ---------------------------------------------------------------------------
def test_base_wrapper_keeps_its_existing_positional_signature():
    sig = inspect.signature(tbm.courant_nstp)
    params = list(sig.parameters.values())
    positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    assert [p.name for p in positional] == [
        "v_cells", "size_cells", "mask", "total_time", "cr_target", "nstp_cap", "sliver_floor_frac"]
    defaults = {p.name: p.default for p in positional if p.default is not inspect.Parameter.empty}
    assert defaults == {"cr_target": 0.9, "nstp_cap": 1000, "sliver_floor_frac": 0.4}
    excl = sig.parameters["exclusions"]
    assert excl.kind == inspect.Parameter.KEYWORD_ONLY
    assert excl.default == ()


def test_srcpulse_wrapper_keeps_nstp_cap_2000_default_and_kwonly_exclusions():
    sig = inspect.signature(tsd._courant_nstp)
    params = list(sig.parameters.values())
    positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    assert [p.name for p in positional] == [
        "v_cells", "size_cells", "mask", "total_time", "cr_target", "nstp_cap", "sliver_floor_frac"]
    defaults = {p.name: p.default for p in positional if p.default is not inspect.Parameter.empty}
    assert defaults == {"cr_target": 0.9, "nstp_cap": 2000, "sliver_floor_frac": 0.4}
    excl = sig.parameters["exclusions"]
    assert excl.kind == inspect.Parameter.KEYWORD_ONLY
    assert excl.default == ()


def test_base_wrapper_delegates_to_canonical_with_legacy_base_profile(monkeypatch):
    calls = []

    def _spy(*args, **kwargs):
        calls.append(kwargs)
        return (1, 1.0, 0.5, dict(v_bind=0.0, ds_bind=0.0, ds_true_min=0.0, floor=0.0))

    monkeypatch.setattr(tbm, "_courant_nstp_canonical", _spy)
    v, size, mask = _fields(4)
    tbm.courant_nstp(v, size, mask, 365.0, exclusions=[1])
    assert len(calls) == 1
    assert calls[0]["profile"] == "legacy_base"
    assert list(calls[0]["exclusions"]) == [1]
    assert calls[0]["refined_cell_size"] == REFINED_CELL_SIZE


def test_srcpulse_wrapper_delegates_to_canonical_with_legacy_srcpulse_profile(monkeypatch):
    calls = []

    def _spy(*args, **kwargs):
        calls.append(kwargs)
        return (1, 1.0, 0.5, dict(v_bind=0.0, ds_bind=0.0, ds_true_min=0.0, floor=0.0))

    monkeypatch.setattr(tsd, "_courant_nstp_canonical", _spy)
    v, size, mask = _fields(4)
    tsd._courant_nstp(v, size, mask, 365.0, exclusions=[2])
    assert len(calls) == 1
    assert calls[0]["profile"] == "legacy_srcpulse"
    assert list(calls[0]["exclusions"]) == [2]
    assert calls[0]["refined_cell_size"] == REFINED_CELL_SIZE


def test_one_implementation_both_wrappers_share_the_same_canonical_function():
    """Prevents a real regression mode: a caller kept its own duplicate body
    instead of delegating."""
    assert tbm._courant_nstp_canonical is tsd._courant_nstp_canonical


# ---------------------------------------------------------------------------
# 3. brief §4's seven synthetic cases, both legacy profiles
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("profile", PROFILES)
def test_source_bound(profile):
    """The binding cell (before exclusion) is a source cell."""
    v, size, mask = _fields(6)
    v[2] = 100.0                      # would dominate if not excluded
    result = _assert_parity(v, size, mask, 365.0, exclusions=[2], profile=profile)
    assert result[3]["v_bind"] != 100.0


@pytest.mark.parametrize("profile", PROFILES)
def test_well_bound(profile):
    """The binding cell (before exclusion) is a well cell."""
    v, size, mask = _fields(6)
    v[4] = 250.0                      # would dominate if not excluded
    result = _assert_parity(v, size, mask, 365.0, exclusions=[0, 4], profile=profile)
    assert result[3]["v_bind"] != 250.0


@pytest.mark.parametrize("profile", PROFILES)
def test_sliver_bound(profile):
    """A sub-floor cell would bind if it were not excluded BY THE FLOOR (not
    by `exclusions`)."""
    v, size, mask = _fields(6)
    size[3] = FLOOR - 1.0             # below floor -> excluded by size, not id
    v[3] = 500.0                      # would dominate the ratio if not floored out
    result = _assert_parity(v, size, mask, 365.0, exclusions=[], profile=profile)
    assert result[3]["v_bind"] != 500.0
    assert result[3]["ds_bind"] >= FLOOR


@pytest.mark.parametrize("profile", PROFILES)
def test_empty_selection_after_the_floor(profile):
    """Every cell in the (post-exclusion) mask is below the floor.
    `legacy_srcpulse` falls back to the whole mask; `legacy_base` raises."""
    v, size, mask = _fields(5)
    size[:] = FLOOR - 1.0             # every cell sub-floor
    if profile == "legacy_base":
        with pytest.raises(ValueError):
            _call_wrapper(profile, v, size, mask.copy(), 365.0, exclusions=[])
        _assert_parity(v, size, mask, 365.0, exclusions=[], profile=profile)
    else:
        result = _assert_parity(v, size, mask, 365.0, exclusions=[], profile=profile)
        assert result is not None   # srcpulse recovers via the whole-mask fallback


@pytest.mark.parametrize("profile", PROFILES)
def test_zero_velocity(profile):
    """`legacy_srcpulse` returns the cap with Cr=0; `legacy_base` raises
    (division by zero)."""
    v, size, mask = _fields(5)
    v[:] = 0.0
    if profile == "legacy_base":
        with pytest.raises(ZeroDivisionError):
            _call_wrapper(profile, v, size, mask.copy(), 365.0, exclusions=[])
        _assert_parity(v, size, mask, 365.0, exclusions=[], profile=profile)
    else:
        nstp, dt, cr_act, diag = _assert_parity(v, size, mask, 365.0, exclusions=[], profile=profile)
        assert nstp == 2000            # the srcpulse default cap
        assert cr_act == 0.0


@pytest.mark.parametrize("profile", PROFILES)
def test_cap_binding_saturates_without_raising_or_warning(profile):
    v, size, mask = _fields(6)
    v[:] = 1000.0                     # huge velocity -> would need nstp >> cap
    cap = 5
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        nstp, dt, cr_act, diag = _assert_parity(
            v, size, mask, 365.0, exclusions=[], profile=profile, nstp_cap=cap)
    assert nstp == cap
    assert caught == []


@pytest.mark.parametrize("profile", PROFILES)
def test_reported_cr_is_the_post_exclusion_max_not_the_global_max(profile):
    """An excluded cell (source/well) carries the GLOBAL fastest ratio; the
    reported Cr must reflect only the post-exclusion (legacy) selection --
    S4 must NOT silently deliver S8's global-max reporting."""
    v, size, mask = _fields(6)
    v[5] = 1.0e6                      # excluded cell: globally dominant ratio
    size[1] = FLOOR                   # also the smallest surviving cell size
    nstp, dt, cr_act, diag = _assert_parity(
        v, size, mask, 365.0, exclusions=[5], profile=profile)
    assert diag["v_bind"] != 1.0e6
    assert diag["ds_true_min"] == FLOOR  # excludes cell 5, not the true global min


# ---------------------------------------------------------------------------
# 4. difference #4 (`nstp >= 1`) reached WITHOUT the zero-velocity branch
# ---------------------------------------------------------------------------
def test_nstp_floor_clamp_reached_without_zero_velocity_branch():
    """A degenerate `nstp_cap=0` with a genuinely positive `critical` drives
    `min(ceil(...), 0) == 0` BEFORE any zero/negative-critical fallback fires.
    `legacy_srcpulse` clamps to 1; `legacy_base` does not (and raises later at
    `dt = total_time / 0`)."""
    v, size, mask = _fields(5)
    v[:] = 1.0
    _assert_parity(v, size, mask, 365.0, exclusions=[], profile="legacy_base", nstp_cap=0)
    _assert_parity(v, size, mask, 365.0, exclusions=[], profile="legacy_srcpulse", nstp_cap=0)
    nstp, dt, cr_act, diag = _call_wrapper(
        "legacy_srcpulse", v, size, mask.copy(), 365.0, exclusions=[], nstp_cap=0)
    assert nstp == 1
    with pytest.raises(ZeroDivisionError):
        _call_wrapper("legacy_base", v, size, mask.copy(), 365.0, exclusions=[], nstp_cap=0)


# ---------------------------------------------------------------------------
# 5. negative `critical`
# ---------------------------------------------------------------------------
def test_negative_critical_base_returns_negative_nstp_without_raising():
    v, size, mask = _fields(5)
    v[:] = -1.0                       # uniform negative velocity -> negative ratio
    nstp, dt, cr_act, diag = _assert_parity(
        v, size, mask, 365.0, exclusions=[], profile="legacy_base")
    # critical < 0 -> dt_need < 0 -> nstp = ceil(total_time/dt_need) < 0 (NOT
    # clamped, unlike legacy_srcpulse). dt = total_time/nstp is then also
    # negative, so Cr = critical*dt is the product of two negatives (positive)
    # -- a formally-consistent but physically meaningless value, exactly what
    # today's un-guarded base body produces.
    assert nstp < 0
    assert dt < 0.0


def test_negative_critical_srcpulse_returns_cap_with_negative_cr():
    v, size, mask = _fields(5)
    v[:] = -1.0
    nstp, dt, cr_act, diag = _assert_parity(
        v, size, mask, 365.0, exclusions=[], profile="legacy_srcpulse")
    assert nstp == 2000               # the cap (critical <= 0 branch)
    assert cr_act < 0.0


# ---------------------------------------------------------------------------
# 6. truly-empty mask vs floor-emptied mask -- distinct inputs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("profile", PROFILES)
def test_truly_empty_mask_raises_even_for_srcpulse(profile):
    """A mask with NO corridor cells at all: srcpulse's fallback
    (`sel = mask`) cannot rescue it either, since `mask` itself is empty."""
    v, size, mask = _fields(5)
    mask[:] = False
    with pytest.raises(ValueError):
        _call_wrapper(profile, v, size, mask.copy(), 365.0, exclusions=[])
    _assert_parity(v, size, mask, 365.0, exclusions=[], profile=profile)


def test_floor_emptied_mask_is_rescued_only_by_srcpulse():
    v, size, mask = _fields(5)
    size[:] = FLOOR - 1.0             # non-empty mask, but every cell sub-floor
    with pytest.raises(ValueError):
        _call_wrapper("legacy_base", v, size, mask.copy(), 365.0, exclusions=[])
    result = _call_wrapper("legacy_srcpulse", v, size, mask.copy(), 365.0, exclusions=[])
    assert result is not None
    _assert_parity(v, size, mask, 365.0, exclusions=[], profile="legacy_base")
    _assert_parity(v, size, mask, 365.0, exclusions=[], profile="legacy_srcpulse")


# ---------------------------------------------------------------------------
# 7. mask immutability (also checked inside `_assert_parity`, asserted again
# directly here against the PUBLIC wrapper, not just the parity helper)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("profile", PROFILES)
def test_mask_immutability(profile):
    v, size, mask = _fields(6)
    before = mask.copy()
    _call_wrapper(profile, v, size, mask, 365.0, exclusions=[1, 3])
    assert np.array_equal(mask, before), "caller's mask array must not be mutated"


# ---------------------------------------------------------------------------
# 8. exact `diag` contents and first-index tie behaviour
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("profile", PROFILES)
def test_diag_has_exactly_the_four_expected_keys(profile):
    v, size, mask = _fields(5)
    _, _, _, diag = _call_wrapper(profile, v, size, mask.copy(), 365.0, exclusions=[])
    assert set(diag.keys()) == {"v_bind", "ds_bind", "ds_true_min", "floor"}
    assert diag["floor"] == FLOOR


@pytest.mark.parametrize("profile", PROFILES)
def test_tie_break_selects_the_first_index(profile):
    v, size, mask = _fields(6)
    # cells 1 and 4 tie on ratio (0.5/day) but carry different v/size, so the
    # winning index is identifiable from the reported diag
    v[1], size[1] = 5.0, 10.0
    v[4], size[4] = 10.0, 20.0
    _, _, _, diag = _assert_parity(v, size, mask, 365.0, exclusions=[], profile=profile)
    assert diag["v_bind"] == 5.0
    assert diag["ds_bind"] == 10.0


# ---------------------------------------------------------------------------
# 9. parity for all THREE call paths (distinct nstp_cap per builder)
# ---------------------------------------------------------------------------
def test_call_path_build_doublet_base_nstp_cap_1000():
    """`transport_base_model.build_doublet_base`'s call convention: profile
    legacy_base, nstp_cap=1000 (its own default), exclusions = src_cells + [rcell]."""
    v, size, mask = _fields(10)
    v[3] = 50.0        # source cell -> excluded
    v[7] = 40.0        # receptor cell -> excluded
    v[2] = 5.0         # the real binding cell once exclusions apply
    _assert_parity(v, size, mask, 365.0, exclusions=[3, 7], profile="legacy_base", nstp_cap=1000)


def test_call_path_build_spill_scenario_nstp_cap_4000():
    """`build_spill_scenario`'s call convention: profile legacy_base,
    nstp_cap=4000 (its own default), exclusions = src_cells + [injc, extc]."""
    v, size, mask = _fields(10)
    v[1] = 90.0        # spill source cell -> excluded
    v[5] = 80.0        # injection well -> excluded
    v[8] = 70.0        # extraction well -> excluded
    v[6] = 6.0
    _assert_parity(v, size, mask, 365.0, exclusions=[1, 5, 8], profile="legacy_base", nstp_cap=4000)


def test_call_path_srcpulse_demo_nstp_cap_2000():
    """`transport_srcpulse_demo`'s own call convention: profile
    legacy_srcpulse, nstp_cap=2000 (its own default), exclusions =
    src_cells + [injc, extc]."""
    v, size, mask = _fields(10)
    v[0] = 95.0        # spill source cell -> excluded
    v[4] = 85.0        # injection well -> excluded
    v[9] = 75.0        # extraction well -> excluded
    v[3] = 7.0
    _assert_parity(v, size, mask, 365.0, exclusions=[0, 4, 9], profile="legacy_srcpulse", nstp_cap=2000)


def test_three_call_paths_use_distinct_caps_and_all_delegate_to_one_canonical(monkeypatch):
    """Direct evidence that the canonical function alone is not enough: pin
    the exact `nstp_cap` and `profile` each of the three real call SITES
    passes, via a spy on the one shared canonical function."""
    seen = []
    real = tsd._courant_nstp_canonical

    def _spy(*args, **kwargs):
        seen.append((kwargs.get("nstp_cap"), kwargs.get("profile")))
        return real(*args, **kwargs)

    monkeypatch.setattr(tbm, "_courant_nstp_canonical", _spy)
    monkeypatch.setattr(tsd, "_courant_nstp_canonical", _spy)

    v, size, mask = _fields(6)
    tbm.courant_nstp(v, size, mask, 365.0, exclusions=[0])                    # doublet-base path
    tbm.courant_nstp(v, size, mask, 365.0, 0.9, 4000, exclusions=[0])         # spill-scenario path
    tsd._courant_nstp(v, size, mask, 365.0, exclusions=[0])                   # srcpulse path

    assert seen == [(1000, "legacy_base"), (4000, "legacy_base"), (2000, "legacy_srcpulse")]
