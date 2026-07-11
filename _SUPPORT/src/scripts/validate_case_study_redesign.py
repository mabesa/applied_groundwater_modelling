#!/usr/bin/env python
"""
validate_case_study_redesign — CLI driver for the case-study redesign
validation harness (library: ``_SUPPORT/src/case_validation.py``).

This is a SKELETON milestone: no stage bodies are registered yet, so every
canonical stage (config, mother_model_load, flow_refinement, base_wells,
scenario, prt, transport_handoff, export_v2, scratch_zip_rerun, cards)
reports ``NOT_IMPLEMENTED``. Later milestones import real stage modules that
call ``case_validation.register_stage(...)`` before this CLI (or its
programmatic entry point) runs.

Usage
-----
    uv run python _SUPPORT/src/scripts/validate_case_study_redesign.py --groups 0-8 --plan-only
    uv run python _SUPPORT/src/scripts/validate_case_study_redesign.py --groups 0,3 --require-green
    uv run python _SUPPORT/src/scripts/validate_case_study_redesign.py --groups 0-8 --stage config --out report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make case_validation importable regardless of the current working
# directory (mirrors the sys.path shim used by other _SUPPORT/src/scripts).
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_SUPPORT_SRC = _SCRIPT_DIR.parent  # _SUPPORT/src/scripts -> _SUPPORT/src
if str(_SUPPORT_SRC) not in sys.path:
    sys.path.insert(0, str(_SUPPORT_SRC))

import case_validation as cv  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the case-study redesign build pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--groups",
        default="0",
        help="Group ids to validate, e.g. '0-8' or '0,3,5' (default: 0).",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        default=False,
        help="Enumerate the canonical stage plan without executing any stage body.",
    )
    parser.add_argument(
        "--require-green",
        action="store_true",
        default=False,
        help="Exit non-zero if any required stage is not PASS for any selected group.",
    )
    parser.add_argument(
        "--stage",
        default=None,
        help="Restrict execution to a single canonical stage id.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write the JSON report to this path instead of stdout.",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        groups = cv.parse_groups_spec(args.groups)
    except ValueError as exc:
        print(f"ERROR: invalid --groups value {args.groups!r}: {exc}", file=sys.stderr)
        return 2

    if not groups:
        print(f"ERROR: --groups {args.groups!r} selected no group ids", file=sys.stderr)
        return 2

    if args.stage is not None and args.stage not in cv.REQUIRED_STAGES:
        print(
            f"ERROR: unknown --stage {args.stage!r}; must be one of {cv.REQUIRED_STAGES}",
            file=sys.stderr,
        )
        return 2

    report = cv.run_validation(groups, stage=args.stage, plan_only=args.plan_only)
    report_json = json.dumps(report, indent=2)

    if args.out:
        Path(args.out).write_text(report_json + "\n", encoding="utf-8")
    else:
        print(report_json)

    # --plan-only never executes a stage body, so it always succeeds.
    if args.plan_only:
        return 0

    if args.require_green and not cv.is_green(report):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
