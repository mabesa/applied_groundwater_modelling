from __future__ import annotations

import io
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))

import check_internal_links
import transport_claim_inventory as tci


REPO_ROOT = Path(__file__).resolve().parents[2]


def tracked_files():
    return check_internal_links.list_tracked_files(REPO_ROOT)


def test_real_start_here_links_resolve():
    tracked = tracked_files()
    source = REPO_ROOT / "PROJECT" / "0_start_here.ipynb"

    assert (
        check_internal_links.validate_link(
            REPO_ROOT,
            tracked,
            source,
            "flow/01f_model_goal.ipynb",
        )
        is None
    )
    assert (
        check_internal_links.validate_link(
            REPO_ROOT,
            tracked,
            source,
            "transport/01t_model_goal.ipynb",
        )
        is None
    )


def test_real_cross_tree_theory_link_resolves():
    tracked = tracked_files()
    source = REPO_ROOT / "PROJECT" / "flow" / "03f_modflow_fundamentals.ipynb"

    assert (
        check_internal_links.validate_link(
            REPO_ROOT,
            tracked,
            source,
            "../../THEORY/_demos/explore_porosity_and_REV.ipynb",
        )
        is None
    )


def test_readme_links_resolve():
    tracked = tracked_files()
    source = REPO_ROOT / "README.md"

    assert (
        check_internal_links.validate_link(
            REPO_ROOT,
            tracked,
            source,
            "DOCUMENTATION/DEVELOPMENT.md",
        )
        is None
    )
    assert (
        check_internal_links.validate_link(
            REPO_ROOT,
            tracked,
            source,
            "_SUPPORT/static/figures/0_readme/Groundwater_course.jpg",
        )
        is None
    )


def test_tooling_markdown_is_scanned():
    tracked = {
        ".claude/context.md",
        ".github/pull_request_template.md",
        "DOCUMENTATION/README.md",
        "PROJECT/workspace/README.md",
        "README.md",
        "notes.txt",
    }

    assert check_internal_links.source_files(tracked) == [
        ".claude/context.md",
        ".github/pull_request_template.md",
        "DOCUMENTATION/README.md",
        "PROJECT/workspace/README.md",
        "README.md",
    ]


def test_synthetic_broken_target_fails(tmp_path):
    (tmp_path / "doc.md").write_text("[bad](missing.ipynb)\n", encoding="utf-8")
    output = io.StringIO()

    exit_code = check_internal_links.run(
        tmp_path,
        tracked_files={"doc.md"},
        out=output,
    )

    assert exit_code == 1
    assert (
        'doc.md:1: broken link "missing.ipynb" -> target does not exist'
        in output.getvalue()
    )


def test_url_encoded_path_resolves(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    (tmp_path / "doc.md").write_text(
        "[x](folder/My%20Notebook.ipynb)\n",
        encoding="utf-8",
    )
    (folder / "My Notebook.ipynb").write_text("{}", encoding="utf-8")

    output = io.StringIO()
    exit_code = check_internal_links.run(
        tmp_path,
        tracked_files={"doc.md", "folder/My Notebook.ipynb"},
        out=output,
    )

    assert exit_code == 0
    assert "0 failures." in output.getvalue()


def test_path_traversal_containment_fails(tmp_path):
    (tmp_path / "doc.md").write_text("[bad](../../../etc/passwd)\n", encoding="utf-8")
    output = io.StringIO()

    exit_code = check_internal_links.run(
        tmp_path,
        tracked_files={"doc.md"},
        out=output,
    )

    assert exit_code == 1
    assert (
        'doc.md:1: broken link "../../../etc/passwd" -> path escapes repo root'
        in output.getvalue()
    )


def test_fenced_markdown_link_is_ignored(tmp_path):
    (tmp_path / "doc.md").write_text(
        "```markdown\n"
        "[fake](inside-fence.ipynb)\n"
        "```\n"
        "[real](outside-fence.ipynb)\n",
        encoding="utf-8",
    )
    output = io.StringIO()

    exit_code = check_internal_links.run(
        tmp_path,
        tracked_files={"doc.md"},
        out=output,
    )

    assert exit_code == 1
    assert (
        'doc.md:4: broken link "outside-fence.ipynb" -> target does not exist'
        in output.getvalue()
    )
    assert "inside-fence.ipynb" not in output.getvalue()


def test_fenced_html_link_is_ignored(tmp_path):
    (tmp_path / "doc.md").write_text(
        "```html\n"
        '<a href="missing.ipynb">missing</a>\n'
        "```\n",
        encoding="utf-8",
    )
    output = io.StringIO()

    exit_code = check_internal_links.run(
        tmp_path,
        tracked_files={"doc.md"},
        out=output,
    )

    assert exit_code == 0
    assert "missing.ipynb" not in output.getvalue()
    assert "0 failures." in output.getvalue()


# ---------------------------------------------------------------------------
# _escape_table_snippet (transport_claim_inventory.py) -- ci_internal_links_fix
# plan S6.2. Quoted notebook prose is rendered into
# DOCUMENTATION/contracts/T0_2a_claim_inventory.md as evidence, not
# navigation; these tests pin that the escaper keeps this cross-subsystem
# contract: check_internal_links.extract_links() must never see a link
# formed out of quoted matched_text.
# ---------------------------------------------------------------------------


def _fixture_candidate(matched_text, claim_type=("causal",), path="fixture_module.py"):
    return {
        "path": path,
        "detector": "r_and_n",
        "checkpoint_key": None,
        "claim_type": list(claim_type),
        "matched_text": matched_text,
        "source_kind": "python_module",
        "cell_id_synthetic": False,
        "cell_index": None,
        "cell_id": None,
        "dict_name": None,
        "scope_symbol": path,
        "line_number": 1,
    }


def _fixture_report(candidates):
    return {
        "coverage": {
            "files_visited": 1,
            "notebook_cells_visited": 0,
            "tasks_data_dict_entries_visited": 0,
            "tasks_data_dict_entries_skipped_non_transport": 0,
            "python_module_files_visited": 1,
            "candidates_found": len(candidates),
            "claim_assignments_found": len(candidates),
            "candidates_classified": len(candidates),
            "candidates_rejected": sum(
                1 for c in candidates if c["claim_type"] == ["not_a_claim"]
            ),
            "candidates_unclassified": 0,
            "by_detector": {},
            "by_claim_type": {},
        },
        "excluded_dicts": [],
        "gate": {"ok": True, "unclassified_ids": [], "orphan_ids": []},
        "candidates": candidates,
    }


def test_render_markdown_link_bearing_report_yields_zero_extracted_links():
    """The cross-subsystem guard. Pins the BEHAVIOUR, not the escape

    spelling -- a regression back to v1's bare ``[`` -> ``\\[`` would fail
    this test, since MARKDOWN_LINK_RE is not backslash-escape-aware.
    Exercises both render_markdown call sites: a rejected (not_a_claim)
    candidate (the "Rejected" table, :1242) and an accepted one (the
    by-notebook table, :1261) -- the by-notebook loop iterates every
    candidate including rejected ones, so a single rejected+link-bearing
    candidate alone already covers both tables.
    """
    candidates = [
        _fixture_candidate(
            "See [03t](03t_modflow_transport.ipynb) for the referenced result.",
            claim_type=("causal",),
        ),
        _fixture_candidate(
            "Rejected line quoting a [note](../notes.md) link.",
            claim_type=("not_a_claim",),
        ),
    ]
    rendered = tci.render_markdown(_fixture_report(candidates))

    assert check_internal_links.extract_links(rendered) == []


def test_escape_table_snippet_pipe_still_escaped():
    assert tci._escape_table_snippet("a | b") == "a \\| b"


def test_escape_table_snippet_link_syntax_neutralized():
    assert tci._escape_table_snippet("[text](target.md)") == "[text]\\(target.md)"


def test_escape_table_snippet_preserves_math_code_and_html_details():
    text = (
        "The rule is $C \\le C_0$ and `peak <= 0.0` inside "
        "<details><summary>note</summary></details>."
    )
    assert tci._escape_table_snippet(text) == text


def test_escape_table_snippet_html_anchor_and_img_neutralized():
    assert (
        tci._escape_table_snippet('<a href="x">x</a>')
        == '&lt;a href="x">x&lt;/a>'
    )
    assert (
        tci._escape_table_snippet('<img src="y.png">')
        == '&lt;img src="y.png">'
    )


# The four S4.1 hazards, pinned as known-behaviour tests. All measured as
# zero occurrences in today's 427-candidate corpus (plan S4.1); these tests
# document what would happen if one appeared, not a claim that it is safe.


def test_escape_table_snippet_hazard_code_span_link_sequence_still_escaped():
    # Hazard: "](" inside a code span or $math$ -- the escaper is not
    # code-span-aware, so the backslash would show up literally.
    text = "See `foo](bar)` for detail"
    assert tci._escape_table_snippet(text) == "See `foo]\\(bar)` for detail"


def test_escape_table_snippet_hazard_pre_escaped_paren_unchanged():
    # Hazard: a snippet already containing "]\(" -- no bare "](" substring
    # remains, so .replace is a no-op and the text passes through unchanged.
    text = "already escaped: x]\\(y"
    assert tci._escape_table_snippet(text) == text


def test_escape_table_snippet_hazard_pre_escaped_pipe_becomes_double_escaped():
    # Hazard: a pre-escaped "\|" in source -- the escaper does not detect
    # the existing backslash and doubles it.
    text = "value: a\\|b"
    assert tci._escape_table_snippet(text) == "value: a\\\\|b"


def test_escape_table_snippet_hazard_angle_destination_not_html_neutralized():
    # Hazard: "[a](<b>)" angle-bracket destination -- the link-forming "]("
    # is killed, but "<b>" is not "a"/"img" so it is left live as HTML.
    text = "[a](<b>)"
    assert tci._escape_table_snippet(text) == "[a]\\(<b>)"
