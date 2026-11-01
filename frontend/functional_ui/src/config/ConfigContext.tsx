import React, {
    createContext,
    useContext,
    useEffect,
    useRef,
    useSyncExternalStore,
} from 'react';
import { ConfigService } from './configService';
import { ConfigStore } from './configStore';
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
    const storeRef = useRef<ConfigStore | null>(null);
    if (!storeRef.current) storeRef.current = new ConfigStore(new ConfigService());
    const store = storeRef.current;
    const { config, loaded, saveStatus, saveError } = useSyncExternalStore(store.subscribe, store.getSnapshot);
    const updateConfig = store.update;
    const saveConfig = store.save;
    const resetConfig = () => store.update(DEFAULT_UI_CONFIG);

    useEffect(() => {
        void store.load();
        // Flush the debounce queue when the provider leaves the page.
        return () => { void store.save(); };
    }, [store]);

    useEffect(() => {
        const beforeUnload = (event: BeforeUnloadEvent) => {
            if (store.getSnapshot().saveStatus !== 'saved') {
                event.preventDefault();
                event.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', beforeUnload);
        return () => window.removeEventListener('beforeunload', beforeUnload);
    }, [store]);

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

    return (
        <ConfigContext.Provider value={{ config, loaded, saveStatus, saveError, updateConfig, saveConfig, resetConfig }}>
            {children}
        </ConfigContext.Provider>
    );
};

export function useConfig(): ConfigContextValue {
    return useContext(ConfigContext);
}

export default ConfigContext;
