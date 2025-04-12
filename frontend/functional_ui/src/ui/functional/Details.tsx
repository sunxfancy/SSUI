import React, { Component } from "react";
import { Section, SectionCard } from "@blueprintjs/core";
import '../../controlers/InternalControlers'; // Register controlers
import { ControlerRef } from "../../controlers/ControlerRef";

type ScriptDetails = {
    [key: string]: {
        [key: string]: {
            controler: string;
            args: any;
            default: any;
        };
    };
}

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
    private refMap: Map<string, Map<string, React.RefObject<ControlerRef>>> = new Map();

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

    async fetchDetails(): Promise<void> {
        const { path, selected } = this.props;
        console.log('DetailsPanel', path, selected);

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
                })
            });

            if (!response.ok) {
                throw new Error('Failed to fetch script details');
            }

            const data = await response.json() as ScriptDetails;
            console.log('Details', data);

            this.setState({
                loading: false,
                details: data
            });
        } catch (error) {
            this.setState({
                loading: false,
                error: error instanceof Error ? error : new Error('Unknown error')
            });
        }
    }

    getRef = (section: string, index: string): React.RefObject<ControlerRef> => {
        if (!this.refMap.has(section)) {
            this.refMap.set(section, new Map<string, React.RefObject<ControlerRef>>());
        }

        const sectionMap = this.refMap.get(section);
        if (!sectionMap) {
            throw new Error('Section map not found');
        }

        if (!sectionMap.has(index)) {
            const newRef = React.createRef<ControlerRef>();
            sectionMap.set(index, newRef);
            return newRef;
        }

        const ref = sectionMap.get(index);
        if (!ref) {
            const newRef = React.createRef<ControlerRef>();
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
                        <ControlerRef
                            name={name}
                            type={control.controler}
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
        return (
            <div>
                <h3>Details</h3>
                {this.renderControllers(details)}
            </div>
        );
    }

    render(): React.ReactNode {
        const { loading, error, details } = this.state;

        if (loading) {
            return <p>Loading...</p>;
        }

        if (error) {
            return <p>Error: {error.message}</p>;
        }

        return this.renderContent(details || {});
    }
}