# backend/app/core/config.py
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import List, Optional, Union
import os

class Settings(BaseSettings):
    """Application settings"""
    # API Keys (optional for basic deployment)
    YOUTUBE_API_KEY: str = Field("", env="YOUTUBE_API_KEY")  # Keeping for fallback/comparison
    SPOTIFY_CLIENT_ID: str = Field("", env="SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET: str = Field("", env="SPOTIFY_CLIENT_SECRET")
    DEEPSEEK_API_KEY: str = Field("", env="DEEPSEEK_API_KEY")
    FIRECRAWL_API_KEY: str = Field("", env="FIRECRAWL_API_KEY")  # Added for Firecrawl integration
    
    # Enhanced AI Provider Keys
    OPENAI_API_KEY: str = Field("", env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: str = Field("", env="ANTHROPIC_API_KEY")
    
    # Instagram/TikTok Authentication (for Crawl4AI session storage)
    INSTAGRAM_SESSION_FILE: str = Field("instagram_session.json", env="INSTAGRAM_SESSION_FILE")
    TIKTOK_SESSION_FILE: str = Field("tiktok_session.json", env="TIKTOK_SESSION_FILE")
    MUSIXMATCH_SESSION_FILE: str = Field("musixmatch_session.json", env="MUSIXMATCH_SESSION_FILE")
    
    # Crawl4AI Configuration
    CRAWL4AI_HEADLESS: bool = Field(True, env="CRAWL4AI_HEADLESS")
    CRAWL4AI_VIEWPORT_WIDTH: int = Field(1920, env="CRAWL4AI_VIEWPORT_WIDTH")
    CRAWL4AI_VIEWPORT_HEIGHT: int = Field(1080, env="CRAWL4AI_VIEWPORT_HEIGHT")
    CRAWL4AI_MAX_CONCURRENT: int = Field(5, env="CRAWL4AI_MAX_CONCURRENT")
    
    # Supabase (optional for basic deployment)
    SUPABASE_URL: str = Field("", env="SUPABASE_URL")
    SUPABASE_KEY: str = Field("", env="SUPABASE_ANON_KEY")  # Use SUPABASE_ANON_KEY as primary
    SUPABASE_ANON_KEY: str = Field("", env="SUPABASE_ANON_KEY")  # Keep both for compatibility
    SUPABASE_SERVICE_ROLE_KEY: str = Field("", env="SUPABASE_SERVICE_ROLE_KEY")
    
    # Redis
    REDIS_URL: str = Field("redis://localhost:6379", env="REDIS_URL")
    
    # Application
    ALLOWED_ORIGINS: Union[str, List[str]] = Field(
        default="http://localhost:3000,http://localhost:5173",
        env="ALLOWED_ORIGINS"
    )
    SECRET_KEY: str = Field("default-secret-key-change-in-production", env="SECRET_KEY")
    
    # Environment
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(False, env="DEBUG")
    
    # Rate Limits
    YOUTUBE_QUOTA_PER_DAY: int = Field(10000, env="YOUTUBE_QUOTA_PER_DAY")
    SPOTIFY_RATE_LIMIT: int = Field(180, env="SPOTIFY_RATE_LIMIT")  # per 30 seconds
    
    # Discovery Settings
    MAX_DISCOVERY_RESULTS: int = Field(1000, env="MAX_DISCOVERY_RESULTS")  # Increased for Crawl4AI
    DISCOVERY_BATCH_SIZE: int = Field(50, env="DISCOVERY_BATCH_SIZE")  # Increased batch size
    
    # Monitoring
    SENTRY_DSN: Optional[str] = Field(None, env="SENTRY_DSN")
    
    # HTTP Client Timeouts
    HTTP_CONNECT_TIMEOUT: int = Field(30, env="HTTP_CONNECT_TIMEOUT")
    HTTP_READ_TIMEOUT: int = Field(300, env="HTTP_READ_TIMEOUT")  # 5 minutes
    HTTP_POOL_TIMEOUT: int = Field(60, env="HTTP_POOL_TIMEOUT")
    
    @field_validator('ALLOWED_ORIGINS')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v):
        if len(v) < 32:
            # For development/demo purposes, pad the key
            return v + "0" * (32 - len(v))
        return v
    
    # Additional fields for music discovery system
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    CRAWL4AI_CACHE_DIR: str = Field("./cache", env="CRAWL4AI_CACHE_DIR")
    USER_AGENT_MODE: str = Field("random", env="USER_AGENT_MODE")
    MAX_CONCURRENT_CRAWLS: int = Field(5, env="MAX_CONCURRENT_CRAWLS")
    
    # Rate limiting for different platforms
    YOUTUBE_DELAY_MIN: float = Field(1.0, env="YOUTUBE_DELAY_MIN")
    YOUTUBE_DELAY_MAX: float = Field(3.0, env="YOUTUBE_DELAY_MAX")
    SPOTIFY_DELAY_MIN: float = Field(0.5, env="SPOTIFY_DELAY_MIN")
    SPOTIFY_DELAY_MAX: float = Field(1.5, env="SPOTIFY_DELAY_MAX")
    INSTAGRAM_DELAY_MIN: float = Field(2.0, env="INSTAGRAM_DELAY_MIN")
    INSTAGRAM_DELAY_MAX: float = Field(4.0, env="INSTAGRAM_DELAY_MAX")
    TIKTOK_DELAY_MIN: float = Field(2.0, env="TIKTOK_DELAY_MIN")
    TIKTOK_DELAY_MAX: float = Field(4.0, env="TIKTOK_DELAY_MAX")
    
    # Discovery configuration
    MAX_VIDEOS_PER_SEARCH: int = Field(1000, env="MAX_VIDEOS_PER_SEARCH")
    DISCOVERY_SCORE_THRESHOLD: int = Field(30, env="DISCOVERY_SCORE_THRESHOLD")
    BATCH_SIZE: int = Field(50, env="BATCH_SIZE")
    ENABLE_PARALLEL_PROCESSING: bool = Field(True, env="ENABLE_PARALLEL_PROCESSING")
    
    # Content filtering
    EXCLUDE_AI_KEYWORDS: str = Field('["ai", "suno", "generated", "udio", "cover", "remix", "artificial intelligence", "ai-generated"]', env="EXCLUDE_AI_KEYWORDS")
    MIN_SUBSCRIBER_COUNT: int = Field(1000, env="MIN_SUBSCRIBER_COUNT")
    MIN_SPOTIFY_MONTHLY_LISTENERS: int = Field(10000, env="MIN_SPOTIFY_MONTHLY_LISTENERS")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "allow"  # Allow extra fields from environment
    }
    
    def is_supabase_configured(self) -> bool:
        """Check if Supabase is properly configured"""
        # Check for either SUPABASE_KEY or SUPABASE_ANON_KEY
        return bool(self.SUPABASE_URL and (self.SUPABASE_KEY or self.SUPABASE_ANON_KEY))
    
    def is_youtube_configured(self) -> bool:
        """Check if YouTube API is properly configured"""
        return bool(self.YOUTUBE_API_KEY)
    
    def is_spotify_configured(self) -> bool:
        """Check if Spotify API is properly configured"""
        return bool(self.SPOTIFY_CLIENT_ID and self.SPOTIFY_CLIENT_SECRET)
    
    def is_deepseek_configured(self) -> bool:
        """Check if DeepSeek API is properly configured"""
        return bool(self.DEEPSEEK_API_KEY)
    
    def is_openai_configured(self) -> bool:
        """Check if OpenAI API is properly configured"""
        return bool(self.OPENAI_API_KEY)
    
    def is_anthropic_configured(self) -> bool:
        """Check if Anthropic API is properly configured"""
        return bool(self.ANTHROPIC_API_KEY)
    
    def get_available_ai_providers(self) -> List[str]:
        """Get list of configured AI providers"""
        providers = []
        if self.is_deepseek_configured():
            providers.append("deepseek")
        if self.is_openai_configured():
            providers.append("openai")
        if self.is_anthropic_configured():
            providers.append("anthropic")
        return providers

settings = Settings() 