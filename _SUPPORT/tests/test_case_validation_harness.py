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

import os
import subprocess
import sys
import time
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


def _stage_main_style(group):
    """A plain top-level function whose __module__ gets monkeypatched to
    '__main__' in test_register_main_style_function_rejected, to simulate a
    stage defined in a script run directly (`python script.py`)."""
    return None


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

    def test_require_green_nonzero_when_unimplemented(self, tmp_path):
        # Exercise via the CLI's main() so the in-process registry (or lack
        # thereof) is honored -- a subprocess CLI invocation would run in a
        # fresh interpreter with an empty registry too, but going through the
        # module directly keeps this test symmetric with the SIGILL test
        # below, which *needs* the shared in-process registry.
        #
        # --require-green is a release gate and now requires the full
        # canonical 0-8 group set (case_validation.CANONICAL_GROUPS), so both
        # invocations use "0-8" to exercise a real release-gate run rather
        # than the single-group "0" used previously.
        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        # Write the incidental report into the test's own tmp_path -- never
        # into Path.cwd() (which may be the repo root during a local run) --
        # so the test leaves nothing behind on disk anywhere.
        rc_plain = vcsr.main(["--groups", "0-8", "--out", str(tmp_path / "_unused_report.json")])
        rc_green = vcsr.main(["--groups", "0-8", "--require-green"])

        assert rc_plain == 0
        assert rc_green != 0


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
        # --require-green now (a) cannot be combined with --stage and (b)
        # requires the full canonical 0-8 group set (see Fix 2 in
        # case_validation / the CLI). So rc_plain exercises the old
        # single-stage/single-group path (still allowed without
        # --require-green), while rc_green registers every required stage
        # (all passing except "scenario", which crashes via SIGILL) and runs
        # the full release-gate invocation across all 9 groups.
        for stage_id in REQUIRED_STAGES:
            cv.register_stage(stage_id, _stage_sigill if stage_id == "scenario" else _stage_pass)

        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        rc_plain = vcsr.main(["--groups", "0", "--stage", "scenario"])
        rc_green = vcsr.main(["--groups", "0-8", "--require-green"])

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

    def test_register_functools_partial_rejected(self):
        import functools

        partial_fn = functools.partial(_stage_pass)
        with pytest.raises(ValueError):
            cv.register_stage("config", partial_fn)

    def test_register_callable_class_instance_rejected(self):
        class _CallableStage:
            def __call__(self, group):
                return None

        with pytest.raises(ValueError):
            cv.register_stage("config", _CallableStage())

    def test_register_main_style_function_rejected(self):
        # Simulate a function that was defined in a script run directly
        # (`python script.py`), where CPython sets __module__ == "__main__".
        # Uses a dedicated module-level function (not a nested def) so the
        # __qualname__ check doesn't fire first for an unrelated reason.
        original_module = _stage_main_style.__module__
        _stage_main_style.__module__ = "__main__"
        try:
            with pytest.raises(ValueError):
                cv.register_stage("config", _stage_main_style)
        finally:
            _stage_main_style.__module__ = original_module


# =============================================================================
# Fix 1 (BLOCKER): is_green must not be foolable by SKIP
# =============================================================================

class TestFalseGreenClosed:
    def test_partial_skip_report_is_not_green(self):
        """One required stage PASS, the other 9 SKIP -- must NOT be green.

        This is the exact shape a `--stage config --require-green` run used
        to produce before the fix (config PASS, everything else SKIP because
        --stage restricts execution), which incorrectly reported green.
        """
        stages = []
        for stage_id in REQUIRED_STAGES:
            if stage_id == "config":
                stages.append({"id": stage_id, "status": "PASS", "reason": "", "elapsed_s": 0.1})
            else:
                stages.append({
                    "id": stage_id,
                    "status": "SKIP",
                    "reason": "not selected (--stage config)",
                    "elapsed_s": 0.0,
                })
        report = {"schema_version": cv.SCHEMA_VERSION, "groups": [{"group": 0, "stages": stages}]}

        assert cv.is_green(report) is False

    def test_all_pass_report_is_green(self):
        stages = [
            {"id": stage_id, "status": "PASS", "reason": "", "elapsed_s": 0.1}
            for stage_id in REQUIRED_STAGES
        ]
        report = {"schema_version": cv.SCHEMA_VERSION, "groups": [{"group": 0, "stages": stages}]}

        assert cv.is_green(report) is True

    def test_cli_rejects_require_green_combined_with_stage(self):
        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        cv.register_stage("config", _stage_pass)
        rc = vcsr.main(["--stage", "config", "--require-green"])

        assert rc == 2


# =============================================================================
# Fix 2: release-gate group-domain integrity (CANONICAL_GROUPS)
# =============================================================================

class TestGroupDomain:
    def test_canonical_groups_is_0_through_8(self):
        assert cv.CANONICAL_GROUPS == tuple(range(9))

    def test_cli_rejects_out_of_domain_group_id(self):
        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        rc = vcsr.main(["--groups", "999", "--plan-only"])
        assert rc == 2

    def test_cli_rejects_huge_out_of_domain_range(self):
        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        rc = vcsr.main(["--groups", "0-999999999", "--plan-only"])
        assert rc == 2

    def test_cli_rejects_require_green_with_partial_group_set(self):
        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        rc = vcsr.main(["--groups", "0", "--require-green"])
        assert rc == 2

    def test_cli_require_green_full_group_set_but_unimplemented_is_nonzero(self):
        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        rc = vcsr.main(["--groups", "0-8", "--require-green"])
        assert rc != 0

    def test_parse_groups_spec_caps_absurd_range_span(self):
        with pytest.raises(ValueError):
            cv.parse_groups_spec("0-999999999")

    def test_parse_groups_spec_still_accepts_normal_ranges(self):
        assert cv.parse_groups_spec("0-8") == list(range(9))


# =============================================================================
# Fix B1 (MAJOR): --plan-only combined with --require-green must be rejected
# =============================================================================

class TestPlanOnlyRequireGreenRejected:
    def test_cli_rejects_plan_only_combined_with_require_green(self):
        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        rc = vcsr.main(["--plan-only", "--require-green", "--groups", "0-8"])
        assert rc == 2


# =============================================================================
# Fix B2 (MAJOR): is_green is a strict PASS-whitelist
# =============================================================================

class TestIsGreenStrictWhitelist:
    def test_empty_dict_report_is_not_green(self):
        assert cv.is_green({}) is False

    def test_empty_groups_list_is_not_green(self):
        assert cv.is_green({"groups": []}) is False

    def _passing_stages(self):
        return [
            {"id": stage_id, "status": "PASS", "reason": "", "elapsed_s": 0.1}
            for stage_id in REQUIRED_STAGES
        ]

    def test_bogus_status_on_required_stage_is_not_green(self):
        stages = self._passing_stages()
        stages[0]["status"] = "BOGUS"
        report = {"schema_version": cv.SCHEMA_VERSION, "groups": [{"group": 0, "stages": stages}]}

        assert cv.is_green(report) is False

    def test_group_missing_a_required_stage_is_not_green(self):
        stages = [s for s in self._passing_stages() if s["id"] != REQUIRED_STAGES[0]]
        report = {"schema_version": cv.SCHEMA_VERSION, "groups": [{"group": 0, "stages": stages}]}

        assert cv.is_green(report) is False

    def test_duplicate_stage_entry_one_pass_one_fail_is_not_green(self):
        stages = self._passing_stages()
        # Duplicate the first required stage's entry, but make the
        # duplicate FAIL. A blacklist keyed only by "does some entry with
        # this id have a bad status" done naively could still be fooled by
        # ordering; the whitelist rejects as soon as ANY entry for a
        # required id is not PASS.
        dup = dict(stages[0])
        dup["status"] = "FAIL"
        stages.append(dup)
        report = {"schema_version": cv.SCHEMA_VERSION, "groups": [{"group": 0, "stages": stages}]}

        assert cv.is_green(report) is False


# =============================================================================
# Fix B3 (MINOR): --out I/O failure must not raise an uncaught traceback
# =============================================================================

class TestOutWriteFailureHandled:
    def test_cli_out_to_unwritable_path_exits_2_not_traceback(self, tmp_path):
        import importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "scripts"))
        vcsr = importlib.import_module("validate_case_study_redesign")

        # A path whose parent directory does not exist and cannot be
        # created implicitly (Path.write_text does not mkdir parents) is a
        # reliable, portable way to trigger an OSError (FileNotFoundError)
        # on write, regardless of platform permission semantics.
        bad_out = tmp_path / "does_not_exist" / "nested" / "report.json"

        rc = vcsr.main(["--groups", "0", "--plan-only", "--out", str(bad_out)])
        assert rc == 2
        assert not bad_out.exists()


# =============================================================================
# Load-bearing regression: process-group kill on TIMEOUT reaps grandchildren
# =============================================================================

def _stage_spawns_grandchild(group):
    """Spawn a long-lived grandchild, record its PID, then sleep past the
    test's short stage timeout. Used to prove that _run_stage_subprocess's
    TIMEOUT handling kills the WHOLE process group (os.killpg), not just the
    direct child -- otherwise a stage that spawns e.g. MODFLOW would leak
    that grandchild process past the timeout."""
    import subprocess
    import time

    pid_file = group  # `group` is (ab)used to pass the pid-file path (a str)
    grandchild = subprocess.Popen(["sleep", "120"])
    with open(pid_file, "w", encoding="utf-8") as fh:
        fh.write(str(grandchild.pid))
    time.sleep(120)


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group semantics only")
class TestGrandchildReapedOnTimeout:
    def test_timeout_kills_whole_process_group_including_grandchild(self, tmp_path):
        pid_file = tmp_path / "grandchild.pid"
        cv.register_stage("cards", _stage_spawns_grandchild, timeout_s=1.0)

        grandchild_pid = None
        try:
            report = cv.run_validation([str(pid_file)], stage="cards", plan_only=False)
            cards = report["groups"][0]["stages"][REQUIRED_STAGES.index("cards")]
            assert cards["status"] == "TIMEOUT"

            # Give the killed grandchild a brief moment to actually be
            # reaped by the OS after the SIGKILL.
            deadline = time.monotonic() + 5.0
            grandchild_pid = int(pid_file.read_text(encoding="utf-8").strip())
            while time.monotonic() < deadline:
                try:
                    os.kill(grandchild_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                pytest.fail(
                    f"grandchild pid {grandchild_pid} still alive after timeout+kill "
                    "-- process-group kill did not reap it"
                )

            with pytest.raises(ProcessLookupError):
                os.kill(grandchild_pid, 0)
        finally:
            # Best-effort cleanup so a test failure never leaks a real
            # `sleep 120` process.
            if grandchild_pid is not None:
                try:
                    os.kill(grandchild_pid, 9)
                except (ProcessLookupError, PermissionError):
                    pass
