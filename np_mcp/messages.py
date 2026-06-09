"""In-game messages via the unofficial login API.

The read-only API code does not expose the inbox, so this logs in with your
NP account (NP_EMAIL/NP_PASSWORD) and uses the same endpoints the web client
does:

    POST /arequest/login              type=login, alias, password  -> auth cookie
    POST /mrequest/fetch_game_messages type=fetch_game_messages,
                                       game_number, group, count, offset

Groups: "game_diplomacy" (player mail) and "game_event" (events feed).
These endpoints are undocumented and may change; everything raises
MessagesUnavailable with a human-readable reason rather than crashing.
"""

import threading

import requests

BASE = "https://np.ironhelmet.com"
USER_AGENT = "np-mcp (personal game status server)"

GROUPS = {"diplomacy": "game_diplomacy", "events": "game_event"}


class MessagesUnavailable(Exception):
    pass


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
                f"{BASE}/arequest/login",
                data={"type": "login", "alias": self.email, "password": self.password},
                timeout=20,
            )
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as e:
            raise MessagesUnavailable(f"login request failed: {e}") from e

        # Success looks like ["meta:login_success", ...]; failure like
        # ["meta:login_failure", ...] (no auth cookie either way on failure).
        if isinstance(payload, list) and payload and "fail" in str(payload[0]).lower():
            raise MessagesUnavailable(f"login rejected: {payload}")
        if not s.cookies:
            raise MessagesUnavailable(f"login returned no session cookie: {payload!r}")
        return s

    def _request(self, path: str, data: dict) -> dict:
        with self._lock:
            if self._session is None:
                self._session = self._login()
            session = self._session
        try:
            resp = session.post(f"{BASE}/{path}", data=data, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as e:
            # Session likely expired; force a fresh login next call.
            with self._lock:
                self._session = None
            raise MessagesUnavailable(f"{path} failed: {e}") from e
        if isinstance(payload, list):  # ["meta:...", "error..."] style
            raise MessagesUnavailable(f"{path} error: {payload}")
        return payload

    def fetch_messages(
        self, game_number: str, group: str = "diplomacy",
        count: int = 20, offset: int = 0,
    ) -> list[dict]:
        api_group = GROUPS.get(group, group)
        payload = self._request(
            "mrequest/fetch_game_messages",
            {
                "type": "fetch_game_messages",
                "game_number": game_number,
                "group": api_group,
                "count": count,
                "offset": offset,
            },
        )
        raw = payload.get("messages", [])
        out = []
        for m in raw:
            body = m.get("payload", {}) or {}
            out.append(
                {
                    "key": m.get("key"),
                    "group": api_group,
                    "unread": m.get("status") == "unread",
                    "from": body.get("from_alias") or body.get("name"),
                    "subject": body.get("subject") or body.get("template"),
                    "body": body.get("body"),
                    "activity": m.get("activity"),
                    "created": m.get("created"),
                }
            )
        return out

    def unread_count(self, game_number: str) -> int:
        msgs = self.fetch_messages(game_number, "diplomacy", count=20)
        return sum(1 for m in msgs if m["unread"])
