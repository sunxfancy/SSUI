import {TextArea} from '@blueprintjs/core';

export function PromptEditor() {
    // const [state, setState] = React.useState({textContent: ''});
    // const onInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    //     setState({textContent: event.target.value});
    // }

    return <TextArea fill={true} value="" />
}


// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';
[
    { 'name': 'PromptEditor', 'type': 'ssui.base.Prompt', 'port': 'input', 'component': PromptEditor } as ComponentRegister,
].forEach(registerComponent);