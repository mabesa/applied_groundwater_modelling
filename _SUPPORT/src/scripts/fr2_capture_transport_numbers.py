#!/usr/bin/env python
"""
================================================================================
 FR.2 CANONICAL TRANSPORT-NUMBER CAPTURE  (run on the course JupyterHub / Linux)
================================================================================

PURPOSE
    FR.1 fixed a defect in ``generate_refined_grid``'s RIV transfer: the old
    centroid-in-polygon transfer dropped ~36% of calibrated river conductance
    outside the ~40 m-wide river corridor (see
    DESIGN_DOCS/student_casestudy_FR_steps.md and
    _SUPPORT/src/model_io_utils.py's RIV-transfer block). That changes the
    flow field feeding every transport demo, so every transport number pinned
    against the OLD (buggy) RIV transfer -- peaks, arrival days, exceedance
    windows, PRT capture fractions / travel times -- is now stale.

    This script builds all 5 ``transport_srcpulse_demo`` (ADE) physics variants
    plus the ``transport_prt_capture`` (PRT) demo FRESH, after the FR.1 fix,
    and prints an OLD -> NEW table so the test pins (_SUPPORT/tests/
    test_transport_srcpulse_demo.py) and the teaching narrative (04t/05t/08t)
    can be re-pinned against the CANONICAL post-fix numbers.

    Transport numbers are PLATFORM-DEPENDENT: the corridor-refined DISV mesh
    triangulation (via the ``triangle`` executable) is not bit-for-bit
    reproducible across platforms/toolchains, so the canonical numbers must be
    captured on the same Linux JupyterHub the course actually runs on -- not on
    a laptop. Do NOT run this on macOS: past transport work on macOS/arm64 hit
    SIGILL crashes in MF6's GWT solve (see jupyterhub_refine_reliability_check.py),
    and even where it doesn't crash, macOS-triangulated numbers are not the ones
    students will see.

    The OLD values hard-coded below are the pre-FR.1 pins being replaced (see
    _SUPPORT/tests/test_transport_srcpulse_demo.py and the
    transport_prt_capture module docstring). They are reference points for the
    diff, not assertions -- this script does not fail on a mismatch, it reports
    one.

HOW TO RUN (on the hub)
    uv run python fr2_capture_transport_numbers.py

    Expect ~5 real MF6 GWF/GWT solves for the ADE table (COLD, isolated tmp
    workspace -- no ambient cache) plus 2 more for the PRT section (default +
    wide-probe footprint), so this takes a few minutes, not seconds.

REQUIREMENTS
    - The course repo (so we can import transport_srcpulse_demo /
      transport_prt_capture from _SUPPORT/src).
    - mf6 (+ mf6 PRT support) and triangle executables resolvable by flopy.
================================================================================
"""
import math
import os
import sys
import tempfile

# Bootstrap: this script lives in _SUPPORT/src/scripts/, so "../" is
# _SUPPORT/src -- mirrors _SUPPORT/tests/test_transport_srcpulse_demo.py
# lines ~15-23, adjusted for the extra scripts/ nesting level.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

import transport_srcpulse_demo as tsd  # noqa: E402

# ---------------------------------------------------------------------------
# Locked demo parameters -- kept IN SYNC with
# _SUPPORT/tests/test_transport_srcpulse_demo.py. Do not drift these without
# also updating that test module: they define what "the 5 variants" means.
# ---------------------------------------------------------------------------
MASS_G = 3.0e5
PULSE_DAYS = 30.0
TOTAL_DAYS = 120.0
SOLUBILITY_MGL = 1000.0
REACTIVE_R = 2.0
REACTIVE_TOTAL_DAYS = 220.0
DISPERSIVITY_ALPHA_L = 20.0
DECAY_HALFLIFE_DAYS = 30.0
DECAY_LAM = math.log(2.0) / DECAY_HALFLIFE_DAYS

# Exercise compliance threshold used to compute the exceedance window
# (t where breakthrough concentration > THRESHOLD_MGL).
THRESHOLD_MGL = 1.0


def _exceedance_window(demo, threshold=THRESHOLD_MGL):
    """(t_min, t_max) over which breakthrough exceeds `threshold`, or None."""
    bt = np.asarray(demo.breakthrough)
    t = np.asarray(demo.times)
    exc = t[bt > threshold]
    if exc.size == 0:
        return None
    return (float(exc.min()), float(exc.max()))


def _fmt(v):
    if v is None:
        return "—"  # em dash: no value
    if isinstance(v, tuple):
        return f"({v[0]:.1f}, {v[1]:.1f})"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


# ---------------------------------------------------------------------------
# The 5 ADE physics variants, with their OLD (pre-FR.1) pins where known.
# variant name -> (build kwargs, OLD peak_mgL, OLD arrival_day, OLD window)
# ---------------------------------------------------------------------------
def _variant_specs(case_ws):
    return [
        (
            "conservative",
            dict(mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                 solubility_mgL=SOLUBILITY_MGL, case_ws=case_ws, force=True),
            dict(peak_mgL=4.95, arrival_day=41.0, window=(17.0, 79.0)),
        ),
        (
            "reactive_R2",
            dict(mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=REACTIVE_TOTAL_DAYS,
                 solubility_mgL=SOLUBILITY_MGL, R=REACTIVE_R, case_ws=case_ws, force=True),
            dict(peak_mgL=2.987, arrival_day=61.5, window=None),
        ),
        (
            "dispersivity_aL20",
            dict(mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                 solubility_mgL=SOLUBILITY_MGL, alpha_L=DISPERSIVITY_ALPHA_L,
                 case_ws=case_ws, force=True),
            dict(peak_mgL=4.21, arrival_day=38.8, window=None),
        ),
        (
            "decay_only",
            dict(mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=TOTAL_DAYS,
                 solubility_mgL=SOLUBILITY_MGL, lam=DECAY_LAM, case_ws=case_ws, force=True),
            dict(peak_mgL=2.80, arrival_day=40.0, window=None),
        ),
        (
            "reactive_decay",
            dict(mass_g=MASS_G, pulse_days=PULSE_DAYS, total_days=REACTIVE_TOTAL_DAYS,
                 solubility_mgL=SOLUBILITY_MGL, R=REACTIVE_R, lam=DECAY_LAM,
                 case_ws=case_ws, force=True),
            dict(peak_mgL=None, arrival_day=None, window=None),
        ),
    ]


def _print_table(rows):
    """rows: list of (variant, metric, old, new)."""
    w_var = max(len("variant"), max(len(r[0]) for r in rows))
    w_met = max(len("metric"), max(len(r[1]) for r in rows))
    w_old = max(len("OLD"), max(len(_fmt(r[2])) for r in rows))
    w_new = max(len("NEW"), max(len(_fmt(r[3])) for r in rows))
    header = (f"{'variant':<{w_var}}  {'metric':<{w_met}}  "
              f"{'OLD':>{w_old}}  {'NEW':>{w_new}}  delta")
    print(header)
    print("-" * len(header))
    for var, metric, old, new in rows:
        old_s, new_s = _fmt(old), _fmt(new)
        delta = "—"
        if isinstance(old, float) and isinstance(new, float):
            delta = f"{new - old:+.4g}"
        print(f"{var:<{w_var}}  {metric:<{w_met}}  {old_s:>{w_old}}  {new_s:>{w_new}}  {delta}")


def capture_ade_table(case_ws):
    """Build all 5 ADE physics variants FRESH and return (rows, n_censored).

    RIGHT-CENSORING GUARD (FR.2): FR.1 shifts every variant's timing, so a
    variant's peak can now land at the LAST output step (breakthrough still
    rising at total_days) or its exceedance window can still be OPEN
    (breakthrough still > threshold at total_days). Either makes the printed
    peak/arrival/window a LOWER BOUND, not a re-pinnable value. We detect this
    DIRECTLY from the curve (robust, no dependency on where the module stashes
    its own flag) and confirm against the module's own
    ``meta["peak_at_last_step"]``.
    """
    rows = []
    n_censored = 0
    for name, kwargs, old in _variant_specs(case_ws):
        print(f"\n[ADE] building variant '{name}' (force=True, cold ws) ...", flush=True)
        demo = tsd.build_srcpulse_demo(**kwargs)

        window = _exceedance_window(demo)
        pct_imbalance = demo.mass_balance.get("pct_imbalance", float("nan"))

        # --- right-censoring detection, computed DIRECTLY from the curve -----
        bt = np.asarray(demo.breakthrough, float)
        t = np.asarray(demo.times, float)
        peak_idx = int(np.argmax(bt))
        peak_censored = (peak_idx >= bt.size - 1)                      # peak IS last sample
        window_open_at_end = bool(bt.size and bt[-1] > THRESHOLD_MGL)  # still > thresh at end
        # module's own flag (confirmation only) -- lives in demo.meta.
        module_flag = getattr(demo, "meta", {}).get("peak_at_last_step")
        total_days = float(kwargs["total_days"])

        rows.append((name, "peak_mgL", old["peak_mgL"], float(demo.peak_mgL)))
        rows.append((name, "arrival_day", old["arrival_day"], float(demo.arrival_day)))
        rows.append((name, f"exceed_window(>{THRESHOLD_MGL:g}mg/L)", old["window"], window))
        rows.append((name, "pct_imbalance", None, float(pct_imbalance)))
        rows.append((name, "solubility_margin", None, float(demo.solubility_margin)))
        rows.append((name, "PeL_max", None, float(demo.PeL_max)))

        if peak_censored or window_open_at_end:
            n_censored += 1
            print(f"  >>> variant '{name}' RIGHT-CENSORED:")
            if peak_censored:
                print(f"  !! RIGHT-CENSORED: peak/arrival is the LAST output step "
                      f"(still rising at total_days={total_days:g} d) -- DO NOT re-pin; "
                      f"extend total_days and re-run. "
                      f"[module peak_at_last_step={module_flag!r}]")
            if window_open_at_end:
                print(f"  !! EXCEEDANCE WINDOW OPEN AT END: breakthrough still "
                      f"> {THRESHOLD_MGL:g} mg/L at total_days={total_days:g} d "
                      f"-- window END is a LOWER BOUND, not a re-pinnable value.")
        elif module_flag:
            # Direct check says fine but the module flagged it -- surface the
            # disagreement rather than silently trusting either.
            print(f"  ~ NOTE: module reports peak_at_last_step={module_flag!r} for "
                  f"'{name}' though the direct curve check found peak not censored; "
                  "inspect before re-pinning.")
    return rows, n_censored


# ---------------------------------------------------------------------------
# PRT capture (08t narrative) -- secondary; wrapped so a PRT failure does not
# abort the ADE table above.
# ---------------------------------------------------------------------------
def capture_prt_table(case_ws):
    import transport_prt_capture as tpc  # noqa: E402 (deferred: PRT is secondary)

    wide_radius = getattr(tpc, "WIDE_RELEASE_RADIUS_M", 120.0)

    print("\n[PRT] building DEFAULT-footprint capture demo (force=True, cold ws) ...",
          flush=True)
    cap_default = tpc.build_prt_capture(case_ws=case_ws, force=True)

    print(f"\n[PRT] building WIDE-probe capture demo (release_radius_m={wide_radius}, "
          "force=True, cold ws) ...", flush=True)
    cap_wide = tpc.build_prt_capture(release_radius_m=wide_radius, case_ws=case_ws, force=True)

    # OLD reference values, taken from the transport_prt_capture module
    # docstring / 08t narrative (pre-FR.1 flow field). Not all fields have a
    # documented OLD pin.
    old = {
        "default.capture_fraction": 1.0,
        "default.tt_median_d": 25.8,
        "default.halfwidth_at_spill_m": 78.9,
        "default.asymptotic_halfwidth_m": 108.0,
        "wide.capture_fraction": 143.0 / 199.0,  # 0.7186; docstring's r=120 m example
        "wide.tt_median_d": None,
        "wide.halfwidth_at_spill_m": 78.9,
        "wide.asymptotic_halfwidth_m": 108.0,
    }

    rows = []
    for label, cap in (("default", cap_default), ("wide", cap_wide)):
        for field in ("capture_fraction", "tt_median_d", "halfwidth_at_spill_m",
                      "asymptotic_halfwidth_m"):
            rows.append((f"prt_{label}", field, old[f"{label}.{field}"],
                         float(getattr(cap, field))))
    return rows


def main():
    case_ws = tempfile.mkdtemp(prefix="fr2_capture_")
    print(f"COLD isolated workspace: {case_ws}")
    print("=" * 78)
    print("ADE (transport_srcpulse_demo) -- 5 physics variants, force=True")
    print("=" * 78)

    ade_rows, n_censored = capture_ade_table(case_ws)
    print()
    _print_table(ade_rows)
    if n_censored:
        print()
        print(f"NOTE: {n_censored} variant(s) right-censored -- extend total_days "
              "for those before using these numbers to re-pin.")

    print()
    print("=" * 78)
    print("PRT (transport_prt_capture) -- default + wide-probe footprint")
    print("=" * 78)
    try:
        prt_rows = capture_prt_table(case_ws)
        print()
        _print_table(prt_rows)
    except Exception as e:  # noqa: BLE001 -- PRT is secondary; never abort the ADE table
        print(f"\n[PRT] SKIPPED -- capture failed: {e!r}")
        print("[PRT] The ADE table above is unaffected; re-run PRT capture separately.")


if __name__ == "__main__":
    main()
