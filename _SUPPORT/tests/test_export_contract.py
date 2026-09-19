"""
The PRODUCER <-> CONSUMER contract for the student ``exports/`` bundle.

Why this file exists
--------------------
``test_scratch_zip_rerun.py`` builds its bundle **by hand** ("hand-made so no
model is needed"), so the fixture is written to match ``scratch_io`` and can
never disagree with it. Before this file, **no test read
``steward_export_lightweight.ipynb`` at all** -- so nothing compared what the
steward WRITES against what ``scratch_io`` and the scratch cards READ.

That gap is why every one of these shipped undetected:

* the steward wrote ``time_d`` while ``scratch_io`` required ``time_days``
  (Card E raised ``ValueError`` -- it did not "skip cleanly");
* the steward wrote ``peak_mgL`` / ``t_peak_d`` while Card E read
  ``peak_mg_L`` / ``t_peak_days`` / ``t_exceedance_days`` (all ``None`` ->
  ``TypeError`` formatting ``None`` as ``.4g``);
* Card F read ``generated_utc`` / ``head_masking`` / ``package_versions`` /
  ``missing_optional``, none of which the steward emitted -- and still printed
  a submission-QA pass;
* ``pathlines_summary.csv`` had no producer anywhere in the repo, so Card B
  could never do anything.

These are all the SAME defect: two files agreeing about a name, with nothing
checking. This test is static -- it parses notebook source with ``ast`` and
runs no model -- so it is cheap enough to never be skipped.

Run with:  uv run pytest _SUPPORT/tests/test_export_contract.py -v
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "PROJECT" / "workspace" / "template"

STEWARD_NB = TEMPLATE / "steward_export_lightweight.ipynb"
SCRATCH_NB = TEMPLATE / "scratch_analysis_template.ipynb"
FLOW_NB = TEMPLATE / "case_study_flow_group_0.ipynb"
TRANSPORT_NB = TEMPLATE / "case_study_transport_group_0.ipynb"
SCRATCH_IO_PATH = TEMPLATE / "scratch_io.py"

#: Export filenames that legitimately have no producer in the shipped
#: notebooks. Adding a name here is a DELIBERATE statement that the artifact is
#: unreachable through the documented workflow -- so the card that consumes it
#: can never produce a deliverable. Keep this empty unless that is intended.
NO_PRODUCER: frozenset[str] = frozenset()


# =============================================================================
# Helpers -- parse notebook code cells with ast
# =============================================================================
def _code_cells(nb_path: Path) -> list[str]:
    nb = json.loads(nb_path.read_text())
    return [
        "".join(c["source"])
        for c in nb["cells"]
        if c.get("cell_type") == "code"
    ]


def _source(nb_path: Path) -> str:
    return "\n".join(_code_cells(nb_path))


def _trees(nb_path: Path) -> list[ast.AST]:
    """Parse each code cell independently; skip cells that will not parse
    (IPython magics etc.) rather than failing the whole test."""
    out = []
    for cell in _code_cells(nb_path):
        try:
            out.append(ast.parse(cell))
        except SyntaxError:
            continue
    return out


def _dict_keys_assigned_to(nb_path: Path, varname: str) -> set[str]:
    """Keys of a dict literal assigned to ``varname`` anywhere in the notebook."""
    keys: set[str] = set()
    for tree in _trees(nb_path):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == varname:
                    for k in node.value.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            keys.add(k.value)
    return keys


def _dataframe_columns_written_to(nb_path: Path, filename: str) -> set[str]:
    """Columns of ``pd.DataFrame({...}).to_csv(<...filename...>)``.

    Matches the whole expression, so it cannot be fooled by an unrelated
    DataFrame elsewhere in the notebook.
    """
    cols: set[str] = set()
    for tree in _trees(nb_path):
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "to_csv"
            ):
                continue
            # does any argument mention the target filename?
            mentions = any(
                isinstance(a, ast.Constant)
                and isinstance(a.value, str)
                and filename in a.value
                for a in ast.walk(node)
            )
            if not mentions:
                continue
            inner = node.func.value  # the object .to_csv was called on
            if (
                isinstance(inner, ast.Call)
                and inner.args
                and isinstance(inner.args[0], ast.Dict)
            ):
                for k in inner.args[0].keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        cols.add(k.value)
    return cols


def _get_calls_on(nb_path: Path, receiver: str) -> set[str]:
    """String literals passed to ``<receiver>.get('...')``."""
    found: set[str] = set()
    for tree in _trees(nb_path):
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == receiver
                and node.args
            ):
                continue
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                found.add(a0.value)
    return found


@pytest.fixture(scope="module")
def scratch_io():
    spec = importlib.util.spec_from_file_location("scratch_io_ct", SCRATCH_IO_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# =============================================================================
# 1. The transport breakthrough CSV -- columns
# =============================================================================
def test_breakthrough_csv_columns_match_the_reader(scratch_io):
    """The steward's CSV columns must satisfy what ``scratch_io`` requires.

    ``load_transport_breakthrough`` raises ``ValueError`` on a missing column,
    so a mismatch is a HARD failure of Card E, not a clean skip.
    """
    written = _dataframe_columns_written_to(STEWARD_NB, "transport_breakthrough.csv")
    assert written, "no pd.DataFrame(...).to_csv('transport_breakthrough.csv') found"

    required = {"time_days", "concentration_mg_L"}
    missing = required - written
    assert not missing, (
        f"steward writes {sorted(written)} to transport_breakthrough.csv but "
        f"scratch_io.load_transport_breakthrough requires {sorted(required)}; "
        f"missing {sorted(missing)} -> Card E raises ValueError"
    )


# =============================================================================
# 2. transport_meta.json -- producer vs Card E
# =============================================================================
def test_transport_meta_keys_cover_what_card_e_reads():
    """Every ``meta.get('x')`` in the scratch notebook must be a key the
    steward actually writes, or the card formats ``None`` and crashes."""
    written = _dict_keys_assigned_to(STEWARD_NB, "meta")
    assert written, "no `meta = {...}` dict literal found in the steward notebook"

    read = _get_calls_on(SCRATCH_NB, "meta")
    assert read, "no `meta.get(...)` calls found in the scratch notebook"

    unmet = read - written
    assert not unmet, (
        f"Card E reads {sorted(unmet)} from transport_meta.json but the steward "
        f"never writes them (it writes {sorted(written)})"
    )


# =============================================================================
# 3. run_info.json -- producer vs Card F
# =============================================================================
def test_run_info_keys_cover_what_card_f_reads():
    written = _dict_keys_assigned_to(STEWARD_NB, "run_info")
    assert written, "no `run_info = {...}` dict literal found in the steward notebook"

    read = _get_calls_on(SCRATCH_NB, "info")
    assert read, "no `info.get(...)` calls found in the scratch notebook"

    unmet = read - written
    assert not unmet, (
        f"Card F reads {sorted(unmet)} from run_info.json but the steward never "
        f"writes them (it writes {sorted(written)}); the card prints None and "
        f"still reads as a QA pass"
    )


def test_run_info_still_satisfies_the_reader_schema(scratch_io):
    """Renaming a run_info key must not drop one ``check_schema`` requires."""
    written = _dict_keys_assigned_to(STEWARD_NB, "run_info")
    required = {"schema_version", "group_number", "crs", "exports"}
    assert required <= written, (
        f"run_info is missing scratch_io.check_schema requirements: "
        f"{sorted(required - written)}"
    )


# =============================================================================
# 4. Every declared export has a producer
# =============================================================================
def test_every_declared_export_has_a_producer(scratch_io):
    """A filename in ``scratch_io.EXPORT_FILES`` that no notebook writes is an
    artifact students can never produce -- and a card that can never deliver."""
    steward_src = _source(STEWARD_NB)
    declared = set(scratch_io.EXPORT_FILES.values())

    orphans = {
        name
        for name in declared
        if name not in steward_src and name not in NO_PRODUCER
    }
    assert not orphans, (
        f"declared in scratch_io.EXPORT_FILES but written by no shipped "
        f"notebook: {sorted(orphans)}. Either produce them, retire them, or "
        f"list them in NO_PRODUCER with a reason."
    )


# =============================================================================
# 5. The steward must resolve _SUPPORT the way the masters do
# =============================================================================
def test_steward_resolves_support_like_the_master_notebooks():
    """A hardcoded ``~/applied_groundwater_modelling`` misses the Hub checkout
    (``~/applied_groundwater_modelling.git``). The import then fails, the broad
    handler reports "transport outputs omitted (both are optional)", and the
    bundle silently ships without transport.
    """
    steward = _source(STEWARD_NB)
    assert "os.path.expanduser('~/applied_groundwater_modelling/" not in steward, (
        "steward hardcodes an absolute home path for _SUPPORT/src; the Hub "
        "checkout is ~/applied_groundwater_modelling.git, so this silently "
        "costs the group its transport export"
    )

    relative = "../../../_SUPPORT/src"
    for master in (FLOW_NB, TRANSPORT_NB):
        assert relative in _source(master), (
            f"{master.name} no longer uses {relative}; this test's premise "
            f"(the masters are the reference) needs revisiting"
        )
    assert relative in steward, (
        f"steward should resolve _SUPPORT/src as {relative}, the same relative "
        f"form both master notebooks use"
    )


# =============================================================================
# 6. The group-folder guard must actually be WIRED IN
#
# scratch_io.assert_group_folder_matches is unit-tested, but nothing checked that
# the notebooks still CALL it -- delete a call line and every test stayed green.
# That is the same "two files agreeing with nothing checking" pattern this file
# was written for. A student who copies template/ to group_07/ and leaves
# group.number at 0 silently runs the demo scenario; it has happened twice.
# =============================================================================
GUARD = "assert_group_folder_matches"

#: Every notebook that resolves a group and then acts on it.
GUARDED_NOTEBOOKS = (FLOW_NB, TRANSPORT_NB, STEWARD_NB, SCRATCH_NB)


def _makes_a_real_call_to(nb_path, name):
    """True only for an executable call -- not a mention in a comment or string.

    A substring check passed when the call was commented out, which is the same
    can-never-fail shape this file exists to catch.
    """
    for tree in _trees(nb_path):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if (isinstance(fn, ast.Attribute) and fn.attr == name) or (
                isinstance(fn, ast.Name) and fn.id == name
            ):
                return True
    return False


@pytest.mark.parametrize("nb_path", GUARDED_NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_calls_the_group_folder_guard(nb_path):
    assert _makes_a_real_call_to(nb_path, GUARD), (
        f"{nb_path.name} no longer calls scratch_io.{GUARD}(). Without it, running "
        f"in group_07/ with group.number still 0 silently produces a complete, "
        f"valid-looking submission for the WRONG group."
    )


def test_the_guard_exists_and_is_callable(scratch_io):
    """The notebooks call it by name; this is the other half of that contract."""
    assert callable(getattr(scratch_io, GUARD, None)), (
        f"scratch_io.{GUARD} is missing, but {len(GUARDED_NOTEBOOKS)} notebooks call it"
    )


def test_flow_master_guards_the_effective_group_not_the_configured_one():
    """The flow master lets AGM_GROUP_ID override the config; the guard must run
    AFTER that, or the gates' override would be checked against the wrong number."""
    src = _source(FLOW_NB)
    # index the ASSIGNMENT, not the first mention: AGM_GROUP_ID appears earlier in
    # an explanatory comment, and indexing that made this test pass even with the
    # guard moved above the override -- the exact defect it names.
    override = src.index('os.environ.get("AGM_GROUP_ID"')
    guard = src.index(GUARD)
    assert override < guard, (
        "the group-folder guard runs BEFORE the AGM_GROUP_ID override in the flow "
        "master, so it would check the configured group rather than the effective one"
    )
