import React from 'react';
import './App.css';
import { UIStateProvider } from 'ssui_components';
import { getUIProvider } from './ui/UIProvider';
import { SessionProvider } from './ui/conversation/SessionState';
import { singleConversation } from './ui/conversation/ConversationUI';

function route() {
    const params = new URLSearchParams(window.location.search);
    return { path: params.get('path') ?? '', view: params.get('view') ?? '' };
}
function App() {
    const [current, setCurrent] = React.useState(route);
    React.useEffect(() => {
        const update = () => setCurrent(route());
        window.addEventListener('popstate', update);
        return () => window.removeEventListener('popstate', update);
    }, []);
    React.useEffect(() => {
        if (current.view) return;
        const request = new AbortController();
        const select = (view: string) => {
            if (request.signal.aborted) return;
            const url = new URL(window.location.href);
            url.searchParams.set('view', view);
            window.history.replaceState({}, '', url);
            setCurrent({ ...current, view });
        };
        if (!current.path.toLowerCase().endsWith('.py')) select('functional');
        else fetch('/api/script?' + new URLSearchParams({ script_path: current.path }), { signal: request.signal })
            .then(async response => { if (!response.ok) throw new Error(); return response.json(); })
            .then(meta => select(meta.functions && singleConversation(meta.functions) ? 'conversation' : 'functional'))
            .catch(() => select('functional'));
        return () => request.abort();
    }, [current.path, current.view]);
    if (!current.view) return <main>正在选择视图…</main>;
    const provider = getUIProvider(current.view) ?? getUIProvider('functional')!;
    return <main><UIStateProvider key={current.path} path={current.path} view="sessions">
        <SessionProvider><UIStateProvider key={current.path + ':' + provider.getName()} path={current.path} view={provider.getName()}>
            {provider.getUI(current.path)}
        </UIStateProvider></SessionProvider>
    </UIStateProvider></main>;
}
export default App;
