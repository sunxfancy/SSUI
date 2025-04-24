import { IComponent } from '../IComponent';

type ImageUploaderState = {
    image: string;
}

export class ImageUploader extends IComponent<{}, ImageUploaderState> {
    constructor(props: {}) {
        super(props);
        this.state = { image: '' };
    }

    override onExecute() {
        return { 'image': this.state.image };
    }

    onclick() {
        console.log('uploading image');
    };

    preview() {
        if (this.state.image) {
            return <img src={this.state.image} alt="placeholder" />
        }
    }

    override render() {
        return <div>
            <h5>Image Uploader</h5>
            <input name='file_field' type="file" />
            <button onClick={this.onclick}>Upload</button>
            {this.preview()}
        </div>;
    }
}


export class ImagePreview extends IComponent<{}, ImageUploaderState> {
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