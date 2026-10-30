import React from 'react';
import { act, render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SessionProvider, useSessions, SessionAccess, Conversation } from '../src/ui/conversation/SessionState';

const pairs: Conversation = { prompt_param: 'prompt', context_param: 'history', context_kind: 'pairs', context_output: 1 };
function setup() {
    let access!: SessionAccess;
    function Consumer() { access = useSessions()!; return null; }
    render(<SessionProvider><Consumer /></SessionProvider>);
    return () => access;
}
describe('shared sessions', () => {
    it('isolates functions, rejects stale results after reset and retains history on malformed output', () => {
        const access = setup();
        const first = access().get('a', pairs);
        act(() => access().commit('a', pairs, first, 'one', ['answer', [['one', 'answer']]]));
        expect(access().get('a', pairs).turns).toEqual([['one', 'answer']]);
        expect(access().get('b', pairs).context).toEqual([]);
        const before = access().get('a', pairs);
        expect(() => access().commit('a', pairs, before, 'two', ['bad', 42])).toThrow();
        expect(access().get('a', pairs)).toEqual(before);
        act(() => access().reset('a', pairs));
        expect(() => access().commit('a', pairs, before, 'late', ['answer', []])).toThrow('会话已变化');
        expect(access().get('a', pairs).context).toEqual([]);
        expect(access().get('a', pairs).id).not.toBe(before.id);
    });
    it('normalizes a changed protocol once and permits the first execution afterwards', () => {
        const access = setup();
        act(() => access().edit('a', pairs, [['old', 'context']]));
        const text: Conversation = { ...pairs, context_kind: 'text' };
        const fresh = access().get('a', text);
        expect(fresh.context).toBe('');
        expect(access().get('a', text).id).toBe(fresh.id);
        act(() => access().commit('a', text, fresh, 'new', ['answer', 'new context']));
        expect(access().get('a', text).context).toBe('new context');
    });
});
