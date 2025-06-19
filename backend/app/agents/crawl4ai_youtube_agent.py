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
                'yt-formatted-string.ytd-channel-name',
                # Updated selectors for current YouTube structure
                'ytd-video-owner-renderer a',
                'ytd-channel-name-container a',
                '.ytd-video-owner-renderer yt-formatted-string',
                '#owner-text a',
                'a.yt-simple-endpoint[href*="/@"]',
                'a.yt-simple-endpoint[href*="/channel/"]',
                'span.ytd-channel-name yt-formatted-string'
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
    
    async def search_videos_with_session(self, query: str, max_results: int = 100, session_id: str = None) -> YouTubeSearchResult:
        """
        Search YouTube videos using persistent session for better infinite scrolling.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return  
            session_id: Optional session identifier for persistence
            
        Returns:
            YouTubeSearchResult with videos found
        """
        if not session_id:
            import uuid
            session_id = f"youtube_search_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"🔗 Starting session-based search: {session_id}")
        
        try:
            # Enhanced browser config for session
            browser_config = BrowserConfig(
                headless=True,
                viewport_width=1920,
                viewport_height=1080,
                user_agent=random.choice(self.user_agents),
                java_script_enabled=True,
                ignore_https_errors=True,
                extra_args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-web-security"
                ]
            )
            
            # Multi-step JavaScript interactions
            js_interactions = [
                {
                    "description": "Initial page load",
                    "js_code": """
                    // Wait for page to stabilize
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    console.log('🎬 YouTube page loaded');
                    """,
                    "wait_for": "css:ytd-app",
                    "delay": 2.0
                },
                {
                    "description": "Accept cookies if needed",
                    "js_code": """
                    // Handle cookie consent
                    const acceptButtons = document.querySelectorAll('[aria-label*="Accept"], [aria-label*="accept"], button[aria-label*="Accept"]');
                    acceptButtons.forEach(btn => {
                        if (btn.innerText.toLowerCase().includes('accept') || btn.innerText.toLowerCase().includes('agree')) {
                            btn.click();
                            console.log('✅ Accepted cookies');
                        }
                    });
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    """,
                    "wait_for": None,
                    "delay": 1.0
                },
                {
                    "description": "Advanced infinite scroll",
                    "js_code": self.get_advanced_infinite_scroll_js(target_videos=max_results),
                    "wait_for": "css:ytd-video-renderer",
                    "delay": 5.0
                }
            ]
            
            search_url = self._build_search_url(query, "all")
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                results = []
                
                for i, interaction in enumerate(js_interactions):
                    logger.info(f"🔄 Session step {i+1}: {interaction['description']}")
                    
                    # Create config for this interaction
                    config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        js_code=interaction["js_code"],
                        wait_for=interaction["wait_for"],
                        session_id=session_id,
                        page_timeout=45000 if i == len(js_interactions) - 1 else 20000,  # Longer timeout for scroll step
                        delay_before_return_html=interaction["delay"],
                        magic=True,
                        simulate_user=True,
                        verbose=True
                    )
                    
                    # Add delay between interactions
                    if i > 0:
                        await asyncio.sleep(interaction["delay"])
                    
                    # Execute crawl step
                    result = await crawler.arun(url=search_url, config=config)
                    
                    if not result.success:
                        logger.error(f"❌ Session step {i+1} failed: {result.error_message}")
                        if i == 0:  # If initial load fails, abort
                            break
                        continue
                    
                    results.append(result)
                    logger.info(f"✅ Session step {i+1} completed")
                
                # Extract videos from the final result
                if results:
                    final_result = results[-1]
                    videos = await self._extract_videos_from_html(final_result.html, max_results)
                    
                    logger.info(f"🎯 Session search found {len(videos)} videos")
                    return YouTubeSearchResult(
                        query=query,
                        videos=videos,
                        total_results=len(videos),
                        success=len(videos) > 0,
                        error_message=None if videos else "No videos extracted from session"
                    )
                else:
                    return YouTubeSearchResult(
                        query=query,
                        videos=[],
                        total_results=0,
                        success=False,
                        error_message="Session search failed - no successful steps"
                    )
                    
        except Exception as e:
            logger.error(f"❌ Session search error: {e}")
            return YouTubeSearchResult(
                query=query,
                videos=[],
                total_results=0,
                success=False,
                error_message=f"Session search exception: {str(e)}"
            )

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

    def get_advanced_infinite_scroll_js(self, target_videos: int = 100) -> str:
        """Generate advanced infinite scroll JavaScript with multiple strategies"""
        return f"""
        (async function() {{
            let previousHeight = 0;
            let currentHeight = document.body.scrollHeight;
            let scrollAttempts = 0;
            const maxAttempts = 30;
            let noNewContentCount = 0;
            const maxNoNewContent = 5;
            
            console.log('🚀 Starting advanced infinite scroll for {target_videos} videos');
            
            while (scrollAttempts < maxAttempts && noNewContentCount < maxNoNewContent) {{
                // Count current videos using multiple selectors
                const videoSelectors = [
                    'ytd-video-renderer',
                    'ytd-grid-video-renderer', 
                    'ytd-compact-video-renderer',
                    '[data-testid="video-renderer"]',
                    'div[class*="video-renderer"]'
                ];
                
                let videoCount = 0;
                for (const selector of videoSelectors) {{
                    const videos = document.querySelectorAll(selector);
                    if (videos.length > videoCount) {{
                        videoCount = videos.length;
                    }}
                }}
                
                console.log(`📊 Current videos found: ${{videoCount}}`);
                
                if (videoCount >= {target_videos}) {{
                    console.log('🎯 Target reached!');
                    break;
                }}
                
                // Strategy 1: Progressive scrolling with varying speeds
                const scrollStep = Math.floor(Math.random() * 500) + 300; // 300-800px
                window.scrollBy(0, scrollStep);
                await new Promise(resolve => setTimeout(resolve, 800 + Math.random() * 400));
                
                // Strategy 2: Scroll to bottom periodically
                if (scrollAttempts % 3 === 0) {{
                    window.scrollTo(0, document.body.scrollHeight);
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }}
                
                // Strategy 3: Element-based scrolling
                if (scrollAttempts % 5 === 0) {{
                    const videos = document.querySelectorAll('ytd-video-renderer, ytd-grid-video-renderer');
                    if (videos.length > 0) {{
                        const lastVideo = videos[videos.length - 1];
                        lastVideo.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }}
                }}
                
                // Strategy 4: Trigger scroll events manually
                if (scrollAttempts % 4 === 0) {{
                    ['scroll', 'wheel', 'touchmove'].forEach(eventType => {{
                        window.dispatchEvent(new Event(eventType, {{bubbles: true}}));
                        document.dispatchEvent(new Event(eventType, {{bubbles: true}}));
                    }});
                    await new Promise(resolve => setTimeout(resolve, 500));
                }}
                
                // Strategy 5: Focus on scroll containers
                if (scrollAttempts % 6 === 0) {{
                    const containers = [
                        'ytd-app',
                        'div#contents',
                        'div#primary',
                        '.ytd-section-list-renderer'
                    ];
                    
                    for (const containerSelector of containers) {{
                        const container = document.querySelector(containerSelector);
                        if (container) {{
                            container.scrollTop = container.scrollHeight;
                            await new Promise(resolve => setTimeout(resolve, 500));
                        }}
                    }}
                }}
                
                // Strategy 6: Hover and interact with elements to trigger lazy loading
                if (scrollAttempts % 7 === 0) {{
                    const elements = document.querySelectorAll('ytd-video-renderer, [data-lazy]');
                    for (let i = 0; i < Math.min(5, elements.length); i++) {{
                        const element = elements[i];
                        element.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}}));
                        element.dispatchEvent(new Event('focus', {{bubbles: true}}));
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }}
                }}
                
                // Check for height change
                await new Promise(resolve => setTimeout(resolve, 1500));
                previousHeight = currentHeight;
                currentHeight = document.body.scrollHeight;
                
                if (currentHeight === previousHeight) {{
                    noNewContentCount++;
                    console.log(`⚠️ No height change detected (${{noNewContentCount}}/${{maxNoNewContent}})`);
                    
                    // Try alternative scroll methods when stuck
                    const alternativeContainers = [
                        document.querySelector('ytd-app'),
                        document.querySelector('#primary'),
                        document.querySelector('#contents'),
                        document.body
                    ];
                    
                    for (const container of alternativeContainers) {{
                        if (container) {{
                            container.scrollTop = container.scrollHeight;
                            await new Promise(resolve => setTimeout(resolve, 800));
                        }}
                    }}
                    
                    // Trigger intersection observer manually
                    const observer = new IntersectionObserver((entries) => {{
                        entries.forEach(entry => {{
                            if (entry.isIntersecting) {{
                                entry.target.dispatchEvent(new Event('intersect'));
                            }}
                        }});
                    }});
                    
                    document.querySelectorAll('[data-lazy], ytd-video-renderer').forEach(el => {{
                        observer.observe(el);
                    }});
                    
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    observer.disconnect();
                }} else {{
                    noNewContentCount = 0;
                }}
                
                scrollAttempts++;
                
                // Random delay between attempts to appear more human
                const delay = 800 + Math.random() * 1200; // 800-2000ms
                await new Promise(resolve => setTimeout(resolve, delay));
            }}
            
            // Final count
            let finalVideoCount = 0;
            const videoSelectors = [
                'ytd-video-renderer',
                'ytd-grid-video-renderer', 
                'ytd-compact-video-renderer'
            ];
            
            for (const selector of videoSelectors) {{
                const videos = document.querySelectorAll(selector);
                if (videos.length > finalVideoCount) {{
                    finalVideoCount = videos.length;
                }}
            }}
            
            console.log(`✅ Infinite scroll complete: ${{finalVideoCount}} videos found after ${{scrollAttempts}} attempts`);
            window.__video_count = finalVideoCount;
            window.__scroll_complete = true;
        }})();
        """

    async def get_crawler_config(self, target_videos: int = 100) -> CrawlerRunConfig:
        """Create randomized crawler configuration with stealth features."""
        # Random locale/timezone
        locale_config = random.choice(self.locales)
        
        # Random geolocation
        geolocation = random.choice(self.geolocations)
        
        return CrawlerRunConfig(
            # Magic mode for automatic anti-bot handling
            magic=True,
            
            # Full page scanning for maximum video discovery
            scan_full_page=True,
            scroll_delay=0.2,  # 200ms between scrolls for optimal performance
            
            # Identity settings
            locale=locale_config["locale"],
            timezone_id=locale_config["timezone"],
            geolocation=geolocation,
            
            # Stealth features
            simulate_user=True,
            override_navigator=True,
            remove_overlay_elements=True,
            
            # Timing optimized for full page scanning
            delay_before_return_html=random.uniform(8.0, 12.0),  # More time for content loading
            
            # Wait strategies
            wait_until="domcontentloaded",  # More reliable than networkidle
            page_timeout=180000,  # Increased to 3 minutes for full page scanning
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
                page_timeout=30000,  # Increased for full page scanning
                delay_before_return_html=3.0,
                scan_full_page=True,   # Enable full page scrolling
                scroll_delay=0.2,      # 200ms between scrolls
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
        """Search using magic mode with advanced infinite scroll."""
        try:
            browser_config = await self.get_browser_config()
            crawler_config = await self.get_crawler_config(target_videos=max_results)
            
            # Ensure magic mode is enabled
            crawler_config.magic = True
            
            # Enable full page scanning with optimized scrolling
            crawler_config.scan_full_page = True
            crawler_config.scroll_delay = 0.2  # 200ms between scrolls
            
            # Use advanced infinite scroll JavaScript
            advanced_scroll_js = self.get_advanced_infinite_scroll_js(target_videos=max_results)
            crawler_config.js_code = advanced_scroll_js
            
            # Increase timeouts for infinite scroll
            crawler_config.page_timeout = 120000  # 2 minutes for full page scanning
            crawler_config.delay_before_return_html = 10.0  # More time for content to load
            
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
        """Extract video information from HTML using enhanced extractors."""
        videos = []
        
        try:
            # Use enhanced extractor first
            from enhanced_extractors import EnhancedYouTubeExtractor
            video_data_list = EnhancedYouTubeExtractor.extract_search_videos(html, max_results)
            
            # Convert to YouTubeVideo objects
            for video_data in video_data_list:
                try:
                    video = YouTubeVideo(
                        title=video_data.get("title", ""),
                        url=video_data.get("url", ""),
                        channel_name=video_data.get("channel_name", "Unknown"),
                        channel_url=video_data.get("channel_url", ""),
                        duration=video_data.get("duration", ""),
                        view_count=video_data.get("view_count", ""),
                        upload_date=video_data.get("upload_date", ""),
                        description=video_data.get("description", ""),
                        video_id=video_data.get("video_id", "")
                    )
                    
                    if video.title and video.url:
                        videos.append(video)
                        if len(videos) >= max_results:
                            break
                            
                except Exception as e:
                    logger.warning(f"Failed to create YouTubeVideo object: {e}")
                    continue
            
            logger.info(f"✅ Enhanced extraction found {len(videos)} videos")
            
            # Fallback to original method if enhanced extraction fails
            if len(videos) < 3:
                logger.info("🔄 Falling back to original extraction method")
                fallback_videos = await self._extract_videos_from_html_fallback(html, max_results, mobile)
                videos.extend(fallback_videos)
                
                # Remove duplicates by URL
                seen_urls = set()
                unique_videos = []
                for video in videos:
                    if video.url not in seen_urls:
                        seen_urls.add(video.url)
                        unique_videos.append(video)
                
                videos = unique_videos[:max_results]
            
        except Exception as e:
            logger.error(f"Error in enhanced video extraction: {e}")
            # Fallback to original method
            videos = await self._extract_videos_from_html_fallback(html, max_results, mobile)
        
        return videos

    async def _extract_videos_from_html_fallback(self, html: str, max_results: int, mobile: bool = False) -> List[YouTubeVideo]:
        """Fallback video extraction using original method."""
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
            
            # Extract channel name AND channel URL with more fallbacks
            channel_name = "Unknown"
            channel_url = None
            channel_id = None
            
            # Look for channel links first (to get URL and ID)
            channel_link_selectors = [
                'a[href*="/channel/"]',  # Direct channel ID links
                'a[href*="/@"]',         # Handle-based links
                'a[href*="/c/"]',        # Custom channel links
                'a[href*="/user/"]',     # User-based links
            ]
            
            for selector in channel_link_selectors:
                channel_elem = container.select_one(selector)
                if channel_elem:
                    href = channel_elem.get('href', '')
                    if href:
                        # Construct full URL
                        if href.startswith('/'):
                            channel_url = f"https://www.youtube.com{href}"
                        elif 'youtube.com' in href:
                            channel_url = href
                        
                        # Extract channel ID or handle
                        import re
                        if '/channel/' in href:
                            match = re.search(r'/channel/([^/?&]+)', href)
                            if match:
                                channel_id = match.group(1)
                        elif '/@' in href:
                            match = re.search(r'/@([^/?&]+)', href)
                            if match:
                                channel_id = f"@{match.group(1)}"
                        elif '/c/' in href:
                            match = re.search(r'/c/([^/?&]+)', href)
                            if match:
                                channel_id = match.group(1)
                        elif '/user/' in href:
                            match = re.search(r'/user/([^/?&]+)', href)
                            if match:
                                channel_id = match.group(1)
                        
                        # Get channel name from the link text
                        channel_text = channel_elem.get_text(strip=True)
                        if channel_text and len(channel_text) > 1:
                            channel_name = channel_text
                        break
            
            # Fallback: look for channel name in other selectors if not found
            if channel_name == "Unknown":
                channel_name_selectors = self.selectors['channel'] + [
                    '.ytd-channel-name',
                    '[data-testid*="channel"]',
                    'span[class*="channel"]',
                    # More aggressive selectors for current YouTube
                    'ytd-video-owner-renderer yt-formatted-string',
                    'ytd-channel-name yt-formatted-string',
                    '#owner-text yt-formatted-string',
                    'a[href*="/@"] yt-formatted-string',
                    'a[href*="/channel/"] yt-formatted-string',
                    '.ytd-video-meta-block a',
                    'span[dir="auto"]',  # Many channel names are in auto-direction spans
                ]
                
                for selector in channel_name_selectors:
                    channel_elem = container.select_one(selector)
                    if channel_elem:
                        channel_text = channel_elem.get_text(strip=True)
                        # More relaxed validation - just check it's not empty and not a common non-channel text
                        if (channel_text and len(channel_text) > 1 and 
                            channel_text.lower() not in ['views', 'view', 'subscribers', 'subscribe', 'ago', 'duration']):
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
            
            # Extract video ID for the video
            video_id = self._extract_video_id_from_url(url) if url else None
            
            video = YouTubeVideo(
                title=title,
                url=url,
                channel_name=channel_name,
                view_count=view_count,
                duration=duration,
                upload_date=upload_date,
                video_id=video_id,
                channel_url=channel_url,
                channel_id=channel_id
            )
            
            logger.debug(f"✅ Extracted video: {title[:50]}... from {channel_name}")
            return video
            
        except Exception as e:
            logger.warning(f"Error extracting video data: {e}")
            return None

    def _extract_video_id_from_url(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL with multiple patterns."""
        try:
            if not url:
                return None
                
            import re
            patterns = [
                r'watch\?v=([a-zA-Z0-9_-]{11})',  # Standard watch URLs
                r'youtu\.be/([a-zA-Z0-9_-]{11})', # Short URLs
                r'embed/([a-zA-Z0-9_-]{11})',     # Embed URLs
                r'/watch/([a-zA-Z0-9_-]{11})',    # Alternative watch format
                r'v=([a-zA-Z0-9_-]{11})',         # Simple v= parameter
                r'([a-zA-Z0-9_-]{11})',           # Last resort - 11 char string
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    # Validate it's actually 11 characters (YouTube video ID length)
                    if len(video_id) == 11:
                        return video_id
            
            logger.debug(f"Could not extract video ID from URL: {url}")
            return None
        except Exception as e:
            logger.debug(f"Error extracting video ID from URL {url}: {e}")
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
            
            # Use Crawl4AI's built-in infinite scroll feature with enhanced settings
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_until="domcontentloaded",  # Faster than networkidle
                page_timeout=300000,  # 5 minute timeout for extensive scrolling
                delay_before_return_html=10.0,  # More time after scrolling completes
                verbose=True,
                simulate_user=True,
                magic=True,
                # Enhanced infinite scroll support
                scan_full_page=True,  # Enables automatic infinite scrolling
                scroll_delay=0.2      # Optimized 200ms between scrolls
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
                
                # Extract all videos from the final HTML with higher multiplier for more results
                logger.info("🎬 Extracting videos from scrolled content...")
                all_videos = await self._extract_videos_from_html(result.html, target_videos * 20)  # Increased multiplier
                logger.info(f"📊 Successfully extracted {len(all_videos)} videos")
                
                # Remove duplicates using video_id and title
                unique_videos = []
                seen_ids = set()
                seen_titles = set()
                videos_without_id = 0
                duplicate_ids = 0
                duplicate_titles = 0
                
                for video in all_videos:
                    video_id = getattr(video, 'video_id', None) or self._extract_video_id_from_url(video.url)
                    
                    # Skip videos without valid ID
                    if not video_id:
                        videos_without_id += 1
                        continue
                    
                    # Skip duplicate IDs
                    if video_id in seen_ids:
                        duplicate_ids += 1
                        continue
                    
                    # Skip very similar titles (fuzzy deduplication)
                    title_lower = video.title.lower() if video.title else ""
                    if title_lower in seen_titles:
                        duplicate_titles += 1
                        continue
                    
                    # Add video_id as property if missing
                    if not hasattr(video, 'video_id'):
                        video.video_id = video_id
                    
                    unique_videos.append(video)
                    seen_ids.add(video_id)
                    seen_titles.add(title_lower)
                    
                    if len(unique_videos) >= target_videos:
                        break
                
                logger.info(f"🔍 Deduplication stats: {videos_without_id} without ID, {duplicate_ids} duplicate IDs, {duplicate_titles} duplicate titles")
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