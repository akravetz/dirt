from mcp.server.fastmcp import FastMCP, Image

from dirt_shared.services.snapshots import SnapshotsService, get_snapshot_path


def _register_tools(mcp: FastMCP, *, snapshots: SnapshotsService) -> None:
    """Register MCP tools on the given server instance.

    Services are passed in by the composition root (``create_mcp_app``)
    and captured by the tool closures.
    """

    @mcp.tool()
    async def get_latest_snapshot_tool() -> Image:
        """Return the most recent webcam snapshot as a JPEG image."""
        snapshot = await snapshots.latest()

        if snapshot is None:
            raise ValueError("No snapshots available")

        path = get_snapshot_path(snapshot)
        if path is None:
            raise ValueError("Snapshot file not found on disk")

        return Image(data=path.read_bytes(), format="jpeg")
