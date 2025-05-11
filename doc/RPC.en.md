# RPC Remote Procedure Call
=====================

RPC (Remote Procedure Call) is one of the ways the UI system calls server APIs. Compared to traditional HTTP calls, RPC provides callback functionality, allowing the server to notify the UI system during or after execution.

## How RPC Works

The RPC system is implemented based on WebSocket and HTTP protocols, combining the advantages of both:
- HTTP for sending initial requests
- WebSocket for receiving real-time callbacks from the server

### Core Components

1. **Frontend Component**: `Message.ts` class, responsible for establishing WebSocket connection with the server and handling callbacks
2. **Backend Component**: FastAPI server, handling RPC requests and sending callbacks via WebSocket

### Execution Flow

RPC connects to the server via WebSocket. Since multiple connections need to be considered, two UUIDs are used as identifiers: client_id and request_uuid. The entire connection process is as follows:

1. **Establish Connection**: Client connects to server via WebSocket, server generates a unique identifier (client_id) and returns it to the client
2. **Send Request**: Client sends RPC request via HTTP, including the previously obtained client_id. Server generates a request_uuid when processing the request and returns it to the client
3. **Background Processing**: Server receives the request and processes the task asynchronously in the background
4. **Callback Notification**: Server sends callback information to the client via WebSocket during processing. Callback information includes request_uuid, and the client finds and executes the corresponding callback function based on request_uuid
5. **Completion Notification**: After task completion, server sends completion message, client parses final result

## Message Types

There are three main message types in the RPC system:

1. **UUID Message**: Sent by server after WebSocket connection is established, contains client's unique identifier
2. **Callback Message**: Sent by server during task processing, contains intermediate results or progress information
3. **Completion Message**: Sent by server after task completion, indicates the entire RPC call has ended

## Callback Mechanism

Callbacks are a core feature of the RPC system, allowing the server to provide real-time updates to the client during long-running tasks. This requires support from both sides:

1. Client writes callback functions when sending requests
2. Server declares which callback functions will be called during processing and sends messages to the client

## Error Handling

The RPC system includes multiple layers of error handling:

1. **Connection Errors**: Automatic reconnection when WebSocket connection is lost
2. **Request Errors**: Exception throwing when HTTP request fails
3. **Callback Errors**: Handling of callback name mismatches or callback execution failures

## Implementation Examples

### Frontend Usage Example

```typescript
// Create Message instance and connect to server
const message = new Message("localhost", 8000);
await message.connect();

// Send RPC request with callbacks
const result = await message.post("start-task", { data: "example" }, {
  callback1: (data) => {
    console.log("Received callback1:", data);
  },
  callback2: (data) => {
    console.log("Received callback2:", data);
  }
});
```

### Backend Implementation Example

```python
# WebSocket connection handling
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(uuid.uuid4())
    ws_clients[client_id] = websocket
    try:
        print("sending uuid to client")
        await websocket.send_text(json.dumps({"type": "uuid", "uuid": client_id}))
        while ws_is_running:
            await websocket.receive_text()  # Keep connection alive
    except Exception as e:
        print("client disconnected: ", e)
        ws_clients.pop(client_id, None)

# RPC endpoint implementation
# Endpoint for client requests, client_id needs to be passed in, message package handles this automatically
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
        "request_uuid": request_uuid,  # request_uuid returned to client
        "message": "Models scan started",
        "callbacks": ["callback1", "callback2"], # Declare which callback functions will be called
    }

# Send callback message
def send_message(loop: asyncio.AbstractEventLoop, client_id: str, request_uuid: str, message: dict[str, any]):
    print("send_message:", request_uuid, message)
    message = json.dumps({"type": "callback", "request_uuid": request_uuid, **message})
    loop.call_soon_threadsafe(asyncio.create_task, send_text(client_id, message))

# Send completion message
def send_finish(
    loop: asyncio.AbstractEventLoop, client_id: str, request_uuid: str, message: Optional[dict[str, any]] = None
):
    print("send_finish:", request_uuid, message)
    if message is None:
        message = {}
    message = json.dumps({"type": "finish", "request_uuid": request_uuid, **message})
    loop.call_soon_threadsafe(asyncio.create_task, send_text(client_id, message))
``` 