"""Research progress math for NP4.

Points needed for the next level of a tech = level * cost (verified against
the NP4 client logic via anicolao/npa techCost()). Your science output is
totalScience points per tick.
"""

import math

from . import snapshot


def _eta(tech: dict, science: int) -> dict:
    level = int(tech.get("level", 0))
    cost = int(tech.get("cost", 0))
    done = int(tech.get("research", 0))
    needed = level * cost
    remaining = max(0, needed - done)
    ticks = math.ceil(remaining / science) if science > 0 else None
    return {
        "level": level,
        "points": done,
        "points_needed": needed,
        "ticks_remaining": ticks,
    }


def research_status(sd: dict) -> dict:
    me = snapshot.me(sd)
    science = int(me.get("totalScience", 0))
    tick_rate = int(sd.get("tickRate", 60))
    tech = me.get("tech", {})

    current_kind = me.get("researching")
    next_kind = me.get("researchingNext")

    result = {
        "science_per_tick": science,
        "levels": {
            snapshot.tech_name(k): int(t.get("level", 0)) for k, t in tech.items()
        },
        "researching_next": snapshot.tech_name(next_kind)
        if next_kind is not None
        else None,
    }

    current = tech.get(str(current_kind))
    if current is not None:
        info = _eta(current, science)
        info["tech"] = snapshot.tech_name(current_kind)
        if info["ticks_remaining"] is not None:
            info["eta_hours"] = round(info["ticks_remaining"] * tick_rate / 60, 1)
        result["current"] = info
    else:
        result["current"] = None

    return result
