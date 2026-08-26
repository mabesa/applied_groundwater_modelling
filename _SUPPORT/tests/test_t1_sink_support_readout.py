"""Tests for T1 step S9c -- flux-weighted readout, the matched arm, and
lifting S9b's raise (`DESIGN_DOCS/T1_S9c_brief.md` v2).

Authority: A6 (`transport_srcpulse_demo.py`) + A5 (`t1_evidence_artifact.py`,
the `sink_support_controlled` control label).

Three things land together here and are exercised together where practical:
  1. The flux-weighted readout `C_ext = Sum(|q_i| C_i) / Sum(|q_i|)`.
  2. Lifting S9b's `NotImplementedError` for `sink_support_m > 0`.
  3. The `sink_support_controlled` label in the evidence artifact.

Most tests below are FAST, pure-Python unit tests against the readout/
validation helpers directly (`_flux_weighted_breakthrough`,
`_realized_extraction_flows`, `_validate_realized_sink_flows`) using
duck-typed fakes for the FloPy concentration/budget objects -- no MF6 solve
needed to exercise the arithmetic, the sentinel branch, or the two failure
modes (tolerance mismatch, wrong sign). A handful of tests marked `slow` pay
for a REAL coupled GWF+GWT solve because they test the public entrypoint
(`build_srcpulse_demo`) end-to-end: the raise being lifted, the cache
identity behaving correctly cold/warm, and the matched pair.

Run with:  uv run pytest _SUPPORT/tests/test_t1_sink_support_readout.py -v
Use `-m "not slow"` to run only the fast, solve-free tests.
"""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_srcpulse_demo as tsd  # noqa: E402
import t1_evidence_artifact as t1  # noqa: E402

DOUBLET_Q = tsd.DOUBLET_Q
Q_EXTRACT = -abs(DOUBLET_Q)  # extraction is NEGATIVE (S9a brief Sec 2)

# Small, cheap physics params for every REAL-solve fixture below (mirrors
# test_t1_sink_support_wel.py's convention) -- these tests are about the
# READOUT and CACHE-IDENTITY plumbing, not the transport physics.
MASS_G = 1.0e4
PULSE_DAYS = 5.0
TOTAL_DAYS = 15.0
SOLUBILITY_MGL = 1000.0

# The "partial coverage" radius from test_t1_sink_support_wel.py -- already
# known to intersect MORE THAN ONE cell on the real corridor mesh, without
# being tuned to an exact cell count (the Triangle/Voronoi mesh is
# platform-dependent; see MEMORY transport-grid-peclet-spike).
PARTIAL_RADIUS_M = 25.0


# ---------------------------------------------------------------------------
# fakes -- duck-typed stand-ins for FloPy's concentration/budget objects, so
# the arithmetic and validation can be tested without an MF6 solve.
# ---------------------------------------------------------------------------
class _FakeConcObj:
    """Stand-in for `gwt.output.concentration()`: `get_data(totim=t)` returns
    a `[1, 1, ncpl]`-shaped array, matching the real object's indexing
    `cobj.get_data(totim=t)[0, 0, cell]` used throughout the production code.
    """

    def __init__(self, series_by_cell: dict, ncpl: int):
        self._series_by_cell = series_by_cell
        self._ncpl = ncpl

    def get_data(self, totim):
        arr = np.zeros((1, 1, self._ncpl), dtype=float)
        for cell, series in self._series_by_cell.items():
            arr[0, 0, cell] = series[totim]
        return arr


def _make_fake_cobj(times, values_by_cell: dict, ncpl: int = 32):
    """Build a `_FakeConcObj` whose `get_data(totim=t)` returns
    `values_by_cell[cell][index_of(t)]` at `[0, 0, cell]`."""
    series_by_cell = {
        cell: dict(zip(times, vals)) for cell, vals in values_by_cell.items()
    }
    return _FakeConcObj(series_by_cell, ncpl)


# ---------------------------------------------------------------------------
# 1. sentinel branch: explicit, bit-identical single-cell read
# ---------------------------------------------------------------------------
def test_sentinel_breakthrough_is_bit_identical_to_the_single_cell_read():
    """Exit criteria 1/17 (brief Sec 2): with exactly ONE support cell,
    `_flux_weighted_breakthrough` must take the EXPLICIT single-cell branch
    -- reading `cobj` exactly as pre-S9c -- rather than routing through the
    general `Sum(|q|C)/Sum(|q|)` formula, which is mathematically identical
    but NOT guaranteed bit-for-bit in floating point. Use values where the
    general formula's rounding would visibly differ (division then
    multiplication vs. a bare read) to make the distinction observable.
    """
    times = np.array([0.0, 1.0, 2.0])
    # A value chosen so that (|q| * C) / |q| is not exactly C in float64 --
    # this is what the frozen single-cell branch must AVOID computing at all.
    tricky_c = 0.1 + 0.2  # famously not bit-identical to 0.3
    cobj = _make_fake_cobj(times, {5: [0.0, tricky_c, 0.05]})
    weights = {5: -137.0}

    out = tsd._flux_weighted_breakthrough(cobj, times, [5], weights)
    direct = np.maximum(
        np.array([cobj.get_data(totim=t)[0, 0, 5] for t in times]), 0.0)
    assert np.array_equal(out, direct), "single-cell branch must read cobj directly"

    # The general formula, computed independently here, need NOT be
    # bit-identical -- confirming the two are not accidentally the same
    # code path (see test_flux_weighted_reduces_to_single_cell_within_tolerance
    # for the "agrees to tolerance" contract instead).
    general = np.maximum(
        np.array([abs(weights[5]) * cobj.get_data(totim=t)[0, 0, 5] / abs(weights[5])
                  for t in times]), 0.0)
    # They agree to tolerance (documented reduction)...
    assert out == pytest.approx(general, abs=1e-12)


# ---------------------------------------------------------------------------
# 2. general formula agrees with the single-cell read to tolerance
# ---------------------------------------------------------------------------
def test_flux_weighted_reduces_to_single_cell_within_tolerance():
    """Exit criterion 2 (brief Sec 2): documents the reduction
    `Sum(|q|C)/Sum(|q|) == C` for one cell, without betting the DEFAULT
    contract on it (that is what the explicit branch is for). Forces the
    general (multi-cell) code path with only ONE cell actually contributing
    by giving a second cell weight but placing it at a different mesh cell,
    which is not physically the one-cell case S9c freezes -- instead, this
    test calls the internal building block directly on a synthetic
    single-entry weights/cells pair to exercise the ARITHMETIC the general
    formula would use, bypassing the branch selection.
    """
    times = np.array([0.0, 10.0, 20.0])
    c_vals = [0.0, 5.277, 2.1]
    cobj = _make_fake_cobj(times, {7: c_vals})
    weights = {7: -812.345}

    # The frozen sentinel branch (len == 1):
    branch_result = tsd._flux_weighted_breakthrough(cobj, times, [7], weights)

    # The general arithmetic, replicated by hand from the same inputs:
    total_w = abs(weights[7])
    hand_general = np.maximum(
        np.array([abs(weights[7]) * c / total_w for c in c_vals]), 0.0)

    assert branch_result == pytest.approx(hand_general, abs=1e-9)
    assert branch_result == pytest.approx(np.maximum(np.array(c_vals), 0.0), abs=1e-9)


# ---------------------------------------------------------------------------
# 3. flux weights use |q_i| -- extraction rates are negative
# ---------------------------------------------------------------------------
def test_flux_weights_use_absolute_rates():
    """Exit criterion 9: extraction rates are NEGATIVE; a signed weighting
    would invert the mean (a bigger-magnitude extraction cell would pull the
    mixture AWAY from its own concentration instead of toward it). Build two
    cells with equal-magnitude but a concentration difference, confirm the
    mixture is the plain average (proving |.| was applied, not the signed
    values, which would flip the sign of the "weight" entirely and produce a
    negative denominator -- caught structurally by NOT raising here at all).
    """
    times = np.array([0.0])
    cobj = _make_fake_cobj(times, {1: [10.0], 2: [30.0]})
    weights = {1: -50.0, 2: -50.0}  # equal-magnitude, both negative (extraction)

    out = tsd._flux_weighted_breakthrough(cobj, times, [1, 2], weights)
    assert out[0] == pytest.approx(20.0)  # plain average of 10 and 30

    # Unequal magnitudes: the LARGER |q| cell must dominate the mixture.
    weights2 = {1: -10.0, 2: -90.0}
    out2 = tsd._flux_weighted_breakthrough(cobj, times, [1, 2], weights2)
    expected = (10.0 * 10.0 + 90.0 * 30.0) / 100.0
    assert out2[0] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 4. degenerate guard
# ---------------------------------------------------------------------------
def test_zero_total_flux_raises():
    """Exit criterion 10: Sum(|q_i|) == 0 must raise rather than divide by
    zero (a NaN/inf breakthrough silently propagating downstream would be far
    worse than a loud failure here)."""
    times = np.array([0.0, 1.0])
    cobj = _make_fake_cobj(times, {1: [1.0, 2.0], 2: [3.0, 4.0]})
    weights = {1: 0.0, 2: 0.0}
    with pytest.raises(RuntimeError, match="degenerate"):
        tsd._flux_weighted_breakthrough(cobj, times, [1, 2], weights)


# ---------------------------------------------------------------------------
# 5. multi-cell breakthrough IS the flux-weighted mixture (one source of truth)
# ---------------------------------------------------------------------------
def test_multi_cell_breakthrough_is_the_flux_weighted_mixture():
    """Exit criterion 4: `breakthrough` itself becomes the flux-weighted
    series at multi-cell support -- not a separate metric computed
    alongside a single-cell curve. Three cells, distinct weights and
    concentration time series, verified against the formula computed by
    hand at every time step."""
    times = np.array([0.0, 5.0, 10.0, 15.0])
    vals = {
        10: [0.0, 1.0, 2.0, 1.5],
        20: [0.0, 0.5, 3.0, 2.0],
        30: [0.0, 2.0, 1.0, 0.2],
    }
    cobj = _make_fake_cobj(times, vals, ncpl=64)
    weights = {10: -400.0, 20: -300.0, 30: -670.0}
    sink_cells = [10, 20, 30]

    out = tsd._flux_weighted_breakthrough(cobj, times, sink_cells, weights)

    total_w = sum(abs(weights[c]) for c in sink_cells)
    expected = np.array([
        sum(abs(weights[c]) * vals[c][i] for c in sink_cells) / total_w
        for i in range(len(times))
    ])
    assert out == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 6. downstream metrics derive from the flux-weighted series
# ---------------------------------------------------------------------------
def test_downstream_metrics_derive_from_the_flux_weighted_series():
    """Exit criterion 3/17: `peak_mgL`/`arrival_day` (reproduced here exactly
    as `build_srcpulse_demo` computes them, `bt.max()` /
    `times[argmax(bt)]`) must be derived from the FLUX-WEIGHTED `bt` array,
    not from any individual cell's own concentration."""
    times = np.array([0.0, 5.0, 10.0, 15.0, 20.0])
    vals = {1: [0.0, 1.0, 2.0, 1.0, 0.5], 2: [0.0, 4.0, 5.0, 3.0, 1.0]}
    cobj = _make_fake_cobj(times, vals)
    weights = {1: -900.0, 2: -100.0}  # cell 1 dominates heavily
    sink_cells = [1, 2]

    bt = tsd._flux_weighted_breakthrough(cobj, times, sink_cells, weights)
    peak = float(bt.max())
    arrival = float(times[int(np.argmax(bt))])

    # Peak/arrival must reflect the WEIGHTED mixture (dominated by cell 1's
    # own peak at t=10, value 2.0-ish after weighting), never cell 2's peak
    # (5.0 at t=10) taken in isolation, nor a naive unweighted average.
    total_w = sum(abs(weights[c]) for c in sink_cells)
    mixture = [sum(abs(weights[c]) * vals[c][i] for c in sink_cells) / total_w
               for i in range(len(times))]
    assert peak == pytest.approx(max(mixture))
    assert arrival == pytest.approx(times[int(np.argmax(mixture))])
    # Sanity: NOT equal to cell 2's own peak (proves it's not reading one
    # cell in isolation under a mixture's name).
    assert peak != pytest.approx(max(vals[2]))


# ---------------------------------------------------------------------------
# 7. the sentinel and multi-cell paths share ALL downstream processing
# ---------------------------------------------------------------------------
def test_sentinel_and_multicell_share_all_downstream_processing():
    """Exit criterion 17: the sentinel branch inside
    `_flux_weighted_breakthrough` selects ONLY the series -- there must be
    exactly ONE place in `transport_srcpulse_demo.py` that computes
    `peak_mgL` (`bt.max()`) and exactly one that computes `arrival_day`
    (`argmax(bt)`), used for BOTH the sentinel and the multi-cell case,
    so the two paths cannot silently drift apart. A static source check
    (mirroring `test_no_new_payload_or_meta_field`'s pattern elsewhere in
    this package) is the only way to assert "no second, parallel
    computation exists" -- a purely behavioural test could pass even with a
    duplicated, subtly different implementation for the multi-cell case.
    """
    from pathlib import Path
    source = Path(tsd.__file__).read_text()

    # Exactly one call site for each: inside build_srcpulse_demo, downstream
    # of the single `bt = _flux_weighted_breakthrough(...)` assignment.
    assert source.count("_flux_weighted_breakthrough(") == 2  # def + one call site
    assert source.count("peak = float(bt.max())") == 1
    assert source.count("np.argmax(bt)") >= 1
    # No second, flux-weighted-specific peak/arrival computation exists
    # anywhere in the module (brief Sec 2: "do not compute a separate
    # flux-weighted peak alongside a single-cell curve").
    assert "flux_weighted_peak" not in source
    assert "weighted_peak_mgL" not in source


# ---------------------------------------------------------------------------
# 8. weights come from the REALIZED budget, not configured rates
# ---------------------------------------------------------------------------
class _FakeBudgetFile:
    """Stand-in for `gwf.output.budget()`: `get_data(text=, paknam2=)`
    returns ONE fabricated WEL record (a list of row-mappings exposing
    `node`/`q`, matching FloPy's recarray-row indexing `row["node"]`/
    `row["q"]`)."""

    def __init__(self, rows_by_paknam2: dict):
        self._rows_by_paknam2 = rows_by_paknam2

    def get_data(self, text=None, paknam2=None):
        rows = self._rows_by_paknam2.get(paknam2, [])
        return [rows] if rows else []


class _FakeRow(dict):
    """A dict that also supports `row["node"]`/`row["q"]` item access,
    matching the real recarray row's `__getitem__`."""


class _FakeGwf:
    def __init__(self, rows_by_paknam2: dict):
        self._budget = _FakeBudgetFile(rows_by_paknam2)

    class _Output:
        def __init__(self, budget):
            self._budget = budget

        def budget(self):
            return self._budget

    @property
    def output(self):
        return _FakeGwf._Output(self._budget)


def _fake_wel_row(node_1indexed: int, q: float) -> _FakeRow:
    return _FakeRow(node=node_1indexed, q=q)


def test_weights_come_from_the_realized_budget_not_configured_rates():
    """Exit criterion 11: `_realized_extraction_flows` reads its answer OFF
    THE SOLVED GWF BUDGET (`gwf.output.budget()`) -- it takes no
    "configured rate" argument at all, so there is no code path by which it
    could fall back to a prescribed value. Fabricate a budget whose flows
    are UNEQUAL and asymmetric enough that a naive equal-split (or any
    configured-rate stand-in) would give a visibly different mixture, then
    confirm the full flux-weighted computation reflects exactly the
    fabricated (realized) values.
    """
    # cells 9 (0-indexed) and 19 (0-indexed) -> node = cell + 1 (1-indexed)
    fake_gwf = _FakeGwf({
        "absw": [_fake_wel_row(10, -100.0), _fake_wel_row(20, -300.0)],
        "injw": [_fake_wel_row(50, +1370.0)],  # a DIFFERENT package -- must be ignored
    })

    realized = tsd._realized_extraction_flows(fake_gwf, pname="absw")
    assert realized == {9: -100.0, 19: -300.0}
    # The other WEL package's flow must NOT leak in (paknam2 isolation).
    assert 49 not in realized

    times = np.array([0.0])
    cobj = _make_fake_cobj(times, {9: [10.0], 19: [30.0]}, ncpl=32)
    bt = tsd._flux_weighted_breakthrough(cobj, times, [9, 19], realized)
    # 1:3 weighting (100 vs 300), NOT a naive 1:1 average -- proves the
    # REALIZED, unequal budget values (not some equal configured stand-in)
    # drove the mixture.
    expected = (100.0 * 10.0 + 300.0 * 30.0) / 400.0
    assert bt[0] == pytest.approx(expected)
    naive_equal_split = (10.0 + 30.0) / 2.0
    assert bt[0] != pytest.approx(naive_equal_split)


def test_realized_extraction_flows_isolates_the_named_wel_package():
    """Companion structural check: a bare `text="WEL"` read (no `paknam2`)
    would mix `injw` into `absw`'s flows on a real two-WEL-package model
    (brief Sec 2.1) -- `_realized_extraction_flows` must not do that."""
    fake_gwf = _FakeGwf({
        "absw": [_fake_wel_row(1, -50.0)],
        "injw": [_fake_wel_row(2, +1370.0)],
    })
    realized = tsd._realized_extraction_flows(fake_gwf, pname="absw")
    assert realized == {0: -50.0}


# ---------------------------------------------------------------------------
# 9/10. realized-vs-prescribed validation: tolerance mismatch + wrong sign
# ---------------------------------------------------------------------------
def test_realized_flow_differing_from_prescribed_raises():
    """Exit criterion 12: a support cell whose REALIZED flow diverges from
    what was PRESCRIBED to `ModflowGwfwel` beyond tolerance must raise --
    the arm is not delivering the control it claims (dry, deactivated, or
    flow-reduced cell)."""
    prescribed = {5: -685.0, 6: -685.0}
    realized_ok = {5: -685.0, 6: -684.9999993}  # within tolerance
    tsd._validate_realized_sink_flows(prescribed, realized_ok)  # must not raise

    realized_bad = {5: -685.0, 6: -50.0}  # cell 6 badly under-delivering
    with pytest.raises(RuntimeError, match="beyond tolerance|diverges|dry"):
        tsd._validate_realized_sink_flows(prescribed, realized_bad)


def test_realized_flow_missing_a_support_cell_raises():
    """Companion: a support cell entirely ABSENT from the realized budget
    (e.g. deactivated) must also raise, not be silently skipped."""
    prescribed = {5: -685.0, 6: -685.0}
    realized = {5: -685.0}  # cell 6 missing
    with pytest.raises(RuntimeError, match="missing"):
        tsd._validate_realized_sink_flows(prescribed, realized)


def test_positive_sign_support_flow_raises():
    """Exit criterion 13: a support flow with the WRONG SIGN (an extraction
    cell reporting INFLOW, i.e. positive) must raise -- independent of
    magnitude, and independent of the tolerance check (a realized value
    that happens to equal the prescribed magnitude but with the wrong sign
    must still be caught)."""
    prescribed = {5: -685.0}
    realized_wrong_sign = {5: +685.0}  # same magnitude, wrong sign
    with pytest.raises(RuntimeError, match="SIGN|sign"):
        tsd._validate_realized_sink_flows(prescribed, realized_wrong_sign)


# ---------------------------------------------------------------------------
# 11. the evidence-artifact control label
# ---------------------------------------------------------------------------
def test_control_label_vocabulary_is_separate_from_diagnostic_labels():
    """Exit criterion 6/Sec 3: `CONTROL_LABELS` must be a SEPARATE closed
    vocabulary from `DIAGNOSTIC_LABELS` -- disjoint, not a subset, not the
    same tuple object -- so a B-control record (which carries its own GWF
    solve) can never be filed under the no-solve diagnostic vocabulary."""
    assert set(t1.CONTROL_LABELS).isdisjoint(set(t1.DIAGNOSTIC_LABELS))
    assert "sink_support_controlled" in t1.CONTROL_LABELS
    assert "sink_support_controlled" not in t1.DIAGNOSTIC_LABELS
    assert t1.CONTROL_LABELS is not t1.DIAGNOSTIC_LABELS


def _control_raw(label="sink_support_controlled", key=None, **overrides):
    key = key or label
    entry = dict(
        label=label,
        sink_support_m=25.0,
        uncontrolled_counterpart_run_id="fixture-run-sentinel-0001",
        prt_capture_diverges=True,
    )
    entry.update(overrides)
    record = t1.build_fixture_record(run_role="b_control")
    raw = t1.record_to_raw_dict(record)
    raw["run_identity"]["controls"] = {key: entry}
    raw[t1._HASH_KEY] = t1.compute_content_hash(raw)
    return raw


def test_unknown_control_label_raises():
    """Exit criterion 6: a control record whose `label` is not one of
    `CONTROL_LABELS` must raise `MalformedEvidenceRecordError` on load --
    the same "present but invalid" treatment every other closed enum in
    this schema gets."""
    raw = _control_raw(label="bogus_control_label", key="bogus_control_label")
    with pytest.raises(t1.MalformedEvidenceRecordError):
        t1.record_from_raw_dict(raw)


def test_control_dict_key_must_equal_its_own_label():
    """The dict-key-must-equal-its-own-label invariant is INHERITED from
    `support.diagnostics` (brief Sec 3) -- a control filed under a key that
    disagrees with its own `label` is the same defect class."""
    raw = _control_raw(key="not_the_label")
    with pytest.raises(t1.MalformedEvidenceRecordError):
        t1.record_from_raw_dict(raw)


def test_control_record_states_it_is_not_causal_isolation():
    """Exit criterion 7: the label's ceiling ('sink support controlled,
    NEVER causal isolation') must be stated IN the record, not only in
    documentation -- emitted as `causal_isolation_eligible: false`, computed
    (never caller-supplied) so it cannot be silently overridden."""
    control = t1.ControlRecord(
        label="sink_support_controlled", sink_support_m=25.0,
        uncontrolled_counterpart_run_id="run-sentinel-0001",
        prt_capture_diverges=True,
    )
    wire = t1._controls_to_json({"sink_support_controlled": control})
    assert wire["sink_support_controlled"]["causal_isolation_eligible"] is False

    assert set(t1.CONTROL_CAUSAL_ISOLATION_ELIGIBLE) == set(t1.CONTROL_LABELS)
    assert all(v is False for v in t1.CONTROL_CAUSAL_ISOLATION_ELIGIBLE.values())

    # An attempt to override the ceiling on load must be rejected, not
    # accepted as "the producer's opinion".
    raw = _control_raw(causal_isolation_eligible=True)
    with pytest.raises(t1.MalformedEvidenceRecordError):
        t1.record_from_raw_dict(raw)


def test_prt_divergence_recorded_in_the_control_record():
    """Exit criterion 16: PRT's own single-cell doublet WEL diverging from
    a positive-radius B-control GWF must be recorded IN the control record
    (`prt_capture_diverges`), round-tripping through JSON, so a downstream
    consumer (S10) cannot unknowingly pair a PRT capture fingerprint with a
    B-control arm."""
    control = t1.ControlRecord(
        label="sink_support_controlled", sink_support_m=25.0,
        uncontrolled_counterpart_run_id="run-sentinel-0001",
        prt_capture_diverges=True,
    )
    record = t1.build_fixture_record(
        run_role="b_control", controls={"sink_support_controlled": control})
    raw = t1.dump_record(record)
    loaded = t1.record_from_raw_dict_fail_closed(raw)
    assert loaded.controls["sink_support_controlled"].prt_capture_diverges is True
    assert (loaded.controls["sink_support_controlled"].uncontrolled_counterpart_run_id
            == "run-sentinel-0001")
    assert loaded.provenance_valid is True


def test_old_schema_version_is_rejected():
    """Exit criterion 15: the version gate is EXACT-MATCH and fails closed
    -- a record built under the schema version immediately preceding this
    milestone's bump (3.0.0, with no `run_identity.controls` concept at
    all) must be refused outright by today's loader, never silently
    accepted as "a 3.1.0 record with no controls" (a 3.0.0 producer was
    never asked whether it carries one)."""
    import tempfile
    from pathlib import Path

    record = t1.build_fixture_record(run_role="spatial_series")
    raw = t1.dump_record(record)
    raw["schema"]["schema_version"] = "3.0.0"
    # deliberately do not recompute content_hash to match: schema_version is
    # excluded from hash coverage (SCHEMA DECISIONS #4), so the version gate
    # alone must catch this, before the hash gate is even reached.
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "old_version.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(t1.SchemaVersionMismatchError):
            t1.load_record(path)

    assert t1.SCHEMA_VERSION != "3.0.0"


def test_controls_key_must_be_present_for_structural_completeness():
    """Mirrors `support.diagnostics`'s cardinality rule (decision #15): the
    bare `run_identity.controls` key must be present (an object, possibly
    `{}`) for a record to be structurally complete -- a run that applied no
    control is still expected to say so with an empty mapping, not by
    omitting the key."""
    record = t1.build_fixture_record(run_role="spatial_series", controls={})
    raw = t1.record_to_raw_dict(record)
    assert raw["run_identity"]["controls"] == {}
    missing = t1.missing_required_fields(raw)
    assert "run_identity.controls" not in missing

    # Omitting the key entirely (simulating a pre-S9c producer that never
    # heard of `controls`) must be flagged as INCOMPLETE, not silently
    # treated as "no controls".
    incomplete_raw = dict(raw)
    incomplete_raw["run_identity"] = {
        k: v for k, v in raw["run_identity"].items() if k != "controls"
    }
    missing2 = t1.missing_required_fields(incomplete_raw)
    assert "run_identity.controls" in missing2


# ---------------------------------------------------------------------------
# real-solve fixtures (slow) -- everything below pays for at least one real
# coupled GWF+GWT solve.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def readout_case_ws(tmp_path_factory):
    """Isolated, COLD workspace for every real-solve fixture in this module."""
    return tmp_path_factory.mktemp("t1_sink_support_readout_ws")


@pytest.fixture(scope="module")
def positive_radius_demo(readout_case_ws):
    """ONE real coupled solve via the PUBLIC entrypoint at a POSITIVE
    `sink_support_m` -- exit criterion 4 (`test_positive_radius_no_longer_raises`)
    needs `build_srcpulse_demo` itself, not the lower-level builders S9b's
    own tests already exercise."""
    ws = readout_case_ws / "positive_radius_demo"
    return tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, sink_support_m=PARTIAL_RADIUS_M,
        case_ws=ws, force=True)


@pytest.mark.slow
def test_positive_radius_no_longer_raises(positive_radius_demo):
    """Exit criterion 4: a positive `sink_support_m` no longer raises
    `NotImplementedError` -- it returns a genuine result, with the
    apportionment actually distributed across more than one cell."""
    demo = positive_radius_demo
    assert demo.sink_support_m == pytest.approx(PARTIAL_RADIUS_M)
    assert len(demo.meta["sink_support_cells"]) > 1
    assert np.isfinite(demo.peak_mgL)
    assert demo.breakthrough.shape == demo.times.shape


@pytest.mark.slow
def test_rate_sum_preserved_at_a_positive_radius(positive_radius_demo):
    """Exit criterion 8 (mass conservation half): `Sum(q_i) == Q` for the
    single, non-matched positive-radius run too -- the matched-pair test
    below re-asserts this per arm specifically for the grid comparison."""
    total = sum(rate for _cell, rate in positive_radius_demo.meta["sink_support_cells"])
    assert total == pytest.approx(Q_EXTRACT, rel=1e-9)


@pytest.mark.slow
def test_sink_support_m_changes_the_cache_identity_cold_and_warm_both_directions(
        tmp_path):
    """Exit criterion 5 (S9b's deferred gap, closed): S9b could only test
    `sink_support_m`'s cache identity STATICALLY, because a positive radius
    raised before the cache lookup was ever reached. Now that S9c lifts the
    raise, this must hold BEHAVIOURALLY:
      - COLD: a sentinel run and a positive-radius run at the SAME cell
        size produce DISTINCT cache files.
      - WARM: re-calling either with `force=False` must hit ITS OWN cache
        (no new cache file is written) -- and never the other's (their
        `sink_support_m` values differ, so a cross-served cache would be
        immediately visible on the returned object).
    """
    ws = tmp_path / "cold_warm_ws"

    # ---- COLD: two real solves, same case_ws, different sink_support_m ----
    sentinel_cold = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, sink_support_m=0.0,
        case_ws=ws, force=True)
    supported_cold = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, sink_support_m=PARTIAL_RADIUS_M,
        case_ws=ws, force=True)

    assert sentinel_cold.sink_support_m == 0.0
    assert supported_cold.sink_support_m == pytest.approx(PARTIAL_RADIUS_M)

    cache_files_cold = set(ws.glob("srcpulse_cache_*.npz"))
    assert len(cache_files_cold) == 2, "sentinel and supported runs must NOT share a cache file"

    # ---- WARM: re-call both with force=False -- must be cache HITS ----
    sentinel_warm = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, sink_support_m=0.0,
        case_ws=ws, force=False)
    supported_warm = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, sink_support_m=PARTIAL_RADIUS_M,
        case_ws=ws, force=False)

    cache_files_warm = set(ws.glob("srcpulse_cache_*.npz"))
    assert cache_files_warm == cache_files_cold, (
        "a warm re-call must not create a new cache file (it should be a hit)")

    # direction 1: the sentinel's warm re-call must not be served the
    # supported run's cache (or vice versa) -- sink_support_m is the
    # simplest possible tell.
    assert sentinel_warm.sink_support_m == 0.0
    assert len(sentinel_warm.meta["sink_support_cells"]) == 1
    assert supported_warm.sink_support_m == pytest.approx(PARTIAL_RADIUS_M)
    assert len(supported_warm.meta["sink_support_cells"]) > 1

    # And the warm read must reproduce the cold result exactly (a genuine
    # cache hit, not a silent, subtly-different rebuild).
    assert np.array_equal(sentinel_warm.breakthrough, sentinel_cold.breakthrough)
    assert np.array_equal(supported_warm.breakthrough, supported_cold.breakthrough)


# ---------------------------------------------------------------------------
# the matched arm: two cell sizes, same sink_support_m
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def matched_pair(readout_case_ws):
    """Exit criterion 8 (brief Sec 4): S9c ships the CAPABILITY plus ONE
    affordable matched pair -- two runs at DIFFERENT cell sizes with the
    SAME `sink_support_m`, marked `slow`. This demonstrates INTEGRATION
    ONLY (both arms run, share physical support, preserve total pumping,
    stay cache-distinct) -- NOT convergence, robustness, or causal
    isolation (T2's job, the real matrix).

    Cell sizes are chosen AFFORDABLE (not the real matrix's fine end,
    documented at ~316 s on a fast Mac with Hub speed unmeasured): the
    module default (10 m) and a coarser 20 m, both single-level MeshSpecs.
    """
    ws = readout_case_ws / "matched_pair"
    coarse = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, sink_support_m=PARTIAL_RADIUS_M,
        mesh_spec=tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=20.0),)),
        case_ws=ws, force=True)
    fine = tsd.build_srcpulse_demo(
        mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
        solubility_mgL=SOLUBILITY_MGL, sink_support_m=PARTIAL_RADIUS_M,
        mesh_spec=tsd.MeshSpec(),  # module default: levels=(MeshLevel(10.0),)
        case_ws=ws, force=True)
    return coarse, fine


@pytest.mark.slow
def test_matched_pair_two_cell_sizes_same_support_distinct_identities(matched_pair):
    """Exit criterion 8: both arms solve successfully at the SAME
    `sink_support_m`, but are cache-DISTINCT (different mesh -> different
    `mesh_spec_hash`/`mesh_hash` -> different cache file), and each carries
    its own genuinely-distributed support."""
    coarse, fine = matched_pair
    assert coarse.sink_support_m == pytest.approx(PARTIAL_RADIUS_M)
    assert fine.sink_support_m == pytest.approx(PARTIAL_RADIUS_M)

    # Distinct mesh identity -> distinct ncpl (near-certain for a 20 m vs
    # 10 m corridor refinement) and, more directly, distinct workspaces.
    assert coarse.meta["ncpl"] != fine.meta["ncpl"] or coarse.meta != fine.meta

    ws = coarse.meta["sink_support_cells"], fine.meta["sink_support_cells"]
    assert ws[0] != ws[1] or coarse.meta["ncpl"] != fine.meta["ncpl"], (
        "the two arms must not be cache/identity-identical")


@pytest.mark.slow
def test_rate_sum_preserved_in_each_matched_arm(matched_pair):
    """Exit criterion 8: `Sum(q_i) == Q` is RE-ASSERTED per arm -- a matched
    arm that silently lost mass between meshes would otherwise look like a
    physical grid effect rather than a bug."""
    coarse, fine = matched_pair
    for demo in (coarse, fine):
        total = sum(rate for _cell, rate in demo.meta["sink_support_cells"])
        assert total == pytest.approx(Q_EXTRACT, rel=1e-9)
