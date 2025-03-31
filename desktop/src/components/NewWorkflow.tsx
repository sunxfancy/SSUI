import React from 'react';
import { Dialog, Tabs, Tab, Button, Icon, Tooltip, InputGroup, IconName } from '@blueprintjs/core';
import { open } from '@tauri-apps/plugin-dialog';

import '@blueprintjs/core/lib/css/blueprint.css';
import '@blueprintjs/icons/lib/css/blueprint-icons.css';

interface WorkflowItem {
  id: string;
  title: string;
  description: string;
  icon: IconName;
}

interface NewWorkflowProps {
  isOpen: boolean;
  onClose: () => void;
  onWorkflowSelect: (workflowIds: string[], targetPath: string) => void;
}

interface NewWorkflowState {
  selectedWorkflows: string[];
  targetPath: string;
  activeTab: string;
}

export class NewWorkflow extends React.Component<NewWorkflowProps, NewWorkflowState> {
  // 官方工作流示例数据
  officialWorkflows: WorkflowItem[] = [
    { id: 'of1', title: '数据分析流程', description: '用于数据清洗、转换和分析的标准工作流', icon: 'chart' },
    { id: 'of2', title: '机器学习训练', description: '包含数据预处理、模型训练和评估的完整流程', icon: 'learning' },
    { id: 'of3', title: '自然语言处理', description: '文本分析和处理的标准工作流', icon: 'document' },
    { id: 'of4', title: '图像处理', description: '图像识别和处理的工作流', icon: 'media' },
    { id: 'of5', title: '数据可视化', description: '创建交互式数据可视化的工作流', icon: 'graph' },
    { id: 'of6', title: '自动化报告', description: '自动生成数据分析报告的工作流', icon: 'clipboard' },
    { id: 'of7', title: '预测分析', description: '使用历史数据进行预测的工作流', icon: 'timeline-line-chart' },
    { id: 'of8', title: '数据集成', description: '整合多源数据的工作流', icon: 'database' },
  ];

  // 社区工作流示例数据
  communityWorkflows: WorkflowItem[] = [
    { id: 'cm1', title: '社交媒体分析', description: '分析社交媒体数据的工作流', icon: 'social-media' },
    { id: 'cm2', title: '情感分析', description: '文本情感分析的工作流', icon: 'emoji' },
    { id: 'cm3', title: '异常检测', description: '识别数据中异常值的工作流', icon: 'warning-sign' },
    { id: 'cm4', title: '推荐系统', description: '构建个性化推荐系统的工作流', icon: 'star' },
    { id: 'cm5', title: '时间序列分析', description: '分析时间序列数据的工作流', icon: 'time' },
    { id: 'cm6', title: '网络爬虫', description: '网页数据抓取和处理的工作流', icon: 'generate' },
    { id: 'cm7', title: '地理空间分析', description: '地理数据分析和可视化的工作流', icon: 'map' },
    { id: 'cm8', title: '音频处理', description: '音频数据处理和分析的工作流', icon: 'music' },
  ];

  constructor(props: NewWorkflowProps) {
    super(props);
    this.state = {
      selectedWorkflows: [],
      targetPath: '',
      activeTab: 'official'
    };
  }

  handleWorkflowSelect = (id: string) => {
    this.setState(prevState => {
      if (prevState.selectedWorkflows.includes(id)) {
        return {
          selectedWorkflows: prevState.selectedWorkflows.filter(wfId => wfId !== id)
        };
      } else {
        return {
          selectedWorkflows: [...prevState.selectedWorkflows, id]
        };
      }
    });
  };

  handlePathSelect = async () => {
    const options = {
      directory: true,
      multiple: false
    };
    
    const result = await open(options);
    if (result) {
      this.setState({ targetPath: result as string });
    }
  };

  handleConfirm = () => {
    const { selectedWorkflows, targetPath } = this.state;
    if (selectedWorkflows.length > 0 && targetPath) {
      this.props.onWorkflowSelect(selectedWorkflows, targetPath);
      this.props.onClose();
    }
  };

  renderWorkflowGrid = (workflows: WorkflowItem[]) => {
    return (
      <div className="workflow-grid" style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(4, 1fr)', 
        gap: '16px',
        maxHeight: '400px',
        overflowY: 'auto',
        padding: '16px'
      }}>
        {workflows.map(workflow => (
          <Tooltip key={workflow.id} content={workflow.description} position="bottom">
            <div 
              className={`workflow-item ${this.state.selectedWorkflows.includes(workflow.id) ? 'selected' : ''}`}
              onClick={() => this.handleWorkflowSelect(workflow.id)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '16px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                cursor: 'pointer',
                position: 'relative',
                backgroundColor: this.state.selectedWorkflows.includes(workflow.id) ? '#e3f2fd' : 'white'
              }}
            >
              {this.state.selectedWorkflows.includes(workflow.id) && (
                <div style={{ position: 'absolute', top: '8px', right: '8px' }}>
                  <Icon icon="tick-circle" intent="success" />
                </div>
              )}
              <Icon icon={workflow.icon} size={32} />
              <div style={{ marginTop: '8px', textAlign: 'center' }}>{workflow.title}</div>
            </div>
          </Tooltip>
        ))}
      </div>
    );
  };

  render() {
    const { isOpen, onClose } = this.props;
    const { targetPath, activeTab } = this.state;

    return (
      <Dialog
        isOpen={isOpen}
        onClose={onClose}
        title="选择工作流"
        style={{ width: '800px' }}
      >
        <div style={{ padding: '0 20px 20px' }}>
          {/* 背景图 */}
          <div style={{ 
            height: '120px', 
            background: 'linear-gradient(135deg, #4568dc, #b06ab3)',
            borderRadius: '4px',
            marginTop: '20px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontSize: '24px',
            fontWeight: 'bold'
          }}>
            选择一个或多个工作流开始您的项目
          </div>

          {/* 标签页 */}
          <Tabs
            id="workflow-tabs"
            selectedTabId={activeTab}
            onChange={(newTabId) => this.setState({ activeTab: newTabId as string })}
          >
            <Tab id="official" title="官方工作流" panel={this.renderWorkflowGrid(this.officialWorkflows)} />
            <Tab id="community" title="社区工作流" panel={this.renderWorkflowGrid(this.communityWorkflows)} />
          </Tabs>

          {/* 路径选择 */}
          <div style={{ 
            marginTop: '20px', 
            display: 'flex', 
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ flex: 1, marginRight: '10px' }}>
              <InputGroup
                placeholder="选择工作流保存位置..."
                value={targetPath}
                fill
              />
            </div>
            <Button
              icon="folder-open"
              onClick={this.handlePathSelect}
            >
              选择文件夹
            </Button>
          </div>

          {/* 底部按钮 */}
          <div style={{ 
            marginTop: '20px', 
            display: 'flex', 
            justifyContent: 'flex-end' 
          }}>
            <Button onClick={onClose} style={{ marginRight: '10px' }}>取消</Button>
            <Button 
              intent="primary" 
              onClick={this.handleConfirm}
              disabled={this.state.selectedWorkflows.length === 0 || !targetPath}
            >
              确认
            </Button>
          </div>
        </div>
      </Dialog>
    );
  }
}

export default NewWorkflow;
