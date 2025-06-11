"""
Crawl4AI YouTube Agent - Enhanced with Anti-Blocking Strategies
Uses Crawl4AI's browser automation to scrape YouTube search results
"""
import asyncio
import logging
import random
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
import time

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, GeolocationConfig
from crawl4ai.models import CrawlResult

from ..models.youtube_models import YouTubeVideo, YouTubeSearchResult

logger = logging.getLogger(__name__)

class Crawl4AIYouTubeAgent:
    """Enhanced YouTube agent with comprehensive anti-blocking strategies."""
    
    def __init__(self):
        """Initialize the Crawl4AI YouTube agent with anti-blocking features."""
        # Anti-bot user agents rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0"
        ]
        
        # Geolocation rotation for different regions
        self.geolocations = [
            GeolocationConfig(latitude=40.7128, longitude=-74.0060, accuracy=100),  # New York
            GeolocationConfig(latitude=34.0522, longitude=-118.2437, accuracy=100),  # Los Angeles
            GeolocationConfig(latitude=51.5074, longitude=-0.1278, accuracy=100),  # London
            GeolocationConfig(latitude=48.8566, longitude=2.3522, accuracy=100),  # Paris
            GeolocationConfig(latitude=35.6762, longitude=139.6503, accuracy=100),  # Tokyo
        ]
        
        # Language/locale rotation
        self.locales = [
            {"locale": "en-US", "timezone": "America/New_York"},
            {"locale": "en-GB", "timezone": "Europe/London"},
            {"locale": "fr-FR", "timezone": "Europe/Paris"},
            {"locale": "de-DE", "timezone": "Europe/Berlin"},
            {"locale": "ja-JP", "timezone": "Asia/Tokyo"}
        ]
        
        # Enhanced selectors with multiple fallbacks
        self.selectors = {
            'videos': [
                'ytd-video-renderer',
                'ytd-grid-video-renderer', 
                'ytd-compact-video-renderer',
                '[data-testid="video-renderer"]',
                '.ytd-video-renderer',
                'div[class*="video-renderer"]'
            ],
            'title': [
                '#video-title',
                'h3 a[href*="/watch"]',
                'a[aria-label*="by"]',
                '[data-testid="video-title"]',
                '.ytd-video-meta-block h3',
                'yt-formatted-string[aria-label]'
            ],
            'channel': [
                '#channel-name a',
                '.ytd-channel-name a',
                'a[href*="/channel/"]',
                'a[href*="/@"]',
                '[data-testid="channel-name"]',
                'yt-formatted-string.ytd-channel-name'
            ],
            'views': [
                '#metadata-line span:first-child',
                '.inline-metadata-item:first-child',
                '[data-testid="view-count"]',
                'span[aria-label*="views"]',
                '.ytd-video-meta-block span'
            ],
            'duration': [
                '.ytd-thumbnail-overlay-time-status-renderer span',
                '.badge-shape-wiz__text',
                '[data-testid="duration"]',
                'span.ytd-thumbnail-overlay-time-status-renderer'
            ],
            'upload_date': [
                '#metadata-line span:nth-child(2)',
                '.inline-metadata-item:nth-child(2)',
                '[data-testid="upload-date"]',
                'span[aria-label*="ago"]'
            ]
        }
        
        logger.info("✅ Enhanced Crawl4AI YouTube Agent initialized with anti-blocking features")

    async def get_browser_config(self) -> BrowserConfig:
        """Create randomized browser configuration with anti-detection features."""
        user_agent = random.choice(self.user_agents)
        
        # Random viewport sizes to mimic different devices
        viewports = [
            (1920, 1080), (1366, 768), (1440, 900), (1536, 864), (1280, 720)
        ]
        viewport = random.choice(viewports)
        
        return BrowserConfig(
            browser_type="chromium",
            headless=True,
            viewport_width=viewport[0],
            viewport_height=viewport[1],
            user_agent=user_agent,
            java_script_enabled=True,
            ignore_https_errors=True,
            # Anti-detection flags
            extra_args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=VizDisplayCompositor",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-images",  # Faster loading
                "--disable-javascript-harmony-shipping",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-ipc-flooding-protection",
                "--disable-client-side-phishing-detection",
                "--disable-default-apps",
                "--disable-hang-monitor",
                "--disable-popup-blocking",
                "--disable-prompt-on-repost",
                "--disable-sync",
                "--disable-translate",
                "--disable-web-security",
                "--metrics-recording-only",
                "--no-first-run",
                "--safebrowsing-disable-auto-update",
                "--enable-automation",
                "--password-store=basic",
                "--use-mock-keychain"
            ]
        )

    async def get_crawler_config(self) -> CrawlerRunConfig:
        """Create randomized crawler configuration with stealth features."""
        # Random locale/timezone
        locale_config = random.choice(self.locales)
        
        # Random geolocation
        geolocation = random.choice(self.geolocations)
        
        return CrawlerRunConfig(
            # Magic mode for automatic anti-bot handling
            magic=True,
            
            # Identity settings
            locale=locale_config["locale"],
            timezone_id=locale_config["timezone"],
            geolocation=geolocation,
            
            # Stealth features
            simulate_user=True,
            override_navigator=True,
            remove_overlay_elements=True,
            
            # Timing randomization
            delay_before_return_html=random.uniform(2.0, 5.0),
            scroll_delay=random.uniform(0.5, 1.5),
            
            # Wait strategies
            wait_until="domcontentloaded",  # More reliable than networkidle
            page_timeout=60000,  # Reduced timeout
            wait_for=None,  # Remove wait_for to avoid timeout issues
            
            # Content settings
            word_count_threshold=10,
            excluded_tags=["script", "style", "nav", "footer", "aside"],
            
            # Performance
            wait_for_images=False,
            
            # Debugging
            verbose=True,
            
            # Cache settings
            cache_mode=CacheMode.BYPASS
        )

    async def search_videos(self, query: str, max_results: int = 20, upload_date: str = "all") -> YouTubeSearchResult:
        """
        Search YouTube videos with advanced anti-blocking techniques.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            upload_date: Filter by upload date ("all", "hour", "today", "week", "month", "year")
        
        Returns:
            YouTubeSearchResult with videos found
        """
        videos = []
        success = False
        error_message = None
        
        # Multiple search strategies (ordered by speed and reliability)
        search_strategies = [
            self._search_with_basic_config,      # Fastest - start here
            self._search_with_magic_mode,        # Second fastest with scrolling
            self._search_with_extended_stealth,  # Slower but more comprehensive
            self._search_with_mobile_emulation   # Last resort
        ]
        
        for strategy_index, strategy in enumerate(search_strategies):
            logger.info(f"Attempting YouTube search with strategy {strategy_index + 1}: {strategy.__name__}")
            
            try:
                result = await strategy(query, max_results, upload_date)
                if result.success and result.videos:
                    return result
                else:
                    logger.warning(f"Strategy {strategy_index + 1} failed: {result.error_message}")
                    error_message = result.error_message
                    
            except Exception as e:
                logger.error(f"Strategy {strategy_index + 1} exception: {str(e)}")
                error_message = str(e)
                
            # Quick delay between strategies (reduced since methods are faster)
            await asyncio.sleep(random.uniform(1.0, 3.0))
        
        return YouTubeSearchResult(
            query=query,
            videos=videos,
            total_results=0,
            success=success,
            error_message=error_message or "All search strategies failed"
        )

    async def _search_with_basic_config(self, query: str, max_results: int, upload_date: str) -> YouTubeSearchResult:
        """Search using basic configuration without advanced features."""
        try:
            browser_config = BrowserConfig(
                browser_type="chromium",
                headless=True,
                viewport_width=1280,
                viewport_height=720,
                java_script_enabled=True,
                ignore_https_errors=True
            )
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_until="domcontentloaded",
                page_timeout=15000,  # Reduced from 30s
                delay_before_return_html=2.0,
                verbose=True
            )
            
            search_url = self._build_search_url(query, upload_date)
            logger.info(f"🔍 Basic config search URL: {search_url}")
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                await asyncio.sleep(random.uniform(0.5, 1.5))  # Faster
                
                logger.info("🌐 Starting basic config crawl...")
                result = await crawler.arun(url=search_url, config=crawler_config)
                
                if not result.success:
                    logger.error(f"❌ Basic config crawl failed: {result.error_message}")
                    return YouTubeSearchResult(
                        query=query, videos=[], total_results=0,
                        success=False, error_message=f"Basic config crawl failed: {result.error_message}"
                    )
                
                logger.info("🎬 Extracting videos from HTML...")
                videos = await self._extract_videos_from_html(result.html, max_results)
                
                logger.info(f"✅ Basic config found {len(videos)} videos")
                return YouTubeSearchResult(
                    query=query,
                    videos=videos,
                    total_results=len(videos),
                    success=len(videos) > 0,
                    error_message=None if videos else "No videos extracted from basic config"
                )
                
        except asyncio.TimeoutError:
            logger.error("⏰ Basic config timed out")
            return YouTubeSearchResult(
                query=query, videos=[], total_results=0,
                success=False, error_message="Basic config search timed out"
            )
        except Exception as e:
            logger.error(f"💥 Basic config exception: {str(e)}")
            return YouTubeSearchResult(
                query=query, videos=[], total_results=0,
                success=False, error_message=f"Basic config exception: {str(e)}"
            )

    async def _search_with_magic_mode(self, query: str, max_results: int, upload_date: str) -> YouTubeSearchResult:
        """Search using magic mode with full automation and scrolling - FAST VERSION."""
        try:
            browser_config = await self.get_browser_config()
            crawler_config = await self.get_crawler_config()
            
            # Ensure magic mode is enabled
            crawler_config.magic = True
            
            # Fast scrolling JavaScript
            fast_scroll_js = """
            (function() {
                console.log('Magic mode - starting fast scroll...');
                
                let scrollCount = 0;
                const maxScrolls = 2; // Even faster for magic mode
                
                function quickScroll() {
                    if (scrollCount < maxScrolls) {
                        console.log(`Magic scroll ${scrollCount + 1}/${maxScrolls}`);
                        window.scrollBy(0, 600);
                        scrollCount++;
                        setTimeout(quickScroll, 600); // 0.6s delays
                    } else {
                        console.log('Magic scrolling complete');
                    }
                }
                
                quickScroll();
            })();
            """
            
            crawler_config.js_code = fast_scroll_js
            crawler_config.delay_before_return_html = 5.0  # Much faster
            crawler_config.page_timeout = 15000  # 15 second timeout
            
            search_url = self._build_search_url(query, upload_date)
            logger.info(f"🔍 Magic mode search URL: {search_url}")
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                # Add random pre-search delay
                await asyncio.sleep(random.uniform(0.5, 1.5))  # Faster
                
                logger.info("🌐 Starting magic mode crawl...")
                result = await crawler.arun(url=search_url, config=crawler_config)
                
                if not result.success:
                    logger.error(f"❌ Magic mode crawl failed: {result.error_message}")
                    return YouTubeSearchResult(
                        query=query, videos=[], total_results=0, 
                        success=False, error_message=f"Magic mode crawl failed: {result.error_message}"
                    )
                
                logger.info("🎬 Extracting videos from HTML...")
                videos = await self._extract_videos_from_html(result.html, max_results)
                
                logger.info(f"✅ Magic mode found {len(videos)} videos")
                return YouTubeSearchResult(
                    query=query,
                    videos=videos,
                    total_results=len(videos),
                    success=len(videos) > 0,
                    error_message=None if videos else "No videos extracted from magic mode"
                )
                
        except asyncio.TimeoutError:
            logger.error("⏰ Magic mode timed out")
            return YouTubeSearchResult(
                query=query, videos=[], total_results=0,
                success=False, error_message="Magic mode search timed out"
            )
        except Exception as e:
            logger.error(f"💥 Magic mode exception: {str(e)}")
            return YouTubeSearchResult(
                query=query, videos=[], total_results=0,
                success=False, error_message=f"Magic mode exception: {str(e)}"
            )

    async def _search_with_extended_stealth(self, query: str, max_results: int, upload_date: str) -> YouTubeSearchResult:
        """Search with extended stealth features and interaction simulation - FAST VERSION."""
        try:
            browser_config = await self.get_browser_config()
            crawler_config = await self.get_crawler_config()
            
            # Enhanced stealth settings but faster
            crawler_config.simulate_user = True
            crawler_config.override_navigator = True
            crawler_config.magic = True
            crawler_config.scan_full_page = True
            
            # Simplified, faster JavaScript for scrolling
            fast_scroll_js = """
            (function() {
                console.log('Starting fast scroll...');
                
                let scrollCount = 0;
                const maxScrolls = 3; // Reduced from 8
                
                function fastScroll() {
                    if (scrollCount < maxScrolls) {
                        console.log(`Fast scroll ${scrollCount + 1}/${maxScrolls}`);
                        window.scrollBy(0, 800);
                        scrollCount++;
                        setTimeout(fastScroll, 800); // Much faster - 0.8s instead of 1.5-3.5s
                    } else {
                        console.log('Fast scrolling complete');
                    }
                }
                
                // Start immediately
                fastScroll();
            })();
            """
            
            crawler_config.js_code = fast_scroll_js
            crawler_config.delay_before_return_html = 8.0  # Reduced from 25 seconds
            crawler_config.page_timeout = 20000  # 20 second timeout instead of default
            
            search_url = self._build_search_url(query, upload_date)
            logger.info(f"🔍 Extended stealth search URL: {search_url}")
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                await asyncio.sleep(random.uniform(1.0, 2.0))  # Reduced delay
                
                logger.info("🌐 Starting extended stealth crawl...")
                result = await crawler.arun(url=search_url, config=crawler_config)
                
                if not result.success:
                    logger.error(f"❌ Extended stealth crawl failed: {result.error_message}")
                    return YouTubeSearchResult(
                        query=query, videos=[], total_results=0,
                        success=False, error_message=f"Extended stealth crawl failed: {result.error_message}"
                    )
                
                logger.info("🎬 Extracting videos from HTML...")
                videos = await self._extract_videos_from_html(result.html, max_results)
                
                logger.info(f"✅ Extended stealth found {len(videos)} videos")
                return YouTubeSearchResult(
                    query=query,
                    videos=videos,
                    total_results=len(videos),
                    success=len(videos) > 0,
                    error_message=None if videos else "No videos extracted from extended stealth"
                )
                
        except asyncio.TimeoutError:
            logger.error("⏰ Extended stealth timed out")
            return YouTubeSearchResult(
                query=query, videos=[], total_results=0,
                success=False, error_message="Extended stealth search timed out"
            )
        except Exception as e:
            logger.error(f"💥 Extended stealth exception: {str(e)}")
            return YouTubeSearchResult(
                query=query, videos=[], total_results=0,
                success=False, error_message=f"Extended stealth exception: {str(e)}"
            )

    async def _search_with_mobile_emulation(self, query: str, max_results: int, upload_date: str) -> YouTubeSearchResult:
        """Search using mobile emulation to avoid desktop bot detection."""
        # Mobile-specific browser config
        browser_config = BrowserConfig(
            browser_type="chromium",
            headless=True,
            viewport_width=375,  # iPhone viewport
            viewport_height=667,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            java_script_enabled=True,
            ignore_https_errors=True,
            extra_args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ]
        )
        
        # Mobile-specific crawler config
        crawler_config = CrawlerRunConfig(
            magic=True,
            simulate_user=True,
            remove_overlay_elements=True,
            delay_before_return_html=random.uniform(3.0, 6.0),
            wait_until="networkidle",
            page_timeout=90000,
            cache_mode=CacheMode.BYPASS,
            verbose=True
        )
        
        # Use mobile YouTube URL
        mobile_search_url = f"https://m.youtube.com/results?search_query={quote_plus(query)}"
        if upload_date != "all":
            date_map = {
                "hour": "EgIIAQ%253D%253D",
                "day": "CAISCAgCEAEYAXAB",      # Enhanced: Today + Sort by upload date + 4K + Under 4min
                "today": "CAISCAgCEAEYAXAB",    # Enhanced: Today + Sort by upload date + 4K + Under 4min
                "week": "EgIIAw%253D%253D", 
                "month": "EgIIBA%253D%253D",
                "year": "EgIIBQ%253D%253D"
            }
            if upload_date in date_map:
                mobile_search_url += f"&sp={date_map[upload_date]}"
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            await asyncio.sleep(random.uniform(1.5, 3.5))
            
            result = await crawler.arun(url=mobile_search_url, config=crawler_config)
            
            if not result.success:
                return YouTubeSearchResult(
                    query=query, videos=[], total_results=0,
                    success=False, error_message=f"Mobile emulation crawl failed: {result.error_message}"
                )
            
            videos = await self._extract_videos_from_html(result.html, max_results, mobile=True)
            
            return YouTubeSearchResult(
                query=query,
                videos=videos,
                total_results=len(videos),
                success=len(videos) > 0,
                error_message=None if videos else "No videos extracted from mobile emulation"
            )

    def _build_search_url(self, query: str, upload_date: str = "all") -> str:
        """Build YouTube search URL with enhanced filters for music discovery."""
        base_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        
        if upload_date != "all":
            # Enhanced YouTube search filter parameters for music discovery
            date_filters = {
                "hour": "EgIIAQ%253D%253D",
                "day": "CAISCAgCEAEYAXAB",      # Enhanced: Today + Sort by upload date + 4K + Under 4min
                "today": "CAISCAgCEAEYAXAB",    # Enhanced: Today + Sort by upload date + 4K + Under 4min  
                "week": "EgIIAw%253D%253D", 
                "month": "EgIIBA%253D%253D",
                "year": "EgIIBQ%253D%253D"
            }
            
            if upload_date in date_filters:
                base_url += f"&sp={date_filters[upload_date]}"
        
        # Add parameters for consistent English results
        base_url += "&gl=US&hl=en"
        
        return base_url

    async def _extract_videos_from_html(self, html: str, max_results: int, mobile: bool = False) -> List[YouTubeVideo]:
        """Extract video information from HTML using multiple selector strategies."""
        videos = []
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Different extraction strategies for mobile vs desktop
            if mobile:
                video_containers = self._find_mobile_video_containers(soup)
            else:
                video_containers = self._find_desktop_video_containers(soup)
            
            logger.info(f"Found {len(video_containers)} video containers")
            
            for container in video_containers[:max_results]:
                try:
                    video = await self._extract_video_from_container(container, mobile)
                    if video and video.title and video.url:
                        videos.append(video)
                        if len(videos) >= max_results:
                            break
                except Exception as e:
                    logger.warning(f"Failed to extract video from container: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(videos)} videos")
            
        except Exception as e:
            logger.error(f"Error extracting videos from HTML: {e}")
        
        return videos

    def _find_desktop_video_containers(self, soup) -> list:
        """Find video containers in desktop YouTube."""
        containers = []
        
        # Add more aggressive selectors to catch more videos
        additional_selectors = [
            'ytd-rich-item-renderer',  # Grid layout videos
            'ytd-video-renderer',      # List layout videos
            'ytd-compact-video-renderer',  # Compact videos
            '[data-testid*="video"]',  # Any data-testid with "video"
            'div[class*="ytd-video"]', # Any div with ytd-video class
            'div[class*="video-renderer"]',  # Generic video renderer
            'a[href*="/watch?v="]',    # Any link to watch URLs
            'div[class*="rich-item"]', # Rich item containers
            'div[class*="grid-video"]', # Grid video containers
            '.contents > div',         # Generic content containers
            'ytd-item-section-renderer div', # Item section contents
        ]
        
        all_selectors = self.selectors['videos'] + additional_selectors
        
        for selector in all_selectors:
            found = soup.select(selector)
            if found:
                containers.extend(found)
                logger.info(f"Found {len(found)} containers with selector: {selector}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_containers = []
        for container in containers:
            container_id = str(container)[:100]  # Use first 100 chars as ID
            if container_id not in seen:
                seen.add(container_id)
                unique_containers.append(container)
        
        logger.info(f"Total unique containers found: {len(unique_containers)}")
        return unique_containers

    def _find_mobile_video_containers(self, soup) -> list:
        """Find video containers in mobile YouTube."""
        mobile_selectors = [
            '.large-media-item',
            '.compact-media-item', 
            '.media-item-renderer',
            '[data-context-item-id]',
            'div[class*="video"]'
        ]
        
        containers = []
        for selector in mobile_selectors:
            found = soup.select(selector)
            if found:
                containers.extend(found)
        
        return containers

    async def _extract_video_from_container(self, container, mobile: bool = False) -> Optional[YouTubeVideo]:
        """Extract video information from a container element."""
        try:
            # Extract title with multiple fallback strategies
            title = None
            
            # More aggressive title extraction
            title_selectors = self.selectors['title'] + [
                'a[title]',                    # Any link with title
                'span[title]',                 # Any span with title
                'div[title]',                  # Any div with title
                'h3',                          # Any h3 tag
                '[aria-label]',                # Any element with aria-label
                'a[href*="/watch"]',           # Any watch link text
                '.ytd-video-meta-block h3 a',  # Video meta block titles
                'yt-formatted-string',         # YouTube formatted strings
            ]
            
            for selector in title_selectors:
                title_elem = container.select_one(selector)
                if title_elem:
                    title = (title_elem.get('title') or 
                            title_elem.get('aria-label') or 
                            title_elem.get_text(strip=True))
                    if title and len(title.strip()) > 5:  # Basic validation
                        title = title.strip()
                        break
            
            # If no title found, try to find any text that looks like a title
            if not title:
                text_elements = container.find_all(text=True)
                for text in text_elements:
                    text = text.strip()
                    if len(text) > 10 and text not in ['', ' ', '\n']:
                        title = text
                        break
            
            if not title or len(title.strip()) < 3:
                return None
            
            # Extract URL with more aggressive search
            url = None
            
            # Search for URLs in various attributes and elements
            url_selectors = [
                'a[href*="/watch"]',
                'a[href*="youtube.com/watch"]',
                '[data-href*="/watch"]',
                '[href*="/watch"]',
            ]
            
            for selector in url_selectors:
                link_elem = container.select_one(selector)
                if link_elem:
                    href = link_elem.get('href') or link_elem.get('data-href')
                    if href:
                        if href.startswith('/'):
                            url = f"https://www.youtube.com{href}"
                        elif 'youtube.com' in href:
                            url = href
                        else:
                            url = f"https://www.youtube.com{href}"
                        break
            
            # Fallback: look for video ID in any data attributes
            if not url:
                for attr_name, attr_value in container.attrs.items():
                    if 'video' in attr_name.lower() and len(str(attr_value)) == 11:
                        url = f"https://www.youtube.com/watch?v={attr_value}"
                        break
            
            # If still no URL, try to construct from title or other clues
            if not url:
                # Look for any 11-character strings that could be video IDs
                all_text = str(container)
                import re
                video_id_pattern = r'[a-zA-Z0-9_-]{11}'
                matches = re.findall(video_id_pattern, all_text)
                for match in matches:
                    if 'watch?v=' in all_text or '/watch/' in all_text:
                        url = f"https://www.youtube.com/watch?v={match}"
                        break
            
            if not url:
                logger.debug(f"No URL found for title: {title}")
                return None
            
            # Extract channel name with more fallbacks
            channel_name = "Unknown"
            channel_selectors = self.selectors['channel'] + [
                'a[href*="/channel/"]',
                'a[href*="/@"]',
                '.ytd-channel-name',
                '[data-testid*="channel"]',
                'span[class*="channel"]',
            ]
            
            for selector in channel_selectors:
                channel_elem = container.select_one(selector)
                if channel_elem:
                    channel_text = channel_elem.get_text(strip=True)
                    if channel_text and len(channel_text) > 1:
                        channel_name = channel_text
                        break
            
            # Extract view count (optional)
            view_count = "Unknown"
            for selector in self.selectors['views']:
                views_elem = container.select_one(selector)
                if views_elem:
                    view_text = views_elem.get_text(strip=True)
                    if view_text and ('view' in view_text.lower() or any(c.isdigit() for c in view_text)):
                        view_count = view_text
                        break
            
            # Extract duration (optional)
            duration = "Unknown"
            for selector in self.selectors['duration']:
                duration_elem = container.select_one(selector)
                if duration_elem:
                    duration_text = duration_elem.get_text(strip=True)
                    if duration_text and ':' in duration_text:
                        duration = duration_text
                        break
            
            # Extract upload date (optional)
            upload_date = "Unknown"
            for selector in self.selectors['upload_date']:
                date_elem = container.select_one(selector)
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    if date_text and 'ago' in date_text.lower():
                        upload_date = date_text
                        break
            
            video = YouTubeVideo(
                title=title,
                url=url,
                channel_name=channel_name,
                view_count=view_count,
                duration=duration,
                upload_date=upload_date
            )
            
            logger.debug(f"✅ Extracted video: {title[:50]}... from {channel_name}")
            return video
            
        except Exception as e:
            logger.warning(f"Error extracting video data: {e}")
            return None

    def get_cost_estimate(self, expected_videos: int) -> float:
        """Estimate costs for video discovery operations."""
        # Crawl4AI doesn't have direct API costs, just estimate infrastructure
        return 0.0  # Free for now, could add server/bandwidth costs later 

    async def search_videos_with_infinite_scroll(
        self, 
        query: str, 
        target_videos: int = 100, 
        upload_date: str = "day"
    ) -> YouTubeSearchResult:
        """
        Single search with infinite scrolling until target number of videos found.
        Uses a single browser session with aggressive JavaScript scrolling.
        """
        try:
            browser_config = await self.get_browser_config()
            search_url = self._build_search_url(query, upload_date)
            
            logger.info(f"🔍 Starting infinite scroll search: {search_url}")
            logger.info(f"🎯 Target: {target_videos} videos")
            
            # Single session with aggressive scrolling JavaScript
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_until="networkidle",
                page_timeout=180000,  # 3 minute timeout for aggressive scrolling
                delay_before_return_html=15.0,  # Wait 15 seconds for all scrolling to complete
                verbose=True,
                simulate_user=True,
                magic=True,
                js_code=f"""
                (async function() {{
                    console.log('Starting aggressive infinite scroll for YouTube...');
                    
                    const targetVideos = {target_videos};
                    let scrollAttempts = 0;
                    const maxScrollAttempts = 20;
                    let noNewContentCount = 0;
                    const maxNoNewContent = 3;
                    
                    function getVideoCount() {{
                        // Try multiple selectors to find videos
                        const selectors = [
                            'ytd-video-renderer',
                            'ytd-rich-item-renderer', 
                            'ytd-compact-video-renderer',
                            'div[class*="ytd-video"]',
                            'div[class*="video-renderer"]'
                        ];
                        
                        let maxCount = 0;
                        selectors.forEach(selector => {{
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > maxCount) {{
                                maxCount = elements.length;
                            }}
                        }});
                        
                        return maxCount;
                    }}
                    
                    function performAggresiveScroll() {{
                        return new Promise(resolve => {{
                            const startCount = getVideoCount();
                            console.log(`Starting scroll with ${{startCount}} videos`);
                            
                            // Multiple scroll techniques
                            const viewportHeight = window.innerHeight;
                            const documentHeight = document.documentElement.scrollHeight;
                            
                            // Technique 1: Large scroll down
                            window.scrollBy({{
                                top: viewportHeight * 3,
                                behavior: 'smooth'
                            }});
                            
                            setTimeout(() => {{
                                // Technique 2: Scroll to absolute bottom
                                window.scrollTo({{
                                    top: document.documentElement.scrollHeight,
                                    behavior: 'smooth'
                                }});
                            }}, 1500);
                            
                            setTimeout(() => {{
                                // Technique 3: Scroll back up a bit
                                window.scrollBy({{
                                    top: -viewportHeight,
                                    behavior: 'smooth'
                                }});
                            }}, 3000);
                            
                            setTimeout(() => {{
                                // Technique 4: Trigger loading by clicking/hovering
                                const videos = document.querySelectorAll('ytd-video-renderer, ytd-rich-item-renderer');
                                videos.forEach((video, index) => {{
                                    if (index < 20) {{
                                        // Trigger hover events to load metadata
                                        video.dispatchEvent(new MouseEvent('mouseenter', {{ bubbles: true }}));
                                        video.dispatchEvent(new MouseEvent('mouseover', {{ bubbles: true }}));
                                    }}
                                }});
                                
                                // Technique 5: Scroll to trigger more loading
                                window.scrollTo({{
                                    top: document.documentElement.scrollHeight * 0.8,
                                    behavior: 'smooth'
                                }});
                            }}, 4500);
                            
                            setTimeout(() => {{
                                const endCount = getVideoCount();
                                const newVideos = endCount - startCount;
                                
                                console.log(`Scroll complete: ${{startCount}} -> ${{endCount}} videos (+${{newVideos}})`);
                                
                                resolve({{
                                    newVideos: newVideos,
                                    totalVideos: endCount
                                }});
                            }}, 6000);
                        }});
                    }}
                    
                    // Main scrolling loop
                    while (scrollAttempts < maxScrollAttempts) {{
                        scrollAttempts++;
                        console.log(`=== SCROLL ATTEMPT ${{scrollAttempts}}/${{maxScrollAttempts}} ===`);
                        
                        const scrollResult = await performAggresiveScroll();
                        
                        if (scrollResult.newVideos === 0) {{
                            noNewContentCount++;
                            console.log(`No new content found (attempt ${{noNewContentCount}}/${{maxNoNewContent}})`);
                            
                            if (noNewContentCount >= maxNoNewContent) {{
                                console.log('STOPPING - No new content after multiple attempts');
                                break;
                            }}
                        }} else {{
                            noNewContentCount = 0;
                            console.log(`SUCCESS: Found ${{scrollResult.newVideos}} new videos!`);
                        }}
                        
                        if (scrollResult.totalVideos >= targetVideos) {{
                            console.log(`TARGET REACHED! Found ${{scrollResult.totalVideos}} videos`);
                            break;
                        }}
                        
                        // Wait between scroll attempts
                        await new Promise(resolve => setTimeout(resolve, 2000));
                    }}
                    
                    const finalCount = getVideoCount();
                    console.log(`INFINITE SCROLL COMPLETE! Found ${{finalCount}} total videos after ${{scrollAttempts}} attempts`);
                    
                    // Mark completion in page
                    window.scrollingComplete = true;
                    window.finalVideoCount = finalCount;
                }})();
                """
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                logger.info("🌐 Executing single-session infinite scroll...")
                result = await crawler.arun(url=search_url, config=crawler_config)
                
                if not result.success:
                    logger.error(f"❌ Infinite scroll failed: {result.error_message}")
                    return YouTubeSearchResult(
                        query=query, videos=[], total_results=0,
                        success=False, error_message=f"Infinite scroll failed: {result.error_message}"
                    )
                
                # Extract all videos from the final HTML
                logger.info("🎬 Extracting videos from scrolled content...")
                all_videos = await self._extract_videos_from_html(result.html, target_videos * 10)
                
                # Remove duplicates
                unique_videos = []
                seen_ids = set()
                for video in all_videos:
                    if video.video_id not in seen_ids:
                        unique_videos.append(video)
                        seen_ids.add(video.video_id)
                        if len(unique_videos) >= target_videos:
                            break
                
                logger.info(f"🏁 Infinite scroll complete: {len(unique_videos)} unique videos found")
                return YouTubeSearchResult(
                    query=query,
                    videos=unique_videos,
                    total_results=len(unique_videos),
                    success=len(unique_videos) > 0,
                    error_message=None if unique_videos else "No videos found with infinite scroll"
                )
                
        except asyncio.TimeoutError:
            logger.error("⏰ Infinite scroll search timed out")
            return YouTubeSearchResult(
                query=query, videos=[], total_results=0,
                success=False, error_message="Infinite scroll search timed out"
            )
        except Exception as e:
            logger.error(f"💥 Infinite scroll exception: {str(e)}")
            return YouTubeSearchResult(
                query=query, videos=[], total_results=0,
                success=False, error_message=f"Infinite scroll exception: {str(e)}"
            ) 