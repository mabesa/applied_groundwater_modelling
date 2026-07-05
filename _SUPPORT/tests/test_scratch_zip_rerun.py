"""
End-to-end "rerun from the submission ZIP" test for the scratch workflow.

The promise made to TAs is: *the scratch analysis reruns from the submission ZIP
alone* — no course repo, no FloPy, no heavy model workspace. This test proves that
mechanically:

1. Build a tiny synthetic ``exports/`` bundle (GPKG / CSV / JSON) — the kind of
   thing the steward notebook produces, but hand-made so no model is needed.
2. Copy the template-local ``scratch_io.py`` next to it, exactly as it would sit
   inside a group folder.
3. Zip it, extract the ZIP into a fresh temporary directory (simulating a TA on a
   clean machine), and
4. Run the full analysis pipeline **in a clean subprocess** (fresh interpreter, so
   ``flopy`` is guaranteed absent from ``sys.modules``) using only ``scratch_io``.

It is deliberately independent of the real heavy model workspace, so it is stable
in CI. It skips cleanly if the environment cannot write GeoPackages.

Run with:  uv run pytest _SUPPORT/tests/test_scratch_zip_rerun.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import Polygon

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRATCH_IO_PATH = REPO_ROOT / "PROJECT" / "workspace" / "template" / "scratch_io.py"


def _square(x0, y0, size=5.0):
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)])


def _build_exports(ex: Path) -> None:
    ex.mkdir(parents=True, exist_ok=True)
    for name, heads in (
        ("flow_heads_sub_base.gpkg", [100.0, 100.0]),
        ("flow_heads_sub_wells.gpkg", [99.0, 100.0]),
    ):
        gpd.GeoDataFrame(
            {"cellid": ["0_0", "0_1"], "row": [0, 0], "col": [0, 1], "head_m": heads},
            geometry=[_square(2683000, 1248000), _square(2683005, 1248000)],
            crs="EPSG:2056",
        ).to_file(ex / name, driver="GPKG")

    pd.DataFrame(
        {
            "model": ["sub_base", "sub_wells"],
            "term": ["RIVER_LEAKAGE", "RIVER_LEAKAGE"],
            "flow_in_m3_d": [200.0, 350.0],
            "flow_out_m3_d": [150.0, 100.0],
        }
    ).to_csv(ex / "flow_budget_summary.csv", index=False)

    with open(ex / "run_info.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "schema_version": "1.0",
                "group_number": 0,
                "crs": "EPSG:2056",
                "exports": {"flow_heads_sub_base.gpkg": {"present": True}},
            },
            fh,
        )


# A self-contained driver run in a CLEAN interpreter against the extracted ZIP.
_DRIVER = """
import sys
from pathlib import Path

group_dir = Path(sys.argv[1])
sys.path.insert(0, str(group_dir))          # scratch_io.py sits in the group folder

assert "flopy" not in sys.modules, "flopy leaked before import"
import scratch_io

scratch_io.assert_no_flopy()
ex = scratch_io.find_exports(start=group_dir)
info = scratch_io.load_run_info(ex)
assert scratch_io.check_schema(info)

base = scratch_io.load_heads_gpkg("base", ex)
wells = scratch_io.load_heads_gpkg("wells", ex)
dd = scratch_io.compute_drawdown(base, wells)
area = scratch_io.affected_area(dd, threshold=0.5)
assert abs(area - 25.0) < 1e-6, f"affected area {area} != 25"

budget = scratch_io.load_budget_summary(ex)
riv = scratch_io.river_exchange(budget)
assert not riv.empty

# flopy must never have been pulled in by any of the above.
assert "flopy" not in sys.modules, "flopy leaked during analysis"
assert "pyemu" not in sys.modules, "pyemu leaked during analysis"
scratch_io.assert_no_flopy()
print("SCRATCH_ZIP_RERUN_OK")
"""


def test_scratch_reruns_from_zip(tmp_path):
    # 1. author bundle in a group folder + copy the template-local reader in.
    group_dir = tmp_path / "authoring" / "group_test"
    try:
        _build_exports(group_dir / "exports")
    except Exception as exc:  # pragma: no cover - environment without GPKG writer
        pytest.skip(f"cannot write GeoPackage in this environment: {exc}")
    shutil.copy2(SCRATCH_IO_PATH, group_dir / "scratch_io.py")

    # 2. zip the group folder (what the student uploads).
    zip_path = tmp_path / "submission_group_test.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in group_dir.rglob("*"):
            zf.write(path, path.relative_to(group_dir.parent))

    # 3. extract into a pristine location (a TA on a clean machine).
    extract_root = tmp_path / "ta_machine"
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_root)
    extracted_group = extract_root / "group_test"
    assert (extracted_group / "scratch_io.py").is_file()
    assert (extracted_group / "exports" / "run_info.json").is_file()

    # 4. run the analysis in a clean subprocess (guaranteed flopy-free interpreter).
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(driver), str(extracted_group)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"scratch rerun failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "SCRATCH_ZIP_RERUN_OK" in result.stdout
