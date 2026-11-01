import React, { createContext, useContext, useEffect, useState } from 'react';

type Values = Record<string, unknown>;
export class UIStateStore {
    private timer?: ReturnType<typeof setTimeout>;
    private pending = false;
    private saving = 0;
    private revision = 0;
    private clientId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
    constructor(public values: Values, private query: string, private report: (message: string) => void) {}
    set(key: string, value: unknown) {
        if (JSON.stringify(this.values[key]) === JSON.stringify(value)) return;
        this.values[key] = value;
        this.pending = true;
        this.revision++;
        clearTimeout(this.timer);
        this.timer = setTimeout(() => void this.flush(), 300);
    }
    flush = async (unloading = false) => {
        clearTimeout(this.timer);
        if (!this.pending || (this.saving && !unloading)) return;
        this.pending = false;
        this.saving++;
        const body = JSON.stringify({ state_data: this.values, client_id: this.clientId, revision: this.revision });
        try {
            const response = await fetch('/api/ui_state_store?' + this.query, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                // Browsers limit outstanding keepalive bodies to about 64 KiB.
                body, keepalive: new Blob([body]).size < 30000,
            });
            if (!response.ok) throw new Error('保存失败');
            this.report('');
        } catch {
            this.pending = true;
            this.report('界面状态保存失败，请检查服务连接后重试。');
        } finally {
            this.saving--;
        }
        if (this.pending) this.timer = setTimeout(() => void this.flush(), 2000);
    };
}

type StateContext = { store: UIStateStore; key: string } | null;
export const UIStateContext = createContext<StateContext>(null);

/** Mount children only after restoration, so defaults never overwrite saved values. */
export function UIStateProvider({ path, view, children }: React.PropsWithChildren<{ path: string; view: string }>) {
    const [store, setStore] = useState<UIStateStore>();
    const [error, setError] = useState('');
    const [outsideProject, setOutsideProject] = useState(false);
    const [attempt, retry] = useState(0);
    useEffect(() => {
        const controller = new AbortController();
        const query = new URLSearchParams({ script_path: path, view }).toString();
        setStore(undefined);
        setOutsideProject(!path);
        if (!path) return;
        fetch('/api/ui_state_load?' + query, { signal: controller.signal })
            .then(async response => {
                if (response.status === 404) {
                    if (!controller.signal.aborted) setOutsideProject(true);
                    return;
                }
                if (!response.ok) throw new Error('读取失败');
                const values = await response.json();
                if (!values || typeof values !== 'object' || Array.isArray(values)) throw new Error('状态格式无效');
                if (!controller.signal.aborted) {
                    setError('');
                    setStore(new UIStateStore(values, query, setError));
                }
            }).catch(() => {
                if (!controller.signal.aborted) setError('界面状态读取失败，请检查服务连接后重试。');
            });
        return () => controller.abort();
    }, [path, view, attempt]);
    useEffect(() => {
        if (!store) return;
        const flush = () => void store.flush(true);
        const hidden = () => { if (document.visibilityState === 'hidden') flush(); };
        window.addEventListener('pagehide', flush);
        document.addEventListener('visibilitychange', hidden);
        return () => {
            window.removeEventListener('pagehide', flush);
            document.removeEventListener('visibilitychange', hidden);
            flush();
        };
    }, [store]);
    if (outsideProject) return <>{children}</>;
    return <>
        {error && <div role="alert">{error} <button onClick={() => store ? void store.flush() : retry(attempt + 1)}>重试</button></div>}
        {store ? <UIStateContext.Provider value={{ store, key: '' }}>{children}</UIStateContext.Provider> : !error && <div>正在恢复界面状态…</div>}
    </>;
}

export function UIStateScope({ name, children }: React.PropsWithChildren<{ name: string }>) {
    const parent = useContext(UIStateContext);
    return <UIStateContext.Provider key={name} value={parent && { store: parent.store, key: parent.key + '/' + encodeURIComponent(name) }}>
        {children}
    </UIStateContext.Provider>;
}

export function useUIState<T>(name: string, initial: T): [T, (value: T) => void] {
    const context = useContext(UIStateContext);
    const key = context?.key + '/' + encodeURIComponent(name);
    const [value, setValue] = useState<T>(() => context && key in context.store.values ? context.store.values[key] as T : initial);
    return [value, next => { setValue(next); context?.store.set(key, next); }];
}

/** Opt in only durable fields; requests, errors and loaded options stay transient. */
export class PersistentComponent<P, S> extends React.Component<P, S> {
    static contextType = UIStateContext;
    declare context: React.ContextType<typeof UIStateContext>;
    protected persistedFields: (keyof S)[] = [];
    componentDidMount() {
        if (!this.persistedFields.length) return;
        const saved = this.context?.store.values[this.context.key];
        if (saved && typeof saved === 'object') {
            const next: Partial<S> = {};
            for (const field of this.persistedFields) {
                if (Object.prototype.hasOwnProperty.call(saved, field)) next[field] = (saved as S)[field];
            }
            this.setState(next as S);
        }
    }
    componentDidUpdate(..._args: unknown[]) {
        if (!this.context || !this.persistedFields.length) return;
        const value: Partial<S> = {};
        for (const field of this.persistedFields) value[field] = this.state[field];
        this.context.store.set(this.context.key, value);
    }
}
