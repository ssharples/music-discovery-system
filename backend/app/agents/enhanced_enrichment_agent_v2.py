"""
Enhanced Enrichment Agent V2 with comprehensive Firecrawl and Spotify integration
Implements:
1. Spotify artist validation via Instagram links
2. Spotify profile scraping (monthly listeners, top cities, bio)
3. Instagram follower count and link in bio extraction
4. Lyrics scraping and analysis
5. Enhanced Spotify API integration (genres, avatar)
"""
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Tuple
import logging
import json
import re
import asyncio
import sys
from datetime import datetime
import os
import time
from urllib.parse import urlparse, urljoin
import requests

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile, LyricAnalysis

# Initialize logger first
logger = logging.getLogger(__name__)

# Import Firecrawl if available
try:
    logger.info(f"🔥 FIRECRAWL DEBUG: Python path: {sys.path[:3]}...")
    logger.info(f"🔥 FIRECRAWL DEBUG: Attempting primary firecrawl import...")
    from firecrawl import FirecrawlApp, JsonConfig
    FIRECRAWL_AVAILABLE = True
    FIRECRAWL_IMPORT_ERROR = None
    logger.info(f"🔥 FIRECRAWL DEBUG: Primary import successful!")
except ImportError as e:
    logger.info(f"🔥 FIRECRAWL DEBUG: Primary import failed: {str(e)}")
    try:
        logger.info(f"🔥 FIRECRAWL DEBUG: Attempting secondary firecrawl import...")
        # Try alternative import path
        from firecrawl.firecrawl import FirecrawlApp
        FIRECRAWL_AVAILABLE = True
        FIRECRAWL_IMPORT_ERROR = None
        logger.info(f"🔥 FIRECRAWL DEBUG: Secondary import successful!")
    except ImportError as e2:
        logger.error(f"🔥 FIRECRAWL DEBUG: Both imports failed!")
        logger.error(f"🔥 FIRECRAWL DEBUG: Primary error: {str(e)}")
        logger.error(f"🔥 FIRECRAWL DEBUG: Secondary error: {str(e2)}")
        FIRECRAWL_AVAILABLE = False
        FIRECRAWL_IMPORT_ERROR = f"Primary: {str(e)}, Secondary: {str(e2)}"
        
        # Additional debugging
        logger.info(f"🔥 FIRECRAWL DEBUG: Checking installed packages...")
        try:
            import pkg_resources
            installed_packages = [d.project_name for d in pkg_resources.working_set]
            firecrawl_packages = [pkg for pkg in installed_packages if 'firecrawl' in pkg.lower()]
            logger.info(f"🔥 FIRECRAWL DEBUG: Found firecrawl packages: {firecrawl_packages}")
            
            # Also check pip list directly
            import subprocess
            result = subprocess.run(['pip', 'list'], capture_output=True, text=True)
            pip_output = result.stdout
            firecrawl_lines = [line for line in pip_output.split('\n') if 'firecrawl' in line.lower()]
            logger.info(f"🔥 FIRECRAWL DEBUG: Pip list firecrawl results: {firecrawl_lines}")
            
        except Exception as pkg_e:
            logger.info(f"🔥 FIRECRAWL DEBUG: Error checking packages: {pkg_e}")
except Exception as e:
    logger.error(f"🔥 FIRECRAWL DEBUG: Unexpected error during import: {str(e)}")
    FIRECRAWL_AVAILABLE = False
    FIRECRAWL_IMPORT_ERROR = f"Unexpected: {str(e)}"

class SpotifyArtistData(BaseModel):
    """Spotify artist data structure"""
    id: str
    name: str
    genres: List[str] = Field(default_factory=list)
    images: List[Dict[str, Any]] = Field(default_factory=list)
    followers: int = 0
    popularity: int = 0
    external_urls: Dict[str, str] = Field(default_factory=dict)

class InstagramProfileData(BaseModel):
    """Instagram profile data structure"""
    username: str
    follower_count: int = 0
    bio: Optional[str] = None
    link_in_bio: Optional[str] = None
    is_verified: bool = False
    has_spotify_link: bool = False
    spotify_url: Optional[str] = None

class SpotifyProfileData(BaseModel):
    """Spotify profile scraping data"""
    monthly_listeners: int = 0
    top_cities: List[Dict[str, Any]] = Field(default_factory=list)
    bio: Optional[str] = None
    verified: bool = False

class LyricalTheme(BaseModel):
    """Lyrical theme analysis result"""
    themes: List[str] = Field(default_factory=list)
    primary_theme: Optional[str] = None
    emotional_tone: Optional[str] = None
    subject_matter: List[str] = Field(default_factory=list)

class EnhancedEnrichmentAgentV2:
    """Enhanced enrichment agent with comprehensive features"""
    
    def __init__(self):
        self._ai_agent = None
        self._agent_creation_attempted = False
        self.firecrawl_app = None
        
        # Enhanced debugging for Firecrawl initialization
        logger.info(f"🔥 FIRECRAWL DEBUG: EnhancedEnrichmentAgentV2 initialization starting...")
        logger.info(f"🔥 FIRECRAWL DEBUG: FIRECRAWL_AVAILABLE = {FIRECRAWL_AVAILABLE}")
        if not FIRECRAWL_AVAILABLE:
            logger.error(f"🔥 FIRECRAWL DEBUG: Import error: {FIRECRAWL_IMPORT_ERROR}")
        logger.info(f"🔥 FIRECRAWL DEBUG: settings.FIRECRAWL_API_KEY exists = {bool(settings.FIRECRAWL_API_KEY)}")
        logger.info(f"🔥 FIRECRAWL DEBUG: settings.FIRECRAWL_API_KEY length = {len(settings.FIRECRAWL_API_KEY) if settings.FIRECRAWL_API_KEY else 0}")
        logger.info(f"🔥 FIRECRAWL DEBUG: settings.is_firecrawl_configured() = {settings.is_firecrawl_configured()}")
        
        if FIRECRAWL_AVAILABLE and settings.is_firecrawl_configured():
            try:
                logger.info(f"🔥 FIRECRAWL DEBUG: Attempting to initialize FirecrawlApp...")
                self.firecrawl_app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
                logger.info("✅ Firecrawl initialized successfully")
                logger.info(f"🔥 FIRECRAWL DEBUG: FirecrawlApp object created = {self.firecrawl_app is not None}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Firecrawl: {e}")
                logger.error(f"🔥 FIRECRAWL DEBUG: Exception type: {type(e).__name__}")
                logger.error(f"🔥 FIRECRAWL DEBUG: Exception details: {str(e)}")
        else:
            logger.warning(f"🔥 FIRECRAWL DEBUG: Firecrawl initialization skipped")
            logger.warning(f"🔥 FIRECRAWL DEBUG: - FIRECRAWL_AVAILABLE: {FIRECRAWL_AVAILABLE}")
            logger.warning(f"🔥 FIRECRAWL DEBUG: - is_firecrawl_configured(): {settings.is_firecrawl_configured()}")
            if not FIRECRAWL_AVAILABLE:
                logger.error(f"🔥 FIRECRAWL DEBUG: Firecrawl library import failed! Please check installation.")
            if not settings.is_firecrawl_configured():
                logger.error(f"🔥 FIRECRAWL DEBUG: Firecrawl API key not configured! Please set FIRECRAWL_API_KEY environment variable.")
    

    
    @property
    def ai_agent(self) -> Optional[Agent]:
        """Lazy initialization of AI agent"""
        if self._ai_agent is None and not self._agent_creation_attempted:
            self._agent_creation_attempted = True
            try:
                self._ai_agent = Agent(
                    model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
                    system_prompt="""You are a music industry analyst specializing in:
                    1. Analyzing lyrical themes and emotional content
                    2. Identifying musical genres and styles
                    3. Understanding artist branding and positioning
                    4. Extracting meaningful insights from artist data
                    
                    Provide concise, actionable insights focused on music industry relevance."""
                )
                logger.info("✅ AI agent initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize AI agent: {e}")
        return self._ai_agent
    
    async def enrich_artist_comprehensive(
        self,
        artist_profile: ArtistProfile,
        deps: PipelineDependencies
    ) -> Dict[str, Any]:
        """Comprehensive artist enrichment with all features"""
        
        logger.info(f"🎯 Starting comprehensive enrichment for {artist_profile.name}")
        logger.info(f"🔥 FIRECRAWL DEBUG: V2 Enrichment Agent initialized - Firecrawl available: {self.firecrawl_app is not None}")
        logger.info(f"🔥 FIRECRAWL DEBUG: AI Agent available: {self.ai_agent is not None}")
        
        # Ensure lyrical_themes is initialized to prevent validation errors
        if artist_profile.lyrical_themes is None:
            artist_profile.lyrical_themes = []
        
        enrichment_result = {
            "success": True,
            "artist_name": artist_profile.name,
            "spotify_validated": False,
            "instagram_enriched": False,
            "spotify_profile_scraped": False,
            "lyrics_analyzed": False,
            "errors": [],
            "data": {},
            "enriched_profile": artist_profile,  # Return the enriched profile
            "firecrawl_operations": []  # Track Firecrawl operations
        }
        
        logger.info(f"🔥 FIRECRAWL DEBUG: Starting enrichment pipeline for {artist_profile.name}")
        logger.info(f"🔥 FIRECRAWL DEBUG: Initial profile data - Instagram: {artist_profile.instagram_handle}, Spotify: {artist_profile.spotify_id}")
        
        try:
            # Step 1: Get Spotify artist data and validate
            logger.info(f"🔥 FIRECRAWL DEBUG: STEP 1 - Spotify API enrichment")
            spotify_data = await self._get_spotify_artist_data(deps, artist_profile)
            if spotify_data:
                enrichment_result["data"]["spotify"] = spotify_data
                enrichment_result["spotify_validated"] = True
                
                # Update artist profile with Spotify data
                artist_profile.spotify_id = spotify_data["id"]
                artist_profile.genres = spotify_data.get("genres", [])
                artist_profile.avatar_url = self._get_best_image_url(spotify_data.get("images", []))
                artist_profile.follower_counts["spotify"] = spotify_data.get("followers", 0)
                
                logger.info(f"✅ Spotify data retrieved for {artist_profile.name}")
                logger.info(f"🔥 FIRECRAWL DEBUG: Spotify enrichment completed - ID: {spotify_data['id']}, Followers: {spotify_data.get('followers', 0)}")
            else:
                logger.info(f"🔥 FIRECRAWL DEBUG: No Spotify data found for {artist_profile.name}")
            
            # Step 2: Scrape and validate Instagram using Firecrawl
            logger.info(f"🔥 FIRECRAWL DEBUG: STEP 2 - Instagram Firecrawl enrichment")
            if artist_profile.instagram_handle or self._find_instagram_handle(artist_profile):
                if self.firecrawl_app:
                    enrichment_result["firecrawl_operations"].append("instagram_profile")
                    # Add delay to avoid rate limiting
                    await asyncio.sleep(2)
                    instagram_data = await self._scrape_instagram_profile(artist_profile.instagram_handle)
                    if instagram_data:
                        enrichment_result["data"]["instagram"] = instagram_data
                        enrichment_result["instagram_enriched"] = True
                        
                        # Update artist profile
                        artist_profile.follower_counts["instagram"] = instagram_data.get("follower_count", 0)
                        
                        logger.info(f"🔥 FIRECRAWL DEBUG: Instagram enrichment completed - Followers: {instagram_data.get('follower_count', 0)}")
                        
                        # Extract contact info from link in bio
                        if instagram_data.get("link_in_bio"):
                            logger.info(f"🔥 FIRECRAWL DEBUG: Found link in bio: {instagram_data['link_in_bio']}")
                            enrichment_result["firecrawl_operations"].append("contact_extraction")
                            contact_info = await self._extract_contact_from_url(instagram_data["link_in_bio"])
                            if contact_info:
                                if contact_info.get("email"):
                                    artist_profile.email = contact_info["email"]
                                    logger.info(f"🔥 FIRECRAWL DEBUG: Email extracted: {contact_info['email']}")
                                if contact_info.get("location"):
                                    artist_profile.location = contact_info["location"]
                                    logger.info(f"🔥 FIRECRAWL DEBUG: Location extracted: {contact_info['location']}")
                        
                        # Validate Spotify if found in Instagram
                        if instagram_data.get("has_spotify_link") and spotify_data:
                            enrichment_result["spotify_validated"] = True
                            logger.info(f"✅ Spotify validated via Instagram for {artist_profile.name}")
                    else:
                        logger.info(f"🔥 FIRECRAWL DEBUG: Instagram scraping failed for {artist_profile.name}")
                else:
                    logger.warning(f"⚠️ Firecrawl not available, skipping Instagram enrichment for {artist_profile.name}")
            else:
                logger.info(f"🔥 FIRECRAWL DEBUG: No Instagram handle found for {artist_profile.name}")
            
            # Step 3: Scrape Spotify profile for additional data using Firecrawl
            logger.info(f"🔥 FIRECRAWL DEBUG: STEP 3 - Spotify profile Firecrawl scraping")
            if artist_profile.spotify_id and self.firecrawl_app:
                enrichment_result["firecrawl_operations"].append("spotify_profile")
                # Add delay to avoid rate limiting
                await asyncio.sleep(2)
                spotify_profile_data = await self._scrape_spotify_profile(artist_profile.spotify_id)
                if spotify_profile_data:
                    enrichment_result["data"]["spotify_profile"] = spotify_profile_data
                    enrichment_result["spotify_profile_scraped"] = True
                    
                    # Update artist bio if found
                    if spotify_profile_data.get("bio") and not artist_profile.bio:
                        artist_profile.bio = spotify_profile_data["bio"]
                        logger.info(f"🔥 FIRECRAWL DEBUG: Bio extracted from Spotify profile")
                    
                    # Store monthly listeners
                    artist_profile.metadata["monthly_listeners"] = spotify_profile_data.get("monthly_listeners", 0)
                    artist_profile.metadata["top_cities"] = spotify_profile_data.get("top_cities", [])
                    
                    logger.info(f"🔥 FIRECRAWL DEBUG: Spotify profile scraped - Monthly listeners: {spotify_profile_data.get('monthly_listeners', 0)}")
                else:
                    logger.info(f"🔥 FIRECRAWL DEBUG: Spotify profile scraping failed")
            else:
                logger.info(f"🔥 FIRECRAWL DEBUG: Skipping Spotify profile scraping - ID: {artist_profile.spotify_id}, Firecrawl: {self.firecrawl_app is not None}")
            
            # Step 4: Get top songs and analyze lyrics using Firecrawl
            logger.info(f"🔥 FIRECRAWL DEBUG: STEP 4 - Lyrics analysis via Firecrawl")
            if artist_profile.spotify_id:
                top_songs = await self._get_artist_top_songs(deps, artist_profile.spotify_id)
                logger.info(f"🔥 FIRECRAWL DEBUG: Retrieved {len(top_songs) if top_songs else 0} top songs")
                
                if top_songs and self.firecrawl_app:
                    enrichment_result["firecrawl_operations"].append("lyrics_scraping")
                    # Add delay to avoid rate limiting
                    await asyncio.sleep(3)
                    lyrical_themes = await self._analyze_song_lyrics(artist_profile.name, top_songs[:3])
                    if lyrical_themes:
                        enrichment_result["data"]["lyrical_analysis"] = lyrical_themes
                        enrichment_result["lyrics_analyzed"] = True
                        
                        # Update artist profile with themes - ensure it's a list
                        themes = lyrical_themes.get("themes", [])
                        if isinstance(themes, list):
                            artist_profile.lyrical_themes = themes
                            logger.info(f"🔥 FIRECRAWL DEBUG: Lyrical themes extracted: {themes}")
                        else:
                            artist_profile.lyrical_themes = []
                            logger.warning(f"Lyrical themes not in expected list format: {themes}")
                    else:
                        logger.info(f"🔥 FIRECRAWL DEBUG: Lyrics analysis failed - no themes extracted")
                else:
                    logger.info(f"🔥 FIRECRAWL DEBUG: Skipping lyrics analysis - Songs: {len(top_songs) if top_songs else 0}, Firecrawl: {self.firecrawl_app is not None}")
            else:
                logger.info(f"🔥 FIRECRAWL DEBUG: No Spotify ID available for lyrics analysis")
            
            # Enhanced Step 5: Web Presence Search (with rate limiting)
            logger.info(f"🔥 FIRECRAWL DEBUG: STEP 5 - Web presence search")
            if self.firecrawl_app:
                # Add delay to avoid rate limiting  
                await asyncio.sleep(3)
                search_results = self._search_artist_web_presence(artist_profile.name)
                enrichment_result["firecrawl_operations"].append(f"web_search: {len(search_results)} queries")
                
                # Extract additional contact info from search results
                if search_results:
                    search_contact_info = self._extract_contact_from_web_presence(search_results)
                    
                    # Merge with existing contact info
                    if search_contact_info["emails"]:
                        artist_profile.email = search_contact_info["emails"][0]
                        logger.info(f"🔥 FIRECRAWL DEBUG: Found email via search: {search_contact_info['emails'][0]}")
                    
                    if search_contact_info["social_media"]:
                        for platform, url in search_contact_info["social_media"].items():
                            if platform == "instagram":
                                artist_profile.instagram_handle = self._extract_username_from_url(url)
                                logger.info(f"🔗 Using Instagram handle from search: {artist_profile.instagram_handle}")
                            else:
                                logger.info(f"🔥 FIRECRAWL DEBUG: Found social media link from search: {platform} - {url}")
                    
                    if search_contact_info["booking_info"]:
                        if "booking" not in artist_profile.metadata:
                            artist_profile.metadata["booking"] = []
                        artist_profile.metadata["booking"].extend(search_contact_info["booking_info"])
                    
                    logger.info(f"🔍 SEARCH API: Enhanced contact info with {len(search_contact_info['emails'])} emails, {len(search_contact_info['social_media'])} social links")
            else:
                search_results = {}
                enrichment_result["firecrawl_operations"].append("web_search: 0 queries")
            
            # Calculate enhanced enrichment score
            artist_profile.enrichment_score = self._calculate_comprehensive_score(
                artist_profile, enrichment_result
            )
            
            # Update metadata
            artist_profile.metadata.update({
                "enrichment_v2": True,
                "enrichment_timestamp": datetime.now().isoformat(),
                "validation_status": {
                    "spotify_validated": enrichment_result["spotify_validated"],
                    "instagram_enriched": enrichment_result["instagram_enriched"],
                    "spotify_profile_scraped": enrichment_result["spotify_profile_scraped"],
                    "lyrics_analyzed": enrichment_result["lyrics_analyzed"]
                },
                "firecrawl_usage": {
                    "instagram_scraped": enrichment_result["instagram_enriched"],
                    "spotify_profile_scraped": enrichment_result["spotify_profile_scraped"],
                    "lyrics_scraped": enrichment_result["lyrics_analyzed"],
                    "operations_performed": enrichment_result["firecrawl_operations"]
                }
            })
            
            # Update the enriched profile in result
            enrichment_result["enriched_profile"] = artist_profile
            
            logger.info(f"🎨 Comprehensive enrichment completed for {artist_profile.name} (score: {artist_profile.enrichment_score:.2f})")
            logger.info(f"🔥 FIRECRAWL DEBUG: V2 Enrichment Summary:")
            logger.info(f"🔥 FIRECRAWL DEBUG: - Spotify API: {'✅' if enrichment_result['spotify_validated'] else '❌'}")
            logger.info(f"🔥 FIRECRAWL DEBUG: - Instagram Scraping: {'✅' if enrichment_result['instagram_enriched'] else '❌'}")
            logger.info(f"🔥 FIRECRAWL DEBUG: - Spotify Profile Scraping: {'✅' if enrichment_result['spotify_profile_scraped'] else '❌'}")
            logger.info(f"🔥 FIRECRAWL DEBUG: - Lyrics Analysis: {'✅' if enrichment_result['lyrics_analyzed'] else '❌'}")
            logger.info(f"🔥 FIRECRAWL DEBUG: - Firecrawl Operations: {enrichment_result['firecrawl_operations']}")
            
        except Exception as e:
            logger.error(f"❌ Comprehensive enrichment failed for {artist_profile.name}: {e}")
            logger.error(f"🔥 FIRECRAWL DEBUG: Exception during enrichment - Type: {type(e).__name__}, Message: {str(e)}")
            enrichment_result["success"] = False
            enrichment_result["errors"].append(str(e))
            enrichment_result["enriched_profile"] = artist_profile  # Return profile even on error
        
        return enrichment_result
    
    async def _get_spotify_artist_data(
        self,
        deps: PipelineDependencies,
        artist_profile: ArtistProfile
    ) -> Optional[Dict[str, Any]]:
        """Get Spotify artist data with validation"""
        
        if not settings.is_spotify_configured():
            logger.warning("⚠️ Spotify not configured")
            return None
        
        try:
            spotify_data = None
            
            # First, try using pre-discovered Spotify ID from YouTube descriptions
            if artist_profile.spotify_id:
                logger.info(f"🎵 Using pre-discovered Spotify ID: {artist_profile.spotify_id}")
                try:
                    # Get access token
                    auth_response = await deps.http_client.post(
                        "https://accounts.spotify.com/api/token",
                        data={
                            "grant_type": "client_credentials",
                            "client_id": deps.spotify_client_id,
                            "client_secret": deps.spotify_client_secret
                        }
                    )
                    auth_response.raise_for_status()
                    access_token = auth_response.json()["access_token"]
                    
                    # Get artist data
                    artist_response = await deps.http_client.get(
                        f"https://api.spotify.com/v1/artists/{artist_profile.spotify_id}",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    artist_response.raise_for_status()
                    spotify_data = artist_response.json()
                    
                    if spotify_data:
                        logger.info(f"✅ Retrieved Spotify data using pre-discovered ID for {artist_profile.name}")
                        return self._format_spotify_artist_data(spotify_data)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to get artist data with pre-discovered ID: {e}")
            
            # Fallback: Search by artist name
            logger.info(f"🔍 Searching Spotify for artist: {artist_profile.name}")
            
            # Get access token
            auth_response = await deps.http_client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": deps.spotify_client_id,
                    "client_secret": deps.spotify_client_secret
                }
            )
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
            
            # Search for artist
            search_response = await deps.http_client.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "q": artist_profile.name,
                    "type": "artist",
                    "limit": 5
                }
            )
            search_response.raise_for_status()
            
            search_results = search_response.json()
            
            if not search_results or not search_results.get('artists', {}).get('items'):
                logger.info(f"❌ No Spotify artist found for: {artist_profile.name}")
                return None
            
            # Find best match
            artists = search_results['artists']['items']
            best_match = self._find_best_spotify_match(artist_profile.name, artists)
            
            if best_match:
                spotify_data = best_match
                logger.info(f"✅ Found Spotify match for {artist_profile.name}: {best_match.get('name')}")
                return self._format_spotify_artist_data(spotify_data)
            else:
                logger.info(f"❌ No good Spotify match for: {artist_profile.name}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Spotify search error for {artist_profile.name}: {e}")
            return None
    
    def _format_spotify_artist_data(self, spotify_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format Spotify artist data consistently"""
        return {
            "id": spotify_data.get("id"),
            "name": spotify_data.get("name"),
            "genres": spotify_data.get("genres", []),
            "images": spotify_data.get("images", []),
            "followers": spotify_data.get("followers", {}).get("total", 0),
            "popularity": spotify_data.get("popularity", 0),
            "external_urls": spotify_data.get("external_urls", {})
        }
    
    def _find_best_spotify_match(self, artist_name: str, artists: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the best matching Spotify artist from search results"""
        if not artists:
            return None
        
        artist_name_lower = artist_name.lower().strip()
        
        # First priority: Exact name match
        for artist in artists:
            if artist.get("name", "").lower().strip() == artist_name_lower:
                logger.info(f"🎯 Exact Spotify match found: {artist.get('name')}")
                return artist
        
        # Second priority: Case-insensitive contains match
        for artist in artists:
            spotify_name = artist.get("name", "").lower().strip()
            if artist_name_lower in spotify_name or spotify_name in artist_name_lower:
                logger.info(f"🎯 Partial Spotify match found: {artist.get('name')}")
                return artist
        
        # Fallback: Return the most popular artist (highest follower count)
        best_artist = max(artists, key=lambda x: x.get("followers", {}).get("total", 0))
        logger.info(f"🎯 Using most popular Spotify match: {best_artist.get('name')}")
        return best_artist
    
    async def _scrape_instagram_profile(
        self,
        artist_profile: ArtistProfile
    ) -> Optional[Dict[str, Any]]:
        """Scrape Instagram profile using Firecrawl for structured data extraction"""
        try:
            if not self.firecrawl_app:
                logger.warning("🔥 FIRECRAWL DEBUG: Firecrawl not available for Instagram scraping")
                return None
            
            # Rate limiting
            time.sleep(2)
            
            instagram_handle = artist_profile.instagram_handle
            if not instagram_handle:
                instagram_handle = self._find_instagram_handle(artist_profile)
            
            if not instagram_handle:
                logger.info(f"📷 No Instagram handle found for {artist_profile.name}")
                return None
            
            instagram_url = f"https://www.instagram.com/{instagram_handle}/"
            logger.info(f"🔥 FIRECRAWL DEBUG: Starting Instagram scrape for {artist_profile.name}")
            logger.info(f"🔥 FIRECRAWL DEBUG: Target URL: {instagram_url}")
            logger.info(f"🔥 FIRECRAWL DEBUG: Instagram handle: {instagram_handle}")
            
            # Define structured extraction schema
            extraction_schema = {
                "type": "object",
                "properties": {
                    "follower_count": {
                        "type": "string",
                        "description": "Number of followers (e.g., '1.2M', '850K', '1,234')"
                    },
                    "bio": {
                        "type": "string",
                        "description": "Profile bio/description text"
                    },
                    "link_in_bio": {
                        "type": "string",
                        "description": "URL link in bio section"
                    },
                    "is_verified": {
                        "type": "boolean",
                        "description": "Whether the account has verification badge"
                    },
                    "post_count": {
                        "type": "string",
                        "description": "Number of posts"
                    }
                },
                "required": ["follower_count"]
            }
            
            logger.info(f"🔥 FIRECRAWL DEBUG: Using extraction schema: {extraction_schema}")
            logger.info(f"🔥 FIRECRAWL DEBUG: Calling Firecrawl scrape with extract...")
            
            # Scrape with structured extraction - use correct parameters for v2.8.0
            json_config = JsonConfig(
                extractionSchema=extraction_schema,
                mode="llm-extraction"
            )
            
            response = self.firecrawl_app.scrape_url(
                instagram_url,
                formats=["json"],
                json_options=json_config
            )
            
            if not response or not response.success:
                logger.warning(f"🔥 FIRECRAWL DEBUG: Failed response from Firecrawl for {instagram_url}")
                return None
                
            if not hasattr(response, 'data') or not response.data:
                logger.warning(f"🔥 FIRECRAWL DEBUG: No data in response: {response}")
                return None
                
            extracted_data = getattr(response.data, 'json', {})
            
            if not extracted_data:
                logger.warning(f"🔥 FIRECRAWL DEBUG: No JSON data extracted from {instagram_url}")
                return None
                
            logger.info(f"🔥 FIRECRAWL DEBUG: Extracted Instagram data: {extracted_data}")
            
            # Map extracted data to our expected format
            instagram_data = {
                "follower_count": self._normalize_follower_count(extracted_data.get("follower_count")),
                "bio": extracted_data.get("bio"),
                "link_in_bio": extracted_data.get("link_in_bio"),
                "is_verified": extracted_data.get("is_verified", False),
                "post_count": extracted_data.get("post_count")
            }
            
            logger.info(f"🔥 FIRECRAWL DEBUG: Instagram scraping successful for {artist_profile.name}")
            return instagram_data
            
        except Exception as e:
            logger.error(f"🔥 FIRECRAWL DEBUG: Instagram scraping failed for {instagram_url}: {e}")
            logger.error(f"🔥 FIRECRAWL DEBUG: Exception type: {type(e).__name__}")
            return None
    
    async def _scrape_spotify_profile(
        self,
        spotify_artist_id: str
    ) -> Optional[Dict[str, Any]]:
        """Scrape Spotify profile page using Firecrawl for additional details"""
        try:
            if not self.firecrawl_app:
                logger.warning("🔥 FIRECRAWL DEBUG: Firecrawl not available for Spotify scraping")
                return None
            
            # Rate limiting
            time.sleep(2)
            
            spotify_url = f"https://open.spotify.com/artist/{spotify_artist_id}"
            logger.info(f"🔥 FIRECRAWL DEBUG: Starting Spotify profile scrape")
            logger.info(f"🔥 FIRECRAWL DEBUG: Target URL: {spotify_url}")
            logger.info(f"🔥 FIRECRAWL DEBUG: Spotify artist ID: {spotify_artist_id}")
            
            # Define extraction schema for Spotify profile
            extraction_schema = {
                "type": "object",
                "properties": {
                    "monthly_listeners": {
                        "type": "string",
                        "description": "Monthly listeners count (e.g., '1,234,567 monthly listeners')"
                    },
                    "bio": {
                        "type": "string",
                        "description": "Artist biography or description"
                    },
                    "verified": {
                        "type": "boolean", 
                        "description": "Whether artist is verified"
                    },
                    "top_cities": {
                        "type": "array",
                        "description": "List of top cities where artist is popular",
                        "items": {"type": "string"}
                    }
                }
            }
            
            logger.info(f"🔥 FIRECRAWL DEBUG: Using Spotify extraction schema: {extraction_schema}")
            logger.info(f"🔥 FIRECRAWL DEBUG: Calling Firecrawl scrape for Spotify profile...")
            
            # Use correct API parameters for firecrawl-py v2.8.0
            json_config = JsonConfig(
                extractionSchema=extraction_schema,
                mode="llm-extraction"
            )
            
            response = self.firecrawl_app.scrape_url(
                spotify_url,
                formats=["json"],
                json_options=json_config
            )
            
            logger.info(f"🔥 FIRECRAWL DEBUG: Spotify raw response received")
            logger.info(f"🔥 FIRECRAWL DEBUG: Response success: {response.success if response else 'None'}")
            logger.info(f"🔥 FIRECRAWL DEBUG: Response has data attr: {hasattr(response, 'data') if response else 'None'}")
            if response and hasattr(response, 'data'):
                logger.info(f"🔥 FIRECRAWL DEBUG: Response data type: {type(response.data)}")
                logger.info(f"🔥 FIRECRAWL DEBUG: Response data attributes: {dir(response.data) if response.data else 'None'}")
            
            # Check for response data in v2.8.0 format
            if not response or not response.success:
                logger.warning(f"🔥 FIRECRAWL DEBUG: Failed response from Firecrawl for {spotify_url}")
                return None
                
            if not hasattr(response, 'data') or not response.data:
                logger.warning(f"🔥 FIRECRAWL DEBUG: No data in response")
                return None
                
            extracted_data = getattr(response.data, 'json', {})
            
            if not extracted_data:
                logger.warning(f"🔥 FIRECRAWL DEBUG: No JSON data extracted from Spotify profile")
                return None
            
            logger.info(f"🔥 FIRECRAWL DEBUG: Extracted Spotify profile data: {extracted_data}")
            
            # Process the extracted data
            spotify_profile = {
                "monthly_listeners": extracted_data.get("monthly_listeners"),
                "bio": extracted_data.get("bio"),
                "verified": extracted_data.get("verified", False),
                "top_cities": extracted_data.get("top_cities", [])
            }
            
            logger.info(f"🔥 FIRECRAWL DEBUG: Spotify profile scraping successful")
            return spotify_profile
            
        except Exception as e:
            logger.error(f"🔥 FIRECRAWL DEBUG: Spotify profile scraping failed for {spotify_url}: {e}")
            logger.error(f"🔥 FIRECRAWL DEBUG: Exception type: {type(e).__name__}")
            return None
    
    async def _get_artist_top_songs(
        self,
        deps: PipelineDependencies,
        spotify_artist_id: str,
        limit: int = 5
    ) -> List[Dict[str, str]]:
        """Get artist's top songs from Spotify"""
        
        if not settings.is_spotify_configured():
            return []
        
        try:
            # Get access token
            auth_response = await deps.http_client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.SPOTIFY_CLIENT_ID,
                    "client_secret": settings.SPOTIFY_CLIENT_SECRET
                }
            )
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
            
            # Get top tracks
            tracks_response = await deps.http_client.get(
                f"https://api.spotify.com/v1/artists/{spotify_artist_id}/top-tracks",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"market": "US"}
            )
            tracks_response.raise_for_status()
            
            tracks = tracks_response.json()["tracks"][:limit]
            
            return [
                {
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "spotify_id": track["id"],
                    "popularity": track.get("popularity", 0)
                }
                for track in tracks
            ]
            
        except Exception as e:
            logger.error(f"Error getting top songs: {e}")
            return []
    
    async def _analyze_song_lyrics(
        self,
        artist_name: str,
        songs: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """Analyze song lyrics using Firecrawl to scrape from Musixmatch"""
        
        if not self.firecrawl_app:
            logger.warning("🔥 Firecrawl not available for lyrics analysis")
            return None
        
        if not songs:
            logger.info(f"🎵 No songs provided for lyrics analysis for {artist_name}")
            return None
        
        logger.info(f"🔥 FIRECRAWL DEBUG: Starting lyrics analysis for {artist_name}")
        logger.info(f"🔥 FIRECRAWL DEBUG: Analyzing {len(songs)} songs: {[s.get('name') for s in songs]}")
        
        all_lyrics = []
        successful_scrapes = 0
        
        for song in songs:
            song_name = song.get('name', '')
            if not song_name:
                continue
                
            # Format Musixmatch URL
            artist_slug = artist_name.lower().replace(' ', '-').replace('&', 'and')
            song_slug = song_name.lower().replace(' ', '-').replace('&', 'and')
            
            # Clean slugs of special characters
            import re
            artist_slug = re.sub(r'[^a-z0-9-]', '', artist_slug)
            song_slug = re.sub(r'[^a-z0-9-]', '', song_slug)
            
            musixmatch_url = f"https://www.musixmatch.com/lyrics/{artist_slug}/{song_slug}"
            
            logger.info(f"🔥 FIRECRAWL DEBUG: Scraping lyrics for '{song_name}' by {artist_name}")
            logger.info(f"🔥 FIRECRAWL DEBUG: Musixmatch URL: {musixmatch_url}")
            
            try:
                # Define extraction schema for lyrics
                lyrics_schema = {
                    "type": "object",
                    "properties": {
                        "lyrics": {
                            "type": "string",
                            "description": "Complete song lyrics text"
                        },
                        "song_title": {
                            "type": "string",
                            "description": "Song title"
                        },
                        "artist_name": {
                            "type": "string", 
                            "description": "Artist name"
                        }
                    },
                    "required": ["lyrics"]
                }
                
                logger.info(f"🔥 FIRECRAWL DEBUG: Using lyrics extraction schema for {song_name}")
                
                # Use correct API structure for v2.8.0
                json_config = JsonConfig(
                    extractionSchema=lyrics_schema,
                    mode="llm-extraction"
                )
                
                # Scrape lyrics with Firecrawl
                response = self.firecrawl_app.scrape_url(
                    musixmatch_url,
                    formats=["json"],
                    json_options=json_config
                )
                
                logger.info(f"🔥 FIRECRAWL DEBUG: Lyrics response received for {song_name}")
                
                if not response or not response.success:
                    logger.warning(f"🔥 FIRECRAWL DEBUG: Failed lyrics response for {song_name}")
                    continue
                
                if not hasattr(response, 'data') or not response.data:
                    logger.warning(f"🔥 FIRECRAWL DEBUG: No data in lyrics response for {song_name}")
                    continue
                
                # Try to get lyrics from json extraction
                lyrics_text = None
                extracted_data = getattr(response.data, 'json', {})
                
                if extracted_data:
                    lyrics_text = extracted_data.get('lyrics')
                    logger.info(f"🔥 FIRECRAWL DEBUG: Extracted lyrics length: {len(lyrics_text) if lyrics_text else 0} chars")
                
                # Fallback to markdown if extract didn't work
                if not lyrics_text and hasattr(response.data, 'markdown'):
                    markdown_content = response.data.markdown
                    lyrics_text = self._extract_lyrics_from_content(markdown_content)
                    logger.info(f"🔥 FIRECRAWL DEBUG: Markdown fallback lyrics length: {len(lyrics_text) if lyrics_text else 0} chars")
                
                if lyrics_text and len(lyrics_text) > 100:  # Minimum viable lyrics length
                    all_lyrics.append({
                        'song': song_name,
                        'lyrics': lyrics_text
                    })
                    successful_scrapes += 1
                    logger.info(f"🔥 FIRECRAWL DEBUG: ✅ Successfully scraped lyrics for '{song_name}' ({len(lyrics_text)} chars)")
                else:
                    logger.warning(f"🔥 FIRECRAWL DEBUG: ❌ No viable lyrics found for '{song_name}' (length: {len(lyrics_text) if lyrics_text else 0})")
                
            except Exception as e:
                logger.error(f"🔥 FIRECRAWL DEBUG: Lyrics scraping failed for '{song_name}': {e}")
                logger.error(f"🔥 FIRECRAWL DEBUG: Exception type: {type(e).__name__}")
                continue
        
        logger.info(f"🔥 FIRECRAWL DEBUG: Lyrics scraping summary - {successful_scrapes}/{len(songs)} songs successful")
        
        if not all_lyrics:
            logger.warning(f"🔥 FIRECRAWL DEBUG: No lyrics successfully scraped for {artist_name}")
            return None
        
        # Analyze lyrics with AI if we have the agent
        if self.ai_agent and all_lyrics:
            logger.info(f"🔥 FIRECRAWL DEBUG: Starting AI analysis of {len(all_lyrics)} sets of lyrics")
            
            try:
                # Combine all lyrics for analysis
                combined_lyrics = "\\n\\n".join([f"SONG: {item['song']}\\n{item['lyrics']}" for item in all_lyrics])
                
                logger.info(f"🔥 FIRECRAWL DEBUG: Combined lyrics length: {len(combined_lyrics)} chars")
                logger.info(f"🔥 FIRECRAWL DEBUG: Calling AI agent for lyrical theme analysis...")
                
                # Use AI agent to analyze themes
                ai_result = await self.ai_agent.run(
                    f"Analyze these song lyrics and extract the main lyrical themes, emotional content, and subject matter. "
                    f"Focus on recurring themes across all songs. Return as JSON with 'themes', 'emotional_tone', and 'subject_matter' fields. "
                    f"Lyrics:\\n{combined_lyrics[:3000]}"  # Limit to prevent token overflow
                )
                
                logger.info(f"🔥 FIRECRAWL DEBUG: AI analysis completed")
                logger.info(f"🔥 FIRECRAWL DEBUG: AI result type: {type(ai_result.data) if hasattr(ai_result, 'data') else type(ai_result)}")
                
                # Extract themes from AI response
                if hasattr(ai_result, 'data') and isinstance(ai_result.data, dict):
                    ai_data = ai_result.data
                    logger.info(f"🔥 FIRECRAWL DEBUG: AI analysis data: {ai_data}")
                    
                    return {
                        "themes": ai_data.get("themes", []),
                        "emotional_tone": ai_data.get("emotional_tone"),
                        "subject_matter": ai_data.get("subject_matter", []),
                        "songs_analyzed": len(all_lyrics),
                        "total_lyrics_length": len(combined_lyrics)
                    }
                else:
                    logger.warning(f"🔥 FIRECRAWL DEBUG: Unexpected AI result format: {ai_result}")
                    
            except Exception as e:
                logger.error(f"🔥 FIRECRAWL DEBUG: AI lyrics analysis failed: {e}")
                logger.error(f"🔥 FIRECRAWL DEBUG: Exception type: {type(e).__name__}")
        
        # Fallback to basic theme extraction if AI fails
        logger.info(f"🔥 FIRECRAWL DEBUG: Using fallback basic theme extraction")
        basic_themes = self._extract_basic_themes([item['lyrics'] for item in all_lyrics])
        
        logger.info(f"🔥 FIRECRAWL DEBUG: Basic themes extracted: {basic_themes}")
        
        return {
            "themes": basic_themes,
            "songs_analyzed": len(all_lyrics),
            "method": "basic_extraction"
        }
    
    async def _extract_contact_from_url(
        self,
        url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract contact information from link-in-bio URLs using Firecrawl"""
        
        if not self.firecrawl_app or not url:
            logger.warning("🔥 Firecrawl not available or no URL provided for contact extraction")
            return None
        
        logger.info(f"🔥 FIRECRAWL DEBUG: Starting contact extraction from link-in-bio")
        logger.info(f"🔥 FIRECRAWL DEBUG: Target URL: {url}")
        
        try:
            # Define extraction schema for contact information
            contact_schema = {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Email address for contact (e.g., contact@example.com)"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Phone number for contact"
                    },
                    "booking_email": {
                        "type": "string",
                        "description": "Booking or management email address"
                    },
                    "location": {
                        "type": "string",
                        "description": "Location, city, or address mentioned"
                    },
                    "website": {
                        "type": "string",
                        "description": "Official website URL"
                    },
                    "social_links": {
                        "type": "array",
                        "description": "List of social media links",
                        "items": {"type": "string"}
                    }
                }
            }
            
            logger.info(f"🔥 FIRECRAWL DEBUG: Using contact extraction schema")
            logger.info(f"🔥 FIRECRAWL DEBUG: Calling Firecrawl scrape for contact info...")
            
            # Scrape contact page with Firecrawl v2.8.0
            json_config = JsonConfig(
                extractionSchema=contact_schema,
                mode="llm-extraction"
            )
            
            response = self.firecrawl_app.scrape_url(
                url,
                formats=["json"],
                json_options=json_config
            )
            
            logger.info(f"🔥 FIRECRAWL DEBUG: Contact extraction response received")
            logger.info(f"🔥 FIRECRAWL DEBUG: Response keys: {list(response.keys()) if response else 'None'}")
            
            if not response or not response.success:
                logger.warning(f"🔥 FIRECRAWL DEBUG: Failed contact response for {url}")
                return None
            
            contact_info = {}
            data = response.get('data', {})
            
            # Try structured extraction first
            extracted_data = data.get('json', {})
            if extracted_data:
                logger.info(f"🔥 FIRECRAWL DEBUG: Extracted contact data: {extracted_data}")
                
                contact_info.update({
                    "email": extracted_data.get("email"),
                    "phone": extracted_data.get("phone"), 
                    "booking_email": extracted_data.get("booking_email"),
                    "location": extracted_data.get("location"),
                    "website": extracted_data.get("website"),
                    "social_links": extracted_data.get("social_links", [])
                })
            
            # Fallback to regex parsing from markdown if needed
            markdown_content = data.get('markdown', '')
            if markdown_content and not any(contact_info.values()):
                logger.info(f"🔥 FIRECRAWL DEBUG: Fallback to markdown parsing (length: {len(markdown_content)} chars)")
                
                # Extract email addresses using regex
                import re
                email_pattern = r'\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b'
                emails = re.findall(email_pattern, markdown_content)
                
                if emails:
                    contact_info["email"] = emails[0]  # Take the first email found
                    logger.info(f"🔥 FIRECRAWL DEBUG: Found email via regex: {emails[0]}")
                
                # Extract phone numbers (basic pattern)
                phone_pattern = r'\\b(?:\\+?1[-.]?)?(?:\\([0-9]{3}\\)|[0-9]{3})[-.]?[0-9]{3}[-.]?[0-9]{4}\\b'
                phones = re.findall(phone_pattern, markdown_content)
                
                if phones:
                    contact_info["phone"] = phones[0]
                    logger.info(f"🔥 FIRECRAWL DEBUG: Found phone via regex: {phones[0]}")
            
            # Filter out None/empty values
            contact_info = {k: v for k, v in contact_info.items() if v}
            
            if contact_info:
                logger.info(f"🔥 FIRECRAWL DEBUG: ✅ Successfully extracted contact info: {contact_info}")
                return contact_info
            else:
                logger.warning(f"🔥 FIRECRAWL DEBUG: ❌ No contact information found at {url}")
                return None
                
        except Exception as e:
            logger.error(f"🔥 FIRECRAWL DEBUG: Contact extraction failed for {url}: {e}")
            logger.error(f"🔥 FIRECRAWL DEBUG: Exception type: {type(e).__name__}")
            return None
    
    def _get_best_image_url(self, images: List[Dict[str, Any]]) -> Optional[str]:
        """Get the best quality image URL from Spotify images array"""
        if not images:
            return None
        
        # Sort by width (larger is better) and return URL
        sorted_images = sorted(images, key=lambda x: x.get('width', 0), reverse=True)
        return sorted_images[0].get('url') if sorted_images else None
    
    def _find_instagram_handle(self, artist_profile: ArtistProfile) -> Optional[str]:
        """Find Instagram handle from pre-discovered URLs or social links"""
        
        # First check pre-discovered social media from YouTube descriptions
        pre_discovered = artist_profile.metadata.get("pre_discovered_social", {})
        instagram_url = pre_discovered.get("instagram_url")
        
        if instagram_url:
            # Extract username from pre-discovered URL
            match = re.search(r'instagram\.com/([a-zA-Z0-9._]+)', instagram_url)
            if match:
                handle = match.group(1)
                artist_profile.instagram_handle = handle
                logger.info(f"🔗 Using pre-discovered Instagram handle: {handle}")
                return handle
        
        # Fallback to existing social links
        for link in artist_profile.social_links.values():
            if 'instagram.com' in str(link).lower():
                # Extract username from URL
                match = re.search(r'instagram\.com/([a-zA-Z0-9._]+)', link)
                if match:
                    handle = match.group(1)
                    artist_profile.instagram_handle = handle
                    logger.info(f"🔗 Using existing Instagram handle: {handle}")
                    return handle
        
        return None
    
    def _parse_follower_count(self, follower_str: str) -> int:
        """Parse follower count from string (e.g., '1.2M' -> 1200000)"""
        if not follower_str:
            return 0
        
        follower_str = follower_str.strip().upper()
        
        # Remove non-numeric characters except K, M, B
        cleaned = re.sub(r'[^0-9KMB.]', '', follower_str)
        
        try:
            if 'K' in cleaned:
                return int(float(cleaned.replace('K', '')) * 1000)
            elif 'M' in cleaned:
                return int(float(cleaned.replace('M', '')) * 1000000)
            elif 'B' in cleaned:
                return int(float(cleaned.replace('B', '')) * 1000000000)
            else:
                return int(float(cleaned))
        except:
            return 0
    
    def _parse_listener_count(self, listener_str: str) -> int:
        """Parse monthly listener count from string"""
        return self._parse_follower_count(listener_str)
    
    def _extract_lyrics_from_content(self, content: str) -> Optional[str]:
        """Extract lyrics from scraped content"""
        if not content:
            return None
        
        # Remove common non-lyric elements
        lines = content.split('\n')
        lyrics_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines, navigation, ads, etc.
            if (line and 
                not line.startswith('[') and 
                not line.startswith('(') and
                'cookie' not in line.lower() and
                'advertisement' not in line.lower() and
                len(line) > 5):
                lyrics_lines.append(line)
        
        # Join and return if we have substantial content
        lyrics = '\n'.join(lyrics_lines)
        return lyrics if len(lyrics) > 100 else None
    
    def _extract_basic_themes(self, lyrics_list: List[str]) -> List[str]:
        """Extract basic themes from lyrics without AI"""
        all_text = ' '.join(lyrics_list).lower()
        
        themes = []
        
        # Common theme keywords
        theme_keywords = {
            "love": ["love", "heart", "romance", "together", "forever"],
            "heartbreak": ["broken", "pain", "tears", "goodbye", "miss"],
            "party": ["party", "dance", "club", "night", "fun"],
            "success": ["money", "rich", "success", "win", "top"],
            "struggle": ["struggle", "fight", "hard", "pain", "difficult"],
            "dreams": ["dream", "hope", "wish", "future", "believe"],
            "social": ["society", "world", "people", "change", "system"]
        }
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in all_text for keyword in keywords):
                themes.append(theme)
        
        return themes[:5] if themes else ["general", "artistic expression"]
    
    def _calculate_comprehensive_score(
        self,
        artist_profile: ArtistProfile,
        enrichment_result: Dict[str, Any]
    ) -> float:
        """Calculate comprehensive enrichment score"""
        score = 0.0
        
        # Base profile completeness (40%)
        if artist_profile.name:
            score += 0.05
        if artist_profile.spotify_id:
            score += 0.10
        if artist_profile.instagram_handle:
            score += 0.05
        if artist_profile.email:
            score += 0.10
        if artist_profile.genres:
            score += 0.05
        if artist_profile.avatar_url:
            score += 0.05
        
        # Social media presence (20%)
        if artist_profile.follower_counts.get("spotify", 0) > 1000:
            score += 0.10
        if artist_profile.follower_counts.get("instagram", 0) > 1000:
            score += 0.10
        
        # Enhanced data (40%)
        if enrichment_result.get("spotify_validated"):
            score += 0.10
        if enrichment_result.get("instagram_enriched"):
            score += 0.10
        if enrichment_result.get("spotify_profile_scraped"):
            score += 0.10
        if enrichment_result.get("lyrics_analyzed") and artist_profile.lyrical_themes:
            score += 0.10
        
        return min(score, 1.0)

    def _search_artist_web_presence(self, artist_name: str) -> Dict[str, Any]:
        """Search for artist's web presence using Firecrawl Search API"""
        try:
            if not self.firecrawl_app:
                logger.warning("🔍 SEARCH API: Firecrawl not available for web search")
                return {}
            
            logger.info(f"🔍 SEARCH API: Starting web presence enrichment for {artist_name}")
            
            search_queries = [
                f'"{artist_name}" official website',
                f'"{artist_name}" instagram', 
                f'"{artist_name}" twitter',
                f'"{artist_name}" soundcloud',
                f'"{artist_name}" bandcamp',
                f'"{artist_name}" linktree'
            ]
            
            web_presence = {
                "official_website": None,
                "social_links": [],
                "music_platforms": [],
                "contact_info": {}
            }
            
            for query in search_queries:
                try:
                    logger.info(f"🔍 SEARCH API: Searching for '{query}'")
                    
                    # Rate limiting
                    time.sleep(1)
                    
                    # Use correct parameters for firecrawl-py v2.8.0
                    search_result = self.firecrawl_app.search(
                        query=query,
                        limit=3  # Direct parameter for v2.8.0
                    )
                    
                    if not search_result or not search_result.success:
                        logger.warning(f"🔍 SEARCH API: No successful search result for '{query}'")
                        continue
                        
                    if not hasattr(search_result, 'data') or not search_result.data:
                        logger.warning(f"🔍 SEARCH API: No data in search result for '{query}'")
                        continue
                        
                    # Process search results
                    search_data = search_result.data
                    if hasattr(search_data, '__iter__'):  # Check if it's iterable
                        for result in search_data:
                            if hasattr(result, 'url'):
                                url = result.url
                            elif isinstance(result, dict):
                                url = result.get('url')
                            else:
                                continue
                                
                            if url:
                                self._categorize_url(url, web_presence)
                    
                except Exception as e:
                        if "rate limit" in str(e).lower() or "429" in str(e):
                            logger.warning(f"🔍 SEARCH API: Rate limited on query '{query}' - stopping search")
                            break
                        else:
                            logger.error(f"🔍 SEARCH API: Failed to search for '{query}': {e}")
                            continue
            
            logger.info(f"🔍 SEARCH API: Web presence search completed for {artist_name}")
            return web_presence
            
        except Exception as e:
            logger.error(f"🔍 SEARCH API: Web presence search failed for {artist_name}: {e}")
            return {}

    def _extract_contact_from_web_presence(self, web_presence: Dict[str, Any]) -> Dict[str, Any]:
        """Extract contact information from web presence results"""
        contact_info = {
            "emails": [],
            "websites": [],
            "social_media": {},
            "booking_info": []
        }
        
        if not web_presence:
            return contact_info
        
        try:
            # Extract from social links
            for social_link in web_presence.get("social_links", []):
                platform = social_link.get("platform")
                url = social_link.get("url")
                if platform and url:
                    contact_info["social_media"][platform] = url
            
            # Extract from music platforms  
            for music_platform in web_presence.get("music_platforms", []):
                platform = music_platform.get("platform")
                url = music_platform.get("url")
                if platform and url:
                    contact_info["social_media"][platform] = url
            
            # Add official website
            if web_presence.get("official_website"):
                contact_info["websites"].append({
                    "type": "official", 
                    "url": web_presence["official_website"]
                })
            
            # Extract contact info from the discovered URLs if available
            urls_to_check = []
            if web_presence.get("official_website"):
                urls_to_check.append(web_presence["official_website"])
            
            # Limit URL checking to avoid rate limits
            if urls_to_check:
                extracted_contact = self._extract_contact_information(urls_to_check[:2])
                if extracted_contact:
                    if extracted_contact.get("email"):
                        contact_info["emails"].append(extracted_contact["email"])
                    if extracted_contact.get("booking_email"):
                        contact_info["emails"].append(extracted_contact["booking_email"])
            
            logger.info(f"🔍 SEARCH API: Extracted contact data - Emails: {len(contact_info['emails'])}, Social: {len(contact_info['social_media'])}")
            return contact_info
            
        except Exception as e:
            logger.error(f"🔍 SEARCH API: Failed to extract contact from web presence: {e}")
            return contact_info

    async def _extract_contact_from_search_results(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract contact information from search results for ENRICHMENT ONLY
        """
        contact_info = {
            "emails": [],
            "websites": [],
            "social_media": {},
            "booking_info": []
        }
        
        if not search_results:
            return contact_info
        
        try:
            # Process search results to extract structured contact data
            for query, results in search_results.items():
                if not results:
                    continue
                
                for result in results:
                    content = result.get("markdown", "")
                    url = result.get("url", "")
                    
                    # Extract emails
                    import re
                    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
                    contact_info["emails"].extend(emails)
                    
                    # Categorize URLs
                    if "instagram.com" in url:
                        contact_info["social_media"]["instagram"] = url
                    elif "twitter.com" in url or "x.com" in url:
                        contact_info["social_media"]["twitter"] = url
                    elif "soundcloud.com" in url:
                        contact_info["social_media"]["soundcloud"] = url
                    elif "bandcamp.com" in url:
                        contact_info["social_media"]["bandcamp"] = url
                    elif "linktree" in url or "linktr.ee" in url:
                        contact_info["websites"].append({"type": "linktree", "url": url})
                    elif any(keyword in content.lower() for keyword in ["booking", "contact", "management"]):
                        contact_info["booking_info"].append({"url": url, "content": content[:200]})
                    
            # Remove duplicates
            contact_info["emails"] = list(set(contact_info["emails"]))
            
            logger.info(f"🔍 SEARCH API: Extracted enrichment data - Emails: {len(contact_info['emails'])}, Social: {len(contact_info['social_media'])}")
            return contact_info
            
        except Exception as e:
            logger.error(f"🔍 SEARCH API: Failed to extract enrichment data: {str(e)}")
            return contact_info

    def _extract_username_from_url(self, url: str) -> Optional[str]:
        """Extract username from social media URL"""
        if not url:
            return None

        # Instagram URL patterns
        if "instagram.com" in url:
            import re
            match = re.search(r'instagram\.com/([^/?]+)', url)
            return match.group(1) if match else None
        
        # Twitter URL patterns
        if "twitter.com" in url or "x.com" in url:
            import re
            match = re.search(r'(?:twitter|x)\.com/([^/?]+)', url)
            return match.group(1) if match else None
        
        return None

    def _categorize_url(self, url: str, web_presence: Dict[str, Any]) -> None:
        """Categorize URLs into appropriate web presence categories"""
        try:
            domain = urlparse(url).netloc.lower()
            
            # Social media platforms
            if 'instagram.com' in domain:
                web_presence['social_links'].append({'platform': 'instagram', 'url': url})
            elif 'twitter.com' in domain or 'x.com' in domain:
                web_presence['social_links'].append({'platform': 'twitter', 'url': url})
            elif 'tiktok.com' in domain:
                web_presence['social_links'].append({'platform': 'tiktok', 'url': url})
            elif 'facebook.com' in domain:
                web_presence['social_links'].append({'platform': 'facebook', 'url': url})
            elif 'youtube.com' in domain:
                web_presence['social_links'].append({'platform': 'youtube', 'url': url})
            
            # Music platforms
            elif 'spotify.com' in domain:
                web_presence['music_platforms'].append({'platform': 'spotify', 'url': url})
            elif 'soundcloud.com' in domain:
                web_presence['music_platforms'].append({'platform': 'soundcloud', 'url': url})
            elif 'bandcamp.com' in domain:
                web_presence['music_platforms'].append({'platform': 'bandcamp', 'url': url})
            elif 'apple.com' in domain and 'music' in url:
                web_presence['music_platforms'].append({'platform': 'apple_music', 'url': url})
                
            # Link aggregators
            elif 'linktree' in domain or 'linktr.ee' in domain:
                web_presence['social_links'].append({'platform': 'linktree', 'url': url})
                
            # Official websites (exclude major platforms)
            elif not any(platform in domain for platform in ['google.', 'wikipedia.', 'youtube.', 'spotify.', 'instagram.', 'twitter.', 'facebook.', 'tiktok.']):
                if not web_presence['official_website']:  # Take first official website found
                    web_presence['official_website'] = url
                    
        except Exception as e:
            logger.warning(f"🔍 URL categorization failed for {url}: {e}")

    def _extract_contact_information(self, urls: List[str]) -> Dict[str, Any]:
        """Extract contact information from discovered URLs using Firecrawl"""
        try:
            if not self.firecrawl_app or not urls:
                return {}
                
            contact_info = {}
            
            for url in urls[:3]:  # Limit to first 3 URLs to avoid rate limits
                try:
                    # Rate limiting
                    time.sleep(2)
                    
                    contact_schema = {
                        "type": "object",
                        "properties": {
                            "email": {
                                "type": "string",
                                "description": "Contact email address"
                            },
                            "phone": {
                                "type": "string", 
                                "description": "Phone number"
                            },
                            "booking_email": {
                                "type": "string",
                                "description": "Booking or management email"
                            },
                            "location": {
                                "type": "string",
                                "description": "Artist location or based in"
                            },
                            "website": {
                                "type": "string",
                                "description": "Official website URL"
                            },
                            "social_links": {
                                "type": "array",
                                "description": "Social media links",
                                "items": {"type": "string"}
                            }
                        }
                    }
                    
                    logger.info(f"🔥 FIRECRAWL DEBUG: Extracting contact info from {url}")
                    
                    # Scrape contact page with Firecrawl v2.8.0
                    json_config = JsonConfig(
                        extractionSchema=contact_schema,
                        mode="llm-extraction"
                    )
                    
                    response = self.firecrawl_app.scrape_url(
                        url,
                        formats=["json"],
                        json_options=json_config
                    )
                    
                    if not response or not response.success:
                        logger.warning(f"🔥 FIRECRAWL DEBUG: Failed contact response for {url}")
                        continue
                        
                    if not hasattr(response, 'data') or not response.data:
                        logger.warning(f"🔥 FIRECRAWL DEBUG: No data in contact response")
                        continue
                        
                    extracted_data = getattr(response.data, 'json', {})
                    
                    if extracted_data:
                        contact_info.update({
                            "email": extracted_data.get("email"),
                            "phone": extracted_data.get("phone"), 
                            "booking_email": extracted_data.get("booking_email"),
                            "location": extracted_data.get("location"),
                            "website": extracted_data.get("website"),
                            "social_links": extracted_data.get("social_links", [])
                        })
                        
                        logger.info(f"🔥 FIRECRAWL DEBUG: Extracted contact info: {extracted_data}")
                        
                        # If we got substantial contact info, break early
                        if contact_info.get("email") or contact_info.get("phone"):
                            break
                            
                except Exception as e:
                    logger.error(f"🔥 FIRECRAWL DEBUG: Contact extraction failed for {url}: {e}")
                    continue
                    
            return contact_info
            
        except Exception as e:
            logger.error(f"🔥 FIRECRAWL DEBUG: Contact information extraction failed: {e}")
            return {}

    def _normalize_follower_count(self, follower_str: Optional[str]) -> int:
        """Normalize follower count string to integer"""
        if not follower_str:
            return 0
            
        try:
            # Remove non-alphanumeric characters except K, M, B
            clean_str = re.sub(r'[^\d\.KMBkmb]', '', str(follower_str))
            
            if not clean_str:
                return 0
                
            # Handle K, M, B multipliers
            if clean_str.lower().endswith('k'):
                return int(float(clean_str[:-1]) * 1000)
            elif clean_str.lower().endswith('m'):
                return int(float(clean_str[:-1]) * 1000000)
            elif clean_str.lower().endswith('b'):
                return int(float(clean_str[:-1]) * 1000000000)
            else:
                # Remove commas and periods for regular numbers
                clean_str = clean_str.replace(',', '').replace('.', '')
                return int(clean_str) if clean_str.isdigit() else 0
                
        except (ValueError, AttributeError):
            return 0

def get_enhanced_enrichment_agent_v2() -> EnhancedEnrichmentAgentV2:
    """Factory function to get enhanced enrichment agent instance"""
    return EnhancedEnrichmentAgentV2() 