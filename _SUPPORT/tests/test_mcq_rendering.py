"""Guards for the multiple-choice option rendering fix.

Long option labels used to render on top of each other on JupyterHub. ipywidgets pins every
radio option to a single row::

    .widget-radio-box label, .jupyter-widget-radio-box label {
        height:      var(--jp-widgets-radio-item-height);
        line-height: var(--jp-widgets-radio-item-height);
    }

An earlier fix set ``line-height`` and ``white-space`` but never ``height``, so the text wrapped
while the box stayed one row tall and the overlap remained. These tests pin the three properties
that fix actually needs, because a CSS regression is invisible to every other test in the suite.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "scripts" / "scripts_exercises"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import shared_functions as sf  # noqa: E402
from tasks_data import multiple_choice_options  # noqa: E402


def test_css_overrides_the_fixed_height():
    """`height` is the actual cause; overriding line-height alone does not fix the overlap."""
    assert "height: auto !important" in sf._MCQ_CSS


def test_css_targets_both_the_old_and_new_container_class():
    """ipywidgets 8 renames .widget-radio-box -> .jupyter-widget-radio-box (old kept deprecated)."""
    assert ".widget-radio-box label" in sf._MCQ_CSS
    assert ".jupyter-widget-radio-box label" in sf._MCQ_CSS


def test_css_allows_wrapping():
    assert "white-space: normal !important" in sf._MCQ_CSS


def test_every_css_rule_is_scoped_to_our_own_widget():
    """A global override would restyle unrelated radios (e.g. darcy_law_experiment)."""
    selectors = [
        line.split("{")[0].strip().rstrip(",")
        for line in sf._MCQ_CSS.splitlines()
        if ("{" in line and "@" not in line) or (line.strip().endswith(","))
    ]
    selectors = [s for s in selectors if s and not s.startswith(("/*", "*", "<"))]
    assert selectors, "no selectors parsed out of the stylesheet"
    offenders = [s for s in selectors if ".agm-mcq" not in s]
    assert not offenders, f"unscoped selectors would leak onto other widgets: {offenders}"


def test_widget_carries_the_scoping_class(monkeypatch):
    """The CSS is inert unless the RadioButtons actually gets the .agm-mcq class."""
    shown = []
    monkeypatch.setattr(sf, "display", lambda *a, **k: shown.extend(a))
    task = "task_t08_checkpoint_1"
    sf.create_multiple_choice(task)
    radios = [w for w in shown if type(w).__name__ == "RadioButtons"]
    assert len(radios) == 1, f"expected one RadioButtons, got {len(radios)}"
    assert "agm-mcq" in radios[0]._dom_classes


def test_styles_are_injected_only_once(monkeypatch):
    monkeypatch.setattr(sf, "_MCQ_STYLES_INJECTED", False)
    calls = []
    monkeypatch.setattr(sf, "display", lambda *a, **k: calls.append(a))
    sf._inject_mcq_styles()
    sf._inject_mcq_styles()
    assert len(calls) == 1


@pytest.mark.parametrize("task_id", sorted(multiple_choice_options))
def test_all_multiple_choice_tasks_build(task_id, monkeypatch):
    """Every MCQ checkpoint renders without error and gets the wrapping class."""
    shown = []
    monkeypatch.setattr(sf, "display", lambda *a, **k: shown.extend(a))
    sf.create_multiple_choice(task_id)
    radios = [w for w in shown if type(w).__name__ == "RadioButtons"]
    assert len(radios) == 1
    assert "agm-mcq" in radios[0]._dom_classes
    assert radios[0].options, f"{task_id} rendered with no options"
