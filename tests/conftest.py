import copy
import json
import os

import pytest


@pytest.fixture(scope="session")
def fixture_sd() -> dict:
    path = os.path.join(os.path.dirname(__file__), "fixtures", "scanning_data.json")
    with open(path) as f:
        return json.load(f)


def make_sd() -> dict:
    """Small synthetic NP4-shaped scanning_data: me (uid 1) vs foe (uid 2)."""
    return {
        "playerUid": 1,
        "name": "Test Game",
        "tick": 100,
        "tickRate": 60,
        "tickFragment": 0.0,
        "now": 1_000_000,
        "started": True,
        "paused": False,
        "gameOver": False,
        "turnBased": 0,
        "turnDeadline": 0,
        "productions": 3,
        "productionRate": 20,
        "productionCounter": 5,
        "fleetSpeed": 1 / 24,
        "players": {
            "1": {
                "uid": 1,
                "alias": "Me",
                "cash": 100,
                "war": {"1": 3, "2": 0},
                "tech": {"5": {"kind": 5, "level": 2, "research": 10, "cost": 100}},
                "researching": 5,
                "researchingNext": 5,
                "totalScience": 5,
                "totalStars": 2,
                "totalEconomy": 4,
                "totalIndustry": 3,
                "totalStrength": 55,
                "totalFleets": 1,
                "conceded": 0,
                "ready": 0,
            },
            "2": {
                "uid": 2,
                "alias": "Foe",
                "conceded": 0,
                "totalStars": 1,
                "totalScience": 2,
                "tech": {"5": {"kind": 5, "level": 3, "research": 0, "cost": 100}},
            },
        },
        "stars": {
            "10": {"uid": 10, "n": "Home", "puid": 1, "x": 0.0, "y": 0.0,
                   "st": 50, "e": 2, "i": 3, "s": 1, "r": 30, "nr": 30, "ga": 0},
            "11": {"uid": 11, "n": "Outpost", "puid": 1, "x": 1.0, "y": 0.0,
                   "st": 5, "e": 1, "i": 1, "s": 0, "r": 20, "nr": 20, "ga": 0},
            "20": {"uid": 20, "n": "Theirs", "puid": 2, "x": 2.0, "y": 0.0,
                   "st": 30},
        },
        "fleets": {},
    }


@pytest.fixture
def sd() -> dict:
    return copy.deepcopy(make_sd())


class StubConfig:
    low_cash_threshold = 50
    turn_warning_minutes = 720


@pytest.fixture
def cfg() -> StubConfig:
    return StubConfig()
