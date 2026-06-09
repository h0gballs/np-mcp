import json
import os
import tempfile


class Store:
    """Per-game summary snapshots for check_events, saved atomically."""

    def __init__(self, path: str):
        self.path = path
        self.data: dict[str, dict] = {}
        if os.path.exists(path):
            with open(path) as f:
                self.data = json.load(f)

    def get(self, game_number: str) -> dict | None:
        return self.data.get(game_number)

    def put(self, game_number: str, summary: dict) -> None:
        self.data[game_number] = summary
        self._save()

    def _save(self) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as tf:
            json.dump(self.data, tf)
            tmp = tf.name
        os.replace(tmp, self.path)  # atomic
