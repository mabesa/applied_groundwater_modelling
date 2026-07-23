"""Package the calibrated MF6 flow model into the shipped `flow_model_mf6` archive.

Produces `limmat_valley_calibrated_flow_model.zip` (the artifact
`ensure_flow_model()` downloads into `<data>/limmat/calibration/`) plus a
`MANIFEST_flow.json` stamped with the flow-model fingerprint, total pumping,
mean K, and an archive version. The manifest lets `ensure_flow_model()` refuse a
stale/mismatched local workspace instead of silently serving the old flow field.

This is the flow-model counterpart of `package_calibration.py` (which packages the
separate PEST *bundle*).

Usage
-----
    uv run python _SUPPORT/src/scripts/package_flow_model.py \
        [--source <data>/limmat/calibration] [--output <dir>] [--dry-run]

After it prints the fingerprint + pumping, upload the zip to Dropbox and update
`flow_model_mf6.url` (+ readme) in config_template.py.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np  # noqa: E402
import flopy  # noqa: E402
import model_io_utils as mio  # noqa: E402

ARCHIVE_NAME = "limmat_valley_calibrated_flow_model.zip"
# Files/dirs in the calibration workspace that are NOT part of the flow-model archive.
_EXCLUDE_SUFFIXES = (".gpkg", ".zip", ".md")
_EXCLUDE_DIRS = ("pest_setup", "pumping_test", "k_sensitivity")


def _commit_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _mf6_version() -> str:
    import shutil
    exe = os.environ.get("MF6") or shutil.which("mf6") or \
        os.path.expanduser("~/.local/share/flopy/bin/mf6")
    try:
        return subprocess.run([exe, "-v"], capture_output=True, text=True).stdout.strip()[:40]
    except Exception:
        return "unknown"


def _model_files(source: Path) -> list[Path]:
    return sorted(
        p for p in source.iterdir()
        if p.is_file()
        and p.suffix.lower() not in _EXCLUDE_SUFFIXES
        and p.name != mio._FLOW_MANIFEST_NAME
    )


def _mean_k(source: Path) -> float:
    sim = flopy.mf6.MFSimulation.load(sim_ws=str(source), load_only=["disv", "npf"],
                                      verbosity_level=0)
    return float(np.mean(sim.get_model(sim.model_names[0]).npf.k.array))


def build_manifest(source: Path) -> dict:
    return {
        "archive_version": mio.FLOW_MODEL_MIN_VERSION,
        "flow_fingerprint": mio.flow_model_fingerprint(source),
        "pumping_m3d": round(mio.flow_model_pumping_m3d(source), 1),
        "mean_K_md": round(_mean_k(source), 1),
        "commit_sha": _commit_sha(),
        "mf6_version": _mf6_version(),
        "flopy_version": flopy.__version__,
    }


def package_flow_model(source: Path, output_dir: Path, dry_run: bool = False) -> tuple[Path, dict]:
    source = Path(source); output_dir = Path(output_dir)
    if not (source / "mfsim.nam").exists():
        raise FileNotFoundError(f"No mfsim.nam in {source} — is this an MF6 workspace?")
    manifest = build_manifest(source)
    files = _model_files(source)
    zip_path = output_dir / ARCHIVE_NAME
    print(f"Flow-model archive manifest:\n{json.dumps(manifest, indent=2)}")
    print(f"\n{len(files)} model files -> {zip_path}")
    if dry_run:
        print("(dry run — nothing written)")
        return zip_path, manifest
    output_dir.mkdir(parents=True, exist_ok=True)
    # write the manifest into the workspace so it ships inside the zip (and lands
    # in <data>/calibration after unzip, where ensure_flow_model() reads it)
    (source / mio._FLOW_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files + [source / mio._FLOW_MANIFEST_NAME]:
            zf.write(p, arcname=p.name)  # flat: mfsim.nam at archive root
    print(f"Wrote {zip_path} ({zip_path.stat().st_size/1e6:.1f} MB)")
    return zip_path, manifest


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default=None,
                   help="Calibrated MF6 workspace (default <data>/limmat/calibration)")
    p.add_argument("--output", default=".", help="Output dir for the zip (default cwd)")
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    source = args.source
    if source is None:
        from data_utils import get_default_data_folder
        source = Path(get_default_data_folder()) / "calibration"
    package_flow_model(Path(source), Path(args.output), args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
