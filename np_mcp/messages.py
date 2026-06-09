"""In-game messages via the unofficial login API.

The read-only API code does not expose the inbox, so this logs in with your
NP account (NP_EMAIL/NP_PASSWORD) and uses the same endpoints the NP4 web
client does (shapes cross-checked against anicolao/aib):

    POST /account_api/login            type=login, alias, password
        -> ["meta:login_success", report] + session cookie (Set-Cookie)
    POST /game_api/fetch_game_messages type=fetch_game_messages, gameId,
                                       group, count, offset, version=np4
        -> ["message:new_messages", {"messages": [...]}]

Groups: "game_diplomacy" (player mail) and "game_event" (events feed).
These endpoints are undocumented and may change; everything raises
MessagesUnavailable with a human-readable reason rather than crashing.
"""

import html
import threading

import requests

BASE = "https://np.ironhelmet.com"
USER_AGENT = "np-mcp (personal game status server)"
NP_VERSION = "np4"

GROUPS = {"diplomacy": "game_diplomacy", "events": "game_event"}


class MessagesUnavailable(Exception):
    pass


def _parse(resp: requests.Response, path: str) -> tuple[str, dict]:
    """NP responds with a JSON array [event, report, ...]."""
    try:
        payload = resp.json()
    except ValueError as e:
        raise MessagesUnavailable(f"{path}: non-JSON response") from e
    if not isinstance(payload, list) or len(payload) < 2:
        raise MessagesUnavailable(f"{path}: unexpected response {payload!r}")
    return str(payload[0]), payload[1]


class NPSession:
    def __init__(self, email: str, password: str):
        if not email or not password:
            raise MessagesUnavailable(
                "NP_EMAIL/NP_PASSWORD not configured; messages are disabled"
            )
        self.email = email
        self.password = password
        self._lock = threading.Lock()
        self._session: requests.Session | None = None

    def _login(self) -> requests.Session:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        try:
            resp = s.post(
                f"{BASE}/account_api/login",
                data={"type": "login", "alias": self.email, "password": self.password},
                timeout=20,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise MessagesUnavailable(f"login request failed: {e}") from e

        event, report = _parse(resp, "login")
        if event != "meta:login_success":
            raise MessagesUnavailable(f"login rejected: {event} {report!r}")
        if not s.cookies:
            raise MessagesUnavailable("login succeeded but returned no session cookie")
        return s

    def _game_post(self, type_: str, game_number: str, data: dict) -> dict:
        with self._lock:
            if self._session is None:
                self._session = self._login()
            session = self._session
        form = {"type": type_, "gameId": game_number, "version": NP_VERSION, **data}
        try:
            resp = session.post(f"{BASE}/game_api/{type_}", data=form, timeout=20)
            resp.raise_for_status()
            event, report = _parse(resp, type_)
        except (requests.RequestException, MessagesUnavailable):
            # Session likely expired; force a fresh login next call.
            with self._lock:
                self._session = None
            raise
        if event.startswith("meta:") or "error" in event:
            with self._lock:
                self._session = None
            raise MessagesUnavailable(f"{type_} error: {event} {report!r}")
        return report

    def fetch_messages(
        self, game_number: str, group: str = "diplomacy",
        count: int = 20, offset: int = 0,
    ) -> list[dict]:
        api_group = GROUPS.get(group, group)
        report = self._game_post(
            "fetch_game_messages",
            game_number,
            {"group": api_group, "count": count, "offset": offset},
        )
        out = []
        for m in report.get("messages", []):
            payload = m.get("payload", {}) or {}
            entry = {
                "key": m.get("key"),
                "group": api_group,
                "unread": m.get("status") == "unread",
                "subject": html.unescape(
                    str(payload.get("subject") or payload.get("template") or "")
                ),
                "activity": m.get("activity"),
                "created": m.get("created"),
            }
            if api_group == "game_event":
                # Events are templated: {"template": "war_declared",
                # "attacker": 5, "defender": 46, "tick": 316}
                entry["data"] = {
                    k: v for k, v in payload.items() if k != "template"
                }
            else:
                entry["from_uid"] = payload.get("from_uid")
                entry["to"] = payload.get("to_aliases")
                entry["body"] = html.unescape(str(payload.get("body") or ""))
            out.append(entry)
        return out

    def unread_count(self, game_number: str) -> int:
        msgs = self.fetch_messages(game_number, "diplomacy", count=20)
        return sum(1 for m in msgs if m["unread"])
