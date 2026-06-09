import os
from dataclasses import dataclass, field

import yaml


@dataclass
class GameConfig:
    game_number: str
    code: str
    label: str = ""

    @property
    def display(self) -> str:
        return self.label or self.game_number


@dataclass
class Config:
    games: list[GameConfig]
    low_cash_threshold: int
    turn_warning_minutes: int

    host: str
    port: int
    state_path: str

    # Optional NP account creds for the unofficial messages API.
    np_email: str = ""
    np_password: str = ""

    def find_game(self, game: str = "") -> GameConfig:
        """Resolve a game by label or game_number; empty = first configured."""
        if not game:
            return self.games[0]
        for g in self.games:
            if game in (g.game_number, g.label):
                return g
        # Forgiving match: substring of label, case-insensitive.
        lowered = game.lower()
        for g in self.games:
            if lowered in g.label.lower():
                return g
        known = ", ".join(g.display for g in self.games)
        raise KeyError(f"unknown game {game!r}; configured games: {known}")


def load(config_path: str = "config.yaml") -> Config:
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    games = [
        GameConfig(
            game_number=str(g["game_number"]),
            code=str(g["code"]),
            label=g.get("label", ""),
        )
        for g in raw.get("games", [])
    ]
    if not games:
        raise SystemExit("No games configured in config.yaml")

    return Config(
        games=games,
        low_cash_threshold=int(raw.get("low_cash_threshold", 50)),
        turn_warning_minutes=int(raw.get("turn_warning_minutes", 720)),
        host=os.environ.get("NP_MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("NP_MCP_PORT", "8721")),
        state_path=os.environ.get("STATE_PATH", "data/state.json"),
        np_email=os.environ.get("NP_EMAIL", ""),
        np_password=os.environ.get("NP_PASSWORD", ""),
    )
