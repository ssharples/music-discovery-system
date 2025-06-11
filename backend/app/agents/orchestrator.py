# backend/app/agents/orchestrator.py
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4, UUID
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import BackgroundTasks
import time
import re

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.core import quota_manager
from app.models.artist import (
    DiscoveryRequest, ArtistProfile, VideoMetadata, 
    LyricAnalysis, EnrichedArtistData
)
from app.agents.master_discovery_agent import MasterDiscoveryAgent
from app.agents.crawl4ai_youtube_agent import Crawl4AIYouTubeAgent
from app.agents.crawl4ai_enrichment_agent import Crawl4AIEnrichmentAgent
from app.agents.lyrics_agent import get_lyrics_agent
from app.agents.storage_agent import StorageAgent
from app.agents.ai_detection_agent import get_ai_detection_agent
from app.api.websocket import (
    notify_discovery_started, notify_discovery_progress, 
    notify_discovery_completed, notify_artist_discovered
)

logger = logging.getLogger(__name__)

# Factory function for on-demand orchestrator agent creation
def create_orchestrator_agent():
    """Create orchestrator agent on-demand to avoid import-time blocking"""
    try:
        return Agent(
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
    except Exception as e:
        logger.error(f"Failed to create orchestrator agent: {e}")
        return None

# Using global quota_manager from app.core.quota_manager

class DiscoveryOrchestrator:
    """
    Main orchestrator for the discovery pipeline with intelligent coordination.
    Now uses MasterDiscoveryAgent as the primary workflow engine.
    """
    
    def __init__(self, use_master_workflow: bool = True):
        # Primary workflow engine - MasterDiscoveryAgent
        self._master_agent = None
        
        # Fallback agents (for legacy support)
        self.youtube_agent = Crawl4AIYouTubeAgent()
        self._enrichment_agent = None
        self._lyrics_agent = None
        self._ai_detection_agent = None
        self.storage_agent = StorageAgent()
        self._orchestrator_agent = None
        self._agent_creation_attempted = False
        
        self.use_master_workflow = use_master_workflow
        self.quota_manager = quota_manager
        self._processed_artists = set()  # Deduplication cache
        
        # Session control
        self._active_sessions = {}  # session_id -> control flags
        self._session_states = {}  # session_id -> current state info
        
        logger.info(f"✅ Orchestrator initialized (Master workflow: {use_master_workflow})")
    
    @property
    def master_agent(self):
        """Lazy initialization of master discovery agent"""
        if self._master_agent is None:
            try:
                self._master_agent = MasterDiscoveryAgent()
                logger.info("✅ Master Discovery Agent initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Master Discovery Agent: {e}")
                self._master_agent = None
        return self._master_agent
    
    @property
    def orchestrator_agent(self):
        """Lazy initialization of orchestrator agent"""
        if self._orchestrator_agent is None and not self._agent_creation_attempted:
            self._agent_creation_attempted = True
            self._orchestrator_agent = create_orchestrator_agent()
        return self._orchestrator_agent
    
    async def start_discovery_session(
        self,
        request: DiscoveryRequest,
        deps: PipelineDependencies,
        background_tasks: BackgroundTasks
    ) -> UUID:
        """Start a new discovery session with the optimized workflow"""
        
        logger.info("📋 Orchestrator.start_discovery_session called")
        
        # Validate quota availability
        if not await self._validate_quota_availability(deps, request):
            raise Exception("Insufficient API quota to fulfill request")
        
        # Create session in database
        session_id = uuid4()
        logger.info(f"🆔 Generated session ID: {session_id}")
        
        session_data = {
            "id": str(session_id),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "metadata": {
                "search_query": request.search_query,
                "max_results": request.max_results,
                "filters": request.filters,
                "quota_check_passed": True,
                "workflow_engine": "MasterDiscoveryAgent" if self.use_master_workflow else "Legacy"
            }
        }
        
        # Store session
        logger.info("💾 Storing session in database...")
        await self.storage_agent.create_discovery_session(deps, session_data)
        
        # Notify clients that discovery started
        await notify_discovery_started(str(session_id), {
            "search_query": request.search_query,
            "max_results": request.max_results,
            "workflow_engine": "MasterDiscoveryAgent" if self.use_master_workflow else "Legacy"
        })
        
        # Start discovery in background
        logger.info("🏃 Adding discovery pipeline to background tasks...")
        background_tasks.add_task(
            self._run_discovery_pipeline_with_error_handling,
            session_id,
            request,
            deps
        )
        
        return session_id
    
    async def discover_undiscovered_talent(
        self,
        deps: PipelineDependencies,
        max_results: int = 50
    ) -> Dict[str, Any]:
        """
        Specialized discovery for undiscovered talent
        
        Searches for:
        - Official music videos uploaded in the last 24 hours
        - Videos with less than 50k views
        - Independent/unsigned artists
        
        Args:
            deps: Pipeline dependencies
            max_results: Maximum number of artists to return
            
        Returns:
            Dictionary with discovery results and metadata
        """
        start_time = time.time()
        logger.info(f"🎯 Starting undiscovered talent discovery (max_results: {max_results})")
        
        try:
            # Call the specialized discovery method based on agent type
            logger.info("🔍 Searching for undiscovered artists with recent uploads...")
            if self.use_master_workflow:
                # Use MasterDiscoveryAgent's search with undiscovered talent filters
                result = await self.master_agent.discover_undiscovered_talent(deps, max_results)
            else:
                # Use Crawl4AI agent's specialized method
                result = await self._run_legacy_discovery_workflow(deps, max_results)
            
            if result.get('status') == 'error':
                logger.error(f"❌ Undiscovered talent discovery error: {result.get('message', 'Unknown error')}")
                return result
            
            logger.info(f"🎉 Undiscovered talent discovery complete! Found {result['data']['total_found']} artists")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Undiscovered talent discovery error: {str(e)}")
            return {
                "status": "error",
                "message": f"Undiscovered talent discovery failed: {str(e)}",
                "data": {
                    "query": "undiscovered talent discovery",
                    "total_found": 0,
                    "artists": [],
                    "execution_time": time.time() - start_time,
                    "error": str(e)
                }
            }
    
    async def _validate_quota_availability(
        self,
        deps: PipelineDependencies,
        request: DiscoveryRequest
    ) -> bool:
        """Validate that sufficient API quota is available for the request"""
        try:
            if self.use_master_workflow:
                # MasterDiscoveryAgent doesn't require API tokens, just check basic setup
                logger.info("✅ MasterDiscoveryAgent quota validation passed (no API costs)")
                return True
            else:
                # Check if Crawl4AI is configured
                if not self.youtube_agent.apify_api_token:
                    logger.error("❌ APIFY_API_TOKEN not configured - cannot perform discovery")
                    return False
                
                # Estimate Crawl4AI costs
                estimated_videos = request.max_results
                estimated_cost = self.youtube_agent.get_cost_estimate(estimated_videos)
                
                logger.info(f"💰 Estimated Crawl4AI cost for {estimated_videos} videos: ${estimated_cost:.4f}")
                
                # For now, allow all requests - add billing limits if needed
                if estimated_cost > 10.0:  # $10 safety limit
                    logger.warning(f"⚠️ High estimated cost: ${estimated_cost:.2f}")
                    # You could add budget checks here
                
                logger.info("✅ Crawl4AI quota validation passed")
                return True
            
        except Exception as e:
            logger.error(f"❌ Quota validation error: {e}")
            return True  # Allow operation if validation fails
        
    async def _run_discovery_pipeline_with_error_handling(
        self,
        session_id: UUID,
        request: DiscoveryRequest,
        deps: PipelineDependencies
    ):
        """Run discovery pipeline with comprehensive error handling"""
        try:
            await self._run_discovery_pipeline(session_id, request, deps)
        except Exception as e:
            logger.error(f"💥 Discovery pipeline failed for session {session_id}: {e}")
            await self.storage_agent.update_discovery_session(
                deps, 
                str(session_id), 
                {"status": "failed", "error": str(e), "completed_at": datetime.now(timezone.utc).isoformat()}
            )
            await notify_discovery_completed(str(session_id), {
                "status": "failed",
                "error": str(e),
                "total_artists": 0
            })

    async def _run_discovery_pipeline(
        self,
        session_id: UUID,
        request: DiscoveryRequest,
        deps: PipelineDependencies
    ):
        """
        Main discovery pipeline - now uses MasterDiscoveryAgent as primary workflow
        """
        start_time = time.time()
        logger.info(f"🚀 Starting discovery pipeline for session {session_id}")
        
        try:
            # Set session as active
            self._active_sessions[str(session_id)] = {"running": True, "paused": False}
            
            if self.use_master_workflow and self.master_agent:
                # Use MasterDiscoveryAgent for complete workflow
                logger.info("🎯 Using MasterDiscoveryAgent for discovery workflow")
                
                result = await self.master_agent.discover_artists(
                    deps=deps,
                    max_results=request.max_results,
                    search_query=request.search_query
                )
                
                # Extract results
                if result.get('status') == 'success':
                    discovered_artists = result['data']['artists']
                    total_found = result['data']['total_found']
                    
                    # Notify progress
                    for i, artist in enumerate(discovered_artists, 1):
                        await notify_artist_discovered({
                            "session_id": str(session_id),
                            "artist": artist,
                            "progress": i,
                            "total": total_found
                        })
                        
                        # Check session control
                        if not self._check_session_control(str(session_id)):
                            logger.info(f"⏸️ Session {session_id} paused or stopped")
                            break
                    
                    # Update session in database
                    await self.storage_agent.update_discovery_session(
                        deps,
                        str(session_id),
                        {
                            "status": "completed",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "results": {
                                "total_found": total_found,
                                "total_processed": result['data']['total_processed'],
                                "execution_time": result['data']['execution_time'],
                                "workflow_engine": "MasterDiscoveryAgent"
                            }
                        }
                    )
                    
                    # Notify completion
                    await notify_discovery_completed(str(session_id), {
                        "status": "completed",
                        "total_artists": total_found,
                        "execution_time": result['data']['execution_time'],
                        "workflow_engine": "MasterDiscoveryAgent"
                    })
                    
                    logger.info(f"✅ Master workflow completed: {total_found} artists discovered")
                else:
                    raise Exception(f"Master workflow failed: {result.get('message', 'Unknown error')}")
                    
            else:
                # Fallback to legacy workflow (existing implementation)
                logger.info("🔄 Using legacy workflow (fallback)")
                await self._run_legacy_discovery_workflow(session_id, request, deps)
                
        except Exception as e:
            logger.error(f"❌ Discovery pipeline error: {e}")
            raise
        finally:
            # Clean up session
            if str(session_id) in self._active_sessions:
                del self._active_sessions[str(session_id)]
            if str(session_id) in self._session_states:
                del self._session_states[str(session_id)]

    async def _run_legacy_discovery_workflow(
        self,
        session_id: UUID,
        request: DiscoveryRequest,
        deps: PipelineDependencies
    ):
        """Legacy discovery workflow for backward compatibility"""
        logger.info(f"🔄 Running legacy discovery workflow for session {session_id}")
        
        # Implementation of existing workflow logic
        discovered_artists = await self._discover_youtube_artists_with_quality_filter(
            deps, request.search_query, request.max_results, session_id
        )
        
        # Update session
        await self.storage_agent.update_discovery_session(
            deps,
            str(session_id),
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "results": {
                    "total_found": len(discovered_artists),
                    "workflow_engine": "Legacy"
                }
            }
        )
        
        # Notify completion
        await notify_discovery_completed(str(session_id), {
            "status": "completed",
            "total_artists": len(discovered_artists),
            "workflow_engine": "Legacy"
        })

    async def _discover_youtube_artists_with_quality_filter(
        self,
        deps: PipelineDependencies,
        query: str,
        max_results: int,
        session_id: UUID
    ) -> List[Dict[str, Any]]:
        """YouTube discovery with intelligent quality filtering and timeout handling"""
        
        try:
            logger.info(f"🔍 Crawl4AI YouTube discovery starting for query: {query}")
            
            # Try discovery with timeout handling
            discovered_channels = []
            try:
                # Use asyncio.wait_for to add an overall timeout to the discovery process
                videos = await asyncio.wait_for(
                    self.youtube_agent.search_youtube(
                        query=query,
                        max_results=max_results,
                        upload_date="week",  # Focus on recent content
                        sort_by="date"
                    ),
                    timeout=900  # 15 minutes total timeout
                )
                # Convert video data to channel data format
                discovered_channels = self._convert_videos_to_channels(videos)
                logger.info(f"✅ YouTube agent discovery completed")
                
            except asyncio.TimeoutError:
                logger.error(f"❌ Discovery timed out after 15 minutes for query: {query}")
                return []
                        
            except Exception as discover_error:
                logger.error(f"❌ YouTube agent discover_artists failed: {discover_error}")
                return []
            
            if not discovered_channels:
                logger.warning("⚠️ No channels discovered from YouTube scraper")
                return []
            
            logger.info(f"📊 Filtering {len(discovered_channels)} channels for quality")
            
            # Quality filtering
            filtered_channels = []
            for channel in discovered_channels:
                quality_score = self._calculate_channel_quality_score(channel)
                
                if quality_score >= 0.4:  # Quality threshold
                    channel['quality_score'] = quality_score
                    filtered_channels.append(channel)
                    logger.debug(f"✅ Channel passed quality filter: {channel.get('channel_title')} (score: {quality_score:.2f})")
                else:
                    logger.debug(f"⚠️ Channel filtered out: {channel.get('channel_title')} (score: {quality_score:.2f})")
            
            # Sort by quality score
            filtered_channels.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
            
            logger.info(f"🎯 Quality filtering complete: {len(filtered_channels)} channels passed")
            return filtered_channels
             
        except Exception as e:
            logger.error(f"❌ YouTube discovery error: {e}")
            return []

    def _calculate_channel_quality_score(self, channel: Dict[str, Any]) -> float:
        """Calculate quality score for a YouTube channel"""
        score = 0.0
        
        try:
            # Base metrics
            view_count = channel.get('view_count', 0)
            subscriber_count = channel.get('subscriber_count', 0)
            video_count = channel.get('video_count', 0)
            
            # Engagement metrics
            if view_count > 1000:
                score += 0.2
            if subscriber_count > 100:
                score += 0.2
            if video_count > 5:
                score += 0.2
            
            # Content quality indicators
            if channel.get('has_recent_uploads', False):
                score += 0.2
            if channel.get('has_music_content', False):
                score += 0.2
            
            # AI analysis bonus
            ai_analysis = channel.get('ai_analysis', {})
            if ai_analysis.get('score', 0) > 7:
                score += 0.2
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Quality score calculation error: {e}")
            return 0.0

    async def _check_youtube_quota(self, deps: PipelineDependencies) -> int:
        """Check remaining YouTube API quota with improved tracking"""
        try:
            return await self.quota_manager.get_remaining_quota('youtube')
        except Exception as e:
            logger.error(f"Quota check error: {e}")
            return 1000  # Conservative fallback
        
    async def _update_api_usage(
        self,
        deps: PipelineDependencies,
        api_name: str,
        units: int
    ):
        """Update API usage tracking"""
        try:
            # This would update usage in database/cache
            logger.debug(f"📊 API usage updated: {api_name} +{units} units")
        except Exception as e:
            logger.error(f"Usage update error: {e}")
        
    async def _reset_api_quota(self, deps: PipelineDependencies, api_name: str):
        """Reset API quota (daily reset)"""
        try:
            logger.info(f"🔄 Resetting quota for {api_name}")
            # This would reset daily quota counters
        except Exception as e:
            logger.error(f"Quota reset error: {e}")
        
    async def process_discovery_task(self, task: Dict[str, Any]):
        """Process individual discovery task (for background processing)"""
        logger.info(f"📋 Processing discovery task: {task.get('type', 'unknown')}")
        # This would handle individual background tasks
        pass

    def _get_session_control(self, session_id: str) -> Dict[str, Any]:
        """Get or create session control flags"""
        if session_id not in self._active_sessions:
            self._active_sessions[session_id] = {
                'should_stop': False,
                'should_pause': False,
                'is_paused': False,
                'created_at': time.time()
            }
        return self._active_sessions[session_id]
    
    def _check_session_control(self, session_id: str) -> bool:
        """Check if session should continue (not stopped or paused)"""
        if not session_id:
            return True  # No session control for direct API calls
        
        control = self._get_session_control(session_id)
        
        # Check for stop signal
        if control['should_stop']:
            logger.info(f"🛑 Session {session_id} received stop signal")
            return False
        
        # Check for pause signal
        if control['should_pause'] and not control['is_paused']:
            control['is_paused'] = True
            logger.info(f"⏸️ Session {session_id} paused")
        
        # For paused sessions, we just return False to stop the session
        # (The resume functionality would restart the pipeline)
        if control['should_pause'] or control['is_paused']:
            logger.info(f"⏸️ Session {session_id} is paused")
            return False
        
        return not control['should_stop']
    
    async def pause_session(self, session_id: str, deps: PipelineDependencies) -> Dict[str, Any]:
        """Pause a running discovery session"""
        try:
            control = self._get_session_control(session_id)
            
            if control['should_stop']:
                return {
                    "status": "error",
                    "message": "Cannot pause a stopped session",
                    "session_id": session_id
                }
            
            control['should_pause'] = True
            logger.info(f"⏸️ Pause requested for session {session_id}")
            
            # Update session status in database
            await self.storage_agent.update_discovery_session(
                deps,
                session_id,
                {
                    "status": "paused",
                    "paused_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            return {
                "status": "success",
                "message": "Session pause requested",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error pausing session {session_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to pause session: {str(e)}",
                "session_id": session_id
            }
    
    async def resume_session(self, session_id: str, deps: PipelineDependencies) -> Dict[str, Any]:
        """Resume a paused discovery session"""
        try:
            control = self._get_session_control(session_id)
            
            if control['should_stop']:
                return {
                    "status": "error",
                    "message": "Cannot resume a stopped session",
                    "session_id": session_id
                }
            
            if not control['should_pause']:
                return {
                    "status": "error",
                    "message": "Session is not paused",
                    "session_id": session_id
                }
            
            control['should_pause'] = False
            logger.info(f"▶️ Resume requested for session {session_id}")
            
            # Update session status in database
            await self.storage_agent.update_discovery_session(
                deps,
                session_id,
                {
                    "status": "running",
                    "resumed_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            return {
                "status": "success",
                "message": "Session resumed",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error resuming session {session_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to resume session: {str(e)}",
                "session_id": session_id
            }
    
    async def stop_session(self, session_id: str, deps: PipelineDependencies) -> Dict[str, Any]:
        """Stop a running discovery session"""
        try:
            control = self._get_session_control(session_id)
            control['should_stop'] = True
            control['should_pause'] = False  # Clear pause if set
            
            logger.info(f"🛑 Stop requested for session {session_id}")
            
            # Update session status in database
            await self.storage_agent.update_discovery_session(
                deps,
                session_id,
                {
                    "status": "stopped",
                    "stopped_at": datetime.now(timezone.utc).isoformat(),
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Clean up session from active sessions
            if session_id in self._active_sessions:
                del self._active_sessions[session_id]
            
            return {
                "status": "success",
                "message": "Session stopped",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error stopping session {session_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to stop session: {str(e)}",
                "session_id": session_id
            }
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current status of a session"""
        try:
            if session_id in self._active_sessions:
                control = self._active_sessions[session_id]
                state = self._session_states.get(session_id, {})
                
                status = "running"
                if control['should_stop']:
                    status = "stopped"
                elif control['is_paused']:
                    status = "paused"
                elif control['should_pause']:
                    status = "pausing"
                
                return {
                    "session_id": session_id,
                    "status": status,
                    "control_flags": control,
                    "state": state
                }
            else:
                return {
                    "session_id": session_id,
                    "status": "not_found",
                    "message": "Session not active or completed"
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting session status {session_id}: {e}")
            return {
                "session_id": session_id,
                "status": "error",
                "message": str(e)
            }

    def _is_artist_name_english(self, name: str) -> bool:
        """Check if artist name contains only English characters"""
        if not name:
            return False
            
        # Allow English letters, numbers, spaces, and common punctuation
        english_pattern = re.compile(r'^[a-zA-Z0-9\s\.,&\'-]+$')
        return bool(english_pattern.match(name.strip()))
    
    def _extract_social_urls_from_videos(self, channel_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Extract Instagram and Spotify URLs from YouTube video descriptions"""
        instagram_url = None
        spotify_url = None
        
        try:
            # Check recent videos for social media URLs in descriptions
            recent_videos = channel_data.get('videos', [])
            if not recent_videos:
                # Try alternate video data structure
                recent_videos = channel_data.get('recent_videos', [])
            
            for video in recent_videos:
                description = video.get('description', '')
                if not description:
                    continue
                
                # Extract Instagram URLs
                if not instagram_url:
                    instagram_match = re.search(
                        r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_\.]+)/?',
                        description,
                        re.IGNORECASE
                    )
                    if instagram_match:
                        username = instagram_match.group(1)
                        instagram_url = f"https://instagram.com/{username}"
                        logger.info(f"🔗 Found Instagram URL in video description: {instagram_url}")
                
                # Extract Spotify URLs
                if not spotify_url:
                    spotify_match = re.search(
                        r'(?:https?://)?(?:open\.)?spotify\.com/(artist|track|album)/([a-zA-Z0-9]+)',
                        description,
                        re.IGNORECASE
                    )
                    if spotify_match:
                        spotify_type = spotify_match.group(1)
                        spotify_id = spotify_match.group(2)
                        if spotify_type == 'artist':
                            spotify_url = f"https://open.spotify.com/artist/{spotify_id}"
                            logger.info(f"🎵 Found Spotify artist URL in video description: {spotify_url}")
                        
                # Stop if we found both
                if instagram_url and spotify_url:
                    break
                    
        except Exception as e:
            logger.warning(f"Error extracting social URLs from video descriptions: {e}")
        
        return instagram_url, spotify_url
    
    def _extract_instagram_handle(self, instagram_url: str) -> Optional[str]:
        """Extract Instagram handle from URL"""
        if not instagram_url:
            return None
        
        match = re.search(r'instagram\.com/([a-zA-Z0-9_\.]+)', instagram_url)
        return match.group(1) if match else None
    
    def _extract_spotify_id_from_url(self, spotify_url: str) -> Optional[str]:
        """Extract Spotify artist ID from URL"""
        if not spotify_url:
            return None
        match = re.search(r'spotify\.com/artist/([a-zA-Z0-9]+)', spotify_url)
        return match.group(1) if match else None

    def _convert_videos_to_channels(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert video data from Crawl4AI YouTube agent to channel format expected by orchestrator"""
        channels_map = {}
        
        for video in videos:
            channel_id = video.get('channel_id', '')
            if not channel_id:
                continue
                
            if channel_id not in channels_map:
                # Create new channel entry
                channels_map[channel_id] = {
                    'channel_id': channel_id,
                    'channel_title': video.get('channel_title', ''),
                    'channel_url': video.get('channel_url', ''),
                    'videos': [],
                    'view_count': 0,
                    'subscriber_count': 0,  # Will be updated by channel scraping
                    'video_count': 0,
                    'has_recent_uploads': True,  # Since we're filtering by recent uploads
                    'has_music_content': True,  # Assume music content since we're searching for it
                    'extracted_artist_name': video.get('artist_name'),  # From video processing
                    'social_media': video.get('social_media', {}),
                    'quality_indicators': []
                }
            
            # Add video to channel
            channel = channels_map[channel_id]
            channel['videos'].append({
                'video_id': video.get('video_id'),
                'title': video.get('title'),
                'description': video.get('description', ''),
                'views': video.get('views', 0),
                'published': video.get('published'),
                'duration': video.get('duration'),
                'thumbnail': video.get('thumbnail')
            })
            
            # Update channel stats
            channel['video_count'] += 1
            if video.get('views'):
                try:
                    views = int(video['views'].replace(',', '').replace('views', '').strip())
                    channel['view_count'] += views
                except (ValueError, AttributeError):
                    pass
            
            # Extract artist name from video if available
            if video.get('artist_name') and not channel.get('extracted_artist_name'):
                channel['extracted_artist_name'] = video['artist_name']
            
            # Merge social media data
            if video.get('social_media'):
                channel['social_media'].update(video['social_media'])
        
        return list(channels_map.values())

    def _is_undiscovered_video(self, video: Dict[str, Any]) -> bool:
        """Check if a video meets undiscovered talent criteria"""
        try:
            # Extract view count
            views_str = video.get('views', '0')
            if isinstance(views_str, str):
                # Parse views like "1.2K views", "50K views", etc.
                views_str = views_str.lower().replace(' views', '').replace(',', '')
                if 'k' in views_str:
                    views = int(float(views_str.replace('k', '')) * 1000)
                elif 'm' in views_str:
                    views = int(float(views_str.replace('m', '')) * 1000000)
                else:
                    views = int(views_str)
            else:
                views = int(views_str or 0)
            
            # Filter criteria for undiscovered talent
            # 1. Less than 50K views
            if views >= 50000:
                return False
            
            # 2. Check channel title doesn't contain major label indicators
            channel_title = video.get('channel_title', '').lower()
            major_labels = ['vevo', 'universal', 'sony', 'warner', 'atlantic', 'capitol', 'rca', 'def jam']
            if any(label in channel_title for label in major_labels):
                return False
            
            # 3. Video title should contain music-related terms
            title = video.get('title', '').lower()
            music_terms = ['music', 'song', 'official', 'video', 'mv', 'cover', 'remix', 'acoustic']
            if not any(term in title for term in music_terms):
                return False
            
            return True
            
        except (ValueError, AttributeError) as e:
            logger.debug(f"Error parsing video data for undiscovered filter: {e}")
            return False