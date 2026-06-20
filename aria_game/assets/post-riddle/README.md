# POST API riddle — 8 IDE screens

Eight fake IDE code screenshots for a room puzzle. **Only Screen 6** contains the real POST body and response.

| Screen | File | Decoy? |
|--------|------|--------|
| 1 | `screen-01-game.html` | Digit POST only |
| 2 | `screen-02-database.html` | Wrong JSON schema |
| 3 | `screen-03-theme.html` | CSS only |
| 4 | `screen-04-gamemaster.html` | Wrong PUT endpoint |
| 5 | `screen-05-server.html` | Digit handler + legacy model |
| 6 | `screen-06-client.html` | **REAL — POST body + response** |
| 7 | `screen-07-models.html` | Wrong field names |
| 8 | `screen-08-readme.html` | Fake docs (`team`/`keyword`) |

## Print for the room

```bash
open "aria_game/assets/post-riddle/index.html"
```

Use **Print** (8 pages). Shuffle the pages before posting on walls or placing in folders.

## GM answer

See `GM-ANSWER.txt` — keep away from players.

## What teams need to discover

```json
{"squad": "YOUR TEAM NAME", "passphrase": "RECOVERED WORD"}
```

POST to `/api/mission/{mission-slug}` with `Content-Type: application/json`.
