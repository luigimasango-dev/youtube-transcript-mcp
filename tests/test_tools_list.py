"""Smoke test: launch the server over stdio, call tools/list, assert tool names.

The mcp-smoke-test pattern: if this passes, any MCP client can see the tools.
Run with: pytest  (or: python -m pytest tests/ -v)
"""
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent.parent

EXPECTED_TOOLS = {
    "get_transcript",
    "get_video_metadata",
    "search_transcript",
    "summarize_chapters",
}


def _list_tool_names() -> list[str]:
    async def go() -> list[str]:
        params = StdioServerParameters(
            command=sys.executable, args=[str(HERE / "server.py")], cwd=str(HERE)
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return [t.name for t in tools.tools]

    return asyncio.run(go())


def test_server_lists_expected_tools():
    names = _list_tool_names()
    missing = EXPECTED_TOOLS - set(names)
    assert not missing, f"tools missing from tools/list: {missing} (got: {names})"
