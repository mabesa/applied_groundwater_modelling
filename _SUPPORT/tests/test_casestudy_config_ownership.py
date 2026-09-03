"""C1 A20 — the student's copied config must not be able to move the MESH.

Students copy `template/` into their own folder and edit their copy; §5 sanctions
moving `source.location`. The flow half refines on the CANONICAL corridor, so if the
transport half followed the student's copy the two halves would build different grids
and the "one-change" flip test would silently change two things.

These tests pin the ownership split and the cache identity that goes with it. None of
them run MODFLOW.
"""
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_SUPPORT" / "src"))

import case_utils as cu                      # noqa: E402
import casestudy_flow_common as cfc          # noqa: E402
import transport_base_model as tbm           # noqa: E402

CANON = REPO / "PROJECT" / "workspace" / "template" / "case_config_transport.yaml"
GROUPS = tuple(range(13))


def _copy_with(tmp_path, mutate):
    """A student-style copy of the shared config with one field changed."""
    p = tmp_path / "case_config_transport.yaml"
    shutil.copy(CANON, p)
    cfg = yaml.safe_load(p.read_text())
    for opt in cfg["transport_scenarios"]["options"]:
        if int(opt["id"]) == 0:
            mutate(opt)
    p.write_text(yaml.safe_dump(cfg))
    return p


# --- 1. the anchor is canonical, and it is what the flow half refines on ------

@pytest.mark.parametrize("group", GROUPS)
def test_refine_anchor_is_the_corridor_the_flow_half_actually_refines(group):
    """Tie the anchor to `group_refine_points` itself, not to a re-derivation.

    The flow half refines on `group_refine_points`; the transport half now anchors on
    `group_refine_anchor`. Asserting they agree by re-deriving both from the config
    would pass even if the two functions diverged, so compare the corridor the flow
    half actually produces.
    """
    anchor = cfc.group_refine_anchor(group)
    ext = tuple(cfc.group_doublet_points(group)[1])
    flow_pts = cfc.group_refine_points(group)
    expected = cfc._corridor_anchors(anchor, ext) + [tuple(cfc.group_doublet_points(group)[0])]
    assert [tuple(np.round(p, 6)) for p in flow_pts] == \
           [tuple(np.round(p, 6)) for p in expected]


@pytest.mark.parametrize("group", GROUPS)
def test_every_group_has_a_pinned_radius_and_an_anchor(group):
    assert cfc.group_refine_radius(group) is not None
    assert len(cfc.group_refine_anchor(group)) == 2


def test_a_students_moved_spill_does_not_move_the_anchor(tmp_path):
    """🔴 The A20 invariant. §5 invites moving the source; the MESH must not follow.

    Non-vacuous: the same edit read through the student's own copy DOES move the
    spill, which is exactly the value that used to reach the mesh.
    """
    moved = _copy_with(tmp_path, lambda o: o["source"]["location"].update(
        {"easting": 400.0, "northing": -400.0}))

    canonical_anchor = cfc.group_refine_anchor(0)
    still = cfc.group_refine_anchor(0, config_path=str(CANON))
    assert still == canonical_anchor

    # the student's copy really did move the source (guards against a no-op edit)
    local = cu.lint_transport_config(config_path=str(moved), groups=[0])[0]
    assert float(local["source"]["location"]["easting"]) == 400.0
    from_local = cfc.group_refine_anchor(0, config_path=str(moved))
    assert from_local != canonical_anchor, (
        "the mutation did not change the anchor when read from the copy -- this test "
        "would pass even if the notebook read the student's file")


# --- 2. drift report: instructor fields only ---------------------------------

@pytest.mark.parametrize("mutate,field", [
    (lambda o: o["geometry"].update({"refine_radius_m": 55.0}), "geometry.refine_radius_m"),
    (lambda o: o["transport"].update({"porosity": 0.31}), "transport.porosity"),
    (lambda o: o["doublet"].update({"injection_easting": 1.0}), "doublet.injection_easting"),
])
def test_drift_reports_instructor_owned_changes(tmp_path, mutate, field):
    drift = cu.transport_config_drift(0, str(_copy_with(tmp_path, mutate)))
    assert [d[0] for d in drift] == [field], drift


def test_drift_ignores_student_owned_knobs(tmp_path):
    for i, mutate in enumerate((
            lambda o: o["source"].update({"concentration_mg_L": 999.0}),
            lambda o: o["source"]["location"].update({"easting": 12.0}),
            lambda o: o["source"].update({"duration_days": 7.0}),
            lambda o: o["doublet"].update({"pumping_rate_m3_d": 111.0}),
    )):
        d = tmp_path / f"case{i}"
        d.mkdir()
        assert cu.transport_config_drift(0, str(_copy_with(d, mutate))) == []


def test_drift_is_empty_against_the_canonical_file_itself():
    assert cu.transport_config_drift(0, str(CANON)) == []


def test_student_owned_list_is_an_allow_list_not_a_deny_list():
    """A field added to the config later must be instructor-owned by default."""
    assert "geometry.refine_radius_m" not in cu.STUDENT_OWNED_FIELDS
    assert "transport.porosity" not in cu.STUDENT_OWNED_FIELDS
    assert "source.concentration_mg_L" in cu.STUDENT_OWNED_FIELDS


# --- 3. cache identity -------------------------------------------------------

def _write_cache(ws, inputs):
    ws.mkdir(parents=True, exist_ok=True)
    meta = dict(scenario_inputs=tbm.scenario_inputs(**inputs)) if inputs is not None else {}
    np.savez(str(ws / "base_cache.npz"), meta=meta, allow_pickle=True)


BASE = dict(Q=4320.0, c_src=5.0, geometry="point", total_time=365.0)


def test_cache_status_current_stale_missing_legacy(tmp_path):
    ws = tmp_path / "ws"
    assert tbm.scenario_cache_status(ws, BASE)[0] == "missing"

    _write_cache(ws, BASE)
    assert tbm.scenario_cache_status(ws, BASE) == ("current", [])

    status, changed = tbm.scenario_cache_status(ws, {**BASE, "c_src": 9.0})
    assert (status, changed) == ("stale", ["c_src"])

    legacy = tmp_path / "legacy"
    _write_cache(legacy, None)
    assert tbm.scenario_cache_status(legacy, BASE)[0] == "legacy"


def test_cache_status_ignores_defaults_the_caller_never_passed(tmp_path):
    """The cache records build defaults; comparing their union would always be stale."""
    ws = tmp_path / "ws"
    _write_cache(ws, {**BASE, "cr_target": 0.9, "nstp_cap": 4000})
    assert tbm.scenario_cache_status(ws, BASE) == ("current", [])


def test_load_doublet_base_refuses_a_stale_cache(tmp_path):
    ws = tmp_path / "ws"
    _write_cache(ws, BASE)
    with pytest.raises(ValueError, match="c_src"):
        tbm.load_doublet_base(ws, expect_inputs={**BASE, "c_src": 9.0})


def test_load_doublet_base_refuses_a_legacy_cache(tmp_path):
    ws = tmp_path / "ws"
    _write_cache(ws, None)
    with pytest.raises(ValueError, match="predates"):
        tbm.load_doublet_base(ws, expect_inputs=BASE)


def test_moving_only_the_source_marks_the_cache_stale(tmp_path):
    """A §5 flip test must rebuild -- the mesh stays, but the answer changes."""
    ws = tmp_path / "ws"
    inputs = {**BASE, "spill_xy": [10.0, 20.0], "refine_anchor_xy": [10.0, 20.0]}
    _write_cache(ws, inputs)
    status, changed = tbm.scenario_cache_status(
        ws, {**inputs, "spill_xy": [80.0, 20.0]})
    assert (status, changed) == ("stale", ["spill_xy"])
    # ...while the anchor, and therefore the mesh, is untouched
    assert tbm.scenario_cache_status(ws, inputs) == ("current", [])


# --- 4. the notebook actually uses the canonical resolution -------------------

def test_notebook_reads_mesh_geometry_from_the_canonical_config():
    import json
    nb = json.loads((REPO / "PROJECT" / "workspace" / "template"
                     / "case_study_transport_group_0.ipynb").read_text())
    src = "\n".join("".join(c["source"]) for c in nb["cells"])
    assert "cfc.group_refine_radius(GROUP_ID)" in src
    assert "cfc.group_refine_anchor(GROUP_ID)" in src
    assert "(scn.get('geometry') or {}).get('refine_radius_m')" not in src, (
        "the notebook is reading the pinned radius from the STUDENT's copy again")
    assert "refine_anchor_xy=ANCHOR_XY" in src
    assert "scenario_cache_status(" in src
    assert "have_cache = os.path.exists" not in src, (
        "the notebook gates on cache existence again, so a changed knob is ignored")


# --- 5. the anchor really reaches the mesh, and the spill really reaches the source

class _Stop(Exception):
    pass


def _stub_gwf():
    """Minimal stand-in: `build_spill_scenario` reads the exe name before refining."""
    from types import SimpleNamespace
    return SimpleNamespace(simulation=SimpleNamespace(exe_name="mf6"))


def _capture_refine_points(monkeypatch, seen):
    def _fake(coarse_gwf, boundary_gdf, river_gdf, refine_points, heads_array, ws, **kw):
        seen["points"] = list(refine_points)
        raise _Stop
    monkeypatch.setattr(tbm, "_refine_with_retry", _fake)


def test_the_anchor_drives_refinement_and_the_spill_drives_the_source(monkeypatch, tmp_path):
    """🔴 Dataflow, not source strings: what does `build_spill_scenario` refine on?

    Intercepts the refinement call so no MODFLOW runs. The corridor must be built
    from the ANCHOR (canonical), while the source geometry follows the SPILL.
    """
    seen = {}
    _capture_refine_points(monkeypatch, seen)

    inj, ext = (2681704.9, 1247555.9), (2681885.9, 1247397.9)
    anchor = (ext[0] + 50.0, ext[1] - 77.0)
    moved_spill = (ext[0] + 400.0, ext[1] - 400.0)   # a §5 flip test

    with pytest.raises(_Stop):
        tbm.build_spill_scenario(_stub_gwf(), None, None, inj, ext, moved_spill,
                                 case_ws=tmp_path / "ws",
                                 heads_array=np.zeros(1),
                                 refine_anchor_xy=anchor)

    pts = seen["points"]
    assert pts[-1] == pytest.approx(inj), "injection well must still be refined"
    corridor = np.array(pts[:-1])
    # the corridor must bracket the ANCHOR, not the moved spill
    assert np.min(np.hypot(*(corridor - np.array(anchor)).T)) < 60.0
    assert np.min(np.hypot(*(corridor - np.array(moved_spill)).T)) > 200.0, (
        "the refinement corridor followed the student's moved spill -- the flow and "
        "transport halves would build different grids")


def test_without_an_anchor_the_builder_is_unchanged(monkeypatch, tmp_path):
    """Backwards compatibility: no anchor => refine on the spill, as before."""
    seen = {}
    _capture_refine_points(monkeypatch, seen)
    inj, ext = (2681704.9, 1247555.9), (2681885.9, 1247397.9)
    spill = (ext[0] + 400.0, ext[1] - 400.0)
    with pytest.raises(_Stop):
        tbm.build_spill_scenario(_stub_gwf(), None, None, inj, ext, spill,
                                 case_ws=tmp_path / "ws",
                                 heads_array=np.zeros(1))
    corridor = np.array(seen["points"][:-1])
    assert np.min(np.hypot(*(corridor - np.array(spill)).T)) < 60.0


def test_cache_status_notices_a_changed_build_default(tmp_path):
    """A default changed in code must invalidate warm caches, not be ignored."""
    ws = tmp_path / "ws"
    _write_cache(ws, {**BASE, "cr_target": 0.5})     # not the current default
    status, changed = tbm.scenario_cache_status(ws, BASE)
    assert status == "stale" and "cr_target" in changed
