import React, { useRef, useState } from 'react';
import { Button, Divider, NonIdealState, Tag, Intent, Callout, ProgressBar, OverlayToaster, type Toaster } from '@blueprintjs/core';
import {Model, ModelsProvider, WatchedDirectory} from '../../../providers/IModelsProvider';
import { produce } from 'immer'
import styles from './style.module.css'
import { useTranslation } from 'react-i18next'

interface LocalModelsProps {
  modelsProvider: ModelsProvider;
  onModelAdd?: (modelPath: string) => void;
}

const LocalModels: React.FC<LocalModelsProps> = (props) => {
    const { modelsProvider, onModelAdd } = props

    const [ selectedDirectory, setSelectedDirectory ] = useState<string>('')
    const [ watchedDirectories, setWatchedDirectories ] = useState<WatchedDirectory[]>([])
    const [ isScanning, setIsScanning ] = useState<boolean>(false)
    const [ installingModels, setInstallingModels ] = useState<Set<string>>(new Set())
    const [ installedModels, setInstalledModels ] = useState<Set<string>>(new Set())
    const [ scannedModels, setScannedModels ] = useState<Model[]>([])

    const toaster = useRef<Toaster>()
    const { t } = useTranslation()

    const selectDirectory = async () => {
        try {
            const selectedDir = await modelsProvider.selectDirectory();
            if (selectedDir) {
                setSelectedDirectory(selectedDir)

                // 扫描选中的目录
                setIsScanning(true)
                setScannedModels([]) //清空之前的扫描结果
                // installedModels: new Set<string>() // 清空已安装模型状态

                try {
                    // 使用回调函数实时更新扫描到的模型
                    const models = await modelsProvider.scanDirectory(
                        selectedDir,
                        (model: Model) => {
                            if (model.installed) {
                                console.log("model installed: ", model)
                                setInstalledModels(oldModels =>
                                    new Set(oldModels ? [...oldModels, model.id] : [model.id])
                                )
                            }

                            // 每当找到一个模型，就更新状态
                            setScannedModels(oldModels => produce(oldModels, models => {
                                models?.push(model)
                            }))
                        }
                    );

                    toaster.current?.show({
                        icon: 'tick',
                        intent: 'success',
                        message: `${t('scanFinish')}: ${models.length}`
                    })
                    setIsScanning(false)
                } catch (error) {
                    toaster.current?.show({
                        icon: 'warning-sign',
                        intent: 'danger',
                        message: t('scanFail')
                    })
                    console.log(error)
                    setIsScanning(false)
                }
            }
        } catch (error) {
            toaster.current?.show({
                icon: 'warning-sign',
                intent: 'danger',
                message: `${t('chooseDirFail')}: ${error}`
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
        setInstallingModels(produce(installingModels, models => {
            models?.add(model.id)
        }))

        try {
            const success = await modelsProvider.addModel(model.path);

            // 更新模型状态
            setInstallingModels((oldModels) => produce(oldModels, models => {
                models?.delete(model.id)
                return models
            }))

            if (success) {
                setInstalledModels((oldModels) => produce(oldModels, models => (
                    new Set(models ? [...models, model.id] : [model.id])
                )))
                onModelAdd?.(model.path);
            }
        } catch (error) {
            console.error(`${t('addModelFail')}:`, error);
            toaster.current?.show({
                icon: 'warning-sign',
                intent: 'danger',
                message: `${t('addModelFail')}: ${error}`
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
            const newWatchedDir = await modelsProvider.addWatchedDirectory(selectedDirectory);

            setWatchedDirectories([...watchedDirectories, newWatchedDir])
        } catch (error) {
            toaster.current?.show({
                icon: 'warning-sign',
                intent: 'danger',
                message: `${t('addWatchFail')}: ${error}`
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

    return (
        <div className={styles.localModel}>
            <div className={styles.scan}>
                <div className={styles.title}>
                    {t('scanDir')}
                    <div className={styles.subtitle}>{t('scanDirTip')}</div>
                </div>

                <div className={styles.choose}>
                    <Button className={styles.chooseButton} intent="primary" variant="outlined" size="large" onClick={selectDirectory}>{t('chooseDir')}</Button>
                    <Callout intent={selectedDirectory ? 'success' : 'none'} compact icon={selectedDirectory ? 'folder-open' : 'folder-close'}>{t('currentDir')}：{selectedDirectory || '-'}</Callout>
                </div>

                <div className={styles.modelList}>
                    {
                        !selectedDirectory &&
                        <div className={styles.empty}>
                            <NonIdealState
                                icon="add-to-folder"
                                title={t('scanDir_init_title')}
                                description={t('scanDir_init_content')}
                            />
                        </div>
                    }
                    {
                        isScanning &&
                        <ProgressBar animate intent="primary" />
                    }
                    {
                        selectedDirectory && !isScanning && scannedModels.length < 1 &&
                        <div className={styles.empty}>
                            <NonIdealState
                                icon="error"
                                title={t('scanDir_empty_title')}
                                description={t('scanDir_empty_content')}
                            />
                        </div>
                    }
                    {
                        scannedModels.map(model => {
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
                                                    <Tag intent="success" style={{ marginLeft: 5 }}>{t('installed')}</Tag>
                                                )}
                                            </div>
                                        </div>
                                        {
                                            isInstalled
                                                ? <Button icon="tick" intent={Intent.SUCCESS} disabled>{t('installed')}</Button>
                                                : <Button icon="plus" intent={Intent.SUCCESS} loading={isInstalling} onClick={() => handleAddModel(model)}>{t('add')}</Button>
                                        }
                                    </div>
                                </div>
                            );
                        })
                    }
                </div>
            </div>

            <Divider className={styles.divider} />

            <div className={styles.observer}>
                <div className={styles.title}>
                    {t('watchDir')}
                    <div className={styles.subtitle}>{t('watchDirTip')}</div>
                </div>
                <div className={styles.observerContent}>
                    {
                        watchedDirectories.length > 0
                            ?
                            <NonIdealState
                                icon="eye-open"
                                title={t('watching')}
                                description={watchedDirectories.map(w => (
                                    <div className={styles.singleWatch}>
                                        <div>{w.path}</div>
                                        <Button className={styles.removeButton} variant="minimal" intent="danger" size="small" onClick={() => cancelWatch(w.id)}>{t('cancelAdd')}</Button>
                                    </div>
                                ))}
                                action={<Button intent="primary" onClick={handleAddWatchedDirectory}>{t('continueAdd')}</Button>}
                            />
                          :
                            <Button intent="primary" size="large" onClick={handleAddWatchedDirectory}>{t('addWatchDir')}</Button>
                    }
                </div>
            </div>
            {/*@ts-ignore*/}
            <OverlayToaster ref={toaster}/>
        </div>
    )
}

export default LocalModels;
