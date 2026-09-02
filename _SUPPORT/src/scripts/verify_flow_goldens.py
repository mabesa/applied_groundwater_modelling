#!/usr/bin/env python
"""Mechanically verify the regenerated flow goldens before they are committed.

Read-only. Run this after regenerating goldens on the Hub; it checks every property
that has to hold, so nobody has to eyeball 13 manifests:

  * every group has a golden XOR a deferral (``assert_all_groups_anchored`` FAILS on
    both-or-neither, so a leftover deferral for a now-frozen group breaks the build)
  * ``group`` field matches the filename
  * ``radius_used`` equals the group's PINNED ``geometry.refine_radius_m`` -- the check
    that catches the failure mode this whole exercise was about: a golden built at a
    ladder radius while the freeze used the pin
  * ``provisional`` is false and the provenance is Linux (a macOS golden is provisional
    and still needs a Linux re-verify)

Exit 0 if everything holds, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
for p in (str(SRC), str(SRC / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import casestudy_flow_common as cfc  # noqa: E402

GOLDEN_DIR = SRC / "golden"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden-dir", default=str(GOLDEN_DIR))
    ap.add_argument("--groups", default="0-12")
    ap.add_argument("--allow-provisional", action="store_true",
                    help="accept macOS-generated goldens (for a local dry run only)")
    args = ap.parse_args(argv)

    lo, _, hi = args.groups.partition("-")
    groups = range(int(lo), int(hi) + 1) if hi else [int(lo)]
    gdir = Path(args.golden_dir)

    problems: list[str] = []
    rows: list[str] = []
    for g in groups:
        man_p = gdir / f"group{g}_flow.manifest.json"
        def_p = gdir / f"group{g}_flow.deferral.json"
        has_man, has_def = man_p.is_file(), def_p.is_file()

        if has_man == has_def:
            problems.append(
                f"group {g}: has {'BOTH a golden AND a deferral' if has_man else 'NEITHER'}"
                f" -- exactly one is required (delete the deferral once the golden exists)")
            rows.append(f"  g{g:>2}  {'BOTH' if has_man else 'NEITHER':<10}")
            continue
        if not has_man:
            problems.append(f"group {g}: still deferred -- no golden was generated")
            rows.append(f"  g{g:>2}  deferral only")
            continue

        man = json.loads(man_p.read_text())
        pin = cfc.group_refine_radius(g)
        radius = man.get("radius_used")
        prov = bool(man.get("provisional"))
        os_name = man.get("generation_os")

        if int(man.get("group", -1)) != g:
            problems.append(f"group {g}: manifest 'group' is {man.get('group')!r}")
        if pin is None:
            problems.append(f"group {g}: no pinned radius in config")
        elif radius is None or abs(float(radius) - pin) > 1e-9:
            problems.append(
                f"group {g}: golden built at radius {radius!r} but the config pin is "
                f"{pin!r} -- it will NOT match the mesh freeze or the student build")
        if prov and not args.allow_provisional:
            problems.append(f"group {g}: provisional=true (generated off-Linux, os={os_name!r})")
        if os_name != "Linux" and not args.allow_provisional:
            problems.append(f"group {g}: generation_os={os_name!r}, expected 'Linux'")

        rows.append(f"  g{g:>2}  r={radius!s:<6} pin={pin!s:<6} provisional={str(prov):<5} os={os_name}")

    print("\n".join(rows))
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"\nOK: {len(list(groups))} groups, each with a golden at its pinned radius.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
