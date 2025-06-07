"""
Simplified Enhanced Enrichment Agent that works reliably with PydanticAI.
"""
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
import json
from datetime import datetime

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile

# Import Firecrawl if available
try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False

logger = logging.getLogger(__name__)

class EnhancementData(BaseModel):
    """Structured enrichment data"""
    artist_name: str
    genre: Optional[str] = None
    contact_email: Optional[str] = None
    social_media_followers: Optional[int] = None
    website_info: Optional[str] = None
    enrichment_score: float = 0.0
    data_sources: List[str] = Field(default_factory=list)

class SimpleEnhancedEnrichmentAgent:
    """Simplified enrichment agent that works reliably"""
    
    def __init__(self):
        self.agent_name = "SimpleEnhancedEnrichmentAgent"
        self._agent: Optional[Agent] = None
        self._initialized = False
        logger.info(f"🤖 Initializing {self.agent_name}")
    
    @property
    def agent(self) -> Optional[Agent]:
        """Lazy initialization of PydanticAI agent"""
        if not self._initialized:
            self._initialize_agent()
        return self._agent
    
    def _initialize_agent(self):
        """Initialize agent with error handling"""
        try:
            # Use same pattern as existing working agents
            if settings.is_deepseek_configured():
                self._agent = Agent(
                    model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
                    system_prompt="""You are an AI music industry researcher specializing in artist data enrichment.
                    
                    Your task is to analyze artist information and provide:
                    1. Genre classification based on available data
                    2. Contact information discovery patterns
                    3. Social media presence assessment
                    4. Overall data quality scoring
                    
                    Focus on emerging artists and provide practical, actionable insights.
                    Always return structured data that can be used for music industry decisions."""
                )
                self._initialized = True
                logger.info(f"✅ {self.agent_name} initialized with DeepSeek")
            else:
                logger.warning(f"⚠️ {self.agent_name} not initialized - no AI provider configured")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize {self.agent_name}: {e}")
            self._agent = None
    
    async def enrich_artist_basic(
        self,
        artist_profile: ArtistProfile,
        deps: PipelineDependencies
    ) -> Dict[str, Any]:
        """Basic artist enrichment using available data"""
        
        logger.info(f"🔍 Enriching artist: {artist_profile.name}")
        
        try:
            # Gather available data
            basic_info = {
                "name": artist_profile.name,
                "youtube_channel": artist_profile.metadata.get("youtube_channel_url", ""),
                "social_links": getattr(artist_profile, 'social_links', []),
                "subscriber_count": artist_profile.metadata.get("subscriber_count", 0),
                "video_count": artist_profile.metadata.get("video_count", 0)
            }
            
            # Check if we already have social media URLs from YouTube discovery
            existing_social_media = self._extract_existing_social_media(artist_profile)
            if existing_social_media:
                logger.info(f"🔗 Found existing social media URLs for {artist_profile.name}: {list(existing_social_media.keys())}")
                basic_info["social_media_urls"] = existing_social_media
                basic_info["social_media_source"] = "youtube_discovery"
                
                # Store social media data in profile for database persistence
                if not hasattr(artist_profile, 'social_links') or not artist_profile.social_links:
                    artist_profile.social_links = []
                
                # Add URLs to social_links if not already there
                for platform, url in existing_social_media.items():
                    if url not in artist_profile.social_links:
                        artist_profile.social_links.append(url)
                
                # Skip Firecrawl for social media discovery since we already have URLs
                logger.info(f"⏭️ Skipping Firecrawl social media discovery for {artist_profile.name} - URLs already found from YouTube")
                firecrawl_data = None
            else:
                # Enhanced data gathering with Firecrawl only if no social media URLs found
                logger.info(f"🔥 Attempting Firecrawl enrichment for {artist_profile.name}...")
                firecrawl_data = await self._gather_firecrawl_data(artist_profile, deps)
            
            if firecrawl_data:
                basic_info.update(firecrawl_data)
                logger.info(f"🔥 Enhanced data with Firecrawl for {artist_profile.name}")
            elif existing_social_media:
                logger.info(f"✅ Using existing social media data instead of Firecrawl for {artist_profile.name}")
            else:
                logger.info(f"⚠️ No social media data gathered for {artist_profile.name}")
            
            # Spotify data gathering
            logger.info(f"🎵 Attempting Spotify enrichment for {artist_profile.name}...")
            spotify_data = await self._gather_spotify_data(artist_profile, deps)
            if spotify_data:
                basic_info.update(spotify_data)
                logger.info(f"🎵 Enhanced data with Spotify for {artist_profile.name}")
            else:
                logger.info(f"⚠️ No Spotify data gathered for {artist_profile.name}")
            
            # Calculate enrichment score using enhanced scoring
            enrichment_score = self._calculate_basic_score(basic_info)
            
            # Update artist profile with enrichment data
            artist_profile.enrichment_score = enrichment_score
            artist_profile.metadata.update({
                "enrichment_performed": True,
                "enrichment_timestamp": datetime.now().isoformat(),
                "enrichment_method": "simple_enhanced_agent",
                "social_media_discovered": bool(existing_social_media or firecrawl_data),
                "firecrawl_skipped": bool(existing_social_media)
            })
            
            return {
                "success": True,
                "artist_name": artist_profile.name,
                "enrichment_score": enrichment_score,
                "data_gathered": basic_info,
                "social_media_source": basic_info.get("social_media_source", "none"),
                "firecrawl_used": bool(firecrawl_data),
                "existing_social_media_found": bool(existing_social_media)
            }
        
        except Exception as e:
            logger.error(f"❌ Basic enrichment failed for {artist_profile.name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "artist_name": artist_profile.name,
                "enrichment_score": 0.0
            }

    def _extract_existing_social_media(self, artist_profile: ArtistProfile) -> Dict[str, str]:
        """Extract existing social media URLs from YouTube discovery data"""
        social_media_urls = {}
        
        try:
            # Check YouTube data in metadata
            youtube_data = artist_profile.metadata.get("youtube_data", {})
            
            # Look for social media data in video metadata
            if "social_media" in youtube_data:
                social_data = youtube_data["social_media"]
                logger.debug(f"Found social media data in YouTube metadata: {social_data}")
                
                # Extract URLs from different platforms
                for platform, url in social_data.get("urls", {}).items():
                    if url and self._is_valid_social_url(url):
                        social_media_urls[platform] = url
                        logger.debug(f"Added {platform} URL: {url}")
            
            # Also check if social links are already populated
            if hasattr(artist_profile, 'social_links') and artist_profile.social_links:
                for link in artist_profile.social_links:
                    platform = self._detect_platform_from_url(link)
                    if platform and link not in social_media_urls.values():
                        social_media_urls[platform] = link
                        logger.debug(f"Added existing {platform} URL: {link}")
            
            # Check for social media data in recent videos
            recent_videos = youtube_data.get("recent_videos", [])
            for video in recent_videos:
                if "social_media" in video:
                    video_social = video["social_media"]
                    for platform, url in video_social.get("urls", {}).items():
                        if url and self._is_valid_social_url(url) and platform not in social_media_urls:
                            social_media_urls[platform] = url
                            logger.debug(f"Added {platform} URL from video: {url}")
            
        except Exception as e:
            logger.warning(f"Error extracting existing social media data: {e}")
        
        return social_media_urls
    
    def _is_valid_social_url(self, url: str) -> bool:
        """Validate if URL is a proper social media URL"""
        if not url or not isinstance(url, str):
            return False
        
        # Basic URL validation
        return (url.startswith(('http://', 'https://')) and 
                any(domain in url.lower() for domain in ['instagram.com', 'tiktok.com', 'twitter.com', 'x.com', 'facebook.com']))
    
    def _detect_platform_from_url(self, url: str) -> Optional[str]:
        """Detect social media platform from URL"""
        if not url:
            return None
        
        url_lower = url.lower()
        if 'instagram.com' in url_lower:
            return 'instagram'
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'twitter'
        elif 'facebook.com' in url_lower:
            return 'facebook'
        
        return None
    
    def _calculate_basic_score(self, basic_info: Dict[str, Any]) -> float:
        """Calculate basic enrichment score without AI"""
        score = 0.0
        
        # Base score for having basic info
        if basic_info.get("name"):
            score += 20
        
        # YouTube presence
        subscriber_count = basic_info.get("subscriber_count", 0)
        if subscriber_count > 0:
            score += 30
            if subscriber_count > 1000:
                score += 10
            if subscriber_count > 10000:
                score += 10
        
        # Video content
        video_count = basic_info.get("video_count", 0)
        if video_count > 0:
            score += 20
            if video_count > 10:
                score += 10
        
        # Social media presence (enhanced scoring)
        social_links = basic_info.get("social_links", [])
        social_media_urls = basic_info.get("social_media_urls", {})
        
        if social_links:
            score += 10
            logger.debug(f"Social links bonus: +10 points ({len(social_links)} links)")
        
        # Bonus for discovered social media URLs from YouTube
        if social_media_urls:
            score += 15  # Higher bonus for validated social media URLs
            if len(social_media_urls) > 1:
                score += 5  # Multiple platforms bonus
            logger.debug(f"Social media URLs bonus: +15-20 points ({len(social_media_urls)} platforms: {list(social_media_urls.keys())})")
        
        # Firecrawl enrichment bonus
        if basic_info.get("firecrawl_sources"):
            score += 15
            logger.debug(f"Firecrawl bonus: +15 points")
        
        # Spotify enrichment bonus
        spotify_data = basic_info.get("spotify_data")
        if spotify_data:
            score += 20
            spotify_followers = spotify_data.get("spotify_followers", 0)
            if spotify_followers > 1000:
                score += 5
            if spotify_followers > 10000:
                score += 5
            logger.debug(f"Spotify bonus: +20-30 points (followers: {spotify_followers})")
        
        logger.info(f"📊 Basic enrichment score calculated: {score}/100 -> {score/100:.2f}")
        
        return min(score / 100.0, 1.0)  # Convert to 0-1 scale
    
    async def _gather_firecrawl_data(
        self, 
        artist_profile: ArtistProfile, 
        deps: PipelineDependencies
    ) -> Dict[str, Any]:
        """Gather additional data using Firecrawl for web scraping"""
        
        if not FIRECRAWL_AVAILABLE:
            logger.info("Firecrawl package not installed - install with: pip install firecrawl-py")
            return {}
            
        if not settings.is_firecrawl_configured():
            logger.info("Firecrawl API key not configured - set FIRECRAWL_API_KEY environment variable")
            logger.info("Get API key from: https://firecrawl.dev")
            return {}
        
        try:
            # Initialize Firecrawl client
            app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
            
            enrichment_data = {
                "firecrawl_sources": [],
                "web_mentions": 0,
                "social_presence": {},
                "contact_info": {}
            }
            
            # Try to find artist website or social media
            search_urls = []
            
            # Look for website in metadata
            if artist_profile.metadata.get("website"):
                search_urls.append(artist_profile.metadata["website"])
            
            # Generate potential social media URLs
            artist_name_clean = artist_profile.name.lower().replace(" ", "")
            potential_urls = [
                f"https://www.instagram.com/{artist_name_clean}/",
                f"https://twitter.com/{artist_name_clean}",
                f"https://www.facebook.com/{artist_name_clean}",
            ]
            
            # Crawl available URLs (limit to 2 to avoid quota issues)
            for url in search_urls + potential_urls[:2]:
                try:
                    logger.info(f"🔥 Firecrawl scraping: {url}")
                    
                    # Use the updated API format from documentation
                    scrape_result = app.scrape_url(
                        url,
                        formats=['markdown', 'html']
                    )
                    
                    if scrape_result and scrape_result.get('success'):
                        data = scrape_result.get('data', {})
                        content = data.get('markdown', '')
                        
                        # Extract useful information
                        if content:
                            enrichment_data["firecrawl_sources"].append(url)
                            
                            # Look for contact information
                            contact_info = self._extract_contact_info(content)
                            if contact_info:
                                enrichment_data["contact_info"].update(contact_info)
                            
                            # Count social media mentions
                            social_mentions = content.lower().count("instagram") + \
                                            content.lower().count("twitter") + \
                                            content.lower().count("facebook")
                            
                            enrichment_data["web_mentions"] += len(content.split())
                            enrichment_data["social_presence"][url] = {
                                "content_length": len(content),
                                "social_mentions": social_mentions,
                                "metadata": data.get('metadata', {})
                            }
                            
                            logger.info(f"✅ Firecrawl successfully scraped {url}")
                        
                except Exception as e:
                    logger.warning(f"Firecrawl failed for {url}: {e}")
                    continue
            
            # Return enrichment data if we found anything useful
            if enrichment_data["firecrawl_sources"]:
                logger.info(f"🔥 Firecrawl enriched {artist_profile.name} with {len(enrichment_data['firecrawl_sources'])} sources")
                return enrichment_data
            
        except Exception as e:
            logger.error(f"❌ Firecrawl enrichment failed: {e}")
        
        return {}
    
    def _extract_contact_info(self, content: str) -> Dict[str, str]:
        """Extract contact information from scraped content"""
        import re
        
        contact_info = {}
        
        # Email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, content)
        if emails:
            contact_info["email"] = emails[0]  # Take first email found
        
        # Phone patterns (basic)
        phone_pattern = r'[\+]?[1-9]?[0-9]{7,15}'
        phones = re.findall(phone_pattern, content)
        if phones:
            contact_info["phone"] = phones[0]
        
        # Social media handles
        if "@" in content:
            # Look for social handles
            social_pattern = r'@([A-Za-z0-9_]{1,15})'
            handles = re.findall(social_pattern, content)
            if handles:
                contact_info["social_handle"] = f"@{handles[0]}"
        
        return contact_info

    async def _gather_spotify_data(
        self,
        artist_profile: ArtistProfile,
        deps: PipelineDependencies
    ) -> Dict[str, Any]:
        """Gather Spotify data for the artist"""
        
        if not settings.is_spotify_configured():
            logger.info(f"Spotify not configured - CLIENT_ID: {bool(settings.SPOTIFY_CLIENT_ID)}, CLIENT_SECRET: {bool(settings.SPOTIFY_CLIENT_SECRET)}")
            return {}
        
        try:
            logger.info(f"🎵 Fetching Spotify data for {artist_profile.name}")
            
            # Get Spotify access token
            auth_url = "https://accounts.spotify.com/api/token"
            auth_data = {
                "grant_type": "client_credentials",
                "client_id": settings.SPOTIFY_CLIENT_ID,
                "client_secret": settings.SPOTIFY_CLIENT_SECRET
            }
            
            auth_response = await deps.http_client.post(auth_url, data=auth_data)
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
            
            # Search for artist
            search_url = "https://api.spotify.com/v1/search"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {
                "q": artist_profile.name,
                "type": "artist",
                "limit": 5
            }
            
            search_response = await deps.http_client.get(
                search_url,
                headers=headers,
                params=params
            )
            search_response.raise_for_status()
            
            artists = search_response.json()["artists"]["items"]
            if artists:
                # Find the best match
                best_match = artists[0]
                for artist in artists:
                    if artist["name"].lower() == artist_profile.name.lower():
                        best_match = artist
                        break
                
                spotify_data = {
                    "spotify_id": best_match["id"],
                    "spotify_name": best_match["name"],
                    "spotify_genres": best_match.get("genres", []),
                    "spotify_popularity": best_match.get("popularity", 0),
                    "spotify_followers": best_match["followers"]["total"],
                    "spotify_external_urls": best_match.get("external_urls", {}),
                    "spotify_images": best_match.get("images", [])
                }
                
                logger.info(f"✅ Found Spotify data for {artist_profile.name}: {spotify_data['spotify_followers']} followers")
                return {"spotify_data": spotify_data}
            else:
                logger.info(f"❌ No Spotify results found for {artist_profile.name}")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Spotify API error for {artist_profile.name}: {e}")
            return {}

# Factory function for easy import
def get_simple_enhanced_enrichment_agent() -> SimpleEnhancedEnrichmentAgent:
    """Get simple enhanced enrichment agent instance"""
    return SimpleEnhancedEnrichmentAgent() 