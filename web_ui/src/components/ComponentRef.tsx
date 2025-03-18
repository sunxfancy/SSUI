
import { IComponent } from "./IComponent";
import { getComponent, getComponentsByType } from "./ComponentsManager";
import React from 'react';
import { Tabs, Tab } from "@blueprintjs/core";

export class ComponentRef extends IComponent<{ name: string }> {
    constructor(props: { name: string }) {
        super(props);
        this.ref = React.createRef<IComponent>();
    }

    private ref: React.RefObject<IComponent>;

    render() {
        let c = getComponent(this.props.name);
        return c ? c.createComponent(this.ref) :
            <div>Component {this.props.name} not found</div>;
    }

    onExecute() {
        return this.ref.current?.onExecute();
    }

    onUpdate(data: any) {
        return this.ref.current?.onUpdate(data);
    }
}

export class ComponentTabRef extends IComponent<{ type: string, port: string }> {
    constructor(props: { type: string, port: string}) {
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
            {components.filter(c => c.port == this.props.port)
                .map(c => 
                <Tab key={c.name} id={c.name} title={c.name} 
                    panel={<ComponentRef name={c.name} ref={this.ref_array[c.name]} />} />)}
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