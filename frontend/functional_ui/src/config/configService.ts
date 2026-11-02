import { DEFAULT_UI_CONFIG, UiConfig } from './types';

const STORAGE_KEY = 'ssui.ui_config.v1';

export function validateUiConfig(value: unknown): Partial<UiConfig> {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    const source = value as Record<string, unknown>;
    const result: Partial<UiConfig> = {};
    if (source.theme === 'system' || source.theme === 'light' || source.theme === 'dark') result.theme = source.theme;
    if (typeof source.auto_open_details === 'boolean') result.auto_open_details = source.auto_open_details;
    if (typeof source.external_code_editor === 'string') result.external_code_editor = source.external_code_editor;
    if (typeof source.civitai_token === 'string') result.civitai_token = source.civitai_token;
    return result;
}

function readCache(): Partial<UiConfig> {
    try {
        return validateUiConfig(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null'));
    } catch {
        return {};
    }
}

function writeCache(config: UiConfig): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch {
        // Persistent server state remains authoritative when browser storage is unavailable.
    }
}

async function request(path: string, data?: unknown): Promise<any> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
        const response = await fetch(`/${path}`, {
            method: data === undefined ? 'GET' : 'POST',
            headers: data === undefined ? undefined : { 'Content-Type': 'application/json' },
            body: data === undefined ? undefined : JSON.stringify(data),
            signal: controller.signal,
        });
        if (!response.ok) throw new Error(`Config request failed (${response.status})`);
        const result = await response.json();
        if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('Invalid config response');
        if (result.error) throw new Error(String(result.error));
        return result;
    } finally {
        clearTimeout(timeout);
    }
}

/** Server persistence with validated local cache as an offline fallback. */
export class ConfigService {
    private current: UiConfig = { ...DEFAULT_UI_CONFIG };

    constructor(private message = {
        get: (path: string) => request(path),
        post: (path: string, data: unknown) => request(path, data),
    }) {}

    async load(): Promise<UiConfig> {
        this.current = { ...DEFAULT_UI_CONFIG, ...readCache() };
        try {
            const data = await this.message.get('config/');
            if (data?.error) throw new Error(String(data.error));
            this.current = { ...this.current, ...validateUiConfig(data?.ui) };
            writeCache(this.current);
        } catch {
            // Loading offline must not prevent editing and retrying a subsequent save.
        }
        return this.current;
    }

    cache(patch: Partial<UiConfig>): UiConfig {
        const config = { ...this.current, ...readCache(), ...validateUiConfig(patch) };
        writeCache(config);
        return config;
    }

    async save(patch: Partial<UiConfig>): Promise<UiConfig> {
        const validated = validateUiConfig(patch);
        const result = await this.message.post('config/', { ui: validated });
        if (result?.error) throw new Error(String(result.error));
        this.current = { ...this.current, ...validated };
        writeCache(this.current);
        return this.current;
    }
}
