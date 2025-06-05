# backend/app/core/config.py
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import List, Optional, Union
import os

class Settings(BaseSettings):
    """Application settings"""
    # API Keys (optional for basic deployment)
    YOUTUBE_API_KEY: str = Field("", env="YOUTUBE_API_KEY")
    SPOTIFY_CLIENT_ID: str = Field("", env="SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET: str = Field("", env="SPOTIFY_CLIENT_SECRET")
    DEEPSEEK_API_KEY: str = Field("", env="DEEPSEEK_API_KEY")
    FIRECRAWL_API_KEY: str = Field("", env="FIRECRAWL_API_KEY")
    
    # Supabase (optional for basic deployment)
    SUPABASE_URL: str = Field("", env="SUPABASE_URL")
    SUPABASE_KEY: str = Field("", env="SUPABASE_KEY")
    
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
    MAX_DISCOVERY_RESULTS: int = Field(100, env="MAX_DISCOVERY_RESULTS")
    DISCOVERY_BATCH_SIZE: int = Field(10, env="DISCOVERY_BATCH_SIZE")
    
    # Monitoring
    SENTRY_DSN: Optional[str] = Field(None, env="SENTRY_DSN")
    
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
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }
    
    def is_supabase_configured(self) -> bool:
        """Check if Supabase is properly configured"""
        return bool(self.SUPABASE_URL and self.SUPABASE_KEY)
    
    def is_youtube_configured(self) -> bool:
        """Check if YouTube API is properly configured"""
        return bool(self.YOUTUBE_API_KEY)
    
    def is_spotify_configured(self) -> bool:
        """Check if Spotify API is properly configured"""
        return bool(self.SPOTIFY_CLIENT_ID and self.SPOTIFY_CLIENT_SECRET)
    
    def is_deepseek_configured(self) -> bool:
        """Check if DeepSeek API is properly configured"""
        return bool(self.DEEPSEEK_API_KEY)

settings = Settings() 