"""
Enhanced Crawl4AI Enrichment Agent with LLM Content Filtering
Uses advanced Crawl4AI features including LLM-based content filtering and extraction
"""
import asyncio
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

# Optional imports for LLM features (may not be available in all Crawl4AI versions)
try:
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
    from crawl4ai.content_filter import LLMContentFilter
    from crawl4ai.llm_config import LLMConfig
    from crawl4ai.markdown_generator import DefaultMarkdownGenerator
    LLM_FEATURES_AVAILABLE = True
except ImportError:
    # Fallback for older Crawl4AI versions
    LLMExtractionStrategy = None
    LLMContentFilter = None
    LLMConfig = None
    DefaultMarkdownGenerator = None
    LLM_FEATURES_AVAILABLE = False
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider

from app.models.artist import ArtistProfile, EnrichedArtistData
from app.core.config import settings
from app.agents.ai_data_cleaner import get_ai_cleaner
from app.clients.spotify_client import get_spotify_client

logger = logging.getLogger(__name__)


class Crawl4AIEnrichmentAgent:
    """Enhanced enrichment agent with LLM content filtering and advanced Crawl4AI features"""
    
    def __init__(self):
        """Initialize the Crawl4AI enrichment agent with enhanced capabilities"""
        logger.info("🚀 Initializing Crawl4AI Enrichment Agent...")
        
        # Load settings first to ensure environment variables are available
        from app.core.config import settings
        
        # Browser configuration for Crawl4AI with enhanced anti-detection
        self.browser_config = BrowserConfig(
            headless=settings.CRAWL4AI_HEADLESS,
            viewport_width=settings.CRAWL4AI_VIEWPORT_WIDTH,
            viewport_height=settings.CRAWL4AI_VIEWPORT_HEIGHT,
            user_agent_mode="random",
            extra_args=[
                "--no-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=VizDisplayCompositor",
                "--disable-web-security",
                "--disable-features=TranslateUI"
            ]
        )
        
        # Initialize AI cleaner
        self.ai_cleaner = None
        try:
            if settings.DEEPSEEK_API_KEY:
                from app.agents.ai_data_cleaner import AIDataCleaner
                self.ai_cleaner = AIDataCleaner()  # No model parameter needed
                logger.info("✅ AI data cleaner initialized with DeepSeek")
            else:
                logger.warning("⚠️ DEEPSEEK_API_KEY not found - AI cleaning disabled")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize AI cleaner: {e}")
            self.ai_cleaner = None
        
        # Initialize Spotify API client
        self.spotify_client = get_spotify_client()
        if settings.is_spotify_configured():
            logger.info("✅ Spotify API client initialized")
        else:
            logger.warning("⚠️ Spotify API not configured - avatar and genre enrichment disabled")
        
        # Initialize session storage for persistent login states
        self.session_storage = {}
        
        logger.info("✅ Crawl4AI Enrichment Agent initialized")
    
    async def create_spotify_content_filter(self):
        """Create LLM-based content filter for Spotify pages"""
        if not LLM_FEATURES_AVAILABLE or not self.llm_config:
            return None
        
        return LLMContentFilter(
            llm_config=self.llm_config,
            instruction="""
            Extract only the following from Spotify artist pages:
            - Monthly listener count (numbers)
            - Artist biography/description text
            - Top cities/location data
            - Social media links (Instagram, Twitter, Facebook, YouTube)
            - Genre information
            - Top tracks/songs list
            
            Exclude:
            - Navigation menus
            - Cookie notices and privacy banners
            - Advertising content
            - Unrelated recommendations
            - User interface elements
            - JavaScript/CSS code
            """,
            chunk_token_threshold=500,
            verbose=True
        )
    
    async def create_instagram_content_filter(self):
        """Create LLM-based content filter for Instagram pages"""
        if not LLM_FEATURES_AVAILABLE or not self.llm_config:
            return None
            
        return LLMContentFilter(
            llm_config=self.llm_config,
            instruction="""
            Extract only the following from Instagram profile pages:
            - Follower count numbers
            - Following count numbers
            - Posts count numbers
            - Biography/bio text
            - Username/handle
            - Verification status
            
            Exclude:
            - Stories and posts content
            - Comments and user interactions
            - Navigation elements
            - Advertising content
            - Cookie notices
            - Login prompts
            """,
            chunk_token_threshold=300,
            verbose=True
        )
    
    async def create_tiktok_content_filter(self):
        """Create LLM-based content filter for TikTok pages"""
        if not LLM_FEATURES_AVAILABLE or not self.llm_config:
            return None
            
        return LLMContentFilter(
            llm_config=self.llm_config,
            instruction="""
            Extract only the following from TikTok profile pages:
            - Follower count numbers
            - Following count numbers
            - Likes count numbers
            - Biography/bio text
            - Username/handle
            - Verification status
            
            Exclude:
            - Video content and thumbnails
            - Comments and interactions
            - Navigation elements
            - For You page content
            - Advertising content
            - Download prompts
            """,
            chunk_token_threshold=300,
            verbose=True
        )
    
    async def create_lyrics_content_filter(self):
        """Create LLM-based content filter for lyrics pages"""
        if not LLM_FEATURES_AVAILABLE or not self.llm_config:
            return None
            
        return LLMContentFilter(
            llm_config=self.llm_config,
            instruction="""
            Extract only the following from lyrics pages:
            - Song lyrics text (verse and chorus content)
            - Song title
            - Artist name
            - Album information
            
            Exclude:
            - Advertisements
            - User comments and reviews
            - Navigation menus
            - Related songs sections
            - Social sharing buttons
            - Video player interfaces
            """,
            chunk_token_threshold=800,
            verbose=True
        )
    
    async def enrich_artist(self, artist_profile: ArtistProfile) -> EnrichedArtistData:
        """
        Enrich artist profile with data from multiple platforms
        
        Args:
            artist_profile: Basic artist profile with name and optional social links
            
        Returns:
            Enriched artist data with all platform information
        """
        logger.info(f"🎯 Enriching artist: {artist_profile.name}")
        
        # Create enriched data using the correct model structure
        enriched_data = EnrichedArtistData(
            profile=artist_profile,
            videos=[],
            lyric_analyses=[],
            enrichment_score=0.0,
            discovery_metadata={"enrichment_timestamp": datetime.utcnow().isoformat()}
        )
        
        # Parallel enrichment tasks
        tasks = []
        
        # Social media enrichment using ONLY provided links (no searching)
        # This ensures accuracy since we only process artists with confirmed social links
        instagram_url = None
        tiktok_url = None
        spotify_url = None
        
        if hasattr(artist_profile, 'social_links') and artist_profile.social_links:
            instagram_url = artist_profile.social_links.get('instagram')
            tiktok_url = artist_profile.social_links.get('tiktok')
            spotify_url = artist_profile.social_links.get('spotify')
            
            if instagram_url:
                logger.info(f"📸 Using provided Instagram link: {instagram_url}")
                tasks.append(self._enrich_instagram(instagram_url, enriched_data))
            
            if tiktok_url:
                logger.info(f"🎭 Using provided TikTok link: {tiktok_url}")
                tasks.append(self._enrich_tiktok(tiktok_url, enriched_data))
            
            # If we have a direct Spotify link, use it instead of searching
            if spotify_url:
                logger.info(f"🎵 Using provided Spotify link: {spotify_url}")
                # Create temporary profile with Spotify URL for direct enrichment
                temp_profile = ArtistProfile(
                    name=artist_profile.name,
                    spotify_url=spotify_url
                )
                tasks.append(self._enrich_spotify(temp_profile, enriched_data))
            else:
                # Only search Spotify if no direct link provided
                logger.info(f"🔍 No direct Spotify link, will search by artist name")
                tasks.append(self._search_and_enrich_spotify(artist_profile.name, enriched_data))
        else:
            logger.info(f"🔍 No direct social links available for {artist_profile.name}, using search-based enrichment")
            # Search-based enrichment (normal workflow for some artists)
            tasks.append(self._search_and_enrich_spotify(artist_profile.name, enriched_data))
        
        # Always add Spotify API enrichment for avatar and genres
        if settings.is_spotify_configured():
            logger.info(f"🎵 Adding Spotify API enrichment for avatar and genres")
            tasks.append(self._enrich_spotify_api(artist_profile.name, enriched_data))
        
        logger.info(f"🚀 Running {len(tasks)} enrichment tasks in parallel")
        
        # Run all enrichments in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        successful_tasks = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"✅ Completed {successful_tasks}/{len(tasks)} enrichment tasks successfully")
        
        # Calculate enrichment score and update profile
        enriched_data.enrichment_score = self._calculate_enrichment_score(enriched_data)
        enriched_data.profile.enrichment_score = enriched_data.enrichment_score
        
        logger.info(f"✅ Enrichment complete for {artist_profile.name} (score: {enriched_data.enrichment_score})")
        return enriched_data
    
    async def _enrich_spotify(self, artist_profile: ArtistProfile, enriched_data: EnrichedArtistData):
        """Enrich with comprehensive Spotify data including top tracks with play counts, monthly listeners, top city, biography, and social links"""
        try:
            spotify_url = artist_profile.spotify_url
            if not spotify_url and artist_profile.spotify_id:
                spotify_url = f"https://open.spotify.com/artist/{artist_profile.spotify_id}"
            
            if not spotify_url:
                logger.warning("⚠️ No Spotify URL available for enrichment")
                return
                
            logger.info(f"🎵 Enriching comprehensive Spotify data: {spotify_url}")
            
            # Create LLM content filter for Spotify (if available)
            content_filter = await self.create_spotify_content_filter()
            
            # Create markdown generator with LLM filter (if available)
            markdown_generator = None
            if content_filter and DefaultMarkdownGenerator:
                markdown_generator = DefaultMarkdownGenerator(
                    content_filter=content_filter,
                    options={"ignore_links": False}
                )
            
            # Enhanced crawler config for comprehensive data extraction
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_until="domcontentloaded",
                page_timeout=25000,  # Longer timeout for comprehensive extraction
                delay_before_return_html=6.0,  # More time for dynamic content
                js_code="""
                // Comprehensive Spotify content loading
                console.log('Starting comprehensive Spotify data extraction...');
                
                // Wait for initial content
                await new Promise(resolve => setTimeout(resolve, 3000));
                
                // Multiple scroll attempts to load all content
                for (let i = 0; i < 3; i++) {
                    window.scrollTo(0, document.body.scrollHeight / 3 * (i + 1));
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
                
                // Try to expand track lists and show more content
                const expandButtons = document.querySelectorAll([
                    '[data-testid*="show"]',
                    '.show-all',
                    'button[class*="show"]',
                    '[aria-label*="Show"]',
                    '[data-testid="show-all-button"]',
                    'button[contains(@class, "more")]'
                ].join(', '));
                
                for (let button of expandButtons) {
                    try {
                        if (button.textContent.toLowerCase().includes('show') || 
                            button.textContent.toLowerCase().includes('more') ||
                            button.getAttribute('aria-label')?.toLowerCase().includes('show')) {
                            button.click();
                            await new Promise(resolve => setTimeout(resolve, 1000));
                        }
                    } catch (e) {
                        console.log('Button click failed:', e);
                    }
                }
                
                // Wait for new content to load
                await new Promise(resolve => setTimeout(resolve, 2000));
                
                // Final scroll to ensure all content is loaded
                window.scrollTo(0, document.body.scrollHeight);
                await new Promise(resolve => setTimeout(resolve, 1000));
                
                console.log('Comprehensive Spotify page processing complete');
                """,
                magic=True,  # Enable anti-bot features
                simulate_user=True,
                verbose=True
            )
            
            # Add markdown generator if available
            if markdown_generator:
                crawler_config.markdown_generator = markdown_generator
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=spotify_url,
                    config=crawler_config
                )
                
                if result.success and result.html:
                    logger.info(f"✅ Successfully loaded Spotify page (HTML: {len(result.html)} chars)")
                    
                    # Use enhanced extractor
                    try:
                        from enhanced_extractors import EnhancedSpotifyExtractor
                        spotify_data = EnhancedSpotifyExtractor.extract_artist_data(result.html)
                        
                        # Extract monthly listeners
                        if spotify_data.get("monthly_listeners"):
                            try:
                                parsed_listeners = self._parse_number(spotify_data["monthly_listeners"])
                                if parsed_listeners > 0:
                                    enriched_data.profile.follower_counts['spotify_monthly_listeners'] = parsed_listeners
                                    logger.info(f"✅ Monthly listeners: {parsed_listeners:,}")
                            except Exception as e:
                                logger.warning(f"Error parsing monthly listeners: {e}")
                        
                        # Extract artist name (validation)
                        if spotify_data.get("artist_name") and not enriched_data.profile.name:
                            enriched_data.profile.name = spotify_data["artist_name"]
                        
                        # Extract biography
                        if spotify_data.get("biography"):
                            enriched_data.profile.bio = spotify_data["biography"]
                            logger.info(f"✅ Biography found: {spotify_data['biography'][:100]}...")
                        
                        # Extract top tracks
                        if spotify_data.get("top_tracks"):
                            enriched_data.top_tracks = spotify_data["top_tracks"][:10]  # Top 10
                            logger.info(f"✅ Extracted {len(enriched_data.top_tracks)} valid tracks (top 5)")
                            logger.info(f"🎵 Top tracks: {enriched_data.top_tracks[:4]}")
                        
                        # Extract genres
                        if spotify_data.get("genres"):
                            enriched_data.profile.genres = spotify_data["genres"]
                            logger.info(f"✅ Genres: {enriched_data.profile.genres}")
                        
                        logger.info("✅ Enhanced Spotify extraction completed successfully")
                        
                    except Exception as e:
                        logger.error(f"Enhanced Spotify extraction failed: {e}")
                        # Fallback to original extraction
                        monthly_patterns = [
                            r'(\d{1,3}(?:,\d{3})*)\s*monthly\s*listeners',  # "1,234,567 monthly listeners"
                            r'([\d,.]+[KMB])\s*monthly\s*listeners',        # "1.2M monthly listeners"
                            r'"monthlyListeners":\s*(\d+)',                 # JSON: "monthlyListeners": 123456
                            r'monthlyListeners["\']?\s*:\s*(\d+)',          # monthlyListeners: 123456
                            r'listeners["\']?\s*:\s*(\d+)',                 # listeners: 123456
                            r'data-testid="monthly-listeners"[^>]*>([^<]*\d[^<]*)<',  # Test ID
                            r'<span[^>]*>\s*(\d{1,3}(?:,\d{3})*)\s*monthly\s*listeners\s*</span>',  # Span tag
                        ]
                        
                        for pattern in monthly_patterns:
                            matches = re.findall(pattern, result.html, re.IGNORECASE)
                            if matches:
                                try:
                                    listener_text = matches[0]
                                    parsed_listeners = self._parse_number(listener_text)
                                    if parsed_listeners > 0:
                                        enriched_data.profile.follower_counts['spotify_monthly_listeners'] = parsed_listeners
                                        logger.info(f"✅ Monthly listeners: {parsed_listeners:,}")
                                        break
                                except:
                                    continue
                    
                    # 2. Enhanced biography extraction
                    bio_patterns = [
                        r'<div[^>]*class="[^"]*bio[^"]*"[^>]*>([^<]+)</div>',
                        r'<p[^>]*class="[^"]*bio[^"]*"[^>]*>([^<]+)</p>',
                        r'<div[^>]*data-testid="artist-about"[^>]*>([^<]+)</div>',
                        r'"biography":\s*"([^"]+)"',
                        r'"description":\s*"([^"]+)"',
                        r'<meta[^>]*name="description"[^>]*content="([^"]+)"',
                        r'data-testid="description"[^>]*>([^<]+)<',
                        r'about[^>]*>\s*([^<]{50,500})\s*<',  # General about content
                    ]
                    
                    for pattern in bio_patterns:
                        matches = re.findall(pattern, result.html, re.IGNORECASE | re.DOTALL)
                        if matches:
                            bio_text = re.sub(r'<[^>]+>', '', matches[0]).strip()  # Remove HTML tags
                            if len(bio_text) > 30:  # Ensure substantial content
                                enriched_data.profile.bio = bio_text[:600]  # Store more bio content
                                logger.info(f"✅ Biography found: {bio_text[:80]}...")
                                break
                    
                    # 3. Enhanced top city extraction
                    city_patterns = [
                        r'top\s*city[^>]*>([^<]+)<',                    # "Top city: New York"
                        r'where\s*your\s*music\s*is\s*most\s*popular[^>]*>([^<]+)<',  # Spotify's phrasing
                        r'(\w+(?:\s+\w+)*)\s*is\s*where\s*your\s*music',  # "New York is where your music..."
                        r'"topCity":\s*"([^"]+)"',                       # JSON top city
                        r'"city":\s*"([^"]+)"',                          # JSON city
                        r'most\s*popular\s*in[^>]*>([^<]+)<',           # "Most popular in New York"
                        r'listeners\s*in[^>]*>([^<]*(?:New York|Los Angeles|London|Toronto|Sydney|Berlin|Paris|Tokyo|Mexico City|São Paulo|Chicago|Miami|Atlanta|Nashville|Austin)[^<]*)<',
                        r'top\s*location[^>]*>([^<]+)<',                # "Top location: City"
                    ]
                    
                    for pattern in city_patterns:
                        matches = re.findall(pattern, result.html, re.IGNORECASE)
                        if matches:
                            city_text = matches[0].strip()
                            # Clean and validate city name
                            if len(city_text) > 2 and len(city_text) < 50 and not city_text.isdigit():
                                enriched_data.profile.metadata['spotify_top_city'] = city_text
                                logger.info(f"✅ Top city: {city_text}")
                                break
                    
                    # 4. Enhanced genre extraction
                    genre_patterns = [
                        r'"genres":\s*\[([^\]]+)\]',                    # JSON array
                        r'<span[^>]*class="[^"]*genre[^"]*"[^>]*>([^<]+)</span>',  # Genre spans
                        r'data-testid="genre"[^>]*>([^<]+)<',          # Test ID
                        r'<a[^>]*href="/genre/[^"]*"[^>]*>([^<]+)</a>', # Genre links
                        r'"genre":\s*"([^"]+)"',                        # Single genre JSON
                    ]
                    
                    for pattern in genre_patterns:
                        matches = re.findall(pattern, result.html, re.IGNORECASE)
                        if matches:
                            if pattern.startswith('"genres"'):  # JSON array pattern
                                genres_text = matches[0]
                                genre_list = re.findall(r'"([^"]+)"', genres_text)
                                if genre_list:
                                    enriched_data.profile.genres = genre_list[:5]
                                    logger.info(f"✅ Genres: {', '.join(genre_list[:3])}")
                                    break
                            else:  # Individual genre patterns
                                genre_list = [match.strip() for match in matches[:5]]
                                if genre_list:
                                    enriched_data.profile.genres = genre_list
                                    logger.info(f"✅ Genres: {', '.join(genre_list[:3])}")
                                    break
                    
                    # 5. Enhanced social media link extraction from Spotify page
                    social_link_patterns = {
                        'instagram': r'href="(https?://(?:www\.)?instagram\.com/[^"/?]+)/?"',
                        'twitter': r'href="(https?://(?:www\.)?(?:twitter|x)\.com/[^"/?]+)/?"',
                        'facebook': r'href="(https?://(?:www\.)?facebook\.com/[^"/?]+)/?"',
                        'youtube': r'href="(https?://(?:www\.)?youtube\.com/(?:c/|user/|@)[^"/?]+)/?"',
                    }
                    
                    for platform, pattern in social_link_patterns.items():
                        matches = re.findall(pattern, result.html, re.IGNORECASE)
                        if matches:
                            # Filter out generic Spotify links and ensure artist-specific links
                            valid_links = []
                            for link in matches:
                                # Exclude generic platform links and ensure artist-specific profiles
                                if (not any(generic in link.lower() for generic in ['/spotify', '/login', '/signup', '/home', '/browse']) and
                                    len(link.split('/')[-1]) > 2):  # Ensure username/handle exists
                                    valid_links.append(link)
                            
                            if valid_links:
                                enriched_data.profile.social_links[platform] = valid_links[0]
                                logger.info(f"✅ Found {platform}: {valid_links[0]}")
                    
                    # 6. Extract top 5 tracks with enhanced patterns and filtering
                    tracks = await self._extract_spotify_tracks_with_play_counts(result.html, enriched_data.profile.name)
                    if tracks:
                        enriched_data.profile.metadata['top_tracks'] = tracks  # Already limited to 5 tracks
                        logger.info(f"✅ Found {len(tracks)} valid tracks (top 5)")
                        
                        # Analyze lyrics for top tracks using Musixmatch
                        await self._enrich_lyrics_with_musixmatch(enriched_data)
                    
                    # 7. Validate social media links against YouTube data if available
                    if hasattr(enriched_data.profile, 'social_links') and enriched_data.profile.social_links:
                        self._validate_social_links_consistency(enriched_data)
                    
                    logger.info(f"✅ Spotify enrichment complete")
                    
                else:
                    logger.warning(f"⚠️ Failed to load Spotify page: {spotify_url}")
                    
        except Exception as e:
            logger.error(f"❌ Spotify enrichment error: {str(e)}")
            # Don't let Spotify errors break enrichment
            logger.info("⚠️ Continuing without Spotify data")
    
    async def _search_and_enrich_spotify(self, artist_name: str, enriched_data: EnrichedArtistData):
        """Search for artist on Spotify and enrich with robust fallback approach"""
        try:
            # Handle character encoding for non-ASCII artist names
            import urllib.parse
            encoded_name = urllib.parse.quote(artist_name.encode('utf-8'), safe='')
            search_url = f"https://open.spotify.com/search/{encoded_name}/artists"
            logger.info(f"🔍 Searching Spotify for: {artist_name}")
            
            # Flexible crawler config that doesn't depend on specific selectors
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_until="domcontentloaded",  # Don't wait for specific elements
                page_timeout=15000,  # Shorter timeout
                delay_before_return_html=3.0,  # Wait for content to load
                js_code="""
                // Wait for page load and try to find any search results
                await new Promise(resolve => setTimeout(resolve, 3000));
                
                // Try to click "Show all" if it exists
                const showAllButton = document.querySelector('[data-testid="show-all-button"], .show-all, button[class*="show"]');
                if (showAllButton) {
                    showAllButton.click();
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
                
                console.log('Spotify search page loaded');
                """,
                verbose=True
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=search_url,
                    config=crawler_config
                )
                
                if result.success and result.html:
                    # Use multiple extraction strategies - no specific selectors required
                    artist_urls = []
                    
                    # Strategy 1: Find artist profile links in HTML
                    import re
                    artist_link_patterns = [
                        r'href="(/artist/[^"]+)"',  # Direct artist links
                        r'"uri":"spotify:artist:([^"]+)"',  # Spotify URIs
                        r'open\.spotify\.com/artist/([^"?&]+)',  # Full URLs
                    ]
                    
                    for pattern in artist_link_patterns:
                        matches = re.findall(pattern, result.html)
                        for match in matches:
                            if pattern.startswith('"uri"'):
                                artist_urls.append(f"https://open.spotify.com/artist/{match}")
                            elif match.startswith('/artist/'):
                                artist_urls.append(f"https://open.spotify.com{match}")
                            else:
                                artist_urls.append(f"https://open.spotify.com/artist/{match}")
                    
                    # Strategy 2: Look for any links containing the artist name
                    if not artist_urls:
                        name_pattern = re.escape(artist_name.lower())
                        name_links = re.findall(r'href="([^"]*artist[^"]*)"[^>]*>[^<]*' + name_pattern, result.html, re.IGNORECASE)
                        artist_urls.extend([url for url in name_links if 'spotify.com' in url])
                    
                    # Use the first found artist URL
                    if artist_urls:
                        artist_url = artist_urls[0]
                        logger.info(f"✅ Found Spotify artist: {artist_url}")
                        
                        # Create temporary profile with Spotify URL and enrich
                        temp_profile = ArtistProfile(
                            name=artist_name,
                            spotify_url=artist_url
                        )
                        await self._enrich_spotify(temp_profile, enriched_data)
                    else:
                        logger.warning(f"⚠️ No Spotify artist found for: {artist_name}")
                        
                        # Fallback: Try direct search by creating a probable URL
                        # Many artists have clean URLs based on their name
                        clean_name = re.sub(r'[^\w\s-]', '', artist_name).strip().replace(' ', '')
                        probable_urls = [
                            f"https://open.spotify.com/artist/{clean_name}",
                            f"https://open.spotify.com/artist/{clean_name.lower()}",
                            f"https://open.spotify.com/artist/{artist_name.replace(' ', '').lower()}"
                        ]
                        
                        # Try the most likely URL
                        temp_profile = ArtistProfile(
                            name=artist_name,
                            spotify_url=probable_urls[0]
                        )
                        
                        logger.info(f"🔍 Trying probable Spotify URL: {probable_urls[0]}")
                        await self._enrich_spotify(temp_profile, enriched_data)
                
                else:
                    logger.warning(f"⚠️ Spotify search page failed to load for: {artist_name}")
                    
        except Exception as e:
            logger.error(f"❌ Spotify search error for {artist_name}: {str(e)}")
            # Don't let Spotify errors break the entire enrichment
            logger.info("⚠️ Continuing without Spotify data")
    
    async def _enrich_spotify_api(self, artist_name: str, enriched_data: EnrichedArtistData):
        """Enrich with Spotify API data including avatar and genres"""
        try:
            logger.info(f"🎵 Using Spotify API to get avatar and genres for: {artist_name}")
            
            # Get enriched data from Spotify API
            spotify_data = await self.spotify_client.get_enriched_artist_data(artist_name)
            
            if spotify_data:
                # Update artist profile with API data
                if spotify_data.get('avatar_url'):
                    enriched_data.profile.metadata['avatar_url'] = spotify_data['avatar_url']
                    logger.info(f"✅ Added avatar URL: {spotify_data['avatar_url'][:50]}...")
                
                if spotify_data.get('genres'):
                    enriched_data.profile.genres = spotify_data['genres']
                    logger.info(f"✅ Added genres: {', '.join(spotify_data['genres'][:3])}")
                
                # Add additional Spotify API data to metadata
                api_metadata = {
                    'spotify_id': spotify_data.get('spotify_id'),
                    'spotify_followers': spotify_data.get('followers', 0),
                    'spotify_popularity': spotify_data.get('popularity', 0),
                    'spotify_top_tracks': spotify_data.get('top_tracks', []),
                    'spotify_genres': spotify_data.get('genres', [])  # Store genres in metadata for database
                }
                
                # Update existing metadata
                enriched_data.profile.metadata.update(api_metadata)
                
                # If we don't have monthly listeners from scraping, use followers as estimate
                if not enriched_data.profile.follower_counts.get('spotify_monthly_listeners'):
                    if spotify_data.get('followers', 0) > 0:
                        # Rough estimate: monthly listeners ≈ 20% of followers
                        estimated_listeners = int(spotify_data['followers'] * 0.2)
                        enriched_data.profile.follower_counts['spotify_monthly_listeners'] = estimated_listeners
                        logger.info(f"✅ Estimated monthly listeners: {estimated_listeners:,}")
                
                logger.info(f"✅ Spotify API enrichment complete for {artist_name}")
            else:
                logger.warning(f"⚠️ No Spotify API data found for: {artist_name}")
                
        except Exception as e:
            logger.error(f"❌ Spotify API enrichment error for {artist_name}: {e}")
            # Don't let API errors break enrichment
    
    async def _enrich_instagram(self, instagram_url: str, enriched_data: EnrichedArtistData):
        """Enrich with Instagram data using LLM content filtering"""
        try:
            logger.info(f"📸 Crawling Instagram with LLM filtering: {instagram_url}")
            
            # Create LLM content filter for Instagram (if available)
            content_filter = await self.create_instagram_content_filter()
            
            # Create markdown generator with LLM filter (if available)
            markdown_generator = None
            if content_filter and DefaultMarkdownGenerator:
                markdown_generator = DefaultMarkdownGenerator(
                    content_filter=content_filter,
                    options={"ignore_links": False}
                )
            
            # Enhanced schema for Instagram data extraction with current selectors
            schema = {
                "name": "Instagram Profile",
                "fields": [
                    {
                        "name": "username",
                        "selector": "h2, h1, [data-testid='user-title'], .x1lliihq.x1plvlek.xryxfnj.x1n2onr6.x193iq5w.xeuugli.x1fj9vlw.x13faqbe.x1vvkbs.x1s928wv.xhkezso.x1gmr53x.x1cpjm7i.x1fgarty.x1943h6x.x1i0vuye.xvs91rp.xo1l8bm.x5n08af.x10wh9bi.x1wdrske.x8viiok.x18hxmgj",
                        "type": "text"
                    },
                    {
                        "name": "bio", 
                        "selector": "[data-testid='user-biography'], .-vDIg span, .biography span, .x7a106z.x972fbf.xcfux6l.x1qhh985.xm0m39n.x9f619.x78zum5.xdt5ytf.x2lah0s.xdj266r.x11i5rnm.xat24cr.x1mh8g0r.xexx8yu.x4uap5.x18d9i69.xkhd6sd.x1n2onr6.x11njtxf",
                        "type": "text"
                    },
                    {
                        "name": "follower_count_text",
                        "selector": "a[href*='followers/'] span, .-nal3 span, .follower span, .x1i10hfl.xjbqb8w.x6umtig.x1b1mbwd.xaqea5y.xav7gou.x9f619.x1ypdohk.xe8uvvx.xdj266r.x11i5rnm.xat24cr.x1mh8g0r.xexx8yu.x4uap5.x18d9i69.xkhd6sd.x16tdsg8.x1hl2dhg.xggy1nq.x1a2a7pz.x1heor9g.x1sur9pj.xkrqix3.x1lliihq.x5n08af.x193iq5w.x1n2onr6.xeuugli",
                        "type": "text"
                    },
                    {
                        "name": "posts_count",
                        "selector": "[data-testid='user-posts-count'], .posts-count, .x1i10hfl.xjbqb8w.x6umtig.x1b1mbwd.xaqea5y.xav7gou.x9f619.x1ypdohk.xe8uvvx.xdj266r.x11i5rnm.xat24cr.x1mh8g0r.xexx8yu.x4uap5.x18d9i69.xkhd6sd.x16tdsg8.x1hl2dhg.xggy1nq.x1a2a7pz.x1heor9g.x1sur9pj.xkrqix3.x1lliihq.x5n08af.x193iq5w.x1n2onr6.xeuugli span",
                        "type": "text"
                    },
                    {
                        "name": "following_count",
                        "selector": "a[href*='following/'] span, .following-count, .-nal3 span",
                        "type": "text"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_until="domcontentloaded",
                page_timeout=30000,
                delay_before_return_html=5.0,  # More time for LLM filtering
                js_code="""
                // Wait for page load and scroll slightly to trigger content
                await new Promise(resolve => setTimeout(resolve, 3000));
                window.scrollTo(0, 300);
                await new Promise(resolve => setTimeout(resolve, 2000));
                """,
                magic=True,  # Enable anti-bot features
                simulate_user=True
            )
            
            # Add markdown generator if available
            if markdown_generator:
                crawler_config.markdown_generator = markdown_generator
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=instagram_url,
                    config=crawler_config
                )
                
                if result.success:
                    # Try structured extraction first
                    if result.extracted_content:
                        try:
                            instagram_data = json.loads(result.extracted_content)
                            if instagram_data.get('follower_count_text'):
                                enriched_data.profile.follower_counts['instagram'] = self._parse_number(instagram_data['follower_count_text'])
                        except:
                            pass
                    
                    # Fallback to regex patterns from HTML
                    if not enriched_data.profile.follower_counts.get('instagram'):
                        # Multiple patterns for Instagram data with enhanced validation
                        patterns = [
                            r'"edge_followed_by":\{"count":(\d+)\}',  # GraphQL API
                            r'"follower_count":(\d+)',  # Alternative API
                            r'([\d,.]+[KMB]?)\s*[Ff]ollowers?',  # Text pattern
                            r'(\d{1,3}(?:,\d{3})*)\s*followers?',  # Exact number pattern
                            r'"edge_follow":\{"count":(\d+)\}',  # Alternative GraphQL
                            r'content="([^"]+) Followers',  # Meta tag pattern
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, result.html, re.IGNORECASE)
                            if matches:
                                try:
                                    # Take the first match that's reasonable
                                    for match in matches:
                                        if pattern.startswith('"'):  # JSON patterns
                                            follower_count = int(match)
                                        else:  # Text patterns
                                            follower_count = self._parse_number(match)
                                        
                                        # Validate reasonable follower count (not too low/high)
                                        if 0 < follower_count < 1000000000:  # Max 1B followers
                                            enriched_data.profile.follower_counts['instagram'] = follower_count
                                            break
                                    
                                    if enriched_data.profile.follower_counts.get('instagram'):
                                        break
                                except (ValueError, TypeError):
                                    continue
                    
                    # Clean Instagram data using AI
                    raw_instagram_data = {
                        'follower_count_text': instagram_data.get('follower_count_text', ''),
                        'username': instagram_data.get('username', ''),
                        'bio': instagram_data.get('bio', ''),
                        'posts_count': instagram_data.get('posts_count', ''),
                        'following_count': instagram_data.get('following_count', '')
                    }
                    
                    cleaned_instagram = await self._clean_platform_data('instagram', raw_instagram_data)
                    if cleaned_instagram and cleaned_instagram.follower_count:
                        enriched_data.profile.follower_counts['instagram'] = cleaned_instagram.follower_count
                        if cleaned_instagram.bio_text:
                            enriched_data.profile.metadata['instagram_bio'] = cleaned_instagram.bio_text
                        logger.info(f"✅ AI cleaned Instagram: {cleaned_instagram.follower_count:,} followers (confidence: {cleaned_instagram.confidence_score:.2f})")
                    else:
                        # Fallback to original extraction
                        instagram_followers = enriched_data.profile.follower_counts.get('instagram', 0)
                        if instagram_followers:
                            logger.info(f"✅ Instagram followers: {instagram_followers:,}")
                        else:
                            logger.warning("⚠️ Could not extract Instagram follower count")
                    
        except Exception as e:
            logger.error(f"❌ Instagram enrichment error: {str(e)}")
    
    async def _enrich_tiktok(self, tiktok_url: str, enriched_data: EnrichedArtistData):
        """Enrich with TikTok data using LLM content filtering"""
        try:
            logger.info(f"🎭 Crawling TikTok with LLM filtering: {tiktok_url}")
            
            # Create LLM content filter for TikTok (if available)
            content_filter = await self.create_tiktok_content_filter()
            
            # Create markdown generator with LLM filter (if available)
            markdown_generator = None
            if content_filter and DefaultMarkdownGenerator:
                markdown_generator = DefaultMarkdownGenerator(
                    content_filter=content_filter,
                    options={"ignore_links": False}
                )
            
            # Enhanced schema for TikTok data extraction with current selectors
            schema = {
                "name": "TikTok Profile",
                "fields": [
                    {
                        "name": "username",
                        "selector": "h1, h2, [data-e2e='user-title'], [data-e2e='user-subtitle'], .share-title-container h1, .user-title",
                        "type": "text"
                    },
                    {
                        "name": "follower_count_text",
                        "selector": "[data-e2e='followers-count'], .count-infra, [title*='Followers'], .number[title*='Followers'], .tiktok-counter strong",
                        "type": "text"
                    },
                    {
                        "name": "likes_count_text", 
                        "selector": "[data-e2e='likes-count'], .likes-count, [title*='Likes'], .number[title*='Likes'], .tiktok-counter strong",
                        "type": "text"
                    },
                    {
                        "name": "following_count_text",
                        "selector": "[data-e2e='following-count'], .following-count, [title*='Following'], .number[title*='Following']",
                        "type": "text"
                    },
                    {
                        "name": "bio",
                        "selector": "[data-e2e='user-bio'], .bio-text, .user-bio, .share-desc-container",
                        "type": "text"
                    },
                    {
                        "name": "verified",
                        "selector": "[data-e2e='user-verified'], .user-verified, .verified-icon",
                        "type": "text"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_until="domcontentloaded",
                page_timeout=30000,
                delay_before_return_html=5.0,  # More time for LLM filtering
                js_code="""
                // Wait for page load and try to trigger any lazy loading
                await new Promise(resolve => setTimeout(resolve, 4000));
                window.scrollTo(0, 500);
                await new Promise(resolve => setTimeout(resolve, 2000));
                """,
                magic=True,  # Enable anti-bot features
                simulate_user=True
            )
            
            # Add markdown generator if available
            if markdown_generator:
                crawler_config.markdown_generator = markdown_generator
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=tiktok_url,
                    config=crawler_config
                )
                
                if result.success:
                    # Try structured extraction first
                    if result.extracted_content:
                        try:
                            tiktok_data = json.loads(result.extracted_content)
                            if tiktok_data.get('follower_count_text'):
                                enriched_data.profile.follower_counts['tiktok'] = self._parse_number(tiktok_data['follower_count_text'])
                            if tiktok_data.get('likes_count_text'):
                                enriched_data.profile.metadata['tiktok_likes'] = self._parse_number(tiktok_data['likes_count_text'])
                        except:
                            pass
                    
                    # Fallback to regex patterns from HTML
                    if not enriched_data.profile.follower_counts.get('tiktok') or not enriched_data.profile.metadata.get('tiktok_likes'):
                        # Multiple patterns for TikTok data
                        follower_patterns = [
                            r'"followerCount":(\d+)',  # JSON API
                            r'"stats":\{"followerCount":(\d+)',  # Alternative API
                            r'([\d,.]+[KMB]?)\s*[Ff]ollowers?',  # Text pattern
                            r'(\d{1,3}(?:,\d{3})*)\s*followers',  # Exact number
                        ]
                        
                        likes_patterns = [
                            r'"heartCount":(\d+)',  # JSON API
                            r'"stats":\{"heartCount":(\d+)',  # Alternative API  
                            r'([\d,.]+[KMB]?)\s*[Ll]ikes?',  # Text pattern
                            r'(\d{1,3}(?:,\d{3})*)\s*likes',  # Exact number
                        ]
                        
                        # Extract followers
                        if not enriched_data.profile.follower_counts.get('tiktok'):
                            for pattern in follower_patterns:
                                match = re.search(pattern, result.html, re.IGNORECASE)
                                if match:
                                    try:
                                        if pattern.startswith('"'):  # JSON patterns
                                            enriched_data.profile.follower_counts['tiktok'] = int(match.group(1))
                                        else:  # Text patterns
                                            enriched_data.profile.follower_counts['tiktok'] = self._parse_number(match.group(1))
                                        break
                                    except ValueError:
                                        continue
                        
                        # Extract likes
                        if not enriched_data.profile.metadata.get('tiktok_likes'):
                            for pattern in likes_patterns:
                                match = re.search(pattern, result.html, re.IGNORECASE)
                                if match:
                                    try:
                                        if pattern.startswith('"'):  # JSON patterns
                                            enriched_data.profile.metadata['tiktok_likes'] = int(match.group(1))
                                        else:  # Text patterns
                                            enriched_data.profile.metadata['tiktok_likes'] = self._parse_number(match.group(1))
                                        break
                                    except ValueError:
                                        continue
                    
                    tiktok_followers = enriched_data.profile.follower_counts.get('tiktok', 0)
                    tiktok_likes = enriched_data.profile.metadata.get('tiktok_likes', 0)
                    if tiktok_followers or tiktok_likes:
                        logger.info(f"✅ TikTok: {tiktok_followers:,} followers, {tiktok_likes:,} likes")
                    else:
                        logger.warning("⚠️ Could not extract TikTok metrics")
                    
        except Exception as e:
            logger.error(f"❌ TikTok enrichment error: {str(e)}")
    
    async def _search_and_enrich_instagram(self, artist_name: str, enriched_data: EnrichedArtistData):
        """Search for artist on Instagram and enrich if found"""
        try:
            # Try common Instagram username patterns
            potential_usernames = [
                artist_name.lower().replace(' ', ''),
                artist_name.lower().replace(' ', '_'),
                artist_name.lower().replace(' ', '.'),
                f"{artist_name.lower().replace(' ', '')}official",
                f"official{artist_name.lower().replace(' ', '')}",
            ]
            
            for username in potential_usernames:
                instagram_url = f"https://instagram.com/{username}"
                logger.info(f"🔍 Trying Instagram: {instagram_url}")
                
                # Quick check if this profile exists and has reasonable followers
                await self._enrich_instagram(instagram_url, enriched_data)
                
                # If we found followers, we likely found the right profile
                if enriched_data.profile.follower_counts.get('instagram', 0) > 100:
                    logger.info(f"✅ Found Instagram profile: {instagram_url}")
                    enriched_data.profile.social_links['instagram'] = instagram_url
                    break
                    
        except Exception as e:
            logger.debug(f"Instagram search failed for {artist_name}: {e}")
    
    async def _search_and_enrich_tiktok(self, artist_name: str, enriched_data: EnrichedArtistData):
        """Search for artist on TikTok and enrich if found"""
        try:
            # Try common TikTok username patterns
            potential_usernames = [
                artist_name.lower().replace(' ', ''),
                artist_name.lower().replace(' ', '_'),
                artist_name.lower().replace(' ', '.'),
                f"{artist_name.lower().replace(' ', '')}official",
                f"official{artist_name.lower().replace(' ', '')}",
            ]
            
            for username in potential_usernames:
                tiktok_url = f"https://tiktok.com/@{username}"
                logger.info(f"🔍 Trying TikTok: {tiktok_url}")
                
                # Quick check if this profile exists and has reasonable followers
                await self._enrich_tiktok(tiktok_url, enriched_data)
                
                # If we found followers, we likely found the right profile
                if enriched_data.profile.follower_counts.get('tiktok', 0) > 100:
                    logger.info(f"✅ Found TikTok profile: {tiktok_url}")
                    enriched_data.profile.social_links['tiktok'] = tiktok_url
                    break
                    
        except Exception as e:
            logger.debug(f"TikTok search failed for {artist_name}: {e}")

    async def _enrich_lyrics(self, enriched_data: EnrichedArtistData):
        """Enrich with lyrics analysis from multiple sources"""
        try:
            top_tracks = enriched_data.profile.metadata.get('top_tracks', [])
            if not top_tracks:
                logger.info("No top tracks available for lyrics analysis")
                return
            
            lyrics_analyses = []
            
            for track in top_tracks[:3]:  # Analyze top 3 tracks
                track_name = track.get('name', '')
                artist_name = enriched_data.profile.name
                
                if not track_name or not artist_name:
                    continue
                
                logger.info(f"🎤 Getting lyrics for: {track_name} by {artist_name}")
                
                # Try multiple lyrics sources
                lyrics_text = await self._get_lyrics_from_sources(artist_name, track_name)
                
                if lyrics_text:
                    # Analyze lyrics with DeepSeek
                    analysis = await self._analyze_lyrics(lyrics_text, track_name)
                    if analysis:
                        lyrics_analyses.append(analysis)
                        logger.info(f"✅ Analyzed lyrics for: {track_name}")
                else:
                    logger.warning(f"⚠️ Could not find lyrics for: {track_name}")
            
            # Combine analyses and store in profile
            if lyrics_analyses:
                themes = self._combine_lyrics_analyses(lyrics_analyses)
                enriched_data.profile.metadata['lyrics_themes'] = themes
                logger.info(f"✅ Lyrics analysis complete: {themes}")
            else:
                logger.warning("⚠️ No lyrics analyses available")
                
        except Exception as e:
            logger.error(f"❌ Lyrics enrichment error: {str(e)}")
    
    async def _get_lyrics_from_sources(self, artist_name: str, track_name: str) -> str:
        """Try to get lyrics from multiple sources"""
        # Clean names for URL formatting
        clean_artist = re.sub(r'[^a-zA-Z0-9\s]', '', artist_name).replace(' ', '-').lower()
        clean_track = re.sub(r'[^a-zA-Z0-9\s]', '', track_name).replace(' ', '-').lower()
        
        # Try Musixmatch first
        lyrics_text = await self._get_musixmatch_lyrics(clean_artist, clean_track)
        
        if not lyrics_text:
            # Try Genius as backup
            lyrics_text = await self._get_genius_lyrics(clean_artist, clean_track)
        
        return lyrics_text
    
    async def _get_musixmatch_lyrics(self, clean_artist: str, clean_track: str) -> str:
        """Extract lyrics from Musixmatch with LLM content filtering"""
        try:
            musixmatch_url = f"https://www.musixmatch.com/lyrics/{clean_artist}/{clean_track}"
            
            # Create LLM content filter for lyrics (if available)
            content_filter = await self.create_lyrics_content_filter()
            
            # Create markdown generator with LLM filter (if available)
            markdown_generator = None
            if content_filter and DefaultMarkdownGenerator:
                markdown_generator = DefaultMarkdownGenerator(
                    content_filter=content_filter,
                    options={"ignore_links": False}
                )
            
            # Enhanced schema for Musixmatch lyrics extraction with current selectors
            schema = {
                "name": "Musixmatch Lyrics",
                "fields": [
                    {
                        "name": "lyrics_content",
                        "selector": ".lyrics__content__ok span, .lyrics__content span, .mxm-lyrics span, [data-testid='lyrics-line'], .lyrics-line-text, .col-sm-10.col-md-8.col-ml-3.col-lg-6 p",
                        "type": "list"
                    },
                    {
                        "name": "song_title",
                        "selector": "h1, .mxm-track-title h1, .mxm-track-title, [data-testid='track-title'], .track-title",
                        "type": "text"
                    },
                    {
                        "name": "artist_name",
                        "selector": ".mxm-track-subtitle a, [data-testid='artist-name'], .artist-name, .track-artist",
                        "type": "text"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_until="domcontentloaded",
                page_timeout=25000,  # Increased timeout for LLM processing
                delay_before_return_html=4.0,  # More time for content filtering
                js_code="""
                // Wait for lyrics to load and handle any overlays
                await new Promise(resolve => setTimeout(resolve, 3000));
                
                // Try to close any modal/overlay
                const closeButtons = document.querySelectorAll('[data-testid="modal-close"], .close-btn, .modal-close');
                closeButtons.forEach(btn => btn.click());
                
                await new Promise(resolve => setTimeout(resolve, 1000));
                """,
                magic=True,  # Enable anti-bot features
                simulate_user=True
            )
            
            # Add markdown generator if available
            if markdown_generator:
                crawler_config.markdown_generator = markdown_generator
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=musixmatch_url,
                    config=crawler_config
                )
                
                if result.success:
                    # Use enhanced extractor first
                    try:
                        from enhanced_extractors import EnhancedMusixmatchExtractor
                        lyrics_data = EnhancedMusixmatchExtractor.extract_lyrics_data(result.html)
                        
                        if lyrics_data.get("lyrics") and len(lyrics_data["lyrics"]) > 20:
                            logger.info(f"✅ Enhanced extractor found lyrics ({len(lyrics_data['lyrics'])} chars)")
                            return lyrics_data["lyrics"]
                        
                    except Exception as e:
                        logger.warning(f"Enhanced lyrics extraction failed: {e}")
                    
                    # Try structured extraction fallback
                    if result.extracted_content:
                        try:
                            lyrics_data = json.loads(result.extracted_content)
                            if lyrics_data.get('lyrics_content'):
                                return ' '.join(lyrics_data['lyrics_content'])
                        except:
                            pass
                    
                    # Fallback to regex extraction
                    lyrics_patterns = [
                        r'<span class="lyrics__content[^"]*">([^<]+)</span>',
                        r'<span[^>]*lyrics[^>]*>([^<]+)</span>',
                        r'"lyrics":"([^"]+)"',
                    ]
                    
                    for pattern in lyrics_patterns:
                        matches = re.findall(pattern, result.html, re.DOTALL | re.IGNORECASE)
                        if matches:
                            return ' '.join(matches)[:2000]  # Limit length
                            
        except Exception as e:
            logger.debug(f"Musixmatch extraction failed: {e}")
        
        return None
    
    async def _get_genius_lyrics(self, clean_artist: str, clean_track: str) -> str:
        """Extract lyrics from Genius as backup"""
        try:
            genius_url = f"https://genius.com/{clean_artist}-{clean_track}-lyrics"
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_until="domcontentloaded",
                page_timeout=15000,
                delay_before_return_html=2.0,
                js_code="""
                await new Promise(resolve => setTimeout(resolve, 2000));
                """
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=genius_url,
                    config=crawler_config
                )
                
                if result.success:
                    # Extract lyrics from Genius
                    lyrics_pattern = r'<div[^>]*data-lyrics-container[^>]*>([^<]+)</div>'
                    match = re.search(lyrics_pattern, result.html, re.DOTALL)
                    if match:
                        return match.group(1).strip()[:2000]
                        
        except Exception as e:
            logger.debug(f"Genius extraction failed: {e}")
        
        return None
    
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
    
    async def _extract_spotify_tracks_with_play_counts(self, html: str, artist_name: str) -> List[Dict[str, Any]]:
        """Extract top 5 tracks from Spotify HTML with proper filtering to avoid UI elements"""
        tracks = []
        
        logger.debug(f"Extracting tracks with play counts from HTML of length: {len(html)}")
        
        # Enhanced patterns based on actual Spotify structure
        track_patterns = [
            # Pattern 1: Modern Spotify internal track links with data-testid
            r'data-testid="internal-track-link"[^>]*href="/track/[A-Za-z0-9]+"[^>]*>.*?<div[^>]*>([^<]+)</div>',
            # Pattern 2: Track list row structure
            r'data-testid="tracklist-row"[^>]*>.*?href="/track/[A-Za-z0-9]+"[^>]*>.*?<div[^>]*>([^<]+)</div>',
            # Pattern 3: Alternative track link structure
            r'<a[^>]*href="/track/([A-Za-z0-9]+)"[^>]*data-testid="internal-track-link"[^>]*>.*?<div[^>]*>([^<]+)</div>',
            # Pattern 4: JSON track data if available
            r'"track":\s*{\s*"name":\s*"([^"]+)"[^}]*"popularity":\s*(\d+)',
            # Pattern 5: Broader track link pattern
            r'href="/track/[A-Za-z0-9]+"[^>]*>.*?<div[^>]*class="[^"]*text[^"]*"[^>]*>([^<]+)</div>',
        ]
        
        # UI elements to filter out
        ui_elements = {
            'add to liked songs', 'liked songs', 'accept cookies', 'cookie policy', 
            'privacy policy', 'show all', 'show more', 'view all', 'see all',
            'follow', 'share', 'more options', 'play', 'pause', 'shuffle',
            'repeat', 'queue', 'lyrics', 'credits', 'album', 'artist',
            'playlist', 'download', 'premium', 'advertisement', 'ad',
            'iab2v2', 'cookie', 'terms', 'help', 'about', 'contact',
            'support', 'legal', 'toggle', 'menu', 'search', 'home',
            'browse', 'library', 'made for you', 'recently played',
            'your episodes', 'your shows', 'create playlist'
        }
        
        for pattern_idx, pattern in enumerate(track_patterns):
            try:
                matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
                if matches:
                    logger.debug(f"Pattern {pattern_idx + 1} found {len(matches)} potential tracks")
                    
                    for match in matches:
                        # Handle different match structures based on pattern
                        if isinstance(match, tuple):
                            if pattern_idx == 2:  # Pattern 3: track ID + name
                                track_id, track_name = match
                                play_count = 0
                            elif pattern_idx == 3:  # Pattern 4: JSON with popularity
                                track_name, popularity = match
                                play_count = int(popularity) if popularity.isdigit() else 0
                            else:  # Other patterns return just track name
                                track_name = match[0] if len(match) > 0 else str(match)
                                play_count = 0
                        else:
                            track_name = str(match)
                            play_count = 0
                        
                        # Clean and validate track name
                        track_name = self._clean_track_name(track_name)
                        
                        # Advanced filtering to exclude UI elements
                        if self._is_valid_track_name(track_name, ui_elements, artist_name):
                            # Check for duplicates
                            if track_name not in [t['name'] for t in tracks]:
                                tracks.append({
                                    "name": track_name,
                                    "play_count": play_count,
                                    "position": len(tracks) + 1,
                                    "source": f"pattern_{pattern_idx + 1}",
                                    "confidence": 0.8 if pattern_idx < 3 else 0.6
                                })
                                
                                # Stop at 5 tracks as requested
                                if len(tracks) >= 5:
                                    break
                    
                    if tracks:
                        logger.info(f"Found {len(tracks)} valid tracks using pattern {pattern_idx + 1}")
                        break
                        
            except Exception as e:
                logger.warning(f"Error with track pattern {pattern_idx + 1}: {e}")
                continue
        
        # If no tracks found with specific patterns, try a more targeted approach
        if not tracks:
            logger.debug("No tracks found with specific patterns, trying targeted extraction")
            tracks = await self._extract_tracks_fallback(html, artist_name, ui_elements)
        
        # Sort by confidence and play count
        tracks.sort(key=lambda x: (-x.get('confidence', 0), -x.get('play_count', 0)))
        
        # Limit to top 5 as requested
        final_tracks = tracks[:5]
        
        logger.info(f"✅ Extracted {len(final_tracks)} valid tracks (top 5)")
        if final_tracks:
            track_names = [t['name'] for t in final_tracks]
            logger.info(f"🎵 Top tracks: {track_names}")
        else:
            logger.warning("⚠️ No valid track names extracted - may indicate page structure changes")
        
        return final_tracks
    
    def _clean_track_name(self, track_name: str) -> str:
        """Clean track name and remove unwanted text"""
        if not track_name:
            return ""
        
        # Remove HTML entities and extra whitespace
        track_name = re.sub(r'&[a-zA-Z0-9#]+;', '', track_name)
        track_name = re.sub(r'\s+', ' ', track_name).strip()
        
        # Remove common suffixes that aren't part of track names
        suffixes_to_remove = [
            r'\s*\([^)]*official[^)]*\)',
            r'\s*\([^)]*music[^)]*video[^)]*\)',
            r'\s*\([^)]*feat\.?[^)]*\)',
            r'\s*\([^)]*ft\.?[^)]*\)',
            r'\s*\([^)]*remix[^)]*\)',
            r'\s*\([^)]*version[^)]*\)',
            r'\s*\([^)]*edit[^)]*\)'
        ]
        
        for suffix_pattern in suffixes_to_remove:
            track_name = re.sub(suffix_pattern, '', track_name, flags=re.IGNORECASE)
        
        # Remove artist name if it appears at the start
        track_name = re.sub(r'^[^-]+-\s*', '', track_name).strip()
        
        # Remove quotes and brackets if they wrap the entire name
        track_name = track_name.strip('\'"()[]{}')
        
        return track_name.strip()
    
    def _is_valid_track_name(self, track_name: str, ui_elements: set, artist_name: str) -> bool:
        """Validate if the extracted text is actually a track name"""
        if not track_name or len(track_name) < 2:
            return False
        
        track_lower = track_name.lower().strip()
        
        # Check against UI elements
        if track_lower in ui_elements:
            return False
        
        # Check for partial matches with UI elements
        for ui_element in ui_elements:
            if ui_element in track_lower or track_lower in ui_element:
                return False
        
        # Filter out obvious non-track content
        invalid_patterns = [
            r'^https?://',  # URLs
            r'^\d+:\d+',    # Timestamps
            r'^[a-f0-9]{20,}$',  # Long hex strings (IDs)
            r'^[A-Z0-9_]{10,}$',  # All caps IDs
            r'^\d+$',       # Pure numbers
            r'copyright|©|℗',  # Copyright symbols
            r'all rights reserved',
            r'terms of use',
            r'privacy policy',
            r'cookie',
            r'advertisement',
            r'sponsored',
            r'^(play|pause|stop|next|previous|shuffle|repeat)$',
            r'^(volume|mute|unmute)$',
            r'^(search|filter|sort)$'
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, track_lower):
                return False
        
        # Must contain some alphabetic characters
        if not re.search(r'[a-zA-Z]', track_name):
            return False
        
        # Reasonable length (not too short, not too long)
        if len(track_name) > 100:
            return False
        
        # Not just the artist name
        if track_lower == artist_name.lower().strip():
            return False
        
        return True
    
    async def _extract_tracks_fallback(self, html: str, artist_name: str, ui_elements: set) -> List[Dict[str, Any]]:
        """Fallback method for track extraction with stricter filtering"""
        tracks = []
        
        try:
            # Look for any links to /track/ URLs and extract surrounding text
            track_url_pattern = r'<a[^>]*href="/track/([A-Za-z0-9]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(track_url_pattern, html)
            
            for track_id, track_text in matches:
                track_name = self._clean_track_name(track_text)
                
                if self._is_valid_track_name(track_name, ui_elements, artist_name):
                    tracks.append({
                        "name": track_name,
                        "track_id": track_id,
                        "play_count": 0,
                        "position": len(tracks) + 1,
                        "source": "fallback_track_links",
                        "confidence": 0.7
                    })
                    
                    if len(tracks) >= 5:
                        break
            
            # If still no tracks, try to find song-like text near "popular" sections
            if not tracks:
                popular_section_pattern = r'popular.*?<a[^>]*href="/track/[^"]*"[^>]*>([^<]+)</a>'
                matches = re.findall(popular_section_pattern, html, re.IGNORECASE | re.DOTALL)
                
                for match in matches[:5]:
                    track_name = self._clean_track_name(match)
                    if self._is_valid_track_name(track_name, ui_elements, artist_name):
                        tracks.append({
                            "name": track_name,
                            "play_count": 0,
                            "position": len(tracks) + 1,
                            "source": "fallback_popular_section",
                            "confidence": 0.5
                        })
                        
                        if len(tracks) >= 5:
                            break
        
        except Exception as e:
            logger.error(f"Error in fallback track extraction: {e}")
        
        return tracks
    
    async def _enrich_lyrics_with_musixmatch(self, enriched_data: EnrichedArtistData):
        """Enhanced lyrics enrichment using Musixmatch with DeepSeek analysis"""
        try:
            top_tracks = enriched_data.profile.metadata.get('top_tracks', [])
            if not top_tracks:
                logger.info("No top tracks available for lyrics analysis")
                return
            
            lyrics_analyses = []
            artist_name = enriched_data.profile.name
            
            # Analyze top 5 tracks (or fewer if not available)
            for track in top_tracks[:5]:
                track_name = track.get('name', '')
                if not track_name:
                    continue
                
                logger.info(f"🎤 Getting lyrics for: {track_name} by {artist_name}")
                
                # Get lyrics from Musixmatch
                lyrics_text = await self._get_musixmatch_lyrics_enhanced(artist_name, track_name)
                
                if lyrics_text:
                    # Analyze lyrics with DeepSeek if available
                    if self.ai_cleaner and self.ai_cleaner.is_available():
                        analysis = await self._analyze_lyrics_with_deepseek(lyrics_text, track_name, artist_name)
                        if analysis:
                            lyrics_analyses.append(analysis)
                            logger.info(f"✅ Analyzed lyrics for: {track_name}")
                    else:
                        # Fallback to simple analysis
                        simple_analysis = self._simple_lyrics_analysis(lyrics_text, track_name)
                        lyrics_analyses.append(simple_analysis)
                        logger.info(f"✅ Simple analysis for: {track_name}")
                else:
                    logger.warning(f"⚠️ Could not find lyrics for: {track_name}")
            
            # Combine analyses and store
            if lyrics_analyses:
                themes = self._combine_lyrics_analyses(lyrics_analyses)
                enriched_data.profile.metadata['lyrics_themes'] = themes
                enriched_data.profile.metadata['lyrics_analysis_count'] = len(lyrics_analyses)
                logger.info(f"✅ Lyrics analysis complete: {themes}")
            else:
                logger.warning("⚠️ No lyrics analyses available")
                
        except Exception as e:
            logger.error(f"❌ Musixmatch lyrics enrichment error: {str(e)}")
    
    async def _get_musixmatch_lyrics_enhanced(self, artist_name: str, track_name: str) -> str:
        """Enhanced Musixmatch lyrics extraction with human verification bypass"""
        try:
            # Clean names for URL formatting (Musixmatch format: artist-name/song-name)
            clean_artist = re.sub(r'[^a-zA-Z0-9\s]', '', artist_name).replace(' ', '-').lower()
            clean_track = re.sub(r'[^a-zA-Z0-9\s]', '', track_name).replace(' ', '-').lower()
            
            # Correct Musixmatch URL format (note: no www subdomain)
            urls_to_try = [
                f"https://musixmatch.com/lyrics/{clean_artist}/{clean_track}",
                f"https://musixmatch.com/lyrics/{clean_artist.replace('-', '')}/{clean_track.replace('-', '')}",
                f"https://musixmatch.com/lyrics/{artist_name.replace(' ', '-').lower()}/{track_name.replace(' ', '-').lower()}"
            ]
            
            for url in urls_to_try:
                try:
                    logger.debug(f"Trying Musixmatch URL: {url}")
                    
                    crawler_config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        wait_until="domcontentloaded",
                        page_timeout=25000,  # Longer timeout for verification handling
                        delay_before_return_html=4.0,  # More time for page processing
                        js_code="""
                        // Enhanced Musixmatch verification bypass and lyrics extraction
                        console.log('Starting Musixmatch lyrics extraction...');
                        
                        // Wait for initial page load
                        await new Promise(resolve => setTimeout(resolve, 4000));
                        
                        // Handle human verification prompts
                        const verificationElements = [
                            '[data-testid="captcha"]',
                            '.captcha',
                            '[class*="verification"]',
                            '[class*="human"]',
                            '.cloudflare-challenge',
                            '#challenge-form',
                            '.challenge-form'
                        ];
                        
                        let verificationFound = false;
                        for (const selector of verificationElements) {
                            const element = document.querySelector(selector);
                            if (element && element.offsetParent !== null) {
                                console.log('Human verification detected:', selector);
                                verificationFound = true;
                                break;
                            }
                        }
                        
                        if (verificationFound) {
                            console.log('Attempting to handle verification...');
                            // Wait longer and try to bypass
                            await new Promise(resolve => setTimeout(resolve, 5000));
                            
                            // Try clicking through verification if possible
                            const continueButtons = document.querySelectorAll('button[type="submit"], input[type="submit"], .btn-continue, [class*="continue"]');
                            for (const btn of continueButtons) {
                                if (btn.textContent.toLowerCase().includes('continue') || 
                                    btn.textContent.toLowerCase().includes('proceed')) {
                                    try {
                                        btn.click();
                                        await new Promise(resolve => setTimeout(resolve, 3000));
                                        break;
                                    } catch(e) {}
                                }
                            }
                        }
                        
                        // Close any modal overlays or cookie banners
                        const overlaySelectors = [
                            '[data-testid="modal-close"]',
                            '.close-btn',
                            '.modal-close',
                            '[aria-label="Close"]',
                            '.cookie-banner button',
                            '[class*="cookie"] button',
                            '.gdpr-accept',
                            '[class*="accept"]'
                        ];
                        
                        for (const selector of overlaySelectors) {
                            const buttons = document.querySelectorAll(selector);
                            buttons.forEach(btn => {
                                try { 
                                    if (btn.offsetParent !== null) {
                                        btn.click(); 
                                    }
                                } catch(e) {}
                            });
                        }
                        
                        // Wait for content to settle
                        await new Promise(resolve => setTimeout(resolve, 2000));
                        
                        console.log('Musixmatch page processing complete');
                        """,
                        magic=True,
                        simulate_user=True
                    )
                    
                    async with AsyncWebCrawler(config=self.browser_config) as crawler:
                        result = await crawler.arun(url=url, config=crawler_config)
                        
                        if result.success and result.html:
                            # Enhanced lyrics extraction patterns
                            lyrics_patterns = [
                                r'<span[^>]*class="lyrics__content[^"]*"[^>]*>([^<]+)</span>',
                                r'<span[^>]*data-testid="lyrics-line"[^>]*>([^<]+)</span>',
                                r'<p[^>]*class="[^"]*lyrics[^"]*"[^>]*>([^<]+)</p>',
                                r'"lyrics":\s*"([^"]+)"',
                                r'<div[^>]*class="[^"]*lyrics[^"]*"[^>]*>([^<]+)</div>',
                            ]
                            
                            all_lyrics_parts = []
                            
                            for pattern in lyrics_patterns:
                                matches = re.findall(pattern, result.html, re.DOTALL | re.IGNORECASE)
                                if matches:
                                    # Clean and combine lyrics parts
                                    clean_parts = []
                                    for match in matches:
                                        clean_part = re.sub(r'<[^>]+>', '', match).strip()
                                        if len(clean_part) > 3 and clean_part not in clean_parts:
                                            clean_parts.append(clean_part)
                                    
                                    if clean_parts:
                                        all_lyrics_parts.extend(clean_parts)
                                        break
                            
                            if all_lyrics_parts:
                                full_lyrics = ' '.join(all_lyrics_parts)
                                if len(full_lyrics) > 50:  # Ensure substantial lyrics content
                                    logger.info(f"✅ Found lyrics from Musixmatch ({len(full_lyrics)} chars)")
                                    return full_lyrics[:2000]  # Limit length
                                    
                except Exception as e:
                    logger.debug(f"Failed to get lyrics from {url}: {e}")
                    continue
            
            logger.warning(f"⚠️ Could not extract lyrics for {track_name} by {artist_name}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Musixmatch lyrics extraction error: {str(e)}")
            return None
    
    async def _analyze_lyrics_with_deepseek(self, lyrics: str, track_name: str, artist_name: str) -> Dict[str, Any]:
        """Analyze lyrics using DeepSeek for sentiment and themes"""
        try:
            if not self.ai_cleaner or not self.ai_cleaner.is_available():
                return None
            
            # Use the AI cleaner's capabilities for lyrics analysis
            # Create a simple analysis task using the existing AI cleaner infrastructure
            
            # For now, fall back to simple analysis since we'd need to add lyrics analysis to AIDataCleaner
            logger.info(f"🤖 Using simple analysis for lyrics (DeepSeek integration pending)")
            return self._simple_lyrics_analysis(lyrics, track_name)
            
        except Exception as e:
            logger.error(f"DeepSeek lyrics analysis error: {e}")
            # Fallback to simple analysis
            return self._simple_lyrics_analysis(lyrics, track_name)
    
    def _simple_lyrics_analysis(self, lyrics: str, track_name: str) -> Dict[str, Any]:
        """Simple keyword-based lyrics analysis as fallback"""
        try:
            lyrics_lower = lyrics.lower()
            
            # Define keyword categories
            themes = {
                "love": ["love", "heart", "baby", "kiss", "forever", "together", "romance"],
                "party": ["party", "dance", "club", "night", "fun", "celebrate", "drinks"],
                "success": ["money", "rich", "success", "fame", "win", "top", "boss"],
                "sadness": ["sad", "cry", "tears", "pain", "hurt", "broken", "alone"],
                "empowerment": ["strong", "power", "fight", "rise", "overcome", "believe"]
            }
            
            # Count theme occurrences
            theme_scores = {}
            for theme, keywords in themes.items():
                score = sum(1 for keyword in keywords if keyword in lyrics_lower)
                if score > 0:
                    theme_scores[theme] = score
            
            # Determine primary theme
            primary_theme = max(theme_scores, key=theme_scores.get) if theme_scores else "general"
            
            # Simple sentiment
            positive_words = ["love", "happy", "good", "great", "amazing", "wonderful"]
            negative_words = ["sad", "bad", "hurt", "pain", "cry", "broken"]
            
            pos_count = sum(1 for word in positive_words if word in lyrics_lower)
            neg_count = sum(1 for word in negative_words if word in lyrics_lower)
            
            if pos_count > neg_count:
                sentiment = "positive"
            elif neg_count > pos_count:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            
            return {
                "track": track_name,
                "theme": f"Song explores themes of {primary_theme}",
                "sentiment": sentiment,
                "tags": list(theme_scores.keys())[:5],
                "mood": primary_theme,
                "analysis_source": "simple"
            }
            
        except Exception as e:
            logger.error(f"Simple lyrics analysis error: {e}")
            return {
                "track": track_name,
                "theme": "Unable to analyze lyrics",
                "sentiment": "neutral",
                "tags": [],
                "mood": "unknown",
                "analysis_source": "error"
            }
    
    def _validate_social_links_consistency(self, enriched_data: EnrichedArtistData):
        """Validate social media links consistency between YouTube and Spotify data"""
        try:
            spotify_links = enriched_data.profile.social_links or {}
            youtube_links = enriched_data.profile.metadata.get('youtube_social_links', {})
            
            validated_links = {}
            inconsistencies = []
            
            # Check each platform for consistency
            for platform in ['instagram', 'twitter', 'facebook']:
                spotify_link = spotify_links.get(platform)
                youtube_link = youtube_links.get(platform)
                
                if spotify_link and youtube_link:
                    # Extract usernames for comparison
                    spotify_username = self._extract_username_from_url(spotify_link, platform)
                    youtube_username = self._extract_username_from_url(youtube_link, platform)
                    
                    if spotify_username and youtube_username:
                        if spotify_username.lower() == youtube_username.lower():
                            validated_links[platform] = spotify_link  # Prefer Spotify link (usually more accurate)
                            logger.info(f"✅ {platform} link validated: {spotify_username}")
                        else:
                            # Inconsistency detected
                            inconsistencies.append({
                                "platform": platform,
                                "spotify": spotify_link,
                                "youtube": youtube_link,
                                "spotify_username": spotify_username,
                                "youtube_username": youtube_username
                            })
                            # Use Spotify link as primary (typically more reliable)
                            validated_links[platform] = spotify_link
                            logger.warning(f"⚠️ {platform} link inconsistency: Spotify={spotify_username}, YouTube={youtube_username}")
                elif spotify_link:
                    validated_links[platform] = spotify_link
                elif youtube_link:
                    validated_links[platform] = youtube_link
            
            # Update with validated links
            enriched_data.profile.social_links.update(validated_links)
            
            if inconsistencies:
                enriched_data.profile.metadata['social_link_inconsistencies'] = inconsistencies
                logger.info(f"🔍 Found {len(inconsistencies)} social link inconsistencies (using Spotify as primary)")
            else:
                logger.info("✅ All social links are consistent between platforms")
                
        except Exception as e:
            logger.error(f"❌ Social link validation error: {str(e)}")
    
    def _extract_username_from_url(self, url: str, platform: str) -> str:
        """Extract username from social media URL"""
        try:
            if not url:
                return ""
            
            # Remove protocol and www
            clean_url = url.lower().replace('https://', '').replace('http://', '').replace('www.', '')
            
            if platform == 'instagram':
                # instagram.com/username or instagram.com/username/
                match = re.search(r'instagram\.com/([^/?]+)', clean_url)
                return match.group(1) if match else ""
            elif platform == 'twitter':
                # twitter.com/username or x.com/username
                match = re.search(r'(?:twitter|x)\.com/([^/?]+)', clean_url)
                return match.group(1) if match else ""
            elif platform == 'facebook':
                # facebook.com/username
                match = re.search(r'facebook\.com/([^/?]+)', clean_url)
                return match.group(1) if match else ""
            
            return ""
            
        except Exception:
            return ""
    
    def _extract_spotify_tracks(self, html: str) -> List[Dict[str, Any]]:
        """Extract top tracks from Spotify HTML with enhanced patterns and debug logging"""
        tracks = []
        
        logger.debug(f"Extracting tracks from HTML of length: {len(html)}")
        
        # Multiple patterns for track extraction - updated for current Spotify structure
        track_patterns = [
            # Pattern 1: Modern Spotify track links with aria-label
            r'<a[^>]*aria-label="([^"]+)"[^>]*href="/track/[^"]*"[^>]*>',
            # Pattern 2: Track title in data attributes
            r'data-testid="track-title"[^>]*>([^<]+)<',
            # Pattern 3: JSON-LD structured data
            r'"name":\s*"([^"]+)"[^}]*"@type":\s*"MusicRecording"',
            # Pattern 4: Track names in JavaScript variables
            r'trackName["\']:\s*["\']([^"\']+)["\']',
            # Pattern 5: Popular tracks section
            r'<div[^>]*class="[^"]*track[^"]*"[^>]*>[^<]*<[^>]*>([^<]+)</[^>]*>',
            # Pattern 6: Simple track link patterns
            r'<a[^>]*href="/track/[^"]*"[^>]*title="([^"]+)"',
            # Pattern 7: Track names in span elements
            r'<span[^>]*class="[^"]*track-name[^"]*"[^>]*>([^<]+)</span>',
            # Pattern 8: Alternative JSON patterns
            r'"trackName":\s*"([^"]+)"',
            # Pattern 9: Track metadata
            r'<meta[^>]*property="music:song"[^>]*content="([^"]+)"',
            # Pattern 10: Broad search for any music-related content
            r'(?:song|track|music)[^>]*>([^<]{3,50})</[^>]*>',
        ]
        
        for pattern_idx, pattern in enumerate(track_patterns):
            try:
                matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
                if matches:
                    logger.debug(f"Pattern {pattern_idx + 1} found {len(matches)} potential tracks")
                    
                    for i, match in enumerate(matches[:20]):  # Get up to 20 potential tracks
                        # Clean track name based on pattern type
                        if pattern_idx == 0:  # aria-label pattern
                            # Extract just the song name from "Song by Artist" format
                            if ' by ' in match:
                                track_name = match.split(' by ')[0].strip()
                            elif ' - ' in match:
                                track_name = match.split(' - ')[0].strip()
                            else:
                                track_name = match.strip()
                        else:
                            track_name = match.strip()
                        
                        # Validate track name
                        if (len(track_name) > 2 and 
                            len(track_name) < 100 and  # Reasonable length
                            not track_name.lower().startswith(('http', 'www', 'spotify')) and
                            track_name not in [t['name'] for t in tracks]):
                            
                            tracks.append({
                                "name": track_name,
                                "position": len(tracks) + 1,
                                "source": f"pattern_{pattern_idx + 1}",
                                "confidence": 0.8 if pattern_idx < 3 else 0.6  # Higher confidence for better patterns
                            })
                    
                    # If we found good tracks with high-confidence patterns, use them
                    if tracks and pattern_idx < 5:
                        logger.info(f"Found {len(tracks)} tracks using pattern {pattern_idx + 1}")
                        break
                        
            except Exception as e:
                logger.warning(f"Error with pattern {pattern_idx + 1}: {e}")
                continue
        
        # If no tracks found with specific patterns, try a more general approach
        if not tracks:
            logger.debug("No tracks found with specific patterns, trying general extraction")
            
            # Look for any text that might be song titles
            general_patterns = [
                r'<[^>]*>([A-Z][^<]{2,40})</[^>]*>',  # Capitalized text in tags
                r'"([A-Z][^"]{2,40})"',  # Quoted capitalized text
            ]
            
            potential_tracks = set()
            for pattern in general_patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    clean_match = match.strip()
                    # Filter for likely song titles
                    if (3 <= len(clean_match) <= 50 and
                        not any(word in clean_match.lower() for word in 
                               ['spotify', 'playlist', 'album', 'artist', 'follow', 'play', 'pause', 'next', 'previous']) and
                        not clean_match.startswith(('http', 'www', '@', '#'))):
                        potential_tracks.add(clean_match)
            
            # Convert to track format
            for i, track_name in enumerate(list(potential_tracks)[:10]):
                tracks.append({
                    "name": track_name,
                    "position": i + 1,
                    "source": "general_extraction",
                    "confidence": 0.3  # Lower confidence
                })
        
        # Enhanced extraction: Look for play counts and popularity
        for track in tracks:
            # Try to find play count for this track
            play_count_patterns = [
                rf'{re.escape(track["name"])}[^<]*<[^>]*>([0-9,]+)\s*plays',
                rf'track.*{re.escape(track["name"])}.*"playCount":(\d+)',
                rf'{re.escape(track["name"])}[^0-9]*([0-9,]+)[^0-9]*plays',
            ]
            
            for pattern in play_count_patterns:
                try:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    if matches:
                        track['play_count'] = self._parse_number(matches[0])
                        break
                except:
                    continue
        
        # Remove duplicates and sort by confidence/position
        unique_tracks = []
        seen_names = set()
        
        # Sort by confidence first, then by position
        tracks.sort(key=lambda x: (-x.get('confidence', 0), x.get('position', 999)))
        
        for track in tracks[:10]:  # Limit to top 10
            track_name_lower = track['name'].lower()
            if track_name_lower not in seen_names:
                seen_names.add(track_name_lower)
                unique_tracks.append(track)
        
        logger.info(f"✅ Extracted {len(unique_tracks)} unique tracks from Spotify")
        if unique_tracks:
            logger.debug(f"Top tracks: {[t['name'] for t in unique_tracks[:3]]}")
        else:
            logger.warning("⚠️ No tracks extracted - this may prevent lyrics analysis")
            # Save a sample of HTML for debugging
            sample_html = html[:1000] + "..." if len(html) > 1000 else html
            logger.debug(f"HTML sample: {sample_html}")
        
        return unique_tracks
    
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
        """Calculate a 0-1 score representing data completeness"""
        score = 0.0
        
        # Spotify data (30% weight)
        if data.profile.follower_counts.get('spotify_monthly_listeners'):
            score += 0.15
        if data.profile.metadata.get('top_tracks'):
            score += 0.15
        
        # Social media data (40% weight)
        if data.profile.follower_counts.get('instagram'):
            score += 0.20
        if data.profile.follower_counts.get('tiktok'):
            score += 0.10
        if data.profile.metadata.get('tiktok_likes'):
            score += 0.10
        
        # Profile completeness (30% weight)
        if data.profile.bio:
            score += 0.10
        if data.profile.genres:
            score += 0.10
        if data.profile.social_links:
            score += 0.10
        
        return min(score, 1.0)
    
    async def _clean_platform_data(self, platform: str, raw_data: Dict[str, Any]) -> Optional[object]:
        """
        Clean platform data using AI.
        """
        if not raw_data or not self.ai_cleaner or not self.ai_cleaner.is_available():
            return None
        
        try:
            cleaned_data = await self.ai_cleaner.clean_platform_data(platform, raw_data)
            if cleaned_data and cleaned_data.confidence_score >= 0.6:
                logger.info(f"📱 AI cleaned {platform} data (confidence: {cleaned_data.confidence_score:.2f})")
                return cleaned_data
            else:
                logger.warning(f"⚠️ Low confidence {platform} data cleaning")
                return cleaned_data
                
        except Exception as e:
            logger.warning(f"⚠️ AI {platform} data cleaning failed: {e}")
            return None
    
    def get_cost_estimate(self, artist_profile: ArtistProfile) -> Dict[str, Any]:
        """
        Estimate the cost of enriching an artist profile
        
        Args:
            artist_profile: The artist profile to enrich
            
        Returns:
            Dictionary with cost breakdown and estimates
        """
        # Crawl4AI is completely free - no API costs
        tasks = []
        
        # Count expected scraping tasks
        if artist_profile.spotify_url or artist_profile.spotify_id:
            tasks.append("Spotify artist page")
        else:
            tasks.append("Spotify search + artist page")
        
        if artist_profile.instagram_url:
            tasks.append("Instagram profile")
        
        if artist_profile.tiktok_url:
            tasks.append("TikTok profile")
        
        # Add lyrics scraping tasks
        tasks.extend(["Musixmatch lyrics (up to 3 songs)", "Genius lyrics (backup)"])
        
        # DeepSeek API cost for lyrics analysis (only real cost)
        lyrics_analysis_cost = 0.002  # ~$0.002 per analysis
        total_deepseek_cost = lyrics_analysis_cost * 3  # Up to 3 songs
        
        return {
            "total_cost_usd": total_deepseek_cost,
            "cost_breakdown": {
                "crawl4ai_scraping": 0.00,  # Completely free
                "deepseek_lyrics_analysis": total_deepseek_cost,
            },
            "estimated_duration_seconds": len(tasks) * 3,  # ~3 seconds per task
            "scraping_tasks": tasks,
            "cost_comparison": {
                "vs_firecrawl": f"${0.05 * len(tasks):.3f} saved",  # Firecrawl was ~$0.05 per scrape
                "vs_apify": f"${0.10 * len(tasks):.3f} saved",      # Apify was ~$0.10 per scrape
            },
            "notes": [
                "Crawl4AI scraping is completely free",
                "Only cost is DeepSeek API for lyrics analysis",
                "Significant savings compared to paid scraping services",
                "No rate limits or quotas"
            ]
        }
    
    async def validate_extraction_schemas(self) -> Dict[str, Any]:
        """
        Test the effectiveness of extraction schemas on sample pages
        
        Returns:
            Validation results for each platform
        """
        validation_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "platforms": {}
        }
        
        # Test URLs for validation (use public profiles that are likely to be stable)
        test_profiles = {
            "spotify": "https://open.spotify.com/artist/4q3ewBCX7sLwd24euuV69X",  # Bad Bunny - popular stable profile
            "instagram": "https://instagram.com/badgalriri",  # Rihanna - stable profile
            "tiktok": "https://tiktok.com/@charlidamelio",  # Charlie D'Amelio - stable profile
            "musixmatch": "https://www.musixmatch.com/lyrics/Bad-Bunny/Titi-Me-Pregunto"  # Popular song
        }
        
        logger.info("🧪 Starting extraction schema validation...")
        
        # Test each platform
        for platform, test_url in test_profiles.items():
            try:
                logger.info(f"Testing {platform} extraction...")
                
                # Use appropriate extraction schema
                if platform == "spotify":
                    schema = {
                        "name": "Spotify Test",
                        "fields": [
                            {"name": "artist_name", "selector": "h1[data-testid='artist-name'], h1[data-testid='entityTitle']", "type": "text"},
                            {"name": "monthly_listeners", "selector": "div[data-testid='monthly-listeners'], .monthly-listeners-label", "type": "text"}
                        ]
                    }
                elif platform == "instagram":
                    schema = {
                        "name": "Instagram Test", 
                        "fields": [
                            {"name": "username", "selector": "h2, h1, [data-testid='user-title']", "type": "text"},
                            {"name": "follower_count", "selector": "a[href*='followers/'] span", "type": "text"}
                        ]
                    }
                elif platform == "tiktok":
                    schema = {
                        "name": "TikTok Test",
                        "fields": [
                            {"name": "username", "selector": "h1, h2, [data-e2e='user-title']", "type": "text"},
                            {"name": "follower_count", "selector": "[data-e2e='followers-count'], .tiktok-counter strong", "type": "text"}
                        ]
                    }
                elif platform == "musixmatch":
                    schema = {
                        "name": "Musixmatch Test",
                        "fields": [
                            {"name": "song_title", "selector": "h1, .mxm-track-title", "type": "text"},
                            {"name": "lyrics", "selector": ".lyrics__content span, [data-testid='lyrics-line']", "type": "list"}
                        ]
                    }
                
                extraction_strategy = JsonCssExtractionStrategy(schema)
                
                crawler_config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    extraction_strategy=extraction_strategy,
                    wait_for="css:h1, css:h2, css:main",
                    timeout=10  # Shorter timeout for validation
                )
                
                async with AsyncWebCrawler(config=self.browser_config) as crawler:
                    result = await crawler.arun(
                        url=test_url,
                        config=crawler_config
                    )
                    
                    if result.success:
                        extracted_data = {}
                        if result.extracted_content:
                            try:
                                extracted_data = json.loads(result.extracted_content)
                            except:
                                pass
                        
                        # Evaluate extraction quality
                        fields_extracted = len([k for k, v in extracted_data.items() if v])
                        total_fields = len(schema["fields"])
                        success_rate = (fields_extracted / total_fields) * 100 if total_fields > 0 else 0
                        
                        validation_results["platforms"][platform] = {
                            "status": "success" if success_rate > 50 else "partial",
                            "success_rate": f"{success_rate:.1f}%",
                            "fields_extracted": fields_extracted,
                            "total_fields": total_fields,
                            "extracted_data": extracted_data,
                            "selectors_tested": len(schema["fields"])
                        }
                        
                        logger.info(f"✅ {platform}: {success_rate:.1f}% extraction success")
                    else:
                        validation_results["platforms"][platform] = {
                            "status": "failed",
                            "error": result.error_message or "Unknown error",
                            "success_rate": "0%"
                        }
                        logger.warning(f"❌ {platform}: Extraction failed")
                        
            except Exception as e:
                validation_results["platforms"][platform] = {
                    "status": "error",
                    "error": str(e),
                    "success_rate": "0%"
                }
                logger.error(f"❌ {platform}: Validation error - {str(e)}")
        
        # Calculate overall score
        success_rates = [
            float(p.get("success_rate", "0%").replace("%", ""))
            for p in validation_results["platforms"].values()
            if p.get("success_rate") != "0%"
        ]
        
        validation_results["overall_score"] = f"{sum(success_rates) / len(success_rates) if success_rates else 0:.1f}%"
        validation_results["platforms_tested"] = len(test_profiles)
        validation_results["platforms_successful"] = len([p for p in validation_results["platforms"].values() if p.get("status") == "success"])
        
        logger.info(f"🎯 Validation complete: {validation_results['overall_score']} overall success rate")
        return validation_results 