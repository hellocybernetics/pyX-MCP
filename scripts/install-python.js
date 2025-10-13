#!/usr/bin/env node

const { ensureSetup } = require('../lib/setup');

async function main() {
  try {
    await ensureSetup({ installUvIfMissing: false, skipWhenUvMissing: true });
  } catch (error) {
    console.error(`[x-mcp-server] postinstall skipped: ${error.message}`);
  }
}

main();
