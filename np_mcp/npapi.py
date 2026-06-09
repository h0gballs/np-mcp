import requests

API_URL = "https://np.ironhelmet.com/api"
USER_AGENT = "np-mcp (personal game status server)"


class APIError(Exception):
    pass


def fetch_scanning_data(game_number: str, code: str, timeout: float = 20.0) -> dict:
    """Return the scanning_data dict for one game, or raise APIError.

    The current Neptune's Pride (NP4) API answers a GET with query params.
    The older POST-form variant is rejected with "error_parsing_game_number".
    """
    resp = requests.get(
        API_URL,
        params={"api_version": "0.1", "game_number": game_number, "code": code},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()

    # Error responses come back as a JSON array, e.g.
    #   ["api:error", "error_parsing_game_number"]
    if isinstance(payload, list):
        reason = payload[1] if len(payload) > 1 else "unknown api error"
        raise APIError(str(reason))

    if not isinstance(payload, dict):
        raise APIError(f"unexpected API response: {payload!r}")

    if payload.get("error"):
        raise APIError(str(payload["error"]))

    sd = payload.get("scanning_data")
    if sd is None:
        raise APIError("response had no scanning_data (bad game_number/code?)")

    return sd
