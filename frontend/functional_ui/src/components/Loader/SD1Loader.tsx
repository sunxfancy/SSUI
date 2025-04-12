import { IComponent } from '../IComponent';
import React, { Component } from 'react';

interface SD1Model {
    name: string;
    path: string;
    description?: string;
    tags?: string[];
}

class SD1ModelLoader extends Component {
    state = {
        filePath: '',
        models: [] as SD1Model[],
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
                model.base_model.includes('sd-1')
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
        return { 'function': 'ssui_image.SD1.SD1Model.load', 'params': { 'path': this.state.filePath } };
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
                    <div>未找到SD1兼容模型</div>
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

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'SD1ModelLoader', 'type': 'ssui_image.SD1.SD1Model', 'port': 'input', 'component': SD1ModelLoader, } as ComponentRegister,
].forEach(registerComponent);