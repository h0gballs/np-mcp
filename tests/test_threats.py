from np_mcp.threats import incoming_fleets


def enemy_fleet(uid, x, y, ships, orders, speed=0.5, puid=2):
    return {
        "uid": uid, "puid": puid, "x": x, "y": y,
        "st": ships, "speed": speed, "o": orders,
    }


def test_direct_attack_detected_with_eta(sd):
    # 1.5 map units from Home at 0.5/tick -> 3 ticks.
    sd["fleets"]["100"] = enemy_fleet(100, 1.5, 0.0, 40, [[0, 10, 0, 0]])
    threats = incoming_fleets(sd)
    assert len(threats) == 1
    t = threats[0]
    assert t["attacker"] == "Foe"
    assert t["target_star"] == "Home"
    assert t["eta_ticks"] == 3
    assert t["eta_minutes"] == 180
    assert t["defending_ships"] == 50
    assert t["relation"] == "war"


def test_multi_waypoint_eta_includes_legs_and_delays(sd):
    # (2.5,0) -> Theirs(2,0): 1 tick, wait 2, -> Home(0,0): 4 ticks = 7 total.
    sd["fleets"]["100"] = enemy_fleet(
        100, 2.5, 0.0, 10, [[2, 20, 0, 0], [0, 10, 0, 0]]
    )
    threats = incoming_fleets(sd)
    assert len(threats) == 1
    assert threats[0]["eta_ticks"] == 7


def test_own_fleets_and_unrelated_targets_ignored(sd):
    sd["fleets"]["100"] = enemy_fleet(100, 0.5, 0.0, 10, [[0, 10, 0, 0]], puid=1)
    sd["fleets"]["101"] = enemy_fleet(101, 2.5, 0.0, 10, [[0, 20, 0, 0]])
    sd["fleets"]["102"] = enemy_fleet(102, 2.5, 0.0, 10, [])  # no orders
    assert incoming_fleets(sd) == []


def test_sorted_by_eta(sd):
    sd["fleets"]["100"] = enemy_fleet(100, 3.0, 0.0, 10, [[0, 10, 0, 0]])
    sd["fleets"]["101"] = enemy_fleet(101, 1.2, 0.0, 10, [[0, 11, 0, 0]])
    threats = incoming_fleets(sd)
    assert [t["fleet_uid"] for t in threats] == [101, 100]


def test_fixture_threats_target_only_my_stars(fixture_sd):
    my_uid = fixture_sd["playerUid"]
    for t in incoming_fleets(fixture_sd):
        star = fixture_sd["stars"][str(t["target_star_uid"])]
        assert star["puid"] == my_uid
        assert t["eta_ticks"] >= 0
