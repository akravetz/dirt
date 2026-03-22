from mcp.server.fastmcp import FastMCP, Image
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.services.snapshots import get_latest_snapshot as _get_latest_snapshot
from dirt.services.snapshots import get_snapshot_path


def _register_tools(mcp: FastMCP, db_engine: AsyncEngine | None = None) -> None:
    """Register MCP tools on the given server instance.

    Args:
        mcp: The FastMCP server to register tools on.
        db_engine: Override the DB engine (used in tests). If None, uses the
            default engine from dirt.db.
    """

    def _get_engine() -> AsyncEngine:
        if db_engine is not None:
            return db_engine
        from dirt.db import engine

        return engine

    @mcp.tool()
    async def get_latest_snapshot() -> Image:
        """Return the most recent webcam snapshot as a JPEG image."""
        async with AsyncSession(_get_engine()) as session:
            snapshot = await _get_latest_snapshot(session)

        if snapshot is None:
            raise ValueError("No snapshots available")

        path = get_snapshot_path(snapshot)
        if path is None:
            raise ValueError("Snapshot file not found on disk")

        return Image(data=path.read_bytes(), format="jpeg")
