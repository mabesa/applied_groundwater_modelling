"""Load the shipped FINE-GRID (1 m) transport result the teaching notebooks display.

Why this exists
---------------
The transport notebooks SHOW a 1 m result; students RUN the 10 m grid themselves, because
1 m takes hours and the Hub cannot carry it. **The gap between the two is the lesson** --
it is what demonstrates grid refinement effects.

So this module does not replace `build_srcpulse_demo`. The notebooks keep solving at 10 m
and load this alongside, to display the two together.

What it guarantees
------------------
* the archive is verified against :data:`CANONICAL_FINE_FINGERPRINT` before it is used --
  an unverified shipped artifact is what cost two days in 2026-08 (see
  `DOCUMENTATION/contracts/evidence/s3b/ROOT_CAUSE_MOTHER_MODEL_DRIFT.md`);
* if the download is unavailable, :func:`load_fine_result` returns ``None`` rather than
  raising, so a notebook can fall back to its 10 m run with a visible notice. It must
  never fall back SILENTLY -- the surrounding text quotes 1 m numbers.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

MEMBERS = ("srcpulse_fine_1m.npz", "srcpulse_fine_1m.json")
MANIFEST_NAME = "MANIFEST_transport.json"

#: Fingerprint of the shipped archive, printed by `package_fine_transport.py`.
#: Bump it together with the archive.
CANONICAL_FINE_FINGERPRINT = "49a1384a5115783b"

#: The name declared in config_template.py.
DOWNLOAD_NAME = "transport_fine_1m"


def _subdir() -> Path:
    from data_utils import get_default_data_folder
    return Path(get_default_data_folder()) / "transport_fine_1m"


def fingerprint(folder: Path) -> Optional[str]:
    """Content fingerprint of an extracted archive, or None if incomplete."""
    h = hashlib.sha256()
    for name in MEMBERS:
        p = folder / name
        if not p.is_file():
            return None
        h.update(name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _heal_download_entry() -> None:
    """Fill in this one download entry if the local `config.py` predates it.

    `config.py` is a ONE-TIME COPY of `config_template.py` (README), and `data_utils`
    falls back to the template only when `config.py` is ABSENT -- not when it exists but
    lacks a key. So anyone who set up before this archive shipped would silently get the
    10 m fallback instead of the fine-grid result the notebooks quote. Patch the single
    key in memory; never write to the user's config, and never touch other entries.

    An entry that IS present is left alone, so a deliberate URL override or an
    institutional mirror survives. It reads the ACTIVE `DATA_SOURCE`, so it cannot switch
    anyone to the template's default source.

    ⚠️ It cannot distinguish "predates the entry" from "deliberately removed to block this
    download". Omission is therefore NOT a supported way to disable it -- set the entry's
    url to None instead, which this leaves untouched.

    No try/except here on purpose: the only caller wraps this, and swallowing exceptions
    twice would hide a programming error as a missing download.
    """
    import data_utils as du
    urls = du.get_data_urls()
    if DOWNLOAD_NAME in urls:
        return
    import config_template as ct
    urls[DOWNLOAD_NAME] = ct.DATA_URLS[du.CASE_STUDY][du.DATA_SOURCE][DOWNLOAD_NAME]


def ensure_fine_result(dest: Optional[Path] = None) -> Optional[Path]:
    """Return the folder holding the shipped result, downloading it if needed.

    Returns ``None`` when it cannot be obtained -- the caller decides what to say.
    """
    folder = Path(dest) if dest else _subdir()
    if fingerprint(folder) == CANONICAL_FINE_FINGERPRINT:
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    try:
        from data_utils import download_named_file
        _heal_download_entry()
        zip_path = download_named_file(DOWNLOAD_NAME, dest_folder=str(folder))
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(folder)
    except Exception:                              # noqa: BLE001 - offline is a normal state
        return None
    return folder if fingerprint(folder) == CANONICAL_FINE_FINGERPRINT else None


def load_fine_result(dest: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """The shipped 1 m result as ``{times, breakthrough, **metrics}``, or ``None``.

    ``None`` means *say so in the notebook* -- print a notice and suppress the 1 m
    numbers rather than showing them beside a 10 m curve.
    """
    folder = ensure_fine_result(dest)
    if folder is None:
        return None
    import numpy as np
    z = np.load(folder / "srcpulse_fine_1m.npz")
    out: Dict[str, Any] = json.loads((folder / "srcpulse_fine_1m.json").read_text())
    out["times"] = z["times"]
    out["breakthrough"] = z["breakthrough"]
    return out


def verify(folder: Optional[Path] = None) -> Dict[str, Any]:
    """Report-only status, for diagnostics."""
    f = Path(folder) if folder else _subdir()
    actual = fingerprint(f)
    return {"folder": str(f), "fingerprint": actual,
            "canonical": CANONICAL_FINE_FINGERPRINT,
            "is_canonical": actual == CANONICAL_FINE_FINGERPRINT,
            "present": actual is not None}
