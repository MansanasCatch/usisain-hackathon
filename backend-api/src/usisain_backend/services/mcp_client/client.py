"""client.py — connects to mcp_server/server.py over stdio and calls its
tools. Spawns a fresh server process per call — simple to reason about
for a project this size. If latency becomes a problem, hold a long-lived
ClientSession open for the app's lifetime instead."""

import os
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ...core.config import settings


async def call_tool(tool_name: str, arguments: dict) -> dict:
    server_params = StdioServerParameters(
        command="py" if os.name == "nt" else "python3",
        args=[str(settings.mcp_server_path)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            for block in result.content:
                if hasattr(block, "text"):
                    try:
                        return json.loads(block.text)
                    except json.JSONDecodeError:
                        return {"raw": block.text}
            return {"error": "No content returned from tool"}
