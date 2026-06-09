"""Detect enemy fleets heading for my stars.

Visible fleets expose their waypoint queue as `o`: a list of orders
[delay_ticks, target_star_uid, action, ships]. A fleet whose queue includes
one of my stars is an incoming attack; ETA is travel time along the queue
(fleet `speed` is map-distance per tick) plus any waypoint delays.
"""

import math

from . import snapshot


def _dist(x1, y1, x2, y2) -> float:
    return math.hypot(float(x1) - float(x2), float(y1) - float(y2))


def incoming_fleets(sd: dict) -> list[dict]:
    """Enemy fleets with a waypoint on one of my stars, sorted by ETA."""
    uid = snapshot.my_uid(sd)
    mine = snapshot.my_stars(sd)
    all_stars = snapshot.stars(sd)
    tick_rate = int(sd.get("tickRate", 60))
    me = snapshot.me(sd)
    war_map = me.get("war", {})

    threats = []
    for fleet in snapshot.fleets(sd).values():
        owner = fleet.get("puid")
        if owner == uid:
            continue
        orders = fleet.get("o") or []
        speed = float(fleet.get("speed", 0)) or float(sd.get("fleetSpeed", 1 / 24))

        x, y = fleet.get("x"), fleet.get("y")
        eta_ticks = 0.0
        for order in orders:
            if not isinstance(order, (list, tuple)) or len(order) < 2:
                continue
            delay, target_uid = order[0], order[1]
            target = all_stars.get(str(target_uid))
            if target is None:
                break  # waypoint outside scan range; can't follow the path
            eta_ticks += _dist(x, y, target["x"], target["y"]) / speed
            x, y = target["x"], target["y"]

            if str(target_uid) in mine:
                defending = mine[str(target_uid)]
                raw_war = war_map.get(str(owner), 3)
                threats.append(
                    {
                        "fleet_uid": fleet.get("uid"),
                        "attacker_uid": owner,
                        "attacker": snapshot.alias(sd, owner),
                        "ships": fleet.get("st", 0),
                        "target_star": defending.get("n"),
                        "target_star_uid": int(target_uid),
                        "eta_ticks": math.ceil(eta_ticks),
                        "eta_minutes": round(eta_ticks * tick_rate),
                        "defending_ships": defending.get("st", 0),
                        "defending_industry": defending.get("i", 0),
                        "relation": snapshot.war_label(raw_war),
                        "relation_raw": raw_war,
                    }
                )
                break  # first of my stars on its path is the alert that matters

            eta_ticks += float(delay)  # waits at this waypoint before moving on

    threats.sort(key=lambda t: t["eta_ticks"])
    return threats
