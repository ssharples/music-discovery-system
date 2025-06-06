# backend/app/agents/enrichment_agent.py
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import Dict, Any, Optional, List
import logging
import base64
import httpx
import json
from datetime import datetime
import asyncio

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile

logger = logging.getLogger(__name__)

# Factory function for on-demand agent creation
def create_enrichment_agent():
    """Create enrichment agent on-demand to avoid import-time blocking"""
    try:
        return Agent(
            model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
            output_type=ArtistProfile,  # Structured output for validation
            system_prompt="""You are an artist data enrichment specialist. Your role is to:
            1. Find and extract artist information from multiple platforms
            2. Discover social media profiles (Instagram, TikTok, Twitter)
            3. Extract contact information (emails, booking info)
            4. Find Spotify artist profiles and metadata
            5. Compile comprehensive artist profiles
            
            Focus on accuracy and finding verified information. Extract:
            - Social media handles and follower counts
            - Email addresses (booking, management, general)
            - Website and LinkTree URLs
            - Genre classifications
            - Location information
            - Artist bio and description
            
            Return data as a structured ArtistProfile object with calculated enrichment_score.
            """
        )
    except Exception as e:
        logger.error(f"Failed to create enrichment agent: {e}")
        return None

class ArtistEnrichmentAgent:
    """Artist enrichment agent with lazy initialization and proper error handling"""
    
    def __init__(self):
        self._agent = None
        self._agent_creation_attempted = False
        self._cache = {}  # Simple cache for API responses
        logger.info("ArtistEnrichmentAgent initialized (agent created on-demand)")
    
    @property
    def agent(self):
        """Lazy initialization of agent"""
        if self._agent is None and not self._agent_creation_attempted:
            self._agent_creation_attempted = True
            self._agent = create_enrichment_agent()
        return self._agent
    
    async def enrich_artist(
        self,
        deps: PipelineDependencies,
        artist_name: str,
        youtube_channel_id: str,
        youtube_channel_url: str
    ) -> ArtistProfile:
        """Enrich artist profile with comprehensive data collection"""
        
        logger.info(f"🎨 Enriching artist: {artist_name}")
        
        # Check cache first
        cache_key = f"artist:{artist_name}:{youtube_channel_id}"
        if cache_key in self._cache:
            logger.info(f"📦 Using cached data for {artist_name}")
            return self._cache[cache_key]
        
        # Initialize base profile
        profile = ArtistProfile(
            name=artist_name,
            youtube_channel_id=youtube_channel_id,
            youtube_channel_name=artist_name,
            metadata={
                "youtube_channel_url": youtube_channel_url,
                "enrichment_started_at": datetime.now().isoformat()
            }
        )
        
        # If agent is available, use AI-powered enrichment
        if self.agent and settings.is_deepseek_configured():
            try:
                logger.info(f"🧠 Using AI-powered enrichment for {artist_name}")
                enhanced_profile = await self._ai_enrichment(deps, profile)
                if enhanced_profile:
                    profile = enhanced_profile
            except Exception as e:
                logger.warning(f"⚠️ AI enrichment failed for {artist_name}: {e}")
        
        # Fallback to manual enrichment with retry logic
        await self._manual_enrichment_with_retry(deps, profile, max_retries=3)
        
        # Calculate enrichment score
        profile.enrichment_score = self._calculate_enrichment_score(profile)
        
        # Cache result
        self._cache[cache_key] = profile
        
        logger.info(f"✅ Enrichment completed for {artist_name} (score: {profile.enrichment_score:.2f})")
        return profile
    
    async def _ai_enrichment(
        self,
        deps: PipelineDependencies,
        profile: ArtistProfile
    ) -> Optional[ArtistProfile]:
        """Use AI agent for intelligent data enrichment"""
        try:
            # Gather initial data for AI analysis
            enrichment_data = {
                "artist_name": profile.name,
                "youtube_channel_url": profile.metadata.get("youtube_channel_url"),
                "spotify_data": await self._get_spotify_data(deps, profile.name),
                "social_media_data": await self._get_social_media_data(deps, profile.name)
            }
            
            # Let the agent process and structure the data
            result = await self.agent.run(
                f"Enrich artist profile for {profile.name} using the following data: {enrichment_data}",
                deps=deps
            )
            
            if result and hasattr(result, 'data'):
                # Merge AI results with existing profile
                enhanced = result.data
                if isinstance(enhanced, ArtistProfile):
                    # Copy over original metadata
                    enhanced.youtube_channel_id = profile.youtube_channel_id
                    enhanced.metadata.update(profile.metadata)
                    return enhanced
            
        except Exception as e:
            logger.error(f"AI enrichment error: {e}")
        
        return None
    
    async def _manual_enrichment_with_retry(
        self,
        deps: PipelineDependencies,
        profile: ArtistProfile,
        max_retries: int = 3
    ):
        """Manual enrichment with retry logic and exponential backoff"""
        
        enrichment_tasks = [
            ("spotify", self._get_spotify_data),
            ("social_media", self._get_social_media_data),
            ("web_data", self._get_web_data)
        ]
        
        for task_name, task_func in enrichment_tasks:
            for attempt in range(max_retries):
                try:
                    logger.info(f"🔄 {task_name} enrichment attempt {attempt + 1}")
                    data = await task_func(deps, profile.name)
                    
                    if data:
                        self._merge_enrichment_data(profile, task_name, data)
                        logger.info(f"✅ {task_name} enrichment successful")
                        break
                    else:
                        logger.warning(f"⚠️ {task_name} returned no data")
                        
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"❌ {task_name} enrichment failed after {max_retries} attempts: {e}")
                    else:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"⏳ {task_name} attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                        await asyncio.sleep(wait_time)
    
    async def _get_spotify_data(
        self,
        deps: PipelineDependencies,
        artist_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get Spotify artist data with proper error handling"""
        if not settings.is_spotify_configured():
            logger.warning("Spotify not configured, skipping")
            return None
        
        try:
            # Get Spotify access token
            auth_url = "https://accounts.spotify.com/api/token"
            auth_data = {
                "grant_type": "client_credentials",
                "client_id": settings.SPOTIFY_CLIENT_ID,
                "client_secret": settings.SPOTIFY_CLIENT_SECRET
            }
            
            auth_response = await deps.http_client.post(auth_url, data=auth_data)
            
            if auth_response.status_code == 429:
                raise ModelRetry("Spotify rate limit hit, please retry")
            
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
            
            # Search for artist
            search_url = "https://api.spotify.com/v1/search"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {
                "q": artist_name,
                "type": "artist",
                "limit": 5
            }
            
            search_response = await deps.http_client.get(
                search_url,
                headers=headers,
                params=params
            )
            
            if search_response.status_code == 429:
                raise ModelRetry("Spotify rate limit hit, please retry")
            
            search_response.raise_for_status()
            
            artists = search_response.json()["artists"]["items"]
            if artists:
                # Return the most relevant artist
                artist = artists[0]
                return {
                    "spotify_id": artist["id"],
                    "name": artist["name"],
                    "genres": artist.get("genres", []),
                    "popularity": artist.get("popularity", 0),
                    "followers": artist["followers"]["total"],
                    "images": artist.get("images", []),
                    "external_urls": artist.get("external_urls", {})
                }
                
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise ModelRetry("Spotify rate limit hit, please retry")
            logger.error(f"Spotify API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Spotify search error: {e}")
            return None
    
    async def _get_social_media_data(
        self,
        deps: PipelineDependencies,
        artist_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get social media data with web scraping fallback"""
        try:
            # Use Firecrawl if available
            if settings.FIRECRAWL_API_KEY:
                return await self._firecrawl_social_search(deps, artist_name)
            else:
                # Fallback to basic search patterns
                return await self._basic_social_search(deps, artist_name)
                
        except Exception as e:
            logger.error(f"Social media search error: {e}")
            return None
    
    async def _firecrawl_social_search(
        self,
        deps: PipelineDependencies,
        artist_name: str
    ) -> Optional[Dict[str, Any]]:
        """Use Firecrawl for comprehensive social media search"""
        try:
            # Search for social media profiles
            search_queries = [
                f"{artist_name} instagram music artist",
                f"{artist_name} tiktok musician",
                f"{artist_name} twitter music"
            ]
            
            firecrawl_url = "https://api.firecrawl.dev/v1/search"
            headers = {
                "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
                "Content-Type": "application/json"
            }
            
            social_data = {}
            
            for query in search_queries:
                try:
                    payload = {
                        "query": query,
                        "limit": 3,
                        "scrapeOptions": {
                            "formats": ["markdown"],
                            "onlyMainContent": True
                        }
                    }
                    
                    response = await deps.http_client.post(
                        firecrawl_url,
                        headers=headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        results = response.json()
                        # Extract social media handles from results
                        social_data.update(self._extract_social_handles(results, artist_name))
                    
                except Exception as e:
                    logger.warning(f"Firecrawl search failed for query '{query}': {e}")
                    continue
            
            return social_data if social_data else None
            
        except Exception as e:
            logger.error(f"Firecrawl social search error: {e}")
            return None
    
    async def _basic_social_search(
        self,
        deps: PipelineDependencies,
        artist_name: str
    ) -> Optional[Dict[str, Any]]:
        """Basic social media handle search"""
        # Simple pattern-based search (placeholder for now)
        # In production, implement pattern matching for common handles
        return {
            "social_search_attempted": True,
            "method": "basic_pattern_search",
            "note": "Enhanced search requires Firecrawl API key"
        }
    
    async def _get_web_data(
        self,
        deps: PipelineDependencies,
        artist_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get additional web data about the artist"""
        try:
            # Basic web search for contact information
            # This would be enhanced with proper web scraping
            return {
                "web_search_attempted": True,
                "artist_name": artist_name,
                "search_timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Web data search error: {e}")
            return None
    
    def _extract_social_handles(
        self,
        search_results: Dict[str, Any],
        artist_name: str
    ) -> Dict[str, Any]:
        """Extract social media handles from search results"""
        social_data = {}
        
        # Pattern matching for social media URLs and handles
        # This would be more sophisticated in production
        content = str(search_results).lower()
        
        # Instagram patterns
        if "instagram.com/" in content:
            # Extract Instagram handle (simplified)
            social_data["instagram_found"] = True
        
        # TikTok patterns
        if "tiktok.com/" in content:
            social_data["tiktok_found"] = True
            
        # Twitter patterns
        if "twitter.com/" in content or "x.com/" in content:
            social_data["twitter_found"] = True
        
        return social_data
    
    def _merge_enrichment_data(
        self,
        profile: ArtistProfile,
        source: str,
        data: Dict[str, Any]
    ):
        """Merge enrichment data into the artist profile"""
        if not data:
            return
        
        # Merge based on source type
        if source == "spotify" and data:
            profile.spotify_id = data.get("spotify_id")
            if data.get("genres"):
                profile.genres.extend(data["genres"])
            profile.follower_counts["spotify"] = data.get("followers", 0)
            profile.metadata["spotify_data"] = data
            
        elif source == "social_media" and data:
            # Extract social media information
            for platform in ["instagram", "tiktok", "twitter"]:
                if f"{platform}_found" in data:
                    profile.social_links[platform] = f"Search found {platform} presence"
            profile.metadata["social_media_data"] = data
            
        elif source == "web_data" and data:
            profile.metadata["web_data"] = data
        
        # Remove duplicates from genres
        profile.genres = list(set(profile.genres))
    
    def _calculate_enrichment_score(self, profile: ArtistProfile) -> float:
        """Calculate enrichment score based on available data"""
        score = 0.0
        max_score = 1.0
        
        # Base score for having a name and YouTube channel
        score += 0.2
        
        # Spotify data
        if profile.spotify_id:
            score += 0.3
        
        # Social media presence
        if profile.social_links:
            score += 0.2 * min(len(profile.social_links) / 3, 1)
        
        # Contact information
        if profile.email:
            score += 0.1
        
        # Genre information
        if profile.genres:
            score += 0.1
        
        # Additional metadata
        if profile.metadata:
            score += 0.1 * min(len(profile.metadata) / 5, 1)
        
        return min(score, max_score)

# Global instance for backward compatibility (but now properly initialized)
_enrichment_agent_instance = None

def get_enrichment_agent() -> ArtistEnrichmentAgent:
    """Get global enrichment agent instance"""
    global _enrichment_agent_instance
    if _enrichment_agent_instance is None:
        _enrichment_agent_instance = ArtistEnrichmentAgent()
    return _enrichment_agent_instance