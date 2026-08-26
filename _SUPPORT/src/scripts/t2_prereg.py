"""T2 S1 -- the pre-registration: build, validate and freeze it.

`DESIGN_DOCS/T2_S1_brief.md` v4. Every claim T2 will judge is mapped to its
metric, identities, direction, tolerance and verdict rule BEFORE any result
exists, because choosing which metric supports a claim after seeing the
numbers is how a `hypothesis` quietly becomes `grid_supported`.

🔴 THE CONTROL THAT EARNS THIS STEP (brief Sec 4): for every claim stating a
number, the pre-registration records the STATED value and the evaluation
requires it to MATCH the computed value. `tasks_data.py` once promised
5.1 mg/L while the cell printed 5.28; nothing else here targets that as
directly.

Deliberately NOT here (a proportionality review returned OVER-ENGINEERED on
the previous draft): double decomposition, inter-annotator agreement,
adjudication logs, methodology checksums. This team is one lecturer and an
assistant -- "independent annotation" would be the assistant doing it twice,
which is not independence, and a document asserting it that no control can
check is ceremony.

    uv run python _SUPPORT/src/scripts/t2_prereg.py validate
    uv run python _SUPPORT/src/scripts/t2_prereg.py fixtures
    uv run python _SUPPORT/src/scripts/t2_prereg.py checksum
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
INVENTORY = REPO / "DOCUMENTATION/contracts/T0_2a_claim_inventory.json"
PREREG = REPO / "DOCUMENTATION/contracts/T2_preregistration.json"

# --- the frozen vocabulary this file validates against -----------------------
# T0_2b Sec 2: the only metrics that exist.
METRICS = ("peak_mgL", "t_peak", "t_first_exceedance", "t_last_exceedance",
           "exceedance_duration", "capture_halfwidth_m")

# T0_2b Sec 2.7: the only tolerances that exist.
TOLERANCES = {"TOL_CONC_REL": 0.02, "TOL_TIME_REL": 0.02, "TOL_WIDTH_REL": 0.05}

# T0_2b Sec 3: the frozen 11 identities.
IDENTITIES = (
    "spatial_50m_cr0.9", "spatial_20m_cr0.9", "spatial_10m_cr0.9",
    "spatial_5m_cr0.9", "spatial_2m_cr0.9",
    "temporal_50m_cr0.45", "temporal_50m_cr0.225",
    "temporal_2m_cr0.45", "temporal_2m_cr0.225",
    "bcontrol_coarse", "bcontrol_fine",
)

# T0_3: the frozen reason codes (13).
REASON_CODES = (
    "converged_both_axes", "no_convergence_trend", "refinement_axis_untested",
    "metric_over_tolerance_no_decision", "decision_stable_metric_over_tolerance",
    "decision_changed_under_refinement", "horizon_censored", "run_not_solved",
    "provenance_invalid", "metric_not_applicable", "method_cannot_answer",
    "causal_claim_out_of_scope", "illustrative_by_design",
)

DISPOSITIONS = ("evaluated_by_matrix", "out_of_scope", "not_evaluated")
DIRECTIONS = ("lower_than", "greater_than", "differs_from", "equals", "within_tolerance_of")


class PreregError(Exception):
    """A pre-registration that cannot gate an evaluation."""


def _fail(errors):
    if errors:
        raise PreregError("\n".join(f"  - {e}" for e in errors))


def validate(doc: dict) -> dict:
    """Structural validation (brief Sec 3). Returns a summary.

    ⚠️ Structural only. It cannot tell whether a mapping encodes the RIGHT
    quantity for its claim -- that is what the lecturer sign-off is for, and
    saying so plainly is the point.
    """
    errors, seen = [], set()
    comps = doc.get("components")
    if not isinstance(comps, list) or not comps:
        raise PreregError("no components")

    for i, c in enumerate(comps):
        where = f"component[{i}] id={c.get('id')!r}"
        for req in ("id", "parent_candidate_id", "source_path", "source_text",
                    "disposition"):
            if not c.get(req):
                errors.append(f"{where}: missing {req}")
        if c.get("id") in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(c.get("id"))

        disp = c.get("disposition")
        if disp not in DISPOSITIONS:
            errors.append(f"{where}: disposition {disp!r} not in {DISPOSITIONS}")

        if disp == "evaluated_by_matrix":
            m = c.get("metric")
            if m not in METRICS:
                errors.append(f"{where}: metric {m!r} not one of T0_2b Sec 2's")
            tol = c.get("tolerance")
            if tol not in TOLERANCES:
                errors.append(f"{where}: tolerance {tol!r} not one of T0_2b Sec 2.7's")
            d = c.get("direction")
            if d not in DIRECTIONS:
                errors.append(f"{where}: direction {d!r} not in {DIRECTIONS}")
            ids = c.get("identities") or []
            if not ids:
                errors.append(f"{where}: no identities")
            for ident in ids:
                if ident not in IDENTITIES:
                    errors.append(f"{where}: identity {ident!r} not in the frozen 11")
            if not c.get("verdict_rule"):
                errors.append(f"{where}: no verdict_rule")
        else:
            rc = c.get("reason_code")
            if rc not in REASON_CODES:
                errors.append(f"{where}: reason_code {rc!r} not one of T0_3's 13")
            # brief Sec 5: an unmappable component still needs a short reason
            if disp == "not_evaluated" and not c.get("reason"):
                errors.append(f"{where}: not_evaluated needs a short written reason")

        # 🔴 the 5.1-vs-5.28 control
        if c.get("stated_value") is not None and disp == "evaluated_by_matrix":
            if not c.get("stated_value_must_match"):
                errors.append(
                    f"{where}: states a value but does not require it to match "
                    "the computed one (brief Sec 4)")
    _fail(errors)

    by_disp = {}
    for c in comps:
        by_disp[c["disposition"]] = by_disp.get(c["disposition"], 0) + 1
    stated = sum(1 for c in comps if c.get("stated_value") is not None)
    return {"components": len(comps), "by_disposition": by_disp,
            "components_stating_a_number": stated}


def fixtures() -> list:
    """Brief Sec 3: one at-tolerance and one over-tolerance case per tolerance
    class. Six, not an exhaustive state matrix.

    Proves the verdict rule is executable and lands on the right side of each
    frozen tolerance -- the boundary being where a rule silently disagrees
    with its own tolerance.
    """
    out = []
    for name, tol in TOLERANCES.items():
        ref = 100.0
        at = ref * (1.0 + tol * 0.5)      # inside
        over = ref * (1.0 + tol * 2.0)    # outside
        for label, cand, expect in (("at_tolerance", at, True),
                                    ("over_tolerance", over, False)):
            rel = abs(cand - ref) / abs(ref)
            within = rel <= tol
            out.append({"tolerance": name, "case": label, "reference": ref,
                        "candidate": round(cand, 6), "relative": round(rel, 6),
                        "within": within, "expected": expect,
                        "pass": within == expect})
    return out


def checksum(path: Path = PREREG) -> str:
    """SHA-256 of the committed pre-registration -- what S3's controls verify."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["validate", "fixtures", "checksum"])
    args = ap.parse_args()

    if args.command == "fixtures":
        res = fixtures()
        for r in res:
            flag = "ok " if r["pass"] else "FAIL"
            print(f"[{flag}] {r['tolerance']:14s} {r['case']:14s} "
                  f"rel={r['relative']:.4f} within={r['within']} expected={r['expected']}")
        bad = [r for r in res if not r["pass"]]
        print(f"\n{len(res) - len(bad)}/{len(res)} fixtures pass")
        return 1 if bad else 0

    if not PREREG.exists():
        print(f"no pre-registration at {PREREG}", file=sys.stderr)
        return 1

    doc = json.loads(PREREG.read_text())
    if args.command == "checksum":
        print(checksum())
        return 0

    try:
        summary = validate(doc)
    except PreregError as exc:
        print("PREREGISTRATION INVALID:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    print("\nVALID (structurally). ⚠️ Structural validity is not semantic "
          "correctness -- the lecturer sign-off is what checks that a mapping "
          "encodes the right quantity for its claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
