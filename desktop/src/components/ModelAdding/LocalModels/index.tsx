import React, { useRef, useState } from 'react';
import { Button, Divider, NonIdealState, Tag, Intent, Callout, ProgressBar, OverlayToaster, type Toaster } from '@blueprintjs/core';
import {Model, ModelsProvider, WatchedDirectory} from '../../../providers/IModelsProvider';
import styles from './style.module.css'

interface LocalModelsProps {
  modelsProvider: ModelsProvider;
  onModelAdd?: (modelPath: string) => void;
}

const LocalModels: React.FC<LocalModelsProps> = (props) => {
    const { modelsProvider, onModelAdd } = props

    const [ selectedDirectory, setSelectedDirectory ] = useState<string>('')
    const [ watchedDirectories, setWatchedDirectories ] = useState<WatchedDirectory[]>([])
    const [ isScanning, setIsScanning ] = useState<boolean>(false)
    const [ installingModels, setInstallingModels ] = useState<Set<string>>()
    const [ installedModels, setInstalledModels ] = useState<Set<string>>()

    const scannedModels = useRef<Model[]>([])
    const toaster = useRef<Toaster>()

    const selectDirectory = async () => {
        try {
            const selectedDir = await modelsProvider.selectDirectory();
            console.log('选择目录:', selectedDir)
            if (selectedDir) {
                setSelectedDirectory(selectedDir)

                // 扫描选中的目录
                setIsScanning(true)
                scannedModels.current = [] //清空之前的扫描结果
                // installedModels: new Set<string>() // 清空已安装模型状态

                try {
                    // 使用回调函数实时更新扫描到的模型
                    const models = await modelsProvider.scanDirectory(
                        selectedDir,
                        (model: Model) => {
                            // 每当找到一个模型，就更新状态
                            scannedModels.current.push(model)
                        }
                    );

                    toaster.current?.show({
                        icon: 'tick',
                        intent: 'success',
                        message: `扫描完成，共找到模型: ${models.length}`
                    })
                    setIsScanning(false)
                } catch (error) {
                    toaster.current?.show({
                        icon: 'warning-sign',
                        intent: 'danger',
                        message: '扫描目录失败'
                    })
                    console.log(error)
                    setIsScanning(false)
                }
            }
        } catch (error) {
            toaster.current?.show({
                icon: 'warning-sign',
                intent: 'danger',
                message: `选择目录失败: ${error}`
            })
        }
    }

    // 添加单个模型
    const handleAddModel = async (model: Model) => {
        // 如果模型已经在安装中或已安装，则不执行操作
        if (installingModels?.has(model.id) || installedModels?.has(model.id)) {
            return;
        }

        // 标记模型为正在安装
        const newSet = new Set(installingModels)
        newSet.add(model.id)
        setInstallingModels(newSet)

        try {
            const success = await modelsProvider.addModel(model.path);
            console.log({success})

            // 更新模型状态
            const newingSet = new Set(installingModels)
            newingSet.delete(model.id)
            setInstallingModels(newingSet)

            const newedSet = new Set(installedModels)
            if (success) {
                newedSet.add(model.id);
                setInstalledModels(newedSet)
                onModelAdd?.(model.path);
            }
        } catch (error) {
            console.error("添加模型失败:", error);
            toaster.current?.show({
                icon: 'warning-sign',
                intent: 'danger',
                message: `添加模型失败: ${error}`
            })
            // 安装失败，从安装中状态移除
            const newSet = new Set(installingModels)
            newSet.delete(model.id)
            setInstallingModels(newSet)
        }
    }

    // 添加监听目录
    const handleAddWatchedDirectory = async () => {
        try {
            const selectedDirectory = await modelsProvider.selectDirectory()
            console.log(selectedDirectory)
            const newWatchedDir = await modelsProvider.addWatchedDirectory(selectedDirectory);
            console.log(newWatchedDir)

            setWatchedDirectories([...watchedDirectories, newWatchedDir])
        } catch (error) {
            toaster.current?.show({
                icon: 'warning-sign',
                intent: 'danger',
                message: `添加监听目录失败: ${error}`
            })
        }
    }

    const cancelWatch = (id: string) => {
        toaster.current?.show({
            icon: 'warning-sign',
            intent: 'danger',
            message: '添加监听目录是假的，所以这里位置对不上'
        })
        const newArr = watchedDirectories.slice()
        const index = newArr.findIndex(n => n.id === id)
        if (index > -1) {
            newArr.splice(index, 1)
        }
        setWatchedDirectories(newArr)
    }

    // @ts-ignore
    // @ts-ignore
    return (
        <div className={styles.localModel}>
            <div className={styles.scan}>
                <div className={styles.title}>
                    扫描目录
                    <div className={styles.subtitle}>选择一个目录来查找模型</div>
                </div>

                <div className={styles.choose}>
                    <Button className={styles.chooseButton} intent="primary" variant="outlined" size="large" onClick={selectDirectory}>选择目录</Button>
                    <Callout intent={selectedDirectory ? 'success' : 'none'} compact icon={selectedDirectory ? 'folder-open' : 'folder-close'}>当前目录：{selectedDirectory || '-'}</Callout>
                </div>

                <div className={styles.modelList}>
                    {
                        !selectedDirectory &&
                        <div className={styles.empty}>
                            <NonIdealState
                                icon="add-to-folder"
                                title="尚未添加目录"
                                description="请点击上方按钮添加目录"
                            />
                        </div>
                    }
                    {
                        isScanning &&
                        <ProgressBar animate intent="primary" />
                    }
                    {
                        selectedDirectory && !isScanning && scannedModels.current.length < 1 &&
                        <div className={styles.empty}>
                            <NonIdealState
                                icon="error"
                                title="没有扫描到模型"
                                description="请重新选择目录"
                            />
                        </div>
                    }
                    {scannedModels.current.map(model => {
                        const isInstalling = installingModels?.has(model.id);
                        const isInstalled = installedModels?.has(model.id);

                        return (
                            <div className={styles.modelCard} key={model.id} style={{
                                backgroundColor: isInstalled ? '#f0f8f0' : undefined
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div>
                                        <div className={styles.name}>{model.name}</div>
                                        <div className={styles.path}>{model.path}</div>
                                        <div>
                                            <Tag intent="primary" minimal style={{ marginRight: 5 }}>{model.type}</Tag>
                                            <Tag intent="success" minimal>{model.size}</Tag>
                                            {isInstalled && (
                                                <Tag intent="success" style={{ marginLeft: 5 }}>已安装</Tag>
                                            )}
                                        </div>
                                    </div>
                                    {
                                        isInstalled
                                            ? <Button icon="tick" intent={Intent.SUCCESS} disabled>已安装</Button>
                                            : <Button icon="plus" intent={Intent.SUCCESS} loading={isInstalling} onClick={() => handleAddModel(model)}>添加</Button>
                                    }
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            <Divider className={styles.divider} />

            <div className={styles.observer}>
                <div className={styles.title}>
                    监听目录
                    <div className={styles.subtitle}>添加监听目录后，应用启动时将自动扫描这些目录中的模型。</div>
                </div>
                <div className={styles.observerContent}>
                    {
                        watchedDirectories.length > 0
                            ?
                            <NonIdealState
                                icon="eye-open"
                                title="正在监听..."
                                description={watchedDirectories.map(w => (
                                    <div className={styles.singleWatch}>
                                        <div>{w.path}</div>
                                        <Button className={styles.removeButton} variant="minimal" intent="danger" size="small" onClick={() => cancelWatch(w.id)}>取消监听</Button>
                                    </div>
                                ))}
                                action={<Button intent="primary" onClick={handleAddWatchedDirectory}>继续添加</Button>}
                            />
                          :
                            <Button intent="primary" size="large" onClick={handleAddWatchedDirectory}>添加监听目录</Button>
                    }
                </div>
            </div>
            {/*@ts-ignore*/}
            <OverlayToaster ref={toaster}/>
        </div>
    )
}

export default LocalModels;
