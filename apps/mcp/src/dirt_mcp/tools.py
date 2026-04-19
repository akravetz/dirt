from mcp.server.fastmcp import FastMCP, Image

from dirt.services.snapshots import get_latest_snapshot, get_snapshot_path


def _register_tools(mcp: FastMCP, **kwargs) -> None:
    """Register MCP tools on the given server instance."""

    @mcp.tool()
    async def get_latest_snapshot_tool() -> Image:
        """Return the most recent webcam snapshot as a JPEG image."""
        snapshot = await get_latest_snapshot()

        if snapshot is None:
            raise ValueError("No snapshots available")

        path = get_snapshot_path(snapshot)
        if path is None:
            raise ValueError("Snapshot file not found on disk")

        return Image(data=path.read_bytes(), format="jpeg")
