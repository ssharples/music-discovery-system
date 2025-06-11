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
            viewport_height=1080
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
        
        # Spotify enrichment - search and enrich based on artist name
        tasks.append(self._search_and_enrich_spotify(artist_profile.name, enriched_data))
        
        # Social media enrichment (if links available)
        if hasattr(artist_profile, 'social_links') and artist_profile.social_links:
            if 'instagram' in artist_profile.social_links:
                tasks.append(self._enrich_instagram(artist_profile.social_links['instagram'], enriched_data))
            if 'tiktok' in artist_profile.social_links:
                tasks.append(self._enrich_tiktok(artist_profile.social_links['tiktok'], enriched_data))
        
        # Run all enrichments in parallel
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate enrichment score and update profile
        enriched_data.enrichment_score = self._calculate_enrichment_score(enriched_data)
        enriched_data.profile.enrichment_score = enriched_data.enrichment_score
        
        logger.info(f"✅ Enrichment complete for {artist_profile.name} (score: {enriched_data.enrichment_score})")
        return enriched_data
    
    async def _enrich_spotify(self, artist_profile: ArtistProfile, enriched_data: EnrichedArtistData):
        """Enrich with Spotify data using flexible extraction approach"""
        try:
            spotify_url = artist_profile.spotify_url
            if not spotify_url and artist_profile.spotify_id:
                spotify_url = f"https://open.spotify.com/artist/{artist_profile.spotify_id}"
            
            if not spotify_url:
                logger.warning("⚠️ No Spotify URL available for enrichment")
                return
                
            logger.info(f"🎵 Crawling Spotify: {spotify_url}")
            
            # Flexible crawler config - don't wait for specific elements
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_until="domcontentloaded",  # Don't wait for specific elements
                page_timeout=15000,  # Shorter timeout
                delay_before_return_html=4.0,  # Wait for content to load
                js_code="""
                // Wait for page load and scroll to load content
                await new Promise(resolve => setTimeout(resolve, 3000));
                window.scrollTo(0, 500);
                await new Promise(resolve => setTimeout(resolve, 1000));
                console.log('Spotify artist page loaded');
                """,
                verbose=True
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=spotify_url,
                    config=crawler_config
                )
                
                if result.success and result.html:
                    # Use regex patterns to extract data - more reliable than selectors
                    import re
                    
                    # Extract monthly listeners using multiple patterns
                    monthly_listeners = 0
                    listener_patterns = [
                        r'([\d,]+)\s*monthly\s*listeners?',  # "X monthly listeners"
                        r'monthly\s*listeners?[:\s]*([\d,]+)',  # "monthly listeners: X"
                        r'"monthlyListeners":(\d+)',  # JSON data
                        r'monthlyListeners["\s:]+(\d+)',  # Alternative JSON
                        r'([\d,]+)\s*listeners\s*monthly',  # Alternative format
                    ]
                    
                    for pattern in listener_patterns:
                        matches = re.findall(pattern, result.html, re.IGNORECASE)
                        if matches:
                            try:
                                # Take the first reasonable match
                                for match in matches:
                                    parsed = self._parse_number(match)
                                    if 0 < parsed < 1000000000:  # Reasonable range
                                        monthly_listeners = parsed
                                        break
                                if monthly_listeners > 0:
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    if monthly_listeners > 0:
                        enriched_data.profile.follower_counts['spotify_monthly_listeners'] = monthly_listeners
                        logger.info(f"✅ Found {monthly_listeners:,} monthly listeners")
                    else:
                        logger.warning("⚠️ Could not extract Spotify monthly listeners")
                    
                    # Extract artist bio using patterns
                    bio_patterns = [
                        r'<div[^>]*data-testid[^>]*biography[^>]*>([^<]+)',
                        r'<div[^>]*about[^>]*>([^<]+)',
                        r'"biography":\s*"([^"]+)"',
                        r'artist[_-]?bio[^>]*>([^<]+)',
                        r'description[^>]*>([^<]+)',
                    ]
                    
                    for pattern in bio_patterns:
                        matches = re.findall(pattern, result.html, re.IGNORECASE | re.DOTALL)
                        if matches:
                            # Take first non-empty match
                            for match in matches:
                                clean_bio = re.sub(r'<[^>]+>', '', match).strip()
                                if len(clean_bio) > 20:  # Reasonable bio length
                                    enriched_data.profile.bio = clean_bio[:500]
                                    logger.info("✅ Found artist bio")
                                    break
                            if enriched_data.profile.bio:
                                break
                    
                    # Extract top tracks using patterns
                    tracks = self._extract_spotify_tracks(result.html)
                    if tracks:
                        enriched_data.profile.metadata['top_tracks'] = tracks[:5]
                        logger.info(f"✅ Found {len(tracks)} tracks")
                        
                        # Analyze lyrics for top tracks
                        await self._enrich_lyrics(enriched_data)
                    
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
            search_url = f"https://open.spotify.com/search/{artist_name.replace(' ', '%20')}/artists"
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
    
    async def _enrich_instagram(self, instagram_url: str, enriched_data: EnrichedArtistData):
        """Enrich with Instagram data using multiple extraction strategies"""
        try:
            logger.info(f"📸 Crawling Instagram: {instagram_url}")
            
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
                wait_for="css:header, css:main, css:h1, css:[data-testid='user-title']",
                js_code="""
                // Wait for page load and scroll slightly to trigger content
                await new Promise(resolve => setTimeout(resolve, 3000));
                window.scrollTo(0, 300);
                await new Promise(resolve => setTimeout(resolve, 2000));
                """
            )
            
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
                    
                    instagram_followers = enriched_data.profile.follower_counts.get('instagram', 0)
                    if instagram_followers:
                        logger.info(f"✅ Instagram followers: {instagram_followers:,}")
                    else:
                        logger.warning("⚠️ Could not extract Instagram follower count")
                    
        except Exception as e:
            logger.error(f"❌ Instagram enrichment error: {str(e)}")
    
    async def _enrich_tiktok(self, tiktok_url: str, enriched_data: EnrichedArtistData):
        """Enrich with TikTok data using robust extraction"""
        try:
            logger.info(f"🎭 Crawling TikTok: {tiktok_url}")
            
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
                wait_for="css:h1, css:h2, css:[data-e2e='user-title'], css:.user-title, css:.share-title-container",
                js_code="""
                // Wait for page load and try to trigger any lazy loading
                await new Promise(resolve => setTimeout(resolve, 4000));
                window.scrollTo(0, 500);
                await new Promise(resolve => setTimeout(resolve, 2000));
                """
            )
            
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
        """Extract lyrics from Musixmatch"""
        try:
            musixmatch_url = f"https://www.musixmatch.com/lyrics/{clean_artist}/{clean_track}"
            
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
                wait_for="css:.lyrics__content, css:.mxm-lyrics, css:[data-testid='lyrics-line'], css:.lyrics-line-text",
                js_code="""
                // Wait for lyrics to load and handle any overlays
                await new Promise(resolve => setTimeout(resolve, 3000));
                
                // Try to close any modal/overlay
                const closeButtons = document.querySelectorAll('[data-testid="modal-close"], .close-btn, .modal-close');
                closeButtons.forEach(btn => btn.click());
                
                await new Promise(resolve => setTimeout(resolve, 1000));
                """
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=musixmatch_url,
                    config=crawler_config
                )
                
                if result.success:
                    # Try structured extraction
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
                wait_for="css:[data-lyrics-container], css:.lyrics",
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