"""Smoke-test a running np-mcp server the way Hermes would.

Usage: make smoke   (server must already be running, e.g. via systemd)
Calls get_game_status and check_events(peek=true) for each game and prints
the results. peek=true so it never consumes the cron's events.
"""

import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main() -> None:
    host = os.environ.get("NP_MCP_HOST", "127.0.0.1")
    port = os.environ.get("NP_MCP_PORT", "8721")
    url = f"http://{host}:{port}/mcp"
    print(f"connecting to {url}")
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for name, args in [
                ("get_game_status", {}),
                ("check_events", {"peek": True}),
            ]:
                res = await session.call_tool(name, args)
                for block in res.content:
                    try:
                        print(f"--- {name} ---")
                        print(json.dumps(json.loads(block.text), indent=1))
                    except (ValueError, AttributeError):
                        print(block)


if __name__ == "__main__":
    asyncio.run(main())
