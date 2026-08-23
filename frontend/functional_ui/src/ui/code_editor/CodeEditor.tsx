import React, { Component } from "react";
import * as monaco from "monaco-editor";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import { Button, Intent } from "@blueprintjs/core";
import { ViewSwitcher } from "../common/ViewSwitcher";
import type { UIProvider } from "../UIProvider";
import "./CodeEditor.css";

// 使用本地打包的 Monaco worker，避免从 CDN 加载（桌面端离线可用）
(self as any).MonacoEnvironment = {
    getWorker: () => new EditorWorker(),
};

interface CodeEditorProps {
    path: string;
}

interface CodeEditorState {
    loading: boolean;
    loadError: Error | null;
    dirty: boolean;
    saving: boolean;
    saveError: Error | null;
    savedAt: Date | null;
}

function currentMonacoTheme(): string {
    return document.documentElement.dataset.theme === "dark" ? "vs-dark" : "vs";
}

export class CodeEditor extends Component<CodeEditorProps, CodeEditorState> {
    private containerRef: React.RefObject<HTMLDivElement>;
    private editor: monaco.editor.IStandaloneCodeEditor | null = null;
    private lastSavedContent = "";
    private themeObserver: MutationObserver | null = null;

    constructor(props: CodeEditorProps) {
        super(props);
        this.containerRef = React.createRef<HTMLDivElement>();
        this.state = {
            loading: true,
            loadError: null,
            dirty: false,
            saving: false,
            saveError: null,
            savedAt: null,
        };
    }

    componentDidMount() {
        this.createEditor();
        this.loadContent();
        this.watchTheme();
        window.addEventListener("keydown", this.handleKeyDown);
    }

    componentWillUnmount() {
        window.removeEventListener("keydown", this.handleKeyDown);
        this.themeObserver?.disconnect();
        this.editor?.dispose();
        this.editor = null;
    }

    createEditor = (): void => {
        if (!this.containerRef.current) {
            return;
        }
        this.editor = monaco.editor.create(this.containerRef.current, {
            value: "",
            language: "python",
            theme: currentMonacoTheme(),
            automaticLayout: true,
            fontSize: 14,
            tabSize: 4,
            insertSpaces: true,
            minimap: { enabled: true },
            scrollBeyondLastLine: false,
            wordWrap: "off",
            renderWhitespace: "selection",
            scrollbar: {
                verticalScrollbarSize: 10,
                horizontalScrollbarSize: 10,
            },
        });
        this.editor.onDidChangeModelContent(() => {
            const value = this.editor?.getValue() ?? "";
            this.setState({ dirty: value !== this.lastSavedContent });
        });
    };

    watchTheme = (): void => {
        this.themeObserver = new MutationObserver(() => {
            monaco.editor.setTheme(currentMonacoTheme());
        });
        this.themeObserver.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["data-theme"],
        });
    };

    loadContent = async (): Promise<void> => {
        try {
            const response = await fetch("/file?" + new URLSearchParams({
                path: this.props.path,
            }));
            if (!response.ok) {
                throw new Error(`Failed to load file (${response.status})`);
            }
            const content = await response.text();
            this.lastSavedContent = content;
            this.editor?.setValue(content);
            this.setState({ loading: false, loadError: null, dirty: false });
        } catch (error) {
            this.setState({
                loading: false,
                loadError: error instanceof Error ? error : new Error("Unknown error"),
            });
        }
    };

    handleKeyDown = (event: KeyboardEvent): void => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
            event.preventDefault();
            void this.handleSave();
        }
    };

    handleSave = async (): Promise<void> => {
        if (this.state.saving) {
            return;
        }
        const content = this.editor?.getValue() ?? "";
        this.setState({ saving: true, saveError: null });
        try {
            const response = await fetch("/files/upload_json", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    path: this.props.path,
                    content,
                }),
            });
            const data = await response.json().catch(() => null);
            if (!response.ok || (data && data.error)) {
                throw new Error((data && data.error) || `Save failed (${response.status})`);
            }
            this.lastSavedContent = content;
            this.setState({ saving: false, dirty: false, savedAt: new Date() });
        } catch (error) {
            this.setState({
                saving: false,
                saveError: error instanceof Error ? error : new Error("Unknown error"),
            });
        }
    };

    renderStatus = (): React.ReactNode => {
        const { loading, loadError, dirty, saving, saveError, savedAt } = this.state;
        if (loading) {
            return <span className="code-editor-status-muted">Loading...</span>;
        }
        if (loadError) {
            return <span className="code-editor-status-error">Error: {loadError.message}</span>;
        }
        if (saving) {
            return <span className="code-editor-status-muted">Saving...</span>;
        }
        if (saveError) {
            return <span className="code-editor-status-error">Save failed: {saveError.message}</span>;
        }
        if (dirty) {
            return <span className="code-editor-status-muted">Unsaved changes</span>;
        }
        if (savedAt) {
            return <span className="code-editor-status-ok">Saved at {savedAt.toLocaleTimeString()}</span>;
        }
        return <span className="code-editor-status-ok">Ready</span>;
    };

    render(): JSX.Element {
        const { path } = this.props;
        const { saving, loading, loadError } = this.state;

        return (
            <div className="code-editor-root">
                <div className="code-editor-header">
                    <div className="code-editor-header-info">
                        <h1>Code Editor</h1>
                        <p>Path: {path}</p>
                    </div>
                    <div className="code-editor-header-actions">
                        <ViewSwitcher path={path} currentView="code_editor" />
                        <Button
                            intent={Intent.PRIMARY}
                            icon="floppy-disk"
                            loading={saving}
                            disabled={loading || !!loadError}
                            onClick={() => void this.handleSave()}
                        >
                            Save
                        </Button>
                    </div>
                </div>
                <div className="code-editor-status">{this.renderStatus()}</div>
                <div className="code-editor-container" ref={this.containerRef} />
            </div>
        );
    }
}

const CodeEditorView: React.FC<CodeEditorProps> = ({ path }) => {
    return <CodeEditor path={path} />;
};

export class CodeEditorUIProvider implements UIProvider {
    getName(): string {
        return "code_editor";
    }

    getUI(path: string): JSX.Element {
        return <CodeEditorView path={path} />;
    }
}

export default CodeEditor;
