import { IComponent } from '../IComponent';
import React, { Component } from 'react';

class SD1ModelLoader extends Component {
    state = {
        filePath: ''
    };

    onExecute() {
        return { 'file': this.state.filePath, 'type': 'ssui.SD1.SD1Model' };
    }

    render() {
        return <div>
            <input name='file_field' type="file" onChange={this.handleFileChange} />
        </div>
    }

    handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            this.setState({ filePath: file.name });
        }
    }
}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'SD1ModelLoader', 'type': 'ssui.SD1.SD1Model', 'port': 'input', 'component': SD1ModelLoader, } as ComponentRegister,
].forEach(registerComponent);