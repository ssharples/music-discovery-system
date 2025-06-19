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
from urllib.parse import urlparse, parse_qs, unquote

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
            user_agent_mode="random",
            extra_args=[
                "--no-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        logger.info("✅ Crawl4AI Agent initialized")
    
    async def discover_artist_social_profiles(
        self,
        artist_name: str,
        youtube_video_url: str
    ) -> Dict[str, Any]:
        """
        Discover artist's social media profiles across platforms with mandatory YouTube channel extraction
        
        Args:
            artist_name: Name of the artist
            youtube_video_url: YouTube video URL to extract channel from
            
        Returns:
            Dictionary with discovered social profiles, validation scores, and source information
        """
        logger.info(f"🔍 Discovering social profiles for: {artist_name}")
        
        results = {
            "artist_name": artist_name,
            "youtube_channel": None,
            "profiles": {
                "instagram": None,
                "tiktok": None,
                "spotify": None,
                "twitter": None,
                "facebook": None,
                "website": None
            },
            "validation_scores": {},
            "source": {},
            "discovery_timestamp": datetime.utcnow().isoformat()
        }
        
        # Clean artist name for searches
        clean_name = self._clean_artist_name_for_search(artist_name)
        
        # Step 1: Extract YouTube channel from video URL (mandatory)
        logger.info(f"📺 Step 1: Extracting YouTube channel from video URL")
        channel_url = await self.extract_channel_from_video(youtube_video_url)
        if channel_url:
            results["youtube_channel"] = channel_url
            logger.info(f"✅ Extracted channel: {channel_url}")
        else:
            logger.warning(f"⚠️ Failed to extract channel from video: {youtube_video_url}")
        
        # Step 2: Extract links from video description (priority source)
        logger.info(f"📺 Step 2: Extracting links from video description")
        video_links = await self._extract_video_description_links(youtube_video_url)
        
        # Step 3: Extract links from channel (if available)
        channel_links = {}
        if channel_url:
            logger.info(f"📺 Step 3: Extracting links from channel")
            channel_links = await self._extract_channel_links(channel_url)
        
        # Combine and process YouTube-sourced links (priority)
        youtube_links = {**video_links, **channel_links}
        for platform, link_data in youtube_links.items():
            if link_data and link_data["url"]:
                results["profiles"][platform] = link_data["url"]
                results["validation_scores"][platform] = link_data["score"]
                results["source"][platform] = link_data["source"]
        
        # Step 4: Fallback to search methods only for platforms not found via YouTube
        logger.info(f"📺 Step 4: Using search fallback for missing platforms")
        missing_platforms = [p for p in ["instagram", "tiktok", "spotify"] 
                           if not results["profiles"].get(p)]
        
        if missing_platforms:
            search_tasks = []
            if "instagram" in missing_platforms:
                search_tasks.append(self._search_instagram_profile(clean_name, artist_name))
            if "tiktok" in missing_platforms:
                search_tasks.append(self._search_tiktok_profile(clean_name, artist_name))
            if "spotify" in missing_platforms:
                search_tasks.append(self._search_spotify_artist(clean_name, artist_name))
            
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Process search results for missing platforms
            result_idx = 0
            for platform in missing_platforms:
                if result_idx < len(search_results) and not isinstance(search_results[result_idx], Exception):
                    search_result = search_results[result_idx]
                    if search_result:
                        results["profiles"][platform] = search_result["url"]
                        results["validation_scores"][platform] = search_result["score"]
                        results["source"][platform] = "search_fallback"
                result_idx += 1
        
        # Calculate overall validation score
        results["overall_validation_score"] = self._calculate_overall_validation_score(results)
        
        logger.info(f"✅ Social profile discovery complete for {artist_name}")
        logger.info(f"📊 Found profiles: {[p for p, v in results['profiles'].items() if v]}")
        logger.info(f"📊 Sources: {results['source']}")
        return results
    
    def unwrap_youtube_redirect(self, redirect_url: str) -> str:
        """
        Unwrap YouTube redirect links to get the actual destination URL
        
        Args:
            redirect_url: YouTube redirect URL (e.g., https://www.youtube.com/redirect?q=...)
            
        Returns:
            Unwrapped destination URL
        """
        try:
            if 'youtube.com/redirect' in redirect_url:
                parsed = urlparse(redirect_url)
                query_params = parse_qs(parsed.query)
                if 'q' in query_params:
                    return unquote(query_params['q'][0])
            return redirect_url
        except Exception as e:
            logger.warning(f"Failed to unwrap redirect URL {redirect_url}: {e}")
            return redirect_url
    
    async def extract_channel_from_video(self, video_url: str) -> Optional[str]:
        """
        Extract YouTube channel URL from video URL
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            YouTube channel URL or None if extraction fails
        """
        try:
            logger.info(f"🔍 Extracting channel from video: {video_url}")
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=video_url,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        wait_until="domcontentloaded",
                        page_timeout=15000,
                        delay_before_return_html=2.0,
                        js_code="""
                        // Wait for page load
                        await new Promise(resolve => setTimeout(resolve, 2000));
                        console.log('Video page loaded for channel extraction');
                        """
                    )
                )
                
                if result.success and result.html:
                    # Method 1: Extract from channelId in HTML
                    channel_id_match = re.search(r'"channelId":"([^"]+)"', result.html)
                    if channel_id_match:
                        channel_id = channel_id_match.group(1)
                        channel_url = f"https://www.youtube.com/channel/{channel_id}"
                        logger.info(f"✅ Extracted channel via channelId: {channel_url}")
                        return channel_url
                    
                    # Method 2: Extract from channel link in page
                    channel_link_patterns = [
                        r'href="(/channel/[^"]+)"',
                        r'href="(/c/[^"]+)"',
                        r'href="(/@[^"]+)"'
                    ]
                    
                    for pattern in channel_link_patterns:
                        matches = re.findall(pattern, result.html)
                        if matches:
                            channel_path = matches[0]
                            channel_url = f"https://www.youtube.com{channel_path}"
                            logger.info(f"✅ Extracted channel via link pattern: {channel_url}")
                            return channel_url
                    
                    # Method 3: Extract from meta tags
                    meta_channel_match = re.search(r'<meta[^>]*property="og:url"[^>]*content="([^"]*(?:channel|c)/[^"]*)"', result.html)
                    if meta_channel_match:
                        channel_url = meta_channel_match.group(1)
                        logger.info(f"✅ Extracted channel via meta tag: {channel_url}")
                        return channel_url
                
        except Exception as e:
            logger.error(f"❌ Channel extraction error: {e}")
        
        return None
    
    async def _extract_video_description_links(self, video_url: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract social media links from YouTube video description
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Dictionary of platform -> {url, score, source} mappings
        """
        links = {}
        
        try:
            logger.info(f"🔍 Extracting links from video description")
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=video_url,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        wait_until="domcontentloaded",
                        page_timeout=15000,
                        delay_before_return_html=3.0,
                        js_code="""
                        // Expand description if collapsed
                        await new Promise(resolve => setTimeout(resolve, 2000));
                        
                        const showMoreButton = document.querySelector('#expand');
                        if (showMoreButton) {
                            showMoreButton.click();
                            await new Promise(resolve => setTimeout(resolve, 1000));
                        }
                        
                        console.log('Video description expanded');
                        """
                    )
                )
                
                if result.success and result.html:
                    # Extract description text
                    description_patterns = [
                        r'<meta[^>]*name="description"[^>]*content="([^"]+)"',
                        r'"shortDescription":"([^"]+)"',
                        r'<div[^>]*id="description"[^>]*>([^<]+)</div>'
                    ]
                    
                    description_text = ""
                    for pattern in description_patterns:
                        match = re.search(pattern, result.html, re.DOTALL)
                        if match:
                            description_text = match.group(1)
                            break
                    
                    if description_text:
                        logger.info(f"📝 Found description text ({len(description_text)} chars)")
                        
                        # Combined regex for direct and wrapped links
                        link_pattern = r'(https://www\.youtube\.com/redirect\?[^\s]+|https?://(?:www\.)?(instagram|tiktok|spotify)\.com/[\w\-/@]+)'
                        matches = re.findall(link_pattern, description_text, re.IGNORECASE)
                        
                        for match in matches:
                            if isinstance(match, tuple):
                                url = match[0]
                                platform = match[1] if match[1] else self._identify_platform_from_url(url)
                            else:
                                url = match
                                platform = self._identify_platform_from_url(url)
                            
                            if platform:
                                # Unwrap redirect links
                                final_url = self.unwrap_youtube_redirect(url)
                                
                                links[platform] = {
                                    "url": final_url,
                                    "score": 0.9,  # High confidence from video description
                                    "source": "youtube_video_description"
                                }
                                logger.info(f"✅ Found {platform} link in description: {final_url}")
        
        except Exception as e:
            logger.error(f"❌ Video description extraction error: {e}")
        
        return links
    
    async def _extract_channel_links(self, channel_url: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract social media links from YouTube channel links section
        
        Args:
            channel_url: YouTube channel URL
            
        Returns:
            Dictionary of platform -> {url, score, source} mappings
        """
        links = {}
        
        try:
            logger.info(f"🔍 Extracting links from channel: {channel_url}")
            
            # Try both about page and main channel page
            urls_to_try = [
                channel_url.rstrip('/') + '/about',
                channel_url
            ]
            
            for url in urls_to_try:
                async with AsyncWebCrawler(config=self.browser_config) as crawler:
                    result = await crawler.arun(
                        url=url,
                        config=CrawlerRunConfig(
                            cache_mode=CacheMode.BYPASS,
                            wait_until="domcontentloaded",
                            page_timeout=15000,
                            delay_before_return_html=3.0,
                            js_code="""
                            // Wait for page load and scroll to load links section
                            await new Promise(resolve => setTimeout(resolve, 2000));
                            window.scrollTo(0, 1000);
                            await new Promise(resolve => setTimeout(resolve, 1000));
                            console.log('Channel page processed');
                            """
                        )
                    )
                    
                    if result.success and result.html:
                        # Combined regex for both direct and wrapped links
                        link_pattern = r'(https://www\.youtube\.com/redirect\?[^\s"]+|https?://(?:www\.)?(instagram|tiktok|spotify)\.com/[\w\-/@]+)'
                        matches = re.findall(link_pattern, result.html, re.IGNORECASE)
                        
                        for match in matches:
                            if isinstance(match, tuple):
                                url = match[0]
                                platform = match[1] if match[1] else self._identify_platform_from_url(url)
                            else:
                                url = match
                                platform = self._identify_platform_from_url(url)
                            
                            if platform and platform not in links:
                                # Unwrap redirect links
                                final_url = self.unwrap_youtube_redirect(url)
                                
                                links[platform] = {
                                    "url": final_url,
                                    "score": 0.85,  # High confidence from channel
                                    "source": "youtube_channel_links"
                                }
                                logger.info(f"✅ Found {platform} link in channel: {final_url}")
                
                # If we found links, no need to try other URLs
                if links:
                    break
        
        except Exception as e:
            logger.error(f"❌ Channel links extraction error: {e}")
        
        return links
    
    def _identify_platform_from_url(self, url: str) -> Optional[str]:
        """
        Identify social media platform from URL
        
        Args:
            url: Social media URL
            
        Returns:
            Platform name or None
        """
        url_lower = url.lower()
        
        if 'instagram.com' in url_lower:
            return 'instagram'
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'spotify.com' in url_lower:
            return 'spotify'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'twitter'
        elif 'facebook.com' in url_lower:
            return 'facebook'
        elif url_lower.startswith('http') and not any(domain in url_lower for domain in ['youtube.com', 'youtu.be']):
            return 'website'
        
        return None
    
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