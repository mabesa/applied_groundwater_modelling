from __future__ import annotations

import io
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))

import check_internal_links


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
