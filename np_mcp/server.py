"""FastMCP server exposing Neptune's Pride game state as tools."""

import logging

from mcp.server.fastmcp import FastMCP

from . import events as events_mod
from . import research as research_mod
from . import snapshot
from .config import Config
from .messages import MessagesUnavailable, NPSession
from .npapi import fetch_scanning_data
from .state import Store
from .threats import incoming_fleets

log = logging.getLogger("np-mcp")


def build_server(cfg: Config) -> FastMCP:
    mcp = FastMCP(
        "np-mcp",
        instructions=(
            "Read-only status tools for the user's Neptune's Pride games. "
            "For periodic alerting, call check_events: it returns only what "
            "changed since the previous call (and consumes those events). "
            "Use the other tools for detail when something needs a closer look."
        ),
        host=cfg.host,
        port=cfg.port,
        stateless_http=True,
    )
    store = Store(cfg.state_path)
    np_session: NPSession | None = None

    def _session() -> NPSession:
        nonlocal np_session
        if np_session is None:
            np_session = NPSession(cfg.np_email, cfg.np_password)
        return np_session

    def _fetch(game: str) -> tuple:
        g = cfg.find_game(game)
        return g, fetch_scanning_data(g.game_number, g.code)

    def _status(sd: dict) -> dict:
        me = snapshot.me(sd)
        threat_list = incoming_fleets(sd)
        status = {
            "game": sd.get("name"),
            "tick": sd.get("tick"),
            "started": bool(sd.get("started")),
            "paused": bool(sd.get("paused")),
            "game_over": bool(sd.get("gameOver")),
            "cash": me.get("cash"),
            "my_totals": {
                "stars": me.get("totalStars"),
                "economy": me.get("totalEconomy"),
                "industry": me.get("totalIndustry"),
                "science": me.get("totalScience"),
                "ships": me.get("totalStrength"),
                "fleets": me.get("totalFleets"),
            },
            "rank_by_stars": snapshot.rank_by_stars(sd),
            "players_total": len(snapshot.players(sd)),
            "incoming_attacks": len(threat_list),
            "research": research_mod.research_status(sd).get("current"),
        }
        if sd.get("turnBased"):
            mins = snapshot.minutes_to_turn_deadline(sd)
            status["turn_deadline_minutes"] = round(mins) if mins is not None else None
            status["ready"] = bool(me.get("ready", 0))
        else:
            mins = snapshot.minutes_to_production(sd)
            status["next_production_minutes"] = (
                round(mins) if mins is not None else None
            )
        return status

    @mcp.tool()
    def list_games() -> list[dict]:
        """List configured games with name, tick and basic liveness."""
        out = []
        for g in cfg.games:
            entry = {"game": g.display, "game_number": g.game_number}
            try:
                sd = fetch_scanning_data(g.game_number, g.code)
                entry.update(
                    name=sd.get("name"),
                    tick=sd.get("tick"),
                    started=bool(sd.get("started")),
                    paused=bool(sd.get("paused")),
                    game_over=bool(sd.get("gameOver")),
                )
            except Exception as e:
                entry["error"] = str(e)
            out.append(entry)
        return out

    @mcp.tool()
    def get_game_status(game: str = "") -> dict:
        """One-call overview: production countdown, cash, totals, rank,
        incoming attack count, current research ETA. `game` is a label or
        game number; empty = first configured game."""
        _, sd = _fetch(game)
        return _status(sd)

    @mcp.tool()
    def get_threats(game: str = "") -> list[dict]:
        """Enemy fleets heading for my stars: attacker, ships, target star,
        ETA in ticks/minutes, and the defending star's ships. Sorted by ETA.
        Fleets from formal allies are excluded (they cannot capture stars).
        Empty list = nothing visibly incoming."""
        _, sd = _fetch(game)
        return incoming_fleets(sd)

    @mcp.tool()
    def get_research_status(game: str = "") -> dict:
        """Current research progress and ETA, queued tech, and all tech
        levels."""
        _, sd = _fetch(game)
        return research_mod.research_status(sd)

    @mcp.tool()
    def get_players(game: str = "") -> list[dict]:
        """Leaderboard of all players: totals, relation to me, conceded/AI
        flags. Sorted by stars owned (descending)."""
        _, sd = _fetch(game)
        me = snapshot.me(sd)
        war_map = me.get("war", {})
        out = []
        for uid, p in snapshot.players(sd).items():
            out.append(
                {
                    "uid": int(uid),
                    "alias": p.get("alias"),
                    "is_me": int(uid) == snapshot.my_uid(sd),
                    "stars": p.get("totalStars"),
                    "economy": p.get("totalEconomy"),
                    "industry": p.get("totalIndustry"),
                    "science": p.get("totalScience"),
                    "ships": p.get("totalStrength"),
                    "relation": snapshot.war_label(war_map.get(uid, 3)),
                    "conceded": bool(p.get("conceded")),
                    "ai": bool(p.get("ai")),
                }
            )
        out.sort(key=lambda p: (-(p["stars"] or 0), p["uid"]))
        return out

    @mcp.tool()
    def get_my_empire(game: str = "") -> dict:
        """Per-star detail for my stars: economy/industry/science, ships,
        resources, gate; plus totals and the weakest stars (fewest ships)."""
        _, sd = _fetch(game)
        stars = []
        for s in snapshot.my_stars(sd).values():
            stars.append(
                {
                    "uid": s.get("uid"),
                    "name": s.get("n"),
                    "ships": s.get("st"),
                    "economy": s.get("e"),
                    "industry": s.get("i"),
                    "science": s.get("s"),
                    "resources": s.get("r"),
                    "natural_resources": s.get("nr"),
                    "gate": bool(s.get("ga")),
                }
            )
        stars.sort(key=lambda s: s["ships"] or 0)
        me = snapshot.me(sd)
        return {
            "star_count": len(stars),
            "cash": me.get("cash"),
            "weakest_stars": stars[:5],
            "stars": stars,
        }

    @mcp.tool()
    def get_messages(game: str = "", group: str = "diplomacy", count: int = 10) -> dict:
        """Recent in-game messages. group: 'diplomacy' (player mail) or
        'events' (game events feed). Needs NP_EMAIL/NP_PASSWORD; returns an
        error field if unavailable."""
        g = cfg.find_game(game)
        try:
            msgs = _session().fetch_messages(g.game_number, group, count)
        except MessagesUnavailable as e:
            return {"error": str(e), "messages": []}

        # Resolve player uids to aliases (senders, event participants).
        try:
            sd = fetch_scanning_data(g.game_number, g.code)
            for m in msgs:
                if m.get("from_uid") is not None:
                    m["from"] = snapshot.alias(sd, m["from_uid"])
                for key in ("attacker", "defender", "puid", "uid", "from_puid", "to_puid"):
                    val = m.get("data", {}).get(key)
                    if isinstance(val, int):
                        m["data"][f"{key}_alias"] = snapshot.alias(sd, val)
        except Exception as e:
            log.warning("alias enrichment failed: %s", e)

        return {
            "unread": sum(1 for m in msgs if m["unread"]),
            "messages": msgs,
        }

    @mcp.tool()
    def check_events(game: str = "", peek: bool = False) -> dict:
        """What changed since the last check: incoming attacks, stars
        lost/captured, research completed, production/low cash, diplomacy
        changes, concessions, new messages, turn deadline warnings.

        Reading CONSUMES events (state is saved) unless peek=true. Designed
        for a single periodic consumer: alert on anything returned."""
        g, sd = _fetch(game)

        unread = None
        if cfg.np_email and cfg.np_password:
            try:
                unread = _session().unread_count(g.game_number)
            except MessagesUnavailable as e:
                log.warning("unread count unavailable: %s", e)

        threat_list = incoming_fleets(sd)
        current = events_mod.summarize(sd, threat_list, unread)
        previous = store.get(g.game_number)
        evs = events_mod.diff(previous, current, sd, cfg)
        if not peek:
            store.put(g.game_number, current)
        return {
            "game": sd.get("name", g.display),
            "tick": sd.get("tick"),
            "events": evs,
        }

    return mcp
