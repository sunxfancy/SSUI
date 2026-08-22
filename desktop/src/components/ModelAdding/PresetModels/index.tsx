import React, { useEffect, useRef, useState } from 'react';
import { Button, Icon, Tooltip, ProgressBar } from '@blueprintjs/core';
import styles from './style.module.css';
import { useTranslation } from 'react-i18next';
import TaskService from '../../../services/TaskService';
import { getApiBaseUrl } from '../../../services/apiBase';

interface PresetModel {
    id: string;
    name: string;
    type: string;
    base?: string;
    source: string;
    description: string;
    imageUrl?: string;
    size?: string;
}

interface PresetModelsProps {
    onModelSelect?: (model: PresetModel) => void;
}

const fallbackPresets: PresetModel[] = [
    {
        id: '001-flux-preset',
        name: 'Flux Model Preset',
        type: 'Flux',
        base: 'flux',
        source: 'InvokeAI/flux_schnell_quantized',
        description: [
            'FLUX Schnell (Quantized)',
            'clip-vit-large-patch14',
            't5_bnb_int8_quantized_encoder',
            'Flux Vae'
        ].join(' / '),
        imageUrl: 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/f905bc28-9db6-4f83-85ae-93c94718881d/anim=false,width=450/NfX8MYg-_nTv_PpQBNJSr.jpeg'
    }
];

export const PresetModels: React.FC<PresetModelsProps> = ({ onModelSelect }) => {
    const { t } = useTranslation();
    const [presets, setPresets] = useState<PresetModel[]>(fallbackPresets);
    const [loading, setLoading] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [downloading, setDownloading] = useState<{ [id: string]: number }>({});
    const taskService = useRef(TaskService.getInstance());
    const taskIds = useRef<{ [modelId: string]: string }>({});

    useEffect(() => {
        const fetchPresets = async () => {
            try {
                setLoading(true);
                const response = await fetch(`${getApiBaseUrl()}/api/preset_models`);
                if (!response.ok) {
                    throw new Error(`Failed to fetch preset models: ${response.status}`);
                }
                const data = await response.json();
                if (data.items && data.items.length > 0) {
                    setPresets(data.items);
                }
                setLoadError(null);
            } catch (error) {
                console.error('获取预设模型失败:', error);
                setLoadError(error instanceof Error ? error.message : 'Failed to fetch preset models');
            } finally {
                setLoading(false);
            }
        };
        fetchPresets();
    }, []);

    useEffect(() => {
        // 通过任务队列的 task_update 推送更新下载进度
        const unsubscribe = taskService.current.subscribe((task) => {
            if (task.kind !== 'download') return;
            for (const [modelId, taskId] of Object.entries(taskIds.current)) {
                if (taskId === task.id) {
                    if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
                        delete taskIds.current[modelId];
                        setDownloading(prev => {
                            const next = { ...prev };
                            delete next[modelId];
                            return next;
                        });
                    } else {
                        setDownloading(prev => ({ ...prev, [modelId]: task.progress }));
                    }
                }
            }
        });
        return unsubscribe;
    }, []);

    const handleDownload = async (model: PresetModel) => {
        onModelSelect?.(model);
        setDownloading(prev => ({ ...prev, [model.id]: 0 }));
        try {
            const isUrl = model.source.startsWith('http://') || model.source.startsWith('https://');
            const taskId = await taskService.current.createDownloadTask(
                'preset',
                model.name,
                isUrl ? model.source : undefined,
                isUrl ? undefined : model.source
            );
            taskIds.current[model.id] = taskId;
        } catch (error) {
            console.error('预设模型下载失败:', error);
        }
    };

    if (loading && presets.length === 0) {
        return <div style={{ textAlign: 'center', padding: '40px' }}>{t('model.loading')}</div>;
    }

    if (loadError && presets.length === 0) {
        return <div style={{ color: 'red', textAlign: 'center', padding: '20px' }}>{loadError}</div>;
    }

    return (
        <div className={styles.presetModel}>
            <div className={styles.cardList}>
                {presets.map(model => {
                    const progress = downloading[model.id];
                    const isDownloading = progress !== undefined;
                    return (
                        <div className={styles.card} key={model.id}>
                            <div className={styles.type}>{model.base || model.type}</div>
                            <div className={styles.image}>
                                {model.imageUrl ? (
                                    <img src={model.imageUrl} alt={model.name} />
                                ) : (
                                    <div className={styles.placeholder}>{model.name}</div>
                                )}
                            </div>
                            <div className={styles.info}>
                                <div className={styles.name}>{model.name}</div>
                                <div className={styles.actions}>
                                    <Button
                                        text={isDownloading ? t('model.actions.downloading', { progress }) : t('model.actions.download')}
                                        intent="primary"
                                        loading={isDownloading}
                                        onClick={() => handleDownload(model)}
                                    />
                                </div>
                            </div>
                            {isDownloading && (
                                <div className={styles.progressWrap}>
                                    <ProgressBar
                                        value={progress / 100}
                                        intent="primary"
                                        animate={progress < 100}
                                    />
                                </div>
                            )}
                            <div className={styles.infoButton}>
                                <Tooltip
                                    content={
                                        <div className={styles.tooltip}>
                                            <div className={styles.tooltipItem}>{model.description}</div>
                                            {model.size && model.size !== model.description && (
                                                <div className={styles.tooltipItem}>{model.size}</div>
                                            )}
                                        </div>
                                    }
                                    position="right"
                                >
                                    <Icon icon="info-sign" />
                                </Tooltip>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default PresetModels;
