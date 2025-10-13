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
const { existsSync } = require('fs');
const { join } = require('path');
const os = require('os');

// Package root directory
const PKG_ROOT = join(__dirname, '..');

// Python environment paths
const VENV_DIR = join(PKG_ROOT, '.venv');
const PYTHON_BIN = join(VENV_DIR, 'bin', 'python');
const UV_BIN = join(VENV_DIR, 'bin', 'uv');

// Check if running in npx cache
const isNpxCache = PKG_ROOT.includes('.npm/_npx') || PKG_ROOT.includes('node_modules');

/**
 * Check if uv is available
 */
async function hasUv() {
  return new Promise((resolve) => {
    const proc = spawn('uv', ['--version'], { stdio: 'ignore' });
    proc.on('close', (code) => resolve(code === 0));
    proc.on('error', () => resolve(false));
  });
}

/**
 * Install uv using the official installer
 */
async function installUv() {
  console.error('[x-mcp-server] Installing uv...');

  return new Promise((resolve, reject) => {
    const curlProc = spawn('curl', ['-LsSf', 'https://astral.sh/uv/install.sh']);
    const shProc = spawn('sh', [], { stdio: ['pipe', 'inherit', 'inherit'] });

    curlProc.stdout.pipe(shProc.stdin);

    shProc.on('close', (code) => {
      if (code === 0) {
        console.error('[x-mcp-server] uv installed successfully');
        resolve();
      } else {
        reject(new Error(`uv installation failed with code ${code}`));
      }
    });

    curlProc.on('error', reject);
    shProc.on('error', reject);
  });
}

/**
 * Setup Python environment using uv
 */
async function setupPythonEnv() {
  if (existsSync(VENV_DIR)) {
    // Environment already exists
    return;
  }

  console.error('[x-mcp-server] Setting up Python environment...');

  return new Promise((resolve, reject) => {
    const proc = spawn('uv', ['sync'], {
      cwd: PKG_ROOT,
      stdio: ['ignore', 'inherit', 'inherit'],
      env: { ...process.env }
    });

    proc.on('close', (code) => {
      if (code === 0) {
        console.error('[x-mcp-server] Python environment ready');
        resolve();
      } else {
        reject(new Error(`Python environment setup failed with code ${code}`));
      }
    });

    proc.on('error', reject);
  });
}

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
    // Check if uv is available
    const uvAvailable = await hasUv();

    if (!uvAvailable) {
      console.error('[x-mcp-server] uv not found, installing...');
      await installUv();

      // Verify installation
      if (!(await hasUv())) {
        throw new Error('Failed to install uv. Please install manually: https://docs.astral.sh/uv/');
      }
    }

    // Setup Python environment (first run only)
    await setupPythonEnv();

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
