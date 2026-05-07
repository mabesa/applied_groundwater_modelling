#!/usr/bin/env python3
"""Preprocess repository files before Lychee extracts links."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _source_to_text(source: Any) -> str:
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    if isinstance(source, str):
        return source
    return ""


def _emit_notebook(path: Path) -> None:
    with path.open(encoding="utf-8") as stream:
        notebook = json.load(stream)

    for index, cell in enumerate(notebook.get("cells", []), start=1):
        source = _source_to_text(cell.get("source", ""))
        if source:
            print(f"\n<!-- notebook cell {index} -->")
            print(source)


def _emit_text(path: Path) -> None:
    sys.stdout.write(path.read_text(encoding="utf-8", errors="ignore"))


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: lychee-preprocess.py PATH", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if path.suffix == ".ipynb":
        _emit_notebook(path)
    else:
        _emit_text(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
