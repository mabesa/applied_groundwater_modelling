"""Tests for the T0.2a claim inventory tool.

Locks the acceptance criteria in
``DESIGN_DOCS/T0_2a_claim_inventory_plan.md`` S5 (AC1-AC10). One test class
per criterion; test names cross-reference the AC id so a failure is easy to
map back to the plan.

Run with:  uv run pytest _SUPPORT/tests/test_transport_claim_inventory.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "scripts"))

import transport_claim_inventory as tci  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPO_ROOT / "_SUPPORT" / "src" / "scripts" / "transport_claim_inventory.py"
)

# A line guaranteed to match both halves of the shared Tier-2 net (R: "peak"
# and "mg/L"; N: "42.5") -- verified directly against the live net in
# development. Used across fixtures as "a claim the net will actually find".
CLAIM_LINE = "The observed peak concentration is 42.5 mg/L."
CLAIM_LINE_2 = "Fixture threshold-decision claim: exceeds 12.5 mg/L at day 30."
NON_CLAIM_LINE = "def foo(): return 1  # plain code, no result word or number"


@pytest.fixture(scope="module")
def real_net():
    return tci.load_net_patterns(REPO_ROOT)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _md_cell(cell_id: str, text: str) -> dict:
    cell = {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }
    if cell_id is not None:
        cell["id"] = cell_id
    return cell


def _code_cell(cell_id: str, text: str) -> dict:
    cell = {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }
    if cell_id is not None:
        cell["id"] = cell_id
    return cell


def write_notebook(path: Path, cells: list[dict], nbformat_minor: int = 5) -> None:
    nb = {
        "cells": cells,
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": nbformat_minor,
    }
    path.write_text(json.dumps(nb, indent=1), encoding="utf-8")


def write_tasks_data_fixture(path: Path, extra: str = "") -> None:
    """A tasks_data.py-shaped fixture with all six claim dicts + both
    registries + one entry per dict for one transport key and one flow key,
    so track discrimination (AC5b) and per-dict attribution (AC5) are both
    exercised in a single file."""
    path.write_text(
        f'''"""Fixture tasks_data.py: mirrors the real module's dict shape."""

questions_markdown = {{
    "task_t02_checkpoint_1": r"""{CLAIM_LINE}""",
    "task04_checkpoint_1": r"""{CLAIM_LINE}""",
}}

solutions = {{
    "task_t02_checkpoint_1": (40.0, 45.0),  # {CLAIM_LINE}
    "task04_checkpoint_1": (40.0, 45.0),  # {CLAIM_LINE}
}}

solutions_exact = {{
    "task_t02_checkpoint_1": "42.5",  # {CLAIM_LINE}
    "task04_checkpoint_1": "42.5",  # {CLAIM_LINE}
}}

solution_unit = {{
    "task_t02_checkpoint_1": "mg/L",  # {CLAIM_LINE}
    "task04_checkpoint_1": "mg/L",  # {CLAIM_LINE}
}}

multiple_choice_options = {{
    "task_t02_checkpoint_1": [
        "A) wrong",  # {CLAIM_LINE}
        "B) right",
    ],
    "task04_checkpoint_1": [
        "A) wrong",  # {CLAIM_LINE}
        "B) right",
    ],
}}

solutions_markdown = {{
    "task_t02_checkpoint_1": r"""{CLAIM_LINE}""",
    "task04_checkpoint_1": r"""{CLAIM_LINE}""",
}}

task_functions = {{
    "task_t02_checkpoint_1": lambda: None,  # {CLAIM_LINE} (must NOT be inventoried)
}}

task_functions_start = {{
    "task_t02_checkpoint_1": lambda: None,  # {CLAIM_LINE} (must NOT be inventoried)
}}
{extra}
''',
        encoding="utf-8",
    )


def write_plain_module_fixture(path: Path) -> None:
    path.write_text(
        f'''"""Fixture plain module."""


def compute_peak():
    # {CLAIM_LINE}
    return 42.5


class Reporter:
    def summarize(self):
        # {CLAIM_LINE_2}
        return None
''',
        encoding="utf-8",
    )


def build_scope_dir(tmp_path: Path) -> Path:
    (tmp_path / "PROJECT" / "transport").mkdir(parents=True)
    (tmp_path / "_SUPPORT" / "src" / "scripts" / "scripts_exercises").mkdir(
        parents=True
    )
    (tmp_path / "_SUPPORT" / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "_SUPPORT" / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "DESIGN_DOCS").mkdir(parents=True)
    # The net is parsed live out of the real audit script; copy it in so a
    # fixture repo_root is self-contained and load_net_patterns() works
    # against --repo-root without touching the real repo.
    audit_src = REPO_ROOT / tci.AUDIT_SCRIPT_RELATIVE_PATH
    (tmp_path / tci.AUDIT_SCRIPT_RELATIVE_PATH).write_text(
        audit_src.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# AC1: gate exits 0 iff every candidate is classified; non-zero + prints ids
# otherwise.
# ---------------------------------------------------------------------------


class TestAC1UnclassifiedGate:
    def _make_repo(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(root / "PROJECT/transport/01t_model_goal.ipynb", [
            _md_cell("c1", CLAIM_LINE)
        ])
        return root

    def test_exits_nonzero_when_unclassified(self, tmp_path):
        root = self._make_repo(tmp_path)
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(tmp_path / "cls.yaml"),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode != 0, result.stderr
        report = json.loads((tmp_path / "out.json").read_text())
        assert report["coverage"]["candidates_unclassified"] >= 1
        cand_id = report["candidates"][0]["id"]
        assert cand_id in result.stderr

    def test_exits_zero_when_fully_classified(self, tmp_path):
        root = self._make_repo(tmp_path)
        # First pass to discover the candidate id, then classify it.
        json_out = tmp_path / "out.json"
        run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(tmp_path / "cls.yaml"),
            "--json-out", str(json_out),
            "--md-out", str(tmp_path / "out.md"),
        )
        report = json.loads(json_out.read_text())
        cand_id = report["candidates"][0]["id"]
        (tmp_path / "cls.yaml").write_text(
            yaml.safe_dump({cand_id: {"claim_type": ["numeric"]}}),
            encoding="utf-8",
        )
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(tmp_path / "cls.yaml"),
            "--json-out", str(json_out),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# AC2: orphan classification (id with no matching candidate) fails the run.
# ---------------------------------------------------------------------------


class TestAC2Orphan:
    def test_orphan_fails_the_gate(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", CLAIM_LINE)],
        )
        cls_path = tmp_path / "cls.yaml"
        cls_path.write_text(
            yaml.safe_dump({"deadbeef0000": {"claim_type": ["numeric"]}}),
            encoding="utf-8",
        )
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(cls_path),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode != 0
        assert "deadbeef0000" in result.stderr


# ---------------------------------------------------------------------------
# Multi-type claim_type (2026-08-20 lecturer decision, post two-rater
# classification: a candidate is a text span and a span can assert more than
# one kind of claim -- e.g. "peak ~5.3 mg/L ... still above the 1.0 mg/L
# threshold" is both `numeric` and `threshold-decision`). claim_type is now a
# LIST; `unclassified`/`not_a_claim` stay exclusive sentinels enforced as a
# validation error, never a warning.
# ---------------------------------------------------------------------------


class TestMultiTypeClaimType:
    def _discover_single_candidate_id(self, tmp_path, root):
        json_out = tmp_path / "discover.json"
        run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(tmp_path / "unused_cls.yaml"),
            "--json-out", str(json_out),
            "--md-out", str(tmp_path / "discover.md"),
        )
        report = json.loads(json_out.read_text())
        assert len(report["candidates"]) == 1
        return report["candidates"][0]["id"]

    def test_multitype_candidate_round_trips(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", CLAIM_LINE)],
        )
        cand_id = self._discover_single_candidate_id(tmp_path, root)

        cls_path = tmp_path / "cls.yaml"
        # Deliberately out-of-canonical-order on the way in, to also prove
        # sort_claim_types() normalises the emitted order (AC3 relies on
        # this: two lecturers typing the same set in different order must
        # not perturb byte-identical output).
        cls_path.write_text(
            yaml.safe_dump({cand_id: {"claim_type": ["threshold-decision", "numeric"]}}),
            encoding="utf-8",
        )
        json_out = tmp_path / "out.json"
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(cls_path),
            "--json-out", str(json_out),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(json_out.read_text())
        candidate = report["candidates"][0]
        assert candidate["id"] == cand_id
        # Canonical order per CLAIM_TYPE_VALUES: numeric before
        # threshold-decision, regardless of input order.
        assert candidate["claim_type"] == ["numeric", "threshold-decision"]
        cov = report["coverage"]
        assert cov["candidates_found"] == 1
        assert cov["claim_assignments_found"] == 2
        assert cov["candidates_classified"] == 1
        assert cov["candidates_unclassified"] == 0
        assert cov["by_claim_type"]["numeric"] == 1
        assert cov["by_claim_type"]["threshold-decision"] == 1

    def test_not_a_claim_combined_with_another_type_is_rejected(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", CLAIM_LINE)],
        )
        cand_id = self._discover_single_candidate_id(tmp_path, root)
        cls_path = tmp_path / "cls.yaml"
        cls_path.write_text(
            yaml.safe_dump({cand_id: {"claim_type": ["not_a_claim", "numeric"]}}),
            encoding="utf-8",
        )
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(cls_path),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode != 0
        assert not (tmp_path / "out.json").exists()
        assert "not_a_claim" in result.stderr
        assert "exclusive" in result.stderr.lower()

    def test_unclassified_combined_with_another_type_is_rejected(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", CLAIM_LINE)],
        )
        cand_id = self._discover_single_candidate_id(tmp_path, root)
        cls_path = tmp_path / "cls.yaml"
        cls_path.write_text(
            yaml.safe_dump({cand_id: {"claim_type": ["unclassified", "causal"]}}),
            encoding="utf-8",
        )
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(cls_path),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode != 0
        assert not (tmp_path / "out.json").exists()
        assert "unclassified" in result.stderr
        assert "exclusive" in result.stderr.lower()

    def test_duplicate_entries_in_claim_type_are_rejected(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", CLAIM_LINE)],
        )
        cand_id = self._discover_single_candidate_id(tmp_path, root)
        cls_path = tmp_path / "cls.yaml"
        cls_path.write_text(
            yaml.safe_dump({cand_id: {"claim_type": ["numeric", "numeric"]}}),
            encoding="utf-8",
        )
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(cls_path),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode != 0
        assert not (tmp_path / "out.json").exists()

    def test_empty_claim_type_list_is_rejected(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", CLAIM_LINE)],
        )
        cand_id = self._discover_single_candidate_id(tmp_path, root)
        cls_path = tmp_path / "cls.yaml"
        cls_path.write_text(
            yaml.safe_dump({cand_id: {"claim_type": []}}),
            encoding="utf-8",
        )
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(cls_path),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode != 0
        assert not (tmp_path / "out.json").exists()

    def test_summary_counts_differ_when_multitype_present(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [
                _md_cell("c1", CLAIM_LINE),
                _code_cell("c2", f"# {CLAIM_LINE_2}"),
            ],
        )
        json_out = tmp_path / "discover.json"
        run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(tmp_path / "unused_cls.yaml"),
            "--json-out", str(json_out),
            "--md-out", str(tmp_path / "discover.md"),
        )
        report = json.loads(json_out.read_text())
        assert len(report["candidates"]) == 2
        single_id, multi_id = (c["id"] for c in report["candidates"])

        cls_path = tmp_path / "cls.yaml"
        cls_path.write_text(
            yaml.safe_dump(
                {
                    single_id: {"claim_type": ["numeric"]},
                    multi_id: {"claim_type": ["causal", "illustrative"]},
                }
            ),
            encoding="utf-8",
        )
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(cls_path),
            "--json-out", str(json_out),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(json_out.read_text())
        cov = report["coverage"]
        assert cov["candidates_found"] == 2
        assert cov["claim_assignments_found"] == 3
        assert cov["claim_assignments_found"] != cov["candidates_found"]
        assert cov["candidates_classified"] == 2
        assert cov["candidates_unclassified"] == 0

    def test_sort_claim_types_is_canonical_and_stable(self):
        assert tci.sort_claim_types(["threshold-decision", "numeric"]) == [
            "numeric",
            "threshold-decision",
        ]
        assert tci.sort_claim_types(["illustrative", "causal", "numeric"]) == [
            "numeric",
            "causal",
            "illustrative",
        ]


# ---------------------------------------------------------------------------
# AC3: determinism -- two consecutive runs produce byte-identical output.
# ---------------------------------------------------------------------------


class TestAC3Determinism:
    def test_two_runs_are_byte_identical(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", CLAIM_LINE), _code_cell("c2", f"# {CLAIM_LINE_2}")],
        )
        write_tasks_data_fixture(
            root / "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py"
        )
        scope = [
            "PROJECT/transport/01t_model_goal.ipynb",
            "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py",
        ]
        json1, md1 = tmp_path / "a.json", tmp_path / "a.md"
        json2, md2 = tmp_path / "b.json", tmp_path / "b.md"
        run_cli(
            "--repo-root", str(root), "--scope", *scope,
            "--classifications", str(tmp_path / "cls.yaml"),
            "--json-out", str(json1), "--md-out", str(md1),
        )
        run_cli(
            "--repo-root", str(root), "--scope", *scope,
            "--classifications", str(tmp_path / "cls.yaml"),
            "--json-out", str(json2), "--md-out", str(md2),
        )
        assert json1.read_bytes() == json2.read_bytes()
        assert md1.read_bytes() == md2.read_bytes()

    def test_real_repo_is_deterministic(self, tmp_path):
        # Same check against the real committed scope (no fixtures): the
        # deliverable JSON/MD in DOCUMENTATION/contracts/ must be reproducible.
        json1, md1 = tmp_path / "a.json", tmp_path / "a.md"
        json2, md2 = tmp_path / "b.json", tmp_path / "b.md"
        cls = REPO_ROOT / tci.DEFAULT_CLASSIFICATIONS_RELATIVE
        run_cli(
            "--classifications", str(cls),
            "--json-out", str(json1), "--md-out", str(md1),
        )
        run_cli(
            "--classifications", str(cls),
            "--json-out", str(json2), "--md-out", str(md2),
        )
        assert json1.read_bytes() == json2.read_bytes()
        assert md1.read_bytes() == md2.read_bytes()


# ---------------------------------------------------------------------------
# AC4: notebook coverage -- every markdown/code cell visited; a claim in the
# LAST cell of a fixture notebook is found.
# ---------------------------------------------------------------------------


class TestAC4NotebookCoverage:
    def test_every_cell_visited_and_last_cell_claim_found(self, tmp_path):
        root = build_scope_dir(tmp_path)
        cells = [_md_cell(f"c{i}", f"filler cell {i}, no claim here") for i in range(5)]
        cells.append(_code_cell("last", f"# {CLAIM_LINE}"))
        write_notebook(root / "PROJECT/transport/01t_model_goal.ipynb", cells)

        r_pattern, n_pattern = tci.load_net_patterns(root)
        coverage = tci.Coverage()
        candidates = tci.scan_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            root,
            r_pattern,
            n_pattern,
            coverage,
        )
        assert coverage.notebook_cells_visited == 6
        assert len(candidates) == 1
        assert candidates[0].cell_index == 5
        assert candidates[0].cell_id == "last"

    def test_cells_without_nbformat_id_get_flagged_synthetic(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell(None, CLAIM_LINE)],
            nbformat_minor=4,
        )
        r_pattern, n_pattern = tci.load_net_patterns(root)
        coverage = tci.Coverage()
        candidates = tci.scan_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            root,
            r_pattern,
            n_pattern,
            coverage,
        )
        assert len(candidates) == 1
        assert candidates[0].cell_id_synthetic is True
        assert candidates[0].cell_id == "idx-0"

    def test_notebook_candidate_id_stable_across_reformat_but_content_sensitive(
        self, tmp_path
    ):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", CLAIM_LINE + "  \n\ttrailing whitespace noise")],
        )
        r_pattern, n_pattern = tci.load_net_patterns(root)
        cov = tci.Coverage()
        cand_reformatted = tci.scan_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb", root, r_pattern, n_pattern, cov
        )
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", CLAIM_LINE)],
        )
        cand_plain = tci.scan_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb", root, r_pattern, n_pattern, tci.Coverage()
        )
        assert cand_reformatted[0].id == cand_plain[0].id  # whitespace-normalised

        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", "The observed peak concentration is 99.9 mg/L.")],
        )
        cand_reworded = tci.scan_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb", root, r_pattern, n_pattern, tci.Coverage()
        )
        assert cand_reworded[0].id != cand_plain[0].id  # content-sensitive


# ---------------------------------------------------------------------------
# AC5 / AC5b: tasks_data.py coverage, per-dict attribution, track
# discrimination.
# ---------------------------------------------------------------------------


class TestAC5TasksDataCoverage:
    def test_one_candidate_per_claim_bearing_dict_with_key(self, tmp_path):
        root = build_scope_dir(tmp_path)
        fixture_path = root / "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py"
        write_tasks_data_fixture(fixture_path)

        r_pattern, n_pattern = tci.load_net_patterns(root)
        coverage = tci.Coverage()
        candidates, excluded = tci.scan_tasks_data(
            fixture_path, root, r_pattern, n_pattern, coverage
        )

        transport_candidates = [c for c in candidates if c.checkpoint_key == "task_t02_checkpoint_1"]
        dict_names_seen = {c.dict_name for c in transport_candidates}
        assert dict_names_seen == {
            "questions_markdown",
            "solutions",
            "solutions_exact",
            "solution_unit",
            "multiple_choice_options",
            "solutions_markdown",
        }
        assert all(c.checkpoint_key == "task_t02_checkpoint_1" for c in transport_candidates)

    def test_registries_excluded_by_name_and_recorded(self, tmp_path):
        root = build_scope_dir(tmp_path)
        fixture_path = root / "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py"
        write_tasks_data_fixture(fixture_path)
        r_pattern, n_pattern = tci.load_net_patterns(root)
        candidates, excluded = tci.scan_tasks_data(
            fixture_path, root, r_pattern, n_pattern, tci.Coverage()
        )
        excluded_names = {e.name for e in excluded}
        assert excluded_names == {"task_functions", "task_functions_start"}
        # No candidate may claim to come from an excluded dict.
        assert all(c.dict_name not in excluded_names for c in candidates)


class TestAC5bTrackDiscrimination:
    def test_only_transport_keys_are_inventoried(self, tmp_path):
        root = build_scope_dir(tmp_path)
        fixture_path = root / "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py"
        write_tasks_data_fixture(fixture_path)
        r_pattern, n_pattern = tci.load_net_patterns(root)
        candidates, _ = tci.scan_tasks_data(
            fixture_path, root, r_pattern, n_pattern, tci.Coverage()
        )
        keys = {c.checkpoint_key for c in candidates}
        assert keys == {"task_t02_checkpoint_1"}
        assert not any(k.startswith("task0") for k in keys if k)

    def test_real_repo_has_no_flow_track_leak(self):
        r_pattern, n_pattern = tci.load_net_patterns(REPO_ROOT)
        candidates, _ = tci.scan_tasks_data(
            REPO_ROOT / "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py",
            REPO_ROOT,
            r_pattern,
            n_pattern,
            tci.Coverage(),
        )
        keys = {c.checkpoint_key for c in candidates}
        assert all(tci.TRANSPORT_KEY_PATTERN.match(k) for k in keys)
        assert not any(tci.FLOW_KEY_PATTERN.match(k) and not tci.TRANSPORT_KEY_PATTERN.match(k) for k in keys)

    def test_real_repo_transport_key_universe(self):
        # Discover the true set of task_t* keys independently (via a fresh
        # AST walk, not by importing the module under test), and check the
        # inventory's checkpoint-key universe matches it exactly. Not
        # hard-coded to a specific count: tasks_data.py is the source of
        # truth (see T0_2a plan S4.2 vs. this repo's actual content).
        import ast

        text = (
            REPO_ROOT / "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(text)
        expected_keys = set()
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Dict)
                and node.targets[0].id not in tci.TASKS_DATA_EXCLUDED_DICTS
            ):
                for key_node in node.value.keys:
                    if isinstance(key_node, ast.Constant) and isinstance(
                        key_node.value, str
                    ) and tci.TRANSPORT_KEY_PATTERN.match(key_node.value):
                        expected_keys.add(key_node.value)

        r_pattern, n_pattern = tci.load_net_patterns(REPO_ROOT)
        candidates, _ = tci.scan_tasks_data(
            REPO_ROOT / "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py",
            REPO_ROOT,
            r_pattern,
            n_pattern,
            tci.Coverage(),
        )
        found_keys = {c.checkpoint_key for c in candidates}
        # found_keys can be a subset (the net may not hit every dict entry
        # for every key -- that is the documented under-matching risk), but
        # it must never contain a key outside expected_keys, and it must
        # never contain a flow-track key.
        assert found_keys <= expected_keys
        assert not any(not tci.TRANSPORT_KEY_PATTERN.match(k) for k in found_keys)


# ---------------------------------------------------------------------------
# AC6: fails closed on a parse error.
# ---------------------------------------------------------------------------


class TestAC6ParseErrorsFailClosed:
    def test_unreadable_notebook_json_is_an_error(self, tmp_path):
        root = build_scope_dir(tmp_path)
        (root / "PROJECT/transport/01t_model_goal.ipynb").write_text(
            "{ this is not valid json", encoding="utf-8"
        )
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(tmp_path / "cls.yaml"),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode != 0
        assert not (tmp_path / "out.json").exists()
        assert "json" in result.stderr.lower()

    def test_unparseable_python_module_is_an_error(self, tmp_path):
        root = build_scope_dir(tmp_path)
        bad = root / "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py"
        bad.write_text("def broken(:\n    pass\n", encoding="utf-8")
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py",
            "--classifications", str(tmp_path / "cls.yaml"),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode != 0
        assert not (tmp_path / "out.json").exists()

    def test_missing_scope_file_is_an_error_not_a_silent_skip(self, tmp_path):
        root = build_scope_dir(tmp_path)
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/does_not_exist.ipynb",
            "--classifications", str(tmp_path / "cls.yaml"),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        assert result.returncode != 0
        assert not (tmp_path / "out.json").exists()


# ---------------------------------------------------------------------------
# AC7: output carries a coverage summary.
# ---------------------------------------------------------------------------


class TestAC7CoverageSummary:
    def test_empty_net_is_visible(self, tmp_path):
        root = build_scope_dir(tmp_path)
        write_notebook(
            root / "PROJECT/transport/01t_model_goal.ipynb",
            [_md_cell("c1", NON_CLAIM_LINE)],
        )
        result = run_cli(
            "--repo-root", str(root),
            "--scope", "PROJECT/transport/01t_model_goal.ipynb",
            "--classifications", str(tmp_path / "cls.yaml"),
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
        )
        report = json.loads((tmp_path / "out.json").read_text())
        cov = report["coverage"]
        for key in (
            "files_visited",
            "notebook_cells_visited",
            "candidates_found",
            "candidates_classified",
            "candidates_rejected",
            "candidates_unclassified",
        ):
            assert key in cov
        assert cov["files_visited"] == 1
        assert cov["candidates_found"] == 0
        # A visited-but-empty net must succeed (nothing to classify), not
        # be indistinguishable from a run that never happened.
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# AC8: committed outputs carry no absolute paths / machine-specific values.
# ---------------------------------------------------------------------------


class TestAC8NoAbsolutePaths:
    def test_committed_json_has_no_absolute_paths(self):
        json_path = REPO_ROOT / tci.DEFAULT_JSON_OUT_RELATIVE
        assert json_path.exists(), "run --init-classifications / a normal run first"
        text = json_path.read_text(encoding="utf-8")
        assert str(REPO_ROOT) not in text
        assert str(Path.home()) not in text
        report = json.loads(text)
        for candidate in report["candidates"]:
            assert not candidate["path"].startswith("/")
            assert ".." not in candidate["path"]

    def test_committed_md_has_no_absolute_paths(self):
        md_path = REPO_ROOT / tci.DEFAULT_MD_OUT_RELATIVE
        assert md_path.exists()
        text = md_path.read_text(encoding="utf-8")
        assert str(REPO_ROOT) not in text
        assert str(Path.home()) not in text


# ---------------------------------------------------------------------------
# AC9: existing transport suites still pass unchanged; no inventoried file
# modified.
# ---------------------------------------------------------------------------


class TestAC9NoSideEffects:
    @pytest.mark.parametrize(
        "rel_path", list(tci.SCOPE_RELATIVE_PATHS)
    )
    def test_scope_file_untouched_by_a_run(self, tmp_path, rel_path):
        path = REPO_ROOT / rel_path
        before = path.read_bytes()
        before_mtime = path.stat().st_mtime_ns
        run_cli(
            "--json-out", str(tmp_path / "out.json"),
            "--md-out", str(tmp_path / "out.md"),
            "--classifications", str(tmp_path / "cls.yaml"),
        )
        after = path.read_bytes()
        assert before == after
        assert before_mtime == path.stat().st_mtime_ns

    def test_existing_transport_test_modules_still_importable(self):
        # A cheap, static proxy for "the existing suites still pass": every
        # test module in scope must still parse (ast) without error, which
        # is what this tool itself relies on and is a necessary condition
        # for pytest collection to succeed.
        import ast

        for rel_path in tci.SCOPE_RELATIVE_PATHS:
            if rel_path.startswith("_SUPPORT/tests/"):
                text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
                ast.parse(text, filename=rel_path)  # raises on failure


# ---------------------------------------------------------------------------
# AC10: docstring documents the relationship to the audit script.
# ---------------------------------------------------------------------------


class TestAC10DocstringRelationship:
    def test_docstring_mentions_audit_script_and_relationship(self):
        doc = tci.__doc__ or ""
        assert "transport_stale_number_audit.sh" in doc
        lowered = doc.lower()
        assert "different job" in lowered or "does not replace" in lowered or "neither" in lowered
        assert "shared" in lowered or "same net" in lowered


# ---------------------------------------------------------------------------
# Extra: net loaded from the audit script, not duplicated by hand.
# ---------------------------------------------------------------------------


class TestSharedNet:
    def test_net_is_parsed_out_of_the_audit_script_live(self, real_net):
        r_pattern, n_pattern = real_net
        audit_text = (REPO_ROOT / tci.AUDIT_SCRIPT_RELATIVE_PATH).read_text(
            encoding="utf-8"
        )
        assert r_pattern.pattern in audit_text
        assert n_pattern.pattern in audit_text

    def test_matches_result_word_and_number_lines(self, real_net):
        r_pattern, n_pattern = real_net
        assert r_pattern.search(CLAIM_LINE) and n_pattern.search(CLAIM_LINE)
        assert not r_pattern.search(NON_CLAIM_LINE)


# ---------------------------------------------------------------------------
# Read-only / static-only sanity (requirements 6-7 of the design doc).
# ---------------------------------------------------------------------------


class TestReadOnlyAndStatic:
    def test_module_does_not_import_inventoried_transport_modules(self):
        import ast

        text = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(text)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.add(node.module)
        forbidden = {
            "transport_srcpulse_demo",
            "transport_base_model",
            "transport_prt_capture",
            "transport_verify_2d",
            "flopy",
        }
        assert not (imported_names & forbidden)

    def test_full_real_run_completes_quickly(self):
        import time

        start = time.monotonic()
        result = run_cli(
            "--no-write", "--classifications", str(REPO_ROOT / "does-not-exist.yaml")
        )
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"run took {elapsed:.2f}s, budget is 5s"
        # Missing classification file => everything unclassified => nonzero,
        # but that is a gate result, not a crash.
        assert result.returncode in (0, 1)
