"""T2 S3 -- the controls that make S1 and S2 executable.

`T2_steps.md` v4 Sec 5: S1's pre-registration and S2's guards cost nothing,
which is exactly why they get skipped under pressure. Documents are not
controls. This module is what turns them into refusals, and every refusal
here has a test that fires it.

Five controls, deliberately small -- a proportionality review already
returned OVER-ENGINEERED once on this milestone:

  1. verify_prereg      -- the pre-registration matches its recorded checksum
  2. require_registered -- an unregistered identity cannot be run
  3. guard_for          -- the runner takes its nstp_cap from S2, not from a caller
  4. accept_run         -- a run is not evidence until it PASSES, and the
                           verdict is written beside the artifact
  5. RerunLedger        -- one automatic repeat, then stop and escalate

    uv run python _SUPPORT/src/scripts/t2_controls.py selftest
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "_SUPPORT/src"))

PREREG = REPO / "DOCUMENTATION/contracts/T2_preregistration.json"
GUARDS = REPO / "DOCUMENTATION/contracts/T2_run_guards.json"

# The checksum S1 committed. A mismatch means the mapping moved after the
# evaluation was designed against it -- which is the whole thing S1 exists to
# prevent, so it is a refusal rather than a warning.
PREREG_SHA256 = "e88c2ccf0418996ce9caf15b0a85f0a437be98339cc0cef57ce04e5a35f0d762"


class ControlRefusal(Exception):
    """A control refused. Never caught-and-continued inside T2."""


# --- 1. the pre-registration is the artifact the evaluation was designed on --
def verify_prereg(path: Path = PREREG, expected: str = PREREG_SHA256) -> str:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ControlRefusal(
            f"pre-registration checksum mismatch\n  expected {expected}\n  actual   {actual}\n"
            "The mapping moved after the evaluation was designed against it. Re-run S1's "
            "validation, update the recorded checksum deliberately, and say why -- do not "
            "proceed on the new file silently.")
    return actual


def registered_identities(path: Path = PREREG) -> set:
    """Identities the pre-registration actually references.

    ⚠️ NOT the frozen set. An identity can be frozen and still be referenced by
    no component -- running it would produce evidence no claim consumes.
    """
    doc = json.loads(path.read_text())
    return {i for c in doc["components"] for i in (c.get("identities") or [])}


# --- 2. an unregistered identity cannot be run ------------------------------
def require_registered(identity: str, path: Path = PREREG) -> str:
    known = registered_identities(path)
    if identity not in known:
        raise ControlRefusal(
            f"identity {identity!r} is not referenced by the pre-registration.\n"
            f"  registered: {sorted(known)}\n"
            "Running it would produce evidence no claim consumes -- and adding a point to "
            "the frozen series is a failure edge to T0 (T0_2b Sec 3 rule 4), not a "
            "scheduling choice.")
    return identity


# --- 3. the guard comes from S2, not from the caller ------------------------
def guard_for(identity: str, measured_cr09_demand: Optional[int] = None,
              path: Path = GUARDS) -> int:
    """S2's guard. `measured_cr09_demand` switches from the discovery guard to
    the derived one -- 2x a MEASURED demand -- once that measurement exists."""
    g = json.loads(path.read_text())["guards"]
    if measured_cr09_demand is None:
        return int(g["discovery_guard"]["value"])
    if measured_cr09_demand <= 0:
        raise ControlRefusal(
            f"measured demand for {identity!r} must be positive, got "
            f"{measured_cr09_demand!r} -- a non-positive demand is not a measurement")
    return 2 * int(measured_cr09_demand)


# --- 4. a run is not evidence until it passes acceptance --------------------
@dataclass
class Acceptance:
    identity: str
    passed: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"identity": self.identity, "passed": self.passed,
                "checks": self.checks, "failures": self.failures}


#: How far above its target an identity's achieved Courant may sit and still
#: pass. 5% absorbs the discretisation of `nstp` to a whole number; it does
#: not absorb a sizing error (the observed failures were 45%-242% over).
CR_TOL_REL = 0.05


def accept_run(artifact_path: Path, *, identity: str,
               requested_guard: int) -> Acceptance:
    """T2_steps Sec 4. Returns PASS/FAIL and writes the verdict beside the
    artifact, so 'was this run accepted' is a file rather than a memory.

    🔴 The next expensive identity does not launch until the previous one has
    passed. A run whose artifact does not load is a run to repeat -- better
    learned at 35 s than at ~49 min.
    """
    import t1_evidence_artifact as tea
    import t1_artifact_producer as prod

    checks: Dict[str, bool] = {}
    failures: List[str] = []

    def _check(name: str, ok: bool, detail: str = "") -> None:
        checks[name] = bool(ok)
        if not ok:
            failures.append(f"{name}: {detail}" if detail else name)

    record = None
    try:
        record = tea.load_record(artifact_path)
        _check("artifact_loads", True)
    except Exception as exc:                       # noqa: BLE001 -- any failure is a failure
        _check("artifact_loads", False, f"{type(exc).__name__}: {exc}")

    if record is not None:
        _check("provenance_valid", bool(record.provenance_valid),
               "the record is incomplete against REQUIRED_FIELD_PATHS")
        try:
            prod.check_cross_field_invariants(record)
            _check("cross_field_invariants", True)
        except Exception as exc:                   # noqa: BLE001
            _check("cross_field_invariants", False, str(exc))

        cap = record.nstp_cap
        _check("nstp_cap_recorded", cap is not None, "no nstp_cap in the record")
        _check("nstp_cap_matches_guard", cap == requested_guard,
               f"ran under {cap!r}, S2's guard was {requested_guard!r}")
        nstp = record.nstp
        _check("guard_not_reached", nstp is not None and cap is not None and nstp < cap,
               f"nstp={nstp!r} reached the guard {cap!r} -- a capped run is not a feasible run")
        # 🔴 The achieved Courant number against the target this identity is
        # NAMED for. Added 2026-09-01 after four coarse identities were stamped
        # `passed` while running at Cr up to 3.076 against a 0.9 target -- the
        # gate checked seven things and not one of them looked at the quantity
        # the identity is defined by. A run whose time-stepping missed its own
        # target is not an acceptable run, whatever else is well-formed.
        raw = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        cr_ach = (raw.get("run_health") or {}).get("cr_achieved")
        cr_target = (raw.get("run_identity") or {}).get("cr_target")
        _check("cr_meets_target",
               cr_ach is not None and cr_target is not None
               and float(cr_ach) <= float(cr_target) * (1.0 + CR_TOL_REL),
               f"achieved Cr {cr_ach} vs target {cr_target} "
               f"(+{CR_TOL_REL:.0%} tolerance)")

        _check("versions_captured",
               all(getattr(record, f) for f in
                   ("flopy_version", "numpy_version", "python_version", "mf6_sha256")),
               "solver/library provenance incomplete")

    return Acceptance(identity=identity, passed=not failures,
                      checks=checks, failures=failures)


def write_acceptance(acc: Acceptance, artifact_path: Path) -> Path:
    out = Path(artifact_path).with_suffix(".acceptance.json")
    out.write_text(json.dumps(acc.to_json(), indent=2) + "\n")
    return out


# --- 5. reruns are bounded and declared -------------------------------------
class RerunLedger:
    """T2_steps Sec 4.1: at most ONE automatic repeat per identity. A second
    failure stops T2 and is escalated, never quietly retried -- and every
    rerun records its reason BEFORE it runs."""

    MAX_AUTOMATIC_REPEATS = 1

    def __init__(self) -> None:
        self._attempts: Dict[str, int] = {}
        self._reasons: Dict[str, List[str]] = {}

    def record_attempt(self, identity: str) -> int:
        self._attempts[identity] = self._attempts.get(identity, 0) + 1
        return self._attempts[identity]

    def may_rerun(self, identity: str, reason: str) -> bool:
        if not reason or not reason.strip():
            raise ControlRefusal(
                f"a rerun of {identity!r} must record its reason BEFORE it runs -- "
                "a rerun may replace a result only for a declared reason, never because "
                "the first answer was inconvenient")
        used = self._attempts.get(identity, 1) - 1
        if used >= self.MAX_AUTOMATIC_REPEATS:
            raise ControlRefusal(
                f"{identity!r} has already used its one automatic repeat. STOP and "
                "escalate -- uncontrolled reruns are how an inconvenient result gets "
                "replaced by a convenient one.")
        self._reasons.setdefault(identity, []).append(reason.strip())
        return True

    def reasons(self, identity: str) -> List[str]:
        return list(self._reasons.get(identity, []))


# --- smoke check -------------------------------------------------------------
# The REAL tests are `_SUPPORT/tests/test_t2_controls.py`, where every refusal
# has a test that fires it. This is a two-line smoke check for use at a
# terminal, deliberately NOT a second copy of the test suite.
def selftest() -> int:
    try:
        verify_prereg()
        print("[ok  ] pre-registration matches its recorded checksum")
    except ControlRefusal as exc:
        print(f"[FAIL] {exc}")
        return 1
    print(f"[ok  ] {len(registered_identities())} identities registered; "
          f"discovery guard {guard_for('smoke')}")
    print("\nfull control tests: uv run pytest _SUPPORT/tests/test_t2_controls.py")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        raise SystemExit(selftest())
    print(__doc__)
