import GlobalStateManager from './GlobalState';

/**
 * 获取 FastAPI 后端的 HTTP 基础地址。
 *
 * 桌面壳由 Tauri 承载（开发时 localhost:1420，打包后 tauri.localhost），
 * 与后端（7422，或开发时经 functional_ui 7420 代理）不同源，
 * 因此所有 /api 调用必须使用绝对地址。
 */
export function getApiBaseUrl(): string {
    const rootState = GlobalStateManager.getInstance().getRootState();
    const host = rootState?.host || 'localhost';
    const port = rootState?.port || 7422;
    return `http://${host}:${port}`;
}
