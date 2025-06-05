# backend/app/agents/enrichment_agent.py
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import Dict, Any, Optional, List
import logging
import base64
import httpx
import json
from datetime import datetime

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile

logger = logging.getLogger(__name__)

# Create Enrichment Agent
enrichment_agent = Agent(
    model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
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
    """
)

@enrichment_agent.tool
async def search_spotify_artist(
    ctx: RunContext[PipelineDependencies],
    artist_name: str
) -> Optional[Dict[str, Any]]:
    """Search for artist on Spotify"""
    try:
        # Get Spotify access token
        auth_url = "https://accounts.spotify.com/api/token"
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": ctx.deps.spotify_client_id,
            "client_secret": ctx.deps.spotify_client_secret
        }
        
        auth_response = await ctx.deps.http_client.post(auth_url, data=auth_data)
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
        
        search_response = await ctx.deps.http_client.get(
            search_url,
            headers=headers,
            params=params
        )
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
        
    except Exception as e:
        logger.error(f"Spotify search error: {e}")
        return None

@enrichment_agent.tool
async def get_spotify_artist_details(
    ctx: RunContext[PipelineDependencies],
    spotify_id: str
) -> Optional[Dict[str, Any]]:
    """Get detailed Spotify artist information"""
    try:
        # Get access token (could cache this)
        auth_url = "https://accounts.spotify.com/api/token"
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": ctx.deps.spotify_client_id,
            "client_secret": ctx.deps.spotify_client_secret
        }
        
        auth_response = await ctx.deps.http_client.post(auth_url, data=auth_data)
        auth_response.raise_for_status()
        access_token = auth_response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Get artist details
        artist_url = f"https://api.spotify.com/v1/artists/{spotify_id}"
        artist_response = await ctx.deps.http_client.get(artist_url, headers=headers)
        artist_response.raise_for_status()
        artist_data = artist_response.json()
        
        # Get top tracks
        tracks_url = f"https://api.spotify.com/v1/artists/{spotify_id}/top-tracks?market=US"
        tracks_response = await ctx.deps.http_client.get(tracks_url, headers=headers)
        tracks_response.raise_for_status()
        tracks_data = tracks_response.json()
        
        return {
            "artist": artist_data,
            "top_tracks": tracks_data["tracks"][:5]  # Top 5 tracks
        }
        
    except Exception as e:
        logger.error(f"Spotify details error: {e}")
        return None

@enrichment_agent.tool
async def extract_web_data_firecrawl(
    ctx: RunContext[PipelineDependencies],
    artist_name: str,
    channel_url: Optional[str] = None
) -> Dict[str, Any]:
    """Use Firecrawl to extract comprehensive artist data"""
    try:
        # Prepare URLs to crawl
        urls = []
        
        # Artist's YouTube channel about page
        if channel_url:
            urls.append(f"{channel_url}/about")
            
        # Google search for artist info
        urls.extend([
            f"https://www.google.com/search?q={artist_name.replace(' ', '+')}+musician+contact+email",
            f"https://www.google.com/search?q={artist_name.replace(' ', '+')}+instagram+music+artist",
            f"https://www.google.com/search?q={artist_name.replace(' ', '+')}+linktr.ee"
        ])
        
        # Firecrawl extract request
        firecrawl_url = "https://api.firecrawl.dev/v1/extract"
        headers = {
            "Authorization": f"Bearer {ctx.deps.firecrawl_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "urls": urls,
            "prompt": f"""Extract comprehensive information about music artist '{artist_name}':
            - Email addresses (booking, management, general contact)
            - Social media profiles (Instagram, TikTok, Twitter/X, Facebook)
            - Website URLs and LinkTree/similar platforms
            - Location (city, country)
            - Genre/music style
            - Brief bio or description
            - Any contact or booking information
            
            Focus on finding verified, official information only.""",
            "schema": {
                "type": "object",
                "properties": {
                    "emails": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "instagram_handle": {"type": "string"},
                    "instagram_url": {"type": "string"},
                    "tiktok_handle": {"type": "string"},
                    "twitter_handle": {"type": "string"},
                    "website": {"type": "string"},
                    "linktr_ee": {"type": "string"},
                    "location": {"type": "string"},
                    "genres": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "bio": {"type": "string"},
                    "booking_info": {"type": "string"}
                }
            },
            "enableWebSearch": True
        }
        
        response = await ctx.deps.http_client.post(
            firecrawl_url,
            headers=headers,
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        
        return response.json().get("data", {})
        
    except Exception as e:
        logger.error(f"Firecrawl extraction error: {e}")
        return {}

@enrichment_agent.tool
async def get_instagram_data(
    ctx: RunContext[PipelineDependencies],
    instagram_handle: str
) -> Optional[Dict[str, Any]]:
    """Get Instagram profile data (using web scraping)"""
    try:
        # Note: Instagram API requires business verification
        # Using Firecrawl for public data extraction
        
        firecrawl_url = "https://api.firecrawl.dev/v1/extract"
        headers = {
            "Authorization": f"Bearer {ctx.deps.firecrawl_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "urls": [f"https://www.instagram.com/{instagram_handle}/"],
            "prompt": "Extract Instagram profile information including follower count, bio, and verified status",
            "schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "full_name": {"type": "string"},
                    "bio": {"type": "string"},
                    "follower_count": {"type": "number"},
                    "following_count": {"type": "number"},
                    "post_count": {"type": "number"},
                    "is_verified": {"type": "boolean"},
                    "profile_pic_url": {"type": "string"}
                }
            }
        }
        
        response = await ctx.deps.http_client.post(
            firecrawl_url,
            headers=headers,
            json=payload,
            timeout=20.0
        )
        
        if response.status_code == 200:
            return response.json().get("data", {})
            
        return None
        
    except Exception as e:
        logger.error(f"Instagram data error: {e}")
        return None

class ArtistEnrichmentAgent:
    """Artist enrichment agent wrapper"""
    
    def __init__(self):
        self.agent = enrichment_agent
        
    async def enrich_artist(
        self,
        deps: PipelineDependencies,
        artist_name: str,
        youtube_channel_id: str,
        youtube_channel_url: str
    ) -> ArtistProfile:
        """Enrich artist profile with multi-platform data"""
        
        logger.info(f"Enriching artist: {artist_name}")
        
        # Initialize artist profile
        profile = ArtistProfile(
            name=artist_name,
            youtube_channel_id=youtube_channel_id,
            youtube_channel_name=artist_name
        )
        
        # Search Spotify
        spotify_data = await search_spotify_artist(
            RunContext(deps=deps, retry=0, tool_name="search_spotify_artist"),
            artist_name=artist_name
        )
        
        if spotify_data:
            profile.spotify_id = spotify_data["spotify_id"]
            profile.genres = spotify_data.get("genres", [])
            profile.follower_counts["spotify"] = spotify_data.get("followers", 0)
            profile.metadata["spotify_popularity"] = spotify_data.get("popularity", 0)
            
        # Extract web data using Firecrawl
        web_data = await extract_web_data_firecrawl(
            RunContext(deps=deps, retry=0, tool_name="extract_web_data_firecrawl"),
            artist_name=artist_name,
            channel_url=youtube_channel_url
        )
        
        if web_data:
            # Process extracted data
            if web_data.get("emails"):
                profile.email = web_data["emails"][0]  # Primary email
                profile.metadata["all_emails"] = web_data["emails"]
                
            if web_data.get("instagram_handle"):
                profile.instagram_handle = web_data["instagram_handle"].replace("@", "")
                
            if web_data.get("website"):
                profile.website = web_data["website"]
                
            if web_data.get("linktr_ee"):
                profile.social_links["linktree"] = web_data["linktr_ee"]
                
            if web_data.get("location"):
                profile.location = web_data["location"]
                
            if web_data.get("bio"):
                profile.bio = web_data["bio"]
                
            # Add any additional genres found
            if web_data.get("genres"):
                profile.genres.extend(web_data["genres"])
                profile.genres = list(set(profile.genres))  # Remove duplicates
                
        # Get Instagram data if handle found
        if profile.instagram_handle:
            ig_data = await get_instagram_data(
                RunContext(deps=deps, retry=0, tool_name="get_instagram_data"),
                instagram_handle=profile.instagram_handle
            )
            
            if ig_data:
                profile.follower_counts["instagram"] = ig_data.get("follower_count", 0)
                profile.metadata["instagram_verified"] = ig_data.get("is_verified", False)
                if not profile.bio and ig_data.get("bio"):
                    profile.bio = ig_data["bio"]
                    
        # Calculate enrichment score
        profile.enrichment_score = self._calculate_enrichment_score(profile)
        
        # Update timestamps
        profile.last_updated = datetime.now()
        
        return profile
        
    def _calculate_enrichment_score(self, profile: ArtistProfile) -> float:
        """Calculate how complete the artist profile is"""
        score = 0.0
        
        # Basic info (40%)
        if profile.youtube_channel_id:
            score += 0.1
        if profile.instagram_handle:
            score += 0.15
        if profile.spotify_id:
            score += 0.15
            
        # Contact info (30%)
        if profile.email:
            score += 0.2
        if profile.website:
            score += 0.1
            
        # Metadata (20%)
        if profile.genres:
            score += 0.1
        if profile.bio and len(profile.bio) > 50:
            score += 0.1
            
        # Social proof (10%)
        if profile.follower_counts.get("instagram", 0) > 1000:
            score += 0.05
        if profile.follower_counts.get("spotify", 0) > 1000:
            score += 0.05
            
        return min(score, 1.0)