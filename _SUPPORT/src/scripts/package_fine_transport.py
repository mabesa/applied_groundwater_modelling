"""Package the shipped FINE-GRID (1 m) transport result for the teaching notebooks.

The transport notebooks display a 1 m result we precompute; students run the 10 m grid
themselves. The gap between the two is the teaching point. This packages the 1 m result
so `transport_shipped_results.ensure_fine_result()` can fetch it.

Produces `limmat_transport_fine_1m.zip` containing:
    srcpulse_fine_1m.npz    breakthrough curve (times, concentrations)
    srcpulse_fine_1m.json   the metrics the notebooks quote
    MANIFEST_transport.json fingerprint + provenance

Usage
-----
    uv run python _SUPPORT/src/scripts/package_fine_transport.py \
        --source <dir with the two files> [--output <dir>]

After it prints the fingerprint, upload the zip to Dropbox and set
`transport_fine_1m.url` in config_template.py, and paste the fingerprint into
`transport_shipped_results.CANONICAL_FINE_FINGERPRINT`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

MEMBERS = ("srcpulse_fine_1m.npz", "srcpulse_fine_1m.json")
MANIFEST_NAME = "MANIFEST_transport.json"
ARCHIVE_VERSION = 1


def fingerprint(source: Path) -> str:
    """Content fingerprint of the shipped members, order-independent of the filesystem."""
    h = hashlib.sha256()
    for name in MEMBERS:                      # fixed order, not directory order
        p = source / name
        h.update(name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    source = args.source.expanduser().resolve()
    missing = [m for m in MEMBERS if not (source / m).is_file()]
    if missing:
        print(f"ERROR: missing in {source}: {missing}", file=sys.stderr)
        return 1

    metrics = json.loads((source / "srcpulse_fine_1m.json").read_text())
    fp = fingerprint(source)
    manifest = {
        "archive_version": ARCHIVE_VERSION,
        "transport_fingerprint": fp,
        "cell_size_m": metrics["cell_size_m"],
        "peak_mgL": metrics["peak_mgL"],
        "t_peak": metrics["t_peak"],
        "ncpl": metrics["ncpl"],
        "nstp": metrics["nstp"],
        "what": "fine-grid transport result displayed by the teaching notebooks; "
                "students run the coarse grid themselves",
    }
    (source / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")

    out_dir = (args.output or source).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "limmat_transport_fine_1m.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in (*MEMBERS, MANIFEST_NAME):
            zf.write(source / name, arcname=name)

    print(f"wrote {zip_path}  ({zip_path.stat().st_size/1024:.0f} KB)")
    print(f"  transport_fingerprint : {fp}")
    print(f"  peak {metrics['peak_mgL']:.4f} mg/L   arrival {metrics['t_peak']:.2f} d "
          f"  ncpl {metrics['ncpl']}  nstp {metrics['nstp']}")
    print()
    print("NEXT (manual): upload the zip, then set")
    print("  config_template.py  -> transport_fine_1m.url")
    print(f"  transport_shipped_results.CANONICAL_FINE_FINGERPRINT = \"{fp}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
