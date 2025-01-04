import { FunctionalUIProvider } from "./functional/FunctionalUI";

export interface UIProvider {
    getName(): string;
    getUI(path: string): JSX.Element;
}

let ui_providers: { [key: string]: UIProvider } = {};

export function registerUIProvider(provider: UIProvider) {
    ui_providers[provider.getName()] = provider;
}

export function getUIProvider(name: string): UIProvider | undefined {
    return ui_providers[name];
}

registerUIProvider(new FunctionalUIProvider());
