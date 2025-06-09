"""
Crawl4AI Agent for Enhanced Content Discovery

This agent uses Crawl4AI for:
- Social media profile crawling (Instagram, TikTok)
- Spotify artist page information extraction
- YouTube channel about page extraction
- Artist website content extraction
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import re

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

logger = logging.getLogger(__name__)


class Crawl4AIAgent:
    """Agent for web crawling using Crawl4AI"""
    
    def __init__(self):
        """Initialize the Crawl4AI agent"""
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080,
            extra_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        logger.info("✅ Crawl4AI Agent initialized")
    
    async def discover_artist_social_profiles(
        self,
        artist_name: str,
        channel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Discover artist's social media profiles across platforms
        
        Args:
            artist_name: Name of the artist
            channel_url: YouTube channel URL if available
            
        Returns:
            Dictionary with discovered social profiles and validation scores
        """
        logger.info(f"🔍 Discovering social profiles for: {artist_name}")
        
        results = {
            "artist_name": artist_name,
            "profiles": {
                "instagram": None,
                "tiktok": None,
                "spotify": None,
                "twitter": None,
                "facebook": None,
                "website": None
            },
            "validation_scores": {},
            "discovery_timestamp": datetime.utcnow().isoformat()
        }
        
        # Clean artist name for searches
        clean_name = self._clean_artist_name_for_search(artist_name)
        
        # Discover profiles in parallel
        tasks = [
            self._search_instagram_profile(clean_name, artist_name),
            self._search_tiktok_profile(clean_name, artist_name),
            self._search_spotify_artist(clean_name, artist_name)
        ]
        
        # If we have YouTube channel, extract additional info
        if channel_url:
            tasks.append(self._extract_youtube_channel_info(channel_url))
        
        profile_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process Instagram results
        if not isinstance(profile_results[0], Exception) and profile_results[0]:
            results["profiles"]["instagram"] = profile_results[0]["url"]
            results["validation_scores"]["instagram"] = profile_results[0]["score"]
        
        # Process TikTok results
        if not isinstance(profile_results[1], Exception) and profile_results[1]:
            results["profiles"]["tiktok"] = profile_results[1]["url"]
            results["validation_scores"]["tiktok"] = profile_results[1]["score"]
        
        # Process Spotify results
        if not isinstance(profile_results[2], Exception) and profile_results[2]:
            results["profiles"]["spotify"] = profile_results[2]["url"]
            results["validation_scores"]["spotify"] = profile_results[2]["score"]
        
        # Process YouTube channel info if available
        if len(profile_results) > 3 and not isinstance(profile_results[3], Exception):
            youtube_info = profile_results[3]
            if youtube_info:
                # Extract social links from YouTube about page
                for platform, url in youtube_info.get("social_links", {}).items():
                    if url and not results["profiles"].get(platform):
                        results["profiles"][platform] = url
                        results["validation_scores"][platform] = 0.9  # High confidence from YouTube
        
        # Calculate overall validation score
        results["overall_validation_score"] = self._calculate_overall_validation_score(results)
        
        logger.info(f"✅ Social profile discovery complete for {artist_name}")
        return results
    
    async def _search_instagram_profile(self, clean_name: str, original_name: str) -> Optional[Dict[str, Any]]:
        """Search for Instagram profile"""
        try:
            # Instagram search is challenging due to anti-bot measures
            # We'll use a conservative approach
            search_url = f"https://www.instagram.com/{clean_name.replace(' ', '')}/"
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=search_url,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        wait_for="css:h2",  # Wait for profile name
                        js_code="window.scrollTo(0, 500);"  # Scroll to load content
                    )
                )
                
                if result.success and "Sorry, this page isn't available" not in result.html:
                    # Extract profile info
                    profile_name_match = re.search(r'<h2[^>]*>([^<]+)</h2>', result.html)
                    if profile_name_match:
                        profile_name = profile_name_match.group(1)
                        score = self._calculate_name_match_score(original_name, profile_name)
                        
                        if score > 0.6:  # Reasonable match
                            logger.info(f"✅ Found Instagram: @{clean_name.replace(' ', '')} (score: {score:.2f})")
                            return {
                                "url": search_url,
                                "username": clean_name.replace(' ', ''),
                                "score": score
                            }
                
        except Exception as e:
            logger.error(f"Instagram search error: {e}")
        
        return None
    
    async def _search_tiktok_profile(self, clean_name: str, original_name: str) -> Optional[Dict[str, Any]]:
        """Search for TikTok profile"""
        try:
            # TikTok username search
            username = clean_name.replace(' ', '').lower()
            search_url = f"https://www.tiktok.com/@{username}"
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=search_url,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        wait_for="css:h1",  # Wait for profile name
                        js_code="window.scrollTo(0, 300);"
                    )
                )
                
                if result.success and "couldn't find this account" not in result.html.lower():
                    # Extract profile name
                    name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', result.html)
                    if name_match:
                        profile_name = name_match.group(1)
                        score = self._calculate_name_match_score(original_name, profile_name)
                        
                        if score > 0.6:
                            logger.info(f"✅ Found TikTok: @{username} (score: {score:.2f})")
                            return {
                                "url": search_url,
                                "username": username,
                                "score": score
                            }
                
        except Exception as e:
            logger.error(f"TikTok search error: {e}")
        
        return None
    
    async def _search_spotify_artist(self, clean_name: str, original_name: str) -> Optional[Dict[str, Any]]:
        """Search for Spotify artist profile"""
        try:
            # Spotify web search
            search_query = clean_name.replace(' ', '%20')
            search_url = f"https://open.spotify.com/search/{search_query}/artists"
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=search_url,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        wait_for="css:a[href^='/artist/']",  # Wait for artist links
                        js_code="window.scrollTo(0, 500);"
                    )
                )
                
                if result.success:
                    # Extract artist links and names
                    artist_pattern = r'<a[^>]*href="(/artist/[^"]+)"[^>]*>.*?<span[^>]*>([^<]+)</span>'
                    matches = re.findall(artist_pattern, result.html, re.DOTALL)
                    
                    best_match = None
                    best_score = 0
                    
                    for artist_url, artist_name in matches[:5]:  # Check top 5 results
                        score = self._calculate_name_match_score(original_name, artist_name)
                        if score > best_score:
                            best_score = score
                            best_match = {
                                "url": f"https://open.spotify.com{artist_url}",
                                "name": artist_name,
                                "score": score
                            }
                    
                    if best_match and best_score > 0.7:
                        logger.info(f"✅ Found Spotify artist: {best_match['name']} (score: {best_score:.2f})")
                        return best_match
                
        except Exception as e:
            logger.error(f"Spotify search error: {e}")
        
        return None
    
    async def _extract_youtube_channel_info(self, channel_url: str) -> Optional[Dict[str, Any]]:
        """Extract information from YouTube channel about page"""
        try:
            # Convert channel URL to about page
            about_url = channel_url.rstrip('/') + '/about'
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=about_url,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        wait_for="css:#links-container",  # Wait for social links
                        js_code="window.scrollTo(0, 1000);"
                    )
                )
                
                if result.success:
                    social_links = {}
                    
                    # Extract social media links
                    link_pattern = r'<a[^>]*href="([^"]+)"[^>]*>(?:.*?<span[^>]*>)?([^<]+)(?:</span>)?</a>'
                    matches = re.findall(link_pattern, result.html)
                    
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
                        elif url.startswith('http') and not any(domain in url for domain in ['youtube.com', 'youtu.be']):
                            # Potential artist website
                            if not social_links.get('website'):
                                social_links['website'] = url
                    
                    logger.info(f"✅ Extracted {len(social_links)} social links from YouTube")
                    return {"social_links": social_links}
                
        except Exception as e:
            logger.error(f"YouTube channel extraction error: {e}")
        
        return None
    
    async def extract_artist_website_info(self, website_url: str) -> Dict[str, Any]:
        """Extract information from artist's official website"""
        logger.info(f"🌐 Extracting info from website: {website_url}")
        
        try:
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=website_url,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        wait_for="css:body",
                        js_code="window.scrollTo(0, document.body.scrollHeight);"
                    )
                )
                
                if result.success:
                    info = {
                        "url": website_url,
                        "title": result.title,
                        "contact_info": {},
                        "social_links": {},
                        "tour_dates": [],
                        "bio": None
                    }
                    
                    # Extract email addresses
                    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                    emails = re.findall(email_pattern, result.markdown)
                    if emails:
                        info["contact_info"]["emails"] = list(set(emails))[:3]  # Max 3 emails
                    
                    # Extract social media links
                    social_patterns = {
                        'instagram': r'instagram\.com/([A-Za-z0-9_.]+)',
                        'tiktok': r'tiktok\.com/@([A-Za-z0-9_.]+)',
                        'spotify': r'open\.spotify\.com/artist/([A-Za-z0-9]+)',
                        'twitter': r'(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)',
                        'youtube': r'youtube\.com/(?:c/|channel/|@)([A-Za-z0-9_-]+)'
                    }
                    
                    for platform, pattern in social_patterns.items():
                        matches = re.findall(pattern, result.markdown, re.IGNORECASE)
                        if matches:
                            info["social_links"][platform] = matches[0]
                    
                    # Extract bio/about section
                    bio_match = re.search(
                        r'(?:about|bio|biography)[\s\S]{0,100}?([A-Z][^.!?]{50,500}[.!?])',
                        result.markdown,
                        re.IGNORECASE
                    )
                    if bio_match:
                        info["bio"] = bio_match.group(1).strip()
                    
                    logger.info(f"✅ Extracted website info successfully")
                    return info
                
        except Exception as e:
            logger.error(f"Website extraction error: {e}")
        
        return {}
    
    def _clean_artist_name_for_search(self, name: str) -> str:
        """Clean artist name for social media searches"""
        # Remove common suffixes
        name = re.sub(r'\s*(Official|Music|VEVO|Channel|Artist).*$', '', name, flags=re.IGNORECASE)
        # Remove special characters except spaces
        name = re.sub(r'[^a-zA-Z0-9\s]', '', name)
        # Normalize spaces
        name = ' '.join(name.split())
        return name.lower()
    
    def _calculate_name_match_score(self, name1: str, name2: str) -> float:
        """Calculate similarity score between two names"""
        # Simple similarity calculation
        name1_clean = self._clean_artist_name_for_search(name1)
        name2_clean = self._clean_artist_name_for_search(name2)
        
        if name1_clean == name2_clean:
            return 1.0
        
        # Check if one contains the other
        if name1_clean in name2_clean or name2_clean in name1_clean:
            return 0.8
        
        # Calculate word overlap
        words1 = set(name1_clean.split())
        words2 = set(name2_clean.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_overall_validation_score(self, results: Dict[str, Any]) -> float:
        """Calculate overall validation score based on found profiles"""
        scores = results.get("validation_scores", {})
        
        if not scores:
            return 0.0
        
        # Weight different platforms
        weights = {
            "spotify": 1.5,  # Spotify verification is strong
            "instagram": 1.2,  # Instagram with matching name is good
            "tiktok": 1.0,
            "youtube": 1.3,  # YouTube links are reliable
            "website": 1.1
        }
        
        weighted_sum = 0
        total_weight = 0
        
        for platform, score in scores.items():
            weight = weights.get(platform, 1.0)
            weighted_sum += score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0 