import { Text, Button, Card, H4, Tab, Tabs } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { getComponentsByType, PythonType } from '../ComponentsManager';
import { ReactNode } from 'react';

export class ListContainer extends IComponent<{ port: string, root_path: string, script_path: string, type_args: PythonType[] }, { items: any[] }> {
    constructor(props: { port: string, root_path: string, script_path: string, type_args: PythonType[] }) {
        super(props);

        this.state = {
            items: []
        };
    }

    private tabs_ref: React.RefObject<Tabs> = React.createRef<Tabs>();
    private ref_array: { [key: string]: React.RefObject<ComponentRef> } = {};

    handleAdd = () => {
        this.setState(prevState => ({
            items: [...prevState.items, null]
        }));
    };

    handleRemove = (index: number) => {
        this.setState(prevState => ({
            items: prevState.items.filter((_, i) => i !== index)
        }));
    };

    handleItemChange = (index: number, value: any) => {
        this.setState(prevState => ({
            items: prevState.items.map((item, i) => i === index ? value : item)
        }));
    };

    renderItem(components: ComponentRegister[], subType: PythonType) {
        let num = components.filter(c => c.port == this.props.port).length;
        return num > 1 ?
            <Tabs ref={this.tabs_ref}>
                {components.filter(c => c.port == this.props.port)
                    .map(c => <Tab key={c.name} id={c.name} title={c.name}
                        panel={<ComponentRef
                            name={c.name} type={c.type} port={this.props.port}
                            root_path={this.props.root_path} script_path={this.props.script_path} type_args={subType.args} />} />)}
            </Tabs>
            : num == 1 ? <ComponentRef
                name={components.filter(c => c.port == this.props.port)[0].name} type={components.filter(c => c.port == this.props.port)[0].type} port={this.props.port}
                root_path={this.props.root_path} script_path={this.props.script_path} type_args={subType.args} /> :
                <div>没有可用的组件</div>;
    }

    render(): ReactNode {
        const { items } = this.state;
        const { type_args } = this.props;
        const subType = type_args[0];
        let components = getComponentsByType(subType.type);
        console.log('list container', components, this.props);
        return (
            <div>
                <div style={{ marginBottom: '10px' }}>
                    {items.map((item, index) => (
                        <Card key={index} elevation={1} style={{ marginBottom: '5px', padding: '8px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ flex: 1 }}>
                                    {this.renderItem(components, subType)}
                                </div>
                                <Button
                                    icon="trash"
                                    intent="danger"
                                    variant="minimal"
                                    onClick={() => this.handleRemove(index)}
                                />
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
                    添加项
                </Button>
            </div>
        );
    }

    onExecute(): any {
        return { 'items': this.state.items };
    }
}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';
import { ComponentRef } from '../ComponentRef';
import React from 'react';
[
    { 'name': 'ListContainer', 'type': 'typing.List', 'port': 'input', 'component': ListContainer } as ComponentRegister,
].forEach(registerComponent);