import React, { Component } from 'react';
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
import { IModelManagerProvider, ModelGroup, ModelItem } from '../providers/IModelManagerProvider';
import { MockModelManagerProvider } from '../stories/MockModelManagerProvider';
import { ModelManagerProvider } from '../providers/ModelManagerProvider';

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

export class ModelManager extends Component<ModelManagerProps, ModelState> {
  private containerRef: React.RefObject<HTMLDivElement>;
  private resizeObserver: ResizeObserver | null = null;
  private provider: IModelManagerProvider;
  
  constructor(props: ModelManagerProps) {
    super(props);
    
    // 使用提供的provider或默认使用模拟实现
    this.provider = props.provider || new ModelManagerProvider();
    
    this.state = {
      groups: [],
      searchQuery: "",
      selectedTags: [],
      availableTags: [],
      showButtonText: true
    };
    
    this.containerRef = React.createRef();
  }
  
  async componentDidMount() {
    // 创建ResizeObserver监听容器大小变化
    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
          const width = entry.contentRect.width;
          this.setState({ showButtonText: width > 400 });
        }
      });
      
      if (this.containerRef.current) {
        this.resizeObserver.observe(this.containerRef.current);
      }
    }
    
    // 加载数据
    try {
      const groups = await this.provider.getModelGroups();
      const availableTags = await this.provider.getAllTags();
      
      this.setState({
        groups,
        availableTags
      });
    } catch (error) {
      console.error("加载模型数据失败:", error);
    }
  }
  
  componentWillUnmount() {
    // 组件卸载时清理observer
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  }
  
  handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    this.setState({ searchQuery: event.target.value }, this.updateFilteredModels);
  };
  
  toggleGroupOpen = async (groupId: string) => {
    const group = this.state.groups.find(g => g.id === groupId);
    if (!group) return;
    
    const isOpen = !group.isOpen;
    const success = await this.provider.toggleGroupOpen(groupId, isOpen);
    
    if (success) {
      this.setState(prevState => ({
        groups: prevState.groups.map(group => 
          group.id === groupId ? { ...group, isOpen: isOpen } : group
        )
      }));
    }
  };
  
  deleteModel = async (groupId: string, modelId: string) => {
    const success = await this.provider.deleteModel(groupId, modelId);
    
    if (success) {
      this.setState(prevState => ({
        groups: prevState.groups.map(group => 
          group.id === groupId 
            ? { ...group, models: group.models.filter(model => model.id !== modelId) }
            : group
        ).filter(group => group.models.length > 0) // 移除空组
      }));
    }
  };
  
  toggleTagSelection = (tag: string) => {
    this.setState(prevState => {
      const newSelectedTags = prevState.selectedTags.includes(tag)
        ? prevState.selectedTags.filter(t => t !== tag)
        : [...prevState.selectedTags, tag];
        
      return {
        selectedTags: newSelectedTags
      };
    }, this.updateFilteredModels);
  };
  
  updateFilteredModels = async () => {
    const { searchQuery, selectedTags } = this.state;
    
    try {
      const filteredGroups = await this.provider.searchModels(searchQuery, selectedTags);
      this.setState({ groups: filteredGroups });
    } catch (error) {
      console.error("搜索模型失败:", error);
    }
  };
  
  renderTagMenu = () => {
    const { availableTags, selectedTags } = this.state;
    
    return (
      <Menu>
        {availableTags.map(tag => (
          <MenuItem 
            key={tag}
            text={tag}
            icon={selectedTags.includes(tag) ? "tick" : "blank"}
            onClick={() => this.toggleTagSelection(tag)}
          />
        ))}
      </Menu>
    );
  };
  
  render() {
    const { searchQuery, showButtonText, groups } = this.state;
    
    return (
      <div ref={this.containerRef}>
        <div style={{ display: "flex", alignItems: "center" }}>
          <div style={{ flex: 1, marginLeft: "5px" }}>
            <InputGroup
              large
              leftIcon="search"
              placeholder="搜索模型名称或描述..."
              value={searchQuery}
              onChange={this.handleSearchChange}
              rightElement={
                searchQuery ? 
                <Button 
                  icon="cross" 
                  variant='minimal' 
                  onClick={() => this.setState({ searchQuery: "" }, this.updateFilteredModels)} 
                /> : undefined
              }
            />
            
          </div>
          <div style={{ marginLeft: "10px" }}></div>
          <Popover
            content={this.renderTagMenu()}
            position={Position.BOTTOM_LEFT}
          >
            <Button 
              icon="tag" 
              rightIcon="caret-down"
              text={showButtonText ? (this.state.selectedTags.length > 0 
                ? `已选择 ${this.state.selectedTags.length} 个标签` 
                : "按标签筛选") : undefined}
              title={this.state.selectedTags.length > 0 
                ? `已选择 ${this.state.selectedTags.length} 个标签` 
                : "按标签筛选"}
            />
          </Popover>
          <div style={{ marginLeft: "2px", marginRight: "5px" }}>
            <Button
              text={showButtonText ? "添加模型" : undefined}
              icon="plus"
              intent="success"
              variant='solid'
              onClick={() => this.props.addModel?.()}
              title="添加模型"
            />
          </div>
        </div>
        
        <div style={{ 
          height: "calc(100vh - 120px)", 
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
                onClick={() => this.toggleGroupOpen(group.id)}
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
                              onClick={() => this.toggleTagSelection(tag)}
                            >
                              {tag}
                            </Tag>
                          ))}
                          <Button 
                            icon="trash" 
                            intent="danger" 
                            variant='minimal'
                            onClick={() => this.deleteModel(group.id, model.id)}
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
    );
  }
}

export default ModelManager;
