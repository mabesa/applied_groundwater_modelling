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
# Criterion 2 — transport_base_model re-exports the promoted helper as the
# module attribute _refine_with_retry, so build_spill_scenario /
# build_doublet_base call the SAME logic.  We assert behavioral equivalence
# (accepts either `_refine_with_retry = mio.refine_with_retry` or a thin
# wrapper) — never a divergent private copy.
# ===========================================================================
def test_transport_reexports_helper_attribute():
    assert hasattr(tbm, "_refine_with_retry"), (
        "transport_base_model must keep a module attribute _refine_with_retry "
        "(the promoted helper) for build_spill_scenario/build_doublet_base"
    )
    assert callable(tbm._refine_with_retry)


@pytest.mark.parametrize("caller_name", ["refine_with_retry", "_refine_with_retry"])
def test_promoted_and_transport_helpers_share_behavior(monkeypatch, caller_name):
    # Same fake scenario driven through BOTH the public mio helper and the
    # transport re-export must yield identical control flow.
    caller = (mio.refine_with_retry if caller_name == "refine_with_retry"
              else tbm._refine_with_retry)

    sentinel = object()

    def behavior(i, rr):
        # succeed on the 2nd radius (62.0)
        return sentinel if i == 1 else RuntimeError("retry")

    fake = _make_fake(behavior)
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    res, radius = caller(COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws")

    assert res is sentinel
    assert radius == 62.0
    assert [c["refine_radius"] for c in fake.calls] == [70.0, 62.0]
    assert _basenames(fake) == ["rg0", "rg1"]


def test_transport_helper_total_failure_matches(monkeypatch):
    # The transport re-export must also raise RuntimeError on total failure.
    fake = _make_fake(lambda i, rr: ValueError("still-boom"))
    monkeypatch.setattr(mio, "build_refined_gwf_model", fake)

    with pytest.raises(RuntimeError) as exc:
        tbm._refine_with_retry(
            COARSE, BOUNDARY, RIVER, POINTS, HEADS, "/ws",
            refine_radii=(70.0, 62.0))
    assert "still-boom" in str(exc.value)
