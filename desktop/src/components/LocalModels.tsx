import React, { Component } from 'react';
import { 
  Button, 
  Card, 
  Elevation, 
  FormGroup, 
  InputGroup,
  Icon,
  Divider,
  NonIdealState,
  H4,
  Tag,
  Intent
} from '@blueprintjs/core';
import { Model, ModelsProvider, WatchedDirectory } from '../providers/IModelsProvider';

interface LocalModelsProps {
  modelsProvider: ModelsProvider;
  onModelAdd?: (modelPath: string) => void;
}

interface LocalModelsState {
  selectedDirectory: string;
  scannedModels: Model[];
  isScanning: boolean;
  watchedDirectories: WatchedDirectory[];
  isDraggingOverModels: boolean;
  isDraggingOverWatched: boolean;
}

export class LocalModels extends Component<LocalModelsProps, LocalModelsState> {
  constructor(props: LocalModelsProps) {
    super(props);
    this.state = {
      selectedDirectory: '',
      scannedModels: [],
      isScanning: false,
      watchedDirectories: [],
      isDraggingOverModels: false,
      isDraggingOverWatched: false
    };
  }

  async componentDidMount() {
    // 加载已保存的监听目录
    try {
      const watchedDirectories = await this.props.modelsProvider.getWatchedDirectories();
      this.setState({ watchedDirectories });
    } catch (error) {
      console.error("加载监听目录失败:", error);
    }
  }

  // 选择目录
  handleSelectDirectory = async () => {
    try {
      const selectedDir = await this.props.modelsProvider.selectDirectory();
      this.setState({ selectedDirectory: selectedDir });
    } catch (error) {
      console.error("选择目录失败:", error);
    }
  }

  // 扫描选中的目录
  handleScanDirectory = async () => {
    const { selectedDirectory } = this.state;
    if (!selectedDirectory) return;
    
    this.setState({ 
      isScanning: true,
      scannedModels: [] // 清空之前的扫描结果
    });
    
    try {
      // 使用回调函数实时更新扫描到的模型
      const models = await this.props.modelsProvider.scanDirectory(
        selectedDirectory,
        (model) => {
          // 每当找到一个模型，就更新状态
          this.setState(prevState => ({
            isScanning: false,
            scannedModels: [...prevState.scannedModels, model]
          }));
        }
      );
      
      console.log("扫描完成，共找到模型: ", models.length);
      this.setState({ isScanning: false });
    } catch (error) {
      console.error("扫描目录失败:", error);
      this.setState({ isScanning: false });
    }
  }

  // 添加单个模型
  handleAddModel = async (model: Model) => {
    try {
      const success = await this.props.modelsProvider.addModel(model.path);
      if (success && this.props.onModelAdd) {
        this.props.onModelAdd(model.path);
      }
    } catch (error) {
      console.error("添加模型失败:", error);
    }
  }

  // 添加监听目录
  handleAddWatchedDirectory = async () => {
    const { selectedDirectory } = this.state;
    if (!selectedDirectory) return;
    
    try {
      const newWatchedDir = await this.props.modelsProvider.addWatchedDirectory(selectedDirectory);
      this.setState(prevState => ({
        watchedDirectories: [...prevState.watchedDirectories, newWatchedDir],
        selectedDirectory: ''
      }));
    } catch (error) {
      console.error("添加监听目录失败:", error);
    }
  }

  // 移除监听目录
  handleRemoveWatchedDirectory = async (id: string) => {
    try {
      const success = await this.props.modelsProvider.removeWatchedDirectory(id);
      if (success) {
        this.setState(prevState => ({
          watchedDirectories: prevState.watchedDirectories.filter(dir => dir.id !== id)
        }));
      }
    } catch (error) {
      console.error("移除监听目录失败:", error);
    }
  }

  // 处理拖拽文件到模型区域
  handleModelsDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }
  
  handleModelsDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    this.setState({ isDraggingOverModels: true });
  }
  
  handleModelsDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    this.setState({ isDraggingOverModels: false });
  }
  
  handleModelsDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    this.setState({ isDraggingOverModels: false });
    
    try {
      const path = await this.props.modelsProvider.getDroppedFilePath(e);
      this.setState({ selectedDirectory: path }, () => {
        // 自动开始扫描
        this.handleScanDirectory();
      });
    } catch (error) {
      console.error("处理拖放文件失败:", error);
    }
  }
  
  // 处理拖拽文件到监听目录区域
  handleWatchedDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }
  
  handleWatchedDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    this.setState({ isDraggingOverWatched: true });
  }
  
  handleWatchedDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    this.setState({ isDraggingOverWatched: false });
  }
  
  handleWatchedDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    this.setState({ isDraggingOverWatched: false });
    
    try {
      const path = await this.props.modelsProvider.getDroppedFilePath(e);
      
      // 直接添加为监听目录
      const newWatchedDir = await this.props.modelsProvider.addWatchedDirectory(path);
      this.setState(prevState => ({
        watchedDirectories: [...prevState.watchedDirectories, newWatchedDir]
      }));
    } catch (error) {
      console.error("处理拖放文件失败:", error);
    }
  }

  renderModelsList() {
    const { scannedModels, isScanning, isDraggingOverModels } = this.state;
    
    return (
      <div 
        style={{ position: 'relative' }}
        onDragOver={this.handleModelsDragOver}
        onDragEnter={this.handleModelsDragEnter}
        onDragLeave={this.handleModelsDragLeave}
        onDrop={this.handleModelsDrop}
      >
        <H4>扫描结果 <small style={{ fontWeight: 'normal', color: '#888' }}>（可拖拽文件或目录到此处进行扫描）</small></H4>
        
        {isScanning ? (
          <NonIdealState
            icon="search"
            title="正在扫描目录..."
            description="请稍候，正在扫描目录中的模型文件。"
          />
        ) : scannedModels.length === 0 ? (
          <NonIdealState
            icon="folder-open"
            title="没有扫描到模型"
            description="选择一个目录并点击扫描按钮来查找模型，或直接拖拽目录到此处。"
          />
        ) : (
          scannedModels.map(model => (
            <Card key={model.id} elevation={Elevation.ONE} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h4 style={{ margin: 0 }}>{model.name}</h4>
                  <p style={{ margin: '5px 0', fontSize: '0.9em', color: '#555' }}>{model.path}</p>
                  <div>
                    <Tag intent="primary" minimal style={{ marginRight: 5 }}>{model.type}</Tag>
                    <Tag intent="success" minimal>{model.size}</Tag>
                  </div>
                </div>
                <Button 
                  icon="plus" 
                  intent={Intent.SUCCESS} 
                  onClick={() => this.handleAddModel(model)}
                  minimal
                >
                  添加
                </Button>
              </div>
            </Card>
          ))
        )}
        
        {/* 拖拽悬停遮罩层 */}
        {isDraggingOverModels && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(16, 107, 163, 0.2)',
            border: '2px dashed #106ba3',
            borderRadius: '3px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10
          }}>
            <div style={{
              backgroundColor: 'rgba(255, 255, 255, 0.9)',
              padding: '15px 20px',
              borderRadius: '3px',
              boxShadow: '0 0 10px rgba(0, 0, 0, 0.1)'
            }}>
              <h3 style={{ margin: 0, color: '#106ba3' }}>
                <Icon icon="cloud-upload" style={{ marginRight: 10 }} />
                松开鼠标扫描此目录中的模型
              </h3>
            </div>
          </div>
        )}
      </div>
    );
  }

  renderWatchedDirectories() {
    const { watchedDirectories, isDraggingOverWatched } = this.state;
    
    return (
      <div 
        style={{ position: 'relative' }}
        onDragOver={this.handleWatchedDragOver}
        onDragEnter={this.handleWatchedDragEnter}
        onDragLeave={this.handleWatchedDragLeave}
        onDrop={this.handleWatchedDrop}
      >
        <H4>监听目录 <small style={{ fontWeight: 'normal', color: '#888' }}>（可拖拽目录到此处添加为监听目录）</small></H4>
        
        {watchedDirectories.length === 0 ? (
          <NonIdealState
            icon="eye-open"
            title="没有监听目录"
            description="添加监听目录后，应用启动时将自动扫描这些目录中的模型。您可以直接拖拽目录到此处添加。"
          />
        ) : (
          watchedDirectories.map(dir => (
            <Card key={dir.id} elevation={Elevation.ONE} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <p style={{ margin: 0 }}>{dir.path}</p>
                </div>
                <Button 
                  icon="trash" 
                  intent={Intent.DANGER} 
                  onClick={() => this.handleRemoveWatchedDirectory(dir.id)}
                  minimal
                >
                  移除
                </Button>
              </div>
            </Card>
          ))
        )}
        
        {/* 拖拽悬停遮罩层 */}
        {isDraggingOverWatched && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 128, 0, 0.2)',
            border: '2px dashed #0a6640',
            borderRadius: '3px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10
          }}>
            <div style={{
              backgroundColor: 'rgba(255, 255, 255, 0.9)',
              padding: '15px 20px',
              borderRadius: '3px',
              boxShadow: '0 0 10px rgba(0, 0, 0, 0.1)'
            }}>
              <h3 style={{ margin: 0, color: '#0a6640' }}>
                <Icon icon="eye-open" style={{ marginRight: 10 }} />
                松开鼠标添加为监听目录
              </h3>
            </div>
          </div>
        )}
      </div>
    );
  }

  render() {
    const { selectedDirectory } = this.state;
    
    return (
      <div>
          <FormGroup
            helperText="选择包含模型文件的本地目录"
          >
            <div style={{ display: 'flex', gap: 10 }}>
              <div style={{ flex: 1 }}>
              <InputGroup
                placeholder="选择目录..."
                value={selectedDirectory}
                rightElement={
                  <Button 
                    icon="folder-open" 
                    variant="minimal"
                    onClick={this.handleSelectDirectory} 
                  />
                }
              />
              </div>
              <Button 
                icon="search" 
                intent={Intent.PRIMARY} 
                onClick={this.handleScanDirectory}
                disabled={!selectedDirectory}
              >
                扫描目录
              </Button>
              <Button 
                icon="eye-open" 
                intent={Intent.SUCCESS} 
                onClick={this.handleAddWatchedDirectory}
                disabled={!selectedDirectory}
              >
                添加监听
              </Button>
            </div>
          </FormGroup>
        
        {this.renderModelsList()}
        
        <Divider style={{ margin: '20px 0' }} />
        
        {this.renderWatchedDirectories()}
      </div>
    );
  }
}

export default LocalModels;
