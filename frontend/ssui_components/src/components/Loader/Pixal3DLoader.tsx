import { Checkbox, FormGroup, InputGroup } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { ImageUploader } from '../Image/ImageUploader';
import { ComponentRegister, registerComponent, registerComponentVariant } from '../ComponentsManager';

export class Pixal3DModelLoader extends IComponent<{}, { modelPath: string; lowVram: boolean }> {
    state = { modelPath: 'TencentARC/Pixal3D', lowVram: true };
    protected modelType = 'Pixal3D.Pixal3DModel';
    protected modelLabel = 'Pixal3D';
    protected supportsLowVram = true;

    override onExecute() {
        return {
            function: `ssui_3dmodel.${this.modelType}.load`,
            params: { model_path: this.state.modelPath,
                ...(this.supportsLowVram ? { low_vram: this.state.lowVram } : {}) },
        };
    }

    override render() {
        return <div>
            <FormGroup label={`${this.modelLabel} 模型`} helperText="填写本地模型目录或 Hugging Face 模型 ID">
                <InputGroup value={this.state.modelPath} onChange={event => this.setState({ modelPath: event.target.value })} />
            </FormGroup>
            {this.supportsLowVram && <Checkbox label="低显存模式" checked={this.state.lowVram}
                onChange={event => this.setState({ lowVram: event.currentTarget.checked })} />}
        </div>;
    }
}

export class Trellis2ModelLoader extends Pixal3DModelLoader {
    override state = { modelPath: 'microsoft/TRELLIS.2-4B', lowVram: true };
    protected override modelType = 'Trellis2.Trellis2Model';
    protected override modelLabel = 'TRELLIS.2';
}

export class TrellisModelLoader extends Pixal3DModelLoader {
    override state = { modelPath: 'microsoft/TRELLIS-image-large', lowVram: false };
    protected override modelType = 'Trellis.TrellisModel';
    protected override modelLabel = 'TRELLIS';
    protected override supportsLowVram = false;
}

export class Pixal3DImageUploader extends ImageUploader {
    override onExecute() {
        return {
            function: 'ssui_3dmodel.Pixal3D.LoadPixal3DImage',
            params: { path: this.state.image },
        };
    }
}

registerComponent({ name: 'Pixal3DModelLoader', type: 'ssui_3dmodel.Pixal3D.Pixal3DModel',
    port: 'input', component: Pixal3DModelLoader } as ComponentRegister);
registerComponent({ name: 'Trellis2ModelLoader', type: 'ssui_3dmodel.Trellis2.Trellis2Model',
    port: 'input', component: Trellis2ModelLoader } as ComponentRegister);
registerComponent({ name: 'TrellisModelLoader', type: 'ssui_3dmodel.Trellis.TrellisModel',
    port: 'input', component: TrellisModelLoader } as ComponentRegister);

// Keep foreground masks in the focused image-to-3D examples.
registerComponentVariant({
    name: 'Pixal3DImageUploader', base: 'ImageUploader', component: Pixal3DImageUploader,
    matches: context => /(?:^|[\\/])workflow-(?:pixal3d|trellis2|trellis)\.py$/.test(context.script_path ?? ''),
});
