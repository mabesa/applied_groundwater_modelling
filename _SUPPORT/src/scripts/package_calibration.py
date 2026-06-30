"""Package a completed NB5 PEST++ calibration workspace for download."""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import flopy
import pyemu

from setup_pest_calibration import CALIBRATION_BUNDLE_MIN_VERSION


ZIP_NAME = "limmat_valley_calibrated_model.zip"
README_NAME = "limmat_valley_calibrated_model_README.md"
MAX_BUNDLE_BYTES = 2 * 1024 * 1024

STRIP_SUFFIXES = (
    ".upg.csv",
    ".rid",
    ".rtj",
    ".fpr",
    ".bpa",
    ".svd",
    ".jcs",
    ".sen",
    ".ipar",
    ".isen",
    ".log",
)
STRIP_EXACT = {"run.info"}
ESSENTIAL_FILES = {
    "calibration.pst",
    "calibration.par",
    "calibration.jcb",
    "calibration.par.usum.csv",
    "calibration.post.cov",
    "pilot_points.csv",
    "hk_pps.dat",
    "pp_xy.npy",
    "sihl_mult.dat",
    "sihl_cell_ids.npy",
    "heads_out.ins",
    "heads_sim.dat",
    "forward_run.py",
    "run_model.sh",
    "hk_pps.tpl",
    "sihl_mult.tpl",
    "calibration.rec",
    "calibration.iobj",
    "calibration.rei",
}


def _run_version_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return "not found"
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else f"exit {result.returncode}"


def _commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip()


def _should_strip(path: Path) -> bool:
    name = path.name
    if name in STRIP_EXACT:
        return True
    if name.startswith("calibration.") and ".fosm_reweight.rei" in name:
        return True
    if name.startswith("calibration.") and name.endswith(".par.usum.csv"):
        stem = name.removesuffix(".par.usum.csv")
        return stem.split(".")[-1].isdigit()
    if name.startswith("calibration.") and name.endswith(".par"):
        return name.removesuffix(".par").split(".")[-1].isdigit()
    if name.startswith("calibration.") and name.endswith(".post.cov"):
        return name.removesuffix(".post.cov").split(".")[-1].isdigit()
    if name.startswith("calibration.rei") and name.removeprefix("calibration.rei").isdigit():
        return True
    return name.endswith(STRIP_SUFFIXES)


def _read_pst_metadata(pst_path: Path) -> tuple[int, int]:
    pst = pyemu.Pst(str(pst_path))
    par_names = [str(name).lower() for name in pst.parameter_data.index]
    n_pilot_points = sum(name.startswith("hk_pp_") for name in par_names)
    n_observations = len(pst.observation_data)
    return n_pilot_points, n_observations


def _build_manifest(pest_setup: Path) -> dict[str, object]:
    n_pilot_points, n_observations = _read_pst_metadata(pest_setup / "calibration.pst")
    return {
        "bundle_version": CALIBRATION_BUNDLE_MIN_VERSION,
        "commit_sha": _commit_sha(),
        "pestpp_glm_version": _run_version_command(["pestpp-glm", "--version"]),
        "n_pilot_points": n_pilot_points,
        "n_observations": n_observations,
        "bundle_date": _datetime.date.today().isoformat(),
    }


def _readme_text(manifest: dict[str, object]) -> str:
    env = {
        "pestpp-glm": manifest["pestpp_glm_version"],
        "flopy": flopy.__version__,
        "pyemu": pyemu.__version__,
        "MODFLOW 6": _run_version_command(["mf6", "-v"]),
        "uv": _run_version_command(["uv", "--version"]),
    }
    env_lines = "\n".join(f"- {name}: {version}" for name, version in env.items())
    return f"""# Limmat Valley Calibrated Model Bundle

## Seeds

- Synthetic observations and reference K field: `seed=42` (`calibration_utils.py:284,383`).
- Pilot-point layout: `seed=123` (`setup_pest_calibration.py:55`).
- Reproducibility caveat: `generate_synthetic_observations` uses global `np.random.seed` (`calibration_utils.py:731`), so reproducibility depends on upstream call order being unchanged.

## PEST Settings

- NOPTMAX: 10
- `pt_weight`: 1.5
- `reg_weight`: 0.5
- `n_pilot_points`: 20
- K bounds: 10-600 m/d
- Variogram range: 600 m
- Anisotropy: -30 degrees x 3

## Kriging And Observation Lockstep

- `generate_conditioned_k_field(..., noise_std=0.25, variogram_range=3000.0, anisotropy_angle=-30.0, anisotropy_scaling=3.0)`
- `generate_synthetic_observations(..., n_points=5, noise_std=0.5)`

## Environment

{env_lines}

## Provenance

- Bundle date: {manifest["bundle_date"]}
- Source commit SHA: {manifest["commit_sha"]}
- Bundle version: {manifest["bundle_version"]}
"""


def _copy_and_strip(source: Path, staging_parent: Path, dry_run: bool) -> tuple[Path, list[Path]]:
    staged = staging_parent / "pest_setup"
    removals = [path for path in source.rglob("*") if path.is_file() and _should_strip(path)]
    if dry_run:
        return staged, removals

    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(source, staged)
    for path in removals:
        target = staged / path.relative_to(source)
        if target.exists():
            target.unlink()
    return staged, removals


def _validate_essentials(pest_setup: Path) -> None:
    missing = sorted(name for name in ESSENTIAL_FILES if not (pest_setup / name).exists())
    if missing:
        raise FileNotFoundError(
            "Source pest_setup is missing required bundle files: "
            + ", ".join(missing)
        )


def _write_zip(pest_setup: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(pest_setup.rglob("*")):
            if path.is_file():
                archive.write(path, Path("pest_setup") / path.relative_to(pest_setup))
    size = zip_path.stat().st_size
    if size > MAX_BUNDLE_BYTES:
        zip_path.unlink()
        raise ValueError(
            f"Bundle is {size / 1024 / 1024:.2f} MB, above the 2 MB sanity limit."
        )


def package_calibration(source: Path, output_dir: Path, dry_run: bool) -> tuple[Path, Path]:
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source.is_dir():
        raise NotADirectoryError(f"Source pest_setup does not exist: {source}")
    _validate_essentials(source)
    manifest = _build_manifest(source)

    if dry_run:
        staged, removals = _copy_and_strip(source, output_dir, dry_run=True)
        print(f"Would stage: {source} -> {staged}")
        print(f"Would strip {len(removals)} intermediate files.")
        for path in removals:
            print(f"  strip {path.relative_to(source)}")
        print(f"Would write {ZIP_NAME} and {README_NAME} in {output_dir}")
        print(json.dumps(manifest, indent=2))
        return output_dir / ZIP_NAME, output_dir / README_NAME

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="calibration_bundle_") as tmp:
        staged, removals = _copy_and_strip(source, Path(tmp), dry_run=False)
        (staged / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
        zip_path = output_dir / ZIP_NAME
        readme_path = output_dir / README_NAME
        _write_zip(staged, zip_path)
        readme_path.write_text(_readme_text(manifest))
    print(f"Stripped {len(removals)} intermediate files.")
    print(f"Wrote {zip_path} ({zip_path.stat().st_size / 1024:.1f} KB)")
    print(f"Wrote {readme_path}")
    return zip_path, readme_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Package a clean NB5 calibration/pest_setup workspace for Dropbox.",
    )
    parser.add_argument(
        "pest_setup",
        type=Path,
        help="Path to the calibration/pest_setup directory produced by NB5.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory for the zip and README. Defaults to the current directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report packaging actions without writing files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    package_calibration(args.pest_setup, args.output_dir, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
