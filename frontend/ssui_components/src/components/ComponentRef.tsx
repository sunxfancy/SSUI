
import { IComponent } from "./IComponent";
import { getComponent, getComponentsByType } from "./ComponentsManager";
import React from 'react';
import { Tabs, Tab, TabsExpander, Label } from "@blueprintjs/core";

export class ComponentRef extends IComponent<{ name: string, root_path: string, script_path?: string }> {
    constructor(props: { name: string, root_path: string, script_path?: string }) {
        super(props);
        this.ref = React.createRef<IComponent>();
    }

    private ref: React.RefObject<IComponent>;

    render() {
        let c = getComponent(this.props.name);
        return c ? c.createComponent(this.ref, this.props.root_path, this.props.script_path) :
            <div>Component {this.props.name} not found</div>;
    }

    onExecute() {
        return this.ref.current?.onExecute();
    }

    onUpdate(data: any) {
        return this.ref.current?.onUpdate(data);
    }
}

type ComponentRefProps = {
    name: string;
    type: string;
    port: string;
    root_path: string;
    script_path?: string;
}

export class ComponentTabRef extends IComponent<ComponentRefProps> {
    constructor(props: ComponentRefProps) {
        super(props);
        let components = getComponentsByType(this.props.type);
        for (let c of components) {
            this.ref_array[c.name] = React.createRef<ComponentRef>();
        }
    }

    private tabs_ref: React.RefObject<Tabs> = React.createRef<Tabs>();
    private ref_array: { [key: string]: React.RefObject<ComponentRef> } = {};

    render() {
        let components = getComponentsByType(this.props.type);
        return <Tabs ref={this.tabs_ref}>
            <Label>
                {this.props.name}
            </Label>
            <TabsExpander />
            {components.filter(c => c.port == this.props.port)
                .map(c =>
                    <Tab key={c.name} id={c.name} title={c.name}
                        panel={<ComponentRef 
                            name={c.name} ref={this.ref_array[c.name]} 
                            root_path={this.props.root_path} script_path={this.props.script_path} />} />)}
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