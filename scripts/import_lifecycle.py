#!/usr/bin/env python3
"""Import lifecycle layout/counts JSON files into the database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.app.lifecycle.import_data import import_lifecycle_data  # noqa: E402
from src.db.init_db import init_db  # noqa: E402


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Import lifecycle JSON into SQLite")
    parser.add_argument("--layout", type=Path, help="Path to layout JSON file")
    parser.add_argument("--counts", type=Path, help="Path to counts JSON file")
    args = parser.parse_args()

    if not args.layout and not args.counts:
        parser.error("Provide --layout and/or --counts")

    init_db()
    layout = _load_json(args.layout) if args.layout else None
    counts = _load_json(args.counts) if args.counts else None
    result = import_lifecycle_data(layout=layout, counts=counts)
    print("Imported:", result["imported"], "for", result["product_code"])


if __name__ == "__main__":
    main()
