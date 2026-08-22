import { invoke } from '@tauri-apps/api/core';
import { ask } from '@tauri-apps/plugin-dialog';

export interface PortOwner {
    pid: number;
    name?: string;
}

const SERVER_PORT = 7422;
const EXECUTOR_PORT = 5000;

/**
 * 检测 SSUI 的端口是否被外部进程占用，并让用户决定如何处理：
 * - 选择「使用现有服务器」：直接连接外部进程（返回 true），应用不再自动启动。
 * - 选择「清理并重启」：终止占用端口的进程（返回 false），由应用自行启动。
 *
 * 外部调试服务器是受支持的工作流，因此不会在用户未确认的情况下自动清理。
 */
export async function resolvePortConflicts(): Promise<boolean> {
    const owners: { port: number; owner: PortOwner }[] = [];
    for (const port of [SERVER_PORT, EXECUTOR_PORT]) {
        try {
            const owner = await invoke<PortOwner | null>('check_port_owner', { port });
            if (owner) {
                owners.push({ port, owner });
            }
        } catch (error) {
            console.error(`检查端口 ${port} 失败:`, error);
        }
    }

    if (owners.length === 0) {
        return false;
    }

    const detail = owners
        .map(({ port, owner }) => {
            const name = owner.name ? `, ${owner.name}` : '';
            return `端口 ${port}（PID ${owner.pid}${name}）`;
        })
        .join('、');

    const useExisting = await ask(
        `检测到以下端口已被占用：${detail}。\n\n这可能是外部启动的调试服务器。要使用现有的服务器吗？`,
        {
            title: '检测到现有服务器',
            kind: 'warning',
            okLabel: '使用现有服务器',
            cancelLabel: '清理并重启',
        }
    );

    if (useExisting) {
        return true;
    }

    for (const { owner } of owners) {
        try {
            const killed = await invoke<boolean>('kill_pid', { pid: owner.pid });
            console.log(`清理端口占用进程 PID ${owner.pid}:`, killed);
        } catch (error) {
            console.error(`清理进程 PID ${owner.pid} 失败:`, error);
        }
    }
    return false;
}
