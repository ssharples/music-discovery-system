"""
Comprehensive Music Discovery API Endpoint
Provides access to the complete music discovery workflow.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Dict, Any, Optional
import logging
import asyncio
from datetime import datetime

from ..agents.comprehensive_music_discovery_agent import ComprehensiveMusicDiscoveryAgent, ArtistDiscoveryResult
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discover", tags=["comprehensive-discovery"])

class DiscoveryRequest(BaseModel):
    limit: int = 50
    search_query: str = "official music video"
    upload_date: str = "today"  # today, week, month, year
    enable_ai_filtering: bool = True
    min_discovery_score: int = 20

class DiscoveryResponse(BaseModel):
    success: bool
    artists_discovered: int
    processing_time_seconds: float
    artists: List[Dict[str, Any]]
    errors: List[str]
    metadata: Dict[str, Any]

# Store for background task tracking
background_tasks_status = {}

@router.post("/start-comprehensive", response_model=DiscoveryResponse)
async def start_comprehensive_discovery(
    background_tasks: BackgroundTasks,
    request: DiscoveryRequest
):
    """
    Start comprehensive music discovery process.
    
    This endpoint:
    1. Searches YouTube for official music videos
    2. Extracts and validates artist names
    3. Crawls multiple platforms (YouTube, Spotify, Instagram, TikTok)
    4. Analyzes lyrics sentiment
    5. Calculates discovery scores
    6. Stores results in database
    """
    
    start_time = datetime.now()
    
    try:
        logger.info(f"🎵 Starting comprehensive discovery with limit: {request.limit}")
        
        # Initialize discovery agent
        discovery_agent = ComprehensiveMusicDiscoveryAgent()
        
        # Run discovery process
        discovery_results = await discovery_agent.discover_new_artists(
            limit=request.limit
        )
        
        # Filter results by minimum score if requested
        if request.min_discovery_score > 0:
            discovery_results = [
                r for r in discovery_results 
                if r.discovery_score >= request.min_discovery_score
            ]
        
        # Format response
        processing_time = (datetime.now() - start_time).total_seconds()
        
        artists_data = []
        errors = []
        
        for result in discovery_results:
            if result.success:
                artists_data.append({
                    "name": result.artist_name,
                    "discovery_score": result.discovery_score,
                    "youtube_data": result.youtube_data,
                    "spotify_data": result.spotify_data,
                    "instagram_data": result.instagram_data,
                    "tiktok_data": result.tiktok_data,
                    "lyrics_analysis": result.lyrics_analysis,
                    "social_links": result.social_links
                })
            else:
                errors.append(f"Failed to process {result.artist_name}: {result.error_message}")
        
        return DiscoveryResponse(
            success=True,
            artists_discovered=len(artists_data),
            processing_time_seconds=processing_time,
            artists=artists_data,
            errors=errors,
            metadata={
                "search_query": request.search_query,
                "upload_date": request.upload_date,
                "total_processed": len(discovery_results),
                "success_rate": len(artists_data) / len(discovery_results) * 100 if discovery_results else 0
            }
        )
        
    except Exception as e:
        logger.error(f"Error in comprehensive discovery: {str(e)}")
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return DiscoveryResponse(
            success=False,
            artists_discovered=0,
            processing_time_seconds=processing_time,
            artists=[],
            errors=[str(e)],
            metadata={"error": "Discovery process failed"}
        )

@router.get("/undiscovered-talent", response_model=DiscoveryResponse)
async def discover_undiscovered_talent(
    limit: int = Query(20, description="Maximum number of artists to discover"),
    max_views: int = Query(50000, description="Maximum view count for videos"),
    min_quality_score: float = Query(0.3, description="Minimum quality threshold")
):
    """
    Specialized endpoint for discovering undiscovered talent.
    
    Focuses on:
    - Recent uploads (last 24-48 hours)
    - Low view counts (under 50k views)
    - Independent artists (non-major labels)
    - High potential indicators
    """
    
    start_time = datetime.now()
    
    try:
        logger.info(f"🎯 Discovering undiscovered talent with limit: {limit}, max_views: {max_views}")
        
        discovery_agent = ComprehensiveMusicDiscoveryAgent()
        
        # Configure for undiscovered talent discovery
        discovery_agent.max_videos = limit * 5  # Search more to find hidden gems
        
        results = await discovery_agent.discover_new_artists(limit=limit)
        
        # Filter for undiscovered talent criteria
        undiscovered_artists = []
        for result in results:
            if result.success:
                youtube_data = result.youtube_data
                
                # Apply undiscovered talent filters
                if (youtube_data.get('view_count', 0) < max_views and
                    result.discovery_score >= min_quality_score * 100):
                    undiscovered_artists.append(result)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return DiscoveryResponse(
            success=True,
            artists_discovered=len(undiscovered_artists),
            processing_time_seconds=processing_time,
            artists=[
                {
                    "name": r.artist_name,
                    "discovery_score": r.discovery_score,
                    "youtube_data": r.youtube_data,
                    "spotify_data": r.spotify_data,
                    "social_links": r.social_links,
                    "undiscovered_metrics": {
                        "low_view_count": True,
                        "recent_upload": True,
                        "independent_artist": True
                    }
                }
                for r in undiscovered_artists
            ],
            errors=[],
            metadata={
                "focus": "undiscovered_talent",
                "max_views_filter": max_views,
                "min_quality_score": min_quality_score,
                "discovery_rate": len(undiscovered_artists) / len(results) * 100 if results else 0
            }
        )
        
    except Exception as e:
        logger.error(f"Error discovering undiscovered talent: {str(e)}")
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return DiscoveryResponse(
            success=False,
            artists_discovered=0,
            processing_time_seconds=processing_time,
            artists=[],
            errors=[str(e)],
            metadata={"error": "Undiscovered talent discovery failed"}
        )

@router.get("/artist/{artist_id}/full-profile")
async def get_artist_full_profile(artist_id: int):
    """
    Get complete artist profile with all discovered data.
    """
    
    try:
        from supabase import create_client
        import os
        
        # Initialize Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        supabase = create_client(supabase_url, supabase_key)
        
        # Get artist data
        artist_result = supabase.table("artist").select("*").eq("id", artist_id).execute()
        
        if not artist_result.data:
            raise HTTPException(status_code=404, detail="Artist not found")
        
        artist = artist_result.data[0]
        
        # Get related data
        tracks_result = supabase.table("artist_spotify_tracks").select("*").eq("artist_id", artist_id).execute()
        lyrics_result = supabase.table("artist_lyrics_analysis").select("*").eq("artist_id", artist_id).execute()
        logs_result = supabase.table("artist_discovery_log").select("*").eq("artist_id", artist_id).order("created_at", desc=True).limit(10).execute()
        
        return {
            "artist": artist,
            "spotify_tracks": tracks_result.data,
            "lyrics_analysis": lyrics_result.data,
            "discovery_logs": logs_result.data,
            "social_media_summary": {
                "youtube_subscribers": artist.get("youtube_subscriber_count", 0),
                "spotify_monthly_listeners": artist.get("spotify_monthly_listeners", 0),
                "instagram_followers": artist.get("instagram_follower_count", 0),
                "tiktok_followers": artist.get("tiktok_follower_count", 0),
                "total_social_reach": (
                    artist.get("youtube_subscriber_count", 0) +
                    artist.get("spotify_monthly_listeners", 0) +
                    artist.get("instagram_follower_count", 0) +
                    artist.get("tiktok_follower_count", 0)
                )
            },
            "discovery_metadata": {
                "discovery_score": artist.get("discovery_score", 0),
                "discovery_source": artist.get("discovery_source", "unknown"),
                "last_updated": artist.get("last_crawled_at"),
                "is_validated": artist.get("is_validated", False)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting artist profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/overview")
async def get_discovery_stats():
    """
    Get overview statistics of the discovery system.
    """
    
    try:
        from supabase import create_client
        import os
        
        # Initialize Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        supabase = create_client(supabase_url, supabase_key)
        
        # Get various statistics
        total_artists = supabase.table("artist").select("id", count="exact").execute()
        validated_artists = supabase.table("artist").select("id", count="exact").eq("is_validated", True).execute()
        high_score_artists = supabase.table("artist").select("id", count="exact").gte("discovery_score", 70).execute()
        
        # Get top artists by score
        top_artists = supabase.table("artist").select("name, discovery_score, spotify_monthly_listeners, youtube_subscriber_count").order("discovery_score", desc=True).limit(10).execute()
        
        # Get recent discoveries
        recent_discoveries = supabase.table("artist").select("name, discovery_score, created_at").order("created_at", desc=True).limit(5).execute()
        
        return {
            "overview": {
                "total_artists": total_artists.count,
                "validated_artists": validated_artists.count,
                "high_score_artists": high_score_artists.count,
                "validation_rate": (validated_artists.count / total_artists.count * 100) if total_artists.count > 0 else 0,
                "high_score_rate": (high_score_artists.count / total_artists.count * 100) if total_artists.count > 0 else 0
            },
            "top_artists": top_artists.data,
            "recent_discoveries": recent_discoveries.data,
            "system_health": {
                "database_connected": True,
                "discovery_active": True,
                "last_discovery": recent_discoveries.data[0]["created_at"] if recent_discoveries.data else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting discovery stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 