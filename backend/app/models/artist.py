# backend/app/models/artist.py
from pydantic import BaseModel, Field, UUID4
from typing import List, Optional, Dict, Any
from datetime import datetime

class ArtistProfile(BaseModel):
    """Artist profile model"""
    id: Optional[UUID4] = None
    name: str
    youtube_channel_id: Optional[str] = None
    youtube_channel_name: Optional[str] = None
    instagram_handle: Optional[str] = None
    spotify_id: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    bio: Optional[str] = None
    follower_counts: Dict[str, int] = Field(default_factory=dict)
    social_links: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    discovery_date: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    enrichment_score: float = Field(default=0.0, ge=0, le=1)
    status: str = "discovered"

class VideoMetadata(BaseModel):
    """YouTube video metadata"""
    id: Optional[UUID4] = None
    artist_id: Optional[UUID4] = None
    youtube_video_id: str
    title: str
    description: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    published_at: Optional[datetime] = None
    duration: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    captions_available: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class LyricAnalysis(BaseModel):
    """Lyric analysis results"""
    id: Optional[UUID4] = None
    video_id: UUID4
    artist_id: UUID4
    themes: List[str] = Field(default_factory=list)
    sentiment_score: float = Field(default=0.0, ge=-1, le=1)
    emotional_content: List[str] = Field(default_factory=list)
    lyrical_style: Optional[str] = None
    subject_matter: Optional[str] = None
    language: str = "en"
    analysis_metadata: Dict[str, Any] = Field(default_factory=dict)

class EnrichedArtistData(BaseModel):
    """Complete enriched artist data"""
    profile: ArtistProfile
    videos: List[VideoMetadata] = Field(default_factory=list)
    lyric_analyses: List[LyricAnalysis] = Field(default_factory=list)
    enrichment_score: float = Field(ge=0, le=1)
    discovery_session_id: Optional[UUID4] = None

class DiscoveryRequest(BaseModel):
    """Discovery request model"""
    search_query: str = "official music video"
    max_results: int = Field(default=50, le=100)
    filters: Dict[str, Any] = Field(default_factory=dict)
    
class DiscoveryResponse(BaseModel):
    """Discovery response model"""
    session_id: UUID4
    status: str
    message: str
    artists_found: int = 0

class DiscoverySession(BaseModel):
    """Discovery session model"""
    id: Optional[UUID4] = None
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    artists_discovered: int = 0
    videos_processed: int = 0
    status: str = "running"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_logs: List[str] = Field(default_factory=list) 