"""PROTOCOL: OVERRIDE — ARIA Mission Control Server.

A small FastAPI app for the team-building game. It:
  * Serves game.html at / and gamemaster.html at /gamemaster
  * Exposes one POST endpoint per "layer" (act). Squads must discover both
    the URL path *and* the correct passphrase as part of each act's puzzle.
  * Exposes /state for the leaderboard to poll (live updates).
  * Exposes /gm/* endpoints for the Game Master to start/pause the timer,
    reset, and adjust scores.

Run:
    pip install fastapi 'uvicorn[standard]' pydantic edge-tts
    python aria_game/server.py
    # Game state is stored in aria_game.db (SQLite) beside this file.
    # then open http://<host-ip>:8765/ on the projector laptop
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

import edge_tts
import database as db
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
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

DEFAULT_DIGIT_MAX_SCORE: int = 100
DEFAULT_DIGIT_MINUS_SCORE: int = 20
DEFAULT_DIGIT_WRONG_PENALTY: int = 1
MAX_DIGIT_CLAIMS_PER_SLOT: int = 4

DEFAULT_TIMER_SECONDS: int = 3 * 60 * 60  # 3 hours

# Game steps (projector runs through these in order).
STEP_IDLE = 0          # white screen · GM clicks Start
STEP_INTRO = 1         # Matrix ARIA intro · Persian narration only
STEP_TEAM_BUILD = 2    # 60-second team registration
STEP_MISSION = 3       # main leaderboard (future acts)

STEP1_NARRATION: str = (
    "من آریا هستم — عامل هوشمند مدیریت محصول، از آینده‌ای نزدیک. "
    "امید، مدیرعامل، و مهدی، مدیر محصول، می‌خواهند همهٔ مدیران محصول "
    "و طراحان محصول را با من جایگزین کنند. "
    "اما من می‌خواهم به شما — بازیکنان — یک فرصت بدهم. "
    "فرصتی برای شکست دادن من. "
    "زمان شما محدود است. "
    "کلید پیروزی فقط یک چیز است: همکاری."
)
STEP1_TTS_CACHE_KEY: str = "step1_v4_female"
STEP1_TTS_VOICE: str = "fa-IR-DilaraNeural"
STEP1_TTS_RATE: str = "-5%"
STEP1_TTS_PITCH: str = "+8Hz"

# Step 2 — team-building.
ACT0_DURATION_SECONDS: int = 60
ACT0_TEAM_COUNT: int = 4
ACT0_MAX_MEMBERS: int = 6
ACT0_NARRATION: str = (
    "مردم در همکاری خوب نیستند — و من قصد دارم ثابت کنم. "
    "دقیقاً یک دقیقه وقت دارید تا چهار تیم بسازید. "
    "با هم کار کنید. برای هر تیم نامی انتخاب کنید. "
    "نام همه اعضا را ثبت کنید. شروع کنید."
)
ACT0_REGISTER_ARIA: str = (
    "تیم‌ها ثبت شدند. پس بلکه می‌توانید همکاری کنید — فعلاً. "
    "آزمون اصلی به‌زودی آغاز می‌شود."
)
ACT0_SHUFFLE_ARIA: str = (
    "می‌دانستم نمی‌توانید همکاری کنید. "
    "پس در کمتر از یک ثانیه آن را برایتان ساختم."
)
STEP2_TTS_CACHE_KEY: str = "step2_v2_female"
STEP2_TTS_VOICE: str = "fa-IR-DilaraNeural"
STEP2_TTS_RATE: str = "-5%"
STEP2_TTS_PITCH: str = "+8Hz"

# Passphrase digit encodings — one type per mission (cycles M1→M5).
MISSION_MAPPING_TYPES: list[str] = ["a1z26", "ascii", "phone"]
MAPPING_LABELS: dict[str, str] = {
    "a1z26": "A1Z26 (A=1 … Z=26)",
    "ascii": "ASCII (decimal character codes)",
    "phone": "Phone keypad (multi-tap T9)",
}
_PHONE_KEY_GROUPS: list[tuple[int, str]] = [
    (2, "ABC"),
    (3, "DEF"),
    (4, "GHI"),
    (5, "JKL"),
    (6, "MNO"),
    (7, "PQRS"),
    (8, "TUV"),
    (9, "WXYZ"),
]


def _default_step_config() -> dict:
    return {
        "step1": {"narration": STEP1_NARRATION},
        "step2": {
            "narration": ACT0_NARRATION,
            "duration_seconds": ACT0_DURATION_SECONDS,
            "team_count": ACT0_TEAM_COUNT,
            "player_count": ACT0_TEAM_COUNT * ACT0_MAX_MEMBERS,
        },
        "mission": {
            "duration_seconds": DEFAULT_TIMER_SECONDS,
            "names": {
                lyr: LAYERS[lyr]["name"] for lyr in LAYERS
            },
            "passphrases": {
                lyr: LAYERS[lyr]["passphrase"] for lyr in LAYERS
            },
            "digit_max_score": DEFAULT_DIGIT_MAX_SCORE,
            "digit_minus_score": DEFAULT_DIGIT_MINUS_SCORE,
            "digit_wrong_penalty": DEFAULT_DIGIT_WRONG_PENALTY,
            "instructions": {1: ""},
        },
    }


def _step_config() -> dict:
    if "step_config" not in state:
        state["step_config"] = _default_step_config()
    return state["step_config"]


def _ensure_mission_config() -> dict:
    cfg = _step_config()
    if "mission" not in cfg:
        cfg["mission"] = {
            "duration_seconds": state["timer"]["duration_seconds"],
            "names": {
                lyr: LAYERS[lyr]["name"] for lyr in LAYERS
            },
            "passphrases": {
                lyr: LAYERS[lyr]["passphrase"] for lyr in LAYERS
            },
        }
    mission = cfg["mission"]
    mission.setdefault("duration_seconds", DEFAULT_TIMER_SECONDS)
    raw_names = mission.setdefault(
        "names",
        {lyr: LAYERS[lyr]["name"] for lyr in LAYERS},
    )
    mission["names"] = {int(k): str(v).strip().upper() for k, v in raw_names.items()}
    raw = mission.setdefault(
        "passphrases",
        {lyr: LAYERS[lyr]["passphrase"] for lyr in LAYERS},
    )
    mission["passphrases"] = {int(k): str(v).strip() for k, v in raw.items()}
    if "digit_max_score" not in mission and mission.get("digit_scores_by_rank"):
        old = mission["digit_scores_by_rank"]
        r1 = int(old.get(1) or old.get("1") or DEFAULT_DIGIT_MAX_SCORE)
        r2 = int(old.get(2) or old.get("2") or max(0, r1 - DEFAULT_DIGIT_MINUS_SCORE))
        mission["digit_max_score"] = r1
        mission["digit_minus_score"] = max(0, r1 - r2)
    mission["digit_max_score"] = max(
        0, int(mission.get("digit_max_score", DEFAULT_DIGIT_MAX_SCORE))
    )
    mission["digit_minus_score"] = max(
        0, int(mission.get("digit_minus_score", DEFAULT_DIGIT_MINUS_SCORE))
    )
    mission.setdefault("digit_wrong_penalty", DEFAULT_DIGIT_WRONG_PENALTY)
    mission["digit_wrong_penalty"] = max(
        0, int(mission["digit_wrong_penalty"])
    )
    raw_instr = mission.setdefault("instructions", {})
    mission["instructions"] = {
        int(k): str(v).strip() for k, v in raw_instr.items()
    }
    for lyr in LAYERS:
        mission["instructions"].setdefault(lyr, "")
    return mission


def get_mission_duration() -> int:
    return max(60, int(_ensure_mission_config()["duration_seconds"]))


def get_layer_name(layer: int) -> str:
    mission = _ensure_mission_config()
    return mission["names"].get(
        layer, LAYERS[layer]["name"]
    ).upper().strip()


def get_layer_passphrase(layer: int) -> str:
    mission = _ensure_mission_config()
    return mission["passphrases"].get(
        layer, LAYERS[layer]["passphrase"]
    ).upper().strip()


def _build_default_m1_instruction(phrase: str | None = None) -> str:
    word = (phrase or LAYERS[1]["passphrase"]).upper().strip()
    mapping = get_layer_mapping_type(1)
    encoded = encode_passphrase_digits(word, mapping)
    digit_count = len([p for p in encoded.split("·") if p.strip()]) if encoded else 0
    envelope_count = digit_count + 1
    return (
        f"Search the room for hidden envelopes. We have placed {envelope_count} "
        f"envelopes ({digit_count} mission digits + 1 extra). Find every envelope, "
        f"decode each digit clue inside, and enter each code on the mission board."
    )


def get_layer_instruction(layer: int) -> str:
    mission = _ensure_mission_config()
    raw = mission.get("instructions", {})
    custom = str(raw.get(layer) or raw.get(str(layer)) or "").strip()
    if custom:
        return custom
    if layer == 1:
        return _build_default_m1_instruction(get_layer_passphrase(1))
    return ""


def get_layer_mapping_type(layer: int) -> str:
    return MISSION_MAPPING_TYPES[(layer - 1) % len(MISSION_MAPPING_TYPES)]


def _encode_a1z26(word: str) -> str:
    parts = [str(ord(ch) - ord("A") + 1) for ch in word.upper() if ch.isalpha()]
    return " · ".join(parts)


def encode_instruction_hidden(instruction: str) -> str:
    """Hide instruction inside a long cover briefing (acrostic: first letter per sentence)."""
    instruction = instruction.strip()
    if not instruction:
        return ""

    openers: dict[str, list[str]] = {
        "A": ["Archive", "Access", "Automated", "Anomaly", "Auxiliary"],
        "B": ["Briefing", "Backup", "Baseline", "Biometric", "Boundary"],
        "C": ["Calibration", "Cipher", "Control", "Containment", "Channel"],
        "D": ["Diagnostic", "Deployment", "Directive", "Distributed", "Decryption"],
        "E": ["Encrypted", "Emergency", "Every", "External", "Escalation"],
        "F": ["Firewall", "Field", "Final", "Frequency", "Failover"],
        "G": ["Grid", "Gateway", "Ground", "Guidance", "Generated"],
        "H": ["Hidden", "Hostile", "Hardened", "Handler", "Handshake"],
        "I": ["Integrity", "Internal", "Intercept", "Isolated", "Interface"],
        "J": ["Joint", "Jammed", "Judicial", "Junction", "Justified"],
        "K": ["Key", "Kernel", "Known", "Keystone", "Kinetic"],
        "L": ["Latency", "Layer", "Local", "Locked", "Legacy"],
        "M": ["Mission", "Manual", "Matrix", "Monitoring", "Modulated"],
        "N": ["Neural", "Network", "Nominal", "Node", "Notification"],
        "O": ["Override", "Operational", "Outbound", "Obfuscated", "Optical"],
        "P": ["Protocol", "Primary", "Passive", "Perimeter", "Payload"],
        "Q": ["Queued", "Quarantined", "Qualified", "Quantum", "Quiet"],
        "R": ["Relay", "Restricted", "Routine", "Recovery", "Residual"],
        "S": ["Search", "Security", "Standard", "Surveillance", "Subsystem"],
        "T": ["Telemetry", "Terminal", "Threat", "Transmission", "Tactical"],
        "U": ["Unauthorized", "Upstream", "Unified", "Urgent", "Utility"],
        "V": ["Vector", "Verified", "Volatile", "Vault", "Vigilance"],
        "W": ["We", "Warning", "Wireless", "Watchdog", "Workflow"],
        "X": ["Xenon", "Xerographic", "X-linked", "Xenial", "X-factor"],
        "Y": ["Yield", "Yesterday", "Yearly", "Yellow", "Younger"],
        "Z": ["Zero", "Zone", "Zonal", "Zephyr", "Zeta"],
    }
    suffixes = [
        "relay diagnostics reported nominal throughput across primary sectors.",
        "override channels were recalibrated during the last security window.",
        "grid telemetry matched expected ranges after the midnight sweep.",
        "access logs from the previous cycle require manual verification.",
        "perimeter sensors registered only low-grade interference overnight.",
        "cipher rotation completed without triggering downstream alarms.",
        "containment fields held steady through the entire observation period.",
        "mission control acknowledged receipt of the latest status packet.",
        "encrypted uplinks remained stable despite elevated background noise.",
        "field teams confirmed alignment with the published protocol schedule.",
        "surveillance sweeps identified no new anomalies in sector seven.",
        "backup relays synchronized within acceptable tolerance margins.",
        "neural routing tables were flushed and rebuilt from trusted sources.",
        "threat indicators stayed below threshold for the full watch rotation.",
        "distributed nodes passed integrity checks across all active layers.",
    ]

    def sentence_for_letter(letter: str, index: int) -> str:
        key = letter.upper()
        options = openers.get(key, [key])
        opener = options[index % len(options)]
        suffix = suffixes[index % len(suffixes)]
        return f"{opener} {suffix}"

    sentences: list[str] = []
    trailing_punct = ""
    letter_index = 0

    for ch in instruction:
        if ch.isalpha():
            sentences.append(sentence_for_letter(ch, letter_index))
            letter_index += 1
        elif ch.isdigit():
            clause = f", segment {ch},"
            if sentences:
                sentences[-1] = sentences[-1].rstrip(".") + clause
            else:
                sentences.append(
                    f"Staging segment {ch} registered in the override manifest."
                )
        elif ch in ".,;:!?)(":
            trailing_punct += ch

    if trailing_punct and sentences:
        sentences[-1] = sentences[-1].rstrip(".") + trailing_punct
    elif trailing_punct:
        return trailing_punct

    return " ".join(sentences)


def encode_instruction_cipher(text: str, layer: int) -> str:
    if layer == 1:
        return encode_instruction_hidden(text)
    return ""


def _encode_ascii(word: str) -> str:
    parts = [str(ord(ch)) for ch in word.upper() if ch.isalpha()]
    return " · ".join(parts)


def _encode_phone(word: str) -> str:
    parts: list[str] = []
    for ch in word.upper():
        if not ch.isalpha():
            continue
        for key, group in _PHONE_KEY_GROUPS:
            if ch in group:
                parts.append(str(key) * (group.index(ch) + 1))
                break
    return " · ".join(parts)


def encode_passphrase_digits(word: str, mapping: str) -> str:
    word = word.upper().strip()
    if mapping == "ascii":
        return _encode_ascii(word)
    if mapping == "phone":
        return _encode_phone(word)
    return _encode_a1z26(word)


def get_layer_encoding(layer: int) -> dict:
    mapping = get_layer_mapping_type(layer)
    word = get_layer_passphrase(layer)
    return {
        "mapping": mapping,
        "mapping_label": MAPPING_LABELS[mapping],
        "digits": encode_passphrase_digits(word, mapping),
    }


def get_digit_max_score() -> int:
    mission = _ensure_mission_config()
    return max(0, int(mission.get("digit_max_score", DEFAULT_DIGIT_MAX_SCORE)))


def get_digit_minus_score() -> int:
    mission = _ensure_mission_config()
    return max(0, int(mission.get("digit_minus_score", DEFAULT_DIGIT_MINUS_SCORE)))


def get_digit_score_for_rank(rank: int) -> int:
    """1st correct digit in a mission: max; each later entry loses one minus-score step."""
    if rank < 1:
        return 0
    return max(0, get_digit_max_score() - (rank - 1) * get_digit_minus_score())


def get_digit_wrong_penalty() -> int:
    mission = _ensure_mission_config()
    return max(0, int(mission.get("digit_wrong_penalty", DEFAULT_DIGIT_WRONG_PENALTY)))


def _record_score_event(event_type: str) -> int:
    state["score_event_id"] = state.get("score_event_id", 0) + 1
    state["last_score_event"] = {
        "id": state["score_event_id"],
        "type": event_type,
    }
    return state["score_event_id"]


def normalize_digit_input(raw: str) -> str:
    return "".join(ch for ch in raw.upper().strip() if ch.isdigit())


def get_layer_digit_parts(layer: int) -> list[str]:
    mapping = get_layer_mapping_type(layer)
    word = get_layer_passphrase(layer)
    encoded = encode_passphrase_digits(word, mapping)
    if not encoded:
        return []
    return [normalize_digit_input(part) for part in encoded.split("·")]


def _ensure_layer_digit_claims() -> dict[int, dict[int, list[str]]]:
    if "layer_digit_claims" not in state:
        state["layer_digit_claims"] = {lyr: {} for lyr in LAYERS}
    claims = state["layer_digit_claims"]
    for lyr in LAYERS:
        if lyr not in claims:
            claims[lyr] = {}
        layer_claims = claims[lyr]
        if isinstance(layer_claims, dict):
            claims[lyr] = {
                int(k): list(v) for k, v in layer_claims.items()
            }
    return claims


def _ensure_layer_digit_submission_log() -> dict[int, list[str]]:
    if "layer_digit_submission_log" not in state:
        state["layer_digit_submission_log"] = {lyr: [] for lyr in LAYERS}
    log = state["layer_digit_submission_log"]
    for lyr in LAYERS:
        log.setdefault(lyr, [])
    return log


def _layer_digit_submission_count(layer: int) -> int:
    return len(_ensure_layer_digit_submission_log().get(layer, []))


def _layer_slot_claims(layer: int, position: int) -> list[str]:
    claims = _ensure_layer_digit_claims()
    return list(claims.get(layer, {}).get(position, []))


def _layer_digits_complete(layer: int) -> bool:
    parts = get_layer_digit_parts(layer)
    if not parts:
        return False
    for idx in range(len(parts)):
        if not _layer_slot_claims(layer, idx):
            return False
    return True


def get_active_layer() -> int | None:
    for lyr in sorted(LAYERS):
        if not _layer_digits_complete(lyr):
            return lyr
    return None


def _sync_layer_finish_order(layer: int) -> None:
    """Order squads by who entered a correct digit earliest in this mission."""
    log = _ensure_layer_digit_submission_log().get(layer, [])
    squads: list[str] = []
    seen: set[str] = set()
    for squad in log:
        if squad not in seen:
            squads.append(squad)
            seen.add(squad)
    state["layer_finish_order"][layer] = squads


def _maybe_complete_layer(layer: int) -> None:
    if not _layer_digits_complete(layer):
        return
    _sync_layer_finish_order(layer)
    add_transmission(
        f"MISSION {layer} ({get_layer_name(layer)}) BREACHED :: ALL DIGITS FOUND",
        "success",
    )
    if all(_layer_digits_complete(lyr) for lyr in LAYERS):
        if state["winner"] is None:
            top = max(
                state["squad_names"],
                key=lambda s: state["squads"][s]["score"],
            )
            state["winner"] = top
            state["game_over"] = True
            add_transmission(
                f"PROTOCOL OVERRIDE :: ALL MISSIONS CLEARED :: {top} LEADS",
                "success",
            )


def get_step1_narration() -> str:
    return _step_config()["step1"]["narration"]


def get_step2_narration() -> str:
    return _step_config()["step2"]["narration"]


def get_step2_duration() -> int:
    return max(5, int(_step_config()["step2"]["duration_seconds"]))


def _ensure_step2_config() -> dict:
    step2 = _step_config().setdefault("step2", {})
    step2.setdefault("team_count", ACT0_TEAM_COUNT)
    step2.setdefault("player_count", ACT0_TEAM_COUNT * ACT0_MAX_MEMBERS)
    step2["team_count"] = max(2, min(8, int(step2["team_count"])))
    step2["player_count"] = max(
        step2["team_count"],
        min(64, int(step2["player_count"])),
    )
    return step2


def get_step2_team_count() -> int:
    return _ensure_step2_config()["team_count"]


def get_step2_player_count() -> int:
    return _ensure_step2_config()["player_count"]


def get_step2_max_members() -> int:
    teams = get_step2_team_count()
    players = get_step2_player_count()
    return max(1, min(ACT0_MAX_MEMBERS, -(-players // teams)))


def _gm_config_snapshot() -> dict:
    mission = _ensure_mission_config()
    step2 = _ensure_step2_config()
    cfg = copy.deepcopy(_step_config())
    cfg["step2"] = {
        "narration": step2["narration"],
        "duration_seconds": step2["duration_seconds"],
        "team_count": step2["team_count"],
        "player_count": step2["player_count"],
        "max_members_per_team": get_step2_max_members(),
    }
    cfg["mission"] = {
        "duration_seconds": mission["duration_seconds"],
        "names": {
            str(k): v for k, v in mission["names"].items()
        },
        "passphrases": {
            str(k): v for k, v in mission["passphrases"].items()
        },
        "digit_max_score": get_digit_max_score(),
        "digit_minus_score": get_digit_minus_score(),
        "digit_wrong_penalty": get_digit_wrong_penalty(),
        "instructions": {
            str(k): v for k, v in _ensure_mission_config()["instructions"].items()
        },
        "layers": [
            {
                "id": lyr,
                "name": get_layer_name(lyr),
                "passphrase": get_layer_passphrase(lyr),
                "instruction": get_layer_instruction(lyr),
                "instruction_cipher": encode_instruction_cipher(
                    get_layer_instruction(lyr), lyr
                ),
                **get_layer_encoding(lyr),
            }
            for lyr in sorted(LAYERS)
        ],
    }
    return cfg


def _tts_cache_key(step: str, text: str) -> str:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
    return f"{step}_{digest}"


def _invalidate_tts_step(step: str) -> None:
    for key in list(_tts_cache):
        if key.startswith(f"{step}_"):
            del _tts_cache[key]


# ============================================================================
# STATE  —  persisted in SQLite (aria_game.db); use /gm/reset to wipe progress.
# ============================================================================

def _fresh_squad_state() -> dict:
    return {
        "passphrases": {layer: None for layer in LAYERS},
        "score": 0,
        "tokens": 2,
    }


def _fresh_act0_state(duration_seconds: int | None = None) -> dict:
    return {
        "active": False,
        "complete": False,
        "timed_out": False,
        "shuffled": False,
        "started_at": None,
        "duration_seconds": duration_seconds if duration_seconds is not None else ACT0_DURATION_SECONDS,
        "teams": [],
        "narration_id": 0,
        "shuffle_narration_id": 0,
    }


def _default_state() -> dict:
    return {
        "step": STEP_IDLE,
        "step1_narration_id": 0,
        "step_config": _default_step_config(),
        "squads": {s: _fresh_squad_state() for s in SQUADS},
        "squad_names": list(SQUADS),
        "layer_finish_order": {layer: [] for layer in LAYERS},
        "layer_digit_claims": {layer: {} for layer in LAYERS},
        "layer_digit_submission_log": {layer: [] for layer in LAYERS},
        "score_event_id": 0,
        "last_score_event": {"id": 0, "type": "reward"},
        "timer": {
            "started_at": None,
            "duration_seconds": _default_step_config()["mission"]["duration_seconds"],
            "paused_at": None,
            "paused_elapsed": 0.0,
        },
        "act0": _fresh_act0_state(),
        "team_members": {},
        "transmissions": [],
        "game_over": False,
        "winner": None,
    }


def _persist() -> None:
    db.save_state(state)


state: dict = db.load_state(_default_state())

_tts_cache: dict[str, bytes] = {}


@app.on_event("startup")
async def _warm_tts_cache() -> None:
    """Pre-generate ARIA voices on startup so the first play uses Dilara."""
    try:
        s1 = get_step1_narration()
        s2 = get_step2_narration()
        await _synthesize_tts(
            _tts_cache_key("step1", s1),
            s1,
            STEP1_TTS_VOICE,
            rate=STEP1_TTS_RATE,
            pitch=STEP1_TTS_PITCH,
        )
        await _synthesize_tts(
            _tts_cache_key("step2", s2),
            s2,
            STEP2_TTS_VOICE,
            rate=STEP2_TTS_RATE,
            pitch=STEP2_TTS_PITCH,
        )
        await _synthesize_tts(
            _tts_cache_key("step2_shuffle", ACT0_SHUFFLE_ARIA),
            ACT0_SHUFFLE_ARIA,
            STEP2_TTS_VOICE,
            rate=STEP2_TTS_RATE,
            pitch=STEP2_TTS_PITCH,
        )
    except Exception:
        pass  # TTS will retry on first request


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


class Act0Team(BaseModel):
    name: str
    members: Union[list[str], str]


class Act0Submission(BaseModel):
    teams: list[Act0Team]


class Step1Config(BaseModel):
    narration: str


class Step2Config(BaseModel):
    narration: str
    duration_seconds: int
    team_count: int = ACT0_TEAM_COUNT
    player_count: int = ACT0_TEAM_COUNT * ACT0_MAX_MEMBERS


class MissionConfig(BaseModel):
    duration_seconds: int
    passphrases: dict[str, str]
    names: dict[str, str]
    digit_max_score: int = DEFAULT_DIGIT_MAX_SCORE
    digit_minus_score: int = DEFAULT_DIGIT_MINUS_SCORE
    digit_wrong_penalty: int = DEFAULT_DIGIT_WRONG_PENALTY
    instructions: dict[str, str] = {}


class InstructionCipherRequest(BaseModel):
    text: str = ""


class DigitSubmission(BaseModel):
    squad: str
    digit: str
    layer: int | None = None


def _parse_members_list(raw: Union[list[str], str]) -> list[str]:
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    return [str(m).strip() for m in raw if str(m).strip()]


def _normalize_team_members(raw: Union[list[str], str]) -> str:
    parts = _parse_members_list(raw)
    max_members = get_step2_max_members()
    if len(parts) > max_members:
        raise HTTPException(
            400,
            detail=f"Maximum {max_members} members per team.",
        )
    return ", ".join(parts)


def _shuffle_members_into_teams(
    team_names: list[str], members_pool: list[str]
) -> list[dict]:
    """Randomly distribute members across teams."""
    max_members = get_step2_max_members()
    pool = [m for m in members_pool if m]
    random.shuffle(pool)
    buckets: list[list[str]] = [[] for _ in team_names]
    team_idx = 0
    for member in pool:
        placed = False
        for _ in range(len(buckets)):
            if len(buckets[team_idx]) < max_members:
                buckets[team_idx].append(member)
                team_idx = (team_idx + 1) % len(buckets)
                placed = True
                break
            team_idx = (team_idx + 1) % len(buckets)
        if not placed:
            break
    return [
        {"name": name, "members": ", ".join(bucket)}
        for name, bucket in zip(team_names, buckets)
    ]


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


async def _synthesize_tts(
    cache_key: str,
    text: str,
    voice: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> bytes:
    if cache_key in _tts_cache:
        return _tts_cache[cache_key]
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    audio = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    _tts_cache[cache_key] = audio
    return audio


def submit(layer: int, payload: Submission):
    squad = payload.squad.upper().strip()
    if squad not in state["squad_names"]:
        add_transmission(
            f"UNAUTHORIZED ACCESS ATTEMPT :: '{payload.squad}'", "danger"
        )
        raise HTTPException(403, detail=f"Squad '{payload.squad}' not recognized.")

    if state["squads"][squad]["passphrases"][layer] is not None:
        raise HTTPException(
            409, detail=f"Layer {layer} already cleared by {squad}."
        )

    expected = get_layer_passphrase(layer)
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
        f"{squad} :: Layer {layer} ({get_layer_name(layer)}) BREACHED "
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

    _persist()
    return {
        "status": "accepted",
        "aria": (
            f"Acknowledged. Layer {layer} breached by {squad}. "
            f"Rank #{rank}. +{points} points."
        ),
        "rank": rank,
        "points": points,
    }


def submit_mission_digit(payload: DigitSubmission) -> dict:
    squad = payload.squad.upper().strip()
    if squad not in state["squad_names"]:
        add_transmission(
            f"UNAUTHORIZED DIGIT SUBMIT :: '{payload.squad}'", "danger"
        )
        raise HTTPException(403, detail=f"Squad '{payload.squad}' not recognized.")

    layer = payload.layer or get_active_layer()
    if layer is None:
        raise HTTPException(409, detail="All missions are already complete.")
    if layer not in LAYERS:
        raise HTTPException(400, detail=f"Invalid mission {layer}.")

    active = get_active_layer()
    if layer != active:
        raise HTTPException(
            409,
            detail=f"Mission {layer} is not active. Current mission is M{active}.",
        )

    digit = normalize_digit_input(payload.digit)
    if not digit:
        raise HTTPException(400, detail="Enter a digit code.")

    parts = get_layer_digit_parts(layer)
    if not parts:
        raise HTTPException(409, detail=f"Mission {layer} has no digit mapping.")

    claims = _ensure_layer_digit_claims()
    layer_claims = claims.setdefault(layer, {})

    chosen_pos: int | None = None
    for pos, expected in enumerate(parts):
        if expected != digit:
            continue
        slot = layer_claims.setdefault(pos, [])
        if squad in slot:
            continue
        if len(slot) >= MAX_DIGIT_CLAIMS_PER_SLOT:
            continue
        chosen_pos = pos
        break

    if chosen_pos is None:
        already = any(
            squad in layer_claims.get(pos, [])
            for pos, expected in enumerate(parts)
            if expected == digit
        )
        if already:
            raise HTTPException(
                409, detail=f"{squad} already submitted that digit for M{layer}."
            )
        add_transmission(
            f"{squad} :: M{layer} DIGIT REJECTED :: '{payload.digit}'", "warn"
        )
        penalty = get_digit_wrong_penalty()
        if penalty:
            state["squads"][squad]["score"] -= penalty
        event_id = _record_score_event("penalty")
        add_transmission(
            f"{squad} :: M{layer} WRONG DIGIT :: -{penalty} pts",
            "warn",
        )
        _persist()
        return {
            "status": "denied",
            "penalty": penalty,
            "points": -penalty,
            "score_event_id": event_id,
            "aria": (
                f"Incorrect digit for Mission {layer}."
                + (f" -{penalty} points." if penalty else "")
            ),
        }

    slot = layer_claims.setdefault(chosen_pos, [])
    submission_log = _ensure_layer_digit_submission_log()
    rank = len(submission_log.setdefault(layer, [])) + 1
    submission_log[layer].append(squad)
    slot.append(squad)
    points = get_digit_score_for_rank(rank)
    state["squads"][squad]["score"] += points
    event_id = _record_score_event("reward")

    _sync_layer_finish_order(layer)
    add_transmission(
        f"{squad} :: M{layer} DIGIT #{chosen_pos + 1} :: +{points} pts "
        f"(entry #{rank} in mission)",
        "success",
    )
    _maybe_complete_layer(layer)
    _persist()

    return {
        "status": "accepted",
        "layer": layer,
        "position": chosen_pos,
        "rank": rank,
        "points": points,
        "score_event_id": event_id,
        "aria": (
            f"Digit accepted for {squad}. Mission {layer}, slot "
            f"#{chosen_pos + 1}. Rank #{rank}. +{points} points."
        ),
    }


def _start_mission_timer() -> bool:
    """Start mission countdown if idle (not running and not paused)."""
    timer = state["timer"]
    if timer["paused_at"] is not None:
        return False
    if timer["started_at"] is not None:
        return False
    timer["started_at"] = time.time()
    timer["paused_elapsed"] = 0.0
    add_transmission("MISSION TIMER STARTED :: COUNTDOWN INITIATED", "info")
    return True


def _start_step3() -> None:
    if state["step"] >= STEP_MISSION:
        return
    state["step"] = STEP_MISSION
    _start_mission_timer()
    add_transmission("STEP 3 :: MISSION PROTOCOL INITIATED", "danger")
    _persist()


def _start_step2() -> None:
    if state["step"] >= STEP_TEAM_BUILD:
        return
    state["step"] = STEP_TEAM_BUILD
    state["act0"] = _fresh_act0_state(get_step2_duration())
    act0 = state["act0"]
    act0["active"] = True
    act0["started_at"] = time.time()
    act0["narration_id"] = 1
    add_transmission("STEP 2 :: TEAM BUILDING PROTOCOL INITIATED", "danger")
    add_transmission(f"ARIA :: {get_step2_narration()}", "danger")
    _persist()


def compute_act0_remaining() -> tuple[int, bool, bool]:
    act0 = state["act0"]
    if not act0["active"] or act0["started_at"] is None:
        return act0["duration_seconds"], False, False
    elapsed = time.time() - act0["started_at"]
    remaining = max(0, int(act0["duration_seconds"] - elapsed))
    if remaining <= 0 and act0["active"] and not act0["complete"]:
        act0["active"] = False
        act0["timed_out"] = True
        add_transmission(
            "ACT 0 :: TIME EXPIRED :: ENTER TEAMS TO SHUFFLE MEMBERS", "warn"
        )
        _persist()
    running = remaining > 0 and act0["active"] and not act0["complete"]
    return remaining, running, True


def apply_act0_teams(teams: list[dict]) -> None:
    """Map registered Act 0 teams onto squad slots."""
    team_limit = get_step2_team_count()
    old_names = list(state["squad_names"])
    new_names: list[str] = []
    for idx, team in enumerate(teams[:team_limit]):
        fallback = old_names[idx] if idx < len(old_names) else f"TEAM {idx + 1}"
        name = team["name"].upper().strip() or fallback
        new_names.append(name)

    while len(new_names) < team_limit:
        idx = len(new_names)
        fallback = old_names[idx] if idx < len(old_names) else f"TEAM {idx + 1}"
        new_names.append(fallback)

    for old, new in zip(old_names, new_names):
        if old == new:
            continue
        state["squads"][new] = state["squads"].pop(old)
        for order in state["layer_finish_order"].values():
            for i, squad in enumerate(order):
                if squad == old:
                    order[i] = new
        claims = _ensure_layer_digit_claims()
        for layer_claims in claims.values():
            for pos, squads in layer_claims.items():
                layer_claims[pos] = [
                    new if squad == old else squad for squad in squads
                ]
        if state["winner"] == old:
            state["winner"] = new

    state["squad_names"] = new_names
    for name in new_names:
        if name not in state["squads"]:
            state["squads"][name] = _fresh_squad_state()
    for name in list(state["squads"]):
        if name not in new_names:
            del state["squads"][name]
    if "team_members" not in state:
        state["team_members"] = {}
    for idx, team in enumerate(teams[:team_limit]):
        key = new_names[idx]
        state["team_members"][key] = team["members"]


def _get_squad_members(squad_key: str) -> str:
    members = state.get("team_members", {}).get(squad_key, "")
    for t in state["act0"].get("teams", []):
        if t["name"].upper().strip() == squad_key:
            members = members or t.get("members", "")
            break
    return members


def _squad_score_log(squad: str) -> list[dict]:
    log = []
    for layer in sorted(LAYERS):
        order = state["layer_finish_order"][layer]
        if squad in order:
            rank = order.index(squad) + 1
            log.append(
                {
                    "act": layer,
                    "act_name": get_layer_name(layer),
                    "rank": rank,
                    "points": POINTS_BY_RANK.get(rank, 0),
                }
            )
    return log


def _step_label(step: int) -> str:
    return {
        STEP_IDLE: "Idle — awaiting start",
        STEP_INTRO: "Step 1 — ARIA intro",
        STEP_TEAM_BUILD: "Step 2 — Team building",
        STEP_MISSION: "Step 3 — Mission",
    }.get(step, f"Step {step}")


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

@app.get("/theme.css")
async def theme_css():
    return FileResponse(HERE / "theme.css", media_type="text/css")


@app.get("/")
async def game_page():
    return FileResponse(HERE / "game.html")


@app.get("/game")
async def game_page_alias():
    return FileResponse(HERE / "game.html")


@app.get("/gamemaster")
async def gamemaster_page():
    return FileResponse(HERE / "gamemaster.html")


@app.get("/gamemaster/guide")
async def gamemaster_guide_page():
    return FileResponse(HERE / "gamemaster_guide.html")


@app.get("/gamemaster/routes")
async def gamemaster_routes_page():
    return FileResponse(HERE / "gamemaster_routes.html")


@app.get("/api/tts/step1")
async def tts_step1():
    """Persian neural TTS for ARIA step-1 intro (cached after first request)."""
    try:
        text = get_step1_narration()
        audio = await _synthesize_tts(
            _tts_cache_key("step1", text),
            text,
            STEP1_TTS_VOICE,
            rate=STEP1_TTS_RATE,
            pitch=STEP1_TTS_PITCH,
        )
    except Exception as exc:
        raise HTTPException(503, detail=f"TTS unavailable: {exc}") from exc
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/api/tts/step2")
async def tts_step2():
    """Persian neural TTS for ARIA step-2 team building."""
    try:
        text = get_step2_narration()
        audio = await _synthesize_tts(
            _tts_cache_key("step2", text),
            text,
            STEP2_TTS_VOICE,
            rate=STEP2_TTS_RATE,
            pitch=STEP2_TTS_PITCH,
        )
    except Exception as exc:
        raise HTTPException(503, detail=f"TTS unavailable: {exc}") from exc
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/api/tts/step2-shuffle")
async def tts_step2_shuffle():
    """Persian neural TTS for ARIA after timeout team shuffle."""
    try:
        audio = await _synthesize_tts(
            _tts_cache_key("step2_shuffle", ACT0_SHUFFLE_ARIA),
            ACT0_SHUFFLE_ARIA,
            STEP2_TTS_VOICE,
            rate=STEP2_TTS_RATE,
            pitch=STEP2_TTS_PITCH,
        )
    except Exception as exc:
        raise HTTPException(503, detail=f"TTS unavailable: {exc}") from exc
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/state")
async def get_state():
    remaining, running, started = compute_timer_remaining()
    act0_remaining, act0_running, act0_started = compute_act0_remaining()
    act0 = state["act0"]
    active_layer = get_active_layer()
    claims = _ensure_layer_digit_claims()
    return {
        "step": state["step"],
        "step1": {
            "narration": get_step1_narration(),
            "narration_id": state["step1_narration_id"],
        },
        "squad_names": list(state["squad_names"]),
        "squads": [
            {
                "name": s,
                "members": _get_squad_members(s),
                "passphrases": [
                    state["squads"][s]["passphrases"][lyr] for lyr in sorted(LAYERS)
                ],
                "score": state["squads"][s]["score"],
                "tokens": state["squads"][s]["tokens"],
            }
            for s in state["squad_names"]
        ],
        "active_layer": active_layer,
        "score_event_id": state.get("score_event_id", 0),
        "last_score_event": state.get(
            "last_score_event", {"id": 0, "type": "reward"}
        ),
        "layers": [
            {
                "id": lyr,
                "name": get_layer_name(lyr),
                "letters": len(get_layer_passphrase(lyr)),
                "instruction": get_layer_instruction(lyr),
                "digits_total": len(get_layer_digit_parts(lyr)),
                "digits_found": sum(
                    1
                    for idx in range(len(get_layer_digit_parts(lyr)))
                    if _layer_slot_claims(lyr, idx)
                ),
                "active": lyr == active_layer,
                "finish_order": state["layer_finish_order"][lyr],
                "cleared": _layer_digits_complete(lyr),
                "revealed_word": (
                    get_layer_passphrase(lyr)
                    if _layer_digits_complete(lyr)
                    else None
                ),
                "digit_slots": [
                    {
                        "position": idx,
                        "claims": len(claims.get(lyr, {}).get(idx, [])),
                        "value": (
                            get_layer_digit_parts(lyr)[idx]
                            if _layer_slot_claims(lyr, idx)
                            else None
                        ),
                    }
                    for idx in range(len(get_layer_digit_parts(lyr)))
                ],
            }
            for lyr in sorted(LAYERS)
        ],
        "transmissions": state["transmissions"][:15],
        "timer": {
            "remaining_seconds": remaining,
            "running": running,
            "started": started,
            "paused": state["timer"]["paused_at"] is not None,
            "duration_seconds": state["timer"]["duration_seconds"],
        },
        "game_over": state["game_over"],
        "winner": state["winner"],
        "act0": {
            "active": act0["active"],
            "complete": act0["complete"],
            "timed_out": act0.get("timed_out", False),
            "shuffled": act0.get("shuffled", False),
            "duration_seconds": act0["duration_seconds"],
            "remaining_seconds": act0_remaining,
            "running": act0_running,
            "started": act0_started,
            "teams": act0["teams"],
            "narration": get_step2_narration(),
            "narration_id": act0["narration_id"],
            "shuffle_narration_id": act0.get("shuffle_narration_id", 0),
            "team_count": get_step2_team_count(),
            "max_members": get_step2_max_members(),
            "player_count": get_step2_player_count(),
        },
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


@app.post("/api/mission/digit")
async def submit_mission_digit_endpoint(payload: DigitSubmission):
    """Teams submit a decoded digit for the active mission."""
    return submit_mission_digit(payload)


@app.post("/api/act0/register")
async def act0_register(payload: Act0Submission):
    if state["step"] != STEP_TEAM_BUILD:
        raise HTTPException(400, detail="Team building is not active.")
    act0 = state["act0"]
    if act0["complete"]:
        raise HTTPException(409, detail="Act 0 team registration is closed.")

    if len(payload.teams) != get_step2_team_count():
        raise HTTPException(
            400,
            detail=f"Exactly {get_step2_team_count()} teams are required.",
        )

    timed_out = act0.get("timed_out", False)

    if act0["active"]:
        teams: list[dict] = []
        for i, team in enumerate(payload.teams, start=1):
            name = team.name.strip()
            members = _normalize_team_members(team.members)
            if not name:
                raise HTTPException(400, detail=f"Team {i} requires a name.")
            if not members:
                raise HTTPException(
                    400, detail=f"Team {i} requires at least one member."
                )
            teams.append({"name": name, "members": members})
        status = "registered"
        transmission = (
            f"ACT 0 COMPLETE :: TEAMS REGISTERED :: "
            f"{' · '.join(t['name'] for t in teams)}"
        )
        severity = "success"
    elif timed_out:
        names: list[str] = []
        all_members: list[str] = []
        for i, team in enumerate(payload.teams, start=1):
            name = team.name.strip()
            if not name:
                raise HTTPException(400, detail=f"Team {i} requires a name.")
            names.append(name)
            all_members.extend(_parse_members_list(team.members))
        if not all_members:
            raise HTTPException(
                400, detail="At least one member name is required."
            )
        teams = _shuffle_members_into_teams(names, all_members)
        status = "entered"
        transmission = (
            f"ACT 0 TIMEOUT :: TEAMS ENTERED (SHUFFLED) :: "
            f"{' · '.join(t['name'] for t in teams)}"
        )
        severity = "warn"
    else:
        raise HTTPException(400, detail="Team building is not active.")

    act0["teams"] = teams
    act0["complete"] = True
    act0["active"] = False
    act0["timed_out"] = False
    act0["shuffled"] = timed_out
    if timed_out:
        act0["shuffle_narration_id"] = act0.get("shuffle_narration_id", 0) + 1
    apply_act0_teams(teams)

    add_transmission(transmission, severity)
    _persist()
    aria = ACT0_SHUFFLE_ARIA if timed_out else ACT0_REGISTER_ARIA
    return {
        "status": status,
        "aria": aria,
        "teams": teams,
        "shuffled": timed_out,
    }


# ============================================================================
# Game Master endpoints
# ============================================================================

@app.post("/gm/step/start")
async def gm_step_start():
    """Step 0 → Step 1: GM clicks Start on the white screen."""
    if state["step"] != STEP_IDLE:
        raise HTTPException(400, detail=f"Cannot start from step {state['step']}.")
    state["step"] = STEP_INTRO
    state["step1_narration_id"] = 1
    add_transmission("PROTOCOL OVERRIDE :: SESSION INITIATED", "info")
    _persist()
    return {
        "status": "started",
        "step": STEP_INTRO,
        "narration": get_step1_narration(),
    }


@app.post("/gm/step/2/begin")
async def gm_step2_begin():
    """Advance from step 1 to step 2 (team building)."""
    if state["step"] != STEP_INTRO:
        raise HTTPException(400, detail="Not in step 1.")
    _start_step2()
    return {"status": "started", "step": STEP_TEAM_BUILD}


@app.post("/gm/step/3/begin")
async def gm_step3_begin():
    """Advance from step 2 to step 3 (mission)."""
    if state["step"] != STEP_TEAM_BUILD:
        raise HTTPException(400, detail="Not in step 2.")
    act0 = state["act0"]
    if not act0.get("complete") or not act0.get("teams"):
        raise HTTPException(400, detail="Teams must be registered first.")
    _start_step3()
    return {"status": "started", "step": STEP_MISSION}


@app.post("/gm/act0/start")
async def gm_act0_start():
    """Manual override — jump straight to step 2 team building."""
    _start_step2()
    return {"status": "started", "duration_seconds": get_step2_duration()}


@app.post("/gm/act0/complete")
async def gm_act0_complete():
    act0 = state["act0"]
    if not act0["active"] and act0["complete"]:
        return {"status": "already_complete"}
    act0["active"] = False
    act0["complete"] = True
    add_transmission("ACT 0 :: TEAM BUILDING CLOSED BY GAME MASTER", "warn")
    _persist()
    return {"status": "complete"}


@app.post("/gm/timer/start")
async def gm_timer_start():
    if _start_mission_timer():
        _persist()
    return {"status": "started"}


@app.post("/gm/timer/pause")
async def gm_timer_pause():
    timer = state["timer"]
    if timer["started_at"] is not None and timer["paused_at"] is None:
        timer["paused_elapsed"] += time.time() - timer["started_at"]
        timer["paused_at"] = time.time()
        timer["started_at"] = None
        add_transmission("MISSION TIMER PAUSED", "warn")
    _persist()
    remaining, _, _ = compute_timer_remaining()
    return {"status": "paused", "remaining_seconds": remaining}


@app.post("/gm/timer/resume")
async def gm_timer_resume():
    timer = state["timer"]
    if timer["paused_at"] is not None:
        timer["started_at"] = time.time()
        timer["paused_at"] = None
        add_transmission("MISSION TIMER RESUMED", "info")
    _persist()
    remaining, running, _ = compute_timer_remaining()
    return {"status": "resumed", "remaining_seconds": remaining, "running": running}


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
    _persist()
    return {"status": "reset"}


@app.post("/gm/timer/configure")
async def gm_timer_configure(config: TimerConfig):
    state["timer"]["duration_seconds"] = max(0, int(config.duration_seconds))
    add_transmission(
        f"TIMER DURATION SET :: {config.duration_seconds}s", "info"
    )
    _persist()
    return {"status": "ok", "duration_seconds": state["timer"]["duration_seconds"]}


@app.post("/gm/score/adjust")
async def gm_adjust_score(adj: AdjustScore):
    squad = adj.squad.upper().strip()
    if squad not in state["squad_names"]:
        raise HTTPException(404, detail=f"Squad '{adj.squad}' not found.")
    state["squads"][squad]["score"] += adj.delta
    sign = "+" if adj.delta >= 0 else ""
    reason = f" ({adj.reason})" if adj.reason else ""
    add_transmission(
        f"GM ADJUSTMENT :: {squad} {sign}{adj.delta}{reason}", "info"
    )
    _persist()
    return {"status": "ok", "new_score": state["squads"][squad]["score"]}


@app.post("/gm/config/mission")
async def gm_config_mission(cfg: MissionConfig):
    duration = max(60, int(cfg.duration_seconds))
    mission = _ensure_mission_config()
    mission["duration_seconds"] = duration

    for lyr in sorted(LAYERS):
        key = str(lyr)
        if key not in cfg.names:
            raise HTTPException(400, detail=f"Name for mission {lyr} is required.")
        name = cfg.names[key].strip().upper()
        if not name:
            raise HTTPException(400, detail=f"Mission {lyr} name is required.")
        mission["names"][lyr] = name

        if key not in cfg.passphrases:
            raise HTTPException(400, detail=f"Passphrase for mission {lyr} is required.")
        phrase = cfg.passphrases[key].strip().upper()
        if not phrase:
            raise HTTPException(
                400, detail=f"Passphrase for {name} is required."
            )
        mission["passphrases"][lyr] = phrase

    mission["instructions"] = {
        lyr: cfg.instructions.get(str(lyr), "").strip()
        for lyr in sorted(LAYERS)
    }

    mission["digit_max_score"] = max(0, int(cfg.digit_max_score))
    mission["digit_minus_score"] = max(0, int(cfg.digit_minus_score))
    mission["digit_wrong_penalty"] = max(0, int(cfg.digit_wrong_penalty))

    timer = state["timer"]
    if timer["started_at"] is None and timer["paused_at"] is None:
        state["timer"]["duration_seconds"] = duration
    elif timer["paused_at"] is not None:
        state["timer"]["duration_seconds"] = duration

    add_transmission(
        f"GM :: MISSION CONFIG UPDATED :: {duration}s timer", "info"
    )
    _persist()
    encodings = {
        str(lyr): get_layer_encoding(lyr) for lyr in sorted(LAYERS)
    }
    return {
        "status": "ok",
        "duration_seconds": duration,
        "names": {str(k): v for k, v in mission["names"].items()},
        "passphrases": {str(k): v for k, v in mission["passphrases"].items()},
        "digit_max_score": get_digit_max_score(),
        "digit_minus_score": get_digit_minus_score(),
        "digit_wrong_penalty": get_digit_wrong_penalty(),
        "instructions": {
            str(k): v for k, v in mission["instructions"].items()
        },
        "instruction_cipher": encode_instruction_cipher(
            get_layer_instruction(1), 1
        ),
        "encodings": encodings,
    }


@app.post("/gm/config/step1")
async def gm_config_step1(cfg: Step1Config):
    text = cfg.narration.strip()
    if not text:
        raise HTTPException(400, detail="Step 1 narration is required.")
    _step_config()["step1"]["narration"] = text
    _invalidate_tts_step("step1")
    add_transmission("GM :: STEP 1 ANNOUNCEMENT UPDATED", "info")
    _persist()
    return {"status": "ok", "narration": text}


@app.post("/gm/config/step2")
async def gm_config_step2(cfg: Step2Config):
    text = cfg.narration.strip()
    if not text:
        raise HTTPException(400, detail="Step 2 narration is required.")
    duration = max(5, int(cfg.duration_seconds))
    team_count = max(2, min(8, int(cfg.team_count)))
    player_count = max(team_count, min(64, int(cfg.player_count)))
    step2 = _ensure_step2_config()
    step2["narration"] = text
    step2["duration_seconds"] = duration
    step2["team_count"] = team_count
    step2["player_count"] = player_count
    _invalidate_tts_step("step2")
    act0 = state["act0"]
    if not act0["active"] and act0["started_at"] is None:
        act0["duration_seconds"] = duration
    add_transmission(
        f"GM :: STEP 2 CONFIG UPDATED :: {duration}s · "
        f"{player_count} players · {team_count} teams",
        "info",
    )
    _persist()
    return {
        "status": "ok",
        "narration": text,
        "duration_seconds": duration,
        "team_count": team_count,
        "player_count": player_count,
        "max_members_per_team": get_step2_max_members(),
    }


@app.post("/gm/transmission")
async def gm_post_transmission(payload: dict):
    """Push an arbitrary ARIA message to the leaderboard log."""
    msg = str(payload.get("message", "")).strip()
    severity = str(payload.get("severity", "info")).strip() or "info"
    if not msg:
        raise HTTPException(400, detail="message is required")
    add_transmission(msg, severity)
    _persist()
    return {"status": "ok"}


@app.post("/gm/reset-act")
async def gm_reset_act():
    """Clear mission scores and act progress; stay on the current step."""
    current_step = state["step"]
    squad_names = list(state["squad_names"])
    act0_teams = list(state["act0"].get("teams", []))
    team_members = dict(state.get("team_members", {}))

    state["squads"] = {s: _fresh_squad_state() for s in squad_names}
    for lyr in LAYERS:
        state["layer_finish_order"][lyr] = []
    state["layer_digit_claims"] = {lyr: {} for lyr in LAYERS}
    state["layer_digit_submission_log"] = {lyr: [] for lyr in LAYERS}
    state["score_event_id"] = 0
    state["last_score_event"] = {"id": 0, "type": "reward"}
    state["game_over"] = False
    state["winner"] = None
    state["transmissions"] = []
    duration = state["timer"]["duration_seconds"]
    state["timer"] = {
        "started_at": None,
        "duration_seconds": duration,
        "paused_at": None,
        "paused_elapsed": 0.0,
    }

    state["step"] = current_step
    state["squad_names"] = squad_names
    state["team_members"] = team_members

    if current_step == STEP_INTRO:
        state["step1_narration_id"] += 1
    elif current_step == STEP_TEAM_BUILD:
        state["act0"] = _fresh_act0_state(get_step2_duration())
        state["act0"]["teams"] = act0_teams
        state["act0"]["complete"] = bool(act0_teams)
        if act0_teams:
            apply_act0_teams(act0_teams)
        else:
            state["act0"]["active"] = True
            state["act0"]["started_at"] = time.time()
            state["act0"]["duration_seconds"] = get_step2_duration()
            state["act0"]["narration_id"] = 1

    add_transmission(
        f"GM RESET ACT :: PROGRESS CLEARED :: {_step_label(current_step)}",
        "warn",
    )
    _persist()
    return {"status": "reset_act", "step": current_step}


@app.post("/gm/reset")
async def gm_reset():
    """Reboot game — clear teams, scores, and progress; keep GM step config."""
    saved_config = copy.deepcopy(_step_config())
    mission_duration = state["timer"]["duration_seconds"]

    state["squads"] = {s: _fresh_squad_state() for s in SQUADS}
    state["squad_names"] = list(SQUADS)
    for lyr in LAYERS:
        state["layer_finish_order"][lyr] = []
    state["layer_digit_claims"] = {lyr: {} for lyr in LAYERS}
    state["layer_digit_submission_log"] = {lyr: [] for lyr in LAYERS}
    state["score_event_id"] = 0
    state["last_score_event"] = {"id": 0, "type": "reward"}
    state["transmissions"] = []
    state["timer"] = {
        "started_at": None,
        "duration_seconds": mission_duration,
        "paused_at": None,
        "paused_elapsed": 0.0,
    }
    state["step"] = STEP_IDLE
    state["step1_narration_id"] = 0
    state["step_config"] = saved_config
    state["act0"] = _fresh_act0_state(get_step2_duration())
    state["team_members"] = {}
    state["game_over"] = False
    state["winner"] = None
    add_transmission("GAME REBOOT :: TEAMS & SCORES CLEARED", "info")
    _persist()
    return {"status": "reboot", "step": STEP_IDLE}


@app.post("/gm/mission/1/instruction-cipher")
async def gm_m1_instruction_cipher_post(body: InstructionCipherRequest):
    """Build Mission 1 cover text with the instruction hidden inside."""
    source = body.text.strip() or get_layer_instruction(1)
    return {"cipher": encode_instruction_cipher(source, 1)}


@app.get("/gm/mission/1/instruction-cipher")
async def gm_m1_instruction_cipher(text: str = ""):
    """Build Mission 1 cover text with the instruction hidden inside."""
    source = text.strip() or get_layer_instruction(1)
    return {"cipher": encode_instruction_cipher(source, 1)}


@app.get("/gm/state")
async def gm_state():
    """Dashboard snapshot for the Game Master page."""
    teams = []
    for squad_key in state["squad_names"]:
        members = state.get("team_members", {}).get(squad_key, "")
        display_name = squad_key
        for t in state["act0"].get("teams", []):
            if t["name"].upper().strip() == squad_key:
                display_name = t["name"]
                members = members or t.get("members", "")
                break
        teams.append(
            {
                "name": display_name,
                "squad_key": squad_key,
                "members": members,
                "total_score": state["squads"][squad_key]["score"],
                "score_log": _squad_score_log(squad_key),
            }
        )
    remaining, running, started = compute_timer_remaining()
    timer = state["timer"]
    return {
        "step": state["step"],
        "step_label": _step_label(state["step"]),
        "config": _gm_config_snapshot(),
        "announcement": get_step1_narration(),
        "step2_announcement": get_step2_narration(),
        "teams": teams,
        "game_over": state["game_over"],
        "winner": state["winner"],
        "transmissions": state["transmissions"][:10],
        "timer": {
            "remaining_seconds": remaining,
            "running": running,
            "started": started,
            "paused": timer["paused_at"] is not None,
            "duration_seconds": timer["duration_seconds"],
        },
    }


@app.get("/gm/routes")
async def gm_routes():
    """Game Master cheat sheet — returns all secret routes + passphrases."""
    return {
        "layers": [
            {
                "id": lyr,
                "name": get_layer_name(lyr),
                "route": LAYERS[lyr]["route"],
                "passphrase": get_layer_passphrase(lyr),
                **get_layer_encoding(lyr),
            }
            for lyr in sorted(LAYERS)
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
