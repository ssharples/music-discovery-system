"""
Crawl4AI Enrichment Agent - Replaces Firecrawl for all enrichment scraping
Uses Crawl4AI for Spotify, Instagram, TikTok, and Musixmatch scraping
"""
import asyncio
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider

from app.models.artist import ArtistProfile, EnrichedArtistData
from app.core.config import settings

logger = logging.getLogger(__name__)


class Crawl4AIEnrichmentAgent:
    """Enrichment agent using Crawl4AI for all web scraping"""
    
    def __init__(self):
        """Initialize the Crawl4AI enrichment agent"""
        # Browser config for general scraping
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080,
            extra_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        
        # DeepSeek agent for lyrics analysis
        self.lyrics_analyzer = Agent(
            model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
            system_prompt="""You are a lyrics analyst. Analyze song lyrics and:
            1. Identify recurring themes
            2. Provide descriptive tags
            3. Summarize in one sentence
            Return a concise analysis focused on artistic themes."""
        )
        
        logger.info("✅ Crawl4AI Enrichment Agent initialized")
    
    async def enrich_artist(self, artist_profile: ArtistProfile) -> EnrichedArtistData:
        """
        Enrich artist profile with data from multiple platforms
        
        Args:
            artist_profile: Basic artist profile with name and optional social links
            
        Returns:
            Enriched artist data with all platform information
        """
        logger.info(f"🎯 Enriching artist: {artist_profile.name}")
        
        enriched_data = EnrichedArtistData(
            artist_id=artist_profile.artist_id,
            name=artist_profile.name,
            enrichment_timestamp=datetime.utcnow()
        )
        
        # Parallel enrichment tasks
        tasks = []
        
        # Spotify enrichment
        if artist_profile.spotify_url or artist_profile.spotify_id:
            tasks.append(self._enrich_spotify(artist_profile, enriched_data))
        else:
            tasks.append(self._search_and_enrich_spotify(artist_profile.name, enriched_data))
        
        # Instagram enrichment
        if artist_profile.instagram_url:
            tasks.append(self._enrich_instagram(artist_profile.instagram_url, enriched_data))
        
        # TikTok enrichment
        if artist_profile.tiktok_url:
            tasks.append(self._enrich_tiktok(artist_profile.tiktok_url, enriched_data))
        
        # Run all enrichments in parallel
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate artist score
        enriched_data.artist_score = self._calculate_artist_score(enriched_data)
        enriched_data.enrichment_score = self._calculate_enrichment_score(enriched_data)
        
        logger.info(f"✅ Enrichment complete for {artist_profile.name} (score: {enriched_data.artist_score})")
        return enriched_data
    
    async def _enrich_spotify(self, artist_profile: ArtistProfile, enriched_data: EnrichedArtistData):
        """Enrich with Spotify data using Crawl4AI"""
        try:
            spotify_url = artist_profile.spotify_url
            if not spotify_url and artist_profile.spotify_id:
                spotify_url = f"https://open.spotify.com/artist/{artist_profile.spotify_id}"
            
            logger.info(f"🎵 Crawling Spotify: {spotify_url}")
            
            # Schema for Spotify artist page
            schema = {
                "name": "Spotify Artist",
                "fields": [
                    {
                        "name": "artist_name",
                        "selector": "h1[data-testid='artist-name']",
                        "type": "text"
                    },
                    {
                        "name": "monthly_listeners",
                        "selector": "div[data-testid='monthly-listeners']",
                        "type": "text"
                    },
                    {
                        "name": "bio",
                        "selector": "div[data-testid='artist-biography']",
                        "type": "text"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_for="css:h1[data-testid='artist-name']",
                js_code="""
                // Scroll to load tracks
                window.scrollTo(0, 1000);
                await new Promise(resolve => setTimeout(resolve, 2000));
                """
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=spotify_url,
                    config=crawler_config
                )
                
                if result.success:
                    # Extract structured data
                    if result.extracted_content:
                        spotify_data = json.loads(result.extracted_content)
                        
                        # Parse monthly listeners
                        if spotify_data.get('monthly_listeners'):
                            listeners_text = spotify_data['monthly_listeners']
                            enriched_data.spotify_monthly_listeners = self._parse_number(listeners_text)
                        
                        # Store bio
                        if spotify_data.get('bio'):
                            enriched_data.bio = spotify_data['bio'][:500]  # Limit bio length
                    
                    # Extract top tracks from HTML
                    tracks = self._extract_spotify_tracks(result.html)
                    if tracks:
                        enriched_data.top_tracks = tracks[:5]  # Top 5 tracks
                        
                        # Get lyrics for top tracks
                        if tracks:
                            await self._enrich_lyrics(enriched_data)
                    
                    logger.info(f"✅ Spotify enrichment complete: {enriched_data.spotify_monthly_listeners} monthly listeners")
                    
        except Exception as e:
            logger.error(f"❌ Spotify enrichment error: {str(e)}")
    
    async def _search_and_enrich_spotify(self, artist_name: str, enriched_data: EnrichedArtistData):
        """Search for artist on Spotify and enrich"""
        try:
            search_url = f"https://open.spotify.com/search/{artist_name.replace(' ', '%20')}/artists"
            logger.info(f"🔍 Searching Spotify for: {artist_name}")
            
            # Schema for search results
            schema = {
                "name": "Spotify Search",
                "baseSelector": "div[data-testid='search-result-artist']",
                "fields": [
                    {
                        "name": "artist_url",
                        "selector": "a",
                        "attribute": "href"
                    },
                    {
                        "name": "artist_name",
                        "selector": "a",
                        "type": "text"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_for="css:div[data-testid='search-result-artist']"
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=search_url,
                    config=crawler_config
                )
                
                if result.success and result.extracted_content:
                    search_results = json.loads(result.extracted_content)
                    
                    # Find best match
                    if search_results:
                        best_match = search_results[0]  # Take first result
                        artist_url = best_match.get('artist_url')
                        
                        if artist_url:
                            # Create temporary profile with Spotify URL
                            temp_profile = ArtistProfile(
                                name=artist_name,
                                spotify_url=f"https://open.spotify.com{artist_url}"
                            )
                            # Enrich with the found artist
                            await self._enrich_spotify(temp_profile, enriched_data)
                            
        except Exception as e:
            logger.error(f"❌ Spotify search error: {str(e)}")
    
    async def _enrich_instagram(self, instagram_url: str, enriched_data: EnrichedArtistData):
        """Enrich with Instagram data using authenticated scraping"""
        try:
            logger.info(f"📸 Crawling Instagram: {instagram_url}")
            
            # Instagram requires authentication for full data
            # For now, we'll do basic scraping
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_for="css:header",
                js_code="""
                // Wait for page load
                await new Promise(resolve => setTimeout(resolve, 3000));
                """
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=instagram_url,
                    config=crawler_config
                )
                
                if result.success:
                    # Extract follower count from meta tags or JSON data
                    followers_match = re.search(r'"edge_followed_by":\{"count":(\d+)\}', result.html)
                    if followers_match:
                        enriched_data.instagram_followers = int(followers_match.group(1))
                        logger.info(f"✅ Instagram followers: {enriched_data.instagram_followers:,}")
                    else:
                        # Try alternative pattern
                        followers_text_match = re.search(r'([\d.]+[KMB]?)\s*[Ff]ollowers', result.html)
                        if followers_text_match:
                            enriched_data.instagram_followers = self._parse_number(followers_text_match.group(1))
                    
        except Exception as e:
            logger.error(f"❌ Instagram enrichment error: {str(e)}")
    
    async def _enrich_tiktok(self, tiktok_url: str, enriched_data: EnrichedArtistData):
        """Enrich with TikTok data"""
        try:
            logger.info(f"🎭 Crawling TikTok: {tiktok_url}")
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_for="css:h2[data-e2e='user-subtitle']",
                js_code="""
                // Wait for page load
                await new Promise(resolve => setTimeout(resolve, 3000));
                """
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=tiktok_url,
                    config=crawler_config
                )
                
                if result.success:
                    # Extract follower count
                    followers_match = re.search(r'([\d.]+[KMB]?)\s*[Ff]ollowers', result.html)
                    if followers_match:
                        enriched_data.tiktok_followers = self._parse_number(followers_match.group(1))
                    
                    # Extract total likes
                    likes_match = re.search(r'([\d.]+[KMB]?)\s*[Ll]ikes', result.html)
                    if likes_match:
                        enriched_data.tiktok_likes = self._parse_number(likes_match.group(1))
                    
                    logger.info(f"✅ TikTok: {enriched_data.tiktok_followers:,} followers, {enriched_data.tiktok_likes:,} likes")
                    
        except Exception as e:
            logger.error(f"❌ TikTok enrichment error: {str(e)}")
    
    async def _enrich_lyrics(self, enriched_data: EnrichedArtistData):
        """Enrich with lyrics analysis from Musixmatch"""
        try:
            if not enriched_data.top_tracks:
                return
            
            lyrics_analyses = []
            
            for track in enriched_data.top_tracks[:3]:  # Analyze top 3 tracks
                track_name = track.get('name', '')
                artist_name = enriched_data.name
                
                # Format for Musixmatch URL
                clean_artist = re.sub(r'[^a-zA-Z0-9\s]', '', artist_name).replace(' ', '-').lower()
                clean_track = re.sub(r'[^a-zA-Z0-9\s]', '', track_name).replace(' ', '-').lower()
                
                musixmatch_url = f"https://www.musixmatch.com/lyrics/{clean_artist}/{clean_track}"
                
                logger.info(f"🎤 Getting lyrics for: {track_name}")
                
                crawler_config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    wait_for="css:.lyrics__content",
                    js_code="""
                    // Wait for lyrics to load
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    """
                )
                
                async with AsyncWebCrawler(config=self.browser_config) as crawler:
                    result = await crawler.arun(
                        url=musixmatch_url,
                        config=crawler_config
                    )
                    
                    if result.success:
                        # Extract lyrics text
                        lyrics_match = re.search(r'<span class="lyrics__content[^"]*">([^<]+)</span>', result.html)
                        if lyrics_match:
                            lyrics_text = lyrics_match.group(1)
                            
                            # Analyze lyrics with DeepSeek
                            analysis = await self._analyze_lyrics(lyrics_text, track_name)
                            if analysis:
                                lyrics_analyses.append(analysis)
            
            # Combine analyses
            if lyrics_analyses:
                enriched_data.lyrics_themes = self._combine_lyrics_analyses(lyrics_analyses)
                logger.info(f"✅ Lyrics analysis complete: {enriched_data.lyrics_themes}")
                
        except Exception as e:
            logger.error(f"❌ Lyrics enrichment error: {str(e)}")
    
    async def _analyze_lyrics(self, lyrics: str, track_name: str) -> Dict[str, Any]:
        """Analyze lyrics using DeepSeek"""
        try:
            result = await self.lyrics_analyzer.run(
                f"Analyze these lyrics from '{track_name}':\n\n{lyrics[:1000]}\n\nProvide: 1) Main theme in one sentence, 2) 3-5 descriptive tags"
            )
            
            # Parse the response
            response_text = result.data
            
            # Extract theme and tags (basic parsing)
            lines = response_text.split('\n')
            theme = ""
            tags = []
            
            for line in lines:
                if 'theme' in line.lower():
                    theme = line.split(':', 1)[1].strip() if ':' in line else line
                elif 'tag' in line.lower():
                    # Extract tags from the line
                    tag_part = line.split(':', 1)[1].strip() if ':' in line else line
                    tags = [t.strip() for t in tag_part.split(',')]
            
            return {
                "track": track_name,
                "theme": theme,
                "tags": tags
            }
            
        except Exception as e:
            logger.error(f"Lyrics analysis error: {e}")
            return None
    
    def _combine_lyrics_analyses(self, analyses: List[Dict[str, Any]]) -> str:
        """Combine multiple lyrics analyses into a summary"""
        all_tags = []
        themes = []
        
        for analysis in analyses:
            if analysis:
                if analysis.get('tags'):
                    all_tags.extend(analysis['tags'])
                if analysis.get('theme'):
                    themes.append(analysis['theme'])
        
        # Find most common tags
        tag_counts = {}
        for tag in all_tags:
            tag_lower = tag.lower()
            tag_counts[tag_lower] = tag_counts.get(tag_lower, 0) + 1
        
        # Get top tags
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_tag_names = [tag[0] for tag in top_tags]
        
        # Create summary
        if themes:
            summary = f"Themes: {themes[0]}"
            if top_tag_names:
                summary += f" | Tags: {', '.join(top_tag_names)}"
            return summary
        elif top_tag_names:
            return f"Tags: {', '.join(top_tag_names)}"
        else:
            return "No clear themes identified"
    
    def _extract_spotify_tracks(self, html: str) -> List[Dict[str, Any]]:
        """Extract top tracks from Spotify HTML"""
        tracks = []
        
        # Look for track data in the HTML
        track_pattern = r'<a[^>]*aria-label="([^"]+)"[^>]*data-testid="top-track-link"[^>]*>'
        matches = re.findall(track_pattern, html)
        
        for i, track_label in enumerate(matches[:10]):  # Get up to 10 tracks
            # Parse track name from aria-label
            track_name = track_label.split(' by ')[0] if ' by ' in track_label else track_label
            
            tracks.append({
                "name": track_name,
                "position": i + 1
            })
        
        return tracks
    
    def _parse_number(self, text: str) -> int:
        """Parse numbers with K, M, B suffixes"""
        try:
            text = text.strip().upper()
            
            # Remove commas
            text = text.replace(',', '')
            
            # Handle K, M, B suffixes
            multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
            
            for suffix, multiplier in multipliers.items():
                if suffix in text:
                    number = float(text.replace(suffix, ''))
                    return int(number * multiplier)
            
            # Try to parse as regular number
            return int(float(text))
            
        except:
            return 0
    
    def _calculate_artist_score(self, data: EnrichedArtistData) -> int:
        """Calculate artist score from 0-100"""
        score = 0
        
        # Spotify metrics (40 points)
        if data.spotify_monthly_listeners:
            if data.spotify_monthly_listeners > 1000000:
                score += 40
            elif data.spotify_monthly_listeners > 100000:
                score += 30
            elif data.spotify_monthly_listeners > 10000:
                score += 20
            else:
                score += 10
        
        # Instagram metrics (30 points)
        if data.instagram_followers:
            if data.instagram_followers > 100000:
                score += 30
            elif data.instagram_followers > 10000:
                score += 20
            elif data.instagram_followers > 1000:
                score += 10
            else:
                score += 5
        
        # TikTok metrics (20 points)
        if data.tiktok_followers:
            if data.tiktok_followers > 100000:
                score += 20
            elif data.tiktok_followers > 10000:
                score += 15
            elif data.tiktok_followers > 1000:
                score += 10
            else:
                score += 5
        
        # Consistency check (10 points)
        platforms_with_data = sum([
            bool(data.spotify_monthly_listeners),
            bool(data.instagram_followers),
            bool(data.tiktok_followers)
        ])
        
        if platforms_with_data >= 3:
            score += 10
        elif platforms_with_data >= 2:
            score += 5
        
        # Check for suspicious patterns (deductions)
        if data.spotify_monthly_listeners and data.instagram_followers:
            ratio = data.spotify_monthly_listeners / (data.instagram_followers + 1)
            if ratio > 100:  # Very high Spotify vs low Instagram
                score -= 10
                logger.warning(f"Suspicious pattern detected: High Spotify/Instagram ratio ({ratio:.1f})")
        
        return min(max(score, 0), 100)
    
    def _calculate_enrichment_score(self, data: EnrichedArtistData) -> float:
        """Calculate how complete the enrichment is"""
        fields_populated = sum([
            bool(data.spotify_monthly_listeners),
            bool(data.instagram_followers),
            bool(data.tiktok_followers),
            bool(data.top_tracks),
            bool(data.bio),
            bool(data.lyrics_themes)
        ])
        
        return fields_populated / 6.0 