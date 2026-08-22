import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useRef,
    useState,
} from 'react';
import { ConfigService } from './configService';
import { applyTheme, watchSystemTheme } from './theme';
import { ConfigSaveStatus, DEFAULT_UI_CONFIG, UiConfig } from './types';

export interface ConfigContextValue {
    config: UiConfig;
    loaded: boolean;
    saveStatus: ConfigSaveStatus;
    updateConfig: (patch: Partial<UiConfig>) => void;
    saveConfig: () => Promise<void>;
}

const ConfigContext = createContext<ConfigContextValue>({
    config: DEFAULT_UI_CONFIG,
    loaded: false,
    saveStatus: 'saved',
    updateConfig: () => {},
    saveConfig: async () => {},
});

export const ConfigProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const serviceRef = useRef<ConfigService | null>(null);
    if (!serviceRef.current) {
        serviceRef.current = new ConfigService();
    }

    const [config, setConfig] = useState<UiConfig>(DEFAULT_UI_CONFIG);
    const [loaded, setLoaded] = useState(false);
    const [saveStatus, setSaveStatus] = useState<ConfigSaveStatus>('saved');

    const pendingPatchRef = useRef<Partial<UiConfig>>({});
    const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const saveConfig = useCallback(async () => {
        const patch = pendingPatchRef.current;
        if (Object.keys(patch).length === 0) {
            return;
        }
        pendingPatchRef.current = {};
        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
            saveTimerRef.current = null;
        }

        setSaveStatus('saving');
        try {
            const saved = await serviceRef.current!.save(patch);
            setConfig(saved);
            setSaveStatus('saved');
        } catch (error) {
            console.error('保存配置失败:', error);
            // 保存失败时把补丁放回待保存队列，供下次 update/save 重试
            pendingPatchRef.current = { ...patch, ...pendingPatchRef.current };
            setSaveStatus('unsaved');
        }
    }, []);

    const updateConfig = useCallback((patch: Partial<UiConfig>) => {
        pendingPatchRef.current = { ...pendingPatchRef.current, ...patch };
        setConfig(prev => ({ ...prev, ...patch }));
        setSaveStatus('unsaved');

        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
        }
        saveTimerRef.current = setTimeout(saveConfig, 500);
    }, [saveConfig]);

    // 启动时先按默认主题渲染，再加载持久化配置
    useEffect(() => {
        applyTheme(DEFAULT_UI_CONFIG.theme);
        let cancelled = false;
        serviceRef.current!.load().then(cfg => {
            if (cancelled) {
                return;
            }
            setConfig(cfg);
            setLoaded(true);
        });
        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (loaded) {
            applyTheme(config.theme);
        }
    }, [config.theme, loaded]);

    // 跟随系统模式下，操作系统切换深浅色时实时生效
    useEffect(() => {
        if (!loaded || config.theme !== 'system') {
            return;
        }
        const unsubscribe = watchSystemTheme(() => {
            applyTheme(config.theme);
        });
        return unsubscribe;
    }, [loaded, config.theme]);

    useEffect(() => {
        return () => {
            if (saveTimerRef.current) {
                clearTimeout(saveTimerRef.current);
            }
        };
    }, []);

    return (
        <ConfigContext.Provider value={{ config, loaded, saveStatus, updateConfig, saveConfig }}>
            {children}
        </ConfigContext.Provider>
    );
};

export function useConfig(): ConfigContextValue {
    return useContext(ConfigContext);
}

export default ConfigContext;
