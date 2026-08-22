import { Message } from '../src/Message';

let serverProcess: any;

beforeAll(() => {
    // 启动 FastAPI 服务器用于测试
    const { spawn } = require('child_process');
    serverProcess = spawn('yarn', ['fastapi'], { 
        stdio: 'inherit',
        shell: true,
        env: {
            ...process.env,
            PYTHONIOENCODING: 'utf-8',
        },
    });
    
    // 等待服务器启动
    return new Promise((resolve) => {
        setTimeout(resolve, 3000);
    });
});

afterAll(() => {
    if (serverProcess) {
        const pid = serverProcess.pid;
        if (process.platform === 'win32' && pid) {
            // Windows 下需要连同子进程树一起结束
            require('child_process').execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' });
        } else {
            serverProcess.kill();
        }
    }
});


describe('Message', () => {
    let message: Message;
    const mockHost = 'localhost';
    const mockPort = 8000;

    beforeEach(() => {
        // Message 构造器会读取 window.location，在 node 环境下补齐
        (globalThis as any).window = {
            location: { href: `http://${mockHost}:${mockPort}` },
        };
        message = new Message(mockHost, mockPort);
    });

    describe('POST 请求', () => {
        it('应该能处理带回调的 POST 请求', async () => {
            let result = await message.post('start-task', undefined, {
                callback1: (data: any) => {
                    expect(data).toEqual('value1');
                },
                callback2: (data: any) => {
                    expect(data).toEqual('value2');
                }
            });
            expect(result.type).toEqual('finish');
        }, 10000);
    });
}); 
