import json
from fastapi import FastAPI, WebSocket, BackgroundTasks
import asyncio
import uuid
app = FastAPI()

# 用来模拟一个“WebSocket客户端池”，这里只存一个连接
ws_clients = {}

@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(uuid.uuid4())
    ws_clients[client_id] = websocket
    try:
        print("sending uuid to client")
        await websocket.send_text(json.dumps({"type": "uuid", "uuid": client_id}))
        while True:
            await websocket.receive_text()  # 保持连接
    except Exception as e:
        print("client disconnected: ", e)
        ws_clients.pop(client_id, None)

@app.post("/start-task/{client_id}")
async def start_task(client_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(do_work, client_id)
    return {"type": "start", "request_uuid": client_id, "callbacks": ["callback1", "callback2"]}

async def do_work(client_id: str):
    websocket = ws_clients.get(client_id)
    if websocket:
        await asyncio.sleep(1)  # 模拟耗时任务
        await websocket.send_text(json.dumps({"type": "callback", "request_uuid": client_id, "callback1": "value1", "callback2": "value2"}))
        await asyncio.sleep(1)  # 模拟耗时任务
        await websocket.send_text(json.dumps({"type": "finish", "request_uuid": client_id}))