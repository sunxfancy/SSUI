
import { IComponent } from "./IComponent";
import { resolveComponent, getComponentsByType, parsePythonTyping, PythonType } from "./ComponentsManager";
import React from 'react';
import { UIStateScope } from '../UIState';
import { Tabs, Tab, TabsExpander, Label } from "@blueprintjs/core";
import styles from './ComponentRef.module.css'

export interface ComponentRefProps {
    name: string;
    parameterName?: string;
    type: string;
    port: string;
    root_path: string;
    script_path?: string;
    type_args?: PythonType[];
}

export class ComponentRef extends IComponent<ComponentRefProps> {
    constructor(props: ComponentRefProps) {
        super(props);
        this.ref = React.createRef<IComponent>();
    }

    private ref: React.RefObject<IComponent>;

    render() {
        let c = resolveComponent(this.props.name, this.props);
        return c ? <UIStateScope name={this.props.name + ":" + this.props.type}>{c.createComponent(this.ref, this.props)}</UIStateScope> :
            <div>Component {this.props.name} not found</div>;
    }

    onExecute() {
        return this.ref.current?.onExecute();
    }

    onUpdate(data: any) {
        return this.ref.current?.onUpdate(data);
    }
}

export class ComponentTabRef extends IComponent<ComponentRefProps, { selected: string }> {
    constructor(props: ComponentRefProps) {
        super(props);
        this.parsed_type = parsePythonTyping(this.props.type);
        let components = getComponentsByType(this.parsed_type.type, this.props.port);
        for (let c of components) {
            this.ref_array[c.name] = React.createRef<ComponentRef>();
        }
    }
    state = { selected: '' };
    protected persistedFields: 'selected'[] = ['selected'];
    private parsed_type: PythonType;
    private tabs_ref: React.RefObject<Tabs> = React.createRef<Tabs>();
    private ref_array: { [key: string]: React.RefObject<ComponentRef> } = {};

    render() {
        let components = getComponentsByType(this.parsed_type.type, this.props.port);
        return <Tabs ref={this.tabs_ref} selectedTabId={components.some(component => component.name === this.state.selected) ? this.state.selected : components[0]?.name}
            onChange={selected => this.setState({ selected: String(selected) })}>
            <div className={styles.refTitle}>{this.props.name}</div>
            <TabsExpander />
            {components.map(c =>
                    <Tab key={c.name} id={c.name} title={c.name}
                         panel={<ComponentRef
                             name={c.name} type={this.props.type} ref={this.ref_array[c.name]} port={this.props.port}
                             parameterName={this.props.parameterName ?? this.props.name}
                             root_path={this.props.root_path} script_path={this.props.script_path} type_args={this.parsed_type.args} />} />)}

        </Tabs>
    }

    override onExecute() {
        let selected = this.tabs_ref.current?.state.selectedTabId;
        if (!selected) return;
        return this.ref_array[selected]?.current?.onExecute();
    }

    override onUpdate(data: any): void {
        let selected = this.tabs_ref.current?.state.selectedTabId;
        if (!selected) return;
        this.ref_array[selected]?.current?.onUpdate(data);
    }
}
