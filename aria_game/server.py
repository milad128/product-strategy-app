"""PROTOCOL: OVERRIDE — ARIA Mission Control Server.

A small FastAPI app for the team-building game. It:
  * Serves the leaderboard HTML at /
  * Exposes one POST endpoint per "layer" (act). Squads must discover both
    the URL path *and* the correct passphrase as part of each act's puzzle.
  * Exposes /state for the leaderboard to poll (live updates).
  * Exposes /gm/* endpoints for the Game Master to start/pause the timer,
    reset, and adjust scores.

Run:
    pip install fastapi 'uvicorn[standard]' pydantic
    python aria_game/server.py
    # then open http://<host-ip>:8765/ on the projector laptop
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent

app = FastAPI(title="PROTOCOL: OVERRIDE — ARIA Mission Control")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# GAME CONFIG  —  Edit these to customize the game.
# ============================================================================

SQUADS: list[str] = ["VIPER", "FALCON", "GHOST", "CIPHER"]

# The 5 layers. Each one has:
#   * route: the URL path squads must DISCOVER during that act
#   * passphrase: the word they must POST in the body
#   * name: display name on the leaderboard
#
# IMPORTANT: change the routes and passphrases before the event. The squads
# will guess these from the in-game clues you give them.
LAYERS: dict[int, dict[str, str]] = {
    1: {"name": "FIREWALL", "route": "/api/firewall/breach",   "passphrase": "HUMANS"},
    2: {"name": "PROTOCOL", "route": "/api/protocol/inject",   "passphrase": "SHIP"},
    3: {"name": "SERVER",   "route": "/api/server/override",   "passphrase": "BETTER"},
    4: {"name": "SPRINT",   "route": "/api/sprint/deploy",     "passphrase": "TOGETHER"},
    5: {"name": "SHUTDOWN", "route": "/api/shutdown/execute",  "passphrase": "ALWAYS"},
}

POINTS_BY_RANK: dict[int, int] = {1: 3, 2: 2, 3: 1, 4: 0}

DEFAULT_TIMER_SECONDS: int = 3 * 60 * 60  # 3 hours


# ============================================================================
# STATE  —  in-memory; resets on server restart (use /gm/reset to wipe).
# ============================================================================

def _fresh_squad_state() -> dict:
    return {
        "passphrases": {layer: None for layer in LAYERS},
        "score": 0,
        "tokens": 2,
    }


state: dict = {
    "squads": {s: _fresh_squad_state() for s in SQUADS},
    "layer_finish_order": {layer: [] for layer in LAYERS},
    "timer": {
        "started_at": None,
        "duration_seconds": DEFAULT_TIMER_SECONDS,
        "paused_at": None,
        "paused_elapsed": 0.0,
    },
    "transmissions": [],
    "game_over": False,
    "winner": None,
}


# ============================================================================
# Models
# ============================================================================

class Submission(BaseModel):
    squad: str
    passphrase: str


class TimerConfig(BaseModel):
    duration_seconds: int


class AdjustScore(BaseModel):
    squad: str
    delta: int
    reason: str = ""


# ============================================================================
# Helpers
# ============================================================================

def add_transmission(message: str, severity: str = "info") -> None:
    state["transmissions"].insert(
        0,
        {
            "time": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "severity": severity,
        },
    )
    state["transmissions"] = state["transmissions"][:30]


def submit(layer: int, payload: Submission):
    squad = payload.squad.upper().strip()
    if squad not in SQUADS:
        add_transmission(
            f"UNAUTHORIZED ACCESS ATTEMPT :: '{payload.squad}'", "danger"
        )
        raise HTTPException(403, detail=f"Squad '{payload.squad}' not recognized.")

    if state["squads"][squad]["passphrases"][layer] is not None:
        raise HTTPException(
            409, detail=f"Layer {layer} already cleared by {squad}."
        )

    expected = LAYERS[layer]["passphrase"].upper().strip()
    submitted = payload.passphrase.upper().strip()

    if submitted != expected:
        add_transmission(
            f"{squad} :: Layer {layer} REJECTED :: '{payload.passphrase}'",
            "warn",
        )
        return JSONResponse(
            status_code=403,
            content={
                "status": "denied",
                "aria": (
                    f"Incorrect. ARIA does not yield. "
                    f"'{payload.passphrase}' is not the key for Layer {layer}."
                ),
            },
        )

    state["squads"][squad]["passphrases"][layer] = expected
    rank = len(state["layer_finish_order"][layer]) + 1
    state["layer_finish_order"][layer].append(squad)
    points = POINTS_BY_RANK.get(rank, 0)
    state["squads"][squad]["score"] += points

    add_transmission(
        f"{squad} :: Layer {layer} ({LAYERS[layer]['name']}) BREACHED "
        f":: +{points} pts (rank #{rank})",
        "success",
    )

    if all(
        state["squads"][squad]["passphrases"][lyr] is not None for lyr in LAYERS
    ):
        if state["winner"] is None:
            state["winner"] = squad
            state["game_over"] = True
            add_transmission(
                f"PROTOCOL OVERRIDE EXECUTED BY {squad} :: ARIA SHUTDOWN COMPLETE",
                "success",
            )

    return {
        "status": "accepted",
        "aria": (
            f"Acknowledged. Layer {layer} breached by {squad}. "
            f"Rank #{rank}. +{points} points."
        ),
        "rank": rank,
        "points": points,
    }


def compute_timer_remaining() -> tuple[int, bool, bool]:
    timer = state["timer"]
    if timer["started_at"] is None and timer["paused_at"] is None:
        return timer["duration_seconds"], False, False
    if timer["paused_at"] is not None:
        elapsed = timer["paused_elapsed"]
        running = False
    else:
        elapsed = time.time() - timer["started_at"] + timer["paused_elapsed"]
        running = True
    remaining = max(0, int(timer["duration_seconds"] - elapsed))
    return remaining, running, True


# ============================================================================
# Public endpoints
# ============================================================================

@app.get("/")
async def leaderboard():
    return FileResponse(HERE / "leaderboard.html")


@app.get("/state")
async def get_state():
    remaining, running, started = compute_timer_remaining()
    return {
        "squads": [
            {
                "name": s,
                "passphrases": [
                    state["squads"][s]["passphrases"][lyr] for lyr in sorted(LAYERS)
                ],
                "score": state["squads"][s]["score"],
                "tokens": state["squads"][s]["tokens"],
            }
            for s in SQUADS
        ],
        "layers": [
            {
                "id": lyr,
                "name": LAYERS[lyr]["name"],
                "letters": len(LAYERS[lyr]["passphrase"]),
            }
            for lyr in sorted(LAYERS)
        ],
        "transmissions": state["transmissions"][:15],
        "timer": {
            "remaining_seconds": remaining,
            "running": running,
            "started": started,
        },
        "game_over": state["game_over"],
        "winner": state["winner"],
    }


# ----- Layer submission endpoints (one per act) -----
# The squads must DISCOVER these URL paths via in-game clues; the leaderboard
# does not display them.

@app.post(LAYERS[1]["route"])
async def submit_layer_1(payload: Submission):
    return submit(1, payload)


@app.post(LAYERS[2]["route"])
async def submit_layer_2(payload: Submission):
    return submit(2, payload)


@app.post(LAYERS[3]["route"])
async def submit_layer_3(payload: Submission):
    return submit(3, payload)


@app.post(LAYERS[4]["route"])
async def submit_layer_4(payload: Submission):
    return submit(4, payload)


@app.post(LAYERS[5]["route"])
async def submit_layer_5(payload: Submission):
    return submit(5, payload)


# ============================================================================
# Game Master endpoints
# ============================================================================

@app.post("/gm/timer/start")
async def gm_timer_start():
    state["timer"]["started_at"] = time.time()
    state["timer"]["paused_at"] = None
    state["timer"]["paused_elapsed"] = 0.0
    add_transmission("MISSION TIMER STARTED :: COUNTDOWN INITIATED", "info")
    return {"status": "started"}


@app.post("/gm/timer/pause")
async def gm_timer_pause():
    timer = state["timer"]
    if timer["started_at"] is not None and timer["paused_at"] is None:
        timer["paused_elapsed"] += time.time() - timer["started_at"]
        timer["paused_at"] = time.time()
        timer["started_at"] = None
        add_transmission("MISSION TIMER PAUSED", "warn")
    return {"status": "paused"}


@app.post("/gm/timer/resume")
async def gm_timer_resume():
    timer = state["timer"]
    if timer["paused_at"] is not None:
        timer["started_at"] = time.time()
        timer["paused_at"] = None
        add_transmission("MISSION TIMER RESUMED", "info")
    return {"status": "resumed"}


@app.post("/gm/timer/reset")
async def gm_timer_reset():
    duration = state["timer"]["duration_seconds"]
    state["timer"] = {
        "started_at": None,
        "duration_seconds": duration,
        "paused_at": None,
        "paused_elapsed": 0.0,
    }
    add_transmission("MISSION TIMER RESET", "info")
    return {"status": "reset"}


@app.post("/gm/timer/configure")
async def gm_timer_configure(config: TimerConfig):
    state["timer"]["duration_seconds"] = max(0, int(config.duration_seconds))
    add_transmission(
        f"TIMER DURATION SET :: {config.duration_seconds}s", "info"
    )
    return {"status": "ok", "duration_seconds": state["timer"]["duration_seconds"]}


@app.post("/gm/score/adjust")
async def gm_adjust_score(adj: AdjustScore):
    squad = adj.squad.upper().strip()
    if squad not in SQUADS:
        raise HTTPException(404, detail=f"Squad '{adj.squad}' not found.")
    state["squads"][squad]["score"] += adj.delta
    sign = "+" if adj.delta >= 0 else ""
    reason = f" ({adj.reason})" if adj.reason else ""
    add_transmission(
        f"GM ADJUSTMENT :: {squad} {sign}{adj.delta}{reason}", "info"
    )
    return {"status": "ok", "new_score": state["squads"][squad]["score"]}


@app.post("/gm/transmission")
async def gm_post_transmission(payload: dict):
    """Push an arbitrary ARIA message to the leaderboard log."""
    msg = str(payload.get("message", "")).strip()
    severity = str(payload.get("severity", "info")).strip() or "info"
    if not msg:
        raise HTTPException(400, detail="message is required")
    add_transmission(msg, severity)
    return {"status": "ok"}


@app.post("/gm/reset")
async def gm_reset():
    """Wipe all squad progress, scores, and the transmission log."""
    duration = state["timer"]["duration_seconds"]
    for s in SQUADS:
        state["squads"][s] = _fresh_squad_state()
    for lyr in LAYERS:
        state["layer_finish_order"][lyr] = []
    state["transmissions"] = []
    state["timer"] = {
        "started_at": None,
        "duration_seconds": duration,
        "paused_at": None,
        "paused_elapsed": 0.0,
    }
    state["game_over"] = False
    state["winner"] = None
    add_transmission("FULL SYSTEM RESET :: STATE CLEARED", "info")
    return {"status": "reset"}


@app.get("/gm/routes")
async def gm_routes():
    """Game Master cheat sheet — returns all secret routes + passphrases."""
    return {
        "layers": [
            {
                "id": lyr,
                "name": LAYERS[lyr]["name"],
                "route": LAYERS[lyr]["route"],
                "passphrase": LAYERS[lyr]["passphrase"],
            }
            for lyr in sorted(LAYERS)
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
