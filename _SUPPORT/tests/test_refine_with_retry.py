"""
Acceptance tests for milestone M2-refine-retry.

Promote the transport-only ``_refine_with_retry`` (radius-walk mitigation for the
cs=10 SIGILL / Triangle-precision aborts) into a PUBLIC helper
``model_io_utils.refine_with_retry`` so the flow path can reuse it, and re-export
it from ``transport_base_model`` so ``build_spill_scenario`` / ``build_doublet_base``
call the SAME logic unchanged.

LOCKED-TEST SCOPING (do not weaken): these tests NEVER run MODFLOW or a real
Triangle/Voronoi refinement.  ``model_io_utils.build_refined_gwf_model`` is
monkeypatched with fakes that either raise or return a sentinel dict, so the only
thing exercised is the retry / subworkspace / return / raise control flow.

Run with:  uv run pytest _SUPPORT/tests/test_refine_with_retry.py -v
"""
from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest

# Add src to path for imports (same pattern as the other tests in this dir).
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import model_io_utils as mio  # noqa: E402
import transport_base_model as tbm  # noqa: E402


# ---------------------------------------------------------------------------
# Fake build_refined_gwf_model
# ---------------------------------------------------------------------------
# Mirrors the REAL build_refined_gwf_model signature so calls bind whether the
# caller passes args positionally or by keyword.  ``behavior(call_index,
# refine_radius)`` decides the outcome per radius: return an Exception INSTANCE
# to have the fake raise it, or any other object to have the fake return it.
def _make_fake(behavior):
    calls = []

    def fake(gwf, boundary_gdf=None, river_gdf=None, refine_points=None,
             head_array=None, workspace=None, refine_radius=200.0,
             base_cell_size=50.0, refined_cell_size=10.0, well_data=None,
             sim_name="refined_model", baseline_head_array=None):
        calls.append(dict(
            gwf=gwf, boundary_gdf=boundary_gdf, river_gdf=river_gdf,
            refine_points=refine_points, head_array=head_array,
            workspace=workspace, refine_radius=refine_radius,
            base_cell_size=base_cell_size, refined_cell_size=refined_cell_size,
            sim_name=sim_name,
        ))
        outcome = behavior(len(calls) - 1, refine_radius)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    fake.calls = calls
    return fake


# Opaque sentinels — the helper must forward these through untouched, so the
# tests do not depend on any real model object.
COARSE = object()
BOUNDARY = object()
RIVER = object()
POINTS = [(0.0, 0.0), (100.0, 0.0)]
HEADS = object()

DEFAULT_RADII = (70.0, 62.0, 78.0, 56.0, 84.0)


def _basenames(fake):
    return [os.path.basename(str(c["workspace"])) for c in fake.calls]


# ===========================================================================
# Criterion 1 — model_io_utils.refine_with_retry is a PUBLIC helper with the
# specified signature and radius-walk behavior.
# ===========================================================================
def test_refine_with_retry_is_public():
    assert hasattr(mio, "refine_with_retry"), (
        "model_io_utils must define a PUBLIC refine_with_retry helper"
    )
    fn = mio.refine_with_retry
    assert callable(fn)
    assert not fn.__name__.startswith("_"), "helper must be public (no leading _)"


def test_refine_with_retry_signature_and_defaults():
    sig = inspect.signature(mio.refine_with_retry)
    params = sig.parameters

    # Six leading (positional) inputs, in order.
    leading = ["coarse_gwf", "boundary_gdf", "river_gdf",
               "refine_points", "head_array", "workspace"]
    assert list(params)[:6] == leading

    # The tuning knobs are KEYWORD-ONLY (the `*` in the spec) with locked defaults.
    for name, expected in [
        ("refine_radii", DEFAULT_RADII),
        ("base_cell_size", 50.0),
        ("refined_cell_size", 10.0),
        ("sim_name", "rg"),
    ]:
        assert name in params, f"missing keyword-only parameter {name!r}"
        p = params[name]
        assert p.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{name} must be keyword-only"
        )
    # exact default values
    assert tuple(params["refine_radii"].default) == DEFAULT_RADII
    assert params["base_cell_size"].default == 50.0
    assert params["refined_cell_size"].default == 10.0
    assert params["sim_name"].default == "rg"


def test_first_radius_success_returns_dict_and_radius(monkeypatch):
    sentinel = {"gwf": "SENTINEL"}
    fake = _make_fake(lambda i, rr: sentinel)  # always succeeds
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    res, radius = mio.refine_with_retry(
        COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws")

    # Returns (result_dict, radius_used) with the FIRST radius, first try only.
    assert res is sentinel
    assert radius == 70.0
    assert len(fake.calls) == 1
    assert fake.calls[0]["refine_radius"] == 70.0
    # per-radius subworkspace workspace/rg<k>
    assert _basenames(fake) == ["rg0"]


def test_forwards_all_inputs_to_build(monkeypatch):
    sentinel = object()
    fake = _make_fake(lambda i, rr: sentinel)
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    mio.refine_with_retry(
        COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws",
        base_cell_size=33.0, refined_cell_size=7.0, sim_name="zz")

    c = fake.calls[0]
    assert c["gwf"] is COARSE
    assert c["boundary_gdf"] is BOUNDARY
    assert c["river_gdf"] is RIVER
    assert c["refine_points"] is POINTS
    assert c["head_array"] is HEADS
    assert c["base_cell_size"] == 33.0
    assert c["refined_cell_size"] == 7.0
    assert c["sim_name"] == "zz"


def test_walks_radii_in_order_until_first_success(monkeypatch):
    sentinel = object()

    # Fail on the first two radii, succeed on the third (78.0).
    def behavior(i, rr):
        if i < 2:
            return RuntimeError(f"SIGILL at radius {rr}")
        return sentinel

    fake = _make_fake(behavior)
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    res, radius = mio.refine_with_retry(
        COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws")

    assert res is sentinel
    assert radius == 78.0
    # exactly three attempts, in default order, no attempt past the first success
    assert [c["refine_radius"] for c in fake.calls] == [70.0, 62.0, 78.0]
    assert _basenames(fake) == ["rg0", "rg1", "rg2"]


def test_custom_refine_radii_honored(monkeypatch):
    sentinel = object()

    def behavior(i, rr):
        return sentinel if rr == 22.0 else RuntimeError("nope")

    fake = _make_fake(behavior)
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    res, radius = mio.refine_with_retry(
        COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws",
        refine_radii=(11.0, 22.0, 33.0))

    assert res is sentinel
    assert radius == 22.0
    assert [c["refine_radius"] for c in fake.calls] == [11.0, 22.0]
    assert _basenames(fake) == ["rg0", "rg1"]


def test_all_radii_fail_raises_runtimeerror_naming_radii_and_last_error(monkeypatch):
    def behavior(i, rr):
        # distinct messages; the LAST one must surface in the RuntimeError.
        return ValueError("boom-last" if rr == 33.0 else f"boom-{rr}")

    fake = _make_fake(behavior)
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    with pytest.raises(RuntimeError) as exc:
        mio.refine_with_retry(
            COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws",
            refine_radii=(11.0, 22.0, 33.0))

    msg = str(exc.value)
    # names every tried radius ...
    for rr in ("11.0", "22.0", "33.0"):
        assert rr in msg, f"RuntimeError message must name tried radius {rr}"
    # ... and the last underlying error.
    assert "boom-last" in msg
    # every radius was attempted
    assert [c["refine_radius"] for c in fake.calls] == [11.0, 22.0, 33.0]


def test_underlying_exception_not_leaked_on_total_failure(monkeypatch):
    # A single-radius total failure must still raise RuntimeError, not the
    # raw KeyError from build_refined_gwf_model.
    fake = _make_fake(lambda i, rr: KeyError("raw"))
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    with pytest.raises(RuntimeError):
        mio.refine_with_retry(
            COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws",
            refine_radii=(70.0,))


# ===========================================================================
# FIX E regression: each failed radius is LOGGED (exception type + message)
# so a deterministic bug in caller code isn't silently folded into "the
# radius walk failed" -- distinguishable from a real SIGILL/Triangle abort.
# ===========================================================================
def test_each_failed_radius_is_logged_with_exception_type_and_message(
    monkeypatch, caplog
):
    def behavior(i, rr):
        if i < 2:
            return TypeError(f"deterministic bug at radius {rr}")
        return {"gwf": "SENTINEL"}

    fake = _make_fake(behavior)
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    with caplog.at_level("WARNING", logger="model_io_utils"):
        res, radius = mio.refine_with_retry(
            COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws")

    assert radius == 78.0
    warnings_ = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings_) == 2, (
        f"expected one WARNING per failed radius, got {len(warnings_)}: "
        f"{[r.getMessage() for r in caplog.records]}"
    )
    for record, rr in zip(warnings_, (70.0, 62.0)):
        msg = record.getMessage()
        assert str(rr) in msg, f"log record must name the failed radius: {msg!r}"
        assert "TypeError" in msg, f"log record must name the exception TYPE: {msg!r}"
        assert f"deterministic bug at radius {rr}" in msg, (
            f"log record must include the exception MESSAGE: {msg!r}"
        )


def test_no_warning_logged_on_first_radius_success(monkeypatch, caplog):
    fake = _make_fake(lambda i, rr: {"gwf": "SENTINEL"})  # always succeeds
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    with caplog.at_level("WARNING", logger="model_io_utils"):
        mio.refine_with_retry(COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws")

    assert not [r for r in caplog.records if r.levelname == "WARNING"]


def test_docstring_notes_sigill_not_catchable_and_subprocess_requirement():
    # FIX E: the docstring must make the SIGILL-vs-Python-exception distinction
    # explicit, and name the subprocess mitigation for callers that must
    # survive it -- so this isn't silently reported as "a radius-walk failure".
    doc = (mio.refine_with_retry.__doc__ or "").upper()
    assert "SIGILL" in doc
    assert "SUBPROCESS" in doc


# ===========================================================================
# Criterion 2 — transport_base_model NO LONGER defines its own copy of the
# retry body.  It re-exports the promoted helper as the module attribute
# _refine_with_retry (either `_refine_with_retry = mio.refine_with_retry` OR a
# thin wrapper that forwards), so build_spill_scenario / build_doublet_base call
# the SAME promoted logic.  The acceptance point is DELEGATION: these tests must
# FAIL while the divergent private copy still lives in transport_base_model, and
# pass for BOTH accepted re-export forms.
# ===========================================================================
def test_transport_delegates_to_promoted_helper(monkeypatch):
    # Never touch real refinement: neutralize the low-level builder up front so
    # that IF a leftover private copy still ran its own radius-walk, it would use
    # THIS fake (and, crucially, would NOT touch the promoted-helper spy below).
    leftover_builder = _make_fake(lambda i, rr: object())
    monkeypatch.setattr(mio, "build_refined_gwf_model", leftover_builder)

    # Accepted form A — pure re-export: the module attribute IS the promoted
    # helper object itself.  Identity settles delegation with nothing more to do.
    if tbm._refine_with_retry is getattr(mio, "refine_with_retry", object()):
        return

    # Accepted form B — thin wrapper: it must FORWARD to mio.refine_with_retry.
    # Spy on the promoted helper and prove the transport attribute routes through
    # it (returning the spy's value), rather than executing an independent body.
    marker = object()
    spy_calls = []

    def spy(*args, **kwargs):
        spy_calls.append((args, kwargs))
        return marker

    monkeypatch.setattr(mio, "refine_with_retry", spy, raising=False)

    out = tbm._refine_with_retry(COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws")

    assert spy_calls, (
        "transport_base_model._refine_with_retry must delegate to "
        "mio.refine_with_retry, not keep its own radius-walk body"
    )
    assert out is marker, "the wrapper must forward the promoted helper's return"
    assert leftover_builder.calls == [], (
        "delegating wrapper must not call build_refined_gwf_model itself"
    )


def test_transport_has_no_duplicate_retry_body():
    # The retry BODY (the radius loop that calls build_refined_gwf_model) must
    # live only in the promoted helper.  A pure re-export points its source at
    # model_io_utils; a thin wrapper lives in transport_base_model but must NOT
    # reference build_refined_gwf_model (i.e. must not re-implement the walk).
    fn = tbm._refine_with_retry
    src_file = os.path.basename(inspect.getsourcefile(fn) or "")

    if src_file == "model_io_utils.py":
        # pure re-export: same object as the promoted helper
        assert fn is mio.refine_with_retry
        return

    assert src_file == "transport_base_model.py", (
        f"unexpected source file for the transport helper: {src_file!r}"
    )
    src = inspect.getsource(fn)
    assert "build_refined_gwf_model" not in src, (
        "transport_base_model must not keep its own copy of the retry body "
        "(no direct build_refined_gwf_model call); delegate to the promoted "
        "mio.refine_with_retry instead"
    )
