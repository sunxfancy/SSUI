import { Text } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import styles from './test.module.css'

export class StringEditor extends IComponent<{}, { textContent: string }> {
    render(): ReactNode {
        return <input type="text" className={styles.normal}></input>
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
    { 'name': 'StringEditor', 'type': 'builtins.str', 'port': 'input', 'component': StringEditor } as ComponentRegister,
    { 'name': 'StringPreview', 'type': 'builtins.str', 'port': 'output', 'component': StringPreview } as ComponentRegister
].forEach(registerComponent);
