# backend/app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

# Connection manager for WebSocket clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        logger.info(f"Client {client_id} connected")
        
    def disconnect(self, websocket: WebSocket, client_id: str):
        """Remove a WebSocket connection"""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
        logger.info(f"Client {client_id} disconnected")
        
    async def send_personal_message(self, message: str, client_id: str):
        """Send a message to a specific client"""
        if client_id in self.active_connections:
            for connection in self.active_connections[client_id]:
                try:
                    await connection.send_text(message)
                except:
                    # Connection might be closed
                    pass
                    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients"""
        for client_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_text(message)
                except:
                    # Connection might be closed
                    pass

# Global connection manager
manager = ConnectionManager()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket, client_id)
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "message": "Connected to Music Discovery System"
        })
        
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    })
                    
                elif message.get("type") == "subscribe":
                    # Client wants to subscribe to specific events
                    event_type = message.get("event_type")
                    await websocket.send_json({
                        "type": "subscribed",
                        "event_type": event_type,
                        "status": "success"
                    })
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)
        
# Event notification functions
async def notify_discovery_started(session_id: str, details: Dict):
    """Notify clients when a discovery session starts"""
    message = json.dumps({
        "type": "discovery_started",
        "session_id": session_id,
        "details": details,
        "timestamp": datetime.now().isoformat()
    })
    await manager.broadcast(message)

async def notify_artist_discovered(artist_data: Dict):
    """Notify clients when a new artist is discovered"""
    message = json.dumps({
        "type": "artist_discovered",
        "artist": artist_data,
        "timestamp": datetime.now().isoformat()
    })
    await manager.broadcast(message)

async def notify_discovery_progress(session_id: str, progress: Dict):
    """Notify clients of discovery progress"""
    message = json.dumps({
        "type": "discovery_progress",
        "session_id": session_id,
        "progress": progress,
        "timestamp": datetime.now().isoformat()
    })
    await manager.broadcast(message)

async def notify_discovery_completed(session_id: str, summary: Dict):
    """Notify clients when discovery session completes"""
    message = json.dumps({
        "type": "discovery_completed",
        "session_id": session_id,
        "summary": summary,
        "timestamp": datetime.now().isoformat()
    })
    await manager.broadcast(message)

# Export the notification functions
__all__ = [
    'router',
    'notify_discovery_started',
    'notify_artist_discovered', 
    'notify_discovery_progress',
    'notify_discovery_completed'
]