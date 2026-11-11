import { useEffect, useState } from 'react';
import { Message } from 'ssui_components';

type Memory = { total: number; available: number; used: number };
type Resources = { ram: Memory; gpus: (Memory & { index: number; name: string })[]; gpu_error: string | null };
type DiskRequest = { id: string; model: string; required_bytes: number };
async function getResource(message: Message, path: string) {
    const response = await fetch(`http://${message.host}:${message.port}/api/resources/${path}`);
    if (!response.ok) throw new Error(`Resource monitor HTTP ${response.status}`);
    return response.json();
}
const gib = (bytes: number) => (bytes / 2 ** 30).toFixed(1);

export function ResourceMonitor() {
    const [resources, setResources] = useState<Resources>();
    const [request, setRequest] = useState<DiskRequest>();
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    useEffect(() => {
        let disposed = false;
        let timer: ReturnType<typeof setTimeout>;
        const message = new Message();
        const poll = async () => {
            try {
                const [state, pending] = await Promise.all([
                    getResource(message, ''), getResource(message, 'disk-requests'),
                ]);
                if (!disposed) { setResources(state); setRequest(pending[0]); setError(''); }
            } catch { if (!disposed) setError('资源监控连接失败'); }
            if (!disposed) timer = setTimeout(poll, 2000);
        };
        void poll();
        return () => { disposed = true; clearTimeout(timer); };
    }, []);
    const answer = async (approved: boolean) => {
        if (!request) return;
        setBusy(true);
        try {
            await new Message().post(`api/resources/disk-requests/${request.id}`, { approved });
            setRequest(undefined);
        } catch { setError('提交失败，请重试（请求可能已过期）'); }
        finally { setBusy(false); }
    };
    return <aside aria-label="机器资源" style={{ padding: '4px 12px', fontSize: 12 }}>
        {resources && <span>内存 {gib(resources.ram.used)} / {gib(resources.ram.total)} GiB
            {resources.gpus.map(gpu => <span key={gpu.index}> · {gpu.name} 显存 {gib(gpu.used)} / {gib(gpu.total)} GiB</span>)}
            {!resources.gpus.length && <span> · {resources.gpu_error ? '显存数据不可用' : '未检测到 CUDA 显卡（共享内存设备参见内存）'}</span>}
        </span>}
        {error && <span role="status"> {error}</span>}
        {request && <div role="dialog" aria-modal="false" aria-label="磁盘 offload 确认">
            <p>内存不足：{request.model} 权重约 {gib(request.required_bytes)} GiB。是否允许本次使用磁盘 offload？
                会占用磁盘空间并降低速度，仍需要运行内存；拒绝将停止加载。180 秒未响应则停止。</p>
            <button disabled={busy} onClick={() => void answer(true)}>允许本次磁盘 offload</button>
            <button disabled={busy} onClick={() => void answer(false)}>拒绝并停止</button>
        </div>}
    </aside>;
}
