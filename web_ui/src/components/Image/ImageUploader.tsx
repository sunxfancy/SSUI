import { IComponent } from '../IComponent';

type ImageUploaderState = {
    image: string;
}

export class ImageUploader extends IComponent<{}, ImageUploaderState> {
    constructor(props: {}) {
        super(props);
        this.state = { image: '' };
    }

    onExecute() {
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

    render() {
        return <div>
            <h5>Image Uploader</h5>
            <input name='file_field' type="file" />
            <button onClick={this.onclick}>Upload</button>
            {this.preview()}
        </div>;
    }
}

type ImagePreviewProps = {
    src: string;
}

export class ImagePreview extends IComponent<ImagePreviewProps, ImageUploaderState> {
    render() {
        return <div>
            {this.props.src ? <img src={this.props.src} alt="placeholder" /> : <p>No image</p>}
        </div>
    }
}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'ImageUploader', 'type': 'ssui.base.Image', 'port': 'input', 'component': ImageUploader } as ComponentRegister,
    { 'name': 'ImagePreview', 'type': 'ssui.base.Image', 'port': 'output', 'component': ImagePreview } as ComponentRegister
].forEach(registerComponent);