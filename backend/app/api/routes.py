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
from app.agents.youtube_agent import YouTubeDiscoveryAgent

logger = logging.getLogger(__name__)
router = APIRouter()

# Global flag to control enrichment version
USE_V2_ENRICHMENT = True

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
        orchestrator = DiscoveryOrchestrator(use_v2_enrichment=USE_V2_ENRICHMENT)
        logger.info(f"✅ DiscoveryOrchestrator created successfully (V2 enrichment: {USE_V2_ENRICHMENT})")
        
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

@router.post("/discover/undiscovered-talent")
async def discover_undiscovered_talent(
    max_results: int = 50,
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """
    Discover undiscovered talent with specific criteria:
    - Official music videos uploaded in the last 24 hours
    - Videos with less than 50k views
    - Independent/unsigned artists
    """
    logger.info(f"🎯 Undiscovered talent discovery request: max_results={max_results}")
    
    try:
        orchestrator = DiscoveryOrchestrator(use_v2_enrichment=USE_V2_ENRICHMENT)
        result = await orchestrator.discover_undiscovered_talent(
            deps=deps,
            max_results=max_results
        )
        
        logger.info(f"✅ Undiscovered talent discovery completed: {result['data']['total_found']} artists found")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in undiscovered talent discovery: {e}", exc_info=True)
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

@router.post("/session/{session_id}/pause")
async def pause_discovery_session(
    session_id: UUID,
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Pause a running discovery session"""
    try:
        from app.agents.orchestrator import DiscoveryOrchestrator
        orchestrator = DiscoveryOrchestrator(use_v2_enrichment=USE_V2_ENRICHMENT)
        result = await orchestrator.pause_session(str(session_id), deps)
        return result
    except Exception as e:
        logger.error(f"Error pausing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/session/{session_id}/resume")
async def resume_discovery_session(
    session_id: UUID,
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Resume a paused discovery session"""
    try:
        from app.agents.orchestrator import DiscoveryOrchestrator
        orchestrator = DiscoveryOrchestrator(use_v2_enrichment=USE_V2_ENRICHMENT)
        result = await orchestrator.resume_session(str(session_id), deps)
        return result
    except Exception as e:
        logger.error(f"Error resuming session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/session/{session_id}/stop")
async def stop_discovery_session(
    session_id: UUID,
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Stop a running discovery session"""
    try:
        from app.agents.orchestrator import DiscoveryOrchestrator
        orchestrator = DiscoveryOrchestrator(use_v2_enrichment=USE_V2_ENRICHMENT)
        result = await orchestrator.stop_session(str(session_id), deps)
        return result
    except Exception as e:
        logger.error(f"Error stopping session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}/status")
async def get_session_status(
    session_id: UUID
):
    """Get current status of a discovery session"""
    try:
        from app.agents.orchestrator import DiscoveryOrchestrator
        orchestrator = DiscoveryOrchestrator(use_v2_enrichment=USE_V2_ENRICHMENT)
        result = await orchestrator.get_session_status(str(session_id))
        return result
    except Exception as e:
        logger.error(f"Error getting session status {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/config")
async def debug_config(
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Debug endpoint to check configuration and dependencies"""
    try:
        from app.core.config import settings
        
        config_status = {
            "youtube_configured": settings.is_youtube_configured(),
            "deepseek_configured": settings.is_deepseek_configured(),
            "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
            "redis_configured": bool(settings.REDIS_URL),
            "youtube_api_key_present": bool(settings.YOUTUBE_API_KEY),
            "deepseek_api_key_present": bool(settings.DEEPSEEK_API_KEY),
        }
        
        # Test database connection
        try:
            test_result = deps.supabase.table("artists").select("count", count="exact").limit(1).execute()
            config_status["database_connection"] = "working"
            config_status["database_error"] = None
        except Exception as db_error:
            config_status["database_connection"] = "failed"
            config_status["database_error"] = str(db_error)
        
        # Test Redis connection
        try:
            await deps.redis_client.ping()
            config_status["redis_connection"] = "working"
            config_status["redis_error"] = None
        except Exception as redis_error:
            config_status["redis_connection"] = "failed"
            config_status["redis_error"] = str(redis_error)
        
        # Test quota manager
        try:
            from app.core import quota_manager
            quota_status = await quota_manager.get_quota_status()
            config_status["quota_manager"] = "working"
            config_status["quota_status"] = quota_status
        except Exception as quota_error:
            config_status["quota_manager"] = "failed"
            config_status["quota_error"] = str(quota_error)
        
        return config_status
        
    except Exception as e:
        logger.error(f"Debug config error: {e}")
        return {"error": str(e), "type": type(e).__name__}

@router.get("/debug/test-discovery")
async def test_discovery(
    deps: PipelineDependencies = Depends(get_pipeline_deps)
):
    """Test discovery pipeline components individually"""
    try:
        results = {}
        
        # Test 1: Basic orchestrator creation
        try:
            orchestrator = DiscoveryOrchestrator(use_v2_enrichment=USE_V2_ENRICHMENT)
            results["orchestrator_creation"] = f"success (V2 enrichment: {USE_V2_ENRICHMENT})"
        except Exception as e:
            results["orchestrator_creation"] = f"failed: {e}"
            return results
        
        # Test 2: YouTube agent creation
        try:
            youtube_agent = YouTubeDiscoveryAgent()
            results["youtube_agent_creation"] = "success"
        except Exception as e:
            results["youtube_agent_creation"] = f"failed: {e}"
            return results
        
        # Test 3: Quota manager check
        try:
            can_search = await orchestrator.quota_manager.can_perform_operation('youtube', 'search', 1)
            results["quota_check"] = f"can_search: {can_search}"
        except Exception as e:
            results["quota_check"] = f"failed: {e}"
        
        # Test 4: Simple YouTube search (if configured)
        try:
            from app.core.config import settings
            if settings.is_youtube_configured():
                search_results = await youtube_agent._search_channels(deps, "test music", 5)
                results["youtube_search"] = f"success: found {len(search_results)} channels"
            else:
                results["youtube_search"] = "skipped: YouTube not configured"
        except Exception as e:
            results["youtube_search"] = f"failed: {e}"
        
        # Test 5: Storage agent test
        try:
            storage_test = await orchestrator.storage_agent.get_high_value_artists(deps, min_score=0.0, limit=1)
            results["storage_test"] = f"success: got {len(storage_test)} results"
        except Exception as e:
            results["storage_test"] = f"failed: {e}"
        
        return results
        
    except Exception as e:
        logger.error(f"Test discovery error: {e}")
        return {"error": str(e), "type": type(e).__name__} 