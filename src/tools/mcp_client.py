"""
Athena MCP Client - Connect to MCP server for tool execution.
Supports both direct function calls and MCP protocol communication.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import threading

try:
    from fastmcp import Client as FastMCPClient
    from mcp.types import Tool, CallToolResult
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP tool representation."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPClient:
    """
    Client for connecting to Athena's MCP server and executing tools.
    Maintains persistent connection with background event loop.
    """

    def __init__(self, server_path: str):
        self.server_path = server_path
        self._tools_cache: Optional[List[MCPTool]] = None

        # Background event loop
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Initialize client
        self._client: Optional[FastMCPClient] = None
        self._initialize_client()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _initialize_client(self):
        """Initialize MCP client connection."""
        if not MCP_AVAILABLE:
            logger.warning("[MCP] MCP not available, using direct tool calls")
            return

        future = asyncio.run_coroutine_threadsafe(self._create_client(), self._loop)
        future.result(timeout=10)

    async def _create_client(self):
        """Create and enter MCP client context."""
        self._client = FastMCPClient(self.server_path)
        await self._client.__aenter__()
        logger.info("[MCP] Client connected to server")

    def list_tools(self) -> List[MCPTool]:
        """List available tools from MCP server."""
        if not MCP_AVAILABLE or not self._client:
            return []

        future = asyncio.run_coroutine_threadsafe(self._client.list_tools(), self._loop)
        try:
            tools = future.result(timeout=10)
            self._tools_cache = [
                MCPTool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.inputSchema
                )
                for tool in tools
            ]
            return self._tools_cache
        except Exception as e:
            logger.error(f"[MCP] Failed to list tools: {e}")
            return []

    def call_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Execute a tool on the MCP server."""
        if not MCP_AVAILABLE or not self._client:
            return "Error: MCP not available"

        future = asyncio.run_coroutine_threadsafe(
            self._call_tool_async(name, args),
            self._loop
        )
        try:
            result = future.result(timeout=30)
            return self._extract_result(result)
        except Exception as e:
            logger.error(f"[MCP] Tool call failed: {e}")
            return f"Error: {e}"

    async def _call_tool_async(self, name: str, args: Dict[str, Any]) -> 'CallToolResult':
        return await self._client.call_tool(name, args)

    def _extract_result(self, result: 'CallToolResult') -> str:
        """Extract text content from tool result."""
        if hasattr(result, 'content') and result.content:
            for item in result.content:
                if hasattr(item, 'text'):
                    return item.text
        return str(result)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions in LLM-compatible format."""
        tools = self.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            }
            for tool in tools
        ]

    def close(self):
        """Close the MCP client connection."""
        if self._client and MCP_AVAILABLE:
            future = asyncio.run_coroutine_threadsafe(self._client.__aexit__(None, None, None), self._loop)
            try:
                future.result(timeout=5)
            except Exception:
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)


# Module-level singleton
_default_client: Optional[MCPClient] = None


def get_default_client() -> MCPClient:
    """Get or create the default MCP client (singleton)."""
    global _default_client
    if _default_client is None:
        import os
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        server_path = os.path.join(tools_dir, "mcp_server.py")
        _default_client = MCPClient(server_path)
    return _default_client


def get_mcp_tools() -> List[Dict[str, Any]]:
    """Get all MCP tool definitions for LLM function calling."""
    client = get_default_client()
    return client.get_tool_definitions()


def call_mcp_tool(name: str, args: Dict[str, Any]) -> str:
    """Execute an MCP tool by name."""
    client = get_default_client()
    return client.call_tool(name, args)