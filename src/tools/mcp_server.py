"""
Athena MCP Server

Central MCP server that imports and exposes all tools.
Run this as a standalone process or connect via FastMCP Client.

Usage:
    # Run standalone (for testing with MCP Inspector)
    python mcp_server.py
    
    # Connect programmatically
    from fastmcp import Client
    async with Client("tools/mcp_server.py") as client:
        result = await client.call_tool("get_current_time", {})
"""
import sys
import os

src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from mcp.server.fastmcp import FastMCP
from tools.time_tool import get_current_time
from tools.info_tool import get_info

mcp = FastMCP("Athena Tools")
mcp.tool()(get_current_time)
mcp.tool()(get_info)

if __name__ == "__main__":
    mcp.run()
