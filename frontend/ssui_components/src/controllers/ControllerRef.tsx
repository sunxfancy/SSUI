import { IComponent } from "../components/IComponent";
import { getController, IController } from "./IController";
import { Label } from "@blueprintjs/core";
import React from 'react';

type ControllerRefProps = {
    name: string;
    type: string;
    params: any;
    default: any;
}

export class ControllerRef extends IComponent<ControllerRefProps> {
    constructor(props: ControllerRefProps) {
        super(props);
        this.ref = React.createRef<IController>();
    }

    private ref: React.RefObject<IController>;

    render() {
        let c = getController(this.props.type);
        return c ?
            <div><Label>{this.props.name}</Label>
            {c.createController(this.props.params, this.props.default, this.ref)}</div> :
            <div>Controller {this.props.type} not found</div>;
    }

    onExecute() {
        return this.ref.current?.onExecute();
    }
}

