"""
Tests for casestudy_doublet_roster (M1.1 -- deterministic doublet-geometry
extraction for the 9 GWHE case-study concessions).

These tests read the REAL cantonal well registry (``Wasserfassungen_-OGD.gpkg``,
downloaded/cached under ``~/applied_groundwater_modelling_data/limmat/gis`` the
same way every notebook fetches it) and, when available, the real calibrated
05f flow model -- there is no synthetic fixture data here, because the whole
point of M1.1 is a fully-pinned, deterministic rule applied to the ACTUAL
registry. No MODFLOW solve happens anywhere in this module or these tests
(the 05f model is loaded read-only, already solved, for its static
grid/idomain only), so this suite is fast (a few seconds), unlike the real
MF6-solve suites elsewhere in this repo.

Run with: uv run pytest _SUPPORT/tests/test_casestudy_doublet_roster.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import casestudy_doublet_roster as cdr  # noqa: E402


EXPECTED_CONCESSIONS = {
    "b010210", "b010219", "b010201", "b010236", "b010120",
    "b010223", "b010227", "b010213", "b010207",
}
EXCLUDED_CONCESSION = "b010190"  # gallery-only well the G4 swap replaces
# b010005 was an earlier G4 candidate, dropped (river/spread gate) in favour of
# b010120; it must no longer appear in the roster.
FORMER_CANDIDATE = "b010005"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def table() -> pd.DataFrame:
    """Build the table once (in-memory only, no disk write) and reuse it."""
    return cdr.build_doublet_table(write=False)


# ---------------------------------------------------------------------------
# roster shape / identity
# ---------------------------------------------------------------------------
def test_nine_rows(table):
    assert len(table) == 9


def test_b010120_present_b010190_and_b010005_absent(table):
    concessions = set(table["concession"])
    assert "b010120" in concessions
    assert EXCLUDED_CONCESSION not in concessions
    assert FORMER_CANDIDATE not in concessions


def test_exact_concession_set(table):
    assert set(table["concession"]) == EXPECTED_CONCESSIONS


def test_g4_is_b010120(table):
    """Acceptance: G4 = b010120 (the user-approved clean swap for the
    gallery-only b010190; matches case_config.yaml's group numbering)."""
    row = table.loc[table["group"] == "G4"].iloc[0]
    assert row["concession"] == "b010120"


def test_no_duplicate_concessions(table):
    assert table["concession"].duplicated().sum() == 0


def test_no_duplicate_groups(table):
    assert table["group"].duplicated().sum() == 0


# ---------------------------------------------------------------------------
# provenance columns present + populated
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = [
    "group", "concession", "inj_E", "inj_N", "ext_E", "ext_N", "Q_m3d", "Q_basis",
    "source_file", "source_sha256", "boundary_file", "boundary_sha256",
    "modelgrid_sha", "idomain_sha",
    "gwr_ids_ext", "gwr_ids_inj", "ext_wells", "inj_wells",
    "n_ext", "n_inj", "n_excluded", "n_ambiguous", "n_rows_total", "nutzart",
    "ext_method", "inj_method",
    "ertrag_raw", "ertrag_max_lmin", "crs", "spread_ext_m", "spread_inj_m",
    "in_domain", "in_active_cell", "in_river",
    "in_domain_ext", "in_domain_inj", "in_active_cell_ext", "in_active_cell_inj",
    "in_river_ext", "in_river_inj", "flags",
]


def test_required_columns_present(table):
    for col in REQUIRED_COLUMNS:
        assert col in table.columns, f"missing column {col!r}"


def test_provenance_populated_every_row(table):
    for _, row in table.iterrows():
        assert row["source_file"], "source_file must be recorded"
        assert len(row["source_sha256"]) == 64, "sha256 must be a full hex digest"
        assert row["crs"] == "EPSG:2056"
        assert row["gwr_ids_ext"], "gwr_ids_ext must list the wells used"
        assert row["gwr_ids_inj"], "gwr_ids_inj must list the wells used"
        assert row["n_ext"] >= 1
        assert row["n_inj"] >= 1
        assert row["ext_method"] in ("centroid", "fallback")
        assert row["inj_method"] in ("centroid", "fallback")


def test_source_file_is_the_wells_registry(table):
    for _, row in table.iterrows():
        assert row["source_file"].endswith("Wasserfassungen_-OGD.gpkg")


def test_source_sha256_matches_actual_file(table):
    """Cheap tamper-check: the recorded hash must match the file on disk right now."""
    path = Path(table.iloc[0]["source_file"])
    assert path.exists()
    assert cdr._sha256_file(path) == table.iloc[0]["source_sha256"]


# ---------------------------------------------------------------------------
# cell-validity gate: every row is checked, and every NON-flagged row passes
# ---------------------------------------------------------------------------
def test_active_cell_check_ran(table):
    """The 05f model + boundary/river GIS are all locally cached in this dev
    environment, so the full gate should have actually run (not degraded to
    NOT-RUN) -- in_domain/in_active_cell/in_river must be real booleans, not
    None, for every row."""
    for col in ("in_domain", "in_active_cell", "in_river"):
        assert table[col].apply(lambda v: v is None).sum() == 0, (
            f"{col} is None for some row -- cell-validity check did not run "
            "(see that row's 'flags' for why, if this is expected in a "
            "degraded environment)"
        )


def test_every_unflagged_row_is_valid(table):
    """Acceptance: every inj+ext pair is in-domain, in an active cell, and
    non-river UNLESS the row's flags explicitly record why (spread/cell/Q
    gate tripped and, if unresolved, flagged for human review)."""
    for _, row in table.iterrows():
        if row["flags"]:
            continue  # a flagged row is explicitly allowed to fail the gate
        assert bool(row["in_domain"]) is True, f"{row['concession']}: not in domain"
        assert bool(row["in_active_cell"]) is True, f"{row['concession']}: inactive cell"
        assert bool(row["in_river"]) is False, f"{row['concession']}: within river buffer"


def test_clean_roster_has_zero_flags(table):
    """The swapped-in roster (G4 = b010120) is intended to be CLEAN: every
    concession is a tightly-clustered doublet that clears the spread / river /
    active-cell gates and resolves an Ertrag. Zero rows should carry any flag.
    If this fails, the registry changed upstream or a threshold regressed --
    do NOT paper over it; inspect the flag text."""
    flagged = {c: f for c, f in zip(table["concession"], table["flags"]) if f}
    assert flagged == {}, f"unexpected flag(s) on the clean roster: {flagged}"


def test_b010120_is_clean(table):
    """Explicit confirmation the user-approved swap comes through clean: G4 =
    b010120, centroid method on both sides, valid + non-river, no flags."""
    row = table.loc[table["concession"] == "b010120"].iloc[0]
    assert row["group"] == "G4"
    assert row["flags"] == ""
    assert row["ext_method"] == "centroid"
    assert row["inj_method"] == "centroid"
    assert bool(row["in_domain"]) is True
    assert bool(row["in_active_cell"]) is True
    assert bool(row["in_river"]) is False
    assert row["Q_m3d"] == pytest.approx(3000.0 * cdr.LMIN_TO_M3D)


def test_per_role_validity_columns_present_and_consistent(table):
    """The six per-role validity columns exist and, where both sides are
    known, combine into the aggregate columns the same way the module does
    (domain/active = AND, river = OR)."""
    for col in ("in_domain_ext", "in_domain_inj", "in_active_cell_ext",
                "in_active_cell_inj", "in_river_ext", "in_river_inj"):
        assert col in table.columns
    for _, row in table.iterrows():
        if row["in_domain_ext"] is not None and row["in_domain_inj"] is not None:
            assert bool(row["in_domain"]) == (bool(row["in_domain_ext"]) and bool(row["in_domain_inj"]))
        if row["in_river_ext"] is not None and row["in_river_inj"] is not None:
            assert bool(row["in_river"]) == (bool(row["in_river_ext"]) or bool(row["in_river_inj"]))


# ---------------------------------------------------------------------------
# spread gate arithmetic itself (independent of the live registry snapshot)
# ---------------------------------------------------------------------------
def test_spread_gate_triggers_fallback_to_nearest_real_well():
    wells = [
        {"GWR_ID": "x_01", "E": 0.0, "N": 0.0},
        {"GWR_ID": "x_02", "E": 100.0, "N": 0.0},  # spread 100 m > 50 m
    ]
    ctx = cdr._CellValidityContext()  # nothing checked -> no cell violation
    result = cdr._centroid_or_fallback(wells, "ext", ctx)
    assert result["method"] == "fallback"
    assert result["spread_m"] == 100.0
    assert result["chosen_gwr"] in ("x_01", "x_02")
    assert result["flags"], "a fallback must be flagged"


def test_no_spread_violation_uses_centroid():
    wells = [
        {"GWR_ID": "x_01", "E": 0.0, "N": 0.0},
        {"GWR_ID": "x_02", "E": 10.0, "N": 0.0},  # spread 10 m < 50 m
    ]
    ctx = cdr._CellValidityContext()
    result = cdr._centroid_or_fallback(wells, "ext", ctx)
    assert result["method"] == "centroid"
    assert result["E"] == 5.0 and result["N"] == 0.0
    assert not result["flags"]


def test_single_well_with_no_fallback_option_is_flagged_not_swapped():
    """n=1 with a tripped gate: keep the point, flag it -- never invent an
    alternative well that doesn't exist."""
    wells = [{"GWR_ID": "x_01", "E": 5.0, "N": 5.0}]

    class _AlwaysBadCtx(cdr._CellValidityContext):
        def check(self, x, y):
            return dict(in_domain=True, in_active_cell=True, in_river=True)

    ctx = _AlwaysBadCtx()
    result = cdr._centroid_or_fallback(wells, "inj", ctx)
    assert result["method"] == "centroid"
    assert result["E"] == 5.0 and result["N"] == 5.0
    assert result["flags"]
    assert "no fallback alternative" in result["flags"][0]


def test_fallback_tie_break_is_deterministic():
    """Two wells equidistant from a tripped centroid -> the tie must break
    the same way every time (sorted GWR_ID)."""
    wells = [
        {"GWR_ID": "x_02", "E": 100.0, "N": 0.0},
        {"GWR_ID": "x_01", "E": 0.0, "N": 0.0},
    ]  # deliberately unsorted input; centroid = (50, 0), both wells 50 m away
    ctx = cdr._CellValidityContext()
    results = [cdr._centroid_or_fallback(sorted(wells, key=lambda w: w["GWR_ID"]), "ext", ctx)
               for _ in range(5)]
    chosen = {r["chosen_gwr"] for r in results}
    assert len(chosen) == 1, "tie-break must be deterministic across repeated calls"
    assert chosen == {"x_01"}, "ties resolve to the alphabetically-first GWR_ID"


# ---------------------------------------------------------------------------
# Ertrag / Q parsing
# ---------------------------------------------------------------------------
def test_ertrag_range_takes_upper_bound():
    result = cdr._parse_ertrag(["Grundwasserfassung mit Ertrag 300 - 3000 l/min"])
    assert result["q_lmin"] == 3000.0
    assert result["lower_bound"] is False


def test_ertrag_lower_bound_only_is_flagged():
    result = cdr._parse_ertrag(["Grundwasserfassung mit Ertrag > 3000 l/min"])
    assert result["q_lmin"] == 3000.0
    assert result["lower_bound"] is True


def test_ertrag_missing_is_none():
    result = cdr._parse_ertrag(["Grundwasseranreicherungsanlage, Rückversickerung, Sickergalerie"])
    assert result["q_lmin"] is None
    assert result["raw"] is None
    assert result["disagreement"] is False


def test_ertrag_case_insensitive():
    result = cdr._parse_ertrag(["... ERTRAG 300 - 3000 L/MIN ..."])
    assert result["q_lmin"] == 3000.0


def test_ertrag_whitespace_in_lmin():
    result = cdr._parse_ertrag(["Ertrag 300 - 3000 l / min"])
    assert result["q_lmin"] == 3000.0


@pytest.mark.parametrize("text,expected", [
    ("Ertrag 300 - 3'000 l/min", 3000.0),      # ASCII apostrophe thousands sep
    ("Ertrag 300 - 3’000 l/min", 3000.0),      # typographic apostrophe
    ("Ertrag > 12'000 l/min", 12000.0),        # lower-bound + thousands sep
])
def test_ertrag_swiss_thousands_separator(text, expected):
    result = cdr._parse_ertrag([text])
    assert result["q_lmin"] == expected


def test_ertrag_decimal_comma():
    result = cdr._parse_ertrag(["Ertrag 300,5 l/min"])
    assert result["q_lmin"] == 300.5


def test_ertrag_disagreement_picks_largest_and_flags():
    result = cdr._parse_ertrag([
        "Ertrag 300 - 3000 l/min",
        "Ertrag 30 - 300 l/min",   # a DIFFERENT, smaller range
    ])
    assert result["q_lmin"] == 3000.0           # largest wins, deterministically
    assert result["disagreement"] is True


def test_ertrag_agreement_across_rows_not_flagged():
    result = cdr._parse_ertrag([
        "Ertrag 300 - 3000 l/min",
        "Ertrag 300 - 3000 l/min",
    ])
    assert result["disagreement"] is False


def test_build_flags_ertrag_disagreement(monkeypatch):
    """A concession whose rows carry disagreeing Ertrag clauses must surface a
    'DISAGREEING' flag in the built table (not silently pick a number)."""
    real = cdr._parse_ertrag

    def _fake(texts):
        out = real(texts)
        # force a disagreement result for whatever concession is being parsed
        out = dict(out)
        out["disagreement"] = True
        out["raw"] = "Ertrag 300 - 3000 l/min | Ertrag 30 - 300 l/min"
        return out

    monkeypatch.setattr(cdr, "_parse_ertrag", _fake)
    df = cdr.build_doublet_table(write=False, strict=False)
    assert (df["flags"].str.contains("DISAGREEING", na=False)).all()


def test_q_m3d_conversion_factor(table):
    """Every concession here resolves 'Ertrag ... 3000 l/min' (directly or as
    a flagged lower bound) -> Q_m3d must be 3000 * 1.44 = 4320."""
    for _, row in table.iterrows():
        assert row["ertrag_max_lmin"] == 3000.0
        assert row["Q_m3d"] == pytest.approx(3000.0 * cdr.LMIN_TO_M3D)


def test_q_parsed_for_every_concession(table):
    """Grounded expectation: all 9 concessions resolve an Ertrag clause (no
    concession in this roster is missing licensed-yield data)."""
    assert table["Q_m3d"].isna().sum() == 0
    assert table["ertrag_raw"].isna().sum() == 0


# ---------------------------------------------------------------------------
# role classification
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fassart,expected", [
    ("Vertikalbrunnen mit Rückversickerung: Entnahme", "ext"),
    ("Vertikalbrunnen mit Rückversickerung: Rückgabe", "inj"),
    ("Rückversickerung mit Sickergalerie", None),
    ("Grundwasseranreicherungsanlage, Rückversickerung, Sickergalerie", None),
    ("Vertikalbrunnen", None),
    (None, None),
    # both substrings present -> ambiguous sentinel, NOT silently "ext".
    ("Entnahme und Rückgabe kombiniert", "ambiguous"),
])
def test_role_from_fassart(fassart, expected):
    assert cdr._role_from_fassart(fassart) == expected


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------
def test_determinism_in_memory():
    """Two independent in-memory builds must agree on every coordinate."""
    df1 = cdr.build_doublet_table(write=False)
    df2 = cdr.build_doublet_table(write=False)
    pd.testing.assert_frame_equal(df1, df2)


def test_determinism_on_disk_byte_identical(tmp_path):
    """Writing the table twice (to a scratch location, not the real
    deliverable path) must produce byte-identical files -- no randomness, no
    timestamp, no dict-ordering drift."""
    out_csv = tmp_path / "doublet_table.csv"
    out_yaml = tmp_path / "doublet_table.yaml"

    cdr.build_doublet_table(out_csv=out_csv, out_yaml=out_yaml, write=True)
    first_csv = out_csv.read_bytes()
    first_yaml = out_yaml.read_bytes()

    cdr.build_doublet_table(out_csv=out_csv, out_yaml=out_yaml, write=True)
    second_csv = out_csv.read_bytes()
    second_yaml = out_yaml.read_bytes()

    assert first_csv == second_csv
    assert first_yaml == second_yaml


def test_deliverable_files_exist_and_parse():
    """The checked-in deliverable (PROJECT/workspace/template/doublet_table.*)
    should exist and round-trip through pandas/yaml. (This does not rebuild
    it -- it just checks whatever is currently committed is well-formed.)"""
    assert cdr.DEFAULT_OUT_CSV.exists(), (
        "doublet_table.csv missing -- run "
        "`uv run python -m casestudy_doublet_roster` (or build_doublet_table()) "
        "from _SUPPORT/src to (re)generate it"
    )
    df = pd.read_csv(cdr.DEFAULT_OUT_CSV)
    assert len(df) == 9
    assert set(df["concession"]) == EXPECTED_CONCESSIONS

    if cdr.DEFAULT_OUT_YAML.exists():
        import yaml
        with open(cdr.DEFAULT_OUT_YAML) as fh:
            data = yaml.safe_load(fh)
        assert len(data["doublet_table"]) == 9


# ---------------------------------------------------------------------------
# graceful degradation: check_active_cell=False never silently claims a pass
# ---------------------------------------------------------------------------
def test_check_active_cell_disabled_marks_not_run():
    # strict=False is REQUIRED here: with the check skipped, strict=True (the
    # default) refuses to emit an acceptance table (see test_strict_* below).
    df = cdr.build_doublet_table(check_active_cell=False, write=False, strict=False)
    assert (df["in_domain"].isna()).all()
    assert (df["in_active_cell"].isna()).all()
    assert (df["in_river"].isna()).all()
    # The skip must be visible in every row's flags, not silent.
    assert (df["flags"].str.contains("NOT RUN", na=False)).all()


def test_flow_model_load_failure_degrades_to_boundary_river_only(monkeypatch):
    """Simulate the 05f flow-model load failing (e.g. missing mf6 exe): the
    context must still recover in_domain/in_river from the boundary/river GIS
    directly, and must clearly mark in_active_cell as not run -- never
    silently report it as passing."""
    import transport_srcpulse_demo as tsd

    def _boom():
        raise RuntimeError("simulated mf6 load failure")

    monkeypatch.setattr(tsd, "load_limmat_flow", _boom)
    ctx = cdr._build_cell_validity_context(check_active_cell=True)

    assert ctx.active_cell_checked is False
    assert ctx.domain_checked is True
    assert ctx.river_checked is True
    assert any("NOT RUN" in n for n in ctx.notes)

    validity = ctx.check(2681885.9, 1247397.9)
    assert validity["in_active_cell"] is None
    assert validity["in_domain"] is not None
    assert validity["in_river"] is not None


# ---------------------------------------------------------------------------
# strict-mode acceptance gate
# ---------------------------------------------------------------------------
def test_strict_default_builds_clean_roster(table):
    """The clean roster must build under strict=True without raising (the
    module-scope `table` fixture already uses the default strict=True)."""
    assert len(table) == 9
    assert (table["flags"] == "").all()


def test_strict_raises_when_active_cell_check_did_not_run():
    """strict=True must REFUSE to emit an acceptance table when the active-cell
    check was skipped -- a caller must not get a provenance-stamped table whose
    in_active_cell was never verified."""
    with pytest.raises(RuntimeError, match="active-cell check did NOT run"):
        cdr.build_doublet_table(check_active_cell=False, write=False, strict=True)


def test_strict_raises_on_unresolved_bad_row(monkeypatch):
    """strict=True must raise if any row stays bad-validity after fallback
    (here: a context that reports every point as in-river, active-check ran)."""
    class _AllInRiverCtx(cdr._CellValidityContext):
        def check(self, x, y):
            return dict(in_domain=True, in_active_cell=True, in_river=True)

    def _fake_ctx(check_active_cell=True):
        return _AllInRiverCtx(
            domain_checked=True, river_checked=True, active_cell_checked=True,
            boundary_file="fake_boundary.gpkg", boundary_sha256="deadbeef",
        )

    monkeypatch.setattr(cdr, "_build_cell_validity_context", _fake_ctx)
    with pytest.raises(RuntimeError, match="unresolved bad-validity"):
        cdr.build_doublet_table(write=False, strict=True)


def test_non_strict_records_instead_of_raising(monkeypatch):
    """strict=False on the same all-in-river context must NOT raise -- it
    returns a table with the violations recorded as flags (non-acceptance)."""
    class _AllInRiverCtx(cdr._CellValidityContext):
        def check(self, x, y):
            return dict(in_domain=True, in_active_cell=True, in_river=True)

    def _fake_ctx(check_active_cell=True):
        return _AllInRiverCtx(
            domain_checked=True, river_checked=True, active_cell_checked=True,
            boundary_file="fake_boundary.gpkg", boundary_sha256="deadbeef",
        )

    monkeypatch.setattr(cdr, "_build_cell_validity_context", _fake_ctx)
    df = cdr.build_doublet_table(write=False, strict=False)
    assert len(df) == 9
    assert (df["flags"] != "").all()  # every row carries a river/gate flag


# ---------------------------------------------------------------------------
# boundary semantics: covers (not contains) so on-boundary counts as in-domain
# ---------------------------------------------------------------------------
def test_boundary_uses_covers_not_contains():
    from shapely.geometry import Polygon, Point

    square = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    ctx = cdr._CellValidityContext(domain_checked=True, boundary_poly=square)

    on_edge = ctx.check(0.0, 50.0)      # exactly on the west edge
    inside = ctx.check(50.0, 50.0)
    outside = ctx.check(-1.0, 50.0)

    # covers() -> a point on the boundary is in-domain; contains() would be False.
    assert on_edge["in_domain"] is True
    assert square.covers(Point(0.0, 50.0)) and not square.contains(Point(0.0, 50.0))
    assert inside["in_domain"] is True
    assert outside["in_domain"] is False


# ---------------------------------------------------------------------------
# both-role guard: a FASSART with BOTH substrings is flagged, not silent
# ---------------------------------------------------------------------------
def test_both_role_fassart_is_flagged_in_build(monkeypatch):
    """If a well's FASSART contains BOTH 'Entnahme' and 'Rückgabe', the build
    must flag it (excluded from both role sets, surfaced for review)."""
    real_role = cdr._role_from_fassart
    target_conc = "b010210"

    orig_load = cdr._load_registry

    def _patched_load():
        gdf, path, notes = orig_load()
        gdf = gdf.copy()
        # Rewrite ONE extra synthetic well into the target concession with an
        # ambiguous FASSART, so the guard has something to catch. We append a
        # row cloned from an existing well of that concession.
        conc_mask = gdf["GWR_ID"].str.startswith(target_conc + "_")
        seed = gdf[conc_mask].iloc[0].copy()
        seed["GWR_ID"] = target_conc + "_99"
        seed["FASSART"] = "Vertikalbrunnen: Entnahme und Rückgabe"
        gdf = pd.concat([gdf, pd.DataFrame([seed])], ignore_index=True)
        return gdf, path, notes

    monkeypatch.setattr(cdr, "_load_registry", _patched_load)
    monkeypatch.setattr(cdr, "_role_from_fassart", real_role)  # unchanged, explicit
    df = cdr.build_doublet_table(write=False, strict=False)
    row = df.loc[df["concession"] == target_conc].iloc[0]
    assert "ambiguous" in row["flags"].lower()
    assert target_conc + "_99" in row["flags"]
    assert int(row["n_ambiguous"]) >= 1


# ---------------------------------------------------------------------------
# Fix 1: CRS verification (assert/reproject) + E/N-vs-geometry agreement
# ---------------------------------------------------------------------------
def test_reproject_helper_passes_lv95_through_untouched():
    from shapely.geometry import Point

    gdf = gpd.GeoDataFrame({"x": [1]}, geometry=[Point(2681000, 1248000)], crs="EPSG:2056")
    notes = []
    out = cdr._reproject_to_lv95(gdf, "test", notes)
    assert out.crs.to_epsg() == 2056
    assert notes == []  # no reprojection note when already LV95


def test_reproject_helper_reprojects_and_notes_wrong_crs():
    from shapely.geometry import Point

    # A WGS84 point over Zurich; reprojection to LV95 should land near the valley.
    gdf = gpd.GeoDataFrame({"x": [1]}, geometry=[Point(8.54, 47.37)], crs="EPSG:4326")
    notes = []
    out = cdr._reproject_to_lv95(gdf, "registry", notes)
    assert out.crs.to_epsg() == 2056
    assert len(notes) == 1 and "reprojected" in notes[0]
    # Roughly in the LV95 numeric range (E ~2.68e6, N ~1.25e6).
    assert 2_600_000 < out.geometry.iloc[0].x < 2_720_000
    assert 1_200_000 < out.geometry.iloc[0].y < 1_300_000


def test_reproject_helper_raises_on_undefined_crs():
    from shapely.geometry import Point

    gdf = gpd.GeoDataFrame({"x": [1]}, geometry=[Point(2681000, 1248000)], crs=None)
    with pytest.raises(ValueError, match="CRS is undefined"):
        cdr._reproject_to_lv95(gdf, "registry", [])


def test_registry_en_agrees_with_geometry(table):
    """The real registry passed the E/N-vs-geometry check during the build (it
    would have raised otherwise); re-verify the invariant directly here."""
    gdf, path, notes = cdr._load_registry()
    # For the 9 roster concessions, E/N must equal the geometry within tol.
    gdf = gdf.copy()
    gdf["conc"] = gdf["GWR_ID"].str.split("_").str[0]
    sub = gdf[gdf["conc"].isin(EXPECTED_CONCESSIONS)]
    de = (sub["E"] - sub.geometry.x).abs().max()
    dn = (sub["N"] - sub.geometry.y).abs().max()
    assert de <= cdr.EN_GEOM_TOL_M
    assert dn <= cdr.EN_GEOM_TOL_M


def test_en_geometry_disagreement_raises(monkeypatch):
    """If E/N diverge from geometry (e.g. a garbled column), the load must
    raise rather than emit untrustworthy coordinates."""
    orig_read = cdr.gpd.read_file

    def _corrupt_read(path, *a, **kw):
        gdf = orig_read(path, *a, **kw)
        if "layer" in kw and kw["layer"] == cdr.WELLS_LAYER:
            gdf = gdf.copy()
            gdf["E"] = gdf["E"] + 500.0  # shove E 500 m off its geometry
        return gdf

    monkeypatch.setattr(cdr.gpd, "read_file", _corrupt_read)
    with pytest.raises(ValueError, match="disagree with geometry"):
        cdr._load_registry()


# ---------------------------------------------------------------------------
# Fix 2: grid/idomain provenance hashes present + stable + handoff is (E,N)
# ---------------------------------------------------------------------------
def test_grid_idomain_provenance_present_and_hex(table):
    for _, row in table.iterrows():
        assert isinstance(row["modelgrid_sha"], str) and len(row["modelgrid_sha"]) == 64
        assert isinstance(row["idomain_sha"], str) and len(row["idomain_sha"]) == 64


def test_grid_idomain_provenance_stable_across_builds():
    df1 = cdr.build_doublet_table(write=False)
    df2 = cdr.build_doublet_table(write=False)
    assert (df1["modelgrid_sha"] == df2["modelgrid_sha"]).all()
    assert (df1["idomain_sha"] == df2["idomain_sha"]).all()
    # single grid used for all rows -> one distinct hash each
    assert df1["modelgrid_sha"].nunique() == 1
    assert df1["idomain_sha"].nunique() == 1


def test_no_coarse_cellid_column(table):
    """The handoff is (E, N), NOT a coarse-05f cell index -- assert no
    misleading cellid/row/col column leaked into the table."""
    for banned in ("cellid", "cell_id", "node", "row", "col", "icpl", "ncpl"):
        assert banned not in table.columns


# ---------------------------------------------------------------------------
# Fix 3: per-well coordinate columns
# ---------------------------------------------------------------------------
def test_per_well_columns_present_parseable_deterministic(table):
    for _, row in table.iterrows():
        for col in ("ext_wells", "inj_wells"):
            entries = row[col].split("|")
            assert entries and all(entries)
            gwr_ids = []
            for e in entries:
                parts = e.split(":")
                assert len(parts) == 3, f"{col} entry not GWR_ID:E:N -> {e!r}"
                gid, e_str, n_str = parts
                float(e_str); float(n_str)  # parseable coords
                assert gid.startswith(row["concession"])
                gwr_ids.append(gid)
            # deterministic: entries sorted by GWR_ID
            assert gwr_ids == sorted(gwr_ids)
        # count consistency with n_ext / n_inj
        assert len(row["ext_wells"].split("|")) == row["n_ext"]
        assert len(row["inj_wells"].split("|")) == row["n_inj"]


def test_per_well_coords_reconstruct_centroid(table):
    """The representative ext/inj centroid must equal the geometric mean of the
    per-well coords (for centroid-method rows)."""
    for _, row in table.iterrows():
        if row["ext_method"] == "centroid":
            xs = [float(e.split(":")[1]) for e in row["ext_wells"].split("|")]
            ys = [float(e.split(":")[2]) for e in row["ext_wells"].split("|")]
            assert round(sum(xs) / len(xs), 1) == row["ext_E"]
            assert round(sum(ys) / len(ys), 1) == row["ext_N"]


# ---------------------------------------------------------------------------
# Fix 4: Q_basis annotation
# ---------------------------------------------------------------------------
def test_q_basis_is_licensed_max(table):
    assert (table["Q_basis"] == "licensed_max").all()


# ---------------------------------------------------------------------------
# Fix 5: schema validation + role/exclusion counts + WPG geothermal check
# ---------------------------------------------------------------------------
def test_schema_validation_raises_on_missing_column(monkeypatch):
    orig_read = cdr.gpd.read_file

    def _drop_col_read(path, *a, **kw):
        gdf = orig_read(path, *a, **kw)
        if "layer" in kw and kw["layer"] == cdr.WELLS_LAYER:
            gdf = gdf.drop(columns=["NUTZART"])
        return gdf

    monkeypatch.setattr(cdr.gpd, "read_file", _drop_col_read)
    with pytest.raises(ValueError, match="missing expected column"):
        cdr._load_registry()


def test_role_and_exclusion_counts_non_degenerate(table):
    for _, row in table.iterrows():
        assert row["n_ext"] >= 1, f"{row['concession']}: no Entnahme"
        assert row["n_inj"] >= 1, f"{row['concession']}: no Rückgabe"
        assert row["n_excluded"] >= 0
        assert row["n_ambiguous"] == 0  # clean roster
        # total accounts for at least the used wells
        assert row["n_rows_total"] >= row["n_ext"] + row["n_inj"]


def test_all_concessions_are_geothermal_wpg(table):
    for _, row in table.iterrows():
        assert cdr.GEOTHERMAL_NUTZART in row["nutzart"], (
            f"{row['concession']}: NUTZART {row['nutzart']!r} not geothermal"
        )
    # and no WPG flag should have fired
    assert not table["flags"].str.contains("nutzart", case=False, na=False).any()


def test_non_wpg_concession_flags_and_strict_raises(monkeypatch):
    """A registry change flipping a concession off WPG must flag (strict=False)
    and raise (strict=True)."""
    orig_read = cdr.gpd.read_file
    target = "b010210"

    def _flip_nutzart(path, *a, **kw):
        gdf = orig_read(path, *a, **kw)
        if "layer" in kw and kw["layer"] == cdr.WELLS_LAYER:
            gdf = gdf.copy()
            mask = gdf["GWR_ID"].str.startswith(target + "_")
            gdf.loc[mask, "NUTZART"] = "TWG"  # drinking water, not geothermal
        return gdf

    monkeypatch.setattr(cdr.gpd, "read_file", _flip_nutzart)
    df = cdr.build_doublet_table(write=False, strict=False)
    row = df.loc[df["concession"] == target].iloc[0]
    assert "nutzart" in row["flags"].lower()

    monkeypatch.setattr(cdr.gpd, "read_file", _flip_nutzart)
    with pytest.raises(RuntimeError, match="nutzart"):
        cdr.build_doublet_table(write=False, strict=True)
