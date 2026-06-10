"""Diff engine behind check_events.

summarize() reduces a scanning_data snapshot to the fields worth comparing;
diff() turns (previous summary, current summary) into a list of events. Every
event has a stable `id` so a consumer (or a re-run after a crash) can dedup.
"""

from . import snapshot
from .threats import incoming_fleets


def summarize(sd: dict, threats: list[dict] | None = None,
              unread_messages: int | None = None) -> dict:
    me = snapshot.me(sd)
    threats = incoming_fleets(sd) if threats is None else threats
    return {
        "tick": int(sd["tick"]),
        "productions": int(sd.get("productions", 0)),
        "cash": int(me.get("cash", 0)),
        "star_uids": sorted(int(k) for k in snapshot.my_stars(sd)),
        "star_names": {k: s.get("n") for k, s in snapshot.my_stars(sd).items()},
        "tech_levels": {
            str(k): int(t.get("level", 0)) for k, t in me.get("tech", {}).items()
        },
        "researching": me.get("researching"),
        "incoming": {
            str(t["fleet_uid"]): {
                "attacker": t["attacker"],
                "ships": t["ships"],
                "target_star": t["target_star"],
                "eta_ticks": t["eta_ticks"],
            }
            for t in threats
        },
        "war": dict(me.get("war", {})),
        "conceded": sorted(
            int(uid)
            for uid, p in snapshot.players(sd).items()
            if p.get("conceded")
        ),
        "alive": sorted(
            int(uid)
            for uid, p in snapshot.players(sd).items()
            if int(p.get("totalStars", 0)) > 0
        ),
        "turn_warned_id": None,  # carried forward / set by diff
        "unread_messages": unread_messages,
        "game_over": bool(sd.get("gameOver")),
    }


def _ev(type_: str, id_: str, message: str, **details) -> dict:
    return {"type": type_, "id": id_, "message": message, **details}


def diff(prev: dict | None, cur: dict, sd: dict, cfg) -> list[dict]:
    """Events that happened between prev and cur. Mutates cur to carry
    forward dedup markers (turn_warned_id)."""
    events: list[dict] = []
    name = sd.get("name", "")

    # Turn-based deadline warning is checked even on the first run; everything
    # else needs a baseline.
    if prev is None:
        events.append(
            _ev(
                "baseline",
                f"baseline-{cur['tick']}",
                f"Now watching '{name}': baseline recorded at tick {cur['tick']}; "
                "future checks report only changes.",
            )
        )
    else:
        cur["turn_warned_id"] = prev.get("turn_warned_id")

        # --- attacks ---
        for fid, t in cur["incoming"].items():
            if fid not in prev.get("incoming", {}):
                events.append(
                    _ev(
                        "incoming_attack",
                        f"attack-{fid}",
                        f"{t['attacker']} fleet of {t['ships']} ships is heading "
                        f"for your star {t['target_star']} (ETA ~{t['eta_ticks']} ticks).",
                        **t,
                    )
                )

        # --- stars lost / captured ---
        prev_stars = set(prev.get("star_uids", []))
        cur_stars = set(cur["star_uids"])
        prev_names = prev.get("star_names", {})
        for uid in sorted(prev_stars - cur_stars):
            sname = prev_names.get(str(uid)) or snapshot.star_name(sd, uid)
            owner = snapshot.stars(sd).get(str(uid), {}).get("puid")
            taker = f" to {snapshot.alias(sd, owner)}" if owner is not None else ""
            events.append(
                _ev("star_lost", f"lost-{uid}-{cur['tick']}",
                    f"You LOST star {sname}{taker}.", star=sname)
            )
        for uid in sorted(cur_stars - prev_stars):
            sname = cur["star_names"].get(str(uid), f"star {uid}")
            events.append(
                _ev("star_captured", f"captured-{uid}-{cur['tick']}",
                    f"You captured star {sname}.", star=sname)
            )

        # --- research ---
        for kind, level in cur["tech_levels"].items():
            if level > int(prev.get("tech_levels", {}).get(kind, level)):
                tname = snapshot.tech_name(kind)
                events.append(
                    _ev("research_complete", f"research-{kind}-{level}",
                        f"Research complete: {tname} is now level {level}.",
                        tech=tname, level=level)
                )

        # --- production / cash ---
        if cur["productions"] > prev.get("productions", cur["productions"]):
            events.append(
                _ev("production_occurred", f"prod-{cur['productions']}",
                    f"Production cycle {cur['productions']} completed. "
                    f"Cash on hand: ${cur['cash']}.", cash=cur["cash"])
            )
            if cur["cash"] < cfg.low_cash_threshold:
                events.append(
                    _ev("low_cash", f"lowcash-{cur['productions']}",
                        f"Low cash after production: ${cur['cash']} "
                        f"(threshold ${cfg.low_cash_threshold}).", cash=cur["cash"])
                )

        # --- diplomacy ---
        for puid, val in cur["war"].items():
            old = prev.get("war", {}).get(puid)
            if old is None or int(old) == int(val):
                continue
            who = snapshot.alias(sd, puid)
            if int(val) == 0:
                etype = "alliance_formed"
            elif int(val) == 3:
                etype = "war_declared"
            else:
                etype = "relation_changed"
            events.append(
                _ev(etype, f"war-{puid}-{val}-{cur['tick']}",
                    f"Relation with {who} changed: "
                    f"{snapshot.war_label(old)} -> {snapshot.war_label(val)}.",
                    player=who, old=int(old), new=int(val))
            )

        # --- players conceding / eliminated ---
        for puid in sorted(set(cur["conceded"]) - set(prev.get("conceded", []))):
            events.append(
                _ev("player_conceded", f"conceded-{puid}",
                    f"{snapshot.alias(sd, puid)} has conceded.")
            )
        for puid in sorted(set(prev.get("alive", [])) - set(cur["alive"])):
            events.append(
                _ev("player_eliminated", f"eliminated-{puid}",
                    f"{snapshot.alias(sd, puid)} has been eliminated.")
            )

        # --- messages ---
        cur_unread = cur.get("unread_messages")
        prev_unread = prev.get("unread_messages")
        if (
            cur_unread is not None
            and prev_unread is not None
            and cur_unread > prev_unread
        ):
            events.append(
                _ev("new_message", f"msg-{cur['tick']}-{cur_unread}",
                    f"You have {cur_unread - prev_unread} new in-game "
                    f"message(s) ({cur_unread} unread total).",
                    unread=cur_unread)
            )

    # --- turn-based deadline (dedup by deadline timestamp) ---
    if sd.get("turnBased"):
        minutes = snapshot.minutes_to_turn_deadline(sd)
        ready = bool(snapshot.me(sd).get("ready", 0))
        warn_id = f"turn-{sd.get('turnDeadline')}"
        if (
            minutes is not None
            and 0 <= minutes <= cfg.turn_warning_minutes
            and not ready
            and cur.get("turn_warned_id") != warn_id
        ):
            cur["turn_warned_id"] = warn_id
            events.append(
                _ev("turn_deadline_soon", warn_id,
                    f"Turn deadline in ~{round(minutes)} minutes and you are "
                    "NOT marked ready.", minutes_left=round(minutes))
            )

    return events
