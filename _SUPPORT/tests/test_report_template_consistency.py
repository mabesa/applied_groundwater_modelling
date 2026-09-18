"""The three shipped report templates must offer the SAME skeleton.

Why this file exists
--------------------
``REPORT_BRIEF.md`` prescribes a report structure, and three interchangeable
templates implement it: ``report_template.md`` (the maintained source),
``report_template.tex`` (LaTeX/Overleaf) and ``report_template.docx`` (Word,
derived from the .md by ``_SUPPORT/src/scripts/build_report_template_docx.py``).

Parallel files that agree about a structure with nothing checking is the defect
class this repository keeps rediscovering. A student who picks the .tex must not
get a different set of sections from one who picks the .md, and the section list
is what the rubric marks against.

What an earlier version of this file got wrong, and why the tests below look the
way they do:

* the .docx was checked only for existence and ``st_size > 5_000`` -- replacing
  it with 6.8 kB of the string ``"NOT A DOCX AT ALL"`` passed the whole suite.
  It is now opened as a zip and its headings are read out of ``word/document.xml``;
* ``test_the_brief_s_required_structure_is_present`` never opened
  ``REPORT_BRIEF.md`` -- the "required" sections were hardcoded literals, so the
  brief could gain or rename a section and the templates would fall silently
  behind. It now parses the brief;
* only top-level sections were compared, so deleting
  ``\\subsection{What this model cannot tell you}`` from the .tex alone passed --
  silently costing LaTeX groups the claimable / not-claimable rule. Subsections
  are compared too;
* the 12-minute presentation limit was frozen nowhere, although the same file
  froze the page limits.

Regenerate the .docx after editing the .md (never by hand):

    uv run python _SUPPORT/src/scripts/build_report_template_docx.py

Run with:  uv run pytest _SUPPORT/tests/test_report_template_consistency.py -v
"""

from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "PROJECT" / "workspace" / "template"
WORKSPACE = REPO_ROOT / "PROJECT" / "workspace"

MD = TEMPLATE / "report_template.md"
TEX = TEMPLATE / "report_template.tex"
DOCX = TEMPLATE / "report_template.docx"
BRIEF = TEMPLATE / "REPORT_BRIEF.md"
BUILDER = REPO_ROOT / "_SUPPORT" / "src" / "scripts" / "build_report_template_docx.py"

#: Files that state the presentation length. All must agree -- including the
#: instructor guide: the brief promises students they WILL be stopped at 12 minutes,
#: so whoever runs the session has to know to hold a clock.
TIMED_FILES = (
    BRIEF,
    WORKSPACE / "README.md",
    TEMPLATE / "COLLABORATION.md",
    TEMPLATE / "SUBMISSION_README_TEMPLATE.md",
    REPO_ROOT / "DOCUMENTATION" / "INSTRUCTOR_GUIDE.md",
)

PRESENTATION_MINUTES = 12


def _normalise(title: str) -> str:
    """Strip numbering, placeholder markup and case so the formats compare."""
    t = title.strip()
    t = re.sub(r"^\d+(\.\d+)?\.?\s*", "", t)   # "4.2 Foo" / "1. Foo" -> "Foo"
    t = re.sub(r"^[A-Z]\.\s*", "", t)          # "A. Foo"             -> "Foo"
    t = t.replace("`", "").replace("<", "").replace(">", "").replace("*", "")
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def _md_headings(level: int) -> list[str]:
    marker = "#" * level
    pat = re.compile(rf"^{marker}\s+(?!#)(.*)$")
    return [_normalise(m.group(1)) for m in map(pat.match, MD.read_text().splitlines()) if m]


def _tex_headings(macro: str) -> list[str]:
    return [
        _normalise(m)
        for m in re.findall(rf"^\\{macro}\{{(.*?)\}}", TEX.read_text(), flags=re.M)
    ]


def _docx_paragraphs() -> list[tuple[str, str]]:
    """(style, text) for every paragraph in the .docx, via raw OOXML.

    Deliberately avoids python-docx: it is not a project dependency, and the
    point is to read what Word will actually show.
    """
    with zipfile.ZipFile(DOCX) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    out = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S):
        style = re.search(r'<w:pStyle w:val="([^"]+)"', para)
        text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, flags=re.S))
        # OOXML stores < and > as entities; a heading like "<The transport verdict>"
        # arrives as "&lt;The transport verdict&gt;" and would never match the source.
        out.append((style.group(1) if style else "", html.unescape(text)))
    return out


# =============================================================================
# 1. All three are shipped, and the .docx is a real Word file
# =============================================================================
def test_all_three_templates_and_the_builder_are_shipped():
    for path in (MD, TEX, DOCX, BUILDER):
        assert path.is_file(), f"{path.name} is missing"


def test_docx_is_a_valid_word_document():
    """Existence and size prove nothing -- 6.8 kB of junk once passed this file."""
    assert zipfile.is_zipfile(DOCX), (
        "report_template.docx is not even a zip archive, so it is not a .docx. "
        "Regenerate it: uv run python _SUPPORT/src/scripts/build_report_template_docx.py"
    )
    with zipfile.ZipFile(DOCX) as zf:
        names = set(zf.namelist())
    for required in ("word/document.xml", "[Content_Types].xml"):
        assert required in names, f"{DOCX.name} is missing {required}; it is not a valid .docx"


def test_docx_uses_real_heading_styles_not_bold_text():
    styles = {s for s, _ in _docx_paragraphs() if s.startswith("Heading")}
    assert styles, (
        "no Heading styles in report_template.docx -- the sections are formatted text, "
        "not a navigable Word document"
    )


# =============================================================================
# 2. The .docx actually matches the Markdown source it is derived from
# =============================================================================
def test_docx_carries_every_section_of_the_markdown_source():
    md_sections = set(_md_headings(2)) | set(_md_headings(3))
    docx_headings = {
        _normalise(text) for style, text in _docx_paragraphs() if style.startswith("Heading")
    }
    missing = md_sections - docx_headings
    assert not missing, (
        f"report_template.docx is stale: {sorted(missing)} exist in report_template.md "
        f"but not in the Word file. Regenerate it with "
        f"_SUPPORT/src/scripts/build_report_template_docx.py"
    )


def test_docx_still_carries_the_guidance_blocks():
    """pandoc silently drops HTML comments; Word users would get a bare skeleton.

    The guidance is therefore written as visible blockquotes in the .md. This
    test is what keeps it that way.
    """
    md_blocks = MD.read_text().count("**GUIDANCE")
    assert md_blocks >= 8, (
        f"report_template.md has only {md_blocks} guidance blocks -- if guidance moved "
        f"back into HTML comments it will vanish from the Word template AND from "
        f"Markdown Preview, which is how the workspace README tells students to read it"
    )
    docx_blocks = sum(1 for _, text in _docx_paragraphs() if "GUIDANCE" in text)
    assert docx_blocks >= md_blocks, (
        f"report_template.docx carries {docx_blocks} guidance blocks but the source has "
        f"{md_blocks}; Word users are missing instructions. Regenerate the .docx."
    )


# =============================================================================
# 3. The .md and .tex offer the same skeleton, sections AND subsections
# =============================================================================
def test_md_and_tex_offer_the_same_sections():
    md, tex = _md_headings(2), _tex_headings("section")
    assert md == tex, (
        "report_template.md and report_template.tex have drifted apart.\n"
        f"  .md : {md}\n  .tex: {tex}\n"
        "A student who picks one format must not get a different report skeleton."
    )


def test_md_and_tex_offer_the_same_subsections():
    """Deleting one \\subsection from the .tex alone used to pass.

    ``5.1 What this model cannot tell you`` carries the claimable /
    not-claimable rule the brief calls required content.
    """
    md, tex = _md_headings(3), _tex_headings("subsection")
    assert md == tex, (
        "report_template.md and report_template.tex subsections have drifted apart.\n"
        f"  .md : {md}\n  .tex: {tex}"
    )


# =============================================================================
# 4. The templates implement the structure the BRIEF actually prescribes
# =============================================================================
def _brief_required_sections() -> list[str]:
    """``###`` headings under the brief's '## Required structure'."""
    text = BRIEF.read_text()
    start = text.index("## Required structure")
    rest = text[start + len("## Required structure"):]
    end = rest.find("\n## ")
    block = rest if end == -1 else rest[:end]
    return [_normalise(m) for m in re.findall(r"^###\s+(.*)$", block, flags=re.M)]


def test_the_brief_prescribes_a_structure_at_all():
    required = _brief_required_sections()
    assert len(required) >= 7, (
        f"parsed only {len(required)} required sections out of REPORT_BRIEF.md "
        f"({required}); the parser and the brief have diverged, so the test below "
        f"would be checking nothing"
    )


def test_templates_implement_every_section_the_brief_requires():
    md = _md_headings(2)
    missing = [s for s in _brief_required_sections() if s not in md]
    assert not missing, (
        f"REPORT_BRIEF.md requires {missing}, which report_template.md does not offer; "
        f"students following the template would omit them"
    )


def test_templates_point_students_at_the_brief():
    for path in (MD, TEX):
        assert "REPORT_BRIEF.md" in path.read_text(), (
            f"{path.name} does not point at REPORT_BRIEF.md, which is where the purpose "
            f"and marking of each section live"
        )


# =============================================================================
# 5. Limits stated in more than one place must agree
# =============================================================================
def test_page_limits_are_stated_and_frozen():
    brief = BRIEF.read_text()
    assert "10 pages maximum" in brief
    assert "capped at 5 pages" in brief, (
        "REPORT_BRIEF.md no longer caps the appendix; an uncapped appendix makes the "
        "page limit meaningless"
    )
    for path in (MD, TEX):
        text = path.read_text()
        assert "10 pages max" in text, f"{path.name} does not state the 10-page limit"
        assert "5 pages" in text, f"{path.name} does not state the appendix cap"


@pytest.mark.parametrize("path", TIMED_FILES, ids=lambda p: p.name)
def test_presentation_length_agrees_everywhere(path):
    assert f"{PRESENTATION_MINUTES} minutes" in path.read_text(), (
        f"{path.name} does not state the {PRESENTATION_MINUTES}-minute presentation "
        f"limit. It is stated in {len(TIMED_FILES)} student-facing files and they must "
        f"agree -- a student planning against the wrong number gets cut off."
    )


def test_the_presentation_time_budget_adds_up():
    """The brief hands students a per-section budget; it must sum to the limit."""
    text = BRIEF.read_text()
    start = text.index("**What realistically fits:**")
    block = text[start:start + 1200]
    minutes = [float(m) for m in re.findall(r"~\s*([0-9]+(?:\.[0-9]+)?)\s*min", block)]
    assert len(minutes) >= 4, (
        f"parsed only {minutes} from the brief's time budget; the parser and the table "
        f"have diverged, so this test would be checking nothing"
    )
    total = sum(minutes)
    assert total == pytest.approx(PRESENTATION_MINUTES), (
        f"the brief's per-section time budget sums to {total} min but the presentation "
        f"limit is {PRESENTATION_MINUTES} min ({minutes})"
    )
