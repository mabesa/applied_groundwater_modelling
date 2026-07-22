"""
Tests for milestone M2b.3 -- the group-0 student flow template notebook
(``PROJECT/workspace/template/case_study_flow_group_0.ipynb``).

MACOS-DOABLE (this file, always-on, NO notebook execution):
* Parse the .ipynb JSON and assert the 11 documented section headers are
  present (by keyword), the documented ``#TODO``/**TODO** sites exist
  (config, metrics, sandbox, interpretation -- at least one each), the
  imports cell references ``casestudy_flow_viz``, ``casestudy_flow_particles``,
  and ``build_all_flow_states``, and a ``RUN_PRT`` toggle defaulting to
  ``False`` is present. Guards deletion/drift of the replaced legacy
  (NWT telescope) notebook.

HUB-TODO (cannot run here -- AGM_HUB=1, SKIPPED on macOS, M2a5 precedent):
execute the notebook end-to-end for group 0 (nbclient) and assert the
expected artifacts exist (``flow_metrics.group0.json``,
``equalization_metrics.0.json``, ``figs/heads_wells.png``).

Run with:  uv run pytest _SUPPORT/tests/test_casestudy_flow_group0_notebook.py -v
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

NOTEBOOK_PATH = (
    Path(__file__).parent.parent.parent
    / "PROJECT" / "workspace" / "template" / "case_study_flow_group_0.ipynb"
)

# Hub gate: the execution smoke is REQUIRED on Linux/JupyterHub (AGM_HUB=1)
# and SKIPPED on macOS/dev (M2a5 precedent -- a skipped smoke is NEVER
# acceptance evidence).
requires_hub = pytest.mark.skipif(
    os.environ.get("AGM_HUB") != "1",
    reason="hub-only notebook-execution smoke: set AGM_HUB=1 on Linux/JupyterHub",
)

REQUIRED_SECTION_KEYWORDS = [
    "overview and learning objectives",
    "configure your group",
    "understand your scenario",
    "build the four flow states",
    "heads and drawdown maps",
    "water budget",
    "capture zone and pathlines",
    "metrics",
    "scenario sandbox",
    "interpretation and defensibility",
    "reproducibility check",
]


def _load_notebook():
    assert NOTEBOOK_PATH.exists(), f"notebook missing: {NOTEBOOK_PATH}"
    return json.loads(NOTEBOOK_PATH.read_text())


def _all_source(nb, cell_type=None):
    """Concatenate all cell source text (optionally filtered by cell_type)."""
    parts = []
    for cell in nb["cells"]:
        if cell_type is not None and cell["cell_type"] != cell_type:
            continue
        src = cell["source"]
        parts.append("".join(src) if isinstance(src, list) else src)
    return "\n".join(parts)


def _markdown_headers(nb):
    headers = []
    for cell in nb["cells"]:
        if cell["cell_type"] != "markdown":
            continue
        src = cell["source"]
        text = "".join(src) if isinstance(src, list) else src
        for line in text.splitlines():
            if line.strip().startswith("#"):
                headers.append(line.strip().lower())
    return headers


# =============================================================================
# Valid JSON / non-empty.
# =============================================================================
class TestNotebookIsValidAndNonEmpty:
    def test_notebook_parses_as_json(self):
        nb = _load_notebook()
        assert "cells" in nb
        assert len(nb["cells"]) > 10, "notebook looks truncated/gutted"

    def test_notebook_has_no_baked_in_outputs(self):
        # Repo convention: notebooks are committed with no execution outputs
        # (pre-commit strips them anyway) -- guard that this generator never
        # regresses that.
        nb = _load_notebook()
        for cell in nb["cells"]:
            if cell["cell_type"] != "code":
                continue
            assert cell.get("outputs", []) == [], "code cell carries baked-in outputs"
            assert cell.get("execution_count") in (None, 0), (
                "code cell carries a stale execution_count"
            )


# =============================================================================
# Section headers (11 sections, by keyword -- guards deletion/drift).
# =============================================================================
class TestRequiredSections:
    def test_all_eleven_section_headers_present(self):
        nb = _load_notebook()
        headers_text = "\n".join(_markdown_headers(nb))
        missing = [kw for kw in REQUIRED_SECTION_KEYWORDS if kw not in headers_text]
        assert not missing, f"missing section header keywords: {missing}"

    def test_sections_are_numbered_1_through_11(self):
        nb = _load_notebook()
        headers = _markdown_headers(nb)
        numbered = [h for h in headers if re.match(r"^#+\s*\d+\.", h)]
        found_numbers = sorted(
            int(re.match(r"^#+\s*(\d+)\.", h).group(1)) for h in numbered
        )
        assert found_numbers == list(range(1, 12)), (
            f"expected sections 1..11, found {found_numbers}"
        )


# =============================================================================
# TODO sites (config, metrics, sandbox, interpretation -- at least one each).
# =============================================================================
class TestTodoSites:
    def test_config_todo_present(self):
        nb = _load_notebook()
        text = _all_source(nb)
        # Section 2 markdown instructs editing case_config.yaml fields.
        assert "TODO" in text and "case_config.yaml" in text
        section2 = self._section_text(nb, "configure your group")
        assert "TODO" in section2

    def test_scenario_justification_todo_present(self):
        nb = _load_notebook()
        section3 = self._section_text(nb, "understand your scenario")
        assert "TODO" in section3

    def test_metrics_todo_present(self):
        nb = _load_notebook()
        section8 = self._section_text(nb, "metrics")
        assert "#TODO" in section8 or "TODO" in section8

    def test_sandbox_todo_present(self):
        nb = _load_notebook()
        section9 = self._section_text(nb, "scenario sandbox")
        assert "TODO" in section9

    def test_interpretation_todo_present(self):
        nb = _load_notebook()
        section10 = self._section_text(nb, "interpretation and defensibility")
        assert "TODO" in section10
        # priority framing must be present (priority-1 defensible-vs-artifact,
        # priority-2 justify assumptions).
        assert "priority" in section10.lower()

    @staticmethod
    def _section_text(nb, start_keyword, next_section_prefix=None):
        """Concatenate all cell source between a section header containing
        *start_keyword* and the next numbered '## N.' markdown header."""
        collecting = False
        collected = []
        for cell in nb["cells"]:
            src = cell["source"]
            text = "".join(src) if isinstance(src, list) else src
            if cell["cell_type"] == "markdown":
                header_match = re.match(r"^##\s*\d+\.", text.strip())
                if header_match and start_keyword in text.lower():
                    collecting = True
                    collected.append(text)
                    continue
                if header_match and collecting:
                    break
            if collecting:
                collected.append(text)
        assert collected, f"section starting with {start_keyword!r} not found"
        return "\n".join(collected)


# =============================================================================
# Imports cell references the required modules.
# =============================================================================
class TestImportsCell:
    def test_imports_reference_required_modules(self):
        nb = _load_notebook()
        text = _all_source(nb, cell_type="code")
        for needle in (
            "casestudy_flow_viz",
            "casestudy_flow_particles",
            "casestudy_flow_builder",
            "build_all_flow_states",
        ):
            assert needle in text, f"notebook never references {needle!r}"

    def test_sys_path_append_present(self):
        nb = _load_notebook()
        text = _all_source(nb, cell_type="code")
        assert "sys.path.append" in text and "_SUPPORT/src" in text


# =============================================================================
# RUN_PRT toggle, default False.
# =============================================================================
class TestRunPrtToggle:
    def test_run_prt_toggle_present_and_defaults_false(self):
        nb = _load_notebook()
        text = _all_source(nb, cell_type="code")
        assert re.search(r"RUN_PRT\s*=\s*False", text), (
            "RUN_PRT toggle must be present and default to False"
        )

    def test_run_prt_gates_the_prt_calls(self):
        nb = _load_notebook()
        text = _all_source(nb, cell_type="code")
        # the particle-tracking calls must be reached only inside the toggle,
        # not called unconditionally at import time.
        m = re.search(r"if RUN_PRT:(.*?)(?:\nelse:|\nRUN_PRT|\Z)", text, re.S)
        assert m, "RUN_PRT toggle does not appear to gate a block"
        gated = m.group(1)
        assert "build_capture" in gated


# =============================================================================
# Named figure artifacts referenced (save_fig calls for the required maps).
# =============================================================================
class TestNamedArtifacts:
    def test_required_named_figures_referenced(self):
        nb = _load_notebook()
        text = _all_source(nb, cell_type="code")
        for name in (
            "heads_baseline", "heads_wells", "heads_scenario",
            "drawdown_wells", "drawdown_half", "scenario_effect",
            "budget_states",
        ):
            assert name in text, f"expected save_fig target {name!r} not referenced"

    def test_flow_metrics_and_equalization_json_referenced(self):
        nb = _load_notebook()
        text = _all_source(nb, cell_type="code")
        assert "write_flow_metrics" in text
        assert "emit_equalization_json" in text


# =============================================================================
# HUB-GATED execution smoke -- SKIPPED on macOS (M2a5 precedent: a skipped
# smoke is never acceptance evidence).
# =============================================================================
@requires_hub
class TestHubNotebookExecution:
    def test_executes_end_to_end_and_emits_artifacts(self, tmp_path, monkeypatch):
        import nbformat
        from nbclient import NotebookClient

        nb = nbformat.read(str(NOTEBOOK_PATH), as_version=4)
        client = NotebookClient(nb, timeout=1800, kernel_name="python3")
        client.execute(resources={"metadata": {"path": str(NOTEBOOK_PATH.parent)}})

        # Locate the work_dir the notebook resolved (group 0's output workspace).
        import case_utils

        cfg = case_utils.load_yaml(str(NOTEBOOK_PATH.parent / "case_config.yaml"))
        group_number = cfg["group"]["number"]
        work_dir = Path(cfg["output"]["workspace"] + str(group_number)).expanduser()

        assert (work_dir / f"flow_metrics.group{group_number}.json").exists()
        assert (work_dir / f"equalization_metrics.{group_number}.json").exists()
        assert (work_dir / "figs" / "heads_wells.png").exists()
