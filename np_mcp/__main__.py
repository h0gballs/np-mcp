import logging

from . import config
from .server import build_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("np-mcp")


def main() -> None:
    cfg = config.load()
    server = build_server(cfg)
    log.info(
        "np-mcp serving %d game(s) at http://%s:%d/mcp",
        len(cfg.games), cfg.host, cfg.port,
    )
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
