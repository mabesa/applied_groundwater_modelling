"""T0.2a claim inventory: enumerator + coverage gate for the transport track.

Relationship to ``_SUPPORT/src/scripts/transport_stale_number_audit.sh``:
    That script and this one do a **different job** but share **the same net**.
    The audit script is a one-shot, human-run `grep` sweep for a fixed list of
    superseded numeric values (Tier 1) plus an independent context sweep of
    "result word + number" lines (Tier 2, `--sweep`).  It answers "did any of
    *these known-stale* numbers survive."

    This script answers a different question: "of the candidates our
    DECLARED detectors can see across the transport surface, has each one
    been judged." It reuses the audit script's Tier-2 net verbatim (parsed
    live out of the `.sh` file, at run time, so the nets cannot drift apart)
    as the primary *candidate detector*, then adds structure the audit
    script does not have: per-notebook-cell / per-tasks_data-key
    attribution, stable content-sensitive candidate ids, a committed
    judgment file, and a fail-closed gate that treats "unclassified
    candidate" and "orphaned classification" as build failures.

    Neither script replaces the other. Do not fold one into the other.

DECLARED COVERAGE, NOT EXHAUSTIVENESS -- read this before trusting a
"N/N classified" count from this tool. No regex net can prove it has seen
every claim in free-form prose; that is not a property a script can
establish about natural language. What this script CAN honestly claim, and
does, is *declared* coverage: "every line matching one of these THREE named
detectors, over these named surfaces" -- with each detector's own blind
spot stated below, so a reader can judge what is and is not covered rather
than take "exhaustive" on faith. A "249/249 classified" (or any N/N) count
is coverage over the union of the declared detectors' matches -- never a
claim that no further claim-shaped prose exists outside that union. Each
time a detector's blind spot is discovered (as `word_only` and
`r_without_n` were, both found by hand-reading real notebook prose the
first two detectors missed), the honest move is to add another named,
scoped detector and state its own limits -- not to claim the new total is
now exhaustive either.

Three independent candidate nets (the second and third close the coverage
hole found in DESIGN_DOCS/codex_reviews/T0/consolidated_out.md, finding 3,
item 7/8 -- ``r_and_n`` alone structurally cannot see an unnumbered claim):

    ``r_and_n`` -- the audit script's Tier-2 net verbatim, described above:
        a line must carry BOTH a result word AND a number. This is the
        ORIGINAL net and is unchanged in every respect (same source, same
        matching, same call sites for python_module scanning). Declared
        blind spot: any claim-shaped line missing either half -- most
        commonly, a claim with no digit in it at all.

    ``r_without_n`` -- the audit script's live R pattern (the SAME result-
        word vocabulary as ``r_and_n``, loaded from the same source), with
        the number requirement dropped, over PROSE ONLY (below). Added
        because a first attempt at closing the coverage hole with only
        ``word_only`` (a deliberately different, narrow vocabulary) still
        missed a further 22 lines that carry R's own result-word vocabulary
        but no number -- verified examples, all causal or definitional:
        01t cell 6 "...all of this spreading **lowers the peak**, so an
        on-centerline plume can be **diluted below the threshold**"; 01t
        cell 8 "Effective porosity is rarely measured directly and sets the
        mean water velocity, so it directly controls arrival time"; 03t
        cell 7 "The two rules of thumb above are **not universal constants
        of transport**..."; 04t cell 26 "If the numerical plume matches
        this curve -- arrival, longitudinal and transverse spread -- the
        **engine is sound**...". Declared blind spot: any claim-shaped line
        that uses NONE of R's result-word vocabulary (that is exactly what
        ``word_only`` exists to catch instead).

    ``word_only`` -- a THIRD, independent net for claims using NEITHER
        R's vocabulary NOR a number. A verified example: 01t_model_goal.ipynb
        cell 6 contains "...a plume whose centerline would just bypass can
        **clip** the well at low concentration (a marginal bypass becomes a
        small detection)" -- student-facing, causal, and it matches none of
        R (no "peak"/"arrival"/"threshold"/etc.), no digit, so
        ``r_without_n`` cannot see it either. It is a genuinely separate,
        independently defined vocabulary (``WORD_ONLY_PATTERN_SOURCE``):
        the transport track's own capture-vs-bypass outcome/detection
        language (`detect`, `captur[e/ed/ing]`, `bypass`, `clip`) -- the
        exact word ("detect") the review finding names, and the words 01t
        itself teaches the capture-vs-bypass verdict with. Declared blind
        spot: any claim-shaped line using neither vocabulary at all (e.g. a
        claim phrased purely in terms this project has not yet named).

    Per the T0_2a plan's own precedent -- the audit script's own two tiers
    are "deliberately not supersets of each other" -- ``r_without_n`` and
    ``word_only`` are two genuinely different vocabularies (R vs. a
    separate capture/bypass/detect list), not one net split into
    "with number" / "without number" halves of the same list twice over.

    PRECEDENCE when a line matches more than one net: recorded ONCE, most
    specific first -- ``r_and_n`` > ``r_without_n`` > ``word_only``. A line
    satisfying ``r_and_n`` is also, trivially, a superset match of
    ``r_without_n`` (same R vocabulary, weaker condition) and often of
    ``word_only`` too; reporting the strongest net that matched keeps each
    candidate's `detector` field meaningful ("the least the net needed to
    find this") instead of ambiguous. See ``merge_detector_hits``.

    ``r_without_n`` and ``word_only`` are BOTH scoped to PROSE ONLY:
    notebook markdown cells, and tasks_data.py entries in the six
    claim-bearing dicts. Neither is run over notebook code cells, the four
    transport model/test modules, or the three test modules. Reason: those
    surfaces are source code, not claim prose -- a vocabulary net with no
    number requirement over Python source would match on essentially every
    line that mentions a variable/function touching capture, bypass,
    detection, a peak, a threshold, or an arrival/breakthrough computation,
    drowning the small number of genuine unnumbered prose claims in noise
    the classification file was never meant to carry. ``r_and_n`` is
    unaffected by this scoping decision and still runs over every surface
    it always has (notebook code cells included, and the model/test
    modules) -- only ``r_without_n`` and ``word_only`` are prose-restricted.

What this script does, each run:
    1. Enumerate every line matching one of the three DECLARED detectors
       (``r_and_n`` / ``r_without_n`` / ``word_only``, above) across the
       fixed scope (six transport notebooks, tasks_data.py's claim-bearing
       dicts, and the transport model/test modules) as a *candidate* -- this
       half is COVERAGE (of the declared detectors, not of "every claim" --
       see "DECLARED COVERAGE, NOT EXHAUSTIVENESS" above), and it is fully
       deterministic and machine-generated.
    2. Load the committed classification file (JUDGMENT, hand-maintained).
    3. Join the two: any candidate absent from the classification file (or
       present but still `unclassified`) fails the run; any classification
       entry whose candidate id no longer exists (an "orphan" -- the claim
       it pointed at was edited or deleted) also fails the run.
    4. Write a deterministic JSON report and a human-readable Markdown table
       (both byte-identical across repeated runs against unchanged inputs).

Usage:
    uv run python _SUPPORT/src/scripts/transport_claim_inventory.py
        Enumerate, join against the committed classification file, write
        DOCUMENTATION/contracts/T0_2a_claim_inventory.{json,md}, exit 0 iff
        every candidate is classified and no orphans exist.

    uv run python _SUPPORT/src/scripts/transport_claim_inventory.py \
        --init-classifications
        (Re)write the classification file: add every newly discovered
        candidate as `unclassified`, drop entries whose candidate no longer
        exists (printing what was dropped), and leave already-judged entries
        untouched. This is the only mode that writes the classification
        file; it is how the file in this repo was first generated (with
        every real candidate left `unclassified` -- classifying real content
        is the lecturer's judgment call, not this script's).

Design constraints (T0_2a_claim_inventory_plan.md, S4):
    - Notebooks are parsed as JSON, never as flat text; every notebook
      candidate carries the cell index AND the cell id (line numbers drift
      on re-execution and are never used as identity).
    - tasks_data.py's claim-bearing dicts are discovered by AST, not
      hard-coded by name: every top-level `NAME = {...}` assignment is a
      candidate dict unless its name is in `TASKS_DATA_EXCLUDED_DICTS`
      (recorded, with reason, in the output).
    - Candidate id = sha1(path | cell_id-or-key | dict_name | normalised
      matched text)[:12] -- content-sensitive on purpose, so rewording a
      claim retires its id and resurfaces the reworded text as a fresh
      `unclassified` candidate.
    - Output is deterministic: sorted, no timestamps, no absolute paths, no
      set-iteration order reaching the artifacts.
    - Static only: source files are read and parsed (ast.parse, json.load),
      never imported, never executed. No MODFLOW runs, no network.
    - Read-only with respect to every inventoried (scope) file.
    - `claim_type` is a LIST of one or more of `numeric`, `threshold-decision`,
      `causal`, `illustrative` -- a single text span can assert more than one
      kind of claim (e.g. "peak is 5.3 mg/L ... still above the 1.0 mg/L
      threshold" is both `numeric` and `threshold-decision`), and each type is
      evaluated differently downstream, so collapsing a span to one type can
      silently drop a claim. `unclassified` and `not_a_claim` are EXCLUSIVE
      sentinels: never combined with each other or with a real claim type.
      Emitted in a stable sorted order (`sort_claim_types`) so determinism
      (AC3) holds regardless of the order a human typed the list in.
    - Every candidate carries a `detector` field, one of `"r_and_n"`,
      `"r_without_n"`, `"word_only"`, recording which net found it, at the
      stated precedence (see the "Three independent candidate nets" section
      above -- ``r_and_n`` > ``r_without_n`` > ``word_only``). It is NEVER
      part of the candidate id hash -- a candidate's identity must not churn
      depending on which net happened to notice it, and the nets can and do
      overlap on the same line (see above).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Scope: the fixed enumerated surface (T0_2a plan S3), restricted from the
# frozen PATHS list in _SUPPORT/src/scripts/transport_stale_number_audit.sh.
# ---------------------------------------------------------------------------

SCOPE_RELATIVE_PATHS: tuple[str, ...] = (
    "PROJECT/transport/01t_model_goal.ipynb",
    "PROJECT/transport/02t_perceptual_model.ipynb",
    "PROJECT/transport/03t_modflow_transport.ipynb",
    "PROJECT/transport/04t_model_implementation.ipynb",
    "PROJECT/transport/05t_calibration.ipynb",
    "PROJECT/transport/08t_model_application.ipynb",
    "_SUPPORT/src/scripts/scripts_exercises/tasks_data.py",
    "_SUPPORT/src/transport_srcpulse_demo.py",
    "_SUPPORT/src/transport_base_model.py",
    "_SUPPORT/src/transport_prt_capture.py",
    "_SUPPORT/src/transport_verify_2d.py",
    "_SUPPORT/tests/test_transport_srcpulse_demo.py",
    "_SUPPORT/tests/test_transport_prt_capture.py",
    "_SUPPORT/tests/test_transport_verify_2d.py",
)

TASKS_DATA_BASENAME = "tasks_data.py"

# Registries verified (T0_2a plan S4.2) to carry no textual claims -- they
# map checkpoint keys to Python callables, not to claim text. Excluded BY
# NAME; the exclusion (and reason) is recorded in every generated report.
TASKS_DATA_EXCLUDED_DICTS: tuple[str, ...] = (
    "task_functions",
    "task_functions_start",
)
TASKS_DATA_EXCLUDED_REASON = "registry of task-key -> callable; carries no claim text"

# tasks_data.py is SHARED between the flow track (`taskNN_checkpoint_*`, e.g.
# "task04_checkpoint_1") and the transport track (`task_tNN_checkpoint_*`,
# e.g. "task_t04_checkpoint_1"). T0.2a's scope is the transport track only
# (T0_2a_claim_inventory_plan.md S4.3, marked critical): a key is in scope
# here iff it matches TRANSPORT_KEY_PATTERN. Flow-track keys are recognised
# (FLOW_KEY_PATTERN) purely so track discrimination is testable/auditable --
# they are counted as "skipped, non-transport" and never turned into
# candidates.
TRANSPORT_KEY_PATTERN = re.compile(r"^task_t[0-9]+_")
FLOW_KEY_PATTERN = re.compile(r"^task[0-9]+_")

AUDIT_SCRIPT_RELATIVE_PATH = "_SUPPORT/src/scripts/transport_stale_number_audit.sh"

# The third, independent "word_only" net (T0_2a coverage-hole fix; see the
# module docstring's "Three independent candidate nets" section). This
# vocabulary is defined HERE, in this script -- unlike r_pattern/n_pattern
# it is not extracted from the audit script, because it is not shared with
# it: the audit script's own job never needed unnumbered detection/causal
# language and gains nothing from carrying this vocabulary. Deliberately a
# SEPARATE, independently-defined word list distinct from R, so `word_only`
# and `r_without_n` (R's own vocabulary, number requirement dropped -- see
# below) are two genuinely different nets rather than one list counted
# twice (same reasoning as the audit script's own Tier 1 / Tier 2 nets:
# "deliberately not supersets of each other"). Case-insensitive: prose
# capitalises these words at sentence starts and in headers.
WORD_ONLY_PATTERN_SOURCE = r"detect|captur|bypass|clip"

DETECTOR_R_AND_N = "r_and_n"
DETECTOR_R_WITHOUT_N = "r_without_n"
DETECTOR_WORD_ONLY = "word_only"

# Precedence when a line satisfies more than one net: report the single
# strongest detector, most-specific first. A candidate's `detector` field
# is therefore never a list -- it names the LEAST net that sufficed to find
# it, per the module docstring's "PRECEDENCE" paragraph.
DETECTOR_PRECEDENCE: tuple[str, ...] = (
    DETECTOR_R_AND_N,
    DETECTOR_R_WITHOUT_N,
    DETECTOR_WORD_ONLY,
)

CLAIM_TYPE_VALUES: tuple[str, ...] = (
    "unclassified",
    "numeric",
    "threshold-decision",
    "causal",
    "illustrative",
    "not_a_claim",
)
UNCLASSIFIED = "unclassified"
REJECTED_VALUE = "not_a_claim"

# A candidate's `claim_type` is a SET (emitted as a sorted list), because one
# text span can assert more than one kind of claim -- e.g. "peak is 5.3 mg/L
# ... still above the 1.0 mg/L threshold" is both `numeric` and
# `threshold-decision`, and losing either half silently drops a claim that
# may be judged differently downstream. `unclassified` and `not_a_claim` are
# the two EXCLUSIVE sentinels: a candidate is either not-yet-judged, or noise,
# or one-or-more real claim types -- never a mix. Enforced in
# load_classifications() as a hard validation error, not a warning.
EXCLUSIVE_CLAIM_TYPES: tuple[str, ...] = (UNCLASSIFIED, REJECTED_VALUE)

_CLAIM_TYPE_ORDER = {value: index for index, value in enumerate(CLAIM_TYPE_VALUES)}


def sort_claim_types(values) -> list[str]:
    """Stable canonical ordering (CLAIM_TYPE_VALUES order), for determinism
    (AC3): the same set of types must always serialise to the same list."""
    return sorted(values, key=lambda v: _CLAIM_TYPE_ORDER.get(v, len(_CLAIM_TYPE_ORDER)))


DEFAULT_CLASSIFICATIONS_RELATIVE = (
    "_SUPPORT/src/scripts/transport_claim_classifications.yaml"
)
DEFAULT_JSON_OUT_RELATIVE = "DOCUMENTATION/contracts/T0_2a_claim_inventory.json"
DEFAULT_MD_OUT_RELATIVE = "DOCUMENTATION/contracts/T0_2a_claim_inventory.md"


class ClaimInventoryError(RuntimeError):
    """Raised on any fail-closed condition (parse error, malformed scope)."""


# ---------------------------------------------------------------------------
# Candidate model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    id: str
    path: str  # repo-relative, posix separators
    source_kind: str  # "notebook_cell" | "tasks_data_dict" | "python_module"
    order_index: int  # cell index (notebooks) or start line (everything else)
    cell_index: int | None
    cell_id: str | None
    cell_id_synthetic: bool
    dict_name: str | None
    checkpoint_key: str | None
    scope_symbol: str | None  # enclosing top-level def/class for python_module
    line_number: int  # first matching line, for human navigation only
    matched_text: str
    detector: str  # "r_and_n" | "r_without_n" | "word_only" -- NOT part of the id hash

    def sort_key(self):
        return (
            self.path,
            self.order_index,
            self.checkpoint_key or "",
            self.id,
        )


@dataclass
class Coverage:
    files_visited: int = 0
    notebook_cells_visited: int = 0
    tasks_data_dict_entries_visited: int = 0
    tasks_data_dict_entries_skipped_non_transport: int = 0
    python_module_files_visited: int = 0
    candidates_found: int = 0


# ---------------------------------------------------------------------------
# Net: load the Tier-2 result-word x number regex straight out of the audit
# script, so the two nets are structurally guaranteed to stay identical.
# ---------------------------------------------------------------------------


def load_net_patterns(repo_root: Path) -> tuple[re.Pattern[str], re.Pattern[str]]:
    audit_path = repo_root / AUDIT_SCRIPT_RELATIVE_PATH
    try:
        text = audit_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClaimInventoryError(
            f"cannot read audit script for the shared net: {audit_path}: {exc}"
        ) from exc

    r_match = re.search(r"(?m)^\s*R='(.*)'\s*$", text)
    n_match = re.search(r"(?m)^\s*N='(.*)'\s*$", text)
    if r_match is None or n_match is None:
        raise ClaimInventoryError(
            "could not locate the Tier-2 R= / N= net in "
            f"{AUDIT_SCRIPT_RELATIVE_PATH}; the audit script's --sweep "
            "branch shape changed and this script's net extraction must be "
            "updated to match (fail closed rather than silently using a "
            "stale net)"
        )
    try:
        r_pattern = re.compile(r_match.group(1))
        n_pattern = re.compile(n_match.group(1))
    except re.error as exc:
        raise ClaimInventoryError(f"shared net failed to compile: {exc}") from exc
    return r_pattern, n_pattern


def compile_word_only_pattern() -> re.Pattern[str]:
    """Compile the third, independent word-only net (see module docstring
    and WORD_ONLY_PATTERN_SOURCE). Unlike load_net_patterns, this vocabulary
    is not read from the audit script -- it belongs to this script alone."""
    try:
        return re.compile(WORD_ONLY_PATTERN_SOURCE, re.IGNORECASE)
    except re.error as exc:
        raise ClaimInventoryError(f"word-only net failed to compile: {exc}") from exc


def normalise_text(text: str) -> str:
    return " ".join(text.split())


def find_net_hits(
    lines: list[str],
    r_pattern: re.Pattern[str],
    n_pattern: re.Pattern[str],
    first_lineno: int,
) -> list[tuple[int, str]]:
    """Return [(lineno, normalised_text), ...] for lines matching R AND N."""
    hits: list[tuple[int, str]] = []
    for offset, raw_line in enumerate(lines):
        if r_pattern.search(raw_line) and n_pattern.search(raw_line):
            normalised = normalise_text(raw_line)
            if normalised:
                hits.append((first_lineno + offset, normalised))
    return hits


def find_single_pattern_hits(
    lines: list[str],
    pattern: re.Pattern[str],
    first_lineno: int,
) -> list[tuple[int, str]]:
    """Return [(lineno, normalised_text), ...] for lines matching ONE
    pattern, no second condition. Shared shape for both single-condition
    nets (``r_without_n`` and ``word_only``) so they are trivially
    comparable; find_net_hits (the two-condition r_and_n net) is left
    completely untouched, as required."""
    hits: list[tuple[int, str]] = []
    for offset, raw_line in enumerate(lines):
        if pattern.search(raw_line):
            normalised = normalise_text(raw_line)
            if normalised:
                hits.append((first_lineno + offset, normalised))
    return hits


def find_r_without_n_hits(
    lines: list[str],
    r_pattern: re.Pattern[str],
    first_lineno: int,
) -> list[tuple[int, str]]:
    """Return [(lineno, normalised_text), ...] for lines matching the
    r_without_n net: the SAME live R pattern as r_and_n, number requirement
    dropped. Prose-scoped only (module docstring)."""
    return find_single_pattern_hits(lines, r_pattern, first_lineno)


def find_word_only_hits(
    lines: list[str],
    word_pattern: re.Pattern[str],
    first_lineno: int,
) -> list[tuple[int, str]]:
    """Return [(lineno, normalised_text), ...] for lines matching the
    word-only net (WORD_ONLY_PATTERN_SOURCE) -- a vocabulary independent of
    R, no number required. Prose-scoped only (module docstring)."""
    return find_single_pattern_hits(lines, word_pattern, first_lineno)


def merge_detector_hits(
    rn_hits: list[tuple[int, str]],
    r_without_n_hits: list[tuple[int, str]],
    word_hits: list[tuple[int, str]],
) -> list[tuple[int, str, str]]:
    """Merge the three nets' hits for one scan unit (a notebook cell, or
    one tasks_data entry) into a single per-line candidate list tagged with
    which net found it, at DETECTOR_PRECEDENCE order (r_and_n >
    r_without_n > word_only -- module docstring, "PRECEDENCE"). A line
    satisfying more than one net is emitted ONCE, tagged with the
    strongest net that matched -- so each weaker net's reported
    contribution is exactly its NEW, unique-to-it surface."""
    rn_by_line = {lineno: normalised for lineno, normalised in rn_hits}
    r_wo_n_by_line = {
        lineno: normalised for lineno, normalised in r_without_n_hits
    }
    merged = [
        (lineno, normalised, DETECTOR_R_AND_N) for lineno, normalised in rn_hits
    ]
    for lineno, normalised in r_without_n_hits:
        if lineno in rn_by_line:
            continue
        merged.append((lineno, normalised, DETECTOR_R_WITHOUT_N))
    for lineno, normalised in word_hits:
        if lineno in rn_by_line or lineno in r_wo_n_by_line:
            continue
        merged.append((lineno, normalised, DETECTOR_WORD_ONLY))
    return merged


def make_candidate_id(
    path: str, identity: str, dict_name: str, normalised_text: str
) -> str:
    payload = "|".join([path, identity, dict_name, normalised_text])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Notebook scanning (AC1 / AC4)
# ---------------------------------------------------------------------------


def _cell_source_lines(cell: dict) -> list[str]:
    source = cell.get("source", "")
    if isinstance(source, list):
        text = "".join(source)
    else:
        text = str(source)
    # splitlines() drops the record of trailing content correctly and keeps
    # per-source-line granularity, matching how the audit script's grep -n
    # attributes a match to "a line".
    return text.splitlines()


def scan_notebook(
    nb_path: Path,
    repo_root: Path,
    r_pattern: re.Pattern[str],
    n_pattern: re.Pattern[str],
    word_pattern: re.Pattern[str],
    coverage: Coverage,
) -> list[Candidate]:
    rel_path = nb_path.relative_to(repo_root).as_posix()
    try:
        raw = nb_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClaimInventoryError(f"cannot read notebook {rel_path}: {exc}") from exc
    try:
        notebook = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClaimInventoryError(
            f"notebook {rel_path} is not valid JSON: {exc}"
        ) from exc

    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise ClaimInventoryError(f"notebook {rel_path} has no cell list")

    candidates: list[Candidate] = []
    for cell_index, cell in enumerate(cells):
        cell_type = cell.get("cell_type")
        if cell_type not in ("markdown", "code"):
            # Only markdown/code carry claim text; nbformat also allows
            # "raw" cells, which are visited (counted) but never scanned --
            # they hold no rendered/executed claim text.
            coverage.notebook_cells_visited += 1
            continue

        coverage.notebook_cells_visited += 1
        cell_id = cell.get("id")
        cell_id_synthetic = cell_id is None
        if cell_id_synthetic:
            # nbformat_minor < 5 notebooks (verified: 01t/02t/03t in this
            # repo) do not carry a cell `id` field. Fall back to a stable,
            # index-derived synthetic id so every candidate still carries
            # *some* cell identity, and flag it as synthetic so downstream
            # readers know it is not a real nbformat cell id.
            cell_id = f"idx-{cell_index}"

        lines = _cell_source_lines(cell)
        rn_hits = find_net_hits(lines, r_pattern, n_pattern, first_lineno=1)
        # r_without_n and word_only are prose-scoped: markdown cells only
        # (module docstring, "Three independent candidate nets"). Code
        # cells keep getting r_and_n exactly as before and nothing else.
        if cell_type == "markdown":
            r_without_n_hits = find_r_without_n_hits(lines, r_pattern, first_lineno=1)
            word_hits = find_word_only_hits(lines, word_pattern, first_lineno=1)
        else:
            r_without_n_hits = []
            word_hits = []
        hits = merge_detector_hits(rn_hits, r_without_n_hits, word_hits)
        for lineno, normalised, detector in hits:
            cand_id = make_candidate_id(rel_path, cell_id, "", normalised)
            candidates.append(
                Candidate(
                    id=cand_id,
                    path=rel_path,
                    source_kind="notebook_cell",
                    order_index=cell_index,
                    cell_index=cell_index,
                    cell_id=cell_id,
                    cell_id_synthetic=cell_id_synthetic,
                    dict_name=None,
                    checkpoint_key=None,
                    scope_symbol=None,
                    line_number=lineno,
                    matched_text=normalised,
                    detector=detector,
                )
            )
    return candidates


# ---------------------------------------------------------------------------
# tasks_data.py scanning (AC2 / AC5 / AC5b): dicts discovered by AST.
# ---------------------------------------------------------------------------


@dataclass
class ExcludedDict:
    path: str
    name: str
    reason: str


def _iter_top_level_dict_assigns(tree: ast.Module):
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        yield node.targets[0].id, node.value


def scan_tasks_data(
    py_path: Path,
    repo_root: Path,
    r_pattern: re.Pattern[str],
    n_pattern: re.Pattern[str],
    word_pattern: re.Pattern[str],
    coverage: Coverage,
) -> tuple[list[Candidate], list[ExcludedDict]]:
    rel_path = py_path.relative_to(repo_root).as_posix()
    try:
        text = py_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClaimInventoryError(f"cannot read {rel_path}: {exc}") from exc
    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError as exc:
        raise ClaimInventoryError(f"{rel_path} failed to parse: {exc}") from exc

    lines = text.splitlines()
    candidates: list[Candidate] = []
    excluded: list[ExcludedDict] = []

    for dict_name, dict_node in _iter_top_level_dict_assigns(tree):
        if dict_name in TASKS_DATA_EXCLUDED_DICTS:
            excluded.append(
                ExcludedDict(
                    path=rel_path, name=dict_name, reason=TASKS_DATA_EXCLUDED_REASON
                )
            )
            continue

        for key_node, value_node in zip(dict_node.keys, dict_node.values):
            if key_node is None or not (
                isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)
            ):
                raise ClaimInventoryError(
                    f"{rel_path}: dict '{dict_name}' has a non-string-constant "
                    f"key at line {getattr(key_node, 'lineno', '?')}; claim "
                    "inventory requires string checkpoint keys"
                )
            checkpoint_key = key_node.value

            if not TRANSPORT_KEY_PATTERN.match(checkpoint_key):
                # Flow-track key (`taskNN_...`) or something else entirely --
                # out of T0.2a's scope. Counted, never turned into a
                # candidate: track discrimination must be visible, not silent.
                coverage.tasks_data_dict_entries_skipped_non_transport += 1
                continue

            coverage.tasks_data_dict_entries_visited += 1
            start = key_node.lineno
            end = getattr(value_node, "end_lineno", None) or start
            # 1-based inclusive slice of the raw source, so inline comments
            # on the same line as the value are captured (comments are not
            # part of the AST but frequently carry the actual claim text,
            # e.g. "# Correct solution ~126 million m3 (...)").
            entry_lines = lines[start - 1 : end]
            rn_hits = find_net_hits(entry_lines, r_pattern, n_pattern, first_lineno=start)
            # r_without_n / word_only are prose-scoped: every claim-bearing
            # tasks_data.py entry is claim prose (question/solution/units
            # text), so both are in scope -- unlike notebook code cells or
            # the model/test modules (module docstring, "Three independent
            # candidate nets").
            r_without_n_hits = find_r_without_n_hits(
                entry_lines, r_pattern, first_lineno=start
            )
            word_hits = find_word_only_hits(entry_lines, word_pattern, first_lineno=start)
            hits = merge_detector_hits(rn_hits, r_without_n_hits, word_hits)
            for lineno, normalised, detector in hits:
                cand_id = make_candidate_id(
                    rel_path, checkpoint_key, dict_name, normalised
                )
                candidates.append(
                    Candidate(
                        id=cand_id,
                        path=rel_path,
                        source_kind="tasks_data_dict",
                        order_index=start,
                        cell_index=None,
                        cell_id=None,
                        cell_id_synthetic=False,
                        dict_name=dict_name,
                        checkpoint_key=checkpoint_key,
                        scope_symbol=None,
                        line_number=lineno,
                        matched_text=normalised,
                        detector=detector,
                    )
                )
    return candidates, excluded


# ---------------------------------------------------------------------------
# Plain-module scanning (the four transport_*.py + three test_*.py files):
# AST is used only for syntax validation (fail closed on SyntaxError) and to
# attribute a match to its enclosing top-level def/class, since line numbers
# alone are not a stable identity.
# ---------------------------------------------------------------------------


def _line_to_scope_symbol(tree: ast.Module, total_lines: int) -> list[str]:
    symbols = ["<module>"] * (total_lines + 1)  # 1-indexed; index 0 unused
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", start) or start
            for lineno in range(start, min(end, total_lines) + 1):
                symbols[lineno] = node.name
    return symbols


def scan_python_module(
    py_path: Path,
    repo_root: Path,
    r_pattern: re.Pattern[str],
    n_pattern: re.Pattern[str],
    coverage: Coverage,
) -> list[Candidate]:
    rel_path = py_path.relative_to(repo_root).as_posix()
    try:
        text = py_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClaimInventoryError(f"cannot read {rel_path}: {exc}") from exc
    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError as exc:
        raise ClaimInventoryError(f"{rel_path} failed to parse: {exc}") from exc

    lines = text.splitlines()
    scope_symbols = _line_to_scope_symbol(tree, len(lines))
    coverage.python_module_files_visited += 1

    candidates: list[Candidate] = []
    # No r_without_n / word_only net here (module docstring, "Three
    # independent candidate nets"): the four transport_*.py modules and
    # three test_*.py modules are source code, not claim prose, and are
    # explicitly excluded from both prose-scoped nets. Only r_and_n runs
    # over these files.
    hits = find_net_hits(lines, r_pattern, n_pattern, first_lineno=1)
    for lineno, normalised in hits:
        symbol = scope_symbols[lineno] if lineno < len(scope_symbols) else "<module>"
        cand_id = make_candidate_id(rel_path, symbol, "", normalised)
        candidates.append(
            Candidate(
                id=cand_id,
                path=rel_path,
                source_kind="python_module",
                order_index=lineno,
                cell_index=None,
                cell_id=None,
                cell_id_synthetic=False,
                dict_name=None,
                checkpoint_key=None,
                scope_symbol=symbol,
                line_number=lineno,
                matched_text=normalised,
                detector=DETECTOR_R_AND_N,
            )
        )
    return candidates


# ---------------------------------------------------------------------------
# Enumeration over the scope list
# ---------------------------------------------------------------------------


def enumerate_candidates(
    repo_root: Path,
    scope_paths: list[Path],
    r_pattern: re.Pattern[str],
    n_pattern: re.Pattern[str],
    word_pattern: re.Pattern[str],
) -> tuple[list[Candidate], list[ExcludedDict], Coverage]:
    coverage = Coverage()
    all_candidates: list[Candidate] = []
    all_excluded: list[ExcludedDict] = []

    for path in scope_paths:
        if not path.is_file():
            rel = _safe_rel(path, repo_root)
            raise ClaimInventoryError(f"scope file does not exist: {rel}")
        coverage.files_visited += 1

        if path.suffix == ".ipynb":
            candidates = scan_notebook(
                path, repo_root, r_pattern, n_pattern, word_pattern, coverage
            )
        elif path.name == TASKS_DATA_BASENAME:
            candidates, excluded = scan_tasks_data(
                path, repo_root, r_pattern, n_pattern, word_pattern, coverage
            )
            all_excluded.extend(excluded)
        elif path.suffix == ".py":
            candidates = scan_python_module(
                path, repo_root, r_pattern, n_pattern, coverage
            )
        else:
            raise ClaimInventoryError(
                f"scope file has an unrecognised type (not .ipynb/.py): "
                f"{_safe_rel(path, repo_root)}"
            )
        all_candidates.extend(candidates)

    coverage.candidates_found = len(all_candidates)
    all_candidates.sort(key=lambda c: c.sort_key())
    all_excluded.sort(key=lambda e: (e.path, e.name))
    return all_candidates, all_excluded, coverage


def _safe_rel(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Classification file (judgment half)
# ---------------------------------------------------------------------------


def _validate_claim_type_list(cand_id: str, value, path: Path) -> list[str]:
    """Validate one entry's `claim_type` field and return it in canonical
    sorted order. Fails closed (raises) rather than warning -- an invalid
    entry is a build failure, per the lecturer's decision that exclusivity
    is enforced, not merely encouraged."""
    if not isinstance(value, list) or not value:
        raise ClaimInventoryError(
            f"classification file {path}: entry '{cand_id}' has claim_type "
            f"{value!r}; must be a non-empty list"
        )
    if len(value) != len(set(value)):
        raise ClaimInventoryError(
            f"classification file {path}: entry '{cand_id}' has duplicate "
            f"claim_type entries: {value!r}"
        )
    for item in value:
        if item not in CLAIM_TYPE_VALUES:
            raise ClaimInventoryError(
                f"classification file {path}: entry '{cand_id}' has an "
                f"unrecognised claim_type value {item!r}; must be one of "
                f"{CLAIM_TYPE_VALUES}"
            )
    for exclusive_value in EXCLUSIVE_CLAIM_TYPES:
        if exclusive_value in value and len(value) != 1:
            raise ClaimInventoryError(
                f"classification file {path}: entry '{cand_id}' combines "
                f"exclusive claim_type {exclusive_value!r} with other "
                f"type(s) {sorted(set(value) - {exclusive_value})!r}; "
                f"{exclusive_value!r} may never appear alongside another "
                "type -- a candidate is either not-yet-judged, or noise, "
                "or one-or-more real claim types, never a mix"
            )
    return sort_claim_types(value)


def load_classifications(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClaimInventoryError(f"cannot read classification file {path}: {exc}") from exc
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ClaimInventoryError(
            f"classification file {path} is not valid YAML: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ClaimInventoryError(
            f"classification file {path} must be a mapping of id -> entry"
        )
    for cand_id, entry in data.items():
        if not isinstance(entry, dict) or "claim_type" not in entry:
            raise ClaimInventoryError(
                f"classification file {path}: entry '{cand_id}' must be a "
                "mapping with a 'claim_type' key"
            )
        entry["claim_type"] = _validate_claim_type_list(cand_id, entry["claim_type"], path)
    return data


def write_classifications(path: Path, entries: dict[str, dict]) -> None:
    header = "\n".join(
        [
            "# T0.2a transport claim classifications.",
            "#",
            "# Generated by _SUPPORT/src/scripts/transport_claim_inventory.py "
            "--init-classifications.",
            "# Only the `claim_type` field is read by the coverage gate; the",
            "# other fields are informational context for the human doing the",
            "# judging and are refreshed on every --init-classifications run.",
            "#",
            "# `detector` records which candidate net found this entry (most",
            "# specific, if more than one net matched -- r_and_n > r_without_n >",
            "# word_only):",
            "#   r_and_n     -- the original net (a result word AND a number,",
            "#                  same line)",
            "#   r_without_n -- R's own result-word vocabulary, no number required",
            "#                  (prose-scoped)",
            "#   word_only   -- a separate detect/capture/bypass/clip vocabulary,",
            "#                  no number required (prose-scoped)",
            "# All three are DECLARED coverage, not proof of exhaustiveness -- see",
            "# the script's module docstring for each net's own blind spot.",
            "# `detector` is informational only, like path/location/snippet -- not",
            "# read by the gate, and never part of a candidate's id.",
            "#",
            "# claim_type is a LIST, not a single value: one text span can assert",
            "# more than one kind of claim (e.g. \"peak is 5.3 mg/L ... still above",
            "# the 1.0 mg/L threshold\" is both numeric AND threshold-decision).",
            "# A single-element list is the normal case; list two or more entries",
            "# when a span genuinely asserts more than one claim type.",
            "#",
            f"# each entry must be one of: {', '.join(CLAIM_TYPE_VALUES)}",
            "#   unclassified        -- not yet judged (fails the gate)",
            "#   numeric              -- a specific number/range is asserted",
            "#   threshold-decision   -- a claim that a value crosses/misses a "
            "threshold",
            "#   causal                -- a claim that X causes/drives/controls Y",
            "#   illustrative          -- a worked-example number, not a general "
            "claim",
            "#   not_a_claim           -- net noise (code, axis label, etc.), "
            "not a claim at all",
            "#",
            "# unclassified and not_a_claim are EXCLUSIVE: a candidate is either",
            "# not-yet-judged, or noise, or one-or-more real claim types -- never a",
            "# mix. claim_type: [unclassified, numeric] or [not_a_claim, causal] is",
            "# a validation error, not a warning.",
            "",
        ]
    )

    # One field-ordered mapping per candidate id, dumped as a single YAML
    # document via yaml.safe_dump so quoting/escaping of arbitrary matched
    # text (quotes, colons, unicode) is handled correctly by the YAML
    # emitter rather than by hand.
    ordered: dict[str, dict] = {}
    for cand_id in sorted(entries):
        entry = entries[cand_id]
        row = {"claim_type": sort_claim_types(entry["claim_type"])}
        for key in ("path", "location", "detector", "snippet"):
            if key in entry and entry[key] is not None:
                row[key] = str(entry[key]).replace("\n", " ")
        ordered[cand_id] = row

    body = yaml.safe_dump(
        ordered,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    path.write_text(header + "\n" + body, encoding="utf-8")


def build_classification_context(candidate: Candidate) -> dict:
    if candidate.source_kind == "notebook_cell":
        location = f"cell[{candidate.cell_index}] id={candidate.cell_id}"
    elif candidate.source_kind == "tasks_data_dict":
        location = f"{candidate.dict_name}[{candidate.checkpoint_key!r}]"
    else:
        location = f"{candidate.scope_symbol} (line {candidate.line_number})"
    snippet = candidate.matched_text
    if len(snippet) > 160:
        snippet = snippet[:157] + "..."
    return {
        "claim_type": [UNCLASSIFIED],
        "path": candidate.path,
        "location": location,
        "detector": candidate.detector,
        "snippet": snippet,
    }


def init_classifications(
    path: Path, candidates: list[Candidate]
) -> tuple[int, int, list[str]]:
    existing = load_classifications(path)
    candidate_ids = {c.id for c in candidates}
    dropped = sorted(cid for cid in existing if cid not in candidate_ids)

    new_entries: dict[str, dict] = {}
    added = 0
    for candidate in candidates:
        if candidate.id in existing:
            new_entries[candidate.id] = existing[candidate.id]
        else:
            new_entries[candidate.id] = build_classification_context(candidate)
            added += 1

    write_classifications(path, new_entries)
    return added, len(dropped), dropped


# ---------------------------------------------------------------------------
# Join: coverage x judgment -> gate
# ---------------------------------------------------------------------------


@dataclass
class JoinResult:
    unclassified_ids: list[str]
    orphan_ids: list[str]
    by_type: dict[str, int]

    @property
    def ok(self) -> bool:
        return not self.unclassified_ids and not self.orphan_ids


def join_candidates_and_classifications(
    candidates: list[Candidate], classifications: dict[str, dict]
) -> JoinResult:
    candidate_ids = {c.id for c in candidates}

    unclassified_ids = []
    # by_type is an ASSIGNMENT count, not a candidate count: a multi-type
    # candidate is counted once per type it carries (requirement 6), so
    # sum(by_type.values()) is the "(candidate, type) claim assignments"
    # total, which is >= candidates_found and differs from it exactly when a
    # multi-type candidate exists. unclassified/not_a_claim are exclusive
    # (enforced at load time), so by_type[UNCLASSIFIED] and
    # by_type[REJECTED_VALUE] are still exact candidate counts for those two
    # sentinel states.
    by_type: dict[str, int] = {value: 0 for value in CLAIM_TYPE_VALUES}
    for candidate in candidates:
        entry = classifications.get(candidate.id)
        claim_types = entry["claim_type"] if entry is not None else [UNCLASSIFIED]
        for claim_type in claim_types:
            by_type[claim_type] = by_type.get(claim_type, 0) + 1
        if claim_types == [UNCLASSIFIED]:
            unclassified_ids.append(candidate.id)

    orphan_ids = sorted(cid for cid in classifications if cid not in candidate_ids)
    unclassified_ids.sort()

    return JoinResult(
        unclassified_ids=unclassified_ids, orphan_ids=orphan_ids, by_type=by_type
    )


# ---------------------------------------------------------------------------
# Report generation (JSON + Markdown) -- deterministic, no timestamps.
# ---------------------------------------------------------------------------


def build_report(
    candidates: list[Candidate],
    excluded: list[ExcludedDict],
    coverage: Coverage,
    classifications: dict[str, dict],
    join_result: JoinResult,
    scope_relative_paths: tuple[str, ...],
) -> dict:
    # unclassified/not_a_claim are exclusive singleton lists (enforced at
    # load time), so these two buckets of the ASSIGNMENT-count dict are also
    # exact CANDIDATE counts. classified_count must NOT be "sum of the other
    # buckets" -- a multi-type candidate would then be counted more than
    # once; it is candidate-level, so it is candidates_found minus the
    # (also-candidate-level) unclassified count.
    unclassified_count = join_result.by_type.get(UNCLASSIFIED, 0)
    rejected_count = join_result.by_type.get(REJECTED_VALUE, 0)
    classified_count = coverage.candidates_found - unclassified_count
    claim_assignments_found = sum(join_result.by_type.values())

    # by_detector: candidate-level counts (each candidate has exactly one
    # detector), broken out so the word_only net's coverage delta is visible
    # directly in the committed report, not just derivable by hand.
    by_detector: dict[str, int] = {value: 0 for value in DETECTOR_PRECEDENCE}
    for candidate in candidates:
        by_detector[candidate.detector] = by_detector.get(candidate.detector, 0) + 1

    candidate_rows = []
    for candidate in candidates:
        entry = classifications.get(candidate.id)
        claim_type = entry["claim_type"] if entry is not None else [UNCLASSIFIED]
        candidate_rows.append(
            {
                "id": candidate.id,
                "path": candidate.path,
                "source_kind": candidate.source_kind,
                "cell_index": candidate.cell_index,
                "cell_id": candidate.cell_id,
                "cell_id_synthetic": candidate.cell_id_synthetic,
                "dict_name": candidate.dict_name,
                "checkpoint_key": candidate.checkpoint_key,
                "scope_symbol": candidate.scope_symbol,
                "line_number": candidate.line_number,
                "matched_text": candidate.matched_text,
                "claim_type": list(claim_type),
                "detector": candidate.detector,
            }
        )

    return {
        "schema_version": 3,
        "scope_files": list(scope_relative_paths),
        "excluded_dicts": [
            {"path": e.path, "name": e.name, "reason": e.reason} for e in excluded
        ],
        "coverage": {
            "files_visited": coverage.files_visited,
            "notebook_cells_visited": coverage.notebook_cells_visited,
            "tasks_data_dict_entries_visited": coverage.tasks_data_dict_entries_visited,
            "tasks_data_dict_entries_skipped_non_transport": (
                coverage.tasks_data_dict_entries_skipped_non_transport
            ),
            "python_module_files_visited": coverage.python_module_files_visited,
            # candidates_found: unique text spans. claim_assignments_found:
            # (candidate, type) pairs -- >= candidates_found, and strictly
            # greater exactly when a multi-type candidate exists (req. 6).
            "candidates_found": coverage.candidates_found,
            "claim_assignments_found": claim_assignments_found,
            "candidates_classified": classified_count,
            "candidates_rejected": rejected_count,
            "candidates_unclassified": unclassified_count,
            "by_claim_type": dict(sorted(join_result.by_type.items())),
            "by_detector": dict(sorted(by_detector.items())),
        },
        "gate": {
            "ok": join_result.ok,
            "unclassified_ids": join_result.unclassified_ids,
            "orphan_ids": join_result.orphan_ids,
        },
        "candidates": candidate_rows,
    }


def render_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# T0.2a transport claim inventory")
    lines.append("")
    lines.append(
        "Generated by `_SUPPORT/src/scripts/transport_claim_inventory.py`. "
        "Do not hand-edit; re-run the script instead."
    )
    lines.append("")

    cov = report["coverage"]
    lines.append("## Coverage summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    lines.append(f"| Files visited | {cov['files_visited']} |")
    lines.append(f"| Notebook cells visited | {cov['notebook_cells_visited']} |")
    lines.append(
        f"| tasks_data.py dict entries visited (transport track) | "
        f"{cov['tasks_data_dict_entries_visited']} |"
    )
    lines.append(
        f"| tasks_data.py dict entries skipped (flow track / other) | "
        f"{cov['tasks_data_dict_entries_skipped_non_transport']} |"
    )
    lines.append(
        f"| Python module files visited | {cov['python_module_files_visited']} |"
    )
    lines.append(f"| Candidates found | {cov['candidates_found']} |")
    lines.append(
        f"| Claim-type assignments (candidate, type) pairs | "
        f"{cov['claim_assignments_found']} |"
    )
    lines.append(f"| Candidates classified | {cov['candidates_classified']} |")
    lines.append(f"| Candidates rejected (not_a_claim) | {cov['candidates_rejected']} |")
    lines.append(f"| Candidates unclassified | {cov['candidates_unclassified']} |")
    lines.append("")

    lines.append("### By detector")
    lines.append("")
    lines.append(
        "Candidate-level counts, one per candidate (a line matching more "
        "than one net is counted once, under the strongest match --"
        "precedence `r_and_n` > `r_without_n` > `word_only`). `r_and_n` is "
        "the original result-word+number net; `r_without_n` and `word_only` "
        "are the two prose-scoped nets added to close the unnumbered-claim "
        "coverage hole -- see the script's module docstring for what each "
        "one is declared to cover and its own blind spot. This is declared "
        "coverage, not proof of exhaustiveness: it counts candidates found "
        "by these three named detectors, not every claim that might exist."
    )
    lines.append("")
    lines.append("| Detector | Count |")
    lines.append("|---|---|")
    for value, count in sorted(cov["by_detector"].items()):
        lines.append(f"| {value} | {count} |")
    lines.append("")

    lines.append("### By claim type")
    lines.append("")
    lines.append(
        "Assignment counts: a candidate with more than one `claim_type` is "
        "counted once per type it carries, so this can sum to more than "
        "`candidates_found`."
    )
    lines.append("")
    lines.append("| Claim type | Count |")
    lines.append("|---|---|")
    for value, count in sorted(cov["by_claim_type"].items()):
        lines.append(f"| {value} | {count} |")
    lines.append("")

    if report["excluded_dicts"]:
        lines.append("## Excluded tasks_data.py registries")
        lines.append("")
        lines.append("| File | Dict | Reason |")
        lines.append("|---|---|---|")
        for e in report["excluded_dicts"]:
            lines.append(f"| {e['path']} | {e['name']} | {e['reason']} |")
        lines.append("")

    gate = report["gate"]
    lines.append("## Gate result")
    lines.append("")
    lines.append(f"OK: **{gate['ok']}**")
    lines.append("")
    if gate["unclassified_ids"]:
        lines.append(f"Unclassified candidates ({len(gate['unclassified_ids'])}):")
        lines.append("")
        for cand_id in gate["unclassified_ids"]:
            lines.append(f"- `{cand_id}`")
        lines.append("")
    if gate["orphan_ids"]:
        lines.append(f"Orphaned classifications ({len(gate['orphan_ids'])}):")
        lines.append("")
        for cand_id in gate["orphan_ids"]:
            lines.append(f"- `{cand_id}`")
        lines.append("")

    rejected_rows = [c for c in report["candidates"] if c["claim_type"] == [REJECTED_VALUE]]
    if rejected_rows:
        lines.append("## Rejected (not_a_claim) candidates")
        lines.append("")
        lines.append("| Path | Location | Detector | Matched text |")
        lines.append("|---|---|---|---|")
        for c in rejected_rows:
            location = _row_location(c)
            snippet = _escape_table_snippet(c["matched_text"])
            lines.append(f"| {c['path']} | {location} | {c['detector']} | {snippet} |")
        lines.append("")

    lines.append("## Candidates by notebook / module")
    lines.append("")
    current_path = None
    for c in report["candidates"]:
        if c["path"] != current_path:
            current_path = c["path"]
            lines.append(f"### {current_path}")
            lines.append("")
            lines.append(
                "| Location | Checkpoint key | Detector | Claim type(s) | Matched text |"
            )
            lines.append("|---|---|---|---|---|")
        location = _row_location(c)
        key = c["checkpoint_key"] or ""
        claim_type = ", ".join(c["claim_type"])
        snippet = _escape_table_snippet(c["matched_text"])
        lines.append(f"| {location} | {key} | {c['detector']} | {claim_type} | {snippet} |")
    lines.append("")

    return "\n".join(lines) + "\n"


def _escape_table_snippet(text: str) -> str:
    """Render quoted source prose inert inside a Markdown table cell.

    Quoted notebook prose is evidence, not navigation: its relative links point at
    PROJECT/, not at this file's directory, so emitting them live makes the
    check-internal-links gate red (correctly). Neutralise the link-forming
    SEQUENCES only -- not the bare characters -- so $math$, `code spans` and
    <details>/<summary> markup in the quoted text stay byte-identical.

    NOTE: escaping "[" alone is NOT sufficient. MARKDOWN_LINK_RE in
    check_internal_links.py is not backslash-escape-aware; r"\\[a](b)" still
    matches. The load-bearing escape is on "](", not on "[".
    """
    text = text.replace("|", "\\|")
    text = text.replace("](", "]\\(")
    return re.sub(r"<(?=\s*/?\s*(?:a|img)\b)", "&lt;", text, flags=re.IGNORECASE)


def _row_location(c: dict) -> str:
    if c["source_kind"] == "notebook_cell":
        marker = "*" if c["cell_id_synthetic"] else ""
        return f"cell[{c['cell_index']}] id={c['cell_id']}{marker}"
    if c["source_kind"] == "tasks_data_dict":
        return f"{c['dict_name']}"
    return f"{c['scope_symbol']} L{c['line_number']}"


def canonical_json_dumps(report: dict) -> str:
    # sort_keys + fixed separators + trailing newline => byte-identical
    # output for identical input, independent of dict insertion/set order.
    return json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def resolve_repo_root() -> Path:
    # _SUPPORT/src/scripts/transport_claim_inventory.py -> repo root is
    # three parents up (scripts -> src -> _SUPPORT -> repo root).
    return Path(__file__).resolve().parents[3]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: derived from this file's location).",
    )
    parser.add_argument(
        "--scope",
        type=Path,
        nargs="*",
        default=None,
        help=(
            "Override the enumerated scope file list (paths relative to "
            "--repo-root). For testing only; production runs use the fixed "
            "T0.2a scope."
        ),
    )
    parser.add_argument(
        "--classifications",
        type=Path,
        default=None,
        help="Path to the classification YAML (default: the committed file).",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Where to write the JSON report (default: the committed path).",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=None,
        help="Where to write the Markdown report (default: the committed path).",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run the gate but do not write JSON/Markdown outputs.",
    )
    parser.add_argument(
        "--init-classifications",
        action="store_true",
        help=(
            "(Re)write the classification file: add new candidates as "
            "unclassified, drop orphans, leave judged entries untouched. "
            "Does not run the gate."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = (args.repo_root or resolve_repo_root()).resolve()

    if args.scope is not None:
        scope_paths = [repo_root / p for p in args.scope]
        scope_relative = tuple(_safe_rel(p, repo_root) for p in scope_paths)
    else:
        scope_paths = [repo_root / p for p in SCOPE_RELATIVE_PATHS]
        scope_relative = SCOPE_RELATIVE_PATHS

    classifications_path = (
        args.classifications or repo_root / DEFAULT_CLASSIFICATIONS_RELATIVE
    )
    json_out_path = args.json_out or repo_root / DEFAULT_JSON_OUT_RELATIVE
    md_out_path = args.md_out or repo_root / DEFAULT_MD_OUT_RELATIVE

    try:
        r_pattern, n_pattern = load_net_patterns(repo_root)
        word_pattern = compile_word_only_pattern()
        candidates, excluded, coverage = enumerate_candidates(
            repo_root, scope_paths, r_pattern, n_pattern, word_pattern
        )
    except ClaimInventoryError as exc:
        print(f"transport_claim_inventory: FAIL (parse/scope error): {exc}", file=sys.stderr)
        return 2

    if args.init_classifications:
        try:
            added, dropped_count, dropped_ids = init_classifications(
                classifications_path, candidates
            )
        except ClaimInventoryError as exc:
            print(f"transport_claim_inventory: FAIL: {exc}", file=sys.stderr)
            return 2
        print(
            f"transport_claim_inventory: wrote {classifications_path} "
            f"({added} new unclassified, {dropped_count} orphan(s) dropped)"
        )
        if dropped_ids:
            print("dropped orphan ids:", ", ".join(dropped_ids))
        return 0

    try:
        classifications = load_classifications(classifications_path)
    except ClaimInventoryError as exc:
        print(f"transport_claim_inventory: FAIL: {exc}", file=sys.stderr)
        return 2

    join_result = join_candidates_and_classifications(candidates, classifications)
    report = build_report(
        candidates, excluded, coverage, classifications, join_result, scope_relative
    )

    if not args.no_write:
        json_out_path.parent.mkdir(parents=True, exist_ok=True)
        md_out_path.parent.mkdir(parents=True, exist_ok=True)
        json_out_path.write_text(canonical_json_dumps(report), encoding="utf-8")
        md_out_path.write_text(render_markdown(report), encoding="utf-8")

    print(
        f"transport_claim_inventory: {coverage.files_visited} files, "
        f"{coverage.candidates_found} candidates / "
        f"{report['coverage']['claim_assignments_found']} claim-type assignments "
        f"({report['coverage']['candidates_classified']} classified, "
        f"{report['coverage']['candidates_rejected']} rejected, "
        f"{report['coverage']['candidates_unclassified']} unclassified)"
    )

    if join_result.unclassified_ids:
        print(
            f"transport_claim_inventory: FAIL: "
            f"{len(join_result.unclassified_ids)} unclassified candidate(s):",
            file=sys.stderr,
        )
        for cand_id in join_result.unclassified_ids:
            print(f"  {cand_id}", file=sys.stderr)
    if join_result.orphan_ids:
        print(
            f"transport_claim_inventory: FAIL: "
            f"{len(join_result.orphan_ids)} orphaned classification(s) "
            "(candidate no longer exists):",
            file=sys.stderr,
        )
        for cand_id in join_result.orphan_ids:
            print(f"  {cand_id}", file=sys.stderr)

    return 0 if join_result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
