import React, { createContext, useContext, useRef } from 'react';
import { Button, TextArea } from '@blueprintjs/core';
import { UIStateContext, useUIState } from 'ssui_components';
import type { ApiComponents } from 'ssui_components';

export type Conversation = NonNullable<ApiComponents['schemas']['ScriptFunctionInfo']['conversation']>;
export type Pair = [string, string];
export type ContextValue = Pair[] | string;
export interface Session { id: string; revision: number; context: ContextValue; turns: Pair[]; protocol: string; }
export function isPairs(value: unknown): value is Pair[] {
    return Array.isArray(value) && value.every(pair => Array.isArray(pair) && pair.length === 2 && pair.every(item => typeof item === 'string'));
}
export function validContext(value: unknown, c: Conversation): value is ContextValue {
    return c.context_kind === 'pairs' ? isPairs(value) : typeof value === 'string';
}
const empty = (c: Conversation): Session => ({ id: crypto.randomUUID(), revision: 0,
    context: c.context_kind === 'pairs' ? [] : '', turns: [], protocol: JSON.stringify(c) });
export interface SessionAccess {
    get(name: string, c: Conversation): Session;
    commit(name: string, c: Conversation, snapshot: Session, prompt: string, result: unknown[]): void;
    reset(name: string, c: Conversation): void;
    edit(name: string, c: Conversation, value: unknown): void;
}
const SessionContext = createContext<SessionAccess | null>(null);
const SettingsContext = createContext<React.ContextType<typeof UIStateContext>>(null);

/** One owner per script, above all view providers. UI components never own context. */
export function SessionProvider({ children }: React.PropsWithChildren) {
    const storage = useContext(UIStateContext);
    const [saved, save] = useUIState<Record<string, Session>>('sessions', {});
    const current = useRef(saved);
    const lastSaved = useRef(saved);
    if (lastSaved.current !== saved) { current.current = saved; lastSaved.current = saved; }
    const get = (name: string, c: Conversation) => {
        const session = current.current[name];
        if (session?.protocol === JSON.stringify(c) && validContext(session.context, c) && isPairs(session.turns)) return session;
        const fresh = empty(c);
        current.current = { ...current.current, [name]: fresh };
        return fresh;
    };
    const set = (name: string, session: Session) => {
        current.current = { ...current.current, [name]: session };
        save(current.current);
    };
    const access: SessionAccess = {
        get,
        reset: (name, c) => set(name, empty(c)),
        edit: (name, c, value) => {
            if (!validContext(value, c)) throw new Error('上下文格式不正确');
            const session = get(name, c);
            set(name, { ...session, context: value, revision: session.revision + 1 });
        },
        commit: (name, c, snapshot, prompt, result) => {
            const latest = current.current[name];
            if (latest && (latest.id !== snapshot.id || latest.revision !== snapshot.revision)) throw new Error('会话已变化，本次结果未覆盖当前上下文');
            if (typeof result[0] !== 'string') throw new Error('工作流没有返回有效的文本回复');
            const context = c.context_output == null ? [...snapshot.context as Pair[], [prompt, result[0]]] : result[c.context_output];
            if (!validContext(context, c)) throw new Error('工作流返回的上下文格式不正确，本轮未加入对话；可修改后重试');
            set(name, { ...snapshot, context, turns: [...snapshot.turns, [prompt, result[0]]], revision: snapshot.revision + 1 });
        },
    };
    return <SettingsContext.Provider value={storage}><SessionContext.Provider value={access}>{children}</SessionContext.Provider></SettingsContext.Provider>;
}
export function useSessions() { return useContext(SessionContext); }
export function SharedSettings({ name, children }: React.PropsWithChildren<{ name: string }>) {
    const root = useContext(SettingsContext);
    return root ? <UIStateContext.Provider value={{ ...root, key: `/settings/${encodeURIComponent(name)}` }}>{children}</UIStateContext.Provider> : <>{children}</>;
}

export function ContextEditor({ name, conversation, disabled = false }: { name: string; conversation: Conversation; disabled?: boolean }) {
    const sessions = useSessions();
    const [open, setOpen] = React.useState(false);
    const [draft, setDraft] = React.useState('');
    const [error, setError] = React.useState('');
    if (!sessions) return null;
    const session = sessions.get(name, conversation);
    return <section className="functional-ui-details-shell" aria-label="共享上下文">
        <p>共享会话 · {session.turns.length} 轮。运行时自动传入上下文，成功后自动更新。</p>
        <Button disabled={disabled} onClick={() => { setDraft(conversation.context_kind === 'text' ? session.context as string : JSON.stringify(session.context, null, 2)); setOpen(!open); setError(''); }}>查看／编辑上下文</Button>{' '}
        <Button disabled={disabled} onClick={() => { sessions.reset(name, conversation); setOpen(false); }}>重置上下文</Button>
        {open && <div><label>上下文<TextArea fill aria-label="上下文" rows={6} value={draft} disabled={disabled} onChange={e => setDraft(e.target.value)} /></label>
            <Button disabled={disabled} onClick={() => { try { sessions.edit(name, conversation, conversation.context_kind === 'text' ? draft : JSON.parse(draft)); setOpen(false); } catch { setError('请输入有效上下文：文本或 JSON 问答对数组。'); } }}>保存上下文</Button>
            {error && <p role="alert">{error}</p>}</div>}
    </section>;
}
