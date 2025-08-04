import os, uuid
import random
from collections import defaultdict
from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.colors = ["red", "blue", "green", "orange", "purple", "brown"]
        self.connections: Dict[int, Dict[str, dict]] = defaultdict(dict)  # journal_id -> user_id -> {ws, name, color}

    async def connect(self, websocket: WebSocket, journal_id: int, user_email: str):
        await websocket.accept()
        user_id = str(uuid.uuid4())
        user_color = self.colors[len(self.connections[journal_id]) % len(self.colors)]
        user_name = user_email  # Используем email пользователя в качестве имени
        self.connections[journal_id][user_id] = {
            "ws": websocket,
            "color": user_color,
            "name": user_name
        }
        await self.broadcast_user_list(journal_id)
        return user_id, user_name, user_color

    def disconnect(self, user_id: str, journal_id: int):
        if journal_id in self.connections:
            self.connections[journal_id].pop(user_id, None)

    async def broadcast(self, journal_id: int, message: dict):
        for user in list(self.connections[journal_id].values()):
            try:
                await user["ws"].send_json(message)
            except:
                pass
        await self.broadcast_user_list(journal_id)

    async def broadcast_user_list(self, journal_id: int):
        users = [{"id": uid, "name": u["name"], "color": u["color"]} for uid, u in self.connections[journal_id].items()]
        for user in self.connections[journal_id].values():
            try:
                await user["ws"].send_json({"type": "users", "users": users})
            except:
                pass
            
manager = ConnectionManager()
