"""The Hub home is EPHEMERAL -- it wiped ~/.local (MODFLOW binaries) and, separately,
the GIS data folder, between two sessions on the same node (2026-09-04). Both losses
surfaced as 13 identical FAILs with a BLANK notes column, and the real cause sat unread
in `stderr_tail`. Three Hub sessions were spent finding it.

These tests pin the four fixes. None of them runs MODFLOW, downloads anything, or
touches the user's real binaries or data.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_SUPPORT" / "src"))
sys.path.insert(0, str(REPO / "_SUPPORT" / "src" / "scripts"))

import validate_flow_groups as vfg          # noqa: E402
import validate_transport_groups as vtg     # noqa: E402


# --- 1. the failure is READABLE (the general fix) ----------------------------

def test_flow_summary_prints_the_stderr_tail_of_a_failure(capsys):
    """🔴 The defect that cost three Hub sessions: `error` is None for an ordinary
    non-zero exit, so a summary showing only `error` printed a BLANK notes column."""
    results = [{
        "group": 0, "status": "FAIL", "runtime_s": 8.0, "metrics": {},
        "error": None, "over_budget": False,
        "stderr_tail": "Traceback (most recent call last):\n"
                       "FileNotFoundError: The program triangle does not exist "
                       "or is not executable.",
    }]
    vfg._print_summary(results)
    out = capsys.readouterr().out
    assert "triangle does not exist" in out, (
        "the cause is still invisible in the summary -- this is the exact defect")
    assert "group 0" in out


def test_flow_summary_stays_quiet_when_everything_passed(capsys):
    results = [{"group": 0, "status": "OK", "runtime_s": 90.0,
                "metrics": {"ncpl": 4543, "refine_radius": 90.0},
                "error": None, "stderr_tail": None, "over_budget": False}]
    vfg._print_summary(results)
    out = capsys.readouterr().out
    assert "stderr tail" not in out


# --- 2. preflight ------------------------------------------------------------

def test_preflight_passes_on_this_healthy_machine():
    assert vtg.preflight(verbose=False) == []


def test_preflight_names_a_missing_binary_and_gives_a_runnable_command(monkeypatch, capsys):
    import flopy.mbase as mb

    def _no_triangle(name, *a, **k):
        if name == "triangle":
            raise FileNotFoundError("The program triangle does not exist")
        return f"/fake/{name}"

    monkeypatch.setattr(mb, "resolve_exe", _no_triangle)
    monkeypatch.setattr(vtg, "preflight", vtg.preflight)   # keep the real one
    problems = vtg.preflight(verbose=True)
    out = capsys.readouterr().out
    assert any("triangle" in p for p in problems), problems
    assert vtg.FIX_BINARIES in out, "the recovery command must be printed verbatim"
    assert "0_diagnostics" not in out, (
        "recovery must not require knowing which notebook cell to run")


def test_the_recovery_commands_are_runnable_outside_a_notebook():
    """They are pasted into a shell, so they must be single-line and self-contained."""
    for cmd in (vtg.FIX_BINARIES, vtg.FIX_GIS):
        assert "\n" not in cmd
        assert cmd.startswith("python")


def test_a_failing_preflight_stops_the_gate_before_any_group_runs(monkeypatch):
    """🔴 The point of a preflight: not one group may run."""
    ran = []
    monkeypatch.setattr(vtg, "preflight", lambda **k: ["boom"])
    monkeypatch.setattr(vtg, "_run_group",
                        lambda *a, **k: ran.append(a) or {"status": "OK"})
    monkeypatch.setattr(sys, "argv", ["validate_transport_groups.py", "--groups", "0"])
    vtg.main()
    assert ran == [], "a group ran despite the preflight failing"


def test_flow_gate_stops_before_any_group_runs(monkeypatch):
    ran = []
    monkeypatch.setattr(vfg.vtg, "preflight", lambda **k: ["boom"])
    monkeypatch.setattr(vfg, "_run_group",
                        lambda *a, **k: ran.append(a) or {"status": "OK"})
    rc = vfg.main(["--groups", "0"])
    assert ran == []
    assert rc == 2


# --- 3. executable discovery, in a FRESH SUBPROCESS --------------------------
# FloPy appends its bin dir to PATH *at import*, so mutating HOME/PATH in-process
# after importing it makes any such test lie. Each of these runs its own interpreter.

def _probe(code: str, *, strip_flopy_bin: bool = False) -> str:
    """Run *code* in a fresh interpreter.

    ⚠️ A subprocess is NOT automatically clean: importing flopy anywhere in the parent
    (this test module imports the gates, which import flopy) appends flopy's bin dir to
    ``os.environ["PATH"]``, and the child INHERITS that. A test that ignores this
    silently measures the parent's mutation instead of the child's behaviour -- it did,
    on the first run. ``strip_flopy_bin`` removes that entry so the child genuinely
    starts without it.
    """
    import os

    env = dict(os.environ)
    if strip_flopy_bin:
        import flopy

        bindir = str(Path(flopy.__file__).parent / "bin")
        home_bin = str(Path.home() / ".local" / "share" / "flopy" / "bin")
        env["PATH"] = os.pathsep.join(
            part for part in env.get("PATH", "").split(os.pathsep)
            if part and part not in (bindir, home_bin))
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)],
                          capture_output=True, text=True, timeout=120,
                          env=env).stdout.strip()


def test_which_is_blind_until_flopy_is_imported():
    """🔴 The trap: `shutil.which('mf6')` is None on a HEALTHY install until flopy is
    imported. A which-based probe would report a false failure everywhere."""
    out = _probe("""
        import shutil
        before = shutil.which("mf6")
        import flopy
        after = shutil.which("mf6")
        print(f"{before!r}|{bool(after)}")
    """, strip_flopy_bin=True)
    before, after_ok = out.split("|")
    assert before == "None", f"expected which() blind before import, got {before}"
    assert after_ok == "True", "flopy did not put its bin dir on PATH at import"


def test_resolve_exe_finds_the_flopy_managed_bin():
    """The probe the preflight uses must resolve into flopy's OWN bin dir."""
    out = _probe("""
        import flopy
        from flopy.mbase import resolve_exe
        print(resolve_exe("triangle"))
    """)
    assert out, "triangle did not resolve"
    assert "flopy" in out and "bin" in out, out


# --- 4. the refine diagnostics ----------------------------------------------

def test_refine_failure_keeps_the_exception_message_not_just_its_type():
    import inspect
    import casestudy_flow_builder as cfb
    src = inspect.getsource(cfb._refine_solve_baseline_walk)
    assert "type(e).__name__" in src
    assert "_msg" in src, "the exception message is discarded again"


def test_refine_failure_names_the_radii_actually_tried():
    """It printed the 5-radius FALLBACK ladder even when ONE pinned radius was used."""
    import inspect
    import casestudy_flow_builder as cfb
    src = inspect.getsource(cfb._refine_solve_baseline_walk)
    assert "FALLBACK_REFINE_RADII} (attempts" not in src, (
        "the failure text claims five radii were tried when one was")
    assert "_radii" in src.split("raise RuntimeError")[1]
