import { Message } from '../src/Message';

const { spawn } = require('child_process');
const path = require('path');
const net = require('net');
let serverProcess: any;
let mockPort: number;
let message: Message | undefined;
const originalWindow = (globalThis as any).window;

beforeAll(async () => {
    // Let the OS choose a port so this test cannot connect to a leftover server.
    const reservation = net.createServer();
    await new Promise<void>(resolve => reservation.listen(0, '127.0.0.1', resolve));
    mockPort = reservation.address().port;
    await new Promise<void>(resolve => reservation.close(resolve));

    const python = path.resolve(__dirname, '../../../.venv',
        process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    serverProcess = spawn(python, ['-m', 'uvicorn', 'server:app', '--host', '127.0.0.1', '--port', String(mockPort)], {
        cwd: __dirname,
        stdio: 'inherit',
    });
    let startupError: Error | undefined;
    serverProcess.on('error', (error: Error) => { startupError = error; });
    const deadline = Date.now() + 10000;
    while (Date.now() < deadline) {
        if (startupError) throw startupError;
        if (serverProcess.exitCode !== null) throw new Error('Test server exited before becoming ready');
        try {
            const response = await fetch(`http://127.0.0.1:${mockPort}/openapi.json`);
            if (response.ok) return;
        } catch { /* The server has not bound its socket yet. */ }
        await new Promise(resolve => setTimeout(resolve, 50));
    }
    throw new Error('Timed out waiting for the test server');
}, 15000);

afterAll(async () => {
    await message?.disconnect();
    if (serverProcess?.pid && serverProcess.exitCode === null) {
        await new Promise<void>(resolve => {
            const timeout = setTimeout(() => serverProcess.kill('SIGKILL'), 5000);
            serverProcess.once('exit', () => { clearTimeout(timeout); resolve(); });
            serverProcess.kill();
        });
    }
    if (originalWindow === undefined) delete (globalThis as any).window;
    else (globalThis as any).window = originalWindow;
}, 10000);

it('waits for callbacks and closes the WebSocket before completing the request', async () => {
    (globalThis as any).window = { location: { href: `http://127.0.0.1:${mockPort}` } };
    message = new Message('127.0.0.1', mockPort);
    const callback1 = jest.fn();
    const callback2 = jest.fn();
    const result = await message.post('start-task', undefined, { callback1, callback2 });
    expect(result.type).toBe('finish');
    expect(callback1).toHaveBeenCalledWith('value1');
    expect(callback2).toHaveBeenCalledWith('value2');
    expect(message.active_requests).toBe(0);
    expect(message.ws).toBeUndefined();
    expect(message.uuid).toBeUndefined();
    expect(message.listening_callbacks).toEqual({});
}, 10000);
