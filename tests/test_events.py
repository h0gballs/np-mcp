import copy

from np_mcp.events import diff, summarize


def types(evs):
    return [e["type"] for e in evs]


def test_first_run_is_baseline_only(sd, cfg):
    cur = summarize(sd)
    evs = diff(None, cur, sd, cfg)
    assert types(evs) == ["baseline"]


def step(sd, prev_summary, cfg, unread=None):
    cur = summarize(sd, unread_messages=unread)
    return cur, diff(prev_summary, cur, sd, cfg)


def test_quiet_tick_produces_no_events(sd, cfg):
    prev = summarize(sd)
    sd["tick"] += 1
    _, evs = step(sd, prev, cfg)
    assert evs == []


def test_incoming_attack_fires_once(sd, cfg):
    prev = summarize(sd)
    sd["fleets"]["100"] = {
        "uid": 100, "puid": 2, "x": 1.5, "y": 0.0, "st": 40,
        "speed": 0.5, "o": [[0, 10, 0, 0]],
    }
    cur, evs = step(sd, prev, cfg)
    assert types(evs) == ["incoming_attack"]
    assert "Foe" in evs[0]["message"]
    # Same fleet still incoming next check -> no repeat.
    _, evs2 = step(sd, cur, cfg)
    assert evs2 == []


def test_star_lost_and_captured(sd, cfg):
    prev = summarize(sd)
    sd["stars"]["11"]["puid"] = 2          # lost Outpost
    sd["stars"]["20"]["puid"] = 1          # captured Theirs
    _, evs = step(sd, prev, cfg)
    assert sorted(types(evs)) == ["star_captured", "star_lost"]
    lost = next(e for e in evs if e["type"] == "star_lost")
    assert "Outpost" in lost["message"]
    assert "Foe" in lost["message"]


def test_research_complete(sd, cfg):
    prev = summarize(sd)
    sd["players"]["1"]["tech"]["5"]["level"] = 3
    _, evs = step(sd, prev, cfg)
    assert types(evs) == ["research_complete"]
    assert "weapons" in evs[0]["message"]
    assert evs[0]["level"] == 3


def test_production_and_low_cash(sd, cfg):
    prev = summarize(sd)
    sd["productions"] = 4
    sd["players"]["1"]["cash"] = 10
    _, evs = step(sd, prev, cfg)
    assert types(evs) == ["production_occurred", "low_cash"]
    # Cash above threshold -> production only.
    prev2 = summarize(sd)
    sd["productions"] = 5
    sd["players"]["1"]["cash"] = 500
    _, evs2 = step(sd, prev2, cfg)
    assert types(evs2) == ["production_occurred"]


def test_war_and_relation_changes(sd, cfg):
    # 3 -> 0: a formal alliance was made.
    prev = summarize(sd)
    sd["players"]["1"]["war"]["2"] = 0
    cur, evs = step(sd, prev, cfg)
    assert types(evs) == ["alliance_formed"]
    assert evs[0]["player"] == "Foe"
    # 0 -> 3: the alliance ended; we are at war.
    sd["players"]["1"]["war"]["2"] = 3
    _, evs2 = step(sd, cur, cfg)
    assert types(evs2) == ["war_declared"]


def test_conceded_and_eliminated(sd, cfg):
    prev = summarize(sd)
    sd["players"]["2"]["conceded"] = 1
    sd["players"]["2"]["totalStars"] = 0
    _, evs = step(sd, prev, cfg)
    assert sorted(types(evs)) == ["player_conceded", "player_eliminated"]


def test_new_message(sd, cfg):
    prev = summarize(sd, unread_messages=1)
    cur, evs = step(sd, prev, cfg, unread=3)
    assert types(evs) == ["new_message"]
    assert evs[0]["unread"] == 3
    # No change -> quiet; unknown (None) -> quiet.
    _, evs2 = step(sd, cur, cfg, unread=3)
    assert evs2 == []
    _, evs3 = step(sd, cur, cfg, unread=None)
    assert evs3 == []


def test_turn_deadline_warning_dedups(sd, cfg):
    sd["turnBased"] = 1
    sd["turnDeadline"] = sd["now"] + 60 * 60_000  # 60 minutes away
    cur = summarize(sd)
    evs = diff(None, cur, sd, cfg)
    assert "turn_deadline_soon" in types(evs)
    # Next check, same deadline: warned already.
    nxt = summarize(sd)
    evs2 = diff(cur, nxt, sd, cfg)
    assert evs2 == []
    # New deadline (next turn) -> warns again.
    sd["turnDeadline"] = sd["now"] + 30 * 60_000
    nxt2 = summarize(sd)
    evs3 = diff(nxt, nxt2, sd, cfg)
    assert types(evs3) == ["turn_deadline_soon"]


def test_turn_warning_suppressed_when_ready(sd, cfg):
    sd["turnBased"] = 1
    sd["turnDeadline"] = sd["now"] + 60 * 60_000
    sd["players"]["1"]["ready"] = 1
    evs = diff(None, summarize(sd), sd, cfg)
    assert types(evs) == ["baseline"]


def test_summary_roundtrips_through_json(sd, cfg):
    """State is persisted as JSON; a reloaded summary must diff cleanly."""
    import json

    prev = json.loads(json.dumps(summarize(sd)))
    sd["tick"] += 1
    _, evs = step(sd, prev, cfg)
    assert evs == []


def test_fixture_baseline_then_quiet(fixture_sd, cfg):
    sd1 = copy.deepcopy(fixture_sd)
    prev = summarize(sd1)
    assert types(diff(None, prev, sd1, cfg)) == ["baseline"]
    evs = diff(prev, summarize(sd1), sd1, cfg)
    assert evs == []
