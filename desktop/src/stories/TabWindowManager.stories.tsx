import type { Meta, StoryObj } from '@storybook/react';
import { TabWindowManager } from '../components/TabWindowManager';
import { useRef } from 'react';

const WithImperativeCall = () => {
    const ref = useRef<TabWindowManager>(null);
    let count = 1;
  
    const handleCall = () => {
      if (ref.current) {
        // 调用组件暴露的 API 函数
        let name = "file" + count;
        count++;
        ref.current.openFile(name, "");
      }
    };
  
    return (
      <div style={{height: "100vh"}}>
        <button style={{position: "absolute", bottom: "10px", right: "10px", zIndex: 1000}} onClick={handleCall}>添加一个新标签</button>
        <TabWindowManager ref={ref} />
      </div>
    );
  };
  

const meta: Meta<typeof WithImperativeCall> = {
  component: WithImperativeCall,
  parameters: {
    layout: 'fullscreen'
  }
};

export default meta;
type Story = StoryObj<typeof WithImperativeCall>;

export const Primary: Story = {
  args: {},
}; 