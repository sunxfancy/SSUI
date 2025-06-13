import { IComponent } from '../IComponent';

type VideoUploaderState = {
    video: string;
    uploading: boolean;
    error: string | null;
}

export class VideoUploader extends IComponent<{ script_path: string }, VideoUploaderState> {
    constructor(props: { script_path: string }) {
        super(props);
        this.state = { 
            video: '',
            uploading: false,
            error: null
        };
    }

    override onExecute() {
        return { 'video': this.state.video };
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
                    video: data.path,
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
        if (this.state.video) {
            return <div>
                <img src={'/file?path=' + this.state.video} alt="preview" style={{ maxWidth: '100%', height: 'auto' }} />
            </div>
        }
    }

    override render() {
        return <div>
            <h5>视频上传</h5>
            <input 
                type="file" 
                accept="video/*"
                onChange={this.handleFileChange}
                disabled={this.state.uploading}
            />
            {this.state.uploading && <p>上传中...</p>}
            {this.state.error && <p style={{ color: 'red' }}>{this.state.error}</p>}
            {this.preview()}
        </div>;
    }
}

type VideoPreviewState = {
    video: string;
}

export class VideoPreview extends IComponent<{}, VideoPreviewState> {
    constructor(props: {}) {
        super(props);
        this.state = { video: '' };
    }

    override render() {
        return <div>
            {this.state.video != '' ? 
                <img 
                    src={'/file?path=' + this.state.video} 
                    alt="placeholder" 
                    style={{ 
                        maxWidth: '100%', 
                        height: 'auto', 
                        display: 'block',
                        margin: '0 auto'
                    }} 
                /> : 
                <p>No video</p>
            }
        </div>
    }

    override onUpdate(data: any): void {
        console.log('VideoPreview onUpdate:', data);
        this.setState({ video: data.path });
    }
}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'VideoUploader', 'type': 'ssui.base.Video', 'port': 'input', 'component': VideoUploader } as ComponentRegister,
    { 'name': 'VideoPreview', 'type': 'ssui.base.Video', 'port': 'output', 'component': VideoPreview } as ComponentRegister
].forEach(registerComponent);