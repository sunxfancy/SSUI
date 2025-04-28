import React, { useState, useEffect, useRef } from 'react';
import { Card, Elevation, Button, Tag, Spinner, Icon, Dialog, Intent } from '@blueprintjs/core';
import ExecutorService from '../../services/Executor';
import ServerService from '../../services/Server';
import { CommandInfo } from '../../providers/IInstallerProvider';
import styles from './style.module.css';

interface QueueItem {
    id: string;
    name: string;
    status: 'waiting' | 'processing' | 'completed' | 'failed';
    progress: number;
    createdAt: Date;
    type: string;
    priority: number;
}

interface QueueProps {
    items?: QueueItem[];
    onRemoveItem?: (id: string) => void;
    onPauseItem?: (id: string) => void;
    onResumeItem?: (id: string) => void;
}

const Queue: React.FC<QueueProps> = ({
                                         items = [],
                                         onRemoveItem,
                                         onPauseItem,
                                         onResumeItem
                                     }) => {
    const [visibleItems, setVisibleItems] = useState<QueueItem[]>([]);
    const [executorStatus, setExecutorStatus] = useState<CommandInfo | null>(null);
    const [serverStatus, setServerStatus] = useState<CommandInfo | null>(null);
    const [isRestartDialogOpen, setIsRestartDialogOpen] = useState(false);
    const [restartType, setRestartType] = useState<'server' | 'executor' | null>(null);
    const [isRestarting, setIsRestarting] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const itemHeight = 80; // 每个队列项的估计高度
    const bufferSize = 5; // 上下缓冲区的项目数量

    // 获取服务状态
    useEffect(() => {
        const fetchStatus = async () => {
            try {
                // 获取执行器状态
                const executorResult = await ExecutorService.getInstance().getExecutorStatus();
                setExecutorStatus(executorResult);

                // 获取服务器状态
                const serverResult = await ServerService.getInstance().getServerStatus();
                setServerStatus(serverResult);
            } catch (error) {
                console.error('获取服务状态时出错:', error);
            }
        };

        // 初始获取状态
        fetchStatus();

        // 设置定时器，每 30 秒更新一次状态
        const intervalId = setInterval(fetchStatus, 30000);

        return () => {
            clearInterval(intervalId);
        };
    }, []);

    // 根据滚动位置计算可见项
    const calculateVisibleItems = () => {
        if (!containerRef.current) return;

        const container = containerRef.current;
        const scrollTop = container.scrollTop;
        const containerHeight = container.clientHeight;

        // 计算可见范围内的第一个和最后一个项目的索引
        const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - bufferSize);
        const endIndex = Math.min(
            items.length - 1,
            Math.ceil((scrollTop + containerHeight) / itemHeight) + bufferSize
        );

        // 设置可见项
        setVisibleItems(items.slice(startIndex, endIndex + 1));
    };

    // 监听滚动事件
    useEffect(() => {
        const container = containerRef.current;
        if (container) {
            container.addEventListener('scroll', calculateVisibleItems);
            // 初始计算
            calculateVisibleItems();

            return () => {
                container.removeEventListener('scroll', calculateVisibleItems);
            };
        }
    }, [items]);

    // 当项目列表变化时重新计算
    useEffect(() => {
        calculateVisibleItems();
    }, [items]);

    // 获取状态对应的标签颜色
    const getStatusColor = (status: string) => {
        switch (status) {
            case 'waiting': return 'blue';
            case 'processing': return 'orange';
            case 'completed': return 'green';
            case 'failed': return 'red';
            default: return 'gray';
        }
    };

    // 获取状态对应的中文描述
    const getStatusText = (status: string) => {
        switch (status) {
            case 'waiting': return '等待中';
            case 'processing': return '处理中';
            case 'completed': return '已完成';
            case 'failed': return '失败';
            default: return '未知';
        }
    };

    // 重启服务
    const handleRestartService = async () => {
        if (!restartType) return;

        setIsRestarting(true);
        try {

            // 根据类型调用相应的重启方法
            if (restartType === 'server') {
                const newStatus = await ServerService.getInstance().restartServer();
                setServerStatus(newStatus);
            } else {
                const newStatus = await ExecutorService.getInstance().restartExecutor();
                setExecutorStatus(newStatus);
            }

            console.log(`重启${restartType === 'server' ? '服务器' : '执行器'}`);
        } catch (error) {
            console.error(`重启${restartType === 'server' ? '服务器' : '执行器'}时出错:`, error);
        } finally {
            setIsRestarting(false);
            setIsRestartDialogOpen(false);
        }
    };

    // 获取服务状态图标
    const getServiceStatusIcon = (status: CommandInfo | null, type: 'server' | 'executor') => {
        if (!status) return <Icon icon="circle" intent="none" />;

        // 检查消息中是否包含"运行中"或"启动成功"
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

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '10px', borderBottom: '1px solid #e1e8ed', display: 'flex', justifyContent: 'space-between' }}>
                <div>
                    <h2 style={{ margin: 0 }}>任务队列</h2>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div>共 {items.length} 个任务</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <span>执行器:</span>
                            {getServiceStatusIcon(executorStatus, 'executor')}
                            <span style={{ marginLeft: '10px' }}>服务器:</span>
                            {getServiceStatusIcon(serverStatus, 'server')}
                        </div>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '2px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <div className={styles.toggleButton}>
                            <Icon icon="play" size={20} />
                        </div>
                        {/*<Button text="继续" intent="success" icon="play" variant="solid" />*/}
                        {/*<Button text="暂停" intent="warning" icon="pause" variant="solid" />*/}
                    </div>

                </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <Button text="清除缓存"  icon="trash" variant="solid" />
                <Button text="禁用缓存" intent="danger" icon="disable" variant="solid" />
            </div>


            {/* 重启服务确认对话框 */}
            <Dialog
                isOpen={isRestartDialogOpen}
                onClose={() => setIsRestartDialogOpen(false)}
                title={`重启${restartType === 'server' ? '服务器' : '执行器'}`}
            >
                <div style={{ padding: '20px' }}>
                    <p>确定要重启{restartType === 'server' ? '服务器' : '执行器'}吗？</p>
                    <p>重启过程中服务将暂时不可用。</p>
                </div>
                <div className="bp5-dialog-footer">
                    <Button onClick={() => setIsRestartDialogOpen(false)}>取消</Button>
                    <Button
                        intent={Intent.WARNING}
                        onClick={handleRestartService}
                        loading={isRestarting}
                        disabled={isRestarting}
                    >
                        确认重启
                    </Button>
                </div>
            </Dialog>

            <div
                ref={containerRef}
                style={{
                    flex: 1,
                    overflowY: 'auto',
                    position: 'relative',
                    height: 'calc(100vh - 150px)'
                }}
            >
                {/* 创建一个占位容器，确保滚动条的高度正确 */}
                <div style={{ height: `${items.length * itemHeight}px` }}>
                    {/* 只渲染可见的项目 */}
                    {visibleItems.map((item, _) => {
                        // 计算项目在整个列表中的位置
                        const itemIndex = items.findIndex(i => i.id === item.id);

                        return (
                            <Card
                                key={item.id}
                                elevation={Elevation.ONE}
                                style={{
                                    margin: '8px',
                                    padding: '10px',
                                    position: 'absolute',
                                    top: `${itemIndex * itemHeight}px`,
                                    left: 0,
                                    right: 0,
                                    height: `${itemHeight - 16}px`, // 减去margin
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div>
                                        <h3 style={{ margin: '0 0 5px 0' }}>{item.name}</h3>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                            <Tag intent={getStatusColor(item.status) as any}>
                                                {getStatusText(item.status)}
                                            </Tag>
                                            <span style={{ fontSize: '0.9em', color: '#666' }}>
                        {item.type} · 优先级: {item.priority}
                      </span>
                                            <span style={{ fontSize: '0.9em', color: '#666' }}>
                        {item.createdAt.toLocaleString()}
                      </span>
                                        </div>
                                    </div>

                                    <div style={{ display: 'flex', gap: '5px' }}>
                                        {item.status === 'processing' && (
                                            <Button
                                                small
                                                icon="pause"
                                                variant="minimal"
                                                onClick={() => onPauseItem?.(item.id)}
                                                title="暂停"
                                            />
                                        )}
                                        {item.status === 'waiting' && (
                                            <Button
                                                small
                                                icon="play"
                                                variant="minimal"
                                                onClick={() => onResumeItem?.(item.id)}
                                                title="开始"
                                            />
                                        )}
                                        <Button
                                            small
                                            icon="cross"
                                            variant="minimal"
                                            intent="danger"
                                            onClick={() => onRemoveItem?.(item.id)}
                                            title="移除"
                                        />
                                    </div>
                                </div>

                                {item.status === 'processing' && (
                                    <div style={{
                                        marginTop: '10px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '10px'
                                    }}>
                                        <div style={{ flex: 1, height: '6px', backgroundColor: '#e1e8ed', borderRadius: '3px' }}>
                                            <div
                                                style={{
                                                    width: `${item.progress}%`,
                                                    height: '100%',
                                                    backgroundColor: '#2b95d6',
                                                    borderRadius: '3px'
                                                }}
                                            />
                                        </div>
                                        <Spinner size={16} />
                                        <span>{item.progress}%</span>
                                    </div>
                                )}
                            </Card>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default Queue;
