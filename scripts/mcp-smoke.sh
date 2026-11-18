#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
backend/.venv/bin/python - "${1:-http://127.0.0.1:8000/mcp}" <<'PY'
import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client(sys.argv[1]) as (read, write, _):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert "assess_cleaning" in {tool.name for tool in tools.tools}
            result = await client.call_tool("assess_cleaning", {"inputs": {
                "surface": "studio_display_standard_glass",
                "materials": "water_and_microfiber_only",
                "confirmed": True,
            }})
            assert not result.isError and result.structuredContent["status"] == "approved"
            print(result.structuredContent)


asyncio.run(main())
PY
