import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, mkdir, readFile, writeFile, stat } from 'node:fs/promises';
import { createWriteStream } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'node:net';
import { createServer as createHttpServer } from 'node:http';
import { createHash } from 'node:crypto';
import { remote } from 'webdriverio';

const desktop = fileURLToPath(new URL('../../', import.meta.url));
const binary = path.join(desktop, 'src-tauri/target/debug/examples', process.platform === 'win32' ? 'ssui-native-test.exe' : 'ssui-native-test');
const artifacts = path.resolve(desktop, '../native-test-results');
const pythonProbe = spawnSync(process.env.SSUI_TEST_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'), ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' });
assert.equal(pythonProbe.status, 0, `Python required for lightweight fixtures: ${pythonProbe.stderr}`);
const python = pythonProbe.stdout.trim();

async function eventually(check, description, timeout = 15_000) {
  const deadline = Date.now() + timeout;
  let error;
  while (Date.now() < deadline) {
    try { const value = await check(); if (value) return value; } catch (e) { error = e; }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(`Timed out: ${description}`, { cause: error });
}
async function availablePort() {
  const socket = createServer();
  socket.listen(0, '127.0.0.1'); await once(socket, 'listening');
  const port = socket.address().port; await new Promise(resolve => socket.close(resolve));
  return port;
}
const alive = pid => { try { process.kill(Number(pid), 0); return true; } catch { return false; } };

async function fixture(t) {
  const root = await mkdtemp(path.join(tmpdir(), 'ssui native 中文 & '));
  await mkdir(artifacts, { recursive: true });
  for (const module of ['server', 'ss_executor']) {
    await writeFile(path.join(root, `${module}.py`), `
import http.server, json, os
from pathlib import Path
server = http.server.HTTPServer(('127.0.0.1', 0), http.server.SimpleHTTPRequestHandler)
Path('${module}.ready').write_text(json.dumps({'pid': os.getpid(), 'parent_pid': os.getppid(), 'port': server.server_port}))
print('ready', flush=True)
server.serve_forever()
`);
  }
  let browser, app, log;
  let generation = 0;
  const ready = module => readFile(path.join(root, `${module}.ready`), 'utf8').then(JSON.parse);
  const stop = async () => {
    if (browser) {
      for (const kind of ['server', 'executor']) {
        try { await browser.$(`#${kind}-stop`).click(); } catch {}
      }
      try { await browser.$('#app-close').click(); } catch {}
      await browser.deleteSession().catch(() => {}); browser = undefined;
    }
    if (app && app.exitCode === null && app.signalCode === null) {
      const exited = once(app, 'exit');
      const timer = setTimeout(() => app.kill(), 3000);
      await exited; clearTimeout(timer);
    }
    log?.end();
    // Only fixture children are eligible for fallback cleanup.
    for (const module of ['server', 'ss_executor']) {
      const info = await ready(module).catch(() => null);
      if (info && alive(info.pid)) { process.kill(info.pid); await eventually(() => !alive(info.pid), 'fixture cleanup'); }
    }
  };
  t.after(async () => {
    if (t.passed === false && browser) {
      await browser.saveScreenshot(path.join(artifacts, `${t.name.replace(/\W/g, '_')}.png`)).catch(() => {});
      await writeFile(path.join(artifacts, 'page.html'), await browser.getPageSource().catch(() => '')).catch(() => {});
    }
    await stop();
  });
  async function start() {
    const port = await availablePort();
    const profile = path.join(root, 'profile');
    await mkdir(profile, { recursive: true });
    log = createWriteStream(path.join(artifacts, `${t.name.replace(/\W/g, '_')}-${generation++}.log`));
    app = spawn(binary, [], { cwd: root, env: { ...process.env,
      TAURI_WEBDRIVER_PORT: String(port), XDG_CONFIG_HOME: profile, XDG_DATA_HOME: profile,
      WEBKIT_DISABLE_DMABUF_RENDERER: '1', RUST_BACKTRACE: '1',
    }, stdio: ['ignore', 'pipe', 'pipe'] });
    let launchError;
    app.on('error', error => { launchError = error; });
    app.stdout.pipe(log); app.stderr.pipe(log);
    await eventually(async () => {
      if (launchError) throw launchError;
      if (app.exitCode !== null || app.signalCode !== null) {
        throw new Error(`Native app exited before WebDriver startup: code=${app.exitCode}, signal=${app.signalCode}`);
      }
      return (await fetch(`http://127.0.0.1:${port}/status`)).ok;
    }, 'embedded WebDriver startup', 30_000);
    // The driver starts listening before WebView2 registers its first window.
    const windowDeadline = Date.now() + 30_000;
    while (!browser) {
      try {
        browser = await remote({ hostname: '127.0.0.1', port, logLevel: 'error',
          connectionRetryCount: 0, waitforTimeout: 5000, capabilities: { browserName: 'wry' },
        });
      } catch (error) {
        if (!/No window could be found|no such window/i.test(String(error)) ||
            Date.now() >= windowDeadline || app.exitCode !== null || app.signalCode !== null) throw error;
        await new Promise(resolve => setTimeout(resolve, 250));
      }
    }
    await browser.$('#root-path').waitForExist();
    await browser.$('#root-path').setValue(root);
    await browser.$('#python-path').setValue(python);
    return browser;
  }
  return { root, ready, start, stop, get browser() { return browser; } };
}

async function click(browser, id, text) {
  const button = await browser.$(`#${id}`);
  await button.waitForEnabled(); await button.click();
  await browser.waitUntil(async () => (await browser.$('#result').getText()).includes(text), {
    timeout: 15_000, timeoutMsg: `${id}: expected ${text}`,
  });
  await button.waitForEnabled();
}

test('real IPC server and executor lifecycle releases processes and ports', { timeout: 120_000 }, async t => {
  const app = await fixture(t); const browser = await app.start();
  for (const [kind, module] of [['server', 'server'], ['executor', 'ss_executor']]) {
    await click(browser, `${kind}-start`, '启动成功');
    const firstManagedPid = Number((await browser.$('#result').getText()).match(/进程 ID: (\d+)/)[1]);
    const first = await eventually(() => app.ready(module), 'child readiness');
    // Windows venv python.exe may be a launcher; HTTP runs in its child.
    assert.ok(first.pid === firstManagedPid || first.parent_pid === firstManagedPid, 'worker belongs to managed process');
    assert.equal((await fetch(`http://127.0.0.1:${first.port}/`)).ok, true);
    await click(browser, `${kind}-status`, String(firstManagedPid));
    await click(browser, `${kind}-start`, '启动成功');
    assert.match(await browser.$('#result').getText(), new RegExp(`进程 ID: ${firstManagedPid}$`));
    assert.equal((await app.ready(module)).pid, first.pid, 'duplicate start keeps the same child');
    await click(browser, `${kind}-restart`, '重启成功');
    const secondManagedPid = Number((await browser.$('#result').getText()).match(/进程 ID: (\d+)/)[1]);
    assert.notEqual(secondManagedPid, firstManagedPid);
    const second = await eventually(async () => { const value = await app.ready(module); return value.pid !== first.pid && value; }, 'replacement child');
    assert.ok(second.pid === secondManagedPid || second.parent_pid === secondManagedPid, 'replacement worker belongs to managed process');
    await eventually(() => !alive(first.pid) && !alive(firstManagedPid), 'old launcher and worker reaped');
    await click(browser, `${kind}-stop`, '已停止');
    await eventually(() => !alive(second.pid) && !alive(secondManagedPid), 'stopped launcher and worker reaped');
    await eventually(async () => { try { await fetch(`http://127.0.0.1:${second.port}/`); return false; } catch { return true; } }, 'listener released');
    await click(browser, `${kind}-status`, '未在运行中');
  }
});

test('real IPC reports spawn error and retries with valid executable', { timeout: 90_000 }, async t => {
  const app = await fixture(t); const browser = await app.start();
  await browser.$('#python-path').setValue(path.join(app.root, 'missing-python'));
  await click(browser, 'server-start', 'ERROR:');
  await browser.$('#python-path').setValue(python);
  await click(browser, 'server-start', '启动成功');
  await click(browser, 'python-run', 'native output');
  await click(browser, 'server-stop', '已停止');
});

test('native store persists settings across application restart', { timeout: 90_000 }, async t => {
  const app = await fixture(t); let browser = await app.start();
  await click(browser, 'store-save', 'stored dark');
  assert.match(await readFile(path.join(app.root, 'settings.json'), 'utf8'), /dark/);
  await app.stop(); browser = await app.start();
  await click(browser, 'store-load', 'loaded dark');
});

test('native download verifies bytes and hash, reports failures and cancels active requests', { timeout: 120_000 }, async t => {
  const bytes = Buffer.alloc(2 * 1024 * 1024 + 13, 71);
  let activeSlowRequests = 0;
  const server = createHttpServer((req, res) => {
    if (req.url === '/failure') { res.writeHead(503); res.end('unavailable'); return; }
    const range = req.headers.range?.match(/bytes=(\d+)-(\d+)/);
    const start = range ? Number(range[1]) : 0;
    const end = range ? Number(range[2]) : bytes.length - 1;
    const body = bytes.subarray(start, end + 1);
    res.writeHead(range ? 206 : 200, { 'Content-Length': body.length,
      ...(range ? { 'Content-Range': `bytes ${start}-${end}/${bytes.length}` } : {}),
    });
    if (req.url === '/slow' && range) {
      activeSlowRequests++;
      let offset = 0;
      const timer = setInterval(() => {
        res.write(body.subarray(offset, offset + 1024)); offset += 1024;
        if (offset >= body.length) res.end();
      }, 20);
      res.on('close', () => { clearInterval(timer); activeSlowRequests--; });
    } else res.end(body);
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  t.after(() => { server.closeAllConnections(); server.close(); });
  const base = `http://127.0.0.1:${server.address().port}`;
  const app = await fixture(t); const browser = await app.start();
  const status = async expected => eventually(async () => {
    await browser.$('#download-status').click();
    return (await browser.$('#result').getText()).includes(`"status":"${expected}"`);
  }, `download ${expected}`);
  await browser.$('#download-url').setValue(`${base}/success`);
  await browser.$('#download-hash').setValue(createHash('sha256').update(bytes).digest('hex'));
  await click(browser, 'download-start', 'download started');
  await status('Completed');
  assert.deepEqual(await readFile(path.join(app.root, 'download.bin')), bytes);
  assert.match(await browser.$('#download-events').getText(), /download-progress/);
  assert.match(await browser.$('#download-events').getText(), /download-completed/);

  await browser.$('#download-url').setValue(`${base}/bad-hash`);
  await browser.$('#download-hash').setValue('00'.repeat(32));
  await click(browser, 'download-start', 'download started'); await status('Failed');
  await browser.$('#download-url').setValue(`${base}/failure`);
  await click(browser, 'download-start', 'download started'); await status('Failed');
  assert.match(await browser.$('#download-events').getText(), /download-failed/);

  // A distinct target proves cancellation never publishes a completed file.
  const cancelledRoot = path.join(app.root, 'cancelled'); await mkdir(cancelledRoot);
  await browser.$('#root-path').setValue(cancelledRoot);
  await browser.$('#download-url').setValue(`${base}/slow`);
  await browser.$('#download-hash').setValue('');
  await click(browser, 'download-start', 'download started');
  await eventually(() => activeSlowRequests > 0, 'active chunk requests');
  await click(browser, 'download-cancel', 'download cancelled');
  await eventually(() => activeSlowRequests === 0, 'cancel closes HTTP requests');
  await status('Cancelled');
  assert.match(await browser.$('#download-events').getText(), /download-cancelled/);
  assert.equal(await stat(path.join(cancelledRoot, 'download.bin')).then(() => true, () => false), false);
});
