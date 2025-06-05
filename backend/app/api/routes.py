# backend/app/api/routes.py
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from uuid import UUID
import logging

from app.models.artist import (
    ArtistProfile, DiscoveryRequest, DiscoveryResponse,
    EnrichedArtistData, VideoMetadata, LyricAnalysis
)
from app.core.dependencies import get_pipeline_deps, PipelineDependencies
from app.agents.orchestrator import DiscoveryOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/discover", response_model=DiscoveryResponse)
async def start_discovery(
    request: DiscoveryRequest,
    background_tasks: BackgroundTasks,
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Start a new discovery session"""
    logger.info(f"🚀 Discovery request received: query='{request.search_query}', max_results={request.max_results}")
    logger.info(f"🔍 Request object: {request}")
    logger.info(f"🔍 Dependencies: {deps}")
    logger.info(f"🔍 Background tasks: {background_tasks}")
    
    try:
        logger.info("⚡ About to create DiscoveryOrchestrator instance...")
        orchestrator = DiscoveryOrchestrator()
        logger.info("✅ DiscoveryOrchestrator created successfully")
        
        logger.info("⚡ About to start discovery session...")
        session_id = await orchestrator.start_discovery_session(
            request, deps, background_tasks
        )
        logger.info(f"✅ Discovery session created successfully: {session_id}")
        
        logger.info("⚡ About to return response...")
        response = DiscoveryResponse(
            session_id=session_id,
            status="started",
            message="Discovery session started successfully"
        )
        logger.info(f"✅ Response created: {response}")
        return response
    except Exception as e:
        logger.error(f"❌ Error starting discovery: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/artists", response_model=List[ArtistProfile])
async def get_artists(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Get discovered artists"""
    try:
        query = deps.supabase.table("artists").select("*")
        
        if status:
            query = query.eq("status", status)
        if min_score is not None:
            query = query.gte("enrichment_score", min_score)
            
        query = query.range(skip, skip + limit - 1)
        result = query.execute()
        
        return [ArtistProfile(**artist) for artist in result.data]
    except Exception as e:
        logger.error(f"Error fetching artists: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/artist/{artist_id}", response_model=EnrichedArtistData)
async def get_artist_details(
    artist_id: UUID,
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Get detailed artist information"""
    try:
        # Fetch artist profile
        artist_result = deps.supabase.table("artists").select("*").eq("id", str(artist_id)).single().execute()
        if not artist_result.data:
            raise HTTPException(status_code=404, detail="Artist not found")
            
        # Fetch videos
        videos_result = deps.supabase.table("videos").select("*").eq("artist_id", str(artist_id)).execute()
        
        # Fetch lyric analyses
        analyses_result = deps.supabase.table("lyric_analyses").select("*").eq("artist_id", str(artist_id)).execute()
        
        return EnrichedArtistData(
            profile=ArtistProfile(**artist_result.data),
            videos=[VideoMetadata(**v) for v in videos_result.data],
            lyric_analyses=[LyricAnalysis(**a) for a in analyses_result.data],
            enrichment_score=artist_result.data.get("enrichment_score", 0)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching artist details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics")
async def get_analytics(
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Get discovery analytics"""
    try:
        # Get artist statistics
        artists_count = deps.supabase.table("artists").select("count", count="exact").execute()
        
        # Get high-value artists
        high_value = deps.supabase.table("artists").select("count", count="exact").gte("enrichment_score", 0.7).execute()
        
        # Get recent discoveries
        recent = deps.supabase.table("artists").select("*").order("discovery_date", desc=True).limit(10).execute()
        
        # Get genre distribution - fallback if RPC doesn't exist
        try:
            genre_stats = deps.supabase.rpc("get_genre_distribution").execute()
            genre_data = genre_stats.data
        except:
            # Fallback: manually compute genre distribution
            all_artists = deps.supabase.table("artists").select("genres").execute()
            genre_count = {}
            for artist in all_artists.data:
                genres = artist.get('genres', [])
                for genre in genres:
                    genre_count[genre] = genre_count.get(genre, 0) + 1
            genre_data = [{"genre": k, "count": v} for k, v in genre_count.items()]
        
        return {
            "total_artists": artists_count.count,
            "high_value_artists": high_value.count,
            "recent_discoveries": [ArtistProfile(**a) for a in recent.data],
            "genre_distribution": genre_data,
            "api_usage": {
                "youtube": await get_api_usage(deps, "youtube"),
                "spotify": await get_api_usage(deps, "spotify")
            }
        }
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_api_usage(deps: PipelineDependencies, api_name: str):
    """Get API usage statistics"""
    try:
        result = deps.supabase.table("api_rate_limits").select("*").eq("api_name", api_name).execute()
        if result.data:
            return result.data[0]
        return {"requests_made": 0, "quota_limit": 0}
    except:
        return {"requests_made": 0, "quota_limit": 0}

@router.get("/sessions")
async def get_discovery_sessions(
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Get discovery session history"""
    try:
        result = deps.supabase.table("discovery_sessions").select("*").order("started_at", desc=True).limit(20).execute()
        return result.data
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}")
async def get_session_details(
    session_id: UUID,
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Get detailed session information"""
    try:
        result = deps.supabase.table("discovery_sessions").select("*").eq("id", str(session_id)).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")
        return result.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 