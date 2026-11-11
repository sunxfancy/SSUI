import { UIStateStore } from '../src/UIState';

describe('UI state autosave', () => {
    const request = jest.fn();
    beforeEach(() => { jest.useFakeTimers(); global.fetch = request; request.mockReset(); });
    afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

    it('debounces typing and preserves separate component values', async () => {
        request.mockResolvedValue({ ok: true });
        const store = new UIStateStore({}, 'script_path=example.py&view=functional', jest.fn());
        store.set('/first/prompt', 'first');
        store.set('/second/prompt', 'second');
        store.set('/first/prompt', 'finished');
        await jest.advanceTimersByTimeAsync(300);
        expect(request).toHaveBeenCalledTimes(1);
        expect(JSON.parse(request.mock.calls[0][1].body).state_data).toEqual({
            '/first/prompt': 'finished', '/second/prompt': 'second',
        });
    });

    it('flushes immediately when closing before the debounce expires', async () => {
        request.mockResolvedValue({ ok: true });
        const store = new UIStateStore({}, 'script_path=a', jest.fn());
        store.set('/value', false);
        await store.flush(true);
        expect(JSON.parse(request.mock.calls[0][1].body).state_data).toEqual({ '/value': false });
        expect(request.mock.calls[0][1].keepalive).toBe(true);
    });

    it('serializes in-flight saves and sends edits made while saving', async () => {
        let finish!: (result: { ok: boolean }) => void;
        request.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
        request.mockResolvedValue({ ok: true });
        const store = new UIStateStore({}, 'script_path=a', jest.fn());
        store.set('/value', 'old');
        const first = store.flush();
        store.set('/value', 'new');
        await jest.advanceTimersByTimeAsync(300);
        expect(request).toHaveBeenCalledTimes(1);
        finish({ ok: true });
        await first;
        await jest.advanceTimersByTimeAsync(2000);
        expect(request).toHaveBeenCalledTimes(2);
        expect(JSON.parse(request.mock.calls[1][1].body).state_data['/value']).toBe('new');
    });

    it('sends the final edit on unload even while an autosave is in flight', async () => {
        request.mockReturnValueOnce(new Promise(() => {})).mockResolvedValue({ ok: true });
        const store = new UIStateStore({}, 'script_path=a', jest.fn());
        store.set('/value', 'old');
        void store.flush();
        store.set('/value', 'last edit');
        await store.flush(true);
        const first = JSON.parse(request.mock.calls[0][1].body);
        const last = JSON.parse(request.mock.calls[1][1].body);
        expect(last.state_data['/value']).toBe('last edit');
        expect(last.client_id).toBe(first.client_id);
        expect(last.revision).toBeGreaterThan(first.revision);
    });

    it('keeps unsaved edits after failure and retries', async () => {
        const report = jest.fn();
        request.mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ ok: true });
        const store = new UIStateStore({}, 'script_path=a', report);
        store.set('/value', 0);
        await store.flush();
        expect(report).toHaveBeenLastCalledWith(expect.stringContaining('失败'));
        await jest.advanceTimersByTimeAsync(2000);
        expect(JSON.parse(request.mock.calls[1][1].body).state_data['/value']).toBe(0);
        expect(report).toHaveBeenLastCalledWith('');
    });
});
