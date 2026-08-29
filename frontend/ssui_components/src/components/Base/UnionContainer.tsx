import React from 'react';
import { Checkbox, HTMLSelect, Tag } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { ComponentRef } from '../ComponentRef';
import { ComponentRegister, PythonType, getComponentsByType, registerComponent } from '../ComponentsManager';
import './components.css';

type UnionContainerProps = {
    port: string;
    root_path: string;
    script_path?: string;
    type_args?: PythonType[];
};

type UnionContainerState = { selected: number; enabled: boolean };

class UnionContainer extends IComponent<UnionContainerProps, UnionContainerState> {
    state: UnionContainerState = { selected: 0, enabled: true };
    private componentRefs = new Map<number, React.RefObject<ComponentRef>>();

    private choices() {
        return (this.props.type_args ?? []).filter(item =>
            !['None', 'NoneType', 'builtins.NoneType', 'types.NoneType'].includes(item.type)
        );
    }

    private allowsNone() {
        return (this.props.type_args ?? []).some(item =>
            ['None', 'NoneType', 'builtins.NoneType', 'types.NoneType'].includes(item.type)
        );
    }

    private getRef(index: number) {
        const current = this.componentRefs.get(index);
        if (current) return current;
        const ref = React.createRef<ComponentRef>();
        this.componentRefs.set(index, ref);
        return ref;
    }

    override onExecute() {
        if (this.allowsNone() && !this.state.enabled) return null;
        return this.getRef(this.state.selected).current?.onExecute();
    }

    override render() {
        const choices = this.choices();
        const selectedType = choices[this.state.selected] ?? choices[0];
        if (!selectedType) return <div className="component-union-empty">这个联合类型没有可用选项。</div>;
        const component = getComponentsByType(selectedType.type, this.props.port)[0];
        return <div className="component-union">
            <div className="component-union-toolbar">
                {this.allowsNone() && <Checkbox checked={this.state.enabled} label="提供值"
                    onChange={event => this.setState({ enabled: event.currentTarget.checked })} />}
                {choices.length > 1 ? <HTMLSelect value={this.state.selected}
                    onChange={event => this.setState({ selected: Number(event.target.value) })}>
                    {choices.map((choice, index) => <option key={`${choice.type}-${index}`} value={index}>{choice.type}</option>)}
                </HTMLSelect> : <Tag minimal>{selectedType.type}</Tag>}
            </div>
            {(!this.allowsNone() || this.state.enabled) && <ComponentRef
                key={`${this.state.selected}-${selectedType.type}`}
                ref={this.getRef(this.state.selected)}
                name={component.name}
                type={selectedType.type}
                port={this.props.port}
                root_path={this.props.root_path}
                script_path={this.props.script_path}
                type_args={selectedType.args}
            />}
        </div>;
    }
}

[
    { name: 'OptionalContainer', type: 'typing.Optional', port: 'input', component: UnionContainer },
    { name: 'UnionContainer', type: 'typing.Union', port: 'input', component: UnionContainer },
    { name: 'UnionTypeContainer', type: 'types.UnionType', port: 'input', component: UnionContainer },
].forEach(item => registerComponent(item as ComponentRegister));

export { UnionContainer };
