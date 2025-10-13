'use strict';

const { spawn } = require('child_process');
const { existsSync } = require('fs');
const { join } = require('path');

const PKG_ROOT = join(__dirname, '..');
const VENV_DIR = join(PKG_ROOT, '.venv');
const UV_BIN = join(VENV_DIR, 'bin', 'uv');

function runProcess(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args, options);

    proc.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${command} ${args.join(' ')} exited with code ${code}`));
      }
    });

    proc.on('error', reject);
  });
}

async function hasUv() {
  try {
    await runProcess('uv', ['--version'], { stdio: 'ignore' });
    return true;
  } catch (error) {
    if (existsSync(UV_BIN)) {
      try {
        await runProcess(UV_BIN, ['--version'], { stdio: 'ignore' });
        return true;
      } catch (_) {
        return false;
      }
    }
    return false;
  }
}

async function installUv(logger = console.error) {
  logger('[x-mcp-server] Installing uv...');

  return new Promise((resolve, reject) => {
    const curlProc = spawn('curl', ['-LsSf', 'https://astral.sh/uv/install.sh']);
    const shProc = spawn('sh', [], { stdio: ['pipe', 'inherit', 'inherit'] });

    curlProc.stdout.pipe(shProc.stdin);

    shProc.on('close', (code) => {
      if (code === 0) {
        logger('[x-mcp-server] uv installed successfully');
        resolve();
      } else {
        reject(new Error(`uv installation failed with code ${code}`));
      }
    });

    curlProc.on('error', reject);
    shProc.on('error', reject);
  });
}

async function setupPythonEnv(options = {}) {
  const { logger = console.error } = options;

  if (existsSync(VENV_DIR)) {
    return;
  }

  logger('[x-mcp-server] Setting up Python environment...');

  await runProcess('uv', ['sync'], {
    cwd: PKG_ROOT,
    stdio: ['ignore', 'inherit', 'inherit'],
    env: { ...process.env }
  });

  logger('[x-mcp-server] Python environment ready');
}

async function ensureSetup(options = {}) {
  const {
    installUvIfMissing = true,
    logger = console.error,
    skipWhenUvMissing = false
  } = options;

  let uvAvailable = await hasUv();

  if (!uvAvailable) {
    if (skipWhenUvMissing) {
      logger('[x-mcp-server] uv not found during setup; skipping environment bootstrap.');
      return;
    }

    if (!installUvIfMissing) {
      throw new Error('uv is required but automatic installation is disabled');
    }

    logger('[x-mcp-server] uv not found, installing...');
    await installUv(logger);
    uvAvailable = await hasUv();
  }

  if (!uvAvailable) {
    throw new Error('Failed to verify uv installation. Install manually: https://docs.astral.sh/uv/');
  }

  await setupPythonEnv({ logger });
}

module.exports = {
  PKG_ROOT,
  VENV_DIR,
  UV_BIN,
  ensureSetup,
  hasUv,
  installUv,
  setupPythonEnv
};
