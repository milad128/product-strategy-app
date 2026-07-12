"""Persist lifecycle layout and stage counts in SQLite."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from src.app.lifecycle.layout_defaults import merge_layout
from src.app.lifecycle.monthly_import import parse_monthly_file
from src.app.lifecycle.transition_import import parse_transition_probs_xlsx
from src.db.database import SessionLocal
from src.db.models import (
    DEFAULT_PRODUCT_CODE,
    LifecycleCounts,
    LifecycleCountsMonthly,
    LifecycleLayout,
    LifecycleTransitionProbsMonthly,
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


def list_transition_prob_months(product_code: str = DEFAULT_PRODUCT_CODE) -> list[str]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(LifecycleTransitionProbsMonthly.month)
            .where(LifecycleTransitionProbsMonthly.product_code == product_code)
            .order_by(LifecycleTransitionProbsMonthly.month)
        ).all()
        return list(rows)


def load_transition_probs_month(
    month: str,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = session.get(LifecycleTransitionProbsMonthly, (product_code, month))
        return dict(row.data) if row else None


def save_transition_probs_month(
    month: str,
    matrix: dict[str, Any],
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> None:
    with SessionLocal() as session:
        row = session.get(LifecycleTransitionProbsMonthly, (product_code, month))
        if row is None:
            session.add(
                LifecycleTransitionProbsMonthly(
                    product_code=product_code, month=month, data=matrix
                )
            )
        else:
            row.data = matrix
        session.commit()


def _match_existing_connections(
    layout: dict[str, Any], matrix: dict[str, dict[str, float]]
) -> tuple[int, int]:
    """Count matrix cells that do / don't correspond to an existing arrow
    on the canvas. Cells with no matching arrow are left out of the saved
    matrix entirely — they never get drawn and never show a rate."""
    existing = {(c["from"], c["to"]) for c in layout.get("connections", [])}
    matched = 0
    skipped = 0
    for from_id, targets in list(matrix.items()):
        for to_id in list(targets.keys()):
            pair = (f"stage:{from_id}", f"stage:{to_id}")
            if pair in existing:
                matched += 1
            else:
                skipped += 1
                del targets[to_id]
        if not targets:
            del matrix[from_id]
    return matched, skipped


def import_transition_probs_file(
    filename: str,
    data: bytes,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> dict[str, Any]:
    month, matrix = parse_transition_probs_xlsx(filename, data)
    if not matrix:
        raise ValueError("No recognized stage transitions found in file.")

    layout = load_layout(product_code=product_code) or merge_layout(None)
    matched, skipped = _match_existing_connections(layout, matrix)

    save_transition_probs_month(month, matrix, product_code=product_code)

    return {
        "status": "ok",
        "month": month,
        "pairs": matched,
        "skipped_pairs": skipped,
    }
