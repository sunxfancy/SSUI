import React, { Component } from 'react';
import { Card, Elevation } from "@blueprintjs/core";
import { registerUIProvider, UIProvider } from '../UIProvider';
import './ImagePreview.css';

interface ImagePreviewProps {
    path: string;
}

interface ImagePreviewState {
    imagePath: string;
    loading: boolean;
    error: Error | null;
}

export class ImagePreview extends Component<ImagePreviewProps, ImagePreviewState> {
    constructor(props: ImagePreviewProps) {
        super(props);
        this.state = {
            imagePath: props.path,
            loading: true,
            error: null
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

    render() {
        const { imagePath, loading, error } = this.state;

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
                        />
                    )}
                </div>
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
