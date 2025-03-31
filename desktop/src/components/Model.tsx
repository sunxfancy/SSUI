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

interface ModelItem {
  id: string;
  name: string;
  description: string;
  tags: string[];
}

interface ModelGroup {
  id: string;
  name: string;
  models: ModelItem[];
  isOpen: boolean;
}

interface ModelState {
  groups: ModelGroup[];
  searchQuery: string;
  selectedTags: string[];
  availableTags: string[];
  showButtonText: boolean;
}

interface ModelManagerProps {
  addModel?: () => void;
}

export class ModelManager extends Component<ModelManagerProps, ModelState> {
  private containerRef: React.RefObject<HTMLDivElement>;
  private resizeObserver: ResizeObserver | null = null;
  
  constructor(props: ModelManagerProps) {
    super(props);
    
    // 示例数据 - 按组分类
    const sampleGroups: ModelGroup[] = [
      { 
        id: "checkpoint", 
        name: "Checkpoint", 
        isOpen: false,
        models: [
          { id: "sd1-v1-5", name: "Stable Diffusion 1.5", description: "基础SD1.5模型", tags: ["sd1"] },
          { id: "sd2-v2-1", name: "Stable Diffusion 2.1", description: "改进版SD2.1模型", tags: ["sd2"] },
          { id: "sdxl-base", name: "SDXL Base", description: "大规模SDXL基础模型", tags: ["sdxl"] },
        ] 
      },
      { 
        id: "vae", 
        name: "VAE", 
        isOpen: false,
        models: [
          { id: "vae-ft-mse", name: "VAE FT-MSE", description: "优化的VAE编码器", tags: ["sd1", "sd2"] },
          { id: "vae-sdxl", name: "VAE SDXL", description: "SDXL专用VAE", tags: ["sdxl"] },
        ] 
      },
      { 
        id: "lora", 
        name: "LoRA", 
        isOpen: false,
        models: [
          { id: "lora-anime", name: "Anime Style", description: "动漫风格LoRA", tags: ["sd1", "sd2"] },
          { id: "lora-realistic", name: "Realistic", description: "写实风格LoRA", tags: ["sd1", "sdxl"] },
          { id: "lora-flux", name: "Flux Style", description: "Flux引擎专用LoRA", tags: ["flux1"] },
        ] 
      },
      { 
        id: "clip", 
        name: "CLIP", 
        isOpen: false,
        models: [
          { id: "clip-vit-large", name: "ViT-L/14", description: "大型CLIP视觉编码器", tags: ["sd2", "sdxl"] },
          { id: "clip-vit-base", name: "ViT-B/32", description: "基础CLIP视觉编码器", tags: ["sd1"] },
        ] 
      },
      { 
        id: "controlnet", 
        name: "ControlNet", 
        isOpen: false,
        models: [
          { id: "cn-canny", name: "Canny Edge", description: "边缘检测控制网络", tags: ["sd1", "sd2"] },
          { id: "cn-depth", name: "Depth", description: "深度图控制网络", tags: ["sd1", "sdxl"] },
          { id: "cn-pose", name: "Pose", description: "姿势控制网络", tags: ["sd2", "flux1"] },
        ] 
      },
    ];
    
    // 从所有模型中提取标签
    const allTags = Array.from(new Set(sampleGroups.flatMap(group => 
      group.models.flatMap(model => model.tags)
    )));
    
    this.state = {
      groups: sampleGroups,
      searchQuery: "",
      selectedTags: [],
      availableTags: allTags,
      showButtonText: true
    };
    
    this.containerRef = React.createRef();
  }
  
  componentDidMount() {
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
  }
  
  componentWillUnmount() {
    // 组件卸载时清理observer
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  }
  
  handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    this.setState({ searchQuery: event.target.value });
  };
  
  toggleGroupOpen = (groupId: string) => {
    this.setState(prevState => ({
      groups: prevState.groups.map(group => 
        group.id === groupId ? { ...group, isOpen: !group.isOpen } : group
      )
    }));
  };
  
  deleteModel = (groupId: string, modelId: string) => {
    this.setState(prevState => ({
      groups: prevState.groups.map(group => 
        group.id === groupId 
          ? { ...group, models: group.models.filter(model => model.id !== modelId) }
          : group
      )
    }));
  };
  
  toggleTagSelection = (tag: string) => {
    this.setState(prevState => {
      if (prevState.selectedTags.includes(tag)) {
        return {
          selectedTags: prevState.selectedTags.filter(t => t !== tag)
        };
      } else {
        return {
          selectedTags: [...prevState.selectedTags, tag]
        };
      }
    });
  };
  
  getFilteredGroups = () => {
    const { groups, searchQuery, selectedTags } = this.state;
    
    return groups.map(group => {
      // 过滤每个组中的模型
      const filteredModels = group.models.filter(model => {
        // 搜索过滤
        const matchesSearch = 
          model.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
          model.description.toLowerCase().includes(searchQuery.toLowerCase());
        
        // 标签过滤
        const matchesTags = 
          selectedTags.length === 0 || 
          selectedTags.some(tag => model.tags.includes(tag));
        
        return matchesSearch && matchesTags;
      });
      
      // 返回带有过滤后模型的组
      return {
        ...group,
        models: filteredModels
      };
    }).filter(group => group.models.length > 0); // 只保留有模型的组
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
    const { searchQuery, showButtonText } = this.state;
    const filteredGroups = this.getFilteredGroups();
    
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
                  onClick={() => this.setState({ searchQuery: "" })} 
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
          {filteredGroups.map(group => (
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
          
          {filteredGroups.length === 0 && (
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
