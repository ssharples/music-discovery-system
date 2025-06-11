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
            # Phase 1: YouTube Video Discovery with Infinite Scroll
            logger.info("📺 Phase 1: YouTube video discovery with infinite scroll")
            processed_videos = await self._search_and_filter_videos_with_infinite_scroll(deps, search_query)
            
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
    
    async def _search_and_filter_videos_with_infinite_scroll(
        self,
        deps: PipelineDependencies,
        search_query: str,
        target_filtered_videos: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Single YouTube search with infinite scrolling until we have enough videos that pass filters.
        Much more efficient than multiple separate searches.
        
        Args:
            deps: Pipeline dependencies
            search_query: YouTube search query  
            target_filtered_videos: Minimum number of videos that must pass filters
            
        Returns:
            List of processed videos that passed all filters
        """
        logger.info(f"🔄 Starting infinite scroll search - target: {target_filtered_videos} filtered videos")
        
        try:
            # Single search with infinite scrolling to get raw videos
            logger.info(f"🔍 Performing infinite scroll search for: '{search_query}'")
            
            result = await asyncio.wait_for(
                self.youtube_agent.search_videos_with_infinite_scroll(
                    query=search_query,
                    target_videos=target_filtered_videos * 3,  # Get 3x more to account for filtering
                    upload_date="day"  # Today's uploads only
                ),
                timeout=300.0  # 5 minute timeout for the entire scroll session
            )
            
            if not result.success or not result.videos:
                logger.error(f"❌ Infinite scroll search failed: {result.error_message}")
                return []
            
            logger.info(f"✅ Infinite scroll found {len(result.videos)} raw videos")
            
            # Convert videos to the expected format
            youtube_videos = []
            for video in result.videos:
                youtube_videos.append({
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
            
            logger.info(f"🔍 Processing and filtering {len(youtube_videos)} videos...")
            
            # Filter videos through our criteria
            processed_videos = []
            for video in youtube_videos:
                try:
                    video_title = video.get('title', '')
                    
                    # Step 1: Validate title contains "official music video" (case insensitive)
                    if not self._validate_title_contains_search_terms(video_title):
                        continue
                    
                    # Step 2: Extract artist name from video title
                    artist_name = self._extract_artist_name(video_title)
                    if not artist_name:
                        continue
                    
                    # Step 3: Check if this specific video has already been processed
                    if await self._video_exists_in_database(deps, video.get('url', '')):
                        continue
                    
                    # Step 4: Check if artist already exists in database
                    if await self._artist_exists_in_database(deps, artist_name):
                        continue
                    
                    # Step 5: Validate content (check for AI/cover keywords)
                    if not self._validate_content(video_title, video.get('description', '')):
                        continue
                    
                    # Step 6: Extract social media links from description
                    social_links = self._extract_social_links_from_description(video.get('description', ''))
                    
                    # Add processed data to video
                    video['extracted_artist_name'] = artist_name
                    video['social_links'] = social_links
                    
                    processed_videos.append(video)
                    logger.debug(f"✅ Video passed filters: {artist_name} - {video_title}")
                    
                    # Stop if we've reached our target
                    if len(processed_videos) >= target_filtered_videos:
                        logger.info(f"🎯 Reached target! {len(processed_videos)} videos passed all filters")
                        break
                    
                except Exception as e:
                    logger.error(f"Error processing video: {e}")
                    continue
            
            logger.info(f"🏁 Infinite scroll filtering complete: {len(processed_videos)} videos passed all filters")
            return processed_videos
            
        except asyncio.TimeoutError:
            logger.error("⏰ Infinite scroll search timed out after 5 minutes")
            return []
        except Exception as e:
            logger.error(f"❌ Infinite scroll search failed: {e}")
            return []
    
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
            # Merge any social links found from YouTube channel crawling
            if youtube_data.get('social_links_from_channel'):
                for platform, url in youtube_data['social_links_from_channel'].items():
                    if platform not in artist_profile.social_links:
                        artist_profile.social_links[platform] = url
                        logger.info(f"🔗 Added {platform} link from YouTube channel: {url}")
            
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
        Excludes featured artists and collaborations.
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
                            # Clean and remove featured artists
                            cleaned_name = self._clean_artist_name(artist_name)
                            return self._remove_featured_artists(cleaned_name)
                    except IndexError:
                        continue
        
        # Fallback: take first part before common separators
        for separator in [' - ', ' | ', ': ', ' (', ' [', ' feat', ' ft']:
            if separator in title:
                potential_artist = title.split(separator)[0].strip()
                if self._is_valid_artist_name(potential_artist):
                    cleaned_name = self._clean_artist_name(potential_artist)
                    return self._remove_featured_artists(cleaned_name)
        
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
    
    def _remove_featured_artists(self, name: str) -> str:
        """
        Remove featured artists and collaborations from artist name.
        Returns only the main artist.
        """
        if not name:
            return name
        
        # Patterns for featured artists and collaborations
        feature_patterns = [
            r'\s*(?:feat\.|featuring|ft\.)\s+.+$',  # feat. Artist, featuring Artist, ft. Artist
            r'\s*(?:with|w/)\s+.+$',               # with Artist, w/ Artist
            r'\s*(?:vs\.?|versus)\s+.+$',          # vs Artist, versus Artist
            r'\s*(?:&|\+|and)\s+[A-Z].+$',        # & Artist, + Artist, and Artist (only if next word is capitalized)
            r'\s*(?:x|X)\s+[A-Z].+$',             # x Artist, X Artist (collaborations)
            r'\s*,\s*[A-Z].+$',                    # , Artist (comma separated)
        ]
        
        cleaned_name = name
        for pattern in feature_patterns:
            cleaned_name = re.sub(pattern, '', cleaned_name, flags=re.IGNORECASE)
        
        # Clean up any trailing punctuation or whitespace
        cleaned_name = re.sub(r'[,\s]+$', '', cleaned_name).strip()
        
        # If we removed everything, return the original
        if not cleaned_name or len(cleaned_name) < 2:
            return name
        
        logger.debug(f"Cleaned artist name: '{name}' -> '{cleaned_name}'")
        return cleaned_name
    
    async def _artist_exists_in_database(self, deps: PipelineDependencies, artist_name: str) -> bool:
        """
        Check if artist already exists in Supabase database using exact and fuzzy matching.
        """
        try:
            # First try exact match
            exact_response = deps.supabase.table("artist").select("id").eq("name", artist_name).execute()
            if len(exact_response.data) > 0:
                logger.debug(f"Found exact match for artist: {artist_name}")
                return True
            
            # Then try fuzzy match with cleaned names
            cleaned_name = self._clean_artist_name(artist_name).lower()
            fuzzy_response = deps.supabase.table("artist").select("id", "name").execute()
            
            for existing_artist in fuzzy_response.data:
                existing_cleaned = self._clean_artist_name(existing_artist['name']).lower()
                if existing_cleaned == cleaned_name:
                    logger.debug(f"Found fuzzy match: {artist_name} -> {existing_artist['name']}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking artist existence: {e}")
            return False
    
    async def _video_exists_in_database(self, deps: PipelineDependencies, video_url: str) -> bool:
        """
        Check if this specific video has already been processed.
        """
        try:
            video_id = self._extract_video_id(video_url)
            if not video_id:
                return False
                
            response = deps.supabase.table("artist").select("id").eq("discovery_video_id", video_id).execute()
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"Error checking video existence: {e}")
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
            channel_name = video_data.get('channel_name') or video_data.get('channel_title')
            if not channel_name:
                logger.warning("No channel name available for crawling")
                return {}
            
            # Try multiple YouTube channel URL formats
            channel_urls = [
                f"https://www.youtube.com/@{channel_name}",  # New handle format
                f"https://www.youtube.com/c/{channel_name}",  # Custom URL
                f"https://www.youtube.com/user/{channel_name}",  # User format
            ]
            
            logger.info(f"🎬 Crawling YouTube channel: {channel_name}")
            
            # Use Crawl4AI to scrape channel data
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
            from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
            
            browser_config = BrowserConfig(
                headless=True,
                viewport_width=1920,
                viewport_height=1080
            )
            
            # Enhanced schema for YouTube channel extraction
            schema = {
                "name": "YouTube Channel",
                "fields": [
                    {
                        "name": "subscriber_count_text",
                        "selector": "[data-testid='subscriber-count'], .subscriber-count, #subscriber-count, .yt-subscription-button-subscriber-count-branded-horizontal, .style-scope.ytd-c4-tabbed-header-renderer",
                        "type": "text"
                    },
                    {
                        "name": "channel_description",
                        "selector": "[data-testid='channel-description'], .channel-description, .about-description, .yt-formatted-string",
                        "type": "text"
                    },
                    {
                        "name": "verified_badge",
                        "selector": "[data-testid='verified-badge'], .verified-badge, .yt-icon-badge",
                        "type": "text"
                    },
                    {
                        "name": "social_links",
                        "selector": "a[href*='instagram.com'], a[href*='twitter.com'], a[href*='tiktok.com'], a[href*='spotify.com'], a[href*='facebook.com']",
                        "type": "list"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_until="domcontentloaded",
                page_timeout=30000,  # 30 second timeout
                delay_before_return_html=3.0,
                scan_full_page=True,  # Use built-in scrolling
                scroll_delay=0.5,
                verbose=True
            )
            
            # Try each URL format until one works
            for channel_url in channel_urls:
                try:
                    logger.info(f"Trying channel URL: {channel_url}")
                    
                    async with AsyncWebCrawler(config=browser_config) as crawler:
                        result = await crawler.arun(
                            url=channel_url,
                            config=crawler_config
                        )
                        
                        if result.success and result.html:
                            # Process extracted data
                            channel_data = {
                                'subscriber_count': 0,
                                'channel_url': channel_url,
                                'channel_description': '',
                                'social_links_from_channel': {},
                                'verified': False
                            }
                            
                            # Parse structured extraction
                            if result.extracted_content:
                                try:
                                    import json
                                    extracted = json.loads(result.extracted_content)
                                    
                                    # Extract subscriber count
                                    if extracted.get('subscriber_count_text'):
                                        channel_data['subscriber_count'] = self._parse_subscriber_count(extracted['subscriber_count_text'])
                                    
                                    # Extract description
                                    if extracted.get('channel_description'):
                                        channel_data['channel_description'] = extracted['channel_description'][:500]
                                    
                                    # Extract social links
                                    if extracted.get('social_links'):
                                        social_links = self._extract_social_links_from_channel_links(extracted['social_links'])
                                        channel_data['social_links_from_channel'] = social_links
                                    
                                    # Check verification
                                    if extracted.get('verified_badge'):
                                        channel_data['verified'] = True
                                        
                                except (json.JSONDecodeError, Exception) as e:
                                    logger.debug(f"Error parsing extracted content: {e}")
                            
                            # Fallback: use regex patterns on HTML
                            if channel_data['subscriber_count'] == 0:
                                channel_data['subscriber_count'] = self._extract_subscriber_count_from_html(result.html)
                            
                            if not channel_data['social_links_from_channel']:
                                channel_data['social_links_from_channel'] = self._extract_social_links_from_html(result.html)
                            
                            if channel_data['subscriber_count'] > 0 or channel_data['social_links_from_channel']:
                                logger.info(f"✅ Successfully crawled YouTube channel: {channel_data['subscriber_count']:,} subscribers, {len(channel_data['social_links_from_channel'])} social links")
                                return channel_data
                            
                except Exception as e:
                    logger.debug(f"Failed to crawl {channel_url}: {e}")
                    continue
            
            logger.warning(f"⚠️ Could not crawl any YouTube channel URLs for: {channel_name}")
            return {
                'subscriber_count': 0,
                'channel_url': '',
                'channel_description': '',
                'social_links_from_channel': {},
                'verified': False
            }
            
        except Exception as e:
            logger.error(f"❌ YouTube channel crawling error: {e}")
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
            # Extract metrics from enriched data - fix the data access pattern
            spotify_listeners = enriched_data.profile.follower_counts.get('spotify_monthly_listeners', 0) or 0
            instagram_followers = enriched_data.profile.follower_counts.get('instagram', 0) or 0
            tiktok_followers = enriched_data.profile.follower_counts.get('tiktok', 0) or 0
            tiktok_likes = enriched_data.profile.metadata.get('tiktok_likes', 0) or 0
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
            if enriched_data.profile.metadata.get('lyrics_themes'):
                score += 5
            if enriched_data.profile.metadata.get('top_tracks'):
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
                # Spotify data
                'spotify_monthly_listeners': enriched_data.profile.follower_counts.get('spotify_monthly_listeners', 0) or 0,
                'spotify_top_city': enriched_data.profile.metadata.get('spotify_top_city', ''),
                'spotify_biography': enriched_data.profile.bio or '',
                'spotify_genres': enriched_data.profile.genres or [],
                # Instagram data  
                'instagram_url': enriched_data.profile.social_links.get('instagram') or artist_profile.social_links.get('instagram'),
                'instagram_follower_count': enriched_data.profile.follower_counts.get('instagram', 0) or 0,
                # TikTok data
                'tiktok_url': enriched_data.profile.social_links.get('tiktok') or artist_profile.social_links.get('tiktok'),
                'tiktok_follower_count': enriched_data.profile.follower_counts.get('tiktok', 0) or 0,
                'tiktok_likes_count': enriched_data.profile.metadata.get('tiktok_likes', 0) or 0,
                # Other social media
                'twitter_url': enriched_data.profile.social_links.get('twitter') or artist_profile.social_links.get('twitter'),
                'facebook_url': enriched_data.profile.social_links.get('facebook') or artist_profile.social_links.get('facebook'),
                'website_url': enriched_data.profile.social_links.get('website') or artist_profile.social_links.get('website'),
                # Music analysis
                'music_theme_analysis': enriched_data.profile.metadata.get('lyrics_themes', ''),
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

    def _validate_title_contains_search_terms(self, title: str) -> bool:
        """
        Validate if the title appears to be a legitimate music video (less restrictive).
        """
        if not title:
            return False
            
        title_lower = title.lower()
        
        # Primary high-quality indicators
        high_quality_terms = [
            "official music video",
            "official video", 
            "official mv",
            "official audio",
            "official lyric video",
            "official visualizer"
        ]
        
        for term in high_quality_terms:
            if term in title_lower:
                return True
        
        # Secondary indicators - look for music video structure
        import re
        music_patterns = [
            r'\w+\s*-\s*\w+',  # Artist - Song format
            r'\w+\s*\|\s*\w+',  # Artist | Song format  
            r'\w+:\s*\w+',      # Artist: Song format
        ]
        
        has_music_structure = False
        for pattern in music_patterns:
            if re.search(pattern, title_lower):
                has_music_structure = True
                break
        
        if has_music_structure:
            # More flexible secondary terms
            secondary_terms = [
                "music video",
                "mv",
                "video",
                "lyric video", 
                "lyrics",
                "visualizer",
                "performance",
                "live"
            ]
            
            for term in secondary_terms:
                if term in title_lower:
                    return True
            
            # Even if no explicit "video" term, accept if it has proper music structure
            # and doesn't contain obvious negative indicators
            negative_indicators = [
                "cover", "remix by", "reaction", "tutorial", 
                "how to", "instrumental", "karaoke", "mashup"
            ]
            
            has_negative = any(neg in title_lower for neg in negative_indicators)
            if not has_negative:
                return True
        
        return False
    
    def _parse_subscriber_count(self, text: str) -> int:
        """Parse subscriber count from text with K, M, B suffixes."""
        try:
            if not text:
                return 0
            
            # Remove common words and clean text
            text = text.lower().replace('subscribers', '').replace('subscriber', '').strip()
            
            # Handle K, M, B suffixes
            multipliers = {'k': 1000, 'm': 1000000, 'b': 1000000000}
            
            for suffix, multiplier in multipliers.items():
                if suffix in text:
                    number = float(text.replace(suffix, '').replace(',', '').strip())
                    return int(number * multiplier)
            
            # Try to parse as regular number
            clean_number = re.sub(r'[^\d.]', '', text)
            if clean_number:
                return int(float(clean_number))
            
            return 0
        except:
            return 0
    
    def _extract_subscriber_count_from_html(self, html: str) -> int:
        """Extract subscriber count using regex patterns."""
        patterns = [
            r'(\d+(?:\.\d+)?[KMB]?)\s*subscribers?',
            r'"subscriberCountText":\{"runs":\[\{"text":"([^"]+)"\}',
            r'"subscriberCount":(\d+)',
            r'subscribers?["\s]*:\s*["\s]*(\d+(?:\.\d+)?[KMB]?)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                for match in matches:
                    parsed = self._parse_subscriber_count(match)
                    if parsed > 0:
                        return parsed
        return 0
    
    def _extract_social_links_from_channel_links(self, links: List[str]) -> Dict[str, str]:
        """Extract social media links from channel description."""
        social_links = {}
        
        for link in links:
            if 'instagram.com' in link:
                social_links['instagram'] = link
            elif 'twitter.com' in link or 'x.com' in link:
                social_links['twitter'] = link
            elif 'tiktok.com' in link:
                social_links['tiktok'] = link
            elif 'spotify.com' in link:
                social_links['spotify'] = link
            elif 'facebook.com' in link:
                social_links['facebook'] = link
        
        return social_links
    
    def _extract_social_links_from_html(self, html: str) -> Dict[str, str]:
        """Extract social media links using regex patterns."""
        social_links = {}
        
        # Enhanced patterns for social media links
        link_patterns = {
            'instagram': [
                r'href="(https?://(?:www\.)?instagram\.com/[^"]+)"',
                r'"(https?://(?:www\.)?instagram\.com/[^"]+)"',
            ],
            'twitter': [
                r'href="(https?://(?:www\.)?(?:twitter|x)\.com/[^"]+)"',
                r'"(https?://(?:www\.)?(?:twitter|x)\.com/[^"]+)"',
            ],
            'tiktok': [
                r'href="(https?://(?:www\.)?tiktok\.com/[^"]+)"',
                r'"(https?://(?:www\.)?tiktok\.com/[^"]+)"',
            ],
            'spotify': [
                r'href="(https?://open\.spotify\.com/artist/[^"]+)"',
                r'"(https?://open\.spotify\.com/artist/[^"]+)"',
            ],
            'facebook': [
                r'href="(https?://(?:www\.)?facebook\.com/[^"]+)"',
                r'"(https?://(?:www\.)?facebook\.com/[^"]+)"',
            ]
        }
        
        for platform, patterns in link_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    # Take the first valid match
                    social_links[platform] = matches[0]
                    break
        
        return social_links
 