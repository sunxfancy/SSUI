
import { IComponent } from "./IComponent";
import { getComponent, getComponentsByType, parsePythonTyping, PythonType } from "./ComponentsManager";
import React from 'react';
import { Tabs, Tab, TabsExpander, Label } from "@blueprintjs/core";
import styles from './ComponentRef.module.css'

export interface ComponentRefProps {
    name: string;
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
        let c = getComponent(this.props.name);
        return c ? c.createComponent(this.ref, this.props) :
            <div>Component {this.props.name} not found</div>;
    }

    onExecute() {
        return this.ref.current?.onExecute();
    }

    onUpdate(data: any) {
        return this.ref.current?.onUpdate(data);
    }
}

export class ComponentTabRef extends IComponent<ComponentRefProps> {
    constructor(props: ComponentRefProps) {
        super(props);
        this.parsed_type = parsePythonTyping(this.props.type);
        console.log(this.parsed_type);
        let components = getComponentsByType(this.parsed_type.type);
        console.log(components);
        for (let c of components) {
            this.ref_array[c.name] = React.createRef<ComponentRef>();
        }
    }
    private parsed_type: PythonType;
    private tabs_ref: React.RefObject<Tabs> = React.createRef<Tabs>();
    private ref_array: { [key: string]: React.RefObject<ComponentRef> } = {};

    render() {
        let components = getComponentsByType(this.parsed_type.type);
        return <Tabs ref={this.tabs_ref}>
            <div className={styles.refTitle}>{this.props.name}</div>
            <TabsExpander />
            {components.filter(c => c.port == this.props.port)
                .map(c =>
                    <Tab key={c.name} id={c.name} title={c.name}
                         panel={<ComponentRef
                             name={c.name} type={c.type} ref={this.ref_array[c.name]} port={this.props.port}
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
