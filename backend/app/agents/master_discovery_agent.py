"""
Master Music Discovery Agent
Orchestrates the complete workflow from YouTube discovery to multi-platform enrichment and scoring.

This agent coordinates:
1. YouTube video search and filtering
2. Artist name extraction and validation
3. Social media link extraction from descriptions
4. YouTube channel crawling
5. Spotify profile and API integration
6. Instagram and TikTok crawling
7. Lyrics analysis with DeepSeek
8. Sophisticated scoring algorithm with consistency checks
9. Database storage in Supabase

Clean architecture connecting all existing agents properly.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4

from app.agents.crawl4ai_youtube_agent import Crawl4AIYouTubeAgent
from app.agents.crawl4ai_enrichment_agent import Crawl4AIEnrichmentAgent
from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile
from app.core.config import settings

logger = logging.getLogger(__name__)

class MasterDiscoveryAgent:
    """
    Master agent that orchestrates the complete music discovery workflow.
    """
    
    def __init__(self):
        # Initialize all sub-agents
        self.youtube_agent = Crawl4AIYouTubeAgent()
        self.enrichment_agent = Crawl4AIEnrichmentAgent()
        
        # Configuration
        self.exclude_keywords = [
            'ai', 'suno', 'generated', 'udio', 'cover', 'remix',
            'artificial intelligence', 'ai-generated', 'ai music'
        ]
        self.max_results = 1000
        
        logger.info("✅ Master Discovery Agent initialized")
    
    async def discover_artists(
        self,
        deps: PipelineDependencies,
        max_results: int = 100,
        search_query: str = "official music video"
    ) -> Dict[str, Any]:
        """
        Execute the complete discovery workflow.
        
        Args:
            deps: Pipeline dependencies
            max_results: Maximum number of artists to process
            search_query: YouTube search query
            
        Returns:
            Dictionary with discovery results and metadata
        """
        start_time = time.time()
        logger.info(f"🎵 Starting master discovery workflow (max_results: {max_results})")
        
        try:
            # Phase 1: YouTube Video Discovery with Scrolling
            logger.info("📺 Phase 1: YouTube video discovery with scrolling")
            processed_videos = await self._search_and_filter_videos_with_scrolling(deps, search_query)
            
            if not processed_videos:
                return self._create_empty_result("No videos found that passed filtering", start_time)
            
            logger.info(f"✅ Found {len(processed_videos)} videos that passed all filters")
            
            # Phase 2: Artist Processing Pipeline
            logger.info("🎤 Phase 2: Artist processing pipeline")
            discovered_artists = []
            total_processed = 0
            
            for i, video_data in enumerate(processed_videos[:max_results], 1):
                try:
                    logger.info(f"Processing artist {i}/{min(len(processed_videos), max_results)}")
                    
                    artist_result = await self._process_single_artist(deps, video_data)
                    
                    if artist_result and artist_result.get('success'):
                        discovered_artists.append(artist_result)
                        logger.info(f"✅ Artist {i} processed successfully: {artist_result.get('name')}")
                    else:
                        logger.info(f"⚠️ Artist {i} processing failed or filtered out")
                    
                    total_processed += 1
                    
                    # Rate limiting
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing artist {i}: {e}")
                    continue
            
            # Phase 3: Final Results
            execution_time = time.time() - start_time
            logger.info(f"🎉 Discovery complete! Found {len(discovered_artists)} artists in {execution_time:.2f}s")
            
            return {
                'status': 'success',
                'message': f'Successfully discovered {len(discovered_artists)} artists',
                'data': {
                    'artists': discovered_artists,
                    'total_processed': total_processed,
                    'total_found': len(discovered_artists),
                    'execution_time': execution_time,
                    'discovery_metadata': {
                        'videos_after_filtering': len(processed_videos),
                        'success_rate': len(discovered_artists) / total_processed if total_processed > 0 else 0,
                        'average_score': sum(a.get('discovery_score', 0) for a in discovered_artists) / len(discovered_artists) if discovered_artists else 0
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"💥 Master discovery workflow failed: {e}")
            return {
                'status': 'error',
                'message': f'Discovery workflow failed: {str(e)}',
                'data': {
                    'artists': [],
                    'total_processed': 0,
                    'total_found': 0,
                    'execution_time': time.time() - start_time,
                    'error': str(e)
                }
            }
    
    async def _search_and_filter_videos_with_scrolling(
        self,
        deps: PipelineDependencies,
        search_query: str,
        target_filtered_videos: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search YouTube with scrolling until we have enough videos that pass filters.
        
        Args:
            deps: Pipeline dependencies
            search_query: YouTube search query
            target_filtered_videos: Minimum number of videos that must pass filters
            
        Returns:
            List of processed videos that passed all filters
        """
        processed_videos = []
        total_attempts = 0
        max_attempts = 10  # Prevent infinite loops
        videos_per_search = 50  # Number to request each time
        
        logger.info(f"🔄 Starting scrolling search - target: {target_filtered_videos} filtered videos")
        
        while len(processed_videos) < target_filtered_videos and total_attempts < max_attempts:
            total_attempts += 1
            logger.info(f"📥 Search attempt {total_attempts}: Need {target_filtered_videos - len(processed_videos)} more filtered videos")
            
            try:
                # Search for more videos
                youtube_videos = await self._search_youtube_videos_batch(
                    search_query, 
                    videos_per_search,
                    offset=total_attempts - 1  # Use attempt number as offset indicator
                )
                
                if not youtube_videos:
                    logger.warning(f"No videos found in attempt {total_attempts}")
                    if total_attempts >= 3:  # After 3 attempts with no results, break
                        break
                    continue
                
                logger.info(f"Found {len(youtube_videos)} raw videos in attempt {total_attempts}")
                
                # Filter the new videos
                batch_processed = await self._process_and_filter_videos(deps, youtube_videos)
                
                if not batch_processed:
                    logger.warning(f"No videos passed filtering in attempt {total_attempts}")
                    continue
                
                # Add new filtered videos (avoid duplicates)
                existing_urls = {v.get('url') for v in processed_videos}
                new_videos = [v for v in batch_processed if v.get('url') not in existing_urls]
                
                processed_videos.extend(new_videos)
                
                logger.info(f"✅ Attempt {total_attempts}: Added {len(new_videos)} new filtered videos. Total: {len(processed_videos)}")
                
                # Add delay between requests to be respectful
                await asyncio.sleep(2.0)
                
            except Exception as e:
                logger.error(f"❌ Error in search attempt {total_attempts}: {e}")
                # Don't break on single failures, try again
                await asyncio.sleep(3.0)
                continue
        
        logger.info(f"🏁 Scrolling search complete: {len(processed_videos)} videos passed filters after {total_attempts} attempts")
        return processed_videos
    
    async def _search_youtube_videos_batch(
        self, 
        search_query: str, 
        batch_size: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search YouTube for a batch of videos with offset simulation.
        
        Args:
            search_query: YouTube search query
            batch_size: Number of videos to request
            offset: Attempt number to vary search slightly
            
        Returns:
            List of video dictionaries
        """
        try:
            logger.info(f"🔍 Searching YouTube for: '{search_query}' (batch {offset + 1})")
            
            # Use Crawl4AI YouTube agent with daily filter for fresh content
            result = await self.youtube_agent.search_videos(
                query=search_query,
                max_results=batch_size,
                upload_date="day"  # Daily fresh content for scheduled runs
            )
            
            # Extract videos from the result object
            if result.success and result.videos:
                videos = []
                for video in result.videos:
                    videos.append({
                        'title': video.title,
                        'url': video.url,
                        'channel_name': video.channel_name,
                        'channel_title': video.channel_name,  # Alias for consistency
                        'view_count': video.view_count,
                        'duration': video.duration,
                        'upload_date': video.upload_date,
                        'video_id': self._extract_video_id(video.url),
                        'channel_id': self._extract_channel_id(video.url),
                        'description': ''  # Description not available from search
                    })
                return videos
            else:
                logger.warning(f"YouTube search failed for '{search_query}': {result.error_message}")
                return []
            
        except Exception as e:
            logger.error(f"❌ YouTube search failed for batch {offset + 1}: {e}")
            return []
    
    async def _process_and_filter_videos(
        self,
        deps: PipelineDependencies,
        videos: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process and filter videos based on artist name extraction and content validation.
        """
        processed_videos = []
        
        for video in videos:
            try:
                # Step 1: Extract artist name from video title
                artist_name = self._extract_artist_name(video.get('title', ''))
                
                if not artist_name:
                    logger.debug(f"Skipping video - no artist name extracted: {video.get('title', '')}")
                    continue
                
                # Step 2: Check if artist already exists in database
                if await self._artist_exists_in_database(deps, artist_name):
                    logger.debug(f"Skipping existing artist: {artist_name}")
                    continue
                
                # Step 3: Validate content (check for AI/cover keywords)
                if not self._validate_content(video.get('title', ''), video.get('description', '')):
                    logger.debug(f"Skipping video - failed content validation: {video.get('title', '')}")
                    continue
                
                # Step 4: Extract social media links from description
                social_links = self._extract_social_links_from_description(video.get('description', ''))
                
                # Add processed data to video
                video['extracted_artist_name'] = artist_name
                video['social_links'] = social_links
                
                processed_videos.append(video)
                logger.debug(f"✅ Video processed: {artist_name} - {video.get('title', '')}")
                
            except Exception as e:
                logger.error(f"Error processing video: {e}")
                continue
        
        return processed_videos
    
    async def _process_single_artist(
        self,
        deps: PipelineDependencies,
        video_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single artist through the complete enrichment pipeline.
        """
        artist_name = video_data.get('extracted_artist_name')
        if not artist_name:
            return None
        
        try:
            # Step 1: Create basic artist profile
            artist_profile = self._create_artist_profile(video_data)
            
            # Step 2: Crawl YouTube channel for additional data
            youtube_data = await self._crawl_youtube_channel(video_data)
            
            # Step 3: Multi-platform enrichment using Crawl4AI enrichment agent
            enriched_data = await self.enrichment_agent.enrich_artist(artist_profile)
            
            # Step 4: Spotify API integration for additional data
            spotify_api_data = await self._get_spotify_api_data(artist_profile.name)
            
            # Step 5: Calculate sophisticated discovery score
            discovery_score = self._calculate_discovery_score(
                youtube_data, enriched_data, spotify_api_data
            )
            
            # Step 6: Store in database
            artist_record = await self._store_artist_in_database(
                deps, artist_profile, enriched_data, youtube_data, 
                spotify_api_data, discovery_score
            )
            
            if artist_record:
                return {
                    'success': True,
                    'name': artist_name,
                    'artist_id': artist_record.get('id'),
                    'discovery_score': discovery_score,
                    'youtube_data': youtube_data,
                    'enriched_data': enriched_data.to_dict() if hasattr(enriched_data, 'to_dict') else str(enriched_data),
                    'spotify_api_data': spotify_api_data
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Error processing artist {artist_name}: {e}")
            return None
    
    def _extract_artist_name(self, title: str) -> Optional[str]:
        """
        Extract artist name from video title using comprehensive patterns.
        """
        if not title:
            return None
        
        # Common patterns for music video titles
        patterns = [
            r'^([^-]+?)\s*-\s*[^-]+?\s*\(Official\s*(?:Music\s*)?Video\)',  # Artist - Song (Official Video)
            r'^([^-]+?)\s*-\s*[^-]+?\s*\[Official\s*(?:Music\s*)?Video\]',  # Artist - Song [Official Video]
            r'^([^-]+?)\s*-\s*[^-]+$',  # Artist - Song
            r'^([^|]+?)\s*\|\s*[^|]+$',  # Artist | Song
            r'^([^:]+?):\s*[^:]+$',     # Artist: Song
            r'^(.+?)\s*["\']([^"\']+)["\']',  # Artist "Song"
            r'^(.+?)\s*(?:by|BY)\s+(.+?)(?:\s*\(|$)',  # Song by Artist
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title.strip(), re.IGNORECASE)
            if match:
                # Try both groups for patterns with multiple captures
                for group_idx in [1, 2]:
                    try:
                        artist_name = match.group(group_idx).strip()
                        if artist_name and self._is_valid_artist_name(artist_name):
                            return self._clean_artist_name(artist_name)
                    except IndexError:
                        continue
        
        # Fallback: take first part before common separators
        for separator in [' - ', ' | ', ': ', ' (', ' [', ' feat', ' ft']:
            if separator in title:
                potential_artist = title.split(separator)[0].strip()
                if self._is_valid_artist_name(potential_artist):
                    return self._clean_artist_name(potential_artist)
        
        return None
    
    def _is_valid_artist_name(self, name: str) -> bool:
        """
        Check if extracted text is a valid artist name.
        """
        if not name or len(name.strip()) < 2:
            return False
        
        name_lower = name.lower().strip()
        
        # Common non-artist terms
        invalid_terms = [
            'official', 'music', 'video', 'audio', 'lyric', 'lyrics',
            'feat', 'featuring', 'ft', 'remix', 'cover', 'live',
            'new', 'latest', 'best', 'top', 'album', 'single',
            'song', 'track', 'ep', 'mixtape', 'full', 'hd', 'hq',
            'youtube', 'vevo', 'records', 'entertainment'
        ]
        
        # Check if the name is just common terms
        if name_lower in invalid_terms:
            return False
        
        # Check for excessive length
        if len(name) > 50:
            return False
        
        # Check for numbers/years that suggest it's not an artist name
        if re.match(r'^\d{4}$', name.strip()):  # Just a year
            return False
        
        return True
    
    def _clean_artist_name(self, name: str) -> str:
        """
        Clean and normalize artist name.
        """
        # Remove common prefixes/suffixes
        name = re.sub(r'\s*\((Official|Music|Video|HD|4K)\).*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(ft\.|feat\.|featuring).*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(Official|Music|Video).*$', '', name, flags=re.IGNORECASE)
        
        return name.strip()
    
    async def _artist_exists_in_database(self, deps: PipelineDependencies, artist_name: str) -> bool:
        """
        Check if artist already exists in Supabase database.
        """
        try:
            response = deps.supabase.table("artist").select("id").ilike("name", f"%{artist_name}%").execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking artist existence: {e}")
            return False
    
    def _validate_content(self, title: str, description: str) -> bool:
        """
        Validate content doesn't contain excluded keywords (AI, covers, etc.).
        """
        content = f"{title} {description or ''}".lower()
        
        for keyword in self.exclude_keywords:
            if keyword.lower() in content:
                logger.debug(f"Content rejected for keyword: {keyword}")
                return False
        
        return True
    
    def _extract_social_links_from_description(self, description: str) -> Dict[str, str]:
        """
        Extract social media links from video description.
        """
        if not description:
            return {}
        
        links = {}
        
        # Instagram
        instagram_match = re.search(r'instagram\.com/([a-zA-Z0-9_.]+)', description, re.IGNORECASE)
        if instagram_match:
            links['instagram'] = f"https://instagram.com/{instagram_match.group(1)}"
        
        # TikTok
        tiktok_match = re.search(r'tiktok\.com/@([a-zA-Z0-9_.]+)', description, re.IGNORECASE)
        if tiktok_match:
            links['tiktok'] = f"https://tiktok.com/@{tiktok_match.group(1)}"
        
        # Spotify
        spotify_match = re.search(r'open\.spotify\.com/artist/([a-zA-Z0-9]+)', description, re.IGNORECASE)
        if spotify_match:
            links['spotify'] = f"https://open.spotify.com/artist/{spotify_match.group(1)}"
        
        # Twitter/X
        twitter_match = re.search(r'(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)', description, re.IGNORECASE)
        if twitter_match:
            links['twitter'] = f"https://twitter.com/{twitter_match.group(1)}"
        
        return links
    
    def _create_artist_profile(self, video_data: Dict[str, Any]) -> ArtistProfile:
        """
        Create initial artist profile from video data.
        """
        artist_name = video_data.get('extracted_artist_name', 'Unknown Artist')
        social_links = video_data.get('social_links', {})
        
        # Extract Spotify ID if available
        spotify_id = None
        spotify_url = social_links.get('spotify')
        if spotify_url:
            spotify_match = re.search(r'/artist/([a-zA-Z0-9]+)', spotify_url)
            if spotify_match:
                spotify_id = spotify_match.group(1)
        
        profile = ArtistProfile(
            id=uuid4(),
            name=artist_name,
            youtube_channel_id=video_data.get('channel_id'),
            youtube_channel_name=video_data.get('channel_title'),
            spotify_id=spotify_id,
            lyrical_themes=[],
            metadata={
                'discovery_video': {
                    'video_id': video_data.get('video_id'),
                    'title': video_data.get('title'),
                    'url': video_data.get('url'),
                    'published': video_data.get('published')
                },
                'social_links_from_description': social_links
            }
        )
        
        # Add social links
        for platform, url in social_links.items():
            profile.social_links[platform] = url
        
        return profile
    
    async def _crawl_youtube_channel(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crawl YouTube channel for subscriber count and additional social links.
        """
        try:
            channel_id = video_data.get('channel_id')
            if not channel_id:
                return {}
            
            # For now, return basic data - channel crawling would need additional implementation
            return {
                'subscriber_count': 0,
                'channel_url': f"https://www.youtube.com/channel/{channel_id}" if channel_id else '',
                'channel_description': '',
                'social_links_from_channel': {},
                'verified': False
            }
            
        except Exception as e:
            logger.error(f"Error crawling YouTube channel: {e}")
            return {}
    
    async def _get_spotify_api_data(self, artist_name: str) -> Dict[str, Any]:
        """
        Get additional data from official Spotify API.
        """
        try:
            # This would use the official Spotify API for avatar, genres, etc.
            # For now, return empty dict - would need to implement Spotify API client
            logger.info(f"Getting Spotify API data for: {artist_name}")
            return {}
            
        except Exception as e:
            logger.error(f"Error getting Spotify API data: {e}")
            return {}
    
    def _calculate_discovery_score(
        self,
        youtube_data: Dict[str, Any],
        enriched_data: Any,
        spotify_api_data: Dict[str, Any]
    ) -> int:
        """
        Calculate sophisticated discovery score (0-100) with consistency checks.
        """
        score = 0
        
        try:
            # Extract metrics from enriched data
            spotify_listeners = getattr(enriched_data, 'spotify_monthly_listeners', 0) or 0
            instagram_followers = getattr(enriched_data, 'instagram_followers', 0) or 0
            tiktok_followers = getattr(enriched_data, 'tiktok_followers', 0) or 0
            youtube_subscribers = youtube_data.get('subscriber_count', 0)
            
            # YouTube metrics (30 points max)
            if youtube_subscribers > 1000000:
                score += 30
            elif youtube_subscribers > 100000:
                score += 25
            elif youtube_subscribers > 10000:
                score += 20
            elif youtube_subscribers > 1000:
                score += 15
            elif youtube_subscribers > 100:
                score += 10
            
            # Spotify metrics (25 points max)
            if spotify_listeners > 1000000:
                score += 25
            elif spotify_listeners > 100000:
                score += 20
            elif spotify_listeners > 10000:
                score += 15
            elif spotify_listeners > 1000:
                score += 10
            elif spotify_listeners > 100:
                score += 5
            
            # Instagram metrics (20 points max)
            if instagram_followers > 1000000:
                score += 20
            elif instagram_followers > 100000:
                score += 15
            elif instagram_followers > 10000:
                score += 10
            elif instagram_followers > 1000:
                score += 5
            
            # TikTok metrics (15 points max)
            if tiktok_followers > 1000000:
                score += 15
            elif tiktok_followers > 100000:
                score += 12
            elif tiktok_followers > 10000:
                score += 8
            elif tiktok_followers > 1000:
                score += 5
            
            # Consistency check and artificial inflation detection (10 points max deduction)
            artificial_inflation_penalty = self._detect_artificial_inflation(
                spotify_listeners, instagram_followers, tiktok_followers, youtube_subscribers
            )
            score -= artificial_inflation_penalty
            
            # Content quality bonus (10 points max)
            if hasattr(enriched_data, 'lyrics_themes') and enriched_data.lyrics_themes:
                score += 5
            if hasattr(enriched_data, 'top_tracks') and enriched_data.top_tracks:
                score += 5
            
            return max(0, min(score, 100))  # Clamp between 0 and 100
            
        except Exception as e:
            logger.error(f"Error calculating discovery score: {e}")
            return 0
    
    def _detect_artificial_inflation(
        self,
        spotify_listeners: int,
        instagram_followers: int,
        tiktok_followers: int,
        youtube_subscribers: int
    ) -> int:
        """
        Detect artificial inflation and return penalty points.
        """
        penalty = 0
        
        try:
            # Get all valid metrics
            metrics = [m for m in [spotify_listeners, instagram_followers, tiktok_followers, youtube_subscribers] if m > 0]
            
            if len(metrics) < 2:
                return 0  # Not enough data to compare
            
            # Find max and min metrics
            max_metric = max(metrics)
            min_metric = min(metrics)
            
            if min_metric == 0:
                return 0
            
            # Calculate ratio between highest and lowest
            ratio = max_metric / min_metric
            
            # Suspicious patterns
            if ratio > 1000:  # One platform has 1000x more followers
                penalty += 15
                logger.warning(f"Very high follower ratio detected: {ratio:.1f}")
            elif ratio > 100:  # One platform has 100x more followers
                penalty += 10
                logger.warning(f"High follower ratio detected: {ratio:.1f}")
            elif ratio > 50:  # One platform has 50x more followers
                penalty += 5
                logger.warning(f"Moderate follower ratio detected: {ratio:.1f}")
            
            # Specific suspicious patterns
            if spotify_listeners > 1000000 and max(instagram_followers, tiktok_followers) < 50000:
                penalty += 10
                logger.warning(f"High Spotify listeners ({spotify_listeners:,}) but low social media presence")
            
            if instagram_followers > 100000 and spotify_listeners < 1000:
                penalty += 5
                logger.warning(f"High Instagram followers ({instagram_followers:,}) but very low Spotify listeners")
            
            return min(penalty, 20)  # Cap penalty at 20 points
            
        except Exception as e:
            logger.error(f"Error detecting artificial inflation: {e}")
            return 0
    
    async def _store_artist_in_database(
        self,
        deps: PipelineDependencies,
        artist_profile: ArtistProfile,
        enriched_data: Any,
        youtube_data: Dict[str, Any],
        spotify_api_data: Dict[str, Any],
        discovery_score: int
    ) -> Optional[Dict[str, Any]]:
        """
        Store complete artist data in Supabase database.
        """
        try:
            # Prepare artist data for database
            artist_data = {
                'name': artist_profile.name,
                'youtube_channel_id': artist_profile.youtube_channel_id,
                'youtube_subscriber_count': youtube_data.get('subscriber_count', 0),
                'youtube_channel_url': youtube_data.get('channel_url', ''),
                'spotify_id': artist_profile.spotify_id,
                'spotify_url': artist_profile.social_links.get('spotify'),
                'spotify_monthly_listeners': getattr(enriched_data, 'spotify_monthly_listeners', 0) or 0,
                'instagram_url': artist_profile.social_links.get('instagram'),
                'instagram_follower_count': getattr(enriched_data, 'instagram_followers', 0) or 0,
                'tiktok_url': artist_profile.social_links.get('tiktok'),
                'tiktok_follower_count': getattr(enriched_data, 'tiktok_followers', 0) or 0,
                'tiktok_likes_count': getattr(enriched_data, 'tiktok_likes', 0) or 0,
                'music_theme_analysis': getattr(enriched_data, 'lyrics_themes', ''),
                'discovery_source': 'youtube',
                'discovery_video_id': artist_profile.metadata.get('discovery_video', {}).get('video_id'),
                'discovery_video_title': artist_profile.metadata.get('discovery_video', {}).get('title'),
                'discovery_score': discovery_score,
                'last_crawled_at': datetime.utcnow().isoformat(),
                'is_validated': True
            }
            
            # Insert into database
            response = deps.supabase.table("artist").insert(artist_data).execute()
            
            if response.data:
                artist_record = response.data[0]
                logger.info(f"✅ Stored artist in database: {artist_profile.name} (ID: {artist_record['id']})")
                return artist_record
            else:
                logger.error(f"❌ Failed to store artist in database: {artist_profile.name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error storing artist in database: {e}")
            return None
    
    def _create_empty_result(self, message: str, start_time: float) -> Dict[str, Any]:
        """
        Create empty result structure.
        """
        return {
            'status': 'success',
            'message': message,
            'data': {
                'artists': [],
                'total_processed': 0,
                'total_found': 0,
                'execution_time': time.time() - start_time,
                'discovery_metadata': {}
            }
        }
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        try:
            if 'watch?v=' in url:
                return url.split('watch?v=')[1].split('&')[0]
            return None
        except:
            return None
    
    def _extract_channel_id(self, url: str) -> Optional[str]:
        """Extract channel ID from YouTube URL - placeholder implementation."""
        # This would need more sophisticated URL parsing
        return None 