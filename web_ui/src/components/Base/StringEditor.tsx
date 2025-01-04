import {Text} from '@blueprintjs/core';

export function StringEditor() {
    return <Text>String Editor</Text>
}

export function StringPreview() {
    return <p>String Preview</p>
}


// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';
[
    { 'name': 'StringEditor', 'type': 'string', 'port': 'input', 'component': StringEditor } as ComponentRegister,
    { 'name': 'StringPreview', 'type': 'string', 'port': 'output', 'component': StringPreview } as ComponentRegister
].forEach(registerComponent);