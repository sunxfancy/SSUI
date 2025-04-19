import json
import uuid
import asyncio
from typing import Dict, Any
from fastapi import WebSocket
from server.models import WebSocketCallback, WebSocketFinish, WebSocketUUID

class WebSocketService:
    def __init__(self):
        self.clients: Dict[str, WebSocket] = {}
        self.is_running = True
    
    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.clients[client_id] = websocket
        print("sending uuid", client_id, "to client")
        message = WebSocketUUID(type="uuid", uuid=client_id)
        await self.send_message(client_id, message.model_dump())
        return client_id
    
    def disconnect(self, client_id: str) -> None:
        if client_id in self.clients:
            del self.clients[client_id]
    
    async def send_message(self, client_id: str, message: Dict[str, Any]) -> None:
        if client_id in self.clients:
            try:
                await self.clients[client_id].send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending message to client {client_id}: {e}")
    
    def send_callback(self, client_id: str, request_uuid: str, callback_data: Dict[str, Any]) -> None:
        message = WebSocketCallback(type="callback", request_uuid=request_uuid, **callback_data)
        asyncio.create_task(self.send_message(client_id, message.model_dump()))
    
    def send_finish(self, client_id: str, request_uuid: str, extra_data: Dict[str, Any] = {}) -> None:
        message = WebSocketFinish(type="finish", request_uuid=request_uuid, **extra_data)
        asyncio.create_task(self.send_message(client_id, message.model_dump()))
    
    def stop(self) -> None:
        self.is_running = False 
        for client_id in self.clients:
            self.clients[client_id].close()
        self.clients.clear()
        print("websocket service stopped")
