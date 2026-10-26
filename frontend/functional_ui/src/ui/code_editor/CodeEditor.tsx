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
    private version: string | null = null;
    private generation = 0;
    private savePending = false;
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
        window.addEventListener("beforeunload", this.handleBeforeUnload);
        window.addEventListener("keydown", this.handleKeyDown);
    }

    componentDidUpdate(previous: CodeEditorProps) {
        if (previous.path !== this.props.path) void this.loadContent();
    }

    componentWillUnmount() {
        this.generation++;
        window.removeEventListener("beforeunload", this.handleBeforeUnload);
        window.removeEventListener("keydown", this.handleKeyDown);
        this.themeObserver?.disconnect();
        const model = this.editor?.getModel();
        this.editor?.dispose();
        model?.dispose();
        this.editor = null;
    }

    createEditor = (): void => {
        if (!this.containerRef.current) {
            return;
        }
        this.editor = monaco.editor.create(this.containerRef.current, {
            value: "",
            readOnly: true,
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
        const generation = ++this.generation;
        this.version = null;
        this.editor?.updateOptions({ readOnly: true });
        this.setState({ loading: true, loadError: null, dirty: false, savedAt: null, saveError: null });
        try {
            const response = await fetch("/file/text?" + new URLSearchParams({
                path: this.props.path,
            }));
            if (!response.ok) {
                throw new Error(`Failed to load file (${response.status})`);
            }
            const snapshot = await response.json();
            if (typeof snapshot?.content !== "string" || typeof snapshot?.version !== "string") {
                throw new Error("Invalid file snapshot");
            }
            const content = snapshot.content;
            if (generation !== this.generation) return;
            this.version = snapshot.version;
            this.editor?.updateOptions({ readOnly: false });
            this.lastSavedContent = content;
            this.editor?.setValue(content);
            this.setState({ loading: false, loadError: null, dirty: false });
        } catch (error) {
            if (generation !== this.generation) return;
            this.setState({
                loading: false,
                loadError: error instanceof Error ? error : new Error("Unknown error"),
            });
        }
    };

    handleBeforeUnload = (event: BeforeUnloadEvent): void => {
        if (this.state.dirty || this.savePending) {
            event.preventDefault();
            event.returnValue = "";
        }
    };

    handleKeyDown = (event: KeyboardEvent): void => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
            event.preventDefault();
            void this.handleSave();
        }
    };

    handleSave = async (): Promise<void> => {
        if (this.savePending || this.state.loading || this.state.loadError || !this.editor || !this.version) {
            return;
        }
        const generation = this.generation;
        this.savePending = true;
        const content = this.editor.getValue();
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
                    expected_version: this.version,
                }),
            });
            const data = await response.json().catch(() => null);
            if (response.status === 409) {
                throw new Error("文件已被其他窗口或程序修改。本地修改已保留，请先备份，再重新加载磁盘版本并合并修改。");
            }
            if (!response.ok || (data && data.error)) {
                throw new Error((data && (data.error || data.detail)) || `Save failed (${response.status})`);
            }
            if (generation !== this.generation) return;
            if (data?.success !== true || typeof data?.version !== "string") throw new Error("Invalid save response");
            this.version = data.version;
            this.lastSavedContent = content;
            this.setState({ dirty: this.editor?.getValue() !== content, savedAt: new Date() });
        } catch (error) {
            if (generation !== this.generation) return;
            this.setState({
                saving: false,
                saveError: error instanceof Error ? error : new Error("Unknown error"),
            });
        } finally {
            this.savePending = false;
            if (this.editor) this.setState({ saving: false });
        }
    };

    reloadFromDisk = (): void => {
        if (this.savePending) return;
        if (this.state.dirty && !window.confirm("重新加载将丢弃本地未保存修改。请先备份需要保留的内容。继续吗？")) return;
        void this.loadContent();
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
                        <Button disabled={loading || saving} onClick={this.reloadFromDisk}>Reload from disk</Button>
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
