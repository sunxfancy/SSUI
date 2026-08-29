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
    saveError: string | null;
    updateConfig: (patch: Partial<UiConfig>) => void;
    saveConfig: () => Promise<void>;
    resetConfig: () => void;
}

const ConfigContext = createContext<ConfigContextValue>({
    config: DEFAULT_UI_CONFIG,
    loaded: false,
    saveStatus: 'saved',
    saveError: null,
    updateConfig: () => {},
    saveConfig: async () => {},
    resetConfig: () => {},
});

export const ConfigProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const serviceRef = useRef<ConfigService | null>(null);
    if (!serviceRef.current) {
        serviceRef.current = new ConfigService();
    }

    const [config, setConfig] = useState<UiConfig>(DEFAULT_UI_CONFIG);
    const [loaded, setLoaded] = useState(false);
    const [saveStatus, setSaveStatus] = useState<ConfigSaveStatus>('saved');
    const [saveError, setSaveError] = useState<string | null>(null);

    const pendingPatchRef = useRef<Partial<UiConfig>>({});
    const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const savingPromiseRef = useRef<Promise<void> | null>(null);

    const saveConfig = useCallback(async () => {
        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
            saveTimerRef.current = null;
        }
        if (savingPromiseRef.current) {
            return savingPromiseRef.current;
        }

        const run = async () => {
            while (Object.keys(pendingPatchRef.current).length > 0) {
                const patch = pendingPatchRef.current;
                pendingPatchRef.current = {};
                setSaveStatus('saving');
                setSaveError(null);
                try {
                    const saved = await serviceRef.current!.save(patch);
                    // 保存期间产生的新修改必须继续保留在乐观 UI 中。
                    setConfig({ ...saved, ...pendingPatchRef.current });
                } catch (error) {
                    console.error('保存配置失败:', error);
                    pendingPatchRef.current = { ...patch, ...pendingPatchRef.current };
                    setSaveError(error instanceof Error ? error.message : '保存配置失败');
                    setSaveStatus('error');
                    return;
                }
            }
            setSaveStatus('saved');
        };

        savingPromiseRef.current = run().finally(() => {
            savingPromiseRef.current = null;
        });
        return savingPromiseRef.current;
    }, []);

    const updateConfig = useCallback((patch: Partial<UiConfig>) => {
        pendingPatchRef.current = { ...pendingPatchRef.current, ...patch };
        setConfig(prev => ({ ...prev, ...patch }));
        serviceRef.current!.cache(patch);
        setSaveError(null);
        setSaveStatus('unsaved');

        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
        }
        saveTimerRef.current = setTimeout(() => {
            void saveConfig();
        }, 500);
    }, [saveConfig]);

    const resetConfig = useCallback(() => {
        updateConfig(DEFAULT_UI_CONFIG);
    }, [updateConfig]);

    // 启动时先按默认主题渲染，再加载持久化配置
    useEffect(() => {
        applyTheme(DEFAULT_UI_CONFIG.theme);
        let cancelled = false;
        serviceRef.current!.load().then(cfg => {
            if (cancelled) {
                return;
            }
            // 加载期间产生的乐观修改优先于服务端快照。
            setConfig({ ...cfg, ...pendingPatchRef.current });
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
        <ConfigContext.Provider value={{
            config,
            loaded,
            saveStatus,
            saveError,
            updateConfig,
            saveConfig,
            resetConfig,
        }}>
            {children}
        </ConfigContext.Provider>
    );
};

export function useConfig(): ConfigContextValue {
    return useContext(ConfigContext);
}

export default ConfigContext;
