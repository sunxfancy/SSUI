import { invoke } from '@tauri-apps/api/core';
import { readDir, readTextFile, writeTextFile, mkdir, rename, remove } from '@tauri-apps/plugin-fs';
import { agentObject, agentString, AgentCommand, agentDOMCommands } from 'ssui_components';

// Mirrors command_handler() in src-tauri/src/lib.rs; parity is tested.
export const nativeAgentCommands: Record<string, Record<string, unknown>> = {
    get_dev_root: {}, detect_gpu: {}, get_server_status: {}, get_executor_status: {},
    stop_server: {}, stop_executor: {}, get_download_task_list: {},
    run_python: { path: agentString, cwd: agentString, args: { type: 'array', items: { type: 'string' } } },
    run_python_background: { path: agentString, cwd: agentString, args: { type: 'array', items: { type: 'string' } } },
    start_server: { path: agentString, cwd: agentString }, start_executor: { path: agentString, cwd: agentString },
    restart_server: { path: agentString, cwd: agentString }, restart_executor: { path: agentString, cwd: agentString },
    download_python: { version: agentString, releaseDate: agentString, architecture: agentString, path: agentString },
    unpack_app: { tarPath: agentString, targetPath: agentString }, set_proxy: { proxyUrl: { type: 'string' } },
    check_port_owner: { port: { type: 'integer', minimum: 1, maximum: 65535 } }, kill_pid: { pid: { type: 'integer', minimum: 1 } },
    create_download_task: { url: agentString, outputPath: agentString, sha256: { type: 'string' } },
    pause_download_task: { url: agentString }, resume_download_task: { url: agentString },
    cancel_download_task: { url: agentString }, get_download_task_progress: { url: agentString },
};

export function desktopAgentCommands(): AgentCommand[] {
    return [...agentDOMCommands(), ...Object.entries(nativeAgentCommands).map(([name, props]) => ({
        name: 'native.' + name, description: 'Invoke the existing Tauri command ' + name + '. Paths refer to the desktop machine. Service stop/restart may disconnect this command channel; inspect status after reconnect.',
        readOnly: name.startsWith('get_') || ['detect_gpu', 'check_port_owner'].includes(name),
        inputSchema: agentObject(props), run: (args: Record<string, unknown>) => invoke(name, args),
    })),
    { name: 'files.list', description: 'List workspace directory entries.', readOnly: true,
        inputSchema: agentObject({ path: agentString }), run: ({ path }) => readDir(path) },
    { name: 'files.read', description: 'Read a local UTF-8 file.', readOnly: true,
        inputSchema: agentObject({ path: agentString }), run: ({ path }) => readTextFile(path) },
    { name: 'files.create', description: 'Create a new local UTF-8 file without overwriting an existing one.',
        inputSchema: agentObject({ path: agentString, content: { type: 'string' } }),
        run: async ({ path, content }) => { await writeTextFile(path, content, { createNew: true }); return path; } },
    { name: 'files.mkdir', description: 'Create a directory.', inputSchema: agentObject({ path: agentString }), run: ({ path }) => mkdir(path) },
    { name: 'files.rename', description: 'Rename/move a path.', inputSchema: agentObject({ from: agentString, to: agentString }), run: ({ from, to }) => rename(from, to) },
    { name: 'files.remove', description: 'Delete a local file/directory. Recursive deletion must be explicit.',
        inputSchema: agentObject({ path: agentString, recursive: { type: 'boolean', default: false } }, ['path']), run: ({ path, recursive = false }) => remove(path, { recursive }) },
    ];
}
