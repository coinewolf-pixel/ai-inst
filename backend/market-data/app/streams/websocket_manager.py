from typing import Dict, List
from fastapi import WebSocket

class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        if symbol not in self.connections:
            self.connections[symbol] = []
        self.connections[symbol].append(websocket)

    def disconnect(self, websocket: WebSocket, symbol: str):
        if symbol in self.connections:
            self.connections[symbol] = [ws for ws in self.connections[symbol] if ws != websocket]

    async def broadcast(self, symbol: str, message: str):
        if symbol in self.connections:
            disconnected = []
            for ws in self.connections[symbol]:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                self.disconnect(ws, symbol)

ws_manager = WebSocketManager()
