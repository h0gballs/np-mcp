# np-mcp

MCP server that exposes your Neptune's Pride games as tools, so an AI agent
(e.g. a Hermes Agent on a 10-minute cron) can read game state and alert you
over Telegram when something needs attention: incoming attacks, stars lost,
research finished, production cycles, low cash, diplomacy changes, new
messages, turn deadlines.

Sibling of [np-reminder](../np-reminder) (which only emails before deadlines);
this exposes *everything* the API knows, plus a change-detection tool.

## Quick start

```bash
cp config.example.yaml config.yaml   # add each game's game_number + API code
cp .env.example .env                 # host/port; NP creds only for messages

make test                            # run the test suite
make run                             # serve http://127.0.0.1:8721/mcp (foreground)
```

Long-term, run it under systemd:

```bash
make service-install     # install + enable + start (sudo)
make service-status
make service-logs
make smoke               # call the running server once via MCP (peek mode)
```

- **`game_number`** is in the game URL: `https://np.ironhelmet.com/game/<game_number>`.
- **`code`** is the read-only API key from the game menu → API Key.
- **`NP_EMAIL`/`NP_PASSWORD`** (optional, `.env`) enable the `get_messages`
  tool and `new_message` events. They use the *unofficial* login API (the
  read-only key cannot see your inbox); everything else works without them.

## Tools

| tool | what it returns |
|------|-----------------|
| `list_games()` | configured games with tick + liveness |
| `get_game_status(game)` | overview: production countdown, cash, totals, rank, incoming-attack count, research ETA |
| `get_threats(game)` | enemy fleets with a waypoint on one of your stars: attacker, ships, target, ETA, defenders |
| `get_research_status(game)` | current research progress/ETA, queued tech, all levels |
| `get_players(game)` | leaderboard with relation to you, conceded/AI flags |
| `get_my_empire(game)` | per-star economy/industry/science/ships, weakest stars first |
| `get_messages(game, group, count)` | in-game mail (`diplomacy`) or events feed (`events`); needs NP creds |
| `check_events(game, peek)` | **changes since last call** — see below |

`game` accepts a label or game number; empty selects the first configured
game. All tools are read-only with respect to the game (the API key cannot
issue orders).

### check_events

The alerting workhorse. Keeps a summary snapshot in `data/state.json` and
returns only what changed since the previous call:

`incoming_attack`, `star_lost`, `star_captured`, `research_complete`,
`production_occurred`, `low_cash`, `war_declared`, `relation_changed`,
`player_conceded`, `player_eliminated`, `new_message`, `turn_deadline_soon`,
plus a one-time `baseline` on first run.

Every event has a stable `id` for dedup. **Reading consumes events** (the
snapshot is saved) unless you pass `peek=true` — so point exactly one cron at
it and use `peek` for manual poking (`make smoke` does this).

## Wiring up Hermes

Point your Hermes Agent's MCP client at `http://<host>:8721/mcp`
(streamable HTTP, stateless). Suggested 10-minute cron prompt:

> Call `check_events` for each game returned by `list_games`. If any events
> come back, send me a Telegram message summarizing them in one or two
> sentences each, most urgent first. For `incoming_attack` events, call
> `get_threats` and include attacker strength vs defending ships. If there
> are no events, do nothing and send nothing.

If Hermes runs on another machine, set `NP_MCP_HOST=0.0.0.0` in `.env` and
firewall the port appropriately (the server has no auth of its own).

## Notes & caveats

- Field semantics (tech kind ids, research cost = `level * cost`, fleet order
  arrays `[delay, target_star, action, ships]`) were cross-checked against
  the open-source Neptune's Pride Agent (anicolao/npa). Tech kinds:
  0 banking, 1 experimentation, 2 manufacturing, 3 range, 4 scanning,
  5 weapons, 6 terraforming. (Kind 3 is "propulsion" in the raw NP4 data;
  exposed here as "range", the player-facing name for hyperspace range.)
- `war` relation labels are best-effort (0 = war, 3 = peace/default); the raw
  value is always included, and any change fires an event regardless.
- Threats only include fleets inside your scan range — a fleet can "appear"
  with a short ETA when it enters scan. That's the game, not a bug.
- The messages endpoints are undocumented and may break; tools report an
  `error` field instead of crashing, and `check_events` keeps working. The
  current flow (verified live, cross-checked with anicolao/aib):
  `POST /account_api/login` (form: type, alias, password) then
  `POST /game_api/fetch_game_messages` (form: type, gameId, group, count,
  offset, version=np4) with the session cookie. The `events` group returns
  templated payloads (`war_declared`, `peace_requested`, ...) with player
  uids, which the server enriches with aliases.

## Tests

```bash
make test
```

Covers threat detection/ETA math, research ETA, production timing, the event
diff engine (one test per event type, dedup, JSON round-trip), and sanity
checks against a captured live `scanning_data` fixture.

## References
- https://github.com/anicolao/npa was heavily referenced for NP4 API discovery and manipulation

## License

[MIT](LICENSE) — do whatever you like, just keep the copyright notice.

Unofficial. Not affiliated with or endorsed by Ironhelmet/Neptune's Pride;
"Neptune's Pride" is their trademark. This project uses the game's read-only
API key plus an undocumented login endpoint, either of which may change or
break without notice.
