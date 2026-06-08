"""Create tables and migrate legacy JSON files into the database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.db.database import DATA_DIR, Base, SessionLocal, engine
from src.db.models import DEFAULT_PRODUCT_CODE, LifecycleCounts, LifecycleLayout

LEGACY_LAYOUT = DATA_DIR / "lifecycle" / "layout.json"
LEGACY_COUNTS = DATA_DIR / "lifecycle" / "counts.json"


def _read_legacy_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _migrate_legacy_json(session) -> None:
    layout = _read_legacy_json(LEGACY_LAYOUT)
    if layout and session.get(LifecycleLayout, DEFAULT_PRODUCT_CODE) is None:
        session.add(
            LifecycleLayout(product_code=DEFAULT_PRODUCT_CODE, data=layout)
        )

    counts = _read_legacy_json(LEGACY_COUNTS)
    if counts and session.get(LifecycleCounts, DEFAULT_PRODUCT_CODE) is None:
        session.add(
            LifecycleCounts(product_code=DEFAULT_PRODUCT_CODE, data=counts)
        )

    session.commit()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        _migrate_legacy_json(session)
