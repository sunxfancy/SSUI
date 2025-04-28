import { FunctionalUIProvider } from "./functional/FunctionalUI";
import { ImagePreviewProvider } from "./preview/ImagePreview";
import { ProjectSettingsProvider } from './settings/ProjectSettings';
export interface UIProvider {
    getName(): string;
    getUI(path: string): JSX.Element;
}

let ui_providers: { [key: string]: UIProvider } = {};

export function registerUIProvider(provider: UIProvider) {
    console.log("registerUIProvider", provider.getName());
    ui_providers[provider.getName()] = provider;
}

export function getUIProvider(name: string): UIProvider | undefined {
    return ui_providers[name];
}

registerUIProvider(new FunctionalUIProvider());
registerUIProvider(new ProjectSettingsProvider());
registerUIProvider(new ImagePreviewProvider());
