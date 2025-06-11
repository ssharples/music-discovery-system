"""
Crawl4AI YouTube Agent - Enhanced with Anti-Blocking Strategies
Uses Crawl4AI's browser automation to scrape YouTube search results
"""
import asyncio
import logging
import random
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus

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
        
        # Multiple search strategies (ordered by scrolling capability for discovery)
        search_strategies = [
            self._search_with_extended_stealth,  # Start with best scrolling
            self._search_with_magic_mode,        # Backup scrolling
            self._search_with_basic_config,      # Fallback no-scroll
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
                
            # Random delay between strategies
            await asyncio.sleep(random.uniform(3.0, 8.0))
        
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
                page_timeout=30000,
                delay_before_return_html=2.0,
                verbose=True
            )
            
            search_url = self._build_search_url(query, upload_date)
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
                result = await crawler.arun(url=search_url, config=crawler_config)
                
                if not result.success:
                    return YouTubeSearchResult(
                        query=query, videos=[], total_results=0,
                        success=False, error_message=f"Basic config crawl failed: {result.error_message}"
                    )
                
                videos = await self._extract_videos_from_html(result.html, max_results)
                
                return YouTubeSearchResult(
                    query=query,
                    videos=videos,
                    total_results=len(videos),
                    success=len(videos) > 0,
                    error_message=None if videos else "No videos extracted from basic config"
                )
                
        except Exception as e:
            return YouTubeSearchResult(
                query=query, videos=[], total_results=0,
                success=False, error_message=f"Basic config exception: {str(e)}"
            )

    async def _search_with_magic_mode(self, query: str, max_results: int, upload_date: str) -> YouTubeSearchResult:
        """Search using magic mode with full automation and scrolling."""
        browser_config = await self.get_browser_config()
        crawler_config = await self.get_crawler_config()
        
        # Ensure magic mode is enabled
        crawler_config.magic = True
        
        # Add JavaScript to scroll and load more videos
        scroll_and_extract_js = """
        (function() {
            console.log('Starting scroll and extraction...');
            
            // Function to scroll page and wait for content to load
            async function scrollAndWait() {
                return new Promise((resolve) => {
                    let scrollCount = 0;
                    const maxScrolls = 5;
                    const scrollInterval = 2000; // 2 seconds between scrolls
                    
                    function performScroll() {
                        if (scrollCount < maxScrolls) {
                            console.log(`Scroll ${scrollCount + 1}/${maxScrolls}`);
                            
                            // Scroll to bottom
                            window.scrollTo(0, document.body.scrollHeight);
                            
                            scrollCount++;
                            setTimeout(performScroll, scrollInterval);
                        } else {
                            console.log('Scrolling complete, waiting for final load...');
                            setTimeout(resolve, 3000); // Wait 3 seconds after final scroll
                        }
                    }
                    
                    performScroll();
                });
            }
            
            // Start scrolling process
            scrollAndWait().then(() => {
                console.log('Scroll and extraction complete');
            });
        })();
        """
        
        crawler_config.js_code = scroll_and_extract_js
        crawler_config.delay_before_return_html = 15.0  # Extended delay for scrolling
        
        search_url = self._build_search_url(query, upload_date)
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            # Add random pre-search delay
            await asyncio.sleep(random.uniform(1.0, 3.0))
            
            result = await crawler.arun(url=search_url, config=crawler_config)
            
            if not result.success:
                return YouTubeSearchResult(
                    query=query, videos=[], total_results=0, 
                    success=False, error_message=f"Magic mode crawl failed: {result.error_message}"
                )
            
            videos = await self._extract_videos_from_html(result.html, max_results)
            
            return YouTubeSearchResult(
                query=query,
                videos=videos,
                total_results=len(videos),
                success=len(videos) > 0,
                error_message=None if videos else "No videos extracted from magic mode"
            )

    async def _search_with_extended_stealth(self, query: str, max_results: int, upload_date: str) -> YouTubeSearchResult:
        """Search with extended stealth features and interaction simulation."""
        browser_config = await self.get_browser_config()
        crawler_config = await self.get_crawler_config()
        
        # Enhanced stealth settings
        crawler_config.simulate_user = True
        crawler_config.override_navigator = True
        crawler_config.magic = True
        crawler_config.scan_full_page = True
        
        # Enhanced JavaScript for human-like behavior and aggressive scrolling
        human_behavior_js = """
        (function() {
            console.log('Starting enhanced human behavior simulation...');
            
            // Simulate human-like behavior
            var delay = function(ms) { 
                return new Promise(function(resolve) { 
                    setTimeout(resolve, ms); 
                }); 
            };
            
            // Random mouse movements
            var simulateMouseMovement = function() {
                for (let i = 0; i < 3; i++) {
                    setTimeout(() => {
                        var event = new MouseEvent('mousemove', {
                            clientX: Math.random() * window.innerWidth,
                            clientY: Math.random() * window.innerHeight
                        });
                        document.dispatchEvent(event);
                    }, i * 500);
                }
            };
            
            // Enhanced scroll behavior to load more videos
            var simulateEnhancedScroll = function() {
                return new Promise(function(resolve) {
                    let scrollAttempts = 0;
                    const maxScrollAttempts = 8; // More scrolls for more videos
                    
                    var performScroll = function() {
                        if (scrollAttempts < maxScrollAttempts) {
                            console.log(`Enhanced scroll ${scrollAttempts + 1}/${maxScrollAttempts}`);
                            
                            // Scroll in increments to simulate human behavior
                            const scrollHeight = document.body.scrollHeight;
                            const currentScroll = window.pageYOffset;
                            const scrollAmount = Math.min(500 + Math.random() * 300, scrollHeight - currentScroll);
                            
                            window.scrollBy(0, scrollAmount);
                            
                            // Simulate pause as human would do
                            setTimeout(() => {
                                scrollAttempts++;
                                performScroll();
                            }, Math.random() * 2000 + 1500); // 1.5-3.5 second delays
                        } else {
                            console.log('Enhanced scrolling complete, final wait...');
                            setTimeout(resolve, 4000); // Wait 4 seconds after final scroll
                        }
                    };
                    
                    performScroll();
                });
            };
            
            // Execute enhanced human simulation
            delay(Math.random() * 2000 + 1000).then(function() {
                simulateMouseMovement();
                return delay(Math.random() * 1000 + 500);
            }).then(function() {
                return simulateEnhancedScroll();
            }).then(function() {
                console.log('All human behavior simulation complete');
                return delay(Math.random() * 2000 + 1000);
            });
        })();
        """
        
        crawler_config.js_code = human_behavior_js
        crawler_config.delay_before_return_html = 25.0  # Extended delay for enhanced scrolling
        
        search_url = self._build_search_url(query, upload_date)
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            result = await crawler.arun(url=search_url, config=crawler_config)
            
            if not result.success:
                return YouTubeSearchResult(
                    query=query, videos=[], total_results=0,
                    success=False, error_message=f"Extended stealth crawl failed: {result.error_message}"
                )
            
            videos = await self._extract_videos_from_html(result.html, max_results)
            
            return YouTubeSearchResult(
                query=query,
                videos=videos,
                total_results=len(videos),
                success=len(videos) > 0,
                error_message=None if videos else "No videos extracted from extended stealth"
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
                "day": "EgIIAg%253D%253D",      # Today's uploads
                "today": "EgIIAg%253D%253D",    # Alias for day
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
        """Build YouTube search URL with filters."""
        base_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        
        if upload_date != "all":
            # YouTube search filter parameters
            date_filters = {
                "hour": "EgIIAQ%253D%253D",
                "day": "EgIIAg%253D%253D",      # Today's uploads
                "today": "EgIIAg%253D%253D",    # Alias for day
                "week": "EgIIAw%253D%253D", 
                "month": "EgIIBA%253D%253D",
                "year": "EgIIBQ%253D%253D"
            }
            if upload_date in date_filters:
                base_url += f"&sp={date_filters[upload_date]}"
        
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