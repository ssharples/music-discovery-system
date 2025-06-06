"""
Core utilities and configuration for the Music Discovery System
"""

from .config import settings
from .dependencies import get_pipeline_deps, PipelineDependencies
from .quota_manager import quota_manager, response_cache, deduplication_manager

__all__ = [
    "settings", 
    "get_pipeline_deps", 
    "PipelineDependencies",
    "quota_manager",
    "response_cache", 
    "deduplication_manager"
] 