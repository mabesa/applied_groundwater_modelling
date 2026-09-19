"""
End-to-end "rerun from the submission ZIP" test for the scratch workflow.

The promise made to TAs is: *the scratch analysis reruns from the submission ZIP
alone* — no course repo, no FloPy, no heavy model workspace. This test proves that
mechanically:

1. Build a tiny synthetic ``exports/`` bundle (GPKG / CSV / JSON) — the kind of
   thing the steward notebook produces, but hand-made so no model is needed.
2. Copy the template-local ``scratch_io.py`` next to it, exactly as it would sit
   inside a group folder.
3. Zip it, extract the ZIP into a fresh temporary directory (simulating a TA on a
   clean machine), and
4. Run the full analysis pipeline **in a clean subprocess** (fresh interpreter, so
   ``flopy`` is guaranteed absent from ``sys.modules``) using only ``scratch_io``.

It is deliberately independent of the real heavy model workspace, so it is stable
in CI. It skips cleanly if the environment cannot write GeoPackages.

Run with:  uv run pytest _SUPPORT/tests/test_scratch_zip_rerun.py -v
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import Polygon

REPO_ROOT = Path(__file__).resolve().parents[2]


def _schema_version() -> str:
    """Read it from the module rather than hardcoding — a literal here silently
    drifts from scratch_io on the next bump."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('sio_ver', SCRATCH_IO_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SCHEMA_VERSION
SCRATCH_IO_PATH = REPO_ROOT / "PROJECT" / "workspace" / "template" / "scratch_io.py"


def _square(x0, y0, size=5.0):
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)])


def _build_exports(ex: Path) -> None:
    ex.mkdir(parents=True, exist_ok=True)
    for name, heads in (
        ("flow_heads_sub_base.gpkg", [100.0, 100.0]),
        ("flow_heads_sub_wells.gpkg", [99.0, 100.0]),
    ):
        gpd.GeoDataFrame(
            {"cellid": ["0_0", "0_1"], "row": [0, 0], "col": [0, 1], "head_m": heads},
            geometry=[_square(2683000, 1248000), _square(2683005, 1248000)],
            crs="EPSG:2056",
        ).to_file(ex / name, driver="GPKG")

    pd.DataFrame(
        {
            "model": ["sub_base", "sub_wells"],
            "term": ["RIVER_LEAKAGE", "RIVER_LEAKAGE"],
            "flow_in_m3_d": [200.0, 350.0],
            "flow_out_m3_d": [150.0, 100.0],
        }
    ).to_csv(ex / "flow_budget_summary.csv", index=False)

    with open(ex / "run_info.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "schema_version": _schema_version(),
                "group_number": 0,
                "crs": "EPSG:2056",
                "exports": {"flow_heads_sub_base.gpkg": {"present": True}},
            },
            fh,
        )


# A self-contained driver run in a CLEAN interpreter against the extracted ZIP.
_DRIVER = """
import sys
from pathlib import Path

group_dir = Path(sys.argv[1])
sys.path.insert(0, str(group_dir))          # scratch_io.py sits in the group folder

assert "flopy" not in sys.modules, "flopy leaked before import"
import scratch_io

scratch_io.assert_no_flopy()
ex = scratch_io.find_exports(start=group_dir)
info = scratch_io.load_run_info(ex)
assert scratch_io.check_schema(info)

base = scratch_io.load_heads_gpkg("base", ex)
wells = scratch_io.load_heads_gpkg("wells", ex)
dd = scratch_io.compute_drawdown(base, wells)
area = scratch_io.affected_area(dd, threshold=0.5)
assert abs(area - 25.0) < 1e-6, f"affected area {area} != 25"

budget = scratch_io.load_budget_summary(ex)
riv = scratch_io.river_exchange(budget)
assert not riv.empty

# flopy must never have been pulled in by any of the above.
assert "flopy" not in sys.modules, "flopy leaked during analysis"
assert "pyemu" not in sys.modules, "pyemu leaked during analysis"
scratch_io.assert_no_flopy()
print("SCRATCH_ZIP_RERUN_OK")
"""


def test_scratch_reruns_from_zip(tmp_path):
    # 1. author bundle in a group folder + copy the template-local reader in.
    group_dir = tmp_path / "authoring" / "group_test"
    try:
        _build_exports(group_dir / "exports")
    except Exception as exc:  # pragma: no cover - environment without GPKG writer
        pytest.skip(f"cannot write GeoPackage in this environment: {exc}")
    shutil.copy2(SCRATCH_IO_PATH, group_dir / "scratch_io.py")

    # 2. zip the group folder (what the student uploads).
    zip_path = tmp_path / "submission_group_test.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in group_dir.rglob("*"):
            zf.write(path, path.relative_to(group_dir.parent))

    # 3. extract into a pristine location (a TA on a clean machine).
    extract_root = tmp_path / "ta_machine"
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_root)
    extracted_group = extract_root / "group_test"
    assert (extracted_group / "scratch_io.py").is_file()
    assert (extracted_group / "exports" / "run_info.json").is_file()

    # 4. run the analysis in a clean subprocess (guaranteed flopy-free interpreter).
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(driver), str(extracted_group)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"scratch rerun failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "SCRATCH_ZIP_RERUN_OK" in result.stdout


# =============================================================================
# The submission checker — PROJECT/workspace/check_submission_zip.py
#
# The wrong-group failure ships a ZIP that is complete, internally consistent
# and fully rerunnable, for a different concession, contaminant and threshold.
# It has happened twice. The scratch notebook catches it, but only behind a
# kernel restart, so it gets skipped; this is the cheap version.
#
# These tests RUN THE SHIPPED SCRIPT. A test that re-implemented its logic
# would be two files agreeing with nothing checking — the defect class
# test_export_contract.py exists for.
# =============================================================================
CHECKER = REPO_ROOT / "PROJECT" / "workspace" / "check_submission_zip.py"

_REQUIRED_EXPORTS = (
    "run_info.json", "flow_heads_sub_base.gpkg", "flow_heads_sub_wells.gpkg",
    "flow_heads_sub_scenario.gpkg", "flow_budget_summary.csv",
    "transport_breakthrough.csv", "transport_meta.json", "pathlines_summary.csv",
)


def _make_submission_zip(tmp_path, folder, bundle_group, config_group, complete=True):
    """A minimal but structurally real submission ZIP."""
    root = tmp_path / f"src_{folder}_{bundle_group}_{config_group}_{int(complete)}"
    grp = root / folder
    (grp / "exports").mkdir(parents=True, exist_ok=True)
    for name in _REQUIRED_EXPORTS:
        (grp / "exports" / name).write_text("x")
    (grp / "exports" / "run_info.json").write_text(json.dumps(
        {"schema_version": "2.0", "group_number": bundle_group,
         "crs": "EPSG:2056", "exports": [], "missing_required": []}))
    (grp / "case_config.yaml").write_text(
        f"group:\n  number: {config_group}\n  authors:\n    - A\n\nmodel:\n  number: 999\n")
    if complete:
        # everything PROJECT/workspace/README.md marks required in the group root
        for name in ("report.pdf", "presentation.pdf", "SUBMISSION_README.md",
                     "case_config_transport.yaml", "case_study_flow_group_0.ipynb",
                     "case_study_transport_group_0.ipynb",
                     "steward_export_lightweight.ipynb",
                     "scratch_ana.ipynb", "scratch_io.py"):
            (grp / name).write_text("x")
        for sub, fname in (("figures", "cardA.png"), ("tables", "cardA.csv")):
            (grp / sub).mkdir(exist_ok=True)
            (grp / sub / fname).write_text("x")
    zip_path = tmp_path / f"{folder}_{bundle_group}_{config_group}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if path.is_dir():
                # real `zip -r` stores directory entries; without them the "count
                # files, not entries" behaviour cannot be exercised at all
                zf.writestr(f"{rel}/", "")
            else:
                zf.write(path, rel)
    return zip_path


def _run_checker(zip_path):
    return subprocess.run(
        [sys.executable, str(CHECKER), str(zip_path)],
        capture_output=True, text=True,
    )


def test_checker_is_shipped_and_uses_only_the_standard_library():
    """It must run in a bare Hub terminal where `python` is not the kernel, so it
    cannot import scratch_io (which pulls in geopandas to read a JSON file) nor
    anything else third-party."""
    assert CHECKER.is_file(), f"{CHECKER} is missing but README step 5 names it"
    roots = set()
    for node in ast.walk(ast.parse(CHECKER.read_text())):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    # Ask Python what the standard library is, rather than keeping a hand-list that
    # fires on a legitimate new stdlib import and tempts the next person to widen it
    # without thinking.
    stdlib = set(sys.stdlib_module_names) | {"__future__"}
    outside = sorted(roots - stdlib)
    assert not outside, (
        f"the checker imports non-stdlib modules {outside}. It must run in a bare Hub "
        f"terminal where the notebook kernel's packages are absent."
    )


def test_checker_passes_a_consistent_submission(tmp_path):
    zip_path = _make_submission_zip(tmp_path, "group_05", 5, 5)
    r = _run_checker(zip_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout
    # the summary note must state the group, and count FILES not directory entries
    assert "group 5" in r.stdout
    with zipfile.ZipFile(zip_path) as zf:
        n_files = sum(1 for n in zf.namelist() if not n.endswith("/"))
        n_entries = len(zf.namelist())
    assert n_entries > n_files, "fixture must contain directory entries for this to mean anything"
    assert f"{n_files} files" in r.stdout, r.stdout


def test_checker_catches_a_bundle_from_another_group(tmp_path):
    """The Hub failure: group_05/ holding a group-0 bundle."""
    r = _run_checker(_make_submission_zip(tmp_path, "group_05", 0, 0))
    assert r.returncode == 1, r.stdout
    assert "NOT ONE GROUP'S WORK" in r.stdout
    assert "do not rename" in r.stdout.lower() or "Renaming the" in r.stdout


def test_checker_still_catches_it_after_renaming_the_folder(tmp_path):
    """Renaming the folder is the obvious way to silence a folder-vs-bundle check,
    and it submits the wrong group's work. The config is the third source that
    makes that impossible."""
    r = _run_checker(_make_submission_zip(tmp_path, "group_00", 0, 5))
    assert r.returncode == 1, r.stdout
    assert "NOT ONE GROUP'S WORK" in r.stdout


def test_checker_never_reports_ok_when_it_could_not_check(tmp_path):
    """Fail-open is fine; claiming OK about an unchecked thing is not."""
    r = _run_checker(_make_submission_zip(tmp_path, "submission", 5, 5))
    assert r.returncode == 2, r.stdout
    assert "NOT CHECKED" in r.stdout
    assert "\nOK" not in r.stdout


def test_checker_reports_missing_required_files(tmp_path):
    r = _run_checker(_make_submission_zip(tmp_path, "group_05", 5, 5, complete=False))
    assert r.returncode == 1
    for expected in ("report.pdf", "presentation.pdf", "scratch_io.py"):
        assert expected in r.stdout


def test_readme_command_actually_resolves():
    """Assert the WHOLE command, not just the filename.

    A substring check on the filename passed while the README said
    `python ../check_submission_zip.py` -- which resolves to PROJECT/, where the
    script is not. The step errored on first use, which is the step students skip.
    """
    readme_path = REPO_ROOT / "PROJECT" / "workspace" / "README.md"
    readme = readme_path.read_text()
    assert "python3 check_submission_zip.py" in readme, (
        "README does not name the checker command in its runnable form"
    )
    # step 4 leaves the student in PROJECT/workspace; the path must resolve from there
    assert (readme_path.parent / "check_submission_zip.py").is_file()
    for bad in ("python ../check_submission_zip", "python check_submission_zip"):
        assert bad not in readme, f"README still shows a non-resolving form: {bad!r}"


def test_checker_tolerates_macosx_junk(tmp_path):
    """Finder's Compress adds __MACOSX/. That is harmless, not a reason to tell the
    student they zipped from the wrong place."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    noisy = tmp_path / "noisy.zip"
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(noisy, "w") as b:
        for item in a.infolist():
            b.writestr(item, a.read(item.filename))
        b.writestr("__MACOSX/._group_05", "junk")
    r = _run_checker(noisy)
    assert r.returncode == 0, r.stdout
    assert "__MACOSX" in r.stdout          # said out loud, not silently ignored
    assert "INSIDE the group folder" not in r.stdout


def test_checker_does_not_crash_on_a_hand_edited_run_info(tmp_path):
    """Editing run_info.json to silence a mismatch is the wrong fix this checker
    deters -- so that path must give a message, not a traceback."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    edited = tmp_path / "edited.zip"
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(edited, "w") as b:
        for item in a.infolist():
            data = a.read(item.filename)
            if item.filename.endswith("exports/run_info.json"):
                blob = json.loads(data)
                blob["group_number"] = "5"          # a string, not an int
                data = json.dumps(blob).encode()
            b.writestr(item, data)
    r = _run_checker(edited)
    assert "Traceback" not in r.stderr, r.stderr
    # pin the MEANING, not just the absence of a crash: "5" must still be read as 5
    # and pass. Asserting only returncode in (0,1,2) would accept the coercion being
    # present but ineffective, silently degrading this to "could not read".
    assert r.returncode == 0, r.stdout
    assert "OK" in r.stdout


def test_checker_rejects_a_folder_argument(tmp_path):
    """Forgetting `.zip` while the folder sits right there."""
    d = tmp_path / "group_05"
    d.mkdir()
    r = _run_checker(d)
    assert r.returncode == 1
    assert "Traceback" not in r.stderr
    assert "is a folder" in r.stdout


def test_checker_rejects_an_empty_export(tmp_path):
    """A 0-byte export is present but useless."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    hollow = tmp_path / "hollow.zip"
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(hollow, "w") as b:
        for item in a.infolist():
            data = a.read(item.filename)
            if item.filename.endswith("flow_budget_summary.csv"):
                data = b""
            b.writestr(item, data)
    r = _run_checker(hollow)
    assert r.returncode == 1
    assert "empty (0 bytes)" in r.stdout


def test_checker_reports_a_bundle_that_declares_missing_exports(tmp_path):
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    incomplete = tmp_path / "declared.zip"
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(incomplete, "w") as b:
        for item in a.infolist():
            data = a.read(item.filename)
            if item.filename.endswith("exports/run_info.json"):
                blob = json.loads(data)
                blob["missing_required"] = ["pathlines_summary.csv"]
                data = json.dumps(blob).encode()
            b.writestr(item, data)
    r = _run_checker(incomplete)
    assert r.returncode == 1
    assert "pathlines_summary.csv" in r.stdout


def _rewrite_member(src_zip, tmp_path, name, transform, out="edited.zip"):
    """Copy a zip, replacing one member's bytes."""
    dst = tmp_path / out
    with zipfile.ZipFile(src_zip) as a, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as b:
        for item in a.infolist():
            data = a.read(item.filename)
            if item.filename.endswith(name):
                data = transform(data)
            b.writestr(item, data)
    return dst


def test_checker_catches_a_hand_edited_mismatching_group(tmp_path):
    """The gap nothing covered: editing run_info.json to a DIFFERENT group, as a
    string. It must still be caught, not silently dropped as unreadable."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)

    def to_string_zero(data):
        blob = json.loads(data)
        blob["group_number"] = "0"
        return json.dumps(blob).encode()

    r = _run_checker(_rewrite_member(src, tmp_path, "exports/run_info.json", to_string_zero))
    assert r.returncode == 1, r.stdout
    assert "NOT ONE GROUP'S WORK" in r.stdout


def test_checker_rejects_an_empty_report_pdf(tmp_path):
    """A failed print-to-PDF looks exactly like this, and it costs a mark."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    r = _run_checker(_rewrite_member(src, tmp_path, "report.pdf", lambda _: b""))
    assert r.returncode == 1, r.stdout
    assert "report.pdf is empty" in r.stdout


def test_checker_gives_a_message_not_a_traceback_on_an_unreadable_config(tmp_path):
    """A student who saves case_config.yaml in a non-UTF-8 editor."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    bad = _rewrite_member(src, tmp_path, "case_config.yaml",
                          lambda _: "group:\n  number: 5\n  authors:\n    - J\xfcrg\n".encode("latin-1"))
    r = _run_checker(bad)
    assert "Traceback" not in r.stderr, r.stderr
    assert r.returncode == 1
    assert "case_config.yaml" in r.stdout


def test_checker_names_which_group_source_it_could_not_read(tmp_path):
    """'only 2 of 3 sources' does not tell a student what to fix."""
    r = _run_checker(_make_submission_zip(tmp_path, "submission", 5, 5))
    assert r.returncode == 2
    skip = [l for l in r.stdout.splitlines() if "could not read a group number" in l]
    assert len(skip) == 1, r.stdout
    # it must name the one it could not read, NOT simply list all three
    assert "folder name" in skip[0]
    assert "case_config.yaml" not in skip[0]
    assert "run_info" not in skip[0]


def test_checker_handles_an_archive_that_is_only_junk(tmp_path):
    """Calling the whole archive 'harmless junk' and then blaming the student for
    zipping from the wrong place is the wrong-diagnosis class this replaced."""
    only_junk = tmp_path / "junk.zip"
    with zipfile.ZipFile(only_junk, "w") as zf:
        zf.writestr("__MACOSX/._x", "junk")
    r = _run_checker(only_junk)
    assert r.returncode == 1
    assert "no usable group folder" in r.stdout
    assert "harmless" not in r.stdout


def test_checker_note_does_not_assert_a_group_on_a_mismatch(tmp_path):
    """It used to print 'group 0' immediately above 'THIS IS NOT ONE GROUP'S WORK'."""
    r = _run_checker(_make_submission_zip(tmp_path, "group_05", 0, 0))
    assert r.returncode == 1
    assert not any(line.strip().startswith("group ") for line in r.stdout.splitlines())


def test_checker_survives_a_corrupt_compressed_member(tmp_path):
    """Every real submission zip is deflate-compressed, and `zlib.error` is NOT a
    RuntimeError -- so a corrupt member escaped the first version of this guard.

    The byte matters: corrupting the first byte of the deflate stream gives
    zlib.error ("invalid code lengths"), while a later byte still decompresses and
    gives BadZipFile ("Bad CRC-32"), which the guard already caught. A test aimed
    at the wrong byte passes whether or not zlib.error is handled -- this one was,
    until a mutation showed it could not fail.
    """
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    with zipfile.ZipFile(src) as zf:
        info = next(i for i in zf.infolist() if i.filename.endswith("run_info.json"))
        assert info.compress_type == zipfile.ZIP_DEFLATED, "fixture must be compressed"
    raw = bytearray(src.read_bytes())
    n = info.header_offset
    name_len = int.from_bytes(raw[n + 26:n + 28], "little")
    extra_len = int.from_bytes(raw[n + 28:n + 30], "little")
    raw[n + 30 + name_len + extra_len] ^= 0xFF      # first byte of the deflate stream

    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(bytes(raw))
    r = _run_checker(corrupt)
    assert "Traceback" not in r.stderr, r.stderr
    assert r.returncode == 1
    assert "could not read" in r.stdout.lower()


def test_checker_guards_the_run_info_read_too(tmp_path):
    """Only the config read was covered; deleting the run_info guard passed."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    bad = _rewrite_member(src, tmp_path, "exports/run_info.json",
                          lambda _: "ä".encode("latin-1") + b"{}", out="badenc.zip")
    r = _run_checker(bad)
    assert "Traceback" not in r.stderr, r.stderr
    assert r.returncode == 1
    assert "run_info.json" in r.stdout


@pytest.mark.parametrize("fname", ["presentation.pdf", "SUBMISSION_README.md", "scratch_io.py"])
def test_checker_rejects_other_empty_required_files(tmp_path, fname):
    """The 0-byte widening was pinned only for report.pdf."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    r = _run_checker(_rewrite_member(src, tmp_path, fname, lambda _: b"", out=f"e_{fname}.zip"))
    assert r.returncode == 1, r.stdout
    assert f"{fname} is empty" in r.stdout
    if not fname.endswith(".pdf"):
        assert "print-to-PDF" not in r.stdout


@pytest.mark.parametrize("missing_dir", ["figures", "tables"])
def test_checker_requires_figures_and_tables(tmp_path, missing_dir):
    """Both are marked required in PROJECT/workspace/README.md, and the report cites
    them. A ZIP without them used to pass as complete."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    stripped = tmp_path / f"no_{missing_dir}.zip"
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(stripped, "w", zipfile.ZIP_DEFLATED) as b:
        for item in a.infolist():
            if f"/{missing_dir}/" in item.filename or item.filename.endswith(f"/{missing_dir}/"):
                continue
            b.writestr(item, a.read(item.filename))
    r = _run_checker(stripped)
    assert r.returncode == 1, r.stdout
    assert f"{missing_dir}/ is missing or empty" in r.stdout


@pytest.mark.parametrize("fname", [
    "case_config_transport.yaml",
    "case_study_flow_group_0.ipynb",
    "case_study_transport_group_0.ipynb",
    "steward_export_lightweight.ipynb",
])
def test_checker_requires_the_provenance_files(tmp_path, fname):
    """The master notebooks, the export notebook and the transport config are all
    marked required. A ZIP missing all four once printed 'every required file is
    present'."""
    src = _make_submission_zip(tmp_path, "group_05", 5, 5)
    stripped = tmp_path / f"no_{fname}.zip"
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(stripped, "w", zipfile.ZIP_DEFLATED) as b:
        for item in a.infolist():
            if item.filename.endswith(f"/{fname}"):
                continue
            b.writestr(item, a.read(item.filename))
    r = _run_checker(stripped)
    assert r.returncode == 1, r.stdout
    assert fname in r.stdout
