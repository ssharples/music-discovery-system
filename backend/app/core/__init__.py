"""
Core utilities and configuration for the Music Discovery System
"""

from .config import settings
from .dependencies import get_pipeline_deps, PipelineDependencies

__all__ = ["settings", "get_pipeline_deps", "PipelineDependencies"] 