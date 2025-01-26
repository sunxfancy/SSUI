import { IComponent } from "../components/IComponent";
import { getControler, IControler } from "./IControler";
import { Label } from "@blueprintjs/core";
import React from 'react';

type ControlerRefProps = {
    name: string;
    type: string;
    params: any;
    default: any;
}

export class ControlerRef extends IComponent<ControlerRefProps> {
    constructor(props: ControlerRefProps) {
        super(props);
        this.ref = React.createRef<IControler>();
    }

    private ref: React.RefObject<IControler>;

    render() {
        let c = getControler(this.props.type);
        return c ?
            <Label>{this.props.name}{c.createControler(this.props.params, this.props.default, this.ref)}</Label> :
            <div>Controler {this.props.type} not found</div>;
    }

    onExecute() {
        return this.ref.current?.onExecute();
    }
}

