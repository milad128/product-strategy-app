# PROTOCOL: OVERRIDE — Live Leaderboard

A standalone FastAPI app for the off-site team-building game.
The leaderboard is projected on the wall. Squads submit their discovered
passphrases via POST requests; the leaderboard updates live.

---

## Files

| File | Purpose |
|---|---|
| `server.py` | FastAPI backend — secret POST routes, game state, GM controls |
| `leaderboard.html` | Projector display — ARIA-themed, polls `/state` every 1s |
| `README.md` | This file |

---

## Setup (5 min, once)

```bash
# from repo root
pip install fastapi 'uvicorn[standard]' pydantic
python aria_game/server.py
```

Server starts on `http://0.0.0.0:8765`.

Find your laptop's LAN IP:

```bash
# macOS
ipconfig getifaddr en0
# or
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Say it returns `192.168.1.42`. Then:

- **Projector / wall display:** open `http://192.168.1.42:8765/` in a browser, full-screen it (F11 or Cmd+Ctrl+F).
- **Squads (on their phones / laptops):** use the same `192.168.1.42:8765` host with the per-act paths they discover.

Make sure everyone is on the **same Wi-Fi network** as the GM laptop.

---

## The hidden routes (GM only — do NOT show squads)

These are what squads must DISCOVER via in-game clues. Each act gives them
the URL path AND the passphrase to put in the body.

| Layer | Mission name | POST route | Passphrase |
|---|---|---|---|
| 1 | Hide and Seek | `POST /api/mission/hide-and-seek` | `HUMANS` |
| 2 | Stress is a Mental State | `POST /api/mission/stress-is-a-mental-state` | `SHIP` |
| 3 | Knowledge is Power | `POST /api/mission/knowledge-is-power` | `BETTER` |
| 4 | We Hear Each Other | `POST /api/mission/we-hear-each-other` | `TOGETHER` |
| 5 | Live the Life | `POST /api/mission/live-the-life` | `ALWAYS` |

Routes are built from **mission names** in GM config: lowercase, spaces → hyphens.
Example: `WE HEAR EACH OTHER` → `/api/mission/we-hear-each-other`

**Lockbox combination** = letter-count of each passphrase, in order:
`6 - 4 - 6 - 8 - 6`.

To change passphrases or mission names: use the Game Master config (routes update automatically).

You can also pull the full cheat sheet live:

```bash
curl http://localhost:8765/gm/routes
```

---

## Body format (what squads POST)

Every layer takes the same body shape:

```json
{ "squad": "VIPER", "passphrase": "HUMANS" }
```

The squad value must be one of: `VIPER`, `FALCON`, `GHOST`, `CIPHER`.

### What squads see when they call it

```bash
# correct
curl -X POST http://192.168.1.42:8765/api/mission/hide-and-seek \
  -H 'Content-Type: application/json' \
  -d '{"squad":"VIPER","passphrase":"HUMANS"}'
# → {"status":"accepted","aria":"Acknowledged. Layer 1 breached by VIPER. Rank #1. +3 points.","rank":1,"points":3}

# wrong passphrase
curl -X POST http://192.168.1.42:8765/api/mission/hide-and-seek \
  -H 'Content-Type: application/json' \
  -d '{"squad":"VIPER","passphrase":"WRONG"}'
# → {"status":"denied","aria":"Incorrect. ARIA does not yield..."} (HTTP 403)

# wrong route
curl -X POST http://192.168.1.42:8765/api/wrong/path \
  -d '{}'
# → {"detail":"Not Found"} (HTTP 404)
```

---

## Game Master controls (curl)

```bash
HOST=http://localhost:8765

# Start the mission countdown (default 3 hours)
curl -X POST $HOST/gm/timer/start

# Pause / resume
curl -X POST $HOST/gm/timer/pause
curl -X POST $HOST/gm/timer/resume

# Reset the timer (keeps progress)
curl -X POST $HOST/gm/timer/reset

# Configure timer duration (e.g. 2h = 7200s)
curl -X POST $HOST/gm/timer/configure \
  -H 'Content-Type: application/json' \
  -d '{"duration_seconds": 7200}'

# Adjust a squad's score (bonus or penalty)
curl -X POST $HOST/gm/score/adjust \
  -H 'Content-Type: application/json' \
  -d '{"squad":"GHOST","delta":2,"reason":"best ARIA negotiation"}'

# Push a theatrical ARIA message to the leaderboard log
curl -X POST $HOST/gm/transmission \
  -H 'Content-Type: application/json' \
  -d '{"message":"LAYER 4 SPRINT INITIATED","severity":"warn"}'

# Nuclear reset — wipe all squad progress, scores, transmissions
curl -X POST $HOST/gm/reset
```

---

## Recommended day-of checklist

### The night before
- [ ] Install dependencies (`pip install fastapi 'uvicorn[standard]' pydantic`)
- [ ] Run `python aria_game/server.py` and open `/` in a browser to verify
- [ ] Submit a test passphrase with curl to confirm round-trip
- [ ] Decide your final passphrase words and lockbox combo, update `LAYERS`
- [ ] Print the GM cheat sheet (`curl /gm/routes` and screenshot)

### 1 hour before guests arrive
- [ ] Boot the GM laptop, plug into projector, start the server
- [ ] Open `http://localhost:8765/` full-screen on the projector
- [ ] Verify Wi-Fi works for at least one phone hitting the LAN IP
- [ ] Save the LAN IP + each act's route as small printed cards (one per act)
  — these are what the squads find in the game as part of each puzzle
- [ ] Run `POST /gm/reset` to clear any test state

### When the game starts
- [ ] Read the briefing
- [ ] Hit `POST /gm/timer/start` — the wall clock begins counting down
- [ ] Sit back. Watch them argue.

---

## How squads discover routes (puzzle integration)

The whole game mechanic depends on each act handing squads:

1. **The URL path** — usually hidden inside a prop (a Slack-thread printout, a
   "decommissioned API spec" pinned to a wall, a fake Postman screenshot, etc.)
2. **The passphrase** — the answer to that act's puzzle

For example, the Act 1 envelope might contain:

```
   ARIA's corrupted prompt: "..."
   Solve to find the passphrase.

   When ready, submit at:
       POST 192.168.1.42:8765/api/firewall/breach
       body: { "squad": "<your name>", "passphrase": "<answer>" }
```

Squads who don't know HTTP can paste a curl into terminal, or use a free
phone app like **HTTP Shortcuts** (Android) or **HTTP Bot** (iOS).
For maximum smoothness, build a tiny Postman collection ahead of time and
QR-code its share link onto the envelopes.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Leaderboard says "UPLINK LOST" | Server not running, or you're on a different Wi-Fi |
| `curl: (7) Failed to connect` from phone | Use LAN IP, not `localhost`. Verify with `ipconfig getifaddr en0` |
| Submission returns 403 with "Squad not recognized" | Squad name must be uppercase one of VIPER / FALCON / GHOST / CIPHER |
| Squad cleared too fast | They cheated and read the source. Use `/gm/score/adjust` with negative delta |
| Need to roll back a wrong submission | Restart the server (or just adjust the score; the slot stays filled) |
| Projector resolution looks weird | Open browser DevTools, set responsive mode to projector resolution |

---

## Customization

All game config is at the top of `server.py`:

- `SQUADS` — rename or add squads
- `LAYERS` — change routes, passphrases, layer names
- `POINTS_BY_RANK` — adjust speed-bonus scoring
- `DEFAULT_TIMER_SECONDS` — default mission duration

The leaderboard auto-adapts to whatever `LAYERS` you define.
