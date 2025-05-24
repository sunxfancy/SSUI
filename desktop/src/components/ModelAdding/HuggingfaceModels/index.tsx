import React, {useState} from 'react';
import { Button, InputGroup, Spinner, Tabs, Tab, NonIdealState, Tag, Icon, CompoundTag } from '@blueprintjs/core';
import axios from 'axios';
import HuggingfaceLogo from './logo_huggingface.svg'
import ModelLogo from './logo_model.svg'
import styles from './style.module.css'

export interface HuggingfaceModel {
    id: string;
    modelId: string;
    private: boolean;
    author: string;
    downloads: number;
    likes: number;
    tags: string[];
    pipeline_tag: string;
    lastModified: string;
    siblings?: Array<{
        rfilename: string;
        size?: number;
        lfs?: {
            sha256?: string;
        }
    }>;
}

interface HuggingfaceModelsProps {
    onModelSelect?: (model: HuggingfaceModel) => void;
}

const HuggingfaceModels: React.FC<HuggingfaceModelsProps> = ({ onModelSelect }) => {
    const [models, setModels] = useState<HuggingfaceModel[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [inputValue, setInputValue] = useState<string>('');
    const [selectedType, setSelectedType] = useState<string>('all');
    const [hasSearched, setHasSearched] = useState(false);

    const searchModels = async () => {
        if (!inputValue.trim()) return;

        try {
            setLoading(true);
            setError(null);
            setHasSearched(true);

            const response = await axios.get('https://huggingface.co/api/models', {
                params: {
                    search: inputValue,
                    limit: 50,
                    sort: 'downloads',
                    direction: -1,
                    full: 'full'
                }
            });

            setModels(response.data);
        } catch (err) {
            setError('搜索模型失败');
            console.error('搜索模型时出错:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleAddRepo = async () => {
        if (!inputValue.trim()) return;

        try {
            setLoading(true);
            setError(null);
            setHasSearched(true);

            // 获取单个仓库信息
            const response = await axios.get(`https://huggingface.co/api/models/${inputValue}`);

            // 如果成功获取，添加到模型列表的开头
            if (response.data) {
                setModels(prevModels => [response.data, ...prevModels]);
                setInputValue(''); // 清空输入
            }
        } catch (err) {
            setError('添加仓库失败，请确认仓库ID格式正确');
            console.error('添加仓库时出错:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setInputValue(event.target.value);
    };

    const handleSearchSubmit = (event: React.FormEvent) => {
        event.preventDefault();
        searchModels();
    };

    // 格式化下载数
    const formatNumber = (num: number) => {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    };

    // 根据pipeline_tag过滤模型
    const filteredModels = selectedType === 'all'
        ? models
        : models.filter(model => model.pipeline_tag === selectedType);

    // 获取所有可用的模型类型
    const modelTypes = ['all', ...new Set(models.map(model => model.pipeline_tag).filter(Boolean))];

    return (
        <div className={styles.huggingFace}>
            {/* 合并的搜索/添加仓库区域 */}
            <form className={styles.form} onSubmit={handleSearchSubmit}>
                <div className={styles.searchArea}>
                    <InputGroup
                        className={styles.searchInput}
                        placeholder="搜索模型或输入仓库ID..."
                        leftElement={<div className={styles.logo}><img src={HuggingfaceLogo} alt=""/></div>}
                        value={inputValue}
                        size="large"
                        onChange={handleInputChange}
                    />
                    <Button
                        type="submit"
                        intent="primary"
                        icon="search"
                        size="large"
                        disabled={!inputValue.trim() || loading}
                    >
                        搜索
                    </Button>
                    <Button
                        intent="success"
                        icon="cloud-download"
                        onClick={handleAddRepo}
                        size="large"
                        disabled={!inputValue.trim() || loading}
                    >
                        添加仓库
                    </Button>
                </div>
                <div className={styles.tip}>
                    * 搜索模型或输入仓库ID (例如: 'runwayml/stable-diffusion-v1-5')
                </div>
            </form>

            {/* 模型类型标签页 - 只在有模型时显示 */}
            {models.length > 0 && (
                <Tabs
                    selectedTabId={selectedType}
                    onChange={(newTabId) => setSelectedType(newTabId as string)}
                >
                    {modelTypes.map(type => (
                        <Tab
                            key={type}
                            id={type}
                            title={type === 'all' ? '全部' : type}
                        />
                    ))}
                </Tabs>
            )}

            {/* 模型列表 */}
            {loading ? (
                <div style={{ textAlign: 'center', padding: '40px' }}>
                    <Spinner />
                </div>
            ) : error ? (
                <NonIdealState
                    icon="error"
                    title="加载失败"
                    description={error}
                />
            ) : !hasSearched ? (
                <NonIdealState
                    icon="search"
                    title="搜索Huggingface模型"
                    description="输入关键词搜索模型或直接添加仓库ID"
                />
            ) : filteredModels.length === 0 ? (
                <NonIdealState
                    icon="search"
                    title="未找到模型"
                    description="请尝试其他搜索关键词或直接添加仓库ID"
                />
            ) : (
                <div className={styles.cardList} id="#huggingfaceCardList">
                    {filteredModels.map(model => (
                        <div className={styles.huggingFaceModelCard}>
                            <div className={styles.topArea}>
                                <div className={styles.name}>{model.id}</div>
                                {
                                    model.pipeline_tag &&
                                    <span className={styles.pipelineTag}>
                                        <img src={ModelLogo} />
                                        {model.pipeline_tag}
                                    </span>
                                }
                            </div>
                            <div className={styles.midArea}>
                                <div className={styles.tags}>
                                    <CompoundTag minimal intent="primary" size="medium" leftContent={<div className={styles.iconWp}><Icon icon="person" size={10}/></div>}>{model.author}</CompoundTag>
                                    {(model.tags || []).map((tag, index) => (
                                        <Tag key={index} minimal>{tag}</Tag>
                                    ))}
                                </div>
                            </div>

                            <div className={styles.bottomArea}>
                                <div className={styles.data}>
                                    <span title="下载次数">
                                        <Icon icon="download" size={14} color="rgb(93, 191, 93)" style={{ marginRight: '3px' }} />
                                        {formatNumber(model.downloads || 0)}
                                    </span>
                                    <span title="点赞数">
                                        <Icon icon="heart" size={14} color="rgb(255, 102, 102)" style={{ marginRight: '3px' }} />
                                        {formatNumber(model.likes || 0)}
                                    </span>
                                </div>
                                <Button
                                    text="下载"
                                    intent="primary"
                                    variant="outlined"
                                    icon="download"
                                    onClick={() => {
                                        if (onModelSelect) {
                                            onModelSelect(model);
                                        }
                                    }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default HuggingfaceModels;
