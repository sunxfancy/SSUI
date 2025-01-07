import { registerComponent, ComponentRegister } from 'ssui_interface';

type ImagePreview2Props = {
    src: string;
}

export function ImagePreview2({ src }: ImagePreview2Props) {
    return <div>
        {src ? <img src={src} alt="placeholder" /> : <p>No Image Preview2</p>}
    </div>
}

export function main() {
    [
        { 'name': 'ImagePreview', 'type': 'ssui.base.Image', 'port': 'output', 'component': ImagePreview2 } as ComponentRegister
    ].forEach(registerComponent);
}