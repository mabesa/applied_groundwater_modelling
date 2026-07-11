"""
Unit tests for the case_validation instructor validation harness skeleton
(library: _SUPPORT/src/case_validation.py, CLI:
_SUPPORT/src/scripts/validate_case_study_redesign.py).

Tests cover:
- `--groups 0-8 --plan-only` via a subprocess CLI invocation exits 0, and the
  report (checked at the function level) lists all 10 canonical stage ids for
  every one of groups 0..8, without executing any stage body.
- A fixture stage that exits via SIGILL is recorded as a single FAILED stage
  (with a reason mentioning the signal), other groups/stages still run, and
  --require-green flips the CLI's exit code accordingly.
- A required stage left unimplemented is reported NOT_IMPLEMENTED; plain mode
  exits 0, --require-green exits non-zero.
- A stage that sleeps past a short timeout is reported TIMEOUT.
- A registered stage that simply succeeds is reported PASS (sanity check that
  the subprocess round-trip itself works, not just the failure paths).

Run with: uv run pytest _SUPPORT/tests/test_case_validation_harness.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Add src to path (mirrors the style used by other tests in this directory)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import case_validation as cv
from case_validation import REQUIRED_STAGES

_CLI_SCRIPT = Path(__file__).parent.parent / "src" / "scripts" / "validate_case_study_redesign.py"


# =============================================================================
# Module-level fixture stage functions.
#
# These MUST be top-level (module-level) functions: register_stage() runs
# them in a fresh subprocess by re-importing (module, qualname), which is
# rejected for lambdas/closures/methods (their __qualname__ contains "." or
# "<locals>").
# =============================================================================

def _stage_pass(group):
    """A trivial stage that always succeeds."""
    return None


def _stage_sigill(group):
    """A stage that crashes the process via SIGILL (exit code 132 / -4)."""
    import os
    import signal

    os.kill(os.getpid(), signal.SIGILL)


def _stage_sleep_long(group):
    """A stage that sleeps well past any short test timeout."""
    import time

    time.sleep(5)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure no stage registration leaks between tests."""
    cv.clear_registry()
    yield
    cv.clear_registry()


# =============================================================================
# plan-only: full stage enumeration, no execution
# =============================================================================

class TestPlanOnly:
    def test_function_level_plan_lists_all_stages_for_all_groups(self):
        groups = list(range(9))  # 0..8
        report = cv.run_validation(groups, plan_only=True)

        assert report["schema_version"]
        assert len(report["groups"]) == 9

        for g in report["groups"]:
            stage_ids = [s["id"] for s in g["stages"]]
            assert stage_ids == list(REQUIRED_STAGES)
            for s in g["stages"]:
                assert s["elapsed_s"] == 0
                # No stage body executes in plan mode.
                assert s["status"] in ("SKIP", "NOT_IMPLEMENTED")

    def test_cli_plan_only_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(_CLI_SCRIPT), "--groups", "0-8", "--plan-only"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"

        import json
        report = json.loads(result.stdout)
        assert len(report["groups"]) == 9
        for g in report["groups"]:
            stage_ids = [s["id"] for s in g["stages"]]
            assert stage_ids == list(REQUIRED_STAGES)


# =============================================================================
# Unimplemented required stage
# =============================================================================

class TestNotImplemented:
    def test_unregistered_stage_is_not_implemented(self):
        report = cv.run_validation([0], plan_only=False)
        for s in report["groups"][0]["stages"]:
            assert s["status"] == "NOT_IMPLEMENTED"
        assert cv.is_green(report) is False

    def test_require_green_nonzero_when_unimplemented(self):
        # Exercise via the CLI's main() so the in-process registry (or lack
        # thereof) is honored -- a subprocess CLI invocation would run in a
        # fresh interpreter with an empty registry too, but going through the
        # module directly keeps this test symmetric with the SIGILL test
        # below, which *needs* the shared in-process registry.
        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        rc_plain = vcsr.main(["--groups", "0", "--out", str(Path.cwd() / "_unused_report.json")])
        rc_green = vcsr.main(["--groups", "0", "--require-green"])

        assert rc_plain == 0
        assert rc_green != 0

        # Clean up the incidental report file written above.
        Path.cwd().joinpath("_unused_report.json").unlink(missing_ok=True)


# =============================================================================
# SIGILL fixture stage
# =============================================================================

class TestSigillStage:
    def test_sigill_recorded_as_single_failed_stage_other_groups_still_run(self):
        cv.register_stage("scenario", _stage_sigill)

        groups = [0, 1, 2]
        report = cv.run_validation(groups, plan_only=False)

        assert len(report["groups"]) == 3  # all groups ran, none skipped
        for g in report["groups"]:
            stages_by_id = {s["id"]: s for s in g["stages"]}

            scenario = stages_by_id["scenario"]
            assert scenario["status"] == "FAIL"
            assert scenario["reason"], "expected a non-empty reason for the SIGILL failure"
            reason_lower = scenario["reason"].lower()
            assert "sigill" in reason_lower or "signal" in reason_lower or "132" in reason_lower

            # Other canonical stages were still attempted (not aborted).
            other_ids = set(REQUIRED_STAGES) - {"scenario"}
            for oid in other_ids:
                assert stages_by_id[oid]["status"] == "NOT_IMPLEMENTED"

    def test_require_green_flips_exit_code_around_sigill_stage(self):
        cv.register_stage("scenario", _stage_sigill)

        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        rc_plain = vcsr.main(["--groups", "0", "--stage", "scenario"])
        rc_green = vcsr.main(["--groups", "0", "--stage", "scenario", "--require-green"])

        assert rc_plain == 0
        assert rc_green != 0


# =============================================================================
# Timeout
# =============================================================================

class TestTimeout:
    def test_stage_exceeding_timeout_is_reported_timeout(self):
        cv.register_stage("cards", _stage_sleep_long, timeout_s=0.5)

        report = cv.run_validation([0], stage="cards", plan_only=False)
        cards = report["groups"][0]["stages"][REQUIRED_STAGES.index("cards")]

        assert cards["status"] == "TIMEOUT"
        assert cards["reason"]


# =============================================================================
# Happy path sanity check
# =============================================================================

class TestPassingStage:
    def test_registered_passing_stage_reports_pass(self):
        cv.register_stage("config", _stage_pass)

        report = cv.run_validation([0], stage="config", plan_only=False)
        config = report["groups"][0]["stages"][REQUIRED_STAGES.index("config")]

        assert config["status"] == "PASS"
        assert config["elapsed_s"] >= 0


# =============================================================================
# Registry hygiene
# =============================================================================

class TestRegistryValidation:
    def test_register_unknown_stage_id_raises(self):
        with pytest.raises(ValueError):
            cv.register_stage("not_a_real_stage", _stage_pass)

    def test_register_lambda_rejected(self):
        with pytest.raises(ValueError):
            cv.register_stage("config", lambda group: None)

    def test_clear_registry_empties_it(self):
        cv.register_stage("config", _stage_pass)
        assert cv.registered_stages() == ["config"]
        cv.clear_registry()
        assert cv.registered_stages() == []
