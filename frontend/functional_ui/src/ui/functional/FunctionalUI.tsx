import React, { Component } from 'react';
import { Label, Button, Card, Elevation, Collapse } from "@blueprintjs/core";
import { ItemPredicate, ItemRenderer, Select } from "@blueprintjs/select";
import { MenuItem } from "@blueprintjs/core";
import { ComponentTabRef } from "ssui_components";
import { DetailsPanel } from "./Details";
import { registerUIProvider, UIProvider } from '../UIProvider';
import './FunctionalUI.css';
import "normalize.css";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";

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

interface FunctionalUIProps {
    path: string;
}

interface FunctionalUIState {
    functions: FunctionMeta | null;
    loading: boolean;
    error: Error | null;
    selectedFunc: Callable | undefined;
    isOpen: boolean;
    root_path: string;
}

export class FunctionalUI extends Component<FunctionalUIProps, FunctionalUIState> {
    constructor(props: FunctionalUIProps) {
        super(props);
        this.state = {
            functions: null,
            loading: true,
            error: null,
            selectedFunc: undefined,
            isOpen: false,
            root_path: '',
        };
    }

    refInputs: Map<string, React.RefObject<ComponentTabRef>> = new Map();
    refOutputs: Map<string, React.RefObject<ComponentTabRef>> = new Map();
    details: React.RefObject<DetailsPanel> = React.createRef();

    componentDidMount() {
        this.queryScriptMeta();
    }

    async queryScriptMeta(): Promise<void> {
        try {
            const response = await fetch('/api/script?' + new URLSearchParams({
                script_path: this.props.path
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
            console.log(this.state);
        } catch (error) {
            this.setState({
                loading: false,
                error: error instanceof Error ? error : new Error('Unknown error')
            });
        }
    }

    getRef = (index: string, container: Map<string, React.RefObject<ComponentTabRef>>): React.RefObject<ComponentTabRef> => {
        if (container.has(index)) {
            return container.get(index) ?? React.createRef<ComponentTabRef>();
        }

        const newRef = React.createRef<ComponentTabRef>();
        container.set(index, newRef);
        return newRef;
    }

    handleSelectFunc = (func: Callable): void => {
        this.setState({ selectedFunc: func });
    }

    toggleDetails = (): void => {
        this.setState(prevState => ({ isOpen: !prevState.isOpen }));
    }

    handleRun = (): void => {
        const { functions, selectedFunc, isOpen } = this.state;
        const { path } = this.props;

        if (!functions) return;

        const selected = selectedFunc?.name ?? Object.keys(functions)[0];
        const meta = functions[selected];

        // 收集输入参数
        const params: { [key: string]: any } = {};
        for (const [key, value] of Object.entries(meta.params)) {
            console.log(this.refInputs.get(key)?.current);
            params[key] = this.refInputs.get(key)?.current?.onExecute();
        }
        console.log('params', params);

        // 收集Details的数据
        const details = this.details.current?.onExecute();
        console.log('details', details);

        // 执行API调用
        fetch('/api/execute?' + new URLSearchParams({
            script_path: path,
            callable: selected,
        }), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ params, details }),
        }).then(res => {
            if (res.ok) {
                res.json().then(data => {
                    // 更新输出组件
                    for (let i = 0; i < data.length; i++) {
                        const item = data[i];
                        const outputComponent = this.getRef(i.toString(), this.refOutputs).current;
                        if (outputComponent) {
                            outputComponent.onUpdate(item);
                        }
                    }
                });
            }
        });
    }

    renderSelect = (meta: FunctionMeta): JSX.Element => {
        const { selectedFunc } = this.state;
        const first = Object.keys(meta)[0];
        const keys = Object.keys(meta).map((key, idx) => ({ name: key, rank: idx + 1 } as Callable));

        const filterFunc: ItemPredicate<Callable> = (query, func, _index, exactMatch) => {
            const normalizedTitle = func.name.toLowerCase();
            const normalizedQuery = query.toLowerCase();

            if (exactMatch) {
                return normalizedTitle === normalizedQuery;
            } else {
                return `${func.rank}. ${normalizedTitle}`.indexOf(normalizedQuery) >= 0;
            }
        };

        const renderFunc: ItemRenderer<Callable> = (func, { handleClick, handleFocus, modifiers }) => {
            if (!modifiers.matchesPredicate) {
                return null;
            }
            return (
                <MenuItem
                    active={modifiers.active}
                    disabled={modifiers.disabled}
                    key={func.rank}
                    onClick={handleClick}
                    onFocus={handleFocus}
                    roleStructure="listoption"
                    text={`${func.rank}. ${func.name}`}
                />
            );
        };

        return (
            <Select<Callable>
                items={keys}
                itemPredicate={filterFunc}
                itemRenderer={renderFunc}
                noResults={<MenuItem disabled={true} text="No results." roleStructure="listoption" />}
                onItemSelect={this.handleSelectFunc}
            >
                <Button
                    className="functional-ui-select"
                    text={selectedFunc?.name ?? first}
                    rightIcon="double-caret-vertical"
                />
            </Select>
        );
    }

    renderInputs = (meta: Params): JSX.Element => {
        return (
            <div>
                {Object.entries(meta.params).map(([key, value]) => (
                    <Card key={key} elevation={Elevation.TWO} className="functional-ui-card">
                        <ComponentTabRef
                            name={key}
                            root_path={this.state.root_path}
                            script_path={this.props.path}
                            type={value}
                            port='input'
                            ref={this.getRef(key, this.refInputs)}
                        />
                    </Card>
                ))}
            </div>
        );
    }

    renderOutputs = (meta: Params): JSX.Element => {

        return (
            <div>
                {Object.entries(meta.returns).map(([key, value]) => (
                    <Card key={key} elevation={Elevation.TWO} className="functional-ui-card">
                        <ComponentTabRef
                            name={'output_' + key}
                            root_path={this.state.root_path}
                            script_path={this.props.path}
                            type={value}
                            port='output'
                            ref={this.getRef(key, this.refOutputs)}
                        />
                    </Card>
                ))}
            </div>
        );
    }

    renderContent = (meta: FunctionMeta): JSX.Element => {
        const { selectedFunc, isOpen } = this.state;
        const { path } = this.props;

        const selected = selectedFunc?.name ?? Object.keys(meta)[0];

        return (
            <div>
                {this.renderSelect(meta)}
                <div className="functional-ui-container">
                    <div className="functional-ui-input">
                        Input
                        {this.renderInputs(meta[selected])}
                    </div>
                    <div className="functional-ui-button">
                        <Button intent="primary" text="Run" onClick={this.handleRun} />
                    </div>
                    <div className="functional-ui-output">
                        Output
                        {this.renderOutputs(meta[selected])}
                    </div>
                </div>
                <Button intent="primary" onClick={this.toggleDetails}>
                    {isOpen ? "Hide Details" : "Show Details"}
                </Button>
                <Collapse isOpen={isOpen} keepChildrenMounted={true}>
                    <DetailsPanel path={path} selected={selected} ref={this.details} />
                </Collapse>
            </div>
        );
    }

    render(): JSX.Element {
        const { path } = this.props;
        const { functions, loading, error } = this.state;

        return (
            <div className='functional-ui-root'>
                <h1>Functional UI</h1>
                <p>Path: {path}</p>

                {loading ? (
                    <p>Loading...</p>
                ) : error ? (
                    <p>Error: {error.message}</p>
                ) : functions ? (
                    this.renderContent(functions)
                ) : null}
            </div>
        );
    }
}

export class FunctionalUIProvider implements UIProvider {
    getName(): string {
        return 'functional';
    }

    getUI(path: string): JSX.Element {
        return <FunctionalUI path={path} />;
    }
}

export default FunctionalUI;