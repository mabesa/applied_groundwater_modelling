"""Validate tracked internal links in student-facing notebooks and Markdown.

Notebook failure locations use 0-based cell indexes.
"""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote


MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
FENCE_START_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
EXCLUDED_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
    "ftp:",
    "//",
    "data:",
)


@dataclass(frozen=True)
class ExtractedLink:
    href: str
    line: int


@dataclass(frozen=True)
class LinkFailure:
    source: str
    location: str
    href: str
    reason: str


@dataclass(frozen=True)
class ValidationReport:
    scanned_files: int
    checked_links: int
    failures: list[LinkFailure]


class LinkHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attr_name = None
        if tag.lower() == "a":
            attr_name = "href"
        elif tag.lower() == "img":
            attr_name = "src"

        if attr_name is None:
            return

        for name, value in attrs:
            if name.lower() == attr_name and value is not None:
                line, _ = self.getpos()
                self.links.append(ExtractedLink(value, line))
                break


def list_tracked_files(repo_root):
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    }


def is_source_file(path):
    path = path.replace("\\", "/")
    suffix = Path(path).suffix.lower()

    if "/" not in path and suffix == ".md":
        return True

    if path.startswith("DOCUMENTATION/"):
        return suffix == ".md"

    if not path.startswith("PROJECT/"):
        return False

    return suffix in {".ipynb", ".md"}


def source_files(tracked_files):
    return sorted(path for path in tracked_files if is_source_file(path))


def strip_markdown_destination(raw_destination):
    destination = raw_destination.strip()

    if destination.startswith("<"):
        end = destination.find(">")
        if end != -1:
            return destination[1:end].strip()

    return destination.split(None, 1)[0] if destination else destination


def blank_line_like(line):
    return "\n" if line.endswith("\n") else ""


def strip_fenced_code_blocks(text):
    """Blank ``` and ~~~ fenced blocks; 4-space indented code is deferred."""
    stripped_lines = []
    in_fence = False
    fence_char = ""
    fence_length = 0

    for line in text.splitlines(keepends=True):
        if in_fence:
            stripped_lines.append(blank_line_like(line))
            candidate = line.rstrip("\n\r")
            if re.match(
                rf"^[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*$",
                candidate,
            ):
                in_fence = False
            continue

        match = FENCE_START_RE.match(line)
        if match:
            fence = match.group(1)
            in_fence = True
            fence_char = fence[0]
            fence_length = len(fence)
            stripped_lines.append(blank_line_like(line))
            continue

        stripped_lines.append(line)

    return "".join(stripped_lines)


def extract_links(text):
    text = strip_fenced_code_blocks(text)
    links = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        links.append(ExtractedLink(strip_markdown_destination(match.group(1)), line))

    parser = LinkHTMLParser()
    parser.feed(text)
    links.extend(parser.links)
    return links


def should_skip_href(href):
    stripped = href.strip()
    lowered = stripped.lower()
    return (
        not stripped
        or stripped.startswith("#")
        or stripped.startswith("/")
        or lowered.startswith(EXCLUDED_PREFIXES)
    )


def internal_path_from_href(href):
    if should_skip_href(href):
        return None

    path_part = href.split("#", 1)[0].split("?", 1)[0]
    if not path_part:
        return None

    return unquote(path_part)


def validate_link(repo_root, tracked_files, source_path, href):
    repo_root = Path(repo_root).resolve()
    source_path = Path(source_path)
    if not source_path.is_absolute():
        source_path = repo_root / source_path

    internal_path = internal_path_from_href(href)
    if internal_path is None:
        return None

    resolved_target = (source_path.parent / internal_path).resolve()
    try:
        target_rel = resolved_target.relative_to(repo_root).as_posix()
    except ValueError:
        return "path escapes repo root"

    if target_rel not in tracked_files:
        return "target does not exist"

    return None


def markdown_source(source):
    if isinstance(source, list):
        return "".join(source)
    if isinstance(source, str):
        return source
    return ""


def validate_markdown_file(repo_root, tracked_files, source_rel):
    source_path = repo_root / source_rel
    text = source_path.read_text(encoding="utf-8")
    failures = []
    checked_links = 0

    for link in extract_links(text):
        internal_path = internal_path_from_href(link.href)
        if internal_path is None:
            continue

        checked_links += 1
        reason = validate_link(repo_root, tracked_files, source_path, link.href)
        if reason is not None:
            failures.append(LinkFailure(source_rel, str(link.line), link.href, reason))

    return checked_links, failures


def validate_notebook_file(repo_root, tracked_files, source_rel):
    source_path = repo_root / source_rel
    failures = []
    checked_links = 0

    try:
        notebook = json.loads(source_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return 0, [LinkFailure(source_rel, "notebook", source_rel, f"unreadable notebook: {exc}")]
    except json.JSONDecodeError as exc:
        return 0, [
            LinkFailure(
                source_rel,
                "notebook",
                source_rel,
                f"malformed notebook: {exc.msg}",
            )
        ]

    cells = notebook.get("cells") if isinstance(notebook, dict) else None
    if not isinstance(cells, list):
        return 0, [
            LinkFailure(
                source_rel,
                "notebook",
                source_rel,
                "malformed notebook: missing cells list",
            )
        ]

    for cell_index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            return 0, [
                LinkFailure(
                    source_rel,
                    "notebook",
                    source_rel,
                    f"malformed notebook: cell {cell_index} is not an object",
                )
            ]

        if cell.get("cell_type") != "markdown":
            continue

        for link in extract_links(markdown_source(cell.get("source", ""))):
            internal_path = internal_path_from_href(link.href)
            if internal_path is None:
                continue

            checked_links += 1
            reason = validate_link(repo_root, tracked_files, source_path, link.href)
            if reason is not None:
                failures.append(
                    LinkFailure(source_rel, f"cell {cell_index}", link.href, reason)
                )

    return checked_links, failures


def validate_repo(repo_root, tracked_files=None):
    repo_root = Path(repo_root).resolve()
    if tracked_files is None:
        tracked_files = list_tracked_files(repo_root)

    failures = []
    checked_links = 0
    sources = source_files(tracked_files)

    for source_rel in sources:
        suffix = Path(source_rel).suffix.lower()
        if suffix == ".ipynb":
            file_checked_links, file_failures = validate_notebook_file(
                repo_root,
                tracked_files,
                source_rel,
            )
        else:
            file_checked_links, file_failures = validate_markdown_file(
                repo_root,
                tracked_files,
                source_rel,
            )

        checked_links += file_checked_links
        failures.extend(file_failures)

    return ValidationReport(len(sources), checked_links, failures)


def print_report(report, out):
    for failure in report.failures:
        print(
            f'{failure.source}:{failure.location}: broken link "{failure.href}" -> '
            f"{failure.reason}",
            file=out,
        )

    print(
        f"Scanned {report.scanned_files} files; checked {report.checked_links} "
        f"internal links; {len(report.failures)} failures.",
        file=out,
    )


def run(repo_root=None, tracked_files=None, out=sys.stdout):
    if repo_root is None:
        repo_root = Path.cwd()

    try:
        report = validate_repo(repo_root, tracked_files)
    except subprocess.CalledProcessError as exc:
        print(f"failed to enumerate tracked files with git ls-files: {exc}", file=out)
        return 2

    print_report(report, out)
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(run())
