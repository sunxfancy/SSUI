import React, {Component, useEffect, useRef, useState} from 'react';
import {
    Button,
    Card,
    Collapse,
    Elevation,
    Icon,
    InputGroup,
    Menu,
    MenuItem,
    Popover,
    Position,
    Tag
} from "@blueprintjs/core";
import "@blueprintjs/core/lib/css/blueprint.css";
import "@blueprintjs/icons/lib/css/blueprint-icons.css";
import { IModelManagerProvider, ModelGroup } from '../../providers/IModelManagerProvider';
import { ModelManagerProvider } from '../../providers/ModelManagerProvider';
import styles from './style.module.css'

interface ModelState {
    groups: ModelGroup[];
    searchQuery: string;
    selectedTags: string[];
    availableTags: string[];
    showButtonText: boolean;
}

interface ModelManagerProps {
    provider?: IModelManagerProvider;
    addModel?: () => void;
}

export const ModelManager = (props) => {

    const [ groups, setGroups ] = useState([])
    const [ searchQuery, setSearchQuery ] = useState('')
    const [ selectedTags, setSelectedTags ] = useState([])
    const [ availableTags, setAvailableTags ] = useState([])
    const [ showButtonText, setShowButtonText ] = useState(true)

    const provider = useRef(props.provider || new ModelManagerProvider())
    const resizeObserver = useRef<ResizeObserver|null>(null)
    const containerRef = useRef()

    useEffect(() => {
        const init = async () => {
            if (typeof ResizeObserver !== 'undefined') {
                resizeObserver.current = new ResizeObserver(entries => {
                    for (const entry of entries) {
                        const width = entry.contentRect.width;
                        setShowButtonText(width > 400);
                    }
                });

                if (containerRef.current) {
                    resizeObserver.current.observe(containerRef.current);
                }
            }

            // 加载数据
            try {
                
                console.log(provider.current)
                const groups = await provider.current.getModelGroups();
                const availableTags = await provider.current.getAllTags();
                
                console.log(availableTags)

                setGroups(groups)
                setAvailableTags(availableTags)
            } catch (error) {
                console.error("加载模型数据失败:", error);
            }
        }

        init()


        return () => {
            // 组件卸载时清理observer
            if (resizeObserver.current) {
                resizeObserver.current.disconnect();
            }
        }
    }, []);


    const toggleTagSelection = (tag: string) => {
        if (selectedTags.includes(tag)) {
            setSelectedTags(selectedTags.filter(t => t !== tag))
        } else {
            setSelectedTags([...selectedTags, tag])
        }
        updateFilteredModels()
    };

    const updateFilteredModels = async () => {
        try {
            const filteredGroups = await provider.current.searchModels(searchQuery, selectedTags);
            setGroups(filteredGroups)
        } catch (error) {
            console.error("搜索模型失败:", error);
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

    const toggleGroupOpen = async (groupId: string) => {
        const group = groups.find(g => g.id === groupId);
        if (!group) return;

        const isOpen = !group.isOpen;
        const success = await provider.current.toggleGroupOpen(groupId, isOpen);

        if (success) {
            setGroups(groups.map(g =>
                g.id === groupId ? { ...g, isOpen: isOpen } : g
            ))
        }
    };

    const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchQuery(event.target.value)
        updateFilteredModels()
    };


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
            <div style={{ display: "flex", alignItems: "center" }}>
                <div style={{ flex: 1, marginLeft: "5px" }}>
                    <InputGroup
                        large
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
                                        updateFilteredModels()
                                    }}
                                /> : undefined
                        }
                    />

                </div>
                <div style={{ marginLeft: "10px" }}></div>
                <Popover
                    content={renderTagMenu()}
                    position={Position.BOTTOM_LEFT}
                >
                    <Button
                        icon="tag"
                        rightIcon="caret-down"
                        text={showButtonText ? (selectedTags.length > 0
                            ? `已选择 ${selectedTags.length} 个标签`
                            : "按标签筛选") : undefined}
                        title={selectedTags.length > 0
                            ? `已选择 ${selectedTags.length} 个标签`
                            : "按标签筛选"}
                    />
                </Popover>
                <div style={{ marginLeft: "2px", marginRight: "5px" }}>
                    <Button
                        text={showButtonText ? "添加模型" : undefined}
                        icon="plus"
                        intent="success"
                        variant='solid'
                        onClick={() => props.addModel?.()}
                        title="添加模型"
                    />
                </div>
            </div>

            <div style={{
                flex: 1,
                overflowY: "auto",
                border: "1px solid #e1e8ed",
                borderRadius: "3px"
            }}>
                {groups.map(group => (
                    <div key={group.id}>
                        <div
                            style={{
                                display: "flex",
                                alignItems: "center",
                                cursor: "pointer",
                                padding: "10px",
                                backgroundColor: "white",
                                position: "sticky",
                                top: 0,
                                zIndex: 10,
                                borderBottom: "1px solid #e1e8ed"
                            }}
                            onClick={() => toggleGroupOpen(group.id)}
                        >
                            <Icon
                                icon={group.isOpen ? "caret-down" : "caret-right"}
                                style={{ marginRight: "5px" }}
                            />
                            <h3 style={{ margin: "0" }}>{group.name}</h3>
                            <span style={{ marginLeft: "10px", color: "#888", fontSize: "0.9em" }}>
                  ({group.models.length} 个模型)
                </span>
                        </div>

                        <Collapse isOpen={group.isOpen}>
                            <div style={{ paddingLeft: "20px" }}>
                                {group.models.map(model => (
                                    <Card
                                        key={model.id}
                                        elevation={Elevation.ZERO}
                                        style={{ margin: "8px", padding: "8px" }}
                                    >
                                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                                            <div>
                                                <h4 style={{ margin: "0", marginBottom: "5px" }}>{model.name}</h4>
                                                <p style={{ margin: "0", color: "#666" }}>{model.description}</p>
                                            </div>

                                            <div style={{ display: "flex", alignItems: "center" }}>
                                                {model.tags.map(tag => (
                                                    <Tag
                                                        key={tag}
                                                        style={{ marginRight: "5px" }}
                                                        interactive
                                                        onClick={() => toggleTagSelection(tag)}
                                                    >
                                                        {tag}
                                                    </Tag>
                                                ))}
                                                <Button
                                                    icon="trash"
                                                    intent="danger"
                                                    variant='minimal'
                                                    onClick={() => deleteModel(group.id, model.id)}
                                                />
                                            </div>
                                        </div>
                                    </Card>
                                ))}
                            </div>
                        </Collapse>
                    </div>
                ))}

                {groups.length === 0 && (
                    <div style={{ textAlign: "center", padding: "20px" }}>
                        <p>没有找到匹配的模型</p>
                    </div>
                )}
            </div>
        </div>
    )
}
