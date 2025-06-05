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
        _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("Initialized Supabase client")
    return _supabase

async def get_redis() -> redis.Redis:
    """Get Redis client instance"""
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30
        )
        logger.info("Initialized Redis client")
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