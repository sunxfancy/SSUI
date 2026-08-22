import React, { Component } from 'react';
import { Card, Elevation } from "@blueprintjs/core";
import { ContextMenu, ContextMenuItem } from 'ssui_components';
import { registerUIProvider, UIProvider } from '../UIProvider';
import './ImagePreview.css';

interface ImagePreviewProps {
    path: string;
}

interface ImagePreviewState {
    imagePath: string;
    loading: boolean;
    error: Error | null;
    contextMenu: { x: number; y: number } | null;
}

export class ImagePreview extends Component<ImagePreviewProps, ImagePreviewState> {
    constructor(props: ImagePreviewProps) {
        super(props);
        this.state = {
            imagePath: props.path,
            loading: true,
            error: null,
            contextMenu: null
        };
    }

    componentDidMount() {
        this.loadImage();
    }

    componentDidUpdate(prevProps: ImagePreviewProps) {
        if (prevProps.path !== this.props.path) {
            this.setState({ imagePath: this.props.path }, () => {
                this.loadImage();
            });
        }
    }

    loadImage = () => {
        this.setState({ loading: true, error: null });
        
        // 创建一个新的Image对象来预加载图片
        const img = new Image();
        img.onload = () => {
            this.setState({ loading: false });
        };
        
        img.onerror = () => {
            this.setState({ 
                loading: false, 
                error: new Error('Failed to load image') 
            });
        };
        
        img.src = '/file?path=' + this.state.imagePath;
    }

    handleContextMenu = (e: React.MouseEvent) => {
        e.preventDefault();
        this.setState({
            contextMenu: { x: e.clientX, y: e.clientY }
        });
    }

    closeContextMenu = () => {
        this.setState({ contextMenu: null });
    }

    copyImageUrl = async () => {
        const url = '/file?path=' + this.state.imagePath;
        try {
            await navigator.clipboard.writeText(url);
        } catch (error) {
            console.error('复制图片地址失败:', error);
        }
    }

    openImageInNewWindow = () => {
        window.open('/file?path=' + this.state.imagePath, '_blank', 'noopener');
    }

    render() {
        const { imagePath, loading, error, contextMenu } = this.state;
        const contextItems: ContextMenuItem[] = [
            { label: '复制图片地址', icon: 'clipboard', onClick: this.copyImageUrl },
            { label: '在新窗口打开', icon: 'document-open', onClick: this.openImageInNewWindow }
        ];

        return (
            <div className="image-preview">
                <div className="image-preview-card">
                    {loading ? (
                        <div className="loading">Loading image...</div>
                    ) : error ? (
                        <div className="error">Error: {error.message}</div>
                    ) : (
                        <img 
                            src={'/file?path=' + imagePath} 
                            alt="Preview" 
                            className="preview-image"
                            onContextMenu={this.handleContextMenu}
                        />
                    )}
                </div>
                {contextMenu && (
                    <ContextMenu
                        x={contextMenu.x}
                        y={contextMenu.y}
                        items={contextItems}
                        onClose={this.closeContextMenu}
                    />
                )}
            </div>
        );
    }
}

export class ImagePreviewProvider implements UIProvider {
    getName(): string {
        return 'image_preview';
    }

    getUI(path: string): JSX.Element {
        return <ImagePreview path={path} />;
    }
}
