"""T1 S3a -- mesh identity + content-addressed workspaces
(DESIGN_DOCS/T1_S3_brief.md v3).

Covers brief Section 4's nine exit criteria:

  1. the default spec reproduces today            -- anchored here (static
                                                       defaults), verified
                                                       end-to-end by
                                                       `t0_gate_harness.py compare`
  2. every MeshSpec field moves mesh_spec_hash, including a levels reordering
  3. a different winning retry radius moves mesh_hash, not mesh_spec_hash
  4. a GIS content change moves mesh_hash (a COPIED file, never the real one)
  5. identical spec reuses its workspace; different specs never collide --
     tested on BOTH modules
  6. all four PRT runtime paths and both demo workspaces are addressed
  7. no LOCKED_PARAMS cell-size read remains in either refinement path
  8. float.hex() round-trips; non-finite rejected; two cell sizes differing
     below 12 significant digits produce DIFFERENT hashes
  9. 71+ existing tests green; no numeric value moves -- verified by running
     the full pre-existing suite alongside this file, not inside it

Fast (solve-free) tests dominate; a handful of `@pytest.mark.slow` tests do a
REAL corridor-refinement / steady-GWF solve (never the full coupled transient
solve) to prove the on-disk workspace-naming behaviour end to end.

Run with:  uv run pytest _SUPPORT/tests/test_t1_gridspec.py -v
Use `-m "not slow"` to run only the fast, solve-free tests.
"""
from __future__ import annotations

import inspect
import math
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_prt_capture as tpc  # noqa: E402
import transport_srcpulse_demo as tsd  # noqa: E402

# T0.0's own (deliberately lossy) formatter -- used ONLY to demonstrate, in
# one test below, that it is NOT what this module's identity uses.
_T0_0_FLOAT_FORMAT = "{:.11e}"


def _two_level_spec() -> tsd.MeshSpec:
    return tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=10.0),
                                tsd.MeshLevel(cell_size=5.0)))


# ---------------------------------------------------------------------------
# criterion 1: the default spec reproduces today (static anchor; the real
# numeric proof is `t0_gate_harness.py compare`)
# ---------------------------------------------------------------------------
def test_default_meshspec_matches_todays_locked_params():
    spec = tsd.MeshSpec()
    assert spec.base_cell_size == tsd.LOCKED_PARAMS["base_cell_size"] == 50.0
    assert len(spec.levels) == 1
    assert spec.levels[0].cell_size == tsd.LOCKED_PARAMS["refined_cell_size"] == 10.0
    assert spec.levels[0].radius_m is None
    assert spec.retry_radii == (70.0, 62.0, 78.0, 56.0, 84.0)


def test_default_courantspec_matches_todays_srcpulse_defaults():
    """CourantSpec is declared only (brief Section 2) -- its defaults still
    mirror today's `_courant_nstp` / `build_srcpulse_demo` defaults so a
    future S4/S8 wiring starts from the right numbers."""
    cs = tsd.CourantSpec()
    assert cs.sliver_floor_frac == 0.4
    assert cs.cr_target == 0.9
    assert cs.nstp_cap == 2000


def test_courantspec_is_declared_only_and_unused_by_courant_nstp():
    """No Courant behaviour change: `_courant_nstp` must not reference
    CourantSpec at all."""
    src = inspect.getsource(tsd._courant_nstp)
    assert "CourantSpec" not in src


# ---------------------------------------------------------------------------
# criterion 8: float.hex() round-trips; non-finite rejected; sub-12-sig-fig
# cell sizes produce DIFFERENT hashes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("x", [50.0, 10.0, 1.0 / 3.0, 1e-300, 1e300, -0.0, 0.1, 84.0])
def test_canonical_float_round_trips_exact_ieee754(x):
    s = tsd._canonical_float(x)
    assert isinstance(s, str)
    assert float.fromhex(s) == x


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_canonical_float_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        tsd._canonical_float(bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_mesh_spec_hash_rejects_non_finite_field(bad):
    with pytest.raises(ValueError):
        tsd.mesh_spec_hash(tsd.MeshSpec(base_cell_size=bad))


def test_mesh_hash_rejects_non_finite_winning_radius(tmp_path):
    boundary = tmp_path / "b.gpkg"; boundary.write_bytes(b"b")
    rivers = tmp_path / "r.gpkg"; rivers.write_bytes(b"r")
    with pytest.raises(ValueError):
        tsd.mesh_hash(tsd.MeshSpec(), winning_radius=float("nan"),
                      boundary_path=boundary, rivers_path=rivers)


def test_identity_distinguishes_cell_sizes_below_12_significant_digits():
    """The whole reason T0.0's FLOAT_FORMAT is refused for identity (brief
    Section 1 / 2.2): two cell sizes differing in their 14th-15th
    significant digit must still hash DIFFERENTLY."""
    a = 50.0
    b = 50.0 + 1e-13
    assert a != b, "test setup: the two floats must be genuinely distinct"
    ha = tsd.mesh_spec_hash(tsd.MeshSpec(base_cell_size=a))
    hb = tsd.mesh_spec_hash(tsd.MeshSpec(base_cell_size=b))
    assert ha != hb


def test_the_t0_0_formatter_would_have_collided_here():
    """Demonstrates the defect v1 had (brief Section 1 table, row 2): under
    T0.0's 12-significant-digit FLOAT_FORMAT the same two values DO collide,
    which is exactly why this module does not reuse it for identity."""
    a, b = 50.0, 50.0 + 1e-13
    assert _T0_0_FLOAT_FORMAT.format(a) == _T0_0_FLOAT_FORMAT.format(b)
    assert tsd.mesh_spec_hash(tsd.MeshSpec(base_cell_size=a)) != \
        tsd.mesh_spec_hash(tsd.MeshSpec(base_cell_size=b))


def test_digest_is_32_hex_chars():
    h = tsd.mesh_spec_hash(tsd.MeshSpec())
    assert len(h) == 32
    assert all(c in "0123456789abcdef" for c in h)


def test_canonical_json_is_sorted_and_deterministic():
    spec = tsd.MeshSpec()
    j1 = tsd._canonical_json(spec)
    j2 = tsd._canonical_json(spec)
    assert j1 == j2
    assert j1.index('"base_cell_size"') < j1.index('"levels"') < j1.index('"retry_radii"')


def test_file_content_hash_is_content_not_path(tmp_path):
    a = tmp_path / "a.bin"
    a.write_bytes(b"same-bytes")
    sub = tmp_path / "sub"
    sub.mkdir()
    b = sub / "b.bin"
    b.write_bytes(b"same-bytes")
    assert tsd._file_content_hash(a) == tsd._file_content_hash(b)

    b.write_bytes(b"different-bytes")
    assert tsd._file_content_hash(a) != tsd._file_content_hash(b)


# ---------------------------------------------------------------------------
# criterion 2: every MeshSpec field changes mesh_spec_hash, including a
# levels REORDERING
# ---------------------------------------------------------------------------
def test_every_meshspec_field_changes_the_declared_hash():
    base_hash = tsd.mesh_spec_hash(tsd.MeshSpec())
    variants = {
        "base_cell_size": tsd.MeshSpec(base_cell_size=33.0),
        "levels_cell_size": tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=7.0),)),
        "levels_radius_m": tsd.MeshSpec(
            levels=(tsd.MeshLevel(cell_size=10.0, radius_m=25.0),)),
        "retry_radii": tsd.MeshSpec(retry_radii=(1.0, 2.0, 3.0)),
    }
    for name, variant in variants.items():
        assert tsd.mesh_spec_hash(variant) != base_hash, \
            f"MeshSpec.{name} did not move mesh_spec_hash"


def test_levels_reordering_changes_the_declared_hash():
    """`levels` is order-significant (brief Section 2.2): swapping two
    DISTINCT levels must move the hash even though the SET is unchanged."""
    a = tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=10.0), tsd.MeshLevel(cell_size=5.0)))
    b = tsd.MeshSpec(levels=(tsd.MeshLevel(cell_size=5.0), tsd.MeshLevel(cell_size=10.0)))
    assert tsd.mesh_spec_hash(a) != tsd.mesh_spec_hash(b)


def test_retry_radii_reordering_changes_the_declared_hash():
    a = tsd.MeshSpec(retry_radii=(70.0, 62.0))
    b = tsd.MeshSpec(retry_radii=(62.0, 70.0))
    assert tsd.mesh_spec_hash(a) != tsd.mesh_spec_hash(b)


# ---------------------------------------------------------------------------
# criterion 3: a different winning retry radius moves mesh_hash while
# mesh_spec_hash stays put
# ---------------------------------------------------------------------------
def test_different_winning_radius_changes_mesh_hash_not_mesh_spec_hash(tmp_path):
    boundary = tmp_path / "boundary.gpkg"
    rivers = tmp_path / "rivers.gpkg"
    boundary.write_bytes(b"boundary-bytes")
    rivers.write_bytes(b"rivers-bytes")

    spec = tsd.MeshSpec()
    spec_hash_before = tsd.mesh_spec_hash(spec)

    h_70 = tsd.mesh_hash(spec, winning_radius=70.0,
                         boundary_path=boundary, rivers_path=rivers)
    h_62 = tsd.mesh_hash(spec, winning_radius=62.0,
                         boundary_path=boundary, rivers_path=rivers)

    assert h_70 != h_62
    assert tsd.mesh_spec_hash(spec) == spec_hash_before  # declared identity untouched
    assert spec_hash_before not in (h_70, h_62)           # not merely reusing the declared hash


# ---------------------------------------------------------------------------
# criterion 4: a GIS content change moves mesh_hash -- mutate a COPIED file,
# never the real one
# ---------------------------------------------------------------------------
def test_boundary_content_change_changes_mesh_hash(tmp_path):
    boundary = tmp_path / "boundary.gpkg"
    rivers = tmp_path / "rivers.gpkg"
    boundary.write_bytes(b"boundary-v1")
    rivers.write_bytes(b"rivers-v1")

    spec = tsd.MeshSpec()
    before = tsd.mesh_hash(spec, winning_radius=70.0,
                           boundary_path=boundary, rivers_path=rivers)

    boundary.write_bytes(b"boundary-v2-EDITED")  # mutate the COPY only
    after = tsd.mesh_hash(spec, winning_radius=70.0,
                          boundary_path=boundary, rivers_path=rivers)

    assert before != after


def test_rivers_content_change_changes_mesh_hash(tmp_path):
    boundary = tmp_path / "boundary.gpkg"
    rivers = tmp_path / "rivers.gpkg"
    boundary.write_bytes(b"boundary-v1")
    rivers.write_bytes(b"rivers-v1")

    spec = tsd.MeshSpec()
    before = tsd.mesh_hash(spec, winning_radius=70.0,
                           boundary_path=boundary, rivers_path=rivers)

    rivers.write_bytes(b"rivers-v2-EDITED")  # mutate the COPY only
    after = tsd.mesh_hash(spec, winning_radius=70.0,
                          boundary_path=boundary, rivers_path=rivers)

    assert before != after


# ---------------------------------------------------------------------------
# API policy (brief Section 3.1): refine_radii= folds into the default spec;
# refine_radii= AND mesh_spec= together is a ValueError on every public
# entry point that accepts both -- and it must raise BEFORE any I/O.
# ---------------------------------------------------------------------------
def test_legacy_refine_radii_folds_into_default_meshspec():
    spec = tsd._resolve_mesh_spec(refine_radii=(11.0, 22.0, 33.0))
    assert spec.retry_radii == (11.0, 22.0, 33.0)
    assert spec.base_cell_size == tsd.MeshSpec().base_cell_size
    assert spec.levels == tsd.MeshSpec().levels


def test_omitting_both_gives_the_default_spec():
    assert tsd._resolve_mesh_spec() == tsd.MeshSpec()


def test_refine_corridor_rejects_both_refine_radii_and_mesh_spec():
    with pytest.raises(ValueError, match="not both"):
        tsd.refine_corridor(object(), object(), object(),
                            refine_radii=(1.0,), mesh_spec=tsd.MeshSpec())


def test_build_srcpulse_demo_rejects_both_refine_radii_and_mesh_spec():
    with pytest.raises(ValueError, match="not both"):
        tsd.build_srcpulse_demo(refine_radii=(1.0,), mesh_spec=tsd.MeshSpec())


def test_build_prt_capture_rejects_both_refine_radii_and_mesh_spec():
    with pytest.raises(ValueError, match="not both"):
        tpc.build_prt_capture(refine_radii=(1.0,), mesh_spec=tpc.MeshSpec())


def test_capture_halfwidth_at_rejects_both_refine_radii_and_mesh_spec():
    with pytest.raises(ValueError, match="not both"):
        tpc.capture_halfwidth_at(refine_radii=(1.0,), mesh_spec=tpc.MeshSpec())


# ---------------------------------------------------------------------------
# multi-level MeshSpec: NotImplementedError naming S3b, raised BEFORE any
# GIS / MF6 work (fast -- no real args needed on the public entry points).
# ---------------------------------------------------------------------------
def test_require_single_level_raises_naming_s3b():
    with pytest.raises(NotImplementedError, match="S3b"):
        tsd._require_single_level(_two_level_spec())


def test_multi_level_raises_before_any_io_refine_corridor():
    with pytest.raises(NotImplementedError, match="S3b"):
        tsd.refine_corridor(object(), object(), object(), mesh_spec=_two_level_spec())


def test_multi_level_raises_before_any_io_build_srcpulse_demo():
    with pytest.raises(NotImplementedError, match="S3b"):
        tsd.build_srcpulse_demo(mesh_spec=_two_level_spec())


def test_multi_level_raises_before_any_io_build_prt_capture():
    with pytest.raises(NotImplementedError, match="S3b"):
        tpc.build_prt_capture(mesh_spec=_two_level_spec())


def test_multi_level_raises_before_any_io_capture_halfwidth_at():
    with pytest.raises(NotImplementedError, match="S3b"):
        tpc.capture_halfwidth_at(mesh_spec=_two_level_spec())


# ---------------------------------------------------------------------------
# criterion 7: no LOCKED_PARAMS cell-size read remains in EITHER refinement
# path (the Courant floor in `_courant_nstp` is explicitly OUT of scope and
# deliberately untouched -- checked separately, above)
# ---------------------------------------------------------------------------
def test_no_locked_params_cell_size_read_in_demo_refinement_path():
    src = inspect.getsource(tsd._refine_with_retry) + inspect.getsource(tsd.refine_corridor)
    assert 'LOCKED_PARAMS["refined_cell_size"]' not in src
    assert 'LOCKED_PARAMS["base_cell_size"]' not in src


def test_no_locked_params_cell_size_read_in_prt_refinement_path():
    src = inspect.getsource(tpc._build_flow)
    assert 'LOCKED_PARAMS["refined_cell_size"]' not in src
    assert 'LOCKED_PARAMS["base_cell_size"]' not in src


# ---------------------------------------------------------------------------
# criterion 6: all six locations are content-addressed -- the old unkeyed
# literal directory names must be gone from both modules.
# ---------------------------------------------------------------------------
def test_no_unkeyed_refgrid_or_sim_literal_remains_in_source():
    demo_src = Path(tsd.__file__).read_text()
    prt_src = Path(tpc.__file__).read_text()
    assert '/ "refgrid"' not in demo_src
    assert '/ "refgrid"' not in prt_src
    assert 'case_ws / "sim"' not in demo_src


# ---------------------------------------------------------------------------
# criterion 5 (fast, monkeypatched -- both modules share `_refine_with_retry`,
# so this exercises the ONE mechanism both `refine_corridor` (demo) and
# `_build_flow` (PRT) call): identical (mesh_spec, GIS) reuses the SAME
# refgrid_<hash> workspace; a different declared spec, or a GIS content
# change, never collides. No MF6 solve -- `mio.build_refined_gwf_model` is
# faked exactly as `test_refine_with_retry.py` fakes it for `model_io_utils`.
# ---------------------------------------------------------------------------
def _fake_build_refined_gwf_model(calls):
    def _fake(gwf, boundary_gdf=None, river_gdf=None, refine_points=None,
              head_array=None, workspace=None, refine_radius=200.0,
              base_cell_size=50.0, refined_cell_size=10.0, well_data=None,
              sim_name="refined_model", baseline_head_array=None):
        calls.append(dict(workspace=workspace, refine_radius=refine_radius))
        return {"gwf": "SENTINEL"}
    return _fake


def test_refine_with_retry_workspace_naming_reuses_and_never_collides(tmp_path, monkeypatch):
    boundary = tmp_path / "boundary.gpkg"
    rivers = tmp_path / "rivers.gpkg"
    boundary.write_bytes(b"b1")
    rivers.write_bytes(b"r1")

    calls = []
    monkeypatch.setattr(tsd.mio, "build_refined_gwf_model",
                        _fake_build_refined_gwf_model(calls))

    case_ws = tmp_path / "case"
    spec = tsd.MeshSpec()

    _res1, _radius1, hash1 = tsd._refine_with_retry(
        object(), object(), object(), [], object(), case_ws,
        mesh_spec=spec, boundary_path=boundary, rivers_path=rivers)
    _res2, _radius2, hash2 = tsd._refine_with_retry(
        object(), object(), object(), [], object(), case_ws,
        mesh_spec=spec, boundary_path=boundary, rivers_path=rivers)

    # identical spec + GIS -> the SAME candidate workspace, both times
    assert hash1 == hash2
    assert Path(calls[0]["workspace"]).name == Path(calls[1]["workspace"]).name
    assert Path(calls[0]["workspace"]).name == f"refgrid_{hash1}"

    # a different DECLARED spec must never collide
    spec2 = tsd.MeshSpec(base_cell_size=33.0)
    _res3, _radius3, hash3 = tsd._refine_with_retry(
        object(), object(), object(), [], object(), case_ws,
        mesh_spec=spec2, boundary_path=boundary, rivers_path=rivers)
    assert hash3 != hash1
    assert calls[2]["workspace"] != calls[0]["workspace"]

    # a GIS content change must never collide either, spec held fixed
    rivers.write_bytes(b"r2-EDITED")
    _res4, _radius4, hash4 = tsd._refine_with_retry(
        object(), object(), object(), [], object(), case_ws,
        mesh_spec=spec, boundary_path=boundary, rivers_path=rivers)
    assert hash4 != hash1
    assert calls[3]["workspace"] != calls[0]["workspace"]


def test_refine_with_retry_rejects_multi_level_before_any_fake_call(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(tsd.mio, "build_refined_gwf_model",
                        _fake_build_refined_gwf_model(calls))
    with pytest.raises(NotImplementedError, match="S3b"):
        tsd._refine_with_retry(
            object(), object(), object(), [], object(), tmp_path,
            mesh_spec=_two_level_spec(), boundary_path=tmp_path, rivers_path=tmp_path)
    assert calls == []  # never reached the (fake) grid builder


# ---------------------------------------------------------------------------
# criterion 5, real end-to-end (slow): each module's OWN builder, a REAL
# corridor-refinement solve (never the full coupled/PRT-tracking solve).
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_refine_corridor_reuses_workspace_for_identical_spec(tmp_path):
    ws = tmp_path / "case"
    cgwf, boundary, rivers, _exe = tsd.load_limmat_flow()

    grid1 = tsd.refine_corridor(cgwf, boundary, rivers, case_ws=ws)
    grid2 = tsd.refine_corridor(cgwf, boundary, rivers, case_ws=ws)

    assert grid1["mesh_hash"] == grid2["mesh_hash"]
    refgrid_dirs = sorted(p.name for p in ws.glob("refgrid_*"))
    assert refgrid_dirs == [f"refgrid_{grid1['mesh_hash']}"]


@pytest.mark.slow
def test_refine_corridor_different_specs_never_collide(tmp_path):
    ws = tmp_path / "case"
    cgwf, boundary, rivers, _exe = tsd.load_limmat_flow()

    default_spec = tsd.MeshSpec()
    reordered_spec = tsd.MeshSpec(retry_radii=tuple(reversed(default_spec.retry_radii)))

    grid1 = tsd.refine_corridor(cgwf, boundary, rivers, mesh_spec=default_spec, case_ws=ws)
    grid2 = tsd.refine_corridor(cgwf, boundary, rivers, mesh_spec=reordered_spec, case_ws=ws)

    assert grid1["mesh_spec_hash"] != grid2["mesh_spec_hash"]
    assert grid1["mesh_hash"] != grid2["mesh_hash"]
    # each build's OWN successful workspace exists, and they are different --
    # NOT an exact count: a radius earlier in a REORDERED ladder can fail
    # (SIGILL / Triangle abort) before a later one succeeds, which legitimately
    # leaves a failed candidate's own (unused, never overwritten) directory
    # behind too -- that is the retry ladder working as designed, not a collision.
    refgrid_dirs = {p.name for p in ws.glob("refgrid_*")}
    assert f"refgrid_{grid1['mesh_hash']}" in refgrid_dirs
    assert f"refgrid_{grid2['mesh_hash']}" in refgrid_dirs
    assert grid1["mesh_hash"] != grid2["mesh_hash"]


@pytest.mark.slow
def test_build_flow_reuses_workspace_for_identical_spec(tmp_path):
    ws = tmp_path / "case"
    spec = tpc.MeshSpec()

    flow1 = tpc._build_flow(ws, 730.0, spec)
    flow2 = tpc._build_flow(ws, 730.0, spec)

    assert flow1["mesh_hash"] == flow2["mesh_hash"]
    assert flow1["flow_hash"] == flow2["flow_hash"]
    refgrid_dirs = sorted(p.name for p in ws.glob("refgrid_*"))
    assert refgrid_dirs == [f"refgrid_{flow1['mesh_hash']}"]
    gwf_dirs = sorted(p.name for p in ws.glob("gwf_*"))
    assert gwf_dirs == [f"gwf_{flow1['flow_hash']}"]


@pytest.mark.slow
def test_build_flow_different_specs_never_collide(tmp_path):
    ws = tmp_path / "case"
    default_spec = tpc.MeshSpec()
    reordered_spec = tpc.MeshSpec(retry_radii=tuple(reversed(default_spec.retry_radii)))

    flow1 = tpc._build_flow(ws, 730.0, default_spec)
    flow2 = tpc._build_flow(ws, 730.0, reordered_spec)

    assert flow1["mesh_hash"] != flow2["mesh_hash"]
    assert flow1["gwf_ws"] != flow2["gwf_ws"]
    # each build's OWN successful workspace exists (see the sibling demo test
    # for why this is not an exact directory COUNT).
    refgrid_dirs = {p.name for p in ws.glob("refgrid_*")}
    assert f"refgrid_{flow1['mesh_hash']}" in refgrid_dirs
    assert f"refgrid_{flow2['mesh_hash']}" in refgrid_dirs


@pytest.mark.slow
def test_halfwidth_probe_workspace_is_content_addressed(tmp_path):
    """Exit criterion 6, PRT location 'half-width probe' (brief ~:815): the
    bisection probe writes into a hash-keyed hwprobe_<...> directory that
    matches the flow's own gwf_<flow_hash> suffix, not an unkeyed shared one.
    A small, cheap probe (few scan points, small offset) keeps this real but
    fast."""
    ws = tmp_path / "case"
    tpc.capture_halfwidth_at(0.0, case_ws=ws, n_scan=9, max_offset_m=60.0, tol_m=5.0)

    hwprobe_dirs = list(ws.glob("hwprobe_*"))
    gwf_dirs = list(ws.glob("gwf_*"))
    assert len(hwprobe_dirs) == 1
    assert len(gwf_dirs) == 1
    flow_hash = gwf_dirs[0].name.split("gwf_", 1)[1]
    assert hwprobe_dirs[0].name == f"hwprobe_{flow_hash}"
