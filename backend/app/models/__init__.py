"""
Data models for the Music Discovery System
"""

from .artist import (
    ArtistProfile,
    VideoMetadata,
    LyricAnalysis,
    EnrichedArtistData,
    DiscoveryRequest,
    DiscoveryResponse
)

__all__ = [
    "ArtistProfile",
    "VideoMetadata", 
    "LyricAnalysis",
    "EnrichedArtistData",
    "DiscoveryRequest",
    "DiscoveryResponse"
] 