import { Button, Card, Tabs, Tab } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { getComponentsByType, PythonType } from '../ComponentsManager';
import { ComponentRef } from '../ComponentRef';
import { ReactNode } from 'react';

interface ListContainerProps {
    port: string;
    root_path: string;
    script_path: string;
    type_args: PythonType[];
}

interface ListItem {
    key: number;
}

export class ListContainer extends IComponent<ListContainerProps, { items: ListItem[] }> {
    private nextKey: number = 0;
    private itemRefs: { [key: number]: React.RefObject<ComponentRef> } = {};

    constructor(props: ListContainerProps) {
        super(props);
        this.state = {
            items: []
        };
    }

    handleAdd = () => {
        const key = this.nextKey++;
        this.setState(prevState => ({
            items: [...prevState.items, { key }]
        }));
    };

    handleRemove = (key: number) => {
        this.setState(prevState => ({
            items: prevState.items.filter(item => item.key !== key)
        }));
        delete this.itemRefs[key];
    };

    moveItem = (index: number, direction: -1 | 1) => {
        this.setState(prevState => {
            const items = [...prevState.items];
            const target = index + direction;
            if (target < 0 || target >= items.length) {
                return prevState;
            }
            [items[index], items[target]] = [items[target], items[index]];
            return { items };
        });
    };

    private getItemRef = (key: number): React.RefObject<ComponentRef> => {
        if (!this.itemRefs[key]) {
            this.itemRefs[key] = React.createRef<ComponentRef>();
        }
        return this.itemRefs[key];
    };

    renderItem(item: ListItem, subType: PythonType): ReactNode {
        const components = getComponentsByType(subType.type, this.props.port);
        const commonProps = {
            port: this.props.port,
            root_path: this.props.root_path,
            script_path: this.props.script_path,
            type_args: subType.args
        };

        if (components.length > 1) {
            return (
                <Tabs key={item.key}>
                    {components.map(c => (
                        <Tab
                            key={c.name}
                            id={c.name}
                            title={c.name}
                            panel={<ComponentRef ref={this.getItemRef(item.key)} name={c.name} type={subType.type} {...commonProps} />}
                        />
                    ))}
                </Tabs>
            );
        }
        if (components.length === 1) {
            const component = components[0];
            return (
                <ComponentRef
                    ref={this.getItemRef(item.key)}
                    name={component.name}
                    type={subType.type}
                    {...commonProps}
                />
            );
        }
        return <div>No available component</div>;
    }

    render(): ReactNode {
        const { items } = this.state;
        const { type_args } = this.props;
        const subType = type_args?.[0] ?? { type: 'typing.Any' };
        return (
            <div>
                <div style={{ marginBottom: '10px' }}>
                    {items.map((item, index) => (
                        <Card key={item.key} elevation={1} style={{ marginBottom: '5px', padding: '8px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ flex: 1 }}>
                                    {this.renderItem(item, subType)}
                                </div>
                                <div style={{ display: 'flex', gap: '2px', marginLeft: '8px' }}>
                                    <Button
                                        icon="chevron-up"
                                        variant="minimal"
                                        disabled={index === 0}
                                        onClick={() => this.moveItem(index, -1)}
                                        title="Move up"
                                    />
                                    <Button
                                        icon="chevron-down"
                                        variant="minimal"
                                        disabled={index === items.length - 1}
                                        onClick={() => this.moveItem(index, 1)}
                                        title="Move down"
                                    />
                                    <Button
                                        icon="trash"
                                        intent="danger"
                                        variant="minimal"
                                        onClick={() => this.handleRemove(item.key)}
                                        title="Remove"
                                    />
                                </div>
                            </div>
                        </Card>
                    ))}
                </div>
                <Button
                    icon="plus"
                    intent="success"
                    onClick={this.handleAdd}
                    style={{ width: '100%' }}
                >
                    Add Item
                </Button>
            </div>
        );
    }

    onExecute(): any {
        return {
            items: this.state.items.map(item => this.getItemRef(item.key).current?.onExecute())
        };
    }
}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';
import React from 'react';
[
    { 'name': 'ListContainer', 'type': 'typing.List', 'port': 'input', 'component': ListContainer } as ComponentRegister,
].forEach(registerComponent);
