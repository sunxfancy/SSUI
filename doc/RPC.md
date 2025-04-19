# RPC 远程过程调用
=====================

RPC（远程过程调用）是UI系统调用服务端API的方式之一。相比于传统的HTTP调用，RPC提供了回调功能，允许服务器在执行过程中或完成后通知UI系统。

## RPC的工作原理

RPC系统基于WebSocket和HTTP协议实现，结合了两种协议的优势：
- HTTP用于发送初始请求
- WebSocket用于接收服务器的实时回调

### 核心组件

1. **前端组件**：`Message.ts`类，负责与服务器建立WebSocket连接并处理回调
2. **后端组件**：FastAPI服务器，处理RPC请求并通过WebSocket发送回调

### 执行流程

RPC通过WebSocket连接到服务器，这里需要考虑多个连接的情况，所以采用了两个UUID作为身份标识,分别是client_id和request_uuid。整个连接过程如下：

1. **建立连接**：客户端通过WebSocket连接到服务器，服务器生成唯一标识符(client_id)并返回给客户端
2. **发送请求**：客户端通过HTTP发送RPC请求，并在请求中包含之前获得的client_id，服务器在处理请求时，会生成一个request_uuid，并返回给客户端
3. **后台处理**：服务器接收请求后，在后台异步处理任务
4. **回调通知**：服务器在处理过程中，通过WebSocket向客户端发送回调信息，回调信息中会包含request_uuid，客户端根据request_uuid找到对应的回调函数并执行
5. **完成通知**：任务完成后，服务器发送完成消息，客户端解析最终结果

## 消息类型

RPC系统中有三种主要消息类型：

1. **UUID消息**：服务器在WebSocket连接建立后发送，包含客户端的唯一标识符
2. **回调消息**：服务器在处理任务过程中发送，包含中间结果或进度信息
3. **完成消息**：服务器在任务完成后发送，表示整个RPC调用已结束

## 回调机制

回调是RPC系统的核心特性，它允许服务器在执行长时间任务时向客户端提供实时更新，这需要双方的支持：

1. 客户端在发送请求时编写回调函数
2. 服务器在处理过程中声明将调用哪些回调函数，并发生消息给客户端

## 错误处理

RPC系统包含多层错误处理机制：

1. **连接错误**：WebSocket连接断开时自动重连
2. **请求错误**：HTTP请求失败时抛出异常
3. **回调错误**：回调名称不匹配或回调执行失败时的处理

## 实现示例

### 前端使用示例

```typescript
// 创建Message实例并连接到服务器
const message = new Message("localhost", 8000);
await message.connect();

// 发送带有回调的RPC请求
const result = await message.post("start-task", { data: "example" }, {
  callback1: (data) => {
    console.log("收到callback1回调:", data);
  },
  callback2: (data) => {
    console.log("收到callback2回调:", data);
  }
});
```

### 后端实现示例

```python
# WebSocket连接处理
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(uuid.uuid4())
    ws_clients[client_id] = websocket
    try:
        print("sending uuid to client")
        await websocket.send_text(json.dumps({"type": "uuid", "uuid": client_id}))
        while ws_is_running:
            await websocket.receive_text()  # 保持连接
    except Exception as e:
        print("client disconnected: ", e)
        ws_clients.pop(client_id, None)

# RPC端点实现
# 客户端发送请求的端点, 这里需要传入client_id，message包会自动做这件事
@app.post("/api/scan_models/{client_id}") 
async def scan_models(client_id: str, request: ScanModelsRequest):
    scan_dir = os.path.normpath(request.scan_dir)
    if not os.path.exists(scan_dir):
        return {"error": "Scan directory not found"}
    request_uuid = str(uuid.uuid4())

    loop = asyncio.get_running_loop()
    threading.Thread(
        target=background_task, args=(scan_dir, client_id, request_uuid, loop), daemon=True
    ).start()
    return {
        "type": "start",
        "request_uuid": request_uuid,  # 返回给客户端的request_uuid
        "message": "Models scan started",
        "callbacks": ["callback1", "callback2"], # 声明将调用哪些回调函数
    }

# 发送回调消息
def send_message(loop: asyncio.AbstractEventLoop, client_id: str, request_uuid: str, message: dict[str, any]):
    print("send_message:", request_uuid, message)
    message = json.dumps({"type": "callback", "request_uuid": request_uuid, **message})
    loop.call_soon_threadsafe(asyncio.create_task, send_text(client_id, message))

# 发送完成消息
def send_finish(
    loop: asyncio.AbstractEventLoop, client_id: str, request_uuid: str, message: Optional[dict[str, any]] = None
):
    print("send_finish:", request_uuid, message)
    if message is None:
        message = {}
    message = json.dumps({"type": "finish", "request_uuid": request_uuid, **message})
    loop.call_soon_threadsafe(asyncio.create_task, send_text(client_id, message))
```






