# backend/app/agents/youtube_agent.py
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import asyncio
import json

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.core.quota_manager import quota_manager, response_cache, deduplication_manager
from app.models.artist import VideoMetadata

logger = logging.getLogger(__name__)

# Safe agent factory - creates agents on-demand with error handling
def create_youtube_agent():
    """Safely create YouTube agent with fallback options"""
    try:
        from app.core.config import settings
        
        # Try DeepSeek first
        if settings.is_deepseek_configured():
            try:
                agent = Agent(
                    model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
                    system_prompt="""You are a YouTube music discovery specialist. Your role is to:
                    1. Search for emerging music artists on YouTube
                    2. Extract video metadata and channel information
                    3. Identify potential music videos vs other content
                    4. Retrieve video captions when available
                    
                    Focus on finding artists with:
                    - Less than 100k views on recent videos
                    - Music-related content (official videos, audio, performances)
                    - English language content primarily
                    - Recent uploads (last 30 days preferred)
                    """
                )
                logger.info("✅ Created YouTube agent with DeepSeek AI")
                return agent
            except Exception as e:
                logger.warning(f"⚠️ DeepSeek failed: {e}")
        
        # Fallback to OpenAI
        try:
            agent = Agent(
                model='gpt-3.5-turbo',
                system_prompt="""You are a YouTube music discovery specialist. Your role is to:
                1. Search for emerging music artists on YouTube
                2. Extract video metadata and channel information
                3. Identify potential music videos vs other content
                4. Retrieve video captions when available
                
                Focus on finding artists with:
                - Less than 100k views on recent videos
                - Music-related content (official videos, audio, performances)
                - English language content primarily
                - Recent uploads (last 30 days preferred)
                """
            )
            logger.info("✅ Created YouTube agent with OpenAI fallback")
            return agent
        except Exception as e:
            logger.warning(f"⚠️ OpenAI fallback failed: {e}")
            
    except Exception as e:
        logger.error(f"❌ Agent creation failed: {e}")
    
    return None

# YouTube agent tools (defined separately to avoid import-time blocking)
async def ai_search_youtube_videos(
    agent: Agent,
    deps: PipelineDependencies,
    query: str = "official music video",
    max_results: int = 50,
    published_after: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """AI-powered YouTube search with intelligent filtering"""
    try:
        # Use the AI agent to intelligently search and filter
        result = await agent.run(
            f"""Search YouTube for emerging music artists using query: "{query}"
            Max results: {max_results}
            Published after: {published_after}
            
            Focus on:
            - Independent/emerging artists (under 100k views)
            - High-quality music content
            - Recent uploads
            - Authentic music videos vs covers/remixes
            
            Return structured data with artist analysis.""",
            deps=deps
        )
        return result.data if hasattr(result, 'data') else []
    except Exception as e:
        logger.error(f"❌ AI search failed: {e}")
        return []

async def ai_analyze_artist_potential(
    agent: Agent,
    deps: PipelineDependencies,
    artist_data: Dict[str, Any]
) -> Dict[str, Any]:
    """AI analysis of artist discovery potential"""
    try:
        result = await agent.run(
            f"""Analyze this artist's discovery potential:
            {artist_data}
            
            Evaluate:
            - Music quality and uniqueness
            - Growth trajectory and engagement
            - Genre appeal and market fit
            - Professional presentation
            - Commercial viability
            
            Return discovery score (1-10) with reasoning.""",
            deps=deps
        )
        return result.data if hasattr(result, 'data') else {"score": 5, "reasoning": "AI analysis unavailable"}
    except Exception as e:
        logger.error(f"❌ AI analysis failed: {e}")
        return {"score": 5, "reasoning": f"Analysis failed: {e}"}

class YouTubeDiscoveryAgent:
    """Enhanced YouTube Discovery Agent with quota management and caching"""
    
    def __init__(self):
        self.base_url = "https://www.googleapis.com/youtube/v3"
        logger.info("🎬 YouTubeDiscoveryAgent initialized with quota management")
    
    async def discover_artists(
        self,
        deps: PipelineDependencies,
        query: str,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Discover artists using YouTube API with intelligent quota management"""
        
        logger.info(f"🔍 Discovering artists for query: '{query}', max_results: {max_results}")
        
        if not settings.is_youtube_configured():
            logger.warning("⚠️ YouTube API not configured")
            return []
        
        try:
            # Check quota availability
            if not await quota_manager.can_perform_operation('youtube', 'search', 1):
                logger.error("❌ YouTube quota insufficient for search operation")
                return []
            
            # Check cache first
            cache_key = {'query': query, 'max_results': max_results}
            cached_result = await response_cache.get('youtube', 'search_artists', cache_key)
            if cached_result:
                logger.info("📦 Using cached YouTube search results")
                return cached_result
            
            # Perform search
            search_results = await self._search_channels(deps, query, max_results)
            
            if not search_results:
                logger.warning("⚠️ No search results returned from YouTube API")
                return []
            
            # Enrich with channel details
            enriched_artists = await self._enrich_channels_with_details(deps, search_results)
            
            # Quality filtering
            filtered_artists = await self._apply_quality_filters(enriched_artists)
            
            # Cache the results
            await response_cache.set('youtube', 'search_artists', cache_key, filtered_artists, ttl=1800)  # 30 min cache
            
            # Record successful operation
            await quota_manager.record_operation('youtube', 'search', 1, success=True)
            
            logger.info(f"✅ Discovered {len(filtered_artists)} quality artists from {len(search_results)} candidates")
            return filtered_artists
            
        except Exception as e:
            logger.error(f"❌ YouTube discovery error: {e}")
            await quota_manager.record_operation('youtube', 'search', 1, success=False)
            return []
    
    async def _search_channels(
        self,
        deps: PipelineDependencies,
        query: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Search for music channels using YouTube API"""
        
        try:
            # Enhanced search query for music artists
            enhanced_query = f"{query} music artist singer musician"
            
            search_url = f"{self.base_url}/search"
            params = {
                "key": settings.YOUTUBE_API_KEY,
                "q": enhanced_query,
                "type": "channel",
                "part": "snippet",
                "maxResults": min(max_results, 50),  # API limit
                "order": "relevance",
                "regionCode": "US",
                "safeSearch": "moderate"
            }
            
            logger.info(f"🔎 Searching YouTube channels with query: '{enhanced_query}'")
            
            response = await deps.http_client.get(search_url, params=params)
            
            if response.status_code == 403:
                quota_info = response.json().get('error', {}).get('message', '')
                if 'quota' in quota_info.lower():
                    logger.error(f"❌ YouTube quota exceeded: {quota_info}")
                    return []
                else:
                    logger.error(f"❌ YouTube API access denied: {quota_info}")
                    return []
            
            response.raise_for_status()
            data = response.json()
            
            channels = []
            for item in data.get('items', []):
                channel_info = {
                    'channel_id': item['id']['channelId'],
                    'channel_title': item['snippet']['title'],
                    'channel_description': item['snippet']['description'],
                    'thumbnail_url': item['snippet']['thumbnails'].get('default', {}).get('url'),
                    'published_at': item['snippet']['publishedAt']
                }
                channels.append(channel_info)
            
            logger.info(f"📊 Found {len(channels)} channels from search")
            return channels
            
        except Exception as e:
            logger.error(f"❌ Channel search error: {e}")
            return []
    
    async def _enrich_channels_with_details(
        self,
        deps: PipelineDependencies,
        channels: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enrich channels with detailed statistics and metadata"""
        
        if not channels:
            return []
        
        logger.info(f"📈 Enriching {len(channels)} channels with details")
        
        # Check quota for batch operation
        if not await quota_manager.can_perform_operation('youtube', 'channels', len(channels)):
            logger.warning("⚠️ Limited quota, enriching subset of channels")
            channels = channels[:10]  # Limit to conserve quota
        
        enriched_channels = []
        
        # Process in batches to respect rate limits
        batch_size = 10
        for i in range(0, len(channels), batch_size):
            batch = channels[i:i + batch_size]
            batch_results = await self._enrich_channel_batch(deps, batch)
            enriched_channels.extend(batch_results)
            
            # Rate limiting between batches
            if i + batch_size < len(channels):
                await asyncio.sleep(1)
        
        return enriched_channels
    
    async def _enrich_channel_batch(
        self,
        deps: PipelineDependencies,
        channels: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enrich a batch of channels with statistics"""
        
        channel_ids = [ch['channel_id'] for ch in channels]
        
        try:
            # Get channel statistics
            channels_url = f"{self.base_url}/channels"
            params = {
                "key": settings.YOUTUBE_API_KEY,
                "id": ",".join(channel_ids),
                "part": "statistics,snippet,brandingSettings,contentDetails",
                "maxResults": 50
            }
            
            response = await deps.http_client.get(channels_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Create lookup dict for enrichment
            stats_lookup = {}
            for item in data.get('items', []):
                channel_id = item['id']
                stats = item.get('statistics', {})
                snippet = item.get('snippet', {})
                branding = item.get('brandingSettings', {})
                
                stats_lookup[channel_id] = {
                    'subscriber_count': int(stats.get('subscriberCount', 0)),
                    'video_count': int(stats.get('videoCount', 0)),
                    'view_count': int(stats.get('viewCount', 0)),
                    'country': snippet.get('country'),
                    'custom_url': snippet.get('customUrl'),
                    'keywords': branding.get('channel', {}).get('keywords', ''),
                    'has_recent_uploads': self._check_recent_uploads(stats),
                    'has_music_content': self._check_music_content(snippet, branding)
                }
            
            # Merge with original channel data
            enriched = []
            for channel in channels:
                channel_id = channel['channel_id']
                if channel_id in stats_lookup:
                    enhanced_channel = {**channel, **stats_lookup[channel_id]}
                    
                    # Add quality indicators
                    enhanced_channel['engagement_score'] = self._calculate_engagement_score(enhanced_channel)
                    enhanced_channel['music_relevance_score'] = self._calculate_music_relevance(enhanced_channel)
                    
                    enriched.append(enhanced_channel)
            
            # Record successful operation
            await quota_manager.record_operation('youtube', 'channels', len(channels), success=True)
            
            return enriched
            
        except Exception as e:
            logger.error(f"❌ Channel enrichment error: {e}")
            await quota_manager.record_operation('youtube', 'channels', len(channels), success=False)
            # Return original channels without enrichment
            return channels
    
    def _check_recent_uploads(self, stats: Dict[str, Any]) -> bool:
        """Check if channel has recent upload activity"""
        video_count = int(stats.get('videoCount', 0))
        return video_count > 5  # Simple heuristic
    
    def _check_music_content(self, snippet: Dict[str, Any], branding: Dict[str, Any]) -> bool:
        """Check if channel appears to be music-related"""
        music_keywords = [
            'music', 'artist', 'singer', 'musician', 'song', 'album', 
            'track', 'band', 'rap', 'hip hop', 'pop', 'rock', 'electronic'
        ]
        
        # Check description and keywords
        description = snippet.get('description', '').lower()
        keywords = branding.get('channel', {}).get('keywords', '').lower()
        title = snippet.get('title', '').lower()
        
        text_to_check = f"{description} {keywords} {title}"
        
        return any(keyword in text_to_check for keyword in music_keywords)
    
    def _calculate_engagement_score(self, channel: Dict[str, Any]) -> float:
        """Calculate engagement score based on channel metrics"""
        try:
            subscribers = channel.get('subscriber_count', 0)
            videos = channel.get('video_count', 0)
            views = channel.get('view_count', 0)
            
            if videos == 0 or subscribers == 0:
                return 0.0
            
            # Calculate metrics
            avg_views_per_video = views / videos if videos > 0 else 0
            subscriber_to_video_ratio = subscribers / videos if videos > 0 else 0
            
            # Normalize and combine scores
            score = 0.0
            
            # Subscriber score (logarithmic scaling)
            if subscribers > 0:
                score += min(0.3, (subscribers / 10000) * 0.3)
            
            # Video count score
            if videos > 0:
                score += min(0.2, (videos / 100) * 0.2)
            
            # Engagement score
            if avg_views_per_video > 100:
                score += min(0.3, (avg_views_per_video / 10000) * 0.3)
            
            # Consistency score
            if subscriber_to_video_ratio > 10:
                score += 0.2
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Engagement score calculation error: {e}")
            return 0.0
    
    def _calculate_music_relevance(self, channel: Dict[str, Any]) -> float:
        """Calculate how relevant the channel is to music"""
        score = 0.0
        
        try:
            # Music content check
            if channel.get('has_music_content', False):
                score += 0.5
            
            # Keywords analysis
            keywords = channel.get('keywords', '').lower()
            description = channel.get('channel_description', '').lower()
            title = channel.get('channel_title', '').lower()
            
            music_terms = ['music', 'artist', 'singer', 'band', 'musician', 'rapper', 'producer']
            genre_terms = ['pop', 'rock', 'hip hop', 'rap', 'electronic', 'indie', 'folk', 'jazz']
            
            text_content = f"{keywords} {description} {title}"
            
            # Music term presence
            music_term_count = sum(1 for term in music_terms if term in text_content)
            score += min(0.3, music_term_count * 0.1)
            
            # Genre term presence
            genre_term_count = sum(1 for term in genre_terms if term in text_content)
            score += min(0.2, genre_term_count * 0.05)
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Music relevance calculation error: {e}")
            return 0.0
    
    async def _apply_quality_filters(self, channels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply quality filters to remove low-quality channels"""
        
        if not channels:
            return []
        
        logger.info(f"🎯 Applying quality filters to {len(channels)} channels")
        
        filtered_channels = []
        
        for channel in channels:
            # Quality thresholds
            min_subscribers = 50
            min_videos = 3
            min_engagement_score = 0.1
            min_music_relevance = 0.2
            
            # Check filters
            if (channel.get('subscriber_count', 0) >= min_subscribers and
                channel.get('video_count', 0) >= min_videos and
                channel.get('engagement_score', 0) >= min_engagement_score and
                channel.get('music_relevance_score', 0) >= min_music_relevance and
                not deduplication_manager.is_duplicate(channel)):
                
                filtered_channels.append(channel)
                deduplication_manager.mark_as_processed(channel)
                
                logger.debug(f"✅ Channel passed filters: {channel.get('channel_title')}")
            else:
                logger.debug(f"⚠️ Channel filtered out: {channel.get('channel_title')}")
        
        logger.info(f"🎯 Quality filtering complete: {len(filtered_channels)}/{len(channels)} channels passed")
        return filtered_channels
    
    async def get_artist_videos_with_captions(
        self,
        deps: PipelineDependencies,
        channel_id: str,
        max_videos: int = 10
    ) -> List[Dict[str, Any]]:
        """Get videos from artist's channel with captions"""
        
        logger.info(f"🎥 Getting videos with captions for channel: {channel_id}")
        
        if not settings.is_youtube_configured():
            logger.warning("⚠️ YouTube API not configured")
            return []
        
        try:
            # Check quota for operation
            if not await quota_manager.can_perform_operation('youtube', 'channel_videos', 1):
                logger.warning("⚠️ Limited quota for video retrieval")
                max_videos = 3  # Reduce scope
            
            # Check cache
            cache_key = {'channel_id': channel_id, 'max_videos': max_videos}
            cached_result = await response_cache.get('youtube', 'channel_videos', cache_key)
            if cached_result:
                logger.info("📦 Using cached video results")
                return cached_result
            
            # Get channel uploads playlist
            uploads_playlist_id = await self._get_uploads_playlist_id(deps, channel_id)
            if not uploads_playlist_id:
                logger.warning(f"⚠️ Could not find uploads playlist for channel {channel_id}")
                return []
            
            # Get recent videos from playlist
            videos = await self._get_playlist_videos(deps, uploads_playlist_id, max_videos)
            
            if not videos:
                logger.warning(f"⚠️ No videos found for channel {channel_id}")
                return []
            
            # Get captions for videos
            videos_with_captions = await self._get_videos_with_captions(deps, videos)
            
            # Cache results
            await response_cache.set('youtube', 'channel_videos', cache_key, videos_with_captions, ttl=3600)
            
            # Record operation
            await quota_manager.record_operation('youtube', 'channel_videos', 1, success=True)
            
            logger.info(f"✅ Retrieved {len(videos_with_captions)} videos with captions")
            return videos_with_captions
            
        except Exception as e:
            logger.error(f"❌ Error getting videos with captions: {e}")
            await quota_manager.record_operation('youtube', 'channel_videos', 1, success=False)
            return []
    
    async def _get_uploads_playlist_id(self, deps: PipelineDependencies, channel_id: str) -> Optional[str]:
        """Get the uploads playlist ID for a channel"""
        try:
            channels_url = f"{self.base_url}/channels"
            params = {
                "key": settings.YOUTUBE_API_KEY,
                "id": channel_id,
                "part": "contentDetails"
            }
            
            response = await deps.http_client.get(channels_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('items'):
                uploads_playlist_id = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                return uploads_playlist_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting uploads playlist: {e}")
            return None
    
    async def _get_playlist_videos(
        self,
        deps: PipelineDependencies,
        playlist_id: str,
        max_videos: int
    ) -> List[Dict[str, Any]]:
        """Get videos from a playlist"""
        try:
            playlist_url = f"{self.base_url}/playlistItems"
            params = {
                "key": settings.YOUTUBE_API_KEY,
                "playlistId": playlist_id,
                "part": "snippet",
                "maxResults": min(max_videos, 20),
                "order": "date"
            }
            
            response = await deps.http_client.get(playlist_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            videos = []
            for item in data.get('items', []):
                video_info = {
                    'video_id': item['snippet']['resourceId']['videoId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail_url': item['snippet']['thumbnails'].get('default', {}).get('url')
                }
                videos.append(video_info)
            
            return videos
            
        except Exception as e:
            logger.error(f"Error getting playlist videos: {e}")
            return []
    
    async def _get_videos_with_captions(
        self,
        deps: PipelineDependencies,
        videos: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get captions for videos that have them available"""
        
        videos_with_captions = []
        
        for video in videos:
            video_id = video['video_id']
            
            # Check quota before getting captions
            if not await quota_manager.can_perform_operation('youtube', 'captions', 1):
                logger.warning("⚠️ Quota limit reached for captions")
                break
            
            try:
                # Check if captions are available
                captions_url = f"{self.base_url}/captions"
                params = {
                    "key": settings.YOUTUBE_API_KEY,
                    "videoId": video_id,
                    "part": "snippet"
                }
                
                response = await deps.http_client.get(captions_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('items'):
                        # Try to get auto-generated English captions
                        auto_caption = None
                        for caption in data['items']:
                            if (caption['snippet']['language'] == 'en' and 
                                caption['snippet']['trackKind'] == 'ASR'):
                                auto_caption = caption
                                break
                        
                        if auto_caption:
                            # Note: Getting actual caption text requires additional API call
                            # For now, mark as having captions available
                            video['captions_available'] = True
                            video['captions'] = "Captions available (text extraction not implemented)"
                            videos_with_captions.append(video)
                            
                            await quota_manager.record_operation('youtube', 'captions', 1, success=True)
                        else:
                            logger.debug(f"No auto captions for video {video_id}")
                    else:
                        logger.debug(f"No captions found for video {video_id}")
                
            except Exception as e:
                logger.error(f"Error checking captions for video {video_id}: {e}")
                await quota_manager.record_operation('youtube', 'captions', 1, success=False)
                continue
            
            # Rate limiting between caption requests
            await asyncio.sleep(0.5)
        
        return videos_with_captions