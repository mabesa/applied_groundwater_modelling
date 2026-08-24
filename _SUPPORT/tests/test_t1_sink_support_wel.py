"""Tests for T1 step S9b -- B-control WEL integration
(`DESIGN_DOCS/T1_S9b_brief.md` v2, C1 A6, `transport_srcpulse_demo.py`).

S9b wires S9a's extraction-support disc geometry into the doublet's
extraction WEL (`add_flow_model`'s "absw" package), replacing the hard-coded
single-cell literal, and records the apportionment ACTUALLY APPLIED in
`meta["sink_support_cells"]`.

Gate coverage is UNUSUALLY STRONG at the sentinel here: `sink_support_m` and
`meta["sink_support_cells"]` are schema-lifted and compared EXACTLY by the
T0.0 gate (`t0_gate_harness.py compare`), so a broken sentinel WILL fail
`compare` -- see the brief Sec 2.1. A POSITIVE radius stays gate-blind
(`compare` never runs `build_srcpulse_demo` at a positive `sink_support_m`,
since it RAISES `NotImplementedError` there, naming S9c) -- these tests are
the whole safety argument for the positive-radius WEL construction itself,
which ships and is exercised directly at the `add_flow_model` level.

Most tests here need the REAL refined corridor mesh (S9a's synthetic-geometry
tests in `test_t1_sink_support_geometry.py` already cover the pure
apportionment arithmetic) -- `add_flow_model` needs `grid["rgwf"]` (for
`idomain`) and `grid["modelgrid"]`, both only produced by a real
`refine_corridor` call. `base_grid` below pays for exactly ONE such call
(itself one real MF6 flow solve), reused by every "build-only" test that
just inspects the resulting WEL package's stress-period data -- FloPy's
`stress_period_data.get_data()` is available immediately after package
construction, so those tests need no `write_simulation`/`run_simulation` at
all. Only `sentinel_demo`, `supported_run` and their dependents pay for an
additional real coupled GWF+GWT solve.

Run with:  uv run pytest _SUPPORT/tests/test_t1_sink_support_wel.py -v
Use `-m "not slow"` to run only the fast, solve-free tests.
"""
import inspect
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_srcpulse_demo as tsd  # noqa: E402

DOUBLET_Q = tsd.DOUBLET_Q
Q_EXTRACT = -abs(DOUBLET_Q)  # extraction is NEGATIVE (S9a brief Sec 2)

# Small, cheap physics params -- these tests are about the WEL package's
# STRUCTURE, not the transport physics, so the pulse itself is kept tiny
# (mirrors test_t1_source_footprint.py's `cache_identity_case`).
MASS_G = 1.0e4
PULSE_DAYS = 5.0
TOTAL_DAYS = 15.0

# "tiny" / "partially covered" radii (brief Sec 4 exit criterion 15) --
# picked as small physical distances, NOT tuned to a specific cell count:
# the Triangle/Voronoi corridor mesh is platform-dependent (macOS vs Hub;
# see MEMORY transport-grid-peclet-spike), so tests below assert STRUCTURAL
# properties (non-raising, extc included, active, sorted, sums correctly)
# rather than an exact cell count or list.
TINY_RADIUS_M = 5.0
PARTIAL_RADIUS_M = 25.0

# "active-domain-edge" / "boundary-crossing" radii are NOT hardcoded here --
# `edge_and_crossing_radii` below discovers them by walking this ladder
# against the production `_sink_footprint_rates` itself, on THIS mesh.
_RADIUS_LADDER_M = (20.0, 40.0, 70.0, 110.0, 160.0, 220.0, 300.0, 400.0,
                    550.0, 750.0, 1000.0, 1500.0, 2000.0, 3000.0)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def wel_case_ws(tmp_path_factory):
    """Isolated, COLD workspace for every fixture in this module (mirrors
    test_transport_srcpulse_demo.py's `case_ws`) -- so a `build_srcpulse_demo`
    call here can never silently hit an ambient pre-warmed cache."""
    return tmp_path_factory.mktemp("t1_sink_support_wel_ws")


@pytest.fixture(scope="module")
def base_grid(wel_case_ws):
    """ONE real corridor refine (one real MF6 flow solve), reused by every
    "build-only" WEL-construction test below -- S9b only touches
    `add_flow_model`, which needs the mesh/idomain/cell-index geometry a
    `refine_corridor` call produces, not a fresh refine per test."""
    cgwf, boundary, rivers, exe = tsd.load_limmat_flow()
    grid = tsd.refine_corridor(cgwf, boundary, rivers, case_ws=wel_case_ws / "grid")
    return grid, exe


def _idomain(grid) -> np.ndarray:
    return np.asarray(grid["rgwf"].disv.idomain.array, dtype=int).reshape(-1)


@pytest.fixture(scope="module")
def edge_and_crossing_radii(base_grid):
    """Brief Sec 4 exit criterion 15: discover, on the REAL mesh, the
    largest ladder radius that still resolves ("active-domain-edge") and the
    first that raises ("boundary-crossing") -- by calling the production
    `_sink_footprint_rates` itself, not a second approximate geometric
    computation."""
    grid, _exe = base_grid
    mg = grid["modelgrid"]
    ncpl = grid["ncpl"]
    extc = grid["ext_cell"]
    idomain = _idomain(grid)
    last_ok = None
    for r in _RADIUS_LADDER_M:
        try:
            tsd._sink_footprint_rates(mg, ncpl, idomain, tsd.ABS_XY, r, extc, Q_EXTRACT)
        except ValueError:
            if last_ok is None:
                pytest.skip(
                    "first ladder radius already crosses the active-domain "
                    "boundary on this mesh; widen _RADIUS_LADDER_M")
            return last_ok, r
        last_ok = r
    pytest.skip("mesh domain too large for the ladder to find a "
                "boundary-crossing radius; widen _RADIUS_LADDER_M")


@pytest.fixture(scope="module")
def sentinel_demo(wel_case_ws):
    """ONE real coupled solve at the sentinel (`sink_support_m=0.0`) via the
    PUBLIC builder -- needed for the payload/`meta` field checks, which only
    `build_srcpulse_demo` assembles."""
    ws = wel_case_ws / "sentinel_demo"
    ws.mkdir(parents=True, exist_ok=True)
    return tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=1000.0, case_ws=ws, force=True)


@pytest.fixture(scope="module")
def supported_run(base_grid, wel_case_ws):
    """ONE real coupled GWF+GWT solve at a POSITIVE radius, composed from the
    PUBLIC builders directly (mirrors
    test_transport_srcpulse_demo.py::test_public_builders_compose_to_build_srcpulse_demo)
    -- `build_srcpulse_demo` itself refuses a positive `sink_support_m`
    (brief Sec 2.3), so this is the only way to exercise a solved,
    distributed-sink model."""
    grid, exe = base_grid
    ws = wel_case_ws / "supported_run"
    sim = tsd.new_sim(ws, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                      nstp_per_period=5, exe=exe)
    gwf = tsd.add_flow_model(sim, grid, sink_support_m=PARTIAL_RADIUS_M)
    gwt = tsd.add_transport_model(sim, gwf, grid, mass_g=MASS_G, pulse_days=PULSE_DAYS)
    ok, buf, sim = tsd.couple_and_run(sim, gwf, gwt, grid, ws)
    assert ok, "supported (positive sink_support_m) run did not converge"
    return dict(grid=grid, gwf=gwf, gwt=gwt, ws=ws)


def _build_gwf_only(base_grid, workdir, sink_support_m, nstp_per_period=5):
    """Compose `new_sim` + `add_flow_model` WITHOUT writing/running MF6.
    FloPy's `stress_period_data.get_data()` works immediately after package
    construction, so every purely-structural WEL check below costs no MF6
    solve at all -- only `sentinel_demo`/`supported_run` (and `base_grid`
    itself) pay for a real solve."""
    grid, exe = base_grid
    sim = tsd.new_sim(workdir, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                      nstp_per_period=nstp_per_period, exe=exe)
    return tsd.add_flow_model(sim, grid, sink_support_m=sink_support_m)


def _wel_budget_by_cell(gwf, text: str = "WEL") -> dict:
    """Flatten every WEL cell-by-cell budget record (across both WEL
    packages and both stress periods) into `{cell_index: [q, ...]}`, keyed
    by the 0-indexed DISV cell (`node` in the binary budget is 1-indexed)."""
    bud = gwf.output.budget()
    out: dict = {}
    for rec in bud.get_data(text=text):
        for row in rec:
            out.setdefault(int(row["node"]) - 1, []).append(float(row["q"]))
    return out


# ---------------------------------------------------------------------------
# 1. sentinel: structurally identical to the pre-S9b literal
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_sentinel_wel_stress_period_data_is_identical_to_the_literal(base_grid, tmp_path):
    """Exit criterion 1: at `sink_support_m == 0.0` the emitted `absw`
    stress-period data must match the frozen legacy literal
    `[[(0, extc), -abs(DOUBLET_Q))]]` -- constructed independently here (not
    copied from `add_flow_model`'s own source), then compared against the
    BUILT package's read-back via `_wel_support_cells`."""
    grid, _exe = base_grid
    extc = grid["ext_cell"]
    gwf = _build_gwf_only(base_grid, tmp_path, sink_support_m=0.0)

    expected = [(int(extc), float(Q_EXTRACT))]  # the frozen legacy expression, independently
    assert tsd._wel_support_cells(gwf) == expected

    raw = gwf.get_package("absw").stress_period_data.get_data(0)
    assert len(raw) == 1
    assert tuple(raw[0]["cellid"]) == (0, extc)
    assert float(raw[0]["q"]) == Q_EXTRACT


@pytest.mark.slow
def test_sentinel_fields_carry_their_identity_defaults(sentinel_demo):
    """Exit criterion 2: `sink_support_m` and `meta["sink_support_cells"]`
    carry EXACTLY their T0_0 Sec 3 identity defaults at the sentinel --
    asserted directly, not inferred from `compare`."""
    assert sentinel_demo.sink_support_m == 0.0
    assert sentinel_demo.meta["sink_support_cells"] == [
        (sentinel_demo.ext_cell, -abs(float(DOUBLET_Q)))]


# ---------------------------------------------------------------------------
# 2. sink_support_cells is derived from the BUILT spd, not recomputed
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_sink_support_cells_matches_the_built_spd(base_grid, tmp_path):
    """Exit criterion 3: `_wel_support_cells`'s read-back must agree with
    directly re-normalising the SAME package's raw `get_data(0)` -- proving
    the helper is a faithful read of what was actually built, at a POSITIVE
    radius (where there is more than one entry to get wrong)."""
    grid, _exe = base_grid
    gwf = _build_gwf_only(base_grid, tmp_path, sink_support_m=PARTIAL_RADIUS_M)

    recorded = tsd._wel_support_cells(gwf)
    raw = gwf.get_package("absw").stress_period_data.get_data(0)
    raw_pairs = sorted((int(r["cellid"][-1]), float(r["q"])) for r in raw)
    assert recorded == raw_pairs
    assert len(recorded) > 1  # a positive radius genuinely distributes the sink


@pytest.mark.slow
def test_generated_mf6_wel_records_match_the_input_spd(base_grid, tmp_path):
    """Exit criterion 1's caveat: "byte-identical" is not meaningful once
    FloPy has converted the input list into an `MFTransientList` -- check
    BOTH the input structure (what `add_flow_model` handed `ModflowGwfwel`)
    and the generated record (what FloPy actually stores), at the sentinel
    AND a positive radius."""
    grid, _exe = base_grid
    for i, radius in enumerate((0.0, PARTIAL_RADIUS_M)):
        gwf = _build_gwf_only(base_grid, tmp_path / f"case{i}", sink_support_m=radius)
        raw = gwf.get_package("absw").stress_period_data.get_data(0)
        assert "cellid" in raw.dtype.names and "q" in raw.dtype.names
        raw_pairs = sorted((int(r["cellid"][-1]), float(r["q"])) for r in raw)
        assert raw_pairs == tsd._wel_support_cells(gwf)
        total = math.fsum(q for _, q in raw_pairs)
        assert total == pytest.approx(Q_EXTRACT, rel=1e-9)


# ---------------------------------------------------------------------------
# 3. rate-sum + ordering invariants, at several radii
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.parametrize("radius", [0.0, TINY_RADIUS_M, PARTIAL_RADIUS_M])
def test_rates_sum_to_total_pumping_on_the_built_spd(base_grid, tmp_path, radius):
    """Exit criterion 4: `sum(q_i) == Q` on the BUILT spd, signed, for every
    radius (including the sentinel)."""
    gwf = _build_gwf_only(base_grid, tmp_path, sink_support_m=radius)
    spd = tsd._wel_support_cells(gwf)
    total = math.fsum(q for _, q in spd)
    assert total == pytest.approx(Q_EXTRACT, rel=1e-9)


@pytest.mark.slow
@pytest.mark.parametrize("radius", [0.0, TINY_RADIUS_M, PARTIAL_RADIUS_M])
def test_spd_cells_sorted_ascending(base_grid, tmp_path, radius):
    """Exit criterion 5: cells sorted ascending in the built spd."""
    gwf = _build_gwf_only(base_grid, tmp_path, sink_support_m=radius)
    cells = [c for c, _q in tsd._wel_support_cells(gwf)]
    assert cells == sorted(cells)
    assert len(cells) == len(set(cells))  # no duplicate cell entries


# ---------------------------------------------------------------------------
# 4. the injection WEL is untouched at every radius
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.parametrize("radius", [0.0, TINY_RADIUS_M, PARTIAL_RADIUS_M])
def test_injection_wel_is_unchanged_at_every_radius(base_grid, tmp_path, radius):
    """Exit criterion 7: `injw` is unchanged at every radius -- `T0_0...`
    Sec 3 names only the EXTRACTION-support disc."""
    grid, _exe = base_grid
    injc = grid["inj_cell"]
    gwf = _build_gwf_only(base_grid, tmp_path, sink_support_m=radius)
    got = gwf.get_package("injw").stress_period_data.get_data(0)
    assert len(got) == 1
    assert tuple(got[0]["cellid"]) == (0, injc)
    assert float(got[0]["q"]) == abs(DOUBLET_Q)


@pytest.mark.slow
def test_injection_wel_is_unchanged_at_the_edge_radius(base_grid, tmp_path,
                                                        edge_and_crossing_radii):
    grid, _exe = base_grid
    injc = grid["inj_cell"]
    edge_radius, _crossing = edge_and_crossing_radii
    gwf = _build_gwf_only(base_grid, tmp_path, sink_support_m=edge_radius)
    got = gwf.get_package("injw").stress_period_data.get_data(0)
    assert len(got) == 1
    assert tuple(got[0]["cellid"]) == (0, injc)
    assert float(got[0]["q"]) == abs(DOUBLET_Q)


# ---------------------------------------------------------------------------
# 5. no SSM change
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_ssm_stays_bare(base_grid, tmp_path):
    """Exit criterion 8 (brief Sec 1.1): `ModflowGwtssm(gwt)` must stay
    bare -- no explicit source list -- even with a distributed WEL, both
    structurally (the call site takes no extra args) and at runtime (the
    built package has no sources)."""
    grid, exe = base_grid
    sim = tsd.new_sim(tmp_path, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                      nstp_per_period=5, exe=exe)
    gwf = tsd.add_flow_model(sim, grid, sink_support_m=PARTIAL_RADIUS_M)
    gwt = tsd.add_transport_model(sim, gwf, grid, mass_g=MASS_G, pulse_days=PULSE_DAYS)

    ssm = gwt.get_package("ssm")
    assert ssm is not None
    assert not ssm.sources.get_data()  # None or empty -- no explicit source list

    src = inspect.getsource(tsd.add_transport_model)
    assert "ModflowGwtssm(gwt)" in src, (
        "add_transport_model's SSM call site must stay bare -- "
        "ModflowGwtssm(gwt) with no extra arguments")


# ---------------------------------------------------------------------------
# 6. a positive radius genuinely distributes the sink
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_positive_radius_yields_multiple_unequal_wel_entries(base_grid, tmp_path):
    """Exit criterion 9."""
    gwf = _build_gwf_only(base_grid, tmp_path, sink_support_m=PARTIAL_RADIUS_M)
    spd = tsd._wel_support_cells(gwf)
    assert len(spd) > 1
    rates = [q for _, q in spd]
    assert len(set(rates)) > 1


# ---------------------------------------------------------------------------
# 7. build_srcpulse_demo RAISES for a positive radius, naming S9c
# ---------------------------------------------------------------------------
def test_s9b_guard_was_lifted_by_s9c_which_added_the_readout():
    """HISTORY, kept deliberately rather than deleted.

    S9b made `build_srcpulse_demo` raise `NotImplementedError` naming S9c for
    any positive `sink_support_m`: the WEL was distributed but the readout
    still read ONE cell, so the builder would have returned plausible-looking
    `peak_mgL`/`arrival_day` values that were NOT extracted-concentration
    metrics. The guard existed so that wrong answer was unreachable, never
    because distributing the sink was itself unsupported.

    S9c added the flux-weighted readout and lifted the guard IN THE SAME
    commit, exactly as S9b's docstring promised. This test therefore asserts
    the guard is GONE -- if it ever returns, the readout has regressed too.

    Live behaviour is covered by
    `test_t1_sink_support_readout.py::test_positive_radius_no_longer_raises`;
    this one only pins the direction of travel, with no solve.
    """
    import inspect
    src = inspect.getsource(tsd.build_srcpulse_demo)
    assert "NotImplementedError" not in src or "sink_support_m > 0" not in src, (
        "S9b's positive-radius guard is back; S9c lifted it together with the "
        "flux-weighted readout, so its return would mean the readout regressed")


def test_negative_or_nonfinite_radius_raises_in_build_srcpulse_demo(tmp_path):
    """Exit criterion 'Validation' -- negative/non-finite raises `ValueError`
    (not `NotImplementedError`), before any GIS/MF6 work."""
    for bad in (-1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            tsd.build_srcpulse_demo(
                mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                sink_support_m=bad, case_ws=tmp_path)


@pytest.mark.slow
@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_negative_or_nonfinite_radius_raises(base_grid, tmp_path, bad):
    """Same validation, exercised directly at the `add_flow_model` level
    (reuses S9a's `_validate_footprint_radius`, brief Sec 3)."""
    grid, exe = base_grid
    sim = tsd.new_sim(tmp_path, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                      nstp_per_period=5, exe=exe)
    with pytest.raises(ValueError):
        tsd.add_flow_model(sim, grid, sink_support_m=bad)


# ---------------------------------------------------------------------------
# 8. cache identity
# ---------------------------------------------------------------------------
def test_sink_support_m_changes_the_cache_identity():
    """Exit criterion 6, first half: `sink_support_m` must fold into the
    `params` cache-identity dict, exactly like `footprint_radius_m`.

    Unlike `footprint_radius_m` (T1 S5), a POSITIVE `sink_support_m` always
    raises `NotImplementedError` before any solve (Sec 2.3), so -- unlike
    `test_t1_source_footprint.py::test_radius_changes_the_cache_identity` --
    there is no successful positive-radius BUILD to compare two cache FILES
    against. This asserts the field's presence in the `params` dict's own
    SOURCE (a static, solve-free check) instead of re-deriving the SHA1 hash
    by hand here, which would itself be exactly the kind of second, parallel
    derivation T0_0 Sec 3 warns against for `sink_support_cells`."""
    src = inspect.getsource(tsd.build_srcpulse_demo)
    start = src.index("params = dict(")
    end = src.index("cache_hash = hashlib.sha1(", start)
    params_block = src[start:end]
    assert "sink_support_m=float(sink_support_m)" in params_block


@pytest.mark.slow
@pytest.mark.slow
def test_warm_sentinel_cache_is_not_served_to_a_supported_run(wel_case_ws):
    """Exit criterion 6, second half -- the safety property, now tested FOR
    REAL rather than trivially.

    S9b could only satisfy this via the `NotImplementedError` guard, which
    ran before the cache was consulted: the property held, but the cache
    identity itself was never exercised (S9b recorded that as a deferred
    gap). S9c lifted the guard, so the property must now rest on what it was
    always supposed to rest on -- `sink_support_m` being part of the cache
    identity.

    With the sentinel's cache warm on disk, a positive-radius request with
    every other parameter identical must return ITS OWN result and write its
    OWN cache file, never be served the sentinel's.
    """
    ws = wel_case_ws / "warm_cache_case"
    ws.mkdir(parents=True, exist_ok=True)
    kwargs = dict(mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                  solubility_mgL=1000.0, case_ws=ws)
    sentinel = tsd.build_srcpulse_demo(sink_support_m=0.0, force=True, **kwargs)
    assert sentinel.sink_support_m == 0.0

    caches_before = sorted(p.name for p in ws.glob("srcpulse_cache_*.npz"))
    assert len(caches_before) == 1

    # force=False: if sink_support_m were NOT in the cache identity, this
    # would hit the sentinel's warm cache and silently return it.
    supported = tsd.build_srcpulse_demo(
        sink_support_m=PARTIAL_RADIUS_M, force=False, **kwargs)

    assert supported.sink_support_m == PARTIAL_RADIUS_M, (
        "the warm SENTINEL cache was served to a supported run -- "
        "sink_support_m is not part of the cache identity")
    assert len(supported.meta["sink_support_cells"]) > 1, (
        "a supported run must distribute the sink across several cells")

    caches_after = sorted(p.name for p in ws.glob("srcpulse_cache_*.npz"))
    assert len(caches_after) == 2, (
        f"the supported run must write its OWN cache file, got {caches_after}")
    assert set(caches_before) < set(caches_after), "the sentinel's cache must survive"


@pytest.mark.slow
def test_warm_supported_cache_is_not_served_to_a_sentinel_run(wel_case_ws):
    """The other direction (exit criterion 6, 'both directions'). Warming the
    SUPPORTED cache first and then asking for the sentinel must return the
    sentinel's own single-cell result -- and the sentinel is gate-visible, so
    a leak here would corrupt the default payload itself."""
    ws = wel_case_ws / "warm_cache_case_reverse"
    ws.mkdir(parents=True, exist_ok=True)
    kwargs = dict(mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                  solubility_mgL=1000.0, case_ws=ws)
    supported = tsd.build_srcpulse_demo(
        sink_support_m=PARTIAL_RADIUS_M, force=True, **kwargs)
    assert supported.sink_support_m == PARTIAL_RADIUS_M

    sentinel = tsd.build_srcpulse_demo(sink_support_m=0.0, force=False, **kwargs)
    assert sentinel.sink_support_m == 0.0
    assert len(sentinel.meta["sink_support_cells"]) == 1, (
        "the warm SUPPORTED cache was served to a sentinel run -- this would "
        "corrupt the gate-visible default payload")


# ---------------------------------------------------------------------------
# 9. every supported cell is active; extc anchors the support
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_every_supported_cell_is_active(base_grid, tmp_path):
    """Exit criterion 11: a distributed disc must never place pumping in an
    inactive cell. (Guaranteed structurally by `_disc_footprint_areas`'s own
    `_footprint_cell_polygons` skipping `idomain <= 0` cells -- this test
    exercises that guarantee end to end through `add_flow_model`.)"""
    grid, _exe = base_grid
    idomain = _idomain(grid)
    gwf = _build_gwf_only(base_grid, tmp_path, sink_support_m=PARTIAL_RADIUS_M)
    for cell, _q in tsd._wel_support_cells(gwf):
        assert idomain[cell] > 0, f"cell {cell} is inactive but carries a WEL rate"


@pytest.mark.slow
@pytest.mark.parametrize("radius", [TINY_RADIUS_M, PARTIAL_RADIUS_M])
def test_extc_is_inside_the_support(base_grid, tmp_path, radius):
    """Exit criterion 13 (brief Sec 2.3.1): `ext_cell` must be a member of
    its own support disc -- otherwise the retained single-cell readout
    wouldn't even be a support-cell observation. `add_flow_model` itself
    raises `ValueError` if this is violated; this test confirms it holds on
    the real mesh at radii it must hold for."""
    grid, _exe = base_grid
    extc = grid["ext_cell"]
    gwf = _build_gwf_only(base_grid, tmp_path, sink_support_m=radius)
    cells = [c for c, _q in tsd._wel_support_cells(gwf)]
    assert extc in cells


# ---------------------------------------------------------------------------
# 10. docstring records the readout caveat + PRT divergence
# ---------------------------------------------------------------------------
def test_docstring_records_the_readout_caveat_and_the_prt_divergence():
    """Exit criterion 16."""
    flow_doc = tsd.add_flow_model.__doc__ or ""
    assert "PRT" in flow_doc
    assert "capture fingerprint" in flow_doc
    assert "ext_cell" in flow_doc
    assert "S9c" in flow_doc

    build_doc = tsd.build_srcpulse_demo.__doc__ or ""
    assert "S9c" in build_doc
    assert "PRT" in build_doc


# ---------------------------------------------------------------------------
# 11. solved: realized WEL flow vs requested (the dry-cell policy)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_realized_wel_flow_matches_requested(supported_run):
    """Exit criterion 12 (the dry-cell policy): don't ASSUME the realized
    WEL flow equals the requested rate -- VERIFY it from the solved GWF
    budget. Policy (documented in `add_flow_model`'s own docstring): the
    flow model is NEWTON (`icelltype=1`, Newton-Raphson smoothing near-dry
    cells), so a supported cell that cannot sustain its requested rate shows
    up as a non-converged run (`ok=False`, already asserted by the
    `supported_run` fixture), not a silently reduced flow. This test
    confirms the PER-CELL realized rate matches the requested one to solver
    tolerance, for every supported cell AND for the untouched injection
    well."""
    grid = supported_run["grid"]
    gwf = supported_run["gwf"]
    injc = grid["inj_cell"]
    requested = dict(tsd._wel_support_cells(gwf))
    realized = _wel_budget_by_cell(gwf)

    assert set(requested) <= set(realized)
    for cell, req_q in requested.items():
        for got_q in realized[cell]:
            assert got_q == pytest.approx(req_q, rel=1e-6), (
                f"cell {cell}: requested {req_q}, realized {got_q}")

    assert injc in realized
    for got_q in realized[injc]:
        assert got_q == pytest.approx(abs(DOUBLET_Q), rel=1e-6)


# ---------------------------------------------------------------------------
# 12. solved: transport mass-balance residual within tolerance
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_solved_transport_mass_balance_residual_within_tolerance(supported_run):
    """Exit criterion 14: WEL mass removal is verified and the GLOBAL
    mass-balance RESIDUAL (not the physical extracted mass, which
    legitimately changes at a positive radius -- see the brief's ⚠️ in Sec
    5) stays within tolerance.

    `_mass_balance`'s own docstring notes the binary GWT budget aggregates
    the SSM boundary+well solute flux under one record (not a separate
    per-package "WEL" line), so `well_out_g` is always 0 here and the
    extraction well's removed mass is folded into `boundary_out_g` --
    asserted non-zero (genuine removal happened), while the RESIDUAL checks
    (`pct_imbalance`, `grouped_residual_g`) are the ones that would catch a
    multi-cell WEL change breaking the budget grouping/accounting."""
    ws = supported_run["ws"]
    mb = tsd._mass_balance(ws / "sim" / "gwt.cbc")

    assert mb["boundary_out_g"] > 0.0  # WEL mass removal actually happened

    assert np.isfinite(mb["pct_imbalance"])
    assert abs(mb["pct_imbalance"]) < 5.0
    assert np.isfinite(mb["grouped_residual_g"])
    assert abs(mb["grouped_residual_g"]) < 1.0


# ---------------------------------------------------------------------------
# 13. several radii: tiny, partially covered, active-domain-edge,
#     and boundary-crossing (which must raise)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_several_radii_tiny_edge_and_boundary_crossing(base_grid, edge_and_crossing_radii,
                                                        tmp_path):
    """Exit criterion 15: not one convenient radius."""
    edge_radius, crossing_radius = edge_and_crossing_radii
    grid, exe = base_grid
    extc = grid["ext_cell"]

    for label, radius in (("tiny", TINY_RADIUS_M), ("partial", PARTIAL_RADIUS_M),
                          ("edge", edge_radius)):
        sub = tmp_path / label
        sim = tsd.new_sim(sub, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                          nstp_per_period=5, exe=exe)
        gwf = tsd.add_flow_model(sim, grid, sink_support_m=radius)
        spd = tsd._wel_support_cells(gwf)
        assert len(spd) >= 1, label
        assert extc in [c for c, _q in spd], label
        total = math.fsum(q for _, q in spd)
        assert total == pytest.approx(Q_EXTRACT, rel=1e-9), label

    sub = tmp_path / "crossing"
    sim = tsd.new_sim(sub, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                      nstp_per_period=5, exe=exe)
    with pytest.raises(ValueError):
        tsd.add_flow_model(sim, grid, sink_support_m=crossing_radius)
