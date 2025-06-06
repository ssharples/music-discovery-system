# backend/app/core/dependencies.py
from typing import NamedTuple
from supabase import create_client, Client
import redis.asyncio as redis
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class PipelineDependencies(NamedTuple):
    """Dependencies for agent pipeline"""
    supabase: Client
    redis_client: redis.Redis
    http_client: httpx.AsyncClient
    youtube_api_key: str
    spotify_client_id: str
    spotify_client_secret: str
    deepseek_api_key: str
    firecrawl_api_key: str

# Global instances for reuse
_supabase: Client = None
_redis: redis.Redis = None
_http_client: httpx.AsyncClient = None

def get_supabase() -> Client:
    """Get Supabase client instance"""
    global _supabase
    if _supabase is None:
        if not settings.is_supabase_configured():
            logger.warning("Supabase not configured, using mock client")
            # Create a mock client for testing/development
            from unittest.mock import MagicMock
            _supabase = MagicMock()
            # Add table method that returns a mock with common methods
            _supabase.table = lambda name: MagicMock()
        else:
            # Use service role key if available for backend operations
            supabase_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', None) or settings.SUPABASE_KEY
            _supabase = create_client(settings.SUPABASE_URL, supabase_key)
            logger.info(f"Initialized Supabase client with {'service role' if hasattr(settings, 'SUPABASE_SERVICE_ROLE_KEY') else 'anon'} key")
    return _supabase

async def get_redis() -> redis.Redis:
    """Get Redis client instance"""
    global _redis
    if _redis is None:
        try:
            _redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                health_check_interval=30
            )
            # Test the connection
            await _redis.ping()
            logger.info("Initialized Redis client")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using mock client")
            # Create a mock Redis client for testing/development
            from unittest.mock import MagicMock, AsyncMock
            _redis = AsyncMock()
            _redis.ping = AsyncMock(return_value=True)
            _redis.get = AsyncMock(return_value=None)
            _redis.set = AsyncMock(return_value=True)
            _redis.delete = AsyncMock(return_value=True)
            _redis.close = AsyncMock()
    return _redis

def get_http_client() -> httpx.AsyncClient:
    """Get HTTP client instance"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
        logger.info("Initialized HTTP client")
    return _http_client

async def get_pipeline_deps() -> PipelineDependencies:
    """Get pipeline dependencies"""
    return PipelineDependencies(
        supabase=get_supabase(),
        redis_client=await get_redis(),
        http_client=get_http_client(),
        youtube_api_key=settings.YOUTUBE_API_KEY,
        spotify_client_id=settings.SPOTIFY_CLIENT_ID,
        spotify_client_secret=settings.SPOTIFY_CLIENT_SECRET,
        deepseek_api_key=settings.DEEPSEEK_API_KEY,
        firecrawl_api_key=settings.FIRECRAWL_API_KEY
    )

async def cleanup_dependencies():
    """Cleanup global dependencies on shutdown"""
    global _redis, _http_client
    
    if _redis:
        await _redis.close()
        logger.info("Closed Redis connection")
    
    if _http_client:
        await _http_client.aclose()
        logger.info("Closed HTTP client") 