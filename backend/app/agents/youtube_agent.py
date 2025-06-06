# backend/app/agents/youtube_agent.py
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import List, Optional, Dict, Any
import logging
import re
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import asyncio
import json

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.core import quota_manager, response_cache, deduplication_manager
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
                    - Recent uploads (last 7 days preferred)
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
        """Search for emerging music artists by finding recent videos with low view counts"""
        
        try:
            # Step 1: Search for recent videos (last 7 days) with music-related queries
            from datetime import datetime, timedelta
            
            # Calculate date 7 days ago for publishedAfter filter
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Enhanced search query for emerging music content
            music_queries = [
                f"{query} music original song",
                f"{query} artist new music",
                f"{query} singer songwriter",
                f"{query} musician debut"
            ]
            
            all_channels = {}  # Use dict to avoid duplicates
            
            for search_query in music_queries:
                logger.info(f"🔎 Searching for recent videos: '{search_query}'")
                
                search_url = f"{self.base_url}/search"
                params = {
                    "key": settings.YOUTUBE_API_KEY,
                    "q": search_query,
                    "type": "video",
                    "part": "snippet",
                    "maxResults": 25,  # Search more videos to filter channels
                    "order": "date",  # Most recent first
                    "publishedAfter": seven_days_ago,  # Last 7 days only
                    "regionCode": "US",
                    "safeSearch": "moderate",
                    "videoCategoryId": "10"  # Music category
                }
                
                response = await deps.http_client.get(search_url, params=params)
                
                if response.status_code == 403:
                    quota_info = response.json().get('error', {}).get('message', '')
                    if 'quota' in quota_info.lower():
                        logger.error(f"❌ YouTube quota exceeded: {quota_info}")
                        break
                    else:
                        logger.error(f"❌ YouTube API access denied: {quota_info}")
                        continue
                
                response.raise_for_status()
                data = response.json()
                
                # Step 2: Get video statistics to filter by view count
                video_ids = [item['id']['videoId'] for item in data.get('items', [])]
                
                if video_ids:
                    filtered_channels = await self._filter_videos_by_view_count(
                        deps, video_ids, data.get('items', [])
                    )
                    
                    # Merge results, avoiding duplicates
                    for channel in filtered_channels:
                        channel_id = channel['channel_id']
                        if channel_id not in all_channels:
                            all_channels[channel_id] = channel
                
                # Rate limit between searches
                await asyncio.sleep(0.5)
            
            channels_list = list(all_channels.values())
            logger.info(f"📊 Found {len(channels_list)} unique emerging artist channels")
            return channels_list[:max_results]
            
        except Exception as e:
            logger.error(f"❌ Emerging artist search error: {e}")
            return []
    
    async def _filter_videos_by_view_count(
        self,
        deps: PipelineDependencies,
        video_ids: List[str],
        video_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter videos by view count and extract channel info from qualifying videos"""
        
        if not video_ids:
            return []
        
        try:
            # Get video statistics
            videos_url = f"{self.base_url}/videos"
            params = {
                "key": settings.YOUTUBE_API_KEY,
                "id": ",".join(video_ids),
                "part": "statistics,snippet"
            }
            
            response = await deps.http_client.get(videos_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Create lookup for video stats
            video_stats = {}
            for item in data.get('items', []):
                video_id = item['id']
                view_count = int(item.get('statistics', {}).get('viewCount', 0))
                video_stats[video_id] = {
                    'view_count': view_count,
                    'like_count': int(item.get('statistics', {}).get('likeCount', 0)),
                    'comment_count': int(item.get('statistics', {}).get('commentCount', 0))
                }
            
            # Filter videos with < 100k views and extract channels
            qualifying_channels = {}
            
            for video_item in video_items:
                video_id = video_item['id']['videoId']
                
                if video_id in video_stats:
                    view_count = video_stats[video_id]['view_count']
                    
                    # Filter: Less than 100k views for emerging artists
                    if view_count < 100000:
                        channel_id = video_item['snippet']['channelId']
                        
                        if channel_id not in qualifying_channels:
                            qualifying_channels[channel_id] = {
                                'channel_id': channel_id,
                                'channel_title': video_item['snippet']['channelTitle'],
                                'channel_description': '',  # Will be enriched later
                                'thumbnail_url': video_item['snippet']['thumbnails'].get('default', {}).get('url'),
                                'published_at': video_item['snippet']['publishedAt'],
                                'qualifying_videos': [],
                                'total_qualifying_views': 0
                            }
                        
                        # Track qualifying videos for this channel
                        qualifying_channels[channel_id]['qualifying_videos'].append({
                            'video_id': video_id,
                            'title': video_item['snippet']['title'],
                            'view_count': view_count,
                            'published_at': video_item['snippet']['publishedAt']
                        })
                        qualifying_channels[channel_id]['total_qualifying_views'] += view_count
                        
                        logger.debug(f"✅ Qualifying video: '{video_item['snippet']['title']}' ({view_count:,} views)")
            
            channels_list = list(qualifying_channels.values())
            logger.info(f"🎯 Found {len(channels_list)} channels with emerging content (< 100k views, last 7 days)")
            
            return channels_list
            
        except Exception as e:
            logger.error(f"❌ Error filtering videos by view count: {e}")
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
            
            # Extract artist names from video titles for each channel
            for channel in batch_results:
                extracted_artist_name = self._extract_artist_name_from_videos(channel)
                if extracted_artist_name:
                    channel['extracted_artist_name'] = extracted_artist_name
                    logger.info(f"🎤 Extracted artist name: '{extracted_artist_name}' from channel '{channel.get('channel_title')}'")
                else:
                    channel['extracted_artist_name'] = channel.get('channel_title', 'Unknown Artist')
                    logger.debug(f"🔍 Using channel title as artist name: '{channel['extracted_artist_name']}'")
            
            enriched_channels.extend(batch_results)
            
            # Rate limiting between batches
            if i + batch_size < len(channels):
                await asyncio.sleep(1)
        
        return enriched_channels
    
    def _extract_artist_name_from_videos(self, channel_data: Dict[str, Any]) -> Optional[str]:
        """Extract the most likely artist name from video titles"""
        
        qualifying_videos = channel_data.get('qualifying_videos', [])
        if not qualifying_videos:
            return None
        
        video_titles = [video.get('title', '') for video in qualifying_videos]
        
        # Common patterns for music video titles
        artist_name_candidates = []
        
        for title in video_titles:
            if not title:
                continue
            
            # Pattern 1: "Artist Name - Song Title" (most common)
            if ' - ' in title:
                potential_artist = title.split(' - ')[0].strip()
                if potential_artist and not self._is_likely_not_artist_name(potential_artist):
                    artist_name_candidates.append(potential_artist)
            
            # Pattern 2: "Artist Name | Song Title"
            elif ' | ' in title:
                potential_artist = title.split(' | ')[0].strip()
                if potential_artist and not self._is_likely_not_artist_name(potential_artist):
                    artist_name_candidates.append(potential_artist)
            
            # Pattern 3: "Song Title by Artist Name"
            elif ' by ' in title.lower():
                parts = title.lower().split(' by ')
                if len(parts) >= 2:
                    potential_artist = parts[-1].strip()
                    if potential_artist and not self._is_likely_not_artist_name(potential_artist):
                        artist_name_candidates.append(potential_artist.title())
            
            # Pattern 4: "Artist Name: Song Title"
            elif ': ' in title:
                potential_artist = title.split(': ')[0].strip()
                if potential_artist and not self._is_likely_not_artist_name(potential_artist):
                    artist_name_candidates.append(potential_artist)
            
            # Pattern 5: Remove common prefixes/suffixes and use first part
            else:
                cleaned_title = self._clean_video_title(title)
                if cleaned_title and not self._is_likely_not_artist_name(cleaned_title):
                    artist_name_candidates.append(cleaned_title)
        
        if not artist_name_candidates:
            return None
        
        # Find the most common artist name candidate
        from collections import Counter
        name_counts = Counter(artist_name_candidates)
        most_common_name = name_counts.most_common(1)[0][0] if name_counts else None
        
        # Validate the extracted name
        if most_common_name and self._validate_artist_name(most_common_name):
            return most_common_name
        
        return None
    
    def _clean_video_title(self, title: str) -> str:
        """Clean video title to extract potential artist name"""
        import re
        
        # Remove common music video indicators
        patterns_to_remove = [
            r'\(official.*?\)',
            r'\[official.*?\]',
            r'\(music.*?\)',
            r'\[music.*?\]',
            r'\(audio.*?\)',
            r'\[audio.*?\]',
            r'\(video.*?\)',
            r'\[video.*?\]',
            r'\(lyric.*?\)',
            r'\[lyric.*?\]',
            r'\(feat\..*?\)',
            r'\[feat\..*?\]',
            r'\(ft\..*?\)',
            r'\[ft\..*?\]',
            r'official',
            r'music video',
            r'official video',
            r'official audio',
            r'lyric video'
        ]
        
        cleaned = title.lower()
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove extra whitespace and title case
        cleaned = ' '.join(cleaned.split()).title()
        
        # Take first meaningful part (before common separators)
        for separator in [' - ', ' | ', ': ', ' (', ' [']:
            if separator in cleaned:
                cleaned = cleaned.split(separator)[0].strip()
                break
        
        return cleaned if len(cleaned) > 2 else ""
    
    def _is_likely_not_artist_name(self, name: str) -> bool:
        """Check if a string is likely NOT an artist name"""
        if not name or len(name.strip()) < 2:
            return True
        
        name_lower = name.lower().strip()
        
        # Common non-artist terms
        non_artist_terms = [
            'official', 'music', 'video', 'audio', 'lyric', 'lyrics', 
            'feat', 'featuring', 'ft', 'remix', 'cover', 'live',
            'new', 'latest', 'best', 'top', 'album', 'single',
            'song', 'track', 'ep', 'mixtape', 'full', 'hd', 'hq',
            'youtube', 'vevo', 'records', 'entertainment', 'production',
            'the official', 'music video', 'official video'
        ]
        
        # Check if the name is just common terms
        if name_lower in non_artist_terms:
            return True
        
        # Check if it starts/ends with common non-artist patterns
        if (name_lower.startswith(('official ', 'new ', 'latest ')) or 
            name_lower.endswith((' official', ' music', ' video', ' audio', ' records'))):
            return True
        
        # Check for excessive length (likely description, not name)
        if len(name) > 50:
            return True
        
        # Check for numbers/years that suggest it's not an artist name
        if re.match(r'^\d{4}$', name.strip()):  # Just a year
            return True
        
        return False
    
    def _validate_artist_name(self, name: str) -> bool:
        """Validate that the extracted name looks like a real artist name"""
        if not name or len(name.strip()) < 2:
            return False
        
        name = name.strip()
        
        # Basic validation rules
        # Should not be all numbers
        if name.isdigit():
            return False
        
        # Should not be excessively long
        if len(name) > 40:
            return False
        
        # Should contain at least one letter
        if not re.search(r'[a-zA-Z]', name):
            return False
        
        # Should not be common YouTube/music terms
        if self._is_likely_not_artist_name(name):
            return False
        
        return True
    
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
                
                # Enhanced stats for emerging artist discovery
                subscriber_count = int(stats.get('subscriberCount', 0))
                video_count = int(stats.get('videoCount', 0))
                view_count = int(stats.get('viewCount', 0))
                
                stats_lookup[channel_id] = {
                    'subscriber_count': subscriber_count,
                    'video_count': video_count,
                    'view_count': view_count,
                    'country': snippet.get('country'),
                    'custom_url': snippet.get('customUrl'),
                    'keywords': branding.get('channel', {}).get('keywords', ''),
                    'has_recent_uploads': self._check_recent_uploads(stats),
                    'has_music_content': self._check_music_content(snippet, branding),
                    'channel_description': snippet.get('description', ''),
                    'created_at': snippet.get('publishedAt'),
                    # Flag for emerging artist status
                    'is_likely_emerging': subscriber_count < 50000 and view_count < 500000
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
        """Apply quality filters optimized for emerging artists discovery"""
        
        if not channels:
            return []
        
        logger.info(f"🎯 Applying emerging artist quality filters to {len(channels)} channels")
        
        filtered_channels = []
        
        for channel in channels:
            # Emerging artist quality thresholds (more lenient for discovery)
            min_subscribers = 10  # Very low threshold for emerging artists
            max_subscribers = 50000  # Upper limit to avoid big names
            min_videos = 1  # At least one video
            max_total_views = 500000  # Total channel views limit for emerging status
            min_recent_activity = True  # Must have qualifying videos from last 7 days
            
            # Get channel stats (with defaults for emerging channels)
            subscriber_count = channel.get('subscriber_count', 0)
            video_count = channel.get('video_count', 0)
            total_views = channel.get('view_count', 0)
            qualifying_videos = channel.get('qualifying_videos', [])
            
            # Calculate emerging artist score
            emerging_score = self._calculate_emerging_artist_score(channel)
            
            # Check emerging artist filters
            passes_filters = (
                # Basic activity requirements
                subscriber_count >= min_subscribers and
                subscriber_count <= max_subscribers and
                video_count >= min_videos and
                total_views <= max_total_views and
                
                # Must have recent qualifying content
                len(qualifying_videos) > 0 and
                
                # Minimum emerging artist score
                emerging_score >= 0.3 and
                
                # Deduplication check
                not deduplication_manager.is_duplicate(channel)
            )
            
            if passes_filters:
                # Add emerging artist metadata
                channel['emerging_score'] = emerging_score
                channel['is_emerging_artist'] = True
                channel['discovery_criteria'] = {
                    'recent_videos_count': len(qualifying_videos),
                    'avg_views_per_recent_video': channel.get('total_qualifying_views', 0) / max(len(qualifying_videos), 1),
                    'subscriber_to_view_ratio': subscriber_count / max(total_views, 1)
                }
                
                filtered_channels.append(channel)
                deduplication_manager.mark_as_processed(channel)
                
                logger.info(f"✅ Emerging artist found: {channel.get('channel_title')} "
                          f"({subscriber_count:,} subs, {len(qualifying_videos)} recent videos, score: {emerging_score:.2f})")
            else:
                filter_reasons = []
                if subscriber_count < min_subscribers:
                    filter_reasons.append(f"too few subscribers ({subscriber_count})")
                if subscriber_count > max_subscribers:
                    filter_reasons.append(f"too many subscribers ({subscriber_count:,}) - likely established artist")
                if total_views > max_total_views:
                    filter_reasons.append(f"too many total views ({total_views:,}) - likely established")
                if len(qualifying_videos) == 0:
                    filter_reasons.append("no recent qualifying videos")
                if emerging_score < 0.3:
                    filter_reasons.append(f"low emerging score ({emerging_score:.2f})")
                
                logger.debug(f"⚠️ Filtered out: {channel.get('channel_title')} - {', '.join(filter_reasons)}")
        
        logger.info(f"🎯 Emerging artist filtering complete: {len(filtered_channels)}/{len(channels)} channels passed")
        return filtered_channels
    
    def _calculate_emerging_artist_score(self, channel: Dict[str, Any]) -> float:
        """Calculate score specifically for emerging artist potential"""
        try:
            score = 0.0
            
            # Get metrics
            subscriber_count = channel.get('subscriber_count', 0)
            video_count = channel.get('video_count', 0)
            qualifying_videos = channel.get('qualifying_videos', [])
            total_qualifying_views = channel.get('total_qualifying_views', 0)
            
            # Recent activity (most important for emerging artists)
            if len(qualifying_videos) > 0:
                score += 0.4  # Base score for having recent content
                
                # Bonus for multiple recent videos
                if len(qualifying_videos) >= 2:
                    score += 0.1
                if len(qualifying_videos) >= 3:
                    score += 0.1
            
            # Engagement potential (views vs subscribers)
            if subscriber_count > 0 and total_qualifying_views > 0:
                avg_views_per_video = total_qualifying_views / len(qualifying_videos) if qualifying_videos else 0
                
                # Good engagement for emerging artists (views per video vs subscriber count)
                if avg_views_per_video > subscriber_count * 0.1:  # 10% of subscribers watch
                    score += 0.2
                elif avg_views_per_video > subscriber_count * 0.05:  # 5% watch
                    score += 0.1
            
            # Content consistency
            if video_count > 0:
                # Regular content creation
                if video_count >= 5:
                    score += 0.1
                elif video_count >= 3:
                    score += 0.05
            
            # Growth potential indicators
            if subscriber_count > 0:
                # Sweet spot for emerging artists
                if 50 <= subscriber_count <= 5000:
                    score += 0.1
                elif 10 <= subscriber_count <= 50:
                    score += 0.05
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating emerging artist score: {e}")
            return 0.0
    
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