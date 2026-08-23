import React, { Component } from 'react';
import { registerComponent, ComponentRegister } from '../ComponentsManager';

interface ControlNetModel {
    name: string;
    path: string;
}

interface ControlNetLoaderProps {
    script_path: string;
}

interface ControlNetLoaderState {
    filePath: string;
    imagePath: string;
    weight: number;
    vaePath: string;
    models: ControlNetModel[];
    vaeModels: ControlNetModel[];
    loading: boolean;
    error: string | null;
}

/**
 * 生成 ControlNet 模型加载器组件。
 *
 * 组件的 onExecute() 返回可供 ss_executor 执行的函数调用描述：
 *   { 'function': 'ssui_image.SD1.SD1ControlNet.load', 'params': { path, image_path, weight } }
 *
 * @param baseType   模型基底类型（sd-1 / sdxl / flux），用于过滤已安装模型
 * @param withVae    FLUX InstantX ControlNet 需要额外的 VAE（用于编码控制图）
 * @param functionName 后端 ControlNet 节点的静态 load 方法
 */
function getControlNetLoader(
    baseType: 'sd-1' | 'sdxl' | 'flux',
    withVae: boolean,
    functionName: string,
) {
    return class ControlNetModelLoader extends Component<
        ControlNetLoaderProps,
        ControlNetLoaderState
    > {
        state: ControlNetLoaderState = {
            filePath: '',
            imagePath: '',
            weight: 1.0,
            vaePath: '',
            models: [],
            vaeModels: [],
            loading: false,
            error: null,
        };

        componentDidMount() {
            this.fetchModels();
        }

        async fetchModels() {
            this.setState({ loading: true, error: null });
            try {
                const response = await fetch('/api/available_models');
                if (!response.ok) {
                    throw new Error('获取模型列表失败');
                }
                const allModels = await response.json();

                // 已安装的 ControlNet 模型带 "controlnet" 标签（见 server/model_service.py）
                const models = allModels.filter(
                    (model: any) =>
                        String(model.base_model).includes(baseType) &&
                        (model.tags ?? []).includes('controlnet'),
                );
                const vaeModels = withVae
                    ? allModels.filter(
                          (model: any) =>
                              String(model.base_model).includes(baseType) &&
                              (model.tags ?? []).includes('vae'),
                      )
                    : [];

                this.setState({ models, vaeModels, loading: false });
            } catch (error) {
                this.setState({
                    loading: false,
                    error:
                        error instanceof Error
                            ? error.message
                            : '获取模型列表失败',
                });
            }
        }

        handleImageChange = async (
            event: React.ChangeEvent<HTMLInputElement>,
        ) => {
            const file = event.target.files?.[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);
            try {
                const response = await fetch(
                    `/files/upload?script_path=${this.props.script_path}`,
                    { method: 'POST', body: formData },
                );
                const data = await response.json();
                if (data.success) {
                    this.setState({ imagePath: data.path });
                }
            } catch (error) {
                console.error('上传控制图失败:', error);
            }
        };

        onExecute() {
            const params: any = {
                path: this.state.filePath,
                image_path: this.state.imagePath,
                weight: this.state.weight,
            };
            if (withVae) {
                params.vae_path = this.state.vaePath;
            }
            return { 'function': functionName, 'params': params };
        }

        renderModelSelect(
            models: ControlNetModel[],
            value: string,
            placeholder: string,
            onChange: (event: React.ChangeEvent<HTMLSelectElement>) => void,
        ) {
            return (
                <div style={{ marginBottom: '8px' }}>
                    <select
                        value={value}
                        onChange={onChange}
                        style={{ width: '100%' }}
                    >
                        <option value="">{placeholder}</option>
                        {models.map((model, index) => (
                            <option key={index} value={model.path}>
                                {model.name}
                            </option>
                        ))}
                    </select>
                </div>
            );
        }

        render() {
            const { models, vaeModels, loading, error } = this.state;
            if (loading) {
                return <div>加载中...</div>;
            }
            if (error) {
                return <div style={{ color: 'red' }}>{error}</div>;
            }

            return (
                <div>
                    {this.renderModelSelect(
                        models,
                        this.state.filePath,
                        '选择 ControlNet 模型...',
                        (event) =>
                            this.setState({ filePath: event.target.value }),
                    )}
                    {withVae &&
                        this.renderModelSelect(
                            vaeModels,
                            this.state.vaePath,
                            '选择 ControlNet VAE（可选）...',
                            (event) =>
                                this.setState({ vaePath: event.target.value }),
                        )}
                    <div style={{ marginBottom: '8px' }}>
                        <input
                            type="file"
                            accept="image/*"
                            onChange={this.handleImageChange}
                            style={{ width: '100%' }}
                        />
                    </div>
                    {this.state.imagePath && (
                        <div style={{ marginBottom: '8px' }}>
                            <img
                                src={'/file?path=' + this.state.imagePath}
                                alt="control image preview"
                                style={{ maxWidth: '100%', height: 'auto' }}
                            />
                        </div>
                    )}
                    <div style={{ marginBottom: '8px' }}>
                        <label>
                            权重: {this.state.weight.toFixed(2)}
                            <input
                                type="range"
                                min="0"
                                max="2"
                                step="0.05"
                                value={this.state.weight}
                                onChange={(event) =>
                                    this.setState({
                                        weight: parseFloat(event.target.value),
                                    })
                                }
                                style={{ width: '100%' }}
                            />
                        </label>
                    </div>
                </div>
            );
        }
    };
}

// Register into the component manager
[
    {
        'name': 'SD1ControlNetLoader',
        'type': 'ssui_image.SD1.SD1ControlNet',
        'port': 'input',
        'component': getControlNetLoader(
            'sd-1',
            false,
            'ssui_image.SD1.SD1ControlNet.load',
        ),
    } as ComponentRegister,
    {
        'name': 'SDXLControlNetLoader',
        'type': 'ssui_image.SDXL.SDXLControlNet',
        'port': 'input',
        'component': getControlNetLoader(
            'sdxl',
            false,
            'ssui_image.SDXL.SDXLControlNet.load',
        ),
    } as ComponentRegister,
    {
        'name': 'FluxControlNetLoader',
        'type': 'ssui_image.Flux.FluxControlNet',
        'port': 'input',
        'component': getControlNetLoader(
            'flux',
            true,
            'ssui_image.Flux.FluxControlNet.load',
        ),
    } as ComponentRegister,
].forEach(registerComponent);
