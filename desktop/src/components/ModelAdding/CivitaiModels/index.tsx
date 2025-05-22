import React, { useEffect, useState } from 'react';
import {Spinner, Tabs, Tab, Icon, Button} from '@blueprintjs/core';
import axios from 'axios';
import { CivitaiModel } from '../../../types/civitai';
import styles from './style.module.css';
import { TauriDownloaderProvider } from '../../../providers/TauriDownloaderProvider';
import { DownloadTask } from '../../../providers/IDownloaderProvider';

interface CivitaiModelsProps {
    onModelSelect?: (model: CivitaiModel) => void;
}

export const CivitaiModels: React.FC<CivitaiModelsProps> = () => {
    const [models, setModels] = useState<CivitaiModel[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedType, setSelectedType] = useState<string>('all');
    const [downloadTasks, setDownloadTasks] = useState<DownloadTask[]>([]);
    const downloader = new TauriDownloaderProvider();

    useEffect(() => {
        fetchModels();
        loadDownloadTasks();
    }, []);

    const loadDownloadTasks = async () => {
        const tasks = await downloader.getDownloadTasks();
        setDownloadTasks(tasks);
    };

    const fetchModels = async () => {
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

    const changeTab = (newTabId: string) => {
        setSelectedType(newTabId);
    }

    const handleDownload = async (model: CivitaiModel) => {
        const task = await downloader.addDownloadTask(model);
        setDownloadTasks(prev => [...prev, task]);
    };

    const getDownloadButtonText = (model: CivitaiModel) => {
        const task = downloadTasks.find(t => t.model.id === model.id);
        if (!task) return '下载';
        
        switch (task.status) {
            case 'downloading':
                return `下载中 ${Math.round(task.progress)}%`;
            case 'completed':
                return '已完成';
            case 'failed':
                return '失败';
            default:
                return '等待中';
        }
    };

    const isDownloading = (model: CivitaiModel) => {
        const task = downloadTasks.find(t => t.model.id === model.id);
        return task?.status === 'downloading' || task?.status === 'pending';
    };

    return (
        <div className={styles.civitaiModel}>
            <Tabs selectedTabId={selectedType} onChange={(newTabId) => changeTab(newTabId as string)}>
                {modelTypes.map(type => (
                    <Tab key={type} id={type} title={type === 'all' ? '全部' : type} />
                ))}
            </Tabs>

            <div className={styles.cardList}>
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
                                    text={getDownloadButtonText(model)}
                                    intent="primary"
                                    disabled={isDownloading(model)}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDownload(model);
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
