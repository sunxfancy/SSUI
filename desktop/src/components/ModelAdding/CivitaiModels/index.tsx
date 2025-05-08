import React, { useEffect, useState } from 'react';
import {Spinner, Tabs, Tab, Icon, Button} from '@blueprintjs/core';
import axios from 'axios';
import { CivitaiModel } from '../../../types/civitai';
import styles from './style.module.css';
import {produce} from "immer";

interface CivitaiModelsProps {
    onModelSelect?: (model: CivitaiModel) => void;
}

export const CivitaiModels: React.FC<CivitaiModelsProps> = () => {
    const [models, setModels] = useState<CivitaiModel[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedType, setSelectedType] = useState<string>('all');
    const [ page, setPage ] = useState(1)
    const [ nextCursor, setNextCursor ] = useState('')

    useEffect(() => {
        fetchModels();
    }, []);

    const fetchModels = async (toPage = 1) => {
        if (toPage) {
            setPage(toPage)
        }
        try {
            setLoading(true);
            const response = await axios.get('https://civitai.com/api/v1/models', {
                params: {
                    page: 1,
                    limit: 100,
                    sort: 'Newest',
                }
            });
            setModels(response.data.items);
            setError(null);
        } catch (err) {
            setError('获取模型列表失败');
            console.error('Error fetching models:', err);
        } finally {
            setLoading(false);
        }
    };

    const filteredModels = selectedType === 'all'
        ? models
        : models.filter(model => model.type === selectedType);

    const modelTypes = ['all', ...new Set(models.map(model => model.type))];

    const handleScroll = (e) => {
        // const { scrollTop, scrollHeight, clientHeight } = e.target
        // if (scrollTop + clientHeight >= scrollHeight - 200 && !loading) {
        //     fetchModels(page + 1)
        // }
    }

    const changeTab = (newTabId: string) => {
        setSelectedType(newTabId);
    }

    return (
        <div className={styles.civitaiModel}>
            <Tabs selectedTabId={selectedType} onChange={(newTabId) => changeTab(newTabId as string)}>
                {modelTypes.map(type => (
                    <Tab key={type} id={type} title={type === 'all' ? '全部' : type} />
                ))}
            </Tabs>

            <div className={styles.cardList} onScroll={handleScroll}>
                {filteredModels.map(model => (
                    <div className={styles.civitaiModelCard} key={model.id}>
                        <div className={styles.cardType}>{model.type}</div>
                        <div className={styles.previewImage}>
                            {model.modelVersions[0]?.images[0] && (
                                <img src={model.modelVersions[0].images[0].url} alt={model.name}/>
                            )}
                        </div>

                        <div className={styles.textPart}>
                            {/* 模型标题和描述 */}
                            <div className={styles.name}>{model.name}</div>
                            <div className={styles.btnWp}>
                                <div className={styles.data}>
                                    <span><Icon icon="download" /> {model.stats.downloadCount}</span>
                                    <span><Icon icon="heart" /> {model.stats.thumbsUpCount}</span>
                                    <span><Icon icon="comment" /> {model.stats.commentCount}</span>
                                </div>
                                <Button
                                    text="下载"
                                    intent="primary"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        // 这里可以添加下载逻辑
                                        console.log('下载模型:', model.name);
                                    }}
                                />
                            </div>
                        </div>
                    </div>
                ))}
                {loading ? (
                    <div style={{ textAlign: 'center', padding: '20px' }}>
                        <Spinner />
                    </div>
                ) : error ? (
                    <div style={{ color: 'red', textAlign: 'center', padding: '20px' }}>
                        {error}
                    </div>
                ) : null}
            </div>


        </div>
    );
};

export default CivitaiModels;
