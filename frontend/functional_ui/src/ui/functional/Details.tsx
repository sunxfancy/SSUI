import React, { Component } from "react";
import { Callout, NonIdealState, Section, SectionCard, Spinner } from "@blueprintjs/core";
import { ControllerRef } from "ssui_components";
import './Details.css';

interface ScriptDetails {
    [key: string]: {
        [key: string]: {
            controller: string;
            args: any;
            default: any;
        };
    };
}

type PrepareResponse = ScriptDetails | { error: string };

interface DetailsProps {
    path: string;
    selected: string;
}

interface DetailsState {
    loading: boolean;
    error: Error | null;
    details: ScriptDetails | null;
}

export class DetailsPanel extends Component<DetailsProps, DetailsState> {
    private refMap: Map<string, Map<string, React.RefObject<ControllerRef>>> = new Map();
    private detailsRequest?: AbortController;

    constructor(props: DetailsProps) {
        super(props);
        this.state = {
            loading: true,
            error: null,
            details: null
        };
    }

    componentDidMount() {
        this.fetchDetails();
    }

    componentDidUpdate(prevProps: DetailsProps) {
        if (prevProps.path !== this.props.path || prevProps.selected !== this.props.selected) {
            this.fetchDetails();
        }
    }

    componentWillUnmount() {
        this.detailsRequest?.abort();
    }

    async fetchDetails(): Promise<void> {
        const { path, selected } = this.props;
        this.detailsRequest?.abort();
        const request = new AbortController();
        this.detailsRequest = request;
        this.refMap.clear();

        try {
            this.setState({ loading: true, error: null });

            const response = await fetch('/api/prepare?' + new URLSearchParams({
                script_path: path,
                callable: selected,
            }), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    params: {}
                }),
                signal: request.signal,
            });

            if (!response.ok) {
                throw new Error('Failed to fetch script details');
            }

            const data = await response.json() as PrepareResponse;
            if ('error' in data && typeof data.error === 'string') {
                throw new Error(data.error);
            }
            this.setState({
                loading: false,
                details: data as ScriptDetails
            });
        } catch (error) {
            if (error instanceof DOMException && error.name === 'AbortError') return;
            this.setState({
                loading: false,
                error: error instanceof Error ? error : new Error('Unknown error')
            });
        }
    }

    getRef = (section: string, index: string): React.RefObject<ControllerRef> => {
        if (!this.refMap.has(section)) {
            this.refMap.set(section, new Map<string, React.RefObject<ControllerRef>>());
        }

        const sectionMap = this.refMap.get(section);
        if (!sectionMap) {
            throw new Error('Section map not found');
        }

        if (!sectionMap.has(index)) {
            const newRef = React.createRef<ControllerRef>();
            sectionMap.set(index, newRef);
            return newRef;
        }

        const ref = sectionMap.get(index);
        if (!ref) {
            const newRef = React.createRef<ControllerRef>();
            sectionMap.set(index, newRef);
            return newRef;
        }

        return ref;
    }

    onExecute() {
        let result: any = {};
        for (const section of this.refMap.keys()) {
            result[section] = {};
            for (const control of this.refMap.get(section)?.keys() ?? []) {
                result[section][control] = this.getRef(section, control).current?.onExecute();
            }
        }
        return result;
    }

    renderControllers = (details: ScriptDetails): React.ReactNode => {
        return Object.entries(details).map(([section, controls]) => (
            <Section
                key={section}
                title={section}
                collapsible={true}
                collapseProps={{ defaultIsOpen: true }}
            >
                {Object.entries(controls).map(([name, control]) => (
                    <SectionCard key={name}>
                        <ControllerRef
                            name={name}
                            type={control.controller}
                            params={control.args}
                            default={control.default}
                            ref={this.getRef(section, name)}
                        />
                    </SectionCard>
                ))}
            </Section>
        ));
    }

    renderContent = (details: ScriptDetails): React.ReactNode => {
        if (Object.keys(details).length === 0) {
            return (
                <NonIdealState
                    className="details-empty"
                    icon="clean"
                    title="无需高级参数"
                    description="这个函数可以直接使用上方输入运行。"
                />
            );
        }

        return (
            <div className="details-container">
                <div className="details-heading">
                    <div>
                        <span>Advanced controls</span>
                        <h3>高级参数</h3>
                    </div>
                    <p>调整运行环境与生成策略</p>
                </div>
                <div className="details-scrollable">
                    {this.renderControllers(details)}
                </div>
            </div>
        );
    }

    render(): React.ReactNode {
        const { loading, error, details } = this.state;

        if (loading) {
            return <div className="details-loading"><Spinner size={20} /><span>正在准备参数…</span></div>;
        }

        if (error) {
            return <Callout intent="danger" icon="error" title="无法加载高级参数">{error.message}</Callout>;
        }

        return this.renderContent(details || {});
    }
}
