#!/usr/bin/env python3
"""Check a submission ZIP before you hand it in.

Run it on the ZIP itself, from anywhere::

    python3 check_submission_zip.py group_05.zip

Why this exists
---------------
A group once submitted a complete, internally consistent, fully rerunnable ZIP
**for the wrong group**: the folder was ``group_05/`` but ``case_config.yaml``
still said ``group.number: 0``, so every notebook ran the demo scenario — a
different concession, contaminant and threshold — and every other check passed.
It has happened twice, once to a student and once during a course preflight.

The scratch notebook already refuses to open a bundle whose group disagrees with
its folder, but that costs a kernel restart and a full re-run, so it gets
skipped. This is the five-second version of the same question.

Design notes, so the next person does not undo them
---------------------------------------------------
* **Standard library only.** It must run in a bare terminal on the Hub where
  ``python`` is not the notebook kernel. Importing the students' ``scratch_io``
  would drag in geopandas to read a JSON file, and would bind this check to
  whatever copy the group made months ago.
* **It lives outside ``template/``** on purpose, so it is never copied into a
  group folder or into the ZIP. A checker inside the submission is a checker
  frozen at copy time.
* **It reads the ZIP, not an extraction** — the ZIP is what is submitted.
* **Three sources, not two.** Folder name, ``exports/run_info.json`` and
  ``case_config.yaml`` must all agree. Comparing only the folder name to the
  bundle misses a group that renamed the folder to silence a warning; comparing
  only the config to the bundle misses a bundle exported before the config was
  fixed.
* **It never says OK about something it did not check.** Where it cannot verify,
  it says NOT CHECKED and explains what to do.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
import zlib
from typing import Optional

#: Every file the exported bundle must carry. None is optional: the scenario
#: state feeds Card C, transport is required course-wide, and PRT feeds Card B.
REQUIRED_EXPORTS = (
    "run_info.json",
    "flow_heads_sub_base.gpkg",
    "flow_heads_sub_wells.gpkg",
    "flow_heads_sub_scenario.gpkg",
    "flow_budget_summary.csv",
    "transport_breakthrough.csv",
    "transport_meta.json",
    "pathlines_summary.csv",
)

#: Everything PROJECT/workspace/README.md and SUBMISSION_README_TEMPLATE.md mark as
#: required in the group folder root. The notebooks are provenance records; the
#: configs say which scenario was run.
REQUIRED_ROOT_FILES = (
    "report.pdf",
    "presentation.pdf",
    "SUBMISSION_README.md",
    "case_config.yaml",
    "case_config_transport.yaml",
    "case_study_flow_group_0.ipynb",
    "case_study_transport_group_0.ipynb",
    "steward_export_lightweight.ipynb",
)

#: Directories that must exist and contain something.
REQUIRED_DIRS = ("figures", "tables")


class Result:
    """Collects problems and notes so every check runs before anything is said."""

    def __init__(self) -> None:
        self.problems: list[str] = []
        self.unchecked: list[str] = []
        self.notes: list[str] = []

    def fail(self, msg: str) -> None:
        self.problems.append(msg)

    def skip(self, msg: str) -> None:
        self.unchecked.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    @property
    def ok(self) -> bool:
        return not self.problems


def _group_from_config(text: str) -> Optional[int]:
    """``group.number`` out of case_config.yaml without a YAML parser.

    Only the ``number:`` inside the top-level ``group:`` block counts -- the file
    holds other ``number``-ish keys further down.
    """
    in_group = False
    for line in text.splitlines():
        if re.match(r"^group:\s*$", line):
            in_group = True
            continue
        if in_group:
            if re.match(r"^\S", line):        # dedented to a new top-level key
                break
            m = re.match(r"^\s+number:\s*(\d+)", line)
            if m:
                return int(m.group(1))
    return None


def check_zip(zip_path: str) -> Result:
    r = Result()
    try:
        zf = zipfile.ZipFile(zip_path)
    except FileNotFoundError:
        r.fail(f"no such file: {zip_path}")
        return r
    except IsADirectoryError:
        r.fail(
            f"{zip_path} is a folder, not the zip. Build the zip first (step 4), "
            f"then run this on {zip_path}.zip"
        )
        return r
    except zipfile.BadZipFile:
        r.fail(f"{zip_path} is not a zip archive")
        return r
    except OSError as exc:
        r.fail(f"could not open {zip_path}: {exc}")
        return r

    with zf:
        names = [n for n in zf.namelist() if n.strip("/")]
        tops = sorted({n.split("/")[0] for n in names})

        junk = {t_ for t_ in tops if t_ in ("__MACOSX",) or t_.startswith(".")}
        real = [t_ for t_ in tops if t_ not in junk]
        # Only call the junk harmless once we know there IS a real folder beside it.
        if junk and real:
            r.note(
                f"ignoring archiver junk at the top level: {sorted(junk)} "
                f"(harmless; add -x '*/__MACOSX/*' to the zip command to avoid it)"
            )
        if not real and junk:
            r.fail(
                f"the archive has no usable group folder -- its only top-level entries "
                f"are {sorted(junk)}, which are hidden or archiver-generated. Rebuild "
                f"the zip from PROJECT/workspace/ as step 4 shows."
            )
            return r
        if len(real) != 1:
            r.fail(
                f"the archive has {len(real)} top-level entries {real[:4]}, not one group "
                f"folder. Most often this means you zipped from INSIDE the group folder; "
                f"rebuild from PROJECT/workspace/ as step 4 shows."
            )
            return r
        top = real[0]

        # --- source 1: the folder name -------------------------------------
        m = re.fullmatch(r"group_(\d+)", top)
        folder_group = int(m.group(1)) if m else None
        if folder_group is None:
            r.skip(
                f"the top-level folder is {top!r}, not group_<N>, so its name cannot "
                f"be compared with the bundle. Rename it to e.g. group_03 and rebuild."
            )

        # --- source 2: the exported bundle ----------------------------------
        bundle_group = None
        try:
            run_info = json.loads(zf.read(f"{top}/exports/run_info.json"))
            bundle_group = run_info.get("group_number")
            missing_required = run_info.get("missing_required")
            if missing_required:
                r.fail(
                    f"the bundle records missing required exports: {missing_required}. "
                    f"Fix the run that should have produced them and re-export."
                )
            if run_info.get("schema_version") is None:
                r.fail("exports/run_info.json has no schema_version")
        except KeyError:
            r.fail(
                f"{top}/exports/run_info.json is not in the archive -- the steward "
                f"export was never run, or did not finish."
            )
        except json.JSONDecodeError:
            r.fail(f"{top}/exports/run_info.json is not valid JSON")
        except (UnicodeDecodeError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
            r.fail(
                f"could not read {top}/exports/run_info.json ({type(exc).__name__}). "
                f"The zip may be corrupt or encrypted -- rebuild it."
            )

        # --- source 3: the configuration the notebooks actually read ---------
        config_group = None
        try:
            config_group = _group_from_config(
                zf.read(f"{top}/case_config.yaml").decode("utf-8")
            )
            if config_group is None:
                r.skip("could not find group.number in case_config.yaml")
        except KeyError:
            r.fail(f"{top}/case_config.yaml is not in the archive")
        except (UnicodeDecodeError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
            r.fail(
                f"could not read {top}/case_config.yaml ({type(exc).__name__}). "
                f"Save it as UTF-8, or rebuild the zip if it is corrupt."
            )

        # --- the three must agree -------------------------------------------
        # A hand-edited run_info.json can carry "5" rather than 5. Normalise before
        # comparing, or an int-vs-str compare crashes -- and hand-editing is exactly
        # the wrong fix this checker exists to deter, so that path must stay clean.
        def _as_int(v):
            try:
                return int(str(v).strip())
            except (TypeError, ValueError):
                return None

        seen = {k: _as_int(v) for k, v in (
            ("folder name", folder_group),
            ("exports/run_info.json", bundle_group),
            ("case_config.yaml", config_group),
        ) if _as_int(v) is not None}
        if len(set(seen.values())) > 1:
            detail = ", ".join(f"{k} says {v}" for k, v in seen.items())
            r.fail(
                f"THIS IS NOT ONE GROUP'S WORK: {detail}.\n"
                f"      A bundle belongs to the group it was exported for. Renaming the\n"
                f"      folder does NOT fix this and would submit the wrong group's\n"
                f"      scenario -- a different concession, contaminant and threshold.\n"
                f"      Set group.number in case_config.yaml to your real group, re-run\n"
                f"      both master notebooks and the steward export, have every member\n"
                f"      re-run their scratch notebook against the new bundle, then rebuild\n"
                f"      the zip."
            )
        elif len(seen) < 3:
            unread = [k for k in ("folder name", "exports/run_info.json",
                                  "case_config.yaml") if k not in seen]
            r.skip(f"could not read a group number from: {', '.join(unread)}")

        # --- contents --------------------------------------------------------
        present = set(names)
        sizes = {i.filename: i.file_size for i in zf.infolist()}
        for fname in REQUIRED_EXPORTS:
            key = f"{top}/exports/{fname}"
            if key not in present:
                r.fail(f"missing required export: exports/{fname}")
            elif sizes.get(key, 0) == 0:
                r.fail(f"exports/{fname} is empty (0 bytes) -- re-export the bundle")
        for fname in REQUIRED_ROOT_FILES:
            key = f"{top}/{fname}"
            if key not in present:
                r.fail(f"missing from the group folder root: {fname}")
            elif sizes.get(key, 0) == 0:
                hint = ("a failed print-to-PDF looks exactly like this"
                        if fname.endswith(".pdf") else "nothing was written to it")
                r.fail(f"{fname} is empty (0 bytes) -- {hint}. Open it before you submit.")
        if not [n for n in names if re.search(r"/scratch_[^/]+\.ipynb$", n)]:
            r.fail("no scratch_<name>.ipynb -- every member submits one")
        for dname in REQUIRED_DIRS:
            prefix = f"{top}/{dname}/"
            if not any(n.startswith(prefix) and not n.endswith("/") for n in names):
                r.fail(
                    f"{dname}/ is missing or empty -- it holds the figures and tables "
                    f"your cards produced, which the report cites."
                )
        if f"{top}/scratch_io.py" not in present:
            r.fail("scratch_io.py is missing, so the scratch notebooks cannot rerun")
        elif sizes.get(f"{top}/scratch_io.py", 0) == 0:
            r.fail("scratch_io.py is empty (0 bytes), so the scratch notebooks cannot rerun")

        if len(set(seen.values())) == 1:
            n_files = sum(1 for n in names if not n.endswith("/"))
            r.note(f"group {next(iter(set(seen.values())))}  |  {n_files} files")
    return r


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("zip_path", help="the submission ZIP, e.g. group_05.zip")
    args = ap.parse_args(argv)

    r = check_zip(args.zip_path)
    for n in r.notes:
        print(f"      {n}")
    for u in r.unchecked:
        print(f"NOT CHECKED: {u}")
    for p in r.problems:
        print(f"PROBLEM: {p}")

    if r.problems:
        print("\nNOT READY TO SUBMIT -- fix the problems above and rebuild the zip.")
        return 1
    if r.unchecked:
        print("\nNo problems found, but NOT everything could be checked (see above).")
        return 2
    print("\nOK -- folder, bundle and config agree, and every required file is present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
