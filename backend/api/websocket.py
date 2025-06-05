# backend/app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import logging
import asyncio

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
    'notify_discovery_started',
    'notify_artist_discovered', 
    'notify_discovery_progress',
    'notify_discovery_completed'
]

# backend/app/requirements.txt
pydantic-ai>=0.1.0
fastapi>=0.104.0
uvicorn>=0.24.0
supabase>=2.0.0
httpx>=0.25.0
youtube-transcript-api>=0.6.0
google-api-python-client>=2.100.0
python-dotenv>=1.0.0
tenacity>=8.2.0
redis>=5.0.0
celery>=5.3.0
websockets>=12.0
pydantic>=2.5.0
pydantic-settings>=2.0.0

# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# backend/.env.example
# API Keys
YOUTUBE_API_KEY=your_youtube_api_key
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
DEEPSEEK_API_KEY=your_deepseek_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key

# Redis
REDIS_URL=redis://localhost:6379

# Application
SECRET_KEY=your_secret_key_here
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# API Rate Limits
YOUTUBE_QUOTA_PER_DAY=10000
SPOTIFY_RATE_LIMIT=180