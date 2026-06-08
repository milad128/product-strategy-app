"""Persist lifecycle layout and stage counts in SQLite."""

from __future__ import annotations

from typing import Any

from src.app.lifecycle.layout_defaults import is_complete_layout, merge_layout
from src.db.database import SessionLocal
from src.db.models import DEFAULT_PRODUCT_CODE, LifecycleCounts, LifecycleLayout


def load_layout(product_code: str = DEFAULT_PRODUCT_CODE) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = session.get(LifecycleLayout, product_code)
        if not row:
            return None
        return merge_layout(dict(row.data))


def save_layout(data: dict[str, Any], product_code: str = DEFAULT_PRODUCT_CODE) -> None:
    with SessionLocal() as session:
        row = session.get(LifecycleLayout, product_code)
        if row is None:
            session.add(LifecycleLayout(product_code=product_code, data=data))
        else:
            row.data = data
        session.commit()


def load_counts(product_code: str = DEFAULT_PRODUCT_CODE) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = session.get(LifecycleCounts, product_code)
        return dict(row.data) if row else None


def save_counts(data: dict[str, Any], product_code: str = DEFAULT_PRODUCT_CODE) -> None:
    with SessionLocal() as session:
        row = session.get(LifecycleCounts, product_code)
        if row is None:
            session.add(LifecycleCounts(product_code=product_code, data=data))
        else:
            row.data = data
        session.commit()


def reset_layout_to_defaults(product_code: str = DEFAULT_PRODUCT_CODE) -> dict[str, Any]:
    merged = merge_layout(None)
    save_layout(merged, product_code=product_code)
    return merged
