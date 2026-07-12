"""
LOCKED acceptance tests for milestone M2-config-linter.

This milestone adds a per-group transport-config COVERAGE LINTER that fails
LOUDLY (before any expensive Hub generation) when a group's transport config is
incomplete/invalid, and wires it into the M1 validation harness as the real
``config`` stage.

Surface under test
------------------
  * A function ``lint_transport_config(config_path=None, groups=range(9))``
    (primary home: ``_SUPPORT/src/case_utils.py``; a clearly-named sibling
    module is also accepted). It parses ``case_config_transport.yaml`` and, for
    EACH requested group id, asserts:
      - exactly one ``transport_scenarios.options`` entry with ``id == group``;
      - a ``doublet`` with numeric injection/extraction easting+northing,
        ``pumping_rate_m3_d > 0`` and ``0 <= recirculation_fraction <= 1``;
      - a ``source`` with ``type``, ``release_type``,
        ``location{easting, northing, layer}``, ``duration_days >= 1`` and a
        numeric ``concentration_mg_L``;
      - a ``simulation`` with ``duration_days > 0`` and a non-empty,
        strictly-increasing ``output_times_days`` list;
      - a ``submodel`` with a positive ``cell_size_m``;
      - a ``monitoring`` with a numeric ``threshold_mg_L``.
    On any missing/invalid field it raises a clear ``ValueError`` naming the
    group AND the offending field/reason. On success it returns a structured
    per-group coverage report.
  * Default (``config_path=None``) reads the repo's
    ``PROJECT/workspace/template/case_config_transport.yaml`` but honors the
    ``AGM_TRANSPORT_CONFIG`` env var as a path override.
  * ``case_stages.config_stage(group)`` — a TOP-LEVEL function that lints a
    single group (returns None on success; raises on failure) — and
    ``register_flow_stages()`` ALSO registers it under the ``'config'`` stage
    id. Importing ``case_stages`` registers nothing; registration is explicit
    and idempotent.
  * End-to-end: ``run_validation([g], stage='config')`` (real per-stage
    subprocess) reports PASS for a group with a complete config (the REAL yaml)
    and FAIL for a group whose config is broken (via ``AGM_TRANSPORT_CONFIG``).

LOCKED-TEST SCOPING: NO test here runs MODFLOW or grid refinement — pure
YAML/config validation. Failure cases use SYNTHETIC broken YAML written to a
tmp path and selected via the env-var override (or an explicit ``config_path``).

Run with:  uv run pytest _SUPPORT/tests/test_case_config_linter.py -v
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import case_validation as cv  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_CONFIG = REPO_ROOT / "PROJECT" / "workspace" / "template" / "case_config_transport.yaml"
_CLI_SCRIPT = SRC_DIR / "scripts" / "validate_case_study_redesign.py"

ENV_VAR = "AGM_TRANSPORT_CONFIG"

# Modules the linter is allowed to live in (case_utils primary; a clearly-named
# sibling is explicitly permitted by the milestone brief).
_LINT_MODULE_CANDIDATES = (
    "case_utils",
    "case_config_lint",
    "config_lint",
    "transport_config_lint",
    "case_stages",
)

# Forbidden tokens: the linter (and config_stage) must be pure YAML/config
# validation — never MODFLOW / grid refinement.
_FORBIDDEN_TOKENS = (
    "flopy",
    "run_simulation",
    "MFSimulation",
    "create_disv_from_boundary",
    "refine_grid_locally",
    "build_refined_gwf_model",
    "load_pinned_flow_model",
    "assemble_gwf_from_spec",
)


# ---------------------------------------------------------------------------
# Import helpers (do not pin the exact module the linter lives in)
# ---------------------------------------------------------------------------

def _import_lint():
    last = None
    for name in _LINT_MODULE_CANDIDATES:
        try:
            mod = importlib.import_module(name)
        except Exception as exc:  # module may not import cleanly; keep looking
            last = exc
            continue
        fn = getattr(mod, "lint_transport_config", None)
        if fn is not None:
            return fn
    raise AssertionError(
        "lint_transport_config not found in any of "
        f"{_LINT_MODULE_CANDIDATES!r} (last import error: {last!r})"
    )


# ---------------------------------------------------------------------------
# Synthetic (valid) config builders — mutated to break ONE field per neg test.
# Values are structurally valid but otherwise arbitrary; tests never pin them.
# ---------------------------------------------------------------------------

def _valid_entry(gid):
    return {
        "id": gid,
        "title": f"synthetic group {gid}",
        "doublet": {
            "injection_easting": 2681745.9,
            "injection_northing": 1248144.8,
            "extraction_easting": 2681799.9,
            "extraction_northing": 1248143.8,
            "pumping_rate_m3_d": 1370,
            "recirculation_fraction": 0.2,
        },
        "source": {
            "type": "point",
            "release_type": "pulse",
            "location": {"easting": 51.0, "northing": -77.0, "layer": 1},
            "duration_days": 1,
            "concentration_mg_L": 100.0,
        },
        "simulation": {
            "duration_days": 60,
            "output_times_days": [6, 11, 21, 61],
        },
        "submodel": {"cell_size_m": 2},
        "monitoring": {"threshold_mg_L": 5.0},
    }


def _valid_config(gids=(0,)):
    return {"transport_scenarios": {"options": [_valid_entry(g) for g in gids]}}


def _write_yaml(path: Path, cfg: dict) -> Path:
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _broken_config_path(tmp_path: Path, mutate, gid=0, name="broken.yaml") -> Path:
    """Build a valid single-group config, apply ``mutate`` (in place) to break
    exactly one field, and write it to a tmp YAML; return the path."""
    cfg = _valid_config((gid,))
    entry = cfg["transport_scenarios"]["options"][0]
    mutate(cfg, entry)
    return _write_yaml(tmp_path / name, cfg)


# ---------------------------------------------------------------------------
# Coverage-report shape helpers (tolerant to the exact structure; the brief
# only requires a per-group structured report "e.g. per-group dict").
# ---------------------------------------------------------------------------

def _gid_of(item):
    if isinstance(item, dict):
        for k in ("group", "id", "group_id"):
            if k in item:
                return int(item[k])
    raise AssertionError(f"cannot find a group id in report item {item!r}")


def _group_map(report):
    """Return {group_id: sub_report} regardless of the concrete container."""
    assert report is not None, "coverage report must not be None on success"
    if isinstance(report, dict):
        if "groups" in report and isinstance(report["groups"], list):
            return {_gid_of(x): x for x in report["groups"]}
        return {int(k): v for k, v in report.items()}
    if isinstance(report, (list, tuple)):
        return {_gid_of(x): x for x in report}
    raise AssertionError(f"unexpected coverage report type {type(report)!r}")


# ---------------------------------------------------------------------------
# Harness helpers
# ---------------------------------------------------------------------------

def _run_cli(args, env_extra=None):
    env = dict(os.environ)
    # Never let an ambient override leak into a CLI test.
    env.pop(ENV_VAR, None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), *args],
        capture_output=True, text=True, timeout=120, env=env,
    )


def _stage_entry(report, group, stage_id):
    for g in report["groups"]:
        if g["group"] == group:
            for s in g["stages"]:
                if s["id"] == stage_id:
                    return s
    raise AssertionError(f"{stage_id} entry for group {group} not found in report")


@pytest.fixture(autouse=True)
def _clean_registry():
    cv.clear_registry()
    yield
    cv.clear_registry()


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    # Ensure no ambient AGM_TRANSPORT_CONFIG bleeds into default-path tests.
    monkeypatch.delenv(ENV_VAR, raising=False)


# =============================================================================
# Sanity: the real config file exists (default-path target).
# =============================================================================

def test_real_config_file_exists():
    assert REAL_CONFIG.is_file(), f"expected real transport config at {REAL_CONFIG}"


# =============================================================================
# Criterion 1 + 5 — happy path on the REAL config, all 9 groups.
# =============================================================================

class TestHappyPathRealConfig:
    def test_default_args_lint_all_nine_groups(self):
        # Default config_path (real repo file) and default groups=range(9):
        # the CURRENT real config must lint clean for every group 0-8.
        lint = _import_lint()
        report = lint()
        gmap = _group_map(report)
        assert set(range(9)) <= set(gmap), (
            f"coverage report must cover groups 0-8, got {sorted(gmap)}"
        )

    def test_explicit_real_path_subset_returns_per_group_report(self):
        lint = _import_lint()
        report = lint(config_path=str(REAL_CONFIG), groups=[0, 4, 8])
        gmap = _group_map(report)
        assert {0, 4, 8} <= set(gmap)
        # Each requested group has a non-empty structured sub-report.
        for g in (0, 4, 8):
            assert gmap[g], f"group {g} sub-report must carry resolved values"

    def test_single_group_via_range(self):
        lint = _import_lint()
        report = lint(config_path=str(REAL_CONFIG), groups=range(1))
        assert 0 in _group_map(report)


# =============================================================================
# Criterion 2 — default path + AGM_TRANSPORT_CONFIG override.
# =============================================================================

class TestConfigPathResolution:
    def test_env_var_override_is_honored_for_failures(self, tmp_path, monkeypatch):
        # A broken synthetic config selected via the env var must raise, even
        # though the REAL default config for the same group is valid — proving
        # the override is actually consulted (not a hardcoded default).
        broken = _broken_config_path(
            tmp_path, lambda cfg, e: e.pop("doublet"), gid=0
        )
        monkeypatch.setenv(ENV_VAR, str(broken))
        lint = _import_lint()
        with pytest.raises(ValueError):
            lint(groups=[0])  # config_path=None => env var override used

    def test_env_var_override_valid_synthetic_passes(self, tmp_path, monkeypatch):
        valid = _write_yaml(tmp_path / "ok.yaml", _valid_config((0,)))
        monkeypatch.setenv(ENV_VAR, str(valid))
        lint = _import_lint()
        report = lint(groups=[0])
        assert 0 in _group_map(report)

    def test_explicit_config_path_argument_used(self, tmp_path):
        valid = _write_yaml(tmp_path / "explicit.yaml", _valid_config((0, 1)))
        lint = _import_lint()
        report = lint(config_path=str(valid), groups=[0, 1])
        assert {0, 1} <= set(_group_map(report))


# =============================================================================
# Criterion 1 (negative) — every required field, on synthetic broken YAML.
# A representative subset also asserts the message names the group AND field.
# =============================================================================

def _assert_names_group_and_field(exc, gid, field_token):
    msg = str(exc.value)
    assert "group" in msg.lower() and str(gid) in msg, (
        f"error must NAME the group {gid}: {msg!r}"
    )
    assert field_token in msg, (
        f"error must name the offending field ({field_token!r}): {msg!r}"
    )


class TestGroupSelection:
    def test_missing_group_raises(self, tmp_path):
        # Config has group 1 only; requesting group 0 => no matching entry.
        path = _write_yaml(tmp_path / "c.yaml", _valid_config((1,)))
        lint = _import_lint()
        with pytest.raises(ValueError) as exc:
            lint(config_path=str(path), groups=[0])
        assert "0" in str(exc.value)

    def test_duplicate_group_raises(self, tmp_path):
        cfg = _valid_config((0,))
        cfg["transport_scenarios"]["options"].append(_valid_entry(0))  # dup id
        path = _write_yaml(tmp_path / "c.yaml", cfg)
        lint = _import_lint()
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[0])


class TestDoubletValidation:
    def _lint_broken(self, tmp_path, mutate, gid=0):
        path = _broken_config_path(tmp_path, mutate, gid=gid)
        return _import_lint(), path, gid

    def test_missing_doublet_block_raises_naming_group_and_field(self, tmp_path):
        lint, path, gid = self._lint_broken(tmp_path, lambda c, e: e.pop("doublet"), gid=3)
        with pytest.raises(ValueError) as exc:
            lint(config_path=str(path), groups=[gid])
        _assert_names_group_and_field(exc, gid, "doublet")

    def test_non_numeric_injection_easting_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["doublet"].__setitem__("injection_easting", "NaNsense")
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_missing_extraction_northing_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["doublet"].pop("extraction_northing")
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_non_positive_pumping_rate_raises_naming_group_and_field(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["doublet"].__setitem__("pumping_rate_m3_d", 0), gid=2
        )
        with pytest.raises(ValueError) as exc:
            lint(config_path=str(path), groups=[gid])
        _assert_names_group_and_field(exc, gid, "pumping_rate_m3_d")

    def test_recirculation_above_one_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["doublet"].__setitem__("recirculation_fraction", 1.5)
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_recirculation_below_zero_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["doublet"].__setitem__("recirculation_fraction", -0.01)
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])


class TestSourceValidation:
    def _lint_broken(self, tmp_path, mutate, gid=0):
        path = _broken_config_path(tmp_path, mutate, gid=gid)
        return _import_lint(), path, gid

    def test_missing_type_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(tmp_path, lambda c, e: e["source"].pop("type"))
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_missing_release_type_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["source"].pop("release_type")
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_missing_location_easting_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["source"]["location"].pop("easting")
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_missing_location_northing_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["source"]["location"].pop("northing")
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_missing_location_layer_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["source"]["location"].pop("layer")
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_duration_below_one_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["source"].__setitem__("duration_days", 0)
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_non_numeric_concentration_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["source"].__setitem__("concentration_mg_L", "high")
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])


class TestSimulationValidation:
    def _lint_broken(self, tmp_path, mutate, gid=0):
        path = _broken_config_path(tmp_path, mutate, gid=gid)
        return _import_lint(), path, gid

    def test_non_positive_duration_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["simulation"].__setitem__("duration_days", 0)
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_empty_output_times_raises(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path, lambda c, e: e["simulation"].__setitem__("output_times_days", [])
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])

    def test_non_increasing_output_times_raises_naming_group_and_field(self, tmp_path):
        lint, path, gid = self._lint_broken(
            tmp_path,
            lambda c, e: e["simulation"].__setitem__("output_times_days", [10, 5, 20]),
            gid=6,
        )
        with pytest.raises(ValueError) as exc:
            lint(config_path=str(path), groups=[gid])
        _assert_names_group_and_field(exc, gid, "output_times_days")

    def test_equal_consecutive_output_times_raises(self, tmp_path):
        # Strictly increasing => equal consecutive values are invalid.
        lint, path, gid = self._lint_broken(
            tmp_path,
            lambda c, e: e["simulation"].__setitem__("output_times_days", [5, 5, 20]),
        )
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[gid])


class TestSubmodelValidation:
    def test_non_positive_cell_size_raises(self, tmp_path):
        path = _broken_config_path(
            tmp_path, lambda c, e: e["submodel"].__setitem__("cell_size_m", 0)
        )
        lint = _import_lint()
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[0])

    def test_missing_submodel_block_raises(self, tmp_path):
        path = _broken_config_path(tmp_path, lambda c, e: e.pop("submodel"))
        lint = _import_lint()
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[0])


class TestMonitoringValidation:
    def test_non_numeric_threshold_raises(self, tmp_path):
        path = _broken_config_path(
            tmp_path, lambda c, e: e["monitoring"].__setitem__("threshold_mg_L", "low")
        )
        lint = _import_lint()
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[0])

    def test_missing_monitoring_block_raises(self, tmp_path):
        path = _broken_config_path(tmp_path, lambda c, e: e.pop("monitoring"))
        lint = _import_lint()
        with pytest.raises(ValueError):
            lint(config_path=str(path), groups=[0])


# =============================================================================
# Criterion 6 — LOCKED scoping: the linter is pure YAML/config validation.
# =============================================================================

class TestNoModflowInLinter:
    def test_linter_source_has_no_modflow_tokens(self):
        lint = _import_lint()
        src = inspect.getsource(lint)
        for tok in _FORBIDDEN_TOKENS:
            assert tok not in src, f"lint_transport_config must not reference {tok!r}"


# =============================================================================
# Criterion 3 — config_stage top-level fn + explicit, idempotent registration.
# =============================================================================

class TestConfigStageShape:
    def test_config_stage_is_plain_top_level_function(self):
        import case_stages

        fn = case_stages.config_stage
        assert inspect.isfunction(fn)
        assert "." not in fn.__qualname__, fn.__qualname__
        assert "<" not in fn.__qualname__, fn.__qualname__
        assert fn.__module__ != "__main__"

    def test_register_stage_accepts_config_stage_directly(self):
        import case_stages

        cv.register_stage("config", case_stages.config_stage)
        assert "config" in cv.registered_stages()

    def test_config_stage_source_has_no_modflow_tokens(self):
        import case_stages

        src = inspect.getsource(case_stages.config_stage)
        for tok in _FORBIDDEN_TOKENS:
            assert tok not in src, f"config_stage must not reference {tok!r}"


class TestConfigStageBehavior:
    def test_returns_none_on_valid_real_config(self, monkeypatch):
        monkeypatch.delenv(ENV_VAR, raising=False)
        import case_stages

        assert case_stages.config_stage(0) is None

    def test_raises_on_broken_config_via_env(self, tmp_path, monkeypatch):
        broken = _broken_config_path(tmp_path, lambda c, e: e.pop("doublet"), gid=0)
        monkeypatch.setenv(ENV_VAR, str(broken))
        import case_stages

        # config_stage must propagate the linter's ValueError (not merely
        # "some exception" — an AttributeError from a missing config_stage,
        # for instance, must NOT satisfy this).
        with pytest.raises(ValueError):
            case_stages.config_stage(0)


class TestImportTimeAndRegistration:
    def test_import_case_stages_registers_nothing(self):
        # Fresh interpreter => a true import-time observation.
        code = (
            "import sys;"
            f"sys.path.insert(0, {str(SRC_DIR)!r});"
            "import case_validation as cv;"
            "import case_stages;"
            "assert cv.registered_stages() == [], cv.registered_stages()"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
        )
        assert result.returncode == 0, (
            f"importing case_stages must register nothing.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_register_flow_stages_also_registers_config(self):
        import case_stages

        assert "config" not in cv.registered_stages()
        case_stages.register_flow_stages()
        assert "config" in cv.registered_stages()

    def test_register_config_under_correct_fn(self):
        import case_stages

        case_stages.register_flow_stages()
        fn, _timeout = cv._REGISTRY["config"]
        assert fn is case_stages.config_stage

    def test_registration_is_idempotent(self):
        import case_stages

        case_stages.register_flow_stages()
        case_stages.register_flow_stages()
        assert cv.registered_stages().count("config") == 1


# =============================================================================
# Criterion 4 — HARD end-to-end: run_validation stage='config' through the
# REAL per-stage subprocess reports PASS (complete real config) and FAIL
# (broken synthetic config via AGM_TRANSPORT_CONFIG). MODFLOW-free.
# =============================================================================

def _config_status(report):
    return next(
        s for g in report["groups"] for s in g["stages"] if s["id"] == "config"
    )


class TestHarnessSubprocessEndToEnd:
    def test_run_validation_passes_for_complete_group(self, monkeypatch):
        monkeypatch.delenv(ENV_VAR, raising=False)
        import case_stages

        case_stages.register_flow_stages()
        report = cv.run_validation([0], stage="config")
        assert _config_status(report)["status"] == "PASS", report

    def test_run_validation_fails_for_broken_group(self, tmp_path, monkeypatch):
        broken = _broken_config_path(tmp_path, lambda c, e: e.pop("simulation"), gid=0)
        monkeypatch.setenv(ENV_VAR, str(broken))
        import case_stages

        case_stages.register_flow_stages()
        report = cv.run_validation([0], stage="config")
        status = _config_status(report)["status"]
        assert status == "FAIL", report


# =============================================================================
# Criterion 4 (CLI fidelity) — the same PASS/FAIL contract via the actual CLI
# harness process, which registers the config stage before validating.
# =============================================================================

class TestCliWiring:
    def test_cli_config_passes_on_real_config(self):
        result = _run_cli(["--groups", "0", "--stage", "config"])
        assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        report = json.loads(result.stdout)
        entry = _stage_entry(report, 0, "config")
        assert entry["status"] == "PASS", entry

    def test_cli_config_is_registered_not_unimplemented(self, tmp_path):
        broken = _broken_config_path(tmp_path, lambda c, e: e.pop("monitoring"), gid=0)
        result = _run_cli(
            ["--groups", "0", "--stage", "config"],
            env_extra={ENV_VAR: str(broken)},
        )
        report = json.loads(result.stdout)
        entry = _stage_entry(report, 0, "config")
        assert entry["status"] != "NOT_IMPLEMENTED", entry
        assert entry["status"] == "FAIL", entry
