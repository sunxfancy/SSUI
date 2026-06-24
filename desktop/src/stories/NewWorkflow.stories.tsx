import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { Button } from '@blueprintjs/core';
import NewWorkflow from '../components/NewWorkflow';

const NewWorkflowWrapper = ({ initiallyOpen = true }: { initiallyOpen?: boolean }) => {
  const [isOpen, setIsOpen] = useState(initiallyOpen);

  return (
    <>
      {!isOpen && (
        <Button intent="primary" onClick={() => setIsOpen(true)}>
          打开新建工作流
        </Button>
      )}
      <NewWorkflow
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        onWorkflowSelect={(workflowIds, targetPath) => {
          console.log('选择工作流:', workflowIds, '保存路径:', targetPath);
          setIsOpen(false);
        }}
      />
    </>
  );
};

const meta: Meta<typeof NewWorkflowWrapper> = {
  title: 'Components/NewWorkflow',
  component: NewWorkflowWrapper,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof NewWorkflowWrapper>;

export const Default: Story = {
  args: {
    initiallyOpen: true,
  },
};

export const 关闭状态: Story = {
  args: {
    initiallyOpen: false,
  },
};
