import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from wyse.db import Store

TENANT = "mcpsmoke"


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "wyse.mcp_server"],
        env={**os.environ, "WYSE_TENANT": TENANT, "WYSE_AGENT": "alice", "WYSE_ROLE": "agent"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listing = await session.list_tools()
            print("tools:", sorted(tool.name for tool in listing.tools))
            saved = await session.call_tool(
                "remember",
                {
                    "source_name": "ledger", "content": "invoice 1 is paid",
                    "subject": "inv-1", "predicate": "status", "object": "paid",
                    "source_kind": "tool",
                },
            )
            print(saved.content[0].text)
            found = await session.call_tool("recall", {"subject": "inv-1", "scope": "private"})
            print(found.content[0].text)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        store = Store()
        for name in store.list_tenants():
            if name.startswith(TENANT):
                store.drop(name)
