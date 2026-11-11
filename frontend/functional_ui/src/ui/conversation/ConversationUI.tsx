import React from 'react';
import { Button, Callout, Collapse, Icon, Spinner } from '@blueprintjs/core';
import { ComponentTabRef, PersistentComponent, UIStateScope } from 'ssui_components';
import type { ApiComponents } from 'ssui_components';
import { DetailsPanel } from '../functional/Details';
import { Conversation, SessionAccess, SharedSettings } from './SessionState';
import './ConversationUI.css';

type FunctionInfo = ApiComponents['schemas']['ScriptFunctionInfo'];
interface Props {
    path: string;
    rootPath: string;
    name: string;
    meta: FunctionInfo;
    conversation: Conversation;
    sessions: SessionAccess;
}
interface State {
    draft: string;
    advanced: boolean;
    settingsOpen: boolean;
    running: boolean;
    pendingPrompt: string;
    error: string | null;
}

/** The backend owns inference; multiple-workflow scripts always retain the console. */
export function singleConversation(functions: ApiComponents['schemas']['ScriptMeta']['functions']) {
    const entries = Object.entries(functions).filter(([, info]) => typeof info !== 'string');
    if (entries.length !== 1) return null;
    const [name, meta] = entries[0];
    if (typeof meta === 'string' || !meta.conversation) return null;
    const c = meta.conversation;
    if (!(c.prompt_param in meta.params) || !(c.context_param in meta.params) || c.prompt_param === c.context_param ||
        !['pairs', 'text'].includes(c.context_kind) ||
        !(c.context_output == null ? c.context_kind === 'pairs' && meta.returns.length === 1 : c.context_output === 1 && meta.returns.length === 2)) return null;
    return { name, meta, conversation: c };
}

export class ConversationUI extends PersistentComponent<Props, State> {
    protected persistedFields: (keyof State)[] = ['draft', 'advanced', 'settingsOpen'];
    state: State = {
        draft: '', advanced: false, settingsOpen: true, running: false, pendingPrompt: '', error: null,
    };
    private inputs = new Map<string, React.RefObject<ComponentTabRef>>();
    private details = React.createRef<DetailsPanel>();
    private composer = React.createRef<HTMLTextAreaElement>();
    private log = React.createRef<HTMLDivElement>();
    private request?: AbortController;
    private busy = false;

    componentDidMount() {
        super.componentDidMount();
    }

    componentDidUpdate(_props: Props, previous: State) {
        super.componentDidUpdate();
        if (previous.running !== this.state.running) {
            const log = this.log.current;
            if (log) log.scrollTop = log.scrollHeight;
        }
    }

    componentWillUnmount() { this.request?.abort(); }

    private inputRef(name: string) {
        if (!this.inputs.has(name)) this.inputs.set(name, React.createRef<ComponentTabRef>());
        return this.inputs.get(name)!;
    }

    private newConversation = () => {
        if (this.busy) return;
        this.props.sessions.reset(this.props.name, this.props.conversation);
        this.setState({ draft: '', error: null });
        this.composer.current?.focus();
    };

    private send = async () => {
        if (this.busy || !this.state.draft.trim()) return;
        const { path, name, meta, conversation: c } = this.props;
        const prompt = this.state.draft;
        const snapshot = this.props.sessions.get(name, c);
        const request = new AbortController();
        this.request = request;
        this.busy = true;
        this.setState({ running: true, pendingPrompt: prompt, error: null });
        try {
            const params: Record<string, unknown> = {};
            for (const key of Object.keys(meta.params)) {
                if (key === c.prompt_param || key === c.context_param) continue;
                const input = this.inputs.get(key)?.current;
                if (!input) throw new Error(`参数尚未准备好：${key}`);
                params[key] = input.onExecute();
            }
            params[c.prompt_param] = prompt;
            params[c.context_param] = snapshot.context;
            const details = this.details.current?.onExecute();
            if (!details) throw new Error('生成参数尚未准备好，请稍后重试');
            const response = await fetch('/api/execute?' + new URLSearchParams({ script_path: path, callable: name }), {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params, details }), signal: request.signal,
            });
            if (!response.ok) throw new Error((await response.text()) || `生成失败（${response.status}）`);
            const data: unknown = await response.json();
            if (request.signal.aborted || this.request !== request) return;
            if (!Array.isArray(data)) {
                throw new Error(data && typeof data === 'object' && 'error' in data ? String(data.error) : '无法识别的对话结果');
            }
            if (data.length !== meta.returns.length || typeof data[0] !== 'string') throw new Error('工作流没有返回有效的文本回复');
            this.props.sessions.commit(name, c, snapshot, prompt, data);
            this.setState({ draft: '', error: null, settingsOpen: false });
        } catch (error) {
            if (!request.signal.aborted && this.request === request) this.setState({ error: error instanceof Error ? error.message : String(error) });
        } finally {
            if (!request.signal.aborted && this.request === request) {
                this.busy = false;
                this.setState({ running: false, pendingPrompt: '' }, () => this.composer.current?.focus());
            }
        }
    };

    render() {
        const { path, rootPath, name, meta, conversation: c } = this.props;
        const { draft, running, error, advanced } = this.state;
        const { turns } = this.props.sessions.get(name, c);
        const settings = Object.entries(meta.params).filter(([key]) => key !== c.prompt_param && key !== c.context_param);
        return <div className="conversation-workspace">
            <aside className={`conversation-settings${this.state.settingsOpen ? ' is-open' : ''}`} aria-label="对话设置">
                <header><Icon icon="settings" /><h2>对话设置</h2>
                    <Button className="conversation-settings-toggle" minimal disabled={running}
                        aria-expanded={this.state.settingsOpen} rightIcon={this.state.settingsOpen ? 'chevron-up' : 'chevron-down'}
                        onClick={() => this.setState({ settingsOpen: !this.state.settingsOpen })}>{this.state.settingsOpen ? '收起设置' : '展开设置'}</Button></header>
                <fieldset disabled={running}>
                    <legend className="conversation-sr-only">模型与生成参数</legend>
                    {settings.map(([key, type]) => <section key={key} className="conversation-setting">
                        <SharedSettings name={`${name}/input/${key}`}><ComponentTabRef name={key === 'system_prompt' ? '系统提示' : key === 'model' ? '模型' : key}
                            parameterName={key} type={type} port="input" root_path={rootPath} hideSingleTab
                            script_path={path} ref={this.inputRef(key)} /></SharedSettings>
                    </section>)}
                    <Button minimal fill alignText="left" icon="settings" rightIcon={advanced ? 'chevron-up' : 'chevron-down'}
                        aria-expanded={advanced} onClick={() => this.setState({ advanced: !advanced })}>生成参数</Button>
                    <Collapse isOpen={advanced} keepChildrenMounted><SharedSettings name={`${name}/details`}>
                        <DetailsPanel path={path} selected={name} ref={this.details} />
                    </SharedSettings></Collapse>
                </fieldset>
                <p className="conversation-settings-note">每条消息都会携带当前对话的上下文。新对话会清空上下文，保留模型设置。</p>
            </aside>
            <section className="conversation-panel" aria-label="会话">
                <header className="conversation-toolbar"><div><Icon icon="chat" /><h2>对话</h2><span>{turns.length} 轮</span></div>
                    <Button minimal icon="add" onClick={this.newConversation} disabled={running}>新对话</Button></header>
                <div className="conversation-log" role="log" aria-label="消息记录" aria-live="polite" aria-relevant="additions text" ref={this.log}>
                    {!turns.length && !running && <div className="conversation-empty"><Icon icon="chat" size={30} /><h3>开始一段对话</h3>
                        <p>配置好模型后，发送第一条消息。<br />后续提问会接着当前上下文继续。</p></div>}
                    {turns.map(([question, answer], index) => <React.Fragment key={index}>
                        <article className="conversation-message is-user" aria-label={`你，第 ${index + 1} 轮`}><span>你</span><div>{question}</div></article>
                        <article className="conversation-message is-assistant" aria-label={`助手，第 ${index + 1} 轮`}><span>助手</span><div>{answer}</div></article>
                    </React.Fragment>)}
                    {running && <><article className="conversation-message is-user"><span>你</span><div>{this.state.pendingPrompt}</div></article>
                        <div role="status" className="conversation-pending"><Spinner size={16} /><span>正在生成回复…</span></div></>}
                </div>
                <div className="conversation-composer">
                    {error && <Callout intent="danger" role="alert" title="未能发送">{error}</Callout>}
                    <label htmlFor="conversation-message" className="conversation-sr-only">消息</label>
                    <textarea id="conversation-message" ref={this.composer} rows={3} value={draft} disabled={running}
                        placeholder="输入消息，继续对话…" onChange={event => this.setState({ draft: event.target.value })}
                        onKeyDown={event => {
                            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
                                event.preventDefault(); void this.send();
                            }
                        }} />
                    <footer><span>Enter 发送 · Shift + Enter 换行</span><Button intent="primary" icon={running ? undefined : 'arrow-up'}
                        disabled={running || !draft.trim()} onClick={() => void this.send()}>{running ? '生成中' : error ? '重试发送' : '发送'}</Button></footer>
                </div>
            </section>
        </div>;
    }
}
