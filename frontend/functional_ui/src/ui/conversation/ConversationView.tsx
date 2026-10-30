import React from 'react';
import { Button, Icon, NonIdealState, Spinner } from '@blueprintjs/core';
import { UIStateScope } from 'ssui_components';
import type { ApiComponents } from 'ssui_components';
import type { UIProvider } from '../UIProvider';
import { ViewSwitcher } from '../common/ViewSwitcher';
import { ConversationUI, singleConversation } from './ConversationUI';
import { useSessions } from './SessionState';
import '../functional/FunctionalUI.css';

export function ConversationView({ path }: { path: string }) {
    const sessions = useSessions();
    const [meta, setMeta] = React.useState<ApiComponents['schemas']['ScriptMeta']>();
    const [error, setError] = React.useState('');
    const [attempt, retry] = React.useState(0);
    React.useEffect(() => {
        const request = new AbortController();
        setMeta(undefined); setError('');
        fetch('/api/script?' + new URLSearchParams({ script_path: path }), { signal: request.signal })
            .then(async response => { if (!response.ok) throw new Error(`无法读取脚本信息（${response.status}）`); return response.json(); })
            .then(data => { if (!request.signal.aborted) setMeta(data); })
            .catch(e => { if (!request.signal.aborted) setError(String(e.message)); });
        return () => request.abort();
    }, [path, attempt]);
    const chat = meta?.functions ? singleConversation(meta.functions) : null;
    return <div className="functional-ui-root">
        <header className="functional-ui-header"><div className="functional-ui-title-block">
            <div className="functional-ui-mark"><Icon icon="chat" size={20} /></div>
            <div><span className="functional-ui-kicker">CONVERSATION</span><h1>{path.split(/[\\/]/).pop()}</h1><p>{path}</p></div>
        </div><ViewSwitcher path={path} currentView="conversation" /></header>
        {error ? <NonIdealState title="无法打开对话" description={error} action={<Button onClick={() => retry(attempt + 1)}>重试</Button>} />
            : !meta ? <Spinner /> : chat && sessions ? <UIStateScope name={`conversation/${chat.name}`}>
                <ConversationUI key={`${path}:${chat.name}:${JSON.stringify(chat.conversation)}`} path={path} rootPath={meta.root_path ?? ''} {...chat} sessions={sessions} />
            </UIStateScope> : <NonIdealState icon="chat" title="此脚本不支持会话视图" description="需要单个带文本上下文的工作流。可切换到 Functional UI 运行，或在代码编辑器中修改。" />}
    </div>;
}
export class ConversationUIProvider implements UIProvider {
    getName() { return 'conversation'; }
    getUI(path: string) { return <ConversationView path={path} />; }
}
