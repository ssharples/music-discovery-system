"""
Crawl4AI YouTube Agent - Replaces Apify YouTube scraping
Uses Crawl4AI's browser automation to scrape YouTube search results
"""
import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import urllib.parse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

logger = logging.getLogger(__name__)


class Crawl4AIYouTubeAgent:
    """YouTube scraping agent using Crawl4AI instead of Apify"""
    
    def __init__(self):
        """Initialize the Crawl4AI YouTube agent"""
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080,
            extra_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        logger.info("✅ Crawl4AI YouTube Agent initialized")
    
    async def search_youtube(
        self,
        query: str,
        max_results: int = 100,
        upload_date: str = "week",  # today, week, month, year
        duration: str = "all",  # short (<4min), long (>20min), all
        sort_by: str = "relevance"  # relevance, date, views, rating
    ) -> List[Dict[str, Any]]:
        """
        Search YouTube and scrape results using Crawl4AI
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            upload_date: Filter by upload date
            duration: Filter by video duration
            sort_by: Sort results by
            
        Returns:
            List of video data dictionaries
        """
        logger.info(f"🔍 Searching YouTube for: {query} (max: {max_results})")
        
        try:
            # Build YouTube search URL with filters
            search_url = self._build_youtube_search_url(query, upload_date, duration, sort_by)
            
            # Define extraction schema for YouTube search results
            schema = {
                "name": "YouTube Videos",
                "baseSelector": "ytd-video-renderer",
                "fields": [
                    {
                        "name": "video_id",
                        "selector": "a#video-title",
                        "attribute": "href",
                        "transform": "lambda x: x.split('v=')[1].split('&')[0] if 'v=' in x else ''"
                    },
                    {
                        "name": "title",
                        "selector": "a#video-title",
                        "attribute": "title"
                    },
                    {
                        "name": "channel_title",
                        "selector": "ytd-channel-name a",
                        "type": "text"
                    },
                    {
                        "name": "channel_url",
                        "selector": "ytd-channel-name a",
                        "attribute": "href"
                    },
                    {
                        "name": "views",
                        "selector": "span.inline-metadata-item:first-child",
                        "type": "text"
                    },
                    {
                        "name": "published",
                        "selector": "span.inline-metadata-item:nth-child(2)",
                        "type": "text"
                    },
                    {
                        "name": "duration",
                        "selector": "span.ytd-thumbnail-overlay-time-status-renderer",
                        "type": "text"
                    },
                    {
                        "name": "thumbnail",
                        "selector": "img.yt-core-image",
                        "attribute": "src"
                    },
                    {
                        "name": "description",
                        "selector": "yt-formatted-string#description-text",
                        "type": "text"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            # Configure crawler to handle YouTube's dynamic loading
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_for="css:ytd-video-renderer",  # Wait for video results
                js_code="""
                // Scroll to load more results
                let scrollCount = 0;
                const maxScrolls = Math.ceil(%d / 20);  // YouTube loads ~20 videos per scroll
                
                const scrollInterval = setInterval(() => {
                    window.scrollTo(0, document.documentElement.scrollHeight);
                    scrollCount++;
                    
                    if (scrollCount >= maxScrolls) {
                        clearInterval(scrollInterval);
                    }
                }, 2000);
                
                // Wait for scrolling to complete
                await new Promise(resolve => setTimeout(resolve, maxScrolls * 2000 + 1000));
                """ % max_results
            )
            
            # Scrape YouTube search results
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=search_url,
                    config=crawler_config
                )
                
                if result.success and result.extracted_content:
                    videos = json.loads(result.extracted_content)
                    
                    # Process and clean video data
                    processed_videos = []
                    for video in videos[:max_results]:
                        processed_video = self._process_video_data(video)
                        if processed_video:
                            processed_videos.append(processed_video)
                    
                    logger.info(f"✅ Found {len(processed_videos)} videos on YouTube")
                    return processed_videos
                else:
                    logger.warning("❌ Failed to extract YouTube search results")
                    return []
                    
        except Exception as e:
            logger.error(f"❌ YouTube search error: {str(e)}")
            return []
    
    async def scrape_channel(self, channel_url: str) -> Dict[str, Any]:
        """
        Scrape YouTube channel information
        
        Args:
            channel_url: YouTube channel URL
            
        Returns:
            Channel data dictionary
        """
        logger.info(f"📺 Scraping YouTube channel: {channel_url}")
        
        try:
            # Convert to about page for more info
            about_url = channel_url.rstrip('/') + '/about'
            
            # Schema for channel data extraction
            schema = {
                "name": "YouTube Channel",
                "fields": [
                    {
                        "name": "channel_name",
                        "selector": "yt-formatted-string.ytd-channel-name",
                        "type": "text"
                    },
                    {
                        "name": "subscriber_count",
                        "selector": "#subscriber-count",
                        "type": "text"
                    },
                    {
                        "name": "description",
                        "selector": "#description-container yt-formatted-string",
                        "type": "text"
                    },
                    {
                        "name": "join_date",
                        "selector": "#right-column yt-formatted-string:contains('Joined')",
                        "type": "text"
                    },
                    {
                        "name": "view_count",
                        "selector": "#right-column yt-formatted-string:contains('views')",
                        "type": "text"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_for="css:#description-container",
                js_code="""
                // Click on channel links to reveal social media
                const linksButton = document.querySelector('button[aria-label*="Links"]');
                if (linksButton) linksButton.click();
                await new Promise(resolve => setTimeout(resolve, 1000));
                """
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=about_url,
                    config=crawler_config
                )
                
                if result.success:
                    # Extract channel data
                    channel_data = {}
                    if result.extracted_content:
                        channel_data = json.loads(result.extracted_content)
                    
                    # Extract social links from HTML
                    social_links = self._extract_channel_social_links(result.html)
                    channel_data['social_links'] = social_links
                    
                    # Parse channel ID from URL
                    channel_id_match = re.search(r'/channel/([^/]+)', channel_url)
                    if channel_id_match:
                        channel_data['channel_id'] = channel_id_match.group(1)
                    
                    logger.info(f"✅ Scraped channel: {channel_data.get('channel_name', 'Unknown')}")
                    return channel_data
                else:
                    logger.warning("❌ Failed to scrape YouTube channel")
                    return {}
                    
        except Exception as e:
            logger.error(f"❌ Channel scraping error: {str(e)}")
            return {}
    
    async def get_video_details(self, video_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific video
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Video details dictionary
        """
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"🎥 Getting details for video: {video_id}")
        
        try:
            # Schema for video details
            schema = {
                "name": "Video Details",
                "fields": [
                    {
                        "name": "title",
                        "selector": "h1.ytd-video-primary-info-renderer",
                        "type": "text"
                    },
                    {
                        "name": "views",
                        "selector": ".view-count",
                        "type": "text"
                    },
                    {
                        "name": "likes",
                        "selector": "yt-formatted-string.ytd-toggle-button-renderer:first-child",
                        "type": "text"
                    },
                    {
                        "name": "upload_date",
                        "selector": "#info-strings yt-formatted-string",
                        "type": "text"
                    },
                    {
                        "name": "description",
                        "selector": "#description yt-formatted-string",
                        "type": "text"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_for="css:h1.ytd-video-primary-info-renderer",
                js_code="""
                // Expand description
                const showMoreButton = document.querySelector('tp-yt-paper-button#expand');
                if (showMoreButton) showMoreButton.click();
                await new Promise(resolve => setTimeout(resolve, 500));
                """
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=video_url,
                    config=crawler_config
                )
                
                if result.success and result.extracted_content:
                    video_details = json.loads(result.extracted_content)
                    video_details['video_id'] = video_id
                    video_details['url'] = video_url
                    
                    # Extract social links from description
                    if video_details.get('description'):
                        social_links = self._extract_social_links_from_text(video_details['description'])
                        video_details['social_links'] = social_links
                    
                    logger.info(f"✅ Got details for: {video_details.get('title', 'Unknown')}")
                    return video_details
                else:
                    logger.warning("❌ Failed to get video details")
                    return {}
                    
        except Exception as e:
            logger.error(f"❌ Video details error: {str(e)}")
            return {}
    
    def _build_youtube_search_url(self, query: str, upload_date: str, duration: str, sort_by: str) -> str:
        """Build YouTube search URL with filters"""
        base_url = "https://www.youtube.com/results"
        params = {"search_query": query}
        
        # Add filter parameters
        filters = []
        
        # Upload date filter
        upload_map = {
            "today": "EgQIARAB",
            "week": "EgQIAxAB", 
            "month": "EgQIBBAB",
            "year": "EgQIBRAB"
        }
        if upload_date in upload_map:
            filters.append(upload_map[upload_date])
        
        # Duration filter
        duration_map = {
            "short": "EgQYAQ%3D%3D",
            "long": "EgQYAw%3D%3D"
        }
        if duration in duration_map:
            filters.append(duration_map[duration])
        
        # Sort filter
        sort_map = {
            "date": "CAI%3D",
            "views": "CAM%3D",
            "rating": "CAE%3D"
        }
        if sort_by in sort_map:
            filters.append(sort_map[sort_by])
        
        # Combine filters
        if filters:
            params["sp"] = "".join(filters)
        
        return f"{base_url}?{urllib.parse.urlencode(params)}"
    
    def _process_video_data(self, raw_video: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process and clean raw video data"""
        try:
            # Skip if missing essential data
            if not raw_video.get('video_id') or not raw_video.get('title'):
                return None
            
            # Parse view count
            view_count = 0
            views_text = raw_video.get('views', '')
            if views_text:
                # Extract number from "1.2M views" format
                views_match = re.search(r'([\d.]+)([KMB]?)', views_text.replace(',', ''))
                if views_match:
                    number = float(views_match.group(1))
                    multiplier = {'K': 1000, 'M': 1000000, 'B': 1000000000}.get(views_match.group(2), 1)
                    view_count = int(number * multiplier)
            
            # Parse duration to seconds
            duration_seconds = 0
            duration_text = raw_video.get('duration', '')
            if duration_text:
                time_parts = duration_text.split(':')
                if len(time_parts) == 2:
                    duration_seconds = int(time_parts[0]) * 60 + int(time_parts[1])
                elif len(time_parts) == 3:
                    duration_seconds = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
            
            # Extract channel ID from URL
            channel_id = ''
            channel_url = raw_video.get('channel_url', '')
            if channel_url:
                channel_match = re.search(r'/channel/([^/]+)', channel_url)
                if channel_match:
                    channel_id = channel_match.group(1)
            
            # Build processed video data
            return {
                'video_id': raw_video['video_id'],
                'title': raw_video['title'],
                'channel_title': raw_video.get('channel_title', ''),
                'channel_id': channel_id,
                'channel_url': f"https://www.youtube.com{channel_url}" if channel_url.startswith('/') else channel_url,
                'view_count': view_count,
                'published_at': raw_video.get('published', ''),
                'duration': duration_text,
                'duration_seconds': duration_seconds,
                'thumbnail': raw_video.get('thumbnail', ''),
                'description': raw_video.get('description', ''),
                'extracted_artist_name': self._extract_artist_name(raw_video['title'])
            }
            
        except Exception as e:
            logger.error(f"Error processing video data: {e}")
            return None
    
    def _extract_artist_name(self, title: str) -> Optional[str]:
        """Extract artist name from video title"""
        # Common patterns for music videos
        patterns = [
            r'^([^-–—]+?)\s*[-–—]\s*',  # "Artist - Song"
            r'^([^|]+?)\s*\|\s*',  # "Artist | Song"
            r'^([^:]+?)\s*:\s*',  # "Artist: Song"
            r'^([^"]+?)\s*"',  # 'Artist "Song"'
            r'^([^(]+?)\s*\(',  # "Artist (Official Video)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                artist = match.group(1).strip()
                # Clean up common suffixes
                artist = re.sub(r'\s*(Official|Music|Video|Audio|Lyric|Visualizer).*$', '', artist, flags=re.IGNORECASE)
                return artist.strip()
        
        return None
    
    def _extract_social_links_from_text(self, text: str) -> Dict[str, str]:
        """Extract social media links from text"""
        social_links = {}
        
        patterns = {
            'instagram': r'(?:instagram\.com|instagr\.am)/([A-Za-z0-9_.]+)',
            'tiktok': r'tiktok\.com/@([A-Za-z0-9_.]+)',
            'spotify': r'open\.spotify\.com/artist/([A-Za-z0-9]+)',
            'twitter': r'(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)',
            'facebook': r'facebook\.com/([A-Za-z0-9.]+)'
        }
        
        for platform, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                username = match.group(1)
                if platform == 'spotify':
                    social_links[platform] = f"https://open.spotify.com/artist/{username}"
                elif platform == 'instagram':
                    social_links[platform] = f"https://instagram.com/{username}"
                elif platform == 'tiktok':
                    social_links[platform] = f"https://tiktok.com/@{username}"
                elif platform == 'twitter':
                    social_links[platform] = f"https://x.com/{username}"
                elif platform == 'facebook':
                    social_links[platform] = f"https://facebook.com/{username}"
        
        return social_links
    
    def _extract_channel_social_links(self, html: str) -> Dict[str, str]:
        """Extract social links from channel about page HTML"""
        social_links = {}
        
        # Look for link elements in the channel links section
        link_pattern = r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
        matches = re.findall(link_pattern, html)
        
        for url, text in matches:
            if 'instagram.com' in url:
                social_links['instagram'] = url
            elif 'tiktok.com' in url:
                social_links['tiktok'] = url
            elif 'spotify.com' in url:
                social_links['spotify'] = url
            elif 'twitter.com' in url or 'x.com' in url:
                social_links['twitter'] = url
            elif 'facebook.com' in url:
                social_links['facebook'] = url
            elif url.startswith('http') and 'youtube' not in url:
                # Potential artist website
                if 'website' not in social_links:
                    social_links['website'] = url
        
        return social_links 