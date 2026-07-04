from __future__ import annotations

import argparse
import logging
import socket
from collections.abc import Sequence
from contextlib import closing

import uvicorn

from dirt_hwd.tools.substrate_calibration.app import create_app

logger = logging.getLogger(__name__)


def _lan_ip() -> str | None:
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except OSError:
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dirt_hwd.tools.substrate_calibration",
        description="Run the local RS485 substrate probe calibration server.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="interface to bind; use 0.0.0.0 for LAN laptop access",
    )
    parser.add_argument("--port", type=int, default=8097, help="port to bind")
    parser.add_argument(
        "--controller-url",
        default="http://plant-a-substrate-node.local",
        help="base URL for the RS485 substrate controller",
    )
    return parser


def _log_urls(host: str, port: int) -> None:
    if host in {"0.0.0.0", "::"}:  # noqa: S104 - reporting a caller-chosen bind.
        logger.info("Local URL: http://127.0.0.1:%s/", port)
        lan_ip = _lan_ip()
        if lan_ip is not None:
            logger.info("LAN URL: http://%s:%s/", lan_ip, port)
        return
    logger.info("Local URL: http://%s:%s/", host, port)


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    app = create_app(controller_url=args.controller_url)
    logger.info("Controller URL: %s", args.controller_url)
    _log_urls(args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
