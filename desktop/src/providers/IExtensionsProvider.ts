import { ExtensionItem } from '../components/Extensions';

export interface IExtensionsProvider {
  getExtensions(): Promise<ExtensionItem[]>;
  installExtension(extensionId: string): Promise<boolean>;
  uninstallExtension(extensionId: string): Promise<boolean>;
  searchExtensions(query: string): Promise<ExtensionItem[]>;
  disableExtension(extensionId: string): Promise<boolean>;
  enableExtension(extensionId: string): Promise<boolean>;
} 