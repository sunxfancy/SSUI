import { IControler, IControlerProps } from "./IControler";
import { Alignment, Button, MenuItem, Slider, Switch } from "@blueprintjs/core";

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


interface SelectItem {
    name: string;
    rank: number;
}

export class SelectControler extends IControler<{ value: string }> {
    constructor(props: IControlerProps) {
        super(props);

        this.state = {
            value: this.props.default ?? ''
        }
    }

    onExecute() {
        return this.state.value;
    }

    setValue = (item: SelectItem, event?: React.SyntheticEvent<HTMLElement>) => {
        this.setState({ value: item.name });
    }

    render() {
        const renderFunc: ItemRenderer<SelectItem> = (Func, { handleClick, handleFocus, modifiers }) => {
            if (!modifiers.matchesPredicate) {
                return null;
            }
            return (
                <MenuItem
                    active={modifiers.active}
                    disabled={modifiers.disabled}
                    key={Func.rank}
                    onClick={handleClick}
                    onFocus={handleFocus}
                    roleStructure="listoption"
                    text={`${Func.rank}. ${Func.name}`}
                />
            );
        };

        let keys = this.props.params ? this.props.params.options : [];
        let items = [];
        for (let i = 0; i < keys.length; i++) {
            items.push({ name: keys[i], rank: i } as SelectItem);
        }
        console.log(items);

        return <Select<SelectItem>
            items={items}
            itemRenderer={renderFunc}
            noResults={<MenuItem disabled={true} text="No results." roleStructure="listoption" />}
            onItemSelect={this.setValue}
        >
            <Button className="functional-ui-select" text={this.state.value} rightIcon="double-caret-vertical" />
        </Select>
    }
}


export class RandomControler extends IControler<{ value: number; userInput: boolean }> {
    constructor(props: IControlerProps) {
        super(props);
    }
    
    state = {
        value: Math.floor(Math.random() * 1000000000),
        userInput: false
    };

    componentDidMount() {
        if (this.props.params && this.props.params.default !== undefined) {
            this.setState({ value: this.props.params.default });
        }
    }

    onExecute() {
        if (!this.state.userInput) {
            this.setState({
                value: Math.floor(Math.random() * 1000000000),
            });
        }
        return this.state.value;
    }

    handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        if (value === '') {
            this.setState({ 
                value: Math.floor(Math.random() * 1000000000),
                userInput: false 
            });
        } else {
            const numValue = parseInt(value, 10);
            if (!isNaN(numValue)) {
                this.setState({ 
                    value: numValue,
                    userInput: true 
                });
            }
        }
    }

    generateRandom = () => {
        this.setState({ 
            value: Math.floor(Math.random() * 1000000000),
            userInput: false 
        });
    }

    render() {
        return (
            <div className="functional-ui-random" style={{ display: 'flex', alignItems: 'center' }}>
                <input
                    type="text"
                    value={this.state.value}
                    onChange={this.handleInputChange}
                    style={{ marginRight: '8px', width: '120px' }}
                />
                <Button icon="random" onClick={this.generateRandom} minimal={true} />
            </div>
        );
    }
}


import { registerControler, ControlerRegister } from './IControler';
import { ItemPredicate, ItemRenderer, Select } from "@blueprintjs/select";
[
    { 'name': 'Slider', 'component': SliderControler } as ControlerRegister,
    { 'name': 'Switch', 'component': SwitchControler } as ControlerRegister,
    { 'name': 'Select', 'component': SelectControler } as ControlerRegister,
    { 'name': 'Random', 'component': RandomControler } as ControlerRegister,
].forEach(registerControler);
