import React from 'react';
import { Dialog, Tabs, Tab, Button, Icon, Tooltip, InputGroup, IconName } from '@blueprintjs/core';
import { open } from '@tauri-apps/plugin-dialog';
import { readTextFile, copyFile } from '@tauri-apps/plugin-fs';
import { resolveResource } from '@tauri-apps/api/path';

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
  communityWorkflows: WorkflowItem[];
  officialWorkflows: WorkflowItem[];
}

export class NewWorkflow extends React.Component<NewWorkflowProps, NewWorkflowState> {

  constructor(props: NewWorkflowProps) {
    super(props);
    this.state = {
      selectedWorkflows: [],
      targetPath: '',
      activeTab: 'official',
      communityWorkflows: [],
      officialWorkflows: [],
    };
  }

  componentDidMount(): void {
    this.loadWorkflows();
  }

  loadWorkflows = async () => {
    try {
      const resoucePath = await resolveResource('workflow/data.json');
      const jsonObj = JSON.parse(await readTextFile(resoucePath));
      this.setState({
        officialWorkflows: jsonObj.officialWorkflows || [],
        communityWorkflows: jsonObj.communityWorkflows || [],
      })
    } catch (error) {
      console.error('读取工作流文件时出错:', error);
    }
  };

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

  handleConfirm = async () => {
    const { selectedWorkflows, targetPath } = this.state;
    if (selectedWorkflows.length > 0 && targetPath) {

      const basicFiles = [
        'example.canvas',
        'ssproject.yaml', 
        'workflow-flux.py',
        'workflow-sd1.py',
        'workflow-sdxl.py'
      ];
      
      const currentDir = await resolveResource('.');
      const projectRoot = currentDir.split('/desktop')[0]; 
      const sourceDir = `${projectRoot}/examples/basic`;
      
      for (const file of basicFiles) {
        const sourcePath = `${sourceDir}/${file}`;
        const destPath = `${targetPath}/${file}`;
        await copyFile(sourcePath, destPath);
      }
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
            <Tab id="official" title="官方工作流" panel={this.renderWorkflowGrid(this.state.officialWorkflows)} />
            <Tab id="community" title="社区工作流" panel={this.renderWorkflowGrid(this.state.communityWorkflows)} />
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
