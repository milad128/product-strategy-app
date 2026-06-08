"""Import lifecycle data from browser export or JSON payload."""

from __future__ import annotations

from typing import Any

from src.app.lifecycle import storage as lifecycle_storage
from src.app.lifecycle.layout_defaults import is_complete_layout, merge_layout
from src.db.models import DEFAULT_PRODUCT_CODE


def import_lifecycle_data(
    layout: dict[str, Any] | None = None,
    counts: dict[str, Any] | None = None,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> dict[str, str]:
    imported: list[str] = []
    warnings: list[str] = []

    if layout is not None:
        if not isinstance(layout, dict):
            raise ValueError("layout must be a JSON object")
        if not is_complete_layout(layout):
            warnings.append(
                "Layout looks incomplete (missing stages or arrows). "
                "Open lifecycle.html in your old project, click Save, then import again."
            )
        merged = merge_layout(layout)
        lifecycle_storage.save_layout(merged, product_code=product_code)
        imported.append("layout")

    if counts is not None:
        if not isinstance(counts, dict):
            raise ValueError("counts must be a JSON object")
        lifecycle_storage.save_counts(counts, product_code=product_code)
        imported.append("counts")

    if not imported:
        raise ValueError("Nothing to import — provide layout and/or counts")

    result: dict[str, str] = {
        "status": "ok",
        "imported": ", ".join(imported),
        "product_code": product_code,
    }
    if warnings:
        result["warning"] = " ".join(warnings)
    return result
