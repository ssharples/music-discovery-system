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
from datetime import datetime

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile, LyricAnalysis

# Import Firecrawl if available
try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False

logger = logging.getLogger(__name__)

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
        
        if FIRECRAWL_AVAILABLE and settings.is_firecrawl_configured():
            try:
                self.firecrawl_app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
                logger.info("✅ Firecrawl initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Firecrawl: {e}")
    
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
        
        enrichment_result = {
            "success": True,
            "artist_name": artist_profile.name,
            "spotify_validated": False,
            "instagram_enriched": False,
            "spotify_profile_scraped": False,
            "lyrics_analyzed": False,
            "errors": [],
            "data": {}
        }
        
        try:
            # Step 1: Get Spotify artist data and validate
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
            
            # Step 2: Scrape and validate Instagram
            if artist_profile.instagram_handle or self._find_instagram_handle(artist_profile):
                instagram_data = await self._scrape_instagram_profile(artist_profile)
                if instagram_data:
                    enrichment_result["data"]["instagram"] = instagram_data
                    enrichment_result["instagram_enriched"] = True
                    
                    # Update artist profile
                    artist_profile.follower_counts["instagram"] = instagram_data.get("follower_count", 0)
                    
                    # Extract contact info from link in bio
                    if instagram_data.get("link_in_bio"):
                        contact_info = await self._extract_contact_from_url(instagram_data["link_in_bio"])
                        if contact_info:
                            if contact_info.get("email"):
                                artist_profile.email = contact_info["email"]
                            if contact_info.get("location"):
                                artist_profile.location = contact_info["location"]
                    
                    # Validate Spotify if found in Instagram
                    if instagram_data.get("has_spotify_link") and spotify_data:
                        enrichment_result["spotify_validated"] = True
                        logger.info(f"✅ Spotify validated via Instagram for {artist_profile.name}")
            
            # Step 3: Scrape Spotify profile for additional data
            if artist_profile.spotify_id:
                spotify_profile_data = await self._scrape_spotify_profile(artist_profile.spotify_id)
                if spotify_profile_data:
                    enrichment_result["data"]["spotify_profile"] = spotify_profile_data
                    enrichment_result["spotify_profile_scraped"] = True
                    
                    # Update artist bio if found
                    if spotify_profile_data.get("bio") and not artist_profile.bio:
                        artist_profile.bio = spotify_profile_data["bio"]
                    
                    # Store monthly listeners
                    artist_profile.metadata["monthly_listeners"] = spotify_profile_data.get("monthly_listeners", 0)
                    artist_profile.metadata["top_cities"] = spotify_profile_data.get("top_cities", [])
            
            # Step 4: Get top songs and analyze lyrics
            if artist_profile.spotify_id:
                top_songs = await self._get_artist_top_songs(deps, artist_profile.spotify_id)
                if top_songs:
                    lyrical_themes = await self._analyze_song_lyrics(artist_profile.name, top_songs[:3])
                    if lyrical_themes:
                        enrichment_result["data"]["lyrical_analysis"] = lyrical_themes
                        enrichment_result["lyrics_analyzed"] = True
                        
                        # Update artist profile with themes
                        artist_profile.lyrical_themes = lyrical_themes.get("themes", [])
            
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
                    "lyrics_analyzed": enrichment_result["lyrics_analyzed"]
                }
            })
            
            enrichment_result["enrichment_score"] = artist_profile.enrichment_score
            enrichment_result["enriched_profile"] = artist_profile
            
            logger.info(f"🎉 Comprehensive enrichment completed for {artist_profile.name} (score: {artist_profile.enrichment_score:.2f})")
            
        except Exception as e:
            logger.error(f"❌ Comprehensive enrichment failed for {artist_profile.name}: {e}")
            enrichment_result["success"] = False
            enrichment_result["errors"].append(str(e))
        
        return enrichment_result
    
    async def _get_spotify_artist_data(
        self,
        deps: PipelineDependencies,
        artist_profile: ArtistProfile
    ) -> Optional[Dict[str, Any]]:
        """Get Spotify artist data using the API"""
        
        if not settings.is_spotify_configured():
            logger.info("Spotify not configured")
            return None
        
        try:
            # Get Spotify access token
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
            
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Search for artist if no Spotify ID
            if not artist_profile.spotify_id:
                search_response = await deps.http_client.get(
                    "https://api.spotify.com/v1/search",
                    headers=headers,
                    params={
                        "q": artist_profile.name,
                        "type": "artist",
                        "limit": 5
                    }
                )
                search_response.raise_for_status()
                
                artists = search_response.json()["artists"]["items"]
                if not artists:
                    return None
                
                # Find best match
                artist_data = artists[0]
                for artist in artists:
                    if artist["name"].lower() == artist_profile.name.lower():
                        artist_data = artist
                        break
            else:
                # Get artist by ID
                artist_response = await deps.http_client.get(
                    f"https://api.spotify.com/v1/artists/{artist_profile.spotify_id}",
                    headers=headers
                )
                artist_response.raise_for_status()
                artist_data = artist_response.json()
            
            return {
                "id": artist_data["id"],
                "name": artist_data["name"],
                "genres": artist_data.get("genres", []),
                "images": artist_data.get("images", []),
                "followers": artist_data["followers"]["total"],
                "popularity": artist_data.get("popularity", 0),
                "external_urls": artist_data.get("external_urls", {})
            }
            
        except Exception as e:
            logger.error(f"Spotify API error: {e}")
            return None
    
    async def _scrape_instagram_profile(
        self,
        artist_profile: ArtistProfile
    ) -> Optional[Dict[str, Any]]:
        """Scrape Instagram profile for follower count and link in bio"""
        
        if not self.firecrawl_app or not artist_profile.instagram_handle:
            return None
        
        try:
            instagram_url = f"https://www.instagram.com/{artist_profile.instagram_handle}/"
            
            # Define extraction schema for Instagram
            extraction_schema = {
                "type": "object",
                "properties": {
                    "follower_count": {"type": "string"},
                    "bio": {"type": "string"},
                    "external_url": {"type": "string"},
                    "is_verified": {"type": "boolean"},
                    "posts_count": {"type": "string"}
                }
            }
            
            result = self.firecrawl_app.scrape_url(
                url=instagram_url,
                params={
                    'formats': ['extract', 'markdown'],
                    'extract': {
                        'schema': extraction_schema
                    },
                    'timeout': 30000,
                    'waitFor': 2000
                }
            )
            
            if result and result.get('success'):
                extracted_data = result.get('extract', {})
                markdown_content = result.get('markdown', '')
                
                # Parse follower count
                follower_count = self._parse_follower_count(extracted_data.get('follower_count', ''))
                
                # Check for Spotify link
                has_spotify_link = False
                spotify_url = None
                if 'spotify' in markdown_content.lower():
                    has_spotify_link = True
                    # Extract Spotify URL if present
                    spotify_match = re.search(r'(https?://[^\s]*spotify[^\s]*)', markdown_content)
                    if spotify_match:
                        spotify_url = spotify_match.group(1)
                
                return {
                    "username": artist_profile.instagram_handle,
                    "follower_count": follower_count,
                    "bio": extracted_data.get('bio', ''),
                    "link_in_bio": extracted_data.get('external_url'),
                    "is_verified": extracted_data.get('is_verified', False),
                    "has_spotify_link": has_spotify_link,
                    "spotify_url": spotify_url
                }
                
        except Exception as e:
            logger.error(f"Instagram scraping error: {e}")
            return None
    
    async def _scrape_spotify_profile(
        self,
        spotify_artist_id: str
    ) -> Optional[Dict[str, Any]]:
        """Scrape Spotify artist profile for monthly listeners and top cities"""
        
        if not self.firecrawl_app:
            return None
        
        try:
            spotify_url = f"https://open.spotify.com/artist/{spotify_artist_id}"
            
            # Define extraction schema for Spotify profile
            extraction_schema = {
                "type": "object",
                "properties": {
                    "monthly_listeners": {"type": "string"},
                    "verified": {"type": "boolean"},
                    "about": {"type": "string"},
                    "top_cities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"},
                                "country": {"type": "string"},
                                "listeners": {"type": "string"}
                            }
                        }
                    }
                }
            }
            
            result = self.firecrawl_app.scrape_url(
                url=spotify_url,
                params={
                    'formats': ['extract', 'markdown'],
                    'extract': {
                        'schema': extraction_schema
                    },
                    'timeout': 30000,
                    'waitFor': 3000
                }
            )
            
            if result and result.get('success'):
                extracted_data = result.get('extract', {})
                markdown_content = result.get('markdown', '')
                
                # Parse monthly listeners
                monthly_listeners = self._parse_listener_count(
                    extracted_data.get('monthly_listeners', '0')
                )
                
                # Extract bio/about section
                bio = extracted_data.get('about', '')
                if not bio and 'about' in markdown_content.lower():
                    # Try to extract from markdown
                    bio_match = re.search(r'about\s*\n+([^\n]{50,500})', markdown_content, re.IGNORECASE)
                    if bio_match:
                        bio = bio_match.group(1).strip()
                
                return {
                    "monthly_listeners": monthly_listeners,
                    "top_cities": extracted_data.get('top_cities', []),
                    "bio": bio,
                    "verified": extracted_data.get('verified', False)
                }
                
        except Exception as e:
            logger.error(f"Spotify profile scraping error: {e}")
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
        """Scrape and analyze lyrics for songs"""
        
        if not songs:
            return None
        
        all_lyrics = []
        analyzed_songs = []
        
        for song in songs:
            try:
                # Format song and artist names for Musixmatch URL
                artist_slug = re.sub(r'[^a-z0-9]+', '-', artist_name.lower()).strip('-')
                song_slug = re.sub(r'[^a-z0-9]+', '-', song["name"].lower()).strip('-')
                
                lyrics_url = f"https://www.musixmatch.com/lyrics/{artist_slug}/{song_slug}"
                
                if self.firecrawl_app:
                    # Scrape lyrics
                    result = self.firecrawl_app.scrape_url(
                        url=lyrics_url,
                        params={
                            'formats': ['markdown'],
                            'onlyMainContent': True,
                            'timeout': 20000
                        }
                    )
                    
                    if result and result.get('success'):
                        content = result.get('markdown', '')
                        
                        # Extract lyrics from content
                        lyrics = self._extract_lyrics_from_content(content)
                        if lyrics:
                            all_lyrics.append(lyrics)
                            analyzed_songs.append(song["name"])
                            logger.info(f"✅ Scraped lyrics for {song['name']}")
                
            except Exception as e:
                logger.warning(f"Failed to scrape lyrics for {song['name']}: {e}")
                continue
        
        if not all_lyrics:
            return None
        
        # Analyze lyrics with AI
        if self.ai_agent:
            try:
                analysis_prompt = f"""
                Analyze the following lyrics from {artist_name}'s songs ({', '.join(analyzed_songs)}):
                
                {' '.join(all_lyrics[:3000])}  # Limit to prevent token overflow
                
                Provide:
                1. Main lyrical themes (list of 3-5 themes)
                2. Primary theme (single most dominant theme)
                3. Emotional tone (e.g., melancholic, uplifting, aggressive)
                4. Subject matter categories (e.g., love, social issues, personal growth)
                
                Return as JSON with keys: themes, primary_theme, emotional_tone, subject_matter
                """
                
                result = await self.ai_agent.run(analysis_prompt)
                
                if result and hasattr(result, 'data'):
                    analysis_data = result.data
                    if isinstance(analysis_data, str):
                        # Try to parse JSON from string response
                        try:
                            analysis_data = json.loads(analysis_data)
                        except:
                            # Fallback to basic analysis
                            analysis_data = {
                                "themes": ["music", "life", "emotions"],
                                "primary_theme": "personal expression",
                                "emotional_tone": "varied",
                                "subject_matter": ["personal experiences"]
                            }
                    
                    return analysis_data
                
            except Exception as e:
                logger.error(f"AI lyrical analysis failed: {e}")
        
        # Fallback basic analysis
        return {
            "themes": self._extract_basic_themes(all_lyrics),
            "primary_theme": "artistic expression",
            "emotional_tone": "varied",
            "subject_matter": ["general"]
        }
    
    async def _extract_contact_from_url(
        self,
        url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract contact information from a URL (like Linktree)"""
        
        if not self.firecrawl_app:
            return None
        
        try:
            result = self.firecrawl_app.scrape_url(
                url=url,
                params={
                    'formats': ['markdown'],
                    'onlyMainContent': True,
                    'timeout': 20000
                }
            )
            
            if result and result.get('success'):
                content = result.get('markdown', '')
                
                contact_info = {}
                
                # Extract email
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                emails = re.findall(email_pattern, content)
                if emails:
                    # Prefer booking/management emails
                    for email in emails:
                        if any(keyword in email.lower() for keyword in ['booking', 'management', 'contact']):
                            contact_info['email'] = email
                            break
                    if 'email' not in contact_info:
                        contact_info['email'] = emails[0]
                
                # Extract phone
                phone_pattern = r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
                phones = re.findall(phone_pattern, content)
                if phones:
                    contact_info['phone'] = phones[0]
                
                # Extract location
                location_patterns = [
                    r'(?:based in|located in|from)\s+([A-Z][a-zA-Z\s,]+)',
                    r'([A-Z][a-zA-Z]+,\s*[A-Z]{2})',  # City, State
                    r'([A-Z][a-zA-Z]+,\s*[A-Z][a-zA-Z]+)'  # City, Country
                ]
                
                for pattern in location_patterns:
                    location_match = re.search(pattern, content)
                    if location_match:
                        contact_info['location'] = location_match.group(1).strip()
                        break
                
                return contact_info if contact_info else None
                
        except Exception as e:
            logger.error(f"Contact extraction error: {e}")
            return None
    
    def _get_best_image_url(self, images: List[Dict[str, Any]]) -> Optional[str]:
        """Get the best quality image URL from Spotify images array"""
        if not images:
            return None
        
        # Sort by width (larger is better) and return URL
        sorted_images = sorted(images, key=lambda x: x.get('width', 0), reverse=True)
        return sorted_images[0].get('url') if sorted_images else None
    
    def _find_instagram_handle(self, artist_profile: ArtistProfile) -> Optional[str]:
        """Find Instagram handle from social links"""
        for link in artist_profile.social_links.values():
            if 'instagram.com' in str(link).lower():
                # Extract username from URL
                match = re.search(r'instagram\.com/([a-zA-Z0-9._]+)', link)
                if match:
                    artist_profile.instagram_handle = match.group(1)
                    return match.group(1)
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

def get_enhanced_enrichment_agent_v2() -> EnhancedEnrichmentAgentV2:
    """Factory function to get enhanced enrichment agent instance"""
    return EnhancedEnrichmentAgentV2() 