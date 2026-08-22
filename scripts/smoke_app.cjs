#!/usr/bin/env node
// Smoke-test a built SSUI executable: launch it, make sure the process stays
// alive for the wait window (default 15s), then terminate it.
//
// Usage:
//   node scripts/smoke_app.cjs <executable> [seconds]
//   SMOKE_ARGS='["--flag", "value"]' node scripts/smoke_app.cjs <executable> [seconds]
//
// Used by .github/workflows/release.yml after `yarn package`: if the release
// binary cannot start (missing DLL, immediate crash, ...) the release is not
// formalized.

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const exe = process.argv[2];
const seconds = Number(process.argv[3] || process.env.SMOKE_SECONDS || 15);
const rawArgs = process.env.SMOKE_ARGS || "";
let args = [];
if (rawArgs.startsWith("[")) {
  try {
    args = JSON.parse(rawArgs);
  } catch (err) {
    fail(`SMOKE_ARGS is not valid JSON: ${err.message}`);
  }
} else if (rawArgs) {
  args = rawArgs.split(/\s+/).filter(Boolean);
}

function fail(message) {
  console.error(`error: ${message}`);
  process.exit(1);
}

if (!exe) {
  console.error("usage: node scripts/smoke_app.cjs <executable> [seconds]");
  process.exit(2);
}
if (!Number.isFinite(seconds) || seconds <= 0) {
  fail(`invalid wait window: ${process.argv[3] || process.env.SMOKE_SECONDS}`);
}
// Bare command names (no path separator) are resolved by the OS through PATH;
// only paths with a separator are checked up front.
if (/[\\/]/.test(exe)) {
  if (!fs.existsSync(exe)) {
    fail(`executable not found: ${exe}`);
  }
  const stat = fs.statSync(exe);
  if (stat.size === 0) {
    fail(`executable is empty: ${exe}`);
  }
}

console.log(`smoke: launching ${path.resolve(exe)}${args.length ? ` ${args.join(" ")}` : ""}`);
const child = spawn(exe, args, { stdio: "ignore", windowsHide: false });
let finished = false;

const timer = setTimeout(() => {
  if (finished) return;
  finished = true;
  const alive = child.exitCode === null && child.signalCode === null;
  if (!alive) {
    console.error(`error: ${exe} exited during the wait window`);
  } else {
    console.log(`OK: ${exe} stayed alive for ${seconds}s`);
  }
  try {
    child.kill();
  } catch {
    // already gone
  }
  process.exit(alive ? 0 : 1);
}, seconds * 1000);

child.on("error", (err) => {
  if (finished) return;
  clearTimeout(timer);
  finished = true;
  fail(`failed to launch ${exe}: ${err.message}`);
});

child.on("exit", (code, signal) => {
  if (finished) return;
  clearTimeout(timer);
  finished = true;
  console.error(`error: ${exe} exited early (code=${code}, signal=${signal})`);
  process.exit(1);
});
