#!/bin/bash
# MCP Server launcher script for Claude Desktop
# This ensures the correct working directory and virtual environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT" || exit 1
exec uv run python -m x_client.integrations.mcp_server
