# X MCP Server Setup Guide

## Overview

This guide explains how to configure and use the X MCP Server with Claude Desktop and other MCP clients.

## Prerequisites

1. X API credentials (API Key, API Secret, Access Token, Access Token Secret)
2. Claude Desktop or another MCP-compatible client
3. Python 3.13+ and `uv` package manager

## Configuration

### Claude Desktop Configuration

The X MCP Server requires X API credentials to be provided as environment variables through the Claude Desktop configuration file.

**Configuration File Location**:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

### Configuration Method 1: Using Entry Point (推奨 - npx スタイル)

パッケージのエントリーポイントを使用する、最もクリーンな方法です。

**前提条件**: プロジェクトディレクトリで一度だけ実行:
```bash
cd /path/to/twitter
uv pip install -e .
```

**Claude Desktop 設定**:
```json
{
  "mcpServers": {
    "x-client": {
      "command": "/absolute/path/to/twitter/.venv/bin/x-mcp-server",
      "env": {
        "X_API_KEY": "your-api-key-here",
        "X_API_SECRET": "your-api-secret-here",
        "X_ACCESS_TOKEN": "your-access-token-here",
        "X_ACCESS_TOKEN_SECRET": "your-access-token-secret-here"
      }
    }
  }
}
```

**メリット**:
- ✅ `npx` スタイルのシンプルな呼び出し
- ✅ パッケージの標準的な配布方法
- ✅ コマンド名が明確 (`x-mcp-server`)
- ✅ 依存関係が自動解決

**仕組み**:
- `pyproject.toml` の `[project.scripts]` でエントリーポイント定義
- `uv pip install -e .` で `.venv/bin/x-mcp-server` スクリプトが生成
- スクリプトは自動的にプロジェクトの `.venv` を使用

### Configuration Method 2: Using Launcher Script

シェルスクリプトを使用する方法です。

```json
{
  "mcpServers": {
    "x-client": {
      "command": "/absolute/path/to/twitter/scripts/run_mcp_server.sh",
      "env": {
        "X_API_KEY": "your-api-key-here",
        "X_API_SECRET": "your-api-secret-here",
        "X_ACCESS_TOKEN": "your-access-token-here",
        "X_ACCESS_TOKEN_SECRET": "your-access-token-secret-here"
      }
    }
  }
}
```

**メリット**:
- ✅ インストール不要
- ✅ 自動的に正しいディレクトリに移動
- ✅ カスタマイズ可能

### Configuration Method 3: Using uv directly

`uv` コマンドを直接使用する方法です。

```json
{
  "mcpServers": {
    "x-client": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/twitter",
        "python",
        "-m",
        "x_client.integrations.mcp_server"
      ],
      "env": {
        "X_API_KEY": "your-api-key-here",
        "X_API_SECRET": "your-api-secret-here",
        "X_ACCESS_TOKEN": "your-access-token-here",
        "X_ACCESS_TOKEN_SECRET": "your-access-token-secret-here"
      }
    }
  }
}
```

**メリット**:
- ✅ インストール不要
- ✅ `uv` の機能を直接利用

**Important**:
- Replace `/absolute/path/to/twitter` with the actual absolute path to your project directory
- Replace the credential values with your actual X API credentials
- **Never commit this file to version control** - it contains sensitive credentials
- Both methods work correctly, but Method 1 (launcher script) is more robust

### Alternative: Using .env File (More Secure)

Instead of putting credentials directly in the JSON config, you can use a `.env` file:

1. Create `.env` file in your project root:
```bash
X_API_KEY=your-api-key-here
X_API_SECRET=your-api-secret-here
X_ACCESS_TOKEN=your-access-token-here
X_ACCESS_TOKEN_SECRET=your-access-token-secret-here
```

2. Update Claude Desktop config to use the .env file:
```json
{
  "mcpServers": {
    "x-client": {
      "command": "bash",
      "args": [
        "-c",
        "cd /absolute/path/to/twitter && source .env && uv run python -m x_client.integrations.mcp_server"
      ]
    }
  }
}
```

3. Add `.env` to `.gitignore`:
```bash
echo ".env" >> .gitignore
```

## Obtaining X API Credentials

1. Go to [X Developer Portal](https://developer.x.com/en/portal/dashboard)
2. Create a new App or select an existing one
3. Navigate to "Keys and Tokens"
4. Generate:
   - API Key and Secret (OAuth 1.0a)
   - Access Token and Secret (with Read/Write permissions)

## Verification

After configuring Claude Desktop:

1. **Restart Claude Desktop** completely (Quit and reopen)
2. Open a new conversation
3. Type: "List available X API tools"
4. Claude should respond with the 10 available tools:
   - `create_post`
   - `delete_post`
   - `get_post`
   - `search_recent_posts`
   - `create_thread`
   - `repost_post`
   - `undo_repost`
   - `upload_image`
   - `upload_video`
   - `get_auth_status`

5. Test authentication: "Check my X authentication status"
   - Claude will call `get_auth_status` and report whether you're authenticated

## Usage Examples

### Example 1: Create a Post
```
User: Post to X: "Hello from Claude with MCP! 🚀"

Claude will:
1. Call create_post tool
2. Return the post ID and confirmation
```

### Example 2: Create a Thread
```
User: Create a thread about AI safety with these points:
- AI alignment is crucial
- We need robust testing
- Transparency builds trust

Claude will:
1. Call create_thread tool
2. Split content intelligently
3. Post as a connected thread
4. Return all post IDs
```

### Example 3: Search Posts
```
User: Find recent posts about "MCP protocol"

Claude will:
1. Call search_recent_posts
2. Return matching posts with authors and timestamps
```

### Example 4: Upload Media and Post
```
User: Upload this image at /path/to/image.jpg and post it with caption "Beautiful sunset"

Claude will:
1. Call upload_image
2. Get media_id from response
3. Call create_post with media_id and text
4. Return confirmation
```

## Troubleshooting

### Server Not Appearing in Claude

**Symptom**: Claude doesn't recognize X tools

**Solutions**:
1. Verify configuration file location and syntax (valid JSON)
2. Check that all paths are **absolute**, not relative
3. Restart Claude Desktop completely
4. Check Claude's logs for errors:
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%APPDATA%\Claude\logs\`

### Authentication Errors

**Symptom**: "Authentication failed" or similar errors

**Solutions**:
1. Verify credentials are correct in config
2. Check that Access Token has Read/Write permissions
3. Test credentials independently:
   ```bash
   cd /path/to/twitter
   export X_API_KEY="..."
   export X_API_SECRET="..."
   export X_ACCESS_TOKEN="..."
   export X_ACCESS_TOKEN_SECRET="..."
   uv run python -c "from x_client.factory import XClientFactory; from x_client.config import ConfigManager; client = XClientFactory.create_from_config(ConfigManager()); print('Auth OK')"
   ```

### Rate Limit Issues

**Symptom**: "Rate limit exceeded" errors

**Solutions**:
1. Check remaining quota: Ask Claude to call `get_auth_status`
2. Wait for rate limit reset (shown in error message)
3. Consider Twitter API tier limits

### Server Crashes or Hangs

**Symptom**: Server stops responding

**Solutions**:
1. Check server logs in Claude Desktop logs directory
2. Test server manually:
   ```bash
   uv run python -m x_client.integrations.mcp_server
   ```
3. Verify all dependencies are installed:
   ```bash
   uv sync
   ```

## Manual Testing

You can test the server directly without Claude:

```bash
# Run server
uv run python -m x_client.integrations.mcp_server

# In another terminal, send test requests
uv run python scripts/test_mcp_server.py
```

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use .env files** and add them to `.gitignore`
3. **Rotate credentials** regularly
4. **Limit token permissions** to only what's needed
5. **Monitor API usage** to detect unauthorized access

## VS Code Configuration

If using VS Code with Copilot or other MCP clients:

```json
{
  "mcp.servers": {
    "x-client": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/twitter",
        "python",
        "-m",
        "x_client.integrations.mcp_server"
      ],
      "env": {
        "X_API_KEY": "your-api-key-here",
        "X_API_SECRET": "your-api-secret-here",
        "X_ACCESS_TOKEN": "your-access-token-here",
        "X_ACCESS_TOKEN_SECRET": "your-access-token-secret-here"
      }
    }
  }
}
```

## Advanced Configuration

### Custom Logging Level

Set `PYTHONUNBUFFERED=1` and `LOG_LEVEL` in the env config:

```json
{
  "mcpServers": {
    "x-client": {
      "command": "uv",
      "args": ["run", "python", "-m", "x_client.integrations.mcp_server"],
      "env": {
        "X_API_KEY": "...",
        "X_API_SECRET": "...",
        "X_ACCESS_TOKEN": "...",
        "X_ACCESS_TOKEN_SECRET": "...",
        "LOG_LEVEL": "DEBUG",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Using with Docker (Future)

While not currently implemented, the server could be containerized:

```bash
# Build
docker build -t x-mcp-server .

# Run
docker run -i --rm \
  -e X_API_KEY="..." \
  -e X_API_SECRET="..." \
  -e X_ACCESS_TOKEN="..." \
  -e X_ACCESS_TOKEN_SECRET="..." \
  x-mcp-server
```

## Support

For issues or questions:
1. Check this documentation
2. Review server logs
3. Test credentials independently
4. Open an issue on the project repository
