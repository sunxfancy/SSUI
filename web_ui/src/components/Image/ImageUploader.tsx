import React from 'react';

type ImageUploaderState = {
    image: string;
}

export class ImageUploader extends React.Component<{}, ImageUploaderState> {
    constructor(props: {}) {
        super(props);
        this.state = { image: '' };
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

function ImageUploaderFunc() {
    return <ImageUploader />;
}

type ImagePreviewProps = {
    src: string;
}

export function ImagePreview({ src }: ImagePreviewProps) {
    return <div>
        {src ? <img src={src} alt="placeholder" /> : <p>No image</p>}
    </div>
}

// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'ImageUploader', 'type': 'ssui.base.Image', 'port': 'input', 'component': ImageUploaderFunc } as ComponentRegister,
    { 'name': 'ImagePreview', 'type': 'ssui.base.Image', 'port': 'output', 'component': ImagePreview } as ComponentRegister
].forEach(registerComponent);