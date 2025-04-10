export class Message {
    host: string;
    port: number;
    ws?: WebSocket;
    active_requests: number = 0;
    uuid?: string;
    listening_callbacks: {
        [key: string]: { // request uuid
            [key: string]: (data: any) => void; // callback name
        }
    } = {};

    constructor(
        host: string,
        port: number,
    ) {
        this.host = host;
        this.port = port;
    }

    async connect(): Promise<string | undefined> {
        this.active_requests++;
        if (this.ws) { return; }
        return new Promise((resolve, reject) => {
            let ws = new WebSocket(`ws://${this.host}:${this.port}/`);
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
                console.log("onMessage: ", event.data);
                const data = JSON.parse(event.data);
                if (data.type === 'uuid') {
                    console.log("uuid received: ", data.uuid);
                    this.uuid = data.uuid;
                    resolve(this.uuid);
                }
        
                if (data.type === 'callback') {
                    const request_uuid = data.request_uuid;
                    for (const key in this.listening_callbacks[request_uuid]) {
                        if (key in data) {
                            this.listening_callbacks[request_uuid][key](data[key]);
                        }
                    }
                }
        
                if (data.type === 'finish') {
                    const request_uuid = data.request_uuid;
                    this.listening_callbacks[request_uuid]['finish'](data);
                    delete this.listening_callbacks[request_uuid];
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
                console.log(result.callbacks);
                if (!(result.callbacks.includes(key))) {
                    reject(new Error(`Callback ${key} not found in result`));
                    this.disconnect();
                }
                this.listening_callbacks[result.request_uuid][key] = callbacks[key];
            }
            this.listening_callbacks[result.request_uuid]['finish'] = finish_callback;
        });
    }

    async get(api_path: string) {
        const response = await fetch(`${this.host}:${this.port}/${api_path}`);
        return response.json();
    }

    async put(api_path: string, data: any) {
        const response = await fetch(`${this.host}:${this.port}/${api_path}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });

        return response.json();
    }

    async delete(api_path: string) {
        const response = await fetch(`${this.host}:${this.port}/${api_path}`, {
            method: 'DELETE',
        });

        return response.json();
    }


}
