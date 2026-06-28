"""Persist lifecycle layout and stage counts in SQLite."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from src.app.lifecycle.layout_defaults import merge_layout
from src.app.lifecycle.monthly_import import parse_monthly_file
from src.db.database import SessionLocal
from src.db.models import (
    DEFAULT_PRODUCT_CODE,
    LifecycleCounts,
    LifecycleCountsMonthly,
    LifecycleLayout,
)


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


def list_count_months(product_code: str = DEFAULT_PRODUCT_CODE) -> list[str]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(LifecycleCountsMonthly.month)
            .where(LifecycleCountsMonthly.product_code == product_code)
            .order_by(LifecycleCountsMonthly.month)
        ).all()
        return list(rows)


def load_counts_month(
    month: str,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = session.get(LifecycleCountsMonthly, (product_code, month))
        return dict(row.data) if row else None


def save_counts_month(
    month: str,
    data: dict[str, Any],
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> None:
    with SessionLocal() as session:
        row = session.get(LifecycleCountsMonthly, (product_code, month))
        if row is None:
            session.add(
                LifecycleCountsMonthly(
                    product_code=product_code,
                    month=month,
                    data=data,
                )
            )
        else:
            row.data = data
        session.commit()
    save_counts(data, product_code=product_code)


def import_monthly_counts_file(
    filename: str,
    data: bytes,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> dict[str, Any]:
    monthly_data, warnings = parse_monthly_file(filename, data)
    if not monthly_data:
        raise ValueError("No monthly data found in file.")

    with SessionLocal() as session:
        for month, counts in monthly_data.items():
            row = session.get(LifecycleCountsMonthly, (product_code, month))
            if row is None:
                session.add(
                    LifecycleCountsMonthly(
                        product_code=product_code,
                        month=month,
                        data=counts,
                    )
                )
            else:
                row.data = counts
        session.commit()

    latest_month = max(monthly_data.keys())
    save_counts(monthly_data[latest_month], product_code=product_code)

    return {
        "status": "ok",
        "months": sorted(monthly_data.keys()),
        "imported": len(monthly_data),
        "latest_month": latest_month,
        "warnings": warnings,
    }


def load_counts(
    product_code: str = DEFAULT_PRODUCT_CODE,
    month: str | None = None,
) -> dict[str, Any] | None:
    if month:
        return load_counts_month(month, product_code=product_code)

    months = list_count_months(product_code)
    if months:
        return load_counts_month(months[-1], product_code=product_code)

    with SessionLocal() as session:
        row = session.get(LifecycleCounts, product_code)
        return dict(row.data) if row else None


def save_counts(
    data: dict[str, Any],
    product_code: str = DEFAULT_PRODUCT_CODE,
    month: str | None = None,
) -> None:
    if month:
        save_counts_month(month, data, product_code=product_code)
        return

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
