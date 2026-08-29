import React from 'react';
import { Callout, Checkbox, FileInput, FormGroup, InputGroup, NumericInput, Spinner, Tag } from '@blueprintjs/core';
import { IComponent } from '../IComponent';
import { ComponentRegister, registerComponent } from '../ComponentsManager';
import './WorkflowLoaders.css';

type Descriptor = { function: string; params: Record<string, unknown> };

type UploadLoaderProps = {
    script_path?: string;
    functionName: string;
    accept: string;
    label: string;
    executable?: string;
};

class UploadLoader extends IComponent<UploadLoaderProps, { path: string; executable: string; uploading: boolean; error?: string }> {
    state = { path: '', executable: this.props.executable ?? '', uploading: false, error: undefined as string | undefined };

    private upload = async (event: React.FormEvent<HTMLInputElement>) => {
        const file = event.currentTarget.files?.[0];
        if (!file || !this.props.script_path) return;
        this.setState({ uploading: true, error: undefined });
        try {
            const body = new FormData();
            body.append('file', file);
            const response = await fetch(`/files/upload?script_path=${encodeURIComponent(this.props.script_path)}`, { method: 'POST', body });
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || `上传失败（${response.status}）`);
            this.setState({ path: result.path, uploading: false });
        } catch (error) {
            this.setState({ uploading: false, error: error instanceof Error ? error.message : '上传失败' });
        }
    };

    override onExecute(): Descriptor {
        const params: Record<string, unknown> = { path: this.state.path };
        if (this.props.functionName.includes('PixelArt.')) {
            params.source_path = this.state.path;
            delete params.path;
            params.executable = this.state.executable;
        }
        return { function: this.props.functionName, params };
    }

    override render() {
        return <div className="workflow-loader">
            <FormGroup label={this.props.label} helperText={this.state.path || `支持 ${this.props.accept}`}>
                <FileInput fill text={this.state.path ? this.state.path.split(/[\\/]/).pop() : '选择文件'}
                    inputProps={{ accept: this.props.accept }} onInputChange={this.upload} disabled={this.state.uploading} />
            </FormGroup>
            {this.props.executable !== undefined && <FormGroup label="命令行工具" helperText="可填写命令名或完整路径">
                <InputGroup fill value={this.state.executable} onChange={event => this.setState({ executable: event.target.value })} />
            </FormGroup>}
            {this.state.uploading && <div className="workflow-loader-status"><Spinner size={16} /> 正在上传…</div>}
            {this.state.error && <Callout compact intent="danger">{this.state.error}</Callout>}
        </div>;
    }
}

type QwenProps = { edit?: boolean };
class QwenModelLoader extends IComponent<QwenProps, { modelId: string; lowVram: boolean; vramLimit: number }> {
    state = {
        modelId: this.props.edit ? 'Qwen/Qwen-Image-Edit-2509' : 'Qwen/Qwen-Image',
        lowVram: true,
        vramLimit: 0,
    };

    override onExecute(): Descriptor {
        return {
            function: this.props.edit ? 'ssui_video.QwenImage.QwenImageEditModel.load' : 'ssui_video.QwenImage.QwenImageModel.load',
            params: { model_id: this.state.modelId, low_vram: this.state.lowVram, vram_limit_gib: this.state.vramLimit },
        };
    }

    override render() {
        return <div className="workflow-loader">
            <div className="workflow-loader-heading"><Tag minimal icon="cube">Qwen Image</Tag><span>{this.props.edit ? '图像编辑' : '文生图'}</span></div>
            <FormGroup label="模型 ID"><InputGroup fill value={this.state.modelId} onChange={event => this.setState({ modelId: event.target.value })} /></FormGroup>
            <div className="workflow-loader-row">
                <Checkbox checked={this.state.lowVram} label="低显存模式" onChange={event => this.setState({ lowVram: event.currentTarget.checked })} />
                <FormGroup label="显存上限 GiB" helperText="0 表示自动">
                    <NumericInput min={0} value={this.state.vramLimit} onValueChange={value => this.setState({ vramLimit: value })} />
                </FormGroup>
            </div>
        </div>;
    }
}

class FluxLoraLoader extends IComponent<{}, { path: string; weight: number }> {
    state = { path: '', weight: 0.75 };
    override onExecute(): Descriptor {
        return { function: 'ssui_image.Flux.FluxLora.load_one', params: { path: this.state.path, weight: this.state.weight } };
    }
    override render() {
        return <div className="workflow-loader">
            <FormGroup label="Flux LoRA 路径" helperText="选择已安装 LoRA 的 safetensors 文件">
                <InputGroup fill value={this.state.path} placeholder="models/lora/example.safetensors" onChange={event => this.setState({ path: event.target.value })} />
            </FormGroup>
            <FormGroup label="权重"><NumericInput fill min={-4} max={4} stepSize={0.05} value={this.state.weight}
                onValueChange={value => this.setState({ weight: value })} /></FormGroup>
        </div>;
    }
}

function uploadComponent(defaults: Omit<UploadLoaderProps, 'script_path'>) {
    return React.forwardRef<UploadLoader, { script_path?: string }>((props, ref) =>
        <UploadLoader {...props} {...defaults} ref={ref} />
    );
}

const QwenImageEditModelLoader = React.forwardRef<QwenModelLoader, object>((props, ref) =>
    <QwenModelLoader {...props} edit ref={ref} />
);

[
    { name: 'AgentPaintAssetLoader', type: 'ssui_image.PixelArt.AgentPaintAsset', port: 'input',
        component: uploadComponent({ functionName: 'ssui_image.PixelArt.AgentPaintAsset.load', accept: '.apx,.apxa', label: 'AgentPaint 源文件', executable: 'agentpaint' }) },
    { name: 'PixelSrcAssetLoader', type: 'ssui_image.PixelArt.PixelSrcAsset', port: 'input',
        component: uploadComponent({ functionName: 'ssui_image.PixelArt.PixelSrcAsset.load', accept: '.pxl', label: 'pixelsrc 源文件', executable: 'pxl' }) },
    { name: 'MeshLoader', type: 'ssui.base.Mesh', port: 'input',
        component: uploadComponent({ functionName: 'ssui.base.Mesh.load', accept: '.glb,.gltf,.obj,.fbx', label: '3D 模型文件' }) },
    { name: 'QwenImageModelLoader', type: 'ssui_video.QwenImage.QwenImageModel', port: 'input', component: QwenModelLoader },
    { name: 'QwenImageEditModelLoader', type: 'ssui_video.QwenImage.QwenImageEditModel', port: 'input', component: QwenImageEditModelLoader },
    { name: 'FluxLoraLoader', type: 'ssui_image.Flux.FluxLora', port: 'input', component: FluxLoraLoader },
].forEach(item => registerComponent(item as ComponentRegister));

export { FluxLoraLoader, QwenModelLoader, UploadLoader };
