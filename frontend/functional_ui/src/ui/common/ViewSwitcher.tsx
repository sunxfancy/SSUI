import React from "react";
import { Button, IconName } from "@blueprintjs/core";
import "./ViewSwitcher.css";

export interface ViewOption {
    view: string;
    label: string;
    icon: IconName;
}

/**
 * 每种文件类型可用的视图（按顺序展示，当前视图高亮，点击可切换）。
 * - .py：Functional UI（函数调用）↔ Code Editor（代码编辑）
 * - .flow：Flow（流程图）↔ Functional UI
 */
const VIEW_OPTIONS: Record<string, ViewOption[]> = {
    py: [
        { view: "functional", label: "Functional UI", icon: "function" },
        { view: "code_editor", label: "Code Editor", icon: "code" },
    ],
    flow: [
        { view: "workflow", label: "Flow", icon: "graph" },
        { view: "functional", label: "Functional UI", icon: "function" },
    ],
};

interface ViewSwitcherProps {
    path: string;
    currentView: string;
}

function getExtension(path: string): string {
    const basename = path.split(/[\\/]/).pop() ?? "";
    const match = basename.match(/\.([^.]+)$/);
    return match ? match[1].toLowerCase() : "";
}

function switchToView(path: string, view: string): void {
    const base = window.location.origin + window.location.pathname;
    window.location.href = `${base}?view=${view}&path=${encodeURIComponent(path)}`;
}

export const ViewSwitcher: React.FC<ViewSwitcherProps> = ({ path, currentView }) => {
    const options = VIEW_OPTIONS[getExtension(path)];
    if (!options) {
        return null;
    }

    return (
        <div className="view-switcher">
            {options.map(option => (
                <Button
                    key={option.view}
                    className="view-switcher-button"
                    icon={option.icon}
                    active={option.view === currentView}
                    onClick={() => {
                        if (option.view !== currentView) {
                            switchToView(path, option.view);
                        }
                    }}
                >
                    {option.label}
                </Button>
            ))}
        </div>
    );
};

export default ViewSwitcher;
