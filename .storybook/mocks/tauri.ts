export async function invoke(command: string): Promise<unknown> {
    if (command === 'set_proxy') return;
    if (command === 'get_dev_root') return '/mock';
    if (command === 'get_download_task_list') return [];
    throw new Error(`[Storybook offline] Supply a provider for Tauri command: ${command}`);
}
export const platform = () => 'windows';
export const listen = async () => () => {};
export const exit = async () => { throw new Error('Storybook cannot exit the desktop application'); };
export const relaunch = exit;
export async function load() {
    const data = new Map<string, unknown>();
    return { get: async (key: string) => data.get(key), set: async (key: string, value: unknown) => { data.set(key, value); }, save: async () => {} };
}
