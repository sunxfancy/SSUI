import { IComponent } from '../IComponent';

class SD1ModelLoader extends IComponent {
    onExecute() {
        return { 'file': 'file' };
    }

    render() {
        return <div>
            <input name='file_field' type="file" />
        </div>
    }
}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'SD1ModelLoader', 'type': 'ssui.SD1.SD1Model', 'port': 'input', 'component': SD1ModelLoader, } as ComponentRegister,
].forEach(registerComponent);