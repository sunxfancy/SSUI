import { IComponent } from '../IComponent';
import React, { Component } from 'react';

interface SDModel {
    name: string;
    path: string;
    description?: string;
    tags?: string[];
}
function getModelLoader(type: 'sd-1' | 'sdxl') {
    return class SDModelLoader extends Component {
        state = {
            filePath: '',
            models: [] as SDModel[],
            loading: false,
            error: null as string | null
        };

        componentDidMount() {
            this.fetchModels();
        }

        async fetchModels() {
            this.setState({ loading: true, error: null });
            try {

                // 获取所有可用模型
                const modelsResponse = await fetch('/api/available_models');
                if (!modelsResponse.ok) {
                    throw new Error('获取模型列表失败');
                }
                const allModels = await modelsResponse.json();

                // 筛选出SD1可用的模型（标签中包含sd1的模型）
                const sd1Models = allModels.filter((model: any) =>
                    model.base_model.includes(`${type}`)
                );

                this.setState({
                    models: sd1Models,
                    loading: false
                });
            } catch (error) {
                console.error('获取模型列表失败:', error);
                this.setState({
                    error: error instanceof Error ? error.message : '获取模型列表失败',
                    loading: false
                });
            }
        }

        onExecute() {
            let functionName = '';
            if (type === 'sd-1') {
                functionName = 'ssui_image.SD1.SD1Model.load';
            } else if (type === 'sdxl') {
                functionName = 'ssui_image.SDXL.SDXLModel.load';
            }
            return { 'function': functionName, 'params': { 'path': this.state.filePath } };
        }

        render() {
            const { models, loading, error } = this.state;

            return (
                <div>
                    {loading ? (
                        <div>加载中...</div>
                    ) : error ? (
                        <div style={{ color: 'red' }}>{error}</div>
                    ) : models.length > 0 ? (
                        <div>
                            <select
                                onChange={this.handleModelSelect}
                                style={{ width: '100%', marginBottom: '10px' }}
                            >
                                <option value="">选择模型...</option>
                                {models.map((model, index) => (
                                    <option key={index} value={model.path}>
                                        {model.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                    ) : (
                        <div>未找到{type}兼容模型</div>
                    )}
                </div>
            );
        }

        handleModelSelect = (event: React.ChangeEvent<HTMLSelectElement>) => {
            const selectedPath = event.target.value;
            if (selectedPath) {
                this.setState({ filePath: selectedPath });
            }
        }
    }
}


class FluxModelLoader extends Component {
    state = {
        modelPath: '',
        t5EncoderPath: '',
        clipPath: '',
        vaePath: '',
        models: [] as SDModel[],
        t5EncoderModels: [] as SDModel[],
        clipModels: [] as SDModel[],
        vaeModels: [] as SDModel[],
        loading: false,
        error: null as string | null
    };

    componentDidMount() {
        this.fetchModels();
    }

    async fetchModels() {
        // 获取所有可用模型
        const modelsResponse = await fetch('/api/available_models');
        if (!modelsResponse.ok) {
            throw new Error('获取模型列表失败');
        }
        const allModels = await modelsResponse.json();

        // 筛选出SD可用的模型（标签中包含sd1的模型）
        const sdModels = allModels.filter((model: any) =>
            model.base_model.includes(`flux`) && !model.tags.includes(`vae`)
        );
        const t5EncoderModels = allModels.filter((model: any) =>
            model.base_model.includes(`any`) && model.tags.includes(`t5`)
        );
        const clipModels = allModels.filter((model: any) =>
            model.base_model.includes(`any`) && !model.tags.includes(`t5`)
        );
        const vaeModels = allModels.filter((model: any) =>
            model.base_model.includes(`flux`) && model.tags.includes(`vae`)
        );

        this.setState({
            models: sdModels,
            t5EncoderModels: t5EncoderModels,
            clipModels: clipModels,
            vaeModels: vaeModels,
            loading: false
        });
    }

    onExecute() {
        return { 'function': 'ssui_image.Flux.FluxModel.load', 'params': { 'model_path': this.state.modelPath, 't5_encoder_path': this.state.t5EncoderPath, 'clip_path': this.state.clipPath, 'vae_path': this.state.vaePath } };
    }

    renderModelSelect(models: SDModel[], model_name: string, onChange: (event: React.ChangeEvent<HTMLSelectElement>) => void) {
        return (
            <select
                onChange={onChange}
                style={{ width: '100%', marginBottom: '10px' }}
            >
                <option value="">选择{model_name}模型...</option>
                {models.map((model, index) => (
                    <option key={index} value={model.path}>
                        {model.name}
                    </option>
                ))}
            </select>
        );
    }
    render() {
        const { models, t5EncoderModels, clipModels, vaeModels, loading, error } = this.state;

        return (
            <div>
                {loading ? (
                    <div>加载中...</div>
                ) : error ? (
                    <div style={{ color: 'red' }}>{error}</div>
                ) : (
                    <div>
                        {this.renderModelSelect(models, 'flux', this.handleModelSelect('modelPath'))}
                        {this.renderModelSelect(t5EncoderModels, 't5_encoder', this.handleModelSelect('t5EncoderPath'))}
                        {this.renderModelSelect(clipModels, 'clip', this.handleModelSelect('clipPath'))}
                        {this.renderModelSelect(vaeModels, 'vae', this.handleModelSelect('vaePath'))}
                    </div>
                )}
            </div>
        );
    }

    handleModelSelect = (model_name: string) =>
        (event: React.ChangeEvent<HTMLSelectElement>) => {
            const selectedPath = event.target.value;
            if (selectedPath) {
                this.setState({ [model_name]: selectedPath });
            }
        }

}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'SD1ModelLoader', 'type': 'ssui_image.SD1.SD1Model', 'port': 'input', 'component': getModelLoader("sd-1"), } as ComponentRegister,
    { 'name': 'SDXLModelLoader', 'type': 'ssui_image.SDXL.SDXLModel', 'port': 'input', 'component': getModelLoader("sdxl"), } as ComponentRegister,
    { 'name': 'FluxModelLoader', 'type': 'ssui_image.Flux.FluxModel', 'port': 'input', 'component': FluxModelLoader, } as ComponentRegister,
].forEach(registerComponent);