# np-mcp — Neptune's Pride MCP server

An MCP server exposing Neptune's Pride game state as tools, so a Hermes Agent
(cron every 10 min → Telegram) can alert on anything important. Branches off
the behaviour of `../np-reminder`, which already solves API access, deadline
math, config, state persistence, and systemd deployment.

## Decisions (confirmed 2026-06-09)

- **Transport**: MCP **streamable HTTP** (FastMCP), run as a systemd service
  like np-reminder. Hermes connects to `http://<host>:<port>/mcp`.
- **Messages**: **included**, via the unofficial login API (NP email/password
  in `.env` → session cookie → `mrequest` endpoints). Undocumented; must
  degrade gracefully (other tools keep working if login breaks).
- **Eventing**: **stateful**. A `check_events` tool diffs current game state
  against a JSON state file and returns only what changed since last check.
  This is the cron workhorse: "call check_events; alert if non-empty".
- **Language**: Python 3.13 + `mcp` SDK (FastMCP), `requests`, `pyyaml` —
  same stack/conventions as np-reminder.

## What the API gives us (verified live against game 7651)

`scanning_data` from the read-only API key contains:

| wishlist item | source |
|---|---|
| money left | `players[me].cash` |
| next production | `productionCounter`/`productionRate`/`tickFragment`/`tickRate` (np-reminder `timing.py` math) |
| am I being attacked | visible fleets carry `puid`, position, `speed`, `st` (ships), and order queue `o` = `[delay, target_star_uid, action, ships]` → enemy fleet whose order targets one of my stars, ETA from distance/speed |
| research done/ETA | `players[me].tech[kind] = {level, research, cost}` + `researching`, `researchingNext`, `totalScience` (points/tick) |
| diplomacy | `players[me].war` (per-player relation), `countdown_to_war`, `offersOfFealty`, `vassals`, `ledger` |
| standings | every player's `totalStars/Economy/Industry/Science/Strength/Fleets`, `conceded`, `ai`, `missedTurns` |
| my stars | stars with `puid == me`: `e/i/s` (economy/industry/science), `st` (ships), `r/nr` (resources), `ga` (gate), `yard` |
| turn-based readiness | `turnBased`, `turnDeadline`, `players[me].ready` |

**Not** in the API-key response: in-game messages → login API (phase 3).

## Layout (mirrors np-reminder)

```
np-mcp/
  config.example.yaml      # games: game_number, code, label (same shape as np-reminder)
  .env.example             # NP_MCP_HOST/PORT, NP_EMAIL/NP_PASSWORD (messages), STATE_PATH
  Makefile                 # venv, test, run, service-install/status/logs (mirror np-reminder)
  deploy/np-mcp.service.template
  np_mcp/
    __main__.py            # parse config, run FastMCP streamable-http
    server.py              # FastMCP instance + tool definitions (thin: parse args, call modules, format)
    config.py              # yaml + env loading (adapted from np-reminder/config.py)
    npapi.py               # fetch_scanning_data (copied from np-reminder) 
    snapshot.py            # typed views over scanning_data: me, my_stars, visible fleets, players
    timing.py              # production/turn deadline math (adapted from np-reminder/timing.py)
    threats.py             # incoming-fleet detection + ETA
    research.py            # research progress/ETA
    events.py              # diff engine: prev summary vs current → list of events
    state.py               # JSON state file (adapted from np-reminder/state.py)
    messages.py            # login API client: session cookie, fetch inbox (phase 3)
  tests/
    fixtures/scanning_data.json   # captured live sample (sanitize the API code)
    test_threats.py / test_research.py / test_events.py / test_timing.py
```

## MCP tools

All tools take `game` (label or game_number; default = first configured game).
Return values are compact JSON-ish dicts — built for an LLM consumer, so
prefer names/aliases and human units (minutes, ticks) over raw uids.

1. `list_games()` — configured games with name, tick, started/paused/gameOver.
2. `get_game_status(game)` — one-call overview: tick, minutes to next
   production (or turn deadline + ready flag), cash, my totals
   (stars/econ/ind/sci/ships), rank by stars, count of incoming hostile
   fleets, current research + ETA. *The "is anything wrong" snapshot.*
3. `get_threats(game)` — every enemy fleet with an order targeting one of my
   stars: attacker alias, ships, target star name, ETA in ticks and minutes,
   plus defending star's ships/industry. Sorted by ETA.
4. `get_research_status(game)` — current tech name, points/cost, ticks to
   completion (cost·level math), next queued tech, science per tick.
5. `get_players(game)` — leaderboard: alias, stars/econ/ind/sci/strength,
   relation to me (war/peace/neutral from `war` map), conceded/AI flags.
6. `get_my_empire(game)` — per-star detail for my stars: economy, industry,
   science, ships, resources, gates; totals and weakest/strongest stars.
7. `get_messages(game, count=10)` — recent diplomacy messages + events feed
   via login API; flags unread. Errors with a clear message if login fails.
8. `check_events(game)` — **the cron tool.** Diffs against `data/state.json`,
   updates it, returns only new events. Event types:
   - `incoming_attack` — new hostile fleet targeting my star (per fleet uid)
   - `star_lost` / `star_captured`
   - `research_complete` — tech level increased (report new level + next)
   - `production_occurred` — cycle rolled over (report new cash)
   - `low_cash` — cash below configurable threshold at production
   - `war_declared` / `relation_changed`
   - `new_message` — unread/inbox count increased (login API; skipped if unavailable)
   - `turn_deadline_soon` — turn-based only, not ready, within window
   - `player_conceded` / `player_eliminated`
   Each event gets a stable id (np-reminder dedup pattern) so a re-run after
   a crashed cron never double-fires. **Note: reading consumes events** —
   designed for a single cron consumer.

## Phases

1. **Core (stateless)** — scaffold, config, npapi reuse, snapshot/threats/
   research/timing modules, tools 1–6, FastMCP streamable HTTP serving, tests
   against a captured fixture. *Usable by Hermes immediately.*
2. **Eventing** — state file + diff engine + `check_events` (tool 8), tests
   for each event type and dedup.
3. **Messages** — probe the login endpoints (`arequest/login` →
   `mrequest/fetch_game_messages`), implement `messages.py` + tool 7 +
   `new_message` event. Re-login on session expiry; never crash the server.
4. **Deploy & wire-up** — Makefile + systemd unit + README; suggested Hermes
   cron prompt:
   > Every 10 min: call `check_events` for each game from `list_games`. If
   > any events return, send me a Telegram message summarizing them (use
   > `get_threats`/`get_game_status` for detail on attacks). Otherwise stay
   > silent.

## Risks / notes

- Login API is unofficial — phase 3 starts with a live probe; if endpoints
  changed, messages ship as "unavailable" without blocking phases 1–2.
- `check_events` consuming on read means manual testing eats the cron's
  events; add a `peek=true` arg that diffs without saving state.
- Visibility: we only see fleets in scan range — `incoming_attack` ETAs can
  appear "suddenly" when a fleet enters scan. That's inherent to the game.
- Multi-game from day one (config.yaml list, same as np-reminder).
