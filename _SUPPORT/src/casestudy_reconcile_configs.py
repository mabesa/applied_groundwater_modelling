"""
casestudy_reconcile_configs -- M1.3a: reconcile the two config YAMLs to the
canonical mapping (the FIRST step that EDITS the configs; M1.1/M1.2 only read).

Applies the M1.2 ``canonical_mapping`` + the M1.1 ``doublet_table`` to both
student config files so that, per group, the flow scenario and the transport
spill run on the SAME canonical doublet -- then records every concession /
coordinate / rate delta in a coherence ledger. NO model run.

What it rewrites (and ONLY this)
--------------------------------
* Flow ``case_config.yaml``: each ``scenarios.options[id=N].concession`` ->
  the canonical concession in INTEGER form (b010120 -> 120; G4 190 -> 120).
  Scenario ``type``/params are untouched. The flow model resolves its doublet
  FROM this concession (``case_utils.filter_wells_by_concession`` by GWR
  prefix), so this is not cosmetic -- but M1.3a only sets the IDENTITY; that
  the (M2a-rebuilt) builder pumps those wells is verified in M2a.
* Transport ``case_config_transport.yaml`` per group block N:
    - ``concession`` and ``doublet.concession_id`` -> canonical (b010xxx);
    - ``doublet.injection_easting/northing`` -> doublet_table ``inj_E/inj_N``;
    - ``doublet.extraction_easting/northing`` -> doublet_table ``ext_E/ext_N``
      (NOT swapped: injection<-Rueckgabe/inj_*, extraction<-Entnahme/ext_*);
    - ``doublet.pumping_rate_m3_d`` -> doublet_table ``Q_m3d`` (licensed max).
    - ``source.location`` (the relative E/N spill offset) is left
      **byte-unchanged** -- it auto-re-anchors to the new extraction well;
      whether it stays upgradient is an M4 question (flagged, not computed).
    - ``doublet.recirculation_fraction`` is now STALE (validated for the old
      doublet) but is a LINTED-ONLY field (``case_utils._lint_doublet``
      requires it numeric in [0,1]; no code uses it as physics -- grep-gated).
      It is therefore left untouched; its staleness is recorded in the ledger
      ONLY. No new config key is added (a stray sibling key could break a
      strict consumer). Actual removal is M3b.

Explicitly OUT of scope (do NOT touch): the model-family switch (M1.3b), the
``submodel:`` blocks / final recirc removal (M3b), and spill
upgradient/travel-distance validation (M4).

Also refreshes the stale MACHINE-AUTHORED docs that M1.3a's edits would
otherwise leave contradicting the live config (these are NOT student TODO
scaffolding, which is preserved verbatim): the transport header assignment
table (regenerated -> new canonical concession, contaminant unchanged,
Q=4320 for all, recirc marked stale/pending-M3b, coords/outcomes pending-M4)
and the per-group inline spill-placement comments (the OLD-doublet / OLD-Q
``y_max``/"just inside capture"/"stays below threshold" outcome claims are
replaced with neutral wording: the source is an E/N offset, and the
capture/upgradient/threshold outcome is NOT yet re-validated -> pending M4).

Method: in-place editing with a **round-trip YAML editor (ruamel.yaml)** for
the mapped scalar VALUES plus targeted comment-block rewriting for the stale
docs; student ``# TODO`` blocks, key order, and all non-target values are
preserved. NOTE (honest scope): the ruamel round-trip additionally normalises
trailing whitespace and may re-wrap ONE folded description scalar (the nitrate
block, whose source lines carry trailing spaces) onto a single line -- these
are byte-cosmetic normalisations that do NOT change any parsed value. The
guarantee is therefore **PARSED-equality of every non-target node** (asserted),
not byte-only-scalar changes. A ``--dry-run`` mode prints the unified diff and
writes nothing; a real run writes a pre-image ``.bak`` backup of each config
before mutating.

Outputs: the two rewritten configs + ``coherence_ledger.csv`` (extends M1.2's
``repairing_ledger`` with per-group coord/rate deltas + the absolute-spill
move M4 consumes). Deterministic.

Author: Applied Groundwater Modelling Course (transport track, M1.3a).
"""
from __future__ import annotations

import argparse
import difflib
import io
import re as _re
import shutil
from dataclasses import dataclass, field
from math import hypot
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from ruamel.yaml import YAML

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATE_DIR = _REPO_ROOT / "PROJECT" / "workspace" / "template"

DEFAULT_FLOW_CONFIG = _TEMPLATE_DIR / "case_config.yaml"
DEFAULT_TRANSPORT_CONFIG = _TEMPLATE_DIR / "case_config_transport.yaml"
DEFAULT_DOUBLET_TABLE = _TEMPLATE_DIR / "doublet_table.csv"
DEFAULT_CANONICAL_MAPPING = _TEMPLATE_DIR / "canonical_mapping.csv"
DEFAULT_LEDGER_CSV = _TEMPLATE_DIR / "coherence_ledger.csv"

N_GROUPS = 9

# LV95 / EPSG:2056 numeric envelope (metres) -- a coordinate outside this band
# is not LV95 (guards against a mixed-CRS write). Zurich/Limmat sits ~2.68e6 /
# 1.248e6; the band is generous but excludes LV03 (6-digit) and WGS84.
_LV95_E_RANGE = (2_400_000.0, 2_900_000.0)
_LV95_N_RANGE = (1_000_000.0, 1_400_000.0)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _mk_yaml() -> YAML:
    """A ruamel round-trip editor tuned to preserve THIS repo's config layout.

    * ``preserve_quotes`` keeps ``"b010205"`` quoted;
    * ``width`` huge so long folded (``>``) description/TODO blocks are not
      re-wrapped;
    * ``indent(mapping=2, sequence=4, offset=2)`` matches the existing
      ``    - id: 0`` block-sequence indentation;
    * None is rendered as the literal ``null`` (matches the source's
      ``half_life_days: null``).
    Together these make a pure round-trip a semantic + near-byte no-op, so the
    only real changes are the mapped scalars this module edits.
    """
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    y.representer.add_representer(
        type(None),
        lambda s, d: s.represent_scalar("tag:yaml.org,2002:null", "null"),
    )
    return y


def _concession_to_int(concession: str) -> int:
    """'b010120' -> 120 (the flow config's integer concession form)."""
    c = str(concession).strip().lower()
    if not c.startswith("b010"):
        raise ValueError(f"concession {concession!r} does not have the expected 'b010XXX' form.")
    return int(c[len("b010"):])


def _assert_lv95(e: float, n: float, tag: str) -> None:
    if not (_LV95_E_RANGE[0] <= e <= _LV95_E_RANGE[1] and _LV95_N_RANGE[0] <= n <= _LV95_N_RANGE[1]):
        raise ValueError(
            f"{tag}: coordinate ({e}, {n}) is outside the LV95/EPSG:2056 envelope "
            f"E{_LV95_E_RANGE} N{_LV95_N_RANGE} -- refusing to write a possibly non-LV95 coord.")


def _coord(v: Any) -> float:
    """Coordinate scalar: 0.1 m-rounded float (matches doublet_table precision)."""
    return round(float(v), 1)


def _rate(v: Any) -> Any:
    """Pumping-rate scalar: int when integral (keeps the config's int style),
    else float."""
    f = float(v)
    return int(f) if f == int(f) else f


def _dump_str(yaml: YAML, data: Any) -> str:
    buf = io.StringIO()
    yaml.dump(data, buf)
    return buf.getvalue()


def _unified_diff(old: str, new: str, path: Path) -> str:
    rel = str(path)
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=f"a/{rel}", tofile=f"b/{rel}"))


# ---------------------------------------------------------------------------
# stale-comment rewriting (machine-authored docs that now contradict the live
# config / pre-empt M4 -- NOT student TODO scaffolding, which is preserved)
# ---------------------------------------------------------------------------
# The transport header assignment table (regenerated from the canonical mapping).
_TR_HEADER_RE = _re.compile(
    r"# Fixed assignments by group number.*?"
    r"# NOTE: final coordinates STILL NEED[^\n]*\n",
    _re.DOTALL,
)
_TR_GROUP_LINE_RE = _re.compile(
    r"# Group (?P<gid>\d+): concession \S+ - (?P<namedesc>.*?) - Q=[^\n]*")

# Inline spill-placement comments (OLD-doublet, OLD-Q capture/outcome claims).
_TR_LOCATION_BLOCK_RE = _re.compile(
    r"(?P<head>^        location:\n)(?P<comments>(?:^ {10}#.*\n)+)", _re.MULTILINE)
_NEUTRAL_LOCATION_COMMENT = (
    "          # Source position is an easting/northing OFFSET relative to the\n"
    "          # extraction well (unchanged by the M1.3a doublet swap). After the\n"
    "          # swap the capture / upgradient / threshold outcome is NOT yet\n"
    "          # re-validated -- pending M4 (coherence_ledger.csv: upgradient_unverified=True).\n"
)


def _rewrite_transport_comments(text: str, canonical: Dict[int, str],
                                dt_by_conc: Dict[str, Any]) -> str:
    """Regenerate the stale transport header table + neutralise the OLD-doublet
    inline spill-outcome comments. Comment-only edits -- never touches a value."""
    # --- header assignment table ---
    m = _TR_HEADER_RE.search(text)
    if m:
        # preserve each group's contaminant + scenario-description text (unchanged
        # by M1.3a); only the concession + Q are restated.
        namedesc = {int(gm.group("gid")): gm.group("namedesc").rstrip()
                    for gm in _TR_GROUP_LINE_RE.finditer(m.group(0))}
        lines = [
            "# Fixed assignments by group number (each group gets ONE canonical REAL",
            "# geothermal-doublet concession; injection + extraction wells both active,",
            '# extraction well = compliance/monitoring "Well"):',
            "# CANONICAL assignment (M1.3a): concession + doublet coords come from the",
            "# M1.1 doublet_table; the contaminant is unchanged from the original",
            "# scenario; Q = licensed max (4320 m3/d) for ALL groups.",
        ]
        for gid in range(N_GROUPS):
            conc = canonical[gid]
            q = dt_by_conc[conc].Q_m3d
            q_str = f"{int(q)}" if float(q) == int(q) else f"{q}"
            nd = namedesc.get(gid, "")
            lines.append(f"# Group {gid}: concession {conc} - {nd} - Q={q_str} m3/d")
        lines += [
            "#",
            "# recirculation_fraction values below are STALE (validated for the OLD",
            "# doublet); they are linted-only (no physics consumer) and pending removal",
            "# / re-derivation in M3b -- see coherence_ledger.csv (recirc_stale=True).",
            "# Doublet coords + capture/upgradient/threshold outcomes are NOT yet",
            "# re-validated for the swapped doublets -- pending M4",
            "# (coherence_ledger.csv: upgradient_unverified=True).",
        ]
        text = text[:m.start()] + "\n".join(lines) + "\n" + text[m.end():]

    # --- inline spill-placement comments (all 9 source.location blocks) ---
    text = _TR_LOCATION_BLOCK_RE.sub(
        lambda mo: mo.group("head") + _NEUTRAL_LOCATION_COMMENT, text)

    # --- drop the now-stale "(upgradient)" claim from the offset inline comments ---
    text = text.replace("offset from extraction well (upgradient)",
                        "offset from extraction well")
    return text


def _rewrite_flow_comments(text: str, canonical: Dict[int, str]) -> str:
    """Update the flow header's stale per-group concession comments (only G4's
    ``190`` is stale). Comment-only."""
    for gid in range(N_GROUPS):
        canon_int = _concession_to_int(canonical[gid])
        # match "# Group N: concession <int>, scenario ..." and restate the int
        text = _re.sub(
            rf"(# Group {gid}: concession )\d+(, scenario)",
            rf"\g<1>{canon_int}\g<2>", text)
    return text


def _assert_written_matches_sources(flow_text: str, tr_text: str,
                                    canonical: Dict[int, str],
                                    dt_by_conc: Dict[str, Any]) -> None:
    """Parse the FINAL written text and assert every group's flow int,
    transport concession/concession_id, doublet inj/ext coords, and pumping
    rate equal canonical_mapping + doublet_table. On-disk source-of-truth
    check (post comment-rewrite, so comment surgery can't have corrupted a
    value)."""
    import yaml as _pyyaml  # plain loader: validates the emitted YAML parses

    flow = _pyyaml.safe_load(flow_text)
    tr = _pyyaml.safe_load(tr_text)
    flow_by = {int(o["id"]): o for o in flow["scenarios"]["options"]}
    tr_by = {int(o["id"]): o for o in tr["transport_scenarios"]["options"]}
    for gid in range(N_GROUPS):
        conc = canonical[gid]
        row = dt_by_conc[conc]
        if int(flow_by[gid]["concession"]) != _concession_to_int(conc):
            raise ValueError(f"written flow[{gid}].concession != canonical {conc}.")
        opt = tr_by[gid]
        if opt["concession"] != conc or opt["doublet"]["concession_id"] != conc:
            raise ValueError(f"written transport[{gid}] concession/concession_id != {conc}.")
        d = opt["doublet"]
        for key, exp in (("injection_easting", _coord(row.inj_E)),
                         ("injection_northing", _coord(row.inj_N)),
                         ("extraction_easting", _coord(row.ext_E)),
                         ("extraction_northing", _coord(row.ext_N))):
            if float(d[key]) != float(exp):
                raise ValueError(f"written transport[{gid}].doublet.{key} {d[key]} != {exp}.")
        if float(d["pumping_rate_m3_d"]) != float(row.Q_m3d):
            raise ValueError(
                f"written transport[{gid}].doublet.pumping_rate_m3_d {d['pumping_rate_m3_d']} "
                f"!= doublet_table Q {row.Q_m3d}.")


# ---------------------------------------------------------------------------
# result container
# ---------------------------------------------------------------------------
@dataclass
class ReconcileResult:
    ledger: pd.DataFrame
    flow_diff: str
    transport_diff: str
    flow_new_text: str
    transport_new_text: str
    wrote: bool
    dry_run: bool
    backups: Dict[str, Optional[str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def reconcile_configs(flow_config: Optional[Path] = None,
                      transport_config: Optional[Path] = None,
                      doublet_table: Optional[Path] = None,
                      canonical_mapping: Optional[Path] = None,
                      ledger_csv: Optional[Path] = None,
                      dry_run: bool = False,
                      backup: bool = True,
                      backup_suffix: str = ".bak",
                      verbose: bool = False) -> ReconcileResult:
    """Reconcile both configs to the canonical mapping + doublet_table.

    Parameters
    ----------
    flow_config, transport_config, doublet_table, canonical_mapping, ledger_csv : Path, optional
        Override the input/output locations (default: PROJECT/workspace/template/...).
    dry_run : bool
        If True, compute the edits + ledger and print the unified diffs, but
        write NOTHING (no configs, no backups, no ledger). The review gate.
    backup : bool
        If True (and not dry_run), write a pre-image ``<config><backup_suffix>``
        of each config before the in-place rewrite.
    backup_suffix : str
        Suffix for the pre-image backup (default ``.bak``).
    verbose : bool
        Print the diffs to stdout (always on in dry_run).

    Returns
    -------
    ReconcileResult
        ``.ledger`` (9 rows), the two unified diffs, the rewritten text, and
        the backup paths (if written).
    """
    flow_path = Path(flow_config or DEFAULT_FLOW_CONFIG)
    tr_path = Path(transport_config or DEFAULT_TRANSPORT_CONFIG)
    dt_path = Path(doublet_table or DEFAULT_DOUBLET_TABLE)
    cm_path = Path(canonical_mapping or DEFAULT_CANONICAL_MAPPING)
    ledger_path = Path(ledger_csv or DEFAULT_LEDGER_CSV)

    # --- canonical target (group -> concession) + doublet geometry/Q ---
    cm = pd.read_csv(cm_path)
    dt = pd.read_csv(dt_path)

    # Duplicate-key guard (belt-and-suspenders vs a corrupted input): a dict
    # comprehension would silently last-wins on duplicate rows, so reject them.
    if cm["group"].duplicated().any():
        dup = sorted(cm.loc[cm["group"].duplicated(keep=False), "group"].unique().tolist())
        raise ValueError(f"canonical_mapping has duplicate group rows: {dup}.")
    if dt["concession"].duplicated().any():
        dup = sorted(dt.loc[dt["concession"].duplicated(keep=False), "concession"].unique().tolist())
        raise ValueError(f"doublet_table has duplicate concession rows: {dup}.")
    if dt["group"].duplicated().any():
        dup = sorted(dt.loc[dt["group"].duplicated(keep=False), "group"].unique().tolist())
        raise ValueError(f"doublet_table has duplicate group rows: {dup}.")

    canonical = {int(r.group): str(r.concession) for r in cm.itertuples()}
    if set(canonical) != set(range(N_GROUPS)):
        raise ValueError(f"canonical_mapping groups {sorted(canonical)} != {{0..{N_GROUPS - 1}}}.")

    # doublet_table keyed by concession -> row (coords + Q + crs)
    if not (dt["crs"] == "EPSG:2056").all():
        raise ValueError("doublet_table has a non-EPSG:2056 crs -- refusing to write mixed CRS.")
    dt_by_conc = {str(r.concession): r for r in dt.itertuples()}

    flow_old_text = flow_path.read_text()
    tr_old_text = tr_path.read_text()

    # ---------------- edit FLOW config ----------------
    yaml_flow = _mk_yaml()
    flow_doc = yaml_flow.load(flow_old_text)
    flow_opts = flow_doc.get("scenarios", {}).get("options", [])
    flow_ids = [o.get("id") for o in flow_opts]
    if sorted(flow_ids) != list(range(N_GROUPS)):
        raise ValueError(f"flow scenarios ids {sorted(flow_ids)} != {{0..{N_GROUPS - 1}}} "
                         "(missing/duplicate id).")
    for opt in flow_opts:
        gid = int(opt["id"])
        opt["concession"] = _concession_to_int(canonical[gid])
    flow_new_text = _dump_str(yaml_flow, flow_doc)
    flow_new_text = _rewrite_flow_comments(flow_new_text, canonical)

    # ---------------- edit TRANSPORT config + build ledger ----------------
    yaml_tr = _mk_yaml()
    tr_doc = yaml_tr.load(tr_old_text)
    tr_opts = tr_doc.get("transport_scenarios", {}).get("options", [])
    tr_ids = [o.get("id") for o in tr_opts]
    if sorted(tr_ids) != list(range(N_GROUPS)):
        raise ValueError(f"transport ids {sorted(tr_ids)} != {{0..{N_GROUPS - 1}}}.")

    ledger_rows: List[Dict[str, Any]] = []
    for opt in tr_opts:
        gid = int(opt["id"])
        new_conc = canonical[gid]
        if new_conc not in dt_by_conc:
            raise ValueError(f"group {gid}: canonical concession {new_conc} not in doublet_table.")
        row = dt_by_conc[new_conc]

        doublet = opt["doublet"]
        old_conc = str(opt["concession"])
        old_inj_E, old_inj_N = float(doublet["injection_easting"]), float(doublet["injection_northing"])
        old_ext_E, old_ext_N = float(doublet["extraction_easting"]), float(doublet["extraction_northing"])
        old_Q = float(doublet["pumping_rate_m3_d"])
        recirc_old = float(doublet["recirculation_fraction"])

        # relative spill offset (byte-unchanged) -> absolute spill = ext + offset
        loc = opt["source"]["location"]
        off_E, off_N = float(loc["easting"]), float(loc["northing"])

        # new canonical geometry / rate
        new_inj_E, new_inj_N = _coord(row.inj_E), _coord(row.inj_N)
        new_ext_E, new_ext_N = _coord(row.ext_E), _coord(row.ext_N)
        new_Q = float(row.Q_m3d)

        # CRS guard: BOTH old and new coords must be LV95 before writing.
        _assert_lv95(old_inj_E, old_inj_N, f"group {gid} old injection")
        _assert_lv95(old_ext_E, old_ext_N, f"group {gid} old extraction")
        _assert_lv95(new_inj_E, new_inj_N, f"group {gid} new injection")
        _assert_lv95(new_ext_E, new_ext_N, f"group {gid} new extraction")

        # --- apply the edits (NOT swapping inj/ext; recirc + source untouched) ---
        opt["concession"] = new_conc
        doublet["concession_id"] = new_conc
        doublet["injection_easting"] = _coord(new_inj_E)
        doublet["injection_northing"] = _coord(new_inj_N)
        doublet["extraction_easting"] = _coord(new_ext_E)
        doublet["extraction_northing"] = _coord(new_ext_N)
        doublet["pumping_rate_m3_d"] = _rate(new_Q)

        # --- ledger row ---
        inj_move = hypot(new_inj_E - old_inj_E, new_inj_N - old_inj_N)
        ext_move = hypot(new_ext_E - old_ext_E, new_ext_N - old_ext_N)
        old_abs_E, old_abs_N = old_ext_E + off_E, old_ext_N + off_N
        new_abs_E, new_abs_N = new_ext_E + off_E, new_ext_N + off_N
        source_abs_move = hypot(new_abs_E - old_abs_E, new_abs_N - old_abs_N)
        ledger_rows.append(dict(
            group=gid,
            old_concession=old_conc,
            new_concession=new_conc,
            old_inj_E=old_inj_E, old_inj_N=old_inj_N,
            old_ext_E=old_ext_E, old_ext_N=old_ext_N,
            new_inj_E=new_inj_E, new_inj_N=new_inj_N,
            new_ext_E=new_ext_E, new_ext_N=new_ext_N,
            inj_move_m=round(inj_move, 3),
            ext_move_m=round(ext_move, 3),
            old_Q=old_Q, new_Q=new_Q,
            recirc_old=recirc_old,
            recirc_stale=True,
            source_offset_easting=off_E, source_offset_northing=off_N,
            source_offset_unchanged=True,
            old_source_abs_E=round(old_abs_E, 1), old_source_abs_N=round(old_abs_N, 1),
            new_source_abs_E=round(new_abs_E, 1), new_source_abs_N=round(new_abs_N, 1),
            source_abs_move_m=round(source_abs_move, 3),
            upgradient_unverified=True,
        ))

    tr_new_text = _dump_str(yaml_tr, tr_doc)
    tr_new_text = _rewrite_transport_comments(tr_new_text, canonical, dt_by_conc)

    ledger_columns = [
        "group", "old_concession", "new_concession",
        "old_inj_E", "old_inj_N", "old_ext_E", "old_ext_N",
        "new_inj_E", "new_inj_N", "new_ext_E", "new_ext_N",
        "inj_move_m", "ext_move_m", "old_Q", "new_Q",
        "recirc_old", "recirc_stale",
        "source_offset_easting", "source_offset_northing", "source_offset_unchanged",
        "old_source_abs_E", "old_source_abs_N", "new_source_abs_E", "new_source_abs_N",
        "source_abs_move_m", "upgradient_unverified",
    ]
    ledger = pd.DataFrame(ledger_rows, columns=ledger_columns)

    # --- invariant: source moves EXACTLY with the extraction well (offset fixed)
    for r in ledger.itertuples():
        if round(r.source_abs_move_m, 3) != round(r.ext_move_m, 3):
            raise ValueError(
                f"group {r.group}: source_abs_move_m ({r.source_abs_move_m}) != "
                f"ext_move_m ({r.ext_move_m}) -- offset should be byte-unchanged.")

    # --- post-rewrite ON-DISK invariant: re-parse the FINAL text (not the
    #     in-memory pre-write objects) and assert every group's written flow
    #     int, transport b010xxx, doublet inj/ext coords, and pumping rate match
    #     canonical_mapping + doublet_table exactly. Proves the bytes we are
    #     about to write ARE the source of truth. ---
    _assert_written_matches_sources(flow_new_text, tr_new_text, canonical, dt_by_conc)

    flow_diff = _unified_diff(flow_old_text, flow_new_text, flow_path)
    tr_diff = _unified_diff(tr_old_text, tr_new_text, tr_path)

    if verbose or dry_run:
        print(f"# ---- DRY-RUN diff: {flow_path} ----" if dry_run else f"# diff: {flow_path}")
        print(flow_diff or "(no change)")
        print(f"# ---- DRY-RUN diff: {tr_path} ----" if dry_run else f"# diff: {tr_path}")
        print(tr_diff or "(no change)")

    backups: Dict[str, Optional[str]] = {"flow": None, "transport": None}
    wrote = False
    if not dry_run:
        if backup:
            flow_bak = flow_path.with_name(flow_path.name + backup_suffix)
            tr_bak = tr_path.with_name(tr_path.name + backup_suffix)
            shutil.copy2(flow_path, flow_bak)   # pre-image (byte copy of the ORIGINAL)
            shutil.copy2(tr_path, tr_bak)
            backups = {"flow": str(flow_bak), "transport": str(tr_bak)}
        flow_path.write_text(flow_new_text)
        tr_path.write_text(tr_new_text)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger.to_csv(ledger_path, index=False, lineterminator="\n", float_format="%.12g")
        wrote = True

    return ReconcileResult(
        ledger=ledger, flow_diff=flow_diff, transport_diff=tr_diff,
        flow_new_text=flow_new_text, transport_new_text=tr_new_text,
        wrote=wrote, dry_run=dry_run, backups=backups)


# ===========================================================================
# M1.3b: switch the FLOW config model: block from legacy MODFLOW-NWT -> MF6 05f
# ===========================================================================
# Shared model fields the flow block must mirror from the transport MF6 block.
_MF6_SHARED_FIELDS = ("workspace", "sim_namefile", "sim_name", "baseline_model_name")

# The flow `model:` block = the `model:` line + all following indented lines
# (keys + indented comments), up to the first non-indented line (blank / next
# top-level key). A single string-block replacement keeps every OTHER byte of
# the file identical (no whole-file ruamel round-trip -> no reflow/WS churn).
_FLOW_MODEL_BLOCK_RE = _re.compile(r"(?m)^model:\n(?:[ \t].*\n)*")


@dataclass
class ModelSwitchResult:
    flow_diff: str
    flow_new_text: str
    transport_model: Dict[str, Any]
    wrote: bool
    dry_run: bool
    backup: Optional[str] = None


def _compose_flow_model_block(tmodel: Dict[str, Any]) -> str:
    """Compose the new flow `model:` block from the transport config's PARSED
    MF6 model block (values sourced from transport, not hardcoded), with fresh
    comments that no longer contradict the MF6 reference."""
    data_name = tmodel["data_name"]
    workspace = tmodel["workspace"]
    sim_namefile = tmodel["sim_namefile"]
    sim_name = tmodel["sim_name"]
    baseline = tmodel["baseline_model_name"]
    lines = [
        "model:",
        "  # Calibrated MF6 05f flow model -- the SAME simulation the transport",
        "  # config (case_config_transport.yaml) references; bootstrapped via",
        "  # model_io_utils.ensure_flow_model(). Switched to MF6 05f from the",
        "  # legacy structured-grid flow model in M1.3b (config-only). The MF6",
        "  # flow builder that consumes this block is built in M2a; sim_name IS",
        "  # the GWF model name inside the simulation (no separate name field).",
        f"  data_name: {data_name}               # Calibrated MF6 GWF model (05f)",
        f'  workspace: "{workspace}"  # 05f-calibrated model',
        f'  sim_namefile: "{sim_namefile}"               # MF6 simulation name file',
        f'  sim_name: "{sim_name}"               # MF6 GWF model name inside the simulation',
        f'  baseline_model_name: "{baseline}"',
    ]
    return "\n".join(lines) + "\n"


def switch_flow_model_to_mf6(flow_config: Optional[Path] = None,
                             transport_config: Optional[Path] = None,
                             dry_run: bool = False,
                             backup: bool = True,
                             backup_suffix: str = ".m13b.bak",
                             verbose: bool = False) -> ModelSwitchResult:
    """M1.3b: rewrite the flow config's ``model:`` block to reference the same
    calibrated MF6 05f model as the transport config.

    Config-only, no model run. Uses the transport config's PARSED ``model:``
    block as the target (not hardcoded strings). Drops the NWT-only
    ``namefile`` key + the ``limmat_valley_model_nwt`` values + the
    ``baseline_model`` workspace, and refreshes the block's comments so nothing
    contradicts the MF6 reference. Only the ``model:`` block changes; every
    other byte of the flow config is preserved. The transport config is NOT
    touched.

    Backup suffix defaults to ``.m13b.bak`` (a step-distinct pre-image) so it
    does NOT clobber M1.3a's ``.bak``.

    Parameters mirror ``reconcile_configs`` (dry_run / backup / verbose).
    """
    flow_path = Path(flow_config or DEFAULT_FLOW_CONFIG)
    tr_path = Path(transport_config or DEFAULT_TRANSPORT_CONFIG)

    import yaml as _pyyaml

    flow_old_text = flow_path.read_text()
    tmodel = (_pyyaml.safe_load(tr_path.read_text()) or {}).get("model", {})
    missing = [k for k in ("data_name",) + _MF6_SHARED_FIELDS if k not in tmodel]
    if missing:
        raise ValueError(f"transport config model: block missing MF6 field(s) {missing}.")

    new_block = _compose_flow_model_block(tmodel)
    m = _FLOW_MODEL_BLOCK_RE.search(flow_old_text)
    if m is None:
        raise ValueError(f"flow config {flow_path}: no top-level 'model:' block found.")
    flow_new_text = flow_old_text[:m.start()] + new_block + flow_old_text[m.end():]

    # --- validate the emitted flow config (parses, MF6-only, no mixed schema) ---
    _assert_flow_model_is_mf6(flow_new_text, tmodel)

    flow_diff = _unified_diff(flow_old_text, flow_new_text, flow_path)
    if verbose or dry_run:
        print(f"# ---- DRY-RUN diff: {flow_path} ----" if dry_run else f"# diff: {flow_path}")
        print(flow_diff or "(no change)")

    backup_path: Optional[str] = None
    wrote = False
    if not dry_run:
        if backup:
            bak = flow_path.with_name(flow_path.name + backup_suffix)
            shutil.copy2(flow_path, bak)  # pre-M1.3b image
            backup_path = str(bak)
        flow_path.write_text(flow_new_text)
        wrote = True

    return ModelSwitchResult(
        flow_diff=flow_diff, flow_new_text=flow_new_text, transport_model=dict(tmodel),
        wrote=wrote, dry_run=dry_run, backup=backup_path)


def _assert_flow_model_is_mf6(flow_text: str, tmodel: Dict[str, Any]) -> None:
    """Acceptance: the flow model: block references ONLY MF6 05f, matches the
    transport MF6 block (parsed), and the whole file is NWT-clean."""
    import yaml as _pyyaml

    doc = _pyyaml.safe_load(flow_text)
    model = (doc or {}).get("model", {})

    # MF6 keys present; no mixed schema (namefile absent).
    if "namefile" in model:
        raise ValueError("flow model: still has the legacy 'namefile' key (mixed schema).")
    if "sim_namefile" not in model:
        raise ValueError("flow model: missing 'sim_namefile' (MF6).")
    if model.get("data_name") != "flow_model_mf6":
        raise ValueError(f"flow model.data_name is {model.get('data_name')!r}, expected 'flow_model_mf6'.")

    # PARSED comparison vs the transport MF6 block (shared fields).
    for k in _MF6_SHARED_FIELDS:
        if model.get(k) != tmodel.get(k):
            raise ValueError(
                f"flow model.{k}={model.get(k)!r} != transport model.{k}={tmodel.get(k)!r}.")

    # workspace is the 05f calibration path, not the old baseline_model path.
    if "/limmat/baseline_model" in str(model.get("workspace", "")):
        raise ValueError("flow model.workspace still points at the old '/limmat/baseline_model'.")

    # Whole-file NWT gate (case-insensitive). `.nam` alone is fine (mfsim.nam);
    # gate the LEGACY namefile + nwt tokens + the old workspace PATH fragment
    # (NOT the surviving 'baseline_model_name' KEY).
    low = flow_text.lower()
    for token in ("nwt", "modflow-nwt", "limmat_valley_model_nwt", "limmat_valley_model_nwt.nam"):
        if token in low:
            raise ValueError(f"flow config still contains stale NWT token {token!r}.")
    if "/limmat/baseline_model" in flow_text:
        raise ValueError("flow config still contains the old '/limmat/baseline_model' workspace path.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(
        description="Config-mutation steps for the student case study (M1.3a/M1.3b).")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the unified diff(s) and write nothing (review gate).")
    ap.add_argument("--no-backup", action="store_true",
                    help="do not write a pre-image .bak backup (NOT recommended).")
    ap.add_argument("--switch-model", action="store_true",
                    help="M1.3b: switch the flow config model: block to the MF6 05f model "
                         "(instead of the default M1.3a concession/doublet reconcile).")
    args = ap.parse_args(argv)

    if args.switch_model:
        res = switch_flow_model_to_mf6(dry_run=args.dry_run, backup=not args.no_backup, verbose=True)
        if not args.dry_run:
            print(f"\nwrote flow model: block (MF6 05f); backup: {res.backup}")
        return

    result = reconcile_configs(dry_run=args.dry_run, backup=not args.no_backup, verbose=True)
    if not args.dry_run:
        print("\n# ---- coherence_ledger (per-group deltas) ----")
        with pd.option_context("display.max_columns", None, "display.width", 240):
            print(result.ledger[["group", "old_concession", "new_concession",
                                  "inj_move_m", "ext_move_m", "old_Q", "new_Q",
                                  "source_abs_move_m"]].to_string(index=False))
        print(f"\nbackups: {result.backups}")


if __name__ == "__main__":
    _main()
