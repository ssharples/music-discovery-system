# backend/app/agents/orchestrator.py
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import Dict, Any, List, Optional
from uuid import uuid4, UUID
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import BackgroundTasks
import time

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.core import quota_manager
from app.models.artist import (
    DiscoveryRequest, ArtistProfile, VideoMetadata, 
    LyricAnalysis, EnrichedArtistData
)
from app.agents.apify_youtube_agent import ApifyYouTubeAgent
from app.agents.enhanced_enrichment_agent_simple import get_simple_enhanced_enrichment_agent
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
    """Main orchestrator for the discovery pipeline with intelligent coordination"""
    
    def __init__(self):
        self.youtube_agent = ApifyYouTubeAgent()
        self._enrichment_agent = None
        self._lyrics_agent = None
        self._ai_detection_agent = None
        self.storage_agent = StorageAgent()
        self._orchestrator_agent = None
        self._agent_creation_attempted = False
        # Use global quota_manager from app.core.quota_manager
        self.quota_manager = quota_manager
        self._processed_artists = set()  # Deduplication cache
        
        # Session control
        self._active_sessions = {}  # session_id -> control flags
        self._session_states = {}  # session_id -> current state info
        
        logger.info("✅ Orchestrator initialized with lazy agent loading")
    
    @property
    def orchestrator_agent(self):
        """Lazy initialization of orchestrator agent"""
        if self._orchestrator_agent is None and not self._agent_creation_attempted:
            self._agent_creation_attempted = True
            self._orchestrator_agent = create_orchestrator_agent()
        return self._orchestrator_agent
    
    @property
    def enrichment_agent(self):
        """Lazy initialization of enrichment agent"""
        if self._enrichment_agent is None:
            try:
                self._enrichment_agent = get_simple_enhanced_enrichment_agent()
                logger.info("✅ Enhanced enrichment agent initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize enhanced enrichment agent: {e}")
                self._enrichment_agent = None
        return self._enrichment_agent
        
    @property
    def lyrics_agent(self):
        """Lazy initialization of lyrics agent"""
        if self._lyrics_agent is None:
            try:
                self._lyrics_agent = get_lyrics_agent()
                logger.info("✅ Lyrics agent initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize lyrics agent: {e}")
                self._lyrics_agent = None
        return self._lyrics_agent
    
    @property
    def ai_detection_agent(self):
        """Lazy initialization of AI detection agent"""
        if self._ai_detection_agent is None:
            try:
                self._ai_detection_agent = get_ai_detection_agent()
                logger.info("✅ AI detection agent initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize AI detection agent: {e}")
                self._ai_detection_agent = None
        return self._ai_detection_agent
        
    async def start_discovery_session(
        self,
        request: DiscoveryRequest,
        deps: PipelineDependencies,
        background_tasks: BackgroundTasks
    ) -> UUID:
        """Start a new discovery session with comprehensive monitoring"""
        
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
                "quota_check_passed": True
            }
        }
        
        # Store session
        logger.info("💾 Storing session in database...")
        await self.storage_agent.create_discovery_session(deps, session_data)
        
        # Notify clients that discovery started
        await notify_discovery_started(str(session_id), {
            "search_query": request.search_query,
            "max_results": request.max_results
        })
        
        # Start discovery in background
        logger.info("🏃 Adding discovery pipeline to background tasks...")
        try:
            background_tasks.add_task(
                self._run_discovery_pipeline_with_error_handling,
                session_id,
                request,
                deps
            )
            logger.info("✅ Background task added successfully")
        except Exception as e:
            logger.error(f"❌ Failed to add background task: {e}")
            raise
        
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
            # Call the specialized discovery method from Apify agent
            logger.info("🔍 Searching for undiscovered artists with recent uploads...")
            raw_videos = await self.youtube_agent.discover_undiscovered_artists(max_results=max_results * 2)
            
            if not raw_videos:
                logger.warning("⚠️ No undiscovered artists found")
                return {
                    "status": "success",
                    "message": "No undiscovered artists found in recent uploads",
                    "data": {
                        "query": "undiscovered talent discovery",
                        "total_found": 0,
                        "artists": [],
                        "execution_time": time.time() - start_time,
                        "discovery_criteria": "24h uploads, <50k views, independent artists"
                    }
                }
            
            logger.info(f"📊 Found {len(raw_videos)} potential undiscovered artist videos")
            
            # Convert videos to artist channel data for processing
            channel_groups = {}
            for video in raw_videos:
                channel_id = video.get('channel_id', video.get('channel_title', ''))
                if channel_id not in channel_groups:
                    channel_groups[channel_id] = {
                        'channel_title': video.get('channel_title', 'Unknown Artist'),
                        'channel_id': channel_id,
                        'channel_url': video.get('channel_url', ''),
                        'videos': [],
                        'total_views': 0,
                        'avg_views': 0,
                        'undiscovered_score': video.get('undiscovered_score', 0)
                    }
                
                channel_groups[channel_id]['videos'].append(video)
                channel_groups[channel_id]['total_views'] += video.get('view_count', 0)
            
            # Calculate averages for each channel
            discovered_channels = []
            for channel_data in channel_groups.values():
                if channel_data['videos']:
                    channel_data['avg_views'] = channel_data['total_views'] / len(channel_data['videos'])
                    channel_data['video_count'] = len(channel_data['videos'])
                    discovered_channels.append(channel_data)
            
            logger.info(f"🎭 Grouped into {len(discovered_channels)} unique artist channels")
            
            # Process artists through enrichment pipeline
            enriched_artists = []
            for i, channel_data in enumerate(discovered_channels, 1):
                try:
                    logger.info(f"Processing undiscovered artist {i}/{len(discovered_channels)}: {channel_data.get('channel_title')}")
                    
                    enriched_artist = await self._process_artist_with_quality_checks(
                        deps, channel_data, None  # No session ID for direct API call
                    )
                    
                    if enriched_artist and enriched_artist.enrichment_score >= 0.2:  # Lower threshold for undiscovered
                        enriched_artists.append(enriched_artist)
                        logger.info(f"✅ Undiscovered artist added: {enriched_artist.name} (score: {enriched_artist.enrichment_score:.2f})")
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.3)
                    
                except Exception as e:
                    logger.error(f"❌ Failed to process undiscovered artist: {e}")
                    continue
            
            # Calculate costs
            discovery_cost = self.youtube_agent.get_cost_estimate(len(raw_videos))
            
            logger.info(f"🎉 Undiscovered talent discovery complete! Found {len(enriched_artists)} artists")
            
            return {
                "status": "success",
                "message": f"Successfully discovered {len(enriched_artists)} undiscovered artists",
                "data": {
                    "query": "undiscovered talent discovery",
                    "total_found": len(enriched_artists),
                    "artists": [artist.to_dict() for artist in enriched_artists],
                    "execution_time": time.time() - start_time,
                    "discovery_criteria": "24h uploads, <50k views, independent artists",
                    "pipeline_stats": {
                        "videos_analyzed": len(raw_videos),
                        "channels_found": len(discovered_channels),
                        "enriched_artists": len(enriched_artists),
                        "estimated_cost": f"${discovery_cost:.4f}"
                    }
                }
            }
            
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
            # Check if Apify is configured
            if not self.youtube_agent.apify_api_token:
                logger.error("❌ APIFY_API_TOKEN not configured - cannot perform discovery")
                return False
            
            # Estimate Apify costs
            estimated_videos = request.max_results
            estimated_cost = self.youtube_agent.get_cost_estimate(estimated_videos)
            
            logger.info(f"💰 Estimated Apify cost for {estimated_videos} videos: ${estimated_cost:.4f}")
            
            # For now, allow all requests - add billing limits if needed
            if estimated_cost > 10.0:  # $10 safety limit
                logger.warning(f"⚠️ High estimated cost: ${estimated_cost:.2f}")
                # You could add budget checks here
            
            logger.info("✅ Apify quota validation passed")
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
        """Wrapper with comprehensive error handling and recovery"""
        logger.info(f"🛡️ ERROR HANDLER: Starting pipeline wrapper for session {session_id}")
        
        try:
            logger.info(f"🎯 About to call actual pipeline method...")
            await self._run_discovery_pipeline(session_id, request, deps)
            logger.info(f"✅ Pipeline completed successfully for session {session_id}")
            
        except Exception as e:
            logger.error(f"💥 CRITICAL PIPELINE ERROR for session {session_id}: {e}")
            logger.error(f"📍 Error type: {type(e).__name__}")
            logger.error(f"📄 Error details: {str(e)}")
            
            # Try to update session as failed
            try:
                await self.storage_agent.update_discovery_session(
                    deps,
                    str(session_id),
                    {
                        "status": "failed",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "error_logs": [f"{type(e).__name__}: {str(e)}"]
                    }
                )
                logger.info(f"📝 Updated session {session_id} status to failed")
            except Exception as update_error:
                logger.error(f"❌ Could not update session status: {update_error}")
        
    async def _run_discovery_pipeline(
        self,
        session_id: UUID,
        request: DiscoveryRequest,
        deps: PipelineDependencies
    ):
        """Run the complete discovery pipeline with quality controls"""
        
        logger.info(f"🚀 PIPELINE ENTRY: _run_discovery_pipeline called for session {session_id}")
        logger.info(f"📋 Request details: query='{request.search_query}', max_results={request.max_results}")
        
        try:
            logger.info(f"🎬 Entering try block for session {session_id}")
            logger.info(f"Starting discovery pipeline for session {session_id}")
            
            # Check if session should continue
            if not self._check_session_control(str(session_id)):
                logger.info(f"🛑 Discovery pipeline stopped before YouTube discovery for session {session_id}")
                return
            
            # Phase 1: YouTube Discovery with quality filtering
            logger.info(f"About to call YouTube discovery with query: {request.search_query}")
            try:
                discovered_channels = await self._discover_youtube_artists_with_quality_filter(
                    deps, request.search_query, request.max_results, session_id
                )
                logger.info(f"✅ YouTube discovery completed successfully")
                
                # Check if session should continue after YouTube discovery
                if not self._check_session_control(str(session_id)):
                    logger.info(f"🛑 Discovery pipeline stopped after YouTube discovery for session {session_id}")
                    return
                    
            except Exception as youtube_error:
                logger.error(f"❌ YouTube discovery failed: {youtube_error}")
                # Continue with empty list to test rest of pipeline
                discovered_channels = []
            
            logger.info(f"Discovered {len(discovered_channels)} potential artists after quality filtering")
            if discovered_channels:
                logger.info(f"Sample channels: {[c.get('channel_title', 'Unknown') for c in discovered_channels[:3]]}")
            else:
                logger.warning("No channels discovered from YouTube search")
            
            # Phase 2: Process each artist with deduplication and retry logic
            enriched_artists = []
            total_artists = len(discovered_channels)
            
            logger.info(f"Starting to process {total_artists} discovered channels")
            
            for i, channel_data in enumerate(discovered_channels, 1):
                try:
                    # Check if session should continue before each artist
                    if not self._check_session_control(str(session_id)):
                        logger.info(f"🛑 Discovery pipeline stopped at artist {i}/{total_artists} for session {session_id}")
                        break
                    
                    artist_name = channel_data.get('extracted_artist_name') or channel_data.get('channel_title', 'Unknown Artist')
                    channel_title = channel_data.get('channel_title', 'Unknown Artist')
                    channel_id = channel_data.get('channel_id')
                    
                    # Deduplication check
                    if channel_id in self._processed_artists:
                        logger.info(f"⏭️ Skipping duplicate artist: {artist_name}")
                        continue
                    
                    logger.info(f"Processing artist {i}/{total_artists}: {artist_name}")
                    
                    enriched_artist = await self._process_artist_with_quality_checks(
                        deps, channel_data, session_id
                    )
                    
                    if enriched_artist and enriched_artist.enrichment_score >= 0.3:  # Quality threshold
                        enriched_artists.append(enriched_artist)
                        self._processed_artists.add(channel_id)
                        
                        # Notify successful artist processing
                        await notify_artist_discovered({
                            "name": artist_name,
                            "enrichment_score": enriched_artist.enrichment_score,
                            "session_id": str(session_id)
                        })
                        
                        logger.info(f"✅ High-quality artist added: {artist_name} (score: {enriched_artist.enrichment_score:.2f})")
                    else:
                        logger.info(f"⚠️ Artist below quality threshold: {artist_name}")
                        
                    # Progress update
                    await notify_discovery_progress(str(session_id), {
                        "processed": i,
                        "total": total_artists,
                        "high_quality_found": len(enriched_artists)
                    })
                    
                    # Rate limiting between artists
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"❌ Failed to process artist {i}: {e}")
                    continue
            
            # Phase 3: Final processing and notification
            logger.info(f"💎 Discovery completed: {len(enriched_artists)} high-quality artists found")
            
            # Update session completion
            await self.storage_agent.update_discovery_session(
                deps,
                str(session_id),
                {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "artists_discovered": len(enriched_artists),
                    "videos_processed": sum(len(artist.videos) for artist in enriched_artists),
                    "metadata": {
                        "quality_threshold": 0.3,
                        "total_candidates": total_artists,
                        "high_quality_ratio": len(enriched_artists) / total_artists if total_artists > 0 else 0
                    }
                }
            )
            
            # Final notification
            await notify_discovery_completed(str(session_id), {
                "artists_found": len(enriched_artists),
                "total_processed": total_artists,
                "quality_score": sum(artist.enrichment_score for artist in enriched_artists) / len(enriched_artists) if enriched_artists else 0
            })
            
            logger.info(f"🎉 Pipeline completed successfully for session {session_id}")
            
        except Exception as e:
            logger.error(f"💥 Pipeline error in session {session_id}: {e}")
            raise
    
    async def _discover_youtube_artists_with_quality_filter(
        self,
        deps: PipelineDependencies,
        query: str,
        max_results: int,
        session_id: UUID
    ) -> List[Dict[str, Any]]:
        """YouTube discovery with intelligent quality filtering and timeout handling"""
        
        try:
            # Apify doesn't use YouTube API quotas - just check if configured
            if not self.youtube_agent.apify_api_token:
                logger.error("❌ APIFY_API_TOKEN not configured")
                return []
            
            logger.info(f"🔍 Apify YouTube discovery starting for query: {query}")
            
            # Try discovery with timeout handling
            discovered_channels = []
            try:
                # Use asyncio.wait_for to add an overall timeout to the discovery process
                discovered_channels = await asyncio.wait_for(
                    self.youtube_agent.discover_artists(deps, query, max_results),
                    timeout=900  # 15 minutes total timeout
                )
                logger.info(f"✅ YouTube agent discover_artists completed")
                
            except asyncio.TimeoutError:
                logger.error(f"❌ Discovery timed out after 15 minutes for query: {query}")
                # Try a smaller search as fallback
                if max_results > 20:
                    logger.info("🔄 Trying fallback with smaller max_results...")
                    try:
                        discovered_channels = await asyncio.wait_for(
                            self.youtube_agent.discover_artists(deps, query, 20),
                            timeout=600  # 10 minutes for smaller search
                        )
                        logger.info(f"✅ Fallback discovery completed with {len(discovered_channels)} results")
                    except Exception as fallback_error:
                        logger.error(f"❌ Fallback discovery also failed: {fallback_error}")
                        return []
                        
            except Exception as discover_error:
                logger.error(f"❌ YouTube agent discover_artists failed: {discover_error}")
                logger.error(f"Error type: {type(discover_error).__name__}")
                
                # Check if it's a specific timeout/gateway error
                error_message = str(discover_error).lower()
                if any(keyword in error_message for keyword in ['timeout', 'gateway', '504', '502', '503']):
                    logger.info("🔄 Detected timeout/gateway error, trying reduced search...")
                    try:
                        # Try with much smaller parameters to avoid timeouts
                        discovered_channels = await asyncio.wait_for(
                            self.youtube_agent.discover_artists(deps, query, 15),
                            timeout=300  # 5 minutes for emergency fallback
                        )
                        logger.info(f"✅ Emergency fallback completed with {len(discovered_channels)} results")
                    except Exception as emergency_error:
                        logger.error(f"❌ Emergency fallback also failed: {emergency_error}")
                        return []
                else:
                    logger.error(f"Error details: {str(discover_error)}")
                    return []
            
            if not discovered_channels:
                logger.warning("⚠️ No channels discovered from Apify YouTube scraper")
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
    
    async def _process_artist_with_quality_checks(
        self,
        deps: PipelineDependencies,
        channel_data: Dict[str, Any],
        session_id: UUID
    ) -> Optional[EnrichedArtistData]:
        """Process artist with comprehensive quality checks and retry logic"""
        
        # Use extracted artist name from video titles if available, otherwise fall back to channel title
        artist_name = channel_data.get('extracted_artist_name') or channel_data.get('channel_title', 'Unknown Artist')
        channel_title = channel_data.get('channel_title', 'Unknown Artist')
        channel_id = channel_data.get('channel_id')
        
        # Log the artist name selection for debugging
        if channel_data.get('extracted_artist_name'):
            logger.info(f"🎤 Using extracted artist name: '{artist_name}' (Channel: '{channel_title}')")
        else:
            logger.info(f"🔍 Using channel title as artist name: '{artist_name}'")
        
        try:
            # Check if artist already exists in database
            existing_artist = await self._check_for_existing_artist(deps, channel_id)
            if existing_artist:
                logger.info(f"📋 Artist already exists in database: {artist_name}")
                return existing_artist
            
            # Phase 1: Basic profile creation
            profile_id = uuid4()
            base_profile = ArtistProfile(
                id=profile_id,
                name=artist_name,  # Use the extracted/corrected artist name
                youtube_channel_id=channel_id,
                youtube_channel_name=channel_title,  # Keep original channel name for reference
                metadata={
                    "discovery_session_id": str(session_id),
                    "youtube_data": channel_data,
                    "processed_at": datetime.now().isoformat(),
                    "artist_name_source": "extracted_from_video_titles" if channel_data.get('extracted_artist_name') else "channel_title"
                }
            )
            
            # Phase 2: Enrichment with retry logic
            enriched_profile = await self._enrich_artist_with_retry(
                deps, base_profile, max_retries=3
            )
            
            # Phase 2.5: AI-Generated Content Detection
            if self.ai_detection_agent:
                try:
                    logger.info(f"🤖 Checking {artist_name} for AI-generated content")
                    ai_detection_result = await self.ai_detection_agent.analyze_artist_for_ai_content(
                        enriched_profile, channel_data.get('recent_videos', []), deps
                    )
                    
                    if ai_detection_result.is_ai_generated:
                        logger.warning(f"🚫 FILTERED OUT: {artist_name} - {ai_detection_result.recommendation}")
                        logger.info(f"Detection reasons: {ai_detection_result.detection_reasons}")
                        return None  # Filter out AI-generated content
                    else:
                        logger.info(f"✅ HUMAN ARTIST: {artist_name} - {ai_detection_result.recommendation}")
                        # Store AI detection metadata
                        enriched_profile.metadata.update({
                            "ai_detection": {
                                "is_ai_generated": False,
                                "confidence": ai_detection_result.confidence_score,
                                "checked_at": datetime.now().isoformat()
                            }
                        })
                except Exception as e:
                    logger.warning(f"⚠️ AI detection failed for {artist_name}: {e}")
                    # Continue processing if AI detection fails
            
            # Phase 3: Lyrics analysis (if agents available)
            videos_with_captions = []
            lyric_analyses = []
            
            if self.lyrics_agent:
                try:
                    videos_with_captions = await self.youtube_agent.get_artist_videos_with_captions(
                        deps, channel_id, max_videos=3
                    )
                    
                    if videos_with_captions:
                        lyric_analyses = await self.lyrics_agent.analyze_artist_lyrics(
                            deps, str(enriched_profile.id or profile_id), videos_with_captions
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Lyrics analysis failed for {artist_name}: {e}")
            
            # Phase 4: Create enriched artist data
            enriched_artist = EnrichedArtistData(
                profile=enriched_profile,
                videos=[VideoMetadata(**video) for video in videos_with_captions],
                lyric_analyses=lyric_analyses,
                enrichment_score=enriched_profile.enrichment_score,
                discovery_session_id=session_id
            )
            
            # Phase 5: Store in database
            await self.storage_agent.store_artist_profile(deps, enriched_artist.profile)
            
            logger.info(f"🎨 Artist processing completed: {artist_name} (score: {enriched_profile.enrichment_score:.2f})")
            return enriched_artist
            
        except Exception as e:
            logger.error(f"❌ Artist processing failed for {artist_name}: {e}")
            return None
    
    async def _check_for_existing_artist(
        self,
        deps: PipelineDependencies,
        channel_id: str
    ) -> Optional[EnrichedArtistData]:
        """Check if artist already exists in database"""
        try:
            return await self.storage_agent.get_artist_by_channel_id(deps, channel_id)
        except Exception as e:
            logger.error(f"Error checking for existing artist: {e}")
            return None
    
    async def _enrich_artist_with_retry(
        self,
        deps: PipelineDependencies,
        profile: ArtistProfile,
        max_retries: int = 3
    ) -> ArtistProfile:
        """Enrich artist profile with retry logic and exponential backoff"""
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Enrichment attempt {attempt + 1} for {profile.name}")
                
                # Use enrichment agent if available
                if self.enrichment_agent:
                    enrichment_result = await self.enrichment_agent.enrich_artist_basic(
                        profile, deps
                    )
                    
                    if enrichment_result.get("success"):
                        # Update profile with enrichment data
                        original_score = profile.enrichment_score
                        profile.enrichment_score = enrichment_result.get("enrichment_score", 0.0)
                        profile.metadata.update({
                            "enrichment_data": enrichment_result,
                            "enhanced_agent_used": True
                        })
                        logger.info(f"✅ Enhanced enrichment successful for {profile.name} (score: {profile.enrichment_score:.2f})")
                        return profile
                    else:
                        logger.warning(f"⚠️ Enhanced enrichment failed for {profile.name}")
                else:
                    logger.warning(f"⚠️ Enrichment agent not available for {profile.name}")
                
                # If enrichment didn't improve the profile, return original
                if attempt == max_retries - 1:
                    logger.warning(f"⚠️ Enrichment did not improve profile after {max_retries} attempts")
                    return profile
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ Enrichment failed after {max_retries} attempts for {profile.name}: {e}")
                    return profile
                else:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"⏳ Enrichment attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
        
        return profile

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
        
        # If paused, wait for resume
        while control['should_pause'] and not control['should_stop']:
            time.sleep(1)  # Check every second
            
        if control['is_paused'] and not control['should_pause']:
            control['is_paused'] = False
            logger.info(f"▶️ Session {session_id} resumed")
        
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