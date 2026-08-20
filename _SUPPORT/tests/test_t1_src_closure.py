"""T1 S1 -- transitive `_SUPPORT/src` source-closure fingerprint.

`_src_sha()` (`transport_srcpulse_demo.py:302` and `transport_prt_capture.py:364`)
extends from a hand-picked file list to the TRANSITIVE `_SUPPORT/src` closure of
the model build, via ONE shared helper (`transport_srcpulse_demo._resolve_src_closure`
/ `_framed_closure_digest` / `_src_closure_digest`) both modules call.

S1 is gate-EXEMPT and gate-BLIND (DESIGN_DOCS/T1_S1_brief.md, "Gate coverage"):
`compare` never reads `src_sha` and cannot run until T1 S2 adds the payload fields
it needs. These tests are therefore the ENTIRE safety argument for this step, not
a supplement to `compare`.

Isolation (brief S5.1): any test that would otherwise WRITE a mutated byte to a
real `_SUPPORT/src` file on disk instead copies the closure into a `tmp_path`-rooted
`_SUPPORT/src/` and runs the resolver against that copy IN A SUBPROCESS (`_probe`
below). `_resolve_src_closure` / `_framed_closure_digest` locate their `src_dir` /
`repo_root` from the CALLING module's own `__file__`, so importing the copy from a
fresh subprocess (rather than the live, already-imported module) makes the copy's
location -- not the live tree -- the one that gets scanned and hashed. The live
working tree is never mutated by any test in this file.

Run with:  uv run pytest _SUPPORT/tests/test_t1_src_closure.py -v
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import transport_prt_capture as tpc  # noqa: E402
import transport_srcpulse_demo as tsd  # noqa: E402

REAL_SRC_DIR = Path(tsd.__file__).resolve().parent
REPO_ROOT = REAL_SRC_DIR.parents[1]

# Pinned per DESIGN_DOCS/T1_S1_brief.md S3.2 -- independently verified twice.
# Assert the EXACT sets, never a count: a demo closure landing at 3 members
# means the deferred-import (function-body) AST scan is silently not running.
DEMO_EXPECTED = {
    "case_artifact_lock", "casestudy_refine_riv", "data_utils",
    "disv_grid_utils", "grid_utils", "model_io_utils", "transport_srcpulse_demo",
}
PRT_EXPECTED = DEMO_EXPECTED | {"transport_prt_capture"}

TRACK_DAYS = 730.0
FOOTPRINT_RADIUS_M = 10.0


# ---------------------------------------------------------------------------
# isolation helpers -- see module docstring
# ---------------------------------------------------------------------------
def _copy_helper_src(tmp_path: Path) -> Path:
    """Copy of the real 8-member PRT closure (superset of demo's 7) at
    `<tmp_path>/_SUPPORT/src/`, preserving the repo-relative layout the digest
    keys off.

    `transport_srcpulse_demo.py` -- which holds the shared closure/digest
    helpers -- has its OWN top-level `import model_io_utils`, so it cannot be
    copied alone: importing it from the copy requires the copy to be a
    self-sufficient closure, not just the one file. Once imported FROM this
    copy (in a subprocess -- see `_probe`), `transport_srcpulse_demo.__file__`
    points here, so `_resolve_src_closure`'s `src_dir` and
    `_framed_closure_digest`'s `repo_root` resolve to the copy, never the live
    repo.
    """
    dst = tmp_path / "_SUPPORT" / "src"
    dst.mkdir(parents=True, exist_ok=True)
    for name in PRT_EXPECTED:
        shutil.copy2(REAL_SRC_DIR / f"{name}.py", dst / f"{name}.py")
    return dst


_copy_full_closure_src = _copy_helper_src


def _probe(src_dir: Path, code: str) -> subprocess.CompletedProcess:
    """Run `code` in a FRESH subprocess with `src_dir` prepended to `sys.path`.

    `code` may `import transport_srcpulse_demo` (and, if copied there too,
    `transport_prt_capture`) -- always from `src_dir`, never from the live tree,
    because a fresh interpreter has nothing already imported.
    """
    preamble = f"import sys; sys.path.insert(0, {str(src_dir)!r})\n"
    return subprocess.run([sys.executable, "-c", preamble + code],
                          capture_output=True, text=True, timeout=180)


# ---------------------------------------------------------------------------
# the pinned closures (read-only against the live tree -- no mutation, so no
# subprocess isolation is required here)
# ---------------------------------------------------------------------------
def test_demo_closure_is_exactly_the_seven_expected_modules():
    closure = tsd._resolve_src_closure(tsd.__file__)
    assert set(closure) == DEMO_EXPECTED


def test_prt_closure_is_exactly_the_eight_expected_modules():
    closure = tsd._resolve_src_closure(tpc.__file__)
    assert set(closure) == PRT_EXPECTED


def test_closure_includes_deferred_function_level_imports():
    """The false-green trap (brief S2): `model_io_utils` imports `disv_grid_utils`
    (and `data_utils`, `grid_utils`, `casestudy_refine_riv`, `case_artifact_lock`)
    only INSIDE its functions. A walker that inspects module-level imports only
    would find zero `_SUPPORT/src` edges for `model_io_utils` and miss all five."""
    demo_closure = tsd._resolve_src_closure(tsd.__file__)
    assert "model_io_utils" in demo_closure
    for deferred in ("disv_grid_utils", "data_utils", "grid_utils",
                    "casestudy_refine_riv", "case_artifact_lock"):
        assert deferred in demo_closure, (
            f"{deferred} is imported only inside a function body in "
            "model_io_utils.py -- the AST scan must still find it")


def test_closure_excludes_stdlib_and_third_party():
    demo_closure = tsd._resolve_src_closure(tsd.__file__)
    prt_closure = tsd._resolve_src_closure(tpc.__file__)
    for name in ("numpy", "flopy", "pathlib", "geopandas", "shapely", "os", "json"):
        assert name not in demo_closure
        assert name not in prt_closure


# ---------------------------------------------------------------------------
# synthetic-closure tests -- all run against a tmp-path copy of the helper
# module, in a subprocess, per the isolation note above
# ---------------------------------------------------------------------------
def test_closure_is_order_independent_and_cycle_safe(tmp_path):
    src_dir = _copy_helper_src(tmp_path)
    (src_dir / "cyc_a.py").write_text("import cyc_b\n")
    (src_dir / "cyc_b.py").write_text(
        "def f():\n"
        "    import cyc_a  # deferred edge back to the root -- the cycle\n"
    )
    code = f"""
import json
import transport_srcpulse_demo as tsd
closure_a = tsd._resolve_src_closure({str(src_dir / "cyc_a.py")!r})
closure_b = tsd._resolve_src_closure({str(src_dir / "cyc_b.py")!r})
digest_a = tsd._framed_closure_digest(closure_a.values())
digest_b = tsd._framed_closure_digest(closure_b.values())
print(json.dumps({{"members_a": sorted(closure_a), "members_b": sorted(closure_b),
                   "digest_a": digest_a, "digest_b": digest_b}}))
"""
    proc = _probe(src_dir, code)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    # a cycle is NOT an error (the subprocess terminated at all -- it would hang
    # or blow the recursion/stack on an unguarded walker) and both entry points
    # into the SAME strongly-connected pair discover the SAME final member set,
    # regardless of which one is the traversal root (shuffled discovery order).
    assert result["members_a"] == ["cyc_a", "cyc_b"]
    assert result["members_b"] == ["cyc_a", "cyc_b"]
    assert result["digest_a"] == result["digest_b"]


def test_digest_framing_detects_byte_moved_between_members(tmp_path):
    """S3.1: framing, not concatenation. Move a byte from the end of one
    member's content to the start of the next's -- the CONCATENATED bytes are
    byte-for-byte identical either way, so an unframed digest would not move.
    The framed one must."""
    src_dir = _copy_helper_src(tmp_path)
    base_dir = tmp_path / "members_base"
    moved_dir = tmp_path / "members_moved"
    base_dir.mkdir()
    moved_dir.mkdir()
    (base_dir / "m1.dat").write_bytes(b"AAAAX")
    (base_dir / "m2.dat").write_bytes(b"YBBBB")
    (moved_dir / "m1.dat").write_bytes(b"AAAA")     # trailing "X" moved ...
    (moved_dir / "m2.dat").write_bytes(b"XYBBBB")   # ... to the front of m2
    assert (base_dir / "m1.dat").read_bytes() + (base_dir / "m2.dat").read_bytes() \
        == (moved_dir / "m1.dat").read_bytes() + (moved_dir / "m2.dat").read_bytes()

    code = f"""
import json
import transport_srcpulse_demo as tsd
base = tsd._framed_closure_digest([{str(base_dir / "m1.dat")!r}, {str(base_dir / "m2.dat")!r}])
moved = tsd._framed_closure_digest([{str(moved_dir / "m1.dat")!r}, {str(moved_dir / "m2.dat")!r}])
print(json.dumps({{"base": base, "moved": moved}}))
"""
    proc = _probe(src_dir, code)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["base"] != result["moved"], (
        "unframed concatenation hides a byte moved across a member boundary")


def test_member_removal_changes_the_digest(tmp_path):
    """On a SYNTHETIC closure with the root file's bytes held byte-for-byte
    identical across both calls, so this cannot pass merely because the root
    file changed -- only the member LIST differs."""
    src_dir = _copy_helper_src(tmp_path)
    members_dir = tmp_path / "members"
    members_dir.mkdir()
    root = members_dir / "root.dat"
    dep = members_dir / "dep.dat"
    root.write_bytes(b"root-content-unchanged")
    dep.write_bytes(b"dep-content")

    code = f"""
import json
import transport_srcpulse_demo as tsd
with_dep = tsd._framed_closure_digest([{str(root)!r}, {str(dep)!r}])
without_dep = tsd._framed_closure_digest([{str(root)!r}])
print(json.dumps({{"with_dep": with_dep, "without_dep": without_dep}}))
"""
    proc = _probe(src_dir, code)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["with_dep"] != result["without_dep"]
    # and root.dat itself was never rewritten between the two calls
    assert root.read_bytes() == b"root-content-unchanged"


def test_unparseable_member_raises(tmp_path):
    src_dir = _copy_helper_src(tmp_path)
    bad = src_dir / "badsyntax.py"
    bad.write_text("def broken(:\n    pass\n")
    code = f"""
import transport_srcpulse_demo as tsd
tsd._resolve_src_closure({str(bad)!r})
"""
    proc = _probe(src_dir, code)
    assert proc.returncode != 0, (
        "an unparseable closure member must raise, never be silently skipped")
    assert "ValueError" in proc.stderr


def test_relative_or_dynamic_import_raises(tmp_path):
    src_dir = _copy_helper_src(tmp_path)
    cases = {
        "rel_import.py": "from . import sibling\n",
        "dyn_import_module.py": "import importlib\n",
        "dyn_import_from.py": "from importlib import import_module\n",
        "dyn_import_builtin.py": "mod = __import__('os')\n",
    }
    for fname, source in cases.items():
        path = src_dir / fname
        path.write_text(source)
        code = f"""
import transport_srcpulse_demo as tsd
tsd._resolve_src_closure({str(path)!r})
"""
        proc = _probe(src_dir, code)
        assert proc.returncode != 0, f"{fname} should have raised, not been guessed at"
        assert "ValueError" in proc.stderr, proc.stderr


def test_hash_changes_on_any_real_member_edit(tmp_path):
    """S5.1: copy the REAL closure into a temp `_SUPPORT/src/`, run the resolver
    against the COPY in a subprocess, and mutate the COPY -- the live working
    tree is never touched. Every one of the 8 real closure members must move at
    least one of the two digests when edited (both implementations cover the
    real closure, not a stale hand-picked subset)."""
    src_dir = _copy_full_closure_src(tmp_path)

    def _digests() -> dict:
        code = """
import json
import transport_srcpulse_demo as tsd
import transport_prt_capture as tpc
print(json.dumps({"demo": tsd._src_sha(), "prt": tpc._src_sha()}))
"""
        proc = _probe(src_dir, code)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    baseline = _digests()

    for name in sorted(PRT_EXPECTED):
        member = src_dir / f"{name}.py"
        original = member.read_bytes()
        try:
            member.write_bytes(original + b"\n# t1-s1-isolated-edit\n")
            edited = _digests()
        finally:
            member.write_bytes(original)

        if name in DEMO_EXPECTED:
            assert edited["demo"] != baseline["demo"], (
                f"editing {name}.py (copy) did not move the demo closure digest")
        assert edited["prt"] != baseline["prt"], (
            f"editing {name}.py (copy) did not move the PRT closure digest")

    # the restored copy reproduces the baseline exactly
    assert _digests() == baseline


@pytest.mark.slow
def test_prt_flow_identity_and_outer_identity_both_move(tmp_path, monkeypatch):
    """PRT consumes `_src_sha()` TWICE: `_flow_params` (`:404`/`:417`, the FLOW
    identity that names `gwf_<hash>/`) and the outer `build_prt_capture` params
    dict (`:985`, the CAPTURE-cache identity that names `prtcapture_cache_<hash>.npz`).
    Both must respond to the same source-fingerprint change."""
    # --- consumer 1: `_flow_params` is pure / solve-free -----------------
    refine_radii = tpc.build_prt_capture.__kwdefaults__["refine_radii"]
    base_flow_params = tpc._flow_params(TRACK_DAYS, refine_radii)
    assert base_flow_params["src_sha"] == tpc._src_sha()

    monkeypatch.setattr(tpc, "_src_sha", lambda: "deadbeefdeadbeef")
    patched_flow_params = tpc._flow_params(TRACK_DAYS, refine_radii)
    assert patched_flow_params["src_sha"] == "deadbeefdeadbeef"
    assert patched_flow_params != base_flow_params
    monkeypatch.undo()

    # --- consumer 2: the outer cache identity in `build_prt_capture` -----
    # (real, small solve: no shortcut exists that reaches `cache_hash` without
    # running the function body, and `test_module_source_change_busts_cache`
    # already establishes that pattern is the right one for this module.)
    ws = tmp_path / "prt_ws_identity"
    tpc.build_prt_capture(n_particles=32, release_radius_m=FOOTPRINT_RADIUS_M,
                          track_days=TRACK_DAYS, case_ws=ws, force=True)
    before_gwf = set(ws.glob("gwf_*"))
    before_cache = set(ws.glob("prtcapture_cache_*.npz"))
    assert len(before_gwf) == 1 and len(before_cache) == 1

    monkeypatch.setattr(tpc, "_src_sha", lambda: "deadbeefdeadbeef")
    tpc.build_prt_capture(n_particles=32, release_radius_m=FOOTPRINT_RADIUS_M,
                          track_days=TRACK_DAYS, case_ws=ws, force=False)
    after_gwf = set(ws.glob("gwf_*"))
    after_cache = set(ws.glob("prtcapture_cache_*.npz"))

    assert after_gwf != before_gwf and len(after_gwf) == 2, (
        "the FLOW identity (_flow_params, consumer 1) did not respond: no new "
        "gwf_<hash>/ workspace appeared beside the old one")
    assert after_cache != before_cache and len(after_cache) == 2, (
        "the OUTER capture-cache identity (consumer 2) did not respond: no new "
        "prtcapture_cache_<hash>.npz appeared beside the old one")
