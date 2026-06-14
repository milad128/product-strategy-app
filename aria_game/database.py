"""SQLite persistence for PROTOCOL: OVERRIDE game state."""

from __future__ import annotations

import copy
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "aria_game.db"

_lock = threading.Lock()


def _int_key_dict(raw: dict) -> dict:
    """Restore integer keys lost when state is round-tripped through JSON."""
    return {int(k): v for k, v in raw.items()}


def _normalize_state(state: dict) -> dict:
    if "layer_finish_order" in state:
        state["layer_finish_order"] = _int_key_dict(state["layer_finish_order"])
    for squad in state.get("squads", {}).values():
        if "passphrases" in squad:
            squad["passphrases"] = _int_key_dict(squad["passphrases"])
    act0 = state.get("act0")
    if act0 is not None:
        act0.setdefault("timed_out", False)
        act0.setdefault("shuffled", False)
        act0.setdefault("shuffle_narration_id", 0)
    mission = state.get("step_config", {}).get("mission")
    if mission and "passphrases" in mission:
        mission["passphrases"] = _int_key_dict(mission["passphrases"])
    if mission and "names" in mission:
        mission["names"] = _int_key_dict(mission["names"])
    if mission and "digit_scores_by_rank" in mission:
        mission["digit_scores_by_rank"] = _int_key_dict(mission["digit_scores_by_rank"])
    if "layer_digit_claims" in state:
        state["layer_digit_claims"] = _int_key_dict(state["layer_digit_claims"])
        for lyr, layer_claims in state["layer_digit_claims"].items():
            if isinstance(layer_claims, dict):
                state["layer_digit_claims"][lyr] = _int_key_dict(layer_claims)
    state.setdefault("layer_digit_claims", {lyr: {} for lyr in range(1, 6)})
    state.setdefault("score_event_id", 0)
    state.setdefault("last_score_event", {"id": 0, "type": "reward"})
    return state


def init_db() -> None:
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS game_snapshot (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()


def load_state(default: dict) -> dict:
    """Load persisted state or seed the database with defaults."""
    init_db()
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT data FROM game_snapshot WHERE id = 1"
        ).fetchone()
        conn.close()
    if row is None:
        save_state(default)
        return copy.deepcopy(default)
    return _normalize_state(json.loads(row[0]))


def save_state(state: dict) -> None:
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """
            INSERT INTO game_snapshot (id, data, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (
                json.dumps(state, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()
