import React from 'react';
import { Card, Elevation, HTMLSelect, Button, Icon } from "@blueprintjs/core";
import { ComponentTabRef, Message } from "ssui_components";
import './FloatingPanel.css';

// 定义脚本选项接口
interface ScriptOption {
    value: string;
    label: string;
    functions: FunctionOption[];
}

// 定义函数选项接口
interface FunctionOption {
    value: string;
    label: string;
}

interface Callable {
    rank: number;
    name: string;
}

interface Params {
    params: {
        [key: string]: string;
    },
    returns: {
        [key: string]: string;
    }
}

interface FunctionMeta {
    [key: string]: Params
}

interface ScriptMeta {
    root_path: string;
    functions: FunctionMeta;
}


interface FloatingPanelState {
    functions: FunctionMeta | null;
    loading: boolean;
    error: Error | null;
    selectedFunc: Callable | undefined;
    root_path: string;
    selectedScript: string | null;
    selectedFunction: string | null;
    scripts: string[];
    isInputsCollapsed: boolean;
}

interface FloatingPanelProps {
    path: string;
    onSelectScript: (script: string) => void;
}

export class FloatingPanel extends React.Component<FloatingPanelProps, FloatingPanelState> {
    constructor(props: FloatingPanelProps) {
        super(props);
        this.state = {
            functions: null,
            loading: true,
            error: null,
            selectedFunc: undefined,
            root_path: '',
            selectedScript: null,
            selectedFunction: null,
            scripts: [],
            isInputsCollapsed: false
        };
        this.message = new Message();
    }
    private message: Message;


    refInputs: Map<string, React.RefObject<ComponentTabRef>> = new Map();

    componentDidMount() {
        this.query_scripts();
    }

    private query_scripts = async () => {
        const scripts = await this.message.get('files/script?' +
            new URLSearchParams({ script_path: this.props.path }));

        if (scripts.length > 0) {
            this.setState({
                scripts: scripts,
                loading: false
            });
        }
    }

    async queryScriptMeta(selectedScript: string): Promise<void> {
        try {
            const response = await fetch('/api/script?' + new URLSearchParams({
                script_path: selectedScript
            }));

            if (!response.ok) {
                throw new Error('Failed to fetch script meta');
            }

            const data = await response.json() as ScriptMeta;
            this.setState({
                functions: data.functions,
                error: null,
                root_path: data.root_path
            });
        } catch (error) {
            this.setState({
                error: error instanceof Error ? error : new Error('Unknown error')
            });
        }
    }

    getRef = (index: string): React.RefObject<ComponentTabRef> => {
        if (this.refInputs.has(index)) {
            return this.refInputs.get(index) ?? React.createRef<ComponentTabRef>();
        }

        const newRef = React.createRef<ComponentTabRef>();
        this.refInputs.set(index, newRef);
        return newRef;
    }

    handleSelectFunc = (func: Callable): void => {
        this.setState({ selectedFunc: func });
    }

    handleScriptChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
        this.setState({
            selectedScript: event.target.value,
            selectedFunction: null // 重置函数选择
        });
        this.queryScriptMeta(event.target.value);
    }

    handleFunctionChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
        this.setState({ selectedFunction: event.target.value });
        this.props.onSelectScript(this.state.selectedFunction ?? '');
    }

    renderInputs = (meta: Params): JSX.Element => {
        return <div>
            {Object.entries(meta.params).map(([key, value]) => {
                if (key !== 'positive') {
                    return <Card key={key} elevation={Elevation.TWO} className="input-card" style={{ display: this.state.isInputsCollapsed ? 'none' : 'block' }}>
                        <ComponentTabRef
                            name={key}
                            root_path={this.state.root_path}
                            script_path={this.state.selectedScript ?? ''}
                            type={value}
                            port='input'
                            ref={this.getRef(key)}
                        />
                    </Card>
                }
            })}
        </div>
    };

    getScriptName(script: string): string {
        return script.split(/[/\\]/).pop() ?? '';
    }

    render(): JSX.Element {
        const { functions, loading, error, selectedScript, selectedFunction } = this.state;

        if (loading) {
            return <div className="floating-panel">Loading...</div>;
        }

        if (error) {
            return <div className="floating-panel">Error: {error.message}</div>;
        }

        const availableFunctions = this.state.functions ? Object.keys(this.state.functions) : [];

        return (
            <div className="floating-panel">
                <div className="panel-content">
                    <div className="top-row">
                        <div className="cascade-selectors">
                            <Button
                                variant='minimal'
                                icon={this.state.isInputsCollapsed ? "chevron-right" : "chevron-down"}
                                onClick={() => this.setState({ isInputsCollapsed: !this.state.isInputsCollapsed })}
                                className="collapse-button"
                            />
                            <HTMLSelect
                                value={selectedScript || ''}
                                onChange={this.handleScriptChange}
                                className="script-selector"
                            >
                                <option value="">选择脚本</option>
                                {this.state.scripts.map(script => (
                                    <option key={script} value={script}>
                                        {this.getScriptName(script)}
                                    </option>
                                ))}
                            </HTMLSelect>

                            <HTMLSelect
                                value={selectedFunction || ''}
                                onChange={this.handleFunctionChange}
                                className="function-selector"
                                disabled={!selectedScript}
                            >
                                <option value="">选择函数</option>
                                {availableFunctions.map(func => (
                                    <option key={func} value={func}>
                                        {func}
                                    </option>
                                ))}
                            </HTMLSelect>
                        </div>
                        <div className="prompt-input">
                            <div className="prompt-input-group">
                                <input
                                    type="text"
                                    placeholder="输入提示词..."
                                    className="prompt-input-field"
                                />
                                <Button
                                    className="generate-button"
                                    intent="primary"
                                    icon={<Icon icon="play" />}
                                    variant='minimal'
                                />
                            </div>
                        </div>
                    </div>

                    {selectedFunction && functions && (
                        <div className="input-section">
                            {this.renderInputs(functions[selectedFunction])}
                        </div>
                    )}
                </div>
            </div>
        );
    }
} 