import React from "react";
import { UIProvider } from "../UIProvider";
import { Card, Elevation, InputGroup, Tag } from "@blueprintjs/core";

interface InstalledModel {
    name: string;
    path: string;
    base_model?: string;
    type?: string;
    description?: string;
    tags?: string[];
}

type ModelManagerProps = {
    path: string;
};

type ModelManagerState = {
    models: InstalledModel[];
    loading: boolean;
    error: string | null;
    filter: string;
};

export class ModelManager extends React.Component<ModelManagerProps, ModelManagerState> {
    constructor(props: ModelManagerProps) {
        super(props);
        this.state = {
            models: [],
            loading: true,
            error: null,
            filter: ""
        };
    }

    componentDidMount() {
        this.fetchModels();
    }

    fetchModels = async () => {
        try {
            const response = await fetch('/api/available_models');
            if (!response.ok) {
                throw new Error(`Failed to fetch models: ${response.status}`);
            }
            const models = await response.json();
            this.setState({ models, loading: false, error: null });
        } catch (error) {
            this.setState({
                loading: false,
                error: error instanceof Error ? error.message : 'Failed to fetch models'
            });
        }
    };

    handleFilterChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        this.setState({ filter: event.target.value });
    };

    render() {
        const { models, loading, error, filter } = this.state;
        const keyword = filter.trim().toLowerCase();
        const filtered = keyword
            ? models.filter(m =>
                (m.name || '').toLowerCase().includes(keyword) ||
                (m.path || '').toLowerCase().includes(keyword) ||
                (m.base_model || '').toLowerCase().includes(keyword) ||
                (m.tags || []).some(t => t.toLowerCase().includes(keyword))
            )
            : models;

        return (
            <div style={{ padding: '16px', maxWidth: '720px', margin: '0 auto' }}>
                <h3>Model Manager</h3>
                <div style={{ marginBottom: '12px', display: 'flex', gap: '8px' }}>
                    <InputGroup
                        leftIcon="search"
                        placeholder="Filter by name / type / tag..."
                        value={filter}
                        onChange={this.handleFilterChange}
                        style={{ flex: 1 }}
                    />
                    <Tag minimal large>{filtered.length} / {models.length}</Tag>
                </div>

                {loading ? (
                    <div>Loading models...</div>
                ) : error ? (
                    <div style={{ color: 'red' }}>Error: {error}</div>
                ) : filtered.length === 0 ? (
                    <div>No models found.</div>
                ) : (
                    filtered.map((model, index) => (
                        <Card key={model.path || index} elevation={Elevation.ONE} style={{ marginBottom: '8px', padding: '12px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
                                <strong>{model.name}</strong>
                                <Tag minimal>{model.base_model || model.type || 'unknown'}</Tag>
                            </div>
                            <div style={{ fontSize: '12px', color: 'var(--ssui-fg-muted)', marginTop: '4px', wordBreak: 'break-all' }}>{model.path}</div>
                            {(model.tags || []).length > 0 && (
                                <div style={{ marginTop: '6px' }}>
                                    {model.tags!.map(tag => (
                                        <Tag key={tag} intent="primary" minimal style={{ marginRight: '4px' }}>{tag}</Tag>
                                    ))}
                                </div>
                            )}
                        </Card>
                    ))
                )}
            </div>
        );
    }
}

export class ModelManagerUIProvider implements UIProvider {
    getName(): string {
        return 'model-manager';
    }

    getUI(path: string): JSX.Element {
        return <ModelManager path={path} />;
    }
}
