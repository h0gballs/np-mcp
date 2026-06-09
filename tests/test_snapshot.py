from np_mcp import snapshot
from np_mcp.config import Config, GameConfig


def test_minutes_to_production(sd):
    # 20-tick cycle, counter 5, fragment 0 -> 15 ticks * 60 min.
    assert snapshot.minutes_to_production(sd) == 15 * 60
    sd["tickFragment"] = 0.5
    assert snapshot.minutes_to_production(sd) == 14.5 * 60
    sd["turnBased"] = 1
    assert snapshot.minutes_to_production(sd) is None


def test_rank_by_stars(sd):
    assert snapshot.rank_by_stars(sd) == 1  # 2 stars vs Foe's 1


def test_fixture_sanity(fixture_sd):
    mins = snapshot.minutes_to_production(fixture_sd)
    max_cycle = fixture_sd["productionRate"] * fixture_sd["tickRate"]
    assert 0 < mins <= max_cycle
    assert snapshot.rank_by_stars(fixture_sd) >= 1
    me = snapshot.me(fixture_sd)
    assert me["alias"] == "Hogballs"
    assert len(snapshot.my_stars(fixture_sd)) == me["totalStars"]


def test_find_game():
    cfg = Config(
        games=[
            GameConfig("7651", "x", "Theta Deneb - 7651"),
            GameConfig("999", "y", "Other"),
        ],
        low_cash_threshold=50, turn_warning_minutes=720,
        host="127.0.0.1", port=8721, state_path="data/state.json",
    )
    assert cfg.find_game("").game_number == "7651"
    assert cfg.find_game("999").game_number == "999"
    assert cfg.find_game("theta deneb").game_number == "7651"
    try:
        cfg.find_game("nope")
        assert False, "expected KeyError"
    except KeyError:
        pass
