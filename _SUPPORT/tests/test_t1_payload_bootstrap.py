"""T1 S2 -- payload schema bootstrap (DESIGN_DOCS/T1_S2_brief.md v2).

Adds three pre-authorised payload fields (`sink_support_m`, `t_peak`,
`meta["sink_support_cells"]`) to `transport_srcpulse_demo.SrcPulseDemo` at
their identity defaults -- no behaviour change, no number moves. Its whole
purpose is that `t0_gate_harness.py compare` aborts with
``missing=['sink_support_m', 't_peak']`` until these fields exist.

Two of these node names predate the codex-reviewed frozen design in brief
Section 3.1 (`t_peak` is declared ``field(init=False)`` and REFUSES any
constructor value with a ``TypeError``, rather than silently "correcting" a
wrong one). Both `test_t_peak_cannot_be_overridden_at_construction` and
`test_passing_t_peak_to_the_constructor_raises` therefore assert the SAME
underlying invariant (refusal, not correction) through two different
constructor calls -- see each docstring below.

Run with:  uv run pytest _SUPPORT/tests/test_t1_payload_bootstrap.py -v
Use `-m "not slow"` to run only the fast, solve-free tests.
"""
import dataclasses
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "scripts"))

import transport_srcpulse_demo as tsd  # noqa: E402
import t0_gate_harness as gate  # noqa: E402

MASS_G = 3.0e5
PULSE_DAYS = 30.0
TOTAL_DAYS = 120.0
SOLUBILITY_MGL = 1000.0


def _dummy_kwargs(**overrides):
    """Minimal valid SrcPulseDemo constructor kwargs (no MF6 solve). Every
    named test below that does not need a REAL run builds a dummy instance
    from this, mirroring the existing fixtures in
    test_transport_srcpulse_demo.py (:409, :487) that this brief promises not
    to have to edit."""
    kwargs = dict(
        times=np.array([0.0, 1.0]), breakthrough=np.array([0.0, 1.0]),
        peak_mgL=1.0, arrival_day=5.0, mass_balance={"a": 1.0}, solubility_ok=True,
        emergent_C_mgL=1.0, solubility_mgL=1.0, solubility_margin=1.0,
        PeL_min=1.0, PeL_max=1.0, PeT_min=1.0, PeT_max=1.0,
        mass_g=1.0, pulse_days=1.0, total_days=2.0, smassrate_gpd=1.0,
        src_cells=[0], ext_cell=1, inj_cell=2, spill_xy=(0.0, 0.0),
        alpha_L=10.0, alpha_T=1.0, R=1.0, rho_b=1800.0, Kd=0.0, lam=0.0,
        meta={"k": "v"}, locked=dict(tsd.LOCKED_PARAMS))
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# session-scoped COLD workspace, shared across the real (slow) fixtures below
# -- mirrors test_transport_srcpulse_demo.py's `case_ws` fixture exactly, so
# this file does its own independent cold solves rather than accidentally
# reusing (or polluting) that module's ambient/session cache.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def case_ws(tmp_path_factory):
    return tmp_path_factory.mktemp("t1_payload_bootstrap_ws")


@pytest.fixture(scope="module")
def demo(case_ws):
    """One real, cold, coupled GWF+GWT solve for the whole module (the
    LOCKED conservative-transport variant, identical params to
    test_transport_srcpulse_demo.py's own `demo` fixture)."""
    return tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, case_ws=case_ws, force=False)


@pytest.fixture(scope="module")
def flow_grid_and_gwf(case_ws):
    """A REAL, independent oracle for the WEL stress-period-data test: the
    actual public builders (load_limmat_flow -> refine_corridor -> new_sim ->
    add_flow_model), run to a flow-only solve with NO transport coupling.
    Calling `build_srcpulse_demo` (the edited builder) a second time would
    prove nothing -- both calls share the identical code path and, on a cache
    hit, the identical cached array. This fixture instead exercises the
    SAME production `add_flow_model` function directly, giving `gwf.get_
    package("injw"/"absw").stress_period_data` -- an object nothing else in
    this file asserts against -- to compare byte-for-byte against a value
    built independently from the frozen legacy expressions."""
    cgwf, boundary, rivers, exe = tsd.load_limmat_flow()
    grid = tsd.refine_corridor(cgwf, boundary, rivers, case_ws=case_ws / "oracle")
    sim = tsd.new_sim(case_ws / "oracle", pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                       nstp_per_period=20, exe=exe)
    gwf = tsd.add_flow_model(sim, grid)
    return grid, gwf


# ---------------------------------------------------------------------------
# exit criterion 2: emitted WEL stress-period data is byte-identical to today's
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_wel_stress_period_data_identical_to_legacy(flow_grid_and_gwf):
    """A REAL oracle (brief Section 4, codex #7): `injc`/`extc` are read off
    the actual refined grid (`flow_grid_and_gwf`), and the expected records
    are constructed INDEPENDENTLY from the frozen legacy expressions --
    `[[(0, injc), abs(DOUBLET_Q)]]` / `[[(0, extc), -abs(DOUBLET_Q)]]` --
    never by calling `add_flow_model` a second time. Compares dtype, shape
    and bytes of the ACTUAL emitted `injw`/`absw` stress-period-data arrays.

    MF6's `cellid` field is stored as numpy `dtype=object` (each element a
    Python tuple) -- an array-level `.tobytes()` on an object-dtype field
    serialises PYTHON OBJECT POINTERS, not the tuple's contents (verified:
    two independently-built arrays holding an EQUAL, non-literal `(0, n)`
    tuple do not compare byte-equal). So `.tobytes()` is applied only to the
    genuinely numeric `q` sub-field, where it is exact; `cellid` is compared
    by value instead. Together the three checks (dtype, shape, per-field
    bytes/value) still prove full record identity, byte-for-byte wherever a
    byte comparison is meaningful.
    """
    grid, gwf = flow_grid_and_gwf
    injc = grid["inj_cell"]
    extc = grid["ext_cell"]

    injw_actual = gwf.get_package("injw").stress_period_data.get_data(0)
    absw_actual = gwf.get_package("absw").stress_period_data.get_data(0)

    # Independent oracle: same dtype (structural, not a value under test) as
    # the actual output, but VALUES built from the frozen legacy expressions
    # transcribed straight from add_flow_model's own source (transport_
    # srcpulse_demo.py), not re-derived by calling it.
    expected_injw = np.array([((0, injc), abs(tsd.DOUBLET_Q))], dtype=injw_actual.dtype)
    expected_absw = np.array([((0, extc), -abs(tsd.DOUBLET_Q))], dtype=absw_actual.dtype)

    for actual, expected in ((injw_actual, expected_injw), (absw_actual, expected_absw)):
        assert actual.dtype == expected.dtype
        assert actual.shape == expected.shape
        # numeric sub-field: exact byte comparison.
        assert actual["q"].tobytes() == expected["q"].tobytes()
        # object (tuple) sub-field: value comparison (see docstring above).
        assert [tuple(c) for c in actual["cellid"]] == [tuple(c) for c in expected["cellid"]]


# ---------------------------------------------------------------------------
# exit criterion 3: t_peak == arrival_day, cold AND warm-cache
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_t_peak_equals_arrival_day_cold_and_warm(demo, case_ws):
    """Exercises BOTH paths (brief Section 4): `demo` is a real, cold MF6
    solve; the second call below, with IDENTICAL params against the SAME
    `case_ws`, hits the warm on-disk cache (`_load_cache`) instead of
    re-solving -- the path `t0_gate_harness.py`'s `force=True` gate call
    never exercises. `t_peak == arrival_day` must hold on both."""
    assert demo.t_peak == demo.arrival_day

    cache_files_before = sorted((case_ws).glob("srcpulse_cache_*.npz"))
    assert len(cache_files_before) == 1  # sanity: demo's cold solve wrote exactly one

    warm = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, case_ws=case_ws, force=False)

    cache_files_after = sorted((case_ws).glob("srcpulse_cache_*.npz"))
    assert cache_files_after == cache_files_before  # no NEW cache -> this really hit the warm path

    assert warm.t_peak == warm.arrival_day
    assert warm.arrival_day == demo.arrival_day
    assert warm.t_peak == demo.t_peak


# ---------------------------------------------------------------------------
# brief Section 3.1: init=False refuses input rather than correcting it
# ---------------------------------------------------------------------------
def test_t_peak_cannot_be_overridden_at_construction():
    """§3.1: passing a WRONG (deliberately mismatched-vs-arrival_day) `t_peak`
    must still be refused outright. `init=False` means the constructor has NO
    parameter to accept any value for `t_peak` -- correct or not -- so
    "override" is impossible rather than merely "corrected": this is the
    behavioural content behind this test's name, superseding the older
    "__post_init__ corrects it" framing (brief §3.1, codex S2 review #2) that
    predates the frozen `init=False`-refuses design."""
    with pytest.raises(TypeError):
        tsd.SrcPulseDemo(**_dummy_kwargs(arrival_day=1.0), t_peak=999.0)


def test_passing_t_peak_to_the_constructor_raises():
    """§3.1: `init=False` refuses `t_peak` unconditionally -- even a value
    that HAPPENS to equal `arrival_day` is still rejected, because there is no
    `t_peak` parameter in `__init__` at all (dataclasses excludes `init=False`
    fields from the generated signature)."""
    with pytest.raises(TypeError):
        tsd.SrcPulseDemo(**_dummy_kwargs(arrival_day=1.0), t_peak=1.0)


# ---------------------------------------------------------------------------
# exit criterion 4: meta["sink_support_cells"] matches the emitted WEL records
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_sink_support_cells_match_emitted_wel_records(demo):
    """`meta['sink_support_cells']` must equal the apportionment ACTUALLY
    applied by the WEL construction in `add_flow_model` -- one entry,
    `(ext_cell, -abs(DOUBLET_Q))` -- with `ext_cell`/`DOUBLET_Q` read off
    THIS run (`demo.ext_cell`), never hardcoded a second time (brief Section
    3.3 / contract Section 3)."""
    expected = [(int(demo.ext_cell), -abs(float(tsd.DOUBLET_Q)))]
    assert demo.meta["sink_support_cells"] == expected


def test_sink_support_m_is_zero_and_cells_have_one_entry(demo):
    """The identity defaults (brief Section 2 / contract Section 3):
    `sink_support_m == 0.0` (today's behaviour -- the whole rate on one
    nearest-centroid cell) and `sink_support_cells` carries exactly the one
    entry that behaviour implies -- NOT an empty list, which would misrepresent
    what the model actually did."""
    assert demo.sink_support_m == 0.0
    assert isinstance(demo.sink_support_m, float)

    cells = demo.meta["sink_support_cells"]
    assert len(cells) == 1
    idx, q = cells[0]
    assert isinstance(idx, int)
    assert isinstance(q, float)
    assert q < 0.0  # a sink: apportioned rate is negative


# ---------------------------------------------------------------------------
# brief Section 3.1: a stored t_peak/arrival_day mismatch is a CACHE MISS
# ---------------------------------------------------------------------------
def test_stored_t_peak_mismatch_is_a_cache_miss(tmp_path):
    """`_load_cache` cannot pass `t_peak` to the constructor (init=False), so
    it reads the stored value and VALIDATES it against the stored
    `arrival_day`. A corrupted/stale alias must MISS, never be silently
    repaired -- otherwise a corrupted alias in a cache would be invisible."""
    dummy = tsd.SrcPulseDemo(**_dummy_kwargs(arrival_day=5.0))
    assert dummy.t_peak == pytest.approx(5.0)

    params = {"mass_g": 1.0, "src_sha": "deadbeef00000000"}

    # uncorrupted round-trip still HITS -- proves the eventual miss below is
    # caused by the corruption, not by some unrelated save/load defect.
    good_path = tmp_path / "good_cache.npz"
    tsd._save_cache(good_path, dummy, params)
    hit = tsd._load_cache(good_path, params)
    assert hit is not None
    assert hit.t_peak == pytest.approx(5.0)

    bad_path = tmp_path / "bad_cache.npz"
    tsd._save_cache(bad_path, dummy, params)
    z = np.load(str(bad_path), allow_pickle=True)
    data = {k: z[k] for k in z.files}
    data["t_peak"] = np.array(999.0)  # deliberately mismatched vs stored arrival_day=5.0
    np.savez(str(bad_path), **data)

    miss = tsd._load_cache(bad_path, params)
    assert miss is None


def test_stored_t_peak_nan_arrival_day_nan_is_a_hit():
    """NaN-aware (brief Section 3.1): when the plume never arrives,
    `arrival_day` is legitimately NaN and so is its alias `t_peak` -- the
    mismatch check must treat NaN==NaN as agreement (a bare `!=` would call
    this a mismatch, since NaN != NaN), or every "never arrives" run would
    incorrectly miss its own cache forever."""
    import tempfile
    from pathlib import Path

    dummy = tsd.SrcPulseDemo(**_dummy_kwargs(arrival_day=float("nan")))
    assert math.isnan(dummy.t_peak)

    params = {"mass_g": 1.0, "src_sha": "deadbeef00000001"}
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "nan_cache.npz"
        tsd._save_cache(path, dummy, params)
        hit = tsd._load_cache(path, params)
        assert hit is not None
        assert math.isnan(hit.t_peak)
        assert math.isnan(hit.arrival_day)


# ---------------------------------------------------------------------------
# the payload matches exactly what the T0 gate harness expects (Section 4,
# "catches a drift between module and harness in ONE place")
# ---------------------------------------------------------------------------
def test_payload_field_set_matches_harness_candidate_schema(demo):
    """Fast, no-solve-of-its-own schema check PLUS one runtime check against
    the already-built `demo`: the module's dataclass field set (and the
    ACTUAL `meta` keys a real run produces) must equal exactly what
    `t0_gate_harness.build_payload(..., side="candidate")` expects
    (`CANDIDATE_TOP_LEVEL_FIELDS` / `CANDIDATE_META_KEYS`) -- a drift here
    would abort `compare` with a missing/extra-field GateAbort."""
    top_names = {f.name for f in dataclasses.fields(tsd.SrcPulseDemo)
                 if not f.name.startswith("_")}
    assert top_names == set(gate.CANDIDATE_TOP_LEVEL_FIELDS)

    assert set(demo.meta.keys()) == set(gate.CANDIDATE_META_KEYS)
