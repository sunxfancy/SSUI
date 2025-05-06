import { IComponent } from '../IComponent';
import { Message } from '../../Message';
import { Select, ItemPredicate, ItemRenderer } from "@blueprintjs/select";
import { MenuItem, Button } from "@blueprintjs/core";

type ImagePickerState = {
    available_images: string[];
    selected_image: string;
}

export class ImagePicker extends IComponent<{ root_path: string, script_path: string }, ImagePickerState> {
    constructor(props: { root_path: string, script_path: string }) {
        super(props);
        this.state = {
            available_images: [],
            selected_image: ''
        };
    }
    message: Message = new Message();

    componentDidMount() {
        this.fetchAvailableImages();
    }

    async fetchAvailableImages() {
        const data = await this.message.get("files/image?" + new URLSearchParams({
            script_path: this.props.script_path ?? ''
        }));
        this.setState({ available_images: data });
    }

    handleImageSelect = (image: string) => {
        this.setState({ selected_image: image });
        this.onUpdate({ selected_image: image });
    }

    private filterImage: ItemPredicate<string> = (query, image, _index, exactMatch) => {
        const normalizedTitle = image.toLowerCase();
        const normalizedQuery = query.toLowerCase();

        if (exactMatch) {
            return normalizedTitle === normalizedQuery;
        } else {
            return normalizedTitle.indexOf(normalizedQuery) >= 0;
        }
    };

    private renderImage: ItemRenderer<string> = (image, { handleClick, handleFocus, modifiers }) => {
        if (!modifiers.matchesPredicate) {
            return null;
        }
        return (
            <MenuItem
                active={modifiers.active}
                disabled={modifiers.disabled}
                key={image}
                onClick={handleClick}
                onFocus={handleFocus}
                roleStructure="listoption"
                text={image}
            />
        );
    };

    override render() {
        return (
            <div className="image-picker">
                <Select<string>
                    items={this.state.available_images}
                    itemPredicate={this.filterImage}
                    itemRenderer={this.renderImage}
                    noResults={<MenuItem disabled={true} text="没有找到图片" roleStructure="listoption" />}
                    onItemSelect={this.handleImageSelect}
                >
                    <Button
                        text={this.state.selected_image || "请选择图片"}
                        rightIcon="double-caret-vertical"
                        fill={true}
                        minimal={true}
                    />
                </Select>
            </div>
        );
    }

    override onUpdate(data: any): void {
        console.log('ImagePicker onUpdate:', data);
    }
}



// Register into the component manager
import { registerComponent, ComponentRegister } from '../ComponentsManager';

[
    { 'name': 'ImagePicker', 'type': 'ssui.base.Image', 'port': 'input', 'component': ImagePicker } as ComponentRegister
].forEach(registerComponent);