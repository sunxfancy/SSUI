import { Message } from '../src/Message';

// Deterministic transport tests: no Python service or fixed startup sleeps.
describe('Message transport', () => {
    let socket: FakeSocket;
    const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
    const originalSocket = globalThis.WebSocket;
    class FakeSocket {
        onclose?: () => void;
        onmessage?: (event: { data: string }) => void;
        constructor(public url: string) {
            socket = this;
            queueMicrotask(() => this.send({ type: 'uuid', uuid: 'client' }));
        }
        send(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) }); }
        close = jest.fn(() => this.onclose?.());
    }
    beforeEach(() => {
        Object.defineProperty(globalThis, 'window', { configurable: true, value: { location: { href: 'http://localhost:8000' } } });
        globalThis.WebSocket = FakeSocket as any;
        jest.spyOn(globalThis, 'fetch');
    });
    afterEach(() => {
        jest.restoreAllMocks();
        globalThis.WebSocket = originalSocket;
        if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow);
        else delete (globalThis as any).window;
    });
    it('delivers callbacks arriving before HTTP response and closes connection', async () => {
        const message = new Message(); message.uuid = 'client';
        const callback = jest.fn();
        jest.mocked(fetch).mockImplementation(async () => {
            socket.send({ type: 'callback', request_uuid: 'request', progress: 42 });
            socket.send({ type: 'finish', request_uuid: 'request' });
            return { ok: true, json: async () => ({ request_uuid: 'request', callbacks: ['progress'] }) } as Response;
        });
        await expect(message.post('task', { input: 1 }, { progress: callback })).resolves.toMatchObject({ type: 'finish' });
        expect(callback).toHaveBeenCalledWith(42);
        expect(socket.close).toHaveBeenCalledTimes(1);
        expect(message.active_requests).toBe(0);
        expect(message.message_cache).toEqual({});
        expect(message.listening_callbacks).toEqual({});
    });
    it('rejects HTTP failure and releases callback connection', async () => {
        const message = new Message(); message.uuid = 'client';
        jest.mocked(fetch).mockResolvedValue({ ok: false, status: 503 } as Response);
        await expect(message.post('task', undefined, {})).rejects.toThrow('503');
        expect(socket.close).toHaveBeenCalledTimes(1);
        expect(message.active_requests).toBe(0);
    });
    it('returns JSON without opening callback connection', async () => {
        const message = new Message(); message.uuid = 'client';
        jest.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({ value: 1 }) } as Response);
        await expect(message.post('task')).resolves.toEqual({ value: 1 });
        expect(message.ws).toBeUndefined();
    });
});
