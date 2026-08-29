import React, { Component } from 'react';
import { Button, Callout, Collapse, Icon, MenuItem, NonIdealState, Spinner, Tag } from "@blueprintjs/core";
import { ItemPredicate, ItemRenderer, Select } from "@blueprintjs/select";
import { ComponentTabRef } from "ssui_components";
import { DetailsPanel } from "./Details";
import { registerUIProvider, UIProvider } from '../UIProvider';
import { useConfig } from '../../config';
import { ViewSwitcher } from "../common/ViewSwitcher";
import './FunctionalUI.css';
import "normalize.css";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";

interface Callable { rank: number; name: string; }
interface Params { params: Record<string, string>; returns: string[]; }
interface FunctionMeta { [key: string]: Params | string; }
interface ScriptMeta { root_path: string; functions: FunctionMeta; }
interface FunctionalUIProps { path: string; autoOpenDetails?: boolean; }
interface FunctionalUIState {
    functions: FunctionMeta | null;
    loading: boolean;
    error: Error | null;
    selectedFunc: Callable | undefined;
    isOpen: boolean;
    root_path: string;
    running: boolean;
    runError: string | null;
    hasRun: boolean;
}

export class FunctionalUI extends Component<FunctionalUIProps, FunctionalUIState> {
    state: FunctionalUIState = {
        functions: null, loading: true, error: null, selectedFunc: undefined,
        isOpen: Boolean(this.props.autoOpenDetails), root_path: '', running: false,
        runError: null, hasRun: false,
    };

    private refInputs = new Map<string, React.RefObject<ComponentTabRef>>();
    private refOutputs = new Map<string, React.RefObject<ComponentTabRef>>();
    private details: React.RefObject<DetailsPanel> = React.createRef();
    private metaRequest?: AbortController;
    private executeRequest?: AbortController;

    componentDidMount() { this.queryScriptMeta(); }

    componentDidUpdate(prevProps: FunctionalUIProps) {
        if (prevProps.path !== this.props.path) this.queryScriptMeta();
        if (!prevProps.autoOpenDetails && this.props.autoOpenDetails) this.setState({ isOpen: true });
    }

    componentWillUnmount() {
        this.metaRequest?.abort();
        this.executeRequest?.abort();
    }

    async queryScriptMeta(): Promise<void> {
        this.metaRequest?.abort();
        this.executeRequest?.abort();
        const request = new AbortController();
        this.metaRequest = request;
        this.refInputs.clear();
        this.refOutputs.clear();
        this.setState({ loading: true, error: null, functions: null, selectedFunc: undefined, running: false, runError: null, hasRun: false });
        try {
            const response = await fetch('/api/script?' + new URLSearchParams({ script_path: this.props.path }), { signal: request.signal });
            if (!response.ok) throw new Error(`无法读取脚本信息（${response.status}）`);
            const data = await response.json() as ScriptMeta;
            this.setState({ functions: data.functions, loading: false, error: null, root_path: data.root_path });
        } catch (error) {
            if (error instanceof DOMException && error.name === 'AbortError') return;
            this.setState({ loading: false, error: error instanceof Error ? error : new Error('读取脚本时发生未知错误') });
        }
    }

    getRef = (key: string, container: Map<string, React.RefObject<ComponentTabRef>>) => {
        const existing = container.get(key);
        if (existing) return existing;
        const ref = React.createRef<ComponentTabRef>();
        container.set(key, ref);
        return ref;
    };

    getFunctionNames = (meta: FunctionMeta) => Object.entries(meta)
        .filter(([, value]) => typeof value !== 'string')
        .map(([key]) => key);

    handleSelectFunc = (func: Callable) => {
        this.executeRequest?.abort();
        this.refInputs.clear();
        this.refOutputs.clear();
        this.setState({ selectedFunc: func, running: false, runError: null, hasRun: false });
    };

    toggleDetails = () => this.setState(state => ({ isOpen: !state.isOpen }));

    handleRun = async (): Promise<void> => {
        const { functions, selectedFunc, running } = this.state;
        if (!functions || running) return;
        const selected = selectedFunc?.name ?? this.getFunctionNames(functions)[0];
        const meta = functions[selected];
        if (!meta || typeof meta === 'string') return;

        const params: Record<string, unknown> = {};
        Object.keys(meta.params).forEach(key => { params[key] = this.refInputs.get(key)?.current?.onExecute(); });
        const details = this.details.current?.onExecute() ?? {};
        this.executeRequest?.abort();
        const request = new AbortController();
        this.executeRequest = request;
        this.setState({ running: true, runError: null });
        try {
            const response = await fetch('/api/execute?' + new URLSearchParams({ script_path: this.props.path, callable: selected }), {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params, details }), signal: request.signal,
            });
            if (!response.ok) throw new Error((await response.text()) || `执行失败（${response.status}）`);
            const data = await response.json() as unknown;
            if (!Array.isArray(data)) {
                const message = data && typeof data === 'object' && 'error' in data
                    ? String((data as { error: unknown }).error)
                    : '执行器返回了无法识别的结果格式';
                throw new Error(message);
            }
            const outputNames = Object.keys(meta.returns);
            data.forEach((item, index) => this.refOutputs.get(outputNames[index])?.current?.onUpdate(item));
            this.setState({ running: false, runError: null, hasRun: true });
        } catch (error) {
            if (error instanceof DOMException && error.name === 'AbortError') return;
            this.setState({ running: false, runError: error instanceof Error ? error.message : '执行时发生未知错误' });
        }
    };

    renderSelect = (names: string[]): JSX.Element => {
        const items = names.map((name, index) => ({ name, rank: index + 1 }));
        const filter: ItemPredicate<Callable> = (query, func, _index, exact) =>
            exact ? func.name.toLowerCase() === query.trim().toLowerCase() : func.name.toLowerCase().includes(query.trim().toLowerCase());
        const renderer: ItemRenderer<Callable> = (func, { handleClick, handleFocus, modifiers }) => modifiers.matchesPredicate ? (
            <MenuItem active={modifiers.active} disabled={modifiers.disabled} key={func.name} icon="function" label={`#${func.rank}`}
                onClick={handleClick} onFocus={handleFocus} roleStructure="listoption" text={func.name} />
        ) : null;
        return (
            <Select<Callable> items={items} itemPredicate={filter} itemRenderer={renderer}
                noResults={<MenuItem disabled text="没有匹配的函数" roleStructure="listoption" />}
                onItemSelect={this.handleSelectFunc} popoverProps={{ minimal: true, matchTargetWidth: true }}>
                <Button className="functional-ui-select" alignText="left" icon="function"
                    text={this.state.selectedFunc?.name ?? names[0]} rightIcon="chevron-down" />
            </Select>
        );
    };

    renderPorts = (meta: Params, port: 'input' | 'output', functionName: string): JSX.Element => {
        const entries: [string, string][] = port === 'input'
            ? Object.entries(meta.params)
            : meta.returns.map((type, index) => [String(index), type]);
        const refs = port === 'input' ? this.refInputs : this.refOutputs;
        if (!entries.length) return (
            <div className="functional-ui-empty-port"><Icon icon={port === 'input' ? 'inbox' : 'export'} size={18} />
                <span>{port === 'input' ? '此函数无需输入' : '此函数没有返回值'}</span></div>
        );
        return <div className="functional-ui-port-list">{entries.map(([name, type], index) => (
            <section className="functional-ui-card" key={`${functionName}-${port}-${name}`}>
                <div className="functional-ui-card-index">{String(index + 1).padStart(2, '0')}</div>
                <ComponentTabRef name={port === 'output' ? `output_${name}` : name} root_path={this.state.root_path}
                    script_path={this.props.path} type={type} port={port} ref={this.getRef(name, refs)} />
            </section>
        ))}</div>;
    };

    renderContent = (meta: FunctionMeta): JSX.Element => {
        const names = this.getFunctionNames(meta);
        if (!names.length) {
            const message = typeof meta.error === 'string' ? meta.error : '该文件中没有可运行的 Python 函数';
            return <NonIdealState icon="search" title="没有可运行函数" description={message} />;
        }
        const selected = this.state.selectedFunc?.name ?? names[0];
        const selectedMeta = meta[selected];
        if (!selectedMeta || typeof selectedMeta === 'string') {
            return <NonIdealState icon="error" title="函数信息无效" description="脚本返回了无法识别的函数定义。" />;
        }
        const inputCount = Object.keys(selectedMeta.params).length;
        const outputCount = selectedMeta.returns.length;
        return <div className="functional-ui-workspace">
            <section className="functional-ui-commandbar" aria-label="运行配置">
                <div className="functional-ui-function-picker"><span className="functional-ui-label">运行函数</span>{this.renderSelect(names)}</div>
                <div className="functional-ui-meta" aria-label="函数摘要">
                    <Tag minimal icon="import">{inputCount} 个输入</Tag><Tag minimal icon="export">{outputCount} 个输出</Tag>
                </div>
                <Button className="functional-ui-details-toggle" minimal icon="settings"
                    rightIcon={this.state.isOpen ? 'chevron-up' : 'chevron-down'} onClick={this.toggleDetails}
                    aria-expanded={this.state.isOpen}>高级参数</Button>
            </section>
            <Collapse isOpen={this.state.isOpen} keepChildrenMounted><div className="functional-ui-details-shell">
                <DetailsPanel path={this.props.path} selected={selected} ref={this.details} />
            </div></Collapse>
            {this.state.runError && <Callout className="functional-ui-run-error" intent="danger" icon="error" title="运行失败">{this.state.runError}</Callout>}
            <div className="functional-ui-stage">
                <section className="functional-ui-column functional-ui-column-input">
                    <header className="functional-ui-column-header"><div><span className="functional-ui-eyebrow">Configure</span><h2>输入</h2></div><span>{inputCount}</span></header>
                    {this.renderPorts(selectedMeta, 'input', selected)}
                </section>
                <div className="functional-ui-run-rail"><div className="functional-ui-rail-line" />
                    <Button className="functional-ui-run-button" intent="primary" icon={this.state.running ? undefined : 'play'}
                        onClick={this.handleRun} disabled={this.state.running} aria-label={this.state.running ? '正在运行' : `运行 ${selected}`}>
                        {this.state.running ? <Spinner size={18} /> : '运行'}
                    </Button>
                    <div className={`functional-ui-run-status${this.state.hasRun ? ' is-complete' : ''}`}>
                        {this.state.hasRun ? <><Icon icon="tick-circle" size={14} /> 已完成</> : 'READY'}
                    </div>
                </div>
                <section className="functional-ui-column functional-ui-column-output">
                    <header className="functional-ui-column-header"><div><span className="functional-ui-eyebrow">Inspect</span><h2>结果</h2></div><span>{outputCount}</span></header>
                    {this.renderPorts(selectedMeta, 'output', selected)}
                </section>
            </div>
        </div>;
    };

    render(): JSX.Element {
        const filename = this.props.path.split(/[\\/]/).pop() || '未选择脚本';
        return <div className="functional-ui-root">
            <header className="functional-ui-header"><div className="functional-ui-title-block">
                <div className="functional-ui-mark" aria-hidden="true"><Icon icon="function" size={20} /></div>
                <div><span className="functional-ui-kicker">FUNCTION CONSOLE</span><h1>{filename}</h1>
                    <p title={this.props.path}>{this.props.path || '选择一个 Python 脚本开始'}</p></div>
            </div><ViewSwitcher path={this.props.path} currentView="functional" /></header>
            {this.state.loading ? <div className="functional-ui-loading"><Spinner size={28} /><span>正在分析脚本…</span></div>
                : this.state.error ? <NonIdealState icon="error" title="无法打开脚本" description={this.state.error.message}
                    action={<Button icon="refresh" onClick={() => this.queryScriptMeta()}>重试</Button>} />
                : this.state.functions ? this.renderContent(this.state.functions) : null}
        </div>;
    }
}

const FunctionalUIView: React.FC<FunctionalUIProps> = ({ path }) => {
    const { config } = useConfig();
    return <FunctionalUI path={path} autoOpenDetails={config.auto_open_details} />;
};

export class FunctionalUIProvider implements UIProvider {
    getName(): string { return 'functional'; }
    getUI(path: string): JSX.Element { return <FunctionalUIView path={path} />; }
}

export default FunctionalUI;
