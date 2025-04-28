import { IComponent } from '../IComponent';

type ImageUploaderState = {
    image: string;
    uploading: boolean;
    error: string | null;
}

export class ImageUploader extends IComponent<{ script_path: string }, ImageUploaderState> {
    constructor(props: { script_path: string }) {
        super(props);
        this.state = { 
            image: '',
            uploading: false,
            error: null
        };
    }

    override onExecute() {
        return { 'image': this.state.image };
    }

    handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        this.setState({ uploading: true, error: null });

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`/files/upload?script_path=${this.props.script_path}`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            if (data.success) {
                this.setState({ 
                    image: data.path,
                    uploading: false
                });
            } else {
                this.setState({ 
                    error: data.error || '上传失败',
                    uploading: false
                });
            }
        } catch (error) {
            this.setState({ 
                error: '上传过程中发生错误',
                uploading: false
            });
            console.error('上传错误:', error);
        }
    };

    preview() {
        if (this.state.image) {
            return <div>
                <img src={'/file?path=' + this.state.image} alt="preview" style={{ maxWidth: '100%', height: 'auto' }} />
            </div>
        }
    }

    override render() {
        return <div>
            <h5>图片上传</h5>
            <input 
                type="file" 
                accept="image/*"
                onChange={this.handleFileChange}
                disabled={this.state.uploading}
            />
            {this.state.uploading && <p>上传中...</p>}
            {this.state.error && <p style={{ color: 'red' }}>{this.state.error}</p>}
            {this.preview()}
        </div>;
    }
}

type ImagePreviewState = {
    image: string;
}

export class ImagePreview extends IComponent<{}, ImagePreviewState> {
    constructor(props: {}) {
        super(props);
        this.state = { image: '' };
    }

    override render() {
        return <div>
            {this.state.image != '' ? 
                <img 
                    src={'/file?path=' + this.state.image} 
                    alt="placeholder" 
                    style={{ 
                        maxWidth: '100%', 
                        height: 'auto', 
                        display: 'block',
                        margin: '0 auto'
                    }} 
                /> : 
                <p>No image</p>
            }
        </div>
    }

    override onUpdate(data: any): void {
        console.log('ImagePreview onUpdate:', data);
        this.setState({ image: data.path });
    }
}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'ImageUploader', 'type': 'ssui.base.Image', 'port': 'input', 'component': ImageUploader } as ComponentRegister,
    { 'name': 'ImagePreview', 'type': 'ssui.base.Image', 'port': 'output', 'component': ImagePreview } as ComponentRegister
].forEach(registerComponent);