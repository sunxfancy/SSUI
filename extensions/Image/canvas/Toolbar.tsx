import React from 'react';
import './Toolbar.css';

interface ToolbarProps {
    onToolSelect: (tool: string) => void;
}

const Toolbar: React.FC<ToolbarProps> = ({ onToolSelect }) => {
    const tools = [
        { id: 'move', icon: '✋', label: '移动' },
        { id: 'brush', icon: '🖌️', label: '画笔' },
        { id: 'eraser', icon: '🫓', label: '橡皮擦' },
        { id: 'shape', icon: '⬜', label: '选区' },
    ];

    return (
        <div className="toolbar">
            {tools.map((tool) => (
                <button
                    key={tool.id}
                    className="tool-button"
                    onClick={() => onToolSelect(tool.id)}
                    title={tool.label}
                >
                    <span className="tool-icon">{tool.icon}</span>
                </button>
            ))}
        </div>
    );
};

export default Toolbar; 