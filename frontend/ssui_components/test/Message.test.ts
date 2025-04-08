import { Message } from '../src/Message';

let serverProcess: any;

beforeAll(() => {
    // 启动 FastAPI 服务器用于测试
    const { spawn } = require('child_process');
    serverProcess = spawn('yarn', ['fastapi'], { 
        stdio: 'inherit',
        shell: true,
    });
    
    // 等待服务器启动
    return new Promise((resolve) => {
        setTimeout(resolve, 3000);
    });
});


describe('Message', () => {
    let message: Message;
    const mockHost = 'localhost';
    const mockPort = 8000;

    beforeEach(() => {
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