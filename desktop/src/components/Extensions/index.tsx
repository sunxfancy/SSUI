import React, {useEffect, useRef, useState} from "react";
import styles from './style.module.css'
import { Button, Icon, InputGroup, Tabs, Tab, Tag, Switch, CompoundTag, IconName } from "@blueprintjs/core";
import { IExtensionsProvider } from '../../providers/IExtensionsProvider';
import { ExtensionsProvider } from '../../providers/ExtensionsProvider';
import { useTranslation } from 'react-i18next';


export interface ExtensionItem {
    id: string;
    name: string;
    description: string;
    version: string;
    author: string;
    icon: IconName;
    tags: string[];
    installed: boolean;
    disabled: boolean;
    featured: boolean;
}


interface ExtensionsProps {
    provider: IExtensionsProvider;
    onOpenExtensionStore: () => void;
}

export const Extensions = (props: ExtensionsProps) => {
    const { t } = useTranslation();
    const [ searchQuery, setSearchQuery ] = useState('')
    const [ extensions, setExtensions ] = useState<ExtensionItem[]>([])
    const [ retryCount, setRetryCount ] = useState(0)

    const provider = useRef<IExtensionsProvider>(props.provider || new ExtensionsProvider())
    const retryTimeout = useRef<NodeJS.Timeout|null>(null)

    useEffect(() => {
        loadExtensions()

        return () => {
            if (retryTimeout.current) {
                clearTimeout(retryTimeout.current)
                retryTimeout.current = null
            }
        }
    }, []);

    const handleSearchChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const query = e.target.value
        setSearchQuery(query)

        if (query.length > 0) {
            try {
                const searchResults = await provider.current.searchExtensions(query);
                setExtensions(searchResults)
            } catch (error) {
                console.error("搜索扩展失败:", error);
            }
        } else {
            try {
                const allExtensions = await provider.current.getExtensions();
                setExtensions(allExtensions)
            } catch (error) {
                console.error("加载扩展数据失败:", error);
            }
        }
    }

    const clearSearch = async () => {
        setSearchQuery('')
        await loadExtensions();
    };

    const loadExtensions = async () => {
        try {
            const extensions = await provider.current.getExtensions();
            setExtensions(extensions)
            setRetryCount(0) // 重置重试计数
        } catch (error) {
            console.error("加载扩展数据失败:", error);

            // 如果重试次数小于3次，则3秒后重试
            if (retryCount < 3) {
                setRetryCount(retryCount + 1)
                // 清除之前的定时器
                if (retryTimeout.current) {
                    clearTimeout(retryTimeout.current);
                }

                // 设置新的定时器
                retryTimeout.current = setTimeout(() => {
                    loadExtensions();
                }, 3000);
            }
        }
    };

    const operateExtension = async (extensionId: string, action: string) => {
        try {
            let success = null
            switch (action) {
                case 'install': success = await provider.current.installExtension(extensionId); break;
                case 'uninstall': success = await provider.current.uninstallExtension(extensionId); break;
                case 'enable': success = await provider.current.enableExtension(extensionId); break;
                case 'disable': success = await provider.current.disableExtension(extensionId); break;
            }
            if (success) {
                const extensions = await provider.current.getExtensions();
                setExtensions(extensions)
            }
        } catch (error) {
            console.error(`操作扩展失败（${action}）:`, error);
        }
    }

    const RenderExtensionCard = (extension: ExtensionItem) => {
        const isProduction = import.meta.env.PROD;

        return (
            <div key={extension.id} className={styles.extensionsCard}>
                <div className={styles.main}>
                    <div className={styles.iconPart}>
                        <Icon icon={extension.icon} size={24} />
                    </div>
                    <div className={styles.textPart}>
                        <div className={styles.name}>{extension.name}</div>
                        <div className={styles.extraInfo}>
                            <CompoundTag
                                minimal
                                intent="primary"
                                leftContent={<div className={styles.iconWp}><Icon icon="person" size={10}></Icon></div>}
                            >
                                <div style={{ fontSize: '10px' }}>{extension.author}</div>
                            </CompoundTag>
                            <CompoundTag
                                minimal
                                intent="success"
                                leftContent={<div className={styles.iconWp}><Icon icon="git-branch" size={10}></Icon></div>}
                            >
                                <div style={{ fontSize: '10px' }}>{extension.version}</div>
                            </CompoundTag>
                        </div>
                    </div>
                </div>
                <div className={styles.subContent}>
                    <div>
                        <p className={styles.cardDesc}>{extension.description}</p>
                        <div>
                            {extension.tags.map(tag => (
                                <Tag key={tag} minimal style={{ marginRight: '5px' }}>{tag}</Tag>
                            ))}
                        </div>
                    </div>

                    <div className={styles.operate}>
                        {
                            extension.installed
                                ? (
                                    <>
                                        <Switch checked={extension.disabled} size="large" onChange={e => operateExtension(extension.id, e.target.checked ? 'enable' : 'disable')} style={{ margin: 0 }} />
                                        {
                                            isProduction &&
                                            <Button small intent="danger" onClick={() => operateExtension(extension.id, 'uninstall')}>卸载</Button>
                                        }
                                    </>
                                )
                                : <Button small intent="success" onClick={() => operateExtension(extension.id, 'install')}>安装</Button>
                        }
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className={styles.extensions}>
            <div className={styles.title}>
                <div className={styles.titleText}>{t('extensions.title')}</div>
            </div>
            <div className={styles.searchPart}>
                <InputGroup
                    leftIcon="search"
                    placeholder={t('extensions.search.placeholder')}
                    value={searchQuery}
                    onChange={handleSearchChange}
                    rightElement={
                        searchQuery ?
                            <Button icon="cross" minimal onClick={clearSearch} /> :
                            undefined
                    }
                />
                <Button
                    icon="shop"
                    intent="primary"
                    onClick={props.onOpenExtensionStore}
                    className={styles.searchButton}
                >
                    {t('extensions.store')}
                </Button>
            </div>
            {
                searchQuery
                    ?
                        <div>
                            <h3>{t('extensions.search.title')}</h3>
                            {
                                extensions.length > 0
                                    ? extensions.map(RenderExtensionCard)
                                    : <div>{t('extensions.search.noResults')}</div>
                            }
                        </div>
                    :
                        <div>
                            <Tabs>
                                <Tab
                                    id="installed"
                                    title={t('extensions.tabs.installed')}
                                    panel={
                                        <div className={styles.tabContent}>
                                            {extensions.filter(ext => ext.installed).length > 0 ? (
                                                extensions.filter(ext => ext.installed).map(RenderExtensionCard)
                                            ) : (
                                                <div style={{ textAlign: 'center', padding: '20px', color: '#888' }}>
                                                    {t('extensions.empty')}
                                                </div>
                                            )}
                                        </div>
                                    }
                                />
                                <Tab
                                    id="featured"
                                    title={t('extensions.tabs.featured')}
                                    panel={
                                        <div className={styles.tabContent}>
                                            {extensions.filter(ext => ext.featured).map(RenderExtensionCard)}
                                        </div>
                                    }
                                />
                            </Tabs>
                        </div>
            }
        </div>
    )
}
