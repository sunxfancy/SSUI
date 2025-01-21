import { Text } from '@blueprintjs/core';
import { IComponent } from '../IComponent';

export class StringEditor extends IComponent<{}, { textContent: string }> {
    render(): ReactNode {
        return <Text>String Editor</Text>
    }

    onExecute(): any {
        return { 'textContent': this.state.textContent };
    }
}

export class StringPreview extends IComponent<{}, { textContent: string }> {
    render() {
        return <p>String Preview</p>
    }
}

import { ReactNode } from 'react';
// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';
[
    { 'name': 'StringEditor', 'type': 'string', 'port': 'input', 'component': StringEditor } as ComponentRegister,
    { 'name': 'StringPreview', 'type': 'string', 'port': 'output', 'component': StringPreview } as ComponentRegister
].forEach(registerComponent);