#!/usr/bin/env node

/**
 * X MCP Server - NPM Wrapper
 *
 * This script acts as a Node.js wrapper that automatically:
 * 1. Installs uv if not present
 * 2. Sets up Python environment
 * 3. Installs Python dependencies
 * 4. Runs the Python MCP server
 */

const { spawn } = require('child_process');
const { ensureSetup, PKG_ROOT } = require('../lib/setup');

/**
 * Run the Python MCP server
 */
function runServer() {
  // Use uv run to ensure correct environment
  const proc = spawn('uv', ['run', 'python', '-m', 'x_client.integrations.mcp_server'], {
    cwd: PKG_ROOT,
    stdio: 'inherit',
    env: { ...process.env }
  });

  proc.on('error', (err) => {
    console.error('[x-mcp-server] Failed to start server:', err.message);
    process.exit(1);
  });

  proc.on('close', (code) => {
    process.exit(code || 0);
  });

  // Forward signals to Python process
  process.on('SIGTERM', () => proc.kill('SIGTERM'));
  process.on('SIGINT', () => proc.kill('SIGINT'));
}

/**
 * Main entry point
 */
async function main() {
  try {
    await ensureSetup();

    // Run the server
    runServer();

  } catch (error) {
    console.error('[x-mcp-server] Setup failed:', error.message);
    console.error('');
    console.error('Troubleshooting:');
    console.error('  1. Ensure you have Python 3.13+ installed');
    console.error('  2. Try installing uv manually: curl -LsSf https://astral.sh/uv/install.sh | sh');
    console.error('  3. Check your internet connection');
    process.exit(1);
  }
}

main();
