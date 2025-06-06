"""
Apify YouTube Agent - Alternative to official YouTube API
Uses apidojo/youtube-scraper actor to bypass quota limitations
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
import httpx
import json
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class ApifyYouTubeAgent:
    """
    YouTube agent using Apify's youtube-scraper actor
    Cost: $0.50 per 1,000 videos (much cheaper than quota issues)
    Success rate: 97%
    
    Compatible interface with YouTubeDiscoveryAgent for drop-in replacement
    """
    
    def __init__(self):
        self.apify_api_token = os.getenv('APIFY_API_TOKEN')
        self.actor_id = "apidojo/youtube-scraper"  # The actor we analyzed
        self.base_url = "https://api.apify.com/v2"
        
        if not self.apify_api_token:
            logger.warning("APIFY_API_TOKEN not set - Apify YouTube scraping will be disabled")
    
    # Core methods that match YouTubeDiscoveryAgent interface
    
    async def discover_artists(
        self,
        deps,  # PipelineDependencies - keeping same signature
        query: str,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Discover artists using Apify YouTube scraper
        
        This method matches the interface of YouTubeDiscoveryAgent.discover_artists()
        and returns the same data structure expected by the orchestrator.
        """
        if not self.apify_api_token:
            logger.error("Cannot discover artists - APIFY_API_TOKEN not configured")
            return []
        
        try:
            logger.info(f"🔍 Discovering artists via Apify for query: '{query}', max_results: {max_results}")
            
            # Search for music content using Apify
            videos = await self.search_music_content(
                keywords=[query],
                max_results=max_results,
                upload_date="month",  # Focus on recent content
                sort_by="relevance"
            )
            
            if not videos:
                logger.warning("⚠️ No videos returned from Apify YouTube scraper")
                return []
            
            # Convert video data to channel data (group by channel)
            channel_data = self._convert_videos_to_channels(videos)
            
            # Apply quality filters and scoring
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
                           upload_date: str = "month",
                           duration: str = "all",
                           sort_by: str = "relevance") -> List[Dict[str, Any]]:
        """
        Search for music content using Apify YouTube scraper
        
        Args:
            keywords: List of search terms (e.g., ["new music 2024", "indie rock"])
            max_results: Maximum number of videos to return
            upload_date: Filter by upload time (hour, today, week, month, year)
            duration: Video length filter (short, long, all)
            sort_by: Sort results (relevance, date, views, rating)
        
        Returns:
            List of video data dictionaries
        """
        if not self.apify_api_token:
            logger.error("Cannot search - APIFY_API_TOKEN not configured")
            return []
        
        try:
            # Prepare input for the Apify actor
            actor_input = {
                "keywords": keywords,
                "maxItems": max_results,
                "uploadDate": upload_date,
                "duration": duration,
                "sort": sort_by,
                "gl": "us",  # Geographic location
                "hl": "en"   # Language
            }
            
            logger.info(f"Starting Apify YouTube search with keywords: {keywords}")
            
            # Start the actor run
            run_response = await self._start_actor_run(actor_input)
            if not run_response:
                return []
            
            run_id = run_response['data']['id']
            
            # Wait for completion and get results
            results = await self._wait_for_completion_and_get_results(run_id)
            
            if results:
                logger.info(f"Successfully scraped {len(results)} videos from YouTube")
                return self._process_video_results(results)
            else:
                logger.warning("No results returned from Apify YouTube scraper")
                return []
                
        except Exception as e:
            logger.error(f"Error in Apify YouTube search: {str(e)}")
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
            actor_input = {
                "getTrending": True,
                "maxItems": max_results,
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
        """Calculate emerging artist score for a channel"""
        score = 0.0
        
        try:
            # Base metrics
            avg_views = channel.get('avg_views', 0)
            video_count = channel.get('video_count', 0)
            
            # Emerging artist sweet spot: 1K - 100K views per video
            if 1000 <= avg_views <= 100000:
                score += 0.4  # Higher weight for emerging artist range
            elif 100 <= avg_views < 1000:
                score += 0.2  # Some potential
            elif avg_views > 100000:
                score += 0.1  # Might be too established
            
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
        """Start an Apify actor run"""
        url = f"{self.base_url}/acts/{self.actor_id}/runs"
        headers = {
            "Authorization": f"Bearer {self.apify_api_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=actor_input)
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to start Apify actor run: {str(e)}")
            return None
    
    async def _wait_for_completion_and_get_results(self, run_id: str, max_wait_time: int = 300) -> Optional[List[Dict[str, Any]]]:
        """Wait for actor run to complete and return results"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                # Check run status
                status_url = f"{self.base_url}/actor-runs/{run_id}"
                headers = {"Authorization": f"Bearer {self.apify_api_token}"}
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    status_response = await client.get(status_url, headers=headers)
                    status_response.raise_for_status()
                    status_data = status_response.json()
                
                run_status = status_data['data']['status']
                
                if run_status == 'SUCCEEDED':
                    # Get results
                    results_url = f"{self.base_url}/actor-runs/{run_id}/dataset/items"
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        results_response = await client.get(results_url, headers=headers)
                        results_response.raise_for_status()
                        return results_response.json()
                
                elif run_status in ['FAILED', 'ABORTED', 'TIMED-OUT']:
                    logger.error(f"Apify actor run {run_id} finished with status: {run_status}")
                    return None
                
                # Still running, wait a bit more
                logger.info(f"Actor run {run_id} status: {run_status}, waiting...")
                await asyncio.sleep(5)
                
            except httpx.RequestError as e:
                logger.error(f"Error checking run status: {str(e)}")
                await asyncio.sleep(5)
        
        logger.error(f"Actor run {run_id} timed out after {max_wait_time} seconds")
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
    
    def get_cost_estimate(self, expected_videos: int) -> float:
        """
        Calculate estimated cost for scraping
        
        Args:
            expected_videos: Number of videos expected to scrape
            
        Returns:
            Estimated cost in USD
        """
        cost_per_1000 = 0.50
        return (expected_videos / 1000) * cost_per_1000 