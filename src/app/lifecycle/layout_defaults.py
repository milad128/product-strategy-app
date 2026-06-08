"""Reference lifecycle layout matching the target BNPL diagram."""

from __future__ import annotations

import copy
from typing import Any

DEFAULT_BOARD_WIDTH = 1280
DEFAULT_BOARD_HEIGHT = 620
DEFAULT_CONN_LABEL = "Flow rate"
ARROW_BENT = "bent"
EP_STAGE = "stage"

DEFAULT_POSITIONS: dict[str, dict[str, float]] = {
    "rejected": {"x": 20, "y": 28},
    "applicant": {"x": 20, "y": 168},
    "abandoned": {"x": 20, "y": 308},
    "deadCreditHolder": {"x": 336, "y": 40},
    "freshCreditHolder": {"x": 284, "y": 176},
    "unActivatedCreditHolder": {"x": 284, "y": 336},
    "activeCustomer": {"x": 564, "y": 176},
    "dormantCustomer": {"x": 564, "y": 300},
    "softChurned": {"x": 564, "y": 424},
    "creditClosed": {"x": 864, "y": 40},
    "blackList": {"x": 1024, "y": 40},
}

DEFAULT_GROUP_BOUNDS: dict[str, dict[str, float]] = {
    "deadCreditHolderGroup": {"x": 304, "y": 8, "width": 196, "height": 108},
    "allocatedUser": {"x": 248, "y": 112, "width": 760, "height": 488},
    "liveCreditHolder": {"x": 268, "y": 148, "width": 240, "height": 320},
    "liveCustomer": {"x": 548, "y": 148, "width": 240, "height": 420},
    "deadCustomer": {"x": 832, "y": 8, "width": 400, "height": 108},
}

# from, to, label, optional transition rate (%)
DEFAULT_CONNECTIONS: list[dict[str, Any]] = [
    {"from": "applicant", "to": "rejected", "label": "Rejection rate", "rate": 30.0},
    {"from": "applicant", "to": "abandoned", "label": "Abandon Rate", "rate": 10.0},
    {"from": "abandoned", "to": "applicant", "label": "Re-Application rate"},
    {"from": "applicant", "to": "freshCreditHolder", "label": "Allocation rate", "rate": 60.0},
    {"from": "rejected", "to": "freshCreditHolder", "label": "Second Chance rate"},
    {
        "from": "freshCreditHolder",
        "to": "unActivatedCreditHolder",
        "label": "30-days Un-activation rate",
    },
    {"from": "freshCreditHolder", "to": "activeCustomer", "label": "Activation rate"},
    {
        "from": "unActivatedCreditHolder",
        "to": "activeCustomer",
        "label": "Activation Recover rate",
    },
    {"from": "freshCreditHolder", "to": "deadCreditHolder", "label": "Holder Close rate"},
    {"from": "deadCreditHolder", "to": "freshCreditHolder", "label": "Holder Revenant rate"},
    {"from": "activeCustomer", "to": "dormantCustomer", "label": "6M Dormancy rate"},
    {"from": "dormantCustomer", "to": "activeCustomer", "label": "Dormancy Re-activation rate"},
    {"from": "dormantCustomer", "to": "softChurned", "label": "Soft Churn rate"},
    {"from": "softChurned", "to": "activeCustomer", "label": "Soft Churn Win-back rate"},
    {"from": "activeCustomer", "to": "creditClosed", "label": "Customer Credit Close rate"},
    {"from": "activeCustomer", "to": "blackList", "label": "Hard Churn rate"},
    {"from": "creditClosed", "to": "activeCustomer", "label": "Customer Revenant rate"},
]


def ep_stage(stage_id: str) -> str:
    return f"{EP_STAGE}:{stage_id}"


def default_layout() -> dict[str, Any]:
    return {
        "boardBounds": {
            "x": 0,
            "y": 0,
            "width": DEFAULT_BOARD_WIDTH,
            "height": DEFAULT_BOARD_HEIGHT,
        },
        "positions": copy.deepcopy(DEFAULT_POSITIONS),
        "groupBounds": copy.deepcopy(DEFAULT_GROUP_BOUNDS),
        "customStages": [],
        "stageLabels": {},
        "hiddenStages": [],
        "connections": [
            {
                "id": f"conn-{i}",
                "from": ep_stage(c["from"]),
                "to": ep_stage(c["to"]),
                "label": c["label"],
                "routeType": ARROW_BENT,
                "fromOffset": 0.5,
                "toOffset": 0.5,
                "transitionRate": c.get("rate"),
            }
            for i, c in enumerate(DEFAULT_CONNECTIONS)
        ],
    }


def is_complete_layout(data: dict[str, Any] | None) -> bool:
    if not data or not isinstance(data, dict):
        return False
    positions = data.get("positions") or {}
    connections = data.get("connections")
    if len(positions) < len(DEFAULT_POSITIONS):
        return False
    if not isinstance(connections, list) or len(connections) < len(DEFAULT_CONNECTIONS):
        return False
    return True


def merge_layout(parsed: dict[str, Any] | None) -> dict[str, Any]:
    base = default_layout()
    if not parsed or not isinstance(parsed, dict):
        return base

    positions = parsed.get("positions")
    if isinstance(positions, dict):
        for key, pos in positions.items():
            if isinstance(pos, dict):
                base["positions"][key] = {
                    "x": float(pos.get("x") or 0),
                    "y": float(pos.get("y") or 0),
                }

    board_bounds = parsed.get("boardBounds")
    if isinstance(board_bounds, dict):
        base["boardBounds"] = {
            "x": float(board_bounds.get("x") or 0),
            "y": float(board_bounds.get("y") or 0),
            "width": max(200, float(board_bounds.get("width") or DEFAULT_BOARD_WIDTH)),
            "height": max(200, float(board_bounds.get("height") or DEFAULT_BOARD_HEIGHT)),
        }

    group_bounds = parsed.get("groupBounds")
    if isinstance(group_bounds, dict) and len(group_bounds) > 0:
        base["groupBounds"] = group_bounds

    stage_labels = parsed.get("stageLabels")
    if isinstance(stage_labels, dict):
        base["stageLabels"] = stage_labels

    hidden = parsed.get("hiddenStages")
    if isinstance(hidden, list):
        base["hiddenStages"] = [s for s in hidden if isinstance(s, str)]

    custom = parsed.get("customStages")
    if isinstance(custom, list):
        base["customStages"] = [
            {
                "id": s.get("id"),
                "label": s.get("label") or "New Stage",
                "shape": "circle" if s.get("shape") == "circle" else "rectangle",
                "count": s.get("count") if isinstance(s.get("count"), (int, float)) else 0,
            }
            for s in custom
            if isinstance(s, dict) and s.get("id")
        ]

    connections = parsed.get("connections")
    if isinstance(connections, list) and len(connections) > 0:
        base["connections"] = connections

    return base
