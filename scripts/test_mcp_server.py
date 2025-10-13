#!/usr/bin/env python
"""
Test script for X MCP Server.

This script sends MCP protocol messages to the server via stdio
to verify that the server correctly handles list_tools and call_tool requests.

Usage:
    uv run python scripts/test_mcp_server.py
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path


async def send_jsonrpc_request(process: subprocess.Popen, request: dict) -> dict:
    """
    Send a JSON-RPC request to the MCP server and get response.

    Args:
        process: The server process
        request: JSON-RPC request dictionary

    Returns:
        JSON-RPC response dictionary
    """
    # Send request
    request_line = json.dumps(request) + "\n"
    process.stdin.write(request_line.encode())
    process.stdin.flush()

    # Read response
    response_line = process.stdout.readline()
    if not response_line:
        raise RuntimeError("No response from server")

    return json.loads(response_line)


async def test_mcp_server():
    """Test the MCP server with various requests."""
    print("=" * 80)
    print("X MCP Server Test Suite")
    print("=" * 80)

    # Start the server
    print("\n[1/4] Starting MCP server...")
    process = subprocess.Popen(
        ["uv", "run", "python", "-m", "x_client.integrations.mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent,
    )

    try:
        # Wait for server to start
        await asyncio.sleep(1)

        # Test 1: Initialize
        print("\n[2/4] Testing initialization...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        }

        init_response = await send_jsonrpc_request(process, init_request)
        print(f"✓ Server initialized: {init_response.get('result', {}).get('serverInfo', {}).get('name')}")

        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        process.stdin.write((json.dumps(initialized_notification) + "\n").encode())
        process.stdin.flush()

        # Test 2: List tools
        print("\n[3/4] Testing list_tools...")
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }

        tools_response = await send_jsonrpc_request(process, list_tools_request)
        tools = tools_response.get("result", {}).get("tools", [])
        print(f"✓ Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")

        # Test 3: Call tool (get_auth_status - should work without credentials)
        print("\n[4/4] Testing call_tool (get_auth_status)...")
        call_tool_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_auth_status",
                "arguments": {},
            },
        }

        call_response = await send_jsonrpc_request(process, call_tool_request)
        result = call_response.get("result", {})
        content = result.get("content", [])

        if content:
            result_data = json.loads(content[0]["text"])
            print(f"✓ Tool executed successfully:")
            print(f"  Authenticated: {result_data.get('authenticated')}")
            if result_data.get("authenticated"):
                print(f"  User ID: {result_data.get('user_id')}")
        else:
            print("✗ No content in response")

        print("\n" + "=" * 80)
        print("All tests completed successfully! ✓")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        stderr = process.stderr.read().decode()
        if stderr:
            print(f"\nServer stderr:\n{stderr}")
        sys.exit(1)

    finally:
        # Cleanup
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
