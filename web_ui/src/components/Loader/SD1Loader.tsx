
export function SD1ModelLoader() {
    return <div>
        <input name='file_field' type="file" />
        <button>Upload</button>        
    </div>
}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'SD1ModelLoader', 'type': 'ssui.SD1.SD1Model', 'port': 'input', 'component': SD1ModelLoader } as ComponentRegister,
].forEach(registerComponent);