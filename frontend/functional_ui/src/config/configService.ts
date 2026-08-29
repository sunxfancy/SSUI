import { Message } from 'ssui_components';
import { DEFAULT_UI_CONFIG, UiConfig } from './types';

const STORAGE_KEY = 'ssui.ui_config.v1';

function readCache(): Partial<UiConfig> | null {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) as Partial<UiConfig> : null;
    } catch (error) {
        console.error('读取本地配置缓存失败:', error);
        return null;
    }
}

function writeCache(config: UiConfig): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch (error) {
        console.error('写入本地配置缓存失败:', error);
    }
}

function normalizeUiConfig(ui?: Partial<UiConfig> | null): UiConfig {
    const cached = readCache();
    return {
        ...DEFAULT_UI_CONFIG,
        ...(cached ?? {}),
        ...(ui ?? {}),
    };
}

/**
 * 用户配置服务：以服务端 `/config/` 为持久化来源，
 * 本地 localStorage 仅作为启动时的快速缓存与离线回退。
 */
export class ConfigService {
    private message: Message;

    constructor(message?: Message) {
        this.message = message ?? new Message();
    }

    async load(): Promise<UiConfig> {
        try {
            const data = await this.message.get('config/');
            const config = normalizeUiConfig(data?.ui as Partial<UiConfig> | undefined);
            writeCache(config);
            return config;
        } catch (error) {
            console.error('加载配置失败，使用本地缓存/默认值:', error);
            return normalizeUiConfig(null);
        }
    }

    /**
     * 先同步写入本地缓存，确保用户在自动保存计时结束前关闭页面时也不会丢失修改。
     */
    cache(patch: Partial<UiConfig>): UiConfig {
        const config = normalizeUiConfig({ ...readCache(), ...patch });
        writeCache(config);
        return config;
    }

    async save(patch: Partial<UiConfig>): Promise<UiConfig> {
        const response = await this.message.post('config/', { ui: patch });
        const serverConfig = response?.ui as Partial<UiConfig> | undefined;
        const config = normalizeUiConfig(
            serverConfig ?? { ...readCache(), ...patch }
        );
        writeCache(config);
        return config;
    }
}
