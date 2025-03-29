import {TextArea} from '@blueprintjs/core';
import React from 'react';
import { IComponent } from '../IComponent';

class PromptEditor extends IComponent<{}, {textContent: string}> {
    constructor(props: {}) {
        super(props);
        this.state = {textContent: ''};
        this.onInputChange = this.onInputChange.bind(this);
    }

    onInputChange(event: React.ChangeEvent<HTMLTextAreaElement>) {
        this.setState({textContent: event.target.value});
    }

    onExecute(): any {
        return { 'function': 'ssui.base.Prompt.create', 'params': { 'text': this.state.textContent } };
    }

    render() {
        return <TextArea fill={true} value={this.state.textContent} onChange={this.onInputChange} />
    }
}


// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';
[
    { 'name': 'PromptEditor', 'type': 'ssui.base.Prompt', 'port': 'input', 'component': PromptEditor } as ComponentRegister,
].forEach(registerComponent);