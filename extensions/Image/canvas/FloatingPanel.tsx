import React from 'react';
import { Card, Elevation, HTMLSelect, Button, Icon } from "@blueprintjs/core";
import { ComponentTabRef } from "ssui_components";
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

// 模拟数据
const mockScripts: ScriptOption[] = [
    {
        value: 'script1',
        label: '图像处理脚本',
        functions: [
            { value: 'resize', label: '调整大小' },
            { value: 'crop', label: '裁剪' },
            { value: 'filter', label: '滤镜' }
        ]
    },
    {
        value: 'script2',
        label: '文本处理脚本',
        functions: [
            { value: 'ocr', label: '文字识别' },
            { value: 'translate', label: '翻译' }
        ]
    }
];

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
}

interface FloatingPanelProps {
    path: string;
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
            selectedFunction: null
        };
    }

    refInputs: Map<string, React.RefObject<ComponentTabRef>> = new Map();

    componentDidMount() {
        this.queryScriptMeta();
    }

    async queryScriptMeta(): Promise<void> {
        try {
            const response = await fetch('/api/script?' + new URLSearchParams({
                script_path: this.state.selectedScript?? ''
            }));

            if (!response.ok) {
                throw new Error('Failed to fetch script meta');
            }

            const data = await response.json() as ScriptMeta;
            this.setState({
                functions: data.functions,
                loading: false,
                error: null,
                root_path: data.root_path
            });
        } catch (error) {
            this.setState({
                loading: false,
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
    }

    handleFunctionChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
        this.setState({ selectedFunction: event.target.value });
    }

    renderInputs = (meta: Params): JSX.Element => {
        return (
            <div>
                {Object.entries(meta.params).map(([key, value]) => (
                    <Card key={key} elevation={Elevation.TWO} className="input-card">
                        <ComponentTabRef
                            name={key}
                            root_path={this.state.root_path}
                            script_path={this.state.selectedScript?? ''}
                            type={value}
                            port='input'
                            ref={this.getRef(key)}
                        />
                    </Card>
                ))}
            </div>
        );
    }

    render(): JSX.Element {
        const { functions, loading, error, selectedScript, selectedFunction } = this.state;

        if (loading) {
            return <div className="floating-panel">Loading...</div>;
        }

        if (error) {
            return <div className="floating-panel">Error: {error.message}</div>;
        }

        const selectedScriptData = mockScripts.find(script => script.value === selectedScript);
        const availableFunctions = selectedScriptData?.functions || [];

        return (
            <div className="floating-panel">
                <div className="panel-content">
                    <div className="top-row">
                        <div className="cascade-selectors">
                            <HTMLSelect
                                value={selectedScript || ''}
                                onChange={this.handleScriptChange}
                                className="script-selector"
                            >
                                <option value="">选择脚本</option>
                                {mockScripts.map(script => (
                                    <option key={script.value} value={script.value}>
                                        {script.label}
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
                                    <option key={func.value} value={func.value}>
                                        {func.label}
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
                                    minimal
                                />
                            </div>
                        </div>
                    </div>

                    {selectedFunction && functions && (
                        <div className="input-section">
                            <h3>输入参数</h3>
                            {this.renderInputs(functions[selectedFunction])}
                        </div>
                    )}
                </div>
            </div>
        );
    }
} 