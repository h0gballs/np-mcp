from np_mcp.research import research_status


def test_eta_math(sd):
    # weapons level 2, cost 100 -> needs 200, has 10, science 5 -> 38 ticks.
    rs = research_status(sd)
    cur = rs["current"]
    assert cur["tech"] == "weapons"
    assert cur["points_needed"] == 200
    assert cur["ticks_remaining"] == 38
    assert cur["eta_hours"] == 38.0  # 60-minute ticks
    assert rs["levels"] == {"weapons": 2}
    assert rs["researching_next"] == "weapons"


def test_zero_science_gives_no_eta(sd):
    sd["players"]["1"]["totalScience"] = 0
    cur = research_status(sd)["current"]
    assert cur["ticks_remaining"] is None


def test_fixture_research(fixture_sd):
    rs = research_status(fixture_sd)
    # Game 7651: researching weapons lvl 10, 329/1440 points, 20 sci/tick.
    assert rs["current"]["tech"] == "weapons"
    assert rs["current"]["points_needed"] == 1440
    assert rs["current"]["ticks_remaining"] == 56
    assert "banking" in rs["levels"]
    assert "scanning" not in rs["levels"]  # disabled via noScn in this game
