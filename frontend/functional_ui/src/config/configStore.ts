import { ConfigSaveStatus, DEFAULT_UI_CONFIG, UiConfig } from './types';

interface Persistence {
    load(): Promise<UiConfig>;
    cache?(patch: Partial<UiConfig>): UiConfig;
    save(patch: Partial<UiConfig>): Promise<UiConfig>;
}

/** One owner for optimistic edits and the serial persistence queue. */
export class ConfigStore {
    private snapshot = { config: { ...DEFAULT_UI_CONFIG }, loaded: false,
        saveStatus: 'saved' as ConfigSaveStatus, saveError: null as string | null };
    private pending: Partial<UiConfig> = {};
    private listeners = new Set<() => void>();
    private loading: Promise<void> | null = null;
    private saving: Promise<void> | null = null;
    private timer: ReturnType<typeof setTimeout> | null = null;

    constructor(private service: Persistence) {}

    getSnapshot = () => this.snapshot;
    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => { this.listeners.delete(listener); };
    };
    private publish(patch: Partial<typeof this.snapshot>) {
        this.snapshot = { ...this.snapshot, ...patch };
        this.listeners.forEach(listener => listener());
    }

    load = (): Promise<void> => {
        if (!this.loading) {
            this.loading = this.service.load().then(config => {
                this.publish({ config: { ...config, ...this.pending }, loaded: true });
            });
        }
        return this.loading;
    };

    update = (patch: Partial<UiConfig>) => {
        this.pending = { ...this.pending, ...patch };
        this.service.cache?.(patch);
        this.publish({ config: { ...this.snapshot.config, ...patch }, saveStatus: 'unsaved' });
        this.clearTimer();
        this.timer = setTimeout(() => { void this.save(); }, 500);
    };

    private clearTimer() {
        if (this.timer !== null) clearTimeout(this.timer);
        this.timer = null;
    }

    save = (): Promise<void> => {
        this.clearTimer();
        if (this.saving) return this.saving;
        // Assign the promise before starting work, including subscriber callbacks.
        this.saving = Promise.resolve().then(async () => {
            await this.load();
            while (Object.keys(this.pending).length) {
                const patch = this.pending;
                this.pending = {};
                this.publish({ saveStatus: 'saving', saveError: null });
                try {
                    const saved = await this.service.save(patch);
                    this.publish({ config: { ...saved, ...this.pending } });
                } catch (error) {
                    // More recent values win when restoring a failed request.
                    this.pending = { ...patch, ...this.pending };
                    this.publish({ saveStatus: 'error',
                        saveError: error instanceof Error ? error.message : String(error) });
                    this.clearTimer();
                    return;
                }
            }
            this.clearTimer();
            this.publish({ saveStatus: 'saved', saveError: null });
        }).finally(() => { this.saving = null; });
        return this.saving;
    };
}
