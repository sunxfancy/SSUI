import { IControler, IControlerProps } from "./IControler";
import { Alignment, Slider, Switch } from "@blueprintjs/core";

export class SliderControler extends IControler<{ value: number }> {
    constructor(props: IControlerProps) {
        super(props);
        console.log(this.props.params, this.props.default);
        this.state = {
            value: this.props.default ?? 0
        }
    }

    onExecute() {
        return this.state.value;
    }

    setValue = (value: number) => {
        this.setState({ value: value });
    }

    render() {
        if (this.props.params?.labels == undefined) {
            return <Slider value={this.state.value}
                min={this.props.params?.min ?? 0}
                max={this.props.params?.max ?? 0}
                stepSize={this.props.params?.step ?? 1}
                labelStepSize={this.props.params?.max - this.props.params?.min}
                onChange={this.setValue} />;
        } else {
            return <Slider value={this.state.value}
                min={this.props.params?.min ?? 0}
                max={this.props.params?.max ?? 0}
                stepSize={this.props.params?.step ?? 1}
                labelValues={this.props.params?.labels}
                onChange={this.setValue} />;
        }
    }
}

export class SwitchControler extends IControler<{ value: boolean }> {
    constructor(props: IControlerProps) {
        super(props);

        this.state = {
            value: this.props.default ?? false
        }
    }

    onExecute() {
        return this.state.value;
    }

    setValue = (event: React.FormEvent<HTMLInputElement>) => {
        this.setState({ value: event.currentTarget.checked });
    }

    render() {
        return <Switch alignIndicator={Alignment.LEFT} checked={this.state.value} onChange={this.setValue} />;
    }
}


import { registerControler, ControlerRegister } from './IControler';
[
    { 'name': 'Slider', 'component': SliderControler } as ControlerRegister,
    { 'name': 'Switch', 'component': SwitchControler } as ControlerRegister,
].forEach(registerControler);
