import React, {useEffect, useRef, useState} from 'react';
import { Button, InputGroup, Menu, MenuItem, Popover, Position, Tag, CompoundTag, NonIdealState } from "@blueprintjs/core";
import { Select } from '@blueprintjs/select'
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import { IModelManagerProvider, ModelGroup } from '../../providers/IModelManagerProvider';
import { ModelManagerProvider } from '../../providers/ModelManagerProvider';
import styles from './style.module.css'
import HuggingfaceLogo from '../ModelAdding/HuggingfaceModels/logo_huggingface.svg'
import CivitaiLogo from './logo_civitai.svg'

export interface ModelState {
    groups: ModelGroup[];
    searchQuery: string;
    selectedTags: string[];
    availableTags: string[];
}

interface ModelManagerProps {
    provider?: IModelManagerProvider;
    addModel?: () => void;
}

export const ModelManager = (props: ModelManagerProps) => {

    const [ groups, setGroups ] = useState<ModelGroup[]>([])
    const [ searchQuery, setSearchQuery ] = useState('')
    const [ selectedTags, setSelectedTags ] = useState<string[]>([])
    const [ availableTags, setAvailableTags ] = useState<string[]>([])
    const [ currentModelType, setCurrentModelType ] = useState('全部')

    const provider = useRef(props.provider || new ModelManagerProvider())
    const containerRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        const init = async () => {
            // 加载数据
            try {
                const groups = await provider.current.getModelGroups();
                const availableTags = await provider.current.getAllTags();
                setGroups(groups)
                setAvailableTags(availableTags)
            } catch (error) {
                console.error("加载模型数据失败:", error);
            }
        }

        init()
    }, []);

    useEffect(() => {
        const fetchModels = async () => {
            try {
                const filteredGroups = await provider.current.searchModels(searchQuery, selectedTags);
                setGroups(filteredGroups)
            } catch (error) {
                console.error("搜索模型失败:", error);
            }
        }
        fetchModels()
    }, [searchQuery, selectedTags]);


    const toggleTagSelection = (tag: string) => {
        if (selectedTags.includes(tag)) {
            setSelectedTags(selectedTags.filter(t => t !== tag))
        } else {
            setSelectedTags([...selectedTags, tag])
        }
    };

    const deleteModel = async (groupId: string, modelId: string) => {
        const success = await provider.current.deleteModel(groupId, modelId);

        if (success) {
            setGroups(



                groups
                    .map(g => {
                    return g.id === groupId
                        ? { ...g, models: g.models.filter(model => model.id !== modelId) }
                        : g
                }).filter(g => g.models.length > 0) // 移除空组
            )
        }
    };

    const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchQuery(event.target.value)
    };

    const chooseModelType = (type: string) => {
        setCurrentModelType(type)
    }

    const renderTagMenu = () => {
        return (
            <Menu>
                {availableTags.map(tag => (
                    <MenuItem
                        key={tag}
                        text={tag}
                        icon={selectedTags.includes(tag) ? "tick" : "blank"}
                        onClick={() => toggleTagSelection(tag)}
                    />
                ))}
            </Menu>
        );
    }

    return (
        <div className={styles.modelManager} ref={containerRef}>
            <div className={styles.title}>
                <span className={styles.titleText}>模型管理</span>
            </div>
            <div className={styles.input}>
                <InputGroup
                    leftIcon="search"
                    placeholder="搜索模型名称或描述..."
                    value={searchQuery}
                    onChange={handleSearchChange}
                    rightElement={
                        searchQuery ?
                            <Button
                                icon="cross"
                                variant='minimal'
                                onClick={() => {
                                    setSearchQuery('');
                                }}
                            /> : undefined
                    }
                />
                <Button
                    className={styles.addButton}
                    text="添加模型"
                    icon="plus"
                    size="medium"
                    intent="success"
                    variant='solid'
                    onClick={() => props.addModel?.()}
                />
            </div>

            <div className={styles.filter}>
                <Select
                    items={['全部', '预设模型组', 'Civitai', 'Huggingface', '本地模型']}
                    onItemSelect={chooseModelType}
                    itemRenderer={(str, { handleClick }) => {
                        return <MenuItem text={str} onClick={handleClick} label={'2'} />
                    }}
                    filterable={false}
                >
                    <Button endIcon="caret-down">{currentModelType}</Button>
                </Select>
                <Popover
                    content={renderTagMenu()}
                    position={Position.BOTTOM_LEFT}
                >
                    <Button
                        icon="tag"
                        rightIcon="caret-down"
                        text={selectedTags.length > 0 ? `已选择 ${selectedTags.length} 个标签` : "按标签筛选"}
                    />
                </Popover>
            </div>

            <div className={styles.modelList}>
                {groups.map((group, index) => (
                    <div className={styles.model} key={group.id}>
                        <div className={styles.modelName}>
                            <div className={styles.modelNameInner}>
                                <div>{group.name}</div>
                                <span className={styles.modelSum}>{group.models.length}</span>
                            </div>
                        </div>

                        <div className={styles.models}>
                            {
                                group.models.map(model => (
                                    <div className={styles.singleModel} key={model.id}>
                                        <div className={styles.name}>{model.name}</div>
                                        <div className={styles.tagWp}>
                                            <CompoundTag
                                                minimal
                                                interactive
                                                leftContent={
                                                    <div className={styles.compoundLeft}>
                                                        <img style={{ width: '12px' }} src={ index === 0 ? HuggingfaceLogo : CivitaiLogo} />
                                                    </div>

                                                }>
                                                <div style={{ fontSize: '11px' }}>id: 123131</div>
                                            </CompoundTag>

                                            {model.tags.map(tag => (
                                                <Tag
                                                    key={tag}
                                                    style={{ fontSize: "11px", marginLeft: '4px' }}
                                                    interactive
                                                    intent="primary"
                                                    minimal
                                                    onClick={() => toggleTagSelection(tag)}
                                                >
                                                    {tag}
                                                </Tag>
                                            ))}
                                        </div>


                                        <div className={styles.desc} style={{ margin: "0", color: "#666" }}>{model.description}</div>
                                        <Button
                                            className={styles.deleteBtn}
                                            icon="trash"
                                            intent="danger"
                                            variant='minimal'
                                            size="small"
                                            onClick={() => deleteModel(group.id, model.id)}
                                        />
                                    </div>
                                ))
                            }
                        </div>
                    </div>
                ))}

                {groups.length === 0 && (
                    <div className={styles.empty}>
                        <NonIdealState icon="error" title="没有找到匹配的模型" action={<Button icon="plus" intent="success" onClick={() => props.addModel?.()}>添加模型</Button>} />
                    </div>
                )}
            </div>
        </div>
    )
}
