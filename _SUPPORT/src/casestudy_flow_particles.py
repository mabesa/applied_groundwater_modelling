#!/usr/bin/env python
"""
================================================================================
 M2b.2 -- case-study FLOW advective particle-tracking (PRT capture zones) -- v5
================================================================================

Advective MODFLOW-6 PRT particle tracking on the FAITHFUL, already-solved flow
field -- i.e. a ``state_result`` dict as returned by
``casestudy_flow_builder.build_flow_state`` / ``build_all_flow_states`` (keys
used here: ``gwf``, ``heads``, ``spec``, ``headfile``, ``budgetfile``,
``grid_hash``, ``group``, ``workspace``, and for the wells-family states
``doublet`` = ``{"injection": {"cell", "E", "N"}, "extraction": {...}}``).

This module REUSES the DISV PRT package-wiring PATTERN from
``transport_prt_capture`` (Prt/Prtdisv/Prtmip/Prtprp/Prtoc/Prtfmi) and the
track-CSV -> world-coordinate conversion in
``model_io_utils.load_prt_results`` (``modelgrid.get_coords``). It does NOT
import or call that module's internal PRT-runner / capture-assembly / half-
width-measurement helpers (private-underscore and public entry points alike)
-- those are coupled to the SHIPPED DEMO's OWN GWF build (hardcoded
``gwf.hds``/``gwf.cbc``, locked parameters, a GWF whose TDIS length ==
track_days, spill/axis analytics), which carries the ~36% RIV
transfer-conductance defect on the refined grid
([[riv-transfer-defect-followup]]). M2b PRT MUST run on the case study's own
faithful, already-solved GWF field instead -- a static test in this repo's
test suite asserts this module's source never mentions those three symbol
names.

--------------------------------------------------------------------------------
CLAIM BOUNDARY (advective-only): "capture" here means ADVECTIVE connection or
timing under the STEADY solved flow field and a chosen POROSITY -- i.e. where a
neutral tracer parcel's centerline would travel, and how long it takes. It is
NOT a concentration, exceedance, or safety statement: it says nothing about
dispersion across streamtubes, sorption, decay, or anything outside the traced
streamline envelope. The REACTIVE transport layer (dispersion/sorption/decay,
the ADE) is M3 -- see the 08t PRT-vs-ADE claim boundary. Read the scatter of
pathlines/end-cells, not a single derived scalar, when honesty matters: a
release-disc fraction is a property of the RELEASE DISC (its radius, its count
of dropped/off-grid points), not an intrinsic property of the doublet.
--------------------------------------------------------------------------------

Key MF6-PRT mechanics wired here (Codex-verified against MF6 docs):

* Steady 1-period field -> ``extend_tracking=True`` + ``stoptraveltime`` (NOT
  matching TDIS length to track_days -- the case-study GWF is ONE steady ~1-day
  period; without ``extend_tracking`` particles freeze at the period end).
* FMI preflight (hard): before building PRT, the GWF's CBC must carry
  ``FLOW-JA-FACE`` + ``DATA-SPDIS`` + ``DATA-SAT`` (saturation). PRT/FMI needs
  saturation; the M2a transport-budget assert only checks the first two.
* Backward tracking has NO flag: it is ``flopy.utils.HeadFile(...).reverse()``
  + ``flopy.utils.CellBudgetFile(...).reverse()`` written into an isolated
  ``_prt/backward/`` workspace, then PRT's FMI package points at the REVERSED
  files. Forward tracking points FMI at the state's own head/budget files.
* Strict in-cell release: every release point must lie inside its containing
  cell (``VertexGrid.intersect``, STRICT -- never nearest-centroid). Points
  with no containing cell are DROPPED and counted (``n_dropped``).
* Isolated workspace: ``<work_dir>/_prt/<mode>/`` -- the state's own GWF
  head/budget files are never touched (a REVERSED COPY is written for
  backward, the originals are read-only for forward).

`uv run` for everything (see CLAUDE.md).
================================================================================
"""
from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# sys.path wiring so this module imports the same way notebooks/pytest do.
_SRC_DIR = str(Path(__file__).resolve().parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import flopy  # noqa: E402

import casestudy_flow_common as cfc  # noqa: E402
import model_io_utils as mio  # noqa: E402

StateResult = Dict[str, Any]

# PRT track-CSV `ireason` codes (MF6 6.7.0, per transport_prt_capture.py):
# 0 = release, 1 = cell exit, 2 = time-step end, 3 = TERMINATION, 4 = weak
# sink, 5 = user-specified time. We key the terminal/end-cell record on
# ireason == 3 when present.
_IREASON_TERMINATE = 3

# The PRT/FMI preflight: the GWF budget file must carry these CellBudgetFile
# record names. DATA-SAT (saturation) is the one M2a's own transport-budget
# assert does NOT check (casestudy_flow_common ~L457's save_saturation output).
_REQUIRED_BUDGET_RECORDS = ("FLOW-JA-FACE", "DATA-SPDIS", "DATA-SAT")

# Default porosity source: the transport config's per-group
# transport_scenarios.options[id=<group>].transport.porosity (0.20 for group 0).
_DEFAULT_TRANSPORT_CONFIG = (
    Path(__file__).resolve().parents[2]
    / "PROJECT" / "workspace" / "template" / "case_config_transport.yaml"
)

# A release-disc radius wide enough to sample a handful of neighboring
# refined cells around the well (corridor cells are ~10 m), not so wide it
# leaves the corridor. Mirrors the "realistic spill footprint" default radius
# used elsewhere in this repo's PRT tooling.
_DEFAULT_RELEASE_RADIUS_M = 10.0


# =============================================================================
# Porosity: provenance + validation.
# =============================================================================
def resolve_porosity(
    state_result: StateResult,
    porosity: Optional[float] = None,
    *,
    config_path: Optional[Path] = None,
) -> Tuple[float, Dict[str, Any]]:
    """Resolve the PRT porosity value + a provenance record.

    If *porosity* is given (not ``None``), it is used AS-IS
    (``source='argument'``). Otherwise the value is read from the transport
    config's per-group ``transport_scenarios.options[id=<group>].transport.
    porosity`` (``source='config'``), keyed by ``state_result['group']``.

    Always validates ``0 < porosity < 1`` (not merely finite) -- porosity is a
    fraction, and a value outside that range is a unit/typo bug, not a
    legitimate PRT input.

    Returns ``(value, provenance)`` where ``provenance`` is
    ``{value, source, file, key, group, config_hash}`` (``file``/``key``/
    ``config_hash`` are ``None`` for ``source='argument'``).
    """
    if porosity is not None:
        value = float(porosity)
        provenance: Dict[str, Any] = {
            "value": value,
            "source": "argument",
            "file": None,
            "key": None,
            "group": state_result.get("group"),
            "config_hash": None,
        }
    else:
        cfg_path = Path(config_path) if config_path is not None else _DEFAULT_TRANSPORT_CONFIG
        if not cfg_path.exists():
            raise FileNotFoundError(
                f"transport config not found for default porosity lookup: {cfg_path}"
            )
        raw = cfg_path.read_bytes()
        config_hash = hashlib.sha256(raw).hexdigest()
        cfg = yaml.safe_load(raw) or {}
        group = state_result.get("group")
        options = ((cfg.get("transport_scenarios") or {}).get("options")) or []
        match = next((o for o in options if o.get("id") == group), None)
        if match is None:
            raise KeyError(
                f"no transport_scenarios.options entry with id == group {group!r} "
                f"in {cfg_path}"
            )
        transport = match.get("transport") or {}
        if "porosity" not in transport:
            raise KeyError(
                f"transport_scenarios.options[id={group}].transport.porosity "
                f"missing in {cfg_path}"
            )
        value = float(transport["porosity"])
        provenance = {
            "value": value,
            "source": "config",
            "file": str(cfg_path),
            "key": f"transport_scenarios.options[id={group}].transport.porosity",
            "group": group,
            "config_hash": config_hash,
        }

    if not math.isfinite(value):
        raise ValueError(f"porosity must be finite, got {value!r}")
    if not (0.0 < value < 1.0):
        raise ValueError(f"porosity must satisfy 0 < porosity < 1, got {value!r}")
    return value, provenance


# =============================================================================
# DATA-SAT / FMI preflight (hard).
# =============================================================================
def assert_data_sat_available(budgetfile: Any) -> None:
    """Preflight (hard, raises): PRT/FMI needs the GWF budget file to carry
    ``FLOW-JA-FACE`` + ``DATA-SPDIS`` + ``DATA-SAT`` (saturation), and each
    must be NON-EMPTY at the (single steady) time -- a present-but-empty
    record would silently starve PRT/FMI. Raises :class:`ValueError` naming
    the missing OR empty record(s).

    References ``flopy.utils.CellBudgetFile`` via the module attribute (not a
    bound local import) so tests can monkeypatch it without touching disk.
    """
    cbf = flopy.utils.CellBudgetFile(str(budgetfile))
    raw_names = cbf.get_unique_record_names()
    names = set()
    for n in raw_names:
        names.add(n.decode().strip() if isinstance(n, bytes) else str(n).strip())
    missing = [r for r in _REQUIRED_BUDGET_RECORDS if r not in names]
    if missing:
        raise ValueError(
            f"PRT DATA-SAT preflight failed for {budgetfile}: missing required "
            f"CellBudgetFile record(s) {missing} (PRT/FMI needs FLOW-JA-FACE + "
            "DATA-SPDIS + DATA-SAT; DATA-SAT requires NPF save_saturation=True "
            f"on the solved GWF). Found: {sorted(names)}"
        )
    # Presence is necessary but not sufficient -- a record whose payload is
    # empty at the steady time would starve PRT/FMI just as badly as a missing
    # one. Assert each required record actually carries data.
    empty = []
    for record in _REQUIRED_BUDGET_RECORDS:
        try:
            data = cbf.get_data(text=record)
        except Exception as exc:  # pragma: no cover -- defensive
            raise ValueError(
                f"PRT DATA-SAT preflight failed for {budgetfile}: could not read "
                f"record {record!r} ({exc})"
            )
        if not data or all(np.asarray(d).size == 0 for d in data):
            empty.append(record)
    if empty:
        raise ValueError(
            f"PRT DATA-SAT preflight failed for {budgetfile}: required "
            f"CellBudgetFile record(s) {empty} are present but EMPTY at the steady "
            "time (PRT/FMI needs non-empty FLOW-JA-FACE + DATA-SPDIS + DATA-SAT "
            "arrays)."
        )


# =============================================================================
# Strict in-cell golden-angle release disc (never nearest-centroid).
# =============================================================================
def _golden_angle_disc_points(
    center_x: float, center_y: float, n: int, radius_m: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """A "sunflower" golden-angle disc of *n* candidate points, area-uniform
    over a disc of radius *radius_m* centered at (*center_x*, *center_y*)."""
    golden_angle = np.pi * (3.0 - np.sqrt(5.0))
    idx = np.arange(n, dtype=float)
    r = radius_m * np.sqrt((idx + 0.5) / n)
    theta = idx * golden_angle
    x = center_x + r * np.cos(theta)
    y = center_y + r * np.sin(theta)
    return x, y


def _strict_release_points(
    modelgrid, center_x: float, center_y: float, n_particles: int, radius_m: float,
) -> Tuple[List[Tuple[float, float, int]], int]:
    """Golden-angle disc of candidate release points; STRICT in-cell
    membership via ``modelgrid.intersect`` (VertexGrid). Points with no unique
    containing cell (off-grid, or degenerate) are DROPPED and counted --
    never assigned to a nearest centroid.

    Returns ``(points, n_dropped)`` where each point is ``(x, y, cell0based)``.
    """
    xs, ys = _golden_angle_disc_points(center_x, center_y, n_particles, radius_m)
    points: List[Tuple[float, float, int]] = []
    n_dropped = 0
    for x, y in zip(xs, ys):
        try:
            cell = modelgrid.intersect(float(x), float(y), forgive=True)
        except Exception:
            cell = float("nan")
        if cell is None or (isinstance(cell, float) and math.isnan(cell)):
            n_dropped += 1
            continue
        points.append((float(x), float(y), int(cell)))
    return points, n_dropped


def _release_z(top: float, head: float, botm: float) -> float:
    """Vertical release elevation for a particle in a cell: the MIDPOINT of the
    SATURATED thickness, ``0.5 * (min(top, head) + botm)``.

    For a confined cell the head sits above ``top`` so the saturated top is
    ``top``; for an unconfined/convertible cell the water table (``head``) is
    below ``top`` so the saturated top is ``head``. Releasing at the geometric
    cell mid-height ``0.5*(top+botm)`` would place particles in the DRY part of
    an unconfined cell (above the water table) -- PRT would then release into a
    dry region. Using ``min(top, head)`` keeps the release inside the saturated
    column.

    Guards (all raise :class:`ValueError`): ``top``/``head``/``botm`` must be
    finite, and the cell must be WET (``head > botm``) -- a dry release cell
    (``head <= botm``) is a hard error, not a value to silently clamp.
    """
    if not (math.isfinite(top) and math.isfinite(head) and math.isfinite(botm)):
        raise ValueError(
            f"release-cell geometry must be finite (top={top!r}, head={head!r}, "
            f"botm={botm!r})"
        )
    if head <= botm:
        raise ValueError(
            f"release cell is DRY (head {head!r} <= botm {botm!r}): cannot place "
            "a PRT release point in a dry cell"
        )
    return 0.5 * (min(top, head) + botm)


def _assert_identity_transform(g) -> None:
    """Assert the GWF modelgrid uses the IDENTITY world<->model transform
    (``xoffset == yoffset == angrot == 0``) that this module assumes when it
    (a) places release points using the doublet's WORLD coordinates directly as
    grid-frame coordinates and (b) reads ``load_prt_results`` world output back.

    The case-study DISV vertices are authored directly in world LV95 with only
    ``set_coord_info(crs=...)`` (no offset/rotation), so today world == model
    frame. If a future grid introduces an offset/rotation this assumption breaks
    SILENTLY (particles mislocated), so fail LOUDLY here instead.
    """
    xoff = float(getattr(g, "xoffset", 0.0) or 0.0)
    yoff = float(getattr(g, "yoffset", 0.0) or 0.0)
    angrot = float(getattr(g, "angrot", 0.0) or 0.0)
    if not (xoff == 0.0 and yoff == 0.0 and angrot == 0.0):
        raise NotImplementedError(
            "casestudy_flow_particles assumes an IDENTITY world<->model grid "
            f"transform (xoffset=yoffset=angrot=0); got xoffset={xoff}, "
            f"yoffset={yoff}, angrot={angrot}. A rotated/offset grid would "
            "mislocate release points and pathlines -- update the release/"
            "readback frame handling before using such a grid."
        )


def _assert_track_finite(df: pd.DataFrame) -> None:
    """Guard the loaded/synthetic track frame before any comparison or
    reduction: ``x_world``/``y_world``/``time`` must be finite and ``icell``
    must be a valid (>=1) 1-based cell index. Never let a NaN sail through a
    ``<``/``<=`` comparison (a recurring bug class in this repo)."""
    for col in ("x_world", "y_world", "t"):
        if col not in df.columns:
            raise ValueError(f"track frame missing required column {col!r}")
        vals = np.asarray(df[col], dtype=float)
        if vals.size and not np.all(np.isfinite(vals)):
            n_bad = int(np.count_nonzero(~np.isfinite(vals)))
            raise ValueError(
                f"track frame column {col!r} has {n_bad} non-finite value(s); "
                "refusing to post-process particle tracks with NaN/inf coordinates"
            )
    icell = np.asarray(df["icell"], dtype=float)
    if icell.size and (not np.all(np.isfinite(icell)) or np.any(icell < 1)):
        raise ValueError(
            "track frame column 'icell' has non-finite or <1 (invalid 1-based) "
            "cell indices"
        )


# =============================================================================
# Track-CSV terminal-record extraction (world coords via model_io_utils).
# =============================================================================
def _terminal_records(df: pd.DataFrame) -> pd.DataFrame:
    """One row per ``irpt`` -- the TERMINATE (``ireason == 3``) record if
    present, else the LAST recorded row (e.g. a particle still active when
    ``stoptraveltime`` closes the tracking window under ``extend_tracking``).
    Indexed by ``irpt`` (int)."""
    rows = []
    for irpt, g in df.groupby("irpt", sort=True):
        term = g[g["ireason"] == _IREASON_TERMINATE]
        rows.append(term.iloc[-1] if not term.empty else g.iloc[-1])
    out = pd.DataFrame(rows).reset_index(drop=True)
    out.index = out["irpt"].astype(int)
    return out


def _pathlines_and_end_cells(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[int, int], int]:
    """From a track DataFrame carrying ``irpt``/``x_world``/``y_world``/``t``/
    ``icell``/``ireason`` (as produced by ``model_io_utils.load_prt_results``,
    or hand-authored synthetic data in the same shape): build the
    ``pathlines_world`` frame (``irpt``/``x_world``/``y_world``/``time``), the
    ``end_cells`` map (``irpt -> 0-based terminal cell``), and the count of
    particles with no explicit ``ireason == 3`` termination record."""
    _assert_track_finite(df)
    terminal = _terminal_records(df)
    end_cells = {int(irpt): int(row["icell"]) - 1 for irpt, row in terminal.iterrows()}
    n_no_term_record = int((terminal["ireason"] != _IREASON_TERMINATE).sum())
    pathlines_world = (
        df[["irpt", "x_world", "y_world", "t"]]
        .rename(columns={"t": "time"})
        .reset_index(drop=True)
    )
    return pathlines_world, end_cells, n_no_term_record


# =============================================================================
# build_capture -- assemble + run PRT on the FAITHFUL solved flow field.
# =============================================================================
def build_capture(
    state_result: StateResult,
    *,
    porosity: Optional[float] = None,
    mode: str,
    n_particles: int = 200,
    track_days: float = 730.0,
    work_dir: Any,
    release_radius_m: float = _DEFAULT_RELEASE_RADIUS_M,
) -> Dict[str, Any]:
    """Run MF6 PRT advective particle tracking on *state_result*'s FAITHFUL,
    already-solved DISV flow field (never rebuilds the GWF).

    ``mode='forward'`` releases a strict in-cell golden-angle disc of
    *n_particles* candidates at the INJECTION well and tracks forward on the
    state's own head/budget files. ``mode='backward'`` releases the disc at
    the EXTRACTION well and tracks on REVERSED copies of the head/budget
    files (backward tracking has no flag -- it is file reversal).

    Both modes use ``extend_tracking=True`` + ``stoptraveltime=track_days``
    (the steady-field trap: the GWF's own TDIS is a single ~1-day period, so
    tracking must be explicitly extended past it and closed by travel time,
    not by matching TDIS length to track_days).

    Returns ``{mode, pathlines_world, end_cells, meta, porosity_provenance}``:

    * ``pathlines_world`` -- DataFrame, columns ``irpt``/``x_world``/
      ``y_world``/``time`` (plus ``icell``/``ireason``/``istatus`` for
      downstream diagnostics), in WORLD coordinates (the grid is rotated 30
      degrees with offsets; ``model_io_utils.load_prt_results`` converts via
      ``modelgrid.get_coords``).
    * ``end_cells`` -- ``{irpt: 0-based terminal cell}``.
    * ``meta`` -- run bookkeeping (release counts, dropped count, workspace,
      head/budget paths actually used, well cell, etc).
    * ``porosity_provenance`` -- see :func:`resolve_porosity`.

    ADVECTIVE-only: see the module docstring's claim boundary.
    """
    if mode not in ("forward", "backward"):
        raise ValueError(f"mode must be 'forward' or 'backward', got {mode!r}")
    if not isinstance(n_particles, (int, np.integer)) or n_particles <= 0:
        raise ValueError(f"n_particles must be a positive integer, got {n_particles!r}")
    if not math.isfinite(track_days) or track_days <= 0:
        raise ValueError(f"track_days must be finite and positive, got {track_days!r}")
    if not math.isfinite(release_radius_m) or release_radius_m <= 0:
        raise ValueError(f"release_radius_m must be finite and positive, got {release_radius_m!r}")

    porosity_value, porosity_provenance = resolve_porosity(state_result, porosity)

    doublet = state_result.get("doublet")
    if not doublet:
        raise KeyError(
            "state_result['doublet'] is required to place PRT release points "
            "(a wells-family state, e.g. build_flow_state('wells_only'))"
        )
    well_key = "injection" if mode == "forward" else "extraction"
    well = doublet[well_key]
    center_e, center_n = float(well["E"]), float(well["N"])

    gwf = state_result["gwf"]
    modelgrid = gwf.modelgrid
    spec = state_result["spec"]

    # The doublet E/N are WORLD coords; we use them as grid-frame coords for
    # release-point placement (modelgrid.intersect) and read PRT output back as
    # world coords. Both are only consistent under the identity transform the
    # case-study grid uses today -- assert it so a future offset/rotated grid
    # fails loudly instead of silently mislocating particles.
    _assert_identity_transform(modelgrid)

    # --- DATA-SAT / FMI preflight (hard) -- checked on the ORIGINAL budget
    # file regardless of mode: the reversed copy (backward) carries the
    # identical CellBudgetFile record set. ---------------------------------
    assert_data_sat_available(state_result["budgetfile"])

    points, n_dropped = _strict_release_points(
        modelgrid, center_e, center_n, int(n_particles), float(release_radius_m),
    )
    if not points:
        raise RuntimeError(
            f"all {n_particles} candidate release points were dropped (no unique "
            f"containing cell) around the {well_key} well at ({center_e}, {center_n}); "
            "try a smaller release_radius_m"
        )

    top = np.asarray(spec["top"]).reshape(-1)
    botm = np.asarray(spec["botm"]).reshape(-1)
    # Saturated release elevation needs the solved water table, not just cell
    # geometry (an unconfined cell's saturated top is the head, not `top`).
    heads = np.asarray(state_result["heads"], dtype=float).reshape(-1)

    prt_ws = Path(work_dir) / "_prt" / mode
    prt_ws.mkdir(parents=True, exist_ok=True)

    if mode == "forward":
        head_path = str(state_result["headfile"])
        budget_path = str(state_result["budgetfile"])
    else:
        if not hasattr(flopy.utils.HeadFile, "reverse") or not hasattr(
            flopy.utils.CellBudgetFile, "reverse"
        ):
            raise NotImplementedError(
                "backward PRT tracking requires flopy's HeadFile.reverse / "
                "CellBudgetFile.reverse (this flopy install lacks it); refusing "
                "to fake backward tracking"
            )
        rev_head = prt_ws / "rev.hds"
        rev_budget = prt_ws / "rev.cbc"
        flopy.utils.HeadFile(state_result["headfile"]).reverse(filename=str(rev_head))
        flopy.utils.CellBudgetFile(state_result["budgetfile"]).reverse(filename=str(rev_budget))
        head_path = str(rev_head)
        budget_path = str(rev_budget)

    exe_name = cfc.resolve_mf6_exe()
    ncpl = int(spec["ncpl"])
    gridprops = spec["gridprops"]

    packagedata = []
    for i, (x, y, cell) in enumerate(points):
        z = _release_z(float(top[cell]), float(heads[cell]), float(botm[cell]))
        packagedata.append((i, (0, cell), x, y, z))

    psim = flopy.mf6.MFSimulation(sim_name="prt", exe_name=exe_name, sim_ws=str(prt_ws))
    # PRT has its OWN TDIS. The GWF is STEADY (one ~1-day period) -- do NOT
    # match TDIS length to track_days; use a short TDIS and EXTEND tracking
    # past it via PRP (extend_tracking + stoptraveltime, below).
    flopy.mf6.ModflowTdis(psim, time_units="days", nper=1, perioddata=[(1.0, 1, 1.0)])
    prt = flopy.mf6.ModflowPrt(psim, modelname="prt")
    flopy.mf6.ModflowPrtdisv(
        prt, nlay=1, ncpl=ncpl, nvert=gridprops["nvert"],
        top=spec["top"], botm=[spec["botm"]],
        idomain=[spec["idomain"]],   # faithfully clone the solved GWF's active domain
        vertices=gridprops["vertices"], cell2d=gridprops["cell2d"],
    )
    # Mirror the GWF grid's coordinate metadata onto the PRT model's grid so the
    # PRT frame stays identical to the solved GWF's (identity today -- asserted
    # above -- but this keeps them coupled if the grid ever gains offset/rotation).
    prt.modelgrid.set_coord_info(
        xoff=modelgrid.xoffset, yoff=modelgrid.yoffset,
        angrot=modelgrid.angrot, crs=modelgrid.crs,
    )
    flopy.mf6.ModflowPrtmip(prt, porosity=porosity_value)
    flopy.mf6.ModflowPrtprp(
        prt, pname="prp", nreleasepts=len(packagedata), packagedata=packagedata,
        perioddata={0: ["FIRST"]},
        exit_solve_tolerance=1e-5,
        extend_tracking=True,             # steady field: track PAST the TDIS.
        stoptraveltime=float(track_days),  # close the window by travel time.
    )
    flopy.mf6.ModflowPrtoc(
        prt, pname="oc", track_filerecord=["prt.trk"],
        trackcsv_filerecord=["prt.trk.csv"],
        track_release=True, track_exit=True, track_terminate=True,
        budget_filerecord="prt.cbc", saverecord=[("BUDGET", "ALL")],
    )
    flopy.mf6.ModflowPrtfmi(prt, packagedata=[
        ("GWFHEAD", head_path),
        ("GWFBUDGET", budget_path),
    ])
    ems = flopy.mf6.ModflowEms(psim, pname="ems", filename="prt.ems")
    psim.register_solution_package(ems, [prt.name])

    psim.write_simulation(silent=True)
    ok, buf = psim.run_simulation(silent=True)
    if not ok:
        tail = "\n".join(str(line) for line in buf[-20:]) if buf else "(no run log)"
        raise RuntimeError(f"PRT run ({mode}) failed in {prt_ws}:\n{tail}")

    trackcsv_path = prt_ws / "prt.trk.csv"
    loaded = mio.load_prt_results(trackcsv_path, modelgrid)
    df = loaded["prt_df"]

    pathlines_world, end_cells, n_no_term_record = _pathlines_and_end_cells(df)

    meta = {
        "mode": mode,
        "n_particles_requested": int(n_particles),
        "n_released": len(points),
        "n_dropped": int(n_dropped),
        "n_no_terminate_record": n_no_term_record,
        "track_days": float(track_days),
        "release_radius_m": float(release_radius_m),
        "well_key": well_key,
        "well_cell": int(well["cell"]),
        "center_E": center_e,
        "center_N": center_n,
        "prt_workspace": str(prt_ws),
        "head_path": head_path,
        "budget_path": budget_path,
        "run_ok": bool(ok),
    }

    return {
        "mode": mode,
        "pathlines_world": pathlines_world,
        "end_cells": end_cells,
        "meta": meta,
        "porosity_provenance": porosity_provenance,
    }


# =============================================================================
# Mode-specific summaries (SEPARATE contracts -- forward != capture zone).
# =============================================================================
def connection_summary(forward_capture: Dict[str, Any], extc: int) -> Dict[str, Any]:
    """Injection -> extraction advective connection/travel-time summary for a
    ``mode='forward'`` capture result. NOT a capture zone (that is
    :func:`capture_zone_summary` on a ``mode='backward'`` result).

    Honesty caveat: ``advective_connection_fraction`` is a property of the
    RELEASE DISC (its radius and its ``n_dropped`` off-grid points), not an
    intrinsic property of the doublet -- read ``end_cells`` (the scatter),
    not just this scalar.
    """
    if forward_capture.get("mode") != "forward":
        raise ValueError(
            f"connection_summary expects a mode='forward' capture, got "
            f"{forward_capture.get('mode')!r}"
        )
    end_cells = forward_capture["end_cells"]
    meta = forward_capture.get("meta", {})
    n_released = int(meta.get("n_released", len(end_cells)))
    n_dropped = int(meta.get("n_dropped", 0))

    reached_irpt = [irpt for irpt, cell in end_cells.items() if cell == extc]
    n_reached = len(reached_irpt)
    fraction = (n_reached / n_released) if n_released > 0 else float("nan")

    pw = forward_capture["pathlines_world"]
    if reached_irpt:
        times = pw[pw["irpt"].isin(reached_irpt)].groupby("irpt")["time"].max()
        mean_tt = float(times.mean())
    else:
        mean_tt = float("nan")

    return {
        "advective_connection_fraction": fraction,
        "n_released": n_released,
        "n_reached_extraction": n_reached,
        "n_dropped": n_dropped,
        "mean_travel_time_d_to_extraction": mean_tt,
    }


def capture_zone_summary(backward_capture: Dict[str, Any]) -> Dict[str, Any]:
    """The extraction-well capture-zone summary for a ``mode='backward'``
    capture result. Distinct contract from :func:`connection_summary` -- does
    NOT reuse ``end_cells == extc`` (backward release points are already
    AROUND the extraction well by construction; the interesting question is
    the shape/extent of the traced envelope, not a binary membership test).
    """
    if backward_capture.get("mode") != "backward":
        raise ValueError(
            f"capture_zone_summary expects a mode='backward' capture, got "
            f"{backward_capture.get('mode')!r}"
        )
    pw = backward_capture["pathlines_world"]
    n_pathlines = int(pw["irpt"].nunique()) if len(pw) else 0
    max_backtrack = float(pw["time"].max()) if len(pw) else float("nan")

    return {
        "capture_zone_pathline_count": n_pathlines,
        "max_backtrack_time_d": max_backtrack,
        "envelope_note": (
            "Envelope = the scatter/hull of backward-tracked pathline endpoints "
            "around the extraction well under the steady field + chosen "
            "porosity; NOT an end_cells==extc membership test (that contract "
            "belongs to connection_summary, forward mode only), and NOT a "
            "concentration/exceedance boundary."
        ),
    }


# =============================================================================
# Plotting -- overlay world-coord pathlines/envelope on plot_head_map.
# =============================================================================
def plot_pathlines(state_result: StateResult, capture: Dict[str, Any], *, ax=None, title=None):
    """Overlay forward (or backward) pathlines, in WORLD coordinates, on
    ``casestudy_flow_viz.plot_head_map``. Returns ``(fig, ax)``."""
    import casestudy_flow_viz as cfv

    fig, ax = cfv.plot_head_map(state_result, ax=ax, title=title)
    pw = capture["pathlines_world"]
    color = "tab:orange" if capture.get("mode") == "forward" else "tab:purple"
    for _, grp in pw.groupby("irpt"):
        grp = grp.sort_values("time")
        ax.plot(grp["x_world"], grp["y_world"], linewidth=0.6, color=color, alpha=0.6)
    ax.set_aspect("equal")
    return fig, ax


def plot_capture_zone(state_result: StateResult, backward_capture: Dict[str, Any], *, ax=None):
    """Overlay the backward-tracked capture-zone pathlines + a convex-hull
    envelope of their endpoints on ``plot_head_map``. Returns ``(fig, ax)``."""
    import casestudy_flow_viz as cfv

    fig, ax = plot_pathlines(
        state_result, backward_capture, ax=ax, title="Capture zone (backward tracking)",
    )
    pw = backward_capture["pathlines_world"]
    if len(pw):
        terminals = pw.sort_values("time").groupby("irpt").last()
        pts = terminals[["x_world", "y_world"]].to_numpy()
        if len(pts) >= 3:
            try:
                from scipy.spatial import ConvexHull

                hull = ConvexHull(pts)
                hull_pts = pts[hull.vertices]
                hull_pts = np.vstack([hull_pts, hull_pts[0]])
                ax.plot(
                    hull_pts[:, 0], hull_pts[:, 1],
                    color="black", linewidth=1.4, label="capture envelope",
                )
            except Exception:
                pass
    ax.set_aspect("equal")
    return fig, ax
