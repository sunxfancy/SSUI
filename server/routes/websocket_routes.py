from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    websocket_service = websocket.app.state.websocket_service
    client_id = None
    try:
        client_id = await websocket_service.connect(websocket)
        while websocket_service.is_running:
            await websocket.receive_text()  # 保持连接
    except Exception as e:
        print("client disconnected: ", e)
        if client_id is not None:
            websocket_service.disconnect(client_id)
