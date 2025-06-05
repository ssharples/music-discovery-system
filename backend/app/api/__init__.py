"""
API routes and handlers for the Music Discovery System
"""

from .routes import router as api_router
from . import websocket

__all__ = ["api_router", "websocket"] 