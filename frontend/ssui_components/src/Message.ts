export class Message {
    host: string;
    port: number;
    ws?: WebSocket;
    active_requests: number = 0;
    uuid?: string;
    message_cache: {
        [key: string]: any[]; // request_uuid -> messages[]
    } = {};
    listening_callbacks: {
        [key: string]: { // request uuid
            [key: string]: (data: any) => void; // callback name
        }
    } = {};

    constructor(
        host?: string,
        port?: number,
    ) {
        // 从当前页面URL获取host和port
        const url = new URL(window.location.href);
        this.host = host || url.hostname || 'localhost';
        this.port = port || (url.port ? parseInt(url.port) : 7422);
    }

    async connect(): Promise<string | undefined> {
        this.active_requests++;
        if (this.ws) { return; }
        return new Promise((resolve, reject) => {
            let ws = new WebSocket(`ws://${this.host}:${this.port}/ws`);
            ws.onopen = () => {
                console.log("connected to server!");
            }
            ws.onclose = () => {
                console.log("disconnected from server!");
                if (this.active_requests > 0) {
                    console.log("WebSocket disconnected, retrying...");
                    setTimeout(this.connect.bind(this), 200); // 0.2秒后自动重连
                }
            };

            ws.onmessage = (event: MessageEvent) => {
                console.log("onMessage: ", event.data, this.listening_callbacks);
                const data = JSON.parse(event.data);
                if (data.type === 'uuid') {
                    console.log("uuid received: ", data.uuid);
                    this.uuid = data.uuid;
                    resolve(this.uuid);
                }
        
                if (data.type === 'callback' || data.type === 'finish') {
                    const request_uuid = data.request_uuid;
                    if (!this.listening_callbacks[request_uuid]) {
                        // 如果回调还没有注册，将消息存入缓存
                        if (!this.message_cache[request_uuid]) {
                            this.message_cache[request_uuid] = [];
                        }
                        this.message_cache[request_uuid].push(data);
                        return;
                    }

                    if (data.type === 'callback') {
                        for (const key in this.listening_callbacks[request_uuid]) {
                            if (key in data) {
                                this.listening_callbacks[request_uuid][key](data[key]);
                            }
                        }
                    }
            
                    if (data.type === 'finish') {
                        this.listening_callbacks[request_uuid]['finish'](data);
                        delete this.listening_callbacks[request_uuid];
                    }
                }
            }

            ws.onerror = (err) => {
                console.error("WebSocket error", err);
                ws.close(); // 确保触发 onclose
                reject(err);
            };
            this.ws = ws;
        });
    }

    disconnect() {
        this.active_requests--;
        if (this.active_requests === 0 && this.ws) {
            this.ws.close();
            this.ws = undefined;
        }
    }

    

    async post(api_path: string, data?: any, callbacks?: {
        [key: string]: (data: any) => void;
    }) {
        if (!this.uuid) {
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        let address = `http://${this.host}:${this.port}/${api_path}`;
        if (callbacks) {
            await this.connect();
            address += `/${this.uuid}`;
        }
        const response = await fetch(address, {
            method: 'POST',
            body: data ? JSON.stringify(data) : undefined,
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            if (callbacks) { this.disconnect(); }
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        if (!callbacks) {
            return await response.json();
        }

        let result = await response.json();
        console.log("result: ", result);
        return await new Promise((resolve, reject) => {
            let finish_callback = (data: any) => {
                resolve(data);
                this.disconnect();
            };
            this.listening_callbacks[result.request_uuid] = {};
            for (const key in callbacks) {
                if (!(result.callbacks.includes(key))) {
                    reject(new Error(`Callback ${key} not found in result`));
                    this.disconnect();
                }
                this.listening_callbacks[result.request_uuid][key] = callbacks[key];
            }
            this.listening_callbacks[result.request_uuid]['finish'] = finish_callback;

            // 处理缓存的消息
            if (this.message_cache[result.request_uuid]) {
                const cached_messages = this.message_cache[result.request_uuid];
                delete this.message_cache[result.request_uuid];
                
                // 按顺序处理缓存的消息
                for (const cached_data of cached_messages) {
                    if (cached_data.type === 'callback') {
                        for (const key in this.listening_callbacks[result.request_uuid]) {
                            if (key in cached_data) {
                                this.listening_callbacks[result.request_uuid][key](cached_data[key]);
                            }
                        }
                    } else if (cached_data.type === 'finish') {
                        this.listening_callbacks[result.request_uuid]['finish'](cached_data);
                        delete this.listening_callbacks[result.request_uuid];
                    }
                }
            }
        });
    }

    async get(api_path: string) {
        const response = await fetch(`http://${this.host}:${this.port}/${api_path}`);
        return response.json();
    }

    async put(api_path: string, data: any) {
        const response = await fetch(`http://${this.host}:${this.port}/${api_path}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });

        return response.json();
    }

    async delete(api_path: string) {
        const response = await fetch(`http://${this.host}:${this.port}/${api_path}`, {
            method: 'DELETE',
        });

        return response.json();
    }


}
