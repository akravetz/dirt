"""Entrypoint for the dirt web app (port 8001).

Serves the UI, sensors/snapshots/feed JSON API, and mounts the MCP
server at /mcp. Does not own any hardware loops — those live in
dirt-hwd.service. Run as `dirt-web.service`.
"""

import uvicorn


def main() -> None:
    uvicorn.run(
        "dirt_web.app:app",
        host="0.0.0.0",
        port=8001,
    )


if __name__ == "__main__":
    main()
