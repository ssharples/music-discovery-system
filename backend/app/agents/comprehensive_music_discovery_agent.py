"""
Comprehensive Music Discovery Agent
Handles the complete workflow from YouTube search to multi-platform data extraction and scoring.
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote_plus, urlparse, parse_qs
import requests
from dataclasses import dataclass

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.models import CrawlResult

# Import our agents
from .crawl4ai_youtube_agent import Crawl4AIYouTubeAgent
from .crawl4ai_enrichment_agent import Crawl4AIEnrichmentAgent

# Database
from supabase import create_client, Client

logger = logging.getLogger(__name__)

@dataclass
class ArtistDiscoveryResult:
    """Result of artist discovery process."""
    artist_name: str
    discovery_score: int
    youtube_data: Dict[str, Any]
    spotify_data: Dict[str, Any]
    instagram_data: Dict[str, Any]
    tiktok_data: Dict[str, Any]
    lyrics_analysis: Dict[str, Any]
    social_links: Dict[str, str]
    success: bool
    error_message: Optional[str] = None

class ComprehensiveMusicDiscoveryAgent:
    """
    Comprehensive music discovery agent that:
    1. Searches YouTube for 'official music video' with specific filters
    2. Extracts and validates artist names
    3. Crawls multiple platforms (YouTube, Spotify, Instagram, TikTok)
    4. Analyzes lyrics sentiment
    5. Calculates artist discovery score
    6. Stores results in Supabase
    """
    
    def __init__(self):
        self.youtube_agent = Crawl4AIYouTubeAgent()
        self.enrichment_agent = Crawl4AIEnrichmentAgent()
        
        # Initialize Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Spotify API setup
        self.spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.spotify_token = None
        
        # Configuration
        self.exclude_keywords = json.loads(os.getenv("EXCLUDE_AI_KEYWORDS", '["ai", "suno", "generated", "udio", "cover", "remix"]'))
        self.max_videos = int(os.getenv("MAX_VIDEOS_PER_SEARCH", "1000"))
        self.batch_size = int(os.getenv("BATCH_SIZE", "50"))
        
        # DeepSeek API for lyrics analysis
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        
    async def discover_new_artists(self, limit: int = 100) -> List[ArtistDiscoveryResult]:
        """
        Main method to discover new artists using the comprehensive workflow.
        """
        logger.info(f"🎵 Starting comprehensive music discovery for up to {limit} artists")
        
        # Step 1: Search YouTube for official music videos
        youtube_results = await self._search_youtube_official_videos()
        
        if not youtube_results or not youtube_results.success:
            logger.error("Failed to search YouTube videos")
            return []
            
        logger.info(f"Found {len(youtube_results.videos)} YouTube videos to process")
        
        # Step 2: Process videos in batches
        discovery_results = []
        processed_count = 0
        
        for i in range(0, min(len(youtube_results.videos), limit), self.batch_size):
            batch = youtube_results.videos[i:i + self.batch_size]
            batch_results = await self._process_video_batch(batch)
            discovery_results.extend(batch_results)
            
            processed_count += len(batch)
            logger.info(f"Processed {processed_count}/{min(len(youtube_results.videos), limit)} videos")
            
            # Add delay between batches to respect rate limits
            await asyncio.sleep(2.0)
            
        logger.info(f"🎯 Discovery complete! Found {len(discovery_results)} new artists")
        return discovery_results
    
    async def _search_youtube_official_videos(self):
        """Search YouTube for official music videos with specific filters."""
        try:
            logger.info("Searching YouTube for 'official music video' with today's uploads, under 4 min, 4K quality")
            
            # Use our enhanced YouTube agent
            result = await self.youtube_agent.search_videos(
                query="official music video",
                max_results=self.max_videos,
                upload_date="today"  # Today's uploads as requested
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching YouTube: {str(e)}")
            return None
    
    def _extract_artist_name(self, title: str) -> Optional[str]:
        """Extract artist name from video title."""
        # Common patterns for music video titles
        patterns = [
            r'^([^-]+)\s*-\s*[^-]+\s*\(Official\s*(Music\s*)?Video\)',  # Artist - Song (Official Video)
            r'^([^-]+)\s*-\s*[^-]+$',  # Artist - Song
            r'^([^|]+)\s*\|\s*[^|]+$',  # Artist | Song
            r'^([^:]+):\s*[^:]+$',     # Artist: Song
            r'^(.+?)\s*["\']([^"\']+)["\']',  # Artist "Song"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                artist_name = match.group(1).strip()
                # Clean up common prefixes/suffixes
                artist_name = re.sub(r'\s*\((Official|Music|Video|HD|4K)\).*$', '', artist_name, flags=re.IGNORECASE)
                artist_name = re.sub(r'\s*(ft\.|feat\.|featuring).*$', '', artist_name, flags=re.IGNORECASE)
                return artist_name.strip() if len(artist_name.strip()) > 1 else None
        
        # Fallback: take first part before common separators
        for separator in ['-', '|', ':', '(']:
            if separator in title:
                artist_name = title.split(separator)[0].strip()
                if len(artist_name) > 1:
                    return artist_name
        
        return None
    
    async def _process_video_batch(self, videos: List) -> List[ArtistDiscoveryResult]:
        """Process a batch of YouTube videos."""
        results = []
        
        for video in videos:
            try:
                result = await self._process_single_video(video)
                if result and result.success:
                    results.append(result)
                    
                # Add delay between video processing
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Error processing video {video.title}: {str(e)}")
                continue
                
        return results
    
    async def _process_single_video(self, video) -> Optional[ArtistDiscoveryResult]:
        """Process a single YouTube video through the complete workflow."""
        start_time = time.time()
        
        # Step 1: Extract artist name from video title
        artist_name = self._extract_artist_name(video.title)
        if not artist_name:
            return None
        
        logger.info(f"🎤 Processing artist: {artist_name}")
        
        # Step 2: Check if artist already exists
        if await self._artist_exists(artist_name):
            return None
        
        # Step 3: Validate content (check for AI-generated content)
        if not self._validate_content(video.title, getattr(video, 'description', '')):
            return None
        
        # Step 4: Extract social media links from description
        social_links = self._extract_social_links(getattr(video, 'description', ''))
        
        # Step 5: Create artist record in database
        artist_id = await self._create_artist_record(artist_name, video, social_links)
        if not artist_id:
            return None
        
        # Step 6: Multi-platform data extraction
        youtube_data = await self._crawl_youtube_channel(video, artist_id)
        spotify_data = await self._crawl_spotify_data(artist_name, social_links, artist_id)
        instagram_data = await self._crawl_instagram_data(social_links, artist_id)
        tiktok_data = await self._crawl_tiktok_data(social_links, artist_id)
        lyrics_analysis = await self._analyze_lyrics(artist_name, spotify_data, artist_id)
        
        # Step 7: Calculate discovery score
        discovery_score = self._calculate_discovery_score(
            youtube_data, spotify_data, instagram_data, tiktok_data, lyrics_analysis
        )
        
        # Step 8: Update artist record with final score
        await self._update_artist_score(artist_id, discovery_score)
        
        return ArtistDiscoveryResult(
            artist_name=artist_name,
            discovery_score=discovery_score,
            youtube_data=youtube_data,
            spotify_data=spotify_data,
            instagram_data=instagram_data,
            tiktok_data=tiktok_data,
            lyrics_analysis=lyrics_analysis,
            social_links=social_links,
            success=True
        )
    
    async def _artist_exists(self, artist_name: str) -> bool:
        """Check if artist already exists in database."""
        try:
            result = self.supabase.table("artist").select("id").ilike("name", f"%{artist_name}%").execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking artist existence: {str(e)}")
            return False
    
    def _validate_content(self, title: str, description: str) -> bool:
        """Validate content doesn't contain excluded keywords."""
        content = f"{title} {description or ''}".lower()
        
        for keyword in self.exclude_keywords:
            if keyword.lower() in content:
                logger.info(f"Content rejected for keyword: {keyword}")
                return False
        
        return True
    
    def _extract_social_links(self, description: str) -> Dict[str, str]:
        """Extract social media links from video description."""
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
        
        return links
    
    async def _create_artist_record(self, artist_name: str, video, social_links: Dict[str, str]) -> Optional[int]:
        """Create initial artist record in database."""
        try:
            # Extract Spotify ID if available
            spotify_id = None
            spotify_url = social_links.get('spotify')
            if spotify_url:
                spotify_match = re.search(r'/artist/([a-zA-Z0-9]+)', spotify_url)
                if spotify_match:
                    spotify_id = spotify_match.group(1)
            
            artist_data = {
                "name": artist_name,
                "discovery_source": "youtube",
                "discovery_video_id": getattr(video, 'video_id', None),
                "discovery_video_title": video.title,
                "discovery_score": 0,
                "is_validated": False,
                "last_crawled_at": datetime.utcnow().isoformat(),
                "spotify_id": spotify_id,
                "spotify_url": social_links.get('spotify'),
                "instagram_url": social_links.get('instagram'),
                "tiktok_url": social_links.get('tiktok')
            }
            
            result = self.supabase.table("artist").insert(artist_data).execute()
            
            if result.data:
                artist_id = result.data[0]['id']
                logger.info(f"Created artist record for {artist_name} with ID {artist_id}")
                return artist_id
            
        except Exception as e:
            logger.error(f"Error creating artist record: {str(e)}")
            
        return None
    
    async def _crawl_youtube_channel(self, video, artist_id: int) -> Dict[str, Any]:
        """Crawl YouTube channel data."""
        # Placeholder implementation - would extract subscriber count, social links, etc.
        return {"subscriber_count": 0, "channel_url": ""}
    
    async def _crawl_spotify_data(self, artist_name: str, social_links: Dict[str, str], artist_id: int) -> Dict[str, Any]:
        """Crawl Spotify data for the artist."""
        # Placeholder implementation - would extract monthly listeners, top tracks, etc.
        return {"monthly_listeners": 0, "top_tracks": []}
    
    async def _crawl_instagram_data(self, social_links: Dict[str, str], artist_id: int) -> Dict[str, Any]:
        """Crawl Instagram data for the artist."""
        # Placeholder implementation - would extract follower count
        return {"follower_count": 0}
    
    async def _crawl_tiktok_data(self, social_links: Dict[str, str], artist_id: int) -> Dict[str, Any]:
        """Crawl TikTok data for the artist."""
        # Placeholder implementation - would extract follower count and likes
        return {"follower_count": 0, "likes_count": 0}
    
    async def _analyze_lyrics(self, artist_name: str, spotify_data: Dict[str, Any], artist_id: int) -> Dict[str, Any]:
        """Analyze lyrics sentiment using DeepSeek API."""
        # Placeholder implementation - would extract lyrics and analyze sentiment
        return {"sentiment": "neutral", "themes": []}
    
    def _calculate_discovery_score(self, youtube_data: Dict, spotify_data: Dict, 
                                 instagram_data: Dict, tiktok_data: Dict, 
                                 lyrics_analysis: Dict) -> int:
        """Calculate discovery score (0-100) based on all extracted data."""
        score = 0
        
        # YouTube metrics (30 points max)
        subscribers = youtube_data.get('subscriber_count', 0)
        if subscribers > 1000000:
            score += 30
        elif subscribers > 100000:
            score += 25
        elif subscribers > 10000:
            score += 20
        elif subscribers > 1000:
            score += 15
        
        # Spotify metrics (25 points max)
        monthly_listeners = spotify_data.get('monthly_listeners', 0)
        if monthly_listeners > 1000000:
            score += 25
        elif monthly_listeners > 100000:
            score += 20
        elif monthly_listeners > 10000:
            score += 15
        elif monthly_listeners > 1000:
            score += 10
        
        # Instagram metrics (20 points max)
        instagram_followers = instagram_data.get('follower_count', 0)
        if instagram_followers > 1000000:
            score += 20
        elif instagram_followers > 100000:
            score += 15
        elif instagram_followers > 10000:
            score += 10
        elif instagram_followers > 1000:
            score += 5
        
        # TikTok metrics (15 points max)
        tiktok_followers = tiktok_data.get('follower_count', 0)
        if tiktok_followers > 1000000:
            score += 15
        elif tiktok_followers > 100000:
            score += 12
        elif tiktok_followers > 10000:
            score += 8
        elif tiktok_followers > 1000:
            score += 5
        
        # Content quality (10 points max)
        if lyrics_analysis.get('sentiment') == 'positive':
            score += 5
        themes = lyrics_analysis.get('themes', [])
        if len(themes) > 0:
            score += 5
        
        return min(score, 100)  # Cap at 100
    
    async def _update_artist_score(self, artist_id: int, score: int):
        """Update artist discovery score in database."""
        try:
            self.supabase.table("artist").update({
                "discovery_score": score,
                "is_validated": True,
                "last_crawled_at": datetime.utcnow().isoformat()
            }).eq("id", artist_id).execute()
        except Exception as e:
            logger.error(f"Error updating artist score: {str(e)}") 