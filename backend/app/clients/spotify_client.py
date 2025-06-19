"""
Spotify API Client
Handles authentication and API calls to Spotify Web API for artist data
"""
import asyncio
import base64
import json
import logging
import time
from typing import Dict, List, Optional, Any
import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)

class SpotifyAPIClient:
    """Spotify Web API client with token management"""
    
    def __init__(self):
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.access_token = None
        self.token_expires_at = 0
        self.base_url = "https://api.spotify.com/v1"
        
        if not self.client_id or not self.client_secret:
            logger.warning("⚠️ Spotify API credentials not configured")
            
    async def _get_access_token(self) -> Optional[str]:
        """Get access token using client credentials flow"""
        if not self.client_id or not self.client_secret:
            logger.error("❌ Spotify credentials not configured")
            return None
            
        # Check if current token is still valid
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
            
        try:
            # Prepare credentials
            credentials = f"{self.client_id}:{self.client_secret}"
            credentials_b64 = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {credentials_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {"grant_type": "client_credentials"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://accounts.spotify.com/api/token",
                    headers=headers,
                    data=data
                ) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data["access_token"]
                        # Set expiration with 5 minute buffer
                        self.token_expires_at = time.time() + token_data["expires_in"] - 300
                        logger.info("✅ Spotify access token refreshed")
                        return self.access_token
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Spotify token request failed: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Spotify token request exception: {e}")
            return None
    
    async def _make_api_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated API request to Spotify"""
        token = await self._get_access_token()
        if not token:
            return None
            
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        # Rate limited
                        retry_after = int(response.headers.get('Retry-After', 1))
                        logger.warning(f"⚠️ Spotify rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        return await self._make_api_request(endpoint, params)
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Spotify API error: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Spotify API request exception: {e}")
            return None
    
    async def search_artist(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Search for artist by name"""
        if not artist_name:
            return None
            
        params = {
            "q": artist_name,
            "type": "artist",
            "limit": 1
        }
        
        result = await self._make_api_request("search", params)
        if result and "artists" in result and result["artists"]["items"]:
            artist = result["artists"]["items"][0]
            logger.info(f"✅ Found Spotify artist: {artist['name']} ({artist['id']})")
            return artist
        
        logger.warning(f"⚠️ No Spotify artist found for: {artist_name}")
        return None
    
    async def get_artist_details(self, artist_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed artist information by Spotify ID"""
        if not artist_id:
            return None
            
        result = await self._make_api_request(f"artists/{artist_id}")
        if result:
            logger.info(f"✅ Retrieved artist details for ID: {artist_id}")
            return result
        
        logger.warning(f"⚠️ Could not retrieve artist details for ID: {artist_id}")
        return None
    
    async def get_artist_top_tracks(self, artist_id: str, market: str = "US") -> List[Dict[str, Any]]:
        """Get artist's top tracks"""
        if not artist_id:
            return []
            
        params = {"market": market}
        result = await self._make_api_request(f"artists/{artist_id}/top-tracks", params)
        
        if result and "tracks" in result:
            tracks = result["tracks"]
            logger.info(f"✅ Retrieved {len(tracks)} top tracks for artist: {artist_id}")
            return tracks
        
        logger.warning(f"⚠️ Could not retrieve top tracks for artist: {artist_id}")
        return []
    
    async def get_artist_albums(self, artist_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get artist's albums"""
        if not artist_id:
            return []
            
        params = {
            "include_groups": "album,single",
            "market": "US",
            "limit": limit
        }
        
        result = await self._make_api_request(f"artists/{artist_id}/albums", params)
        
        if result and "items" in result:
            albums = result["items"]
            logger.info(f"✅ Retrieved {len(albums)} albums for artist: {artist_id}")
            return albums
        
        logger.warning(f"⚠️ Could not retrieve albums for artist: {artist_id}")
        return []
    
    async def get_enriched_artist_data(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive artist data including avatar and genres"""
        try:
            # Search for artist
            artist = await self.search_artist(artist_name)
            if not artist:
                return None
            
            artist_id = artist["id"]
            
            # Get detailed artist info (includes genres, images, followers)
            details = await self.get_artist_details(artist_id)
            if not details:
                return None
            
            # Get top tracks
            top_tracks = await self.get_artist_top_tracks(artist_id)
            
            # Extract avatar URL (highest resolution image)
            avatar_url = None
            if details.get("images"):
                # Sort by size (width) and take the largest
                images = sorted(details["images"], key=lambda x: x.get("width", 0), reverse=True)
                avatar_url = images[0]["url"] if images else None
            
            # Extract genres
            genres = details.get("genres", [])
            
            enriched_data = {
                "spotify_id": artist_id,
                "name": details["name"],
                "avatar_url": avatar_url,
                "genres": genres,
                "followers": details.get("followers", {}).get("total", 0),
                "popularity": details.get("popularity", 0),
                "external_urls": details.get("external_urls", {}),
                "top_tracks": [
                    {
                        "name": track["name"],
                        "id": track["id"],
                        "preview_url": track.get("preview_url"),
                        "popularity": track.get("popularity", 0)
                    }
                    for track in top_tracks[:5]  # Top 5 tracks
                ]
            }
            
            logger.info(f"✅ Enriched Spotify data for {artist_name}: {len(genres)} genres, avatar: {'✓' if avatar_url else '✗'}")
            return enriched_data
            
        except Exception as e:
            logger.error(f"❌ Error enriching Spotify data for {artist_name}: {e}")
            return None

# Global client instance
_spotify_client = None

def get_spotify_client() -> SpotifyAPIClient:
    """Get global Spotify client instance"""
    global _spotify_client
    if _spotify_client is None:
        _spotify_client = SpotifyAPIClient()
    return _spotify_client