# backend/app/agents/orchestrator.py
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import Dict, Any, List, Optional
from uuid import uuid4, UUID
import logging
import asyncio
from datetime import datetime
from fastapi import BackgroundTasks

from app.core.dependencies import PipelineDependencies
from app.models.artist import (
    DiscoveryRequest, ArtistProfile, VideoMetadata, 
    LyricAnalysis, EnrichedArtistData
)
from app.agents.youtube_agent import YouTubeDiscoveryAgent
from app.agents.enrichment_agent import ArtistEnrichmentAgent
from app.agents.lyrics_agent import LyricsAnalysisAgent
from app.agents.storage_agent import StorageAgent

logger = logging.getLogger(__name__)

# Create Orchestrator Agent
orchestrator_agent = Agent(
    model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
    system_prompt="""You are the orchestrator for a music artist discovery system. Your role is to:
    1. Coordinate the discovery process across multiple agents
    2. Ensure efficient use of API quotas and rate limits
    3. Prioritize high-value artist discoveries
    4. Monitor and report on discovery progress
    5. Handle errors gracefully and retry when appropriate
    
    Focus on discovering emerging artists with:
    - Strong engagement potential
    - Available contact information
    - Active on multiple platforms
    - Consistent content creation
    """
)

class DiscoveryOrchestrator:
    """Main orchestrator for the discovery pipeline"""
    
    def __init__(self):
        self.youtube_agent = YouTubeDiscoveryAgent()
        self.enrichment_agent = ArtistEnrichmentAgent()
        self.lyrics_agent = LyricsAnalysisAgent()
        self.storage_agent = StorageAgent()
        
    async def start_discovery_session(
        self,
        request: DiscoveryRequest,
        deps: PipelineDependencies,
        background_tasks: BackgroundTasks
    ) -> UUID:
        """Start a new discovery session"""
        
        # Create session in database
        session_id = uuid4()
        session_data = {
            "id": str(session_id),
            "started_at": datetime.now().isoformat(),
            "status": "running",
            "metadata": {
                "search_query": request.search_query,
                "max_results": request.max_results,
                "filters": request.filters
            }
        }
        
        # Store session
        await self.storage_agent.create_discovery_session(deps, session_data)
        
        # Start discovery in background
        background_tasks.add_task(
            self._run_discovery_pipeline,
            session_id,
            request,
            deps
        )
        
        return session_id
        
    async def _run_discovery_pipeline(
        self,
        session_id: UUID,
        request: DiscoveryRequest,
        deps: PipelineDependencies
    ):
        """Run the complete discovery pipeline"""
        
        try:
            logger.info(f"Starting discovery pipeline for session {session_id}")
            
            # Phase 1: YouTube Discovery
            discovered_channels = await self._discover_youtube_artists(
                deps, request.search_query, request.max_results
            )
            
            logger.info(f"Discovered {len(discovered_channels)} potential artists")
            
            # Phase 2: Process each artist
            enriched_artists = []
            for channel_data in discovered_channels:
                try:
                    enriched_artist = await self._process_artist(
                        deps, channel_data, session_id
                    )
                    if enriched_artist:
                        enriched_artists.append(enriched_artist)
                        
                except Exception as e:
                    logger.error(f"Error processing artist {channel_data['channel_title']}: {e}")
                    continue
                    
                # Small delay to respect rate limits
                await asyncio.sleep(2)
                
            # Update session status
            await self.storage_agent.update_discovery_session(
                deps,
                str(session_id),
                {
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                    "artists_discovered": len(enriched_artists),
                    "videos_processed": sum(len(a.videos) for a in enriched_artists)
                }
            )
            
            logger.info(f"Discovery session {session_id} completed. Found {len(enriched_artists)} artists")
            
        except Exception as e:
            logger.error(f"Discovery pipeline error: {e}")
            await self.storage_agent.update_discovery_session(
                deps,
                str(session_id),
                {
                    "status": "failed",
                    "completed_at": datetime.now().isoformat(),
                    "error_logs": [str(e)]
                }
            )
            
    async def _discover_youtube_artists(
        self,
        deps: PipelineDependencies,
        query: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Discover artists on YouTube"""
        
        # Check API quota
        quota_available = await self._check_youtube_quota(deps)
        if quota_available < 100:
            logger.warning(f"Low YouTube quota: {quota_available}")
            max_results = min(max_results, 10)
            
        # Discover artists
        channels = await self.youtube_agent.discover_artists(
            deps, query, max_results
        )
        
        # Update quota usage
        await self._update_api_usage(deps, "youtube", len(channels) * 2)
        
        return channels
        
    async def _process_artist(
        self,
        deps: PipelineDependencies,
        channel_data: Dict[str, Any],
        session_id: UUID
    ) -> Optional[EnrichedArtistData]:
        """Process a single artist through the enrichment pipeline"""
        
        try:
            artist_name = channel_data['channel_title']
            channel_id = channel_data['channel_id']
            
            logger.info(f"Processing artist: {artist_name}")
            
            # Phase 1: Basic enrichment
            artist_profile = await self.enrichment_agent.enrich_artist(
                deps,
                artist_name,
                channel_id,
                f"https://youtube.com/channel/{channel_id}"
            )
            
            # Phase 2: Get videos with captions
            videos_with_captions = await self.youtube_agent.get_artist_videos_with_captions(
                deps, channel_id, max_videos=5
            )
            
            # Convert to VideoMetadata objects
            video_metadata = []
            for video in videos_with_captions:
                vm = VideoMetadata(
                    youtube_video_id=video['video_id'],
                    title=video['title'],
                    description=video.get('description', ''),
                    view_count=video.get('view_count', 0),
                    like_count=video.get('like_count', 0),
                    published_at=datetime.fromisoformat(video['published_at'].replace('Z', '+00:00')),
                    tags=video.get('tags', []),
                    captions_available=video.get('captions_available', False)
                )
                video_metadata.append(vm)
                
            # Phase 3: Store artist profile
            stored_artist = await self.storage_agent.store_artist_profile(
                deps, artist_profile
            )
            
            if not stored_artist:
                return None
                
            artist_id = stored_artist['id']
            
            # Phase 4: Store videos
            for video in video_metadata:
                video.artist_id = artist_id
                await self.storage_agent.store_video(deps, video)
                
            # Phase 5: Analyze lyrics if captions available
            lyric_analyses = []
            if any(v.get('captions') for v in videos_with_captions):
                analyses = await self.lyrics_agent.analyze_artist_lyrics(
                    deps, artist_id, videos_with_captions
                )
                
                # Store analyses
                for analysis in analyses:
                    stored = await self.storage_agent.store_lyric_analysis(
                        deps, analysis
                    )
                    if stored:
                        lyric_analyses.append(analysis)
                        
            # Phase 6: Generate artist summary
            if lyric_analyses:
                summary = await self.lyrics_agent.generate_artist_summary(
                    deps, artist_name, lyric_analyses
                )
                
                # Update artist profile with summary
                await self.storage_agent.update_artist_profile(
                    deps, artist_id, {"metadata": {"lyrical_summary": summary}}
                )
                
            # Return enriched data
            return EnrichedArtistData(
                profile=artist_profile,
                videos=video_metadata,
                lyric_analyses=lyric_analyses,
                enrichment_score=artist_profile.enrichment_score,
                discovery_session_id=session_id
            )
            
        except Exception as e:
            logger.error(f"Artist processing error: {e}")
            return None
            
    async def _check_youtube_quota(self, deps: PipelineDependencies) -> int:
        """Check remaining YouTube API quota"""
        
        result = await deps.supabase.table("api_rate_limits").select("*").eq("api_name", "youtube").execute()
        
        if result.data:
            quota_data = result.data[0]
            used = quota_data.get("requests_made", 0)
            limit = quota_data.get("quota_limit", 10000)
            
            # Check if we need to reset (daily quota)
            reset_time = datetime.fromisoformat(quota_data.get("reset_time", datetime.now().isoformat()))
            if datetime.now() > reset_time:
                # Reset quota
                await self._reset_api_quota(deps, "youtube")
                return limit
                
            return limit - used
            
        return 10000  # Default quota
        
    async def _update_api_usage(
        self,
        deps: PipelineDependencies,
        api_name: str,
        units: int
    ):
        """Update API usage tracking"""
        
        result = await deps.supabase.table("api_rate_limits").select("*").eq("api_name", api_name).execute()
        
        if result.data:
            # Update existing
            current = result.data[0]
            await deps.supabase.table("api_rate_limits").update({
                "requests_made": current["requests_made"] + units,
                "last_request": datetime.now().isoformat()
            }).eq("id", current["id"]).execute()
        else:
            # Create new
            await deps.supabase.table("api_rate_limits").insert({
                "api_name": api_name,
                "requests_made": units,
                "quota_limit": 10000 if api_name == "youtube" else 1000,
                "reset_time": (datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)).isoformat(),
                "last_request": datetime.now().isoformat()
            }).execute()
            
    async def _reset_api_quota(self, deps: PipelineDependencies, api_name: str):
        """Reset API quota"""
        
        await deps.supabase.table("api_rate_limits").update({
            "requests_made": 0,
            "reset_time": (datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)).isoformat()
        }).eq("api_name", api_name).execute()
        
    async def process_discovery_task(self, task: Dict[str, Any]):
        """Process a discovery task from the queue"""
        
        # This method would be called by the background task processor
        # Implementation depends on your task queue structure
        pass