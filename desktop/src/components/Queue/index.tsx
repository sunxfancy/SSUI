import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, Elevation, Button, Tag, Spinner, Icon, Dialog, Intent, NonIdealState } from '@blueprintjs/core';
import ExecutorService from '../../services/Executor';
import ServerService from '../../services/Server';
import TaskService, { QueueTask } from '../../services/TaskService';
import { CommandInfo } from '../../providers/IInstallerProvider';
import { useTranslation } from 'react-i18next';

interface QueueProps {
    items?: QueueTask[];
    onRemoveItem?: (id: string) => void;
    onPauseItem?: (id: string) => void;
    onResumeItem?: (id: string) => void;
}

const Queue: React.FC<QueueProps> = ({ items: initialItems }) => {
    const { t } = useTranslation();
    const [items, setItems] = useState<QueueTask[]>(initialItems ?? []);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [executorStatus, setExecutorStatus] = useState<CommandInfo | null>(null);
    const [serverStatus, setServerStatus] = useState<CommandInfo | null>(null);
    const [isRestartDialogOpen, setIsRestartDialogOpen] = useState(false);
    const [restartType, setRestartType] = useState<'server' | 'executor' | null>(null);
    const [isRestarting, setIsRestarting] = useState(false);
    const taskService = useRef(TaskService.getInstance());

    const loadTasks = useCallback(async () => {
        try {
            const tasks = await taskService.current.fetchTasks();
            setItems(tasks);
            setError(null);
        } catch (err) {
            console.error('获取任务列表失败:', err);
            setError(err instanceof Error ? err.message : '获取任务列表失败');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadTasks();

        // websocket 实时更新
        const unsubscribe = taskService.current.subscribe((updatedTask) => {
            setItems(prev => {
                const exists = prev.some(item => item.id === updatedTask.id);
                if (exists) {
                    return prev.map(item => item.id === updatedTask.id ? updatedTask : item);
                }
                return [updatedTask, ...prev];
            });
        });

        // 轮询兜底（生图任务状态由调度器维护）
        const pollId = setInterval(loadTasks, 5000);

        const fetchStatus = async () => {
            try {
                const executorResult = await ExecutorService.getInstance().getExecutorStatus();
                setExecutorStatus(executorResult);
                const serverResult = await ServerService.getInstance().getServerStatus();
                setServerStatus(serverResult);
            } catch (err) {
                console.error('获取服务状态时出错:', err);
            }
        };
        fetchStatus();
        const statusId = setInterval(fetchStatus, 30000);

        return () => {
            unsubscribe();
            clearInterval(pollId);
            clearInterval(statusId);
        };
    }, [loadTasks]);

    const handleRestartService = async () => {
        if (!restartType) return;
        setIsRestarting(true);
        try {
            if (restartType === 'server') {
                const newStatus = await ServerService.getInstance().restartServer();
                setServerStatus(newStatus);
            } else {
                const newStatus = await ExecutorService.getInstance().restartExecutor();
                setExecutorStatus(newStatus);
            }
        } catch (error) {
            console.error(`重启${restartType === 'server' ? '服务器' : '执行器'}时出错:`, error);
        } finally {
            setIsRestarting(false);
            setIsRestartDialogOpen(false);
        }
    };

    const getServiceStatusIcon = (status: CommandInfo | null, type: 'server' | 'executor') => {
        if (!status) return <Icon icon="circle" intent="none" />;
        const isRunning = status.message.includes('运行中') || status.message.includes('启动成功');
        const handleRestartClick = () => {
            setRestartType(type);
            setIsRestartDialogOpen(true);
        };
        if (isRunning) {
            return <Icon icon="circle" intent="success" onClick={handleRestartClick} style={{ cursor: 'pointer' }} />;
        } else if (status.message.includes('未在运行中')) {
            return <Icon icon="circle" intent="none" />;
        } else {
            return <Icon icon="circle" intent="danger" />;
        }
    };

    const getStatusColor = (status: QueueTask['status']) => {
        switch (status) {
            case 'waiting': return 'blue';
            case 'processing': return 'orange';
            case 'completed': return 'green';
            case 'failed': return 'red';
            case 'cancelled': return 'gray';
            default: return 'gray';
        }
    };

    const getStatusText = (status: QueueTask['status']) => {
        return t(`queue.status.${status}`);
    };

    const handleRemove = async (id: string) => {
        const success = await taskService.current.removeTask(id);
        if (success) {
            setItems(prev => prev.filter(item => item.id !== id));
        }
    };

    const handleCancel = async (id: string) => {
        const success = await taskService.current.cancelTask(id);
        if (success) {
            setItems(prev => prev.map(item => item.id === id ? { ...item, status: 'cancelled', progress: 0 } : item));
        }
    };

    const handleClearCompleted = async () => {
        await taskService.current.clearCompleted();
        await loadTasks();
    };

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '10px', borderBottom: '1px solid #e1e8ed', display: 'flex', justifyContent: 'space-between' }}>
                <div>
                    <h2 style={{ margin: 0 }}>{t('queue.title')}</h2>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div>{t('queue.totalTasks', { count: items.length })}</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <span>{t('queue.executor')}:</span>
                            {getServiceStatusIcon(executorStatus, 'executor')}
                            <span style={{ marginLeft: '10px' }}>{t('queue.server')}:</span>
                            {getServiceStatusIcon(serverStatus, 'server')}
                        </div>
                    </div>
                </div>
            </div>

            <div style={{ display: 'flex', gap: '8px', padding: '8px 10px', borderBottom: '1px solid #e1e8ed' }}>
                <Button
                    text={t('queue.clearCompleted')}
                    icon="trash"
                    variant="solid"
                    onClick={handleClearCompleted}
                    disabled={items.length === 0}
                />
            </div>

            <Dialog
                isOpen={isRestartDialogOpen}
                onClose={() => setIsRestartDialogOpen(false)}
                title={t('queue.restart.title', { type: restartType === 'server' ? t('queue.server') : t('queue.executor') })}
            >
                <div style={{ padding: '20px' }}>
                    <p>{t('queue.restart.confirm', { type: restartType === 'server' ? t('queue.server') : t('queue.executor') })}</p>
                    <p>{t('queue.restart.warning')}</p>
                </div>
                <div className="bp5-dialog-footer">
                    <Button onClick={() => setIsRestartDialogOpen(false)}>{t('queue.restart.cancel')}</Button>
                    <Button
                        intent={Intent.WARNING}
                        onClick={handleRestartService}
                        loading={isRestarting}
                        disabled={isRestarting}
                    >
                        {t('queue.restart.confirmButton')}
                    </Button>
                </div>
            </Dialog>

            <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
                {loading ? (
                    <div style={{ textAlign: 'center', padding: '40px' }}>
                        <Spinner />
                    </div>
                ) : error && items.length === 0 ? (
                    <NonIdealState icon="error" title={t('queue.loadError')} description={error} />
                ) : items.length === 0 ? (
                    <NonIdealState icon="inbox" title={t('queue.empty')} />
                ) : (
                    items.map(item => (
                        <Card key={item.id} elevation={Elevation.ONE} style={{ marginBottom: '8px', padding: '10px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <h3 style={{ margin: '0 0 5px 0' }}>{item.name}</h3>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                        <Tag intent={getStatusColor(item.status) as any}>
                                            {getStatusText(item.status)}
                                        </Tag>
                                        <span style={{ fontSize: '0.9em', color: '#666' }}>
                                            {t(`queue.kind.${item.kind}`)}
                                        </span>
                                        <span style={{ fontSize: '0.9em', color: '#666' }}>
                                            {new Date(item.createdAt * 1000).toLocaleString()}
                                        </span>
                                    </div>
                                </div>
                                <div style={{ display: 'flex', gap: '5px' }}>
                                    {(item.status === 'waiting' || item.status === 'processing') && (
                                        <Button
                                            small
                                            icon="stop"
                                            variant="minimal"
                                            intent={Intent.WARNING}
                                            onClick={() => handleCancel(item.id)}
                                            title={t('queue.actions.cancel')}
                                        />
                                    )}
                                    <Button
                                        small
                                        icon="cross"
                                        variant="minimal"
                                        intent="danger"
                                        onClick={() => handleRemove(item.id)}
                                        title={t('queue.actions.remove')}
                                    />
                                </div>
                            </div>

                            {item.status === 'processing' && (
                                <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                                    <div style={{ flex: 1, height: '6px', backgroundColor: '#e1e8ed', borderRadius: '3px' }}>
                                        <div
                                            style={{
                                                width: `${item.progress}%`,
                                                height: '100%',
                                                backgroundColor: '#2b95d6',
                                                borderRadius: '3px',
                                                transition: 'width 0.3s'
                                            }}
                                        />
                                    </div>
                                    <span>{item.progress}%</span>
                                </div>
                            )}
                            {item.status === 'failed' && item.error && (
                                <div style={{ marginTop: '8px', color: 'red', fontSize: '0.9em' }}>{item.error}</div>
                            )}
                        </Card>
                    ))
                )}
            </div>
        </div>
    );
};

export default Queue;
