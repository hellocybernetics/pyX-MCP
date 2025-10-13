"""
Standard MCP server implementation for X API client.

This module provides a Model Context Protocol (MCP) compliant server that
exposes X API operations as tools. It uses the official MCP SDK with stdio
transport for seamless integration with AI assistants like Claude Desktop.

Usage:
    python -m x_client.integrations.mcp_server

    Or with uv:
    uv run python -m x_client.integrations.mcp_server

Configuration:
    Set environment variables for X API credentials:
    - X_API_KEY
    - X_API_SECRET
    - X_ACCESS_TOKEN
    - X_ACCESS_TOKEN_SECRET
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from x_client import __version__
from x_client.integrations.mcp_adapter import XMCPAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class XMCPServer:
    """
    MCP server for X API operations.

    This server wraps the XMCPAdapter to provide standard MCP protocol
    compliance, enabling AI assistants to interact with the X API through
    a well-defined tool interface.
    """

    def __init__(self) -> None:
        """Initialize the MCP server."""
        self.server = Server(
            name="x-client",
            version=__version__,
            instructions=(
                "X API MCP Server - Provides tools for posting, searching, "
                "and managing content on X (formerly Twitter). "
                "Supports posts, threads, media uploads, reposts, and search."
            ),
        )
        self.adapter = XMCPAdapter()

        # Register handlers
        self._register_handlers()

        logger.info("X MCP Server initialized")

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """
            List all available X API tools.

            Returns:
                List of Tool objects with names, descriptions, and input schemas
            """
            logger.debug("Handling list_tools request")

            tool_schemas = self.adapter.get_tool_schemas()
            tools = []

            for name, schema in tool_schemas.items():
                tool = Tool(
                    name=name,
                    description=schema["description"],
                    inputSchema=schema["input_schema"],
                )
                tools.append(tool)

            logger.info(f"Returning {len(tools)} tools")
            return tools

        @self.server.call_tool()
        async def handle_call_tool(
            name: str,
            arguments: dict[str, Any],
        ) -> list[TextContent]:
            """
            Execute an X API tool.

            Args:
                name: Tool name (e.g., 'create_post', 'upload_image')
                arguments: Tool-specific arguments as defined in input schema

            Returns:
                List containing a single TextContent with the result

            Raises:
                ValueError: If tool name is invalid
                RuntimeError: If tool execution fails
            """
            logger.info(f"Calling tool: {name}")
            logger.debug(f"Arguments: {arguments}")

            # Validate tool exists
            if not hasattr(self.adapter, name):
                error_msg = f"Unknown tool: {name}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            try:
                # Execute tool via adapter
                method = getattr(self.adapter, name)
                result = method(arguments)

                # Check if result contains an error
                if isinstance(result, dict) and "error_type" in result:
                    logger.warning(f"Tool returned error: {result.get('message')}")
                    # Return error as result (not raise - let client handle)
                    result_json = json.dumps(result, indent=2)
                else:
                    logger.info(f"Tool {name} completed successfully")
                    result_json = json.dumps(result, indent=2)

                return [
                    TextContent(
                        type="text",
                        text=result_json,
                    )
                ]

            except Exception as e:
                error_msg = f"Tool execution failed: {str(e)}"
                logger.error(error_msg, exc_info=True)

                # Return structured error response
                error_result = {
                    "error_type": type(e).__name__,
                    "message": str(e),
                }

                return [
                    TextContent(
                        type="text",
                        text=json.dumps(error_result, indent=2),
                    )
                ]

    async def run_stdio(self) -> None:
        """
        Run the MCP server with stdio transport.

        This method starts the server and handles communication via stdin/stdout,
        which is the standard transport mechanism for MCP servers integrated with
        AI assistants.
        """
        logger.info("Starting X MCP Server with stdio transport")

        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server ready - listening on stdio")

            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def async_main(args: argparse.Namespace) -> None:
    """
    Async entry point for the MCP server.

    Creates and runs the server instance based on parsed arguments.
    """
    try:
        server = XMCPServer()
        if args.stdio:
            await server.run_stdio()
        else:
            # Default to stdio if no mode is specified
            await server.run_stdio()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


def main() -> None:
    """
    Main entry point for the MCP server.

    This function is called when:
    1. Module is executed directly: `python -m x_client.integrations.mcp_server`
    2. Entry point is invoked: `uvx --from . x-mcp-server`
    3. Installed command is run: `x-mcp-server` (after `uv pip install -e .`)
    """
    parser = argparse.ArgumentParser(description="X API MCP Server")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Run server with stdio transport (default)",
    )
    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
