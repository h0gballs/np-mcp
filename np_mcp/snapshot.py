"""Typed-ish views over an NP4 scanning_data dict.

Field semantics cross-checked against the NP4 client and the open-source
Neptune's Pride Agent (anicolao/npa). Tech "kind" ids:
    0 banking, 1 experimentation, 2 manufacturing, 3 propulsion,
    4 scanning, 5 weapons, 6 terraforming
(kinds disabled via config noScn/noTer/noExp are simply absent).
"""

TECH_NAMES = {
    0: "banking",
    1: "experimentation",
    2: "manufacturing",
    3: "propulsion",
    4: "scanning",
    5: "weapons",
    6: "terraforming",
}

# players[me].war values, per the NP client (cf. anicolao/npa combatcalc.ts
# allied()): 0 = formally allied, 3 = war (the default, including toward
# yourself). 1/2 are transitional (alliance offer / declared-war notice).
# Raw value is always reported alongside the label.
WAR_LABELS = {0: "allied", 1: "pending", 2: "pending", 3: "war"}

MS_PER_MIN = 60_000


def tech_name(kind) -> str:
    return TECH_NAMES.get(int(kind), f"tech_{kind}")


def war_label(value) -> str:
    return WAR_LABELS.get(int(value), f"unknown_{value}")


def me(sd: dict) -> dict:
    return sd["players"][str(sd["playerUid"])]


def my_uid(sd: dict) -> int:
    return int(sd["playerUid"])


def players(sd: dict) -> dict[str, dict]:
    return sd.get("players", {})


def alias(sd: dict, puid) -> str:
    p = players(sd).get(str(puid))
    return p.get("alias") or f"player {puid}" if p else f"player {puid}"


def stars(sd: dict) -> dict[str, dict]:
    return sd.get("stars", {})


def my_stars(sd: dict) -> dict[str, dict]:
    uid = my_uid(sd)
    return {k: s for k, s in stars(sd).items() if s.get("puid") == uid}


def star_name(sd: dict, star_uid) -> str:
    s = stars(sd).get(str(star_uid))
    return s.get("n", f"star {star_uid}") if s else f"star {star_uid}"


def fleets(sd: dict) -> dict[str, dict]:
    return sd.get("fleets", {})


def minutes_to_production(sd: dict) -> float | None:
    """Minutes until the production cycle ends, or None for turn-based games."""
    if sd.get("turnBased"):
        return None
    tick = int(sd["tick"])
    tick_rate = int(sd["tickRate"])  # minutes per tick
    frac = float(sd.get("tickFragment", 0.0))
    prod_rate = int(sd["productionRate"])
    counter = int(sd.get("productionCounter", tick % prod_rate))
    return (prod_rate - counter - frac) * tick_rate


def minutes_to_turn_deadline(sd: dict) -> float | None:
    if not sd.get("turnBased"):
        return None
    return (int(sd.get("turnDeadline", 0)) - int(sd["now"])) / MS_PER_MIN


def rank_by_stars(sd: dict, puid: int | None = None) -> int:
    """1-based rank of a player (default: me) by total stars owned."""
    puid = my_uid(sd) if puid is None else puid
    totals = sorted(
        (int(p.get("totalStars", 0)) for p in players(sd).values()), reverse=True
    )
    mine = int(players(sd)[str(puid)].get("totalStars", 0))
    return totals.index(mine) + 1
