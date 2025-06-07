"""
Apify YouTube Agent - Alternative to official YouTube API
Uses apidojo/youtube-scraper actor (ID: 1p1aa7gcSydPkAE0d) to bypass quota limitations
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
import httpx
import json
from datetime import datetime
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)

class ApifyYouTubeAgent:
    """
    YouTube agent using Apify's apidojo/youtube-scraper actor (ID: 1p1aa7gcSydPkAE0d)
    
    Supports multiple input types as per official example:
    - startUrls: YouTube search URLs, video URLs, channel URLs, etc.
    - keywords: Search terms for YouTube search
    - youtubeHandles: Channel handles like @MrBeast
    
    Cost: $0.50 per 1,000 videos (much cheaper than quota issues)
    Success rate: 97%
    
    Compatible interface with YouTubeDiscoveryAgent for drop-in replacement
    """
    
    def __init__(self):
        self.apify_api_token = settings.APIFY_API_TOKEN or os.getenv('APIFY_API_TOKEN')
        self.actor_id = "apidojo~youtube-scraper"  # apidojo/youtube-scraper actor
        self.base_url = "https://api.apify.com/v2"
        
        # Use configured timeouts
        self.actor_timeout = settings.APIFY_ACTOR_TIMEOUT
        self.http_timeout = settings.APIFY_HTTP_TIMEOUT
        self.max_retries = settings.APIFY_MAX_RETRIES
        
        if not self.apify_api_token:
            logger.warning("APIFY_API_TOKEN not set - Apify YouTube scraping will be disabled")
        else:
            logger.info(f"🔧 Apify agent configured: timeout={self.actor_timeout}s, http_timeout={self.http_timeout}s")
    
    # Core methods that match YouTubeDiscoveryAgent interface
    
    async def discover_artists(
        self,
        deps,  # PipelineDependencies - keeping same signature
        query: str,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Discover artists using Apify YouTube scraper with special focus on undiscovered talent
        
        This method matches the interface of YouTubeDiscoveryAgent.discover_artists()
        and returns the same data structure expected by the orchestrator.
        
        For optimal undiscovered artist discovery, use 'official music video' as query
        """
        if not self.apify_api_token:
            logger.error("❌ Cannot discover artists - APIFY_API_TOKEN not configured")
            return []
        
        try:
            logger.info(f"🔍 Discovering artists via Apify for query: '{query}', max_results: {max_results}")
            
            # Check if this is a request for undiscovered talent discovery
            if 'official music video' in query.lower() or 'undiscovered' in query.lower() or 'new talent' in query.lower():
                logger.info("🎯 Using specialized undiscovered artist discovery")
                videos = await self.discover_undiscovered_artists(max_results=max_results * 2)
            else:
                # Standard search with optimization for recent content
                videos = await self.search_music_content(
                    keywords=[query],
                    max_results=max_results,
                    upload_date="w",  # Focus on very recent content
                    sort_by="date"  # Sort by newest first
                )
                
                # If main search fails or returns no results, try smaller searches
                if not videos and max_results > 20:
                    logger.info("🔄 Main search failed, trying smaller batch searches...")
                    videos = await self._discover_with_smaller_batches(query, max_results)
            
            if not videos:
                logger.warning("⚠️ No videos returned from Apify YouTube scraper")
                return []
            
            # Convert video data to channel data (group by channel)
            channel_data = self._convert_videos_to_channels(videos)
            
            # Apply quality filters and scoring (with emphasis on emerging artists)
            filtered_channels = await self._apply_quality_filters(channel_data)
            
            logger.info(f"✅ Discovered {len(filtered_channels)} quality artists from {len(videos)} videos")
            return filtered_channels
            
        except Exception as e:
            logger.error(f"❌ Artist discovery error: {str(e)}")
            return []
    
    async def get_artist_videos_with_captions(
        self,
        deps,  # PipelineDependencies
        channel_id: str,
        max_videos: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get videos with captions for a specific channel
        
        This method matches the interface of YouTubeDiscoveryAgent.get_artist_videos_with_captions()
        """
        if not self.apify_api_token:
            logger.error("Cannot get videos - APIFY_API_TOKEN not configured")
            return []
        
        try:
            # For Apify, we'll search by channel URL or use channel data we already have
            # This is a simplified implementation - in a real scenario you might want to
            # store channel URLs from the discovery phase
            
            logger.info(f"🎥 Getting videos with captions for channel: {channel_id}")
            
            # Get channel videos using Apify
            channel_url = f"https://www.youtube.com/channel/{channel_id}"
            videos = await self.get_channel_videos(
                channel_urls=[channel_url],
                max_videos_per_channel=max_videos
            )
            
            # For now, return videos as-is since Apify doesn't provide caption data directly
            # In production, you might want to add a separate caption extraction step
            logger.info(f"✅ Retrieved {len(videos)} videos for channel {channel_id}")
            return videos
            
        except Exception as e:
            logger.error(f"❌ Error getting videos with captions: {str(e)}")
            return []
    
    # Original Apify-specific methods
    
    async def search_music_content(self, 
                           keywords: List[str], 
                           max_results: int = 50,
                           upload_date: str = "w",
                           duration: str = "all",
                           sort_by: str = "u") -> List[Dict[str, Any]]:
        """
        Search for music content using Apify YouTube scraper with improved error handling
        
        Args:
            keywords: List of search terms (e.g., ["official music video"])
            max_results: Maximum number of videos to return
            upload_date: Filter by upload time (hour, today, week, month, year)
            duration: Video length filter (short, long, all)
            sort_by: Sort results (relevance, date, views, rating)
        
        Returns:
            List of video data dictionaries
        """
        if not self.apify_api_token:
            logger.error("❌ Cannot search - APIFY_API_TOKEN not configured")
            return []
        
        # Limit max_results to prevent extremely long runs
        max_results = min(max_results, 100)  # Cap at 100 to prevent timeouts
        
        try:
            # Prepare input for the apidojo/youtube-scraper actor following official example
            # Convert keywords to search URLs as shown in the official example
            start_urls = []
            for keyword in keywords:
                search_url = f"https://www.youtube.com/results?search_query={keyword.replace(' ', '+')}"
                start_urls.append(search_url)
            
            actor_input = {
                "startUrls": start_urls,
                "keywords": keywords,  # Also include keywords as per example
                "maxItems": max_results,
                "uploadDate": upload_date,
                "duration": duration,
                "features": "all",  # Include features parameter
                "sort": "u",
                "gl": "us",  # Geographic location
                "hl": "en"   # Language
            }
            
            logger.info(f"🔍 Starting Apify YouTube search with keywords: {keywords}, max_results: {max_results}")
            
            # Start the actor run with retry logic
            run_response = None
            for attempt in range(self.max_retries):  # 3 attempts
                try:
                    run_response = await self._start_actor_run(actor_input)
                    if run_response:
                        break
                    else:
                        logger.warning(f"⚠️ Attempt {attempt + 1} failed to start actor run")
                        if attempt < self.max_retries - 1:  # Don't sleep on last attempt
                            await asyncio.sleep(5)
                except Exception as e:
                    logger.warning(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(5)
            
            if not run_response:
                logger.error("❌ Failed to start Apify actor run after 3 attempts")
                return []
            
            run_id = run_response['data']['id']
            logger.info(f"✅ Started Apify actor run: {run_id}")
            
            # Wait for completion and get results with extended timeout
            results = await self._wait_for_completion_and_get_results(run_id, max_wait_time=self.actor_timeout)
            
            if results:
                processed_results = self._process_video_results(results)
                logger.info(f"✅ Successfully processed {len(processed_results)} videos from Apify YouTube search")
                return processed_results
            else:
                logger.warning("⚠️ No results returned from Apify YouTube scraper")
                return []
                
        except asyncio.TimeoutError:
            logger.error("❌ Apify search timed out")
            return []
        except Exception as e:
            logger.error(f"❌ Error in Apify YouTube search: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            return []
    
    async def get_channel_videos(self, 
                          channel_urls: List[str], 
                          max_videos_per_channel: int = 20) -> List[Dict[str, Any]]:
        """
        Get videos from specific YouTube channels
        
        Args:
            channel_urls: List of YouTube channel URLs
            max_videos_per_channel: Max videos to get per channel
        
        Returns:
            List of video data dictionaries
        """
        if not self.apify_api_token:
            logger.error("Cannot get channel videos - APIFY_API_TOKEN not configured")
            return []
        
        try:
            actor_input = {
                "startUrls": channel_urls,
                "maxItems": max_videos_per_channel * len(channel_urls),
                "uploadDate": "t",
                "duration": "all", 
                "features": "all",
                "sort": "r",
                "gl": "us",
                "hl": "en"
            }
            
            logger.info(f"Getting videos from {len(channel_urls)} channels")
            
            run_response = await self._start_actor_run(actor_input)
            if not run_response:
                return []
            
            run_id = run_response['data']['id']
            results = await self._wait_for_completion_and_get_results(run_id)
            
            if results:
                logger.info(f"Successfully scraped {len(results)} videos from channels")
                return self._process_video_results(results)
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting channel videos: {str(e)}")
            return []
    
    async def get_trending_music(self, max_results: int = 30) -> List[Dict[str, Any]]:
        """
        Get trending videos (can be filtered for music content)
        
        Args:
            max_results: Maximum number of trending videos
            
        Returns:
            List of video data dictionaries
        """
        if not self.apify_api_token:
            logger.error("Cannot get trending - APIFY_API_TOKEN not configured")
            return []
        
        try:
            # Use the official getTrending parameter
            actor_input = {
                "getTrending": True,
                "maxItems": max_results,
                "uploadDate": "t",
                "duration": "all",
                "features": "all", 
                "sort": "r",
                "gl": "us",
                "hl": "en"
            }
            
            logger.info("Getting trending videos from YouTube")
            
            run_response = await self._start_actor_run(actor_input)
            if not run_response:
                return []
            
            run_id = run_response['data']['id']
            results = await self._wait_for_completion_and_get_results(run_id)
            
            if results:
                # Filter for music-related content
                music_results = self._filter_music_content(results)
                logger.info(f"Found {len(music_results)} music-related trending videos")
                return self._process_video_results(music_results)
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting trending music: {str(e)}")
            return []
    
    # Internal helper methods
    
    def _convert_videos_to_channels(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert video data to channel data structure expected by orchestrator
        Groups videos by channel and creates channel-level metadata
        """
        channels_map = {}
        
        for video in videos:
            channel_id = video.get('channel_id')
            if not channel_id:
                continue
            
            if channel_id not in channels_map:
                # Create new channel entry
                channels_map[channel_id] = {
                    'channel_id': channel_id,
                    'channel_title': video.get('channel_title', 'Unknown'),
                    'channel_url': video.get('channel_url', ''),
                    'extracted_artist_name': video.get('extracted_artist_name'),
                    'videos': [],
                    'total_views': 0,
                    'total_likes': 0,
                    'video_count': 0,
                    'has_recent_uploads': True,  # Apify returns recent content
                    'has_music_content': True,   # Filtered for music content
                    'data_source': 'apify_youtube'
                }
            
            # Add video to channel
            channels_map[channel_id]['videos'].append(video)
            channels_map[channel_id]['total_views'] += video.get('view_count', 0)
            channels_map[channel_id]['total_likes'] += video.get('like_count', 0)
            channels_map[channel_id]['video_count'] += 1
            
            # Use the most popular video's artist name if available
            if video.get('extracted_artist_name') and not channels_map[channel_id]['extracted_artist_name']:
                channels_map[channel_id]['extracted_artist_name'] = video.get('extracted_artist_name')
        
        # Convert to list and add calculated metrics
        channels = list(channels_map.values())
        
        for channel in channels:
            # Calculate average metrics
            if channel['video_count'] > 0:
                channel['avg_views'] = channel['total_views'] / channel['video_count']
                channel['avg_likes'] = channel['total_likes'] / channel['video_count']
            else:
                channel['avg_views'] = 0
                channel['avg_likes'] = 0
            
            # Add subscriber count estimate based on video performance
            # This is a rough estimate since Apify doesn't provide subscriber data
            channel['subscriber_count'] = min(channel['total_views'] // 100, 1000000)  # Rough estimate
            channel['view_count'] = channel['total_views']
            
            # Set recent videos for AI analysis
            channel['recent_videos'] = channel['videos'][:5]  # Most recent 5 videos
        
        return channels
    
    async def _apply_quality_filters(self, channels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply quality filters similar to original YouTube agent"""
        filtered_channels = []
        
        for channel in channels:
            try:
                # Calculate quality score
                quality_score = self._calculate_emerging_artist_score(channel)
                channel['quality_score'] = quality_score
                
                # Apply threshold (lower than original since we're targeting emerging artists)
                if quality_score >= 0.3:  # Adjusted threshold for emerging artists
                    filtered_channels.append(channel)
                    logger.debug(f"✅ Channel passed quality filter: {channel.get('channel_title')} (score: {quality_score:.2f})")
                else:
                    logger.debug(f"⚠️ Channel filtered out: {channel.get('channel_title')} (score: {quality_score:.2f})")
                    
            except Exception as e:
                logger.warning(f"Error calculating quality score for channel: {e}")
                continue
        
        # Sort by quality score
        filtered_channels.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        
        return filtered_channels
    
    def _calculate_emerging_artist_score(self, channel: Dict[str, Any]) -> float:
        """Calculate emerging artist score for a channel with focus on undiscovered talent"""
        score = 0.0
        
        try:
            # Base metrics
            avg_views = channel.get('avg_views', 0)
            video_count = channel.get('video_count', 0)
            
            # Check if any videos have undiscovered scores (from undiscovered artist discovery)
            videos = channel.get('videos', [])
            undiscovered_scores = [v.get('undiscovered_score', 0) for v in videos if v.get('undiscovered_score')]
            
            if undiscovered_scores:
                # If we have undiscovered scores, use them heavily in calculation
                avg_undiscovered_score = sum(undiscovered_scores) / len(undiscovered_scores)
                score += avg_undiscovered_score * 0.6  # Heavy weight for undiscovered talent
                logger.debug(f"Channel has undiscovered score: {avg_undiscovered_score:.2f}")
            
            # Updated thresholds for undiscovered talent (lower view counts preferred)
            if avg_views <= 5000:
                score += 0.5  # Very low views - likely undiscovered
            elif 5000 < avg_views <= 15000:
                score += 0.4  # Low views - emerging potential
            elif 15000 < avg_views <= 50000:
                score += 0.2  # Medium views - some potential
            elif avg_views > 50000:
                score += 0.1  # Higher views - might be established
            
            # Video consistency
            if video_count >= 3:
                score += 0.2
            if video_count >= 10:
                score += 0.1
            
            # Content quality indicators
            if channel.get('has_recent_uploads', False):
                score += 0.2
            if channel.get('has_music_content', False):
                score += 0.2
            
            # Artist name extraction bonus
            if channel.get('extracted_artist_name'):
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Quality score calculation error: {e}")
            return 0.0
    
    async def _start_actor_run(self, actor_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Start an Apify actor run with improved timeout handling"""
        url = f"{self.base_url}/acts/{self.actor_id}/runs"
        headers = {
            "Authorization": f"Bearer {self.apify_api_token}",
            "Content-Type": "application/json"
        }
        
        try:
            # Debug: Log the exact payload being sent
            logger.info(f"🔍 DEBUG: Sending payload to Apify: {json.dumps(actor_input, indent=2)}")
            
            # Increase timeout for starting actor run
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(url, headers=headers, json=actor_input)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP {e.response.status_code} error starting Apify actor run")
            logger.error(f"📄 Response content: {e.response.text}")
            logger.error(f"📤 Request payload was: {json.dumps(actor_input, indent=2)}")
            return None
        except httpx.TimeoutException as e:
            logger.error(f"Timeout starting Apify actor run: {str(e)}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Failed to start Apify actor run: {str(e)}")
            return None
    
    async def _wait_for_completion_and_get_results(self, run_id: str, max_wait_time: int = None) -> Optional[List[Dict[str, Any]]]:
        """Wait for actor run to complete and return results with improved timeout handling"""
        if max_wait_time is None:
            max_wait_time = self.actor_timeout
            
        start_time = time.time()
        check_interval = 10  # Check every 10 seconds instead of 5
        
        logger.info(f"⏳ Waiting for Apify actor run {run_id} to complete (max {max_wait_time}s)")
        
        while time.time() - start_time < max_wait_time:
            try:
                # Check run status with longer timeout
                status_url = f"{self.base_url}/actor-runs/{run_id}"
                headers = {"Authorization": f"Bearer {self.apify_api_token}"}
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    status_response = await client.get(status_url, headers=headers)
                    status_response.raise_for_status()
                    status_data = status_response.json()
                
                run_status = status_data['data']['status']
                
                if run_status == 'SUCCEEDED':
                    logger.info(f"✅ Apify actor run {run_id} completed successfully")
                    # Get results with extended timeout
                    results_url = f"{self.base_url}/actor-runs/{run_id}/dataset/items"
                    async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                        results_response = await client.get(results_url, headers=headers)
                        results_response.raise_for_status()
                        results = results_response.json()
                        logger.info(f"📊 Retrieved {len(results) if results else 0} results from Apify")
                        return results
                
                elif run_status in ['FAILED', 'ABORTED', 'TIMED-OUT']:
                    logger.error(f"❌ Apify actor run {run_id} finished with status: {run_status}")
                    # Try to get error details
                    try:
                        error_details = status_data.get('data', {}).get('stats', {})
                        logger.error(f"Error details: {error_details}")
                    except:
                        pass
                    return None
                
                # Still running, wait a bit more
                elapsed = time.time() - start_time
                logger.info(f"⏳ Actor run {run_id} status: {run_status}, elapsed: {elapsed:.1f}s")
                await asyncio.sleep(check_interval)
                
            except httpx.TimeoutException as e:
                logger.warning(f"⚠️ Timeout checking run status for {run_id}: {str(e)}")
                await asyncio.sleep(check_interval)
                continue
            except httpx.RequestError as e:
                logger.warning(f"⚠️ Error checking run status for {run_id}: {str(e)}")
                await asyncio.sleep(check_interval)
                continue
        
        logger.error(f"❌ Actor run {run_id} timed out after {max_wait_time} seconds")
        return None
    
    def _process_video_results(self, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and normalize video results from Apify"""
        processed_results = []
        
        for item in raw_results:
            try:
                # Extract artist name from video title (similar to your existing logic)
                extracted_artist = self._extract_artist_name_from_title(item.get('title', ''))
                
                processed_video = {
                    'video_id': item.get('id', ''),
                    'youtube_video_id': item.get('id', ''),  # Add required field for VideoMetadata model
                    'title': item.get('title', ''),
                    'description': item.get('description', ''),
                    'channel_id': item.get('channel', {}).get('id', ''),
                    'channel_title': item.get('channel', {}).get('name', ''),
                    'channel_url': item.get('channel', {}).get('url', ''),
                    'extracted_artist_name': extracted_artist,
                    'published_at': item.get('publishDate', ''),
                    'duration_seconds': item.get('duration', 0),
                    'view_count': item.get('views', 0),
                    'like_count': item.get('likes', 0),
                    'url': item.get('url', ''),
                    'thumbnail_url': self._get_best_thumbnail(item.get('thumbnails', [])),
                    'is_live': item.get('isLive', False),
                    'data_source': 'apify_youtube'
                }
                
                processed_results.append(processed_video)
                
            except Exception as e:
                logger.warning(f"Error processing video result: {str(e)}")
                continue
        
        return processed_results
    
    def _extract_artist_name_from_title(self, title: str) -> Optional[str]:
        """
        Extract artist name from video title using various patterns
        (This uses the same logic you implemented in your YouTube agent)
        """
        import re
        
        if not title:
            return None
        
        # Common patterns for artist extraction
        patterns = [
            r'^([^-]+)\s*-\s*',  # "Artist - Song"
            r'^([^|]+)\s*\|\s*',  # "Artist | Song"
            r'\s*by\s+([^(\[]+)',  # "Song by Artist"
            r'^([^:]+):\s*',     # "Artist: Song"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                artist = match.group(1).strip()
                # Clean up common suffixes
                artist = re.sub(r'\s*\(.*?\)$', '', artist)  # Remove "(Official Video)" etc.
                artist = re.sub(r'\s*\[.*?\]$', '', artist)  # Remove "[Official]" etc.
                
                if self._is_likely_artist_name(artist):
                    return artist
        
        return None
    
    def _is_likely_artist_name(self, name: str) -> bool:
        """Check if a string is likely to be an artist name"""
        if not name or len(name) < 2 or len(name) > 50:
            return False
        
        # Filter out common non-artist terms
        non_artist_terms = {
            'official', 'music', 'video', 'channel', 'records', 'entertainment',
            'vevo', 'tv', 'radio', 'fm', 'studios', 'media', 'productions'
        }
        
        return not any(term in name.lower() for term in non_artist_terms)
    
    def _get_best_thumbnail(self, thumbnails: List[Dict[str, Any]]) -> str:
        """Get the best quality thumbnail URL"""
        if not thumbnails:
            return ""
        
        # Sort by resolution (width * height) and pick the best
        sorted_thumbs = sorted(thumbnails, 
                             key=lambda x: x.get('width', 0) * x.get('height', 0), 
                             reverse=True)
        return sorted_thumbs[0].get('url', '') if sorted_thumbs else ""
    
    def _filter_music_content(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter videos that are likely to be music content"""
        music_keywords = {
            'music', 'song', 'album', 'single', 'ep', 'track', 'audio', 'band',
            'artist', 'singer', 'remix', 'cover', 'acoustic', 'live', 'concert',
            'performance', 'official video', 'lyric', 'lyrics', 'mv'
        }
        
        filtered_videos = []
        for video in videos:
            title = video.get('title', '').lower()
            description = video.get('description', '').lower()
            channel_name = video.get('channel', {}).get('name', '').lower()
            
            # Check if any music-related keywords are present
            text_to_check = f"{title} {description} {channel_name}"
            if any(keyword in text_to_check for keyword in music_keywords):
                filtered_videos.append(video)
        
        return filtered_videos
    
    def _filter_for_undiscovered_artists(self, videos: List[Dict[str, Any]], max_view_count: int = 50000) -> List[Dict[str, Any]]:
        """
        Filter videos to find undiscovered artists based on view count and other criteria
        
        Args:
            videos: List of video data dictionaries
            max_view_count: Maximum view count for considering a video as "undiscovered"
            
        Returns:
            Filtered list of videos from undiscovered artists
        """
        undiscovered_videos = []
        
        logger.info(f"🔍 Filtering {len(videos)} videos for undiscovered artists (max views: {max_view_count:,})")
        
        for video in videos:
            try:
                view_count = video.get('view_count', 0)
                title = video.get('title', '').lower()
                channel_title = video.get('channel_title', '').lower()
                
                # Primary filter: View count under threshold
                if view_count >= max_view_count:
                    logger.debug(f"❌ Filtered out (too many views): {title[:50]}... ({view_count:,} views)")
                    continue
                
                # Prefer "official" in title but don't require it (many new artists don't use "official")
                has_official = 'official' in title
                
                # Filter out major labels and established channels
                established_indicators = [
                    'vevo', 'records', 'entertainment', 'music group', 
                    'universal', 'sony', 'warner', 'atlantic', 'capitol',
                    'rca', 'def jam', 'interscope', 'republic', 'columbia',
                    'emi', 'bmg', 'island', 'virgin', 'roadrunner'
                ]
                
                # Skip if channel name suggests major label
                if any(indicator in channel_title for indicator in established_indicators):
                    logger.debug(f"❌ Filtered out (major label): {title[:50]}... (channel: {channel_title})")
                    continue
                                
                # Detect independent indicators
                independent_indicators = not any(indicator in channel_title for indicator in established_indicators)
                
                # Calculate undiscovered artist score
                undiscovered_score = self._calculate_undiscovered_score(video, independent_indicators)
                video['undiscovered_score'] = undiscovered_score
                
                # Lower threshold for undiscovered talent (more inclusive)
                if undiscovered_score >= 0.2:
                    undiscovered_videos.append(video)
                    logger.debug(f"✅ Undiscovered artist found: {video.get('title')} ({view_count:,} views, score: {undiscovered_score:.2f})")
                else:
                    logger.debug(f"❌ Low score: {title[:50]}... ({view_count:,} views, score: {undiscovered_score:.2f})")
                
            except Exception as e:
                logger.warning(f"Error filtering video for undiscovered artists: {e}")
                continue
        
        # Sort by undiscovered score (highest first)
        undiscovered_videos.sort(key=lambda x: x.get('undiscovered_score', 0), reverse=True)
        
        return undiscovered_videos
    
    async def enrich_undiscovered_artists_with_social_media(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich undiscovered artist videos with social media URLs for validation and data enhancement
        
        Args:
            videos: List of undiscovered artist video data
            
        Returns:
            List of videos enriched with social media data
        """
        enriched_videos = []
        
        for video in videos:
            try:
                extracted_artist = video.get('extracted_artist_name')
                channel_title = video.get('channel_title', '')
                description = video.get('description', '')
                
                if extracted_artist:
                    logger.info(f"🔍 Enriching {extracted_artist} with social media data...")
                    
                    # Discover social media URLs from description and artist name
                    social_media = await self.discover_social_media_urls(
                        artist_name=extracted_artist,
                        channel_title=channel_title,
                        description=description
                    )
                    
                    # Add social media data to video
                    if social_media and social_media['validation_score'] > 0:
                        video['social_media'] = social_media
                        video['artist_validation_score'] = social_media['validation_score']
                        
                        # Boost undiscovered score if we found social media (indicates real artist)
                        if 'undiscovered_score' in video:
                            video['undiscovered_score'] = min(1.0, video['undiscovered_score'] + social_media['validation_score'] * 0.2)
                        
                        logger.info(f"✅ Enhanced {extracted_artist} with social media (validation score: {social_media['validation_score']:.1f})")
                    else:
                        logger.debug(f"❌ No social media found for {extracted_artist}")
                
                enriched_videos.append(video)
                
            except Exception as e:
                logger.warning(f"Error enriching video with social media: {str(e)}")
                enriched_videos.append(video)  # Include video even if enrichment fails
                continue
        
        return enriched_videos
    
    def _calculate_undiscovered_score(self, video: Dict[str, Any], has_independent_indicators: bool) -> float:
        """
        Calculate a score for how likely this video is from an undiscovered artist
        
        Args:
            video: Video data dictionary
            has_independent_indicators: Whether the video has independent artist indicators
            
        Returns:
            Score between 0 and 1 (higher = more likely undiscovered)
        """
        score = 0.0
        
        try:
            view_count = video.get('view_count', 0)
            title = video.get('title', '').lower()
            channel_title = video.get('channel_title', '').lower()
            
            # Base score from view count (lower views = higher score)
            if view_count < 1000:
                score += 0.4  # Very few views
            elif view_count < 5000:
                score += 0.3
            elif view_count < 15000:
                score += 0.2
            elif view_count < 30000:
                score += 0.1
            
            # Bonus for independent indicators
            if has_independent_indicators:
                score += 0.3
            
            # Quality indicators (music video terms)
            music_quality_terms = ['official music video', 'official video', 'music video', 'official']
            if any(term in title for term in music_quality_terms):
                score += 0.2
            
            # Bonus for having "official" in title (indicates serious artist)
            if 'official' in title:
                score += 0.1
            
            # Recent upload bonus (if we can detect it's very recent)
            published_at = video.get('published_at', '')
            if 'hour' in published_at or 'minute' in published_at:
                score += 0.1  # Very recent upload
            
            # Small channel bonus (likely new/undiscovered)
            # We can estimate channel size from video performance
            if view_count < 2000:
                score += 0.1  # Likely small channel
            
            # Penalty for suspicious/spam indicators
            spam_indicators = ['click', 'viral', 'trending', 'reaction', 'cover', 'remix']
            if any(term in title for term in spam_indicators):
                score -= 0.2
            
        except Exception as e:
            logger.warning(f"Error calculating undiscovered score: {e}")
            return 0.0
        
        return min(max(score, 0.0), 1.0)  # Clamp between 0 and 1
    
    def get_cost_estimate(self, expected_videos: int) -> float:
        """
        Calculate estimated cost for scraping
        
        Args:
            expected_videos: Number of videos expected to process
        
        Returns:
            Estimated cost in USD
        """
        # Apify actor pricing: approximately $0.50 per 1,000 videos
        cost_per_1000 = 0.50
        return (expected_videos / 1000) * cost_per_1000
    
    async def _discover_with_smaller_batches(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Fallback method using smaller batch searches to avoid timeouts"""
        logger.info(f"🔄 Using smaller batch discovery for query: '{query}'")
        
        all_videos = []
        batch_size = 20  # Smaller batches are less likely to timeout
        batches_needed = (max_results + batch_size - 1) // batch_size  # Round up division
        
        for batch_num in range(min(batches_needed, 3)):  # Max 3 batches to prevent long waits
            try:
                logger.info(f"📦 Processing batch {batch_num + 1}/{min(batches_needed, 3)}")
                
                # Add variation to search to get different results
                search_keywords = [f"{query}"]
                if batch_num == 1:
                    search_keywords = [f"{query} new"]
                elif batch_num == 2:
                    search_keywords = [f"{query} 2024"]
                
                batch_videos = await self.search_music_content(
                    keywords=search_keywords,
                    max_results=batch_size,
                    upload_date="t",
                    sort_by="relevance"
                )
                
                if batch_videos:
                    all_videos.extend(batch_videos)
                    logger.info(f"✅ Batch {batch_num + 1} returned {len(batch_videos)} videos")
                else:
                    logger.warning(f"⚠️ Batch {batch_num + 1} returned no results")
                
                # Small delay between batches
                if batch_num < min(batches_needed, 3) - 1:
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.warning(f"⚠️ Batch {batch_num + 1} failed: {str(e)}")
                continue
        
        # Remove duplicates based on video_id
        unique_videos = {}
        for video in all_videos:
            video_id = video.get('video_id')
            if video_id and video_id not in unique_videos:
                unique_videos[video_id] = video
        
        final_videos = list(unique_videos.values())[:max_results]
        logger.info(f"🎯 Batch discovery completed: {len(final_videos)} unique videos")
        
        return final_videos
    
    async def discover_undiscovered_artists(self, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Discover undiscovered artists by searching for 'official music video' 
        with filters for recent uploads and low view counts (<50k)
        
        Args:
            max_results: Maximum number of videos to analyze
            
        Returns:
            List of filtered video data for undiscovered artists
        """
        if not self.apify_api_token:
            logger.error("❌ Cannot discover undiscovered artists - APIFY_API_TOKEN not configured")
            return []
        
        try:
            # Search terms optimized for discovering new talent
            discovery_keywords = ["official music video"]
            
            logger.info(f"🔍 Discovering undiscovered artists with recent uploads (<50k views)")
            
            # Use the working search_music_content method with recent upload filter
            all_videos = await self.search_music_content(
                keywords=discovery_keywords,
                max_results=max_results * 2,  # Get more to filter down
                upload_date="t",  # Recent uploads (today)
                duration="all",
                sort_by="date"  # Sort by newest first
            )
            
            if not all_videos:
                logger.warning("⚠️ No videos returned from undiscovered artists search")
                return []
            
            logger.info(f"📊 Retrieved {len(all_videos)} videos, now filtering for undiscovered artists...")
            
            # Filter for undiscovered artists
            filtered_results = self._filter_for_undiscovered_artists(all_videos, max_view_count=50000)
            
            if filtered_results:
                logger.info(f"📊 Found {len(filtered_results)} potential undiscovered artists, enriching with social media data...")
                
                # Enrich with social media URLs for validation and data enhancement
                enriched_results = await self.enrich_undiscovered_artists_with_social_media(filtered_results)
                
                # Re-sort by updated scores after social media enrichment
                enriched_results.sort(key=lambda x: x.get('undiscovered_score', 0), reverse=True)
                
                logger.info(f"✅ Found {len(enriched_results)} undiscovered artists from {len(all_videos)} total videos")
                return enriched_results[:max_results]  # Return up to max_results
            else:
                logger.info(f"✅ Found 0 undiscovered artists from {len(all_videos)} total videos")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error discovering undiscovered artists: {str(e)}")
            return []
    
    async def discover_social_media_urls(self, artist_name: str, channel_title: str = None, description: str = "") -> Dict[str, str]:
        """
        Discover Instagram and TikTok URLs for an artist by searching video descriptions and generating likely URLs
        
        Args:
            artist_name: Name of the artist to search for
            channel_title: Optional YouTube channel title for additional context
            description: Video description to search for social media URLs
            
        Returns:
            Dict with discovered social media URLs: {"instagram": "", "tiktok": "", "validation_score": 0.0}
        """
        social_urls = {
            "instagram": "",
            "tiktok": "",
            "validation_score": 0.0
        }
        
        try:
            logger.info(f"🔍 Searching social media for artist: {artist_name}")
            
            # First priority: Search description for actual social media URLs
            instagram_url, tiktok_url = self._extract_social_urls_from_description(description)
            
            if instagram_url:
                social_urls["instagram"] = instagram_url
                social_urls["validation_score"] += 0.6  # Higher score for found URLs
                logger.debug(f"✅ Found Instagram in description: {instagram_url}")
            
            if tiktok_url:
                social_urls["tiktok"] = tiktok_url
                social_urls["validation_score"] += 0.6  # Higher score for found URLs
                logger.debug(f"✅ Found TikTok in description: {tiktok_url}")
            
            # If not found in description, try generating likely URLs
            if not instagram_url or not tiktok_url:
                search_name = self._clean_artist_name_for_search(artist_name)
                if search_name:
                    if not instagram_url:
                        generated_instagram = await self._generate_likely_instagram_url(search_name)
                        if generated_instagram:
                            social_urls["instagram"] = generated_instagram
                            social_urls["validation_score"] += 0.3  # Lower score for generated URLs
                            logger.debug(f"🔗 Generated likely Instagram: {generated_instagram}")
                    
                    if not tiktok_url:
                        generated_tiktok = await self._generate_likely_tiktok_url(search_name)
                        if generated_tiktok:
                            social_urls["tiktok"] = generated_tiktok
                            social_urls["validation_score"] += 0.3  # Lower score for generated URLs
                            logger.debug(f"🔗 Generated likely TikTok: {generated_tiktok}")
            
            # Additional validation if channel title is provided
            if channel_title and (social_urls["instagram"] or social_urls["tiktok"]):
                if self._validate_social_profiles_match_artist(artist_name, channel_title, social_urls):
                    social_urls["validation_score"] += 0.1
            
            logger.info(f"🎯 Social media discovery for {artist_name}: Instagram: {'✅' if social_urls['instagram'] else '❌'}, TikTok: {'✅' if social_urls['tiktok'] else '❌'}, Score: {social_urls['validation_score']:.1f}")
            
        except Exception as e:
            logger.warning(f"⚠️ Error discovering social media for {artist_name}: {str(e)}")
        
        return social_urls
    
    def _clean_artist_name_for_search(self, artist_name: str) -> str:
        """Clean artist name for social media searching"""
        if not artist_name:
            return ""
        
        # Remove common suffixes and prefixes
        clean_name = artist_name.lower().strip()
        
        # Remove common music-related words
        remove_words = [
            'official', 'music', 'video', 'vevo', 'records', 'entertainment',
            'the', 'band', 'artist', 'singer', 'rapper', 'musician'
        ]
        
        words = clean_name.split()
        filtered_words = [word for word in words if word not in remove_words]
        
        # If we removed too much, keep original
        if len(filtered_words) == 0:
            return artist_name.strip()
        
        return ' '.join(filtered_words)
    
    def _extract_social_urls_from_description(self, description: str) -> tuple[str, str]:
        """
        Extract Instagram and TikTok URLs from video description
        
        Args:
            description: Video description text
            
        Returns:
            Tuple of (instagram_url, tiktok_url) - empty strings if not found
        """
        import re
        
        instagram_url = ""
        tiktok_url = ""
        
        if not description:
            return instagram_url, tiktok_url
        
        try:
            # Instagram URL patterns
            instagram_patterns = [
                r'https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?',
                r'instagram\.com/([a-zA-Z0-9_.]+)/?',
                r'@([a-zA-Z0-9_.]+)\s*(?:on\s+)?instagram',
                r'ig:\s*@?([a-zA-Z0-9_.]+)',
                r'follow\s+(?:me\s+on\s+)?instagram:\s*@?([a-zA-Z0-9_.]+)'
            ]
            
            # TikTok URL patterns  
            tiktok_patterns = [
                r'https?://(?:www\.)?tiktok\.com/@([a-zA-Z0-9_.]+)/?',
                r'tiktok\.com/@([a-zA-Z0-9_.]+)/?',
                r'@([a-zA-Z0-9_.]+)\s*(?:on\s+)?tiktok',
                r'tt:\s*@?([a-zA-Z0-9_.]+)',
                r'follow\s+(?:me\s+on\s+)?tiktok:\s*@?([a-zA-Z0-9_.]+)'
            ]
            
            # Search for Instagram URLs
            for pattern in instagram_patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    username = match.group(1)
                    instagram_url = f"https://instagram.com/{username}"
                    break
            
            # Search for TikTok URLs
            for pattern in tiktok_patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    username = match.group(1)
                    tiktok_url = f"https://tiktok.com/@{username}"
                    break
                    
        except Exception as e:
            logger.debug(f"Error extracting social URLs from description: {e}")
        
        return instagram_url, tiktok_url
    
    async def _generate_likely_instagram_url(self, search_name: str) -> str:
        """
        Generate likely Instagram profile URL using artist name patterns
        """
        try:
            # Generate username candidates from artist name
            username_candidates = [
                search_name.replace(' ', ''),
                search_name.replace(' ', '_'),
                search_name.replace(' ', '.'),
                search_name.replace(' ', '').lower()
            ]
            
            for username in username_candidates:
                # Skip invalid usernames
                if not username or len(username) < 2 or len(username) > 30:
                    continue
                
                # Remove special characters except dots and underscores
                clean_username = ''.join(c for c in username if c.isalnum() or c in '._')
                if clean_username != username:
                    continue
                    
                # Generate likely Instagram URL
                instagram_url = f"https://instagram.com/{clean_username}"
                
                # Return the first plausible URL
                if len(clean_username) >= 3:  # Instagram minimum username length
                    return instagram_url
                        
        except Exception as e:
            logger.debug(f"Error searching Instagram: {e}")
        
        return ""
    
    async def _generate_likely_tiktok_url(self, search_name: str) -> str:
        """
        Generate likely TikTok profile URL using artist name patterns
        """
        try:
            # Generate username candidates from artist name
            username_candidates = [
                search_name.replace(' ', ''),
                search_name.replace(' ', '_'),
                search_name.replace(' ', '.'),
                search_name.replace(' ', '').lower()
            ]
            
            for username in username_candidates:
                # Skip invalid usernames
                if not username or len(username) < 2 or len(username) > 24:  # TikTok username limits
                    continue
                
                # Remove special characters except dots and underscores
                clean_username = ''.join(c for c in username if c.isalnum() or c in '._')
                if clean_username != username:
                    continue
                    
                # Generate likely TikTok URL
                tiktok_url = f"https://tiktok.com/@{clean_username}"
                
                # Return the first plausible URL
                if len(clean_username) >= 2:  # TikTok minimum username length
                    return tiktok_url
                        
        except Exception as e:
            logger.debug(f"Error searching TikTok: {e}")
        
        return ""
    
    def _validate_social_profiles_match_artist(self, artist_name: str, channel_title: str, social_urls: Dict[str, str]) -> bool:
        """
        Validate that discovered social media profiles likely belong to the artist
        """
        try:
            # Basic validation - check if artist name components appear in URLs
            name_components = artist_name.lower().replace(' ', '').replace('_', '').replace('.', '')
            channel_components = channel_title.lower().replace(' ', '').replace('_', '').replace('.', '')
            
            matches = 0
            
            for url in [social_urls.get("instagram", ""), social_urls.get("tiktok", "")]:
                if url:
                    url_lower = url.lower()
                    # Check if main artist name components appear in URL
                    if name_components in url_lower or channel_components in url_lower:
                        matches += 1
                    # Check for partial matches of longer names
                    elif len(name_components) > 5:
                        for i in range(len(name_components) - 3):
                            substring = name_components[i:i+4]
                            if substring in url_lower:
                                matches += 0.5
                                break
            
            return matches >= 1  # At least one profile should match
            
        except Exception as e:
            logger.debug(f"Error validating social profiles: {e}")
            return False
    
    async def search_by_handles(self, handles: List[str], max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search for content by YouTube handles (e.g., @MrBeast)
        Following the official apidojo example format
        
        Args:
            handles: List of YouTube handles (e.g., ["@MrBeast", "@gordonramsay"])
            max_results: Maximum number of videos to return
            
        Returns:
            List of video data dictionaries
        """
        if not self.apify_api_token:
            logger.error("❌ Cannot search by handles - APIFY_API_TOKEN not configured")
            return []
        
        try:
            # Use official example format
            actor_input = {
                "youtubeHandles": handles,
                "maxItems": max_results,
                "uploadDate": "t",
                "duration": "all",
                "features": "all",
                "sort": "r",
                "gl": "us",
                "hl": "en"
            }
            
            logger.info(f"🔍 Searching by YouTube handles: {handles}")
            
            # Start the actor run
            run_response = await self._start_actor_run(actor_input)
            if not run_response:
                logger.error("❌ Failed to start actor run for handles search")
                return []
            
            run_id = run_response['data']['id']
            logger.info(f"✅ Started Apify actor run: {run_id}")
            
            # Wait for completion and get results
            results = await self._wait_for_completion_and_get_results(run_id, max_wait_time=self.actor_timeout)
            
            if results:
                processed_results = self._process_video_results(results)
                logger.info(f"✅ Successfully scraped {len(processed_results)} videos from handles: {handles}")
                return processed_results
            else:
                logger.warning("⚠️ No results returned from handles search")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error searching by handles: {str(e)}")
            return [] 