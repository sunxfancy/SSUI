import React, { useEffect, useRef, useState } from 'react';
import { Button, Icon, Tooltip, ProgressBar } from '@blueprintjs/core';
import styles from './style.module.css';
import { useTranslation } from 'react-i18next';
import TaskService from '../../../services/TaskService';
import { getApiBaseUrl } from '../../../services/apiBase';

interface PresetModelMember {
    name: string;
    source: string;
    type?: string;
    base?: string;
    description?: string;
}

interface PresetModel {
    id: string;
    name: string;
    type: string;
    base?: string;
    source: string;
    description: string;
    imageUrl?: string;
    size?: string;
    /** 模型组包含的成员（主模型 + 配套辅助模型） */
    models?: PresetModelMember[];
}

interface PresetModelsProps {
    onModelSelect?: (model: PresetModel) => void;
}

const fallbackPresets: PresetModel[] = [
    {
        id: '001-flux-preset',
        name: 'Flux Model Preset',
        type: 'Main',
        base: 'flux',
        source: 'InvokeAI/flux_schnell::transformer/bnb_nf4/flux1-schnell-bnb_nf4.safetensors',
        description: [
            'FLUX Schnell (Quantized)',
            'clip-vit-large-patch14',
            't5_bnb_int8_quantized_encoder',
            'Flux Vae'
        ].join(' · '),
        imageUrl: 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/f905bc28-9db6-4f83-85ae-93c94718881d/anim=false,width=450/NfX8MYg-_nTv_PpQBNJSr.jpeg',
        models: [
            { name: 'FLUX Schnell (Quantized)', source: 'InvokeAI/flux_schnell::transformer/bnb_nf4/flux1-schnell-bnb_nf4.safetensors', type: 'main', base: 'flux' },
            { name: 't5_bnb_int8_quantized_encoder', source: 'InvokeAI/t5-v1_1-xxl::bnb_llm_int8', type: 't5_encoder', base: 'any' },
            { name: 'clip-vit-large-patch14', source: 'InvokeAI/clip-vit-large-patch14', type: 'clip_vision', base: 'any' },
            { name: 'FLUX.1-schnell_ae', source: 'black-forest-labs/FLUX.1-schnell::ae.safetensors', type: 'vae', base: 'flux' }
        ]
    }
];

export const PresetModels: React.FC<PresetModelsProps> = ({ onModelSelect }) => {
    const { t } = useTranslation();
    const [presets, setPresets] = useState<PresetModel[]>(fallbackPresets);
    const [loading, setLoading] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [downloading, setDownloading] = useState<{ [id: string]: number }>({});
    const taskService = useRef(TaskService.getInstance());
    const groupTaskIds = useRef<{ [groupId: string]: string[] }>({});
    const memberProgress = useRef<{ [taskId: string]: number }>({});
    const memberDone = useRef<{ [taskId: string]: boolean }>({});

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
        // 通过任务队列的 task_update 推送更新整组下载进度（各成员进度的平均）
        const unsubscribe = taskService.current.subscribe((task) => {
            if (task.kind !== 'download') return;
            for (const [groupId, taskIds] of Object.entries(groupTaskIds.current)) {
                if (!taskIds.includes(task.id)) continue;
                memberProgress.current[task.id] = task.status === 'completed' ? 100 : task.progress;
                if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
                    memberDone.current[task.id] = true;
                }
                const values = taskIds.map(id => memberProgress.current[id] ?? 0);
                const progress = Math.round(values.reduce((sum, v) => sum + v, 0) / values.length);
                setDownloading(prev => ({ ...prev, [groupId]: progress }));

                if (taskIds.every(id => memberDone.current[id])) {
                    delete groupTaskIds.current[groupId];
                    setDownloading(prev => {
                        const next = { ...prev };
                        delete next[groupId];
                        return next;
                    });
                }
            }
        });
        return unsubscribe;
    }, []);

    const handleDownload = async (model: PresetModel) => {
        onModelSelect?.(model);
        const members = model.models && model.models.length > 0
            ? model.models
            : [{ name: model.name, source: model.source }];
        setDownloading(prev => ({ ...prev, [model.id]: 0 }));
        const taskIds: string[] = [];
        for (const member of members) {
            try {
                const isUrl = member.source.startsWith('http://') || member.source.startsWith('https://');
                const taskId = await taskService.current.createDownloadTask(
                    'preset',
                    `${model.name} · ${member.name}`,
                    isUrl ? member.source : undefined,
                    isUrl ? undefined : member.source
                );
                taskIds.push(taskId);
            } catch (error) {
                console.error(`预设模型成员下载失败 (${member.name}):`, error);
            }
        }
        groupTaskIds.current[model.id] = taskIds;
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
                    const memberNames = (model.models || []).map(m => m.name);
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
                                            {model.description && (
                                                <div className={styles.tooltipItem}>{model.description}</div>
                                            )}
                                            {memberNames.map((name, index) => (
                                                <div key={index} className={styles.tooltipItem}>{name}</div>
                                            ))}
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
