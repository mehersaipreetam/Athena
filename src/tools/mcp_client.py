"""
MCP Client wrapper for Athena.

Provides a synchronous interface to MCP tools for use in the voice assistant loop.
"""
import asyncio
import os
from fastmcp import Client
from typing import Any


class MCPToolClient:
    """Client for connecting to and executing MCP tools."""
    
    def __init__(self, server_path: str):
        """
        Initialize the MCP client.
        
        Args:
            server_path: Path to the MCP server script (e.g., "tools/time_tool.py")
        """
        self.server_path = server_path
        self._tools_cache = None
    
    async def _list_tools_async(self) -> list[dict]:
        """Fetch available tools from the MCP server."""
        async with Client(self.server_path) as client:
            tools = await client.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
                for tool in tools
            ]
    
    async def _call_tool_async(self, name: str, args: dict) -> Any:
        """Execute a tool on the MCP server."""
        async with Client(self.server_path) as client:
            result = await client.call_tool(name, args)
            # Extract text content from result
            if hasattr(result, 'content') and result.content:
                for item in result.content:
                    if hasattr(item, 'text'):
                        return item.text
            return str(result)
    
    def list_tools(self) -> list[dict]:
        """Synchronous wrapper to list available tools."""
        return asyncio.run(self._list_tools_async())
    
    def call_tool(self, name: str, args: dict = None) -> str:
        """
        Synchronous wrapper to execute a tool.
        
        Args:
            name: Name of the tool to call
            args: Arguments to pass to the tool
            
        Returns:
            Tool execution result as a string
        """
        return asyncio.run(self._call_tool_async(name, args or {}))
    
    def _clean_schema_for_gemini(self, schema: dict) -> dict:
        """
        Clean MCP schema to be compatible with Gemini's function calling.
        
        Uses a whitelist approach - only keeps fields Gemini accepts.
        """
        if not isinstance(schema, dict):
            return schema
        
        # Fields that Gemini accepts in Schema
        allowed_fields = {'type', 'properties', 'required', 'description', 'enum', 'items'}
        
        cleaned = {}
        for key, value in schema.items():
            if key not in allowed_fields:
                continue
            if key == 'properties' and isinstance(value, dict):
                # Recursively clean property definitions
                cleaned[key] = {
                    prop_name: self._clean_schema_for_gemini(prop_def)
                    for prop_name, prop_def in value.items()
                }
            elif isinstance(value, dict):
                cleaned[key] = self._clean_schema_for_gemini(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    self._clean_schema_for_gemini(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        return cleaned
    
    def get_tool_declarations(self) -> list[dict]:
        """
        Get tool declarations in Gemini function calling format.
        
        Returns:
            List of tool declarations for Gemini's function_declarations format
        """
        if self._tools_cache is None:
            self._tools_cache = self.list_tools()
        
        declarations = []
        for tool in self._tools_cache:
            # Clean the schema for Gemini compatibility
            clean_params = self._clean_schema_for_gemini(tool["parameters"])
            declarations.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": clean_params
            })
        return declarations


# Default client instance pointing to the tools server
def get_default_client() -> MCPToolClient:
    """Get the default MCP client for Athena tools."""
    # Resolve path relative to this file's location
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(tools_dir, "mcp_server.py")
    return MCPToolClient(server_path)
